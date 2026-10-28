import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app import auth
from app.auth import (
    make_session_token,
    read_session_token,
    validate_init_data,
    validate_login_widget,
)
from app.db import add_missing_columns, init_db

TOKEN = "123456:TEST"


def sign_init(fields: dict, token: str = TOKEN) -> str:
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields = dict(fields, hash=hmac.new(secret, check.encode(), hashlib.sha256).hexdigest())
    return urlencode(fields)


def sign_widget(fields: dict, token: str = TOKEN) -> dict:
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hashlib.sha256(token.encode()).digest()
    return dict(fields, hash=hmac.new(secret, check.encode(), hashlib.sha256).hexdigest())


def test_init_data_without_user_is_rejected():
    raw = sign_init({"auth_date": str(int(time.time()))})
    assert validate_init_data(raw, TOKEN) is None


def test_init_data_with_malformed_query_is_rejected():
    assert validate_init_data("novalue", TOKEN) is None


def test_init_data_needs_bot_token():
    raw = sign_init({"auth_date": str(int(time.time())), "user": json.dumps({"id": 1})})
    assert validate_init_data(raw, "") is None


def test_widget_missing_hash_or_token_rejected():
    assert validate_login_widget({"id": 1, "auth_date": int(time.time())}, TOKEN) is False
    assert validate_login_widget(sign_widget({"id": 1, "auth_date": int(time.time())}), "") is False


def test_widget_non_numeric_auth_date_rejected():
    data = sign_widget({"id": 1, "auth_date": "abc"})
    assert validate_login_widget(data, TOKEN) is False


def test_session_token_roundtrip():
    assert read_session_token(make_session_token(5)) == 5


def test_session_token_garbage_rejected():
    assert read_session_token("abc") is None
    assert read_session_token("1.2") is None


def test_session_token_with_bad_expiry_rejected():
    body = "1.x"
    sig = hmac.new(auth._session_key(), body.encode(), hashlib.sha256).hexdigest()
    assert read_session_token(f"{body}.{sig}") is None


def test_expired_session_rejected():
    body = f"1.{int(time.time()) - 10}"
    sig = hmac.new(auth._session_key(), body.encode(), hashlib.sha256).hexdigest()
    assert read_session_token(f"{body}.{sig}") is None


async def test_migration_adds_missing_columns_and_is_idempotent(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/old.db")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        await conn.execute(text("CREATE TABLE cards (id INTEGER PRIMARY KEY)"))
    async with engine.begin() as conn:
        await add_missing_columns(conn)
    async with engine.begin() as conn:
        await add_missing_columns(conn)  # повторный запуск ничего не ломает
    async with engine.connect() as conn:
        users = await conn.run_sync(lambda c: {col["name"] for col in inspect(c).get_columns("users")})
        cards = await conn.run_sync(lambda c: {col["name"] for col in inspect(c).get_columns("cards")})
    await engine.dispose()
    assert {"role", "streak", "explain_lang", "last_seen_day"} <= users
    assert {"published", "summary_be", "body_be"} <= cards


async def test_init_db_creates_tables_on_existing_database():
    await init_db()  # таблицы уже есть из фикстуры — функция должна пройти без ошибок
