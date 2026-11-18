
from datetime import date, datetime
from contextlib import asynccontextmanager, closing, contextmanager, suppress
import asyncio
import logging
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit
import sqlite3
import json
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from local_auth import build_auth
from attachments import init_attachments, attach_files, attachment_router
from record_export import render_export
from pydantic import BaseModel, Field


# ==============================
# 1. 创建知己后台
# ==============================

@asynccontextmanager
async def lifespan(app):
    async def maintain_trash():
        while True:
            try:
                await asyncio.to_thread(purge_expired_trash)
            except sqlite3.Error:
                logging.getLogger(__name__).exception("Unable to clean expired trash")
            await asyncio.sleep(3600)

    cleanup = asyncio.create_task(maintain_trash())
    try:
        yield
    finally:
        cleanup.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup


app = FastAPI(
    title="知己个人知识管理系统",
    description="知己 Knowledge Hub V1.0 后台服务",
    version="1.0.0",
    lifespan=lifespan,
)


# ==============================
# 2. 配置前端访问权限
# ==============================

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])


@app.middleware("http")
async def protect_browser_requests(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
        if request.headers.get("origin") not in {
            "http://127.0.0.1:8765", "http://localhost:5173", "http://127.0.0.1:5173",
            "http://127.0.0.1:18766",
        } or request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "请从本机知己页面操作。"}, status_code=403)
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# ==============================
# 3. 设置本地数据库位置
# ==============================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"

DB_PATH = DATA_DIR / "zhiji.db"

# 如果 data 文件夹不存在，就自动创建
DATA_DIR.mkdir(parents=True, exist_ok=True)
auth_router, require_session = build_auth(DATA_DIR)
app.include_router(auth_router)
frontend_dist = BASE_DIR.parent / "frontend" / "dist"


# ==============================
# 4. 初始化数据库
# ==============================


def init_db():
    # Back up existing user data before the additive task scheduling migration.
    if DB_PATH.exists():
        with closing(sqlite3.connect(DB_PATH)) as source:
            columns = {row[1] for row in source.execute("PRAGMA table_info(note_tasks)")}
            if columns and not {"due_time", "priority"}.issubset(columns):
                backup_dir = DB_PATH.parent / "backups"
                backup_dir.mkdir(exist_ok=True)
                backup_path = backup_dir / ("before-task-planning-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".db")
                with closing(sqlite3.connect(backup_path)) as target:
                    source.backup(target)
    conn = sqlite3.connect(DB_PATH)

    try:
        with conn:
            # 第一次运行时创建基础数据表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '待整理',
                    created_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS saved_searches (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    view TEXT NOT NULL,
                    category TEXT NOT NULL,
                    keyword TEXT NOT NULL
                )
            """)

            conn.execute("CREATE TABLE IF NOT EXISTS categories (name TEXT PRIMARY KEY)")
            init_attachments(conn)
            conn.execute("""CREATE TABLE IF NOT EXISTS note_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
                category TEXT NOT NULL, content TEXT NOT NULL
            )""")
            conn.execute("""
                INSERT OR IGNORE INTO categories (name)
                SELECT DISTINCT category FROM records WHERE trim(category) <> ''
            """)

            saved_columns = {row[1] for row in conn.execute("PRAGMA table_info(saved_searches)")}
            if "tag" not in saved_columns:
                conn.execute("ALTER TABLE saved_searches ADD COLUMN tag TEXT NOT NULL DEFAULT ''")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS trash_policy (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1))
                )
            """)
            conn.execute("INSERT OR IGNORE INTO trash_policy (id, enabled) VALUES (1, 0)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS record_links (
                    source_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
                    target_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
                    PRIMARY KEY (source_id, target_id),
                    CHECK (source_id <> target_id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS record_links_target ON record_links(target_id)")

            for column in ("date_from", "date_to"):
                if column not in saved_columns:
                    conn.execute(f"ALTER TABLE saved_searches ADD COLUMN {column} TEXT")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS record_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
                    captured_at TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    category TEXT NOT NULL,
                    tags TEXT NOT NULL
                )
            """)
            version_columns = {row[1] for row in conn.execute("PRAGMA table_info(record_versions)")}
            if "note_date" not in version_columns:
                conn.execute("ALTER TABLE record_versions ADD COLUMN note_date TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS record_versions_record ON record_versions(record_id, id DESC)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_reviews (
                    day TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS note_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    due_date TEXT,
                    completed_at TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS note_tasks_record ON note_tasks(record_id)")
            task_columns = {row[1] for row in conn.execute("PRAGMA table_info(note_tasks)")}
            if "due_time" not in task_columns:
                conn.execute("ALTER TABLE note_tasks ADD COLUMN due_time TEXT")
            if "priority" not in task_columns:
                conn.execute("ALTER TABLE note_tasks ADD COLUMN priority INTEGER NOT NULL DEFAULT 0")

            # 读取当前已经存在的字段
            existing_columns = {
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(records)"
                ).fetchall()
            }

            # 准备新增的字段
            new_columns = {
                "pinned": "INTEGER NOT NULL DEFAULT 0",
                "note_date": "TEXT",
                "deleted_at": "TEXT",
                "title": "TEXT NOT NULL DEFAULT ''",
                "summary": "TEXT NOT NULL DEFAULT ''",
                "tags": "TEXT NOT NULL DEFAULT '[]'",
                "source_type": "TEXT NOT NULL DEFAULT '文本'",
                "ai_status": "TEXT NOT NULL DEFAULT 'not_started'",
                "ai_error": "TEXT NOT NULL DEFAULT ''",
                "updated_at": "TEXT NOT NULL DEFAULT ''"
            }

            # 只增加不存在的字段，避免重复添加
            added_columns = []

            for column, definition in new_columns.items():
                if column not in existing_columns:
                    conn.execute(
                        f"ALTER TABLE records ADD COLUMN {column} {definition}"
                    )
                    added_columns.append(column)

            # 为以前的记录补充更新时间
            conn.execute("""
                UPDATE records
                SET updated_at = created_at
                WHERE updated_at = ''
            """)

        if added_columns:
            print(
                "数据库升级成功，新增字段："
                + "、".join(added_columns)
            )
        else:
            print("数据库结构已经是最新版本。")

    finally:
        conn.close()


# 启动后台时自动检查数据库
init_db()


# ==============================
# 5. 定义记录输入格式
# ==============================

class RecordCreate(BaseModel):
    note_date: date | None = None
    title: str = Field(default="", max_length=200)
    category: str = Field(default="待整理", max_length=50)
    content: str = Field(min_length=1, max_length=10000)
    attachment_ids: list[str] = Field(default_factory=list, max_length=50)

# 修改记录时允许提交的字段
class RecordUpdate(BaseModel):
    note_date: date | None = None
    pinned: bool | None = None
    content: str | None = Field(default=None, max_length=10000)
    title: str | None = Field(default=None, max_length=200)
    summary: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, max_length=50)
    tags: list[str] | None = None
    attachment_ids: list[str] = Field(default_factory=list, max_length=50)


# ==============================
# 6. 获取数据库连接
# ==============================


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        yield conn
        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


app.include_router(attachment_router(get_db, require_session, DATA_DIR, DB_PATH))



# ==============================
# 7. 首页测试接口
# ==============================

@app.get("/")
async def home():
    index = frontend_dist / "index.html"
    if index.is_file():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return {
        "success": True,
        "message": "欢迎使用知己！后台服务运行正常。",
        "version": "1.0.0"
    }


# ==============================
# 8. 后台健康检查
# ==============================

@app.get("/api/health")
async def health_check():
    return {
        "success": True,
        "message": "知己后台运行正常",
        "service": "知己 Knowledge Hub",
        "desktop_ready": (frontend_dist / "index.html").is_file(),
        "desktop_instance": getattr(app.state, "desktop_instance", "")
    }


# ==============================
# 9. 保存一条记录
# ==============================

def insert_record(conn, record: RecordCreate):
    content = record.content.strip()
    if not content:
        raise HTTPException(400, "记录内容不能为空。")
    title = record.title.strip()
    category = record.category.strip() or "待整理"
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (category,))
    note_date = record.note_date.isoformat() if record.note_date else None
    cursor = conn.execute("""
        INSERT INTO records (content, category, created_at, title, updated_at, note_date)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (content, category, created_at, title, created_at, note_date))
    return {"id": cursor.lastrowid, "content": content, "category": category,
            "title": title, "created_at": created_at, "note_date": note_date}


@app.post("/api/records", dependencies=[Depends(require_session)])
def create_record(record: RecordCreate):
    with get_db() as conn:
        saved = insert_record(conn, record)
        attach_files(conn, saved['id'], record.attachment_ids)
    return {"success": True, "message": "记录已成功保存", "record": saved}


class RecordImport(BaseModel):
    records: list[RecordCreate] = Field(min_length=1, max_length=30)


@app.post("/api/records/import", dependencies=[Depends(require_session)])
def import_records(batch: RecordImport):
    imported = 0
    skipped = 0
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        for record in batch.records:
            content = record.content.strip()
            if not content:
                raise HTTPException(400, "导入文件的正文不能为空。")
            existing = conn.execute(
                "SELECT 1 FROM records WHERE deleted_at IS NULL AND content = ? LIMIT 1", (content,)
            ).fetchone()
            if existing:
                skipped += 1
            else:
                insert_record(conn, record)
                imported += 1
    return {"imported": imported, "skipped": skipped}


# ==============================
# 10. 获取历史记录
# ==============================

@app.get("/api/records", dependencies=[Depends(require_session)])
def get_records():

    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, content, category, created_at, title, summary, tags, pinned, note_date
            FROM records
            WHERE deleted_at IS NULL
            ORDER BY pinned DESC, id DESC
            LIMIT 100
            """
        ).fetchall()

    records = [dict(row) for row in rows]

    return {
        "success": True,
        "total": len(records),
        "records": records
    }

# ==============================
# 修改已有记录
# ==============================

VERSION_FIELDS = ("title", "content", "summary", "category", "tags", "note_date")


def save_record_version(conn, record, captured_at):
    conn.execute("""
        INSERT INTO record_versions (record_id, captured_at, title, content, summary, category, tags, note_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (record["id"], captured_at, *(record[field] for field in VERSION_FIELDS)))


@app.put("/api/records/{record_id}", dependencies=[Depends(require_session)])
def update_record(record_id: int, record: RecordUpdate):

    updates = record.model_dump(exclude_unset=True)
    attachment_ids = updates.pop('attachment_ids', [])
    if updates.get("note_date") is not None:
        updates["note_date"] = updates["note_date"].isoformat()
    if "pinned" in updates and updates["pinned"] is None:
        raise HTTPException(400, "置顶状态不能为空。")

    if not updates and not attachment_ids:
        raise HTTPException(
            status_code=400,
            detail="没有提供需要修改的内容"
        )

    # 检查文字内容
    for field in ("content", "title", "summary", "category"):
        if field in updates:
            value = updates[field]

            if value is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"{field} 不能设置为空值"
                )

            value = value.strip()

            if field in ("content", "category") and not value:
                raise HTTPException(
                    status_code=400,
                    detail=f"{field} 不能为空"
                )

            updates[field] = value

    # 将标签列表转换为 JSON 字符串
    if "tags" in updates:
        if updates["tags"] is None:
            raise HTTPException(
                status_code=400,
                detail="标签不能设置为空值，请使用空列表清空标签"
            )

        clean_tags = []

        for tag in updates["tags"]:
            tag = tag.strip()

            if tag and tag not in clean_tags:
                clean_tags.append(tag)

        updates["tags"] = json.dumps(
            clean_tags,
            ensure_ascii=False
        )

    # 更新修改时间
    updates["updated_at"] = datetime.now().astimezone().isoformat(
        timespec="seconds"
    )

    # 生成数据库更新语句
    set_clause = ", ".join(
        f"{field} = ?" for field in updates
    )

    values = list(updates.values()) + [record_id]

    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        previous = active_record(conn, record_id)
        attach_files(conn, record_id, attachment_ids)
        if any(field in updates and updates[field] != previous[field] for field in VERSION_FIELDS):
            save_record_version(conn, previous, updates["updated_at"])

        conn.execute(f"UPDATE records SET {set_clause} WHERE id = ?", values)

        if "category" in updates:
            conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (updates["category"],))

        updated_record = conn.execute(
            """
            SELECT *
            FROM records
            WHERE id = ?
            """,
            (record_id,)
        ).fetchone()

    return {
        "success": True,
        "message": "记录修改成功",
        "record": dict(updated_record)
    }

# ==============================
# 删除指定记录
# ==============================

@app.delete("/api/records/{record_id}", dependencies=[Depends(require_session)])
def delete_record(record_id: int):

    if record_id <= 0:
        raise HTTPException(
            status_code=400,
            detail="记录编号无效"
        )

    deleted_at = datetime.now().astimezone().isoformat(timespec="seconds")
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE records SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
            (deleted_at, record_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(404, "没有找到这条记录，或它已在回收站。")
    return {"success": True, "deleted_id": record_id}


class TrashPolicy(BaseModel):
    enabled: bool


def delete_expired_records(conn):
    cursor = conn.execute("""
        DELETE FROM records
        WHERE deleted_at IS NOT NULL
          AND julianday(deleted_at) <= julianday('now', '-30 days')
          AND EXISTS (SELECT 1 FROM trash_policy WHERE id = 1 AND enabled = 1)
    """)
    return cursor.rowcount


def purge_expired_trash():
    with get_db() as conn:
        return delete_expired_records(conn)


@app.get("/api/trash/policy", dependencies=[Depends(require_session)])
def get_trash_policy():
    with get_db() as conn:
        row = conn.execute("SELECT enabled FROM trash_policy WHERE id = 1").fetchone()
    return {"enabled": bool(row["enabled"])}


@app.put("/api/trash/policy", dependencies=[Depends(require_session)])
def update_trash_policy(policy: TrashPolicy):
    with get_db() as conn:
        conn.execute("UPDATE trash_policy SET enabled = ? WHERE id = 1", (policy.enabled,))
        if policy.enabled:
            delete_expired_records(conn)
    return {"enabled": policy.enabled}


@app.post("/api/records/{record_id}/restore", dependencies=[Depends(require_session)])
def restore_record(record_id: int):
    purge_expired_trash()
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE records SET deleted_at = NULL WHERE id = ? AND deleted_at IS NOT NULL",
            (record_id,),
        )
        if cursor.rowcount == 0:
            raise HTTPException(404, "这条记录已恢复，或回收站中没有这条记录。")
    return {"success": True, "restored_id": record_id}


@app.delete("/api/records/{record_id}/trash", dependencies=[Depends(require_session)])
def permanently_delete_record(record_id: int):
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM records WHERE id = ? AND deleted_at IS NOT NULL",
            (record_id,),
        )
        if cursor.rowcount == 0:
            raise HTTPException(404, "只能永久删除回收站里的笔记。")
    return {"success": True, "deleted_id": record_id}


def is_web_url(content: str) -> bool:
    value = content.strip()
    if any(char.isspace() or ord(char) < 32 or char == chr(92) for char in value):
        return False
    try:
        url = urlsplit(value)
        return url.scheme in {"http", "https"} and bool(url.hostname)
    except ValueError:
        return False


RECORD_DATE_SQL = "COALESCE(note_date, substr(created_at, 1, 10))"


def validate_date_range(date_from, date_to):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(400, "开始日期不能晚于结束日期。")


def query_records(q, category, view, tag, order, *, date_from=None, date_to=None, page=1, page_size=None):
    validate_date_range(date_from, date_to)
    keyword = q.strip()
    category_filter = category.strip()
    conditions = ["deleted_at IS NOT NULL" if view == "trash" else "deleted_at IS NULL"]
    params = []

    if keyword:
        conditions.append("""
            (
                instr(lower(content), lower(?)) > 0
                OR instr(lower(title), lower(?)) > 0
                OR instr(lower(summary), lower(?)) > 0
                OR instr(lower(category), lower(?)) > 0
                OR EXISTS (
                    SELECT 1
                    FROM json_each(CASE WHEN json_valid(records.tags) THEN records.tags ELSE '[]' END) AS tag
                    WHERE tag.type = 'text' AND instr(lower(tag.value), lower(?)) > 0
                )
            )
        """)
        params.extend([keyword] * 5)

    if category_filter and category_filter != "全部":
        conditions.append("category = ?")
        params.append(category_filter)

    if tag.strip():
        conditions.append("""EXISTS (
            SELECT 1 FROM json_each(CASE WHEN json_valid(records.tags) THEN records.tags ELSE '[]' END) AS item
            WHERE item.type = 'text' AND item.value = ?
        )""")
        params.append(tag.strip())

    if view == "web":
        conditions.append("(category = '网站收藏' OR is_web_url(content))")
    elif view == "pinned":
        conditions.append("pinned = 1")
    elif view == "recent":
        conditions.append(f"{RECORD_DATE_SQL} BETWEEN date('now', 'localtime', '-6 days') AND date('now', 'localtime')")

    if date_from:
        conditions.append(f"{RECORD_DATE_SQL} >= ?")
        params.append(date_from.isoformat())
    if date_to:
        conditions.append(f"{RECORD_DATE_SQL} <= ?")
        params.append(date_to.isoformat())

    where_sql = "WHERE " + " AND ".join(conditions)
    direction = "ASC" if order == "oldest" else "DESC"
    ordering = f"deleted_at {direction}, id {direction}" if view == "trash" else f"pinned DESC, id {direction}"
    query = f"SELECT * FROM records {where_sql} ORDER BY {ordering}"
    with get_db() as conn:
        conn.create_function("is_web_url", 1, is_web_url, deterministic=True)
        if page_size is None:
            rows = conn.execute(query, params).fetchall()
            return rows, len(rows), 1

        conn.execute("BEGIN")
        total = conn.execute(f"SELECT COUNT(*) FROM records {where_sql}", params).fetchone()[0]
        page = min(page, max(1, (total + page_size - 1) // page_size))
        rows = conn.execute(query + " LIMIT ? OFFSET ?", [*params, page_size, (page - 1) * page_size]).fetchall()
        return rows, total, page


@app.get("/api/records/calendar", dependencies=[Depends(require_session)])
def calendar_counts(month: Annotated[str, Query(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")]):
    try:
        start = date.fromisoformat(month + "-01")
        end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    except ValueError:
        raise HTTPException(400, "无效的月份。") from None
    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT {RECORD_DATE_SQL} AS day, COUNT(*) AS total
            FROM records
            WHERE deleted_at IS NULL AND {RECORD_DATE_SQL} >= ? AND {RECORD_DATE_SQL} < ?
            GROUP BY day
            ORDER BY day
        """, (start.isoformat(), end.isoformat())).fetchall()
    return {"month": month, "days": {row["day"]: row["total"] for row in rows}}


@app.get("/api/records/search", dependencies=[Depends(require_session)])
def search_records(q: str = "", category: str = "", view: Literal["web", "recent", "pinned", "trash", ""] = "",
                   tag: str = "", order: Literal["newest", "oldest"] = "newest",
                   date_from: date | None = None, date_to: date | None = None,
                   page: Annotated[int, Query(ge=1)] = 1,
                   page_size: Annotated[int, Query(ge=1, le=100)] = 100):
    if view == "trash":
        purge_expired_trash()
    rows, total, page = query_records(q, category, view, tag, order, date_from=date_from,
                                      date_to=date_to, page=page, page_size=page_size)
    return {
        "success": True,
        "keyword": q.strip(),
        "category": category.strip() or "全部",
        "total": total,
        "page": page,
        "page_size": page_size,
        "records": [dict(row) for row in rows]
    }


class SavedSearch(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    view: Literal["inbox", "library", "web", "recent", "pinned"]
    category: str = Field(default="", max_length=50)
    tag: str = Field(default="", max_length=10000)
    keyword: str = Field(default="", max_length=10000)
    date_from: date | None = None
    date_to: date | None = None


@app.get("/api/saved-searches", dependencies=[Depends(require_session)])
def list_saved_searches():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, name, view, category, keyword, tag, date_from, date_to FROM saved_searches ORDER BY id
        """).fetchall()
    return {"searches": [dict(row) for row in rows]}


@app.post("/api/saved-searches", status_code=201, dependencies=[Depends(require_session)])
def create_saved_search(search: SavedSearch):
    name = search.name.strip()
    if not name:
        raise HTTPException(400, "请输入搜索名称。")
    category = "" if search.view == "inbox" else search.category.strip()
    keyword = search.keyword.strip()
    tag = search.tag.strip()
    validate_date_range(search.date_from, search.date_to)
    start = search.date_from.isoformat() if search.date_from else None
    end = search.date_to.isoformat() if search.date_to else None
    if search.view == "library" and not (category or keyword or tag or start or end):
        raise HTTPException(400, "请先设置筛选条件。")

    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO saved_searches (name, view, category, keyword, tag, date_from, date_to) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO NOTHING
        """, (name, search.view, category, keyword, tag, start, end))
        if cursor.rowcount == 0:
            raise HTTPException(409, "已有同名的常用搜索。")
        search_id = cursor.lastrowid
    return {"id": search_id, "name": name, "view": search.view, "category": category, "keyword": keyword, "tag": tag,
            "date_from": start, "date_to": end}


@app.delete("/api/saved-searches/{search_id}", dependencies=[Depends(require_session)])
def delete_saved_search(search_id: int):
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM saved_searches WHERE id = ?", (search_id,))
        if cursor.rowcount == 0:
            raise HTTPException(404, "这条常用搜索已不存在。")
    return {"id": search_id}


class InboxClassification(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=50)


@app.get("/api/categories", dependencies=[Depends(require_session)])
def list_categories():
    with get_db() as conn:
        rows = conn.execute("SELECT name AS category FROM categories ORDER BY name").fetchall()
    return {"categories": [row["category"] for row in rows]}


SYSTEM_CATEGORIES = frozenset({
    "待整理", "工作经验", "学习笔记", "AI工具", "网站收藏", "个人灵感", "生活记录", "商业想法"
})


class CategoryName(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class CategoryRename(CategoryName):
    previous: str = Field(min_length=1, max_length=50)


@app.post("/api/categories", status_code=201, dependencies=[Depends(require_session)])
def create_category(category: CategoryName):
    name = category.name.strip()
    if not name:
        raise HTTPException(400, "请输入分类名称。")
    with get_db() as conn:
        cursor = conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
        if name in SYSTEM_CATEGORIES or not cursor.rowcount:
            raise HTTPException(409, "该分类已经存在。")
    return {"name": name}


@app.put("/api/categories/rename", dependencies=[Depends(require_session)])
def rename_category(category: CategoryRename):
    previous = category.previous.strip()
    name = category.name.strip()
    if not name or name == previous:
        raise HTTPException(400, "请输入新的分类名称。")
    if previous in SYSTEM_CATEGORIES:
        raise HTTPException(400, "基础分类名称固定。")
    with get_db() as conn:
        cursor = conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
        if name in SYSTEM_CATEGORIES or not cursor.rowcount:
            raise HTTPException(409, "该分类已经存在。")
        cursor = conn.execute("DELETE FROM categories WHERE name = ?", (previous,))
        if not cursor.rowcount:
            raise HTTPException(404, "没有找到原分类。")
        conn.execute("UPDATE records SET category = ? WHERE category = ?", (name, previous))
        conn.execute("UPDATE saved_searches SET category = ? WHERE category = ?", (name, previous))
    return {"name": name}


@app.get("/api/settings/overview", dependencies=[Depends(require_session)])
def settings_overview():
    with get_db() as conn:
        row = conn.execute("""
            SELECT
                COUNT(CASE WHEN deleted_at IS NULL THEN 1 END) AS active,
                COUNT(CASE WHEN deleted_at IS NULL AND category = '待整理' THEN 1 END) AS inbox,
                COUNT(CASE WHEN deleted_at IS NULL AND pinned = 1 THEN 1 END) AS pinned,
                COUNT(CASE WHEN deleted_at IS NOT NULL THEN 1 END) AS trash
            FROM records
        """).fetchone()
    return dict(row)


class NoteDateMove(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=100)
    note_date: date


@app.post("/api/records/move-date", dependencies=[Depends(require_session)])
def move_notes_to_date(batch: NoteDateMove):
    target = batch.note_date.isoformat()
    ids = list(dict.fromkeys(batch.ids))
    placeholders = ",".join("?" for _ in ids)
    updated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        records = conn.execute(f"""
            SELECT *, {RECORD_DATE_SQL} AS effective_date
            FROM records WHERE deleted_at IS NULL AND id IN ({placeholders})
        """, ids).fetchall()
        if len(records) != len(ids):
            raise HTTPException(409, "部分记录已改变，请刷新后重新选择。")
        changed = [record for record in records if record["effective_date"] != target]
        for record in changed:
            save_record_version(conn, record, updated_at)
        conn.executemany("UPDATE records SET note_date = ?, updated_at = ? WHERE id = ?",
                         [(target, updated_at, record["id"]) for record in changed])
    return {"updated": len(changed), "unchanged": len(ids) - len(changed)}


class DailyReview(BaseModel):
    content: str = Field(max_length=10000)


@app.get("/api/daily-reviews/{day}", dependencies=[Depends(require_session)])
def get_daily_review(day: date):
    key = day.isoformat()
    with get_db() as conn:
        row = conn.execute("SELECT content, updated_at FROM daily_reviews WHERE day = ?", (key,)).fetchone()
    return {"day": key, "content": row["content"] if row else "", "updated_at": row["updated_at"] if row else None}


@app.put("/api/daily-reviews/{day}", dependencies=[Depends(require_session)])
def save_daily_review(day: date, review: DailyReview):
    key = day.isoformat()
    content = review.content.strip()
    updated_at = datetime.now().astimezone().isoformat(timespec="seconds") if content else None
    with get_db() as conn:
        if content:
            conn.execute("""
                INSERT INTO daily_reviews (day, content, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(day) DO UPDATE SET content = excluded.content, updated_at = excluded.updated_at
            """, (key, content, updated_at))
        else:
            conn.execute("DELETE FROM daily_reviews WHERE day = ?", (key,))
    return {"day": key, "content": content, "updated_at": updated_at}


@app.post("/api/records/classify", dependencies=[Depends(require_session)])
def classify_inbox(batch: InboxClassification):
    category = batch.category.strip()
    if not category or category == "待整理":
        raise HTTPException(400, "请输入目标分类。")
    ids = list(dict.fromkeys(batch.ids))
    placeholders = ",".join("?" for _ in ids)
    updated = datetime.now().astimezone().isoformat(timespec="seconds")
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        records = conn.execute(
            f"SELECT * FROM records WHERE category = ? AND deleted_at IS NULL AND id IN ({placeholders})",
            ["待整理", *ids],
        ).fetchall()
        for record in records:
            save_record_version(conn, record, updated)
        cursor = conn.execute(
            f"UPDATE records SET category = ?, updated_at = ? WHERE category = ? AND deleted_at IS NULL AND id IN ({placeholders})",
            [category, updated, "待整理", *ids],
        )
        if cursor.rowcount != len(ids):
            raise HTTPException(409, "部分记录已改变，请刷新收集箱后重试。")
        conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (category,))
    return {"updated": len(ids)}


class BatchOrganization(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=100)
    category: str = Field(default='', max_length=50)
    tag: str = Field(default='', max_length=50)


@app.post('/api/records/organize', dependencies=[Depends(require_session)])
def organize_records(batch: BatchOrganization):
    category, tag = batch.category.strip(), batch.tag.strip()
    if not category and not tag:
        raise HTTPException(400, '请选择目标分类或填写标签。')
    ids = list(dict.fromkeys(batch.ids))
    placeholders = ','.join('?' for _ in ids)
    now = datetime.now().astimezone().isoformat(timespec='seconds')
    changed = 0
    with get_db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        rows = conn.execute(f'SELECT * FROM records WHERE deleted_at IS NULL AND id IN ({placeholders})', ids).fetchall()
        if len(rows) != len(ids):
            raise HTTPException(409, '部分笔记已不存在或进入回收站，本次没有修改，请刷新后再试。')
        for row in rows:
            target = category or row['category']
            tags_json = row['tags']
            if tag:
                try:
                    tags = json.loads(tags_json or '[]')
                except (TypeError, ValueError):
                    raise HTTPException(409, '有笔记的标签无法读取，本次没有修改。') from None
                if not isinstance(tags, list):
                    raise HTTPException(409, '有笔记的标签无法读取，本次没有修改。')
                if tag not in tags:
                    tags_json = json.dumps([*tags, tag], ensure_ascii=False)
            if target == row['category'] and tags_json == row['tags']:
                continue
            save_record_version(conn, row, now)
            conn.execute('UPDATE records SET category=?, tags=?, updated_at=? WHERE id=?', (target, tags_json, now, row['id']))
            changed += 1
        if category:
            conn.execute('INSERT OR IGNORE INTO categories(name) VALUES (?)', (category,))
    return {'updated': changed}


@app.get("/api/records/export", dependencies=[Depends(require_session)])
def export_records(format: Literal["md", "docx", "json", "xlsx"] = "md", q: str = "", category: str = "",
                   view: Literal["web", "recent", "pinned", ""] = "", tag: str = "",
                   order: Literal["newest", "oldest"] = "newest",
                   date_from: date | None = None, date_to: date | None = None):
    rows, _, _ = query_records(q, category, view, tag, order, date_from=date_from, date_to=date_to)
    content, media_type = render_export([dict(row) for row in rows], format)
    title = "知己筛选结果" if q or category or view or tag or date_from or date_to else "知己知识库"
    filename = quote(f"{title}-{datetime.now().date().isoformat()}.{format}")
    return Response(content, media_type=media_type,
                    headers={"Content-Disposition": "attachment; filename*=UTF-8''" + filename})


def active_record(conn, record_id):
    record = conn.execute("SELECT * FROM records WHERE id = ? AND deleted_at IS NULL", (record_id,)).fetchone()
    if record is None:
        raise HTTPException(404, "记录不存在，或已移入回收站。")
    return record


def query_tasks(conn, record_id=None):
    conditions = "r.deleted_at IS NULL"
    params = []
    if record_id is not None:
        conditions += " AND t.record_id = ?"
        params.append(record_id)
    rows = conn.execute(f"""
        SELECT t.id, t.record_id, t.title, t.due_date, t.due_time, t.priority, t.completed_at,
               COALESCE(NULLIF(trim(r.title), ''), substr(r.content, 1, 45)) AS record_title
        FROM note_tasks t JOIN records r ON t.record_id = r.id
        WHERE {conditions}
        ORDER BY t.completed_at IS NOT NULL, t.due_date IS NULL, t.due_date,
                 COALESCE(t.due_time, '23:59'), t.priority DESC, t.id DESC
    """, params).fetchall()
    return [dict(row) for row in rows]


class NoteTaskDetails(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    due_date: date | None = None
    due_time: str | None = Field(default=None, pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    priority: int = Field(default=0, ge=0, le=2)


class NoteTaskCreate(NoteTaskDetails):
    record_id: int


def task_details(task: NoteTaskDetails):
    title = task.title.strip()
    if not title:
        raise HTTPException(400, "请输入待办内容。")
    if task.due_time and not task.due_date:
        raise HTTPException(400, "设置具体时间前，请先选择日期。")
    return (title, task.due_date.isoformat() if task.due_date else None, task.due_time, task.priority)


class NoteTaskState(BaseModel):
    completed: bool


class NoteTaskBatch(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)
    action: Literal['complete', 'reopen', 'reschedule']
    due_date: date | None = None
    due_time: str | None = Field(default=None, pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


@app.post("/api/tasks/batch", dependencies=[Depends(require_session)])
def batch_tasks(batch: NoteTaskBatch):
    ids = list(dict.fromkeys(batch.ids))
    if batch.due_time and not batch.due_date:
        raise HTTPException(400, "设置具体时间前，请先选择日期。")
    placeholders = ','.join('?' for _ in ids)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        count = conn.execute(f"""
            SELECT count(*) FROM note_tasks t JOIN records r ON r.id = t.record_id
            WHERE t.id IN ({placeholders}) AND r.deleted_at IS NULL
        """, ids).fetchone()[0]
        if count != len(ids):
            raise HTTPException(409, "部分待办已被移除，请刷新后重新选择。本次没有修改任何待办。")
        if batch.action == 'reschedule':
            conn.execute(f"UPDATE note_tasks SET due_date = ?, due_time = ? WHERE id IN ({placeholders})",
                         [batch.due_date.isoformat() if batch.due_date else None, batch.due_time, *ids])
        elif batch.action == 'complete':
            conn.execute(f"UPDATE note_tasks SET completed_at = COALESCE(completed_at, ?) WHERE id IN ({placeholders})",
                         [datetime.now().astimezone().isoformat(timespec='seconds'), *ids])
        else:
            conn.execute(f"UPDATE note_tasks SET completed_at = NULL WHERE id IN ({placeholders})", ids)
    return {"success": True, "updated": len(ids)}


@app.get("/api/tasks", dependencies=[Depends(require_session)])
def list_tasks():
    with get_db() as conn:
        tasks = query_tasks(conn)
    return {"tasks": tasks}


@app.post("/api/tasks", status_code=201, dependencies=[Depends(require_session)])
def create_task(task: NoteTaskCreate):
    details = task_details(task)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        active_record(conn, task.record_id)
        cursor = conn.execute("INSERT INTO note_tasks(record_id,title,due_date,due_time,priority) VALUES(?, ?, ?, ?, ?)",
                              (task.record_id, *details))
    return {"id": cursor.lastrowid}


@app.patch("/api/tasks/{task_id}", dependencies=[Depends(require_session)])
def edit_task(task_id: int, task: NoteTaskDetails):
    details = task_details(task)
    with get_db() as conn:
        cursor = conn.execute("""
            UPDATE note_tasks SET title = ?, due_date = ?, due_time = ?, priority = ?
            WHERE id = ? AND EXISTS (
                SELECT 1 FROM records r WHERE r.id = note_tasks.record_id AND r.deleted_at IS NULL
            )
        """, (*details, task_id))
        if not cursor.rowcount:
            raise HTTPException(404, "待办不存在，或原笔记已移入回收站。")
    return {"success": True}


@app.put("/api/tasks/{task_id}", dependencies=[Depends(require_session)])
def set_task_state(task_id: int, task: NoteTaskState):
    completed_at = datetime.now().astimezone().isoformat(timespec="seconds") if task.completed else None
    with get_db() as conn:
        cursor = conn.execute("""
            UPDATE note_tasks
            SET completed_at = CASE WHEN ? IS NULL THEN NULL ELSE COALESCE(completed_at, ?) END
            WHERE id = ? AND EXISTS (
                SELECT 1 FROM records r WHERE r.id = note_tasks.record_id AND r.deleted_at IS NULL
            )
        """, (completed_at, completed_at, task_id))
        if not cursor.rowcount:
            raise HTTPException(404, "待办不存在，或原笔记已移入回收站。")
    return {"success": True}


@app.delete("/api/tasks/{task_id}", dependencies=[Depends(require_session)])
def delete_task(task_id: int):
    with get_db() as conn:
        cursor = conn.execute("""
            DELETE FROM note_tasks WHERE id = ? AND EXISTS (
                SELECT 1 FROM records r WHERE r.id = note_tasks.record_id AND r.deleted_at IS NULL
            )
        """, (task_id,))
        if not cursor.rowcount:
            raise HTTPException(404, "待办不存在，或原笔记已移入回收站。")
    return {"success": True}


@app.get("/api/records/{record_id}/links", dependencies=[Depends(require_session)])
def get_record_links(record_id: int):
    with get_db() as conn:
        record = conn.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
        if record is None:
            raise HTTPException(404, "记录不存在。")
        if record["deleted_at"] is not None:
            return {"record": dict(record), "links": [], "tasks": []}
        links = conn.execute("""
            SELECT r.id, r.title, r.content, r.category,
                   CASE WHEN l.source_id = ? THEN 'outgoing' ELSE 'incoming' END AS direction
            FROM record_links l
            JOIN records r ON r.id = CASE WHEN l.source_id = ? THEN l.target_id ELSE l.source_id END
            WHERE (l.source_id = ? OR l.target_id = ?) AND r.deleted_at IS NULL
            ORDER BY r.id DESC
        """, (record_id,)*4).fetchall()
        tasks = query_tasks(conn, record_id)
    return {"record": dict(record), "links": [dict(row) for row in links], "tasks": tasks}


@app.put("/api/records/{record_id}/links/{target_id}", dependencies=[Depends(require_session)])
def add_record_link(record_id: int, target_id: int):
    if record_id == target_id:
        raise HTTPException(400, "记录不能关联自己。")
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        active_record(conn, record_id)
        active_record(conn, target_id)
        conn.execute("INSERT OR IGNORE INTO record_links(source_id, target_id) VALUES (?, ?)", (record_id, target_id))
    return {"success": True}


@app.delete("/api/records/{record_id}/links/{target_id}", dependencies=[Depends(require_session)])
def remove_record_link(record_id: int, target_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM record_links WHERE source_id = ? AND target_id = ?", (record_id, target_id))
    return {"success": True}


@app.get("/api/records/{record_id}/versions", dependencies=[Depends(require_session)])
def list_record_versions(record_id: int):
    with get_db() as conn:
        current = active_record(conn, record_id)
        versions = conn.execute("""
            SELECT id, captured_at, title, content, summary, category, tags, note_date
            FROM record_versions WHERE record_id = ? ORDER BY id DESC
        """, (record_id,)).fetchall()
    return {"record": dict(current), "versions": [dict(row) for row in versions]}


@app.post("/api/records/{record_id}/versions/{version_id}/restore", dependencies=[Depends(require_session)])
def restore_record_version(record_id: int, version_id: int):
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = active_record(conn, record_id)
        version = conn.execute(
            "SELECT * FROM record_versions WHERE id = ? AND record_id = ?", (version_id, record_id)
        ).fetchone()
        if version is None:
            raise HTTPException(404, "没有找到该版本。")
        if any(version[field] != current[field] for field in VERSION_FIELDS):
            save_record_version(conn, current, now)
            conn.execute("""
                UPDATE records SET title = ?, content = ?, summary = ?, category = ?, tags = ?, note_date = ?, updated_at = ?
                WHERE id = ?
            """, (*(version[field] for field in VERSION_FIELDS), now, record_id))
            conn.execute("INSERT OR IGNORE INTO categories(name) VALUES (?)", (version["category"],))
    return {"success": True}


@app.post("/api/records/{record_id}/duplicate", status_code=201, dependencies=[Depends(require_session)])
def duplicate_record(record_id: int):
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        source = active_record(conn, record_id)
        suffix = "（副本）"
        fallback = (source["content"].strip().splitlines() or ["未命名记录"])[0][:28]
        title = (source["title"].strip() or fallback)[:200-len(suffix)] + suffix
        cursor = conn.execute("""
            INSERT INTO records (title, content, summary, category, tags, created_at, updated_at, source_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, source["content"], source["summary"], source["category"], source["tags"], now, now, source["source_type"]))
        new_id = cursor.lastrowid
    return {"id": new_id, "title": title}


@app.get("/api/settings/backup", dependencies=[Depends(require_session)])
def download_backup():
    with closing(sqlite3.connect(DB_PATH.resolve().as_uri() + "?mode=ro", uri=True)) as source:
        with closing(sqlite3.connect(":memory:")) as snapshot:
            source.backup(snapshot)
            if snapshot.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise HTTPException(500, "备份完整性校验失败。")
            data = snapshot.serialize()
    filename = quote(f"知己数据备份-{datetime.now().date().isoformat()}.sqlite3")
    return Response(data, media_type="application/vnd.sqlite3",
                    headers={"Content-Disposition": "attachment; filename*=UTF-8''" + filename})


if (frontend_dist / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")


@app.get("/favicon.svg", include_in_schema=False)
def favicon():
    icon = frontend_dist / "favicon.svg"
    if not icon.is_file():
        raise HTTPException(404)
    return FileResponse(icon)


class TemplateInput(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    title: str = Field(default='', max_length=200)
    category: str = Field(default='待整理', max_length=50)
    content: str = Field(min_length=1, max_length=10000)


@app.get('/api/templates', dependencies=[Depends(require_session)])
def list_templates():
    with get_db() as conn:
        return {'templates': [dict(row) for row in conn.execute('SELECT * FROM note_templates ORDER BY id')]}


def template_values(body):
    if not body.name.strip() or not body.content.strip():
        raise HTTPException(400, '请填写模板名称和正文。')
    return (body.name.strip(), body.title.strip(), body.category.strip() or '待整理', body.content)


@app.post('/api/templates', status_code=201, dependencies=[Depends(require_session)])
def create_template(body: TemplateInput):
    values = template_values(body)
    try:
        with get_db() as conn:
            cursor = conn.execute('INSERT INTO note_templates(name,title,category,content) VALUES(?,?,?,?)', values)
            return {'id': cursor.lastrowid}
    except sqlite3.IntegrityError:
        raise HTTPException(409, '已有同名模板，请换个名称或更新原模板。')


@app.put('/api/templates/{template_id}', dependencies=[Depends(require_session)])
def update_template(template_id: int, body: TemplateInput):
    values = template_values(body)
    try:
        with get_db() as conn:
            cursor = conn.execute('UPDATE note_templates SET name=?,title=?,category=?,content=? WHERE id=?', (*values, template_id))
            if not cursor.rowcount:
                raise HTTPException(404, '模板不存在。')
        return {'success': True}
    except sqlite3.IntegrityError:
        raise HTTPException(409, '已有同名模板。')


@app.delete('/api/templates/{template_id}', dependencies=[Depends(require_session)])
def delete_template(template_id: int):
    with get_db() as conn:
        if not conn.execute('DELETE FROM note_templates WHERE id=?', (template_id,)).rowcount:
            raise HTTPException(404, '模板不存在。')
    return {'success': True}


class TemplateImport(BaseModel):
    templates: list[TemplateInput] = Field(min_length=1, max_length=100)


@app.post('/api/templates/import', dependencies=[Depends(require_session)])
def import_templates(body: TemplateImport):
    values = [template_values(item) for item in body.templates]
    imported = 0
    skipped = 0
    with get_db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        for value in values:
            cursor = conn.execute('INSERT OR IGNORE INTO note_templates(name,title,category,content) VALUES(?,?,?,?)', value)
            if cursor.rowcount:
                imported += 1
            else:
                skipped += 1
    return {'imported': imported, 'skipped': skipped}
