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
import paths

# ---------------------------------------------------------------- the models
CORES = {
    "4b": dict(label="Qwen3.5 4B", repo="bartowski/Qwen_Qwen3.5-4B-GGUF", quant="Q4_K_M", size=3.0e9, layers=99,
               note="About 3 GB. Fits fully on a 6 GB graphics card, so it's quick."),
    "9b": dict(label="Qwen3.5 9B", repo="bartowski/Qwen_Qwen3.5-9B-GGUF", quant="Q4_K_M", size=5.7e9, layers=24,
               note="About 5.7 GB. Smarter; on a 6 GB card part of it runs on the processor, so it's slower (needs 16 GB+ PC memory)."),
}
TAB_MODELS = {                             # text models a tab can use instead of the core
    "coder7b": dict(label="Qwen2.5 Coder 7B", repo="bartowski/Qwen2.5-Coder-7B-Instruct-GGUF", quant="Q4_K_M", size=4.7e9, layers=99,
                    note="Made for code. About 4.7 GB; fits on a 6 GB card."),
}
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
    k = _prefs().get("core_model"); return k if k in CORES or (k == "custom-core" and model_file(k)) else "4b"

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

def model_file(key):
    d = _model_dir(key)
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.lower().endswith(".gguf") and "mmproj" not in f.lower(): return os.path.join(d, f)
    return None

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
    with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)

def _fetch(url, dest, label, size_hint=0, report=None):
    """download url to dest with progress (resumes a part-finished file). report(text, fraction) defaults to this module's status"""
    report = report or (lambda text, frac: _set("downloading", text, frac))
    tmp = dest + ".part"; have = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    req = urllib.request.Request(url, headers={"User-Agent": "InstantEasel", **({"Range": f"bytes={have}-"} if have else {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        if have and r.status != 206: have = 0                                          # the server started over
        total = have + int(r.headers.get("Content-Length") or 0) or size_hint
        with open(tmp, "ab" if have else "wb") as f:
            done = have
            while True:
                chunk = r.read(1 << 20)
                if not chunk: break
                f.write(chunk); done += len(chunk)
                report(f"Downloading {label}… {done / 1e9:.2f} of {total / 1e9:.2f} GB" if total else f"Downloading {label}… {done / 1e6:.0f} MB",
                       done / total if total else 0)
    os.replace(tmp, dest)

def _runtime_asset():
    """the right llama.cpp download for this computer"""
    rel = _get_json("https://api.github.com/repos/ggml-org/llama.cpp/releases/latest")
    if sys.platform == "win32": wants = ("bin-win-vulkan-x64", "bin-win-cpu-x64")
    elif sys.platform == "darwin": wants = ("bin-macos-arm64", "bin-macos-x64")
    else: wants = ("bin-ubuntu-vulkan-x64", "bin-ubuntu-x64")
    for w in wants:
        for a in rel.get("assets", []):
            if w in a["name"] and a["name"].endswith((".zip", ".tar.gz")): return a["name"], a["browser_download_url"], a.get("size", 0)
    raise RuntimeError("no llama.cpp download found for this computer")

def _install_runtime():
    name, url, size = _runtime_asset(); os.makedirs(RUNTIME, exist_ok=True); arc = os.path.join(ROOT, "runtime", name)
    _fetch(url, arc, "the engine (llama.cpp)", size)
    shutil.rmtree(RUNTIME, ignore_errors=True); os.makedirs(RUNTIME)
    if name.endswith(".zip"):
        with zipfile.ZipFile(arc) as z: z.extractall(RUNTIME)
    else:
        with tarfile.open(arc) as t: t.extractall(RUNTIME, filter="data")
    os.remove(arc)
    exe = server_exe()
    if not exe: raise RuntimeError("the engine downloaded but llama-server wasn't in it")
    if sys.platform != "win32": os.chmod(exe, 0o755)

def _pick_file(repo, quant):
    files = [s["rfilename"] for s in _get_json(f"https://huggingface.co/api/models/{repo}").get("siblings", [])]
    ggufs = [f for f in files if f.lower().endswith(".gguf") and "mmproj" not in f.lower()]
    exact = [f for f in ggufs if f.lower().endswith(f"-{quant.lower()}.gguf")]
    pick = exact or [f for f in ggufs if quant.lower() in f.lower()]
    if not pick: raise RuntimeError(f"{repo} has no {quant} file")
    return pick[0]

def _install_model(key):
    s = spec(key); f = _pick_file(s["repo"], s["quant"]); d = _model_dir(key); os.makedirs(d, exist_ok=True)
    _fetch(f"https://huggingface.co/{s['repo']}/resolve/main/{f}", os.path.join(d, os.path.basename(f)), s["label"], s["size"])
    with open(os.path.join(d, "source.json"), "w") as fh: json.dump(dict(repo=s["repo"], file=f, when=datetime.datetime.now().isoformat(timespec="seconds")), fh)

def download(on_done=None, key=None):
    """the engine (if missing) and a model (the core by default), in the background. on_done(ok, message)"""
    key = key or core_key()
    def work():
        try:
            import storage
            ok, msg = storage.room("Shared models", 0 if model_file(key) else spec(key)["size"])
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

def start(key=None):
    """make sure the engine is running `key` (the core by default); swaps models if another one is loaded"""
    key = key or core_key()
    with _lock:
        if ready() and _server["key"] == key: return
        stop(); exe, f, s = server_exe(), model_file(key), spec(key)
        if not exe or not f: raise RuntimeError(f"{s['label']} isn't downloaded yet (Settings > AI Models)")
        mode = _prefs().get("speed_text") or "Balanced"                            # Fast / Balanced / Safe
        first = {"Fast": 99, "Balanced": s["layers"], "Safe": min(s["layers"], 12)}.get(mode, s["layers"])
        ctx = "4096" if mode == "Safe" else "8192"                                 # Safe: a shorter memory too, so it needs less room
        for layers in dict.fromkeys((first, 0)):                                   # the graphics card first; the processor if that fails
            _set("loading", f"Starting {s['label']}{' on the processor' if not layers else ''}…", 0.0, s["label"])
            port = _free_port(); log = open(paths.log_file("text_engine.log"), "a", encoding="utf-8", errors="replace")
            log.write(f"\n=== {datetime.datetime.now().isoformat(timespec='seconds')} {s['label']} {mode} layers={layers} context={ctx} ===\n"); log.flush()
            cmd = [exe, "-m", f, "-ngl", str(layers), "-c", ctx, "--jinja", "--host", "127.0.0.1", "--port", str(port)]
            p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=os.path.dirname(exe),
                                 creationflags=0x08000000 if sys.platform == "win32" else 0)
            _server.update(proc=p, port=port, key=key); t0 = time.time()
            while time.time() - t0 < 300 and p.poll() is None:
                try:
                    if _http("/health", timeout=5).get("status") == "ok":
                        where = "processor" if not layers else ("graphics card" if layers >= 99 else "graphics card + processor")
                        _set("ready", f"{s['label']} ready ({where}, {mode}).", 1.0, s["label"]); return
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

def complete(tab, messages, max_tokens=800, temperature=0.7):
    """one answer for a full list of messages (system first) from the tab's model"""
    start(tab_model(tab))
    with _lock:
        before = _state["detail"]; _set("busy", "Thinking…")
        try:
            r = _http("/v1/chat/completions", dict(messages=messages, max_tokens=max_tokens, temperature=temperature, top_p=0.8,
                                                  chat_template_kwargs=dict(enable_thinking=False)))
        finally: _set("ready", before)
    out = r["choices"][0]["message"].get("content") or ""
    return re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()

def ask(tab, text, system=None, max_tokens=600, use_library=True):
    start(tab_model(tab))
    sysmsg = system or SYSTEMS.get(tab, CHAT_SYSTEM)
    found = lookup(tab, text) if use_library else []
    if found: sysmsg += "\n\nUse these notes from the user's library when they help:\n" + "\n---\n".join(f"[{f}]\n{c}" for f, c in found)
    msgs = [dict(role="system", content=sysmsg)] + _shots(tab, text) + [dict(role="user", content=text)]
    with _lock:
        before = _state["detail"]; _set("busy", "Thinking…")
        try:
            r = _http("/v1/chat/completions", dict(messages=msgs, max_tokens=max_tokens, temperature=0.7, top_p=0.8,
                                                  chat_template_kwargs=dict(enable_thinking=False)))
        finally: _set("ready", before)
    out = r["choices"][0]["message"].get("content") or ""
    return re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()
