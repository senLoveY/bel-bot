"""Аналитика для админки: активность по дням, открываемость карточек, удержание, что сохраняют.

Дни считаются по UTC. Удержание dN: доля пользователей, которые проявили активность ровно
на N-й день после регистрации (среди тех, кто зарегистрировался не позднее чем N дней назад
и не раньше окна в 60 дней, за которое хранятся события)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Optional

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Card, Delivery, Event, SavedCard, User

WINDOW_DAYS = 60
OPEN_KINDS = ("open_today", "open_card")


def record_event(session: AsyncSession, user_id: int, kind: str, card_id: Optional[int] = None) -> None:
    """Добавляет событие в текущую сессию; сохраняется вместе с остальными изменениями запроса."""
    session.add(Event(user_id=user_id, kind=kind, card_id=card_id))


def _start_of(day: date) -> datetime:
    return datetime.combine(day, time.min)


async def build_analytics(session: AsyncSession, today: date) -> dict:
    window_start = today - timedelta(days=WINDOW_DAYS)
    events = (
        await session.execute(
            select(Event.user_id, Event.kind, Event.created_at).where(Event.created_at >= _start_of(window_start))
        )
    ).all()

    active_by_day: dict = defaultdict(set)
    for user_id, _, created_at in events:
        active_by_day[created_at.date()].add(user_id)

    daily_active = [
        {"day": day.isoformat(), "users": len(active_by_day.get(day, ()))}
        for day in (today - timedelta(days=i) for i in range(13, -1, -1))
    ]

    week_start = today - timedelta(days=6)
    week_openers = {
        user_id for user_id, kind, created_at in events if kind in OPEN_KINDS and created_at.date() >= week_start
    }
    week_opens = sum(1 for _, kind, created_at in events if kind in OPEN_KINDS and created_at.date() >= week_start)
    recipients = set(
        (
            await session.execute(
                select(Delivery.user_id).where(Delivery.status == "sent", Delivery.sent_at >= _start_of(week_start))
            )
        )
        .scalars()
        .all()
    )

    users = (await session.execute(select(User.id, User.created_at))).all()
    retention = {}
    for n in (1, 7, 30):
        cohort = [
            (user_id, created_at.date())
            for user_id, created_at in users
            if window_start <= created_at.date() <= today - timedelta(days=n)
        ]
        retained = sum(1 for user_id, joined in cohort if user_id in active_by_day.get(joined + timedelta(days=n), ()))
        retention[f"d{n}"] = {
            "cohort": len(cohort),
            "retained": retained,
            "rate": round(retained / len(cohort), 3) if cohort else None,
        }

    saves = (
        await session.execute(
            select(
                SavedCard.card_id,
                func.count(),
                func.sum(case((SavedCard.status == "learned", 1), else_=0)),
            )
            .group_by(SavedCard.card_id)
            .order_by(func.count().desc(), SavedCard.card_id)
            .limit(10)
        )
    ).all()
    cards = {
        c.id: c
        for c in (await session.execute(select(Card).where(Card.id.in_([row[0] for row in saves])))).scalars()
    }
    top_saved = [
        {
            "card_id": card_id,
            "title": (cards[card_id].accent or cards[card_id].be) if card_id in cards else str(card_id),
            "kind": cards[card_id].kind if card_id in cards else None,
            "saves": total,
            "learned": int(learned or 0),
        }
        for card_id, total, learned in saves
    ]

    return {
        "daily_active": daily_active,
        "week": {
            "opens": week_opens,
            "openers": len(week_openers),
            "recipients": len(recipients),
            "open_rate": round(len(week_openers & recipients) / len(recipients), 3) if recipients else None,
        },
        "retention": retention,
        "top_saved": top_saved,
    }
