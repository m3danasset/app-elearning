"""Mini player mengambang: pemutar video kecil di SEBELAH ikon aplikasi saat murid sedang di Blender.

- Muncul hanya saat mode mengambang aktif (murid menekan tombol Blender di sidebar), tepat di
  sebelah kanan ikon aplikasi, dengan sisi bawahnya sejajar ikon. Kalau di sisi kanan tidak muat
  (ikon dekat tepi kanan jendela Blender), mini player pindah ke sisi kiri ikon.
- Melanjutkan pelajaran yang sedang dibuka di aplikasi, dari posisi terakhirnya.
- Bisa DI-RESIZE: tarik pegangan di pojok kanan-atas. Rasio selalu 16:9; ukurannya diingat.
- Tidak bisa digeser sendiri: hanya ikon yang digeser, mini player selalu mengikuti di sebelahnya.
- Tombol putar/jeda: overlay di tengah video, hanya tampil saat kursor di atas mini player
  (klik video juga memutar/menjeda). Bar kontrol: mundur 10 detik, garis posisi, waktu, bisukan.
  Tidak ada tombol sebelumnya/selanjutnya. Subtitle dan volume mengikuti pilihan murid.
- Klik kanan pada ikon aplikasi: mini player dijeda dan disembunyikan; klik kanan lagi untuk
  memunculkannya kembali (tetap dalam keadaan jeda).
- Klik ikon aplikasi = kembali ke aplikasi penuh, dan video di aplikasi melanjutkan dari posisi
  terakhir di mini player (diatur oleh floating.py).

Memakai mesin pemutar yang sama dengan pemutar utama (mpv bila ada, cadangan OpenCV).
"""

import sys
import time
import tkinter as tk

from elearning import blender_launcher as BL
from elearning import config as C
from elearning import mpv_support
from elearning.ui import aa_icons
from elearning.ui import lesson_view as LV
from elearning.ui.play_overlay import PlayOverlay, no_activate

MIN_W, MAX_W, DEFAULT_W = 320, 1000, 420   # lebar total jendela (px)
HEAD_H = 26      # tinggi bilah judul
BAR_H = 34       # tinggi bar kontrol
GAP = 8          # jarak antara ikon dan mini player
EDGE = 1         # tebal bingkai
TRACK = LV.TRACK
_KEY = "mini_width"
_KEY_FOLD = "mini_collapsed"
REWIND_S = 10
OV = 72          # ukuran tombol putar/jeda di tengah video
# pegangan resize: kursor diagonal Windows; di sistem lain pakai kursor sudut bawaan Tk
GRIP_CURSOR = "size_ne_sw" if sys.platform == "win32" else "top_right_corner"


def _fmt(seconds):
    return LV._fmt(seconds)


class MiniPlayer(tk.Toplevel):
    """Jendela kecil tanpa bingkai OS, selalu di atas, berisi video + kontrol."""

    def __init__(self, app, color=None, on_nav=None, on_drag=None, on_drag_end=None,
                 get_anchor=None, on_fullscreen=None):
        super().__init__(app)
        self.color = color or C.ACCENT
        self.on_fullscreen = on_fullscreen  # tombol layar penuh: kembali ke aplikasi dalam layar penuh
        self.on_nav = on_nav                # on_nav(+1 / -1): pelajaran sebelumnya / selanjutnya
        self.on_drag = on_drag              # on_drag(x_ikon, y_ikon): geser ikon + mini player
        self.on_drag_end = on_drag_end
        self.get_anchor = get_anchor        # () -> (x_ikon, y_ikon) saat ini
        self.closed = False                 # ditutup murid (tombol x)
        self.engine = None
        self.has_video = False
        self.playing = False
        self.pos = self.dur = 0.0
        self.can_prev = self.can_next = False
        self.photo = None
        self._path = None
        self._start = None                  # (posisi, putar?) yang diterapkan setelah video termuat
        self._load_t = 0.0
        self._n = 0
        self._job = None
        self._drag_seek = False
        self._click_t = 0.0                 # waktu klik-video terakhir (cegah putar/jeda dua kali)
        self._btn_prev = False
        self._anchor = None                 # (x_ikon, y_ikon, ukuran_ikon, batas_jendela_blender)
        self._last_geo = ""

        saved = BL.load_setting(_KEY)
        self.width = int(saved) if isinstance(saved, (int, float)) else DEFAULT_W
        self.width = max(MIN_W, min(MAX_W, self.width))
        self.collapsed = False          # lipat tidak dipakai lagi

        self.overrideredirect(True)
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass
        self.configure(bg=C.BORDER)
        self.withdraw()
        no_activate(self)       # tidak merebut fokus dari Blender, tidak muncul di Alt+Tab

        self.box = tk.Frame(self, bg=C.BG)
        # --- bilah judul (geser = pindahkan ikon + mini player) ---
        self.head = tk.Frame(self.box, bg=C.CARD)
        self.grip = tk.Canvas(self.head, width=22, height=HEAD_H, bg=C.CARD,
                              highlightthickness=0, bd=0, cursor=GRIP_CURSOR)
        self.grip.pack(side="right")
        self.title = tk.Label(self.head, text="", bg=C.CARD, fg=C.TEXT, anchor="w",
                              font=(C.FONT, 9, "bold"), padx=8)
        self.title.pack(side="left", fill="both", expand=True)
        self._draw_grip()
        self.grip.bind("<ButtonPress-1>", self._grip_press)
        self.grip.bind("<B1-Motion>", self._grip_motion)
        self.grip.bind("<ButtonRelease-1>", self._grip_release)

        # --- layar: kanvas (gambar cadangan / pesan) + permukaan untuk mpv ---
        self.stage = tk.Frame(self.box, bg="#000000")
        self.screen = tk.Canvas(self.stage, bg="#000000", highlightthickness=0, bd=0)
        self.screen.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.img_item = self.screen.create_image(0, 0, anchor="nw")
        self.screen.create_text(0, 0, text="", fill=C.MUTED, font=(C.FONT, 9),
                                justify="center", tags="msg")
        self.screen.bind("<Configure>", self._on_stage_resize)
        self.screen.bind("<Button-1>", lambda e: self._click_toggle())
        self.surface = tk.Frame(self.stage, bg="#000000")   # mpv menggambar di sini

        # --- bar kontrol ---
        self.bar = tk.Frame(self.box, bg=C.CARD)
        self.bar.pack_propagate(False)
        self.back_btn = self._ctl(28)
        self.fs_btn = self._ctl(28, side="right", padx=(0, 6))
        self.mute_btn = self._ctl(28, side="right", padx=(0, 0))
        self.time_lbl = tk.Label(self.bar, text="00:00 / 00:00", bg=C.CARD, fg=C.MUTED,
                                 font=(C.FONT, 8), width=11)
        self.time_lbl.pack(side="right", padx=(2, 2))
        self.seekbar = tk.Canvas(self.bar, height=24, bg=C.CARD, highlightthickness=0, bd=0,
                                 cursor="hand2")
        self.seekbar.pack(side="left", fill="x", expand=True, padx=4)
        # Tombol putar/jeda: segitiga / dua balok putih di tengah video, hanya saat kursor di atasnya
        self.ov = PlayOverlay(self, on_click=self._click_toggle, size=OV)
        self.back_btn.bind("<Button-1>", lambda e: self.rewind())
        self.mute_btn.bind("<Button-1>", lambda e: self._toggle_mute())
        self.fs_btn.bind("<Button-1>", lambda e: self._fullscreen())
        self.seekbar.bind("<Configure>", lambda e: self._draw_seek())
        self.seekbar.bind("<Button-1>", lambda e: self._seek_at(e.x, exact=False))
        self.seekbar.bind("<B1-Motion>", lambda e: self._seek_at(e.x, exact=False))
        self.seekbar.bind("<ButtonRelease-1>", self._seek_release)

        self._apply_size()
        self._refresh()
        self._tick()

    def _ctl(self, size, side="left", padx=(2, 0)):
        c = tk.Canvas(self.bar, width=size, height=size, bg=C.CARD, highlightthickness=0,
                      bd=0, cursor="hand2")
        c.pack(side=side, padx=padx)
        return c

    # =========================================================================
    # Ukuran & posisi
    # =========================================================================
    def _video_h(self, width=None):
        return int(((width or self.width) - 2 * EDGE) * 9 / 16)

    def _total_h(self, width=None):
        if self.collapsed:      # dilipat: hanya bilah judul + kontrol (video disembunyikan)
            return 2 * EDGE + HEAD_H + BAR_H
        return 2 * EDGE + HEAD_H + self._video_h(width) + BAR_H

    def _apply_size(self):
        w_in = self.width - 2 * EDGE
        vh = self._video_h()
        self.box.place(x=EDGE, y=EDGE, width=w_in, height=self._total_h() - 2 * EDGE)
        self.head.place(x=0, y=0, width=w_in, height=HEAD_H)
        if self.collapsed:
            self.stage.place_forget()
            self.bar.place(x=0, y=HEAD_H, width=w_in, height=BAR_H)
        else:
            self.stage.place(x=0, y=HEAD_H, width=w_in, height=vh)
            self.bar.place(x=0, y=HEAD_H + vh, width=w_in, height=BAR_H)
        if self.engine is not None and isinstance(self.engine, LV._MpvEngine):
            self.surface.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._apply_geometry()

    def _max_width(self):
        if self._anchor:
            bounds = self._anchor[3]
            if bounds:
                room = (bounds[2] - bounds[0]) - self._anchor[2] - 3 * GAP
                return max(MIN_W, min(MAX_W, int(room * 0.8)))
        return MAX_W

    def set_width(self, width, save=False):
        width = int(max(MIN_W, min(self._max_width(), width)))
        if width != self.width:
            self.width = width
            self._apply_size()
        if save:
            BL.save_setting(_KEY, self.width)

    def rewind(self):
        if not self.has_video or self.engine is None:
            return
        self.pos = max(0.0, self.pos - REWIND_S)
        self.engine.seek(self.pos, exact=True)
        self._update_time()
        self._draw_seek()

    def place_beside(self, ix, iy, tile, bounds=None):
        """ix, iy = pojok kiri-atas ikon; bounds = (kiri, atas, kanan, bawah) jendela Blender."""
        self._anchor = (ix, iy, tile, bounds)
        self._apply_geometry()

    def _apply_geometry(self):
        if not self._anchor:
            return
        ix, iy, tile, b = self._anchor
        w, h = self.width, self._total_h()
        x = ix + tile + GAP                  # di kanan ikon
        if b is not None and x + w > b[2]:   # tidak muat: pindah ke kiri ikon
            x = ix - GAP - w
            if x < b[0]:
                x = max(b[0], b[2] - w)
        y = iy + tile - h                    # sisi bawah sejajar dengan ikon
        if b is not None:
            y = max(b[1], min(y, b[3] - h))      # tetap di dalam layar (atas dan bawah)
        geo = f"{w}x{h}+{int(x)}+{int(y)}"
        if geo != self._last_geo:
            self._last_geo = geo
            # Mini player bergerak / berubah ukuran (ikon digeser, resize): tombol putar/jeda
            # (jendela terpisah) langsung disembunyikan supaya tidak tertinggal di luar mini
            # player; baru muncul lagi setelah mini player diam sebentar.
            self.ov.settle()
            self.geometry(geo)

    # =========================================================================
    # Tampil / sembunyi
    # =========================================================================
    def show(self):
        if self.closed:
            return
        if self.state() == "withdrawn":
            self.deiconify()
        self.attributes("-topmost", True)
        self.lift()
        if self.ov.shown:
            self.ov.lift()          # tombol putar/jeda tetap di atas mini player

    def hide(self):
        """Sembunyikan (ikon disembunyikan / aplikasi dibuka): video dijeda."""
        self._pause()
        self.ov.hide()
        if self.state() != "withdrawn":
            self.withdraw()

    def close(self):
        """Disembunyikan + dijeda (klik kanan pada ikon). Dibuka lagi dengan klik kanan berikutnya."""
        self.closed = True
        self.hide()

    def reopen(self):
        self.closed = False
        self.show()

    # =========================================================================
    # Memuat video
    # =========================================================================
    def open(self, path, subs=(), title="", start=0.0, play=False, can_prev=False,
             can_next=False):
        """Tampilkan jendela lalu muat video, lanjut dari posisi start (detik)."""
        self.show()
        self.update_idletasks()
        self.load(path, subs, title, start, play, can_prev, can_next)

    def load(self, path, subs=(), title="", start=0.0, play=False, can_prev=False,
             can_next=False):
        self.title.config(text=title)
        self.can_prev, self.can_next = can_prev, can_next
        if not self._ensure_engine():
            self.has_video = False
            self._message("Video tidak bisa diputar.")
            return
        e = self.engine
        self.playing = False
        self.pos = self.dur = 0.0
        self.screen.itemconfig(self.img_item, image="")
        self.photo = None
        e.stop()
        self._message("")
        self._path, self._subs = path, subs
        self._load_t = time.time()
        self._start = (max(0.0, float(start)), bool(play))
        try:
            if e.has_audio:
                e.load(path, subs)
            else:
                e.load(path, size=(self.screen.winfo_width(), self.screen.winfo_height()))
        except Exception as exc:
            C.log(f"Mini player: gagal memuat {path!r}: {exc!r}")
            self._fallback_to_cv("mpv gagal memuat video")
            return
        self.has_video = True
        self._refresh()

    def _ensure_engine(self):
        if self.engine is not None:
            return True
        if mpv_support.get() is not None:
            try:
                self.surface.place(relx=0, rely=0, relwidth=1, relheight=1)
                self.surface.update_idletasks()
                self.engine = LV._MpvEngine(self.surface.winfo_id())
                for name, value in (("focus-on-open", "no"),):
                    try:        # jendela video tidak boleh merebut fokus saat video dibuka
                        self.engine.mp.command("set", name, value)
                    except Exception as exc:
                        C.log(f"Mini player: mpv {name} tidak bisa diatur: {exc!r}")
            except Exception as exc:
                C.log(f"Mini player: mpv gagal dibuat, pakai OpenCV tanpa suara: {exc!r}")
                self.surface.place_forget()
                self.engine = None
        if isinstance(self.engine, LV._MpvEngine):
            # Video diperkecil banyak: pakai penskala yang lebih tajam supaya tidak buram / bergerigi
            for name, value in (("scale", "spline36"), ("cscale", "spline36"),
                                ("dscale", "mitchell"), ("correct-downscaling", "yes"),
                                ("sigmoid-upscaling", "yes")):
                try:
                    self.engine.mp.command("set", name, value)
                except Exception as exc:
                    C.log(f"Mini player: mpv {name} tidak bisa diatur: {exc!r}")
        if self.engine is None and LV.HAS_VIDEO:
            self.engine = LV._CvEngine()
        if self.engine is None:
            C.log(f"Mini player: tidak ada mesin pemutar: {LV.IMPORT_ERROR}")
            return False
        self._refresh()
        return True

    def _fallback_to_cv(self, why):
        path, start = self._path, self._start
        old = self.engine
        self.surface.place_forget()
        if old is not None:
            try:
                old.terminate()
            except Exception:
                pass
        self.engine = None
        self.has_video = False
        self.playing = False
        if not LV.HAS_VIDEO or not path:
            self._message("Video tidak bisa diputar (lihat app.log).")
            return
        C.log(f"Mini player: pindah ke OpenCV: {why}")
        self.engine = LV._CvEngine()
        self.engine.load(path, size=(self.screen.winfo_width(), self.screen.winfo_height()))
        self._start = start
        self.has_video = True
        self._refresh()

    def resume_state(self):
        """(posisi detik, sedang diputar?) untuk dilanjutkan di aplikasi."""
        if self._start is not None:          # belum sempat termuat: posisi awal yang diminta
            return self._start[0], False
        return (self.pos if self.has_video else None), self.playing

    # =========================================================================
    # Kontrol
    # =========================================================================
    def toggle(self):
        if not self.has_video or self.engine is None:
            return
        want = not self.playing
        self.engine.set_playing(want)
        self.playing = want
        self._refresh()

    def _pause(self):
        if self.playing and self.engine is not None:
            try:
                self.engine.set_playing(False)
            except Exception:
                pass
            self.playing = False
            self._refresh()

    def _nav(self, delta):
        if self.on_nav is None:
            return
        if (delta < 0 and not self.can_prev) or (delta > 0 and not self.can_next):
            return
        self.on_nav(delta)

    def _toggle_mute(self):
        e = self.engine
        if e is None or not e.has_audio:
            return
        e.set_volume(LV._PREF["volume"] or 80, not LV._PREF["mute"])
        self._draw_mute()

    def _seek_at(self, x, exact):
        if not self.has_video or self.dur <= 0:
            return
        self._drag_seek = True
        w = max(1, self.seekbar.winfo_width() - 16)
        frac = min(1.0, max(0.0, (x - 8) / w))
        self.pos = frac * self.dur
        self.engine.seek(self.pos, exact=exact)
        self._update_time()
        self._draw_seek()

    def _seek_release(self, event):
        if self._drag_seek:
            self._seek_at(event.x, exact=True)
            self._drag_seek = False

    # --- resize lewat pegangan pojok kanan-atas ---
    def _grip_press(self, e):
        self._gp = (e.x_root, e.y_root, self.width)

    def _grip_motion(self, e):
        gp = getattr(self, "_gp", None)
        if not gp:
            return
        dx, dy = e.x_root - gp[0], e.y_root - gp[1]
        by_x, by_y = dx, -dy * 16 / 9      # tarik ke kanan atau ke atas = membesar
        self.set_width(gp[2] + (by_x if abs(by_x) >= abs(by_y) else by_y))

    def _grip_release(self, e):
        if getattr(self, "_gp", None):
            self.set_width(self.width, save=True)
        self._gp = None

    # =========================================================================
    # Gambar
    # =========================================================================
    def _message(self, text):
        self.screen.itemconfig("msg", text=text)
        self._refresh()

    def _on_stage_resize(self, event):
        if self.engine is not None:
            self.engine.set_size(event.width, event.height)
        self.screen.coords("msg", event.width / 2, event.height / 2)
        self.screen.itemconfig("msg", width=max(80, event.width - 30))

    def _refresh(self):
        self._draw_play()
        self._draw_back()
        self._draw_mute()
        self._draw_fs()
        self._update_time()
        self._draw_seek()

    def _draw_grip(self):
        c = self.grip
        c.delete("all")
        ph = aa_icons.photo("mini-grip", lambda: aa_icons.render([(aa_icons.grip, C.MUTED)], 22, HEAD_H))
        if ph is not None:
            c.create_image(0, 0, image=ph, anchor="nw")
            return
        for d in (6, 11, 16):       # cadangan: garis biasa
            c.create_line(22 - d - 2, 6, 22 - 2, 6 + d, fill=C.MUTED, width=1)

    def _draw_back(self):
        c = self.back_btn
        c.delete("all")
        col = C.TEXT if self.has_video else C.LOCKED
        ph = aa_icons.photo(("mini-back", col), lambda: aa_icons.render([(aa_icons.rewind10, col)], 28, 28))
        if ph is not None:
            c.create_image(14, 14, image=ph)
        else:
            c.create_text(14, 14, text="-10", fill=col, font=(C.FONT, 8, "bold"))

    def _draw_play(self):
        self.ov.set_playing(self.playing)

    def _pointer_inside(self):
        if self.state() == "withdrawn":
            return False
        px, py = self.winfo_pointerxy()
        x, y = self.winfo_rootx(), self.winfo_rooty()
        return x <= px < x + self.winfo_width() and y <= py < y + self.winfo_height()

    def _update_overlay(self):
        """Tombol putar/jeda tampil hanya saat kursor di atas mini player (mpv menelan event
        mouse Tk, jadi posisi kursor diperiksa langsung)."""
        want = self.has_video and self._pointer_inside()
        cx = self.stage.winfo_rootx() + self.stage.winfo_width() // 2
        cy = self.stage.winfo_rooty() + self.stage.winfo_height() // 2
        self.ov.sync(want, cx, cy)

    def _click_toggle(self):
        now = time.time()
        if now - self._click_t < 0.35:      # satu klik bisa datang dari beberapa jalur
            return
        self._click_t = now
        self.toggle()

    def _pointer_in_stage(self):
        px, py = self.winfo_pointerxy()
        x, y = self.stage.winfo_rootx(), self.stage.winfo_rooty()
        return x <= px < x + self.stage.winfo_width() and y <= py < y + self.stage.winfo_height()

    def _poll_click(self):
        """Klik di mana pun pada video = putar/jeda (mpv tidak selalu meneruskan klik ke Tk)."""
        down = BL.left_button_down()
        if down is None:
            return
        pressed, self._btn_prev = down and not self._btn_prev, down
        if (not pressed or not self.has_video or self.state() == "withdrawn"
                or not self._pointer_in_stage()):
            return
        px, py = self.winfo_pointerxy()
        mine = BL.root_of(self.winfo_id())
        if mine and BL.root_at_point(px, py) == mine:
            self._click_toggle()

    def _fullscreen(self):
        if self.on_fullscreen is not None and self.has_video:
            self.on_fullscreen()

    def _draw_fs(self):
        c = self.fs_btn
        c.delete("all")
        col = C.TEXT if self.has_video else C.LOCKED
        x0, x1, y0, y1, k = 7, 21, 7, 21, 5
        pts = [[(x0, y0 + k), (x0, y0), (x0 + k, y0)], [(x1 - k, y0), (x1, y0), (x1, y0 + k)],
               [(x0, y1 - k), (x0, y1), (x0 + k, y1)], [(x1 - k, y1), (x1, y1), (x1, y1 - k)]]
        ph = aa_icons.photo(("mini-fs", col), lambda: aa_icons.render(
            [(aa_icons.polylines(pts, 1.0), col)], 28, 28))
        if ph is not None:
            c.create_image(14, 14, image=ph)
        else:
            for p in pts:
                c.create_line(*p[0], *p[1], *p[2], fill=col, width=2)

    def _draw_mute(self):
        c = self.mute_btn
        c.delete("all")
        muted = bool(LV._PREF["mute"] or LV._PREF["volume"] == 0)
        col = C.MUTED if muted else C.TEXT
        layers = [(aa_icons.speaker, col)] + ([(aa_icons.cross, C.ERROR)] if muted
                                              else [(aa_icons.waves, col)])
        ph = aa_icons.photo(("mini-mute", muted), lambda: aa_icons.render(layers, 28, 28))
        if ph is not None:
            c.create_image(14, 14, image=ph)
            return
        c.create_polygon(5, 11, 9, 11, 14, 7, 14, 21, 9, 17, 5, 17, fill=col, outline="")
        if muted:
            c.create_line(17, 11, 23, 17, fill=C.ERROR, width=2)
            c.create_line(23, 11, 17, 17, fill=C.ERROR, width=2)

    def _draw_seek(self):
        c = self.seekbar
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 20:
            return
        x0, x1, y = 8, w - 8, h // 2
        c.create_rectangle(x0, y - 2, x1, y + 2, fill=TRACK, outline="")
        if self.has_video and self.dur > 0:
            frac = min(1.0, max(0.0, self.pos / self.dur))
            x = x0 + (x1 - x0) * frac
            c.create_rectangle(x0, y - 2, x, y + 2, fill=self.color, outline="")
            ph = aa_icons.photo("mini-knob", lambda: aa_icons.render([(aa_icons.knob, C.TEXT)], 14, 14))
            if ph is not None:
                c.create_image(round(x), y, image=ph)
            else:
                c.create_oval(x - 5, y - 5, x + 5, y + 5, fill=C.TEXT, outline="")

    def _update_time(self):
        self.time_lbl.config(text=f"{_fmt(self.pos)} / {_fmt(self.dur)}")

    # =========================================================================
    # Pembaruan berkala
    # =========================================================================
    def _tick(self):
        e = self.engine
        try:
            self._update_overlay()
            self._poll_click()
            if e is not None and self.has_video and self.state_visible():
                self._n += 1
                if e.take_toggle():
                    self._click_toggle()
                take_key = getattr(e, "take_key", None)
                if take_key is not None:
                    take_key()          # tombol papan ketik (F / Esc) diabaikan di mini player
                if not e.has_audio or self._n % 3 == 0:
                    self._poll(e)
        except Exception as exc:
            try:
                alive = bool(self.winfo_exists())
            except tk.TclError:
                alive = False
            if not alive:
                return              # jendela sudah dihancurkan: hentikan pembaruan
            C.log(f"Mini player: {exc!r}")
        self._job = self.after(40, self._tick)

    def state_visible(self):
        return self.state() != "withdrawn"

    def _poll(self, e):
        st = e.poll()
        if st.image is not None:
            try:
                self.photo = LV.ImageTk.PhotoImage(st.image)   # simpan referensi
                self.screen.itemconfig(self.img_item, image=self.photo)
            except Exception as exc:
                C.log(f"Mini player: gagal menampilkan frame: {exc!r}")
        if e.has_audio and not e.loaded and time.time() - self._load_t > 6:
            self._load_t = float("inf")
            self._fallback_to_cv("mpv tidak bisa membuka video")
            return
        if st.error:
            C.log(f"Mini player: video gagal diputar: {st.error}")
            e.stop()
            self.has_video = False
            self.playing = False
            self._message("Video tidak bisa diputar.")
            return
        if self._start is not None and (not e.has_audio or e.loaded):
            pos, play = self._start      # video sudah termuat: lanjut dari posisi terakhir
            self._start = None
            if pos > 0.5:
                e.seek(pos, exact=True)
                self.pos = pos
            e.set_playing(play)
            self.playing = play
            self._refresh()
            return
        self.dur = st.dur
        if not self._drag_seek:
            self.pos = st.pos
        changed = st.playing != self.playing
        self.playing = st.playing
        if changed:
            self._refresh()
        else:
            self._update_time()
            self._draw_seek()

    def destroy(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        if self.engine is not None:
            try:
                self.engine.terminate()     # hentikan video dan suara
            except Exception:
                pass
            self.engine = None
        super().destroy()
