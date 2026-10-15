"""Panel admin: memantau aktivitas guru dan murid, serta mengatur status murid (active / expired)."""

import tkinter as tk

from elearning import config as C
from elearning import sessions
from elearning.students import (STATUS_ACTIVE, STATUS_EXPIRED, STATUS_LABEL,
                                list_students, set_status)
from elearning.teachers import TEACHERS
from elearning.ui.avatar import Avatar
from elearning.ui.topbar import TopBar
from elearning.ui.widgets import ScrollFrame, add_hover

REFRESH_MS = 30_000
PROGRAM_LABEL = {"adult": "Murid dewasa", "kids": "Murid anak"}
# (judul kolom, bobot lebar)
COLUMNS = (("Nama", 8), ("Aktivitas", 5), ("Terakhir aktif", 6),
           ("Jumlah masuk", 3), ("Total waktu", 3), ("Status akun", 7))


class AdminScreen(tk.Frame):
    def __init__(self, master, admin, on_logout):
        super().__init__(master, bg=C.BG)
        TopBar(self, admin, on_logout, title="Panel Admin").pack(fill="x")

        body = tk.Frame(self, bg=C.BG, padx=32, pady=24)
        body.pack(fill="both", expand=True)

        self.tab = "students"
        self._after = None

        bar = tk.Frame(body, bg=C.BG)
        bar.pack(fill="x")
        self.tab_btns = {}
        for key, label in (("students", "Murid"), ("teachers", "Guru")):
            b = tk.Button(bar, text=label, command=lambda k=key: self._set_tab(k),
                          relief="flat", bd=0, highlightthickness=0, cursor="hand2",
                          font=(C.FONT, 10, "bold"), padx=16, pady=6)
            b.pack(side="left", padx=(0, 6))
            self.tab_btns[key] = b
        reload_btn = tk.Button(bar, text="Muat ulang", command=self.refresh,
                               bg=C.CARD, fg=C.MUTED, activebackground=C.BORDER,
                               activeforeground=C.TEXT, relief="flat", bd=0,
                               highlightthickness=0, font=(C.FONT, 10),
                               cursor="hand2", padx=14, pady=6)
        reload_btn.pack(side="right")
        add_hover(reload_btn, C.CARD, C.BORDER)

        self.summary = tk.Label(body, text="", bg=C.BG, fg=C.MUTED,
                                font=(C.FONT, 10), anchor="w")
        self.summary.pack(fill="x", pady=(12, 10))

        header = tk.Frame(body, bg=C.BG, padx=14)
        header.pack(fill="x")
        self._configure_columns(header)
        for i, (title, _w) in enumerate(COLUMNS):
            tk.Label(header, text=title, bg=C.BG, fg=C.MUTED, anchor="w",
                     font=(C.FONT, 9, "bold")).grid(row=0, column=i, sticky="w")

        self.scroll = ScrollFrame(body, bg=C.BG)
        self.scroll.pack(fill="both", expand=True, pady=(6, 0))

        self._paint_tabs()
        self.refresh()

    # --- tab -----------------------------------------------------------------
    def _paint_tabs(self):
        for key, b in self.tab_btns.items():
            if key == self.tab:
                b.config(bg=C.ACCENT, fg="white", activebackground=C.ACCENT_HOVER,
                         activeforeground="white")
            else:
                b.config(bg=C.CARD, fg=C.MUTED, activebackground=C.BORDER,
                         activeforeground=C.TEXT)

    def _set_tab(self, key):
        if key == self.tab:
            return
        self.tab = key
        self._paint_tabs()
        self.scroll.scroll_to_top()
        self.refresh()

    # --- data ------------------------------------------------------------------
    def _people(self):
        if self.tab == "teachers":
            return [{"id": tid, "name": d["name"], "sub": "Guru"}
                    for tid, d in sorted(TEACHERS.items())]
        return [{"id": s["id"], "name": s["name"], "status": s["status"],
                 "sub": PROGRAM_LABEL.get(s["program"], "")}
                for s in list_students()]

    @staticmethod
    def _configure_columns(frame):
        for i, (_t, weight) in enumerate(COLUMNS):
            frame.grid_columnconfigure(i, weight=weight, uniform="col")

    def refresh(self):
        """Muat ulang daftar (otomatis tiap 30 detik selama layar ini terbuka)."""
        if self._after is not None:
            self.after_cancel(self._after)
        for w in self.scroll.inner.winfo_children():
            w.destroy()

        people = self._people()
        stats = sessions.overview([p["id"] for p in people])
        online = sum(1 for p in people if stats.get(p["id"], {}).get("online"))
        noun = "guru" if self.tab == "teachers" else "murid"
        expired = sum(1 for p in people if p.get("status") == STATUS_EXPIRED)
        extra = f"{expired} expired  ·  " if self.tab == "students" else ""
        self.summary.config(
            fg=C.MUTED,
            text=f"{len(people)} {noun}  ·  {online} sedang online  ·  {extra}"
                 f"diperbarui {sessions.format_time(sessions.datetime.now())}")

        if not people:
            tk.Label(self.scroll.inner, text=f"Belum ada {noun}.", bg=C.BG,
                     fg=C.MUTED, font=(C.FONT, 11)).pack(pady=24)
        for p in people:
            self._build_row(p, stats.get(p["id"]))

        self._after = self.after(REFRESH_MS, self.refresh)

    # --- satu baris --------------------------------------------------------------
    def _build_row(self, person, st):
        row = tk.Frame(self.scroll.inner, bg=C.CARD, highlightthickness=1,
                       highlightbackground=C.BORDER, padx=14, pady=10)
        row.pack(fill="x", pady=(0, 6))
        self._configure_columns(row)

        who = tk.Frame(row, bg=C.CARD)
        who.grid(row=0, column=0, sticky="w")
        Avatar(who, person["id"], person["name"], size=36,
               bg=C.CARD).pack(side="left", padx=(0, 10))
        names = tk.Frame(who, bg=C.CARD)
        names.pack(side="left")
        tk.Label(names, text=person["name"], bg=C.CARD, fg=C.TEXT, anchor="w",
                 font=(C.FONT, 11, "bold")).pack(fill="x")
        tk.Label(names, text=f"{person['id']}  ·  {person['sub']}", bg=C.CARD,
                 fg=C.MUTED, anchor="w", font=(C.FONT, 9)).pack(fill="x")

        if st is None:
            status, color = "Belum pernah masuk", C.MUTED
            last = count = total = "-"
        else:
            status, color = (("●  Online", C.ON) if st["online"]
                             else ("○  Offline", C.MUTED))
            seen = st["last_seen"]
            last = ("Sekarang" if st["online"] else
                    f"{sessions.format_date(seen)}, {sessions.format_time(seen)}")
            count = str(st["count"])
            total = sessions.format_duration(st["total"])

        for col, (text, fg) in enumerate(
                ((status, color), (last, C.TEXT), (count, C.TEXT), (total, C.TEXT)),
                start=1):
            tk.Label(row, text=text, bg=C.CARD, fg=fg, anchor="w",
                     font=(C.FONT, 10)).grid(row=0, column=col, sticky="w")

        self._build_account_cell(row, person)

    def _build_account_cell(self, row, person):
        """Kolom 'Status akun': badge Active/Expired + tombol untuk mengubahnya (murid saja)."""
        cell = tk.Frame(row, bg=C.CARD)
        cell.grid(row=0, column=len(COLUMNS) - 1, sticky="w")
        status = person.get("status")
        if status is None:   # guru: tidak punya status akun
            tk.Label(cell, text="-", bg=C.CARD, fg=C.MUTED,
                     font=(C.FONT, 10)).pack(side="left")
            return
        expired = status == STATUS_EXPIRED
        tk.Label(cell, text="●  " + STATUS_LABEL[status], bg=C.CARD,
                 fg=C.ERROR if expired else C.ON, width=10, anchor="w",
                 font=(C.FONT, 10, "bold")).pack(side="left")
        new = STATUS_ACTIVE if expired else STATUS_EXPIRED
        btn = tk.Button(cell, text="Set Active" if expired else "Set Expired",
                        command=lambda: self._set_status(person["id"], new),
                        bg=C.BG, fg=C.TEXT, activebackground=C.BORDER,
                        activeforeground=C.TEXT, relief="flat", bd=0,
                        highlightthickness=0, font=(C.FONT, 9), cursor="hand2",
                        padx=10, pady=3)
        btn.pack(side="left", padx=(6, 0))
        add_hover(btn, C.BG, C.BORDER)

    def _set_status(self, student_id, status):
        top = self.scroll.canvas.yview()[0]
        try:
            set_status(student_id, status)
        except Exception as exc:
            C.log(f"Gagal mengubah status {student_id}: {exc!r}")
            self.summary.config(
                text="Gagal menyimpan status. Pastikan folder data bisa ditulis.",
                fg=C.ERROR)
            return
        self.refresh()
        self.update_idletasks()
        self.scroll.canvas.yview_moveto(top)   # tetap di posisi gulir semula

    def destroy(self):
        if self._after is not None:
            try:
                self.after_cancel(self._after)
            except Exception:
                pass
            self._after = None
        super().destroy()
