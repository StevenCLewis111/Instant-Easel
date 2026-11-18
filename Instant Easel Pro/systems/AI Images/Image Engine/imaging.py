"""
imaging.py: Instant Easel Pro's image engine. Paints pictures from words (and repaints pictures) on this PC.

    The engine      stable-diffusion.cpp (sd-cli), downloaded once: the Vulkan build on Windows, which runs on Intel Arc, AMD and
                    NVIDIA cards. Like the text engine it needs no Python add-ons.
    The model       chosen in Settings > AI Models > AI Images:
                      Stable Diffusion 1.5 (2.1 GB, downloaded for you) - right for a 6 GB card
                      Stable Diffusion XL / a model file you add (.safetensors) - put in my-models/image/
    Your models     an image model from AI Training > Image Learning (Cartoon, Fashion...) switches on its trained add-on
                    (lora/<name>.safetensors) and its trigger word.
    Every picture   is saved straight into your Images folder (Settings > General > Your work folder).

    import imaging
    imaging.status()                     -> dict(state, detail, progress)
    imaging.download(on_done)            engine + Stable Diffusion 1.5 (background)
    imaging.paint("a red shoe", n=1, on_progress=fn) -> [paths of the saved pictures]
"""
import os, sys, re, json, shutil, threading, subprocess, zipfile, tarfile, random, time, datetime
import paths

SD15 = dict(label="Stable Diffusion 1.5", repo="Comfy-Org/stable-diffusion-v1-5-archive", file="v1-5-pruned-emaonly-fp16.safetensors", size=2.13e9)
ROOT = paths.ai("my-models"); RUNTIME = os.path.join(ROOT, "runtime", "stable-diffusion.cpp"); IMAGE = os.path.join(ROOT, "image")
NEGATIVE = "blurry, low quality, deformed, extra fingers, watermark, text, signature"
SIZES = {"Square 512 x 512": (512, 512), "Tall 512 x 768": (512, 768), "Wide 768 x 512": (768, 512)}

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

def model_file():
    """the image model file to paint with: the chosen one, else Stable Diffusion 1.5 if it's there, else any file you added"""
    os.makedirs(IMAGE, exist_ok=True)
    files = sorted(f for f in os.listdir(IMAGE) if f.lower().endswith((".safetensors", ".ckpt", ".gguf")))
    choice = _prefs().get("model_AI_Images")
    if choice == "sd15" and SD15["file"] in files: return os.path.join(IMAGE, SD15["file"])
    if choice == "sdxl":
        xl = [f for f in files if "xl" in f.lower()]
        if xl: return os.path.join(IMAGE, xl[0])
    if choice == "file":
        mine = _prefs().get("image_file")
        if mine in files: return os.path.join(IMAGE, mine)
        own = [f for f in files if f != SD15["file"]]
        if own: return os.path.join(IMAGE, own[0])
    return os.path.join(IMAGE, files[0]) if files else None

def status():
    if _state["state"] in ("downloading", "painting", "error"): return dict(_state)
    miss = [x for x, ok in (("the image engine (stable-diffusion.cpp)", engine_exe()), ("an image model", model_file())) if not ok]
    if miss: return dict(state="not-installed", detail="Not downloaded yet: " + " and ".join(miss) + ".", progress=0)
    return dict(state="ready", detail=f"Ready: {os.path.basename(model_file())}.", progress=0)

def ready(): return bool(engine_exe() and model_file())

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
    os.remove(arc)
    exe = engine_exe()
    if not exe: raise RuntimeError("the image engine downloaded but sd-cli wasn't in it")
    if sys.platform != "win32": os.chmod(exe, 0o755)

def _install_sd15():
    import brain
    os.makedirs(IMAGE, exist_ok=True)
    brain._fetch(f"https://huggingface.co/{SD15['repo']}/resolve/main/{SD15['file']}", os.path.join(IMAGE, SD15["file"]), SD15["label"], SD15["size"],
                 report=lambda t, f: _set("downloading", t, f))

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

def download(on_done=None):
    def work():
        try:
            import storage
            ok, msg = storage.room("Shared models", 0 if model_file() else SD15["size"])
            if not ok: raise RuntimeError(msg)
            if not engine_exe(): _install_runtime()
            if not os.path.exists(os.path.join(IMAGE, SD15["file"])) and _prefs().get("model_AI_Images") in ("sd15", None): _install_sd15()
            _set(None, ""); on_done and on_done(True, "the image engine and model are downloaded")
        except Exception as e:
            _set("error", f"Download failed: {e}"); on_done and on_done(False, str(e))
    _set("downloading", "Starting the download…", 0.0); threading.Thread(target=work, name="download image engine", daemon=True).start()

# ---------------------------------------------------------------- painting
def _flags():
    """the engine's option names (they changed between versions), read once from its own help"""
    if "text" not in _help:
        try: _help["text"] = subprocess.run([engine_exe(), "--help"], capture_output=True, text=True, timeout=30,
                                            creationflags=0x08000000 if sys.platform == "win32" else 0).stdout
        except Exception: _help["text"] = ""
    h = _help["text"]
    mode = _prefs().get("speed_image") or "Balanced"; low = []
    for flag, modes in (("--vae-tiling", ("Balanced", "Safe")), ("--clip-on-cpu", ("Safe",)), ("--vae-on-cpu", ("Safe",)), ("--offload-to-cpu", ("Safe",))):
        if mode in modes and flag in h: low.append(flag)                       # Safe: parts of the work on the processor, so it can't run out of card memory
    return dict(low=low, width="-W" if re.search(r"(^|\s)-W[,\s]", h) or not h else "--width", height="-H" if re.search(r"(^|\s)-H[,\s]", h) or not h else "--height",
                negative="-n" if re.search(r"(^|\s)-n[,\s]", h) or not h else "--negative-prompt", mode="--mode" in h and "img2img" in h)

def image_model_bits(name):
    """(text added to the prompt, the add-on folder) for one of your image models; ("", None) if it has no trained add-on yet"""
    if not name: return "", None
    import image_models as IM
    lora = os.path.join(IM.folder(name), "lora")
    files = [f for f in os.listdir(lora) if f.endswith((".safetensors", ".gguf"))] if os.path.isdir(lora) else []
    trig = IM.info(name).get("trigger", "")
    if not files: return (f", {trig}" if trig else ""), None
    stem = os.path.splitext(files[0])[0]; strength = {"Gentle": 0.6, "Normal": 0.85, "Strong": 1.0}.get(IM.info(name).get("strength", "Normal"), 0.85)
    return f", {trig} <lora:{stem}:{strength}>", lora

def paint(prompt, n=1, size="Square 512 x 512", steps=20, cfg=7.0, seed=None, negative=NEGATIVE, image_model="", init_image=None,
          strength=0.6, on_progress=None, stop=None):
    """paint n pictures; each is saved into Images as soon as it's done. -> list of saved paths"""
    from PIL import Image
    import prefs
    exe, model = engine_exe(), model_file()
    if not exe or not model: raise RuntimeError("the image engine isn't downloaded yet (Settings > AI Models > AI Images)")
    w, h = SIZES.get(size, (512, 512)); extra, lora_dir = image_model_bits(image_model); f = _flags()
    base_seed = random.randint(0, 2 ** 31 - 2) if seed is None else int(seed); out = []
    tmp = os.path.join(ROOT, "image-work"); os.makedirs(tmp, exist_ok=True)
    init_path = None
    if init_image is not None:
        init_path = os.path.join(tmp, "start.png"); im = init_image.convert("RGB"); im.thumbnail((w, h)); im = im.resize((w, h)); im.save(init_path)
    with _lock:
        try:
            for i in range(n):
                if stop is not None and stop.is_set(): break
                dest = os.path.join(tmp, f"out-{i}.png")
                if os.path.exists(dest): os.remove(dest)
                cmd = [exe, "-m", model, "-p", prompt + extra, f["negative"], negative, f["width"], str(w), f["height"], str(h),
                       "--steps", str(steps), "--cfg-scale", str(cfg), "-s", str(base_seed + i), "--sampling-method", "euler_a", "-o", dest]
                if lora_dir: cmd += ["--lora-model-dir", lora_dir]
                cmd += f["low"]
                if init_path:
                    cmd += (["--mode", "img2img"] if f["mode"] else []) + ["-i", init_path, "--strength", str(strength)]
                _set("painting", f"Painting {i + 1} of {n}…", i / n)
                log = open(paths.log_file("image_engine.log"), "a", encoding="utf-8", errors="replace")
                log.write(f"\n=== {datetime.datetime.now().isoformat(timespec='seconds')} {' '.join(cmd)}\n"); log.flush()
                p = _proc["p"] = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
                                                   cwd=os.path.dirname(exe), creationflags=0x08000000 if sys.platform == "win32" else 0)
                buf = ""
                while True:
                    ch = p.stdout.read(1)
                    if not ch: break
                    log.write(ch)
                    if ch in "\r\n":
                        m = re.search(r"(\d+)/(\d+)", buf)
                        if m and int(m.group(2)) == steps:
                            frac = (i + int(m.group(1)) / steps) / n; _set("painting", f"Painting {i + 1} of {n}: step {m.group(1)} of {steps}", frac)
                            if on_progress: on_progress(frac, _state["detail"])
                        buf = ""
                    else: buf += ch
                    if stop is not None and stop.is_set(): p.terminate(); break
                p.wait(); log.close(); _proc["p"] = None
                if stop is not None and stop.is_set(): break
                if p.returncode != 0 or not os.path.exists(dest):
                    raise RuntimeError("the image engine stopped with an error (details in logs/image_engine.log)")
                out.append(prefs.new_image(Image.open(dest).copy(), prompt))
                if on_progress: on_progress((i + 1) / n, f"Saved {i + 1} of {n} to Images")
        finally:
            _set(None, "")
    return out

def stop_now():
    p = _proc["p"]
    if p is not None and p.poll() is None:
        try: p.terminate()
        except Exception: pass
