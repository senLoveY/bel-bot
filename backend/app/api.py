from __future__ import annotations

import os
import re
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .admin import router as admin_router
from .analytics import record_event
from .auth import (
    SESSION_COOKIE,
    SESSION_TTL,
    current_user,
    make_session_token,
    verify_login_token,
)
from .config import settings
from .cards import card_for_date, card_to_dict
from .clock import user_today
from .db import get_session, utcnow
from .models import Card, SavedCard, UsedLoginToken, User
from .streak import current_streak, touch_streak

router = APIRouter(prefix="/api")

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


async def saved_map(session: AsyncSession, user_id: int) -> dict:
    rows = (await session.execute(select(SavedCard).where(SavedCard.user_id == user_id))).scalars()
    return {r.card_id: r.status for r in rows}


class SettingsIn(BaseModel):
    send_time: Optional[str] = None
    tz: Optional[str] = None
    is_active: Optional[bool] = None
    explain_lang: Optional[str] = None  # ru | be


class SaveIn(BaseModel):
    status: str = "saved"  # saved | learned


def user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "first_name": user.first_name,
        "tz": user.tz,
        "tz_set": user.tz_set,
        "send_time": user.send_time,
        "is_active": user.is_active,
        "explain_lang": user.explain_lang or "ru",
        "streak": current_streak(user, user_today(user)),
        "longest_streak": user.longest_streak or 0,
        "role": user.role or "user",
    }


HEALTH_VARS = ("BOT_TOKEN", "DATABASE_URL", "WEBAPP_URL", "ADMIN_IDS", "WEBHOOK_SECRET", "CRON_SECRET")


@router.get("/health")
async def health():
    """Диагностика без секретов: какие переменные заданы (да/нет) и какой драйвер базы выбран."""
    return {
        "serverless": settings.serverless,
        "vercel_env": os.environ.get("VERCEL_ENV"),
        "database_driver": settings.database_url.split("://", 1)[0],
        # схема из окружения на момент запроса (без хоста и пароля): видно, если переменная появилась после старта
        "env_database_driver": os.environ.get("DATABASE_URL", "").split("://", 1)[0] or None,
        "env_set": {name: bool(os.environ.get(name)) for name in HEALTH_VARS},
    }


@router.get("/me")
async def me(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    # открытие приложения — это визит за сегодня, он двигает серию
    touch_streak(user, user_today(user))
    session.add(user)
    await session.commit()
    return user_to_dict(user)


@router.put("/me/settings")
async def update_settings(body: SettingsIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    if body.send_time is not None:
        if not TIME_RE.match(body.send_time):
            raise HTTPException(422, "send_time must be HH:MM")
        user.send_time = body.send_time
    if body.tz is not None:
        try:
            ZoneInfo(body.tz)
        except (ZoneInfoNotFoundError, ValueError):
            raise HTTPException(422, "unknown timezone")
        user.tz = body.tz
        user.tz_set = True
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.explain_lang is not None:
        if body.explain_lang not in ("ru", "be"):
            raise HTTPException(422, "explain_lang must be ru or be")
        user.explain_lang = body.explain_lang
    session.add(user)
    await session.commit()
    return user_to_dict(user)


@router.get("/today")
async def today(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    card = await card_for_date(session, user_today(user))
    if card is None:
        raise HTTPException(404, "no cards")
    record_event(session, user.id, "open_today", card.id)
    await session.commit()
    return card_to_dict(card, (await saved_map(session, user.id)).get(card.id))


@router.get("/cards")
async def list_cards(
    kind: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Card).where(Card.published.is_(True)).order_by(Card.id)
    if kind:
        stmt = stmt.where(Card.kind == kind)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(Card.be.ilike(like) | Card.ru.ilike(like))
    cards = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    saved = await saved_map(session, user.id)
    return [card_to_dict(c, saved.get(c.id)) for c in cards]


@router.get("/cards/{card_id}")
async def get_card(card_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    card = await session.get(Card, card_id)
    if card is None or not card.published:
        raise HTTPException(404, "card not found")
    record_event(session, user.id, "open_card", card.id)
    await session.commit()
    return card_to_dict(card, (await saved_map(session, user.id)).get(card.id))


@router.put("/cards/{card_id}/save")
async def save_card(card_id: int, body: SaveIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    if body.status not in ("saved", "learned"):
        raise HTTPException(422, "bad status")
    if await session.get(Card, card_id) is None:
        raise HTTPException(404, "card not found")
    row = await session.get(SavedCard, (user.id, card_id))
    if row is None:
        session.add(SavedCard(user_id=user.id, card_id=card_id, status=body.status))
    else:
        row.status = body.status
    record_event(session, user.id, "learn" if body.status == "learned" else "save", card_id)
    await session.commit()
    return {"card_id": card_id, "status": body.status}


@router.delete("/cards/{card_id}/save")
async def unsave_card(card_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    row = await session.get(SavedCard, (user.id, card_id))
    if row is not None:
        await session.delete(row)
        await session.commit()
    return {"card_id": card_id, "status": None}


@router.get("/me/saved")
async def my_saved(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(
            select(Card, SavedCard.status)
            .join(SavedCard, SavedCard.card_id == Card.id)
            .where(SavedCard.user_id == user.id, Card.published.is_(True))
            .order_by(SavedCard.created_at.desc())
        )
    ).all()
    return [card_to_dict(card, status) for card, status in rows]


def set_session_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        make_session_token(user_id),
        max_age=SESSION_TTL,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


@router.get("/web/tg-login")
async def tg_login(token: str, session: AsyncSession = Depends(get_session)):
    """Ссылка из бота (/admin): одноразовый токен -> сессия -> переход в админку."""
    verified = verify_login_token(token)
    if verified is None:
        raise HTTPException(401, "link expired or already used")
    user_id, nonce = verified
    # одноразовость: nonce — первичный ключ, вторая вставка того же значения падает
    await session.execute(delete(UsedLoginToken).where(UsedLoginToken.used_at < utcnow() - timedelta(days=1)))
    session.add(UsedLoginToken(nonce=nonce))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(401, "link expired or already used")
    user = await session.get(User, user_id)
    if user is None or user.role not in ("editor", "admin"):
        raise HTTPException(403, "forbidden")
    response = RedirectResponse("/admin", status_code=303)
    set_session_cookie(response, user.id)
    return response


@router.post("/web/logout")
async def web_logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@asynccontextmanager
async def lifespan(_: FastAPI):
    from .setup import setup_database

    if not settings.serverless:  # на Vercel подготовка идёт лениво, см. setup.ensure_ready
        await setup_database()
    yield


def create_app() -> FastAPI:
    from .setup import ensure_ready
    from .webhook import router as webhook_router

    # ensure_ready работает только в serverless: там подготовка базы идёт при первом запросе
    app = FastAPI(title="Belarusian Daily", lifespan=lifespan, dependencies=[Depends(ensure_ready)])
    app.include_router(router)
    app.include_router(admin_router)
    app.include_router(webhook_router)

    dist = Path(__file__).resolve().parents[2] / "webapp" / "dist"
    if dist.is_dir():
        # сайт админки должен быть объявлен до общего маршрута статики
        app.add_api_route("/admin", lambda: FileResponse(dist / "admin" / "index.html"), include_in_schema=False)
        app.mount("/", StaticFiles(directory=dist, html=True), name="webapp")
    return app


app = create_app()
