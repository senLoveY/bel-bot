"""Ежедневная рассылка: планировщик кладёт задачи в таблицу deliveries, воркер отправляет их
с общим ограничением скорости и разбирает ошибки Telegram (429 / 403 / сетевые)."""
from __future__ import annotations

import asyncio
import logging
import time as monotonic_clock
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .cards import card_for_date, format_card_message
from .config import settings
from .db import SessionLocal, utcnow
from .keyboards import card_keyboard
from .models import Card, Delivery, User

log = logging.getLogger(__name__)
CLAIM_TIMEOUT = timedelta(minutes=5)


class RateLimiter:
    """Равномерно распределяет отправки: не чаще `rate` в секунду на весь процесс."""

    def __init__(self, rate: int):
        self.interval = 1.0 / rate
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = monotonic_clock.monotonic()
            wait = self._next - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._next = max(now, self._next) + self.interval

    def penalize(self, seconds: float) -> None:
        """После 429 притормаживаем все отправки, а не только одну."""
        self._next = max(self._next, monotonic_clock.monotonic() + seconds)


def local_now(user: User, now_utc: datetime) -> datetime:
    try:
        tz = ZoneInfo(user.tz)
    except ZoneInfoNotFoundError:
        tz = timezone.utc
    return now_utc.replace(tzinfo=timezone.utc).astimezone(tz)


def jitter_minutes(user_id: int) -> int:
    """Стабильный сдвиг в пределах ±send_jitter_min минут: у каждого пользователя свой, но неизменный."""
    span = 2 * settings.send_jitter_min + 1
    return (user_id * 2654435761) % span - settings.send_jitter_min


def is_due(user: User, now_utc: datetime) -> Optional[date]:
    """Возвращает дату карточки, если у пользователя сейчас окно отправки, иначе None.

    Момент отправки = выбранное время + личный сдвиг. Около полуночи сдвиг переносит его
    на соседние сутки, поэтому проверяем карточки вчерашнего, сегодняшнего и завтрашнего дня."""
    local = local_now(user, now_utc)
    hh, mm = (int(x) for x in user.send_time.split(":"))
    for day in (local.date() + timedelta(days=1), local.date(), local.date() - timedelta(days=1)):
        target = datetime.combine(day, time(hh, mm), tzinfo=local.tzinfo) + timedelta(minutes=jitter_minutes(user.id))
        if target <= local < target + timedelta(hours=settings.catchup_hours):
            return day
    return None


async def enqueue_due(now_utc: Optional[datetime] = None) -> int:
    """Создаёт pending-доставки тем, у кого наступило время. Повторный вызов безопасен."""
    now_utc = now_utc or utcnow()
    async with SessionLocal() as session:
        users = (await session.execute(select(User).where(User.is_active.is_(True)))).scalars().all()
        due = {}
        for user in users:
            day = is_due(user, now_utc)
            if day:
                due[user.id] = day
        if not due:
            return 0

        already = set()
        ids = list(due)
        days = {d.isoformat() for d in due.values()}
        for i in range(0, len(ids), 500):
            rows = await session.execute(
                select(Delivery.user_id, Delivery.local_date).where(
                    Delivery.user_id.in_(ids[i : i + 500]), Delivery.local_date.in_(days)
                )
            )
            already.update((uid, d) for uid, d in rows)

        cards: dict = {}
        created = 0
        for uid, day in due.items():
            if (uid, day.isoformat()) in already:
                continue
            if day not in cards:
                cards[day] = await card_for_date(session, day)
            if cards[day] is None:
                continue
            session.add(Delivery(user_id=uid, card_id=cards[day].id, local_date=day.isoformat()))
            created += 1
        try:
            await session.commit()
        except IntegrityError:  # параллельный воркер успел раньше — не страшно
            await session.rollback()
            return 0
        return created


def backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(30 * 2 ** attempts, 3600))


async def claim(session, delivery_id: int) -> bool:
    """Занимает запись: сдвигает время следующей попытки, чтобы параллельный вызов крона её не взял.
    Если отправка оборвётся посреди, запись снова станет доступной через CLAIM_TIMEOUT."""
    now = utcnow()
    result = await session.execute(
        update(Delivery)
        .where(Delivery.id == delivery_id, Delivery.status == "pending", Delivery.next_attempt_at <= now)
        .values(next_attempt_at=now + CLAIM_TIMEOUT)
    )
    await session.commit()
    return result.rowcount == 1


async def send_one(bot: Bot, delivery_id: int, limiter: RateLimiter) -> None:
    async with SessionLocal() as session:
        if not await claim(session, delivery_id):
            return  # уже отправлена, отменена или её отправляет другой вызов
        delivery = await session.get(Delivery, delivery_id)
        user = await session.get(User, delivery.user_id)
        card = await session.get(Card, delivery.card_id)
        if user is None or not user.is_active:
            delivery.status = "skipped"  # пользователь нажал /stop после постановки в очередь
            await session.commit()
            return
        if card is None:
            delivery.status = "failed"
            delivery.error = "card not found"
            await session.commit()
            return

        await limiter.acquire()
        try:
            await bot.send_message(
                user.id,
                format_card_message(card, user.explain_lang or "ru"),
                reply_markup=card_keyboard(card.id),
                parse_mode="HTML",
            )
            delivery.status = "sent"
            delivery.sent_at = utcnow()
        except TelegramRetryAfter as e:  # 429: не считаем попыткой, ждём сколько просят
            limiter.penalize(e.retry_after)
            delivery.next_attempt_at = utcnow() + timedelta(seconds=e.retry_after + 1)
        except TelegramForbiddenError:  # пользователь заблокировал бота / удалил аккаунт
            delivery.status = "blocked"
            user.is_active = False
        except TelegramBadRequest as e:
            delivery.status = "failed"
            delivery.error = str(e)[:250]
            if "chat not found" in str(e).lower():
                user.is_active = False
        except (TelegramNetworkError, TelegramAPIError) as e:
            delivery.attempts += 1
            delivery.error = str(e)[:250]
            if delivery.attempts >= settings.max_attempts:
                delivery.status = "failed"
            else:
                delivery.next_attempt_at = utcnow() + backoff(delivery.attempts)
        await session.commit()


async def process_pending(bot: Bot, limiter: RateLimiter, batch: int = 500) -> int:
    async with SessionLocal() as session:
        ids = (
            (
                await session.execute(
                    select(Delivery.id)
                    .where(Delivery.status == "pending", Delivery.next_attempt_at <= utcnow())
                    .order_by(Delivery.id)
                    .limit(batch)
                )
            )
            .scalars()
            .all()
        )
    sem = asyncio.Semaphore(settings.send_concurrency)

    async def guarded(did: int) -> None:
        async with sem:
            await send_one(bot, did, limiter)

    results = await asyncio.gather(*(guarded(i) for i in ids), return_exceptions=True)
    for delivery_id, result in zip(ids, results):
        if isinstance(result, Exception):
            log.error("delivery %s failed", delivery_id, exc_info=result)
    return len(ids)


async def run_scheduler(bot: Bot) -> None:
    limiter = RateLimiter(settings.send_rate_per_sec)
    while True:
        try:
            created = await enqueue_due()
            sent = await process_pending(bot, limiter)
            if created or sent:
                log.info("scheduler: enqueued=%s processed=%s", created, sent)
        except Exception:  # планировщик не должен падать
            log.exception("scheduler tick failed")
        await asyncio.sleep(settings.scheduler_tick_sec)
