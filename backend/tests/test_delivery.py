from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select

from app.db import SessionLocal
from app.delivery import RateLimiter, enqueue_due, is_due, jitter_minutes, process_pending
from app.models import Delivery, User


def make_user(**kw):
    defaults = dict(id=1, tz="Europe/Minsk", send_time="09:00", is_active=True)
    defaults.update(kw)
    return User(**defaults)


def utc_at_minsk(minutes_from_midnight: int) -> datetime:
    """Минск = UTC+3 без перехода на летнее время, поэтому UTC выводится простым сдвигом."""
    return datetime(2026, 3, 10) + timedelta(minutes=minutes_from_midnight) - timedelta(hours=3)


def test_jitter_is_stable_and_bounded():
    for uid in range(1, 500):
        j = jitter_minutes(uid)
        assert -10 <= j <= 10
        assert j == jitter_minutes(uid)
    assert len({jitter_minutes(uid) for uid in range(1, 500)}) > 5  # не все сдвинуты одинаково


def test_is_due_respects_timezone_jitter_and_window():
    u = make_user()  # id=1, Минск
    target = 9 * 60 + jitter_minutes(u.id)  # 09:00 плюс личный сдвиг
    assert is_due(u, utc_at_minsk(target)) is not None
    assert is_due(u, utc_at_minsk(target - 1)) is None  # ещё рано
    assert is_due(u, utc_at_minsk(target + 6 * 60)) is None  # окно догонки (6 ч) закрыто


async def test_enqueue_is_idempotent():
    async with SessionLocal() as s:
        s.add(make_user())
        await s.commit()
    now = utc_at_minsk(9 * 60 + jitter_minutes(1))
    assert await enqueue_due(now) == 1
    assert await enqueue_due(now) == 0


async def test_inactive_users_skipped():
    async with SessionLocal() as s:
        s.add(make_user(is_active=False))
        await s.commit()
    assert await enqueue_due(utc_at_minsk(9 * 60 + jitter_minutes(1))) == 0


def fake_bot(exc=None):
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=exc)
    return bot


async def run_once(bot):
    async with SessionLocal() as s:
        s.add(make_user())
        await s.commit()
    await enqueue_due(utc_at_minsk(9 * 60 + jitter_minutes(1)))
    await process_pending(bot, RateLimiter(1000))
    async with SessionLocal() as s:
        d = (await s.execute(select(Delivery))).scalar_one()
        u = await s.get(User, 1)
        return d, u


async def test_success_marks_sent():
    d, u = await run_once(fake_bot())
    assert d.status == "sent" and u.is_active


async def test_blocked_user_is_deactivated():
    exc = TelegramForbiddenError(method=MagicMock(), message="Forbidden: bot was blocked by the user")
    d, u = await run_once(fake_bot(exc))
    assert d.status == "blocked" and not u.is_active


async def test_retry_after_keeps_pending_and_delays():
    exc = TelegramRetryAfter(method=MagicMock(), message="Too Many Requests", retry_after=30)
    d, u = await run_once(fake_bot(exc))
    assert d.status == "pending" and d.attempts == 0
    assert d.next_attempt_at > datetime.utcnow() and u.is_active
