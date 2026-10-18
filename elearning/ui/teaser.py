"""Video teaser kursus di Dashboard murid (course_dock, hero): kartu video kecil-sedang di atas
sapaan yang hanya muncul saat kursor di atas kartu kursus.

- Video: assets\\video\\teaser\\<id kursus>.mp4 (nama folder / judul kursus juga boleh), kalau
  tidak ada -> berkas pertama yang namanya diawali "teaser" (sampel 8 detik). Tanpa suara, diulang.
- Dibaca & diperkecil di thread (VideoPlayer, OpenCV), frame RGBA sudah bersudut bulat dan
  ber-alpha (pudar masuk / keluar) supaya thread utama hanya menempel ke PhotoImage.
"""

import os

from elearning import config as C
from elearning import photos
from elearning.ui import ui_icons as I

TEASER_DIR = os.path.join(C.APP_DIR, "assets", "video", "teaser")
EXTS = (".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm")
RADIUS = 16


def _norm(text):
    return "".join(ch for ch in str(text).lower() if ch.isalnum())


def teaser_path(course):
    """Video teaser kursus ini, atau sampel umum, atau None."""
    try:
        names = sorted(n for n in os.listdir(TEASER_DIR)
                       if n.lower().endswith(EXTS) and not n.startswith("."))
    except OSError:
        return None
    want = {_norm(course.get("id", "")), _norm(course.get("title", ""))}
    for n in names:
        if _norm(os.path.splitext(n)[0]) in want:
            return os.path.join(TEASER_DIR, n)
    for n in names:
        if n.lower().startswith("teaser"):
            return os.path.join(TEASER_DIR, n)
    return None


def make_player(path, fps):
    """Pemutar teaser di thread (None kalau OpenCV tidak ada). .alpha = tingkat tampil 0..1."""
    from elearning.ui import video_background as VB
    if not VB.HAS_VIDEO:
        return None
    Image = photos.Image

    class TeaserPlayer(VB.VideoPlayer):
        alpha = 0.0
        mask = None                    # masker sudut bulat ukuran target (dibuat thread utama)

        def set_target(self_, w, h):
            self_.set_size(w, h)
            self_.mask = I.round_mask(w, h, RADIUS).copy()

        def _prepare(self_, frame):
            img = VB.VideoPlayer._prepare(self_, frame).convert("RGBA")
            m = self_.mask
            if m is None or m.size != img.size:
                return None
            a = max(0.0, min(1.0, self_.alpha))
            img.putalpha(m if a >= 0.999 else m.point(lambda v: int(v * a)))
            return img

    p = TeaserPlayer(path, dim=1.0, max_fps=fps)
    return p
