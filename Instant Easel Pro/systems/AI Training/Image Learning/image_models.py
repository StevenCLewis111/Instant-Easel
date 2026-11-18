"""
image_models.py: your own image models (Cartoon, Fashion, Nature...). Each one is a small add-on (a LoRA) trained on top of the
image model chosen in Settings > AI Models, from its own pictures, so a cartoon model never picks up the fashion model's look.

    my-library/Image models/<Name>/
        model.json          name, focus, description, trigger word, when made, last trained
        pictures/<label>/   the pictures it learns from, one folder per label (the word you searched, e.g. "shoe")
        lora/               the trained add-on (once training is built)

    import image_models as IM
    IM.create("Cartoon", focus="Cartoons")   IM.names()   IM.active() / IM.set_active(name)   IM.pictures("Cartoon")
"""
import os, json, re, shutil, datetime
import paths

FOCUS = ["Cartoons", "Fashion", "Nature", "Portraits", "Animals", "Products", "Architecture", "Anything"]
EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp")

def root():
    d = paths.data("my-library", "Image models"); os.makedirs(d, exist_ok=True); return d

def _safe(name): return re.sub(r'[<>:"/\\|?*]+', "", name).strip()[:60]

def folder(name): return os.path.join(root(), _safe(name))
def pictures_dir(name): d = os.path.join(folder(name), "pictures"); os.makedirs(d, exist_ok=True); return d

def names():
    return sorted(d for d in os.listdir(root()) if os.path.isfile(os.path.join(root(), d, "model.json")))

def info(name):
    try: return json.load(open(os.path.join(folder(name), "model.json"), encoding="utf-8"))
    except Exception: return {}

def _save(name, d):
    with open(os.path.join(folder(name), "model.json"), "w", encoding="utf-8") as f: json.dump(d, f, indent=1)

def create(name, focus="Anything", description=""):
    name = _safe(name)
    if not name: raise ValueError("give it a name")
    if name in names(): raise ValueError(f"there's already an image model called {name}")
    os.makedirs(folder(name)); pictures_dir(name)
    trigger = re.sub(r"[aeiou\s]", "", name.lower())[:8] + "style"                       # a made-up word: vowels out, so it's unique
    _save(name, dict(name=name, focus=focus, description=description, trigger=trigger,
                     made=datetime.datetime.now().isoformat(timespec="seconds"), trained=None))
    return name

def rename(old, new):
    new = _safe(new)
    if not new or new in names(): raise ValueError("pick a new name that isn't used yet")
    os.rename(folder(old), folder(new)); d = info(new); d["name"] = new; _save(new, d)
    import prefs
    if prefs.get("image_model") == old: prefs.set("image_model", new)
    return new

def delete(name):
    shutil.rmtree(folder(name), ignore_errors=True)
    import prefs
    if prefs.get("image_model") == name: prefs.set("image_model", "")

def update(name, **kw): d = info(name); d.update(kw); _save(name, d)

def active():
    import prefs
    n = prefs.get("image_model") or ""; return n if n in names() else (names()[0] if names() else "")

def set_active(name):
    import prefs; prefs.set("image_model", name)

def pictures(name):
    """{label: number of pictures} for one image model"""
    out = {}; d = pictures_dir(name)
    for lab in sorted(os.listdir(d)):
        p = os.path.join(d, lab)
        if os.path.isdir(p): out[lab] = len([f for f in os.listdir(p) if f.lower().endswith(EXT)])
    return out
