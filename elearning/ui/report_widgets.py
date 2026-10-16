"""Komponen tampilan laporan kerja guru.

Dipakai dua layar: layar guru (menulis laporan) dan Panel Admin (melihat laporan).

PeriodBar         : tombol pilihan periode (Hari ini / 7 hari / 30 hari / Semua)
PortfolioSummary  : tabel siapa yang sudah / belum submit portfolio pada periode itu
ReportCard        : satu laporan; tombol Ubah / Hapus hanya muncul kalau diberi aksi
"""

import tkinter as tk

from elearning import config as C
from elearning.ui.controls import RoundButton, RoundPanel
from elearning import reports, sessions
from elearning.ui.widgets import add_hover

PROGRAM_LABEL = {"adult": "Murid dewasa", "kids": "Murid anak"}
KIND_COLOR = {"portfolio": C.ACCENT, "student": "#4a90e2", "class": C.ON,
              "issue": C.ERROR, "other": C.MUTED}
# (judul kolom, bobot lebar)
PORTFOLIO_COLUMNS = (("Murid", 6), ("Submit pada periode", 5), ("Total", 2),
                     ("Terakhir submit", 5))


def section_title(parent, text, sub="", pady=(18, 8)):
    row = tk.Frame(parent, bg=C.BG)
    row.pack(fill="x", pady=pady)
    tk.Label(row, text=text, bg=C.BG, fg=C.TEXT,
             font=(C.FONT, 13, "bold")).pack(side="left")
    if sub:
        tk.Label(row, text=f"   {sub}", bg=C.BG, fg=C.MUTED,
                 font=(C.FONT, 10)).pack(side="left")
    return row


def empty_note(parent, text):
    tk.Label(parent, text=text, bg=C.BG, fg=C.MUTED, font=(C.FONT, 10),
             anchor="w", justify="left", wraplength=520).pack(fill="x", pady=8)


def small_button(parent, text, command, fg=C.MUTED, bg=C.CARD, hover=C.BORDER):
    btn = RoundButton(parent, text=text, command=command, bg=bg, fg=fg,
                    activebackground=hover, activeforeground=fg, relief="flat", bd=0,
                    highlightthickness=0, font=(C.FONT, 9), cursor="hand2",
                    padx=10, pady=3)
    add_hover(btn, bg, hover)
    return btn


class PeriodBar(tk.Frame):
    """Pilihan periode. on_change() dipanggil setelah pilihan berubah; range() = (dari, sampai)."""

    def __init__(self, master, on_change, key="7d", bg=C.BG):
        super().__init__(master, bg=bg)
        self.key = key
        self.on_change = on_change
        self._btns = {}
        for k, label in reports.PERIODS:
            b = RoundButton(self, text=label, command=lambda k=k: self.select(k),
                          relief="flat", bd=0, highlightthickness=0, cursor="hand2",
                          font=(C.FONT, 10), padx=12, pady=5)
            b.pack(side="left", padx=(0, 6))
            self._btns[k] = b
        self._paint()

    def _paint(self):
        for k, b in self._btns.items():
            on = k == self.key
            b.config(bg=C.ACCENT if on else C.CARD, fg="white" if on else C.MUTED,
                     activebackground=C.ACCENT_HOVER if on else C.BORDER,
                     activeforeground="white" if on else C.TEXT)

    def select(self, key):
        if key == self.key:
            return
        self.key = key
        self._paint()
        self.on_change()

    def range(self):
        return reports.period(self.key)


class PortfolioSummary(tk.Frame):
    """Tabel portfolio per murid. Yang belum submit tampil di atas supaya mudah terlihat.

    warn=True mewarnai 'Belum submit' dengan merah (dimatikan untuk periode 'Hari ini'
    karena hampir semua murid memang belum submit hari itu).
    """

    def __init__(self, master, rows, warn=True):
        super().__init__(master, bg=C.BG)
        done = sum(1 for r in rows if r["submitted"])
        files = sum(r["submitted"] for r in rows)
        section_title(self, "Portfolio murid",
                      f"{done} dari {len(rows)} murid aktif sudah submit  ·  {files} file",
                      pady=(0, 8))
        if not rows:
            empty_note(self, "Belum ada murid aktif.")
            return
        self.warn = warn

        header = tk.Frame(self, bg=C.BG, padx=14)
        header.pack(fill="x")
        self._columns(header)
        for i, (title, _w) in enumerate(PORTFOLIO_COLUMNS):
            tk.Label(header, text=title, bg=C.BG, fg=C.MUTED, anchor="w",
                     font=(C.FONT, 9, "bold")).grid(row=0, column=i, sticky="w")
        for r in sorted(rows, key=lambda r: (bool(r["submitted"]), r["id"])):
            self._row(r)

    @staticmethod
    def _columns(frame):
        for i, (_t, weight) in enumerate(PORTFOLIO_COLUMNS):
            frame.grid_columnconfigure(i, weight=weight, uniform="pcol")

    def _row(self, r):
        panel = RoundPanel(self, padx=14, pady=8)
        panel.pack(fill="x", pady=(6, 0))
        row = panel.inner
        self._columns(row)

        who = tk.Frame(row, bg=C.CARD)
        who.grid(row=0, column=0, sticky="w")
        tk.Label(who, text=r["name"], bg=C.CARD, fg=C.TEXT, anchor="w",
                 font=(C.FONT, 11, "bold")).pack(fill="x")
        tk.Label(who, text=f"{r['id']}  ·  {PROGRAM_LABEL.get(r['program'], '')}",
                 bg=C.CARD, fg=C.MUTED, anchor="w", font=(C.FONT, 9)).pack(fill="x")

        sub = tk.Frame(row, bg=C.CARD)
        sub.grid(row=0, column=1, sticky="w")
        if r["submitted"]:
            detail = []
            if r["images"]:
                detail.append(f"{r['images']} gambar")
            if r["videos"]:
                detail.append(f"{r['videos']} video")
            tk.Label(sub, text=f"●  {' · '.join(detail)}", bg=C.CARD, fg=C.ON, anchor="w",
                     font=(C.FONT, 10, "bold")).pack(fill="x")
            tk.Label(sub, text=", ".join(r["courses"]), bg=C.CARD, fg=C.MUTED, anchor="w",
                     font=(C.FONT, 9)).pack(fill="x")
        else:
            tk.Label(sub, text="○  Belum submit", bg=C.CARD, anchor="w",
                     fg=C.ERROR if self.warn else C.MUTED,
                     font=(C.FONT, 10, "bold" if self.warn else "normal")).pack(fill="x")

        last = (f"{sessions.format_date(r['last'])}, {sessions.format_time(r['last'])}"
                if r["last"] else "Belum pernah")
        for col, text in ((2, f"{r['total']} file"), (3, last)):
            tk.Label(row, text=text, bg=C.CARD, fg=C.TEXT if r["total"] else C.MUTED,
                     anchor="w", font=(C.FONT, 10)).grid(row=0, column=col, sticky="w")


class ReportCard(RoundPanel):
    """Satu laporan.

    rec          : item dari reports.list_reports()
    student_name : fungsi ID murid -> nama (None kalau murid sudah dihapus)
    teacher_name : kalau diisi, nama guru ikut ditampilkan (untuk admin)
    on_edit / on_delete : kalau diisi, muncul tombol Ubah / Hapus -> fungsi(rec)
    """

    def __init__(self, master, rec, student_name, teacher_name=None,
                 on_edit=None, on_delete=None):
        color = KIND_COLOR.get(rec["kind"], C.MUTED)
        super().__init__(master, padx=14, pady=12, stripe=color)
        body = self.inner

        head = tk.Frame(body, bg=C.CARD)
        head.pack(fill="x")
        tk.Label(head, text=reports.KIND_LABEL[rec["kind"]].upper(), bg=C.CARD, fg=color,
                 font=(C.FONT, 9, "bold")).pack(side="left")
        when = sessions.format_date(rec["day"])
        if teacher_name:
            when += f"  ·  {teacher_name}"
        tk.Label(head, text=when, bg=C.CARD, fg=C.MUTED,
                 font=(C.FONT, 9)).pack(side="right")

        if rec["student"]:
            name = student_name(rec["student"]) or "(murid sudah dihapus)"
            tk.Label(body, text=f"{rec['student']}  ·  {name}", bg=C.CARD, fg=C.TEXT,
                     anchor="w", font=(C.FONT, 11, "bold")).pack(fill="x", pady=(4, 0))

        text = tk.Label(body, text=rec["text"], bg=C.CARD, fg=C.TEXT, anchor="w",
                        justify="left", font=(C.FONT, 10))
        text.pack(fill="x", pady=(4, 0))
        # Teks mengikuti lebar kartu, termasuk saat jendela diperbesar / diperkecil
        text.bind("<Configure>", lambda e: text.config(wraplength=max(200, e.width - 4)))

        foot = tk.Frame(body, bg=C.CARD)
        foot.pack(fill="x", pady=(6, 0))
        if rec.get("edited"):
            tk.Label(foot, text=f"Diubah {rec['edited'][:16]}", bg=C.CARD, fg=C.MUTED,
                     font=(C.FONT, 8)).pack(side="left")
        if on_delete is not None:
            small_button(foot, "Hapus", lambda: on_delete(rec),
                         fg=C.ERROR).pack(side="right")
        if on_edit is not None:
            small_button(foot, "Ubah", lambda: on_edit(rec)).pack(side="right", padx=(0, 6))
