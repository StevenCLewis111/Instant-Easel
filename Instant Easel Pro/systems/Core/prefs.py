"""
prefs.py: Instant Easel's settings. One store, saved as instant_easel_settings.json next to the app, read by every page.
    import prefs
    prefs.get("save_format")          # -> "PNG"
    prefs.set("auto_save", True)      # saves to disk and tells anything listening
"""
import os, sys, json, datetime, subprocess, shutil, traceback

import paths
def home_dir(): return paths.HOME                                     # your data: next to main.py (or the .exe)

DEFAULTS = {
    # General
    "save_folder": os.path.join(os.path.expanduser("~"), "Pictures", "Instant Easel"),
    "save_format": "PNG", "jpeg_quality": 92, "auto_save": False, "name_pattern": "instant-easel-{date}-{time}-{n}",
    "start_tab": "AI Images", "confirm_exit": True,
    "seed_mode": "random", "fixed_seed": 1234,
    # Performance
    "edit_preview": "Normal", "undo_steps": 30,
    # Display
    "text_size": "Normal", "show_hints": True, "show_splash": True,
    "window_mode": "Maximized", "remember_window": True, "window_geometry": "", "last_tab": "AI Images",
    # Privacy & data
    "keep_training_copies": False,
    # AI models: one core text model for every AI tab; a tab can add its own model (Settings > AI Models)
    "core_model": "4b", "model_AI_Coding": "core", "model_AI_Images": "sd15", "model_AI_Videos": "none", "image_model": "",
    "use_gpu": True, "models_folder": "",
    # Updates
    "check_updates_on_start": False,
}
SIZES = {"edit_preview": {"Fast": 700, "Normal": 1000, "Sharp": 1400},
         "text_size": {"Small": 0.9, "Normal": 1.0, "Large": 1.15}}
_FILE = paths.json_file("instant_easel_settings.json"); _data = None; _listeners = []

def _load():
    global _data
    if _data is None:
        _data = dict(DEFAULTS)
        try: _data.update(json.load(open(_FILE)))
        except Exception: pass
        if not _data.get("_launch_maximized_v1"):                         # once: the new start-up default (title bar, fills the screen above the taskbar)
            _data["window_mode"] = "Maximized"; _data["_launch_maximized_v1"] = True
            try: json.dump(_data, open(_FILE, "w"), indent=1)
            except Exception: pass
    return _data

def get(key): return _load().get(key, DEFAULTS.get(key))
def set(key, value):
    _load()[key] = value
    try: json.dump(_data, open(_FILE, "w"), indent=1)
    except Exception: pass
    for fn in list(_listeners):
        try: fn(key, value)
        except Exception: pass
def on_change(fn): _listeners.append(fn)
def reset_all():
    global _data
    _data = dict(DEFAULTS)
    try: os.remove(_FILE)
    except OSError: pass
def size(key): return SIZES[key][get(key)]
def all_settings(): return dict(_load())

# ---------------- files and folders
def models_folder():
    f = get("models_folder") or os.path.join(home_dir(), "models"); os.makedirs(f, exist_ok=True); return f

def save_folder():
    f = get("save_folder"); os.makedirs(f, exist_ok=True); return f

def ext(): return {"PNG": ".png", "JPEG": ".jpg", "WebP": ".webp"}[get("save_format")]

def next_name(n=1):
    now = datetime.datetime.now()
    return get("name_pattern").format(date=now.strftime("%Y-%m-%d"), time=now.strftime("%H%M%S"), n=n) + ext()

def save_image(img, path):
    """save in the chosen format and quality (JPEG has no transparency, so it's flattened)"""
    fmt = {".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}.get(os.path.splitext(path)[1].lower(), "PNG")
    if fmt == "JPEG" and img.mode != "RGB": img = img.convert("RGB")
    img.save(path, fmt, quality=int(get("jpeg_quality")))
    return path

def auto_save(images, label="result"):
    """if auto-save is on, every result goes to the save folder (dated subfolder) the moment it's made"""
    if not get("auto_save"): return []
    d = os.path.join(save_folder(), datetime.date.today().isoformat()); os.makedirs(d, exist_ok=True); out = []
    for i, im in enumerate(images): out.append(save_image(im, os.path.join(d, next_name(i + 1))))
    return out

def open_folder(path):
    os.makedirs(path, exist_ok=True)
    try:
        if sys.platform == "win32": os.startfile(path)
        elif sys.platform == "darwin": subprocess.Popen(["open", path])
        else: subprocess.Popen(["xdg-open", path])
    except Exception: pass

def folder_size(path):
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try: total += os.path.getsize(os.path.join(root, f))
            except OSError: pass
    return total

def human(n):
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB": return f"{n:.0f} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1024

# ---------------- error log (a local file only; nothing is sent anywhere)
LOG = paths.log_file("instant_easel_errors.log")
LOG_MAX = 1_000_000                                                          # ~1 MB; the older log rolls to instant_easel_errors.1.log
def log_error(exc_type, exc, tb):
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > LOG_MAX: os.replace(LOG, LOG[:-4] + ".1.log")
    except Exception: pass
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"\n=== {datetime.datetime.now().isoformat(timespec='seconds')} ===\n" + "".join(traceback.format_exception(exc_type, exc, tb)))
    except Exception: pass
