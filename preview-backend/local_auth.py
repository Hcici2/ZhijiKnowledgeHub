from contextlib import closing
from hashlib import scrypt
from hmac import compare_digest
from pathlib import Path
import secrets
import sqlite3
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field


def build_auth(data_dir: Path):
    router = APIRouter(prefix="/api/auth")
    database = data_dir / "account.sqlite3"
    lock = Lock()
    sessions: dict[str, float] = {}
    failures = 0
    retry_after = 0.0
    lifetime = 12 * 60 * 60
    cookie = "zhiji_session"

    class Password(BaseModel):
        password: str = Field(min_length=1, max_length=128)

    class ChangePassword(Password):
        new_password: str = Field(min_length=8, max_length=128)

    def account(connection):
        connection.execute("""
            CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                salt BLOB NOT NULL,
                digest BLOB NOT NULL
            )
        """)
        return connection.execute("SELECT salt, digest FROM account WHERE id = 1").fetchone()

    def digest(password: str, salt: bytes):
        return scrypt(password.encode("utf-8"), salt=salt, n=32768, r=8, p=1, maxmem=64 * 1024 * 1024)

    def issue(request: Request, response: Response):
        now = monotonic()
        for token, expires in list(sessions.items()):
            if expires <= now:
                sessions.pop(token)
        sessions.pop(request.cookies.get(cookie, ""), None)
        token = secrets.token_urlsafe(32)
        sessions[token] = now + lifetime
        response.set_cookie(cookie, token, httponly=True, samesite="strict", max_age=lifetime)
        return {"authenticated": True, "needs_setup": False}

    def require_session(request: Request):
        with lock:
            if sessions.get(request.cookies.get(cookie, ""), 0) <= monotonic():
                raise HTTPException(401, "请先登录。")

    def verify(password, row):
        nonlocal failures, retry_after
        if monotonic() < retry_after:
            raise HTTPException(429, "尝试次数过多，请 30 秒后重试。")
        if row is None or not compare_digest(digest(password, row[0]), row[1]):
            failures += 1
            if failures >= 5:
                retry_after = monotonic() + 30
                failures = 0
            raise HTTPException(401, "密码不正确。")
        failures = 0

    @router.get("/status")
    def status(request: Request):
        with lock, closing(sqlite3.connect(database)) as connection:
            return {
                "needs_setup": account(connection) is None,
                "authenticated": sessions.get(request.cookies.get(cookie, ""), 0) > monotonic(),
            }

    @router.post("/setup")
    def setup(body: Password, request: Request, response: Response):
        if len(body.password) < 8:
            raise HTTPException(400, "密码至少需要 8 个字符。")
        with lock, closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            if account(connection) is not None:
                raise HTTPException(409, "账户已经设置，请登录。")
            salt = secrets.token_bytes(16)
            connection.execute("INSERT INTO account VALUES (1, ?, ?)", (salt, digest(body.password, salt)))
            connection.commit()
            return issue(request, response)

    @router.post("/login")
    def login(body: Password, request: Request, response: Response):
        with lock, closing(sqlite3.connect(database)) as connection:
            verify(body.password, account(connection))
            return issue(request, response)

    @router.post("/logout")
    def logout(request: Request, response: Response):
        with lock:
            sessions.pop(request.cookies.get(cookie, ""), None)
        response.delete_cookie(cookie)
        return {"authenticated": False, "needs_setup": False}

    @router.post("/password", dependencies=[Depends(require_session)])
    def change_password(body: ChangePassword, request: Request, response: Response):
        with lock, closing(sqlite3.connect(database)) as connection, connection:
            if sessions.get(request.cookies.get(cookie, ""), 0) <= monotonic():
                raise HTTPException(401, "请先登录。")
            verify(body.password, account(connection))
            salt = secrets.token_bytes(16)
            connection.execute("UPDATE account SET salt = ?, digest = ? WHERE id = 1", (salt, digest(body.new_password, salt)))
            connection.commit()
            sessions.clear()
            return issue(request, response)

    return router, require_session
