"""
REA Audio Engine - Core Module
Reverse-engineered YouTube Music / InnerTube API client, stream player,
synchronized lyrics engine, queue manager, Google OAuth 2.0 authentication,
and local SQLite persistence.
"""

from .innertube_client import InnerTubeClient
from .player import AudioPlayer
from .lyrics_engine import LyricsEngine
from .queue_manager import QueueManager
from .auth import AuthManager
from .database import DatabaseManager

__all__ = [
    "InnerTubeClient",
    "AudioPlayer",
    "LyricsEngine",
    "QueueManager",
    "AuthManager",
    "DatabaseManager",
]
