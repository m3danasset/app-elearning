"""Halaman Sertifikat di layar kursus murid + daftar permintaan untuk admin & guru.

CertificatePage   : syarat kursus ini (centang / angka) + tombol "Request Certificate"
                    (terkunci sampai semua syarat terpenuhi). Satu canvas, gaya claude.ai.
CertificateBoard  : daftar permintaan (admin & guru): nama, kursus, waktu, tombol Selesai.
Hitungan syarat dibaca di thread (file progres / folder portfolio), hasil digambar di
thread utama.
"""

import threading
import tkinter as tk
import tkinter.font as tkfont

from elearning import certificates as CERT
from elearning import config as C
from elearning.ui import ui_icons as I

CARD_W = 560
ROW_H = 54
BTN_H = 44


class CertificatePage(tk.Frame):
    def __init__(self, master, student, course, on_change=None):
        super().__init__(master, bg=C.BG)
        self.student, self.course, self.on_change = student, course, on_change
        self.items, self.ok, self.req = None, False, None
        self.msg, self.msg_err = "", False
        self._imgs = []
        self._busy = False
        self.cv = tk.Canvas(self, bg=C.BG, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True, padx=28, pady=(8, 16))
        self.f = {"title": tkfont.Font(font=(C.FONT, 14, "bold")),
                  "body": tkfont.Font(font=(C.FONT, 10)),
                  "bold": tkfont.Font(font=(C.FONT, 10, "bold")),
                  "small": tkfont.Font(font=(C.FONT, 9)),
                  "btn": tkfont.Font(font=(C.FONT, 11, "bold"))}
        self.cv.bind("<Configure>", lambda e: self._draw())
        self.cv.tag_bind("btn", "<Button-1>", lambda e: self._request())
        self.cv.tag_bind("btn", "<Enter>", lambda e: self._hover(True))
        self.cv.tag_bind("btn", "<Leave>", lambda e: self._hover(False))
        self._btn_hover = False
        self._btn_item = None
        self.reload()

    # --- data (thread) --------------------------------------------------------------------
    def reload(self):
        """Hitung syarat di thread; Tk TIDAK dipanggil dari thread itu (hasil disimpan,
        lalu diambil thread utama 1x per frame lewat _poll)."""
        self._result = None

        def work():
            try:
                items, ok = CERT.requirements(self.student, self.course)
                req = CERT.request_of(self.student["id"], self.course["id"])
            except Exception as exc:
                C.log(f"Sertifikat: syarat tidak bisa dihitung: {exc!r}")
                items, ok, req = [], False, None
            self._result = (items, ok, req)
        threading.Thread(target=work, daemon=True).start()
        self._poll()

    def _poll(self):
        if not self.winfo_exists():
            return
        res = self._result
        if res is None:
            self.after(C.UI_FRAME_MS, self._poll)
            return
        self.items, self.ok, self.req = res
        self._draw()

    # --- gambar -----------------------------------------------------------------------------
    def _draw(self):
        cv = self.cv
        cv.delete("all")
        self._imgs = []
        W = cv.winfo_width()
        if W < 100:
            return
        cw = min(CARD_W, W)
        x0, y = 0, 0
        if self.items is None:
            cv.create_text(x0, 20, text="Checking requirements...", anchor="w", fill=C.MUTED,
                           font=self.f["body"])
            return
        n = len(self.items)
        ch = 112 + n * ROW_H + 24 + BTN_H + 44
        card = I.pill(cw, ch, C.CARD, C.BG, r=14, border=C.BORDER)
        if card is not None:
            self._imgs.append(card)
            cv.create_image(x0, y, image=card, anchor="nw")
        px = x0 + 24
        aw = I.icon("award", C.ACCENT, C.CARD, 22)
        if aw is not None:
            self._imgs.append(aw)
            cv.create_image(px, y + 34, image=aw, anchor="w")
        cv.create_text(px + 32, y + 34, text=f"{self.course['title']} Certificate", anchor="w",
                       fill=C.TEXT, font=self.f["title"])
        cv.create_text(px, y + 70, anchor="w", fill=C.MUTED, font=self.f["small"],
                       text="Complete every requirement below, then request your certificate.")
        ry = y + 96
        for key, label, now, want in self.items:
            done = now >= want and (want > 0 or key != "videos")
            ring = I.pill(26, 26, C.ON if done else C.BG, C.CARD, r=13,
                          border=None if done else C.BORDER)
            if ring is not None:
                self._imgs.append(ring)
                cv.create_image(px, ry + ROW_H / 2, image=ring, anchor="w")
            if done:
                ck = I.icon("check_bold", "#ffffff", C.ON, 16)
                if ck is not None:
                    self._imgs.append(ck)
                    cv.create_image(px + 13, ry + ROW_H / 2, image=ck)
            cv.create_text(px + 40, ry + ROW_H / 2 - 9, text=label, anchor="w",
                           fill=C.TEXT if done else C.TEXT, font=self.f["bold"])
            if key == "videos" and want == 0:
                sub = "Lesson videos are not available yet"
            else:
                sub = f"{min(now, want) if key != 'badges' else now} / {want}"
            cv.create_text(px + 40, ry + ROW_H / 2 + 10, text=sub, anchor="w",
                           fill=C.ON if done else C.MUTED, font=self.f["small"])
            # garis progres tipis di kanan
            bw = 120
            bx = x0 + cw - 24 - bw
            frac = 1.0 if done else (now / want if want else 0)
            track = I.pill(bw, 6, C.BORDER, C.CARD, r=3)
            if track is not None:
                self._imgs.append(track)
                cv.create_image(bx, ry + ROW_H / 2, image=track, anchor="w")
            fw = int(bw * max(0.0, min(1.0, frac)))
            if fw >= 6:
                bar = I.pill(fw, 6, C.ON if done else C.ACCENT, C.BORDER, r=3)
                if bar is not None:
                    self._imgs.append(bar)
                    cv.create_image(bx, ry + ROW_H / 2, image=bar, anchor="w")
            ry += ROW_H
        # tombol
        by = ry + 24
        bw = cw - 48
        req = self.req
        if req is not None:
            done = req.get("status") == CERT.DONE
            text = "Certificate received" if done else "Request sent"
            fill, fg, icon = C.CARD_HOVER, C.ON if done else C.TEXT, "check"
            sub = (f"Given on {req.get('done_at', '')[:10]}" if done
                   else f"Sent {req.get('at', '')[:16]}  ·  waiting for your teacher")
        elif self.ok:
            text, fill = "Request Certificate", C.ACCENT
            fg, icon, sub = "#ffffff", "award", "All requirements complete."
        else:
            text, fill, fg, icon = "Request Certificate", C.BG, C.LOCKED, "lock"
            sub = "Locked until every requirement is complete."
        btn = I.pill(bw, BTN_H, fill, C.CARD, r=10,
                     border=C.BORDER if (req is None and not self.ok) else None)
        tags = ("btn",) if (req is None and self.ok) else ()
        self._btn_item = None
        if btn is not None:
            self._imgs.append(btn)
            self._btn_item = cv.create_image(px, by, image=btn, anchor="nw", tags=tags)
            if tags:        # hover: cukup tukar gambar (tanpa gambar ulang, tidak kedip)
                self._btn_ph = (btn, I.pill(bw, BTN_H, C.ACCENT_HOVER, C.CARD, r=10))
                self._imgs.append(self._btn_ph[1])
        tw = self.f["btn"].measure(text)
        ic = I.icon(icon, fg, fill, 18)
        cx = px + bw / 2
        if ic is not None:
            self._imgs.append(ic)
            cv.create_image(cx - tw / 2 - 8, by + BTN_H / 2, image=ic, anchor="e", tags=tags)
        cv.create_text(cx + 6, by + BTN_H / 2, text=text, fill=fg, font=self.f["btn"],
                       tags=tags)
        msg, col = (self.msg, C.ERROR if self.msg_err else C.MUTED) if self.msg else (sub, C.MUTED)
        cv.create_text(px, by + BTN_H + 18, text=msg, anchor="w", fill=col,
                       font=self.f["small"])
        cv.configure(cursor="")

    def _hover(self, on):
        self._btn_hover = on
        self.cv.configure(cursor="hand2" if on else "")
        ph = getattr(self, "_btn_ph", None)
        if self._btn_item is not None and ph and ph[1] is not None:
            self.cv.itemconfigure(self._btn_item, image=ph[1] if on else ph[0])

    def _request(self):
        if self._busy or self.req is not None or not self.ok:
            return
        self._busy = True
        try:
            self.req = CERT.send_request(self.student, self.course)
            self.msg, self.msg_err = "Request sent to your teacher.", False
        except ValueError as exc:
            self.msg, self.msg_err = str(exc), True
        except OSError as exc:
            C.log(f"Sertifikat gagal disimpan: {exc!r}")
            self.msg, self.msg_err = "Could not save. Try again or ask your teacher.", True
        self._busy = False
        self._btn_hover = False
        self._draw()
        if self.on_change is not None:
            self.on_change()


class CertificateBoard(tk.Canvas):
    """Daftar permintaan sertifikat (admin & guru) di SATU canvas, gambar ulang utuh."""

    ROW_H, GAP = 60, 6

    def __init__(self, master, by=""):
        super().__init__(master, bg=C.BG, highlightthickness=0, bd=0, height=60)
        self.by = by          # nama / ID admin atau guru yang menandai selesai
        self._imgs = []
        self._width = 0
        self.rows = []
        self.f = {"name": tkfont.Font(font=(C.FONT, 11, "bold")),
                  "sub": tkfont.Font(font=(C.FONT, 9)),
                  "cell": tkfont.Font(font=(C.FONT, 10)),
                  "btn": tkfont.Font(font=(C.FONT, 9)),
                  "head": tkfont.Font(font=(C.FONT, 9, "bold"))}
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, e):
        if e.width != self._width:
            self._width = e.width
            self.redraw()

    def show(self, rows):
        self.rows = rows
        self.redraw()

    def redraw(self):
        self.delete("all")
        self._imgs = []
        W = self.winfo_width()
        if W < 200:
            return
        y = 0
        self.create_text(14, 12, text="Murid", anchor="w", font=self.f["head"], fill=C.MUTED)
        self.create_text(int(W * 0.42), 12, text="Kursus", anchor="w", font=self.f["head"],
                         fill=C.MUTED)
        self.create_text(int(W * 0.62), 12, text="Diminta", anchor="w", font=self.f["head"],
                         fill=C.MUTED)
        y = 24
        if not self.rows:
            self.create_text(W / 2, y + 40, text="Belum ada permintaan sertifikat.",
                             fill=C.MUTED, font=self.f["cell"])
            self.configure(height=y + 80)
            return
        card = I.pill(int(W), self.ROW_H, C.CARD, C.BG, r=12, border=C.BORDER)
        for n, r in enumerate(self.rows):
            if card is not None:
                self._imgs.append(card)
                self.create_image(0, y, image=card, anchor="nw")
            cy = y + self.ROW_H / 2
            done = r.get("status") == CERT.DONE
            self.create_text(14, cy - 9, text=r.get("name", r.get("student", "")), anchor="w",
                             font=self.f["name"], fill=C.TEXT)
            self.create_text(14, cy + 10, text=r.get("student", ""), anchor="w",
                             font=self.f["sub"], fill=C.MUTED)
            self.create_text(int(W * 0.42), cy, text=r.get("title", r.get("course", "")),
                             anchor="w", font=self.f["cell"], fill=C.TEXT)
            self.create_text(int(W * 0.62), cy, text=r.get("at", "")[:16], anchor="w",
                             font=self.f["cell"], fill=C.TEXT)
            label = "Batalkan" if done else "Tandai selesai"
            bw = self.f["btn"].measure(label) + 20
            bx = W - 14 - bw
            state = "●  Selesai" if done else "●  Menunggu"
            self.create_text(bx - 14, cy, text=state, anchor="e", font=self.f["cell"],
                             fill=C.ON if done else C.ACCENT)
            self._button(bx, cy, bw, label, n)
            y += self.ROW_H + self.GAP
        self.configure(height=y)

    def _button(self, x, cy, w, text, n):
        tag = f"cb{n}"
        normal = I.pill(w, 24, C.BG, C.CARD, r=8)
        hover = I.pill(w, 24, C.BORDER, C.CARD, r=8)
        self._imgs += [normal, hover]
        img = self.create_image(x, cy - 12, image=normal, anchor="nw", tags=(tag,))
        self.create_text(x + w / 2, cy, text=text, font=self.f["btn"], fill=C.TEXT, tags=(tag,))
        self.tag_bind(tag, "<Enter>", lambda e: (self.itemconfigure(img, image=hover),
                                                 self.config(cursor="hand2")))
        self.tag_bind(tag, "<Leave>", lambda e: (self.itemconfigure(img, image=normal),
                                                 self.config(cursor="")))
        self.tag_bind(tag, "<Button-1>", lambda e: self._toggle(n))

    def _toggle(self, n):
        r = self.rows[n]
        try:
            CERT.set_done(r["id"], r.get("status") != CERT.DONE, by=self.by)
        except (ValueError, OSError) as exc:
            C.log(f"Sertifikat {r.get('id')}: {exc!r}")
        self.show(CERT.list_requests())
