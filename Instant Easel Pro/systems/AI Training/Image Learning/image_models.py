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
    d = paths.ai("my-library", "Image models"); os.makedirs(d, exist_ok=True); return d

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


# ---------------------------------------------------------------- the things it learns (one per label): what each one is
KINDS = ["Character", "Creature / animal", "Person", "Object", "Vehicle", "Clothing", "Food", "Place / building", "Plant", "Style / look", "Other"]
FIELDS = [  # key, label, help (the same questions for anything you want it to learn)
    ("name", "Name", "What it's called, exactly: its full, proper name."),
    ("category", "Category", "The broad family it belongs to (a franchise, brand, product line, species...). Searched with its name."),
    ("subcategory", "Subcategory", "A narrower group inside the category (a type, a model range, a series, a generation...). Optional."),
    ("kind", "Kind of thing", "Character, creature, person, object, vehicle, food, place, style..."),
    ("what_it_is", "What it is", "A sentence or two: Look it up fills this in from Wikipedia or a dictionary."),
    ("looks", "What it looks like", "Colours, shape, size, parts and markings: the things that make it it. This matters most."),
    ("confused_with", "Often confused with", "Things that look similar, so it learns the difference."),
    ("search", "Extra search words", "Comma-separated, for the image search (official art, 3d model, side view). Its name is always searched."),
    ("notes", "Notes", "Anything else that helps: what to avoid in its pictures (toys, merchandise, fan art, text), its usual pose or setting."),
]


def _token(label):
    """its own word for training: its name squashed, plus a tag so it never clashes with an everyday word"""
    t = re.sub(r"[^a-z0-9]+", "", label.lower())[:16] or "thing"; return t + "_ie"


def subjects(name):
    """{label: profile} for every label (thing) of an image model, with the empty fields filled in"""
    d = info(name).get("subjects", {}); out = {}
    for lab in sorted(set(pictures(name)) | set(d)):
        p = dict(name=lab, category="", subcategory="", kind="", what_it_is="", looks="", confused_with="", search="", notes="", token=_token(lab))
        saved = dict(d.get(lab, {}))
        if "group" in saved and not saved.get("category"): saved["category"] = saved.pop("group")     # (earlier versions said 'group')
        p.update(saved); out[lab] = p
    return out


def set_subject(model, label, **fields):
    d = info(model); s = d.setdefault("subjects", {}); p = s.setdefault(label, {}); p.update({k: v for k, v in fields.items() if v is not None})
    p.setdefault("token", _token(label)); _save(model, d)


def add_subject(model, label, **fields):
    label = _safe(label)
    if not label: raise ValueError("give it a name")
    os.makedirs(os.path.join(pictures_dir(model), label), exist_ok=True); fields.setdefault("name", label); set_subject(model, label, **fields); return label


def remove_subject(name, label, delete_pictures=False):
    d = info(name); d.get("subjects", {}).pop(label, None); _save(name, d)
    if delete_pictures: shutil.rmtree(os.path.join(pictures_dir(name), label), ignore_errors=True)


def search_words(profile):
    """what the image search looks for: its name with its category (so a name that's also an everyday word finds the right thing), plus
    each extra search word"""
    base = " ".join(x for x in (profile.get("name", ""), profile.get("category", "")) if x).strip()
    out = [base] if base else []
    for w in (profile.get("search") or "").split(","):
        w = w.strip()
        if w: out.append(f"{base} {w}".strip())
    return list(dict.fromkeys(out))


def caption(name, label, profile=None):
    """the description written beside each of its pictures for training: its own word first, then what it is and how it looks"""
    p = profile or subjects(name).get(label, {}); i = info(name)
    bits = [p.get("token") or _token(label), p.get("name") or label]
    kind = (p.get("kind") or "").split("/")[0].strip().lower(); cat = p.get("category", "").strip(); sub = p.get("subcategory", "").strip()
    if kind or cat: bits.append(" ".join(x for x in (f"a {kind}" if kind else "", f"from {cat}" if cat else "", f"({sub})" if sub else "") if x))
    elif sub: bits.append(sub)
    if p.get("looks"): bits.append(p["looks"].strip().rstrip("."))
    if i.get("style_words"): bits.append(i["style_words"].strip())
    return ", ".join(b for b in bits if b)


def write_captions(name):
    """a .txt caption beside every picture (the way training tools read them). -> (pictures captioned, labels with no profile yet)"""
    n, missing = 0, []
    for lab, p in subjects(name).items():
        if not p.get("looks") and not p.get("what_it_is"): missing.append(lab)
        d = os.path.join(pictures_dir(name), lab); text = caption(name, lab, p)
        if not os.path.isdir(d): continue
        for f in os.listdir(d):
            if f.lower().endswith(EXT):
                with open(os.path.join(d, os.path.splitext(f)[0] + ".txt"), "w", encoding="utf-8") as fh: fh.write(text + "\n"); n += 1
    return n, missing
