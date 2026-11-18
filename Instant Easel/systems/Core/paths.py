"""
paths.py: where everything in Instant Easel lives. Every script asks here instead of building paths from its own location, so
scripts can sit in any folder under systems/ and still find the pictures, fonts, settings and logs.

    APP     the program's own files (images/, fonts/) - inside the .exe bundle when frozen
    HOME    your data (settings, logs, my-library, my-models ...) - next to main.py, or next to the .exe

    paths.image("UI", "Header", "title-logo.png")      paths.font("CourierPrime-Bold.ttf")
    paths.json_file("instant_easel_settings.json")      ->  HOME/.json/...     (folder made if needed)
    paths.log_file("instant_easel_errors.log")         ->  HOME/logs/...
    paths.data("my-library")                           ->  HOME/my-library
"""
import os, sys

def _project_root():
    """the folder holding main.py (this file is somewhere under systems/)"""
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        if os.path.exists(os.path.join(d, "main.py")) and os.path.isdir(os.path.join(d, "systems")): return d
        d = os.path.dirname(d)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FROZEN = bool(getattr(sys, "frozen", False))
APP = getattr(sys, "_MEIPASS", None) or _project_root()
HOME = os.path.dirname(os.path.abspath(sys.executable)) if FROZEN else _project_root()

IMAGES = os.path.join(APP, "images")
UI = os.path.join(IMAGES, "UI")
FONTS = os.path.join(APP, "fonts")
JSON_DIR = os.path.join(HOME, ".json")
LOGS = os.path.join(HOME, "logs")

def image(*p): return os.path.join(IMAGES, *p)
def ui(*p): return os.path.join(UI, *p)
def font(name): return os.path.join(FONTS, name)
def data(*p): return os.path.join(HOME, *p)
def saved_images(*p):
    """pictures the app saves (scraped images, the starting image ...): HOME/images/..."""
    d = os.path.join(HOME, "images", *p[:-1]) if p else os.path.join(HOME, "images")
    os.makedirs(d, exist_ok=True); return os.path.join(HOME, "images", *p)

def json_file(name):
    os.makedirs(JSON_DIR, exist_ok=True); return os.path.join(JSON_DIR, name)

def log_file(name):
    os.makedirs(LOGS, exist_ok=True); return os.path.join(LOGS, name)

def systems_folders(root=None):
    """every folder under systems/ that holds scripts (added to the import path at start-up)"""
    base = os.path.join(root or APP, "systems"); out = []
    for d, dirs, files in os.walk(base):
        dirs[:] = sorted(x for x in dirs if not x.startswith((".", "__")))
        if any(f.endswith(".py") for f in files): out.append(d)
    return out
