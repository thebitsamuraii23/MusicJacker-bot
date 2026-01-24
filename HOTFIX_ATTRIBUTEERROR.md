# 🔴 HOTFIX - AttributeError in blocking_yt_dlp_download

## Issue Found

**Error:** `AttributeError: 'dict' object has no attribute 'rsplit'`

**Location:** `utils/yt_downloader.py`, line 61 in `blocking_yt_dlp_download()`

**Cause:** Attempting to extract `temp_dir` from `ydl_opts` dictionary in an unsafe way

```python
# BROKEN ❌
temp_dir = ydl_opts.get('outtmpl', '.').rsplit(os.sep, 1)[0]
```

## Root Cause

The `blocking_yt_dlp_download()` function was trying to extract the temporary directory path from the `ydl_opts` dictionary, but this approach was fragile and could fail if the dictionary structure wasn't exactly as expected.

## Fix Applied

Changed the function signature to **accept `temp_dir` as a parameter** instead of trying to extract it:

```python
# FIXED ✅
def blocking_yt_dlp_download(ydl_opts: Dict, url_to_download: str, temp_dir: str, max_retries: int = 2) -> None:
    # temp_dir is now a direct parameter
```

### Changes Made

**File:** `utils/yt_downloader.py`

**Change 1:** Function signature (line 52)
```python
# Before
def blocking_yt_dlp_download(ydl_opts: Dict, url_to_download: str, max_retries: int = 2) -> None:
    temp_dir = ydl_opts.get('outtmpl', '.').rsplit(os.sep, 1)[0]

# After
def blocking_yt_dlp_download(ydl_opts: Dict, url_to_download: str, temp_dir: str, max_retries: int = 2) -> None:
    # temp_dir directly available as parameter
```

**Change 2:** Function call (line 386)
```python
# Before
await asyncio.to_thread(blocking_yt_dlp_download, ydl_opts, url_to_use)

# After
await asyncio.to_thread(blocking_yt_dlp_download, ydl_opts, url_to_use, temp_dir)
```

## Testing

✅ **Syntax validation:** Passed (no errors)  
✅ **Type checking:** Correct parameter types  
✅ **Backwards compatibility:** Not affected (internal function)

## Deployment

### For Production Servers

Copy the updated file:
```bash
cp utils/yt_downloader.py /root/MusicJacker-bot/utils/yt_downloader.py
```

Restart the bot:
```bash
systemctl restart musicjacker-bot
```

## Verification

The bot should now handle downloads without the AttributeError. Test with a music search:

```
User: "starboy"
Expected: Download starts without AttributeError
Logs: Should show "[Download] Attempt 1/2: ..." instead of crash
```

## Status

✅ Hotfix ready  
✅ Code compiled successfully  
✅ All syntax valid  
✅ Ready to deploy to production

---

**Note:** This was a critical bug in the initial implementation. The fix makes the code more robust by explicitly passing the temporary directory instead of trying to extract it from configuration.
