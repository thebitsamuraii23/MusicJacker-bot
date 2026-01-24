"""Download with caching functionality for audio files."""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Optional, Callable

import yt_dlp
from telegram import Update
from telegram.ext import ContextTypes

from utils.cache_manager import (
    MUSIC_DIR, check_cached_file, add_to_cache, get_cache_file_path,
    _ensure_music_dir, search_cache_by_name
)

logger = logging.getLogger(__name__)

# Telegram's file size limit: 50 MB
TELEGRAM_FILE_SIZE_LIMIT_BYTES = 50 * 1024 * 1024


class CachingDownloader:
    """Download audio with automatic caching and size checking."""
    
    def __init__(self, ffmpeg_path: Optional[str] = None, cookies_path: Optional[str] = None):
        """
        Initialize downloader.
        
        Args:
            ffmpeg_path: Path to ffmpeg executable
            cookies_path: Path to cookies file for yt-dlp
        """
        self.ffmpeg_path = ffmpeg_path or '/usr/bin/ffmpeg'
        self.cookies_path = cookies_path
        self.ffmpeg_available = os.path.exists(self.ffmpeg_path) and os.access(self.ffmpeg_path, os.X_OK)
    
    def _get_ydl_opts(self, output_path: str) -> Dict:
        """Get yt-dlp options for audio download."""
        opts = {
            'format': 'bestaudio/best',
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '120',
                }
            ],
            'quiet': False,
            'no_warnings': False,
            'outtmpl': output_path.replace('.mp3', ''),  # yt-dlp will add extension
            'socket_timeout': 30,
            'nocheckcertificate': True,
            'default_search': 'auto',
        }
        
        if self.cookies_path and os.path.exists(self.cookies_path):
            opts['cookiefile'] = self.cookies_path
        
        if self.ffmpeg_available:
            opts['ffmpeg_location'] = self.ffmpeg_path
        
        return opts
    
    async def download_and_cache(
        self,
        url: str,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        texts: Dict[str, str],
        progress_callback: Optional[Callable] = None,
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Download audio from URL, cache it, and check size.
        
        Args:
            url: YouTube URL or search query
            update: Telegram Update object
            context: Telegram context
            texts: Dictionary with user messages (localized)
            progress_callback: Async callback for progress updates (optional)
        
        Returns:
            Tuple of (file_path, youtube_id, title) if successful and file <= 50MB
            Tuple of (None, youtube_id, title) if file > 50MB
            Tuple of (None, None, error_message) if error occurred
        """
        chat_id = update.message.chat_id
        temp_dir = None
        
        try:
            logger.info(f"[Download] Starting: {url}")
            
            # Extract video info
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'nocheckcertificate': True,
                'socket_timeout': 30,
            }
            if self.cookies_path and os.path.exists(self.cookies_path):
                ydl_opts['cookiefile'] = self.cookies_path
            
            loop = asyncio.get_running_loop()
            
            def extract_info():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)
            
            logger.debug(f"[Extract] Extracting info from: {url}")
            info = await loop.run_in_executor(None, extract_info)
            
            youtube_id = info.get('id')
            title = info.get('title', 'Unknown')
            artist = info.get('uploader', 'Unknown Artist')
            
            logger.info(f"[Extract] Got: title='{title}', artist='{artist}', id={youtube_id}")
            
            if not youtube_id:
                logger.warning("[Download] Cannot extract video ID")
                return None, None, "Cannot extract video ID"
            
            # Check cache first by youtube_id
            logger.debug(f"[Cache] Checking by youtube_id: {youtube_id}")
            cached_path = check_cached_file(youtube_id)
            if cached_path:
                logger.info(f"[Cache] HIT by youtube_id: {youtube_id}")
                return cached_path, youtube_id, title
            
            # Check cache by name/artist (fuzzy search)
            logger.debug(f"[Cache] Checking by name: title='{title}', artist='{artist}'")
            name_cached = search_cache_by_name(title, artist, threshold=0.6)
            if name_cached:
                cached_path, cached_title, cached_artist = name_cached
                logger.info(f"[Cache] HIT by name: '{title}' -> '{cached_title}'")
                return cached_path, youtube_id, title  # Return original title but cached file
            
            # No cache found, proceed with download
            logger.info(f"[Download] No cache found, downloading: {title}")
            
            # Create temp directory for download
            temp_dir = tempfile.mkdtemp(prefix="music_dl_")
            output_path = os.path.join(temp_dir, f"audio.mp3")
            logger.debug(f"[Download] Temp dir: {temp_dir}")
            
            # Prepare download options
            ydl_opts = self._get_ydl_opts(output_path)
            
            # Add progress hook
            download_started = False
            
            def progress_hook(data: Dict):
                nonlocal download_started
                if data.get('status') == 'downloading':
                    download_started = True
                    if progress_callback:
                        percent = data.get('_percent_str', 'N/A').strip()
                        speed = data.get('_speed_str', 'N/A').strip()
                        eta = data.get('_eta_str', 'N/A').strip()
                        logger.debug(f"[Progress] {percent} | {speed} | ETA: {eta}")
                        try:
                            asyncio.run_coroutine_threadsafe(
                                progress_callback(percent, speed, eta),
                                loop
                            )
                        except Exception as exc:
                            logger.debug(f"[Progress] Callback error: {exc}")
            
            ydl_opts['progress_hooks'] = [progress_hook]
            
            # Download in executor
            logger.info(f"[Download] Starting download: {url}")
            def download_audio():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                return output_path
            
            downloaded_file = await loop.run_in_executor(None, download_audio)
            logger.info(f"[Download] Download completed")
            
            # Check if file was created
            if not os.path.exists(downloaded_file):
                logger.error(f"[Download] File not found after download: {downloaded_file}")
                return None, youtube_id, "Downloaded file not found on disk"
            
            file_size = os.path.getsize(downloaded_file)
            file_size_mb = round(file_size / (1024 * 1024), 2)
            logger.info(f"[Download] Downloaded '{title}': {file_size_mb} MB ({file_size} bytes)")
            
            # Check file size
            if file_size > TELEGRAM_FILE_SIZE_LIMIT_BYTES:
                logger.warning(f"[Size] File too large: {file_size_mb} MB > 50 MB for {youtube_id}")
                # Clean up temp file
                try:
                    os.remove(downloaded_file)
                except Exception:
                    pass
                return None, youtube_id, f"FILE_TOO_LARGE"
            
            # Move to cache directory
            logger.debug(f"[Cache] Moving file to cache directory")
            _ensure_music_dir()
            cache_path = get_cache_file_path(artist, title, youtube_id)
            logger.info(f"[Cache] Target path: {cache_path}")
            
            try:
                # Ensure unique filename
                if os.path.exists(cache_path):
                    logger.warning(f"[Cache] File already exists: {cache_path}")
                else:
                    os.rename(downloaded_file, cache_path)
                    logger.info(f"[Cache] ✅ File moved to: {cache_path}")
            except Exception as exc:
                logger.error(f"[Cache] Failed to move file: {exc}")
                # Try copying instead
                try:
                    import shutil
                    logger.debug(f"[Cache] Trying copy instead of move...")
                    shutil.copy2(downloaded_file, cache_path)
                    os.remove(downloaded_file)
                    logger.info(f"[Cache] ✅ File copied to: {cache_path}")
                except Exception as exc2:
                    logger.error(f"[Cache] Failed to copy file: {exc2}")
                    return None, youtube_id, "Failed to save file to cache"
            
            # Add to database
            logger.debug(f"[DB] Adding entry: {youtube_id}")
            add_to_cache(youtube_id, cache_path, title, artist)
            logger.info(f"[DB] ✅ Added to database: {youtube_id}")
            
            logger.info(f"[Success] ✅ Complete: {title} ({file_size_mb}MB) cached successfully")
            return cache_path, youtube_id, title
        
        except yt_dlp.utils.DownloadError as exc:
            error_msg = str(exc).lower()
            logger.error(f"[Error] yt-dlp error: {exc}")
            if 'not available' in error_msg or 'removed' in error_msg:
                return None, None, "VIDEO_NOT_AVAILABLE"
            elif 'geo' in error_msg or 'country' in error_msg:
                return None, None, "GEO_BLOCKED"
            elif 'private' in error_msg:
                return None, None, "VIDEO_PRIVATE"
            else:
                return None, None, f"Download error: {str(exc)[:100]}"
        
        except Exception as exc:
            logger.error(f"[Error] Unexpected error during download: {exc}", exc_info=True)
            return None, None, f"Unexpected error: {str(exc)[:100]}"
        
        finally:
            # Clean up temp directory
            if temp_dir and os.path.exists(temp_dir):
                try:
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as exc:
                    logger.warning(f"Failed to cleanup temp dir: {exc}")
