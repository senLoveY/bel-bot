import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api import create_app

H = {"X-Dev-User": "77"}


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        yield c


async def test_requires_auth(client):
    assert (await client.get("/api/today")).status_code == 401


async def test_today_and_save_flow(client):
    today = (await client.get("/api/today", headers=H)).json()
    assert today["be"] and today["saved"] is None

    r = await client.put(f"/api/cards/{today['id']}/save", json={"status": "saved"}, headers=H)
    assert r.status_code == 200
    saved = (await client.get("/api/me/saved", headers=H)).json()
    assert [c["id"] for c in saved] == [today["id"]]

    await client.delete(f"/api/cards/{today['id']}/save", headers=H)
    assert (await client.get("/api/me/saved", headers=H)).json() == []


async def test_list_filters(client):
    words = (await client.get("/api/cards?kind=word", headers=H)).json()
    assert words and all(c["kind"] == "word" for c in words)
    found = (await client.get("/api/cards?q=вада", headers=H)).json()
    assert any(c["be"] == "вада" for c in found)


async def test_me_reports_streak_and_explain_lang(client):
    me = (await client.get("/api/me", headers=H)).json()
    assert me["streak"] == 1 and me["explain_lang"] == "ru"

    r = await client.put("/api/me/settings", json={"explain_lang": "be"}, headers=H)
    assert r.json()["explain_lang"] == "be"
    assert (await client.put("/api/me/settings", json={"explain_lang": "en"}, headers=H)).status_code == 422


async def test_card_contains_belarusian_explanation(client):
    card = (await client.get("/api/cards?kind=holiday", headers=H)).json()[0]
    assert card["summary_be"] and card["body_be"]


async def test_settings_validation(client):
    ok = await client.put("/api/me/settings", json={"send_time": "08:30", "tz": "Europe/Warsaw"}, headers=H)
    assert ok.json()["send_time"] == "08:30" and ok.json()["tz_set"] is True
    assert (await client.put("/api/me/settings", json={"send_time": "25:00"}, headers=H)).status_code == 422
    assert (await client.put("/api/me/settings", json={"tz": "Mars/Base"}, headers=H)).status_code == 422
