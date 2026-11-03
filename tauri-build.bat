@echo off
set "ProgramData=C:\ProgramData"
set "ProgramFiles=C:\Program Files"
set "ProgramFiles(x86)=C:\Program Files (x86)"
set "PUBLIC=C:\Users\Public"
set "HOME=%USERPROFILE%"
set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
cd /d "%~dp0translate-tauri"
call node build-cli.cjs > build.log 2>&1
echo EXIT_CODE=%ERRORLEVEL% >> build.log
