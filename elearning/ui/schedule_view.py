"""Tab Jadwal di Panel Admin: kalender mingguan (Senin-Minggu x jam) gaya claude.ai.

ScheduleBoard  : SATU canvas berisi seluruh kalender (judul hari, garis jam, blok jadwal),
                 digambar ulang utuh sekaligus -> tidak ada keadaan setengah jadi saat
                 windowed <-> fullscreen. Blok bersudut bulat (ui_icons.pill, antialias).
                 Klik kotak kosong = tambah jadwal di hari & jam itu; klik blok = ubah.
ScheduleDialog : tambah / ubah / hapus jadwal: hari, jam mulai-selesai, guru, catatan, murid.
"""

import tkinter as tk
import tkinter.font as tkfont
from datetime import date, datetime, timedelta

from elearning import config as C
from elearning import schedule as SCH
from elearning.ui import ui_icons as I
from elearning.ui.controls import RoundButton, RoundCheck, RoundEntry, RoundSelect, dark_titlebar
from elearning.ui.widgets import ScrollFrame, add_hover

HOURS = getattr(C, "SCHEDULE_HOURS", (8, 21))   # jam pertama & terakhir yang tampil
HOUR_H = 52
HEAD_H = 50
TOOL_H = 46        # baris atas: Hari / Minggu, panah, Hari ini, tanggal
TOP = TOOL_H + HEAD_H
MONTHS = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
          "September", "Oktober", "November", "Desember")
_view = {"mode": "slots"}  # admin: tampilan Sesi (seperti sheet) default
MAX_ROWS = 20              # slot murid per sesi jam (baris)
SLOT_H = 30                # tinggi baris di tampilan Sesi
SLOT_HEAD = 46   # tampilan terakhir (diingat selama aplikasi terbuka)
GUTTER = 58
GRID = "#2f2e2b"
PROGRAM_COLOR = {"adult": "#3f6f8f", "kids": "#9a4f73", "mix": "#6b5f8f", "none": "#4a4945"}
NO_TEACHER = "Tanpa guru"
STEP = 30          # pilihan jam tiap 30 menit


def _mix(a, b, t):
    ca, cb = I._rgb(a), I._rgb(b)
    return "#%02x%02x%02x" % tuple(int(round(ca[i] + (cb[i] - ca[i]) * t)) for i in range(3))


def _fit(font, text, avail):
    if font.measure(text) <= avail:
        return text
    while text and font.measure(text + "…") > avail:
        text = text[:-1]
    return text + "…" if text else ""


class ScheduleBoard(tk.Canvas):
    def __init__(self, master, on_add=None, on_edit=None, day_only=False):
        super().__init__(master, bg=C.BG, highlightthickness=0, bd=0,
                         height=TOP + (HOURS[1] - HOURS[0]) * HOUR_H + 12)
        self.on_add, self.on_edit = on_add, on_edit
        self.slots, self.students, self.teachers = [], {}, {}
        self.query = ""
        self.hover = None          # ("slot", id) / ("cell", day, hour)
        self.boxes = []            # (x0, y0, x1, y1, slot)
        self._imgs = []
        self._width = 0
        self.day_only = day_only    # guru: hanya tampilan Hari, hanya lihat
        self.on_nav = None          # dipanggil setelah pindah hari / minggu
        self.mode = "day" if day_only else _view["mode"]   # "week" / "day"
        self.anchor = date.today()  # hari yang tampil (Hari) / minggu yang tampil (Minggu)
        self.tools = []            # (x0, y0, x1, y1, nama) tombol baris atas
        self.f = {"day": tkfont.Font(font=(C.FONT, 10, "bold")),
                  "date": tkfont.Font(font=(C.FONT, 9)),
                  "hour": tkfont.Font(font=(C.FONT, 8)),
                  "time": tkfont.Font(font=(C.FONT, 8, "bold")),
                  "body": tkfont.Font(font=(C.FONT, 9)),
                  "plus": tkfont.Font(font=(C.FONT, 9)),
                  "tool": tkfont.Font(font=(C.FONT, 10)),
                  "tool_b": tkfont.Font(font=(C.FONT, 10, "bold")),
                  "range": tkfont.Font(font=(C.FONT, 12, "bold"))}
        self.bind("<Configure>", self._on_configure)
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<Button-1>", self._click)

    def set_data(self, slots, students, teachers, query=""):
        self.slots, self.students, self.teachers = slots, students, teachers
        self.query = query.strip().lower()
        self.redraw()

    def _on_configure(self, e):
        if e.width != self._width:
            self._width = e.width
            self.redraw()

    # --- ukuran ------------------------------------------------------------------------
    def _days(self):
        """Hari (0 = Senin) yang tampil: semua di Minggu, satu di Hari."""
        return list(range(7)) if self.mode == "week" else [self.anchor.weekday()]

    def _date_of(self, day):
        return self.anchor + timedelta(days=day - self.anchor.weekday())

    def _col(self, day):
        days = self._days()
        n = len(days)
        w = max(n * 60, self._width - GUTTER - 4)
        cw = w / n
        i = days.index(day)
        return GUTTER + i * cw, GUTTER + (i + 1) * cw

    def _y(self, minutes):
        return TOP + (minutes - HOURS[0] * 60) * HOUR_H / 60

    # --- tampilan & navigasi -------------------------------------------------------------
    def set_mode(self, mode):
        if mode != self.mode:
            self.mode = _view["mode"] = mode
            self.hover = None
            self.redraw()

    def shift(self, step):
        self.anchor += timedelta(days=step * (7 if self.mode == "week" else 1))
        self.hover = None
        self.redraw()
        if self.on_nav:
            self.on_nav()

    def go_today(self):
        self.anchor = date.today()
        self.redraw()
        if self.on_nav:
            self.on_nav()

    def _range_text(self):
        if self.mode != "week":
            d = self.anchor
            return f"{SCH.DAYS[d.weekday()]}, {d.day} {MONTHS[d.month - 1]} {d.year}"
        a = self._date_of(0)
        b = a + timedelta(days=6)
        if a.month == b.month:
            return f"{a.day} – {b.day} {MONTHS[b.month - 1]} {b.year}"
        if a.year == b.year:
            return f"{a.day} {MONTHS[a.month - 1][:3]} – {b.day} {MONTHS[b.month - 1][:3]} {b.year}"
        return f"{a.day} {MONTHS[a.month - 1][:3]} {a.year} – {b.day} {MONTHS[b.month - 1][:3]} {b.year}"

    def _tool(self, x, y, w, h, name, text=None, icon=None, on=False, font=None):
        hover = self.hover == ("tool", name)
        fill = C.SEG_ON if on else (C.CARD_HOVER if hover else C.CARD)
        p = I.pill(w, h, fill, C.BG, r=8, border=None if on else C.BORDER)
        if p is not None:
            self._imgs.append(p)
            self.create_image(x, y, image=p, anchor="nw")
        if icon:
            ic = I.icon(icon, C.TEXT, fill, 16)
            if ic is not None:
                self._imgs.append(ic)
                self.create_image(x + w / 2, y + h / 2, image=ic)
        if text:
            self.create_text(x + w / 2, y + h / 2, text=text, font=font or self.f["tool"],
                             fill=C.TEXT if (on or hover) else C.MUTED)
        self.tools.append((x, y, x + w, y + h, name))

    def _draw_toolbar(self):
        self.tools = []
        y, h = 6, 30
        x = GUTTER
        for mode, label in (() if self.day_only else (("slots", "Sesi"), ("day", "Hari"),
                                                       ("week", "Minggu"))):
            on = self.mode == mode
            f = self.f["tool_b"] if on else self.f["tool"]
            w = f.measure(label) + 28
            self._tool(x, y, w, h, mode, text=label, on=on, font=f)
            x += w + 4
        x += 0 if self.day_only else 14
        self._tool(x, y, 30, h, "prev", icon="chev_left")
        x += 34
        self._tool(x, y, 30, h, "next", icon="chev_right")
        x += 38
        label = "Minggu ini" if self.mode == "week" else "Hari ini"
        w = self.f["tool"].measure(label) + 26
        self._tool(x, y, w, h, "today", text=label)
        x += w + 16
        self.create_text(x, y + h / 2, text=self._range_text(), anchor="w",
                         font=self.f["range"], fill=C.TEXT)

    def _lanes(self, day_slots):
        """Jadwal yang bertabrakan di hari yang sama dibagi jadi lajur berdampingan."""
        lanes, out = [], {}
        for s in sorted(day_slots, key=lambda s: s["start"]):
            a = SCH.to_min(s["start"])
            for i, end in enumerate(lanes):
                if end <= a:
                    lanes[i] = SCH.to_min(s["end"])
                    out[s["id"]] = i
                    break
            else:
                lanes.append(SCH.to_min(s["end"]))
                out[s["id"]] = len(lanes) - 1
        return out, max(1, len(lanes))

    def _program(self, slot):
        progs = {self.students[sid]["program"] for sid in slot["students"]
                 if sid in self.students}
        if not progs:
            return "none"
        return progs.pop() if len(progs) == 1 else "mix"

    def _matches(self, slot):
        if not self.query:
            return True
        texts = [self.teachers.get(slot["teacher"], ""), slot["note"], SCH.DAYS[slot["day"]]]
        for sid in slot["students"]:
            texts += [sid, self.students.get(sid, {}).get("name", "")]
        return any(self.query in t.lower() for t in texts if t)

    # --- gambar ------------------------------------------------------------------------
    def redraw(self):
        self.delete("all")
        self._imgs = []
        self.boxes = []
        if self._width < 100:
            return
        W = self._width
        top, bottom = TOP, self._y(HOURS[1] * 60)
        today = date.today()
        self._draw_toolbar()
        if self.mode == "slots":
            self._draw_sessions()
            return
        want = TOP + (HOURS[1] - HOURS[0]) * HOUR_H + 12
        if int(self.cget("height")) != want:
            self.configure(height=want)
        for d in self._days():
            x0, x1 = self._col(d)
            day = self._date_of(d)
            is_today = day == today
            if is_today:     # kolom hari ini: latar sedikit lebih terang
                self.create_rectangle(x0, top, x1, bottom, fill=_mix(C.BG, C.CARD, 0.5),
                                      outline="")
            label = f"{SCH.DAYS[d]}"
            self.create_text((x0 + x1) / 2, TOOL_H + 16, text=label, font=self.f["day"],
                             fill=C.TEXT if is_today else C.MUTED)
            num = str(day.day)
            if is_today:
                p = I.pill(26, 22, C.ACCENT, C.BG, r=11)
                if p is not None:
                    self._imgs.append(p)
                    self.create_image((x0 + x1) / 2 - 13, TOOL_H + 26, image=p, anchor="nw")
            self.create_text((x0 + x1) / 2, TOOL_H + 37, text=num, font=self.f["date"],
                             fill="#ffffff" if is_today else C.MUTED)
            # sel yang disorot (tambah jadwal)
            if self.on_add and self.hover and self.hover[0] == "cell" and self.hover[1] == d:
                h = self.hover[2]
                y0, y1 = self._y(h * 60), self._y((h + 1) * 60)
                p = I.pill(int(x1 - x0 - 6), int(y1 - y0 - 4), C.CARD_HOVER,
                           _mix(C.BG, C.CARD, 0.5) if is_today else C.BG, r=8)
                if p is not None:
                    self._imgs.append(p)
                    self.create_image(x0 + 3, y0 + 2, image=p, anchor="nw")
                self.create_text((x0 + x1) / 2, (y0 + y1) / 2, text="+  Tambah",
                                 font=self.f["plus"], fill=C.MUTED)
        # garis jam & kolom (persegi 1 px: lurus, tidak perlu antialias)
        for h in range(HOURS[0], HOURS[1] + 1):
            y = self._y(h * 60)
            self.create_rectangle(GUTTER, y, W - 4, y + 1, fill=GRID, outline="")
            if h < HOURS[1]:
                self.create_text(GUTTER - 10, y + 1, text=f"{h:02d}:00", anchor="ne",
                                 font=self.f["hour"], fill=C.LOCKED)
        days = self._days()
        for i in range(len(days) + 1):
            x = self._col(days[i])[0] if i < len(days) else self._col(days[-1])[1]
            self.create_rectangle(x, top, x + 1, bottom, fill=GRID, outline="")
        # blok jadwal
        by_day = {}
        for s in self.slots:
            by_day.setdefault(s["day"], []).append(s)
        for d, day_slots in by_day.items():
            if d not in days:
                continue
            lane_of, n = self._lanes(day_slots)
            x0, x1 = self._col(d)
            lw = (x1 - x0 - 6) / n
            for s in day_slots:
                a, b = SCH.to_min(s["start"]), SCH.to_min(s["end"])
                a, b = max(a, HOURS[0] * 60), min(b, HOURS[1] * 60)
                if b <= a:
                    continue
                bx0 = x0 + 3 + lane_of[s["id"]] * lw
                self._draw_slot(s, bx0, self._y(a) + 2, bx0 + lw - 3, self._y(b) - 2,
                                _mix(C.BG, C.CARD, 0.5) if self._date_of(d) == today
                                else C.BG)
        # garis "sekarang" di kolom hari ini
        now = datetime.now()
        m = now.hour * 60 + now.minute
        if HOURS[0] * 60 <= m <= HOURS[1] * 60 and today.weekday() in days \
                and self._date_of(today.weekday()) == today:
            x0, x1 = self._col(today.weekday())
            y = self._y(m)
            self.create_rectangle(x0, y - 1, x1, y + 1, fill=C.ACCENT, outline="")
            p = I.dot(C.ACCENT, _mix(C.BG, C.CARD, 0.5), 10, 4.2)
            if p is not None:
                self._imgs.append(p)
                self.create_image(x0, y, image=p)

    def _draw_slot(self, s, x0, y0, x1, y1, bg):
        w, h = int(x1 - x0), int(y1 - y0)
        if w < 6 or h < 6:
            return
        base = PROGRAM_COLOR[self._program(s)]
        hover = self.hover == ("slot", s["id"]) and self.on_edit is not None
        match = self._matches(s)
        fill = _mix(base, "#ffffff", 0.12) if hover else base
        if not match:
            fill = _mix(base, bg, 0.7)          # tidak cocok dengan pencarian: redup
        border = C.ACCENT if (self.query and match) else None
        p = I.pill(w, h, fill, bg, r=8, border=border)
        if p is not None:
            self._imgs.append(p)
            self.create_image(x0, y0, image=p, anchor="nw")
        fg = "#ffffff" if match else C.MUTED
        avail = w - 14
        y = y0 + 7
        lines = [(f"{s['start']}–{s['end']}", self.f["time"], fg)]
        teacher = self.teachers.get(s["teacher"], "")
        names = [self.students[sid]["name"] for sid in s["students"] if sid in self.students]
        n = len(names)
        if teacher:
            lines.append((teacher, self.f["body"], _mix(fg, fill, 0.15)))
        lines.append((f"{n} murid" if n else "Belum ada murid", self.f["body"],
                      _mix(fg, fill, 0.25)))
        if s["note"]:
            lines.append((s["note"], self.f["body"], _mix(fg, fill, 0.25)))
        wide = w > 360          # tampilan Hari: nama murid berkolom di sebelah kanan
        if not wide:
            for nm in names:
                lines.append(("• " + nm, self.f["body"], _mix(fg, fill, 0.2)))
        else:
            info_w = 200
            avail = info_w - 14
            col_w = 190
            cols = max(1, int((w - info_w - 10) // col_w))
            lh = self.f["body"].metrics("linespace") + 2
            rows = max(1, int((h - 14) // lh))
            for i, nm in enumerate(names[:cols * rows]):
                c, r = divmod(i, rows)
                self.create_text(x0 + info_w + c * col_w, y0 + 7 + r * lh,
                                 text=_fit(self.f["body"], "• " + nm, col_w - 12), anchor="nw",
                                 font=self.f["body"], fill=_mix(fg, fill, 0.2))
            if len(names) > cols * rows:
                self.create_text(x1 - 8, y1 - 6, text=f"+{len(names) - cols * rows} lagi",
                                 anchor="se", font=self.f["body"], fill=_mix(fg, fill, 0.3))
        for text, font, color in lines:
            lh = font.metrics("linespace")
            if y + lh > y1 - 4:
                break
            self.create_text(x0 + 7, y, text=_fit(font, text, avail), anchor="nw", font=font,
                             fill=color)
            y += lh + 1
        self.boxes.append((x0, y0, x1, y1, s))

    # --- interaksi -----------------------------------------------------------------------
    # --- tampilan Sesi: kolom = sesi jam, baris = slot murid (maks. 20), seperti sheet ---
    def _label(self, sid):
        s = self.students.get(sid)
        if s is None:
            return "", PROGRAM_COLOR["none"]
        if s["program"] == "kids":
            return "SK", PROGRAM_COLOR["kids"]
        if any(c.startswith("intermediate") for c in s.get("courses", [])):
            return "IC", "#4f6f9a"
        return "PB", PROGRAM_COLOR["adult"]

    def _session_rows(self, day):
        """{(baris, jam): (id murid, jadwal)} + {jam: jumlah yang tidak muat}.
        Murid yang sama di jam berurutan tetap di baris yang sama (mudah dibaca)."""
        cells, over = {}, {}
        items = []
        for sl in self.slots:
            if sl["day"] != day:
                continue
            a = max(HOURS[0], SCH.to_min(sl["start"]) // 60)
            b = min(HOURS[1], -(-SCH.to_min(sl["end"]) // 60))
            for sid in sl["students"]:
                if sid in self.students:
                    items.append((a, b, sid, sl))
        items.sort(key=lambda t: (t[0], -(t[1] - t[0]), self.students[t[2]]["name"].lower()))
        for a, b, sid, sl in items:
            for r in range(MAX_ROWS):
                if all((r, h) not in cells for h in range(a, b)):
                    for h in range(a, b):
                        cells[(r, h)] = (sid, sl)
                    break
            else:
                for h in range(a, b):
                    over[h] = over.get(h, 0) + 1
        return cells, over

    def _draw_sessions(self):
        W = self._width
        day = self.anchor.weekday()
        hours = list(range(HOURS[0], HOURS[1]))
        x0 = GUTTER
        cw = max(90, (W - 4 - x0) / len(hours))
        top = TOOL_H + SLOT_HEAD
        bottom = top + MAX_ROWS * SLOT_H
        want = int(bottom + 34)
        if int(self.cget("height")) != want:
            self.configure(height=want)
        cells, over = self._session_rows(day)
        self.grid_cells = []
        now = datetime.now()
        is_today = self.anchor == date.today()
        for i, h in enumerate(hours):
            cx = x0 + i * cw
            live = is_today and h == now.hour
            used = sum(1 for r in range(MAX_ROWS) if (r, h) in cells)
            self.create_text(cx + cw / 2, TOOL_H + 14, text=f"{h:02d}.00-{h + 1:02d}.00",
                             font=self.f["day"], fill=C.TEXT if live else C.MUTED)
            fill = C.ERROR if used >= MAX_ROWS else (C.ACCENT if live else C.LOCKED)
            self.create_text(cx + cw / 2, TOOL_H + 32,
                             text=f"{used}/{MAX_ROWS}" + (f"  +{over[h]}" if over.get(h) else ""),
                             font=self.f["hour"], fill=fill)
            if live:
                self.create_rectangle(cx, top, cx + cw, bottom, fill=_mix(C.BG, C.CARD, 0.5),
                                      outline="")
        for r in range(MAX_ROWS):          # nomor slot di kiri
            self.create_text(x0 - 10, top + r * SLOT_H + SLOT_H / 2, text=str(r + 1),
                             anchor="e", font=self.f["hour"], fill=C.LOCKED)
        for r in range(MAX_ROWS + 1):
            y = top + r * SLOT_H
            self.create_rectangle(x0, y, x0 + cw * len(hours), y + 1, fill=GRID, outline="")
        for i in range(len(hours) + 1):
            x = x0 + i * cw
            self.create_rectangle(x, top, x + 1, bottom, fill=GRID, outline="")
        for (r, h), (sid, sl) in cells.items():
            i = hours.index(h)
            bx, by = x0 + i * cw + 3, top + r * SLOT_H + 3
            w, hh = int(cw - 6), SLOT_H - 6
            label, base = self._label(sid)
            hover = self.hover == ("slot", sl["id"]) and self.on_edit is not None
            match = self._matches(sl)
            bg = _mix(C.BG, C.CARD, 0.5) if (is_today and h == now.hour) else C.BG
            fill = _mix(base, "#ffffff", 0.12) if hover else base
            if not match:
                fill = _mix(base, bg, 0.7)
            p = I.pill(w, hh, fill, bg, r=6, border=C.ACCENT if (self.query and match) else None)
            if p is not None:
                self._imgs.append(p)
                self.create_image(bx, by, image=p, anchor="nw")
            name = self.students[sid]["name"]
            self.create_text(bx + 7, by + hh / 2, anchor="w", font=self.f["body"],
                             fill="#ffffff" if match else C.MUTED,
                             text=_fit(self.f["body"], f"{label} {name}", w - 12))
            self.boxes.append((bx, by, bx + w, by + hh, sl))
        # kotak kosong: tambah jadwal di jam itu
        if self.on_add and self.hover and self.hover[0] == "cell":
            _d, h = self.hover[1], self.hover[2]
            r = self.hover[3] if len(self.hover) > 3 else 0
            if h in hours:
                i = hours.index(h)
                bx, by = x0 + i * cw + 3, top + r * SLOT_H + 3
                p = I.pill(int(cw - 6), SLOT_H - 6, C.CARD_HOVER, C.BG, r=6)
                if p is not None:
                    self._imgs.append(p)
                    self.create_image(bx, by, image=p, anchor="nw")
                self.create_text(bx + (cw - 6) / 2, by + (SLOT_H - 6) / 2, text="+  Tambah",
                                 font=self.f["plus"], fill=C.MUTED)
        legend = "SK = SUPERKIDS   ·   PB = basic   ·   IC = intermediate   ·   " \
                 "klik nama = ubah jadwal, klik kotak kosong = tambah"
        self.create_text(x0, bottom + 18, text=legend, anchor="w", font=self.f["hour"],
                         fill=C.LOCKED)

    def _hit(self, x, y):
        for x0, y0, x1, y1, name in self.tools:
            if x0 <= x < x1 and y0 <= y < y1:
                return ("tool", name), None
        for x0, y0, x1, y1, s in reversed(self.boxes):
            if x0 <= x <= x1 and y0 <= y <= y1:
                return ("slot", s["id"]), s
        if self.mode == "slots":
            hours = list(range(HOURS[0], HOURS[1]))
            cw = max(90, (self._width - 4 - GUTTER) / len(hours))
            top = TOOL_H + SLOT_HEAD
            if x < GUTTER or y < top or y >= top + MAX_ROWS * SLOT_H:
                return None, None
            i = int((x - GUTTER) // cw)
            if not 0 <= i < len(hours):
                return None, None
            r = int((y - top) // SLOT_H)
            return ("cell", self.anchor.weekday(), hours[i], r), None
        if self.mode == "week" and TOOL_H <= y < TOP and x >= GUTTER:
            for d in self._days():
                x0, x1 = self._col(d)
                if x0 <= x < x1:
                    return ("dayhead", d), None
        if x < GUTTER or y < TOP or y >= self._y(HOURS[1] * 60):
            return None, None
        for d in self._days():
            x0, x1 = self._col(d)
            if x0 <= x < x1:
                h = HOURS[0] + int((y - TOP) // HOUR_H)
                return ("cell", d, h), None
        return None, None

    def _motion(self, e):
        key, _s = self._hit(e.x, e.y)
        self._set_hover(key)

    def _set_hover(self, key):
        if key is not None and ((key[0] == "cell" and not self.on_add)
                                or (key[0] == "slot" and not self.on_edit)):
            key = None              # hanya lihat: kotak & blok tidak bisa diklik
        if key != self.hover:
            self.hover = key
            self.config(cursor="hand2" if key else "")
            self.redraw()

    def _click(self, e):
        key, s = self._hit(e.x, e.y)
        if key is None:
            return
        if key[0] == "tool":
            name = key[1]
            if name in ("day", "week"):
                self.set_mode(name)
            elif name == "prev":
                self.shift(-1)
            elif name == "next":
                self.shift(1)
            elif name == "today":
                self.go_today()
        elif key[0] == "dayhead":      # klik nama hari (Minggu) = buka hari itu
            self.anchor = self._date_of(key[1])
            self.set_mode("day")
        elif key[0] == "slot" and self.on_edit:
            self.on_edit(s)
        elif key[0] == "cell" and self.on_add:
            self.on_add(key[1], key[2])


# --- dialog --------------------------------------------------------------------------------
def _times():
    return [SCH.to_hhmm(m) for m in range(6 * 60, 23 * 60 + 1, STEP)]


class ScheduleDialog(tk.Toplevel):
    """Tambah (slot=None) / ubah jadwal. on_done() dipanggil setelah simpan / hapus."""

    def __init__(self, master, students, teachers, on_done, slot=None, day=0, hour=9):
        super().__init__(master, bg=C.CARD, highlightthickness=1, highlightbackground=C.BORDER)
        self.title("Ubah jadwal" if slot else "Tambah jadwal")
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        dark_titlebar(self)
        try:
            self.iconbitmap(C.ICON_PATH)
        except Exception:
            pass
        self.slot, self.on_done = slot, on_done
        self.students = students          # [{"id","name","program"}]
        self.teachers = teachers          # {id: name}
        start = slot["start"] if slot else f"{hour:02d}:00"
        end = slot["end"] if slot else SCH.to_hhmm(min(23 * 60, (hour + 2) * 60))
        chosen = set(slot["students"]) if slot else set()

        body = tk.Frame(self, bg=C.CARD, padx=28, pady=22)
        body.pack(fill="both", expand=True)
        tk.Label(body, text=self.title(), bg=C.CARD, fg=C.TEXT, font=(C.FONT, 14, "bold"),
                 anchor="w").pack(fill="x", pady=(0, 14))

        row = tk.Frame(body, bg=C.CARD)
        row.pack(fill="x")
        self.day_var = tk.StringVar(value=SCH.DAYS[slot["day"] if slot else day])
        self.start_var = tk.StringVar(value=start)
        self.end_var = tk.StringVar(value=end)
        for label, var, values in (("Hari", self.day_var, SCH.DAYS),
                                   ("Mulai", self.start_var, _times()),
                                   ("Selesai", self.end_var, _times())):
            col = tk.Frame(row, bg=C.CARD)
            col.pack(side="left", padx=(0, 12))
            tk.Label(col, text=label, bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10),
                     anchor="w").pack(fill="x")
            RoundSelect(col, var, *values, bg=C.BG).pack(anchor="w", pady=(6, 0))

        col = tk.Frame(body, bg=C.CARD)
        col.pack(fill="x", pady=(12, 0))
        tk.Label(col, text="Guru", bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10),
                 anchor="w").pack(fill="x")
        self._teacher_ids = {NO_TEACHER: ""}
        self._teacher_ids.update({f"{n} ({t})": t for t, n in teachers.items()})
        cur = next((k for k, v in self._teacher_ids.items()
                    if slot and v == slot["teacher"]), NO_TEACHER)
        self.teacher_var = tk.StringVar(value=cur)
        RoundSelect(col, self.teacher_var, *self._teacher_ids, bg=C.BG).pack(anchor="w",
                                                                           pady=(6, 0))

        col = tk.Frame(body, bg=C.CARD)
        col.pack(fill="x", pady=(12, 0))
        tk.Label(col, text="Catatan (mis. ruang / kelas)", bg=C.CARD, fg=C.MUTED,
                 font=(C.FONT, 10), anchor="w").pack(fill="x")
        self.note_var = tk.StringVar(value=slot["note"] if slot else "")
        RoundEntry(col, self.note_var, width_chars=40, font=(C.FONT, 11), height=36,
                   fill=C.BG, radius=9).pack(fill="x", pady=(6, 0))

        head = tk.Frame(body, bg=C.CARD)
        head.pack(fill="x", pady=(14, 0))
        tk.Label(head, text="Murid", bg=C.CARD, fg=C.MUTED, font=(C.FONT, 10),
                 anchor="w").pack(side="left")
        self.count = tk.Label(head, text="", bg=C.CARD, fg=C.MUTED, font=(C.FONT, 9))
        self.count.pack(side="right")
        self.find_var = tk.StringVar()
        RoundEntry(body, self.find_var, placeholder="Cari nama / ID murid", width_chars=40,
                   font=(C.FONT, 10), height=34, fill=C.BG, radius=9,
                   icon="search").pack(fill="x", pady=(6, 6))
        box = tk.Frame(body, bg=C.BG, height=210)
        box.pack(fill="x")
        box.pack_propagate(False)
        self.scroll = ScrollFrame(box, bg=C.BG)
        self.scroll.pack(fill="both", expand=True, padx=8, pady=6)
        self.checks = []
        label = {"adult": "dewasa", "kids": "anak"}
        for s in students:
            c = RoundCheck(self.scroll.inner, s["name"], value=s["id"] in chosen, bg=C.BG,
                           sub=f"{s['id']}  ·  {label.get(s['program'], '')}",
                           command=self._update_count)
            c.pack(anchor="w", pady=1)
            self.checks.append((s, c))
        self.find_var.trace_add("write", lambda *a: self._filter())

        self.error = tk.Label(body, text="", bg=C.CARD, fg=C.ERROR, font=(C.FONT, 10),
                              anchor="w", wraplength=380, justify="left")
        self.error.pack(fill="x", pady=(10, 0))
        btns = tk.Frame(body, bg=C.CARD)
        btns.pack(fill="x", pady=(10, 0))
        ok = RoundButton(btns, text="Simpan", command=self._submit, bg=C.ACCENT, fg="white",
                         activebackground=C.ACCENT_HOVER, activeforeground="white",
                         font=(C.FONT, 11, "bold"), padx=22, pady=7)
        ok.pack(side="right")
        add_hover(ok, C.ACCENT, C.ACCENT_HOVER)
        cancel = RoundButton(btns, text="Batal", command=self.destroy, bg=C.CARD, fg=C.MUTED,
                             activebackground=C.BORDER, activeforeground=C.TEXT,
                             font=(C.FONT, 11), padx=18, pady=7)
        cancel.pack(side="right", padx=(0, 8))
        add_hover(cancel, C.CARD, C.BORDER)
        if slot:
            rm = RoundButton(btns, text="Hapus jadwal", command=self._delete, bg=C.CARD,
                             fg=C.ERROR, activebackground=C.BORDER, activeforeground=C.ERROR,
                             font=(C.FONT, 10), padx=14, pady=7)
            rm.pack(side="left")
            add_hover(rm, C.CARD, C.BORDER)
        self._update_count()
        self.bind("<Escape>", lambda e: self.destroy())
        self._center(master.winfo_toplevel())
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass

    def _center(self, parent):
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _filter(self):
        q = self.find_var.get().strip().lower()
        for s, c in self.checks:
            c.pack_forget()
        for s, c in self.checks:
            if not q or q in s["name"].lower() or q in s["id"].lower():
                c.pack(anchor="w", pady=1)
        self.scroll.scroll_to_top()

    def _update_count(self):
        n = sum(1 for _s, c in self.checks if c.value)
        self.count.config(text=f"{n} dipilih")

    def _submit(self):
        slot = {"id": self.slot["id"] if self.slot else "",
                "day": SCH.DAYS.index(self.day_var.get()),
                "start": self.start_var.get(), "end": self.end_var.get(),
                "teacher": self._teacher_ids.get(self.teacher_var.get(), ""),
                "note": self.note_var.get().strip(),
                "students": [s["id"] for s, c in self.checks if c.value]}
        try:
            SCH.save_slot(slot)
        except ValueError as exc:
            self.error.config(text=str(exc))
            return
        except Exception as exc:
            C.log(f"Jadwal gagal disimpan: {exc!r}")
            self.error.config(text="Gagal menyimpan. Pastikan folder data bisa ditulis.")
            return
        self.destroy()
        self.on_done()

    def _delete(self):
        from elearning.ui.dialogs import ConfirmDialog

        def confirm():
            try:
                SCH.delete_slot(self.slot["id"])
            except Exception as exc:
                C.log(f"Jadwal gagal dihapus: {exc!r}")
                return "Gagal menghapus."
            self.after(1, self._deleted)
            return None
        ConfirmDialog(self, "Hapus jadwal ini?",
                      f"{SCH.DAYS[self.slot['day']]} {self.slot['start']}–{self.slot['end']} "
                      "akan dihapus.", confirm, confirm_text="Hapus")

    def _deleted(self):
        try:
            self.destroy()
        finally:
            self.on_done()


class TeacherSchedule(tk.Frame):
    """Layar guru, menu Jadwal Murid: kalender per HARI saja, hanya lihat (diatur admin)."""

    REFRESH_MS = 60_000      # garis jam sekarang & perubahan dari admin ikut diperbarui

    def __init__(self, master):
        super().__init__(master, bg=C.BG)
        from elearning import teachers as T
        from elearning.students import age_text, list_students
        self._T, self._age, self._list = T, age_text, list_students
        self.info = tk.Label(self, text="", bg=C.BG, fg=C.MUTED, font=(C.FONT, 10),
                             anchor="w")
        self.info.pack(fill="x", padx=28, pady=(4, 6))
        self.scroll = ScrollFrame(self, bg=C.BG)
        self.scroll.pack(fill="both", expand=True, padx=(28, 12), pady=(0, 12))
        self.board = ScheduleBoard(self.scroll.inner, day_only=True)
        self.board.on_nav = self.refresh       # ringkasan ikut hari yang dipilih
        self.board.pack(fill="x")
        self._job = None
        self.refresh()

    def refresh(self):
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        studs = self._list()
        # umur ikut tampil di nama (guru tidak melihat tanggal lahir)
        by_id = {}
        for s in studs:
            age = self._age(s)
            by_id[s["id"]] = dict(s, name=f"{s['name']} ({age})" if age else s["name"])
        teachers = {t["id"]: t["name"] for t in self._T.list_teachers()}
        slots = SCH.list_slots()
        day = self.board.anchor.weekday()
        today_slots = [s for s in slots if s["day"] == day]
        n = len({m for s in today_slots for m in s["students"] if m in by_id})
        when = "hari ini" if self.board.anchor == date.today() else SCH.DAYS[day]
        self.info.config(text=f"{len(today_slots)} jadwal  ·  {n} murid {when}  ·  "
                              "jadwal diatur admin")
        self.board.set_data(slots, by_id, teachers)
        self._job = self.after(self.REFRESH_MS, self.refresh)

    def destroy(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
        super().destroy()

