import hashlib
import hmac
import time
from typing import Optional

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api import create_app
from app.db import SessionLocal
from app.models import User

TOKEN = "123456:TEST"


def widget_data(uid: int, auth_date: Optional[int] = None, **extra) -> dict:
    """Собирает данные, как их отдаёт Telegram Login Widget, и подписывает их токеном бота."""
    data = {"id": uid, "first_name": "Ala", "auth_date": auth_date or int(time.time())}
    data.update(extra)
    check = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hashlib.sha256(TOKEN.encode()).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return data


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        yield c


async def set_role(uid: int, role: str) -> None:
    async with SessionLocal() as s:
        user = await s.get(User, uid)
        if user is None:
            s.add(User(id=uid, first_name="Ala", role=role))
        else:
            user.role = role
        await s.commit()


def cookie_header(response) -> dict:
    return {"Cookie": f"admin_session={response.cookies['admin_session']}"}


async def test_bad_signature_rejected(client):
    data = widget_data(30)
    data["first_name"] = "Eve"  # подпись уже не совпадает
    assert (await client.post("/api/web/login", json=data)).status_code == 401


async def test_expired_login_rejected(client):
    await set_role(31, "admin")
    old = widget_data(31, auth_date=int(time.time()) - 2 * 24 * 3600)
    assert (await client.post("/api/web/login", json=old)).status_code == 401


async def test_plain_user_forbidden(client):
    await set_role(32, "user")
    assert (await client.post("/api/web/login", json=widget_data(32))).status_code == 403


async def test_admin_gets_session_cookie_and_api_access(client):
    await set_role(33, "admin")
    r = await client.post("/api/web/login", json=widget_data(33))
    assert r.status_code == 200
    assert "admin_session" in r.cookies

    # без заголовков Telegram: доступ только по cookie
    stats = await client.get("/api/admin/stats", headers=cookie_header(r))
    assert stats.status_code == 200


async def test_editor_cannot_manage_roles(client):
    await set_role(34, "editor")
    r = await client.post("/api/web/login", json=widget_data(34))
    assert r.status_code == 200
    assert (await client.get("/api/admin/users", headers=cookie_header(r))).status_code == 403


async def test_tampered_cookie_rejected(client):
    await set_role(35, "admin")
    r = await client.post("/api/web/login", json=widget_data(35))
    forged = f"35.{int(time.time()) + 999}.deadbeef"
    assert (await client.get("/api/admin/stats", headers={"Cookie": f"admin_session={forged}"})).status_code == 401


async def test_logout_clears_cookie(client):
    await set_role(36, "admin")
    r = await client.post("/api/web/login", json=widget_data(36))
    out = await client.post("/api/web/logout", headers=cookie_header(r))
    assert out.status_code == 200
    assert "admin_session" in out.headers.get("set-cookie", "")
