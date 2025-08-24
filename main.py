from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from bot.config import load_settings
from bot.handlers import router as core_router
from bot.security import AdminOnlyMiddleware


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
