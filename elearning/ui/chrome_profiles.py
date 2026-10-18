"""Popup "Who's using Chrome?" (layar murid, English): pilih profil Chrome sebelum Pinterest.

Gaya mirip pemilih profil Chrome asli tapi minimalis & konsisten dengan aplikasi (overlay
bersudut bulat + latar redup, sama dengan search palette): logo Chrome asli dari PC, judul,
lalu kartu profil:
  - Teacher  : Pinterest akun guru / studio (config.WEB_STUDIO_ACCOUNT) -> semua murid.
  - Personal : akun Google murid sendiri -> hanya program WEB_OWN_PROFILE_PROGRAMS (dewasa);
               SUPERKIDS melihat kartu ini terkunci ("Adults only").
Klik kartu / Enter = buka Pinterest dengan profil itu (web_launcher.open_web). Esc = tutup.
"""

import tkinter as tk
import tkinter.font as tkfont

from elearning import config as C
from elearning import photos
from elearning import web_launcher as W
from elearning.ui import ui_icons as I
from elearning.ui.search_palette import KEY, RADIUS, OverlayPanel, open_overlay

CARD_W, CARD_H, GAP = 176, 200, 16
AVATAR = 76
STUDIO_COLOR = "#5f6fd6"      # ungu-biru seperti avatar profil Chrome


def open_chrome_profiles(widget, student):
    return open_overlay(ChromeProfiles, widget.winfo_toplevel(), {"widget": widget,
                                                                  "student": student})


def _initials(name):
    parts = [p for p in str(name).replace(".", " ").split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


class ChromeProfiles(OverlayPanel):
    def _focus_target(self):
        return self.cv

    def _build(self, top, opts):
        self.widget = opts["widget"]
        self.student = opts["student"]
        self.f = {"h": tkfont.Font(family=C.FONT, size=17),
                  "sub": tkfont.Font(family=C.FONT, size=10),
                  "tag": tkfont.Font(family=C.FONT, size=9, weight="bold"),
                  "name": tkfont.Font(family=C.FONT, size=10),
                  "small": tkfont.Font(family=C.FONT, size=8),
                  "av": tkfont.Font(family=C.FONT, size=26)}
        name = self.student.get("name", "")
        self.cards = []
        for key, ok in W.profiles_for(self.student):
            if key == "studio":
                self.cards.append({"key": key, "ok": ok, "tag": "Teacher",
                                   "name": getattr(C, "WEB_STUDIO_NAME", "Teacher"),
                                   "sub": "Teacher's Pinterest", "letter": "M",
                                   "color": STUDIO_COLOR})
            else:
                self.cards.append({"key": key, "ok": ok, "tag": "Personal", "name": name,
                                   "sub": "Your Google account" if ok else "Adults only",
                                   "letter": _initials(name), "color": "#3f8f6a"})
        n = len(self.cards)
        want_w = max(460, n * CARD_W + (n - 1) * GAP + 96)
        self._make_window(top, want_w, 430, min_w=420, min_h=400)
        cv = self.cv
        W_, H_ = self.W, self.H
        panel = I.pill(W_, H_, C.CARD, KEY, r=RADIUS, border=C.BORDER)
        if panel is not None:
            cv._imgs.append(panel)
            cv.create_image(0, 0, image=panel, anchor="nw")
        logo = W.chrome_logo(46)
        if logo is not None:
            bg = photos.Image.new("RGBA", logo.size, I._rgb(C.CARD) + (255,))
            bg.alpha_composite(logo)
            ph = photos.to_photoimage(bg.convert("RGB"))
            cv._imgs.append(ph)
            cv.create_image(W_ / 2, 46, image=ph)
        cv.create_text(W_ / 2, 94, text="Who's using Chrome?", font=self.f["h"], fill=C.TEXT)
        cv.create_text(W_ / 2, 122, font=self.f["sub"], fill=C.MUTED,
                       text="Pinterest opens with the profile you choose.")
        x = (W_ - (n * CARD_W + (n - 1) * GAP)) / 2
        y = 160
        self.hover = None
        self.sel = next((i for i, c in enumerate(self.cards) if c["ok"]), None)
        for i, c in enumerate(self.cards):
            c["rect"] = (x + i * (CARD_W + GAP), y, x + i * (CARD_W + GAP) + CARD_W, y + CARD_H)
        self._draw()
        cv.create_text(W_ / 2, H_ - 26, font=self.f["small"], fill=C.LOCKED,
                       text="Esc to close  ·  Enter to open")
        cv.bind("<Motion>", self._motion)
        cv.bind("<Leave>", lambda e: self._set_hover(None))
        cv.bind("<Button-1>", self._click)
        for k in ("<Escape>",):
            self.bind(k, lambda e: self.close())
        self.bind("<Return>", lambda e: self._choose(self.sel))
        self.bind("<Left>", lambda e: self._move(-1))
        self.bind("<Right>", lambda e: self._move(1))
        self._reveal()

    # --- gambar kartu -------------------------------------------------------------------
    @staticmethod
    def _avatar(color, ok, bg):
        # latar = warna kartu (biasa / disorot); I.dot menyimpan gambarnya sendiri (cache)
        return I.dot(color if ok else "#4a4945", bg, AVATAR, AVATAR / 2 - 0.5)

    def _draw(self):
        cv = self.cv
        cv.delete("card")
        for i, c in enumerate(self.cards):
            x0, y0, x1, y1 = c["rect"]
            hot = c["ok"] and (i == self.hover or (self.hover is None and i == self.sel))
            body = I.pill(int(x1 - x0), int(y1 - y0), C.CARD_HOVER if hot else C.BG, C.CARD,
                          r=14, border=C.ACCENT if hot else C.BORDER)
            if body is not None:          # (I.pill menyimpan gambarnya di cache ui_icons)
                cv.create_image(x0, y0, image=body, anchor="nw", tags="card")
            cx = (x0 + x1) / 2
            dim = not c["ok"]
            cv.create_text(cx, y0 + 22, text=c["tag"], font=self.f["tag"],
                           fill=C.LOCKED if dim else C.TEXT, tags="card")
            av = self._avatar(c["color"], c["ok"], C.CARD_HOVER if hot else C.BG)
            if av is not None:
                cv.create_image(cx, y0 + 34 + AVATAR / 2, image=av, tags="card")
            cv.create_text(cx, y0 + 34 + AVATAR / 2, text=c["letter"], font=self.f["av"],
                           fill="#ffffff" if c["ok"] else "#8f8b82", tags="card")
            if dim:     # gembok kecil di pojok avatar
                lk = I.icon("lock", C.MUTED, C.CARD_HOVER if hot else C.BG, 16)
                if lk is not None:
                    cv.create_image(cx + AVATAR / 2 - 6, y0 + 34 + AVATAR - 8, image=lk,
                                    tags="card")
            cv.create_text(cx, y0 + 140, text=self._fit(c["name"], CARD_W - 20),
                           font=self.f["name"], fill=C.LOCKED if dim else C.TEXT, tags="card")
            cv.create_text(cx, y0 + 162, text=c["sub"], font=self.f["small"],
                           fill=C.LOCKED if dim else C.MUTED, tags="card")

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
        ok = i is not None and self.cards[i]["ok"]
        self.cv.config(cursor="hand2" if ok else "")
        self._draw()

    def _motion(self, e):
        self._set_hover(self._index_at(e.x, e.y))

    def _move(self, d):
        ok = [i for i, c in enumerate(self.cards) if c["ok"]]
        if not ok:
            return
        cur = ok.index(self.sel) if self.sel in ok else 0
        self.sel = ok[(cur + d) % len(ok)]
        self.hover = None
        self._draw()

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
        W.open_web(widget, student, "pinterest", profile=key)
