import os
import logging
import asyncio
import tempfile
import shutil
import json
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv
import yt_dlp
from telegram.constants import ParseMode

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.critical("TELEGRAM_BOT_TOKEN не найден в переменных окружения.")
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения.")

cookies_path = os.getenv('COOKIES_PATH', 'youtube.com_cookies.txt')
ffmpeg_path_from_env = os.getenv('FFMPEG_PATH')
ffmpeg_path = ffmpeg_path_from_env if ffmpeg_path_from_env else '/usr/bin/ffmpeg'

FFMPEG_IS_AVAILABLE = os.path.exists(ffmpeg_path) and os.access(ffmpeg_path, os.X_OK)

logger.info("Текущий рабочий каталог: %s", os.getcwd())
if os.path.exists(cookies_path):
    logger.info("Cookies файл найден, размер: %d байт", os.path.getsize(cookies_path))
else:
    logger.warning("Файл cookies не найден по указанному пути: %s. Некоторые видео могут быть недоступны.", cookies_path)

if FFMPEG_IS_AVAILABLE:
    logger.info(f"FFmpeg найден и доступен по пути: {ffmpeg_path}.")
else:
    if ffmpeg_path_from_env:
        logger.error(f"FFmpeg НЕ найден или недоступен по пути, указанному в FFMPEG_PATH: {ffmpeg_path_from_env}.")
    else:
        logger.warning(f"FFmpeg НЕ найден или недоступен по пути по умолчанию: {ffmpeg_path}.")
    logger.warning("Бот попытается использовать ffmpeg из системного PATH, если он там есть. "
                   "Для полного функционала (MP3/WAV конвертация с водяным знаком) "
                   "рекомендуется установить FFmpeg и указать к нему путь через переменную окружения FFMPEG_PATH "
                   "или убедиться, что он в системном PATH и имеет права на выполнение.")


REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@ytdlpdeveloper")

# Лимит размера файла для отправки через Telegram (50 МБ)
TELEGRAM_FILE_SIZE_LIMIT_BYTES = 50 * 1024 * 1024
TELEGRAM_FILE_SIZE_LIMIT_TEXT = "50 МБ"

LANGUAGES = {
    "ru": {
        "start": (
            "Привет! Я бот для скачивания аудио с YouTube.\n\n"
            "Отправьте ссылку на YouTube, YT Music или SoundCloud (видео или трек), "
            "и я предложу вам варианты загрузки аудио.\n\n"
            f"Для работы с ботом, пожалуйста, подпишитесь на канал {REQUIRED_CHANNEL}.\n"
            "Приятного использования!"
        ),
        "choose_lang": "Выберите язык / Choose language:",
        "not_subscribed": f"Чтобы пользоваться ботом, подпишитесь на канал {REQUIRED_CHANNEL} и попробуйте снова.",
        "checking": "Проверяю ссылку...",
        "not_youtube": "Это не поддерживаемая ссылка. Отправьте корректную ссылку на YouTube или SoundCloud.",
        "choose_download_type": "Выберите формат аудио:",
        "audio_button_mp3": "🎧 Аудио (MP3)",
        "audio_button_sc": "🎧 SoundCloud (MP3)",
        "downloading_audio": "Скачиваю аудио... Подождите.",
        "download_progress": "Скачиваю: {percent} на скорости {speed}, осталось ~{eta}",
        "too_big": f"Файл слишком большой (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Попробуйте другое видео или трек.",
        "done_audio": "Готово! Аудио отправлено.",
        "error": "Что-то пошло не так. Проверьте ссылку или попробуйте позже!\n",
        "error_private_video": "Это приватное видео и не может быть скачано.",
        "error_video_unavailable": "Видео недоступно.",
        "sending_file": "Отправляю файл {index} из {total}...",
        "cancel_button": "Отмена",
        "cancelling": "Отменяю загрузку...",
        "cancelled": "Загрузка отменена.",
        "download_in_progress": "Другая загрузка уже в процессе. Пожалуйста, подождите или отмените её.",
        "already_cancelled_or_done": "Загрузка уже отменена или завершена.",
        "url_error_generic": "Не удалось обработать URL. Убедитесь, что это корректная ссылка на YouTube или SoundCloud."
    },
    "en": {
        "start": (
            "Hello! I am a bot for downloading audio from YouTube.\n\n"
            "Send a YouTube or YT Music link (video or playlist), "
            "and I will offer you audio download options.\n\n"
            f"To use the bot, please subscribe to the channel {REQUIRED_CHANNEL}.\n"
            "Enjoy!"
        ),
        "choose_lang": "Choose language:",
        "not_subscribed": f"To use the bot, please subscribe to {REQUIRED_CHANNEL} and try again.",
        "checking": "Checking link...",
        "not_youtube": "This is not a YouTube link. Please send a valid link.",
        "choose_download_type": "Choose audio format:",
        "audio_button_mp3": "🎧 Audio (MP3)",
        "audio_button_sc": "🎧 SoundCloud (MP3)",
        "downloading_audio": "Downloading audio... Please wait.",
        "download_progress": "Downloading: {percent} at {speed}, ETA ~{eta}",
        "too_big": f"File is too large (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Try another video or playlist.",
        "done_audio": "Done! Audio sent.",
        "error": "Something went wrong. Check the link or try again!\n",
        "error_private_video": "This is a private video and cannot be downloaded.",
        "error_video_unavailable": "Video unavailable.",
        "sending_file": "Sending file {index} of {total}...",
        "cancel_button": "Cancel",
        "cancelling": "Cancelling download...",
        "cancelled": "Download cancelled.",
        "download_in_progress": "Another download is already in progress. Please wait or cancel it.",
        "already_cancelled_or_done": "Download already cancelled or completed.",
        "url_error_generic": "Failed to process URL. Make sure it's a valid YouTube link."
    },
    "az": {
        "start": (
            "Salam! Mən YouTube-dan audio yükləmək üçün botam.\n\n"
            "YouTube və ya YT Music linki göndərin (video və ya playlist), "
            "və mən sizə audio yükləmə seçimlərini təqdim edəcəyəm.\n\n"
            f"Botdan istifadə etmək üçün zəhmət olmasa {REQUIRED_CHANNEL} kanalına abunə olun.\n"
            "Uğurlar!"
        ),
        "choose_lang": "Dil seçin:",
        "not_subscribed": f"Botdan istifadə etmək üçün {REQUIRED_CHANNEL} kanalına abunə olun və yenidən cəhd edin.",
        "checking": "Link yoxlanılır...",
        "not_youtube": "Bu YouTube linki deyil. Zəhmət olmasa düzgün link göndərin.",
        "choose_download_type": "Audio formatını seçin:",
        "audio_button_mp3": "🎧 Səs (MP3)",
        "audio_button_sc": "🎧 SoundCloud (MP3)",
        "downloading_audio": "Səs yüklənir... Zəhmət olmasa gözləyin.",
        "download_progress": "Yüklənir: {percent}, sürət {speed}, qalan vaxt ~{eta}",
        "too_big": f"Fayl çox böyükdür (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Başqa video və ya playlist yoxlayın.",
        "done_audio": "Hazırdır! Səs göndərildi.",
        "error": "Nəsə səhv oldu. Linki yoxlayın və ya yenidən cəhd edin!\n",
        "error_private_video": "Bu şəxsi videodur və yüklənə bilməz.",
        "error_video_unavailable": "Video mövcud deyil.",
        "sending_file": "Fayl {index} / {total} göndərilir...",
        "cancel_button": "Ləğv et",
        "cancelling": "Yükləmə ləğv edilir...",
        "cancelled": "Yükləmə ləğv edildi.",
        "download_in_progress": "Başqa bir yükləmə artıq davam edir. Zəhmət olmasa gözləyin və ya onu ləğv edin.",
        "already_cancelled_or_done": "Yükləmə artıq ləğv edilib və ya tamamlanıb.",
        "url_error_generic": "URL emal edilə bilmədi. Düzgün YouTube linki olduğundan əmin olun."
    },
    "tr": {
        "start": (
            "Merhaba! Ben YouTube'dan ses indiren bir botum.\n\n"
            "Bir YouTube veya YT Music bağlantısı gönderin (video veya çalma listesi), "
            "ve size ses indirme seçenekleri sunacağım.\n\n"
            f"Botu kullanmak için lütfen {REQUIRED_CHANNEL} kanalına abone olun.\n"
            "İyi eğlenceler!"
        ),
        "choose_lang": "Dil seçin:",
        "not_subscribed": f"Botu kullanmak için {REQUIRED_CHANNEL} kanalına abone olun ve tekrar deneyin.",
        "checking": "Bağlantı kontrol ediliyor...",
        "not_youtube": "Bu bir YouTube bağlantısı değil. Lütfen geçerli bir bağlantı gönderin.",
        "choose_download_type": "Ses formatını seçin:",
        "audio_button_mp3": "🎧 Ses (MP3)",
        "audio_button_sc": "🎧 SoundCloud (MP3)",
        "downloading_audio": "Ses indiriliyor... Lütfen bekleyin.",
        "download_progress": "İndiriliyor: {percent}, hız {speed}, ETA ~{eta}",
        "too_big": f"Dosya çok büyük (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Başka bir video veya çalma listesi deneyin.",
        "done_audio": "Hazır! Ses gönderildi.",
        "error": "Bir şeyler ters gitti. Bağlantıyı kontrol edin veya tekrar deneyin!\n",
        "error_private_video": "Bu özel bir video ve indirilemez.",
        "error_video_unavailable": "Video kullanılamıyor.",
        "sending_file": "{index} / {total} dosya gönderiliyor...",
        "cancel_button": "İptal",
        "cancelling": "İndirme iptal ediliyor...",
        "cancelled": "İndirme iptal edildi.",
        "download_in_progress": "Başka bir indirme zaten devam ediyor. Lütfen bekleyin veya iptal edin.",
        "already_cancelled_or_done": "İndirme zaten iptal edildi veya tamamlandı.",
        "url_error_generic": "URL işlenemedi. Geçerli bir YouTube bağlantısı olduğundan emin olun."
    },
    "es": {
        "start": (
            "¡Hola! Soy un bot para descargar audio de YouTube.\n\n"
            "Envía un enlace de YouTube o YT Music (video o lista de reproducción), "
            "y te ofreceré opciones de descarga de audio.\n\n"
            f"Para usar el bot, por favor suscríbete al canal {REQUIRED_CHANNEL}.\n"
            "¡Disfruta!"
        ),
        "choose_lang": "Elige idioma:",
        "not_subscribed": f"Para usar el bot, suscríbete al canal {REQUIRED_CHANNEL} y vuelve a intentarlo.",
        "checking": "Comprobando enlace...",
        "not_youtube": "Esto no es un enlace de YouTube. Por favor, envía un enlace válido.",
        "choose_download_type": "Elige el formato de audio:",
        "audio_button_mp3": "🎧 Audio (MP3)",
        "audio_button_sc": "🎧 SoundCloud (MP3)",
        "downloading_audio": "Descargando audio... Por favor espera.",
        "download_progress": "Descargando: {percent} a {speed}, ETA ~{eta}",
        "too_big": f"El archivo es demasiado grande (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Prueba con otro video o lista de reproducción.",
        "done_audio": "¡Listo! Audio enviado.",
        "error": "Algo salió mal. ¡Verifica el enlace o inténtalo de nuevo!\n",
        "error_private_video": "Este es un video privado y no se puede descargar.",
        "error_video_unavailable": "Video no disponible.",
        "sending_file": "Enviando archivo {index} de {total}...",
        "cancel_button": "Cancelar",
        "cancelling": "Cancelando descarga...",
        "cancelled": "Descarga cancelada.",
        "download_in_progress": "Ya hay otra descarga en curso. Por favor, espera o cancélela.",
        "already_cancelled_or_done": "La descarga ya ha sido cancelada o completada.",
        "url_error_generic": "No se pudo procesar la URL. Asegúrate de que sea un enlace de YouTube válido."
    },
    "uk": {
        "start": (
            "Привіт! Я бот для завантаження аудіо з YouTube.\n\n"
            "Надішліть посилання на YouTube або YT Music (відео чи плейлист), "
            "і я запропоную вам варіанти завантаження аудіо.\n\n"
            f"Щоб користуватися ботом, будь ласка, підпишіться на канал {REQUIRED_CHANNEL}.\n"
            "Гарного користування!"
        ),
        "choose_lang": "Оберіть мову:",
        "not_subscribed": f"Щоб користуватися ботом, підпишіться на канал {REQUIRED_CHANNEL} і спробуйте ще раз.",
        "checking": "Перевіряю посилання...",
        "not_youtube": "Це не посилання на YouTube. Надішліть коректне посилання.",
        "choose_download_type": "Оберіть формат аудіо:",
        "audio_button_mp3": "🎧 Аудіо (MP3)",
        "audio_button_sc": "🎧 SoundCloud (MP3)",
        "downloading_audio": "Завантажую аудіо... Зачекайте.",
        "download_progress": "Завантаження: {percent} зі швидкістю {speed}, залишилось ~{eta}",
        "too_big": f"Файл занадто великий (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Спробуйте інше відео або трек.",
        "done_audio": "Готово! Аудіо надіслано.",
        "error": "Щось пішло не так. Перевірте посилання або спробуйте ще раз!\n",
        "error_private_video": "Це приватне відео і не може бути завантажене.",
        "error_video_unavailable": "Відео недоступне.",
        "sending_file": "Надсилаю файл {index} з {total}...",
        "cancel_button": "Скасувати",
        "cancelling": "Скасовую завантаження...",
        "cancelled": "Завантаження скасовано.",
        "download_in_progress": "Інше завантаження вже триває. Будь ласка, зачекайте або скасуйте його.",
        "already_cancelled_or_done": "Завантаження вже скасовано або завершено.",
        "url_error_generic": "Не вдалося обробити URL. Переконайтеся, що це дійсне посилання на YouTube."
    },
    "ar": {
        "start": (
            "مرحبًا! أنا بوت لتحميل الصوت من يوتيوب.\n\n"
            "أرسل رابط YouTube أو YT Music (فيديو أو قائمة تشغيل)، "
            "وسأقدم لك خيارات تحميل الصوت.\n\n"
            f"لاستخدام البوت، يرجى الاشتراك في قناة {REQUIRED_CHANNEL}.\n"
            "استخدام ممتع!"
        ),
        "choose_lang": "اختر اللغة:",
        "not_subscribed": f"لاستخدام البوت، يرجى الاشتراك في قناة {REQUIRED_CHANNEL} ثم المحاولة مرة أخرى.",
        "checking": "جارٍ التحقق من الرابط...",
        "not_youtube": "هذا ليس رابط يوتيوب. يرجى إرسال رابط صحيح.",
        "choose_download_type": "اختر صيغة الصوت:",
        "audio_button_mp3": "🎧 صوت (MP3)",
        "audio_button_sc": "🎧 SoundCloud (MP3)",
        "downloading_audio": "جارٍ تحميل الصوت... يرجى الانتظار.",
        "download_progress": "جار التحميل: {percent} بسرعة {speed}، الوقت المتبقي ~{eta}",
        "too_big": f"الملف كبير جدًا (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). جرب فيديو أو قائمة تشغيل أخرى.",
        "done_audio": "تم! تم إرسال الصوت.",
        "error": "حدث خطأ ما. تحقق من الرابط أو حاول مرة أخرى!\n",
        "error_private_video": "هذا الفيديو خاص ولا يمكن تحميله.",
        "error_video_unavailable": "الفيديو غير متوفر.",
        "sending_file": "جاري إرسال الملف {index} من {total}...",
        "cancel_button": "إلغاء",
        "cancelling": "جاري إلغاء التنزيل...",
        "cancelled": "تم إلغاء التنزيل.",
        "download_in_progress": "هناك تنزيل آخر قيد التقدم بالفعل. يرجى الانتظار أو إلغائه.",
        "already_cancelled_or_done": "تم إلغاء التنزيل أو اكتماله بالفعل.",
        "url_error_generic": "فشل في معالجة الرابط. تأكد من أنه رابط يوتيوب صالح."
    }
}
user_langs = {}
USER_LANGS_FILE = "user_languages.json"

def load_user_langs():
    global user_langs
    if os.path.exists(USER_LANGS_FILE):
        with open(USER_LANGS_FILE, 'r', encoding='utf-8') as f:
            try:
                loaded_langs = json.load(f)
                user_langs = {int(k): v for k, v in loaded_langs.items()}
            except json.JSONDecodeError:
                logger.error(f"Could not decode {USER_LANGS_FILE}, starting with empty langs.")
                user_langs = {}
    else:
        user_langs = {}

def save_user_langs():
    with open(USER_LANGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_langs, f)

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
    "Русский": "ru", "English": "en", "Español": "es",
    "Azərbaycan dili": "az", "Türkçe": "tr", "Українська": "uk",
    "العربية": "ar"
}

async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        LANGUAGES["ru"]["choose_lang"],
        reply_markup=LANG_KEYBOARD
    )

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang_name = update.message.text
    lang_code = LANG_CODES.get(lang_name)
    user_id = update.effective_user.id
    if lang_code:
        user_langs[user_id] = lang_code
        save_user_langs()
        await update.message.reply_text(LANGUAGES[lang_code]["start"])
    else:
        await update.message.reply_text(
            "Пожалуйста, выберите язык с клавиатуры / Please choose a language from the keyboard."
        )

def get_user_lang(user_id):
    return user_langs.get(user_id, "ru")

async def check_subscription(user_id: int, bot) -> bool:
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.warning(f"Не удалось проверить подписку для {user_id} в {REQUIRED_CHANNEL}: {e}")
        return False

async def get_url_info(url: str) -> dict:
    cmd = [
        "yt-dlp",
        "--no-check-certificate",
        "--flat-playlist",
        "--dump-single-json",
        url
    ]
    if os.path.exists(cookies_path):
        cmd.insert(1, cookies_path)
        cmd.insert(1, "--cookies")

    logger.info(f"Получение информации о URL: {' '.join(cmd)}")
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            error_output = stderr.decode('utf-8', 'ignore')
            logger.error(f"yt-dlp info error (code {proc.returncode}): {error_output}")
            if "private video" in error_output.lower():
                raise Exception("private_video_error")
            if "video unavailable" in error_output.lower():
                raise Exception("video_unavailable_error")
            raise Exception(f"Failed to get URL info: {error_output[:500]}")
        return json.loads(stdout.decode('utf-8', 'ignore'))
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error for URL info {url}: {e}\nStdout: {stdout.decode('utf-8', 'ignore')}")
        raise Exception("Failed to parse URL info.")
    except Exception as e:
        logger.error(f"Error getting URL info for {url}: {e}")
        raise

def blocking_yt_dlp_download(ydl_opts, url_to_download):
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url_to_download])
        return True
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp DownloadError: {e}")
        error_message = str(e)
        if "private video" in error_message.lower() or "login required" in error_message.lower():
            raise Exception("private_video_error")
        if "video unavailable" in error_message.lower():
            raise Exception("video_unavailable_error")
        if "ffmpeg is not installed" in error_message.lower() or "ffmpeg command not found" in error_message.lower():
            logger.error("FFmpeg не найден yt-dlp во время выполнения download().")
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка в blocking_yt_dlp_download: {e}")
        raise

async def ask_download_type(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    context.user_data[f'url_for_download_{user_id}'] = url
    if "soundcloud.com/" in url.lower():
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(texts["audio_button_sc"], callback_data=f"dltype_audio_sc_{user_id}")]
        ])
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(texts["audio_button_mp3"], callback_data=f"dltype_audio_mp3_{user_id}")]
        ])
    await update.message.reply_text(texts["choose_download_type"], reply_markup=keyboard)

def is_soundcloud_url(url):
    return "soundcloud.com/" in url.lower()

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, texts: dict, user_id: int, download_type: str):
    if not update.message:
        try:
            await context.bot.send_message(chat_id=user_id, text=texts["error"] + " (внутренняя ошибка: не найден чат для ответа)")
        except Exception:
            pass
        return
    chat_id = update.message.chat_id
    temp_dir = None
    status_message = None
    active_downloads = context.bot_data.setdefault('active_downloads', {})
    loop = asyncio.get_running_loop()
    cancel_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(texts["cancel_button"], callback_data=f"cancel_{user_id}")]])
    async def update_status_message_async(text_to_update, show_cancel_button=True):
        nonlocal status_message
        if status_message:
            try:
                current_keyboard = cancel_keyboard if show_cancel_button else None
                await status_message.edit_text(text_to_update, reply_markup=current_keyboard)
            except Exception:
                pass
    def progress_hook(d):
        if d['status'] == 'downloading':
            percent_str = d.get('_percent_str', 'N/A').strip()
            speed_str = d.get('_speed_str', 'N/A').strip()
            eta_str = d.get('_eta_str', 'N/A').strip()
            progress_text = texts["download_progress"].format(percent=percent_str, speed=speed_str, eta=eta_str)
            asyncio.run_coroutine_threadsafe(update_status_message_async(progress_text), loop)
    try:
        status_message = await context.bot.send_message(chat_id=chat_id, text=texts["downloading_audio"], reply_markup=cancel_keyboard)
        temp_dir = tempfile.mkdtemp()
        if download_type == "audio_mp3":
            ydl_opts = {
                'outtmpl': os.path.join(temp_dir, '%(title).140B - Made by @ytdlpload_bot [%(id)s].%(ext)s'),
                'format': 'bestaudio/best',
                'cookiefile': cookies_path if os.path.exists(cookies_path) else None,
                'progress_hooks': [progress_hook],
                'nocheckcertificate': True,
                'quiet': True,
                'no_warnings': True,
                'ffmpeg_location': ffmpeg_path if FFMPEG_IS_AVAILABLE else None,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192K',
                }],
                'postprocessor_args': {
                    'FFmpegExtractAudio': ['-metadata', 'comment=Made by @ytdlpload_bot']
                },
                'verbose': True
            }
        elif download_type == "audio_sc":
            ydl_opts = {
                'outtmpl': os.path.join(temp_dir, '%(title).140B - Made by @ytdlpload_bot [%(id)s].%(ext)s'),
                'format': 'bestaudio/best',
                'progress_hooks': [progress_hook],
                'nocheckcertificate': True,
                'quiet': True,
                'no_warnings': True,
                'ffmpeg_location': ffmpeg_path if FFMPEG_IS_AVAILABLE else None,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192K',
                }],
                'postprocessor_args': {
                    'FFmpegExtractAudio': ['-metadata', 'comment=Made by @ytdlpload_bot']
                },
                'verbose': True
            }
        else:
            await update_status_message_async(texts["error"] + " (неизвестный тип)", show_cancel_button=False)
            return
        ydl_opts = {k: v for k, v in ydl_opts.items() if v is not None}
        await asyncio.to_thread(blocking_yt_dlp_download, ydl_opts, url)
        downloaded_files_info = []
        all_temp_files = os.listdir(temp_dir)
        for file_name in all_temp_files:
            file_path = os.path.join(temp_dir, file_name)
            file_ext_lower = os.path.splitext(file_name)[1].lower()
            base_title = os.path.splitext(file_name.split(" [")[0])[0]
            if file_ext_lower in [".mp3", ".m4a", ".webm", ".ogg", ".opus", ".aac"]:
                downloaded_files_info.append((file_path, base_title))
        if not downloaded_files_info:
            await update_status_message_async(texts["error"] + " (файл не найден)", show_cancel_button=False)
            return
        total_files = len(downloaded_files_info)
        for i, (file_to_send, title_str) in enumerate(downloaded_files_info):
            await update_status_message_async(texts["sending_file"].format(index=i+1, total=total_files))
            file_size = os.path.getsize(file_to_send)
            if file_size > TELEGRAM_FILE_SIZE_LIMIT_BYTES:
                await context.bot.send_message(chat_id=chat_id, text=f"{texts['too_big']} ({os.path.basename(file_to_send)})")
                continue
            try:
                with open(file_to_send, 'rb') as f_send:
                    await context.bot.send_audio(
                        chat_id=chat_id, audio=f_send, title=title_str,
                        filename=os.path.basename(file_to_send)
                    )
            except Exception as send_error:
                await context.bot.send_message(chat_id=chat_id, text=f"{texts['error']} (Ошибка отправки файла {os.path.basename(file_to_send)})")
        await update_status_message_async(texts["done_audio"], show_cancel_button=False)
    except asyncio.CancelledError:
        if status_message:
            await update_status_message_async(texts["cancelled"], show_cancel_button=False)
        else:
            await context.bot.send_message(chat_id=chat_id, text=texts["cancelled"])
    except Exception as e:
        if status_message:
            await update_status_message_async(texts["error"] + str(e), show_cancel_button=False)
        else:
            await context.bot.send_message(chat_id=chat_id, text=texts["error"] + str(e))
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        if user_id in active_downloads:
            del active_downloads[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await choose_language(update, context)

async def process_link_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    active_downloads = context.bot_data.setdefault('active_downloads', {})
    if user_id in active_downloads and active_downloads[user_id].get('task') and not active_downloads[user_id]['task'].done():
        await update.message.reply_text(texts["download_in_progress"])
        return
    is_subscribed = await check_subscription(user_id, context.bot)
    if not is_subscribed:
        await update.message.reply_text(texts["not_subscribed"])
        return
    url = update.message.text.strip()
    url_lower = url.lower()
    if not ("youtube.com/" in url_lower or "youtu.be/" in url_lower or "soundcloud.com/" in url_lower):
        await update.message.reply_text(texts["not_youtube"])
        return
    await ask_download_type(update, context, url)
async def select_download_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        parts = query.data.split("_")
        if len(parts) != 4 or parts[0] != "dltype" or (parts[1] != "audio" and parts[1] != "audio"): 
            raise ValueError("Некорректный формат callback_data для аудио")
        specific_format = parts[2]
        user_id_from_callback = int(parts[3])
        if specific_format == "mp3":
            download_type_for_handler = "audio_mp3"
        elif specific_format == "sc":
            download_type_for_handler = "audio_sc"
        else:
            raise ValueError("Неизвестный тип загрузки")
    except (IndexError, ValueError) as e:
        await query.edit_message_text("Ошибка выбора. Попробуйте снова отправить ссылку.")
        return
    requesting_user_id = query.from_user.id
    if user_id_from_callback != requesting_user_id:
        await query.edit_message_text("Эта кнопка не для вас.")
        return
    lang = get_user_lang(requesting_user_id)
    texts = LANGUAGES[lang]
    url_to_download = context.user_data.pop(f'url_for_download_{requesting_user_id}', None)
    if not url_to_download:
        await query.edit_message_text(texts["error"] + " (URL не найден, попробуйте снова)")
        return
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    task = asyncio.create_task(handle_download(query, context, url_to_download, texts, requesting_user_id, download_type_for_handler))
    active_downloads = context.bot_data.setdefault('active_downloads', {})
    active_downloads[requesting_user_id] = {'task': task}

async def cancel_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        user_id_to_cancel = int(query.data.split("_")[1])
    except (IndexError, ValueError):
        logger.error(f"Не удалось извлечь user_id из callback_data для отмены: {query.data}")
        return
        
    requesting_user_id = query.from_user.id
    lang = get_user_lang(requesting_user_id)
    texts = LANGUAGES[lang]

    if user_id_to_cancel != requesting_user_id:
        logger.warning(f"User {requesting_user_id} попытался отменить загрузку для user {user_id_to_cancel}.")
        return

    active_downloads = context.bot_data.get('active_downloads', {})
    task_info = active_downloads.get(user_id_to_cancel)

    if task_info and task_info.get('task') and not task_info['task'].done():
        task_info['task'].cancel()
        try:
            await query.edit_message_text(text=texts["cancelling"], reply_markup=None)
        except Exception as e:
            logger.info(f"Не удалось изменить сообщение на 'cancelling' (кнопка отмены) для user {user_id_to_cancel}: {e}")
    else:
        try:
            await query.edit_message_text(text=texts["already_cancelled_or_done"], reply_markup=None)
        except Exception as e:
            logger.info(f"Не удалось изменить сообщение на 'already_cancelled_or_done' (кнопка отмены) для user {user_id_to_cancel}: {e}")

async def search_youtube(query: str):
    """Ищет музыку на YouTube и возвращает список результатов."""
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'extract_flat': 'in_playlist',
        'nocheckcertificate': True,
        'default_search': 'ytsearch',
        'forcejson': True,
        'noplaylist': True,
        'dump_single_json': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            entries = info.get('entries', [])
            return entries[:SEARCH_RESULTS_LIMIT]
    except Exception as e:
        logger.error(f"Ошибка поиска на YouTube: {e}")
        return []

SEARCH_RESULTS_LIMIT = 6

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    await update.message.reply_text(
        "Введите название трека или исполнителя для поиска на YouTube:"
    )
    context.user_data['awaiting_search_query'] = True

async def handle_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    query = update.message.text.strip()
    await update.message.reply_text("Ищу музыку...")

    results = await asyncio.to_thread(search_youtube, query)
    if not results:
        await update.message.reply_text("Ничего не найдено. Попробуйте другой запрос.")
        context.user_data.pop('awaiting_search_query', None)
        return

    keyboard = []
    for idx, entry in enumerate(results):
        title = entry.get('title', 'Без названия')
        video_id = entry.get('id')
        url = f"https://youtu.be/{video_id}"
        keyboard.append([InlineKeyboardButton(f"{idx+1}. {title}", callback_data=f"searchsel_{video_id}")])

    await update.message.reply_text(
        "Выберите трек для скачивания MP3:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data['search_results'] = {entry.get('id'): entry for entry in results}
    context.user_data.pop('awaiting_search_query', None)

async def search_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]

    try:
        video_id = query.data.split("_")[1]
    except Exception:
        await query.edit_message_text("Ошибка выбора трека.")
        return

    url = f"https://youtu.be/{video_id}"
    await query.edit_message_text("Скачиваю выбранный трек в MP3...")

    
    task = asyncio.create_task(handle_download(query, context, url, texts, user_id, "audio_mp3"))
    active_downloads = context.bot_data.setdefault('active_downloads', {})
    active_downloads[user_id] = {'task': task}

def main():
    load_user_langs()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", choose_language))
    app.add_handler(CommandHandler("search", search_command))  
    app.add_handler(MessageHandler(filters.Regex(f"^({'|'.join(LANG_CODES.keys())})$"), set_language))
    
    app.add_handler(CallbackQueryHandler(select_download_type_callback, pattern="^dltype_"))
    app.add_handler(CallbackQueryHandler(cancel_download_callback, pattern="^cancel_"))
    app.add_handler(CallbackQueryHandler(search_select_callback, pattern="^searchsel_"))  
    
    
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^({'|'.join(LANG_CODES.keys())})$"),
        lambda update, context: handle_search_query(update, context)
        if context.user_data.get('awaiting_search_query')
        else process_link_message(update, context)
    ))
    
    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()
