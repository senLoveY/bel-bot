from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select

from app.db import SessionLocal
from app.delivery import RateLimiter, enqueue_due, is_due, process_pending
from app.models import Delivery, User


def make_user(**kw):
    defaults = dict(id=1, tz="Europe/Minsk", send_time="09:00", is_active=True)
    defaults.update(kw)
    return User(**defaults)


def test_is_due_respects_timezone_and_window():
    u = make_user()  # Минск = UTC+3
    assert is_due(u, datetime(2026, 3, 10, 6, 0)) is not None  # 09:00 локально
    assert is_due(u, datetime(2026, 3, 10, 5, 59)) is None  # ещё рано
    assert is_due(u, datetime(2026, 3, 10, 13, 0)) is None  # окно догонки (6 ч) закрыто


async def test_enqueue_is_idempotent():
    async with SessionLocal() as s:
        s.add(make_user())
        await s.commit()
    now = datetime(2026, 3, 10, 6, 5)
    assert await enqueue_due(now) == 1
    assert await enqueue_due(now) == 0


async def test_inactive_users_skipped():
    async with SessionLocal() as s:
        s.add(make_user(is_active=False))
        await s.commit()
    assert await enqueue_due(datetime(2026, 3, 10, 6, 5)) == 0


def fake_bot(exc=None):
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=exc)
    return bot


async def run_once(bot):
    async with SessionLocal() as s:
        s.add(make_user())
        await s.commit()
    await enqueue_due(datetime(2026, 3, 10, 6, 5))
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
