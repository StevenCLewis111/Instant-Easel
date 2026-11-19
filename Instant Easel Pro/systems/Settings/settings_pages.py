"""
settings_pages.py: Instant Easel Pro's Settings pages. Every value lives in prefs.py (instant_easel_settings.json next to the app).
"""
import os, sys, json, glob, shutil, zipfile, platform, subprocess, threading, tkinter as tk
from tkinter import filedialog
import theme as T, prefs

def _frame(parent):
    f = tk.Frame(parent, bg=parent["bg"]); T.on_change(lambda: f.configure(bg=f.master["bg"])); return f

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
        for text, cmd, kind in items: T.Button(r, text, cmd, kind=kind).pack(side="left", padx=(0, 8))
        return r

# ---------------------------------------------------------------- General
class GeneralPage(SettingsPage):
    TITLE = "General"; NOTE = "Where your work is saved, in what format, and how the app starts and closes."
    def build(self):
        c = self.row("Your work folder", "images, videos, code and chats folders inside it. Every tab saves its work there and opens from there. "
                     "Normally the folder of the app you launched (the project folder, or EXE Build for the .exe).")
        self.folder_lbl = T.Text(c, prefs.work_root(), font=T.f(9)); self.folder_lbl.pack(side="left", padx=(0, 8))
        T.Button(c, "Change", self.pick).pack(side="left"); T.Button(c, "App's own folder", self.own).pack(side="left", padx=(6, 0)); T.Button(c, "Open", lambda: prefs.open_folder(prefs.work_root())).pack(side="left", padx=6)
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
        T.Button(c, "Open", lambda: prefs.open_folder(paths.ai_root())).pack(side="left")
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
                              + ("" if catalog.can("AI Videos") else "Making videos needs a graphics card with 16 GB or more, so the AI Videos tab is hidden."),
                              muted=True, font=T.f(9)); self.pc_note.configure(wraplength=900); self.pc_note.pack(anchor="w", padx=(30, 0))
        head("CORE TEXT MODEL  (every AI tab uses it)")
        cores = self._choices("core", custom=("custom-core", "Your own model file (core)"))
        cur = brain.core_key() if brain.core_key() in cores else self._default("core", cores)
        self._row_with("CORE", "built", "core_model", cores, cur, download=self._dl_text, add=lambda: self._add_text("custom-core", "core_model"), speed="speed_text")
        r = _frame(self.body); r.pack(anchor="w", padx=(30, 0), pady=(2, 0))
        T.Button(r, "Start", self._start, width=7).pack(side="left", padx=(0, 4)); T.Button(r, "Stop", self._stop, kind="danger", width=6).pack(side="left", padx=4)
        self.state = T.Text(r, "", font=T.f(10)); self.state.pack(side="left", padx=10)
        head("EACH TAB'S MODEL")
        chat = {"core": ("Core text model (recommended)", "AI Chat talks to the core model.")}
        if brain.model_file("custom-AI_Chat"): chat["custom-AI_Chat"] = ("Your own model file", "A .gguf text model you added with Add manually.")
        self._row_with("AI CHAT", "built", "model_AI_Chat", chat, prefs.get("model_AI_Chat") if prefs.get("model_AI_Chat") in chat else "core",
                       download=lambda k: self._dl_text(brain.core_key()), add=lambda: self._add_text("custom-AI_Chat", "model_AI_Chat"))
        coding = self._choices("AI Coding", custom=("custom-AI_Coding", "Your own model file"))
        coding["core"] = ("Core text model", "The core model writes and explains code too.")
        self._row_with("AI CODING", "built", "model_AI_Coding", coding, prefs.get("model_AI_Coding") if prefs.get("model_AI_Coding") in coding else self._default("AI Coding", coding),
                       download=lambda k: self._dl_text(brain.core_key() if k == "core" else k), add=lambda: self._add_text("custom-AI_Coding", "model_AI_Coding"))
        images = self._choices("AI Images", custom=("file", "Your own model file"))
        self._row_with("AI IMAGES", "built", "model_AI_Images", images, imaging.choice() if imaging.choice() in images else self._default("AI Images", images),
                       download=self._dl_images, add=self._add_image, folder=imaging.IMAGE, speed="speed_image")
        T.Text(self.body, "SPEED: Fast puts everything on the graphics card. Balanced lets the engine fit the model to the card's free memory. Safe keeps "
               "more in PC memory: slower, but big models fit. Before every run the app checks the free memory and steps down by itself (Fast → "
               "Balanced → Safe), and if a run still runs out of memory it's tried again in Safe instead of failing.", muted=True, font=T.f(8),
               wraplength=900).pack(anchor="w", pady=(8, 0))
        if catalog.can("AI Videos"):
            videos = self._choices("AI Videos", custom=("file", "Your own model file"))
            self._row_with("AI VIDEOS", "planned", "model_AI_Videos", videos, prefs.get("model_AI_Videos") if prefs.get("model_AI_Videos") in videos else self._default("AI Videos", videos),
                           download=self._dl_video, add=self._add_video, folder=os.path.join(brain.ROOT, "video"))
        self._tick()

    # ---- what's offered: the models that fit this PC (best first), plus any you already downloaded
    def _choices(self, area, custom=None):
        out = {}; best = self.cat.best(area)
        for e in self.cat.options(area):
            tag = " (best for your PC)" if best and e["key"] == best["key"] else ""
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
        if area == "AI Images":
            if key == "zimage": return bool(self.imaging.zimage_parts())
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
        if folder: T.Button(r, "Open folder", lambda: prefs.open_folder(folder), width=11).pack(side="left", padx=4)
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
        e = self.cat.entry("AI Images", key)
        if key == "file" or (e and e.get("manual")): return T.banner(self.app, "ADD THIS ONE WITH ADD MANUALLY — choose its model file (.safetensors)", "busy")
        self._select("model_AI_Images", key); self.imaging.download(on_done=self._done("INSTALLED"), key=key)
        quant, _ = self.cat.variant(e)
        T.banner(self.app, f"DOWNLOADING — the image engine and {e['label']}{f' ({quant}, the size that suits your card)' if key == 'zimage' else ''}, "
                 f"about {self.imaging.download_size(key) / 1e9:.1f} GB; it's set up when it finishes", "success")
    def _add_image(self):
        p = filedialog.askopenfilename(parent=self.app, title="Choose an image model file", filetypes=[("Image models", "*.safetensors *.ckpt *.gguf"), ("All files", "*.*")])
        if not p: return
        import learning_areas as LA
        if not LA.fits(self.app, "Shared models", [p]): return
        self.imaging.add_file(p, on_done=self._done("INSTALLED")); self._select("model_AI_Images", "file")
    def _dl_video(self, key):
        T.popup(self.app, "VIDEO MAKING ISN'T BUILT YET", "Your PC can run the video model, but making videos is still being built.\n"
                "Nothing was downloaded. When it's ready, this button will install it.", (("OK", "normal"),))
    def _add_video(self):
        p = filedialog.askopenfilename(parent=self.app, title="Choose a video model file", filetypes=[("Video models", "*.safetensors *.gguf"), ("All files", "*.*")])
        if not p: return
        d = os.path.join(self.brain.ROOT, "video"); os.makedirs(d, exist_ok=True); shutil.copy(p, d); self._select("model_AI_Videos", "file")
        T.banner(self.app, f"KEPT — {os.path.basename(p)} is ready for when video making is built", "success")

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
        pct = lambda x: f" ({x['progress'] * 100:.0f}%)" if x["state"] == "downloading" and x.get("progress") else ""
        line = f"TEXT: {st['detail'] or st['state'] or ''}{pct(st)}"
        if ist["state"] in ("downloading", "error"): line += f"     IMAGES: {ist['detail']}{pct(ist)}"
        self.state.configure(text=line)
        if not once: self.after(1000, self._tick)

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
class ShortcutsPage(SettingsPage):
    TITLE = "Shortcuts"
    def build(self):
        for group, items in SHORTCUTS:
            T.Text(self.body, group.upper(), font=T.f(10)).pack(anchor="w", pady=(8, 2))
            for k, what in items: T.Text(self.body, f"   {k:<26} {what}", font=T.f(9)).pack(anchor="w")

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
