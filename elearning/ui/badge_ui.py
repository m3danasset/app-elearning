"""Tampilan badge (PER KURSUS): papan badge (halaman Badges di layar kursus murid & tab guru),
notifikasi kecil, dan pelacak.

BadgeBoard   : kartu badge satu kursus per kategori, jumlah kolom mengikuti lebar (disusun
               ulang setelah ukuran stabil, tanpa membuat ulang kartu -> tidak berkedip).
               Guru: pilihan kursus di atas papan. Teks murid English (lihat i18n.py).
BadgeToast   : notifikasi kecil di pojok kiri-bawah, DI ATAS SIDEBAR (tidak menutupi video),
               masuk-keluar dengan geser berbasis waktu, maks. 30 fps (config.UI_FRAME_MS).
BadgeTracker : dipasang di App. Menghitung badge dari data di thread terpisah, memberi badge
               easter egg, dan menahan notifikasi selama video layar penuh / Blender dipakai /
               aplikasi tidak di depan; notifikasi tampil begitu murid kembali.
"""

import threading
import time
import tkinter as tk

from elearning import achievements as A
from elearning import config as C
from elearning import progress
from elearning.courses import COURSES
from elearning.i18n import L, is_en
from elearning.ui import badge_art as BA
from elearning.ui import ui_icons as I

MONTHS = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")
MONTHS_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
COURSE_TITLE = {c["id"]: c["title"] for c in COURSES}


def _date(text):
    """'2026-10-17 09:30:00' -> '17 Okt 2026' (English: '17 Oct 2026')."""
    try:
        y, m, d = text[:10].split("-")
        return f"{int(d)} {(MONTHS_EN if is_en() else MONTHS)[int(m) - 1]} {y}"
    except Exception:
        return ""


def bname(badge):
    return badge["name_en"] if is_en() else badge["name"]


def bdesc(badge):
    return badge["desc_en"] if is_en() else badge["desc"]


def badge_photo(badge, size, bg, state):
    ph = BA.photo(badge["icon"], size, badge["color"], bg, state)
    if ph is None:   # tanpa numpy: titik berwarna (tetap halus)
        ph = I.dot(badge["color"] if state == "on" else C.LOCKED, bg, size)
    return ph


# =============================================================================================
# Papan badge
# =============================================================================================
class _Card(tk.Canvas):
    W, H = 236, 88
    ICON = 48

    def __init__(self, master, badge, when, bg, action=None):
        super().__init__(master, width=self.W, height=self.H, bg=bg, highlightthickness=0, bd=0)
        on = bool(when)
        secret = badge["secret"] and not on
        self._card = I.pill(self.W, self.H, C.CARD, bg, r=12,
                            border=_mix_border(badge["color"]) if on else None)
        if self._card is not None:
            self.create_image(0, 0, image=self._card, anchor="nw")
        state = "on" if on else ("secret" if secret else "off")
        self._icon = badge_photo(badge, self.ICON, C.CARD, state)
        if self._icon is not None:
            self.create_image(14, (self.H - self.ICON) // 2, image=self._icon, anchor="nw")
        x = 14 + self.ICON + 12
        name = L("Rahasia", "Secret") if secret else bname(badge)
        desc = L("Temukan sendiri.", "Find it yourself.") if secret else bdesc(badge)
        self.create_text(x, 15, text=name, anchor="nw", fill=C.TEXT if on else C.MUTED,
                         font=(C.FONT, 10, "bold"), width=self.W - x - 10)
        self.create_text(x, 35, text=desc, anchor="nw", fill=C.MUTED if on else C.LOCKED,
                         font=(C.FONT, 8), width=self.W - x - 10)
        if on:
            self.create_text(x, self.H - 12, text=_date(when), anchor="sw",
                             fill=badge["color"], font=(C.FONT, 8, "bold"))
        if action is not None:          # tautan kecil (guru): beri / cabut badge
            label, fn = action
            t = self.create_text(self.W - 12, self.H - 12, text=label, anchor="se",
                                 fill=C.ACCENT, font=(C.FONT, 8, "bold"))
            self.tag_bind(t, "<Button-1>", lambda e: fn())
            self.tag_bind(t, "<Enter>", lambda e: self.configure(cursor="hand2"))
            self.tag_bind(t, "<Leave>", lambda e: self.configure(cursor=""))


def _mix_border(color):
    return BA._mix(C.CARD, color, 0.45)


class BadgeBoard(tk.Frame):
    """Badge satu murid di SATU kursus. teacher=True: pilihan kursus di atas papan, dan kartu
    "Masuk Galeri" punya tautan beri/cabut."""

    GAP = 10

    def __init__(self, master, student, course_id=None, bg=C.BG, teacher=False,
                 on_change=None):
        super().__init__(master, bg=bg)
        self.student, self.bg, self.teacher, self.on_change = student, bg, teacher, on_change
        self.course_id = course_id or self._first_course()
        self._cols = 0
        self._job = None
        self._grids = []        # (frame grid, [kartu])
        self._build()
        self.bind("<Configure>", self._on_configure)

    def _student_courses(self):
        from elearning.courses import courses_for
        allowed = set(self.student.get("courses", ()))
        return [c for c in courses_for(self.student.get("program", "adult"))
                if c["id"] in allowed]

    def _first_course(self):
        cs = self._student_courses()
        return cs[0]["id"] if cs else None

    def _build(self):
        for w in self.winfo_children():
            w.destroy()
        self._grids = []
        self._cols = 0
        if self.teacher:                 # guru: pilih kursus yang badge-nya dilihat
            cs = self._student_courses()
            if not cs:
                tk.Label(self, text="Murid ini belum punya kursus yang terbuka.", bg=self.bg,
                         fg=C.MUTED, font=(C.FONT, 10), anchor="w").pack(fill="x")
                return
            from elearning.ui.controls import RoundSelect
            titles = {c["title"]: c["id"] for c in cs}
            var = tk.StringVar(value=COURSE_TITLE.get(self.course_id, cs[0]["title"]))
            pick = tk.Frame(self, bg=self.bg)
            pick.pack(fill="x", pady=(0, 10))
            tk.Label(pick, text="Kursus", bg=self.bg, fg=C.MUTED, font=(C.FONT, 10)).pack(
                side="left", padx=(0, 8))
            RoundSelect(pick, var, *titles, bg=C.CARD,
                        command=lambda t: self._set_course(titles[t])).pack(side="left")
        got = A.earned(self.student["id"], self.course_id) if self.course_id else {}
        n = len(got)

        top = tk.Frame(self, bg=self.bg)
        top.pack(fill="x", pady=(0, 6))
        tk.Label(top, text=L(f"{n} dari {A.TOTAL} badge", f"{n} of {A.TOTAL} badges"),
                 bg=self.bg, fg=C.TEXT, font=(C.FONT, 12, "bold"), anchor="w").pack(side="left")
        self._bar = tk.Canvas(top, height=8, width=160, bg=self.bg, highlightthickness=0, bd=0)
        self._bar.pack(side="left", padx=(14, 0), pady=(3, 0))
        self._bar_frac = n / float(A.TOTAL)
        self._draw_bar()

        for key, label, color in A.CATEGORIES:
            label = A.CAT_EN[key] if is_en() else label
            items = [b for b in A.BADGES if b["cat"] == key]
            have = sum(1 for b in items if b["id"] in got)
            head = tk.Frame(self, bg=self.bg)
            head.pack(fill="x", pady=(16, 8))
            dot = I.dot(color, self.bg, 10)
            if dot is not None:
                d = tk.Label(head, image=dot, bg=self.bg, bd=0)
                d.image = dot
                d.pack(side="left", padx=(0, 8))
            tk.Label(head, text=label, bg=self.bg, fg=C.TEXT, font=(C.FONT, 11, "bold"),
                     anchor="w").pack(side="left")
            tk.Label(head, text=f"{have}/{len(items)}", bg=self.bg, fg=C.MUTED,
                     font=(C.FONT, 9), anchor="w").pack(side="left", padx=(8, 0))
            grid = tk.Frame(self, bg=self.bg)
            grid.pack(fill="x")
            cards = [_Card(grid, b, got.get(b["id"]), self.bg, self._action(b, got))
                     for b in items]
            self._grids.append((grid, cards))
        self._relayout()

    def _draw_bar(self):
        cv = self._bar
        cv.delete("all")
        w, h = 160, 8
        self._track = I.pill(w, h, C.BORDER, self.bg, r=4)
        if self._track is not None:
            cv.create_image(0, 0, image=self._track, anchor="nw")
        fw = int(w * self._bar_frac)
        if fw >= h:
            self._fill = I.pill(fw, h, C.ON, C.BORDER, r=4)
            if self._fill is not None:
                cv.create_image(0, 0, image=self._fill, anchor="nw")

    def _action(self, badge, got):
        if not (self.teacher and badge["teacher"]):
            return None
        sid = self.student["id"]
        if badge["id"] in got:
            return ("Cabut", lambda: self._set_teacher_badge(badge["id"], False))
        return ("Beri badge", lambda: self._set_teacher_badge(badge["id"], True))

    def _set_course(self, cid):
        self.course_id = cid
        self._build()

    def _set_teacher_badge(self, bid, give):
        sid = self.student["id"]
        if give:
            A.award(sid, self.course_id, bid, by="guru")
        else:
            A.revoke(sid, self.course_id, bid)
        self._build()
        if self.on_change is not None:
            self.on_change()

    # --- jumlah kolom mengikuti lebar (disusun ulang setelah ukuran stabil) ------------------
    def _on_configure(self, e):
        if e.widget is not self:
            return
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(60, self._relayout)

    def _relayout(self):
        self._job = None
        width = self.winfo_width()
        if width < 50:
            width = self.master.winfo_width()
        cols = max(1, (max(width, _Card.W) + self.GAP) // (_Card.W + self.GAP))
        if cols == self._cols:
            return
        self._cols = cols
        for grid, cards in self._grids:
            for i, card in enumerate(cards):
                card.grid(row=i // cols, column=i % cols, padx=(0, self.GAP), pady=(0, self.GAP),
                          sticky="nw")


# =============================================================================================
# Notifikasi
# =============================================================================================
class BadgeToast(tk.Canvas):
    W, H = 248, 64
    ICON = 40
    HOLD_MS = 4500
    SLIDE_MS = 240

    def __init__(self, app, badge, course_title="", on_click=None, on_done=None):
        super().__init__(app, width=self.W, height=self.H, bg=C.SIDEBAR, highlightthickness=0,
                         bd=0, cursor="hand2")
        self.app, self.badge = app, badge
        self.on_click, self.on_done = on_click, on_done
        self._card = I.pill(self.W, self.H, C.CARD, C.SIDEBAR, r=12,
                            border=_mix_border(badge["color"]))
        if self._card is not None:
            self.create_image(0, 0, image=self._card, anchor="nw")
        self._icon = badge_photo(badge, self.ICON, C.CARD, "on")
        if self._icon is not None:
            self.create_image(12, (self.H - self.ICON) // 2, image=self._icon, anchor="nw")
        x = 12 + self.ICON + 12
        head = L("Badge baru", "New badge")
        if course_title:
            head += f"  ·  {course_title}"
        self.create_text(x, 15, text=head, anchor="nw", fill=badge["color"],
                         font=(C.FONT, 8, "bold"), width=self.W - x - 10)
        self.create_text(x, 31, text=bname(badge), anchor="nw", fill=C.TEXT,
                         font=(C.FONT, 11, "bold"), width=self.W - x - 10)
        self.bind("<Button-1>", lambda e: self._clicked())
        self._job = None
        self._closing = False

    def raise_widget(self):
        """Naikkan WIDGET ini ke atas layar (Canvas.lift() = menaikkan item gambar)."""
        tk.Misc.tkraise(self)

    # posisi: kiri-bawah, di atas Buka Blender + profil di dasar sidebar
    def _target(self):
        h = self.app.winfo_height()
        y = h - 128 - self.H
        # daftar Courses menempel di bawah sidebar: notifikasi tampil di atasnya
        dock = getattr(getattr(getattr(self.app, "_screen", None), "sb", None), "_dock_box", None)
        try:
            if dock is not None and dock.winfo_exists() and dock.winfo_children():
                y = dock.winfo_rooty() - self.app.winfo_rooty() - self.H - 8
        except tk.TclError:
            pass
        return 10, max(10, y)

    def show(self):
        x1, y = self._target()
        self._slide(-self.W - 4, x1, self.SLIDE_MS, then=self._hold)

    def _hold(self):
        self._job = self.after(self.HOLD_MS, self.close)

    def close(self):
        if self._closing:
            return
        self._closing = True
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        try:
            x0 = int(self.place_info().get("x", 10))
        except Exception:
            x0 = 10
        self._slide(x0, -self.W - 4, 200, then=self._finish)

    def hide_now(self):
        """Keadaan berubah (layar penuh, Blender, ganti layar): langsung hilang tanpa animasi."""
        self._closing = True
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        self._finish()

    def _finish(self):
        try:
            self.destroy()
        except tk.TclError:
            pass
        if self.on_done is not None:
            self.on_done()

    def _clicked(self):
        if self.on_click is not None:
            self.on_click()
        self.close()

    def _slide(self, x0, x1, ms, then):
        """Geser berbasis waktu (ease-out), frame tetap maks. 30 fps. Mode ringan: langsung."""
        if C.lite():
            _x, y = self._target()
            self.place(x=int(x1), y=y)
            self.raise_widget()
            if then is not None:
                self.after(1, then)
            return
        t0 = time.perf_counter()

        def step():
            self._job = None
            if not self.winfo_exists():
                return
            t = min(1.0, (time.perf_counter() - t0) * 1000.0 / ms)
            e = 1 - (1 - t) ** 3
            _x, y = self._target()
            self.place(x=int(x0 + (x1 - x0) * e), y=y)
            self.raise_widget()
            if t < 1.0:
                self._job = self.after(C.UI_FRAME_MS, step)
            elif then is not None:
                then()
        step()


# =============================================================================================
# Pelacak (satu per aplikasi)
# =============================================================================================
class BadgeTracker:
    POLL_MS = 500
    EVAL_S = 20              # badge dari data dihitung ulang sesering ini (di thread)
    SABAR_S = 90             # easter egg "Si Sabar": diam di halaman kursus selama ini
    LOGO_CLICKS, LOGO_WINDOW = 5, 3.0

    def __init__(self, app):
        self.app = app
        self.student = None
        self._queue = []          # id badge menunggu notifikasi
        self._results = []        # hasil thread (diambil thread utama)
        self._rlock = threading.Lock()
        self._wake = threading.Event()
        self._stop = None
        self._job = None
        self._toast = None
        self._ticks = 0
        self._idle = (None, 0.0)
        self._logo = []
        self.course_id = None     # kursus yang sedang / terakhir dibuka (badge kejadian)

    # --- dipanggil App --------------------------------------------------------------------
    def start(self, student):
        self.stop()
        if not A._eligible(student):
            return
        self.student = student
        self.course_id = None
        try:
            self._enqueue(A.unshown(student["id"]))
        except Exception as exc:
            C.log(f"Badge saat login: {exc!r}")
        stop = self._stop = threading.Event()
        threading.Thread(target=self._work, args=(student, stop), daemon=True).start()
        self._idle = (None, time.time())
        self._job = self.app.after(self.POLL_MS, self._poll)

    def stop(self):
        if self._stop is not None:
            self._stop.set()
            self._wake.set()
            self._stop = None
        if self._job is not None:
            try:
                self.app.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        if self._toast is not None:
            self._toast.hide_now()
            self._toast = None
        self.student = None
        self.course_id = None
        self._queue = []
        with self._rlock:
            self._results = []

    def course_opened(self, course_id):
        """Layar kursus dibuka: kursus ini jadi tujuan badge kejadian; Halo + hari belajar."""
        if self.student is None:
            return
        self.course_id = course_id
        try:
            self._enqueue(A.on_open_course(self.student, course_id))
        except Exception as exc:
            C.log(f"Badge buka kursus: {exc!r}")
        self.poke()

    def event(self, bid):
        """Kejadian dari UI (buka Blender, easter egg) -> badge di kursus yang sedang /
        terakhir dibuka. Diabaikan untuk guru/admin dan kalau belum ada kursus dibuka."""
        if self.student is None or not self.course_id:
            return
        try:
            self._enqueue(A.award(self.student["id"], self.course_id, bid))
        except Exception as exc:
            C.log(f"Badge {bid}: {exc!r}")

    def poke(self):
        """Ada data baru (unggah karya, video selesai): hitung ulang sekarang."""
        self._wake.set()

    def logo_clicked(self):
        now = time.time()
        self._logo = [t for t in self._logo if now - t <= self.LOGO_WINDOW] + [now]
        if len(self._logo) >= self.LOGO_CLICKS:
            self._logo = []
            self.event("pemburu_logo")

    def search_typed(self, text):
        if text.strip().lower() == str(getattr(C, "SECRET_CODE", "")).lower() != "":
            self.event("kode_rahasia")

    # --- thread: badge dari data -------------------------------------------------------------
    def _work(self, student, stop):
        while not stop.is_set():
            try:
                new = A.evaluate(student)
            except Exception as exc:
                C.log(f"Badge evaluate: {exc!r}")
                new = []
            if new and not stop.is_set():
                with self._rlock:
                    self._results.extend(new)
            self._wake.wait(self.EVAL_S)
            self._wake.clear()

    # --- thread utama ----------------------------------------------------------------------
    def _enqueue(self, ids):
        for i in ids:
            if i not in self._queue:
                self._queue.append(i)
        if ids:      # angka "Badge 5/20" di sidebar ikut diperbarui
            sb = getattr(getattr(self.app, "_screen", None), "sb", None)
            if sb is not None:
                try:
                    sb.refresh()
                except Exception:
                    pass

    def _poll(self):
        self._job = None
        if self.student is None:
            return
        try:
            with self._rlock:
                res, self._results = self._results, []
            self._enqueue(res)
            self._ticks += 1
            if self._ticks % 4 == 0:      # tiap 2 detik
                self._check_practice()
                self._check_patience()
            self._update_toast()
        except Exception as exc:
            C.log(f"Pelacak badge: {exc!r}")
        if self.student is not None:
            self._job = self.app.after(self.POLL_MS, self._poll)

    def _student_screen(self):
        from elearning.ui.course_screen import CourseScreen
        from elearning.ui.home_screen import HomeScreen
        return isinstance(getattr(self.app, "_screen", None), (HomeScreen, CourseScreen))

    def _can_show(self):
        """Notifikasi hanya saat murid melihat aplikasi biasa: bukan video layar penuh, bukan
        saat Blender dipakai (mode mengambang), bukan saat popup konfirmasi terbuka."""
        app = self.app
        try:
            if not self._student_screen() or app.attributes("-fullscreen"):
                return False
            if getattr(app, "_confirming", False):
                return False
            bf = getattr(app, "blender_float", None)
            if bf is not None and bf.icon is not None:
                return False
            if app.state() in ("iconic", "withdrawn"):
                return False
            from elearning import blender_launcher as BL
            fg = BL.is_foreground(app.winfo_id())
            return fg is None or bool(fg)
        except Exception:
            return False

    def _update_toast(self):
        ok = self._can_show()
        if self._toast is not None:
            if not ok:                   # keadaan berubah: tahan, tampilkan lagi nanti
                self._queue.insert(0, self._toast.key)
                t, self._toast = self._toast, None
                t.on_done = None
                t.hide_now()
            return
        if not ok or not self._queue:
            return
        cid, bid = self._queue.pop(0)
        badge = A.BY_ID.get(bid)
        if badge is None:
            return
        sid = self.student["id"]

        def done():
            self._toast = None

        def open_page():
            show = getattr(self.app, "show_badges", None)
            if show is not None and self.student is not None:
                self.app.after(10, lambda: show(self.student, cid))

        self._toast = BadgeToast(self.app, badge, COURSE_TITLE.get(cid, ""), on_click=open_page,
                                 on_done=done)
        self._toast.key = (cid, bid)
        self._toast.show()
        A.mark_shown(sid, cid, bid)

    def _check_practice(self):
        """Belajar Sambil Praktik: video pelajaran berjalan saat Blender terbuka
        (di mini player mode mengambang, atau di aplikasi)."""
        if not self.course_id or "belajar_praktik" in A.earned(self.student["id"],
                                                               self.course_id):
            return
        bf = getattr(self.app, "blender_float", None)
        mini = getattr(bf, "mini", None) if bf is not None else None
        playing_mini = bf is not None and bf.icon is not None and mini is not None \
            and getattr(mini, "playing", False)
        playing_app = time.time() - progress.last_play < 3
        if playing_mini:
            self.event("belajar_praktik")
        elif playing_app:
            from elearning import blender_launcher as BL
            if BL.window_exists():
                self.event("belajar_praktik")

    def _check_patience(self):
        """Si Sabar: di halaman kursus (video tidak berjalan), aplikasi di depan, mouse tidak
        bergerak selama SABAR_S detik."""
        from elearning.ui.course_screen import CourseScreen
        scr = getattr(self.app, "_screen", None)
        now = time.time()
        try:
            pos = self.app.winfo_pointerxy()
        except tk.TclError:
            return
        if not isinstance(scr, CourseScreen) or time.time() - progress.last_play < 3 \
                or not self._can_show():
            self._idle = (None, now)
            return
        last, since = self._idle
        if pos != last:
            self._idle = (pos, now)
        elif now - since >= self.SABAR_S:
            self._idle = (pos, now)
            self.event("si_sabar")
