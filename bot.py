# -*- coding: utf-8 -*-

# Standard library imports
import os
import logging
import asyncio
import tempfile
import shutil
import json
import time
import re
from io import BytesIO
from http import cookiejar

# Third party imports
import requests
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, InlineQueryHandler
from dotenv import load_dotenv
import yt_dlp
from mutagen.id3 import ID3, TIT2, TPE1, APIC
from mutagen.mp4 import MP4, MP4Cover
from PIL import Image

# Load environment variables from .env file
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION & CONSTANTS ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("Cant found TELEGRAM_BOT_TOKEN in environment variables.")

cookies_path = os.getenv('COOKIES_PATH', 'youtube.com_cookies.txt')
ffmpeg_path_from_env = os.getenv('FFMPEG_PATH')
ffmpeg_path = ffmpeg_path_from_env if ffmpeg_path_from_env else '/usr/bin/ffmpeg'
FFMPEG_IS_AVAILABLE = os.path.exists(ffmpeg_path) and os.access(ffmpeg_path, os.X_OK)

REQUIRED_CHANNELS = ["@ytdlpdeveloper", "@samuraicodingrus"]
TELEGRAM_FILE_SIZE_LIMIT_BYTES = 50 * 1024 * 1024  # 50 MB
TELEGRAM_FILE_SIZE_LIMIT_TEXT = "50 МБ"
USER_LANGS_FILE = "user_languages.json"
SEARCH_RESULTS_LIMIT = 10

if not os.path.exists(cookies_path):
    logger.warning(f"Cookies file {cookies_path} not found. Some features may not work properly.")

# --- GLOBAL VARIABLES & STATE ---
user_langs = {}
user_stats = {}  # user_id: {"downloads": int, "searches": int}
user_last_download_time = {}
user_last_search_time = {}

# --- LANGUAGE DEFINITIONS ---
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
            "\n� Həmçinin adla musiqi axtara bilərəm! Sadəcə /search yazın.\n\n"
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
    "uk": {
        # Добавьте украинский перевод здесь
    }
}


# --- HELPER FUNCTIONS ---

def get_user_lang(user_id):
    """Determines the user's language by their ID. Defaults to Russian."""
    lang = user_langs.get(user_id)
    return lang if lang in LANGUAGES else "ru"

def is_soundcloud_url(url):
    """Checks if the URL is a SoundCloud link."""
    return "soundcloud.com/" in url.lower()

def is_url(text):
    """Checks if a string is a YouTube or SoundCloud URL."""
    text = text.lower().strip()
    return (text.startswith("http://") or text.startswith("https://")) and \
           ("youtube.com/" in text or "youtu.be/" in text or "soundcloud.com/" in text)

def load_user_langs():
    """Loads user language preferences from a file."""
    global user_langs
    if os.path.exists(USER_LANGS_FILE):
        try:
            with open(USER_LANGS_FILE, 'r', encoding='utf-8') as f:
                loaded_langs = json.load(f)
                user_langs = {int(k): v for k, v in loaded_langs.items()}
        except (json.JSONDecodeError, ValueError):
            logger.error(f"Could not decode {USER_LANGS_FILE}. Starting with empty langs.")
            user_langs = {}
    else:
        user_langs = {}

def save_user_langs():
    """Saves user language preferences to a file."""
    with open(USER_LANGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_langs, f)

def parse_artist_title(raw_title):
    """Parses a raw string to extract a clean title and a list of artists."""
    base = os.path.splitext(os.path.basename(raw_title))[0]
    if ' - ' in base:
        artist_part, title_part = base.split(' - ', 1)
    else:
        artist_part, title_part = '', base

    feat_regex = r'\(ft\.?|feat\.?|featuring\s*([^\)]+)\)'
    feat_regex2 = r'\[(ft\.?|feat\.?|featuring)\s*([^\]]+)\]'
    
    featured = []
    for regex in [feat_regex, feat_regex2]:
        for m in re.finditer(regex, title_part, re.IGNORECASE):
            # The actual featured artist is in the group after the keyword
            if len(m.groups()) > 1:
                 featured.append(m.group(1).strip())

    clean_title = re.sub(feat_regex, '', title_part, flags=re.IGNORECASE).strip()
    clean_title = re.sub(feat_regex2, '', clean_title, flags=re.IGNORECASE).strip()
    
    all_artists = [artist_part.strip()] if artist_part.strip() else []
    for f in featured:
        for a in re.split(',|&| and ', f):
            a = a.strip()
            if a and a not in all_artists:
                all_artists.append(a)
                
    return clean_title, ', '.join(all_artists)


async def check_subscription(user_id: int, bot) -> bool:
    """Checks if the user is subscribed to all required channels."""
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

# --- YT-DLP & FILE PROCESSING ---

def get_youtube_thumbnail(url):
    """Fetches a thumbnail for a YouTube video."""
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
                cookies = None
                if os.path.exists(cookies_path):
                    cj = cookiejar.MozillaCookieJar()
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

def blocking_yt_dlp_download(ydl_opts, url_to_download):
    """Performs download using yt-dlp in a blocking manner."""
    yt_dlp_logger = logging.getLogger("yt_dlp")
    yt_dlp_logger.setLevel(logging.WARNING)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url_to_download])
        return True
    except yt_dlp.utils.UnsupportedError:
        raise Exception(f"Unsupported URL: {url_to_download}")
    except Exception as e:
        logger.error(f"yt-dlp download error: {e}")
        raise

async def search_youtube(query: str):
    """Performs a search for videos on YouTube."""
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


# --- CORE HANDLERS ---

async def handle_download(update_or_query, context: ContextTypes.DEFAULT_TYPE, url: str, texts: dict, user_id: int, download_type: str):
    """Handles the entire download and processing workflow for a file."""
    chat_id = update_or_query.effective_chat.id
    status_message = None
    temp_dir = None
    
    # --- Status Message Management ---
    async def update_status_message_async(text, show_cancel_button=True):
        nonlocal status_message
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(texts["cancel_button"], callback_data=f"cancel_{user_id}")]]) if show_cancel_button else None
        try:
            if status_message:
                await status_message.edit_text(text, reply_markup=markup)
            else:
                status_message = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)
        except Exception as e:
            logger.warning(f"Could not update status message: {e}")

    try:
        # --- Cooldown Check ---
        now = time.time()
        download_cooldown = 15  # seconds
        last_download = user_last_download_time.get(user_id, 0)
        if now - last_download < download_cooldown:
            await context.bot.send_message(chat_id=chat_id, text=texts["cooldown_message"])
            return

        await update_status_message_async(texts["downloading_audio"])
        temp_dir = tempfile.mkdtemp()

        # --- YDL Options ---
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'quiet': True,
            'nocheckcertificate': True,
            'cookiefile': cookies_path if os.path.exists(cookies_path) else None,
            'writethumbnail': True,
            'postprocessors': [],
        }

        if download_type == "audio_mp3":
            ydl_opts['postprocessors'].append({
                'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192',
            })
        elif download_type == "audio_m4a":
             ydl_opts['postprocessors'].append({
                'key': 'FFmpegExtractAudio', 'preferredcodec': 'm4a', 'preferredquality': '192',
            })
        elif download_type == "video_mp4":
            ydl_opts['format'] = 'best[ext=mp4][height<=720]/best[ext=mp4]/best'
        
        # --- Download ---
        await asyncio.to_thread(blocking_yt_dlp_download, ydl_opts, url)

        # --- File Processing ---
        downloaded_files_info = []
        for f in os.listdir(temp_dir):
            if f.lower().endswith(('.mp3', '.m4a', '.mp4')):
                base_name = os.path.splitext(f)[0]
                downloaded_files_info.append((os.path.join(temp_dir, f), base_name))
        
        if not downloaded_files_info:
            raise Exception("No media file found after download.")

        total_files = len(downloaded_files_info)
        for i, (file_to_send, title_str) in enumerate(downloaded_files_info):
            await update_status_message_async(texts["sending_file"].format(index=i+1, total=total_files))
            
            if os.path.getsize(file_to_send) > TELEGRAM_FILE_SIZE_LIMIT_BYTES:
                await context.bot.send_message(chat_id=chat_id, text=f"{texts['too_big']} ({os.path.basename(file_to_send)})")
                continue

            # --- Metadata and Thumbnail ---
            title, artist = parse_artist_title(title_str)
            cover_bytes = None

            # 1. Try to get thumbnail from downloaded file
            thumb_path = None
            for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                p = os.path.join(temp_dir, title_str + ext)
                if os.path.exists(p):
                    thumb_path = p
                    break
            
            if thumb_path:
                with open(thumb_path, 'rb') as tf:
                    cover_bytes = tf.read()
            
            # 2. Fallback to manual fetch
            if not cover_bytes and (is_url(url) and "soundcloud.com" not in url):
                 cover_bytes = get_youtube_thumbnail(url)

            # --- Compress and Set Cover ---
            if cover_bytes:
                try:
                    img = Image.open(BytesIO(cover_bytes))
                    img_format = 'JPEG' if img.mode in ('RGB', 'L', 'P') else 'PNG'
                    out = BytesIO()
                    img.save(out, format=img_format, quality=85, optimize=True)
                    if out.tell() > 200 * 1024: # Compress further if > 200KB
                        img = img.resize((int(img.size[0]*0.9), int(img.size[1]*0.9)), Image.Resampling.LANCZOS)
                        out = BytesIO()
                        img.save(out, format=img_format, quality=80, optimize=True)
                    cover_bytes = out.getvalue()
                except Exception as e:
                    logger.debug(f"Error compressing cover: {e}")
                    cover_bytes = None

            # --- Write Tags ---
            try:
                final_title = f"{title} (Made by @ytdlpload_bot)" if title else f"{title_str} (Made by @ytdlpload_bot)"
                if file_to_send.endswith('.mp3'):
                    audio = ID3(file_to_send)
                    audio.delall('TIT2'); audio.add(TIT2(encoding=3, text=final_title))
                    if artist: audio.delall('TPE1'); audio.add(TPE1(encoding=3, text=artist))
                    if cover_bytes: audio.delall('APIC'); audio.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=cover_bytes))
                    audio.save()
                elif file_to_send.endswith('.m4a'):
                    audio = MP4(file_to_send)
                    audio.tags['\xa9nam'] = [final_title]
                    if artist: audio.tags['\xa9ART'] = [artist]
                    if cover_bytes: audio.tags['covr'] = [MP4Cover(cover_bytes, imageformat=MP4Cover.FORMAT_JPEG)]
                    audio.save()
            except Exception as e:
                logger.debug(f"Error writing tags/cover: {e}")

            # --- Send File ---
            try:
                with open(file_to_send, 'rb') as f_send:
                    if download_type == "video_mp4":
                        await context.bot.send_video(chat_id=chat_id, video=f_send, filename=os.path.basename(file_to_send))
                    else:
                        await context.bot.send_audio(chat_id=chat_id, audio=f_send, filename=os.path.basename(file_to_send), title=title or '', performer=artist or '')
                await context.bot.send_message(chat_id=chat_id, text=texts.get("copyright_post"))
                logger.info(f"Successfully sent file for {url} to user {user_id}")
            except Exception as e:
                logger.error(f"Error sending file to user {user_id}: {e}")
                await context.bot.send_message(chat_id=chat_id, text=f"{texts['error']} (Sending file failed)")

        await update_status_message_async(texts["done_audio"], show_cancel_button=False)
        user_last_download_time[user_id] = time.time()
        user_stats.setdefault(user_id, {"downloads": 0, "searches": 0})["downloads"] += 1


    except asyncio.CancelledError:
        logger.info(f"Download cancelled for user {user_id}.")
        await update_status_message_async(texts["cancelled"], show_cancel_button=False)
    except Exception as e:
        logger.critical(f"Unhandled error in handle_download for user {user_id}: {e}", exc_info=True)
        error_text = texts["error"]
        if 'private video' in str(e).lower(): error_text = texts["error_private_video"]
        elif 'video unavailable' in str(e).lower(): error_text = texts["error_video_unavailable"]
        elif 'Unsupported URL' in str(e): error_text = texts["unsupported_url_in_search"]
        await update_status_message_async(error_text, show_cancel_button=False)
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temporary directory {temp_dir} for user {user_id}.")
        
        # Remove task from active downloads
        active_downloads = context.user_data.get('active_downloads', [])
        context.user_data['active_downloads'] = [d for d in active_downloads if not d['task'].done()]


# --- COMMAND HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /start: prompts to choose a language."""
    logger.info(f"User {update.effective_user.id} issued /start command.")
    await choose_language(update, context)

async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends the user a keyboard to choose a language."""
    logger.info(f"User {update.effective_user.id} requested language choice.")
    await update.message.reply_text(
        LANGUAGES["ru"]["choose_lang"],  # Default to Russian for the prompt itself
        reply_markup=LANG_KEYBOARD
    )

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sets the language for the user and sends a welcome message."""
    lang_name = update.message.text
    lang_code = LANG_CODES.get(lang_name)
    user_id = update.effective_user.id
    if lang_code:
        user_langs[user_id] = lang_code
        save_user_langs()
        logger.info(f"User {user_id} set language to {lang_code}.")
        await update.message.reply_text(LANGUAGES[lang_code]["start"], parse_mode='HTML', disable_web_page_preview=True)
    else:
        logger.warning(f"User {user_id} sent invalid language: {lang_name}.")
        await update.message.reply_text("Please choose a language from the keyboard.")

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the music search process."""
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    logger.info(f"User {user_id} issued /search command.")

    now = time.time()
    search_cooldown = 5  # seconds
    last_search = user_last_search_time.get(user_id, 0)
    if now - last_search < search_cooldown:
        wait_sec = int(search_cooldown - (now - last_search))
        await update.message.reply_text(f"⏳ Пожалуйста, подождите {wait_sec} сек. перед следующим поиском.")
        return
    
    user_last_search_time[user_id] = now
    await update.message.reply_text(texts["search_prompt"])
    context.user_data[f'awaiting_search_query_{user_id}'] = True
    user_stats.setdefault(user_id, {"downloads": 0, "searches": 0})["searches"] += 1


async def copyright_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends the copyright message."""
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    logger.info(f"User {user_id} issued /copyright command.")
    await update.message.reply_text(texts["copyright_command"])

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows user statistics."""
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    stats = user_stats.get(user_id, {"downloads": 0, "searches": 0})
    await update.message.reply_text(
        f"📊 Ваша статистика:\nСкачиваний: {stats['downloads']}\nПоисков: {stats['searches']}"
    )

# --- MESSAGE & QUERY HANDLERS ---

async def smart_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text messages, routing them to download or search."""
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    text = update.message.text.strip()
    logger.info(f"User {user_id} sent message: '{text}'")

    if not await check_subscription(user_id, context.bot):
        await update.message.reply_text(texts["not_subscribed"])
        return

    active_downloads = context.user_data.get('active_downloads', [])
    active_downloads = [d for d in active_downloads if not d['task'].done()]
    context.user_data['active_downloads'] = active_downloads
    
    if len(active_downloads) >= 3:
        await update.message.reply_text("У вас уже есть 3 активные загрузки. Пожалуйста, дождитесь их завершения.")
        return

    if is_url(text):
        await ask_download_type(update, context, text)
    elif context.user_data.get(f'awaiting_search_query_{user_id}'):
        await handle_search_query(update, context)
    else:
        # Auto-search for short non-URL messages
        await handle_search_query(update, context)


async def handle_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes a search query and displays results."""
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    query_text = update.message.text.strip()
    logger.info(f"User {user_id} sent search query: '{query_text}'")

    await update.message.reply_text(texts["searching"])
    results = await search_youtube(query_text)

    if results == 'unsupported_url':
        await update.message.reply_text(texts["unsupported_url_in_search"])
    elif not results:
        await update.message.reply_text(texts["no_results"])
    else:
        keyboard = []
        for idx, entry in enumerate(results):
            title = entry.get('title', 'Unknown Title')
            video_id = entry.get('id')
            keyboard.append([InlineKeyboardButton(f"{idx+1}. {title}", callback_data=f"searchsel_{user_id}_{video_id}")])
        
        await update.message.reply_text(texts["choose_track"], reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data[f'search_results_{user_id}'] = {entry.get('id'): entry for entry in results}

    context.user_data.pop(f'awaiting_search_query_{user_id}', None)


async def ask_download_type(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    """Sends a copyright warning and asks for the download format."""
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    
    await update.message.reply_text(texts.get("copyright_pre"))
    context.user_data[f'url_for_download_{user_id}'] = url
    
    if is_soundcloud_url(url):
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(texts["audio_button_sc"], callback_data=f"dltype_audio_sc_{user_id}")]])
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎵 MP3", callback_data=f"dltype_audio_mp3_{user_id}"),
             InlineKeyboardButton("🎵 M4A", callback_data=f"dltype_audio_m4a_{user_id}")],
            [InlineKeyboardButton("📹 MP4 (720p)", callback_data=f"dltype_video_mp4_{user_id}")]
        ])
    await update.message.reply_text(texts["choose_download_type"], reply_markup=keyboard)


# --- CALLBACK HANDLERS ---

async def select_download_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles selection from the download format keyboard."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"User {user_id} selected download type: {query.data}")

    try:
        parts = query.data.split("_")
        download_type_for_handler = f"{parts[1]}_{parts[2]}"
        user_id_from_callback = int(parts[3])
    except (IndexError, ValueError) as e:
        logger.error(f"Error parsing callback_data for user {user_id}: {e} - Data: {query.data}")
        await query.edit_message_text("Selection error. Please try again.")
        return

    if user_id_from_callback != user_id:
        await query.edit_message_text("This button is not for you.")
        return

    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    url_to_download = context.user_data.pop(f'url_for_download_{user_id}', None)

    if not url_to_download:
        await query.edit_message_text(texts["error"] + " (URL not found, try again)")
        return

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    task = asyncio.create_task(handle_download(query, context, url_to_download, texts, user_id, download_type_for_handler))
    active_downloads = context.user_data.setdefault('active_downloads', [])
    active_downloads.append({'task': task, 'type': download_type_for_handler, 'start_time': time.time()})


async def search_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles track selection from search results."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"User {user_id} selected track from search: {query.data}")

    try:
        _, sel_user_id, video_id = query.data.split("_", 2)
        if user_id != int(sel_user_id):
            await query.edit_message_text("This button is not for you.")
            return
    except Exception as e:
        logger.error(f"Error parsing search select callback: {e}")
        await query.edit_message_text("Track selection error.")
        return

    url = f"https://youtu.be/{video_id}"
    await query.edit_message_reply_markup(reply_markup=None)
    await ask_download_type(query, context, url)


async def cancel_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the request to cancel a download."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    logger.info(f"User {user_id} requested download cancellation.")

    active_downloads = context.user_data.get('active_downloads', [])
    task_to_cancel = None
    for download in active_downloads:
        if not download['task'].done():
            task_to_cancel = download['task']
            break
    
    if task_to_cancel:
        task_to_cancel.cancel()
        await query.edit_message_text(texts["cancelling"])
    else:
        await query.edit_message_text(texts["already_cancelled_or_done"])


# --- MAIN FUNCTION & BOT SETUP ---

def main():
    """Main function to run the bot."""
    load_user_langs()
    
    try:
        app = Application.builder().token(TOKEN).build()
        logger.info("Bot application built successfully.")
    except Exception as e:
        logger.critical(f"Failed to build bot application: {e}", exc_info=True)
        raise

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler(["language", "languages"], choose_language))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("copyright", copyright_command))
    app.add_handler(CommandHandler("stats", stats_command))

    # Callback query handlers
    app.add_handler(CallbackQueryHandler(select_download_type_callback, pattern="^dltype_"))
    app.add_handler(CallbackQueryHandler(search_select_callback, pattern="^searchsel_"))
    app.add_handler(CallbackQueryHandler(cancel_download_callback, pattern="^cancel_"))

    # Message handlers
    app.add_handler(MessageHandler(filters.Regex(f"^({'|'.join(LANG_CODES.keys())})$"), set_language))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, smart_message_handler))

    async def set_commands(_):
        logger.info("Setting bot commands.")
        await app.bot.set_my_commands([
            BotCommand("start", "Запуск и выбор языка / Start and choose language"),
            BotCommand("languages", "Сменить язык / Change language"),
            BotCommand("search", "Поиск музыки / Search music"),
            BotCommand("copyright", "Информация об авторских правах / Copyright info"),
            BotCommand("stats", "Ваша статистика / Your stats")
        ])
    app.post_init = set_commands
    
    logger.info("Starting bot polling.")
    try:
        app.run_polling()
    except Exception as e:
        logger.critical(f"Bot polling failed: {e}", exc_info=True)

if __name__ == '__main__':
    main()
