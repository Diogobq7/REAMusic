"""
REA UI - Synchronized Lyrics View Component
Renders timestamped lyrics with line-by-line active highlighting,
buttery-smooth 60fps auto-scrolling viewport, anticipation lead-time offset,
and live interactive synchronization calibration controls.
"""

from typing import Any, Callable, Dict, List, Optional
import customtkinter as ctk
from ui import theme
from ui.icons import IconManager


class LyricsView(ctk.CTkFrame):
    # Default anticipation lead-time offset (seconds)
    # Compensates for hardware audio output buffering and human reading latency
    DEFAULT_SYNC_OFFSET: float = 0.35

    def __init__(
        self,
        master,
        on_seek: Callable[[float], None],
        on_close: Callable[[], None],
        **kwargs,
    ):
        super().__init__(
            master,
            fg_color="#0d1118",
            corner_radius=theme.RADIUS_LARGE,
            border_width=1,
            border_color=theme.BORDER_COLOR,
            **kwargs,
        )
        self.on_seek = on_seek
        self.on_close = on_close

        self.lyrics_data: List[Dict[str, Any]] = []
        self.is_synced: bool = False
        self.active_line_index: int = -1
        self.line_widgets: List[ctk.CTkLabel] = []

        # Synchronization calibration state
        self.sync_offset: float = self.DEFAULT_SYNC_OFFSET
        self._last_current_time: float = 0.0

        # Smooth scrolling animation state
        self._target_scroll_fraction: float = 0.0
        self._scroll_anim_job: Optional[str] = None

        self._build_ui()

    def _build_ui(self):
        # 1. Top Header Bar
        header = ctk.CTkFrame(self, fg_color="transparent", height=44)
        header.pack(fill="x", padx=16, pady=(12, 4))

        self.title_label = ctk.CTkLabel(
            header,
            text="Lyrics",
            font=(theme.FONT_FAMILY, 15, "bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        self.title_label.pack(side="left")

        self.source_badge = ctk.CTkLabel(
            header,
            text="",
            font=(theme.FONT_FAMILY, 10, "bold"),
            text_color=theme.ACCENT_COLOR,
            fg_color=theme.ACCENT_BG,
            corner_radius=10,
            padx=8,
            pady=2,
        )
        self.source_badge.pack(side="left", padx=12)

        # Crisp vector close button
        close_icon = IconManager.get("close", (14, 14), color="#888888")
        self.close_btn = ctk.CTkButton(
            header,
            text="",
            image=close_icon,
            fg_color="transparent",
            hover_color=theme.SURFACE_HOVER,
            width=30,
            height=30,
            corner_radius=15,
            command=self.on_close,
        )
        self.close_btn.pack(side="right")

        # 2. Interactive Real-Time Sync Offset Calibration Bar
        self.calib_bar = ctk.CTkFrame(self, fg_color="#121722", corner_radius=8, height=30)
        self.calib_bar.pack(fill="x", padx=14, pady=(0, 6))

        lbl_off = ctk.CTkLabel(
            self.calib_bar,
            text="Sync Calib:",
            font=(theme.FONT_FAMILY, 10, "bold"),
            text_color="#64748b",
        )
        lbl_off.pack(side="left", padx=(10, 4))

        self.btn_minus = ctk.CTkButton(
            self.calib_bar,
            text="−0.1s",
            font=(theme.FONT_FAMILY, 10, "bold"),
            fg_color="#1a2232",
            hover_color="#253248",
            text_color="#cbd5e1",
            width=38,
            height=22,
            corner_radius=5,
            command=lambda: self.adjust_offset(-0.1),
        )
        self.btn_minus.pack(side="left", padx=2)

        self.offset_badge = ctk.CTkLabel(
            self.calib_bar,
            text=f"+{self.DEFAULT_SYNC_OFFSET:.2f}s",
            font=(theme.FONT_FAMILY, 11, "bold"),
            text_color=theme.ACCENT_COLOR,
            width=50,
        )
        self.offset_badge.pack(side="left", padx=2)

        self.btn_plus = ctk.CTkButton(
            self.calib_bar,
            text="+0.1s",
            font=(theme.FONT_FAMILY, 10, "bold"),
            fg_color="#1a2232",
            hover_color="#253248",
            text_color="#cbd5e1",
            width=38,
            height=22,
            corner_radius=5,
            command=lambda: self.adjust_offset(0.1),
        )
        self.btn_plus.pack(side="left", padx=2)

        self.btn_reset = ctk.CTkButton(
            self.calib_bar,
            text="Reset",
            font=(theme.FONT_FAMILY, 10),
            fg_color="transparent",
            hover_color="#1a2232",
            text_color="#64748b",
            width=40,
            height=22,
            corner_radius=5,
            command=self.reset_offset,
        )
        self.btn_reset.pack(side="right", padx=(0, 8))

        # 3. Scrollable Lyrics Container
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color="#1a2232",
            scrollbar_button_hover_color="#253248",
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # Initial Placeholder
        self._show_placeholder("No track currently playing.")

    def adjust_offset(self, delta: float):
        """Adjusts anticipation offset in real-time and refreshes highlighting immediately."""
        self.sync_offset = round(self.sync_offset + delta, 2)
        sign = "+" if self.sync_offset >= 0 else ""
        self.offset_badge.configure(text=f"{sign}{self.sync_offset:.2f}s")
        if self._last_current_time > 0:
            self.sync_time(self._last_current_time)

    def reset_offset(self):
        """Resets anticipation offset to default."""
        self.sync_offset = self.DEFAULT_SYNC_OFFSET
        self.offset_badge.configure(text=f"+{self.DEFAULT_SYNC_OFFSET:.2f}s")
        if self._last_current_time > 0:
            self.sync_time(self._last_current_time)

    def _show_placeholder(self, message: str):
        self._clear_lines()
        placeholder = ctk.CTkLabel(
            self.scroll_frame,
            text=message,
            font=(theme.FONT_FAMILY, 13),
            text_color=theme.TEXT_MUTED,
        )
        placeholder.pack(expand=True, pady=60)

    def _clear_lines(self):
        if self._scroll_anim_job:
            self.after_cancel(self._scroll_anim_job)
            self._scroll_anim_job = None

        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.line_widgets.clear()
        self.lyrics_data.clear()
        self.active_line_index = -1

    def set_loading(self, track_title: str):
        self._clear_lines()
        display_title = track_title if len(track_title) <= 26 else track_title[:24] + "..."
        self.title_label.configure(text=f"Lyrics • {display_title}")
        self.source_badge.configure(text="Searching...", text_color=theme.TEXT_MUTED, fg_color="#1a1a1a")
        self._show_placeholder("Retrieving synchronized lyrics...")

    def set_lyrics(self, lyrics_result: Dict[str, Any], track_title: str = ""):
        """Populates the lyrics container with parsed line items."""
        self._clear_lines()

        if track_title:
            display_title = track_title if len(track_title) <= 26 else track_title[:24] + "..."
            self.title_label.configure(text=f"Lyrics • {display_title}")

        if not lyrics_result.get("success") or not lyrics_result.get("lines"):
            self.source_badge.configure(text="Unavailable", text_color="#e67e22", fg_color="#2b2210")
            self._show_placeholder("Lyrics not available for this track.")
            return

        self.lyrics_data = lyrics_result["lines"]
        self.is_synced = lyrics_result.get("is_synced", False)
        source = lyrics_result.get("source", "LRC")

        # Update source badge
        badge_color = theme.ACCENT_COLOR if self.is_synced else theme.TEXT_SECONDARY
        badge_bg = theme.ACCENT_BG if self.is_synced else "#222222"
        self.source_badge.configure(text=source, text_color=badge_color, fg_color=badge_bg)

        # Build lyric line items
        for i, item in enumerate(self.lyrics_data):
            text = item.get("text", "").strip()
            if not text:
                text = "♪"

            lbl = ctk.CTkLabel(
                self.scroll_frame,
                text=text,
                font=(theme.FONT_FAMILY, 14),
                text_color="#555555" if self.is_synced else theme.TEXT_PRIMARY,
                anchor="w",
                justify="left",
                wraplength=340,
                cursor="hand2" if self.is_synced else "arrow",
            )
            lbl.pack(fill="x", padx=10, pady=6)

            if self.is_synced and item.get("time") is not None:
                seek_time = item["time"]
                lbl.bind("<Button-1>", lambda e, st=seek_time: self.on_seek(st))
                # Hover preview
                lbl.bind("<Enter>", lambda e, w=lbl, idx=i: self._on_line_hover(w, idx))
                lbl.bind("<Leave>", lambda e, w=lbl, idx=i: self._on_line_unhover(w, idx))

            self.line_widgets.append(lbl)

    def _on_line_hover(self, widget: ctk.CTkLabel, idx: int):
        if idx != self.active_line_index:
            widget.configure(text_color="#888888")

    def _on_line_unhover(self, widget: ctk.CTkLabel, idx: int):
        if idx != self.active_line_index:
            color = "#808080" if (idx < self.active_line_index) else "#555555"
            widget.configure(text_color=color)

    def sync_time(self, current_time: float):
        """
        Calculates the active lyric line according to player position + anticipation offset
        and applies smooth highlighting and 60fps eased scrolling.
        """
        if not self.is_synced or not self.lyrics_data:
            return

        self._last_current_time = current_time
        effective_time = max(0.0, current_time + self.sync_offset)

        # Find the active line (last line where line["time"] <= effective_time)
        new_active = -1
        for i, item in enumerate(self.lyrics_data):
            t = item.get("time")
            if t is not None and t <= effective_time:
                new_active = i
            elif t is not None and t > effective_time:
                break

        if new_active == self.active_line_index:
            return

        old_active = self.active_line_index
        self.active_line_index = new_active

        # Restore previous active line
        if 0 <= old_active < len(self.line_widgets):
            self.line_widgets[old_active].configure(
                text_color="#64748b",
                font=(theme.FONT_FAMILY, 14),
            )

        # Highlight new active line
        if 0 <= new_active < len(self.line_widgets):
            self.line_widgets[new_active].configure(
                text_color="#ffffff",
                font=(theme.FONT_FAMILY, 16, "bold"),
            )

            # Trigger smooth natural 60fps auto-scroll to center the active line
            total = len(self.line_widgets)
            if total > 0:
                target_fraction = max(0.0, min(1.0, (new_active - 1.5) / float(max(1, total - 1))))
                self._smooth_scroll_to(target_fraction)

    def _smooth_scroll_to(self, target_fraction: float):
        """Initiates an eased scrolling animation toward target_fraction."""
        self._target_scroll_fraction = target_fraction
        if self._scroll_anim_job is None:
            self._animate_scroll_step()

    def _animate_scroll_step(self):
        """Performs a single step of the smooth ease-out scrolling animation."""
        try:
            canvas = self.scroll_frame._parent_canvas
            current = canvas.yview()[0]
            diff = self._target_scroll_fraction - current

            # Stop when within threshold
            if abs(diff) < 0.001:
                canvas.yview_moveto(self._target_scroll_fraction)
                self._scroll_anim_job = None
                return

            # Smooth ease-out lerp (0.16 damping gives natural deceleration)
            new_val = current + (diff * 0.16)
            canvas.yview_moveto(new_val)
            self._scroll_anim_job = self.after(16, self._animate_scroll_step)  # ~60 FPS
        except Exception:
            self._scroll_anim_job = None
