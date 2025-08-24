from __future__ import annotations

import asyncio
import logging
import os
import platform
import socket
import sys
from contextlib import suppress
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from bot.config import Settings, load_settings
from bot.handlers import router as core_router
from bot.security import AdminOnlyMiddleware


async def _notify_admins(bot: Bot, settings: Settings, text: str) -> None:
    """Best-effort broadcast to all admin IDs; ignore per-recipient failures."""
    tasks = [bot.send_message(uid, text) for uid in settings.admin_ids]
    if not tasks:
        return
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for uid, res in zip(settings.admin_ids, results):
        if isinstance(res, Exception):
            logging.error("Failed to notify admin_id=%s: %s", uid, repr(res))


def _startup_text(settings: Settings) -> str:
    now = datetime.now(timezone.utc).astimezone()
    host = socket.gethostname()
    pid = os.getpid()
    py = sys.version.split()[0]
    sysname = platform.system()
    return (
        "✅ Bot started\n"
        f"time: {now.isoformat()}\n"
        f"host: {host} (PID {pid})\n"
        f"python: {py} on {sysname}\n"
        f"BASE_DIR: <code>{settings.base_dir}</code>\n"
        f"LOG_LEVEL: {settings.log_level}"
    )


def _shutdown_text() -> str:
    now = datetime.now(timezone.utc).astimezone()
    return f"🛑 Bot stopped\ntime: {now.isoformat()}"


async def main() -> None:
    # Load .env if present
    load_dotenv()

    settings = load_settings()

    # Configure logging: console always; optional rotating file
    log_format = "%(asctime)s %(levelname)s %(name)s %(message)s"
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, format=log_format)
    if settings.log_file:
        try:
            settings.log_file.parent.mkdir(parents=True, exist_ok=True)
            fh = RotatingFileHandler(
                settings.log_file,
                maxBytes=settings.log_max_bytes,
                backupCount=settings.log_backups,
                encoding="utf-8",
            )
            fh.setLevel(level)
            fh.setFormatter(logging.Formatter(log_format))
            root = logging.getLogger()
            root.addHandler(fh)
        except Exception:
            logging.exception("Failed to set up file logging")

    bot = Bot(token=settings.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Admin-only middleware and DI for settings
    dp.update.middleware(AdminOnlyMiddleware(settings))

    # Lifecycle notifications
    async def _on_startup(bot: Bot) -> None:
        await _notify_admins(bot, settings, _startup_text(settings))

    async def _on_shutdown(bot: Bot) -> None:
        await _notify_admins(bot, settings, _shutdown_text())

    dp.startup.register(_on_startup)
    dp.shutdown.register(_on_shutdown)

    # Routers
    dp.include_router(core_router)

    logging.info("Starting bot. Base dir: %s", settings.base_dir)
    with suppress(KeyboardInterrupt):
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (SystemExit, KeyboardInterrupt):
        pass
