"""
model_mixes.py: Model Mixes — a main picture model with add-on files (LoRAs) of your choice switched on with it, saved as a new main model
you pick like any other ("Z-Image Turbo / Tumblr"). A mix is kept until you delete it; templates still go on top of it.

    import model_mixes as MM
    MM.check("zimage", [path, ...])        -> [dict(path, base, ok, problem, note)]: can each file go with that main model?
    MM.create(name, "zimage", items)       items: [dict(path, weight, trigger)] -> the new mix's key 'mix:<name>'
    MM.mixes()                             {key: dict(name, base, addons=[dict(file, label, weight, trigger)])}
    MM.is_mix(key) / MM.base(key) / MM.name(key) / MM.ready(key)
    MM.bits(key)                           (text for the prompt, folder) the engine needs for the mix's add-ons
    MM.delete(key)

The add-on files are copied into the templates' folder (style_addons.folder()) under their own names, so the engine finds a mix's add-ons
and a template's in one folder and can switch them all on in one run.
"""
import os, re, json, shutil

PREFIX = "mix:"
MAX_ADDONS = 6                                                        # more than this and the picture is mostly add-ons
HEAVY = 2.4                                                           # add-on strengths adding up past this tend to spoil pictures
MAIN_MODELS = ("zimage", "klein", "sdxl", "sd15")                     # the picture models a mix can be made on


def _folder():
    import style_addons as SA
    return SA.folder()


def _file():
    import imaging
    return os.path.join(imaging.IMAGE, "model-mixes.json")


def mixes():
    try:
        with open(_file(), encoding="utf-8") as f: data = json.load(f)
        return {k: v for k, v in data.items() if str(k).startswith(PREFIX) and isinstance(v, dict)}
    except Exception: return {}


def _save(data):
    os.makedirs(os.path.dirname(_file()), exist_ok=True)
    tmp = _file() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(data, f, indent=1)
    os.replace(tmp, _file())


def is_mix(key): return isinstance(key, str) and key.startswith(PREFIX)
def get(key): return mixes().get(key) if is_mix(key) else None
def base(key): return (get(key) or {}).get("base", "")
def name(key): return (get(key) or {}).get("name", "")


def slug(text): return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "mix"


def ready(key):
    """the mix is saved and every one of its add-on files is still here"""
    m = get(key)
    return bool(m) and bool(m.get("addons")) and all(os.path.isfile(os.path.join(_folder(), a["file"])) for a in m["addons"])


def for_base(kind):
    """the keys of the mixes made on this main model, in name order"""
    return sorted((k for k, m in mixes().items() if m.get("base") == kind), key=lambda k: mixes()[k].get("name", "").lower())


def _is_addon_file(path):
    """(True, '') for a LoRA-type add-on; (False, why) for a whole model or a file that isn't a .safetensors"""
    import style_addons as SA
    try: h = SA._header(path)
    except Exception: return False, "it isn't a .safetensors file Pro can read"
    keys = " ".join(k for k in h if k != "__metadata__").lower()
    if any(t in keys for t in ("lora", "lokr", "hada_", ".alpha", "lora_a", "lora_b")): return True, ""
    if os.path.getsize(path) > 3e9: return False, "it's a whole picture model, not an add-on (add it in Settings > AI Models instead)"
    return False, "it doesn't look like an add-on (LoRA) file"


def check(main, paths):
    """can each file go with the main model? -> [dict(path, base, ok, problem, note)]; ok False = it can't be used in this mix"""
    import style_addons as SA
    out = []; seen = set()
    for p in paths:
        r = dict(path=p, base="", ok=False, problem="", note="")
        if not os.path.isfile(p): r["problem"] = "the file isn't there"; out.append(r); continue
        real = os.path.realpath(p)
        if real in seen: r["problem"] = "it's in the list twice"; out.append(r); continue
        seen.add(real)
        fits, why = _is_addon_file(p)
        if not fits: r["problem"] = why; out.append(r); continue
        b = SA.detect_base(p); r["base"] = b
        if b in SA.UNSUPPORTED: r["problem"] = f"it's made for {SA.UNSUPPORTED[b]}, which Pro doesn't run"
        elif b and b != main: r["problem"] = f"it's made for {SA.BASES.get(b, b)}, not {SA.BASES.get(main, main)}"
        else:
            r["ok"] = True
            if not b: r["note"] = "the file doesn't say which model it's for; it's tried, and left out of a picture if it doesn't fit"
        out.append(r)
    good = [r for r in out if r["ok"]]
    for r in good[MAX_ADDONS:]: r.update(ok=False, problem=f"a mix takes at most {MAX_ADDONS} add-ons")
    return out


def warnings(items):
    """what to say before a mix is made, besides the files that can't be used: e.g. strengths that add up too high"""
    total = sum(float(i.get("weight", 0.8)) for i in items)
    return [f"the strengths add up to {total:g}: past about {HEAVY:g} pictures tend to come out overdone (lower some of them)"] if total > HEAVY else []


def create(mix_name, main, items):
    """save a mix: items are dict(path, weight, trigger) that check() passed. -> its key. Raises ValueError with what's wrong"""
    import style_addons as SA
    mix_name = str(mix_name or "").strip()
    if main not in MAIN_MODELS: raise ValueError("pick the main model")
    if not mix_name: raise ValueError("give the mix a name")
    if not items: raise ValueError("add at least one add-on file")
    checked = check(main, [i["path"] for i in items])
    bad = [r for r in checked if not r["ok"]]
    if bad: raise ValueError(f"{os.path.basename(bad[0]['path'])}: {bad[0]['problem']}")
    key = PREFIX + slug(mix_name); data = mixes()
    if key in data: raise ValueError(f"there's already a mix called {data[key]['name']}")
    os.makedirs(_folder(), exist_ok=True)
    addons = []
    for n, i in enumerate(items, 1):
        stem = f"mix-{slug(mix_name)}-{n}"; dest = os.path.join(_folder(), stem + ".safetensors")
        shutil.copy2(i["path"], dest)
        addons.append(dict(file=stem + ".safetensors", label=os.path.splitext(os.path.basename(i["path"]))[0],
                           weight=round(max(0.0, min(1.5, float(i.get("weight", 0.8)))), 2), trigger=str(i.get("trigger", "")).strip()))
    data[key] = dict(name=f"{SA.BASES.get(main, main)} / {mix_name}", short=mix_name, base=main, addons=addons)
    _save(data); return key


def delete(key):
    """remove a mix and its copies of the add-on files (the files you picked are left where they were)"""
    data = mixes(); m = data.pop(key, None)
    if not m: return False
    for a in m.get("addons", []):
        try: os.remove(os.path.join(_folder(), a["file"]))
        except OSError: pass
    _save(data); return True


def bits(key):
    """(text for the prompt, folder): each add-on's trigger words and its <lora:...> tag; ('', None) when it isn't a ready mix"""
    m = get(key)
    if not m or not ready(key): return "", None
    text = ""
    for a in m["addons"]:
        stem = os.path.splitext(a["file"])[0]
        text += (f", {a['trigger']}" if a.get("trigger") else "") + f" <lora:{stem}:{float(a.get('weight', 0.8)):g}>"
    return text, _folder()


def place_in(key, folder):
    """the engine reads add-ons from one folder: when a picture's other add-on lives elsewhere, the mix's files are put there too"""
    m = get(key)
    if not m or os.path.normcase(os.path.abspath(folder)) == os.path.normcase(os.path.abspath(_folder())): return
    for a in m.get("addons", []):
        src, dest = os.path.join(_folder(), a["file"]), os.path.join(folder, a["file"])
        if os.path.isfile(dest) and os.path.getsize(dest) == os.path.getsize(src): continue
        try: os.link(src, dest)
        except OSError: shutil.copy2(src, dest)
