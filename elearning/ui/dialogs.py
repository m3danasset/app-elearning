"""Kotak dialog kecil bertema gelap untuk layar guru (tambah murid, ubah nama)."""

import tkinter as tk

from elearning import config as C
from elearning import students as S
from elearning.ui.widgets import add_hover

PROGRAMS = (("adult", "Murid dewasa"), ("kids", "Murid anak"))


class StudentDialog(tk.Toplevel):
    """Dialog tambah murid (add=True) atau ubah nama (add=False).

    on_submit(nama, kategori, id) dipanggil saat tombol Simpan diklik. Kalau
    mengembalikan teks, teks itu ditampilkan sebagai pesan kesalahan dan dialog
    tetap terbuka; kalau mengembalikan None, dialog ditutup.
    """

    def __init__(self, master, title, on_submit, add=True, name="",
                 program="adult", submit_text="Simpan"):
        super().__init__(master, bg=C.CARD, highlightthickness=1,
                         highlightbackground=C.BORDER)
        self.title(title)
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        try:
            self.iconbitmap(C.ICON_PATH)
        except Exception:
            pass
        self.on_submit = on_submit
        self.add = add
        self.program = program
        self._auto_id = ""        # ID saran terakhir; kalau guru sudah mengubahnya, jangan ditimpa

        body = tk.Frame(self, bg=C.CARD, padx=28, pady=22)
        body.pack(fill="both", expand=True)
        tk.Label(body, text=title, bg=C.CARD, fg=C.TEXT,
                 font=(C.FONT, 14, "bold"), anchor="w").pack(fill="x", pady=(0, 14))

        self.name_var = tk.StringVar(value=name)
        self.name_entry = self._field(body, "Nama murid", self.name_var, 32)

        if add:
            tk.Label(body, text="Kategori", bg=C.CARD, fg=C.MUTED,
                     font=(C.FONT, 10), anchor="w").pack(fill="x", pady=(12, 0))
            row = tk.Frame(body, bg=C.CARD)
            row.pack(fill="x", pady=(6, 0))
            self._prog_btns = {}
            for key, label in PROGRAMS:
                b = tk.Button(row, text=label, relief="flat", bd=0,
                              highlightthickness=0, cursor="hand2",
                              font=(C.FONT, 10, "bold"), padx=16, pady=6,
                              command=lambda k=key: self._set_program(k))
                b.pack(side="left", padx=(0, 8))
                self._prog_btns[key] = b

            self.id_var = tk.StringVar()
            self.id_entry = self._field(body, "ID murid (dipakai untuk login)",
                                        self.id_var, 32, pady=12)
            tk.Label(body, text="ID dibuat otomatis; boleh diganti. "
                                "Semua kursus murid baru terkunci dulu.",
                     bg=C.CARD, fg=C.MUTED, font=(C.FONT, 9), anchor="w",
                     wraplength=330, justify="left").pack(fill="x", pady=(6, 0))
            self._set_program(program)

        self.error = tk.Label(body, text="", bg=C.CARD, fg=C.ERROR,
                              font=(C.FONT, 10), anchor="w", wraplength=330,
                              justify="left")
        self.error.pack(fill="x", pady=(10, 0))

        btns = tk.Frame(body, bg=C.CARD)
        btns.pack(fill="x", pady=(10, 0))
        ok = tk.Button(btns, text=submit_text, command=self._submit, bg=C.ACCENT,
                       fg="white", activebackground=C.ACCENT_HOVER,
                       activeforeground="white", relief="flat", bd=0,
                       highlightthickness=0, font=(C.FONT, 11, "bold"),
                       cursor="hand2", padx=22, pady=7)
        ok.pack(side="right")
        add_hover(ok, C.ACCENT, C.ACCENT_HOVER)
        cancel = tk.Button(btns, text="Batal", command=self.destroy, bg=C.CARD,
                           fg=C.MUTED, activebackground=C.BORDER,
                           activeforeground=C.TEXT, relief="flat", bd=0,
                           highlightthickness=0, font=(C.FONT, 11),
                           cursor="hand2", padx=18, pady=7)
        cancel.pack(side="right", padx=(0, 8))
        add_hover(cancel, C.CARD, C.BORDER)

        self.bind("<Return>", lambda e: self._submit())
        self.bind("<Escape>", lambda e: self.destroy())
        self._center(master.winfo_toplevel())
        self.name_entry.focus_set()
        self.name_entry.select_range(0, "end")
        try:
            self.wait_visibility()
            self.grab_set()   # modal: jendela guru di belakang tidak bisa diklik
        except tk.TclError:
            pass

    # --- bagian-bagian dialog ---------------------------------------------------
    @staticmethod
    def _field(parent, label, var, width, pady=0):
        wrap = tk.Frame(parent, bg=C.CARD)
        wrap.pack(fill="x", pady=(pady, 0))
        tk.Label(wrap, text=label, bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10),
                 anchor="w").pack(fill="x")
        border = tk.Frame(wrap, bg=C.BORDER, padx=1, pady=1)
        border.pack(fill="x", pady=(6, 0))
        entry = tk.Entry(border, textvariable=var, width=width, bg=C.BG, fg=C.TEXT,
                         insertbackground=C.TEXT, relief="flat", font=(C.FONT, 12))
        entry.pack(fill="x", ipady=7, padx=1, pady=1)
        entry.bind("<FocusIn>", lambda e: border.config(bg=C.ACCENT))
        entry.bind("<FocusOut>", lambda e: border.config(bg=C.BORDER))
        return entry

    def _set_program(self, key):
        self.program = key
        for k, b in self._prog_btns.items():
            on = k == key
            b.config(bg=C.ACCENT if on else C.BG, fg="white" if on else C.MUTED,
                     activebackground=C.ACCENT_HOVER if on else C.BORDER,
                     activeforeground="white" if on else C.TEXT)
        if self.id_var.get().strip() in ("", self._auto_id):  # ID saran ikut berganti
            try:                                              # (PB... / SK...) kecuali
                self._auto_id = S.next_student_id(key)        # sudah diubah guru
                self.id_var.set(self._auto_id)
            except Exception:
                pass

    def _center(self, parent):
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _submit(self):
        sid = self.id_var.get() if self.add else None
        try:
            err = self.on_submit(self.name_var.get(), self.program, sid)
        except Exception as exc:  # jangan sampai dialog macet karena error tak terduga
            C.log(f"Dialog murid gagal: {exc!r}")
            err = "Gagal menyimpan. Pastikan folder data bisa ditulis."
        if err:
            self.error.config(text=err)
        else:
            self.destroy()


class ConfirmDialog(tk.Toplevel):
    """Dialog konfirmasi untuk tindakan yang tidak bisa dibatalkan (mis. hapus murid).

    on_confirm() dipanggil saat tombol konfirmasi diklik. Kalau mengembalikan teks,
    teks itu ditampilkan sebagai pesan kesalahan dan dialog tetap terbuka.
    Fokus awal ada di Batal supaya tidak terhapus karena salah tekan Enter.
    """

    DANGER = "#e5484d"
    DANGER_HOVER = "#ff6369"

    def __init__(self, master, title, message, on_confirm, confirm_text="Hapus"):
        super().__init__(master, bg=C.CARD, highlightthickness=1,
                         highlightbackground=C.BORDER)
        self.title(title)
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        try:
            self.iconbitmap(C.ICON_PATH)
        except Exception:
            pass
        self.on_confirm = on_confirm

        body = tk.Frame(self, bg=C.CARD, padx=28, pady=22)
        body.pack(fill="both", expand=True)
        tk.Label(body, text=title, bg=C.CARD, fg=C.TEXT,
                 font=(C.FONT, 14, "bold"), anchor="w").pack(fill="x")
        tk.Label(body, text=message, bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10),
                 anchor="w", justify="left", wraplength=340).pack(fill="x", pady=(10, 0))
        self.error = tk.Label(body, text="", bg=C.CARD, fg=C.ERROR,
                              font=(C.FONT, 10), anchor="w", wraplength=340,
                              justify="left")
        self.error.pack(fill="x", pady=(8, 0))

        btns = tk.Frame(body, bg=C.CARD)
        btns.pack(fill="x", pady=(10, 0))
        ok = tk.Button(btns, text=confirm_text, command=self._confirm,
                       bg=self.DANGER, fg="white", activebackground=self.DANGER_HOVER,
                       activeforeground="white", relief="flat", bd=0,
                       highlightthickness=0, font=(C.FONT, 11, "bold"),
                       cursor="hand2", padx=22, pady=7)
        ok.pack(side="right")
        add_hover(ok, self.DANGER, self.DANGER_HOVER)
        self.cancel = tk.Button(btns, text="Batal", command=self.destroy, bg=C.BORDER,
                                fg=C.TEXT, activebackground=C.CARD_HOVER,
                                activeforeground=C.TEXT, relief="flat", bd=0,
                                highlightthickness=0, font=(C.FONT, 11),
                                cursor="hand2", padx=18, pady=7)
        self.cancel.pack(side="right", padx=(0, 8))
        add_hover(self.cancel, C.BORDER, C.CARD_HOVER)

        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        parent = master.winfo_toplevel()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.cancel.focus_set()
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass

    def _confirm(self):
        try:
            err = self.on_confirm()
        except Exception as exc:
            C.log(f"Dialog konfirmasi gagal: {exc!r}")
            err = "Gagal. Pastikan folder data bisa ditulis."
        if err:
            self.error.config(text=err)
        else:
            self.destroy()
