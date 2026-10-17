"""Jendela Dev (Ctrl KANAN + Shift KANAN + Backspace, di layar mana pun).

Sengaja sederhana: widget Tk biasa, selalu di atas (topmost). Dua tab:
- Login    : cari akun (admin, guru, murid, trial) lalu masuk tanpa PIN.
- Settings : tampilan login, warna aksen, dan fitur aplikasi on/off (data\\app_settings.json).
"""

import tkinter as tk

from elearning import app_settings as S
from elearning import config as C

BG, FG, MUTED, FIELD = "#202020", "#e8e8e8", "#9a9a9a", "#2c2c2c"
FONT = (C.FONT, 9)
BOLD = (C.FONT, 9, "bold")
MONO = ("Consolas", 9)            # huruf lebar tetap: kolom Jenis | ID | Nama rata
MONO_B = ("Consolas", 9, "bold")
FILTERS = ("Semua", "Murid", "Dewasa", "SUPERKIDS", "Guru", "Admin", "Trial")
FILTER_KIND = {"Semua": None, "Murid": ("adult", "kids"), "Dewasa": ("adult",),
               "SUPERKIDS": ("kids",), "Guru": ("teacher",), "Admin": ("admin",),
               "Trial": ("trial",)}
SORTS = ("Nama", "ID", "Jenis")
KIND_ORDER = ("admin", "teacher", "adult", "kids", "trial")
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


def open_dev(app):
    """Buka jendela Dev (atau munculkan lagi kalau sudah terbuka)."""
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
        self.show("login")

    def show(self, key):
        for k, b in self._tab_btns.items():
            b.config(bg="#3a3a3a" if k == key else FIELD)
        for w in self.body.winfo_children():
            w.destroy()
        (self._login_tab if key == "login" else self._settings_tab)()

    def _note(self, text):
        self.status.config(text=text)

    # --- Login ----------------------------------------------------------------------------
    def _login_tab(self):
        from elearning.ui.dev_login import KIND, accounts
        self._kind = KIND
        self.items = accounts()
        self.q = tk.StringVar()
        e = tk.Entry(self.body, textvariable=self.q, font=FONT, bg=FIELD, fg=FG,
                     insertbackground=FG, relief="flat")
        e.pack(fill="x", ipady=4)
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
        # judul kolom + daftar (huruf lebar tetap: 3 kolom rata)
        tk.Label(self.body, text=self._row("Jenis", "ID", "Nama"), bg=BG, fg=MUTED,
                 font=MONO_B, anchor="w").pack(fill="x", pady=(6, 0))
        self.lb = tk.Listbox(self.body, font=MONO, bg=FIELD, fg=FG, relief="flat",
                             selectbackground=C.ACCENT, selectforeground="white",
                             highlightthickness=0, activestyle="none")
        self.lb.pack(fill="both", expand=True, pady=(2, 6))
        btns = tk.Frame(self.body, bg=BG)
        btns.pack(fill="x")
        tk.Button(btns, text="Masuk", font=BOLD, relief="flat", bg=C.ACCENT, fg="white",
                  activebackground=C.ACCENT_HOVER, activeforeground="white",
                  command=self._login).pack(side="left", fill="x", expand=True, ipady=3)
        self.edit_btn = tk.Button(btns, text="Edit murid", font=BOLD, relief="flat", bg=FIELD,
                                  fg=FG, activebackground="#3a3a3a", activeforeground=FG,
                                  command=self._edit)
        self.edit_btn.pack(side="left", fill="x", expand=True, ipady=3, padx=(6, 0))
        self.q.trace_add("write", lambda *a: self._refill())
        self._refill()
        e.bind("<Return>", lambda ev: self._login())
        e.bind("<Down>", lambda ev: self._move(1))
        e.bind("<Up>", lambda ev: self._move(-1))
        self.lb.bind("<Double-Button-1>", lambda ev: self._login())
        self.lb.bind("<<ListboxSelect>>", lambda ev: self._sel_changed())
        e.focus_set()

    @staticmethod
    def _row(kind, uid, name):
        return f"{kind[:10]:<10} {uid[:9]:<9} {name}"

    def _refill(self):
        q = self.q.get().strip().lower()
        want = FILTER_KIND.get(self.f_kind.get())
        shown = [it for it in self.items
                 if (want is None or it[0] in want)
                 and (not q or q in it[2].lower() or q in it[1].lower()
                      or q in self._kind[it[0]][0].lower())]
        key = {"Nama": lambda it: it[2].lower(), "ID": lambda it: it[1],
               "Jenis": lambda it: (KIND_ORDER.index(it[0]), it[2].lower())}[self.f_sort.get()]
        self.shown = sorted(shown, key=key)
        self.lb.delete(0, "end")
        for kind, uid, name, _acc in self.shown:
            self.lb.insert("end", self._row(self._kind[kind][0], uid, name))
        if self.shown:
            self.lb.selection_set(0)
        self._sel_changed()

    def _selected(self):
        sel = self.lb.curselection()
        return self.shown[sel[0]] if sel and self.shown else None

    def _sel_changed(self):
        it = self._selected()
        ok = it is not None and it[0] in ("adult", "kids")
        self.edit_btn.config(state="normal" if ok else "disabled")

    def _move(self, d):
        sel = self.lb.curselection()
        i = max(0, min(len(self.shown) - 1, (sel[0] if sel else 0) + d))
        self.lb.selection_clear(0, "end")
        self.lb.selection_set(i)
        self.lb.see(i)
        self._sel_changed()
        return "break"

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
        if it is None or it[0] not in ("adult", "kids"):
            return
        StudentEditor(self, it[1])

    def reload_accounts(self, select_id=None):
        """Setelah murid diedit: muat ulang daftar, pilih murid itu lagi."""
        from elearning.ui.dev_login import accounts
        self.items = accounts()
        self._refill()
        for n, it in enumerate(self.shown):
            if it[1] == select_id:
                self.lb.selection_clear(0, "end")
                self.lb.selection_set(n)
                self.lb.see(n)
                break
        self._sel_changed()

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
        cv.configure(yscrollcommand=sb.set)
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
        self._filter()
        self._q.trace_add("write", lambda *a: self._filter())
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
        super().destroy()


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
        app = self.panel.app
        cur = getattr(app, "_student", None)
        if cur is not None and cur.get("id") == self.st["id"]:   # murid yang sedang login
            fresh = ST.lookup_student(sid)
            app._student = fresh
            scr = getattr(app, "_screen", None)
            if scr is not None and getattr(scr, "student", None) is not None:
                scr.student = fresh
        try:
            app.rebuild_screen()     # perubahan langsung terlihat di aplikasi
        except Exception as exc:
            C.log(f"Dev: layar tidak dibangun ulang: {exc!r}")
        self.destroy()
