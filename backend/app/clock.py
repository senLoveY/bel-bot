from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import settings
from .models import User


def user_today(user: User) -> date:
    # у только что созданного пользователя tz ещё None: default применяется при записи в базу
    try:
        tz = ZoneInfo(user.tz or settings.default_tz)
    except ZoneInfoNotFoundError:
        tz = timezone.utc
    return datetime.now(tz).date()
