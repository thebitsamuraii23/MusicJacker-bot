"""SQLite cache manager for downloaded audio files."""
from __future__ import annotations

import os
import re
import sqlite3
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Cache directory constant
MUSIC_DIR = "/home/music"


def _ensure_music_dir() -> None:
    """Create MUSIC_DIR if it doesn't exist."""
    Path(MUSIC_DIR).mkdir(parents=True, exist_ok=True)


def _sanitize_filename(text: str) -> str:
    """Sanitize filename by removing/replacing forbidden characters."""
    # Replace forbidden characters with underscore
    text = re.sub(r'[<>:"/\\|?*]', '_', text)
    # Remove leading/trailing spaces and dots
    text = text.strip('. ')
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    return text


def init_cache_db(db_path: str = None) -> str:
    """Initialize SQLite database for caching. Returns path to DB."""
    if db_path is None:
        db_path = os.path.join(MUSIC_DIR, 'cache.db')
    
    _ensure_music_dir()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                youtube_id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                title TEXT,
                artist TEXT,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        logger.info(f"Cache database initialized at {db_path}")
        return db_path
    except Exception as exc:
        logger.error(f"Failed to initialize cache database: {exc}")
        raise


def check_cached_file(youtube_id: str, db_path: str = None) -> Optional[str]:
    """
    Check if file with this youtube_id exists in cache.
    Returns file path if exists and file exists on disk, otherwise None.
    """
    if db_path is None:
        db_path = os.path.join(MUSIC_DIR, 'cache.db')
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT file_path FROM cache WHERE youtube_id = ?', (youtube_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            file_path = result[0]
            # Verify file still exists on disk
            if os.path.exists(file_path):
                logger.debug(f"Cache hit for youtube_id {youtube_id}")
                return file_path
            else:
                logger.warning(f"Cache entry found but file missing: {file_path}")
                # Optionally clean up the stale cache entry
                _remove_cache_entry(youtube_id, db_path)
        return None
    except Exception as exc:
        logger.error(f"Error checking cache for {youtube_id}: {exc}")
        return None


def _remove_cache_entry(youtube_id: str, db_path: str) -> None:
    """Remove a cache entry from database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM cache WHERE youtube_id = ?', (youtube_id,))
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.error(f"Error removing cache entry: {exc}")


def add_to_cache(youtube_id: str, file_path: str, title: str = "", artist: str = "", 
                 db_path: str = None) -> bool:
    """Add file to cache database."""
    if db_path is None:
        db_path = os.path.join(MUSIC_DIR, 'cache.db')
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO cache (youtube_id, file_path, title, artist, added_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (youtube_id, file_path, title, artist))
        conn.commit()
        conn.close()
        logger.info(f"Added to cache: {youtube_id} -> {file_path}")
        return True
    except Exception as exc:
        logger.error(f"Error adding to cache: {exc}")
        return False


def generate_cache_filename(artist: str, title: str, youtube_id: str) -> str:
    """Generate cache filename in format: {artist} - {title} [{youtube_id}].mp3"""
    sanitized_artist = _sanitize_filename(artist) if artist else "Unknown"
    sanitized_title = _sanitize_filename(title) if title else "Unknown"
    filename = f"{sanitized_artist} - {sanitized_title} [{youtube_id}].mp3"
    return filename


def get_cache_file_path(artist: str, title: str, youtube_id: str) -> str:
    """Get full cache file path for audio."""
    _ensure_music_dir()
    filename = generate_cache_filename(artist, title, youtube_id)
    return os.path.join(MUSIC_DIR, filename)


def cleanup_cache(max_age_days: int = 30, db_path: str = None) -> int:
    """
    Remove cache entries older than max_age_days.
    Returns number of removed entries.
    """
    if db_path is None:
        db_path = os.path.join(MUSIC_DIR, 'cache.db')
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT youtube_id, file_path FROM cache 
            WHERE datetime(added_at) <= datetime('now', ? || ' days')
        ''', (f'-{max_age_days}',))
        old_entries = cursor.fetchall()
        
        for youtube_id, file_path in old_entries:
            # Try to delete file
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Deleted old cache file: {file_path}")
            except Exception as exc:
                logger.warning(f"Failed to delete file {file_path}: {exc}")
            
            # Remove from database
            cursor.execute('DELETE FROM cache WHERE youtube_id = ?', (youtube_id,))
        
        conn.commit()
        conn.close()
        logger.info(f"Cleanup complete: removed {len(old_entries)} old cache entries")
        return len(old_entries)
    except Exception as exc:
        logger.error(f"Error during cache cleanup: {exc}")
        return 0
