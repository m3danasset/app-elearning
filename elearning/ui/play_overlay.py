"""Tombol putar/jeda minimalis (segitiga / dua balok putih saja) yang melayang di tengah video.

Dipakai oleh mini player dan pemutar utama (termasuk layar penuh). Widget Tk biasa tidak bisa
transparan di atas jendela video mpv, jadi tombol ini jendela kecil terpisah dengan warna latar
yang dibuat transparan oleh Windows (seperti ikon aplikasi mengambang). Di Windows jendelanya
dibuat "tidak merebut fokus", jadi mengklik tombol tidak memindahkan fokus keyboard dari aplikasi.
"""

import sys
import time
import tkinter as tk

from elearning import config as C
from elearning.ui import aa_icons

KEY = "#010203"      # warna yang dibuat transparan oleh Windows (tidak dipakai di gambar)
SETTLE = 0.3         # detik posisi harus diam sebelum tombol muncul lagi


def no_activate(win):
    """Windows: jendela melayang tidak pernah merebut fokus (Blender / aplikasi tetap aktif) dan
    tidak muncul di daftar Alt+Tab / taskbar (WS_EX_NOACTIVATE + WS_EX_TOOLWINDOW)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        win.update_idletasks()
        u = ctypes.WinDLL("user32", use_last_error=True)
        u.GetParent.argtypes = [wintypes.HWND]
        u.GetParent.restype = wintypes.HWND
        u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        u.GetWindowLongW.restype = ctypes.c_long
        u.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        hwnd = u.GetParent(win.winfo_id()) or win.winfo_id()
        style = u.GetWindowLongW(hwnd, -20)      # GWL_EXSTYLE
        u.SetWindowLongW(hwnd, -20, style | 0x08000000 | 0x00000080)
    except Exception as exc:
        C.log(f"Jendela melayang: gagal diatur tanpa fokus: {exc!r}")


class PlayOverlay(tk.Toplevel):
    def __init__(self, master, on_click, size=72):
        super().__init__(master)
        self.size = size
        self.playing = False
        self.shown = False
        self._center = None
        self._block = 0.0
        self.overrideredirect(True)
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass
        self.configure(bg=KEY)
        try:
            self.attributes("-transparentcolor", KEY)
        except Exception as exc:
            C.log(f"Tombol putar/jeda: transparentcolor gagal: {exc!r}")
        self.geometry(f"{size}x{size}+0+0")
        self.withdraw()
        self.label = tk.Label(self, bg=KEY, bd=0, highlightthickness=0, cursor="hand2",
                              fg="#ffffff", font=(C.FONT, 22, "bold"))
        self.label.place(x=0, y=0, width=size, height=size)
        self.label.bind("<Button-1>", lambda e: on_click())
        no_activate(self)
        self._apply_image()

    def _apply_image(self):
        kind = "pause" if self.playing else "play"
        size = self.size
        ph = aa_icons.photo(("ov", kind, size), lambda: aa_icons.render_overlay(kind, size, KEY))
        if ph is not None:
            self.label.config(image=ph, text="")
            self.label.image = ph
        else:                   # cadangan kalau gambar gagal dibuat
            self.label.config(image="", text="❚❚" if self.playing else "▶")

    def set_playing(self, playing):
        playing = bool(playing)
        if playing != self.playing:
            self.playing = playing
            self._apply_image()

    def set_size(self, size):
        if size != self.size:
            self.size = size
            self._center = None
            self.geometry(f"{size}x{size}")
            self.label.place(x=0, y=0, width=size, height=size)
            self._apply_image()

    def hide(self):
        if self.shown:
            self.withdraw()
            self.shown = False

    def settle(self):
        """Posisi sedang berubah: sembunyikan segera, tampil lagi setelah diam sebentar."""
        self.hide()
        self._block = time.time() + SETTLE

    def sync(self, want, cx, cy):
        """Tampilkan di tengah (cx, cy) kalau want; kalau tidak, sembunyikan."""
        if not want:
            self.hide()
            return
        if self._center is None:
            self._center = (cx, cy)
        elif (cx, cy) != self._center:
            self._center = (cx, cy)
            self.settle()               # video pindah / berubah ukuran
        if time.time() < self._block:
            return
        half = self.size // 2
        self.geometry(f"+{cx - half}+{cy - half}")
        if not self.shown:
            self.deiconify()
            self.attributes("-topmost", True)
            self.lift()
            self.shown = True
