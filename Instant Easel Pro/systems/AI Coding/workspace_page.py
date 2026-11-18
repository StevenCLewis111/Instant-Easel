"""
workspace_page.py: AI Coding > Projects and AI Chat > Chats. The conversation on the left, its memory on the right.
"""
import os, threading, tkinter as tk
from tkinter import filedialog
import theme as T, prefs, skin

GUIDE = {"user_rules.md": "Your rules for every project. Short and specific; 'Never ...' works better than 'prefer ...'.",
         "project.md": "What this project does, its rules, what never to do, what to look for, and its commands. Loaded in every request: "
                       "keep it short, and leave out what the code already shows.",
         "summary.md": "The older conversation, compressed. Fix anything it got wrong.",
         "notes.md": "Things it keeps (one per line). Type 'remember: ...' in the chat to add one."}

def _frame(parent):
    f = tk.Frame(parent, bg=parent["bg"]); T.on_change(lambda: f.configure(bg=f.master["bg"])); return f

class WorkspacePage(tk.Frame):
    KIND = "coding"; TITLE = "Projects"; WORD = "project"
    def __init__(self, master, app):
        super().__init__(master, bg=master["bg"]); self.app = app; T.on_change(lambda: self.configure(bg=self.master["bg"]))
        import workspace, paths; self.ws = workspace.Workspace(self.KIND); self.busy = False; self.last = None
        top = _frame(self); top.pack(fill="x")
        T.Title(top, self.TITLE).pack(side="left", padx=(0, 16))
        T.Text(top, self.WORD.upper() + ":", font=T.f(11)).pack(side="left", padx=(0, 6))
        self.proj = tk.StringVar(value=(self.ws.projects() or ["—"])[0]); self.choice = T.Choice(top, "", self.ws.projects() or ["—"], self.proj); self.choice.pack(side="left")
        self.proj.trace_add("write", lambda *a: self.show())
        for text, cmd, kind in ((f"+ New {self.WORD}", self.new, "normal"), ("Rename", self.rename, "normal"), ("Delete", self.delete, "danger")):
            T.Button(top, text, cmd, kind=kind).pack(side="left", padx=(8, 0))
        T.Text(top, f"USER: {paths.user_id()}", muted=True, font=T.f(8)).pack(side="right")
        body = _frame(self); body.pack(fill="both", expand=True, pady=(8, 0))
        side = self.side = T.Panel(body, pad=10, inner=True); side.pack(side="right", fill="y", padx=(10, 0))
        left = _frame(body); left.pack(side="left", fill="both", expand=True)
        box = T.ScrollBox(left); box.pack(fill="both", expand=True)
        self.talk = tk.Text(box.body, wrap="word", relief="flat", font=T.f(10), padx=10, pady=8, highlightthickness=0, cursor="arrow")
        box.attach(self.talk); self.talk.pack(side="left", fill="both", expand=True)
        self.talk.bind("<Key>", lambda e: None if (e.state & 4 and e.keysym.lower() in ("c", "a")) else "break")
        self._talk_style(); T.on_change(self._talk_style)
        self.entry = T.Field(left, height=3); self.entry.pack(fill="x", pady=(8, 0))
        self.entry.bind("<Control-Return>", lambda e: (self.send(), "break")[1])
        r = _frame(left); r.pack(fill="x", pady=(6, 0))
        self.send_btn = skin.button(T.Button(r, "Send", self.send, width=10)); self.send_btn.pack(side="left")
        T.Button(r, "Save last answer", self.save_last, width=18).pack(side="left", padx=8)
        T.Text(r, "Ctrl+Enter sends.  'remember: ...' keeps a note.", muted=True, font=T.f(8)).pack(side="left", padx=8)
        self.msg = T.Text(r, "", muted=True, font=T.f(9)); self.msg.pack(side="right")
        # ---- memory side
        T.Title(side, "Memory").pack(pady=(0, 6))
        for text, f in (("Your rules (every " + self.WORD + ")", "user_rules.md"), (f"This {self.WORD}'s memory", "project.md"),
                        ("Summary so far", "summary.md"), ("Notes it keeps", "notes.md")):
            T.Button(side, text, lambda f=f, t=text: self.edit(f, t), width=24).pack(fill="x", pady=2)
        T.Button(side, "Update memory from this talk", self.propose, width=24).pack(fill="x", pady=2)
        T.Button(side, "Compress now", self.compress, width=24).pack(fill="x", pady=2)
        T.Text(side, "LIBRARY", font=T.f(10)).pack(anchor="w", pady=(10, 2))
        T.Button(side, "Add files", self.add_files, width=24).pack(fill="x", pady=2)
        if self.KIND == "coding": T.Button(side, "Add a code folder", self.add_folder, width=24).pack(fill="x", pady=2)
        T.Text(side, "THE WEB", font=T.f(10)).pack(anchor="w", pady=(10, 2))
        self.web = tk.StringVar(value=prefs.get(f"web_{self.KIND}") or "When needed")
        T.Choice(side, "search", ["Off", "When needed", "Always"], self.web).pack(fill="x")
        self.web.trace_add("write", lambda *a: prefs.set(f"web_{self.KIND}", self.web.get()))
        self.stats = T.Text(side, "", muted=True, font=T.f(7)); self.stats.pack(anchor="w", pady=(8, 0))
        self.show()

    def _talk_style(self):
        self.talk.configure(bg=T.PALETTE["field"], fg="white", insertbackground="white")
        self.talk.tag_configure("you", foreground=T.PALETTE["title"], font=T.f(10)); self.talk.tag_configure("ai", foreground="white")
        self.talk.tag_configure("muted", foreground=T.PALETTE["muted"], font=T.f(8))

    def name(self):
        n = self.proj.get(); return n if n in self.ws.projects() else None

    def show(self):
        self.talk.delete("1.0", "end"); n = self.name()
        if not n:
            self.talk.insert("end", f"Make a {self.WORD} first: + New {self.WORD}.\n\nEach {self.WORD} keeps its own memory, notes, library and history.", "muted"); self._stats(); return
        msgs = self.ws.messages(n); st = self.ws.state(n)
        if st.get("summarized"): self.talk.insert("end", f"({st['summarized']} older messages are in the summary and still searchable.)\n\n", "muted")
        for m in msgs[st.get("summarized", 0):]: self._line(m["role"], m["text"])
        self.talk.see("end"); self._stats()

    def _line(self, role, text):
        self.talk.insert("end", ("YOU: " if role == "you" else "AI: ") + text.strip() + "\n\n", "you" if role == "you" else "ai")

    def _stats(self):
        n = self.name()
        if not n: self.stats.configure(text=""); return
        s = self.ws.stats(n)
        self.stats.configure(text=f"rules {s['rules']} · memory {s['project']} · summary {s['summary']} chars\n"
                                  f"{s['messages']} msgs ({s['summarized']} summarized) · {s['notes']} notes · {s['library']} library")

    def _refresh_list(self, pick=None):
        ps = self.ws.projects(); self.choice.choices = ps or ["—"]; self.proj.set(pick if pick in ps else (ps[0] if ps else "—"))

    def new(self):
        import learning_areas as LA
        d = LA.Dialog(self.app, f"New {self.WORD}", "Its name", None)
        if not d.result: return
        try: n = self.ws.create(d.result[0])
        except ValueError as e: return T.banner(self.app, f"CAN'T MAKE IT — {e}")
        self._refresh_list(n)
        if self.KIND == "coding": self.edit("project.md", "This project's memory")
    def rename(self):
        import learning_areas as LA
        n = self.name()
        if not n: return
        d = LA.Dialog(self.app, f"Rename {n}", "New name", None)
        if d.result:
            try: self._refresh_list(self.ws.rename(n, d.result[0]))
            except ValueError as e: T.banner(self.app, f"CAN'T RENAME — {e}")
    def delete(self):
        n = self.name()
        if n and T.popup(self.app, f"DELETE {n.upper()}?", "Its conversation, memory, notes and library are deleted.", (("Delete", "danger"), ("Cancel", "normal"))) == "Delete":
            self.ws.delete(n); self._refresh_list()

    def send(self):
        n = self.name(); q = self.entry.get("1.0", "end").strip()
        if not n: return T.banner(self.app, f"MAKE A {self.WORD.upper()} FIRST — + New {self.WORD}")
        if not q or self.busy: return
        import brain
        if not brain.installed(brain.tab_model(self.ws.tab)): return T.banner(self.app, "THE TEXT MODEL ISN'T DOWNLOADED YET — Settings > AI Models")
        self.busy = True; self.entry.delete("1.0", "end"); self._line("you", q); self.talk.see("end"); qq = self.app.q
        web = {"Off": "off", "When needed": "when needed", "Always": "always"}[self.web.get()]
        def work():
            try:
                ans, urls = self.ws.ask(n, q, web=web, on_step=lambda t: qq.put(lambda t=t: self.msg.configure(text=t.upper())))
                self.last = (q, ans)
                def done():
                    self._line("ai", ans)
                    if urls: self.talk.insert("end", "From the web: " + ", ".join(urls) + "\n\n", "muted")
                    self.talk.see("end"); self.msg.configure(text=""); self._stats()
                qq.put(done)
            except Exception as e:
                prefs.log_error(type(e), e, e.__traceback__); qq.put(lambda e=e: (self.msg.configure(text=""), T.banner(self.app, f"COULDN'T ANSWER — {e}")))
            finally: self.busy = False
        threading.Thread(target=work, daemon=True).start()

    def save_last(self):
        if not self.last: return T.banner(self.app, "NOTHING TO SAVE YET")
        import learning_areas as LA
        saved = LA.save_answer(self.ws.tab, *self.last)
        T.banner(self.app, f"SAVED — {', '.join(os.path.basename(x) for x in saved)} in your {'code' if self.KIND == 'coding' else 'chats'} folder", "success")

    def edit(self, f, title):
        n = self.name()
        if not n and f != "user_rules.md": return T.banner(self.app, f"MAKE A {self.WORD.upper()} FIRST")
        Editor(self.app, title, GUIDE.get(f, ""), self.ws.read(n, f), lambda text: (self.ws.write(n, f, text), self._stats()))

    def propose(self):
        n = self.name()
        if not n or self.busy: return
        self.busy = True; qq = self.app.q; self.msg.configure(text="DRAFTING A MEMORY UPDATE…")
        def work():
            try:
                draft = self.ws.propose_memory(n)
                qq.put(lambda: (self.msg.configure(text=""), Editor(self.app, "Update this " + self.WORD + "'s memory?", "Its draft from the conversation. Edit, then Save to "
                                "keep it (or Cancel).", draft, lambda text: (self.ws.write(n, "project.md", text), self._stats()))))
            except Exception as e: qq.put(lambda e=e: (self.msg.configure(text=""), T.banner(self.app, f"COULDN'T DRAFT IT — {e}")))
            finally: self.busy = False
        threading.Thread(target=work, daemon=True).start()

    def compress(self):
        n = self.name()
        if not n or self.busy: return
        self.busy = True; qq = self.app.q; self.msg.configure(text="COMPRESSING…")
        def work():
            try: did = self.ws.compress(n, force=True); qq.put(lambda: (self.show(), self.msg.configure(text=""), T.banner(self.app, "COMPRESSED — older messages are in the summary" if did else "NOTHING TO COMPRESS YET", "success")))
            except Exception as e: qq.put(lambda e=e: (self.msg.configure(text=""), T.banner(self.app, f"COULDN'T COMPRESS — {e}")))
            finally: self.busy = False
        threading.Thread(target=work, daemon=True).start()

    def add_files(self):
        n = self.name()
        if not n: return
        ps = filedialog.askopenfilenames(parent=self.app, title="Add to the library", initialdir=prefs.work_folder("code" if self.KIND == "coding" else "chats"))
        import learning_areas as LA
        if ps and LA.fits(self.app, self.ws.tab, ps):
            k = self.ws.add_library(n, files=ps); self._stats(); T.banner(self.app, f"ADDED — {k} files to {n}'s library", "success")
    def add_folder(self):
        n = self.name()
        if not n: return
        d = filedialog.askdirectory(parent=self.app, title="Add a code folder to the library", initialdir=prefs.work_folder("code"))
        import learning_areas as LA
        if d and LA.fits(self.app, self.ws.tab, folder=d):
            g = lambda k: LA.get("Coding Learning", k)
            k = self.ws.add_library(n, folder=d, permissive=False, dedupe=bool(g("dedupe")), compiles=False)   # your own project: no licence check
            self._stats(); T.banner(self.app, f"ADDED — {k} code files to {n}'s library", "success")

class ChatPage(WorkspacePage):
    KIND = "chat"; TITLE = "Chats"; WORD = "chat"

class Editor(tk.Toplevel):
    def __init__(self, app, title, guide, text, on_save):
        super().__init__(app); self.title(title); self.configure(bg=T.PALETTE["bg"]); self.transient(app)
        p = T.Panel(self, pad=14); p.pack(fill="both", expand=True, padx=8, pady=8)
        T.Title(p, title).pack(pady=(0, 4))
        if guide: g = T.Text(p, guide, muted=True, font=T.f(9)); g.configure(wraplength=640); g.pack(pady=(0, 6))
        self.box = tk.Text(p, width=80, height=22, bg=T.PALETTE["field"], fg="white", insertbackground="white", relief="flat", font=T.f(10), wrap="word",
                           highlightthickness=1, highlightbackground=T.PALETTE["border"], undo=True)
        self.box.pack(fill="both", expand=True); self.box.insert("1.0", text)
        self.count = T.Text(p, "", muted=True, font=T.f(8)); self.count.pack(anchor="e")
        self.box.bind("<KeyRelease>", lambda e: self._count()); self._count()
        r = tk.Frame(p, bg=p["bg"]); r.pack(pady=(6, 0))
        T.Button(r, "Save", lambda: (on_save(self.box.get("1.0", "end").rstrip() + "\n"), self.destroy())).pack(side="left", padx=6)
        T.Button(r, "Cancel", self.destroy, kind="danger").pack(side="left")
    def _count(self):
        n = len(self.box.get("1.0", "end").strip()); self.count.configure(text=f"{n} characters" + ("  — long: it's sent with every request" if n > 3000 else ""))

def page_classes(): return {"Projects": WorkspacePage, "Chats": ChatPage}
