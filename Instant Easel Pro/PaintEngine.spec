# PyInstaller spec: builds InstantEaselPro.exe with everything bundled (offline)
# The scripts live in folders under systems/ (sorted by tab), so every one of those folders is searched.
import os
SYSTEMS = [d for d, _, files in os.walk('systems') if any(f.endswith('.py') for f in files)]
a = Analysis(['main.py'], pathex=['.'] + SYSTEMS,
             datas=[('images/UI', 'images/UI'), ('fonts', 'fonts')],
             hiddenimports=['scipy.ndimage', 'scipy.special._cdflib', 'PIL._tkinter_finder', 'paths', 'prefs', 'features', 'theme', 'skin', 'ui_art',
                            'art_panel', 'crash', 'shortcut', 'brain', 'brushes', 'brush_catalog', 'brush_art', 'paint_window', 'rename_custom', 'draw_studio', 'studio_extras', 'studio_more', 'studio_groups', 'studio_cutout', 'studio_menu', 'studio_ai', 'ai_cutout', 'esr_convert', 'onnxruntime', 'edit', 'edit_pages',
                            'settings_pages', 'learning_areas', 'image_models', 'image_grabber', 'imaging', 'image_pages', 'memory', 'storage', 'workspace', 'workspace_page'],
             excludes=['matplotlib', 'pandas', 'torch', 'transformers', 'onnx',
                       # parts of SciPy and the AI runtime the app never uses (only scipy.ndimage, which needs linalg + special): a smaller download
                       'scipy.optimize', 'scipy.stats', 'scipy.sparse', 'scipy.spatial', 'scipy.io', 'scipy.signal', 'scipy.fft', 'scipy.fftpack',
                       'scipy.interpolate', 'scipy.integrate', 'scipy.odr', 'scipy.cluster', 'scipy.datasets', 'scipy.differentiate',
                       'onnxruntime.transformers', 'onnxruntime.quantization', 'onnxruntime.tools', 'onnxruntime.training', 'onnxruntime.datasets'])
# ---- the cut-out AI's models, built in (the build fetches them into my-models/cutout first; without them the app downloads them
# on first use instead)
import os
_CUT = 'my-models/cutout'
if os.path.isdir(_CUT) and any(f.endswith('.onnx') for f in os.listdir(_CUT)):
    a.datas += [(f'my-models/cutout/{f}', os.path.join(_CUT, f), 'DATA') for f in os.listdir(_CUT) if f.endswith('.onnx')]
pyz = PYZ(a.pure)
# a folder build (dist/InstantEaselPro/: InstantEaselPro.exe + _internal/): it starts at once - a one-file .exe this big would unpack itself
# (300 MB+) every time before the app could even show its splash
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='InstantEaselPro', icon='images/UI/App Icon/icon.ico', console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name='InstantEaselPro', upx=False)
