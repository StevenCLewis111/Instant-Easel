# PyInstaller spec: builds InstantEaselPro.exe with everything bundled (offline)
# The scripts live in folders under systems/ (sorted by tab), so every one of those folders is searched.
import os
SYSTEMS = [d for d, _, files in os.walk('systems') if any(f.endswith('.py') for f in files)]
a = Analysis(['main.py'], pathex=['.'] + SYSTEMS,
             datas=[('images/UI', 'images/UI'), ('images/Styles', 'images/Styles'), ('fonts', 'fonts')],
             hiddenimports=['scipy.ndimage', 'scipy.special._cdflib', 'PIL._tkinter_finder', 'scenes', 'learn', 'painter2', 'bench',
                            'brushes', 'landscape', 'paint_window', 'app', 'language', 'theme', 'img2img', 'paths', 'skin', 'ui_art',
                            'art_panel', 'crash', 'image_grabber', 'shortcut'],
             excludes=['matplotlib', 'pandas'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name='InstantEaselPro', icon='images/UI/App Icon/icon.ico', console=False, upx=False)
