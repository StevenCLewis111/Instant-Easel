"""
imaging.py: Instant Easel Pro's image engine. Paints pictures from words (and repaints pictures) on this PC.

    The engine      stable-diffusion.cpp (sd-cli), downloaded once: the Vulkan build on Windows, which runs on Intel Arc, AMD and
                    NVIDIA cards. Like the text engine it needs no Python add-ons.
    The model       chosen in Settings > AI Models > AI Images, from what fits this PC (catalog.py):
                      Z-Image Turbo     the best quality for a home PC. Three files in my-models/image/zimage/: the picture model
                                        (the size that suits the card: Q8 on 12 GB+, Q4 on 6 GB+, Q3 below), its Qwen3 4B
                                        text reader and the FLUX picture decoder. 1024 pixels, 8 steps.
                      Stable Diffusion 1.5   small and quick; your own image models (Cartoon, Fashion...) train on it
                      Stable Diffusion XL / a model file you add (.safetensors) - put in my-models/image/
    Your models     an image model from AI Training > Image Learning (Cartoon, Fashion...) switches on its trained add-on
                    (lora/<name>.safetensors) and its trigger word. They're made for Stable Diffusion 1.5.
    Every picture   is saved straight into your Images folder (Settings > General > Your work folder).

Memory guard (every picture): the text model is taken off the graphics card first, then the free card and PC memory are checked
and the speed mode is lowered if the model wouldn't fit (Fast -> Balanced -> Safe). If the engine still runs out of memory, the
picture is painted again in Safe, then smaller, instead of failing.

    import imaging
    imaging.status()                     -> dict(state, detail, progress)
    imaging.download(on_done, key)       engine + the chosen model (background)
    imaging.paint("a red shoe", n=1, on_progress=fn) -> [paths of the saved pictures]
"""
import os, sys, re, json, shutil, threading, subprocess, zipfile, tarfile, random, time, datetime
import paths

SD15 = dict(label="Stable Diffusion 1.5", repo="Comfy-Org/stable-diffusion-v1-5-archive", file="v1-5-pruned-emaonly-fp16.safetensors", size=2.13e9)
ZIMAGE = dict(label="Z-Image Turbo", repo="leejet/Z-Image-Turbo-GGUF",                                  # made for stable-diffusion.cpp
              llm_repo="unsloth/Qwen3-4B-Instruct-2507-GGUF", vae_repo="Comfy-Org/z_image_turbo", vae_file="split_files/vae/ae.safetensors")
ROOT = paths.ai("my-models"); RUNTIME = os.path.join(ROOT, "runtime", "stable-diffusion.cpp"); IMAGE = os.path.join(ROOT, "image")
ZDIR = os.path.join(IMAGE, "zimage")
NEGATIVE = "blurry, low quality, deformed, extra fingers, watermark, text, signature"
SHAPES = {"sd": {"Square": (512, 512), "Tall": (512, 768), "Wide": (768, 512)},
          "zimage": {"Square": (1024, 1024), "Tall": (768, 1024), "Wide": (1024, 768)}}
SIZES = {"Square": None, "Tall": None, "Wide": None}                     # the page's size names; pixels depend on the model (SHAPES)
GUIDANCE = {"Loosely": 5.0, "Normal": 7.0, "Closely": 9.5}            # how closely the picture follows the words (cfg scale)
ZSTEPS = {12: 6, 20: 8, 30: 10}                                         # Z-Image Turbo is made for about 8 steps
last = dict(seed=None, note="")                                         # the seed of the last paint() (picture i used seed + i)
OOM = re.compile(r"out of (device |host )?memory|ErrorOutOfDeviceMemory|OutOfDeviceMemory|DeviceLost|failed to allocate|"
                 r"allocation .{0,40}failed|bad_alloc|VK_ERROR_OUT_OF", re.I)

def fit_size(im, long_side=None):
    """a working size with the picture's own shape: the long side long_side (the model's size by default), both sides multiples of 64"""
    long_side = long_side or (1024 if kind() == "zimage" else 768)
    k = long_side / max(im.size); return max(256, round(im.width * k / 64) * 64), max(256, round(im.height * k / 64) * 64)

def pixels(size):
    """(w, h) for a size name ('Square', or an old saved name like 'Square 512 x 512') with the chosen model"""
    if isinstance(size, tuple): return size
    shape = str(size).split()[0] if size else "Square"
    return SHAPES["zimage" if kind() == "zimage" else "sd"].get(shape, SHAPES["sd"]["Square"])

_state = dict(state=None, detail="", progress=0.0); _proc = dict(p=None); _lock = threading.Lock(); _help = {}

def _set(state, detail="", progress=None):
    _state.update(state=state, detail=detail)
    if progress is not None: _state["progress"] = progress

def _prefs():
    import prefs; return prefs

# ---------------------------------------------------------------- what's on disk
def engine_exe():
    if not os.path.isdir(RUNTIME): return None
    names = ("sd-cli.exe", "sd.exe") if sys.platform == "win32" else ("sd-cli", "sd")
    for n in names:
        for d, _, fs in os.walk(RUNTIME):
            if n in fs: return os.path.join(d, n)
    return None

def choice():
    """the chosen image model; if none is chosen yet, the best one already here, else the best one for this PC (catalog.py)"""
    c = _prefs().get("model_AI_Images")
    if c in ("zimage", "sd15", "sdxl", "file"): return c
    if zimage_parts(): return "zimage"
    if os.path.exists(os.path.join(IMAGE, SD15["file"])): return "sd15"
    import catalog; b = catalog.best("AI Images"); return b["key"] if b else "sd15"

def kind():
    """'zimage' or 'sd' (Stable Diffusion 1.5 / XL / a file you added)"""
    return "zimage" if choice() == "zimage" and zimage_parts() else "sd"

def zimage_parts():
    """the three Z-Image files (picture model, text reader, decoder) if they're all here"""
    if not os.path.isdir(ZDIR): return None
    fs = os.listdir(ZDIR)
    dif = [f for f in fs if f.lower().startswith("z_image") and f.endswith(".gguf")]
    llm = [f for f in fs if f.lower().startswith("qwen3") and f.endswith(".gguf")]
    vae = [f for f in fs if f.lower().startswith("ae") and f.endswith((".safetensors", ".sft"))]
    if dif and llm and vae: return dict(diffusion=os.path.join(ZDIR, dif[0]), llm=os.path.join(ZDIR, llm[0]), vae=os.path.join(ZDIR, vae[0]))
    return None

def model_file():
    """the Stable Diffusion model file to paint with: the chosen one, else Stable Diffusion 1.5 if it's there, else any file you added"""
    os.makedirs(IMAGE, exist_ok=True)
    files = sorted(f for f in os.listdir(IMAGE) if f.lower().endswith((".safetensors", ".ckpt", ".gguf")))
    c = choice()
    if c == "sd15" and SD15["file"] in files: return os.path.join(IMAGE, SD15["file"])
    if c == "sdxl":
        xl = [f for f in files if "xl" in f.lower()]
        if xl: return os.path.join(IMAGE, xl[0])
    if c == "file":
        mine = _prefs().get("image_file")
        if mine in files: return os.path.join(IMAGE, mine)
        own = [f for f in files if f != SD15["file"]]
        if own: return os.path.join(IMAGE, own[0])
    return os.path.join(IMAGE, files[0]) if files else None

def _model_args():
    """the engine options that name the model files"""
    z = zimage_parts() if choice() == "zimage" else None
    if z: return ["--diffusion-model", z["diffusion"], "--llm", z["llm"], "--vae", z["vae"]]
    f = model_file(); return ["-m", f] if f else None

def model_label():
    if kind() == "zimage": return "Z-Image Turbo"
    f = model_file(); return os.path.basename(f) if f else ""

def status():
    if _state["state"] in ("downloading", "painting", "error"): return dict(_state)
    have = zimage_parts() if choice() == "zimage" else model_file()
    miss = [x for x, ok in (("the image engine (stable-diffusion.cpp)", engine_exe()), ("Z-Image Turbo" if choice() == "zimage" else "an image model", have)) if not ok]
    if miss: return dict(state="not-installed", detail="Not downloaded yet: " + " and ".join(miss) + ".", progress=0)
    return dict(state="ready", detail=f"Ready: {model_label()}.", progress=0)

def ready(): return bool(engine_exe() and (zimage_parts() if choice() == "zimage" else model_file()))

# ---------------------------------------------------------------- downloading
def _runtime_asset():
    import brain
    rel = brain._get_json("https://api.github.com/repos/leejet/stable-diffusion.cpp/releases/latest")
    if sys.platform == "win32": wants = ("win-vulkan-x64", "win-avx2-x64", "win-cpu-x64")
    elif sys.platform == "darwin": wants = ("Darwin-macOS",)
    else: wants = ("Linux-Ubuntu-24.04-x86_64-vulkan", "Linux-Ubuntu-24.04-x86_64.zip", "Linux")
    for w in wants:
        for a in rel.get("assets", []):
            if w.lower() in a["name"].lower() and a["name"].endswith((".zip", ".tar.gz")): return a["name"], a["browser_download_url"], a.get("size", 0)
    raise RuntimeError("no stable-diffusion.cpp download found for this computer")

def _install_runtime():
    import brain
    name, url, size = _runtime_asset(); os.makedirs(os.path.dirname(RUNTIME), exist_ok=True); arc = os.path.join(os.path.dirname(RUNTIME), name)
    brain._fetch(url, arc, "the image engine", size, report=lambda t, f: _set("downloading", t, f))
    shutil.rmtree(RUNTIME, ignore_errors=True); os.makedirs(RUNTIME)
    if name.endswith(".zip"):
        with zipfile.ZipFile(arc) as z: z.extractall(RUNTIME)
    else:
        with tarfile.open(arc) as t: t.extractall(RUNTIME, filter="data")
    os.remove(arc); _help.clear()
    exe = engine_exe()
    if not exe: raise RuntimeError("the image engine downloaded but sd-cli wasn't in it")
    if sys.platform != "win32": os.chmod(exe, 0o755)

def _install_sd15():
    import brain
    os.makedirs(IMAGE, exist_ok=True)
    brain._fetch(f"https://huggingface.co/{SD15['repo']}/resolve/main/{SD15['file']}", os.path.join(IMAGE, SD15["file"]), SD15["label"], SD15["size"],
                 report=lambda t, f: _set("downloading", t, f))

def _hf_pick(repo, quant):
    """the file in a Hugging Face repo whose name ends in this size (Q4_K, Q8_0...)"""
    import brain
    files = [s["rfilename"] for s in brain._get_json(f"https://huggingface.co/api/models/{repo}").get("siblings", [])]
    ggufs = [f for f in files if f.lower().endswith(".gguf")]
    for q in (quant, quant + "_M", quant + "_S", "Q4_0" if quant.startswith("Q4") else quant):
        hit = [f for f in ggufs if re.search(rf"[-_.]{re.escape(q.lower())}\.gguf$", f.lower())]
        if hit: return hit[0]
    raise RuntimeError(f"{repo} has no {quant} file")

def zimage_download_plan():
    """[(label, repo, file in repo, local name, size GB)] for this PC: the picture model's size suits the card"""
    import catalog
    quant, total = catalog.variant(catalog.entry("AI Images", "zimage"))
    llm_q = "Q8_0" if quant == "Q8_0" else "Q4_K_M"
    return [("Z-Image Turbo", ZIMAGE["repo"], quant, None, total - (4.3 if llm_q == "Q8_0" else 2.5) - 0.33),
            ("its text reader (Qwen3 4B)", ZIMAGE["llm_repo"], llm_q, None, 4.3 if llm_q == "Q8_0" else 2.5),
            ("its picture decoder", ZIMAGE["vae_repo"], None, "ae.safetensors", 0.33)]

def _install_zimage():
    import brain
    os.makedirs(ZDIR, exist_ok=True)
    for label, repo, quant, local, size in zimage_download_plan():
        f = _hf_pick(repo, quant) if quant else ZIMAGE["vae_file"]
        name = local or os.path.basename(f)
        if repo == ZIMAGE["llm_repo"] and not name.lower().startswith("qwen3"): name = "qwen3-" + name     # found by its name later
        dest = os.path.join(ZDIR, name)
        if os.path.exists(dest): continue
        brain._fetch(f"https://huggingface.co/{repo}/resolve/main/{f}", dest, label, size * 1e9, report=lambda t, fr: _set("downloading", t, fr))

def download_size(key=None):
    key = key or choice()
    if key == "zimage": return sum(p[4] for p in zimage_download_plan()) * 1e9 if not zimage_parts() else 0
    if key == "sd15": return 0 if os.path.exists(os.path.join(IMAGE, SD15["file"])) else SD15["size"]
    return 0

def add_file(path, on_done=None):
    """install an image model file you already have, choose it, and get the engine if it isn't here yet"""
    os.makedirs(IMAGE, exist_ok=True); shutil.copy(path, os.path.join(IMAGE, os.path.basename(path)))
    _prefs().set("model_AI_Images", "file"); _prefs().set("image_file", os.path.basename(path))
    if engine_exe():
        if on_done: on_done(True, f"{os.path.basename(path)} is set up")
        return
    def work():
        try: _install_runtime(); _set(None, ""); on_done and on_done(True, f"{os.path.basename(path)} and the image engine are set up")
        except Exception as e: _set("error", f"Download failed: {e}"); on_done and on_done(False, str(e))
    _set("downloading", "Getting the image engine…", 0.0); threading.Thread(target=work, daemon=True).start()

def download(on_done=None, key=None):
    """the engine (if missing) and a model: `key` ('zimage' / 'sd15'), else the one chosen in Settings"""
    key = key or (choice() if choice() in ("zimage", "sd15") else "sd15")
    def work():
        try:
            import storage
            ok, msg = storage.room("Shared models", download_size(key))
            if not ok: raise RuntimeError(msg)
            if not engine_exe(): _install_runtime()
            if key == "zimage": _install_zimage()
            elif not os.path.exists(os.path.join(IMAGE, SD15["file"])): _install_sd15()
            _set(None, ""); on_done and on_done(True, f"the image engine and {ZIMAGE['label'] if key == 'zimage' else SD15['label']} are downloaded")
        except Exception as e:
            _set("error", f"Download failed: {e}"); on_done and on_done(False, str(e))
    _set("downloading", "Starting the download…", 0.0); threading.Thread(target=work, name="download image engine", daemon=True).start()

# ---------------------------------------------------------------- the memory guard
def _help_text():
    """the engine's option names (they changed between versions), read once from its own help"""
    if "text" not in _help:
        try: _help["text"] = subprocess.run([engine_exe(), "--help"], capture_output=True, text=True, timeout=30,
                                            creationflags=0x08000000 if sys.platform == "win32" else 0).stdout
        except Exception: _help["text"] = ""
    return _help["text"]

def _flags():
    h = _help_text()
    return dict(width="-W" if re.search(r"(^|\s)-W[,\s]", h) or not h else "--width", height="-H" if re.search(r"(^|\s)-H[,\s]", h) or not h else "--height",
                negative="-n" if re.search(r"(^|\s)-n[,\s]", h) or not h else "--negative-prompt", mode="--mode" in h and "img2img" in h,
                mask="--mask" in h)

MODES = ["Fast", "Balanced", "Safe"]
def _mode_flags(mode, low_ram=False):
    """Fast: all on the card. Balanced: the picture is decoded in tiles (and Z-Image keeps its weights in PC memory, which costs no speed).
    Safe: the weights wait in PC memory and the text reader and decoder run on the processor. low_ram: weights are read from the
    disk as needed, so PC memory isn't used up either"""
    h = _help_text(); out = []
    want = {"Fast": [], "Balanced": ["--vae-tiling"] + (["--offload-to-cpu"] if kind() == "zimage" else []),
            "Safe": ["--vae-tiling", "--offload-to-cpu", "--clip-on-cpu", "--vae-on-cpu"]}[mode]
    for flag in want:
        if flag in h: out.append(flag)
    if mode == "Safe" and "--clip-on-cpu" not in h and "--backend" in h: out += ["--backend", "te=cpu,vae=cpu"]   # newer engines' way to say it
    if low_ram and "--params-backend" in h:
        out = [f for f in out if f != "--offload-to-cpu"] + ["--params-backend", "disk"]
    if "--threads" in h: import hardware; out += ["-t", str(hardware.threads_for_ai())]
    return out

def need_gb(w, h):
    """(card GB to hold it all, card GB at the least, PC memory GB) for the chosen model at w x h"""
    scale = max(1.0, (w * h) / (1024 * 1024 if kind() == "zimage" else 512 * 512))
    if kind() == "zimage":
        z = zimage_parts(); files = sum(os.path.getsize(p) for p in z.values()) / 2 ** 30 if z else 8.0
        return files + 1.5 * scale, 2.5 + 0.8 * scale, files + 2.0
    f = model_file(); size = os.path.getsize(f) / 2 ** 30 if f and os.path.exists(f) else 2.1
    return size + 1.2 * scale, 1.2 + 0.4 * scale, size + 1.5

def plan_mode(w, h, wanted=None):
    """the speed mode to start with, given what is free right now (compress before it runs out); -> (mode, low_ram, why)"""
    import hardware
    wanted = wanted or _prefs().get("speed_image") or "Balanced"; pc = hardware.pc()
    if not pc.get("vram_gb"): return "Safe", False, "no graphics card for AI: painting on the processor"
    free = hardware.free(); full, least, ram = need_gb(w, h); why = ""
    mode = wanted
    if mode == "Fast" and free["vram_gb"] < full + 0.5: mode, why = "Balanced", f"only {free['vram_gb']:.1f} GB free on the card"
    if mode == "Balanced" and free["vram_gb"] < least + 1.5: mode, why = "Safe", f"only {free['vram_gb']:.1f} GB free on the card"
    low_ram = free["ram_gb"] < ram + 1.0
    if low_ram: why = (why + "; " if why else "") + f"only {free['ram_gb']:.1f} GB PC memory free"
    return mode, low_ram, why

# ---------------------------------------------------------------- painting
def image_model_bits(name):
    """(text added to the prompt, the add-on folder) for one of your image models; ("", None) if it has no trained add-on yet"""
    if not name or kind() == "zimage": return "", None                     # your models are trained for Stable Diffusion 1.5
    import image_models as IM
    lora = os.path.join(IM.folder(name), "lora")
    files = [f for f in os.listdir(lora) if f.endswith((".safetensors", ".gguf"))] if os.path.isdir(lora) else []
    trig = IM.info(name).get("trigger", "")
    if not files: return (f", {trig}" if trig else ""), None
    stem = os.path.splitext(files[0])[0]; strength = {"Gentle": 0.6, "Normal": 0.85, "Strong": 1.0}.get(IM.info(name).get("strength", "Normal"), 0.85)
    return f", {trig} <lora:{stem}:{strength}>", lora

def _smaller(w, h):
    k = 0.75; floor = 512 if kind() == "zimage" else 384
    return max(floor, int(w * k) // 64 * 64), max(floor, int(h * k) // 64 * 64)

def paint(prompt, n=1, size="Square", steps=20, cfg=7.0, seed=None, negative=NEGATIVE, image_model="", init_image=None,
          strength=0.6, mask=None, finish=None, hint=None, on_progress=None, stop=None):
    """paint n pictures; each is saved into Images as soon as it's done. -> list of saved paths
    size: 'Square' / 'Tall' / 'Wide' or (w, h).  mask: a black-and-white picture, white = repaint (inpainting, with init_image).
    finish(picture) -> picture: a last step before saving (inpainting puts the new part back into the full-size original)"""
    from PIL import Image
    import prefs, brain, jobs
    exe, margs = engine_exe(), _model_args()
    if not exe or not margs: raise RuntimeError("the image engine isn't downloaded yet (Settings > AI Models > AI Images)")
    brain.free_card()                                                        # the whole graphics card for the picture
    z = kind() == "zimage"; w, h = pixels(size); extra, lora_dir = image_model_bits(image_model); f = _flags()
    if z: steps, cfg = ZSTEPS.get(steps, 8), 1.0
    base_seed = random.randint(0, 2 ** 31 - 2) if seed is None else int(seed); out = []; last.update(seed=base_seed, note="")
    tmp = os.path.join(ROOT, "image-work"); os.makedirs(tmp, exist_ok=True)
    if mask is not None and not f["mask"]: raise RuntimeError("this image engine version can't do inpainting (no --mask option); download the engine again")
    mode, low_ram, why = plan_mode(w, h)
    if why and mode != (_prefs().get("speed_image") or "Balanced"): jobs.note(f"SAVING MEMORY — painting in {mode} mode ({why})")
    with _lock:
        try:
            for i in range(n):
                if stop is not None and stop.is_set(): break
                while True:                                                      # retries: Safe, then smaller, if it runs out of memory
                    dest = os.path.join(tmp, f"out-{i}.png")
                    if os.path.exists(dest): os.remove(dest)
                    cmd = [exe, *margs, "-p", prompt + extra, f["width"], str(w), f["height"], str(h), "--steps", str(steps), "--cfg-scale", str(cfg),
                           "-s", str(base_seed + i), "-o", dest]
                    if not z: cmd += [f["negative"], negative, "--sampling-method", "euler_a"]
                    if lora_dir: cmd += ["--lora-model-dir", lora_dir]
                    cmd += _mode_flags(mode, low_ram)
                    if init_image is not None:
                        init_path = os.path.join(tmp, "start.png"); init_image.convert("RGB").resize((w, h), Image.LANCZOS).save(init_path)
                        cmd += (["--mode", "img2img"] if f["mode"] else []) + ["-i", init_path, "--strength", str(strength)]
                        if mask is not None:
                            mask_path = os.path.join(tmp, "mask.png"); mask.convert("L").resize((w, h), Image.LANCZOS).save(mask_path); cmd += ["--mask", mask_path]
                    code, tail = _run(cmd, i, n, steps, on_progress, stop)
                    if stop is not None and stop.is_set(): break
                    if code == 0 and os.path.exists(dest): break
                    if not OOM.search(tail): raise RuntimeError("the image engine stopped with an error (details in logs/image_engine.log)")
                    if mode != "Safe":
                        mode = "Safe"; jobs.note("OUT OF GRAPHICS MEMORY — painting it again in Safe mode (slower, but it fits)")
                    elif (w, h) != _smaller(w, h):
                        w, h = _smaller(w, h); last["note"] = f"painted at {w} x {h} to fit"
                        jobs.note(f"STILL OUT OF MEMORY — painting it smaller ({w} x {h}) so it fits")
                    else: raise RuntimeError("the graphics card ran out of memory even in Safe mode at the smallest size. Close other programs and try again")
                if stop is not None and stop.is_set(): break
                pic = Image.open(dest).copy()
                if finish: pic = finish(pic)
                meta = dict(words=prompt, leave_out="" if z else negative, seed=str(base_seed + i), steps=str(steps), follow=str(cfg),
                            model=image_model or model_label(), size=f"{w}x{h}", made_by="Instant Easel Pro")
                out.append(prefs.new_image(pic, hint or prompt, meta=meta))
                if on_progress: on_progress((i + 1) / n, f"Saved {i + 1} of {n} to Images")
        finally:
            _set(None, "")
    return out

def _run(cmd, i, n, steps, on_progress, stop):
    """run the engine once, with progress; -> (exit code, the end of what it printed)"""
    _set("painting", f"Painting {i + 1} of {n}…", i / n)
    log = open(paths.log_file("image_engine.log"), "a", encoding="utf-8", errors="replace")
    log.write(f"\n=== {datetime.datetime.now().isoformat(timespec='seconds')} {' '.join(cmd)}\n"); log.flush()
    p = _proc["p"] = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
                                       cwd=os.path.dirname(cmd[0]), creationflags=0x08000000 if sys.platform == "win32" else 0)
    buf = ""; tail = ""
    try:
        while True:
            ch = p.stdout.read(1)
            if not ch: break
            log.write(ch); tail = (tail + ch)[-6000:]
            if ch in "\r\n":
                m = re.search(r"(\d+)/(\d+)", buf)
                if m and int(m.group(2)) == steps:
                    frac = (i + int(m.group(1)) / steps) / n; _set("painting", f"Painting {i + 1} of {n}: step {m.group(1)} of {steps}", frac)
                    if on_progress: on_progress(frac, _state["detail"])
                buf = ""
            else: buf += ch
            if stop is not None and stop.is_set(): p.terminate(); break
        p.wait()
    finally:
        log.close(); _proc["p"] = None
    return p.returncode, tail

def stop_now():
    p = _proc["p"]
    if p is not None and p.poll() is None:
        try: p.terminate()
        except Exception: pass
