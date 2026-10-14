@echo off
rem Menyalin kode (elearning\) dari folder proyek ke dist\app\ (dan video contoh kalau belum ada)
rem TANPA membuat .exe lagi. Jalankan setiap kali ada revisi kode.
cd /d "%~dp0"
if not exist "dist\Blender E-Learning.exe" (
  echo dist\Blender E-Learning.exe belum ada. Jalankan build.bat sekali dulu.
  pause
  exit /b 1
)
if exist "dist\app\elearning" rd /s /q "dist\app\elearning"
xcopy "%CD%\elearning" "%CD%\dist\app\elearning" /E /I /Y /Q >nul
if errorlevel 1 goto gagal
for /d /r "dist\app\elearning" %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
rem Video hanya disalin kalau folder video di dist\ belum ada (agar video ganti-an tidak tertimpa)
if not exist "dist\assets\video" (
  xcopy "%CD%\assets\video" "%CD%\dist\assets\video" /E /I /Y /Q >nul
  if errorlevel 1 goto gagal
)
if /i not "%1"=="nopause" (
  echo.
  echo SELESAI. dist\ sudah diperbarui. Tidak perlu build ulang.
  pause
)
exit /b 0
:gagal
echo.
echo GAGAL menyalin. Pastikan aplikasi sudah ditutup lalu coba lagi.
if /i not "%1"=="nopause" pause
exit /b 1
