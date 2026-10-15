"""Mode mengambang: saat Blender terbuka, aplikasi mengecil jadi ikon kecil di atas Blender.

- Ikon muncul di pojok kiri-bawah jendela Blender (perkiraan: di atas header Timeline /
  Playback pada tata letak bawaan Blender). Murid bisa menggesernya; posisi diingat
  relatif terhadap jendela Blender, jadi ikut bergerak kalau jendela Blender dipindah.
- Ikon tanpa bingkai: hanya bentuk ikon yang terlihat (latar dibuat transparan oleh Windows).
- Klik ikon  ->  aplikasi kembali penuh (maximize). Ikon tidak muncul lagi sampai murid
  menekan tombol Blender di sidebar lagi (atau Blender ditutup lalu dibuka lagi).
- Blender ditutup  ->  aplikasi otomatis kembali penuh.
- Aktif untuk semua murid (trial, superkids, dewasa), tidak untuk guru/admin. Tanpa add-on:
  aplikasi hanya memantau jendela Blender.
"""

import tkinter as tk

from elearning import blender_icon
from elearning import blender_launcher as BL
from elearning import config as C

ICON = blender_icon.SIZE_EXPANDED   # 56 px: sama dengan foto murid & tombol Blender di sidebar
TILE = ICON          # jendela ikon = persis seukuran gambar, tanpa bingkai
DEFAULT_OFFSET = (18, 102)  # (jarak dari kiri, jarak dari bawah jendela Blender)
KEY = "#010203"      # warna yang dibuat transparan oleh Windows (tidak dipakai di gambar)
VIEWPORT_GRAY = (63, 63, 63)   # abu-abu latar viewport 3D Blender (tema bawaan)
TICK_MS = 500
MISSING_LIMIT = 4    # ~2 detik tanpa jendela Blender = dianggap sudah ditutup
DRAG_THRESHOLD = 5   # geser lebih kecil dari ini dianggap klik
_KEY = "float_offset"


def _hex_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _load_app_icon():
    """Gambar RGBA ikon aplikasi dari icon.ico (sama seperti ikon di judul jendela)."""
    from PIL import Image
    with Image.open(C.ICON_PATH) as ico:
        sizes = sorted(s for s in ico.info.get("sizes", []) if s[0] >= ICON)
        if sizes:
            return ico.ico.getimage(sizes[0]).convert("RGBA")
        return ico.convert("RGBA")


def _icon_image(icon_rgba, hover=False):
    """Ikon tanpa bingkai. Tepi ikon yang membulat dicampur dengan abu-abu viewport Blender
    (bukan dengan warna transparan), jadi tepinya halus dan tidak ada garis tepi gelap.
    Hanya piksel yang benar-benar kosong yang dibuat transparan.

    Hanya memakai Image dan ImageTk dari Pillow (modul lain, mis. ImageEnhance, tidak ikut
    terbungkus di dalam .exe)."""
    from PIL import Image, ImageTk
    resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
    try:
        small = icon_rgba.convert("RGBa").resize((ICON, ICON), resample).convert("RGBA")
    except Exception:
        small = icon_rgba.resize((ICON, ICON), resample)
    alpha = small.getchannel("A")
    rgb = small.convert("RGB")
    if hover:   # sedikit lebih terang saat kursor di atasnya
        rgb = rgb.point(lambda v: min(255, int(v * 1.15)))
    out = Image.new("RGB", (ICON, ICON), VIEWPORT_GRAY)
    out.paste(rgb, (0, 0), alpha)
    empty = alpha.point(lambda v: 255 if v < 8 else 0)
    out.paste(_hex_rgb(KEY), (0, 0, ICON, ICON), empty)
    return ImageTk.PhotoImage(out)


class FloatingIcon(tk.Toplevel):
    """Kotak kecil tanpa bingkai, selalu di atas, bisa digeser; klik = kembali ke aplikasi."""

    def __init__(self, app, on_click, on_moved):
        super().__init__(app)
        self.on_click, self.on_moved = on_click, on_moved
        self.overrideredirect(True)
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass
        self.configure(bg=KEY)
        try:   # Windows: warna KEY menjadi transparan (hanya bentuk ikon yang terlihat)
            self.attributes("-transparentcolor", KEY)
        except Exception as exc:
            C.log(f"Ikon mengambang: transparentcolor gagal: {exc!r}")
        self.geometry(f"{TILE}x{TILE}+0+0")
        self.withdraw()
        self.dragging = False
        self._grab = (0, 0)
        self._start = (0, 0)
        self._imgs = None

        try:
            icon = _load_app_icon()
            normal = _icon_image(icon)
            try:
                hover = _icon_image(icon, hover=True)
            except Exception as exc:   # efek hover gagal: ikon tetap tampil normal
                C.log(f"Ikon mengambang: efek hover gagal: {exc!r}")
                hover = normal
            self._imgs = (normal, hover)
        except Exception as exc:
            C.log(f"Ikon mengambang: gambar gagal dibuat: {exc!r}")

        if self._imgs:
            self.label = tk.Label(self, image=self._imgs[0], bg=KEY, bd=0,
                                  highlightthickness=0, cursor="hand2")
        else:   # cadangan: kotak oranye bertuliskan B
            self.label = tk.Label(self, text="B", bg=C.ACCENT, fg="white", cursor="hand2",
                                  font=(C.FONT, 18, "bold"))
        self.label.place(x=0, y=0, width=TILE, height=TILE)
        self.label.bind("<ButtonPress-1>", self._press)
        self.label.bind("<B1-Motion>", self._motion)
        self.label.bind("<ButtonRelease-1>", self._release)
        self.label.bind("<Enter>", lambda e: self._hover(1))
        self.label.bind("<Leave>", lambda e: self._hover(0))

    def _hover(self, i):
        if self._imgs:
            self.label.config(image=self._imgs[i])

    def _press(self, e):
        self._grab = (e.x_root - self.winfo_x(), e.y_root - self.winfo_y())
        self._start = (e.x_root, e.y_root)
        self.dragging = False

    def _motion(self, e):
        if not self.dragging and (abs(e.x_root - self._start[0]) > DRAG_THRESHOLD
                                  or abs(e.y_root - self._start[1]) > DRAG_THRESHOLD):
            self.dragging = True
        if self.dragging:
            self.geometry(f"+{e.x_root - self._grab[0]}+{e.y_root - self._grab[1]}")

    def _release(self, e):
        if self.dragging:
            self.dragging = False
            self.on_moved(self.winfo_x(), self.winfo_y())
        else:
            self.on_click()

    def move_to(self, x, y):
        if not self.dragging:
            self.geometry(f"+{int(x)}+{int(y)}")

    def show(self):
        if self.state() == "withdrawn":
            self.deiconify()
        self.attributes("-topmost", True)
        self.lift()

    def hide(self):
        if self.state() != "withdrawn":
            self.withdraw()


class BlenderFloat:
    """Pemantau jendela Blender + pengatur mode mengambang (dipakai oleh App)."""

    def __init__(self, app):
        self.app = app
        self.active = False
        self.icon = None
        self._seen = False       # jendela utama Blender sudah terlihat pada pemeriksaan terakhir
        self._missing = 0
        self._info = None
        self._job = None
        self._offset = None

    # --- dipanggil oleh App / layar kursus ---------------------------------
    def start(self):
        """Akun trial masuk. Blender yang SUDAH terbuka tidak langsung membuat mengambang."""
        self.active = True
        info = BL.blender_window_info()
        self._seen = bool(info and not info.get("minimized"))
        self._schedule()

    def stop(self):
        self.active = False
        if self._job is not None:
            try:
                self.app.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        self._destroy_icon()

    def enter(self):
        """Tombol Blender di sidebar ditekan: kalau jendela Blender sudah ada, mengambang sekarang;
        kalau belum (masih dimuat), mengambang begitu jendelanya muncul."""
        if not self.active or self.icon is not None:
            return
        info = BL.blender_window_info()
        if not info or info.get("minimized"):
            self._seen = False
            return
        self._float(info)

    # --- internal -----------------------------------------------------------
    def _schedule(self):
        self._job = self.app.after(TICK_MS, self._tick)

    def _tick(self):
        self._job = None
        if not self.active:
            return
        try:
            info = BL.blender_window_info()
            self._info = info
            if self.icon is None:
                self._tick_full(info)
            else:
                self._tick_floating(info)
        except Exception as exc:
            C.log(f"Mode mengambang: {exc!r}")
        if self.active:
            self._schedule()

    def _tick_full(self, info):
        if info and not info.get("minimized"):
            if not self._seen:
                self._seen = True
                self._float(info)
        elif info is None and not BL.window_exists():
            self._seen = False

    def _tick_floating(self, info):
        if info is None:
            if BL.window_exists():
                self._missing = 0          # Blender masih memuat / ada jendela lain
            else:
                self._missing += 1
                if self._missing >= MISSING_LIMIT:
                    self._seen = False
                    self._leave()          # Blender ditutup: kembali ke aplikasi penuh
            return
        self._missing = 0
        if info.get("minimized"):
            self.icon.hide()
            return
        self.icon.move_to(*self._position(info))
        self.icon.show()

    def _get_offset(self):
        if self._offset is None:
            saved = BL.load_setting(_KEY)
            ok = (isinstance(saved, list) and len(saved) == 2
                  and all(isinstance(v, (int, float)) for v in saved))
            self._offset = tuple(saved) if ok else DEFAULT_OFFSET
        return self._offset

    def _position(self, info):
        dx, dy = self._get_offset()
        dx = max(0, min(dx, info["w"] - TILE))
        dy = max(0, min(dy, info["h"] - TILE))
        return info["x"] + dx, info["y"] + info["h"] - dy - TILE

    def _float(self, info):
        self._seen = True
        self._missing = 0
        self.icon = FloatingIcon(self.app, on_click=self._leave, on_moved=self._moved)
        self.icon.move_to(*self._position(info))
        self.icon.show()
        self.app.iconify()
        hwnd = info.get("hwnd")
        if hwnd:   # pastikan Blender yang aktif setelah aplikasi diminimize
            self.app.after(200, lambda: BL.bring_to_front(hwnd))

    def _moved(self, x, y):
        info = self._info
        if not info or info.get("minimized"):
            return
        dx = max(0, min(x - info["x"], info["w"] - TILE))
        dy = max(0, min(info["y"] + info["h"] - (y + TILE), info["h"] - TILE))
        self._offset = (int(dx), int(dy))
        BL.save_setting(_KEY, [int(dx), int(dy)])

    def _destroy_icon(self):
        if self.icon is not None:
            try:
                self.icon.destroy()
            except Exception:
                pass
            self.icon = None

    def _leave(self):
        """Kembali ke aplikasi penuh (maximize). Blender dibiarkan terbuka."""
        self._destroy_icon()
        self._missing = 0
        try:
            self.app.deiconify()
            self.app.state("zoomed")
            self.app.lift()
            self.app.focus_force()
        except Exception as exc:
            C.log(f"Mode mengambang: gagal memulihkan jendela: {exc!r}")
