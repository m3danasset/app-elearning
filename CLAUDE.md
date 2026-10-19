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
   MODE RINGAN (config.lite()): otomatis di PC <= 4 thread (config.LOW_END_PC, mis. Ryzen 3
   2200G + Vega 8, kena AMD "driver timeout"; Dev > Performa preset Ryzen 3), atau fitur Dev
   "animations" dimatikan: latar = GAMBAR STATIS (VideoPlayer static dipaksa: satu frame,
   tanpa video berjalan; login: carousel diam menunggu frame itu lewat _wait_static_bg),
   carousel login diam tanpa kartu & tanpa thread (Carousel3D.static: pita digambar ulang
   hanya di configure), geser kartu Dashboard murid langsung, palette / file browser tanpa
   fade, notifikasi badge tanpa geser, layar penuh pelajaran tanpa fade, mpv hwdec=no +
   penskala bilinear, Chrome web murid --disable-gpu. Fitur baru beranimasi WAJIB cek C.lite().
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
   Tes di salinan data: mengganti C.DATA_DIR saja TIDAK cukup (STUDENTS_FILE, TEACHERS_FILE,
   SESSIONS_FILE, ... sudah dihitung saat import); ganti semua atribut config yang diawali
   DATA_DIR lama. Jalan dari sumber, data ada di data\ proyek (contoh), bukan dist\data.
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
- Notifikasi badge (BadgeToast) geser masuk SLIDE_MS 300 / keluar CLOSE_MS 260, JADWAL FRAME TETAP
  (frame k = t0 + k * UI_FRAME_MS) + timer Windows 1 ms selama geser (_set_timer); raise sekali.
  Diukur: 34,0 ms / frame (33-34,5), 9 frame masuk (dulu after(34) relatif = 48 ms, 21 fps).
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
  search_palette.py). Tampilan Details / Small thumbnails (bawaan thumbnails) + urutan A–Z /
  Date (terbaru dulu, folder tetap di atas), tombol di kanan atas; keduanya diingat selama app terbuka.
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

- Tombol kecepatan (sebelah kiri CC, tanpa submenu): klik = 1x -> 0.75x -> 0.5x -> 1x
  (lesson_view.SPEEDS, _PREF["speed"], mpv speed; oranye kalau bukan 1x). Berlaku di semua
  pelajaran selama app terbuka; intro selalu 1x; mini player ikut kecepatan ini (load). Pemutar
  cadangan OpenCV: tombol disembunyikan.
- Tombol CC TANPA submenu: teks tombol = bahasa yang tampil ("IND" / "ENG", warna kursus;
  lesson_view.SUB_SHORT), klik = bahasa berikutnya (_cycle_sub, urutan SUB_LANGS). Subtitle
  SELALU menyala kalau videonya punya (tidak ada "Off"); video tanpa subtitle = "CC" redup.
  Pilihan di _PREF["sub"] ("Indonesia" / "English", bawaan Indonesia) dipakai semua pelajaran +
  mini player; video yang tidak punya bahasa itu memakai yang ada tanpa mengubah pilihan.
  mpv: _sub_opts (dibaca sekali saat termuat) + sub_label().
- Emote SUPERKIDS (lesson_extras.EmoteBar, baris di bawah video): SEMUA emote tersembunyi;
  muncul memudar (FADE_MS 160, maks. 30 fps, berbasis waktu, STEPS 8 tingkat warna dicampur ke
  C.BG) saat kursor dalam NEAR 70 px dari baris emote, hilang lagi saat menjauh. Posisi kursor
  dibaca winfo_pointerxy tiap 90 ms (mpv menelan event mouse). Klik saat belum tampil diabaikan.
  Mode ringan: langsung muncul / hilang.

## Export Excel admin (fitur baru ikut)
- excel_export.SHEETS + Jadwal (daftar: hari, jam, guru, catatan, warna, murid) & Jadwal Sesi
  (seperti tampilan Sesi), Kehadiran Jadwal (per murid per jadwal yang sudah selesai; aturan
  sama dengan Analytics lewat analytics.occurrences), Badge Murid. Data Murid + label PB/IC/SK,
  tanggal lahir, umur, badge, upload assignment, jadwal. Portfolio + kolom Bagian
  (Portfolio / Assignment). Sheet baru otomatis tercentang di dialog (baris 2 export_sheets.txt).
- Pilihan "Sertifikat (permintaan + syarat)" (kunci "certificates") = 2 sheet: Sertifikat
  (permintaan dalam periode: diminta, status, selesai, ditandai oleh) & Syarat Sertifikat (per
  murid per kursus dibuka & tampil: video x/y, assignment, portfolio, badge kursus, syarat
  lengkap, Bisa diminta / Menunggu / Selesai; lewat certificates.requirements). Data Murid +
  kolom "Batas Chrome" (_chrome_text: sama dengan tombol guru, AI / bawaan (x mnt) / diblokir /
  tanpa batas) & "Sertifikat" (n diminta, n selesai). Pendaftar + kolom PC / laptop di rumah.


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
- Tab terakhir, kolom Cari, dan posisi gulir Settings diingat di data\dev_ui.json (setelah
  Apply / Reset, tutup-buka jendela, buka ulang app); di-reset kalau PC sudah reboot (waktu
  nyala PC = time.time() - GetTickCount64, beda > 120 dtk = reboot).
- TAMPILAN = SETTINGS CLAUDE, TANPA ANIMASI: jendela tanpa bilah judul bersudut bulat
  (_rounded_window: overrideredirect + -transparentcolor KEY, digeser lewat navigasi / kepala,
  _draggable), navigasi kiri (kolom Search, "Dev: Akun", "Settings: Tampilan, Fitur, 15 grup
  nilai" = NavItem ikon + pill terpilih), isi kanan = judul grup tebal + baris (judul +
  keterangan | kontrol) dipisah garis tipis, tombol x kanan atas, bilah bawah (status + tombol
  RoundButton). Kontrol: Seg (tombol segmen: mode login, filter jenis, urut), Swatches (lingkaran
  warna aksen, cincin = terpilih), widgets.Switch (fitur), RoundEntry (nilai). Baris Settings
  dibuat SEKALI; pindah halaman / cari = pack_forget (isian belum di-Apply tetap). Kolom cari:
  di Akun = saring akun (Enter = Masuk, panah = pilih); di Settings = hasil dari SEMUA halaman.
  Esc = kosongkan cari, Esc lagi = tutup. Popup PIN = kartu kecil gaya sama (DevPinDialog).
- ui/dev_panel.py: selalu di atas. Tab Login (cari akun,
  masuk tanpa PIN; App.dev_login keluar dulu tanpa konfirmasi) dan Settings: tampilan login,
  warna aksen (app_settings.ACCENTS, berlaku setelah app dibuka ulang: apply_theme di App),
  fitur on/off (app_settings.FEATURES: intro, badges, certificate, floating, mini_player,
  palette, fps60; cek dengan app_settings.feature). Fitur baru yang bisa dimatikan: tambahkan
  ke FEATURES + cek feature() di kodenya. Tab Setting di Panel Admin sudah dihapus.
- Tab Login: tabel di SATU kanvas, 4 kolom (Jenis | ID | Nama | PIN, Consolas; x dari lebar
  huruf "0"), filter jenis; urutan utama selalu admin, guru, trial, dewasa, SUPERKIDS, lalu
  Nama / ID. PIN tampil **** (titik), kursor di atas baris = PIN terlihat. Klik 2x sel = ubah
  di tempat (Entry di kanvas; Enter / pindah fokus = simpan, Esc = batal, salah = tetap
  terbuka + pesan): Jenis murid (menu Dewasa / SUPERKIDS), ID murid (change_id), Nama semua,
  PIN guru / admin. Trial tidak bisa diubah. Masuk = tombol / Enter (bukan klik 2x lagi).
  _student_changed: murid yang sedang login ikut diperbarui + rebuild_screen.
  "Edit murid" (StudentEditor): nama, ID, kategori, status, tgl lahir, kursus buka/tampil.
  "Edit PIN" (PinEditor) untuk guru & admin: guru lewat teachers.update_teacher; admin lewat
  admins.set_pin -> data\admin_pins.json (menimpa PIN di admins.ADMINS; check_admin memakai get_pin).
  "Edit akun" (AccountEditor) = nama + PIN guru / admin; nama admin di data\admin_names.json
  (admins.get_name / set_name), lalu App.dev_account_changed membangun ulang layar.
  "Hapus" (DeleteConfirm, fokus awal di Batal) semua akun kecuali trial: murid =
  students.delete_student, guru = teachers.delete_teacher, admin = admins.delete_admin
  (data\admins_deleted.json; admin terakhir ditolak; list_admins dipakai daftar Dev).
  App.dev_account_deleted: akun yang sedang dipakai -> keluar ke login; lainnya rebuild_screen.
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

## Panel Admin > "Agenda & Laporan" (dulu "Laporan Guru"), dua halaman
- task_sheet_view.AgendaPanel: "Agenda saya" = TaskSheet(teacher=admin, admin=admin,
  titles=AGENDA_TITLES: AGENDA HARIAN / MINGGUAN / BULANAN / SUDAH SELESAI; isi + CHECK sendiri,
  data atas nama ID admin) | "Laporan guru" = TaskSheet(admin=admin): pilih guru, hanya CHECK.
  Halaman terakhir diingat selama app terbuka. TaskSheet: editable = ada teacher (pemilik),
  can_check = ada admin. task_sheet.summary(None) TIDAK menghitung agenda admin (ID ADMIN...).
  Dashboard admin: kartu "AGENDA SAYA" (agenda harian / mingguan belum selesai).

## Laporan guru = SHEET tugas (pengganti formulir laporan lama)
- Bagian LAPORAN HARIAN (section "day", field "day" = tanggal) PALING ATAS, panah tanggal di
  kepalanya (_day_hits); bagian kosong = 2 baris (EMPTY_ROWS). Tanggal di kolom LAPORAN (kanan,
  redup / hijau): "harian dd/mm/yy · selesai ... · dicek ..." (done_at / check_at).
- elearning/task_sheet.py: data
eport_tasks.json, per guru per bulan, bagian MINGGU INI (week)
  / BULAN INI (month) / SUDAH SELESAI (otomatis: done=True, urut done_at). Kolom NO | tugas |
  DONE (guru) | LAPORAN (guru) | CHECK (admin, check_by). Tugas dikosongkan = dihapus.
  carry_over = bawa tugas belum selesai bulan lalu. reports.json lama tetap ada (export lama).
- ui/task_sheet_view.py TaskSheet (SATU canvas, bagian berwarna merah / hijau / biru seperti
  sheet studio, kotak centang antialias I.pill + check_bold; warna ikon WAJIB hex, "white"
  gagal diam-diam). Guru: klik sel = Entry di atas sel (Enter simpan, Tab / Shift+Tab pindah,
  Esc batal), baris "+ Ketik tugas baru". Admin (tab Laporan Guru): pilih guru + bulan, hanya
  CHECK. JANGAN pakai atribut self._w di widget Tk (nama path Tk). Dashboard: kartu guru
  "n tugas minggu ini belum selesai", admin "n tugas selesai belum dicek", widget "tugas
  selesai hari ini". Excel: sheet "Laporan Guru Sheet".

## Live Kelas (admin & guru) + widget progres murid
- elearning/presence.py: app murid (bukan trial) menulis data\presence\<ID>.json tiap PUSH_S 15
  dtk (App._presence_tick / _presence_info: layar, view, kursus, pelajaran, posisi video + diputar,
  Blender terbuka / di depan, Chrome, idle GetLastInputInfo, nama PC); logout / tutup = dihapus;
  > STALE_S 75 dtk = offline. activity(rec) -> (teks, jenis video | blender | browse | page | idle).
- Rekap harian (export): tiap status, App menambah detik sejak status sebelumnya (maks. 60) ke
  data\activity\<ID>.json per tanggal per jenis (video / blender / browse / page / idle) + per
  kursus (presence.add_activity). Excel pilihan "live": sheet "Aktivitas Kelas" (per murid per
  hari, menit) + "Live Saat Export" (murid online saat itu).
- ui/live_view.LiveBoard (menu "Live Kelas" tepat di bawah Dashboard, admin tab "live", guru view
  "live"): dibaca di thread tiap 5 dtk, SATU canvas: ringkasan, "Kelas berjalan" (jadwal sekarang,
  hadir x/y = online, nama belum login; guru hanya kelasnya), kartu murid (warna aktivitas, progres
  video, PC, lama tanpa input). Klik kartu = buka murid. JANGAN pakai self._w di widget Tk.
- Dashboard murid: widget progres di bawah kartu kursus (course_dock stats=student,
  student_stats.compute di thread): Videos watched x/y + bar, Badges, Your work (portfolio ·
  assignment), Study time this week + streak. Tampil hanya kalau ruangnya cukup; trial tidak.

## Panel Admin > Survey (pertanyaan bisa dibuat / diubah, English)
- elearning/survey_questions.py: data\survey_questions.json {"student": [...], "trial": [...]};
  pertanyaan {id, kind single | multi | text, text, options (2-8), required}. "student" = SEMUA
  pertanyaan survey murid (bawaan 5: level, interests, hardest, favorite, note); "trial" =
  PERTANYAAN TAMBAHAN setelah isian tetap signups.FIELDS (rec["extra"]). clean_answers (English),
  tally (hitung pilihan). ui/survey_form.QuestionForm dipakai popup murid & survey trial.
- ui/survey_admin.py SurveyBoard (menu "Survey" sidebar admin, ikon quiz): pilih survey, kartu
  pertanyaan (naik / turun / ubah / hapus), "Pertanyaan baru" (QuestionDialog: pertanyaan, jenis,
  8 kolom pilihan, wajib), "Kembalikan bawaan", Hasil (batang per pilihan + jawaban isian).
- student_survey: jawaban "answers" {qid: jawaban}; rekaman lama (level / interests berkode)
  diterjemahkan answers_of. Excel Survey Murid: kolom = pertanyaan sekarang.

## Insight = KARTU DASHBOARD ADMIN (bukan halaman Analytics lagi)
- analytics.insights(d): kesimpulan otomatis dari hasil compute {level bad | warn | good | info, icon,
  title, body, action, target}: tren jam belajar / upload, murid aktif yang tidak belajar, kehadiran +
  jadwal < 50 %, jam ramai, kursus terbanyak, konversi / sumber pendaftar, jawaban survey terbanyak,
  guru belum mengisi laporan, aktivitas Live Kelas (_activity_totals: % Blender / video / diam).
- dashboard._insights(): kartu tag "INSIGHT · 30 HARI" (compute("30d", "all"), cache 5 menit,
  maks. INSIGHT_MAX 6), level bad->urgent, warn->todo, good->done, info->info; tombol = menu
  terkait (INSIGHT_ACTION). Yang sudah jadi kartu Dashboard sendiri dilewati (INSIGHT_DUP). Bisa
  ditutup (x) seperti kartu lain. Insight baru: tambah di analytics.insights().

## Analytics admin = 16 kartu PAS SATU LAYAR (tanpa gulir saat layar penuh)
- 8 kartu angka (+ Survey murid, Tugas guru) lalu kisi 4 x 4 (>= 1000 px; 3 kolom >= 760, 2):
  jam belajar, upload, jam ramai, murid per kategori (donut PB / IC / SK, analytics._categories),
  pendaftar trial, pendaftar per minggu, tahu dari mana, rata-rata per hari (weekday), survey
  murid (donut pertanyaan pilihan ke-1 + batang ke-2), laporan guru (sheet tugas per guru,
  analytics._tasks), murid per kursus, perlu diperhatikan, paling rajin, kehadiran, badge.
  Tinggi kartu = (tinggi area gulir - bar - kartu angka) / baris (AnalyticsPanel._fit_height ->
  board.fit_h, ikut berubah saat ukuran ScrollFrame berubah); min. MIN_CARD_H 128 (lebih kecil =
  boleh gulir). Diukur: 1920x1080 & 1366x768 tanpa scrollbar. Kartu kecil: donut & angka mengecil.

## Survey murid setelah BASIC 2 (config.SURVEY_AFTER_COURSE)
- elearning/student_survey.py: due() = bukan trial, fitur Dev "student_survey", belum mengisi,
  belum Skip di sesi ini, SEMUA video kursus itu completed. Popup English (ui/student_survey_view
  StudentSurveyDialog) ~0,9 dtk setelah Dashboard murid tampil (App.show_home): tingkat
  kesulitan (Easy / Just right / Hard), minat lanjutan (Game, Animation, Advertising, Character,
  Interior; boleh banyak), bagian tersulit, paling disukai, catatan. "Maybe later" = tanya lagi
  sesi app berikutnya. data\student_surveys.json (ikut hapus / ganti ID murid). Admin: Analytics
  Ringkas baris "Survey murid" + Excel sheet "Survey Murid".
- Analytics admin HANYA Ringkas (mode Lengkap & tombol Tampilan dihapus).

## Preset performa (Dev > Pengaturan app > Performa)
- config.PERF_PRESETS: auto (deteksi: <= 4 thread = Ryzen 3, NVIDIA + >= 12 thread = Ryzen 5 +
  NVIDIA, lainnya Ryzen 5), ryzen3 (1 thread kerja + MODE RINGAN, 30 fps), ryzen5 (2 thread,
  efek menyala, 30 fps), ryzen5_nvidia (HIGH_END: carousel login 60 fps / 4 thread). Disimpan di
  datapp_settings.json "perf_preset", dibaca config saat mulai (_saved_perf -> apply_perf
  mengisi WORKER_THREADS / LOW_END_PC / HIGH_END / CAROUSEL_*). Klik di Dev = langsung disimpan +
  apply_perf + app.apply_dev_settings (carousel3d.reconfigure); bagian yang dibuat saat mulai
  ikut penuh setelah app dibuka ulang. JANGAN salin WORKER_THREADS / LOW_END_PC / HIGH_END ke
  konstanta modul saat import: baca C.xxx / C.lite() saat dipakai. Baris lama "PC kuat" di
  Fitur dihapus (ada di Performa: deteksi + ringkasan "Yang dipakai sekarang").

## Label jendela Dev (jelas, tidak ambigu)
- Navigasi: "Kelola" (Akun, Kursus) & "Pengaturan app". Tombol Settings: "Coba sekarang"
  (= Apply Now, sementara sampai app ditutup), "Simpan permanen" (= Apply As Default),
  "Nilai ke bawaan". Akun: "Masuk ke akun", "Edit murid / guru / admin", "Nonaktifkan /
  Aktifkan", "Hapus akun", "Akun baru"; status murid tampil Aktif / Nonaktif. Kursus:
  "Urungkan akses". Dialog: label kiri + KETERANGAN kecil di bawahnya (Card.label(grid, r,
  text, hint)), mis. "Masuk sebagai akun ini" = setelah dibuat Dev langsung login ke akun
  baru. Label / tombol Dev baru wajib jelas begini (Bahasa Indonesia, tanpa istilah Inggris).

## Dev > Akun (lengkap)
- Tabel 6 kolom: Jenis | ID | Nama | Status (murid Active / Expired merah) | Login terakhir
  (sessions.overview, dimuat sekali per reload_accounts, _load_last) | PIN. Kepala: jumlah per
  jenis. Bilah bawah: Akun baru (Ctrl+N), Hapus, Nonaktifkan / Aktifkan (murid, set_status;
  klik 2x sel Status juga), Edit, Masuk. Kolom = _xs() dict + _col_end; sel = _cell(it, col).
- ui/dev_accounts.py: Card (kartu bersudut bulat, TINGGI MENGIKUTI ISI lewat fit(), posisi tetap
  setelah tampil), NewAccount (Seg murid dewasa / SUPERKIDS / guru / admin; nama, ID otomatis
  (murid bisa diubah), PIN + "Acak" (random_pin = os.urandom, tanpa modul random), tanggal lahir
  dicek SEBELUM akun dibuat, Chips kursus dibuka, "Langsung masuk" -> panel.account_created),
  StudentEditor (Seg kategori & status, Switch Tampil / Buka per kursus -> bulk_access),
  AccountEditor (nama + PIN + Acak), DeleteConfirm (fokus Batal). Dialog lama di dev_panel dihapus.
- admins.py: admin BARU dari Dev di data\admins_extra.json {ID: {name, pin}} (add_admin,
  next_admin_id: ID yang pernah dihapus tidak dipakai ulang). _all() = ADMINS + extra dipakai
  get_name / set_name / get_pin / set_pin / list_admins / delete_admin / check_admin.

## Dev > Kursus: panel kursus + master toggle akses murid
- courses.py: daftar di kode = BAWAAN (BUILTIN). Dev membuat / mengubah / menghapus / mengurutkan
  -> SELURUH daftar disimpan di data\courses.json ({"v": 1, "courses": [...]}) dan dipakai
  menggantikan bawaan; COURSES diubah DI TEMPAT (list yang sama, semua importir ikut baru).
  JANGAN salin COURSES ke dict modul saat import: pakai courses.by_id / title_of / order_of
  (students memakai order_of untuk urutan "courses" / "hidden"). add_course (di akhir program,
  folder assets\lessons\<id> dibuat), update_course (ID & program tetap), delete_course,
  move_course, removed_builtins / restore_builtin. Hapus kursus TIDAK menghapus data murid
  (progres, badge, portfolio, video, id di students.json): buat lagi ID yang sama = kembali.
- ui/dev_courses.py CoursesPage (nav "Kursus" di bawah Akun; Seg Dewasa / SUPERKIDS / Trial):
  daftar panel kursus (titik warna, id · grup · jumlah video · n buka / n sembunyi; panah urut,
  pena = CourseEditor, sampah = CourseDelete fokus Batal), "Kursus bawaan yang dihapus" +
  Pulihkan. Tabel Akses murid di SATU kanvas: baris murid (disaring kolom Search Dev), kolom
  "Semua kursus" (ALL_W 76) + tiap kursus (judul 2 baris _wrap2); tiap sel MATA (tampil,
  "hidden") + GEMBOK (terbuka, "courses"). Kepala kolom = master kursus itu untuk semua murid
  yang tampil; kolom Semua kursus = semua kursus murid itu; kepalanya = semuanya. Semua
  tercentang -> dimatikan, selain itu -> dinyalakan. students.bulk_access = SATU kali tulis;
  "Urungkan" bertingkat (maks. 30). Murid yang sedang login ikut diperbarui (_refresh_app,
  500 ms; layar kursus yang dihapus / dikunci -> Dashboard). CourseEditor: program (baru saja),
  judul, ID otomatis dari judul (slug), grup, deskripsi ID / EN, warna (courses.COLORS), video,
  "Buka untuk semua" (baru). Trial: kursus selalu terbuka untuk semua akun trial.

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

## Survey trial -> pendaftar -> murid
- elearning/signups.py: data\trial_signups.json (S0001, ...; pending / approved / rejected).
  FIELDS = (kunci, label English, label admin, wajib, lebar penuh): nama*, telepon/WA*, umur*,
  email, sekolah, minat kelas, nama & telepon orang tua, alamat, tahu dari mana, catatan.
  clean() memeriksa (pesan English). Isian PILIHAN (signups.CHOICES, tombol segmen sekali
  klik, klik lagi = batal): "computer" = "Do you have a PC or laptop at home?" -> pc / laptop /
  none (3 tombol; label admin & Excel lewat signups.display: PC, Laptop, Tidak punya).
- ui/signup_view.py SurveyDialog: popup English saat akun TRIAL keluar / menutup app
  (App._after_trial dipanggil dari logout() & _close(), BUKAN dari _logout yang dipakai Dev).
  Sekali per sesi trial (_survey_done), Submit / Skip -> lanjut keluar. Fitur "survey" di Dev.
- Panel Admin tab "Pendaftar" (SignupBoard, angka menunggu di menu): Detail, Tolak, Setujui
  (ApproveDialog: nama, kategori -- saran SUPERKIDS kalau umur <= 12 --, ID otomatis,
  switch kursus yang dibuka; add_student + set_course_access + signups.approve). Ditolak:
  Buka lagi / Hapus. Export Excel: sheet "Pendaftar".
- Analytics (Lengkap & Ringkas) bagian "Pendaftar dari trial" gaya dashboard: kartu angka
  (konversi + progress bar, pendaftar baru + sparkline, menunggu, rata-rata umur), grafik
  area 2 seri (pendaftar vs jadi murid; per minggu kalau periode > 14 hari), donut "Tahu dari
  mana" (analytics.SOURCES: kata kunci isian bebas), tabel kelompok umur + dinamika, batang
  minat kelas (INTERESTS), tabel menunggu persetujuan. analytics.signup_stats (di thread).
- ui/chart_art.py: area melengkung (Hermite monoton, gradasi) & donut, numpy float32, anti-
  alias, TANPA ImageDraw; cache PhotoImage di AnalyticsBoard._art (area 700x230 ~12 ms sekali).
- Seluruh halaman Analytics bergaya dashboard: kartu angka Lengkap ada progress bar (murid
  aktif, kehadiran) atau sparkline (jam belajar, portfolio, assignment, badge); Jam belajar =
  grafik area (lengkap & ringkas). Urutan Lengkap: kartu, Jam belajar, "Pendaftar dari trial",
  lalu judul "Aktivitas kelas" (jam ramai, upload, kehadiran, badge, kursus, guru, murid).

## Dashboard admin & guru (halaman pertama setelah login)
- elearning/dashboard.py items(role, user): kartu notifikasi / tugas {level urgent | todo |
  info | done, icon, tag, title, body, when, action, target}. Admin: pendaftar menunggu,
  sertifikat, kelas hari ini (berjalan / berikutnya), murid tanpa jadwal, tidak login >= 14
  hari, laporan guru hari ini, akun expired, sedang online. Guru: kelas saya, laporan kerja
  hari ini, sertifikat, karya baru murid (3 hari), murid tidak aktif, online. Dihitung di
  thread, diperbarui tiap 60 dtk; target = menu yang dibuka (admin _set_tab, guru _set_view).
- ui/dashboard_view.py DashboardView: satu canvas, video latar beranda (assets\video\home)
  seperti halaman murid; kartu (bayangan lembut, cahaya warna tingkat dari kiri, ikon bulat,
  tombol aksi, titik oranye untuk urgent) digambar ke SATU lapisan RGBA yang dicampur ke frame
  video DI THREAD video (frame bertanda id lapisan). Hover = bingkai warna terpisah (0,1 ms),
  lapisan tidak digambar ulang. Kanan atas: cincin "x/y beres". 3 kolom >= 1180 px, 2 kolom
  >= 720. Admin: menu "Dashboard" paling atas (tab default); guru: view "dashboard" default.
- Layout (mockup): 3 widget di tengah atas (jam + kelas berikutnya, cincin "x/y beres",
  jumlah online; dashboard.info), sapaan besar di tengah, kartu di bawah. Layar tinggi:
  ruang atas melebar (shift). Widget + sapaan TERKUNCI; hanya area kartu yang digulir (roda mouse,
  per piksel, tanpa scrollbar). Kartu di lapisan sendiri, alpha x _fade_mask: terpotong
  lembut di bawah sapaan (FADE_TOP) dan memudar di bawah layar (FADE_BOTTOM); teks kartu
  (tag "ct") warnanya dicampur ke latar sesuai posisi.
- Admin & guru TANPA kolom cari bawah: kolom cari sidebar membuka search palette (palette=True,
  seperti murid). Guru: "Tambah murid" tidak di sidebar lagi -> tombol di kepala halaman
  Murid & Kursus + aksi Ctrl+K.
- Widget atas diatur per akun di 12 SLOT (6 x 2; data\dashboard_widgets.json = 12 id/null,
  format lama daftar id diisi berurutan). Katalog dashboard.WIDGETS (jam, progres beres,
  online, kalender, pendaftar, sertifikat, kelas hari ini, murid aktif, tidak aktif, tanpa
  jadwal, laporan hari ini, karya baru). Biasa: widget per baris slot dirapatkan & di tengah,
  hanya ikon PENA (ui_icons "pen") di kanan atas. Klik pena = mode atur (ikon jadi centang +
  "Selesai"): grid 6 x 2 dengan slot kosong (+, klik = menu pilihan), baki "Widget
  tersembunyi" (chip) menggantikan sapaan; SERET chip ke slot, seret widget antar slot (tukar),
  seret ke baki / klik x = sembunyikan. Klik widget (mode biasa) = buka menu terkait. Angka
  widget dihitung di thread (dashboard.info); muat ulang diantre (_again).
- Laci kartu (drawer): KECIL (bawaan) = sapaan besar (40 pt) di tengah antara widget & laci,
  hanya baris kartu pertama (3 kartu / sesuai kolom) di paling bawah, tanpa pudar. Tombol
  panah minimalis (ui_icons chev_up / chev_down) di atas kartu: "x dari n · Tampilkan semua"
  / "Kecilkan". PENUH = laci naik tepat di bawah widget, menutupi sapaan, bisa digulir +
  pudar bawah. Roda mouse: ke bawah di laci kecil = buka; ke atas di laci penuh (posisi
  paling atas) = kecilkan. Mode atur widget memakai susunan lama (baki, kartu di bawahnya).
- Laci BERANIMASI (DRAWER_MS 420 ease-out; gulir SCROLL_MS 200, roda berturut = tujuan diganti).
  MODE PITA (_prep_strip): kartu digambar SEKALI ke pita RGBA (item "strip") + teks "ct", latar =
  lapisan TANPA kartu (_no_cards). Laci PENUH selalu mode pita -> gulir hanya canvas.move (roda
  < 1 ms, tanpa persiapan / gambar ulang); kartu terpotong TEGAS di bawah tombol laci (penutup
  atas padat = potongan latar RGB) + pudar di bawah layar (_edge_covers). Laci KECIL: kartu baris
  ke-2 mengintip PEEK 64 px, samar PEEK_ALPHA 0,5 -> 0 di tepi bawah; klik intipan = buka laci.
  Jadwal frame tetap dari jam mulai (UI_FRAME_MS). Sapaan memudar saat laci naik / muncul saat
  turun. Ukuran berubah / data dimuat -> _stop_anim + _layout. Mode ringan: langsung, tanpa pita.
  SAPAAN TETAP TERLIHAT & UKURAN SAMA (HERO_PT = HERO_OPEN_PT = 40, permintaan pemilik): laci
  penuh = sapaan hanya NAIK tepat di bawah widget, laci di bawahnya (_greet_pos / _drawer_y);
  bergerak bersama laci
  (ease-in-out DRAWER_MS 520). JANGAN pudarkan teks ke C.BG (di atas video latar jadi hitam).
  Ukuran huruf per frame = Font yang SUDAH dibuat (_hero_fonts 24..40); Font.configure(size)
  tiap frame ~20 ms = patah-patah. Selama animasi timer Windows 1 ms (_set_timer, timeBeginPeriod)
  supaya after() tidak dibulatkan ke 15,6 ms (31/47 ms). Ukur 2000x1210 & 2560x1400: laci & gulir
  33-35 ms / frame (maks. 35). Error callback Tk dicatat ke app.log (App._tk_error).
- JENDELA PENDEK (windowed): _fit_greeting memastikan sapaan tidak menimpa tombol laci / kartu:
  40 pt + intipan baris 2 -> 40 pt tanpa intipan (_peek_on) -> huruf turun sampai HERO_MIN_PT
  24 (_hero_fonts) -> sapaan disembunyikan (_hero_pt None). Ukuran yang sama di laci penuh.
- WINDOWED VERTIKAL / SEMPIT (kanvas < NARROW_W 900): widget menyusun ulang mengikuti lebar
  (urutan slot tetap; min. WIDGET_MIN_FIT 115 px -> 6 / 5 / 3 / 2 per baris, _widget_rows);
  jendela sempit DAN pendek -> widget ringkas WIDGET_H_COMPACT 72 (tanpa baris ke-3, _sub_y);
  laci kecil tidak pernah naik melewati widget (_drawer_y); sapaan juga dibatasi LEBAR (nama
  panjang -> huruf turun); "x dari n" disembunyikan & tautan kembalikan pindah ke kiri; mode atur
  6 / 4 / 3 / 2 kolom slot. Diperiksa numerik 35 ukuran x laci kecil/penuh (590-2000 x 600-1386):
  widget < sapaan < tombol laci < kartu, semua di dalam lebar.
- Penutup atas laci penuh dipotong SHADOW_ROOM 24 px di atas kartu baris 1 (bayangan kartu
  menjorok 22 px); dipotong tepat di atas kartu = bayangan terpotong = garis di latar. Frame
  latar baru di mode pita -> penutup dibuat ulang dari frame yang sama (_video_tick).
- Tombol PENA widget tersembunyi; muncul saat kursor dalam PEN_NEAR 140 px (_pen_near; mode
  atur: selalu terlihat).
- RESIZE WINDOWED (jendela diseret): DashboardView & CourseDock TIDAK menyusun ulang tiap event
  (~60 ms per event = sangat lambat); ukuran baru disimpan (_pending) dan diterapkan SEKALI
  RESIZE_SETTLE_MS 100 setelah berhenti (_resized). Selama itu tirai gelap App (ResizeCurtain,
  sekarang juga untuk perubahan TINGGI) menutupi; tirai diangkat setelah susunan baru selesai.
  Ukur 20 langkah seret: 5,6 ms / langkah (dulu 61 ms).
- Kartu bisa DITUTUP: tombol x (CLOSE_D 24, ui_icons "close") di pojok kanan atas hanya saat
  kartu disorot (_show_close; kartu terpotong / pudar = tanpa x). Klik x = dashboard.dismiss ->
  data\dashboard_dismissed.json {akun: {key: {sig = judul + isi, t}}}: tersembunyi selama isinya
  sama, isi berubah = muncul lagi; catatan > 30 hari dibuang. Disaring di thread (D.visible).
  Tautan "n kartu ditutup · kembalikan" di kanan baris tombol laci (D.restore_all).
- Kartu PRIORITAS (urgent): gradasi oranye lebar (URGENT_GLOW #ff8a1a, kekuatan 0,46) + garis
  tepi oranye (_tint / _paint_card).
- Halaman utama murid (course_dock): kartu kursus 1:1 dengan cahaya gradasi warna kursus dari kiri-atas
  (_tint, sama gaya kartu Dashboard); terkunci = gradasi samar; hover sedikit lebih terang.
- Halaman utama murid & trial = "Dashboard" (menu sidebar ikon home, juga di layar kursus &
  Ctrl+K), gaya Dashboard admin / guru: CourseDock(hero=True) = sapaan besar 40 pt ("Good
  morning, <nama depan>"; trial "Welcome!") + tanggal, kartu kursus di bawahnya (cy 0,60).
- LATAR STATIS (config.STATIC_BG = True, STATIC_BG_AT 0.4): latar login, Dashboard murid /
  admin / guru = SATU frame dari video latar (tidak bergerak). video_background.VideoPlayer
  static: baca satu frame, disiapkan ulang hanya saat ukuran berubah (pemanggil tetap memakai
  get_latest, tidak berubah). Teaser memakai static=False. Mode ringan tetap tanpa latar video.
- BAYANGAN SATU SPESIFIKASI untuk SEMUA dashboard (admin, guru, murid, trial): dashboard_view
  SH_BLUR 12, SH_DY 6, SH_ALPHA 90, TEXT_SH_ALPHA (85, 60) + text_shadow(canvas, item, ...).
  Dipakai kartu notifikasi, widget, widget USB, kartu kursus, teaser, dan sapaan (admin / guru
  sekarang juga; bayangan sapaan ikut bergerak bersama laci, _greet_sh). course_dock MENGIMPOR
  nilai ini (jangan buat angka sendiri). Bayangan bentuk baru: _shadow(w, h, r) tanpa blur/alpha.
- Bayangan lembut seperti widget USB (dashboard_view._shadow; SH_BLUR 12, SH_DY 6, SH_ALPHA 90)
  di bawah kartu kursus (dicampur ke pita kartu; pita diperpanjang untuk ruang bayangan) dan di
  bawah sapaan + baris tanggal (kapsul ter-blur seukuran teks, CourseDock._text_shadows).
- VIDEO TEASER kursus (CourseDock teaser=True dari home_screen, fitur Dev "teaser"): kursor diam
  TEASER_SHOW_MS 220 di atas kartu kursus (terbuka / terkunci) -> kartu video 16:9 BESAR
  (TEASER_W 840, maks. 720p; mengecil kalau ruang kurang, hilang kalau < 220) muncul memudar +
  naik 14 px di TENGAH ruang di atas sapaan (sapaan & kartu kursus TETAP di posisi biasa, cy 0.60;
  bayangan lembut seperti widget USB: blur 12, turun 6, kepekatan 90); pindah
  kartu = video berganti (ditukar saat frame pertamanya siap, tanpa kedip); keluar kartu / kanvas
  = memudar hilang (TEASER_HIDE_MS 260). Video: assets\video\teaser\<id kursus atau judul>.mp4,
  kalau tidak ada -> teaser*.mp4 (SAMPEL 8 dtk 1280x720 24 fps: kubus 3D berputar, alat sekali
  pakai OpenCV + PIL, bukan kode app). Tanpa suara, diulang.
- Teaser MULUS 30 fps (diukur: jarak frame 33-35 ms saat muncul): (1) video dibuka di thread
  SEBELUM tampil (saat kursor menyentuh kartu), pudar mulai setelah frame pertama siap; (2) pudar
  dihitung di thread utama tiap frame UI (jadwal tetap, ease-in-out kubik _ease), bukan per frame
  video; (3) kartu = SATU gambar RGB solid (potongan latar + bayangan + video bersudut bulat,
  lapisan bawah di-cache) -> Tk menempel RGB ~0,5 ms, sedangkan gambar bertransparansi sebesar
  ini ~7 ms; (4) selama teaser tampil / widget USB bergeser, video LATAR beranda tidak diganti
  (mengganti gambar latar layar penuh ~20 ms di thread utama, 12x/dtk = penyebab patah-patah).
  ui/teaser.py: TeaserPlayer (VideoPlayer) -> frame RGB <= 720p + .mask sudut bulat.
- Widget USB: gambar RGBA TRANSPARAN (tidak menyalin latar, di-cache per keadaan), jadi geser =
  pindah koordinat (+ move teks "usbw"), tidak disusun ulang tiap frame. Bergeser ke KANAN
  teaser (TEASER_GAP 30, SLIDE_MS 340 ease-in-out) selama teaser tampil, lalu kembali ke tengah.
  update.bat menyalin assets\video\teaser dengan /D (file teaser yang diganti di dist dan lebih
  baru tidak ditimpa). BACA-SAYA.txt di folder itu.
- Widget USB (course_dock, usb=True; murid SK / PB / IC, bukan trial, bukan murid AI =
  courses.ai_only): SATU widget tetap (tidak bisa diatur) gaya widget Dashboard, di tengah ruang
  atas sapaan. HANYA tampil kalau ada USB tercolok (tanpa USB = tidak ada widget) dan ruang
  cukup. "USB plugged in" hijau + nama (E:) + sisa ruang, atau "2 USB plugged in".
  Tombol eject bulat di kanan (ui_icons "eject"): usb_save.eject = kunci volume, flush,
  dismount, IOCTL_STORAGE_EJECT_MEDIA (ctypes, di thread); berhasil -> widget langsung hilang;
  gagal (file terbuka) -> pesan oranye 6 dtk. Drive tanpa media (sudah eject / card reader
  kosong) tidak dihitung; baca ulang tiap 5 dtk (SetErrorMode: tanpa popup "insert disk").
  Pemantau bersama usb_save.monitor(widget) (UsbMonitor, satu per jendela, berhenti kalau tak
  ada pendengar): drive_mask tiap 1 dtk di thread utama; berubah / tiap 5 dtk ->
  removable_drives + drive_info di thread (hasil diambil tiap 100 ms selama berjalan);
  subscribe(fn) -> fungsi berhenti; eject_async + drop (yang dikeluarkan langsung hilang).
  Gambar widget = potongan latar (ikut frame video), ~2,5 ms.
- Menu USB sidebar Dashboard murid (aturan sama dengan widget): satu menu per flashdisk,
  label = nama volume "KINGSTON (E:)" (ikon usb), muncul / hilang otomatis. Halaman
  file_browser.UsbPage: nama, sisa ruang, "Open files" (FileBrowser mode resource, root = akar
  flashdisk: tidak bisa naik / junction keluar; dibuka otomatis), "Eject". File program
  (RUN_EXTS: .exe, .bat, .lnk, ...) tidak dibuka. Dicabut / dikeluarkan -> kembali ke Dashboard
  + file browser ditutup.
  Hapus (USB saja, FileBrowser on_delete): centang file / item terpilih (file atau folder) ->
  tombol "Delete n" merah di footer atau tombol Del -> file browser ditutup, popup MiniConfirm
  (App._confirm, sama dengan Log out: Cancel fokus awal, Delete merah) -> hapus di thread
  (cek tetap di dalam akar USB, akar tidak bisa dihapus) -> file browser dibuka lagi di folder
  yang sama (opts start) + status "Deleted n item(s)". Batal -> langsung dibuka lagi.

## Mini player (mode mengambang saat Blender)
- ui/mini_player.py MINIMALIS: jendela = video 16:9 saja (sudut membulat RADIUS 12: Windows 11
  DwmSetWindowAttribute(33, ROUND) antialias, cadangan SetWindowRgn). Kursor di atas: bilah
  judul (atas) & bar kontrol (bawah) MENUMPUK di atas video (place + lift, ukuran jendela tetap);
  kursor keluar -> hilang setelah HIDE_MS 700 ms (tidak saat seek diseret). Dicek di _tick 40 ms.
  Xvfb tidak merender jendela ini (topmost); cek lewat place_info.
- PENTING (Tk di Windows): "wm geometry" baru diterapkan saat idle; perubahan urutan jendela
  (-topmost / lift) SEBELUM itu membuat Tk mengambil lagi posisi lama. Dulu ikon mengambang &
  mini player memanggil topmost + lift tiap tick 250 ms -> saat Blender di-maximize / digeser
  ikon tertinggal di posisi lama dan mini player meloncat-loncat ("kadang tidak di sebelah
  ikon"). Sekarang: FloatingIcon._place / MiniPlayer._apply_geometry = geometry +
  update_idletasks (langsung diterapkan); show() hanya mengatur topmost / lift saat baru
  muncul. Jendela baru apa pun: topmost SEBELUM geometry (tooltip sidebar _Tip dulu kadang di
  pojok kiri-atas layar). _sync_from_app memakai _position(info) (ikon masih tersembunyi).
- Uji mode mengambang tanpa Blender: jendela palsu kelas "GHOST_WindowClass" (ctypes
  RegisterClassW + CreateWindowExW) di luar layar; posisi ikon & mini player dibaca dengan
  GetWindowRect (bukan winfo) di tiap skenario (Blender digeser / diperkecil / minimize /
  kembali dari aplikasi / ikon diseret / ukuran mini).
- Mini player: mpv "focus-on=never" (mpv lama: focus-on-open=no) supaya video tidak merebut
  fokus keyboard Blender.

## Jendela web murid: Pinterest (PB / IC / SK), Gemini + Flow (murid AI); bukan trial
- elearning/web_launcher.py + config.WEB_SITES (key, title, icon, url, allowed, ai). Ikon di
  sebelah "Buka Blender" (sidebar footer extra = daftar): web_pin / web_gemini / web_flow.
  Murid AI = membuka kursus grup config.WEB_AI_GROUPS; murid campuran dapat semua.
- Google Chrome --app (bukan Edge, bukan browser tertanam: login Google diizinkan). SATU
  profil + satu proses Chrome per murid (%LOCALAPPDATA%\M3DAN\browser\<ID>); tiap situs =
  jendela sendiri (klik lagi = tampilkan jendela itu). Unduhan ke Z:\, tanpa simpan sandi.
- Hanya host situs milik murid + config.WEB_LOGIN_HOSTS (--host-resolver-rules, dipasang saat
  proses pertama; tidak berlaku kalau PC pakai proxy). *.google.com selalu terbuka (login).
- Hanya terlihat di aplikasi: jendela Chrome dijadikan milik jendela aplikasi (GWL_HWNDPARENT,
  tanpa taskbar), ditahan di area aplikasi, disembunyikan saat aplikasi mengecil / Blender,
  ditutup saat logout / tutup aplikasi. Pengawas after() 300 ms di thread utama.
- Batas harian per murid (Pinterest: config.PINTEREST_LIMIT_MIN = 10, diatur di Dev > Nilai grup
  "Web murid", 0 = tanpa batas; situs lain: WEB_DAILY_LIMIT_MIN). SISTEM MENIT (seperti batas chat Claude):
  jatah dipakai sampai habis, lalu jeda config.WEB_RESET_MIN (10 menit, Dev), lalu jatah penuh
  lagi (data\web_usage.json v3: {start, secs, hit, warned}; catatan > 1 hari dibuang). Dihitung
  di _watch hanya saat jendela situs terbuka & terlihat (aplikasi mengecil / Blender = jeda).
  Sisa 2 menit -> pesan sekali; habis -> jendela ditutup (WM_CLOSE) + "resets at HH:MM";
  tooltip ikon "Pinterest · 8 min left" / "Limit reached · resets 15:30" (status_text).
  Guru (detail murid, tombol "Pinterest: bawaan / 20 mnt / diblokir / tanpa batas", hanya murid
  yang punya akses Pinterest): PinterestLimitDialog (WheelPicker: Bawaan, Diblokir, 5-120 menit,
  Tanpa batas) -> students.json "pinterest_limit" (None bawaan, 0 blokir, -1 tanpa batas;
  students.set_pinterest_limit, _valid menyimpan). Didahulukan dari bawaan Dev; dibaca launcher
  maks. 1x / 5 dtk (_own_limit), langsung berlaku.
  Belum diuji di Windows asli.
- Situs web murid di sidebar = baris sendiri DI ATAS "Open Blender" (sidebar.blender_footer):
  Pinterest pakai logo asli (elearning\ui\img\pinterest.png, bulat transparan, _site_logo),
  Gemini / Flow ikon garis; kanan = sisa jatah. web_launcher: hanya SATU jendela per situs;
  jendela yang dibuka dari dalam situs (tautan / tab baru) ditutup (_close_extra: judul berisi
  nama situs = langsung, lainnya setelah 4 dtk); popup login Google (judul "Google"/"Sign in")
  dibiarkan.
- Dashboard: ukuran berubah (sidebar dilipat / dibuka) -> frame video terakhir direntang ke
  ukuran baru (bukan latar polos), jadi latar tidak berkedip.
- Login Google di jendela web: WEB_LOGIN_HOSTS juga accounts.google.* (cookie domain negara, mis. .co.id) &
  accounts.youtube.com. _close_extra tidak pernah menutup jendela tanpa judul / masih memuat.
  Aturan host hanya berlaku saat Chrome murid diluncurkan pertama (tutup Chrome profil M3DAN\browser dulu).
  FedCM ("Continue with Google") butuh domain google.com TANPA subdomain (*.google.com tidak mencakupnya)
  -> WEB_LOGIN_HOSTS berisi "google.com". Diuji headless dengan flag aplikasi: popup Sign in muncul.
- PROFIL CHROME MILIK MURID (pengganti akun studio / kartu guru, yang sudah DIHAPUS bersama
  tombol login studio di Dev & Ctrl+K): baris "Chrome" di sidebar murid (logo Chrome ASLI dari
  PC, web_launcher.chrome_logo) -> ui/chrome_profiles.py, overlay "Who's using Chrome?" English
  yang MENIRU pemilih profil Chrome asli (latar #1f1f1f + cahaya warna tepi, kartu #3c4043 r=8,
  fokus biru #a8c7fa, tombol "Close" berbingkai). Kartu = profil murid
  (web_launcher.chrome_profiles: nama & email akun dari Local State info_cache / Preferences
  account_info / gaia_cookie, foto "Google Profile Picture.png" kalau ada, selain itu huruf di
  lingkaran warna; belum login = ikon orang + "Not signed in"). Kartu "Add" putus-putus (plus
  gelap di lingkaran abu, seperti Chrome) = add_profile: folder "Profile N" baru + Chrome di
  halaman login Google (SIGNIN_URL, versi "masuk ke Chrome"); maks. config.WEB_MAX_PROFILES (4),
  kartu Add hilang kalau penuh. Titik tiga (atau Delete setelah panah) = dialog "Delete this
  profile?" di dalam panel (fokus awal Cancel, bingkai fokus hanya lewat keyboard, Esc / klik
  luar = batal) -> delete_profile: Chrome murid ditutup, entri dihapus dari m3dan_profiles.json &
  Local State (os_crypt tetap), folder dihapus di thread (coba ulang 5x). SEMUA murid bebas
  login akun Google sendiri; akun murid lain tidak terlihat (folder data Chrome per ID).
- Folder: %LOCALAPPDATA%\M3DAN\browser\<ID> = SATU --user-data-dir per murid, profil di dalamnya
  (Default, Profile 1, ...; daftar urut di m3dan_profiles.json; pertama kali "Default" yang sudah
  login akun Google ikut tampil). Folder lama %LOCALAPPDATA%\M3DAN\browser\studio tidak
  dipakai lagi (tidak dihapus otomatis).
- CHROME BIASA (SEMUA murid bukan trial, config.WEB_SITES "pinterest" ai=None): kartu profil
  membuka web_launcher.open_browser(widget, student, pdir, url=None) = Google Chrome BIASA (tab,
  kolom alamat, SEMUA situs, --profile-directory). SATU proses Chrome per murid (peluncuran
  berikutnya diteruskan ke proses yang jalan: profil lain = jendela baru, url = tab baru); ganti
  murid / logout -> ditutup. Profil terakhir dicatat di m3dan_profiles.json "last".
- Gemini / Flow (murid AI) = TAB di Chrome biasa (bukan jendela --app lagi; mesin jendela situs,
  WEB_LOGIN_HOSTS / "allowed" / WEB_DAILY_LIMIT_MIN dihapus): open_web -> profil terakhir
  (last_profile) + url; belum punya profil -> popup profil dengan url, lalu kartu profil /
  "Add" (add_profile then_url = continue setelah login Google) membuka situsnya.
- WAKTU BROWSING (_count_browser, kunci data tetap "pinterest" supaya batas guru / Dev lama
  berlaku) dihitung selama ada jendela Chrome murid yang tidak di-minimize. MURID AI (punya
  kursus grup WEB_AI_GROUPS; is_ai_student, dibaca maks. 1x / 5 dtk lewat _own_info): TANPA
  BATAS (tanpa cincin; popup "Browsing · No limit"; tombol guru "Chrome: tanpa batas (AI)",
  klik = pesan, bukan dialog). Sisa 2 mnt = peringatan; habis = semua jendela Chrome murid
  WM_CLOSE (rapi), yang menolak (mis. "Leave site?") dipaksa setelah CLOSE_GRACE_S 5 dtk.
  Batas habis / diblokir guru: open_chrome_profiles TIDAK membuka popup (pesan jam reset);
  open_browser & add_profile juga menolak (_browse_blocked).
- SUPERKIDS (config.WEB_SAFE_PROGRAMS, fitur Dev "safesearch"): --host-resolver-rules
  _safe_rules() = pencarian aman (config.WEB_SAFE_MAP: www.google.com -> forcesafesearch.google.com,
  YouTube restrictmoderate, strict.bing, safe.duckduckgo; google.com tanpa subdomain TIDAK
  dipetakan supaya FedCM aman) + --test-type = TANPA bilah "You are using an unsupported
  command-line flag" (diuji lewat UI Automation: tanpa --test-type bilah ada, dengan --test-type
  tidak); situs lain tetap bebas; popup menulis "SafeSearch is on.". Profil sudah terbuka ->
  jendela Chrome dibawa ke depan (_front). Label: guru "Chrome: 20 mnt", dialog "Batas
  browsing Chrome", cincin "x% of browsing limit". SafeSearch belum bisa dibuktikan headless
  (captcha Google); cek manual di PC studio.
- Murid AI (kursus grup WEB_AI_GROUPS): Gemini / Flow BUKAN baris sendiri, tapi flyout di
  samping baris Chrome saat kursor di atasnya (sidebar._Flyout lewat sb.footer(flyout=...)):
  kartu bulat C.CARD + garis C.BORDER (sudut tembus -transparentcolor), baris 40 px disorot
  pill, logo 32 px + nama; muncul 120 ms, hilang 280 ms setelah kursor keluar dari baris +
  kartu (dicek tiap 100 ms lewat posisi kursor; app mengecil = hilang). Klik = tab Chrome.
  Sidebar dilipat: ikon Chrome tanpa tooltip, flyout = Chrome + Gemini + Flow.
- Popup profil (ChromeProfiles, subkelas OverlayPanel): JANGAN menamai metode _on_close (itu
  kait penutupan OverlayPanel); hit-test tombol Close = _in_close_btn.
- Ikon shortcut sidebar (Chrome, Gemini, Flow, Blender) = sidebar.FOOT_ICON 32 px (= foto murid),
  RGBA transparan (tanpa kotak saat baris disorot); ikon garis Gemini / Flow lewat _glyph_logo
  (kotak 32 px, ikon 20 di tengah) supaya teks semua baris sejajar. Baris 42 px, rail 44x42.
- Latar video (course_dock, dashboard_view) saat ukuran berubah (sidebar dilipat / dibuka,
  windowed <-> fullscreen): frame lama di-"cover" (course_dock.cover_resize: skala proporsional
  + potong tengah), BUKAN ditarik paksa, jadi tidak meloncat saat frame baru datang.
