"""Layar guru: sidebar kiri (menu + daftar murid) dan area kanan.

Menu "Murid & Kursus": pilih murid di sidebar, lalu buka/kunci tiap kursus dengan
tombol ON/OFF (juga riwayat login dan portfolio murid). Menu "Laporan Kerja":
laporan untuk admin (lihat report_panel.py).
"""

import tkinter as tk

from elearning import config as C
from elearning.ui.controls import RoundButton, RoundPanel
from elearning import photos, portfolio, sessions
from elearning.courses import courses_for
from elearning.students import (STATUS_ACTIVE, STATUS_EXPIRED, STATUS_LABEL,
                                add_student, delete_student, list_students, reset_progress,
                                lookup_student, rename_student, set_course_access,
                                set_status)
from elearning.ui import ui_icons as I
from elearning.ui.avatar import Avatar
from elearning.ui.dialogs import ConfirmDialog, StudentDialog
from elearning.ui.gallery import GalleryBoard
from elearning.ui.portfolio_view import ExamplesPanel
from elearning.ui.task_sheet_view import TaskSheetPanel
from elearning.ui.sidebar import AppSidebar, PageHeader, SidebarLayout
from elearning.ui.teacher_progress import ProgressBoard, QuizPanel
from elearning.ui.widgets import ScrollFrame, Switch, add_hover

PROGRAM_LABEL = {"adult": "Murid dewasa", "kids": "Murid anak"}
CATEGORIES = ("adult", "kids")  # urutan kategori di daftar murid
LIST_SORTS = ("Kategori", "Nama A–Z", "ID")
VIEW_TITLE = {"dashboard": "Dashboard", "live": "Live Kelas", "students": "Murid & Kursus", "reports": "Laporan Kerja", "quizzes": "Kuis",
              "examples": "Bahan dari Guru", "schedule": "Jadwal Murid",
              "certificates": "Sertifikat"}


class TeacherScreen(SidebarLayout):
    def __init__(self, master, teacher, on_logout):
        super().__init__(master)
        self.teacher = teacher
        self.on_logout = on_logout
        self.view = "dashboard"  # halaman pertama: kartu notifikasi / hal yang perlu dikerjakan
        self.students = list_students()
        self.collapsed = set()   # kategori yang sedang dilipat
        self.current_id = self.students[0]["id"] if self.students else None
        self.tab = "courses"     # tab detail murid: "courses", "history" atau "portfolio"
        self._row_widgets = {}   # id murid -> baris di daftar murid (halaman Murid & Kursus)
        self._list_ok = False    # daftar murid di halaman Murid & Kursus sudah dibuat

        self.sb = AppSidebar(self, teacher, f"Guru  ·  {teacher['id']}", on_logout,
                             self._populate, placeholder="Cari murid (nama / ID)",
                             on_search=self._on_search, palette=True)
        self.attach(self.sb)   # cari: kolom sidebar membuka search palette (seperti murid)

        # --- Kanan: judul menu + isi ---------------------------------------------
        self.header = PageHeader(self.content, VIEW_TITLE[self.view])
        # Tambah murid: tombol di kepala halaman Murid & Kursus (juga aksi di Ctrl+K)
        self.add_btn = self.header.button("Tambah murid", self._add_student, primary=True,
                                          icon="plus")
        if self.view != "students":
            self.add_btn.pack_forget()
        if self.view != "dashboard":      # Dashboard: halaman penuh tanpa judul
            self.header.pack(fill="x")
        self.body = tk.Frame(self.content, bg=C.BG)
        self.body.pack(fill="both", expand=True)
        self._render_body()

    # --- pindah menu -------------------------------------------------------------
    def _set_view(self, view):
        if view == self.view:
            return
        self.view = view
        self.header.set_title(VIEW_TITLE[view])
        if view == "dashboard":
            self.header.pack_forget()
        elif not self.header.winfo_manager():
            self.header.pack(fill="x", before=self.body)
        if view == "students":
            if not self.add_btn.winfo_manager():
                self.add_btn.pack(side="right", padx=(8, 0))
        else:
            self.add_btn.pack_forget()
        self.sb.refresh()
        self._render_body()

    def _render_body(self):
        for w in self.body.winfo_children():
            w.destroy()
        if self.view == "dashboard":
            from elearning.ui.dashboard_view import DashboardView
            DashboardView(self.body, "teacher", self.teacher,
                          on_action=self._set_view).pack(fill="both", expand=True)
            return
        if self.view == "reports":
            TaskSheetPanel(self.body, self.teacher).pack(fill="both", expand=True)
            return
        if self.view == "live":         # murid online sekarang + kelas guru yang berjalan
            from elearning.ui.live_view import LiveBoard
            from elearning.ui.widgets import ScrollFrame
            wrap = tk.Frame(self.body, bg=C.BG, padx=28, pady=8)
            wrap.pack(fill="both", expand=True)
            sf = ScrollFrame(wrap, bg=C.BG)
            sf.pack(fill="both", expand=True)
            LiveBoard(sf.inner, teacher_id=self.teacher["id"],
                      on_open=self.open_student).pack(fill="x", padx=(0, 12))
            return
        if self.view == "examples":
            ExamplesPanel(self.body).pack(fill="both", expand=True)
            return
        if self.view == "schedule":     # guru: hanya lihat, per hari
            from elearning.ui.schedule_view import TeacherSchedule
            TeacherSchedule(self.body).pack(fill="both", expand=True)
            return
        if self.view == "quizzes":
            QuizPanel(self.body, self.teacher).pack(fill="both", expand=True)
            return
        if self.view == "certificates":     # permintaan sertifikat murid
            from elearning import certificates
            from elearning.ui.certificate_view import CertificateBoard
            from elearning.ui.widgets import ScrollFrame
            wrap = tk.Frame(self.body, bg=C.BG, padx=28, pady=8)
            wrap.pack(fill="both", expand=True)
            sf = ScrollFrame(wrap, bg=C.BG)
            sf.pack(fill="both", expand=True)
            board = CertificateBoard(sf.inner, by=self.teacher["id"])
            board.pack(fill="x")
            board.show(certificates.list_requests())
            return
        self._build_student_panel()

    # --- sidebar kiri ------------------------------------------------------------
    def _populate(self, sb):
        sb.nav("Dashboard", "home", lambda: self._set_view("dashboard"),
               active=self.view == "dashboard")
        sb.nav("Live Kelas", "play", lambda: self._set_view("live"),
               active=self.view == "live")
        sb.nav("Murid & Kursus", "users", lambda: self._set_view("students"),
               active=self.view == "students")
        sb.nav("Bahan dari Guru", "image", lambda: self._set_view("examples"),
               active=self.view == "examples")
        sb.nav("Laporan Kerja", "report", lambda: self._set_view("reports"),
               active=self.view == "reports")
        sb.nav("Jadwal Murid", "clock", lambda: self._set_view("schedule"),
               active=self.view == "schedule")
        try:
            from elearning import certificates
            waiting = certificates.pending_count()
        except Exception:
            waiting = 0
        sb.nav("Sertifikat", "check", lambda: self._set_view("certificates"),
               active=self.view == "certificates", right=str(waiting) if waiting else None)
        sb.nav("Kuis", "quiz", lambda: self._set_view("quizzes"),
               active=self.view == "quizzes")

    def search_sources(self):
        from elearning.ui.search_sources import teacher_sources
        return teacher_sources(self)

    def open_student(self, student_id):
        """Dari search palette: tampilkan murid itu (daftar murid ikut menunjuknya)."""
        self.students = list_students()
        self.collapsed.clear()
        self._on_student_click(student_id)
        self._rebuild_list(keep_scroll=False)

    def _on_search(self, _query):
        self.sb.refresh(keep_scroll=False)

    # --- daftar murid (kolom kiri halaman Murid & Kursus) ------------------------------
    def _build_student_list(self, parent):
        """Kolom daftar murid: urutan (Nama A-Z / ID / Kategori) + daftar yang bisa digulir."""
        from elearning.ui.controls import RoundSelect
        col = tk.Frame(parent, bg=C.BG, width=290)
        col.pack(side="left", fill="y")
        col.pack_propagate(False)
        bar = tk.Frame(col, bg=C.BG)
        bar.pack(fill="x", padx=(20, 8), pady=(18, 8))
        tk.Label(bar, text="Urutkan", bg=C.BG, fg=C.MUTED, font=(C.FONT, 10)).pack(
            side="left", padx=(0, 8))
        self.list_sort = tk.StringVar(value=getattr(TeacherScreen, "_sort", LIST_SORTS[0]))
        RoundSelect(bar, self.list_sort, *LIST_SORTS, command=self._set_list_sort).pack(
            side="left")
        self.list_scroll = ScrollFrame(col, bg=C.BG)
        self.list_scroll.pack(fill="both", expand=True, padx=(12, 0))
        tk.Frame(parent, bg=C.BORDER, width=1).pack(side="left", fill="y", pady=12)
        self._list_ok = True
        self._fill_list()

    def _fill_list(self):
        inner = self.list_scroll.inner
        for w in inner.winfo_children():
            w.destroy()
        self._row_widgets = {}
        mode = self.list_sort.get()
        if mode != "Kategori":           # Nama A-Z / ID: satu daftar rata, tanpa kelompok
            key = (lambda s: s["id"]) if mode == "ID" else \
                (lambda s: (s["name"].lower(), s["id"]))
            for s in sorted(self.students, key=key):
                self._row_widgets[s["id"]] = self._student_row(inner, s)
            if not self.students:
                tk.Label(inner, text="Belum ada murid.", bg=C.BG, fg=C.MUTED,
                         font=(C.FONT, 10)).pack(fill="x", padx=10, pady=10)
            return
        for program in CATEGORIES:
            group = sorted((s for s in self.students if s["program"] == program),
                           key=lambda s: (s["name"].lower(), s["id"]))
            if not group:
                continue
            folded = program in self.collapsed
            head = tk.Frame(inner, bg=C.BG, cursor="hand2")
            head.pack(fill="x", pady=(10, 2))
            tk.Label(head, text=("▸ " if folded else "▾ ") + PROGRAM_LABEL[program], bg=C.BG,
                     fg=C.MUTED, font=(C.FONT, 9, "bold"), anchor="w").pack(side="left", padx=8)
            tk.Label(head, text=str(len(group)), bg=C.BG, fg=C.MUTED,
                     font=(C.FONT, 9)).pack(side="right", padx=8)
            for w in (head, *head.winfo_children()):
                w.bind("<Button-1>", lambda e, p=program: self._toggle_group(p))
            if folded:
                continue
            for s in group:
                self._row_widgets[s["id"]] = self._student_row(inner, s)
        if not self.students:
            tk.Label(inner, text="Belum ada murid.", bg=C.BG, fg=C.MUTED,
                     font=(C.FONT, 10)).pack(fill="x", padx=10, pady=10)

    def _set_list_sort(self, value):
        self.list_sort.set(value)
        TeacherScreen._sort = value      # diingat selama app terbuka
        self._rebuild_list(keep_scroll=False)

    def _rebuild_list(self, keep_scroll=True):
        """Isi ulang daftar murid (dikelompokkan per kategori); murid terpilih dibawa ke area
        yang terlihat kalau keep_scroll False (mis. murid baru ditambah)."""
        if not self._list_ok:
            return
        try:
            if not self.list_scroll.winfo_exists():
                return
            top = self.list_scroll.canvas.yview()[0]
            self._fill_list()
            self.list_scroll.update_idletasks()
            if keep_scroll:
                self.list_scroll.canvas.yview_moveto(top)
            else:
                row = self._row_widgets.get(self.current_id)
                inner_h = max(1, self.list_scroll.inner.winfo_reqheight())
                self.list_scroll.canvas.yview_moveto(
                    max(0.0, (row.winfo_y() - 60) / inner_h) if row is not None else 0.0)
        except tk.TclError:
            pass

    def _student_row(self, parent, s):
        """Satu baris murid: nama (merah kalau expired) + ID; yang terpilih disorot."""
        expired = s.get("status") == STATUS_EXPIRED
        current = s["id"] == self.current_id
        bg = C.SIDEBAR_ACTIVE if current else C.BG
        row = tk.Frame(parent, bg=bg, cursor="hand2")
        row.pack(fill="x", pady=1)
        left = tk.Label(row, text=s["name"], bg=bg, fg=C.ERROR if expired else C.TEXT,
                        font=(C.FONT, 10), anchor="w")
        left.pack(side="left", padx=(10, 4), pady=6)
        right = tk.Label(row, text=f"{s['id']}  ·  expired" if expired else s["id"], bg=bg,
                         fg=C.MUTED, font=(C.FONT, 8))
        right.pack(side="right", padx=8)
        widgets = (row, left, right)
        for w in widgets:
            w.bind("<Button-1>", lambda e, sid=s["id"]: self._on_student_click(sid))
            if not current:
                w.bind("<Enter>", lambda e, ws=widgets: [x.config(bg=C.CARD_HOVER) for x in ws])
                w.bind("<Leave>", lambda e, ws=widgets: [x.config(bg=C.BG) for x in ws])
        return row

    def _toggle_group(self, program):   # klik judul kategori = lipat / buka
        if program in self.collapsed:
            self.collapsed.discard(program)
        else:
            self.collapsed.add(program)
        self._rebuild_list()

    def _on_student_click(self, student_id):
        if self.view != "students":
            self.current_id = student_id
            self._set_view("students")
            return
        if student_id == self.current_id:
            return
        self.current_id = student_id
        self._rebuild_list()
        self._show_student(student_id)

    # --- kanan (menu Murid & Kursus): detail murid terpilih ----------------------------
    def _build_student_panel(self):
        self._build_student_list(self.body)       # kolom kiri: daftar murid
        self.right = tk.Frame(self.body, bg=C.BG, padx=32, pady=24)
        self.right.pack(side="left", fill="both", expand=True)

        # Kepala: foto murid + nama + tombol foto
        head = tk.Frame(self.right, bg=C.BG)
        head.pack(fill="x", pady=(0, 6))
        self.delete_btn = self._small_button(head, "Hapus murid", self._delete_student)
        self.delete_btn.config(fg=C.ERROR, activeforeground=C.ERROR)
        self.delete_btn.pack(side="right", anchor="n")
        self.reset_btn = self._small_button(head, "Reset progres", self._reset_progress)
        self.reset_btn.pack(side="right", anchor="n", padx=(0, 8))
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
        self.badge = RoundButton(name_row, text="", bg=C.CARD, font=(C.FONT, 10, "bold"),
                                 radius=13, cursor="arrow",
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
        # batas Pinterest murid ini (hanya murid yang punya akses Pinterest)
        self.pin_btn = self._small_button(btns, "Chrome…", self._pinterest_limit)

        tabs = tk.Frame(self.right, bg=C.BG)
        tabs.pack(fill="x", pady=(10, 0))
        self.tab_btns = {}
        for key, label in (("courses", "Akses Kursus"), ("progress", "Progres Belajar"),
                           ("history", "Riwayat Login"), ("portfolio", "Portfolio"),
                           ("assignment", "Assignment"), ("badges", "Badge")):
            b = RoundButton(tabs, text=label, command=lambda k=key: self._set_tab(k),
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
        from elearning.students import age_text   # umur saja (tanggal lahir diatur admin)
        age = age_text(student)
        self.sub_lbl.config(text=f"{student['id']}  ·  "
                                 f"{PROGRAM_LABEL.get(student['program'], '')}"
                                 + (f"  ·  {age}" if age else ""))
        self._paint_status(student)
        self._render_tab()

    # --- status murid: active / expired ------------------------------------------
    def _paint_status(self, student):
        if student is None:
            self.badge.pack_forget()
            self.status_btn.config(state="disabled")
            return
        expired = student.get("status") == STATUS_EXPIRED
        self.badge.config(text=f"●  {STATUS_LABEL[STATUS_EXPIRED if expired else STATUS_ACTIVE]}",
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
            b.config(bg=C.SEG_ON if on else C.BG, fg=C.TEXT if on else C.MUTED,
                     activebackground=C.SEG_ON if on else C.CARD_HOVER,
                     activeforeground=C.TEXT)

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
        if self.tab == "progress":
            self.hint.config(text="Video yang sudah ditonton, posisi terakhir, "
                             + ("catatan murid" if student["program"] == "adult"
                                else "emote murid") + ", dan jawaban kuis.")
            ProgressBoard(self.rows, student).pack(fill="x")
        elif self.tab == "history":
            self.hint.config(text="Kapan murid masuk dan keluar aplikasi, beserta lama belajarnya.")
            self._build_history(student)
        elif self.tab == "badges":
            self.hint.config(text="Badge yang sudah didapat murid. Badge Masuk Galeri "
                                  "diberikan guru untuk karya terbaik.")
            from elearning.ui.badge_ui import BadgeBoard
            BadgeBoard(self.rows, student, teacher=True).pack(fill="x")
        elif self.tab == "assignment":
            self.hint.config(text="Hasil render assignment yang diunggah murid, per kursus. "
                                  "Klik thumbnail untuk membukanya.")
            self._build_portfolio(student, portfolio.ASSIGNMENT)
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

    def _build_portfolio(self, student, section=None):
        total = images = videos = 0
        sections = []
        for course in courses_for(student["program"]):
            if section and not course.get("video", True):
                continue
            items = portfolio.list_items(student["id"], course["id"], section)
            if items:
                sections.append((course, items))
                total += len(items)
                videos += sum(1 for i in items if i["kind"] == "video")
        images = total - videos

        if not sections:
            tk.Label(self.rows, text="Murid ini belum mengunggah "
                     + ("assignment." if section else "portfolio."),
                     bg=C.BG, fg=C.MUTED, font=(C.FONT, 10), anchor="w").pack(fill="x", pady=8)
            return
        tk.Label(self.rows, text=f"{total} file  ·  {images} gambar  ·  {videos} video",
                 bg=C.BG, fg=C.TEXT, font=(C.FONT, 11, "bold"), anchor="w").pack(
                     fill="x", pady=(0, 6))
        for course, items in sections:
            head = tk.Frame(self.rows, bg=C.BG)
            head.pack(fill="x", pady=(10, 0))
            dot = I.dot(course["color"], C.BG, 10)
            if dot is not None:
                d = tk.Label(head, image=dot, bg=C.BG, bd=0)
                d.image = dot
                d.pack(side="left", padx=(0, 8))
            tk.Label(head, text=course["title"], bg=C.BG, fg=C.TEXT,
                     font=(C.FONT, 11, "bold")).pack(side="left")
            tk.Label(head, text=f"  {len(items)} file", bg=C.BG, fg=C.MUTED,
                     font=(C.FONT, 10)).pack(side="left")
            g = GalleryBoard(self.rows, on_open=self._open_item)   # galeri gaya Behance
            g.pack(fill="x", pady=(8, 0))
            g.set_items([dict(it, own=True) for it in items])

    def _open_item(self, item):
        try:
            portfolio.open_file(item["path"])
        except Exception as exc:
            C.log(f"Gagal membuka {item['path']!r}: {exc!r}")
            self.status.config(text="File tidak bisa dibuka.", fg=C.ERROR)

    def _build_history(self, student):
        items = sessions.entries(student["id"])
        total = sum(e["seconds"] for e in items)

        # Ringkasan: total belajar, jumlah masuk, terakhir masuk
        panel = RoundPanel(self.rows, padx=4, pady=2)
        panel.pack(fill="x", pady=(0, 10))
        box = panel.inner
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
            panel = RoundPanel(self.rows, padx=2, pady=0)
            panel.pack(fill="x", pady=3)
            row = panel.inner
            dur = tk.Label(row, text=sessions.format_duration(e["seconds"]), bg=C.CARD,
                           fg=C.TEXT, font=(C.FONT, 11), width=9, anchor="e")
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

    # --- reset progres murid --------------------------------------------------------
    def _reset_progress(self):
        sid = self.current_id
        student = lookup_student(sid) if sid else None
        if student is None:
            return
        done = []

        def confirm():
            try:
                reset_progress(sid)
            except ValueError as exc:
                return str(exc)
            done.append(True)
            return None

        ConfirmDialog(
            self, "Reset progres?",
            f"Progres {student['name']} ({sid}) dikembalikan ke awal: video yang sudah "
            "ditonton, posisi lanjut tonton, catatan, emote, jawaban kuis, dan semua badge. "
            "Akun, akses kursus, foto, portfolio, dan riwayat login tetap ada. "
            "Tidak bisa dibatalkan.",
            confirm, confirm_text="Reset").wait_window()
        if done:
            self._render_tab()
            self.status.config(text=f"Progres {sid} ({student['name']}) sudah di-reset.",
                               fg=C.MUTED)

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
        if self.view != "students":   # ditambah dari menu Laporan Kerja: pindah ke menu Murid
            self._set_view("students")
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
        btn = RoundButton(parent, text=text, command=command, bg=C.CARD, fg=C.TEXT,
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
        self._update_pin_button()

    def _update_pin_button(self):
        from elearning import web_launcher as W
        st = lookup_student(self.current_id) if self.current_id else None
        if st is None or not any(s["key"] == "pinterest" for s in W.sites_for(st)):
            self.pin_btn.pack_forget()
            return
        lim = st.get("pinterest_limit")
        text = ("Chrome: tanpa batas (AI)" if W.is_ai_student(st) else
                "Chrome: bawaan" if lim is None else "Chrome: diblokir" if lim == 0
                else "Chrome: tanpa batas" if lim < 0 else f"Chrome: {lim} mnt")
        self.pin_btn.config(text=text)
        if not self.pin_btn.winfo_ismapped():
            self.pin_btn.pack(side="left", padx=(8, 0))

    def _pinterest_limit(self):
        from elearning import web_launcher as W
        from elearning.students import set_pinterest_limit
        from elearning.ui.dialogs import PinterestLimitDialog
        sid = self.current_id
        st = lookup_student(sid) if sid else None
        if st is None:
            return
        if W.is_ai_student(st):            # murid kursus AI: browsing tidak dibatasi
            W._message(self.winfo_toplevel(), "Batas Chrome",
                       f"{st['name']} ikut kursus AI: browsing Chrome tidak dibatasi.")
            return
        used = int(W.used_secs(sid, "pinterest") // 60)   # jendela waktu sekarang

        def submit(minutes):
            try:
                set_pinterest_limit(sid, minutes)
            except Exception as exc:
                C.log(f"Batas Pinterest {sid} gagal disimpan: {exc!r}")
                return "Gagal menyimpan. Pastikan folder data bisa ditulis."
            W._own.pop(sid, None)              # langsung berlaku (juga kalau sedang dibuka)
            self._update_pin_button()
            return None
        PinterestLimitDialog(self, st["name"], st.get("pinterest_limit"),
                             getattr(C, "PINTEREST_LIMIT_MIN", 10), used, submit)

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
        panel = RoundPanel(self.rows, padx=4, pady=2)
        panel.pack(fill="x", pady=4)
        row = panel.inner

        info = tk.Frame(row, bg=C.CARD, padx=16, pady=10)
        info.pack(side="left", fill="x", expand=True)
        title_row = tk.Frame(info, bg=C.CARD)
        title_row.pack(fill="x")
        dot = I.dot(course["color"], C.CARD, 10)     # titik warna kursus (gaya claude.ai)
        if dot is not None:
            d = tk.Label(title_row, image=dot, bg=C.CARD, bd=0)
            d.image = dot
            d.pack(side="left", padx=(0, 8))
        tk.Label(title_row, text=course["title"], bg=C.CARD, fg=C.TEXT,
                 font=(C.FONT, 12, "bold"), anchor="w").pack(side="left")
        tk.Label(info, text=course["desc"], bg=C.CARD, fg=C.MUTED,
                 font=(C.FONT, 9), anchor="w").pack(fill="x")

        state = tk.Label(row, bg=C.CARD, font=(C.FONT, 10), width=9)
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
                     f"{'dibuka' if new_value else 'dikunci'}.",
                fg=C.MUTED)
            return True

        sw = Switch(row, value=unlocked, command=on_change, bg=C.CARD)
        sw.pack(side="right", padx=(8, 18))
        state.pack(side="right")

    @staticmethod
    def _paint_state(label, unlocked):
        label.config(text="Terbuka" if unlocked else "Terkunci",
                     fg=C.TEXT if unlocked else C.MUTED)
