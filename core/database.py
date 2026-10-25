"""
REA Core - Local SQLite Persistence Layer
Manages offline user library:
  - Favorites: starred tracks with instant toggling
  - History: recently played tracks (capped at 100 records)
  - Playlists: custom local user playlists without requiring YouTube authentication
"""

import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional


class DatabaseManager:
    """Thread-safe SQLite database manager for REA Music."""

    _instance: Optional["DatabaseManager"] = None
    _lock = threading.Lock()

    def __new__(cls, db_path: Optional[str] = None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_db(db_path)
            return cls._instance

    def _init_db(self, db_path: Optional[str] = None):
        if db_path is None:
            # 1. Prefer existing local data/reamusic.db in project root or current working directory
            local_db = os.path.join(os.getcwd(), "data", "reamusic.db")
            if os.path.exists(local_db):
                self.db_path = local_db
            else:
                # 2. User profile directory ~/.config/reamusic/reamusic.db for permanent user library
                config_dir = os.path.expanduser("~/.config/reamusic")
                os.makedirs(config_dir, exist_ok=True)
                self.db_path = os.path.join(config_dir, "reamusic.db")
        else:
            self.db_path = db_path
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)

        self._local_lock = threading.Lock()
        self._create_tables()

    def _get_connection(self) -> sqlite3.Connection:
        """Creates a connection with row factory configured."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_tables(self):
        """Initializes database schema."""
        with self._local_lock, self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Favorites Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    artist TEXT,
                    duration TEXT,
                    thumbnail_url TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. History Table (Capped at 100 items)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    artist TEXT,
                    duration TEXT,
                    thumbnail_url TEXT,
                    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 3. Custom Playlists Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 4. Playlist Tracks Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS playlist_tracks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    playlist_id INTEGER NOT NULL,
                    video_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    artist TEXT,
                    duration TEXT,
                    thumbnail_url TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE
                )
            """)

            # Create Indexes for fast lookup
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fav_vid ON favorites(video_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hist_played ON history(played_at DESC)")
            conn.commit()

    # -------------------------------------------------------------
    # Favorites API
    # -------------------------------------------------------------

    def is_favorite(self, video_id: str) -> bool:
        """Checks if a given video_id is starred in favorites."""
        if not video_id:
            return False
        with self._local_lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM favorites WHERE video_id = ? LIMIT 1", (video_id,))
            return cursor.fetchone() is not None

    def add_favorite(self, track: Dict[str, Any]) -> bool:
        """Adds a track to favorites. Returns True on success."""
        vid = track.get("video_id")
        if not vid:
            return False
        with self._local_lock, self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO favorites (video_id, title, artist, duration, thumbnail_url)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    vid,
                    track.get("title", "Untitled"),
                    track.get("artist", ""),
                    track.get("duration", ""),
                    track.get("thumbnail_url", ""),
                ))
                conn.commit()
                return cursor.rowcount > 0
            except Exception:
                return False

    def remove_favorite(self, video_id: str) -> bool:
        """Removes a track from favorites."""
        if not video_id:
            return False
        with self._local_lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM favorites WHERE video_id = ?", (video_id,))
            conn.commit()
            return cursor.rowcount > 0

    def toggle_favorite(self, track: Dict[str, Any]) -> bool:
        """Toggles favorite state. Returns True if now favorite, False if removed."""
        vid = track.get("video_id")
        if not vid:
            return False
        if self.is_favorite(vid):
            self.remove_favorite(vid)
            return False
        else:
            self.add_favorite(track)
            return True

    def get_favorites(self) -> List[Dict[str, Any]]:
        """Retrieves all favorites ordered by added date descending."""
        with self._local_lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT video_id, title, artist, duration, thumbnail_url, added_at FROM favorites ORDER BY added_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    # -------------------------------------------------------------
    # History API (Capped at 100 items)
    # -------------------------------------------------------------

    def add_history(self, track: Dict[str, Any]) -> None:
        """Records a track in playback history and trims to the 100 most recent."""
        vid = track.get("video_id")
        if not vid:
            return
        with self._local_lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO history (video_id, title, artist, duration, thumbnail_url)
                VALUES (?, ?, ?, ?, ?)
            """, (
                vid,
                track.get("title", "Untitled"),
                track.get("artist", ""),
                track.get("duration", ""),
                track.get("thumbnail_url", ""),
            ))
            # Delete older entries exceeding the 100 cap
            cursor.execute("""
                DELETE FROM history WHERE id NOT IN (
                    SELECT id FROM history ORDER BY played_at DESC LIMIT 100
                )
            """)
            conn.commit()

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent playback history."""
        with self._local_lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT video_id, title, artist, duration, thumbnail_url, played_at FROM history ORDER BY played_at DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def clear_history(self) -> None:
        """Clears all entries from history."""
        with self._local_lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM history")
            conn.commit()

    # -------------------------------------------------------------
    # Custom Playlists API
    # -------------------------------------------------------------

    def create_playlist(self, name: str) -> Optional[int]:
        """Creates a new playlist and returns its ID."""
        name = name.strip()
        if not name:
            return None
        with self._local_lock, self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO playlists (name) VALUES (?)", (name,))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                return None

    def get_playlists(self) -> List[Dict[str, Any]]:
        """Lists all local playlists."""
        with self._local_lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.id, p.name, p.created_at, COUNT(pt.id) AS track_count
                FROM playlists p
                LEFT JOIN playlist_tracks pt ON p.id = pt.playlist_id
                GROUP BY p.id
                ORDER BY p.name ASC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def add_to_playlist(self, playlist_id: int, track: Dict[str, Any]) -> bool:
        """Adds a track to a specific playlist."""
        vid = track.get("video_id")
        if not vid:
            return False
        with self._local_lock, self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO playlist_tracks (playlist_id, video_id, title, artist, duration, thumbnail_url)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    playlist_id,
                    vid,
                    track.get("title", "Untitled"),
                    track.get("artist", ""),
                    track.get("duration", ""),
                    track.get("thumbnail_url", ""),
                ))
                conn.commit()
                return True
            except Exception:
                return False

    def get_playlist_tracks(self, playlist_id: int) -> List[Dict[str, Any]]:
        """Retrieves tracks contained in a playlist."""
        with self._local_lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT video_id, title, artist, duration, thumbnail_url, added_at
                FROM playlist_tracks
                WHERE playlist_id = ?
                ORDER BY added_at ASC
            """, (playlist_id,))
            return [dict(row) for row in cursor.fetchall()]

    def delete_playlist(self, playlist_id: int) -> bool:
        """Deletes a playlist and its associated tracks."""
        with self._local_lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
            conn.commit()
            return cursor.rowcount > 0
