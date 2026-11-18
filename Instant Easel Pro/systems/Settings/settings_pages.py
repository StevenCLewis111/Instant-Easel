"""
settings_pages.py: Instant Easel's Settings pages. Every value lives in prefs.py (instant_easel_settings.json next to the app).
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
        c = self.row("Your work folder", "Images, Videos, Code and Chats each have a folder inside it. Every tab saves its work there and opens "
                     "from there, so anything one tab makes is easy to pick up in another.")
        self.folder_lbl = T.Text(c, prefs.get("save_folder"), font=T.f(9)); self.folder_lbl.pack(side="left", padx=(0, 8))
        T.Button(c, "Change", self.pick).pack(side="left"); T.Button(c, "Open", lambda: prefs.open_folder(prefs.work_root())).pack(side="left", padx=6)
        self.choice("File format", "save_format", ["PNG", "JPEG", "WebP"], "PNG keeps every detail (larger files). JPEG and WebP are smaller.")
        self.choice("JPEG / WebP quality", "jpeg_quality", ["75", "85", "92", "100"])
        self.entry("File names", "name_pattern", note="{date}, {time} and {n} (number) are filled in. Example: instant-easel-2026-11-15-163000-1.png")
        self.choice("Open on start", "start_tab", ["Drawing", "AI Images", "AI Videos", "AI Chat", "AI Coding", "AI Training", "Editing", "Settings", "Last used"])
        self.toggle("Confirm before quitting", "confirm_exit")
        self.buttons(("Create desktop shortcut", self.shortcut, "normal"))
    def shortcut(self):
        """a desktop shortcut with the Instant Easel icon"""
        try:
            import shortcut; path = shortcut.make(); T.banner(self.app, f"SHORTCUT CREATED — {os.path.basename(path)} is on your desktop", "success")
        except Exception as e: T.banner(self.app, f"COULDN'T MAKE THE SHORTCUT — {e}")
    def pick(self):
        d = filedialog.askdirectory(parent=self.app, initialdir=prefs.get("save_folder"))
        if d: prefs.set("save_folder", d); self.folder_lbl.configure(text=d)

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
    TITLE = "Privacy & Data"; NOTE = ("Instant Easel works offline. Your prompts, pictures and everything the AI tabs learn stay on this PC. The internet "
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
                ("Your work folder (images, videos, code, chats)", prefs.folder_size(prefs.get("save_folder")) if os.path.isdir(prefs.get("save_folder")) else 0)]
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
    import paths; d = paths.data(*p); os.makedirs(d, exist_ok=True); return d

# ---------------------------------------------------------------- AI models: the core text model + each tab's own model
IMAGE_MODELS = {"sd15": ("Stable Diffusion 1.5", "2.1 GB. Runs on a 6 GB card, and your image models (Cartoon, Fashion...) train on top of it."),
                "sdxl": ("Stable Diffusion XL", "Sharper pictures, but needs about 8 GB; on a 6 GB card it's slow and can't be trained."),
                "file": ("A model file you add", "Any .safetensors image model; put it here with Add a model file.")}
VIDEO_MODELS = {"none": ("None yet", "Making videos needs a video model and a graphics card with 16 GB or more (or a rented one online)."),
                "wan22": ("Wan 2.2 5B", "The smallest good video model; needs about 16 GB. Saved as your choice for later.")}

class AIModelsPage(SettingsPage):
    TITLE = "AI Models"; NOTE = ("One core text model understands you in every AI tab; switch between 4B and 9B any time (both stay downloaded). "
                                 "A tab can add its own model on top for what it makes. Everything runs on this PC.")
    def build(self):
        import brain; self.brain = brain
        def head(text): T.Text(self.body, text, font=T.f(11)).pack(anchor="w", pady=(10, 2))
        head("CORE TEXT MODEL")
        names = {k: v["label"] for k, v in brain.CORES.items()}; self.core_v = tk.StringVar(value=names[brain.core_key()])
        c = self.row("Core model")
        T.Choice(c, "", list(names.values()), self.core_v).pack(side="left")
        self.core_v.trace_add("write", lambda *a: self._switch({v: k for k, v in names.items()}[self.core_v.get()]))
        self.core_note = T.Text(self.body, "", muted=True, font=T.f(9)); self.core_note.pack(anchor="w", padx=(20, 0))
        self.state = T.Text(self.body, "", font=T.f(10)); self.state.pack(anchor="w", pady=(4, 0))
        self.card = T.Text(self.body, "Your graphics card: checking…", muted=True, font=T.f(9)); self.card.pack(anchor="w")
        self.buttons(("Download it", lambda: self._download(None), "normal"), ("Start it now", self._start, "normal"),
                     ("Stop it", self._stop, "danger"), ("Open the models folder", lambda: prefs.open_folder(brain.ROOT), "normal"))
        head("EACH TAB'S MODEL  (text tabs use the core unless you pick their own)")
        self.slot_rows = []
        coder = brain.TAB_MODELS["coder7b"]
        self._slot("AI Chat", "built", {"core": ("Core text model", "Chat talks to the core model directly. Teach it in AI Training > Chat Learning.")})
        self._slot("AI Coding", "built", {"core": ("Core text model", "The core model writes and explains code too."),
                                          "coder7b": (coder["label"], coder["note"])}, text=True)
        self._slot("AI Images", "built", IMAGE_MODELS, files=(".safetensors", ".ckpt"), kind="image", get=self._get_images)
        self._slot("AI Videos", "planned", VIDEO_MODELS)
        threading.Thread(target=self._find_card, daemon=True).start()
        self._tick()

    def _slot(self, tab, status, choices, text=False, files=None, kind=None, get=None):
        import learning_areas as LA
        key = "model_" + tab.replace(" ", "_"); cur = prefs.get(key) if prefs.get(key) in choices else list(choices)[0]
        r = _frame(self.body); r.pack(fill="x", anchor="w", pady=(4, 0))
        if LA.DOT: LA.DOT(r, status, 14).pack(side="left", padx=(0, 8))
        T.Text(r, tab.upper(), font=T.f(10), width=12, anchor="w").pack(side="left")
        v = tk.StringVar(value=choices[cur][0]); T.Choice(r, "", [c[0] for c in choices.values()], v).pack(side="left", padx=(8, 8))
        note = T.Text(self.body, choices[cur][1], muted=True, font=T.f(9)); note.configure(wraplength=820); note.pack(anchor="w", padx=(30, 0))
        def changed(*a):
            k = next(k for k, c in choices.items() if c[0] == v.get()); prefs.set(key, k); note.configure(text=choices[k][1])
        v.trace_add("write", changed)
        if text: T.Button(r, "Download", lambda: self._download(next(k for k, c in choices.items() if c[0] == v.get())), width=10).pack(side="left", padx=4)
        if get: T.Button(r, "Download", get, width=10).pack(side="left", padx=4)
        if files:
            T.Button(r, "Add a model file", lambda: self._add_file(kind, files), width=16).pack(side="left", padx=4)
            T.Button(r, "Open folder", lambda: prefs.open_folder(self._kind_dir(kind)), width=11).pack(side="left", padx=4)

    def _get_images(self):
        import imaging; q = self.app.q
        imaging.download(on_done=lambda ok, m: q.put(lambda: T.banner(self.app, ("DOWNLOADED — " if ok else "DOWNLOAD FAILED — ") + m, "success" if ok else "error")))
        T.banner(self.app, "DOWNLOADING — the image engine and Stable Diffusion 1.5 (about 2.2 GB); progress shows in AI Images", "success")
    def _kind_dir(self, kind): d = os.path.join(self.brain.ROOT, kind); os.makedirs(d, exist_ok=True); return d
    def _add_file(self, kind, exts):
        p = filedialog.askopenfilename(parent=self.app, title="Choose a model file", filetypes=[("Model files", " ".join("*" + e for e in exts)), ("All files", "*.*")])
        if p: shutil.copy(p, self._kind_dir(kind)); T.banner(self.app, f"ADDED — {os.path.basename(p)} is in the {kind} models folder", "success")

    def _find_card(self):
        cards = self.brain.gpu(); txt = "Your graphics card: " + (", ".join(f"{c['name']} ({c['gb']} GB reported)" for c in cards) if cards else "not found (the model runs on the processor)")
        self.app.q.put(lambda: self.card.winfo_exists() and self.card.configure(text=txt))
    def _switch(self, key):
        prefs.set("core_model", key)
        if self.brain.ready(): self.brain.stop()
        self._tick(once=True)
    def _download(self, key):
        if key == "core": key = None
        self.brain.download(on_done=lambda ok, m: self.app.q.put(lambda: T.banner(self.app, ("DOWNLOADED — " if ok else "DOWNLOAD FAILED — ") + m, "success" if ok else "error")), key=key)
        self._tick(once=True)
    def _start(self):
        self.brain.load_async(on_done=lambda ok, m: self.app.q.put(lambda: T.banner(self.app, ("READY — " if ok else "COULDN'T START — ") + m, "success" if ok else "error")))
    def _stop(self): self.brain.stop(); self._tick(once=True)
    def _tick(self, once=False):
        if not self.winfo_exists(): return
        st = self.brain.status(); spec = self.brain.CORES[self.brain.core_key()]
        self.core_note.configure(text=spec["note"])
        pct = f" ({st['progress'] * 100:.0f}%)" if st["state"] == "downloading" and st.get("progress") else ""
        self.state.configure(text=f"STATUS: {st['detail'] or st['state'] or ''}{pct}")
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
        p = filedialog.asksaveasfilename(parent=self.app, defaultextension=".zip", initialfile="instant-easel-backup.zip", filetypes=[("Backup", "*.zip")])
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
