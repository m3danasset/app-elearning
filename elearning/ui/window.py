"""Jendela utama: mengatur layar mana yang sedang tampil."""

import sys
import tkinter as tk

from elearning import config, sessions, splash
from elearning.ui.login_screen import LoginScreen
from elearning.ui.home_screen import HomeScreen
from elearning.ui.course_screen import CourseScreen
from elearning.ui.teacher_screen import TeacherScreen


class App(tk.Tk):
    def __init__(self):
        # Supaya ikon muncul di taskbar Windows (bukan ikon Python)
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    config.APP_ID)
            except Exception:
                pass

        splash.close()  # splash ditutup tepat sebelum jendela utama dibuat
        super().__init__()
        self.title(config.APP_NAME)
        self.configure(bg=config.BG)
        self.minsize(860, 600)
        try:
            self.iconbitmap(config.ICON_PATH)
        except Exception:
            pass  # kalau ikon tidak ada, tetap jalan dengan ikon bawaan
        self._center(1000, 640)

        self._screen = None
        self.protocol("WM_DELETE_WINDOW", self._close)   # tutup jendela = murid keluar
        self.after(60_000, self._beat)
        self.show_login()

    # --- catatan masuk / keluar murid ------------------------------------------
    def _beat(self):
        sessions.heartbeat()
        self.after(60_000, self._beat)

    def _close(self):
        sessions.end()
        self.destroy()

    def login_student(self, student):
        sessions.start(student["id"])
        self.show_home(student)

    def logout(self):
        sessions.end()
        self.show_login()

    def _center(self, w, h):
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _show(self, screen):
        if self._screen is not None:
            self._screen.destroy()
        self._screen = screen
        screen.pack(fill="both", expand=True)

    def show_login(self):
        self._show(LoginScreen(self, on_success=self.login_student,
                               on_teacher=self.show_teacher))

    def show_home(self, student):
        self._show(HomeScreen(
            self, student,
            on_open_course=lambda course: self.show_course(student, course),
            on_logout=self.logout))

    def show_teacher(self, teacher):
        self._show(TeacherScreen(self, teacher, on_logout=self.logout))

    def show_course(self, student, course):
        self._show(CourseScreen(
            self, student, course,
            on_back=lambda: self.show_home(student),
            on_logout=self.logout,
            on_open_course=lambda c: self.show_course(student, c)))
