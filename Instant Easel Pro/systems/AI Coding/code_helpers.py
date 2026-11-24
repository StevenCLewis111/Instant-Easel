"""
code_helpers.py: what makes the coding AI good at each language, without training it.

  1  Which language   detect(question, ...) works out the language from the request (named in it, a code block's language, a file
                      name, the project's main language). The coding model then answers with that language's setup.
  2  A profile each   languages/<Language>/profile.md: your style, the libraries and versions you use, things to avoid. In every
                      request in that language. Starts with sensible defaults; edit it to make it yours.
  3  A library each   languages/<Language>/library/: docs and code of yours for that language, looked up before it answers.
  4  Checked first    check(code, language): the code is compiled / syntax-checked with the tools on this PC (Python always, inside
                      the app; JavaScript with Node, C / C++ with gcc or clang, Java, Go, Rust, Bash, Lua... when they're installed).
                      Errors go back to the model to fix (up to twice) before you see the answer. Code is checked, never run.

Checkers are found on PATH, in the AI drive's "Code Tools" folder, anywhere a few folders deep on the AI drive, and where the usual
Windows installers put them.

Everything lives with your coding memory: memory/coding/<user>/languages/
"""
import os, re, json, shutil, subprocess, tempfile, sys
import paths

# name: file ending, words that name it, its code-block names, how to check it ([command with {f} = the file], ...) - the first one found is used
LANGS = {
    "Python":     dict(ext=".py",   words=["python", "py", "django", "flask", "pandas", "numpy", "tkinter", "pip"], fences=["python", "py", "python3"], check="python"),
    "JavaScript": dict(ext=".js",   words=["javascript", "js", "node", "nodejs", "react", "npm", "jquery", "vue"], fences=["javascript", "js", "jsx", "node"],
                       check=[["node", "--check", "{f}"]]),
    "TypeScript": dict(ext=".ts",   words=["typescript", "ts", "angular", "deno"], fences=["typescript", "ts", "tsx"],
                       check=[["tsc", "--noEmit", "--skipLibCheck", "--target", "es2020", "{f}"]]),
    "C#":         dict(ext=".cs",   words=["c#", "csharp", ".net", "dotnet", "unity", "wpf", "winforms", "asp.net"], fences=["csharp", "cs", "c#"], check=[]),
    "C++":        dict(ext=".cpp",  words=["c++", "cpp", "unreal", "qt"], fences=["cpp", "c++", "cxx", "hpp"],
                       check=[["g++", "-fsyntax-only", "-std=c++17", "{f}"], ["clang++", "-fsyntax-only", "-std=c++17", "{f}"]]),
    "C":          dict(ext=".c",    words=[" c ", "c language", "ansi c", "arduino"], fences=["c", "h"],
                       check=[["gcc", "-fsyntax-only", "{f}"], ["clang", "-fsyntax-only", "{f}"]]),
    "Java":       dict(ext=".java", words=["java", "spring", "android", "maven", "gradle", "kotlin"], fences=["java"], check=[["javac", "-d", "{d}", "{f}"]]),
    "Go":         dict(ext=".go",   words=["golang", " go "], fences=["go", "golang"], check=[["gofmt", "-e", "-l", "{f}"]]),
    "Rust":       dict(ext=".rs",   words=["rust", "cargo", "rustc"], fences=["rust", "rs"],
                       check=[["rustc", "--edition", "2021", "--crate-type", "lib", "--emit=metadata", "-o", "{d}/out.rmeta", "{f}"]]),
    "HTML / CSS": dict(ext=".html", words=["html", "css", "web page", "webpage", "website"], fences=["html", "css", "xml"], check=[]),
    "SQL":        dict(ext=".sql",  words=["sql", "sqlite", "mysql", "postgres", "query"], fences=["sql", "sqlite", "mysql", "postgresql"], check=[]),
    "Bash":       dict(ext=".sh",   words=["bash", "shell script", "linux command", "terminal"], fences=["bash", "sh", "shell", "zsh"], check=[["bash", "-n", "{f}"]]),
    "PowerShell": dict(ext=".ps1",  words=["powershell", "ps1"], fences=["powershell", "ps1", "pwsh"], check=[]),
    "Lua":        dict(ext=".lua",  words=["lua", "roblox", "love2d"], fences=["lua", "luau"], check=[["luac", "-p", "{f}"]]),
    "JSON":       dict(ext=".json", words=["json"], fences=["json"], check="json"),
}

PROFILE_TEMPLATES = {
    "Python": "# Python: how I like it\n- Python 3.10+; type hints on functions.\n- Standard library first; say which pip packages are needed.\n- f-strings, pathlib for files.\n\n# Never\n- Never use a bare except.\n",
    "JavaScript": "# JavaScript: how I like it\n- Modern JS (ES2020+): const / let, arrow functions, async / await.\n\n# Never\n- Never use var.\n",
    "C#": "# C#: how I like it\n- .NET 8, C# 12; nullable reference types on.\n- PascalCase for methods and properties.\n\n# Never\n- Never block on async code with .Result.\n",
}
GENERIC_TEMPLATE = "# {lang}: how I like it\n- (your style, the libraries and versions you use)\n\n# Never\n- (things it must never do in {lang})\n"

FENCE = re.compile(r"```[ \t]*([\w#+.\-]*)[^\n]*\n(.*?)```", re.S)


# ---------------------------------------------------------------- where the language profiles live
def root():
    d = paths.ai("memory", "coding", paths.user_id(), "languages"); os.makedirs(d, exist_ok=True); return d


def _slug(lang): return re.sub(r"[^\w#+]+", "_", lang).strip("_")


def folder(lang):
    d = os.path.join(root(), _slug(lang)); os.makedirs(os.path.join(d, "library"), exist_ok=True); return d


def profile_file(lang):
    f = os.path.join(folder(lang), "profile.md")
    if not os.path.exists(f):
        with open(f, "w", encoding="utf-8") as fh: fh.write(PROFILE_TEMPLATES.get(lang, GENERIC_TEMPLATE.format(lang=lang)))
    return f


def profile(lang):
    try:
        with open(profile_file(lang), encoding="utf-8") as f: return f.read()
    except Exception: return ""


def library_index(lang):
    import memory; return memory.Index(os.path.join(folder(lang), "library.db"))


def library_lookup(lang, text, k=2):
    idx = library_index(lang); idx.sync_folder(os.path.join(folder(lang), "library"))
    return [(r["source"], r["text"]) for r in idx.search(text, k=k, kinds=("library",))]


def add_to_library(lang, files=(), folder_path=None):
    lib = os.path.join(folder(lang), "library"); n = 0
    for f in files: shutil.copy(f, lib); n += 1
    if folder_path:
        import learning_areas as LA
        r = LA.import_code(folder_path, os.path.join(lib, os.path.basename(folder_path.rstrip("/\\")))); n += r["copied"]
    library_index(lang).sync_folder(lib); return n


# ---------------------------------------------------------------- languages you switched off (Settings > Code Languages)
def enabled(lang):
    import prefs
    return lang not in (prefs.get("languages_off") or [])


def set_enabled(lang, on):
    import prefs
    off = [l for l in (prefs.get("languages_off") or []) if l != lang]
    if not on: off.append(lang)
    prefs.set("languages_off", off)


def on_languages(): return [l for l in LANGS if enabled(l)]


# ---------------------------------------------------------------- 1: which language
def detect(question, project_lang="", recent=""):
    """the language this request is about (only the ones switched on): see _detect"""
    lang = _detect(question, project_lang, recent)
    return lang if lang and enabled(lang) else ""


def _detect(question, project_lang="", recent=""):
    """the language this request is about: named in it, a code block's language, a file name in it, then the earlier talk, then the
    project's main language. '' if it can't tell"""
    q = " " + question.lower() + " "
    for m in FENCE.finditer(question):                                         # a code block that says its language
        lang = by_fence(m.group(1))
        if lang: return lang
    for name, d in LANGS.items():                                              # a file name with its ending
        if re.search(re.escape(d["ext"]) + r"\b", q): return name
    scores = {}
    for name, d in LANGS.items():                                              # named in the words
        for w in d["words"]:
            pat = re.escape(w.strip()) if w.strip() in ("c#", "c++", ".net", "asp.net") else r"(?<![\w#+.])" + re.escape(w.strip()) + r"(?![\w#+])"
            if (w.startswith(" ") and w in q) or re.search(pat, q): scores[name] = scores.get(name, 0) + (3 if w.strip() == name.lower() else 1)
    if scores: return max(scores, key=scores.get)
    if project_lang and project_lang in LANGS: return project_lang
    for m in FENCE.finditer(recent or ""):                                     # what the conversation has been in
        lang = by_fence(m.group(1))
        if lang: return lang
    return ""


def by_fence(tag):
    tag = (tag or "").lower().strip()
    if not tag: return ""
    return next((n for n, d in LANGS.items() if tag in d["fences"]), "")


# ---------------------------------------------------------------- 4: checked before you see it
_found = {}
def _places():
    """folders a checker may be in besides PATH: the AI drive's "Code Tools" folder, the AI drive itself, and where the usual Windows
    installers put them"""
    import glob
    out = [os.path.join(paths.ai_root(), "Code Tools")]
    for d, subs, fs in os.walk(out[0]) if os.path.isdir(out[0]) else ():      # (each tool unpacks into its own folder there)
        if d.count(os.sep) - out[0].count(os.sep) >= 3: subs[:] = []
        subs[:] = [x for x in subs if x not in ("node_modules", "include", "lib", "share", "doc", "src")]
        if os.path.basename(d).lower() == "bin" or any(f.lower() in ("node.exe", "node") for f in fs): out.append(d)
    if sys.platform == "win32":
        env = os.environ.get
        pf = [env("ProgramFiles", r"C:\Program Files"), env("ProgramFiles(x86)", r"C:\Program Files (x86)")]
        drive = os.path.splitdrive(paths.ai_root())[0] + os.sep
        for base in pf + [env("LOCALAPPDATA", "") + r"\Programs"]:
            for sub in ("nodejs", r"Git\bin", r"Git\usr\bin", r"Java\*\bin", r"Eclipse Adoptium\*\bin", r"Microsoft\jdk-*\bin", r"Go\bin",
                        r"LLVM\bin", r"Lua\*", "Lua", r"Microsoft VS Code\bin"):
                out += glob.glob(os.path.join(base, sub))
        for root in {drive, "C:\\"}:
            for sub in (r"msys64\ucrt64\bin", r"msys64\mingw64\bin", r"msys64\usr\bin", r"w64devkit\bin", r"mingw64\bin", r"MinGW\bin",
                        r"Go\bin", r"nodejs", r"Program Files\nodejs", r"Program Files\Git\bin", r"Program Files\Java\*\bin"):
                out += glob.glob(os.path.join(root, sub))
        out += [os.path.join(os.path.expanduser("~"), ".cargo", "bin"), os.path.join(env("APPDATA", ""), "npm")]
    return [d for d in out if os.path.isdir(d)]


def _scan_drive(names, depth=4):
    """look for the checkers anywhere on the AI drive (a few folders deep), once"""
    root = paths.ai_root(); hits = {}
    want = {n.lower(): n for n in names}
    base_depth = root.rstrip(os.sep).count(os.sep)
    for d, subs, files in os.walk(root):
        if d.count(os.sep) - base_depth >= depth: subs[:] = []
        subs[:] = [x for x in subs if not x.startswith((".", "$")) and x.lower() not in ("models", "memory", "recovery", "logs", "node_modules")]
        for f in files:
            k = f.lower()
            if k in want and want[k] not in hits: hits[want[k]] = os.path.join(d, f)
    return hits


def _which(cmd):
    if cmd in _found: return _found[cmd]
    exe = cmd + ".exe" if sys.platform == "win32" else cmd
    hit = shutil.which(cmd) or shutil.which(exe)
    if not hit:
        for d in _places():
            f = os.path.join(d, exe)
            if os.path.isfile(f): hit = f; break
    if not hit:
        if "_drive" not in _found:
            names = {(c[0] + ".exe" if sys.platform == "win32" else c[0]) for d in LANGS.values() if isinstance(d["check"], list) for c in d["check"]}
            try: _found["_drive"] = _scan_drive(names)
            except Exception: _found["_drive"] = {}
        hit = _found["_drive"].get(exe)
    _found[cmd] = hit; return hit


def rescan(): _found.clear()


def checker(lang):
    """how this language's code can be checked on this PC: 'python' / 'json' (inside the app), a command, or None"""
    c = LANGS.get(lang, {}).get("check")
    if c in ("python", "json"): return c
    for cmd in c or []:
        if _which(cmd[0]) and all(os.path.exists(_tools(x)) for x in cmd[1:] if "{tools}" in x): return cmd
    return None


def tools_dir(): return os.path.join(paths.ai_root(), "Code Tools")
def _tools(x): return x.replace("{tools}", tools_dir()).replace("/", os.sep) if "{tools}" in x else x


def check(code, lang):
    """-> (ok, errors text, how it was checked). ok is None when nothing on this PC can check this language. Never runs the code"""
    how = checker(lang)
    if how is None: return None, "", ""
    if how == "python":
        try: compile(code, "answer.py", "exec"); return True, "", "Python's compiler"
        except SyntaxError as e:
            line = (e.text or "").rstrip("\n")
            return False, f"SyntaxError on line {e.lineno}: {e.msg}" + (f"\n    {line}" if line else ""), "Python's compiler"
        except Exception as e: return False, f"{e.__class__.__name__}: {e}", "Python's compiler"
    if how == "json":
        try: json.loads(code); return True, "", "a JSON reader"
        except Exception as e: return False, str(e), "a JSON reader"
    d = tempfile.mkdtemp(prefix="ie-check-")
    try:
        name = "Main.java" if lang == "Java" and re.search(r"public\s+class\s+Main\b", code) else ("answer" + LANGS[lang]["ext"])
        if lang == "Java":
            m = re.search(r"public\s+(?:final\s+)?class\s+(\w+)", code); name = (m.group(1) if m else "Answer") + ".java"
        f = os.path.join(d, name)
        with open(f, "w", encoding="utf-8") as fh: fh.write(code)
        cmd = [_which(how[0])] + [_tools(x).replace("{f}", f).replace("{d}", d) for x in how[1:]]
        kw = dict(capture_output=True, text=True, timeout=30, cwd=d)
        if sys.platform == "win32": kw["creationflags"] = 0x08000000                    # (no console window flashing up)
        r = subprocess.run(cmd, **kw)
        out = (r.stdout + "\n" + r.stderr).strip().replace(d + os.sep, "").replace(d, "")
        ok = r.returncode == 0 and not (lang == "Go" and out)                          # (gofmt -e prints problems)
        return ok, out[:2500], os.path.basename(how[0])
    except subprocess.TimeoutExpired: return None, "", ""
    except Exception as e: return None, "", ""
    finally: shutil.rmtree(d, ignore_errors=True)


def blocks(answer, lang):
    """[(start, end, language, code)] for each code block in the answer that can be checked (its language, or the request's when it doesn't say)"""
    out = []
    for m in FENCE.finditer(answer):
        bl = by_fence(m.group(1)) or (lang if not m.group(1) else "")
        if bl and checker(bl): out.append((m.start(2), m.end(2), bl, m.group(2)))
    return out


def check_and_fix(answer, lang, ask_fix, rounds=2, on_step=None):
    """check every code block; ask the model to fix any that don't compile (up to `rounds` times each). ask_fix(language, code, errors)
    -> corrected code. -> (answer, report line)"""
    found = blocks(answer, lang)
    if not found:
        how = checker(lang) if lang else None
        if lang and not how and "```" in answer: return answer, f"(No {lang} checker on this PC: the code wasn't checked.)"
        return answer, ""
    fixed = failed = 0; hows = set(); new = answer
    for start, end, bl, code in reversed(found):                                # (from the end, so earlier positions stay right)
        cur = code; ok, err, how = check(cur, bl); hows.add(how)
        tries = 0
        while ok is False and tries < rounds:
            tries += 1; on_step and on_step(f"Fixing the {bl} code (try {tries})…")
            try: cand = ask_fix(bl, cur, err)
            except Exception: break
            m = FENCE.search(cand); cand = m.group(2) if m else cand
            if not cand.strip(): break
            cur = cand if cand.endswith("\n") else cand + "\n"; ok, err, how = check(cur, bl)
            if ok: fixed += 1
        if ok is False: failed += 1; cur = cur + (f"\n" if not cur.endswith("\n") else "")
        new = new[:start] + cur + new[end:]
        if ok is False: new = new.replace(cur + "```", cur + "```\n(This code still has an error: " + err.splitlines()[0][:200] + ")", 1)
    hows.discard("")
    via = " / ".join(sorted(hows)) or "the checker"
    if failed: report = f"(Checked with {via}: {failed} block(s) still have errors" + (f"; fixed {fixed}" if fixed else "") + ".)"
    else: report = f"(Checked with {via}: it compiles" + (f" — fixed {fixed} error(s) first" if fixed else "") + ".)"
    return new, report


def available():
    """{language: how it's checked on this PC, or ''}"""
    out = {}
    for lang in LANGS:
        h = checker(lang); out[lang] = "" if h is None else ("built in" if isinstance(h, str) else os.path.basename(h[0]))
    return out
