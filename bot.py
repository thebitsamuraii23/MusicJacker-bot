import os
import logging
import asyncio
import tempfile
import shutil
import json
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv
import yt_dlp

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("Cant found TELEGRAM_BOT_TOKEN in environment variables.")

cookies_path = os.getenv('COOKIES_PATH', 'youtube.com_cookies.txt')
ffmpeg_path_from_env = os.getenv('FFMPEG_PATH')
ffmpeg_path = ffmpeg_path_from_env if ffmpeg_path_from_env else '/usr/bin/ffmpeg'
FFMPEG_IS_AVAILABLE = os.path.exists(ffmpeg_path) and os.access(ffmpeg_path, os.X_OK)
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@ytdlpdeveloper")
TELEGRAM_FILE_SIZE_LIMIT_BYTES = 50 * 1024 * 1024
TELEGRAM_FILE_SIZE_LIMIT_TEXT = "50 МБ"

LANGUAGES = {
    "ru": {
        "start": (
            "Привет! Я бот для скачивания аудио с YouTube и SoundCloud.\n\n"
            "Отправьте ссылку на YouTube или SoundCloud (видео или трек), и я предложу вам варианты загрузки аудио.\n\n"
            f"Для работы с ботом, подпишитесь на канал {REQUIRED_CHANNEL}.\n"
            "\n🎵 Также я умею искать музыку по названию! Просто напишите /search и найдите нужный трек.\n"
            "Приятного использования!"
            "Не забудьте подписаться на канал для обновлений и поддержки @ytdlpload_bot. artoflife2303.github.io/miniblog"
        ),
        "choose_lang": "Выберите язык / Choose language:",
        "not_subscribed": f"Чтобы пользоваться ботом, подпишитесь на канал {REQUIRED_CHANNEL} и попробуйте снова.",
        "checking": "Проверяю ссылку...",
        "not_youtube": "Это не поддерживаемая ссылка. Отправьте корректную ссылку на YouTube или SoundCloud.",
        "choose_download_type": "Выберите формат аудио:",
        "audio_button_mp3": "🎵 MP3 (YouTube)",
        "audio_button_sc": "🎵 MP3 (SoundCloud)",
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
            "Hello! I am a bot for downloading audio from YouTube and SoundCloud.\n\n"
            "Send a YouTube or SoundCloud link (video or track), and I will offer you audio download options.\n\n"
            f"To use the bot, please subscribe to the channel {REQUIRED_CHANNEL}.\n"
            "\n🎵 I can also search for music by name! Just type /search and find your track.\n"
            "Enjoy!"
            "Don't forget to subscribe to the channel for updates and support @ytdlpdeveloper. artoflife2303.github.io/miniblog"
        ),
        "choose_lang": "Choose language:",
        "not_subscribed": f"To use the bot, please subscribe to {REQUIRED_CHANNEL} and try again.",
        "checking": "Checking link...",
        "not_youtube": "This is not a supported link. Please send a valid YouTube or SoundCloud link.",
        "choose_download_type": "Choose audio format:",
        "audio_button_mp3": "🎵 MP3 (YouTube)",
        "audio_button_sc": "🎵 MP3 (SoundCloud)",
        "downloading_audio": "Downloading audio... Please wait.",
        "download_progress": "Downloading: {percent} at {speed}, ETA ~{eta}",
        "too_big": f"File is too large (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Try another video or track.",
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
        "url_error_generic": "Failed to process URL. Make sure it's a valid YouTube or SoundCloud link."
    },
    "es": {
        "start": (
            "¡Hola! Soy un bot para descargar audio de YouTube y SoundCloud.\n\n"
            "Envíame un enlace de YouTube o SoundCloud (video o pista) y te ofreceré opciones para descargar el audio.\n\n"
            f"Para usar el bot, suscríbete al canal {REQUIRED_CHANNEL}.\n"
            "\n🎵 ¡También puedo buscar música por nombre! Escribe /search y encuentra tu pista.\n"
            "¡Disfruta!"
            "No olvides suscribirte al canal para actualizaciones y soporte @ytdlpdeveloper. artoflife2303.github.io/miniblog"
        ),
        "choose_lang": "Elige idioma:",
        "not_subscribed": f"Para usar el bot, suscríbete al canal {REQUIRED_CHANNEL} y vuelve a intentarlo.",
        "checking": "Verificando enlace...",
        "not_youtube": "Este enlace no es compatible. Por favor, envía un enlace válido de YouTube o SoundCloud.",
        "choose_download_type": "Elige el formato de audio:",
        "audio_button_mp3": "🎵 MP3 (YouTube)",
        "audio_button_sc": "🎵 MP3 (SoundCloud)",
        "downloading_audio": "Descargando audio... Por favor espera.",
        "download_progress": "Descargando: {percent} a {speed}, queda ~{eta}",
        "too_big": f"El archivo es demasiado grande (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Prueba con otro video o pista.",
        "done_audio": "¡Listo! Audio enviado.",
        "error": "¡Algo salió mal! Verifica el enlace o inténtalo de nuevo.\n",
        "error_private_video": "Este es un video privado y no puede ser descargado.",
        "error_video_unavailable": "Video no disponible.",
        "sending_file": "Enviando archivo {index} de {total}...",
        "cancel_button": "Cancelar",
        "cancelling": "Cancelando descarga...",
        "cancelled": "Descarga cancelada.",
        "download_in_progress": "Otra descarga ya está en progreso. Por favor espera o cancélala.",
        "already_cancelled_or_done": "La descarga ya fue cancelada o completada.",
        "url_error_generic": "No se pudo procesar la URL. Asegúrate de que sea un enlace válido de YouTube o SoundCloud."
    },
    "az": {
        "start": (
            "Salam! Mən YouTube və SoundCloud-dan audio yükləmək üçün botam.\n\n"
            "YouTube və ya SoundCloud linki göndərin (video və ya trek), mən sizə audio yükləmə variantları təklif edəcəyəm.\n\n"
            f"Botdan istifadə etmək üçün {REQUIRED_CHANNEL} kanalına abunə olun.\n"
            "\n🎵 Mən həmçinin adla musiqi axtara bilirəm! Sadəcə /search yazın və trek tapın.\n"
            "Uğurlar!"
            "Botu istifadə etmək üçün kanala abunə olmağı unutmayın @ytdlppload_bot. artoflife2303.github.io/miniblog"
        ),
        "choose_lang": "Dili seçin:",
        "not_subscribed": f"Botdan istifadə etmək üçün {REQUIRED_CHANNEL} kanalına abunə olun və yenidən cəhd edin.",
        "checking": "Link yoxlanılır...",
        "not_youtube": "Bu dəstəklənməyən linkdir. Zəhmət olmasa, düzgün YouTube və ya SoundCloud linki göndərin.",
        "choose_download_type": "Audio formatını seçin:",
        "audio_button_mp3": "🎵 MP3 (YouTube)",
        "audio_button_sc": "🎵 MP3 (SoundCloud)",
        "downloading_audio": "Audio yüklənir... Zəhmət olmasa, gözləyin.",
        "download_progress": "Yüklənir: {percent} sürətlə {speed}, təxmini vaxt ~{eta}",
        "too_big": f"Fayl çox böyükdür (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Başqa video və ya trek yoxlayın.",
        "done_audio": "Hazırdır! Audio göndərildi.",
        "error": "Bir xəta baş verdi. Linki yoxlayın və yenidən cəhd edin!\n",
        "error_private_video": "Bu şəxsi videodur və yüklənə bilməz.",
        "error_video_unavailable": "Video mövcud deyil.",
        "sending_file": "{total} fayldan {index}-ci göndərilir...",
        "cancel_button": "Ləğv et",
        "cancelling": "Yükləmə ləğv olunur...",
        "cancelled": "Yükləmə ləğv edildi.",
        "download_in_progress": "Başqa bir yükləmə artıq davam edir. Zəhmət olmasa, gözləyin və ya ləğv edin.",
        "already_cancelled_or_done": "Yükləmə artıq ləğv edilib və ya tamamlanıb.",
        "url_error_generic": "URL işlənə bilmədi. Düzgün YouTube və ya SoundCloud linki olduğuna əmin olun."
    },
    "tr": {
        "start": (
            "Merhaba! Ben YouTube ve SoundCloud'dan ses indirmek için bir botum.\n\n"
            "YouTube veya SoundCloud bağlantısı gönderin (video veya parça), size ses indirme seçenekleri sunacağım.\n\n"
            f"Botu kullanmak için {REQUIRED_CHANNEL} kanalına abone olun.\n"
            "\n🎵 Ayrıca isimle müzik arayabilirim! Sadece /search yazın ve parçanızı bulun.\n"
            "İyi eğlenceler!"
            "Botu kullanmak için kanala abone olmayı unutmayın @ytdlppload_bot. artoflife2303.github.io/miniblog"
        ),
        "choose_lang": "Dil seçin:",
        "not_subscribed": f"Botu kullanmak için lütfen {REQUIRED_CHANNEL} kanalına abone olun ve tekrar deneyin.",
        "checking": "Bağlantı kontrol ediliyor...",
        "not_youtube": "Bu desteklenmeyen bir bağlantı. Lütfen geçerli bir YouTube veya SoundCloud bağlantısı gönderin.",
        "choose_download_type": "Ses formatı seçin:",
        "audio_button_mp3": "🎵 MP3 (YouTube)",
        "audio_button_sc": "🎵 MP3 (SoundCloud)",
        "downloading_audio": "Ses indiriliyor... Lütfen bekleyin.",
        "download_progress": "İndiriliyor: {percent} hızında {speed}, kalan ~{eta}",
        "too_big": f"Dosya çok büyük (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Başka bir video veya parça deneyin.",
        "done_audio": "Tamamlandı! Ses gönderildi.",
        "error": "Bir hata oluştu. Bağlantıyı kontrol edin veya tekrar deneyin!\n",
        "error_private_video": "Bu özel bir video ve indirilemez.",
        "error_video_unavailable": "Video kullanılamıyor.",
        "sending_file": "{total} dosyadan {index}. gönderiliyor...",
        "cancel_button": "İptal",
        "cancelling": "İndirme iptal ediliyor...",
        "cancelled": "İndirme iptal edildi.",
        "download_in_progress": "Başka bir indirme zaten devam ediyor. Lütfen bekleyin veya iptal edin.",
        "already_cancelled_or_done": "İndirme zaten iptal edildi veya tamamlandı.",
        "url_error_generic": "URL işlenemedi. Geçerli bir YouTube veya SoundCloud bağlantısı olduğundan emin olun."
    },
    "uk": {
        "start": (
            "Вітаю! Я бот для завантаження аудіо з YouTube та SoundCloud.\n\n"
            "Надішліть посилання на YouTube або SoundCloud (відео чи трек), і я запропоную вам варіанти завантаження аудіо.\n\n"
            f"Щоб користуватися ботом, підпишіться на канал {REQUIRED_CHANNEL}.\n"
            "\n🎵 Також я вмію шукати музику за назвою! Просто напишіть /search і знайдіть потрібний трек.\n"
            "Гарного користування!"
            "Не забудьте підписатися на канал для оновлень та підтримки @ytdlppload_bot. artoflife2303.github.io/miniblog"
        ),
        "choose_lang": "Оберіть мову:",
        "not_subscribed": f"Щоб користуватися ботом, підпишіться на канал {REQUIRED_CHANNEL} і спробуйте ще раз.",
        "checking": "Перевіряю посилання...",
        "not_youtube": "Це непідтримуване посилання. Надішліть коректне посилання на YouTube або SoundCloud.",
        "choose_download_type": "Оберіть формат аудіо:",
        "audio_button_mp3": "🎵 MP3 (YouTube)",
        "audio_button_sc": "🎵 MP3 (SoundCloud)",
        "downloading_audio": "Завантажую аудіо... Зачекайте.",
        "download_progress": "Завантаження: {percent} зі швидкістю {speed}, залишилось ~{eta}",
        "too_big": f"Файл занадто великий (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Спробуйте інше відео або трек.",
        "done_audio": "Готово! Аудіо надіслано.",
        "error": "Щось пішло не так. Перевірте посилання або спробуйте ще раз!\n",
        "error_private_video": "Це приватне відео і його не можна завантажити.",
        "error_video_unavailable": "Відео недоступне.",
        "sending_file": "Надсилаю файл {index} з {total}...",
        "cancel_button": "Скасувати",
        "cancelling": "Скасовую завантаження...",
        "cancelled": "Завантаження скасовано.",
        "download_in_progress": "Інше завантаження вже триває. Будь ласка, зачекайте або скасуйте його.",
        "already_cancelled_or_done": "Завантаження вже скасовано або завершено.",
        "url_error_generic": "Не вдалося обробити URL. Переконайтеся, що це коректне посилання на YouTube або SoundCloud."
    },
    "ar": {
        "start": (
            "مرحبًا! أنا بوت لتحميل الصوت من YouTube وSoundCloud.\n\n"
            "أرسل رابط YouTube أو SoundCloud (فيديو أو مقطع)، وسأقدم لك خيارات تحميل الصوت.\n\n"
            f"لاستخدام البوت، يرجى الاشتراك في القناة {REQUIRED_CHANNEL}.\n"
            "\n🎵 يمكنني أيضًا البحث عن الموسيقى بالاسم! فقط اكتب /search وابحث عن المقطع المطلوب.\n"
            "استخدام ممتع!"
            "لا تنس الاشتراك في القناة للحصول على التحديثات والدعم @ytdlppload_bot. artoflife2303.github.io/miniblog"
        ),
        "choose_lang": "اختر اللغة:",
        "not_subscribed": f"لاستخدام البوت، يرجى الاشتراك في القناة {REQUIRED_CHANNEL} ثم المحاولة مرة أخرى.",
        "checking": "جارٍ التحقق من الرابط...",
        "not_youtube": "هذا الرابط غير مدعوم. يرجى إرسال رابط صحيح لـ YouTube أو SoundCloud.",
        "choose_download_type": "اختر صيغة الصوت:",
        "audio_button_mp3": "🎵 MP3 (YouTube)",
        "audio_button_sc": "🎵 MP3 (SoundCloud)",
        "downloading_audio": "جارٍ تحميل الصوت... يرجى الانتظار.",
        "download_progress": "جارٍ التحميل: {percent} بسرعة {speed}، متبقٍ ~{eta}",
        "too_big": f"الملف كبير جدًا (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). جرب فيديو أو مقطع آخر.",
        "done_audio": "تم! تم إرسال الصوت.",
        "error": "حدث خطأ ما. تحقق من الرابط أو حاول مرة أخرى!\n",
        "error_private_video": "هذا فيديو خاص ولا يمكن تحميله.",
        "error_video_unavailable": "الفيديو غير متوفر.",
        "sending_file": "يتم إرسال الملف {index} من {total}...",
        "cancel_button": "إلغاء",
        "cancelling": "جارٍ إلغاء التحميل...",
        "cancelled": "تم إلغاء التحميل.",
        "download_in_progress": "هناك تحميل آخر قيد التنفيذ. يرجى الانتظار أو إلغاؤه.",
        "already_cancelled_or_done": "تم إلغاء التحميل أو اكتماله بالفعل.",
        "url_error_generic": "تعذر معالجة الرابط. تأكد أنه رابط صحيح لـ YouTube أو SoundCloud."
    }
}
    

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

SEARCH_RESULTS_LIMIT = 10 
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
                user_langs = {}
    else:
        user_langs = {}

def save_user_langs():
    with open(USER_LANGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_langs, f)

def get_user_lang(user_id):
    return user_langs.get(user_id, "ru")

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

async def check_subscription(user_id: int, bot) -> bool:
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False

def is_soundcloud_url(url):
    return "soundcloud.com/" in url.lower()

def blocking_yt_dlp_download(ydl_opts, url_to_download):
    import yt_dlp.utils
    import logging
    yt_dlp_logger = logging.getLogger("yt_dlp")
    yt_dlp_logger.setLevel(logging.WARNING)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url_to_download])
        return True
    except yt_dlp.utils.UnsupportedError:
        raise Exception("Unsupported URL: {}".format(url_to_download))
    except Exception as e:
        raise

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
        ydl_opts = {
            'outtmpl': os.path.join(temp_dir, '%(title).140B - Made by @ytdlpload_bot Developed by BitSamurai [%(id)s].%(ext)s'),
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
        ydl_opts = {k: v for k, v in ydl_opts.items() if v is not None}
        try:
            await asyncio.to_thread(blocking_yt_dlp_download, ydl_opts, url)
        except Exception as e:
            if 'Unsupported URL' in str(e) or 'unsupported url' in str(e).lower():
                await update_status_message_async("Ссылка не поддерживается. Пожалуйста, проверьте правильность ссылки или попробуйте другой запрос.", show_cancel_button=False)
                return
            logger.error(f"Ошибка при скачивании: {e}")
            raise
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
            except Exception:
                await context.bot.send_message(chat_id=chat_id, text=f"{texts['error']} (Ошибка отправки файла {os.path.basename(file_to_send)})")
        await update_status_message_async(texts["done_audio"], show_cancel_button=False)
    except asyncio.CancelledError:
        if status_message:
            await update_status_message_async(texts["cancelled"], show_cancel_button=False)
        else:
            await context.bot.send_message(chat_id=chat_id, text=texts["cancelled"])
    except Exception as e:
        if 'Unsupported URL' in str(e) or 'unsupported url' in str(e).lower():
            if status_message:
                await update_status_message_async("Ссылка не поддерживается. Пожалуйста, проверьте правильность ссылки или попробуйте другой запрос.", show_cancel_button=False)
            else:
                await context.bot.send_message(chat_id=chat_id, text="Ссылка не поддерживается. Пожалуйста, проверьте правильность ссылки или попробуйте другой запрос.")
            return
        logger.error(f"Ошибка при скачивании: {e}")
        if status_message:
            await update_status_message_async(texts["error"] + str(e), show_cancel_button=False)
        else:
            await context.bot.send_message(chat_id=chat_id, text=texts["error"] + str(e))
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        if user_id in active_downloads:
            del active_downloads[user_id]

async def ask_download_type(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    context.user_data[f'url_for_download_{user_id}'] = url
    if is_soundcloud_url(url):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(texts["audio_button_sc"], callback_data=f"dltype_audio_sc_{user_id}")]
        ])
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(texts["audio_button_mp3"], callback_data=f"dltype_audio_mp3_{user_id}")]
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
    if not ("youtube.com/" in url_lower or "youtu.be/" in url_lower or "soundcloud.com/" in url_lower):
        await update.message.reply_text(texts["not_youtube"])
        return
    await ask_download_type(update, context, url)

async def select_download_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        parts = query.data.split("_")
        if len(parts) != 4 or parts[0] != "dltype" or (parts[1] != "audio"):
            raise ValueError("Некорректный формат callback_data для аудио")
        specific_format = parts[2]
        user_id_from_callback = int(parts[3])
        if specific_format == "mp3":
            download_type_for_handler = "audio_mp3"
        elif specific_format == "sc":
            download_type_for_handler = "audio_sc"
        else:
            raise ValueError("Неизвестный тип загрузки")
    except (IndexError, ValueError):
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

async def search_youtube(query: str):
    if is_url(query):
        return 'unsupported_url'
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'extract_flat': True,
        'nocheckcertificate': True,
        'default_search': None,
        'noplaylist': True,
        'dump_single_json': True,
    }
    try:
        search_query = f"ytsearch10:{query}"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            entries = info.get('entries', [])
            if entries is None:
                return []
            return entries[:SEARCH_RESULTS_LIMIT]
    except yt_dlp.utils.DownloadError as e:
        if 'Unsupported URL' in str(e) or 'unsupported url' in str(e).lower():
            return 'unsupported_url'
        return []
    except Exception as e:
        logger.error(f"Ошибка поиска на YouTube: {e}")
        return []

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите название трека или исполнителя. После чего, нажмите на музыку, она загрзится в формате MP3.\n"
        "Введите /cancel для отмены поиска.\n"
        "Введите /search для поиска музыки по названию (YouTube).",
    )
    context.user_data['awaiting_search_query'] = True

async def handle_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.message.text.strip()
    await update.message.reply_text("Ищу музыку...")
    results = await search_youtube(query)
    if results == 'unsupported_url':
        await update.message.reply_text("Ссылка не поддерживается. Пожалуйста, проверьте другую ссылку или попробуйте другой запрос.(Альтернативно, если у вас не получилось, вы можете загрузить трек от другого исполнителя или Remix)")
        context.user_data.pop('awaiting_search_query', None)
        return
    if not isinstance(results, list):
        results = []
    if not results:
        await update.message.reply_text("Ничего не найдено. Попробуйте другой запрос.")
        context.user_data.pop('awaiting_search_query', None)
        return
    keyboard = []
    for idx, entry in enumerate(results):
        title = entry.get('title', 'Без названия')
        video_id = entry.get('id')
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
    try:
        video_id = query.data.split("_")[1]
    except Exception:
        await query.edit_message_text("Ошибка выбора трека.")
        return
    url = f"https://youtu.be/{video_id}"
    await query.edit_message_text("Скачиваю выбранный трек в MP3...")
    task = asyncio.create_task(handle_download(query, context, url, LANGUAGES[get_user_lang(user_id)], user_id, "audio_mp3"))
    active_downloads = context.bot_data.setdefault('active_downloads', {})
    active_downloads[user_id] = {'task': task}

def is_url(text):
    text = text.lower().strip()
    return (
        text.startswith("http://") or text.startswith("https://")
    ) and (
        "youtube.com/" in text or "youtu.be/" in text or "soundcloud.com/" in text
    )

async def smart_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    text = update.message.text.strip()
    active_downloads = context.bot_data.setdefault('active_downloads', {})

    if user_id in active_downloads and active_downloads[user_id].get('task') and not active_downloads[user_id]['task'].done():
        await update.message.reply_text(texts["download_in_progress"])
        return

    is_subscribed = await check_subscription(user_id, context.bot)
    if not is_subscribed:
        await update.message.reply_text(texts["not_subscribed"])
        return

    if is_url(text):
        await ask_download_type(update, context, text)
    else:
        await handle_search_query(update, context)

def main():
    load_user_langs()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", choose_language))
    app.add_handler(CommandHandler("languages", choose_language))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(MessageHandler(filters.Regex(f"^({'|'.join(LANG_CODES.keys())})$"), set_language))
    app.add_handler(CallbackQueryHandler(select_download_type_callback, pattern="^dltype_"))
    app.add_handler(CallbackQueryHandler(search_select_callback, pattern="^searchsel_"))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^({'|'.join(LANG_CODES.keys())})$"),
        smart_message_handler
    ))
    async def set_commands(_):
        await app.bot.set_my_commands([
            BotCommand("start", "Запуск и выбор языка / Start and choose language"),
            BotCommand("languages", "Сменить язык / Change language"),
            BotCommand("search", "Поиск музыки по названию (YouTube) / Search music by name (YouTube) (Localized only in russian)"),
        ])
    app.post_init = set_commands
    app.run_polling()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await choose_language(update, context)

if __name__ == '__main__':
    main()
