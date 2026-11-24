"""
settings_pages.py: Instant Easel's Settings pages. Every value lives in prefs.py (instant_easel_settings.json next to the app).
"""
import os, zipfile, threading, tkinter as tk
from tkinter import filedialog
import theme as T, prefs, skin

def _frame(parent):
    f = tk.Frame(parent, bg=parent["bg"]); T.on_change(lambda: f.configure(bg=f.master["bg"])); return f

BUSY = set()   # the downloads running now (by name): their buttons say Downloading… and a second press doesn't start another

def _dl_button(parent, app, have, get, busy=None, width=12, label="Download"):
    """green Download until it's here, then a red Downloaded that doesn't download it again. It looks again every 1.5 s, so it
    turns red by itself when the download finishes; while one runs it says Downloading… and pressing it doesn't start another"""
    b = T.Button(parent, label, None, kind="go", width=width); st = {"shown": None, "asked": 0.0}
    def check(f):
        try: return bool(f())
        except Exception: return False
    def running(): return check(busy) if busy else (time.time() - st["asked"] < 4)
    def click():
        if check(have): return T.banner(app, "ALREADY DOWNLOADED — nothing to get", "success")
        if st["asked"] and running(): return T.banner(app, "STILL DOWNLOADING — it carries on in the background", "busy")
        st["asked"] = time.time(); get(); look(again=False)
    def look(again=True):
        try:
            if not b.winfo_exists(): return
            if again and not b.winfo_viewable(): b.after(1500, look); return
        except tk.TclError: return
        here = check(have); now = "here" if here else ("busy" if st["asked"] and running() else "get")
        if here: st["asked"] = 0.0
        if now != st["shown"]:
            st["shown"] = now; b.kind = "done" if here else "go"
            b.configure(text={"here": "Downloaded", "busy": "Downloading…", "get": label}[now]); b._style()
        if again: b.after(1500, look)
    b.command = click; b.after(10, look); return b


def _bg(name, work):
    """run a download on its own thread, marked busy (BUSY) while it runs"""
    def run():
        BUSY.add(name)
        try: work()
        finally: BUSY.discard(name)
    threading.Thread(target=run, daemon=True, name=name).start()

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
    TITLE = "General"; NOTE = "Where your drawings are saved, in what format, and how the app starts and closes."
    def build(self):
        c = self.row("Your work folder", "images, videos, code and chats folders inside it. Every tab saves its work there and opens from there. "
                     "Normally the folder of the app you launched (the project folder, or EXE Build for the .exe).")
        self.folder_lbl = T.Text(c, prefs.work_root(), font=T.f(9)); self.folder_lbl.pack(side="left", padx=(0, 8))
        T.Button(c, "Change", self.pick).pack(side="left"); T.Button(c, "App's own folder", self.own).pack(side="left", padx=(6, 0)); skin.file_button(T.Button(c, "Open", lambda: prefs.open_folder(prefs.work_root()))).pack(side="left", padx=6)
        self.choice("File format", "save_format", ["PNG", "JPEG", "WebP"], "PNG keeps every detail (larger files). JPEG and WebP are smaller.")
        self.choice("JPEG / WebP quality", "jpeg_quality", ["75", "85", "92", "100"])
        self.choice("Undo steps", "undo_steps", ["10", "30", "60", "100"], "More steps use more memory on big canvases.")
        self.choice("Open on start", "start_tab", ["Drawing", "Settings", "Last used"])
        self.toggle("Confirm before quitting", "confirm_exit")
        self.buttons(("Create desktop shortcut", self.shortcut, "normal"))
    def shortcut(self):
        """a desktop shortcut with the Instant Easel icon"""
        try:
            import shortcut; path = shortcut.make(); T.banner(self.app, f"SHORTCUT CREATED — {os.path.basename(path)} is on your desktop", "success")
        except Exception as e: T.banner(self.app, f"COULDN'T MAKE THE SHORTCUT — {e}")
    def pick(self):
        d = filedialog.askdirectory(parent=self.app, initialdir=prefs.work_root())
        if d: prefs.set("work_folder", d); self.folder_lbl.configure(text=d)
    def own(self):
        prefs.set("work_folder", ""); self.folder_lbl.configure(text=prefs.work_root())



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






# ---------------------------------------------------------------- Shortcuts
SHORTCUTS = [("Anywhere", [("F11", "full screen on / off"), ("Esc", "leave full screen"), ("Tab / Enter", "move between buttons / press")]),
             ("Drawing", [("B / E / I / G / L / T", "brush, eraser, eyedropper, fill, line, text"), ("[  ]", "smaller / bigger brush"),
                          ("Ctrl+Z / Ctrl+Y", "undo / redo"), ("Mouse wheel", "zoom"), ("Right-drag", "pan"), ("Esc", "studio back to normal size")])]
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
BACKUP_FILES = ["instant_easel_settings.json", "instant_easel_theme.json"]

def _data_file(name):
    """where one of the app's own files lives: .json files in .json/, logs in logs/"""
    import paths
    return paths.json_file(name) if name.endswith(".json") else paths.log_file(name) if name.endswith((".log", ".txt")) else paths.data(name)
class BackupPage(SettingsPage):
    TITLE = "Backup & Reset"; NOTE = "Move your setup to another PC: your settings and theme, in one file (no drawings)."
    def build(self):
        self.buttons(("Export backup…", self.export, "normal"), ("Import backup…", self.restore, "normal"))
        self.msg = T.Text(self.body, "", font=T.f(10)); self.msg.pack(anchor="w", pady=6)
        T.Text(self.body, "RESET", font=T.f(10)).pack(anchor="w", pady=(16, 2))
        self.buttons(("Reset all settings", self.reset, "danger"))
    def export(self):
        p = filedialog.asksaveasfilename(parent=self.app, defaultextension=".zip", initialfile="instant-easel-backup.zip", filetypes=[("Backup", "*.zip")])
        if not p: return
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
            for f in BACKUP_FILES:
                src = _data_file(f)
                if os.path.exists(src): z.write(src, f)
        self.msg.configure(text=f"SAVED: {os.path.basename(p)}"); T.banner(self.app, f"EXPORTED — {os.path.basename(p)}", "success")
    def restore(self):
        p = filedialog.askopenfilename(parent=self.app, filetypes=[("Backup", "*.zip")])
        if not p: return
        with zipfile.ZipFile(p) as z:
            for n in z.namelist():
                if ".." in n or n.startswith("/") or os.path.basename(n) not in BACKUP_FILES: continue   # only our own files, nowhere else
                dest = _data_file(os.path.basename(n))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with z.open(n) as src, open(dest, "wb") as out: out.write(src.read())
        self.msg.configure(text="RESTORED. CLOSE AND REOPEN THE APP TO USE EVERYTHING."); T.banner(self.app, "IMPORTED — close and reopen the app to use everything", "success")
    def reset(self):
        if T.popup(self.app, "RESET ALL SETTINGS?", "Every setting goes back to its default. Your drawings are kept.",
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
            _dl_button(r, self.app, lambda k=kind: AI.have(k), lambda k=kind: self._da_get([k]), busy=lambda k=kind: f"drawing ai {k}" in BUSY,
                       width=18, label=f"Download ({AI.download_size(kind) / 1e6:.0f} MB)").pack(side="left", padx=4)
            T.Button(r, "Add your own…", lambda k=kind: self._da_own(k), width=14).pack(side="left", padx=4)
            if here: T.Button(r, "Remove", lambda k=kind: (AI.remove(k), self._da_list()), kind="danger", width=8).pack(side="left", padx=4)
            T.Text(r, what, muted=True, font=T.f(8)).pack(side="left", padx=6)

    def _da_all(self):
        import ai_cutout as AI
        todo = [k for k in AI.KINDS if not AI.have(k)]
        if not todo: return T.banner(self.app, "YOU HAVE THEM ALL", "success")
        self._da_get(todo)

    def _da_get(self, kinds):
        import ai_cutout as AI, threading
        q = self.app.q; self.da_bar.pack(before=self.da_rows, anchor="w", pady=(0, 6))
        kinds = [k for k in kinds if not AI.have(k) and f"drawing ai {k}" not in BUSY]          # (never one that's here or on its way)
        if not kinds: self.da_bar.pack_forget(); return T.banner(self.app, "ALREADY DOWNLOADED — nothing to get", "success")
        for k in kinds: BUSY.add(f"drawing ai {k}")
        def work():
            done = []
            for k in kinds:
                name = AI.KINDS[k][0]
                try:
                    AI.ensure(k, lambda d, t, n=name: q.put(lambda: self.da_bar.winfo_exists() and self.da_bar.set(d / t if t else None, f"Downloading the {n} model…")))
                    done.append(name)
                except Exception as e: q.put(lambda e=e, n=name: T.banner(self.app, f"{n.upper()} DIDN'T DOWNLOAD — {e}", "error"))
            for k in kinds: BUSY.discard(f"drawing ai {k}")
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


class UpdatesPage(SettingsPage):
    TITLE = "Updates"; NOTE = ("Updates in place: the app checks GitHub for a newer build, downloads it, and on restart puts the new program in. "
                               "Your settings, pictures, models and everything else beside the app stay as they are.")
    def build(self):
        import updater as U, main
        me = U.current()
        T.Text(self.body, f"THIS VERSION: {main.VERSION}" + (f"  ·  build {me['sha'][:7]}, made {me['built']}" if me.get("built") else
               ("  ·  running from the source (updates come with git pull)" if not U.FROZEN else "")), font=T.f(11)).pack(anchor="w", pady=(0, 8))
        self.toggle("Check for updates when the app opens", "check_updates_on_start", "When there's a newer build it asks before downloading anything.")
        r = _frame(self.body); r.pack(anchor="w", pady=(6, 4))
        T.Button(r, "Check now", self.check, width=12).pack(side="left")
        self.get_btn = T.Button(r, "Download and update", self.get, width=22)
        self.go_btn = skin.button(T.Button(r, "Restart to update", self.restart, width=20))
        self.msg = T.Text(self.body, "", font=T.f(10)); self.msg.configure(wraplength=800, justify="left"); self.msg.pack(anchor="w", pady=(4, 0))
        self.new = None
        if U.ready(): self._show_ready()

    def _show_ready(self):
        import updater as U
        n = U.ready() or {}
        self.msg.configure(text=f"THE UPDATE IS DOWNLOADED ({n.get('sha', '')[:7]}, made {n.get('built', '')}). RESTART TO PUT IT IN.")
        if self.get_btn.winfo_manager(): self.get_btn.pack_forget()
        if not self.go_btn.winfo_manager(): self.go_btn.pack(side="left", padx=8)

    def check(self, startup=False):
        import updater as U
        if not startup: self.msg.configure(text="CHECKING…")
        def work():
            try: new = U.check(); err = None
            except Exception as e: new, err = None, e
            def show():
                if not self.winfo_exists(): return
                self.new = new
                if err is not None:
                    if not startup:
                        self.msg.configure(text=f"COULDN'T CHECK ({err.__class__.__name__}: {str(err)[:120]}). CHECK YOUR CONNECTION.")
                        T.banner(self.app, "CAN'T CHECK FOR UPDATES — couldn't reach GitHub")
                    return
                if U.ready(): return self._show_ready()
                if not new:
                    if not startup:
                        self.msg.configure(text="YOU HAVE THE NEWEST BUILD." if U.FROZEN else "RUNNING FROM THE SOURCE: UPDATE WITH GIT PULL.")
                        T.banner(self.app, "UP TO DATE", "success")
                    return
                self.msg.configure(text=f"A NEWER BUILD IS READY: {new['sha'][:7]}, made {new['built']} ({new['size'] / 1e6:.0f} MB).")
                if not self.get_btn.winfo_manager(): self.get_btn.pack(side="left", padx=8)
                if startup:
                    a = T.popup(self.app, "AN UPDATE IS READY", f"A newer build of the app is on GitHub (made {new['built']}). Download it now? "
                                "It downloads in the background; then restart to put it in.", (("Update", "normal"), ("Later", "danger")))
                    if a == "Update": self.get()
                else: T.banner(self.app, "AN UPDATE IS READY — press Download and update", "success")
            self.app.q.put(show)
        threading.Thread(target=work, daemon=True, name="update check").start()

    def get(self):
        import updater as U
        if not self.new: return self.check()
        q = self.app.q; new = self.new
        def work():
            try:
                U.download(new, report=lambda t, f: q.put(lambda t=t: self.winfo_exists() and self.msg.configure(text=t.upper())))
                def done():
                    if self.winfo_exists(): self._show_ready()
                    a = T.popup(self.app, "UPDATE DOWNLOADED", "Restart now to put it in? The app closes and opens again by itself in a few seconds (anything unsaved is lost).",
                                (("Restart now", "normal"), ("Later", "danger")))
                    if a == "Restart now": self.restart()
                    else: T.banner(self.app, "UPDATE READY — it goes in when you press Restart to update (Settings > Updates)", "success")
                q.put(done)
            except Exception as e: q.put(lambda e=e: (self.winfo_exists() and self.msg.configure(text=f"THE DOWNLOAD DIDN'T FINISH — {e}"), T.banner(self.app, f"UPDATE DIDN'T DOWNLOAD — {e}", "error")))
        threading.Thread(target=work, daemon=True, name="update download").start()
        self.msg.configure(text="DOWNLOADING THE UPDATE…")
        if self.get_btn.winfo_manager(): self.get_btn.pack_forget()

    def restart(self):
        import updater as U
        try:
            try: self.app.save_state() if hasattr(self.app, "save_state") else None
            except Exception: pass
            U.restart_into_update(self.app)
        except Exception as e: T.banner(self.app, f"COULDN'T UPDATE — {e}", "error")

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

