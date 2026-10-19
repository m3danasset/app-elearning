"""Jendela Dev (Ctrl KANAN + Shift KANAN + Backspace, di layar mana pun).

Dibuka setelah PIN Dev benar (DevPinDialog; yang disimpan hanya hash-nya, DEV_PIN_HASH).
Gaya Settings Claude (tanpa animasi): jendela bersudut bulat, navigasi kiri (Search, Akun,
halaman Settings), isi kanan berupa baris judul + keterangan | kontrol. Selalu di atas.
- Akun     : cari akun (admin, guru, murid, trial) lalu masuk tanpa PIN.
- Settings : tampilan login, warna aksen, fitur on/off, nilai isian (data\\app_settings.json).
"""

import time
import tkinter as tk

from elearning import app_settings as S
from elearning import config as C

BG, FG, MUTED, FIELD = "#1f1e1d", "#ececea", "#9c998f", "#262523"
FONT = (C.FONT, 9)
BOLD = (C.FONT, 9, "bold")
MONO = ("Consolas", 9)            # huruf lebar tetap: kolom Jenis | ID | Nama rata
MONO_B = ("Consolas", 9, "bold")
FILTERS = ("Semua", "Admin", "Guru", "Trial", "Dewasa", "SUPERKIDS", "Murid")
FILTER_KIND = {"Semua": None, "Murid": ("adult", "kids"), "Dewasa": ("adult",),
               "SUPERKIDS": ("kids",), "Guru": ("teacher",), "Admin": ("admin",),
               "Trial": ("trial",)}
SORTS = ("Nama", "ID")             # urutan DI DALAM tiap jenis
KIND_ORDER = ("admin", "teacher", "trial", "adult", "kids")   # selalu paling depan: admin dulu
LOGIN_LABELS = (("carousel", "Carousel + video"), ("rows3", "Carousel 3 baris"),
                ("video", "Video saja"))

_open = {"win": None}


def dev_combo():
    """True kalau Ctrl KANAN + Shift KANAN ditekan dan Ctrl / Shift KIRI tidak (dibaca langsung
    dari Windows, jadi berlaku di layar mana pun)."""
    try:
        import ctypes
        k = ctypes.windll.user32.GetAsyncKeyState
        down = lambda vk: bool(k(vk) & 0x8000)
        return down(0xA3) and down(0xA1) and not down(0xA2) and not down(0xA0)
    except Exception:
        return False


def install_shortcut(app):
    """Ctrl kanan + Shift kanan + Backspace = jendela Dev (semua layar)."""
    def on_backspace(_e):
        if dev_combo():
            open_dev(app)
            return "break"
        return None
    app.bind_all("<KeyPress-BackSpace>", on_backspace, add="+")


# PIN Dev: hanya hash yang disimpan (bukan teks PIN). Ganti PIN: hitung _pin_hash("pinbaru").
DEV_PIN_HASH = "2c241116be877d65"
PIN_TRIES = 5          # salah sekian kali berturut-turut -> dikunci sebentar
PIN_LOCK_S = 60


def _pin_hash(text):
    """FNV-1a 64 bit bergaram, 2000 putaran (tanpa hashlib: hanya modul yang pasti ada di .exe)."""
    h = 0xCBF29CE484222325
    data = ("m3dan-dev:" + text).encode("utf-8")
    for _ in range(2000):
        for b in data:
            h = ((h ^ b) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


_pin = {"win": None, "fails": 0, "locked_until": 0.0}


# --- posisi jendela Dev (tab, cari, gulir Settings): diingat sampai PC di-reboot ------------
def _boot_time():
    """Waktu PC menyala (detik epoch). GetTickCount64 ikut menghitung sleep / hibernate."""
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.GetTickCount64.restype = ctypes.c_ulonglong
        return time.time() - k.GetTickCount64() / 1000.0
    except Exception:
        return 0.0


def _ui_path():
    import os
    return os.path.join(C.DATA_DIR, "dev_ui.json")


_ui = None     # isi dev_ui.json di memori


def _ui_state():
    """{"tab", "query", "scroll"} dari sesi PC ini; kosong kalau PC sudah reboot sejak disimpan."""
    global _ui
    if _ui is None:
        import json
        _ui = {}
        try:
            with open(_ui_path(), encoding="utf-8") as f:
                data = json.load(f)
            boot = _boot_time()
            if isinstance(data, dict) and boot and abs(float(data.get("boot", 0)) - boot) < 120:
                _ui = data
        except (OSError, ValueError, TypeError):
            pass
    return _ui


def _ui_save(**kv):
    import json
    import os
    st = _ui_state()
    st.update(kv)
    st["boot"] = _boot_time()
    try:
        os.makedirs(C.DATA_DIR, exist_ok=True)
        tmp = _ui_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f)
        os.replace(tmp, _ui_path())
    except OSError as exc:
        C.log(f"Dev: posisi jendela tidak tersimpan: {exc!r}")


# =============================================================================================
# Gaya Settings Claude (tanpa animasi): panel bersudut bulat, navigasi kiri + baris di kanan
# =============================================================================================
KEY = "#010203"                      # warna kunci: sudut jendela tembus (-transparentcolor)
PANEL = "#1f1e1d"                    # latar panel
NAV_SEL = "#2c2b28"                  # item navigasi terpilih
NAV_HOV = "#262523"
LINE = "#2e2d2a"                     # garis pemisah baris
SEG_BG, SEG_LINE, SEG_ON = "#262523", "#353431", "#3a3935"
DP_CARD = "#262523"                  # kotak ringkasan (mis. Performa: yang dipakai sekarang)
RADIUS = 14
NAV_W = 226


def _pill(w, h, fill, bg, r=8, border=None):
    from elearning.ui import ui_icons as I
    return I.pill(int(w), int(h), fill, bg, r=r, border=border)


def _rounded_window(win, w, h, bg=PANEL, border=LINE):
    """Jendela tanpa bilah judul, sudut membulat (warna kunci tembus). Kembalikan frame isi."""
    win.overrideredirect(True)
    win.configure(bg=KEY)
    rounded = True
    try:
        win.attributes("-transparentcolor", KEY)
    except tk.TclError:
        rounded = False
    cv = tk.Canvas(win, width=w, height=h, bg=KEY if rounded else bg, highlightthickness=0,
                   bd=0)
    cv.pack(fill="both", expand=True)
    win._round_img = _pill(w, h, bg, KEY if rounded else bg, r=RADIUS, border=border)
    if win._round_img is not None:
        cv.create_image(0, 0, image=win._round_img, anchor="nw")
    inner = tk.Frame(cv, bg=bg)
    inset = 6
    cv.create_window(inset, inset, window=inner, anchor="nw", width=w - 2 * inset,
                     height=h - 2 * inset)
    return inner


def _draggable(win, *widgets):
    """Geser jendela tanpa bilah judul dengan menyeret widget ini."""
    def press(e):
        win._drag = (e.x_root - win.winfo_x(), e.y_root - win.winfo_y())

    def move(e):
        d = getattr(win, "_drag", None)
        if d:
            win.geometry(f"+{e.x_root - d[0]}+{e.y_root - d[1]}")
    for w in widgets:
        w.bind("<ButtonPress-1>", press, add="+")
        w.bind("<B1-Motion>", move, add="+")


class Seg(tk.Canvas):
    """Tombol segmen gaya Claude (mis. Small | Medium | Large): satu terpilih."""

    H, PAD = 32, 3

    def __init__(self, master, options, value, command=None, bg=PANEL):
        import tkinter.font as tkfont
        self.opts, self.value, self.command, self._bg = list(options), value, command, bg
        self.f = tkfont.Font(family=C.FONT, size=10)
        self.ws = [self.f.measure(label) + 26 for _v, label in self.opts]
        w = sum(self.ws) + 2 * self.PAD
        super().__init__(master, width=w, height=self.H, bg=bg, highlightthickness=0, bd=0,
                         cursor="hand2")
        self.W = w
        self._hov = None
        self._imgs = []
        self.bind("<Button-1>", self._click)
        self.bind("<Motion>", lambda e: self._hover(self._at(e.x)))
        self.bind("<Leave>", lambda e: self._hover(None))
        self._draw()

    def _at(self, x):
        cx = self.PAD
        for i, w in enumerate(self.ws):
            if cx <= x < cx + w:
                return i
            cx += w
        return None

    def _hover(self, i):
        if i != self._hov:
            self._hov = i
            self._draw()

    def _click(self, e):
        i = self._at(e.x)
        if i is None:
            return
        v = self.opts[i][0]
        if v != self.value:
            self.value = v
            self._draw()
            if self.command is not None:
                self.command(v)

    def set(self, value):
        self.value = value
        self._draw()

    def _draw(self):
        self.delete("all")
        self._imgs = [_pill(self.W, self.H, SEG_BG, self._bg, r=9, border=SEG_LINE)]
        self.create_image(0, 0, image=self._imgs[0], anchor="nw")
        x = self.PAD
        for i, ((v, label), w) in enumerate(zip(self.opts, self.ws)):
            on = v == self.value
            if on or i == self._hov:
                img = _pill(w, self.H - 2 * self.PAD, SEG_ON if on else NAV_HOV, SEG_BG, r=7,
                            border="#4a4945" if on else None)
                self._imgs.append(img)
                self.create_image(x, self.PAD, image=img, anchor="nw")
            self.create_text(x + w / 2, self.H / 2, text=label, font=self.f,
                             fill=FG if on else MUTED)
            x += w


class Swatches(tk.Canvas):
    """Pilihan warna aksen: lingkaran berwarna, yang terpilih bercincin."""

    D, GAP = 26, 10

    def __init__(self, master, options, value, command=None, bg=PANEL):
        self.opts, self.value, self.command, self._bg = list(options), value, command, bg
        w = len(self.opts) * (self.D + self.GAP) - self.GAP + 4
        super().__init__(master, width=w, height=self.D + 4, bg=bg, highlightthickness=0,
                         bd=0, cursor="hand2")
        self._imgs = []
        self.bind("<Button-1>", self._click)
        self._draw()

    def _click(self, e):
        i = int((e.x - 2) // (self.D + self.GAP))
        if 0 <= i < len(self.opts) and self.opts[i][0] != self.value:
            self.value = self.opts[i][0]
            self._draw()
            if self.command is not None:
                self.command(self.value)

    def _draw(self):
        from elearning.ui import ui_icons as I
        self.delete("all")
        self._imgs = []
        D = self.D
        for i, (key, color, _name) in enumerate(self.opts):
            cx, cy = 2 + i * (D + self.GAP) + D / 2, 2 + D / 2
            if key == self.value:             # cincin terang di sekeliling yang terpilih
                ring = _pill(D, D, self._bg, self._bg, r=D / 2, border=FG)
                self._imgs.append(ring)
                self.create_image(cx, cy, image=ring)
            dot = I.dot(color, self._bg, D - 8, (D - 8) / 2 - 0.5)
            self._imgs.append(dot)
            self.create_image(cx, cy, image=dot)


class NavItem(tk.Canvas):
    """Baris navigasi kiri (ikon + teks), sorot saat terpilih / disorot."""

    H = 32

    def __init__(self, master, text, icon, command, width=NAV_W - 24):
        import tkinter.font as tkfont
        super().__init__(master, width=width, height=self.H, bg=PANEL, highlightthickness=0,
                         bd=0, cursor="hand2")
        self.text, self.icon, self.command, self.W = text, icon, command, width
        self.f = tkfont.Font(family=C.FONT, size=10)
        self.active = self._hov = False
        self._imgs = []
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<Enter>", lambda e: self._set_hov(True))
        self.bind("<Leave>", lambda e: self._set_hov(False))
        self._draw()

    def _set_hov(self, on):
        self._hov = on
        self._draw()

    def set_active(self, on):
        if on != self.active:
            self.active = on
            self._draw()

    def _draw(self):
        from elearning.ui import ui_icons as I
        self.delete("all")
        bg = NAV_SEL if self.active else NAV_HOV if self._hov else PANEL
        self._imgs = []
        if bg != PANEL:
            img = _pill(self.W, self.H, bg, PANEL, r=8)
            self._imgs.append(img)
            self.create_image(0, 0, image=img, anchor="nw")
        ic = I.icon(self.icon, FG if self.active else "#c9c6bd", bg, 18) if self.icon else None
        x = 12
        if ic is not None:
            self._imgs.append(ic)
            self.create_image(x, self.H / 2, image=ic, anchor="w")
            x += 28
        self.create_text(x, self.H / 2, text=self.text, anchor="w", font=self.f,
                         fill=FG if self.active else "#d7d4cb")


class CloseBtn(tk.Canvas):
    def __init__(self, master, command):
        super().__init__(master, width=30, height=30, bg=PANEL, highlightthickness=0, bd=0,
                         cursor="hand2")
        self.command = command
        self._imgs = []
        self.bind("<Button-1>", lambda e: command())
        self.bind("<Enter>", lambda e: self._draw(True))
        self.bind("<Leave>", lambda e: self._draw(False))
        self._draw(False)

    def _draw(self, hov):
        from elearning.ui import ui_icons as I
        self.delete("all")
        bg = NAV_HOV if hov else PANEL
        self._imgs = []
        if hov:
            self._imgs.append(_pill(30, 30, bg, PANEL, r=8))
            self.create_image(0, 0, image=self._imgs[-1], anchor="nw")
        ic = I.icon("close", FG if hov else MUTED, bg, 18)
        if ic is not None:
            self._imgs.append(ic)
            self.create_image(15, 15, image=ic)


def _btn(parent, text, command, kind="secondary", bg=PANEL):
    """Tombol gaya Claude: primary (warna aksen), secondary (abu), danger (teks merah)."""
    from elearning.ui.controls import RoundButton
    if kind == "primary":
        return RoundButton(parent, text=text, command=command, bg=C.ACCENT, fg="white",
                           activebackground=C.ACCENT_HOVER, activeforeground="white",
                           font=(C.FONT, 10, "bold"), padx=16, pady=7, radius=8)
    fg = "#ff6b6b" if kind == "danger" else FG
    return RoundButton(parent, text=text, command=command, bg=SEG_ON, fg=fg,
                       activebackground="#45443f", activeforeground=fg,
                       font=(C.FONT, 10, "bold"), padx=16, pady=7, radius=8)


class DevPinDialog(tk.Toplevel):
    """Minta PIN sebelum jendela Dev dibuka (kartu kecil gaya Claude, tanpa animasi).
    Enter = cek, Esc / x / Batal = batal."""

    W, H = 380, 222

    def __init__(self, app):
        from elearning.ui.controls import RoundEntry
        super().__init__(app)
        self.app = app
        self.withdraw()
        self.title("Dev")
        self.attributes("-topmost", True)
        body = _rounded_window(self, self.W, self.H)
        pad = tk.Frame(body, bg=PANEL)
        pad.pack(fill="both", expand=True, padx=22, pady=(16, 18))
        top = tk.Frame(pad, bg=PANEL)
        top.pack(fill="x")
        title = tk.Label(top, text="PIN Dev", bg=PANEL, fg=FG, font=(C.FONT, 13, "bold"),
                         anchor="w")
        title.pack(side="left")
        CloseBtn(top, self.destroy).pack(side="right")
        sub = tk.Label(pad, text="Masukkan PIN untuk membuka jendela Dev.", bg=PANEL,
                       fg=MUTED, font=(C.FONT, 10), anchor="w")
        sub.pack(fill="x", pady=(2, 12))
        self.var = tk.StringVar()
        box = RoundEntry(pad, self.var, show="•", width_chars=24, font=(C.FONT, 11),
                         height=38, fill=SEG_BG, radius=9)
        box.pack(fill="x")
        self.entry = box.entry
        self.msg = tk.Label(pad, text="", bg=PANEL, fg=C.ERROR, font=(C.FONT, 9), anchor="w")
        self.msg.pack(fill="x", pady=(6, 0))
        btns = tk.Frame(pad, bg=PANEL)
        btns.pack(side="bottom", fill="x")
        _btn(btns, "Buka", self._check, "primary").pack(side="right")
        _btn(btns, "Batal", self.destroy).pack(side="right", padx=(0, 8))
        _draggable(self, pad, top, title, sub)
        self.entry.bind("<Return>", lambda e: self._check())
        self.bind("<Escape>", lambda e: self.destroy())
        self.var.trace_add("write", lambda *a: self._limit())
        x = app.winfo_rootx() + max(0, (app.winfo_width() - self.W) // 2)
        y = app.winfo_rooty() + max(0, (app.winfo_height() - self.H) // 3)
        self.geometry(f"{self.W}x{self.H}+{x}+{y}")
        self.deiconify()
        self._locked_tick()
        self.after(10, self._focus)

    def _focus(self):
        try:
            self.lift()
            self.focus_force()
            self.entry.focus_set()
        except tk.TclError:
            pass

    def _limit(self):
        v = self.var.get()
        if len(v) > 32:
            self.var.set(v[:32])

    def _left(self):
        return max(0, int(_pin["locked_until"] - time.monotonic() + 0.999))

    def _locked_tick(self):
        """Selama dikunci: kolom mati + hitung mundur; sesudahnya kolom aktif lagi."""
        left = self._left()
        if left:
            self.entry.config(state="disabled")
            self.msg.config(text=f"Terlalu banyak salah. Coba lagi {left} dtk.")
            self.after(1000, self._locked_tick)
        else:
            self.entry.config(state="normal")
            if _pin["fails"] >= PIN_TRIES:
                _pin["fails"] = 0
                self.msg.config(text="")

    def _check(self):
        if self._left():
            return
        if _pin_hash(self.var.get()) == DEV_PIN_HASH:
            _pin["fails"] = 0
            app = self.app
            self.destroy()
            _show_dev(app)
            return
        _pin["fails"] += 1
        self.var.set("")
        C.log(f"Dev: PIN salah ({_pin['fails']}x)")
        if _pin["fails"] >= PIN_TRIES:
            _pin["locked_until"] = time.monotonic() + PIN_LOCK_S
            self._locked_tick()
        else:
            self.msg.config(text=f"PIN salah ({PIN_TRIES - _pin['fails']} kali lagi).")

    def destroy(self):
        _pin["win"] = None
        super().destroy()



def open_dev(app):
    """Shortcut Dev: kalau jendela Dev sudah terbuka, munculkan; kalau belum, minta PIN dulu."""
    w = _open["win"]
    if w is not None:
        try:
            if w.winfo_exists():
                w.deiconify()
                w.lift()
                w.focus_force()
                return w
        except tk.TclError:
            pass
    d = _pin["win"]
    if d is not None:
        try:
            if d.winfo_exists():
                d._focus()
                return d
        except tk.TclError:
            pass
    _pin["win"] = DevPinDialog(app)
    return _pin["win"]


def _show_dev(app):
    """Buka jendela Dev (setelah PIN benar)."""
    w = _open["win"]
    if w is not None:
        try:
            if w.winfo_exists():
                w.deiconify()
                w.lift()
                w.focus_force()
                return w
        except tk.TclError:
            pass
    _open["win"] = DevPanel(app)
    return _open["win"]


GROUP_ICONS = {"Web murid": "web_pin", "Tampilan UI": "grid", "Login": "lock",
               "Carousel": "image", "Beranda": "home", "Video": "play", "Mini player": "play",
               "Badge": "award", "Sertifikat": "check", "Jadwal": "clock",
               "Analytics": "activity", "Search": "search", "File": "folder", "Batas": "file",
               "Admin": "teacher"}


class DevPanel(tk.Toplevel):
    """Jendela Dev gaya Settings Claude: navigasi kiri (Search, Akun, halaman Settings),
    isi kanan berupa baris (judul + keterangan | kontrol) dengan garis tipis. Tanpa animasi."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.withdraw()
        self.title("Dev")
        self.attributes("-topmost", True)      # selalu di atas
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.W, self.H = min(1080, sw - 60), min(780, sh - 80)
        self._outer = _rounded_window(self, self.W, self.H)
        self._save_job = None
        self._restoring = False
        self._scroll_cv = None
        self.page = None
        self.bind("<MouseWheel>", self._wheel)
        self.bind("<Escape>", self._escape)
        self._build()
        st = _ui_state()
        page = {"login": "akun", "settings": "umum"}.get(st.get("tab"), st.get("tab") or "akun")
        if page not in self._nav:
            page = "akun"
        self.show(page, restore=True)
        x = app.winfo_rootx() + max(0, (app.winfo_width() - self.W) // 2)
        y = app.winfo_rooty() + max(0, (app.winfo_height() - self.H) // 2)
        self.geometry(f"{self.W}x{self.H}+{x}+{y}")
        self.deiconify()
        self.after(10, self._focus)

    def _focus(self):
        try:
            self.lift()
            self.focus_force()
            self._search.focus_set()
        except tk.TclError:
            pass

    def _escape(self, _e=None):
        if self._q.get():                  # Esc pertama = kosongkan cari, kedua = tutup
            self._q.set("")
        else:
            self.destroy()

    # --- kerangka -------------------------------------------------------------------------
    def _build(self):
        from elearning.ui.controls import RoundEntry
        for w in self._outer.winfo_children():
            w.destroy()
        nav = tk.Frame(self._outer, bg=PANEL, width=NAV_W)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        tk.Frame(self._outer, bg=LINE, width=1).pack(side="left", fill="y")
        main = tk.Frame(self._outer, bg=PANEL)
        main.pack(side="left", fill="both", expand=True)
        # navigasi kiri
        self._q = tk.StringVar(value=_ui_state().get("query", ""))
        box = self._search_box = RoundEntry(nav, self._q, placeholder="Cari", icon="search",
                                            width_chars=14, font=(C.FONT, 10), height=34,
                                            fill=SEG_BG, radius=9)
        box.pack(fill="x", padx=12, pady=(14, 8))
        self._search = box.entry
        self._search.bind("<Return>", lambda e: self._login() if self.page == "akun" else None)
        self._search.bind("<Down>", lambda e: self._move(1) if self.page == "akun" else None)
        self._search.bind("<Up>", lambda e: self._move(-1) if self.page == "akun" else None)
        self._nav = {}

        def section(text):
            tk.Label(nav, text=text, bg=PANEL, fg=MUTED, font=(C.FONT, 9),
                     anchor="w").pack(fill="x", padx=20, pady=(10, 3))
        section("Kelola")
        self._add_nav(nav, "akun", "Akun", "users")
        self._add_nav(nav, "kursus", "Kursus", "grid")
        section("Pengaturan app")
        for key, label, icon in self._pages():
            self._add_nav(nav, key, label, icon)
        _draggable(self, nav)
        # kanan: kepala (tombol x), isi, bilah bawah
        head = tk.Frame(main, bg=PANEL, height=46)
        head.pack(fill="x")
        head.pack_propagate(False)
        CloseBtn(head, self.destroy).pack(side="right", padx=(0, 14), pady=(12, 0))
        _draggable(self, head)
        self.bottom = tk.Frame(main, bg=PANEL)
        self.bottom.pack(side="bottom", fill="x", padx=28, pady=(10, 16))
        tk.Frame(main, bg=LINE, height=1).pack(side="bottom", fill="x")
        self.status = tk.Label(self.bottom, text="", bg=PANEL, fg=MUTED, font=(C.FONT, 9),
                               anchor="w")
        self._bar_acc = tk.Frame(self.bottom, bg=PANEL)
        _btn(self._bar_acc, "Masuk ke akun", self._login, "primary").pack(side="right")
        self.edit_btn = _btn(self._bar_acc, "Edit", self._edit)
        self.edit_btn.pack(side="right", padx=(0, 8))
        self.stat_btn = _btn(self._bar_acc, "Nonaktifkan", self._toggle_status)
        self.stat_btn.pack(side="right", padx=(0, 8))
        self.del_btn = _btn(self._bar_acc, "Hapus akun", self._delete, "danger")
        self.del_btn.pack(side="right", padx=(0, 8))
        _btn(self._bar_acc, "Reset progres", self._reset_progress).pack(side="right",
                                                                       padx=(0, 8))
        _btn(self._bar_acc, "Akun baru", self._new_account).pack(side="right", padx=(0, 8))
        self._bar_set = tk.Frame(self.bottom, bg=PANEL)
        # Apply Now = sementara (sampai app ditutup); Apply As Default = disimpan ke file
        self.apply_btn = _btn(self._bar_set, "Coba sekarang", lambda: self._apply(False),
                              "primary")
        self.apply_btn.pack(side="right")
        self.default_btn = _btn(self._bar_set, "Simpan permanen", lambda: self._apply(True))
        self.default_btn.pack(side="right", padx=(0, 8))
        _btn(self._bar_set, "Nilai ke bawaan", self._reset_values).pack(side="right",
                                                                       padx=(0, 8))
        self._bar_crs = tk.Frame(self.bottom, bg=PANEL)
        _btn(self._bar_crs, "Kursus baru", lambda: self.crs.new_course(), "primary").pack(
            side="right")
        self.undo_btn = _btn(self._bar_crs, "Urungkan akses", lambda: self.crs.undo())
        self.undo_btn.pack(side="right", padx=(0, 8))
        self.area = tk.Frame(main, bg=PANEL)
        self.area.pack(fill="both", expand=True)
        self._build_accounts(self.area)
        self._build_settings(self.area)
        from elearning.ui.dev_courses import CoursesPage
        self.crs = CoursesPage(self, self.area)
        self.undo_btn_state(False)
        self._q.trace_add("write", lambda *a: self._on_query())
        self.bind("<Control-n>", lambda e: self._new_account() if self.page == "akun" else None)
        self.bind("<Control-N>", lambda e: self._new_account() if self.page == "akun" else None)

    def _add_nav(self, nav, key, label, icon):
        item = NavItem(nav, label, icon, lambda k=key: self.show(k))
        item.pack(padx=12, pady=0, anchor="w")
        self._nav[key] = item

    def _pages(self):
        from elearning import dev_values as DV
        out = [("umum", "Tampilan", "image"), ("perf", "Performa", "activity"),
               ("fitur", "Fitur", "check")]
        seen = []
        for _key, grp, _label, _kind, _t in DV.VALUES:
            if grp not in seen:
                seen.append(grp)
                out.append(("v:" + grp, grp, GROUP_ICONS.get(grp, "list")))
        return out

    def show(self, key, restore=False):
        """Buka halaman (Akun / halaman Settings). Kolom cari tetap berlaku."""
        self._restoring = True
        self.page = key
        if _ui_state().get("tab") != key:
            _ui_save(tab=key)
        searching = bool(self._q.get().strip()) and key not in ("akun", "kursus")
        try:                                   # petunjuk kolom cari sesuai halaman
            self._search_box.ph.config(text={"akun": "Cari akun (nama, ID, jenis)",
                                             "kursus": "Cari murid / kursus"}.get(
                key, "Cari setting"))
        except (AttributeError, tk.TclError):
            pass
        for k, n in self._nav.items():
            n.set_active(k == key and not searching)
        for w in self.bottom.winfo_children():
            w.pack_forget()
        self.status.pack(side="left", fill="x", expand=True)
        self.crs.pack_forget()
        if key == "kursus":
            self._set_frame.pack_forget()
            self._acc_frame.pack_forget()
            self.crs.pack(fill="both", expand=True)
            self._bar_crs.pack(side="right")
            self._scroll_cv = self.crs.cv
            self.crs.refresh()
            self._restoring = False
        elif key == "akun":
            self._set_frame.pack_forget()
            self._acc_frame.pack(fill="both", expand=True)
            self._bar_acc.pack(side="right")
            self._scroll_cv = self.tb
            self._refill()
            self._restoring = False
        else:
            self._acc_frame.pack_forget()
            self._set_frame.pack(fill="both", expand=True)
            self._bar_set.pack(side="right")
            self._scroll_cv = self.scv
            self._filter()
            frac = float(_ui_state().get("scroll", 0.0) or 0.0) if restore else 0.0
            self.after_idle(lambda f=frac: self._restore_scroll(f))
            self._changed()
        self.status.pack_forget()
        self.status.pack(side="left", fill="x", expand=True)

    def _on_query(self):
        if not self._restoring:
            self._remember(query=self._q.get())
        if self.page == "akun":
            self._refill()
        elif self.page == "kursus":
            self.crs.filter()
        else:
            for k, n in self._nav.items():
                n.set_active(k == self.page and not self._q.get().strip())
            self._filter()

    def _note(self, text):
        self.status.config(text=text)

    def undo_btn_state(self, on):
        """Tombol Urungkan (halaman Kursus) aktif kalau ada perubahan akses."""
        try:
            self.undo_btn.configure(state="normal" if on else "disabled")
        except tk.TclError:
            pass

    # --- halaman Akun -------------------------------------------------------------------
    # Tabel 6 kolom di SATU kanvas: Jenis | ID | Nama | Status | Login terakhir | PIN.
    # Klik = pilih, klik 2x sel = ubah di tempat (Status murid = Active <-> Expired), kursor di
    # atas baris = PIN terlihat (selain itu ****). Masuk: tombol / Enter. Akun baru: Ctrl+N.
    ROW_H = 34
    COLS = ("kind", "id", "name", "status", "last", "pin")

    def _build_accounts(self, parent):
        import tkinter.font as tkfont
        from elearning.ui.dev_login import KIND, accounts
        from elearning.ui.widgets import DarkScrollbar
        self._kind = KIND
        self.items = accounts()
        self.sel = None
        self._hov = None
        self._editing = None
        self._mono = tkfont.Font(family=C.FONT, size=10)
        self._head_f = tkfont.Font(family=C.FONT, size=9, weight="bold")
        self._load_last()
        f = self._acc_frame = tk.Frame(parent, bg=PANEL)
        wrap = tk.Frame(f, bg=PANEL)
        wrap.pack(fill="both", expand=True, padx=(28, 18))
        top = tk.Frame(wrap, bg=PANEL)
        top.pack(fill="x")
        tk.Label(top, text="Akun", bg=PANEL, fg=FG, font=(C.FONT, 14, "bold"),
                 anchor="w").pack(side="left")
        self.acc_count = tk.Label(top, text="", bg=PANEL, fg=MUTED, font=(C.FONT, 10))
        self.acc_count.pack(side="right", padx=(0, 10))
        tk.Label(wrap, text="Pilih akun lalu \"Masuk ke akun\" (tanpa PIN). Akun baru: "
                            "Ctrl+N. Klik 2x sel = ubah langsung. Arahkan kursor ke baris = PIN "
                            "terlihat. Nonaktif = tidak bisa login, data tetap.", bg=PANEL, fg=MUTED, font=(C.FONT, 10),
                 anchor="w", justify="left", wraplength=700).pack(fill="x", pady=(2, 14))
        bar = tk.Frame(wrap, bg=PANEL)
        bar.pack(fill="x", padx=(0, 10))
        self.f_kind = tk.StringVar(value="Semua")
        self.f_sort = tk.StringVar(value="Nama")
        Seg(bar, [(v, v) for v in FILTERS], "Semua",
            lambda v: (self.f_kind.set(v), self._refill())).pack(side="left")
        Seg(bar, [(v, v) for v in SORTS], "Nama",
            lambda v: (self.f_sort.set(v), self._refill())).pack(side="right")
        self.head = tk.Canvas(wrap, bg=PANEL, height=30, highlightthickness=0, bd=0)
        self.head.pack(fill="x", pady=(14, 0))
        tk.Frame(wrap, bg=LINE, height=1).pack(fill="x")
        tw = tk.Frame(wrap, bg=PANEL)
        tw.pack(fill="both", expand=True)
        self.tb = tk.Canvas(tw, bg=PANEL, highlightthickness=0, bd=0)
        sb = DarkScrollbar(tw, command=self.tb.yview, bg=PANEL)
        self.tb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(6, 0))
        self.tb.pack(fill="both", expand=True)
        self.tb.bind("<Configure>", lambda ev: self._draw())
        self.tb.bind("<Button-1>", self._click)
        self.tb.bind("<Double-Button-1>", self._double)
        self.tb.bind("<Motion>", self._motion)
        self.tb.bind("<Leave>", lambda ev: self._set_hover(None))

    # posisi kolom (px) dihitung dari lebar angka "0": tetap rata di semua skala DPI
    def _xs(self):
        """{kolom: x kiri} + lebar huruf "0"."""
        cw = self._mono.measure("0")
        w = max(200, self.tb.winfo_width())
        x = {"kind": 12, "id": 12 + cw * 12}
        x["name"] = x["id"] + cw * 11
        x["pin"] = w - 12 - cw * 8
        x["last"] = x["pin"] - cw * 16
        x["status"] = x["last"] - cw * 10
        return x, cw

    def _col_at(self, x):
        xs, _cw = self._xs()
        for col in reversed(self.COLS):
            if x >= xs[col] - 3:
                return col
        return "kind"

    def _col_end(self, col):
        xs, cw = self._xs()
        i = self.COLS.index(col)
        return xs[self.COLS[i + 1]] if i + 1 < len(self.COLS) else max(200, self.tb.winfo_width())

    def _load_last(self):
        """Login terakhir semua akun {ID: datetime} (sessions.overview, sekali per muat)."""
        try:
            from elearning import sessions
            self._last = {k: v.get("last_seen") or v.get("last_in")
                          for k, v in sessions.overview().items()}
        except Exception as exc:
            C.log(f"Dev: riwayat login tidak terbaca: {exc!r}")
            self._last = {}

    def _cell(self, it, col, show_pin=False):
        """(teks, warna) sel tabel."""
        kind, uid = it[0], it[1]
        if col == "kind":
            return self._kind[kind][0], FG
        if col == "id":
            return uid, FG
        if col == "name":
            return it[2], FG
        if col == "status":
            if kind in ("adult", "kids"):
                exp = (it[3] or {}).get("status") == "expired"
                return ("Nonaktif", "#ff8a80") if exp else ("Aktif", MUTED)
            return "-", MUTED
        if col == "last":
            if kind == "trial":
                return "-", MUTED
            t = self._last.get(uid)
            return (t.strftime("%d/%m/%y %H:%M") if t else "Belum pernah"), MUTED
        return self._pin_text(it, show_pin), MUTED

    def _load_pins(self):
        """PIN guru & admin {ID: PIN} (murid dan trial tidak memakai PIN)."""
        pins = {}
        try:
            from elearning import admins, teachers
            for uid, _n in admins.list_admins():
                pins[uid] = admins.get_pin(uid) or ""
            for uid, t in teachers._load().items():
                pins[uid] = t.get("pin", "")
        except Exception as exc:
            C.log(f"Dev: PIN tidak terbaca: {exc!r}")
        self._pins = pins

    def _pin_text(self, it, show):
        pin = self._pins.get(it[1]) if it[0] in ("admin", "teacher") else None
        if not pin:
            return "-"
        return pin if show else "\u2022" * 4

    def _refill(self):
        words = self._q.get().lower().split()
        want = FILTER_KIND.get(self.f_kind.get())

        def text(it):                  # semua kata harus ada: jenis, ID, nama, status
            st = (it[3] or {}).get("status") if it[0] in ("adult", "kids") else None
            return " ".join((self._kind[it[0]][0], it[1], it[2],
                             "nonaktif expired" if st == "expired" else
                             "aktif active" if st else "")).lower()
        shown = [it for it in self.items
                 if (want is None or it[0] in want) and all(w in text(it) for w in words)]
        # jenis selalu jadi urutan utama (admin, guru, trial, dewasa, SUPERKIDS), lalu Nama / ID
        by_id = self.f_sort.get() == "ID"
        key = lambda it: (KIND_ORDER.index(it[0]) if it[0] in KIND_ORDER else len(KIND_ORDER),
                          it[1] if by_id else it[2].lower(), it[1])
        self.shown = sorted(shown, key=key)
        self._load_pins()
        n = {}
        for it in self.items:
            n[it[0]] = n.get(it[0], 0) + 1
        self.acc_count.config(text="  ·  ".join(
            f"{n[k]} {self._kind[k][0].lower() if k != 'kids' else 'SUPERKIDS'}"
            for k in KIND_ORDER if k in n and k != "trial"))
        self.sel = 0 if self.shown else None
        self._cancel_edit()
        self._draw()
        self.tb.yview_moveto(0)
        self._sel_changed()

    def _fit(self, text, px):
        cw = self._mono.measure("0")
        n = max(1, int(px // cw))
        return text if len(text) <= n else text[:max(1, n - 1)] + "\u2026"

    def _draw(self):
        tb, R = self.tb, self.ROW_H
        xs, cw = self._xs()
        w = max(200, tb.winfo_width())
        tb.delete("all")
        self.head.delete("all")
        for col, t in zip(self.COLS, ("Jenis", "ID", "Nama", "Status", "Login terakhir",
                                      "PIN")):
            self.head.create_text(xs[col], 15, text=t, anchor="w", font=self._head_f,
                                  fill=MUTED)
        self._hov_rect = tb.create_rectangle(0, -R, w, 0, fill=NAV_HOV, width=0)
        self._sel_rect = tb.create_rectangle(0, -R, w, 0, fill=NAV_SEL, width=0)
        self._pin_ids = []
        self._row_ids = []
        self._row_cols = []
        for i, it in enumerate(self.shown):
            y = i * R + R / 2
            ids, cols = [], []
            for col in self.COLS:
                text, color = self._cell(it, col)
                ids.append(tb.create_text(xs[col], y, anchor="w", font=self._mono, fill=color,
                                          text=self._fit(text, self._col_end(col) - xs[col]
                                                         - cw)))
                cols.append(color)
            self._row_ids.append(ids)
            self._row_cols.append(cols)
            self._pin_ids.append(ids[-1])
        tb.configure(scrollregion=(0, 0, w, max(1, len(self.shown) * R)))
        self._place_rect(self._sel_rect, self.sel)
        self._place_rect(self._hov_rect, self._hov if self._hov != self.sel else None)
        self._paint_sel()
        if self._hov is not None and self._hov < len(self._pin_ids):
            tb.itemconfigure(self._pin_ids[self._hov], text=self._pin_text(self.shown[self._hov], True))

    def _place_rect(self, rect, i):
        R = self.ROW_H
        w = max(200, self.tb.winfo_width())
        if i is None:
            self.tb.coords(rect, 0, -R, w, 0)
        else:
            self.tb.coords(rect, 0, i * R, w, (i + 1) * R)

    def _paint_sel(self):
        for i, ids in enumerate(self._row_ids):
            on = i == self.sel
            for k, item in enumerate(ids):
                base = self._row_cols[i][k]
                self.tb.itemconfigure(item, fill=base if base == "#ff8a80" else
                                      "white" if on else base)

    def _row_at(self, y):
        i = int(self.tb.canvasy(y) // self.ROW_H)
        return i if 0 <= i < len(self.shown) else None

    def _set_hover(self, i):
        if i == self._hov:
            return
        old, self._hov = self._hov, i
        if old is not None and old < len(self._pin_ids):
            self.tb.itemconfigure(self._pin_ids[old], text=self._pin_text(self.shown[old], False))
        if i is not None:
            self.tb.itemconfigure(self._pin_ids[i], text=self._pin_text(self.shown[i], True))
        self._place_rect(self._hov_rect, i if i != self.sel else None)

    def _motion(self, ev):
        self._set_hover(self._row_at(ev.y))

    def _select(self, i):
        if i is None:
            return
        self.sel = i
        self._place_rect(self._sel_rect, i)
        self._place_rect(self._hov_rect, self._hov if self._hov != i else None)
        self._paint_sel()
        self._see(i)
        self._sel_changed()

    def _see(self, i):
        total = max(1, len(self.shown) * self.ROW_H)
        top, bottom = self.tb.yview()
        y0, y1 = i * self.ROW_H / total, (i + 1) * self.ROW_H / total
        if y0 < top:
            self.tb.yview_moveto(y0)
        elif y1 > bottom:
            self.tb.yview_moveto(max(0.0, y1 - (bottom - top)))

    def _click(self, ev):
        if self._editing is not None:
            self._commit_edit()
        self._select(self._row_at(ev.y))

    def _selected(self):
        if self.sel is None or not self.shown or self.sel >= len(self.shown):
            return None
        return self.shown[self.sel]

    def _sel_changed(self):
        it = self._selected()
        kind = it[0] if it is not None else None
        self.del_btn.config(state="disabled" if kind in (None, "trial") else "normal")
        self.edit_btn.config(state="disabled" if kind in (None, "trial") else "normal",
                             text="Edit guru" if kind == "teacher"
                             else "Edit admin" if kind == "admin"
                             else "Edit murid" if kind in ("adult", "kids") else "Edit")
        student = kind in ("adult", "kids")
        exp = student and (it[3] or {}).get("status") == "expired"
        self.stat_btn.config(state="normal" if student else "disabled",
                             text="Aktifkan" if exp else "Nonaktifkan")

    def _move(self, d):
        if not self.shown:
            return "break"
        i = max(0, min(len(self.shown) - 1, (self.sel if self.sel is not None else 0) + d))
        self._select(i)
        return "break"

    # --- ubah di tempat (klik 2x) --------------------------------------------------------
    def _double(self, ev):
        i = self._row_at(ev.y)
        if i is None:
            return
        self._select(i)
        it = self.shown[i]
        kind, col = it[0], self._col_at(ev.x)
        if kind == "trial":
            self._note("Akun trial tidak bisa diubah.")
            return
        student = kind in ("adult", "kids")
        if col == "status":
            if student:
                self._toggle_status()
            else:
                self._note("Status hanya untuk murid.")
            return
        if col == "last":
            return
        if col == "kind":
            if not student:
                self._note("Jenis guru / admin tidak bisa diubah.")
                return
            m = tk.Menu(self, tearoff=0, font=FONT, bg=FIELD, fg=FG, activebackground=C.ACCENT)
            for prog, label in (("adult", "Dewasa"), ("kids", "SUPERKIDS")):
                m.add_command(label=label, command=lambda p=prog: self._save_cell(it, "kind", p))
            m.tk_popup(ev.x_root, ev.y_root)
            return
        if col == "id" and not student:
            self._note("ID guru / admin tidak bisa diubah.")
            return
        if col == "pin" and student:
            self._note("Murid tidak memakai PIN.")
            return
        value = {"id": it[1], "name": it[2], "pin": self._pins.get(it[1], "")}[col]
        self._begin_edit(i, col, value)

    def _begin_edit(self, i, col, value):
        self._cancel_edit()
        xs, _cw = self._xs()
        x0, x1 = xs[col], self._col_end(col)
        var = tk.StringVar(value=value)
        ent = tk.Entry(self.tb, textvariable=var, font=self._mono, bg=SEG_BG, fg="white",
                       insertbackground="white", relief="flat", highlightthickness=1,
                       highlightbackground=C.ACCENT, highlightcolor=C.ACCENT)
        win = self.tb.create_window(x0 - 3, i * self.ROW_H, anchor="nw", window=ent,
                                    width=x1 - x0 - 2, height=self.ROW_H)
        self._editing = (i, col, var, ent, win)
        ent.bind("<Return>", lambda ev: self._commit_edit() or "break")
        ent.bind("<Escape>", lambda ev: self._cancel_edit() or "break")
        ent.bind("<FocusOut>", lambda ev: self.after_idle(self._commit_edit))
        ent.focus_set()
        ent.select_range(0, "end")
        ent.icursor("end")

    def _cancel_edit(self):
        ed, self._editing = getattr(self, "_editing", None), None
        if ed is not None:
            try:
                self.tb.delete(ed[4])
                ed[3].destroy()
            except tk.TclError:
                pass

    def _commit_edit(self):
        ed = self._editing
        if ed is None:
            return
        i, col, var, _ent, _win = ed
        if i >= len(self.shown):
            self._cancel_edit()
            return
        it = self.shown[i]
        old = {"id": it[1], "name": it[2], "pin": self._pins.get(it[1], "")}[col]
        text = var.get().strip()
        if text == old:
            self._cancel_edit()
            return
        self._editing = None                 # cegah simpan dua kali (Enter + FocusOut)
        ok = self._save_cell(it, col, text)
        if ok:
            try:
                self.tb.delete(ed[4])
                ed[3].destroy()
            except tk.TclError:
                pass
        else:
            self._editing = ed               # salah: kolom tetap terbuka untuk diperbaiki
            try:
                ed[3].focus_set()
                ed[3].select_range(0, "end")
            except tk.TclError:
                self._editing = None

    def _save_cell(self, it, col, value):
        """Simpan satu sel. True kalau tersimpan; kalau salah, pesan di baris status."""
        kind, uid = it[0], it[1]
        new_id = uid
        try:
            if kind in ("adult", "kids"):
                from elearning import students as ST
                if col == "kind":
                    if value == kind:
                        return True
                    ST.set_program(uid, value)
                elif col == "name":
                    ST.rename_student(uid, value)
                elif col == "id":
                    ST.change_id(uid, value.upper())
                    new_id = value.strip().upper()
            elif kind == "teacher":
                from elearning import teachers as T
                t = T.get_teacher(uid)
                if t is None:
                    raise ValueError(f"Guru {uid} tidak ditemukan.")
                if col == "name":
                    T.update_teacher(uid, value)
                elif col == "pin":
                    T._clean_pin(value)                  # kosong = salah, bukan "tetap"
                    T.update_teacher(uid, t["name"], value)
            elif kind == "admin":
                from elearning import admins as A
                if col == "name":
                    A.set_name(uid, value)
                elif col == "pin":
                    A.set_pin(uid, value)
        except (ValueError, KeyError) as exc:
            self._note(str(exc).strip("'"))
            return False
        except OSError as exc:
            C.log(f"Dev: simpan {uid} ({col}) gagal: {exc!r}")
            self._note("Gagal menyimpan (folder data?).")
            return False
        C.log(f"Dev: {uid} {col} diubah")
        self.reload_accounts(new_id)
        what = {"kind": "jenis", "id": "ID", "name": "nama", "pin": "PIN"}[col]
        self._note(f"Tersimpan: {new_id} ({what})")
        try:
            if kind in ("adult", "kids"):
                self._student_changed(uid, new_id)
            else:
                self.app.dev_account_changed(kind, uid)
        except Exception as exc:
            C.log(f"Dev: layar tidak dibangun ulang: {exc!r}")
        return True

    def _student_changed(self, old_id, new_id):
        """Murid diubah dari Dev: kalau sedang login, data di aplikasi ikut baru; layar
        dibangun ulang supaya perubahan langsung terlihat."""
        from elearning import students as ST
        app = self.app
        cur = getattr(app, "_student", None)
        if cur is not None and cur.get("id") == old_id:      # murid yang sedang login
            fresh = ST.lookup_student(new_id)
            app._student = fresh
            if getattr(app, "_account_id", None) == old_id:
                app._account_id = new_id
            scr = getattr(app, "_screen", None)
            if scr is not None and getattr(scr, "student", None) is not None:
                scr.student = fresh
        app.rebuild_screen()

    def _login(self):
        it = self._selected()
        if it is None:
            return
        kind, _uid, name, acc = it
        if kind == "trial":
            from elearning.trial import trial_student
            acc = trial_student()
        self.app.dev_login(kind, acc)
        self._note(f"Masuk: {name}")

    def _edit(self):
        from elearning.ui.dev_accounts import AccountEditor, StudentEditor
        it = self._selected()
        if it is None:
            return
        if it[0] in ("adult", "kids"):
            StudentEditor(self, it[1])
        elif it[0] in ("admin", "teacher"):
            AccountEditor(self, it[0], it[1], it[2])

    def _delete(self):
        from elearning.ui.dev_accounts import DeleteConfirm
        it = self._selected()
        if it is None or it[0] == "trial":
            return
        DeleteConfirm(self, it[0], it[1], it[2])

    def _reset_progress(self):
        """Dialog reset progres; murid yang dipilih di tabel sudah tercentang."""
        from elearning.ui.dev_accounts import ResetProgress
        it = self._selected()
        ResetProgress(self, [it[1]] if it is not None and it[0] in ("adult", "kids") else [])

    def _new_account(self):
        from elearning.ui.dev_accounts import NewAccount
        kind = {"Dewasa": "adult", "SUPERKIDS": "kids", "Guru": "teacher",
                "Admin": "admin"}.get(self.f_kind.get(), "adult")
        NewAccount(self, kind)

    def account_created(self, uid, login=False):
        """Akun baru dari dialog: tampilkan & pilih di tabel (filter / cari dikosongkan kalau
        akun itu tidak kelihatan), lalu masuk kalau diminta."""
        self.reload_accounts(uid)
        if not any(it[1] == uid for it in self.shown):
            self._q.set("")
            self.reload_accounts(uid)
        self._note(f"Akun {uid} dibuat.")
        if login and self._selected() is not None and self._selected()[1] == uid:
            self._login()

    def _toggle_status(self):
        """Murid: Active <-> Expired (expired tidak bisa login; data tetap)."""
        from elearning import students as ST
        it = self._selected()
        if it is None or it[0] not in ("adult", "kids"):
            return
        new = "active" if (it[3] or {}).get("status") == "expired" else "expired"
        try:
            ST.set_status(it[1], new)
        except (ValueError, OSError) as exc:
            self._note(str(exc) if isinstance(exc, ValueError) else
                       "Gagal menyimpan (folder data?).")
            return
        C.log(f"Dev: status {it[1]} -> {new}")
        self.reload_accounts(it[1])
        self._note(f"{it[1]} {'diaktifkan' if new == 'active' else 'dinonaktifkan (tidak bisa login)'}.")
        try:
            self._student_changed(it[1], it[1])
        except Exception as exc:
            C.log(f"Dev: layar tidak dibangun ulang: {exc!r}")

    def reload_accounts(self, select_id=None):
        """Setelah akun diubah: muat ulang daftar, pilih akun itu lagi (posisi gulir tetap)."""
        from elearning.ui.dev_login import accounts
        tb = getattr(self, "tb", None)
        try:
            if tb is None or not tb.winfo_exists():
                return                       # tab Login sedang tidak tampil
        except tk.TclError:
            return
        top = self.tb.yview()[0]
        self.items = accounts()
        self._load_last()
        self._refill()
        self.tb.yview_moveto(top)
        for n, it in enumerate(self.shown):
            if it[1] == select_id:
                self._select(n)
                break

    def _remember(self, **kv):
        """Simpan posisi (digabung: tulis file maks. sekali per 400 ms)."""
        self._ui_pending = {**getattr(self, "_ui_pending", {}), **kv}
        if self._save_job is None:
            self._save_job = self.after(400, self._flush_ui)

    def _flush_ui(self):
        self._save_job = None
        kv, self._ui_pending = getattr(self, "_ui_pending", {}), {}
        if kv:
            _ui_save(**kv)

    def _on_scroll(self, sb, first, last):
        sb.set(first, last)
        if not self._restoring:
            self._remember(scroll=round(float(first), 4))

    def _restore_scroll(self, frac):
        try:
            cv = self._scroll_cv
            self.update_idletasks()
            cv.configure(scrollregion=cv.bbox("all"))
            cv.yview_moveto(frac)
        except tk.TclError:
            pass
        self._restoring = False

    def _wheel(self, e):
        cv = self._scroll_cv
        if cv is not None and cv.winfo_exists():
            cv.yview_scroll(int(-e.delta / 120) or (-1 if e.delta > 0 else 1), "units")

    # --- halaman Settings ------------------------------------------------------------------
    # Semua baris dibuat SEKALI (isian yang belum di-Apply tetap ada saat pindah halaman);
    # pindah halaman / cari = hanya pack / pack_forget.
    def _build_settings(self, parent):
        from elearning import dev_values as DV
        from elearning.ui.controls import RoundEntry
        from elearning.ui.widgets import DarkScrollbar, Switch
        self._pending = {}           # perubahan yang belum di-Apply: key -> nilai
        self._pending_feat = {}
        self._val_vars = {}
        self._reg = []               # ("head" | "row", halaman, grup, widget, garis, teks cari)
        f = self._set_frame = tk.Frame(parent, bg=PANEL)
        cv = self.scv = tk.Canvas(f, bg=PANEL, highlightthickness=0, bd=0)
        sb = DarkScrollbar(f, command=cv.yview, bg=PANEL)
        cv.configure(yscrollcommand=lambda a, b, sb=sb: self._on_scroll(sb, a, b))
        sb.pack(side="right", fill="y", padx=(0, 6))
        cv.pack(fill="both", expand=True)
        inner = self._set_inner = tk.Frame(cv, bg=PANEL)
        win = cv.create_window(28, 0, window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Configure>", lambda e: cv.itemconfigure(win, width=max(200, e.width - 56)))

        def head(page, text):
            lbl = tk.Label(inner, text=text, bg=PANEL, fg=FG, font=(C.FONT, 14, "bold"),
                           anchor="w")
            self._reg.append(("head", page, text, lbl, None, text.lower()))

        def row(page, group, title, desc, make, search=""):
            fr = tk.Frame(inner, bg=PANEL)
            left = tk.Frame(fr, bg=PANEL)
            left.pack(side="left", fill="x", expand=True, pady=12)
            tk.Label(left, text=title, bg=PANEL, fg=FG, font=(C.FONT, 11),
                     anchor="w").pack(fill="x")
            if desc:
                tk.Label(left, text=desc, bg=PANEL, fg=MUTED, font=(C.FONT, 10), anchor="w",
                         justify="left", wraplength=480).pack(fill="x", pady=(2, 0))
            ctrl = make(fr)
            ctrl.pack(side="right", padx=(16, 0))
            line = tk.Frame(inner, bg=LINE, height=1)
            self._reg.append(("row", page, group, fr, line,
                              f"{title} {desc} {search} {group}".lower()))

        # Tampilan
        head("umum", "Tampilan login")
        row("umum", "Tampilan login", "Mode layar login",
            "Carousel + video latar, carousel 3 baris kartu, atau video latar saja.",
            lambda p: Seg(p, LOGIN_LABELS, S.login_mode(),
                          lambda v: self._mark("login_mode", v)),
            " ".join(f"{k} {lbl}" for k, lbl in LOGIN_LABELS) + " login mode")
        head("umum", "Warna aksen")
        row("umum", "Warna aksen", "Warna aksen",
            "Tombol utama dan sorotan. Berlaku penuh setelah aplikasi dibuka ulang.",
            lambda p: Swatches(p, [(k, v[1], v[0]) for k, v in S.ACCENTS.items()],
                               S.get("accent"), lambda v: self._mark("accent", v)),
            "accent color " + " ".join(f"{k} {v[0]}" for k, v in S.ACCENTS.items()))
        # Fitur
        head("fitur", "Fitur")
        for key, label in S.FEATURES:
            row("fitur", "Fitur", label, "",
                lambda p, k=key: Switch(p, S.feature(k), bg=PANEL,
                                        command=lambda v, k=k: self._mark_feat(k, v)),
                f"{key} fitur on off")
        # Performa: preset PC (langsung tersimpan + diterapkan, tidak lewat tombol bawah)
        head("perf", "Preset performa")
        # satu blok bertumpuk (tombol preset terlalu lebar untuk baris judul | kontrol)
        fr = tk.Frame(inner, bg=PANEL)
        tk.Label(fr, text="Preset untuk PC ini", bg=PANEL, fg=FG, font=(C.FONT, 11),
                 anchor="w").pack(fill="x", pady=(12, 0))
        tk.Label(fr, text="Klik = langsung tersimpan & dipakai (tidak perlu tombol di bawah). "
                          "Buka ulang app supaya semua bagian (thread render, pemutar video) "
                          "ikut penuh.", bg=PANEL, fg=MUTED, font=(C.FONT, 10), anchor="w",
                 justify="left", wraplength=640).pack(fill="x", pady=(2, 10))
        self._perf_seg = Seg(fr, [(k, lbl) for k, lbl, _d, _v in C.PERF_PRESETS],
                             S.get("perf_preset") or "auto", self._set_perf)
        self._perf_seg.pack(anchor="w")
        tk.Label(fr, text="PC ini terdeteksi:  " + self._perf_detected_text(), bg=PANEL,
                 fg=MUTED, font=(C.FONT, 10), anchor="w").pack(fill="x", pady=(12, 0))
        box = tk.Frame(fr, bg=DP_CARD)
        box.pack(fill="x", pady=(12, 14))
        tk.Label(box, text="Yang dipakai sekarang", bg=DP_CARD, fg=MUTED, font=(C.FONT, 9),
                 anchor="w").pack(fill="x", padx=14, pady=(10, 0))
        self._perf_now = tk.Label(box, text="", bg=DP_CARD, fg=FG, font=(C.FONT, 10),
                                  justify="left", anchor="w", wraplength=620)
        self._perf_now.pack(fill="x", padx=14, pady=(2, 10))
        self._perf_text()
        line = tk.Frame(inner, bg=LINE, height=1)
        self._reg.append(("row", "perf", "Preset performa", fr, line,
                          "performa preset ryzen 3 5 nvidia gpu pc lambat ringan cepat deteksi "
                          "thread cpu mode ringan fps carousel"))
        # Nilai (angka / teks), satu halaman per grup
        group = None
        for key, grp, label, _kind, _t in DV.VALUES:
            if grp != group:
                group = grp
                head("v:" + grp, grp)
            var = tk.StringVar(value=DV.current_text(key))
            self._val_vars[key] = (var, var.get())
            var.trace_add("write", lambda *a: self._changed())

            def entry(p, var=var):
                return RoundEntry(p, var, width_chars=12, font=(C.FONT, 10), height=32,
                                  fill=SEG_BG, radius=8)
            row("v:" + grp, grp, label, key, entry, key.replace("_", " "))
        self._empty = tk.Label(inner, text="Tidak ada setting yang cocok.", bg=PANEL, fg=MUTED,
                               font=(C.FONT, 10), anchor="w")

    def _filter(self):
        """Halaman Settings: baris halaman ini; kalau ada kata di kolom cari = baris yang cocok
        dari SEMUA halaman (judul grup cocok = semua barisnya tampil)."""
        words = self._q.get().lower().split()
        for kind, _p, _g, w, line, _t in self._reg:
            w.pack_forget()
            if line is not None:
                line.pack_forget()
        self._empty.pack_forget()
        if words:
            groups = {g for k, _p, g, _w, _l, _t in self._reg
                      if k == "head" and all(q in g.lower() for q in words)}
            hit = [r for r in self._reg if r[0] == "row"
                   and (r[2] in groups or all(q in r[5] for q in words))]
        else:
            hit = [r for r in self._reg if r[0] == "row" and r[1] == self.page]
        want = {(r[1], r[2]) for r in hit}
        first, last_line = True, None
        for kind, page, group, w, line, _t in self._reg:
            if kind == "head":
                if (page, group) in want:
                    w.pack(fill="x", pady=(4 if first else 26, 4))
                    first = False
                    last_line = None
            elif (kind, page, group, w, line, _t) in hit:
                w.pack(fill="x")
                line.pack(fill="x")
                last_line = line
        if not hit:
            self._empty.pack(fill="x", pady=12)
        self.scv.yview_moveto(0)
        if not self._restoring:
            self._remember(scroll=0.0)

    # --- preset performa ------------------------------------------------------------------
    @staticmethod
    def _perf_detected_text():
        import os
        cpus = getattr(os, "process_cpu_count", os.cpu_count)() or 0
        nv = os.path.isfile(os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                                         "System32", "nvapi64.dll"))
        label = dict((k, lbl) for k, lbl, _d, _v in C.PERF_PRESETS)[C.perf_detected()]
        return f"{cpus} thread CPU  ·  NVIDIA: {'ada' if nv else 'tidak ada'}  ·  saran: {label}"

    def _perf_text(self):
        names = dict((k, (lbl, d)) for k, lbl, d, _v in C.PERF_PRESETS)
        cur = C.PERF_PRESET
        lbl, desc = names[cur]
        if cur == "auto":
            lbl = f"Otomatis = {names[C.perf_detected()][0]}"
            desc = names[C.perf_detected()][1]
        hi = "60 fps, 4 thread" if C.HIGH_END else "30 fps"
        self._perf_now.config(
            text=f"{lbl}:  {desc}\n\nMode ringan: {'ya' if C.lite() else 'tidak'}   ·   "
                 f"thread kerja: {C.WORKER_THREADS}   ·   carousel login: {hi}")

    def _set_perf(self, preset):
        try:
            S.set("perf_preset", preset)
        except OSError as exc:
            C.log(f"Dev: preset performa gagal disimpan: {exc!r}")
            self._note("Gagal menyimpan (folder data?).")
            return
        C.apply_perf(preset)
        self._perf_seg.set(preset)
        C.log(f"Dev: preset performa -> {preset}")
        try:
            self.app.apply_dev_settings()        # layar dibangun ulang dengan preset baru
        except Exception as exc:
            C.log(f"Dev: preset performa tidak diterapkan: {exc!r}")
        self._perf_text()
        self.lift()
        self._note("Preset disimpan. Buka ulang app supaya semua bagian ikut.")

    def _mark(self, key, value):
        self._pending[key] = value
        self._changed()

    def _mark_feat(self, key, on):
        self._pending_feat[key] = bool(on)
        self._changed()

    def _val_changes(self):
        return {k: var.get() for k, (var, start) in self._val_vars.items()
                if var.get().strip() != start}

    def _changed(self):
        n = len(self._pending) + len(self._pending_feat) + len(self._val_changes())
        temp = bool(S.session())          # ada yang diterapkan sementara (Apply Now)
        self.apply_btn.config(state="normal" if n else "disabled")
        self.default_btn.config(state="normal" if n or temp else "disabled")
        if n:
            self._note(f"{n} perubahan belum diterapkan")
        elif temp:
            self._note("Sedang dicoba: kembali seperti semula saat app ditutup "
                       "(Simpan permanen = tetap).")
        else:
            self._note("")

    def _apply(self, as_default):
        """Terapkan semua perubahan langsung ke aplikasi (tanpa buka ulang).
        as_default False (Apply Now): hanya sementara, hilang saat app ditutup.
        as_default True (Apply As Default): juga semua yang tadi sementara, disimpan ke file."""
        from elearning import dev_values as DV
        vals = self._val_changes()
        for key, text in vals.items():          # periksa dulu: salah satu salah = batal semua
            try:
                DV.parse(key, text)
            except ValueError as exc:
                self._note(str(exc))
                return
        # perubahan baru masuk lapisan sementara dulu (dua tombol sama-sama langsung berlaku)
        if vals:
            S.set_session("values", {k: t.strip() for k, t in vals.items()})
        for key, value in self._pending.items():
            S.set_session(key, value)
        if self._pending_feat:
            S.set_session("features", dict(self._pending_feat))
        try:
            if as_default:
                temp = S.session()
                if "values" in temp:
                    saved = dict(S.saved("values") or {})
                    for key, text in temp.pop("values").items():
                        if text == DV.default_text(key):
                            saved.pop(key, None)    # sama dengan bawaan: tidak perlu disimpan
                        else:
                            saved[key] = text
                    S.set("values", saved)
                for key, on in temp.pop("features", {}).items():
                    S.set_feature(key, on)
                for key, value in temp.items():
                    S.set(key, value)
                S.clear_session()
        except OSError as exc:
            C.log(f"Dev: setting gagal disimpan: {exc!r}")
            self._note("Gagal menyimpan (folder data?).")
            return
        self._pending, self._pending_feat = {}, {}
        try:
            self.app.apply_dev_settings()
        except Exception as exc:
            C.log(f"Dev: apply gagal: {exc!r}")
            self._note("Tersimpan, tapi gagal diterapkan (lihat app.log).")
            return
        self._rebuild()                    # warna tombol ikut aksen baru
        self.lift()
        self._note("Disimpan sebagai bawaan." if as_default
                   else "Diterapkan sementara (kembali saat app ditutup).")

    def _reset_values(self):
        """Hapus semua nilai isian dev: kembali ke nilai bawaan kode, langsung diterapkan."""
        try:
            S.set("values", {})
            S.clear_session("values")
            self.app.apply_dev_settings()
        except Exception as exc:
            C.log(f"Dev: reset nilai gagal: {exc!r}")
            self._note("Gagal reset (lihat app.log).")
            return
        self._rebuild()
        self._note("Nilai kembali ke bawaan.")

    def _rebuild(self):
        """Bangun ulang isi panel (setelah Apply / Reset), tetap di halaman yang sama."""
        page = self.page
        self._build()
        self.show(page)

    def destroy(self):
        _open["win"] = None
        if self._save_job is not None:
            self.after_cancel(self._save_job)
            self._flush_ui()
        super().destroy()
