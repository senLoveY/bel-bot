from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app import bot
from app.analytics import build_analytics
from app.api import create_app
from app.db import SessionLocal
from app.models import Card, Delivery, Event, SavedCard, User

TODAY = date(2026, 3, 31)


def at(day: date, hour: int = 12) -> datetime:
    return datetime(day.year, day.month, day.day, hour)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        yield c


async def card_ids(n: int = 3) -> list:
    async with SessionLocal() as s:
        return (await s.execute(select(Card.id).order_by(Card.id).limit(n))).scalars().all()


async def test_retention_daily_active_and_top_saved():
    c1, c2, c3 = await card_ids()
    joined = TODAY - timedelta(days=10)
    async with SessionLocal() as s:
        # трое пришли 10 дней назад: 1 вернулся на 1-й и 7-й день, 2 — только на 1-й, 3 не вернулся
        for uid in (1, 2, 3):
            s.add(User(id=uid, first_name="u", created_at=at(joined)))
        s.add(User(id=4, first_name="new", created_at=at(TODAY)))  # слишком новый для d1
        s.add_all(
            [
                Event(user_id=1, kind="open_today", created_at=at(joined + timedelta(days=1))),
                Event(user_id=1, kind="open_card", created_at=at(joined + timedelta(days=7))),
                Event(user_id=2, kind="save", created_at=at(joined + timedelta(days=1))),
                Event(user_id=1, kind="open_today", created_at=at(TODAY)),
                Event(user_id=4, kind="open_today", created_at=at(TODAY)),
                Event(user_id=4, kind="open_card", created_at=at(TODAY, 13)),
            ]
        )
        s.add_all(
            [
                Delivery(user_id=1, card_id=c1, local_date=TODAY.isoformat(), status="sent", sent_at=at(TODAY, 9)),
                Delivery(user_id=3, card_id=c1, local_date=TODAY.isoformat(), status="sent", sent_at=at(TODAY, 9)),
            ]
        )
        s.add_all(
            [
                SavedCard(user_id=1, card_id=c2, status="saved"),
                SavedCard(user_id=2, card_id=c2, status="learned"),
                SavedCard(user_id=3, card_id=c3, status="saved"),
            ]
        )
        await s.commit()

        result = await build_analytics(s, TODAY)

    assert result["retention"]["d1"] == {"cohort": 3, "retained": 2, "rate": 0.667}
    assert result["retention"]["d7"] == {"cohort": 3, "retained": 1, "rate": 0.333}
    assert result["retention"]["d30"] == {"cohort": 0, "retained": 0, "rate": None}

    assert len(result["daily_active"]) == 14
    assert result["daily_active"][-1] == {"day": TODAY.isoformat(), "users": 2}

    week = result["week"]
    assert week["opens"] == 4 and week["openers"] == 2  # 28.03 (7-й день) тоже входит в последние 7 дней
    assert week["recipients"] == 2 and week["open_rate"] == 0.5  # из получивших (1, 3) открыл только 1

    top = result["top_saved"]
    assert top[0]["card_id"] == c2 and top[0]["saves"] == 2 and top[0]["learned"] == 1
    assert top[1]["card_id"] == c3


async def test_empty_database_gives_zeros_not_errors():
    async with SessionLocal() as s:
        result = await build_analytics(s, TODAY)
    assert result["week"]["open_rate"] is None
    assert result["top_saved"] == []
    assert all(day["users"] == 0 for day in result["daily_active"])


async def test_analytics_endpoint_requires_editor(client):
    await client.get("/api/me", headers={"X-Dev-User": "90"})
    assert (await client.get("/api/admin/analytics", headers={"X-Dev-User": "90"})).status_code == 403
    async with SessionLocal() as s:
        (await s.get(User, 90)).role = "editor"
        await s.commit()
    r = await client.get("/api/admin/analytics", headers={"X-Dev-User": "90"})
    assert r.status_code == 200 and set(r.json()) == {"daily_active", "week", "retention", "top_saved"}


async def test_app_actions_are_recorded_as_events(client):
    h = {"X-Dev-User": "91"}
    today = (await client.get("/api/today", headers=h)).json()
    await client.get(f"/api/cards/{today['id']}", headers=h)
    await client.put(f"/api/cards/{today['id']}/save", json={"status": "saved"}, headers=h)
    await client.put(f"/api/cards/{today['id']}/save", json={"status": "learned"}, headers=h)
    async with SessionLocal() as s:
        kinds = (await s.execute(select(Event.kind).where(Event.user_id == 91).order_by(Event.id))).scalars().all()
    assert kinds == ["open_today", "open_card", "save", "learn"]


async def test_bot_buttons_are_recorded_as_events():
    (card_id,) = await card_ids(1)
    call = MagicMock(data=f"known:{card_id}", answer=AsyncMock())
    call.from_user = SimpleNamespace(id=92, first_name="Ala", username="ala")
    await bot.on_card_button(call)
    async with SessionLocal() as s:
        event = (await s.execute(select(Event).where(Event.user_id == 92))).scalar_one()
    assert event.kind == "learn" and event.card_id == card_id
