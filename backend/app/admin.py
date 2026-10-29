"""Админ-API: мониторинг, карточки, очередь правок с проверкой, расписание и роли.

Роли: user (обычный), editor (предлагает правки), admin (одобряет, расписание, роли).
Правки редакторов не применяются сразу: сначала pending, потом approve/reject админом.
Правки админа применяются сразу (в истории — одобренные им же).
Автор не может одобрить собственную правку из очереди."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .analytics import build_analytics
from .auth import require_role
from .cards import card_to_dict
from .config import settings
from .db import get_session, utcnow
from .models import Card, CardRevision, Delivery, Schedule, User

router = APIRouter(prefix="/api/admin")

EDITOR = require_role("editor", "admin")
ADMIN = require_role("admin")

KINDS = {"word", "holiday", "fact"}
LEVELS = {"A1", "A2", "B1", "B2"}
ROLES = {"user", "editor", "admin"}
CARD_FIELDS = {
    "kind", "be", "accent", "ru", "pos", "example_be", "example_ru",
    "body", "summary_be", "body_be", "month_day", "level", "topic",
}
REQUIRED_FIELDS = {"kind", "be", "ru"}
MD_RE = re.compile(r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_payload(payload: dict, create: bool) -> dict:
    unknown = set(payload) - CARD_FIELDS
    if unknown:
        raise HTTPException(422, f"unknown fields: {sorted(unknown)}")
    if create:
        missing = REQUIRED_FIELDS - set(payload)
        if missing:
            raise HTTPException(422, f"missing fields: {sorted(missing)}")
    if "kind" in payload and payload["kind"] not in KINDS:
        raise HTTPException(422, "kind must be word, holiday or fact")
    if "level" in payload and payload["level"] not in LEVELS:
        raise HTTPException(422, "level must be A1, A2, B1 or B2")
    if payload.get("month_day") and not MD_RE.match(payload["month_day"]):
        raise HTTPException(422, "month_day must be MM-DD")
    for key, value in payload.items():
        limit = getattr(Card.__table__.c[key].type, "length", None)  # у Text длины нет
        if limit and value is not None and len(str(value)) > limit:
            raise HTTPException(422, f"{key} is too long: {len(str(value))} > {limit} characters")
    for key in ("kind", "be", "ru", "body", "level"):  # эти поля в базе не могут быть пустыми
        if key in payload and (payload[key] is None or not str(payload[key]).strip()):
            if key == "body":
                payload[key] = ""
            elif key == "level":
                payload[key] = "A1"
            else:
                raise HTTPException(422, f"{key} must not be empty")
    return payload


def card_admin_dict(card: Card) -> dict:
    return {**card_to_dict(card), "published": card.published}


class RevisionIn(BaseModel):
    card_id: Optional[int] = None  # None — новая карточка
    payload: dict


class RejectIn(BaseModel):
    note: Optional[str] = None


class PublishIn(BaseModel):
    published: bool


class ScheduleIn(BaseModel):
    day: str
    card_id: int


class RoleIn(BaseModel):
    role: str


async def count(session: AsyncSession, stmt) -> int:
    return (await session.execute(stmt)).scalar_one()


@router.get("/stats")
async def stats(_: User = Depends(EDITOR), session: AsyncSession = Depends(get_session)):
    today = datetime.now(timezone.utc).date()
    since = (today - timedelta(days=1)).isoformat()
    by_status = dict(
        (await session.execute(
            select(Delivery.status, func.count()).where(Delivery.local_date >= since).group_by(Delivery.status)
        )).all()
    )
    errors = (
        await session.execute(
            select(Delivery)
            .where(Delivery.status.in_(["failed", "blocked"]))
            .order_by(Delivery.id.desc())
            .limit(20)
        )
    ).scalars().all()
    avg_streak = (await session.execute(select(func.avg(User.streak)).where(User.streak > 0))).scalar()
    return {
        "users_total": await count(session, select(func.count(User.id))),
        "users_active": await count(session, select(func.count(User.id)).where(User.is_active.is_(True))),
        "users_blocked": await count(session, select(func.count(User.id)).where(User.is_active.is_(False))),
        "deliveries_last_24h": by_status,
        "avg_streak": round(float(avg_streak or 0), 1),
        "cards_total": await count(session, select(func.count(Card.id))),
        "cards_published": await count(session, select(func.count(Card.id)).where(Card.published.is_(True))),
        "revisions_pending": await count(session, select(func.count(CardRevision.id)).where(CardRevision.status == "pending")),
        "recent_errors": [
            {"id": d.id, "user_id": d.user_id, "status": d.status, "error": d.error, "local_date": d.local_date}
            for d in errors
        ],
    }


@router.get("/analytics")
async def analytics(_: User = Depends(EDITOR), session: AsyncSession = Depends(get_session)):
    return await build_analytics(session, datetime.now(timezone.utc).date())


@router.get("/cards")
async def admin_cards(
    q: Optional[str] = None,
    kind: Optional[str] = None,
    published: Optional[bool] = None,
    limit: int = Query(100, le=300),
    _: User = Depends(EDITOR),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Card).order_by(Card.id)
    if kind:
        stmt = stmt.where(Card.kind == kind)
    if published is not None:
        stmt = stmt.where(Card.published.is_(published))
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(Card.be.ilike(like) | Card.ru.ilike(like))
    cards = (await session.execute(stmt.limit(limit))).scalars().all()
    return [card_admin_dict(c) for c in cards]


@router.put("/cards/{card_id}/published")
async def set_published(card_id: int, body: PublishIn, _: User = Depends(ADMIN), session: AsyncSession = Depends(get_session)):
    card = await session.get(Card, card_id)
    if card is None:
        raise HTTPException(404, "card not found")
    card.published = body.published
    await session.commit()
    return card_admin_dict(card)


async def apply_revision(session: AsyncSession, rev: CardRevision, reviewer: User) -> Card:
    """Применяет правку к карточке (или создаёт новую) и помечает её одобренной."""
    payload = json.loads(rev.payload)
    if rev.card_id is None:
        card = Card(**payload, slug=f"{payload['kind']}-{uuid.uuid4().hex[:8]}", published=True)
        session.add(card)
        await session.flush()
        rev.card_id = card.id
    else:
        card = await session.get(Card, rev.card_id)
        if card is None:
            raise HTTPException(404, "card not found")
        for key, value in payload.items():
            setattr(card, key, value)
    rev.status = "approved"
    rev.reviewer_id = reviewer.id
    rev.reviewed_at = utcnow()
    return card


@router.post("/revisions", status_code=201)
async def propose_revision(body: RevisionIn, user: User = Depends(EDITOR), session: AsyncSession = Depends(get_session)):
    create = body.card_id is None
    payload = validate_payload(body.payload, create=create)
    if not create and await session.get(Card, body.card_id) is None:
        raise HTTPException(404, "card not found")
    rev = CardRevision(card_id=body.card_id, payload=json.dumps(payload, ensure_ascii=False), author_id=user.id)
    session.add(rev)
    if user.role != "admin":
        await session.commit()
        return {"id": rev.id, "status": rev.status}
    # правку админа применяем сразу; в истории она остаётся одобренной им же
    card = await apply_revision(session, rev, reviewer=user)
    await session.commit()
    return {"id": rev.id, "status": rev.status, "card": card_admin_dict(card)}


def revision_dict(rev: CardRevision, authors: dict, cards: dict) -> dict:
    author = authors.get(rev.author_id)
    current = cards.get(rev.card_id)
    return {
        "id": rev.id,
        "status": rev.status,
        "card_id": rev.card_id,
        "author": (author.first_name or str(author.id)) if author else str(rev.author_id),
        "author_id": rev.author_id,
        "payload": json.loads(rev.payload),
        "current": card_admin_dict(current) if current else None,
        "note": rev.note,
        "created_at": rev.created_at.isoformat(),
    }


@router.get("/revisions")
async def list_revisions(
    status: str = "pending",
    _: User = Depends(EDITOR),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(CardRevision).where(CardRevision.status == status).order_by(CardRevision.id.desc()).limit(100)
        )
    ).scalars().all()
    author_ids = {r.author_id for r in rows}
    card_ids = {r.card_id for r in rows if r.card_id}
    authors = {u.id: u for u in (await session.execute(select(User).where(User.id.in_(author_ids)))).scalars()}
    cards = {c.id: c for c in (await session.execute(select(Card).where(Card.id.in_(card_ids)))).scalars()}
    return [revision_dict(r, authors, cards) for r in rows]


async def pending_revision(session: AsyncSession, rev_id: int, reviewer: User) -> CardRevision:
    rev = await session.get(CardRevision, rev_id)
    if rev is None:
        raise HTTPException(404, "revision not found")
    if rev.status != "pending":
        raise HTTPException(409, "revision already reviewed")
    if rev.author_id == reviewer.id:
        raise HTTPException(403, "cannot review your own revision")
    return rev


@router.post("/revisions/{rev_id}/approve")
async def approve_revision(rev_id: int, user: User = Depends(ADMIN), session: AsyncSession = Depends(get_session)):
    rev = await pending_revision(session, rev_id, user)
    card = await apply_revision(session, rev, reviewer=user)
    await session.commit()
    return card_admin_dict(card)


@router.post("/revisions/{rev_id}/reject")
async def reject_revision(rev_id: int, body: RejectIn, user: User = Depends(ADMIN), session: AsyncSession = Depends(get_session)):
    rev = await pending_revision(session, rev_id, user)
    rev.status = "rejected"
    rev.reviewer_id = user.id
    rev.note = body.note
    rev.reviewed_at = utcnow()
    await session.commit()
    return {"id": rev.id, "status": rev.status}


@router.get("/schedule")
async def list_schedule(days: int = Query(14, le=60), _: User = Depends(EDITOR), session: AsyncSession = Depends(get_session)):
    start = datetime.now(timezone.utc).date()
    keys = [(start + timedelta(days=i)).isoformat() for i in range(days)]
    rows = (
        await session.execute(select(Schedule, Card).join(Card, Card.id == Schedule.card_id).where(Schedule.day.in_(keys)))
    ).all()
    manual = {s.day: card_admin_dict(c) for s, c in rows}
    return [{"day": k, "card": manual.get(k)} for k in keys]


@router.put("/schedule")
async def set_schedule(body: ScheduleIn, user: User = Depends(ADMIN), session: AsyncSession = Depends(get_session)):
    if not DAY_RE.match(body.day):
        raise HTTPException(422, "day must be YYYY-MM-DD")
    card = await session.get(Card, body.card_id)
    if card is None:
        raise HTTPException(404, "card not found")
    if not card.published:
        raise HTTPException(422, "publish the card before scheduling it")
    row = await session.get(Schedule, body.day)
    if row is None:
        session.add(Schedule(day=body.day, card_id=body.card_id, set_by=user.id))
    else:
        row.card_id = body.card_id
        row.set_by = user.id
    await session.commit()
    return {"day": body.day, "card": card_admin_dict(card)}


@router.delete("/schedule/{day}")
async def clear_schedule(day: str, _: User = Depends(ADMIN), session: AsyncSession = Depends(get_session)):
    row = await session.get(Schedule, day)
    if row is not None:
        await session.delete(row)
        await session.commit()
    return {"day": day, "card": None}


@router.get("/users")
async def list_users(q: Optional[str] = None, _: User = Depends(ADMIN), session: AsyncSession = Depends(get_session)):
    stmt = select(User).order_by(User.id.desc()).limit(100)
    if q:
        stmt = stmt.where(User.first_name.ilike(f"%{q}%") | User.username.ilike(f"%{q}%"))
    users = (await session.execute(stmt)).scalars().all()
    return [
        {"id": u.id, "first_name": u.first_name, "username": u.username, "role": u.role, "is_active": u.is_active}
        for u in users
    ]


@router.put("/users/{user_id}/role")
async def set_role(user_id: int, body: RoleIn, admin: User = Depends(ADMIN), session: AsyncSession = Depends(get_session)):
    if body.role not in ROLES:
        raise HTTPException(422, "role must be user, editor or admin")
    if user_id == admin.id and body.role != "admin":
        raise HTTPException(400, "cannot remove your own admin role")
    if user_id in settings.admin_id_set and body.role != "admin":
        raise HTTPException(400, "this admin is set in ADMIN_IDS; change it in the environment variables")
    target = await session.get(User, user_id)
    if target is None:
        raise HTTPException(404, "user not found")
    target.role = body.role
    await session.commit()
    return {"id": target.id, "role": target.role}
