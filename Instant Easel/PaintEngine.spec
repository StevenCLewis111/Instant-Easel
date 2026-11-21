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
# ---- the cut-out AI's models, built in (the build fetches them into my-models/cutout first; without them the app downloads them
# on first use instead). And a picture shown at once while the .exe unpacks itself (it's big), until the app's own splash takes over
import os
from PIL import Image as _Im
_CUT = 'my-models/cutout'
if os.path.isdir(_CUT) and any(f.endswith('.onnx') for f in os.listdir(_CUT)):
    a.datas += [(f'my-models/cutout/{f}', os.path.join(_CUT, f), 'DATA') for f in os.listdir(_CUT) if f.endswith('.onnx')]
os.makedirs('build', exist_ok=True)
_lg = _Im.open('images/UI/Splash/logo-easel.png').convert('RGBA'); _lg.thumbnail((520, 352))
_sp = _Im.new('RGBA', (_lg.width + 48, _lg.height + 40), (26, 32, 51, 255)); _sp.alpha_composite(_lg, (24, 20)); _sp.convert('RGB').save('build/splash.png')
splash = Splash('build/splash.png', binaries=a.binaries, datas=a.datas, text_pos=None)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, splash, splash.binaries, a.binaries, a.datas, name='InstantEasel', icon='images/UI/App Icon/icon.ico', console=False, upx=False)
