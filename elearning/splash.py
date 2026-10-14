"""Splash screen kecil di tengah layar saat aplikasi sedang dibuka.

Dipanggil paling awal (dari elearning/__init__.py), sebelum OpenCV/Pillow dan
layar-layar dimuat, supaya pengguna tahu aplikasi sedang terbuka. Ditutup oleh
App (ui/window.py) tepat sebelum jendela utama dibuat.

Tidak pernah boleh menghentikan aplikasi: semua kegagalan diabaikan.
"""

import sys

_KEY = "_blender_elearning_splash"  # disimpan di modul sys supaya selamat dari
                                    # muat-ulang paket (lihat main.py)
W, H = 360, 128


def show():
    """Tampilkan splash (kalau belum tampil)."""
    if getattr(sys, _KEY, None) is not None:
        return
    try:
        import tkinter as tk
        from elearning import config as C

        root = tk.Tk()
        root.withdraw()
        root.overrideredirect(True)          # tanpa bingkai & tanpa tombol taskbar
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        x = (root.winfo_screenwidth() - W) // 2
        y = (root.winfo_screenheight() - H) // 2
        root.geometry(f"{W}x{H}+{x}+{y}")
        root.configure(bg=C.ACCENT)          # garis tepi oranye

        box = tk.Frame(root, bg=C.BG)
        box.pack(fill="both", expand=True, padx=2, pady=2)
        tk.Label(box, text="B", bg=C.ACCENT, fg="white", width=2,
                 font=(C.FONT, 20, "bold")).pack(pady=(16, 8))
        tk.Label(box, text=C.APP_NAME, bg=C.BG, fg=C.TEXT,
                 font=(C.FONT, 13, "bold")).pack()
        tk.Label(box, text="Memuat aplikasi…", bg=C.BG, fg=C.MUTED,
                 font=(C.FONT, 10)).pack(pady=(2, 0))

        root.deiconify()
        root.update()                        # paksa tergambar sebelum impor berat
        setattr(sys, _KEY, root)
    except Exception:
        setattr(sys, _KEY, None)


def close():
    """Tutup splash (aman dipanggil berkali-kali)."""
    root = getattr(sys, _KEY, None)
    setattr(sys, _KEY, None)
    if root is not None:
        try:
            root.destroy()
        except Exception:
            pass
