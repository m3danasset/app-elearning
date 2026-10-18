"""Latar video yang berputar terus (loop), dipakai di layar login.

- Video dicari otomatis di folder assets/video (lihat config.VIDEO_DIR).
- Video diputar di thread terpisah supaya jendela tetap responsif.
- Kalau video tidak ada / gagal dibuka, latar jadi warna polos (aplikasi tetap jalan).
"""

import os
import threading
import time
import tkinter as tk
from datetime import datetime

from elearning import config as C

try:
    import cv2
    from PIL import Image, ImageTk
    try:    # OpenCV default memakai SEMUA core: batasi supaya Blender tidak terganggu
        cv2.setNumThreads(C.WORKER_THREADS)
    except Exception:
        pass
    HAS_VIDEO = True
    IMPORT_ERROR = ""
except Exception as exc:  # opencv / pillow belum terpasang
    HAS_VIDEO = False
    IMPORT_ERROR = repr(exc)

VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v")


def log(msg):
    """Catat masalah ke app.log di samping aplikasi (berguna saat jalan sebagai .exe)."""
    try:
        with open(C.LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}\n")
    except OSError:
        pass


def find_video(folder):
    """Video pertama (urut abjad) di folder, atau None kalau tidak ada / mode ringan
    (config.lite: semua video latar mati, latar polos)."""
    if C.lite():
        return None
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return None
    for name in names:
        if name.lower().endswith(VIDEO_EXTS) and not name.startswith("."):
            return os.path.join(folder, name)
    return None


class VideoPlayer(threading.Thread):
    """Membaca video terus-menerus dan menyiapkan frame terbaru (sudah pas ukuran jendela)."""

    def __init__(self, path, dim=0.5, max_fps=30):
        super().__init__(daemon=True)
        self.path = path
        self.dim = dim
        self.max_fps = max_fps
        self.failed = False
        self.error = ""
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._size = (960, 600)
        self._latest = None

    # --- dipanggil dari thread utama ---
    def set_size(self, width, height):
        with self._lock:
            self._size = (max(2, int(width)), max(2, int(height)))

    def get_latest(self):
        with self._lock:
            img, self._latest = self._latest, None
        return img

    def stop(self):
        self._stop_event.set()

    # --- berjalan di thread sendiri ---
    def run(self):
        cap = cv2.VideoCapture(self.path)
        try:
            if not cap.isOpened():
                self._fail("Video tidak bisa dibuka (format/codec tidak didukung?)")
                return

            src_fps = cap.get(cv2.CAP_PROP_FPS)
            if not src_fps or src_fps != src_fps or src_fps < 1 or src_fps > 240:
                src_fps = 30.0
            # Kalau video 60 fps, lewati sebagian frame agar kecepatan tetap normal
            step = max(1, round(src_fps / self.max_fps))
            interval = step / src_fps

            while not self._stop_event.is_set():
                t0 = time.perf_counter()

                for _ in range(step - 1):
                    cap.grab()
                ok, frame = cap.read()
                if not ok:  # sampai akhir -> ulang dari awal
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, frame = cap.read()
                    if not ok:
                        self._fail("Video kosong / rusak")
                        return

                img = self._prepare(frame)
                with self._lock:
                    self._latest = img

                wait = interval - (time.perf_counter() - t0)
                if wait > 0:
                    self._stop_event.wait(wait)
        except Exception as exc:
            self._fail(repr(exc))
        finally:
            cap.release()

    def _fail(self, message):
        self.failed = True
        self.error = message

    def _prepare(self, frame):
        """Perbesar/kecilkan agar menutupi seluruh jendela (cover), potong tengah, gelapkan."""
        with self._lock:
            tw, th = self._size
        h, w = frame.shape[:2]
        scale = max(tw / w, th / h)
        nw = max(tw, int(w * scale + 0.5))
        nh = max(th, int(h * scale + 0.5))
        interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
        frame = cv2.resize(frame, (nw, nh), interpolation=interp)
        x0, y0 = (nw - tw) // 2, (nh - th) // 2
        frame = frame[y0:y0 + th, x0:x0 + tw]
        if self.dim < 1.0:
            frame = cv2.convertScaleAbs(frame, alpha=self.dim)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(frame)


class VideoBackground(tk.Canvas):
    """Canvas yang menampilkan video sebagai latar. Pasang dengan .place(relwidth=1, relheight=1)."""

    def __init__(self, master, path, dim=0.5, fallback_bg="#000000"):
        super().__init__(master, bg=fallback_bg, highlightthickness=0, bd=0)
        self._image_item = self.create_image(0, 0, anchor="nw")
        self._photo = None
        self._player = None
        self._job = None

        if not path:
            log(f"Tidak ada video di folder: {C.VIDEO_DIR} -> pakai latar polos")
            return
        if not HAS_VIDEO:
            log(f"opencv/pillow tidak tersedia ({IMPORT_ERROR}) -> pakai latar polos")
            return

        self._player = VideoPlayer(path, dim=dim)
        self.bind("<Configure>", self._on_resize)
        self._player.start()
        self._tick()

    def _on_resize(self, event):
        self._player.set_size(event.width, event.height)

    def _tick(self):
        img = self._player.get_latest()
        if img is not None:
            try:
                self._photo = ImageTk.PhotoImage(img)  # simpan referensi agar tidak hilang
                self.itemconfig(self._image_item, image=self._photo)
            except Exception as exc:
                log(f"Gagal menampilkan frame video: {exc!r} -> pakai latar polos")
                self._player.stop()
                return
        if self._player.failed:
            log(f"Video gagal diputar: {self._player.error}")
            return
        self._job = self.after(C.UI_FRAME_MS, self._tick)   # video maks. 30 fps

    def destroy(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        if self._player is not None:
            self._player.stop()
        super().destroy()
