import os
import logging
import asyncio
import subprocess
from telegram import Update
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

async def check_subscription(user_id: int, bot) -> bool:
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.warning(f"Не удалось проверить подписку: {e}")
        return False

def download_video(url: str) -> tuple[str, str]:
    """
    Скачивает и конвертирует видео в mp3 с фиксированным именем файла output.mp3.
    Возвращает (имя итогового аудиофайла, оригинальный title).
    """
    cmd_title = [
        "yt-dlp",
        "--cookies", cookies_path,
        "--print", "%(title)s",
        "--skip-download",
        url
    ]
    info_result = subprocess.run(cmd_title, capture_output=True, text=True)
    title = info_result.stdout.strip()
    if not title:
        title = "Музыка с YouTube"

    output_name = "output.mp3"
    cmd_download = [
        "yt-dlp",
        "--cookies", cookies_path,
        "--ffmpeg-location", "/usr/bin/ffmpeg",
        "--format", "bestaudio/best",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "192K",
        "--output", output_name,
        url
    ]
    download_result = subprocess.run(cmd_download, capture_output=True, text=True)
    if download_result.returncode != 0:
        raise Exception("Ошибка загрузки: " + download_result.stderr)
    final_audio = "output.mp3"
    if not os.path.exists(final_audio):
        raise Exception("Файл не найден после скачивания.")
    return final_audio, title

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
    'Привет! Я бот для скачивания музыки с YouTube. Для начала работы с ботом, отправьте ссылку на YouTube или YT Music (не плейлист) и бот'
    'Загрузит ее вам в формате MP3'
    'Загруженное вами музыка, обрабатывается в самом высоком качестве и отправляется вам.'
    'для начала работы с ботом, пожалуйста подпишитесь на канал @ytdlpdeveloper. Приятного использования!'
 
        
    )
async def download_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.message.chat_id

    
    is_subscribed = await check_subscription(user_id, context.bot)
    if not is_subscribed:
        await update.message.reply_text(
            f"Чтобы пользоваться ботом, подпишитесь на канал {REQUIRED_CHANNEL} и попробуйте снова."
        )
        return

    url = update.message.text.strip()
    msg = await update.message.reply_text("Проверяю ссылку...")

    if ("youtube.com" not in url) and ("youtu.be" not in url):
        await msg.edit_text("Это не ссылка на YouTube. Отправьте корректную ссылку.")
        return

    await msg.edit_text("Скачиваю и конвертирую... Подождите.")
    try:
        loop = asyncio.get_event_loop()
        audio_file, title = await loop.run_in_executor(None, download_video, url)

        file_size = os.path.getsize(audio_file)
        if file_size > 50 * 1024 * 1024:
            await msg.edit_text("Файл слишком большой (>50 МБ). Попробуйте другое видео.")
            os.remove(audio_file)
            return

        with open(audio_file, 'rb') as audio:
            await context.bot.send_audio(
                chat_id=chat_id,
                audio=audio,
                title=title,
                filename="output.mp3"
            )
        await msg.edit_text("Готово! Музыка отправлена.")
        os.remove(audio_file)
    except Exception as e:
        logger.error("Ошибка при скачивании: %s", str(e))
        await msg.edit_text(f"Что-то пошло не так. Проверьте ссылку или попробуйте позже!\n{str(e)}")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_music))
    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()
