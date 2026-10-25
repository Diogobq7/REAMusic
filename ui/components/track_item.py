"""
REA UI - Spotify-Style Track Item Row Component
Displays track number, artwork, metadata (Title, Artist, Album, Duration)
with vector play indicators and smooth hover/active states.
"""

from typing import Any, Callable, Dict, Optional
import customtkinter as ctk
from ui import theme
from ui.icons import IconManager
from ui.image_cache import ImageCache


class TrackItem(ctk.CTkFrame):
    def __init__(
        self,
        master,
        track: Dict[str, Any],
        on_select: Callable[[Dict[str, Any]], None],
        index: int = 1,
        **kwargs,
    ):
        super().__init__(
            master,
            fg_color="transparent",
            corner_radius=theme.RADIUS_SMALL,
            height=54,
            **kwargs,
        )
        self.track = track
        self.on_select = on_select
        self.index = index
        self._is_active = False

        self.grid_columnconfigure(2, weight=3)  # Title & Artist
        self.grid_columnconfigure(3, weight=2)  # Album
        self.grid_columnconfigure(4, weight=0)  # Duration

        # 0. Track Number / Play Indicator (Col 0)
        self.index_label = ctk.CTkLabel(
            self,
            text=str(index),
            font=(theme.FONT_FAMILY, 12),
            text_color="#6e6e6e",
            width=32,
            anchor="center",
        )
        self.index_label.grid(row=0, column=0, padx=(8, 4), pady=6)

        # 1. Artwork Thumbnail (Col 1)
        self.thumb_label = ctk.CTkLabel(
            self,
            text="",
            image=ImageCache.get_placeholder((40, 40)),
            width=40,
            height=40,
        )
        self.thumb_label.grid(row=0, column=1, padx=(4, 12), pady=6)

        thumb_url = track.get("thumbnail_url") or track.get("raw_thumbnail_url")
        if thumb_url:
            ImageCache.load_async(
                thumb_url,
                size=(40, 40),
                callback=self._update_thumb,
            )

        # 2. Title & Artist (Col 2)
        text_frame = ctk.CTkFrame(self, fg_color="transparent")
        text_frame.grid(row=0, column=2, sticky="w", padx=(0, 12), pady=6)

        title_text = track.get("title", "Untitled")
        if len(title_text) > 42:
            title_text = title_text[:39] + "..."
        self.title_label = ctk.CTkLabel(
            text_frame,
            text=title_text,
            font=(theme.FONT_FAMILY, 13, "bold"),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        self.title_label.pack(anchor="w")

        artist_text = track.get("artist") or ", ".join(track.get("artists", [])) or "Unknown Artist"
        if len(artist_text) > 46:
            artist_text = artist_text[:43] + "..."
        self.artist_label = ctk.CTkLabel(
            text_frame,
            text=artist_text,
            font=(theme.FONT_FAMILY, 11),
            text_color=theme.TEXT_SECONDARY,
            anchor="w",
        )
        self.artist_label.pack(anchor="w")

        # 3. Album Column (Col 3)
        album_text = track.get("album", "")
        if len(album_text) > 36:
            album_text = album_text[:33] + "..."
        self.album_label = ctk.CTkLabel(
            self,
            text=album_text or "—",
            font=(theme.FONT_FAMILY, 12),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        self.album_label.grid(row=0, column=3, sticky="w", padx=(0, 12), pady=6)

        # 4. Duration (Col 4)
        duration_text = track.get("duration", "")
        self.dur_label = ctk.CTkLabel(
            self,
            text=duration_text,
            font=(theme.FONT_FAMILY, 12),
            text_color=theme.TEXT_SECONDARY,
            width=50,
            anchor="e",
        )
        self.dur_label.grid(row=0, column=4, padx=(8, 14), pady=6)

        # Event bindings
        all_widgets = [
            self,
            self.index_label,
            self.thumb_label,
            text_frame,
            self.title_label,
            self.artist_label,
            self.album_label,
            self.dur_label,
        ]
        for w in all_widgets:
            w.bind("<Enter>", lambda e: self._on_enter())
            w.bind("<Leave>", lambda e: self._on_leave())
            w.bind("<Button-1>", lambda e: self.on_select(self.track))

    def _update_thumb(self, ctk_img):
        try:
            self.thumb_label.configure(image=ctk_img)
        except Exception:
            pass

    def _on_enter(self):
        if not self._is_active:
            self.configure(fg_color="#141c28")
            self.index_label.configure(
                text="",
                image=IconManager.get("play", (13, 13), color="#ffffff"),
            )

    def _on_leave(self):
        if not self._is_active:
            self.configure(fg_color="transparent")
            self.index_label.configure(
                text=str(self.index),
                image="",
                text_color="#64748b",
            )

    def set_active(self, active: bool):
        self._is_active = active
        if active:
            self.configure(fg_color="#182334")
            self.title_label.configure(text_color=theme.ACCENT_COLOR)
            self.index_label.configure(
                text="",
                image=IconManager.get("volume_high", (14, 14), color=theme.ACCENT_COLOR),
            )
        else:
            self.configure(fg_color="transparent")
            self.title_label.configure(text_color=theme.TEXT_PRIMARY)
            self.index_label.configure(
                text=str(self.index),
                image="",
                text_color="#64748b",
            )
