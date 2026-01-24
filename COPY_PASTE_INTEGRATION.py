"""
COPY-PASTE READY: Minimal integration for your handlers/downloader.py

Replace or adapt your existing message handler with this code pattern.
This is the simplest way to add caching to your bot.
"""

# ============================================================================
# ADD THESE IMPORTS TO THE TOP OF handlers/downloader.py
# ============================================================================

# from utils.cache_manager import init_cache_db, check_cached_file
# from utils.caching_downloader import CachingDownloader
# from utils.cache_utils import send_cached_or_download_audio, DEFAULT_TEXTS_RU, DEFAULT_TEXTS_EN
# from config import ffmpeg_path, cookies_path


# ============================================================================
# ADD THIS AT MODULE LEVEL (after imports, before any function)
# ============================================================================

# Global downloader instance
_caching_downloader: Optional[CachingDownloader] = None


# ============================================================================
# NEW HANDLER - Replace your existing message handler with this
# ============================================================================

async def handle_music_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user text messages for music download with caching."""
    
    if not update.message or not update.message.text:
        return
    
    global _caching_downloader
    
    # Initialize downloader on first use
    if not _caching_downloader:
        _caching_downloader = CachingDownloader(
            ffmpeg_path=ffmpeg_path,
            cookies_path=cookies_path
        )
    
    user_id = update.message.from_user.id
    query = update.message.text.strip()
    
    # Get user language (use your existing function or fallback to 'en')
    try:
        user_lang = get_user_lang(user_id)  # Your existing function
        texts = TEXTS.get(user_lang, DEFAULT_TEXTS_EN)  # Your existing TEXTS dict or default
    except:
        texts = DEFAULT_TEXTS_RU  # Fallback
    
    # One-liner solution: download with caching, check size, and send
    await send_cached_or_download_audio(
        query=query,
        update=update,
        context=context,
        downloader=_caching_downloader,
        texts=texts
    )


# ============================================================================
# MODIFY bot.py main() function - ADD THESE 2 LINES
# ============================================================================

# def main() -> None:
#     setup_logging()
#     
#     # >>> ADD THESE TWO LINES <<<
#     from utils.cache_manager import init_cache_db
#     init_cache_db()
#     
#     application = ApplicationBuilder().token(TOKEN).post_init(on_post_init).build()
#     start.register(application)
#     downloader.register(application)
#
#     logger.info("Starting bot polling.")
#     try:
#         application.run_polling()
#     except Exception as exc:
#         logger.critical("Bot polling failed: %s", exc, exc_info=True)


# ============================================================================
# UPDATE YOUR register() FUNCTION - REPLACE MESSAGE HANDLER
# ============================================================================

# def register(application: Application) -> None:
#     """Register downloader handlers."""
#     
#     # Replace old handler with:
#     application.add_handler(
#         MessageHandler(filters.TEXT & ~filters.COMMAND, handle_music_download)
#     )
#     
#     # ... rest of your handlers


# ============================================================================
# IF YOU NEED CUSTOM TEXT MESSAGES, MODIFY send_cached_or_download_audio
# ============================================================================

# Example: Call with custom texts
# await send_cached_or_download_audio(
#     query=query,
#     update=update,
#     context=context,
#     downloader=_caching_downloader,
#     texts={
#         "downloading_audio": "⏳ Загружаю с YouTube...",
#         "error": "❌ Ошибка",
#         "file_too_large": "⚠️ Файл >50МБ",
#         "video_not_available": "❌ Видео недоступно",
#         "geo_blocked": "❌ Видео недоступно в регионе",
#         "video_private": "❌ Видео приватное",
#         "cached": "⚡ Уже есть на сервере!",
#     }
# )


# ============================================================================
# FULL MINIMAL EXAMPLE (self-contained)
# ============================================================================

"""
from typing import Optional
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from config import TOKEN, ffmpeg_path, cookies_path
from utils.cache_manager import init_cache_db
from utils.caching_downloader import CachingDownloader
from utils.cache_utils import send_cached_or_download_audio, DEFAULT_TEXTS_RU

_downloader: Optional[CachingDownloader] = None

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _downloader
    if not _downloader:
        _downloader = CachingDownloader(ffmpeg_path, cookies_path)
    
    await send_cached_or_download_audio(
        query=update.message.text,
        update=update,
        context=context,
        downloader=_downloader,
        texts=DEFAULT_TEXTS_RU
    )

def main() -> None:
    init_cache_db()  # Initialize cache
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    app.run_polling()

if __name__ == '__main__':
    main()
"""

# ============================================================================
# THAT'S IT! Just 3 things:
# 1. init_cache_db() in bot.py main()
# 2. Global _caching_downloader in handlers
# 3. Use send_cached_or_download_audio() in message handler
# ============================================================================
