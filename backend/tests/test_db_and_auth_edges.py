import hashlib
import hmac
import json
import time
from urllib.parse import urlencode


from app import auth
from app.auth import (
    make_session_token,
    read_session_token,
    validate_init_data,
)
from app.db import init_db

TOKEN = "123456:TEST"


def sign_init(fields: dict, token: str = TOKEN) -> str:
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields = dict(fields, hash=hmac.new(secret, check.encode(), hashlib.sha256).hexdigest())
    return urlencode(fields)


def test_init_data_without_user_is_rejected():
    raw = sign_init({"auth_date": str(int(time.time()))})
    assert validate_init_data(raw, TOKEN) is None


def test_init_data_with_malformed_query_is_rejected():
    assert validate_init_data("novalue", TOKEN) is None


def test_init_data_needs_bot_token():
    raw = sign_init({"auth_date": str(int(time.time())), "user": json.dumps({"id": 1})})
    assert validate_init_data(raw, "") is None


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


async def test_init_db_creates_tables_on_existing_database():
    await init_db()  # таблицы уже есть из фикстуры — функция должна пройти без ошибок
