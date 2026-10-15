"""Panel guru: laporan kerja untuk admin (tampil di area kanan layar guru).

Atas   : pilihan periode + tombol "Tulis laporan" (membuka dialog).
Bawah  : ringkasan portfolio otomatis + daftar laporan milik guru yang sedang masuk.
Admin melihat hasilnya di Panel Admin, tab "Laporan Guru".
"""

import tkinter as tk

from elearning import config as C
from elearning import reports
from elearning.students import list_students
from elearning.ui.dialogs import ConfirmDialog, ReportDialog
from elearning.ui.report_widgets import (PeriodBar, PortfolioSummary, ReportCard,
                                         empty_note, section_title)
from elearning.ui.widgets import ScrollFrame, add_hover


class ReportPanel(tk.Frame):
    def __init__(self, master, teacher):
        super().__init__(master, bg=C.BG, padx=32, pady=24)
        self.teacher = teacher
        self._students = list_students()
        self._names = {s["id"]: s["name"] for s in self._students}

        bar = tk.Frame(self, bg=C.BG)
        bar.pack(fill="x")
        write = tk.Button(bar, text="+  Tulis laporan", command=self._write,
                          bg=C.ACCENT, fg="white", activebackground=C.ACCENT_HOVER,
                          activeforeground="white", relief="flat", bd=0,
                          highlightthickness=0, font=(C.FONT, 11, "bold"),
                          cursor="hand2", padx=18, pady=6)
        write.pack(side="right")   # dipasang dulu agar tidak tergencet
        add_hover(write, C.ACCENT, C.ACCENT_HOVER)
        tk.Label(bar, text="Periode", bg=C.BG, fg=C.MUTED,
                 font=(C.FONT, 10)).pack(side="left", padx=(0, 10))
        self.period = PeriodBar(bar, on_change=self.refresh, key="7d")
        self.period.pack(side="left")

        self.msg = tk.Label(self, text=self.HINT, bg=C.BG, fg=C.MUTED,
                            font=(C.FONT, 10), anchor="w")
        self.msg.pack(fill="x", pady=(10, 0))

        self.scroll = ScrollFrame(self, bg=C.BG)
        self.scroll.pack(fill="both", expand=True, pady=(8, 0))
        self.refresh()

    HINT = "Laporan yang Anda tulis bisa dilihat admin di Panel Admin, tab Laporan Guru."

    def _say(self, text, error=False):
        self.msg.config(text=text, fg=C.ERROR if error else C.MUTED)

    # --- tulis / ubah / hapus --------------------------------------------------------
    def _write(self):
        self._open_dialog(None)

    def _edit(self, rec):
        self._open_dialog(rec)

    def _open_dialog(self, rec):
        saved = {}

        def submit(day_text, kind, student_id, text):
            try:
                day = reports.parse_day(day_text)
                if rec:
                    reports.update(rec["id"], self.teacher["id"], kind, text,
                                   student_id, day)
                else:
                    reports.add(self.teacher["id"], kind, text, student_id, day)
            except ValueError as exc:   # isian kurang / salah: pesan siap tampil
                return str(exc)
            saved["day"] = day
            return None

        ReportDialog(self, self._students, submit, rec).wait_window()
        if not saved:   # dibatalkan
            return
        self._say("Perubahan tersimpan." if rec else "Laporan tersimpan.")
        # Laporan bertanggal di luar periode yang sedang dilihat tidak akan muncul
        # di daftar; pindah ke 'Semua' supaya guru langsung melihat hasilnya.
        if not reports.in_range(saved["day"], *self.period.range()):
            self.period.select("all")   # memuat ulang daftar
        else:
            self.refresh()

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
        self.refresh()

    # --- isi ---------------------------------------------------------------------------
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
                              "Klik \"Tulis laporan\" untuk membuat.")
        for rec in mine:
            ReportCard(inner, rec, self._names.get, on_edit=self._edit,
                       on_delete=self._delete).pack(fill="x", pady=(0, 8))
        self.update_idletasks()
        self.scroll.canvas.yview_moveto(top)   # tetap di posisi gulir semula
