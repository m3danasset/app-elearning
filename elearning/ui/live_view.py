"""Live Kelas (admin & guru): murid yang online SEKARANG dan apa yang sedang dikerjakan.

Data dari presence.py (tiap aplikasi murid menulis statusnya tiap 15 dtk). Dibaca ulang tiap
REFRESH_MS di THREAD (file kecil per murid), digambar di SATU canvas:
- baris atas: jumlah online, di Blender, menonton video, browsing, diam;
- "Kelas berjalan": jadwal yang sedang berlangsung, hadir x / y + nama yang belum login
  (guru: hanya kelasnya sendiri);
- kartu per murid: titik warna aktivitas, nama + ID, aktivitas (menonton / Blender / halaman),
  kursus, progres video, PC + lama diam. Klik kartu = buka murid itu (on_open).
"""

import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime

from elearning import config as C
from elearning import presence as P
from elearning.ui import ui_icons as I

REFRESH_MS = 5000
KIND_COLOR = {"video": "#7cc8ff", "blender": "#ea7600", "browse": "#b39af0", "page": C.ON,
              "idle": "#6f6c64"}
KIND_LABEL = (("blender", "di Blender"), ("video", "menonton"), ("browse", "browsing"),
              ("page", "di aplikasi"), ("idle", "diam"))
CARD_W, CARD_H, GAP = 300, 118, 10


def _fmt(sec):
    sec = int(sec or 0)
    return f"{sec // 60}:{sec % 60:02d}"


class LiveBoard(tk.Frame):
    def __init__(self, master, teacher_id=None, on_open=None, bg=C.BG):
        """teacher_id: guru (kelas berjalan = kelasnya sendiri); None = admin (semua)."""
        super().__init__(master, bg=bg)
        self.bg, self.teacher_id, self.on_open = bg, teacher_id, on_open
        self.f = {"h": tkfont.Font(family=C.FONT, size=12, weight="bold"),
                  "name": tkfont.Font(family=C.FONT, size=11, weight="bold"),
                  "t": tkfont.Font(family=C.FONT, size=10),
                  "s": tkfont.Font(family=C.FONT, size=9),
                  "big": tkfont.Font(family=C.FONT, size=18, weight="bold")}
        self.note = tk.Label(self, text="Memuat…", bg=bg, fg=C.MUTED, font=(C.FONT, 10),
                             anchor="w")
        self.note.pack(fill="x", pady=(0, 10))
        self.cv = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0, height=300)
        self.cv.pack(fill="x")
        self.cv.bind("<Configure>", lambda e: e.width != self._width and self.draw())
        self.cv.bind("<Motion>", self._motion)
        self.cv.bind("<Button-1>", self._click)
        self._width = None
        self._imgs, self._hits = [], []
        self.rows, self.slots = [], []
        self._job = None
        self._box = None
        self.reload()

    # --- data (thread) ----------------------------------------------------------------------
    def reload(self):
        if self._box is not None:          # pembacaan sebelumnya belum selesai
            return
        box = self._box = {}

        def work():
            try:
                box["rows"] = P.read_all()
                box["slots"] = self._running_slots()
            except Exception as exc:
                C.log(f"Live kelas: gagal dibaca: {exc!r}")
                box["rows"], box["slots"] = [], []
            box["done"] = True
        threading.Thread(target=work, daemon=True).start()
        self._poll()

    def _poll(self):
        if not self.winfo_exists():
            return
        if not self._box or not self._box.get("done"):
            self.after(80, self._poll)
            return
        box, self._box = self._box, None
        self.rows, self.slots = box["rows"], box["slots"]
        self.draw()
        if self._job is None:
            self._job = self.after(REFRESH_MS, self._tick)

    def _tick(self):
        self._job = None
        if self.winfo_exists() and self.winfo_ismapped():
            self.reload()
        elif self.winfo_exists():
            self._job = self.after(REFRESH_MS, self._tick)

    def _running_slots(self):
        """Jadwal yang sedang berlangsung sekarang: [(slot, nama guru)]."""
        from elearning import schedule as SCH
        from elearning import teachers as T
        now = datetime.now()
        m = now.hour * 60 + now.minute
        names = {t["id"]: t["name"] for t in T.list_teachers()}
        out = []
        for sl in SCH.list_slots():
            if sl["day"] != now.weekday():
                continue
            if not SCH.to_min(sl["start"]) <= m < SCH.to_min(sl["end"]):
                continue
            if self.teacher_id and sl.get("teacher") != self.teacher_id:
                continue
            out.append((sl, names.get(sl.get("teacher"), sl.get("teacher") or "-")))
        return out

    # --- gambar ------------------------------------------------------------------------
    def draw(self):
        cv = self.cv
        cv.delete("all")
        self._imgs, self._hits = [], []
        W = max(400, cv.winfo_width())
        self._width = cv.winfo_width()
        kinds = [P.activity(r)[1] for r in self.rows]
        parts = [f"{len(self.rows)} murid online"] + \
            [f"{sum(1 for k in kinds if k == key)} {label}" for key, label in KIND_LABEL
             if any(k == key for k in kinds)]
        self.note.config(text="  ·  ".join(parts) + f"   ·   diperbarui {time.strftime('%H:%M:%S')}"
                         "  (tiap 5 detik)")
        y = 0
        online = {r["id"] for r in self.rows}
        if self.slots:
            cv.create_text(0, y, text="Kelas berjalan", anchor="nw", fill=C.TEXT,
                           font=self.f["h"])
            y += 30
            for sl, tname in self.slots:
                y = self._slot_card(sl, tname, online, y, W) + 8
            y += 12
        cv.create_text(0, y, text="Murid online", anchor="nw", fill=C.TEXT, font=self.f["h"])
        y += 30
        if not self.rows:
            self._card(0, y, W, 70)
            cv.create_text(20, y + 35, text="Belum ada murid yang online. Status muncul beberapa "
                           "detik setelah murid login.", anchor="w", fill=C.MUTED,
                           font=self.f["t"])
            y += 80
        cols = max(1, int((W + GAP) // (CARD_W + GAP)))
        cw = (W - GAP * (cols - 1)) / cols
        for i, r in enumerate(self.rows):
            col, row = i % cols, i // cols
            self._student_card(r, col * (cw + GAP), y + row * (CARD_H + GAP), cw)
        if self.rows:
            y += ((len(self.rows) - 1) // cols + 1) * (CARD_H + GAP)
        cv.configure(height=y + 4)

    def _card(self, x, y, w, h, border=None):
        img = I.pill(int(w), int(h), C.CARD, self.bg, r=12, border=border or C.BORDER)
        if img is not None:
            self._imgs.append(img)
            self.cv.create_image(x, y, image=img, anchor="nw")

    def _slot_card(self, sl, tname, online, y, W):
        from elearning.students import lookup_student
        studs = [lookup_student(sid) for sid in sl.get("students", [])]
        studs = [s for s in studs if s]
        here = [s for s in studs if s["id"] in online]
        away = [s for s in studs if s["id"] not in online]
        h = 64 if not away else 84
        self._card(0, y, W, h)
        cv = self.cv
        cv.create_text(18, y + 14, text=f"{sl['start']} – {sl['end']}  ·  {tname}", anchor="nw",
                       fill=C.TEXT, font=self.f["name"])
        if sl.get("note"):
            cv.create_text(18, y + 36, text=sl["note"], anchor="nw", fill=C.MUTED,
                           font=self.f["s"])
        frac = len(here) / len(studs) if studs else 0
        cv.create_text(W - 18, y + 12, text=f"{len(here)}/{len(studs)}", anchor="ne",
                       fill=C.ON if frac >= 0.8 else C.ACCENT, font=self.f["big"])
        cv.create_text(W - 18, y + 42, text="hadir (login)", anchor="ne", fill=C.MUTED,
                       font=self.f["s"])
        if away:
            names = ", ".join(s["name"] for s in away[:12]) + \
                (f" +{len(away) - 12}" if len(away) > 12 else "")
            cv.create_text(18, y + (56 if sl.get("note") else 40), anchor="nw", fill=C.ERROR,
                           font=self.f["s"], width=W - 140, text="Belum login: " + names)
        return y + h

    def _student_card(self, r, x, y, w):
        cv = self.cv
        text, kind = P.activity(r)
        color = KIND_COLOR.get(kind, C.MUTED)
        self._card(x, y, w, CARD_H, border=color if kind in ("blender", "video") else None)
        d = I.dot(color, C.CARD, 12, 5.5)
        if d is not None:
            self._imgs.append(d)
            cv.create_image(x + 22, y + 22, image=d)
        name = r.get("name") or r.get("id")
        cv.create_text(x + 36, y + 13, text=self._fit(name, w - 120, self.f["name"]),
                       anchor="nw", fill=C.TEXT, font=self.f["name"])
        cv.create_text(x + w - 16, y + 15, text=r.get("id", ""), anchor="ne", fill=C.MUTED,
                       font=self.f["s"])
        cv.create_text(x + 16, y + 40, text=self._fit(text, w - 32, self.f["t"]), anchor="nw",
                       fill=color if kind != "idle" else C.MUTED, font=self.f["t"])
        sub = r.get("course_title") or ""
        if r.get("blender") and kind != "blender":
            sub = (sub + "  ·  " if sub else "") + "Blender terbuka"
        cv.create_text(x + 16, y + 62, text=self._fit(sub or "-", w - 32, self.f["s"]),
                       anchor="nw", fill=C.MUTED, font=self.f["s"])
        if r.get("lesson") and r.get("dur"):
            bw = w - 32 - 70
            frac = min(1.0, float(r.get("pos", 0)) / max(1.0, float(r["dur"])))
            bg = I.pill(int(bw), 6, C.SIDEBAR_ACTIVE, C.CARD, r=3)
            self._imgs.append(bg)
            cv.create_image(x + 16, y + 84, image=bg, anchor="nw")
            if int(bw * frac) >= 6:
                fg = I.pill(int(bw * frac), 6, KIND_COLOR["video"], C.SIDEBAR_ACTIVE, r=3)
                self._imgs.append(fg)
                cv.create_image(x + 16, y + 84, image=fg, anchor="nw")
            cv.create_text(x + w - 16, y + 81, text=f"{_fmt(r.get('pos'))}/{_fmt(r['dur'])}",
                           anchor="ne", fill=C.MUTED, font=self.f["s"])
        idle = r.get("idle", 0)
        foot = r.get("pc") or ""
        if idle >= 60:
            foot += f"  ·  tidak ada input {int(idle // 60)} mnt"
        cv.create_text(x + 16, y + CARD_H - 12, text=self._fit(foot, w - 32, self.f["s"]),
                       anchor="sw", fill=C.LOCKED, font=self.f["s"])
        self._hits.append((x, y, x + w, y + CARD_H, r.get("id")))

    @staticmethod
    def _fit(text, px, f):
        text = str(text)
        if f.measure(text) <= px:
            return text
        while text and f.measure(text + "…") > px:
            text = text[:-1]
        return text + "…"

    def _motion(self, e):
        hit = self.on_open and any(x0 <= e.x < x1 and y0 <= e.y < y1
                                   for x0, y0, x1, y1, _i in self._hits)
        self.cv.configure(cursor="hand2" if hit else "")

    def _click(self, e):
        for x0, y0, x1, y1, sid in self._hits:
            if x0 <= e.x < x1 and y0 <= e.y < y1 and self.on_open:
                self.on_open(sid)
                return

    def destroy(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
        super().destroy()
