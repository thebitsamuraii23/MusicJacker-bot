# 📚 Implementation Overview Diagram

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Telegram User Message                   │
│                    (URL or song query)                        │
└────────────────────────────┬────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Message Handler │
                    │  (async function)│
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        │         ┌──────────▼──────────┐        │
        │         │ send_cached_or_     │        │
        │         │ download_audio()    │        │
        │         │ (cache_utils.py)    │        │
        │         └──────────┬──────────┘        │
        │                    │                    │
   ┌────▼──────────┐    ┌────▼───────┐    ┌──────▼──────┐
   │ Check Cache   │    │  Download  │    │ Error Handle│
   │ (DB lookup)   │    │ (yt-dlp +  │    │             │
   │               │    │ FFmpeg)    │    │             │
   └────┬──────────┘    └────┬───────┘    └──────┬──────┘
        │                    │                    │
        │ Cache Hit          │ Download OK        │ Error
        │ ✅                 │ ✅                 │ ❌
        │                    │                    │
   ┌────▼────────────┐ ┌─────▼──────────┐ ┌─────▼───────┐
   │ Send from       │ │ Check Size     │ │ Send Error  │
   │ /home/music/    │ │ ≤50MB?         │ │ Message     │
   │ (instant ⚡)    │ │                │ │             │
   └────┬────────────┘ └─────┬──────────┘ └─────┬───────┘
        │                    │                   │
        │              ┌─────▴──────┐            │
        │              │ Size OK?    │            │
        │              └──┬──────┬───┘            │
        │         ┌──────┘      └──────┐          │
        │         │                    │          │
        │    ┌────▼────┐          ┌────▼──┐      │
        │    │ ≤50MB   │          │ >50MB │      │
        │    │ Save to │          │ Return│      │
        │    │ cache   │          │ error │      │
        │    │ Add to  │          │ code  │      │
        │    │ SQLite  │          │       │      │
        │    └────┬────┘          └────┬──┘      │
        │         │                    │         │
        ├─────────┤    ┌───────────────┤         │
        │         │    │               │         │
        │    ┌────▼────▼────┐    ┌─────▼──────┐ │
        │    │ Send Audio   │    │ Show       │ │
        │    │ File to User │    │ Warning:   │ │
        │    │ as InputFile │    │ File >50MB │ │
        │    │ (Telegram    │    │ Get from   │ │
        │    │ send_audio)  │    │ YouTube    │ │
        │    └────────┬─────┘    └─────┬──────┘ │
        │             │                │        │
        └─────────────┼────────────────┼────────┘
                      │                │
                      └────────┬───────┘
                             │
                    ┌────────▼────────┐
                    │  User sees file  │
                    │  or error        │
                    │  message         │
                    └──────────────────┘
```

## Database Schema

```sql
CREATE TABLE cache (
    youtube_id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    title TEXT,
    artist TEXT,
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Example rows:**
```
youtube_id          │ file_path                                    │ title              │ artist
────────────────────┼───────────────────────────────────────────────┼────────────────────┼──────────────
dQw4w9WgXcQ         │ /home/music/Rick Astley - Never...           │ Never Gonna Give... │ Rick Astley
E8A2aqPjGhQ         │ /home/music/The Weeknd - Blinding            │ Blinding Lights      │ The Weeknd
```

## File Storage

```
/home/music/
├── cache.db                           # SQLite database
├── Rick Astley - Never Gonna Give... [dQw4w9WgXcQ].mp3    # Cached audio
├── The Weeknd - Blinding Lights... [E8A2aqPjGhQ].mp3       # Cached audio
└── Artist Name - Song Title... [youtube_id].mp3             # Format pattern
```

## Data Flow

### First Download (Cache Miss)

```
User Input → yt-dlp extract info → Check Cache (miss) 
    → Download MP3 120kbps → Check Size (≤50MB) 
    → Save to /home/music/ → Add to SQLite 
    → Send to user
```

### Repeated Request (Cache Hit)

```
User Input → Check Cache (HIT!) 
    → Load from /home/music/ → Send to user ⚡ (instant)
```

### Large File (>50MB)

```
User Input → Check Cache (miss/hit) 
    → Download/Get → Check Size (>50MB) 
    → Don't send file → Send warning + YouTube link
```

## Function Call Sequence

### Minimal Integration

```python
# 1. Initialize (once at startup)
init_cache_db()

# 2. Create downloader (once per bot lifetime)
downloader = CachingDownloader(ffmpeg_path, cookies_path)

# 3. In message handler (per user message)
await send_cached_or_download_audio(
    query,
    update,
    context,
    downloader,
    texts
)
```

### Under the Hood

```
send_cached_or_download_audio()
    │
    ├─→ download_and_cache()
    │       │
    │       ├─→ Extract info from yt-dlp
    │       ├─→ check_cached_file(youtube_id)
    │       │       │
    │       │       └─→ Query SQLite → Found? Return path
    │       │
    │       ├─→ Download with progress hooks
    │       ├─→ Check file size
    │       │   ├─→ ≤50MB: Save to /home/music/
    │       │   │           add_to_cache()
    │       │   │           Return (file_path, id, title)
    │       │   └─→ >50MB: Return (None, id, "FILE_TOO_LARGE")
    │       └─→ Handle errors
    │
    ├─→ Process result
    │   ├─→ File exists? → Send audio
    │   ├─→ Too large? → Send warning + link
    │   └─→ Error? → Send error message
    │
    └─→ Return True/False
```

## Integration Map

```
your_bot.py (main)
    ↓
    ├─→ init_cache_db() ........................ from utils.cache_manager
    ├─→ create downloader ..................... from utils.caching_downloader
    │
    └─→ handlers/downloader.py
            │
            ├─→ @message_handler
            │   └─→ send_cached_or_download_audio() ....... from utils.cache_utils
            │       │
            │       ├─→ CachingDownloader.download_and_cache()
            │       │   ├─→ check_cached_file() ... from utils.cache_manager
            │       │   ├─→ extract_info() (yt-dlp)
            │       │   ├─→ add_to_cache() ......... from utils.cache_manager
            │       │   └─→ Handle errors
            │       │
            │       ├─→ Send audio from file (telegram API)
            │       ├─→ Send error message
            │       └─→ Send warning message
            │
            └─→ (optional) periodic_cleanup()
                └─→ cleanup_cache() ........... from utils.cache_manager
```

## Error Handling Flow

```
Download attempt
    ├─→ DownloadError (yt-dlp)
    │   ├─→ "not available" → VIDEO_NOT_AVAILABLE
    │   ├─→ "geo" → GEO_BLOCKED  
    │   ├─→ "private" → VIDEO_PRIVATE
    │   └─→ other → Download error message
    │
    ├─→ File size > 50MB
    │   └─→ FILE_TOO_LARGE (user can download from YouTube)
    │
    ├─→ Cache DB error
    │   └─→ Logged but doesn't stop download
    │
    └─→ Unexpected error
        └─→ Generic error message to user
```

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Cache DB initialization | <1ms | Async, one-time |
| check_cached_file() | <5ms | SQLite lookup |
| Download (first) | 10-120s | Depends on file size |
| Download (cached) | <100ms | File serve from disk |
| send_audio() | 2-30s | Upload to Telegram API |

## Scalability

- **File storage**: 100GB+ possible in `/home/music/`
- **Database**: SQLite handles 1M+ records easily
- **Concurrent users**: Limited by hardware, not code
- **Memory**: Minimal - only loads downloading files in memory

## Security Considerations

- ✅ Input sanitization for filenames
- ✅ File path validation
- ✅ SQLite parameterized queries (no SQL injection)
- ✅ Error messages don't expose system paths to users
- ✅ Cookies file handled securely (if provided)

## That's the complete picture! 🎯
