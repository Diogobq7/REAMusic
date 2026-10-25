"""
REA UI - Vector Icon System
Renders high-resolution, anti-aliased vector icons using PIL supersampling and CustomTkinter CTkImage.
Replaces low-fidelity unicode emojis with crisp, modern, scalable UI glyphs.
"""

import math
from typing import Dict, Optional, Tuple
from PIL import Image, ImageDraw
import customtkinter as ctk


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    """Converts hex color string (e.g. #ffffff or #1db954) to RGBA tuple."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return (r, g, b, alpha)


class IconManager:
    """
    Centralized icon renderer and memory cache.
    Generates 4x supersampled rasterized vector geometry and scales down with Lanczos anti-aliasing.
    """

    _CACHE: Dict[Tuple[str, int, int, str], ctk.CTkImage] = {}

    @classmethod
    def get(
        cls,
        name: str,
        size: Tuple[int, int] = (20, 20),
        color: str = "#ffffff",
    ) -> ctk.CTkImage:
        """
        Retrieves a cached CTkImage for the specified icon name, size, and color.
        Renders on demand if not present in cache.
        """
        key = (name, size[0], size[1], color.lower())
        if key in cls._CACHE:
            return cls._CACHE[key]

        pil_img = cls._render_icon(name, size, color)
        ctk_img = ctk.CTkImage(
            light_image=pil_img,
            dark_image=pil_img,
            size=size,
        )
        cls._CACHE[key] = ctk_img
        return ctk_img

    @classmethod
    def _render_icon(cls, name: str, size: Tuple[int, int], color: str) -> Image.Image:
        w, h = size
        scale = 4  # 4x supersampling for ultra-crisp antialiased edges
        sw, sh = w * scale, h * scale

        im = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(im)
        rgba = _hex_to_rgba(color)

        render_func = getattr(cls, f"_draw_{name}", None)
        if render_func:
            render_func(draw, sw, sh, rgba)
        else:
            # Fallback circle placeholder
            draw.ellipse([sw * 0.2, sh * 0.2, sw * 0.8, sh * 0.8], fill=rgba)

        # Downsample to 3x Retina resolution for razor-sharp rendering on High-DPI displays
        retina_size = (w * 3, h * 3)
        return im.resize(retina_size, Image.Resampling.LANCZOS)

    # -----------------------------------------------------------------
    # Vector Icon Drawing Routines (Supersampled Geometry)
    # -----------------------------------------------------------------

    @staticmethod
    def _draw_play(draw: ImageDraw.ImageDraw, w: int, h: int, color: Tuple[int, int, int, int]):
        """Equilateral right-pointing play triangle."""
        # Optical horizontal shift so the triangle looks visually centered
        points = [
            (w * 0.30, h * 0.20),
            (w * 0.78, h * 0.50),
            (w * 0.30, h * 0.80),
        ]
        draw.polygon(points, fill=color)

    @staticmethod
    def _draw_pause(draw: ImageDraw.ImageDraw, w: int, h: int, color: Tuple[int, int, int, int]):
        """Dual vertical pause bars with rounded corners."""
        bar_w = w * 0.16
        rad = int(bar_w * 0.4)
        # Left bar
        draw.rounded_rectangle([w * 0.26, h * 0.20, w * 0.26 + bar_w, h * 0.80], radius=rad, fill=color)
        # Right bar
        draw.rounded_rectangle([w * 0.58, h * 0.20, w * 0.58 + bar_w, h * 0.80], radius=rad, fill=color)

    @staticmethod
    def _draw_prev(draw: ImageDraw.ImageDraw, w: int, h: int, color: Tuple[int, int, int, int]):
        """Skip backward: left vertical bar + left-pointing triangle."""
        bar_w = max(2, int(w * 0.11))
        draw.rounded_rectangle([w * 0.20, h * 0.22, w * 0.20 + bar_w, h * 0.78], radius=2, fill=color)
        tri = [
            (w * 0.76, h * 0.22),
            (w * 0.36, h * 0.50),
            (w * 0.76, h * 0.78),
        ]
        draw.polygon(tri, fill=color)

    @staticmethod
    def _draw_next(draw: ImageDraw.ImageDraw, w: int, h: int, color: Tuple[int, int, int, int]):
        """Skip forward: right-pointing triangle + right vertical bar."""
        tri = [
            (w * 0.24, h * 0.22),
            (w * 0.64, h * 0.50),
            (w * 0.24, h * 0.78),
        ]
        draw.polygon(tri, fill=color)
        bar_w = max(2, int(w * 0.11))
        draw.rounded_rectangle([w * 0.69, h * 0.22, w * 0.69 + bar_w, h * 0.78], radius=2, fill=color)

    @staticmethod
    def _draw_heart_filled(draw: ImageDraw.ImageDraw, w: int, h: int, color: Tuple[int, int, int, int]):
        """Smooth parametric heart filled."""
        cx = w / 2.0
        cy = h * 0.48
        scale = w * 0.026
        points = []
        steps = 120
        for i in range(steps):
            t = math.pi * 2 * (i / float(steps))
            x = 16 * (math.sin(t) ** 3)
            y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
            points.append((cx + x * scale, cy + y * scale))
        draw.polygon(points, fill=color)

    @staticmethod
    def _draw_heart_outline(draw: ImageDraw.ImageDraw, w: int, h: int, color: Tuple[int, int, int, int]):
        """Smooth parametric heart outline."""
        cx = w / 2.0
        cy = h * 0.48
        scale = w * 0.026
        points = []
        steps = 140
        for i in range(steps):
            t = math.pi * 2 * (i / float(steps))
            x = 16 * (math.sin(t) ** 3)
            y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
            points.append((cx + x * scale, cy + y * scale))
        stroke_w = max(2, int(w * 0.075))
        draw.line(points + [points[0]], fill=color, width=stroke_w, joint="curve")

    @staticmethod
    def _draw_lyrics(draw: ImageDraw.ImageDraw, w: int, h: int, color: Tuple[int, int, int, int]):
        """Modern lyrics/mic icon: studio microphone capsule with cradle arc and base."""
        stroke = max(2, int(w * 0.08))
        # Mic capsule (rounded pill)
        cap_w = w * 0.28
        cap_h = h * 0.42
        cx = w * 0.50
        cy = h * 0.36
        draw.rounded_rectangle(
            [cx - cap_w / 2, cy - cap_h / 2, cx + cap_w / 2, cy + cap_h / 2],
            radius=int(cap_w / 2),
            fill=color,
        )
        # Cradle arc around bottom of capsule
        arc_box = [cx - cap_w * 0.85, cy - cap_h * 0.1, cx + cap_w * 0.85, cy + cap_h * 0.72]
        draw.arc(arc_box, start=0, end=180, fill=color, width=stroke)
        # Vertical stem
        stem_top = cy + cap_h * 0.72 / 2 + (arc_box[3] - arc_box[1]) / 2
        stem_bot = h * 0.86
        draw.line([(cx, stem_top), (cx, stem_bot)], fill=color, width=stroke)
        # Base horizontal foot
        foot_w = w * 0.40
        draw.line([(cx - foot_w / 2, stem_bot), (cx + foot_w / 2, stem_bot)], fill=color, width=stroke)

    @staticmethod
    def _draw_volume_high(draw: ImageDraw.ImageDraw, w: int, h: int, color: Tuple[int, int, int, int]):
        """Speaker body with 2 sound waves."""
        stroke = max(2, int(w * 0.08))
        # Speaker base & cone
        cone = [
            (w * 0.16, h * 0.38),
            (w * 0.28, h * 0.38),
            (w * 0.46, h * 0.22),
            (w * 0.46, h * 0.78),
            (w * 0.28, h * 0.62),
            (w * 0.16, h * 0.62),
        ]
        draw.polygon(cone, fill=color)
        # Wave 1 (medium)
        draw.arc([w * 0.36, h * 0.34, w * 0.66, h * 0.66], start=-55, end=55, fill=color, width=stroke)
        # Wave 2 (high)
        draw.arc([w * 0.44, h * 0.20, w * 0.86, h * 0.80], start=-55, end=55, fill=color, width=stroke)

    @staticmethod
    def _draw_volume_medium(draw: ImageDraw.ImageDraw, w: int, h: int, color: Tuple[int, int, int, int]):
        """Speaker body with 1 sound wave."""
        stroke = max(2, int(w * 0.08))
        cone = [
            (w * 0.18, h * 0.38),
            (w * 0.30, h * 0.38),
            (w * 0.50, h * 0.22),
            (w * 0.50, h * 0.78),
            (w * 0.30, h * 0.62),
            (w * 0.18, h * 0.62),
        ]
        draw.polygon(cone, fill=color)
        draw.arc([w * 0.40, h * 0.32, w * 0.72, h * 0.68], start=-55, end=55, fill=color, width=stroke)

    @staticmethod
    def _draw_volume_low(draw: ImageDraw.ImageDraw, w: int, h: int, color: Tuple[int, int, int, int]):
        """Speaker body alone."""
        cone = [
            (w * 0.24, h * 0.38),
            (w * 0.38, h * 0.38),
            (w * 0.60, h * 0.22),
            (w * 0.60, h * 0.78),
            (w * 0.38, h * 0.62),
            (w * 0.24, h * 0.62),
        ]
        draw.polygon(cone, fill=color)

    @staticmethod
    def _draw_volume_mute(draw: ImageDraw.ImageDraw, w: int, h: int, color: Tuple[int, int, int, int]):
        """Speaker body with diagonal mute cross."""
        stroke = max(2, int(w * 0.08))
        cone = [
            (w * 0.16, h * 0.38),
            (w * 0.28, h * 0.38),
            (w * 0.46, h * 0.22),
            (w * 0.46, h * 0.78),
            (w * 0.28, h * 0.62),
            (w * 0.16, h * 0.62),
        ]
        draw.polygon(cone, fill=color)
        # Small 'x' mute glyph
        x_cx = w * 0.70
        x_cy = h * 0.50
        xr = w * 0.12
        draw.line([(x_cx - xr, x_cy - xr), (x_cx + xr, x_cy + xr)], fill=color, width=stroke)
        draw.line([(x_cx - xr, x_cy + xr), (x_cx + xr, x_cy - xr)], fill=color, width=stroke)

    @staticmethod
    def _draw_search(draw: ImageDraw.ImageDraw, w: int, h: int, color: Tuple[int, int, int, int]):
        """Crisp magnifying glass search icon."""
        stroke = max(2, int(w * 0.085))
        # Lens circle
        r = w * 0.26
        cx, cy = w * 0.42, h * 0.42
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=stroke)
        # Angled handle
        h_start_x = cx + r * math.cos(math.radians(45))
        h_start_y = cy + r * math.sin(math.radians(45))
        h_end_x = w * 0.84
        h_end_y = h * 0.84
        draw.line([(h_start_x, h_start_y), (h_end_x, h_end_y)], fill=color, width=stroke)

    @staticmethod
    def _draw_close(draw: ImageDraw.ImageDraw, w: int, h: int, color: Tuple[int, int, int, int]):
        """Clean 'X' close icon."""
        stroke = max(2, int(w * 0.09))
        margin = w * 0.28
        draw.line([(margin, margin), (w - margin, h - margin)], fill=color, width=stroke)
        draw.line([(margin, h - margin), (w - margin, margin)], fill=color, width=stroke)

    @staticmethod
    def _draw_clock(draw: ImageDraw.ImageDraw, w: int, h: int, color: Tuple[int, int, int, int]):
        """Clock icon for Recently Played history."""
        stroke = max(2, int(w * 0.08))
        cx, cy = w * 0.50, h * 0.50
        r = w * 0.38
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=stroke)
        # Hour hand (up)
        draw.line([(cx, cy), (cx, cy - r * 0.55)], fill=color, width=stroke)
        # Minute hand (right)
        draw.line([(cx, cy), (cx + r * 0.45, cy)], fill=color, width=stroke)

    @staticmethod
    def _draw_compass(draw: ImageDraw.ImageDraw, w: int, h: int, color: Tuple[int, int, int, int]):
        """Compass / Explore icon."""
        stroke = max(2, int(w * 0.08))
        cx, cy = w * 0.50, h * 0.50
        r = w * 0.38
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=stroke)
        # Diamond needle
        nr = r * 0.65
        needle_top = [
            (cx, cy),
            (cx + nr * 0.65, cy - nr * 0.65),
            (cx, cy - nr * 0.15),
        ]
        draw.polygon(needle_top, fill=color)
        needle_bot = [
            (cx, cy),
            (cx - nr * 0.65, cy + nr * 0.65),
            (cx, cy + nr * 0.15),
        ]
        draw.polygon(needle_bot, fill=color)

    @staticmethod
    def _draw_music(draw: ImageDraw.ImageDraw, w: int, h: int, color: Tuple[int, int, int, int]):
        """Double eighth-notes connected by a horizontal beam."""
        stem_w = max(2, int(w * 0.08))
        note_r = w * 0.13
        # Left note head
        draw.ellipse([w * 0.20, h * 0.62, w * 0.20 + note_r * 2, h * 0.62 + note_r * 1.6], fill=color)
        # Right note head
        draw.ellipse([w * 0.54, h * 0.50, w * 0.54 + note_r * 2, h * 0.50 + note_r * 1.6], fill=color)
        # Stems
        left_stem_x = w * 0.20 + note_r * 2 - stem_w / 2
        right_stem_x = w * 0.54 + note_r * 2 - stem_w / 2
        top_y = h * 0.20
        draw.line([(left_stem_x, h * 0.68), (left_stem_x, top_y + h * 0.08)], fill=color, width=stem_w)
        draw.line([(right_stem_x, h * 0.56), (right_stem_x, top_y)], fill=color, width=stem_w)
        # Crossbar / Beam
        beam_points = [
            (left_stem_x - stem_w / 2, top_y + h * 0.08),
            (right_stem_x + stem_w / 2, top_y),
            (right_stem_x + stem_w / 2, top_y + h * 0.12),
            (left_stem_x - stem_w / 2, top_y + h * 0.20),
        ]
        draw.polygon(beam_points, fill=color)

    @staticmethod
    def _draw_home(draw: ImageDraw.ImageDraw, w: int, h: int, color: Tuple[int, int, int, int]):
        """Clean modern home / house icon."""
        roof = [
            (w * 0.16, h * 0.46),
            (w * 0.50, h * 0.18),
            (w * 0.84, h * 0.46),
            (w * 0.76, h * 0.46),
            (w * 0.76, h * 0.82),
            (w * 0.58, h * 0.82),
            (w * 0.58, h * 0.58),
            (w * 0.42, h * 0.58),
            (w * 0.42, h * 0.82),
            (w * 0.24, h * 0.82),
            (w * 0.24, h * 0.46),
        ]
        draw.polygon(roof, fill=color)

    @staticmethod
    def _draw_shuffle(draw: ImageDraw.ImageDraw, w: int, h: int, color: Tuple[int, int, int, int]):
        """Crossed arrows for shuffle."""
        stroke = max(2, int(w * 0.08))
        # Top-left to bottom-right
        draw.line([(w * 0.20, h * 0.28), (w * 0.45, h * 0.28), (w * 0.65, h * 0.72), (w * 0.78, h * 0.72)], fill=color, width=stroke)
        # Bottom-left to top-right
        draw.line([(w * 0.20, h * 0.72), (w * 0.45, h * 0.72), (w * 0.65, h * 0.28), (w * 0.78, h * 0.28)], fill=color, width=stroke)
        # Arrow heads
        draw.polygon([(w * 0.80, h * 0.20), (w * 0.80, h * 0.36), (w * 0.90, h * 0.28)], fill=color)
        draw.polygon([(w * 0.80, h * 0.64), (w * 0.80, h * 0.80), (w * 0.90, h * 0.72)], fill=color)
