import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from sqlalchemy import delete, select

from app.config import settings
from app.db import SessionLocal
from app.delivery import (
    RateLimiter,
    backoff,
    enqueue_due,
    jitter_minutes,
    local_now,
    process_pending,
    run_scheduler,
    send_one,
)
from app.models import Card, Delivery, User
from tests.test_delivery import utc_at_minsk


def bot_raising(exc):
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=exc)
    return bot


async def seed_user_and_due_delivery(uid: int = 1) -> int:
    async with SessionLocal() as s:
        s.add(User(id=uid, tz="Europe/Minsk", send_time="09:00", is_active=True))
        await s.commit()
    await enqueue_due(utc_at_minsk(9 * 60 + jitter_minutes(uid)))
    async with SessionLocal() as s:
        return (await s.execute(select(Delivery.id))).scalars().first()


async def test_network_error_schedules_retry_with_backoff():
    did = await seed_user_and_due_delivery()
    await process_pending(bot_raising(TelegramNetworkError(method=MagicMock(), message="timeout")), RateLimiter(1000))
    async with SessionLocal() as s:
        d = await s.get(Delivery, did)
        assert d.status == "pending" and d.attempts == 1
        assert d.next_attempt_at > datetime.utcnow()


async def test_network_error_gives_up_after_max_attempts():
    did = await seed_user_and_due_delivery()
    async with SessionLocal() as s:
        d = await s.get(Delivery, did)
        d.attempts = settings.max_attempts - 1
        await s.commit()
    await send_one(bot_raising(TelegramNetworkError(method=MagicMock(), message="timeout")), did, RateLimiter(1000))
    async with SessionLocal() as s:
        assert (await s.get(Delivery, did)).status == "failed"


async def test_chat_not_found_deactivates_user():
    did = await seed_user_and_due_delivery()
    exc = TelegramBadRequest(method=MagicMock(), message="Bad Request: chat not found")
    await send_one(bot_raising(exc), did, RateLimiter(1000))
    async with SessionLocal() as s:
        d = await s.get(Delivery, did)
        assert d.status == "failed" and (await s.get(User, 1)).is_active is False


async def test_other_bad_request_fails_delivery_only():
    did = await seed_user_and_due_delivery()
    exc = TelegramBadRequest(method=MagicMock(), message="Bad Request: message is too long")
    await send_one(bot_raising(exc), did, RateLimiter(1000))
    async with SessionLocal() as s:
        d = await s.get(Delivery, did)
        assert d.status == "failed" and d.error and (await s.get(User, 1)).is_active is True


async def test_send_one_skips_already_sent_delivery():
    did = await seed_user_and_due_delivery()
    bot = bot_raising(None)
    await send_one(bot, did, RateLimiter(1000))
    await send_one(bot, did, RateLimiter(1000))  # уже sent — второй раз не шлём
    assert bot.send_message.await_count == 1


async def test_send_one_ignores_missing_delivery():
    await send_one(bot_raising(None), 999999, RateLimiter(1000))


async def test_enqueue_skips_when_no_cards():
    async with SessionLocal() as s:
        await s.execute(delete(Card))
        s.add(User(id=2, tz="Europe/Minsk", send_time="09:00", is_active=True))
        await s.commit()
    assert await enqueue_due(utc_at_minsk(9 * 60 + jitter_minutes(2))) == 0


async def test_enqueue_without_due_users_returns_zero():
    assert await enqueue_due(utc_at_minsk(3 * 60)) == 0


async def test_process_pending_with_empty_queue():
    assert await process_pending(bot_raising(None), RateLimiter(1000)) == 0


def test_unknown_timezone_falls_back_to_utc():
    u = User(id=3, tz="Mars/Base", send_time="09:00")
    now = datetime(2026, 3, 10, 12, 0)
    assert local_now(u, now).utcoffset().total_seconds() == 0


def test_backoff_grows_and_is_capped():
    assert backoff(1) < backoff(2) < backoff(3)
    assert backoff(20).total_seconds() == 3600


async def test_rate_limiter_penalty_delays_next_send():
    limiter = RateLimiter(1000)
    limiter.penalize(0.05)
    loop_start = asyncio.get_event_loop().time()
    await limiter.acquire()
    assert asyncio.get_event_loop().time() - loop_start >= 0.04


async def test_scheduler_survives_tick_failure_and_stops_on_cancel():
    bot = bot_raising(None)
    with patch("app.delivery.enqueue_due", AsyncMock(side_effect=RuntimeError("db down"))), patch(
        "app.delivery.asyncio.sleep", AsyncMock(side_effect=asyncio.CancelledError)
    ):
        with pytest.raises(asyncio.CancelledError):
            await run_scheduler(bot)


async def test_jitter_minutes_within_bounds_for_real_ids():
    for uid in (874180496, 1, 42):
        assert -settings.send_jitter_min <= jitter_minutes(uid) <= settings.send_jitter_min
