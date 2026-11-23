"""
workspace.py: where the coding AI (and the chat AI) lives and works: projects with layered memory, so a small local model can
handle big projects over many sessions.

Memory, from always-there to look-it-up (the MemGPT / AGENTS.md pattern):
    1  Your rules          user_rules.md   one per user (each copy of the app is its own user). In every request.
    2  Project memory      project.md      what the project does, rules, never-do, what to look for, commands. In every request.
                                           Keep it short and specific: "Never" beats "prefer"; skip what the code already shows.
    3  Summary so far      summary.md      older conversation, compressed. In every request.
    4  Recent messages     the last few turns, word for word.
    5  Looked up each time (full-text search, only what matches the question):
         notes             notes.md        things it was told to remember ("remember: ..."), and facts you approved
         older messages    everything ever said in the project, word for word
         project library   library/        documents and code you added
         the web           (optional)      a quick search when the answer needs current information
Everything lives on the AI drive:  memory/<chat|coding>/<user>/projects/<name>/
"""
import os, re, json, html, shutil, datetime, urllib.request, urllib.parse
import paths

RECENT = 8                 # messages kept word for word
COMPRESS_AT = 14           # compress once this many messages are past the summary
LIMITS = dict(rules=2500, project=3500, summary=2500, notes=1500, library=3600, recall=1500, web=3000)   # characters of each part
PROJECT_TEMPLATE = """# What this project does
(one or two lines)

# Rules (always)
-

# Never do
-

# What to look for / check
-

# Commands (build, run, test)
-
"""
USER_TEMPLATE = """# My rules (every project)
- Explain changes in plain words.
- Ask before deleting anything.
"""
SYSTEM = {"coding": "You are a careful programming assistant inside Instant Easel Pro. Follow the user's rules and the project memory "
                    "exactly; they override your defaults. Give working code first, then a short explanation. If you don't know, say so.",
          "chat": "You are the helper inside Instant Easel Pro. Follow the user's rules and this conversation's memory. Answer clearly and plainly."}
TAB = {"coding": "AI Coding", "chat": "AI Chat"}

def _slug(name): return re.sub(r'[<>:"/\\|?*]+', "", name).strip()[:60]

class Workspace:
    """one user's projects (coding) or conversations (chat)"""
    def __init__(self, kind="coding"):
        self.kind = kind; self.tab = TAB[kind]
        self.root = paths.ai("memory", kind, paths.user_id()); os.makedirs(os.path.join(self.root, "projects"), exist_ok=True)
        if not os.path.exists(self.rules_file()): open(self.rules_file(), "w", encoding="utf-8").write(USER_TEMPLATE)

    # ---- projects
    def rules_file(self): return os.path.join(self.root, "user_rules.md")
    def projects(self): return sorted(d for d in os.listdir(os.path.join(self.root, "projects")) if os.path.isdir(os.path.join(self.root, "projects", d)))
    def dir(self, name): return os.path.join(self.root, "projects", _slug(name))
    def file(self, name, f): return os.path.join(self.dir(name), f)

    def create(self, name):
        name = _slug(name)
        if not name: raise ValueError("give it a name")
        if name in self.projects(): raise ValueError(f"there's already one called {name}")
        os.makedirs(os.path.join(self.dir(name), "library"))
        for f, body in (("project.md", PROJECT_TEMPLATE if self.kind == "coding" else "# What this conversation is about\n- \n\n# Rules\n- \n"),
                        ("summary.md", ""), ("notes.md", ""), ("messages.jsonl", "")):
            open(self.file(name, f), "w", encoding="utf-8").write(body)
        return name

    def rename(self, old, new):
        new = _slug(new)
        if not new or new in self.projects(): raise ValueError("pick a new name that isn't used yet")
        os.rename(self.dir(old), self.dir(new)); return new

    def delete(self, name): shutil.rmtree(self.dir(name), ignore_errors=True)

    def read(self, name, f):
        p = self.rules_file() if f == "user_rules.md" else self.file(name, f)
        try: return open(p, encoding="utf-8").read()
        except OSError: return ""

    def write(self, name, f, text):
        p = self.rules_file() if f == "user_rules.md" else self.file(name, f)
        with open(p, "w", encoding="utf-8") as fh: fh.write(text)
        if f == "notes.md": self._index_notes(name)

    # ---- messages
    def messages(self, name):
        out = []
        for line in self.read(name, "messages.jsonl").splitlines():
            try: out.append(json.loads(line))
            except ValueError: pass
        return out

    def _append(self, name, role, text):
        rec = dict(role=role, text=text, when=datetime.datetime.now().isoformat(timespec="seconds"))
        with open(self.file(name, "messages.jsonl"), "a", encoding="utf-8") as f: f.write(json.dumps(rec) + "\n")
        n = len(self.messages(name)); self.index(name).add("message", f"{role}: {text}", source=f"message {n}", key=f"m{n}")
        return rec

    def state(self, name):
        try: return json.load(open(self.file(name, "state.json")))
        except Exception: return dict(summarized=0)

    def language(self, name): return self.state(name).get("language", "")
    def set_language(self, name, lang): st = self.state(name); st["language"] = lang; self._save_state(name, st)
    def checking(self, name): return self.state(name).get("check", True)
    def set_checking(self, name, on): st = self.state(name); st["check"] = bool(on); self._save_state(name, st)

    def _save_state(self, name, st): json.dump(st, open(self.file(name, "state.json"), "w"))

    # ---- searchable memory
    def index(self, name):
        import memory; return memory.Index(self.file(name, "memory.db"))

    def _index_notes(self, name):
        idx = self.index(name)
        with idx._db() as c: c.execute("DELETE FROM items WHERE kind = 'note'")
        for i, line in enumerate(l.strip("-• ").strip() for l in self.read(name, "notes.md").splitlines()):
            if line: idx.add("note", line, source="notes", key=f"n{i}")

    def remember(self, name, text):
        notes = self.read(name, "notes.md").rstrip(); self.write(name, "notes.md", (notes + "\n" if notes else "") + "- " + text.strip() + "\n")

    def add_library(self, name, files=(), folder=None, **checks):
        """documents or code into the project library (code folders get the licence / duplicate / compiles checks)"""
        lib = os.path.join(self.dir(name), "library"); n = 0
        for f in files: shutil.copy(f, lib); n += 1
        if folder:
            import learning_areas as LA; r = LA.import_code(folder, os.path.join(lib, os.path.basename(folder.rstrip("/\\"))), **checks); n += r["copied"]
        self.index(name).sync_folder(lib); return n

    def stats(self, name):
        idx = self.index(name); msgs = self.messages(name)
        return dict(rules=len(self.read(name, "user_rules.md")), project=len(self.read(name, "project.md")), summary=len(self.read(name, "summary.md")),
                    messages=len(msgs), summarized=self.state(name).get("summarized", 0), notes=idx.count("note"), library=idx.count("library"))

    # ---- the request the model sees
    def context(self, name, question, web_results=(), lang=""):
        idx = self.index(name); idx.sync_folder(os.path.join(self.dir(name), "library"))
        clip = lambda t, k: t if len(t) <= LIMITS[k] else t[:LIMITS[k]] + "\n…(cut to keep memory small)"
        msgs = self.messages(name); recent_from = max(0, len(msgs) - RECENT)
        parts = [SYSTEM[self.kind]]
        for title, key, body in (("YOUR USER'S RULES (follow them)", "rules", self.read(name, "user_rules.md")),
                                 ("PROJECT MEMORY (follow it)" if self.kind == "coding" else "CONVERSATION MEMORY", "project", self.read(name, "project.md")),
                                 ("SUMMARY OF THE EARLIER CONVERSATION", "summary", self.read(name, "summary.md"))):
            if body.strip(): parts.append(f"## {title}\n{clip(body.strip(), key)}")
        notes = idx.search(question, k=6, kinds=("note",))
        if notes: parts.append("## NOTES YOU KEPT\n" + clip("\n".join("- " + r["text"] for r in notes), "notes"))
        old = [r for r in idx.search(question, k=6, kinds=("message",)) if int(r["source"].split()[-1]) <= recent_from][:3]
        if old: parts.append("## EARLIER MESSAGES THAT MAY MATTER\n" + clip("\n".join(r["text"][:500] for r in old), "recall"))
        if lang and self.kind == "coding":                                          # the language's own setup: your profile and its library
            import code_helpers as CH
            prof = CH.profile(lang).strip()
            parts.append(f"## THIS IS {lang.upper()}\nAnswer in {lang}. Put code in ```{CH.LANGS[lang]['fences'][0]} blocks, complete and ready to run. "
                         "Use only libraries that exist; say what to install.")
            if prof: parts.append(f"## HOW YOUR USER WRITES {lang.upper()} (follow it)\n{clip(prof, 'rules')}")
            try: llib = CH.library_lookup(lang, question, k=2)
            except Exception: llib = []
            if llib: parts.append(f"## FROM YOUR {lang.upper()} LIBRARY\n" + clip("\n---\n".join(f"[{s}]\n{t}" for s, t in llib), "library"))
        lib = idx.search(question, k=3, kinds=("library",))
        if lib: parts.append("## FROM THE PROJECT LIBRARY\n" + clip("\n---\n".join(f"[{r['source']}]\n{r['text']}" for r in lib), "library"))
        if web_results:
            parts.append("## FROM THE WEB (cite the address when you use it)\n" + clip("\n---\n".join(f"[{u}] {t}\n{b}" for t, u, b in web_results), "web"))
        out = [dict(role="system", content="\n\n".join(parts))]
        for m in msgs[recent_from:]: out.append(dict(role="user" if m["role"] == "you" else "assistant", content=m["text"][:3000]))
        out.append(dict(role="user", content=question))
        return out

    # ---- talking
    def ask(self, name, question, web="when needed", on_step=None):
        """-> (answer, web addresses used)"""
        import brain
        q = question.strip()
        if re.match(r"^/?remember\b[:,]?\s*", q, re.I):
            note = re.sub(r"^/?remember\b[:,]?\s*", "", q, flags=re.I); self.remember(name, note)
            self._append(name, "you", q); ans = f"Noted. I'll keep this in the project's notes: {note}"; self._append(name, "ai", ans); return ans, []
        found = []
        if web != "off":
            query = q if web == "always" else self._needs_web(name, q)
            if query:
                on_step and on_step(f"Searching the web: {query}")
                try: found = web_search(query)
                except Exception: found = []
        lang = ""; st = self.state(name)
        if self.kind == "coding":
            import code_helpers as CH
            recent = "\n".join(m["text"] for m in self.messages(name)[-4:])
            lang = st.get("language", "") if st.get("language_fixed") else CH.detect(q, st.get("language", ""), recent)
            if lang and lang != st.get("language"): st["language"] = lang; self._save_state(name, st)
        on_step and on_step(f"Thinking in {lang}…" if lang else "Thinking…")
        ans = brain.complete(self.tab, self.context(name, q, found, lang), max_tokens=1600 if lang else 1200, temperature=0.3 if lang else 0.7)
        if lang and st.get("check", True):
            on_step and on_step("Checking the code…")
            def fix(bl, code, err):
                return brain.complete(self.tab, [dict(role="system", content=f"You fix {bl} code so it compiles. Keep what it does. Reply with only "
                                                   f"the whole corrected code in one ```{CH.LANGS[bl]['fences'][0]} block."),
                                                 dict(role="user", content=f"This code:\n```\n{code}```\nGives these errors:\n{err}")],
                                      max_tokens=1600, temperature=0.2)
            try:
                ans, report = CH.check_and_fix(ans, lang, fix, on_step=on_step)
                if report: ans = ans.rstrip() + "\n\n" + report
            except Exception: pass
        self._append(name, "you", q); self._append(name, "ai", ans)
        if len(self.messages(name)) - self.state(name).get("summarized", 0) > COMPRESS_AT + RECENT:
            on_step and on_step("Compressing older messages…"); self.compress(name)
        return ans, [u for _, u, _ in found]

    def _needs_web(self, name, q):
        import brain
        r = brain.complete(self.tab, [dict(role="system", content="Decide if answering needs current information from the internet (new versions, "
                                           "error messages, library docs, news). Reply with ONE short web search query, or exactly NO."),
                                      dict(role="user", content=q)], max_tokens=30, temperature=0.0).strip().strip('"')
        return "" if not r or r.upper().startswith("NO") else r.splitlines()[0][:120]

    def compress(self, name, force=False):
        """fold the older messages into the running summary (they stay searchable word for word)"""
        import brain
        msgs = self.messages(name); st = self.state(name); start = st.get("summarized", 0); end = len(msgs) - RECENT
        if end <= start or (not force and end - start < COMPRESS_AT): return False
        old = "\n".join(f"{m['role'].upper()}: {m['text'][:1500]}" for m in msgs[start:end])
        summary = brain.complete(self.tab, [dict(role="system", content="You keep a project's running summary. Merge the new messages into the summary. "
                                                 "Keep: decisions, rules the user gave, file and function names, what was built, open problems and next steps. "
                                                 "Drop chit-chat. Bullet points, under 300 words. Reply with the summary only."),
                                            dict(role="user", content=f"CURRENT SUMMARY:\n{self.read(name, 'summary.md') or '(none yet)'}\n\nNEW MESSAGES:\n{old}")],
                                 max_tokens=600, temperature=0.2)
        self.write(name, "summary.md", summary.strip() + "\n"); st["summarized"] = end; self._save_state(name, st); return True

    def propose_memory(self, name):
        """a new version of the project memory, drafted from the conversation, for the user to approve"""
        import brain
        talk = self.read(name, "summary.md") + "\n" + "\n".join(f"{m['role'].upper()}: {m['text'][:800]}" for m in self.messages(name)[-RECENT:])
        return brain.complete(self.tab, [dict(role="system", content="Update this project memory file with anything the conversation settled: what the "
                                              "project does, rules, things to never do, what to check, commands. Keep its headings. Short, specific "
                                              "bullets; write 'Never ...' for prohibitions; leave out what the code already shows. Reply with the whole file only."),
                                         dict(role="user", content=f"PROJECT MEMORY NOW:\n{self.read(name, 'project.md')}\n\nCONVERSATION:\n{talk}")],
                              max_tokens=900, temperature=0.2).strip() + "\n"

# ---------------------------------------------------------------- the web
def _get(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) InstantEaselPro"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return r.read(800_000).decode("utf-8", errors="ignore")

def page_text(raw):
    raw = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw); return re.sub(r"\s+", " ", html.unescape(raw)).strip()

def web_search(query, n=2, chars=1500):
    """a few web results for the query: [(title, address, text from the page)]"""
    raw = _get("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote_plus(query))
    out = []
    for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', raw, re.S):
        href, title = html.unescape(m.group(1)), page_text(m.group(2))
        if "uddg=" in href: href = urllib.parse.unquote(urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg", [href])[0])
        if not href.startswith("http") or "duckduckgo.com" in href: continue
        try: body = page_text(_get(href))[:chars]
        except Exception: continue
        out.append((title, href, body))
        if len(out) >= n: break
    return out
