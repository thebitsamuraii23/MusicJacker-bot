"""
INTEGRATION EXAMPLE - Add this to your handlers/downloader.py or modify existing handlers

This shows how to integrate the caching system with your message handler.
"""

# ============================================================================
# ADD THESE IMPORTS to your existing handlers/downloader.py
# ============================================================================

from utils.cache_manager import init_cache_db, check_cached_file
from utils.caching_downloader import CachingDownloader, TELEGRAM_FILE_SIZE_LIMIT_BYTES
from telegram import InputFile
import os

# ============================================================================
# INITIALIZE IN main() function in bot.py BEFORE application.run_polling()
# ============================================================================

# In bot.py main() function, add this line:
# cache_db_path = init_cache_db()  # Initialize cache database on startup
# logger.info(f"Cache database ready at: {cache_db_path}")


# ============================================================================
# CREATE A GLOBAL DOWNLOADER INSTANCE (in handlers/downloader.py)
# ============================================================================

# At module level in handlers/downloader.py:
_caching_downloader: Optional[CachingDownloader] = None

async def init_downloader(ffmpeg_path: str, cookies_path: Optional[str] = None) -> None:
    """Initialize the caching downloader. Call once during bot startup."""
    global _caching_downloader
    _caching_downloader = CachingDownloader(ffmpeg_path=ffmpeg_path, cookies_path=cookies_path)


# ============================================================================
# MODIFY YOUR MESSAGE HANDLER - EXAMPLE IMPLEMENTATION
# ============================================================================

async def handle_music_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Example handler that uses caching downloader.
    Replace your existing message handler with this pattern.
    """
    if not update.message or not update.message.text:
        return
    
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    query = update.message.text.strip()
    
    # Get user language for localized messages
    user_lang = get_user_lang(user_id)  # Your existing function
    texts = TEXTS.get(user_lang, TEXTS['en'])  # Your existing texts dict
    
    # Initialize downloader if not already done
    global _caching_downloader
    if not _caching_downloader:
        await init_downloader(ffmpeg_path, cookies_path)
    
    try:
        # Callback for progress updates
        status_message = None
        
        async def on_progress(percent: str, speed: str, eta: str) -> None:
            """Update message with download progress."""
            nonlocal status_message
            if not status_message:
                status_message = await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"📥 {texts.get('downloading_audio', 'Downloading...')}"
                )
            try:
                progress_text = f"📥 {texts.get('download_progress', 'Downloading...')}\n{percent} | {speed} | ETA: {eta}"
                await status_message.edit_text(progress_text)
            except Exception:
                pass
        
        # Start download with caching
        file_path, youtube_id, result = await _caching_downloader.download_and_cache(
            url=query,
            update=update,
            context=context,
            texts=texts,
            progress_callback=on_progress
        )
        
        # Delete progress message
        if status_message:
            try:
                await status_message.delete()
            except Exception:
                pass
        
        # Handle results
        if file_path and file_path != "FILE_TOO_LARGE":
            # File successfully downloaded and cached
            if youtube_id and not check_cached_file(youtube_id):
                # File was from cache (already checked, so not in the if)
                cache_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text="⚡ Эта песня уже есть на сервере — вот она мгновенно 🎧"
                )
            
            # Send the audio file
            try:
                with open(file_path, 'rb') as audio_file:
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=InputFile(audio_file),
                        title=result if isinstance(result, str) else "Music",
                        read_timeout=30,
                        write_timeout=30,
                    )
                logger.info(f"Sent audio to user {user_id}")
            except Exception as exc:
                logger.error(f"Failed to send audio: {exc}")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ {texts.get('error', 'Error')}: Не удалось отправить файл"
                )
        
        elif result == "FILE_TOO_LARGE":
            # File exists but too large for Telegram
            youtube_url = f"https://youtu.be/{youtube_id}" if youtube_id else query
            msg = (
                "⚠️ Файл слишком большой (>50 МБ). "
                "Telegram не позволяет боту отправлять такие большие аудиофайлы.\n\n"
                f"🔗 Скачай сам: {youtube_url}"
            )
            await context.bot.send_message(chat_id=chat_id, text=msg)
            logger.warning(f"File too large for {youtube_id}")
        
        elif result == "VIDEO_NOT_AVAILABLE":
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Видео недоступно или было удалено."
            )
        elif result == "GEO_BLOCKED":
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Видео недоступно в вашем регионе (географический блок)."
            )
        elif result == "VIDEO_PRIVATE":
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Видео приватное и недоступно для скачивания."
            )
        else:
            # Other error
            error_text = result if isinstance(result, str) else str(result)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ {texts.get('error', 'Error')}: {error_text[:200]}"
            )
    
    except Exception as exc:
        logger.error(f"Unhandled error in handle_music_message: {exc}", exc_info=True)
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Неожиданная ошибка. Попробуй позже."
        )


# ============================================================================
# REGISTER THE HANDLER IN register() FUNCTION
# ============================================================================

# In your register() function, add or replace:
def register(application: Application) -> None:
    """Register message handlers."""
    # Initialize downloader on startup
    async def setup(app):
        await init_downloader(
            ffmpeg_path=ffmpeg_path,  # from config
            cookies_path=cookies_path  # from config
        )
    
    application.post_init = setup
    
    # Add message handler
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_music_message)
    )


# ============================================================================
# MODIFICATIONS TO bot.py main() function
# ============================================================================

# def main() -> None:
#     setup_logging()
#     
#     # Initialize cache database
#     cache_db_path = init_cache_db()
#     logger.info(f"Cache database initialized at {cache_db_path}")
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
# OPTIONAL: Add cleanup task to remove old cache entries (e.g., weekly)
# ============================================================================

# Add to handlers/downloader.py or create handlers/maintenance.py:

from utils.cache_manager import cleanup_cache

async def periodic_cache_cleanup(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove cache entries older than 30 days (runs weekly)."""
    removed = cleanup_cache(max_age_days=30)
    logger.info(f"Cache cleanup completed: removed {removed} old entries")


# In register() function:
# job_queue = application.job_queue
# job_queue.run_repeating(
#     periodic_cache_cleanup,
#     interval=7 * 24 * 3600,  # Weekly
#     first=10
# )
