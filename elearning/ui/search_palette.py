"""Search palette gaya claude.ai (Ctrl+K), dipakai admin, guru, murid, dan trial.

Dua bagian:
  SearchBar     : kolom "Cari ..." di tengah bawah layar (di bawah area isi).
                  Klik / Ctrl+K = buka palette.
  SearchPalette : jendela cari di tengah layar: kolom cari, tab tipe (Semua, Kursus,
                  Murid, ...), "Terakhir dibuka", hasil per tipe, "Aksi", dan petunjuk
                  tombol di bawah (Esc, panah, Enter).

Isi palette diberikan oleh layar lewat search_sources() (lihat sidebar.SidebarLayout):
  {"user": ID akun, "persist": simpan riwayat ke file?, "placeholder": teks,
   "tabs": [(kunci, judul), ...]          # kunci pertama "all", terakhir boleh "actions"
   "items": [{"key", "kind", "title", "sub", "icon" / "dot", "action", "words"}],
   "actions": [{"title", "icon", "action", "sub"}]}
  - kind = kunci tab tempat item itu tampil (mis. "courses", "students").
  - key  = kunci riwayat "Terakhir dibuka" (None = tidak dicatat).
  - action None = item terkunci (tampil redup dengan ikon gembok).

Semua digambar di canvas dengan gambar antialias (ui_icons), daftar hanya menggambar
baris yang terlihat (ringan walau ratusan murid). Palette ditutup kalau jendela utama
dipindah / berubah ukuran (windowed <-> fullscreen), jadi tidak ada sisa yang salah posisi.
"""

import sys
import time
import tkinter as tk
import tkinter.font as tkfont

from elearning import config as C
from elearning import recents
from elearning.ui import ui_icons as I

WIN = sys.platform == "win32"
KEY = "#0d0c0c"          # warna "tembus" sudut panel (= kira-kira latar yang diredupkan)
DIM_ALPHA = 0.55         # gelap latar di belakang palette (Windows)
FADE_S = 0.12            # lama muncul (detik), berbasis waktu
FRAME_MS = 16            # maks. 60 fps untuk transisi kecil
HIGHLIGHT = "#6b3d0c"    # latar kata yang cocok (sama dengan saran sidebar)

PANEL_W, PANEL_H = 680, 540
RADIUS = 16
HEAD_H = 30              # judul bagian ("Terakhir dibuka", "Aksi", ...)
ROW_H = 38
LIST_TOP = 112           # awal daftar di dalam panel
FOOT_H = 44
RECENT_ALL = 6           # riwayat yang tampil di tab Semua
PER_KIND = 5             # hasil per tipe di tab Semua
MAX_ROWS = 300

_open = {"pal": None}    # palette yang sedang terbuka (hanya satu)


def _font(size=10, weight="normal"):
    return (C.FONT, size, weight)


def _fit(font, text, avail):
    if avail <= 0:
        return ""
    if font.measure(text) <= avail:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if font.measure(text[:mid].rstrip() + "…") <= avail:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + "…"


def _keycap(cv, x, y, text, bg, font, anchor="w", tags=()):
    """Tombol keyboard kecil (mis. Esc, Enter). Mengembalikan lebarnya."""
    w = font.measure(text) + 12
    x0 = x if anchor == "w" else x - w
    p = I.pill(w, 20, C.SEG_ON, bg, r=5)
    if p is not None:
        cv._imgs.append(p)
        cv.create_image(x0, y - 10, image=p, anchor="nw", tags=tags)
    cv.create_text(x0 + w / 2, y, text=text, fill=C.MUTED, font=font, tags=tags)
    return w


def open_palette(screen, tab="all"):
    """Buka palette untuk layar ini (dipanggil SearchBar dan Ctrl+K)."""
    pal = _open["pal"]
    if pal is not None:
        try:
            if pal.winfo_exists():
                pal.focus_entry()
                return pal
        except tk.TclError:
            pass
        _open["pal"] = None
    try:
        sources = screen.search_sources()
    except Exception as exc:
        C.log(f"Search palette: isi gagal dibuat: {exc!r}")
        return None
    if not sources:
        return None
    try:
        _open["pal"] = SearchPalette(screen.winfo_toplevel(), sources, tab)
    except Exception as exc:
        C.log(f"Search palette gagal dibuka: {exc!r}")
        return None
    return _open["pal"]


def close_palette():
    pal = _open["pal"]
    if pal is not None:
        pal.close()


# --- kolom cari di tengah bawah layar ---------------------------------------------------
class SearchBar(tk.Canvas):
    """Kolom "Cari ..." bersudut bulat. Lebar mengikuti area isi (maks. 560 px)."""

    H = 44

    def __init__(self, master, on_open, placeholder="Cari", bg=C.BG):
        super().__init__(master, width=360, height=self.H, bg=bg, highlightthickness=0,
                         bd=0, cursor="hand2")
        self.on_open, self.placeholder, self.bg = on_open, placeholder, bg
        self._hover = False
        self._imgs = []
        self._f = tkfont.Font(font=_font(10))
        self._fk = tkfont.Font(font=_font(8))
        self.bind("<Enter>", lambda e: self._set(True))
        self.bind("<Leave>", lambda e: self._set(False))
        self.bind("<Button-1>", lambda e: self.on_open())
        self._draw()

    def set_width(self, w):
        w = int(w)
        if w != int(self["width"]):
            self.configure(width=w)
            self._draw()

    def _set(self, hover):
        if hover != self._hover:
            self._hover = hover
            self._draw()

    def _draw(self):
        self.delete("all")
        self._imgs = []
        w, h = int(self["width"]), self.H
        fill = C.CARD_HOVER if self._hover else C.CARD
        p = I.pill(w, h, fill, self.bg, r=14,
                   border="#5c5a55" if self._hover else C.BORDER)
        if p is not None:
            self._imgs.append(p)
            self.create_image(0, 0, image=p, anchor="nw")
        ic = I.icon("search", C.MUTED, fill, 16)
        if ic is not None:
            self._imgs.append(ic)
            self.create_image(22, h / 2, image=ic)
        kw = _keycap(self, w - 14, h / 2, "Ctrl K", fill, self._fk, anchor="e")
        self.create_text(42, h / 2, anchor="w", fill=C.MUTED, font=self._f,
                         text=_fit(self._f, self.placeholder, w - 42 - kw - 28))


# --- palette ------------------------------------------------------------------------------
class SearchPalette(tk.Toplevel):
    def __init__(self, top, sources, tab="all"):
        super().__init__(top)
        self.dim = None
        self._closed = False
        self._job = self._watch_job = None
        try:
            self._build(top, sources, tab)
        except Exception:
            self.close()      # jangan tinggalkan panel setengah jadi di layar
            raise

    def _build(self, top, sources, tab):
        self.top = top
        self.src = sources
        self.tabs = list(sources.get("tabs") or [("all", "Semua")])
        keys = [k for k, _ in self.tabs]
        self.tab = tab if tab in keys else keys[0]
        self.items = list(sources.get("items") or [])
        self.actions = [dict(a, kind="actions") for a in (sources.get("actions") or [])]
        self.by_key = {it["key"]: it for it in self.items if it.get("key")}
        self.user = sources.get("user")
        self.persist = sources.get("persist", True)
        self.rows = []           # [(jenis, data)] jenis = "head" / "row"
        self.ys = []             # posisi y tiap baris (virtual)
        self.sel = -1            # indeks di self.rows (baris yang bisa dipilih)
        self.offset = 0          # gulir daftar (px)
        self._hover_tab = None
        self._hover_close = False
        self._closed = False
        self._fade_t0 = None
        self._job = None
        self._watch_job = None
        self._imgs = []
        self._f_in = tkfont.Font(font=_font(12))
        self._f_tab = tkfont.Font(font=_font(10))
        self._f_tab_b = tkfont.Font(font=_font(10, "bold"))
        self._f_row = tkfont.Font(font=_font(10))
        self._f_sub = tkfont.Font(font=_font(9))
        self._f_head = tkfont.Font(font=_font(9))
        self._f_key = tkfont.Font(font=_font(8))

        # --- latar redup (Windows: jendela hitam semi-transparan di atas jendela utama)
        self.dim = None
        rx, ry = top.winfo_rootx(), top.winfo_rooty()
        tw, th = top.winfo_width(), top.winfo_height()
        if WIN:
            try:
                d = self.dim = tk.Toplevel(top)
                d.overrideredirect(True)
                d.configure(bg="#000000")
                d.attributes("-alpha", 0.0)
                d.geometry(f"{tw}x{th}+{rx}+{ry}")
                d.bind("<Button-1>", lambda e: self.close())
            except Exception as exc:
                C.log(f"Search palette: latar redup gagal: {exc!r}")
                self.dim = None

        # --- panel
        self.W = max(420, min(PANEL_W, tw - 80))
        self.H = max(320, min(PANEL_H, th - 80))
        self.overrideredirect(True)
        self.configure(bg=KEY)
        if WIN:
            try:
                self.attributes("-alpha", 0.0)
                self.attributes("-transparentcolor", KEY)   # sudut bulat benar-benar bulat
            except Exception:
                pass
        x = rx + (tw - self.W) // 2
        y = ry + max(24, int((th - self.H) / 2 - th * 0.04))
        self.geometry(f"{self.W}x{self.H}+{x}+{y}")
        self._where = (rx, ry, tw, th)

        self.cv = tk.Canvas(self, width=self.W, height=self.H, bg=KEY, highlightthickness=0,
                            bd=0)
        self.cv.place(x=0, y=0)
        self.cv._imgs = []
        self.var = tk.StringVar()
        e = self.entry = tk.Entry(self.cv, textvariable=self.var, bg=C.CARD, fg=C.TEXT,
                                  insertbackground=C.TEXT, relief="flat", bd=0,
                                  highlightthickness=0, font=self._f_in)
        self.ph = tk.Label(e, text=sources.get("placeholder", "Cari"), bg=C.CARD, fg=C.MUTED,
                           font=self._f_in, bd=0, padx=0, cursor="xterm")
        self.ph.bind("<Button-1>", lambda ev: e.focus_set())
        self.cv.create_window(24, 34, anchor="w", window=e, width=self.W - 84, height=28)

        lw, lh = self.W - 24, self.H - LIST_TOP - FOOT_H - 4
        self.lw, self.lh = lw, lh
        self.list = tk.Canvas(self.cv, width=lw, height=lh, bg=C.CARD, highlightthickness=0,
                              bd=0)
        self.list._imgs = []
        self.cv.create_window(12, LIST_TOP, anchor="nw", window=self.list)

        self._draw_frame()
        self._bind_keys()
        self.var.trace_add("write", lambda *a: self._changed())
        self._placeholder()
        self._rebuild()

        self.lift()
        self.after(10, self._start)

    # --- pasang / lepas -----------------------------------------------------------------
    def _bind_keys(self):
        e = self.entry
        e.bind("<Escape>", lambda ev: self._key_escape())
        e.bind("<Return>", lambda ev: self._run_sel())
        e.bind("<KP_Enter>", lambda ev: self._run_sel())
        e.bind("<Down>", lambda ev: self._move(1))
        e.bind("<Up>", lambda ev: self._move(-1))
        e.bind("<Next>", lambda ev: self._move(6))
        e.bind("<Prior>", lambda ev: self._move(-6))
        e.bind("<Tab>", lambda ev: self._switch_tab(1))
        e.bind("<Shift-Tab>", lambda ev: self._switch_tab(-1))
        e.bind("<ISO_Left_Tab>", lambda ev: self._switch_tab(-1))
        e.bind("<Left>", lambda ev: self._arrow_tab(-1))
        e.bind("<Right>", lambda ev: self._arrow_tab(1))
        self.bind("<Button-1>", self._click_any, add="+")
        self.cv.bind("<Motion>", self._frame_motion)
        self.cv.bind("<Leave>", lambda ev: self._frame_motion(None))
        self.list.bind("<Motion>", self._list_motion)
        self.list.bind("<Leave>", lambda ev: self._select(-1, keep=True))
        self.list.bind("<Button-1>", self._list_click)
        for w in (self.list, self.cv, self.entry):
            w.bind("<MouseWheel>", self._wheel)
            w.bind("<Button-4>", lambda ev: self._scroll(-ROW_H * 2))
            w.bind("<Button-5>", lambda ev: self._scroll(ROW_H * 2))

    def _start(self):
        if self._closed:
            return
        try:
            self.lift()
            self.focus_force()
            self.entry.focus_set()
            self.grab_set()
        except Exception:
            pass
        self._fade_t0 = time.perf_counter()
        self._fade()
        self._watch_job = self.after(250, self._watch)

    def _fade(self):
        """Muncul halus: alpha naik berbasis waktu (bukan per frame), maks. 60 fps."""
        if self._closed or not WIN:
            return
        t = min(1.0, (time.perf_counter() - self._fade_t0) / FADE_S)
        k = 1 - (1 - t) ** 3
        try:
            self.attributes("-alpha", k)
            if self.dim is not None:
                self.dim.attributes("-alpha", DIM_ALPHA * k)
        except Exception:
            return
        if t < 1.0:
            self._job = self.after(FRAME_MS, self._fade)

    def _watch(self):
        """Jendela utama dipindah / berubah ukuran / diperkecil: palette ditutup."""
        if self._closed:
            return
        try:
            top = self.top
            now = (top.winfo_rootx(), top.winfo_rooty(), top.winfo_width(), top.winfo_height())
            if now != self._where or top.state() == "iconic":
                self.close()
                return
        except Exception:
            self.close()
            return
        self._watch_job = self.after(250, self._watch)

    def focus_entry(self):
        try:
            self.lift()
            self.entry.focus_set()
        except Exception:
            pass

    def close(self):
        if self._closed:
            return
        self._closed = True
        if _open["pal"] is self:
            _open["pal"] = None
        for job in (self._job, self._watch_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        try:
            self.grab_release()
        except Exception:
            pass
        for w in (self, self.dim):
            if w is not None:
                try:
                    w.destroy()
                except Exception:
                    pass
        try:
            self.top.focus_set()
        except Exception:
            pass

    # --- kerangka: latar panel, ikon tutup, tab, garis, petunjuk tombol -------------------
    def _draw_frame(self):
        cv, W, H = self.cv, self.W, self.H
        cv.delete("frame")
        cv._imgs = []
        p = I.pill(W, H, C.CARD, KEY, r=RADIUS, border=C.BORDER)
        if p is not None:
            cv._imgs.append(p)
            cv.create_image(0, 0, image=p, anchor="nw", tags="frame")
        else:
            cv.create_rectangle(0, 0, W, H, fill=C.CARD, outline=C.BORDER, tags="frame")
        # tombol tutup (x)
        if self._hover_close:
            p = I.pill(30, 30, C.CARD_HOVER, C.CARD, r=8)
            if p is not None:
                cv._imgs.append(p)
                cv.create_image(W - 46, 19, image=p, anchor="nw", tags="frame")
        x = I.icon("close", C.TEXT if self._hover_close else C.MUTED,
                   C.CARD_HOVER if self._hover_close else C.CARD, 16)
        if x is not None:
            cv._imgs.append(x)
            cv.create_image(W - 31, 34, image=x, tags="frame")
        # tab tipe
        self._tab_boxes = []
        tx = 16
        for key, label in self.tabs:
            active = key == self.tab
            f = self._f_tab_b if active else self._f_tab
            tw = f.measure(label) + 24
            fill = C.SEG_ON if active else (C.CARD_HOVER if key == self._hover_tab else None)
            if fill:
                p = I.pill(tw, 30, fill, C.CARD, r=8)
                if p is not None:
                    cv._imgs.append(p)
                    cv.create_image(tx, 62, image=p, anchor="nw", tags="frame")
            cv.create_text(tx + tw / 2, 77, text=label, font=f, tags="frame",
                           fill=C.TEXT if active else C.MUTED)
            self._tab_boxes.append((tx, 62, tx + tw, 92, key))
            tx += tw + 4
        # garis pemisah (persegi 1 px: lurus, tidak perlu antialias)
        cv.create_rectangle(1, 104, W - 1, 105, fill=C.BORDER, outline="", tags="frame")
        cv.create_rectangle(1, H - FOOT_H, W - 1, H - FOOT_H + 1, fill=C.BORDER, outline="",
                            tags="frame")
        # petunjuk tombol
        y = H - FOOT_H / 2
        x = 20
        for text, keys in (("Tutup", ("Esc",)), ("Ganti tipe", ("←", "→")),
                           ("Pilih", ("↑", "↓"))):
            t = cv.create_text(x, y, text=text, anchor="w", fill=C.MUTED, font=self._f_sub,
                               tags="frame")
            x = cv.bbox(t)[2] + 8
            for k in keys:
                x += _keycap(cv, x, y, k, C.CARD, self._f_key, tags="frame") + 4
            x += 18
        kw = _keycap(cv, W - 20, y, "Enter", C.CARD, self._f_key, anchor="e", tags="frame")
        cv.create_text(W - 28 - kw, y, text="Buka", anchor="e", fill=C.MUTED,
                       font=self._f_sub, tags="frame")
        cv.tag_lower("frame")

    def _frame_motion(self, e):
        tab, close = None, False
        if e is not None:
            for x0, y0, x1, y1, key in self._tab_boxes:
                if x0 <= e.x < x1 and y0 <= e.y < y1:
                    tab = key
            close = self.W - 48 <= e.x < self.W - 14 and 18 <= e.y < 50
        if tab != self._hover_tab or close != self._hover_close:
            self._hover_tab, self._hover_close = tab, close
            self._draw_frame()
            self.cv.config(cursor="hand2" if (tab or close) else "")

    def _click_any(self, e):
        x0, y0 = self.winfo_rootx(), self.winfo_rooty()
        if not (x0 <= e.x_root < x0 + self.W and y0 <= e.y_root < y0 + self.H):
            self.close()      # klik di luar panel
            return
        if e.widget is not self.cv:
            return
        if self.W - 48 <= e.x < self.W - 14 and 18 <= e.y < 50:
            self.close()
            return
        for bx0, by0, bx1, by1, key in self._tab_boxes:
            if bx0 <= e.x < bx1 and by0 <= e.y < by1:
                self._set_tab(key)
                return
        self.entry.focus_set()

    # --- tab ------------------------------------------------------------------------------
    def _set_tab(self, key):
        if key != self.tab:
            self.tab = key
            self._draw_frame()
            self._rebuild()
        self.entry.focus_set()

    def _switch_tab(self, step):
        keys = [k for k, _ in self.tabs]
        self._set_tab(keys[(keys.index(self.tab) + step) % len(keys)])
        return "break"

    def _arrow_tab(self, step):
        """Panah kiri/kanan ganti tipe saat kolom kosong (kalau ada teks: gerakkan kursor)."""
        if self.var.get():
            return None
        return self._switch_tab(step)

    def _key_escape(self):
        self.close()
        return "break"

    # --- isi daftar -----------------------------------------------------------------------
    def _placeholder(self):
        if self.var.get():
            self.ph.place_forget()
        else:
            self.ph.place(x=1, rely=0.5, anchor="w")

    def _changed(self):
        self._placeholder()
        self._rebuild()

    def _label(self, kind):
        for k, label in self.tabs:
            if k == kind:
                return label
        return ""

    @staticmethod
    def _score(it, words):
        title = it["title"].lower()
        hay = " ".join((title, str(it.get("sub", "")), str(it.get("words", "")))).lower()
        if not all(w in hay for w in words):
            return None
        q = " ".join(words)
        if title.startswith(q):
            return 0
        if q in title:
            return 1
        if all(w in title for w in words):
            return 2
        return 3

    def _search(self, pool, words, limit):
        found = []
        for i, it in enumerate(pool):
            s = self._score(it, words)
            if s is not None:
                found.append((s, i, it))
        found.sort(key=lambda t: (t[0], t[1]))
        return [it for _s, _i, it in found[:limit]]

    def _recent(self, kind=None, limit=RECENT_ALL):
        out = []
        for key in recents.get(self.user, self.persist):
            it = self.by_key.get(key)
            if it is None or it.get("action") is None:
                continue
            if kind is not None and it["kind"] != kind:
                continue
            out.append(it)
            if len(out) >= limit:
                break
        return out

    def _rebuild(self):
        q = self.var.get().strip().lower()
        words = q.split()
        rows = []

        def section(title, its):
            if its:
                rows.append(("head", title))
                rows.extend(("row", it) for it in its)

        kinds = [k for k, _ in self.tabs if k not in ("all", "actions")]
        if self.tab == "all":
            if words:
                for k in kinds:
                    section(self._label(k),
                            self._search([it for it in self.items if it["kind"] == k],
                                         words, PER_KIND))
                section("Aksi", self._search(self.actions, words, PER_KIND))
            else:
                section("Terakhir dibuka", self._recent())
                section("Aksi", self.actions)
        elif self.tab == "actions":
            section("Aksi", self._search(self.actions, words, MAX_ROWS) if words
                    else self.actions)
        else:
            pool = [it for it in self.items if it["kind"] == self.tab]
            if words:
                section("Hasil", self._search(pool, words, MAX_ROWS))
            else:
                rec = self._recent(self.tab, 5)
                section("Terakhir dibuka", rec)
                seen = {id(it) for it in rec}
                section(self._label(self.tab),
                        [it for it in pool if id(it) not in seen][:MAX_ROWS])
        self.rows = rows
        self.ys, y = [], 4
        for kind, _ in rows:
            self.ys.append(y)
            y += HEAD_H if kind == "head" else ROW_H
        self.total_h = y + 6
        self.offset = 0
        self.sel = next((i for i, (k, d) in enumerate(rows)
                         if k == "row" and d.get("action") is not None), -1)
        self._words = words
        self._draw_list()

    # --- gambar daftar (hanya baris yang terlihat) ----------------------------------------
    def _draw_list(self):
        cv, lw, lh = self.list, self.lw, self.lh
        cv.delete("all")
        cv._imgs = []
        if not self.rows:
            q = self.var.get().strip()
            msg = (f"Tidak ada hasil untuk “{q}”." if q else "Belum ada isi di sini.")
            cv.create_text(lw / 2, 60, text=msg, fill=C.MUTED, font=self._f_row)
            return
        top, bottom = self.offset, self.offset + lh
        for i, (kind, data) in enumerate(self.rows):
            y = self.ys[i] - self.offset
            h = HEAD_H if kind == "head" else ROW_H
            if self.ys[i] + h < top or self.ys[i] > bottom:
                continue
            if kind == "head":
                cv.create_text(12, y + HEAD_H / 2 + 3, text=data, anchor="w", fill=C.MUTED,
                               font=self._f_head)
                continue
            self._draw_row(cv, data, y, i == self.sel)
        if self.total_h > lh:   # bilah gulir tipis bersudut bulat
            th = max(30, int(lh * lh / self.total_h))
            ty = int((lh - th) * self.offset / max(1, self.total_h - lh))
            p = I.pill(4, th, C.BORDER, C.CARD, r=2)
            if p is not None:
                cv._imgs.append(p)
                cv.create_image(lw - 6, ty, image=p, anchor="nw")

    def _draw_row(self, cv, it, y, selected):
        lw = self.lw
        bg = C.CARD_HOVER if selected else C.CARD
        locked = it.get("action") is None
        if selected:
            p = I.pill(lw - 12, ROW_H - 4, C.CARD_HOVER, C.CARD, r=8)
            if p is not None:
                cv._imgs.append(p)
                cv.create_image(2, y + 2, image=p, anchor="nw")
        cy = y + ROW_H / 2
        if it.get("dot"):
            ph = I.dot(it["dot"] if not locked else C.LOCKED, bg, 12, 4.2)
        else:
            ph = I.icon(it.get("icon") or "search", C.MUTED if not selected else C.TEXT, bg, 16)
        if ph is not None:
            cv._imgs.append(ph)
            cv.create_image(24, cy, image=ph)
        # kanan: tipe (tab Semua), gembok / Enter
        right = lw - 20
        if selected and not locked:
            ph = I.icon("enter", C.MUTED, bg, 14)
            if ph is not None:
                cv._imgs.append(ph)
                cv.create_image(right - 6, cy, image=ph)
            right -= 26
        if locked:
            ph = I.icon("lock", C.LOCKED, bg, 14)
            if ph is not None:
                cv._imgs.append(ph)
                cv.create_image(right - 6, cy, image=ph)
            right -= 26
        badge = it.get("badge")
        if badge:
            t = cv.create_text(right, cy, text=badge, anchor="e", fill=C.MUTED,
                               font=self._f_sub)
            b = cv.bbox(t)
            right = (b[0] if b else right) - 12
        # judul + keterangan
        x = 44
        avail = right - x
        title = _fit(self._f_row, it["title"], avail)
        tcol = C.LOCKED if locked else C.TEXT
        self._hl(cv, x, cy, title, tcol, bg)
        used = self._f_row.measure(title) + 12
        sub = it.get("sub")
        if sub and avail - used > 40:
            cv.create_text(x + used, cy, text=_fit(self._f_sub, sub, avail - used),
                           anchor="w", fill=C.MUTED if not locked else C.LOCKED,
                           font=self._f_sub)

    def _hl(self, cv, x, y, text, fill, bg):
        """Judul dengan kata yang dicari diberi latar oranye (seperti saran sidebar)."""
        low = text.lower()
        for w in self._words:
            i = low.find(w)
            if i < 0:
                continue
            x0 = x + self._f_row.measure(text[:i])
            ww = self._f_row.measure(text[i:i + len(w)])
            p = I.pill(max(4, ww + 4), 20, HIGHLIGHT, bg, r=4)
            if p is not None:
                cv._imgs.append(p)
                cv.create_image(x0 - 2, y - 10, image=p, anchor="nw")
        cv.create_text(x, y, text=text, anchor="w", fill=fill, font=self._f_row)

    # --- pilih / gulir --------------------------------------------------------------------
    def _row_at(self, y):
        vy = y + self.offset
        for i, (kind, _d) in enumerate(self.rows):
            if kind == "row" and self.ys[i] <= vy < self.ys[i] + ROW_H:
                return i
        return -1

    def _select(self, i, keep=False):
        if keep and i < 0:
            return          # kursor keluar daftar: pilihan keyboard tetap
        if i != self.sel:
            self.sel = i
            self._draw_list()

    def _list_motion(self, e):
        i = self._row_at(e.y)
        if i >= 0:
            self._select(i)
        locked = i < 0 or self.rows[i][1].get("action") is None
        self.list.config(cursor="" if locked else "hand2")

    def _list_click(self, e):
        i = self._row_at(e.y)
        if i >= 0:
            self.sel = i
            self._run_sel()

    def _move(self, step):
        idx = [i for i, (k, _d) in enumerate(self.rows) if k == "row"]
        if not idx:
            return "break"
        if self.sel not in idx:
            self.sel = idx[0] if step > 0 else idx[-1]
        else:
            pos = idx.index(self.sel)
            if abs(step) == 1:
                pos = (pos + step) % len(idx)            # panah: berputar
            else:
                pos = max(0, min(len(idx) - 1, pos + step))
            self.sel = idx[pos]
        self._ensure_visible(self.sel)
        self._draw_list()
        return "break"

    def _ensure_visible(self, i):
        y = self.ys[i]
        # judul bagian di atas baris pertama ikut terlihat
        if i > 0 and self.rows[i - 1][0] == "head":
            y = self.ys[i - 1]
        if y < self.offset:
            self.offset = max(0, y - 4)
        elif self.ys[i] + ROW_H > self.offset + self.lh:
            self.offset = self.ys[i] + ROW_H - self.lh + 6

    def _scroll(self, dy):
        old = self.offset
        self.offset = max(0, min(max(0, self.total_h - self.lh), self.offset + dy))
        if self.offset != old:
            self._draw_list()
        return "break"

    def _wheel(self, e):
        return self._scroll(-ROW_H * 2 if e.delta > 0 else ROW_H * 2)

    def _run_sel(self):
        if not (0 <= self.sel < len(self.rows)) or self.rows[self.sel][0] != "row":
            return "break"
        it = self.rows[self.sel][1]
        action = it.get("action")
        if action is None:
            return "break"
        if it.get("key"):
            try:
                recents.add(self.user, it["key"], self.persist)
            except Exception as exc:
                C.log(f"Riwayat cari: {exc!r}")
        top = self.top
        self.close()

        def run():
            try:
                action()
            except Exception as exc:
                C.log(f"Search palette: aksi gagal: {exc!r}")
        top.after(1, run)   # palette sudah hilang sebelum layar dibangun ulang
        return "break"
