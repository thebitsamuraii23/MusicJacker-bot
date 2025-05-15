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
            "Отправьте ссылку на YouTube или YT Music (видео или плейлист), "
            "и я предложу вам варианты загрузки аудио.\n\n"
            f"Для работы с ботом, пожалуйста, подпишитесь на канал {REQUIRED_CHANNEL}.\n"
            "Приятного использования!"
        ),
        "choose_lang": "Выберите язык / Choose language:",
        "not_subscribed": f"Чтобы пользоваться ботом, подпишитесь на канал {REQUIRED_CHANNEL} и попробуйте снова.",
        "checking": "Проверяю ссылку...",
        "not_youtube": "Это не ссылка на YouTube. Отправьте корректную ссылку.",
        "choose_download_type": "Выберите формат аудио:",
        "audio_button_mp3": "🎧 Аудио (MP3)",
        "audio_button_wav": "🎧 Аудио (WAV)",
        "downloading_audio": "Скачиваю аудио... Подождите.",
        "download_progress": "Скачиваю: {percent} на скорости {speed}, осталось ~{eta}",
        "too_big": f"Файл слишком большой (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Попробуйте другое видео или плейлист.",
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
        "url_error_generic": "Не удалось обработать URL. Убедитесь, что это корректная ссылка на YouTube."
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
        "audio_button_wav": "🎧 Audio (WAV)",
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
        "audio_button_wav": "🎧 Səs (WAV)",
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
        "audio_button_wav": "🎧 Ses (WAV)",
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
        "audio_button_wav": "🎧 Audio (WAV)",
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
        "audio_button_wav": "🎧 Аудіо (WAV)",
        "downloading_audio": "Завантажую аудіо... Зачекайте.",
        "download_progress": "Завантаження: {percent} зі швидкістю {speed}, залишилось ~{eta}",
        "too_big": f"Файл занадто великий (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Спробуйте інше відео або плейлист.",
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
        "audio_button_wav": "🎧 صوت (WAV)",
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

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, texts: dict, user_id: int, download_type: str):
    if not update.message:
        logger.error(f"Объект message отсутствует в CallbackQuery для user {user_id} при вызове handle_download")
        try:
            await context.bot.send_message(chat_id=user_id, text=texts["error"] + " (внутренняя ошибка: не найден чат для ответа)")
        except Exception as send_err:
            logger.error(f"Не удалось отправить сообщение об ошибке пользователю {user_id}: {send_err}")
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
            except Exception as edit_err:
                logger.debug(f"Не удалось обновить статусное сообщение для {user_id} (возможно, оно уже изменено/удалено): {edit_err}")

    def progress_hook(d):
        if d['status'] == 'downloading':
            percent_str = d.get('_percent_str', 'N/A').strip()
            speed_str = d.get('_speed_str', 'N/A').strip()
            eta_str = d.get('_eta_str', 'N/A').strip()
            progress_text = texts["download_progress"].format(percent=percent_str, speed=speed_str, eta=eta_str)
            asyncio.run_coroutine_threadsafe(update_status_message_async(progress_text), loop)
        elif d['status'] == 'finished':
            logger.info(f"yt-dlp hook: Загрузка файла {d.get('filename')} завершена для user {user_id}.")
        elif d['status'] == 'error':
            logger.error(f"yt-dlp hook: Ошибка во время загрузки для user {user_id}.")

    try:
        initial_download_message = texts["downloading_audio"] # Теперь всегда аудио
        status_message = await context.bot.send_message(chat_id=chat_id, text=initial_download_message, reply_markup=cancel_keyboard)

        temp_dir = tempfile.mkdtemp()
        logger.info(f"Создана временная директория: {temp_dir} для user {user_id}, тип: {download_type}")

        url_info = await get_url_info(url)
        is_playlist = url_info.get('_type') == 'playlist'
        
        watermark_text_for_filename = "Made by @ytdlpload_bot"
        base_output_template = f"%(title).140B - {watermark_text_for_filename} [%(id)s].%(ext)s" # Для аудио

        if is_playlist:
            output_template = os.path.join(temp_dir, "%(playlist_index)02d - " + base_output_template)
        else:
            output_template = os.path.join(temp_dir, base_output_template)

        ydl_opts = {
            'outtmpl': output_template,
            'noplaylist': not is_playlist,
            'cookiefile': cookies_path if os.path.exists(cookies_path) else None,
            'progress_hooks': [progress_hook],
            'nocheckcertificate': True,
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': ffmpeg_path if FFMPEG_IS_AVAILABLE else None,
        }
        
        primary_expected_extension = "" 

        if download_type == "audio_mp3":
            if FFMPEG_IS_AVAILABLE:
                logger.info(f"FFmpeg доступен для user {user_id}. Аудио будет конвертировано в MP3 с водяным знаком в метаданных.")
                metadata_watermark_text = "Made by @ytdlpload_bot" # Этот водяной знак для метаданных
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192K',
                }]
                ydl_opts['postprocessor_args'] = { 
                    'FFmpegExtractAudio': ['-metadata', f'comment={metadata_watermark_text}']
                }
                ydl_opts['verbose'] = True
                primary_expected_extension = ".mp3"
            else:
                logger.warning(f"FFmpeg не найден для user {user_id}. Аудио (MP3) будет скачано в лучшем доступном формате, без водяного знака в метаданных.")
                ydl_opts['format'] = 'bestaudio/best'
                primary_expected_extension = ".m4a (или другой аудио формат)"
            done_message = texts["done_audio"]
        
        elif download_type == "audio_wav":
            if FFMPEG_IS_AVAILABLE:
                logger.info(f"FFmpeg доступен для user {user_id}. Аудио будет конвертировано в WAV с водяным знаком в метаданных.")
                metadata_watermark_text = "Made by @ytdlpload_bot" # Этот водяной знак для метаданных
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                }]
                ydl_opts['postprocessor_args'] = {
                     'FFmpegExtractAudio': ['-metadata', f'comment={metadata_watermark_text}']
                }
                ydl_opts['verbose'] = True
                primary_expected_extension = ".wav"
            else:
                logger.warning(f"FFmpeg не найден для user {user_id}. Аудио (WAV) будет скачано в лучшем доступном формате, без водяного знака в метаданных.")
                ydl_opts['format'] = 'bestaudio/best'
                primary_expected_extension = ".m4a (или другой аудио формат)"
            done_message = texts["done_audio"]
        else: # Если вдруг пришел неизвестный тип, хотя мы его убрали из кнопок
            logger.error(f"Получен неизвестный download_type: {download_type} для user {user_id}")
            raise ValueError(f"Неизвестный тип загрузки: {download_type}")

        ydl_opts = {k: v for k, v in ydl_opts.items() if v is not None}
        if 'postprocessors' in ydl_opts and not ydl_opts['postprocessors']:
            del ydl_opts['postprocessors']
        if 'postprocessor_args' in ydl_opts and not ydl_opts['postprocessor_args']:
            del ydl_opts['postprocessor_args']

        logger.info(f"Запуск yt-dlp (библиотека) для user {user_id}, тип: {download_type}, URL: {url}")
        logger.debug(f"yt-dlp опции: {ydl_opts}")

        await asyncio.to_thread(blocking_yt_dlp_download, ydl_opts, url)
        
        downloaded_files_info = []
        all_temp_files = os.listdir(temp_dir)
        logger.info(f"Файлы во временной директории ({temp_dir}) ПОСЛЕ yt-dlp для user {user_id}: {all_temp_files}")
        
        if is_playlist:
            try:
                all_temp_files.sort(key=lambda x: int(x.split(' - ')[0]) if ' - ' in x and x.split(' - ')[0].isdigit() else float('inf'))
            except ValueError:
                all_temp_files.sort()
        
        found_primary = False
        if FFMPEG_IS_AVAILABLE and (download_type == "audio_mp3" or download_type == "audio_wav"):
            expected_ext_for_ffmpeg_audio = ".mp3" if download_type == "audio_mp3" else ".wav"
            for file_name in all_temp_files:
                file_path = os.path.join(temp_dir, file_name)
                if os.path.splitext(file_name)[1].lower() == expected_ext_for_ffmpeg_audio:
                    base_title = file_name
                    if is_playlist and " - " in base_title: base_title = base_title.split(" - ", 1)[1]
                    base_title = os.path.splitext(base_title.split(" [")[0])[0] 
                    downloaded_files_info.append((file_path, base_title))
                    found_primary = True
                    logger.info(f"Найден основной аудио файл {expected_ext_for_ffmpeg_audio}: '{file_name}' для user {user_id}")
        
        if not found_primary: # Если основной формат не найден или ffmpeg не был доступен
            logger.info(f"Основной формат ('{primary_expected_extension}') не найден или не ожидался для user {user_id}, ищем альтернативные аудио форматы.")
            for file_name in all_temp_files:
                file_path = os.path.join(temp_dir, file_name)
                file_ext_lower = os.path.splitext(file_name)[1].lower()
                logger.info(f"Проверка альтернативного файла для user {user_id}: '{file_name}', расширение: '{file_ext_lower}'")

                base_title = file_name
                if is_playlist and " - " in base_title:
                    base_title = base_title.split(" - ", 1)[1]
                base_title = os.path.splitext(base_title.split(" [")[0])[0]

                if file_ext_lower in [".m4a", ".webm", ".ogg", ".opus", ".aac", ".mp3", ".wav"]: # Ищем любые аудио
                    logger.info(f"Найден альтернативный аудио файл: '{file_name}' для user {user_id}")
                    if not any(f[0] == file_path for f in downloaded_files_info):
                         downloaded_files_info.append((file_path, base_title))

        if not downloaded_files_info:
            error_detail = f"Ожидалось что-то вроде: {primary_expected_extension}. Найдено во временной папке: {all_temp_files if all_temp_files else 'пусто'}."
            logger.error(f"Не найдены подходящие файлы для user {user_id}. {error_detail}")
            raise Exception(f"Не найдены подходящие файлы после скачивания. {error_detail}")

        total_files = len(downloaded_files_info)
        for i, (file_to_send, title_str) in enumerate(downloaded_files_info):
            await update_status_message_async(texts["sending_file"].format(index=i+1, total=total_files))

            file_size = os.path.getsize(file_to_send)
            if file_size > TELEGRAM_FILE_SIZE_LIMIT_BYTES: 
                await context.bot.send_message(chat_id=chat_id, text=f"{texts['too_big']} ({os.path.basename(file_to_send)})")
                continue
            try:
                with open(file_to_send, 'rb') as f_send:
                    await context.bot.send_audio( # Теперь всегда отправляем как аудио
                        chat_id=chat_id, audio=f_send, title=title_str,
                        filename=os.path.basename(file_to_send)
                    )
            except Exception as send_error:
                logger.error(f"Ошибка отправки файла {file_to_send} для user {user_id}: {send_error}")
                if "Request Entity Too Large" in str(send_error):
                    await context.bot.send_message(chat_id=chat_id, text=f"{texts['too_big']} (Файл {os.path.basename(file_to_send)} превысил лимит Telegram API)")
                else:
                    await context.bot.send_message(chat_id=chat_id, text=f"{texts['error']} (Ошибка отправки файла {os.path.basename(file_to_send)})")
        
        await update_status_message_async(texts["done_audio"], show_cancel_button=False) # Теперь всегда done_audio

    except asyncio.CancelledError:
        logger.info(f"Задача загрузки для user {user_id} (URL: {url}, Тип: {download_type}) была отменена.")
        if status_message:
            await update_status_message_async(texts["cancelled"], show_cancel_button=False)
        else:
            await context.bot.send_message(chat_id=chat_id, text=texts["cancelled"])
            
    except Exception as e:
        error_message_key = str(e)
        specific_error_text = ""
        if "Найдено во временной папке:" in error_message_key:
            specific_error_text = error_message_key
        elif error_message_key == "private_video_error":
            specific_error_text = texts.get("error_private_video", "Это приватное видео и не может быть скачано.")
        elif error_message_key == "video_unavailable_error":
            specific_error_text = texts.get("error_video_unavailable", "Видео недоступно.")
        
        final_error_text = specific_error_text if specific_error_text else (texts["error"] + str(e))
        logger.error(f"Ошибка при скачивании для user {user_id} (URL: {url}, Тип: {download_type}): {e}", exc_info=True)

        if status_message:
            await update_status_message_async(final_error_text, show_cancel_button=False)
        else:
            await context.bot.send_message(chat_id=chat_id, text=final_error_text)
            
    finally:
        if temp_dir and os.path.exists(temp_dir):
            logger.info(f"Удаление временной директории: {temp_dir} для user {user_id}")
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        if user_id in active_downloads:
            del active_downloads[user_id]
            logger.info(f"Удалена задача для user {user_id} из active_downloads.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await choose_language(update, context)

async def ask_download_type(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]

    context.user_data[f'url_for_download_{user_id}'] = url

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(texts["audio_button_mp3"], callback_data=f"dltype_audio_mp3_{user_id}"),
            InlineKeyboardButton(texts["audio_button_wav"], callback_data=f"dltype_audio_wav_{user_id}")
        ]
        
    ])
    await update.message.reply_text(texts["choose_download_type"], reply_markup=keyboard)

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
   
    if not ("youtube.com/" in url_lower or "youtu.be/" in url_lower):
        await update.message.reply_text(texts["not_youtube"])
        return
    
    logger.info(f"User {user_id} отправил URL: {url}. Предлагаем выбор типа загрузки аудио.")
    await ask_download_type(update, context, url)

async def select_download_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        parts = query.data.split("_")
     
        if len(parts) != 4 or parts[0] != "dltype" or parts[1] != "audio":
            raise ValueError("Некорректный формат callback_data для аудио")
        
        specific_format = parts[2]
        user_id_from_callback = int(parts[3])
        download_type_for_handler = f"audio_{specific_format}"

    except (IndexError, ValueError) as e:
        logger.error(f"Ошибка разбора callback_data для типа загрузки: {query.data}, {e}")
        await query.edit_message_text("Ошибка выбора. Попробуйте снова отправить ссылку.")
        return

    requesting_user_id = query.from_user.id
    if user_id_from_callback != requesting_user_id:
        logger.warning(f"User {requesting_user_id} нажал кнопку, предназначенную для {user_id_from_callback}.")
        await query.edit_message_text("Эта кнопка не для вас.")
        return

    lang = get_user_lang(requesting_user_id)
    texts = LANGUAGES[lang]

    url_to_download = context.user_data.pop(f'url_for_download_{requesting_user_id}', None)

    if not url_to_download:
        logger.error(f"URL для загрузки не найден в user_data для user {requesting_user_id}")
        await query.edit_message_text(texts["error"] + " (URL не найден, попробуйте снова)")
        return

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception as e:
        logger.warning(f"Не удалось удалить клавиатуру выбора типа: {e}")

    logger.info(f"User {requesting_user_id} выбрал загрузку '{download_type_for_handler}' для URL: {url_to_download}")
    
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

def main():
    load_user_langs()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", choose_language))
    app.add_handler(MessageHandler(filters.Regex(f"^({'|'.join(LANG_CODES.keys())})$"), set_language))
    
    app.add_handler(CallbackQueryHandler(select_download_type_callback, pattern="^dltype_"))
    app.add_handler(CallbackQueryHandler(cancel_download_callback, pattern="^cancel_"))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^({'|'.join(LANG_CODES.keys())})$"), process_link_message))
    
    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()
