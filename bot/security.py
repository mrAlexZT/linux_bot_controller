from __future__ import annotations

import logging
from collections.abc import Awaitable
from typing import Any, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from .config import Settings


class AdminOnlyMiddleware(BaseMiddleware):
    """Blocks all interactions from non-admin users.

    Allows /start and /help to return a friendly message even for non-admins.
    """

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Inject settings for handler DI
        data["settings"] = self.settings

        user_id: int | None = None
        text: str | None = None

        if isinstance(event, Message):
            if event.from_user:
                user_id = event.from_user.id
            text = event.text or event.caption or ""
        elif isinstance(event, CallbackQuery):
            if event.from_user:
                user_id = event.from_user.id
            text = event.data or ""

        # Allow start/help for everyone to avoid confusion.
        if isinstance(event, Message) and text:
            low = text.lower()
            if low.startswith("/start") or low.startswith("/help"):
                return await handler(event, data)

        if user_id is None or user_id not in self.settings.admin_ids:
            # Log access denial for diagnostics
            logging.warning("Access denied for user_id=%s text=%r", user_id, (text or "")[:100])
            if isinstance(event, Message):
                await event.answer("Access denied. This bot is restricted to administrators.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Access denied.", show_alert=True)
            return None

        return await handler(event, data)
