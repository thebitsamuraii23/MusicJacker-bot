# Standard library imports
import os
import logging
import asyncio
import tempfile
import shutil
import json
import time
import requests
from http import cookiejar

# Third party imports
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, InlineQueryHandler
from dotenv import load_dotenv
import yt_dlp
from mutagen.id3 import ID3
from mutagen.mp4 import MP4, MP4Cover
from PIL import Image

# Получение thumbnail через yt-dlp (YouTube)
def get_youtube_thumbnail(url):
    try:
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'nocheckcertificate': True,
            'cookiefile': cookies_path if os.path.exists(cookies_path) else None,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            thumb_url = info.get('thumbnail')
            if not thumb_url and 'thumbnails' in info and info['thumbnails']:
                thumb_url = info['thumbnails'][-1]['url']
            if thumb_url:
                # --- Передаем cookies в requests ---
                cookies = None
                if os.path.exists(cookies_path):
                    import http.cookiejar
                    cj = http.cookiejar.MozillaCookieJar()
                    try:
                        cj.load(cookies_path, ignore_discard=True, ignore_expires=True)
                        cookies = {c.name: c.value for c in cj}
                    except Exception as e:
                        logging.warning(f"Could not load cookies for requests: {e}")
                resp = requests.get(thumb_url, timeout=10, cookies=cookies)
                if resp.status_code == 200:
                    return resp.content
    except Exception as e:
        logging.warning(f"Could not fetch YouTube thumbnail: {e}")
    return None
import os # Import necessary libraries
import logging # Import logging for debugging and information
import asyncio # Import asyncio for asynchronous operations
import tempfile # Import tempfile for temporary file handling
import shutil # Import shutil for file operations
import json # Import json for handling JSON data
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, InlineQueryResultArticle, InputTextMessageContent # Import necessary Telegram bot components 
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, InlineQueryHandler # Import necessary Telegram bot handlers
from dotenv import load_dotenv # Import dotenv for environment variable management 
import yt_dlp # Import yt-dlp for downloading media


load_dotenv()

user_stats = {}  # user_id: {"downloads": int, "searches": int}


import time
from mutagen.id3 import ID3
from mutagen.mp4 import MP4, MP4Cover
from PIL import Image
import io

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("Cant found TELEGRAM_BOT_TOKEN in environment variables.")


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Starts the music search process.
    """
    import time
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    logger.info(f"User {user_id} issued /search command.") 

    # --- Таймаут между поисками ---
    global user_last_search_time
    now = time.time()
    search_cooldown = 5  # секунд
    last_search = user_last_search_time.get(user_id, 0)
    if now - last_search < search_cooldown:
        wait_sec = int(search_cooldown - (now - last_search))
        try:
            await update.message.reply_text(f"⏳ Пожалуйста, подождите {wait_sec} сек. перед следующим поиском.")
        except Exception:
            pass
        return
    user_last_search_time[user_id] = now

    await update.message.reply_text(texts["search_prompt"])
    context.user_data[f'awaiting_search_query_{user_id}'] = True

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id # major change: use effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    stats = user_stats.get(user_id, {"downloads": 0, "searches": 0})
    await update.message.reply_text(
        f"📊 Ваша статистика:\nСкачиваний: {stats['downloads']}\nПоисков: {stats['searches']}"
    )

def main():
    import logging
    load_dotenv() 
    try:
        app = Application.builder().token(TOKEN).build()
        logger.info("Bot application built successfully.")
    except Exception as e:
        logger.critical(f"Failed to build bot application: {e}", exc_info=True)
        raise

    # Add command handlers.
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", choose_language))
    app.add_handler(CommandHandler("languages", choose_language))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("copyright", copyright_command))
    app.add_handler(CommandHandler("stats", stats_command))

    app.add_handler(MessageHandler(filters.Regex(f"^({'|'.join(LANG_CODES.keys())})$"), set_language))
    app.add_handler(CallbackQueryHandler(select_download_type_callback, pattern="^dltype_"))
    app.add_handler(CallbackQueryHandler(search_select_callback, pattern="^searchsel_"))
    app.add_handler(CallbackQueryHandler(cancel_download_callback, pattern="^cancel_"))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^({'|'.join(LANG_CODES.keys())})$"),
        smart_message_handler
    ))

    async def set_commands(_):
        logger.info("Setting bot commands.")
        await app.bot.set_my_commands([
            BotCommand("start", "Запуск и выбор языка / Start and choose language"),
            BotCommand("languages", "Сменить язык / Change language"),
            BotCommand("search", "Поиск музыки (YouTube/SoundCloud) / Search music (YouTube/SoundCloud)"),
            BotCommand("copyright", "Информация об авторских правах / Copyright info"),
            BotCommand("stats", "Ваша статистика / Your stats")
        ])
    app.post_init = set_commands
    logger.info("Starting bot polling.")
    try:
        app.run_polling()
    except Exception as e:
        logger.critical(f"Bot polling failed: {e}", exc_info=True)


cookies_path = os.getenv('COOKIES_PATH', 'youtube.com_cookies.txt')
ffmpeg_path_from_env = os.getenv('FFMPEG_PATH')
ffmpeg_path = ffmpeg_path_from_env if ffmpeg_path_from_env else '/usr/bin/ffmpeg'
FFMPEG_IS_AVAILABLE = os.path.exists(ffmpeg_path) and os.access(ffmpeg_path, os.X_OK)
REQUIRED_CHANNELS = [
    "@ytdlpdeveloper",
    "@samuraicodingrus"
]
TELEGRAM_FILE_SIZE_LIMIT_BYTES = 50 * 1024 * 1024 # 50 MB in bytes
TELEGRAM_FILE_SIZE_LIMIT_TEXT = "50 МБ"
USER_LANGS_FILE = "user_languages.json"
if not os.path.exists(cookies_path):
    logging.warning(f"Cookies file {cookies_path} not found. Some features may not work properly.")

LANG_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["Русский", "English"],
        ["Español", "Azərbaycan dili"],
        ["Türkçe", "Українська"],
        ["العربية"]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)
LANG_CODES = {
    "Русский": "ru", "English": "en", "Españол": "es",
    "Azərbaycan dili": "az", "Türkçe": "tr", "Українська": "uk",
    "العربية": "ar"
}
SEARCH_RESULTS_LIMIT = 10
user_langs = {}
user_last_download_time = {}
user_last_search_time = {}

# --- LANGUAGES dictionary (all languages) ---
LANGUAGES = {
    "ru": {
        # ...русские строки...
    },
    "en": {
        "start": (
            "👋 Hello! I am a bot for downloading music from YouTube and SoundCloud.\n\n"
            "🔗 Just send a YouTube or SoundCloud link (video or track) and I will help you download the audio.\n"
            "\n🎵 I can also search for music by name! Just type /search.\n\n"
            f"📢 To use the bot, please subscribe to the channel {REQUIRED_CHANNELS}.\n"
            "\n✨ Don't forget to subscribe for updates and support: @ytdlpdeveloper\n"
            "\n📝 Blog: https://artoflife2303.github.io/miniblog/\n"
            "\n💻 <a href=\"https://github.com/BitSamurai23/YTMusicDownloader\">GitHub: Open Source Code</a>"
        ),
        "github_message": "💻 <a href=\"https://github.com/BitSamurai23/YTMusicDownloader\">GitHub: Open Source Code</a>\n\n📝 Blog: https://artoflife2303.github.io/miniblog/\n📢 Channel: @ytdlpdeveloper",
        "choose_lang": "Choose language:",
        "not_subscribed": f"To use the bot, please subscribe to all required channels and try again.\n\nRequired: {', '.join(REQUIRED_CHANNELS)}",
        "checking": "Checking link...",
        "not_youtube": "This is not a supported link. Please send a valid YouTube or SoundCloud link.",
        "choose_download_type": "Choose audio format:",
        "audio_button_mp3": "🎵 MP3 (YouTube)",
        "audio_button_sc": "🎵 MP3 (SoundCloud)",
        "downloading_audio": "Downloading audio... Please wait.",
        "download_progress": "Downloading: {percent} at {speed}, ETA ~{eta}",
        "too_big": f"File is too large (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Try another video or track.",
        "done_audio": "Done! Audio sent.",
        "cooldown_message": "⏳ Next download will be available in 15 seconds.",
        "error": "Something went wrong. Check the link or try again!",
        "error_private_video": "This is a private video and cannot be downloaded.",
        "error_video_unavailable": "Video unavailable.",
        "sending_file": "Sending file {index} of {total}...",
        "cancel_button": "Cancel",
        "cancelling": "Cancelling download...",
        "cancelled": "Download cancelled.",
        "download_in_progress": "Another download is already in progress. Please wait or cancel it.",
        "already_cancelled_or_done": "Download already cancelled or completed.",
        "url_error_generic": "Failed to process URL. Make sure it's a valid YouTube or SoundCloud link.",
        "search_prompt": (
            "Enter the track name or artist. Then click on the music, it will download in MP3/M4A format.\n"
            "Enter /cancel to cancel the search.\n"
            "Enter /search to search for music by name (YouTube)."
        ),
        "searching": "Searching for music...",
        "unsupported_url_in_search": "The link is not  supported. Please check the link or try another query. (Alternatively, if it didn't work, you can download a track from another artist or Remix)",
        "no_results": "Nothing found. Try another query.",
        "choose_track": "Select a track to download in MP3:",
        "downloading_selected_track": "Downloading the selected track in MP3...",
        "copyright_pre": "⚠️ Warning! The material you are about to download may be protected by copyright. Use for personal purposes only. If you are a copyright holder and believe your rights are being violated, please contact copyrightytdlpbot@gmail.com for removal.",
        "copyright_post": "⚠️ This material may be protected by copyright. Use for personal purposes only. If you are a copyright holder and believe your rights are being violated, contact copyrightytdlpbot@gmail.com.",
        "copyright_command": "⚠️ Warning! All materials downloaded via this bot may be protected by copyright. Use for personal purposes only. If you are a copyright holder and believe your rights are being violated, contact copyrightytdlpbot@gmail.com and we will remove the content."
    },
    # ...другие языки по аналогии...
}

# Load environment variables from .env file
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("Cant found TELEGRAM_BOT_TOKEN in environment variables.")

# Paths and variables
cookies_path = os.getenv('COOKIES_PATH', 'youtube.com_cookies.txt')
ffmpeg_path_from_env = os.getenv('FFMPEG_PATH')
ffmpeg_path = ffmpeg_path_from_env if ffmpeg_path_from_env else '/usr/bin/ffmpeg'   # Default path for ffmpeg
FFMPEG_IS_AVAILABLE = os.path.exists(ffmpeg_path) and os.access(ffmpeg_path, os.X_OK)   # Check if ffmpeg is available
REQUIRED_CHANNELS = [
    "@ytdlpdeveloper",
    "@samuraicodingrus"
]    # Channel to which users must be subscribed
TELEGRAM_FILE_SIZE_LIMIT_BYTES = 50 * 1024 * 1024 # 50 MB in bytes
TELEGRAM_FILE_SIZE_LIMIT_TEXT = "50 МБ" # Text representation of the file size limit 
# File to store user language preferences
USER_LANGS_FILE = "user_languages.json" # File to store user language preferences
# Check if the cookies file exists              
if not os.path.exists(cookies_path):
    logger.warning(f"Cookies file {cookies_path} not found. Some features may not work properly.")
# Keyboard for language selection # This keyboard will be shown to users when they start the bot or change language 
LANG_KEYBOARD = ReplyKeyboardMarkup( # Keyboard for selecting language
    [
        ["Русский", "English"], # Russian and English
        ["Español", "Azərbaycan dili"], # Spanish and Azerbaijani        
        ["Türkçe", "Українська"], # Turkish and Ukrainian
        ["العربية"] # Arabic
    ], 
    resize_keyboard=True, # Resize keyboard buttons
    one_time_keyboard=True # Hide keyboard after selection
)
# Mapping language names to codes
LANG_CODES = { # Mapping language names to their respective language codes
    "Русский": "ru", "English": "en", "Españол": "es", # Spanish
    "Azərbaycan dili": "az", "Türkçe": "tr", "Українська": "uk", # Ukrainian
    "العربية": "ar" # Arabic
}

SEARCH_RESULTS_LIMIT = 10 # Search results limit
user_langs = {} # Dictionary for storing user language preferences

# Dictionary to store the last download time for each user (user_id: timestamp)

# Dictionary to store the last search time for each user (user_id: timestamp)
user_last_download_time = {}
user_last_search_time = {}

# Dictionaries with localized texts
LANGUAGES = {
    "ru": {
        "start": (
            "👋 Привет! Я — бот для скачивания музыки с YouTube и SoundCloud.\n\n"
            "🔗 Просто отправьте ссылку на видео или трек, и я помогу скачать аудио.\n"
            "\n🎵 Я также умею искать музыку по названию! Просто напишите /search.\n\n"
            f"📢 Для работы с ботом, подпишитесь на канал {REQUIRED_CHANNELS}.\n"
            "\n✨ Не забудьте подписаться на канал для обновлений и поддержки: @ytdlpdeveloper\n"
            "\n📝 Блог: https://artoflife2303.github.io/minиблог/\n"
            "\n💻 GitHub: https://github.com/BitSamurai23/YTMusicDownloader"
        ),
        "choose_lang": "Выберите язык / Choose language:",
        "not_subscribed": f"Чтобы пользоваться ботом, подпишитесь на все каналы и попробуйте снова.\n\nТребуется подписка: {', '.join(REQUIRED_CHANNELS)}",
        "checking": "Проверяю ссылку...",
        "not_youtube": "Это не поддерживаемая ссылка. Отправьте корректную ссылку на YouTube или SoundCloud.",
        "choose_download_type": "Выберите формат аудио:",
        "audio_button_mp3": "🎵 MP3 (YouTube)",
        "audio_button_sc": "🎵 MP3 (SoundCloud)",
        "downloading_audio": "Скачиваю аудио... Подождите.",
        "download_progress": "Скачиваю: {percent} на скорости {speed}, осталось ~{eta}",
        "too_big": f"Файл слишком большой (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Попробуйте другое видео или трек.",
        "done_audio": "Готово! Аудио отправлено.",
        "cooldown_message": "⏳ Следующее скачивание будет доступно через 15 секунд.",
        "error": "Что-то пошло не так. Проверьте ссылку или попробуйте позже!\n",
        "error_private_video": "Это приватное видео и не может быть скачано.",
        "error_video_unavailable": "Видео недоступно.",
        "sending_file": "Отправляю файл {index} из {total}...",
        "cancel_button": "Отмена",
        "cancelling": "Отменяю загрузку...",
        "cancelled": "Загрузка отменена.",
        "download_in_progress": "Другая загрузка уже в процессе. Пожалуйста, подождите или отмените её.",
        "already_cancelled_or_done": "Загрузка уже отменена или завершена.",
        "url_error_generic": "Не удалось обработать URL. Убедитесь, что это корректная ссылка на YouTube или SoundCloud.",
        "search_prompt": (
            "Введите название трека или исполнителя. После чего, нажмите на музыку, она загрузится в формате MP3/M4A.\n"
            "Введите /cancel для отмены поиска.\n"
            "Введите /search для поиска музыки по названию (YouTube)."
        ),
        "searching": "Ищу музыку...",
        "unsupported_url_in_search": "Ссылка не поддерживается. Пожалуйста, проверьте другую ссылку или попробуйте другой запрос.(Альтернативно, если у вас не получилось, вы можете загрузить трек от другого исполнителя или Remix)",
        "no_results": "Ничего не найдено. Попробуйте другой запрос.",
        "choose_track": "Выберите трек для скачивания MP3/M4A:",
        "downloading_selected_track": "Скачиваю выбранный трек в MP3/M4A...",
        "copyright_pre": "⚠️ Внимание! Загружаемый вами материал может быть защищён авторским правом. Используйте только для личных целей. Если вы являетесь правообладателем и считаете, что ваши права нарушены, напишите на copyrightytdlpbot@gmail.com для удаления контента.",
        "copyright_post": "⚠️ Данный материал может быть защищён авторским правом. Используйте только для личных целей. Если вы правообладатель и считаете, что ваши права нарушены, напишите на copyrightytdlpbot@gmail.com.",
        "copyright_command": "⚠️ Внимание! Все материалы, скачиваемые через этого бота, могут быть защищены авторским правом. Используйте только для личных целей. Если вы правообладатель и считаете, что ваши права нарушены, напишите на copyrightytdlpbot@gmail.com, и мы удалим соответствующий контент."
    },
    "en": {
        "start": (
            "👋 Hello! I am a bot for downloading music from YouTube and SoundCloud.\n\n"
            "🔗 Just send a YouTube or SoundCloud link (video or track) and I will help you download the audio.\n"
            "\n🎵 I can also search for music by name! Just type /search.\n\n"
            f"📢 To use the bot, please subscribe to the channel {REQUIRED_CHANNELS}.\n"
            "\n✨ Don't forget to subscribe for updates and support: @ytdlpdeveloper\n"
            "\n📝 Blog: https://artoflife2303.github.io/miniblog/\n"
            "\n💻 <a href=\"https://github.com/BitSamurai23/YTMusicDownloader\">GitHub: Open Source Code</a>"
        ),
        "github_message": "💻 <a href=\"https://github.com/BitSamurai23/YTMusicDownloader\">GitHub: Open Source Code</a>\n\n📝 Blog: https://artoflife2303.github.io/minиблог/\n📢 Channel: @ytdlpdeveloper",
        "choose_lang": "Choose language:",
        "not_subscribed": f"To use the bot, please subscribe to all required channels and try again.\n\nRequired: {', '.join(REQUIRED_CHANNELS)}",
        "checking": "Checking link...",
        "not_youtube": "This is not a supported link. Please send a valid YouTube or SoundCloud link.",
        "choose_download_type": "Choose audio format:",
        "audio_button_mp3": "🎵 MP3 (YouTube)",
        "audio_button_sc": "🎵 MP3 (SoundCloud)",
        "downloading_audio": "Downloading audio... Please wait.",
        "download_progress": "Downloading: {percent} at {speed}, ETA ~{eta}",
        "too_big": f"File is too large (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Try another video or track.",
        "done_audio": "Done! Audio sent.",
        "cooldown_message": "⏳ Next download will be available in 15 seconds.",
        "error": "Something went wrong. Check the link or try again!",
        "error_private_video": "This is a private video and cannot be downloaded.",
        "error_video_unavailable": "Video unavailable.",
        "sending_file": "Sending file {index} of {total}...",
        "cancel_button": "Cancel",
        "cancelling": "Cancelling download...",
        "cancelled": "Download cancelled.",
        "download_in_progress": "Another download is already in progress. Please wait or cancel it.",
        "already_cancelled_or_done": "Download already cancelled or completed.",
        "url_error_generic": "Failed to process URL. Make sure it's a valid YouTube or SoundCloud link.",
        "search_prompt": (
            "Enter the track name or artist. Then click on the music, it will download in MP3/M4A format.\n"
            "Enter /cancel to cancel the search.\n"
            "Enter /search to search for music by name (YouTube)."
        ),
        "searching": "Searching for music...",
        "unsupported_url_in_search": "The link is not  supported. Please check the link or try another query. (Alternatively, if it didn't work, you can download a track from another artist or Remix)",
        "no_results": "Nothing found. Try another query.",
        "choose_track": "Select a track to download in MP3:",
        "downloading_selected_track": "Downloading the selected track in MP3...",
        "copyright_pre": "⚠️ Warning! The material you are about to download may be protected by copyright. Use for personal purposes only. If you are a copyright holder and believe your rights are being violated, please contact copyrightytdlpbot@gmail.com for removal.",
        "copyright_post": "⚠️ This material may be protected by copyright. Use for personal purposes only. If you are a copyright holder and believe your rights are being violated, contact copyrightytdlpbot@gmail.com.",
        "copyright_command": "⚠️ Warning! All materials downloaded via this bot may be protected by copyright. Use for personal purposes only. If you are a copyright holder and believe your rights are being violated, contact copyrightytdlpbot@gmail.com and we will remove the content."
    },
    "es": {
        "start": (
            "👋 ¡Hola! Soy un bot para descargar música de YouTube y SoundCloud.\n\n"
            "🔗 Solo envía un enlace de YouTube o SoundCloud (video o pista) y te ayudaré a descargar el audio.\n"
            "\n🎵 ¡También puedo buscar música por nombre! Escribe /search.\n\n"
            f"📢 Para usar el bot, suscríbete al canal {REQUIRED_CHANNELS}.\n"
            "\n✨ No olvides suscribirte para actualizaciones y soporte: @ytdlpdeveloper\n"
            "\n📝 Blog: https://artoflife2303.github.io/miniblog/\n"
            "\n💻 GitHub: https://github.com/BitSamurai23/YTMusicDownloader"
        ),
        "choose_lang": "Elige idioma:",
        "not_subscribed": f"Para usar el bot, suscríbete al canal {REQUIRED_CHANNELS} y vuelve a intentarlo.",
        "checking": "Verificando enlace...",
        "not_youtube": "Este enlace no es compatible. Por favor, envía un enlace válido de YouTube o SoundCloud.",
        "choose_download_type": "Elige el formato de audio:",
        "audio_button_mp3": "🎵 MP3 (YouTube)",
        "audio_button_sc": "🎵 MP3 (SoundCloud)",
        "downloading_audio": "Descargando audio... Por favor espera.",
        "download_progress": "Descargando: {percent} a {speed}, queda ~{eta}",
        "too_big": f"El archivo es demasiado grande (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Prueba con otro video o pista.",
        "done_audio": "¡Listo! Audio enviado.",
        "cooldown_message": "⏳ La próxima descarga estará disponible en 15 segundos.",
        "error": "¡Algo salió mal! Verifica el enlace o inténtalo de nuevo.",
        "error_private_video": "Este es un video privado y no puede ser descargado.",
        "error_video_unavailable": "Video no disponible.",
        "sending_file": "Enviando archivo {index} de {total}...",
        "cancel_button": "Cancelar",
        "cancelling": "Cancelando descarga...",
        "cancelled": "Descarga cancelada.",
        "download_in_progress": "Otra descarga ya está en progreso. Por favor espera o cancélala.",
        "already_cancelled_or_done": "La descarga ya fue cancelada o completada.",
        "url_error_generic": "No se pudo procesar la URL. Asegúrate de que sea un enlace válido de YouTube o SoundCloud.",
        "search_prompt": (
            "Ingrese el nombre de la pista o artista. Luego haga clic en la música, se descargará en formato MP3.\n"
            "Ingrese /cancel para cancelar la búsqueda.\n"
            "Ingrese /search para buscar música por nombre (YouTube)."
        ),
        "searching": "Buscando música...",
        "unsupported_url_in_search": "El enlace no es compatible. Por favor, compruebe el enlace o pruebe con otra consulta. (Alternativamente, si no funcionó, puede descargar una pista de otro artista o un Remix)",
        "no_results": "No se encontraron resultados. Intente con otra consulta.",
        "choose_track": "Seleccione una pista para descargar en MP3:",
        "downloading_selected_track": "Descargando la pista seleccionada en MP3...",
        "copyright_pre": "⚠️ ¡Atención! El material que está a punto de descargar puede estar protegido por derechos de autor. Úselo solo para fines personales. Si es titular de derechos y cree que se están violando sus derechos, escriba a copyrightytdlpbot@gmail.com para eliminar el contenido.",
        "copyright_post": "⚠️ Este material puede estar protegido por derechos de autor. Úselo solo para fines personales. Si es titular de derechos y cree que se están violando sus derechos, escriba a copyrightytdlpbot@gmail.com.",
        "copyright_command": "⚠️ ¡Atención! Todo el material descargado a través de este bot puede estar protegido por derechos de autor. Úselo solo para fines personales. Si es titular de derechos y cree que se están violando sus derechos, escriba a copyrightytdlpbot@gmail.com y eliminaremos el contenido."
    },
    "tr": {
        "start": (
            "👋 Merhaba! Ben YouTube ve SoundCloud'dan müzik indirmek için bir botum.\n\n"
            "🔗 Sadece bir YouTube veya SoundCloud bağlantısı gönderin (video veya parça), ses dosyasını indirmenize yardımcı olacağım.\n"
            "\n🎵 Ayrıca isimle müzik arayabilirim! Sadece /search yazın.\n\n"
            f"📢 Botu kullanmak için lütfen {REQUIRED_CHANNELS} kanalına abone olun.\n"
            "\n✨ Güncellemeler ve destek için abone olmayı unutmayın: @ytdlpdeveloper\n"
            "\n📝 Blog: https://artoflife2303.github.io/miniblog/\n"
            "\n💻 GitHub: https://github.com/BitSamurai23/YTMusicDownloader"
        ),
        "choose_lang": "Dil seçin:",
        "not_subscribed": f"Botu kullanmak için lütfen {REQUIRED_CHANNELS} kanalına abone olun ve tekrar deneyin.",
        "checking": "Bağlantı kontrol ediliyor...",
        "not_youtube": "Bu desteklenmeyen bir bağlantı. Lütfen geçerli bir YouTube veya SoundCloud bağlantısı gönderin.",
        "choose_download_type": "Ses formatı seçin:",
        "audio_button_mp3": "🎵 MP3 (YouTube)",
        "audio_button_sc": "🎵 MP3 (SoundCloud)",
        "downloading_audio": "Ses indiriliyor... Lütfen bekleyin.",
        "download_progress": "İndiriliyor: {percent} hızında {speed}, kalan ~{eta}",
        "too_big": f"Dosya çok büyük (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Başka bir video veya parça deneyin.",
        "done_audio": "Tamamlandı! Ses gönderildi.",
        "cooldown_message": "⏳ Sonraki indirme 15 saniye sonra mümkün olacak.",
        "error": "Bir hata oluştu. Bağlantıyı kontrol edin veya tekrar deneyin!\n",
        "error_private_video": "Bu özel bir video ve indirilemez.",
        "error_video_unavailable": "Video kullanılamıyor.",
        "sending_file": "{total} dosyadan {index}. gönderiliyor...",
        "cancel_button": "İptal",
        "cancelling": "İndirme iptal ediliyor...",
        "cancelled": "İndirme iptal edildi.",
        "download_in_progress": "Başka bir indirme zaten devam ediyor. Lütfen bekleyin veya iptal edin.",
        "already_cancelled_or_done": "İndirme zaten iptal edildi veya tamamlandı.",
        "url_error_generic": "URL işlenemedi. Geçerli bir YouTube veya SoundCloud bağlantısı olduğundan emin olun.",
        "search_prompt": (
            "Parça adı veya sanatçı adı girin. Ardından müziyə tıklayın, MP3 formatında indirilecektir.\n"
            "Aramayı iptal etmek için /cancel yazın.\n"
            "Müzik adıyla arama yapmak için /search yazın (YouTube)."
        ),
        "searching": "Musiqi axtarılır...",
        "unsupported_url_in_search": "Bağlantı desteklenmir. Zəhmət olmasa, bağlantını yoxlayın və ya başqa bir sorğu sınayın. (Alternativ olaraq, əgər işləmədisə, başqa bir ifaçıdan və ya Remix bir trek yükləyə bilərsiniz)",
        "no_results": "Heç nə tapılmadı. Başqa bir sorğu sınayın.",
        "choose_track": "MP3 olaraq yükləmək üçün bir trek seçin:",
        "downloading_selected_track": "Seçilən trek MP3 olaraq yüklənir...",
        "copyright_pre": "⚠️ Dikkat! İndirmək üzrə olduğunuz materyal telif haqqı ilə qoruna bilər. Yalnızca şəxsi istifadə üçün istifadə edin. Əgər siz hüquq sahibisiniz və hüquqlarınızın pozulduğunu düşünürsənsə, zəhmət olmasa copyrightytdlpbot@gmail.com ünvanına yazın.",
        "copyright_post": "⚠️ Bu materyal telif haqqı ilə qoruna bilər. Yalnızca şəxsi istifadə üçün istifadə edin. Əgər siz hüquq sahibisiniz və hüquqlarınızın pozulduğunu düşünürsə, copyrightytdlpbot@gmail.com ünvanına yazın.",
        "copyright_command": "⚠️ Diqqət! Bu bot vasitəsilə yüklənən bütün materiallar müəllif hüquqları ilə qoruna bilər. Yalnızca şəxsi istifadə üçün istifadə edin. Əgər siz hüquq sahibisiniz və hüquqlarınızın pozulduğunu düşünürsə, copyrightytdlpbot@gmail.com ünvanına yazın, müvafiq məzmunu siləcəyik."
    },
    "ar": {
        "start": (
            "👋 مرحبًا! أنا بوت لتنزيل الموسيقى من YouTube و SoundCloud.\n\n"
            "🔗 فقط أرسل رابط YouTube أو SoundCloud (فيديو أو مسار) وسأساعدك في تنزيل الصوت.\n"
            "\n🎵 يمكنني أيضًا البحث عن الموسيقى بالاسم! فقط اكتب /search.\n\n"
            f"📢 لاستخدام البوت، يرجى الاشتراك في القناة {REQUIRED_CHANNELS}.\n"
            "\n💡 النسخة الويب: youtubemusicdownloader.life (أو bit.ly/ytmusicload)\n"
            "\n✨ لا تنس الاشتراك للحصول على التحديثات والدعم: @ytdlpdeveloper\n"
            "\n📝 المدونة: https://artoflife2303.github.io/miniblog/\n"
            "\n💻 GitHub: https://github.com/BitSamurai23/YTMusicDownloader"
        ),
        "choose_lang": "اختر اللغة:",
        "not_subscribed": f"لاستخدام البوت، يرجى الاشتراك في قناة {REQUIRED_CHANNELS} والمحاولة مرة أخرى.",
        "checking": "جاري التحقق من الرابط...",
        "not_youtube": "هذا ليس رابطًا مدعومًا. يرجى إرسال رابط YouTube أو SoundCloud صالح.",
        "choose_download_type": "اختر تنسيق الصوت:",
        "audio_button_mp3": "🎵 MP3 (يوتيوب)",
        "audio_button_sc": "🎵 MP3 (ساوند كلاود)",
        "downloading_audio": "جاري تنزيل الصوت... يرجى الانتظار.",
        "download_progress": "جاري التنزيل: {percent} بسرعة {speed}، متبقي ~{eta}",
        "too_big": f"الملف كبير جدًا (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). جرب فيديو أو مسارًا آخر.",
        "done_audio": "تم! تم إرسال الصوت.",
        "cooldown_message": "⏳ سيكون التنزيل التالي متاحًا بعد 15 ثانية.",
        "error": "حدث خطأ ما. تحقق من الرابط أو حاول مرة أخرى!",
        "error_private_video": "هذا فيديو خاص ولا يمكن تنزيله.",
        "error_video_unavailable": "الفيديو غير متاح.",
        "sending_file": "جاري إرسال الملف {index} من {total}...",
        "cancel_button": "إلغاء",
        "cancelling": "جاري إلغاء التنزيل...",
        "cancelled": "تم إلغاء التنزيل.",
        "download_in_progress": "تنزيل آخر قيد التقدم بالفعل. يرجى الانتظار أو إلغائه.",
        "already_cancelled_or_done": "تم إلغاء التنزيل أو إكماله بالفعل.",
        "url_error_generic": "فشل في معالجة الرابط. تأكد من أنه رابط YouTube أو SoundCloud صالح.",
        "search_prompt": (
            "أدخل اسم المقطع الصوتي أو الفنان. ثم انقر على الموسيقى، سيتم تنزيلها بصيغة MP3.\n"
            "أدخل /cancel لإلغاء البحث.\n"
            "أدخل /search للبحث عن الموسيقى بالاسم (يوتيوب)."
        ),
        "searching": "جاري البحث عن الموسيقى...",
        "unsupported_url_in_search": "الرابط غير مدعوم. يرجى التحقق من الرابط أو تجربة استعلام آخر. (بدلاً من ذلك، إذا لم ينجح الأمر، يمكنك تنزيل مقطع صوتي من فنان آخر أو ريمكس)",
        "no_results": "لم يتم العثور على شيء. حاول استعلامًا آخر.",
        "choose_track": "حدد مسارًا لتنزيله بصيغة MP3:",
        "downloading_selected_track": "جاري تنزيل المسار المحدد بصيغة MP3...",
        "copyright_pre": " تحذير! قد يكون المحتوى الذي توشك على تنزيله محميًا بحقوق النشر. استخدمه للأغراض الشخصية فقط. إذا كنت صاحب حقوق وتعتقد أن حقوقك منتهكة، يرجى التواصل عبر copyrightytdlpbot@gmail.com لحذف المحتوى.",
        "copyright_post": "⚠️ قد يكون هذا المحتوى محميًا بحقوق النشر. استخدمه للأغراض الشخصية فقط. إذا كنت صاحب حقوق وتعتقد أن حقوقك منتهكة، يرجى التواصل عبر copyrightytdlpbot@gmail.com.",
        "copyright_command": "⚠️ تحذير! جميع المواد التي يتم تنزيلها عبر هذا البوت قد تكون محمية بحقوق النشر. استخدمها للأغراض الشخصية فقط. إذا كنت صاحب حقوق وتعتقد أن حقوقك منتهكة، يرجى التواصل عبر copyrightytdlpbot@gmail.com وسنقوم بحذف المحتوى."
    },
    "az": {
        "start": (
            "👋 Salam! Mən YouTube və SoundCloud-dan musiqi yükləmək üçün bir botam.\n\n"
            "🔗 Sadəcə YouTube və ya SoundCloud linki göndərin (video və ya trek), səs faylını yükləməyə kömək edəcəyəm.\n"
            "\n🎵 Həmçinin adla musiqi axtara bilərəm! Sadəcə /search yazın.\n\n"
            f"📢 Botdan istifadə etmək üçün {REQUIRED_CHANNELS} kanalına abunə olun.\n"
            "\n✨ Yeniliklər və dəstək üçün kanala abunə olmağı unutmayın: @ytdlpdeveloper\n"
            "\n📝 Blog: https://artoflife2303.github.io/miniblog/\n"
            "\n💻 GitHub: https://github.com/BitSamurai23/YTMusicDownloader"
        ),
        "choose_lang": "Dil seçin:",
        "not_subscribed": f"Botdan istifadə etmək üçün zəhmət olmasa {REQUIRED_CHANNELS} kanalına abunə olun və yenidən cəhd edin.",
        "checking": "Link yoxlanılır...",
        "not_youtube": "Bu dəstəklənməyən bir bağlantı. Zəhmət olmasa, etibarlı bir YouTube və ya SoundCloud linki göndərin.",
        "choose_download_type": "Səs formatını seçin:",
        "audio_button_mp3": "🎵 MP3 (YouTube)",
        "audio_button_sc": "🎵 MP3 (SoundCloud)",
        "downloading_audio": "Səs yüklənir... Zəhmət olmasa gözləyin.",
        "download_progress": "Yüklənir: {percent} sürətlə {speed}, qalıb ~{eta}",
        "too_big": f"Fayl çox böyükdür (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Başqa bir video və ya trek sınayın.",
        "done_audio": "Hazırdır! Səs göndərildi.",
        "cooldown_message": "⏳ Növbəti yükləmə 15 saniyədən sonra mümkün olacaq.",
        "error": "Nəsə səhv getdi. Bağlantını yoxlayın və ya sonra cəhd edin!\n",
        "error_private_video": "Bu xüsusi videodur və yüklənə bilməz.",
        "error_video_unavailable": "Video mövcud deyil.",
        "sending_file": "{total} fayldan {index}-i göndərilir...",
        "cancel_button": "Ləğv et",
        "cancelling": "Yükləmə ləğv edilir...",
        "cancelled": "Yükləmə ləğv edildi.",
        "download_in_progress": "Başqa bir yükləmə artıq davam edir. Zəhmət olmasa gözləyin və ya ləğv edin.",
        "already_cancelled_or_done": "Yükləmə artıq ləğv edilib və ya tamamlanıb.",
        "url_error_generic": "URL emal edilə bilmədi. Etibarlı bir YouTube və ya SoundCloud bağlantısı olduğundan əmin olun.",
        "search_prompt": (
            "Trek adı və ya ifaçı adı daxil edin. Sonra musiqiyə tıklayın, MP3 formatında yüklənəcək.\n"
            "Aramayı iptal etmək üçün /cancel yazın.\n"
            "Müzik adıyla arama yapmak için /search yazın (YouTube)."
        ),
        "searching": "Musiqi axtarılır...",
        "unsupported_url_in_search": "Bağlantı desteklenmir. Zəhmət olmasa, bağlantını yoxlayın və ya başqa bir sorğu sınayın. (Alternativ olaraq, əgər işləmədisə, başqa bir ifaçıdan və ya Remix bir trek yükləyə bilərsiniz)",
        "no_results": "Heç nə tapılmadı. Başqa bir sorğu sınayın.",
        "choose_track": "MP3 olaraq yükləmək üçün bir trek seçin:",
        "downloading_selected_track": "Seçilən trek MP3 olaraq yüklənir...",
        "copyright_pre": "⚠️ Diqqət! Yüklədiyiniz material müəllif hüquqları ilə qoruna bilər. Yalnız şəxsi istifadə üçün istifadə edin. Əgər siz hüquq sahibisiniz və hüquqlarınızın pozulduğunu düşünürsənsə, zəhmət olmasa copyrightytdlpbot@gmail.com ünvanına yazın.",
        "copyright_post": "⚠️ Bu material müəllif hüquqları ilə qoruna bilər. Yalnız şəxsi istifadə üçün istifadə edin. Əgər siz hüquq sahibisiniz və hüquqlarınızın pozulduğunu düşünürsə, copyrightytdlpbot@gmail.com ünvanına yazın.",
        "copyright_command": "⚠️ Diqqət! Bu bot vasitəsilə yüklənən bütün materiallar müəllif hüquqları ilə qoruna bilər. Yalnızca şəxsi istifadə üçün istifadə edin. Əgər siz hüquq sahibisiniz və hüquqlarınızın pozulduğunu düşünürsə, copyrightytdlpbot@gmail.com ünvanına yazın, müvafiq məzmunu siləcəyik."
    },
}

def get_user_lang(user_id):
    """
    Determines the user's language by their ID. If no language is found, Russian is used.
    """
    lang = user_langs.get(user_id)
    if lang in LANGUAGES:
        return lang
    return "ru"
def is_soundcloud_url(url):
    """
    Checks if the URL is a SoundCloud link.
    """
    return "soundcloud.com/" in url.lower()
def load_user_langs():
    """
    Loads user language preferences from a file.
    """
    global user_langs
    if os.path.exists(USER_LANGS_FILE):
        with open(USER_LANGS_FILE, 'r', encoding='utf-8') as f:
            try:
                loaded_langs = json.load(f)
                user_langs = {int(k): v for k, v in loaded_langs.items()}
            except json.JSONDecodeError:
                user_langs = {}
    else:
        user_langs = {}
def save_user_langs():
    """
    Saves user language preferences to a file.
    """
    with open(USER_LANGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_langs, f)
    pass
async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Sends the user a keyboard to choose a language.
    """
    logger.info(f"User {update.effective_user.id} requested language choice.")
    await update.message.reply_text(
        LANGUAGES["ru"]["choose_lang"], # Use Russian text by default for language selection.
        reply_markup=LANG_KEYBOARD
    )
    pass
async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Sets the language for the user and sends a welcome message.
    """
    lang_name = update.message.text
    lang_code = LANG_CODES.get(lang_name)
    user_id = update.effective_user.id
    if lang_code:
        user_langs[user_id] = lang_code
        save_user_langs()
        logger.info(f"User {user_id} set language to {lang_code}.")
        await update.message.reply_text(LANGUAGES[lang_code]["start"])
    else:
        logger.warning(f"User {user_id} sent invalid language: {lang_name}.")
        await update.message.reply_text(
            "Please choose a language from the keyboard."
        )
    pass
async def check_subscription(user_id: int, bot) -> bool:
    """
    Checks if the user is subscribed to all required channels.
    """
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status not in ("member", "administrator", "creator"):
                logger.info(f"User {user_id} is NOT subscribed to {channel}")
                return False
        except Exception as e:
            logger.error(f"Error checking subscription for user {user_id} in {channel}: {e}")
            return False
    return True

def blocking_yt_dlp_download(ydl_opts, url_to_download):
    """
    Performs download using yt-dlp in blocking mode.
    """
    import yt_dlp.utils
    import logging
    yt_dlp_logger = logging.getLogger("yt_dlp")
    yt_dlp_logger.setLevel(logging.WARNING) # Set logging level for yt-dlp
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url_to_download])
        return True
    except yt_dlp.utils.UnsupportedError:
        raise Exception("Unsupported URL: {}".format(url_to_download))
    except Exception as e:
        logger.error(f"yt-dlp download error: {e}")
        raise # Re-raise all other exceptions
    pass
async def ask_download_type(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    """
    Sends a copyright warning and asks the user about the download type (MP3/M4A/MP4 for YouTube/SoundCloud).
    """
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    await update.message.reply_text(texts.get("copyright_pre"))
    context.user_data[f'url_for_download_{user_id}'] = url
    # Allow both mp3, m4a, mp4 for YouTube, only mp3 for SoundCloud
    if is_soundcloud_url(url):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(texts["audio_button_sc"], callback_data=f"dltype_audio_sc_{user_id}")]
        ])
    else:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎵 MP3 (YouTube)", callback_data=f"dltype_audio_mp3_{user_id}"),
                InlineKeyboardButton("🎵 M4A (YouTube)", callback_data=f"dltype_audio_m4a_{user_id}"),
                InlineKeyboardButton("📹 MP4 720p (YouTube)", callback_data=f"dltype_video_mp4_{user_id}")
            ]
        ])
    await update.message.reply_text("Выберите формат аудио/видео:", reply_markup=keyboard)

async def handle_download(update_or_query, context: ContextTypes.DEFAULT_TYPE, url: str, texts: dict, user_id: int, download_type: str):
    """
    Handles the download of an audio or video file from YouTube or SoundCloud.
    """
    import time
    if not update_or_query.message:
        try:
            await context.bot.send_message(chat_id=user_id, text=texts["error"] + " (internal error: chat not found)")
        except Exception:
            pass
        return

    chat_id = update_or_query.message.chat_id
    temp_dir = None
    status_message = None
    active_downloads = context.bot_data.setdefault('active_downloads', {})
    loop = asyncio.get_running_loop()
    cancel_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(texts["cancel_button"], callback_data=f"cancel_{user_id}")]])

    # --- Таймаут между скачиваниями ---
    global user_last_download_time
    now = time.time()
    cooldown = 15  # секунд

    async def update_status_message_async(text_to_update, show_cancel_button=True):
        """
        Updates the status message in the chat.
        """
        nonlocal status_message
        if status_message:
            try:
                current_keyboard = cancel_keyboard if show_cancel_button else None
                await status_message.edit_text(text_to_update, reply_markup=current_keyboard)
            except Exception as e:
                logger.debug(f"Could not edit status message: {e}") # Debug message
                pass # Ignore errors when editing the message.

    def progress_hook(d):
        """
        Progress hook for yt-dlp.
        """
        if d['status'] == 'downloading':
            percent_str = d.get('_percent_str', 'N/A').strip()
            speed_str = d.get('_speed_str', 'N/A').strip()
            eta_str = d.get('_eta_str', 'N/A').strip()
            progress_text = texts["download_progress"].format(percent=percent_str, speed=speed_str, eta=eta_str)
            asyncio.run_coroutine_threadsafe(update_status_message_async(progress_text), loop)

    try:
        # Проверка таймаута между скачиваниями
        last_time = user_last_download_time.get(user_id, 0)
        if now - last_time < cooldown and user_id != 7009242731:
            wait_sec = int(cooldown - (now - last_time))
            await context.bot.send_message(chat_id=chat_id, text=f"⏳ Пожалуйста, подождите {wait_sec} сек. перед следующим скачиванием.")
            return

        # Проверка количества активных загрузок для пользователя
        active_downloads = context.user_data.setdefault('active_downloads', [])
        active_downloads = [download for download in active_downloads if not download['task'].done()]
        if len(active_downloads) >= 3 and user_id != 7009242731:
            await context.bot.send_message(chat_id=chat_id, text="У вас уже есть 3 активные загрузки. Пожалуйста, дождитесь их завершения.")
            return

        # Сохраняем время начала скачивания
        user_last_download_time[user_id] = now
        # Статистика
        user_stats.setdefault(user_id, {"downloads": 0, "searches": 0})
        user_stats[user_id]["downloads"] += 1

        status_message = await context.bot.send_message(chat_id=chat_id, text=texts["downloading_audio"], reply_markup=cancel_keyboard)
        temp_dir = tempfile.mkdtemp()
        # Установка базовых настроек для всех форматов
        ydl_opts = {
            'outtmpl': os.path.join(temp_dir, '%(artist,uploader,channel)s - %(title)s [Made by @ytdlpload_bot].%(ext)s'),
            'cookiefile': cookies_path if os.path.exists(cookies_path) else None,
            'progress_hooks': [progress_hook],
            'nocheckcertificate': True,
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': ffmpeg_path if FFMPEG_IS_AVAILABLE else None,
            'verbose': True,
            'writethumbnail': True,
            'embedthumbnail': True,
            'addmetadata': True,
            'writeinfojson': True,
            'postprocessor_args': [
                '-metadata', 'title=%(title)s',
                '-metadata', 'artist=%(artist,uploader,channel)s'
            ]
        }

        # Настройки в зависимости от формата
        if download_type == "audio_mp3" or download_type == "audio_sc":
            ext_list = [".mp3", ".m4a", ".webm", ".ogg", ".opus", ".aac"]
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '320',
                    },
                    {
                        'key': 'FFmpegMetadata',
                        'add_metadata': True,
                    },
                    {
                        'key': 'EmbedThumbnail',
                    }
                ],
                'postprocessor_args': [
                    '-acodec', 'libmp3lame', 
                    '-ar', '48000',
                    '-b:a', '320k',
                    '-ac', '2',
                    '-compression_level', '0',
                    '-id3v2_version', '3',
                    '-metadata', 'title=%(title)s',
                    '-metadata', 'artist=%(artist,uploader,channel)s'
                ]
            })
        elif download_type == "audio_m4a":
            ext_list = [".m4a", ".mp3", ".webm", ".ogg", ".opus", ".aac"]
            ydl_opts.update({
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
                'postprocessors': [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'm4a',
                        'preferredquality': '320',
                    },
                    {
                        'key': 'FFmpegMetadata',
                        'add_metadata': True,
                    },
                    {
                        'key': 'EmbedThumbnail',
                    }
                ],
                'postprocessor_args': [
                    '-acodec', 'aac',
                    '-ar', '48000', 
                    '-b:a', '320k',
                    '-ac', '2',
                    '-q:a', '0',
                    '-movflags', '+faststart',
                    '-metadata', 'title=%(title)s',
                    '-metadata', 'artist=%(artist,uploader,channel)s'
                ]
            })
        elif download_type == "video_mp4":
            ext_list = [".mp4"]
            ydl_opts.update({
                'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]',
                'merge_output_format': 'mp4',
                'postprocessors': [
                    {
                        'key': 'FFmpegVideoConvertor',
                        'preferedformat': 'mp4'
                    },
                    {
                        'key': 'FFmpegMetadata',
                        'add_metadata': True,
                    },
                    {
                        'key': 'EmbedThumbnail',
                    }
                ],
                'postprocessor_args': [
                    '-c:v', 'libx264',
                    '-crf', '18',
                    '-preset', 'slow',
                    '-c:a', 'aac',
                    '-b:a', '320k',
                    '-ar', '48000',
                    '-ac', '2',
                    '-movflags', '+faststart',
                    '-metadata', 'title=%(title)s',
                    '-metadata', 'artist=%(artist,uploader,channel)s'
                ]
            })
        
        # Удаление None значений из опций
        ydl_opts = {k: v for k, v in ydl_opts.items() if v is not None}

        logger.info(f"Starting download for {url} by user {user_id}")
        try:
            await asyncio.to_thread(blocking_yt_dlp_download, ydl_opts, url)
        except Exception as e:
            if 'Unsupported URL' in str(e) or 'unsupported url' in str(e).lower():
                await update_status_message_async("The link is not supported. Please check the link or try another query.", show_cancel_button=False)
                return
            logger.error(f"Error during yt-dlp download for {url}: {e}")
            raise

        downloaded_files_info = []
        all_temp_files = os.listdir(temp_dir)
        for file_name in all_temp_files:
            file_path = os.path.join(temp_dir, file_name)
            file_ext_lower = os.path.splitext(file_name)[1].lower()
            # Сохраняем полное название, только убираем расширение и ID в конце
            base_title = file_name
            if " [" in base_title:
                base_title = base_title.split(" [")[0]  # Убираем ID видео
            base_title = os.path.splitext(base_title)[0]  # Убираем расширение
            if file_ext_lower in ext_list:
                downloaded_files_info.append((file_path, base_title))

        if not downloaded_files_info:
            await update_status_message_async(texts["error"] + " (file not found)", show_cancel_button=False)
            return

        total_files = len(downloaded_files_info)
        for i, (file_to_send, title_str) in enumerate(downloaded_files_info):
            await update_status_message_async(texts["sending_file"].format(index=i+1, total=total_files))
            file_size = os.path.getsize(file_to_send)

            if file_size > TELEGRAM_FILE_SIZE_LIMIT_BYTES:
                await context.bot.send_message(chat_id=chat_id, text=f"{texts['too_big']} ({os.path.basename(file_to_send)})")
                continue

            # --- Обложка (альбомный ковер, сжатие до <200KB, исправлено для Telegram, с fallback на yt-dlp thumbnail) ---
            cover_bytes = None
            try:
                if file_to_send.endswith('.mp3'):
                    audio = ID3(file_to_send)
                    for tag in audio.values():
                        if tag.FrameID == 'APIC':
                            cover_bytes = tag.data
                            break
                elif file_to_send.endswith('.m4a'):
                    audio = MP4(file_to_send)
                    cov = audio.tags.get('covr')
                    if cov:
                        c = cov[0]
                        if isinstance(c, MP4Cover):
                            cover_bytes = bytes(c)
                        else:
                            cover_bytes = c
            except Exception as e:
                logger.debug(f"No cover found or error extracting cover: {e}")
                cover_bytes = None

            # Если не нашли обложку в файле — пробуем получить через yt-dlp
            if not cover_bytes and 'youtube.com' in url or 'youtu.be' in url:
                cover_bytes = get_youtube_thumbnail(url)

            # --- Сжимаем обложку до <200KB (Telegram limit) ---
            thumb_bytes = None
            if cover_bytes:
                try:
                    img = Image.open(io.BytesIO(cover_bytes))
                    img = img.convert('RGB')
                    # Telegram требует JPEG, <=200KB, <=320x320
                    max_size = (320, 320)
                    img.thumbnail(max_size, Image.LANCZOS)
                    for quality in range(90, 10, -10):
                        thumb_io = io.BytesIO()
                        img.save(thumb_io, format='JPEG', quality=quality, optimize=True)
                        if thumb_io.tell() < 195 * 1024:
                            thumb_bytes = thumb_io.getvalue()
                            break
                    else:
                        thumb_bytes = thumb_io.getvalue()
                except Exception as e:
                    logger.debug(f"Error compressing cover: {e}")
                    thumb_bytes = None

            # --- Отправка аудио или видео с обложкой ---
            try:
                with open(file_to_send, 'rb') as f_send:
                    if download_type == "video_mp4":
                        try:
                            if thumb_bytes:
                                with tempfile.NamedTemporaryFile(suffix='.jpg') as temp_thumb:
                                    temp_thumb.write(thumb_bytes)
                                    temp_thumb.flush()
                                    await context.bot.send_video(
                                        chat_id=chat_id,
                                        video=f_send,
                                        caption=title_str,
                                        filename=os.path.basename(file_to_send),
                                        thumb=open(temp_thumb.name, 'rb')
                                    )
                            else:
                                await context.bot.send_video(
                                    chat_id=chat_id,
                                    video=f_send,
                                    caption=title_str,
                                    filename=os.path.basename(file_to_send)
                                )
                        except Exception as e:
                            logger.error(f"Error sending video: {e}")
                            # Fallback to document if video sending fails
                            await context.bot.send_document(
                                chat_id=chat_id,
                                document=f_send,
                                caption=title_str,
                                filename=os.path.basename(file_to_send)
                            )
                    else:
                        try:
                            if thumb_bytes:
                                with tempfile.NamedTemporaryFile(suffix='.jpg') as temp_thumb:
                                    temp_thumb.write(thumb_bytes)
                                    temp_thumb.flush()
                                    await context.bot.send_audio(
                                        chat_id=chat_id,
                                        audio=f_send,
                                        title=title_str,
                                        filename=os.path.basename(file_to_send),
                                        thumb=open(temp_thumb.name, 'rb')
                                    )
                            else:
                                await context.bot.send_audio(
                                    chat_id=chat_id,
                                    audio=f_send,
                                    title=title_str,
                                    filename=os.path.basename(file_to_send)
                                )
                        except Exception as e:
                            logger.error(f"Error sending audio: {e}")
                            # Fallback to document if audio sending fails
                            await context.bot.send_document(
                                chat_id=chat_id,
                                document=f_send,
                                caption=title_str,
                                filename=os.path.basename(file_to_send)
                            )
                await context.bot.send_message(chat_id=chat_id, text=texts.get("copyright_post"))
                await context.bot.send_message(chat_id=chat_id, text="Made by @ytdlpload_bot")
                await context.bot.send_message(chat_id=chat_id, text="💻 GitHub: https://github.com/BitSamurai23/YTMusicDownloader")
                logger.info(f"Successfully sent audio for {url} to user {user_id}")
            except Exception as e:
                logger.error(f"Error sending audio file {os.path.basename(file_to_send)} to user {user_id}: {e}")
                await context.bot.send_message(chat_id=chat_id, text=f"{texts['error']} (Error sending file {os.path.basename(file_to_send)})")

            # --- Текст песни ---
            # Удалено по просьбе пользователя: функция поиска и отправки текста песни

        await update_status_message_async(texts["done_audio"], show_cancel_button=False)
        try:
            await context.bot.send_message(chat_id=chat_id, text=texts.get("cooldown_message", "⏳ Следующее скачивание будет доступно через 15 секунд."))
        except Exception:
            pass

    except asyncio.CancelledError:
        # Handle download cancellation.
        logger.info(f"Download cancelled for user {user_id}.")
        if status_message:
            await update_status_message_async(texts["cancelled"], show_cancel_button=False)
        else:
            await context.bot.send_message(chat_id=chat_id, text=texts["cancelled"])
    except Exception as e:
        # General error handling for download.
        if 'Unsupported URL' in str(e) or 'unsupported url' in str(e).lower():
            if status_message:
                await update_status_message_async("The link is not supported. Please check the link or try another query.", show_cancel_button=False)
            else:
                await context.bot.send_message(chat_id=chat_id, text="The link is not supported. Please check the link or try another query.")
            return
        logger.critical(f"Unhandled error in handle_download for user {user_id}: {e}", exc_info=True) # Use critical for unhandled errors
        if status_message:
            await update_status_message_async(texts["error"] + str(e), show_cancel_button=False)
        else:
            await context.bot.send_message(chat_id=chat_id, text=texts["error"] + str(e))
    finally:
        # Clean up temporary files
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temporary directory {temp_dir} for user {user_id}.")

        # Удаляем текущую задачу из списка активных загрузок
        active_downloads = context.user_data.get('active_downloads', [])
        current_task = None
        for download in active_downloads:
            if download['task'].done():
                current_task = download
                break
        if current_task:
            active_downloads.remove(current_task)
            context.user_data['active_downloads'] = active_downloads
            logger.info(f"Removed completed download task for user {user_id}")

        # Обновляем время последнего скачивания только если не было ошибки
        if 'now' in locals() and 'e' not in locals():
            user_last_download_time[user_id] = time.time()

async def select_download_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the selection of download type from the Inline keyboard.
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"User {user_id} selected download type: {query.data}")
    try:
        parts = query.data.split("_")
        if len(parts) != 4 or parts[0] != "dltype" or (parts[1] not in ("audio", "video")):
            raise ValueError("Incorrect callback_data format for audio/video")
        specific_format = parts[2]
        user_id_from_callback = int(parts[3])

        if parts[1] == "audio":
            if specific_format == "mp3":
                download_type_for_handler = "audio_mp3"
            elif specific_format == "sc":
                download_type_for_handler = "audio_sc"
            elif specific_format == "m4a":
                download_type_for_handler = "audio_m4a"
            else:
                raise ValueError("Unknown download type")
        elif parts[1] == "video":
            if specific_format == "mp4":
                download_type_for_handler = "video_mp4"
            else:
                raise ValueError("Unknown video download type")
        else:
            raise ValueError("Unknown callback type")

    except (IndexError, ValueError) as e:
        logger.error(f"Error parsing callback_data for user {user_id}: {e} - Data: {query.data}")
        await query.edit_message_text("Selection error. Please try sending the link again.")
        return

    requesting_user_id = query.from_user.id
    if user_id_from_callback != requesting_user_id:
        logger.warning(f"User {requesting_user_id} tried to use another user's callback: {user_id_from_callback}")
        await query.edit_message_text("This button is not for you.")
        return

    lang = get_user_lang(requesting_user_id)
    texts = LANGUAGES[lang]

    url_to_download = context.user_data.pop(f'url_for_download_{requesting_user_id}', None)
    if not url_to_download:
        logger.error(f"URL not found in user_data for user {requesting_user_id}")
        await query.edit_message_text(texts["error"] + " (URL not found, try again)")
        return

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception as e:
        logger.debug(f"Could not remove reply markup: {e}")
        pass

    # Инициализация и очистка списка активных загрузок пользователя
    active_downloads = context.user_data.setdefault('active_downloads', [])
    active_downloads = [download for download in active_downloads if not download['task'].done()]
    
    # Проверка лимита одновременных загрузок
    if len(active_downloads) >= 3:
        await query.edit_message_text("У вас уже есть 3 активные загрузки. Пожалуйста, дождитесь их завершения.")
        return
    
    # Создание новой задачи загрузки
    task = asyncio.create_task(handle_download(query, context, url_to_download, texts, requesting_user_id, download_type_for_handler))
    
    # Добавление новой задачи в список активных загрузок
    active_downloads.append({
        'task': task,
        'type': download_type_for_handler,
        'start_time': time.time()
    })
    context.user_data['active_downloads'] = active_downloads

async def search_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the selection of a track from search results.
    """
    query = update.callback_query
    await query.answer() # Answer CallbackQuery to remove the 'clock' from the button.
    user_id = query.from_user.id
    logger.info(f"User {user_id} selected track from search: {query.data}")

    # Parse callback_data: format is 'searchsel_{user_id}_{video_id}'
    try:
        _, sel_user_id, video_id = query.data.split("_", 2)
        sel_user_id = int(sel_user_id)
    except Exception as e:
        logger.error(f"Error parsing search select callback data for user {user_id}: {e} - Data: {query.data}")
        await query.edit_message_text("Track selection error.")
        return

    if user_id != sel_user_id:
        logger.warning(f"User {user_id} tried to use another user's search select callback: {sel_user_id}")
        await query.edit_message_text("This button is not for you.")
        return

    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]

    url = f"https://youtu.be/{video_id}"  # Form URL from video ID.
    # Store the URL for the next step (format selection)
    context.user_data[f'url_for_download_{user_id}'] = url

    # Send copyright warning and ask for format (MP3/M4A/MP4)
    try:
        await query.edit_message_text(texts.get("copyright_pre"))
    except Exception as e:
        logger.debug(f"Could not edit copyright warning: {e}")
        pass

    # Show all three buttons for YouTube
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 MP3 (YouTube)", callback_data=f"dltype_audio_mp3_{user_id}"),
            InlineKeyboardButton("🎵 M4A (YouTube)", callback_data=f"dltype_audio_m4a_{user_id}"),
            InlineKeyboardButton("📹 MP4 720p (YouTube)", callback_data=f"dltype_video_mp4_{user_id}")
        ]
    ])
    await context.bot.send_message(
        chat_id=user_id,
        text=texts.get("choose_download_type", "Choose audio/video format:"),
        reply_markup=keyboard
    )

async def search_youtube(query: str):
    """
    Performs a search for videos on YouTube.
    """
    if is_url(query):
        return 'unsupported_url'

    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'extract_flat': True,
        'nocheckcertificate': True,
        'default_search': None,
        'noplaylist': True
    }
    try:
        search_query = f"ytsearch{SEARCH_RESULTS_LIMIT}:{query}"
        logger.info(f"Searching YouTube for query: {query}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            entries = info.get('entries', [])
            if entries is None:
                logger.info(f"No entries found for YouTube search: {query}")
                return []
            return entries[:SEARCH_RESULTS_LIMIT]
    except yt_dlp.utils.DownloadError as e:
        if 'Unsupported URL' in str(e) or 'unsupported url' in str(e).lower():
            logger.warning(f"Unsupported URL in search query: {query}")
            return 'unsupported_url'
        logger.error(f"DownloadError during YouTube search for {query}: {e}")
        return []
    except Exception as e:
        logger.critical(f"Unhandled error during YouTube search for {query}: {e}", exc_info=True)
        return []

async def handle_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Processes the user's search query and displays the results.
    """
    if not context.user_data.get(f'awaiting_search_query_{update.effective_user.id}'):
        logger.warning(f"User {update.effective_user.id} tried to search without awaiting query.")
        await update.message.reply_text("Please start a search with /search first.")
        return

    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    query_text = update.message.text.strip()
    logger.info(f"User {user_id} sent search query: '{query_text}'")

    await update.message.reply_text(texts["searching"])
    results = await search_youtube(query_text)

    if results == 'unsupported_url':
        await update.message.reply_text(texts["unsupported_url_in_search"])
        context.user_data.pop(f'awaiting_search_query_{user_id}', None)
        return

    if not isinstance(results, list):
        results = []

    if not results:
        await update.message.reply_text(texts["no_results"])
        logger.info(f"User {user_id} search returned no results for query: '{query_text}'")
        context.user_data.pop(f'awaiting_search_query_{user_id}', None)
        return

    keyboard = []
    for idx, entry in enumerate(results):
        title = entry.get('title', texts["no_results"])
        video_id = entry.get('id')
        keyboard.append([InlineKeyboardButton(f"{idx+1}. {title}", callback_data=f"searchsel_{user_id}_{video_id}")])

    await update.message.reply_text(
        texts["choose_track"],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data[f'search_results_{user_id}'] = {entry.get('id'): entry for entry in results}
    context.user_data.pop(f'awaiting_search_query_{user_id}', None)
    logger.info(f"User {user_id} received {len(results)} search results.")

def is_url(text):
    """
    Checks if a string is a YouTube or SoundCloud URL.
    """
    text = text.lower().strip()
    return (
        text.startswith("http://") or text.startswith("https://")
    ) and (
        "youtube.com/" in text or "youtu.be/" in text or "soundcloud.com/" in text
    )

async def smart_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Smart message handler: determines if the message is a URL or a search query.
    """

    # Проверка на наличие текста в сообщении
    if not update.message or not update.message.text:
        logger.warning("smart_message_handler: update.message или update.message.text отсутствует")
        return

    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    text = update.message.text.strip()
    logger.info(f"User {user_id} sent message: '{text}'")

    # Проверяем только активные загрузки текущего пользователя
    active_downloads = context.user_data.setdefault('active_downloads', [])
    # Очищаем завершенные загрузки
    active_downloads = [download for download in active_downloads if not download['task'].done()]
    context.user_data['active_downloads'] = active_downloads
    
    # Ограничиваем количество одновременных загрузок для одного пользователя
    if len(active_downloads) >= 3:  # Максимум 3 одновременные загрузки для одного пользователя
        await update.message.reply_text("У вас уже есть 3 активные загрузки. Пожалуйста, дождитесь их завершения.")
        return

    # Check subscription before any message processing.
    is_subscribed = await check_subscription(user_id, context.bot)
    if not is_subscribed:
        await update.message.reply_text(texts["not_subscribed"])
        return

    if is_url(text):
        await ask_download_type(update, context, text)
    else:
        # If not a URL and the bot is awaiting a search query (e.g., after /search).
        # Check if the bot is awaiting a search query from this user.
        if context.user_data.get(f'awaiting_search_query_{user_id}'):
            await handle_search_query(update, context)
        else:
            # If the user just wrote короткий текст (до 5 слов, ASCII), автоматически выполнить поиск с таймаутом
            if len(text.split()) <= 5 and text.isascii():
                import time
                global user_last_search_time
                now = time.time()
                search_cooldown = 5  # секунд
                last_search = user_last_search_time.get(user_id, 0)
                if now - last_search < search_cooldown:
                    wait_sec = int(search_cooldown - (now - last_search))
                    try:
                        await update.message.reply_text(f"⏳ Пожалуйста, подождите {wait_sec} сек. перед следующим поиском.")
                    except Exception:
                        pass
                    return
                user_last_search_time[user_id] = now

                logger.info(f"User {user_id} auto-search for: '{text}'")
                await update.message.reply_text(texts["searching"])
                results = await search_youtube(text)
                if not results or results == 'unsupported_url':
                    await update.message.reply_text(texts["no_results"])
                    return
                keyboard = []
                for idx, entry in enumerate(results):
                    title = entry.get('title', texts["no_results"])
                    video_id = entry.get('id')
                    keyboard.append([InlineKeyboardButton(f"{idx+1}. {title}", callback_data=f"searchsel_{user_id}_{video_id}")])
                await update.message.reply_text(
                    texts["choose_track"],
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                context.user_data[f'search_results_{user_id}'] = {entry.get('id'): entry for entry in results}
            else:
                await update.message.reply_text(texts["url_error_generic"])

async def cancel_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the request to cancel a download.
    """
    query = update.callback_query
    await query.answer() # Answer CallbackQuery to remove the 'clock' from the button.
    user_id = query.from_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    logger.info(f"User {user_id} requested download cancellation.")

    # Get active downloads from user_data instead of bot_data
    active_downloads = context.user_data.get('active_downloads', [])
    
    # Find the active download task
    active_download = None
    for download in active_downloads:
        if not download['task'].done():
            active_download = download
            break

    if not active_download:
        try:
            await query.edit_message_text(texts["already_cancelled_or_done"])
        except Exception as e:
            logger.debug(f"Could not edit message for already cancelled/done download: {e}")
            pass # Ignore error if message cannot be edited
        return

    # Cancel the task
    active_download['task'].cancel()
    try:
        await query.edit_message_text(texts["cancelling"])
    except Exception as e:
        logger.debug(f"Could not edit message to 'cancelling': {e}")
        pass # Ignore error if message cannot be edited
    
    # Remove cancelled task from active downloads
    active_downloads = [d for d in active_downloads if d != active_download]
    context.user_data['active_downloads'] = active_downloads
    
    logger.info(f"Download task cancelled for user {user_id}.")


async def copyright_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /copyright command and sends the copyright message.
    """
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    logger.info(f"User {user_id} issued /copyright command.")
    await update.message.reply_text(texts["copyright_command"])
    
    if len(query) < 3:
        # Показываем подсказку, если запрос слишком короткий
        await update.inline_query.answer(
            results=[
                InlineQueryResultArticle(
                    id="help",
                    title="Введите минимум 3 символа",
                    description="Например: The Weeknd - Starboy",
                    input_message_content=InputTextMessageContent(
                        message_text="Для поиска музыки введите минимум 3 символа"
                    )
                )
            ],
            cache_time=1
        )
        return
    
    logger.info(f"User {user_id} made inline query: {query}")
    
    # Показываем статус поиска
    await update.inline_query.answer(
        results=[
            InlineQueryResultArticle(
                id="searching",
                title="🔍 Поиск...",
                description=f"Ищем: {query}",
                input_message_content=InputTextMessageContent(
                    message_text="Выполняется поиск..."
                )
            )
        ],
        cache_time=1
    )
    
    try:
        results = await search_youtube(query)
        logger.info(f"Search results for {query}: {len(results) if results else 0} items")
        
        if not results or not isinstance(results, list):
            await update.inline_query.answer(
                results=[
                    InlineQueryResultArticle(
                        id="no_results",
                        title="Ничего не найдено",
                        description="Попробуйте другой запрос",
                        input_message_content=InputTextMessageContent(
                            message_text="По вашему запросу ничего не найдено"
                        )
                    )
                ],
                cache_time=300
            )
            return
        inline_results = []
        for idx, entry in enumerate(results[:5]):  # Limit to 5 results for better UX
            try:
                title = entry.get('title', 'Unknown Title')
                video_id = entry.get('id')
                thumbnails = entry.get('thumbnails', [])
                thumbnail = thumbnails[0]['url'] if thumbnails else None
                duration = entry.get('duration', 0)
                
                # Format duration
                duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Unknown"
                
                # Создаем более информативное описание
                channel = entry.get('channel', 'Unknown Artist')
                views = entry.get('view_count', 0)
                views_str = f"{views:,}" if views else "Unknown"
                
                description = f"👤 {channel}\n⏱ {duration_str}\n👁 {views_str} views"
                
                result = InlineQueryResultArticle(
                    id=video_id,
                    title=title,
                    description=description,
                    thumb_url=thumbnail,
                    input_message_content=InputTextMessageContent(
                        message_text=f"🎵 {title}\n👤 {channel}\n⏱ Duration: {duration_str}\n\n⏳ Preparing download..."
                    ),
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬇️ Download M4A", callback_data=f"idltype_audio_m4a_{user_id}_{video_id}")
                    ]])
                )
                inline_results.append(result)
                logger.info(f"Added result: {title} ({video_id})")
            except Exception as e:
                logger.error(f"Error processing search result: {e}")
                continue
        
        if not inline_results:
            # Если что-то пошло не так с обработкой результатов
            await update.inline_query.answer([
                InlineQueryResultArticle(
                    id="error",
                    title="Ошибка обработки результатов",
                    description="Пожалуйста, попробуйте другой запрос",
                    input_message_content=InputTextMessageContent(
                        message_text="Произошла ошибка при обработке результатов поиска"
                    )
                )
            ], cache_time=5)
            return
        
        logger.info(f"Sending {len(inline_results)} results for query: {query}")
        await update.inline_query.answer(inline_results, cache_time=300)
        
    except Exception as e:
        logger.error(f"Error in inline search: {e}")
        # Показываем ошибку пользователю
        await update.inline_query.answer([
            InlineQueryResultArticle(
                id="error",
                title="Произошла ошибка",
                description="Пожалуйста, попробуйте позже",
                input_message_content=InputTextMessageContent(
                    message_text="Произошла ошибка при поиске. Пожалуйста, попробуйте позже."
                )
            )
        ], cache_time=5)



def main():
    """
    Main function to run the bot.
    """
    load_user_langs() # Load user languages at startup.
    
    try:
        app = Application.builder().token(TOKEN).build()
        logger.info("Bot application built successfully.")
    except Exception as e:
        logger.critical(f"Failed to build bot application: {e}", exc_info=True)
        raise

    # Add command handlers.
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", choose_language))
    app.add_handler(CommandHandler("languages", choose_language))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("copyright", copyright_command))
    app.add_handler(CommandHandler("stats", stats_command))

    app.add_handler(MessageHandler(filters.Regex(f"^({'|'.join(LANG_CODES.keys())})$"), set_language))
    app.add_handler(CallbackQueryHandler(select_download_type_callback, pattern="^dltype_"))
    app.add_handler(CallbackQueryHandler(search_select_callback, pattern="^searchsel_"))
    app.add_handler(CallbackQueryHandler(cancel_download_callback, pattern="^cancel_"))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^({'|'.join(LANG_CODES.keys())})$"),
        smart_message_handler
    ))

    async def set_commands(_):
        logger.info("Setting bot commands.")
        await app.bot.set_my_commands([
            BotCommand("start", "Запуск и выбор языка / Start and choose language"),
            BotCommand("languages", "Сменить язык / Change language"),
            BotCommand("search", "Поиск музыки (YouTube/SoundCloud) / Search music (YouTube/SoundCloud)"),
            BotCommand("copyright", "Информация об авторских правах / Copyright info"),
            BotCommand("stats", "Ваша статистика / Your stats")
        ])
    app.post_init = set_commands
    
    logger.info("Starting bot polling.")
    try:
        app.run_polling()
    except Exception as e:
        logger.critical(f"Bot polling failed: {e}", exc_info=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /start command: prompts to choose a language and sends copyright warning.
    """
    logger.info(f"User {update.effective_user.id} issued /start command.")
    # Только меню выбора языка, без приветственного текста
    await choose_language(update, context)

if __name__ == '__main__':
    main()



# I have written additional lines of codes and "#" in the code for understanding and studying the code.

# Developed and made by BitSamurai.

# Thanks!
