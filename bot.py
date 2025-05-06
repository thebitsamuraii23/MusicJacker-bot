import os
import logging
import asyncio
import subprocess
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.environ.get('7762900402:AAH_Tdrl2NVqlCAlki5BntmgnechHX_dIjE')  # Получаем токен из переменной окружения
cookies_path = os.environ.get('COOKIES_PATH', 'youtube.com_cookies.txt')  # Путь к cookies из переменной окружения или по умолчанию

logger.info("Текущий рабочий каталог: %s", os.getcwd())
if os.path.exists(cookies_path):
    logger.info("Cookies файл найден, размер: %d байт", os.path.getsize(cookies_path))
else:
    logger.error("Файл cookies не найден по указанному пути: %s", cookies_path)

def download_video(url: str) -> tuple[str, str]:
    """
    Скачивает и конвертирует видео в mp3 с фиксированным именем файла output.mp3.
    Возвращает (имя итогового аудиофайла, оригинальный title).
    """
    # Получаем title
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

    # Скачиваем аудио с фиксированным именем
    output_name = "output.%(ext)s"
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
       'Привет! Я бот для скачивания музыки с YouTube. Отправь мне ссылку на видео, и я пришлю MP3.\n'
        'Используй на свой страх и риск!\n'
        'Бот принимает ссылку на видео с YouTube, скачивает видео, конвертирует его в MP3 и отправляет вам.\n'
        'Для начала работы отправьте ссылку на видео с YouTube.\n'
        'Я не несу ответственности за ваши действия!\n'
        'Приятного использования!\n'
        '---\n'
        'Hello! I am a bot for downloading music from YouTube. Use it at your own risk!'
    )

async def download_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    chat_id = update.message.chat_id
    msg = await update.message.reply_text("Проверяю ссылку...")

    if ("youtube.com" not in url) and ("youtu.be" not in url):
        await msg.edit_text("Это не ссылка на YouTube. Отправьте корректную ссылку.")
        return

    await msg.edit_text("Скачиваю и конвертирую... Подождите.")
    try:
        loop = asyncio.get_event_loop()
        audio_file, title = await loop.run_in_executor(None, download_video, url)

        # Проверка размера файла
        file_size = os.path.getsize(audio_file)
        if file_size > 50 * 1024 * 1024:
            await msg.edit_text("Файл слишком большой (>50 МБ). Попробуйте другое видео.")
            os.remove(audio_file)
            return

        with open(audio_file, 'rb') as audio:
            await context.bot.send_audio(chat_id=chat_id, audio=audio, title=title)
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
