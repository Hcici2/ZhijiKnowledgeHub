import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AttachmentTest(unittest.TestCase):
    def test_attachment_lifecycle_and_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(__file__).resolve().parent
            for name in ('main.py', 'local_auth.py', 'record_export.py', 'excel_export.py', 'attachments.py'):
                shutil.copy2(source / name, folder)
            program = r'''
import sqlite3
from pathlib import Path
from zipfile import ZipFile
from fastapi import HTTPException
from main import app, create_record, update_record, delete_record, restore_record, get_db, RecordCreate, RecordUpdate, DATA_DIR, DB_PATH, require_session
from attachments import StorageLocation, attachment_router
import attachments

async def direct_call(function, *args):
    return function(*args)

attachments.run_in_threadpool = direct_call

router = attachment_router(get_db, require_session, DATA_DIR, DB_PATH)
assert 'post' in app.openapi()['paths']['/api/attachments']

def endpoint(path, method):
    return next(route.endpoint for route in router.routes if route.path == path and method in route.methods)

class Body:
    async def stream(self):
        yield b'example'
        yield b' bytes'

def complete(coroutine):
    try:
        coroutine.send(None)
    except StopIteration as finished:
        return finished.value
    raise AssertionError('test upload unexpectedly blocked')

upload = endpoint('/api/attachments', 'POST')
list_files = endpoint('/api/attachments', 'GET')
serve = endpoint('/api/attachments/{key}/file', 'GET')
migrate = endpoint('/api/settings/attachment-storage', 'PUT')
first = complete(upload(Body(), 'docs/example.pdf'))
note = create_record(RecordCreate(content='带附件的笔记', attachment_ids=[first['id']]))['record']
second = complete(upload(Body(), 'example.html'))
update_record(note['id'], RecordUpdate(attachment_ids=[second['id']]))
assert len(list_files(note['id'])['attachments']) == 2
try:
    create_record(RecordCreate(content='should rollback', attachment_ids=[first['id']]))
except HTTPException as error:
    assert error.status_code == 409
else:
    raise AssertionError('reusing a linked attachment should fail')
with get_db() as db:
    assert db.execute('SELECT count(*) FROM records').fetchone()[0] == 1
assert serve(first['id'], True).media_type == 'application/pdf'
assert serve(second['id'], True).headers['content-disposition'].startswith('attachment')
assert Path(serve(first['id']).path).read_bytes() == b'example bytes'
destination = Path.cwd() / 'relocated'
destination.mkdir()
(destination / first['id']).write_bytes(b'conflict')
try:
    migrate(StorageLocation(path=str(destination)))
except HTTPException as error:
    assert error.status_code == 409
else:
    raise AssertionError('migration must not overwrite files')
assert Path(serve(first['id']).path).parent != destination
assert (destination / first['id']).read_bytes() == b'conflict'
(destination / first['id']).unlink()
assert migrate(StorageLocation(path=str(destination)))['copied'] == 2
assert Path(serve(first['id']).path).parent == destination
delete_record(note['id'])
assert all(file['deleted_at'] for file in list_files()['attachments'])
restore_record(note['id'])
assert all(not file['deleted_at'] for file in list_files(note['id'])['attachments'])
with get_db() as db:
    db.execute('DELETE FROM records WHERE id=?', [note['id']])
assert all(file['record_id'] is None for file in list_files()['attachments'])
backup = endpoint('/api/settings/full-backup', 'GET')()
with ZipFile(backup.path) as archive:
    assert archive.testzip() is None
    assert archive.read('attachments/' + first['id']) == b'example bytes'
    Path('restored.db').write_bytes(archive.read('zhiji.db'))
with sqlite3.connect('restored.db') as db:
    assert db.execute('SELECT count(*) FROM attachments').fetchone()[0] == 2
    assert db.execute('SELECT count(*) FROM attachment_storage').fetchone()[0] == 0
backup.background.func()
'''
            result = subprocess.run([sys.executable, '-X', 'utf8', '-c', program], cwd=folder,
                                    capture_output=True, text=True, encoding='utf-8', timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
