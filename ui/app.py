"""
REA Music Desktop Application - Main Window & Controller
Professional Desktop layout inspired by Spotify Desktop and OpenTune:
  - Sleek Left Sidebar Navigation (Explore/Search, Favorites, History, User Profile)
  - Dedicated Table-styled Main Content View with column headers (#, Title, Album, Duration)
  - Seamlessly Integrated Search Header
  - Collapsible Synchronized Lyrics Side Panel
  - High-Fidelity Persistent Bottom Player with Timeline Scrubbing and Volume Control
"""

import gc
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional
import customtkinter as ctk

from core.auth import AuthManager
from core.database import DatabaseManager
from core.innertube_client import InnerTubeClient
from core.player import AudioPlayer
from core.lyrics_engine import LyricsEngine
from core.queue_manager import QueueManager
from ui import theme
from ui.icons import IconManager
from ui.components import BottomPlayer, HomeView, LyricsView, SearchBar, TrackItem, UserProfile


class REAMusicApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Appearance configuration
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title("REA Music - Desktop Player")
        self.geometry("1200x780")
        self.minsize(980, 640)
        self.configure(fg_color=theme.BG_ROOT)

        # Window icon configuration
        self._set_app_icon()

        # Core subsystems
        self.client = InnerTubeClient()
        self.player = AudioPlayer()
        self.lyrics_engine = LyricsEngine()
        self.queue_manager = QueueManager()
        self.auth_manager = AuthManager()
        self.db = DatabaseManager()

        # Engine event hooks
        self.player.on_progress = self._on_player_progress
        self.player.on_state_change = self._on_player_state_change
        self.player.on_track_end = self._on_player_track_end

        # Application state
        self.active_item_widgets: List[TrackItem] = []
        self.is_lyrics_open: bool = False
        self._current_lyrics_vid: Optional[str] = None
        self._active_stream_token: Optional[object] = None
        self.active_tab: str = "home"
        self._toast_job: Optional[str] = None

        # Build UI layout
        self._build_ui()

        # Load existing user session (if any)
        self._init_session()

        # Initial view: Home
        self._switch_tab("home")

        # Window close handler
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # 1. Persistent Player Banner (Pinned at bottom)
        self.bottom_player = BottomPlayer(
            self,
            on_toggle_pause=self._handle_toggle_pause,
            on_prev=self._handle_prev_track,
            on_next=self._handle_next_track,
            on_seek=self._handle_seek,
            on_volume=self._handle_volume,
            on_toggle_lyrics=self._toggle_lyrics,
            on_toggle_favorite=self._handle_toggle_favorite,
        )
        self.bottom_player.pack(side="bottom", fill="x")

        # 2. Main Body Container (Sidebar + Content View)
        self.body_container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.body_container.pack(side="top", fill="both", expand=True)

        # -------------------------------------------------------------
        # Left Sidebar (Navigation, Library & User Profile)
        # -------------------------------------------------------------
        self.sidebar = ctk.CTkFrame(
            self.body_container,
            fg_color=theme.SIDEBAR_BG,
            width=230,
            corner_radius=0,
            border_width=1,
            border_color=theme.BORDER_COLOR,
        )
        self.sidebar.pack(side="left", fill="y", padx=0, pady=0)
        self.sidebar.pack_propagate(False)

        # Branding Header
        brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", padx=18, pady=(20, 24))

        brand_icon = ctk.CTkLabel(
            brand_frame,
            text="",
            image=IconManager.get("music", (24, 24), color=theme.ACCENT_COLOR),
        )
        brand_icon.pack(side="left", padx=(0, 10))

        brand_title = ctk.CTkLabel(
            brand_frame,
            text="REA Music",
            font=(theme.FONT_FAMILY, 18, "bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        brand_title.pack(side="left")

        # Navigation Section
        nav_label = ctk.CTkLabel(
            self.sidebar,
            text="MENU",
            font=(theme.FONT_FAMILY, 10, "bold"),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        nav_label.pack(fill="x", padx=20, pady=(0, 6))

        self.btn_nav_home = ctk.CTkButton(
            self.sidebar,
            text="   Home",
            image=IconManager.get("home", (16, 16), color="#ffffff"),
            compound="left",
            font=(theme.FONT_FAMILY, 13, "bold"),
            fg_color=theme.ACCENT_BG,
            hover_color="#182338",
            border_width=1,
            border_color=theme.ACCENT_BORDER,
            text_color="#ffffff",
            anchor="w",
            height=38,
            corner_radius=8,
            command=lambda: self._switch_tab("home"),
        )
        self.btn_nav_home.pack(fill="x", padx=12, pady=3)

        self.btn_nav_search = ctk.CTkButton(
            self.sidebar,
            text="   Explore",
            image=IconManager.get("compass", (16, 16), color="#94a3b8"),
            compound="left",
            font=(theme.FONT_FAMILY, 13),
            fg_color="transparent",
            hover_color="#182338",
            border_width=0,
            text_color=theme.TEXT_SECONDARY,
            anchor="w",
            height=38,
            corner_radius=8,
            command=lambda: self._switch_tab("search"),
        )
        self.btn_nav_search.pack(fill="x", padx=12, pady=3)

        self.btn_nav_favs = ctk.CTkButton(
            self.sidebar,
            text="   Favorites",
            image=IconManager.get("heart_filled", (16, 16), color="#94a3b8"),
            compound="left",
            font=(theme.FONT_FAMILY, 13),
            fg_color="transparent",
            hover_color="#182338",
            border_width=0,
            text_color=theme.TEXT_SECONDARY,
            anchor="w",
            height=38,
            corner_radius=8,
            command=lambda: self._switch_tab("favorites"),
        )
        self.btn_nav_favs.pack(fill="x", padx=12, pady=3)

        self.btn_nav_hist = ctk.CTkButton(
            self.sidebar,
            text="   History",
            image=IconManager.get("clock", (16, 16), color="#94a3b8"),
            compound="left",
            font=(theme.FONT_FAMILY, 13),
            fg_color="transparent",
            hover_color="#182338",
            border_width=0,
            text_color=theme.TEXT_SECONDARY,
            anchor="w",
            height=38,
            corner_radius=8,
            command=lambda: self._switch_tab("history"),
        )
        self.btn_nav_hist.pack(fill="x", padx=12, pady=3)

        # Library Divider
        lib_divider = ctk.CTkFrame(self.sidebar, fg_color=theme.BORDER_COLOR, height=1)
        lib_divider.pack(fill="x", padx=18, pady=16)

        lib_label = ctk.CTkLabel(
            self.sidebar,
            text="YOUR LIBRARY",
            font=(theme.FONT_FAMILY, 10, "bold"),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        lib_label.pack(fill="x", padx=20, pady=(0, 6))

        btn_liked_playlist = ctk.CTkButton(
            self.sidebar,
            text="⭐   Liked Songs",
            font=(theme.FONT_FAMILY, 12),
            fg_color="transparent",
            hover_color="#182338",
            text_color=theme.TEXT_SECONDARY,
            anchor="w",
            height=34,
            corner_radius=6,
            command=lambda: self._switch_tab("favorites"),
        )
        btn_liked_playlist.pack(fill="x", padx=12, pady=2)

        # Spacer
        spacer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        # Bottom Sidebar: User Profile Card
        user_container = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        user_container.pack(fill="x", padx=12, pady=(0, 16))

        self.user_profile = UserProfile(
            user_container,
            on_login=self._handle_login,
            on_logout=self._handle_logout,
        )
        self.user_profile.pack(fill="x")

        # -------------------------------------------------------------
        # Central Main View Area (Header + Scrollable Track Table)
        # -------------------------------------------------------------
        self.content_area = ctk.CTkFrame(self.body_container, fg_color=theme.SURFACE_MAIN, corner_radius=0)
        self.content_area.pack(side="left", fill="both", expand=True, padx=0, pady=0)

        # Top Header (Search Bar + User Profile)
        self.top_header = ctk.CTkFrame(self.content_area, fg_color=theme.SURFACE_HEADER, height=60, corner_radius=0)
        self.top_header.pack(fill="x", padx=0, pady=0)
        self.top_header.pack_propagate(False)

        # Search Bar on Top Left
        self.search_bar = SearchBar(self.top_header, on_search=self.perform_search, width=440)
        self.search_bar.pack(side="left", padx=24, pady=9)

        # Toast / Alert Notification (Hidden by default)
        self.toast_banner = ctk.CTkLabel(
            self.content_area,
            text="",
            font=(theme.FONT_FAMILY, 12, "bold"),
            text_color="#ffffff",
            fg_color="#3a1c1c",
            corner_radius=8,
            height=32,
        )

        # Meta Header Container (Contains Title, Table Column Headers, and Divider)
        self.table_meta_frame = ctk.CTkFrame(self.content_area, fg_color="transparent")
        self.table_meta_frame.pack(fill="x", padx=0, pady=0)

        # View Title & Subtitle Section
        self.title_sec = ctk.CTkFrame(self.table_meta_frame, fg_color="transparent")
        self.title_sec.pack(fill="x", padx=28, pady=(16, 6))

        self.view_title = ctk.CTkLabel(
            self.title_sec,
            text="Explore",
            font=(theme.FONT_FAMILY, 24, "bold"),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        self.view_title.pack(anchor="w")

        self.view_subtitle = ctk.CTkLabel(
            self.title_sec,
            text="Search songs, artists, or albums on YouTube Music",
            font=(theme.FONT_FAMILY, 12),
            text_color="#888888",
            anchor="w",
        )
        self.view_subtitle.pack(anchor="w", pady=(2, 0))

        # Spotify-Style Table Header Row (#, Title, Album, Duration)
        self.table_header = ctk.CTkFrame(self.table_meta_frame, fg_color="transparent", height=28)
        self.table_header.pack(fill="x", padx=28, pady=(10, 4))

        self.table_header.grid_columnconfigure(2, weight=3)
        self.table_header.grid_columnconfigure(3, weight=2)
        self.table_header.grid_columnconfigure(4, weight=0)

        lbl_h_num = ctk.CTkLabel(self.table_header, text="#", font=(theme.FONT_FAMILY, 11, "bold"), text_color="#6e6e6e", width=32, anchor="center")
        lbl_h_num.grid(row=0, column=0, padx=(8, 4))

        lbl_h_thumb = ctk.CTkLabel(self.table_header, text="", width=40)
        lbl_h_thumb.grid(row=0, column=1, padx=(4, 12))

        lbl_h_title = ctk.CTkLabel(self.table_header, text="TITLE", font=(theme.FONT_FAMILY, 11, "bold"), text_color="#6e6e6e", anchor="w")
        lbl_h_title.grid(row=0, column=2, sticky="w", padx=(0, 12))

        lbl_h_album = ctk.CTkLabel(self.table_header, text="ALBUM", font=(theme.FONT_FAMILY, 11, "bold"), text_color="#6e6e6e", anchor="w")
        lbl_h_album.grid(row=0, column=3, sticky="w", padx=(0, 12))

        lbl_h_dur = ctk.CTkLabel(
            self.table_header,
            text="",
            image=IconManager.get("clock", (13, 13), color="#6e6e6e"),
            width=50,
            anchor="e",
        )
        lbl_h_dur.grid(row=0, column=4, padx=(8, 14))

        # Divider under table header
        self.table_div = ctk.CTkFrame(self.table_meta_frame, fg_color="#1e1e1e", height=1)
        self.table_div.pack(fill="x", padx=28, pady=(0, 6))

        # Scrollable Track List Container
        self.scroll_frame = ctk.CTkScrollableFrame(
            self.content_area,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color="#242424",
            scrollbar_button_hover_color="#363636",
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        # -------------------------------------------------------------
        # Right Column: Lyrics View (Hidden by default, toggled via bottom bar)
        # -------------------------------------------------------------
        self.lyrics_view = LyricsView(
            self.body_container,
            on_seek=self._handle_seek,
            on_close=self._toggle_lyrics,
            width=360,
        )

    # -------------------------------------------------------------
    # Navigation Tabs Switcher
    # -------------------------------------------------------------

    def _switch_tab(self, tab: str):
        self.active_tab = tab

        # Reset button styles with muted icons & slate text
        for btn, icon_name in [
            (self.btn_nav_home, "home"),
            (self.btn_nav_search, "compass"),
            (self.btn_nav_favs, "heart_filled"),
            (self.btn_nav_hist, "clock"),
        ]:
            btn.configure(
                fg_color="transparent",
                border_width=0,
                text_color=theme.TEXT_SECONDARY,
                font=(theme.FONT_FAMILY, 13),
                image=IconManager.get(icon_name, (16, 16), color="#94a3b8"),
            )

        if tab == "home":
            self.btn_nav_home.configure(
                fg_color=theme.ACCENT_BG,
                border_width=1,
                border_color=theme.ACCENT_BORDER,
                text_color="#ffffff",
                font=(theme.FONT_FAMILY, 13, "bold"),
                image=IconManager.get("home", (16, 16), color=theme.ACCENT_COLOR),
            )
            self._render_home_view()
        elif tab == "search":
            self.btn_nav_search.configure(
                fg_color=theme.ACCENT_BG,
                border_width=1,
                border_color=theme.ACCENT_BORDER,
                text_color="#ffffff",
                font=(theme.FONT_FAMILY, 13, "bold"),
                image=IconManager.get("compass", (16, 16), color=theme.ACCENT_COLOR),
            )
            self._render_search_tab()
        elif tab == "favorites":
            self.btn_nav_favs.configure(
                fg_color=theme.ACCENT_BG,
                border_width=1,
                border_color=theme.ACCENT_BORDER,
                text_color="#ffffff",
                font=(theme.FONT_FAMILY, 13, "bold"),
                image=IconManager.get("heart_filled", (16, 16), color="#ff4757"),
            )
            self._render_favorites_view()
        elif tab == "history":
            self.btn_nav_hist.configure(
                fg_color=theme.ACCENT_BG,
                border_width=1,
                border_color=theme.ACCENT_BORDER,
                text_color="#ffffff",
                font=(theme.FONT_FAMILY, 13, "bold"),
                image=IconManager.get("clock", (16, 16), color=theme.ACCENT_COLOR),
            )
            self._render_history_view()

    def _show_table_headers(self, title: str = "", subtitle: str = ""):
        self.title_sec.pack(fill="x", padx=28, pady=(16, 6))
        if title:
            self.view_title.configure(text=title)
        if subtitle:
            self.view_subtitle.configure(text=subtitle)
        self.table_header.pack(fill="x", padx=28, pady=(10, 4))
        self.table_div.pack(fill="x", padx=28, pady=(0, 6))

    def _hide_table_headers(self):
        self.title_sec.pack_forget()
        self.table_header.pack_forget()
        self.table_div.pack_forget()

    def _render_home_view(self):
        self._hide_table_headers()

        for w in self.scroll_frame.winfo_children():
            w.destroy()
        self.active_item_widgets.clear()

        try:
            self.scroll_frame._parent_canvas.yview_moveto(0.0)
        except Exception:
            pass

        home = HomeView(
            self.scroll_frame,
            on_play_track=self._play_shelf_tracks,
            on_select_genre=self._handle_genre_select,
            on_open_favorites=lambda: self._switch_tab("favorites"),
        )
        home.pack(fill="both", expand=True)

    def _render_search_tab(self):
        self._show_table_headers("Explore", "Search songs, artists, or albums on YouTube Music")
        self._show_welcome_state()

    def _play_shelf_tracks(self, tracks: List[Dict[str, Any]], start_index: int = 0):
        self._last_manual_select_time = time.time()
        self.queue_manager.set_queue(tracks, start_index=start_index)
        self.play_current_queue_track()

    def _handle_genre_select(self, genre_name: str):
        self._switch_tab("search")
        self.search_bar.entry.delete(0, "end")
        self.search_bar.entry.insert(0, genre_name)
        self.perform_search(genre_name)

    # -------------------------------------------------------------
    # Toast Alert Notifications
    # -------------------------------------------------------------

    def show_toast(self, message: str, is_error: bool = True):
        """Displays a clean auto-dismissing notification banner."""
        if self._toast_job:
            self.after_cancel(self._toast_job)

        bg = "#3a1c1c" if is_error else theme.ACCENT_BG
        txt_color = "#ff8888" if is_error else theme.ACCENT_COLOR
        self.toast_banner.configure(text=f"  {message}  ", fg_color=bg, text_color=txt_color)
        self.toast_banner.pack(before=self.table_meta_frame, fill="x", padx=28, pady=(8, 0))

        self._toast_job = self.after(4500, self.toast_banner.pack_forget)

    # -------------------------------------------------------------
    # View Renderers (Favorites / History)
    # -------------------------------------------------------------

    def _render_favorites_view(self):
        self._show_table_headers("Liked Songs")

        for w in self.scroll_frame.winfo_children():
            w.destroy()
        self.active_item_widgets.clear()

        favs = self.db.get_favorites()
        self.view_subtitle.configure(text=f"{len(favs)} liked songs in your local library")

        if not favs:
            self._show_empty_state(
                "No liked songs yet.",
                "Click the heart (♡) icon while playing a song to save it here!",
                icon_name="heart_outline",
            )
            return

        for i, track in enumerate(favs, start=1):
            item = TrackItem(
                self.scroll_frame,
                track=track,
                index=i,
                on_select=lambda t=track, idx=i-1: self._select_from_results(favs, idx),
            )
            item.pack(fill="x", pady=2)
            self.active_item_widgets.append(item)

    def _render_history_view(self):
        self._show_table_headers("Recently Played")

        for w in self.scroll_frame.winfo_children():
            w.destroy()
        self.active_item_widgets.clear()

        hist = self.db.get_history(limit=50)
        self.view_subtitle.configure(text=f"Last {len(hist)} played tracks")

        if not hist:
            self._show_empty_state(
                "Your history is empty.",
                "Tracks you listen to will automatically appear here.",
                icon_name="clock",
            )
            return

        for i, track in enumerate(hist, start=1):
            item = TrackItem(
                self.scroll_frame,
                track=track,
                index=i,
                on_select=lambda t=track, idx=i-1: self._select_from_results(hist, idx),
            )
            item.pack(fill="x", pady=2)
            self.active_item_widgets.append(item)

    def _show_empty_state(self, title: str, subtitle: str, icon_name: str = "music"):
        box = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        box.pack(expand=True, pady=60)
        ico = ctk.CTkLabel(box, text="", image=IconManager.get(icon_name, (36, 36), color="#475569"))
        ico.pack(pady=(0, 10))
        t = ctk.CTkLabel(box, text=title, font=(theme.FONT_FAMILY, 16, "bold"), text_color=theme.TEXT_PRIMARY)
        t.pack(pady=(0, 4))
        s = ctk.CTkLabel(box, text=subtitle, font=(theme.FONT_FAMILY, 12), text_color=theme.TEXT_SECONDARY)
        s.pack()

    # -------------------------------------------------------------
    # Favorite (Heart) Toggle
    # -------------------------------------------------------------

    def _handle_toggle_favorite(self):
        current_track = self.queue_manager.get_current_track()
        if not current_track:
            self.show_toast("No active track to favorite.", is_error=False)
            return

        now_fav = self.db.toggle_favorite(current_track)
        self.bottom_player.set_favorite_state(now_fav)

        title = current_track.get("title", "Track")
        if now_fav:
            self.show_toast(f"♥ '{title}' added to Liked Songs!", is_error=False)
        else:
            self.show_toast(f"♡ '{title}' removed from Liked Songs.", is_error=False)

        if self.active_tab == "favorites":
            self._render_favorites_view()

    # -------------------------------------------------------------
    # Google OAuth 2.0 Authentication Workflow
    # -------------------------------------------------------------

    def _init_session(self):
        saved_user = self.auth_manager.load_session()
        self.user_profile.set_user(saved_user)

    def _handle_login(self):
        c_id, c_secret = self.auth_manager.get_credentials()
        if not c_id or not c_secret:
            self.user_profile.show_credentials_dialog(
                self,
                on_save=self._on_credentials_saved,
            )
            return

        self.user_profile.set_loading(True)
        self.show_toast("Waiting for Google authorization in browser...", is_error=False)
        self.auth_manager.login_async(self._on_login_completed)

    def _on_credentials_saved(self, client_id: str, client_secret: str):
        self.auth_manager.save_credentials(client_id, client_secret)
        self._handle_login()

    def _on_login_completed(self, success: bool, user_info: Optional[Dict[str, Any]], err_msg: Optional[str]):
        def update():
            self.user_profile.set_loading(False)
            if success and user_info:
                self.user_profile.set_user(user_info)
                first_name = user_info.get("given_name") or user_info.get("name", "")
                self.show_toast(f"Welcome, {first_name}! Google profile connected.", is_error=False)
            else:
                self.show_toast(f"Authentication not completed: {err_msg or 'Unknown error'}")
        self.after(0, update)

    def _handle_logout(self):
        self.auth_manager.clear_session()
        self.user_profile.set_user(None)
        self.show_toast("Signed out. Switched to guest mode.", is_error=False)

    # -------------------------------------------------------------
    # Welcome & Discovery Suggestions
    # -------------------------------------------------------------

    def _show_welcome_state(self):
        for w in self.scroll_frame.winfo_children():
            w.destroy()

        welcome_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        welcome_frame.pack(fill="both", expand=True, pady=40)

        icon_label = ctk.CTkLabel(
            welcome_frame,
            text="",
            image=IconManager.get("compass", (48, 48), color=theme.ACCENT_COLOR),
        )
        icon_label.pack(pady=(10, 12))

        h1 = ctk.CTkLabel(
            welcome_frame,
            text="Discover and Stream Without Limits",
            font=(theme.FONT_FAMILY, 20, "bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        h1.pack(pady=(0, 4))

        h2 = ctk.CTkLabel(
            welcome_frame,
            text="High-fidelity audio streaming, synchronized LRC lyrics, and zero advertising.",
            font=(theme.FONT_FAMILY, 12),
            text_color=theme.TEXT_SECONDARY,
        )
        h2.pack(pady=(0, 20))

        chips_frame = ctk.CTkFrame(welcome_frame, fg_color="transparent")
        chips_frame.pack()

        suggestions = [
            "Daft Punk Get Lucky",
            "The Weeknd Blinding Lights",
            "JVKE infinity beyond",
            "Queen Bohemian Rhapsody",
            "Coldplay Viva La Vida",
        ]
        for s in suggestions:
            btn = ctk.CTkButton(
                chips_frame,
                text=s,
                font=(theme.FONT_FAMILY, 12),
                fg_color="#131924",
                hover_color="#1a2334",
                border_width=1,
                border_color="#1e293b",
                text_color="#94a3b8",
                corner_radius=16,
                command=lambda q=s: self._quick_search(q),
            )
            btn.pack(side="left", padx=5, pady=4)

    def _quick_search(self, query: str):
        self.search_bar.entry.delete(0, "end")
        self.search_bar.entry.insert(0, query)
        self.perform_search(query)

    # -------------------------------------------------------------
    # Search Workflow (Asynchronous)
    # -------------------------------------------------------------

    def perform_search(self, query: str):
        if self.active_tab != "search":
            self._switch_tab("search")

        self._show_table_headers(f"Results for '{query}'", "Searching YouTube Music...")
        self.search_bar.set_loading(True)

        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.active_item_widgets.clear()

        threading.Thread(target=self._search_worker, args=(query,), daemon=True).start()

    def _search_worker(self, query: str):
        try:
            results = self.client.search(query, filter_songs=True, limit=30)
            self.after(0, self._render_search_results, results)
        except Exception as e:
            self.after(0, self._render_search_error, str(e))

    def _render_search_results(self, results: List[Dict[str, Any]]):
        self.search_bar.set_loading(False)

        if not results:
            self.view_subtitle.configure(text="No results found. Try another query.")
            self._show_empty_state(
                "No songs found.",
                "Check spelling or search for another artist or track.",
                icon_name="search",
            )
            return

        self.view_subtitle.configure(text=f"{len(results)} tracks found")

        for i, track in enumerate(results, start=1):
            item = TrackItem(
                self.scroll_frame,
                track=track,
                index=i,
                on_select=lambda t=track, idx=i-1: self._select_from_results(results, idx),
            )
            item.pack(fill="x", pady=2)
            self.active_item_widgets.append(item)

    def _render_search_error(self, err_msg: str):
        self.search_bar.set_loading(False)
        self.view_subtitle.configure(text=f"Search error: {err_msg}")
        self.show_toast(f"Search error: {err_msg}")

    # -------------------------------------------------------------
    # Queue & Playback Workflow (Leak Prevention & Async Resolution)
    # -------------------------------------------------------------

    def _select_from_results(self, results: List[Dict[str, Any]], index: int):
        self._last_manual_select_time = time.time()
        self.queue_manager.set_queue(results, start_index=index)
        self.play_current_queue_track()

    def play_current_queue_track(self):
        track = self.queue_manager.get_current_track()
        if not track:
            return

        idx = self.queue_manager.get_current_index()

        for i, widget in enumerate(self.active_item_widgets):
            widget.set_active(i == idx)

        dur_sec = self._parse_duration(track.get("duration", ""))
        vid = track.get("video_id", "")

        # Record in local SQLite history
        self.db.add_history(track)
        is_fav = self.db.is_favorite(vid)

        # Immediately update bottom player UI
        self.bottom_player.set_track_info(track, duration_sec=dur_sec, is_fav=is_fav)

        # Notify lyrics view loading state
        self.lyrics_view.set_loading(track.get("title", ""))

        # Atomic token to prevent race conditions & memory leaks from rapid clicks
        token = object()
        self._active_stream_token = token

        # Clean old buffers
        gc.collect()

        threading.Thread(target=self._resolve_and_play_worker, args=(track, dur_sec, token), daemon=True).start()
        threading.Thread(target=self._fetch_lyrics_worker, args=(track, dur_sec), daemon=True).start()

    def _resolve_and_play_worker(self, track: Dict[str, Any], dur_sec: float, token: object):
        vid = track["video_id"]
        try:
            stream_res = self.client.get_audio_stream(vid)
        except Exception as e:
            if self._active_stream_token == token:
                self.after(0, lambda: self.show_toast(f"Network error while resolving stream: {e}"))
            return

        # Check if user clicked another song in the meantime
        if self._active_stream_token != token:
            return

        if stream_res.get("success"):
            stream_url = stream_res["url"]
            self.player.play(
                stream_url,
                title=track.get("title", ""),
                artist=track.get("artist", ""),
                duration_sec=dur_sec,
                thumbnail_url=track.get("thumbnail_url", ""),
            )
        else:
            self.after(0, lambda: self.show_toast("This track is currently unavailable for streaming."))

    def _fetch_lyrics_worker(self, track: Dict[str, Any], dur_sec: float):
        vid = track.get("video_id")
        self._current_lyrics_vid = vid
        try:
            lyrics = self.lyrics_engine.get_lyrics(
                title=track.get("title", ""),
                artist=track.get("artist", ""),
                video_id=vid,
                duration_sec=dur_sec,
            )
            if self._current_lyrics_vid == vid:
                self.after(0, lambda: self.lyrics_view.set_lyrics(lyrics, track.get("title", "")))
        except Exception:
            pass

    @staticmethod
    def _parse_duration(dur_str: str) -> float:
        if not dur_str:
            return 0.0
        parts = dur_str.strip().split(":")
        try:
            if len(parts) == 2:
                return float(int(parts[0]) * 60 + int(parts[1]))
            elif len(parts) == 3:
                return float(int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]))
        except ValueError:
            pass
        return 0.0

    # -------------------------------------------------------------
    # Bottom Bar Control Callbacks & Auto-Advance
    # -------------------------------------------------------------

    def _handle_toggle_pause(self):
        self.player.toggle_pause()

    def _handle_prev_track(self):
        self._last_manual_select_time = time.time()
        if self.queue_manager.has_prev():
            self.queue_manager.prev_track()
            self.play_current_queue_track()

    def _handle_next_track(self):
        self._last_manual_select_time = time.time()
        if self.queue_manager.has_next():
            self.queue_manager.next_track()
            self.play_current_queue_track()

    def _on_player_track_end(self):
        now = time.time()
        if now - getattr(self, "_last_manual_select_time", 0.0) < 3.0:
            return
        if now - getattr(self, "_last_auto_advance_time", 0.0) < 2.5:
            return
        self._last_auto_advance_time = now
        self.after(0, self._auto_advance_queue)

    def _auto_advance_queue(self):
        if self.queue_manager.has_next():
            self.queue_manager.next_track()
            self.play_current_queue_track()

    def _handle_seek(self, target_sec: float):
        self.player.seek(target_sec)
        self.lyrics_view.sync_time(target_sec)

    def _handle_volume(self, vol: int):
        self.player.set_volume(vol)

    def _toggle_lyrics(self):
        self.is_lyrics_open = not self.is_lyrics_open
        if self.is_lyrics_open:
            self.lyrics_view.pack(side="right", fill="both", padx=(14, 0))
            self.bottom_player.set_lyrics_button_active(True)
            current_pos = self.player.get_state().get("position", 0.0)
            self.lyrics_view.sync_time(current_pos)
        else:
            self.lyrics_view.pack_forget()
            self.bottom_player.set_lyrics_button_active(False)

    def _on_player_progress(self, position: float, duration: float):
        self.after(0, self.bottom_player.update_progress, position, duration)
        if self.is_lyrics_open:
            self.after(0, self.lyrics_view.sync_time, position)

    def _on_player_state_change(self, is_playing: bool):
        self.after(0, self.bottom_player.set_playing_state, is_playing)

    def _set_app_icon(self):
        """Sets native window and taskbar icon with PyInstaller bundle fallback."""
        try:
            if hasattr(sys, "_MEIPASS"):
                ico_path = os.path.join(sys._MEIPASS, "assets", "icon.ico")
            else:
                ico_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.ico")
            if os.path.exists(ico_path):
                self.iconbitmap(ico_path)
        except Exception:
            pass

    def _on_close(self):
        try:
            self.player.stop(manual=True)
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
