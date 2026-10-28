from datetime import date

from app.cards import card_for_date, format_card_message
from app.db import SessionLocal


async def test_holiday_wins_on_its_date():
    async with SessionLocal() as s:
        card = await card_for_date(s, date(2026, 7, 7))
        assert card.slug == "holiday-kupalle"


async def test_rotation_is_deterministic_and_skips_fixed_holidays():
    async with SessionLocal() as s:
        a = await card_for_date(s, date(2026, 3, 10))
        b = await card_for_date(s, date(2026, 3, 10))
        assert a.id == b.id and a.month_day is None
        nxt = await card_for_date(s, date(2026, 3, 11))
        assert nxt.id != a.id


async def test_message_escapes_html():
    async with SessionLocal() as s:
        card = await card_for_date(s, date(2026, 3, 10))
        card.ru = "<b>x</b>"
        assert "&lt;b&gt;x&lt;/b&gt;" in format_card_message(card)
