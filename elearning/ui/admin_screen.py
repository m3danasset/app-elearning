"""Panel admin: memantau aktivitas guru dan murid, melihat laporan kerja guru, mengatur
status murid (active / expired), serta menambah / mengubah / menghapus guru."""

import re
import tkinter as tk

from elearning import config as C
from elearning.ui.controls import RoundSelect
from elearning import photos, reports, sessions
from elearning import teachers as T
from elearning.students import (STATUS_ACTIVE, STATUS_EXPIRED, STATUS_LABEL,
                                add_student, list_students, set_status)
from elearning.ui.analytics_view import AnalyticsPanel
from elearning.ui.admin_board import PeopleBoard, ReportsBoard
from elearning.ui.dialogs import ConfirmDialog, StudentDialog, TeacherDialog
from elearning.ui.report_widgets import PeriodBar
from elearning.ui.sidebar import AppSidebar, PageHeader, SidebarLayout
from elearning.ui.widgets import ScrollFrame

REFRESH_MS = 30_000
PROGRAM_LABEL = {"adult": "Murid dewasa", "kids": "Murid anak"}
# (judul kolom, bobot lebar)
COLUMNS = (("Nama", 8), ("Aktivitas", 4), ("Terakhir aktif", 7),
           ("Masuk", 2), ("Total waktu", 3), ("Status akun", 7))


SORTS = ("Nama A–Z", "Nama Z–A", "ID", "Terakhir aktif", "Paling lama belajar")
CATEGORIES = ("Semua kategori", "Murid dewasa", "Murid anak")
STATUSES = ("Semua status", "Active", "Expired", "Sedang online")
# Kata kunci khusus di kolom cari (boleh digabung dengan nama, mis. "anak expired budi")
KEYWORDS = {"expired": ("status", "expired"), "active": ("status", "active"),
            "aktif": ("status", "active"), "online": ("online", True),
            "offline": ("online", False), "anak": ("program", "kids"),
            "dewasa": ("program", "adult")}

TAB_TITLE = {"students": "Murid", "teachers": "Guru", "reports": "Laporan Guru",
             "analytics": "Analytics"}


class AdminScreen(SidebarLayout):
    def __init__(self, master, admin, on_logout):
        super().__init__(master)
        self.admin_id = admin["id"]
        self.tab = "students"
        self._after = None
        self._online = None      # daftar "Sedang online" terakhir
        self._sb_sig = None      # tanda isi sidebar terakhir (lihat _refresh_sidebar)
        self._an_state = {"period": "30d", "program": "all", "view": "full"}   # filter Analytics diingat
        # Urutan & saringan daftar Murid / Guru (diingat selama layar admin terbuka)
        self._sort = "Nama A–Z"
        self._cat = "Semua kategori"
        self._status = "Semua status"

        self.sb = AppSidebar(self, admin, f"Admin  ·  {admin['id']}", on_logout,
                             self._populate, placeholder="Cari murid, guru, laporan",
                             on_search=lambda q: self._search_changed(),
                             suggest=self._suggest, on_enter=self._jump)
        self.attach(self.sb)
        self.enable_search("Cari murid, guru, laporan, atau aksi")

        self.header = PageHeader(self.content, "Panel Admin")
        self.header.pack(fill="x")
        body = tk.Frame(self.content, bg=C.BG, padx=28, pady=4)
        body.pack(fill="both", expand=True)

        self.summary = tk.Label(body, text="", bg=C.BG, fg=C.MUTED,
                                font=(C.FONT, 10), anchor="w")
        self.summary.pack(fill="x", pady=(0, 10))

        # Filter laporan (tab Laporan Guru): periode + guru
        self.rbar = tk.Frame(body, bg=C.BG)
        tk.Label(self.rbar, text="Periode", bg=C.BG, fg=C.MUTED,
                 font=(C.FONT, 10)).pack(side="left", padx=(0, 10))
        self.period = PeriodBar(self.rbar, on_change=self.refresh, key="7d")
        self.period.pack(side="left")
        tk.Label(self.rbar, text="Guru", bg=C.BG, fg=C.MUTED,
                 font=(C.FONT, 10)).pack(side="left", padx=(24, 10))
        self.ALL_TEACHERS = "Semua guru"
        self.teacher_ids = self._teacher_choices(T.list_teachers())
        self.teacher_var = tk.StringVar(value=self.ALL_TEACHERS)
        menu = self.teacher_menu = RoundSelect(
            self.rbar, self.teacher_var, *self.teacher_ids,
            command=lambda _v: self.refresh())
        menu.config(bg=C.CARD, fg=C.TEXT, activebackground=C.BORDER,
                    activeforeground=C.TEXT, relief="flat", bd=0,
                    highlightthickness=0, font=(C.FONT, 10), cursor="hand2")
        menu["menu"].config(bg=C.CARD, fg=C.TEXT, activebackground=C.ACCENT,
                            activeforeground="white", font=(C.FONT, 10), bd=0)
        menu.pack(side="left")

        # Urutkan & saring daftar (tab Murid / Guru)
        self.pbar = tk.Frame(body, bg=C.BG)
        tk.Label(self.pbar, text="Urutkan", bg=C.BG, fg=C.MUTED,
                 font=(C.FONT, 10)).pack(side="left", padx=(0, 8))
        self.sort_var = tk.StringVar(value=self._sort)
        RoundSelect(self.pbar, self.sort_var, *SORTS,
                    command=lambda v: self._set_filter("_sort", v)).pack(side="left")
        self.cat_box = tk.Frame(self.pbar, bg=C.BG)
        self.cat_box.pack(side="left")
        tk.Label(self.cat_box, text="Kategori", bg=C.BG, fg=C.MUTED,
                 font=(C.FONT, 10)).pack(side="left", padx=(20, 8))
        self.cat_var = tk.StringVar(value=self._cat)
        RoundSelect(self.cat_box, self.cat_var, *CATEGORIES,
                    command=lambda v: self._set_filter("_cat", v)).pack(side="left")
        tk.Label(self.cat_box, text="Status", bg=C.BG, fg=C.MUTED,
                 font=(C.FONT, 10)).pack(side="left", padx=(20, 8))
        self.status_var = tk.StringVar(value=self._status)
        RoundSelect(self.cat_box, self.status_var, *STATUSES,
                    command=lambda v: self._set_filter("_status", v)).pack(side="left")

        self.scroll = ScrollFrame(body, bg=C.BG)
        self.scroll.pack(fill="both", expand=True, pady=(6, 0))

        # Isi tiap menu dibuat SEKALI (satu canvas per menu); pindah menu = tukar saja
        self.people_board = PeopleBoard(self.scroll.inner, on_status=self._set_status,
                                        on_edit=self._edit_teacher,
                                        on_delete=self._delete_teacher)
        self.reports_board = ReportsBoard(self.scroll.inner)
        self.analytics = None
        self._shown = None

        # Tombol di kepala halaman dibuat sekali; teks/fungsinya saja yang diganti per menu
        self.reload_btn = self.header.button("Muat ulang", self._reload, icon="refresh")
        self.export_btn = self.header.button("Export Excel", self._export, icon="download")
        self.add_btn = self.header.button("Tambah murid", self._add_student, primary=True,
                                          icon="plus")

        self._layout_tab()
        self.refresh()

    # --- sidebar -------------------------------------------------------------------
    def _populate(self, sb):
        for key, icon in (("students", "users"), ("teachers", "teacher"),
                          ("reports", "report"), ("analytics", "activity")):
            sb.nav(TAB_TITLE[key], icon, lambda k=key: self._set_tab(k),
                   active=self.tab == key)

        # Siapa yang sedang online (klik = tampilkan orang itu di daftar)
        if self._online is None:
            self._online = self._compute_online()
        online = self._online
        sb.section("Sedang online", right=str(len(online)))
        for p in online:
            sb.item(p["name"], lambda p=p: self._show_person(p), dot=C.ON,
                    right="Guru" if p["tab"] == "teachers" else p["id"])
        if not online:
            sb.note("Belum ada guru atau murid yang online.")

    def search_sources(self):
        from elearning.ui.search_sources import admin_sources
        return admin_sources(self)

    def _compute_online(self):
        people = ([{"id": s["id"], "name": s["name"], "tab": "students"}
                   for s in list_students()] +
                  [{"id": t["id"], "name": t["name"], "tab": "teachers"}
                   for t in T.list_teachers()])
        try:
            stats = sessions.overview([p["id"] for p in people])
        except Exception as exc:
            C.log(f"Daftar online gagal: {exc!r}")
            stats = {}
        return [p for p in people if stats.get(p["id"], {}).get("online")]

    def _refresh_sidebar(self):
        """Sidebar dibuat ulang hanya kalau menu aktif / daftar online benar-benar berubah."""
        self._online = self._compute_online()
        sig = (self.tab, tuple((p["id"], p["name"]) for p in self._online))
        if sig != self._sb_sig:
            self._sb_sig = sig
            self.sb.refresh()

    def _show_person(self, person):
        self.tab = person["tab"]
        self._layout_tab()
        self.sb.set_query(person["id"])   # memicu refresh lewat _search_changed

    def _search_changed(self):
        """Kolom cari berubah: saring + sorot di menu yang sedang tampil."""
        for board in (self.people_board, self.reports_board):
            board.focus = -1   # lompatan Enter mulai lagi dari hasil pertama
        if self.tab == "analytics":   # Analytics: nama yang cocok disorot (tanpa pindah menu)
            if self.analytics is not None:
                self.analytics.board.query = self._query_parts()[1]
                self.analytics.board.redraw()
            self.sb.set_count(None)
            return
        self.scroll.scroll_to_top()
        self.refresh()

    # --- kata kunci, saran & lompat ke hasil ----------------------------------------
    def _query_parts(self):
        """(saringan kata kunci, sisa teks). Mis. "anak expired budi" ->
        ({"program": "kids", "status": "expired"}, "budi")."""
        flags, words = {}, []
        for w in self.sb.query.strip().split():
            k = KEYWORDS.get(w.lower())
            if k:
                flags[k[0]] = k[1]
            else:
                words.append(w)
        return flags, " ".join(words)

    def _match(self, *texts):
        q = self._query_parts()[1].lower()
        return not q or any(q in str(t).lower() for t in texts if t)

    def _suggest(self, query):
        """Saran di bawah kolom cari: murid, guru, dan laporan yang cocok (maks 7)."""
        flags, text = self._query_parts()
        q = text.lower()
        out = []
        if not q and not flags:
            return out
        stats = None
        if "online" in flags:
            stats = sessions.overview()
        for s in list_students():
            if flags.get("status") and s.get("status") != flags["status"]:
                continue
            if flags.get("program") and s["program"] != flags["program"]:
                continue
            if stats is not None and bool(stats.get(s["id"], {}).get("online")) != flags["online"]:
                continue
            if q and q not in s["name"].lower() and q not in s["id"].lower():
                continue
            out.append({"title": s["name"],
                        "sub": f"{s['id']}  ·  {PROGRAM_LABEL.get(s['program'], '')}"
                               + ("  ·  expired" if s.get("status") == STATUS_EXPIRED
                                  else ""),
                        "badge": "Murid",
                        "action": lambda s=s: self._show_person({"id": s["id"],
                                                                 "tab": "students"})})
        if not flags.get("status") and not flags.get("program"):
            for t in T.list_teachers():
                if stats is not None and \
                        bool(stats.get(t["id"], {}).get("online")) != flags["online"]:
                    continue
                if q and q not in t["name"].lower() and q not in t["id"].lower():
                    continue
                out.append({"title": t["name"], "sub": t["id"], "badge": "Guru",
                            "action": lambda t=t: self._show_person({"id": t["id"],
                                                                     "tab": "teachers"})})
            if q and "online" not in flags:
                tnames = {t["id"]: t["name"] for t in T.list_teachers()}
                for r in reports.list_reports()[:200]:
                    if q in r["text"].lower() or q in tnames.get(r["teacher"], "").lower():
                        snippet = " ".join(r["text"].split())
                        i = snippet.lower().find(q)
                        if i > 30:
                            snippet = "…" + snippet[i - 20:]
                        out.append({"title": f"Laporan  ·  {tnames.get(r['teacher'], r['teacher'])}",
                                    "sub": snippet, "badge": sessions.format_date(r["day"])[5:],
                                    "hl": False, "action": self._open_reports_all})
                        if len(out) >= 7:
                            break
        return out[:7]

    def _open_reports_all(self):
        """Saran laporan diklik: buka Laporan Guru dengan periode Semua (supaya pasti terlihat)."""
        self._set_tab("reports")
        if self.period.key != "all":
            self.period.select("all")   # memuat ulang daftar

    def _jump(self):
        """Enter di kolom cari: lompat ke hasil berikutnya (garis tepi oranye + digulir)."""
        board = {"students": self.people_board, "teachers": self.people_board,
                 "reports": self.reports_board}.get(self.tab)
        if board is None or not board.item_ys:
            return
        board.focus = (board.focus + 1) % len(board.item_ys)
        board.redraw()
        self.update_idletasks()
        top, _bottom = board.item_ys[board.focus]
        total = max(1, self.scroll.inner.winfo_reqheight())
        self.scroll.canvas.yview_moveto(max(0.0, (board.winfo_y() + top - 40) / total))

    def _set_filter(self, attr, value):
        setattr(self, attr, value)
        self.people_board.focus = -1
        self.scroll.scroll_to_top()
        self.refresh()

    def _open_person(self, pid):
        """Klik nama di Analytics: buka murid / guru itu di tab-nya."""
        tab = "teachers" if any(t["id"] == pid for t in T.list_teachers()) else "students"
        self._show_person({"id": pid, "tab": tab})

    def _add_student(self):
        """Admin menambah murid baru (dialog yang sama dengan layar guru)."""
        created = {}

        def submit(name, program, sid):
            try:
                created.update(add_student(name, program, sid))
            except ValueError as exc:
                return str(exc)
            return None

        StudentDialog(self, "Tambah murid", submit, add=True, program="adult",
                      submit_text="Tambah").wait_window()
        if not created:   # dibatalkan
            return
        self._after_change()
        self.summary.config(
            text=f"Murid {created['id']} ({created['name']}) ditambahkan. Semua kursusnya "
                 "masih terkunci: guru membukanya di menu Murid & Kursus.", fg=C.ON)

    def _add_teacher_from_nav(self):
        self._set_tab("teachers")
        self._add_teacher()

    # --- tab -----------------------------------------------------------------
    def _layout_tab(self):
        """Judul, tombol kepala, baris ringkasan / filter, dan isi yang tampil per menu."""
        self.header.set_title(TAB_TITLE[self.tab], "Panel Admin")
        if self.tab in ("students", "teachers"):
            teachers = self.tab == "teachers"
            self.add_btn.set(text="Tambah guru" if teachers else "Tambah murid",
                             command=self._add_teacher if teachers else self._add_student)
            if not self.add_btn.winfo_manager():
                self.add_btn.pack(side="right", padx=(8, 0), after=self.export_btn)
        else:
            self.add_btn.pack_forget()
        if self.tab == "analytics":   # halaman grafik: tanpa ringkasan & filter laporan
            self.summary.pack_forget()
            self.rbar.pack_forget()
        else:
            if not self.summary.winfo_manager():
                self.summary.pack(fill="x", pady=(0, 10), before=self.scroll)
            if self.tab == "reports":
                if not self.rbar.winfo_manager():
                    self.rbar.pack(fill="x", before=self.scroll)
            else:
                self.rbar.pack_forget()
        # bar urutkan / saring: hanya di Murid & Guru (kategori & status khusus murid)
        if self.tab in ("students", "teachers"):
            if not self.pbar.winfo_manager():
                self.pbar.pack(fill="x", pady=(0, 6), before=self.scroll)
            if self.tab == "students":
                if not self.cat_box.winfo_manager():
                    self.cat_box.pack(side="left")
            else:
                self.cat_box.pack_forget()
        else:
            self.pbar.pack_forget()
        # isi: satu widget per menu, ditukar (tidak dibuat ulang)
        if self.tab == "analytics" and self.analytics is None:
            self.analytics = AnalyticsPanel(self.scroll.inner, self._an_state,
                                            on_open=self._open_person)
        want = {"students": self.people_board, "teachers": self.people_board,
                "reports": self.reports_board, "analytics": self.analytics}[self.tab]
        if self._shown is not want:
            if self._shown is not None:
                self._shown.pack_forget()
            want.pack(fill="x")
            self._shown = want

    def _export(self):
        """Riwayat login ke Excel; admin memilih periode, data, dan foldernya sendiri."""
        try:
            from elearning.ui.export_dialog import ExportDialog
            ExportDialog(self, default_who={"students": "students",
                                            "teachers": "teachers"}.get(self.tab, "all"))
        except Exception as exc:   # jangan diam saja: catat penyebabnya di app.log
            import traceback
            C.log("Export Excel tidak bisa dibuka: " + "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)))
            self.bell()

    def _reload(self):
        """Tombol Muat ulang: Analytics dihitung ulang dari data terbaru."""
        if self.tab == "analytics" and self.analytics is not None:
            self.analytics._cache.clear()
            self.analytics.load()
            return
        self.refresh()

    def _set_tab(self, key):
        if key == self.tab:
            return
        self.tab = key
        self._layout_tab()
        self.scroll.scroll_to_top()
        self.refresh()

    # --- data ------------------------------------------------------------------
    def _people(self):
        """Daftar yang tampil + statistiknya: disaring (cari, kata kunci, kategori, status)
        lalu diurutkan sesuai pilihan "Urutkan"."""
        if self.tab == "teachers":
            people = [{"id": t["id"], "name": t["name"], "sub": "Guru", "teacher": True}
                      for t in T.list_teachers()]
        else:
            people = [{"id": s["id"], "name": s["name"], "status": s["status"],
                       "program": s["program"], "sub": PROGRAM_LABEL.get(s["program"], "")}
                      for s in list_students()]
        stats = sessions.overview([p["id"] for p in people])
        flags, _text = self._query_parts()
        students = self.tab == "students"
        cat = {"Murid dewasa": "adult", "Murid anak": "kids"}.get(self._cat)
        status = {"Active": "active", "Expired": "expired"}.get(self._status)

        def keep(p):
            online = bool(stats.get(p["id"], {}).get("online"))
            if students:
                if cat and p["program"] != cat:
                    return False
                if status and p["status"] != status:
                    return False
                if self._status == "Sedang online" and not online:
                    return False
                if flags.get("program") and p["program"] != flags["program"]:
                    return False
                if flags.get("status") and p["status"] != flags["status"]:
                    return False
            if "online" in flags and online != flags["online"]:
                return False
            return self._match(p["id"], p["name"], p["sub"])

        people = [p for p in people if keep(p)]
        st = lambda p: stats.get(p["id"]) or {}
        def natural(text):   # "Uji 2" sebelum "Uji 10"
            return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", text.lower())]

        if self._sort == "Nama Z–A":
            people.sort(key=lambda p: natural(p["name"]), reverse=True)
        elif self._sort == "ID":
            people.sort(key=lambda p: p["id"])
        elif self._sort == "Terakhir aktif":
            people.sort(key=lambda p: (st(p).get("last_seen") is None,
                                       -(st(p)["last_seen"].timestamp()
                                         if st(p).get("last_seen") else 0)))
        elif self._sort == "Paling lama belajar":
            people.sort(key=lambda p: -(st(p).get("total") or 0))
        else:   # Nama A-Z
            people.sort(key=lambda p: natural(p["name"]))
        return people, stats

    @staticmethod
    def _configure_columns(frame):
        for i, (_t, weight) in enumerate(COLUMNS):
            frame.grid_columnconfigure(i, weight=weight, uniform="col")

    def _filter_note(self):
        q = self.sb.query.strip()
        return f"  ·  cari “{q}”" if q else ""

    def refresh(self):
        """Muat ulang isi menu yang tampil (otomatis tiap 30 detik selama layar ini terbuka).
        Canvas digambar ulang utuh sekaligus: tidak berkedip walau dipanggil berkala."""
        if self._after is not None:
            self.after_cancel(self._after)
        self._refresh_sidebar()   # daftar "Sedang online" ikut diperbarui
        if self.tab == "analytics":   # dihitung ulang hanya saat dibuka / Muat ulang
            return
        if self.tab == "reports":
            self._refresh_reports()
        else:
            self._refresh_people()
        self._after = self.after(REFRESH_MS, self.refresh)

    def _refresh_people(self):
        people, stats = self._people()
        online = sum(1 for p in people if stats.get(p["id"], {}).get("online"))
        noun = "guru" if self.tab == "teachers" else "murid"
        expired = sum(1 for p in people if p.get("status") == STATUS_EXPIRED)
        extra = f"{expired} expired  \u00b7  " if self.tab == "students" else ""
        self.summary.config(
            fg=C.MUTED,
            text=f"{len(people)} {noun}  \u00b7  {online} sedang online  \u00b7  {extra}"
                 f"diperbarui {sessions.format_time(sessions.datetime.now())}"
                 f"{self._filter_note()}")
        filtered = bool(self.sb.query.strip()) or self._cat != CATEGORIES[0] \
            or self._status != STATUSES[0]
        empty = (f"Tidak ada {noun} yang cocok dengan pencarian / saringan." if filtered
                 else f"Belum ada {noun}.")
        self.people_board.query = self._query_parts()[1]
        self.people_board.show(people, stats, empty)
        self.sb.set_count(len(people) if self.sb.query.strip() else None)

    # --- tab Laporan Guru -------------------------------------------------------
    def _refresh_reports(self):
        since, until = self.period.range()
        teachers = T.list_teachers()
        teacher_names = {t["id"]: t["name"] for t in teachers}
        self._rebuild_teacher_menu(teachers)
        teacher_id = self.teacher_ids.get(self.teacher_var.get())
        names = {s["id"]: s["name"] for s in list_students()}
        recs = [r for r in reports.list_reports(teacher_id, since, until)
                if self._match(r["text"], r["teacher"], teacher_names.get(r["teacher"]),
                               r["student"], names.get(r["student"]),
                               reports.KIND_LABEL.get(r["kind"]))]
        try:
            rows = reports.portfolio_status(since, until)
        except Exception as exc:   # ringkasan gagal tidak boleh menghalangi laporan
            C.log(f"Ringkasan portfolio gagal: {exc!r}")
            rows = []

        who = (f"{len({r['teacher'] for r in recs if r['teacher'] in teacher_names})} "
               f"dari {len(teachers)} guru melapor"
               if teacher_id is None else
               teacher_names.get(teacher_id, teacher_id))
        self.summary.config(
            fg=C.MUTED,
            text=f"{len(recs)} laporan  ·  {who}  ·  "
                 f"diperbarui {sessions.format_time(sessions.datetime.now())}"
                 f"{self._filter_note()}")

        text = self._query_parts()[1]
        if text:   # ringkasan portfolio ikut disaring nama / ID murid
            rows = [r for r in rows if self._match(r["id"], r["name"])]
        self.reports_board.query = text
        self.reports_board.show(
            rows, recs, names, teacher_names, warn=self.period.key != "today",
            empty=("Tidak ada laporan yang cocok dengan pencarian." if self.sb.query.strip()
                   else "Belum ada laporan pada periode ini."))
        self.sb.set_count(len(recs) + (len(rows) if text else 0)
                          if self.sb.query.strip() else None)

    # --- kelola guru (tab Guru) ----------------------------------------------------
    def _teacher_choices(self, teachers):
        choices = {self.ALL_TEACHERS: None}
        for t in teachers:
            choices[f"{t['name']}  ({t['id']})"] = t["id"]
        return choices

    def _rebuild_teacher_menu(self, teachers):
        """Samakan isi menu filter Laporan Guru dengan daftar guru terbaru."""
        choices = self._teacher_choices(teachers)
        if choices == self.teacher_ids:
            return
        selected = self.teacher_ids.get(self.teacher_var.get())
        self.teacher_ids = choices
        label = next((l for l, tid in choices.items() if tid == selected), self.ALL_TEACHERS)
        self.teacher_var.set(label)
        menu = self.teacher_menu["menu"]
        menu.delete(0, "end")
        for text in choices:
            menu.add_command(label=text, command=lambda t=text: (
                self.teacher_var.set(t), self.refresh()))

    def _after_change(self):
        """Muat ulang daftar tapi tetap di posisi gulir semula (baris dibuat ulang: foto bisa
        saja berubah)."""
        top = self.scroll.canvas.yview()[0]
        self.refresh()
        self.update_idletasks()
        self.scroll.canvas.yview_moveto(top)

    @staticmethod
    def _apply_photo(teacher_id, photo):
        """photo: None = tidak berubah, False = hapus foto, gambar Pillow = simpan. True kalau berhasil."""
        try:
            if photo is False:
                photos.remove_photo(teacher_id)
            elif photo is not None:
                photos.save_prepared(teacher_id, photo)
            return True
        except Exception as exc:
            C.log(f"Gagal menyimpan foto {teacher_id}: {exc!r}")
            return False

    def _add_teacher(self):
        def submit(name, pin, photo):
            try:
                teacher = T.add_teacher(name, pin)
            except ValueError as exc:
                return str(exc)
            # Guru baru tanpa foto pilihan = tanpa foto (jangan mewarisi file lama yang tersisa)
            ok = self._apply_photo(teacher["id"], False if photo is None else photo)
            self._after_change()
            if not ok:
                self.summary.config(
                    text=f"{teacher['name']} ditambahkan, tetapi fotonya gagal disimpan.",
                    fg=C.ERROR)
            return None

        TeacherDialog(self, "Tambah guru", submit, teacher_id=T.next_teacher_id(), add=True)

    def _edit_teacher(self, person):
        tid = person["id"]

        def submit(name, pin, photo):
            try:
                T.update_teacher(tid, name, pin or None)
            except ValueError as exc:
                return str(exc)
            ok = self._apply_photo(tid, photo)
            self._after_change()
            if not ok:
                self.summary.config(text=f"Data {tid} tersimpan, tetapi fotonya gagal diubah.",
                                    fg=C.ERROR)
            return None

        TeacherDialog(self, f"Ubah guru {tid}", submit, teacher_id=tid, add=False,
                      name=person["name"])

    def _delete_teacher(self, person):
        tid = person["id"]

        def confirm():
            try:
                T.delete_teacher(tid)
            except ValueError as exc:
                return str(exc)
            self._after_change()
            return None

        ConfirmDialog(
            self, "Hapus guru",
            f"Hapus akun {person['name']} ({tid})? Foto dan riwayat masuk/keluarnya ikut "
            "terhapus dan tidak bisa dikembalikan. Laporan kerja yang pernah ditulis guru "
            "ini tetap tersimpan.", confirm)

    def _set_status(self, student_id, status):
        top = self.scroll.canvas.yview()[0]
        try:
            set_status(student_id, status)
        except Exception as exc:
            C.log(f"Gagal mengubah status {student_id}: {exc!r}")
            self.summary.config(
                text="Gagal menyimpan status. Pastikan folder data bisa ditulis.",
                fg=C.ERROR)
            return
        self.refresh()
        self.update_idletasks()
        self.scroll.canvas.yview_moveto(top)   # tetap di posisi gulir semula

    def destroy(self):
        if self._after is not None:
            try:
                self.after_cancel(self._after)
            except Exception:
                pass
            self._after = None
        super().destroy()
