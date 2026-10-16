"""Mode mengambang: saat Blender terbuka, aplikasi mengecil jadi ikon kecil di atas Blender.

- Ikon muncul di pojok kiri-bawah jendela Blender (perkiraan: di atas header Timeline /
  Playback pada tata letak bawaan Blender). Murid bisa menggesernya; posisi diingat
  relatif terhadap jendela Blender, jadi ikut bergerak kalau jendela Blender dipindah.
- Ikon tanpa bingkai: hanya bentuk ikon yang terlihat (latar dibuat transparan oleh Windows).
- Ikon hanya tampil saat aplikasi e-learning TIDAK sedang dibuka: begitu jendela aplikasi aktif
  (mis. dibuka lewat taskbar / Alt+Tab), ikon disembunyikan supaya tidak menimpa aplikasi, dan
  muncul lagi saat murid kembali ke Blender.
- Klik ikon  ->  aplikasi kembali penuh (maximize). Ikon tidak muncul lagi sampai murid
  menekan tombol Blender di sidebar lagi (atau Blender ditutup lalu dibuka lagi).
- Blender ditutup  ->  aplikasi otomatis kembali penuh.
- MINI PLAYER: bersamaan dengan ikon, muncul pemutar video kecil (bisa di-resize) tepat di sebelah
  ikon, melanjutkan pelajaran yang sedang dibuka (lihat mini_player.py). Klik kanan pada ikon =
  sembunyikan (dijeda) / munculkan mini player. Klik ikon untuk kembali: video di aplikasi melanjutkan dari posisi
  terakhir di mini player. Kalau murid menekan tombol Blender saat tidak sedang di halaman
  Materi (mis. di Portfolio), hanya ikon yang muncul.
- Aktif untuk semua murid (trial, superkids, dewasa), tidak untuk guru/admin. Tanpa add-on:
  aplikasi hanya memantau jendela Blender.
"""

import tkinter as tk

from elearning import blender_icon
from elearning import blender_launcher as BL
from elearning import config as C
from elearning import floating_logo
from elearning.ui.mini_player import MiniPlayer
from elearning.ui.play_overlay import no_activate

ICON = 40            # ikon minimalis: kecil supaya tidak menghalangi layar Blender (bawaan lama 56)
TILE = ICON          # jendela ikon = persis seukuran gambar, tanpa bingkai
DEFAULT_OFFSET = (0, 22)    # posisi awal: pojok kiri-bawah jendela Blender, tepat di atas status bar
IDLE_ALPHA = 0.4            # ikon samar kalau kursor tidak di atasnya
KEY = "#010203"      # warna yang dibuat transparan oleh Windows (tidak dipakai di gambar)
VIEWPORT_GRAY = (63, 63, 63)   # abu-abu latar viewport 3D Blender (tema bawaan)
TICK_MS = 250
MISSING_LIMIT = 8    # ~2 detik tanpa jendela Blender = dianggap sudah ditutup
DRAG_THRESHOLD = 5   # geser lebih kecil dari ini dianggap klik
_KEY = "float_offset_v3"


def _hex_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _load_app_icon():
    """Gambar RGBA ikon aplikasi dari icon.ico (sama seperti ikon di judul jendela)."""
    from PIL import Image
    logo = floating_logo.load()
    if logo is not None:
        return logo
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

    def __init__(self, app, on_click, on_moved, on_toggle_mini=None, on_dragging=None,
                 get_bounds=None):
        super().__init__(app)
        self.get_bounds = get_bounds        # () -> (kiri, atas, kanan, bawah) area yang boleh dipakai
        self.on_click, self.on_moved = on_click, on_moved
        self.on_toggle_mini, self.on_dragging = on_toggle_mini, on_dragging
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
        no_activate(self)   # ikon tidak merebut fokus dan tidak muncul di Alt+Tab
        # Posisi ikon berubah dari sebab apa pun (digeser, dipindah program) -> mini player ikut
        self.bind("<Configure>", self._configured)
        self.dragging = False
        self._fade(False)
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
        self.label.bind("<Button-3>", lambda e: self.on_toggle_mini and self.on_toggle_mini())
        self.label.bind("<Enter>", lambda e: self._hover(1))
        self.label.bind("<Leave>", lambda e: self._hover(0))

    def _configured(self, e):
        if e.widget is self and self.on_dragging is not None and self.winfo_viewable():
            try:
                self.on_dragging(self.winfo_x(), self.winfo_y(), False)
            except Exception as exc:
                C.log(f"Ikon mengambang: mini player gagal mengikuti: {exc!r}")

    def _hover(self, i):
        if self._imgs:
            self.label.config(image=self._imgs[i])
        self._fade(i or self.dragging)

    def _fade(self, full):
        """Samar (low opacity) kalau kursor tidak di atas ikon; penuh saat hover / digeser."""
        try:
            self.attributes("-alpha", 1.0 if full else IDLE_ALPHA)
        except Exception:
            pass

    def _press(self, e):
        self._grab = (e.x_root - self.winfo_x(), e.y_root - self.winfo_y())
        self._start = (e.x_root, e.y_root)
        self.dragging = False

    def _motion(self, e):
        if not self.dragging and (abs(e.x_root - self._start[0]) > DRAG_THRESHOLD
                                  or abs(e.y_root - self._start[1]) > DRAG_THRESHOLD):
            self.dragging = True
            self._fade(True)
        if self.dragging:
            x, y = e.x_root - self._grab[0], e.y_root - self._grab[1]
            b = self.get_bounds() if self.get_bounds is not None else None
            if b:                            # ikon tidak boleh keluar dari layar / jendela Blender
                x = max(b[0], min(x, b[2] - TILE))
                y = max(b[1], min(y, b[3] - TILE))
            self.geometry(f"+{x}+{y}")
            if self.on_dragging is not None:
                try:
                    self.on_dragging(x, y, False)   # mini player ikut bergeser
                except Exception as exc:
                    C.log(f"Ikon mengambang: mini player gagal mengikuti: {exc!r}")

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
        self.mini = None         # MiniPlayer di sebelah ikon (None kalau tidak ada pelajaran yang dibuka)
        self._seen = False       # jendela utama Blender sudah terlihat pada pemeriksaan terakhir
        self._missing = 0
        self._info = None
        self._job = None
        self._offset = None
        for seq in ("<FocusIn>", "<Map>", "<Unmap>"):   # sembunyikan ikon segera, tanpa menunggu tick
            try:
                app.bind(seq, self._on_app_event, add="+")
            except Exception:
                pass

    def _blender_in_front(self):
        """True kalau Blender yang paling depan. Dibaca dari urutan tumpukan jendela (langsung benar
        setelah Alt+Tab, tidak menunggu fokus pindah); kalau tidak bisa, jatuh ke jendela aktif.
        Jendela lain yang menutupi Blender (aplikasi e-learning, browser, layar Alt+Tab) = False."""
        bh = (self._info or {}).get("hwnd")
        cov = BL.blender_covered(bh, BL.root_of(self.app.winfo_id())) if bh else None
        if cov is not None:
            return not cov
        fgb = BL.foreground_is_blender()
        return True if fgb is None else bool(fgb)

    def _app_open(self):
        """True kalau jendela aplikasi e-learning sedang terbuka di depan (bukan di-minimize).

        Tidak lagi bergantung pada fokus: setelah Alt+Tab fokus bisa terlambat pindah (baru setelah
        diklik), jadi keadaan jendela dan urutan tumpukannya dibaca langsung dari Windows."""
        wid = self.app.winfo_id()
        st = BL.window_state(wid)
        if st in ("iconic", "hidden"):
            return False
        bh = (self._info or {}).get("hwnd")
        if st == "visible" and bh:
            above = BL.z_above(BL.root_of(wid), bh)
            if above is not None:
                return bool(above)
        fg = BL.is_foreground(wid)
        if fg is not None:
            return bool(fg)
        try:                                     # bukan Windows / tidak bisa dibaca
            return self.app.state() not in ("iconic", "withdrawn")
        except Exception:
            return False

    def _on_app_event(self, event):
        if event.widget is self.app and self.icon is not None:
            self._apply_visibility()

    def _apply_visibility(self):
        if self.icon is None:
            return
        info = self._info
        if self._app_open() or not self._blender_in_front() or not info or info.get("minimized"):
            self._hide_float()
        else:
            self._show_float(info)

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
        if info.get("minimized") or self._app_open() or not self._blender_in_front():
            # Blender di-minimize, aplikasi e-learning terbuka, atau jendela lain di depan
            # (Alt+Tab, browser, ...): ikon + mini player hanya tampil saat Blender yang di depan.
            self._hide_float()
            return
        self._show_float(info)

    # --- ikon + mini player tampil / sembunyi bersama ------------------------
    def _hide_float(self):
        if self.icon is not None:
            self.icon.hide()
        if self.mini is not None:
            self.mini.hide()        # video dijeda saat disembunyikan

    def _show_float(self, info):
        if self.icon.dragging:      # sedang digeser: ikuti posisi nyata ikon
            x, y = self.icon.winfo_x(), self.icon.winfo_y()
        else:
            x, y = self._position(info)
            self.icon.move_to(x, y)
        self.icon.show()
        self._place_mini(info, x, y)

    def _place_mini(self, info, x, y, raise_=True):
        if self.mini is None or not info or info.get("minimized"):
            return
        self.mini.place_beside(x, y, TILE, self._bounds(info))
        if raise_:
            self.mini.show()

    def _icon_dragging(self, x, y, raise_=True):
        self._place_mini(self._info, x, y, raise_)

    def _mini_drag(self, x, y):
        """Bilah judul mini player digeser: ikon dan mini player bergeser bersama."""
        if self.icon is None:
            return
        self.icon.geometry(f"+{int(x)}+{int(y)}")
        self._place_mini(self._info, int(x), int(y), False)

    def _mini_drag_end(self):
        if self.icon is not None:
            self._moved(self.icon.winfo_x(), self.icon.winfo_y())

    def _icon_anchor(self):
        return (self.icon.winfo_x(), self.icon.winfo_y()) if self.icon is not None else None

    def _toggle_mini(self):
        """Klik kanan pada ikon: mini player dijeda + disembunyikan; klik kanan lagi = muncul lagi."""
        m = self.mini
        if m is None:
            return
        if m.closed:
            m.reopen()
        else:
            m.close()       # menyembunyikan + menjeda
        self._place_mini(self._info, self.icon.winfo_x(), self.icon.winfo_y())

    # --- mini player: pelajaran yang sedang dibuka ----------------------------
    def _lesson_state(self):
        """Pemutar pelajaran yang sedang dibuka di aplikasi, atau None kalau tidak ada video."""
        p = getattr(self.app, "_lesson_player", None)
        try:
            if p is None or not p.winfo_exists() or not p.has_video or not p._path:
                return None
            panel = p.master
            items, index = panel.items, panel.index
            title = panel.title.cget("text")
        except Exception:
            return None
        return {"player": p, "panel": panel, "path": p._path, "subs": p._subs,
                "pos": p.pos, "playing": p.playing, "title": title, "index": index,
                "count": len(items), "color": p.color}

    def _open_mini(self, info, x, y):
        """Buat mini player di sebelah ikon (kalau ada pelajaran yang sedang dibuka)."""
        self._destroy_mini()
        st = self._lesson_state()
        if st is None:
            return
        try:
            st["player"]._pause()   # pemutar utama berhenti; mini player melanjutkan
            self.mini = MiniPlayer(self.app, color=st["color"], on_nav=self._mini_nav,
                                   on_drag=self._mini_drag, on_drag_end=self._mini_drag_end,
                                   get_anchor=self._icon_anchor,
                                   on_fullscreen=self._mini_fullscreen)
            bounds = (info["x"], info["y"], info["x"] + info["w"], info["y"] + info["h"])
            self.mini.place_beside(x, y, TILE, bounds)
            self.mini.open(st["path"], st["subs"], st["title"], start=st["pos"],
                           play=False, can_prev=st["index"] > 0,
                           can_next=st["index"] < st["count"] - 1)
            self.mini.close()       # bawaan: tersembunyi + dijeda; klik kanan ikon untuk memunculkan
        except Exception as exc:
            C.log(f"Mini player gagal dibuat: {exc!r}")
            self._destroy_mini()

    def _mini_nav(self, delta):
        """Tombol sebelumnya / selanjutnya di mini player: pelajaran di aplikasi ikut berganti."""
        st = self._lesson_state()
        if st is None or self.mini is None:
            return
        idx = st["index"] + delta
        if not 0 <= idx < st["count"]:
            return
        try:
            st["panel"].select(idx)         # aplikasi ikut pindah (sorotan sidebar, progres)
            item = st["panel"].items[idx]
            if not item["path"]:
                return
            self.mini.load(item["path"], item.get("subs", ()), item["label"], start=0.0,
                           play=True, can_prev=idx > 0, can_next=idx < st["count"] - 1)
        except Exception as exc:
            C.log(f"Mini player: gagal pindah pelajaran: {exc!r}")

    def _destroy_mini(self):
        if self.mini is not None:
            try:
                self.mini.destroy()
            except Exception:
                pass
            self.mini = None

    def _mini_fullscreen(self):
        """Tombol layar penuh di mini player: kembali ke aplikasi, video layar penuh, lanjut."""
        self._leave(fullscreen=True)

    def _resume_in_app(self, resume, fullscreen=False):
        """Aplikasi kembali penuh: video di aplikasi melanjutkan dari posisi di mini player."""
        pos, playing = resume
        st = self._lesson_state()
        if st is None or pos is None:
            return
        p = st["player"]
        try:
            if pos > 0.5 and p.engine is not None:
                p.engine.seek(pos, exact=True)
                p.pos = pos
            if fullscreen:
                p.toggle_fullscreen(True)
            if playing:
                self.app.after(900 if fullscreen else 350, lambda: self._play_if_visible(p))
        except Exception as exc:
            C.log(f"Mini player: gagal melanjutkan di aplikasi: {exc!r}")

    def _play_if_visible(self, p):
        try:
            if p.winfo_exists() and p.winfo_viewable() and not p.playing:
                p.toggle()
        except Exception:
            pass

    def _get_offset(self):
        if self._offset is None:
            saved = BL.load_setting(_KEY)
            ok = (isinstance(saved, list) and len(saved) == 2
                  and all(isinstance(v, (int, float)) for v in saved))
            self._offset = tuple(saved) if ok else DEFAULT_OFFSET
        return self._offset

    def _bounds(self, info=None):
        """Area tempat ikon + mini player boleh berada: jendela Blender dipotong oleh area kerja
        monitornya (jendela Blender bisa lebih besar dari layar), supaya ikon tidak terpotong."""
        info = info or self._info
        if not info or info.get("minimized"):
            return None
        b = (info["x"], info["y"], info["x"] + info["w"], info["y"] + info["h"])
        mon = BL.monitor_work_area(info.get("hwnd"))
        if mon is None:
            try:
                mon = (0, 0, self.app.winfo_screenwidth(), self.app.winfo_screenheight())
            except Exception:
                mon = None
        if mon:
            c = (max(b[0], mon[0]), max(b[1], mon[1]), min(b[2], mon[2]), min(b[3], mon[3]))
            if c[2] - c[0] >= TILE and c[3] - c[1] >= TILE:
                return c
        return b

    def _position(self, info):
        dx, dy = self._get_offset()
        dx = max(0, min(dx, info["w"] - TILE))
        dy = max(0, min(dy, info["h"] - TILE))
        x, y = info["x"] + dx, info["y"] + info["h"] - dy - TILE
        b = self._bounds(info)
        if b:                       # selalu terlihat penuh, tidak terpotong tepi monitor
            x = max(b[0], min(x, b[2] - TILE))
            y = max(b[1], min(y, b[3] - TILE))
        return x, y

    def _float(self, info):
        self._seen = True
        self._info = info
        self._missing = 0
        self.icon = FloatingIcon(self.app, on_click=self._leave, on_moved=self._moved,
                                 on_toggle_mini=self._toggle_mini,
                                 on_dragging=self._icon_dragging,
                                 get_bounds=self._bounds)
        x, y = self._position(info)
        self.icon.move_to(x, y)
        self.icon.show()
        self._open_mini(info, x, y)     # pemutar kecil di sebelah ikon (sebelum aplikasi diminimize)
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
        self._destroy_mini()
        if self.icon is not None:
            try:
                self.icon.destroy()
            except Exception:
                pass
            self.icon = None

    def _leave(self, fullscreen=False):
        """Kembali ke aplikasi penuh (maximize). Blender dibiarkan terbuka."""
        resume = self.mini.resume_state() if self.mini is not None else None
        self._destroy_icon()
        self._missing = 0
        try:
            self.app.deiconify()
            self.app.state("zoomed")
            self.app.lift()
            self.app.focus_force()
        except Exception as exc:
            C.log(f"Mode mengambang: gagal memulihkan jendela: {exc!r}")
        if resume is not None:
            self.app.after(250, lambda: self._resume_in_app(resume, fullscreen))
