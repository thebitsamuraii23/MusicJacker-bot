import os
import logging
import asyncio
import subprocess
import tempfile
import shutil
import json
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.critical("TELEGRAM_BOT_TOKEN не найден в переменных окружения.")
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения.")

cookies_path = os.getenv('COOKIES_PATH', 'youtube.com_cookies.txt')

logger.info("Текущий рабочий каталог: %s", os.getcwd())
if os.path.exists(cookies_path):
    logger.info("Cookies файл найден, размер: %d байт", os.path.getsize(cookies_path))
else:
    logger.error("Файл cookies не найден по указанному пути: %s", cookies_path)

REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@ytdlpdeveloper") # Сделаем настраиваемым

LANGUAGES = {
    "ru": {
        "start": (
            "Привет! Я бот для скачивания музыки с YouTube.\n\n"
            "Для начала работы с ботом, отправьте ссылку на YouTube или YT Music (видео или плейлист), "
            "и бот загрузит её вам в формате MP3.\n\n"
            "Загруженная вами музыка обрабатывается в самом высоком качестве и отправляется вам.\n\n"
            f"Для начала работы с ботом, пожалуйста подпишитесь на канал {REQUIRED_CHANNEL}.\n"
            "Приятного использования!"
        ),
        "choose_lang": "Выберите язык / Choose language:",
        "not_subscribed": f"Чтобы пользоваться ботом, подпишитесь на канал {REQUIRED_CHANNEL} и попробуйте снова.",
        "checking": "Проверяю ссылку...",
        "not_youtube": "Это не ссылка на YouTube. Отправьте корректную ссылку.",
        "downloading": "Скачиваю и конвертирую... Подождите.",
        "too_big": "Файл слишком большой (>50 МБ). Попробуйте другое видео или плейлист.",
        "done": "Готово! Музыка отправлена.",
        "error": "Что-то пошло не так. Проверьте ссылку или попробуйте позже!\n",
        "sending_file": "Отправляю файл {index} из {total}...",
        "cancel_button": "Отмена",
        "cancelling": "Отменяю загрузку...",
        "cancelled": "Загрузка отменена.",
        "download_in_progress": "Другая загрузка уже в процессе. Пожалуйста, подождите или отмените её.",
        "already_cancelled_or_done": "Загрузка уже отменена или завершена."
    },
    "en": {
        "start": (
            "Hello! I am a bot for downloading music from YouTube.\n\n"
            "To get started, send a YouTube or YT Music link (video or playlist), "
            "and the bot will send you an MP3.\n\n"
            "Your music is processed in the highest quality and sent to you.\n\n"
            f"To use the bot, please subscribe to the channel {REQUIRED_CHANNEL}.\n"
            "Enjoy!"
        ),
        "choose_lang": "Choose language:",
        "not_subscribed": f"To use the bot, please subscribe to {REQUIRED_CHANNEL} and try again.",
        "checking": "Checking link...",
        "not_youtube": "This is not a YouTube link. Please send a valid link.",
        "downloading": "Downloading and converting... Please wait.",
        "too_big": "File is too large (>50 MB). Try another video or playlist.",
        "done": "Done! Music sent.",
        "error": "Something went wrong. Check the link or try again!\n",
        "sending_file": "Sending file {index} of {total}...",
        "cancel_button": "Cancel",
        "cancelling": "Cancelling download...",
        "cancelled": "Download cancelled.",
        "download_in_progress": "Another download is already in progress. Please wait or cancel it.",
        "already_cancelled_or_done": "Download already cancelled or completed."
    },
    "az": {
        "start": (
            "Salam! Mən YouTube-dan musiqi yükləmək üçün botam.\n\n"
            "Başlamaq üçün YouTube və ya YT Music linki göndərin (video və ya playlist), "
            "və bot sizə MP3 göndərəcək.\n\n"
            "Yüklədiyiniz musiqi ən yüksək keyfiyyətdə işlənir və sizə göndərilir.\n\n"
            f"Botdan istifadə etmək üçün zəhmət olmasa {REQUIRED_CHANNEL} kanalına abunə olun.\n"
            "Uğurlar!"
        ),
        "choose_lang": "Dil seçin:",
        "not_subscribed": f"Botdan istifadə etmək üçün {REQUIRED_CHANNEL} kanalına abunə olun və yenidən cəhd edin.",
        "checking": "Link yoxlanılır...",
        "not_youtube": "Bu YouTube linki deyil. Zəhmət olmasa düzgün link göndərin.",
        "downloading": "Yüklənir və çevrilir... Zəhmət olmasa gözləyin.",
        "too_big": "Fayl çox böyükdür (>50 MB). Başqa video və ya playlist yoxlayın.",
        "done": "Hazırdır! Musiqi göndərildi.",
        "error": "Nəsə səhv oldu. Linki yoxlayın və ya yenidən cəhd edin!\n",
        "sending_file": "Fayl {index} / {total} göndərilir...",
        "cancel_button": "Ləğv et",
        "cancelling": "Yükləmə ləğv edilir...",
        "cancelled": "Yükləmə ləğv edildi.",
        "download_in_progress": "Başqa bir yükləmə artıq davam edir. Zəhmət olmasa gözləyin və ya onu ləğv edin.",
        "already_cancelled_or_done": "Yükləmə artıq ləğv edilib və ya tamamlanıb."
    },
    "tr": {
        "start": (
            "Merhaba! Ben YouTube'dan müzik indiren bir botum.\n\n"
            "Başlamak için YouTube veya YT Music bağlantısı gönderin (video veya playlist), "
            "ve bot size MP3 gönderecek.\n\n"
            "Yüklediğiniz müzik en yüksek kalitede işlenir ve size gönderilir.\n\n"
            f"Botu kullanmak için lütfen {REQUIRED_CHANNEL} kanalına abone olun.\n"
            "İyi eğlenceler!"
        ),
        "choose_lang": "Dil seçin:",
        "not_subscribed": f"Botu kullanmak için {REQUIRED_CHANNEL} kanalına abone olun ve tekrar deneyin.",
        "checking": "Bağlantı kontrol ediliyor...",
        "not_youtube": "Bu bir YouTube bağlantısı değil. Lütfen geçerli bir bağlantı gönderin.",
        "downloading": "İndiriliyor ve dönüştürülüyor... Lütfen bekleyin.",
        "too_big": "Dosya çok büyük (>50 MB). Başka bir video veya playlist deneyin.",
        "done": "Hazır! Müzik gönderildi.",
        "error": "Bir şeyler ters gitti. Bağlantıyı kontrol edin veya tekrar deneyin!\n",
        "sending_file": "{index} / {total} dosya gönderiliyor...",
        "cancel_button": "İptal",
        "cancelling": "İndirme iptal ediliyor...",
        "cancelled": "İndirme iptal edildi.",
        "download_in_progress": "Başka bir indirme zaten devam ediyor. Lütfen bekleyin veya iptal edin.",
        "already_cancelled_or_done": "İndirme zaten iptal edildi veya tamamlandı."
    },
    "es": {
        "start": (
            "¡Hola! Soy un bot para descargar música de YouTube.\n\n"
            "Para empezar, envía un enlace de YouTube o YT Music (video o lista de reproducción), "
            "y el bot te enviará un MP3.\n\n"
            "La música que subes se procesa con la mejor calidad y se te envía.\n\n"
            f"Para usar el bot, por favor suscríbete al canal {REQUIRED_CHANNEL}.\n"
            "¡Disfruta!"
        ),
        "choose_lang": "Elige idioma:",
        "not_subscribed": f"Para usar el bot, suscríbete al canal {REQUIRED_CHANNEL} y vuelve a intentarlo.",
        "checking": "Comprobando enlace...",
        "not_youtube": "Esto no es un enlace de YouTube. Por favor, envía un enlace válido.",
        "downloading": "Descargando y convirtiendo... Por favor espera.",
        "too_big": "El archivo es demasiado grande (>50 MB). Prueba con otro video o lista de reproducción.",
        "done": "¡Listo! Música enviada.",
        "error": "Algo salió mal. ¡Verifica el enlace o inténtalo de nuevo!\n",
        "sending_file": "Enviando archivo {index} de {total}...",
        "cancel_button": "Cancelar",
        "cancelling": "Cancelando descarga...",
        "cancelled": "Descarga cancelada.",
        "download_in_progress": "Ya hay otra descarga en curso. Por favor, espera o cancélela.",
        "already_cancelled_or_done": "La descarga ya ha sido cancelada o completada."
    },
    "uk": {
        "start": (
            "Привіт! Я бот для завантаження музики з YouTube.\n\n"
            "Щоб почати, надішліть посилання на YouTube або YT Music (відео чи плейлист), "
            "і бот надішле вам MP3.\n\n"
            "Завантажена вами музика обробляється у найвищій якості та надсилається вам.\n\n"
            f"Щоб користуватися ботом, будь ласка, підпишіться на канал {REQUIRED_CHANNEL}.\n"
            "Гарного користування!"
        ),
        "choose_lang": "Оберіть мову:",
        "not_subscribed": f"Щоб користуватися ботом, підпишіться на канал {REQUIRED_CHANNEL} і спробуйте ще раз.",
        "checking": "Перевіряю посилання...",
        "not_youtube": "Це не посилання на YouTube. Надішліть коректне посилання.",
        "downloading": "Завантажую та конвертую... Зачекайте.",
        "too_big": "Файл занадто великий (>50 МБ). Спробуйте інше відео або плейлист.",
        "done": "Готово! Музику надіслано.",
        "error": "Щось пішло не так. Перевірте посилання або спробуйте ще раз!\n",
        "sending_file": "Надсилаю файл {index} з {total}...",
        "cancel_button": "Скасувати",
        "cancelling": "Скасовую завантаження...",
        "cancelled": "Завантаження скасовано.",
        "download_in_progress": "Інше завантаження вже триває. Будь ласка, зачекайте або скасуйте його.",
        "already_cancelled_or_done": "Завантаження вже скасовано або завершено."
    },
    "ar": {
        "start": (
            "مرحبًا! أنا بوت لتحميل الموسيقى من يوتيوب.\n\n"
            "لبدء الاستخدام، أرسل رابط YouTube أو YT Music (فيديو أو قائمة تشغيل)، "
            "وسيرسل لك البوت ملف MP3.\n\n"
            "يتم معالجة الموسيقى التي ترسلها بأعلى جودة وإرسالها إليك.\n\n"
            f"لاستخدام البوت، يرجى الاشتراك في قناة {REQUIRED_CHANNEL}.\n"
            "استخدام ممتع!"
        ),
        "choose_lang": "اختر اللغة:",
        "not_subscribed": f"لاستخدام البوت، يرجى الاشتراك في قناة {REQUIRED_CHANNEL} ثم المحاولة مرة أخرى.",
        "checking": "جارٍ التحقق من الرابط...",
        "not_youtube": "هذا ليس رابط يوتيوب. يرجى إرسال رابط صحيح.",
        "downloading": "جارٍ التحميل والتحويل... يرجى الانتظار.",
        "too_big": "الملف كبير جدًا (>50 ميجابايت). جرب فيديو أو قائمة تشغيل أخرى.",
        "done": "تم! تم إرسال الموسيقى.",
        "error": "حدث خطأ ما. تحقق من الرابط أو حاول مرة أخرى!\n",
        "sending_file": "جاري إرسال الملف {index} من {total}...",
        "cancel_button": "إلغاء",
        "cancelling": "جاري إلغاء التنزيل...",
        "cancelled": "تم إلغاء التنزيل.",
        "download_in_progress": "هناك تنزيل آخر قيد التقدم بالفعل. يرجى الانتظار أو إلغائه.",
        "already_cancelled_or_done": "تم إلغاء التنزيل أو اكتماله بالفعل."
    }
}

user_langs = {}

USER_LANGS_FILE = "user_languages.json"

def load_user_langs():
    global user_langs
    if os.path.exists(USER_LANGS_FILE):
        with open(USER_LANGS_FILE, 'r') as f:
            try:
                loaded_langs = json.load(f)
                user_langs = {int(k): v for k, v in loaded_langs.items()} 
            except json.JSONDecodeError:
                logger.error(f"Could not decode {USER_LANGS_FILE}, starting with empty langs.")
                user_langs = {}
    else:
        user_langs = {}

def save_user_langs():
    with open(USER_LANGS_FILE, 'w') as f:
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
    "Русский": "ru",
    "English": "en",
    "Español": "es",
    "Azərbaycan dili": "az",
    "Türkçe": "tr",
    "Українська": "uk",
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
    if lang_code:
        user_langs[update.effective_user.id] = lang_code
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
        "--cookies", cookies_path,
        "--flat-playlist",
        "--dump-single-json",
        url
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error(f"yt-dlp info error: {stderr.decode('utf-8', 'ignore')}")
            raise Exception("Failed to get URL info")
        return json.loads(stdout.decode('utf-8', 'ignore'))
    except Exception as e:
        logger.error(f"Error getting URL info for {url}: {e}")
        raise


async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, texts: dict, user_id: int):
    chat_id = update.message.chat_id
    temp_dir = None
    status_message = None
    yt_dlp_proc = None
    active_downloads = context.bot_data.setdefault('active_downloads', {})

    try:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(texts["cancel_button"], callback_data=f"cancel_{user_id}")]])
        status_message = await update.message.reply_text(texts["downloading"], reply_markup=keyboard)

        temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temp dir: {temp_dir} for user {user_id}")

        url_info = await get_url_info(url)
        is_playlist = url_info.get('_type') == 'playlist'
        
        downloaded_files_info = []
        output_template = os.path.join(temp_dir, "%(title).200B.%(ext)s") 
        if is_playlist:
            output_template = os.path.join(temp_dir, "%(playlist_index)s - %(title).180B.%(ext)s")

        cmd = [
            "yt-dlp",
            "--cookies", cookies_path,
            "--ffmpeg-location", "/usr/bin/ffmpeg",
            "--format", "bestaudio/best",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "192K",
            "--output", output_template,
            "--no-playlist" if not is_playlist else "--yes-playlist",
            url
        ]
        
        logger.info(f"Executing yt-dlp for user {user_id}: {' '.join(cmd)}")
        yt_dlp_proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        
        active_downloads[user_id]['process'] = yt_dlp_proc
        
        stdout, stderr = await yt_dlp_proc.communicate()

        if yt_dlp_proc.returncode != 0:
            error_message = stderr.decode('utf-8', 'ignore')
            logger.error(f"yt-dlp download error for user {user_id} (return code {yt_dlp_proc.returncode}): {error_message}")
            # Try to find specific error messages
            if "private video" in error_message.lower():
                 raise Exception(texts.get("error_private_video", "Это приватное видео и не может быть скачано."))
            if "video unavailable" in error_message.lower():
                 raise Exception(texts.get("error_video_unavailable", "Видео недоступно."))
            raise Exception("Ошибка загрузки: " + error_message)

        if is_playlist:
            for root, _, files in os.walk(temp_dir):
                for file in sorted(files):
                    if file.endswith(".mp3"):
                        filepath = os.path.join(root, file)
                        title = os.path.splitext(file)[0]
                        downloaded_files_info.append((filepath, title))
        else:
            found_files = [f for f in os.listdir(temp_dir) if f.endswith(".mp3")]
            if not found_files:
                 raise Exception("MP3 файл не найден после скачивания.")
            if len(found_files) > 1 :
                 logger.warning(f"Expected 1 file, found {len(found_files)} for non-playlist download by {user_id}")

            # Take the first (should be only one)
            filepath = os.path.join(temp_dir, found_files[0])
            title = os.path.splitext(found_files[0])[0]
            downloaded_files_info.append((filepath, title))
        
        if not downloaded_files_info:
            raise Exception("Не найдены скачанные MP3 файлы.")

        total_files = len(downloaded_files_info)
        for i, (audio_file, title_str) in enumerate(downloaded_files_info):
            if status_message:
                try:
                    await status_message.edit_text(texts["sending_file"].format(index=i+1, total=total_files), reply_markup=keyboard)
                except Exception as edit_err:
                    logger.warning(f"Could not edit status message for {user_id}: {edit_err}")


            file_size = os.path.getsize(audio_file)
            if file_size > 50 * 1024 * 1024:
                await update.message.reply_text(f"{texts['too_big']} ({os.path.basename(audio_file)})")
                continue

            try:
                with open(audio_file, 'rb') as audio:
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=audio,
                        title=title_str,
                        filename=os.path.basename(audio_file)
                    )
            except Exception as send_error:
                logger.error(f"Error sending audio file {audio_file} for user {user_id}: {send_error}")
                await update.message.reply_text(f"{texts['error']} (Ошибка отправки файла {os.path.basename(audio_file)})")
        
        if status_message:
            await status_message.edit_text(texts["done"], reply_markup=None)

    except asyncio.CancelledError:
        logger.info(f"Download task for user {user_id} (URL: {url}) was cancelled.")
        if yt_dlp_proc and yt_dlp_proc.returncode is None: # Check if process is still running
            logger.info(f"Attempting to terminate yt-dlp process {yt_dlp_proc.pid} for user {user_id}")
            yt_dlp_proc.terminate()
            try:
                await asyncio.wait_for(yt_dlp_proc.wait(), timeout=5.0)
                logger.info(f"yt-dlp process {yt_dlp_proc.pid} terminated gracefully.")
            except asyncio.TimeoutError:
                logger.warning(f"yt-dlp process {yt_dlp_proc.pid} did not terminate gracefully, killing.")
                yt_dlp_proc.kill()
                await yt_dlp_proc.wait()
            except Exception as e:
                logger.error(f"Error during yt-dlp process termination for user {user_id}: {e}")

        if status_message:
            try:
                await status_message.edit_text(texts["cancelled"], reply_markup=None)
            except Exception as edit_err:
                 logger.warning(f"Could not edit status message to cancelled for {user_id}: {edit_err}")
        else:
            await update.message.reply_text(texts["cancelled"])
            
    except Exception as e:
        logger.error(f"Ошибка при скачивании или обработке для user {user_id} (URL: {url}): {e}", exc_info=True)
        error_text = texts["error"] + str(e)
        if status_message:
            try:
                await status_message.edit_text(error_text, reply_markup=None)
            except Exception as edit_err:
                logger.warning(f"Could not edit status message to error for {user_id}: {edit_err}")
                await update.message.reply_text(error_text)
        else:
            await update.message.reply_text(error_text)
    finally:
        if temp_dir and os.path.exists(temp_dir):
            logger.info(f"Removing temp dir: {temp_dir} for user {user_id}")
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        active_downloads = context.bot_data.get('active_downloads', {})
        if user_id in active_downloads:
            del active_downloads[user_id]
            logger.info(f"Removed task for user {user_id} from active_downloads.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await choose_language(update, context)

async def download_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]

    active_downloads = context.bot_data.setdefault('active_downloads', {})
    if user_id in active_downloads and not active_downloads[user_id]['task'].done():
        await update.message.reply_text(texts["download_in_progress"])
        return

    is_subscribed = await check_subscription(user_id, context.bot)
    if not is_subscribed:
        await update.message.reply_text(texts["not_subscribed"])
        return

    url = update.message.text.strip()
    
    
    if not ("youtube.com/" in url or "youtu.be/" in url):
        await update.message.reply_text(texts["not_youtube"])
        return
    
    logger.info(f"User {user_id} initiated download for URL: {url}")
    task = asyncio.create_task(handle_download(update, context, url, texts, user_id))
    active_downloads[user_id] = {'task': task, 'process': None}


async def cancel_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # Acknowledge the button press

    callback_data_parts = query.data.split("_")
    if len(callback_data_parts) < 2 or callback_data_parts[0] != "cancel":
        logger.warning(f"Received unexpected callback_data: {query.data}")
        return

    try:
        user_id_to_cancel = int(callback_data_parts[1])
    except ValueError:
        logger.error(f"Could not parse user_id from callback_data: {query.data}")
        return
        
    requesting_user_id = query.from_user.id
    lang = get_user_lang(requesting_user_id)
    texts = LANGUAGES[lang]

    if user_id_to_cancel != requesting_user_id:
       
        logger.warning(f"User {requesting_user_id} attempted to cancel download for {user_id_to_cancel}. Allowing for now.")
       

    active_downloads = context.bot_data.get('active_downloads', {})
    task_info = active_downloads.get(user_id_to_cancel)

    if task_info and task_info['task'] and not task_info['task'].done():
        task_info['task'].cancel()
        try:
            await query.edit_message_text(text=texts["cancelling"], reply_markup=None)
        except Exception as e:
            logger.info(f"Could not edit message to 'cancelling' for user {user_id_to_cancel}: {e}")
            
    else:
        try:
            await query.edit_message_text(text=texts["already_cancelled_or_done"], reply_markup=None)
        except Exception as e:
            logger.info(f"Could not edit message to 'already_cancelled_or_done' for user {user_id_to_cancel}: {e}")


def main():
    load_user_langs()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", choose_language))
    app.add_handler(MessageHandler(filters.Regex("^(Русский|English|Español|Azərbaycan dili|Türkçe|Українська|العربية)$"), set_language))
    
    app.add_handler(CallbackQueryHandler(cancel_download_callback, pattern="^cancel_"))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_music))
    
    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()
