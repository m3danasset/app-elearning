"""Popup "Who's using Chrome?" (layar murid, English): pilih profil Chrome sebelum Pinterest.

Meniru pemilih profil Chrome asli (mode gelap): latar #1f1f1f dengan cahaya warna lembut di
tepi (hijau kiri, kuning atas, merah muda kanan atas, biru kanan bawah, teal kiri bawah),
logo Chrome ASLI dari PC, judul + paragraf, kartu abu-abu (#3c4043) bersudut membulat: label
tebal di atas, titik tiga di pojok, avatar bulat, nama di bawah. Fokus = bingkai biru
(#a8c7fa); tombol "Close" berbingkai biru di kiri bawah (seperti "Guest mode").
Semua bentuk antialias (numpy / round_mask), TANPA ImageDraw. Overlay sama dengan search
palette (latar redup, sudut panel tembus).

Kartu:
  - Teacher  : Pinterest akun guru / studio (config.WEB_STUDIO_ACCOUNT) -> semua murid.
  - Personal : akun Google murid sendiri -> hanya program WEB_OWN_PROFILE_PROGRAMS (dewasa);
               SUPERKIDS: kartu putus-putus terkunci ("Adults only", seperti kartu "Add").
Klik kartu / Enter = buka Pinterest dengan profil itu (web_launcher.open_web). Esc = tutup.
"""

import tkinter.font as tkfont

from elearning import config as C
from elearning import photos
from elearning import web_launcher as W
from elearning.ui import ui_icons as I
from elearning.ui.search_palette import KEY, RADIUS, OverlayPanel, open_overlay

try:
    import numpy as np
except Exception:
    np = None

BG = "#1f1f1f"
CARD = "#3c4043"
CARD_HOVER = "#46494e"
TEXT = "#e3e3e3"
SUB = "#c4c7c5"
BLUE = "#a8c7fa"
DOTS = "#8e9399"
CARD_W, CARD_H, GAP, CARD_R = 162, 178, 16, 8
AVATAR = 74
# cahaya tepi: (x, y relatif panel, jari-jari relatif lebar, warna, kekuatan)
GLOWS = ((-0.04, 0.42, 0.30, (40, 120, 70), 0.55),       # hijau kiri
         (0.62, -0.10, 0.30, (150, 120, 30), 0.45),      # kuning atas
         (1.02, 0.02, 0.26, (150, 90, 120), 0.55),       # merah muda kanan atas
         (1.04, 0.86, 0.32, (70, 90, 170), 0.55),        # biru kanan bawah
         (-0.02, 1.02, 0.30, (40, 120, 115), 0.50))      # teal kiri bawah
_cache = {}


def open_chrome_profiles(widget, student):
    return open_overlay(ChromeProfiles, widget.winfo_toplevel(), {"widget": widget,
                                                                  "student": student})


def _initials(name):
    parts = [p for p in str(name).replace(".", " ").split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def _background(w, h):
    """Latar gelap + cahaya warna lembut di tepi, sudut membulat (di atas warna KEY)."""
    key = ("bg", w, h)
    if key in _cache:
        return _cache[key]
    Image = photos.Image
    base = Image.new("RGB", (w, h), I._rgb(BG))
    if np is not None:
        img = np.empty((h, w, 3), dtype=np.float32)
        img[:] = I._rgb(BG)
        X = (np.arange(w, dtype=np.float32) + 0.5)[None, :]
        Y = (np.arange(h, dtype=np.float32) + 0.5)[:, None]
        for gx, gy, gr, col, k in GLOWS:
            r = gr * w
            d2 = ((X - gx * w) ** 2 + (Y - gy * h) ** 2) / (r * r)
            a = (np.exp(-d2 * 1.6) * k)[..., None]
            img += (np.array(col, dtype=np.float32) - img) * a
        base = Image.fromarray(np.clip(img + 0.5, 0, 255).astype(np.uint8), "RGB")
    out = Image.new("RGB", (w, h), I._rgb(KEY))
    out.paste(base, (0, 0), I.round_mask(w, h, RADIUS))
    ph = photos.to_photoimage(out)
    _cache[key] = ph
    return ph


def _rgba_shape(w, h, color, r, alpha=255):
    """Bentuk bersudut membulat RGBA (tepi halus) - diletakkan di atas latar bergradasi."""
    key = ("shape", w, h, color, r, alpha)
    if key not in _cache:
        img = photos.Image.new("RGBA", (w, h), I._rgb(color) + (0,))
        img.putalpha(I.round_mask(w, h, r).point(lambda v: v * alpha // 255))
        _cache[key] = photos.to_photoimage(img)
    return _cache[key]


def _ring(w, h, color, r, t=2):
    """Bingkai (garis tepi saja), mis. fokus biru / tombol Close."""
    key = ("ring", w, h, color, r, t)
    if key not in _cache:
        a = I.round_mask(w, h, r).copy()
        a.paste(0, (t, t), I.round_mask(w - 2 * t, h - 2 * t, max(1, r - t)))
        img = photos.Image.new("RGBA", (w, h), I._rgb(color) + (0,))
        img.putalpha(a)
        _cache[key] = photos.to_photoimage(img)
    return _cache[key]


def _dashed_ring(w, h, color, r):
    """Garis tepi putus-putus (kartu terkunci meniru kartu "Add" Chrome)."""
    key = ("dash", w, h, color, r)
    if key not in _cache:
        Image = photos.Image
        a = I.round_mask(w, h, r).copy()
        a.paste(0, (1, 1), I.round_mask(w - 2, h - 2, max(1, r - 1)))
        hor = Image.new("L", (w, h), 255)          # garis atas & bawah: putus tiap 8 px
        for x in range(0, w, 8):
            hor.paste(0, (x + 5, 0, min(w, x + 8), h))
        ver = Image.new("L", (w, h), 255)          # garis kiri & kanan
        for y in range(0, h, 8):
            ver.paste(0, (0, y + 5, w, min(h, y + 8)))
        band = Image.new("L", (w, h), 0)
        band.paste(255, (0, 0, w, r))
        band.paste(255, (0, h - r, w, h))
        mask = Image.composite(hor, ver, band)
        a = Image.composite(a, Image.new("L", (w, h), 0), mask)
        img = Image.new("RGBA", (w, h), I._rgb(color) + (0,))
        img.putalpha(a.point(lambda v: v * 170 // 255))
        _cache[key] = photos.to_photoimage(img)
    return _cache[key]


def _clear_icon(name, color, size):
    """Ikon garis TRANSPARAN (tanpa kotak latar) untuk di atas latar bergradasi: bentuk
    digambar putih di atas hitam, kecerahannya jadi alpha."""
    key = ("icon", name, color, size)
    if key not in _cache:
        try:
            a = I._render_icon(name, "#ffffff", "#000000", size).convert("L")
            img = photos.Image.new("RGBA", (size, size), I._rgb(color) + (0,))
            img.putalpha(a)
            _cache[key] = photos.to_photoimage(img)
        except Exception:
            _cache[key] = None
    return _cache[key]


class ChromeProfiles(OverlayPanel):
    def _focus_target(self):
        return self.cv

    def _build(self, top, opts):
        self.widget = opts["widget"]
        self.student = opts["student"]
        fam = C.FONT
        self.f = {"h": tkfont.Font(family=fam, size=17),
                  "sub": tkfont.Font(family=fam, size=11),
                  "tag": tkfont.Font(family=fam, size=9, weight="bold"),
                  "name": tkfont.Font(family=fam, size=10),
                  "btn": tkfont.Font(family=fam, size=10, weight="bold"),
                  "av": tkfont.Font(family="Segoe UI Light" if fam == "Segoe UI" else fam,
                                    size=27)}
        name = self.student.get("name", "")
        self.cards = []
        for key, ok in W.profiles_for(self.student):
            if key == "studio":
                self.cards.append({"key": key, "ok": ok, "tag": "Teacher",
                                   "name": getattr(C, "WEB_STUDIO_NAME", "Teacher"),
                                   "letter": "M", "color": "#5565bd"})
            else:
                self.cards.append({"key": key, "ok": ok,
                                   "tag": "Your Chrome" if ok else "Adults only",
                                   "name": name, "letter": _initials(name)[:1],
                                   "color": "#455a64"})
        n = len(self.cards)
        self._make_window(top, 1000, 700, min_w=640, min_h=560)
        # seperti pemilih profil Chrome asli: TANPA layar gelap di belakang & tanpa fade
        # (langsung tampil utuh, tidak pernah tertahan setengah redup)
        if self.dim is not None:
            try:
                self.dim.destroy()
            except Exception:
                pass
            self.dim = None
        try:
            self.attributes("-alpha", 1.0)
        except Exception:
            pass
        self._kb = False              # bingkai fokus biru hanya setelah tombol panah
        cv = self.cv
        W_, H_ = self.W, self.H
        cv.create_image(0, 0, image=_background(W_, H_), anchor="nw")
        # blok logo + judul + paragraf + kartu di TENGAH panel (di atas baris tombol bawah)
        block = 46 + 40 + 44 + 52 + CARD_H
        cy = int(max(46, (H_ - 76 - block) / 2 + 23))
        logo = W.chrome_logo(46)
        if logo is not None:
            ph = photos.to_photoimage(logo)            # RGBA di atas latar bergradasi
            cv._imgs.append(ph)
            cv.create_image(W_ / 2, cy, image=ph)
        cv.create_text(W_ / 2, cy + 62, text="Who's using Chrome?", font=self.f["h"], fill=TEXT)
        cv.create_text(W_ / 2, cy + 106, font=self.f["sub"], fill=SUB, justify="center",
                       width=min(470, W_ - 80),
                       text="Choose a profile to open Chrome. Your teacher's profile has "
                            "SafeSearch on for kids; your own Google account is for adult "
                            "students.")
        x = (W_ - (n * CARD_W + (n - 1) * GAP)) / 2
        y = cy + 160
        for i, c in enumerate(self.cards):
            c["rect"] = (x + i * (CARD_W + GAP), y, x + i * (CARD_W + GAP) + CARD_W,
                         y + CARD_H)
        self.hover = None
        self.sel = next((i for i, c in enumerate(self.cards) if c["ok"]), None)
        self._draw_cards()
        # bawah: tombol "Close" berbingkai biru (seperti "Guest mode") + sisa jatah di kanan
        bw, bh = 132, 38
        bx, by = 36, H_ - 36 - bh
        self._btn = (bx, by, bx + bw, by + bh)
        cv.create_image(bx, by, image=_ring(bw, bh, "#3b6f8f", bh // 2, 1), anchor="nw",
                        tags="close")
        ic = _clear_icon("close", BLUE, 16)
        if ic is not None:
            cv.create_image(bx + 26, by + bh / 2, image=ic, tags="close")
        cv.create_text(bx + 44, by + bh / 2, text="Close", anchor="w", font=self.f["btn"],
                       fill=BLUE, tags="close")
        cv.tag_bind("close", "<Button-1>", lambda e: self.close())
        cv.tag_bind("close", "<Enter>", lambda e: cv.config(cursor="hand2"))
        cv.tag_bind("close", "<Leave>", lambda e: cv.config(cursor=""))
        st = W.status_text(self.student.get("id"), "pinterest") if self.student else ""
        cv.create_text(W_ - 36, by + bh / 2, anchor="e", font=self.f["sub"], fill=SUB,
                       text=f"Browsing  ·  {st}" if st else "Browsing")
        cv.bind("<Motion>", self._motion)
        cv.bind("<Leave>", lambda e: self._set_hover(None))
        cv.bind("<Button-1>", self._click)
        self.bind("<Escape>", lambda e: self.close())
        self.bind("<Return>", lambda e: self._choose(self.sel))
        self.bind("<Left>", lambda e: self._move(-1))
        self.bind("<Right>", lambda e: self._move(1))
        self._reveal()

    # --- gambar kartu -------------------------------------------------------------------
    @staticmethod
    def _avatar(color, ok):
        key = ("av", color, ok)
        if key not in _cache:
            col = color if ok else "#3b3d40"
            img = photos.Image.new("RGBA", (AVATAR, AVATAR), I._rgb(col) + (0,))
            img.putalpha(I.round_mask(AVATAR, AVATAR, AVATAR / 2))
            _cache[key] = photos.to_photoimage(img)
        return _cache[key]

    @staticmethod
    def _dots():
        key = ("dots",)
        if key not in _cache:
            d = 4
            img = photos.Image.new("RGBA", (d, 16), I._rgb(DOTS) + (0,))
            a = photos.Image.new("L", (d, 16), 0)
            for k in range(3):
                a.paste(I.round_mask(d, d, d / 2), (0, k * 6))
            img.putalpha(a)
            _cache[key] = photos.to_photoimage(img)
        return _cache[key]

    def _draw_cards(self):
        cv = self.cv
        cv.delete("card")
        for i, c in enumerate(self.cards):
            x0, y0, x1, y1 = c["rect"]
            w, h = int(x1 - x0), int(y1 - y0)
            cx = (x0 + x1) / 2
            ok = c["ok"]
            hot = ok and i == self.hover
            if ok:
                cv.create_image(x0, y0, anchor="nw", tags="card",
                                image=_rgba_shape(w, h, CARD_HOVER if hot else CARD, CARD_R))
                cv.create_image(x1 - 14, y0 + 17, image=self._dots(), tags="card")
            else:                         # terkunci: kartu putus-putus seperti "Add"
                cv.create_image(x0, y0, anchor="nw", tags="card",
                                image=_dashed_ring(w, h, "#8e9399", CARD_R))
            if ok and i == self.sel and self._kb and self.hover is None:
                cv.create_image(x0 - 3, y0 - 3, anchor="nw", tags="card",
                                image=_ring(w + 6, h + 6, BLUE, CARD_R + 3, 2))
            cv.create_text(cx, y0 + 24, text=c["tag"], font=self.f["tag"],
                           fill=TEXT if ok else SUB, tags="card")
            acy = y0 + 24 + 16 + AVATAR / 2
            cv.create_image(cx, acy, image=self._avatar(c["color"], ok), tags="card")
            if ok:
                cv.create_text(cx, acy - 1, text=c["letter"], font=self.f["av"],
                               fill="#ffffff", tags="card")
            else:
                lk = I.icon("lock", TEXT, "#3b3d40", 30)
                if lk is not None:
                    cv.create_image(cx, acy, image=lk, tags="card")
            cv.create_text(cx, y1 - 26, text=self._fit(c["name"], w - 20),
                           font=self.f["name"], fill=TEXT if ok else SUB, tags="card")

    def _fit(self, text, width):
        f = self.f["name"]
        if f.measure(text) <= width:
            return text
        while text and f.measure(text + "…") > width:
            text = text[:-1]
        return text + "…"

    # --- interaksi -----------------------------------------------------------------------
    def _index_at(self, x, y):
        for i, c in enumerate(self.cards):
            x0, y0, x1, y1 = c["rect"]
            if x0 <= x < x1 and y0 <= y < y1:
                return i
        return None

    def _set_hover(self, i):
        if i == self.hover:
            return
        self.hover = i
        if i is not None:
            self._kb = False          # mouse dipakai: bingkai fokus keyboard disembunyikan
        ok = i is not None and self.cards[i]["ok"]
        self.cv.config(cursor="hand2" if ok else "")
        self._draw_cards()

    def _motion(self, e):
        bx0, by0, bx1, by1 = self._btn
        if bx0 <= e.x < bx1 and by0 <= e.y < by1:
            return
        self._set_hover(self._index_at(e.x, e.y))

    def _fade(self):
        """Tanpa animasi muncul: panel langsung penuh (lihat _build)."""
        try:
            self.attributes("-alpha", 1.0)
        except Exception:
            pass

    def _move(self, d):
        ok = [i for i, c in enumerate(self.cards) if c["ok"]]
        if not ok:
            return
        self._kb = True
        cur = ok.index(self.sel) if self.sel in ok else 0
        self.sel = ok[(cur + d) % len(ok)]
        self.hover = None
        self._draw_cards()

    def _click(self, e):
        i = self._index_at(e.x, e.y)
        if i is not None:
            self._choose(i)

    def _choose(self, i):
        if i is None or not self.cards[i]["ok"]:
            return
        key = self.cards[i]["key"]
        widget, student = self.widget, self.student
        self.close()
        W.open_browser(widget, student, profile=key)
