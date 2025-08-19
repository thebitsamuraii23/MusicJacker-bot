
import os  # Import necessary libraries
import logging  # Import logging for debugging and information
import asyncio  # Import asyncio for asynchronous operations
import uuid
import tempfile  # Import tempfile for temporary file handling
import shutil  # Import shutil for file operations
import json  # Import json for handling JSON data
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand  # Import necessary Telegram bot components 
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler  # Import necessary Telegram bot handlers
from dotenv import load_dotenv  # Import dotenv for environment variable management 
import yt_dlp  # Import yt-dlp for downloading media
from PIL import Image  # Import PIL for image processing
import io  # Import io for in-memory byte streams
from urllib.request import urlopen
from urllib.parse import urlparse, parse_qs, quote_plus
from mutagen.mp4 import MP4, MP4Cover  # Import mutagen for editing M4A metadata
from yt_dlp.utils import sanitize_filename  # Import sanitize_filename from yt-dlp

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
REQUIRED_CHANNELS = ["@ytdlpdeveloper"]  # Channel to which users must be subscribed
TELEGRAM_FILE_SIZE_LIMIT_BYTES = 50 * 1024 * 1024  # 50 MB in bytes
TELEGRAM_FILE_SIZE_LIMIT_TEXT = "50 МБ"  # Text representation of the file size limit 
USER_LANGS_FILE = "user_languages.json"  # File to store user language preferences
# Keyboard for language selection
LANG_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["Русский", "English"],
        ["Español", "Azərbaycan dili"],
        ["Türkçe", "العربية"]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)
# Mapping language names to codes
LANG_CODES = {
    "Русский": "ru", "English": "en", "Español": "es",
    "Azərbaycan dili": "az", "Türkçe": "tr",
    "العربية": "ar"
}

SEARCH_RESULTS_LIMIT = 10  # Search results limit
MAX_CONCURRENT_DOWNLOADS_PER_USER = int(os.getenv('MAX_CONCURRENT_DOWNLOADS_PER_USER', '3'))
user_langs = {}  # Dictionary for storing user language preferences

# Dictionaries with localized texts
LANGUAGES = {
    "ru": {
        "start": (
            "👋 Привет! Добро пожаловать в музыкального бота! 🎶\n\n"
            "Я помогу скачать аудио из YouTube и SoundCloud в формате M4A.\n\n"
            "🔗 Просто отправьте ссылку на видео или трек — и получите музыку!\n\n"
            f"📢 Для работы подпишитесь на канал {REQUIRED_CHANNELS[0]}.\n\n"
            "🔍 Хотите найти трек по названию? Используйте команду /search и выберите нужную песню!\n\n"
            "✨ Приятного прослушивания!\n"
            "\nПоддержка и новости — @ytdlpdeveloper | artoflife2303.github.io/miniblog"
        ),
        "choose_lang": "Выберите язык / Choose language:",
        "not_subscribed": f"Чтобы пользоваться ботом, подпишитесь на канал {REQUIRED_CHANNELS[0]} и попробуйте снова.",
        "checking": "Проверяю ссылку...",
        "not_youtube": "Это не поддерживаемая ссылка. Отправьте корректную ссылку на YouTube или SoundCloud.",
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
        "url_error_generic": "Не удалось обработать URL. Убедитесь, что это корректная ссылка на YouTube или SoundCloud.",
        "search_prompt": (
            "Введите название трека или исполнителя. После чего, нажмите на музыку, она загрузится в формате M4A.\n"
            "Введите /cancel для отмены поиска.\n"
            "Введите /search для поиска музыки по названию (YouTube)."
        ),
        "searching": "Ищу музыку...",
        "unsupported_url_in_search": "Ссылка не поддерживается. Пожалуйста, проверьте другую ссылку или попробуйте другой запрос. (Альтернативно, если у вас не получилось, вы можете загрузить трек от другого исполнителя или Remix)",
        "no_results": "Ничего не найдено. Попробуйте другой запрос.",
        "choose_track": "Выберите трек для скачивания M4A:",
        "downloading_selected_track": "Скачиваю выбранный трек в M4A...",
        "copyright_pre": "⚠️ Внимание! Загружаемый вами материал может быть защищён авторским правом. Используйте только для личных целей. Если вы являетесь правообладателем и считаете, что ваши права нарушены, напишите на copyrightytdlpbot@gmail.com для удаления контента.",
        "copyright_post": "⚠️ Данный материал может быть защищён авторским правом. Используйте только для личных целей. Если вы правообладатель и считаете, что ваши права нарушены, напишите на copyrightytdlpbot@gmail.com.",
        "copyright_command": "⚠️ Внимание! Все материалы, скачиваемые через этого бота, могут быть защищены авторским правом. Используйте только для личных целей. Если вы правообладатель и считаете, что ваши права нарушены, напишите на copyrightytdlpbot@gmail.com, и мы удалим соответствующий контент."
    },
    "en": {
        "start": (
            "👋 Hello! Welcome to the music bot! 🎶\n\n"
            "I can help you download audio from YouTube and SoundCloud in M4A format.\n\n"
            "🔗 Just send a link to a video or track — and get your music!\n\n"
            f"📢 To use the bot, please subscribe to the channel {REQUIRED_CHANNELS[0]}.\n\n"
            "🔍 Want to search for a song by name? Use /search and pick your favorite!\n\n"
            "✨ Enjoy your music!\n"
            "\nSupport & news — @ytdlpdeveloper | artoflife2303.github.io/miniblog"
        ),
        "choose_lang": "Choose language:",
        "not_subscribed": f"To use the bot, please subscribe to the channel {REQUIRED_CHANNELS[0]} and try again.",
        "checking": "Checking link...",
        "not_youtube": "This is not a supported link. Please send a valid YouTube or SoundCloud link.",
        "downloading_audio": "Downloading audio... Please wait.",
        "download_progress": "Downloading: {percent} at {speed}, ETA ~{eta}",
        "too_big": f"File is too large (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Try another video or track.",
        "done_audio": "Done! Audio sent.",
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
            "Enter the track name or artist. Then click on the music, it will download in M4A format.\n"
            "Enter /cancel to cancel the search.\n"
            "Enter /search to search for music by name (YouTube)."
        ),
        "searching": "Searching for music...",
        "unsupported_url_in_search": "The link is not supported. Please check the link or try another query. (Alternatively, if it didn't work, you can download a track from another artist or Remix)",
        "no_results": "Nothing found. Try another query.",
        "choose_track": "Select a track to download in M4A:",
        "downloading_selected_track": "Downloading the selected track in M4A...",
        "copyright_pre": "⚠️ Warning! The material you are about to download may be protected by copyright. Use for personal purposes only. If you are a copyright holder and believe your rights are being violated, please contact copyrightytdlpbot@gmail.com for removal.",
        "copyright_post": "⚠️ This material may be protected by copyright. Use for personal purposes only. If you are a copyright holder and believe your rights are being violated, contact copyrightytdlpbot@gmail.com.",
        "copyright_command": "⚠️ Warning! All materials downloaded via this bot may be protected by copyright. Use for personal purposes only. If you are a copyright holder and believe your rights are being violated, contact copyrightytdlpbot@gmail.com and we will remove the content."
    },
    "es": {
        "start": (
            "👋 ¡Hola! ¡Bienvenido al bot musical! 🎶\n\n"
            "Te ayudo a descargar audio de YouTube y SoundCloud en formato M4A.\n\n"
            "🔗 Solo envía un enlace de video o pista — ¡y recibe tu música!\n\n"
            f"📢 Para usar el bot, suscríbete al canal {REQUIRED_CHANNELS[0]}.\n\n"
            "🔍 ¿Quieres buscar una canción por nombre? Usa /search y elige tu favorita.\n\n"
            "✨ ¡Disfruta tu música!\n"
            "\nSoporte y novedades — @ytdlpdeveloper | artoflife2303.github.io/miniblog"
        ),
        "choose_lang": "Elige idioma:",
        "not_subscribed": f"Para usar el bot, suscríbete al canal {REQUIRED_CHANNELS[0]} y vuelve a intentarlo.",
        "checking": "Verificando enlace...",
        "not_youtube": "Este enlace no es compatible. Por favor, envía un enlace válido de YouTube o SoundCloud.",
        "downloading_audio": "Descargando audio... Por favor espera.",
        "download_progress": "Descargando: {percent} a {speed}, queda ~{eta}",
        "too_big": f"El archivo es demasiado grande (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Prueba con otro video o pista.",
        "done_audio": "¡Listo! Audio enviado.",
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
            "Ingrese el nombre de la pista o artista. Luego haga clic en la música, se descargará en formato M4A.\n"
            "Ingrese /cancel para cancelar la búsqueda.\n"
            "Ingrese /search para buscar música por nombre (YouTube)."
        ),
        "searching": "Buscando música...",
        "unsupported_url_in_search": "El enlace no es compatible. Por favor, compruebe el enlace o pruebe con otra consulta. (Alternativamente, si no funcionó, puede descargar una pista de otro artista o un Remix)",
        "no_results": "No se encontraron resultados. Intente con otra consulta.",
        "choose_track": "Seleccione una pista para descargar en M4A:",
        "downloading_selected_track": "Descargando la pista seleccionada en M4A...",
        "copyright_pre": "⚠️ ¡Atención! El material que está a punto de descargar puede estar protegido por derechos de autor. Úselo solo para fines personales. Si es titular de derechos y cree que se están violando sus derechos, escriba a copyrightytdlpbot@gmail.com para eliminar el contenido.",
        "copyright_post": "⚠️ Este material puede estar protegido por derechos de autor. Úselo solo para fines personales. Si es titular de derechos y cree que se están violando sus derechos, escriba a copyrightytdlpbot@gmail.com.",
        "copyright_command": "⚠️ ¡Atención! Todo el material descargado a través de este bot puede estar protegido por derechos de autor. Úselo solo para fines personales. Si es titular de derechos y cree que se están violando sus derechos, escriba a copyrightytdlpbot@gmail.com y eliminaremos el contenido."
    },
    "tr": {
        "start": (
            "👋 Merhaba! Müzik botuna hoş geldin! 🎶\n\n"
            "YouTube ve SoundCloud'dan M4A formatında ses indirmen için buradayım.\n\n"
            "🔗 Sadece bir video veya parça bağlantısı gönder — müziğin hazır!\n\n"
            f"📢 Botu kullanmak için {REQUIRED_CHANNELS[0]} kanalına abone olmalısın.\n\n"
            "🔍 Şarkı ismiyle arama yapmak ister misin? /search yaz ve favorini seç!\n\n"
            "✨ Keyifli dinlemeler!\n"
            "\nDestek ve haberler — @ytdlpdeveloper | artoflife2303.github.io/miniblog"
        ),
        "choose_lang": "Dil seçin:",
        "not_subscribed": f"Botu kullanmak için lütfen {REQUIRED_CHANNELS[0]} kanalına abone olun ve tekrar deneyin.",
        "checking": "Bağlantı kontrol ediliyor...",
        "not_youtube": "Bu desteklenmeyen bir bağlantı. Lütfen geçerli bir YouTube veya SoundCloud bağlantısı gönderin.",
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
        "url_error_generic": "URL işlenemedi. Geçerli bir YouTube veya SoundCloud bağlantısı olduğundan emin olun.",
        "search_prompt": (
            "Parça adı veya sanatçı adı girin. Ardından müziğe tıklayın, M4A formatında indirilecektir.\n"
            "Aramayı iptal etmek için /cancel yazın.\n"
            "Müzik adıyla arama yapmak için /search yazın (YouTube)."
        ),
        "searching": "Müzik aranıyor...",
        "unsupported_url_in_search": "Bağlantı desteklenmiyor. Lütfen bağlantıyı kontrol edin veya başka bir sorgu deneyin. (Alternatif olarak, işe yaramadıysa, başka bir sanatçıdan veya Remix bir parça indirebilirsiniz)",
        "no_results": "Hiçbir sonuç bulunamadı. Başka bir sorgu deneyin.",
        "choose_track": "M4A olarak indirmek için bir parça seçin:",
        "downloading_selected_track": "Seçilen parça M4A olarak indiriliyor...",
        "copyright_pre": "⚠️ Dikkat! İndirmek üzere olduğunuz materyal telif hakkı ile korunabilir. Yalnızca kişisel kullanım için kullanın. Eğer telif hakkı sahibiyseniz ve haklarınızın ihlal edildiğini düşünüyorsanız, lütfen copyrightytdlpbot@gmail.com adresine yazın.",
        "copyright_post": "⚠️ Bu materyal telif hakkı ile korunabilir. Yalnızca kişisel kullanım için kullanın. Eğer telif hakkı sahibiyseniz ve haklarınızın ihlal edildiğini düşünüyorsanız, lütfen copyrightytdlpbot@gmail.com adresine yazın.",
        "copyright_command": "⚠️ Dikkat! Bu bot aracılığıyla indirilen tüm materyaller telif hakkı ile korunabilir. Yalnızca kişisel kullanım için kullanın. Eğer telif hakkı sahibiyseniz ve haklarınızın ihlal edildiğini düşünüyorsanız, lütfen copyrightytdlpbot@gmail.com adresine yazın, ilgili içeriği kaldıracağız."
    },
    "ar": {
        "start": (
            "👋 مرحبًا بك في بوت الموسيقى! 🎶\n\n"
            "سأساعدك في تنزيل الصوت من YouTube و SoundCloud بصيغة M4A.\n\n"
            "🔗 فقط أرسل رابط فيديو أو مقطع — وستحصل على موسيقاك!\n\n"
            f"📢 لاستخدام البوت، يرجى الاشتراك في القناة {REQUIRED_CHANNELS[0]}.\n\n"
            "🔍 هل تريد البحث عن أغنية بالاسم؟ استخدم /search واختر المفضلة لديك!\n\n"
            "✨ استمتع بالموسيقى!\n"
            "\nالدعم والأخبار — @ytdlpdeveloper | artoflife2303.github.io/miniblog"
        ),
        "choose_lang": "اختر اللغة:",
        "not_subscribed": f"لاستخدام البوت، يرجى الاشتراك في قناة {REQUIRED_CHANNELS[0]} والمحاولة مرة أخرى.",
        "checking": "جاري التحقق من الرابط...",
        "not_youtube": "هذا ليس رابطًا مدعومًا. يرجى إرسال رابط YouTube أو SoundCloud صالح.",
        "downloading_audio": "جاري تنزيل الصوت... يرجى الانتظار.",
        "download_progress": "جاري التنزيل: {percent} بسرعة {speed}، متبقي ~{eta}",
        "too_big": f"الملف كبير جدًا (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). جرب فيديو أو مسارًا آخر.",
        "done_audio": "تم! تم إرسال الصوت.",
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
            "أدخل اسم المقطع الصوتي أو الفنان. ثم انقر على الموسيقى، سيتم تنزيلها بصيغة M4A.\n"
            "أدخل /cancel لإلغاء البحث.\n"
            "أدخل /search للبحث عن الموسيقى بالاسم (يوتيوب)."
        ),
        "searching": "جاري البحث عن الموسيقى...",
        "unsupported_url_in_search": "الرابط غير مدعوم. يرجى التحقق من الرابط أو تجربة استعلام آخر. (بدلاً من ذلك، إذا لم ينجح الأمر, يمكنك تنزيل مقطع صوتي من فنان آخر أو ريمكس)",
        "no_results": "لم يتم العثور على شيء. حاول استعلامًا آخر.",
        "choose_track": "حدد مسارًا لتنزيله بصيغة M4A:",
        "downloading_selected_track": "جاري تنزيل المسار المحدد بصيغة M4A...",
        "copyright_pre": "⚠️ تحذير! قد يكون المحتوى الذي توشك على تنزيله محميًا بحقوق النشر. استخدمه للأغراض الشخصية فقط. إذا كنت صاحب حقوق وتعتقد أن حقوقك منتهكة, يرجى التواصل عبر copyrightytdlpbot@gmail.com لحذف المحتوى.",
        "copyright_post": "⚠️ قد يكون هذا المحتوى محميًا بحقوق النشر. استخدمه للأغراض الشخصية فقط. إذا كنت صاحب حقوق وتعتقد أن حقوقك منتهكة, يرجى التواصل عبر copyrightytdlpbot@gmail.com.",
        "copyright_command": "⚠️ تحذير! جميع المواد التي يتم تنزيلها عبر هذا البوت قد تكون محمية بحقوق النشر. استخدمها للأغراض الشخصية فقط. إذا كنت صاحب حقوق وتعتقد أن حقوقك منتهكة, يرجى التواصل عبر copyrightytdlpbot@gmail.com وسنقوم بحذف المحتوى."
    },
    "az": {
        "start": (
            "👋 Salam! Musiqi botuna xoş gəlmisiniz! 🎶\n\n"
            "YouTube və SoundCloud-dan M4A formatında səs yükləmək üçün buradayam.\n\n"
            "🔗 Sadəcə video və ya trek linki göndərin — musiqiniz hazırdır!\n\n"
            f"📢 Botdan istifadə üçün {REQUIRED_CHANNELS[0]} kanalına abunə olun.\n\n"
            "🔍 Mahnını adla axtarmaq istəyirsiniz? /search yazın və sevdiyinizi seçin!\n\n"
            "✨ Xoş dinləmələr!\n"
            "\nDəstək və yeniliklər — @ytdlpdeveloper | artoflife2303.github.io/miniblog"
        ),
        "choose_lang": "Dil seçin:",
        "not_subscribed": f"Botdan istifadə etmək üçün zəhmət olmasa {REQUIRED_CHANNELS[0]} kanalına abunə olun və yenidən cəhd edin.",
        "checking": "Link yoxlanılır...",
        "not_youtube": "Bu dəstəklənməyən bir bağlantıdır. Zəhmət olmasa, etibarlı bir YouTube və ya SoundCloud linki göndərin.",
        "downloading_audio": "Səs yüklənir... Zəhmət olmasa gözləyin.",
        "download_progress": "Yüklənir: {percent} sürətlə {speed}, qalıb ~{eta}",
        "too_big": f"Fayl çox böyükdür (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Başqa bir video və ya trek sınayın.",
        "done_audio": "Hazırdır! Səs göndərildi.",
        "error": "Nəsə səhv getdi. Linki yoxlayın və ya sonra cəhd edin!\n",
        "error_private_video": "Bu şəxsi videodur və yüklənə bilməz.",
        "error_video_unavailable": "Video mövcud deyil.",
        "sending_file": "{total} fayldan {index}-i göndərilir...",
        "cancel_button": "Ləğv et",
        "cancelling": "Yükləmə ləğv edilir...",
        "cancelled": "Yükləmə ləğv edildi.",
        "download_in_progress": "Başqa bir yükləmə artıq davam edir. Zəhmət olmasa gözləyin və ya ləğv edin.",
        "already_cancelled_or_done": "Yükləmə artıq ləğv edilib və ya tamamlanıb.",
        "url_error_generic": "URL emal edilə bilmədi. Etibarlı bir YouTube və ya SoundCloud linki olduğundan əmin olun.",
        "search_prompt": (
            "Trek adı və ya ifaçı adı daxil edin. Sonra musiqiyə tıklayın, M4A formatında yüklənəcək.\n"
            "/cancel daxil edərək axtarışı ləğv edin.\n"
            "/search daxil edərək adla musiqi axtarın (YouTube)."
        ),
        "searching": "Musiqi axtarılır...",
        "unsupported_url_in_search": "Link dəstəklənmir. Zəhmət olmasa, linki yoxlayın və ya başqa bir sorğu sınayın. (Alternativ olaraq, əgər işləmədisə, başqa bir ifaçıdan və ya Remix bir trek yükləyə bilərsiniz)",
        "no_results": "Heç nə tapılmadı. Başqa bir sorğu sınayın.",
        "choose_track": "M4A olaraq yükləmək üçün bir trek seçin:",
        "downloading_selected_track": "Seçilən trek M4A olaraq yüklənir...",
        "copyright_pre": "⚠️ Diqqət! Yüklədiyiniz material müəllif hüquqları ilə qoruna bilər. Yalnız şəxsi istifadə üçün istifadə edin. Əgər siz hüquq sahibisiniz və hüquqlarınızın pozulduğunu düşünürsənsə, zəhmət olmasa copyrightytdlpbot@gmail.com ünvanına yazın.",
        "copyright_post": "⚠️ Bu material müəllif hüquqları ilə qoruna bilər. Yalnız şəxsi istifadə üçün istifadə edin. Əgər siz hüquq sahibisiniz və hüquqlarınızın pozulduğunu düşünürsə, copyrightytdlpbot@gmail.com ünvanına yazın.",
        "copyright_command": "⚠️ Diqqət! Bu bot vasitəsilə yüklənən bütün materiallar müəllif hüquqları ilə qoruna bilər. Yalnız şəxsi istifadə üçün istifadə edin. Əgər siz hüquq sahibisiniz və hüquqlarınızın pozulduğunu düşünürsə, copyrightytdlpbot@gmail.com ünvanına yazın, müvafiq məzmunu siləcəyik."
    }
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

async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Sends the user a keyboard to choose a language.
    """
    logger.info(f"User {update.effective_user.id} requested language choice.")
    await update.message.reply_text(
        LANGUAGES["ru"]["choose_lang"],
        reply_markup=LANG_KEYBOARD
    )

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

async def check_subscription(user_id: int, bot) -> bool:
    """
    Checks if the user is subscribed to all required channels.
    """
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status not in ("member", "administrator", "creator"):
                logger.info(f"User {user_id} is not subscribed to {channel}")
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
    yt_dlp_logger.setLevel(logging.WARNING)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url_to_download])
        return True
    except yt_dlp.utils.UnsupportedError:
        raise Exception("Unsupported URL: {}".format(url_to_download))
    except Exception as e:
        logger.error(f"yt-dlp download error: {e}")
        raise

def compress_image(image_path, max_size=204800):
    """
    Compresses the image to be under the specified max_size in bytes.
    """
    # image_path may be a filesystem path or raw bytes
    if isinstance(image_path, (bytes, bytearray)):
        img = Image.open(io.BytesIO(image_path))
    else:
        img = Image.open(image_path)

    try:
        if img.mode in ('RGBA', 'LA'):
            # remove alpha channel by converting to white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        output = io.BytesIO()
        quality = 95
        # Try reducing quality first
        while True:
            output.seek(0)
            output.truncate(0)
            img.save(output, 'JPEG', quality=quality, optimize=True, progressive=True)
            size = output.tell()
            if size <= max_size or quality <= 20:
                break
            quality -= 5

        # If still too big, progressively resize image until it fits or gets small
        if output.tell() > max_size:
            # resize loop
            width, height = img.size
            while output.tell() > max_size and (width > 200 or height > 200):
                width = int(width * 0.9)
                height = int(height * 0.9)
                img_resized = img.resize((width, height), Image.LANCZOS)
                output.seek(0)
                output.truncate(0)
                q = max(20, quality - 5)
                img_resized.save(output, 'JPEG', quality=q, optimize=True, progressive=True)
                if output.tell() <= max_size:
                    break
                img = img_resized

        return output.getvalue()
    finally:
        try:
            img.close()
        except Exception:
            pass

async def handle_download(update_or_query, context: ContextTypes.DEFAULT_TYPE, url: str, texts: dict, user_id: int):
    """
    Handles the download of an audio file from YouTube or SoundCloud.
    """
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
    # active_downloads structure: {user_id: {task_id: {'task': task, 'temp_dir': str, 'status_message_id': int}}}
    loop = asyncio.get_running_loop()
    # task_id may be registered by the caller; try to discover it from existing active_downloads
    task_id = None
    user_tasks = active_downloads.get(user_id, {})
    # find a task entry that points to the current coroutine (best-effort matching)
    for tid, info in user_tasks.items():
        if info.get('task') and info['task'] == asyncio.current_task():
            task_id = tid
            break
    # if not found, generate a task id (caller normally provides one)
    if not task_id:
        task_id = uuid.uuid4().hex
        user_tasks = active_downloads.setdefault(user_id, {})
        user_tasks[task_id] = {'task': asyncio.current_task()}

    cancel_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(texts["cancel_button"], callback_data=f"cancel_{user_id}_{task_id}")]])

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
                logger.debug(f"Could not edit status message: {e}")
                pass

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
        await context.bot.send_message(chat_id=chat_id, text=texts.get("copyright_pre"))
        status_message = await context.bot.send_message(chat_id=chat_id, text=texts["downloading_audio"], reply_markup=cancel_keyboard)
        # store status message id for potential edits/cancellation
        active_downloads.setdefault(user_id, {})[task_id]['status_message_id'] = status_message.message_id
        await asyncio.sleep(10)  # Timeout for download
        temp_dir = tempfile.mkdtemp()
        # store temp_dir for this task
        active_downloads.setdefault(user_id, {})[task_id]['temp_dir'] = temp_dir
        ydl_opts = {
            'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
            'format': 'bestaudio/best',
            'cookiefile': cookies_path if os.path.exists(cookies_path) else None,
            'progress_hooks': [progress_hook],
            'nocheckcertificate': True,
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': ffmpeg_path if FFMPEG_IS_AVAILABLE else None,
            'noplaylist': True,
            'writethumbnail': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
                'preferredquality': '320',
            }],
            'verbose': True
        }
        ydl_opts = {k: v for k, v in ydl_opts.items() if v is not None}

        # Prefer YouTube Music links when possible to get richer metadata (artist, track, featured, thumbnails)
        def convert_to_ytmusic(original_url: str) -> str:
            """Convert standard YouTube/watch or youtu.be links to music.youtube.com watch links.
            Leave other URLs untouched.
            """
            try:
                u = original_url.strip()
                if 'music.youtube.com' in u:
                    return u
                # short youtu.be links
                if 'youtu.be/' in u:
                    parts = u.split('/')
                    vid = parts[-1].split('?')[0]
                    return f'https://music.youtube.com/watch?v={vid}'
                parsed = urlparse(u)
                if 'youtube.com' in parsed.netloc:
                    qs = parse_qs(parsed.query)
                    v = qs.get('v')
                    if v:
                        return f'https://music.youtube.com/watch?v={v[0]}'
                return original_url
            except Exception:
                return original_url

        url_to_use = convert_to_ytmusic(url)
        logger.info(f"Starting download for {url} (using {url_to_use}) by user {user_id} (task {task_id})")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url_to_use, download=False)
            # Prefer music-specific fields when available
            title = info.get('track') or info.get('title') or 'Unknown'
            # artist may be a string or a list under 'artists'
            artist = ''
            if info.get('artist'):
                artist = info.get('artist')
            elif info.get('artists') and isinstance(info.get('artists'), (list, tuple)):
                artist = ', '.join([a.get('name') if isinstance(a, dict) else str(a) for a in info.get('artists')])
            else:
                artist = info.get('uploader') or info.get('channel') or ''
            # put featured artists into title if present
            if not info.get('track') and '-' in title and not artist:
                # try split 'Artist - Title'
                parts = title.split('-')
                if len(parts) >= 2:
                    possible_artist = parts[0].strip()
                    possible_title = '-'.join(parts[1:]).strip()
                    if possible_artist and possible_title:
                        artist = possible_artist
                        title = possible_title

        # perform the blocking download with the (possibly converted) URL
        await asyncio.to_thread(blocking_yt_dlp_download, ydl_opts, url_to_use)

        all_files = os.listdir(temp_dir)
        audio_files = [f for f in all_files if f.endswith('.m4a')]
        thumbnail_files = [f for f in all_files if f.lower().endswith(('.jpg', '.jpeg', '.webp'))]

        if not audio_files:
            await update_status_message_async(texts["error"] + " (audio file not found)", show_cancel_button=False)
            return

        downloaded_files_info = []
        # attempt to get thumbnail URL from info
        thumbnail_url = None
        try:
            if isinstance(info.get('thumbnail'), str) and info.get('thumbnail'):
                thumbnail_url = info.get('thumbnail')
            elif info.get('thumbnails'):
                # choose the largest thumbnail if available
                thumbs = info.get('thumbnails')
                if isinstance(thumbs, list) and thumbs:
                    # sort by resolution if available
                    thumbs_sorted = sorted(thumbs, key=lambda x: int(x.get('width') or 0), reverse=True)
                    thumbnail_url = thumbs_sorted[0].get('url')
        except Exception:
            thumbnail_url = None

        for audio_file in audio_files:
            audio_path = os.path.join(temp_dir, audio_file)
            jpeg_data = None

            # try remote thumbnail first
            if thumbnail_url:
                try:
                    with urlopen(thumbnail_url, timeout=15) as resp:
                        raw = resp.read()
                        jpeg_data = compress_image(raw, max_size=200000)
                except Exception as e:
                    logger.debug(f"Could not download or compress remote thumbnail {thumbnail_url}: {e}")

            # fallback to local thumbnail files
            if not jpeg_data and thumbnail_files:
                thumbnail_path = os.path.join(temp_dir, thumbnail_files[0])
                try:
                    jpeg_data = compress_image(thumbnail_path, max_size=200000)
                    try:
                        os.remove(thumbnail_path)
                    except Exception:
                        pass
                except Exception as e:
                    logger.debug(f"Could not compress local thumbnail {thumbnail_path}: {e}")

            # embed metadata and cover if available
            try:
                mp4 = MP4(audio_path)
                # Title / track
                mp4['\xa9nam'] = title
                # Artist: try multiple possible fields
                tag_artist = artist
                if not tag_artist and info.get('album_artist'):
                    tag_artist = info.get('album_artist')
                if not tag_artist and info.get('uploader'):
                    tag_artist = info.get('uploader')
                mp4['\xa9ART'] = tag_artist or ''

                # Album
                if info.get('album'):
                    mp4['\xa9alb'] = info.get('album')

                # Year / release date
                if info.get('release_year'):
                    mp4['\xa9day'] = str(info.get('release_year'))
                elif info.get('release_date'):
                    mp4['\xa9day'] = str(info.get('release_date'))

                # Add composer/performer fields for featured artists if available
                if info.get('artists') and isinstance(info.get('artists'), (list, tuple)):
                    performers = []
                    for a in info.get('artists'):
                        if isinstance(a, dict):
                            name = a.get('name')
                        else:
                            name = str(a)
                        if name:
                            performers.append(name)
                    if performers:
                        mp4['\xa9ART'] = ', '.join(performers)

                if jpeg_data:
                    mp4['covr'] = [MP4Cover(jpeg_data, imageformat=MP4Cover.FORMAT_JPEG)]
                mp4.save()
            except Exception as e:
                logger.error(f"Error embedding metadata or cover for {audio_path}: {e}")

            new_filename = sanitize_filename(f"{artist} - {title}.m4a" if artist else f"{title}.m4a")
            new_path = os.path.join(temp_dir, new_filename)
            os.rename(audio_path, new_path)

            downloaded_files_info.append((new_path, title))

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

            try:
                with open(file_to_send, 'rb') as f_send:
                    await context.bot.send_audio(
                        chat_id=chat_id, audio=f_send, title=title_str, performer=artist,
                        filename=os.path.basename(file_to_send)
                    )
                await context.bot.send_message(chat_id=chat_id, text=texts.get("copyright_post"))
                logger.info(f"Successfully sent audio for {url} to user {user_id}")
            except Exception as e:
                logger.error(f"Error sending audio file {os.path.basename(file_to_send)} to user {user_id}: {e}")
                await context.bot.send_message(chat_id=chat_id, text=f"{texts['error']} (Error sending file {os.path.basename(file_to_send)})")

        await update_status_message_async(texts["done_audio"], show_cancel_button=False)

    except asyncio.CancelledError:
        logger.info(f"Download cancelled for user {user_id}.")
        if status_message:
            await update_status_message_async(texts["cancelled"], show_cancel_button=False)
        else:
            await context.bot.send_message(chat_id=chat_id, text=texts["cancelled"])
    except Exception as e:
        if 'Unsupported URL' in str(e) or 'unsupported url' in str(e).lower():
            if status_message:
                await update_status_message_async("The link is not supported. Please check the link or try another query.", show_cancel_button=False)
            else:
                await context.bot.send_message(chat_id=chat_id, text="The link is not supported. Please check the link or try another query.")
            return
        logger.critical(f"Unhandled error in handle_download for user {user_id}: {e}", exc_info=True)
        if status_message:
            await update_status_message_async(texts["error"] + str(e), show_cancel_button=False)
        else:
            await context.bot.send_message(chat_id=chat_id, text=texts["error"] + str(e))
    finally:
        # cleanup this task's temp dir
        try:
            task_info = context.bot_data.get('active_downloads', {}).get(user_id, {}).get(task_id, {})
            td = task_info.get('temp_dir') or temp_dir
            if td and os.path.exists(td):
                shutil.rmtree(td, ignore_errors=True)
                logger.info(f"Cleaned up temporary directory {td} for user {user_id} (task {task_id}).")
        except Exception as e:
            logger.debug(f"Error cleaning temp dir for user {user_id} task {task_id}: {e}")

        # remove only this task entry
        try:
            if user_id in context.bot_data.get('active_downloads', {}):
                user_tasks = context.bot_data['active_downloads'][user_id]
                if task_id in user_tasks:
                    del user_tasks[task_id]
                # if no more tasks for this user, remove the user key
                if not user_tasks:
                    del context.bot_data['active_downloads'][user_id]
                    logger.info(f"No more active downloads for user {user_id}.")
                logger.info(f"Removed active download task {task_id} for user {user_id}.")
        except Exception as e:
            logger.debug(f"Error removing active download entry for user {user_id} task {task_id}: {e}")

async def search_youtube(query: str):
    """
    Performs a search for videos on YouTube.
    """
    if is_url(query):
        return 'unsupported_url'

    # Try YouTube Music search page first to get music-specific metadata (track, artists, album, thumbnails)
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'extract_flat': True,
        'nocheckcertificate': True,
        'default_search': None,
        'noplaylist': True
    }
    try:
        # Build a YT Music search URL
        safe_q = quote_plus(query)
        music_search_url = f"https://music.youtube.com/search?q={safe_q}"
        logger.info(f"Searching YouTube Music for query: {query}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(music_search_url, download=False)
            # yt-dlp may return 'entries' in different shapes for music search; try to normalize
            entries = []
            if isinstance(info, dict):
                if info.get('entries'):
                    entries = info.get('entries')
                elif info.get('results'):
                    entries = info.get('results')
            elif isinstance(info, list):
                entries = info
            # Helper: decide if an entry is an audio/music track (prefer these)
            def is_music_entry(e: dict) -> bool:
                try:
                    if not isinstance(e, dict):
                        return False
                    # direct music-specific fields
                    if e.get('track'):
                        return True
                    if e.get('artists'):
                        return True
                    # extractor key / ie_key containing music
                    ie = str(e.get('ie_key') or e.get('extractor') or '').lower()
                    if 'music' in ie:
                        return True
                    # youtube music urls
                    url = e.get('url') or e.get('webpage_url') or ''
                    if 'music.youtube.com' in url:
                        return True
                    # reasonable duration (shorter tracks) and not live
                    dur = e.get('duration')
                    if isinstance(dur, (int, float)) and dur > 0 and dur < 10 * 60:
                        if not e.get('is_live'):
                            return True
                except Exception:
                    return False
                return False

            # Filter for music-like entries
            music_entries = [ent for ent in entries if is_music_entry(ent)] if entries else []
            # If we got no music-like results, fall back to standard ytsearch
            if not music_entries:
                logger.info(f"No music-specific entries from YT Music search, falling back to ytsearch for query: {query}")
                search_query = f"ytsearch{SEARCH_RESULTS_LIMIT}:{query}"
                info = ydl.extract_info(search_query, download=False)
                entries = info.get('entries', []) or []
                music_entries = [ent for ent in entries if is_music_entry(ent)] or entries
            if not music_entries:
                logger.info(f"No entries found for search: {query}")
                return []
            # Ensure a list and slice to limit
            results_list = music_entries if isinstance(music_entries, list) else list(music_entries)
            return results_list[:SEARCH_RESULTS_LIMIT]
    except yt_dlp.utils.DownloadError as e:
        if 'Unsupported URL' in str(e) or 'unsupported url' in str(e).lower():
            logger.warning(f"Unsupported URL in search query: {query}")
            return 'unsupported_url'
        logger.error(f"DownloadError during YouTube search for {query}: {e}")
        return []
    except Exception as e:
        logger.critical(f"Unhandled error during YouTube search for {query}: {e}", exc_info=True)
        return []

def is_url(text):
    """
    Checks if a string is a YouTube or SoundCloud URL.
    """
    text = text.lower().strip()
    return (
        text.startswith("http://") or text.startswith("https://")
    ) and (
    "youtube.com/" in text or "youtu.be/" in text or "soundcloud.com/" in text or "music.youtube.com/" in text
    )

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Starts the music search process.
    """
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    logger.info(f"User {user_id} issued /search command.")
    await update.message.reply_text(texts["search_prompt"])
    context.user_data[f'awaiting_search_query_{user_id}'] = True

async def handle_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Processes the user's search query and displays the results.
    """
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    query_text = update.message.text.strip()
    logger.info(f"User {user_id} sent search query: '{query_text}'")

    await update.message.reply_text(texts["searching"])
    # perform search immediately (no artificial delay)
    results = await search_youtube(query_text)

    if results == 'unsupported_url':
        await update.message.reply_text(texts["unsupported_url_in_search"])
        context.user_data.pop(f'awaiting_search_query_{user_id}', None)
        return

    if not isinstance(results, list):
        results = []

    if not results:
        await update.message.reply_text(texts["no_results"])
        context.user_data.pop(f'awaiting_search_query_{user_id}', None)
        return

    keyboard = []
    for idx, entry in enumerate(results):
        title = entry.get('title', texts["no_results"])
        # Use index in callback_data to avoid invalid/too-long callback payloads
        keyboard.append([InlineKeyboardButton(f"{idx+1}. {title}", callback_data=f"searchsel_{user_id}_{idx}")])

    await update.message.reply_text(
        texts["choose_track"],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    # Store the full results list (by index) so callback handlers can retrieve safely
    context.user_data[f'search_results_{user_id}'] = results
    context.user_data.pop(f'awaiting_search_query_{user_id}', None)
    logger.info(f"User {user_id} receied {len(results)} search results.")

async def search_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the selection of a track from search results.
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.info(f"User {user_id} selected track from search: {query.data}")

    try:
        _, sel_user_id, idx_str = query.data.split("_", 2)
        sel_user_id = int(sel_user_id)
        sel_index = int(idx_str)
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

    # Retrieve the selected entry from stored search results
    stored = context.user_data.get(f'search_results_{sel_user_id}')
    if not stored or not isinstance(stored, (list, tuple)):
        await query.edit_message_text("Search results expired or invalid. Please /search again.")
        return
    if sel_index < 0 or sel_index >= len(stored):
        await query.edit_message_text("Invalid selection index. Please /search again.")
        return
    entry = stored[sel_index]
    video_id = entry.get('id') or entry.get('url') or ''
    # Prefer music.youtube.com URLs if present
    url = ''
    if entry.get('webpage_url') and 'music.youtube.com' in str(entry.get('webpage_url')):
        url = entry.get('webpage_url')
    elif entry.get('url') and 'music.youtube.com' in str(entry.get('url')):
        url = entry.get('url')
    elif video_id:
        # video_id may already be a full URL or an id
        if video_id.startswith('http'):
            url = video_id
        else:
            url = f"https://youtu.be/{video_id}"
    await query.edit_message_text(texts["downloading_selected_track"], reply_markup=None)
    # check per-user concurrency
    active_downloads = context.bot_data.setdefault('active_downloads', {})
    user_tasks = active_downloads.setdefault(user_id, {})
    if len(user_tasks) >= MAX_CONCURRENT_DOWNLOADS_PER_USER:
        await query.edit_message_text(texts.get('download_in_progress') + f" (max {MAX_CONCURRENT_DOWNLOADS_PER_USER})")
        return

    task_id = uuid.uuid4().hex
    task = asyncio.create_task(handle_download(query, context, url, texts, user_id))
    # register task
    user_tasks[task_id] = {'task': task}

async def smart_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Smart message handler: determines if the message is a URL or a search query.
    """
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    text = update.message.text.strip()
    logger.info(f"User {user_id} sent message: '{text}'")

    active_downloads = context.bot_data.setdefault('active_downloads', {})
    # if any running tasks exist for user, inform but allow other commands
    user_tasks = active_downloads.get(user_id, {})
    running = False
    for info in user_tasks.values():
        t = info.get('task')
        if t and not t.done():
            running = True
            break
    if running:
        await update.message.reply_text(texts["download_in_progress"])
    # do not block further commands; allow starting new downloads up to per-user limit

    is_subscribed = await check_subscription(user_id, context.bot)
    if not is_subscribed:
        await update.message.reply_text(texts["not_subscribed"])
        return

    if is_url(text):
        await update.message.reply_text(texts["checking"])
        # start background download task with concurrency control
        active_downloads = context.bot_data.setdefault('active_downloads', {})
        user_tasks = active_downloads.setdefault(user_id, {})
        if len(user_tasks) >= MAX_CONCURRENT_DOWNLOADS_PER_USER:
            await update.message.reply_text(texts.get('download_in_progress') + f" (max {MAX_CONCURRENT_DOWNLOADS_PER_USER})")
            return
        task_id = uuid.uuid4().hex
        task = asyncio.create_task(handle_download(update, context, text, texts, user_id))
        user_tasks[task_id] = {'task': task}
    else:
        if context.user_data.get(f'awaiting_search_query_{user_id}'):
            await handle_search_query(update, context)
        else:
            if len(text.split()) <= 5 and text.isascii():
                logger.info(f"User {user_id} auto-search for: '{text}'")
                await update.message.reply_text(texts["searching"])
                # perform search immediately (no artificial delay)
                results = await search_youtube(text)
                if not results or results == 'unsupported_url':
                    await update.message.reply_text(texts["no_results"])
                    return
                keyboard = []
                for idx, entry in enumerate(results):
                    title = entry.get('title', texts["no_results"])
                    keyboard.append([InlineKeyboardButton(f"{idx+1}. {title}", callback_data=f"searchsel_{user_id}_{idx}")])
                await update.message.reply_text(
                    texts["choose_track"],
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                # store results as list, keyed by index
                context.user_data[f'search_results_{user_id}'] = results
            else:
                await update.message.reply_text(texts["url_error_generic"])

async def cancel_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the request to cancel a download.
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    logger.info(f"User {user_id} requested download cancellation.")

    active_downloads = context.bot_data.setdefault('active_downloads', {})
    # callback data format: cancel_{user_id}_{task_id}
    try:
        _, uid_str, task_id = query.data.split("_", 2)
        uid = int(uid_str)
    except Exception as e:
        logger.error(f"Invalid cancel callback data: {query.data} - {e}")
        try:
            await query.edit_message_text(texts["already_cancelled_or_done"])
        except Exception:
            pass
        return

    if uid != user_id:
        try:
            await query.edit_message_text("This button is not for you.")
        except Exception:
            pass
        return

    user_tasks = active_downloads.get(user_id, {})
    task_info = user_tasks.get(task_id)
    if not task_info or not task_info.get('task') or task_info['task'].done():
        try:
            await query.edit_message_text(texts["already_cancelled_or_done"])
        except Exception as e:
            logger.debug(f"Could not edit message for already cancelled/done download: {e}")
            pass
        return

    task_info['task'].cancel()
    try:
        await query.edit_message_text(texts["cancelling"])
    except Exception as e:
        logger.debug(f"Could not edit message to 'cancelling': {e}")
        pass
    logger.info(f"Download task {task_id} cancelled for user {user_id}.")

async def copyright_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /copyright command and sends the copyright message.
    """
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    logger.info(f"User {user_id} issued /copyright command.")
    await update.message.reply_text(texts["copyright_command"])

def main():
    """
    Main function to run the bot.
    """
    load_user_langs()
    
    try:
        app = Application.builder().token(TOKEN).build()
        logger.info("Bot application built successfully.")
    except Exception as e:
        logger.critical(f"Failed to build bot application: {e}", exc_info=True)
        raise

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", choose_language))
    app.add_handler(CommandHandler("languages", choose_language))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("copyright", copyright_command))

    app.add_handler(MessageHandler(filters.Regex(f"^({'|'.join(LANG_CODES.keys())})$"), set_language))

    app.add_handler(CallbackQueryHandler(search_select_callback, pattern="^searchsel_"))
    app.add_handler(CallbackQueryHandler(cancel_download_callback, pattern="^cancel_"))

    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^({'|'.join(LANG_CODES.keys())})$"),
        smart_message_handler
    ))

    async def set_commands(_):
        """
        Sets the bot commands in Telegram.
        """
        logger.info("Setting bot commands.")
        await app.bot.set_my_commands([
            BotCommand("start", "Запуск и выбор языка / Start and choose language"),
            BotCommand("languages", "Сменить язык / Change language"),
            BotCommand("search", "Поиск музыки (YouTube/SoundCloud) / Search music (YouTube/SoundCloud)"),
            BotCommand("copyright", "Информация об авторских правах / Copyright info")
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
    await choose_language(update, context)
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    await update.message.reply_text(texts["copyright_post"])

if __name__ == '__main__':
    main()

# Developed and made by BitSamurai.
# Contact: copyrightytdlpbot@gmail.com
# Telegram bot link: t.me/ytdlpload_bot
