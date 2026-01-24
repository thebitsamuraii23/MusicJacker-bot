# Интеграция кэширования музыки в MusicJacker Bot

## 📋 Краткое резюме

Добавлены два новых модуля для кэширования скачанной музыки:
- **`utils/cache_manager.py`** — управление SQLite БД, директорией `/home/music`, генерация имён файлов
- **`utils/caching_downloader.py`** — загрузка с yt-dlp, проверка размера (50MB), кэширование

## 🔧 Что добавилось

### 1. **cache_manager.py** — основные функции

```python
from utils.cache_manager import (
    init_cache_db,              # Инициализировать БД (call once в main())
    check_cached_file,          # Проверить кэш перед скачиванием
    add_to_cache,               # Добавить файл в БД (автоматически в downloader)
    get_cache_file_path,        # Получить путь файла для кэша
    cleanup_cache,              # Удалить старые файлы (>30 дней)
    MUSIC_DIR,                  # Константа "/home/music"
)
```

**Ключевые свойства:**
- Автоматически создаёт `/home/music` если не существует
- SQLite таблица: `youtube_id TEXT PRIMARY KEY, file_path TEXT, title TEXT, artist TEXT, added_at DATETIME`
- Имя файла: `{artist} - {title} [{youtube_id}].mp3` (sanitized)
- Проверяет наличие файла на диске перед возвратом

### 2. **caching_downloader.py** — загрузка и кэш

```python
from utils.caching_downloader import CachingDownloader, TELEGRAM_FILE_SIZE_LIMIT_BYTES

downloader = CachingDownloader(ffmpeg_path="/usr/bin/ffmpeg", cookies_path="youtube.com_cookies.txt")

# Возвращает: (file_path, youtube_id, title) или (None, youtube_id, error_code)
file_path, youtube_id, result = await downloader.download_and_cache(
    url="https://youtu.be/...",
    update=update,
    context=context,
    texts=user_texts_dict,
    progress_callback=async_progress_fn  # optional
)
```

**Логика:**
1. Проверить кэш → если есть, вернуть файл
2. Извлечь metadata (ID, title, artist)
3. Скачать MP3 120kbps через yt-dlp + FFmpeg
4. Проверить размер:
   - **≤50MB** → сохранить в кэш → вернуть path
   - **>50MB** → вернуть `(None, youtube_id, "FILE_TOO_LARGE")`
5. Обработка ошибок: `VIDEO_NOT_AVAILABLE`, `GEO_BLOCKED`, `VIDEO_PRIVATE`, etc.

## 📝 Как интегрировать

### Шаг 1: Инициализация в `bot.py`

```python
from utils.cache_manager import init_cache_db

def main() -> None:
    setup_logging()
    
    # Инициализировать кэш БД (один раз при старте)
    cache_db_path = init_cache_db()
    logger.info(f"Cache database ready: {cache_db_path}")
    
    application = ApplicationBuilder().token(TOKEN).post_init(on_post_init).build()
    # ... остальной код
```

### Шаг 2: Создать экземпляр downloader в `handlers/downloader.py`

```python
from utils.caching_downloader import CachingDownloader
from utils.cache_manager import check_cached_file
from config import ffmpeg_path, cookies_path

# На уровне модуля
_caching_downloader: Optional[CachingDownloader] = None

async def init_downloader(ffmpeg_path: str, cookies_path: Optional[str] = None) -> None:
    global _caching_downloader
    _caching_downloader = CachingDownloader(ffmpeg_path=ffmpeg_path, cookies_path=cookies_path)
```

### Шаг 3: Модифицировать message handler

Вместо текущего скачивания, используйте:

```python
async def handle_music_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _caching_downloader:
        await init_downloader(ffmpeg_path, cookies_path)
    
    user_lang = get_user_lang(update.message.from_user.id)
    texts = TEXTS[user_lang]
    
    # Progress callback (опционально)
    async def on_progress(percent, speed, eta):
        # Обновить сообщение с прогрессом
        pass
    
    # Скачать с кэшем
    file_path, youtube_id, result = await _caching_downloader.download_and_cache(
        url=update.message.text,
        update=update,
        context=context,
        texts=texts,
        progress_callback=on_progress
    )
    
    # Обработать результат
    if file_path:
        # Успешно → отправить файл
        with open(file_path, 'rb') as f:
            await context.bot.send_audio(chat_id=update.message.chat_id, audio=InputFile(f))
    elif result == "FILE_TOO_LARGE":
        # Файл > 50MB
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text=f"⚠️ Файл >50МБ. Скачай сам: https://youtu.be/{youtube_id}"
        )
    elif result == "VIDEO_NOT_AVAILABLE":
        await context.bot.send_message(chat_id=update.message.chat_id, text="❌ Видео недоступно")
    elif result == "GEO_BLOCKED":
        await context.bot.send_message(chat_id=update.message.chat_id, text="❌ Видео недоступно в вашем регионе")
    else:
        # Другая ошибка
        await context.bot.send_message(chat_id=update.message.chat_id, text=f"❌ Ошибка: {result}")
```

### Шаг 4: Опционально — периодическая очистка кэша

```python
from utils.cache_manager import cleanup_cache

async def periodic_cleanup(context: ContextTypes.DEFAULT_TYPE) -> None:
    removed = cleanup_cache(max_age_days=30)
    logger.info(f"Cache cleanup: removed {removed} entries")

# В register() функции:
application.job_queue.run_repeating(
    periodic_cleanup,
    interval=7 * 24 * 3600,  # Weekly
    first=10
)
```

## 📦 Импорты для добавления в `handlers/downloader.py`

```python
from utils.cache_manager import init_cache_db, check_cached_file
from utils.caching_downloader import CachingDownloader, TELEGRAM_FILE_SIZE_LIMIT_BYTES
from telegram import InputFile
```

## ⚙️ Константы и настройки

| Параметр | Значение | Где |
|----------|----------|-----|
| `MUSIC_DIR` | `/home/music` | `utils/cache_manager.py` |
| `TELEGRAM_FILE_SIZE_LIMIT_BYTES` | 50 МБ | `utils/caching_downloader.py` |
| Audio format | MP3 120 kbps | yt-dlp postprocessor в `_get_ydl_opts()` |
| Cache TTL | Бесконечно (удаляется только старше 30 дней) | `cleanup_cache()` |

## 🔍 Примеры использования

### Пример 1: Проверить, закэширован ли видео
```python
youtube_id = "dQw4w9WgXcQ"
cached_path = check_cached_file(youtube_id)
if cached_path:
    print(f"Уже закэширован: {cached_path}")
else:
    print("Нужно скачать")
```

### Пример 2: Скачать, кэшировать и отправить
```python
file_path, yt_id, result = await downloader.download_and_cache(
    url="https://youtu.be/dQw4w9WgXcQ",
    update=update,
    context=context,
    texts={"downloading_audio": "⏳ Загружаю..."},
)

if file_path:
    with open(file_path, 'rb') as f:
        await bot.send_audio(chat_id=chat_id, audio=InputFile(f))
elif result == "FILE_TOO_LARGE":
    await bot.send_message(chat_id=chat_id, text="⚠️ Файл слишком большой")
```

## ✅ Что реализовано

- ✅ Константа `MUSIC_DIR = "/home/music"` с автосозданием
- ✅ MP3 120 kbps через yt-dlp postprocessor
- ✅ Имя файла: `{artist} - {title} [{youtube_id}].mp3` + sanitize
- ✅ Извлечение youtube_id из info_dict['id']
- ✅ Проверка кэша перед скачиванием
- ✅ SQLite база `cache.db` с таблицей cache
- ✅ Прогресс-хуки yt-dlp (callback)
- ✅ Проверка размера файла (≤50MB или >50MB)
- ✅ Обработка ошибок (VIDEO_NOT_AVAILABLE, GEO_BLOCKED, VIDEO_PRIVATE, etc.)
- ✅ Поддержка cookies для yt-dlp
- ✅ Async/await для python-telegram-bot v20+/v21+

## ❌ Важно: Что НЕ делать

1. **Не вызывайте `init_cache_db()` несколько раз** — достаточно один раз в `main()`
2. **Не передавайте None вместо `db_path`** — функции используют дефолт `/home/music/cache.db`
3. **Не редактируйте БД напрямую** — используйте функции из `cache_manager.py`
4. **Не удаляйте директорию `/home/music` вручную** — модуль автоматически пересоздаст
5. **Убедитесь, что FFmpeg установлен** — или передайте правильный путь в `CachingDownloader()`

## 🐛 Отладка

Если что-то не работает:
1. Проверьте права на `/home/music`: `ls -la /home/music`
2. Убедитесь, что FFmpeg установлен: `which ffmpeg`
3. Посмотрите логи: `grep "Cache\|Download\|Error" bot.log`
4. Проверьте БД: `sqlite3 /home/music/cache.db "SELECT * FROM cache;"`

---

**Все готово к интеграции! Два новых модуля полностью независимы и не требуют изменений существующего кода, только добавления вызовов в нужные места.**
