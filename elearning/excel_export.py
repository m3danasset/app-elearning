"""Export data ke SATU file Excel (.xlsx) — hanya dijalankan saat admin menekan Export.

File .xlsx ditulis langsung (zip + XML) dengan modul bawaan Python, tanpa library tambahan,
jadi tidak perlu build ulang .exe. Sheet (bisa dipilih di dialog, lihat SHEETS):
  Riwayat Login, Ringkasan, Data Murid, Portfolio, Laporan Guru, Aktivitas Guru,
  Rekap Harian, Progres Kursus + Progres Video, Jadwal + Jadwal Sesi, Kehadiran Jadwal,
  Badge Murid. Data Murid juga berisi tanggal lahir, umur, label PB/IC/SK, jadwal, badge.
Tanggal & jam disimpan sebagai tanggal Excel asli, jadi bisa diurutkan / disaring / dihitung.
"""

import os
import re
from datetime import datetime, timedelta, timezone

# CATATAN: sengaja TIDAK memakai zipfile / xml / calendar / struct. Modul itu belum tentu
# ikut terbungkus di dalam .exe (kode lama tidak memakainya), dan import yang gagal membuat
# fitur ini mati. File .xlsx (= zip) ditulis sendiri. zlib (kompresi) dipakai kalau ada;
# kalau tidak, file disimpan tanpa kompresi (tetap sah, hanya sedikit lebih besar).
try:
    import zlib
except Exception:      # pragma: no cover - cadangan untuk .exe tanpa zlib
    zlib = None

_CRC_TABLE = []
for _n in range(256):
    _c = _n
    for _k in range(8):
        _c = (0xEDB88320 ^ (_c >> 1)) if _c & 1 else (_c >> 1)
    _CRC_TABLE.append(_c)


def _crc32(data):
    if zlib is not None:
        return zlib.crc32(data) & 0xFFFFFFFF
    crc = 0xFFFFFFFF
    for b in data:
        crc = _CRC_TABLE[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF


def _le(*pairs):
    """Bilangan little-endian: _le((nilai, jumlah byte), ...)."""
    return b"".join(int(v).to_bytes(n, "little") for v, n in pairs)

from elearning import config as C
from elearning import achievements, portfolio, progress, reports, schedule, sessions
from elearning import teachers as T
from elearning.courses import COURSES, courses_for
from elearning.students import STATUS_EXPIRED, STATUS_LABEL, age_of, list_students

MONTHS = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
          "September", "Oktober", "November", "Desember")
DAYS = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")

WHO = (("all", "Murid & guru"), ("students", "Semua murid"), ("adult", "Murid dewasa"),
       ("kids", "Murid anak"), ("teachers", "Guru"))
ROLE = {"adult": "Murid dewasa", "kids": "Murid anak", "teacher": "Guru"}

# (kode, label di dialog) — semua masuk ke satu file, masing-masing satu sheet
SHEETS = (("logins", "Riwayat login"), ("summary", "Ringkasan per orang"),
          ("students", "Data murid"), ("portfolio", "Portfolio"),
          ("reports", "Laporan guru"), ("teachers", "Aktivitas guru"),
          ("daily", "Rekap harian"), ("progress", "Progres, catatan & kuis"),
          ("schedule", "Jadwal kelas (daftar + sesi)"), ("attendance", "Kehadiran jadwal"),
          ("badges", "Badge murid"), ("signups", "Pendaftar dari trial"))
SHEETS_FILE = os.path.join(C.DATA_DIR, "export_sheets.txt")   # pilihan terakhir

FOLDER_FILE = os.path.join(C.DATA_DIR, "export_folder.txt")   # folder terakhir yang dipilih


# --- periode ---------------------------------------------------------------------------
def month_label(month):
    """"2026-09" -> "September 2026"."""
    y, m = int(month[:4]), int(month[5:7])
    return f"{MONTHS[m - 1]} {y}"


def _month_range(month):
    y, m = int(month[:4]), int(month[5:7])
    start = datetime(y, m, 1)
    end = datetime(y + 1, 1, 1) if m == 12 else datetime(y, m + 1, 1)
    return start, end


def escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class _Zip:
    """Penulis zip minimal (deflate) untuk file .xlsx."""

    def __init__(self, path):
        self.f = open(path, "wb")
        self.entries = []

    def writestr(self, name, text):
        data = text.encode("utf-8")
        crc = _crc32(data)
        if zlib is not None:
            c = zlib.compressobj(6, zlib.DEFLATED, -15)
            comp, method = c.compress(data) + c.flush(), 8     # 8 = deflate
        else:
            comp, method = data, 0                              # 0 = tanpa kompresi
        fname = name.encode("utf-8")
        offset = self.f.tell()
        # 0x0800 = nama file UTF-8; 0x21 = tanggal DOS tetap (1 Jan 1980)
        self.f.write(_le((0x04034B50, 4), (20, 2), (0x0800, 2), (method, 2), (0, 2),
                         (0x21, 2), (crc, 4), (len(comp), 4), (len(data), 4),
                         (len(fname), 2), (0, 2)))
        self.f.write(fname)
        self.f.write(comp)
        self.entries.append((fname, crc, len(comp), len(data), offset, method))

    def close(self):
        start = self.f.tell()
        for fname, crc, csize, size, offset, method in self.entries:
            self.f.write(_le((0x02014B50, 4), (20, 2), (20, 2), (0x0800, 2), (method, 2),
                             (0, 2), (0x21, 2), (crc, 4), (csize, 4), (size, 4),
                             (len(fname), 2), (0, 2), (0, 2), (0, 2), (0, 2), (0, 4),
                             (offset, 4)))
            self.f.write(fname)
        size = self.f.tell() - start
        n = len(self.entries)
        self.f.write(_le((0x06054B50, 4), (0, 2), (0, 2), (n, 2), (n, 2), (size, 4),
                         (start, 4), (0, 2)))
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if exc[0] is None:
            self.close()
        else:
            self.f.close()


def periods():
    """Pilihan periode: [(label, start, end, nama file)]. start/end datetime (end eksklusif)."""
    now = datetime.now()
    today = datetime(now.year, now.month, now.day)
    tomorrow = today + timedelta(days=1)
    this_month = now.strftime("%Y-%m")
    prev = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    out = [("Bulan ini", *_month_range(this_month), month_label(this_month)),
           ("Bulan lalu", *_month_range(prev), month_label(prev))]
    for n, label in ((7, "7 hari terakhir"), (30, "30 hari terakhir"),
                     (90, "3 bulan terakhir")):
        start = today - timedelta(days=n - 1)
        out.append((label, start, tomorrow, f"{_d(start)} sd {_d(today)}"))
    out.append(("Semua riwayat", None, None, f"Semua sd {_d(today)}"))
    # bulan-bulan arsip, terbaru dulu (bulan ini & bulan lalu sudah ada di atas)
    for m in reversed(sessions.archive_months()):
        if m not in (this_month, prev):
            out.append((month_label(m), *_month_range(m), month_label(m)))
    return out


def _d(dt):
    return dt.strftime("%d-%m-%Y")


# --- folder ----------------------------------------------------------------------------
def default_folder():
    try:
        with open(FOLDER_FILE, encoding="utf-8") as f:
            path = f.read().strip()
        if path and os.path.isdir(path):
            return path
    except OSError:
        pass
    home = os.path.expanduser("~")
    for sub in ("Documents", "Dokumen", "Desktop"):
        p = os.path.join(home, sub)
        if os.path.isdir(p):
            return p
    return home


def remember_folder(path):
    try:
        os.makedirs(C.DATA_DIR, exist_ok=True)
        with open(FOLDER_FILE, "w", encoding="utf-8") as f:
            f.write(path)
    except OSError as exc:
        C.log(f"Folder export tidak bisa diingat: {exc!r}")


def free_name(folder, base):
    """Nama file yang belum dipakai: "X.xlsx", lalu "X (2).xlsx", dst."""
    base = re.sub(r'[\\/:*?"<>|]', "-", base).strip() or "Riwayat Login"
    path = os.path.join(folder, base + ".xlsx")
    n = 2
    while os.path.exists(path):
        path = os.path.join(folder, f"{base} ({n}).xlsx")
        n += 1
    return path


def load_sheets():
    """Sheet yang terakhir dipilih (default: semua)."""
    keys = [k for k, _l in SHEETS]
    try:
        with open(SHEETS_FILE, encoding="utf-8") as f:
            lines = f.read().split("\n")
        got = [k for k in lines[0].split() if k in keys]
        # baris 2 = sheet yang sudah dikenal saat disimpan; sheet BARU otomatis ikut dicentang
        known = set(lines[1].split()) if len(lines) > 1 and lines[1].strip() else \
            {"logins", "summary", "students", "portfolio", "reports", "teachers", "daily",
             "progress"}
        got += [k for k in keys if k not in known]
        return set(got) if got else set(keys)
    except OSError:
        return set(keys)


def save_sheets(chosen):
    try:
        os.makedirs(C.DATA_DIR, exist_ok=True)
        with open(SHEETS_FILE, "w", encoding="utf-8") as f:
            f.write(" ".join(k for k, _l in SHEETS if k in chosen) + "\n"
                    + " ".join(k for k, _l in SHEETS))
    except OSError as exc:
        C.log(f"Pilihan sheet export tidak bisa diingat: {exc!r}")


# --- data ------------------------------------------------------------------------------
def collect(start, end, who="all"):
    """(baris sesi, baris ringkasan) untuk periode & kelompok yang dipilih."""
    people = {}
    for s in list_students():
        people[s["id"]] = (s["name"], s["program"])
    for t in T.list_teachers():
        people[t["id"]] = (t["name"], "teacher")

    def wanted(role):
        if who == "all":
            return True
        if who == "students":
            return role in ("adult", "kids", None)
        if who == "teachers":
            return role == "teacher"
        return role == who

    now = datetime.now()
    rows = []
    for r in sessions.records(start):
        s0 = sessions._parse(r["in"])
        if s0 is None or (start is not None and s0 < start) or (end is not None and s0 >= end):
            continue
        name, role = people.get(r["id"], ("(sudah dihapus)", None))
        if not wanted(role):
            continue
        out = sessions._parse(r.get("out")) if r.get("out") else None
        note = ""
        if out is None:
            out = sessions._parse(r.get("last")) or s0
            if r.get("last") and (now - out).total_seconds() <= sessions.ONLINE_WINDOW:
                note = "Masih login"
                out = None
            else:
                note = "Jam keluar perkiraan"
        elif r.get("auto"):
            note = "Jam keluar perkiraan"
        seconds = max(0, ((out or now) - s0).total_seconds())
        rows.append({"id": r["id"], "name": name,
                     "role": ROLE.get(role, "Murid" if role is None else role),
                     "start": s0, "end": out, "minutes": round(seconds / 60), "note": note,
                     "seconds": seconds, "pc": r.get("pc", ""), "kind": role})
    rows.sort(key=lambda x: x["start"])

    summary = {}
    for x in rows:
        s = summary.setdefault(x["id"], {"id": x["id"], "name": x["name"], "role": x["role"],
                                         "count": 0, "seconds": 0.0, "last": None})
        s["count"] += 1
        s["seconds"] += x["seconds"]
        if s["last"] is None or x["start"] > s["last"]:
            s["last"] = x["start"]
    summ = sorted(summary.values(), key=lambda s: (-s["seconds"], s["id"]))
    return rows, summ


# --- penulis .xlsx ------------------------------------------------------------------------
_BAD = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")
_EPOCH = datetime(1899, 12, 30)

# gaya: 0 biasa, 1 kepala tabel, 2 tanggal, 3 jam, 4 tanggal+jam, 5 angka 1 desimal,
#       6 judul, 7 keterangan abu, 8 teks panjang (turun baris)
_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="4"><numFmt numFmtId="164" formatCode="dd/mm/yyyy"/>
<numFmt numFmtId="165" formatCode="hh:mm"/><numFmt numFmtId="166" formatCode="dd/mm/yyyy hh:mm"/>
<numFmt numFmtId="167" formatCode="0.0"/></numFmts>
<fonts count="4"><font><sz val="11"/><name val="Calibri"/></font>
<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
<font><b/><sz val="14"/><name val="Calibri"/></font>
<font><sz val="10"/><color rgb="FF7F7F7F"/><name val="Calibri"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFEA7600"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border>
<border><left/><right/><top/><bottom style="thin"><color rgb="FFD9D9D9"/></bottom><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="9">
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment vertical="center"/></xf>
<xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"><alignment horizontal="left"/></xf>
<xf numFmtId="165" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"><alignment horizontal="center"/></xf>
<xf numFmtId="166" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"><alignment horizontal="left"/></xf>
<xf numFmtId="167" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>
<xf numFmtId="0" fontId="3" fillId="0" borderId="0" xfId="0" applyFont="1"/>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""


def _col(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _cell(ref, value, style=0):
    if value is None or value == "":
        return f'<c r="{ref}" s="{style}"/>' if style else ""
    if isinstance(value, datetime):
        v = (value - _EPOCH).total_seconds() / 86400.0
        return f'<c r="{ref}" s="{style}"><v>{v:.10f}</v></c>'
    if isinstance(value, (int, float)):
        return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
    text = escape(_BAD.sub("", str(value)))
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _sheet(title, sub, header, widths, rows, styles):
    """rows: daftar list nilai; styles: gaya per kolom. Judul di baris 1-2, tabel mulai baris 4."""
    first = 4
    last = first + max(1, len(rows))
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
           'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
           '<sheetPr><pageSetUpPr fitToPage="1"/></sheetPr><sheetViews><sheetView workbookViewId="0" showGridLines="0">'
           f'<pane ySplit="{first}" topLeftCell="A{first + 1}" activePane="bottomLeft" '
           'state="frozen"/></sheetView></sheetViews>',
           '<sheetFormatPr defaultRowHeight="15"/><cols>']
    for i, w in enumerate(widths):
        out.append(f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>')
    out.append('</cols><sheetData>')
    out.append(f'<row r="1" ht="22" customHeight="1">{_cell("A1", title, 6)}</row>')
    out.append(f'<row r="2">{_cell("A2", sub, 7)}</row>')
    cells = "".join(_cell(f"{_col(i)}{first}", h, 1) for i, h in enumerate(header))
    out.append(f'<row r="{first}" ht="20" customHeight="1">{cells}</row>')
    for n, row in enumerate(rows):
        r = first + 1 + n
        cells = "".join(_cell(f"{_col(i)}{r}", v, styles[i]) for i, v in enumerate(row))
        out.append(f'<row r="{r}">{cells}</row>')
    out.append('</sheetData>')
    out.append(f'<autoFilter ref="A{first}:{_col(len(header) - 1)}{last - (0 if rows else 1)}"/>')
    out.append('<pageMargins left="0.5" right="0.5" top="0.6" bottom="0.6" header="0.3" '
               'footer="0.3"/><pageSetup orientation="landscape" fitToWidth="1" '
               'fitToHeight="0"/></worksheet>')
    return "".join(out)


def _workbook(path, sheets):
    """sheets: [(nama, xml)]. Ditulis ke file sementara lalu diganti (tidak setengah jadi)."""
    names = [n for n, _x in sheets]
    ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
          '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>']
    for i in range(len(sheets)):
        ct.append(f'<Override PartName="/xl/worksheets/sheet{i + 1}.xml" ContentType='
                  '"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    ct.append('</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '</Relationships>')
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<dc:title>Data E-Learning</dc:title><dc:creator>Blender E-Learning M3DAN Studios</dc:creator>'
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{stamp}</dcterms:created>'
            '</cp:coreProperties>')
    wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>']
    for i, n in enumerate(names):
        wb.append(f'<sheet name="{escape(n)}" sheetId="{i + 1}" r:id="rId{i + 1}"/>')
    wb.append('</sheets><definedNames>')
    for i, (n, xml) in enumerate(sheets):
        m = re.search(r'<autoFilter ref="([A-Z]+)(\d+):([A-Z]+)(\d+)"', xml)
        if m:
            wb.append(f'<definedName name="_xlnm._FilterDatabase" localSheetId="{i}" hidden="1">'
                      f"'{escape(n)}'!${m.group(1)}${m.group(2)}:${m.group(3)}${m.group(4)}"
                      '</definedName>')
    wb.append('</definedNames></workbook>')
    wrels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for i in range(len(sheets)):
        wrels.append(f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/'
                     f'officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i + 1}.xml"/>')
    wrels.append(f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/'
                 'officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')

    tmp = path + ".tmp"
    with _Zip(tmp) as z:
        z.writestr("[Content_Types].xml", "".join(ct))
        z.writestr("_rels/.rels", rels)
        z.writestr("docProps/core.xml", core)
        z.writestr("xl/workbook.xml", "".join(wb))
        z.writestr("xl/_rels/workbook.xml.rels", "".join(wrels))
        z.writestr("xl/styles.xml", _STYLES)
        for i, (_n, xml) in enumerate(sheets):
            z.writestr(f"xl/worksheets/sheet{i + 1}.xml", xml)
    os.replace(tmp, path)



def _in(dt, start, end):
    return (start is None or dt >= start) and (end is None or dt < end)


def _student_ok(program, who):
    return who in ("all", "students") or who == program


def _course_titles():
    return {c["id"]: c["title"] for c in COURSES}


def _uploads(students):
    """Portfolio + assignment murid: [(murid, waktu, jenis, id kursus, nama file, ukuran,
    bagian)]; bagian = "Portfolio" / "Assignment"."""
    out = []
    for s in students:
        for c in courses_for(s["program"]):
            try:
                for sec, label in ((None, "Portfolio"), (portfolio.ASSIGNMENT, "Assignment")):
                    for it in portfolio.list_items(s["id"], c["id"], sec):
                        out.append((s, it["added"], it["kind"], c["id"], it["name"],
                                    it["size"], label))
            except Exception as exc:
                C.log(f"Export: portfolio {s['id']}/{c['id']} gagal dibaca: {exc!r}")
    out.sort(key=lambda u: u[1])
    return out


def _label(s):
    """Label seperti sheet jadwal: SK (anak), IC (intermediate dibuka), PB (dewasa)."""
    if s["program"] == "kids":
        return "SK"
    return "IC" if any(c.startswith("intermediate") for c in s["courses"]) else "PB"


def _slot_text(sl):
    return f"{schedule.DAYS[sl['day']]} {sl['start']}-{sl['end']}"


def _progress_rows(students):
    """(per kursus, per video) dari progres pelajaran murid."""
    data = progress.all_progress()
    titles = _course_titles()
    per_course, per_video = [], []
    counts = {}
    for s in students:
        mine = data.get(s["id"], {})
        for cid in s["courses"]:
            course = next((c for c in COURSES if c["id"] == cid), None)
            if course is None or not course.get("video", True):   # AI: tanpa video
                continue
            if cid not in counts:
                counts[cid] = progress.lesson_count(course)
            total = counts[cid]
            lessons = mine.get(cid, {})
            done = sum(1 for v in lessons.values() if v.get("done"))
            last_title, last = "", None
            for title, v in lessons.items():
                when = sessions._parse(v.get("last"))
                if when and (last is None or when > last):
                    last_title, last = title, when
                emo = progress.emote_of(v)
                emotes = progress.EMOTE_LABEL.get(emo, "") if emo else ""
                per_video.append([s["id"], s["name"], titles.get(cid, cid), title,
                                  int(v.get("pct", 0)), "Selesai" if v.get("done") else "Belum",
                                  _mmss(v.get("pos", 0)), int(v.get("views", 0)),
                                  round(v.get("dur", 0) / 60.0, 1),
                                  sessions._parse(v.get("first")), when,
                                  v.get("note", ""), emotes])
            pct = min(100, round(done * 100 / total)) if total else None
            per_course.append([s["id"], s["name"], ROLE[s["program"]], titles.get(cid, cid),
                               done, total or "-", pct, len(lessons), last_title or "-", last])
    per_video.sort(key=lambda r: (r[0], r[2], r[3]))
    return per_course, per_video


def _mmss(sec):
    sec = max(0, int(sec or 0))
    return f"{sec // 60:02d}:{sec % 60:02d}"


def _quiz_rows(students, titles):
    from elearning import quizzes
    names = {s["id"]: s["name"] for s in students}
    rows = []
    for q in sorted(quizzes.list_quizzes(), key=lambda q: q.get("created", "")):
        for sid in q.get("students", []):
            if sid not in names:
                continue
            a = progress.answers(sid).get(q["id"])
            verdict = ("Belum menjawab" if a is None else
                       {True: "Benar", False: "Salah"}.get(a.get("correct"), "Dinilai guru"))
            rows.append([titles.get(q["course"], q["course"]), q["lesson"], q["question"],
                         q.get("answer") or "-", sid, names[sid],
                         a.get("answer", "") if a else "", verdict,
                         sessions._parse(a.get("t")) if a else None])
    return rows


def export(path, label, start, end, who="all", sheets=None):
    """Tulis SATU file Excel berisi sheet yang dipilih. Mengembalikan jumlah sesi login."""
    chosen = set(sheets) if sheets else {k for k, _l in SHEETS}
    rows, summ = collect(start, end, who)
    now = datetime.now()
    who_label = dict(WHO).get(who, "")
    sub = (f"Periode: {label}   ·   Data: {who_label}   ·   Dibuat "
           f"{now:%d/%m/%Y %H:%M}")
    titles = _course_titles()
    all_students = list_students()
    students = [s for s in all_students if _student_ok(s["program"], who)]
    teachers = T.list_teachers()
    if who == "teachers":
        students = []
    sid_set = {s["id"] for s in students}
    need_up = chosen & {"summary", "students", "portfolio", "daily"}
    uploads = _uploads(students) if need_up else []
    up_period = [u for u in uploads if _in(u[1], start, end)]
    try:
        reps = reports.list_reports(None, start.date() if start else None,
                                    (end - timedelta(days=1)).date() if end else None)
    except Exception as exc:
        C.log(f"Export: laporan gagal dibaca: {exc!r}")
        reps = []
    reps.sort(key=lambda r: (r["date"], r["created"]))
    tnames = {t["id"]: t["name"] for t in teachers}
    snames = {s["id"]: s["name"] for s in all_students}
    out = []

    if "logins" in chosen:
        log_rows = [[i + 1, x["id"], x["name"], x["role"],
                     x["start"].replace(hour=0, minute=0, second=0),
                     DAYS[x["start"].weekday()], x["start"], x["end"], x["minutes"],
                     x["pc"], x["note"]] for i, x in enumerate(rows)]
        out.append(("Riwayat Login", _sheet(
            "Riwayat Login", f"{sub}   ·   {len(rows)} sesi",
            ["No", "ID", "Nama", "Peran", "Tanggal", "Hari", "Masuk", "Keluar",
             "Durasi (menit)", "Nama PC", "Keterangan"],
            [6, 10, 26, 15, 13, 10, 9, 9, 15, 16, 22], log_rows,
            [0, 0, 0, 0, 2, 0, 3, 3, 0, 0, 0])))

    if "summary" in chosen:
        up_by = {}
        for u in up_period:
            if u[6] != "Portfolio":
                continue
            up_by[u[0]["id"]] = up_by.get(u[0]["id"], 0) + 1
        rep_about, rep_by = {}, {}
        for r in reps:
            if r["student"]:
                rep_about[r["student"]] = rep_about.get(r["student"], 0) + 1
            rep_by[r["teacher"]] = rep_by.get(r["teacher"], 0) + 1
        stu = {s["id"]: s for s in all_students}
        sum_rows = []
        for i, s in enumerate(summ):
            st = stu.get(s["id"])
            is_t = s["id"] in tnames
            courses = ", ".join(titles.get(c, c) for c in st["courses"]) if st else ""
            status = STATUS_LABEL.get(st["status"], "") if st else ("Guru" if is_t else "")
            sum_rows.append([i + 1, s["id"], s["name"], s["role"], s["count"],
                             round(s["seconds"] / 3600.0, 1),
                             round(s["seconds"] / 60.0 / s["count"]) if s["count"] else 0,
                             s["last"], up_by.get(s["id"], 0) if not is_t else None,
                             rep_by.get(s["id"], 0) if is_t else rep_about.get(s["id"], 0),
                             status, courses])
        out.append(("Ringkasan", _sheet(
            "Ringkasan per orang", f"{sub}   ·   {len(summ)} orang",
            ["No", "ID", "Nama", "Peran", "Jumlah login", "Total jam",
             "Rata-rata (menit/login)", "Login terakhir", "Upload portfolio",
             "Laporan (guru: ditulis, murid: tentang dia)", "Status akun", "Kursus dibuka"],
            [6, 10, 26, 15, 14, 12, 22, 18, 17, 24, 13, 50], sum_rows,
            [0, 0, 0, 0, 0, 5, 0, 4, 0, 0, 0, 8])))

    if "students" in chosen:
        ov = sessions.overview(sid_set)
        up_all = {}
        for u in uploads:
            up_all[u[0]["id"]] = up_all.get(u[0]["id"], 0) + 1
        prog = progress.all_progress()
        slots_all = schedule.list_slots()
        st_rows = []
        for i, s in enumerate(students):
            birth = s.get("birth") or ""
            try:
                bdt = datetime.strptime(birth, "%Y-%m-%d") if birth else None
            except ValueError:
                bdt = None
            mine = [_slot_text(sl) for sl in slots_all if s["id"] in sl["students"]]
            try:
                n_badge = len(achievements.earned_all(s["id"]))   # semua kursus
            except Exception:
                n_badge = 0
            n_asg = sum(1 for u in uploads if u[0]["id"] == s["id"] and u[6] == "Assignment")
            o = ov.get(s["id"])
            last = o["last_seen"] if o else None
            idle = (now - last).days if last else None
            done = sum(1 for c in prog.get(s["id"], {}).values()
                       for v in c.values() if v.get("done"))
            st_rows.append([i + 1, s["id"], s["name"], ROLE[s["program"]],
                            STATUS_LABEL.get(s["status"], s["status"]), len(s["courses"]),
                            ", ".join(titles.get(c, c) for c in s["courses"]) or "-",
                            o["count"] if o else 0,
                            round(o["total"] / 3600.0, 1) if o else 0.0,
                            last, idle if idle is not None else "Belum pernah",
                            up_all.get(s["id"], 0) - n_asg, n_asg, done,
                            _label(s), bdt, age_of(birth) if birth else None, n_badge,
                            "; ".join(mine) or "-"])
        out.append(("Data Murid", _sheet(
            "Data Murid (sepanjang masa)", f"{sub}   ·   {len(students)} murid",
            ["No", "ID", "Nama", "Kategori", "Status akun", "Jumlah kursus", "Kursus dibuka",
             "Total login", "Total jam", "Login terakhir", "Hari tidak login",
             "Upload portfolio", "Upload assignment", "Video selesai", "Label",
             "Tanggal lahir", "Umur", "Badge", "Jadwal"],
            [6, 10, 26, 15, 13, 14, 50, 12, 11, 18, 16, 16, 18, 14, 8, 14, 8, 8, 40], st_rows,
            [0, 0, 0, 0, 0, 0, 8, 0, 5, 4, 0, 0, 0, 0, 0, 2, 0, 0, 8])))

    if "portfolio" in chosen:
        pf_rows = [[i + 1, u[1], u[0]["id"], u[0]["name"], ROLE[u[0]["program"]],
                    titles.get(u[3], u[3]), u[6], "Gambar" if u[2] == "image" else "Video",
                    u[4], round(u[5] / 1048576.0, 1)] for i, u in enumerate(up_period)]
        out.append(("Portfolio", _sheet(
            "Upload Portfolio & Assignment", f"{sub}   ·   {len(pf_rows)} file",
            ["No", "Waktu upload", "ID", "Nama", "Kategori", "Kursus", "Bagian", "Jenis",
             "Nama file", "Ukuran (MB)"],
            [6, 18, 10, 26, 15, 18, 13, 10, 40, 13], pf_rows,
            [0, 4, 0, 0, 0, 0, 0, 0, 0, 5])))

    if "reports" in chosen:
        rp_rows = []
        for i, r in enumerate(reps):
            if who not in ("all", "teachers") and r["student"] and r["student"] not in sid_set:
                continue
            rp_rows.append([len(rp_rows) + 1, datetime(r["day"].year, r["day"].month,
                                                       r["day"].day),
                            r["teacher"], tnames.get(r["teacher"], r["teacher"]),
                            reports.KIND_LABEL.get(r["kind"], r["kind"]),
                            r["student"] or "-", snames.get(r["student"], "") if r["student"]
                            else "Umum", r["text"], sessions._parse(r["created"])])
        out.append(("Laporan Guru", _sheet(
            "Laporan Guru", f"{sub}   ·   {len(rp_rows)} laporan",
            ["No", "Tanggal", "ID guru", "Guru", "Jenis", "ID murid", "Murid", "Isi laporan",
             "Ditulis"],
            [6, 13, 10, 22, 18, 10, 24, 70, 18], rp_rows, [0, 2, 0, 0, 0, 0, 0, 8, 4])))

    if "teachers" in chosen:
        t_rows_all, _ts = collect(start, end, "teachers") if who not in ("all", "teachers") \
            else (rows, summ)
        per = {}
        for x in t_rows_all:
            if x["kind"] != "teacher":
                continue
            p = per.setdefault(x["id"], {"n": 0, "sec": 0.0, "last": None, "pcs": set()})
            p["n"] += 1
            p["sec"] += x["seconds"]
            if p["last"] is None or x["start"] > p["last"]:
                p["last"] = x["start"]
            if x["pc"]:
                p["pcs"].add(x["pc"])
        t_rows = []
        for i, t in enumerate(teachers):
            p = per.get(t["id"], {"n": 0, "sec": 0.0, "last": None, "pcs": set()})
            mine = [r for r in reps if r["teacher"] == t["id"]]
            studs = sorted({r["student"] for r in mine if r["student"]})
            t_rows.append([i + 1, t["id"], t["name"], p["n"], round(p["sec"] / 3600.0, 1),
                           p["last"], len(mine), len(studs),
                           ", ".join(f"{snames.get(x, x)} ({x})" for x in studs) or "-",
                           ", ".join(sorted(p["pcs"])) or "-"])
        out.append(("Aktivitas Guru", _sheet(
            "Aktivitas Guru", f"{sub}   ·   {len(teachers)} guru",
            ["No", "ID", "Nama", "Jumlah login", "Jam online", "Login terakhir",
             "Laporan ditulis", "Murid ditangani", "Daftar murid", "PC yang dipakai"],
            [6, 10, 24, 14, 12, 18, 16, 16, 60, 22], t_rows,
            [0, 0, 0, 0, 5, 4, 0, 0, 8, 0])))

    if "daily" in chosen:
        if start is not None:
            d0, d1 = start.date(), min(end, now + timedelta(days=1)).date()
        else:
            firsts = [x["start"] for x in rows] + [u[1] for u in up_period]
            d0 = min(firsts).date() if firsts else now.date()
            d1 = now.date() + timedelta(days=1)
        days = {}
        d = d0
        while d < d1:
            days[d] = {"stu": set(), "tea": set(), "n": 0, "sec": 0.0, "up": 0, "rep": 0}
            d += timedelta(days=1)
        for x in rows:
            g = days.get(x["start"].date())
            if g is None:
                continue
            g["n"] += 1
            if x["kind"] == "teacher":
                g["tea"].add(x["id"])
            else:
                g["stu"].add(x["id"])
                g["sec"] += x["seconds"]
        for u in up_period:
            if u[6] != "Portfolio":
                continue
            g = days.get(u[1].date())
            if g is not None:
                g["up"] += 1
        for r in reps:
            g = days.get(r["day"])
            if g is not None:
                g["rep"] += 1
        dy_rows = [[datetime(k.year, k.month, k.day), DAYS[k.weekday()], len(g["stu"]),
                    len(g["tea"]), g["n"], round(g["sec"] / 3600.0, 1), g["up"], g["rep"]]
                   for k, g in sorted(days.items())]
        out.append(("Rekap Harian", _sheet(
            "Rekap Harian", f"{sub}   ·   {len(dy_rows)} hari",
            ["Tanggal", "Hari", "Murid login", "Guru login", "Total sesi",
             "Jam belajar murid", "Upload portfolio", "Laporan guru"],
            [13, 10, 13, 12, 12, 18, 17, 14], dy_rows, [2, 0, 0, 0, 0, 5, 0, 0])))

    if "progress" in chosen:
        per_course, per_video = _progress_rows(students)
        note = "   ·   Video selesai = ditonton minimal 90%"
        out.append(("Progres Kursus", _sheet(
            "Progres Pelajaran per Kursus", f"{sub}{note}",
            ["ID", "Nama", "Kategori", "Kursus", "Video selesai", "Total video",
             "Progres (%)", "Video pernah dibuka", "Pelajaran terakhir", "Terakhir belajar"],
            [10, 26, 15, 18, 14, 12, 12, 19, 36, 18], per_course,
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 4])))
        out.append(("Progres Video", _sheet(
            "Progres per Video", f"{sub}{note}",
            ["ID", "Nama", "Kursus", "Pelajaran", "Ditonton (%)", "Status", "Posisi terakhir",
             "Dibuka (kali)", "Durasi (menit)", "Pertama dibuka", "Terakhir dibuka",
             "Catatan murid", "Emote (review)"],
            [10, 26, 18, 40, 14, 10, 15, 14, 15, 18, 18, 50, 36], per_video,
            [0, 0, 0, 0, 0, 0, 0, 0, 5, 4, 4, 8, 8])))
        qrows = _quiz_rows(students, titles)
        out.append(("Kuis", _sheet(
            "Hasil Kuis", f"{sub}   ·   {len(qrows)} jawaban / penerima",
            ["Kursus", "Video", "Pertanyaan", "Kunci", "ID", "Nama", "Jawaban murid",
             "Hasil", "Dijawab"],
            [16, 30, 50, 20, 10, 26, 30, 16, 18], qrows, [0, 0, 8, 0, 0, 0, 8, 0, 4])))

    if chosen & {"schedule", "attendance"}:
        slots = schedule.list_slots()
        stu_by = {s["id"]: s for s in all_students}
        want = [sl for sl in slots if who == "teachers"
                or any(m in sid_set for m in sl["students"]) or not sl["students"]]

    if "schedule" in chosen:
        colors = {k: n for k, n, _h in schedule.COLORS}
        sc_rows = []
        for i, sl in enumerate(want):
            names = [f"{_label(stu_by[m])} {stu_by[m]['name']} ({m})" for m in sl["students"]
                     if m in stu_by and (who == "teachers" or m in sid_set)]
            sc_rows.append([i + 1, schedule.DAYS[sl["day"]], sl["start"], sl["end"],
                            tnames.get(sl["teacher"], sl["teacher"] or "-"), sl["note"] or "-",
                            colors.get(sl.get("color", ""), "Otomatis"), len(names),
                            "; ".join(names) or "-"])
        out.append(("Jadwal", _sheet(
            "Jadwal Kelas (berulang tiap minggu)", f"{sub}   ·   {len(sc_rows)} jadwal",
            ["No", "Hari", "Mulai", "Selesai", "Guru", "Catatan", "Warna", "Jumlah murid",
             "Murid"],
            [6, 10, 9, 9, 22, 22, 11, 14, 90], sc_rows, [0, 0, 0, 0, 0, 0, 0, 0, 8])))
        # Jadwal Sesi: seperti tampilan Sesi / sheet jadwal (kolom = jam, baris = slot)
        h0, h1 = getattr(C, "SCHEDULE_HOURS", (8, 21))
        hours = list(range(h0, h1))
        ss_rows = []
        for day in range(7):
            cells = {}
            items = []
            for sl in want:
                if sl["day"] != day:
                    continue
                a = max(h0, schedule.to_min(sl["start"]) // 60)
                b = min(h1, -(-schedule.to_min(sl["end"]) // 60))
                for m in sl["students"]:
                    if m in stu_by and (who == "teachers" or m in sid_set):
                        items.append((a, b, m))
            items.sort(key=lambda t: (t[0], -(t[1] - t[0]), stu_by[t[2]]["name"].lower()))
            rows_n = 0
            for a, b, m in items:
                r = 0
                while any((r, h) in cells for h in range(a, b)):
                    r += 1
                for h in range(a, b):
                    cells[(r, h)] = f"{_label(stu_by[m])} {stu_by[m]['name']}"
                rows_n = max(rows_n, r + 1)
            for r in range(rows_n):
                ss_rows.append([schedule.DAYS[day] if r == 0 else "", r + 1]
                               + [cells.get((r, h), "") for h in hours])
        out.append(("Jadwal Sesi", _sheet(
            "Jadwal Sesi (kolom = jam, baris = slot murid)", f"{sub}",
            ["Hari", "Slot"] + [f"{h:02d}.00-{h + 1:02d}.00" for h in hours],
            [10, 6] + [17] * len(hours), ss_rows, [0, 0] + [0] * len(hours))))

    if "attendance" in chosen:
        from elearning import analytics as AN
        a1 = min(end, now) if end is not None else now
        if start is not None:
            a0 = start
        else:
            sinces = [sl["since"] for sl in want if sl.get("since")]
            a0 = datetime.strptime(min(sinces), "%Y-%m-%d") if sinces else a1 - timedelta(days=30)
        by_sid = {}
        for x in rows:
            if x["kind"] != "teacher":
                by_sid.setdefault(x["id"], []).append((x["start"], x["end"]))
        if not rows and sid_set:      # data login hanya guru: baca sesi murid sendiri
            for x in collect(start, end, "students")[0]:
                by_sid.setdefault(x["id"], []).append((x["start"], x["end"]))
        active = {s["id"] for s in students if s["status"] != STATUS_EXPIRED}
        at_rows = []
        for sl, d, m, here, o0, _o1 in sorted(
                AN.occurrences(want, by_sid, active, a0, a1),
                key=lambda t: (t[4], stu_by[t[2]]["name"].lower())):
            at_rows.append([len(at_rows) + 1, datetime(d.year, d.month, d.day),
                            schedule.DAYS[sl["day"]], f"{sl['start']}-{sl['end']}", m,
                            stu_by[m]["name"], _label(stu_by[m]),
                            tnames.get(sl["teacher"], sl["teacher"] or "-"),
                            "Hadir" if here else "Tidak hadir"])
        hadir = sum(1 for r in at_rows if r[-1] == "Hadir")
        pct = f"{round(hadir / len(at_rows) * 100)}%" if at_rows else "-"
        out.append(("Kehadiran Jadwal", _sheet(
            "Kehadiran Sesuai Jadwal",
            f"{sub}   ·   {hadir}/{len(at_rows)} hadir ({pct})   ·   hadir = login min. "
            f"{AN.PRESENT_MIN} menit di jam jadwal",
            ["No", "Tanggal", "Hari", "Jam", "ID", "Nama", "Label", "Guru", "Kehadiran"],
            [6, 13, 10, 13, 10, 26, 8, 22, 14], at_rows, [0, 2, 0, 0, 0, 0, 0, 0, 0])))

    if "badges" in chosen:
        bg_rows = []
        for s in students:
            try:
                got = achievements.earned_all(s["id"])     # badge per kursus
            except Exception as exc:
                C.log(f"Export: badge {s['id']} gagal dibaca: {exc!r}")
                got = []
            for cid, bid, t in sorted(got, key=lambda r: r[2]):
                b = achievements.BY_ID.get(bid)
                if b is None:
                    continue
                try:
                    when = datetime.strptime(t, achievements.FMT)
                except Exception:
                    when = None
                if when is not None and not _in(when, start, end):
                    continue
                cat = dict((k, n) for k, n, _c in achievements.CATEGORIES).get(b["cat"], "")
                bg_rows.append([len(bg_rows) + 1, when, s["id"], s["name"], _label(s),
                                titles.get(cid, cid), b["name"], cat, b["desc"]])
        out.append(("Badge Murid", _sheet(
            "Badge Murid", f"{sub}   ·   {len(bg_rows)} badge didapat (badge berlaku per kursus)",
            ["No", "Didapat", "ID", "Nama", "Label", "Kursus", "Badge", "Kategori",
             "Cara mendapat"],
            [6, 18, 10, 26, 8, 18, 24, 13, 50], bg_rows, [0, 4, 0, 0, 0, 0, 0, 0, 8])))

    if "signups" in chosen:
        from elearning import signups as SU
        st_text = {SU.PENDING: "Menunggu", SU.APPROVED: "Jadi murid", SU.REJECTED: "Ditolak"}
        su_rows = []
        for r in sorted(SU.list_all(), key=lambda r: r.get("at", "")):
            try:
                when = datetime.strptime(r.get("at", ""), SU.FMT)
            except Exception:
                when = None
            if when is not None and not _in(when, start, end):
                continue
            su_rows.append([len(su_rows) + 1, when, r["id"]]
                           + [r.get(k, "") for k in SU.KEYS]
                           + [st_text.get(r.get("status"), r.get("status", "")),
                              r.get("student", "")])
        waiting = sum(1 for x in su_rows if x[-2] == "Menunggu")
        out.append(("Pendaftar", _sheet(
            "Pendaftar dari Trial (survey)",
            f"{sub}   ·   {len(su_rows)} pendaftar   ·   {waiting} menunggu",
            ["No", "Masuk", "Kode"] + [f[2] for f in SU.FIELDS] + ["Status", "ID murid"],
            [6, 18, 8, 24, 16, 7, 24, 26, 18, 24, 16, 36, 18, 30, 12, 10], su_rows,
            [0, 4, 0] + [8 if f[4] else 0 for f in SU.FIELDS] + [0, 0])))

    if not out:
        raise ValueError("tidak ada sheet yang dipilih")
    _workbook(path, out)
    C.log(f"Export Excel: {len(out)} sheet, {len(rows)} sesi -> {path}")
    return len(rows)
