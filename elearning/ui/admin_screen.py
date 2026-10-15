"""Panel admin: memantau aktivitas guru dan murid, melihat laporan kerja guru, mengatur
status murid (active / expired), serta menambah / mengubah / menghapus guru."""

import tkinter as tk

from elearning import config as C
from elearning import photos, reports, sessions
from elearning import teachers as T
from elearning.students import (STATUS_ACTIVE, STATUS_EXPIRED, STATUS_LABEL,
                                list_students, set_status)
from elearning.ui.avatar import Avatar
from elearning.ui.dialogs import ConfirmDialog, TeacherDialog
from elearning.ui.report_widgets import (PeriodBar, PortfolioSummary, ReportCard,
                                         empty_note, section_title)
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
        for key, label in (("students", "Murid"), ("teachers", "Guru"),
                           ("reports", "Laporan Guru")):
            b = tk.Button(bar, text=label, command=lambda k=key: self._set_tab(k),
                          relief="flat", bd=0, highlightthickness=0, cursor="hand2",
                          font=(C.FONT, 10, "bold"), padx=16, pady=6)
            b.pack(side="left", padx=(0, 6))
            self.tab_btns[key] = b
        self.reload_btn = reload_btn = tk.Button(bar, text="Muat ulang", command=self.refresh,
                               bg=C.CARD, fg=C.MUTED, activebackground=C.BORDER,
                               activeforeground=C.TEXT, relief="flat", bd=0,
                               highlightthickness=0, font=(C.FONT, 10),
                               cursor="hand2", padx=14, pady=6)
        reload_btn.pack(side="right")
        add_hover(reload_btn, C.CARD, C.BORDER)
        # Tombol tambah guru: hanya tampil di tab Guru (lihat _layout_tab)
        self.add_btn = tk.Button(bar, text="+  Tambah guru", command=self._add_teacher,
                                 bg=C.ACCENT, fg="white", activebackground=C.ACCENT_HOVER,
                                 activeforeground="white", relief="flat", bd=0,
                                 highlightthickness=0, font=(C.FONT, 10, "bold"),
                                 cursor="hand2", padx=14, pady=6)
        add_hover(self.add_btn, C.ACCENT, C.ACCENT_HOVER)

        self.summary = tk.Label(body, text="", bg=C.BG, fg=C.MUTED,
                                font=(C.FONT, 10), anchor="w")
        self.summary.pack(fill="x", pady=(12, 10))

        self.header = tk.Frame(body, bg=C.BG, padx=14)   # judul kolom (tab Murid / Guru)
        self.header.pack(fill="x")
        self._configure_columns(self.header)
        self.header_labels = []
        for i, (title, _w) in enumerate(COLUMNS):
            lbl = tk.Label(self.header, text=title, bg=C.BG, fg=C.MUTED, anchor="w",
                           font=(C.FONT, 9, "bold"))
            lbl.grid(row=0, column=i, sticky="w")
            self.header_labels.append(lbl)

        # Filter laporan (tab Laporan Guru): periode + guru
        self.rbar = tk.Frame(body, bg=C.BG)
        tk.Label(self.rbar, text="Periode", bg=C.BG, fg=C.MUTED,
                 font=(C.FONT, 10)).pack(side="left", padx=(0, 10))
        self.period = PeriodBar(self.rbar, on_change=self.refresh, key="7d")
        self.period.pack(side="left")
        tk.Label(self.rbar, text="Guru", bg=C.BG, fg=C.MUTED,
                 font=(C.FONT, 10)).pack(side="left", padx=(24, 10))
        self.ALL_TEACHERS = "Semua guru"
        self.teacher_ids = self._teacher_choices(T.list_teachers())
        self.teacher_var = tk.StringVar(value=self.ALL_TEACHERS)
        menu = self.teacher_menu = tk.OptionMenu(
            self.rbar, self.teacher_var, *self.teacher_ids,
            command=lambda _v: self.refresh())
        menu.config(bg=C.CARD, fg=C.TEXT, activebackground=C.BORDER,
                    activeforeground=C.TEXT, relief="flat", bd=0,
                    highlightthickness=0, font=(C.FONT, 10), cursor="hand2")
        menu["menu"].config(bg=C.CARD, fg=C.TEXT, activebackground=C.ACCENT,
                            activeforeground="white", font=(C.FONT, 10), bd=0)
        menu.pack(side="left")

        self.scroll = ScrollFrame(body, bg=C.BG)
        self.scroll.pack(fill="both", expand=True, pady=(6, 0))

        self._paint_tabs()
        self._layout_tab()
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

    def _layout_tab(self):
        """Tab Murid / Guru memakai judul kolom; tab Laporan Guru memakai bar filter."""
        if self.tab == "teachers":
            self.add_btn.pack(side="right", padx=(0, 8), after=self.reload_btn)
        else:
            self.add_btn.pack_forget()
        self.header_labels[-1].config(text="Kelola" if self.tab == "teachers" else "Status akun")
        if self.tab == "reports":
            self.header.pack_forget()
            self.rbar.pack(fill="x", before=self.scroll)
        else:
            self.rbar.pack_forget()
            self.header.pack(fill="x", before=self.scroll)

    def _set_tab(self, key):
        if key == self.tab:
            return
        self.tab = key
        self._paint_tabs()
        self._layout_tab()
        self.scroll.scroll_to_top()
        self.refresh()

    # --- data ------------------------------------------------------------------
    def _people(self):
        if self.tab == "teachers":
            return [{"id": t["id"], "name": t["name"], "sub": "Guru", "teacher": True}
                    for t in T.list_teachers()]
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
        top = self.scroll.canvas.yview()[0]
        for w in self.scroll.inner.winfo_children():
            w.destroy()

        if self.tab == "reports":
            self._refresh_reports()
            self.update_idletasks()
            self.scroll.canvas.yview_moveto(top)   # tetap di posisi gulir semula
            self._after = self.after(REFRESH_MS, self.refresh)
            return

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

    # --- tab Laporan Guru -------------------------------------------------------
    def _refresh_reports(self):
        since, until = self.period.range()
        teachers = T.list_teachers()
        teacher_names = {t["id"]: t["name"] for t in teachers}
        self._rebuild_teacher_menu(teachers)
        teacher_id = self.teacher_ids.get(self.teacher_var.get())
        recs = reports.list_reports(teacher_id, since, until)
        try:
            rows = reports.portfolio_status(since, until)
        except Exception as exc:   # ringkasan gagal tidak boleh menghalangi laporan
            C.log(f"Ringkasan portfolio gagal: {exc!r}")
            rows = []

        who = (f"{len({r['teacher'] for r in recs if r['teacher'] in teacher_names})} "
               f"dari {len(teachers)} guru melapor"
               if teacher_id is None else
               teacher_names.get(teacher_id, teacher_id))
        self.summary.config(
            fg=C.MUTED,
            text=f"{len(recs)} laporan  ·  {who}  ·  "
                 f"diperbarui {sessions.format_time(sessions.datetime.now())}")

        inner = self.scroll.inner
        PortfolioSummary(inner, rows, warn=self.period.key != "today").pack(fill="x")

        section_title(inner, "Laporan guru", f"{len(recs)} laporan")
        if not recs:
            empty_note(inner, "Belum ada laporan pada periode ini.")
        names = {s["id"]: s["name"] for s in list_students()}
        for rec in recs:
            teacher = teacher_names.get(rec["teacher"], f"{rec['teacher']} (sudah dihapus)")
            ReportCard(inner, rec, names.get, teacher_name=teacher).pack(
                fill="x", pady=(0, 8))

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
        if person.get("teacher"):   # guru: tombol Ubah / Hapus
            self._mini_button(cell, "Ubah",
                              lambda: self._edit_teacher(person)).pack(side="left")
            self._mini_button(cell, "Hapus", lambda: self._delete_teacher(person),
                              danger=True).pack(side="left", padx=(6, 0))
            return
        status = person.get("status")
        if status is None:   # cadangan: tidak punya status akun
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

    # --- kelola guru (tab Guru) ----------------------------------------------------
    def _teacher_choices(self, teachers):
        choices = {self.ALL_TEACHERS: None}
        for t in teachers:
            choices[f"{t['name']}  ({t['id']})"] = t["id"]
        return choices

    def _rebuild_teacher_menu(self, teachers):
        """Samakan isi menu filter Laporan Guru dengan daftar guru terbaru."""
        choices = self._teacher_choices(teachers)
        if choices == self.teacher_ids:
            return
        selected = self.teacher_ids.get(self.teacher_var.get())
        self.teacher_ids = choices
        label = next((l for l, tid in choices.items() if tid == selected), self.ALL_TEACHERS)
        self.teacher_var.set(label)
        menu = self.teacher_menu["menu"]
        menu.delete(0, "end")
        for text in choices:
            menu.add_command(label=text, command=lambda t=text: (
                self.teacher_var.set(t), self.refresh()))

    @staticmethod
    def _mini_button(parent, text, command, danger=False):
        btn = tk.Button(parent, text=text, command=command, bg=C.BG,
                        fg=C.ERROR if danger else C.TEXT, activebackground=C.BORDER,
                        activeforeground=C.ERROR if danger else C.TEXT, relief="flat",
                        bd=0, highlightthickness=0, font=(C.FONT, 9), cursor="hand2",
                        padx=10, pady=3)
        add_hover(btn, C.BG, C.BORDER)
        return btn

    def _after_change(self):
        """Muat ulang daftar tapi tetap di posisi gulir semula."""
        top = self.scroll.canvas.yview()[0]
        self.refresh()
        self.update_idletasks()
        self.scroll.canvas.yview_moveto(top)

    @staticmethod
    def _apply_photo(teacher_id, photo):
        """photo: None = tidak berubah, False = hapus foto, gambar Pillow = simpan. True kalau berhasil."""
        try:
            if photo is False:
                photos.remove_photo(teacher_id)
            elif photo is not None:
                photos.save_prepared(teacher_id, photo)
            return True
        except Exception as exc:
            C.log(f"Gagal menyimpan foto {teacher_id}: {exc!r}")
            return False

    def _add_teacher(self):
        def submit(name, pin, photo):
            try:
                teacher = T.add_teacher(name, pin)
            except ValueError as exc:
                return str(exc)
            # Guru baru tanpa foto pilihan = tanpa foto (jangan mewarisi file lama yang tersisa)
            ok = self._apply_photo(teacher["id"], False if photo is None else photo)
            self._after_change()
            if not ok:
                self.summary.config(
                    text=f"{teacher['name']} ditambahkan, tetapi fotonya gagal disimpan.",
                    fg=C.ERROR)
            return None

        TeacherDialog(self, "Tambah guru", submit, teacher_id=T.next_teacher_id(), add=True)

    def _edit_teacher(self, person):
        tid = person["id"]

        def submit(name, pin, photo):
            try:
                T.update_teacher(tid, name, pin or None)
            except ValueError as exc:
                return str(exc)
            ok = self._apply_photo(tid, photo)
            self._after_change()
            if not ok:
                self.summary.config(text=f"Data {tid} tersimpan, tetapi fotonya gagal diubah.",
                                    fg=C.ERROR)
            return None

        TeacherDialog(self, f"Ubah guru {tid}", submit, teacher_id=tid, add=False,
                      name=person["name"])

    def _delete_teacher(self, person):
        tid = person["id"]

        def confirm():
            try:
                T.delete_teacher(tid)
            except ValueError as exc:
                return str(exc)
            self._after_change()
            return None

        ConfirmDialog(
            self, "Hapus guru",
            f"Hapus akun {person['name']} ({tid})? Foto dan riwayat masuk/keluarnya ikut "
            "terhapus dan tidak bisa dikembalikan. Laporan kerja yang pernah ditulis guru "
            "ini tetap tersimpan.", confirm)

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
