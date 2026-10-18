"""Jendela utama: mengatur layar mana yang sedang tampil."""

import os
import sys
import tkinter as tk

from elearning.i18n import L
from elearning import config, sessions, splash, web_launcher
from elearning.trial import is_trial
from elearning.ui.login_screen import LoginScreen
from elearning.ui.home_screen import HomeScreen
from elearning.ui.course_screen import CourseScreen
from elearning.ui.teacher_screen import TeacherScreen
from elearning.ui.admin_screen import AdminScreen
from elearning.ui.floating import BlenderFloat
from elearning.ui.badge_ui import BadgeTracker
from elearning.ui.controls import ResizeCurtain, dark_titlebar


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

        from elearning import app_settings
        app_settings.apply_theme()   # warna aksen pilihan (jendela Dev)
        from elearning import dev_values
        dev_values.apply_all()       # nilai pengaturan dari jendela Dev (Settings > Nilai)
        splash.close()  # splash ditutup tepat sebelum jendela utama dibuat
        super().__init__()
        self.title(config.APP_NAME)
        self.configure(bg=config.BG)
        self.minsize(860, 600)
        self._set_icon()
        dark_titlebar(self)   # bilah judul Windows ikut gelap (tema aplikasi)
        # Tirai sesaat saat jendela <-> layar penuh (seluruh jendela, semua layar):
        # tidak tampak kartu terpotong / blok hitam selama widget digambar ulang
        # (halaman video murid dikecualikan: pemutar punya animasi layar penuh sendiri)
        self.curtain = ResizeCurtain(
            self, bg=config.BG,
            skip=lambda: isinstance(self._screen, CourseScreen))
        # Lebih lebar dari sebelumnya karena ada sidebar kiri (tetap muat di layar kecil)
        self._center(min(1240, self.winfo_screenwidth() - 60),
                     min(760, self.winfo_screenheight() - 80))

        self._screen = None
        self._confirming = False
        self.blender_float = BlenderFloat(self)   # ikon mengambang saat Blender terbuka (murid)
        self.badges = BadgeTracker(self)          # badge murid + notifikasi (lihat badge_ui.py)
        self._student = None
        self.protocol("WM_DELETE_WINDOW", self._close)   # tutup jendela = murid keluar
        self.after(60_000, self._beat)
        from elearning.ui.dev_panel import install_shortcut
        install_shortcut(self)   # Ctrl kanan + Shift kanan + Backspace = jendela Dev
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
        """Tombol X: di layar login langsung tutup; setelah login minta konfirmasi dulu."""
        if isinstance(self._screen, LoginScreen):
            self._quit()
            return
        self._confirm(L("Tutup aplikasi?", "Close the app?"), L("Tutup", "Close"),
                      lambda: self._after_trial(self._quit))

    def _quit(self):
        web_launcher.close()   # jendela Pinterest murid ikut ditutup
        self.badges.stop()
        self.blender_float.stop()
        sessions.end()
        self.destroy()

    def _confirm(self, question, confirm_text, action):
        """Popup konfirmasi mini (gaya aplikasi). Hanya satu yang terbuka sekaligus."""
        if self._confirming:
            return
        from elearning.ui.search_palette import close_palette
        close_palette()      # mis. tombol X jendela saat palette terbuka: tidak bertumpuk
        from elearning.ui.dialogs import MiniConfirm
        self._confirming = True
        try:
            from elearning.ui.play_overlay import PlayOverlay
            PlayOverlay.hide_all()     # tombol putar/jeda (topmost) jangan di atas popup
            dlg = MiniConfirm(self, question, confirm_text=confirm_text)
            dlg.wait_window()
            ok = dlg.result
        finally:
            self._confirming = False
        if ok:
            action()

    def _after_login(self):
        """Setelah login jendela langsung dibuat penuh (maximize, tombol jendela tetap ada)."""
        try:
            if self.state() != "zoomed" and not self.attributes("-fullscreen"):
                self.state("zoomed")
        except tk.TclError:
            pass

    def login_student(self, student):
        from elearning import i18n
        i18n.set_role("trial" if is_trial(student) else "student")   # layar murid: English
        self._account_id = None if is_trial(student) else student["id"]
        self._survey_done = False             # survey trial: sekali per sesi trial
        if not is_trial(student):   # akun trial dipakai bersama, tidak dicatat
            sessions.start(student["id"])
        from elearning.app_settings import feature
        if feature("floating"):           # Dev: mode mengambang bisa dimatikan
            self.blender_float.start()   # ikon mengambang saat Blender terbuka (semua murid)
        self._student = student
        self.show_home(student)
        self._after_login()
        if feature("badges"):             # Dev: badge bisa dimatikan
            self.badges.start(student)   # badge (trial diabaikan); notifikasi setelah layar siap

    def login_teacher(self, teacher):
        from elearning import i18n
        i18n.set_role("teacher")
        self._account_id = teacher["id"]
        sessions.start(teacher["id"])   # aktivitas guru dicatat supaya admin bisa memantau
        self.show_teacher(teacher)
        self._after_login()

    def login_admin(self, admin):
        from elearning import i18n
        i18n.set_role("admin")
        self._account_id = admin["id"]
        self.show_admin(admin)          # login admin tidak dicatat
        self._after_login()

    def dev_login(self, kind, account):
        """Jendela Dev: masuk sebagai akun mana pun tanpa PIN (keluar dari akun sekarang dulu,
        tanpa konfirmasi)."""
        if account is None:
            return
        config.log(f"Dev login: {kind} {account.get('id', '')}")
        if self._screen is not None and not isinstance(self._screen, LoginScreen):
            self._logout()
        if kind == "admin":
            self.login_admin(account)
        elif kind == "teacher":
            self.login_teacher(account)
        else:
            self.login_student(account)

    def dev_account_deleted(self, uid):
        """Jendela Dev menghapus akun: kalau akun itu sedang dipakai -> keluar ke login (tanpa
        konfirmasi); kalau tidak, layar sekarang dibangun ulang supaya daftarnya ikut baru."""
        if getattr(self, "_account_id", None) == uid:
            self._logout()
        elif self._screen is not None and not isinstance(self._screen, LoginScreen):
            self.rebuild_screen()

    def dev_account_changed(self, kind, uid):
        """Jendela Dev mengubah nama / PIN guru atau admin: layar dibangun ulang (nama baru
        langsung tampil di sidebar, daftar guru di Panel Admin ikut baru)."""
        scr = self._screen
        if kind == "teacher" and isinstance(scr, TeacherScreen) and scr.teacher.get("id") == uid:
            from elearning import teachers
            scr.teacher = dict(scr.teacher, **(teachers.get_teacher(uid) or {}))
        if scr is not None and not isinstance(scr, LoginScreen):
            self.rebuild_screen()

    def rebuild_screen(self):
        """Bangun ulang layar yang sedang tampil di posisi yang sama (jendela Dev > Apply:
        warna aksen, fitur, tampilan login langsung terlihat)."""
        scr = self._screen
        try:
            if isinstance(scr, LoginScreen):
                self.show_login()
            elif isinstance(scr, CourseScreen):
                lesson = None
                if scr.view == "materi" and scr.lesson_items:
                    lesson = scr.lesson_items[scr.lesson_index].get("title")
                self.show_course(scr.student, scr.course, lesson=lesson, view=scr.view)
            elif isinstance(scr, HomeScreen):
                self.show_home(scr.student, view=scr.view)
            elif isinstance(scr, TeacherScreen):
                self.show_teacher(scr.teacher)
            elif isinstance(scr, AdminScreen):
                tab = scr.tab
                from elearning import admins
                self.show_admin({"id": scr.admin_id,
                                 "name": admins.get_name(scr.admin_id) or "Admin"})
                self._screen._set_tab(tab)
        except Exception as exc:
            config.log(f"Dev: layar tidak bisa dibangun ulang: {exc!r}")

    def apply_dev_settings(self):
        """Jendela Dev > Apply: terapkan semua pengaturan ke aplikasi yang sedang berjalan."""
        from elearning import app_settings
        from elearning.app_settings import feature
        from elearning.ui import carousel3d
        app_settings.apply_theme()          # warna aksen
        from elearning import dev_values
        dev_values.apply_all()              # nilai (jam jadwal, syarat sertifikat, ...)
        carousel3d.reconfigure()            # 60 fps on/off
        student = self._student
        if student is not None:             # murid sedang masuk: fitur latar ikut
            if feature("floating"):
                if not self.blender_float.active:
                    self.blender_float.start()
            else:
                self.blender_float.stop()
            if feature("badges"):
                if self.badges.student is None:
                    self.badges.start(student)
            else:
                self.badges.stop()
        self.rebuild_screen()

    def logout(self):
        self._confirm(L("Keluar dari akun?", "Log out?"), L("Keluar", "Log out"),
                      lambda: self._after_trial(self._logout))

    def _after_trial(self, then):
        """Akun trial selesai (keluar / tutup aplikasi): popup survey calon murid dulu, lalu
        then(). Survey sekali per sesi trial; bisa dimatikan di jendela Dev (fitur survey)."""
        from elearning.app_settings import feature
        st = self._student
        if not (st is not None and is_trial(st) and feature("survey")
                and not getattr(self, "_survey_done", False)):
            then()
            return
        self._survey_done = True
        try:
            from elearning.ui.play_overlay import PlayOverlay
            PlayOverlay.hide_all()
            from elearning.ui.signup_view import SurveyDialog
            SurveyDialog(self, on_done=lambda: self.after_idle(then))
        except Exception as exc:
            config.log(f"Survey trial tidak bisa dibuka: {exc!r}")
            then()

    def _logout(self):
        web_launcher.close()   # jendela Pinterest murid ikut ditutup
        self._account_id = None
        self.badges.stop()
        self._student = None
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
        toast = getattr(getattr(self, "badges", None), "_toast", None)
        if toast is not None and toast.winfo_exists():
            toast.raise_widget()    # notifikasi badge tetap di atas layar baru
        if self.curtain.cover.winfo_ismapped():
            self.curtain.cover.lift()

    def show_login(self):
        from elearning import i18n
        i18n.set_role("login")          # layar login tetap Bahasa Indonesia
        self._show(LoginScreen(self, on_success=self.login_student,
                               on_teacher=self.login_teacher,
                               on_admin=self.login_admin))

    def show_home(self, student, view="courses"):
        self._show(HomeScreen(
            self, student,
            on_open_course=lambda course: self.show_course(student, course),
            on_logout=self.logout, view=view))

    def show_badges(self, student, course_id=None):
        """Halaman Badges sebuah kursus (menu sidebar kursus / klik notifikasi badge).
        Badge berlaku per kursus, jadi halamannya ada di layar kursus."""
        from elearning.courses import COURSES
        scr = self._screen
        if isinstance(scr, CourseScreen) and (course_id is None
                                              or scr.course["id"] == course_id):
            scr._set_view("badges")
            return
        course = next((c for c in COURSES if c["id"] == course_id), None)
        if course is None:
            return
        self.show_course(student, course, view="badges")

    def show_teacher(self, teacher):
        self._show(TeacherScreen(self, teacher, on_logout=self.logout))

    def show_admin(self, admin):
        self._show(AdminScreen(self, admin, on_logout=self.logout))

    def show_course(self, student, course, lesson=None, view=None):
        try:   # "Terakhir dibuka" di search palette (Ctrl+K)
            from elearning import recents
            recents.add(student["id"], f"course:{course['id']}", persist=not is_trial(student))
        except Exception as exc:
            config.log(f"Riwayat cari: {exc!r}")
        self._show(CourseScreen(
            self, student, course,
            on_back=lambda: self.show_home(student),
            on_logout=self.logout,
            on_open_course=lambda c: self.show_course(student, c),
            on_badges=lambda: self.show_badges(student, course["id"]), lesson=lesson,
            view=view))
