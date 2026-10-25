"""
REA Core - Lightweight Audio Player Interface
Controls mpv via subprocess and high-precision named pipe JSON IPC for instant,
non-blocking audio streaming directly from CDN URLs.
Features real-time timeline synchronization (50ms interval), instant seeking,
volume control, and natural track completion callbacks.
Includes graceful fallback simulation if mpv is not detected.
"""

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from typing import Any, Callable, Dict, Optional


class AudioPlayer:
    """
    Lightweight audio playback controller using mpv with JSON IPC.
    Streams audio directly into memory without disk caching.
    """

    COMMON_MPV_PATHS = [
        "mpv",
        "mpv.exe",
        os.path.expanduser(r"~\scoop\shims\mpv.exe"),
        r"C:\Program Files\mpv\mpv.exe",
        r"C:\Program Files (x86)\mpv\mpv.exe",
        r"C:\ProgramData\chocolatey\bin\mpv.exe",
        os.path.join(os.path.dirname(__file__), "mpv.exe"),
    ]

    def __init__(self, custom_mpv_path: Optional[str] = None):
        self.mpv_path = self._locate_mpv(custom_mpv_path)
        self.process: Optional[subprocess.Popen] = None
        self.pipe_name: Optional[str] = None
        self._pipe_file: Optional[Any] = None

        self.current_title: Optional[str] = None
        self.current_artist: Optional[str] = None
        self.current_url: Optional[str] = None
        self.current_thumbnail_url: Optional[str] = None
        self.total_duration: float = 0.0
        self.current_position: float = 0.0

        self._is_paused: bool = False
        self._is_active: bool = False
        self._manual_stop: bool = False
        self._session_id: int = 0
        self._current_volume: int = 80

        self._lock = threading.Lock()
        self._ipc_lock = threading.Lock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._sim_thread: Optional[threading.Thread] = None

        self.on_progress: Optional[Callable[[float, float], None]] = None
        self.on_state_change: Optional[Callable[[bool], None]] = None
        self.on_track_end: Optional[Callable[[], None]] = None

    @classmethod
    def _locate_mpv(cls, custom_path: Optional[str] = None) -> Optional[str]:
        """Checks if mpv is available on PATH, PyInstaller bundle, or local project directory."""
        if custom_path and os.path.exists(custom_path):
            return custom_path

        # 1. Check PyInstaller extracted bundle path
        if hasattr(sys, "_MEIPASS"):
            bundle_mpv = os.path.join(sys._MEIPASS, "mpv.exe")
            if os.path.exists(bundle_mpv):
                return bundle_mpv

        # 2. Check adjacent to current running executable / script
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        adjacent_mpv = os.path.join(exe_dir, "mpv.exe")
        if os.path.exists(adjacent_mpv):
            return adjacent_mpv

        # 3. Check current working directory
        cwd_mpv = os.path.join(os.getcwd(), "mpv.exe")
        if os.path.exists(cwd_mpv):
            return cwd_mpv

        # 4. Check project root relative to this file
        core_dir = os.path.dirname(os.path.abspath(__file__))
        root_mpv = os.path.join(core_dir, "..", "mpv.exe")
        if os.path.exists(root_mpv):
            return os.path.abspath(root_mpv)

        # 5. Check known system paths and system PATH
        for candidate in cls.COMMON_MPV_PATHS:
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
            if os.path.isabs(candidate) and os.path.exists(candidate):
                return candidate
        return None

    def is_mpv_available(self) -> bool:
        """Returns True if mpv executable was detected on the system."""
        return self.mpv_path is not None

    def _open_ipc_pipe(self, timeout: float = 3.0, session_id: int = 0) -> bool:
        """Connects to the mpv named pipe on Windows."""
        if not self.pipe_name:
            return False
        start_time = time.time()
        while time.time() - start_time < timeout:
            with self._lock:
                if not self._is_active or self._session_id != session_id:
                    return False
                proc = self.process
            if proc and proc.poll() is not None:
                return False
            try:
                pipe = open(self.pipe_name, "r+b", buffering=0)
                with self._ipc_lock:
                    with self._lock:
                        if self._session_id != session_id:
                            try:
                                pipe.close()
                            except Exception:
                                pass
                            return False
                    self._pipe_file = pipe
                return True
            except (OSError, FileNotFoundError):
                time.sleep(0.05)
        return False

    def _send_ipc(self, command: list) -> Optional[Any]:
        """Sends a JSON IPC command to mpv and returns response data."""
        with self._ipc_lock:
            if not self._pipe_file:
                return None
            try:
                msg = json.dumps({"command": command}).encode("utf-8") + b"\n"
                self._pipe_file.write(msg)
                resp_line = self._pipe_file.readline()
                if resp_line:
                    data = json.loads(resp_line.decode("utf-8", errors="replace"))
                    return data.get("data")
            except Exception:
                pass
        return None

    def play(
        self,
        stream_url: str,
        title: str = "Audio Stream",
        artist: str = "",
        duration_sec: float = 0.0,
        thumbnail_url: str = "",
    ) -> bool:
        """
        Starts streaming audio immediately from the direct CDN URL.
        Buffers directly in memory without writing to disk.
        """
        self.stop(manual=True)

        clean_title = (title or "Audio Stream").replace("\r", " ").replace("\n", " ").strip()

        with self._lock:
            self._session_id += 1
            session_id = self._session_id
            self.current_title = clean_title
            self.current_artist = artist
            self.current_url = stream_url
            self.current_thumbnail_url = thumbnail_url
            self.total_duration = duration_sec
            self.current_position = 0.0
            self._is_paused = False
            self._is_active = True
            self._manual_stop = False

        if not self.is_mpv_available():
            self._start_simulation(session_id)
            if self.on_state_change:
                self.on_state_change(True)
            return True

        # Generate unique Windows named pipe
        self.pipe_name = rf"\\.\pipe\rea_mpv_{uuid.uuid4().hex[:8]}"

        cmd = [
            self.mpv_path,
            "--no-video",
            "--really-quiet",
            "--force-window=no",
            "--idle=no",
            "--ytdl=no",
            "--demuxer-readahead-secs=2",
            "--demuxer-max-bytes=2048KiB",
            "--demuxer-lavf-buffersize=32768",
            "--cache-pause=no",
            "--audio-buffer=0.1",
            "--network-timeout=8",
            f"--volume={self._current_volume}",
            f"--input-ipc-server={self.pipe_name}",
            f"--title={clean_title}",
            stream_url,
        ]

        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
        except Exception as e:
            self.stop(manual=True)
            raise RuntimeError(f"Failed to launch mpv: {e}") from e

        # Start background monitor thread for high-precision progress & end-of-track detection
        self._monitor_thread = threading.Thread(
            target=self._monitor_playback_loop,
            args=(session_id,),
            daemon=True,
        )
        self._monitor_thread.start()

        if self.on_state_change:
            self.on_state_change(True)
        return True

    def _monitor_playback_loop(self, session_id: int):
        """
        Monitors playback progress via named pipe IPC at ~40ms intervals.
        Emits on_progress continuously to keep lyrics and progress bars perfectly synchronized.
        Guarded by session_id to prevent ghost threads from firing on_track_end during track transitions.
        """
        connected = self._open_ipc_pipe(timeout=4.0, session_id=session_id)
        with self._lock:
            if self._session_id != session_id:
                return

        playback_started = False
        last_reported_pos = 0.0
        last_sync_time = time.time()

        while True:
            with self._lock:
                if self._session_id != session_id or not self._is_active:
                    break
                proc = self.process

            if proc and proc.poll() is not None:
                # Process exited
                break

            if connected and not self._is_paused:
                # Primary query: time-pos; fallback: audio-pts
                pos = self._send_ipc(["get_property", "time-pos"])
                if pos is None:
                    pos = self._send_ipc(["get_property", "audio-pts"])

                if isinstance(pos, (int, float)) and pos >= 0:
                    playback_started = True
                    last_reported_pos = float(pos)
                    last_sync_time = time.time()
                    with self._lock:
                        if self._session_id == session_id:
                            self.current_position = float(pos)

                    # Query duration if missing or 0
                    if self.total_duration <= 0:
                        dur = self._send_ipc(["get_property", "duration"])
                        if isinstance(dur, (int, float)) and dur > 0:
                            with self._lock:
                                if self._session_id == session_id:
                                    self.total_duration = float(dur)
                elif playback_started:
                    # High-precision interpolation between IPC polling responses
                    elapsed = time.time() - last_sync_time
                    with self._lock:
                        if self._session_id == session_id:
                            if self.total_duration > 0:
                                self.current_position = min(self.total_duration, last_reported_pos + elapsed)
                            else:
                                self.current_position = last_reported_pos + elapsed
                else:
                    # Still buffering before audio starts; hold at 0.0 to prevent lyrics jump
                    with self._lock:
                        if self._session_id == session_id:
                            self.current_position = 0.0
            elif not self._is_paused and playback_started:
                elapsed = time.time() - last_sync_time
                with self._lock:
                    if self._session_id == session_id:
                        self.current_position = last_reported_pos + elapsed

            if self.on_progress and self._is_active and self._session_id == session_id:
                self.on_progress(self.current_position, self.total_duration)

            time.sleep(0.04)  # ~25 updates per second for fluid 60fps timeline and lyrics updates

        # Thread completion check
        with self._lock:
            if self._session_id != session_id:
                # Obsolete session thread: exit silently without modifying player state!
                return

            natural_finish = False
            proc = self.process
            is_exit_clean = (proc is not None and proc.poll() == 0)

            # Robust natural track completion validation:
            # 1. Playback must have actually started (not a launch error or crash)
            # 2. Must not have been interrupted by manual stop
            # 3. Position must be near duration OR process completed cleanly with substantial progress
            if not self._manual_stop and self._is_active and playback_started:
                min_threshold = min(3.0, self.total_duration * 0.8) if self.total_duration > 0 else 3.0
                if self.total_duration > 0 and self.current_position >= (self.total_duration - 2.5):
                    natural_finish = True
                elif is_exit_clean and self.current_position >= min_threshold:
                    natural_finish = True

            self._is_active = False

        self._close_ipc()

        if self.on_state_change:
            self.on_state_change(False)

        if natural_finish and self.on_track_end:
            self.on_track_end()

    def _close_ipc(self):
        """Closes the named pipe handle safely."""
        with self._ipc_lock:
            if self._pipe_file:
                try:
                    self._pipe_file.close()
                except Exception:
                    pass
                self._pipe_file = None

    def _start_simulation(self, session_id: int):
        """Advances timeline simulation when mpv is unavailable."""
        def sim_loop():
            natural_finish = False
            wall_start = time.time()
            base_pos = self.current_position
            while True:
                time.sleep(0.08)
                with self._lock:
                    if self._session_id != session_id or not self._is_active:
                        break
                    if not self._is_paused:
                        self.current_position = base_pos + (time.time() - wall_start)
                        if self.total_duration > 0 and self.current_position >= self.total_duration:
                            self.current_position = self.total_duration
                            self._is_active = False
                            natural_finish = not self._manual_stop
                            break
                    else:
                        wall_start = time.time()
                        base_pos = self.current_position

                if self.on_progress and self._session_id == session_id:
                    self.on_progress(self.current_position, self.total_duration)

            with self._lock:
                if self._session_id != session_id:
                    return

            if self.on_state_change:
                self.on_state_change(False)

            if natural_finish and self.on_track_end:
                self.on_track_end()

        self._sim_thread = threading.Thread(target=sim_loop, daemon=True)
        self._sim_thread.start()

    def stop(self, manual: bool = True) -> None:
        """Terminates active playback immediately."""
        with self._lock:
            self._session_id += 1
            self._manual_stop = manual
            self._is_active = False
            self.current_position = 0.0
            self._is_paused = False

            proc = self.process
            self.process = None

        if proc:
            try:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=0.6)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        self._close_ipc()

        if self.on_state_change:
            self.on_state_change(False)

    def toggle_pause(self) -> bool:
        """Toggles playback pause / resume."""
        with self._lock:
            if not self._is_active:
                return False
            self._is_paused = not self._is_paused
            new_pause_state = self._is_paused

        self._send_ipc(["set_property", "pause", new_pause_state])

        if self.on_state_change:
            self.on_state_change(not new_pause_state)
        return True

    def seek(self, target_seconds: float) -> bool:
        """Seeks to absolute target position in seconds."""
        with self._lock:
            if not self._is_active:
                return False
            self.current_position = max(0.0, min(self.total_duration or 9999.0, target_seconds))
            pos = self.current_position

        self._send_ipc(["seek", pos, "absolute"])

        if self.on_progress:
            self.on_progress(pos, self.total_duration)
        return True

    def set_volume(self, volume: int) -> bool:
        """Adjusts volume level (0-100)."""
        volume = max(0, min(100, volume))
        self._current_volume = volume
        res = self._send_ipc(["set_property", "volume", volume])
        return res is not None

    def is_playing(self) -> bool:
        """Returns True if playback is currently active and not paused."""
        with self._lock:
            return self._is_active and not self._is_paused

    def get_state(self) -> Dict[str, Any]:
        """Returns current playback state."""
        with self._lock:
            return {
                "is_available": self.is_mpv_available(),
                "mpv_path": self.mpv_path,
                "is_active": self._is_active,
                "is_playing": self._is_active and not self._is_paused,
                "is_paused": self._is_paused,
                "title": self.current_title,
                "artist": self.current_artist,
                "url": self.current_url,
                "thumbnail_url": self.current_thumbnail_url,
                "position": self.current_position,
                "duration": self.total_duration,
                "volume": self._current_volume,
            }

    @staticmethod
    def verify_stream_url(stream_url: str) -> Dict[str, Any]:
        """Validates that a direct CDN audio stream URL is active and reachable."""
        req = urllib.request.Request(
            stream_url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Range": "bytes=0-1024",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                headers = dict(resp.headers)
                chunk = resp.read(32)
                magic_hex = chunk[:4].hex()

                is_webm = magic_hex == "1a45dfa3"
                is_mp4 = "ftyp" in chunk[:12].decode("latin-1", errors="replace")

                return {
                    "valid": status in (200, 206),
                    "http_status": status,
                    "content_type": headers.get("Content-Type", ""),
                    "content_range": headers.get("Content-Range", ""),
                    "magic_bytes_hex": magic_hex,
                    "container_detected": "WebM/Opus" if is_webm else ("MP4/AAC" if is_mp4 else "Unknown"),
                    "bytes_received": len(chunk),
                }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
            }
