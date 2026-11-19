"""
prefs.py: Instant Easel's settings. One store, saved as instant_easel_settings.json next to the app, read by every page.
    import prefs
    prefs.get("save_format")          # -> "PNG"
    prefs.set("auto_save", True)      # saves to disk and tells anything listening
"""
import os, sys, json, datetime, subprocess, shutil, traceback, threading

import paths
def home_dir(): return paths.HOME                                     # your data: next to main.py (or the .exe)

DEFAULTS = {
    # General
    "work_folder": "",                     # "" = the folder of the app you launched (main.py's folder, or the .exe's folder)
    "save_format": "PNG", "jpeg_quality": 92, "auto_save": False, "name_pattern": "instant-easel-{date}-{time}-{n}",
    "start_tab": "Drawing", "confirm_exit": True,
    # Generation defaults
    "default_model": "Core (default)", "default_style": "Painterly", "default_aspect": "2:3", "default_count": "1",
    "seed_mode": "random", "fixed_seed": 1234,
    # Performance
    "edit_preview": "Normal", "i2i_size": "Standard", "undo_steps": 30,
    # Display
    "text_size": "Normal", "show_hints": True, "show_splash": True,
    "window_mode": "Maximized", "remember_window": True, "window_geometry": "", "last_tab": "Drawing",
    # Privacy & data
    "keep_training_copies": False, "active_model": "Core (default)",
    # AI models
    "use_gpu": True, "models_folder": "", "text_model": "auto",
    # Updates
    "check_updates_on_start": False,
}
SIZES = {"edit_preview": {"Fast": 700, "Normal": 1000, "Sharp": 1400}, "i2i_size": {"Fast": 1200, "Standard": 1600, "Large": 2400},
         "text_size": {"Small": 0.9, "Normal": 1.0, "Large": 1.15}}
_FILE = paths.json_file("instant_easel_settings.json"); _data = None; _listeners = []; _wlock = threading.RLock()

def _write():
    """save the settings safely: written to a new file first and swapped in whole (a crash mid-save can't leave half a file),
    and the last good copy is kept as .bak, which is read back if the main file is ever damaged"""
    with _wlock:
        try:
            tmp = _FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f: json.dump(_data, f, indent=1); f.flush(); os.fsync(f.fileno())
            if os.path.exists(_FILE):
                try: shutil.copyfile(_FILE, _FILE + ".bak")
                except Exception: pass
            os.replace(tmp, _FILE)
        except Exception: pass

def _read(path):
    with open(path, encoding="utf-8") as f: d = json.load(f)
    if not isinstance(d, dict): raise ValueError("not a settings file")
    return d

def _load():
    global _data
    if _data is None:
        _data = dict(DEFAULTS)
        for path in (_FILE, _FILE + ".bak"):                              # the settings, else the last good copy
            try: _data.update(_read(path)); break
            except FileNotFoundError: continue
            except Exception:
                try: shutil.copyfile(path, path + ".damaged")              # keep the damaged one for a look, then try the backup
                except Exception: pass
        if not _data.get("_launch_maximized_v2"):                         # once more (Nov 2026): start maximized (title bar and taskbar showing), not full screen
            _data["window_mode"] = "Maximized"; _data["_launch_maximized_v2"] = _data["_launch_maximized_v1"] = True
            _write()
        if not _data.get("_launch_maximized_v1"):                         # once: the new start-up default (title bar, fills the screen above the taskbar)
            _data["window_mode"] = "Maximized"; _data["_launch_maximized_v1"] = True
            _write()
    return _data

def get(key): return _load().get(key, DEFAULTS.get(key))
def set(key, value):
    with _wlock: _load()[key] = value; _write()
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

# Your work folder: every tab saves into, and opens from, the folder for that kind of thing, so anything one tab makes is easy to
# pick up in another (an image the chat made is in images; Videos' "load image" opens images). It's the folder of the app you
# launched: main.py's folder when you run the code, the .exe's folder (EXE Build) when you run the .exe. Each app keeps its own.
KINDS = ("images", "videos", "code", "chats")
def work_root():
    f = get("work_folder") or paths.HOME; os.makedirs(f, exist_ok=True); return f

def work_folder(kind="images"):
    d = os.path.join(work_root(), kind.lower()); os.makedirs(d, exist_ok=True); return d

def save_folder(): return work_folder("images")                     # pictures you save or make: the images folder

def _slug(text, n=40):
    import re; t = re.sub(r"[^A-Za-z0-9]+", "-", str(text)).strip("-").lower(); return t[:n].rstrip("-")

def new_image(img, hint=""):
    """save a picture something made straight into Images (named by date and time, plus a hint like the request)"""
    name = next_name(); stem, e = os.path.splitext(name); h = _slug(hint)
    path = os.path.join(save_folder(), f"{stem}-{h}{e}" if h else name); k = 2
    while os.path.exists(path): path = os.path.join(save_folder(), f"{stem}-{h}-{k}{e}" if h else f"{stem}-{k}{e}"); k += 1
    return save_image(img, path)

def new_text(kind, text, hint="", ext=".md"):
    """save text (a chat, some code) into Chats or Code"""
    now = datetime.datetime.now(); h = _slug(hint) or kind.lower()
    path = os.path.join(work_folder(kind), f"{now.strftime('%Y-%m-%d-%H%M%S')}-{h}{ext}")       # kind: "Chats" / "Code" (any case)
    with open(path, "w", encoding="utf-8") as f: f.write(text)
    return path

def ext(): return {"PNG": ".png", "JPEG": ".jpg", "WebP": ".webp"}[get("save_format")]

def next_name(n=1):
    now = datetime.datetime.now()
    return get("name_pattern").format(date=now.strftime("%Y-%m-%d"), time=now.strftime("%H%M%S"), n=n) + ext()

def save_image(img, path):
    """save in the chosen format and quality (JPEG has no transparency, so it's flattened)"""
    fmt = {".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}.get(os.path.splitext(path)[1].lower(), "PNG")
    if fmt == "JPEG" and img.mode != "RGB": img = img.convert("RGB")
    tmp = path + ".saving"                                                    # a whole picture or none: never half a file
    img.save(tmp, fmt, quality=int(get("jpeg_quality"))); os.replace(tmp, path)
    return path

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
