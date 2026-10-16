"""Splash screen di tengah layar saat aplikasi sedang dibuka.

Dipanggil paling awal (dari elearning/__init__.py), sebelum OpenCV dan layar-layar
dimuat, supaya pengguna tahu aplikasi sedang terbuka. Ditutup oleh App (ui/window.py)
tepat sebelum jendela utama dibuat.

Tampilan: kartu gelap bersudut bulat (tema yang sama dengan aplikasi), logo brand
(assets\\logo.png, atau logo kotak M3DAN bawaan), nama aplikasi, dan garis aksen oranye.

Tidak pernah boleh menghentikan aplikasi: semua kegagalan diabaikan.
"""

import sys

_KEY = "_blender_elearning_splash"  # disimpan di modul sys supaya selamat dari
                                    # muat-ulang paket (lihat main.py)
W, H = 440, 280
RADIUS = 18
KEY_COLOR = "#010203"   # warna yang dibuat transparan di Windows (sudut membulat)
BAR_W, BAR_H = 280, 8   # loading bar: panjang & tebal (px)
BAR_COLOR = "#7cc8ff"   # biru muda
BAR_TRACK = "#2e2d2a"
SEG_W = 90              # panjang potongan biru yang bergerak
CYCLE = 1.3             # detik untuk sekali bolak-balik


def _round_bar(cv, x0, y, x1, color, tag):
    r = BAR_H / 2
    cv.delete(tag)
    if x1 - x0 < BAR_H:
        x1 = x0 + BAR_H
    cv.create_oval(x0, y - r, x0 + BAR_H, y + r, fill=color, outline=color, tags=tag)
    cv.create_oval(x1 - BAR_H, y - r, x1, y + r, fill=color, outline=color, tags=tag)
    cv.create_rectangle(x0 + r, y - r, x1 - r, y + r, fill=color, outline=color, tags=tag)


def _draw_bar(root):
    import math
    import time
    cv, x0, x1, y = root._bar
    t = (time.monotonic() % CYCLE) / CYCLE
    k = (1 - math.cos(2 * math.pi * t)) / 2          # 0..1..0 halus
    s = x0 + k * (x1 - x0 - SEG_W)
    _round_bar(cv, s, y, s + SEG_W, BAR_COLOR, "seg")


_last = [0.0]


def _pump():
    """Gerakkan loading bar. Dipanggil berkali-kali selama modul dimuat (lihat _Hook)."""
    import time
    root = getattr(sys, _KEY, None)
    if root is None:
        return
    now = time.monotonic()
    if now - _last[0] < 0.016:
        return
    _last[0] = now
    try:
        _draw_bar(root)
        root.update_idletasks()
        root.update()
    except Exception:
        pass


class _Hook:
    """Setiap kali Python memuat modul baru, loading bar ikut bergerak (thread utama sibuk)."""

    def find_spec(self, *args, **kwargs):
        _pump()
        return None


_HOOK = _Hook()


def _tick():
    root = getattr(sys, _KEY, None)
    if root is not None:   # jalan juga saat thread utama sedang menunggu event Tk
        _pump()
        try:
            root.after(16, _tick)
        except Exception:
            pass


def _build(root, C):
    import tkinter as tk
    rounded = sys.platform == "win32"
    if rounded:
        try:
            root.attributes("-transparentcolor", KEY_COLOR)
        except Exception:
            rounded = False
    outer = KEY_COLOR if rounded else C.LOGIN_BG
    root.configure(bg=outer)

    cv = tk.Canvas(root, width=W, height=H, bg=outer, highlightthickness=0, bd=0)
    cv.pack()
    keep = []
    try:   # kartu bersudut bulat + garis tepi tipis
        from PIL import Image, ImageTk
        from elearning.ui import ui_icons as I
        card = Image.new("RGB", (W, H), I._rgb(C.LOGIN_BG))
        edge = I._render_pill(W, H, RADIUS, C.LOGIN_BG, C.LOGIN_BG, border=C.SIDEBAR_LINE)
        if rounded:   # luar sudut = warna kunci (tepi tajam supaya tidak ada pinggiran gelap)
            mask = I.round_mask(W, H, RADIUS).point(lambda a: 255 if a >= 128 else 0)
            card = Image.new("RGB", (W, H), I._rgb(KEY_COLOR))
            card.paste(edge, (0, 0), mask)
        else:
            card = edge
        ph = ImageTk.PhotoImage(card)
        keep.append(ph)
        cv.create_image(0, 0, image=ph, anchor="nw")
    except Exception:
        cv.create_rectangle(0, 0, W - 1, H - 1, fill=C.LOGIN_BG, outline=C.SIDEBAR_LINE)

    # Logo brand di tengah
    try:
        from elearning import brand
        box = brand.pack_lockup(cv, C.LOGIN_BG, logo_size=(250, 84), mark_size=72,
                                font_size=15, side="top", serif=True)
        cv.create_window(W / 2, 122, window=box)
    except Exception:
        cv.create_text(W / 2, 122, text="M3DAN Studios", fill=C.TEXT,
                       font=(C.SERIF, 20, "bold"))

    # Loading bar biru muda (animasi bolak-balik, lihat _pump)
    x0, x1, y = W / 2 - BAR_W / 2, W / 2 + BAR_W / 2, 214
    _round_bar(cv, x0, y, x1, BAR_TRACK, "track")
    root._bar = (cv, x0, x1, y)
    _draw_bar(root)
    root._splash_images = keep   # simpan referensi supaya gambar tidak hilang


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
        try:
            _build(root, C)
        except Exception:   # tampilan cadangan paling sederhana
            for w in root.winfo_children():
                w.destroy()
            root.configure(bg=C.LOGIN_BG)
            tk.Label(root, text=C.APP_NAME, bg=C.LOGIN_BG, fg=C.TEXT,
                     font=(C.FONT, 13, "bold")).pack(expand=True)

        root.deiconify()
        root.update()                        # paksa tergambar sebelum impor berat
        setattr(sys, _KEY, root)
        if _HOOK not in sys.meta_path:
            sys.meta_path.insert(0, _HOOK)   # animasi tetap jalan selama impor berat
        root.after(16, _tick)
    except Exception:
        setattr(sys, _KEY, None)


def close():
    """Tutup splash (aman dipanggil berkali-kali)."""
    root = getattr(sys, _KEY, None)
    setattr(sys, _KEY, None)
    try:
        sys.meta_path.remove(_HOOK)
    except ValueError:
        pass
    if root is not None:
        try:
            root.destroy()
        except Exception:
            pass
        try:   # gambar logo milik jendela splash ikut hilang: jangan dipakai ulang
            from elearning import brand
            brand._cache.clear()
        except Exception:
            pass
