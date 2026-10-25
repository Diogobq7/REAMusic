"""
REA Music Desktop - Application Entry Point
Minimalist, lightweight, dark-mode desktop music player powered by YouTube Music InnerTube reverse engineering.
"""

import sys
from ui import REAMusicApp


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("reamusic.desktop.player.v1")
        except Exception:
            pass

    app = REAMusicApp()
    app.mainloop()


if __name__ == "__main__":
    main()
