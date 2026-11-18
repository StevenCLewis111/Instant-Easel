"""
models.py: trained models on a shared Core.
  my-models/<id>/model.json      name, focus, description, created, updated
  my-models/<id>/<subject>/      images waiting to be learned (deleted after learning, like the main library)
  my-models/<id>/profile.json    what this model learned (colours, textures, brushwork, light and dark)
  my-models/<id>/history/        a saved version after every training session (roll back any time)
  my-models/<id>/vocab.json      words only this model knows (on top of the Core's)
  core/label_corrections.json    the shared Core: every time you correct a guess, all models' future guesses improve
"""
import os, re, json, glob, shutil, datetime
import prefs

ROOT = os.path.join(prefs.home_dir(), "my-models")
CORE = os.path.join(prefs.home_dir(), "core")
FOCUS = ["Landscapes", "Faces", "Cartoons", "Animals", "Night scenes", "Architecture", "Custom"]
BUILTIN = ["Core (default)", "My learned style"]

def _now(): return datetime.datetime.now().isoformat(timespec="minutes")
def _slug(name): return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "model"
def path(mid): return os.path.join(ROOT, mid)

def list_models():
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, "*", "model.json"))):
        try: m = json.load(open(f)); m["id"] = os.path.basename(os.path.dirname(f)); out.append(m)
        except Exception: pass
    return sorted(out, key=lambda m: m.get("created", ""))

def names(): return [m["name"] for m in list_models()]
def find(name):
    for m in list_models():
        if m["name"] == name: return m
    return None

def _write(mid, meta): os.makedirs(path(mid), exist_ok=True); json.dump(meta, open(os.path.join(path(mid), "model.json"), "w"), indent=1)

def create(name, focus="Custom", description="", copy_from=None):
    name = name.strip()
    if not name: raise ValueError("Give the model a name.")
    if name in BUILTIN or find(name): raise ValueError(f"A model called '{name}' already exists.")
    mid = _slug(name); n = 2
    while os.path.exists(path(mid)): mid = f"{_slug(name)}-{n}"; n += 1
    if copy_from:                                                              # start from another model's learning and words
        src = find(copy_from)
        if src: shutil.copytree(path(src["id"]), path(mid), ignore=shutil.ignore_patterns("model.json"))
        elif copy_from == "My learned style":
            import app as classic
            for f in ("profile.json", "history"):
                s = os.path.join(classic.library_dir(), f)
                if os.path.isfile(s): os.makedirs(path(mid), exist_ok=True); shutil.copy(s, path(mid))
                elif os.path.isdir(s): shutil.copytree(s, os.path.join(path(mid), f))
    _write(mid, dict(name=name, focus=focus, description=description, created=_now(), updated=_now(), copied_from=copy_from or ""))
    return mid

def rename(old, new):
    m = find(old); new = new.strip()
    if not m: raise ValueError("Model not found.")
    if not new or new in BUILTIN or (find(new) and new != old): raise ValueError(f"'{new}' can't be used (empty or already taken).")
    meta = {k: v for k, v in m.items() if k != "id"}; meta.update(name=new, updated=_now()); _write(m["id"], meta)
    if prefs.get("active_model") == old: prefs.set("active_model", new)

def update(name, **kw):
    m = find(name)
    if m: meta = {k: v for k, v in m.items() if k != "id"}; meta.update(kw, updated=_now()); _write(m["id"], meta)

def delete(name):
    m = find(name)
    if m: shutil.rmtree(path(m["id"]), ignore_errors=True)
    if prefs.get("active_model") == name: prefs.set("active_model", "Core (default)")

def folder(name):
    """where a model's images, learning and words live (None for the plain Core)"""
    if name == "Core (default)": return None
    if name == "My learned style":
        import app as classic; return classic.library_dir()
    m = find(name); return path(m["id"]) if m else None

def profile_for(name):
    import learn
    f = folder(name); return learn.load(f) if f else None

def stats(name):
    import learn
    f = folder(name); prof = (learn.load(f) or {}) if f else {}
    learned = sum(v.get("images", 0) for v in prof.get("subjects", {}).values()) + int(prof.get("images", 0) if "per_image" in prof else 0)
    waiting = sum(learn.waiting(f).values()) if f else 0
    versions = len(glob.glob(os.path.join(f, "history", "*.json"))) if f else 0
    return dict(learned=learned, waiting=waiting, versions=versions, subjects={k: v.get("images", 0) for k, v in prof.get("subjects", {}).items()})

def versions(name):
    f = folder(name); return sorted(glob.glob(os.path.join(f, "history", "*.json")), reverse=True) if f else []

def rollback(name, version_file):
    f = folder(name)
    if f: shutil.copy(version_file, os.path.join(f, "profile.json")); update(name) if find(name) else None

# ---------------- the shared Core: corrections every model learns from
def _corr_file(): os.makedirs(CORE, exist_ok=True); return os.path.join(CORE, "label_corrections.json")

def record_correction(stats_vec, label):
    """the user changed a guessed label: remember the picture's measurements and the right answer (numbers only)"""
    f = _corr_file(); data = json.load(open(f)) if os.path.exists(f) else []
    data.append(dict(v=[round(float(x), 5) for x in stats_vec], label=label)); json.dump(data[-2000:], open(f, "w"))

def corrections():
    f = _corr_file()
    try: return json.load(open(f)) if os.path.exists(f) else []
    except Exception: return []
