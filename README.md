# Blender E-Learning

Aplikasi desktop (Python + Tkinter) untuk belajar Blender secara offline.
Tahap saat ini: layar login (video latar) dan pilihan 6 kursus. Isi kursus menyusul.

## Struktur folder

```
BlenderELearning/
├── main.py                  Titik masuk aplikasi
├── build.bat                Membuat .exe (cukup SEKALI di awal)
├── update.bat               Salin revisi kode ke dist\ (tanpa build ulang)
├── requirements.txt         Kebutuhan: opencv-python-headless, Pillow
├── README.md
├── assets/
│   ├── icon.ico             Ikon aplikasi (ikut masuk ke .exe)
│   └── video/               VIDEO LATAR LOGIN: ganti video di sini
│       ├── background.mp4
│       └── BACA-SAYA.txt
└── elearning/               Seluruh kode aplikasi
    ├── config.py            Nama app, warna, font, lokasi file, redup video
    ├── splash.py            Splash screen kecil "Memuat aplikasi…" saat .exe dibuka
    ├── courses.py           Daftar 6 kursus (judul, deskripsi, warna)
    ├── students.py          Data siswa: tambah, ubah nama, hapus, kursus yang boleh dibuka (data\students.json)
    ├── sessions.py          Riwayat masuk/keluar murid + durasi (data\sessions.json)
    ├── teachers.py          Akun guru (ID + PIN)
    ├── photos.py            Foto profil murid (simpan, potong, bulatkan)
    └── ui/
        ├── window.py            Jendela utama, pindah antar layar
        ├── login_screen.py      Layar login
        ├── video_background.py  Pemutar video latar (loop)
        ├── home_screen.py       Layar pilihan kursus setelah login
        ├── course_card.py       Kartu satu kursus (terbuka / terkunci)
        ├── course_screen.py     Layar satu kursus: sidebar kiri bisa dilipat + area materi
        ├── teacher_screen.py    Layar guru: foto murid + tombol ON/OFF akses kursus
        ├── avatar.py            Foto profil bulat (atau lingkaran inisial), tepi anti-alias
        ├── dialogs.py           Dialog Tambah murid / Ubah nama / Konfirmasi hapus (layar guru)
        ├── topbar.py            Bar atas (nama siswa, Kembali, Keluar)
        └── widgets.py           Komponen kecil yang dipakai bersama
```

## Mengganti video latar

Folder `assets\video\` berada DI LUAR .exe, jadi cukup hapus video lama dan
taruh video baru, tanpa build ulang. Setelah build, folder yang dipakai
aplikasi ada di `dist\assets\video\` (di samping .exe).

- Format: .mp4 (disarankan), .mov, .mkv, .avi, .webm, .m4v
- Disarankan MP4 H.264, 720p/1080p, 10-30 detik, tanpa suara
- Kalau ada beberapa video, yang pertama menurut abjad yang dipakai
- Tingkat gelap video diatur di `elearning/config.py` (`VIDEO_DIM`)

## Menjalankan (tanpa membuat .exe)

```
python -m pip install -r requirements.txt
python main.py
```

## Membuat .exe (sekali di awal)

Klik dua kali `build.bat`. Hasilnya folder `dist\` berisi:

```
dist\
├── Blender E-Learning.exe
├── assets\video\       video latar (ganti kapan saja)
└── app\elearning\      kode aplikasi (perbarui kapan saja)
```

Untuk PC lain, copy SEMUA isi `dist\`.

## Revisi tanpa build ulang

.exe memakai kode di `app\elearning\` (di sampingnya) lebih dulu daripada kode
yang tertanam di dalamnya. Jadi untuk revisi biasa:

- **Di PC kamu:** ganti folder `elearning\` di proyek dengan versi baru, lalu klik
  dua kali `update.bat`. Selesai, jalankan .exe.
- **Di PC siswa:** copy folder `app\elearning\` dari `dist\` ke samping .exe di
  PC siswa (timpa yang lama).
- **Aset baru** (logo, gambar): taruh di folder `assets\` di samping .exe.

Kalau kode di `app\elearning\` rusak, .exe otomatis memakai kode bawaannya
dan mencatat penyebabnya di `app.log`.

**Tetap perlu `build.bat` lagi** kalau revisinya menambah library baru
(selain OpenCV dan Pillow), atau mengubah `main.py`, ikon .exe, atau `build.bat`.

## Ganti logo

Ganti `assets\icon.ico`, lalu jalankan `build.bat` lagi.

## Kalau video tidak tampil

Layar login otomatis memakai warna polos. Penyebabnya dicatat di `app.log`
(di samping .exe, atau di folder proyek kalau dijalankan dengan `python main.py`).

## Kursus

Enam kursus: BASIC 1, BASIC 2, INTERMEDIATE 1, INTERMEDIATE 2, AI CHARACTER,
AI INTERIOR. Judul dan deskripsi diubah di `elearning/courses.py`
(deskripsi sekarang masih contoh).

Tiap siswa hanya bisa membuka kursus yang ditugaskan; sisanya tampil abu-abu
(terkunci). Pengaturannya ada di `elearning/students.py`.

## ID contoh

| ID    | Jenis        | Kursus yang terbuka                   |
|-------|--------------|---------------------------------------|
| PB001 | Murid dewasa | BASIC 1, BASIC 2                      |
| PB002 | Murid dewasa | BASIC 1, BASIC 2, INTERMEDIATE 1      |
| PB003 | Murid dewasa | Semua kursus                          |
| SK001 | Murid anak   | SUPERKIDS 1, 2                        |
| SK002 | Murid anak   | SUPERKIDS 1, 2, 3                     |
| SK003 | Murid anak   | Semua kursus                          |

## Login guru dan mengatur akses kursus

Di layar login, ketik ID `GURU001`; kolom PIN muncul otomatis (PIN: `guru123`).
Guru masuk ke layar **Atur Akses Kursus**: pilih murid di kiri, lalu geser tombol
ON/OFF pada tiap kursus. ON = terbuka, OFF = terkunci. Perubahan langsung tersimpan.

- Pengaturan disimpan di `data\students.json` (di samping .exe). Folder `data\`
  TIDAK disentuh `update.bat` maupun `build.bat`, jadi pengaturan guru aman.
- Murid melihat perubahan saat login berikutnya (keluar lalu masuk lagi).
- Pengaturan hanya berlaku di PC tempat file `data\students.json` berada. Untuk
  PC murid lain, copy file itu ke folder `data\` di samping .exe mereka.
- Ganti PIN / tambah guru: edit `elearning/teachers.py`, lalu klik `update.bat`.
- Tambah murid baru: di layar guru klik **+ Tambah murid** (bawah daftar murid), isi
  nama dan kategori. ID dibuat otomatis (PB004, SK004, ...) tapi boleh diganti. Semua
  kursus murid baru terkunci dulu; geser ON untuk membukanya.
- Ubah nama murid: pilih murid, klik **Ubah nama…**. ID, foto, dan akses kursus tidak berubah.
- Hapus murid: pilih murid, klik **Hapus murid** (pojok kanan atas kepala), lalu konfirmasi.
  Akun, foto, dan riwayat login murid itu ikut terhapus dan tidak bisa dikembalikan.

## Riwayat login murid

Di layar guru, pilih murid lalu buka tab **Riwayat Login**: total lama belajar, jumlah
masuk, terakhir masuk, dan daftar sesi (tanggal, jam masuk, jam keluar, durasi). Durasi
ditulis singkat: `<1 Mnt`, `25 Mnt`, `3.5 Jam`.

- Jam keluar tercatat saat murid klik **Keluar** atau menutup jendela aplikasi.
- Kalau aplikasi mati mendadak (listrik padam, ditutup paksa), jam keluar diperkirakan dari
  aktivitas terakhir (dicatat tiap menit) dan ditandai `~` di daftar.
- Disimpan di `data\sessions.json` (aman dari `update.bat`). Seperti data lain, hanya
  berlaku di PC tempat file itu berada.
- Login guru tidak dicatat.
- PIN guru dan file data bisa dibaca siapa saja yang membuka folder aplikasi,
  jadi ini untuk kemudahan di kelas, bukan keamanan tinggi.

## Splash screen

Begitu kode aplikasi mulai berjalan, muncul kotak kecil "Memuat aplikasi…" di tengah
layar, dan hilang otomatis saat jendela login siap. Catatan: beberapa detik pertama
setelah klik dua kali .exe (saat .exe membongkar dirinya) belum bisa ditutupi splash ini,
karena belum ada kode Python yang berjalan.

## Foto profil murid

Guru login, pilih murid di sidebar kiri, lalu klik **Pilih foto…** (atau **Ganti foto…**).
Foto otomatis dipotong persegi dari bagian tengah dan dibulatkan. **Hapus foto**
mengembalikan lingkaran berisi inisial.

- Format: JPG, PNG, BMP, GIF, WEBP. Foto HP yang "miring" diluruskan otomatis.
  Foto HEIC (iPhone) belum didukung: ubah dulu ke JPG.
- Foto disimpan di `data\photos\<ID>.png` (di samping .exe), aman dari `update.bat`.
- Foto muncul di bar atas setelah murid login, dan di sidebar saat membuka kursus.
- Untuk PC murid lain, copy folder `data\photos\` bersama `data\students.json`.

## Sidebar di dalam kursus

Saat murid membuka satu kursus, sidebar kiri menampilkan foto dan nama murid
(paling atas), daftar kursus (klik untuk pindah; yang terkunci abu-abu), serta
tombol Kembali. Tombol **Keluar** ada di pojok kanan atas layar (bukan di sidebar), sama seperti di layar
pilihan kursus. Tombol `«` melipat sidebar jadi strip sempit
(foto kecil + tombol), tombol `»` membukanya lagi. Pilihan lipat diingat selama
aplikasi terbuka.
