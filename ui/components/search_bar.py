"""
REA UI - Modern Search Bar Component
Sleek, pill-shaped search input inspired by Spotify and Apple Music Desktop.
Features vector search icon and responsive submit actions.
"""

from typing import Callable
import customtkinter as ctk
from ui import theme
from ui.icons import IconManager


class SearchBar(ctk.CTkFrame):
    def __init__(self, master, on_search: Callable[[str], None], **kwargs):
        super().__init__(
            master,
            fg_color="#131924",
            corner_radius=20,
            border_width=1,
            border_color="#1e293b",
            height=42,
            **kwargs,
        )
        self.on_search = on_search

        self.grid_columnconfigure(1, weight=1)

        # Vector Search icon on left
        search_icon = IconManager.get("search", (16, 16), color="#64748b")
        self.icon_label = ctk.CTkLabel(
            self,
            text="",
            image=search_icon,
            width=32,
        )
        self.icon_label.grid(row=0, column=0, padx=(12, 2), pady=2)

        # Text input field
        self.entry = ctk.CTkEntry(
            self,
            placeholder_text="What do you want to play? (Song, artist, or album)...",
            placeholder_text_color="#64748b",
            fg_color="transparent",
            border_width=0,
            text_color=theme.TEXT_PRIMARY,
            font=(theme.FONT_FAMILY, 13),
            height=38,
        )
        self.entry.grid(row=0, column=1, sticky="ew", padx=(2, 6), pady=2)
        self.entry.bind("<Return>", lambda event: self._trigger_search())
        self.entry.bind("<KeyRelease>", self._on_key)

        # Clear / Search action button
        self.action_btn = ctk.CTkButton(
            self,
            text="Search",
            font=(theme.FONT_FAMILY, 12, "bold"),
            fg_color=theme.ACCENT_COLOR,
            hover_color=theme.ACCENT_HOVER,
            text_color="#ffffff",
            corner_radius=16,
            width=72,
            height=28,
            command=self._trigger_search,
        )
        self.action_btn.grid(row=0, column=2, padx=(4, 8), pady=6)

    def _on_key(self, event=None):
        pass

    def _trigger_search(self):
        query = self.entry.get().strip()
        if query:
            self.on_search(query)

    def set_loading(self, is_loading: bool):
        if is_loading:
            self.action_btn.configure(text="...", state="disabled", fg_color="#333333", text_color="#888888")
        else:
            self.action_btn.configure(text="Search", state="normal", fg_color=theme.ACCENT_COLOR, text_color="#ffffff")
