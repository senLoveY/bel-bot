from __future__ import annotations

from typing import Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from .config import settings


def webapp_url(card_id: Optional[int] = None, tab: Optional[str] = None) -> str:
    params = []
    if card_id:
        params.append(f"card={card_id}")
    if tab:
        params.append(f"tab={tab}")
    return settings.webapp_url + ("?" + "&".join(params) if params else "")


def card_keyboard(card_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 Падрабязней", web_app=WebAppInfo(url=webapp_url(card_id)))],
            [
                InlineKeyboardButton(text="⭐ Захаваць", callback_data=f"save:{card_id}"),
                InlineKeyboardButton(text="✅ Ведаў", callback_data=f"known:{card_id}"),
            ],
        ]
    )


def open_app_keyboard(tab: Optional[str] = None, text: str = "Адкрыць праграму") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, web_app=WebAppInfo(url=webapp_url(tab=tab)))]]
    )
