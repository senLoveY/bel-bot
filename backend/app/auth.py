from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Optional
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException
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


async def current_user(
    x_telegram_init_data: str = Header(default=""),
    x_dev_user: str = Header(default=""),
    session: AsyncSession = Depends(get_session),
) -> User:
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
