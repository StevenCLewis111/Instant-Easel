"""
settings_pages.py: Instant Easel Pro's Settings pages. Every value lives in prefs.py (instant_easel_settings.json next to the app).
"""
import os, sys, json, glob, shutil, zipfile, platform, subprocess, threading, tkinter as tk
from tkinter import filedialog
import theme as T, prefs, skin

def _frame(parent):
    f = tk.Frame(parent, bg=parent["bg"]); T.on_change(lambda: f.configure(bg=f.master["bg"])); return f

def _rule(parent):
    """the border line above a section's title"""
    l = T.Line(parent, vertical=False); l.pack(fill="x", pady=(10, 0)); return l

class SettingsPage(tk.Frame):
    TITLE = "Settings"; NOTE = ""
    def __init__(self, master, app):
        super().__init__(master, bg=master["bg"]); self.app = app; T.on_change(lambda: self.configure(bg=self.master["bg"]))
        T.Title(self, self.TITLE).pack(anchor="w", pady=(0, 4))
        if self.NOTE: n = T.Text(self, self.NOTE, muted=True); n.configure(wraplength=820); n.pack(anchor="w", pady=(0, 10))
        self.body = _frame(self); self.body.pack(fill="both", expand=True, anchor="w"); self.build()
    def build(self): pass

    # ---- row helpers: label on the left, control on the right, an optional note underneath
    def row(self, label, note=""):
        r = _frame(self.body); r.pack(fill="x", pady=5, anchor="w")
        T.Text(r, label.upper(), font=T.f(10)).pack(side="left"); r.ctrl = _frame(r); r.ctrl.pack(side="left", padx=(16, 0))
        if note: n = T.Text(self.body, "   " + note, muted=True, font=T.f(8)); n.configure(wraplength=800); n.pack(anchor="w")
        return r.ctrl
    def toggle(self, label, key, note="", after=None):
        v = tk.BooleanVar(value=bool(prefs.get(key))); T.Toggle(self.row(label, note), v, command=lambda: (prefs.set(key, v.get()), after and after())).pack(side="left"); return v
    def choice(self, label, key, choices, note="", after=None):
        v = tk.StringVar(value=str(prefs.get(key))); T.Choice(self.row(label, note), "", choices, v).pack(side="left")      # the row already says what it is
        v.trace_add("write", lambda *a: (prefs.set(key, type(prefs.DEFAULTS[key])(v.get()) if not isinstance(prefs.DEFAULTS[key], bool) else v.get() == "True"), after and after())); return v
    def entry(self, label, key, width=34, note=""):
        v = tk.StringVar(value=str(prefs.get(key))); c = self.row(label, note); e = T.Entry(c, v, width=width); e.pack(side="left")
        def save(*a):
            val = v.get(); d = prefs.DEFAULTS[key]
            try: prefs.set(key, int(val) if isinstance(d, int) and not isinstance(d, bool) else val)
            except ValueError: pass
        e.bind("<FocusOut>", save); e.bind("<Return>", save); return v
    def buttons(self, *items):
        r = _frame(self.body); r.pack(anchor="w", pady=8)
        for text, cmd, kind in items: skin.file_button(T.Button(r, text, cmd, kind=kind)).pack(side="left", padx=(0, 8))   # (New / Open / Save: painted)
        return r

# ---------------------------------------------------------------- General
class GeneralPage(SettingsPage):
    TITLE = "General"; NOTE = "Where your work is saved, in what format, and how the app starts and closes."
    def build(self):
        c = self.row("Your work folder", "images, videos, code and chats folders inside it. Every tab saves its work there and opens from there. "
                     "Normally the folder of the app you launched (the project folder, or EXE Build for the .exe).")
        self.folder_lbl = T.Text(c, prefs.work_root(), font=T.f(9)); self.folder_lbl.pack(side="left", padx=(0, 8))
        T.Button(c, "Change", self.pick).pack(side="left"); T.Button(c, "App's own folder", self.own).pack(side="left", padx=(6, 0)); skin.file_button(T.Button(c, "Open", lambda: prefs.open_folder(prefs.work_root()))).pack(side="left", padx=6)
        self.choice("File format", "save_format", ["PNG", "JPEG", "WebP"], "PNG keeps every detail (larger files). JPEG and WebP are smaller.")
        self.choice("JPEG / WebP quality", "jpeg_quality", ["75", "85", "92", "100"])
        self.entry("File names", "name_pattern", note="{date}, {time} and {n} (number) are filled in. Example: instant-easel-pro-2026-11-15-163000-1.png")
        import features
        self.choice("Open on start", "start_tab", [m for m, _, _ in features.visible_menus()] + ["Last used"])
        self.toggle("Confirm before quitting", "confirm_exit")
        self.buttons(("Create desktop shortcut", self.shortcut, "normal"))
    def shortcut(self):
        """a desktop shortcut with the Instant Easel Pro icon"""
        try:
            import shortcut; path = shortcut.make(); T.banner(self.app, f"SHORTCUT CREATED — {os.path.basename(path)} is on your desktop", "success")
        except Exception as e: T.banner(self.app, f"COULDN'T MAKE THE SHORTCUT — {e}")
    def pick(self):
        d = filedialog.askdirectory(parent=self.app, initialdir=prefs.work_root())
        if d: prefs.set("work_folder", d); self.folder_lbl.configure(text=d)
    def own(self):
        prefs.set("work_folder", ""); self.folder_lbl.configure(text=prefs.work_root())

# ---------------------------------------------------------------- Performance
class PerformancePage(SettingsPage):
    TITLE = "Performance"; NOTE = "Trade a little quality for speed on slower PCs."
    def build(self):
        self.choice("Editing preview", "edit_preview", ["Fast", "Normal", "Sharp"], "Size of the live preview while you drag sliders. Saving is always full size.")
        self.choice("Draw undo steps", "undo_steps", ["10", "30", "60", "100"], "More steps use more memory on big canvases.")

# ---------------------------------------------------------------- Display
class DisplayPage(SettingsPage):
    TITLE = "Display"; NOTE = ("The layout never changes: it just scales to fit the window. Maximized (the start-up default) keeps the title bar; "
                               "its restore button goes full screen and minimize goes to the fixed-size window. F11 switches full screen and Esc leaves it.")
    def build(self):
        self.choice("Window mode", "window_mode", ["Maximized", "Windowed", "Full screen"], "How the app opens. Windowed is the fixed-size window, centred.",
                    after=lambda: self.app.apply_window_mode())
        self.choice("Text size", "text_size", ["Small", "Normal", "Large"], "Applies the next time the app opens.")
        self.toggle("Show hints and tips", "show_hints", "The key hints along the bottom of pages. Applies the next time the app opens.")
        self.toggle("Startup splash screen", "show_splash")
        self.buttons(("Full screen now (F11)", lambda: self.app.set_fullscreen(True), "normal"), ("Reset window size", self.app.reset_window, "normal"))

# ---------------------------------------------------------------- Privacy & data
class PrivacyPage(SettingsPage):
    TITLE = "Privacy & Data"; NOTE = ("Instant Easel Pro works offline. Your prompts, pictures and everything the AI tabs learn stay on this PC. The internet "
                                      "is only used to download a model, search for training pictures, or check for updates.")
    def build(self):
        import brain; self.lib = paths_data("my-library"); self.tabs = brain.TABS_DIR; self.models = brain.ROOT
        self.toggle("Keep training copies", "keep_training_copies", "Off: after training, the app's copies of your pictures are deleted.")
        T.Text(self.body, "STORAGE USED", font=T.f(10)).pack(anchor="w", pady=(12, 4)); self.usage = T.Text(self.body, "", font=T.f(9)); self.usage.pack(anchor="w")
        self.buttons(("Refresh", self.refresh, "normal"), ("Open data folder", lambda: prefs.open_folder(prefs.home_dir()), "normal"))
        self.buttons(("Clear training pictures", self.clear_pictures, "danger"), ("Clear what the AI tabs were taught", self.clear_taught, "danger"))
        self.refresh()
    def refresh(self):
        rows = [("Training pictures and image models", prefs.folder_size(self.lib)), ("What the AI tabs were taught", prefs.folder_size(self.tabs)),
                ("Downloaded AI models", prefs.folder_size(self.models)),
                ("Your work folder (images, videos, code, chats)", prefs.folder_size(prefs.work_root()))]
        for name in ("instant_easel_settings.json", "instant_easel_theme.json", "instant_easel_errors.log"):
            p = _data_file(name); rows.append((name, os.path.getsize(p) if os.path.exists(p) else 0))
        self.usage.configure(text="\n".join(f"{k:<44} {prefs.human(v):>10}" for k, v in rows))
    def clear_pictures(self):
        if T.popup(self.app, "CLEAR TRAINING PICTURES?", "Deletes every image model and the pictures waiting to be learned.\nThis can't be undone.",
                   (("Clear", "danger"), ("Cancel", "normal"))) == "Clear":
            shutil.rmtree(self.lib, ignore_errors=True); os.makedirs(self.lib, exist_ok=True); self.refresh(); T.banner(self.app, "TRAINING PICTURES CLEARED", "success")
    def clear_taught(self):
        if T.popup(self.app, "CLEAR WHAT THE AI TABS WERE TAUGHT?", "Every tab's examples and library are deleted. The models themselves stay.",
                   (("Clear", "danger"), ("Cancel", "normal"))) == "Clear":
            shutil.rmtree(self.tabs, ignore_errors=True); self.refresh(); T.banner(self.app, "CLEARED — the AI tabs start fresh", "success")

def paths_data(*p):
    import paths; d = paths.ai(*p); os.makedirs(d, exist_ok=True); return d

# ---------------------------------------------------------------- AI Storage: the AI drive and each AI's portion
class AIStoragePage(SettingsPage):
    TITLE = "AI Storage"; NOTE = ("Give the AI its own drive. Models, what each AI learned, its libraries and memory all live there, and each AI "
                                  "gets its own portion. More room lets an AI keep bigger libraries and longer memory; it can't make a model "
                                  "think faster, because a model runs from your graphics card's memory.")
    def build(self):
        import storage, paths; self.storage = storage; self.paths = paths
        c = self.row("AI drive"); self.where = T.Text(c, paths.ai_root(), font=T.f(9)); self.where.pack(side="left", padx=(0, 8))
        T.Button(c, "Choose…", self.choose).pack(side="left"); T.Button(c, "App's own folder", lambda: self.move(paths.HOME)).pack(side="left", padx=6)
        skin.file_button(T.Button(c, "Open", lambda: prefs.open_folder(paths.ai_root()))).pack(side="left")
        self.free = T.Text(self.body, "", muted=True, font=T.f(9)); self.free.pack(anchor="w", padx=(20, 0))
        T.Text(self.body, "EACH AI'S PORTION", font=T.f(11)).pack(anchor="w", pady=(12, 4)); self.rows = {}
        for area in storage.AREAS:
            r = _frame(self.body); r.pack(fill="x", anchor="w", pady=3)
            T.Text(r, area.upper(), font=T.f(10), width=16, anchor="w").pack(side="left")
            bar = tk.Canvas(r, width=260, height=16, highlightthickness=1, highlightbackground=T.PALETTE["border"], bg=T.PALETTE["field"]); bar.pack(side="left", padx=8)
            lab = T.Text(r, "", font=T.f(9), width=22, anchor="w"); lab.pack(side="left")
            v = tk.StringVar(value=str(storage.budget_gb(area))); T.Choice(r, "portion GB", ["25", "50", "100", "150", "200", "300", "400", "500"], v).pack(side="left", padx=8)
            v.trace_add("write", lambda *a, area=area, v=v: (storage.set_budget_gb(area, int(v.get())), self.refresh()))
            self.rows[area] = (bar, lab)
        self.total = T.Text(self.body, "", muted=True, font=T.f(9)); self.total.pack(anchor="w", pady=(8, 0))
        self.buttons(("Refresh", self.refresh, "normal")); self.refresh()
    def refresh(self):
        st = self.storage; free, total = st.drive_free(); budgets = sum(st.budget_gb(a) for a in st.AREAS)
        self.where.configure(text=self.paths.ai_root())
        self.free.configure(text=f"{free / 1e9:,.0f} GB free of {total / 1e9:,.0f} GB on that drive")
        for area, (bar, lab) in self.rows.items():
            u = st.used(area); b = st.budget_gb(area) * 1e9; frac = min(1.0, u / b) if b else 0
            bar.delete("all"); w = int(bar["width"]); bar.create_rectangle(0, 0, int(w * frac), 18, fill=T.PALETTE["border"], width=0)
            lab.configure(text=f"{u / 1e9:.2f} of {st.budget_gb(area)} GB")
        self.total.configure(text=f"Portions add up to {budgets} GB" + (" — more than the drive's free space" if budgets * 1e9 > free + sum(st.used(a) for a in st.AREAS) else ""))
    def choose(self):
        d = filedialog.askdirectory(parent=self.app, title="Choose the drive (or a folder on it) for the AI")
        if not d: return
        if os.path.dirname(os.path.abspath(d)) == os.path.abspath(d) or len(os.path.abspath(d)) <= 3: d = os.path.join(d, "Instant Easel Pro AI")   # a whole drive: its own folder on it
        self.move(d)
    def move(self, d):
        import brain, imaging
        if os.path.abspath(d) == os.path.abspath(self.paths.ai_root()): return
        if T.popup(self.app, "MOVE THE AI'S THINGS?", f"Everything the AI keeps is copied to\n{d}\nthen removed from where it is now. "
                   "The models stop while this happens.", (("Move", "normal"), ("Cancel", "danger"))) != "Move": return
        brain.stop(); imaging.stop_now(); q = self.app.q
        def work():
            try:
                self.storage.move_to(d, progress=lambda t: q.put(lambda t=t: T.banner(self.app, f"MOVING — {t}", "success")))
                q.put(lambda: (self.refresh(), T.banner(self.app, "MOVED — close and reopen the app to finish", "success")))
            except Exception as e: q.put(lambda e=e: T.banner(self.app, f"COULDN'T MOVE — {e}"))
        threading.Thread(target=work, daemon=True).start()

# ---------------------------------------------------------------- AI models: the core text model + each tab's own model
class AIModelsPage(SettingsPage):
    TITLE = "AI Models"; NOTE = ("This PC was checked, so each AI only offers models that will really run on it: the best one first (marked), then the "
                                 "smaller ones, never a bigger one. Download gets the chosen model in the size that suits your graphics card. "
                                 "Add manually uses a model file you have.")
    def build(self):
        import brain, imaging, hardware, catalog; self.brain = brain; self.imaging = imaging; self.hw = hardware; self.cat = catalog
        self.slot_vars = {}
        def head(text): T.Text(self.body, text, font=T.f(11)).pack(anchor="w", pady=(8, 2))
        head("YOUR PC")
        r = _frame(self.body); r.pack(fill="x", anchor="w")
        self.pc_line = T.Text(r, hardware.describe(), font=T.f(10)); self.pc_line.pack(side="left")
        T.Button(r, "Check again", self._rescan, width=12).pack(side="left", padx=10)
        pc = hardware.pc(); warn = f"Held back right now: {pc['throttled']}. AI runs slower until it's plugged in / on a full-power plan. " if pc.get("throttled") else ""
        self.pc_note = T.Text(self.body, warn + f"Checked {pc.get('when', '')}. "
                              + ("" if catalog.can("AI Videos") else "Making videos needs a 6 GB+ graphics card with 24 GB of PC memory (or 32 GB of PC memory), so the AI Videos tab is hidden."),
                              muted=True, font=T.f(9)); self.pc_note.configure(wraplength=900); self.pc_note.pack(anchor="w", padx=(30, 0))
        head("BASE MODEL  (the language brain: every tab uses it to understand you — it isn't picked in the tabs)")
        cores = self._choices("core", custom=("custom-core", "Your own model file (core)"))
        cur = brain.core_key() if brain.core_key() in cores else self._default("core", cores)
        self._row_with("BASE", "built", "core_model", cores, cur, download=self._dl_text, add=lambda: self._add_text("custom-core", "core_model"), speed="speed_text")
        r = _frame(self.body); r.pack(anchor="w", padx=(30, 0), pady=(2, 0))
        T.Button(r, "Start", self._start, width=7).pack(side="left", padx=(0, 4)); T.Button(r, "Stop", self._stop, kind="danger", width=6).pack(side="left", padx=4)
        self.state = T.Text(r, "", font=T.f(10)); self.state.pack(side="left", padx=10)
        bars = _frame(self.body); bars.pack(anchor="w", padx=(30, 0))                          # real bars while the models download
        self.text_bar = T.ProgressBar(bars, width=420); self.img_bar = T.ProgressBar(bars, width=420, color="#335bb0")
        head("EACH AREA'S MODELS  (the tabs pick between the downloaded ones, weak to strong)")
        chat = {"core": ("Core text model (recommended)", "AI Chat talks to the core model.")}
        if brain.model_file("custom-AI_Chat"): chat["custom-AI_Chat"] = ("Your own model file", "A .gguf text model you added with Add manually.")
        self._row_with("AI CHAT", "built", "model_AI_Chat", chat, prefs.get("model_AI_Chat") if prefs.get("model_AI_Chat") in chat else "core",
                       download=lambda k: self._dl_text(brain.core_key()), add=lambda: self._add_text("custom-AI_Chat", "model_AI_Chat"))
        coding = self._choices("AI Coding", custom=("custom-AI_Coding", "Your own model file"))
        coding["core"] = ("Core text model", "The core model writes and explains code too.")
        self._row_with("CODING", "built", "model_AI_Coding", coding, prefs.get("model_AI_Coding") if prefs.get("model_AI_Coding") in coding else self._default("AI Coding", coding),
                       download=lambda k: self._dl_text(brain.core_key() if k == "core" else k), add=lambda: self._add_text("custom-AI_Coding", "model_AI_Coding"))
        images = self._choices("AI Images", custom=("file", "Your own model file"))
        self._row_with("IMAGE", "built", "model_AI_Images", images, imaging.choice() if imaging.choice() in images else self._default("AI Images", images),
                       download=self._dl_images, add=self._add_image, folder=imaging.IMAGE, speed="speed_image")
        edits = self._choices("Image edits")
        if edits:
            self._row_with("EDITS", "built", "model_image_edits", edits, next(iter(edits)), download=self._dl_images, add=self._add_image, folder=imaging.KDIR)
        else: T.Text(self.body, "IMAGE EDITS: FLUX.2 Klein needs 16 GB of PC memory, so Prompt to Edit and the reference sections can't run on this PC.", muted=True, font=T.f(9)).pack(anchor="w")
        T.Text(self.body, "SPEED: Fast puts everything on the graphics card. Balanced lets the engine fit the model to the card's free memory. Safe keeps "
               "more in PC memory: slower, but big models fit. Before every run the app checks the free memory and steps down by itself (Fast → "
               "Balanced → Safe), and if a run still runs out of memory it's tried again in Safe instead of failing.", muted=True, font=T.f(8),
               wraplength=900).pack(anchor="w", pady=(8, 0))
        if catalog.can("AI Videos"):
            videos = self._choices("AI Videos", custom=("file", "Your own model file"))
            self._row_with("VIDEO", "built", "model_AI_Videos", videos, prefs.get("model_AI_Videos") if prefs.get("model_AI_Videos") in videos else self._default("AI Videos", videos),
                           download=self._dl_video, add=self._add_video, folder=os.path.join(brain.ROOT, "video"))
        self._audio_rows(head)
        self._tick()

    # ---- the audio model: voices and sound effects, each weak or strong (it runs in its own downloaded Python)
    def _audio_rows(self, head):
        import audio_engine as A
        head("AUDIO MODEL  (AI Videos > Add Sound: a voice for your words, sound effects matched to the video)")
        self._aud = {}
        for kind, name, note in (("voices", "VOICES", "Kokoro 82M: 13 voices, runs on the processor (Apache-2.0)."),
                                 ("effects", "EFFECTS", "MMAudio on PyTorch: sound that matches what happens. Non-commercial weights (CC-BY-NC).")):
            r = self._row(name, "built"); v = tk.StringVar(value="Strong" if A.have(kind, "strong") else "Weak")
            T.Choice(r, "size", ["Weak", "Strong"], v).pack(side="left", padx=(0, 6))
            T.Button(r, "Download", lambda k=kind, v=v: self._aud_get(k, v.get().lower()), width=10).pack(side="left", padx=3)
            T.Button(r, "Remove", lambda k=kind, v=v: (A.remove(k, v.get().lower() if k == "voices" else None), self._aud_show()), kind="danger", width=8).pack(side="left", padx=3)
            st = T.Text(r, "", font=T.f(8), muted=True); st.pack(side="left", padx=8); self._aud[kind] = (v, st)
            v.trace_add("write", lambda *a: self._aud_show())
            T.Text(self.body, note, muted=True, font=T.f(8)).pack(anchor="w", padx=(30, 0))
        self._aud_show()

    def _aud_show(self):
        import audio_engine as A
        for kind, (v, st) in self._aud.items():
            p = v.get().lower(); here = A.downloaded(kind)
            st.configure(text=("✓ here" if A.have(kind, p) else f"about {A.size_gb(kind, p):.1f} GB to download")
                         + (f" · downloaded: {', '.join(x.title() for x in here)}" if here else ""))

    def _aud_get(self, kind, power):
        import audio_engine as A
        q = self.app.q
        def work():
            try:
                A.install(kind, power, report=lambda t, f: q.put(lambda t=t: self.winfo_exists() and self._aud[kind][1].configure(text=t[:90])))
                q.put(lambda: (self._aud_show(), T.banner(self.app, f"AUDIO MODEL READY — {kind} ({power})", "success")))
            except Exception as e: q.put(lambda e=e: (self._aud_show(), T.banner(self.app, f"AUDIO DOWNLOAD DIDN'T FINISH — {e}", "error")))
        threading.Thread(target=work, daemon=True, name="audio download").start()
        T.banner(self.app, f"DOWNLOADING THE AUDIO MODEL ({kind}, {power})", "success")

    # ---- what's offered: the models that fit this PC (best first), plus any you already downloaded
    def _choices(self, area, custom=None):
        out = {}; best = self.cat.best(area)
        for e in self.cat.options(area):
            lad = [x["key"] for x in self.cat.ladder(area)]; i = lad.index(e["key"]) if e["key"] in lad else 0
            power = " · strong" if i == 0 else (" · weak" if i == len(lad) - 1 and len(lad) > 1 else " · medium")
            tag = power + (" (best for your PC)" if best and e["key"] == best["key"] else "")
            _, size = self.cat.variant(e)
            how = "Add it with Add manually. " if e.get("manual") else f"About {size:g} GB to download. "
            out[e["key"]] = (e["label"] + tag, how + self.cat.describe_fit(e)[0].upper() + self.cat.describe_fit(e)[1:] + ". " + e["note"])
        for e in self.cat.ladder(area):                                       # downloaded before, though it's more than this PC really has
            if e["key"] not in out and self._downloaded(area, e["key"]):
                out[e["key"]] = (e["label"] + " (downloaded)", "Downloaded already, but it needs more than this PC has, so it may be slow or not start. " + e["note"])
        if custom and (self._downloaded(area, custom[0]) or custom[0] == "file"): out[custom[0]] = (custom[1], "A model file you added with Add manually.")
        return out

    def _downloaded(self, area, key):
        if area in ("core", "AI Coding", "AI Chat"): return bool(self.brain.model_file(key))
        if area in ("AI Images", "Image edits"):
            if key in ("zimage", "klein"): return self.imaging.have(key)
            if key == "sd15": return os.path.exists(os.path.join(self.imaging.IMAGE, self.imaging.SD15["file"]))
            if key == "file": return any(f != self.imaging.SD15["file"] for f in os.listdir(self.imaging.IMAGE)) if os.path.isdir(self.imaging.IMAGE) else False
        return False

    def _default(self, area, choices):
        """not chosen yet: the best one already downloaded, else the best one for this PC"""
        for k in choices:
            if self._downloaded(area, k) and k not in ("file",) and not k.startswith("custom"): return k
        b = self.cat.best(area); return b["key"] if b and b["key"] in choices else next(iter(choices))

    def _row(self, name, status):
        import learning_areas as LA
        r = _frame(self.body); r.pack(fill="x", anchor="w", pady=(4, 0))
        if LA.DOT: LA.DOT(r, status, 14).pack(side="left", padx=(0, 8))
        T.Text(r, name, font=T.f(10), width=10, anchor="w").pack(side="left"); return r

    def _speed(self, r, key, restart=False):
        v = tk.StringVar(value=prefs.get(key) or "Balanced"); T.Choice(r, "speed", ["Fast", "Balanced", "Safe"], v).pack(side="left", padx=(8, 0))
        def changed(*a):
            prefs.set(key, v.get())
            if restart and self.brain.ready(): self.brain.stop(); T.banner(self.app, f"SPEED: {v.get().upper()} — the model starts that way next time it's used", "success")
        v.trace_add("write", changed)

    def _row_with(self, tab, status, key, choices, cur, download, add, folder=None, speed=None):
        """one AI: its model choice (what fits this PC), Download (the chosen one), Add manually, and its speed"""
        r = self._row(tab, status)
        v = tk.StringVar(value=choices[cur][0]); ch = T.Choice(r, "", [c[0] for c in choices.values()], v); ch.pack(side="left", padx=(8, 8))
        note = T.Text(self.body, choices[cur][1], muted=True, font=T.f(9)); note.configure(wraplength=860); note.pack(anchor="w", padx=(30, 0))
        def chosen(): return next(k for k, c in choices.items() if c[0] == v.get())
        def changed(*a):
            k = chosen(); note.configure(text=choices[k][1])
            if key == "core_model": self._switch(k)
            else: prefs.set(key, k)
        v.trace_add("write", changed); self.slot_vars[key] = (v, choices)
        T.Button(r, "Download", lambda: download(chosen()), width=10).pack(side="left", padx=4)
        T.Button(r, "Add manually", add, width=13).pack(side="left", padx=4)
        if folder: skin.file_button(T.Button(r, "Open folder", lambda: prefs.open_folder(folder))).pack(side="left", padx=4)
        if speed: self._speed(r, speed, restart=(speed == "speed_text"))

    def _select(self, key, value):
        prefs.set(key, value); pair = self.slot_vars.get(key)
        if pair and value in pair[1]: pair[0].set(pair[1][value][0])
    def _done(self, title):
        q = self.app.q
        return lambda ok, m: q.put(lambda: T.banner(self.app, (f"{title} — " if ok else "COULDN'T SET IT UP — ") + m, "success" if ok else "error"))
    def _rescan(self):
        self.pc_line.configure(text="CHECKING THIS PC…")
        def done(old, new):
            def show():
                if not self.winfo_exists(): return
                for w in self.body.winfo_children(): w.destroy()
                self.build(); T.banner(self.app, f"CHECKED — {self.hw.describe(new)}", "success")
            self.app.q.put(show)
        self.hw.rescan_async(on_done=done)

    # ---- text models (core, chat, coding)
    def _dl_text(self, key):
        if key in ("file",) or str(key).startswith("custom"): return T.banner(self.app, "THAT'S YOUR OWN FILE — use Add manually to choose it", "busy")
        self.brain.download(on_done=self._done("INSTALLED"), key=key)
        T.banner(self.app, f"DOWNLOADING {self.brain.spec(key)['label'].upper()} — about {self.brain.download_size(key) / 1e9:.1f} GB; it's set up when it finishes (progress below)", "success")
        self._tick(once=True)
    def _add_text(self, slot, pref_key):
        p = filedialog.askopenfilename(parent=self.app, title="Choose a text model file (.gguf)", filetypes=[("Text models", "*.gguf"), ("All files", "*.*")])
        if not p: return
        import learning_areas as LA
        if not LA.fits(self.app, "Shared models", [p]): return
        self.brain.add_file(slot, p, on_done=self._done("INSTALLED")); prefs.set(pref_key, slot)
        T.banner(self.app, "ADDED — reopen this page to see it in the list", "success")
    # ---- image and video models
    def _dl_images(self, key):
        e = self.cat.entry("AI Images", key) or self.cat.entry("Image edits", key)
        if key == "file" or (e and e.get("manual")): return T.banner(self.app, "ADD THIS ONE WITH ADD MANUALLY — choose its model file (.safetensors)", "busy")
        if self.cat.entry("AI Images", key) and key != "klein": self._select("model_AI_Images", key)
        self.imaging.download(on_done=self._done("INSTALLED"), key=key)
        quant, _ = self.cat.variant(e)
        T.banner(self.app, f"DOWNLOADING — the image engine and {e['label']}{f' ({quant}, the size that suits your card)' if key in ('zimage', 'klein') else ''}, "
                 f"about {self.imaging.download_size(key) / 1e9:.1f} GB; it's set up when it finishes", "success")
    def _add_image(self):
        p = filedialog.askopenfilename(parent=self.app, title="Choose an image model file", filetypes=[("Image models", "*.safetensors *.ckpt *.gguf"), ("All files", "*.*")])
        if not p: return
        import learning_areas as LA
        if not LA.fits(self.app, "Shared models", [p]): return
        self.imaging.add_file(p, on_done=self._done("INSTALLED")); self._select("model_AI_Images", "file")
    def _dl_video(self, key):
        import video_engine as V
        q = self.app.q
        def work():
            try:
                V.download()
                q.put(lambda: T.banner(self.app, "VIDEO MODEL READY — make videos in the AI Videos tab", "success"))
            except Exception as e: q.put(lambda e=e: T.banner(self.app, f"VIDEO DOWNLOAD DIDN'T FINISH — {e}", "error"))
        threading.Thread(target=work, daemon=True, name="video download").start()
        T.banner(self.app, "DOWNLOADING THE VIDEO MODEL — in the size that suits this PC", "success")
    def _add_video(self):
        import imaging
        p = filedialog.askopenfilename(parent=self.app, title="Choose a Wan 2.2 5B file (model .gguf, umt5 text reader .gguf or wan2.2_vae)",
                                       filetypes=[("Video model files", "*.safetensors *.gguf"), ("All files", "*.*")])
        if not p: return
        os.makedirs(imaging.VDIR, exist_ok=True); n = os.path.basename(p); low = n.lower()
        if not low.startswith(("wan2.2", "umt5")): n = ("umt5-" if "umt5" in low or "t5" in low else "wan2.2_vae-" if "vae" in low else "wan2.2-") + n
        if "vae" in low and low.endswith(".safetensors"): n = "wan2.2_vae.safetensors"
        shutil.copy(p, os.path.join(imaging.VDIR, n)); self._select("model_AI_Videos", "wan22")
        T.banner(self.app, f"ADDED — {n}", "success")

    def _switch(self, key):
        prefs.set("core_model", key)
        if self.brain.ready(): self.brain.stop()
        self._tick(once=True)
    def _start(self):
        """start the text model as a job in the AI line, so it never lands on the card while a picture is being painted"""
        import jobs
        if jobs.busy("Settings/start"): return T.banner(self.app, "BUSY — the text model is already starting", "busy")
        q = self.app.q; brain = self.brain
        jobs.submit("Settings", "Start the text model", lambda job: brain.start(), kind="text", page="Settings/start", engine=brain.core_key(),
                    on_done=lambda r: q.put(lambda: T.banner(self.app, "READY — " + brain.status()["detail"], "success")),
                    on_error=lambda e: q.put(lambda e=e: T.banner(self.app, f"COULDN'T START — {e}")))
    def _stop(self): self.brain.stop(); self._tick(once=True)
    def _tick(self, once=False):
        if not self.winfo_exists(): return
        st = self.brain.status(); ist = self.imaging.status()
        line = "TEXT: " + ("downloading (below)" if st["state"] == "downloading" else (st["detail"] or st["state"] or ""))
        if ist["state"] == "error": line += f"     IMAGES: {ist['detail']}"
        self.state.configure(text=line)
        for bar, x, who in ((self.text_bar, st, "TEXT"), (self.img_bar, ist, "IMAGES")):
            if x["state"] == "downloading":
                bar.set(x.get("progress") or None, f"{who}: " + (x["detail"] or "").replace("Downloading ", "")[:60])
                if not bar.winfo_manager(): bar.pack(anchor="w", pady=2)
            elif bar.winfo_manager(): bar.pack_forget()
        if not once: self.after(1000, self._tick)

# ---------------------------------------------------------------- AI Images: how the image generator works
class AIImagesPage(SettingsPage):
    TITLE = "AI Images"; NOTE = ("How the image generator works. Each AI Images section remembers its own last settings; these are the defaults and the "
                                 "engine's behaviour. The picture models themselves are in AI Models.")
    def build(self):
        import imaging, styles; self.im = imaging
        self.choice("Default style", "image_default_style", list(styles.BUILT_IN), "The style a section starts with (each section then remembers its own).")
        self.choice("Default size", "image_default_size", imaging.SIZES, "The shape new pictures start at. The pixels follow the model (1024 for Z-Image and FLUX.2, 512 for SD 1.5).")
        self.toggle("Live preview", "image_live_preview", "A rough picture of the run so far, shown while it paints.")
        self.toggle("Fuller descriptions", "image_improve_words", "Text to Image starts with the core text model writing a fuller description of your words.")
        self.toggle("Speed boost", "image_speed_boost", "Reuses work between similar steps: faster, with a little less fine detail.")
        self.toggle("Sharper Stable Diffusion", "image_sharper", "SD pictures get a second, bigger pass (hires fix): sharper and better-shaped, about twice as slow. On by default.")
        self.choice("Upscale every picture", "image_auto_upscale", ["Off", "2x", "4x"], "Each new picture comes out bigger and sharper (the upscaler downloads once, about 70 MB).")
        self.choice("Stop a stuck run after", "image_stall_minutes", ["5", "10", "20", "30"], "Minutes with no sign of life before the image engine is stopped, so the AI line moves on.")
        T.Text(self.body, "ADD-ONS", font=T.f(11)).pack(anchor="w", pady=(12, 2))
        self.rows = _frame(self.body); self.rows.pack(anchor="w", fill="x"); self._addons()


    def _addons(self):
        for w in self.rows.winfo_children(): w.destroy()
        info = {"upscale_photo": "Bigger, sharper photos (Upscale 2x / 4x).", "upscale_art": "Bigger, sharper art: cartoons, anime, line art.",
                "pose": "Pose to Image.", "outline": "Depth to Image: keep its outlines.", "depth": "Depth to Image: from a depth map.",
                "scribble": "Sketch to Image: follow my lines exactly."}
        for k, a in self.im.ADDON_FILES.items():
            r = _frame(self.rows); r.pack(fill="x", anchor="w", pady=2); here = self.im.addon(k); name = a["label"][4:] if a["label"].startswith("the ") else a["label"]
            T.Text(r, ("✓ " if here else "   ") + name.upper(), font=T.f(9), width=40, anchor="w").pack(side="left")
            T.Text(r, f"{a['size'] * 1000:.0f} MB" if a["size"] < 1 else f"{a['size']:.1f} GB", font=T.f(9), muted=True, width=8).pack(side="left")
            if here: T.Button(r, "Remove", lambda k=k: self._remove(k), kind="danger", width=8).pack(side="left", padx=4)
            else: T.Button(r, "Download", lambda k=k: self._get(k), width=10).pack(side="left", padx=4)
            T.Text(r, info.get(k, ""), muted=True, font=T.f(8)).pack(side="left", padx=6)
    def _get(self, k):
        q = self.app.q
        def done(ok, m): q.put(lambda: (T.banner(self.app, ("DOWNLOADED — " if ok else "DOWNLOAD FAILED — ") + m, "success" if ok else "error"), self.winfo_exists() and self._addons()))
        self.im.download(on_done=done, key=k); T.banner(self.app, f"DOWNLOADING — {self.im.ADDON_FILES[k]['label']}", "success")
    def _remove(self, k):
        try: os.remove(self.im.addon(k))
        except Exception as e: return T.banner(self.app, f"COULDN'T REMOVE IT — {e}")
        self._addons(); T.banner(self.app, "REMOVED", "success")


# ---------------------------------------------------------------- Templates (style add-ons)
class DownloadEverythingPage(SettingsPage):
    TITLE = "Download Everything"; NOTE = ("One download that puts every part of Pro on your AI drive: both engines, every text and coding model in every size, "
                                           "every picture model, the upscalers, guides and templates, the video and audio models, and the code checkers for AI Coding. "
                                           "Models too big for this PC are included, ready for when you upgrade; the app always runs the size that suits the PC "
                                           "it's on. What's already here is skipped, and a stopped download carries on where it left off.")
    def build(self):
        top = _frame(self.body); top.pack(fill="x", anchor="w", pady=(2, 6))
        self.go = skin.button(T.Button(top, "Download Everything", self._de_start, width=22)); self.go.pack(side="left")
        self.halt = T.Button(top, "Stop", self._de_stop, kind="danger", width=8); self.halt.pack(side="left", padx=8)
        T.Button(top, "Check again", self._de_list, width=12).pack(side="left")
        self.sum = T.Text(self.body, "", font=T.f(10)); self.sum.pack(anchor="w", pady=(2, 2))
        self.bar = T.ProgressBar(self.body, width=820, height=22); self.bar.pack(anchor="w", fill="x", pady=(2, 2))
        self.now = T.Text(self.body, "", muted=True, font=T.f(8)); self.now.pack(anchor="w")
        box = T.ScrollBox(self.body); box.pack(fill="both", expand=True, pady=(8, 0))
        self.list = tk.Text(box.body, wrap="none", relief="flat", font=T.f(9), padx=10, pady=6, highlightthickness=0, cursor="arrow", height=18)
        box.attach(self.list); self.list.pack(side="left", fill="both", expand=True)
        self.list.bind("<Key>", lambda e: None if (e.state & 4 and e.keysym.lower() in ("c", "a")) else "break")
        self._de_style(); T.on_change(self._de_style)
        self.after(150, self._de_list); self._de_tick()

    def _de_style(self):
        self.list.configure(bg=T.PALETTE["field"], fg="white")
        self.list.tag_configure("group", foreground=T.PALETTE["title"], font=T.f(10)); self.list.tag_configure("muted", foreground=T.PALETTE["muted"])
        self.list.tag_configure("ok", foreground="#5cd65c"); self.list.tag_configure("bad", foreground="#ff6b6b")

    def _de_list(self):
        """what's here and what isn't, by group (worked out in the background: it looks at a lot of files)"""
        import full_setup as FS, storage
        q = self.app.q
        def work():
            try:
                its = FS.items(); rows = [(i.group, i.label, i.gb, i.here(), i.note) for i in its]
                free, _ = storage.drive_free()
                q.put(lambda: self.winfo_exists() and self._de_show(rows, free))
            except Exception as e: q.put(lambda e=e: self.winfo_exists() and self.sum.configure(text=f"Couldn't read the list: {e}"))
        threading.Thread(target=work, daemon=True, name="download everything list").start()

    def _de_show(self, rows, free):
        import full_setup as FS
        failed = dict(FS.state.get("failed") or [])
        self.list.delete("1.0", "end"); group = None
        for g, label, gb, here, note in rows:
            if g != group:
                group = g; self.list.insert("end", ("\n" if self.list.index("end-1c") != "1.0" else "") + g.upper() + "\n", "group")
            mark, tag = ("✓ ", "ok") if here else (("✗ ", "bad") if label in failed else ("· ", "muted"))
            self.list.insert("end", "  " + mark, tag); self.list.insert("end", f"{label:<46}")
            self.list.insert("end", f"{gb:6.1f} GB" + (f"   {note}" if note else "") + ("   " + failed[label][:90] if label in failed and not here else "") + "\n", "muted")
        left = sum(r[2] for r in rows if not r[3]); total = sum(r[2] for r in rows); n = sum(1 for r in rows if not r[3])
        self.sum.configure(text=(f"{n} to download: {left:.0f} GB of {total:.0f} GB in all" if n else f"Everything is here ({total:.0f} GB)")
                                + (f"   ·   the AI drive has {free / 1e9:.0f} GB free" if free else ""))

    def _de_start(self):
        import full_setup as FS
        q = self.app.q
        def done(finished, failed):
            def show():
                msg = f"DOWNLOAD EVERYTHING — {len(finished)} downloaded" + (f", {len(failed)} didn't work (listed in red; tried again next time)" if failed else "")
                T.banner(self.app, msg, "error" if failed and not finished else "success")
                if self.winfo_exists(): self._de_list()
            q.put(show)
        if FS.start(on_done=done): T.banner(self.app, "DOWNLOADING EVERYTHING — one thing at a time; you can keep using the app", "success")
        else: T.banner(self.app, "IT'S ALREADY DOWNLOADING")

    def _de_stop(self):
        import full_setup as FS
        if FS.state["running"]: FS.stop(); T.banner(self.app, "STOPPING — the file in progress carries on from there next time")

    def _de_tick(self):
        if not self.winfo_exists(): return
        import full_setup as FS
        st = FS.state
        if st["running"]:
            self.bar.set(st["fraction"] or None, st["text"][:90]); self.now.configure(text=st["item"])
        elif st["total"] or st["failed"]:
            self.bar.set(1.0 if not st["stop"] else st["fraction"], st["text"]); self.now.configure(text=f"{st['done']} of {st['total']} done")
        self.after(500, self._de_tick)


class StyleAddonsPage(SettingsPage):
    TITLE = "Templates"; NOTE = ("Templates: ready-made styles other people trained, one per style. Each is made for one image or video model and is used "
                                     "whenever that model paints in its style, while it's switched on; without one, the style's own words do the job. "
                                     "Add your own (a character, a thing, a look) from a link, for any model Pro runs: it shows up as a style everywhere.")
    def build(self):
        top = _frame(self.body); top.pack(anchor="w", pady=(4, 8))
        T.Button(top, "Get them all", self._sa_all, width=14).pack(side="left")
        T.Button(top, "Add your own…", self._sa_add, width=16).pack(side="left", padx=6)
        self.sa_rows = _frame(self.body); self.sa_rows.pack(anchor="w", fill="x"); self._sa_list()

    def _sa_list(self):
        import style_addons as SA, imaging
        for w in self.sa_rows.winfo_children(): w.destroy()
        now = imaging.kind(); group = None
        for style, e in sorted(SA.entries().items(), key=lambda kv: (list(SA.BASES).index(SA.base_of(kv[1])) if SA.base_of(kv[1]) in SA.BASES else 9)):
            base = SA.base_of(e)
            if base != group:
                group = base; _rule(self.sa_rows)
                T.Text(self.sa_rows, f"FOR {SA.BASES.get(base, base).upper()}" + ("   (the model you paint with now)" if base == now else ""),
                       font=T.f(10)).pack(anchor="w", pady=(4, 2))
            r = _frame(self.sa_rows); r.pack(fill="x", anchor="w", pady=2); here = SA.installed(style)
            v = tk.BooleanVar(value=SA.enabled(style))
            T.Toggle(r, v, command=lambda s=style, v=v: (SA.set_enabled(s, v.get()), T.banner(self.app, f"{s.upper()} TEMPLATE {'ON' if v.get() else 'OFF'}", "success"))).pack(side="left", padx=(0, 6))
            T.Text(r, ("✓ " if here else "   ") + style.upper(), font=T.f(9), width=30, anchor="w").pack(side="left")
            if here: T.Button(r, "Remove", lambda s=style: (SA.remove(s), self._sa_list()), kind="danger", width=8).pack(side="left", padx=4)
            else: T.Button(r, "Download", lambda s=style: self._sa_get(s), width=10).pack(side="left", padx=4)
            if e.get("own"): T.Button(r, "Forget", lambda s=style: (SA.forget_own(s), self._sa_list()), kind="danger", width=8).pack(side="left", padx=4)
            T.Text(r, e.get("note", ""), muted=True, font=T.f(8)).pack(side="left", padx=6)
    def _sa_get(self, style, quiet=False):
        import style_addons as SA; q = self.app.q
        def done(ok, m): q.put(lambda: (T.banner(self.app, ("TEMPLATE READY — " if ok else "TEMPLATE DOWNLOAD FAILED — ") + m, "success" if ok else "error"),
                                        self.winfo_exists() and self._sa_list(), self._sa_next()))
        SA.download(style, on_done=done)
        if not quiet: T.banner(self.app, f"DOWNLOADING THE {style.upper()} TEMPLATE", "success")
    def _sa_all(self):
        import style_addons as SA
        self._sa_queue = [s for s in SA.entries() if not SA.installed(s)]
        if not self._sa_queue: return T.banner(self.app, "YOU HAVE THEM ALL", "success")
        T.banner(self.app, f"DOWNLOADING {len(self._sa_queue)} TEMPLATES — one after another", "success"); self._sa_next()
    def _sa_next(self):
        if getattr(self, "_sa_queue", None): self._sa_get(self._sa_queue.pop(0), quiet=True)
    def _sa_add(self):
        """your own pick: a Hugging Face link, which style it's for, its trigger words"""
        import style_addons as SA, styles
        win = tk.Toplevel(self.app); win.title("Add a template"); win.configure(bg=T.PALETTE["panel"]); win.transient(self.app)
        f = _frame(win); f.pack(padx=16, pady=14)
        vals = {}
        for key, label, default in (("link", "Link to the template (a LoRA)", ""), ("style", "Style name (an existing one, or a new one)", ""),
                                    ("trigger", "Trigger words (from its page; blank if none)", ""), ("weight", "Strength (0.6 gentle - 1.0 strong)", "0.9")):
            T.Text(f, label.upper(), font=T.f(9)).pack(anchor="w", pady=(6, 2)); v = tk.StringVar(value=default); vals[key] = v
            tk.Entry(f, textvariable=v, width=52, bg=T.PALETTE["field"], fg="white", insertbackground="white", relief="flat").pack(anchor="w")
        T.Text(f, "MADE FOR", font=T.f(9)).pack(anchor="w", pady=(8, 2))
        names = ["Read it from the page"] + list(SA.BASES.values()); base = tk.StringVar(value=names[0])
        T.Choice(f, "", names, base).pack(anchor="w")
        T.Text(f, "A template only works with the model it was made for: its page says which ('base model'). When the page says it, "
                  "that's read for you; otherwise pick it (Z-Image Turbo if you don't).", muted=True, font=T.f(8), wraplength=420, justify="left").pack(anchor="w", pady=(4, 0))
        T.Text(f, "SITE KEY  (only for files that need you signed in: an API key from your account settings on that site)", font=T.f(9)).pack(anchor="w", pady=(8, 2))
        key = tk.StringVar(value=prefs.get("civitai_key") or "")
        tk.Entry(f, textvariable=key, width=52, show="•", bg=T.PALETTE["field"], fg="white", insertbackground="white", relief="flat").pack(anchor="w")
        def ok():
            try:
                w = float(vals["weight"].get() or 0.9); st = vals["style"].get().strip()
                if not st: raise RuntimeError("give it a style name")
                prefs.set("civitai_key", key.get().strip())
                b = next((k for k, n in SA.BASES.items() if n == base.get()), None)
                if b is None and "civitai.com" not in vals["link"].get(): b = "zimage"
                SA.add_own(st, vals["link"].get(), vals["trigger"].get(), w, base=b); win.destroy(); self._sa_list(); self._sa_get(st)
            except Exception as ex: T.banner(self.app, f"COULDN'T ADD IT — {ex}")
        b = _frame(f); b.pack(anchor="w", pady=(10, 0)); T.Button(b, "Add and download", ok).pack(side="left"); T.Button(b, "Cancel", win.destroy).pack(side="left", padx=6)
class CodeLanguagesPage(SettingsPage):
    TITLE = "Code Languages"; NOTE = ("The languages AI Coding works out from your questions. Each has its own setup: how you write it (style, libraries "
                                      "and versions, things to avoid), its own library it looks things up in, and a checker that compiles its code before "
                                      "you see it. Switch off the ones you don't use and it never picks them.")
    def build(self):
        top = _frame(self.body); top.pack(anchor="w", pady=(2, 6))
        T.Button(top, "Look for checkers again", lambda: (__import__("code_helpers").rescan(), self._cl_list()), width=24).pack(side="left")
        self.cl_rows = _frame(self.body); self.cl_rows.pack(anchor="w", fill="x"); self._cl_list()

    def _cl_list(self):
        import code_helpers as CH
        for w in self.cl_rows.winfo_children(): w.destroy()
        have = CH.available()
        for lang in CH.LANGS:
            r = _frame(self.cl_rows); r.pack(fill="x", anchor="w", pady=2)
            v = tk.BooleanVar(value=CH.enabled(lang))
            T.Toggle(r, v, command=lambda l=lang, v=v: CH.set_enabled(l, v.get())).pack(side="left", padx=(0, 6))
            T.Text(r, lang.upper(), font=T.f(9), width=14, anchor="w").pack(side="left")
            T.Button(r, "How I write it", lambda l=lang: self._cl_profile(l), width=14).pack(side="left", padx=4)
            try: n = len([f for _, _, fs in os.walk(os.path.join(CH.folder(lang), "library")) for f in fs])
            except Exception: n = 0
            how = have.get(lang, ""); how = "the app itself" if how == "built in" else how
            T.Text(r, (f"checked with {how}" if how else "no checker on this PC") + (f"   ·   {n} files in its library" if n else ""),
                   muted=True, font=T.f(8)).pack(side="left", padx=8)

    def _cl_profile(self, lang):
        import code_helpers as CH, workspace_page as WP
        f = CH.profile_file(lang)
        def save(text):
            with open(f, "w", encoding="utf-8") as fh: fh.write(text)
        WP.Editor(self.app, f"How you write {lang}", f"Your {lang} style, the libraries and versions you use, and what it must never do. "
                  f"In every {lang} request, in every project.", CH.profile(lang), save)


# ---------------------------------------------------------------- Updates
REPO = "StevenCLewis111/Instant-Easel"
class UpdatesPage(SettingsPage):
    TITLE = "Updates"; NOTE = "Checks GitHub for a newer InstantEaselPro.exe. Nothing is downloaded or installed without asking."
    def build(self):
        import main
        T.Text(self.body, f"THIS VERSION: {main.VERSION}", font=T.f(11)).pack(anchor="w", pady=(0, 8))
        self.toggle("Check for updates when the app opens", "check_updates_on_start", "Off by default: the app only goes online when you ask it to.")
        self.buttons(("Check now", self.check, "normal")); self.msg = T.Text(self.body, "", font=T.f(10)); self.msg.pack(anchor="w")
    def check(self):
        self.msg.configure(text="CHECKING…")
        def work():
            import urllib.request
            try:
                with urllib.request.urlopen(f"https://api.github.com/repos/{REPO}/releases/latest", timeout=8) as r: tag = json.load(r).get("tag_name", "?")
                msg = f"LATEST RELEASE ON GITHUB: {tag}"; T.banner(self.app, f"UPDATE CHECK DONE — latest release on GitHub: {tag}", "success")
            except Exception as e:
                msg = ("NO PUBLIC RELEASE FOUND. While the repository is private, download new versions from its Releases page on GitHub "
                       "while signed in.") if "404" in str(e) else f"COULDN'T REACH GITHUB ({e.__class__.__name__}). CHECK YOUR CONNECTION."
                T.banner(self.app, "NO PUBLIC RELEASE FOUND — download new versions from the Releases page on GitHub" if "404" in str(e) else f"CAN'T CHECK FOR UPDATES — couldn't reach GitHub ({e.__class__.__name__})")
            self.app.q.put(lambda: self.msg.configure(text=msg, wraplength=800))
        threading.Thread(target=work, daemon=True).start()

# ---------------------------------------------------------------- Shortcuts
SHORTCUTS = [("Anywhere", [("F11", "full screen on / off"), ("Esc", "leave full screen"), ("Tab / Enter", "move between buttons / press"), ("Mouse wheel", "scroll when the window is small")]),
             ("Text to Image", [("Ctrl+Enter", "generate")]), ("Image to Image", [("Enter", "repaint")]),
             ("Draw studio", [("B / E / I / G / L / T", "brush, eraser, eyedropper, fill, line, text"), ("[  ]", "smaller / bigger brush"),
                              ("Ctrl+Z / Ctrl+Y", "undo / redo"), ("Mouse wheel", "zoom"), ("Right-drag", "pan")]),
             ("Editing", [("Double-click a slider", "reset it")])]
FIXED_DRAW_KEYS = [("Ctrl+Z / Ctrl+Y", "undo / redo"), ("Ctrl+C / X / V", "copy / cut / paste the selection"), ("Ctrl+A / Ctrl+D", "select all / nothing"),
                   ("Ctrl+T", "free transform (Enter keeps, Esc puts back)"), ("Shift + click", "straight line from the last stroke"),
                   ("Shift (shapes)", "15-degree lines, squares, circles"), ("Mouse wheel", "zoom where the mouse is"), ("Right-drag", "pan"),
                   ("Shift + right-drag", "turn the view"), ("Esc", "studio back to normal size")]
class ShortcutsPage(SettingsPage):
    TITLE = "Shortcuts"; NOTE = "Drawing keys: click one, then press the key you want (Backspace = none, Esc = keep it)."
    def build(self):
        T.Text(self.body, "ANYWHERE", font=T.f(10)).pack(anchor="w", pady=(8, 2))
        for k, what in SHORTCUTS[0][1]: T.Text(self.body, f"   {k:<26} {what}", font=T.f(9)).pack(anchor="w")
        T.Text(self.body, "DRAWING (click to change)", font=T.f(10)).pack(anchor="w", pady=(10, 2))
        self._rows = tk.Frame(self.body, bg=self.body["bg"]); self._rows.pack(anchor="w", fill="x"); T.on_change(lambda: self._rows.configure(bg=self.body["bg"]))
        self._waiting = None; self._fill()
        self.buttons(("Reset drawing keys", self._reset, "danger"))
    def _fill(self):
        import draw_studio as DS
        for w in self._rows.winfo_children(): w.destroy()
        m = DS.key_map(); self._btns = {}
        for i, (a, what, _) in enumerate(DS.KEY_ACTIONS):
            c, r = divmod(i, 9)
            cell = tk.Frame(self._rows, bg=self._rows["bg"]); cell.grid(row=r, column=c, sticky="w", padx=(0, 24), pady=1); T.on_change(lambda cell=cell: cell.configure(bg=self._rows["bg"]))
            b = T.Button(cell, DS.key_label(m.get(a, "")), lambda a=a: self._ask(a), width=6); b.pack(side="left"); self._btns[a] = b
            T.Text(cell, what, font=T.f(9)).pack(side="left", padx=6)
        fx = tk.Frame(self._rows, bg=self._rows["bg"]); fx.grid(row=0, column=2, rowspan=9, sticky="nw", padx=(16, 0)); T.on_change(lambda: fx.configure(bg=self._rows["bg"]))
        T.Text(fx, "ALWAYS", font=T.f(9)).pack(anchor="w")                     # the keys that can't be changed, beside the ones that can
        for k, what in FIXED_DRAW_KEYS: T.Text(fx, f"{k:<20} {what}", font=T.f(8)).pack(anchor="w")
    def _ask(self, a):
        self._waiting = a; self._btns[a].configure(text="press…"); top = self.winfo_toplevel()
        self._kb = top.bind("<KeyPress>", self._got, add="+"); top.focus_set()
    def _got(self, e):
        a = self._waiting
        if a is None: return
        k = e.keysym
        if k in ("Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Caps_Lock", "Super_L", "Super_R", "Win_L", "Win_R"): return
        self._waiting = None
        try: self.winfo_toplevel().unbind("<KeyPress>", self._kb)
        except Exception: pass
        if k == "Escape": self._fill(); return "break"
        import json, paths, draw_studio as DS
        k = "" if k in ("BackSpace", "Delete") else (k.lower() if len(k) == 1 else k)
        m = DS.key_map()
        if k:
            for other, kk in list(m.items()):
                if kk == k and other != a: m[other] = ""                      # the key moves here from what had it
        m[a] = k
        try:
            with open(paths.json_file("draw_keys.json"), "w", encoding="utf-8") as f: json.dump(m, f, indent=1)
        except Exception: pass
        for st in DS.STUDIOS: st.rebind_keys()
        self._fill(); return "break"
    def _reset(self):
        import paths, draw_studio as DS
        try: os.remove(paths.json_file("draw_keys.json"))
        except OSError: pass
        for st in DS.STUDIOS: st.rebind_keys()
        self._fill()

# ---------------------------------------------------------------- Backup & reset
BACKUP_FILES = ["instant_easel_settings.json", "instant_easel_theme.json", "learning_settings.json"]

def _data_file(name):
    """where one of the app's own files lives: .json files in .json/, logs in logs/"""
    import paths
    return paths.json_file(name) if name.endswith(".json") else paths.log_file(name) if name.endswith((".log", ".txt")) else paths.data(name)
class BackupPage(SettingsPage):
    TITLE = "Backup & Reset"; NOTE = "Move your setup to another PC: settings, theme and what each AI tab was taught, in one file (no pictures or models)."
    def build(self):
        self.buttons(("Export backup…", self.export, "normal"), ("Import backup…", self.restore, "normal"))
        self.msg = T.Text(self.body, "", font=T.f(10)); self.msg.pack(anchor="w", pady=6)
        T.Text(self.body, "RESET", font=T.f(10)).pack(anchor="w", pady=(16, 2))
        self.buttons(("Reset all settings", self.reset, "danger"))
    def _learned(self):
        import brain; lib = brain.TABS_DIR
        return glob.glob(os.path.join(lib, "*", "examples.jsonl")), lib
    def export(self):
        p = filedialog.asksaveasfilename(parent=self.app, defaultextension=".zip", initialfile="instant-easel-pro-backup.zip", filetypes=[("Backup", "*.zip")])
        if not p: return
        learned, lib = self._learned()
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
            for f in BACKUP_FILES:
                src = _data_file(f)
                if os.path.exists(src): z.write(src, f)
            for f in learned: z.write(f, "tabs/" + os.path.relpath(f, lib).replace(os.sep, "/"))
        self.msg.configure(text=f"SAVED: {os.path.basename(p)}"); T.banner(self.app, f"EXPORTED — {os.path.basename(p)}", "success")
    def restore(self):
        p = filedialog.askopenfilename(parent=self.app, filetypes=[("Backup", "*.zip")])
        if not p: return
        import brain; lib = brain.TABS_DIR
        with zipfile.ZipFile(p) as z:
            for n in z.namelist():
                if ".." in n or n.startswith("/"): continue                                       # only our own files, nowhere else
                dest = os.path.join(lib, n[len("tabs/"):]) if n.startswith("tabs/") else _data_file(os.path.basename(n))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with z.open(n) as src, open(dest, "wb") as out: out.write(src.read())
        self.msg.configure(text="RESTORED. CLOSE AND REOPEN THE APP TO USE EVERYTHING."); T.banner(self.app, "IMPORTED — close and reopen the app to use everything", "success")
    def reset(self):
        if T.popup(self.app, "RESET ALL SETTINGS?", "Every setting goes back to its default. What the AI tabs learned, your models and your images are kept.",
                   (("Reset", "danger"), ("Cancel", "normal"))) == "Reset":
            prefs.reset_all(); T.banner(self.app, "SETTINGS RESET — close and reopen the app to finish", "success")


# ---------------------------------------------------------------- Pen & Tablet
class DrawingAIPage(SettingsPage):
    TITLE = "Drawing AI"; NOTE = ("The AI models the Drawing tab's smart tools use. None come with the app: download any of them here (or all at once), "
                                  "or the tool asks the first time you use it. Add your own uses an ONNX model file of yours instead. "
                                  "They run on your PC only: no picture is ever sent anywhere.")
    def build(self):
        import threading
        top = _frame(self.body); top.pack(anchor="w", pady=(2, 8))
        T.Button(top, "Download all", self._da_all, width=14).pack(side="left")
        if hasattr(T, "ProgressBar"): self.da_bar = T.ProgressBar(self.body, width=600, height=20)
        else:                                                                    # (no bar widget here: a line that says how far it is)
            self.da_bar = T.Text(self.body, "", font=T.f(9))
            self.da_bar.set = lambda frac, text: self.da_bar.configure(text=text.upper() + (f"  {frac * 100:.0f}%" if frac else ""))
        self.da_rows = _frame(self.body); self.da_rows.pack(anchor="w", fill="x"); self._da_list()

    def _da_list(self):
        import ai_cutout as AI
        for w in self.da_rows.winfo_children(): w.destroy()
        for kind, (name, what) in AI.KINDS.items():
            r = _frame(self.da_rows); r.pack(fill="x", anchor="w", pady=3); here = AI.have(kind)
            T.Text(r, ("✓ " if here else "   ") + name.upper(), font=T.f(9), width=38, anchor="w").pack(side="left")
            if here: T.Button(r, "Remove", lambda k=kind: (AI.remove(k), self._da_list()), kind="danger", width=8).pack(side="left", padx=4)
            else: T.Button(r, f"Download ({AI.download_size(kind) / 1e6:.0f} MB)", lambda k=kind: self._da_get([k]), width=18).pack(side="left", padx=4)
            T.Button(r, "Add your own…", lambda k=kind: self._da_own(k), width=14).pack(side="left", padx=4)
            T.Text(r, what, muted=True, font=T.f(8)).pack(side="left", padx=6)

    def _da_all(self):
        import ai_cutout as AI
        todo = [k for k in AI.KINDS if not AI.have(k)]
        if not todo: return T.banner(self.app, "YOU HAVE THEM ALL", "success")
        self._da_get(todo)

    def _da_get(self, kinds):
        import ai_cutout as AI, threading
        q = self.app.q; self.da_bar.pack(before=self.da_rows, anchor="w", pady=(0, 6))
        def work():
            done = []
            for k in kinds:
                name = AI.KINDS[k][0]
                try:
                    AI.ensure(k, lambda d, t, n=name: q.put(lambda: self.da_bar.winfo_exists() and self.da_bar.set(d / t if t else None, f"Downloading the {n} model…")))
                    done.append(name)
                except Exception as e: q.put(lambda e=e, n=name: T.banner(self.app, f"{n.upper()} DIDN'T DOWNLOAD — {e}", "error"))
            def end():
                if self.winfo_exists(): self.da_bar.pack_forget(); self._da_list()
                if done: T.banner(self.app, "READY — " + ", ".join(done), "success")
            q.put(end)
        threading.Thread(target=work, daemon=True, name="drawing ai download").start()

    def _da_own(self, kind):
        import ai_cutout as AI
        names = AI.file_names(kind); files = []
        for n in names:
            f = filedialog.askopenfilename(parent=self.app, title=f"Your model to use as {n}", filetypes=[("ONNX models", "*.onnx"), ("All files", "*.*")])
            if not f: return
            files.append(f)
        try: AI.add_own(kind, files); T.banner(self.app, f"ADDED — {AI.KINDS[kind][0]} uses your model now", "success")
        except Exception as e: T.banner(self.app, f"COULDN'T ADD IT — {e}", "error")
        self._da_list()


class PenPage(SettingsPage):
    TITLE = "Pen & Tablet"; NOTE = ("A drawing tablet or pen screen (Wacom, XP-Pen, Huion, Surface Pen...) draws with its real pressure: press lightly "
                                    "for thin, light lines, harder for full ones (each brush's Pr. Size / Pr. Opac say how much). A mouse is left alone; "
                                    "for a mouse, Brush Options > Pressure (by speed) fakes it.")
    def build(self):
        self.toggle("Use pen pressure", "pen_pressure", "Off: a pen draws at full strength, like a mouse.")
        self.choice("Pressure feel", "pen_feel", ["Soft", "Normal", "Firm"], "Soft: light touches already count a lot. Firm: you press harder for full strength.")
        self.toggle("Pen's eraser end erases", "pen_eraser", "Turn the pen over and it picks the Eraser; back to the tip, your tool again.")
        r = self.row("Try your pen here", "Draw on the strip: the bar shows the pressure Windows is sending.")
        import pen_input
        self.pad = tk.Canvas(r, width=420, height=70, bg=T.PALETTE["field"], highlightthickness=2, highlightbackground=T.PALETTE["border"], cursor="pencil")
        self.pad.pack(side="left"); self.state = T.Text(self.body, "", font=T.f(9)); self.state.pack(anchor="w", pady=(6, 0))
        self.pen = pen_input.attach(self.pad); self.pen.listeners.append(lambda s: self.after_idle(self.show))
        self.pad.bind("<B1-Motion>", lambda e: self.show(e)); self.pad.bind("<ButtonRelease-1>", lambda e: self.after(300, self.show))
        T.Text(self.body, "   No pressure? In your tablet's own settings (Wacom / XP-Pen / Huion), make sure Windows Ink is switched on:\n"
               "   that's what Instant Easel (and Photoshop, by default) listens to.", muted=True, font=T.f(8)).pack(anchor="w", pady=(8, 0))
        self.show()
    def show(self, e=None):
        if not self.winfo_exists(): return
        import pen_input
        p = self.pen; c = self.pad; c.delete("bar")
        if not p.ok: self.state.configure(text=f"PEN PRESSURE ISN'T AVAILABLE HERE — {p.why}"); return
        if not p.seen:
            self.state.configure(text="NO PEN SEEN YET — draw on the strip with your pen" + ("  (that's the mouse: no pressure)" if e is not None else "")); return
        pr = pen_input.feel(p.pressure, prefs.get("pen_feel")) if p.live() else 0
        c.create_rectangle(4, 4, 4 + pr * 410, 66, fill=T.PALETTE["border"], outline="", tags="bar")
        c.create_text(210, 35, text=f"{int(p.pressure * 100)}% pressed" + ("   (eraser end)" if p.eraser else ""), fill="white", font=T.f(10), tags="bar")
        self.state.configure(text="PEN FOUND — pressure is working" if p.live() else "PEN FOUND — lift and draw again to see the pressure")

