import os

from dotenv import load_dotenv
from telegram import BotCommand, InlineKeyboardButton, ReplyKeyboardMarkup

# Load environment variables from .env file
load_dotenv()

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
        ["Español", "Deutsch"],
        ["Français", "Azərbaycan dili"],
        ["Türkçe", "العربية"],
        ["  ", "한국어", "中文"]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# Mapping language names to codes
LANG_CODES = {
    "Русский": "ru", "English": "en", "Español": "es",
    "Deutsch": "de", "Français": "fr",
    "Azərbaycan dili": "az", "Türkçe": "tr",
    "العربية": "ar",
    "日本語": "ja",
    "한국어": "ko",
    "中文": "zh"
}

# Inline keyboard data for language selection (used on startup)
LANG_INLINE_BUTTONS = [InlineKeyboardButton(name, callback_data=f"lang_{code}") for name, code in LANG_CODES.items()]

SEARCH_RESULTS_LIMIT = 10  # Search results limit
MAX_CONCURRENT_DOWNLOADS_PER_USER = int(os.getenv('MAX_CONCURRENT_DOWNLOADS_PER_USER', '3'))
# Dictionaries with localized texts
LANGUAGES = {
    "ru": {
        "start": (
            "👋 Привет! Добро пожаловать в Music Jacker! 🎶\n\n"
            "Я помогу скачать аудио из YouTube и SoundCloud в формате MP3 (128 kbps).\n\n"
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
            "Введите название трека или исполнителя. После чего, нажмите на музыку, она загрузится в формате MP3 (128 kbps).\n"
            "Введите /cancel для отмены поиска.\n"
            "Введите /search для поиска музыки по названию (YouTube)."
        ),
        "searching": "Ищу музыку...",
        "unsupported_url_in_search": "Ссылка не поддерживается. Пожалуйста, проверьте другую ссылку или попробуйте другой запрос. (Альтернативно, если у вас не получилось, вы можете загрузить трек от другого исполнителя или Remix)",
        "no_results": "Ничего не найдено. Попробуйте другой запрос.",
    "choose_track": "Выберите трек для скачивания в MP3 (128 kbps):",
    "downloading_selected_track": "Скачиваю выбранный трек в MP3 (128 kbps)...",
        "copyright_pre": "⚠️ Внимание! Загружаемый вами материал может быть защищён авторским правом. Используйте только для личных целей. Если вы являетесь правообладателем и считаете, что ваши права нарушены, напишите на copyrightytdlpbot@gmail.com для удаления контента.",
        "copyright_post": "⚠️ Данный материал может быть защищён авторским правом. Используйте только для личных целей. Если вы правообладатель и считаете, что ваши права нарушены, напишите на copyrightytdlpbot@gmail.com.",
        "copyright_command": "⚠️ Внимание! Все материалы, скачиваемые через этого бота, могут быть защищены авторским правом. Используйте только для личных целей. Если вы правообладатель и считаете, что ваши права нарушены, напишите на copyrightytdlpbot@gmail.com, и мы удалим соответствующий контент."
    },
    "en": {
        "start": (
            "👋 Hello! Welcome to Music Jacker! 🎶\n\n"
            "I can help you download audio from YouTube and SoundCloud in MP3 format (128 kbps).\n\n"
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
            "Enter the track name or artist. Then click on the music, it will download in MP3 format (128 kbps).\n"
            "Enter /cancel to cancel the search.\n"
            "Enter /search to search for music by name (YouTube)."
        ),
        "searching": "Searching for music...",
        "unsupported_url_in_search": "The link is not supported. Please check the link or try another query. (Alternatively, if it didn't work, you can download a track from another artist or Remix)",
        "no_results": "Nothing found. Try another query.",
    "choose_track": "Select a track to download in MP3 (128 kbps):",
    "downloading_selected_track": "Downloading the selected track in MP3 (128 kbps)...",
        "copyright_pre": "⚠️ Warning! The material you are about to download may be protected by copyright. Use for personal purposes only. If you are a copyright holder and believe your rights are being violated, please contact copyrightytdlpbot@gmail.com for removal.",
        "copyright_post": "⚠️ This material may be protected by copyright. Use for personal purposes only. If you are a copyright holder and believe your rights are being violated, contact copyrightytdlpbot@gmail.com.",
        "copyright_command": "⚠️ Warning! All materials downloaded via this bot may be protected by copyright. Use for personal purposes only. If you are a copyright holder and believe your rights are being violated, contact copyrightytdlpbot@gmail.com and we will remove the content."
    },
    "es": {
        "start": (
            "👋 ¡Hola! ¡Bienvenido a Music Jacker! 🎶\n\n"
            "Te ayudo a descargar audio de YouTube y SoundCloud en formato MP3 (128 kbps).\n\n"
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
            "Ingrese el nombre de la pista o artista. Luego haga clic en la música, se descargará en formato MP3 (128 kbps).\n"
            "Ingrese /cancel para cancelar la búsqueda.\n"
            "Ingrese /search para buscar música por nombre (YouTube)."
        ),
        "searching": "Buscando música...",
        "unsupported_url_in_search": "El enlace no es compatible. Por favor, compruebe el enlace o pruebe con otra consulta. (Alternativamente, si no funcionó, puede descargar una pista de otro artista o un Remix)",
        "no_results": "No se encontraron resultados. Intente con otra consulta.",
    "choose_track": "Seleccione una pista para descargar en MP3 (128 kbps):",
    "downloading_selected_track": "Descargando la pista seleccionada en MP3 (128 kbps)...",
        "copyright_pre": "⚠️ ¡Atención! El material que está a punto de descargar puede estar protegido por derechos de autor. Úselo solo para fines personales. Si es titular de derechos y cree que se están violando sus derechos, escriba a copyrightytdlpbot@gmail.com para eliminar el contenido.",
        "copyright_post": "⚠️ Este material puede estar protegido por derechos de autor. Úselo solo para fines personales. Si es titular de derechos y cree que se están violando sus derechos, escriba a copyrightytdlpbot@gmail.com.",
        "copyright_command": "⚠️ ¡Atención! Todo el material descargado a través de este bot puede estar protegido por derechos de autor. Úselo solo para fines personales. Si es titular de derechos y cree que se están violando sus derechos, escriba a copyrightytdlpbot@gmail.com y eliminaremos el contenido."
    },
    "tr": {
        "start": (
            "👋 Merhaba! Music Jacker'a hoş geldin! 🎶\n\n"
            "YouTube ve SoundCloud'dan MP3 (128 kbps) formatında ses indirmen için buradayım.\n\n"
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
            "Parça adı veya sanatçı adı girin. Ardından müziğe tıklayın, MP3 (128 kbps) formatında indirilecektir.\n"
            "Aramayı iptal etmek için /cancel yazın.\n"
            "Müzik adıyla arama yapmak için /search yazın (YouTube)."
        ),
        "searching": "Musiqi axtarılır...",
        "unsupported_url_in_search": "Bağlantı desteklenmiyor. Lütfen bağlantıyı kontrol edin veya başka bir sorgu deneyin. (Alternatif olarak, işe yaramadıysa, başka bir sanatçıdan veya Remix bir parça indirebilirsiniz)",
        "no_results": "Hiçbir sonuç bulunamadı. Başka bir sorgu deneyin.",
    "choose_track": "MP3 (128 kbps) olarak indirmek için bir parça seçin:",
    "downloading_selected_track": "Seçilen parça MP3 (128 kbps) olarak indiriliyor...",
        "copyright_pre": "⚠️ Dikkat! İndirmek üzere olduğunuz materyal telif hakkı ile korunabilir. Yalnızca kişisel kullanım için kullanın. Eğer telif hakkı sahibiyseniz ve haklarınızın ihlal edildiğini düşünüyorsanız, lütfen copyrightytdlpbot@gmail.com adresine yazın.",
        "copyright_post": "⚠️ Bu materyal telif hakkı ile korunabilir. Yalnızca kişisel kullanım için kullanın. Eğer telif hakkı sahibiyseniz ve haklarınızın ihlal edildiğini düşünüyorsanız, copyrightytdlpbot@gmail.com adresine yazın.",
        "copyright_command": "⚠️ Dikkat! Bu bot aracılığıyla indirilen tüm materyaller telif hakkı ile korunabilir. Yalnızca kişisel kullanım için kullanın. Eğer telif hakkı sahibiyseniz ve haklarınızın ihlal edildiğini düşünüyorsanız, lütfen copyrightytdlpbot@gmail.com adresine yazın, müvafiq məzmunu siləcəyik."
    },
    "ar": {
        "start": (
            "👋 مرحبًا بك في Music Jacker! 🎶\n\n"
            "سأساعدك في تنزيل الصوت من YouTube و SoundCloud بصيغة MP3 (128 kbps).\n\n"
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
            "أدخل اسم المقطع الصوتي أو الفنان. ثم انقر على الموسيقى، سيتم تنزيلها بصيغة MP3 (128 kbps).\n"
            "أدخل /cancel لإلغاء البحث.\n"
            "أدخل /search للبحث عن الموسيقى بالاسم (يوتيوب)."
        ),
        "searching": "جاري البحث عن الموسيقى...",
        "unsupported_url_in_search": "الرابط غير مدعوم. يرجى التحقق من الرابط أو تجربة استعلام آخر. (بدلاً من ذلك، إذا لم ينجح الأمر, يمكنك تنزيل مقطع صوتي من فنان آخر أو ريمكس)",
        "no_results": "لم يتم العثور على شيء. حاول استعلامًا آخر.",
    "choose_track": "حدد مسارًا لتنزيله بصيغة MP3 (128 kbps):",
    "downloading_selected_track": "جاري تنزيل المسار المحدد بصيغة MP3 (128 kbps)...",
        "copyright_pre": "⚠️ تحذير! قد يكون المحتوى الذي توشك على تنزيله محميًا بحقوق النشر. استخدمه للأغراض الشخصية فقط. إذا كنت صاحب حقوق وتعتقد أن حقوقك منتهكة, يرجى التواصل عبر copyrightytdlpbot@gmail.com لحذف المحتوى.",
        "copyright_post": "⚠️ قد يكون هذا المحتوى محميًا بحقوق النشر. استخدمه للأغراض الشخصية فقط. إذا كنت صاحب حقوق وتعتقد أن حقوقك منتهكة, يرجى التواصل عبر copyrightytdlpbot@gmail.com.",
        "copyright_command": "⚠️ تحذير! جميع المواد التي يتم تنزيلها عبر هذا البوت قد تكون محمية بحقوق النشر. استخدمها للأغراض الشخصية فقط. إذا كنت صاحب حقوق وتعتقد أن حقوقك منتهكة, يرجى التواصل عبر copyrightytdlpbot@gmail.com وسنقوم بحذف المحتوى."
    },
    "az": {
        "start": (
            "👋 Salam! Music Jacker'a xoş gəlmisiniz! 🎶\n\n"
            "YouTube və SoundCloud-dan MP3 (128 kbps) formatında səs yükləmək üçün buradayam.\n\n"
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
            "Trek adı və ya ifaçı adı daxil edin. Sonra musiqiyə tıklayın, MP3 (128 kbps) formatında yüklənəcək.\n"
            "/cancel daxil edərək axtarışı ləğv edin.\n"
            "/search daxil edərək adla musiqi axtarın (YouTube)."
        ),
        "searching": "Musiqi axtarılır...",
        "unsupported_url_in_search": "Link dəstəklənmir. Zəhmət olmasa, linki yoxlayın və ya başqa bir sorğu sınayın. (Alternativ olaraq, əgər işləmədisə, başqa bir ifaçıdan və ya Remix bir trek yükləyə bilərsiniz)",
        "no_results": "Heç nə tapılmadı. Başqa bir sorğu sınayın.",
    "choose_track": "MP3 (128 kbps) olaraq yükləmək üçün bir trek seçin:",
    "downloading_selected_track": "Seçilən trek MP3 (128 kbps) olaraq yüklənir...",
        "copyright_pre": "⚠️ Diqqət! Yüklədiyiniz material müəllif hüquqları ilə qoruna bilər. Yalnız şəxsi istifadə üçün istifadə edin. Əgər siz hüquq sahibiysanız və hüquqlarınızın pozulduğunu düşünürsənsə, zəhmət olmasa copyrightytdlpbot@gmail.com ünvanına yazın.",
        "copyright_post": "⚠️ Bu material müəllif hüquqları ilə qoruna bilər. Yalnız şəxsi istifadə üçün istifadə edin. Əgər siz hüquq sahibiysanız və hüquqlarınızın pozulduğunu düşünürsə, copyrightytdlpbot@gmail.com ünvanına yazın.",
        "copyright_command": "⚠️ Diqqət! Bu bot vasitəsilə yüklənən bütün materiallar müəllif hüquqları ilə qoruna bilər. Yalnız şəxsi istifadə üçün istifadə edin. Əgər siz hüquq sahibiysanız və hüquqlarınızın pozulduğunu düşünürsə, copyrightytdlpbot@gmail.com ünvanına yazın, müvafiq məzmunu siləcəyik."
    },
    "de": {
        "start": (
            "👋 Hallo! Willkommen bei Music Jacker! 🎶\n\n"
            "Ich helfe dir, Audiodateien von YouTube und SoundCloud im MP3-Format (128 kbps) herunterzuladen.\n\n"
            "🔗 Sende einfach einen Link zu einem Video oder Track – und erhalte deine Musik!\n\n"
            f"📢 Um den Bot zu nutzen, abonniere bitte den Kanal {REQUIRED_CHANNELS[0]}.\n\n"
            "🔍 Möchtest du einen Song nach Namen suchen? Nutze /search und wähle deinen Favoriten!\n\n"
            "✨ Viel Spaß beim Hören!\n"
            "\nSupport & Neuigkeiten — @ytdlpdeveloper | artoflife2303.github.io/miniblog"
        ),
        "choose_lang": "Wähle eine Sprache:",
        "not_subscribed": f"Um den Bot zu nutzen, abonniere bitte den Kanal {REQUIRED_CHANNELS[0]} und versuche es erneut.",
        "checking": "Überprüfe den Link...",
        "not_youtube": "Dies ist kein unterstützter Link. Bitte sende einen gültigen YouTube- oder SoundCloud-Link.",
        "downloading_audio": "Lade Audio herunter... Bitte warten.",
        "download_progress": "Herunterladen: {percent} mit {speed}, verbleibend ~{eta}",
        "too_big": f"Die Datei ist zu groß (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Versuche ein anderes Video oder einen anderen Track.",
        "done_audio": "Fertig! Audio wurde gesendet.",
        "error": "Etwas ist schiefgelaufen. Überprüfe den Link oder versuche es später erneut!",
        "error_private_video": "Dies ist ein privates Video und kann nicht heruntergeladen werden.",
        "error_video_unavailable": "Video nicht verfügbar.",
        "sending_file": "Sende Datei {index} von {total}...",
        "cancel_button": "Abbrechen",
        "cancelling": "Download wird abgebrochen...",
        "cancelled": "Download abgebrochen.",
        "download_in_progress": "Ein anderer Download läuft bereits. Bitte warte oder breche ihn ab.",
        "already_cancelled_or_done": "Download wurde bereits abgebrochen oder abgeschlossen.",
        "url_error_generic": "URL konnte nicht verarbeitet werden. Stelle sicher, dass es sich um einen gültigen YouTube- oder SoundCloud-Link handelt.",
        "search_prompt": (
            "Gib den Namen des Tracks oder des Künstlers ein. Klicke dann auf die Musik, sie wird im MP3-Format (128 kbps) heruntergeladen.\n"
            "Gib /cancel ein, um die Suche abzubrechen.\n"
            "Gib /search ein, um Musik nach Namen zu suchen (YouTube)."
        ),
        "searching": "Suche nach Musik...",
        "unsupported_url_in_search": "Der Link wird nicht unterstützt. Bitte überprüfe den Link oder versuche eine andere Anfrage.",
        "no_results": "Keine Ergebnisse gefunden. Versuche eine andere Anfrage.",
    "choose_track": "Wähle einen Track zum Herunterladen im MP3-Format (128 kbps):",
    "downloading_selected_track": "Lade den ausgewählten Track im MP3-Format (128 kbps) herunter...",
        "copyright_pre": "⚠️ Achtung! Das Material, das du herunterladen möchtest, könnte urheberrechtlich geschützt sein. Verwende es nur für persönliche Zwecke.",
        "copyright_post": "⚠️ Dieses Material könnte urheberrechtlich geschützt sein. Verwende es nur für persönliche Zwecke.",
        "copyright_command": "⚠️ Achtung! Alle über diesen Bot heruntergeladenen Materialien könnten urheberrechtlich geschützt sein. Verwende sie nur für persönliche Zwecke."
    },
    "ja": {
        "start": (
            "👋 こんにちは！Music Jackerへようこそ！ 🎶\n\n"
            "YouTubeやSoundCloudからMP3形式（128 kbps）で音声をダウンロードできます。\n\n"
            "🔗 動画やトラックのリンクを送るだけで、音楽を取得できます！\n\n"
            f"📢 ボットを利用するには、チャンネル {REQUIRED_CHANNELS[0]} を購読してください。\n\n"
            "🔍 曲名で検索したいですか？ /search を使って曲を選んでください！\n\n"
            "✨ 音楽をお楽しみください！\n"
            "\nサポートとニュース — @ytdlpdeveloper | artoflife2303.github.io/miniblog"
        ),
        "choose_lang": "言語を選択してください:",
        "not_subscribed": f"ボットを利用するには、チャンネル {REQUIRED_CHANNELS[0]} を購読してから再試行してください。",
        "checking": "リンクを確認しています...",
        "not_youtube": "サポートされていないリンクです。有効なYouTubeまたはSoundCloudのリンクを送信してください。",
        "downloading_audio": "音声をダウンロードしています... お待ちください。",
        "download_progress": "ダウンロード中: {percent}、速度 {speed}、残り時間 ~{eta}",
        "too_big": f"ファイルが大きすぎます (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT})。別のビデオやトラックを試してください。",
        "done_audio": "完了！音声を送信しました。",
        "error": "エラーが発生しました。リンクを確認するか後でもう一度お試しください！",
        "error_private_video": "この動画は非公開のためダウンロードできません。",
        "error_video_unavailable": "動画が利用できません。",
        "sending_file": "ファイル {index}/{total} を送信しています...",
        "cancel_button": "キャンセル",
        "cancelling": "ダウンロードをキャンセルしています...",
        "cancelled": "ダウンロードがキャンセルされました。",
        "download_in_progress": "別のダウンロードが進行中です。しばらくお待ちいただくかキャンセルしてください。",
        "already_cancelled_or_done": "ダウンロードはすでにキャンセルされているか完了しています。",
        "url_error_generic": "URLを処理できませんでした。正しいYouTubeまたはSoundCloudのリンクであることを確認してください。",
        "search_prompt": (
            "トラック名またはアーティスト名を入力してください。曲をクリックすると、MP3（128 kbps）形式でダウンロードされます。\n"
            "検索をキャンセルするには /cancel を入力してください。\n"
            "曲名で検索するには /search を入力してください（YouTube）。"
        ),
        "searching": "音楽を検索しています...",
        "unsupported_url_in_search": "そのリンクはサポートされていません。リンクを確認するか別のクエリを試してください。",
        "no_results": "結果が見つかりません。別のクエリを試してください。",
        "choose_track": "MP3（128 kbps）でダウンロードするトラックを選択してください:",
        "downloading_selected_track": "選択したトラックをMP3（128 kbps）でダウンロードしています...",
        "copyright_pre": "⚠️ 注意！ダウンロードしようとしている素材は著作権で保護されている可能性があります。個人使用のみでご利用ください。権利者であり、権利侵害だと考える場合は copyrightytdlpbot@gmail.com までご連絡ください。",
        "copyright_post": "⚠️ この素材は著作権で保護されている可能性があります。個人使用のみでご利用ください。権利者である場合は copyrightytdlpbot@gmail.com までご連絡ください。",
        "copyright_command": "⚠️ 注意！このボットでダウンロードされるすべての素材は著作権で保護されている可能性があります。個人使用のみでご利用ください。権利者である場合は copyrightytdlpbot@gmail.com までご連絡ください。"
    },
    "ko": {
        "start": (
            "👋 안녕하세요! Music Jacker에 오신 것을 환영합니다! 🎶\n\n"
            "YouTube와 SoundCloud에서 MP3 형식(128 kbps)으로 오디오를 다운로드하도록 도와드립니다.\n\n"
            "🔗 동영상 또는 트랙 링크를 보내면 음악을 받아볼 수 있습니다!\n\n"
            f"📢 봇을 사용하려면 채널 {REQUIRED_CHANNELS[0]} 를 구독해주세요.\n\n"
            "🔍 노래 제목으로 검색하고 싶으신가요? /search 를 사용해 좋아하는 곡을 선택하세요!\n\n"
            "✨ 음악을 즐기세요!\n"
            "\n지원 및 소식 — @ytdlpdeveloper | artoflife2303.github.io/miniblog"
        ),
        "choose_lang": "언어를 선택하세요:",
        "not_subscribed": f"봇을 사용하려면 채널 {REQUIRED_CHANNELS[0]} 를 구독한 후 다시 시도해주세요.",
        "checking": "링크 확인 중...",
        "not_youtube": "지원되지 않는 링크입니다. 유효한 YouTube 또는 SoundCloud 링크를 보내주세요.",
        "downloading_audio": "오디오를 다운로드 중입니다... 잠시만 기다려주세요.",
        "download_progress": "다운로드 중: {percent} 속도 {speed}, 남은 시간 ~{eta}",
        "too_big": f"파일이 너무 큽니다 (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). 다른 비디오나 트랙을 시도해보세요.",
        "done_audio": "완료! 오디오를 전송했습니다.",
        "error": "문제가 발생했습니다. 링크를 확인하거나 나중에 다시 시도하세요!",
        "error_private_video": "이 비디오는 비공개라 다운로드할 수 없습니다.",
        "error_video_unavailable": "비디오를 사용할 수 없습니다.",
        "sending_file": "파일 {index}/{total}을 전송 중...",
        "cancel_button": "취소",
        "cancelling": "다운로드를 취소하는 중...",
        "cancelled": "다운로드가 취소되었습니다.",
        "download_in_progress": "다른 다운로드가 이미 진행 중입니다. 잠시 기다리거나 취소하세요.",
        "already_cancelled_or_done": "다운로드가 이미 취소되었거나 완료되었습니다.",
        "url_error_generic": "URL을 처리할 수 없습니다. 유효한 YouTube 또는 SoundCloud 링크인지 확인하세요.",
        "search_prompt": (
            "트랙명 또는 아티스트를 입력하세요. 음악을 클릭하면 MP3(128 kbps) 형식으로 다운로드됩니다.\n"
            "검색을 취소하려면 /cancel 을 입력하세요.\n"
            "곡명으로 검색하려면 /search 를 입력하세요 (YouTube)."
        ),
        "searching": "음악을 검색 중입니다...",
        "unsupported_url_in_search": "링크가 지원되지 않습니다. 링크를 확인하거나 다른 쿼리를 시도하세요.",
        "no_results": "결과가 없습니다. 다른 쿼리를 시도하세요.",
        "choose_track": "MP3(128 kbps)로 다운로드할 트랙을 선택하세요:",
        "downloading_selected_track": "선택한 트랙을 MP3(128 kbps)로 다운로드 중입니다...",
        "copyright_pre": "⚠️ 경고! 다운로드하려는 자료는 저작권으로 보호될 수 있습니다. 개인적인 용도로만 사용하세요. 권리자이고 권리 침해라고 생각되면 copyrightytdlpbot@gmail.com 으로 연락해주세요.",
        "copyright_post": "⚠️ 이 자료는 저작권으로 보호될 수 있습니다. 개인적인 용도로만 사용하세요. 권리자라면 copyrightytdlpbot@gmail.com 으로 연락해주세요.",
        "copyright_command": "⚠️ 경고! 이 봇을 통해 다운로드되는 모든 자료는 저작권으로 보호될 수 있습니다. 개인적인 용도로만 사용하세요. 권리자라면 copyrightytdlpbot@gmail.com 으로 연락주시면 콘텐츠를 삭제하겠습니다."
    },
    "zh": {
        "start": (
            "👋 你好！欢迎使用 Music Jacker！ 🎶\n\n"
            "我可以帮你从 YouTube 和 SoundCloud 下载 MP3 格式（128 kbps）的音频。\n\n"
            "🔗 只需发送视频或曲目的链接——即可获得音乐！\n\n"
            f"📢 要使用此机器人，请订阅频道 {REQUIRED_CHANNELS[0]} 。\n\n"
            "🔍 想按名称搜索歌曲吗？使用 /search 并选择你喜欢的曲目！\n\n"
            "✨ 祝你听歌愉快！\n"
            "\n支持与新闻 — @ytdlpdeveloper | artoflife2303.github.io/miniblog"
        ),
        "choose_lang": "选择语言:",
        "not_subscribed": f"要使用此机器人，请先订阅频道 {REQUIRED_CHANNELS[0]} 然后重试。",
        "checking": "正在检查链接...",
        "not_youtube": "这不是受支持的链接。请发送有效的 YouTube 或 SoundCloud 链接。",
        "downloading_audio": "正在下载音频... 请稍候。",
        "download_progress": "下载中：{percent}，速度 {speed}，预计剩余 ~{eta}",
        "too_big": f"文件太大（>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}）。请尝试其他视频或曲目。",
        "done_audio": "完成！已发送音频。",
        "error": "出错了。请检查链接或稍后重试！",
        "error_private_video": "这是私人视频，无法下载。",
        "error_video_unavailable": "视频不可用。",
        "sending_file": "正在发送文件 {index} / {total}...",
        "cancel_button": "取消",
        "cancelling": "正在取消下载...",
        "cancelled": "下载已取消。",
        "download_in_progress": "另一个下载正在进行中。请稍候或取消它。",
        "already_cancelled_or_done": "下载已被取消或已完成。",
        "url_error_generic": "无法处理 URL。请确保它是有效的 YouTube 或 SoundCloud 链接。",
        "search_prompt": (
            "输入曲目名称或艺术家。然后点击音乐，系统将以 MP3（128 kbps）格式下载。\n"
            "输入 /cancel 以取消搜索。\n"
            "输入 /search 在 YouTube 上按名称搜索音乐。"
        ),
        "searching": "正在搜索音乐...",
        "unsupported_url_in_search": "该链接不受支持。请检查链接或尝试其他查询。",
        "no_results": "未找到任何结果。请尝试其他查询。",
        "choose_track": "选择要以 MP3（128 kbps）下载的曲目：",
        "downloading_selected_track": "正在以 MP3（128 kbps）下载所选曲目...",
        "copyright_pre": "⚠️ 注意！您即将下载的资料可能受版权保护。仅供个人使用。如果您是权利人并认为您的权利受到侵害，请联系 copyrightytdlpbot@gmail.com。",
        "copyright_post": "⚠️ 该资料可能受版权保护。仅供个人使用。如果您是权利人并认为您的权利受到侵害，请联系 copyrightytdlpbot@gmail.com。",
        "copyright_command": "⚠️ 注意！通过此机器人下载的所有资料可能受版权保护。仅供个人使用。如果您是权利人并认为您的权利受到侵害，请联系 copyrightytdlpbot@gmail.com，我们将删除相关内容。"
    },
    "fr": {
        "start": (
            "👋 Bonjour ! Bienvenue sur Music Jacker ! 🎶\n\n"
            "Je peux t'aider à télécharger de l'audio depuis YouTube et SoundCloud au format MP3 (128 kbps).\n\n"
            "🔗 Envoie simplement un lien vers une vidéo ou une piste — et récupère ta musique !\n\n"
            f"📢 Pour utiliser le bot, abonne-toi à la chaîne {REQUIRED_CHANNELS[0]}.\n\n"
            "🔍 Tu veux chercher une chanson par nom ? Utilise /search et choisis ton préféré !\n\n"
            "✨ Bonne écoute !\n"
            "\nSupport & actualités — @ytdlpdeveloper | artoflife2303.github.io/miniblog"
        ),
        "choose_lang": "Choisis une langue :",
        "not_subscribed": f"Pour utiliser le bot, abonne-toi à la chaîne {REQUIRED_CHANNELS[0]} et réessaie.",
        "checking": "Vérification du lien...",
        "not_youtube": "Ce n'est pas un lien pris en charge. Envoie un lien valide YouTube ou SoundCloud.",
        "downloading_audio": "Téléchargement de l'audio... Veuillez patienter.",
        "download_progress": "Téléchargement : {percent} à {speed}, reste ~{eta}",
        "too_big": f"Le fichier est trop volumineux (>{TELEGRAM_FILE_SIZE_LIMIT_TEXT}). Essaie une autre vidéo ou piste.",
        "done_audio": "Terminé ! Audio envoyé.",
        "error": "Une erreur s'est produite. Vérifie le lien ou réessaie plus tard !",
        "error_private_video": "Ceci est une vidéo privée et ne peut pas être téléchargée.",
        "error_video_unavailable": "Vidéo indisponible.",
        "sending_file": "Envoi du fichier {index} sur {total}...",
        "cancel_button": "Annuler",
        "cancelling": "Annulation du téléchargement...",
        "cancelled": "Téléchargement annulé.",
        "download_in_progress": "Un autre téléchargement est déjà en cours. Veuillez attendre ou l'annuler.",
        "already_cancelled_or_done": "Le téléchargement a déjà été annulé ou terminé.",
        "url_error_generic": "Impossible de traiter l'URL. Assure-toi qu'il s'agit d'un lien valide YouTube ou SoundCloud.",
        "search_prompt": (
            "Saisis le nom de la piste ou de l'artiste. Clique ensuite sur la musique, elle sera téléchargée au format MP3 (128 kbps).\n"
            "Saisis /cancel pour annuler la recherche.\n"
            "Saisis /search pour rechercher de la musique par nom (YouTube)."
        ),
        "searching": "Recherche de musique...",
        "unsupported_url_in_search": "Le lien n'est pas pris en charge. Vérifie le lien ou essaie une autre requête.",
        "no_results": "Aucun résultat trouvé. Essaie une autre requête.",
        "choose_track": "Sélectionne une piste à télécharger au format MP3 (128 kbps) :",
        "downloading_selected_track": "Téléchargement de la piste sélectionnée au format MP3 (128 kbps)...",
        "copyright_pre": "⚠️ Attention ! Le contenu que tu es sur le point de télécharger peut être protégé par des droits d'auteur. Utilise-le uniquement à des fins personnelles.",
        "copyright_post": "⚠️ Ce contenu peut être protégé par des droits d'auteur. Utilise-le uniquement à des fins personnelles.",
        "copyright_command": "⚠️ Attention ! Tous les contenus téléchargés via ce bot peuvent être protégés par des droits d'auteur. Utilise-les uniquement à des fins personnelles."
    }
}


BOT_COMMANDS = [
    BotCommand("start", "Запуск и выбор языка / Start and choose language"),
    BotCommand("languages", "Сменить язык / Change language"),
    BotCommand("search", "Поиск музыки (YouTube/SoundCloud) / Search music (YouTube/SoundCloud)"),
    BotCommand("copyright", "Информация об авторских правах / Copyright info"),
]
