"""Entry point for the Telegram bot."""
from __future__ import annotations

from telegram.ext import Application, ApplicationBuilder

from config import BOT_COMMANDS, TOKEN
from handlers import downloader, start
from utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


async def on_post_init(application: Application) -> None:
    """Configure bot commands once the application is ready."""
    await application.bot.set_my_commands(BOT_COMMANDS)


def main() -> None:
    setup_logging()
    application = ApplicationBuilder().token(TOKEN).post_init(on_post_init).build()
    start.register(application)
    downloader.register(application)

    logger.info("Starting bot polling.")
    try:
        application.run_polling()
    except Exception as exc:
        logger.critical("Bot polling failed: %s", exc, exc_info=True)


if __name__ == '__main__':
    main()
