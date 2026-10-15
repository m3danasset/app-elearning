"""Layar guru: menulis laporan kerja untuk admin.

Kiri  : formulir laporan (tanggal, jenis, murid, catatan).
Kanan : ringkasan portfolio otomatis + daftar laporan milik guru yang sedang masuk.
Admin melihat hasilnya di Panel Admin, tab "Laporan Guru".
"""

import tkinter as tk
from datetime import date

from elearning import config as C
from elearning import reports
from elearning.students import list_students
from elearning.ui.dialogs import ConfirmDialog
from elearning.ui.report_widgets import (KIND_COLOR, PeriodBar, PortfolioSummary,
                                         ReportCard, empty_note, section_title)
from elearning.ui.topbar import TopBar
from elearning.ui.widgets import ScrollFrame, add_hover

NO_STUDENT = "Umum (tidak terkait murid)"
FORM_W = 340


class ReportScreen(tk.Frame):
    def __init__(self, master, teacher, on_back, on_logout):
        super().__init__(master, bg=C.BG)
        self.teacher = teacher
        self.editing = None            # id laporan yang sedang diubah, None = laporan baru
        self.kind = "student"
        TopBar(self, teacher, on_logout, on_back=on_back,
               title="Laporan Kerja").pack(fill="x")

        body = tk.Frame(self, bg=C.BG, padx=32, pady=24)
        body.pack(fill="both", expand=True)

        self._students = list_students()
        self._names = {s["id"]: s["name"] for s in self._students}
        self._build_form(body)

        right = tk.Frame(body, bg=C.BG)
        right.pack(side="left", fill="both", expand=True, padx=(24, 0))
        bar = tk.Frame(right, bg=C.BG)
        bar.pack(fill="x")
        tk.Label(bar, text="Periode", bg=C.BG, fg=C.MUTED,
                 font=(C.FONT, 10)).pack(side="left", padx=(0, 10))
        self.period = PeriodBar(bar, on_change=self.refresh, key="7d")
        self.period.pack(side="left")
        self.scroll = ScrollFrame(right, bg=C.BG)
        self.scroll.pack(fill="both", expand=True, pady=(12, 0))
        self.refresh()

    # --- formulir ----------------------------------------------------------------
    def _build_form(self, body):
        form = tk.Frame(body, bg=C.CARD, width=FORM_W, highlightthickness=1,
                        highlightbackground=C.BORDER)
        form.pack(side="left", fill="y")
        form.pack_propagate(False)
        pad = tk.Frame(form, bg=C.CARD, padx=20, pady=16)
        pad.pack(fill="both", expand=True)

        self.form_title = tk.Label(pad, text="Tulis laporan", bg=C.CARD, fg=C.TEXT,
                                   font=(C.FONT, 13, "bold"), anchor="w")
        self.form_title.pack(fill="x")

        # Tanggal
        self.date_var = tk.StringVar(value=reports.format_day(date.today()))
        self._label(pad, "Tanggal (hari/bulan/tahun)", pady=(12, 0))
        self._entry_box(pad, tk.Entry, textvariable=self.date_var, font=(C.FONT, 11))

        # Jenis laporan
        self._label(pad, "Jenis laporan", pady=(10, 0))
        chips = tk.Frame(pad, bg=C.CARD)
        chips.pack(fill="x", pady=(6, 0))
        self._kind_btns = {}
        for i, (key, label) in enumerate(reports.KINDS):
            b = tk.Button(chips, text=label, command=lambda k=key: self._set_kind(k),
                          relief="flat", bd=0, highlightthickness=0, cursor="hand2",
                          font=(C.FONT, 9, "bold"), padx=8, pady=4)
            b.grid(row=i // 3, column=i % 3, sticky="ew", padx=(0, 4), pady=(0, 4))
            self._kind_btns[key] = b
        for c in range(3):
            chips.grid_columnconfigure(c, weight=1, uniform="kind")

        # Murid
        self.student_lbl = self._label(pad, "Murid", pady=(6, 0))
        self.student_var = tk.StringVar(value=NO_STUDENT)
        self._student_ids = {NO_STUDENT: ""}
        labels = [NO_STUDENT]
        for s in self._students:
            label = f"{s['id']}   {s['name']}"
            self._student_ids[label] = s["id"]
            labels.append(label)
        menu = tk.OptionMenu(pad, self.student_var, *labels)
        menu.config(bg=C.BG, fg=C.TEXT, activebackground=C.BORDER,
                    activeforeground=C.TEXT, relief="flat", bd=0, anchor="w",
                    highlightthickness=1, highlightbackground=C.BORDER,
                    font=(C.FONT, 10), cursor="hand2")
        menu["menu"].config(bg=C.CARD, fg=C.TEXT, activebackground=C.ACCENT,
                            activeforeground="white", font=(C.FONT, 10), bd=0)
        menu.pack(fill="x", pady=(6, 0), ipady=3)

        # Catatan
        self._label(pad, "Catatan", pady=(10, 0))
        self.text = self._entry_box(pad, tk.Text, height=6, width=10, wrap="word",
                                    font=(C.FONT, 10), padx=8, pady=6, undo=True)

        self.msg = tk.Label(pad, text="", bg=C.CARD, fg=C.MUTED, font=(C.FONT, 9),
                            anchor="w", justify="left", wraplength=FORM_W - 50)
        self.msg.pack(side="bottom", fill="x", pady=(8, 0))
        btns = tk.Frame(pad, bg=C.CARD)
        btns.pack(side="bottom", fill="x", pady=(12, 0))
        self.save_btn = tk.Button(btns, text="Simpan laporan", command=self._save,
                                  bg=C.ACCENT, fg="white", activebackground=C.ACCENT_HOVER,
                                  activeforeground="white", relief="flat", bd=0,
                                  highlightthickness=0, font=(C.FONT, 11, "bold"),
                                  cursor="hand2", padx=18, pady=7)
        self.save_btn.pack(side="right")
        add_hover(self.save_btn, C.ACCENT, C.ACCENT_HOVER)
        self.cancel_btn = tk.Button(btns, text="Batal ubah", command=self._reset_form,
                                    bg=C.CARD, fg=C.MUTED, activebackground=C.BORDER,
                                    activeforeground=C.TEXT, relief="flat", bd=0,
                                    highlightthickness=0, font=(C.FONT, 10),
                                    cursor="hand2", padx=12, pady=7)
        add_hover(self.cancel_btn, C.CARD, C.BORDER)   # hanya tampil saat mengubah laporan
        self._set_kind(self.kind)

    @staticmethod
    def _label(parent, text, pady=(0, 0)):
        lbl = tk.Label(parent, text=text, bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10),
                       anchor="w")
        lbl.pack(fill="x", pady=pady)
        return lbl

    @staticmethod
    def _entry_box(parent, widget_cls, **opts):
        """Kolom isian bergaris yang menyala oranye saat difokus (gaya sama dengan dialog)."""
        border = tk.Frame(parent, bg=C.BORDER, padx=1, pady=1)
        border.pack(fill="x", pady=(6, 0))
        w = widget_cls(border, bg=C.BG, fg=C.TEXT, insertbackground=C.TEXT,
                       relief="flat", highlightthickness=0, **opts)
        w.pack(fill="x", ipady=5 if widget_cls is tk.Entry else 0)
        w.bind("<FocusIn>", lambda e: border.config(bg=C.ACCENT))
        w.bind("<FocusOut>", lambda e: border.config(bg=C.BORDER))
        return w

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

    def _reset_form(self):
        self.editing = None
        self.date_var.set(reports.format_day(date.today()))
        self.student_var.set(NO_STUDENT)
        self.text.delete("1.0", "end")
        self._set_kind("student")
        self.form_title.config(text="Tulis laporan")
        self.save_btn.config(text="Simpan laporan")
        self.cancel_btn.pack_forget()

    def _say(self, text, error=False):
        self.msg.config(text=text, fg=C.ERROR if error else C.MUTED)

    # --- simpan / ubah / hapus ---------------------------------------------------
    def _save(self):
        try:
            day = reports.parse_day(self.date_var.get())
            sid = self._student_ids.get(self.student_var.get(), "")
            text = self.text.get("1.0", "end")
            if self.editing:
                reports.update(self.editing, self.teacher["id"], self.kind, text, sid, day)
                done = "Perubahan tersimpan."
            else:
                reports.add(self.teacher["id"], self.kind, text, sid, day)
                done = "Laporan tersimpan. Admin bisa melihatnya di Panel Admin."
        except ValueError as exc:   # isian kurang / salah: pesan sudah siap tampil
            self._say(str(exc), error=True)
            return
        except Exception as exc:
            C.log(f"Gagal menyimpan laporan: {exc!r}")
            self._say("Gagal menyimpan. Pastikan folder data bisa ditulis.", error=True)
            return
        self._reset_form()
        self._say(done)
        # Laporan bertanggal di luar periode yang sedang dilihat tidak akan muncul
        # di daftar; pindah ke 'Semua' supaya guru langsung melihat hasilnya.
        if not reports.in_range(day, *self.period.range()):
            self.period.select("all")   # memuat ulang daftar
        else:
            self.refresh()

    def _edit(self, rec):
        self.editing = rec["id"]
        self.date_var.set(reports.format_day(rec["day"]))
        self._set_kind(rec["kind"])
        label = next((lb for lb, sid in self._student_ids.items()
                      if sid and sid == rec["student"]), NO_STUDENT)
        self.student_var.set(label)
        self.text.delete("1.0", "end")
        self.text.insert("1.0", rec["text"])
        self.form_title.config(text="Ubah laporan")
        self.save_btn.config(text="Simpan perubahan")
        self.cancel_btn.pack(side="right", padx=(0, 8))
        self._say("")
        self.text.focus_set()

    def _delete(self, rec):
        def confirm():
            try:
                reports.delete(rec["id"], self.teacher["id"])
            except ValueError as exc:
                return str(exc)
            return None

        ConfirmDialog(self, "Hapus laporan?",
                      "Laporan ini akan dihapus dan hilang juga dari Panel Admin. "
                      "Tidak bisa dikembalikan.", confirm,
                      confirm_text="Hapus").wait_window()
        if self.editing == rec["id"]:
            self._reset_form()
        self.refresh()

    # --- isi kanan -----------------------------------------------------------------
    def refresh(self):
        top = self.scroll.canvas.yview()[0]
        for w in self.scroll.inner.winfo_children():
            w.destroy()
        since, until = self.period.range()
        inner = self.scroll.inner

        try:
            rows = reports.portfolio_status(since, until)
        except Exception as exc:   # ringkasan gagal tidak boleh menghalangi laporan
            C.log(f"Ringkasan portfolio gagal: {exc!r}")
            rows = []
        PortfolioSummary(inner, rows, warn=self.period.key != "today").pack(fill="x")

        mine = reports.list_reports(self.teacher["id"], since, until)
        section_title(inner, "Laporan saya", f"{len(mine)} laporan")
        if not mine:
            empty_note(inner, "Belum ada laporan pada periode ini. "
                              "Tulis di formulir sebelah kiri.")
        for rec in mine:
            ReportCard(inner, rec, self._names.get, on_edit=self._edit,
                       on_delete=self._delete).pack(fill="x", pady=(0, 8))
        self.update_idletasks()
        self.scroll.canvas.yview_moveto(top)   # tetap di posisi gulir semula
