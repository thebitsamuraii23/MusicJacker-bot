import os
import logging
import asyncio
import subprocess
import tempfile
import shutil
import json
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
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

REQUIRED_CHANNEL = "@ytdlpdeveloper"

LANGUAGES = {
    "ru": {
        "start": (
            "Привет! Я бот для скачивания музыки с YouTube.\n\n"
            "Для начала работы с ботом, отправьте ссылку на YouTube или YT Music (видео или плейлист), "
            "и бот загрузит её вам в формате MP3.\n\n"
            "Загруженная вами музыка обрабатывается в самом высоком качестве и отправляется вам.\n\n"
            "Для начала работы с ботом, пожалуйста подпишитесь на канал @ytdlpdeveloper.\n"
            "Приятного использования!"
        ),
        "choose_lang": "Выберите язык / Choose language:",
        "not_subscribed": "Чтобы пользоваться ботом, подпишитесь на канал @ytdlpdeveloper и попробуйте снова.",
        "checking": "Проверяю ссылку...",
        "not_youtube": "Это не ссылка на YouTube. Отправьте корректную ссылку.",
        "downloading": "Скачиваю и конвертирую... Подождите.",
        "too_big": "Файл слишком большой (>50 МБ). Попробуйте другое видео или плейлист.",
        "done": "Готово! Музыка отправлена.",
        "error": "Что-то пошло не так. Проверьте ссылку или попробуйте позже!\n",
        "sending_file": "Отправляю файл {index} из {total}..."
    },
    "en": {
        "start": (
            "Hello! I am a bot for downloading music from YouTube.\n\n"
            "To get started, send a YouTube or YT Music link (video or playlist), "
            "and the bot will send you an MP3.\n\n"
            "Your music is processed in the highest quality and sent to you.\n\n"
            "To use the bot, please subscribe to the channel @ytdlpdeveloper.\n"
            "Enjoy!"
        ),
        "choose_lang": "Choose language:",
        "not_subscribed": "To use the bot, please subscribe to @ytdlpdeveloper and try again.",
        "checking": "Checking link...",
        "not_youtube": "This is not a YouTube link. Please send a valid link.",
        "downloading": "Downloading and converting... Please wait.",
        "too_big": "File is too large (>50 MB). Try another video or playlist.",
        "done": "Done! Music sent.",
        "error": "Something went wrong. Check the link or try again!\n",
        "sending_file": "Sending file {index} of {total}..."
    },
    "az": {
        "start": (
            "Salam! Mən YouTube-dan musiqi yükləmək üçün botam.\n\n"
            "Başlamaq üçün YouTube və ya YT Music linki göndərin (video və ya playlist), "
            "və bot sizə MP3 göndərəcək.\n\n"
            "Yüklədiyiniz musiqi ən yüksək keyfiyyətdə işlənir və sizə göndərilir.\n\n"
            "Botdan istifadə etmək üçün zəhmət olmasa @ytdlpdeveloper kanalına abunə olun.\n"
            "Uğurlar!"
        ),
        "choose_lang": "Dil seçin:",
        "not_subscribed": "Botdan istifadə etmək üçün @ytdlpdeveloper kanalına abunə olun və yenidən cəhd edin.",
        "checking": "Link yoxlanılır...",
        "not_youtube": "Bu YouTube linki deyil. Zəhmət olmasa düzgün link göndərin.",
        "downloading": "Yüklənir və çevrilir... Zəhmət olmasa gözləyin.",
        "too_big": "Fayl çox böyükdür (>50 MB). Başqa video və ya playlist yoxlayın.",
        "done": "Hazırdır! Musiqi göndərildi.",
        "error": "Nəsə səhv oldu. Linki yoxlayın və ya yenidən cəhd edin!\n",
        "sending_file": "Fayl {index} / {total} göndərilir..."
    },
    "tr": {
        "start": (
            "Merhaba! Ben YouTube'dan müzik indiren bir botum.\n\n"
            "Başlamak için YouTube veya YT Music bağlantısı gönderin (video veya playlist), "
            "ve bot size MP3 gönderecek.\n\n"
            "Yüklediğiniz müzik en yüksek kalitede işlenir ve size gönderilir.\n\n"
            "Botu kullanmak için lütfen @ytdlpdeveloper kanalına abone olun.\n"
            "İyi eğlenceler!"
        ),
        "choose_lang": "Dil seçin:",
        "not_subscribed": "Botu kullanmak için @ytdlpdeveloper kanalına abone olun ve tekrar deneyin.",
        "checking": "Bağlantı kontrol ediliyor...",
        "not_youtube": "Bu bir YouTube bağlantısı değil. Lütfen geçerli bir bağlantı gönderin.",
        "downloading": "İndiriliyor ve dönüştürülüyor... Lütfen bekleyin.",
        "too_big": "Dosya çok büyük (>50 MB). Başka bir video veya playlist deneyin.",
        "done": "Hazır! Müzik gönderildi.",
        "error": "Bir şeyler ters gitti. Bağlantıyı kontrol edin veya tekrar deneyin!\n",
        "sending_file": "{index} / {total} dosya gönderiliyor..."
    },
    "es": {
        "start": (
            "¡Hola! Soy un bot para descargar música de YouTube.\n\n"
            "Para empezar, envía un enlace de YouTube o YT Music (video o lista de reproducción), "
            "y el bot te enviará un MP3.\n\n"
            "La música que subes se procesa con la mejor calidad y se te envía.\n\n"
            "Para usar el bot, por favor suscríbete al canal @ytdlpdeveloper.\n"
            "¡Disfruta!"
        ),
        "choose_lang": "Elige idioma:",
        "not_subscribed": "Para usar el bot, suscríbete al canal @ytdlpdeveloper y vuelve a intentarlo.",
        "checking": "Comprobando enlace...",
        "not_youtube": "Esto no es un enlace de YouTube. Por favor, envía un enlace válido.",
        "downloading": "Descargando y convirtiendo... Por favor espera.",
        "too_big": "El archivo es demasiado grande (>50 MB). Prueba con otro video o lista de reproducción.",
        "done": "¡Listo! Música enviada.",
        "error": "Algo salió mal. ¡Verifica el enlace o inténtalo de nuevo!\n",
        "sending_file": "Enviando archivo {index} de {total}..."
    },
    "uk": {
        "start": (
            "Привіт! Я бот для завантаження музики з YouTube.\n\n"
            "Щоб почати, надішліть посилання на YouTube або YT Music (відео чи плейлист), "
            "і бот надішле вам MP3.\n\n"
            "Завантажена вами музика обробляється у найвищій якості та надсилається вам.\n\n"
            "Щоб користуватися ботом, будь ласка, підпишіться на канал @ytdlpdeveloper.\n"
            "Гарного користування!"
        ),
        "choose_lang": "Оберіть мову:",
        "not_subscribed": "Щоб користуватися ботом, підпишіться на канал @ytdlpdeveloper і спробуйте ще раз.",
        "checking": "Перевіряю посилання...",
        "not_youtube": "Це не посилання на YouTube. Надішліть коректне посилання.",
        "downloading": "Завантажую та конвертую... Зачекайте.",
        "too_big": "Файл занадто великий (>50 МБ). Спробуйте інше відео або плейлист.",
        "done": "Готово! Музику надіслано.",
        "error": "Щось пішло не так. Перевірте посилання або спробуйте ще раз!\n",
        "sending_file": "Надсилаю файл {index} з {total}..."
    },
    "ar": {
        "start": (
            "مرحبًا! أنا بوت لتحميل الموسيقى من يوتيوب.\n\n"
            "لبدء الاستخدام، أرسل رابط YouTube أو YT Music (فيديو أو قائمة تشغيل)، "
            "وسيرسل لك البوت ملف MP3.\n\n"
            "يتم معالجة الموسيقى التي ترسلها بأعلى جودة وإرسالها إليك.\n\n"
            "لاستخدام البوت، يرجى الاشتراك في قناة @ytdlpdeveloper.\n"
            "استخدام ممتع!"
        ),
        "choose_lang": "اختر اللغة:",
        "not_subscribed": "لاستخدام البوت، يرجى الاشتراك في قناة @ytdlpdeveloper ثم المحاولة مرة أخرى.",
        "checking": "جارٍ التحقق من الرابط...",
        "not_youtube": "هذا ليس رابط يوتيوب. يرجى إرسال رابط صحيح.",
        "downloading": "جارٍ التحميل والتحويل... يرجى الانتظار.",
        "too_big": "الملف كبير جدًا (>50 ميجابايت). جرب فيديو أو قائمة تشغيل أخرى.",
        "done": "تم! تم إرسال الموسيقى.",
        "error": "حدث خطأ ما. تحقق من الرابط أو حاول مرة أخرى!\n",
        "sending_file": "جاري إرسال الملف {index} من {total}..."
    }
}

user_langs = {}

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
    lang = LANG_CODES.get(update.message.text)
    if lang:
        user_langs[update.effective_user.id] = lang
        await update.message.reply_text(LANGUAGES[lang]["start"])
    else:
        await update.message.reply_text("Пожалуйста, выберите язык с клавиатуры / Please choose a language from the keyboard.")

def get_user_lang(user_id):
    return user_langs.get(user_id, "ru")

async def check_subscription(user_id: int, bot) -> bool:
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.warning(f"Не удалось проверить подписку: {e}")
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
            logger.error(f"yt-dlp info error: {stderr.decode()}")
            raise Exception("Failed to get URL info")
        return json.loads(stdout.decode())
    except Exception as e:
        logger.error(f"Error getting URL info: {e}")
        raise

async def async_download_audio(url: str, temp_dir: str, is_playlist: bool) -> list[tuple[str, str]]:
    downloaded_files_info = []
    output_template = os.path.join(temp_dir, "%(title)s.%(ext)s")
    if is_playlist:
        output_template = os.path.join(temp_dir, "%(playlist_index)s - %(title)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "--cookies", cookies_path,
        "--ffmpeg-location", "/usr/bin/ffmpeg",
        "--format", "bestaudio/best",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "192K",
        "--output", output_template,
        url
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise Exception("Ошибка загрузки: " + stderr.decode())

        if is_playlist:
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith(".mp3"):
                        filepath = os.path.join(root, file)
                        title = os.path.splitext(file)[0]
                        downloaded_files_info.append((filepath, title))
            downloaded_files_info.sort()
        else:
            downloaded_files = [f for f in os.listdir(temp_dir) if f.endswith(".mp3")]
            if len(downloaded_files) != 1:
                raise Exception("Неожиданное количество файлов после скачивания одиночного видео.")
            filepath = os.path.join(temp_dir, downloaded_files[0])
            title = os.path.splitext(downloaded_files[0])[0]
            downloaded_files_info.append((filepath, title))

        if not downloaded_files_info:
            raise Exception("Не найдены скачанные MP3 файлы.")

        return downloaded_files_info

    except Exception as e:
        logger.error(f"Error during download process: {e}")
        raise e


async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, texts: dict):
    chat_id = update.message.chat_id
    temp_dir = None
    msg = None

    try:
        msg = await update.message.reply_text(texts["downloading"])
        temp_dir = tempfile.mkdtemp()

        url_info = await get_url_info(url)
        is_playlist = url_info.get('_type') == 'playlist'

        downloaded_files_info = await async_download_audio(url, temp_dir, is_playlist)

        total_files = len(downloaded_files_info)
        for i, (audio_file, title) in enumerate(downloaded_files_info):
            if msg:
                await msg.edit_text(texts["sending_file"].format(index=i+1, total=total_files))

            file_size = os.path.getsize(audio_file)
            if file_size > 50 * 1024 * 1024:
                await update.message.reply_text(f"{texts['too_big']} ({os.path.basename(audio_file)})")
                continue

            try:
                with open(audio_file, 'rb') as audio:
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=audio,
                        title=title,
                        filename=os.path.basename(audio_file)
                    )
            except Exception as send_error:
                 logger.error(f"Error sending audio file {audio_file}: {send_error}")
                 await update.message.reply_text(f"{texts['error']} (Ошибка отправки файла {os.path.basename(audio_file)})")


        if msg:
             await msg.edit_text(texts["done"])

    except Exception as e:
        logger.error("Ошибка при скачивании или обработке: %s", str(e))
        if msg:
            await msg.edit_text(texts["error"] + str(e))
        else:
            await update.message.reply_text(texts["error"] + str(e))
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await choose_language(update, context)

async def download_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]

    is_subscribed = await check_subscription(user_id, context.bot)
    if not is_subscribed:
        await update.message.reply_text(texts["not_subscribed"])
        return

    url = update.message.text.strip()

    if not ("youtube.com/" in url or "youtu.be/" in url or "music.youtube.com/" in url):
         await update.message.reply_text(texts["not_youtube"])
         return

    asyncio.create_task(handle_download(update, context, url, texts))


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", choose_language))
    app.add_handler(MessageHandler(filters.Regex("^(Русский|English|Español|Azərbaycan dili|Türkçe|Українська|العربية)$"), set_language))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_music))
    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()
