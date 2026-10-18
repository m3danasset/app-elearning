"""Kotak dialog kecil bertema gelap untuk layar guru (tambah murid, ubah nama, tulis laporan)."""

import tkinter as tk
from datetime import date

from elearning.i18n import L
from elearning import config as C
from elearning import photos, reports
from elearning import students as S
from elearning.ui.avatar import Avatar
from elearning.ui.report_widgets import KIND_COLOR
from elearning.ui.controls import (RoundButton, RoundEntry, RoundPanel, RoundSelect,
                                   WheelPicker, dark_titlebar)
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
        dark_titlebar(self)
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
                b = RoundButton(row, text=label, relief="flat", bd=0,
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
        ok = RoundButton(btns, text=submit_text, command=self._submit, bg=C.ACCENT,
                       fg="white", activebackground=C.ACCENT_HOVER,
                       activeforeground="white", relief="flat", bd=0,
                       highlightthickness=0, font=(C.FONT, 11, "bold"),
                       cursor="hand2", padx=22, pady=7)
        ok.pack(side="right")
        add_hover(ok, C.ACCENT, C.ACCENT_HOVER)
        cancel = RoundButton(btns, text="Batal", command=self.destroy, bg=C.CARD,
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
    def _field(parent, label, var, width, pady=0, show=None):
        wrap = tk.Frame(parent, bg=C.CARD)
        wrap.pack(fill="x", pady=(pady, 0))
        tk.Label(wrap, text=label, bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10),
                 anchor="w").pack(fill="x")
        box = RoundEntry(wrap, var, show=show, width_chars=width, font=(C.FONT, 12),
                         height=40, fill=C.BG, radius=9)
        box.pack(fill="x", pady=(6, 0))
        return box.entry

    def _set_program(self, key):
        self.program = key
        for k, b in self._prog_btns.items():
            on = k == key
            b.config(bg=C.SEG_ON if on else C.BG, fg=C.TEXT if on else C.MUTED,
                     activebackground=C.SEG_ON if on else C.CARD_HOVER,
                     activeforeground=C.TEXT)
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
        dark_titlebar(self)
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
        ok = RoundButton(btns, text=confirm_text, command=self._confirm,
                       bg=self.DANGER, fg="white", activebackground=self.DANGER_HOVER,
                       activeforeground="white", relief="flat", bd=0,
                       highlightthickness=0, font=(C.FONT, 11, "bold"),
                       cursor="hand2", padx=22, pady=7)
        ok.pack(side="right")
        add_hover(ok, self.DANGER, self.DANGER_HOVER)
        self.cancel = RoundButton(btns, text=L("Batal", "Cancel"), command=self.destroy,
                                  bg=C.BORDER,
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


class MiniConfirm(tk.Toplevel):
    """Popup konfirmasi mini (keluar / tutup aplikasi): hanya pertanyaan + 2 tombol.

    Tanpa bilah judul Windows; kartu bersudut bulat (warna kunci transparan seperti splash).
    Fokus awal di Batal: Enter / Esc yang tak sengaja tidak menutup apa pun.
    Tab / panah = pindah tombol. self.result = True kalau dikonfirmasi.
    """

    KEY = "#010203"
    W, H, R = 268, 104, 14
    BW, BH = 76, 32
    DANGER, DANGER_HOVER = "#e5484d", "#ff6369"

    def __init__(self, master, question, confirm_text="Keluar"):
        from elearning.ui import ui_icons as I
        top = master.winfo_toplevel()
        super().__init__(top, bg=self.KEY)
        self.withdraw()
        self.overrideredirect(True)
        self.transient(top)
        self.result = False
        rounded = True
        try:
            self.attributes("-transparentcolor", self.KEY)
        except tk.TclError:
            rounded = False
        outer = self.KEY if rounded else C.CARD
        cv = tk.Canvas(self, width=self.W, height=self.H, bg=outer, highlightthickness=0, bd=0)
        cv.pack()
        self.cv, self.I = cv, I
        self._card = I.pill(self.W, self.H, C.CARD, outer, r=self.R, border=C.BORDER)
        if self._card is not None:
            cv.create_image(0, 0, image=self._card, anchor="nw")
        cv.create_text(20, 30, text=question, anchor="w", fill=C.TEXT,
                       font=(C.FONT, 12, "bold"))

        y = self.H - 16 - self.BH
        x_ok = self.W - 16 - self.BW
        x_no = x_ok - 8 - self.BW
        self._btns = {
            "no": dict(x=x_no, y=y, text=L("Batal", "Cancel"), fill=C.BORDER,
                       hover=C.CARD_HOVER,
                       fg=C.TEXT, bold=False),
            "ok": dict(x=x_ok, y=y, text=confirm_text, fill=self.DANGER,
                       hover=self.DANGER_HOVER, fg="white", bold=True),
        }
        for name, b in self._btns.items():
            b["img"] = cv.create_image(b["x"], b["y"], anchor="nw")
            b["txt"] = cv.create_text(b["x"] + self.BW / 2, b["y"] + self.BH / 2, text=b["text"],
                                      fill=b["fg"], font=(C.FONT, 10, "bold" if b["bold"] else ""))
            for item in (b["img"], b["txt"]):
                cv.tag_bind(item, "<Enter>", lambda e, n=name: self._hover(n, True))
                cv.tag_bind(item, "<Leave>", lambda e, n=name: self._hover(n, False))
                cv.tag_bind(item, "<Button-1>", lambda e, n=name: self._press(n))
        self._hovered = None
        self._focus = "no"
        self._draw()

        self.bind("<Escape>", lambda e: self._press("no"))
        self.bind("<Return>", lambda e: self._press(self._focus))
        self.bind("<space>", lambda e: self._press(self._focus))
        for key in ("<Tab>", "<Left>", "<Right>"):
            self.bind(key, lambda e: self._move())

        self.update_idletasks()
        x = top.winfo_rootx() + (top.winfo_width() - self.W) // 2
        y = top.winfo_rooty() + (top.winfo_height() - self.H) // 2
        self.geometry(f"{self.W}x{self.H}+{max(0, x)}+{max(0, y)}")
        self.deiconify()
        self.lift()
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_force()

    def _draw(self):
        for name, b in self._btns.items():
            fill = b["hover"] if self._hovered == name else b["fill"]
            ring = C.TEXT if self._focus == name else None   # tanda tombol aktif (keyboard)
            b["ph"] = self.I.pill(self.BW, self.BH, fill, C.CARD, r=8, border=ring)
            self.cv.itemconfigure(b["img"], image=b["ph"])
        self.cv.configure(cursor="hand2" if self._hovered else "")

    def _hover(self, name, on):
        self._hovered = name if on else None
        self._draw()

    def _move(self):
        self._focus = "ok" if self._focus == "no" else "no"
        self._draw()
        return "break"

    def _press(self, name):
        self.result = name == "ok"
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


class ReportDialog(tk.Toplevel):
    """Dialog tulis laporan kerja (rec=None) atau ubah laporan (rec = item reports.list_reports).

    on_submit(tanggal_teks, jenis, id_murid, catatan) dipanggil saat tombol Simpan diklik.
    Kalau mengembalikan teks, teks itu ditampilkan sebagai pesan kesalahan dan dialog
    tetap terbuka; kalau mengembalikan None, dialog ditutup.
    """

    NO_STUDENT = "Umum (tidak terkait murid)"

    def __init__(self, master, students, on_submit, rec=None, default_kind="student"):
        super().__init__(master, bg=C.CARD, highlightthickness=1,
                         highlightbackground=C.BORDER)
        title = "Ubah laporan" if rec else "Tulis laporan"
        self.title(title)
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        dark_titlebar(self)
        try:
            self.iconbitmap(C.ICON_PATH)
        except Exception:
            pass
        self.on_submit = on_submit
        self.kind = rec["kind"] if rec else default_kind

        body = tk.Frame(self, bg=C.CARD, padx=28, pady=22)
        body.pack(fill="both", expand=True)
        tk.Label(body, text=title, bg=C.CARD, fg=C.TEXT,
                 font=(C.FONT, 14, "bold"), anchor="w").pack(fill="x", pady=(0, 6))

        day = reports.format_day(rec["day"] if rec else date.today())
        self.date_var = tk.StringVar(value=day)
        StudentDialog._field(body, "Tanggal (hari/bulan/tahun)", self.date_var, 36, pady=8)

        tk.Label(body, text="Jenis laporan", bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10),
                 anchor="w").pack(fill="x", pady=(12, 0))
        chips = tk.Frame(body, bg=C.CARD)
        chips.pack(fill="x", pady=(6, 0))
        self._kind_btns = {}
        for i, (key, label) in enumerate(reports.KINDS):
            b = RoundButton(chips, text=label, command=lambda k=key: self._set_kind(k),
                          relief="flat", bd=0, highlightthickness=0, cursor="hand2",
                          font=(C.FONT, 9, "bold"), padx=8, pady=5)
            b.grid(row=i // 3, column=i % 3, sticky="ew", padx=(0, 6), pady=(0, 6))
            self._kind_btns[key] = b
        for c in range(3):
            chips.grid_columnconfigure(c, weight=1, uniform="kind")

        self.student_lbl = tk.Label(body, text="Murid", bg=C.CARD, fg=C.MUTED,
                                    font=(C.FONT, 10), anchor="w")
        self.student_lbl.pack(fill="x", pady=(6, 0))
        self._ids = {self.NO_STUDENT: ""}
        labels = [self.NO_STUDENT]
        chosen = self.NO_STUDENT
        for s in students:
            label = f"{s['id']}   {s['name']}"
            self._ids[label] = s["id"]
            labels.append(label)
            if rec and s["id"] == rec["student"]:
                chosen = label
        self.student_var = tk.StringVar(value=chosen)
        menu = RoundSelect(body, self.student_var, *labels, bg=C.BG)
        menu.pack(fill="x", pady=(6, 0), ipady=3)

        tk.Label(body, text="Catatan", bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10),
                 anchor="w").pack(fill="x", pady=(12, 0))
        border = RoundPanel(body, fill=C.BG, padx=6, pady=6, radius=10)
        border.pack(fill="x", pady=(6, 0))
        self.text = tk.Text(border.inner, width=40, height=7, wrap="word", bg=C.BG, fg=C.TEXT,
                            insertbackground=C.TEXT, relief="flat", highlightthickness=0,
                            font=(C.FONT, 11), padx=8, pady=6, undo=True)
        self.text.pack(fill="x")
        self.text.bind("<FocusIn>", lambda e: border.set_style(border=RoundEntry.FOCUS_BORDER))
        self.text.bind("<FocusOut>", lambda e: border.set_style(border=C.BORDER))
        if rec:
            self.text.insert("1.0", rec["text"])

        self.error = tk.Label(body, text="", bg=C.CARD, fg=C.ERROR, font=(C.FONT, 10),
                              anchor="w", wraplength=380, justify="left")
        self.error.pack(fill="x", pady=(10, 0))

        btns = tk.Frame(body, bg=C.CARD)
        btns.pack(fill="x", pady=(10, 0))
        ok = RoundButton(btns, text="Simpan perubahan" if rec else "Simpan laporan",
                       command=self._submit, bg=C.ACCENT, fg="white",
                       activebackground=C.ACCENT_HOVER, activeforeground="white",
                       relief="flat", bd=0, highlightthickness=0,
                       font=(C.FONT, 11, "bold"), cursor="hand2", padx=22, pady=7)
        ok.pack(side="right")
        add_hover(ok, C.ACCENT, C.ACCENT_HOVER)
        cancel = RoundButton(btns, text="Batal", command=self.destroy, bg=C.CARD,
                           fg=C.MUTED, activebackground=C.BORDER,
                           activeforeground=C.TEXT, relief="flat", bd=0,
                           highlightthickness=0, font=(C.FONT, 11),
                           cursor="hand2", padx=18, pady=7)
        cancel.pack(side="right", padx=(0, 8))
        add_hover(cancel, C.CARD, C.BORDER)

        self.bind("<Escape>", lambda e: self.destroy())   # Enter tidak dipakai: catatan butuh baris baru
        self._set_kind(self.kind)
        self._center(master.winfo_toplevel())
        self.text.focus_set()
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass

    def _center(self, parent):
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _set_kind(self, key):
        self.kind = key
        for k, b in self._kind_btns.items():
            on = k == key
            color = KIND_COLOR.get(k, C.MUTED)
            b.config(bg=color if on else C.BG, fg="white" if on else C.MUTED,
                     activebackground=color if on else C.BORDER,
                     activeforeground="white" if on else C.TEXT)
        need = key in reports.STUDENT_KINDS
        self.student_lbl.config(text="Murid" if need else "Murid (boleh dikosongkan)")

    def _submit(self):
        sid = self._ids.get(self.student_var.get(), "")
        try:
            err = self.on_submit(self.date_var.get(), self.kind, sid,
                                 self.text.get("1.0", "end"))
        except Exception as exc:  # jangan sampai dialog macet karena error tak terduga
            C.log(f"Dialog laporan gagal: {exc!r}")
            err = "Gagal menyimpan. Pastikan folder data bisa ditulis."
        if err:
            self.error.config(text=err)
        else:
            self.destroy()


class TeacherDialog(tk.Toplevel):
    """Dialog tambah guru (add=True) atau ubah guru (add=False): foto, nama, dan PIN.

    on_submit(nama, pin, foto) dipanggil saat tombol Simpan diklik.
      foto : None = tidak berubah, False = hapus foto, gambar Pillow = foto baru
      pin  : teks PIN (saat mengubah: kosong = PIN tidak diganti)
    Kalau mengembalikan teks, teks itu ditampilkan sebagai pesan kesalahan dan dialog
    tetap terbuka; kalau mengembalikan None, dialog ditutup. Foto baru baru disimpan
    ke disk oleh pemanggil, jadi menekan Batal tidak mengubah apa pun.
    """

    def __init__(self, master, title, on_submit, teacher_id, add=True, name="",
                 submit_text="Simpan"):
        super().__init__(master, bg=C.CARD, highlightthickness=1,
                         highlightbackground=C.BORDER)
        self.title(title)
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        dark_titlebar(self)
        try:
            self.iconbitmap(C.ICON_PATH)
        except Exception:
            pass
        self.on_submit = on_submit
        self.add = add
        self.teacher_id = teacher_id
        self._photo = None                                  # lihat 'foto' di atas
        self._on_disk = (not add) and photos.has_photo(teacher_id)

        body = tk.Frame(self, bg=C.CARD, padx=28, pady=22)
        body.pack(fill="both", expand=True)
        tk.Label(body, text=title, bg=C.CARD, fg=C.TEXT,
                 font=(C.FONT, 14, "bold"), anchor="w").pack(fill="x", pady=(0, 14))

        # Foto (pratinjau bulat) + tombol pilih / hapus
        top = tk.Frame(body, bg=C.CARD)
        top.pack(fill="x")
        self.avatar = Avatar(top, teacher_id, name, size=72, bg=C.CARD)
        if add:                       # guru baru: jangan pakai foto lama yang mungkin tersisa
            self.avatar.override = False
            self.avatar.refresh()
        self.avatar.pack(side="left", padx=(0, 16))
        side = tk.Frame(top, bg=C.CARD)
        side.pack(side="left", fill="x")
        tk.Label(side, text=f"ID login: {teacher_id}", bg=C.CARD, fg=C.MUTED,
                 font=(C.FONT, 10), anchor="w").pack(fill="x")
        row = tk.Frame(side, bg=C.CARD)
        row.pack(fill="x", pady=(8, 0))
        self.pick_btn = self._small_button(row, "Pilih foto…", self._pick_photo)
        self.pick_btn.pack(side="left")
        self.clear_btn = self._small_button(row, "Hapus foto", self._clear_photo)
        self.clear_btn.pack(side="left", padx=(8, 0))

        self.name_var = tk.StringVar(value=name)
        self.name_entry = StudentDialog._field(body, "Nama guru", self.name_var, 32, pady=14)
        self.name_var.trace_add("write", lambda *_: self.avatar.set_student(
            self.teacher_id, self.name_var.get()))   # inisial ikut berubah saat mengetik

        self.pin_var = tk.StringVar()
        StudentDialog._field(
            body, "PIN (untuk login)" if add else "PIN baru (kosongkan kalau tidak diganti)",
            self.pin_var, 32, pady=12)
        tk.Label(body, text="PIN 4-10 karakter tanpa spasi. Foto dipotong persegi dari tengah.",
                 bg=C.CARD, fg=C.MUTED, font=(C.FONT, 9), anchor="w",
                 wraplength=340, justify="left").pack(fill="x", pady=(6, 0))

        self.error = tk.Label(body, text="", bg=C.CARD, fg=C.ERROR,
                              font=(C.FONT, 10), anchor="w", wraplength=340,
                              justify="left")
        self.error.pack(fill="x", pady=(10, 0))

        btns = tk.Frame(body, bg=C.CARD)
        btns.pack(fill="x", pady=(10, 0))
        ok = RoundButton(btns, text=submit_text, command=self._submit, bg=C.ACCENT,
                       fg="white", activebackground=C.ACCENT_HOVER,
                       activeforeground="white", relief="flat", bd=0,
                       highlightthickness=0, font=(C.FONT, 11, "bold"),
                       cursor="hand2", padx=22, pady=7)
        ok.pack(side="right")
        add_hover(ok, C.ACCENT, C.ACCENT_HOVER)
        cancel = RoundButton(btns, text="Batal", command=self.destroy, bg=C.CARD,
                           fg=C.MUTED, activebackground=C.BORDER,
                           activeforeground=C.TEXT, relief="flat", bd=0,
                           highlightthickness=0, font=(C.FONT, 11),
                           cursor="hand2", padx=18, pady=7)
        cancel.pack(side="right", padx=(0, 8))
        add_hover(cancel, C.CARD, C.BORDER)

        self._paint_photo_buttons()
        self.bind("<Return>", lambda e: self._submit())
        self.bind("<Escape>", lambda e: self.destroy())
        self._center(master.winfo_toplevel())
        self.name_entry.focus_set()
        self.name_entry.select_range(0, "end")
        try:
            self.wait_visibility()
            self.grab_set()   # modal: Panel Admin di belakang tidak bisa diklik
        except tk.TclError:
            pass

    # --- foto ---------------------------------------------------------------------
    @staticmethod
    def _small_button(parent, text, command):
        btn = RoundButton(parent, text=text, command=command, bg=C.BG, fg=C.TEXT,
                        activebackground=C.BORDER, activeforeground=C.TEXT,
                        disabledforeground=C.LOCKED, relief="flat", bd=0,
                        highlightthickness=0, font=(C.FONT, 10), cursor="hand2",
                        padx=12, pady=5)
        add_hover(btn, C.BG, C.BORDER)
        return btn

    def _has_photo_now(self):
        if self._photo is False:
            return False
        return True if self._photo is not None else self._on_disk

    def _paint_photo_buttons(self):
        has = self._has_photo_now()
        self.pick_btn.config(text="Ganti foto…" if has else "Pilih foto…")
        self.clear_btn.config(state="normal" if has else "disabled")

    def _pick_photo(self):
        """Dialog pilih file bawaan Windows (lewat Tk, tanpa modul tambahan)."""
        try:
            result = self.tk.call(
                "tk_getOpenFile", "-parent", str(self), "-title", "Pilih foto guru",
                "-filetypes",
                (("Gambar", (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")),
                 ("Semua file", "*")))
            path = str(result).strip()
        except Exception as exc:
            C.log(f"Dialog pilih foto guru gagal: {exc!r}")
            self.error.config(text="Dialog pilih file tidak bisa dibuka.")
            return
        if not path:   # dibatalkan
            return
        try:
            img = photos.prepare_photo(path)
        except Exception as exc:
            C.log(f"Foto guru dari {path!r} tidak bisa dipakai: {exc!r}")
            self.error.config(
                text="Foto tidak bisa dipakai. Pilih file JPG atau PNG yang tidak rusak.")
            return
        self._photo = img
        self.avatar.override = img
        self.avatar.refresh()
        self.error.config(text="")
        self._paint_photo_buttons()

    def _clear_photo(self):
        self._photo = False
        self.avatar.override = False
        self.avatar.refresh()
        self._paint_photo_buttons()

    # --- umum ---------------------------------------------------------------------
    def _center(self, parent):
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _submit(self):
        try:
            err = self.on_submit(self.name_var.get(), self.pin_var.get(), self._photo)
        except Exception as exc:  # jangan sampai dialog macet karena error tak terduga
            C.log(f"Dialog guru gagal: {exc!r}")
            err = "Gagal menyimpan. Pastikan folder data bisa ditulis."
        if err:
            self.error.config(text=err)
        else:
            self.destroy()


class BirthDialog(tk.Toplevel):
    """Admin mengisi tanggal lahir murid: Tanggal / Bulan / Tahun (pilihan, tanpa ketik).
    on_submit("YYYY-MM-DD" atau "") -> teks error atau None. Umur dihitung otomatis."""

    MONTHS = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
              "September", "Oktober", "November", "Desember")
    MIN_YEAR = 1980           # tahun lahir paling lama yang bisa dipilih

    def __init__(self, master, name, birth, on_submit):
        super().__init__(master, bg=C.CARD, highlightthickness=1, highlightbackground=C.BORDER)
        self.title("Tanggal lahir")
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        dark_titlebar(self)
        try:
            self.iconbitmap(C.ICON_PATH)
        except Exception:
            pass
        self.on_submit = on_submit
        today = date.today()
        try:
            b = date.fromisoformat(birth) if birth else None
        except ValueError:
            b = None
        body = tk.Frame(self, bg=C.CARD, padx=28, pady=22)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="Tanggal lahir", bg=C.CARD, fg=C.TEXT, font=(C.FONT, 14, "bold"),
                 anchor="w").pack(fill="x")
        tk.Label(body, text=name, bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10),
                 anchor="w").pack(fill="x", pady=(2, 14))
        row = tk.Frame(body, bg=C.CARD)
        row.pack(fill="x")
        self.d_var = tk.StringVar(value=str(b.day) if b else "1")
        self.m_var = tk.StringVar(value=self.MONTHS[b.month - 1] if b else self.MONTHS[0])
        self.y_var = tk.StringVar(value=str(b.year) if b else str(today.year - 10))
        if b and b.year < self.MIN_YEAR:
            self.y_var.set(str(self.MIN_YEAR))
        years = [str(y) for y in range(self.MIN_YEAR, today.year + 1)]
        # Tanpa menu turun: gulir roda mouse di atas angka untuk mengganti
        for label, var, values in (("Tanggal", self.d_var, [str(i) for i in range(1, 32)]),
                                   ("Bulan", self.m_var, self.MONTHS),
                                   ("Tahun", self.y_var, years)):
            col = tk.Frame(row, bg=C.CARD)
            col.pack(side="left", padx=(0, 12))
            tk.Label(col, text=label, bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10),
                     anchor="w").pack(fill="x")
            WheelPicker(col, var, values, bg=C.CARD, fill=C.BG).pack(anchor="w", pady=(6, 0))
            var.trace_add("write", lambda *a: self._preview())
        self.age = tk.Label(body, text="", bg=C.CARD, fg=C.TEXT, font=(C.FONT, 11, "bold"),
                            anchor="w")
        self.age.pack(fill="x", pady=(14, 0))
        tk.Label(body, text="Gulir roda mouse di atas angka untuk mengganti. Umur diperbarui "
                            "otomatis setiap hari. Guru hanya melihat umur.",
                 bg=C.CARD, fg=C.MUTED, font=(C.FONT, 9), anchor="w", justify="left",
                 wraplength=420).pack(fill="x")
        self.error = tk.Label(body, text="", bg=C.CARD, fg=C.ERROR, font=(C.FONT, 10),
                              anchor="w")
        self.error.pack(fill="x", pady=(8, 0))
        btns = tk.Frame(body, bg=C.CARD)
        btns.pack(fill="x", pady=(8, 0))
        ok = RoundButton(btns, text="Simpan", command=self._submit, bg=C.ACCENT, fg="white",
                         activebackground=C.ACCENT_HOVER, activeforeground="white",
                         font=(C.FONT, 11, "bold"), padx=22, pady=7)
        ok.pack(side="right")
        add_hover(ok, C.ACCENT, C.ACCENT_HOVER)
        cancel = RoundButton(btns, text="Batal", command=self.destroy, bg=C.CARD, fg=C.MUTED,
                             activebackground=C.BORDER, activeforeground=C.TEXT,
                             font=(C.FONT, 11), padx=18, pady=7)
        cancel.pack(side="right", padx=(0, 8))
        add_hover(cancel, C.CARD, C.BORDER)
        if b:
            rm = RoundButton(btns, text="Kosongkan", command=lambda: self._send(""),
                             bg=C.CARD, fg=C.ERROR, activebackground=C.BORDER,
                             activeforeground=C.ERROR, font=(C.FONT, 10), padx=14, pady=7)
            rm.pack(side="left")
            add_hover(rm, C.CARD, C.BORDER)
        self._preview()
        self.bind("<Return>", lambda e: self._submit())
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        top = master.winfo_toplevel()
        x = top.winfo_rootx() + (top.winfo_width() - self.winfo_reqwidth()) // 2
        y = top.winfo_rooty() + (top.winfo_height() - self.winfo_reqheight()) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass

    def _value(self):
        try:
            return date(int(self.y_var.get()), self.MONTHS.index(self.m_var.get()) + 1,
                        int(self.d_var.get()))
        except ValueError:
            return None

    def _preview(self):
        d = self._value()
        if d is None:
            self.age.config(text="Tanggal tidak ada (mis. 31 Februari).", fg=C.ERROR)
        elif d > date.today():
            self.age.config(text="Tanggal lahir belum terjadi.", fg=C.ERROR)
        else:
            from elearning.students import age_of
            self.age.config(text=f"Umur sekarang: {age_of(d.isoformat())} tahun", fg=C.TEXT)

    def _submit(self):
        d = self._value()
        if d is None or d > date.today():
            self.error.config(text="Periksa lagi tanggal lahirnya.")
            return
        self._send(d.isoformat())

    def _send(self, value):
        err = self.on_submit(value)
        if err:
            self.error.config(text=err)
        else:
            self.destroy()


class CourseAccessDialog(tk.Toplevel):
    """Admin: per kursus program murid ini ada dua switch.
    Terbuka = murid bisa membuka kursus (mati = terkunci, tetap terlihat dengan gembok).
    Tampil  = kursus muncul di halaman murid (mati = disembunyikan sama sekali).
    Setiap switch langsung disimpan (seperti layar guru)."""

    def __init__(self, master, student_id):
        from elearning.courses import courses_for
        from elearning.ui import ui_icons as I
        from elearning.ui.widgets import Switch
        super().__init__(master, bg=C.CARD, highlightthickness=1, highlightbackground=C.BORDER)
        self.title("Kursus murid")
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        dark_titlebar(self)
        try:
            self.iconbitmap(C.ICON_PATH)
        except Exception:
            pass
        self.sid = student_id
        st = S.lookup_student(student_id) or {"name": student_id, "program": "adult",
                                              "courses": [], "hidden": []}
        opened, hidden = set(st["courses"]), set(st.get("hidden") or ())
        self._imgs = []
        body = tk.Frame(self, bg=C.CARD, padx=28, pady=22)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="Kursus", bg=C.CARD, fg=C.TEXT, font=(C.FONT, 14, "bold"),
                 anchor="w").pack(fill="x")
        tk.Label(body, text=f"{st['name']}  ·  {student_id}", bg=C.CARD, fg=C.MUTED,
                 font=(C.FONT, 10), anchor="w").pack(fill="x", pady=(2, 14))
        tk.Frame(body, bg=C.CARD, width=520, height=1).pack()   # lebar tetap: switch tidak terpotong
        head = tk.Frame(body, bg=C.CARD)
        head.pack(fill="x")
        for text in ("Tampil", "Terbuka"):      # judul kolom (kanan ke kiri)
            tk.Label(head, text=text, bg=C.CARD, fg=C.MUTED, font=(C.FONT, 9, "bold"),
                     width=8).pack(side="right", padx=(6, 0))
        for course in courses_for(st["program"]):
            panel = RoundPanel(body, padx=4, pady=2)
            panel.pack(fill="x", pady=4)
            row = panel.inner
            # switch dipasang lebih dulu (kanan) supaya selalu utuh; judul mengisi sisanya
            sw_box = tk.Frame(row, bg=C.CARD)
            sw_box.pack(side="right", padx=(0, 6))
            info = tk.Frame(row, bg=C.CARD, padx=14, pady=8)
            info.pack(side="left", fill="x", expand=True)
            line = tk.Frame(info, bg=C.CARD)
            line.pack(fill="x")
            dot = I.dot(course["color"], C.CARD, 10)
            if dot is not None:
                self._imgs.append(dot)
                tk.Label(line, image=dot, bg=C.CARD, bd=0).pack(side="left", padx=(0, 8))
            title = tk.Label(line, text=course["title"], bg=C.CARD, fg=C.TEXT,
                             font=(C.FONT, 11, "bold"), anchor="w")
            title.pack(side="left")
            state = tk.Label(info, bg=C.CARD, font=(C.FONT, 9), anchor="w")
            state.pack(fill="x")
            cell = dict(open=course["id"] in opened, show=course["id"] not in hidden)
            self._paint(state, title, cell)
            show_sw = Switch(sw_box, value=cell["show"], bg=C.CARD,
                             command=lambda v, c=course, k=cell, s=state, t=title:
                             self._save(c, "show", v, k, s, t))
            show_sw.pack(side="right", padx=(10, 14))
            open_sw = Switch(sw_box, value=cell["open"], bg=C.CARD,
                             command=lambda v, c=course, k=cell, s=state, t=title:
                             self._save(c, "open", v, k, s, t))
            open_sw.pack(side="right", padx=(10, 0))
        self.msg = tk.Label(body, text="Perubahan langsung tersimpan.", bg=C.CARD, fg=C.MUTED,
                            font=(C.FONT, 9), anchor="w")
        self.msg.pack(fill="x", pady=(10, 0))
        btns = tk.Frame(body, bg=C.CARD)
        btns.pack(fill="x", pady=(8, 0))
        ok = RoundButton(btns, text="Selesai", command=self.destroy, bg=C.ACCENT, fg="white",
                         activebackground=C.ACCENT_HOVER, activeforeground="white",
                         font=(C.FONT, 11, "bold"), padx=22, pady=7)
        ok.pack(side="right")
        add_hover(ok, C.ACCENT, C.ACCENT_HOVER)
        self.bind("<Return>", lambda e: self.destroy())
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        top = master.winfo_toplevel()
        x = top.winfo_rootx() + (top.winfo_width() - self.winfo_reqwidth()) // 2
        y = top.winfo_rooty() + (top.winfo_height() - self.winfo_reqheight()) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass

    @staticmethod
    def _paint(state, title, cell):
        if not cell["show"]:
            text, fg = "Disembunyikan dari murid", C.LOCKED
        elif cell["open"]:
            text, fg = "Terbuka", C.ON
        else:
            text, fg = "Terkunci (terlihat dengan gembok)", C.MUTED
        state.config(text=text, fg=fg)
        title.config(fg=C.TEXT if cell["show"] else C.MUTED)

    def _save(self, course, what, value, cell, state, title):
        try:
            if what == "open":
                S.set_course_access(self.sid, course["id"], value)
            else:
                S.set_course_hidden(self.sid, course["id"], not value)
        except Exception as exc:
            C.log(f"Kursus {self.sid}/{course['id']} ({what}) gagal disimpan: {exc!r}")
            self.msg.config(text="Gagal menyimpan. Pastikan folder data bisa ditulis.",
                            fg=C.ERROR)
            return False
        cell[what] = value
        self._paint(state, title, cell)
        self.msg.config(text=f"Tersimpan: {course['title']}.", fg=C.MUTED)
        return True


class PinterestLimitDialog(tk.Toplevel):
    """Guru mengatur batas Pinterest per hari untuk SATU murid (gulir roda mouse, tanpa ketik).
    on_submit(menit | None) -> teks error atau None. None = ikut bawaan, -1 = tanpa batas,
    0 = diblokir."""

    STEPS = (5, 10, 15, 20, 30, 45, 60, 90, 120)

    def __init__(self, master, name, current, default, used_min, on_submit):
        super().__init__(master, bg=C.CARD, highlightthickness=1, highlightbackground=C.BORDER)
        self.title("Batas Pinterest")
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        dark_titlebar(self)
        try:
            self.iconbitmap(C.ICON_PATH)
        except Exception:
            pass
        self.on_submit = on_submit
        dflt = f"Bawaan · {default} mnt" if default else "Bawaan · tanpa batas"
        self.options = [(dflt, None), ("Diblokir", 0)] + \
            [(f"{m} menit", m) for m in self.STEPS] + [("Tanpa batas", -1)]
        labels = [lb for lb, _v in self.options]
        cur = next((lb for lb, v in self.options if v == current), None)
        if cur is None and current is not None:          # angka lain (mis. dari data lama)
            self.options.insert(2, (f"{current} menit", current))
            labels.insert(2, f"{current} menit")
            cur = f"{current} menit"
        body = tk.Frame(self, bg=C.CARD, padx=28, pady=22)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="Batas Pinterest", bg=C.CARD, fg=C.TEXT,
                 font=(C.FONT, 14, "bold"), anchor="w").pack(fill="x")
        tk.Label(body, text=name, bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10),
                 anchor="w").pack(fill="x", pady=(2, 14))
        self.var = tk.StringVar(value=cur or labels[0])
        WheelPicker(body, self.var, labels, width=320, bg=C.CARD, fill=C.BG).pack(anchor="w")
        tk.Label(body, text=f"Sudah dipakai {used_min} menit (jatah reset {getattr(C, 'WEB_WINDOW_HOURS', 5):g} jam setelah mulai dipakai). Gulir roda mouse untuk "
                            "mengganti. Bawaan diatur di jendela Dev.",
                 bg=C.CARD, fg=C.MUTED, font=(C.FONT, 9), anchor="w", justify="left",
                 wraplength=380).pack(fill="x", pady=(12, 0))
        self.error = tk.Label(body, text="", bg=C.CARD, fg=C.ERROR, font=(C.FONT, 10),
                              anchor="w")
        self.error.pack(fill="x", pady=(8, 0))
        btns = tk.Frame(body, bg=C.CARD)
        btns.pack(fill="x", pady=(8, 0))
        ok = RoundButton(btns, text="Simpan", command=self._submit, bg=C.ACCENT, fg="white",
                         activebackground=C.ACCENT_HOVER, activeforeground="white",
                         font=(C.FONT, 11, "bold"), padx=22, pady=7)
        ok.pack(side="right")
        add_hover(ok, C.ACCENT, C.ACCENT_HOVER)
        cancel = RoundButton(btns, text="Batal", command=self.destroy, bg=C.CARD, fg=C.MUTED,
                             activebackground=C.BORDER, activeforeground=C.TEXT,
                             font=(C.FONT, 11), padx=18, pady=7)
        cancel.pack(side="right", padx=(0, 8))
        add_hover(cancel, C.CARD, C.BORDER)
        self.bind("<Return>", lambda e: self._submit())
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        top = master.winfo_toplevel()
        x = top.winfo_rootx() + (top.winfo_width() - self.winfo_reqwidth()) // 2
        y = top.winfo_rooty() + (top.winfo_height() - self.winfo_reqheight()) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass

    def _submit(self):
        value = dict(self.options).get(self.var.get())
        err = self.on_submit(value)
        if err:
            self.error.config(text=err)
            return
        self.destroy()
