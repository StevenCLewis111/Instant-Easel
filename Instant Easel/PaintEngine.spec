# PyInstaller spec: builds InstantEasel.exe, the standalone drawing app, with everything bundled (offline)
# The scripts live in folders under systems/ (Core, Drawing, Settings), so every one of those folders is searched.
import os
SYSTEMS = [d for d, _, files in os.walk('systems') if any(f.endswith('.py') for f in files)]
a = Analysis(['main.py'], pathex=['.'] + SYSTEMS,
             datas=[('images/UI', 'images/UI'), ('fonts', 'fonts')],
             hiddenimports=['PIL._tkinter_finder', 'paths', 'prefs', 'features', 'theme', 'skin', 'ui_art', 'art_panel', 'crash', 'shortcut',
                            'brushes', 'brush_catalog', 'brush_art', 'paint_window', 'rename_custom', 'draw_studio', 'studio_extras', 'studio_more', 'studio_groups', 'studio_cutout', 'studio_menu', 'studio_ai', 'ai_cutout', 'onnxruntime', 'settings_pages'],
             excludes=['matplotlib', 'pandas', 'torch', 'transformers',
                       # parts of SciPy and the AI runtime the app never uses (only scipy.ndimage, which needs linalg + special): a smaller download
                       'scipy.optimize', 'scipy.stats', 'scipy.sparse', 'scipy.spatial', 'scipy.io', 'scipy.signal', 'scipy.fft', 'scipy.fftpack',
                       'scipy.interpolate', 'scipy.integrate', 'scipy.odr', 'scipy.cluster', 'scipy.datasets', 'scipy.differentiate',
                       'onnxruntime.transformers', 'onnxruntime.quantization', 'onnxruntime.tools', 'onnxruntime.training', 'onnxruntime.datasets'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name='InstantEasel', icon='images/UI/App Icon/icon.ico', console=False, upx=False)
