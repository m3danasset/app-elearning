"""Jendela utama: mengatur layar mana yang sedang tampil."""

import os
import sys
import tkinter as tk

from elearning import config, sessions, splash
from elearning.trial import is_trial
from elearning.ui.login_screen import LoginScreen
from elearning.ui.home_screen import HomeScreen
from elearning.ui.course_screen import CourseScreen
from elearning.ui.teacher_screen import TeacherScreen
from elearning.ui.admin_screen import AdminScreen
from elearning.ui.floating import BlenderFloat


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
        self._set_icon()
        self._center(1000, 640)

        self._screen = None
        self.blender_float = BlenderFloat(self)   # ikon mengambang saat Blender terbuka (murid)
        self.protocol("WM_DELETE_WINDOW", self._close)   # tutup jendela = murid keluar
        self.after(60_000, self._beat)
        self.show_login()

    def _set_icon(self):
        """Ikon jendela + ikon tombol taskbar (supaya bukan ikon bulu pena bawaan Tk).

        Tiga cara dipasang berurutan; hasil tiap cara dicatat di app.log
        (cari baris yang diawali "Ikon:"), jadi kalau masih salah penyebabnya terlihat.
        """
        path = config.ICON_PATH
        config.log(f"Ikon: file={path!r} ada={os.path.isfile(path)}")

        # 1) Cara bawaan Tk
        try:
            self.iconbitmap(path)
            config.log("Ikon: iconbitmap OK")
        except Exception as exc:
            config.log(f"Ikon: iconbitmap GAGAL: {exc!r}")

        # 2) Gambar PNG dari icon.ico (beberapa ukuran), tidak bergantung pada pembaca .ico milik Tk
        try:
            import base64
            import io
            from PIL import Image
            icons = []
            with Image.open(path) as ico:
                sizes = sorted(s for s in ico.info.get("sizes", []) if s[0] in (16, 32, 48, 64))
                for size in sizes:
                    buf = io.BytesIO()
                    ico.ico.getimage(size).convert("RGBA").save(buf, format="PNG")
                    icons.append(tk.PhotoImage(data=base64.b64encode(buf.getvalue())))
            if icons:
                self.iconphoto(True, *icons)
                self._icons = icons   # simpan referensi supaya ikon tidak hilang
            config.log(f"Ikon: iconphoto OK ({len(icons)} ukuran)")
        except Exception as exc:
            config.log(f"Ikon: iconphoto GAGAL: {exc!r}")

        # 3) Windows: pasang langsung ke jendela (judul + taskbar), cara yang paling pasti
        if sys.platform == "win32":
            self.update_idletasks()
            self._win32_icon(path)
            self.after(300, lambda: self._win32_icon(path))   # ulang setelah jendela tampil

    def _win32_icon(self, path):
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            user32.GetParent.restype = wintypes.HWND
            user32.GetParent.argtypes = [wintypes.HWND]
            user32.LoadImageW.restype = wintypes.HANDLE
            user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                                          ctypes.c_int, ctypes.c_int, wintypes.UINT]
            user32.SendMessageW.restype = wintypes.LPARAM
            user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                            wintypes.LPARAM]
            hwnd = user32.GetParent(self.winfo_id()) or self.winfo_id()
            handles = []
            for kind, cx, cy in ((1, 11, 12), (0, 49, 50)):   # 1 = ikon besar, 0 = ikon kecil
                w, h = user32.GetSystemMetrics(cx), user32.GetSystemMetrics(cy)
                hicon = user32.LoadImageW(None, path, 1, w, h, 0x10)   # IMAGE_ICON, LR_LOADFROMFILE
                if not hicon:
                    raise OSError(f"LoadImage gagal (ukuran {w}x{h}, error {ctypes.GetLastError()})")
                handles.append(hicon)
                user32.SendMessageW(hwnd, 0x0080, kind, hicon)   # WM_SETICON
            self._hicons = handles
            config.log("Ikon: WM_SETICON OK")
        except Exception as exc:
            config.log(f"Ikon: WM_SETICON GAGAL: {exc!r}")

    # --- catatan masuk / keluar murid ------------------------------------------
    def _beat(self):
        sessions.heartbeat()
        self.after(60_000, self._beat)

    def _close(self):
        self.blender_float.stop()
        sessions.end()
        self.destroy()

    def login_student(self, student):
        if not is_trial(student):   # akun trial dipakai bersama, tidak dicatat
            sessions.start(student["id"])
        self.blender_float.start()   # ikon mengambang saat Blender terbuka (semua murid)
        self.show_home(student)

    def login_teacher(self, teacher):
        sessions.start(teacher["id"])   # aktivitas guru dicatat supaya admin bisa memantau
        self.show_teacher(teacher)

    def login_admin(self, admin):
        self.show_admin(admin)          # login admin tidak dicatat

    def logout(self):
        self.blender_float.stop()
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
                               on_teacher=self.login_teacher,
                               on_admin=self.login_admin))

    def show_home(self, student):
        self._show(HomeScreen(
            self, student,
            on_open_course=lambda course: self.show_course(student, course),
            on_logout=self.logout))

    def show_teacher(self, teacher):
        self._show(TeacherScreen(self, teacher, on_logout=self.logout))

    def show_admin(self, admin):
        self._show(AdminScreen(self, admin, on_logout=self.logout))

    def show_course(self, student, course):
        self._show(CourseScreen(
            self, student, course,
            on_back=lambda: self.show_home(student),
            on_logout=self.logout,
            on_open_course=lambda c: self.show_course(student, c)))
