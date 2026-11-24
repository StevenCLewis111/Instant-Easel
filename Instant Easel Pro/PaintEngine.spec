# PyInstaller spec: builds InstantEaselPro.exe with everything bundled (offline)
# The scripts live in folders under systems/ (sorted by tab), so every one of those folders is searched.
import os
SYSTEMS = [d for d, _, files in os.walk('systems') if any(f.endswith('.py') for f in files)]
a = Analysis(['main.py'], pathex=['.'] + SYSTEMS,
             datas=[('images/UI', 'images/UI'), ('fonts', 'fonts'), ('systems/Core/common_words.txt', '.')],
             hiddenimports=['updater', 'scipy.ndimage', 'scipy.special._cdflib', 'PIL._tkinter_finder', 'paths', 'prefs', 'features', 'theme', 'skin', 'ui_art',
                            'art_panel', 'crash', 'shortcut', 'brain', 'brushes', 'brush_catalog', 'brush_art', 'paint_window', 'rename_custom', 'draw_studio', 'studio_extras', 'studio_more', 'studio_groups', 'studio_cutout', 'studio_menu', 'studio_ai', 'ai_cutout', 'esr_convert', 'onnx', 'onnx.helper', 'onnx.numpy_helper', 'pen_input', 'onnxruntime', 'edit', 'edit_pages', 'style_addons', 'glossary',
                            'settings_pages', 'learning_areas', 'image_models', 'image_grabber', 'imaging', 'image_pages', 'memory', 'storage', 'workspace', 'workspace_page', 'code_helpers', 'full_setup', 'style_addons', 'video_engine', 'video_pages', 'audio_engine'],
             excludes=['matplotlib', 'pandas', 'torch', 'transformers',
                       # parts of SciPy and the AI runtime the app never uses (only scipy.ndimage, which needs linalg + special): a smaller download
                       'scipy.optimize', 'scipy.stats', 'scipy.sparse', 'scipy.spatial', 'scipy.io', 'scipy.signal', 'scipy.fft', 'scipy.fftpack',
                       'scipy.interpolate', 'scipy.integrate', 'scipy.odr', 'scipy.cluster', 'scipy.datasets', 'scipy.differentiate',
                       'onnxruntime.transformers', 'onnxruntime.quantization', 'onnxruntime.tools', 'onnxruntime.training', 'onnxruntime.datasets'])
# ---- no AI models are built in: every one is downloaded from Settings (or when its tool is first used)
a.datas += [('build.json', 'build.json', 'DATA')] if os.path.exists('build.json') else []   # (which commit this build is: for updates)
pyz = PYZ(a.pure)
# a folder build (dist/InstantEaselPro/: InstantEaselPro.exe + _internal/): it starts at once - a one-file .exe this big would unpack itself
# (300 MB+) every time before the app could even show its splash
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='InstantEaselPro', icon='images/UI/App Icon/icon.ico', console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name='InstantEaselPro', upx=False)
