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

# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Получение токена бота из переменных окружения
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("Cant found TELEGRAM_BOT_TOKEN in environment variables.")

# Пути к файлам и переменные
cookies_path = os.getenv('COOKIES_PATH', 'youtube.com_cookies.txt')
ffmpeg_path_from_env = os.getenv('FFMPEG_PATH')
ffmpeg_path = ffmpeg_path_from_env if ffmpeg_path_from_env else '/usr/bin/ffmpeg'
FFMPEG_IS_AVAILABLE = os.path.exists(ffmpeg_path) and os.access(ffmpeg_path, os.X_OK)
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@ytdlpdeveloper")
TELEGRAM_FILE_SIZE_LIMIT_BYTES = 50 * 1024 * 1024
TELEGRAM_FILE_SIZE_LIMIT_TEXT = "50 МБ"

USER_LANGS_FILE = "user_languages.json"
# Клавиатура для выбора языка
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
# Сопоставление названий языков с кодами
LANG_CODES = {
    "Русский": "ru", "English": "en", "Español": "es",
    "Azərbaycan dili": "az", "Türkçe": "tr", "Українська": "uk",
    "العربية": "ar"
}

SEARCH_RESULTS_LIMIT = 10 # Лимит результатов поиска
user_langs = {} # Словарь для хранения языковых предпочтений пользователей

# Словари с локализованными текстами
LANGUAGES = {
    "ru": {
        "start": (
            "Привет! Я бот для скачивания аудио с YouTube и SoundCloud.\n\n"
            "Отправьте ссылку на YouTube или SoundCloud (видео или трек), и я предложу вам варианты загрузки аудио.\n\n"
            f"Для работы с ботом, подпишитесь на канал {REQUIRED_CHANNEL}.\n"
            "\n🎵 Также я умею искать музыку по названию! Просто напишите /search и найдите нужный трек.\n"
            "Приятного использования! "
            "Не забудьте подписаться на канал для обновлений и поддержки @ytdlpdeveloper. artoflife2303.github.io/miniblog "
            "Веб версия бота: youtubemusicdownloader.life, если не работает то bit.ly/ytmusicload"
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
        "url_error_generic": "Не удалось обработать URL. Убедитесь, что это корректная ссылка на YouTube или SoundCloud.",
        "search_prompt": (
            "Введите название трека или исполнителя. После чего, нажмите на музыку, она загрзится в формате MP3.\n"
            "Введите /cancel для отмены поиска.\n"
            "Введите /search для поиска музыки по названию (YouTube)."
        ),
        "searching": "Ищу музыку...",
        "unsupported_url_in_search": "Ссылка не поддерживается. Пожалуйста, проверьте другую ссылку или попробуйте другой запрос.(Альтернативно, если у вас не получилось, вы можете загрузить трек от другого исполнителя или Remix)",
        "no_results": "Ничего не найдено. Попробуйте другой запрос.",
        "choose_track": "Выберите трек для скачивания MP3:",
        "downloading_selected_track": "Скачиваю выбранный трек в MP3...",
        "copyright_pre": "⚠️ Внимание! Загружаемый вами материал может быть защищён авторским правом. Используйте только для личных целей. Если вы являетесь правообладателем и считаете, что ваши права нарушены, напишите на copyrightytdlpbot@gmail.com для удаления контента.",
        "copyright_post": "⚠️ Данный материал может быть защищён авторским правом. Используйте только для личных целей. Если вы правообладатель и считаете, что ваши права нарушены, напишите на copyrightytdlpbot@gmail.com.",
        "copyright_command": "⚠️ Внимание! Все материалы, скачиваемые через этого бота, могут быть защищены авторским правом. Используйте только для личных целей. Если вы правообладатель и считаете, что ваши права нарушены, напишите на copyrightytdlpbot@gmail.com, и мы удалим соответствующий контент."
    },
    "en": {
        "start": (
            "Hello! I am a bot for downloading audio from YouTube and SoundCloud.\n\n"
            "Send a YouTube or SoundCloud link (video or track), and I will offer you audio download options.\n\n"
            f"To use the bot, please subscribe to the channel {REQUIRED_CHANNEL}.\n"
            "\n🎵 I can also search for music by name! Just type /search and find your track.\n"
            "Enjoy!\n"
            "Don't forget to subscribe to the channel for updates and support @ytdlpdeveloper. artoflife2303.github.io/miniblog. \n"
            "Web version of the bot: youtubemusicdownloader.life, if it doesn't work then bit.ly/ytmusicload"
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
        "url_error_generic": "Failed to process URL. Make sure it's a valid YouTube or SoundCloud link.",
        "search_prompt": (
            "Enter the track name or artist. Then click on the music, it will download in MP3 format.\n"
            "Enter /cancel to cancel the search.\n"
            "Enter /search to search for music by name (YouTube)."
        ),
        "searching": "Searching for music...",
        "unsupported_url_in_search": "The link is not supported. Please check the link or try another query. (Alternatively, if it didn't work, you can download a track from another artist or Remix)",
        "no_results": "Nothing found. Try another query.",
        "choose_track": "Select a track to download in MP3:",
        "downloading_selected_track": "Downloading the selected track in MP3...",
        "copyright_pre": "⚠️ Warning! The material you are about to download may be protected by copyright. Use for personal purposes only. If you are a copyright holder and believe your rights are being violated, please contact copyrightytdlpbot@gmail.com for removal.",
        "copyright_post": "⚠️ This material may be protected by copyright. Use for personal purposes only. If you are a copyright holder and believe your rights are being violated, contact copyrightytdlpbot@gmail.com.",
        "copyright_command": "⚠️ Warning! All materials downloaded via this bot may be protected by copyright. Use for personal purposes only. If you are a copyright holder and believe your rights are being violated, contact copyrightytdlpbot@gmail.com and we will remove the content."
    },
    "es": {
        "start": (
            "¡Hola! Soy un bot para descargar audio de YouTube y SoundCloud.\n\n"
            "Envíame un enlace de YouTube o SoundCloud (video o pista) y te ofreceré opciones para descargar el audio.\n\n"
            f"Para usar el bot, suscríbete al canal {REQUIRED_CHANNEL}.\n"
            "\n🎵 ¡También puedo buscar música por nombre! Escribe /search y encuentra tu pista.\n"
            "¡Disfruta!"
            "No olvides suscribirte al canal para actualizaciones y soporte @ytdlpdeveloper. artoflife2303.github.io/miniblog. \n"
            "Versión web del bot: youtubemusicdownloader.life, si no funciona entonces bit.ly/ytmusicload"
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
            "Merhaba! Ben YouTube ve SoundCloud'dan ses indirmek için bir botum.\n\n"
            "YouTube veya SoundCloud bağlantısı gönderin (video veya parça), size ses indirme seçenekleri sunacağım.\n\n"
            f"Botu kullanmak için {REQUIRED_CHANNEL} kanalına abone olun.\n"
            "\n🎵 Ayrıca isimle müzik arayabilirim! Sadece /search yazın ve parçanızı bulun.\n"
            "İyi eğlenceler!"
            "Botu kullanmak için kanala abone olmayı unutmayın @ytdlpdeveloper. artoflife2303.github.io/miniblog \n\n"
            "Web bot versiyonu: youtubemusicdownloader.life, eğer çalışmıyorsa hbit.ly/ytmusicload"
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
        "url_error_generic": "URL işlenemedi. Geçerli bir YouTube veya SoundCloud bağlantısı olduğundan emin olun.",
        "search_prompt": (
            "Parça adı veya sanatçı adı girin. Ardından müziğe tıklayın, MP3 formatında indirilecektir.\n"
            "Aramayı iptal etmek için /cancel yazın.\n"
            "Müzik adıyla arama yapmak için /search yazın (YouTube)."
        ),
        "searching": "Müzik aranıyor...",
        "unsupported_url_in_search": "Bağlantı desteklenmiyor. Lütfen bağlantıyı kontrol edin veya başka bir sorgu deneyin. (Alternatif olarak, işe yaramadıysa, başka bir sanatçıdan veya Remix bir parça indirebilirsiniz)",
        "no_results": "Hiçbir sonuç bulunamadı. Başka bir sorgu deneyin.",
        "choose_track": "MP3 olarak indirmek için bir parça seçin:",
        "downloading_selected_track": "Seçilen parça MP3 olarak indiriliyor...",
        "copyright_pre": "⚠️ Dikkat! İndirmek üzrə olduğunuz materyal telif haqqı ilə qoruna bilər. Yalnızca şəxsi istifadə üçün istifadə edin. Əgər siz hüquq sahibisiniz və hüquqlarınızın pozulduğunu düşünürsənsə, zəhmət olmasa copyrightytdlpbot@gmail.com ünvanına yazın.",
        "copyright_post": "⚠️ Bu materyal telif haqqı ilə qoruna bilər. Yalnızca şəxsi istifadə üçün istifadə edin. Əgər siz hüquq sahibisiniz və hüquqlarınızın pozulduğunu düşünürsə, copyrightytdlpbot@gmail.com ünvanına yazın.",
        "copyright_command": "⚠️ Dikkat! Bu bot vasitəsilə yüklənən bütün materiallar müəllif hüquqları ilə qoruna bilər. Yalnızca şəxsi istifadə üçün istifadə edin. Əgər siz hüquq sahibisiniz və hüquqlarınızın pozulduğunu düşünürsə, copyrightytdlpbot@gmail.com ünvanına yazın, müvafiq məzmunu siləcəyik."
    },
    "ar": {
        "start": (
            "مرحبًا! أنا بوت لتنزيل الصوت من YouTube و SoundCloud.\n\n"
            "أرسل رابط YouTube أو SoundCloud (فيديو أو مسار) وسأقدم لك خيارات تنزيل الصوت.\n\n"
            f"لاستخدام البوت، يرجى الاشتراك في القناة {REQUIRED_CHANNEL}.\n"
            "\n🎵 يمكنني أيضًا البحث عن الموسيقى بالاسم! ما عليك سوى كتابة /search والعثور على المسار الخاص بك.\n"
            "استمتع!\n"
            "لا تنس الاشتراك في القناة للحصول على التحديثات والدعم @ytdlpdeveloper. artoflife2303.github.io/miniblog. \n"
            "النسخة الويب من البوت: youtubemusicdownloader.life، إذا لم تعمل، فجرّب bit.ly/ytmusicload"
        ),
        "choose_lang": "اختر اللغة:",
        "not_subscribed": f"لاستخدام البوت، يرجى الاشتراك في قناة {REQUIRED_CHANNEL} والمحاولة مرة أخرى.",
        "checking": "جاري التحقق من الرابط...",
        "not_youtube": "هذا ليس رابطًا مدعومًا. يرجى إرسال رابط YouTube أو SoundCloud صالح.",
        "choose_download_type": "اختر تنسيق الصوت:",
        "audio_button_mp3": "🎵 MP3 (يوتيوب)",
        "audio_button_sc": "🎵 MP3 (ساوند كلاود)",
        "downloading_audio": "جاري تنزيل الصوت... يرجى الانتظار.",
        "download_progress": "جاري التنزيل: {percent} بسرعة {speed}، متبقي ~{eta}",
        "too_big": f"الملف كبير جدًا (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). جرب فيديو أو مسارًا آخر.",
        "done_audio": "تم! تم إرسال الصوت.",
        "error": "حدث خطأ ما. تحقق من الرابط أو حاول مرة أخرى!\n",
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
        "copyright_pre": "⚠️ تحذير! قد يكون المحتوى الذي توشك على تنزيله محميًا بحقوق النشر. استخدمه للأغراض الشخصية فقط. إذا كنت صاحب حقوق وتعتقد أن حقوقك منتهكة، يرجى التواصل عبر copyrightytdlpbot@gmail.com لحذف المحتوى.",
        "copyright_post": "⚠️ قد يكون هذا المحتوى محميًا بحقوق النشر. استخدمه للأغراض الشخصية فقط. إذا كنت صاحب حقوق وتعتقد أن حقوقك منتهكة، يرجى التواصل عبر copyrightytdlpbot@gmail.com.",
        "copyright_command": "⚠️ تحذير! جميع المواد التي يتم تنزيلها عبر هذا البوت قد تكون محمية بحقوق النشر. استخدمها للأغراض الشخصية فقط. إذا كنت صاحب حقوق وتعتقد أن حقوقك منتهكة، يرجى التواصل عبر copyrightytdlpbot@gmail.com وسنقوم بحذف المحتوى.",
    },
    "az": {
        "start": (
            "Salam! Mən YouTube və SoundCloud-dan səs yükləmək üçün bir botam.\n\n"
            "YouTube və ya SoundCloud linki (video və ya trek) göndərin, sizə səs yükləmə seçimləri təklif edəcəm.\n\n"
            f"Botdan istifadə etmək üçün {REQUIRED_CHANNEL} kanalına abunə olun.\n"
            "\n🎵 Həmçinin adla musiqi axtara bilərəm! Sadəcə /search yazın və trekinizi tapın.\n"
            "Əylənin!"
            "Yeniliklər və dəstək üçün kanala abunə olmağı unutmayın @ytdlpdeveloper. artoflife2303.github.io/miniblog. \n"
            "Botun veb versiyası: youtubemusicdownloader.life, əgər işləmirsə bit.ly/ytmusicload"
        ),
        "choose_lang": "Dil seçin:",
        "not_subscribed": f"Botdan istifadə etmək üçün zəhmət olmasa {REQUIRED_CHANNEL} kanalına abunə olun və yenidən cəhd edin.",
        "checking": "Link yoxlanılır...",
        "not_youtube": "Bu dəstəklənməyən bir bağlantıdır. Zəhmət olmasa, etibarlı bir YouTube və ya SoundCloud linki göndərin.",
        "choose_download_type": "Səs formatını seçin:",
        "audio_button_mp3": "🎵 MP3 (YouTube)",
        "audio_button_sc": "🎵 MP3 (SoundCloud)",
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
            "Trek adı və ya ifaçı adı daxil edin. Sonra musiqiyə tıklayın, MP3 formatında yüklənəcək.\n"
            "/cancel daxil edərək axtarışı ləğv edin.\n"
            "/search daxil edərək adla musiqi axtarın (YouTube)."
        ),
        "searching": "Musiqi axtarılır...",
        "unsupported_url_in_search": "Link dəstəklənmir. Zəhmət olmasa, linki yoxlayın və ya başqa bir sorğu sınayın. (Alternativ olaraq, əgər işləmədisə, başqa bir ifaçıdan və ya Remix bir trek yükləyə bilərsiniz)",
        "no_results": "Heç nə tapılmadı. Başqa bir sorğu sınayın.",
        "choose_track": "MP3 olaraq yükləmək üçün bir trek seçin:",
        "downloading_selected_track": "Seçilən trek MP3 olaraq yüklənir...",
        "copyright_pre": "⚠️ Diqqət! Yüklədiyiniz material müəllif hüquqları ilə qoruna bilər. Yalnız şəxsi istifadə üçün istifadə edin. Əgər siz hüquq sahibisiniz və hüquqlarınızın pozulduğunu düşünürsə, zəhmət olmasa copyrightytdlpbot@gmail.com ünvanına yazın.",
        "copyright_post": "⚠️ Bu material müəllif hüquqları ilə qoruna bilər. Yalnız şəxsi istifadə üçün istifadə edin. Əgər siz hüquq sahibisiniz və hüquqlarınızın pozulduğunu düşünürsə, copyrightytdlpbot@gmail.com ünvanına yazın.",
        "copyright_command": "⚠️ Diqqət! Bu bot vasitəsilə yüklənən bütün materiallar müəllif hüquqları ilə qoruna bilər. Yalnız şəxsi istifadə üçün istifadə edin. Əgər siz hüquq sahibisiniz və hüquqlarınızın pozulduğunu düşünürsə, copyrightytdlpbot@gmail.com ünvanına yazın, müvafiq məzmunu siləcəyik."
    }
}

def get_user_lang(user_id):
    """
    Определяет язык пользователя по его ID. Если язык не найден, используется русский.
    Determines the user's language by their ID. If no language is found, Russian is used.
    """
    lang = user_langs.get(user_id)
    if lang in LANGUAGES:
        return lang
    return "ru"

def is_soundcloud_url(url):
    """
    Проверяет, является ли URL ссылкой на SoundCloud.
    Checks if the URL is a SoundCloud link.
    """
    return "soundcloud.com/" in url.lower()

def load_user_langs():
    """
    Загружает языковые предпочтения пользователей из файла.
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
    Сохраняет языковые предпочтения пользователей в файл.
    Saves user language preferences to a file.
    """
    with open(USER_LANGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_langs, f)

async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отправляет пользователю клавиатуру для выбора языка.
    Sends the user a keyboard to choose a language.
    """
    logger.info(f"User {update.effective_user.id} requested language choice.")
    await update.message.reply_text(
        LANGUAGES["ru"]["choose_lang"], # Использование русского текста по умолчанию для выбора языка.
        reply_markup=LANG_KEYBOARD
    )

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Устанавливает язык для пользователя и отправляет приветственное сообщение.
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
            "Пожалуйста, выберите язык с клавиатуры / Please choose a language from the keyboard."
        )

async def check_subscription(user_id: int, bot) -> bool:
    """
    Проверяет, подписан ли пользователь на обязательный канал.
    Checks if the user is subscribed to the required channel.
    """
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.error(f"Error checking subscription for user {user_id}: {e}")
        return False

def blocking_yt_dlp_download(ydl_opts, url_to_download):
    """
    Выполняет загрузку с использованием yt-dlp в блокирующем режиме.
    Performs download using yt-dlp in blocking mode.
    """
    import yt_dlp.utils
    import logging
    yt_dlp_logger = logging.getLogger("yt_dlp")
    yt_dlp_logger.setLevel(logging.WARNING) # Установка уровня логирования для yt-dlp
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url_to_download])
        return True
    except yt_dlp.utils.UnsupportedError:
        raise Exception("Unsupported URL: {}".format(url_to_download))
    except Exception as e:
        logger.error(f"yt-dlp download error: {e}")
        raise # Повторный выброс всех остальных исключений

async def ask_download_type(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    """
    Спрашивает пользователя о типе загрузки (MP3 для YouTube/SoundCloud).
    Sends a copyright warning and asks the user about the download type (MP3 for YouTube/SoundCloud).
    """
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    # Отправка сообщения об авторских правах перед выбором формата
    await update.message.reply_text(texts.get("copyright_pre"))
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

async def handle_download(update_or_query, context: ContextTypes.DEFAULT_TYPE, url: str, texts: dict, user_id: int, download_type: str):
    """
    Обрабатывает загрузку аудиофайла с YouTube или SoundCloud.
    Handles the download of an audio file from YouTube or SoundCloud.
    """
    if not update_or_query.message:
        try:
            # Отправка сообщения об ошибке, если chat_id не найден.
            await context.bot.send_message(chat_id=user_id, text=texts["error"] + " (внутренняя ошибка: не найден чат для ответа)")
        except Exception:
            pass # Игнорируем ошибку, если сообщение не может быть отправлено.
        return

    chat_id = update_or_query.message.chat_id
    temp_dir = None
    status_message = None
    active_downloads = context.bot_data.setdefault('active_downloads', {})
    loop = asyncio.get_running_loop()
    cancel_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(texts["cancel_button"], callback_data=f"cancel_{user_id}")]])

    async def update_status_message_async(text_to_update, show_cancel_button=True):
        """
        Обновляет статусное сообщение в чате.
        Updates the status message in the chat.
        """
        nonlocal status_message
        if status_message:
            try:
                current_keyboard = cancel_keyboard if show_cancel_button else None
                await status_message.edit_text(text_to_update, reply_markup=current_keyboard)
            except Exception as e:
                logger.debug(f"Could not edit status message: {e}") # Отладочное сообщение
                pass # Игнорируем ошибки при редактировании сообщения.

    def progress_hook(d):
        """
        Хук прогресса загрузки для yt-dlp.
        Progress hook for yt-dlp.
        """
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
            'verbose': True # Включите подробный вывод, чтобы видеть, какие ошибки происходят.
        }
        # Удаляем None значения из ydl_opts, чтобы избежать ошибок.
        ydl_opts = {k: v for k, v in ydl_opts.items() if v is not None}

        logger.info(f"Starting download for {url} by user {user_id}")
        try:
            await asyncio.to_thread(blocking_yt_dlp_download, ydl_opts, url)
        except Exception as e:
            if 'Unsupported URL' in str(e) or 'unsupported url' in str(e).lower():
                await update_status_message_async("Ссылка не поддерживается. Пожалуйста, проверьте правильность ссылки или попробуйте другой запрос.", show_cancel_button=False)
                return
            logger.error(f"Error during yt-dlp download for {url}: {e}")
            raise # Повторный выброс исключения после логирования.

        downloaded_files_info = []
        all_temp_files = os.listdir(temp_dir)
        for file_name in all_temp_files:
            file_path = os.path.join(temp_dir, file_name)
            file_ext_lower = os.path.splitext(file_name)[1].lower()
            base_title = os.path.splitext(file_name.split(" [")[0])[0] # Извлечение заголовка из имени файла.
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
                # Отправка сообщения об авторских правах после загрузки каждого файла
                await context.bot.send_message(chat_id=chat_id, text=texts.get("copyright_post"))
                logger.info(f"Successfully sent audio for {url} to user {user_id}")
            except Exception as e:
                logger.error(f"Error sending audio file {os.path.basename(file_to_send)} to user {user_id}: {e}")
                await context.bot.send_message(chat_id=chat_id, text=f"{texts['error']} (Ошибка отправки файла {os.path.basename(file_to_send)})")

        await update_status_message_async(texts["done_audio"], show_cancel_button=False)

    except asyncio.CancelledError:
        # Обработка отмены загрузки.
        logger.info(f"Download cancelled for user {user_id}.")
        if status_message:
            await update_status_message_async(texts["cancelled"], show_cancel_button=False)
        else:
            await context.bot.send_message(chat_id=chat_id, text=texts["cancelled"])
    except Exception as e:
        # Общая обработка ошибок загрузки.
        if 'Unsupported URL' in str(e) or 'unsupported url' in str(e).lower():
            if status_message:
                await update_status_message_async("Ссылка не поддерживается. Пожалуйста, проверьте правильность ссылки или попробуйте другой запрос.", show_cancel_button=False)
            else:
                await context.bot.send_message(chat_id=chat_id, text="Ссылка не поддерживается. Пожалуйста, проверьте правильность ссылки или попробуйте другой запрос.")
            return
        logger.critical(f"Unhandled error in handle_download for user {user_id}: {e}", exc_info=True) # Использование critical для неперехваченных ошибок
        if status_message:
            await update_status_message_async(texts["error"] + str(e), show_cancel_button=False)
        else:
            await context.bot.send_message(chat_id=chat_id, text=texts["error"] + str(e))
    finally:
        # Очистка временных файлов и снятие статуса активной загрузки.
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temporary directory {temp_dir} for user {user_id}.")
        if user_id in active_downloads:
            del active_downloads[user_id]
            logger.info(f"Removed active download for user {user_id}.")

async def select_download_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает выбор типа загрузки из Inline-клавиатуры.
    Handles the selection of download type from the Inline keyboard.
    """
    query = update.callback_query
    await query.answer() # Отправляем ответ на CallbackQuery, чтобы убрать "часики" с кнопки.
    user_id = query.from_user.id
    logger.info(f"User {user_id} selected download type: {query.data}")
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

    except (IndexError, ValueError) as e:
        logger.error(f"Error parsing callback_data for user {user_id}: {e} - Data: {query.data}")
        await query.edit_message_text("Ошибка выбора. Попробуйте снова отправить ссылку.")
        return

    requesting_user_id = query.from_user.id
    if user_id_from_callback != requesting_user_id:
        logger.warning(f"User {requesting_user_id} tried to use another user's callback: {user_id_from_callback}")
        await query.edit_message_text("Эта кнопка не для вас.")
        return

    lang = get_user_lang(requesting_user_id)
    texts = LANGUAGES[lang]

    # Извлечение URL для загрузки из user_data.
    url_to_download = context.user_data.pop(f'url_for_download_{requesting_user_id}', None)
    if not url_to_download:
        logger.error(f"URL not found in user_data for user {requesting_user_id}")
        await query.edit_message_text(texts["error"] + " (URL не найден, попробуйте снова)")
        return

    try:
        await query.edit_message_reply_markup(reply_markup=None) # Удаление клавиатуры после выбора.
    except Exception as e:
        logger.debug(f"Could not remove reply markup: {e}")
        pass # Игнорируем ошибки, если клавиатура уже удалена.

    # Запуск загрузки в фоновом режиме.
    task = asyncio.create_task(handle_download(query, context, url_to_download, texts, requesting_user_id, download_type_for_handler))
    active_downloads = context.bot_data.setdefault('active_downloads', {})
    active_downloads[requesting_user_id] = {'task': task}

async def search_youtube(query: str):
    """
    Выполняет поиск видео на YouTube.
    Performs a search for videos on YouTube.
    """
    if is_url(query):
        return 'unsupported_url'

    ydl_opts = {
        'quiet': True, # Отключение вывода сообщений.
        'skip_download': True, # Пропускать загрузку.
        'extract_flat': True, # Извлекать только плоский список информации.
        'nocheckcertificate': True, # Не проверять сертификаты SSL.
        'default_search': None, # Отключить поиск по умолчанию, чтобы контролировать его.
        'noplaylist': True # Не извлекать плейлисты.
    }
    try:
        # Поиск по 10 лучшим результатам.
        search_query = f"ytsearch{SEARCH_RESULTS_LIMIT}:{query}"
        logger.info(f"Searching YouTube for query: {query}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            entries = info.get('entries', [])
            if entries is None:
                logger.info(f"No entries found for YouTube search: {query}")
                return [] # Возвращаем пустой список, если entries равно None.
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

def is_url(text):
    """
    Проверяет, является ли строка URL-адресом YouTube или SoundCloud.
    Checks if a string is a YouTube or SoundCloud URL.
    """
    text = text.lower().strip()
    return (
        text.startswith("http://") or text.startswith("https://")
    ) and (
        "youtube.com/" in text or "youtu.be/" in text or "soundcloud.com/" in text
    )

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начинает процесс поиска музыки.
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
    Обрабатывает введенный пользователем поисковый запрос и отображает результаты.
    Processes the user's search query and displays the results.
    """
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    query_text = update.message.text.strip()
    logger.info(f"User {user_id} sent search query: '{query_text}'")

    await update.message.reply_text(texts["searching"])
    results = await search_youtube(query_text)

    if results == 'unsupported_url':
        await update.message.reply_text(texts["unsupported_url_in_search"])
        context.user_data.pop(f'awaiting_search_query_{user_id}', None) # Сбрасываем флаг ожидания запроса.
        return

    if not isinstance(results, list): # Проверка, что results является списком.
        results = []

    if not results:
        await update.message.reply_text(texts["no_results"])
        context.user_data.pop(f'awaiting_search_query_{user_id}', None)
        return

    keyboard = []
    for idx, entry in enumerate(results):
        title = entry.get('title', texts["no_results"])
        video_id = entry.get('id')
        keyboard.append([InlineKeyboardButton(f"{idx+1}. {title}", callback_data=f"searchsel_{user_id}_{video_id}")])

    await update.message.reply_text(
        texts["choose_track"],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    # Сохраняем результаты поиска для последующего выбора.
    context.user_data[f'search_results_{user_id}'] = {entry.get('id'): entry for entry in results}
    context.user_data.pop(f'awaiting_search_query_{user_id}', None) # Сбрасываем флаг ожидания запроса.
    logger.info(f"User {user_id} received {len(results)} search results.")

async def search_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает выбор трека из результатов поиска.
    Handles the selection of a track from search results.
    """
    query = update.callback_query
    await query.answer() # Отправляем ответ на CallbackQuery, чтобы убрать "часики" с кнопки.
    user_id = query.from_user.id
    logger.info(f"User {user_id} selected track from search: {query.data}")

    try:
        _, sel_user_id, video_id = query.data.split("_", 2)
        sel_user_id = int(sel_user_id)
    except Exception as e:
        logger.error(f"Error parsing search select callback data for user {user_id}: {e} - Data: {query.data}")
        await query.edit_message_text("Ошибка выбора трека.")
        return

    if user_id != sel_user_id:
        logger.warning(f"User {user_id} tried to use another user's search select callback: {sel_user_id}")
        await query.edit_message_text("Эта кнопка не для вас.")
        return

    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]

    url = f"https://youtu.be/{video_id}" # Формируем URL из ID видео.
    await query.edit_message_text(texts["downloading_selected_track"], reply_markup=None) # Удаляем клавиатуру.

    # Запускаем процесс загрузки выбранного трека.
    task = asyncio.create_task(
        handle_download(query, context, url, texts, user_id, "audio_mp3")
    )
    active_downloads = context.bot_data.setdefault('active_downloads', {})
    active_downloads[user_id] = {'task': task}

async def smart_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Умный обработчик сообщений: определяет, является ли сообщение URL или поисковым запросом.
    Smart message handler: determines if the message is a URL or a search query.
    """
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    text = update.message.text.strip()
    logger.info(f"User {user_id} sent message: '{text}'")

    active_downloads = context.bot_data.setdefault('active_downloads', {})
    if user_id in active_downloads and active_downloads[user_id].get('task') and not active_downloads[user_id]['task'].done():
        await update.message.reply_text(texts["download_in_progress"])
        return

    # Проверка подписки перед любой обработкой сообщения.
    is_subscribed = await check_subscription(user_id, context.bot)
    if not is_subscribed:
        await update.message.reply_text(texts["not_subscribed"])
        return

    if is_url(text):
        await ask_download_type(update, context, text)
    else:
        # Если это не URL и бот ожидает поисковый запрос (например, после /search).
        # Проверяем, ожидает ли бот поисковый запрос от этого пользователя.
        if context.user_data.get(f'awaiting_search_query_{user_id}'):
            await handle_search_query(update, context)
        else:
            # Если пользователь просто написал слово (например, Timeless), автоматически выполняем поиск музыки.
            if len(text.split()) <= 5 and text.isascii():
                # Автоматический поиск по коротким текстам (до 5 слов, латиница)
                logger.info(f"User {user_id} auto-search for: '{text}'")
                await update.message.reply_text(texts["searching"])
                results = await search_youtube(text)
                if not results or results == 'unsupported_url':
                    await update.message.reply_text(texts["no_results"])
                    return
                keyboard = []
                for idx, entry in enumerate(results):
                    title = entry.get('title', texts["no_results"])
                    video_id = entry.get('id')
                    keyboard.append([InlineKeyboardButton(f"{idx+1}. {title}", callback_data=f"searchsel_{user_id}_{video_id}")])
                await update.message.reply_text(
                    texts["choose_track"],
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                context.user_data[f'search_results_{user_id}'] = {entry.get('id'): entry for entry in results}
            else:
                await update.message.reply_text(texts["url_error_generic"])

async def cancel_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает запрос на отмену загрузки.
    Handles the request to cancel a download.
    """
    query = update.callback_query
    await query.answer() # Отправляем ответ на CallbackQuery, чтобы убрать "часики" с кнопки.
    user_id = query.from_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    logger.info(f"User {user_id} requested download cancellation.")

    active_downloads = context.bot_data.setdefault('active_downloads', {})
    download = active_downloads.get(user_id)

    if not download or not download.get('task') or download['task'].done():
        try:
            await query.edit_message_text(texts["already_cancelled_or_done"])
        except Exception as e:
            logger.debug(f"Could not edit message for already cancelled/done download: {e}")
            pass # Игнорируем ошибку, если сообщение не может быть отредактировано (например, уже изменено).
        return

    download['task'].cancel() # Отменяем активную задачу загрузки.
    try:
        await query.edit_message_text(texts["cancelling"])
    except Exception as e:
        logger.debug(f"Could not edit message to 'cancelling': {e}")
        pass # Игнорируем ошибку, если сообщение не может быть отредактировано.
    logger.info(f"Download task cancelled for user {user_id}.")


async def copyright_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает команду /copyright и отправляет сообщение об авторских правах.
    Handles the /copyright command and sends the copyright message.
    """
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES[lang]
    logger.info(f"User {user_id} issued /copyright command.")
    await update.message.reply_text(texts["copyright_command"])

def main():
    """
    Основная функция для запуска бота.
    Main function to run the bot.
    """
    load_user_langs() # Загрузка пользовательских языков при запуске.
    
    try:
        app = Application.builder().token(TOKEN).build()
        logger.info("Bot application built successfully.")
    except Exception as e:
        logger.critical(f"Failed to build bot application: {e}", exc_info=True)
        # Если здесь произошла ошибка, это критично и нужно остановить выполнение.
        raise

    # Добавление обработчиков команд.
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", choose_language))
    app.add_handler(CommandHandler("languages", choose_language))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("copyright", copyright_command)) # Новая команда /copyright.

    # Обработчик сообщений для выбора языка (по тексту кнопки).
    app.add_handler(MessageHandler(filters.Regex(f"^({'|'.join(LANG_CODES.keys())})$"), set_language))

    # Обработчики CallbackQuery для выбора типа загрузки и выбора из поиска.
    app.add_handler(CallbackQueryHandler(select_download_type_callback, pattern="^dltype_"))
    app.add_handler(CallbackQueryHandler(search_select_callback, pattern="^searchsel_"))
    app.add_handler(CallbackQueryHandler(cancel_download_callback, pattern="^cancel_"))

    # Основной обработчик текстовых сообщений (если это не команда и не выбор языка).
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^({'|'.join(LANG_CODES.keys())})$"),
        smart_message_handler
    ))

    async def set_commands(_):
        """
        Устанавливает команды для бота в Telegram. Эти команды отображаются в меню Telegram.
        Sets the bot commands in Telegram. These commands are displayed in the Telegram menu.
        """
        logger.info("Setting bot commands.")
        await app.bot.set_my_commands([
            BotCommand("start", "Запуск и выбор языка / Start and choose language"),
            BotCommand("languages", "Сменить язык / Change language"),
            BotCommand("search", "Поиск музыки (YouTube/SoundCloud) / Search music (YouTube/SoundCloud)"), # Более универсальное описание
            BotCommand("copyright", "Информация об авторских правах / Copyright info") # Более четкое описание
        ])
    app.post_init = set_commands # Выполнение set_commands после инициализации приложения.
    
    logger.info("Starting bot polling.")
    try:
        app.run_polling() # Запуск бота.
    except Exception as e:
        logger.critical(f"Bot polling failed: {e}", exc_info=True)
        

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает команду /start: предлагает выбрать язык и отправляет предупреждение об авторских правах.
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
