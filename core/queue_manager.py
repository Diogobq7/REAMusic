"""
REA Core - Playback Queue Manager
Manages active playlist queues, sequential auto-advance, history, and navigation.
"""

from typing import Any, Callable, Dict, List, Optional


class QueueManager:
    """
    Manages track sequences, next/previous transitions, and auto-progression.
    """

    def __init__(self):
        self._queue: List[Dict[str, Any]] = []
        self._current_index: int = -1
        self.repeat_mode: str = "off"  # "off", "all", "one"
        self.on_queue_updated: Optional[Callable[[], None]] = None

    def set_queue(self, tracks: List[Dict[str, Any]], start_index: int = 0) -> Optional[Dict[str, Any]]:
        """Sets a new track collection and activates start_index."""
        self._queue = list(tracks)
        if 0 <= start_index < len(self._queue):
            self._current_index = start_index
        else:
            self._current_index = 0 if self._queue else -1

        if self.on_queue_updated:
            self.on_queue_updated()

        return self.get_current_track()

    def add_track(self, track: Dict[str, Any]) -> None:
        """Appends a single track to the end of the queue."""
        self._queue.append(track)
        if self._current_index == -1:
            self._current_index = 0
        if self.on_queue_updated:
            self.on_queue_updated()

    def get_current_track(self) -> Optional[Dict[str, Any]]:
        """Returns the currently active track or None if queue is empty."""
        if 0 <= self._current_index < len(self._queue):
            return self._queue[self._current_index]
        return None

    def get_current_index(self) -> int:
        return self._current_index

    def get_queue(self) -> List[Dict[str, Any]]:
        return list(self._queue)

    def has_next(self) -> bool:
        """Returns True if there is a valid subsequent track."""
        if not self._queue:
            return False
        if self.repeat_mode in ("all", "one"):
            return True
        return self._current_index + 1 < len(self._queue)

    def has_prev(self) -> bool:
        """Returns True if there is a preceding track."""
        if not self._queue:
            return False
        if self.repeat_mode == "all":
            return True
        return self._current_index > 0

    def next_track(self) -> Optional[Dict[str, Any]]:
        """Advances to the next track according to repeat mode."""
        if not self._queue:
            return None

        if self.repeat_mode == "one":
            return self.get_current_track()

        if self._current_index + 1 < len(self._queue):
            self._current_index += 1
            return self.get_current_track()
        elif self.repeat_mode == "all":
            self._current_index = 0
            return self.get_current_track()

        return None

    def prev_track(self) -> Optional[Dict[str, Any]]:
        """Returns to the previous track."""
        if not self._queue:
            return None

        if self._current_index > 0:
            self._current_index -= 1
            return self.get_current_track()
        elif self.repeat_mode == "all":
            self._current_index = len(self._queue) - 1
            return self.get_current_track()

        return self.get_current_track()

    def set_index(self, index: int) -> Optional[Dict[str, Any]]:
        """Jumps directly to a given index in the queue."""
        if 0 <= index < len(self._queue):
            self._current_index = index
            return self.get_current_track()
        return None

    def clear(self) -> None:
        """Empties the current queue."""
        self._queue.clear()
        self._current_index = -1
        if self.on_queue_updated:
            self.on_queue_updated()
