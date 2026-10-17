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
        self.geometry(f"360x520+{app.winfo_rootx() + 40}+{app.winfo_rooty() + 60}")
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
        self.items = accounts()
        self.q = tk.StringVar()
        e = tk.Entry(self.body, textvariable=self.q, font=FONT, bg=FIELD, fg=FG,
                     insertbackground=FG, relief="flat")
        e.pack(fill="x", ipady=4)
        self.lb = tk.Listbox(self.body, font=FONT, bg=FIELD, fg=FG, relief="flat",
                             selectbackground=C.ACCENT, selectforeground="white",
                             highlightthickness=0, activestyle="none")
        self.lb.pack(fill="both", expand=True, pady=(6, 6))
        tk.Button(self.body, text="Masuk", font=BOLD, relief="flat", bg=C.ACCENT, fg="white",
                  activebackground=C.ACCENT_HOVER, activeforeground="white",
                  command=self._login).pack(fill="x", ipady=3)
        self._kind = KIND

        def refill(*_a):
            q = self.q.get().strip().lower()
            self.shown = [it for it in self.items if not q or q in it[2].lower()
                          or q in it[1].lower() or q in KIND[it[0]][0].lower()]
            self.lb.delete(0, "end")
            for kind, uid, name, _acc in self.shown:
                self.lb.insert("end", f"{KIND[kind][0]:<10} {uid:<9} {name}")
            if self.shown:
                self.lb.selection_set(0)
        self.q.trace_add("write", refill)
        refill()
        e.bind("<Return>", lambda ev: self._login())
        e.bind("<Down>", lambda ev: self._move(1))
        e.bind("<Up>", lambda ev: self._move(-1))
        self.lb.bind("<Double-Button-1>", lambda ev: self._login())
        e.focus_set()

    def _move(self, d):
        sel = self.lb.curselection()
        i = max(0, min(len(self.shown) - 1, (sel[0] if sel else 0) + d))
        self.lb.selection_clear(0, "end")
        self.lb.selection_set(i)
        self.lb.see(i)
        return "break"

    def _login(self):
        sel = self.lb.curselection()
        if not sel or not self.shown:
            return
        kind, _uid, _name, acc = self.shown[sel[0]]
        if kind == "trial":
            from elearning.trial import trial_student
            acc = trial_student()
        self.app.dev_login(kind, acc)
        self._note(f"Masuk: {_name}")

    # --- Settings ---------------------------------------------------------------------------
    def _section(self, text):
        tk.Label(self.body, text=text, bg=BG, fg=MUTED, font=BOLD, anchor="w").pack(
            fill="x", pady=(8, 2))

    def _settings_tab(self):
        self._section("Tampilan login")
        mode = tk.StringVar(value=S.login_mode())
        for key, label in LOGIN_LABELS:
            tk.Radiobutton(self.body, text=label, value=key, variable=mode, font=FONT,
                           bg=BG, fg=FG, selectcolor=FIELD, activebackground=BG,
                           activeforeground=FG, anchor="w",
                           command=lambda: self._save("login_mode", mode.get(),
                                                      "Tampilan login")).pack(fill="x")
        self._section("Warna aksen  (buka ulang app)")
        acc = tk.StringVar(value=S.get("accent"))
        row = tk.Frame(self.body, bg=BG)
        row.pack(fill="x")
        for n, (key, (name, color, _hover)) in enumerate(S.ACCENTS.items()):
            tk.Radiobutton(row, text=name, value=key, variable=acc, font=FONT, bg=BG,
                           fg=color, selectcolor=FIELD, activebackground=BG,
                           activeforeground=color, anchor="w",
                           command=lambda: self._save("accent", acc.get(), "Warna aksen")
                           ).grid(row=n // 3, column=n % 3, sticky="w", padx=(0, 6))
        self._section("Fitur")
        for key, label in S.FEATURES:
            v = tk.BooleanVar(value=S.feature(key))
            tk.Checkbutton(self.body, text=label, variable=v, font=FONT, bg=BG, fg=FG,
                           selectcolor=FIELD, activebackground=BG, activeforeground=FG,
                           anchor="w",
                           command=lambda k=key, var=v, lb=label: self._feature(k, var.get(), lb)
                           ).pack(fill="x")
        tk.Label(self.body, text=f"PC kuat (NVIDIA + >=12 thread): "
                                 f"{'ya' if getattr(C, 'HIGH_END', False) else 'tidak'}",
                 bg=BG, fg=MUTED, font=FONT, anchor="w").pack(fill="x", pady=(8, 0))

    def _save(self, key, value, label):
        try:
            S.set(key, value)
        except OSError as exc:
            C.log(f"Dev: {key} gagal disimpan: {exc!r}")
            self._note("Gagal menyimpan (folder data?).")
            return
        self._note(f"Tersimpan: {label} = {value}")

    def _feature(self, key, on, label):
        try:
            S.set_feature(key, on)
        except OSError as exc:
            C.log(f"Dev: fitur {key} gagal disimpan: {exc!r}")
            self._note("Gagal menyimpan (folder data?).")
            return
        self._note(f"{label}: {'ON' if on else 'OFF'} (berlaku di layar berikutnya)")

    def destroy(self):
        _open["win"] = None
        super().destroy()
