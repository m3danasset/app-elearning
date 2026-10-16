"""Memuat python-mpv + libmpv-2.dll: pemutar video BERSUARA dan ber-SUBTITLE di dalam aplikasi.

libmpv adalah pustaka (bukan aplikasi pemutar): video tampil di dalam jendela aplikasi ini,
tidak ada jendela VLC/mpv yang terbuka.

Yang dibutuhkan:
  - python-mpv   : pip install python-mpv   (satu file mpv.py)
  - libmpv-2.dll : taruh di samping .exe (dist\\) atau di folder proyek (build mpv-dev x86_64)

Kalau salah satunya tidak ada, aplikasi tetap jalan memakai pemutar cadangan OpenCV
(tanpa suara dan tanpa subtitle), dan alasannya dicatat di app.log.
"""

import os

from elearning import config as C

DLL_NAMES = ("libmpv-2.dll", "mpv-2.dll", "libmpv.dll", "mpv-1.dll")

ERROR = ""
DLL_FOUND = False   # libmpv-2.dll ditemukan di salah satu folder yang dicek
_module = None
_tried = False


def _dirs():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # folder induk 'elearning'
    found = []
    for d in (C.APP_DIR, os.path.join(C.APP_DIR, "app"), os.path.join(C.APP_DIR, "lib"),
              here, os.path.dirname(here)):
        if d and os.path.isdir(d) and d not in found:
            found.append(d)
    return found


def reason():
    """Alasan singkat (untuk ditampilkan ke pengguna) kenapa suara & subtitle belum aktif."""
    if not DLL_FOUND:
        return "libmpv-2.dll tidak ditemukan di samping .exe"
    if "No module named 'mpv'" in ERROR:
        return "mpv.py tidak ada di folder app (jalankan update.bat)"
    return ERROR[:110] or "sebab tidak diketahui"


def get():
    """Modul mpv yang siap dipakai, atau None (alasannya ada di ERROR)."""
    global _module, _tried, ERROR, DLL_FOUND
    if _tried:
        return _module
    _tried = True
    for d in _dirs():
        if any(os.path.exists(os.path.join(d, n)) for n in DLL_NAMES):
            DLL_FOUND = True
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            try:
                os.add_dll_directory(d)
            except Exception:
                pass
    try:
        import locale
        locale.setlocale(locale.LC_NUMERIC, "C")    # syarat libmpv
    except Exception:
        pass
    try:
        import mpv
        _module = mpv
    except Exception as exc:
        ERROR = repr(exc)
        C.log(f"Pemutar mpv tidak aktif (pakai OpenCV tanpa suara): {ERROR} "
              f"dll_ditemukan={DLL_FOUND} folder_dicek={_dirs()!r}")
    return _module
