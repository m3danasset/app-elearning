"""
Blender E-Learning - titik masuk aplikasi.
Jalankan:  python main.py

Update tanpa build ulang: kalau .exe punya folder  app\\elearning  di sampingnya,
kode di folder itu dipakai menggantikan kode yang ada di dalam .exe.
Kalau kode di folder itu rusak, otomatis dipakai kode bawaan .exe
dan penyebabnya dicatat di app.log.
"""

import os
import sys
import traceback
from datetime import datetime


def _base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _log(msg):
    try:
        with open(os.path.join(_base_dir(), "app.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}\n")
    except OSError:
        pass


def _load_app_class():
    external = os.path.join(_base_dir(), "app")
    use_external = (getattr(sys, "frozen", False)
                    and os.path.isdir(os.path.join(external, "elearning")))

    if use_external:
        sys.path.insert(0, external)
        try:
            from elearning.ui.window import App
            return App
        except Exception:
            _log("Kode di folder 'app' gagal dimuat, memakai kode bawaan .exe:\n"
                 + traceback.format_exc())
            sys.path.remove(external)
            for name in [m for m in sys.modules
                         if m == "elearning" or m.startswith("elearning.")]:
                del sys.modules[name]

    from elearning.ui.window import App
    return App


def main():
    _load_app_class()().mainloop()


if __name__ == "__main__":
    main()
