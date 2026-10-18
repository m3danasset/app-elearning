"""Sidebar kiri gaya claude.ai, dipakai SEMUA peran: admin, guru, murid, dan trial.

Susunan (atas -> bawah):
  1. Logo brand (assets\\logo.png; cadangan: logo M3DAN bawaan) + tombol lipat sidebar
  2. Kolom cari (Ctrl+K untuk langsung mengetik, Esc untuk mengosongkan)
  3. Menu utama (ikon + teks)
  4. Daftar bergulir per bagian (kursus, pelajaran, murid, yang sedang online, ...)
  5. Item tambahan di dasar (mis. "Buka Blender" untuk murid)
  6. Profil di paling bawah: foto + nama + peran; klik = menu (Keluar)

Sidebar bisa dilipat jadi rel ikon (lebar 60 px); pilihan lipat diingat selama aplikasi
terbuka. Isi menu dan daftar diberikan oleh layar lewat fungsi populate(sb), yang
memanggil sb.nav(), sb.section(), sb.item(), sb.note(), sb.footer().
"""

import tkinter as tk
import tkinter.font as tkfont

from elearning.i18n import L
from elearning import config as C
from elearning import brand, photos
from elearning.ui import ui_icons as I
from elearning.ui.avatar import PALETTE, initials
from elearning.ui.widgets import ScrollFrame

EXPANDED_W = 268
COLLAPSED_W = 60
ROW_H = 34

_state = {"collapsed": False}   # dilipat / dibuka, sama untuk semua layar
_current = {"sb": None}         # sidebar yang sedang tampil (untuk Ctrl+K)


def _font(size=10, weight="normal"):
    return (C.FONT, size, weight)


def _bind_tree(widget, seq, fn):
    """Pasang binding di widget dan semua anaknya (logo = beberapa label)."""
    widget.bind(seq, fn, add="+")
    for child in widget.winfo_children():
        _bind_tree(child, seq, fn)


def _fit_text(font, text, avail):
    """Potong teks dengan "..." supaya muat di lebar avail (px)."""
    if font.measure(text) <= avail:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if font.measure(text[:mid].rstrip() + "...") <= avail:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + "..."


# --- tooltip (untuk rel ikon saat sidebar dilipat) -----------------------------------
class _Tip:
    DELAY = 450

    def __init__(self, widget, text):
        self.widget, self.text = widget, text
        self.win = None
        self.job = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def _schedule(self, _e=None):
        self._hide()
        self.job = self.widget.after(self.DELAY, self._show)

    def _show(self):
        self.job = None
        try:
            w = self.widget
            x = w.winfo_rootx() + w.winfo_width() + 8
            y = w.winfo_rooty() + w.winfo_height() // 2
            win = self.win = tk.Toplevel(w)
            win.overrideredirect(True)
            win.configure(bg=C.BORDER)
            tk.Label(win, text=self.text, bg="#141413", fg=C.TEXT, font=_font(9),
                     padx=9, pady=4).pack(padx=1, pady=1)
            win.update_idletasks()
            win.geometry(f"+{x}+{y - win.winfo_reqheight() // 2}")
            win.attributes("-topmost", True)
        except Exception:
            self.win = None

    def _hide(self, _e=None):
        if self.job is not None:
            try:
                self.widget.after_cancel(self.job)
            except Exception:
                pass
            self.job = None
        if self.win is not None:
            try:
                self.win.destroy()
            except Exception:
                pass
            self.win = None


# --- satu baris: menu / kursus / pelajaran / murid ----------------------------------
class Row(tk.Canvas):
    """Baris sidebar: latar membulat saat dipilih / disorot, ikon atau titik warna di kiri,
    teks (dipotong "..." kalau kepanjangan; marquee=True -> berjalan saat disorot),
    dan teks / ikon kecil di kanan (jumlah, gembok)."""

    STEP_MS, STEP_PX, START_DELAY = 30, 2, 350

    def __init__(self, master, text, command=None, *, icon=None, icon_color=None,
                 icon_disc=None, image=None, dot=None, right=None, right_icon=None,
                 active=False, dim=False, indent=0, marquee=False, height=ROW_H,
                 bg=C.SIDEBAR, hover=C.SIDEBAR_HOVER, sel=C.SIDEBAR_ACTIVE,
                 font=None, fg=None):
        super().__init__(master, height=height, width=40, bg=bg, highlightthickness=0, bd=0,
                         cursor="hand2" if command else "")
        self.text, self.command = text, command
        self.icon, self.icon_color, self.icon_disc = icon, icon_color, icon_disc
        self.image, self.dot, self.right, self.right_icon = image, dot, right, right_icon
        self.active, self.dim, self.indent, self.marquee = active, dim, indent, marquee
        self.colors = (bg, hover, sel)
        self.fg = fg or (C.LOCKED if dim else C.TEXT)
        self._font = tkfont.Font(font=font or _font(10))
        self._small = tkfont.Font(font=_font(9))
        self._hover = False
        self._job = None
        self._imgs = []
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Destroy>", lambda e: self._stop(), add="+")
        if command is not None:
            self.bind("<Enter>", self._enter)
            self.bind("<Leave>", self._leave)
            self.bind("<Button-1>", lambda e: self.command())

    def _fill(self):
        bg, hover, sel = self.colors
        if self.active:
            return sel
        return hover if self._hover else bg

    def _draw(self):
        self._stop()
        w, h = self.winfo_width(), self.winfo_height()
        if w < 8:
            return
        self.delete("all")
        self._imgs = []
        bg = self.colors[0]
        fill = self._fill()
        self._fill_now = fill
        if fill != bg:
            p = I.pill(w, h, fill, bg)
            if p is not None:
                self._imgs.append(p)
                self.create_image(0, 0, image=p, anchor="nw")
            else:
                self.create_rectangle(0, 0, w, h, fill=fill, outline=fill)
        cy = h / 2
        x = 10 + self.indent
        if self.icon:
            ph = I.icon(self.icon, self.icon_color or (C.MUTED if self.dim else C.TEXT), fill,
                        18 if not self.icon_disc else 22, self.icon_disc)
            if ph is not None:
                self._imgs.append(ph)
                self.create_image(x + 10, cy, image=ph, tags="deco")
            x += 30
        elif self.image is not None:
            self.create_image(x + 10, cy, image=self.image, tags="deco")
            x += 30
        elif self.dot:
            ph = I.dot(self.dot, fill)
            if ph is not None:
                self._imgs.append(ph)
                self.create_image(x + 5, cy, image=ph, tags="deco")
            x += 20
        else:
            x += 2
        right_edge = w - 10
        if self.right_icon:
            ph = I.icon(self.right_icon, C.LOCKED if self.dim else C.MUTED, fill, 16)
            if ph is not None:
                self._imgs.append(ph)
                self.create_image(right_edge - 8, cy, image=ph, tags="deco")
            right_edge -= 22
        if self.right:
            self.create_text(right_edge, cy, text=self.right, anchor="e", fill=C.MUTED,
                             font=self._small, tags="deco")
            right_edge -= self._small.measure(self.right) + 10
        self._tx, self._avail = x, max(10, right_edge - x)
        self._item = self.create_text(x, cy, anchor="w", font=self._font, fill=self.fg,
                                      text=_fit_text(self._font, self.text, self._avail))

    def _enter(self, _e):
        self._hover = True
        self._draw()
        if self.marquee and self._font.measure(self.text) > self._avail:
            self._job = self.after(self.START_DELAY, self._start_marquee)

    def _leave(self, _e):
        self._hover = False
        self._draw()

    # --- teks berjalan (nama pelajaran panjang) --------------------------------------
    def _mask(self, x0, x1):
        """Tutup di kiri/kanan area teks supaya teks berjalan tidak menimpa ikon / tepi."""
        w, h = self.winfo_width(), self.winfo_height()
        bg, fill = self.colors[0], self._fill_now
        if fill != bg:
            ph = I.pill_crop(w, h, fill, bg, x0, x1)
            if ph is not None:
                self._imgs.append(ph)
                self.create_image(x0, 0, image=ph, anchor="nw", tags="mask")
                return
        self.create_rectangle(x0, 0, x1, h, fill=fill, outline=fill, tags="mask")

    def _start_marquee(self):
        self._job = None
        self.itemconfigure(self._item, text=self.text)
        self._mask(0, self._tx - 1)
        self._mask(self._tx + self._avail + 1, self.winfo_width())
        self.tag_raise("deco")
        self._x = self._tx
        self._tick()

    def _tick(self):
        self._job = None
        end = self._tx + self._avail - self._font.measure(self.text)
        if self._x <= end:
            return   # ujung teks sudah terlihat: diam sampai kursor pergi
        self._x = max(end, self._x - self.STEP_PX)
        self.coords(self._item, self._x, self.winfo_height() / 2)
        self._job = self.after(self.STEP_MS, self._tick)

    def _stop(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None


class IconButton(tk.Canvas):
    """Tombol ikon persegi (rel sidebar dilipat, tombol lipat di kepala sidebar)."""

    def __init__(self, master, icon, command, *, active=False, tip=None, size=(40, 36),
                 bg=C.SIDEBAR, image=None, disc=None, icon_color=None, hover_icon=None):
        w, h = size
        super().__init__(master, width=w, height=h, bg=bg, highlightthickness=0, bd=0,
                         cursor="hand2")
        self.icon, self.command, self.active = icon, command, active
        self.image, self.disc, self.icon_color = image, disc, icon_color
        self.hover_icon = hover_icon   # ikon pengganti saat disorot (logo -> tombol buka)
        self.bg, self._hover, self._imgs = bg, False, []
        self.bind("<Enter>", lambda e: self._set(True))
        self.bind("<Leave>", lambda e: self._set(False))
        self.bind("<Button-1>", lambda e: command())
        if tip:
            _Tip(self, tip)
        self._draw()

    def _set(self, hover):
        self._hover = hover
        self._draw()

    def _draw(self):
        self.delete("all")
        self._imgs = []
        w, h = int(self["width"]), int(self["height"])
        fill = C.SIDEBAR_ACTIVE if self.active else (C.SIDEBAR_HOVER if self._hover else self.bg)
        if fill != self.bg:
            p = I.pill(w, h, fill, self.bg)
            if p is not None:
                self._imgs.append(p)
                self.create_image(0, 0, image=p, anchor="nw")
        if self._hover and self.hover_icon:
            ph = I.icon(self.hover_icon, C.TEXT, fill, 18)
        elif self.image is not None:
            ph = self.image
        else:
            ph = I.icon(self.icon, self.icon_color or C.TEXT, fill,
                        22 if self.disc else 18, self.disc)
        if ph is not None:
            self._imgs.append(ph)
            self.create_image(w / 2, h / 2, image=ph)


class PillButton(tk.Canvas):
    """Tombol bersudut bulat untuk kepala halaman (mis. "+ Tambah guru", "Muat ulang")."""

    def __init__(self, master, text, command, *, primary=False, icon=None, bg=C.BG,
                 height=32):
        self._font = tkfont.Font(font=_font(10, "bold" if primary else "normal"))
        w = self._font.measure(text) + 28 + (24 if icon else 0)
        super().__init__(master, width=w, height=height, bg=bg, highlightthickness=0, bd=0,
                         cursor="hand2")
        self.text, self.command, self.icon, self.primary = text, command, icon, primary
        self.bg, self._hover, self._imgs = bg, False, []
        self.bind("<Enter>", lambda e: self._set(True))
        self.bind("<Leave>", lambda e: self._set(False))
        self.bind("<Button-1>", lambda e: self.command())
        self._draw()

    def _set(self, hover):
        self._hover = hover
        self._draw()

    def set(self, text=None, command=None):
        """Ganti teks / fungsi tombol tanpa membuat widget baru (tidak berkedip)."""
        if command is not None:
            self.command = command
        if text is not None and text != self.text:
            self.text = text
            w = self._font.measure(text) + 28 + (24 if self.icon else 0)
            super().configure(width=w)
        self._draw()

    def _draw(self):
        self.delete("all")
        self._imgs = []
        w, h = int(self["width"]), int(self["height"])
        if self.primary:
            fill = C.ACCENT_HOVER if self._hover else C.ACCENT
            fg, border = "#ffffff", None
        else:
            fill = C.CARD_HOVER if self._hover else C.CARD
            fg, border = C.TEXT, C.BORDER
        p = I.pill(w, h, fill, self.bg, r=9, border=border)
        if p is not None:
            self._imgs.append(p)
            self.create_image(0, 0, image=p, anchor="nw")
        x = 14
        if self.icon:
            ph = I.icon(self.icon, fg, fill, 16)
            if ph is not None:
                self._imgs.append(ph)
                self.create_image(x + 8, h / 2, image=ph)
            x += 24
        self.create_text(x, h / 2, text=self.text, anchor="w", fill=fg, font=self._font)


class PageHeader(tk.Frame):
    """Judul halaman di atas area isi (pengganti bar atas lama; tombol Keluar pindah ke profil)."""

    def __init__(self, master, title, sub=""):
        super().__init__(master, bg=C.BG, height=60)
        self.pack_propagate(False)
        self.actions = tk.Frame(self, bg=C.BG)
        self.actions.pack(side="right", padx=(8, 24))
        self.title_lbl = tk.Label(self, text=title, bg=C.BG, fg=C.TEXT, font=_font(14, "bold"),
                                  anchor="w")
        self.title_lbl.pack(side="left", padx=(28, 0))
        self.sub_lbl = tk.Label(self, text=sub, bg=C.BG, fg=C.MUTED, font=_font(10), anchor="w")
        self.sub_lbl.pack(side="left", padx=(10, 0), pady=(4, 0))

    def set_title(self, title, sub=""):
        self.title_lbl.config(text=title)
        self.sub_lbl.config(text=sub)

    def button(self, text, command, primary=False, icon=None):
        b = PillButton(self.actions, text, command, primary=primary, icon=icon)
        b.pack(side="right", padx=(8, 0))
        return b


# --- kolom cari ---------------------------------------------------------------------
class _Search(tk.Canvas):
    H = 36

    def __init__(self, master, sidebar, placeholder):
        super().__init__(master, height=self.H, width=40, bg=C.SIDEBAR, highlightthickness=0,
                         bd=0, cursor="xterm")
        self.sb = sidebar
        self._imgs = []
        self.focused = False
        self.var = tk.StringVar(value=sidebar.query)
        e = self.entry = tk.Entry(self, textvariable=self.var, bg=C.SEARCH_BG, fg=C.TEXT,
                                  insertbackground=C.TEXT, relief="flat", bd=0,
                                  highlightthickness=0, font=_font(10))
        # Jangan teruskan ketikan ke jendela utama (di sana tombol F = layar penuh video)
        e.bindtags((str(e), "Entry", "all"))
        self.ph = tk.Label(e, text=placeholder, bg=C.SEARCH_BG, fg=C.MUTED, font=_font(10),
                           cursor="xterm", bd=0, padx=0)
        self.ph.bind("<Button-1>", lambda ev: e.focus_set())
        self._win = self.create_window(36, self.H / 2, anchor="w", window=e, height=22)
        e.bind("<FocusIn>", lambda ev: self._focus(True))
        e.bind("<FocusOut>", lambda ev: self._focus(False))
        e.bind("<Escape>", self._escape)
        e.bind("<Return>", self._enter)
        e.bind("<Down>", lambda ev: self.sb._suggest_move(1))
        e.bind("<Up>", lambda ev: self.sb._suggest_move(-1))
        self.count = None   # jumlah hasil (ditampilkan di dalam kolom cari)
        self.bind("<Button-1>", self._click)
        self.bind("<Configure>", lambda ev: self._draw())
        self.var.trace_add("write", lambda *a: self._changed())
        if getattr(sidebar, "palette", False):   # klik kolom = buka search palette (Ctrl+K)
            for w in (self, e, self.ph):
                w.bind("<Button-1>", self._open_palette)
                w.config(cursor="hand2")
            e.bind("<FocusIn>", self._open_palette)
        self._placeholder()

    def _open_palette(self, _ev=None):
        from elearning.ui.search_palette import open_palette
        self.winfo_toplevel().focus_set()
        open_palette(self.sb.master)
        return "break"

    def _click(self, ev):
        if self.var.get() and ev.x > self.winfo_width() - 30:   # tombol x: kosongkan
            self.var.set("")
        self.entry.focus_set()

    def _enter(self, _ev):
        self.sb._enter_pressed()
        return "break"

    def _escape(self, _ev):
        if self.sb._suggest_visible():
            self.sb._hide_suggest()
            return "break"
        if self.var.get():
            self.var.set("")
        else:
            self.winfo_toplevel().focus_set()
        return "break"

    def _focus(self, on):
        self.focused = on
        self._draw()
        if not on:   # klik di luar: tutup saran (sedikit ditunda supaya klik saran tetap jalan)
            self.after(180, lambda: (not self.focused) and self.sb._hide_suggest())

    def _placeholder(self):
        if self.var.get():
            self.ph.place_forget()
        else:
            self.ph.place(x=1, rely=0.5, anchor="w")

    def _changed(self):
        self._placeholder()
        self._draw()
        self.sb._query_changed(self.var.get())

    def _draw(self):
        w = self.winfo_width()
        if w < 40:
            return
        self.delete("deco")
        self._imgs = []
        h = self.H
        border = "#5c5a55" if self.focused else C.BORDER
        p = I.pill(w, h, C.SEARCH_BG, C.SIDEBAR, r=9, border=border)
        if p is not None:
            self._imgs.append(p)
            self.create_image(0, 0, image=p, anchor="nw", tags="deco")
        ic = I.icon("search", C.MUTED, C.SEARCH_BG, 16)
        if ic is not None:
            self._imgs.append(ic)
            self.create_image(20, h / 2, image=ic, tags="deco")
        count_w = 0
        if self.var.get():
            x = I.icon("close", C.MUTED, C.SEARCH_BG, 14)
            if x is not None:
                self._imgs.append(x)
                self.create_image(w - 17, h / 2, image=x, tags="deco")
            if self.count is not None:
                txt = (f"{self.count} " + L("hasil", "results")) if self.count \
                    else L("0 hasil", "0 results")
                t = self.create_text(w - 32, h / 2, text=txt, anchor="e", font=_font(8),
                                     fill=C.ACCENT_HOVER if self.count else C.ERROR,
                                     tags="deco")
                b = self.bbox(t)
                count_w = (b[2] - b[0] + 8) if b else 0
        elif not self.focused:
            self.create_text(w - 12, h / 2, text="Ctrl+K", anchor="e", fill=C.LOCKED,
                             font=_font(8), tags="deco")
        self.tag_lower("deco")
        reserve = (34 + count_w) if (self.var.get() or self.focused) else 56   # x / hasil / Ctrl+K
        self.itemconfigure(self._win, width=max(20, w - 36 - reserve))


class _Suggest(tk.Toplevel):
    """Saran hasil cari di bawah kolom cari (satu canvas: tampil utuh, tanpa glitch).

    items: [{"title", "sub", "badge", "action"}]. Klik / Enter (setelah panah) = action().
    """

    ROW_H, W = 46, 340

    def __init__(self, sidebar):
        super().__init__(sidebar)
        self.sb = sidebar
        self.overrideredirect(True)
        self.configure(bg=C.BORDER)
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass
        self.cv = tk.Canvas(self, width=self.W, height=10, bg=C.CARD, highlightthickness=0,
                            bd=0)
        self.cv.pack(padx=1, pady=1)
        self.items = []
        self.sel = -1
        self._imgs = []
        self.cv.bind("<Motion>", self._motion)
        self.cv.bind("<Leave>", lambda e: self._select(-1))
        self.cv.bind("<Button-1>", self._click)
        self.withdraw()

    def show(self, items, query):
        self.items, self.sel = items, -1
        self._query = query.strip().lower()
        self._draw()
        anchor = self.sb._search
        x = anchor.winfo_rootx()
        y = anchor.winfo_rooty() + anchor.winfo_height() + 4
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.lift()

    def _draw(self):
        cv = self.cv
        cv.delete("all")
        self._imgs = []
        if not self.items:
            cv.configure(height=40)
            cv.create_text(14, 20, text=L("Tidak ada hasil", "No results"), anchor="w", fill=C.MUTED,
                           font=_font(10))
            return
        cv.configure(height=len(self.items) * self.ROW_H + 8)
        f_title, f_sub = tkfont.Font(font=_font(10)), tkfont.Font(font=_font(8))
        for i, it in enumerate(self.items):
            y = 4 + i * self.ROW_H
            if i == self.sel:
                p = I.pill(self.W - 8, self.ROW_H - 4, C.CARD_HOVER, C.CARD, r=8)
                self._imgs.append(p)
                cv.create_image(4, y + 2, image=p, anchor="nw")
            badge = it.get("badge", "")
            bw = 0
            if badge:
                bw = f_sub.measure(badge) + 16
                p = I.pill(bw, 18, C.SIDEBAR_ACTIVE, C.CARD_HOVER if i == self.sel else C.CARD,
                           r=9)
                self._imgs.append(p)
                cv.create_image(self.W - 12 - bw, y + self.ROW_H / 2 - 9, image=p, anchor="nw")
                cv.create_text(self.W - 12 - bw / 2, y + self.ROW_H / 2, text=badge,
                               fill=C.MUTED, font=f_sub)
            avail = self.W - 28 - bw - 8
            title = _fit_text(f_title, it["title"], avail)
            self._hl_text(14, y + 15, title, f_title, C.TEXT, it.get("hl", True))
            cv.create_text(14, y + 32, text=_fit_text(f_sub, it.get("sub", ""), avail),
                           anchor="w", fill=C.MUTED, font=f_sub)

    def _hl_text(self, x, y, text, font, fill, hl):
        """Teks dengan bagian yang cocok diberi latar oranye (sama dengan highlight halaman)."""
        q = self._query
        i = text.lower().find(q) if (q and hl) else -1
        if i >= 0:
            x0 = x + font.measure(text[:i])
            w = font.measure(text[i:i + len(q)])
            p = I.pill(max(4, w + 4), 18, HIGHLIGHT, C.CARD_HOVER if False else C.CARD, r=4)
            self._imgs.append(p)
            self.cv.create_image(x0 - 2, y - 9, image=p, anchor="nw")
        self.cv.create_text(x, y, text=text, anchor="w", fill=fill, font=font)

    def _row_at(self, y):
        i = int((y - 4) // self.ROW_H)
        return i if 0 <= i < len(self.items) else -1

    def _motion(self, e):
        self._select(self._row_at(e.y))

    def _select(self, i):
        if i != self.sel:
            self.sel = i
            self._draw()
            self.cv.config(cursor="hand2" if i >= 0 else "")

    def move(self, step):
        if not self.items:
            return
        n = len(self.items)
        self._select((self.sel + step) % n if self.sel >= 0 else (0 if step > 0 else n - 1))

    def choose(self, i=None):
        i = self.sel if i is None else i
        if 0 <= i < len(self.items):
            action = self.items[i]["action"]
            self.sb._hide_suggest()
            action()
            return True
        return False

    def _click(self, e):
        self.choose(self._row_at(e.y))


HIGHLIGHT = "#6b3d0c"   # latar kata yang cocok dengan pencarian (oranye gelap, teks tetap terbaca)


# --- profil di paling bawah ------------------------------------------------------------
def _avatar_photo(user, size, bg):
    """(PhotoImage, punya_foto) avatar bulat yang sudah dicampur dengan warna bg."""
    uid = user.get("id", "")
    color = PALETTE[sum(ord(c) for c in str(uid)) % len(PALETTE)]
    try:
        rendered = photos.render_avatar(uid, size, bg, fill=color, ring=bg, ring_width=0)
        if rendered is not None:
            img, has = rendered
            return photos.to_photoimage(img), has, color
    except Exception as exc:
        C.log(f"Avatar sidebar gagal: {exc!r}")
    return None, False, color


class _Profile(tk.Canvas):
    H = 54

    def __init__(self, master, sidebar, compact=False):
        w = 44 if compact else 40
        super().__init__(master, height=44 if compact else self.H, width=w, bg=C.SIDEBAR,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.sb, self.compact = sidebar, compact
        self._hover = False
        self.open = False
        self._imgs = []
        self._bold = tkfont.Font(font=_font(10, "bold"))
        self._small = tkfont.Font(font=_font(9))
        self.bind("<Enter>", lambda e: self._set(True))
        self.bind("<Leave>", lambda e: self._set(False))
        self.bind("<Button-1>", lambda e: sidebar.open_menu(self))
        self.bind("<Configure>", lambda e: self._draw())
        if compact:
            _Tip(self, sidebar.user.get("name", ""))

    def _set(self, hover):
        self._hover = hover
        self._draw()

    def _draw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20:
            return
        self.delete("all")
        self._imgs = []
        u = self.sb.user
        fill = C.SIDEBAR_ACTIVE if self.open else (C.SIDEBAR_HOVER if self._hover else C.SIDEBAR)
        if fill != C.SIDEBAR:
            p = I.pill(w, h, fill, C.SIDEBAR, r=10)
            if p is not None:
                self._imgs.append(p)
                self.create_image(0, 0, image=p, anchor="nw")
        size = 32
        ax = w / 2 if self.compact else 10 + size / 2
        ph, has, color = _avatar_photo(u, size, fill)
        if ph is not None:
            self._imgs.append(ph)
            self.create_image(ax, h / 2, image=ph)
        else:
            self.create_oval(ax - 16, h / 2 - 16, ax + 16, h / 2 + 16, fill=color, outline=color)
        if not has:
            self.create_text(ax, h / 2, text=initials(u.get("name", "")), fill="white",
                             font=_font(10, "bold"))
        if self.compact:
            return
        x = 10 + size + 10
        avail = w - x - 34
        self.create_text(x, h / 2 - 8, anchor="w", fill=C.TEXT, font=self._bold,
                         text=_fit_text(self._bold, u.get("name", ""), avail))
        self.create_text(x, h / 2 + 9, anchor="w", fill=C.MUTED, font=self._small,
                         text=_fit_text(self._small, self.sb.subtitle, avail))
        ic = I.icon("chevrons", C.MUTED, fill, 16)
        if ic is not None:
            self._imgs.append(ic)
            self.create_image(w - 18, h / 2, image=ic)


class _Menu(tk.Toplevel):
    """Menu kecil di atas profil (seperti claude.ai): nama, ID, lalu Keluar."""

    def __init__(self, sidebar, anchor, items):
        super().__init__(sidebar)
        self.sb, self.anchor = sidebar, anchor
        self.overrideredirect(True)
        self.configure(bg=C.BORDER)
        width = (EXPANDED_W - 20) if not sidebar.collapsed else 240
        box = tk.Frame(self, bg=C.CARD, padx=6, pady=6)
        box.pack(padx=1, pady=1)
        u = sidebar.user
        tk.Label(box, text=u.get("name", ""), bg=C.CARD, fg=C.TEXT, font=_font(10, "bold"),
                 anchor="w", padx=10).pack(fill="x", pady=(4, 0))
        tk.Label(box, text=sidebar.subtitle, bg=C.CARD, fg=C.MUTED, font=_font(9),
                 anchor="w", padx=10).pack(fill="x", pady=(0, 6))
        tk.Frame(box, bg=C.BORDER, height=1).pack(fill="x", pady=(0, 6))
        for text, icon, command in items:
            r = Row(box, text, lambda c=command: self._run(c), icon=icon, bg=C.CARD,
                    hover=C.CARD_HOVER, sel=C.CARD_HOVER, height=34)
            r.config(width=width - 14)
            r.pack(fill="x")
        self.update_idletasks()
        mh = self.winfo_reqheight()
        if sidebar.collapsed:
            x = anchor.winfo_rootx() + anchor.winfo_width() + 8
            y = anchor.winfo_rooty() + anchor.winfo_height() - mh
        else:
            x = anchor.winfo_rootx()
            y = anchor.winfo_rooty() - mh - 6
        self.geometry(f"+{x}+{max(0, y)}")
        top = sidebar.winfo_toplevel()
        self._where = (top.winfo_rootx(), top.winfo_rooty(), top.winfo_width())
        self.bind("<Button-1>", self._click, add="+")
        self.bind("<Escape>", lambda e: self.close())
        self.after(30, self._grab)
        self.after(250, self._watch)

    def _grab(self):
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception:
            pass

    def _watch(self):
        """Tutup kalau jendela utama dipindah / diperkecil."""
        if not self.winfo_exists():
            return
        try:
            top = self.sb.winfo_toplevel()
            now = (top.winfo_rootx(), top.winfo_rooty(), top.winfo_width())
            if now != self._where or top.state() == "iconic":
                self.close()
                return
        except Exception:
            self.close()
            return
        self.after(250, self._watch)

    def _click(self, e):
        x0, y0 = self.winfo_rootx(), self.winfo_rooty()
        if not (x0 <= e.x_root < x0 + self.winfo_width()
                and y0 <= e.y_root < y0 + self.winfo_height()):
            self.close()

    def _run(self, command):
        self.close()
        command()

    def close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
        if self.sb.winfo_exists():
            self.sb._menu_closed()


# --- sidebar --------------------------------------------------------------------------
def _install_shortcut(top):
    if getattr(top, "_sidebar_keys", False):   # pasang sekali saja per jendela
        return
    top._sidebar_keys = True

    def focus_search(_e=None):
        sb = _current["sb"]
        if sb is not None and sb.winfo_exists():
            screen = sb.master
            from elearning.app_settings import feature
            if getattr(screen, "search_sources", None) is not None \
                    and feature("palette"):                         # search palette
                from elearning.ui.search_palette import open_palette
                if open_palette(screen) is not None:
                    return "break"
            sb.focus_search()
        return "break"
    for seq in ("<Control-k>", "<Control-K>"):
        top.bind(seq, focus_search, add="+")


class _Ref:
    """Penunjuk ke widget baris yang dibuat sesudah populate() selesai."""

    widget = None

    def winfo_y(self):
        return self.widget.winfo_y() if self.widget is not None else 0


class AppSidebar(tk.Frame):
    """user: dict dengan 'id' dan 'name'. subtitle: teks di bawah nama (peran / ID).

    populate(sb): fungsi layar yang mengisi menu & daftar (dipanggil ulang oleh refresh()).
    on_search(teks): dipanggil (sedikit tertunda) saat isi kolom cari berubah; kalau tidak
    diberikan, sidebar cukup memanggil refresh() (daftar disaring lewat sb.matches()).
    menu_items: [(teks, ikon, fungsi)] untuk menu profil; "Keluar" selalu ada di akhir.
    """

    def __init__(self, master, user, subtitle, on_logout, populate, placeholder="Cari",
                 on_search=None, menu_items=(), suggest=None, on_enter=None, palette=False):
        from elearning.app_settings import feature
        # True: kolom cari sidebar membuka search palette (murid); Dev bisa mematikan palette
        self.palette = palette and feature("palette")
        super().__init__(master, bg=C.SIDEBAR, width=EXPANDED_W)
        self.pack_propagate(False)
        self.user, self.subtitle = user, subtitle
        self.on_logout, self.populate = on_logout, populate
        self.placeholder, self.on_search = placeholder, on_search
        self.menu_items = list(menu_items)
        self.suggest = suggest     # fungsi(teks) -> daftar saran (lihat _Suggest)
        self.on_enter = on_enter   # Enter di kolom cari (tanpa saran terpilih): lompat ke hasil
        self._sugg = None
        self.query = ""
        self._search_job = None
        self._menu = None
        self._search = None
        self._profile = None
        _current["sb"] = self
        _install_shortcut(self.winfo_toplevel())
        self.render()

    # --- status ---------------------------------------------------------------------
    @property
    def collapsed(self):
        return _state["collapsed"]

    def toggle(self):
        _state["collapsed"] = not _state["collapsed"]
        self.render()

    def matches(self, *texts):
        """True kalau kolom cari kosong atau salah satu teks mengandung kata yang dicari."""
        q = self.query.strip().lower()
        if not q:
            return True
        return any(q in str(t).lower() for t in texts if t)

    def focus_search(self):
        if self.palette:     # (palette dimatikan di Dev -> self.palette False sejak awal)
            from elearning.ui.search_palette import open_palette
            open_palette(self.master)
            return
        if self.collapsed:
            self.toggle()
        if self._search is not None:
            self._search.entry.focus_set()
            self._search.entry.select_range(0, "end")

    def set_query(self, text):
        """Isi kolom cari dari kode (mis. klik nama di daftar 'Sedang online')."""
        if self.collapsed:
            self.toggle()
        if self._search is not None:
            self._search.var.set(text)   # memicu _query_changed
        else:
            self._query_changed(text)

    def _query_changed(self, text):
        self.query = text
        if self._search_job is not None:
            self.after_cancel(self._search_job)
        self._search_job = self.after(160, self._run_search)

    # --- saran, jumlah hasil, Enter -------------------------------------------------------
    def set_count(self, n):
        """Jumlah hasil di dalam kolom cari (None = sembunyikan)."""
        if self._search is not None and self._search.count != n:
            self._search.count = n
            self._search._draw()

    def _suggest_visible(self):
        return self._sugg is not None and self._sugg.winfo_ismapped()

    def _hide_suggest(self):
        if self._sugg is not None:
            try:
                self._sugg.withdraw()
            except tk.TclError:
                self._sugg = None

    def _update_suggest(self):
        q = self.query.strip()
        if self.suggest is None or self._search is None or not q \
                or not self._search.focused:
            self._hide_suggest()
            return
        try:
            items = self.suggest(q)
        except Exception as exc:
            C.log(f"Saran pencarian gagal: {exc!r}")
            items = []
        if self._sugg is None or not self._sugg.winfo_exists():
            self._sugg = _Suggest(self)
        self._sugg.show(items, q)

    def _suggest_move(self, step):
        if self._suggest_visible():
            self._sugg.move(step)
        return "break"

    def _enter_pressed(self):
        if self._suggest_visible() and self._sugg.sel >= 0:
            self._sugg.choose()
            return
        self._hide_suggest()
        if self.on_enter is not None:
            self.on_enter()

    def _badge(self, method, *args):
        """Teruskan kejadian ke pelacak badge (hanya berlaku untuk murid yang masuk)."""
        tracker = getattr(self.winfo_toplevel(), "badges", None)
        if tracker is not None:
            try:
                getattr(tracker, method)(*args)
            except Exception as exc:
                C.log(f"Badge ({method}): {exc!r}")

    def _run_search(self):
        self._search_job = None
        self._badge("search_typed", self.query)
        self._update_suggest()
        if self.on_search is not None:
            self.on_search(self.query)
        else:
            self.refresh(keep_scroll=False)

    # --- kerangka ---------------------------------------------------------------------
    def render(self):
        self._built = None
        for w in self.winfo_children():
            w.destroy()
        self._search = self._profile = None
        self._scroll = None
        if self.collapsed:
            self.config(width=COLLAPSED_W)
            self._render_rail()
        else:
            self.config(width=EXPANDED_W)
            self._render_full()
        self.refresh(keep_scroll=False)

    def _render_full(self):
        head = tk.Frame(self, bg=C.SIDEBAR, height=56)
        head.pack(fill="x")
        head.pack_propagate(False)
        IconButton(head, "panel", self.toggle, tip=L("Tutup sidebar", "Close sidebar"),
                   size=(34, 34)).pack(side="right", padx=(0, 10))
        lockup = brand.pack_lockup(head, C.SIDEBAR)
        lockup.pack(side="left", padx=(16, 0))
        _bind_tree(lockup, "<Button-1>", lambda e: self._badge("logo_clicked"))

        self._search = _Search(self, self, self.placeholder)
        self._search.pack(fill="x", padx=10, pady=(2, 8))

        self._nav_box = tk.Frame(self, bg=C.SIDEBAR)
        self._nav_box.pack(fill="x", padx=8)

        # Bawah: profil, lalu item tambahan (Blender) tepat di atasnya
        bottom = tk.Frame(self, bg=C.SIDEBAR)
        bottom.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
        # Daftar yang "menempel" di bawah (dock=True, mis. Courses murid): di atas Blender
        self._dock_box = tk.Frame(bottom, bg=C.SIDEBAR)
        self._dock_box.pack(fill="x")
        tk.Frame(bottom, bg=C.SIDEBAR_LINE, height=1).pack(fill="x", padx=4, pady=(0, 6))
        self._footer_box = tk.Frame(bottom, bg=C.SIDEBAR)
        self._footer_box.pack(fill="x")
        self._profile = _Profile(bottom, self)
        self._profile.pack(fill="x", pady=(2, 0))

        self._scroll = ScrollFrame(self, bg=C.SIDEBAR)
        self._scroll.pack(fill="both", expand=True, padx=8, pady=(6, 6))
        self._list = self._scroll.inner

    def _render_rail(self):
        head = tk.Frame(self, bg=C.SIDEBAR)
        head.pack(fill="x", pady=(10, 0))
        mark = brand.mark(28)
        IconButton(head, "panel", self.toggle, tip=L("Buka sidebar", "Open sidebar"), size=(40, 40), image=mark,
                   hover_icon="panel").pack()
        IconButton(self, "search", self.focus_search, tip=L("Cari  (Ctrl+K)", "Search  (Ctrl+K)")).pack(pady=(10, 2))
        self._nav_box = tk.Frame(self, bg=C.SIDEBAR)
        self._nav_box.pack(fill="x")
        bottom = tk.Frame(self, bg=C.SIDEBAR)
        bottom.pack(side="bottom", fill="x", pady=(0, 10))
        self._footer_box = tk.Frame(bottom, bg=C.SIDEBAR)
        self._footer_box.pack(fill="x")
        self._dock_box = None
        self._profile = _Profile(bottom, self, compact=True)
        self._profile.pack(pady=(6, 0))
        self._list = None

    def refresh(self, keep_scroll=True):
        """Isi ulang menu & daftar (kolom cari dan profil tidak dibuat ulang).

        populate() hanya mencatat isi yang diminta. Kalau susunannya sama dengan yang sudah
        tampil (hanya menu aktif, angka, warna atau perintah yang berubah), baris yang ada
        diperbarui di tempat; tidak ada widget yang dibuat ulang -> tidak berkedip."""
        top = 0.0
        if keep_scroll and self._scroll is not None:
            top = self._scroll.canvas.yview()[0]
        self._specs = []
        self.populate(self)
        specs, self._specs = self._specs, None
        old = getattr(self, "_built", None)
        if old is not None and [k for k, _s, _w in old] == [self._key(sp) for sp in specs] \
                and all(w is None or w.winfo_exists() for _k, _s, w in old):
            for (key, _sp, widget), sp in zip(old, specs):
                self._update(widget, sp)
                sp["ref"].widget = widget
            self._built = [(k, sp, w) for (k, _s, w), sp in zip(old, specs)]
            return
        for box in (self._nav_box, self._footer_box, self._list, self._dock_box):
            if box is not None:
                for w in box.winfo_children():
                    w.destroy()
        built = []
        for sp in specs:
            widget = getattr(self, "_build_" + sp["kind"])(**sp["kw"])
            sp["ref"].widget = widget
            built.append((self._key(sp), sp, widget))
        self._built = built
        if self._scroll is not None:
            self.update_idletasks()
            self._scroll.canvas.yview_moveto(top)

    # Opsi yang boleh berubah tanpa membuat ulang baris
    _LIVE = {"active", "right", "fg", "command", "on_click", "text_note"}

    def _key(self, sp):
        kw = sp["kw"]
        parts = [sp["kind"], self.collapsed]
        for k in sorted(kw):
            v = kw[k]
            if k in ("active", "right", "fg"):
                if k == "right" and sp["kind"] == "section":
                    parts.append(("right_none", v is None))   # label angka ada / tidak
                continue
            if k in ("command", "on_click"):
                parts.append((k, v is None))
                continue
            if sp["kind"] == "note" and k == "text":
                continue
            parts.append((k, v if not callable(v) else "fn"))
        return tuple(parts)

    def _update(self, widget, sp):
        if widget is None:
            return
        kw = sp["kw"]
        kind = sp["kind"]
        if isinstance(widget, Row):
            changed = False
            for attr in ("active", "right", "fg"):
                if attr in kw or attr == "active":
                    val = kw.get(attr, False if attr == "active" else None)
                    if attr == "fg":
                        val = val or (C.LOCKED if widget.dim else C.TEXT)
                    if getattr(widget, attr) != val:
                        setattr(widget, attr, val)
                        changed = True
            if kw.get("command") is not None:
                widget.command = kw["command"]
            if changed:
                widget._draw()
        elif isinstance(widget, IconButton):
            if widget.active != kw.get("active", False):
                widget.active = kw.get("active", False)
                widget._draw()
            if kw.get("command") is not None:
                widget.command = kw["command"]
        elif kind == "section":
            widget._on_click[0] = kw.get("on_click")
            if widget._right is not None:
                widget._right.config(text=kw.get("right") or "")
        elif kind == "note":
            if widget.cget("text") != kw["text"]:
                widget.config(text=kw["text"])

    def _spec(self, kind, **kw):
        ref = _Ref()
        self._specs.append({"kind": kind, "kw": kw, "ref": ref})
        return ref

    def scroll_to(self, widget):
        """Gulir daftar supaya widget (mis. murid terpilih) terlihat."""
        if isinstance(widget, _Ref):
            widget = widget.widget
        if self._scroll is None or widget is None:
            return
        self.update_idletasks()
        height = max(1, self._list.winfo_reqheight())
        self._scroll.canvas.yview_moveto(max(0.0, (widget.winfo_y() - 60) / height))

    # --- pembuat isi (dipanggil dari populate; dicatat dulu, dibuat di refresh) ----------
    def nav(self, text, icon, command, active=False, primary=False, right=None):
        return self._spec("nav", text=text, icon=icon, command=command, active=active,
                          primary=primary, right=right)

    def section(self, text, on_click=None, folded=None, right=None, top=14, dock=False):
        if self.collapsed:
            return _Ref()
        return self._spec("section", text=text, on_click=on_click, folded=folded,
                          right=right, top=top, dock=dock)

    def item(self, text, command=None, **kw):
        if self.collapsed:
            return _Ref()
        return self._spec("item", text=text, command=command, **kw)

    def note(self, text, dock=False):
        if self.collapsed:
            return _Ref()
        return self._spec("note", text=text, dock=dock)

    def footer(self, text, command, image=None, icon=None, extra=None, right=None):
        """Item di dasar sidebar, tepat di atas profil (mis. Buka Blender).
        extra = [(ikon, perintah, tip), ...]: tombol ikon kecil di sebelah kanannya.
        right = teks kecil di kanan (mis. sisa menit Pinterest)."""
        return self._spec("footer", text=text, command=command, image=image, icon=icon,
                          extra=extra, right=right)

    def _build_nav(self, text, icon, command, active=False, primary=False, right=None):
        if self.collapsed:
            b = IconButton(self._nav_box, icon, command, active=active, tip=text,
                           disc=C.ACCENT if primary else None,
                           icon_color="#ffffff" if primary else None)
            b.pack(pady=1)
            return b
        r = Row(self._nav_box, text, command, icon=icon, active=active, right=right,
                icon_disc=C.ACCENT if primary else None,
                icon_color="#ffffff" if primary else None,
                font=_font(10, "bold") if primary else None)
        r.pack(fill="x", pady=0)
        return r

    def _box(self, dock):
        return self._dock_box if (dock and self._dock_box is not None) else self._list

    def _build_section(self, text, on_click=None, folded=None, right=None, top=14, dock=False):
        row = tk.Frame(self._box(dock), bg=C.SIDEBAR)
        row.pack(fill="x", pady=(top, 3))
        lbl = tk.Label(row, text=text, bg=C.SIDEBAR, fg=C.MUTED, font=_font(9), anchor="w",
                       padx=10)
        lbl.pack(side="left")
        widgets = [row, lbl]
        if folded is not None:
            ic = I.icon("chev_right" if folded else "chev_down", C.MUTED, C.SIDEBAR, 14)
            if ic is not None:
                chev = tk.Label(row, image=ic, bg=C.SIDEBAR, bd=0)
                chev.image = ic
                chev.pack(side="left")
                widgets.append(chev)
        row._right = None
        if right is not None:
            r = tk.Label(row, text=right, bg=C.SIDEBAR, fg=C.LOCKED, font=_font(9), padx=12)
            r.pack(side="right")
            widgets.append(r)
            row._right = r
        row._on_click = [on_click]
        if on_click is not None:
            for w in widgets:
                w.config(cursor="hand2")
                w.bind("<Button-1>", lambda e: row._on_click[0] and row._on_click[0]())
                w.bind("<Enter>", lambda e: lbl.config(fg=C.TEXT))
                w.bind("<Leave>", lambda e: lbl.config(fg=C.MUTED))
        return row

    def _build_item(self, text, command=None, dock=False, **kw):
        r = Row(self._box(dock), text, command, **kw)
        r.pack(fill="x")
        return r

    def _build_note(self, text, dock=False):
        lbl = tk.Label(self._box(dock), text=text, bg=C.SIDEBAR, fg=C.MUTED, font=_font(9),
                       anchor="w", justify="left", wraplength=EXPANDED_W - 50, padx=10)
        lbl.pack(fill="x", pady=(4, 4))
        return lbl

    def _build_footer(self, text, command, image=None, icon=None, extra=None, right=None):
        if self.collapsed:
            b = IconButton(self._footer_box, icon or "play", command, tip=text, image=image)
            b.pack(pady=1)
            for ic, cmd, tip in extra or ():
                IconButton(self._footer_box, ic, cmd, tip=tip).pack(pady=1)
            return b
        box = self._footer_box
        if extra:
            box = tk.Frame(self._footer_box, bg=C.SIDEBAR)
            box.pack(fill="x")
            for ic, cmd, tip in reversed(extra):
                IconButton(box, ic, cmd, tip=tip, size=(34, 36)).pack(side="right")
        r = Row(box, text, command, image=image, icon=None if image else icon, right=right)
        r.pack(fill="x", side="left" if extra else "top", expand=bool(extra))
        return r

    # --- menu profil --------------------------------------------------------------------
    def open_menu(self, anchor):
        if self._menu is not None:
            self._menu.close()
            return
        items = self.menu_items + [(L("Keluar", "Log out"), "logout", self.on_logout)]
        anchor.open = True
        anchor._draw()
        self._menu = _Menu(self, anchor, items)

    def _menu_closed(self):
        self._menu = None
        if self._profile is not None and self._profile.winfo_exists():
            self._profile.open = False
            self._profile._draw()

    def destroy(self):
        if self._sugg is not None:
            try:
                self._sugg.destroy()
            except Exception:
                pass
        if self._menu is not None:
            try:
                self._menu.close()
            except Exception:
                pass
        if _current["sb"] is self:
            _current["sb"] = None
        super().destroy()


class SidebarLayout(tk.Frame):
    """Kerangka layar: sidebar kiri + garis tipis + area isi kanan (self.content).

    Layar yang punya search_sources() (lihat search_palette.py) mendapat search palette
    (Ctrl+K). Dengan enable_search(): kolom cari juga tampil di tengah bawah area isi,
    di jalurnya sendiri (tidak menutupi isi / tombol paling bawah).
    """

    SEARCH_BAR_H = 68

    search_sources = None    # diisi layar: fungsi -> isi palette

    def __init__(self, master):
        super().__init__(master, bg=C.BG)
        self.sidebar = None
        self.sidebar_line = tk.Frame(self, bg=C.SIDEBAR_LINE, width=1)
        self.right = tk.Frame(self, bg=C.BG)
        self.content = tk.Frame(self.right, bg=C.BG)
        self.content.pack(side="top", fill="both", expand=True)
        self.search_bar = None

    def attach(self, sidebar):
        self.sidebar = sidebar
        sidebar.pack(side="left", fill="y")
        self.sidebar_line.pack(side="left", fill="y")
        self.right.pack(side="left", fill="both", expand=True)

    def enable_search(self, placeholder):
        """Kolom cari di tengah bawah (klik = buka search palette)."""
        from elearning.app_settings import feature
        if not feature("palette"):       # Dev: search palette dimatikan -> tanpa kolom bawah
            return
        from elearning.ui.search_palette import SearchBar, open_palette
        lane = tk.Frame(self.right, bg=C.BG, height=self.SEARCH_BAR_H)
        lane.pack_propagate(False)
        lane.pack(side="bottom", fill="x", before=self.content)
        bar = self.search_bar = SearchBar(lane, lambda: open_palette(self), placeholder)
        bar.place(relx=0.5, rely=0.5, anchor="center", y=-4)

        def fit(e):
            bar.set_width(max(300, min(560, e.width * 0.5)))
        lane.bind("<Configure>", fit)

    def open_search(self, tab="all"):
        from elearning.ui.search_palette import open_palette
        return open_palette(self, tab)

    def destroy(self):
        from elearning.ui.search_palette import close_palette
        close_palette()      # ganti layar / keluar: palette yang terbuka ikut ditutup
        super().destroy()

    def hide_sidebar(self):
        self.sidebar.pack_forget()
        self.sidebar_line.pack_forget()

    def show_sidebar(self):
        if not self.sidebar.winfo_manager():
            self.sidebar.pack(side="left", fill="y", before=self.right)
            self.sidebar_line.pack(side="left", fill="y", before=self.right)


# --- bagian yang dipakai beberapa layar ------------------------------------------------
PROGRAM_LABEL = {"adult": "Student", "kids": "Kids student", "trial": "Trial class"}


def student_subtitle(student):
    if student.get("program") == "trial":
        return "Trial class  ·  new student"
    return f"{PROGRAM_LABEL.get(student.get('program'), 'Student')}  ·  {student.get('id', '')}"


_blender_cache = {}


def open_blender(sb):
    """Buka Blender (sidebar murid & search palette)."""
    from elearning import blender_launcher
    app = sb.winfo_toplevel()
    if blender_launcher.open_blender(app):
        sb._badge("event", "siap_berkarya")
        ctl = getattr(app, "blender_float", None)
        if ctl is not None:   # Blender terbuka -> aplikasi mengecil jadi ikon mengambang
            ctl.enter()


def blender_footer(sb):
    """Item "Buka Blender" di dasar sidebar murid (semua murid, termasuk trial)."""
    from elearning import blender_icon, blender_launcher

    from elearning import web_launcher

    def open_blender_now():
        open_blender(sb)

    if "blender" not in _blender_cache:
        _blender_cache["blender"] = blender_icon.get_photo(22)
    student = getattr(sb.winfo_toplevel(), "_student", None)
    # situs web murid = baris sendiri DI ATAS Blender. Pinterest -> baris "Chrome" (logo
    # Chrome asli dari PC) yang membuka popup profil (akun guru / akun saya); Gemini + Flow
    # (murid AI) tetap baris sendiri. Kanan: sisa jatah (mis. "8 min left").
    for s in web_launcher.sites_for(student):
        st = web_launcher.status_text(student["id"], s["key"]) if student else ""
        if s["key"] == "pinterest":
            def pick(sb=sb, student=student):
                from elearning.ui.chrome_profiles import open_chrome_profiles
                open_chrome_profiles(sb, student)
            sb.footer("Chrome", pick, image=_chrome_logo(), icon=s["icon"], right=st or None)
            continue
        sb.footer(s["title"], lambda k=s["key"]: web_launcher.open_web(sb, student, k),
                  image=_site_logo(s["key"]), icon=s["icon"], right=st or None)
    sb.footer(L("Buka Blender", "Open Blender") + f" {blender_launcher.VERSION}", open_blender_now,
              image=_blender_cache["blender"], icon="play")


def _chrome_logo(size=22):
    """Logo Chrome asli dari instalasi Chrome di PC (di atas warna sidebar) atau None."""
    k = ("chrome", size)
    if k not in _blender_cache:
        ph = None
        try:
            from PIL import Image, ImageTk
            from elearning import web_launcher
            img = web_launcher.chrome_logo(size)
            if img is not None:
                bg = Image.new("RGBA", img.size, I._rgb(C.SIDEBAR) + (255,))
                bg.alpha_composite(img)
                ph = ImageTk.PhotoImage(bg.convert("RGB"))
        except Exception as exc:
            C.log(f"Logo Chrome tidak bisa dibuat: {exc!r}")
        _blender_cache[k] = ph
    return _blender_cache[k]


def _site_logo(key, size=22):
    """Logo asli situs (ui/img/<key>.png, bulat transparan, diperkecil halus) atau None."""
    k = ("site", key, size)
    if k not in _blender_cache:
        ph = None
        try:
            import os
            from PIL import Image, ImageTk
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img", f"{key}.png")
            if os.path.isfile(path):
                with Image.open(path) as im:
                    img = im.convert("RGBA").resize((size, size), Image.LANCZOS)
                bg = Image.new("RGBA", img.size, I._rgb(C.SIDEBAR) + (255,))
                bg.alpha_composite(img)          # latar sidebar: tepi bulat halus
                ph = ImageTk.PhotoImage(bg.convert("RGB"))
        except Exception as exc:
            C.log(f"Logo {key} tidak bisa dibuka: {exc!r}")
        _blender_cache[k] = ph
    return _blender_cache[k]



def course_items(sb, courses, allowed, current_id, on_open):
    """Daftar kursus di sidebar (dipakai layar utama murid dan layar kursus)."""
    shown = [c for c in courses if sb.matches(c["title"], c["group"], c["desc"])]
    # menempel di bawah sidebar, tepat di atas "Open Blender" (dock=True)
    sb.section("Courses", right=str(len(shown)) if sb.query else None, top=4, dock=True)
    for c in shown:
        unlocked = c["id"] in allowed
        sb.item(c["title"], (lambda c=c: on_open(c)) if unlocked and c["id"] != current_id
                else None,
                dot=c["color"] if unlocked else C.LOCKED, dim=not unlocked,
                right_icon=None if unlocked else "lock", active=c["id"] == current_id,
                dock=True)
    if not shown:
        sb.note(f"No courses match “{sb.query.strip()}”.", dock=True)
