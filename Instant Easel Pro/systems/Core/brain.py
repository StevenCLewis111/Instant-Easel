"""
brain.py: Instant Easel Pro's core text model. One English model is the base of every AI tab; each tab keeps its own memory.

    The core model      Qwen3.5 4B or 9B (Apache 2.0), chosen in Settings > AI Models and switchable any time.
                          4B  about 3 GB, fits fully on a 6 GB graphics card (fast)
                          9B  about 5.7 GB, smarter; on a 6 GB card part of it runs on the processor (slower)
    The engine          llama.cpp's llama-server, downloaded once (the Vulkan build on Windows, which runs on Intel Arc, AMD and
                        NVIDIA cards). It runs in the background while the app is open and is closed with the app.
    A tab's own model   a tab can use a different text model (e.g. a coding model for AI Coding). Only one runs at a time;
                        switching tabs swaps the model in.
    Each tab's memory   my-models/text/tabs/<Tab_Name>/
                          examples.jsonl   what you taught that tab (a question and the answer you want)
                          library/         documents and code it looks things up in when answering
                        Nothing moves between tabs unless you transfer it.

    import brain
    brain.status()                         -> dict(state, detail, model, progress)   states: not-installed, downloading, loading,
                                              ready, error
    brain.download(on_done)                engine + the chosen core model (background)
    brain.ask("AI Chat", "hello")          -> the answer (starts the engine the first time)
    brain.teach("AI Chat", "q", "a")       brain.examples(tab)  brain.forget(tab)  brain.transfer(src, dst)
"""
import os, sys, json, re, shutil, threading, time, datetime, subprocess, socket, zipfile, tarfile, atexit, urllib.request, urllib.error
import paths, catalog, hardware

# ---------------------------------------------------------------- the models (catalog.py has the ladders and what each needs)
def _spec_from(e): return dict(label=e["label"], repo=e["repo"], quant=None, size=e["size"] * 1e9, layers=e["layers"], note=e["note"])
CORES = {e["key"]: _spec_from(e) for e in catalog.LADDERS["core"]}
TAB_MODELS = {e["key"]: _spec_from(e) for e in catalog.LADDERS["AI Coding"]}      # text models a tab can use instead of the core
_safe_from_now = set()                    # models that ran out of memory this session: they start in Safe from then on
CHAT_SYSTEM = "You are the helper inside Instant Easel Pro, a creative app. Answer clearly and plainly."
SYSTEMS = {"AI Chat": CHAT_SYSTEM,
           "AI Coding": "You are a careful programming assistant. Give working code first, then a short explanation.",
           "AI Images": "You turn requests into clear, detailed picture descriptions for an image model.",
           "AI Videos": "You turn requests into clear, detailed descriptions of short video scenes, including the motion."}
MAX_EXAMPLES_IN_PROMPT = 12

ROOT = paths.ai("my-models"); RUNTIME = os.path.join(ROOT, "runtime", "llama.cpp")
TEXT = os.path.join(ROOT, "text"); TABS_DIR = os.path.join(TEXT, "tabs")

_lock = threading.RLock(); _state = dict(state=None, detail="", model=None, progress=0.0)
_server = dict(proc=None, port=None, key=None)

def _set(state, detail="", progress=None, model=None):
    _state.update(state=state, detail=detail)
    if progress is not None: _state["progress"] = progress
    if model is not None: _state["model"] = model

def _prefs():
    import prefs; return prefs

def core_key():
    """the chosen core model; if none is chosen yet, the best one already downloaded, else the best one for this PC (catalog.py)"""
    k = _prefs().get("core_model")
    if k in CORES or (k == "custom-core" and model_file(k)): return k
    return pick("core", CORES)

def pick(area, keys):
    for e in catalog.options(area):                                            # best first: one that's already here
        if e["key"] in keys and model_file(e["key"]): return e["key"]
    for e in catalog.ladder(area):                                             # (or downloaded though it's big for this PC)
        if e["key"] in keys and model_file(e["key"]): return e["key"]
    b = catalog.best(area); return b["key"] if b and b["key"] in keys else next(iter(keys))

def spec(key):
    """what we know about a model; a model you added yourself ("custom-...") is named after its file"""
    if key and key.startswith("custom"):
        f = model_file(key); return dict(label=os.path.splitext(os.path.basename(f))[0] if f else "Your own model", layers=99, size=0,
                                         note="A model file you added yourself.")
    return CORES.get(key) or TAB_MODELS.get(key)

def tab_model(tab):
    """the model key a tab uses: its own choice in Settings > AI Models, else the core"""
    k = _prefs().get("model_" + _slug(tab)) if tab else None
    return k if k in TAB_MODELS or (k and k.startswith("custom") and model_file(k)) else core_key()

# ---------------------------------------------------------------- what's on disk
def _model_dir(key): return os.path.join(TEXT, key)

def _quant_of(f):
    m = re.search(r"[-_.]((?:IQ|Q)\d[\w]*?|F16|BF16)\.gguf$", f, re.I); return m.group(1).upper() if m else ""

def model_files(key):
    """{quant: path} of every size of this model that's downloaded (Download Everything keeps them all)"""
    d = _model_dir(key); out = {}
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.lower().endswith(".gguf") and "mmproj" not in f.lower(): out.setdefault(_quant_of(f) or f, os.path.join(d, f))
    return out

def model_file(key):
    """the file this PC should run: the size that suits its card (catalog.variant), else the next smaller one here, else any"""
    fs = model_files(key)
    if not fs: return None
    if len(fs) == 1: return next(iter(fs.values()))
    e = catalog.entry("core", key) or catalog.entry("AI Coding", key)
    if e and e.get("variants"):
        order = [q for _, q, _ in e["variants"]]; want = catalog.variant(e)[0]
        i = order.index(want) if want in order else 0
        for q in order[i:] + order[:i][::-1]:                                  # the suited one, then smaller, then bigger
            if q and q.upper() in fs: return fs[q.upper()]
    return fs[sorted(fs)[0]]

def server_exe():
    if not os.path.isdir(RUNTIME): return None
    name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
    for d, _, fs in os.walk(RUNTIME):
        if name in fs: return os.path.join(d, name)
    return None

def installed(key=None): return bool(server_exe() and model_file(key or core_key()))

def status():
    if _state["state"] in ("downloading", "loading", "busy", "error") or (_server["proc"] and _state["state"] == "ready"): return dict(_state)
    key = core_key()
    if installed(key): return dict(state="installed", detail=f"{spec(key)['label']} is downloaded; it starts the first time it's needed.", model=spec(key)["label"], progress=0)
    miss = [x for x, ok in (("the engine (llama.cpp)", server_exe()), (spec(key)["label"], model_file(key))) if not ok]
    return dict(state="not-installed", detail="Not downloaded yet: " + " and ".join(miss) + ".", model=None, progress=0)

def ready(): return _server["proc"] is not None and _server["proc"].poll() is None

def gpu():
    """the graphics cards Windows reports (name, memory GB); the engine itself finds the card through Vulkan"""
    out = []
    try:
        if sys.platform == "win32":
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                "Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name + '|' + $_.AdapterRAM }"],
                               capture_output=True, text=True, timeout=15, creationflags=0x08000000)
            for line in r.stdout.splitlines():
                if "|" in line:
                    n, ram = line.rsplit("|", 1)
                    try: gb = round(int(ram) / 2 ** 30, 1)
                    except ValueError: gb = 0
                    out.append(dict(name=n.strip(), gb=gb))
    except Exception: pass
    return out

# ---------------------------------------------------------------- downloading
def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "InstantEasel", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        if "api.github.com" in url and e.code in (403, 429):
            raise RuntimeError("GitHub is limiting how often this PC can look up downloads (it resets within an hour). Try again a bit later")
        raise

def github_files(repo, groups):
    """the files to download from a GitHub project's releases: [(name, url, size)], one per group.
    groups: [(name parts to look for, best first), required?]. The newest of the last 10 releases that has every file is used
    (the very latest can still be uploading its files); if none has the optional ones too, the newest with the required ones"""
    rels = _get_json(f"https://api.github.com/repos/{repo}/releases?per_page=10")
    if isinstance(rels, dict): rels = [rels]
    def pick(rel, alts):
        for want in alts:
            for a in rel.get("assets", []):
                n = a["name"]
                if want.lower() in n.lower() and n.endswith((".zip", ".tar.gz")) and not n.lower().startswith("cudart"):
                    return n, a["browser_download_url"], a.get("size", 0)
        return None
    for only_required in (False, True):
        for rel in rels:
            if rel.get("draft"): continue
            got = []
            for alts, required in groups:
                if only_required and not required: continue
                hit = pick(rel, alts)
                if not hit: break
                got.append(hit)
            else: return got
    raise RuntimeError(f"no {repo.split('/')[-1]} download for this computer in its last {len(rels)} releases")

def _fetch(url, dest, label, size_hint=0, report=None, tries=5):
    """download url to dest with progress. Robust: a dropped connection is retried (up to `tries` times, waiting a little longer
    each time) and carries on from where it stopped; a file that comes in short, or an error page instead of the file, is never
    kept. report(text, fraction) defaults to this module's status"""
    report = report or (lambda text, frac: _set("downloading", text, frac))
    tmp = dest + ".part"; last = None
    for attempt in range(1, tries + 1):
        have = os.path.getsize(tmp) if os.path.exists(tmp) else 0
        req = urllib.request.Request(url, headers={"User-Agent": "InstantEasel", **({"Range": f"bytes={have}-"} if have else {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                if have and r.status == 416: break                                     # the server says we already have it all
                if have and r.status != 206: have = 0                                  # the server started over
                length = int(r.headers.get("Content-Length") or 0); total = (have + length) if length else size_hint
                if "text/html" in (r.headers.get("Content-Type") or "") and not url.endswith((".html", ".htm")):
                    raise RuntimeError("the download site sent a web page instead of the file (it may need a sign-in, or moved)")
                with open(tmp, "ab" if have else "wb") as f:
                    done = have
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk: break
                        f.write(chunk); done += len(chunk)
                        report(f"Downloading {label}… {done / 1e9:.2f} of {total / 1e9:.2f} GB" if total else f"Downloading {label}… {done / 1e6:.0f} MB",
                               done / total if total else 0)
                if length and done < have + length: raise ConnectionError(f"the connection dropped at {done / 1e9:.2f} GB")
            break
        except urllib.error.HTTPError as e:
            if e.code == 416 and have: break
            if e.code in (401, 403, 404): raise RuntimeError(f"{label}: the download site said {e.code} ({e.reason}) — it may have moved or need a sign-in")
            last = e
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e: last = e
        if attempt == tries: raise RuntimeError(f"{label} didn't finish downloading after {tries} tries ({last}). Press Download again to carry on from where it stopped")
        report(f"Connection trouble — trying again ({attempt + 1} of {tries})…", 0); time.sleep(min(30, 3 * attempt))
    if os.path.getsize(tmp) < 1024: os.remove(tmp); raise RuntimeError(f"{label}: the download was empty")
    os.replace(tmp, dest)

def _runtime_files():
    """the llama.cpp downloads for this computer. Windows releases now come in parts: the programs (the 'cpu' file) plus the
    graphics-card part on its own (the 'vulkan' file, just ggml-vulkan.dll), so both are fetched and unpacked together"""
    if sys.platform == "win32":
        return github_files("ggml-org/llama.cpp", [(("bin-win-cpu-x64",), True), (("bin-win-vulkan-x64",), False)])
    if sys.platform == "darwin": return github_files("ggml-org/llama.cpp", [(("bin-macos-arm64", "bin-macos-x64"), True)])
    return github_files("ggml-org/llama.cpp", [(("bin-ubuntu-vulkan-x64", "bin-ubuntu-x64"), True)])

def unpack(arc, dest):
    if arc.endswith(".zip"):
        with zipfile.ZipFile(arc) as z: z.extractall(dest)
    else:
        with tarfile.open(arc) as t: t.extractall(dest, filter="data")

def _install_runtime(report=None):
    files = _runtime_files(); os.makedirs(os.path.join(ROOT, "runtime"), exist_ok=True)
    new = RUNTIME + ".new"; shutil.rmtree(new, ignore_errors=True); os.makedirs(new)
    for i, (name, url, size) in enumerate(files):
        arc = os.path.join(ROOT, "runtime", name)
        _fetch(url, arc, f"the engine (llama.cpp){f', part {i + 1} of {len(files)}' if len(files) > 1 else ''}", size, report=report)
        unpack(arc, new); os.remove(arc)
    exe_name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
    if not any(exe_name in fs for _, _, fs in os.walk(new)):
        shutil.rmtree(new, ignore_errors=True); raise RuntimeError("the engine downloaded but llama-server wasn't in it")
    if sys.platform == "win32":                                              # every part next to llama-server.exe, so it finds its graphics-card part
        home = next(d for d, _, fs in os.walk(new) if exe_name in fs)
        for d, _, fs in os.walk(new):
            if d != home:
                for f in fs:
                    if f.lower().endswith(".dll") and not os.path.exists(os.path.join(home, f)): shutil.move(os.path.join(d, f), os.path.join(home, f))
    shutil.rmtree(RUNTIME, ignore_errors=True); os.replace(new, RUNTIME); _help.clear()   # the old engine stays until the new one is unpacked
    exe = server_exe()
    if sys.platform != "win32": os.chmod(exe, 0o755)

def _pick_file(repo, quant):
    files = [s["rfilename"] for s in _get_json(f"https://huggingface.co/api/models/{repo}").get("siblings", [])]
    ggufs = [f for f in files if f.lower().endswith(".gguf") and "mmproj" not in f.lower()]
    exact = [f for f in ggufs if f.lower().endswith(f"-{quant.lower()}.gguf")]
    pick = exact or [f for f in ggufs if quant.lower() in f.lower()]
    if not pick: raise RuntimeError(f"{repo} has no {quant} file")
    return pick[0]

def download_size(key):
    """bytes the download of `key` will take on this PC (the file that suits this PC's card: catalog.variant)"""
    e = catalog.entry("core", key) or catalog.entry("AI Coding", key)
    return catalog.variant(e)[1] * 1e9 if e else (spec(key) or {}).get("size", 0)

def have_variant(key, quant): return quant.upper() in model_files(key)

def _install_model(key, quant=None, report=None, strict=False):
    s = spec(key); e = catalog.entry("core", key) or catalog.entry("AI Coding", key)
    quant = quant or s.get("quant") or (catalog.variant(e)[0] if e else "Q4_K_M")
    try: f = _pick_file(s["repo"], quant)
    except RuntimeError:
        if quant == "Q4_K_M" or strict: raise
        f = _pick_file(s["repo"], "Q4_K_M")                                    # that size isn't there: the usual one
    d = _model_dir(key); os.makedirs(d, exist_ok=True)
    size = next((g for _, q, g in (e or {}).get("variants", []) if q == quant), 0) * 1e9 or download_size(key)
    _fetch(f"https://huggingface.co/{s['repo']}/resolve/main/{f}", os.path.join(d, os.path.basename(f)), f"{s['label']} ({quant})", size, report=report)
    with open(os.path.join(d, "source.json"), "w") as fh: json.dump(dict(repo=s["repo"], file=f, when=datetime.datetime.now().isoformat(timespec="seconds")), fh)

def download(on_done=None, key=None):
    """the engine (if missing) and a model (the core by default), in the background. on_done(ok, message)"""
    key = key or core_key()
    def work():
        try:
            import storage
            ok, msg = storage.room("Shared models", 0 if model_file(key) else download_size(key))
            if not ok: raise RuntimeError(msg)
            if not server_exe(): _install_runtime()
            if not model_file(key): _install_model(key)
            _set(None, ""); on_done and on_done(True, f"{spec(key)['label']} is downloaded")
        except Exception as e:
            _set("error", f"Download failed: {e}"); on_done and on_done(False, str(e))
    _set("downloading", "Starting the download…", 0.0); threading.Thread(target=work, name="download model", daemon=True).start()

def add_file(key, path, on_done=None):
    """install a .gguf file you already have into a model slot (and the engine too, if it isn't here yet)"""
    d = _model_dir(key); os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        if f.endswith(".gguf"): os.remove(os.path.join(d, f))
    shutil.copy(path, os.path.join(d, os.path.basename(path)))
    if not server_exe():
        def work():
            try: _install_runtime(); _set(None, ""); on_done and on_done(True, "your model and the engine are set up")
            except Exception as e: _set("error", f"Download failed: {e}"); on_done and on_done(False, str(e))
        _set("downloading", "Getting the engine for your model…", 0.0); threading.Thread(target=work, daemon=True).start()
    elif on_done: on_done(True, "your model is set up")

def remove_model(key):
    if _server["key"] == key: stop()
    shutil.rmtree(_model_dir(key), ignore_errors=True)

# ---------------------------------------------------------------- the engine
def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

def _http(path, body=None, timeout=300):
    url = f"http://127.0.0.1:{_server['port']}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.load(r)

def free_card():
    """take the text model off the graphics card (before a picture is painted, so the image engine has the whole card)"""
    stop()

def stop():
    p = _server["proc"]
    if p is not None and p.poll() is None:
        try: p.terminate(); p.wait(10)
        except Exception:
            try: p.kill()
            except Exception: pass
    _server.update(proc=None, port=None, key=None)
    if _state["state"] == "ready": _set(None, "")
atexit.register(stop)

_help = {}
def _engine_help():
    """the engine's own option list (newer engines can fit a model to the free card memory by themselves: --fit)"""
    if "text" not in _help:
        try: _help["text"] = subprocess.run([server_exe(), "--help"], capture_output=True, text=True, timeout=30,
                                            creationflags=0x08000000 if sys.platform == "win32" else 0).stdout
        except Exception: _help["text"] = ""
    return _help["text"]

def _mode_args(mode, s):
    """the engine options for a speed mode. Fast: all on the card. Balanced: the engine fits it to the free card memory.
    Safe: the same with 2 GB kept free and a shorter memory (context). processor: nothing on the card"""
    h = _engine_help(); fit = "--fit" in h
    args = {"Fast": ["-ngl", "99", "-c", "8192"],
            "Balanced": (["--fit", "on"] if fit else ["-ngl", str(s["layers"])]) + ["-c", "8192"],
            "Safe": (["--fit", "on", "--fit-target", "2048"] if fit else ["-ngl", str(min(s["layers"], 12))]) + ["-c", "4096"],
            "processor": ["-ngl", "0", "-c", "4096"]}[mode]
    if "--threads" in h or not h: args += ["-t", str(hardware.threads_for_ai())]      # the processor's real cores
    return args

def _plan(key, f, wanted):
    """the modes to try, best first, after checking what memory is free right now (compress before it runs out)"""
    size = os.path.getsize(f) / 2 ** 30 if f and os.path.exists(f) else 0
    pc, free = hardware.pc(), hardware.free()
    if not pc.get("vram_gb"): return ["processor"]                                # no graphics card for AI
    mode = "Safe" if key in _safe_from_now else wanted
    if mode == "Fast" and free["vram_gb"] < size + 1.0: mode = "Balanced"          # it wouldn't all fit on the card now: let the engine fit it
    if free["ram_gb"] < 1.5:
        import jobs; jobs.note(f"PC MEMORY IS NEARLY FULL ({free['ram_gb']:.1f} GB free) — the text model may be slow. Close other programs to help")
    return list(dict.fromkeys([mode, "Safe", "processor"]))

def start(key=None, mode=None):
    """make sure the engine is running `key` (the core by default); swaps models if another one is loaded"""
    key = key or core_key()
    with _lock:
        if ready() and _server["key"] == key: return
        stop(); exe, f, s = server_exe(), model_file(key), spec(key)
        if not exe or not f: raise RuntimeError(f"{s['label']} isn't downloaded yet (Settings > AI Models)")
        for m in _plan(key, f, mode or _prefs().get("speed_text") or "Balanced"):    # the graphics card first; the processor if all else fails
            _set("loading", f"Starting {s['label']}{' on the processor' if m == 'processor' else ''}…", 0.0, s["label"])
            port = _free_port(); log = open(paths.log_file("text_engine.log"), "a", encoding="utf-8", errors="replace")
            args = _mode_args(m, s)
            log.write(f"\n=== {datetime.datetime.now().isoformat(timespec='seconds')} {s['label']} {m} {' '.join(args)} ===\n"); log.flush()
            cmd = [exe, "-m", f, *args, "--jinja", "--host", "127.0.0.1", "--port", str(port)]
            p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=os.path.dirname(exe),
                                 creationflags=0x08000000 if sys.platform == "win32" else 0)
            _server.update(proc=p, port=port, key=key, mode=m); t0 = time.time()
            while time.time() - t0 < 300 and p.poll() is None:
                try:
                    if _http("/health", timeout=5).get("status") == "ok":
                        where = {"processor": "processor", "Fast": "graphics card"}.get(m, "graphics card, fitted to its free memory")
                        _set("ready", f"{s['label']} ready ({where}, {m}).", 1.0, s["label"]); return
                except (urllib.error.URLError, ConnectionError, OSError, ValueError): pass
                time.sleep(0.5)
            stop()
        _set("error", f"{s['label']} wouldn't start (details in logs/text_engine.log)")
        raise RuntimeError(f"{s['label']} wouldn't start (details in logs/text_engine.log)")

def load_async(on_done=None, key=None):
    def work():
        try: start(key); on_done and on_done(True, _state["detail"])
        except Exception as e: on_done and on_done(False, str(e))
    threading.Thread(target=work, name="start model", daemon=True).start()

# ---------------------------------------------------------------- each tab's memory
def _slug(tab): return re.sub(r"[^A-Za-z0-9]+", "_", tab).strip("_")
def _tab_dir(tab): d = os.path.join(TABS_DIR, _slug(tab)); os.makedirs(d, exist_ok=True); return d
def _examples_file(tab): return os.path.join(_tab_dir(tab), "examples.jsonl")
def library_dir(tab): d = os.path.join(_tab_dir(tab), "library"); os.makedirs(d, exist_ok=True); return d

def tabs(): return sorted(d.replace("_", " ") for d in os.listdir(TABS_DIR)) if os.path.isdir(TABS_DIR) else []

def examples(tab):
    p = _examples_file(tab); out = []
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            try: out.append(json.loads(line))
            except Exception: pass
    return out

def teach(tab, text, answer, source="you"):
    rec = dict(text=str(text).strip(), answer=answer, source=source, when=datetime.datetime.now().isoformat(timespec="seconds"))
    with open(_examples_file(tab), "a", encoding="utf-8") as f: f.write(json.dumps(rec) + "\n")
    return rec

def info(tab):
    lib = library_dir(tab); n = sum(len(fs) for _, _, fs in os.walk(lib))
    return dict(examples=len(examples(tab)), library=n)

def transfer(src, dst):
    n = 0
    for ex in examples(src): teach(dst, ex["text"], ex["answer"], source=f"from {src}"); n += 1
    return dict(examples=n)

def forget(tab): shutil.rmtree(os.path.join(TABS_DIR, _slug(tab)), ignore_errors=True)

# ---------------------------------------------------------------- answering
_WORD = re.compile(r"[a-z0-9']+")
def _words(t): return set(w for w in _WORD.findall(t.lower()) if len(w) > 2)

def _shots(tab, text):
    """the tab's examples most like this question, as worked examples (dedupe: the same example once)"""
    words = _words(text); seen = set(); pool = []
    for i, e in enumerate(examples(tab)):
        k = (e["text"].lower(), json.dumps(e["answer"]))
        if k not in seen: seen.add(k); pool.append((i, e))
    pool = sorted(pool, key=lambda p: (-len(words & _words(p[1]["text"])), -p[0]))[:MAX_EXAMPLES_IN_PROMPT]
    out = []
    for _, e in reversed(pool):
        out += [dict(role="user", content=e["text"]), dict(role="assistant", content=e["answer"] if isinstance(e["answer"], str) else json.dumps(e["answer"]))]
    return out

def library_index(tab):
    import memory; return memory.Index(os.path.join(_tab_dir(tab), "library.db"))

def lookup(tab, text, k=3):
    """the library passages that best match the question (a full-text index, so big libraries stay fast)"""
    idx = library_index(tab); idx.sync_folder(library_dir(tab))
    return [(r["source"], r["text"]) for r in idx.search(text, k=k, kinds=("library",))]

def _chat(tab, body):
    """one answer from the engine. If the engine stops part-way (almost always: it ran out of memory), it's started again in Safe
    (less on the card, a shorter memory) and asked once more, and that model stays in Safe for the rest of the session"""
    for attempt in (1, 2):
        with _lock:
            before = _state["detail"]; _set("busy", "Thinking…")
            try: return _http("/v1/chat/completions", body)
            except Exception as e:
                if ready() or attempt == 2: raise
                key = _server.get("key") or tab_model(tab); _safe_from_now.add(key)
                with open(paths.log_file("text_engine.log"), "a", encoding="utf-8") as log:
                    log.write(f"\n=== the engine stopped mid-answer ({e.__class__.__name__}); starting again in Safe ===\n")
                import jobs; jobs.note("THE TEXT MODEL RAN OUT OF MEMORY — starting it again in Safe mode and asking once more")
                stop(); start(key, mode="Safe")
            finally:
                if _state["state"] == "busy": _set("ready", before)

def complete(tab, messages, max_tokens=800, temperature=0.7):
    """one answer for a full list of messages (system first) from the tab's model"""
    start(tab_model(tab))
    r = _chat(tab, dict(messages=messages, max_tokens=max_tokens, temperature=temperature, top_p=0.8,
                        chat_template_kwargs=dict(enable_thinking=False)))
    out = r["choices"][0]["message"].get("content") or ""
    return re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()

def ask(tab, text, system=None, max_tokens=600, use_library=True):
    start(tab_model(tab))
    sysmsg = system or SYSTEMS.get(tab, CHAT_SYSTEM)
    found = lookup(tab, text) if use_library else []
    if found: sysmsg += "\n\nUse these notes from the user's library when they help:\n" + "\n---\n".join(f"[{f}]\n{c}" for f, c in found)
    if use_library and tab in ("AI Chat", "AI Coding"):                          # names / words it may not know: looked up once, remembered
        try:
            import glossary; words = glossary.for_text(text, limit=3)
            if words: sysmsg += "\n\nWhat some words in the question mean (looked up):\n" + glossary.notes(words)
        except Exception: pass
    msgs = [dict(role="system", content=sysmsg)] + _shots(tab, text) + [dict(role="user", content=text)]
    r = _chat(tab, dict(messages=msgs, max_tokens=max_tokens, temperature=0.7, top_p=0.8, chat_template_kwargs=dict(enable_thinking=False)))
    out = r["choices"][0]["message"].get("content") or ""
    return re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()
