@echo off
rem Fetches the newest InstantEasel.exe and InstantEaselPro.exe from the Releases page into their EXE Build folders now.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\get-latest-exes.ps1"
echo.
pause
