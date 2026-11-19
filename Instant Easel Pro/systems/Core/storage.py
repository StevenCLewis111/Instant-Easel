"""
storage.py: the AI drive. All of the AI's things (models, what each AI learned, libraries, memory, training pictures) live in one
place: a drive you give it (Settings > AI Storage), or this app's folder until you do. Each AI gets its own portion:

    Shared models   the core text model, the engines, the image and coding models          my-models/runtime, my-models/text/<model>, my-models/image
    AI Chat         its examples, library and memory                                        my-models/text/tabs/AI_Chat, memory/<user>/chat
    AI Coding       its examples, library, projects and memory                              my-models/text/tabs/AI_Coding, memory/<user>/coding
    AI Images       your image models and their pictures                                   my-library/Image models, my-models/text/tabs/AI_Images
    AI Videos       video clips to learn from                                               my-library/Video clips, my-models/text/tabs/AI_Videos

A portion is a budget: adding to an AI stops politely when its portion is full (you can raise it any time).
"""
import os, shutil, json
import paths

AREAS = {
    "Shared models": [("my-models", "runtime")] + [("my-models", "text", k) for k in ("27b", "9b", "4b", "2b", "coder14b", "coder7b", "coder3b")]
                     + [("my-models", "text", "custom"), ("my-models", "image"), ("my-models", "video")],
    "AI Chat": [("my-models", "text", "tabs", "AI_Chat"), ("memory", "chat")],
    "AI Coding": [("my-models", "text", "tabs", "AI_Coding"), ("memory", "coding")],
    "AI Images": [("my-library", "Image models"), ("my-models", "text", "tabs", "AI_Images")],
    "AI Videos": [("my-library", "Video clips"), ("my-models", "text", "tabs", "AI_Videos")],
}
DEFAULT_GB = {"Shared models": 150, "AI Chat": 150, "AI Coding": 200, "AI Images": 300, "AI Videos": 200}     # 1 TB in all
TOP = ("my-models", "my-library", "memory")                     # what moves when the AI drive changes

def _prefs():
    import prefs; return prefs

def budget_gb(area):
    b = _prefs().get("ai_budgets") or {}
    try: return int(b.get(area, DEFAULT_GB[area]))
    except (TypeError, ValueError): return DEFAULT_GB[area]

def set_budget_gb(area, gb):
    b = dict(_prefs().get("ai_budgets") or {}); b[area] = int(gb); _prefs().set("ai_budgets", b)

def _size(path):
    total = 0
    for d, _, fs in os.walk(path):
        for f in fs:
            try: total += os.path.getsize(os.path.join(d, f))
            except OSError: pass
    return total

def used(area, root=None):
    root = root or paths.ai_root(); return sum(_size(os.path.join(root, *p)) for p in AREAS[area])

def area_for(tab):
    return {"AI Chat": "AI Chat", "AI Coding": "AI Coding", "AI Images": "AI Images", "AI Videos": "AI Videos"}.get(tab, "Shared models")

def room(area, adding=0):
    """(fits, message): can `adding` bytes go into this AI's portion?"""
    left = budget_gb(area) * 1e9 - used(area)
    if adding <= left: return True, ""
    return False, f"{area}'s portion is full ({used(area) / 1e9:.1f} of {budget_gb(area)} GB). Raise it in Settings > AI Storage."

def drive_free(root=None):
    try: u = shutil.disk_usage(root or paths.ai_root()); return u.free, u.total
    except OSError: return 0, 0

def move_to(new_root, progress=None):
    """copy everything the AI keeps to new_root, switch to it, then remove the old copies. progress(text)"""
    old = paths.ai_root(); new_root = os.path.abspath(new_root); os.makedirs(new_root, exist_ok=True)
    if os.path.abspath(old) == new_root: return
    need = sum(_size(os.path.join(old, t)) for t in TOP)
    if need > drive_free(new_root)[0]: raise RuntimeError(f"not enough free space there ({need / 1e9:.1f} GB needed)")
    for t in TOP:
        src = os.path.join(old, t)
        if not os.path.isdir(src): continue
        if progress: progress(f"Copying {t}…")
        shutil.copytree(src, os.path.join(new_root, t), dirs_exist_ok=True)
    _prefs().set("ai_drive", new_root)
    for t in TOP:
        src = os.path.join(old, t)
        if os.path.isdir(src): shutil.rmtree(src, ignore_errors=True)
    if progress: progress("Done")
