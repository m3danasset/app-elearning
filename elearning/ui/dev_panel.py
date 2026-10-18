"""Jendela Dev (Ctrl KANAN + Shift KANAN + Backspace, di layar mana pun).

Dibuka setelah PIN Dev benar (DevPinDialog; yang disimpan hanya hash-nya, DEV_PIN_HASH).
Sengaja sederhana: widget Tk biasa, selalu di atas (topmost). Dua tab:
- Login    : cari akun (admin, guru, murid, trial) lalu masuk tanpa PIN.
- Settings : tampilan login, warna aksen, dan fitur aplikasi on/off (data\\app_settings.json).
"""

import time
import tkinter as tk

from elearning import app_settings as S
from elearning import config as C

BG, FG, MUTED, FIELD = "#202020", "#e8e8e8", "#9a9a9a", "#2c2c2c"
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


class DevPinDialog(tk.Toplevel):
    """Minta PIN sebelum jendela Dev dibuka. Enter = cek, Esc / tutup = batal."""

    def __init__(self, app):
        super().__init__(app, bg=BG)
        self.app = app
        self.title("Dev")
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.geometry(f"260x128+{app.winfo_rootx() + 40}+{app.winfo_rooty() + 60}")
        tk.Label(self, text="PIN Dev", bg=BG, fg=FG, font=BOLD, anchor="w").pack(
            fill="x", padx=14, pady=(12, 4))
        self.var = tk.StringVar()
        self.entry = tk.Entry(self, textvariable=self.var, show="\u2022", font=FONT, bg=FIELD,
                              fg=FG, insertbackground=FG, relief="flat")
        self.entry.pack(fill="x", padx=14, ipady=4)
        self.msg = tk.Label(self, text="", bg=BG, fg=C.ERROR, font=FONT, anchor="w")
        self.msg.pack(fill="x", padx=14, pady=(6, 0))
        tk.Button(self, text="Buka", font=BOLD, relief="flat", bg=C.ACCENT, fg="white",
                  activebackground=C.ACCENT_HOVER, activeforeground="white",
                  command=self._check).pack(fill="x", padx=14, pady=(4, 10), ipady=1)
        self.entry.bind("<Return>", lambda e: self._check())
        self.bind("<Escape>", lambda e: self.destroy())
        self.var.trace_add("write", lambda *a: self._limit())
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


class DevPanel(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app, bg=BG)
        self.app = app
        self.title("Dev")
        self.attributes("-topmost", True)      # selalu di atas
        self.resizable(False, True)
        self.geometry(f"380x680+{app.winfo_rootx() + 40}+{app.winfo_rooty() + 60}")
        self._scroll_cv = None
        self.bind("<MouseWheel>", self._wheel)
        tabs = tk.Frame(self, bg=BG)
        tabs.pack(fill="x", padx=8, pady=(8, 4))
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._tab_btns = {}
        for key, label in (("login", "Login"), ("settings", "Settings")):
            b = tk.Button(tabs, text=label, font=BOLD, relief="flat", bd=0, padx=12, pady=4,
                          bg=FIELD, fg=FG, activebackground="#3a3a3a", activeforeground=FG,
                          command=lambda k=key: self.show(k))
            b.pack(side="left", padx=(0, 4))
            self._tab_btns[key] = b
        self.status = tk.Label(self, text="", bg=BG, fg=MUTED, font=FONT, anchor="w")
        self.status.pack(fill="x", padx=8, pady=(0, 6))
        self.bind("<Escape>", lambda e: self.destroy())
        self._save_job = None
        self._restoring = False
        self.show("settings" if _ui_state().get("tab") == "settings" else "login")

    def show(self, key):
        self._restoring = True        # kanvas lama dibuang: jangan simpan gulir "0" sementara
        if _ui_state().get("tab") != key:
            _ui_save(tab=key)
        for k, b in self._tab_btns.items():
            b.config(bg="#3a3a3a" if k == key else FIELD)
        for w in self.body.winfo_children():
            w.destroy()
        (self._login_tab if key == "login" else self._settings_tab)()

    def _note(self, text):
        self.status.config(text=text)

    # --- Login ----------------------------------------------------------------------------
    # Tabel 4 kolom di SATU kanvas: Jenis | ID | Nama | PIN. Klik = pilih, klik 2x sel = ubah
    # di tempat, kursor di atas baris = PIN terlihat (selain itu ****). Masuk: tombol / Enter.
    ROW_H = 20
    COLS = ("kind", "id", "name", "pin")

    def _login_tab(self):
        import tkinter.font as tkfont
        from elearning.ui.dev_login import KIND, accounts
        self._kind = KIND
        self.items = accounts()
        self.sel = None
        self._hov = None
        self._editing = None
        self._mono = tkfont.Font(font=MONO)
        self.q = tk.StringVar()
        e = tk.Entry(self.body, textvariable=self.q, font=FONT, bg=FIELD, fg=FG,
                     insertbackground=FG, relief="flat")
        e.pack(fill="x", ipady=4)
        self._search = e
        # filter jenis + sortir
        bar = tk.Frame(self.body, bg=BG)
        bar.pack(fill="x", pady=(6, 0))
        self.f_kind = tk.StringVar(value="Semua")
        self.f_sort = tk.StringVar(value="Nama")
        for label, var, values in (("Jenis", self.f_kind, FILTERS), ("Urut", self.f_sort, SORTS)):
            tk.Label(bar, text=label, bg=BG, fg=MUTED, font=FONT).pack(side="left", padx=(0, 4))
            om = tk.OptionMenu(bar, var, *values, command=lambda _v: self._refill())
            om.config(font=FONT, bg=FIELD, fg=FG, activebackground="#3a3a3a",
                      activeforeground=FG, relief="flat", highlightthickness=0, bd=0)
            om["menu"].config(font=FONT, bg=FIELD, fg=FG, activebackground=C.ACCENT)
            om.pack(side="left", padx=(0, 10))
        # judul kolom (kanvas sendiri, posisi x sama dengan tabel)
        self.head = tk.Canvas(self.body, bg=BG, height=18, highlightthickness=0, bd=0)
        self.head.pack(fill="x", pady=(6, 0))
        btns = tk.Frame(self.body, bg=BG)
        btns.pack(fill="x", side="bottom")
        tk.Label(self.body, text="Klik 2x sel = ubah  \u00b7  kursor di baris = PIN terlihat",
                 bg=BG, fg=MUTED, font=FONT, anchor="w").pack(fill="x", side="bottom",
                                                             pady=(2, 4))
        wrap = tk.Frame(self.body, bg=FIELD)
        wrap.pack(fill="both", expand=True, pady=(2, 0))
        self.tb = tk.Canvas(wrap, bg=FIELD, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(wrap, command=self.tb.yview)
        self.tb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tb.pack(fill="both", expand=True)
        self._scroll_cv = self.tb            # roda mouse menggulir tabel
        tk.Button(btns, text="Masuk", font=BOLD, relief="flat", bg=C.ACCENT, fg="white",
                  activebackground=C.ACCENT_HOVER, activeforeground="white",
                  command=self._login).pack(side="left", fill="x", expand=True, ipady=3)
        self.edit_btn = tk.Button(btns, text="Edit", font=BOLD, relief="flat", bg=FIELD,
                                  fg=FG, activebackground="#3a3a3a", activeforeground=FG,
                                  command=self._edit)
        self.edit_btn.pack(side="left", fill="x", expand=True, ipady=3, padx=(6, 0))
        self.del_btn = tk.Button(btns, text="Hapus", font=BOLD, relief="flat", bg=FIELD,
                                 fg="#ff6b6b", activebackground="#3a3a3a",
                                 activeforeground="#ff6b6b", command=self._delete)
        self.del_btn.pack(side="left", fill="x", expand=True, ipady=3, padx=(6, 0))
        self.q.trace_add("write", lambda *a: self._refill())
        self.tb.bind("<Configure>", lambda ev: self._draw())
        self.tb.bind("<Button-1>", self._click)
        self.tb.bind("<Double-Button-1>", self._double)
        self.tb.bind("<Motion>", self._motion)
        self.tb.bind("<Leave>", lambda ev: self._set_hover(None))
        self._refill()
        e.bind("<Return>", lambda ev: self._login())
        e.bind("<Down>", lambda ev: self._move(1))
        e.bind("<Up>", lambda ev: self._move(-1))
        e.focus_set()

    # posisi kolom (px) dihitung dari lebar huruf Consolas: tetap rata di semua skala DPI
    def _xs(self):
        cw = self._mono.measure("0")
        w = max(200, self.tb.winfo_width())
        x_kind, x_id = 6, 6 + cw * 11
        x_name = x_id + cw * 10
        x_pin = w - 8 - cw * 10
        return x_kind, x_id, x_name, x_pin, cw

    def _col_at(self, x):
        _k, x_id, x_name, x_pin, _cw = self._xs()
        if x < x_id - 3:
            return "kind"
        if x < x_name - 3:
            return "id"
        if x < x_pin - 3:
            return "name"
        return "pin"

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
        q = self.q.get().strip().lower()
        want = FILTER_KIND.get(self.f_kind.get())
        shown = [it for it in self.items
                 if (want is None or it[0] in want)
                 and (not q or q in it[2].lower() or q in it[1].lower()
                      or q in self._kind[it[0]][0].lower())]
        # jenis selalu jadi urutan utama (admin, guru, trial, dewasa, SUPERKIDS), lalu Nama / ID
        by_id = self.f_sort.get() == "ID"
        key = lambda it: (KIND_ORDER.index(it[0]) if it[0] in KIND_ORDER else len(KIND_ORDER),
                          it[1] if by_id else it[2].lower(), it[1])
        self.shown = sorted(shown, key=key)
        self._load_pins()
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
        x_kind, x_id, x_name, x_pin, cw = self._xs()
        w = max(200, tb.winfo_width())
        tb.delete("all")
        self.head.delete("all")
        for x, t in ((x_kind, "Jenis"), (x_id, "ID"), (x_name, "Nama"), (x_pin, "PIN")):
            self.head.create_text(x, 9, text=t, anchor="w", font=MONO_B, fill=MUTED)
        self._hov_rect = tb.create_rectangle(0, -R, w, 0, fill="#363636", width=0)
        self._sel_rect = tb.create_rectangle(0, -R, w, 0, fill=C.ACCENT, width=0)
        self._pin_ids = []
        self._row_ids = []
        for i, it in enumerate(self.shown):
            y = i * R + R / 2
            ids = (tb.create_text(x_kind, y, anchor="w", font=MONO, fill=FG,
                                  text=self._fit(self._kind[it[0]][0], x_id - x_kind - cw)),
                   tb.create_text(x_id, y, anchor="w", font=MONO, fill=FG,
                                  text=self._fit(it[1], x_name - x_id - cw)),
                   tb.create_text(x_name, y, anchor="w", font=MONO, fill=FG,
                                  text=self._fit(it[2], x_pin - x_name - cw)),
                   tb.create_text(x_pin, y, anchor="w", font=MONO, fill=MUTED,
                                  text=self._pin_text(it, False)))
            self._row_ids.append(ids)
            self._pin_ids.append(ids[3])
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
                self.tb.itemconfigure(item, fill="white" if on else (MUTED if k == 3 else FG))

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
                             text="Edit akun" if kind in ("admin", "teacher")
                             else "Edit murid" if kind in ("adult", "kids") else "Edit")

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
        x_kind, x_id, x_name, x_pin, cw = self._xs()
        w = max(200, self.tb.winfo_width())
        x0, x1 = {"id": (x_id, x_name), "name": (x_name, x_pin), "pin": (x_pin, w)}[col]
        var = tk.StringVar(value=value)
        ent = tk.Entry(self.tb, textvariable=var, font=MONO, bg="#101010", fg="white",
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
        it = self._selected()
        if it is None:
            return
        if it[0] in ("adult", "kids"):
            StudentEditor(self, it[1])
        elif it[0] in ("admin", "teacher"):
            AccountEditor(self, it[0], it[1], it[2])

    def _delete(self):
        it = self._selected()
        if it is None or it[0] == "trial":
            return
        DeleteConfirm(self, it[0], it[1], it[2])

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
        self._refill()
        self.tb.yview_moveto(top)
        for n, it in enumerate(self.shown):
            if it[1] == select_id:
                self._select(n)
                break

    # --- Settings ---------------------------------------------------------------------------
    def _group(self, title):
        """Grup baru (judul + baris-barisnya); baris ditambah lewat _item()."""
        head = tk.Label(self.body, text=title, bg=BG, fg=MUTED, font=BOLD, anchor="w")
        self._groups.append((head, title.lower(), []))

    def _item(self, widget, text):
        self._groups[-1][2].append((widget, text.lower()))

    def _filter(self):
        """Tampilkan hanya grup / baris yang cocok dengan kolom cari (judul grup cocok =
        semua barisnya tampil). Widget tidak dibuat ulang: isian yang belum di-Apply tetap."""
        words = self._q.get().lower().split()
        for head, _t, rows in self._groups:
            head.pack_forget()
            for w, _x in rows:
                w.pack_forget()
        shown = 0
        for head, title, rows in self._groups:
            if all(w in title for w in words):
                hit = rows
            else:
                hit = [(w, x) for w, x in rows if all(q in x + " " + title for q in words)]
            if not hit:
                continue
            head.pack(fill="x", pady=(8, 2))
            for w, _x in hit:
                w.pack(fill="x", pady=1)
            shown += len(hit)
        self._empty.pack_forget()
        if not shown:
            self._empty.pack(fill="x", pady=12)
        self._reset_btn.pack_forget()
        if not words:
            self._reset_btn.pack(fill="x", pady=(10, 4), ipady=2)
        self._scroll_cv.yview_moveto(0)
        if not self._restoring:
            self._remember(query=self._q.get(), scroll=0.0)

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

    def _settings_tab(self):
        from elearning import dev_values as DV
        self._pending = {}           # perubahan yang belum di-Apply: key -> nilai
        self._pending_feat = {}
        self._val_vars = {}
        self._groups = []            # (judul, teks judul, [(baris, teks cari)])
        outer = self.body
        # kolom cari (di atas, tidak ikut tergulir)
        top = tk.Frame(outer, bg=BG)
        top.pack(fill="x", pady=(0, 4))
        tk.Label(top, text="Cari", bg=BG, fg=MUTED, font=FONT).pack(side="left", padx=(0, 6))
        self._q = tk.StringVar()
        q = tk.Entry(top, textvariable=self._q, font=FONT, bg=FIELD, fg=FG,
                     insertbackground=FG, relief="flat")
        q.pack(side="left", fill="x", expand=True, ipady=3)
        q.bind("<Escape>", lambda e: self._q.set(""))
        # area gulir (isi panjang) + tombol Apply tetap di bawah
        bottom = tk.Frame(outer, bg=BG)
        bottom.pack(side="bottom", fill="x")
        cv = tk.Canvas(outer, bg=BG, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(outer, command=cv.yview)
        cv.configure(yscrollcommand=lambda a, b, sb=sb: self._on_scroll(sb, a, b))
        sb.pack(side="right", fill="y")
        cv.pack(fill="both", expand=True)
        inner = tk.Frame(cv, bg=BG)
        win = cv.create_window(0, 0, window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Configure>", lambda e: cv.itemconfigure(win, width=e.width))
        self._scroll_cv = cv
        self.body = inner
        self._group("Tampilan login")
        mode = tk.StringVar(value=S.login_mode())
        for key, label in LOGIN_LABELS:
            self._item(tk.Radiobutton(self.body, text=label, value=key, variable=mode,
                                      font=FONT, bg=BG, fg=FG, selectcolor=FIELD,
                                      activebackground=BG, activeforeground=FG, anchor="w",
                                      command=lambda: self._mark("login_mode", mode.get())),
                       f"{label} {key} login mode")
        self._group("Warna aksen")
        acc = tk.StringVar(value=S.get("accent"))
        row = tk.Frame(self.body, bg=BG)
        for n, (key, (name, color, _hover)) in enumerate(S.ACCENTS.items()):
            tk.Radiobutton(row, text=name, value=key, variable=acc, font=FONT, bg=BG,
                           fg=color, selectcolor=FIELD, activebackground=BG,
                           activeforeground=color, anchor="w",
                           command=lambda: self._mark("accent", acc.get())
                           ).grid(row=n // 3, column=n % 3, sticky="w", padx=(0, 6))
        self._item(row, "warna aksen accent color " + " ".join(
            f"{k} {v[0]}" for k, v in S.ACCENTS.items()))
        self._group("Akun web murid")
        from elearning import web_launcher as WL
        acc = getattr(C, "WEB_STUDIO_ACCOUNT", "") or "(profil per murid)"
        self._item(tk.Label(self.body, text=f"Akun Google studio: {acc}", bg=BG, fg=MUTED,
                            font=FONT, anchor="w"), "akun google studio pinterest web login")
        self._item(tk.Button(self.body, text="Login akun studio di PC ini (sekali)", font=FONT,
                             relief="flat", bg=FIELD, fg=FG, activebackground="#3a3a3a",
                             activeforeground=FG, command=lambda: WL.studio_login(self.app),
                             state="normal" if WL.shared() else "disabled"),
                   "login akun studio google pinterest chrome")
        self._group("Fitur")
        for key, label in S.FEATURES:
            v = tk.BooleanVar(value=S.feature(key))
            self._item(tk.Checkbutton(self.body, text=label, variable=v, font=FONT, bg=BG,
                                      fg=FG, selectcolor=FIELD, activebackground=BG,
                                      activeforeground=FG, anchor="w",
                                      command=lambda k=key, var=v: self._mark_feat(k, var.get())),
                       f"{label} {key} fitur on off")
        self._item(tk.Label(self.body, text=f"PC kuat (NVIDIA + >=12 thread): "
                                            f"{'ya' if getattr(C, 'HIGH_END', False) else 'tidak'}",
                            bg=BG, fg=MUTED, font=FONT, anchor="w"),
                   "pc kuat nvidia high end fps60")
        # --- nilai (isi angka / teks) ---
        group = None
        for key, grp, label, _kind, _t in DV.VALUES:
            if grp != group:
                group = grp
                self._group(grp)
            line = tk.Frame(self.body, bg=BG)
            line.columnconfigure(0, weight=1)
            var = tk.StringVar(value=DV.current_text(key))
            self._val_vars[key] = (var, var.get())
            tk.Label(line, text=label, bg=BG, fg=FG, font=FONT, anchor="w").grid(
                row=0, column=0, sticky="w")
            tk.Entry(line, textvariable=var, font=FONT, bg=FIELD, fg=FG, insertbackground=FG,
                     relief="flat", width=14).grid(row=0, column=1, sticky="e", ipady=1)
            var.trace_add("write", lambda *a: self._changed())
            self._item(line, f"{label} {key.replace('_', ' ')}")
        self._empty = tk.Label(self.body, text="Tidak ada setting yang cocok.", bg=BG,
                               fg=MUTED, font=FONT)
        self._reset_btn = tk.Button(self.body, text="Reset semua nilai ke bawaan", font=FONT,
                                    relief="flat", bg=FIELD, fg=FG, activebackground="#3a3a3a",
                                    activeforeground=FG, command=self._reset_values)
        self.body = outer
        btns = tk.Frame(bottom, bg=BG)
        btns.pack(fill="x", pady=(6, 0))
        # Apply Now = sementara (sampai app ditutup); Apply As Default = disimpan ke file
        self.apply_btn = tk.Button(btns, text="Apply Now", font=BOLD, relief="flat",
                                   bg=C.ACCENT, fg="white", activebackground=C.ACCENT_HOVER,
                                   activeforeground="white", state="disabled",
                                   command=lambda: self._apply(False))
        self.apply_btn.pack(side="left", fill="x", expand=True, ipady=3)
        self.default_btn = tk.Button(btns, text="Apply As Default", font=BOLD, relief="flat",
                                     bg=FIELD, fg=FG, activebackground="#3a3a3a",
                                     activeforeground=FG, state="disabled",
                                     command=lambda: self._apply(True))
        self.default_btn.pack(side="left", fill="x", expand=True, ipady=3, padx=(6, 0))
        # posisi terakhir (juga setelah Apply / Reset / app dibuka ulang, sampai PC reboot)
        st = _ui_state()
        self._restoring = True
        self._q.set(st.get("query", ""))
        self._filter()
        self._q.trace_add("write", lambda *a: self._filter())
        self.after_idle(lambda f=float(st.get("scroll", 0.0) or 0.0): self._restore_scroll(f))
        self._changed()                   # status tombol (ada setting sementara?)
        q.focus_set()

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
            self._note("Sementara: kembali saat app ditutup (Apply As Default = simpan).")
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
        self.show("settings")              # warna tombol ikut aksen baru
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
        self.show("settings")
        self._note("Nilai kembali ke bawaan.")

    def destroy(self):
        _open["win"] = None
        if self._save_job is not None:
            self.after_cancel(self._save_job)
            self._flush_ui()
        super().destroy()


class DeleteConfirm(tk.Toplevel):
    """Konfirmasi hapus akun (jendela Dev). Tidak bisa dibatalkan setelah Hapus."""

    WHAT = {
        "adult": "Akun, foto, progres video, badge, portfolio & assignment, riwayat login, "
                 "jadwal, kuis, dan sertifikat murid ini ikut terhapus.",
        "kids": "Akun, foto, progres video, badge, portfolio & assignment, riwayat login, "
                "jadwal, kuis, dan sertifikat murid ini ikut terhapus.",
        "teacher": "Akun, foto, dan riwayat masuk/keluar guru ini ikut terhapus. Laporan "
                   "kerjanya tetap tersimpan.",
        "admin": "Akun admin ini tidak bisa dipakai login lagi.",
    }

    def __init__(self, panel, kind, uid, name):
        super().__init__(panel, bg=BG)
        self.panel, self.kind, self.uid = panel, kind, uid
        self.title("Hapus akun")
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.geometry(f"300x190+{panel.winfo_rootx() + 30}+{panel.winfo_rooty() + 90}")
        tk.Label(self, text=f"Hapus {uid}  {name}?", bg=BG, fg=FG, font=BOLD, anchor="w",
                 wraplength=272, justify="left").pack(fill="x", padx=14, pady=(12, 4))
        tk.Label(self, text=self.WHAT.get(kind, "") + " Tidak bisa dikembalikan.", bg=BG,
                 fg=MUTED, font=FONT, anchor="w", wraplength=272, justify="left").pack(
            fill="x", padx=14)
        self.msg = tk.Label(self, text="", bg=BG, fg=C.ERROR, font=FONT, anchor="w",
                            wraplength=272, justify="left")
        self.msg.pack(fill="x", padx=14, pady=(6, 0))
        btns = tk.Frame(self, bg=BG)
        btns.pack(fill="x", side="bottom", padx=14, pady=(4, 12))
        tk.Button(btns, text="Hapus", font=BOLD, relief="flat", bg="#c0392b", fg="white",
                  activebackground="#e04a3a", activeforeground="white",
                  command=self._do).pack(side="left", fill="x", expand=True, ipady=2)
        cancel = tk.Button(btns, text="Batal", font=BOLD, relief="flat", bg=FIELD, fg=FG,
                           activebackground="#3a3a3a", activeforeground=FG,
                           command=self.destroy)
        cancel.pack(side="left", fill="x", expand=True, ipady=2, padx=(6, 0))
        self.bind("<Escape>", lambda ev: self.destroy())
        cancel.focus_set()                  # Enter tidak langsung menghapus

    def _do(self):
        try:
            if self.kind == "admin":
                from elearning import admins
                admins.delete_admin(self.uid)
            elif self.kind == "teacher":
                from elearning import teachers
                teachers.delete_teacher(self.uid)
            else:
                from elearning import students
                students.delete_student(self.uid)
        except ValueError as exc:
            self.msg.config(text=str(exc))
            return
        except OSError as exc:
            C.log(f"Dev: hapus {self.uid} gagal: {exc!r}")
            self.msg.config(text="Gagal menghapus (folder data?).")
            return
        C.log(f"Dev: akun {self.uid} dihapus")
        panel, uid = self.panel, self.uid
        self.destroy()
        try:
            panel.reload_accounts()
            panel._note(f"{uid} dihapus.")
            panel.app.dev_account_deleted(uid)
        except Exception as exc:
            C.log(f"Dev: setelah hapus {uid}: {exc!r}")


class AccountEditor(tk.Toplevel):
    """Ubah nama & PIN guru / admin (jendela Dev). PIN lama terlihat supaya dev tahu yang
    dipakai. Dua-duanya diperiksa dulu; salah satu salah = tidak ada yang disimpan."""

    def __init__(self, panel, kind, uid, name):
        super().__init__(panel, bg=BG)
        self.panel, self.kind, self.uid = panel, kind, uid
        self.title("Edit akun")
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.geometry(f"300x186+{panel.winfo_rootx() + 30}+{panel.winfo_rooty() + 90}")
        if kind == "admin":
            from elearning import admins
            pin = admins.get_pin(uid)
            name = admins.get_name(uid) or name
        else:
            from elearning import teachers
            pin = teachers.get_pin(uid)
            name = (teachers.get_teacher(uid) or {}).get("name", name)
        self._old = (name, pin or "")
        tk.Label(self, text=f"{'Admin' if kind == 'admin' else 'Guru'}  {uid}", bg=BG, fg=FG,
                 font=BOLD, anchor="w").pack(fill="x", padx=14, pady=(12, 6))
        grid = tk.Frame(self, bg=BG)
        grid.pack(fill="x", padx=14)
        grid.columnconfigure(1, weight=1)
        self.name_var = tk.StringVar(value=name)
        self.var = tk.StringVar(value=pin or "")
        entries = []
        for r, (label, var) in enumerate((("Nama", self.name_var), ("PIN", self.var))):
            tk.Label(grid, text=label, bg=BG, fg=MUTED, font=FONT, anchor="w").grid(
                row=r, column=0, sticky="w", padx=(0, 8), pady=2)
            e = tk.Entry(grid, textvariable=var, font=FONT, bg=FIELD, fg=FG,
                         insertbackground=FG, relief="flat")
            e.grid(row=r, column=1, sticky="ew", pady=2, ipady=3)
            e.bind("<Return>", lambda ev: self._save())
            entries.append(e)
        self.msg = tk.Label(self, text="PIN 4-10 karakter, tanpa spasi.", bg=BG, fg=MUTED,
                            font=FONT, anchor="w")
        self.msg.pack(fill="x", padx=14, pady=(6, 0))
        btns = tk.Frame(self, bg=BG)
        btns.pack(fill="x", padx=14, pady=(6, 10))
        tk.Button(btns, text="Simpan", font=BOLD, relief="flat", bg=C.ACCENT, fg="white",
                  activebackground=C.ACCENT_HOVER, activeforeground="white",
                  command=self._save).pack(side="left", fill="x", expand=True, ipady=2)
        tk.Button(btns, text="Batal", font=BOLD, relief="flat", bg=FIELD, fg=FG,
                  activebackground="#3a3a3a", activeforeground=FG,
                  command=self.destroy).pack(side="left", fill="x", expand=True, ipady=2,
                                             padx=(6, 0))
        self.bind("<Escape>", lambda ev: self.destroy())
        entries[0].focus_set()
        entries[0].select_range(0, "end")

    def _save(self):
        name, pin = " ".join(self.name_var.get().split()), self.var.get()
        if (name, pin) == self._old:
            self.destroy()
            return
        try:
            if self.kind == "admin":
                from elearning import admins
                admins.check_pin_text(pin)                  # periksa dulu, baru simpan
                if not name:
                    raise ValueError("Nama admin belum diisi.")
                if len(name) > admins.NAME_MAX:
                    raise ValueError(f"Nama terlalu panjang (maksimal {admins.NAME_MAX} huruf).")
                if name != self._old[0]:
                    admins.set_name(self.uid, name)
                if pin != self._old[1]:
                    admins.set_pin(self.uid, pin)
            else:
                from elearning import teachers
                teachers._clean_pin(pin)        # kosong = salah, bukan "tetap"
                if teachers.get_teacher(self.uid) is None:
                    raise ValueError(f"Guru {self.uid} tidak ditemukan.")
                teachers.update_teacher(self.uid, name, pin)
        except ValueError as exc:
            self.msg.config(text=str(exc), fg=C.ERROR)
            return
        except OSError as exc:
            C.log(f"Dev: akun {self.uid} gagal disimpan: {exc!r}")
            self.msg.config(text="Gagal menyimpan (folder data?).", fg=C.ERROR)
            return
        C.log(f"Dev: akun {self.uid} diubah (nama / PIN)")
        panel, kind, uid = self.panel, self.kind, self.uid
        self.destroy()
        try:
            panel.reload_accounts(uid)
            panel._note(f"{uid} disimpan.")
            panel.app.dev_account_changed(kind, uid)
        except Exception as exc:
            C.log(f"Dev: setelah ubah {uid}: {exc!r}")


class StudentEditor(tk.Toplevel):
    """Edit murid (jendela Dev): nama, ID, kategori, status, tanggal lahir, kursus
    (terbuka / tampil). ID diganti PALING AKHIR beserta semua datanya (students.change_id)."""

    def __init__(self, panel, sid):
        from elearning import students as ST
        super().__init__(panel, bg=BG)
        self.panel, self.ST = panel, ST
        self.st = ST.lookup_student(sid)
        self.title(f"Edit {sid}")
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.geometry(f"+{panel.winfo_rootx() + 30}+{panel.winfo_rooty() + 40}")
        f = tk.Frame(self, bg=BG, padx=10, pady=10)
        f.pack(fill="both", expand=True)
        self.v = {"name": tk.StringVar(value=self.st["name"]),
                  "id": tk.StringVar(value=self.st["id"]),
                  "program": tk.StringVar(value=self.st["program"]),
                  "status": tk.StringVar(value=self.st["status"]),
                  "birth": tk.StringVar(value=self.st.get("birth") or "")}
        for r, (label, key) in enumerate((("Nama", "name"), ("ID", "id"),
                                          ("Tgl lahir (YYYY-MM-DD)", "birth"))):
            tk.Label(f, text=label, bg=BG, fg=MUTED, font=FONT, anchor="w").grid(
                row=r, column=0, sticky="w", pady=2)
            tk.Entry(f, textvariable=self.v[key], font=FONT, bg=FIELD, fg=FG,
                     insertbackground=FG, relief="flat", width=26).grid(
                row=r, column=1, columnspan=2, sticky="we", pady=2, ipady=2)
        for r, (label, key, opts) in enumerate(
                (("Kategori", "program", (("adult", "Dewasa"), ("kids", "SUPERKIDS"))),
                 ("Status", "status", (("active", "Active"), ("expired", "Expired")))), start=3):
            tk.Label(f, text=label, bg=BG, fg=MUTED, font=FONT, anchor="w").grid(
                row=r, column=0, sticky="w", pady=2)
            for c, (val, text) in enumerate(opts, start=1):
                tk.Radiobutton(f, text=text, value=val, variable=self.v[key], font=FONT, bg=BG,
                               fg=FG, selectcolor=FIELD, activebackground=BG,
                               activeforeground=FG,
                               command=self._courses if key == "program" else None).grid(
                    row=r, column=c, sticky="w")
        tk.Label(f, text="Kursus            Buka   Tampil", bg=BG, fg=MUTED, font=MONO_B,
                 anchor="w").grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 2))
        self.cbox = tk.Frame(f, bg=BG)
        self.cbox.grid(row=6, column=0, columnspan=3, sticky="we")
        self.msg = tk.Label(f, text="", bg=BG, fg=C.ERROR, font=FONT, anchor="w",
                            wraplength=300, justify="left")
        self.msg.grid(row=7, column=0, columnspan=3, sticky="we", pady=(6, 0))
        tk.Button(f, text="Simpan", font=BOLD, relief="flat", bg=C.ACCENT, fg="white",
                  activebackground=C.ACCENT_HOVER, activeforeground="white",
                  command=self._save).grid(row=8, column=0, columnspan=3, sticky="we",
                                           pady=(8, 0), ipady=3)
        self.bind("<Escape>", lambda e: self.destroy())
        self._courses()

    def _courses(self):
        """Daftar kursus untuk kategori yang dipilih (ganti kategori = ganti daftar)."""
        from elearning.courses import courses_for
        for w in self.cbox.winfo_children():
            w.destroy()
        prog = self.v["program"].get()
        same = prog == self.st["program"]
        opened = set(self.st["courses"]) if same else set()
        hidden = set(self.st.get("hidden") or ()) if same else set()
        self.cv = []
        for n, c in enumerate(courses_for(prog)):
            o = tk.BooleanVar(value=c["id"] in opened or (not same and n == 0))
            t = tk.BooleanVar(value=c["id"] not in hidden)
            tk.Label(self.cbox, text=c["title"][:16], bg=BG, fg=FG, font=MONO, width=17,
                     anchor="w").grid(row=n, column=0, sticky="w")
            for col, var in ((1, o), (2, t)):
                tk.Checkbutton(self.cbox, variable=var, bg=BG, selectcolor=FIELD,
                               activebackground=BG).grid(row=n, column=col, padx=4)
            self.cv.append((c["id"], o, t))

    def _save(self):
        ST, sid = self.ST, self.st["id"]
        try:
            if self.v["program"].get() != self.st["program"]:
                ST.set_program(sid, self.v["program"].get())
            for cid, o, t in self.cv:
                ST.set_course_access(sid, cid, o.get())
                ST.set_course_hidden(sid, cid, not t.get())
            if self.v["name"].get().strip() != self.st["name"]:
                ST.rename_student(sid, self.v["name"].get())
            if self.v["status"].get() != self.st["status"]:
                ST.set_status(sid, self.v["status"].get())
            birth = self.v["birth"].get().strip()
            if birth != (self.st.get("birth") or ""):
                ST.set_birth(sid, birth or None)
            new_id = self.v["id"].get().strip().upper()
            if new_id and new_id != sid:
                ST.change_id(sid, new_id)       # paling akhir: pindahkan semua data
                sid = new_id
        except (ValueError, KeyError) as exc:
            self.msg.config(text=str(exc).strip("'"))
            return
        except OSError as exc:
            C.log(f"Dev edit murid {sid}: {exc!r}")
            self.msg.config(text="Gagal menyimpan (folder data?).")
            return
        C.log(f"Dev: murid {self.st['id']} diedit -> {sid}")
        self.panel.reload_accounts(sid)
        self.panel._note(f"Tersimpan: {sid}")
        try:
            self.panel._student_changed(self.st["id"], sid)   # perubahan langsung terlihat
        except Exception as exc:
            C.log(f"Dev: layar tidak dibangun ulang: {exc!r}")
        self.destroy()
