from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Card

DATA_FILE = Path(__file__).parent / "data" / "cards.json"

KIND_TITLES = {"word": "Слова дня", "holiday": "Традыцыя", "fact": "Цікавы факт"}
KIND_ICONS = {"word": "📖", "holiday": "🎉", "fact": "💡"}


async def seed_cards(session: AsyncSession) -> int:
    """Идемпотентно загружает карточки из JSON (по slug). Возвращает число новых."""
    items = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    existing = {c.slug: c for c in (await session.execute(select(Card))).scalars()}
    created = 0
    for item in items:
        card = existing.get(item["slug"])
        if card is None:
            card = Card(slug=item["slug"])
            session.add(card)
            created += 1
        for key, value in item.items():
            setattr(card, key, value)
    await session.commit()
    return created


async def card_for_date(session: AsyncSession, day: date) -> Optional[Card]:
    """Праздник с фиксированной датой имеет приоритет, иначе — ротация по номеру дня."""
    md = day.strftime("%m-%d")
    holiday_id = (
        await session.execute(select(Card.id).where(Card.month_day == md).order_by(Card.id).limit(1))
    ).scalar_one_or_none()
    if holiday_id is not None:
        return await session.get(Card, holiday_id)

    ids = (
        (await session.execute(select(Card.id).where(Card.month_day.is_(None)).order_by(Card.id))).scalars().all()
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
        "pos": card.pos,
        "example_be": card.example_be,
        "example_ru": card.example_ru,
        "body": card.body,
        "month_day": card.month_day,
        "level": card.level,
        "topic": card.topic,
        "saved": saved_status,
    }


def format_card_message(card: Card) -> str:
    """Текст карточки для сообщения бота (HTML parse mode)."""
    e = html.escape
    lines = [f"{KIND_ICONS.get(card.kind, '')} <b>{KIND_TITLES.get(card.kind, '')}</b>", ""]
    if card.kind == "word":
        lines.append(f"<b>{e(card.accent or card.be)}</b> — {e(card.ru)}")
        if card.pos:
            lines.append(f"<i>{e(card.pos)}</i>")
        if card.example_be:
            lines += ["", f"«{e(card.example_be)}»", f"<i>{e(card.example_ru or '')}</i>"]
    else:
        lines.append(f"<b>{e(card.be)}</b>")
        lines.append(e(card.ru))
    return "\n".join(lines)
