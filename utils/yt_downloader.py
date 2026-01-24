"""Utilities for downloading and processing audio with yt-dlp."""
from __future__ import annotations

import asyncio
import io
import logging
import os
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

import yt_dlp
from PIL import Image
from mutagen.id3 import APIC, ID3, ID3NoHeaderError, TALB, TDRC, TIT2, TPE1
from yt_dlp.utils import sanitize_filename

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DownloadResult:
    files: List[Tuple[str, str]]
    artist: str
    info: Dict


def convert_to_ytmusic(original_url: str) -> str:
    """Convert standard YouTube links to music.youtube.com counterparts when possible."""
    try:
        url = original_url.strip()
        if 'music.youtube.com' in url:
            return url
        if 'youtu.be/' in url:
            parts = url.split('/')
            video_id = parts[-1].split('?')[0]
            return f'https://music.youtube.com/watch?v={video_id}'
        parsed = urlparse(url)
        if 'youtube.com' in parsed.netloc:
            query = parse_qs(parsed.query)
            video = query.get('v')
            if video:
                return f'https://music.youtube.com/watch?v={video[0]}'
        return original_url
    except Exception:
        return original_url


def blocking_yt_dlp_download(ydl_opts: Dict, url_to_download: str, max_retries: int = 2) -> None:
    """
    Perform a blocking yt-dlp download respecting the provided options.
    Includes retry logic for common failures (empty files, network issues).
    """
    yt_logger = logging.getLogger('yt_dlp')
    yt_logger.setLevel(logging.WARNING)
    
    last_error = None
    import time
    temp_dir = ydl_opts.get('outtmpl', '.').rsplit(os.sep, 1)[0]
    
    for attempt in range(1, max_retries + 1):
        files_before = set(os.listdir(temp_dir)) if os.path.exists(temp_dir) else set()
        
        try:
            logger.debug(f"[Download] Attempt {attempt}/{max_retries}: {url_to_download}")
            logger.debug(f"[Download] Temp dir: {temp_dir}")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url_to_download])
            
            # Verify files were actually created
            files_after = set(os.listdir(temp_dir)) if os.path.exists(temp_dir) else set()
            new_files = files_after - files_before
            
            if not new_files:
                raise yt_dlp.utils.DownloadError("No files created after download")
            
            # Check for zero-byte or suspiciously small files
            for f in new_files:
                fpath = os.path.join(temp_dir, f)
                if os.path.isfile(fpath):
                    size = os.path.getsize(fpath)
                    if size == 0 or (f.endswith('.mp3') and size < 8000):
                        logger.warning(f"[Download] Suspicious file size: {f} ({size} bytes), retrying...")
                        try:
                            os.remove(fpath)
                        except:
                            pass
                        raise yt_dlp.utils.DownloadError(f"Downloaded file too small: {size} bytes")
                    logger.debug(f"[Download] File created: {f} ({size} bytes)")
            
            logger.info(f"[Download] ✓ Successfully downloaded on attempt {attempt}")
            return  # Success
            
        except yt_dlp.utils.DownloadError as exc:
            error_msg = str(exc).lower()
            logger.warning(f"[Download] Attempt {attempt} failed: {exc}")
            
            # Check if error is retryable
            retryable_errors = [
                "empty",
                "no fragments",
                "connection",
                "timeout",
                "network",
                "403",
                "429",
                "socket",
                "ssl",
                "http error",
                "timed out",
                "connection reset",
                "broken pipe",
                "too small",
                "no data",
            ]
            
            is_retryable = any(err in error_msg for err in retryable_errors)
            
            if not is_retryable or attempt >= max_retries:
                # Non-retryable or last attempt
                logger.error(f"[Download] ✗ Error (not retrying): {exc}")
                raise
            
            # Wait before retry
            wait_time = 2 ** attempt  # Exponential backoff: 2s, 4s
            logger.info(f"[Download] Retrying in {wait_time}s...")
            time.sleep(wait_time)
            
        except Exception as exc:
            logger.error(f"[Download] ✗ Unexpected error on attempt {attempt}: {type(exc).__name__}: {exc}")
            raise


def compress_image(image_path, max_size: int = 204_800) -> bytes:
    """Compress an image (bytes or path) to stay below max_size bytes."""
    if isinstance(image_path, (bytes, bytearray)):
        img = Image.open(io.BytesIO(image_path))
    else:
        img = Image.open(image_path)

    try:
        if img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        output = io.BytesIO()
        quality = 95
        while True:
            output.seek(0)
            output.truncate(0)
            img.save(output, 'JPEG', quality=quality, optimize=True, progressive=True)
            size = output.tell()
            if size <= max_size or quality <= 20:
                break
            quality -= 5

        if output.tell() > max_size:
            width, height = img.size
            while output.tell() > max_size and (width > 200 or height > 200):
                width = int(width * 0.9)
                height = int(height * 0.9)
                resized = img.resize((width, height), Image.LANCZOS)
                output.seek(0)
                output.truncate(0)
                resized.save(output, 'JPEG', quality=max(20, quality - 5), optimize=True, progressive=True)
                if output.tell() <= max_size:
                    break
                img = resized

        return output.getvalue()
    finally:
        try:
            img.close()
        except Exception:
            pass


def _extract_title_and_artist(info: Dict) -> Tuple[str, str]:
    title = info.get('track') or info.get('title') or 'Unknown'
    artist = info.get('artist') or ''
    if not artist and info.get('artists') and isinstance(info.get('artists'), (list, tuple)):
        candidates = []
        for entry in info['artists']:
            if isinstance(entry, dict):
                name = entry.get('name')
            else:
                name = str(entry)
            if name:
                candidates.append(name)
        if candidates:
            artist = ', '.join(candidates)
    if not artist:
        artist = info.get('uploader') or info.get('channel') or ''
    if not info.get('track') and '-' in title and not artist:
        parts = title.split('-')
        if len(parts) >= 2:
            possible_artist = parts[0].strip()
            possible_title = '-'.join(parts[1:]).strip()
            if possible_artist and possible_title:
                artist = possible_artist
                title = possible_title
    return title, artist


def _pull_thumbnail(info: Dict) -> Optional[str]:
    thumbnail_url = None
    try:
        thumb = info.get('thumbnail')
        if isinstance(thumb, str) and thumb:
            thumbnail_url = thumb
        elif info.get('thumbnails'):
            thumbs = info['thumbnails']
            if isinstance(thumbs, list) and thumbs:
                thumbs_sorted = sorted(thumbs, key=lambda x: int(x.get('width') or 0), reverse=True)
                thumbnail_url = thumbs_sorted[0].get('url')
    except Exception:
        thumbnail_url = None
    return thumbnail_url


def _embed_metadata(audio_path: str, title: str, artist: str, info: Dict, jpeg_data: Optional[bytes]) -> None:
    try:
        try:
            id3 = ID3(audio_path)
        except ID3NoHeaderError:
            id3 = ID3()

        id3.add(TIT2(encoding=3, text=title))

        tag_artist = artist or info.get('album_artist') or info.get('uploader')
        if tag_artist:
            id3.add(TPE1(encoding=3, text=str(tag_artist)))

        if info.get('album'):
            id3.add(TALB(encoding=3, text=str(info.get('album'))))

        if info.get('release_year'):
            id3.add(TDRC(encoding=3, text=str(info.get('release_year'))))
        elif info.get('release_date'):
            id3.add(TDRC(encoding=3, text=str(info.get('release_date'))))

        if info.get('artists') and isinstance(info.get('artists'), (list, tuple)):
            performers = []
            for entry in info['artists']:
                if isinstance(entry, dict):
                    name = entry.get('name')
                else:
                    name = str(entry)
                if name:
                    performers.append(name)
            if performers:
                id3.add(TPE1(encoding=3, text=', '.join(performers)))

        if jpeg_data:
            id3.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=jpeg_data))

        id3.save(audio_path)
    except Exception as exc:
        logger.error("Error embedding metadata for %s: %s", audio_path, exc)


def _prepare_downloaded_files(temp_dir: str, info: Dict, artist: str, title: str, max_thumb_size: int = 200_000) -> List[Tuple[str, str]]:
    audio_files = [f for f in os.listdir(temp_dir) if f.endswith('.mp3')]
    thumbnail_files = [f for f in os.listdir(temp_dir) if f.lower().endswith(('.jpg', '.jpeg', '.webp'))]

    # Validate audio files - check for empty or corrupted files
    valid_audio_files = []
    for audio_file in audio_files:
        audio_path = os.path.join(temp_dir, audio_file)
        try:
            file_size = os.path.getsize(audio_path)
            if file_size < 5000:  # Less than 5KB = likely empty or corrupted
                logger.warning(f"[Download] Skipping tiny/empty file {audio_file}: {file_size} bytes")
                try:
                    os.remove(audio_path)
                except Exception:
                    pass
                continue
            valid_audio_files.append(audio_file)
        except Exception as exc:
            logger.error(f"[Download] Error checking file {audio_file}: {exc}")
    
    audio_files = valid_audio_files

    if not audio_files:
        logger.error("[Download] No valid audio files found after validation")
        all_files = os.listdir(temp_dir)
        logger.debug(f"[Download] Files in temp dir: {all_files}")
        return []

    downloaded: List[Tuple[str, str]] = []
    thumbnail_url = _pull_thumbnail(info)

    jpeg_data: Optional[bytes] = None
    if thumbnail_url:
        try:
            with urlopen(thumbnail_url, timeout=15) as response:
                raw = response.read()
            jpeg_data = compress_image(raw, max_size=max_thumb_size)
        except Exception as exc:
            logger.debug("Failed to fetch remote thumbnail %s: %s", thumbnail_url, exc)

    if not jpeg_data and thumbnail_files:
        thumbnail_path = os.path.join(temp_dir, thumbnail_files[0])
        try:
            jpeg_data = compress_image(thumbnail_path, max_size=max_thumb_size)
        except Exception as exc:
            logger.debug("Failed to process local thumbnail %s: %s", thumbnail_path, exc)
        else:
            try:
                os.remove(thumbnail_path)
            except Exception:
                pass

    for audio_file in audio_files:
        audio_path = os.path.join(temp_dir, audio_file)
        _embed_metadata(audio_path, title, artist, info, jpeg_data)

        new_filename = sanitize_filename(f"{artist} - {title}.mp3" if artist else f"{title}.mp3")
        new_path = os.path.join(temp_dir, new_filename)
        try:
            os.rename(audio_path, new_path)
        except Exception:
            new_path = audio_path
        downloaded.append((new_path, title))

    return downloaded


def create_ydl_opts(temp_dir: str, cookies_path: Optional[str], ffmpeg_path: Optional[str], progress_hook: Optional[Callable[[Dict], None]] = None) -> Dict:
    opts: Dict = {
        'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
        'format': 'bestaudio/best',
        'cookiefile': cookies_path if cookies_path and os.path.exists(cookies_path) else None,
        'progress_hooks': [progress_hook] if progress_hook else None,
        'nocheckcertificate': True,
        # Allow yt-dlp to bypass geo-restrictions when possible
        'geo_bypass': True,
        'geo_bypass_country': 'US',
        'quiet': True,
        'no_warnings': True,
        'ffmpeg_location': ffmpeg_path if ffmpeg_path else None,
        'noplaylist': True,
        'writethumbnail': True,
        # Better socket timeout handling
        'socket_timeout': 30,
        # Retry on network errors
        'retries': 3,
        # Skip unavailable fragments (better for HLS)
        'skip_unavailable_fragments': True,
        # Fragment retries
        'fragment_retries': 3,
        # Better error handling
        'keepvideo': False,
        'quiet': True,
        # For HLS streams specifically
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        },
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }],
        'verbose': False,
    }
    return {k: v for k, v in opts.items() if v is not None}


async def download_audio(url: str, temp_dir: str, cookies_path: Optional[str], ffmpeg_path: Optional[str], progress_hook: Optional[Callable[[Dict], None]] = None) -> DownloadResult:
    ydl_opts = create_ydl_opts(temp_dir, cookies_path, ffmpeg_path, progress_hook)
    url_to_use = convert_to_ytmusic(url)
    logger.info("Starting download for %s (using %s)", url, url_to_use)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url_to_use, download=False)

    title, artist = _extract_title_and_artist(info)

    await asyncio.to_thread(blocking_yt_dlp_download, ydl_opts, url_to_use)

    files = _prepare_downloaded_files(temp_dir, info, artist, title)
    if not files:
        raise FileNotFoundError('audio file not found')

    return DownloadResult(files=files, artist=artist, info=info)
