"""Tabel Panel Admin (Murid, Guru, Laporan Guru) yang digambar di SATU canvas.

Sama seperti halaman Analytics: canvas Tk menyiapkan gambarnya di memori lalu menampilkan
sekaligus. Jadi pindah menu, pembaruan otomatis tiap 30 detik, maupun jendela <-> layar
penuh tidak pernah memperlihatkan tombol terpotong atau blok hitam, dan ringan untuk PC
dengan grafis terintegrasi (puluhan murid = satu widget saja, bukan ratusan).

PeopleBoard  : tabel murid / guru + tombol Set Active/Expired, Ubah, Hapus
ReportsBoard : ringkasan portfolio per murid + kartu laporan guru
"""

import os
import tkinter as tk
import tkinter.font as tkfont

from elearning import config as C
from elearning import photos, reports, sessions
from elearning.students import STATUS_EXPIRED, STATUS_LABEL
from elearning.ui import ui_icons as I
from elearning.ui.avatar import PALETTE, initials
from elearning.ui.report_widgets import KIND_COLOR, PORTFOLIO_COLUMNS, PROGRAM_LABEL
from elearning.ui.sidebar import HIGHLIGHT

PEOPLE_COLUMNS = (("Nama", 8), ("Aktivitas", 4), ("Terakhir aktif", 6),
                  ("Masuk", 2), ("Total waktu", 3), ("Status akun", 9))
# Tabel sempit (jendela kecil): kolom angka disembunyikan (lebar 0), tombol tetap utuh
PEOPLE_NARROW = (("Nama", 8), ("Aktivitas", 5), ("Terakhir aktif", 0),
                 ("Masuk", 0), ("Total waktu", 0), ("Status akun", 12))
NARROW_W = 820


class _Board(tk.Canvas):
    """Dasar: font, gambar, teks terpotong, tombol membulat, gambar ulang saat lebar berubah."""

    def __init__(self, master):
        super().__init__(master, bg=C.BG, highlightthickness=0, bd=0, height=60)
        self._imgs = []
        self._width = 0
        self._btn = 0
        self.query = ""        # kata yang dicari: bagian teks yang cocok diberi latar oranye
        self.focus = -1        # hasil ke-n yang sedang dituju (Enter di kolom cari)
        self.item_ys = []      # posisi y (atas, bawah) tiap hasil, untuk menggulir ke sana
        self.f = {
            "head": tkfont.Font(family=C.FONT, size=9, weight="bold"),
            "name": tkfont.Font(family=C.FONT, size=11, weight="bold"),
            "sub": tkfont.Font(family=C.FONT, size=9),
            "cell": tkfont.Font(family=C.FONT, size=10),
            "cellb": tkfont.Font(family=C.FONT, size=10, weight="bold"),
            "btn": tkfont.Font(family=C.FONT, size=9),
            "title": tkfont.Font(family=C.FONT, size=13, weight="bold"),
            "kind": tkfont.Font(family=C.FONT, size=9, weight="bold"),
            "small": tkfont.Font(family=C.FONT, size=8),
            "init": tkfont.Font(family=C.FONT, size=12, weight="bold"),
        }
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, e):
        if e.width != self._width:
            self._width = e.width
            self.redraw()

    def redraw(self):
        w = self.winfo_width()
        if w < 200:
            return
        self.delete("all")
        self._imgs = []
        self._btn = 0
        self.config(cursor="")
        h = self._draw(w)
        if int(self.cget("height")) != int(h):
            self.configure(height=int(h))

    def _draw(self, w):
        return 60

    def _img(self, ph, x, y, anchor="nw"):
        if ph is not None:
            self._imgs.append(ph)
            return self.create_image(x, y, image=ph, anchor=anchor)
        return None

    def _text(self, x, y, text, font="cell", fill=C.TEXT, anchor="w", width=None, **kw):
        f = self.f[font]
        text = str(text)
        if width is not None and f.measure(text) > width:
            while text and f.measure(text + "...") > width:
                text = text[:-1]
            text = text.rstrip() + "..."
        return self.create_text(x, y, text=text, font=f, fill=fill, anchor=anchor, **kw)

    def _text_hl(self, x, y, text, font="cell", fill=C.TEXT, width=None):
        """Teks rata kiri (anchor w) dengan bagian yang cocok dengan pencarian disorot."""
        f = self.f[font]
        text = str(text)
        if width is not None and f.measure(text) > width:
            while text and f.measure(text + "...") > width:
                text = text[:-1]
            text = text.rstrip() + "..."
        q = self.query.strip().lower()
        i = text.lower().find(q) if q else -1
        if i >= 0:
            x0 = x + f.measure(text[:i])
            w = f.measure(text[i:i + len(q)])
            h = f.metrics("linespace") + 2
            self._img(I.pill(int(w + 4), int(h), HIGHLIGHT, C.CARD, r=4), x0 - 2, y - h / 2)
        return self.create_text(x, y, text=text, font=f, fill=fill, anchor="w")

    def _focus_ring(self, x, y, w, h):
        """Garis tepi oranye di sekitar hasil yang sedang dituju."""
        self._img(I.pill(int(w), int(h), C.CARD, C.BG, r=12, border=C.ACCENT), x, y)

    def _button(self, x, cy, text, command, fg=C.TEXT, bg=C.CARD):
        """Tombol kecil membulat. Kembalikan x ujung kanannya."""
        f = self.f["btn"]
        w, h = f.measure(text) + 20, 24
        self._btn += 1
        tag = f"btn{self._btn}"
        normal = I.pill(w, h, C.BG, bg, r=8)
        hover = I.pill(w, h, C.BORDER, bg, r=8)
        self._imgs += [normal, hover]
        img = self.create_image(x, cy - h / 2, image=normal, anchor="nw", tags=(tag,))
        self.create_text(x + w / 2, cy, text=text, font=f, fill=fg, tags=(tag,))
        self.tag_bind(tag, "<Enter>", lambda e: (self.itemconfigure(img, image=hover),
                                                 self.config(cursor="hand2")))
        self.tag_bind(tag, "<Leave>", lambda e: (self.itemconfigure(img, image=normal),
                                                 self.config(cursor="")))
        self.tag_bind(tag, "<Button-1>", lambda e: command())
        return x + w

    @staticmethod
    def _cols(columns, x0, width):
        total = sum(wt for _t, wt in columns)
        xs, x = [], x0
        for _t, wt in columns:
            xs.append(x)
            x += width * wt / total
        return xs + [x0 + width]


class PeopleBoard(_Board):
    """Tabel murid / guru."""

    ROW_H, GAP, HEAD_H = 60, 6, 24

    def __init__(self, master, on_status=None, on_edit=None, on_delete=None, on_birth=None,
                 on_courses=None):
        super().__init__(master)
        self.on_status, self.on_edit, self.on_delete = on_status, on_edit, on_delete
        self.on_birth = on_birth   # admin: isi tanggal lahir murid
        self.on_courses = on_courses   # admin: kursus terbuka / terkunci, tampil / disembunyikan
        self.people, self.stats, self.empty = [], {}, ""
        self._avatars = {}

    def show(self, people, stats, empty=""):
        self.people, self.stats, self.empty = people, stats, empty
        self.redraw()

    def _avatar(self, pid, name, cx, cy):
        size = 36
        try:
            mt = os.stat(photos.photo_path(pid)).st_mtime_ns
        except OSError:
            mt = None
        key = (pid, mt)
        hit = self._avatars.get(key)
        if hit is None:
            color = PALETTE[sum(ord(c) for c in str(pid)) % len(PALETTE)]
            ph, has = None, False
            try:
                rendered = photos.render_avatar(pid, size, C.CARD, fill=color, ring=C.BORDER)
                if rendered is not None:
                    img, has = rendered
                    ph = photos.to_photoimage(img)
            except Exception as exc:
                C.log(f"Avatar {pid} gagal: {exc!r}")
            hit = (ph, has, color)
            self._avatars[key] = hit
        ph, has, color = hit
        if ph is not None:
            self._img(ph, cx, cy, anchor="center")
        else:
            self.create_oval(cx - 18, cy - 18, cx + 18, cy + 18, fill=color, outline=color)
        if not has:
            self.create_text(cx, cy, text=initials(name), fill="white", font=self.f["init"])

    def _draw(self, W):
        teachers = bool(self.people) and self.people[0].get("teacher")
        cols = PEOPLE_NARROW if W < NARROW_W else PEOPLE_COLUMNS
        xs = self._cols(cols, 14, W - 28)
        for i, (title, wt) in enumerate(cols):
            if not wt:
                continue
            if i == len(cols) - 1 and teachers:
                title = "Kelola"
            self._text(xs[i], self.HEAD_H / 2, title, "head", C.MUTED)
        y = self.HEAD_H
        if not self.people:
            self._text(W / 2, y + 40, self.empty, "cell", C.MUTED, anchor="center")
            return y + 80
        card = I.pill(int(W), self.ROW_H, C.CARD, C.BG, r=12, border=C.BORDER)
        self.item_ys = []
        for n, p in enumerate(self.people):
            if n == self.focus:   # hasil yang sedang dituju (Enter): garis tepi oranye
                self._focus_ring(0, y, W, self.ROW_H)
            else:
                self._img(card, 0, y)
            self.item_ys.append((y, y + self.ROW_H))
            cy = y + self.ROW_H / 2
            self._avatar(p["id"], p["name"], xs[0] + 18, cy)
            nx = xs[0] + 46
            self._text_hl(nx, cy - 9, p["name"], "name", width=xs[1] - nx - 10)
            self._text_hl(nx, cy + 10, f"{p['id']}  ·  {p['sub']}", "sub", C.MUTED,
                          width=xs[1] - nx - 10)
            st = self.stats.get(p["id"])
            if st is None:
                status, color = "Belum pernah masuk", C.MUTED
                last = count = total = "-"
            else:
                status, color = (("●  Online", C.ON) if st["online"]
                                 else ("○  Offline", C.MUTED))
                seen = st["last_seen"]
                last = ("Sekarang" if st["online"] else
                        f"{sessions.format_date(seen)}, {sessions.format_time(seen)}")
                count = str(st["count"])
                total = sessions.format_duration(st["total"])
            for col, (text, fg) in enumerate(((status, color), (last, C.TEXT),
                                              (count, C.TEXT), (total, C.TEXT)), start=1):
                if xs[col + 1] - xs[col] > 12:          # kolom tersembunyi (tabel sempit)
                    self._text(xs[col], cy, text, "cell", fg, width=xs[col + 1] - xs[col] - 8)
            ax = xs[5]
            if p.get("teacher"):
                if self.on_edit:
                    ax = self._button(ax, cy, "Ubah", lambda p=p: self.on_edit(p)) + 6
                if self.on_delete:
                    self._button(ax, cy, "Hapus", lambda p=p: self.on_delete(p), fg=C.ERROR)
            elif p.get("status") is not None:
                expired = p["status"] == STATUS_EXPIRED
                # Tabel sempit: status cukup titik warna supaya semua tombol tetap utuh
                # (tabel lebih sempit lagi: label tombol dipendekkan)
                fb = self.f["btn"]
                names = {"status": "Set Active" if expired else "Set Expired",
                         "birth": "Tgl lahir", "courses": "Kursus"}
                used = [k for k, on in (("status", self.on_status), ("birth", self.on_birth),
                                        ("courses", self.on_courses)) if on]
                need = sum(fb.measure(names[k]) + 26 for k in used)
                compact = ax + 86 + need > W - 8
                if compact and ax + 24 + need > W - 8:
                    names = {"status": "Active" if expired else "Expired", "birth": "Lahir",
                             "courses": "Kursus"}
                t = self._text(ax, cy, "●" if compact else "●  " + STATUS_LABEL[p["status"]],
                               "cellb", C.ERROR if expired else C.ON)
                bx = self.bbox(t)[2] + 10 if compact else max(self.bbox(t)[2] + 10, ax + 86)
                if self.on_status:
                    from elearning.students import STATUS_ACTIVE
                    new = STATUS_ACTIVE if expired else STATUS_EXPIRED
                    bx = self._button(bx, cy, names["status"],
                                      lambda p=p, n=new: self.on_status(p["id"], n)) + 6
                if self.on_birth:
                    bx = self._button(bx, cy, names["birth"], lambda p=p: self.on_birth(p)) + 6
                if self.on_courses:
                    self._button(bx, cy, names["courses"], lambda p=p: self.on_courses(p))
            else:
                self._text(ax, cy, "-", "cell", C.MUTED)
            y += self.ROW_H + self.GAP
        return y


class ReportsBoard(_Board):
    """Ringkasan portfolio per murid + kartu laporan guru (Panel Admin, hanya lihat)."""

    def __init__(self, master):
        super().__init__(master)
        self.rows, self.recs, self.warn = [], [], True
        self.names, self.teacher_names, self.empty = {}, {}, ""

    def show(self, rows, recs, names, teacher_names, warn=True, empty=""):
        self.rows, self.recs, self.warn = rows, recs, warn
        self.names, self.teacher_names, self.empty = names, teacher_names, empty
        self.redraw()

    def _section(self, y, title, sub):
        t = self._text(0, y + 12, title, "title", anchor="w")
        self._text(self.bbox(t)[2] + 12, y + 13, sub, "sub", C.MUTED)
        return y + 34

    def _draw(self, W):
        rows = self.rows
        done = sum(1 for r in rows if r["submitted"])
        files = sum(r["submitted"] for r in rows)
        y = self._section(0, "Portfolio murid",
                          f"{done} dari {len(rows)} murid aktif sudah submit  ·  {files} file")
        if not rows:
            self._text(0, y + 10, "Belum ada murid aktif.", "cell", C.MUTED)
            y += 30
        else:
            xs = self._cols(PORTFOLIO_COLUMNS, 14, W - 28)
            for i, (title, _w) in enumerate(PORTFOLIO_COLUMNS):
                self._text(xs[i], y + 10, title, "head", C.MUTED)
            y += 22
            rh = 52
            card = I.pill(int(W), rh, C.CARD, C.BG, r=12, border=C.BORDER)
            for r in sorted(rows, key=lambda r: (bool(r["submitted"]), r["id"])):
                self._img(card, 0, y)
                cy = y + rh / 2
                self._text_hl(xs[0], cy - 9, r["name"], "name", width=xs[1] - xs[0] - 10)
                self._text_hl(xs[0], cy + 10,
                              f"{r['id']}  ·  {PROGRAM_LABEL.get(r['program'], '')}",
                              "sub", C.MUTED, width=xs[1] - xs[0] - 10)
                if r["submitted"]:
                    detail = []
                    if r["images"]:
                        detail.append(f"{r['images']} gambar")
                    if r["videos"]:
                        detail.append(f"{r['videos']} video")
                    self._text(xs[1], cy - 9, "●  " + " · ".join(detail), "cellb",
                               C.ON, width=xs[2] - xs[1] - 8)
                    self._text(xs[1], cy + 10, ", ".join(r["courses"]), "sub", C.MUTED,
                               width=xs[2] - xs[1] - 8)
                else:
                    self._text(xs[1], cy, "○  Belum submit",
                               "cellb" if self.warn else "cell",
                               C.ERROR if self.warn else C.MUTED)
                last = (f"{sessions.format_date(r['last'])}, {sessions.format_time(r['last'])}"
                        if r["last"] else "Belum pernah")
                fg = C.TEXT if r["total"] else C.MUTED
                self._text(xs[2], cy, f"{r['total']} file", "cell", fg)
                self._text(xs[3], cy, last, "cell", fg, width=xs[4] - xs[3] - 8)
                y += rh + 6

        y = self._section(y + 14, "Laporan guru", f"{len(self.recs)} laporan")
        if not self.recs:
            self._text(0, y + 10, self.empty, "cell", C.MUTED)
            return y + 34
        self.item_ys = []
        for n, rec in enumerate(self.recs):
            top = y
            y = self._report(rec, y, W, focused=n == self.focus) + 8
            self.item_ys.append((top, y - 8))
        return y

    def _report(self, rec, y, W, focused=False):
        """Satu kartu laporan: tinggi mengikuti panjang catatan (teks dibungkus)."""
        color = KIND_COLOR.get(rec["kind"], C.MUTED)
        x0, pad = 30, 14
        tw = W - x0 - pad
        items = []
        teacher = self.teacher_names.get(rec["teacher"], f"{rec['teacher']} (sudah dihapus)")
        ty = y + 14
        items.append(self._text(x0, ty, reports.KIND_LABEL[rec["kind"]].upper(), "kind", color,
                                anchor="nw"))
        items.append(self._text(W - pad, ty,
                                f"{sessions.format_date(rec['day'])}  ·  {teacher}",
                                "sub", C.MUTED, anchor="ne"))
        ty += 20
        if rec["student"]:
            name = self.names.get(rec["student"]) or "(murid sudah dihapus)"
            items.append(self._text_hl(x0, ty + 9, f"{rec['student']}  ·  {name}", "name",
                                       width=tw))
            ty += 22
        body = self.create_text(x0, ty, text=rec["text"], font=self.f["cell"], fill=C.TEXT,
                                anchor="nw", width=tw)
        ty = self.bbox(body)[3] + 4
        if rec.get("edited"):
            self._text(x0, ty + 2, f"Diubah {rec['edited'][:16]}", "small", C.MUTED, anchor="nw")
            ty += 18
        h = ty - y + 12
        # latar kartu + garis warna (digambar sesudah ukuran teks diketahui, lalu ke belakang)
        # saat mencari: kartu yang cocok bergaris tepi oranye redup; yang sedang dituju tegas
        border = C.ACCENT if focused else ("#7a4a14" if self.query.strip() else C.BORDER)
        bg = self._img(I.pill(int(W), int(h), C.CARD, C.BG, r=12, border=border), 0, y)
        stripe = self._img(I.pill(4, int(h - 24), color, C.CARD, r=2), 14, y + 12)
        for item in (stripe, bg):
            if item is not None:
                self.tag_lower(item)
        return y + h
