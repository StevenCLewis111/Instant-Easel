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
import os, json, shutil, hashlib, threading, tkinter as tk
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
        collect += [B("Add a code folder", "partial", "Copies code files into the coding library after the checks in Clean. "
                      "Kept for the library (looking things up comes next); it isn't trained on yet.", "import_code")]
    else:
        collect += [B("Add documents to the library", "partial", "Facts belong in a library it looks things up in, not in training. "
                      "Your files are kept there now; looking things up while answering comes next.", "import_docs")]
    clean = [S("Remove duplicate examples", "built", "The same example twice makes it lean too hard on it. Duplicates count once when training.", "dedupe", True),
             B("Open the examples folder", "built", "Everything taught is in examples.jsonl, one per line, if you want to look or fix by hand.", "open_folder"),
             B("Review and fix examples", "planned", "A list of every example with edit and delete.", "planned")]
    if code:
        clean = [S("Only permissive licences", "built", "Keeps code from projects licensed MIT, Apache or BSD (others are left out), "
                   "so nothing it writes carries someone else's licence terms.", "permissive", True),
                 S("Skip exact duplicates", "built", "About half of public code is copies; copies teach it to parrot boilerplate.", "dedupe", True),
                 S("Skip Python that doesn't compile", "built", "Broken code teaches broken code.", "compiles", True),
                 B("Remove passwords and keys", "planned", "Finds things like API keys and passwords in code and blanks them out.", "planned")] + clean[1:]
    fmt = [C("Answer style", "partial", "How long its answers should be. Saved now; used when it answers next.", "style", ["Short", "Normal", "Detailed"], "Normal")]
    if code:
        fmt = [C("Main language", "partial", "Saved now; it will steer collecting and testing.", "language", ["Python", "JavaScript", "Any"], "Python"),
               S("Explain the code too", "partial", "Answers come with a short explanation. Saved now; used when it answers next.", "explain", True)]
    settings = [C("Passes over the examples", "built", "1 to 3. More passes make it memorise your examples and forget other things.", "epochs", ["1", "2", "3"], "2"),
                C("Learning speed", "built", "Careful learns slower and safer; Fast can wreck what it knew. Normal suits most.", "speed", SPEEDS, "Normal"),
                C("Add-on size", "built", "How much the small add-on can hold. 8 or 16 for a few hundred examples.", "rank", ["8", "16", "32"], "8"),
                S("Hold back 10% to check it", "built", "Those examples are never trained on; they show whether it learned or just memorised. "
                  "Training stops once the check gets worse. Needs 10+ examples.", "holdout", True)]
    train = [B(f"Train {tab}", "built", "Bakes the examples into this area's own add-on. Other areas don't change.", "train"),
             I("Last training", "built", "When it was trained, on how many examples, and its check score (lower is better).", "trained"),
             B(f"Forget everything {tab} learned", "built", "Clears this area's examples and add-on. The base model and other areas are untouched.", "forget")]
    test = [B("Ask it something", "built", "Try questions that are NOT in your examples. That's the real test.", "ask")]
    test += ([B("Run its code against tests", "planned", "Write a test, let it write the code, and run them together.", "planned")] if code else
             [S("Use the library when answering", "planned", "Looks up your documents first, then answers from them.", "use_library", False)])
    goal = ([C("What should it get better at?", "partial", "Writing code your way is training; knowing a library's details is the library.",
               "goal", ["Write code my way", "Explain code", "Fix bugs"], "Write code my way")] if code else
            [C("What should it get better at?", "partial", "Knowing facts: use the library. Answering your way (tone, format, steps): train it.",
               "goal", ["Answering my way", "Knowing my stuff", "Both"], "Answering my way")])
    return [("Goal", goal), ("Collect", collect), ("Clean", clean), ("Format", fmt), ("Settings", settings), ("Train", train), ("Test", test)]

AREAS = {
 "Image Learning": dict(tab="AI Images", intro="Teaches it how things look: colours, textures, brushwork and light, one subject per word you search.",
  steps=[
   ("Goal", [C("What are you teaching?", "partial", "A subject (a shoe, a cat), a style (watercolour, neon) or a place. Saved now; it will set the right defaults.",
               "goal", ["A subject", "A style", "A place or mood"], "A subject"),
             B("Choose which model learns", "built", "Each model learns only from its own pictures, so a cartoon model never picks up photo looks.", "models")]),
   ("Collect", [B("Search Google Images", "built", "Type the word; every picture found is labelled with that word.", "scraper"),
                B("Add my own pictures", "built", "Your own photos or art. Your files are never changed or moved.", "add_pictures"),
                C("Pictures per word", "built", "15 to 50 varied pictures is the sweet spot. Under about 15 it copies them; past 100 it hardly helps.",
                  "per_word", ["10", "20", "30", "50"], "20")]),
   ("Clean", [B("Review pictures before learning", "built", "Untick anything wrong: one bad picture teaches the wrong thing.", "review"),
              I("Skip pictures it already learned", "built", "Fingerprints stop the same picture counting twice.", "always"),
              S("Skip tiny pictures", "built", "Pictures under 256 pixels are left out: too small to show texture or brushwork.", "skip_small", True),
              S("Square-crop around the middle", "planned", "Same framing on every picture keeps it learning the subject, not the edges.", "crop", False)]),
   ("Label", [I("Search word = label", "built", "Pictures from a search are labelled with the word you searched. Change any label in the review.", "label_note"),
              B("Teach words", "built", "Teach what your words mean (\"moody\" = dark, many clouds).", "words"),
              S("Describe each picture", "planned", "A short automatic description per picture, which you can correct. Wrong descriptions teach wrong things.", "captions", False),
              C("Trigger word", "planned", "A made-up word (like 'shuez') that switches on what it learned, used the same way on every picture.",
                "trigger", ["none", "use the search word"], "none")]),
   ("Settings", [S("Keep copies after learning", "built", "Off: the app's copies are deleted after learning. Your originals are never touched.", "keep", False),
                 C("Strength", "planned", "How strongly it learns. Too strong and everything it paints looks like your pictures.",
                   "strength", ["Gentle", "Normal", "Strong"], "Normal"),
                 C("Training length", "planned", "Longer for more pictures (about 100 steps per picture); start short and check.",
                   "length", ["Short test", "Normal", "Long"], "Normal")]),
   ("Train", [B("Learn now", "built", "Learns every picture waiting in the library, then deletes the copies (unless kept).", "learn"),
              I("Waiting to learn", "built", "Pictures added but not learned yet, per label.", "waiting")]),
   ("Test", [B("Try it in Text to Image", "built", "Paint something with the model you trained and see if it looks right.", "try_images"),
             B("Roll back to an earlier version", "built", "Every training saves a version; go back if a new one made it worse.", "models"),
             S("Compare before and after", "planned", "The same request painted before and after training, side by side.", "compare", False)]),
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
        T.Button(low, "Open this area's folder", lambda: prefs.open_folder(self.folder()), width=24).pack(side="left", padx=6)
        self.show(a["steps"][0][0])

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
                T.Button(r, "Open" if o["status"] != "planned" else "Coming", lambda o=o: self.run(o), width=10,
                         kind="normal").pack(side="left", padx=(8, 0))
            elif o["kind"] == "choice":
                v = tk.StringVar(value=str(get(self.AREA, o["key"]))); T.Choice(r, "", o["values"], v).pack(side="left", padx=(8, 0))
                v.trace_add("write", lambda *x, o=o, v=v: put(self.AREA, o["key"], v.get()))
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
        if self.AREA == "Image Learning": return self.lfi().folder()
        if self.AREA == "Video Learning": d = paths.data("my-library", "Video clips"); os.makedirs(d, exist_ok=True); return d
        import brain; return brain._tab_dir(self.tab)

    def library(self):
        d = os.path.join(self.folder(), "library"); os.makedirs(d, exist_ok=True); return d

    def lfi(self): return self.app.pages["AI Training"].pages["Learn from Images"]

    def info_text(self, what):
        if what in ("tip",): return ""
        if what in ("label_note", "always"): return "ALWAYS ON"
        if what == "waiting":
            import learn; w = {k: v for k, v in learn.waiting(self.folder()).items() if v}
            return "   ".join(f"{k}: {v}" for k, v in w.items()) or "nothing waiting"
        import brain
        if what == "count":
            n = len(brain.examples(self.tab)); return f"{n}  " + ("(a good start)" if n >= 100 else "(aim for 100+)")
        if what == "trained":
            i = brain.info(self.tab)
            if not i["adapter"]: return "not trained yet"
            t = {}
            p = os.path.join(brain._tab_dir(self.tab), "trained.json")
            if os.path.exists(p): t = json.load(open(p))
            cl = f", check {t['check_loss']:.3f}" if t.get("check_loss") is not None else ""
            return f"{i['trained_when'][:16].replace('T', ' ')}, {i['trained_on']} examples{cl}"
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
    def do_models(self): self.goto("Models")
    def do_scraper(self): self.goto("Image Scraper")
    def do_words(self): self.goto("Words")
    def do_review(self): self.goto("Learn from Images")
    def do_add_pictures(self): self.goto("Learn from Images"); self.lfi().add_images()
    def do_learn(self): self.goto("Learn from Images"); self.lfi().learn()
    def do_try_images(self): self.app.goto("AI Images", "Text to Image")
    def do_open_folder(self): prefs.open_folder(self.folder())

    def do_add_clips(self):
        ps = filedialog.askopenfilenames(parent=self.app, title="Choose short video clips",
                                         filetypes=[("Videos", "*.mp4 *.mov *.webm *.mkv *.avi"), ("All files", "*.*")])
        for p in ps: shutil.copy(p, self.folder())
        if ps: T.banner(self.app, f"ADDED — {len(ps)} clips are in the video library", "success")

    def do_import_docs(self):
        ps = filedialog.askopenfilenames(parent=self.app, title="Choose documents for the library",
                                         filetypes=[("Documents", "*.txt *.md *.pdf *.html *.csv *.json"), ("All files", "*.*")])
        for p in ps: shutil.copy(p, self.library())
        if ps: T.banner(self.app, f"ADDED — {len(ps)} documents are in the {self.tab} library", "success")

    def do_import_code(self):
        src = filedialog.askdirectory(parent=self.app, title="Choose a folder of code")
        if not src: return
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

    def do_train(self):
        import brain
        if not brain.examples(self.tab): return T.banner(self.app, f"NOTHING TO LEARN YET — teach {self.tab} some examples first (Collect)")
        g = lambda k: get(self.AREA, k)
        kw = dict(epochs=int(g("epochs")), rank=int(g("rank")), lr=LR.get(g("speed"), 2e-4), holdout=0.1 if g("holdout") else 0.0, dedupe=bool(g("dedupe")))
        T.banner(self.app, f"TRAINING — {self.tab}: this takes a while; you can keep working", "success")
        q = self.app.q
        brain.train_async(self.tab, on_done=lambda ok, m: q.put(lambda: (T.banner(self.app, ("TRAINED — " if ok else "TRAINING FAILED — ") + m,
                                                                                     "success" if ok else "error"), self.refresh())), **kw)

    def do_ask(self):
        d = Dialog(self.app, f"Ask {self.tab}", "Your question", None)
        if not d.result: return
        import brain; q = self.app.q; question = d.result[0]
        T.banner(self.app, "THINKING — the first answer takes longer while the model loads", "success")
        def work():
            try: ans = brain.ask(self.tab, question); q.put(lambda: Answer(self.app, question, ans))
            except Exception as e: q.put(lambda e=e: T.banner(self.app, f"COULDN'T ANSWER — {e}"))
        threading.Thread(target=work, daemon=True).start()

class Dialog(tk.Toplevel):
    """a question box (and an answer box when b is given). .result = (a, b) or None"""
    def __init__(self, app, title, a, b):
        super().__init__(app); self.result = None; self.title(title); self.configure(bg=T.PALETTE["bg"]); self.transient(app)
        p = T.Panel(self, pad=14); p.pack(fill="both", expand=True, padx=8, pady=8); T.Title(p, title).pack(pady=(0, 8)); self.boxes = []
        for label in (a, b):
            if label is None: continue
            T.Text(p, label.upper()).pack(anchor="w")
            t = tk.Text(p, width=60, height=5 if b else 3, bg=T.PALETTE["field"], fg=T.PALETTE["text"], insertbackground=T.PALETTE["text"],
                        relief="flat", font=T.f(10), wrap="word", highlightthickness=1, highlightbackground=T.PALETTE["border"])
            t.pack(fill="both", expand=True, pady=(2, 8)); self.boxes.append(t)
        r = tk.Frame(p, bg=p["bg"]); r.pack()
        T.Button(r, "OK", self.ok).pack(side="left", padx=6); T.Button(r, "Cancel", self.destroy, kind="danger").pack(side="left")
        self.boxes[0].focus_set(); self.grab_set(); app.wait_window(self)
    def ok(self):
        vals = [t.get("1.0", "end").strip() for t in self.boxes]
        if all(vals): self.result = tuple(vals) + ((None,) if len(vals) == 1 else ())
        self.destroy()

class Answer(tk.Toplevel):
    def __init__(self, app, question, answer):
        super().__init__(app); self.title("Its answer"); self.configure(bg=T.PALETTE["bg"]); self.transient(app)
        p = T.Panel(self, pad=14); p.pack(fill="both", expand=True, padx=8, pady=8)
        T.Text(p, question, muted=True, wraplength=600).pack(anchor="w", pady=(0, 8))
        T.Text(p, answer, wraplength=600).pack(anchor="w")
        T.Button(p, "Close", self.destroy, kind="danger").pack(pady=(12, 0))

def page_classes():
    """{"Image Learning": class, ...} for main.py's page list"""
    return {name: type(name.replace(" ", "") + "Page", (AreaPage,), dict(AREA=name)) for name in AREAS}
