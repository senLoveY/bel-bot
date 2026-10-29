from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from typing import Optional, Tuple
from urllib.parse import parse_qsl

from fastapi import Cookie, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import get_session
from .models import User

MAX_AUTH_AGE_SEC = 24 * 3600


def validate_init_data(init_data: str, bot_token: str, max_age: int = MAX_AUTH_AGE_SEC) -> Optional[dict]:
    """Проверяет подпись Telegram WebApp initData. Возвращает данные пользователя или None."""
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        return None
    received_hash = pairs.pop("hash", None)
    if not received_hash or not bot_token:
        return None

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        return None

    try:
        if time.time() - int(pairs.get("auth_date", "0")) > max_age:
            return None
        return json.loads(pairs["user"])
    except (ValueError, KeyError):
        return None


SESSION_TTL = 12 * 3600
SESSION_COOKIE = "admin_session"


def _session_key() -> bytes:
    return hashlib.sha256(("web-session|" + settings.bot_token).encode()).digest()


def make_session_token(user_id: int) -> str:
    body = f"{user_id}.{int(time.time()) + SESSION_TTL}"
    sig = hmac.new(_session_key(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def read_session_token(token: str) -> Optional[int]:
    try:
        user_id, exp, sig = token.split(".")
        body = f"{user_id}.{exp}"
        expected = hmac.new(_session_key(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig) or int(exp) < time.time():
            return None
        return int(user_id)
    except ValueError:
        return None


LOGIN_TTL = 120  # ссылка из бота живёт 2 минуты и работает один раз (использованные nonce хранятся в базе)


def _login_key() -> bytes:
    return hashlib.sha256(("tg-login|" + settings.bot_token).encode()).digest()


def make_login_token(user_id: int) -> str:
    body = f"{user_id}.{int(time.time()) + LOGIN_TTL}.{secrets.token_urlsafe(16)}"
    sig = hmac.new(_login_key(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_login_token(token: str) -> Optional[Tuple[int, str]]:
    """Проверяет подпись и срок ссылки. Возвращает (user_id, nonce); повторное использование ловит база."""
    try:
        user_id, exp, nonce, sig = token.split(".")
        body = f"{user_id}.{exp}.{nonce}"
        expected = hmac.new(_login_key(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig) or int(exp) < time.time():
            return None
        return int(user_id), nonce
    except ValueError:
        return None


def require_role(*roles: str):
    """Зависимость FastAPI: пускает только пользователей с одной из указанных ролей."""

    async def checker(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="forbidden")
        return user

    return checker


async def sync_admin_roles(session: AsyncSession) -> None:
    """Выдаёт роль admin ID из ADMIN_IDS. Эти админы не могут быть понижены через приложение."""
    for uid in settings.admin_id_set:
        user = await session.get(User, uid)
        if user is None:
            session.add(User(id=uid, first_name="", role="admin"))
        else:
            user.role = "admin"
    await session.commit()


async def current_user(
    x_telegram_init_data: str = Header(default=""),
    x_dev_user: str = Header(default=""),
    admin_session: Optional[str] = Cookie(default=None),
    session: AsyncSession = Depends(get_session),
) -> User:
    # вход через сайт (cookie) — проверяем первым
    user_id = read_session_token(admin_session) if admin_session else None
    if user_id is not None:
        user = await session.get(User, user_id)
        if user is not None:
            return user
    if settings.dev_auth and x_dev_user:
        tg = {"id": int(x_dev_user), "first_name": "Dev"}
    else:
        tg = validate_init_data(x_telegram_init_data, settings.bot_token)
        if not tg:
            raise HTTPException(status_code=401, detail="invalid init data")

    user = await session.get(User, tg["id"])
    if user is None:
        user = User(id=tg["id"], first_name=tg.get("first_name", ""), username=tg.get("username"))
        session.add(user)
        await session.commit()
    return user
