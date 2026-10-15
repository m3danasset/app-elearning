"""Layar guru: sidebar kiri (menu + daftar murid) dan area kanan.

Menu "Murid & Kursus": pilih murid di sidebar, lalu buka/kunci tiap kursus dengan
tombol ON/OFF (juga riwayat login dan portfolio murid). Menu "Laporan Kerja":
laporan untuk admin (lihat report_panel.py).
"""

import tkinter as tk

from elearning import config as C
from elearning import photos, portfolio, sessions
from elearning.courses import courses_for
from elearning.students import (STATUS_ACTIVE, STATUS_EXPIRED, STATUS_LABEL,
                                add_student, delete_student, list_students,
                                lookup_student, rename_student, set_course_access,
                                set_status)
from elearning.ui.avatar import Avatar
from elearning.ui.dialogs import ConfirmDialog, StudentDialog
from elearning.ui.portfolio_view import ThumbGrid
from elearning.ui.report_panel import ReportPanel
from elearning.ui.widgets import ScrollFrame, Switch, add_hover

PROGRAM_LABEL = {"adult": "Murid dewasa", "kids": "Murid anak"}
CATEGORIES = ("adult", "kids")  # urutan kategori di sidebar kiri
SIDEBAR_W = 270
VIEW_TITLE = {"students": "Atur Akses Kursus", "reports": "Laporan Kerja"}


class TeacherScreen(tk.Frame):
    def __init__(self, master, teacher, on_logout):
        super().__init__(master, bg=C.BG)
        self.teacher = teacher
        self.on_logout = on_logout
        self.view = "students"   # "students" (murid & kursus) atau "reports" (laporan kerja)
        self.students = list_students()
        self.collapsed = set()   # kategori yang sedang dilipat
        self.current_id = self.students[0]["id"] if self.students else None
        self.tab = "courses"     # tab detail murid: "courses", "history" atau "portfolio"
        self.list_scroll = None  # daftar murid di sidebar (hanya ada di menu Murid)
        self._row_widgets = {}   # id murid -> baris di sidebar

        self.sidebar = tk.Frame(self, bg=C.CARD, width=SIDEBAR_W)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        tk.Frame(self, bg=C.BORDER, width=1).pack(side="left", fill="y")

        # --- Kanan: judul menu + isi ---------------------------------------------
        content = tk.Frame(self, bg=C.BG)
        content.pack(side="left", fill="both", expand=True)
        bar = tk.Frame(content, bg=C.CARD, height=56, highlightthickness=1,
                       highlightbackground=C.BORDER)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        self.title_lbl = tk.Label(bar, text=VIEW_TITLE[self.view], bg=C.CARD, fg=C.TEXT,
                                  font=(C.FONT, 13, "bold"))
        self.title_lbl.pack(side="left", padx=20)
        out = tk.Button(bar, text="Keluar", command=on_logout, bg=C.CARD, fg=C.MUTED,
                        activebackground=C.BORDER, activeforeground=C.TEXT,
                        relief="flat", bd=0, highlightthickness=0, font=(C.FONT, 10),
                        cursor="hand2", padx=14)
        out.pack(side="right", padx=12, pady=12)
        add_hover(out, C.CARD, C.BORDER)

        self.body = tk.Frame(content, bg=C.BG)
        self.body.pack(fill="both", expand=True)

        self._build_sidebar()
        self._render_body()

    # --- pindah menu -------------------------------------------------------------
    def _set_view(self, view):
        if view == self.view:
            return
        self.view = view
        self.title_lbl.config(text=VIEW_TITLE[view])
        self._build_sidebar()
        self._render_body()

    def _render_body(self):
        for w in self.body.winfo_children():
            w.destroy()
        if self.view == "reports":
            ReportPanel(self.body, self.teacher).pack(fill="both", expand=True)
            return
        self._build_student_panel()

    # --- sidebar kiri ------------------------------------------------------------
    def _build_sidebar(self):
        for w in self.sidebar.winfo_children():
            w.destroy()
        sb, t = self.sidebar, self.teacher
        self.list_scroll = None
        self._row_widgets = {}

        if self.view == "students":   # paling bawah: tombol tambah murid
            add_btn = tk.Button(sb, text="+  Tambah murid", command=self._add_student,
                                bg=C.ACCENT, fg="white", activebackground=C.ACCENT_HOVER,
                                activeforeground="white", relief="flat", bd=0,
                                highlightthickness=0, font=(C.FONT, 11, "bold"),
                                cursor="hand2", pady=8)
            add_btn.pack(side="bottom", fill="x", padx=12, pady=(6, 14))
            add_hover(add_btn, C.ACCENT, C.ACCENT_HOVER)

        # Paling atas: foto + nama guru
        head = tk.Frame(sb, bg=C.CARD, padx=16, pady=16)
        head.pack(fill="x")
        Avatar(head, t["id"], t["name"], size=56, bg=C.CARD).pack(side="left")
        who = tk.Frame(head, bg=C.CARD)
        who.pack(side="left", fill="x", expand=True, padx=(12, 4))
        tk.Label(who, text=t["name"], bg=C.CARD, fg=C.TEXT, anchor="w", justify="left",
                 wraplength=160, font=(C.FONT, 12, "bold")).pack(fill="x")
        tk.Label(who, text=f"Guru  ·  {t['id']}", bg=C.CARD, fg=C.MUTED, anchor="w",
                 font=(C.FONT, 9)).pack(fill="x")
        tk.Frame(sb, bg=C.BORDER, height=1).pack(fill="x")

        tk.Label(sb, text="MENU", bg=C.CARD, fg=C.MUTED, anchor="w",
                 font=(C.FONT, 9, "bold")).pack(fill="x", padx=20, pady=(16, 6))
        self._nav_item("Murid & Kursus", "students")
        self._nav_item("Laporan Kerja", "reports")

        if self.view != "students":
            return
        tk.Label(sb, text="MURID", bg=C.CARD, fg=C.MUTED, anchor="w",
                 font=(C.FONT, 9, "bold")).pack(fill="x", padx=20, pady=(18, 6))
        self.list_scroll = ScrollFrame(sb, bg=C.CARD)
        self.list_scroll.pack(fill="both", expand=True, padx=(0, 6))
        self._rebuild_list(keep_scroll=False)

    def _nav_item(self, text, view):
        current = self.view == view
        bg = C.CARD_HOVER if current else C.CARD
        row = tk.Frame(self.sidebar, bg=bg)
        row.pack(fill="x", padx=10, pady=1)
        tk.Frame(row, bg=C.ACCENT if current else "#3a3f4d", width=4).pack(
            side="left", fill="y")
        lbl = tk.Label(row, text=text, bg=bg, fg=C.TEXT, anchor="w", padx=12, pady=8,
                       font=(C.FONT, 10, "bold" if current else "normal"), cursor="hand2")
        lbl.pack(side="left", fill="x", expand=True)
        for w in (row, lbl):
            w.bind("<Button-1>", lambda e, v=view: self._set_view(v))
        if not current:
            for w in (row, lbl):
                w.bind("<Enter>", lambda e, r=row, l=lbl: (r.config(bg=C.CARD_HOVER),
                                                          l.config(bg=C.CARD_HOVER)))
                w.bind("<Leave>", lambda e, r=row, l=lbl: (r.config(bg=C.CARD),
                                                          l.config(bg=C.CARD)))

    def _rebuild_list(self, keep_scroll=True):
        """Isi ulang daftar murid di sidebar (dikelompokkan per kategori)."""
        sc = self.list_scroll
        if self.view != "students" or sc is None:
            return
        top = sc.canvas.yview()[0]
        for w in sc.inner.winfo_children():
            w.destroy()
        self._row_widgets = {}
        if not self.students:
            tk.Label(sc.inner, text="Belum ada murid.", bg=C.CARD, fg=C.MUTED,
                     font=(C.FONT, 10), anchor="w").pack(fill="x", padx=20, pady=6)
        for program in CATEGORIES:
            group = [s for s in self.students if s["program"] == program]
            if not group:
                continue
            folded = program in self.collapsed
            self._group_header(program, len(group), folded)
            if folded:
                continue
            for s in group:
                self._student_row(s)
        self.update_idletasks()
        if keep_scroll:
            sc.canvas.yview_moveto(top)
        else:   # murid terpilih (mis. yang baru ditambah) dibawa ke area yang terlihat
            row = self._row_widgets.get(self.current_id)
            height = max(1, sc.inner.winfo_reqheight())
            sc.canvas.yview_moveto(max(0.0, (row.winfo_y() - 60) / height) if row else 0.0)

    def _group_header(self, program, count, folded):
        lbl = tk.Label(self.list_scroll.inner,
                       text=f"{'▸' if folded else '▾'}  {PROGRAM_LABEL[program].upper()}  ({count})",
                       bg=C.CARD, fg=C.MUTED, anchor="w", padx=20, pady=5,
                       font=(C.FONT, 9, "bold"), cursor="hand2")
        lbl.pack(fill="x", pady=(4, 0))
        lbl.bind("<Button-1>", lambda e, p=program: self._toggle_group(p))
        lbl.bind("<Enter>", lambda e: lbl.config(fg=C.TEXT))
        lbl.bind("<Leave>", lambda e: lbl.config(fg=C.MUTED))

    def _toggle_group(self, program):   # klik judul kategori = lipat / buka
        if program in self.collapsed:
            self.collapsed.discard(program)
        else:
            self.collapsed.add(program)
        self._rebuild_list()

    def _student_row(self, s):
        current = s["id"] == self.current_id
        expired = s.get("status") == STATUS_EXPIRED
        bg = C.CARD_HOVER if current else C.CARD
        row = tk.Frame(self.list_scroll.inner, bg=bg)
        row.pack(fill="x", padx=10, pady=1)
        self._row_widgets[s["id"]] = row
        tk.Frame(row, bg=C.ERROR if expired else (C.ACCENT if current else "#3a3f4d"),
                 width=4).pack(side="left", fill="y")
        text = f"{s['id']}   {s['name']}" + ("   [EXPIRED]" if expired else "")
        lbl = tk.Label(row, text=text, bg=bg, fg=C.ERROR if expired else C.TEXT,
                       anchor="w", justify="left", padx=12, pady=7, wraplength=190,
                       font=(C.FONT, 10, "bold" if current else "normal"), cursor="hand2")
        lbl.pack(side="left", fill="x", expand=True)
        for w in (row, lbl):
            w.bind("<Button-1>", lambda e, sid=s["id"]: self._on_student_click(sid))
        if not current:
            for w in (row, lbl):
                w.bind("<Enter>", lambda e, r=row, l=lbl: (r.config(bg=C.CARD_HOVER),
                                                          l.config(bg=C.CARD_HOVER)))
                w.bind("<Leave>", lambda e, r=row, l=lbl: (r.config(bg=C.CARD),
                                                          l.config(bg=C.CARD)))

    def _on_student_click(self, student_id):
        if student_id == self.current_id:
            return
        self.current_id = student_id
        self._rebuild_list()
        self._show_student(student_id)

    # --- kanan (menu Murid & Kursus): detail murid terpilih ----------------------------
    def _build_student_panel(self):
        self.right = tk.Frame(self.body, bg=C.BG, padx=32, pady=24)
        self.right.pack(fill="both", expand=True)

        # Kepala: foto murid + nama + tombol foto
        head = tk.Frame(self.right, bg=C.BG)
        head.pack(fill="x", pady=(0, 6))
        self.delete_btn = self._small_button(head, "Hapus murid", self._delete_student)
        self.delete_btn.config(fg=C.ERROR, activeforeground=C.ERROR)
        self.delete_btn.pack(side="right", anchor="n")
        self.avatar = Avatar(head, "", "", size=84, bg=C.BG)
        self.avatar.pack(side="left", padx=(0, 18))
        col = tk.Frame(head, bg=C.BG)
        col.pack(side="left", fill="x", expand=True)
        name_row = tk.Frame(col, bg=C.BG)
        name_row.pack(fill="x")
        self.name_lbl = tk.Label(name_row, text="", bg=C.BG, fg=C.TEXT,
                                 font=(C.FONT, 20, "bold"), anchor="w")
        self.name_lbl.pack(side="left")
        # Status akun (Active / Expired): di sebelah kanan nama murid
        self.badge = tk.Label(name_row, text="", bg=C.CARD, font=(C.FONT, 10, "bold"),
                              padx=12, pady=3)
        self.badge.pack(side="left", padx=(14, 0))
        self.sub_lbl = tk.Label(
            col, text="", bg=C.BG, fg=C.MUTED, font=(C.FONT, 11), anchor="w")
        self.sub_lbl.pack(fill="x", pady=(2, 8))
        btns = tk.Frame(col, bg=C.BG)
        btns.pack(anchor="w")
        self.status_btn = self._small_button(btns, "Set Expired", self._toggle_status)
        self.status_btn.pack(side="left", padx=(0, 8))
        self.rename_btn = self._small_button(btns, "Ubah nama…", self._rename_student)
        self.rename_btn.pack(side="left")
        self.photo_btn = self._small_button(btns, "Pilih foto…", self._choose_photo)
        self.photo_btn.pack(side="left", padx=(8, 0))
        self.photo_del_btn = self._small_button(btns, "Hapus foto", self._remove_photo)
        self.photo_del_btn.pack(side="left", padx=(8, 0))

        tabs = tk.Frame(self.right, bg=C.BG)
        tabs.pack(fill="x", pady=(10, 0))
        self.tab_btns = {}
        for key, label in (("courses", "Akses Kursus"), ("history", "Riwayat Login"),
                           ("portfolio", "Portfolio")):
            b = tk.Button(tabs, text=label, command=lambda k=key: self._set_tab(k),
                          relief="flat", bd=0, highlightthickness=0, cursor="hand2",
                          font=(C.FONT, 10, "bold"), padx=16, pady=6)
            b.pack(side="left", padx=(0, 6))
            self.tab_btns[key] = b
        self._paint_tabs()
        self.hint = tk.Label(self.right, text="", bg=C.BG, fg=C.MUTED,
                             font=(C.FONT, 10), anchor="w")
        self.hint.pack(fill="x", pady=(10, 12))

        # Status dipasang dulu di bawah supaya selalu terlihat, sisanya untuk daftar kursus
        self.status = tk.Label(self.right, text="", bg=C.BG, fg=C.MUTED,
                               font=(C.FONT, 10), anchor="w")
        self.status.pack(side="bottom", fill="x", pady=(8, 0))

        self.scroll = ScrollFrame(self.right, bg=C.BG)  # daftar kursus bisa digulir
        self.scroll.pack(fill="both", expand=True)
        self.rows = self.scroll.inner

        self._show_student(self.current_id)

    def _show_student(self, student_id):
        student = lookup_student(student_id) if student_id else None  # data terbaru dari file
        self.status.config(text="")
        if student is None:
            self.name_lbl.config(text="Belum ada murid" if not self.students
                                 else "Murid tidak ditemukan")
            self.sub_lbl.config(text="")
            self.avatar.set_student("", "")
            self._update_photo_buttons()
            self._paint_status(None)
            self._render_tab()
            return

        self.avatar.set_student(student["id"], student["name"])
        self._update_photo_buttons()
        self.name_lbl.config(text=student["name"])
        self.sub_lbl.config(text=f"{student['id']}  ·  "
                                 f"{PROGRAM_LABEL.get(student['program'], '')}")
        self._paint_status(student)
        self._render_tab()

    # --- status murid: active / expired ------------------------------------------
    def _paint_status(self, student):
        if student is None:
            self.badge.pack_forget()
            self.status_btn.config(state="disabled")
            return
        expired = student.get("status") == STATUS_EXPIRED
        self.badge.config(text=f"●  {STATUS_LABEL[STATUS_EXPIRED if expired else STATUS_ACTIVE].upper()}",
                          fg=C.ERROR if expired else C.ON)
        if not self.badge.winfo_ismapped():
            self.badge.pack(side="left", padx=(14, 0))
        self.status_btn.config(text="Set Active" if expired else "Set Expired",
                               state="normal")

    def _toggle_status(self):
        sid = self.current_id
        student = lookup_student(sid) if sid else None
        if student is None:
            return
        new = (STATUS_ACTIVE if student.get("status") == STATUS_EXPIRED
               else STATUS_EXPIRED)
        try:
            set_status(sid, new)
        except Exception as exc:
            C.log(f"Gagal mengubah status {sid}: {exc!r}")
            self.status.config(text="Gagal menyimpan status. Pastikan folder data bisa ditulis.",
                               fg=C.ERROR)
            return
        self.students = list_students()
        self._rebuild_list()
        self._paint_status(lookup_student(sid))
        if new == STATUS_EXPIRED:
            msg = f"{sid} ({student['name']}) sekarang EXPIRED: tidak bisa login."
        else:
            msg = f"{sid} ({student['name']}) sekarang ACTIVE: bisa login lagi."
        self.status.config(text=msg, fg=C.MUTED)

    # --- tab: akses kursus / riwayat login --------------------------------------
    def _paint_tabs(self):
        for key, b in self.tab_btns.items():
            on = key == self.tab
            b.config(bg=C.ACCENT if on else C.CARD, fg="white" if on else C.MUTED,
                     activebackground=C.ACCENT_HOVER if on else C.BORDER,
                     activeforeground="white" if on else C.TEXT)

    def _set_tab(self, key):
        if key == self.tab:
            return
        self.tab = key
        self._paint_tabs()
        self._render_tab()

    def _render_tab(self):
        """Isi area kanan bawah sesuai tab untuk murid yang sedang dipilih."""
        for w in self.rows.winfo_children():
            w.destroy()
        self.scroll.scroll_to_top()
        student = lookup_student(self.current_id) if self.current_id else None
        if student is None:
            self.hint.config(text="")
            return
        if self.tab == "history":
            self.hint.config(text="Kapan murid masuk dan keluar aplikasi, beserta lama belajarnya.")
            self._build_history(student)
        elif self.tab == "portfolio":
            self.hint.config(text="Gambar dan video hasil karya murid, per kursus. "
                                  "Klik thumbnail untuk membukanya.")
            self._build_portfolio(student)
        else:
            self.hint.config(text="ON = kursus terbuka, OFF = terkunci. "
                                  "Perubahan langsung tersimpan.")
            allowed = set(student["courses"])
            for course in courses_for(student["program"]):
                self._build_row(student["id"], course, course["id"] in allowed)

    def _build_portfolio(self, student):
        total = images = videos = 0
        sections = []
        for course in courses_for(student["program"]):
            items = portfolio.list_items(student["id"], course["id"])
            if items:
                sections.append((course, items))
                total += len(items)
                videos += sum(1 for i in items if i["kind"] == "video")
        images = total - videos

        if not sections:
            tk.Label(self.rows, text="Murid ini belum mengunggah portfolio.",
                     bg=C.BG, fg=C.MUTED, font=(C.FONT, 10), anchor="w").pack(fill="x", pady=8)
            return
        tk.Label(self.rows, text=f"{total} file  ·  {images} gambar  ·  {videos} video",
                 bg=C.BG, fg=C.TEXT, font=(C.FONT, 11, "bold"), anchor="w").pack(
                     fill="x", pady=(0, 6))
        for course, items in sections:
            head = tk.Frame(self.rows, bg=C.BG)
            head.pack(fill="x", pady=(10, 0))
            tk.Frame(head, bg=course["color"], width=4, height=18).pack(side="left", padx=(0, 10))
            tk.Label(head, text=course["title"], bg=C.BG, fg=C.TEXT,
                     font=(C.FONT, 11, "bold")).pack(side="left")
            tk.Label(head, text=f"  {len(items)} file", bg=C.BG, fg=C.MUTED,
                     font=(C.FONT, 10)).pack(side="left")
            ThumbGrid(self.rows, items, on_error=lambda msg: self.status.config(
                text=msg, fg=C.ERROR)).pack(fill="x")

    def _build_history(self, student):
        items = sessions.entries(student["id"])
        total = sum(e["seconds"] for e in items)

        # Ringkasan: total belajar, jumlah masuk, terakhir masuk
        box = tk.Frame(self.rows, bg=C.CARD, highlightthickness=1,
                       highlightbackground=C.BORDER)
        box.pack(fill="x", pady=(0, 10))
        last = (f"{sessions.format_date(items[0]['start'])}, "
                f"{sessions.format_time(items[0]['start'])}") if items else "—"
        for label, value in (("Total belajar", sessions.format_duration(total)),
                             ("Jumlah masuk", f"{len(items)}x"),
                             ("Terakhir masuk", last)):
            cell = tk.Frame(box, bg=C.CARD, padx=18, pady=12)
            cell.pack(side="left")
            tk.Label(cell, text=label, bg=C.CARD, fg=C.MUTED, font=(C.FONT, 9),
                     anchor="w").pack(fill="x")
            tk.Label(cell, text=value, bg=C.CARD, fg=C.TEXT, font=(C.FONT, 13, "bold"),
                     anchor="w").pack(fill="x")

        if not items:
            tk.Label(self.rows, text="Belum ada riwayat login. Riwayat tercatat sejak "
                                     "murid ini masuk setelah pembaruan ini.",
                     bg=C.BG, fg=C.MUTED, font=(C.FONT, 10), anchor="w",
                     wraplength=460, justify="left").pack(fill="x", pady=8)
            return

        for e in items[:200]:
            row = tk.Frame(self.rows, bg=C.CARD, highlightthickness=1,
                           highlightbackground=C.BORDER)
            row.pack(fill="x", pady=3)
            dur = tk.Label(row, text=sessions.format_duration(e["seconds"]), bg=C.CARD,
                           fg=C.ACCENT, font=(C.FONT, 12, "bold"), width=9, anchor="e")
            dur.pack(side="right", padx=(8, 16))
            info = tk.Frame(row, bg=C.CARD, padx=16, pady=9)
            info.pack(side="left", fill="x", expand=True)
            tk.Label(info, text=sessions.format_date(e["start"]), bg=C.CARD, fg=C.TEXT,
                     font=(C.FONT, 11, "bold"), anchor="w").pack(fill="x")
            tk.Label(info, text=self._time_range(e), bg=C.CARD, fg=C.MUTED,
                     font=(C.FONT, 10), anchor="w").pack(fill="x")
        if len(items) > 200:
            tk.Label(self.rows, text=f"Menampilkan 200 dari {len(items)} catatan terbaru.",
                     bg=C.BG, fg=C.MUTED, font=(C.FONT, 9), anchor="w").pack(fill="x", pady=6)

    @staticmethod
    def _time_range(e):
        """'Masuk 09:15   Keluar 12:45' (tambah tanggal kalau keluarnya beda hari)."""
        out = "sedang masuk"
        if e["end"] is not None:
            out = sessions.format_time(e["end"])
            if e["end"].date() != e["start"].date():
                out = f"{e['end'].day}/{e['end'].month} {out}"
            if e["approx"]:
                out = f"~{out} (aplikasi tidak ditutup normal)"
        return f"Masuk {sessions.format_time(e['start'])}   ·   Keluar {out}"

    # --- hapus murid ---------------------------------------------------------------
    def _delete_student(self):
        sid = self.current_id
        student = lookup_student(sid) if sid else None
        if student is None:
            return
        done = []

        def confirm():
            try:
                delete_student(sid)
            except ValueError as exc:
                return str(exc)
            done.append(True)
            return None

        ConfirmDialog(
            self, "Hapus murid?",
            f"{student['name']} ({sid}) akan dihapus. Akun, foto, riwayat login, dan "
            "portfolio murid ini ikut hilang dan tidak bisa dikembalikan.",
            confirm, confirm_text="Hapus").wait_window()
        if not done:  # dibatalkan
            return
        old_ids = [s["id"] for s in self.students]
        pos = old_ids.index(sid) if sid in old_ids else 0
        self.students = list_students()
        if self.students:  # pilih murid yang tadinya tepat di bawahnya
            self.current_id = self.students[min(pos, len(self.students) - 1)]["id"]
        else:
            self.current_id = None
        self._rebuild_list(keep_scroll=False)
        self._show_student(self.current_id)
        self.status.config(text=f"Murid {sid} ({student['name']}) dihapus.", fg=C.MUTED)

    # --- tambah murid & ubah nama ---------------------------------------------
    def _add_student(self):
        created = {}

        def submit(name, program, sid):
            try:
                created.update(add_student(name, program, sid))
            except ValueError as exc:
                return str(exc)
            return None

        program = "adult"
        cur = lookup_student(self.current_id) if self.current_id else None
        if cur is not None:
            program = cur["program"]   # kategori awal = kategori murid yang sedang dipilih
        StudentDialog(self, "Tambah murid", submit, add=True, program=program,
                      submit_text="Tambah").wait_window()
        if not created:  # dibatalkan
            return
        self.students = list_students()
        self.current_id = created["id"]
        self.collapsed.discard(created["program"])  # pastikan kategorinya terbuka
        self._rebuild_list(keep_scroll=False)
        self._show_student(created["id"])
        self.status.config(
            text=f"Murid {created['id']} ({created['name']}) ditambahkan. "
                 "Semua kursus masih terkunci: geser ON untuk membukanya.",
            fg=C.MUTED)

    def _rename_student(self):
        sid = self.current_id
        student = lookup_student(sid) if sid else None
        if student is None:
            return
        done = {}

        def submit(name, _program, _sid):
            try:
                done.update(rename_student(sid, name))
            except ValueError as exc:
                return str(exc)
            return None

        StudentDialog(self, f"Ubah nama {sid}", submit, add=False,
                      name=student["name"], submit_text="Simpan").wait_window()
        if not done:  # dibatalkan
            return
        self.students = list_students()
        self._rebuild_list()
        self._show_student(sid)
        self.status.config(text=f"Nama {sid} diubah menjadi {done['name']}.", fg=C.MUTED)

    # --- foto profil murid ---------------------------------------------------
    @staticmethod
    def _small_button(parent, text, command):
        btn = tk.Button(parent, text=text, command=command, bg=C.CARD, fg=C.TEXT,
                        activebackground=C.BORDER, activeforeground=C.TEXT,
                        disabledforeground=C.LOCKED, relief="flat", bd=0,
                        highlightthickness=0, font=(C.FONT, 10), cursor="hand2",
                        padx=14, pady=5)
        add_hover(btn, C.CARD, C.CARD_HOVER)
        return btn

    def _update_photo_buttons(self):
        has = photos.has_photo(self.current_id) if self.current_id else False
        self.photo_btn.config(state="normal" if self.current_id else "disabled")
        self.rename_btn.config(state="normal" if self.current_id else "disabled")
        self.delete_btn.config(state="normal" if self.current_id else "disabled")
        self.photo_del_btn.config(state="normal" if has else "disabled")
        self.photo_btn.config(text="Ganti foto…" if has else "Pilih foto…")

    def _pick_image(self, title):
        """Dialog pilih file bawaan Windows (lewat Tk, tanpa modul tambahan)."""
        try:
            result = self.tk.call(
                "tk_getOpenFile", "-parent", str(self.winfo_toplevel()),
                "-title", title, "-filetypes",
                (("Gambar", (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")),
                 ("Semua file", "*")))
            return str(result).strip()
        except Exception as exc:
            C.log(f"Dialog pilih foto gagal: {exc!r}")
            self.status.config(text="Dialog pilih file tidak bisa dibuka.", fg=C.ERROR)
            return ""

    def _choose_photo(self):
        sid = self.current_id
        if not sid:
            return
        path = self._pick_image(f"Pilih foto untuk {sid}")
        if not path:  # dibatalkan
            return
        try:
            photos.set_photo(sid, path)
        except Exception as exc:
            C.log(f"Gagal memasang foto {sid} dari {path!r}: {exc!r}")
            self.status.config(
                text="Foto tidak bisa dipakai. Pilih file JPG atau PNG yang tidak rusak.",
                fg=C.ERROR)
            return
        if sid == self.current_id:
            self.avatar.refresh()
            self._update_photo_buttons()
        self.status.config(text=f"Foto {sid} tersimpan (dipotong persegi dari tengah).",
                           fg=C.MUTED)

    def _remove_photo(self):
        sid = self.current_id
        if not sid:
            return
        try:
            photos.remove_photo(sid)
        except OSError as exc:
            C.log(f"Gagal menghapus foto {sid}: {exc!r}")
            self.status.config(text="Foto tidak bisa dihapus.", fg=C.ERROR)
            return
        self.avatar.refresh()
        self._update_photo_buttons()
        self.status.config(text=f"Foto {sid} dihapus.", fg=C.MUTED)

    def _build_row(self, student_id, course, unlocked):
        row = tk.Frame(self.rows, bg=C.CARD, highlightthickness=1,
                       highlightbackground=C.BORDER)
        row.pack(fill="x", pady=4)
        tk.Frame(row, bg=course["color"], width=5).pack(side="left", fill="y")

        info = tk.Frame(row, bg=C.CARD, padx=16, pady=10)
        info.pack(side="left", fill="x", expand=True)
        tk.Label(info, text=course["title"], bg=C.CARD, fg=C.TEXT,
                 font=(C.FONT, 12, "bold"), anchor="w").pack(fill="x")
        tk.Label(info, text=course["desc"], bg=C.CARD, fg=C.MUTED,
                 font=(C.FONT, 9), anchor="w").pack(fill="x")

        state = tk.Label(row, bg=C.CARD, font=(C.FONT, 10, "bold"), width=9)
        self._paint_state(state, unlocked)

        def on_change(new_value):
            try:
                set_course_access(student_id, course["id"], new_value)
            except Exception as exc:
                C.log(f"Gagal menyimpan akses {student_id}/{course['id']}: {exc!r}")
                self.status.config(
                    text="Gagal menyimpan. Pastikan folder data bisa ditulis.",
                    fg=C.ERROR)
                return False
            self._paint_state(state, new_value)
            self.status.config(
                text=f"Tersimpan: {course['title']} untuk {student_id} "
                     f"{'DIBUKA' if new_value else 'DIKUNCI'}.",
                fg=C.MUTED)
            return True

        sw = Switch(row, value=unlocked, command=on_change, bg=C.CARD)
        sw.pack(side="right", padx=(8, 18))
        state.pack(side="right")

    @staticmethod
    def _paint_state(label, unlocked):
        label.config(text="TERBUKA" if unlocked else "TERKUNCI",
                     fg=C.ON if unlocked else C.LOCKED)
