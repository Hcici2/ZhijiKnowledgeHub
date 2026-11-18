from contextlib import closing
from hashlib import file_digest
from pathlib import Path
from threading import Lock
from uuid import uuid4
from zipfile import ZipFile
import json
import shutil
import sqlite3
import tempfile

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask


MAX_BYTES = 250 * 1024 * 1024
PREVIEW_TYPES = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
    '.gif': 'image/gif', '.webp': 'image/webp', '.pdf': 'application/pdf',
    '.mp4': 'video/mp4', '.webm': 'video/webm',
}


def init_attachments(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS attachments (
        id TEXT PRIMARY KEY, record_id INTEGER REFERENCES records(id) ON DELETE SET NULL,
        name TEXT NOT NULL, size INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute('CREATE INDEX IF NOT EXISTS attachments_record ON attachments(record_id)')
    conn.execute('CREATE TABLE IF NOT EXISTS attachment_storage (id INTEGER PRIMARY KEY CHECK(id=1), path TEXT NOT NULL)')


def attach_files(conn, record_id, ids):
    ids = list(dict.fromkeys(ids))
    if not ids:
        return
    markers = ','.join('?' for _ in ids)
    updated = conn.execute(
        f'UPDATE attachments SET record_id=? WHERE record_id IS NULL AND id IN ({markers})',
        [record_id, *ids],
    )
    if updated.rowcount != len(ids):
        raise HTTPException(409, '有附件已关联到其他笔记或找不到，请重新选择。')


class StorageLocation(BaseModel):
    path: str = Field(max_length=1024)


def attachment_router(get_db, require_session, data_dir, db_path):
    router = APIRouter(prefix='/api', dependencies=[Depends(require_session)])
    lock = Lock()
    default_root = data_dir / 'attachments'

    def root(conn):
        row = conn.execute('SELECT path FROM attachment_storage WHERE id=1').fetchone()
        return Path(row['path']) if row else default_root

    def finish_upload(path, name, size):
        key = uuid4().hex
        with lock:
            target = None
            created = False
            try:
                with get_db() as conn:
                    directory = root(conn)
                    directory.mkdir(parents=True, exist_ok=True)
                    target = directory / key
                    with path.open('rb') as source, target.open('xb') as output:
                        created = True
                        shutil.copyfileobj(source, output)
                    conn.execute('INSERT INTO attachments(id,name,size) VALUES (?,?,?)', (key, name, size))
            except (OSError, sqlite3.Error) as error:
                if created and target:
                    try:
                        target.unlink(missing_ok=True)
                    except OSError:
                        pass
                raise HTTPException(507, '无法保存附件，请检查存储目录和磁盘空间。') from error
        return {'id': key, 'name': name, 'size': size}

    @router.post('/attachments', status_code=201)
    async def upload(request: Request, name: str):
        name = name.replace('\\', '/').rsplit('/', 1)[-1].strip()
        if not name or len(name) > 240 or any(ord(char) < 32 for char in name):
            raise HTTPException(400, '文件名无效或过长。')
        size = 0
        with tempfile.TemporaryDirectory(dir=data_dir) as staging:
            path = Path(staging) / 'upload'
            with path.open('wb') as output:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise HTTPException(413, '单个附件不能超过 250 MB。')
                    output.write(chunk)
            return await run_in_threadpool(finish_upload, path, name, size)

    @router.get('/attachments')
    def list_files(record_id: int | None = None):
        filters = 'WHERE a.record_id=?' if record_id is not None else ''
        with get_db() as conn:
            rows = conn.execute(f"""SELECT a.*, r.deleted_at, r.note_date,
                COALESCE(NULLIF(TRIM(r.title), ''), substr(r.content,1,60)) AS record_title
                FROM attachments a LEFT JOIN records r ON a.record_id=r.id
                {filters} ORDER BY a.created_at DESC, a.id DESC""",
                (record_id,) if record_id is not None else ()).fetchall()
        return {'attachments': [dict(row) for row in rows]}

    @router.get('/attachments/{key}/file')
    def serve_file(key: str, preview: bool = False):
        with get_db() as conn:
            row = conn.execute('SELECT * FROM attachments WHERE id=?', (key,)).fetchone()
            if not row:
                raise HTTPException(404, '附件不存在。')
            path = root(conn) / row['id']
        if not path.is_file():
            raise HTTPException(404, '附件文件找不到，请检查存储位置。')
        media = PREVIEW_TYPES.get(Path(row['name']).suffix.lower()) if preview else None
        return FileResponse(path, media_type=media or 'application/octet-stream', filename=row['name'],
                            content_disposition_type='inline' if media else 'attachment',
                            headers={'X-Content-Type-Options': 'nosniff'})

    @router.get('/settings/attachment-storage')
    def get_storage():
        with get_db() as conn:
            return {'path': str(root(conn)), 'default_path': str(default_root)}

    @router.put('/settings/attachment-storage')
    def change_storage(settings: StorageLocation):
        requested = Path(settings.path.strip()) if settings.path.strip() else default_root
        if not requested.is_absolute() or requested.drive.startswith('\\'):
            raise HTTPException(400, '请输入本地文件夹的完整路径。')
        with lock, get_db() as conn:
            current = root(conn).resolve()
            destination = requested.resolve()
            if destination == current:
                return {'path': str(current), 'copied': 0}
            if destination in current.parents or current in destination.parents:
                raise HTTPException(400, '请选择与当前目录独立的文件夹。')
            ids = [row['id'] for row in conn.execute('SELECT id FROM attachments')]
            created = []
            try:
                destination.mkdir(parents=True, exist_ok=True)
                for key in ids:
                    source, target = current / key, destination / key
                    if target.exists():
                        with source.open('rb') as original, target.open('rb') as copied:
                            if file_digest(original, 'sha256').digest() != file_digest(copied, 'sha256').digest():
                                raise OSError('destination conflict')
                        continue
                    with source.open('rb') as original, target.open('xb') as copied:
                        created.append(target)
                        shutil.copyfileobj(original, copied)
                    with source.open('rb') as original, target.open('rb') as copied:
                        if file_digest(original, 'sha256').digest() != file_digest(copied, 'sha256').digest():
                            raise OSError('verification failure')
                conn.execute('INSERT OR REPLACE INTO attachment_storage(id,path) VALUES (1,?)', (str(destination),))
                conn.commit()
            except (OSError, sqlite3.Error) as error:
                for path in created:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        pass
                raise HTTPException(409, '迁移未完成。请检查目录权限、空间和原附件，当前存储位置保持不变。') from error
        return {'path': str(destination), 'copied': len(created)}

    @router.get('/settings/full-backup')
    def full_backup():
        folder = tempfile.TemporaryDirectory(dir=data_dir)
        directory = Path(folder.name)
        database, archive = directory / 'zhiji.db', directory / 'zhiji-backup.zip'
        try:
            with lock, closing(sqlite3.connect(db_path)) as source, closing(sqlite3.connect(database)) as snapshot:
                source.backup(snapshot)
                snapshot.row_factory = sqlite3.Row
                attachment_root = root(snapshot)
                snapshot.execute('DELETE FROM attachment_storage')
                snapshot.commit()
                if snapshot.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise OSError('invalid database snapshot')
                rows = snapshot.execute('SELECT id, name, size FROM attachments').fetchall()
                with ZipFile(archive, 'w') as backup:
                    backup.write(database, 'zhiji.db')
                    for row in rows:
                        stored = attachment_root / row['id']
                        if stored.stat().st_size != row['size']:
                            raise OSError('attachment size mismatch')
                        backup.write(stored, 'attachments/' + row['id'])
                    backup.writestr('attachments.json', json.dumps([dict(row) for row in rows], ensure_ascii=False, indent=2))
                    account = data_dir / 'account.sqlite3'
                    if account.is_file():
                        account_snapshot = directory / account.name
                        with closing(sqlite3.connect(account)) as account_source, closing(sqlite3.connect(account_snapshot)) as account_copy:
                            account_source.backup(account_copy)
                            if account_copy.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                                raise OSError('invalid account snapshot')
                        backup.write(account_snapshot, account.name)
                    backup.writestr('恢复说明.txt', '关闭知己后，先另存当前 data 目录。将备份里的 zhiji.db、attachments 文件夹（有附件时）和 account.sqlite3（如有）放到原 data 目录，再启动知己。恢复的数据库会使用默认附件目录。')
        except (OSError, sqlite3.Error) as error:
            folder.cleanup()
            raise HTTPException(409, '无法生成完整备份，请检查附件是否齐全及磁盘空间。') from error
        return FileResponse(archive, media_type='application/zip', filename='知己-笔记与附件.zip', background=BackgroundTask(folder.cleanup))

    return router
