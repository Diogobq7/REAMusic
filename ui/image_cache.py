"""
REA UI - Asynchronous Image Cache & Thumbnail Loader
Fetches, resizes, and caches album artwork and circular user profile avatars in memory.
Engineered with High-DPI supersampling and anti-aliased edge masking for razor-sharp visual fidelity.
"""

import io
import os
import threading
import urllib.request
from typing import Any, Callable, Dict, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageOps
import customtkinter as ctk

from ui.icons import IconManager


class ImageCache:
    """Thread-safe in-memory cache for remote artwork thumbnails and user avatars with Retina supersampling."""

    _cache: Dict[str, ctk.CTkImage] = {}
    _lock = threading.Lock()
    SCALE = 3  # 3x supersampling factor for High-DPI displays

    @classmethod
    def get_placeholder(cls, size: Tuple[int, int] = (52, 52), circular: bool = False) -> ctk.CTkImage:
        """Returns a high-resolution dark placeholder image for loading state."""
        w, h = size
        sw, sh = w * cls.SCALE, h * cls.SCALE

        if circular:
            im = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
            draw = ImageDraw.Draw(im)
            # Smooth filled circle
            draw.ellipse([2, 2, sw - 3, sh - 3], fill=(24, 28, 36, 255), outline=(42, 52, 68, 255), width=cls.SCALE)
            return ctk.CTkImage(light_image=im, dark_image=im, size=size)
        else:
            im = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
            draw = ImageDraw.Draw(im)
            corner_r = int(min(sw, sh) * 0.14)
            draw.rounded_rectangle([1, 1, sw - 2, sh - 2], radius=corner_r, fill=(22, 26, 34, 255), outline=(36, 44, 58, 255), width=cls.SCALE)
            return ctk.CTkImage(light_image=im, dark_image=im, size=size)

    _FONT_CACHE: Dict[int, Any] = {}

    @classmethod
    def _get_font(cls, size_px: int) -> Any:
        """Loads and caches system TrueType fonts for high-resolution PIL rendering."""
        if size_px in cls._FONT_CACHE:
            return cls._FONT_CACHE[size_px]

        candidates = [
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
            "/System/Library/Fonts/SFProText-Bold.otf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        for c in candidates:
            if os.path.exists(c):
                try:
                    f = ImageFont.truetype(c, size_px)
                    cls._FONT_CACHE[size_px] = f
                    return f
                except Exception:
                    pass

        f = ImageFont.load_default()
        cls._FONT_CACHE[size_px] = f
        return f

    @classmethod
    def get_gradient_cover(
        cls,
        size: Tuple[int, int],
        color1: Tuple[int, int, int],
        color2: Tuple[int, int, int],
        corner_radius: int = 10,
        icon_name: Optional[str] = None,
    ) -> ctk.CTkImage:
        """Returns a cached high-res smooth gradient image with optional centered vector icon."""
        key = f"grad_{size}_{color1}_{color2}_{corner_radius}_{icon_name}"
        with cls._lock:
            if key in cls._cache:
                return cls._cache[key]

        w, h = size
        sw, sh = w * cls.SCALE, h * cls.SCALE
        base = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(base)

        r1, g1, b1 = color1
        r2, g2, b2 = color2

        for x in range(sw):
            ratio = x / max(1, sw - 1)
            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)
            draw.line([(x, 0), (x, sh)], fill=(r, g, b, 255))

        mask = Image.new("L", (sw, sh), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, sw, sh], radius=corner_radius * cls.SCALE, fill=255)
        base.putalpha(mask)

        ring = ImageDraw.Draw(base)
        ring.rounded_rectangle([0, 0, sw - 1, sh - 1], radius=corner_radius * cls.SCALE, outline=(255, 255, 255, 30), width=cls.SCALE)

        if icon_name:
            iw = int(min(sw, sh) * 0.44)
            ih = iw
            icon_im = Image.new("RGBA", (iw, ih), (0, 0, 0, 0))
            idraw = ImageDraw.Draw(icon_im)
            render_func = getattr(IconManager, f"_draw_{icon_name}", IconManager._draw_music)
            render_func(idraw, iw, ih, (255, 255, 255, 240))
            px = (sw - iw) // 2
            py = (sh - ih) // 2
            base.paste(icon_im, (px, py), icon_im)

        ctk_img = ctk.CTkImage(light_image=base, dark_image=base, size=size)
        with cls._lock:
            cls._cache[key] = ctk_img
        return ctk_img

    @classmethod
    def get_genre_card_cover(
        cls,
        size: Tuple[int, int],
        name: str,
        color1: Tuple[int, int, int],
        color2: Tuple[int, int, int],
        icon_name: str = "music",
        hover: bool = False,
        corner_radius: int = 10,
    ) -> ctk.CTkImage:
        """
        Renders a composite genre category card in PIL with gradient, rounded corners,
        title typography, and vector glyph. Eliminates Tkinter transparent label black boxes.
        """
        key = f"genre_comp_{size}_{name}_{color1}_{color2}_{icon_name}_{hover}_{corner_radius}"
        with cls._lock:
            if key in cls._cache:
                return cls._cache[key]

        w, h = size
        sw, sh = w * cls.SCALE, h * cls.SCALE
        base = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(base)

        # Slightly brighten gradient on hover
        boost = 1.15 if hover else 1.0
        r1 = min(255, int(color1[0] * boost))
        g1 = min(255, int(color1[1] * boost))
        b1 = min(255, int(color1[2] * boost))

        r2 = min(255, int(color2[0] * boost))
        g2 = min(255, int(color2[1] * boost))
        b2 = min(255, int(color2[2] * boost))

        # Horizontal linear gradient
        for x in range(sw):
            ratio = x / max(1, sw - 1)
            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)
            draw.line([(x, 0), (x, sh)], fill=(r, g, b, 255))

        # Rounded corners alpha mask
        mask = Image.new("L", (sw, sh), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, sw, sh], radius=corner_radius * cls.SCALE, fill=255)
        base.putalpha(mask)

        # Border outline ring
        ring = ImageDraw.Draw(base)
        outline_alpha = 100 if hover else 35
        outline_width = int(cls.SCALE * 1.5) if hover else cls.SCALE
        ring.rounded_rectangle(
            [0, 0, sw - 1, sh - 1],
            radius=corner_radius * cls.SCALE,
            outline=(255, 255, 255, outline_alpha),
            width=outline_width,
        )

        # Category Title text
        font = cls._get_font(int(13.5 * cls.SCALE))
        text_x = int(12 * cls.SCALE)
        text_y = int(10 * cls.SCALE)
        ring.text((text_x, text_y), name, font=font, fill=(255, 255, 255, 255))

        # Bottom-right vector icon glyph
        iw = int(24 * cls.SCALE)
        ih = int(24 * cls.SCALE)
        icon_im = Image.new("RGBA", (iw, ih), (0, 0, 0, 0))
        idraw = ImageDraw.Draw(icon_im)
        render_func = getattr(IconManager, f"_draw_{icon_name}", IconManager._draw_music)
        icon_alpha = 245 if hover else 225
        render_func(idraw, iw, ih, (255, 255, 255, icon_alpha))

        icon_x = sw - iw - int(10 * cls.SCALE)
        icon_y = sh - ih - int(8 * cls.SCALE)
        base.paste(icon_im, (icon_x, icon_y), icon_im)

        # Scale down with Lanczos to Retina resolution
        retina = base.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
        ctk_img = ctk.CTkImage(light_image=retina, dark_image=retina, size=size)

        with cls._lock:
            cls._cache[key] = ctk_img
        return ctk_img

    @staticmethod
    def _dispatch_callback(callback: Callable[[ctk.CTkImage], None], img: ctk.CTkImage) -> None:
        """Schedules UI image callback onto Tkinter main loop to prevent cross-thread PhotoImage errors."""
        try:
            import tkinter
            root = getattr(tkinter, "_default_root", None)
            if root and root.winfo_exists():
                root.after(0, lambda: callback(img))
                return
        except Exception:
            pass
        try:
            callback(img)
        except Exception:
            pass

    @classmethod
    def load_async(
        cls,
        url: str,
        size: Tuple[int, int],
        callback: Callable[[ctk.CTkImage], None],
    ) -> None:
        """Loads a rectangular image from URL asynchronously with rounded corners and Retina caching."""
        if not url:
            cls._dispatch_callback(callback, cls.get_placeholder(size))
            return

        cache_key = f"rect_{url}_{size[0]}x{size[1]}"
        with cls._lock:
            if cache_key in cls._cache:
                cls._dispatch_callback(callback, cls._cache[cache_key])
                return

        def fetch_worker():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=6) as resp:
                    raw_bytes = resp.read()
                    pil_img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")

                    w, h = size
                    sw, sh = w * cls.SCALE, h * cls.SCALE

                    # High-DPI crop and fit
                    fitted = ImageOps.fit(pil_img, (sw, sh), centering=(0.5, 0.5), method=Image.Resampling.LANCZOS)

                    # Smooth rounded corners mask
                    mask = Image.new("L", (sw, sh), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    corner_r = int(min(sw, sh) * 0.14)
                    mask_draw.rounded_rectangle([0, 0, sw, sh], radius=corner_r, fill=255)
                    fitted.putalpha(mask)

                    # Add subtle border ring for modern depth
                    ring = ImageDraw.Draw(fitted)
                    ring.rounded_rectangle([0, 0, sw - 1, sh - 1], radius=corner_r, outline=(255, 255, 255, 20), width=1)

                    ctk_img = ctk.CTkImage(light_image=fitted, dark_image=fitted, size=size)

                    with cls._lock:
                        cls._cache[cache_key] = ctk_img

                    cls._dispatch_callback(callback, ctk_img)
            except Exception:
                cls._dispatch_callback(callback, cls.get_placeholder(size))

        threading.Thread(target=fetch_worker, daemon=True).start()

    @classmethod
    def load_circular_async(
        cls,
        url: str,
        size: Tuple[int, int],
        callback: Callable[[ctk.CTkImage], None],
    ) -> None:
        """Loads an image from URL and applies an anti-aliased circular alpha mask for profile avatars."""
        if not url:
            cls._dispatch_callback(callback, cls.get_placeholder(size, circular=True))
            return

        # Request HD version if Google avatar URL
        hd_url = url
        for tag in ["=s96-c", "=s64-c", "=s32-c", "=s128-c"]:
            if tag in hd_url:
                hd_url = hd_url.replace(tag, "=s256-c")
                break

        cache_key = f"circle_{hd_url}_{size[0]}x{size[1]}"
        with cls._lock:
            if cache_key in cls._cache:
                cls._dispatch_callback(callback, cls._cache[cache_key])
                return

        def fetch_worker():
            try:
                req = urllib.request.Request(hd_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=6) as resp:
                    raw_bytes = resp.read()
                    pil_img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")

                    w, h = size
                    sw, sh = w * cls.SCALE, h * cls.SCALE

                    # High-DPI crop and fit
                    fitted = ImageOps.fit(pil_img, (sw, sh), centering=(0.5, 0.5), method=Image.Resampling.LANCZOS)

                    # Anti-aliased circular mask
                    mask = Image.new("L", (sw, sh), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    mask_draw.ellipse([1, 1, sw - 2, sh - 2], fill=255)
                    fitted.putalpha(mask)

                    # Add sleek subtle border ring
                    ring_draw = ImageDraw.Draw(fitted)
                    ring_draw.ellipse([1, 1, sw - 2, sh - 2], outline=(59, 130, 246, 140), width=cls.SCALE)

                    ctk_img = ctk.CTkImage(light_image=fitted, dark_image=fitted, size=size)

                    with cls._lock:
                        cls._cache[cache_key] = ctk_img

                    cls._dispatch_callback(callback, ctk_img)
            except Exception:
                cls._dispatch_callback(callback, cls.get_placeholder(size, circular=True))

        threading.Thread(target=fetch_worker, daemon=True).start()
