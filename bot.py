import os
import logging
import asyncio
import subprocess
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = '7762900402:AAH_Tdrl2NVqlCAlki5BntmgnechHX_dIjE'


cookies_path = '/workspaces/codespaces-blank/youtube.com_cookies.txt'

logger.info("Текущий рабочий каталог: %s", os.getcwd())
if os.path.exists(cookies_path):
    logger.info("Cookies файл найден, размер: %d байт", os.path.getsize(cookies_path))
else:
    logger.error("Файл cookies не найден по указанному пути: %s", cookies_path)

def download_video(url: str) -> str:
    """
    Определяет имя видеофайла, затем запускает скачивание с конвертацией через yt-dlp
    с использованием subprocess. Возвращает имя итогового аудиофайла (с расширением .mp3).  
    """
    # Пытаемся получить имя файла с cookies
    cmd_info = [
        "yt-dlp",
        "--cookies", cookies_path,
        "--print", "%(title)s.%(ext)s",
        "--skip-download",
        url
    ]
    info_result = subprocess.run(cmd_info, capture_output=True, text=True)
    logger.info("Результат info (stdout с cookies): %s", info_result.stdout)
    logger.info("Результат info (stderr с cookies): %s", info_result.stderr)
    file_name = info_result.stdout.strip()
    
   
    if not file_name:
        logger.warning("Не удалось получить имя файла с cookies, пробую без cookies.")
        cmd_info = [
            "yt-dlp",
            "--print", "%(title)s.%(ext)s",
            "--skip-download",
            url
        ]
        info_result = subprocess.run(cmd_info, capture_output=True, text=True)
        logger.info("Результат info (stdout без cookies): %s", info_result.stdout)
        logger.info("Результат info (stderr без cookies): %s", info_result.stderr)
        file_name = info_result.stdout.strip()
    
    if not file_name:
        raise Exception("Не удалось определить имя файла для видео. Проверьте, доступно ли видео и корректны ли cookies.")
    
    # Запускаем скачивание и конвертацию с указанием пути к ffmpeg
    cmd_download = [
        "yt-dlp",
        "--cookies", cookies_path,
        "--ffmpeg-location", "/usr/bin/ffmpeg",
        "--format", "bestaudio/best",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "192K",
        "--output", "%(title)s.%(ext)s",
        url
    ]
    download_result = subprocess.run(cmd_download, capture_output=True, text=True)
    if download_result.returncode != 0:
        raise Exception("Ошибка загрузки: " + download_result.stderr)
    
   
    base_name = file_name.rsplit('.', 1)[0]
    final_audio = base_name + ".mp3"
    if not os.path.exists(final_audio):
        
        final_audio = file_name
    return final_audio

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
       ' Привет! Я бот для скачивания музыки с YouTube. Отправь мне ссылку на видео, и я пришлю MP3. '
        'Используй на свой страх и риск! '
        'Каким образом работает бот? '
        'Бот принимает ссылку на видео с YouTube, скачивает видео, конвертирует его в MP3 и отправляет вам. '
        'Но, по мерам использования и правилам YouTube, данный бот не является совсем легальным. '
        'Поэтому, используйте его на свой страх и риск! '
        'Для начала работы отправьте ссылку на видео с YouTube. '
        'Я не ношу ответственности за ваши действия! '
        'Приятного использования!\n'
        'Hello! I am a bot for downloading music from YouTube. '
        'Use it at your own risk! '
        'How does the bot work? '
        'The bot takes a YouTube video link, downloads the video, converts it to MP3, and sends it to you. '
        'However, according to the terms of use and YouTube guidelines, this bot is not entirely legal. '
        'So, use it at your own risk! '
        'To get started, send a YouTube video link. '
        'I am not responsible for your actions! '
        'Enjoy using it!'
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
        audio_file = await loop.run_in_executor(None, download_video, url)
        
        # Проверка размера файла
        file_size = os.path.getsize(audio_file)
        if file_size > 50 * 1024 * 1024:
            await msg.edit_text("Файл слишком большой (>50 МБ). Попробуйте другое видео.")
            os.remove(audio_file)
            return

        with open(audio_file, 'rb') as audio:
            await context.bot.send_audio(chat_id=chat_id, audio=audio, title=audio_file.rsplit('.', 1)[0])
        await msg.edit_text("Готово! Музыка отправлена.")
        os.remove(audio_file)
    except Exception as e:
        logger.error("Ошибка при скачивании: %s", str(e))
        await msg.edit_text("Что-то пошло не так. Проверьте ссылку или попробуйте позже!")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_music))
    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()