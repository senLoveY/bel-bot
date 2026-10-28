from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Card, Schedule

DATA_FILE = Path(__file__).parent / "data" / "cards.json"

KIND_TITLES = {"word": "Слова дня", "holiday": "Традыцыя", "fact": "Цікавы факт"}
KIND_ICONS = {"word": "📖", "holiday": "🎉", "fact": "💡"}


async def seed_cards(session: AsyncSession) -> int:
    """Добавляет из JSON только новые карточки (по slug). Существующие не трогаем:
    после запуска база — источник истины, а правки делаются через админку."""
    items = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    existing = set((await session.execute(select(Card.slug))).scalars())
    created = 0
    for item in items:
        if item["slug"] in existing:
            continue
        session.add(Card(**item))
        created += 1
    await session.commit()
    return created


async def card_for_date(session: AsyncSession, day: date) -> Optional[Card]:
    """Порядок: ручное расписание → праздник на эту дату → ротация по номеру дня."""
    scheduled = (
        await session.execute(
            select(Card)
            .join(Schedule, Schedule.card_id == Card.id)
            .where(Schedule.day == day.isoformat(), Card.published.is_(True))
        )
    ).scalar_one_or_none()
    if scheduled is not None:
        return scheduled

    md = day.strftime("%m-%d")
    holiday_id = (
        await session.execute(
            select(Card.id).where(Card.month_day == md, Card.published.is_(True)).order_by(Card.id).limit(1)
        )
    ).scalar_one_or_none()
    if holiday_id is not None:
        return await session.get(Card, holiday_id)

    ids = (
        (
            await session.execute(
                select(Card.id).where(Card.month_day.is_(None), Card.published.is_(True)).order_by(Card.id)
            )
        )
        .scalars()
        .all()
    )
    if not ids:
        return None
    return await session.get(Card, ids[day.toordinal() % len(ids)])


def card_to_dict(card: Card, saved_status: Optional[str] = None) -> dict:
    return {
        "id": card.id,
        "kind": card.kind,
        "be": card.be,
        "accent": card.accent,
        "ru": card.ru,
        "summary_be": card.summary_be,
        "pos": card.pos,
        "example_be": card.example_be,
        "example_ru": card.example_ru,
        "body": card.body,
        "body_be": card.body_be,
        "month_day": card.month_day,
        "level": card.level,
        "topic": card.topic,
        "saved": saved_status,
    }


def explanation(card: Card, lang: str = "ru") -> str:
    """Краткое пояснение на выбранном языке; если белорусского нет, показываем русское."""
    if lang == "be" and card.summary_be:
        return card.summary_be
    return card.ru


def format_card_message(card: Card, lang: str = "ru") -> str:
    """Текст карточки для сообщения бота (HTML parse mode)."""
    e = html.escape
    lines = [f"{KIND_ICONS.get(card.kind, '')} <b>{KIND_TITLES.get(card.kind, '')}</b>", ""]
    if card.kind == "word":
        lines.append(f"<b>{e(card.accent or card.be)}</b> — {e(explanation(card, lang))}")
        if card.pos:
            lines.append(f"<i>{e(card.pos)}</i>")
        if card.example_be:
            lines += ["", f"«{e(card.example_be)}»", f"<i>{e(card.example_ru or '')}</i>"]
    else:
        lines.append(f"<b>{e(card.be)}</b>")
        lines.append(e(explanation(card, lang)))
    return "\n".join(lines)
