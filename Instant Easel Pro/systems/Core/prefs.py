"""
prefs.py: Instant Easel Pro's settings. One store, saved as instant_easel_settings.json next to the app, read by every page.
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
    "save_format": "PNG", "jpeg_quality": 92, "auto_save": False, "name_pattern": "instant-easel-pro-{date}-{time}-{n}",
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
    "ai_drive": "", "ai_budgets": {},       # Settings > AI Storage: where the AI keeps everything, and each AI's portion (GB)
    "core_model": "", "speed_text": "Balanced", "speed_image": "Balanced",   # Fast / Balanced / Safe (Settings > AI Models)
    "model_AI_Chat": "", "model_AI_Coding": "", "model_AI_Images": "", "model_AI_Videos": "", "image_model": "",
    "image_default_style": "None", "image_default_size": "Square 1:1", "image_live_preview": True, "image_speed_boost": False,      # Settings > AI Images
    "image_sharper": False, "image_auto_upscale": "Off", "image_improve_words": True, "image_stall_minutes": 10,   # "": not chosen yet (the best downloaded / best for this PC)
    "use_gpu": True, "models_folder": "",
    # Updates
    "check_updates_on_start": False,
}
SIZES = {"edit_preview": {"Fast": 700, "Normal": 1000, "Sharp": 1400},
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
        if _data.get("name_pattern") == "instant-easel-{date}-{time}-{n}": _data["name_pattern"] = DEFAULTS["name_pattern"]   # the Pro name
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

def new_image(img, hint="", meta=None):
    """save a picture something made straight into Images (named by date and time, plus a hint like the request)"""
    name = next_name(); stem, e = os.path.splitext(name); h = _slug(hint)
    path = os.path.join(save_folder(), f"{stem}-{h}{e}" if h else name); k = 2
    while os.path.exists(path): path = os.path.join(save_folder(), f"{stem}-{h}-{k}{e}" if h else f"{stem}-{k}{e}"); k += 1
    return save_image(img, path, meta)

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

def save_image(img, path, meta=None):
    """save in the chosen format and quality (JPEG has no transparency, so it's flattened). meta: words kept inside a PNG
    (the words and seed it was painted from), read back with picture_info()"""
    fmt = {".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}.get(os.path.splitext(path)[1].lower(), "PNG")
    if fmt == "JPEG" and img.mode != "RGB": img = img.convert("RGB")
    kw = {}
    if meta and fmt == "PNG":
        from PIL.PngImagePlugin import PngInfo
        info = PngInfo(); [info.add_text(f"instant-easel:{k}", str(v)) for k, v in meta.items()]; kw["pnginfo"] = info
    tmp = path + ".saving"                                                    # a whole picture or none: never half a file
    img.save(tmp, fmt, quality=int(get("jpeg_quality")), **kw); os.replace(tmp, path)
    return path

def picture_info(path):
    """the words, seed and settings a picture was painted from ({} if it wasn't painted here, or isn't a PNG)"""
    try:
        from PIL import Image
        with Image.open(path) as im: return {k.split(":", 1)[1]: v for k, v in (getattr(im, "text", None) or {}).items() if k.startswith("instant-easel:")}
    except Exception: return {}

def latest_picture():
    """the newest picture in the Images folder (None if there isn't one)"""
    try:
        d = save_folder(); fs = [os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp"))]
        return max(fs, key=os.path.getmtime) if fs else None
    except Exception: return None

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
APP_NAME = "Instant Easel Pro"
_trail = []                                                                   # the last things you did (written with every error)
_session = False                                                              # the run's details are written once, before its first error
_seen = {}                                                                    # handled problems already noted this run (each once)

def trail(what):
    """remember an action ("tool: brush", "save: picture.png"); the last 25 go into the log with any error"""
    _trail.append(f"{datetime.datetime.now().strftime('%H:%M:%S')}  {what}"); del _trail[:-25]

def _log_write(text):
    global _session
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > LOG_MAX: os.replace(LOG, LOG[:-4] + ".1.log")
    except Exception: pass
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            if not _session:                                                  # which app, version and computer this run was
                _session = True
                import platform
                try: ver = getattr(__import__("features"), "VERSION", "")
                except Exception: ver = ""
                f.write(f"\n##### {APP_NAME}{' ' + str(ver) if ver else ''} started {_started} on {platform.platform()}, Python {platform.python_version()}"
                        f"{' (built app)' if getattr(sys, 'frozen', False) else ''} #####\n")
            f.write(text)
    except Exception: pass

def _recent():
    return ("Recent actions:\n" + "\n".join("    " + t for t in _trail) + "\n") if _trail else ""

def log_error(exc_type, exc, tb):
    """a crash (an error nothing caught): the full traceback, plus what you'd just done"""
    _log_write(f"\n=== {datetime.datetime.now().isoformat(timespec='seconds')} ERROR ===\n" + "".join(traceback.format_exception(exc_type, exc, tb)) + _recent())

def log_note(where, detail="", quiet_missing=False):
    """a problem the app caught and carried on from (a file that wouldn't save, a picture that wouldn't load...). Call it inside the
    `except`: the error being handled is written with it. Each different problem is noted once per run, so a repeat can't flood
    the log. quiet_missing=True: a file that simply isn't there yet isn't a problem"""
    et, ex, tb = sys.exc_info()
    if quiet_missing and isinstance(ex, FileNotFoundError): return
    key = (where, et.__name__ if et else "", str(ex)[:120])
    if key in _seen: return
    _seen[key] = True
    what = "".join(traceback.format_exception(et, ex, tb)) if et else ""
    _log_write(f"\n=== {datetime.datetime.now().isoformat(timespec='seconds')} PROBLEM in {where} ===\n" + (detail + "\n" if detail else "") + what + _recent())

_started = datetime.datetime.now().isoformat(timespec="seconds")
