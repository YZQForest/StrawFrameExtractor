@echo off
setlocal
cd /d "%~dp0"
if not exist ffmpeg\ffmpeg.exe goto missing
if not exist ffmpeg\ffprobe.exe goto missing
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pytest -q
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean StrawFrameStudio.spec
if errorlevel 1 goto fail
xcopy /e /i /y ffmpeg dist\StrawFrameStudio\ffmpeg
if errorlevel 1 goto fail
copy README.md dist\StrawFrameStudio\README.md >nul
copy BUILD.md dist\StrawFrameStudio\BUILD.md >nul
echo Ready: dist\StrawFrameStudio\StrawFrameStudio.exe
pause
exit /b 0
:missing
echo Put ffmpeg.exe and ffprobe.exe in the ffmpeg folder first.
pause
exit /b 1
:fail
echo Build failed. Review the error above.
pause
exit /b 1
