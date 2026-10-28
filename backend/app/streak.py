from __future__ import annotations

from datetime import date, timedelta

from .models import User


def touch_streak(user: User, day: date) -> None:
    """Засчитывает визит в день `day`. Повторный визит в тот же день ничего не меняет."""
    today = day.isoformat()
    if user.last_seen_day == today:
        return
    yesterday = (day - timedelta(days=1)).isoformat()
    user.streak = (user.streak or 0) + 1 if user.last_seen_day == yesterday else 1
    user.longest_streak = max(user.longest_streak or 0, user.streak)
    user.last_seen_day = today


def current_streak(user: User, day: date) -> int:
    """Серия, которая ещё актуальна: если пропущен день, она обнуляется."""
    if user.last_seen_day in (day.isoformat(), (day - timedelta(days=1)).isoformat()):
        return user.streak or 0
    return 0
