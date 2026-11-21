@echo off
rem Turns on automatic exe updates: after this, every GitHub Desktop pull also fetches the newest
rem InstantEasel.exe and InstantEaselPro.exe from the Releases page into their EXE Build folders. Run it once.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\setup-auto-updates.ps1"
echo.
pause
