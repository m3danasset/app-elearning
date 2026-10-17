"""Dialog Export Excel (Panel Admin): pilih periode, data, dan folder tujuan.

Folder terakhir yang dipilih diingat (data\\export_folder.txt). File dibuat di thread
terpisah supaya jendela tidak macet; setelah selesai, admin bisa langsung membuka
file atau foldernya.
"""

import os
import subprocess
import sys
import threading
import tkinter as tk

# CATATAN: sengaja TIDAK memakai tkinter.filedialog (tidak ikut terbungkus di .exe).
# Pilih folder lewat perintah Tk bawaan tk_chooseDirectory, seperti tk_getOpenFile di
# teacher_screen.py.

from elearning import config as C
from elearning import excel_export as X
from elearning.ui.controls import RoundButton, RoundCheck as Check, RoundSelect, dark_titlebar
from elearning.ui.widgets import add_hover

W = 420   # lebar isi dialog


def _short(path, limit=52):
    return path if len(path) <= limit else "…" + path[-(limit - 1):]


def _open(path, select=False):
    try:
        if sys.platform.startswith("win"):
            if select:
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            else:
                os.startfile(path)   # noqa: windows saja
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path] if select else ["open", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path) if select else path])
    except Exception as exc:
        C.log(f"Gagal membuka {path!r}: {exc!r}")


class ExportDialog(tk.Toplevel):
    def __init__(self, master, default_who="all"):
        super().__init__(master, bg=C.CARD, highlightthickness=1,
                         highlightbackground=C.BORDER)
        self.title("Export Excel")
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        dark_titlebar(self)
        try:
            self.iconbitmap(C.ICON_PATH)
        except Exception:
            pass
        self._busy = False
        self._path = None
        self._periods = X.periods()
        self.folder = X.default_folder()

        body = tk.Frame(self, bg=C.CARD, padx=28, pady=22)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="Export Excel", bg=C.CARD, fg=C.TEXT,
                 font=(C.FONT, 14, "bold"), anchor="w").pack(fill="x")
        tk.Label(body, text="Semua data disimpan dalam SATU file Excel (.xlsx); tiap bagian "
                 "menjadi satu sheet. Centang bagian yang mau ikut.", bg=C.CARD, fg=C.MUTED,
                 font=(C.FONT, 10), anchor="w", justify="left", wraplength=W).pack(
            fill="x", pady=(6, 14))

        grid = tk.Frame(body, bg=C.CARD)
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)

        def label(row, text):
            tk.Label(grid, text=text, bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10),
                     anchor="w").grid(row=row, column=0, sticky="w", padx=(0, 16), pady=6)

        label(0, "Periode")
        self.period_var = tk.StringVar(value=self._periods[0][0])
        RoundSelect(grid, self.period_var, *[p[0] for p in self._periods],
                    bg=C.BORDER).grid(row=0, column=1, sticky="w", pady=6)
        label(1, "Data")
        who = dict(X.WHO)
        self._who_keys = {v: k for k, v in X.WHO}
        self.who_var = tk.StringVar(value=who.get(default_who, who["all"]))
        RoundSelect(grid, self.who_var, *who.values(), bg=C.BORDER).grid(
            row=1, column=1, sticky="w", pady=6)
        label(2, "Simpan ke")
        frow = tk.Frame(grid, bg=C.CARD)
        frow.grid(row=2, column=1, sticky="we", pady=6)
        self.folder_lbl = tk.Label(frow, text="", bg=C.CARD, fg=C.TEXT, font=(C.FONT, 10),
                                   anchor="w")
        self.folder_lbl.pack(side="left")
        RoundButton(frow, text="Pilih folder…", command=self._choose, bg=C.BORDER,
                    activebackground=C.CARD_HOVER, font=(C.FONT, 10), padx=12,
                    pady=5).pack(side="left", padx=(10, 0))
        self._show_folder()

        label(3, "Isi file")
        boxes = tk.Frame(grid, bg=C.CARD)
        boxes.grid(row=4, column=0, columnspan=2, sticky="we", pady=(0, 2))
        chosen = X.load_sheets()
        self.checks = {}
        for i, (key, text) in enumerate(X.SHEETS):
            cb = Check(boxes, text, key in chosen, command=self._checks_changed)
            cb.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 18), pady=2)
            self.checks[key] = cb
        self.all_btn = tk.Label(grid, text="", bg=C.CARD, fg=C.ACCENT, cursor="hand2",
                                font=(C.FONT, 10))
        self.all_btn.grid(row=3, column=1, sticky="e")
        self.all_btn.bind("<Button-1>", lambda e: self._toggle_all())
        self._checks_changed()

        self.msg = tk.Label(body, text="", bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10), height=3,
                            anchor="nw", justify="left", wraplength=W)
        self.msg.pack(fill="x", pady=(12, 0))

        self.btns = tk.Frame(body, bg=C.CARD)
        self.btns.pack(fill="x", pady=(12, 0))
        self._form_buttons()

        self.bind("<Escape>", lambda e: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._center(master)
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass

    # --- tampilan ------------------------------------------------------------------------
    def _center(self, master):
        self.update_idletasks()
        parent = master.winfo_toplevel()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _show_folder(self):
        self.folder_lbl.config(text=_short(self.folder, 34))

    def _button(self, text, command, primary=False):
        if primary:
            b = RoundButton(self.btns, text=text, command=command, bg=C.ACCENT, fg="white",
                            activebackground=C.ACCENT_HOVER, activeforeground="white",
                            font=(C.FONT, 11, "bold"), padx=22, pady=7)
            add_hover(b, C.ACCENT, C.ACCENT_HOVER)
        else:
            b = RoundButton(self.btns, text=text, command=command, bg=C.BORDER, fg=C.TEXT,
                            activebackground=C.CARD_HOVER, font=(C.FONT, 11),
                            padx=18, pady=7)
            add_hover(b, C.BORDER, C.CARD_HOVER)
        b.pack(side="right", padx=(8, 0))
        return b

    def _form_buttons(self):
        for w in self.btns.winfo_children():
            w.destroy()
        self.ok = self._button("Export", self._export, primary=True)
        self._button("Batal", self._close)
        self.ok.focus_set()
        self.bind("<Return>", lambda e: self._export())

    def _done_buttons(self):
        for w in self.btns.winfo_children():
            w.destroy()
        b = self._button("Buka file", lambda: (_open(self._path), self._close()), primary=True)
        self._button("Buka folder", lambda: _open(self._path, select=True))
        self._button("Export lagi", self._again)
        b.focus_set()
        self.bind("<Return>", lambda e: (_open(self._path), self._close()))

    # --- aksi ----------------------------------------------------------------------------
    def _choose(self):
        if self._busy:
            return
        try:
            path = self.tk.call("tk_chooseDirectory", "-parent", self, "-initialdir",
                                self.folder, "-mustexist", 1,
                                "-title", "Pilih folder untuk menyimpan file Excel")
        except tk.TclError as exc:
            C.log(f"Dialog pilih folder gagal: {exc!r}")
            path = ""
        path = str(path or "")
        if path:
            self.folder = os.path.normpath(path)
            X.remember_folder(self.folder)
            self._show_folder()

    def _chosen(self):
        return {k for k, cb in self.checks.items() if cb.value}

    def _checks_changed(self):
        every = len(self._chosen()) == len(self.checks)
        self.all_btn.config(text="Kosongkan" if every else "Pilih semua")
        if hasattr(self, "msg") and self.msg.cget("fg") == C.ERROR:
            self.msg.config(text="", fg=C.MUTED)

    def _toggle_all(self):
        every = len(self._chosen()) == len(self.checks)
        for cb in self.checks.values():
            cb.set(not every)
        self._checks_changed()

    def _again(self):
        self._path = None
        self.msg.config(text="", fg=C.MUTED)
        self._form_buttons()

    def _export(self):
        if self._busy or self._path is not None:
            return
        if not os.path.isdir(self.folder):
            self.msg.config(text="Folder tidak ditemukan. Pilih folder lain.", fg=C.ERROR)
            return
        sheets = self._chosen()
        if not sheets:
            self.msg.config(text="Centang minimal satu isi file.", fg=C.ERROR)
            return
        X.save_sheets(sheets)
        label = self.period_var.get()
        _l, start, end, fname = next(p for p in self._periods if p[0] == label)
        who = self._who_keys.get(self.who_var.get(), "all")
        suffix = "" if who == "all" else f" - {self.who_var.get()}"
        path = X.free_name(self.folder, f"Data E-Learning {fname}{suffix}")
        self._busy = True
        self.ok.configure(text="Menyimpan…")
        self.msg.config(text="", fg=C.MUTED)
        box = {}

        def work():
            try:
                box["n"] = X.export(path, fname, start, end, who, sheets)
            except Exception as exc:
                C.log(f"Export Excel gagal: {exc!r}")
                box["err"] = exc

        threading.Thread(target=work, daemon=True).start()
        self._poll(box, path)

    def _poll(self, box, path):
        if not self.winfo_exists():
            return
        if not box:
            self.after(60, lambda: self._poll(box, path))
            return
        self._busy = False
        if "err" in box:
            self.ok.configure(text="Export")
            err = box["err"]
            why = ("Folder itu tidak bisa ditulis. Pilih folder lain."
                   if isinstance(err, PermissionError) else "Gagal menyimpan. Lihat app.log.")
            self.msg.config(text=why, fg=C.ERROR)
            return
        self._path = path
        n = box["n"]
        X.remember_folder(self.folder)
        k = len(self._chosen()) + (2 if "progress" in self._chosen() else 0)
        self.msg.config(text=f"Tersimpan: {os.path.basename(path)}\n"
                        f"{k} sheet  ·  {n} sesi login", fg=C.ON)
        self._done_buttons()

    def _close(self):
        if not self._busy:
            self.destroy()
