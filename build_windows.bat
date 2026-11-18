@echo off
REM Build PaintEngine.exe on your own Windows PC (needs Python 3.10+ from python.org, "Add to PATH" ticked).
cd /d "%~dp0"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm PaintEngine.spec
echo.
echo Done. Your app is in the "dist" folder: dist\InstantEasel.exe
pause
