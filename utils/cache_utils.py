"""Ready-to-use utility functions for quick integration."""
from __future__ import annotations

import os
from typing import Optional, Tuple
from telegram import Update, InputFile
from telegram.ext import ContextTypes

from utils.cache_manager import check_cached_file, MUSIC_DIR
from utils.caching_downloader import CachingDownloader, TELEGRAM_FILE_SIZE_LIMIT_BYTES


async def send_cached_or_download_audio(
    query: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    downloader: CachingDownloader,
    texts: dict,
    ffmpeg_path: str = "/usr/bin/ffmpeg",
    cookies_path: Optional[str] = None,
) -> bool:
    """
    All-in-one function: check cache → download → check size → send audio.
    
    Args:
        query: YouTube URL or search query
        update: Telegram Update
        context: Telegram context
        downloader: CachingDownloader instance
        texts: Dict with localized messages
        ffmpeg_path: Path to ffmpeg
        cookies_path: Path to cookies file
    
    Returns:
        True if audio was sent, False otherwise
    
    Usage:
        success = await send_cached_or_download_audio(
            query=update.message.text,
            update=update,
            context=context,
            downloader=my_downloader,
            texts=user_texts_dict
        )
    """
    chat_id = update.message.chat_id
    
    if not downloader:
        await context.bot.send_message(
            chat_id=chat_id,
            text=texts.get("error", "Error") + " (Downloader not initialized)"
        )
        return False
    
    try:
        # Progress callback
        progress_msg = None
        
        async def on_progress(percent: str, speed: str, eta: str) -> None:
            nonlocal progress_msg
            if not progress_msg:
                progress_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"📥 {texts.get('downloading_audio', 'Downloading...')}"
                )
            try:
                text = f"📥 {percent} | {speed} | ⏱️ {eta}"
                await progress_msg.edit_text(text)
            except Exception:
                pass
        
        # Download and cache
        file_path, youtube_id, result = await downloader.download_and_cache(
            url=query,
            update=update,
            context=context,
            texts=texts,
            progress_callback=on_progress
        )
        
        # Clean up progress message
        if progress_msg:
            try:
                await progress_msg.delete()
            except Exception:
                pass
        
        # Handle results
        if file_path and os.path.exists(file_path):
            # File ready - send it
            try:
                with open(file_path, 'rb') as audio_file:
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=InputFile(audio_file),
                        title=result if isinstance(result, str) else "Music",
                        read_timeout=30,
                        write_timeout=30,
                    )
                return True
            except Exception as exc:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ {texts.get('error', 'Error')}: Failed to send file"
                )
                return False
        
        elif result == "FILE_TOO_LARGE" and youtube_id:
            # File too large for Telegram
            youtube_url = f"https://youtu.be/{youtube_id}"
            msg = (
                "⚠️ " + texts.get("file_too_large", "File too large (>50 MB)") +
                f"\n\n🔗 Download yourself: {youtube_url}"
            )
            await context.bot.send_message(chat_id=chat_id, text=msg)
            return False
        
        elif result == "VIDEO_NOT_AVAILABLE":
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ " + texts.get("video_not_available", "Video not available or removed")
            )
            return False
        
        elif result == "GEO_BLOCKED":
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ " + texts.get("geo_blocked", "Video not available in your region")
            )
            return False
        
        elif result == "VIDEO_PRIVATE":
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ " + texts.get("video_private", "Video is private")
            )
            return False
        
        else:
            # Other error
            error_msg = str(result)[:200] if result else "Unknown error"
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ {texts.get('error', 'Error')}: {error_msg}"
            )
            return False
    
    except Exception as exc:
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Unexpected error. Try again later."
        )
        return False


async def try_send_from_cache(
    youtube_id: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    texts: dict,
) -> bool:
    """
    Try to send audio from cache by youtube_id.
    
    Returns:
        True if file was found and sent, False otherwise
    
    Usage:
        if not await try_send_from_cache(yt_id, update, context, texts):
            # File not in cache, proceed with download
    """
    chat_id = update.message.chat_id
    cached_path = check_cached_file(youtube_id)
    
    if not cached_path:
        return False
    
    try:
        # Optional: send message that file is from cache
        cache_msg = await context.bot.send_message(
            chat_id=chat_id,
            text="⚡ " + texts.get("cached", "File found in cache - sending instantly!")
        )
        
        # Send audio
        with open(cached_path, 'rb') as audio_file:
            await context.bot.send_audio(
                chat_id=chat_id,
                audio=InputFile(audio_file),
                read_timeout=30,
                write_timeout=30,
            )
        
        # Clean up cache message
        try:
            await cache_msg.delete()
        except Exception:
            pass
        
        return True
    except Exception as exc:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ {texts.get('error', 'Error')}: Could not send cached file"
        )
        return False


def get_cache_info() -> dict:
    """Get cache directory information."""
    if not os.path.exists(MUSIC_DIR):
        return {
            "cache_dir": MUSIC_DIR,
            "exists": False,
            "files_count": 0,
            "total_size_mb": 0.0
        }
    
    files_count = 0
    total_size = 0
    
    try:
        for filename in os.listdir(MUSIC_DIR):
            filepath = os.path.join(MUSIC_DIR, filename)
            if os.path.isfile(filepath):
                files_count += 1
                total_size += os.path.getsize(filepath)
    except Exception:
        pass
    
    return {
        "cache_dir": MUSIC_DIR,
        "exists": True,
        "files_count": files_count,
        "total_size_mb": round(total_size / (1024 * 1024), 2)
    }


# Example texts dictionary for Russian
DEFAULT_TEXTS_RU = {
    "downloading_audio": "Загружаю музыку с YouTube...",
    "download_progress": "📥 Загрузка: {percent} | {speed} | ⏱️ {eta}",
    "error": "Ошибка",
    "file_too_large": "Файл слишком большой (>50 МБ)",
    "video_not_available": "Видео недоступно или было удалено",
    "geo_blocked": "Видео недоступно в вашем регионе",
    "video_private": "Видео приватное",
    "cached": "Эта песня уже есть на сервере — вот она мгновенно 🎧",
}

# Example texts dictionary for English
DEFAULT_TEXTS_EN = {
    "downloading_audio": "Downloading music from YouTube...",
    "download_progress": "📥 Downloading: {percent} | {speed} | ⏱️ {eta}",
    "error": "Error",
    "file_too_large": "File too large (>50 MB)",
    "video_not_available": "Video not available or removed",
    "geo_blocked": "Video not available in your region",
    "video_private": "Video is private",
    "cached": "This song is already on the server — here it is instantly 🎧",
}
