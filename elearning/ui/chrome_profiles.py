"""Popup "Who's using Chrome?" (layar murid, English): pilih profil Chrome sebelum browsing.

Meniru pemilih profil Chrome asli (mode gelap): latar #1f1f1f dengan cahaya warna lembut di
tepi (hijau kiri, kuning atas, merah muda kanan atas, biru kanan bawah, teal kiri bawah),
logo Chrome ASLI dari PC, judul + paragraf, kartu abu-abu (#3c4043) bersudut membulat: nama
tebal di atas, titik tiga di pojok, avatar bulat (foto akun Google kalau ada), email di bawah.
Fokus = bingkai biru (#a8c7fa); tombol "Close" berbingkai biru di kiri bawah (seperti
"Guest mode"). Semua bentuk antialias (numpy / round_mask), TANPA ImageDraw.

Kartu = profil Chrome MILIK MURID (web_launcher.chrome_profiles, maks. WEB_MAX_PROFILES):
  - klik kartu / Enter = buka Chrome biasa dengan profil itu (web_launcher.open_browser);
    url (mis. Gemini dari flyout, murid belum punya profil) dibuka sebagai tab setelahnya;
  - titik tiga (atau Delete) = hapus profil, dengan konfirmasi gaya dialog Chrome di panel;
  - kartu "Add" putus-putus (seperti Chrome) = profil baru + halaman login Google.
Esc = tutup (atau batal di dialog hapus). Batas browsing habis -> popup tidak dibuka (pesan).
"""

import os
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
BLUE_TEXT = "#062e6f"
DOTS = "#8e9399"
ADD_CIRCLE = "#a8abaf"
DIALOG = "#2d2f31"
CARD_W, CARD_H, GAP, CARD_R = 162, 178, 16, 8
AVATAR = 74
# warna avatar huruf (profil tanpa foto), dipilih tetap per folder profil
COLORS = ("#5565bd", "#0b8043", "#b0569a", "#c26401", "#007b83", "#7b5cc4")
# cahaya tepi: (x, y relatif panel, jari-jari relatif lebar, warna, kekuatan)
GLOWS = ((-0.04, 0.42, 0.30, (40, 120, 70), 0.55),       # hijau kiri
         (0.62, -0.10, 0.30, (150, 120, 30), 0.45),      # kuning atas
         (1.02, 0.02, 0.26, (150, 90, 120), 0.55),       # merah muda kanan atas
         (1.04, 0.86, 0.32, (70, 90, 170), 0.55),        # biru kanan bawah
         (-0.02, 1.02, 0.30, (40, 120, 115), 0.50))      # teal kiri bawah
_cache = {}


def open_chrome_profiles(widget, student, url=None):
    """Popup profil Chrome; None kalau tidak dibuka (batas browsing habis / diblokir guru)."""
    if not student or W._browse_blocked(widget.winfo_toplevel(), student["id"]):
        return None
    return open_overlay(ChromeProfiles, widget.winfo_toplevel(),
                        {"widget": widget, "student": student, "url": url})


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
    """Garis tepi putus-putus (kartu "Add" Chrome)."""
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


def _circle(color, size=AVATAR):
    key = ("circle", color, size)
    if key not in _cache:
        img = photos.Image.new("RGBA", (size, size), I._rgb(color) + (0,))
        img.putalpha(I.round_mask(size, size, size / 2))
        _cache[key] = photos.to_photoimage(img)
    return _cache[key]


def _add_circle():
    """Lingkaran abu terang + tanda plus gelap tebal (kartu "Add" Chrome), antialias."""
    key = ("add",)
    if key not in _cache:
        Image = photos.Image
        img = Image.new("RGBA", (AVATAR, AVATAR), I._rgb(ADD_CIRCLE) + (0,))
        img.putalpha(I.round_mask(AVATAR, AVATAR, AVATAR / 2))
        L_, T_ = 24, 4
        bar = Image.new("RGBA", (L_, T_), I._rgb("#202124") + (255,))
        bar.putalpha(I.round_mask(L_, T_, T_ / 2))
        o = (AVATAR - L_) // 2, (AVATAR - T_) // 2
        img.alpha_composite(bar, o)
        img.alpha_composite(bar.rotate(90, expand=True), (o[1], o[0]))
        _cache[key] = photos.to_photoimage(img)
    return _cache[key]


def _picture(path):
    """Foto akun Google (bulat, dipotong tengah) atau None."""
    try:
        key = ("pic", path, os.path.getmtime(path))
    except OSError:
        return None
    if key not in _cache:
        ph = None
        try:
            Image = photos.Image
            with Image.open(path) as im:
                img = im.convert("RGB")
            s = min(img.size)
            x0, y0 = (img.width - s) // 2, (img.height - s) // 2
            img = img.crop((x0, y0, x0 + s, y0 + s)).resize((AVATAR, AVATAR), Image.LANCZOS)
            img = img.convert("RGBA")
            img.putalpha(I.round_mask(AVATAR, AVATAR, AVATAR / 2))
            ph = photos.to_photoimage(img)
        except Exception as exc:
            C.log(f"Chrome: foto profil tidak terbaca: {exc!r}")
        _cache[key] = ph
    return _cache[key]


def _dim(w, h):
    """Lapisan gelap di atas panel saat dialog hapus terbuka (ikut sudut bulat panel)."""
    key = ("dim", w, h)
    if key not in _cache:
        img = photos.Image.new("RGBA", (w, h), (0, 0, 0, 0))
        img.putalpha(I.round_mask(w, h, RADIUS).point(lambda v: v * 150 // 255))
        _cache[key] = photos.to_photoimage(img)
    return _cache[key]


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


class ChromeProfiles(OverlayPanel):
    def _focus_target(self):
        return self.cv

    def _build(self, top, opts):
        self.widget = opts["widget"]
        self.student = opts["student"]
        self.url = opts.get("url")
        fam = C.FONT
        self.f = {"h": tkfont.Font(family=fam, size=17),
                  "sub": tkfont.Font(family=fam, size=11),
                  "tag": tkfont.Font(family=fam, size=9, weight="bold"),
                  "name": tkfont.Font(family=fam, size=10),
                  "btn": tkfont.Font(family=fam, size=10, weight="bold"),
                  "dlg": tkfont.Font(family=fam, size=14),
                  "av": tkfont.Font(family="Segoe UI Light" if fam == "Segoe UI" else fam,
                                    size=27)}
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
        self.hover = None
        self.hover_dots = None
        self.modal = None             # dialog hapus: {"card", "focus", "btns", "box"}
        cv = self.cv
        W_, H_ = self.W, self.H
        cv.create_image(0, 0, image=_background(W_, H_), anchor="nw")
        # blok logo + judul + paragraf + kartu di TENGAH panel (di atas baris tombol bawah)
        block = 46 + 40 + 44 + 52 + CARD_H
        cy = int(max(46, (H_ - 76 - block) / 2 + 23))
        self._card_y = cy + 160
        logo = W.chrome_logo(46)
        if logo is not None:
            ph = photos.to_photoimage(logo)            # RGBA di atas latar bergradasi
            cv._imgs.append(ph)
            cv.create_image(W_ / 2, cy, image=ph)
        cv.create_text(W_ / 2, cy + 62, text="Who's using Chrome?", font=self.f["h"], fill=TEXT)
        sub = ("Choose your profile to open Chrome, or add your own Google account. Each "
               "profile keeps its own bookmarks, history and sign-in.")
        if W._safe_rules(self.student):
            sub += " SafeSearch is on."
        cv.create_text(W_ / 2, cy + 106, font=self.f["sub"], fill=SUB, justify="center",
                       width=min(500, W_ - 80), text=sub)
        self._load_cards()
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
        st = "No limit" if W.unlimited(self.student) else             W.status_text(self.student.get("id"), "pinterest")
        cv.create_text(W_ - 36, by + bh / 2, anchor="e", font=self.f["sub"], fill=SUB,
                       text=f"Browsing  ·  {st}" if st else "Browsing")
        cv.bind("<Motion>", self._motion)
        cv.bind("<Leave>", lambda e: self._set_hover(None, None))
        cv.bind("<Button-1>", self._click)
        self.bind("<Escape>", lambda e: self._escape())
        self.bind("<Return>", lambda e: self._enter())
        self.bind("<Left>", lambda e: self._move(-1))
        self.bind("<Right>", lambda e: self._move(1))
        self.bind("<Tab>", lambda e: self._move(1) or "break")
        self.bind("<Delete>", lambda e: self._kb and self._ask_delete(self.sel))
        self._reveal()

    # --- data & susunan kartu ------------------------------------------------------------
    def _load_cards(self):
        self.cards = []
        for n, p in enumerate(W.chrome_profiles(self.student["id"])):
            email = p["email"]
            title = p["name"] or (email.split("@")[0] if email else f"Person {n + 1}")
            col = COLORS[sum(map(ord, p["dir"])) % len(COLORS)]
            self.cards.append({"kind": "profile", "dir": p["dir"], "title": title,
                               "sub": email or "Not signed in", "signed": bool(email),
                               "letter": title[:1].upper(), "color": col,
                               "picture": p["picture"]})
        if len(self.cards) < W.max_profiles():
            self.cards.append({"kind": "add", "title": "Add"})
        n = len(self.cards)
        avail = self.W - 64
        cw = CARD_W
        if n * CARD_W + (n - 1) * GAP > avail:       # layar sempit: kartu sedikit dirampingkan
            cw = max(124, int((avail - (n - 1) * GAP) / n))
        x = (self.W - (n * cw + (n - 1) * GAP)) / 2
        y = self._card_y
        for i, c in enumerate(self.cards):
            c["rect"] = (x + i * (cw + GAP), y, x + i * (cw + GAP) + cw, y + CARD_H)
        self.sel = 0 if self.cards else None
        self.hover = self.hover_dots = None
        self._draw_cards()

    # --- gambar kartu -------------------------------------------------------------------
    def _draw_cards(self):
        cv = self.cv
        cv.delete("card")
        live = self.modal is None
        for i, c in enumerate(self.cards):
            x0, y0, x1, y1 = c["rect"]
            w, h = int(x1 - x0), int(y1 - y0)
            cx = (x0 + x1) / 2
            hot = live and i == self.hover
            acy = y0 + 24 + 16 + AVATAR / 2
            if c["kind"] == "add":                 # kartu "Add": putus-putus, plus di lingkaran
                if hot:
                    cv.create_image(x0, y0, anchor="nw", tags="card",
                                    image=_rgba_shape(w, h, "#ffffff", CARD_R, 14))
                cv.create_image(x0, y0, anchor="nw", tags="card",
                                image=_dashed_ring(w, h, "#8e9399", CARD_R))
                cv.create_text(cx, y0 + 24, text="Add", font=self.f["tag"], fill=TEXT,
                               tags="card")
                cv.create_image(cx, acy, image=_add_circle(), tags="card")
            else:
                cv.create_image(x0, y0, anchor="nw", tags="card",
                                image=_rgba_shape(w, h, CARD_HOVER if hot else CARD, CARD_R))
                if live and i == self.hover_dots:      # sorot titik tiga (= hapus)
                    cv.create_image(x1 - 14, y0 + 17, image=_circle("#5f6368", 26),
                                    tags="card")
                cv.create_image(x1 - 14, y0 + 17, image=_dots(), tags="card")
                cv.create_text(cx, y0 + 24, text=self._fit(c["title"], w - 56, "tag"),
                               font=self.f["tag"], fill=TEXT, tags="card")
                pic = _picture(c["picture"]) if c["picture"] else None
                if pic is not None:
                    cv.create_image(cx, acy, image=pic, tags="card")
                else:
                    cv.create_image(cx, acy, image=_circle(c["color"]), tags="card")
                    if c["signed"]:
                        cv.create_text(cx, acy - 1, text=c["letter"], font=self.f["av"],
                                       fill="#ffffff", tags="card")
                    else:
                        ic = _clear_icon("user", "#ffffff", 34)
                        if ic is not None:
                            cv.create_image(cx, acy, image=ic, tags="card")
                cv.create_text(cx, y1 - 26, text=self._fit(c["sub"], w - 20),
                               font=self.f["name"], fill=TEXT if c["signed"] else SUB,
                               tags="card")
            if live and i == self.sel and self._kb and self.hover is None:
                cv.create_image(x0 - 3, y0 - 3, anchor="nw", tags="card",
                                image=_ring(w + 6, h + 6, BLUE, CARD_R + 3, 2))
        cv.tag_raise("modal")

    def _fit(self, text, width, font="name"):
        f = self.f[font]
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

    def _on_dots(self, i, x, y):
        if i is None or self.cards[i]["kind"] != "profile":
            return False
        x0, y0, x1, y1 = self.cards[i]["rect"]
        return x1 - 30 <= x < x1 and y0 <= y < y0 + 34

    def _in_close_btn(self, x, y):
        bx0, by0, bx1, by1 = self._btn
        return bx0 <= x < bx1 and by0 <= y < by1

    def _set_hover(self, i, dots, cursor=None):
        hand = i is not None or bool(cursor)
        self.cv.config(cursor="hand2" if hand else "")
        if (i, dots) == (self.hover, self.hover_dots):
            return
        self.hover, self.hover_dots = i, dots
        if i is not None:
            self._kb = False          # mouse dipakai: bingkai fokus keyboard disembunyikan
        self._draw_cards()

    def _motion(self, e):
        if self.modal is not None:
            self._modal_motion(e)
            return
        if self._in_close_btn(e.x, e.y):
            self._set_hover(None, None, cursor=True)
            return
        i = self._index_at(e.x, e.y)
        self._set_hover(i, i if self._on_dots(i, e.x, e.y) else None)

    def _fade(self):
        """Tanpa animasi muncul: panel langsung penuh (lihat _build)."""
        try:
            self.attributes("-alpha", 1.0)
        except Exception:
            pass

    def _move(self, d):
        if self.modal is not None:
            self.modal["focus"] = (self.modal["focus"] + d) % 2
            self.modal["kb"] = True
            self._draw_modal()
            return
        if not self.cards:
            return
        self._kb = True
        self.sel = ((self.sel or 0) + d) % len(self.cards)
        self.hover = self.hover_dots = None
        self._draw_cards()

    def _click(self, e):
        if self.modal is not None:
            self._modal_click(e)
            return
        if self._in_close_btn(e.x, e.y):
            self.close()
            return
        i = self._index_at(e.x, e.y)
        if i is None:
            return
        if self._on_dots(i, e.x, e.y):
            self._ask_delete(i)
        else:
            self._choose(i)

    def _enter(self):
        if self.modal is not None:
            self._modal_action(self.modal["focus"])
        else:
            self._choose(self.sel)

    def _escape(self):
        if self.modal is not None:
            self._close_modal()
        else:
            self.close()

    def _choose(self, i):
        if i is None or i >= len(self.cards):
            return
        c = self.cards[i]
        widget, student = self.widget, self.student
        self.close()
        if c["kind"] == "add":
            W.add_profile(widget, student, then_url=self.url)
        else:
            W.open_browser(widget, student, c["dir"], url=self.url)

    # --- dialog hapus (gaya dialog Chrome, di dalam panel) -------------------------------
    def _ask_delete(self, i):
        if i is None or i >= len(self.cards) or self.cards[i]["kind"] != "profile":
            return
        # fokus awal: Cancel; bingkai fokus hanya kalau dibuka / dipakai lewat keyboard
        self.modal = {"card": self.cards[i], "focus": 0, "kb": self._kb}
        self.hover = self.hover_dots = None
        self.cv.config(cursor="")
        self._draw_cards()
        self._draw_modal()

    def _draw_modal(self):
        cv = self.cv
        cv.delete("modal")
        m = self.modal
        if m is None:
            return
        W_, H_ = self.W, self.H
        cv.create_image(0, 0, anchor="nw", image=_dim(W_, H_), tags="modal")
        dw, dh = 420, 178
        x0, y0 = (W_ - dw) // 2, (H_ - dh) // 2
        m["box"] = (x0, y0, x0 + dw, y0 + dh)
        cv.create_image(x0, y0, anchor="nw", image=_rgba_shape(dw, dh, DIALOG, 16),
                        tags="modal")
        c = m["card"]
        who = c["title"] + (f" ({c['sub']})" if c["signed"] and c["sub"] != c["title"] else "")
        cv.create_text(x0 + 26, y0 + 34, anchor="w", text="Delete this profile?",
                       font=self.f["dlg"], fill=TEXT, tags="modal")
        cv.create_text(x0 + 26, y0 + 60, anchor="nw", width=dw - 52, font=self.f["name"],
                       fill=SUB, tags="modal",
                       text=f"{who} will be removed from this computer, with its bookmarks, "
                            "history and saved sign-ins.")
        bw, bh = 92, 36
        by = y0 + dh - 26 - bh
        right = x0 + dw - 26                      # kanan: Delete; kirinya: Cancel
        m["btns"] = [(right - 2 * bw - 10, by, right - bw - 10, by + bh),
                     (right - bw, by, right, by + bh)]
        for k, label in enumerate(("Cancel", "Delete")):
            bx0, by0, bx1, by1 = m["btns"][k]
            if k == 1:
                cv.create_image(bx0, by0, anchor="nw", tags="modal",
                                image=_rgba_shape(bw, bh, BLUE, bh // 2))
            else:
                cv.create_image(bx0, by0, anchor="nw", tags="modal",
                                image=_ring(bw, bh, "#8e918f", bh // 2, 1))
            if k == m["focus"] and m["kb"]:
                cv.create_image(bx0 - 3, by0 - 3, anchor="nw", tags="modal",
                                image=_ring(bw + 6, bh + 6, BLUE, bh // 2 + 3, 2))
            cv.create_text((bx0 + bx1) / 2, by0 + bh / 2, text=label, font=self.f["btn"],
                           fill=BLUE_TEXT if k == 1 else BLUE, tags="modal")
        cv.tag_raise("modal")

    def _modal_hit(self, x, y):
        for k, (x0, y0, x1, y1) in enumerate(self.modal.get("btns", ())):
            if x0 <= x < x1 and y0 <= y < y1:
                return k
        return None

    def _modal_motion(self, e):
        self.cv.config(cursor="hand2" if self._modal_hit(e.x, e.y) is not None else "")

    def _modal_click(self, e):
        k = self._modal_hit(e.x, e.y)
        if k is not None:
            self._modal_action(k)
            return
        x0, y0, x1, y1 = self.modal["box"]
        if not (x0 <= e.x < x1 and y0 <= e.y < y1):
            self._close_modal()             # klik di luar dialog = batal

    def _modal_action(self, k):
        card = self.modal["card"]
        self._close_modal()
        if k == 1:
            W.delete_profile(self.student, card["dir"])
            self._load_cards()

    def _close_modal(self):
        self.modal = None
        self.cv.delete("modal")
        self.cv.config(cursor="")
        self._draw_cards()
