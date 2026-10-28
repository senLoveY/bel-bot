from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .config import settings
from .db import Base, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)  # Telegram user id
    first_name: Mapped[str] = mapped_column(String(128), default="")
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tz: Mapped[str] = mapped_column(String(64), default=settings.default_tz)
    tz_set: Mapped[bool] = mapped_column(Boolean, default=False)  # выбрана ли зона пользователем/приложением
    send_time: Mapped[str] = mapped_column(String(5), default=settings.default_send_time)  # "HH:MM" по tz
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # False — пауза или бот заблокирован
    explain_lang: Mapped[str] = mapped_column(String(2), default="ru")  # язык пояснений: ru | be
    streak: Mapped[int] = mapped_column(Integer, default=0)  # дней подряд, когда открывали приложение
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_day: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD, локальная дата
    role: Mapped[str] = mapped_column(String(16), default="user")  # user | editor | admin
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)  # word | holiday | fact
    be: Mapped[str] = mapped_column(String(256))  # слово / заголовок по-белорусски
    accent: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)  # с ударением
    ru: Mapped[str] = mapped_column(String(512))  # перевод / краткое пояснение
    pos: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    example_be: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    example_ru: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary_be: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # краткое пояснение по-белорусски
    body: Mapped[str] = mapped_column(Text, default="")  # развёрнутый текст для Mini App (русский)
    body_be: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # то же по-белорусски
    month_day: Mapped[Optional[str]] = mapped_column(String(5), nullable=True, index=True)  # "07-07"
    level: Mapped[str] = mapped_column(String(4), default="A1")
    topic: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, default=True)  # черновики пользователям не показываются


class Schedule(Base):
    """Ручное назначение: какая карточка покажется в конкретный день. Перекрывает ротацию."""

    __tablename__ = "schedule"

    day: Mapped[str] = mapped_column(String(10), primary_key=True)  # YYYY-MM-DD
    card_id: Mapped[int] = mapped_column(Integer, ForeignKey("cards.id"))
    set_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)


class CardRevision(Base):
    """Предложенное изменение карточки. Применяется только после одобрения админом."""

    __tablename__ = "card_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("cards.id"), nullable=True)  # None — новая карточка
    payload: Mapped[str] = mapped_column(Text)  # JSON с полями карточки
    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending | approved | rejected
    reviewer_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Delivery(Base):
    """Очередь и журнал ежедневной рассылки: одна запись на пользователя в день."""

    __tablename__ = "deliveries"
    __table_args__ = (UniqueConstraint("user_id", "local_date", name="uq_delivery_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    card_id: Mapped[int] = mapped_column(Integer, ForeignKey("cards.id"))
    local_date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD в часовом поясе пользователя
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending|sent|failed|blocked
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)


class SavedCard(Base):
    __tablename__ = "saved_cards"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), primary_key=True)
    card_id: Mapped[int] = mapped_column(Integer, ForeignKey("cards.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="saved")  # saved | learned
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
