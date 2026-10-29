"""Регрессионные тесты на ошибки рассылки, найденные при ревью кода."""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.delivery import RateLimiter, enqueue_due, is_due, jitter_minutes, process_pending, send_one
from app.models import Card, Delivery, User
from tests.test_delivery import utc_at_minsk


def user_with_jitter(minimum: int) -> int:
    return next(i for i in range(1, 1000) if jitter_minutes(i) >= minimum)


def test_send_time_near_midnight_is_delivered_every_day():
    """Раньше 23:55 + положительный сдвиг давал 0 отправок: момент уходил на следующие сутки."""
    uid = user_with_jitter(6)
    user = User(id=uid, tz="Europe/Minsk", send_time="23:55")
    start = datetime(2026, 3, 10)
    due_days = {is_due(user, start + timedelta(minutes=m)) for m in range(3 * 24 * 60)} - {None}
    assert len(due_days) >= 3

    # первый подходящий момент — ровно 23:55 + сдвиг, карточка — за тот день, когда выбрано 23:55
    target = utc_at_minsk(23 * 60 + 55 + jitter_minutes(uid))
    assert is_due(user, target - timedelta(minutes=1)) is None
    assert is_due(user, target) == datetime(2026, 3, 10).date()


def test_negative_jitter_after_midnight_fires_before_midnight():
    uid = next(i for i in range(1, 1000) if jitter_minutes(i) <= -5)
    user = User(id=uid, tz="Europe/Minsk", send_time="00:02")
    target = utc_at_minsk(2 + jitter_minutes(uid))  # 00:02 минус сдвиг = вечер предыдущих суток
    assert is_due(user, target) == datetime(2026, 3, 10).date()


async def add_user(uid: int, **kw) -> None:
    async with SessionLocal() as s:
        s.add(User(id=uid, tz="Europe/Minsk", send_time="09:00", is_active=True, **kw))
        await s.commit()


async def enqueue_for(uid: int) -> int:
    await enqueue_due(utc_at_minsk(9 * 60 + jitter_minutes(uid)))
    async with SessionLocal() as s:
        return (await s.execute(select(Delivery.id).where(Delivery.user_id == uid))).scalar_one()


async def test_concurrent_sends_deliver_once():
    """Два пересёкшихся вызова крона не должны отправить одну карточку дважды."""
    await add_user(1)
    did = await enqueue_for(1)

    async def slow_send(*_, **__):
        await asyncio.sleep(0.05)

    bot = MagicMock(send_message=AsyncMock(side_effect=slow_send))
    await asyncio.gather(send_one(bot, did, RateLimiter(1000)), send_one(bot, did, RateLimiter(1000)))
    assert bot.send_message.await_count == 1


async def test_stop_after_enqueue_skips_the_card():
    await add_user(1)
    did = await enqueue_for(1)
    async with SessionLocal() as s:
        (await s.get(User, 1)).is_active = False  # /stop после постановки в очередь
        await s.commit()
    bot = MagicMock(send_message=AsyncMock())
    await send_one(bot, did, RateLimiter(1000))
    bot.send_message.assert_not_awaited()
    async with SessionLocal() as s:
        assert (await s.get(Delivery, did)).status == "skipped"


async def test_one_broken_delivery_does_not_stop_the_batch():
    for uid in (1, 2):
        await add_user(uid)
        await enqueue_due(utc_at_minsk(9 * 60 + jitter_minutes(uid)))

    async def send(chat_id, *_, **__):
        if chat_id == 1:
            raise RuntimeError("unexpected")  # не ошибка Telegram

    bot = MagicMock(send_message=AsyncMock(side_effect=send))
    processed = await process_pending(bot, RateLimiter(1000))
    assert processed == 2
    async with SessionLocal() as s:
        sent = (await s.execute(select(Delivery).where(Delivery.user_id == 2))).scalar_one()
    assert sent.status == "sent"


async def test_missing_card_marks_delivery_failed():
    await add_user(1)
    did = await enqueue_for(1)
    async with SessionLocal() as s:
        await s.execute(delete(Card).where(Card.id == (await s.get(Delivery, did)).card_id))
        await s.commit()
    bot = MagicMock(send_message=AsyncMock())
    await send_one(bot, did, RateLimiter(1000))
    async with SessionLocal() as s:
        d = await s.get(Delivery, did)
    assert d.status == "failed" and d.error == "card not found"
    bot.send_message.assert_not_awaited()


async def test_yesterdays_delivery_does_not_block_today():
    await add_user(1)
    async with SessionLocal() as s:
        card_id = (await s.execute(select(Card.id))).scalars().first()
        s.add(Delivery(user_id=1, card_id=card_id, local_date="2026-03-09", status="sent"))
        await s.commit()
    assert await enqueue_due(utc_at_minsk(9 * 60 + jitter_minutes(1))) == 1
