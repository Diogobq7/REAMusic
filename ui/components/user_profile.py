"""
REA UI - User Profile Component
Top-right Google Sign-In profile component supporting:
  - Logged-out state: Clean "Sign in with Google" pill button
  - Logged-in state: Circular avatar with first name & interactive popover dropdown
  - Credentials setup modal if Google Cloud credentials are not configured
"""

from typing import Any, Callable, Dict, Optional
import customtkinter as ctk
from ui import theme
from ui.image_cache import ImageCache


class UserProfile(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_login: Callable[[], None],
        on_logout: Callable[[], None],
        on_save_creds: Optional[Callable[[str, str], None]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_login = on_login
        self.on_logout = on_logout
        self.on_save_creds = on_save_creds

        self.user_data: Optional[Dict[str, Any]] = None
        self._popover: Optional[ctk.CTkToplevel] = None

        self._build_ui()

    def _build_ui(self):
        # 1. Logged Out View (Pill Button)
        self.logged_out_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.logged_out_frame.pack(side="right")

        self.login_btn = ctk.CTkButton(
            self.logged_out_frame,
            text="Sign in with Google",
            font=(theme.FONT_FAMILY, 12, "bold"),
            fg_color="#161f2e",
            hover_color="#223046",
            border_width=1,
            border_color="#25354e",
            text_color="#ffffff",
            corner_radius=18,
            height=36,
            command=self.on_login,
        )
        self.login_btn.pack(side="right")

        # 2. Logged In View (Avatar + First Name + Dropdown trigger)
        self.logged_in_frame = ctk.CTkFrame(
            self,
            fg_color="#121722",
            corner_radius=18,
            border_width=1,
            border_color="#1f293d",
            cursor="hand2",
        )

        self.avatar_label = ctk.CTkLabel(
            self.logged_in_frame,
            text="",
            image=ImageCache.get_placeholder((32, 32), circular=True),
            width=32,
            height=32,
        )
        self.avatar_label.pack(side="left", padx=(4, 8), pady=3)

        self.name_label = ctk.CTkLabel(
            self.logged_in_frame,
            text="",
            font=(theme.FONT_FAMILY, 12, "bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        self.name_label.pack(side="left", padx=(0, 6))

        self.chevron_label = ctk.CTkLabel(
            self.logged_in_frame,
            text="▾",
            font=(theme.FONT_FAMILY, 12),
            text_color=theme.TEXT_SECONDARY,
        )
        self.chevron_label.pack(side="left", padx=(0, 10))

        # Hover states & click bindings
        for w in (self.logged_in_frame, self.avatar_label, self.name_label, self.chevron_label):
            w.bind("<Enter>", lambda e: self.logged_in_frame.configure(fg_color="#1a2334"))
            w.bind("<Leave>", lambda e: self.logged_in_frame.configure(fg_color="#121722"))
            w.bind("<Button-1>", lambda e: self._toggle_popover())

    def set_user(self, user: Optional[Dict[str, Any]]):
        """Switches between logged-in and logged-out states."""
        self.user_data = user
        if user:
            self.logged_out_frame.pack_forget()
            self.logged_in_frame.pack(side="right")

            first_name = user.get("given_name") or user.get("name", "User").split()[0]
            self.name_label.configure(text=first_name)

            pic_url = user.get("picture", "")
            if pic_url:
                ImageCache.load_circular_async(
                    pic_url,
                    size=(32, 32),
                    callback=lambda img: self.avatar_label.configure(image=img),
                )
        else:
            self.logged_in_frame.pack_forget()
            self.logged_out_frame.pack(side="right")
            self._close_popover()

    def set_loading(self, is_loading: bool):
        if is_loading:
            self.login_btn.configure(text="Connecting...", state="disabled")
        else:
            self.login_btn.configure(text="Sign in with Google", state="normal")

    def _toggle_popover(self):
        if self._popover and self._popover.winfo_exists():
            self._close_popover()
        else:
            self._open_popover()

    def _open_popover(self):
        if not self.user_data:
            return

        self._popover = ctk.CTkToplevel(self)
        self._popover.overrideredirect(True)
        self._popover.configure(fg_color="#0e131b")

        # Position right below the logged_in_frame
        self.update_idletasks()
        rx = self.logged_in_frame.winfo_rootx() - 40
        ry = self.logged_in_frame.winfo_rooty() + self.logged_in_frame.winfo_height() + 8
        self._popover.geometry(f"220x130+{rx}+{ry}")
        self._popover.attributes("-topmost", True)

        card = ctk.CTkFrame(
            self._popover,
            fg_color="#0e131b",
            corner_radius=theme.RADIUS_MEDIUM,
            border_width=1,
            border_color="#1e293b",
        )
        card.pack(fill="both", expand=True, padx=4, pady=4)

        full_name = self.user_data.get("name", "")
        email = self.user_data.get("email", "")

        lbl_name = ctk.CTkLabel(
            card,
            text=full_name,
            font=(theme.FONT_FAMILY, 13, "bold"),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        lbl_name.pack(fill="x", padx=14, pady=(12, 2))

        lbl_email = ctk.CTkLabel(
            card,
            text=email,
            font=(theme.FONT_FAMILY, 11),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        lbl_email.pack(fill="x", padx=14, pady=(0, 10))

        # Divider
        divider = ctk.CTkFrame(card, fg_color="#1e293b", height=1)
        divider.pack(fill="x", padx=10, pady=(0, 8))

        logout_btn = ctk.CTkButton(
            card,
            text="Sign Out",
            font=(theme.FONT_FAMILY, 12),
            fg_color="#2b1518",
            hover_color="#3d1d22",
            text_color="#f87171",
            corner_radius=theme.RADIUS_SMALL,
            height=28,
            command=self._handle_logout_click,
        )
        logout_btn.pack(fill="x", padx=12, pady=(0, 10))

        # Close when clicked outside
        self._popover.bind("<FocusOut>", lambda e: self._close_popover())

    def _close_popover(self):
        if self._popover and self._popover.winfo_exists():
            self._popover.destroy()
            self._popover = None

    def _handle_logout_click(self):
        self._close_popover()
        self.on_logout()

    def show_credentials_dialog(self, master_window, on_save: Callable[[str, str], None]):
        """Renders a modal configuration dialog for entering Google OAuth credentials."""
        dialog = ctk.CTkToplevel(master_window)
        dialog.title("Configure Google Credentials")
        dialog.geometry("480x360")
        dialog.resizable(False, False)
        dialog.configure(fg_color="#121212")
        dialog.attributes("-topmost", True)
        dialog.grab_set()

        content = ctk.CTkFrame(dialog, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=20)

        title = ctk.CTkLabel(
            content,
            text="Google OAuth 2.0 Credentials",
            font=(theme.FONT_FAMILY, 16, "bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        title.pack(anchor="w", pady=(0, 6))

        desc = ctk.CTkLabel(
            content,
            text="To sign in with Google, enter the 'Desktop app' credentials created in your Google Cloud Console:",
            font=(theme.FONT_FAMILY, 12),
            text_color=theme.TEXT_SECONDARY,
            wraplength=430,
            justify="left",
        )
        desc.pack(anchor="w", pady=(0, 16))

        # Client ID entry
        lbl_id = ctk.CTkLabel(content, text="Client ID:", font=(theme.FONT_FAMILY, 12), text_color=theme.TEXT_MUTED)
        lbl_id.pack(anchor="w")
        entry_id = ctk.CTkEntry(content, placeholder_text="e.g. 123456...apps.googleusercontent.com", height=34)
        entry_id.pack(fill="x", pady=(2, 10))

        # Client Secret entry
        lbl_sec = ctk.CTkLabel(content, text="Client Secret:", font=(theme.FONT_FAMILY, 12), text_color=theme.TEXT_MUTED)
        lbl_sec.pack(anchor="w")
        entry_sec = ctk.CTkEntry(content, placeholder_text="e.g. GOCSPX-...", show="•", height=34)
        entry_sec.pack(fill="x", pady=(2, 18))

        def save_and_close():
            cid = entry_id.get().strip()
            csec = entry_sec.get().strip()
            if cid and csec:
                on_save(cid, csec)
                dialog.destroy()

        btn_save = ctk.CTkButton(
            content,
            text="Save and Continue",
            font=(theme.FONT_FAMILY, 13, "bold"),
            fg_color=theme.ACCENT_COLOR,
            hover_color=theme.ACCENT_HOVER,
            text_color="#000000",
            height=36,
            command=save_and_close,
        )
        btn_save.pack(fill="x")
