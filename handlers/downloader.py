"""Handlers responsible for downloading music and yt-dlp integration."""
from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import time
import uuid
from typing import Dict, List, Sequence
from urllib.parse import quote_plus

import yt_dlp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from config import (
    FFMPEG_IS_AVAILABLE,
    LANG_CODES,
    LANGUAGES,
    MAX_CONCURRENT_DOWNLOADS_PER_USER,
    REQUIRED_CHANNELS,
    SEARCH_RESULTS_LIMIT,
    TELEGRAM_FILE_SIZE_LIMIT_BYTES,
    TELEGRAM_FILE_SIZE_LIMIT_TEXT,
    cookies_path,
    ffmpeg_path,
)
from handlers.start import get_user_lang
from utils.logger import get_logger
from utils.yt_downloader import DownloadResult, download_audio

logger = get_logger(__name__)

# Кэш для результатов поиска (query -> {data, timestamp})
_search_cache: Dict[str, Dict] = {}
_search_cache_ttl = 600  # 10 минут
_search_cache_lock = asyncio.Lock()


async def check_subscription(user_id: int, bot) -> bool:
    """Ensure user is subscribed to all required channels."""
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
        except Exception as exc:
            logger.error("Error checking subscription for user %s in %s: %s", user_id, channel, exc)
            return False
        if member.status not in {"member", "administrator", "creator"}:
            logger.info("User %s is not subscribed to %s", user_id, channel)
            return False
    return True


def is_url(text: str) -> bool:
    """Check if text looks like a supported URL."""
    normalized = text.lower().strip()
    if not normalized.startswith(('http://', 'https://')):
        return False
    return any(pattern in normalized for pattern in ("youtube.com/", "youtu.be/", "soundcloud.com/", "music.youtube.com/"))


def format_duration(duration_seconds) -> str:
    """Format seconds to H:MM:SS or M:SS."""
    try:
        if duration_seconds is None:
            return ""
        if isinstance(duration_seconds, str):
            if duration_seconds.isdigit():
                duration_seconds = int(duration_seconds)
            else:
                parts = [int(p) for p in duration_seconds.split(':') if p.isdigit()]
                if not parts:
                    return ""
                if len(parts) == 3:
                    h, m, s = parts
                    duration_seconds = h * 3600 + m * 60 + s
                elif len(parts) == 2:
                    m, s = parts
                    duration_seconds = m * 60 + s
                else:
                    duration_seconds = parts[0]
        total = int(duration_seconds)
        hours = total // 3600
        minutes = (total % 3600) // 60
        seconds = total % 60
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"
    except Exception:
        return ""


async def _get_cached_search(query: str) -> List | str | None:
    """Получить результаты поиска из кэша или вернуть None если истекло время."""
    try:
        async with _search_cache_lock:
            cached = _search_cache.get(query)
            if cached and (time.time() - cached['timestamp']) < _search_cache_ttl:
                logger.debug("Using cached search results for %s", query)
                return cached['data']
    except Exception as exc:
        logger.debug("Search cache lookup error: %s", exc)
    return None


async def _cache_search(query: str, results: List | str) -> None:
    """Сохранить результаты поиска в кэш."""
    try:
        async with _search_cache_lock:
            _search_cache[query] = {'data': results, 'timestamp': time.time()}
    except Exception as exc:
        logger.debug("Search cache save error: %s", exc)


async def search_youtube(query: str):
    """Perform YouTube search or return 'unsupported_url'."""
    if is_url(query):
        return 'unsupported_url'

    # Проверяем кэш первым
    cached_results = await _get_cached_search(query)
    if cached_results is not None:
        return cached_results

    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'extract_flat': True,
        'nocheckcertificate': True,
        'default_search': None,
        'noplaylist': True,
    }

    try:
        safe_query = quote_plus(query)
        music_search = f"https://music.youtube.com/search?q={safe_query}"
        logger.info("Searching YouTube Music for query: %s", query)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(music_search, download=False)

        entries: Sequence[Dict] = []
        if isinstance(info, dict):
            if info.get('entries'):
                entries = info['entries']
            elif info.get('results'):
                entries = info['results']
        elif isinstance(info, list):
            entries = info

        def is_music_entry(entry: Dict) -> bool:
            try:
                if not isinstance(entry, dict):
                    return False
                if entry.get('track') or entry.get('artists'):
                    return True
                ie = str(entry.get('ie_key') or entry.get('extractor') or '').lower()
                if 'music' in ie:
                    return True
                url = entry.get('url') or entry.get('webpage_url') or ''
                if 'music.youtube.com' in url:
                    return True
                duration = entry.get('duration')
                if isinstance(duration, (int, float)) and 0 < duration < 600 and not entry.get('is_live'):
                    return True
            except Exception:
                return False
            return False

        music_entries = [item for item in entries if is_music_entry(item)] if entries else []
        if not music_entries:
            logger.info("No music-specific entries found, falling back to ytsearch for query: %s", query)
            yt_search_query = f"ytsearch{SEARCH_RESULTS_LIMIT}:{query}"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(yt_search_query, download=False)
            entries = info.get('entries', []) or []
            music_entries = [item for item in entries if is_music_entry(item)] or entries

        if not music_entries:
            logger.info("No results found for query: %s", query)
            await _cache_search(query, [])
            return []

        results = list(music_entries)[:SEARCH_RESULTS_LIMIT]
        # Сохраняем результаты в кэш
        await _cache_search(query, results)
        return results
    except yt_dlp.utils.DownloadError as exc:
        if 'Unsupported URL' in str(exc) or 'unsupported url' in str(exc).lower():
            logger.warning("Unsupported URL in search query: %s", query)
            return 'unsupported_url'
        logger.error("DownloadError during YouTube search for %s: %s", query, exc)
        return []
    except Exception as exc:
        logger.critical("Unhandled error during YouTube search for %s", query, exc_info=True)
        return []


async def handle_download(update_or_query, context: ContextTypes.DEFAULT_TYPE, url: str, texts: Dict[str, str], user_id: int) -> None:
    if not update_or_query.message:
        try:
            await context.bot.send_message(chat_id=user_id, text=texts['error'] + ' (internal error: chat not found)')
        except Exception:
            pass
        return

    chat_id = update_or_query.message.chat_id
    temp_dir = None
    status_message = None
    active_downloads = context.bot_data.setdefault('active_downloads', {})
    loop = asyncio.get_running_loop()

    task_id = None
    user_tasks = active_downloads.get(user_id, {})
    for tid, info in user_tasks.items():
        if info.get('task') and info['task'] == asyncio.current_task():
            task_id = tid
            break
    if not task_id:
        task_id = uuid.uuid4().hex
        user_tasks = active_downloads.setdefault(user_id, {})
        user_tasks[task_id] = {'task': asyncio.current_task()}

    cancel_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(texts['cancel_button'], callback_data=f"cancel_{user_id}_{task_id}")]])

    async def update_status_message_async(text_to_update: str, show_cancel_button: bool = True) -> None:
        nonlocal status_message
        if status_message:
            try:
                keyboard = cancel_keyboard if show_cancel_button else None
                await status_message.edit_text(text_to_update, reply_markup=keyboard)
            except Exception as exc:
                logger.debug("Could not edit status message: %s", exc)

    def progress_hook(data: Dict) -> None:
        if data.get('status') == 'downloading':
            percent = data.get('_percent_str', 'N/A').strip()
            speed = data.get('_speed_str', 'N/A').strip()
            eta = data.get('_eta_str', 'N/A').strip()
            progress_text = texts['download_progress'].format(percent=percent, speed=speed, eta=eta)
            asyncio.run_coroutine_threadsafe(update_status_message_async(progress_text), loop)

    try:
        status_message = await context.bot.send_message(chat_id=chat_id, text=texts['downloading_audio'], reply_markup=cancel_keyboard)
        active_downloads.setdefault(user_id, {})[task_id]['status_message_id'] = status_message.message_id
        await asyncio.sleep(10)
        temp_dir = tempfile.mkdtemp()
        active_downloads.setdefault(user_id, {})[task_id]['temp_dir'] = temp_dir

        ffmpeg = ffmpeg_path if FFMPEG_IS_AVAILABLE else None
        download_result: DownloadResult = await download_audio(url, temp_dir, cookies_path, ffmpeg, progress_hook)

        total_files = len(download_result.files)
        
        # Отправляем файлы с ограничением на одновременные загрузки (2 максимум)
        semaphore = asyncio.Semaphore(2)
        
        async def send_file_async(index: int, file_path: str, title: str) -> None:
            async with semaphore:
                await update_status_message_async(texts['sending_file'].format(index=index, total=total_files))
                file_size = os.path.getsize(file_path)
                if file_size > TELEGRAM_FILE_SIZE_LIMIT_BYTES:
                    await context.bot.send_message(chat_id=chat_id, text=f"{texts['too_big']} ({os.path.basename(file_path)})")
                    return

                try:
                    with open(file_path, 'rb') as fp:
                        await context.bot.send_audio(
                            chat_id=chat_id,
                            audio=fp,
                            title=title,
                            performer=download_result.artist,
                            filename=os.path.basename(file_path),
                        )
                    await context.bot.send_message(chat_id=chat_id, text=texts.get('copyright_post'))
                    logger.info("Successfully sent audio for %s to user %s", url, user_id)
                except Exception as exc:
                    logger.error("Error sending audio file %s to user %s: %s", os.path.basename(file_path), user_id, exc)
                    await context.bot.send_message(chat_id=chat_id, text=f"{texts['error']} (Error sending file {os.path.basename(file_path)})")
        
        # Выполняем все отправки параллельно с ограничениями
        await asyncio.gather(*[
            send_file_async(index, file_path, title)
            for index, (file_path, title) in enumerate(download_result.files, start=1)
        ], return_exceptions=False)

        await update_status_message_async(texts['done_audio'], show_cancel_button=False)

    except FileNotFoundError:
        await update_status_message_async(texts['error'] + ' (audio file not found)', show_cancel_button=False)
    except asyncio.CancelledError:
        logger.info("Download cancelled for user %s.", user_id)
        if status_message:
            await update_status_message_async(texts['cancelled'], show_cancel_button=False)
        else:
            await context.bot.send_message(chat_id=chat_id, text=texts['cancelled'])
    except Exception as exc:
        if 'Unsupported URL' in str(exc) or 'unsupported url' in str(exc).lower():
            lang = get_user_lang(user_id)
            lang_texts = LANGUAGES.get(lang, LANGUAGES['ru'])
            unsupported = lang_texts.get('unsupported_url_in_search', 'The link is not supported. Please check the link or try another query.')
            if status_message:
                await update_status_message_async(unsupported, show_cancel_button=False)
            else:
                await context.bot.send_message(chat_id=chat_id, text=unsupported)
            return
        logger.critical("Unhandled error in handle_download for user %s: %s", user_id, exc, exc_info=True)
        if status_message:
            await update_status_message_async(texts['error'] + str(exc), show_cancel_button=False)
        else:
            await context.bot.send_message(chat_id=chat_id, text=texts['error'] + str(exc))
    finally:
        try:
            task_info = context.bot_data.get('active_downloads', {}).get(user_id, {}).get(task_id, {})
            temp_path = task_info.get('temp_dir') or temp_dir
            if temp_path and os.path.exists(temp_path):
                shutil.rmtree(temp_path, ignore_errors=True)
                logger.info("Cleaned up temporary directory %s for user %s (task %s).", temp_path, user_id, task_id)
        except Exception as exc:
            logger.debug("Error cleaning temp dir for user %s task %s: %s", user_id, task_id, exc)

        try:
            if user_id in context.bot_data.get('active_downloads', {}):
                tasks = context.bot_data['active_downloads'][user_id]
                if task_id in tasks:
                    del tasks[task_id]
                if not tasks:
                    del context.bot_data['active_downloads'][user_id]
                    logger.info("No more active downloads for user %s.", user_id)
                logger.info("Removed active download task %s for user %s.", task_id, user_id)
        except Exception as exc:
            logger.debug("Error removing active download entry for user %s task %s: %s", user_id, task_id, exc)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    logger.info("User %s issued /search command.", user_id)
    await update.message.reply_text(texts['search_prompt'])
    context.user_data[f'awaiting_search_query_{user_id}'] = True


async def handle_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    query_text = update.message.text.strip()
    logger.info("User %s sent search query: %s", user_id, query_text)

    results = await search_youtube(query_text)
    if results == 'unsupported_url':
        await update.message.reply_text(texts['unsupported_url_in_search'])
        return

    if not results:
        await update.message.reply_text(texts['no_results'])
        return

    keyboard: List[List[InlineKeyboardButton]] = []
    for idx, entry in enumerate(results):
        title = entry.get('title', texts['no_results'])
        artist = entry.get('artist') or entry.get('uploader') or entry.get('channel') or ''
        duration = format_duration(entry.get('duration'))
        parts = [f"{idx + 1}. {title}"]
        if artist:
            parts.append(str(artist))
        if duration:
            parts.append(f"[{duration}]")
        button_label = ' — '.join(parts)
        keyboard.append([InlineKeyboardButton(button_label, callback_data=f"searchsel_{user_id}_{idx}")])

    await update.message.reply_text(
        texts['choose_track'],
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    context.user_data[f'search_results_{user_id}'] = list(results)


async def search_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    try:
        _, raw_user_id, raw_index = query.data.split('_', 2)
        sel_user_id = int(raw_user_id)
        sel_index = int(raw_index)
    except Exception:
        await query.edit_message_text('Invalid selection. Please try again.')
        return

    if user_id != sel_user_id:
        logger.warning("User %s tried to use another user's search callback: %s", user_id, sel_user_id)
        lang = get_user_lang(user_id)
        texts = LANGUAGES.get(lang, LANGUAGES['ru'])
        await query.edit_message_text(texts.get('already_cancelled_or_done', 'This button is not for you.'))
        return

    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]

    stored = context.user_data.get(f'search_results_{sel_user_id}')
    if not stored or not isinstance(stored, (list, tuple)):
        await query.edit_message_text(texts.get('no_results', 'Search results expired or invalid. Please /search again.'))
        return
    if sel_index < 0 or sel_index >= len(stored):
        await query.edit_message_text(texts.get('no_results', 'Invalid selection index. Please /search again.'))
        return

    entry = stored[sel_index]
    video_id = entry.get('id') or entry.get('url') or ''
    if entry.get('webpage_url') and 'music.youtube.com' in str(entry.get('webpage_url')):
        url = entry.get('webpage_url')
    elif entry.get('url') and 'music.youtube.com' in str(entry.get('url')):
        url = entry.get('url')
    elif video_id:
        url = video_id if video_id.startswith('http') else f"https://youtu.be/{video_id}"
    else:
        url = ''

    await query.edit_message_text(texts['downloading_selected_track'], reply_markup=None)

    active_downloads = context.bot_data.setdefault('active_downloads', {})
    user_tasks = active_downloads.setdefault(user_id, {})
    if len(user_tasks) >= MAX_CONCURRENT_DOWNLOADS_PER_USER:
        await query.edit_message_text(texts.get('download_in_progress') + f" (max {MAX_CONCURRENT_DOWNLOADS_PER_USER})")
        return

    task_id = uuid.uuid4().hex
    task = asyncio.create_task(handle_download(query, context, url, texts, user_id))
    user_tasks[task_id] = {'task': task}


async def smart_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    text = update.message.text.strip()
    logger.info("User %s sent message: %s", user_id, text)

    active_downloads = context.bot_data.setdefault('active_downloads', {})
    user_tasks = active_downloads.get(user_id, {})
    running = any(info.get('task') and not info['task'].done() for info in user_tasks.values())
    if running:
        await update.message.reply_text(texts['download_in_progress'])

    is_subscribed = await check_subscription(user_id, context.bot)
    if not is_subscribed:
        await update.message.reply_text(texts['not_subscribed'])
        return

    if is_url(text):
        await update.message.reply_text(texts['checking'])
        user_tasks = active_downloads.setdefault(user_id, {})
        if len(user_tasks) >= MAX_CONCURRENT_DOWNLOADS_PER_USER:
            await update.message.reply_text(texts.get('download_in_progress') + f" (max {MAX_CONCURRENT_DOWNLOADS_PER_USER})")
            return
        task_id = uuid.uuid4().hex
        task = asyncio.create_task(handle_download(update, context, text, texts, user_id))
        user_tasks[task_id] = {'task': task}
        return

    if context.user_data.get(f'awaiting_search_query_{user_id}'):
        await handle_search_query(update, context)
        return

    logger.info("User %s auto-search for: %s", user_id, text)
    await update.message.reply_text(texts['searching'])
    results = await search_youtube(text)
    if results == 'unsupported_url' or not results:
        await update.message.reply_text(texts['no_results'])
        return

    keyboard: List[List[InlineKeyboardButton]] = []
    for idx, entry in enumerate(results):
        title = entry.get('title', texts['no_results'])
        artist = entry.get('artist') or entry.get('uploader') or entry.get('channel') or ''
        duration = format_duration(entry.get('duration'))
        parts = [f"{idx + 1}. {title}"]
        if artist:
            parts.append(str(artist))
        if duration:
            parts.append(f"[{duration}]")
        button_label = ' — '.join(parts)
        keyboard.append([InlineKeyboardButton(button_label, callback_data=f"searchsel_{user_id}_{idx}")])

    await update.message.reply_text(
        texts['choose_track'],
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    context.user_data[f'search_results_{user_id}'] = list(results)


async def cancel_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    logger.info("User %s requested download cancellation.", user_id)

    active_downloads = context.bot_data.setdefault('active_downloads', {})
    try:
        _, uid_str, task_id = query.data.split('_', 2)
        uid = int(uid_str)
    except Exception as exc:
        logger.error("Invalid cancel callback data: %s - %s", query.data, exc)
        try:
            await query.edit_message_text(texts['already_cancelled_or_done'])
        except Exception:
            pass
        return

    if uid != user_id:
        try:
            await query.edit_message_text(texts.get('already_cancelled_or_done', 'This button is not for you.'))
        except Exception:
            pass
        return

    user_tasks = active_downloads.get(user_id, {})
    task_info = user_tasks.get(task_id)
    if not task_info or not task_info.get('task') or task_info['task'].done():
        try:
            await query.edit_message_text(texts['already_cancelled_or_done'])
        except Exception as exc:
            logger.debug("Could not edit message for already cancelled download: %s", exc)
        return

    task_info['task'].cancel()
    try:
        await query.edit_message_text(texts['cancelling'])
    except Exception as exc:
        logger.debug("Could not edit message to 'cancelling': %s", exc)
    logger.info("Download task %s cancelled for user %s.", task_id, user_id)


async def copyright_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    logger.info("User %s issued /copyright command.", user_id)
    await update.message.reply_text(texts['copyright_command'])


def register(application: Application) -> None:
    application.add_handler(CommandHandler('search', search_command))
    application.add_handler(CommandHandler('copyright', copyright_command))
    application.add_handler(CallbackQueryHandler(search_select_callback, pattern='^searchsel_'))
    application.add_handler(CallbackQueryHandler(cancel_download_callback, pattern='^cancel_'))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^({'|'.join(LANG_CODES.keys())})$"),
        smart_message_handler,
    ))
