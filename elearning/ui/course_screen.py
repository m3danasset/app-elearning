"""Layar satu kursus (murid & trial): sidebar kiri gaya claude.ai + area materi.

Sidebar: logo, kolom cari (menyaring pelajaran & kursus), menu Semua kursus / Materi /
Resource / Portfolio, daftar pelajaran, daftar kursus, Buka Blender, lalu profil murid
di paling bawah (klik -> Keluar).
"""

import tkinter as tk

from elearning import achievements
from elearning import config as C
from elearning import portfolio, progress
from elearning import lessons as lessons_mod
from elearning.courses import has_video, visible_for
from elearning.trial import is_trial
from elearning.ui.lesson_view import LessonsPanel
from elearning.ui.portfolio_view import PortfolioPanel
from elearning.ui.sidebar import (AppSidebar, PageHeader, SidebarLayout, blender_footer,
                                  course_items, student_subtitle)


class CourseScreen(SidebarLayout):
    def __init__(self, master, student, course, on_back, on_logout, on_open_course,
                 on_badges=None, lesson=None, view=None):
        super().__init__(master)
        self.student = student
        self.course = course
        self.on_back = on_back
        self.on_badges = on_badges
        self.on_logout = on_logout
        self.on_open_course = on_open_course
        self.trial = is_trial(student)
        # "materi", "resource", "portfolio", "assignment", "certificate", "badges"
        self.view = view if (view and not is_trial(student)) else "materi"
        # AI CHARACTER / AI INTERIOR tidak memakai video: halaman Materi dibiarkan kosong
        self.video = has_video(course)
        self.lesson_items = lessons_mod.lessons_for(course) if self.video else []
        self.lesson_index = 0
        if self.video and not self.trial:     # lanjut tonton: buka video terakhir di kursus ini
            try:
                last = progress.last_lesson(student["id"], course["id"])
                for i, it in enumerate(self.lesson_items):
                    if last and it["title"] == last and not it["sample"]:
                        self.lesson_index = i
                        break
            except Exception as exc:
                C.log(f"Lanjut tonton: {exc!r}")
        if self.video and lesson:             # dipilih dari search palette
            for i, it in enumerate(self.lesson_items):
                if it["title"] == lesson and not it["sample"]:
                    self.lesson_index = i
                    break
        self.panel = None      # LessonsPanel yang sedang tampil (view "materi")

        self.sb = AppSidebar(self, student, student_subtitle(student), on_logout,
                             self._populate,
                             placeholder="Search courses" if self.trial else "Search lessons")
        self.attach(self.sb)

        # --- Kanan: judul kursus + area materi -------------------------------
        self.header = PageHeader(self.content, course["title"])
        self.header.pack(fill="x")
        self.body = tk.Frame(self.content, bg=C.BG)
        self.body.pack(fill="both", expand=True)
        self._render_body()
        tracker = getattr(self.winfo_toplevel(), "badges", None)
        if tracker is not None and not self.trial:   # badge kejadian -> kursus ini
            tracker.course_opened(course["id"])

    def search_sources(self):
        """Ctrl+K: search palette (tanpa kolom cari di bawah, supaya pemutar video lega)."""
        from elearning.ui.search_sources import student_sources
        return student_sources(self, self.student)

    # --- sidebar -----------------------------------------------------------------
    def _populate(self, sb):
        sb.nav("All courses", "grid", self.on_back)
        sb.nav("Lessons", "play", lambda: self._set_view("materi"),
               active=self.view == "materi")
        # Resources: trial juga (semua kelas trial memakai SATU folder bersama, resources/trial)
        sb.nav("Resources", "folder", lambda: self._set_view("resource"),
               active=self.view == "resource")
        if not self.trial:   # calon murid: tanpa portfolio, badge, sertifikat & daftar pelajaran
            n = portfolio.count(self.student["id"], self.course["id"])
            sb.nav("Portfolio", "image", lambda: self._set_view("portfolio"),
                   active=self.view == "portfolio", right=str(n) if n else None)
            if self.video:     # AI CHARACTER / AI INTERIOR: tanpa assignment
                na = portfolio.count(self.student["id"], self.course["id"], portfolio.ASSIGNMENT)
                sb.nav("Assignment", "file", lambda: self._set_view("assignment"),
                       active=self.view == "assignment", right=str(na) if na else None)
            got, total = achievements.summary(self.student, self.course["id"])
            sb.nav("Badges", "award", lambda: self._set_view("badges"),
                   active=self.view == "badges", right=f"{got}/{total}")
            sb.nav("Certificate", "check", lambda: self._set_view("certificate"),
                   active=self.view == "certificate")

            if not self.video:     # kursus tanpa video: tanpa daftar pelajaran
                course_items(sb, visible_for(self.student),
                             set(self.student["courses"]), self.course["id"],
                             self.on_open_course)
                blender_footer(sb)
                return
            shown = [(i, it) for i, it in enumerate(self.lesson_items)
                     if sb.matches(it["label"], it.get("title"))]
            sb.section(f"Lessons  ·  {self.course['title']}", top=10,
                       right=str(len(shown)))
            for i, it in shown:
                sb.item(it["label"], lambda k=i: self._open_lesson(k), marquee=True,
                        active=self.view == "materi" and i == self.lesson_index)
            if not shown:
                sb.note(f"No lessons match “{sb.query.strip()}”.")

        allowed = set(self.student["courses"])
        course_items(sb, visible_for(self.student), allowed, self.course["id"],
                     self.on_open_course)
        blender_footer(sb)

    # --- isi kanan: materi / resource / portfolio ------------------------------------
    def _render_body(self):
        self.panel = None
        for w in self.body.winfo_children():
            w.destroy()
        course = self.course
        if self.view == "assignment":
            self.header.set_title(course["title"], "Assignment")
            PortfolioPanel(self.body, self.student, course, on_change=self._uploads_changed,
                           section=portfolio.ASSIGNMENT).pack(fill="both", expand=True)
            return
        if self.view == "portfolio":
            self.header.set_title(course["title"], "Portfolio")
            PortfolioPanel(self.body, self.student, course,
                           on_change=self._uploads_changed).pack(fill="both", expand=True)
            return
        if self.view == "badges":
            self.header.set_title(course["title"], "Badges")
            from elearning.ui.badge_ui import BadgeBoard
            from elearning.ui.widgets import ScrollFrame
            scroll = ScrollFrame(self.body, bg=C.BG)
            scroll.pack(fill="both", expand=True, padx=(28, 12), pady=(4, 12))
            BadgeBoard(scroll.inner, self.student, course["id"]).pack(fill="x", pady=(0, 12))
            return
        if self.view == "certificate":
            self.header.set_title(course["title"], "Certificate")
            from elearning.ui.certificate_view import CertificatePage
            CertificatePage(self.body, self.student, course).pack(fill="both", expand=True)
            return
        if self.view == "resource":
            self.header.set_title(course["title"], "Resources")
            if self.trial:     # trial: daftar file langsung, klik = buka (tanpa file browser)
                from elearning.ui.resource_list import ResourceList
                ResourceList(self.body, course).pack(fill="both", expand=True)
                return
            from elearning.ui.file_browser import ResourcePage
            ResourcePage(self.body, course).pack(fill="both", expand=True)
            return
        self.header.set_title(course["title"], "Lessons")
        if not self.video:         # AI CHARACTER / AI INTERIOR: halaman kosong
            return
        # Pemutar video untuk semua murid (termasuk trial)
        self.panel = LessonsPanel(self.body, course, self.lesson_items, self.lesson_index,
                                  on_select=self._on_lesson_changed,
                                  on_fullscreen=self._set_fullscreen,
                                  show_nav=not self.trial,
                                  student_id=None if self.trial else self.student["id"],
                                  program=self.student.get("program"))
        self.panel.pack(fill="both", expand=True)

    def _uploads_changed(self):
        """Karya diunggah / dihapus: angka di sidebar + badge Karya dihitung ulang."""
        self.sb.refresh()
        tracker = getattr(self.winfo_toplevel(), "badges", None)
        if tracker is not None:
            tracker.poke()

    def _set_fullscreen(self, want):
        """Layar penuh pemutar video: sembunyikan sidebar dan judul, jendela layar penuh."""
        top = self.winfo_toplevel()
        if want:
            self.hide_sidebar()
            self.header.pack_forget()
            try:
                top.attributes("-fullscreen", True)
            except Exception as exc:
                C.log(f"Layar penuh gagal: {exc!r}")
            return
        try:
            top.attributes("-fullscreen", False)
        except Exception:
            pass
        self.show_sidebar()
        if not self.header.winfo_manager():
            self.header.pack(fill="x", before=self.body)

    def destroy(self):
        try:
            self.winfo_toplevel().attributes("-fullscreen", False)   # jangan terjebak layar penuh
        except Exception:
            pass
        super().destroy()

    def _on_lesson_changed(self, index):
        """Pelajaran berganti (tombol Sebelumnya/Selanjutnya): sorotan di sidebar ikut pindah."""
        self.lesson_index = index
        self.sb.refresh()

    def _open_lesson(self, index):
        """Klik pelajaran di sidebar."""
        if self.view == "materi" and self.panel is not None:
            self.panel.select(index)    # memanggil _on_lesson_changed
            return
        self.lesson_index = index
        self.view = "materi"
        self._render_body()
        self.sb.refresh()

    def _set_view(self, view):
        if view == self.view:
            return
        self.view = view
        self._render_body()
        self.sb.refresh()
