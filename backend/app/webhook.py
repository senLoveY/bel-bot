"""Serverless-вход для бота и рассылки.

/api/telegram/webhook — Telegram присылает обновления (вместо polling).
/api/cron/tick        — внешний крон раз в несколько минут ставит и отправляет ежедневные карточки."""
from __future__ import annotations

import hmac
import logging

from aiogram.types import Update
from fastapi import APIRouter, Header, HTTPException, Request

from .bot import get_dispatcher, make_bot
from .config import settings
from .delivery import RateLimiter, enqueue_due, process_pending

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


def secret_matches(received: str, expected: str) -> bool:
    return bool(expected) and hmac.compare_digest(received, expected)


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str = Header(default="")):
    if not secret_matches(x_telegram_bot_api_secret_token, settings.webhook_secret):
        raise HTTPException(401, "bad secret")
    data = await request.json()
    async with make_bot() as bot:
        try:
            update = Update.model_validate(data, context={"bot": bot})
            await get_dispatcher().feed_update(bot, update)
        except Exception:
            # отвечаем 200 всё равно: иначе Telegram будет повторять это обновление снова и снова
            log.exception("failed to handle update %s", data.get("update_id"))
    return {"ok": True}


@router.post("/cron/tick")
async def cron_tick(authorization: str = Header(default="")):
    if not secret_matches(authorization, f"Bearer {settings.cron_secret}" if settings.cron_secret else ""):
        raise HTTPException(401, "bad secret")
    enqueued = await enqueue_due()
    async with make_bot() as bot:
        processed = await process_pending(bot, RateLimiter(settings.send_rate_per_sec), batch=settings.cron_batch)
    return {"enqueued": enqueued, "processed": processed}
