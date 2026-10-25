"""
REA UI - Spotify-Style Persistent Bottom Player Bar Component
Provides continuous playback controls with vector icons, fluid timeline scrubbing,
dynamic volume adjustment, lyrics drawer toggle, and live artwork/metadata display.
"""

from typing import Any, Callable, Dict, Optional
import customtkinter as ctk
from ui import theme
from ui.icons import IconManager
from ui.image_cache import ImageCache


class BottomPlayer(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_toggle_pause: Callable[[], None],
        on_prev: Callable[[], None],
        on_next: Callable[[], None],
        on_seek: Callable[[float], None],
        on_volume: Callable[[int], None],
        on_toggle_lyrics: Optional[Callable[[], None]] = None,
        on_toggle_favorite: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        super().__init__(
            master,
            fg_color="#121212",
            corner_radius=0,
            border_width=1,
            border_color="#202020",
            height=88,
            **kwargs,
        )
        self.on_toggle_pause = on_toggle_pause
        self.on_prev = on_prev
        self.on_next = on_next
        self.on_seek = on_seek
        self.on_volume = on_volume
        self.on_toggle_lyrics = on_toggle_lyrics
        self.on_toggle_favorite = on_toggle_favorite

        self._is_seeking = False
        self._total_duration_sec = 0.0
        self._lyrics_active = False
        self._is_favorite = False
        self._is_playing = False
        self._last_volume = 80

        self.grid_columnconfigure(0, weight=1, minsize=260)
        self.grid_columnconfigure(1, weight=2, minsize=400)
        self.grid_columnconfigure(2, weight=1, minsize=260)

        # -------------------------------------------------------------
        # 1. Left Section: Now Playing Artwork, Details & Heart Icon
        # -------------------------------------------------------------
        left_frame = ctk.CTkFrame(self, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="w", padx=16, pady=8)

        self.cover_label = ctk.CTkLabel(
            left_frame,
            text="",
            image=ImageCache.get_placeholder((52, 52)),
            width=52,
            height=52,
        )
        self.cover_label.pack(side="left", padx=(0, 12))

        meta_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        meta_frame.pack(side="left", fill="y", expand=True)

        self.title_label = ctk.CTkLabel(
            meta_frame,
            text="No track playing",
            font=(theme.FONT_FAMILY, 13, "bold"),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        self.title_label.pack(anchor="w")

        self.artist_label = ctk.CTkLabel(
            meta_frame,
            text="Select a track to play",
            font=(theme.FONT_FAMILY, 11),
            text_color=theme.TEXT_SECONDARY,
            anchor="w",
        )
        self.artist_label.pack(anchor="w")

        # Heart / Favorite Button with vector icon
        self.fav_btn = ctk.CTkButton(
            left_frame,
            text="",
            image=IconManager.get("heart_outline", (18, 18), color="#888888"),
            fg_color="transparent",
            hover_color="#222222",
            width=32,
            height=32,
            corner_radius=16,
            command=self._handle_fav_click,
        )
        self.fav_btn.pack(side="left", padx=(10, 0))

        # -------------------------------------------------------------
        # 2. Center Section: Transport Controls & Timeline
        # -------------------------------------------------------------
        center_frame = ctk.CTkFrame(self, fg_color="transparent")
        center_frame.grid(row=0, column=1, sticky="nsew", pady=6)

        # Transport Buttons (Row 1)
        btn_frame = ctk.CTkFrame(center_frame, fg_color="transparent")
        btn_frame.pack(pady=(2, 2))

        self.prev_btn = ctk.CTkButton(
            btn_frame,
            text="",
            image=IconManager.get("prev", (16, 16), color="#94a3b8"),
            fg_color="transparent",
            hover_color="#1c2230",
            width=36,
            height=36,
            corner_radius=18,
            command=self.on_prev,
        )
        self.prev_btn.pack(side="left", padx=8)

        self.play_btn = ctk.CTkButton(
            btn_frame,
            text="",
            image=IconManager.get("play", (18, 18), color="#ffffff"),
            fg_color=theme.ACCENT_COLOR,
            hover_color=theme.ACCENT_HOVER,
            width=40,
            height=40,
            corner_radius=20,
            command=self.on_toggle_pause,
        )
        self.play_btn.pack(side="left", padx=8)

        self.next_btn = ctk.CTkButton(
            btn_frame,
            text="",
            image=IconManager.get("next", (16, 16), color="#94a3b8"),
            fg_color="transparent",
            hover_color="#1c2230",
            width=36,
            height=36,
            corner_radius=18,
            command=self.on_next,
        )
        self.next_btn.pack(side="left", padx=8)

        # Timeline Slider (Row 2)
        timeline_frame = ctk.CTkFrame(center_frame, fg_color="transparent")
        timeline_frame.pack(fill="x", padx=16, pady=(0, 2))

        self.pos_label = ctk.CTkLabel(
            timeline_frame,
            text="0:00",
            font=(theme.FONT_FAMILY, 11),
            text_color="#888888",
            width=36,
            anchor="e",
        )
        self.pos_label.pack(side="left", padx=(0, 8))

        self.slider = ctk.CTkSlider(
            timeline_frame,
            from_=0.0,
            to=100.0,
            number_of_steps=1000,
            height=14,
            progress_color=theme.ACCENT_COLOR,
            button_color="#ffffff",
            button_hover_color=theme.ACCENT_HOVER,
            fg_color="#1e293b",
            button_length=10,
            command=self._on_slider_change,
        )
        self.slider.pack(side="left", fill="x", expand=True)
        self.slider.set(0.0)
        self.slider.bind("<ButtonPress-1>", lambda e: self._on_slider_press())
        self.slider.bind("<ButtonRelease-1>", lambda e: self._on_slider_release())

        self.dur_label = ctk.CTkLabel(
            timeline_frame,
            text="0:00",
            font=(theme.FONT_FAMILY, 11),
            text_color="#888888",
            width=36,
            anchor="w",
        )
        self.dur_label.pack(side="left", padx=(8, 0))

        # -------------------------------------------------------------
        # 3. Right Section: Lyrics Toggle & Dynamic Volume
        # -------------------------------------------------------------
        right_frame = ctk.CTkFrame(self, fg_color="transparent")
        right_frame.grid(row=0, column=2, sticky="e", padx=20, pady=8)

        # Lyrics Toggle Button with vector mic/lyrics icon
        self.lyrics_btn = ctk.CTkButton(
            right_frame,
            text="",
            image=IconManager.get("lyrics", (16, 16), color="#94a3b8"),
            fg_color="transparent",
            hover_color="#1c2230",
            width=34,
            height=34,
            corner_radius=17,
            command=self._handle_lyrics_toggle,
        )
        self.lyrics_btn.pack(side="left", padx=(0, 14))

        # Clickable Volume Mute/Unmute Icon Button
        self.vol_btn = ctk.CTkButton(
            right_frame,
            text="",
            image=IconManager.get("volume_high", (18, 18), color="#94a3b8"),
            fg_color="transparent",
            hover_color="#1c2230",
            width=28,
            height=28,
            corner_radius=14,
            command=self._toggle_mute,
        )
        self.vol_btn.pack(side="left", padx=(0, 6))

        self.vol_slider = ctk.CTkSlider(
            right_frame,
            from_=0,
            to=100,
            number_of_steps=100,
            width=88,
            height=14,
            progress_color=theme.ACCENT_COLOR,
            button_color="#ffffff",
            button_hover_color=theme.ACCENT_HOVER,
            fg_color="#1e293b",
            button_length=8,
            command=self._on_vol_change,
        )
        self.vol_slider.set(80)
        self.vol_slider.pack(side="left", padx=(0, 4))

    # --- Interaction Handlers ---

    def _handle_fav_click(self):
        if self.on_toggle_favorite:
            self.on_toggle_favorite()

    def set_favorite_state(self, is_fav: bool):
        self._is_favorite = is_fav
        if is_fav:
            self.fav_btn.configure(image=IconManager.get("heart_filled", (18, 18), color="#ff4757"))
        else:
            self.fav_btn.configure(image=IconManager.get("heart_outline", (18, 18), color="#888888"))

    def _handle_lyrics_toggle(self):
        self._lyrics_active = not self._lyrics_active
        self._update_lyrics_btn_style()
        if self.on_toggle_lyrics:
            self.on_toggle_lyrics()

    def set_lyrics_button_active(self, is_active: bool):
        self._lyrics_active = is_active
        self._update_lyrics_btn_style()

    def _update_lyrics_btn_style(self):
        if self._lyrics_active:
            self.lyrics_btn.configure(
                fg_color=theme.ACCENT_COLOR,
                hover_color=theme.ACCENT_HOVER,
                image=IconManager.get("lyrics", (16, 16), color="#ffffff"),
            )
        else:
            self.lyrics_btn.configure(
                fg_color="transparent",
                hover_color="#1c2230",
                image=IconManager.get("lyrics", (16, 16), color="#94a3b8"),
            )

    def _on_slider_press(self):
        self._is_seeking = True

    def _on_slider_release(self):
        self._is_seeking = False
        target_sec = self.slider.get()
        self.on_seek(target_sec)

    def _on_slider_change(self, val: float):
        if self._is_seeking:
            self.pos_label.configure(text=self._format_time(val))

    def _on_vol_change(self, val: float):
        vol = int(val)
        self._update_vol_icon(vol)
        self.on_volume(vol)

    def _toggle_mute(self):
        current = int(self.vol_slider.get())
        if current > 0:
            self._last_volume = current
            self.vol_slider.set(0)
            self._update_vol_icon(0)
            self.on_volume(0)
        else:
            target = self._last_volume if self._last_volume > 0 else 70
            self.vol_slider.set(target)
            self._update_vol_icon(target)
            self.on_volume(target)

    def _update_vol_icon(self, vol: int):
        if vol == 0:
            self.vol_btn.configure(image=IconManager.get("volume_mute", (18, 18), color="#888888"))
        elif vol < 30:
            self.vol_btn.configure(image=IconManager.get("volume_low", (18, 18), color="#b3b3b3"))
        elif vol < 70:
            self.vol_btn.configure(image=IconManager.get("volume_medium", (18, 18), color="#b3b3b3"))
        else:
            self.vol_btn.configure(image=IconManager.get("volume_high", (18, 18), color="#b3b3b3"))

    @staticmethod
    def _format_time(seconds: float) -> str:
        seconds = max(0, int(seconds))
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}:{secs:02d}"

    # --- State Updaters ---

    def set_track_info(self, track: Dict[str, Any], duration_sec: float = 0.0, is_fav: bool = False):
        """Updates now playing metadata, favorite icon and cover."""
        title = track.get("title", "Untitled")
        if len(title) > 34:
            title = title[:31] + "..."
        self.title_label.configure(text=title)

        artist = track.get("artist") or ", ".join(track.get("artists", [])) or "Unknown Artist"
        if len(artist) > 38:
            artist = artist[:35] + "..."
        self.artist_label.configure(text=artist)

        self._total_duration_sec = duration_sec
        self.dur_label.configure(text=self._format_time(duration_sec))
        self.slider.configure(to=max(1.0, duration_sec))
        self.slider.set(0.0)
        self.pos_label.configure(text="0:00")
        self.set_favorite_state(is_fav)

        thumb_url = track.get("thumbnail_url") or track.get("raw_thumbnail_url")
        if thumb_url:
            ImageCache.load_async(
                thumb_url,
                size=(52, 52),
                callback=lambda img: self.cover_label.configure(image=img),
            )
        else:
            self.cover_label.configure(image=ImageCache.get_placeholder((52, 52)))

    def update_progress(self, position_sec: float, duration_sec: float):
        """Synchronizes timeline progress with the audio engine in real time."""
        if not self._is_seeking:
            if duration_sec > 0 and duration_sec != self._total_duration_sec:
                self._total_duration_sec = duration_sec
                self.slider.configure(to=duration_sec)
                self.dur_label.configure(text=self._format_time(duration_sec))

            self.slider.set(position_sec)
            self.pos_label.configure(text=self._format_time(position_sec))

    def set_playing_state(self, is_playing: bool):
        """Toggles the transport Play/Pause button vector icon."""
        self._is_playing = is_playing
        icon_name = "pause" if is_playing else "play"
        self.play_btn.configure(
            image=IconManager.get(icon_name, (18, 18), color="#ffffff"),
        )

    def set_status_pill(self, text: str, is_active: bool = True):
        """Technical status pills removed for clean consumer interface."""
        pass
