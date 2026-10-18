"""Halaman Materi: pemutar video pelajaran (di dalam aplikasi) + daftar pelajaran.

Dua mesin pemutar:
  - mpv (libmpv, lihat mpv_support.py): video tampil DI DALAM jendela aplikasi, ada SUARA,
    pengatur volume, dan pilihan SUBTITLE (tombol CC). Dipakai kalau python-mpv dan
    libmpv-2.dll tersedia.
  - OpenCV (cadangan): tanpa suara dan tanpa subtitle. Dipakai kalau mpv tidak tersedia,
    supaya aplikasi tetap jalan; alasannya tampil di atas pemutar dan dicatat di app.log.

Kontrol: klik video / tombol putar = putar-jeda, klik/geser garis = pindah posisi,
ikon speaker = bisukan, geser garis kecil = volume, CC = pilih subtitle.
Layar video SELALU 16:9 dan terisi penuh (tanpa bar hitam kiri-kanan; video yang rasionya
berbeda dipotong tipis di tepinya). Pilihan pelajaran ada di sidebar (course_screen.py);
di bawah pemutar hanya ada tombol Sebelumnya / Selanjutnya.
Pemutar berhenti sendiri kalau jendela disembunyikan (mis. saat Blender dibuka).
Dipakai juga untuk akun trial.
"""

import math
import os
import threading
import time
import tkinter as tk
import traceback

# CATATAN: sengaja TIDAK memakai tkinter.filedialog / tkinter.messagebox. Modul itu tidak
# ikut terbungkus di dalam .exe, sehingga import-nya gagal dan aplikasi diam-diam jatuh
# kembali ke kode lama bawaan .exe (layar login lama + splash "Memuat aplikasi" menggantung).
# Dialog dipanggil lewat perintah Tk bawaan (tk_getOpenFile), seperti di teacher_screen.py.

from elearning import config as C
from elearning.ui.controls import RoundButton
from elearning import lessons, mpv_support, progress, quizzes
from elearning.ui.lesson_extras import EmoteBar, NoteBox, QuizPopup
from elearning.ui import ui_icons as I
from elearning import blender_launcher as BL
from elearning.ui import aa_icons as AA
from elearning.ui.play_overlay import PlayOverlay

try:
    import cv2
    import numpy as np
    from PIL import Image, ImageTk
    try:    # OpenCV default memakai SEMUA core: batasi supaya Blender tidak terganggu
        cv2.setNumThreads(C.WORKER_THREADS)
    except Exception:
        pass
    HAS_VIDEO = True
    IMPORT_ERROR = ""
except Exception as exc:   # opencv / pillow belum terpasang
    HAS_VIDEO = False
    IMPORT_ERROR = repr(exc)

MAX_FPS = 30
SUB_LANGS = ("Indonesia", "English")   # pilihan menu CC (urutan tampil)
BAR_H = 48      # tinggi bar kontrol
FOOT_H = 64     # tinggi baris tombol Sebelumnya / Selanjutnya
FS_FADE_OUT_MS = 60     # animasi: layar meredup sebelum berganti layar penuh (0 = mati)
FS_FADE_IN_MS = 150     # animasi: layar muncul perlahan setelah berganti (0 = mati)
TRACK = C.TRACK_OFF
OV_MAIN = 88      # ukuran tombol putar/jeda di tengah video (jendela biasa)
OV_FULL = 120     # ... dan saat layar penuh
OV_IDLE = 2.2     # detik kursor diam saat video diputar -> tombol disembunyikan

# Pilihan murid diingat selama aplikasi terbuka (tidak reset saat pindah pelajaran)
_PREF = {"volume": 80, "mute": False, "sub": None}   # sub: None/"off" = mati, atau nama label

# Subtitle "naik" (on/off): supaya timeline Blender di video tidak tertutup subtitle.
# Disimpan di data\\subtitle.json, berlaku untuk semua video di PC ini.
SUB_UP_POS = 80          # posisi subtitle saat naik (% tinggi video; normal = 100)
_SUB_FILE = os.path.join(C.DATA_DIR, "subtitle.json")
# Video pembuka M3DAN (3 detik) sebelum setiap video pelajaran murid (bukan trial).
INTRO_PATH = os.path.join(C.VIDEO_DIR, "intro", "intro.mp4")
INTRO_MAX = 3.0        # detik; lebih panjang dari ini langsung dipotong
INTRO_TIMEOUT = 4.0    # intro tidak termuat / macet: langsung ke video pelajaran


def _sub_up():
    try:
        import json
        with open(_SUB_FILE, encoding="utf-8") as f:
            return bool(json.load(f).get("up"))
    except Exception:
        return False


def _save_sub_up(on):
    try:
        import json
        os.makedirs(C.DATA_DIR, exist_ok=True)
        with open(_SUB_FILE, "w", encoding="utf-8") as f:
            json.dump({"up": bool(on)}, f)
    except Exception as exc:
        C.log(f"Pengaturan subtitle tidak tersimpan: {exc!r}")

class Status:
    """Hasil poll() sebuah mesin pemutar (tanpa modul collections, biar aman di .exe)."""
    __slots__ = ("pos", "dur", "playing", "ended", "error", "image")

    def __init__(self, pos, dur, playing, ended, error, image):
        self.pos, self.dur, self.playing = pos, dur, playing
        self.ended, self.error, self.image = ended, error, image


def _fmt(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _icon(key, layers, w, h):
    """Ikon halus (anti-alias) sebagai PhotoImage; None kalau gagal (dipakai gambar canvas biasa).
    Canvas Tk tidak anti-alias, jadi lingkaran / diagonal / panah di canvas tampak bergerigi."""
    return AA.photo(key, lambda: AA.render(layers, w, h))


# =============================================================================
# Mesin cadangan: OpenCV (tanpa suara)
# =============================================================================
class _Reader(threading.Thread):
    """Membaca video: putar/jeda/geser, dan menyiapkan frame terbaru (pas di kotak layar)."""

    def __init__(self, path):
        super().__init__(daemon=True)
        self.path = path
        self.failed = False
        self.error = ""
        self.fps = 30.0
        self.total = 0
        self.ended = False
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._size = (640, 360)
        self._latest = None     # (gambar Pillow, nomor frame)
        self._playing = False
        self._seek = None
        self._redraw = False

    def set_size(self, width, height):
        with self._lock:
            self._size = (max(2, int(width)), max(2, int(height)))
            self._redraw = True

    def set_playing(self, value):
        with self._lock:
            self._playing = bool(value)
            if value and self.ended:    # putar lagi setelah selesai -> mulai dari awal
                self.ended = False
                self._seek = 0

    def seek(self, frame):
        with self._lock:
            self._seek = max(0, int(frame))
            self.ended = False

    def get_latest(self):
        with self._lock:
            item, self._latest = self._latest, None
        return item

    def stop(self):
        self._stop_event.set()

    def run(self):
        cap = cv2.VideoCapture(self.path)
        try:
            if not cap.isOpened():
                self._fail("Could not open the video (unsupported format/codec?)")
                return
            fps = cap.get(cv2.CAP_PROP_FPS)
            if not fps or fps != fps or fps < 1 or fps > 240:
                fps = 30.0
            self.fps = fps
            total = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            self.total = int(total) if total and total == total and total > 0 else 0
            step = max(1, round(fps / MAX_FPS))
            interval = step / fps

            ok, last = cap.read()           # frame pertama = gambar awal (jeda)
            if not ok:
                self._fail("Video is empty / damaged")
                return
            pos = 0
            self._publish(last, pos)

            while not self._stop_event.is_set():
                t0 = time.perf_counter()
                with self._lock:
                    playing, seek, redraw = self._playing, self._seek, self._redraw
                    self._seek, self._redraw = None, False
                wait = 0.03
                if seek is not None:
                    if self.total:
                        seek = min(seek, self.total - 1)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, seek)
                    ok, frame = cap.read()
                    if ok:
                        last, pos = frame, seek
                        self._publish(last, pos)
                elif playing:
                    for _ in range(step - 1):
                        cap.grab()
                    ok, frame = cap.read()
                    if not ok:
                        with self._lock:
                            self.ended = True
                            self._playing = False
                    else:
                        last, pos = frame, pos + step
                        self._publish(last, pos)
                    wait = interval - (time.perf_counter() - t0)
                elif redraw:
                    self._publish(last, pos)
                self._stop_event.wait(max(wait, 0.005))
        except Exception as exc:
            self._fail(repr(exc))
        finally:
            cap.release()

    def _fail(self, message):
        self.failed = True
        self.error = message

    def _publish(self, frame, pos):
        img = self._prepare(frame)
        with self._lock:
            self._latest = (img, pos)

    def _prepare(self, frame):
        """Penuhi kotak layar (16:9) tanpa bar hitam: skala lalu potong bagian tengah."""
        with self._lock:
            tw, th = self._size
        h, w = frame.shape[:2]
        scale = max(tw / w, th / h)
        nw, nh = max(tw, int(math.ceil(w * scale))), max(th, int(math.ceil(h * scale)))
        interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
        small = cv2.resize(frame, (nw, nh), interpolation=interp)
        x0, y0 = (nw - tw) // 2, (nh - th) // 2
        canvas = np.ascontiguousarray(small[y0:y0 + th, x0:x0 + tw])
        return Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))


class _CvEngine:
    has_audio = False

    def __init__(self):
        self.reader = None
        self.pos = 0.0

    def load(self, path, subs=(), size=None):
        self.stop()
        self.pos = 0.0
        self.reader = _Reader(path)
        if size and size[0] > 2 and size[1] > 2:
            self.reader.set_size(*size)
        self.reader.start()

    def stop(self):
        if self.reader is not None:
            self.reader.stop()
            self.reader = None

    terminate = stop

    def set_size(self, w, h):
        if self.reader is not None:
            self.reader.set_size(w, h)

    def set_playing(self, value):
        if self.reader is not None:
            self.reader.set_playing(value)

    def seek(self, sec, exact=True):
        if self.reader is not None:
            self.reader.seek(int(sec * self.reader.fps))

    def poll(self):
        r = self.reader
        if r is None:
            return Status(0.0, 0.0, False, False, "", None)
        img = None
        item = r.get_latest()
        if item is not None:
            img, frame_no = item
            self.pos = frame_no / r.fps
        dur = r.total / r.fps if r.total else 0.0
        return Status(self.pos, dur, r._playing and not r.ended, r.ended,
                      r.error if r.failed else "", img)

    # tidak ada suara / subtitle
    def take_toggle(self):
        return False

    def set_volume(self, volume, muted):
        pass

    def sub_options(self):
        return []

    def sub_active(self):
        return False

    def set_sub(self, track_id, label=None):
        pass

    def add_sub_file(self, path):
        pass


# =============================================================================
# Mesin utama: mpv (suara + subtitle, tampil di dalam jendela aplikasi)
# =============================================================================
class _MpvEngine:
    has_audio = True

    def __init__(self, wid):
        mpv = mpv_support.get()
        opts = dict(
            wid=str(int(wid)),              # menempel di dalam widget Tk (bukan jendela baru)
            input_default_bindings=False, input_vo_keyboard=True, osc=False,
            keep_open="yes",                # berhenti di frame terakhir saat selesai
            panscan=1.0,                    # isi penuh layar 16:9 (tanpa bar hitam)
            sub_auto="no", sub_font_size=40, sub_border_size=2.5,
            hwdec="auto-safe",
            vd_lavc_threads=2)              # kalau GPU decode tidak ada: CPU dipakai maks. 2 thread
        if C.lite():
            # mode ringan (iGPU AMD Vega + Blender): decode di CPU dan penskala paling ringan,
            # supaya GPU tidak kelamaan sibuk (AMD "driver timeout" / TDR)
            opts.update(hwdec="no", scale="bilinear", dscale="bilinear", cscale="bilinear",
                        dither_depth="no", correct_downscaling="no", sigmoid_upscaling="no",
                        deband="no", interpolation="no")

        def on_log(level, prefix, text):    # pesan error/peringatan libmpv -> app.log
            if level in ("fatal", "error", "warn"):
                C.log(f"mpv[{level}] {prefix}: {str(text).strip()}")
        try:
            self.mp = mpv.MPV(log_handler=on_log, loglevel="warn", **opts)
        except TypeError:                   # versi python-mpv tanpa log_handler
            self.mp = mpv.MPV(**opts)
        self.loaded = False
        self.toggle_requested = False
        self.key_request = None         # "toggle" (F / F11) atau "esc", dari papan ketik di atas video
        self._need_subs = False
        self._subs = []
        self.set_volume(_PREF["volume"], _PREF["mute"])

        @self.mp.event_callback("file-loaded")
        def _on_loaded(event):
            self.loaded = True

        @self.mp.message_handler("lesson-toggle")
        def _on_toggle(*args):
            self.toggle_requested = True

        @self.mp.message_handler("lesson-key")
        def _on_key(*args):
            a = args[0] if args else "toggle"
            self.key_request = a.decode() if isinstance(a, bytes) else str(a)

        try:    # klik kiri di video = putar/jeda
            self.mp.command("keybind", "MBTN_LEFT", "script-message lesson-toggle")
        except Exception as exc:
            C.log(f"mpv: klik-untuk-jeda tidak aktif: {exc!r}")
        # Papan ketik saat fokus ada di jendela video: F / F11 = layar penuh, Esc = keluar
        for key, arg in (("f", "toggle"), ("F", "toggle"), ("F11", "toggle"), ("ESC", "esc")):
            try:
                self.mp.command("keybind", key, f"script-message lesson-key {arg}")
            except Exception as exc:
                C.log(f"mpv: tombol {key} tidak aktif: {exc!r}")

    # --- memuat / berhenti ---
    def load(self, path, subs=(), size=None):
        self.loaded = False
        self._need_subs = True
        self._subs = list(subs)
        try:
            self.mp.pause = True            # mulai dalam keadaan jeda (gambar awal tampil)
        except Exception as exc:
            C.log(f"mpv: tidak bisa mulai dalam keadaan jeda: {exc!r}")
        self.mp.command("loadfile", path, "replace")

    def stop(self):
        try:
            self.mp.command("stop")
        except Exception:
            pass

    def terminate(self):
        try:
            self.mp.terminate()
        except Exception as exc:
            C.log(f"mpv terminate: {exc!r}")

    def set_size(self, w, h):
        pass    # jendela mpv mengikuti ukuran widget induknya

    # --- putar / geser ---
    def set_playing(self, value):
        try:
            if value and self.mp.eof_reached:
                self.mp.command("seek", "0", "absolute")
            self.mp.pause = not value
        except Exception as exc:
            C.log(f"mpv set_playing: {exc!r}")

    def seek(self, sec, exact=True):
        try:
            self.mp.command("seek", str(max(0.0, float(sec))),
                            "absolute" if exact else "absolute+keyframes")
        except Exception as exc:
            C.log(f"mpv seek: {exc!r}")

    def take_toggle(self):
        if self.toggle_requested:
            self.toggle_requested = False
            return True
        return False

    def take_key(self):
        key, self.key_request = self.key_request, None
        return key

    def poll(self):
        if self.loaded and self._need_subs:
            self._need_subs = False
            self._finish_load()
        try:
            pos = self.mp.time_pos or 0.0
            dur = self.mp.duration or 0.0
            paused = bool(self.mp.pause)
            eof = bool(self.mp.eof_reached)
        except Exception:
            pos, dur, paused, eof = 0.0, 0.0, True, False
        return Status(float(pos), float(dur), (not paused) and not eof, eof, "", None)

    # --- suara ---
    def set_volume(self, volume, muted):
        _PREF["volume"], _PREF["mute"] = volume, muted
        try:
            self.mp.volume = volume
            self.mp.mute = bool(muted)
        except Exception as exc:
            C.log(f"mpv volume: {exc!r}")

    # --- subtitle ---
    def set_sub_up(self, on):
        """Subtitle naik (di atas timeline Blender) atau di posisi normal."""
        try:
            self.mp["sub-pos"] = SUB_UP_POS if on else 100
        except Exception as exc:
            C.log(f"mpv sub-pos: {exc!r}")

    def _finish_load(self):
        self.set_sub_up(_sub_up())      # subtitle naik / normal (pilihan murid)
        for sub in self._subs:
            if sub.get("label") not in SUB_LANGS:
                continue
            args = ["sub-add", sub["path"], "auto", sub["label"]]
            if sub.get("lang"):
                args.append(sub["lang"])
            try:
                self.mp.command(*args)
            except Exception as exc:
                C.log(f"mpv sub-add {sub['path']!r}: {exc!r}")
        opts = self.sub_options()
        C.log(f"mpv: subtitle terbaca={[o['label'] for o in opts]}")
        pref, target = _PREF["sub"], "no"
        if pref is None and opts:
            # belum pernah memilih: nyalakan otomatis (utamakan Indonesia, lalu yang pertama)
            pick = next((o for o in opts if o["label"] == "Indonesia"), opts[0])
            target, _PREF["sub"] = pick["id"], pick["label"]
        elif pref and pref != "off":
            for opt in opts:
                if opt["label"] == pref:
                    target = opt["id"]
                    break
        try:
            self.mp.sid = target
        except Exception as exc:
            C.log(f"mpv sid: {exc!r}")

    def sub_options(self):
        try:
            tracks = self.mp.track_list or []
        except Exception:
            return []
        out = []
        for t in tracks:
            if t.get("type") != "sub":
                continue
            label = t.get("title") or lessons.lang_label(t.get("lang")) or ""
            label = lessons.LANG_NAMES.get(label.strip().lower(), label.strip())
            if label not in SUB_LANGS:      # hanya Indonesia dan English
                continue
            out.append({"id": t.get("id"), "label": label, "selected": bool(t.get("selected"))})
        out.sort(key=lambda o: SUB_LANGS.index(o["label"]))
        return out

    def sub_active(self):
        try:
            sid = self.mp.sid
        except Exception:
            return False
        return sid not in (None, False, "no", 0)

    def set_sub(self, track_id, label=None):
        try:
            self.mp.sid = track_id if track_id else "no"
        except Exception as exc:
            C.log(f"mpv set sub: {exc!r}")
        _PREF["sub"] = label if track_id else "off"

    def add_sub_file(self, path):
        label = os.path.splitext(os.path.basename(path))[0]
        try:
            self.mp.command("sub-add", path, "select", label)
            _PREF["sub"] = label
        except Exception as exc:
            C.log(f"mpv sub-add {path!r}: {exc!r}")


# =============================================================================
# Tampilan pemutar
# =============================================================================
class LessonPlayer(tk.Frame):
    """Layar video + bar kontrol (putar/jeda, posisi, waktu, volume, subtitle)."""

    def __init__(self, master, color):
        super().__init__(master, bg=C.BG)
        self.color = color
        self.engine = None
        self.notice = ""
        self.has_video = False
        self.photo = None
        self.playing = False
        self.on_progress = None   # fn(posisi, durasi, selesai): progres murid
        self._resume = 0.0        # lanjut tonton: detik tujuan setelah video siap
        self._intro = None        # (path, hint, subs) pelajaran yang menunggu intro selesai
        self._intro_t0 = 0.0
        self.on_resumed = None    # fn(detik): diberi tahu saat lanjut tonton terjadi
        self.blocked = False      # True saat popup kuis terbuka: tombol putar melayang disembunyikan
        self.pos = 0.0
        self.dur = 0.0
        self.sub_on = False
        self._drag = False
        self._btn_hover = False
        self._n = 0
        self._job = None
        self._path = None
        self._subs = ()
        self.fullscreen = False
        self.on_fullscreen = None      # diisi LessonsPanel: dipanggil (True/False) saat berganti
        self._fs_busy = False          # True selama peralihan layar penuh (abaikan tekan ganda)
        self._curtain = None           # tirai cadangan kalau -alpha tidak didukung
        self._veil = None              # "alpha" / "curtain" selama peralihan
        self._foot = FOOT_H
        self._hsize = (0, 0)
        self._load_t = 0.0

        # --- layar: kanvas (pesan / gambar cadangan) + permukaan untuk mpv ---
        # Kolom pemutar selalu berukuran pas: layar 16:9 + bar kontrol + baris tombol.
        self.holder = tk.Frame(self, bg=C.BG)
        self.holder.pack(fill="both", expand=True)
        self.column = tk.Frame(self.holder, bg=C.BG)
        self.stage = tk.Frame(self.column, bg="#000000", height=360)
        self.stage.pack(fill="x")
        self.holder.bind("<Configure>", self._layout)
        self.screen = tk.Canvas(self.stage, bg="#000000", highlightthickness=0, bd=0)
        self.screen.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.img_item = self.screen.create_image(0, 0, anchor="nw")
        # Tombol putar/jeda: segitiga / dua balok putih di tengah video (jendela kecil terpisah,
        # lihat play_overlay.py), tampil saat kursor di atas video, juga saat layar penuh.
        self.ov = None
        self._click_t = 0.0            # waktu klik-video terakhir (cegah putar/jeda dua kali)
        self._btn_prev = False         # keadaan tombol mouse pada pemeriksaan sebelumnya
        self._ptr = (0, 0)
        self._ptr_t = 0.0
        self._ov_n = 0
        self.screen.create_text(0, 0, text="", fill=C.MUTED, font=(C.FONT, 11),
                                justify="center", tags="msg")
        self.screen.bind("<Configure>", self._on_resize)
        self.screen.bind("<Button-1>", lambda e: self._click_toggle())
        self.surface = tk.Frame(self.stage, bg="#000000")   # mpv menggambar di sini

        # --- bar kontrol ---
        bar = tk.Frame(self.column, bg=C.CARD, height=BAR_H)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        # Penutup bar selama intro: timeline & tombol tidak tampil, susunan tidak bergeser
        self._bar_cover = tk.Frame(bar, bg=C.BG)
        # Baris di bawah bar: dipakai LessonsPanel untuk tombol Sebelumnya / Selanjutnya
        self.footer = tk.Frame(self.column, bg=C.BG, height=FOOT_H)
        self.footer.pack(fill="x", side="bottom")
        self.footer.pack_propagate(False)
        self.btn = tk.Canvas(bar, width=36, height=36, bg=C.CARD, highlightthickness=0,
                             bd=0, cursor="hand2")
        self.btn.pack(side="left", padx=(12, 6), pady=6)
        self.btn.bind("<Button-1>", lambda e: self.toggle())
        self.btn.bind("<Enter>", lambda e: self._set_hover(True))
        self.btn.bind("<Leave>", lambda e: self._set_hover(False))

        self.fs = tk.Canvas(bar, width=36, height=36, bg=C.CARD, highlightthickness=0,
                            bd=0, cursor="hand2")
        self.fs.pack(side="right", padx=(2, 12), pady=6)
        self.fs.bind("<Button-1>", lambda e: self.toggle_fullscreen())

        self.cc = tk.Canvas(bar, width=44, height=36, bg=C.CARD, highlightthickness=0,
                            bd=0, cursor="hand2")
        self.cc.pack(side="right", padx=(2, 2), pady=6)
        self.cc.bind("<Button-1>", lambda e: self._open_sub_menu())

        # Subtitle naik on/off (supaya timeline Blender di video tidak tertutup)
        self.up = tk.Canvas(bar, width=36, height=36, bg=C.CARD, highlightthickness=0,
                            bd=0, cursor="hand2")
        self.up.pack(side="right", padx=(2, 0), pady=6)
        self.up.bind("<Button-1>", lambda e: self._toggle_sub_up())
        try:
            from elearning.ui.sidebar import _Tip
            _Tip(self.up, "Raise subtitles (keeps the Blender timeline visible)")
        except Exception:
            pass

        self.vol_box = tk.Frame(bar, bg=C.CARD)
        self.vol_box.pack(side="right", padx=(8, 4))
        self.vol_icon = tk.Canvas(self.vol_box, width=30, height=36, bg=C.CARD,
                                  highlightthickness=0, bd=0, cursor="hand2")
        self.vol_icon.pack(side="left")
        self.vol_icon.bind("<Button-1>", lambda e: self._toggle_mute())
        self.vol_bar = tk.Canvas(self.vol_box, width=72, height=36, bg=C.CARD,
                                 highlightthickness=0, bd=0, cursor="hand2")
        self.vol_bar.pack(side="left")
        self.vol_bar.bind("<Button-1>", self._on_volume)
        self.vol_bar.bind("<B1-Motion>", self._on_volume)

        self.time_lbl = tk.Label(bar, text="00:00 / 00:00", bg=C.CARD, fg=C.MUTED,
                                 font=(C.FONT, 9), width=12)
        self.time_lbl.pack(side="right", padx=(6, 6))
        self.seekbar = tk.Canvas(bar, height=24, bg=C.CARD, highlightthickness=0, bd=0,
                                 cursor="hand2")
        self.seekbar.pack(side="left", fill="x", expand=True, padx=6)
        self.seekbar.bind("<Configure>", lambda e: self._draw_seek())
        self.seekbar.bind("<Button-1>", lambda e: self._seek_at(e.x, exact=False))
        self.seekbar.bind("<B1-Motion>", lambda e: self._seek_at(e.x, exact=False))
        self.seekbar.bind("<ButtonRelease-1>", self._seek_release)

        top = self.winfo_toplevel()
        top._lesson_player = self
        if not getattr(top, "_lesson_keys", False):   # pasang sekali saja per jendela
            top._lesson_keys = True

            def key(which):
                p = getattr(top, "_lesson_player", None)
                if p is not None and p.winfo_exists():
                    p._on_key(which)
            top.bind("<Escape>", lambda e: key("esc"), add="+")
            for seq in ("<F11>", "<f>", "<F>"):
                top.bind(seq, lambda e: key("toggle"), add="+")

        self._refresh()
        self._tick()

    def _layout(self, event):
        """Layar dibuat 16:9 dan selebar mungkin; kalau kurang tinggi, mengecil (tetap 16:9)."""
        self._hsize = (event.width, event.height)
        self._apply_layout()

    def _apply_layout(self):
        aw, ah = self._hsize
        if aw < 50 or ah < 50:
            return
        avail = ah - BAR_H - self._foot
        w = aw
        h = int(w * 9 / 16)
        if h > avail:
            h = max(90, avail)
            w = int(h * 16 / 9)
        self.stage.config(height=h)
        self.column.place(relx=0.5, rely=0.5, anchor="center", width=w,
                          height=h + BAR_H + self._foot)
        cb = getattr(self, "on_layout", None)
        if cb is not None:          # judul pelajaran ikut sejajar tepi kiri video
            cb((aw - w) // 2)

    # --- layar penuh ----------------------------------------------------------
    def toggle_fullscreen(self, want=None):
        """Layar penuh: sidebar, judul, dan tombol di bawah disembunyikan; Esc / F / F11 keluar.

        Semua perubahan susunan + perubahan ukuran jendela terjadi DI BALIK jendela transparan (alpha 0),
        lalu jendela ditampilkan lagi setelah ukuran stabil. Hasilnya tidak ada kedip / video loncat.
        """
        want = (not self.fullscreen) if want is None else bool(want)
        if want == self.fullscreen or self._fs_busy:
            return
        if self.ov is not None:
            self.ov.settle()        # sembunyikan tombol putar/jeda selama peralihan layar penuh
        self._fs_busy = True
        self.fullscreen = want

        top = self.winfo_toplevel()
        top.update_idletasks()
        self._fs_before = (top.winfo_width(), top.winfo_height())
        self._veil_on(lambda: self._fs_apply(want))     # meredup dulu, baru berganti

    def _fs_apply(self, want):
        """Ubah susunan layar (terjadi saat jendela sedang transparan)."""
        bg = "#000000" if want else C.BG
        for w in (self.holder, self.column, self._bar_cover):
            w.config(bg=bg)
        no_footer = want or getattr(self, "no_footer", False)   # trial: tanpa baris tombol
        self._foot = 0 if no_footer else FOOT_H
        if no_footer:
            self.footer.pack_forget()
        else:
            self.footer.pack(fill="x", side="bottom")
        if self.on_fullscreen is not None:
            self.on_fullscreen(want)
        self._draw_fs()
        self.after(10, self._settle, want, 0, None)

    def _settle(self, want, tries, last):
        """Tunggu jendela selesai berubah ukuran (sebentar saja), baru tampilkan lagi."""
        try:
            top = self.winfo_toplevel()
            top.update_idletasks()
            size = (top.winfo_width(), top.winfo_height(),
                    self.holder.winfo_width(), self.holder.winfo_height())
            changed = size[:2] != getattr(self, "_fs_before", None)
            stable = (size == last)
            if (changed and stable) or tries >= 15:     # batas aman 15 x 10 ms = 0,15 detik
                self._apply_layout()
                top.update_idletasks()
                C.log(f"layar penuh: want={want} siap setelah {tries} cek (changed={changed})")
                self.after(30, self._reveal)            # beri mpv waktu menggambar frame baru
                return
            self.after(10, self._settle, want, tries + 1, size)
        except tk.TclError:
            self._open_curtain()

    def _fade(self, start, end, ms, done=None):
        """Ubah transparansi jendela dari start ke end (0..1) dalam ms milidetik, melambat di akhir."""
        top = self.winfo_toplevel()
        steps = max(1, int(ms / C.UI_FRAME_MS))     # maks. 30 fps

        def step(i=0):
            t = (i + 1) / steps
            t = 1 - (1 - t) ** 2            # ease-out
            try:
                top.attributes("-alpha", start + (end - start) * t)
            except tk.TclError:
                return
            if i + 1 < steps:
                self.after(C.UI_FRAME_MS, step, i + 1)
            elif done is not None:
                done()
        step()

    def _veil_on(self, cont):
        """Sembunyikan jendela (transparansi level OS: bingkai, taskbar, dan jendela mpv ikut
        tersembunyi), lalu jalankan cont(). Dengan animasi meredup kalau FS_FADE_OUT_MS > 0."""
        top = self.winfo_toplevel()
        try:
            top.attributes("-alpha", 1.0)      # uji dukungan -alpha
            self._veil = "alpha"
            if FS_FADE_OUT_MS > 0 and not C.lite():
                self._fade(1.0, 0.0, FS_FADE_OUT_MS, cont)
                return
            top.attributes("-alpha", 0.0)
        except tk.TclError:
            self._veil = None
            try:    # cadangan: tirai hitam (kurang rapi, tapi lebih baik daripada tanpa penutup)
                curtain = tk.Frame(top, bg="#000000")
                curtain.place(x=0, y=0, relwidth=1, relheight=1)
                curtain.lift()
                self._curtain = curtain
                self._veil = "curtain"
                top.update_idletasks()
            except tk.TclError:
                pass
        cont()

    def _reveal(self):
        """Tampilkan jendela lagi: muncul perlahan (fade-in) kalau FS_FADE_IN_MS > 0."""
        if self._veil == "alpha" and FS_FADE_IN_MS > 0 and not C.lite():
            self._fade(0.0, 1.0, FS_FADE_IN_MS, self._open_curtain)
        else:
            self._open_curtain()

    def _open_curtain(self):
        """Buka veil: jendela tampil kembali (nama lama dipertahankan)."""
        veil, self._veil = self._veil, None
        c, self._curtain = self._curtain, None
        if c is not None:
            try:
                c.destroy()
            except tk.TclError:
                pass
        if veil == "alpha":
            try:
                self.winfo_toplevel().attributes("-alpha", 1.0)
            except tk.TclError:
                pass
        self._fs_busy = False

    def _on_key(self, which):
        if not self.winfo_viewable():
            return
        try:   # sedang mengetik catatan / jawaban: huruf F bukan perintah layar penuh
            if which != "esc" and isinstance(self.focus_get(), tk.Entry):
                return
        except (KeyError, tk.TclError):
            pass
        if which == "esc":
            if self.fullscreen:
                self.toggle_fullscreen(False)
        elif self.has_video:
            self.toggle_fullscreen()

    def _draw_fs(self):
        c = self.fs
        c.delete("all")
        col = C.TEXT if self.has_video else C.LOCKED
        x0, x1, y0, y1, k = 9, 27, 9, 27, 6
        if self.fullscreen:     # sudut menghadap ke dalam = keluar layar penuh
            pts = [((x0 + k, y0), (x0 + k, y0 + k), (x0, y0 + k)),
                   ((x1 - k, y0), (x1 - k, y0 + k), (x1, y0 + k)),
                   ((x0 + k, y1), (x0 + k, y1 - k), (x0, y1 - k)),
                   ((x1 - k, y1), (x1 - k, y1 - k), (x1, y1 - k))]
        else:                   # sudut menghadap ke luar = masuk layar penuh
            pts = [((x0, y0 + k), (x0, y0), (x0 + k, y0)),
                   ((x1 - k, y0), (x1, y0), (x1, y0 + k)),
                   ((x0, y1 - k), (x0, y1), (x0 + k, y1)),
                   ((x1 - k, y1), (x1, y1), (x1, y1 - k))]
        ph = _icon(("pl-fs", self.fullscreen, col),
                   [(AA.polylines([list(p) for p in pts], 1.0), col)], 36, 36)
        if ph is not None:
            c.create_image(0, 0, image=ph, anchor="nw")
            return
        for p in pts:
            c.create_line(*p[0], *p[1], *p[2], fill=col, width=2)

    def _ensure_engine(self):
        if self.engine is not None:
            return
        if mpv_support.get() is not None:
            try:
                self.surface.place(relx=0, rely=0, relwidth=1, relheight=1)
                self.surface.update_idletasks()
                self.engine = _MpvEngine(self.surface.winfo_id())
                self.surface.place_forget()
            except Exception as exc:
                C.log(f"mpv gagal dibuat, pakai OpenCV tanpa suara: {exc!r}")
                self.surface.place_forget()
                self.engine = None
                self.notice = "Sound & subtitles are off (mpv could not start, see app.log)"
        else:
            self.notice = "Sound & subtitles are not active: " + mpv_support.reason()
        if self.engine is None and HAS_VIDEO:
            self.engine = _CvEngine()
        if self.engine is None:
            C.log(f"Pemutar tidak bisa dipakai: {IMPORT_ERROR}")
            return
        if not self.engine.has_audio:    # pemutar cadangan: sembunyikan volume & CC
            self.vol_box.pack_forget()
            self.cc.pack_forget()
            self.up.pack_forget()
        self._refresh()

    def _show_surface(self, show):
        if isinstance(self.engine, _MpvEngine):
            if show:
                self.surface.place(relx=0, rely=0, relwidth=1, relheight=1)
            else:
                self.surface.place_forget()

    # --- memuat video ---------------------------------------------------------
    def resume_to(self, sec):
        """Lanjut tonton: setelah video siap, langsung ke detik ini (masih dijeda)."""
        self._resume = float(sec or 0)

    def load_with_intro(self, path, hint="", subs=()):
        """Putar video pembuka (3 detik) dulu, lalu otomatis video pelajaran."""
        from elearning.app_settings import feature
        if not path or not os.path.isfile(INTRO_PATH) or not feature("intro"):   # Dev: off
            self.load(path, hint, subs)
            return
        self.load(INTRO_PATH)
        if not self.has_video or self.engine is None:
            self.load(path, hint, subs)
            return
        self._intro = (path, hint, subs)
        self._intro_t0 = time.time()
        self._bar_cover.config(bg=self.column.cget("bg"))
        self._bar_cover.place(x=0, y=0, relwidth=1, relheight=1)
        self._bar_cover.lift()
        try:
            self.engine.set_playing(True)
            self.playing = True
        except Exception as exc:
            C.log(f"Intro tidak bisa diputar: {exc!r}")
            self._finish_intro()
            return
        self._refresh()

    def _finish_intro(self):
        """Intro selesai / dilewati: muat video pelajaran dan langsung putar."""
        if self._intro is None:
            return
        (path, hint, subs), self._intro = self._intro, None
        resume = self._resume          # lanjut tonton tetap berlaku untuk video pelajaran
        self.load(path, hint, subs)
        self._resume = resume
        if self.has_video and self.engine is not None:
            try:
                self.engine.set_playing(True)
                self.playing = True
            except Exception as exc:
                C.log(f"Video pelajaran tidak bisa diputar setelah intro: {exc!r}")
        self._refresh()

    def load(self, path, hint="", subs=()):
        self._intro = None
        self._bar_cover.place_forget()
        self._resume = 0.0
        self._ensure_engine()
        e = self.engine
        self.playing = False
        self.pos = self.dur = 0.0
        self.sub_on = False
        self.screen.itemconfig(self.img_item, image="")
        self.photo = None
        if e is not None:
            e.stop()
        if not path or e is None:
            self.has_video = False
            self._show_surface(False)
            self._message(hint or "Video not available yet.")
            return
        self._message("")
        self._path, self._subs = path, subs
        self._load_t = time.time()
        self._show_surface(True)
        try:
            if e.has_audio:
                e.load(path, subs)
            else:
                e.load(path, size=(self.screen.winfo_width(), self.screen.winfo_height()))
        except Exception:
            C.log(f"Gagal memuat video {path!r}:\n{traceback.format_exc()}")
            self._fallback_to_cv("mpv gagal memuat video")
            return
        self.has_video = True
        self._refresh()

    def _fallback_to_cv(self, why):
        """mpv bermasalah: ganti ke pemutar cadangan OpenCV supaya video tetap tampil."""
        path = getattr(self, "_path", None)
        old = self.engine
        self._show_surface(False)
        if old is not None:
            try:
                old.terminate()
            except Exception:
                pass
        self.engine = None
        self.has_video = False
        self.playing = False
        if not HAS_VIDEO or not path:
            self._message("Video cannot be played (see app.log).")
            return
        self.engine = _CvEngine()
        self.vol_box.pack_forget()
        self.cc.pack_forget()
        self.up.pack_forget()
        self.notice = f"Sound & subtitles are off: {why} (see app.log)"
        self.engine.load(path, size=(self.screen.winfo_width(), self.screen.winfo_height()))
        self.has_video = True
        self._refresh()

    def _message(self, text):
        self.screen.itemconfig("msg", text=text)
        self._refresh()

    # --- kontrol --------------------------------------------------------------
    def toggle(self):
        if self._intro is not None:       # intro tidak bisa dijeda / dilewati
            return
        if not self.has_video or self.engine is None:
            return
        want = not self.playing
        self.engine.set_playing(want)
        self.playing = want
        self._refresh()

    def _pause(self):
        if self.playing and self.engine is not None:
            self.engine.set_playing(False)
            self.playing = False
            self._refresh()

    def _seek_at(self, x, exact):
        if self._intro is not None:       # intro tidak bisa digeser
            return
        self._seek_at_real(x, exact)

    def _seek_at_real(self, x, exact):
        if not self.has_video or self.dur <= 0:
            return
        self._drag = True
        w = max(1, self.seekbar.winfo_width() - 16)
        frac = min(1.0, max(0.0, (x - 8) / w))
        self.pos = frac * self.dur
        self.engine.seek(self.pos, exact=exact)
        self._update_time()
        self._draw_seek()

    def _seek_release(self, event):
        if self._drag:
            self._seek_at(event.x, exact=True)
            self._drag = False

    def _set_hover(self, value):
        self._btn_hover = value
        self._draw_button()

    # --- volume ---------------------------------------------------------------
    def _on_volume(self, event):
        if self.engine is None or not self.engine.has_audio:
            return
        w = max(1, self.vol_bar.winfo_width() - 12)
        vol = int(round(min(1.0, max(0.0, (event.x - 6) / w)) * 100))
        self.engine.set_volume(vol, False)
        self._draw_volume()

    def _toggle_mute(self):
        if self.engine is None or not self.engine.has_audio:
            return
        self.engine.set_volume(_PREF["volume"] or 80, not _PREF["mute"])
        self._draw_volume()

    # --- subtitle -------------------------------------------------------------
    def _open_sub_menu(self):
        e = self.engine
        if e is None or not e.has_audio or not self.has_video:
            return
        menu = tk.Menu(self, tearoff=0, bg=C.CARD, fg=C.TEXT, activebackground=self.color,
                       activeforeground="#ffffff", bd=0, relief="flat",
                       selectcolor=self.color, font=(C.FONT, 10))
        opts = e.sub_options()
        current = next((o["id"] for o in opts if o["selected"]), 0) if e.sub_active() else 0
        var = tk.IntVar(value=current or 0)
        menu.add_radiobutton(label="Subtitles: Off", variable=var, value=0,
                             command=lambda: self._pick_sub(0, "off"))
        for o in opts:
            menu.add_radiobutton(label=o["label"], variable=var, value=o["id"],
                                 command=lambda i=o["id"], l=o["label"]: self._pick_sub(i, l))
        if not opts:
            menu.add_command(label="(no subtitles for this video)", state="disabled")
        try:
            menu.tk_popup(self.cc.winfo_rootx() - 90, self.cc.winfo_rooty() - 8 - 30 * (len(opts) + 2))
        finally:
            menu.grab_release()

    def _toggle_sub_up(self):
        if not (self.has_video and self.engine is not None and self.engine.has_audio):
            return
        on = not _sub_up()
        _save_sub_up(on)
        self.engine.set_sub_up(on)
        self._draw_up()

    def _draw_up(self):
        """Tombol di sebelah CC: garis timeline + panah naik. Menyala = subtitle naik."""
        c = self.up
        c.delete("all")
        enabled = self.has_video and self.engine is not None and self.engine.has_audio
        on = _sub_up()
        col = self.color if (on and enabled) else (C.TEXT if enabled else C.LOCKED)
        layers = [(AA.polylines([[(10, 25), (26, 25)]], 1.0), col),
                  (AA.polylines([[(18, 20), (18, 10)], [(13.5, 14.5), (18, 10), (22.5, 14.5)]],
                                1.0), col)]
        ph = _icon(("pl-subup", col), layers, 36, 36)
        if ph is not None:
            c.create_image(0, 0, image=ph, anchor="nw")

    def _pick_sub(self, track_id, label):
        self.engine.set_sub(track_id, label)
        self.sub_on = bool(track_id)
        self._draw_cc()
        self._draw_up()

    # --- gambar ---------------------------------------------------------------
    def _on_resize(self, event):
        w, h = event.width, event.height
        if self.engine is not None:
            self.engine.set_size(w, h)
        cx, cy, r = w / 2, h / 2, 34
        self.screen.coords("msg", cx, cy)
        self.screen.itemconfig("msg", width=max(100, w - 60))

    def _refresh(self):
        show = self.has_video and not self.playing
        self.screen.itemconfig("overlay", state="normal" if show else "hidden")
        self.screen.configure(cursor="hand2" if self.has_video else "")
        self._draw_button()
        self._draw_volume()
        self._draw_cc()
        self._draw_up()
        self._draw_fs()
        self._update_time()
        self._draw_seek()

    def _draw_button(self):
        b = self.btn
        b.delete("all")
        # hover = warna kursus (sama dengan garis waktu, CC, subtitle naik), bukan oranye
        col = self.color if (self._btn_hover and self.has_video) else (
            C.TEXT if self.has_video else C.LOCKED)
        if self.playing:
            ph = _icon(("pl-pause", col), [(AA.bars([(11, 9, 16, 27), (21, 9, 26, 27)], 1.0), col)], 36, 36)
        else:
            ph = _icon(("pl-play", col), [(AA.tri([(12, 9), (12, 27), (27, 18)]), col)], 36, 36)
        if ph is not None:
            b.create_image(0, 0, image=ph, anchor="nw")
        elif self.playing:
            b.create_rectangle(11, 9, 16, 27, fill=col, outline="")
            b.create_rectangle(21, 9, 26, 27, fill=col, outline="")
        else:
            b.create_polygon(12, 9, 12, 27, 27, 18, fill=col, outline="")

    def _draw_volume(self):
        ic, bar = self.vol_icon, self.vol_bar
        ic.delete("all")
        bar.delete("all")
        muted = _PREF["mute"] or _PREF["volume"] == 0
        col = C.MUTED if muted else C.TEXT
        layers = [(AA.tri([(6, 14), (11, 14), (17, 9), (17, 27), (11, 22), (6, 22)]), col)]
        if muted:
            layers.append((AA.polylines([[(20, 14), (27, 22)], [(27, 14), (20, 22)]], 1.0), C.ERROR))
        else:
            layers.append((AA.arc(19, 18, 5, 1.0, -50, 50), col))
            if _PREF["volume"] > 50:
                layers.append((AA.arc(19.5, 18, 10, 1.0, -50, 50), col))
        big = (not muted) and _PREF["volume"] > 50
        ph = _icon(("pl-vol", muted, big, col), layers, 30, 36)
        if ph is not None:
            ic.create_image(0, 0, image=ph, anchor="nw")
        else:
            ic.create_polygon(6, 14, 11, 14, 17, 9, 17, 27, 11, 22, 6, 22, fill=col, outline="")
            if muted:
                ic.create_line(20, 14, 27, 22, fill=C.ERROR, width=2)
                ic.create_line(27, 14, 20, 22, fill=C.ERROR, width=2)
            else:
                ic.create_arc(14, 12, 24, 24, start=-50, extent=100, style="arc", outline=col, width=2)
                if _PREF["volume"] > 50:
                    ic.create_arc(11, 8, 28, 28, start=-50, extent=100, style="arc", outline=col, width=2)
        x0, x1, y = 6, 66, 18
        bar.create_rectangle(x0, y - 2, x1, y + 2, fill=TRACK, outline="")
        frac = 0 if muted else _PREF["volume"] / 100.0
        x = x0 + (x1 - x0) * frac
        if frac > 0:
            bar.create_rectangle(x0, y - 2, x, y + 2, fill=self.color, outline="")
        knob = _icon(("pl-knob10", C.TEXT), [(AA.circle(6, 6, 5), C.TEXT)], 12, 12)
        if knob is not None:
            bar.create_image(round(x), y, image=knob)
        else:
            bar.create_oval(x - 5, y - 5, x + 5, y + 5, fill=C.TEXT, outline="")

    def _draw_cc(self):
        c = self.cc
        c.delete("all")
        enabled = self.has_video
        col = self.color if (self.sub_on and enabled) else (C.TEXT if enabled else C.LOCKED)
        ph = _icon(("pl-cc", col), [(AA.rrect_ring(6, 9, 38, 27, 2.5, 1.0), col)], 44, 36)
        if ph is not None:
            c.create_image(0, 0, image=ph, anchor="nw")
        else:
            c.create_rectangle(6, 9, 38, 27, outline=col, width=2)
        c.create_text(22, 18, text="CC", fill=col, font=(C.FONT, 9, "bold"))

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
            knob = _icon(("pl-knob12", C.TEXT), [(AA.circle(7, 7, 6), C.TEXT)], 14, 14)
            if knob is not None:
                c.create_image(round(x), y, image=knob)
            else:
                c.create_oval(x - 6, y - 6, x + 6, y + 6, fill=C.TEXT, outline="")

    def _update_time(self):
        self.time_lbl.config(text=f"{_fmt(self.pos)} / {_fmt(self.dur)}")

    # --- pembaruan berkala ----------------------------------------------------
    # --- tombol putar/jeda melayang ------------------------------------------
    def _app_active(self):
        """True kalau jendela aplikasi terbuka di depan (bukan di-minimize / tertutup Blender)."""
        top = self.winfo_toplevel()
        try:
            if top.state() in ("iconic", "withdrawn"):
                return False
        except tk.TclError:
            return False
        fg = BL.is_foreground(top.winfo_id())
        return True if fg is None else fg

    def _pointer_in_stage(self):
        px, py = self.winfo_pointerxy()
        x, y = self.stage.winfo_rootx(), self.stage.winfo_rooty()
        return x <= px < x + self.stage.winfo_width() and y <= py < y + self.stage.winfo_height()

    def _update_overlay(self):
        try:
            want = (self.has_video and not self._fs_busy and not self.blocked
                    and self._intro is None          # intro: tanpa tombol putar/jeda
                    and self.winfo_viewable()
                    and self._app_active() and self._pointer_in_stage())
            if want:
                now, ptr = time.time(), self.winfo_pointerxy()
                if ptr != self._ptr:
                    self._ptr, self._ptr_t = ptr, now
                if self.playing and now - self._ptr_t > OV_IDLE:
                    want = False        # kursor diam saat video diputar: sembunyikan
            if self.ov is None:
                if not want:
                    return
                self.ov = PlayOverlay(self.winfo_toplevel(), on_click=self._click_toggle, size=OV_MAIN)
            self.ov.set_size(OV_FULL if self.fullscreen else OV_MAIN)
            self.ov.set_playing(self.playing)
            cx = self.stage.winfo_rootx() + self.stage.winfo_width() // 2
            cy = self.stage.winfo_rooty() + self.stage.winfo_height() // 2
            self.ov.sync(want, cx, cy)
        except tk.TclError:
            pass
        except Exception as exc:
            C.log(f"Tombol putar/jeda pemutar: {exc!r}")

    # --- klik di mana pun pada video = putar/jeda -----------------------------
    def _click_toggle(self):
        """Putar/jeda dari klik video. Klik bisa datang dari beberapa jalur sekaligus (event mpv,
        canvas, pemeriksaan mouse, tombol overlay): hanya satu yang dihitung per klik."""
        now = time.time()
        if now - self._click_t < 0.35:
            return
        self._click_t = now
        self.toggle()

    def _poll_click(self):
        """Mpv kadang tidak meneruskan klik ke Tk, jadi tekanan tombol kiri diperiksa langsung:
        klik di mana pun di area video (jendela biasa maupun layar penuh) memutar/menjeda."""
        down = BL.left_button_down()
        if down is None:
            return
        pressed, self._btn_prev = down and not self._btn_prev, down
        if not pressed or not self.has_video or self._fs_busy or not self._pointer_in_stage():
            return
        px, py = self.winfo_pointerxy()
        mine = BL.root_of(self.winfo_toplevel().winfo_id())
        if mine and BL.root_at_point(px, py) == mine:    # klik di video, bukan di jendela lain
            self._click_toggle()

    def _tick(self):
        self._ov_n += 1
        try:
            self._poll_click()
        except Exception as exc:
            C.log(f"Klik video: {exc!r}")
        if self._ov_n % 3 == 0:
            self._update_overlay()
        e = self.engine
        if e is not None and self.has_video:
            self._n += 1
            if e.take_toggle():
                self._click_toggle()
            key = getattr(e, "take_key", None)
            key = key() if key is not None else None
            if key:
                self._on_key(key)
            if not e.has_audio or self._n % 3 == 0:
                st = e.poll()
                if st.image is not None:
                    try:
                        self.photo = ImageTk.PhotoImage(st.image)   # simpan referensi
                        self.screen.itemconfig(self.img_item, image=self.photo)
                    except Exception as exc:
                        C.log(f"Gagal menampilkan frame pelajaran: {exc!r}")
                if self._intro is not None:   # intro: tanpa progres / lanjut tonton
                    waited = time.time() - self._intro_t0
                    if (st.error or st.ended or st.pos >= INTRO_MAX - 0.05
                            or waited > INTRO_MAX + INTRO_TIMEOUT):
                        self._finish_intro()
                    else:
                        self.dur, self.pos = st.dur, st.pos
                        self._update_time()
                        self._draw_seek()
                    self._job = self.after(30, self._tick)
                    return
                if e.has_audio and not e.loaded and time.time() - self._load_t > 6:
                    C.log(f"mpv tidak memuat video dalam 6 detik: {self._path!r}")
                    self._load_t = float("inf")
                    self._fallback_to_cv("mpv tidak bisa membuka video")
                    self._tell_notice()
                elif st.error:
                    C.log(f"Video pelajaran gagal diputar: {st.error}")
                    e.stop()
                    self.has_video = False
                    self.playing = False
                    self._show_surface(False)
                    self._message("Video cannot be played.")
                else:
                    self.dur = st.dur
                    if not self._drag:
                        self.pos = st.pos
                    if self._resume and st.dur > 0 and (not e.has_audio or e.loaded):
                        target, self._resume = min(self._resume, st.dur - 1), 0.0
                        e.seek(target, exact=True)
                        self.pos = target
                        self._update_time()
                        self._draw_seek()
                        if self.on_resumed is not None:
                            self.on_resumed(target)
                    if self.on_progress is not None and (st.playing or st.ended):
                        try:
                            self.on_progress(st.pos, st.dur, st.ended)
                        except Exception as exc:
                            C.log(f"Progres pelajaran: {exc!r}")
                    changed = st.playing != self.playing
                    self.playing = st.playing
                    if e.has_audio:
                        active = e.sub_active()
                        if active != self.sub_on:
                            self.sub_on = active
                            self._draw_cc()
                            self._draw_up()
                    if changed:
                        self._refresh()
                    else:
                        self._update_time()
                        self._draw_seek()
            if self.playing and not self.winfo_viewable():
                self._pause()    # jendela disembunyikan (mis. Blender dibuka) -> jeda
        self._job = self.after(30, self._tick)

    def _tell_notice(self):
        cb = getattr(self, "on_notice", None)
        if cb is not None:
            cb(self.notice)

    def destroy(self):
        if self.ov is not None:
            try:
                self.ov.destroy()
            except Exception:
                pass
            self.ov = None
        self._open_curtain()
        if self.fullscreen and self.on_fullscreen is not None:
            self.fullscreen = False
            try:
                self.on_fullscreen(False)
            except Exception:
                pass
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        if self.engine is not None:
            self.engine.terminate()     # hentikan video dan suara
            self.engine = None
        super().destroy()


class LessonsPanel(tk.Frame):
    """Isi halaman Materi: judul pelajaran + pemutar 16:9 + tombol Sebelumnya / Selanjutnya.

    Daftar pelajaran ada di sidebar (course_screen.py), bukan di halaman ini.
    items: daftar dari lessons.lessons_for(); on_select(index) dipanggil saat pelajaran berganti.
    """

    def __init__(self, master, course, items, index=0, on_select=None, on_fullscreen=None,
                 show_nav=True, student_id=None, program=None):
        super().__init__(master, bg=C.BG)
        self.course = course
        self.student_id = student_id   # None (trial) = progres tidak dicatat
        self.program = program         # "adult" -> kolom catatan, "kids" -> emote
        self._watching = None
        self._quiz_job = None
        self._quiz_open = None
        self._ended_seen = False
        self.items = items
        self.index = -1
        self.on_select = on_select
        self.on_fullscreen = on_fullscreen

        head = self.head = tk.Frame(self, bg=C.BG)
        head.pack(fill="x", padx=28, pady=(18, 10))
        self.title = tk.Label(head, text="", bg=C.BG, fg=C.TEXT, anchor="w",
                              font=(C.FONT, 16, "bold"))
        self.title.pack(side="left")
        # Salin judul (untuk nama file saat Save di Blender) + tanda "Disalin"
        self.copy_btn = tk.Canvas(head, width=30, height=30, bg=C.BG, highlightthickness=0,
                                  bd=0, cursor="hand2")
        self.copy_btn.pack(side="left", padx=(8, 0))
        self.copy_lbl = tk.Label(head, text="", bg=C.BG, fg=C.MUTED, font=(C.FONT, 9))
        self.copy_lbl.pack(side="left", padx=(2, 0))
        self._copy_state = {"hover": False, "done": False, "job": None, "imgs": []}
        self.copy_btn.bind("<Button-1>", lambda e: self._copy_title())
        self.copy_btn.bind("<Enter>", lambda e: self._paint_copy(hover=True))
        self.copy_btn.bind("<Leave>", lambda e: self._paint_copy(hover=False))
        self._paint_copy()
        self.tag = tk.Label(head, text="SAMPLE VIDEO", bg=C.CARD_HOVER, fg=C.MUTED,
                            font=(C.FONT, 8, "bold"), padx=8, pady=3)
        self.notice = tk.Label(head, text="", bg=C.BG, fg=C.MUTED, anchor="e",
                               font=(C.FONT, 9))
        self.notice.pack(side="right", padx=(16, 0))

        self.player = LessonPlayer(self, course["color"])
        self.player.on_notice = lambda text: self.notice.config(text=text)
        self.player.on_fullscreen = self._fullscreen
        self.player.pack(fill="both", expand=True, padx=28, pady=(0, 8))

        self.show_nav = show_nav   # False = trial: tanpa tombol Sebelumnya / Selanjutnya
        self.prev_btn = self.next_btn = None
        if not show_nav:   # baris tombol di bawah video dihilangkan, video jadi lebih besar
            self.player.no_footer = True
            self.player._foot = 0
            self.player.footer.pack_forget()
        if show_nav:
            self.prev_btn = self._nav_button("‹   Previous", "left", self.previous)
            self.next_btn = self._nav_button("Next   ›", "right", self.next)
        # Di antara tombol: catatan (dewasa) atau emote (SUPERKIDS), hanya murid terdaftar
        self.extra = None
        if show_nav and student_id:
            if program == "kids":
                self.extra = EmoteBar(self.player.footer, lambda: self.player.pos)
                self._extra_geom = (360, 56, 34)
            elif program == "adult":
                self.extra = NoteBox(self.player.footer)
                self._extra_geom = (560, 38, 31)
        if self.extra is not None:     # tepat di tengah bawah video (bukan di antara tombol)
            self.player.footer.bind("<Configure>", lambda e: self._place_extra(), add="+")
        self.player.on_resumed = self._resumed
        self._head_pad = None
        self.player.on_layout = self._align_head

        start = min(max(index, 0), max(len(items) - 1, 0))
        self.after(80, lambda: self.select(start, notify=False))   # tunggu jendela tampil (mpv)

    def _flush_progress(self):
        w, self._watching = getattr(self, "_watching", None), None
        if w is not None:
            progress.flush(*w)

    def destroy(self):
        self._cancel_quiz()
        try:
            self._flush_progress()     # keluar / pindah kursus: posisi terakhir ikut tersimpan
        except Exception as exc:
            C.log(f"Progres tidak tersimpan: {exc!r}")
        super().destroy()

    def _place_extra(self):
        """Catatan / emote dipusatkan pada lebar video; tidak menabrak tombol kiri-kanan."""
        f = self.player.footer
        fw = f.winfo_width()
        if fw < 100 or self.extra is None:
            return
        maxw, h, cy = self._extra_geom
        side = max(self.prev_btn.winfo_reqwidth(), self.next_btn.winfo_reqwidth())
        w = int(min(maxw, fw - 2 * side - 48))
        if w < 120:
            self.extra.place_forget()
            return
        self.extra.place(relx=0.5, y=cy, anchor="center", width=w, height=h)

    def _paint_copy(self, hover=None):
        st = self._copy_state
        if hover is not None:
            st["hover"] = hover
        c = self.copy_btn
        c.delete("all")
        st["imgs"] = []     # minimalis: tanpa kotak, hanya warna garis yang berubah
        col = C.TEXT if (st["hover"] or st["done"]) else C.MUTED
        ic = I.icon("check" if st["done"] else "copy", col, C.BG, 18)
        if ic is not None:
            st["imgs"].append(ic)
            c.create_image(15, 15, image=ic)

    def _copy_title(self):
        """Salin judul pelajaran ke clipboard (paste sebagai nama file di Blender)."""
        if not 0 <= self.index < len(self.items):
            return
        text = self.items[self.index]["title"]
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update_idletasks()
        except tk.TclError as exc:
            C.log(f"Salin judul gagal: {exc!r}")
            return
        st = self._copy_state
        st["done"] = True
        self.copy_lbl.config(text="Copied")
        self._paint_copy()
        if st["job"] is not None:
            self.after_cancel(st["job"])

        def reset():
            st["done"], st["job"] = False, None
            if self.winfo_exists():
                self.copy_lbl.config(text="")
                self._paint_copy()
        st["job"] = self.after(2500, reset)

    def _align_head(self, offset):
        """Judul & keterangan rata dengan tepi kiri / kanan video (bukan tepi halaman)."""
        pad = 28 + max(0, int(offset))
        if pad != self._head_pad and not self.player.fullscreen:
            self._head_pad = pad
            self.head.pack_configure(padx=pad)

    # --- progres, lanjut tonton, kuis --------------------------------------------------
    def _on_progress(self, key, pos, dur, ended):
        progress.update(*key, pos, dur, ended)
        if ended and not self._ended_seen:
            self._ended_seen = True
            self._want_quiz(delay=600)
            tracker = getattr(self.winfo_toplevel(), "badges", None)
            if tracker is not None:      # video selesai: badge Belajar dihitung ulang
                tracker.poke()
        elif not ended:
            self._ended_seen = False

    def _resumed(self, sec):
        if sec >= 3:
            self.notice.config(text=f"Resuming from {_fmt(sec)}")
            self.after(5000, lambda: self.winfo_exists()
                       and self.notice.config(text=self.player.notice))

    def _cancel_quiz(self):
        if self._quiz_job is not None:
            try:
                self.after_cancel(self._quiz_job)
            except Exception:
                pass
            self._quiz_job = None

    def _want_quiz(self, delay=600):
        self._cancel_quiz()
        self._quiz_job = self.after(delay, self._try_quiz)

    def _try_quiz(self):
        """Tampilkan kuis kalau ada; tunggu dulu kalau murid sedang di Blender / jendela lain."""
        self._quiz_job = None
        if not self.winfo_exists() or self._watching is None or self._quiz_open is not None:
            return
        sid, cid, title = self._watching
        try:
            items = quizzes.pending(sid, cid, title)
        except Exception as exc:
            C.log(f"Kuis tidak terbaca: {exc!r}")
            return
        if not items:
            return
        if not self.player._app_active() or self.player._fs_busy:
            self._quiz_job = self.after(800, self._try_quiz)    # cek lagi sebentar lagi
            return
        self.player._pause()
        self.player.blocked = True
        if self.player.ov is not None:
            self.player.ov.hide()

        def closed():
            self._quiz_open = None
            if self.winfo_exists():
                self.player.blocked = False
        try:
            self._quiz_open = QuizPopup(self, sid, items, title, on_close=closed)
        except Exception as exc:
            closed()
            C.log(f"Popup kuis gagal: {exc!r}")

    def _fullscreen(self, want):
        """Layar penuh: hanya pemutar yang tampil (judul disembunyikan, tepi dihapus)."""
        if want:
            self.head.pack_forget()
            self.player.pack_configure(padx=0, pady=0)
        else:
            self.player.pack_configure(padx=28, pady=(0, 8))
            self.head.pack(fill="x", padx=self._head_pad or 28, pady=(18, 10),
                           before=self.player)
        if self.on_fullscreen is not None:
            self.on_fullscreen(want)

    def _nav_button(self, text, side, command):
        btn = RoundButton(self.player.footer, text=text, command=command, relief="flat", bd=0,
                        highlightthickness=0, font=(C.FONT, 11, "bold"), padx=26, pady=9,
                        cursor="hand2")
        btn.pack(side=side, pady=(12, 8))
        return btn

    def _style_nav(self):
        if not self.show_nav:
            return
        last = len(self.items) - 1
        # Video pertama: tombol Sebelumnya disembunyikan (bukan sekadar abu-abu)
        if self.index <= 0:
            if self.prev_btn.winfo_ismapped() or self.prev_btn.winfo_manager():
                self.prev_btn.pack_forget()
        elif not self.prev_btn.winfo_manager():
            self.prev_btn.pack(side="left", pady=(12, 8))
        for btn, enabled, primary in ((self.prev_btn, self.index > 0, False),
                                      (self.next_btn, self.index < last, True)):
            if enabled:
                bg = self.course["color"] if primary else C.CARD_HOVER
                btn.config(state="normal", bg=bg, fg="#ffffff" if primary else C.TEXT,
                           activebackground=bg, activeforeground="#ffffff", cursor="hand2")
            else:
                btn.config(state="disabled", bg=C.CARD, disabledforeground=C.LOCKED,
                           cursor="arrow")

    def previous(self):
        self.select(self.index - 1)

    def next(self):
        self.select(self.index + 1)

    def select(self, index, notify=True):
        if not self.winfo_exists() or index == self.index:
            return
        if not 0 <= index < len(self.items):
            return
        self.index = index
        it = self.items[index]
        self.title.config(text=it["label"])
        if it["sample"]:
            self.tag.pack(side="left", padx=(12, 0))
        else:
            self.tag.pack_forget()
        hint = ""
        if not it["path"]:
            hint = (f"Video not available yet.\nPut {it['no']}.mp4 in the folder:\n"
                    f"{lessons.lesson_folder(self.course)}")
        self._flush_progress()
        self._cancel_quiz()
        if self.student_id:   # murid: video pembuka 3 detik dulu (trial tidak)
            self.player.load_with_intro(it["path"], hint, it.get("subs", ()))
        else:
            self.player.load(it["path"], hint, it.get("subs", ()))
        self.player.on_progress = None
        key = None
        if self.student_id and it["path"] and not it["sample"]:
            sid, cid, title = self.student_id, self.course["id"], it["title"]
            key = self._watching = (sid, cid, title)
            self._ended_seen = False
            try:
                start = progress.begin(sid, cid, title)
                self.player.resume_to(start)
                if progress.record(sid, cid, title).get("done"):
                    self._want_quiz(delay=1200)   # sudah pernah selesai: kuis yang belum dijawab
            except Exception as exc:
                C.log(f"Progres {sid}/{cid}: {exc!r}")
            self.player.on_progress = (lambda pos, dur, ended, k=key:
                                       self._on_progress(k, pos, dur, ended))
        if self.extra is not None:
            self.extra.set_lesson(key)
        if it["sample"]:   # tunjukkan folder yang dicari, supaya mudah dicek
            self.notice.config(text="No videos yet in: " + lessons.lesson_folder(self.course))
        else:
            self.notice.config(text=self.player.notice)
        self._style_nav()
        if notify and self.on_select is not None:
            self.on_select(index)
