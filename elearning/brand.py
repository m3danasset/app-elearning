"""Logo brand M3DAN Studios, dipakai splash, layar login, dan sidebar.

- Logo versi FULL: assets\\logo.png (PNG transparan). Ganti file itu untuk ganti logo,
  tanpa build ulang.
- Logo kotak (ikon): tertanam di floating_logo.py, selalu ada.
Kalau logo.png tidak ada, tampilan memakai logo kotak + tulisan BRAND_NAME.

Sengaja ringan (hanya Pillow + Tk) supaya bisa dipakai splash sebelum modul berat dimuat.
"""

from elearning import config as C
from elearning import floating_logo

BRAND_NAME = "M3DAN Studios"

_cache = {}


def _rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def fit_image(img, max_w, max_h, bg):
    """Kecilkan gambar RGBA agar muat max_w x max_h, lalu campur dengan warna latar (RGB)."""
    from PIL import Image
    bbox = img.getchannel("A").getbbox()   # buang ruang kosong transparan di sekeliling logo
    if bbox:
        img = img.crop(bbox)
    scale = min(max_w / img.width, max_h / img.height, 1.0)
    size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
    try:   # alpha ter-premultiply: tepi tidak bergaris putih
        img = img.convert("RGBa").resize(size, resample).convert("RGBA")
    except Exception:
        img = img.resize(size, resample)
    base = Image.new("RGBA", size, _rgb(bg) + (255,))
    base.alpha_composite(img)
    return base.convert("RGB")


def logo(max_w=150, max_h=30, bg=C.SIDEBAR):
    """PhotoImage logo full dari assets\\logo.png, atau None kalau tidak ada."""
    key = ("logo", max_w, max_h, bg)
    if key not in _cache:
        ph = None
        try:
            from PIL import Image, ImageTk
            with Image.open(C.resource_path("assets", "logo.png")) as f:
                img = f.convert("RGBA")
            ph = ImageTk.PhotoImage(fit_image(img, max_w, max_h, bg))
        except Exception as exc:
            C.log(f"Logo full (assets\\logo.png) tidak dipakai: {exc!r}")
        _cache[key] = ph
    return _cache[key]


def mark(size=28, bg=C.SIDEBAR):
    """PhotoImage logo kotak M3DAN, atau None."""
    key = ("mark", size, bg)
    if key not in _cache:
        ph = None
        try:
            from PIL import ImageTk
            img = floating_logo.load()
            if img is not None:
                ph = ImageTk.PhotoImage(fit_image(img, size, size, bg))
        except Exception as exc:
            C.log(f"Logo kotak gagal: {exc!r}")
        _cache[key] = ph
    return _cache[key]


def pack_lockup(parent, bg, logo_size=(150, 30), mark_size=26, font_size=13, side="left",
                serif=False):
    """Pasang logo full; kalau tidak ada: logo kotak + nama brand. Kembalikan frame-nya."""
    import tkinter as tk
    box = tk.Frame(parent, bg=bg)
    full = logo(logo_size[0], logo_size[1], bg)
    if full is not None:
        tk.Label(box, image=full, bg=bg, bd=0).pack()
        return box
    m = mark(mark_size, bg)
    family = C.SERIF if serif else C.FONT
    if side == "top":   # logo kotak di atas, nama di bawahnya (splash / login)
        if m is not None:
            tk.Label(box, image=m, bg=bg, bd=0).pack()
        tk.Label(box, text=BRAND_NAME, bg=bg, fg=C.TEXT,
                 font=(family, font_size, "bold")).pack(pady=(10, 0))
    else:
        if m is not None:
            tk.Label(box, image=m, bg=bg, bd=0).pack(side="left", padx=(0, 8))
        tk.Label(box, text=BRAND_NAME, bg=bg, fg=C.TEXT,
                 font=(family, font_size, "bold")).pack(side="left")
    return box
