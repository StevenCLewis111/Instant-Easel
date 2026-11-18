"""
brain.py: Instant Easel's English text model: one base model shared by every tab, plus what each tab has learned, kept apart.

    The base model      Qwen3 (Apache 2.0), downloaded once into my-models/text/base/<name> the first time you ask for it.
                        A graphics card with 8 GB or more gets Qwen3-4B-Instruct-2507; otherwise the smaller Qwen3-1.7B. NVIDIA cards
                        are used through CUDA, Intel Arc cards through PyTorch's XPU build; with neither it runs on the processor.
                        It is never changed by training, so no tab can change what another tab knows.
    Each tab's memory   my-models/text/tabs/<Tab_Name>/
                          examples.jsonl   everything you taught that tab (text you wrote -> what it should mean)
                          adapter/         a small add-on (LoRA) trained from those examples, used only for that tab
                        A tab uses its own examples straight away (shown to the model as worked examples); "Train" bakes them into
                        the tab's adapter. Nothing moves between tabs unless you transfer it (transfer()).

    import brain
    brain.status()                       -> dict(state=..., detail=..., model=...)   states: missing-libs, not-installed, downloading,
                                            loading, ready, busy, error
    brain.download(on_done=None)         start the one-time download (background)
    brain.read_settings("AI Images", "a stormy night over jagged peaks", schema)   -> dict of settings (only allowed keys / values)
    brain.ask("AI Chat", "hello")        -> plain text answer
    brain.teach("AI Images", "moody", {"time": "night", "clouds": "many"})
    brain.train("AI Images", progress=fn)   brain.transfer("AI Images", "AI Training")
Needs: pip install -r requirements-ai.txt   (torch, transformers, peft, accelerate, huggingface_hub). Without them the app works as
before (the built-in word rules) and this module just reports "missing-libs".
"""
import os, json, re, shutil, threading, time, datetime
import paths

MODELS = {"large": dict(repo="Qwen/Qwen3-4B-Instruct-2507", name="Qwen3-4B-Instruct-2507", size=8.1e9, label="Qwen3 4B Instruct (needs a graphics card with 8 GB+)"),
          "small": dict(repo="Qwen/Qwen3-1.7B", name="Qwen3-1.7B", size=4.1e9, label="Qwen3 1.7B (any PC; slower without a graphics card)")}
ROOT = paths.data("my-models", "text"); BASE_DIR = os.path.join(ROOT, "base"); TABS_DIR = os.path.join(ROOT, "tabs")
MAX_EXAMPLES_IN_PROMPT = 12

_lock = threading.RLock(); _state = {"state": None, "detail": "", "model": None, "progress": 0.0}
_model = None; _tok = None; _device = "cpu"; _adapters = set()

# ---------------------------------------------------------------- what's installed
def libs_ok():
    try:
        import torch, transformers, peft, huggingface_hub  # noqa: F401
        return True
    except Exception: return False

def gpu():
    """(name, memory in GB, torch device) of the graphics card to use, or None. NVIDIA cards work through CUDA; Intel Arc cards
    through PyTorch's XPU build. With more than one (an Arc card plus the processor's built-in graphics) the one with the most
    memory of its own is used"""
    try: import torch
    except Exception: return None
    found = []
    try:
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                p = torch.cuda.get_device_properties(i); found.append((p.name, p.total_memory / 1e9, f"cuda:{i}"))
    except Exception: pass
    try:
        if hasattr(torch, "xpu") and torch.xpu.is_available():
            for i in range(torch.xpu.device_count()):
                p = torch.xpu.get_device_properties(i); found.append((p.name, p.total_memory / 1e9, f"xpu:{i}"))
    except Exception: pass
    if not found: return None
    dedicated = [f for f in found if not any(w in f[0].lower() for w in ("uhd", "iris", "integrated"))]   # an Arc / GeForce card before built-in graphics
    return max(dedicated or found, key=lambda f: f[1])

def choice():
    """which model: the setting if you picked one, else by your graphics card"""
    try:
        import prefs; c = prefs.get("text_model")
        if c in MODELS: return c
    except Exception: pass
    g = gpu(); return "large" if g and g[1] >= 7.5 else "small"

def model_dir(key=None): return os.path.join(BASE_DIR, MODELS[key or choice()]["name"])

def installed(key=None):
    d = model_dir(key); return os.path.exists(os.path.join(d, "config.json")) and any(f.endswith(".safetensors") for f in os.listdir(d))

def status():
    with _lock:
        if _state["state"] in ("downloading", "loading", "busy", "error") or _model is not None:
            return dict(_state, state=_state["state"] if _model is None or _state["state"] == "busy" else "ready")
    if not libs_ok(): return dict(state="missing-libs", detail="The AI add-ons aren't installed (pip install -r requirements-ai.txt).", model=None, progress=0)
    key = choice()
    if not installed(key): return dict(state="not-installed", detail=f"{MODELS[key]['label']} isn't downloaded yet.", model=MODELS[key]["name"], progress=0)
    return dict(state="installed", detail=f"{MODELS[key]['name']} is downloaded (loads the first time it's needed).", model=MODELS[key]["name"], progress=1)

def ready(): return _model is not None

def _set(state, detail="", progress=None, model=None):
    with _lock:
        _state.update(state=state, detail=detail)
        if progress is not None: _state["progress"] = progress
        if model is not None: _state["model"] = model

# ---------------------------------------------------------------- download (once) and load
def _folder_size(d):
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(d) for f in fs) if os.path.isdir(d) else 0

def download(on_done=None, key=None):
    """fetch the base model from Hugging Face into my-models/text/base (background thread). on_done(ok, message)"""
    key = key or choice(); m = MODELS[key]; d = model_dir(key)
    def work():
        try:
            from huggingface_hub import snapshot_download
            _set("downloading", f"Downloading {m['name']}…", 0.0, m["name"]); os.makedirs(d, exist_ok=True)
            stop = threading.Event()
            def watch():
                while not stop.wait(1.0): _set("downloading", f"Downloading {m['name']}…", min(0.99, _folder_size(d) / m["size"]))
            threading.Thread(target=watch, daemon=True).start()
            try: snapshot_download(m["repo"], local_dir=d, allow_patterns=["*.json", "*.safetensors", "*.txt", "tokenizer*", "merges.txt", "vocab.json"])
            finally: stop.set()
            _set("installed", f"{m['name']} downloaded.", 1.0); on_done and on_done(True, f"{m['name']} downloaded")
        except Exception as e:
            _set("error", f"Download failed: {e}"); on_done and on_done(False, str(e))
    threading.Thread(target=work, name="text model download", daemon=True).start()

def load(key=None):
    """load the base model (and every tab's adapter) into memory; safe to call again"""
    global _model, _tok, _device
    with _lock:
        if _model is not None: return True
        key = key or choice(); d = model_dir(key)
        if not installed(key): raise RuntimeError(f"{MODELS[key]['name']} isn't downloaded yet")
        _set("loading", f"Loading {MODELS[key]['name']}…", model=MODELS[key]["name"])
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        g = gpu(); _device = g[2] if g else "cpu"
        _tok = AutoTokenizer.from_pretrained(d)
        _model = AutoModelForCausalLM.from_pretrained(d, dtype=torch.bfloat16).to(_device)            # half the memory of full precision
        _model.eval(); _adapters.clear()
        for tab in tabs():
            if os.path.exists(os.path.join(_adapter_dir(tab), "adapter_config.json")): _load_adapter(tab)
        _set("ready", f"{MODELS[key]['name']} ready ({'graphics card: ' + g[0] if g else 'processor'}).")
        return True

def load_async(on_done=None):
    def work():
        try: load(); on_done and on_done(True, "ready")
        except Exception as e: _set("error", f"Couldn't load the text model: {e}"); on_done and on_done(False, str(e))
    threading.Thread(target=work, name="text model load", daemon=True).start()

# ---------------------------------------------------------------- each tab's memory
def _slug(tab): return re.sub(r"[^A-Za-z0-9]+", "_", tab).strip("_")
def _tab_dir(tab): d = os.path.join(TABS_DIR, _slug(tab)); os.makedirs(d, exist_ok=True); return d
def _examples_file(tab): return os.path.join(_tab_dir(tab), "examples.jsonl")
def _adapter_dir(tab): return os.path.join(_tab_dir(tab), "adapter")

def tabs():
    return sorted(d.replace("_", " ") for d in os.listdir(TABS_DIR)) if os.path.isdir(TABS_DIR) else []

def examples(tab):
    p = _examples_file(tab); out = []
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            try: out.append(json.loads(line))
            except Exception: pass
    return out

def teach(tab, text, answer, source="you"):
    """remember: in this tab, `text` means `answer` (a dict of settings, or plain text)"""
    rec = dict(text=str(text).strip(), answer=answer, source=source, when=datetime.datetime.now().isoformat(timespec="seconds"))
    with open(_examples_file(tab), "a", encoding="utf-8") as f: f.write(json.dumps(rec) + "\n")
    return rec

def info(tab):
    """how much a tab has learned"""
    ex = examples(tab); ad = os.path.exists(os.path.join(_adapter_dir(tab), "adapter_config.json"))
    trained = json.load(open(os.path.join(_tab_dir(tab), "trained.json"))) if os.path.exists(os.path.join(_tab_dir(tab), "trained.json")) else {}
    return dict(examples=len(ex), adapter=ad, trained_on=trained.get("examples", 0), trained_when=trained.get("when", ""))

def transfer(src, dst, adapter=True):
    """send what `src` learned to `dst`: its examples are added to dst's (marked where they came from); with adapter=True and src
    trained, dst gets a copy of src's adapter too (dst can be trained again later on everything it then has)"""
    n = 0
    for ex in examples(src):
        teach(dst, ex["text"], ex["answer"], source=f"from {src}"); n += 1
    copied = False
    if adapter and os.path.exists(os.path.join(_adapter_dir(src), "adapter_config.json")):
        shutil.rmtree(_adapter_dir(dst), ignore_errors=True); shutil.copytree(_adapter_dir(src), _adapter_dir(dst)); copied = True
        t = os.path.join(_tab_dir(src), "trained.json")
        if os.path.exists(t):                                                                  # what the copied add-on was trained on
            d = json.load(open(t)); d["examples"] = len(examples(dst)); d["from"] = src; json.dump(d, open(os.path.join(_tab_dir(dst), "trained.json"), "w"))
        with _lock:
            if _model is not None: _load_adapter(dst, reload=True)
    return dict(examples=n, adapter=copied)

def forget(tab):
    """clear everything one tab learned (the base model and other tabs are untouched)"""
    with _lock:
        if _model is not None and _slug(tab) in _adapters:
            try: _model.delete_adapter(_slug(tab))
            except Exception: pass
            _adapters.discard(_slug(tab))
    shutil.rmtree(os.path.join(TABS_DIR, _slug(tab)), ignore_errors=True)

# ---------------------------------------------------------------- asking
def _load_adapter(tab, reload=False):
    global _model
    from peft import PeftModel
    name = _slug(tab)
    if name in _adapters and not reload: return
    if name in _adapters:
        try: _model.delete_adapter(name)
        except Exception: pass
    if not hasattr(_model, "peft_config"): _model = PeftModel.from_pretrained(_model, _adapter_dir(tab), adapter_name=name)
    else: _model.load_adapter(_adapter_dir(tab), adapter_name=name)
    _model.eval(); _adapters.add(name)

def _similar(tab, text, k=MAX_EXAMPLES_IN_PROMPT):
    """the tab's examples most like this text (shared words), newest first on ties"""
    words = set(re.findall(r"[a-z0-9']+", text.lower())); ex = examples(tab)
    scored = sorted(enumerate(ex), key=lambda p: (-len(words & set(re.findall(r"[a-z0-9']+", p[1]["text"].lower()))), -p[0]))
    return [e for _, e in scored[:k]]

def _generate(tab, messages, max_new_tokens=200):
    import torch
    with _lock:
        if _model is None: load()
        before = _state["detail"]; _set("busy", "Thinking…")
        try:
            prompt = _tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
            ids = _tok(prompt, return_tensors="pt").to(_device)
            ctx = None; name = _slug(tab)
            if hasattr(_model, "peft_config"):
                if name in _adapters: _model.set_adapter(name)
                else: ctx = _model.disable_adapter()                                    # a tab with no adapter: the plain base model
            with torch.no_grad():
                if ctx is not None:
                    with ctx: out = _model.generate(**ids, max_new_tokens=max_new_tokens, do_sample=False)
                else: out = _model.generate(**ids, max_new_tokens=max_new_tokens, do_sample=False)
            return _tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        finally: _set("ready", before if before and not before.startswith(("Thinking", "Training", "Loading")) else "Ready.")

CHAT_SYSTEM = "You are the helper inside Instant Easel, a painting app. Answer briefly and plainly."

def _untrained(tab):
    """examples taught since the tab was last trained (those are shown to the model as worked examples; trained ones are already in
    its adapter)"""
    ex = examples(tab); return ex[info(tab)["trained_on"]:] if info(tab)["adapter"] else ex

def _shots(tab, text, kind):
    pool = _untrained(tab); words = set(re.findall(r"[a-z0-9']+", text.lower()))
    pool = [e for e in pool if isinstance(e["answer"], dict) == (kind == "settings")]
    pool = sorted(enumerate(pool), key=lambda p: (-len(words & set(re.findall(r"[a-z0-9']+", p[1]["text"].lower()))), -p[0]))[:MAX_EXAMPLES_IN_PROMPT]
    out = []
    for _, e in reversed(pool):
        out += [dict(role="user", content=e["text"]), dict(role="assistant", content=json.dumps(e["answer"]) if kind == "settings" else str(e["answer"]))]
    return out

def _settings_system(schema):
    return ("You turn a painting request into settings for Instant Easel. Reply with ONE JSON object and nothing else. Use only these "
            "keys and values, and leave out anything the request doesn't mention:\n" + _schema_text(schema))

def _schema_file(tab): return os.path.join(_tab_dir(tab), "schema.json")

def ask(tab, text, system=CHAT_SYSTEM, max_new_tokens=300):
    msgs = [dict(role="system", content=system)] + _shots(tab, text, "chat") + [dict(role="user", content=text)]
    return _generate(tab, msgs, max_new_tokens)

def _schema_text(schema):
    lines = []
    for k, v in schema.items():
        if isinstance(v, (list, tuple)): lines.append(f'  "{k}": one of {", ".join(json.dumps(x) for x in v)}')
        else: lines.append(f'  "{k}": {v}')
    return "\n".join(lines)

def _clean(d, schema):
    """keep only the allowed settings, with allowed values"""
    out = {}
    for k, v in (d or {}).items():
        if k not in schema: continue
        allowed = schema[k]
        if isinstance(allowed, (list, tuple)):
            if v in allowed: out[k] = v
            elif isinstance(v, str) and v.lower() in [str(a).lower() for a in allowed]: out[k] = next(a for a in allowed if str(a).lower() == v.lower())
        elif allowed == "number 0..1":
            try: out[k] = max(0.0, min(1.0, float(v)))
            except Exception: pass
        elif allowed == "text": out[k] = str(v)
    return out

def read_settings(tab, text, schema):
    """English -> a dict of settings for this tab (only keys in schema; values from its lists). {} if it can't tell"""
    try: json.dump(schema, open(_schema_file(tab), "w"))                               # remembered, so training uses the same wording
    except Exception: pass
    msgs = [dict(role="system", content=_settings_system(schema))] + _shots(tab, text, "settings") + [dict(role="user", content=text)]
    reply = _generate(tab, msgs, 160); m = re.search(r"\{.*\}", reply, re.S)
    if not m: return {}
    try: return _clean(json.loads(m.group(0)), schema)
    except Exception: return {}

# ---------------------------------------------------------------- training a tab
def train(tab, epochs=3, progress=None, rank=8, lr=2e-4, holdout=0.0, dedupe=True):
    """bake a tab's examples into its own small adapter (LoRA). The base model and the other tabs don't change. progress(fraction, text)
    lr: learning speed. holdout: a share of the examples (e.g. 0.1) kept back to check it; training stops early once the check gets
    worse (it has started memorising). dedupe: the same example taught twice counts once."""
    import torch
    from peft import LoraConfig, get_peft_model
    ex = examples(tab)
    if not ex: raise RuntimeError(f"{tab} has nothing to learn from yet — teach it first")
    if dedupe:
        seen, uniq = set(), []
        for e in ex:
            k = (e["text"].strip().lower(), json.dumps(e["answer"], sort_keys=True))
            if k not in seen: seen.add(k); uniq.append(e)
        ex = uniq
    global _model
    with _lock:
        if _model is None: load()
        _set("busy", f"Training {tab}…"); name = _slug(tab); tmp = name + "_training"
        try:
            cfg = LoraConfig(r=rank, lora_alpha=rank * 2, lora_dropout=0.05, target_modules=["q_proj", "k_proj", "v_proj", "o_proj"], task_type="CAUSAL_LM")
            if hasattr(_model, "peft_config"):
                if tmp in _model.peft_config: _model.delete_adapter(tmp)
                _model.add_adapter(tmp, cfg)
            else: _model = get_peft_model(_model, cfg, adapter_name=tmp)
            _model.set_adapter(tmp)
            for n_, p in _model.named_parameters(): p.requires_grad = f".{tmp}." in n_      # only this tab's new adapter learns
            opt = torch.optim.AdamW([p for p in _model.parameters() if p.requires_grad], lr=lr)
            schema = json.load(open(_schema_file(tab))) if os.path.exists(_schema_file(tab)) else None
            def pair(e):                                                             # the same wording the app uses when it asks
                if isinstance(e["answer"], dict):
                    ans = json.dumps(e["answer"]); sysmsg = _settings_system(schema) if schema else None
                else: ans = str(e["answer"]); sysmsg = CHAT_SYSTEM
                msgs = ([dict(role="system", content=sysmsg)] if sysmsg else []) + [dict(role="user", content=e["text"])]
                prompt = _tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)
                p_ids = _tok(prompt)["input_ids"]; a_ids = _tok(ans + _tok.eos_token)["input_ids"] if _tok.eos_token else _tok(ans)["input_ids"]
                ids = torch.tensor([p_ids + a_ids], device=_device); labels = ids.clone(); labels[0, :len(p_ids)] = -100   # learn only the answer
                return ids, labels
            data = [pair(e) for e in ex]; check = []
            if holdout and len(data) >= 10:                                          # kept back to check it (never trained on)
                import random; order = list(range(len(data))); random.Random(0).shuffle(order); k = max(1, int(round(len(data) * holdout)))
                check = [data[i] for i in order[:k]]; data = [data[i] for i in order[k:]]
            def check_loss():
                with torch.no_grad(): return sum(_model(input_ids=i, labels=l).loss.item() for i, l in check) / len(check)
            steps = epochs * len(data); done = 0; _model.train(); best = None; stopped = 0
            for ep in range(epochs):
                for ids, labels in data:
                    loss = _model(input_ids=ids, labels=labels).loss; loss.backward(); opt.step(); opt.zero_grad(); done += 1
                    _set("busy", f"Training {tab}… {done}/{steps}", done / steps)
                    if progress: progress(done / steps, f"step {done} of {steps}, loss {loss.item():.3f}")
                if check:
                    _model.eval(); cl = check_loss(); _model.train()
                    if progress: progress(done / steps, f"pass {ep + 1}: check score {cl:.3f} (lower is better)")
                    if best is not None and cl > best: stopped = ep + 1; break               # worse on the held-back examples: stop here
                    best = cl if best is None else min(best, cl)
            _model.eval()
            out = os.path.join(_tab_dir(tab), "adapter_new"); shutil.rmtree(out, ignore_errors=True)
            _model.save_pretrained(out, selected_adapters=[tmp])
            src = os.path.join(out, tmp) if os.path.isdir(os.path.join(out, tmp)) else out
            shutil.rmtree(_adapter_dir(tab), ignore_errors=True); shutil.move(src, _adapter_dir(tab)); shutil.rmtree(out, ignore_errors=True)
            _model.delete_adapter(tmp)
            json.dump(dict(examples=len(examples(tab)), when=datetime.datetime.now().isoformat(timespec="seconds"), epochs=epochs, lr=lr, rank=rank,
                           check=len(check), check_loss=best, stopped_after=stopped), open(os.path.join(_tab_dir(tab), "trained.json"), "w"))
            _load_adapter(tab, reload=True)
            return dict(examples=len(ex), steps=steps, check_loss=best, stopped_after=stopped)
        finally:
            for p in _model.parameters(): p.requires_grad = False
            _set("ready", f"{_state.get('model') or 'The text model'} ready ({'processor' if _device == 'cpu' else 'graphics card'}).")

def train_async(tab, on_done=None, progress=None, **settings):
    """settings: epochs, rank, lr, holdout, dedupe (see train)"""
    def work():
        try:
            r = train(tab, progress=progress, **settings)
            msg = f"{tab}: learned from {r['examples']} examples" + (f"; stopped after pass {r['stopped_after']} (it had started memorising)" if r.get("stopped_after") else "")
            on_done and on_done(True, msg)
        except Exception as e: _set("error" if _model is None else "ready", str(e)); on_done and on_done(False, str(e))
    threading.Thread(target=work, name=f"train {tab}", daemon=True).start()
