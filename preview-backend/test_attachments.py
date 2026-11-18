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
from main import app, create_record, update_record, delete_record, restore_record, permanently_delete_record, get_db, RecordCreate, RecordUpdate, DATA_DIR, DB_PATH, require_session
from attachments import StorageLocation, attachment_router, stored_name
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
browse = endpoint('/api/settings/attachment-folders', 'GET')
assert browse('')['folders']
browsing_root = Path.cwd()
(browsing_root / '资料').mkdir()
listing = browse(str(browsing_root))
assert listing['parent'] == str(browsing_root.parent)
assert {'name': '资料', 'path': str(browsing_root / '资料')} in listing['folders']
assert not any(folder['name'] == 'main.py' for folder in listing['folders'])
try:
    browse('relative')
except HTTPException as error:
    assert error.status_code == 400
else:
    raise AssertionError('folder browser accepted a relative path')
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
original_root = DATA_DIR / 'attachments'
assert Path(serve(first['id']).path).name == f"example-{first['id']}.pdf"
Path(serve(first['id']).path).rename(original_root / first['id'])
assert Path(serve(first['id']).path).name == first['id']
assert migrate(StorageLocation(path=str(original_root)))['copied'] == 1
assert not (original_root / first['id']).exists()
assert Path(serve(first['id']).path).name == f"example-{first['id']}.pdf"
(original_root / stored_name(first)).rename(original_root / first['id'])
(original_root / 'unrelated.txt').write_text('keep')
trash_attachment = endpoint('/api/attachments/{key}/trash', 'POST')
restore_attachment = endpoint('/api/attachments/{key}/restore', 'POST')
purge_attachment = endpoint('/api/attachments/{key}', 'DELETE')
trash_attachment(second['id'])
assert Path(serve(second['id'], trash=True).path).read_bytes() == b'example bytes'
assert len(list_files(note['id'])['attachments']) == 1
assert list_files(trash=True)['attachments'][0]['id'] == second['id']
assert migrate(StorageLocation(path=str(destination)))['cleanup_remaining'] == 0
assert not (original_root / first['id']).exists()
assert not (original_root / stored_name(second)).exists()
assert (original_root / 'unrelated.txt').read_text() == 'keep'
assert (destination / stored_name(second)).is_file()
restore_attachment(second['id'])
assert len(list_files(note['id'])['attachments']) == 2
try:
    purge_attachment(second['id'])
except HTTPException as error:
    assert error.status_code == 409
else:
    raise AssertionError('active attachment was purged')
assert Path(serve(first['id']).path).parent == destination
nested = destination / '新的附件目录'
assert migrate(StorageLocation(path=f' "{nested}" '))['copied'] == 2
assert Path(serve(first['id']).path).parent == nested
assert not (destination / stored_name(first)).exists()
assert migrate(StorageLocation(path=''))['copied'] == 2
assert Path(serve(first['id']).path).parent == DATA_DIR / 'attachments'
delete_record(note['id'])
assert all(file['deleted_at'] for file in list_files()['attachments'])
restore_record(note['id'])
assert all(not file['deleted_at'] for file in list_files(note['id'])['attachments'])
try:
    permanently_delete_record(note['id'])
except HTTPException as error:
    assert error.status_code == 404
else:
    raise AssertionError('active note was permanently deleted')
delete_record(note['id'])
assert permanently_delete_record(note['id'])['deleted_id'] == note['id']
assert all(file['record_id'] is None for file in list_files()['attachments'])
backup = endpoint('/api/settings/full-backup', 'GET')()
with ZipFile(backup.path) as archive:
    assert archive.testzip() is None
    assert archive.read('attachments/' + stored_name(first)) == b'example bytes'
    Path('restored.db').write_bytes(archive.read('zhiji.db'))
with sqlite3.connect('restored.db') as db:
    assert db.execute('SELECT count(*) FROM attachments').fetchone()[0] == 2
    assert db.execute('SELECT count(*) FROM attachment_storage').fetchone()[0] == 0
backup.background.func()
trash_attachment(second['id'])
purge_attachment(second['id'])
assert not (original_root / stored_name(second)).exists()
assert not list_files(trash=True)['attachments']
'''
            result = subprocess.run([sys.executable, '-X', 'utf8', '-c', program], cwd=folder,
                                    capture_output=True, text=True, encoding='utf-8', timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
