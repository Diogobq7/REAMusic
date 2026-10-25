"""
REA Music Desktop - PyInstaller Standalone Windows Executable Builder (.exe)
Automates the packaging of REAMusic into a standalone, windowed (no console) binary.
Embeds CustomTkinter assets, application icons, and handles runtime dependencies.
"""

import os
import shutil
import sys
import PyInstaller.__main__


def generate_icon_if_missing():
    """Generates a modern Dark Mode application icon if not already present."""
    icon_path = os.path.join("assets", "icon.ico")
    if not os.path.exists(icon_path):
        os.makedirs("assets", exist_ok=True)
        from PIL import Image, ImageDraw

        size = (256, 256)
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Background rounded box
        draw.rounded_rectangle([(10, 10), (246, 246)], radius=56, fill="#0a0e17", outline="#3b82f6", width=6)
        # Inner glowing circle
        draw.ellipse([(60, 60), (196, 196)], fill="#101a2c", outline="#2563eb", width=4)
        # Musical note symbol in sapphire blue
        draw.polygon([(110, 145), (145, 135), (145, 95), (110, 105)], fill="#60a5fa")
        draw.ellipse([(95, 135), (115, 155)], fill="#3b82f6")
        draw.ellipse([(130, 125), (150, 145)], fill="#3b82f6")
        draw.rectangle([(108, 104), (112, 145)], fill="#60a5fa")
        draw.rectangle([(143, 94), (147, 135)], fill="#60a5fa")

        img.save("assets/icon.png", format="PNG")
        img.save(icon_path, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
        print("[+] Icon generated at assets/icon.ico")


def build():
    print("=" * 70)
    print("  [REA] BUILDING STANDALONE EXECUTABLE (REAMusic.exe)")
    print("=" * 70)

    generate_icon_if_missing()

    icon_ico = os.path.abspath(os.path.join("assets", "icon.ico"))
    assets_dir = os.path.abspath("assets")

    # Separator for PyInstaller --add-data on Windows is ';'
    sep = ";" if sys.platform == "win32" else ":"

    pyinstaller_args = [
        "main.py",
        "--name=REAMusic",
        "--onefile",
        "--noconsole",
        f"--icon={icon_ico}",
        "--collect-all=customtkinter",
        "--collect-all=PIL",
        "--collect-all=yt_dlp",
        f"--add-data={assets_dir}{sep}assets",
        "--clean",
        "--noconfirm",
    ]

    # Check if local mpv.exe exists in root or common paths to bundle it
    local_mpv = os.path.join(os.getcwd(), "mpv.exe")
    if os.path.exists(local_mpv):
        pyinstaller_args.append(f"--add-binary={local_mpv}{sep}.")
        print("[+] Local mpv.exe detected and bundled into the executable package!")

    print(f"[*] Executing PyInstaller with arguments:\n    {' '.join(pyinstaller_args)}\n")

    try:
        PyInstaller.__main__.run(pyinstaller_args)
        print("\n" + "=" * 70)
        dist_exe = os.path.join(os.getcwd(), "dist", "REAMusic.exe")
        root_exe = os.path.join(os.getcwd(), "REAMusic.exe")
        if os.path.exists(dist_exe):
            try:
                shutil.copy2(dist_exe, root_exe)
                print(f"  [+] Copied executable to root: {root_exe}")
            except Exception as copy_err:
                print(f"  [!] Note: Could not overwrite root REAMusic.exe (possibly currently open): {copy_err}")

            size_mb = os.path.getsize(dist_exe) / (1024 * 1024)
            print(f"  [+] SUCCESS: Executable generated at:")
            print(f"      {dist_exe} ({size_mb:.1f} MB)")
            print("=" * 70)
        else:
            print("  [+] Build completed. Check the 'dist/' directory.")
    except Exception as e:
        print(f"\n[-] Error during PyInstaller build: {e}")
        sys.exit(1)


if __name__ == "__main__":
    build()
