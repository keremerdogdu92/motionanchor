@echo off
setlocal
set "MOTIONANCHOR_FFMPEG=C:\Users\kerem\AppData\Local\Microsoft\WinGet\Packages\BtbN.FFmpeg.LGPL.8.1_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-n8.1.2-21-gce3c09c101-win64-lgpl-8.1\bin\ffmpeg.exe"
set "MOTIONANCHOR_FFPROBE=C:\Users\kerem\AppData\Local\Microsoft\WinGet\Packages\BtbN.FFmpeg.LGPL.8.1_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-n8.1.2-21-gce3c09c101-win64-lgpl-8.1\bin\ffprobe.exe"
cd /d C:\Users\kerem\Documents\AI-Work\repos\motionanchor
cd worker
.venv\Scripts\python.exe -m unittest discover -s tests -v
if errorlevel 1 exit /b 1
cd ..
cargo test --manifest-path src-tauri\Cargo.toml
if errorlevel 1 exit /b 1
call npm run typecheck
if errorlevel 1 exit /b 1
call npm run build
if errorlevel 1 exit /b 1
git diff --check
