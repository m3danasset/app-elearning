"""Dijalankan DI DALAM Blender (bukan addon, tidak dipasang):
    blender.exe --python reference_view.py -- <gambar1> [<gambar2> ...]

Gambar referensi dari guru dibuka di Image Editor di sebelah kiri 3D viewport (+-35 %).
Berlaku selama Blender itu terbuka: File > New / Open juga otomatis mendapat Image
Editor + gambar yang sama lagi (lewat handler load_post yang "persistent").
"""

import os
import sys

import bpy
from bpy.app.handlers import persistent

SPLIT = 0.35
PATHS = [p for p in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
         if os.path.isfile(p)]


def _images():
    out = []
    for p in PATHS:
        try:
            out.append(bpy.data.images.load(p, check_existing=True))
        except Exception as exc:
            print(f"[referensi] gagal memuat {p!r}: {exc!r}")
    return out


def _window_region(area):
    return next((r for r in area.regions if r.type == "WINDOW"), None)


def _setup():
    imgs = _images()
    if not imgs:
        return None
    wm = bpy.context.window_manager
    for window in wm.windows:
        screen = window.screen
        ed = next((a for a in screen.areas if a.type == "IMAGE_EDITOR"), None)
        if ed is None:
            views = [a for a in screen.areas if a.type == "VIEW_3D"]
            if not views:
                continue
            view = max(views, key=lambda a: a.width * a.height)
            before = set(screen.areas)
            region = _window_region(view)
            try:
                with bpy.context.temp_override(window=window, screen=screen, area=view,
                                               region=region):
                    bpy.ops.screen.area_split(direction="VERTICAL", factor=SPLIT)
            except Exception as exc:
                print(f"[referensi] gagal membelah area: {exc!r}")
                continue
            new = [a for a in screen.areas if a not in before]
            if not new:
                continue
            pair = sorted([view, new[0]], key=lambda a: a.x)
            ed, view3d = pair[0], pair[1]          # kiri = gambar, kanan = 3D viewport
            view3d.type = "VIEW_3D"
            ed.type = "IMAGE_EDITOR"
        space = ed.spaces.active
        space.image = imgs[0]
        try:
            with bpy.context.temp_override(window=window, screen=screen, area=ed,
                                           region=_window_region(ed)):
                bpy.ops.image.view_all(fit_view=True)
        except Exception:
            pass
    return None      # timer sekali jalan


@persistent
def _on_load(_dummy):
    bpy.app.timers.register(_setup, first_interval=0.3)


if PATHS:
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)
    bpy.app.timers.register(_setup, first_interval=0.5)   # tunggu UI Blender siap
