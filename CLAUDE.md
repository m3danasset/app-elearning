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

## Badge / achievement (tahap 1)
- elearning/achievements.py: 20 badge (sama untuk dewasa & SUPERKIDS, trial tidak dapat),
  data per murid di data\achievements\<ID>.json. Video dihitung dari bagian yang BENAR-BENAR
  ditonton (progress.py "seen", min. 80 %), bukan posisi terjauh.
- ui/badge_art.py (ikon, numpy), ui/badge_ui.py (halaman Badge, notifikasi kiri-bawah di atas
  sidebar, pelacak di thread). Notifikasi ditahan saat video layar penuh / Blender dipakai.
- Easter egg diatur di config.py (SECRET_CODE, SPECIAL_DAYS); ganti berkala.
- Belum: sertifikat, easter egg khusus trial. (Statistik badge sudah ada di Analytics.)

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

## Analytics admin (tab paling atas, dibuka pertama)
- Kartu angka: murid aktif (+ tanpa jadwal), jam belajar, kehadiran jadwal (%), portfolio,
  assignment, badge didapat (naik/turun vs periode sebelumnya; kehadiran dalam poin).
- Kehadiran jadwal: tiap jadwal yang SUDAH selesai sejak jadwal dibuat ("since" di
  schedule.json); hadir = login min. 10 menit di jam jadwal (boleh 15 menit lebih awal).
- Kartu baru: Kehadiran per jadwal, Badge paling banyak didapat; grafik upload ikut
  Assignment; "Perlu diperhatikan" + hadir jadwal < 50 % / belum punya jadwal; "Paling
  rajin" + jumlah badge. compute() tetap di thread.

