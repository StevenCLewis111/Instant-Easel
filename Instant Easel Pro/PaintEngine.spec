# PyInstaller spec: builds InstantEasel.exe with everything bundled (offline)
a = Analysis(['main.py'], pathex=['.'], datas=[('styles', 'styles'), ('fonts', 'fonts'), ('brand', 'brand')],
             hiddenimports=['scipy.ndimage', 'scipy.special._cdflib', 'PIL._tkinter_finder', 'scenes', 'learn', 'painter2', 'bench',
                            'test_scene', 'brushes', 'landscape', 'paint_window', 'app', 'language', 'theme', 'img2img'],
             excludes=['matplotlib', 'pandas'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name='InstantEasel', icon='brand/icon.ico', console=False, upx=False)
