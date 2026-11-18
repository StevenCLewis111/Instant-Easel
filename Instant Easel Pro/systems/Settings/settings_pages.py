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
    TITLE = "General"; NOTE = "Where your images are saved, in what format, and how the app starts and closes."
    def build(self):
        c = self.row("Save folder"); self.folder_lbl = T.Text(c, prefs.get("save_folder"), font=T.f(9)); self.folder_lbl.pack(side="left", padx=(0, 8))
        T.Button(c, "Change", self.pick).pack(side="left"); T.Button(c, "Open", lambda: prefs.open_folder(prefs.save_folder())).pack(side="left", padx=6)
        self.choice("File format", "save_format", ["PNG", "JPEG", "WebP"], "PNG keeps every detail (larger files). JPEG and WebP are smaller.")
        self.choice("JPEG / WebP quality", "jpeg_quality", ["75", "85", "92", "100"])
        self.toggle("Auto-save every result", "auto_save", "Each image you create is saved straight away, in a dated folder inside the save folder.")
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

# ---------------------------------------------------------------- Generation defaults
class GenDefaultsPage(SettingsPage):
    TITLE = "Generation Defaults"; NOTE = "What the Image settings panel starts with each time the app opens."
    def build(self):
        import styles_fx
        import models as MD; self.choice("Model", "default_model", MD.BUILTIN + MD.names())
        self.choice("Art style", "default_style", styles_fx.STYLES)
        self.choice("Aspect", "default_aspect", ["2:3", "3:2", "1:1", "16:9", "9:16", "original"])
        self.choice("How many", "default_count", ["1", "4", "9"])
        self.choice("Seed", "seed_mode", ["random", "fixed"], "Fixed: the same request paints the same picture every time (useful for comparing settings).")
        self.entry("Fixed seed", "fixed_seed", width=10)
        self.buttons(("Apply to Image settings now", self.apply, "normal"))
    def apply(self):
        g = self.app.gen
        for k, key in (("model", "default_model"), ("style", "default_style"), ("aspect", "default_aspect"), ("count", "default_count")): g[k].set(prefs.get(key))
        T.banner(self.app, "APPLIED — Image settings now use your defaults", "success")

# ---------------------------------------------------------------- Performance
class PerformancePage(SettingsPage):
    TITLE = "Performance"; NOTE = "Trade a little quality for speed on slower PCs."
    def build(self):
        self.choice("Editing preview", "edit_preview", ["Fast", "Normal", "Sharp"], "Size of the live preview while you drag sliders. Saving is always full size.")
        self.choice("Image to Image size", "i2i_size", ["Fast", "Standard", "Large"], "Working size of the longest side: 1200, 1600 or 2400 px.")
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
    TITLE = "Privacy & Data"; NOTE = ("Instant Easel works offline. Your prompts, pictures and learning stay on this PC. The internet is only used "
                                      "if you check for updates or download a model.")
    def build(self):
        import app as classic
        self.lib = classic.library_dir()
        self.toggle("Keep training copies", "keep_training_copies", "Off: images you teach it are measured, then the app's copies are deleted.")
        T.Text(self.body, "STORAGE USED", font=T.f(10)).pack(anchor="w", pady=(12, 4)); self.usage = T.Text(self.body, "", font=T.f(9)); self.usage.pack(anchor="w")
        self.buttons(("Refresh", self.refresh, "normal"), ("Open data folder", lambda: prefs.open_folder(prefs.home_dir()), "normal"))
        self.buttons(("Clear learned data", self.clear_learning, "danger"), ("Reset taught words", self.reset_words, "danger"))
        self.refresh()
    def refresh(self):
        rows = [("Learning library (images waiting + learned style)", prefs.folder_size(self.lib)), ("AI model files", prefs.folder_size(prefs.models_folder())),
                ("Saved images", prefs.folder_size(prefs.get("save_folder")) if os.path.isdir(prefs.get("save_folder")) else 0)]
        for name in ("vocab.json", "instant_easel_settings.json", "instant_easel_theme.json", "instant_easel_errors.log"):
            p = _data_file(name); rows.append((name, os.path.getsize(p) if os.path.exists(p) else 0))
        self.usage.configure(text="\n".join(f"{k:<52} {prefs.human(v):>10}" for k, v in rows))
    def clear_learning(self):
        if T.popup(self.app, "CLEAR LEARNED DATA?", "Deletes everything it has learned and any images waiting to be learned.\nThis can't be undone.",
                   (("Clear", "danger"), ("Cancel", "normal"))) == "Clear":
            shutil.rmtree(self.lib, ignore_errors=True); os.makedirs(self.lib, exist_ok=True); self.refresh(); T.banner(self.app, "LEARNED DATA CLEARED", "success")
    def reset_words(self):
        if T.popup(self.app, "RESET TAUGHT WORDS?", "Forgets the words you've taught. Its built-in vocabulary stays.", (("Reset", "danger"), ("Cancel", "normal"))) == "Reset":
            try: os.remove(_data_file("vocab.json"))
            except OSError: pass
            self.refresh(); T.banner(self.app, "TAUGHT WORDS RESET — its built-in vocabulary stays", "success")

# ---------------------------------------------------------------- AI models
CATALOG = [
    dict(name="Gemma 4 E4B", role="Understanding: any wording, labels and sorts training images, prompt to edit, checks results",
         size="about 4-6 GB", license="Apache 2.0", pattern="*gemma*4*e4b*.gguf"),
    dict(name="SDXL-class, 4-8 steps", role="Fast AI image generation (fits a 6 GB graphics card)", size="about 3-7 GB", license="OpenRAIL++", pattern="*sdxl*.gguf"),
    dict(name="FLUX.1 [schnell]", role="Higher-quality AI image generation (slower on 6 GB; uses system RAM too)", size="about 7-12 GB", license="Apache 2.0", pattern="*flux*schnell*.gguf"),
]
def hardware():
    info = {"Processor": platform.processor() or platform.machine(), "System": f"{platform.system()} {platform.release()}"}
    try:
        if sys.platform == "win32":
            import ctypes
            class M(ctypes.Structure): _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong), ("avail", ctypes.c_ulonglong),
                                                   ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("x", ctypes.c_ulonglong)]
            m = M(); m.l = ctypes.sizeof(M); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)); info["Memory"] = prefs.human(m.total)
            out = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_VideoController).Name"], capture_output=True, text=True, timeout=8,
                                 creationflags=0x08000000).stdout.strip()
            info["Graphics"] = ", ".join(x.strip() for x in out.splitlines() if x.strip()) or "unknown"
        else:
            kb = int(open("/proc/meminfo").read().split("MemTotal:")[1].split()[0]); info["Memory"] = prefs.human(kb * 1024)
            out = subprocess.run(["sh", "-c", "lspci 2>/dev/null | grep -i -E 'vga|3d|display'"], capture_output=True, text=True, timeout=5).stdout.strip()
            info["Graphics"] = out.split(": ", 1)[-1] if out else "not detected"
    except Exception: info.setdefault("Graphics", "not detected")
    return info

class AIModelsPage(SettingsPage):
    TITLE = "AI Models"; NOTE = ("Built into Instant Easel: model files are loaded by the app itself, no separate programs. "
                                 "The built-in runner that uses them is the next big build; this page already finds your hardware and model files.")
    def build(self):
        T.Text(self.body, "YOUR PC", font=T.f(10)).pack(anchor="w"); self.hw = T.Text(self.body, "Checking…", font=T.f(9)); self.hw.pack(anchor="w", pady=(2, 10))
        threading.Thread(target=lambda: (lambda h: self.app.q.put(lambda: self.hw.configure(text="\n".join(f"{k:<10} {v}" for k, v in h.items()))))(hardware()), daemon=True).start()
        self.toggle("Use the graphics card", "use_gpu", "Uses Vulkan, which Intel Arc, AMD and NVIDIA cards all support.")
        c = self.row("Models folder"); self.mf = T.Text(c, prefs.models_folder(), font=T.f(9)); self.mf.pack(side="left", padx=(0, 8))
        T.Button(c, "Change", self.pick).pack(side="left"); T.Button(c, "Open", lambda: prefs.open_folder(prefs.models_folder())).pack(side="left", padx=6)
        T.Text(self.body, "MODEL CATALOG", font=T.f(10)).pack(anchor="w", pady=(12, 4)); self.cat = _frame(self.body); self.cat.pack(anchor="w", fill="x")
        self.buttons(("Add a model file…", self.add_file, "normal"), ("Refresh", self.refresh, "normal")); self.refresh()
    def refresh(self):
        for w in self.cat.winfo_children(): w.destroy()
        folder = prefs.models_folder()
        for m in CATALOG:
            have = [os.path.basename(p) for p in glob.glob(os.path.join(folder, m["pattern"]))]
            r = T.Panel(self.cat, pad=8, inner=True); r.pack(fill="x", pady=3)
            T.Text(r, f"{m['name']}   ({m['size']}, {m['license']})", font=T.f(10)).pack(anchor="w")
            T.Text(r, m["role"], muted=True, font=T.f(9)).pack(anchor="w")
            T.Text(r, ("FOUND: " + ", ".join(have)) if have else "NOT INSTALLED YET", font=T.f(9)).pack(anchor="w")
    def pick(self):
        d = filedialog.askdirectory(parent=self.app, initialdir=prefs.models_folder())
        if d: prefs.set("models_folder", d); self.mf.configure(text=d); self.refresh()
    def add_file(self):
        p = filedialog.askopenfilename(parent=self.app, filetypes=[("Model files", "*.gguf *.safetensors"), ("All files", "*.*")])
        if p: shutil.copy(p, prefs.models_folder()); self.refresh()

# ---------------------------------------------------------------- Updates
REPO = "StevenCLewis111/books"
class UpdatesPage(SettingsPage):
    TITLE = "Updates"; NOTE = "Checks GitHub for a newer InstantEasel.exe. Nothing is downloaded or installed without asking."
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
BACKUP_FILES = ["instant_easel_settings.json", "instant_easel_theme.json", "vocab.json"]

def _data_file(name):
    """where one of the app's own files lives: .json files in .json/, logs in logs/"""
    import paths
    return paths.json_file(name) if name.endswith(".json") else paths.log_file(name) if name.endswith((".log", ".txt")) else paths.data(name)
class BackupPage(SettingsPage):
    TITLE = "Backup & Reset"; NOTE = "Move your setup to another PC: settings, theme, taught words and learned style, in one file (no images)."
    def build(self):
        self.buttons(("Export backup…", self.export, "normal"), ("Import backup…", self.restore, "normal"))
        self.msg = T.Text(self.body, "", font=T.f(10)); self.msg.pack(anchor="w", pady=6)
        T.Text(self.body, "RESET", font=T.f(10)).pack(anchor="w", pady=(16, 2))
        self.buttons(("Reset all settings", self.reset, "danger"))
    def _learned(self):
        import app as classic; lib = classic.library_dir()
        return [p for p in [os.path.join(lib, "profile.json")] + glob.glob(os.path.join(lib, "history", "*.json")) if os.path.exists(p)], lib
    def export(self):
        p = filedialog.asksaveasfilename(parent=self.app, defaultextension=".zip", initialfile="instant-easel-backup.zip", filetypes=[("Backup", "*.zip")])
        if not p: return
        learned, lib = self._learned()
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
            for f in BACKUP_FILES:
                src = _data_file(f)
                if os.path.exists(src): z.write(src, f)
            for f in learned: z.write(f, "my-library/" + os.path.relpath(f, lib).replace(os.sep, "/"))
        self.msg.configure(text=f"SAVED: {os.path.basename(p)}"); T.banner(self.app, f"EXPORTED — {os.path.basename(p)}", "success")
    def restore(self):
        p = filedialog.askopenfilename(parent=self.app, filetypes=[("Backup", "*.zip")])
        if not p: return
        import app as classic; lib = classic.library_dir()
        with zipfile.ZipFile(p) as z:
            for n in z.namelist():
                if ".." in n or n.startswith("/"): continue                                       # only our own files, nowhere else
                dest = os.path.join(lib, n[len("my-library/"):]) if n.startswith("my-library/") else _data_file(os.path.basename(n))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with z.open(n) as src, open(dest, "wb") as out: out.write(src.read())
        self.msg.configure(text="RESTORED. CLOSE AND REOPEN THE APP TO USE EVERYTHING."); T.banner(self.app, "IMPORTED — close and reopen the app to use everything", "success")
    def reset(self):
        if T.popup(self.app, "RESET ALL SETTINGS?", "Every setting goes back to its default. Your learning, words and images are kept.",
                   (("Reset", "danger"), ("Cancel", "normal"))) == "Reset":
            prefs.reset_all(); T.banner(self.app, "SETTINGS RESET — close and reopen the app to finish", "success")
