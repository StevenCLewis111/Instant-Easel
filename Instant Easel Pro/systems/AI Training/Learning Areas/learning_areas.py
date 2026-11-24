"""
learning_areas.py: AI Training's learning areas. Each area (Image, Video, Chat, Coding) has its own menu of steps, laid out the way
good training is done: decide the goal, collect, clean, label, choose settings, train, then test. Every option has a status dot
(green: works, blue: started, grey: just a button for now) and one plain line saying why it matters.

What's here follows current best practice:
  - Pictures (image LoRA guides): 15-50 varied pictures beat many similar ones; every picture labelled consistently; a check
    that the captions are right; start with a short run, keep versions, and watch for it copying its pictures (over-training).
  - Video (Wan 2.2 / LTX guides): real short clips (3-8 s), not still pictures (those teach it not to move); captions describe
    the motion; memory grows with frames x size x batch, so start small; save checkpoints often.
  - Chat and coding (LLM fine-tuning guides): facts go in a library it looks things up in (fine-tuning doesn't store facts
    reliably); training teaches HOW to answer. Quality over quantity (100+ examples, 500+ better), duplicates removed, 1-3 passes,
    a held-back check set that stops training when it starts memorising.
  - Coding data (The Stack / BigCode): permissive licences only (MIT, Apache, BSD), exact and near duplicates removed, code that
    doesn't compile left out, secrets removed; test it by running its code.

The settings are kept in .json/learning_settings.json.
"""
import os, re, json, shutil, hashlib, threading, tkinter as tk
from tkinter import filedialog
import theme as T, prefs, paths, skin

DOT = None                                # main.py hands over its status-dot painter (the same dots as the side menu)
SETTINGS_FILE = paths.json_file("learning_settings.json")

# ---------------------------------------------------------------- saved settings
def _all():
    try: return json.load(open(SETTINGS_FILE, encoding="utf-8"))
    except Exception: return {}

def get(area, key, default=None):
    return _all().get(area, {}).get(key, default if default is not None else _default(area, key))

def put(area, key, value):
    d = _all(); d.setdefault(area, {})[key] = value
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE + ".tmp", "w", encoding="utf-8") as f: json.dump(d, f, indent=1)
    os.replace(SETTINGS_FILE + ".tmp", SETTINGS_FILE)

def _default(area, key):
    for _, opts in AREAS[area]["steps"]:
        for o in opts:
            if o.get("key") == key: return o.get("default")
    return None

def reset(area):
    d = _all(); d.pop(area, None)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f: json.dump(d, f, indent=1)

# ---------------------------------------------------------------- the areas
def B(label, status, why, action):                       # a button
    return dict(kind="button", label=label, status=status, why=why, action=action)
def C(label, status, why, key, values, default):         # a choice (click to step through, right-click back)
    return dict(kind="choice", label=label, status=status, why=why, key=key, values=values, default=default)
def S(label, status, why, key, default):                 # a switch
    return dict(kind="toggle", label=label, status=status, why=why, key=key, default=default)
def I(label, status, why, show):                         # a live line of information
    return dict(kind="info", label=label, status=status, why=why, show=show)

SPEEDS = ["Careful", "Normal", "Fast"]; LR = {"Careful": 1e-4, "Normal": 2e-4, "Fast": 3e-4}

def _text_steps(tab, code=False):
    """chat and coding learn the same way (examples -> a small add-on), with their own collecting and cleaning"""
    collect = [B("Teach an example", "built", "Write a question and the perfect answer. Each one shows it how you want it to answer.", "teach"),
               B("Import examples from a file", "built", "A .jsonl (text / answer) or .csv file (two columns: question, answer).", "import_examples"),
               I("Examples so far", "built", "Aim for 100 or more good examples; 500+ is better. A few great ones beat many sloppy ones.", "count")]
    if code:
        collect += [B("Add a code folder", "built", "Copies code files into the coding library after the checks in Clean; it looks things up "
                      "there when it answers.", "import_code")]
    else:
        collect += [B("Add documents to the library", "built", "Facts belong in a library it looks things up in, not in training. "
                      "It reads the parts that match your question before it answers.", "import_docs")]
    clean = [S("Remove duplicate examples", "built", "The same example twice makes it lean too hard on it. Duplicates count once when training.", "dedupe", True),
             B("Open the examples folder", "built", "Everything taught is in examples.jsonl, one per line, if you want to look or fix by hand.", "open_folder"),
             B("Review and fix examples", "planned", "A list of every example with edit and delete.", "planned")]
    if code:
        clean = [S("Only permissive licences", "built", "Keeps code from projects licensed MIT, Apache or BSD (others are left out), "
                   "so nothing it writes carries someone else's licence terms.", "permissive", True),
                 S("Skip exact duplicates", "built", "About half of public code is copies; copies teach it to parrot boilerplate.", "dedupe", True),
                 S("Skip Python that doesn't compile", "built", "Broken code teaches broken code.", "compiles", True),
                 B("Remove passwords and keys", "planned", "Finds things like API keys and passwords in code and blanks them out.", "planned")] + clean[1:]
    fmt = [C("Answer style", "built", "How long its answers should be.", "style", ["Short", "Normal", "Detailed"], "Normal")]
    if code:
        fmt = [C("Main language", "built", "The language it writes in unless you ask for another.", "language", ["Python", "JavaScript", "Any"], "Python"),
               S("Explain the code too", "built", "Answers come with a short explanation.", "explain", True)]
    settings = [I("How it learns right now", "built", "Your examples and library are used every time it answers. Training the model itself "
                  "needs a graphics card with 12 GB or more (or a rented one), so the settings below are saved for then.", "tip"),
                C("Passes over the examples", "planned", "1 to 3. More passes make it memorise your examples and forget other things.", "epochs", ["1", "2", "3"], "2"),
                C("Learning speed", "planned", "Careful learns slower and safer; Fast can wreck what it knew. Normal suits most.", "speed", SPEEDS, "Normal"),
                C("Add-on size", "planned", "How much the small add-on can hold. 8 or 16 for a few hundred examples.", "rank", ["8", "16", "32"], "8"),
                S("Hold back 10% to check it", "planned", "Those examples are never trained on; they show whether it learned or just memorised. "
                  "Training stops once the check gets worse. Needs 10+ examples.", "holdout", True)]
    train = [I("What it knows", "built", "Examples it follows and library files it looks things up in.", "knows"),
             B(f"Train {tab}", "planned", "Bakes the examples into this area's own add-on. Needs a 12 GB+ graphics card (or a rented one).", "planned"),
             B(f"Forget everything {tab} learned", "built", "Clears this area's examples and add-on. The base model and other areas are untouched.", "forget")]
    test = [B("Ask it something", "built", "Try questions that are NOT in your examples. That's the real test.", "ask")]
    test += ([B("Run its code against tests", "planned", "Write a test, let it write the code, and run them together.", "planned")] if code else
             [S("Use the library when answering", "built", "Looks up your documents first, then answers from them.", "use_library", True)])
    goal = ([C("What should it get better at?", "built", "Writing code your way is training; knowing a library's details is the library.",
               "goal", ["Write code my way", "Explain code", "Fix bugs"], "Write code my way")] if code else
            [C("What should it get better at?", "built", "Knowing facts: use the library. Answering your way (tone, format, steps): train it.",
               "goal", ["Answering my way", "Knowing my stuff", "Both"], "Answering my way")])
    return [("Goal", goal), ("Collect", collect), ("Clean", clean), ("Format", fmt), ("Settings", settings), ("Train", train), ("Test", test)]

AREAS = {
 "Image Learning": dict(tab="AI Images", intro="Each image model learns from its own pictures: a set of things (one category of characters, products, vehicles...) or a look. Pick or make one at the top.",
  steps=[
   ("Goal", [C("What is this image model for?", "built", "Saved with the model. A focused model (only cartoons, only shoes) learns faster and better.",
               "focus", ["Cartoons", "Fashion", "Nature", "Portraits", "Animals", "Products", "Architecture", "Anything"], "Anything"),
             I("Image model it trains on top of", "built", "Chosen in Settings > AI Models. Train add-ons for Z-Image Turbo (on a rented graphics card) so they work as Templates.", "base")]),
   ("Collect", [B("The things it learns", "built", "One entry per thing: its name, category, subcategory and what it looks like. Look it up fills them in; Search finds its pictures.", "subjects"),
                B("Search Google Images", "built", "Type the word; every picture found is labelled with that word.", "scraper"),
                B("Add my own pictures", "built", "Your own photos or art. Your files are never changed or moved.", "add_pictures"),
                C("Pictures per word", "built", "15 to 50 varied pictures is the sweet spot. Under about 15 it copies them; past 100 it hardly helps.",
                  "per_word", ["10", "20", "30", "50"], "20")]),
   ("Clean", [B("Review the pictures", "built", "Untick anything wrong: one bad picture teaches the wrong thing.", "review"),
              S("Skip duplicate pictures", "built", "The same picture twice makes it copy that picture.", "dedupe", True),
              S("Skip tiny pictures", "built", "Pictures under 256 pixels are left out: too small to show any detail.", "skip_small", True),
              S("Square-crop around the middle", "planned", "Same framing on every picture keeps it learning the subject, not the edges.", "crop", False)]),
   ("Label", [I("Search word = label", "built", "Pictures from a search are labelled with the word you searched. Change any label in the review.", "label_note"),
              B("Its style words", "built", "A few words for the look (e.g. 'bold black outlines, flat pastel colours, rounded shapes'). They go into every picture painted with it.", "style_words"),
              B("Choose its reference pictures", "built", "Up to 4 of its best pictures. With FLUX.2 Klein they guide the look of every picture painted with it (no training needed).", "pick_refs"),
              I("Trigger word", "built", "A made-up word for this model, used the same way on every picture. Type it in a request to switch the model on.", "trigger"),
              B("Write the captions", "built", "A description beside every picture, from its thing's details (its own word, name, group, looks). Training learns from these.", "captions")]),
   ("Settings", [S("Keep copies after training", "built", "Off: the app's copies are deleted after training. Your originals are never touched.", "keep", False),
                 C("Strength", "planned", "How strongly it learns (the add-on's size). Too strong and everything looks like your pictures.",
                   "strength", ["Gentle", "Normal", "Strong"], "Normal"),
                 C("Training length", "planned", "About 100 steps per picture; start with a short test and check before a long run.",
                   "length", ["Short test", "Normal", "Long"], "Normal")]),
   ("Train", [I("Pictures ready", "built", "Pictures in this model, per label.", "waiting"),
              I("Works now, without training", "built", "Pick it as a STYLE in any AI Images section: its style words and reference pictures guide the look (FLUX.2 Klein).", "works_now"),
              B("Train this image model", "planned", "Training its own add-on (a LoRA) on this PC needs a GPU training kit that isn't built in yet. A LoRA trained elsewhere works below.", "planned"),
              B("Add a trained add-on you already have", "built", "A LoRA file (.safetensors) made for Stable Diffusion 1.5: this model uses it straight away.", "add_lora")]),
   ("Test", [B("Make a test picture", "built", "Opens Text to Image with this model as the style. Try the same request with style None to compare.", "try_model"),
             B("Roll back to an earlier version", "planned", "Every training saves a version; go back if a new one made it worse.", "planned")]),
  ]),
 "Video Learning": dict(tab="AI Videos", intro="Teaches movement: how things move, a look, or a character, from short video clips.",
  warn="Training a video model needs a graphics card with 16 GB or more (or a rented one online). Your settings are saved now so it's ready.",
  steps=[
   ("Goal", [C("What are you teaching?", "partial", "Motion (how something moves), a style, or a character. Saved now.",
               "goal", ["Motion", "A style", "A character"], "Motion")]),
   ("Collect", [B("Add video clips", "partial", "Kept in the video library now; nothing learns from them yet. 10 to 30 short clips is a good start.", "add_clips"),
                C("Clip length", "partial", "Short clips, 3 to 5 seconds. Saved now.", "clip_len", ["2-3 s", "3-5 s", "5-8 s"], "3-5 s"),
                I("Use real clips", "built", "Still pictures alone teach it NOT to move. Mix in pictures only for looks, never only pictures.", "tip")]),
   ("Clean", [S("Cut long videos into scenes", "planned", "Splits a long video at each cut so every clip is one scene.", "scenes", True),
              S("Skip near-duplicate clips", "planned", "Many clips of the same moment make it repeat that moment.", "dedupe", True),
              S("Skip blurry or shaky clips", "planned", "It learns the blur and shake too.", "blur", True)]),
   ("Label", [S("Describe the motion", "planned", "Captions should say what moves and how (\"waves roll in slowly\"), not just what's there.", "captions", True),
              C("Trigger word", "planned", "A made-up word used on every clip that switches on what it learned.", "trigger", ["none", "use a word"], "none")]),
   ("Settings", [C("Frames per clip", "planned", "More frames = longer motion but much more memory.", "frames", ["17", "33", "49", "81"], "33"),
                 C("Size", "planned", "Smaller sizes fit more frames. Start small, prove it works, then grow.", "size", ["256", "384", "512"], "384"),
                 I("Memory", "built", "Memory used grows with frames x size x clips at once. Run out? Lower one of them.", "tip")]),
   ("Train", [B("Train", "planned", "Needs a video model and a graphics card with 16 GB+.", "planned"),
              S("Save checkpoints often", "planned", "Lets you pick the best point instead of the last one.", "checkpoints", True)]),
   ("Test", [B("Make a test clip", "planned", "A short clip with what it learned, to check the motion.", "planned")]),
  ]),
 "Chat Learning": dict(tab="AI Chat", intro="Teaches it how to answer you. Facts go in the library; how to answer is what training changes.",
                       steps=_text_steps("AI Chat")),
 "Coding Learning": dict(tab="AI Coding", intro="Teaches it to write and explain code your way, from clean, permitted code and your own examples.",
                         steps=_text_steps("AI Coding", code=True)),
}

PERMISSIVE = ("mit license", "permission is hereby granted, free of charge", "apache license", "bsd 2-clause", "bsd 3-clause",
              "redistribution and use in source and binary forms", "isc license", "the unlicense", "this is free and unencumbered software")
CODE_EXT = (".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rs", ".rb", ".php", ".html", ".css", ".sh")

def licence_ok(folder):
    """True if the folder (or one above it, up to 3 levels) has a permissive licence file"""
    d = folder
    for _ in range(4):
        for name in ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING", "LICENCE", "license", "License.txt"):
            p = os.path.join(d, name)
            if os.path.isfile(p):
                try: text = open(p, encoding="utf-8", errors="ignore").read(4000).lower()
                except OSError: continue
                return any(k in text for k in PERMISSIVE)
        up = os.path.dirname(d)
        if up == d: break
        d = up
    return False

def import_code(src, dst, permissive=True, dedupe=True, compiles=True):
    """copy code files from src into dst with the Clean checks. -> dict of counts"""
    os.makedirs(dst, exist_ok=True); n = dict(copied=0, licence=0, duplicate=0, broken=0)
    if permissive and not licence_ok(src):
        n["licence"] = sum(1 for _, _, fs in os.walk(src) for f in fs if f.lower().endswith(CODE_EXT)); return n
    seen = set()
    for f in os.listdir(dst):
        try: seen.add(hashlib.md5(open(os.path.join(dst, f), "rb").read()).hexdigest())
        except OSError: pass
    for d, dirs, fs in os.walk(src):
        dirs[:] = [x for x in dirs if not x.startswith(".") and x not in ("node_modules", "__pycache__", "venv", ".venv")]
        for f in fs:
            if not f.lower().endswith(CODE_EXT): continue
            p = os.path.join(d, f)
            try: data = open(p, "rb").read()
            except OSError: continue
            h = hashlib.md5(data).hexdigest()
            if dedupe and h in seen: n["duplicate"] += 1; continue
            if compiles and f.endswith(".py"):
                try: compile(data, p, "exec")
                except Exception: n["broken"] += 1; continue
            seen.add(h); rel = os.path.relpath(p, src).replace(os.sep, "__")
            shutil.copy(p, os.path.join(dst, rel)); n["copied"] += 1
    return n

def read_examples(path):
    """examples from a .jsonl (text/answer, prompt/response, question/answer, instruction/output) or a 2-column .csv"""
    out = []
    if path.lower().endswith(".csv"):
        import csv
        for row in csv.reader(open(path, encoding="utf-8", errors="ignore")):
            if len(row) >= 2 and row[0].strip() and row[1].strip() and row[0].strip().lower() not in ("question", "text", "prompt"):
                out.append((row[0].strip(), row[1].strip()))
        return out
    for line in open(path, encoding="utf-8", errors="ignore"):
        try: d = json.loads(line)
        except Exception: continue
        q = next((d[k] for k in ("text", "prompt", "question", "instruction", "input") if d.get(k)), None)
        a = next((d[k] for k in ("answer", "response", "output", "completion") if d.get(k)), None)
        if q and a: out.append((str(q), a if isinstance(a, dict) else str(a)))
    return out

# ---------------------------------------------------------------- the page
def fits(app, tab, files=(), folder=None):
    """True if these files (or this folder) fit in the AI's portion on the AI drive; otherwise says so and returns False"""
    import storage
    size = sum(os.path.getsize(f) for f in files if os.path.isfile(f))
    if folder:
        for d, _, fs in os.walk(folder):
            for f in fs:
                try: size += os.path.getsize(os.path.join(d, f))
                except OSError: pass
    ok, msg = storage.room(storage.area_for(tab), size)
    if not ok: T.banner(app, "NO ROOM — " + msg)
    return ok

def _frame(parent):
    f = tk.Frame(parent, bg=parent["bg"]); T.on_change(lambda: f.configure(bg=f.master["bg"])); return f

class AreaPage(tk.Frame):
    """one learning area: its steps along the top, the selected step's options below (dot, name, control, why)"""
    AREA = ""
    def __init__(self, master, app):
        super().__init__(master, bg=master["bg"]); self.app = app; T.on_change(lambda: self.configure(bg=self.master["bg"]))
        a = self.spec = AREAS[self.AREA]; self.tab = a["tab"]; self.infos = []
        T.Title(self, self.AREA).pack(pady=(0, 4))
        T.Text(self, a["intro"], muted=True).pack()
        if a.get("warn"): T.Text(self, a["warn"], font=T.f(9)).pack(pady=(4, 0))
        self.top_bar()
        bar = _frame(self); bar.pack(pady=(10, 6)); self.step_buttons = {}
        for i, (name, _) in enumerate(a["steps"]):
            b = skin.button(T.Button(bar, f"{i + 1} {name}", lambda n=name: self.show(n), width=11)); b.pack(side="left", padx=3); self.step_buttons[name] = b
        box = T.ScrollBox(self); box.pack(fill="both", expand=True, pady=(6, 0))
        cv = self.cv = tk.Canvas(box.body, bg=self["bg"], highlightthickness=0); self.inner = tk.Frame(cv, bg=self["bg"])
        T.on_change(lambda: (cv.configure(bg=self["bg"]), self.inner.configure(bg=self["bg"])))
        self.inner.bind("<Configure>", lambda e: T.fit_scrollregion(cv)); cv.create_window((0, 0), window=self.inner, anchor="nw")
        box.attach(cv); cv.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=10)
        low = _frame(self); low.pack(pady=(8, 0))
        T.Button(low, "Use best-practice settings", self.best, width=26).pack(side="left", padx=6)
        skin.file_button(T.Button(low, "Open this area's folder", lambda: prefs.open_folder(self.folder()))).pack(side="left", padx=6)
        self.show(a["steps"][0][0])

    def top_bar(self): pass                                                     # Image Learning: which image model

    # ---- drawing
    def show(self, step):
        self.step = step
        for n, b in self.step_buttons.items(): skin.select(b, n == step)
        for w in self.inner.winfo_children(): w.destroy()
        self.infos = []; opts = dict(self.spec["steps"])[step]
        for o in opts:
            r = _frame(self.inner); r.pack(fill="x", anchor="w", pady=(8, 0))
            if DOT is not None: DOT(r, o["status"], 14).pack(side="left", padx=(0, 8))
            T.Text(r, o["label"].upper(), font=T.f(10), width=34, anchor="w").pack(side="left")
            if o["kind"] == "button":
                ob = T.Button(r, "Open" if o["status"] != "planned" else "Coming", lambda o=o: self.run(o), width=10, kind="normal")
                skin.file_button(ob, height=28).pack(side="left", padx=(8, 0))
            elif o["kind"] == "choice":
                v = tk.StringVar(value=str(self.choice_value(o))); T.Choice(r, "", o["values"], v).pack(side="left", padx=(8, 0))
                v.trace_add("write", lambda *x, o=o, v=v: self.set_choice(o, v.get()))
            elif o["kind"] == "toggle":
                v = tk.BooleanVar(value=bool(self.toggle_value(o))); T.Toggle(r, v, command=lambda o=o, v=v: self.set_toggle(o, v.get())).pack(side="left", padx=(8, 0))
            elif o["kind"] == "info":
                lab = T.Text(r, "", font=T.f(10)); lab.pack(side="left", padx=(8, 0)); self.infos.append((lab, o["show"]))
            n = T.Text(self.inner, o["why"], muted=True, font=T.f(9), anchor="w"); n.configure(wraplength=900)
            n.pack(fill="x", anchor="w", padx=(30, 0), pady=(2, 4))
        self.cv.yview_moveto(0); self.refresh()

    def refresh(self):
        for lab, what in self.infos:
            try: lab.configure(text=self.info_text(what))
            except Exception as e: lab.configure(text=f"({e})")

    def choice_value(self, o): return get(self.AREA, o["key"])
    def set_choice(self, o, v): put(self.AREA, o["key"], v)

    def toggle_value(self, o):
        if o["key"] == "keep": return prefs.get("keep_training_copies")
        return get(self.AREA, o["key"])

    def set_toggle(self, o, on):
        if o["key"] == "keep": prefs.set("keep_training_copies", on)
        put(self.AREA, o["key"], on)

    def best(self):
        reset(self.AREA)
        if self.AREA == "Image Learning": prefs.set("keep_training_copies", False)
        self.show(self.step); T.banner(self.app, f"BEST-PRACTICE SETTINGS — {self.AREA} is back to the recommended settings", "success")

    # ---- where things live
    def folder(self):
        if self.AREA == "Video Learning": d = paths.ai("my-library", "Video clips"); os.makedirs(d, exist_ok=True); return d
        import brain; return brain._tab_dir(self.tab)

    def library(self):
        import brain; return brain.library_dir(self.tab)

    def info_text(self, what):
        if what in ("tip",): return ""
        if what in ("label_note", "always"): return "ALWAYS ON"
        import brain
        if what == "count":
            n = len(brain.examples(self.tab)); return f"{n}  " + ("(a good start)" if n >= 100 else "(aim for 100+)")
        if what == "knows":
            i = brain.info(self.tab); return f"{i['examples']} examples, {i['library']} library files"
        return ""

    # ---- what the buttons do
    def run(self, o):
        a = o["action"]
        if a == "planned": return T.banner(self.app, f"COMING — {o['label']} is planned; the button is here so you can see where it goes")
        try: getattr(self, "do_" + a)()
        except Exception as e:
            prefs.log_error(type(e), e, e.__traceback__); T.banner(self.app, f"COULDN'T DO THAT — {o['label']}: {e}")
        self.refresh()

    def goto(self, page): self.app.goto("AI Training", page)
    def do_open_folder(self): prefs.open_folder(self.folder())

    def do_add_clips(self):
        ps = filedialog.askopenfilenames(parent=self.app, title="Choose short video clips", initialdir=prefs.work_folder("Videos"),
                                         filetypes=[("Videos", "*.mp4 *.mov *.webm *.mkv *.avi"), ("All files", "*.*")])
        if ps and not fits(self.app, "AI Videos", ps): return
        for p in ps: shutil.copy(p, self.folder())
        if ps: T.banner(self.app, f"ADDED — {len(ps)} clips are in the video library", "success")

    def do_import_docs(self):
        ps = filedialog.askopenfilenames(parent=self.app, title="Choose documents for the library",
                                         filetypes=[("Documents", "*.txt *.md *.pdf *.html *.csv *.json"), ("All files", "*.*")])
        if ps and not fits(self.app, self.tab, ps): return
        for p in ps: shutil.copy(p, self.library())
        if ps: T.banner(self.app, f"ADDED — {len(ps)} documents are in the {self.tab} library", "success")

    def do_import_code(self):
        src = filedialog.askdirectory(parent=self.app, title="Choose a folder of code", initialdir=prefs.work_folder("Code"))
        if not src: return
        if not fits(self.app, self.tab, folder=src): return
        g = lambda k, d: get(self.AREA, k, d)
        n = import_code(src, self.library(), permissive=g("permissive", True), dedupe=g("dedupe", True), compiles=g("compiles", True))
        if n["licence"] and not n["copied"]:
            return T.banner(self.app, "LEFT OUT — that folder has no MIT, Apache or BSD licence file (switch off 'Only permissive licences' in Clean to take it anyway)")
        T.banner(self.app, f"ADDED — {n['copied']} code files ({n['duplicate']} duplicates and {n['broken']} broken files left out)", "success")

    def do_import_examples(self):
        p = filedialog.askopenfilename(parent=self.app, title="Choose a file of examples", filetypes=[("Examples", "*.jsonl *.csv"), ("All files", "*.*")])
        if not p: return
        import brain; ex = read_examples(p)
        for q, a in ex: brain.teach(self.tab, q, a, source=os.path.basename(p))
        T.banner(self.app, f"IMPORTED — {len(ex)} examples from {os.path.basename(p)}" if ex else "NOTHING IMPORTED — no question/answer pairs found in that file",
                 "success" if ex else "error")

    def do_teach(self):
        d = Dialog(self.app, f"Teach {self.tab}", "What you'd ask", "The perfect answer")
        if d.result:
            import brain; brain.teach(self.tab, d.result[0], d.result[1]); self.refresh()
            T.banner(self.app, f"TAUGHT — {self.tab} now has {len(brain.examples(self.tab))} examples", "success")

    def do_forget(self):
        if T.popup(self.app, f"FORGET {self.tab.upper()}?", "Every example and the trained add-on for this area are deleted.",
                   (("Forget", "danger"), ("Cancel", "normal"))) != "Forget": return
        import brain; brain.forget(self.tab); T.banner(self.app, f"FORGOTTEN — {self.tab}", "success")

    def do_ask(self):
        d = Dialog(self.app, f"Ask {self.tab}", "Your question", None)
        if not d.result: return
        import brain; q = self.app.q; question = d.result[0]; g = lambda k: get(self.AREA, k)
        style = {"Short": " Keep the answer short.", "Detailed": " Give a detailed answer."}.get(g("style") or "", "")
        if self.tab == "AI Coding":
            style += (f" Write {g('language')} unless the question asks for another language." if g("language") not in (None, "Any") else "")
            style += " Explain the code briefly after it." if g("explain") else " Just the code, no explanation."
        system = brain.SYSTEMS.get(self.tab, brain.CHAT_SYSTEM) + style; lib = bool(g("use_library")) if self.tab == "AI Chat" else True
        import jobs
        key = f"{self.tab}/ask"
        if jobs.busy(key): return T.banner(self.app, f"BUSY — your last question is {jobs.where(jobs.busy(key))}", "busy")
        j = jobs.submit(self.tab, f"Ask: {question[:40]}", lambda job: brain.ask(self.tab, question, system=system, use_library=lib), kind="text", page=key,
                        engine=brain.tab_model(self.tab), on_done=lambda ans: q.put(lambda: Answer(self.app, question, ans, self.tab)),
                        on_error=lambda e: q.put(lambda e=e: T.banner(self.app, f"COULDN'T ANSWER — {e}")))
        T.banner(self.app, "THINKING — the first answer takes longer while the model loads" if j.place() == 1 and not jobs.running()
                 else f"QUEUED — your question is {jobs.where(j)}; it's answered as soon as the AI is free", "success" if j.place() == 1 else "busy")

class Dialog(tk.Toplevel):
    """a question box (and an answer box when b is given). .result = (a, b) or None"""
    def __init__(self, app, title, a, b, default=""):
        super().__init__(app); self.result = None; self.title(title); self.configure(bg=T.PALETTE["bg"]); self.transient(app)
        p = T.Panel(self, pad=14); p.pack(fill="both", expand=True, padx=8, pady=8); T.Title(p, title).pack(pady=(0, 8)); self.boxes = []
        for label in (a, b):
            if label is None: continue
            T.Text(p, label.upper()).pack(anchor="w")
            t = T.Field(p, height=5 if b else 3, scroll=True, width=60); t.configure(font=T.f(10))
            t.pack(fill="both", expand=True, pady=(2, 8)); self.boxes.append(t)
            if default and len(self.boxes) == 1: t.insert("1.0", default)
        r = tk.Frame(p, bg=p["bg"]); r.pack()
        T.Button(r, "OK", self.ok).pack(side="left", padx=6); T.Button(r, "Cancel", self.destroy, kind="danger").pack(side="left")
        self.boxes[0].focus_set(); self.grab_set(); app.wait_window(self)
    def ok(self):
        vals = [t.get("1.0", "end").strip() for t in self.boxes]
        if all(vals): self.result = tuple(vals) + ((None,) if len(vals) == 1 else ())
        self.destroy()

CODE_EXT = {"python": ".py", "py": ".py", "javascript": ".js", "js": ".js", "typescript": ".ts", "html": ".html", "css": ".css",
            "java": ".java", "c": ".c", "cpp": ".cpp", "c++": ".cpp", "csharp": ".cs", "cs": ".cs", "go": ".go", "rust": ".rs", "bash": ".sh", "sh": ".sh"}

def save_answer(tab, question, answer):
    """a chat goes into Chats (question and answer); code goes into Code (each code block as its own file, the full answer beside it)"""
    import re
    if tab == "AI Coding":
        blocks = re.findall(r"```([A-Za-z+#]*)\n(.*?)```", answer, re.S); out = []
        for i, (lang, code) in enumerate(blocks):
            out.append(prefs.new_text("Code", code, question + (f"-{i + 1}" if len(blocks) > 1 else ""), CODE_EXT.get(lang.lower(), ".txt")))
        if not out: out.append(prefs.new_text("Code", answer, question, ".md"))
        return out
    return [prefs.new_text("Chats", f"# {question}\n\n{answer}\n", question, ".md")]

class Answer(tk.Toplevel):
    def __init__(self, app, question, answer, tab="AI Chat"):
        super().__init__(app); self.title("Its answer"); self.configure(bg=T.PALETTE["bg"]); self.transient(app)
        p = T.Panel(self, pad=14); p.pack(fill="both", expand=True, padx=8, pady=8)
        T.Text(p, question, muted=True, wraplength=600).pack(anchor="w", pady=(0, 8))
        T.Text(p, answer, wraplength=600).pack(anchor="w")
        r = tk.Frame(p, bg=p["bg"]); r.pack(pady=(12, 0)); where = "Code" if tab == "AI Coding" else "Chats"
        def save():
            paths_ = save_answer(tab, question, answer)
            T.banner(app, f"SAVED — {', '.join(os.path.basename(x) for x in paths_)} in your {where} folder", "success")
        skin.file_button(T.Button(r, f"Save to {where}", save)).pack(side="left", padx=6); T.Button(r, "Close", self.destroy, kind="danger").pack(side="left")

class ImageAreaPage(AreaPage):
    """Image Learning: the same steps, for the image model picked in the bar at the top"""
    AREA = "Image Learning"
    def top_bar(self):
        import image_models as IM; self.IM = IM
        r = _frame(self); r.pack(pady=(8, 0))
        T.Text(r, "TRAINING:", font=T.f(11)).pack(side="left", padx=(0, 8))
        self.model_v = tk.StringVar(value=IM.active() or "—"); self.model_choice = T.Choice(r, "", IM.names() or ["—"], self.model_v); self.model_choice.pack(side="left")
        self.model_v.trace_add("write", lambda *a: (self.model_v.get() in IM.names() and IM.set_active(self.model_v.get()), self.show(self.step)))
        for text, cmd, kind in (("+ New image model", self.new_model, "normal"), ("Rename", self.rename_model, "normal"), ("Delete", self.delete_model, "danger")):
            T.Button(r, text, cmd, kind=kind).pack(side="left", padx=(8, 0))
    def _models_changed(self, pick=None):
        names = self.IM.names(); self.model_choice.choices = names or ["—"]; self.model_v.set(pick if pick in names else (self.IM.active() or "—"))
    def new_model(self):
        d = Dialog(self.app, "New image model", "Its name (e.g. Cartoon, Fashion, Nature)", None)
        if not d.result: return
        try: n = self.IM.create(d.result[0].strip()); self.IM.set_active(n); self._models_changed(n)
        except ValueError as e: return T.banner(self.app, f"CAN'T MAKE IT — {e}")
        T.banner(self.app, f"MADE — {n} is the image model being trained", "success")
    def rename_model(self):
        cur = self.IM.active()
        if not cur: return T.banner(self.app, "NO IMAGE MODEL YET — make one with + New image model")
        d = Dialog(self.app, f"Rename {cur}", "New name", None)
        if not d.result: return
        try: n = self.IM.rename(cur, d.result[0].strip()); self._models_changed(n)
        except ValueError as e: T.banner(self.app, f"CAN'T RENAME — {e}")
    def delete_model(self):
        cur = self.IM.active()
        if not cur: return
        if T.popup(self.app, f"DELETE {cur.upper()}?", "Its pictures and anything it learned are deleted. Other image models are untouched.",
                   (("Delete", "danger"), ("Cancel", "normal"))) == "Delete":
            self.IM.delete(cur); self._models_changed(); T.banner(self.app, f"DELETED — {cur}", "success")
    def need_model(self):
        n = self.IM.active()
        if not n: T.banner(self.app, "MAKE AN IMAGE MODEL FIRST — press + New image model (e.g. Cartoon, Fashion, Nature)")
        return n
    def folder(self):
        n = self.IM.active(); return self.IM.folder(n) if n else self.IM.root()
    def choice_value(self, o):
        if o["key"] == "focus": return self.IM.info(self.IM.active()).get("focus", "Anything") if self.IM.active() else "Anything"
        return super().choice_value(o)
    def set_choice(self, o, v):
        if o["key"] == "focus" and self.IM.active(): self.IM.update(self.IM.active(), focus=v)
        else: super().set_choice(o, v)
    def info_text(self, what):
        n = self.IM.active()
        if what == "base":
            import catalog, imaging; e = catalog.entry("AI Images", imaging.choice()); return e["label"] if e else "Your own model file"
        if what == "trigger": return self.IM.info(n).get("trigger", "") if n else "(make an image model first)"
        if what == "works_now":
            if not n: return "(make an image model first)"
            import imaging; i = self.IM.info(n); refs = len([p for p in i.get("references", []) if os.path.exists(p)])
            return (f"style words: {'yes' if i.get('style_words') else 'not yet'}   reference pictures: {refs or 'picked for you'}   "
                    f"FLUX.2 Klein: {'downloaded' if imaging.have('klein') else 'not downloaded (words only until then)'}")
        if what == "waiting":
            if not n: return "(make an image model first)"
            w = self.IM.pictures(n); return "   ".join(f"{k}: {v}" for k, v in w.items()) or "no pictures yet"
        return super().info_text(what)
    def pictures(self): return self.app.pages["AI Training"].pages["Pictures"]
    def do_add_lora(self):
        n = self.need_model()
        if not n: return
        p = filedialog.askopenfilename(parent=self.app, title="Choose a LoRA file", filetypes=[("LoRA", "*.safetensors"), ("All files", "*.*")])
        if not p: return
        d = os.path.join(self.IM.folder(n), "lora"); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
        shutil.copy(p, os.path.join(d, re.sub(r"[^A-Za-z0-9_-]+", "_", n) + ".safetensors"))
        T.banner(self.app, f"ADDED — {n} now uses {os.path.basename(p)}", "success")
    def do_try_model(self):
        n = self.need_model()
        if not n: return
        import styles
        self.app.goto("AI Images", "Text to Image"); pg = self.app.pages["AI Images"].pages["Text to Image"]; pg.refresh(); pg.style.set(styles.YOURS + n)
    def do_style_words(self):
        n = self.need_model()
        if not n: return
        d = Dialog(self.app, f"{n}: its style words", "What it should look like (e.g. bold black outlines, flat pastel colours)", None)
        if d.result: self.IM.update(n, style_words=d.result[0].strip()); T.banner(self.app, "SAVED — they go into every picture painted with it", "success"); self.show(self.step)
    def do_pick_refs(self):
        n = self.need_model()
        if not n: return
        ps = filedialog.askopenfilenames(parent=self.app, initialdir=self.IM.pictures_dir(n), title=f"Up to 4 of {n}'s best pictures",
                                         filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp")])
        if not ps: return
        self.IM.update(n, references=list(ps)[:4]); T.banner(self.app, f"CHOSEN — {min(4, len(ps))} reference pictures for {n}", "success"); self.show(self.step)
    def do_scraper(self):
        if self.need_model(): self.goto("Image Scraper")
    def do_subjects(self):
        if self.need_model(): self.goto("Things to learn")
    def do_captions(self):
        n = self.need_model()
        if not n: return
        done, missing = self.IM.write_captions(n)
        if not done: return T.banner(self.app, f"NO PICTURES YET IN {n.upper()} — collect some first")
        T.banner(self.app, f"CAPTIONED {done} PICTURES" + (f" — still no description for: {', '.join(missing[:5])}{'…' if len(missing) > 5 else ''} (Things to learn)" if missing else ""), "success" if not missing else "busy")
    def do_review(self):
        if self.need_model(): self.goto("Pictures")
    def do_add_pictures(self):
        if self.need_model(): self.goto("Pictures"); self.pictures().add_images()

class PicturesPage(tk.Frame):
    """the active image model's pictures, and the 'what does each picture show?' review they come in through"""
    def __init__(self, master, app):
        super().__init__(master, bg=master["bg"]); self.app = app; T.on_change(lambda: self.configure(bg=self.master["bg"]))
        import image_models as IM; self.IM = IM; self.review_view = None
        home = self.home = _frame(self); home.pack(fill="both", expand=True)
        self.title = T.Title(home, "Pictures"); self.title.pack(pady=(0, 8))
        T.Text(home, "The pictures this image model learns from, one folder per label (the word you searched).\n"
                     "Add more, or search Google Images; every new picture goes through a quick review first.", muted=True).pack(pady=(0, 10))
        r = _frame(home); r.pack(pady=6)
        T.Button(r, "Search Google Images", lambda: app.goto("AI Training", "Image Scraper"), width=22).pack(side="left", padx=6)
        T.Button(r, "Add my own pictures", self.add_images, width=22).pack(side="left", padx=6)
        skin.file_button(T.Button(r, "Open the folder", lambda: self.IM.active() and prefs.open_folder(self.IM.pictures_dir(self.IM.active())))).pack(side="left", padx=6)
        T.Button(r, "Back to Image Learning", lambda: app.goto("AI Training", "Image Learning"), width=24).pack(side="left", padx=6)
        self.info = T.Text(home, "", font=T.f(11)); self.info.pack(pady=16)
        self.bind("<Map>", lambda e: self.refresh(), add="+"); self.refresh()

    def refresh(self):
        n = self.IM.active()
        if not n: self.title.configure(text="Pictures"); self.info.configure(text="MAKE AN IMAGE MODEL FIRST (AI TRAINING > IMAGE LEARNING > + NEW IMAGE MODEL)"); return
        self.title.configure(text=f"Pictures for {n}"); w = self.IM.pictures(n)
        self.info.configure(text=("   ".join(f"{k.upper()}: {v}" for k, v in w.items()) or "NO PICTURES YET"))

    def add_images(self):
        ps = filedialog.askopenfilenames(parent=self.app, title="Choose pictures to learn from", initialdir=prefs.save_folder(),
                                         filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")])
        if ps: self.review(ps)

    def review(self, ps, remove_originals=False, source="", file_as=None, more=None, refine=None, words=None):
        """Keep or reject: every new picture in a big grid (click one to reject it, click again to keep it; right-click to see it big),
        each filed under its thing. Pictures from a search are filed under the thing that was searched; your own under the thing named in
        file_as[""] (or the model's name). more(): fetch the next ones for the same search; refine(words): search again with new words.
        remove_originals: they came from the scraper, so the scraped files are deleted once reviewed (nothing left behind)"""
        from PIL import Image, ImageTk
        n = self.IM.active()
        if not n: return T.banner(self.app, "MAKE AN IMAGE MODEL FIRST — AI Training > Image Learning > + New image model")
        self.close_review()
        v_ = self.review_view = _frame(self); self.home.pack_forget(); v_.pack(fill="both", expand=True)
        T.Title(v_, f"Keep or reject  ({n})").pack(pady=(0, 4))
        T.Text(v_, (f"From: {source}.\n" if source else "") + "Click a picture to reject it (click again to keep it). Right-click to see it big. "
               "The label under each is the thing it's filed under.", muted=True).pack()
        self.count_lbl = T.Text(v_, "", font=T.f(11)); self.count_lbl.pack(pady=(4, 0))
        bar = _frame(v_); bar.pack(side="bottom", pady=(8, 0))
        box = T.ScrollBox(v_); box.pack(fill="both", expand=True, pady=(8, 0))
        cv = tk.Canvas(box.body, bg=v_["bg"], highlightthickness=0); inner = tk.Frame(cv, bg=v_["bg"])
        T.on_change(lambda: (cv.configure(bg=self["bg"]), inner.configure(bg=self["bg"])))
        inner.bind("<Configure>", lambda e: T.fit_scrollregion(cv)); cv.create_window((0, 0), window=inner, anchor="nw")
        box.attach(cv); cv.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        rows = []; cells = []; self._thumbs = []; size = max(90, int(round(170 * T.Z))); labels = list(self.IM.pictures(n))
        cols = max(3, (max(800, self.winfo_width()) - 60) // (size + 24))
        def paint(cell, keep):
            cell["img"].configure(highlightbackground="#2ecc71" if keep.get() else "#e74c3c")
            cell["mark"].configure(text="KEEP" if keep.get() else "✗  REJECTED", fg="#2ecc71" if keep.get() else "#e74c3c")
            ph = cell["on"] if keep.get() else cell["off"]
            if ph is not None: cell["img"].configure(image=ph)
        def count():
            k = sum(1 for _, _, use in rows if use.get()); self.count_lbl.configure(text=f"KEEPING {k} OF {len(rows)}")
        def big(path):
            try: im = Image.open(path).convert("RGB")
            except Exception: return
            w = tk.Toplevel(self.app); w.title(os.path.basename(path)); w.configure(bg=T.PALETTE["bg"]); w.transient(self.app)
            im.thumbnail((900, 700)); ph = ImageTk.PhotoImage(im); l = tk.Label(w, image=ph, bg=T.PALETTE["bg"]); l.image = ph; l.pack(padx=8, pady=8)
            T.Text(w, f"{os.path.basename(path)}   {Image.open(path).size[0]} x {Image.open(path).size[1]}", muted=True).pack(pady=(0, 8))
            w.bind("<Button-1>", lambda e: w.destroy()); w.bind("<Escape>", lambda e: w.destroy())
        default = (file_as or {}).get("") or n.lower()
        for i, path in enumerate(ps):
            lab = os.path.basename(os.path.dirname(path)) if remove_originals else default
            lab = (file_as or {}).get(lab, lab)                                       # (a search word filed under its thing's name)
            cell_f = tk.Frame(inner, bg=v_["bg"]); cell_f.grid(row=i // cols, column=i % cols, padx=8, pady=8, sticky="n")
            on = off = None
            try:
                th = Image.open(path).convert("RGB"); th.thumbnail((size, size)); on = ImageTk.PhotoImage(th)
                dim = Image.blend(th, Image.new("RGB", th.size, (40, 0, 0)), 0.65); off = ImageTk.PhotoImage(dim)
            except Exception: pass
            self._thumbs += [on, off]
            img = tk.Label(cell_f, image=on, bg=T.PALETTE["field"], width=size, height=size, cursor="hand2", highlightthickness=4,
                           text="" if on else "?", fg=T.PALETTE["muted"]); img.pack()
            mark = tk.Label(cell_f, text="KEEP", bg=v_["bg"], font=T.f(8, "bold")); mark.pack()
            v = tk.StringVar(value=lab); T.Choice(cell_f, "", list(dict.fromkeys([lab] + labels)), v).pack()
            use = tk.BooleanVar(value=True); cell = dict(img=img, mark=mark, on=on, off=off)
            def toggle(e, use=use, cell=cell): use.set(not use.get()); paint(cell, use); count()
            img.bind("<Button-1>", toggle); img.bind("<Button-3>", lambda e, p=path: big(p))
            paint(cell, use); rows.append((path, v, use)); cells.append(cell)
        count()
        def set_all(on):
            for (_, _, use), cell in zip(rows, cells): use.set(on); paint(cell, use)
            count()
        def commit(close=True):
            """the kept ones go in (skipping tiny ones and duplicates); the rest are left out. -> number added"""
            import hashlib
            if not fits(self.app, "AI Images", [p for p, _, use in rows if use.get()]): return None
            added = dropped = skipped = 0; seen = set()
            if get("Image Learning", "dedupe"):
                for d_, _, fs in os.walk(self.IM.pictures_dir(n)):
                    for f in fs:
                        try: seen.add(hashlib.md5(open(os.path.join(d_, f), "rb").read()).hexdigest())
                        except OSError: pass
            for path, v, use in rows:
                ok = use.get()
                if ok and get("Image Learning", "skip_small"):
                    try: ok = min(Image.open(path).size) >= 256
                    except Exception: ok = False
                    skipped += not ok
                if ok and get("Image Learning", "dedupe"):
                    h = hashlib.md5(open(path, "rb").read()).hexdigest(); ok = h not in seen; seen.add(h); skipped += not ok
                if ok:
                    d = os.path.join(self.IM.pictures_dir(n), v.get()); os.makedirs(d, exist_ok=True)
                    dest = os.path.join(d, os.path.basename(path)); k = 1
                    while os.path.exists(dest): base, ext = os.path.splitext(os.path.basename(path)); dest = os.path.join(d, f"{base}_{k}{ext}"); k += 1
                    shutil.copy(path, dest); added += 1
                elif not use.get(): dropped += 1
                if remove_originals:
                    try: os.remove(path)
                    except OSError: pass
            if close: self.close_review()
            self.refresh()
            T.banner(self.app, f"ADDED — {added} pictures to {n}" + (f"; {dropped} rejected" if dropped else "") + (f"; {skipped} skipped (tiny or duplicate)" if skipped else ""), "success")
            return added
        def get_more():
            if commit() is not None and more: more()
        def refine_it():
            if not refine: return
            d = Dialog(self.app, "Refine the search", "Search words, one per line. Add words that narrow it (official art, side view...); put a minus "
                       "in front of words to leave out (-toy -card -plush).", None, default="\n".join(words or []))
            if not d.result: return
            new = [w.strip() for w in d.result[0].splitlines() if w.strip()]
            if new and commit() is not None: refine(new)
        T.Button(bar, f"Add the kept ones to {n}", commit).pack(side="left", padx=6)
        T.Button(bar, "Keep all", lambda: set_all(True)).pack(side="left", padx=6)
        T.Button(bar, "Reject all", lambda: set_all(False)).pack(side="left", padx=6)
        if more: T.Button(bar, "Get the next ones", get_more).pack(side="left", padx=6)
        if refine: T.Button(bar, "Refine the search…", refine_it).pack(side="left", padx=6)
        T.Button(bar, "Close", self.close_review, kind="danger").pack(side="left", padx=6)
        return v_

    def close_review(self):
        if self.review_view is not None:
            self.review_view.destroy(); self.review_view = None; self._thumbs = []; self.home.pack(fill="both", expand=True)


class SubjectsPage(tk.Frame):
    """AI Training > Things to learn: one entry per thing the active image model learns (any kind of thing),
    with the same questions for any of them. Look it up fills in what it is (Wikipedia / a dictionary) and drafts what it looks like (the text
    model); Search finds its pictures (filed under its name); its details become the captions training learns from."""
    def __init__(self, master, app):
        super().__init__(master, bg=master["bg"]); self.app = app; T.on_change(lambda: self.configure(bg=self.master["bg"]))
        import image_models as IM; self.IM = IM; self.cur = None; self.vars = {}
        self.title = T.Title(self, "Things to learn"); self.title.pack(pady=(0, 4))
        T.Text(self, "One entry per thing this model learns. The same questions work for anything: fill in what you know, or press Look it up.",
               muted=True).pack(pady=(0, 8))
        body = _frame(self); body.pack(fill="both", expand=True)
        left = _frame(body); left.pack(side="left", fill="y", padx=(0, 16))
        T.Text(left, "THINGS", font=T.f(10)).pack(anchor="w")
        self.lb = tk.Listbox(left, width=26, height=18, bg=T.PALETTE["field"], fg="white", selectbackground=T.PALETTE["border"], relief="flat",
                             highlightthickness=1, highlightbackground=T.PALETTE["border"], font=T.f(10), exportselection=False)
        self.lb.pack(fill="y", expand=True, pady=(4, 6)); self.lb.bind("<<ListboxSelect>>", lambda e: self._pick())
        T.on_change(lambda: self.lb.configure(bg=T.PALETTE["field"], selectbackground=T.PALETTE["border"], highlightbackground=T.PALETTE["border"]))
        r = _frame(left); r.pack(anchor="w")
        T.Button(r, "+ Add a thing", self.add, width=13).pack(side="left"); T.Button(r, "Remove", self.remove, kind="danger", width=8).pack(side="left", padx=4)
        T.Button(left, "Back to Image Learning", lambda: app.goto("AI Training", "Image Learning"), width=24).pack(anchor="w", pady=(8, 0))
        form = self.form = _frame(body); form.pack(side="left", fill="both", expand=True)
        for key, label, help_ in self.IM.FIELDS:
            row = _frame(form); row.pack(fill="x", pady=(2, 0))
            T.Text(row, label.upper(), font=T.f(9), width=20, anchor="w").pack(side="left")
            v = tk.StringVar(); self.vars[key] = v
            if key == "kind": T.Choice(row, "", [""] + self.IM.KINDS, v).pack(side="left")
            else:
                e = tk.Entry(row, textvariable=v, width=78, bg=T.PALETTE["field"], fg="white", insertbackground="white", relief="flat", font=T.f(9))
                e.pack(side="left", fill="x", expand=True); T.on_change(lambda e=e: e.configure(bg=T.PALETTE["field"]))
            T.Text(form, "      " + help_, muted=True, font=T.f(8)).pack(anchor="w")
            v.trace_add("write", lambda *a: self._dirty())
        self.token = T.Text(form, "", font=T.f(9)); self.token.pack(anchor="w", pady=(4, 0))
        self.caption = T.Text(form, "", muted=True, font=T.f(8)); self.caption.configure(wraplength=900); self.caption.pack(anchor="w")
        b = _frame(form); b.pack(anchor="w", pady=(6, 0))
        T.Button(b, "Look it up", self.look_up, width=12).pack(side="left")
        T.Button(b, "Search for its pictures", self.search, width=22).pack(side="left", padx=6)
        T.Button(b, "Import pictures…", self.import_pictures, width=16).pack(side="left", padx=6)
        T.Button(b, "Draw one", self.draw_one, width=10).pack(side="left", padx=6)
        T.Button(b, "Save", self.save, width=8).pack(side="left", padx=6)
        self.state = T.Text(form, "", font=T.f(9)); self.state.configure(wraplength=900); self.state.pack(anchor="w", pady=(6, 0))
        self._loading = False; self._save_job = None
        self.bind("<Map>", lambda e: self.refresh(), add="+")

    def refresh(self):
        n = self.IM.active()
        if not n: self.title.configure(text="Things to learn"); self.state.configure(text="MAKE AN IMAGE MODEL FIRST — AI Training > Image Learning > + New image model"); return
        self.title.configure(text=f"Things {n} learns"); subs = self.IM.subjects(n); counts = self.IM.pictures(n)
        keep = self.cur; self.lb.delete(0, "end"); self._labels = list(subs)
        for lab in self._labels:
            done = "✓ " if (subs[lab].get("looks") or subs[lab].get("what_it_is")) else "   "
            self.lb.insert("end", f"{done}{lab}  ({counts.get(lab, 0)})")
        if keep in self._labels: i = self._labels.index(keep)
        elif self._labels: i = 0
        else: self.cur = None; self._fill({}); self.state.configure(text="NOTHING YET — press + Add a thing (or collect pictures: each search word becomes a thing)"); return
        self.lb.selection_clear(0, "end"); self.lb.selection_set(i); self._pick()

    def _pick(self):
        sel = self.lb.curselection()
        if not sel: return
        if self._save_job: self.after_cancel(self._save_job); self.save(quiet=True)
        self.cur = self._labels[sel[0]]; self._fill(self.IM.subjects(self.IM.active()).get(self.cur, {}))

    def _fill(self, p):
        self._loading = True
        try:
            for k, v in self.vars.items(): v.set(p.get(k, ""))
        finally: self._loading = False
        self._show_caption()

    def _profile(self): return {k: v.get().strip() for k, v in self.vars.items()}
    def _dirty(self):
        if self._loading or not self.cur: return
        self._show_caption()
        if self._save_job: self.after_cancel(self._save_job)
        self._save_job = self.after(800, lambda: self.save(quiet=True))        # (saves itself as you type)

    def _show_caption(self):
        if not self.cur: self.token.configure(text=""); self.caption.configure(text=""); return
        p = dict(self.IM.subjects(self.IM.active()).get(self.cur, {}), **self._profile())
        self.token.configure(text=f"ITS OWN WORD: {p.get('token')}   (type it in a request to call it up once it's trained)")
        self.caption.configure(text="CAPTION ON EACH OF ITS PICTURES: " + self.IM.caption(self.IM.active(), self.cur, p))

    def save(self, quiet=False):
        self._save_job = None
        if not self.cur or not self.IM.active(): return
        self.IM.set_subject(self.IM.active(), self.cur, **self._profile())
        if not quiet: T.banner(self.app, f"SAVED — {self.cur}", "success"); self.refresh()

    def add(self):
        n = self.IM.active()
        if not n: return T.banner(self.app, "MAKE AN IMAGE MODEL FIRST")
        d = Dialog(self.app, "Add a thing", "Its name (exactly what it's called)", "Its category (the broad family it belongs to) - optional")
        if not d.result: return
        try: lab = self.IM.add_subject(n, d.result[0].strip(), category=(d.result[1] or "").strip())
        except ValueError as e: return T.banner(self.app, f"CAN'T ADD IT — {e}")
        self.cur = lab; self.refresh(); self.look_up()

    def remove(self):
        if not self.cur: return
        n = self.IM.active(); c = self.IM.pictures(n).get(self.cur, 0)
        a = T.popup(self.app, f"REMOVE {self.cur.upper()}?", f"Its details are removed." + (f" Its {c} pictures too?" if c else ""),
                    ((("Remove it and its pictures", "danger"), ("Keep the pictures", "normal"), ("Cancel", "normal")) if c else (("Remove", "danger"), ("Cancel", "normal"))))
        if a in (None, "Cancel"): return
        self.IM.remove_subject(n, self.cur, delete_pictures=a in ("Remove it and its pictures", "Remove")); self.cur = None; self.refresh()

    def look_up(self):
        """what it is from Wikipedia (or a dictionary), then the text model drafts what it looks like from that (you check it)"""
        if not self.cur: return
        self.save(quiet=True); p = self._profile(); lab = self.cur; q = self.app.q
        term = p.get("name") or lab; hint = " ".join(x for x in (p.get("category", ""), p.get("subcategory", "")) if x)
        self.state.configure(text=f"LOOKING UP {term.upper()}…")
        def work():
            import glossary
            e = glossary.lookup(term, hint=hint); found = {}
            if e: found["what_it_is"] = e["text"]
            looks = ""
            try:
                import brain
                if brain.installed() and (e or hint):
                    ask = (f"Describe exactly what {term}" + (f" ({hint})" if hint else "") + " looks like, for an artist who has never seen it: colours, "
                           "shape, body or parts, size, markings, anything that sets it apart. One plain sentence of 25 to 45 words, no story. "
                           + (f"Here is what it is: {e['text']}" if e else "") + " If you really don't know what it looks like, reply only: UNKNOWN")
                    looks = brain.ask("AI Images", ask, max_tokens=120, use_library=False).strip().strip('"')
                    if "UNKNOWN" in looks.upper(): looks = ""
            except Exception: looks = ""
            if looks: found["looks"] = looks
            def done():
                if not self.winfo_exists(): return
                cur = self.IM.subjects(self.IM.active()).get(lab, {})
                fill = {k: v for k, v in found.items() if not cur.get(k)}            # (never over what you typed)
                if fill: self.IM.set_subject(self.IM.active(), lab, **fill)
                if self.cur == lab: self._fill(self.IM.subjects(self.IM.active()).get(lab, {}))
                self.refresh()
                if not e: self.state.configure(text=f"NOTHING FOUND FOR {term.upper()} — check the spelling, add its group, or type what you know")
                elif not looks: self.state.configure(text=f"FOUND — {e['source']}. Type what it looks like (the text model isn't set up, or didn't know): that matters most")
                else: self.state.configure(text=f"FOUND — {e['source']}. Check 'What it looks like' and fix anything wrong: it's what training learns from")
            q.put(done)
        threading.Thread(target=work, daemon=True, name="look up " + term).start()

    def import_pictures(self):
        """pictures you have (found yourself, or drew and saved): picked from your Images folder, filed under this thing, then keep or reject"""
        if not self.cur: return T.banner(self.app, "PICK A THING FIRST (or + Add a thing)")
        self.save(quiet=True)
        ps = filedialog.askopenfilenames(parent=self.app, title=f"Pictures of {self.cur}", initialdir=prefs.save_folder(),
                                         filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")])
        if not ps: return
        self.app.goto("AI Training", "Pictures"); self.app.pages["AI Training"].pages["Pictures"].review(list(ps), source="your pictures", file_as={"": self.cur})

    def draw_one(self):
        """draw it yourself: Drawing opens; save it, then Import pictures here picks it up from your Images folder"""
        if not self.cur: return T.banner(self.app, "PICK A THING FIRST (or + Add a thing)")
        self.save(quiet=True); self.app.goto("Drawing")
        T.banner(self.app, f"DRAW {self.cur.upper()} — save it (Ctrl+S), then AI Training > Things to learn > Import pictures…", "success")

    def search(self):
        """the image search, with its search words, filed under its name"""
        if not self.cur: return
        self.save(quiet=True); p = self.IM.subjects(self.IM.active())[self.cur]; words = self.IM.search_words(p)
        self.app.goto("AI Training", "Image Scraper"); sp = self.app.pages["AI Training"].pages["Image Scraper"]
        sp.search_for(self.cur, words)

def page_classes():
    """{"Image Learning": class, ...} for main.py's page list"""
    out = {name: type(name.replace(" ", "") + "Page", (AreaPage,), dict(AREA=name)) for name in AREAS}
    out["Image Learning"] = ImageAreaPage; out["Pictures"] = PicturesPage; out["Things to learn"] = SubjectsPage
    return out
