import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, update

from app import auth
from app.api import create_app
from app.config import settings
from app.db import SessionLocal
from app.models import Card, User

H = {"X-Dev-User": "88"}


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        yield c


async def test_today_is_404_without_cards(client):
    async with SessionLocal() as s:
        await s.execute(delete(Card))
        await s.commit()
    assert (await client.get("/api/today", headers=H)).status_code == 404


async def test_unknown_timezone_in_db_still_serves_today(client):
    await client.get("/api/me", headers=H)
    async with SessionLocal() as s:
        await s.execute(update(User).where(User.id == 88).values(tz="Mars/Base"))
        await s.commit()
    assert (await client.get("/api/today", headers=H)).status_code == 200


async def test_search_and_limit(client):
    found = (await client.get("/api/cards?q=вада&limit=5", headers=H)).json()
    assert any(c["be"] == "вада" for c in found)
    assert len((await client.get("/api/cards?limit=2", headers=H)).json()) == 2


async def test_card_not_found(client):
    assert (await client.get("/api/cards/99999", headers=H)).status_code == 404


async def test_save_validation_and_unknown_card(client):
    card_id = (await client.get("/api/cards?limit=1", headers=H)).json()[0]["id"]
    assert (await client.put(f"/api/cards/{card_id}/save", json={"status": "nope"}, headers=H)).status_code == 422
    assert (await client.put("/api/cards/99999/save", json={"status": "saved"}, headers=H)).status_code == 404


async def test_unsave_missing_is_ok_and_saved_list_orders(client):
    cards = (await client.get("/api/cards?limit=2", headers=H)).json()
    for c in cards:
        await client.put(f"/api/cards/{c['id']}/save", json={"status": "learned"}, headers=H)
    saved = (await client.get("/api/me/saved", headers=H)).json()
    assert {c["id"] for c in saved} == {c["id"] for c in cards}
    assert all(c["saved"] == "learned" for c in saved)
    assert (await client.delete("/api/cards/99999/save", headers=H)).json()["status"] is None


async def test_deactivate_and_reactivate(client):
    r = await client.put("/api/me/settings", json={"is_active": False}, headers=H)
    assert r.json()["is_active"] is False
    r = await client.put("/api/me/settings", json={"is_active": True}, headers=H)
    assert r.json()["is_active"] is True


async def test_web_login_creates_missing_user_then_forbids(client):
    from tests.test_web_login import widget_data  # переиспользуем подпись виджета

    r = await client.post("/api/web/login", json=widget_data(777, first_name="New"))
    assert r.status_code == 403
    async with SessionLocal() as s:
        assert (await s.get(User, 777)).role == "user"


async def test_sync_admin_roles_promotes_configured_ids(monkeypatch):
    monkeypatch.setattr(settings, "admin_ids", "555,abc")
    async with SessionLocal() as s:
        await auth.sync_admin_roles(s)
    async with SessionLocal() as s:
        assert (await s.get(User, 555)).role == "admin"
