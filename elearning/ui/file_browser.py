"""File browser minimalis untuk murid, gaya search palette (Ctrl+K).

Dua mode:
  "pick"     : pilih gambar / video dari PC untuk diupload ke Portfolio / Assignment.
               Tab = tempat (Desktop, Dokumen, Unduhan, Gambar, Video, render Blender,
               flashdisk, drive). Klik file = centang (boleh banyak), lalu "Upload".
  "resource" : lihat resource kursus (assets\\resources\\<kursus>), hanya baca.
               Tab = jenis file. Klik dua kali / Enter = buka; centang + "Simpan ke
               flashdisk".

Dua tampilan (diingat selama aplikasi terbuka): Details (daftar: nama, tanggal, ukuran)
dan Small thumbnails (kisi gambar kecil).

Ringan untuk PC low-end: isi folder dan thumbnail dibaca di thread (maks.
config.WORKER_THREADS), hanya thumbnail yang terlihat yang dibuat, hasilnya disimpan di
memori (terbatas). Daftar digambar per baris/sel yang terlihat. Tk hanya dari thread utama.
"""

import collections
import os
import re
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime

from elearning import config as C
from elearning import photos, portfolio
from elearning.ui import ui_icons as I
from elearning.ui.search_palette import FOOT_H, OverlayPanel, _fit, _font, _keycap, open_overlay

PANEL_W, PANEL_H = 820, 580
LIST_TOP = 112
HEAD_H = 28                  # judul kolom (Details)
ROW_H = 34                   # baris Details
CELL_W, CELL_H = 128, 118    # sel Small thumbnails
TW, TH = 112, 74             # ukuran thumbnail
POLL_MS = C.UI_FRAME_MS      # hasil thread diambil maks. 1x per frame (30 fps)
THUMB_CACHE = 400            # thumbnail di memori (~23 KB per gambar)
DRIVES = "::drives"          # folder semu: daftar drive
WIN = sys.platform == "win32"

_state = {"view": "thumbs", "last_pick": None}
_thumbs = collections.OrderedDict()   # (path, mtime) -> gambar PIL (RGB, TW x TH)
_thumbs_lock = threading.Lock()


def _natural(name):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def _kind(name):
    k = portfolio.kind_of(name)
    return k or "file"


def _norm(path):
    return os.path.normcase(os.path.normpath(path)) if path and path != DRIVES else path


# --- tempat (mode pick) ------------------------------------------------------------------
def _roots():
    """Drive yang BOLEH dibuka murid: drive lokal murid (config.STUDENT_DRIVE, mis. Z:)
    dan flashdisk yang tercolok. [(label, path)]"""
    out = []
    z = getattr(C, "STUDENT_DRIVE", "Z:\\")
    if z and os.path.isdir(z):
        out.append((f"Local ({os.path.splitdrive(z)[0] or z.rstrip(os.sep)})", z))
    try:
        from elearning.ui.usb_save import removable_drives
        for d in removable_drives():
            out.append((f"Flashdisk {d[:2]}", d))
    except Exception:
        pass
    return out


def _inside(path, roots):
    """True kalau path DAN tujuan aslinya (shortcut folder / junction) ada di dalam salah
    satu drive yang diizinkan."""
    def ok(p):
        p = _norm(p)
        for _label, r in roots:
            rn = _norm(r).rstrip("\\/")
            if p == rn or p == _norm(r) or p.startswith(rn + os.sep):
                return True
        return False
    try:
        real = os.path.realpath(path)
    except OSError:
        return False
    return bool(roots) and ok(path) and ok(real)


def _places():
    return _roots()


def _drives():
    return [{"name": label, "path": p, "is_dir": True, "kind": "folder", "size": 0,
             "mtime": 0} for label, p in _roots()]


# --- kerja di thread ------------------------------------------------------------------------
def _list_dir(path, exts):
    if path == DRIVES:
        return _drives()
    out = []
    with os.scandir(path) as it:
        for e in it:
            name = e.name
            if name.startswith((".", "~$", "$")) or name in ("_thumbs", "desktop.ini",
                                                              "thumbs.db", "Thumbs.db"):
                continue
            try:
                is_dir = e.is_dir()
                st = e.stat()
            except OSError:
                continue
            if getattr(st, "st_file_attributes", 0) & 0x6:   # Windows: tersembunyi / sistem
                continue
            if not is_dir and exts and not name.lower().endswith(exts):
                continue
            out.append({"name": name, "path": e.path, "is_dir": is_dir,
                        "kind": "folder" if is_dir else _kind(name),
                        "size": 0 if is_dir else st.st_size, "mtime": st.st_mtime})
    out.sort(key=lambda d: (not d["is_dir"], _natural(d["name"])))
    return out


def _make_thumb(path, kind):
    """Gambar TW x TH (RGB) atau None. Berjalan di thread kerja."""
    Image = photos.Image
    img = None
    if kind == "image":
        with Image.open(path) as f:
            try:
                f.draft("RGB", (TW * 2, TH * 2))   # JPEG besar: dibaca kecil (cepat)
            except Exception:
                pass
            f.load()
            img = photos._flatten(photos._fix_orientation(f))
    elif kind == "video":
        img = portfolio._video_frame(path)
    if img is None:
        return None
    img = portfolio._cover(img.convert("RGB"), TW, TH)
    if kind == "video":       # tanda video: lingkaran gelap + segitiga putih, halus
        d = 26
        x, y = (TW - d) // 2, (TH - d) // 2
        img.paste((0, 0, 0), (x, y), I.round_mask(d, d, d / 2).point(lambda v: v * 150 // 255))
        tri = I._render_icon("play_fill", "#ffffff", "#000000", 14).convert("L")
        img.paste((255, 255, 255), (x + 7, y + 6), tri)
    return img


class _Loader:
    """Antrian kerja kecil: isi folder lebih dulu, lalu thumbnail (yang terbaru diminta
    dikerjakan dulu, jadi yang sedang terlihat cepat muncul)."""

    def __init__(self):
        self.cond = threading.Condition()
        self.lists = []                      # (token, path, exts)
        self.thumbs = collections.OrderedDict()   # key -> (path, kind)
        self.results = []                    # ("list", token, path, entries|exc) / ("thumb", key)
        self.stop = False
        self.threads = []
        for _ in range(max(1, min(2, getattr(C, "WORKER_THREADS", 1)))):
            t = threading.Thread(target=self._run, daemon=True)
            t.start()
            self.threads.append(t)

    def list_dir(self, token, path, exts):
        with self.cond:
            self.lists = [(token, path, exts)]
            self.thumbs.clear()              # folder lama: thumbnail tidak perlu lagi
            self.cond.notify()

    def want_thumb(self, key, path, kind):
        with self.cond:
            if key in self.thumbs:
                self.thumbs.move_to_end(key)
            else:
                self.thumbs[key] = (path, kind)
            self.cond.notify()

    def pending(self):
        with self.cond:
            return bool(self.lists or self.thumbs or self.results) or any(
                getattr(t, "_busy", False) for t in self.threads)

    def take(self):
        with self.cond:
            out, self.results = self.results, []
            return out

    def close(self):
        with self.cond:
            self.stop = True
            self.lists, self.thumbs = [], collections.OrderedDict()
            self.cond.notify_all()

    def _run(self):
        me = threading.current_thread()
        while True:
            with self.cond:
                while not self.stop and not self.lists and not self.thumbs:
                    self.cond.wait()
                if self.stop:
                    return
                if self.lists:
                    job = ("list",) + self.lists.pop(0)
                else:
                    key, (path, kind) = self.thumbs.popitem(last=True)
                    job = ("thumb", key, path, kind)
                me._busy = True
            try:
                if job[0] == "list":
                    _tok, token, path, exts = job
                    try:
                        res = _list_dir(path, exts)
                    except Exception as exc:
                        res = exc
                    with self.cond:
                        self.results.append(("list", token, path, res))
                else:
                    _t, key, path, kind = job
                    try:
                        img = _make_thumb(path, kind)
                    except Exception as exc:
                        C.log(f"File browser: thumbnail {path!r} gagal: {exc!r}")
                        img = None
                    with _thumbs_lock:
                        _thumbs[key] = img
                        while len(_thumbs) > THUMB_CACHE:
                            _thumbs.popitem(last=False)
                    with self.cond:
                        self.results.append(("thumb", key))
            finally:
                me._busy = False


# --- jendela -------------------------------------------------------------------------------
def open_file_browser(widget, **opts):
    """Buka file browser di atas jendela widget. Lihat FileBrowser._build untuk opts."""
    return open_overlay(FileBrowser, widget.winfo_toplevel(), opts)


class FileBrowser(OverlayPanel):
    def _focus_target(self):
        return self.list

    def _build(self, top, opts):
        self.mode = opts.get("mode", "pick")
        self.pick = self.mode == "pick"
        self.title = opts.get("title", "")
        self.exts = tuple(opts.get("exts") or ()) or None
        self.root = opts.get("root")            # resource: tidak bisa naik di atas folder ini
        self.on_pick = opts.get("on_pick")
        self.on_save = opts.get("on_save")
        self.on_open = opts.get("on_open")
        self.view = _state["view"]
        self.entries = []        # isi folder (semua)
        self.shown = []          # isi setelah saringan tab (resource)
        self.checked = {}        # path -> entry
        self.sel = -1
        self.offset = 0
        self.total_h = 0
        self.history = []
        self.cur = None
        self.token = 0
        self.error = None
        self.loading = False
        self._load_t0 = 0.0
        self._poll_job = None
        self._photos = {}        # (key, bg) -> PhotoImage (dibuang saat ditutup)
        self._hover = None       # nama tombol di bawah kursor
        self._boxes = []         # (x0, y0, x1, y1, nama, data) untuk klik di kerangka
        self._f_title = tkfont.Font(font=_font(11, "bold"))
        self._f_crumb = tkfont.Font(font=_font(11))
        self._f_tab = tkfont.Font(font=_font(10))
        self._f_tab_b = tkfont.Font(font=_font(10, "bold"))
        self._f_row = tkfont.Font(font=_font(10))
        self._f_sub = tkfont.Font(font=_font(9))
        self._f_cell = tkfont.Font(font=_font(9))
        self._f_key = tkfont.Font(font=_font(8))
        self._f_btn = tkfont.Font(font=_font(10, "bold"))

        if self.pick:
            self.tabs = [(p, label) for label, p in _places()]
            start = opts.get("start") or _state["last_pick"]
            if not start or not os.path.isdir(start) or not _inside(start, self.tabs_roots()):
                start = self.tabs[0][0] if self.tabs else DRIVES
        else:
            self.tabs = [("all", "Semua"), ("image", "Gambar"), ("video", "Video"),
                         ("file", "Lainnya")]
            self.filter = "all"
            start = self.root

        self._make_window(top, PANEL_W, PANEL_H, min_w=560, min_h=380)
        self.lw, self.lh = self.W - 24, self.H - LIST_TOP - FOOT_H - 4
        self.list = tk.Canvas(self.cv, width=self.lw, height=self.lh, bg=C.CARD,
                              highlightthickness=0, bd=0, takefocus=1)
        self.list._imgs = []
        self.cv.create_window(12, LIST_TOP, anchor="nw", window=self.list)
        self.loader = _Loader()
        self._bind_keys()
        self._go(start, remember=False)
        self._draw_frame()
        self._reveal()

    def _on_close(self):
        self.loader.close()
        if self._poll_job is not None:
            try:
                self.after_cancel(self._poll_job)
            except Exception:
                pass
        self._photos.clear()

    # --- tombol & mouse -------------------------------------------------------------------
    def _bind_keys(self):
        b = self.bind
        b("<Escape>", lambda e: self.close())
        b("<Return>", lambda e: self._activate(self.sel))
        b("<KP_Enter>", lambda e: self._activate(self.sel))
        b("<space>", lambda e: self._toggle(self.sel))
        b("<BackSpace>", lambda e: self._up())
        b("<Alt-Left>", lambda e: self._back())
        b("<Alt-Up>", lambda e: self._up())
        b("<Up>", lambda e: self._move(0, -1))
        b("<Down>", lambda e: self._move(0, 1))
        b("<Left>", lambda e: self._move(-1, 0))
        b("<Right>", lambda e: self._move(1, 0))
        b("<Prior>", lambda e: self._move(0, -6))
        b("<Next>", lambda e: self._move(0, 6))
        b("<Home>", lambda e: self._select(0, scroll=True))
        b("<End>", lambda e: self._select(len(self.shown) - 1, scroll=True))
        b("<Tab>", lambda e: self._switch_tab(1))
        b("<Shift-Tab>", lambda e: self._switch_tab(-1))
        b("<ISO_Left_Tab>", lambda e: self._switch_tab(-1))
        b("<Control-a>", lambda e: self._check_all())
        b("<Control-A>", lambda e: self._check_all())
        self.bind("<Button-1>", self._click_any, add="+")
        self.cv.bind("<Motion>", self._frame_motion)
        self.cv.bind("<Leave>", lambda e: self._frame_motion(None))
        L = self.list
        L.bind("<Motion>", self._list_motion)
        L.bind("<Button-1>", self._list_click)
        L.bind("<Double-Button-1>", self._list_double)
        for w in (L, self.cv):
            w.bind("<MouseWheel>", lambda e: self._scroll(-1 if e.delta > 0 else 1))
            w.bind("<Button-4>", lambda e: self._scroll(-1))
            w.bind("<Button-5>", lambda e: self._scroll(1))

    def _click_any(self, e):
        x0, y0 = self.winfo_rootx(), self.winfo_rooty()
        if not (x0 <= e.x_root < x0 + self.W and y0 <= e.y_root < y0 + self.H):
            self.close()      # klik di luar panel
            return
        if e.widget is not self.cv:
            return
        if self._on_close_button(e.x, e.y):
            self.close()
            return
        for bx0, by0, bx1, by1, name, data in self._boxes:
            if bx0 <= e.x < bx1 and by0 <= e.y < by1:
                self._press(name, data)
                return
        self.list.focus_set()

    def _frame_motion(self, e):
        hover = None
        if e is not None:
            if self._on_close_button(e.x, e.y):
                hover = ("close", None)
            for bx0, by0, bx1, by1, name, data in self._boxes:
                if bx0 <= e.x < bx1 and by0 <= e.y < by1:
                    hover = (name, data)
        if hover != self._hover:
            self._hover = hover
            self._draw_frame()
            ok = hover is not None and not (hover[0] == "primary" and not self._primary_ok())
            self.cv.config(cursor="hand2" if ok else "")

    def _press(self, name, data):
        if name == "back":
            self._back()
        elif name == "up":
            self._up()
        elif name == "crumb":
            self._go(data)
        elif name == "tab":
            self._set_tab(data)
        elif name == "view":
            self._set_view(data)
        elif name == "primary":
            self._primary()
        elif name == "secondary":
            self._secondary()
        self.list.focus_set()

    # --- navigasi -------------------------------------------------------------------------
    def tabs_roots(self):
        return [(label, p) for p, label in self.tabs]

    def _go(self, path, remember=True):
        if path is None:
            return
        if self.pick and path != DRIVES:
            roots = _roots()            # flashdisk bisa dicabut / dicolok kapan saja
            if not _inside(path, roots):
                C.log(f"File browser: akses ditolak {path!r}")
                return                  # murid hanya boleh drive lokal murid & flashdisk
        if remember and self.cur is not None and _norm(path) != _norm(self.cur):
            self.history.append(self.cur)
        self.cur = path
        self.token += 1
        self.error = None
        self.loading = True
        self._load_t0 = time.perf_counter()
        self.loader.list_dir(self.token, path, self.exts if self.pick else None)
        self._poll()
        self._draw_frame()
        self._draw_list()

    def _back(self):
        if self.history:
            path = self.history.pop()
            self._go(path, remember=False)
            self._draw_frame()

    def _parent(self):
        cur = self.cur
        if cur in (None, DRIVES):
            return None
        if not self.pick and _norm(cur) == _norm(self.root):
            return None                       # resource: tidak naik di atas folder kursus
        parent = os.path.dirname(os.path.normpath(cur))
        if not parent or _norm(parent) == _norm(cur):
            return DRIVES if self.pick else None
        if self.pick and not _inside(parent, _roots()):
            return DRIVES               # di atas akar drive murid: daftar drive yang boleh
        return parent

    def _up(self):
        p = self._parent()
        if p is not None:
            self._go(p)

    def _set_tab(self, key):
        if self.pick:
            self._go(key)
        elif key != self.filter:
            self.filter = key
            self._apply_filter()
        self._draw_frame()

    def _switch_tab(self, step):
        keys = [k for k, _ in self.tabs]
        if not keys:
            return "break"
        cur = self._active_tab()
        i = keys.index(cur) if cur in keys else -1
        self._set_tab(keys[(i + step) % len(keys)])
        return "break"

    def _active_tab(self):
        if not self.pick:
            return self.filter
        cur = _norm(self.cur)
        best, blen = None, -1
        for key, _label in self.tabs:
            k = _norm(key)
            if cur == k or (key != DRIVES and cur and k and
                            cur.startswith(k.rstrip("\\/") + os.sep)):
                if len(k) > blen:
                    best, blen = key, len(k)
        return best

    def _set_view(self, view):
        if view != self.view:
            self.view = _state["view"] = view
            self.offset = 0
            self._layout()
            self._ensure_visible(self.sel)
            self._draw_frame()
            self._draw_list()

    # --- isi folder -----------------------------------------------------------------------
    def _poll(self):
        """Ambil hasil thread (maks. 1x per frame). Berhenti sendiri kalau tidak ada kerja."""
        self._poll_job = None
        if self._closed:
            return
        redraw = False
        for res in self.loader.take():
            if res[0] == "list":
                _k, token, path, data = res
                if token != self.token:
                    continue
                self.loading = False
                if isinstance(data, Exception):
                    C.log(f"File browser: {path!r} tidak bisa dibuka: {data!r}")
                    self.error = "Folder ini tidak bisa dibuka."
                    self.entries = []
                else:
                    if self.pick and path != DRIVES:   # shortcut ke luar drive murid: sembunyi
                        roots = _roots()
                        data = [e for e in data if not e["is_dir"] or _inside(e["path"], roots)]
                    self.entries = data
                self.offset = 0
                self._apply_filter(draw=False)
                self.sel = 0 if self.shown else -1
                if self.pick and path != DRIVES:
                    _state["last_pick"] = path
                self._draw_frame()
                redraw = True
            else:
                redraw = True
        if self.loading and time.perf_counter() - self._load_t0 > 0.2:
            redraw = True        # folder lambat (flashdisk / disk tidur): tampilkan "Memuat…"
        if redraw:
            self._draw_list()
        if self.loading or self.loader.pending():
            self._poll_job = self.after(POLL_MS, self._poll)

    def _apply_filter(self, draw=True):
        if self.pick or self.filter == "all":
            self.shown = list(self.entries)
        else:
            self.shown = [e for e in self.entries if e["is_dir"] or e["kind"] == self.filter]
        self.sel = min(self.sel, len(self.shown) - 1)
        self._layout()
        if draw:
            self.offset = 0
            self._draw_list()

    def _layout(self):
        n = len(self.shown)
        if self.view == "details":
            self.cols = 1
            self.total_h = HEAD_H + n * ROW_H + 8
        else:
            self.cols = max(1, (self.lw - 8) // CELL_W)
            rows = (n + self.cols - 1) // self.cols
            self.total_h = rows * CELL_H + 12

    def _item_box(self, i):
        """(x0, y0, x1, y1) item i dalam koordinat virtual daftar."""
        if self.view == "details":
            y = HEAD_H + i * ROW_H
            return 4, y, self.lw - 10, y + ROW_H
        pad = (self.lw - 8 - self.cols * CELL_W) // 2 + 4
        r, c = divmod(i, self.cols)
        x, y = pad + c * CELL_W, 6 + r * CELL_H
        return x, y, x + CELL_W, y + CELL_H

    def _item_at(self, x, y):
        vy = y + self.offset
        for i in self._visible_range():
            x0, y0, x1, y1 = self._item_box(i)
            if x0 <= x < x1 and y0 <= vy < y1:
                return i
        return -1

    def _visible_range(self):
        n = len(self.shown)
        if n == 0:
            return range(0)
        if self.view == "details":
            a = max(0, (self.offset - HEAD_H) // ROW_H)
            b = min(n, (self.offset + self.lh - HEAD_H) // ROW_H + 2)
        else:
            a = max(0, (self.offset // CELL_H) * self.cols)
            b = min(n, ((self.offset + self.lh) // CELL_H + 1) * self.cols)
        return range(a, b)

    # --- gambar: kerangka -----------------------------------------------------------------
    def _btn(self, cv, x, y, w, h, name, data, fill, bg, icon=None, text=None, fg=C.TEXT,
             font=None, border=None, r=8):
        hover = self._hover == (name, data)
        if hover and fill == bg:
            fill = C.CARD_HOVER
        if fill != bg or border:
            p = I.pill(w, h, fill, bg, r=r, border=border)
            if p is not None:
                cv._imgs.append(p)
                cv.create_image(x, y, image=p, anchor="nw", tags="frame")
        if icon:
            ph = I.icon(icon, fg, fill, 16)
            if ph is not None:
                cv._imgs.append(ph)
                cv.create_image(x + w / 2, y + h / 2, image=ph, tags="frame")
        if text:
            cv.create_text(x + w / 2, y + h / 2, text=text, fill=fg, font=font or self._f_tab,
                           tags="frame")
        self._boxes.append((x, y, x + w, y + h, name, data))

    def _crumbs(self):
        """[(label, path)] dari folder teratas ke folder sekarang."""
        cur = self.cur
        if cur == DRIVES:
            return [("Drive", DRIVES)]
        out = []
        p = os.path.normpath(cur)
        while True:
            if not self.pick and _norm(p) == _norm(self.root):
                out.append((self.title or "Resource", p))
                break
            head, tail = os.path.split(p)
            if not tail:                      # akar drive, mis. C:\
                out.append((head.rstrip("\\/") or head, head))
                if self.pick:
                    out.append(("Drive", DRIVES))
                break
            out.append((tail, p))
            if not head or _norm(head) == _norm(p):
                break
            p = head
        return out[::-1]

    def _draw_frame(self):
        cv, W, H = self.cv, self.W, self.H
        cv.delete("frame")
        cv._imgs = []
        self._boxes = []
        self._draw_panel_bg(cv, self._hover == ("close", None))
        # baris 1: kembali, naik, jejak folder, tampilan
        self._btn(cv, 16, 19, 30, 30, "back", None, C.CARD, C.CARD, icon="chev_left",
                  fg=C.TEXT if self.history else C.LOCKED)
        self._btn(cv, 48, 19, 30, 30, "up", None, C.CARD, C.CARD, icon="arrow_up",
                  fg=C.TEXT if self._parent() is not None else C.LOCKED)
        vx = W - 54 - 2 * 32
        for i, (view, icon) in enumerate((("details", "list"), ("thumbs", "grid"))):
            on = self.view == view
            self._btn(cv, vx + i * 32, 19, 30, 30, "view", view,
                      C.SEG_ON if on else C.CARD, C.CARD, icon=icon,
                      fg=C.TEXT if on else C.MUTED)
        x, xmax = 90, vx - 12
        crumbs = self._crumbs()
        parts = []
        for i, (label, path) in enumerate(crumbs):
            last = i == len(crumbs) - 1
            f = self._f_title if last else self._f_crumb
            parts.append((label, path, f, last))
        widths = [f.measure(lb) + 10 for lb, _p, f, _l in parts]
        sep = 18
        while len(parts) > 1 and sum(widths) + sep * (len(parts) - 1) > xmax - x - 20:
            parts.pop(0)                      # jejak terlalu panjang: buang dari depan
            widths.pop(0)
            if parts and parts[0][0] != "…":
                parts.insert(0, ("…", None, self._f_crumb, False))
                widths.insert(0, self._f_crumb.measure("…") + 10)
                parts.pop(1)
                widths.pop(1)
        for i, (label, path, f, last) in enumerate(parts):
            if i:
                ph = I.icon("chev_right", C.LOCKED, C.CARD, 14)
                if ph is not None:
                    cv._imgs.append(ph)
                    cv.create_image(x + 4, 34, image=ph, tags="frame")
                x += sep
            txt = _fit(f, label, max(30, xmax - x - 10))
            w = f.measure(txt) + 10
            hover = self._hover == ("crumb", path) and path is not None and not last
            if hover:
                p = I.pill(w, 26, C.CARD_HOVER, C.CARD, r=6)
                if p is not None:
                    cv._imgs.append(p)
                    cv.create_image(x, 21, image=p, anchor="nw", tags="frame")
            cv.create_text(x + 5, 34, text=txt, anchor="w", font=f, tags="frame",
                           fill=C.TEXT if last or hover else C.MUTED)
            if path is not None and not last:
                self._boxes.append((x, 21, x + w, 47, "crumb", path))
            x += w
        # baris 2: tab (tempat / jenis file)
        active = self._active_tab()
        tx = 16
        for key, label in self.tabs:
            on = key == active
            f = self._f_tab_b if on else self._f_tab
            tw = f.measure(label) + 24
            if tx + tw > W - 16:
                break
            self._btn(cv, tx, 62, tw, 30, "tab", key, C.SEG_ON if on else C.CARD, C.CARD,
                      text=label, font=f, fg=C.TEXT if on else C.MUTED)
            tx += tw + 4
        cv.create_rectangle(1, 104, W - 1, 105, fill=C.BORDER, outline="", tags="frame")
        cv.create_rectangle(1, H - FOOT_H, W - 1, H - FOOT_H + 1, fill=C.BORDER, outline="",
                            tags="frame")
        self._draw_footer(cv)
        cv.tag_lower("frame")

    def _primary_ok(self):
        if self.pick:
            return bool(self.checked)
        e = self.shown[self.sel] if 0 <= self.sel < len(self.shown) else None
        return e is not None

    def _draw_footer(self, cv):
        W, H = self.W, self.H
        y = H - FOOT_H / 2
        x = 20
        hints = [("Tutup", "Esc"), ("Naik", "Backspace")]
        hints.append(("Centang", "Spasi") if self.pick else ("Buka", "Enter"))
        for text, key in hints:
            t = cv.create_text(x, y, text=text, anchor="w", fill=C.MUTED, font=self._f_sub,
                               tags="frame")
            x = cv.bbox(t)[2] + 8
            x += _keycap(cv, x, y, key, C.CARD, self._f_key, tags="frame") + 16
        # tombol kanan
        right = W - 16
        if self.pick:
            n = len(self.checked)
            label = f"Upload {n} file" if n else "Upload"
        else:
            label = "Buka"
        ok = self._primary_ok()
        bw = self._f_btn.measure(label) + 32
        hover = self._hover == ("primary", None) and ok
        fill = (C.ACCENT_HOVER if hover else C.ACCENT) if ok else C.SEG_ON
        p = I.pill(bw, 30, fill, C.CARD, r=9)
        if p is not None:
            cv._imgs.append(p)
            cv.create_image(right - bw, y - 15, image=p, anchor="nw", tags="frame")
        cv.create_text(right - bw / 2, y, text=label, font=self._f_btn, tags="frame",
                       fill="#ffffff" if ok else C.LOCKED)
        self._boxes.append((right - bw, y - 15, right, y + 15, "primary", None))
        right -= bw + 8
        if not self.pick and self.on_save is not None:
            n = len(self.checked)
            label = f"Simpan {n} ke flashdisk" if n else "Simpan ke flashdisk"
            bw = self._f_tab.measure(label) + 28
            self._btn(cv, right - bw, y - 15, bw, 30, "secondary", None, C.CARD, C.CARD,
                      text=label, border=C.BORDER, r=9)
            right -= bw + 12
        info = self._info()
        if info and right - x > 60:
            cv.create_text(right, y, text=_fit(self._f_sub, info, right - x - 8), anchor="e",
                           fill=C.MUTED, font=self._f_sub, tags="frame")

    def _info(self):
        if self.checked:
            size = sum(e["size"] for e in self.checked.values())
            return f"{len(self.checked)} dipilih  ·  {portfolio.format_size(size)}"
        files = sum(1 for e in self.shown if not e["is_dir"])
        return f"{files} file" if files else ""

    # --- gambar: daftar ---------------------------------------------------------------------
    def _draw_list(self):
        cv = self.list
        if self.loading and time.perf_counter() - self._load_t0 <= 0.2:
            return      # folder baru sebentar lagi siap: isi lama tetap (tidak berkedip)
        cv.delete("all")
        cv._imgs = []
        lw, lh = self.lw, self.lh
        if not self.loading and (self.error or not self.shown):
            msg = self.error or ("Folder kosong." if not self.pick
                                 else "Tidak ada gambar atau video di folder ini.")
            if not self.pick and self.cur == self.root and not self.entries:
                msg = "Belum ada resource untuk kursus ini."
            if self.pick and self.cur == DRIVES and not self.entries:
                msg = "Drive Z: dan flashdisk tidak ditemukan. Hubungi guru."
            cv.create_text(lw / 2, 70, text=msg, fill=C.MUTED, font=self._f_row)
            return
        if self.loading:
            cv.create_text(lw / 2, 70, text="Memuat…", fill=C.MUTED, font=self._f_row)
            return
        if self.view == "details":
            y = -self.offset
            if y + HEAD_H > 0:
                for text, x, anchor in (("Nama", 70, "w"), ("Diubah", lw - 230, "w"),
                                        ("Ukuran", lw - 22, "e")):
                    cv.create_text(x, y + HEAD_H / 2, text=text, anchor=anchor,
                                   fill=C.MUTED, font=self._f_sub)
        for i in self._visible_range():
            if self.view == "details":
                self._draw_row(cv, i)
            else:
                self._draw_cell(cv, i)
        if self.total_h > lh:              # bilah gulir tipis
            th = max(30, int(lh * lh / self.total_h))
            ty = int((lh - th) * self.offset / max(1, self.total_h - lh))
            p = I.pill(4, th, C.BORDER, C.CARD, r=2)
            if p is not None:
                cv._imgs.append(p)
                cv.create_image(lw - 6, ty, image=p, anchor="nw")

    def _check_img(self, on, bg):
        if on:
            box = I.pill(16, 16, C.ACCENT, bg, r=4)
            tick = I.icon("check_bold", "#ffffff", C.ACCENT, 14)
            return box, tick
        return I.pill(16, 16, bg, bg, r=4, border="#5c5a55"), None

    def _draw_row(self, cv, i):
        e = self.shown[i]
        x0, y0, x1, y1 = self._item_box(i)
        y0 -= self.offset
        cy = y0 + ROW_H / 2
        sel = i == self.sel
        on = e["path"] in self.checked
        bg = C.CARD_HOVER if sel else C.CARD
        if sel:
            p = I.pill(x1 - x0, ROW_H - 2, C.CARD_HOVER, C.CARD, r=8)
            if p is not None:
                cv._imgs.append(p)
                cv.create_image(x0, y0 + 1, image=p, anchor="nw")
        if not e["is_dir"] and (self.pick or self.on_save is not None):
            box, tick = self._check_img(on, bg)
            for ph in (box, tick):
                if ph is not None:
                    cv._imgs.append(ph)
                    cv.create_image(26, cy, image=ph)
        icon = {"folder": "folder", "image": "image", "video": "play"}.get(e["kind"], "file")
        ph = I.icon(icon, C.TEXT if e["is_dir"] else C.MUTED, bg, 16)
        if ph is not None:
            cv._imgs.append(ph)
            cv.create_image(52, cy, image=ph)
        name_w = self.lw - 230 - 70 - 16
        cv.create_text(70, cy, text=_fit(self._f_row, e["name"], name_w), anchor="w",
                       fill=C.ACCENT_HOVER if on else C.TEXT, font=self._f_row)
        if e["mtime"]:
            when = datetime.fromtimestamp(e["mtime"]).strftime("%d/%m/%Y %H:%M")
            cv.create_text(self.lw - 230, cy, text=when, anchor="w", fill=C.MUTED,
                           font=self._f_sub)
        if not e["is_dir"]:
            cv.create_text(self.lw - 22, cy, text=portfolio.format_size(e["size"]), anchor="e",
                           fill=C.MUTED, font=self._f_sub)

    def _thumb_photo(self, e, bg):
        """PhotoImage thumbnail dengan sudut bulat (dicampur ke warna latar), atau None
        kalau belum siap (diminta ke thread)."""
        key = (e["path"], e["mtime"])
        ph = self._photos.get((key, bg))
        if ph is not None:
            return ph
        with _thumbs_lock:
            ready = key in _thumbs
            img = _thumbs.get(key)
        if not ready:
            self.loader.want_thumb(key, e["path"], e["kind"])
            if self._poll_job is None:
                self._poll_job = self.after(POLL_MS, self._poll)
            return None
        if img is None:
            return False                       # file tidak terbaca: pakai ikon
        Image = photos.Image
        base = Image.new("RGB", (TW, TH), I._rgb(bg))
        base.paste(img, (0, 0), I.round_mask(TW, TH, 7))
        ph = photos.to_photoimage(base)
        if len(self._photos) > 600:
            self._photos.clear()
        self._photos[(key, bg)] = ph
        return ph

    def _draw_cell(self, cv, i):
        e = self.shown[i]
        x0, y0, x1, y1 = self._item_box(i)
        y0 -= self.offset
        sel = i == self.sel
        on = e["path"] in self.checked
        bg = C.CARD_HOVER if sel else C.CARD
        if sel:
            p = I.pill(CELL_W - 4, CELL_H - 4, C.CARD_HOVER, C.CARD, r=10)
            if p is not None:
                cv._imgs.append(p)
                cv.create_image(x0 + 2, y0 + 2, image=p, anchor="nw")
        tx, ty = x0 + (CELL_W - TW) // 2, y0 + 8
        inner = bg
        if on:          # dicentang: bingkai oranye di sekeliling gambar
            p = I.pill(TW + 6, TH + 6, C.ACCENT, bg, r=9)
            if p is not None:
                cv._imgs.append(p)
                cv.create_image(tx - 3, ty - 3, image=p, anchor="nw")
            inner = C.ACCENT
        ph = None
        if e["kind"] in ("image", "video"):
            ph = self._thumb_photo(e, inner)
        if ph:
            cv._imgs.append(ph)
            cv.create_image(tx, ty, image=ph, anchor="nw")
        else:            # folder / file lain / thumbnail belum siap: kotak + ikon
            p = I.pill(TW, TH, C.SEG_ON if e["is_dir"] else C.SIDEBAR_ACTIVE, inner, r=7)
            if p is not None:
                cv._imgs.append(p)
                cv.create_image(tx, ty, image=p, anchor="nw")
            icon = {"folder": "folder", "image": "image", "video": "play"}.get(e["kind"],
                                                                              "file")
            fill = C.SEG_ON if e["is_dir"] else C.SIDEBAR_ACTIVE
            ic = I.icon(icon, C.TEXT if e["is_dir"] else C.MUTED, fill, 26)
            if ic is not None:
                cv._imgs.append(ic)
                cv.create_image(tx + TW / 2, ty + TH / 2, image=ic)
        cv.create_text(x0 + CELL_W / 2, ty + TH + 18,
                       text=_fit(self._f_cell, e["name"], CELL_W - 12),
                       fill=C.ACCENT_HOVER if on else C.TEXT, font=self._f_cell)

    # --- pilih / gulir ----------------------------------------------------------------------
    def _select(self, i, scroll=False):
        if not self.shown:
            return "break"
        i = max(0, min(len(self.shown) - 1, i))
        if i != self.sel or scroll:
            self.sel = i
            if scroll:
                self._ensure_visible(i)
            self._draw_list()
            if not self.pick:
                self._draw_frame()      # tombol "Buka" ikut aktif
        return "break"

    def _move(self, dx, dy):
        if not self.shown:
            return "break"
        if self.sel < 0:
            return self._select(0, scroll=True)
        if self.view == "details":
            step = dy if dy else dx
        else:
            step = dx + dy * self.cols
        return self._select(self.sel + step, scroll=True)

    def _ensure_visible(self, i):
        if i < 0:
            return
        _x0, y0, _x1, y1 = self._item_box(i)
        top = y0 - (HEAD_H if self.view == "details" and i == 0 else 0)
        if top < self.offset:
            self.offset = max(0, top - 4)
        elif y1 > self.offset + self.lh:
            self.offset = y1 - self.lh + 6

    def _scroll(self, direction):
        step = ROW_H * 3 if self.view == "details" else CELL_H
        old = self.offset
        self.offset = max(0, min(max(0, self.total_h - self.lh), self.offset + direction * step))
        if self.offset != old:
            self._draw_list()
        return "break"

    def _list_motion(self, e):
        i = self._item_at(e.x, e.y)
        if i >= 0 and i != self.sel:
            self._select(i)
        self.list.config(cursor="hand2" if i >= 0 else "")

    def _list_click(self, e):
        self.list.focus_set()
        i = self._item_at(e.x, e.y)
        self._click_nav = False
        if i < 0:
            return
        self.sel = i
        ent = self.shown[i]
        if ent["is_dir"]:
            self._click_nav = True    # klik dua kali di folder: klik kedua diabaikan
            self._go(ent["path"])
        elif self.pick or self.on_save is not None:
            self._toggle(i)
        else:
            self._draw_list()

    def _list_double(self, e):
        if getattr(self, "_click_nav", False) or self.loading:
            return
        i = self._item_at(e.x, e.y)
        if i >= 0 and not self.shown[i]["is_dir"] and not self.pick:
            self._toggle(i)          # klik pertama sudah mencentang: kembalikan
            self._open_file(self.shown[i])

    def _toggle(self, i):
        if not (0 <= i < len(self.shown)) or self.shown[i]["is_dir"]:
            return "break"
        e = self.shown[i]
        if e["path"] in self.checked:
            del self.checked[e["path"]]
        else:
            self.checked[e["path"]] = e
        self._draw_list()
        self._draw_frame()
        return "break"

    def _check_all(self):
        files = [e for e in self.shown if not e["is_dir"]]
        if files and all(e["path"] in self.checked for e in files):
            for e in files:
                self.checked.pop(e["path"], None)
        else:
            for e in files:
                self.checked[e["path"]] = e
        self._draw_list()
        self._draw_frame()
        return "break"

    def _activate(self, i):
        """Enter: buka folder; file -> centang (pick) / buka (resource)."""
        if not (0 <= i < len(self.shown)):
            return "break"
        e = self.shown[i]
        if e["is_dir"]:
            self._go(e["path"])
        elif self.pick:
            if self.checked:
                self._primary()
            else:
                self._toggle(i)
        else:
            self._open_file(e)
        return "break"

    # --- aksi -------------------------------------------------------------------------------
    def _open_file(self, e):
        try:
            if self.on_open is not None:
                self.on_open(e["path"])
            else:
                portfolio.open_file(e["path"])
        except Exception as exc:
            C.log(f"File browser: gagal membuka {e['path']!r}: {exc!r}")

    def _primary(self):
        if not self._primary_ok():
            return
        if self.pick:
            paths = [e["path"] for e in self.checked.values()]
            fn, top = self.on_pick, self.top
            self.close()
            if fn is not None:
                top.after(1, lambda: fn(paths))
        else:
            self._activate(self.sel)

    def _secondary(self):
        if self.pick or self.on_save is None:
            return
        items = list(self.checked.values())
        if not items and 0 <= self.sel < len(self.shown) and not self.shown[self.sel]["is_dir"]:
            items = [self.shown[self.sel]]
        if not items:
            return
        fn, top = self.on_save, self.top
        self.close()          # dialog pilih folder tidak bertumpuk dengan file browser
        top.after(1, lambda: fn([{"path": e["path"], "name": e["name"]} for e in items]))


# --- halaman Resource (layar kursus murid) ---------------------------------------------------
class ResourcePage(tk.Frame):
    """Halaman Resource: ringkasan + tombol "Buka file" (membuka file browser resource)."""

    def __init__(self, master, course):
        super().__init__(master, bg=C.BG)
        from elearning import resources
        from elearning.ui.controls import RoundButton
        from elearning.ui.widgets import add_hover
        self.course = course
        self.folder = resources.course_folder(course)
        box = tk.Frame(self, bg=C.BG)
        box.place(relx=0.5, rely=0.42, anchor="center")
        ic = I.icon("folder", C.MUTED, C.BG, 40)
        if ic is not None:
            lb = tk.Label(box, image=ic, bg=C.BG, bd=0)
            lb.image = ic
            lb.pack(pady=(0, 10))
        tk.Label(box, text=f"Resource {course['title']}", bg=C.BG, fg=C.TEXT,
                 font=(C.FONT, 18, "bold")).pack()
        self.info = tk.Label(box, text="", bg=C.BG, fg=C.MUTED, font=(C.FONT, 10))
        self.info.pack(pady=(4, 16))
        self.btn = RoundButton(box, text="Buka file", command=self.open_browser, bg=C.ACCENT,
                               fg="white", activebackground=C.ACCENT_HOVER,
                               activeforeground="white", font=(C.FONT, 11, "bold"),
                               padx=22, pady=8)
        add_hover(self.btn, C.ACCENT, C.ACCENT_HOVER)
        self.status = tk.Label(box, text="", bg=C.BG, fg=C.MUTED, font=(C.FONT, 10),
                               wraplength=520, justify="center")
        self.status.pack(side="bottom", pady=(12, 0))
        self._count()

    def _count(self):
        """Hitung isi folder di thread (flashdisk / folder jaringan bisa lambat)."""
        from elearning import resources
        box = {}

        def work():
            try:
                box["res"] = resources.summary(self.course) if os.path.isdir(self.folder) \
                    else (0, 0)
            except Exception as exc:
                C.log(f"Resource: hitung isi gagal: {exc!r}")
                box["res"] = (0, 0)
        threading.Thread(target=work, daemon=True).start()

        def poll():
            try:
                if not self.winfo_exists():
                    return
            except tk.TclError:
                return
            if "res" not in box:
                self.after(POLL_MS * 3, poll)
                return
            files, folders = box["res"]
            if not files and not folders:
                self.info.config(text="Belum ada resource untuk kursus ini.")
                return
            parts = [f"{files} file"] + ([f"{folders} folder"] if folders else [])
            self.info.config(text="  ·  ".join(parts) + "  ·  buka, lihat, simpan ke flashdisk")
            self.btn.pack()
        poll()

    def open_browser(self):
        open_file_browser(self, mode="resource", root=self.folder,
                          title=f"Resource {self.course['title']}", on_save=self._save)

    def _save(self, items):
        from elearning.ui import usb_save

        def done(text, ok):
            try:
                self.status.config(text=text, fg=C.ON if ok else C.ERROR)
            except tk.TclError:
                pass
        usb_save.save_items(self, items, done, subfolder=f"{self.course['title']} - Resource")
