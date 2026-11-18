from http.cookiejar import CookieJar
from json import dumps, loads
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener


class ReleaseSmokeTest(unittest.TestCase):
    def test_page_login_and_note_lifecycle(self):
        source = Path(__file__).resolve().parent
        dist = source.parent / 'frontend' / 'dist'
        self.assertTrue((dist / 'index.html').is_file(), 'Run npm run build first')
        with tempfile.TemporaryDirectory() as folder:
            isolated = Path(folder)
            backend = isolated / 'preview-backend'
            backend.mkdir()
            for name in ('main.py', 'local_auth.py', 'record_export.py', 'excel_export.py', 'attachments.py'):
                shutil.copy2(source / name, backend)
            shutil.copytree(dist, isolated / 'frontend' / 'dist')
            log_path = isolated / 'server.log'
            with log_path.open('wb') as log:
                server = subprocess.Popen(
                    [sys.executable, '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '0'],
                    cwd=backend, stdout=log, stderr=subprocess.STDOUT,
                )
                try:
                    self.check_release(server, log_path)
                finally:
                    if server.poll() is None:
                        if sys.platform == 'win32':
                            subprocess.run(['taskkill', '/PID', str(server.pid), '/T', '/F'],
                                           capture_output=True, timeout=10, check=True)
                        else:
                            server.terminate()
                    server.wait(timeout=10)

    def check_release(self, server, log_path):
        port = None
        for _ in range(100):
            log = log_path.read_text(encoding='utf-8', errors='replace')
            match = re.search(r'Uvicorn running on http://127\.0\.0\.1:(\d+)', log)
            if match:
                port = match[1]
                break
            if server.poll() is not None:
                break
            time.sleep(0.1)
        self.assertIsNotNone(port, log)
        origin = f'http://127.0.0.1:{port}'
        browser = build_opener(HTTPCookieProcessor(CookieJar()))

        def request(path, method='GET', data=None):
            req = Request(origin + path, method=method, data=dumps(data).encode() if data is not None else None,
                          headers={'Origin': 'http://127.0.0.1:18766', 'Content-Type': 'application/json'})
            with browser.open(req, timeout=5) as response:
                body = response.read()
                return loads(body) if response.headers.get_content_type() == 'application/json' else body

        page = request('/').decode()
        script = re.search(r'src="(/assets/[^"]+\.js)"', page)
        self.assertIsNotNone(script)
        self.assertTrue(request(script[1]))
        self.assertTrue(request('/api/auth/status')['needs_setup'])
        password = {'password': 'isolated-smoke-check'}
        self.assertTrue(request('/api/auth/setup', 'POST', password)['authenticated'])
        note = request('/api/records', 'POST', {'content': '隔离环境测试笔记'})['record']
        endpoint = f"/api/records/{note['id']}"
        edited = request(endpoint, 'PUT', {'content': '已更新的测试笔记'})['record']
        self.assertEqual(edited['content'], '已更新的测试笔记')
        request(endpoint, 'DELETE')
        request(endpoint + '/restore', 'POST')
        request('/api/auth/logout', 'POST')
        with self.assertRaises(HTTPError) as blocked:
            request('/api/records')
        self.assertEqual(blocked.exception.code, 401)
        self.assertTrue(request('/api/auth/login', 'POST', password)['authenticated'])


if __name__ == '__main__':
    unittest.main()
