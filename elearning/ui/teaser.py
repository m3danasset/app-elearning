"""Video teaser kursus di Dashboard murid (course_dock, hero): kartu video besar di atas sapaan
yang hanya muncul saat kursor di atas kartu kursus.

- Video: assets\\video\\teaser\\<id kursus>.mp4 (nama folder / judul kursus juga boleh), kalau
  tidak ada -> berkas pertama yang namanya diawali "teaser" (sampel 8 detik). Tanpa suara, diulang.
- Resolusi pratinjau maks. 720p (MAX_W x MAX_H): frame dari video apa pun diperkecil di thread
  ke ukuran kartu (<= 1280x720). Video teaser sebaiknya juga <= 720p supaya decode ringan.
- Dibaca & diperkecil di thread (VideoPlayer, OpenCV) -> frame RGB. course_dock mencampurnya
  dengan latar + bayangan + sudut bulat jadi SATU gambar RGB solid (Tk menempel RGB jauh lebih
  cepat daripada gambar bertransparansi). Pudar dihitung tiap frame UI (30 fps).
"""

import os

from elearning import config as C
from elearning.ui import ui_icons as I

TEASER_DIR = os.path.join(C.APP_DIR, "assets", "video", "teaser")
EXTS = (".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm")
RADIUS = 18
MAX_W, MAX_H = 1280, 720          # batas resolusi pratinjau (720p)


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


def make_player(path, fps, w, h):
    """Pemutar teaser di thread (None kalau OpenCV tidak ada). Frame = RGB w x h (<= 720p,
    diperkecil di thread); .mask = sudut bulat (L) untuk dicampur di thread utama."""
    from elearning.ui import video_background as VB
    if not VB.HAS_VIDEO:
        return None
    w, h = min(int(w), MAX_W), min(int(h), MAX_H)

    class TeaserPlayer(VB.VideoPlayer):
        mask = None                    # masker sudut bulat ukuran target (L), dipakai thread utama

        def set_target(self_, tw, th):
            tw, th = min(int(tw), MAX_W), min(int(th), MAX_H)
            self_.mask = I.round_mask(tw, th, RADIUS).copy()
            self_.set_size(tw, th)

    p = TeaserPlayer(path, dim=1.0, max_fps=fps)
    p.set_target(w, h)
    return p
