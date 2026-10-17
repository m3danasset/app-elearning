# Blender E-Learning (M3DAN Studios): catatan untuk Claude Code

Aplikasi desktop Tkinter (Windows 11), dikirim sebagai .exe (PyInstaller). Revisi dipasang
dengan update.bat yang menimpa file .py yang direvisi. Peran: admin, guru, murid (dewasa
PB..., anak SK...), trial. Balas pengguna dalam bahasa Indonesia.

## Cek wajib sebelum setiap build / revisi
1. Hanya pakai modul yang sudah ikut di .exe. JANGAN pakai: zipfile, xml, socket, glob,
   tkinter.filedialog, tkinter.messagebox, ImageDraw, ImageFilter. Untuk dialog pakai
   bawaan Tk (tk_getOpenFile, tk_chooseDirectory). Tes dengan modul-modul itu diblokir;
   import yang gagal membuat .exe diam-diam kembali ke aplikasi lama.
2. Tidak boleh ada glitch UI (tombol terpotong, blok hitam) saat pindah windowed/fullscreen,
   tab, periode, filter, atau tampilan.
3. Animasi harus mulus, tidak patah-patah: jadwal frame tetap, gerakan berbasis waktu.
   SEMUA animasi UI maks. 30 fps (pakai config.UI_FPS / UI_FRAME_MS, jangan angka sendiri).
   Pengecualian: carousel login di PC spek tinggi (config.HIGH_END = driver NVIDIA + >= 12
   thread) maks. 60 fps dengan 4 thread render (config.CAROUSEL_WORKERS / CAROUSEL_FPS_MAX).
   Ukur jarak antar frame di layar biasa dan 1920x1080 sebelum dikirim.
4. Tidak ada yang pecah/pixelated (ikon, panah, switch, centang, lingkaran, bentuk apa pun):
   pakai gambar antialias (ui/ui_icons.py), bukan garis Tk.
5. Harus ringan di Ryzen 5 2400G + Vega (tanpa GPU terpisah), juga Ryzen 3 (4 thread), dan
   tidak boleh mengganggu Blender murid. Kerja berat di thread (Pillow melepas GIL), tapi
   jumlahnya maks. config.WORKER_THREADS (1 di CPU 4 thread, maks. 2); OpenCV dibatasi
   setNumThreads. Proses berjalan BelowNormal (config._low_priority). Tk hanya dipanggil
   dari thread utama. Simulasi spek rendah: cmd /c start "" /affinity F "dist\Blender E-Learning.exe"
6. Kirim zip kumulatif berisi file .py yang berubah untuk update.bat; folder data harus aman.
7. UI konsisten dengan layar login & gaya claude.ai: sudut membulat, ikon minimalis.
   Setiap fitur/tombol baru wajib mengikuti gaya ini.

## Badge / achievement (PER KURSUS)
- elearning/achievements.py: 20 badge PER KURSUS (tiap kursus set sendiri; sama untuk dewasa &
  SUPERKIDS, trial tidak dapat), data per murid di data\achievements\<ID>.json
  {"courses": {cid: {"badges", "days"}}}; badge global lama disimpan tapi tidak dipakai.
  Video dihitung dari bagian yang BENAR-BENAR ditonton (progress.py "seen", min. 80 %).
- Badge kejadian (buka kursus = Halo, Blender, easter egg) masuk ke kursus yang sedang /
  terakhir dibuka (BadgeTracker.course_opened). Konsisten = hari membuka kursus itu.
  Menu Badges hanya di sidebar kursus (tidak di halaman utama); guru memilih kursus.
- ui/badge_art.py (ikon, numpy), ui/badge_ui.py (halaman Badge, notifikasi kiri-bawah di atas
  sidebar, pelacak di thread). Notifikasi ditahan saat video layar penuh / Blender dipakai.
- Easter egg diatur di config.py (SECRET_CODE, SPECIAL_DAYS); ganti berkala.
- Belum: easter egg khusus trial. (Statistik badge sudah ada di Analytics.)

## Status terakhir (layar login)
- ui/login_screen.py: logo besar (assets\logo.png, dengan bayangan lembut buatan sendiri),
  kolom "Enter Your ID" transparan (gambar + teks canvas, bukan Entry), kolom PIN tambahan
  muncul di bawahnya untuk ID guru/admin (Enter/Tab/panah = pindah, Esc = kembali ke ID).
  Tanpa tombol Masuk (Enter).
- ui/carousel3d.py: carousel 3D silinder, maks. 10 portfolio murid (bukan assignment /
  contoh guru), loop, 30 fps dengan jadwal frame tetap, gerak lambat (1 kartu / 9 detik),
  fade tepi kiri-kanan. Dirender di 2-3 thread.
- ui/login_bg.py: canvas video latar (opacity rendah) + pita carousel.
- config.py: LOGIN_CAROUSEL_FPS = 30 (maks. 30).
- Belum diuji langsung di PC studio (Ryzen 5 2400G): kelancaran carousel & ukuran logo asli.

## Search palette (Ctrl+K), semua peran
- ui/search_palette.py: SearchBar (kolom cari di tengah bawah area isi, jalur sendiri
  setinggi 68 px lewat SidebarLayout.enable_search) + SearchPalette (jendela cari gaya
  claude.ai: tab tipe, "Terakhir dibuka", hasil per tipe, "Aksi", petunjuk Esc/panah/Enter).
  Windows: latar redup (-alpha) + sudut panel tembus (-transparentcolor), muncul 120 ms.
  Ditutup otomatis saat jendela pindah / windowed <-> fullscreen (ResizeCurtain + _watch).
- ui/search_sources.py: isi per peran (murid/trial: kursus, pelajaran, aksi; guru: murid,
  aksi; admin: murid, guru, laporan, aksi). Layar cukup punya search_sources().
- elearning/recents.py: riwayat "Terakhir dibuka" per akun di data\recents.json
  (trial hanya di memori). Layar kursus: tanpa kolom bawah (pemutar video), Ctrl+K tetap.
- Low-end (config.WORKER_THREADS == 1, mis. Ryzen 3 2200G): palette tampil langsung tanpa
  fade alpha. PC lain: fade 120 ms, 30 fps jadwal tetap. Ketikan digabung 1x per frame;
  panel dibuat tersembunyi lalu ditampilkan utuh. Dialog konfirmasi menutup palette dulu.
- students.list_students membaca data sekali (dulu O(n^2) deepcopy): buka palette admin
  300 murid ~50 ms di 1 core (sebelumnya ~600 ms).

## File browser murid (Resource, Portfolio, Assignment)
- ui/file_browser.py: FileBrowser (overlay yang sama dengan search palette: OverlayPanel di
  search_palette.py). Tampilan Details / Small thumbnails (diingat selama aplikasi terbuka).
  Mode "pick": tombol Upload murid (Portfolio / Assignment) memilih gambar & video dari PC
  HANYA drive lokal murid (config.STUDENT_DRIVE, default Z:\) dan flashdisk yang tercolok;
  folder lain, naik di atas akar drive, dan shortcut/junction ke luar drive ditolak.
  Drive B: (sistem e-learning) dan C: (Windows) (config.BLOCKED_DRIVES) diblok total: tidak tampil, tidak bisa dibuka,
  dan Simpan ke flashdisk menolak tujuan di B: / C: (usb_save).
  centang banyak file -> Upload. Guru tetap memakai dialog bawaan Windows.
  Mode "resource": ResourcePage di layar kursus, hanya baca: buka (Enter / klik dua kali),
  centang -> Simpan ke flashdisk; tidak bisa naik di atas folder kursus.
  File cadangan Blender (.blend1, .blend2, ...) disembunyikan di semua mode.
- elearning/resources.py: resource di assets\resources\<id kursus atau judul>\ (boleh
  subfolder). Di .exe: dist\assets\resources\ (update.bat tidak menyalinnya).
- Isi folder & thumbnail di thread (maks. WORKER_THREADS), thumbnail hanya yang terlihat,
  cache 400 gambar; hasil diambil 1x per frame. Ukur (1 core): buka ~50 ms, aksi main
  thread maks. ~11 ms, 24 thumbnail render Full HD ~0,9 dtk (bertahap).

## Referensi guru -> Blender (tanpa addon)
- Gambar "Dari guru" (Portfolio / Assignment murid) punya tombol ikon panel di pojok sampul:
  blender_launcher.open_with_reference membuka Blender BARU dengan
  --python elearning\blender_scripts\reference_view.py -- <gambar>. Skrip itu (bukan addon,
  tidak dipasang) membelah 3D viewport: Image Editor kiri 35 % + gambar. Handler load_post
  persistent: File > New / Open tetap dapat Image Editor + gambar selama Blender itu terbuka.
- Kalau Blender sudah terbuka: pesan "Simpan & tutup Blender dulu" (tanpa addon tidak bisa
  mengirim gambar ke Blender yang sedang jalan). Belum diuji di Blender asli (4.2).


## Jadwal kelas (Panel Admin, tab Jadwal)
- elearning/schedule.py: data\schedule.json, jadwal mingguan berulang {day 0=Senin, start,
  end, teacher, students, note}. Murid dihapus -> otomatis keluar dari semua jadwal.
- ui/schedule_view.py: ScheduleBoard = kalender mingguan di SATU canvas (Senin-Minggu x jam
  config.SCHEDULE_HOURS, default 08-21), kolom hari ini + garis jam sekarang oranye, blok
  bersudut bulat (biru = dewasa, merah muda = anak, ungu = campuran), jadwal bertabrakan
  berdampingan. Klik kotak kosong = tambah di hari/jam itu, klik blok = ubah/hapus
  (ScheduleDialog: hari, mulai, selesai tiap 30 menit, guru, catatan, centang murid + cari).
  Kolom cari sidebar menyorot jadwal yang cocok (nama/ID murid, guru, catatan).
- Baris atas kalender (di canvas yang sama): Hari / Minggu (diingat), panah sebelum/
  sesudah, Hari ini / Minggu ini, tanggal. Tampilan Hari: satu kolom lebar, nama murid
  berkolom. Klik nama hari di tampilan Minggu = buka hari itu. Redraw ~8 ms.
- Tampilan Sesi (default admin, seperti sheet jadwal): satu hari, kolom = sesi per jam,
  baris = slot murid 1-20 (MAX_ROWS), sel "SK/PB/IC Nama" (IC = kursus intermediate dibuka).
  Murid yang sama di jam berurutan tetap satu baris; kepala kolom "terisi/20" (+lebih).
  Klik nama = ubah jadwal, klik sel kosong = tambah di jam itu. Guru tetap tampilan Hari.
- Warna jadwal: schedule.COLORS (Otomatis + 6 template: biru, hijau, oranye, merah, ungu,
  abu-abu), field "color" di schedule.json. Admin memilih di ScheduleDialog (lingkaran warna);
  Otomatis = warna kategori murid. Semua tampilan (Sesi, Hari, Minggu, guru) memakai warna itu;
  guru hanya melihat.

## Analytics admin (tab paling atas, dibuka pertama)
- Kartu angka: murid aktif (+ tanpa jadwal), jam belajar, kehadiran jadwal (%), portfolio,
  assignment, badge didapat (naik/turun vs periode sebelumnya; kehadiran dalam poin).
- Kehadiran jadwal: tiap jadwal yang SUDAH selesai sejak jadwal dibuat ("since" di
  schedule.json); hadir = login min. 10 menit di jam jadwal (boleh 15 menit lebih awal).
- Kartu baru: Kehadiran per jadwal, Badge paling banyak didapat; grafik upload ikut
  Assignment; "Perlu diperhatikan" + hadir jadwal < 50 % / belum punya jadwal; "Paling
  rajin" + jumlah badge. compute() tetap di thread.

## Tanggal lahir & umur; jadwal untuk guru
- students.json: "birth" (YYYY-MM-DD, opsional). Hanya admin yang mengisi: tombol "Tgl lahir"
  di daftar Murid (BirthDialog: tanggal/bulan/tahun, Kosongkan). students.age_of/age_text:
  umur dihitung dari tanggal HARI INI setiap kali tampil (otomatis naik saat ulang tahun).
  Guru hanya melihat umur (detail murid, Jadwal Murid), tidak pernah tanggal lahirnya.
- Guru: menu "Jadwal Murid" (schedule_view.TeacherSchedule) = ScheduleBoard day_only:
  hanya tampilan Hari, panah + Hari ini, hanya lihat (tidak bisa tambah/ubah), nama murid
  + umur, diperbarui tiap 60 detik.


## Impor murid dari sheet jadwal Oktober 2026
- elearning/student_import.py: daftar murid PB / IC / SK dari sheet (label lain tidak).
  IC = intermediate = murid dewasa (ID PB...). Jalan otomatis sekali saat admin login
  (penanda data\import_oktober2026.done), bisa diulang dari Ctrl+K admin; nama + kategori
  yang sudah ada dilewati. Kursus awal dibuka: PB BASIC 1, IC INTERMEDIATE 1, SK SUPERKIDS 1.
- Jadwal Sabtu & Minggu dari sheet yang sama: student_import.SHEET_SCHEDULE -> 39 jadwal
  (satu per hari + jam + guru), otomatis sekali saat admin login (data\import_jadwal_oktober2026.done),
  ulang lewat Ctrl+K (hanya jadwal bercatatan "Sheet Okt 2026" yang diganti). Guru dicocokkan
  ke akun guru menurut nama; kalau tidak ada, nama guru masuk catatan jadwal.

## Video pembuka pelajaran (murid, bukan trial)
- assets\video\intro\intro.mp4: 1080p, 3 detik, fade-out (dari video 4K 6,2 dtk; dikecilkan
  supaya ringan di Vega). update.bat SELALU menyalinnya ke dist\assets\video\intro\.
- lesson_view.LessonPlayer.load_with_intro: intro diputar otomatis di pemutar utama, lalu
  video pelajaran langsung diputar (lanjut tonton tetap berlaku). Maks. 3 dtk; macet/gagal
  > 4 dtk -> langsung pelajaran. Saat intro: tanpa progres, tidak bisa digeser, tombol
  putar/jeda overlay disembunyikan; klik / spasi = lewati intro. Tiap ganti pelajaran
  (Selanjutnya / Sebelumnya / sidebar) intro diputar lagi. Trial (student_id None) tanpa intro.

## Export Excel admin (fitur baru ikut)
- excel_export.SHEETS + Jadwal (daftar: hari, jam, guru, catatan, warna, murid) & Jadwal Sesi
  (seperti tampilan Sesi), Kehadiran Jadwal (per murid per jadwal yang sudah selesai; aturan
  sama dengan Analytics lewat analytics.occurrences), Badge Murid. Data Murid + label PB/IC/SK,
  tanggal lahir, umur, badge, upload assignment, jadwal. Portfolio + kolom Bagian
  (Portfolio / Assignment). Sheet baru otomatis tercentang di dialog (baris 2 export_sheets.txt).


## Sertifikat (request per kursus)
- elearning/certificates.py: syarat per kursus = semua video ditonton (progress.completed),
  min. 5 assignment & min. 1 portfolio di kursus itu, min. 10 badge (total). Kursus tanpa
  video: syarat video & assignment dilewati. Permintaan di data\certificate_requests.json
  (pending / done), satu per murid per kursus; ikut terhapus saat murid dihapus.
- ui/certificate_view.py: CertificatePage (menu "Sertifikat" di sidebar kursus murid, bukan
  trial; syarat dihitung di thread, diambil thread utama 1x per frame) dan CertificateBoard
  (Panel Admin tab Sertifikat + menu Sertifikat guru; Tandai selesai / Batalkan). Angka di
  menu = permintaan yang menunggu.

## Bahasa: layar murid English
- elearning/i18n.py: L("Indonesia", "English"); bahasa diatur saat login (window.py):
  murid & trial = English, login / guru / admin = Indonesia. Komponen bersama (sidebar,
  search palette, dialog, portfolio, gallery, usb_save, pesan Blender) memakai L();
  file khusus murid (lesson_view, lesson_extras, course_dock, file_browser, mini_player,
  halaman sertifikat) langsung English. Badge punya name_en/desc_en, kursus desc_en
  (courses.visible_for). Fitur murid baru wajib English.

## Jendela Dev (Ctrl kanan + Shift kanan + Backspace, semua layar)
- Dikunci PIN: shortcut membuka DevPinDialog dulu (Enter = cek, Esc = batal). Di kode hanya
  hash (dev_panel.DEV_PIN_HASH = _pin_hash(pin), FNV-1a bergaram, tanpa hashlib), bukan teks
  PIN. 5x salah -> dikunci 60 dtk. Tiap jendela Dev ditutup, PIN diminta lagi.
- ui/dev_panel.py: jendela sederhana (widget Tk biasa), selalu di atas. Tab Login (cari akun,
  masuk tanpa PIN; App.dev_login keluar dulu tanpa konfirmasi) dan Settings: tampilan login,
  warna aksen (app_settings.ACCENTS, berlaku setelah app dibuka ulang: apply_theme di App),
  fitur on/off (app_settings.FEATURES: intro, badges, certificate, floating, mini_player,
  palette, fps60; cek dengan app_settings.feature). Fitur baru yang bisa dimatikan: tambahkan
  ke FEATURES + cek feature() di kodenya. Tab Setting di Panel Admin sudah dihapus.
- Tab Login: 3 kolom (Jenis | ID | Nama, huruf Consolas), filter jenis, urut Nama/ID/Jenis.
  "Edit murid" (StudentEditor): nama, ID, kategori, status, tgl lahir, kursus buka/tampil.
  Ganti ID = students.change_id: pindahkan foto, progres, badge, portfolio & assignment,
  riwayat login (+ arsip), jadwal, kuis, sertifikat, recents; ditolak kalau ID sudah dipakai.
  Ganti kategori = students.set_program (kursus disesuaikan). Settings: 2 tombol.
  Apply Now = langsung berlaku tapi SEMENTARA (app_settings._session di memori, hilang saat
  app ditutup); Apply As Default = langsung berlaku + disimpan ke file (termasuk yang tadi
  sementara). app_settings.get/feature membaca file + lapisan sementara; saved() = file saja.
- Settings > nilai isian (bisa digulir, per grup, kolom Cari di atas menyaring grup/baris
  tanpa membuat ulang widget): elearning/dev_values.py VALUES = 70 nilai (login, carousel,
  beranda, video, mini player, badge, sertifikat, jadwal, analytics, search, file/upload,
  batas teks, admin) + grup "Tampilan UI" (16): config.UI_RADIUS_SCALE = pengali SEMUA sudut
  bulat lewat ui_icons._r di pill / pill_crop / round_mask (lingkaran & kapsul tetap bulat),
  radius per komponen, bayangan logo / pesan / teks ID (login_screen LOGO_SHADOW*, SHADOW_*),
  garis tepi kolom ID, warna pesan salah, gelap tombol sampul gallery. Bentuk baru: pakai
  I.pill / I.round_mask supaya ikut pengali. LIMITS = batas aman (min, maks); fps maks. 30. Disimpan di
  app_settings "values" (hanya yang beda dari bawaan), dipasang ke atribut modul lewat
  dev_values.apply_all() (App mulai + Apply). Format salah -> Apply batal + pesan. "Reset semua
  nilai ke bawaan". Nilai baru: tambah baris di VALUES; modulnya harus membaca atribut itu
  saat dipakai (bukan disalin saat import).

## Tampilan login (3 mode, diatur di jendela Dev)
- elearning/app_settings.py: data\app_settings.json (BUKAN data\settings.json, milik
  blender_launcher). login_mode: "carousel" (1 baris + video latar, bawaan), "rows3" (3 baris
  kartu di silinder yang sama, 30 portfolio, TANPA video latar), "video" (video latar saja,
  tanpa kartu). Switch lama login_carousel_rows3 dibaca sebagai "rows3". ui/settings_panel.py:
  (dihapus; pindah ke jendela Dev).
- Kartu carousel melengkung: tiap kartu dibagi irisan vertikal (SLICE_PX) di silinder.
- fps adaptif (kisi 2x FPS, DIVS) memakai waktu render worker DAN waktu tempel thread utama,
  dengan jeda (turun >= 0,5 dtk, naik setelah stabil 3 dtk). Ukur PC ini (HIGH_END, 4 thread):
  carousel 1080p 60 fps, 1440p 30; rows3 1080p 40, 1440p 20; video 1080p 60, 1440p ~58.
  Batas di layar besar = tempel PhotoImage di thread utama Tk (tidak bisa GPU).
