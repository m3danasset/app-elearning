"""Galeri karya gaya Behance minimalis (dipakai halaman Portfolio & Assignment).

- Sampul besar 4:3 bersudut membulat, tanpa kotak kartu; judul & keterangan kecil di bawah.
- Kursor di atas sampul: sampul terangkat sedikit, muncul tombol bulat Simpan / Hapus di
  pojok kanan atas (digambar halus ke dalam gambar, tidak pixelated).
- Video diberi tanda putar di tengah sampul.
- Satu canvas untuk semua karya: tidak ada widget bertumpuk -> tanpa potongan / blok hitam.
- Sampul dimuat di thread terpisah (sekali dibuat, disimpan di _thumbs).
"""

import threading
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime

from elearning import config as C
from elearning import photos, portfolio
from elearning.ui import ui_icons as I

GAP = 22
MIN_W = 230
MAX_W = 330
TEXT_H = 46
RADIUS = 12
LIFT = 3
BTN = 30           # tombol bulat di pojok sampul
MONTHS = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")

_covers = {}       # path -> gambar sampul besar (PIL), diingat selama aplikasi terbuka


def title_of(name):
    """Judul rapi gaya Behance: tanpa cap waktu, tanpa ekstensi, garis bawah jadi spasi."""
    import os
    import re
    stem = os.path.splitext(name)[0]
    while True:
        new = re.sub(r"^\d{8}-\d{6}(?:-\d+)?_", "", stem)
        if new == stem:
            break
        stem = new
    stem = stem.replace("_", " ").strip()
    return (stem[:1].upper() + stem[1:]) if stem else name


def _when(d):
    if isinstance(d, datetime):
        return f"{d.day} {MONTHS[d.month - 1]} {d.year}"
    return str(d or "")


class GalleryBoard(tk.Canvas):
    def __init__(self, master, on_open=None, on_save=None, on_delete=None, empty="",
                 on_blender=None):
        super().__init__(master, bg=C.BG, highlightthickness=0, bd=0, height=80)
        self.on_open, self.on_save, self.on_delete = on_open, on_save, on_delete
        self.on_blender = on_blender   # gambar dari guru: buka di Blender sebagai referensi
        self.empty = empty
        self.items = []
        self.tiles = []          # (x, y, w, h) sampul tiap item
        self.hover = None
        self._hover_btn = None
        self._imgs = {}
        self._width = 0
        self._loading = False
        self.f = {
            "title": tkfont.Font(family=C.FONT, size=10, weight="bold"),
            "meta": tkfont.Font(family=C.FONT, size=9),
            "chip": tkfont.Font(family=C.FONT, size=8, weight="bold"),
            "empty": tkfont.Font(family=C.FONT, size=11),
        }
        self.bind("<Configure>", self._on_configure)
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda e: self._set_hover(None, None))
        self.bind("<Button-1>", self._click)

    # --- data ---------------------------------------------------------------------
    def set_items(self, items, empty=None):
        self.items = list(items)
        if empty is not None:
            self.empty = empty
        self.hover = None
        self._load_covers()
        self.redraw()

    def _load_covers(self):
        todo = [it["path"] for it in self.items if it["path"] not in _covers]
        if not todo or self._loading:
            return
        self._loading = True

        def work():
            for p in todo:
                img = portfolio.load_large(p)
                if img is None:
                    img = photos.Image.new("RGB", (portfolio.LARGE_W, portfolio.LARGE_H),
                                           I._rgb(C.CARD_HOVER))
                _covers[p] = img
            self._loading = False

        threading.Thread(target=work, daemon=True).start()
        self._poll()

    def _poll(self):
        if not self.winfo_exists():
            return
        if self._loading:
            self.after(80, self._poll)
            return
        self.redraw()

    # --- susunan --------------------------------------------------------------------
    def _on_configure(self, e):
        if abs(e.width - self._width) > 1:
            self._width = e.width
            self.redraw()

    def _layout(self, w):
        cols = max(1, int((w + GAP) // (MIN_W + GAP)))
        tw = min(MAX_W, (w - (cols - 1) * GAP) / cols)
        th = tw * 3 / 4
        tiles = []
        for i in range(len(self.items)):
            r, c = divmod(i, cols)
            tiles.append((c * (tw + GAP), r * (th + TEXT_H + GAP) + LIFT, tw, th))
        rows = (len(self.items) + cols - 1) // cols
        return tiles, rows * (th + TEXT_H + GAP) + LIFT

    def redraw(self):
        w = self.winfo_width()
        if w < 100:
            return
        self.delete("all")
        self._imgs = {}
        if not self.items:
            self.create_text(4, 24, text=self.empty, anchor="w", font=self.f["empty"],
                             fill=C.MUTED)
            self.configure(height=56)
            self.tiles = []
            return
        self.tiles, total = self._layout(w)
        for i, it in enumerate(self.items):
            self._draw_tile(i, it)
        if int(self.cget("height")) != int(total):
            self.configure(height=int(total))

    def _cover_img(self, it, tw, th, hover):
        """Sampul membulat (+ tanda video, + tombol saat hover) -> PhotoImage (diingat)."""
        key = (it["path"], int(tw), int(th), hover, bool(self.on_save),
               bool(self.on_delete and it.get("own", True)), self._ref_ok(it))
        ph = self._imgs.get(key)
        if ph is not None:
            return ph
        src = _covers.get(it["path"])
        Image = photos.Image
        tw, th = int(tw), int(th)
        img = Image.new("RGB", (tw, th), I._rgb(C.BG))
        if src is None:
            body = Image.new("RGB", (tw, th), I._rgb(C.CARD))
        else:
            body = src.resize((tw, th), photos._RESAMPLE)
        if it["kind"] == "video":       # tanda putar di tengah
            d = 44
            x, y = (tw - d) // 2, (th - d) // 2
            body.paste((0, 0, 0), (x, y), I.round_mask(d, d, d / 2).point(lambda v: v * 150 // 255))
            tri = I._render_icon("play_fill", "#ffffff", "#000000", 24).convert("L")
            body.paste((255, 255, 255), (x + 11, y + 10), tri)
        if hover:                       # tombol bulat di pojok kanan atas
            for k, (name, _fn) in enumerate(self._buttons(it)):
                bx = tw - 10 - BTN - k * (BTN + 8)
                body.paste((20, 20, 20), (bx, 10),
                           I.round_mask(BTN, BTN, BTN / 2).point(lambda v: v * 200 // 255))
                ic = I._render_icon(name, "#ffffff", "#000000", 18).convert("L")
                body.paste((255, 255, 255), (bx + 6, 16), ic)
        img.paste(body, (0, 0), I.round_mask(tw, th, RADIUS))
        ph = photos.to_photoimage(img)
        self._imgs[key] = ph
        return ph

    def _ref_ok(self, it):
        return (self.on_blender is not None and not it.get("own", True)
                and it["kind"] == "image")

    def _buttons(self, it):
        out = []
        if self._ref_ok(it):        # paling kanan: buka di Blender (Image Editor kiri)
            out.append(("panel", self.on_blender))
        if self.on_delete is not None and it.get("own", True):
            out.append(("close", self.on_delete))
        if self.on_save is not None:
            out.append(("download", lambda item: self.on_save([item])))
        return out

    def _draw_tile(self, i, it):
        x, y, tw, th = self.tiles[i]
        hover = i == self.hover
        dy = -LIFT if hover else 0
        tag = f"t{i}"
        self.create_image(x, y + dy, image=self._cover_img(it, tw, th, hover), anchor="nw",
                          tags=(tag, "cover"))
        ty = y + th + 10 + dy
        name = title_of(it["name"])
        f = self.f["title"]
        avail = tw - 4
        chip = "Guru" if not it.get("own", True) else ""
        if chip:
            avail -= f.measure(chip) + 16
        if f.measure(name) > avail:
            while name and f.measure(name + "...") > avail:
                name = name[:-1]
            name = name.rstrip() + "..."
        self.create_text(x + 2, ty, text=name, anchor="nw", font=f, fill=C.TEXT, tags=tag)
        if chip:      # label kecil "Guru" untuk bahan dari guru
            cw = self.f["chip"].measure(chip) + 12
            ph = I.pill(cw, 18, C.SEG_ON, C.BG, r=9)
            if ph is not None:
                self._imgs[("chip", i)] = ph
                self.create_image(x + tw - cw, ty - 1, image=ph, anchor="nw", tags=tag)
            self.create_text(x + tw - cw / 2, ty + 8, text=chip, font=self.f["chip"],
                             fill=C.TEXT, tags=tag)
        meta = f"{_when(it['added'])}  ·  {portfolio.format_size(it['size'])}"
        if it["kind"] == "video":
            meta += "  ·  Video"
        elif self._ref_ok(it):     # petunjuk tombol ikon di pojok sampul
            meta += "  ·  arahkan kursor: buka di Blender"
        self.create_text(x + 2, ty + 19, text=meta, anchor="nw", font=self.f["meta"],
                         fill=C.MUTED, tags=tag)

    # --- interaksi -----------------------------------------------------------------------
    def _hit(self, ex, ey):
        for i, (x, y, tw, th) in enumerate(self.tiles):
            if x <= ex <= x + tw and y - LIFT <= ey <= y + th + TEXT_H:
                btn = None
                if i == self.hover and y - LIFT + 10 <= ey <= y - LIFT + 10 + BTN:
                    for k, (_n, fn) in enumerate(self._buttons(self.items[i])):
                        bx = x + tw - 10 - BTN - k * (BTN + 8)
                        if bx <= ex <= bx + BTN:
                            btn = fn
                return i, btn
        return None, None

    def _motion(self, e):
        i, btn = self._hit(e.x, e.y)
        self._set_hover(i, btn)

    def _set_hover(self, i, btn):
        self.config(cursor="hand2" if i is not None else "")
        if i == self.hover:
            return
        old, self.hover = self.hover, i
        for j in (old, i):       # hanya dua sampul yang digambar ulang (ringan)
            if j is not None and j < len(self.items):
                self.delete(f"t{j}")
                self._draw_tile(j, self.items[j])

    def _click(self, e):
        i, btn = self._hit(e.x, e.y)
        if i is None:
            return
        it = self.items[i]
        if btn is not None:
            btn(it)
        elif self.on_open is not None:
            self.on_open(it)
