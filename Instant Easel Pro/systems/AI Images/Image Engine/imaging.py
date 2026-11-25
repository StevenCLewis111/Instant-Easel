"""
imaging.py: Instant Easel Pro's image engine. Paints, edits, guides and upscales pictures on this PC.

    The engine      stable-diffusion.cpp (sd-cli), downloaded once: the Vulkan build on Windows (Intel Arc, AMD, NVIDIA).
    Picture models  (my-models/image/, chosen in Settings > AI Models; catalog.py says which fit this PC)
        Z-Image Turbo       the best quality for a home PC: picture model + Qwen3 4B text reader + FLUX decoder. 1024 px, ~8 steps.
        FLUX.2 Klein 4B     the editor: changes a picture from words, and uses up to 4 reference pictures (Prompt to Edit, Multi-Image
                            Fusion, Consistent Character, Image Prompting, and your own style models). Also paints, in 4 steps.
        Stable Diffusion 1.5 small and quick; the guides (pose, outline, depth, scribble) and LoRA add-ons work with it.
        Stable Diffusion XL / your own model file
    Add-ons         (my-models/image/addons/, downloaded when a page first needs them)
        upscalers           Real-ESRGAN x4 (photos) and x4 anime (art): bigger, sharper pictures
        guides              ControlNet 1.1 for SD 1.5: pose, outline (edges), depth, scribble
    Every picture   is saved straight into your Images folder, with its words, seed and settings inside the PNG.

Robust: the text model leaves the graphics card first; free memory is checked and the speed mode stepped down before running out
(Fast -> Balanced -> Safe); out-of-memory runs are repeated in Safe, then smaller; an engine that stops responding is stopped after
a few minutes (Settings > AI Images) instead of hanging the line; there must be room on the disk before painting starts; several
pictures are painted in ONE engine run (the model loads once), and an upscale happens in that same run.

    import imaging
    imaging.paint("a red shoe", n=2, size="Square 1:1", on_progress=fn)              -> [saved paths]
    imaging.paint("make it night", model="klein", refs=[picture])                     (an edit)
    imaging.paint("a dancer", model="sd15", control=dict(image=pose, guide="pose"))   (guided)
    imaging.upscale(path, factor=2)                                                   -> saved path
"""
import os, sys, re, json, shutil, threading, subprocess, zipfile, tarfile, random, time, datetime, glob
import paths

ROOT = paths.ai("my-models"); RUNTIME = os.path.join(ROOT, "runtime", "stable-diffusion.cpp"); IMAGE = os.path.join(ROOT, "image")
ZDIR = os.path.join(IMAGE, "zimage"); KDIR = os.path.join(IMAGE, "klein"); ADDONS = os.path.join(IMAGE, "addons")
SD15 = dict(label="Stable Diffusion 1.5", repo="Comfy-Org/stable-diffusion-v1-5-archive", file="v1-5-pruned-emaonly-fp16.safetensors", size=2.13e9)
ZIMAGE = dict(label="Z-Image Turbo", repo="leejet/Z-Image-Turbo-GGUF", llm_repo="unsloth/Qwen3-4B-Instruct-2507-GGUF",
              vae_repo="Comfy-Org/z_image_turbo", vae_file="split_files/vae/ae.safetensors")
KLEIN = dict(label="FLUX.2 Klein 4B", repos=["leejet/FLUX.2-klein-4B-GGUF", "unsloth/FLUX.2-klein-4B-GGUF"], llm_repo="unsloth/Qwen3-4B-GGUF",
             vae_repo="Comfy-Org/flux2-dev", vae_file="split_files/vae/flux2-vae.safetensors")
# how each kind of model is run (research: Z-Image Turbo ~8 steps at CFG 1, no negative words; Klein 4 steps, euler, CFG 1)
MODELS = {
    "zimage": dict(label="Z-Image Turbo", dit=True, area=1024, steps={12: 6, 20: 8, 30: 10}, cfg=1.0, sampler=None, refs=False),
    "klein": dict(label="FLUX.2 Klein 4B", dit=True, area=1024, steps={12: 4, 20: 4, 30: 6}, cfg=1.0, sampler="euler", refs=True),
    "sd15": dict(label="Stable Diffusion 1.5", dit=False, area=512, steps=None, cfg=None, sampler="dpm++2m", scheduler="karras", refs=False),
    "sdxl": dict(label="Stable Diffusion XL", dit=False, area=1024, steps=None, cfg=None, sampler="dpm++2m", scheduler="karras", refs=False),
}
ADDON_FILES = {
    "upscale_photo": dict(label="the photo upscaler (Real-ESRGAN x4)", file="RealESRGAN_x4plus.pth", size=0.067,
                          url="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"),
    "upscale_art": dict(label="the art upscaler (Real-ESRGAN x4 anime)", file="RealESRGAN_x4plus_anime_6B.pth", size=0.018,
                        url="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth"),
    "pose": dict(label="the pose guide", file="control_v11p_sd15_openpose_fp16.safetensors", size=0.72, type="openpose"),
    "outline": dict(label="the outline guide", file="control_v11p_sd15_canny_fp16.safetensors", size=0.72, type="canny"),
    "depth": dict(label="the depth guide", file="control_v11f1p_sd15_depth_fp16.safetensors", size=0.72, type="depth"),
    "scribble": dict(label="the scribble guide", file="control_v11p_sd15_scribble_fp16.safetensors", size=0.72, type="scribble"),
}
GUIDE_REPO = "comfyanonymous/ControlNet-v1-1_fp16_safetensors"
NEGATIVE = ("blurry, low quality, worst quality, jpeg artifacts, deformed, distorted, disfigured, misshapen, bad anatomy, extra fingers, "
            "extra limbs, cropped, out of frame, duplicate, ugly, watermark, signature, username")
SIZES = ["Square 1:1", "Portrait 3:4", "Tall 2:3", "Phone 9:16", "Landscape 4:3", "Wide 3:2", "Cinema 16:9"]
OLD_SIZES = {"Square": "Square 1:1", "Tall": "Tall 2:3", "Wide": "Wide 3:2"}
GUIDANCE = {"Loosely": 5.0, "Normal": 7.0, "Closely": 9.5}              # how closely the picture follows the words (SD's cfg scale)
ZSTEPS = {12: 6, 20: 8, 30: 10}
last = dict(seed=None, note="", model="")                               # the last paint(): its seed, any note (painted smaller...), model
LORA_MISFIT = re.compile(r"LoRA '([^']+)' has no matching model weights", re.I)
OOM = re.compile(r"out of (device |host )?memory|ErrorOutOfDeviceMemory|OutOfDeviceMemory|DeviceLost|failed to allocate|"
                 r"allocation .{0,40}failed|bad_alloc|VK_ERROR_OUT_OF", re.I)
MODES = ["Fast", "Balanced", "Safe"]

_state = dict(state=None, detail="", progress=0.0); _proc = dict(p=None, stalled=False); _lock = threading.Lock(); _help = {}

def _set(state, detail="", progress=None):
    _state.update(state=state, detail=detail)
    if progress is not None: _state["progress"] = progress

def _prefs():
    import prefs; return prefs
def _pref(key, default):
    v = _prefs().get(key); return default if v is None else v

# ---------------------------------------------------------------- what's on disk
def engine_exe():
    if not os.path.isdir(RUNTIME): return None
    names = ("sd-cli.exe", "sd.exe") if sys.platform == "win32" else ("sd-cli", "sd")
    for n in names:
        for d, _, fs in os.walk(RUNTIME):
            if n in fs: return os.path.join(d, n)
    return None

def choice():
    """the chosen picture model; if none is chosen yet, the best one already here, else the best one for this PC (catalog.py)"""
    c = _prefs().get("model_AI_Images")
    if c in ("zimage", "klein", "sd15", "sdxl", "file"): return c
    if zimage_parts(): return "zimage"
    try:                                                                     # the best for this PC, even if a smaller one is already here
        import catalog; b = catalog.best("AI Images")                        # (Stable Diffusion 1.5 stands in until it's downloaded)
        if b: return b["key"]
    except Exception: pass
    return "sd15"

def _quant_in(f, q): return bool(re.search(rf"[-_.]{re.escape(q.lower())}(_[ms])?\.gguf$", f.lower()))

def _prefer(hits, quants):
    """of several sizes of one part, the first wanted size that's here (else the first file)"""
    for q in quants or ():
        got = [h for h in hits if _quant_in(h, q)]
        if got: return got[0]
    return hits[0]

def _parts(folder, want, prefer=None):
    """{part: path} when every part is there (want: part -> (name start, endings)), else None. prefer: part -> [sizes, best first]
    (Download Everything keeps every size side by side; this picks the one that suits this PC)"""
    if not os.path.isdir(folder): return None
    fs = sorted(os.listdir(folder)); out = {}
    for part, (start, ends) in want.items():
        hit = [f for f in fs if f.lower().startswith(start) and f.lower().endswith(ends)]
        if not hit: return None
        out[part] = os.path.join(folder, _prefer(hit, (prefer or {}).get(part)))
    return out

def _size_order(key):
    """this model's sizes for this PC: the suited one, then smaller, then bigger"""
    try:
        import catalog
        e = catalog.entry("AI Images", key) or catalog.entry("Image edits", key)
        order = [q for _, q, _ in e.get("variants", [])]; want = catalog.variant(e)[0]
        i = order.index(want) if want in order else 0
        return order[i:] + order[:i][::-1]
    except Exception: return []

def _prefs_for(key):
    order = _size_order(key); llm = ["Q8_0", "Q4_K_M"] if order[:1] == ["Q8_0"] else ["Q4_K_M", "Q8_0"]
    return {"diffusion": order, "llm": llm}

def zimage_parts(): return _parts(ZDIR, {"diffusion": ("z_image", (".gguf",)), "llm": ("qwen3", (".gguf",)), "vae": ("ae", (".safetensors", ".sft"))}, _prefs_for("zimage"))
def klein_parts(): return _parts(KDIR, {"diffusion": ("flux2-klein", (".gguf",)), "llm": ("qwen3", (".gguf",)), "vae": ("flux2-vae", (".safetensors",))}, _prefs_for("klein"))

def model_file(key=None):
    """the Stable Diffusion model file for key (sd15 / sdxl / file; the chosen one by default)"""
    os.makedirs(IMAGE, exist_ok=True)
    files = sorted(f for f in os.listdir(IMAGE) if f.lower().endswith((".safetensors", ".ckpt", ".gguf")))
    c = key or choice()
    if c == "sd15": return os.path.join(IMAGE, SD15["file"]) if SD15["file"] in files else None
    if c == "sdxl":
        xl = [f for f in files if "xl" in f.lower()]
        if xl: return os.path.join(IMAGE, xl[0])
    if c == "file":
        mine = _prefs().get("image_file")
        if mine in files: return os.path.join(IMAGE, mine)
        own = [f for f in files if f != SD15["file"]]
        if own: return os.path.join(IMAGE, own[0])
    return os.path.join(IMAGE, files[0]) if files else None

def kind(key=None):
    """the model actually used for key (the chosen one by default): 'zimage', 'klein', 'sd15', 'sdxl' or 'file'.
    A big model that isn't downloaded yet is stood in for by Stable Diffusion 1.5 when that's here"""
    c = key or choice()
    if c == "zimage" and zimage_parts(): return "zimage"
    if c == "klein" and klein_parts(): return "klein"
    if c in ("zimage", "klein"): return "sd15" if model_file("sd15") else c
    return c

def spec(key=None):
    k = kind(key)
    if k in MODELS: return MODELS[k]
    f = model_file(k) or ""; return MODELS["sdxl" if "xl" in os.path.basename(f).lower() else "sd15"]

def have(key):
    """is this model downloaded?"""
    if key == "zimage": return bool(zimage_parts())
    if key == "klein": return bool(klein_parts())
    return bool(model_file(key))

def _model_args(key=None):
    k = kind(key)
    z = zimage_parts() if k == "zimage" else klein_parts() if k == "klein" else None
    if z: return ["--diffusion-model", z["diffusion"], "--llm", z["llm"], "--vae", z["vae"]]
    f = model_file(k); return ["-m", f] if f else None

def model_label(key=None):
    k = kind(key)
    if k in ("zimage", "klein"): return MODELS[k]["label"]
    f = model_file(k); return os.path.basename(f) if f else ""

def addon(key):
    p = os.path.join(ADDONS, ADDON_FILES[key]["file"]); return p if os.path.exists(p) else None

def status():
    if _state["state"] in ("downloading", "painting", "error"): return dict(_state)
    c = choice()
    miss = [x for x, ok in (("the image engine (stable-diffusion.cpp)", engine_exe()), (MODELS.get(c, {}).get("label", "an image model"), have(c))) if not ok]
    if miss: return dict(state="not-installed", detail="Not downloaded yet: " + " and ".join(miss) + ".", progress=0)
    return dict(state="ready", detail=f"Ready: {model_label()}.", progress=0)

def ready(key=None): return bool(engine_exe() and _model_args(key))

# ---------------------------------------------------------------- sizes
def pixels(size, key=None):
    """(w, h) for a size name ('Square 1:1', 'Cinema 16:9', an old 'Square 512 x 512'...) at the model's own size, multiples of 64"""
    if isinstance(size, tuple): return size
    s = str(size or "Square 1:1"); first = s.split()[0] if s.split() else "Square"
    if ":" not in s: s = OLD_SIZES.get(first, "Square 1:1")
    m = re.search(r"(\d+):(\d+)", s); a, b = (int(m[1]), int(m[2])) if m else (1, 1)
    area = spec(key)["area"] ** 2; w = (area * a / b) ** 0.5; h = area / w
    return max(256, round(w / 64) * 64), max(256, round(h / 64) * 64)

def fit_size(im, long_side=None, key=None):
    """a working size with the picture's own shape: the long side long_side (the model's own size by default), multiples of 64"""
    long_side = long_side or (1024 if spec(key)["area"] >= 1024 else 768)
    k = long_side / max(im.size); return max(256, round(im.width * k / 64) * 64), max(256, round(im.height * k / 64) * 64)

# ---------------------------------------------------------------- downloading
def _runtime_asset():
    """the stable-diffusion.cpp download for this computer, from the newest of its recent releases that has it"""
    import brain
    if sys.platform == "win32": wants = ("win-vulkan-x64", "win-avx2-x64", "win-cpu-x64")
    elif sys.platform == "darwin": wants = ("Darwin-macOS",)
    else: wants = ("Linux-Ubuntu-24.04-x86_64-vulkan", "Linux-Ubuntu-24.04-x86_64.zip", "Linux")
    return brain.github_files("leejet/stable-diffusion.cpp", [(wants, True)])[0]

def _install_runtime(report=None):
    import brain
    name, url, size = _runtime_asset(); os.makedirs(os.path.dirname(RUNTIME), exist_ok=True); arc = os.path.join(os.path.dirname(RUNTIME), name)
    brain._fetch(url, arc, "the image engine", size, report=report or (lambda t, f: _set("downloading", t, f)))
    new = RUNTIME + ".new"; shutil.rmtree(new, ignore_errors=True); os.makedirs(new)
    if name.endswith(".zip"):
        with zipfile.ZipFile(arc) as z: z.extractall(new)
    else:
        with tarfile.open(arc) as t: t.extractall(new, filter="data")
    shutil.rmtree(RUNTIME, ignore_errors=True); os.replace(new, RUNTIME); os.remove(arc); _help.clear()   # the old engine stays until the new one is unpacked
    exe = engine_exe()
    if not exe: raise RuntimeError("the image engine downloaded but sd-cli wasn't in it")
    if sys.platform != "win32": os.chmod(exe, 0o755)

def _get(url, dest, label, size_gb, report=None):
    import brain
    if os.path.exists(dest): return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    brain._fetch(url, dest, label, size_gb * 1e9, report=report or (lambda t, f: _set("downloading", t, f)))

def _hf_files(repo):
    import brain
    return [s["rfilename"] for s in brain._get_json(f"https://huggingface.co/api/models/{repo}").get("siblings", [])]

def _hf_pick(repo, quant, files=None):
    """the .gguf file in a Hugging Face repo whose name ends in this size (Q4_K, Q8_0...), trying close sizes too"""
    files = files if files is not None else _hf_files(repo)
    ggufs = [f for f in files if f.lower().endswith(".gguf")]
    for q in (quant, quant + "_M", quant + "_S", "Q4_K_M" if quant.startswith("Q4") else quant, "Q4_0" if quant.startswith("Q4") else quant):
        hit = [f for f in ggufs if re.search(rf"[-_.]{re.escape(q.lower())}\.gguf$", f.lower())]
        if hit: return hit[0]
    raise RuntimeError(f"{repo} has no {quant} file")

def _variant(key, quant=None):
    import catalog
    e = catalog.entry("AI Images", key) or catalog.entry("Image edits", key)
    if quant: return next(((q, g) for _, q, g in e.get("variants", []) if q == quant), (quant, e.get("size", 0)))
    return catalog.variant(e)

def zimage_download_plan(quant=None):
    """[(label, repo, size, local name, GB)] for this PC (the picture model's size suits the card), or for the size given"""
    quant, total = _variant("zimage", quant); llm_q = "Q8_0" if quant == "Q8_0" else "Q4_K_M"
    return [("Z-Image Turbo", ZIMAGE["repo"], quant, None, total - (4.3 if llm_q == "Q8_0" else 2.5) - 0.33),
            ("its text reader (Qwen3 4B)", ZIMAGE["llm_repo"], llm_q, None, 4.3 if llm_q == "Q8_0" else 2.5),
            ("its picture decoder", ZIMAGE["vae_repo"], None, "ae.safetensors", 0.33)]

def klein_download_plan(quant=None):
    quant, total = _variant("klein", quant); llm_q = "Q8_0" if quant == "Q8_0" else "Q4_K_M"
    return [("FLUX.2 Klein 4B", KLEIN["repos"], quant, None, total - (4.3 if llm_q == "Q8_0" else 2.5) - 0.34),
            ("its text reader (Qwen3 4B)", KLEIN["llm_repo"], llm_q, None, 4.3 if llm_q == "Q8_0" else 2.5),
            ("its picture decoder", KLEIN["vae_repo"], None, "flux2-vae.safetensors", 0.34)]

def _install_parts(folder, plan, vae_file, llm_repo, model_prefix, report=None):
    os.makedirs(folder, exist_ok=True)
    for label, repo, quant, local, size in plan:
        if quant:
            repos = repo if isinstance(repo, list) else [repo]; err = None
            for r in repos:                                                    # the first source that has it
                try: f = _hf_pick(r, quant); repo = r; break
                except Exception as e: err = e
            else: raise err
        else: f = vae_file
        name = local or os.path.basename(f)
        if repo == llm_repo: name = name if name.lower().startswith("qwen3") else "qwen3-" + name               # found by its name later
        elif quant and not name.lower().startswith(model_prefix): name = model_prefix + "-" + name
        _get(f"https://huggingface.co/{repo}/resolve/main/{f}", os.path.join(folder, name), label, size, report)

SDXL = dict(label="Stable Diffusion XL", repo="stabilityai/stable-diffusion-xl-base-1.0", file="sd_xl_base_1.0.safetensors", size=6.94)
VDIR = os.path.join(ROOT, "video", "wan22")
WAN = dict(label="Wan 2.2 5B (video)", repo="QuantStack/Wan2.2-TI2V-5B-GGUF", t5_repo="city96/umt5-xxl-encoder-gguf",
           sizes={"Q8_0": 5.4, "Q4_K_M": 3.4}, t5_sizes={"Q8_0": 6.0, "Q4_K_M": 3.7}, vae_size=1.4)

def install_sdxl(report=None):
    _get(f"https://huggingface.co/{SDXL['repo']}/resolve/main/{SDXL['file']}", os.path.join(IMAGE, SDXL["file"]), SDXL["label"], SDXL["size"], report)

def video_parts():
    """{part: path} of the video model's files (Wan 2.2: its video model, text reader and decoder), or None (AI Videos uses them)"""
    q = ["Q8_0", "Q4_K_M"] if _vram() >= 16 else ["Q4_K_M", "Q8_0"]
    return _parts(VDIR, {"diffusion": ("wan2.2", (".gguf",)), "t5": ("umt5", (".gguf",)), "vae": ("wan2.2_vae", (".safetensors",))},
                  {"diffusion": q, "t5": q})

def _vram():
    try: import hardware; return float(hardware.pc().get("vram_gb") or 0)
    except Exception: return 0

def install_video_part(part, quant=None, report=None):
    """one of the video model's files: 'diffusion' / 't5' (in a size) or 'vae'"""
    os.makedirs(VDIR, exist_ok=True)
    if part == "vae":
        if any(f.lower().startswith("wan2.2_vae") for f in os.listdir(VDIR)): return
        try: url = f"https://huggingface.co/{WAN['repo']}/resolve/main/" + next(x for x in _hf_files(WAN["repo"]) if "vae" in x.lower() and x.lower().endswith(".safetensors"))
        except Exception: url = "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan2.2_vae.safetensors"
        return _get(url, os.path.join(VDIR, "wan2.2_vae.safetensors"), "the video decoder", WAN["vae_size"], report)
    repo = WAN["repo"] if part == "diffusion" else WAN["t5_repo"]; f = _hf_pick(repo, quant)
    name = os.path.basename(f); name = name if name.lower().startswith(("wan2.2", "umt5")) else ("wan2.2-" if part == "diffusion" else "umt5-") + name
    size = (WAN["sizes"] if part == "diffusion" else WAN["t5_sizes"]).get(quant, 4)
    _get(f"https://huggingface.co/{repo}/resolve/main/{f}", os.path.join(VDIR, name), f"{WAN['label']} {'' if part == 'diffusion' else 'text reader '}({quant})", size, report)

def have_file(folder, start, quant=None, ends=(".gguf",)):
    """is a file of this part (in this size) in folder?"""
    if not os.path.isdir(folder): return False
    return any(f.lower().startswith(start) and f.lower().endswith(ends) and (not quant or _quant_in(f, quant)) for f in os.listdir(folder))

def download_size(key=None):
    key = key or choice()
    if key == "zimage": return 0 if zimage_parts() else sum(p[4] for p in zimage_download_plan()) * 1e9
    if key == "klein": return 0 if klein_parts() else sum(p[4] for p in klein_download_plan()) * 1e9
    if key == "sd15": return 0 if model_file("sd15") else SD15["size"]
    if key in ADDON_FILES: return 0 if addon(key) else ADDON_FILES[key]["size"] * 1e9
    return 0

def add_file(path, on_done=None):
    """install an image model file you already have, choose it, and get the engine if it isn't here yet"""
    os.makedirs(IMAGE, exist_ok=True); shutil.copy(path, os.path.join(IMAGE, os.path.basename(path)))
    _prefs().set("model_AI_Images", "file"); _prefs().set("image_file", os.path.basename(path))
    download(on_done=lambda ok, m: on_done and on_done(ok, f"{os.path.basename(path)} is set up" if ok else m), key="engine")

_dl_lock = threading.Lock()
def downloading(): return _dl_lock.locked()

def download(on_done=None, key=None):
    """the engine (if missing) and one thing: 'zimage' / 'klein' / 'sd15' / an add-on ('upscale_photo', 'pose'...) / 'engine' alone.
    Default: the picture model chosen in Settings. Runs in the background; on_done(ok, message)"""
    key = key or (choice() if choice() in ("zimage", "klein", "sd15") else "sd15")
    def work():
        if not _dl_lock.acquire(blocking=False):
            on_done and on_done(False, "another image download is still running — it carries on; try again when it's done"); return
        try:
            import storage
            ok, msg = storage.room("Shared models", download_size(key) + (0 if engine_exe() else 1e8))
            if not ok: raise RuntimeError(msg)
            if not engine_exe(): _install_runtime()
            if key == "zimage": _install_parts(ZDIR, zimage_download_plan(), ZIMAGE["vae_file"], ZIMAGE["llm_repo"], "z_image")
            elif key == "klein": _install_parts(KDIR, klein_download_plan(), KLEIN["vae_file"], KLEIN["llm_repo"], "flux2-klein")
            elif key == "sd15": _get(f"https://huggingface.co/{SD15['repo']}/resolve/main/{SD15['file']}", os.path.join(IMAGE, SD15["file"]), SD15["label"], SD15["size"] / 1e9)
            elif key in ADDON_FILES:
                a = ADDON_FILES[key]; url = a.get("url") or f"https://huggingface.co/{GUIDE_REPO}/resolve/main/{a['file']}"
                _get(url, os.path.join(ADDONS, a["file"]), a["label"], a["size"])
            name = {"zimage": ZIMAGE["label"], "klein": KLEIN["label"], "sd15": SD15["label"], "engine": "the image engine"}.get(key) or ADDON_FILES.get(key, {}).get("label", key)
            _set(None, ""); on_done and on_done(True, f"{name} is downloaded")
        except Exception as e:
            _set("error", f"Download failed: {e}"); on_done and on_done(False, str(e))
        finally: _dl_lock.release()
    _set("downloading", "Starting the download…", 0.0); threading.Thread(target=work, name="download image " + key, daemon=True).start()

def ensure_addon(key):
    """download an add-on now, on the calling thread (inside an AI job: a small upscaler is fetched as part of the job)"""
    if addon(key): return addon(key)
    a = ADDON_FILES[key]; url = a.get("url") or f"https://huggingface.co/{GUIDE_REPO}/resolve/main/{a['file']}"
    try: _get(url, os.path.join(ADDONS, a["file"]), a["label"], a["size"])
    finally: _set(None, "")
    return addon(key)

# ---------------------------------------------------------------- the engine's options and the memory guard
def _help_text():
    """the engine's option names (they change between versions), read once from its own help"""
    exe = engine_exe()
    if not exe: return ""
    k = (exe, os.path.getmtime(exe))
    if k not in _help:
        try: _help[k] = subprocess.run([exe, "--help"], capture_output=True, text=True, timeout=30,
                                       creationflags=0x08000000 if sys.platform == "win32" else 0).stdout
        except Exception: _help[k] = ""
    return _help[k]

def has(opt):
    h = _help_text(); return opt in h

def _flags():
    h = _help_text()
    return dict(width="-W" if re.search(r"(^|\s)-W[,\s]", h) or not h else "--width", height="-H" if re.search(r"(^|\s)-H[,\s]", h) or not h else "--height",
                negative="-n" if re.search(r"(^|\s)-n[,\s]", h) or not h else "--negative-prompt", mode="--mode" in h and "img2img" in h,
                mask="--mask" in h or not h, ref="--ref-image" if "--ref-image" in h else "-r")

def _mode_flags(mode, low_ram=False, key=None):
    """Fast: all on the card. Balanced: the picture is decoded in tiles (DiT models keep their weights in PC memory, which costs no
    speed). Safe: weights wait in PC memory and the text reader and decoder run on the processor. low_ram: weights are read from disk"""
    h = _help_text(); out = []; dit = spec(key)["dit"]
    want = {"Fast": [], "Balanced": ["--vae-tiling"] + (["--offload-to-cpu"] if dit else []),
            "Safe": ["--vae-tiling", "--offload-to-cpu", "--clip-on-cpu", "--vae-on-cpu"]}[mode]
    for flag in want:
        if flag in h: out.append(flag)
    if mode == "Safe" and "--clip-on-cpu" not in h and "--backend" in h: out += ["--backend", "te=cpu,vae=cpu"]   # newer engines' way to say it
    if low_ram and "--params-backend" in h: out = [f for f in out if f != "--offload-to-cpu"] + ["--params-backend", "disk"]
    if "--threads" in h:
        import hardware; out += ["-t", str(hardware.threads_for_ai())]
    return out

def need_gb(w, h, key=None):
    """(card GB to hold it all, card GB at the least, PC memory GB) for the model at w x h"""
    k = kind(key); scale = max(1.0, (w * h) / (spec(key)["area"] ** 2))
    if k in ("zimage", "klein"):
        z = zimage_parts() if k == "zimage" else klein_parts(); files = sum(os.path.getsize(p) for p in z.values()) / 2 ** 30 if z else 8.0
        return files + 1.5 * scale, 2.5 + 0.8 * scale, files + 2.0
    f = model_file(k); size = os.path.getsize(f) / 2 ** 30 if f and os.path.exists(f) else 2.1
    return size + 1.2 * scale, 1.2 + 0.4 * scale, size + 1.5

def plan_mode(w, h, wanted=None, key=None):
    """the speed mode to start with, given what is free right now (compress before it runs out); -> (mode, low_ram, why)"""
    import hardware
    wanted = wanted or _pref("speed_image", "Balanced"); pc = hardware.pc()
    if not pc.get("vram_gb"): return "Safe", False, "no graphics card for AI: painting on the processor"
    free = hardware.free(); full, least, ram = need_gb(w, h, key); why = ""; mode = wanted
    if mode == "Fast" and free["vram_gb"] < full + 0.5: mode, why = "Balanced", f"only {free['vram_gb']:.1f} GB free on the card"
    if mode == "Balanced" and free["vram_gb"] < least + 1.5: mode, why = "Safe", f"only {free['vram_gb']:.1f} GB free on the card"
    low_ram = free["ram_gb"] < ram + 1.0
    if low_ram: why = (why + "; " if why else "") + f"only {free['ram_gb']:.1f} GB PC memory free"
    return mode, low_ram, why

def _smaller(w, h, key=None):
    k = 0.75; floor = 512 if spec(key)["area"] >= 1024 else 384
    return max(floor, int(w * k) // 64 * 64), max(floor, int(h * k) // 64 * 64)

def disk_ok(need_mb=300):
    """room for the new pictures in the Images folder and for the engine's working files"""
    for d in (_prefs().save_folder(), ROOT):
        try:
            os.makedirs(d, exist_ok=True)
            if shutil.disk_usage(d).free < need_mb * 1024 * 1024: return False, d
        except OSError: pass
    return True, ""

# ---------------------------------------------------------------- your own image models trained as LoRA add-ons (SD 1.5)
def image_model_bits(name, key=None):
    """(text added to the prompt, the add-on folder) for one of your image models trained as a LoRA; ("", None) if none"""
    if not name or spec(key)["dit"]: return "", None
    try:
        import image_models as IM
        lora = os.path.join(IM.folder(name), "lora")
        files = [f for f in os.listdir(lora) if f.endswith((".safetensors", ".gguf"))] if os.path.isdir(lora) else []
        trig = IM.info(name).get("trigger", "")
        if not files: return "", None
        stem = os.path.splitext(files[0])[0]; strength = {"Gentle": 0.6, "Normal": 0.85, "Strong": 1.0}.get(IM.info(name).get("strength", "Normal"), 0.85)
        return f", {trig} <lora:{stem}:{strength}>", lora
    except Exception: return "", None

# ---------------------------------------------------------------- painting
def build_cmd(prompt, w, h, n, steps, cfg, seed, negative, key, mode, low_ram, work, extra="", lora_dir=None, init_image=None, strength=0.6,
              mask=None, refs=None, control=None, sharper=False, up=None, preview=False, plain=False):
    """the engine command for one run (kept apart so it can be checked without a graphics card)"""
    from PIL import Image
    f = _flags(); sp = spec(key); dit = sp["dit"]; exe = engine_exe()
    dest = os.path.join(work, "out_%03d.png" if "printf-style" in _help_text() else "out.png")
    cmd = [exe, *_model_args(key), "-p", prompt + extra, f["width"], str(w), f["height"], str(h), "--steps", str(steps), "--cfg-scale", str(cfg),
           "-s", str(seed), "-o", dest]
    if n > 1: cmd += ["-b", str(n)]
    if not dit and negative: cmd += [f["negative"], negative]
    if sp["sampler"]: cmd += ["--sampling-method", sp["sampler"] if sp["sampler"] != "dpm++2m" or has("dpm++2m") else "euler_a"]
    if sp.get("scheduler") and has("--scheduler") and has(sp["scheduler"]): cmd += ["--scheduler", sp["scheduler"]]   # (sharper, cleaner shapes than euler_a)
    if lora_dir: cmd += ["--lora-model-dir", lora_dir]
    cmd += _mode_flags(mode, low_ram, key)
    if plain: sharper = preview = False                                         # plain: none of the optional extras (a retry after an odd error)
    if _pref("image_speed_boost", False) and has("--cache-mode") and not plain: cmd += ["--cache-mode", "easycache" if dit else "ucache"]
    if sharper and not dit and init_image is None and has("--hires"): cmd += ["--hires", "--hires-scale", "1.5", "--hires-denoising-strength", "0.45"]
    if init_image is not None:
        init_path = os.path.join(work, "start.png"); init_image.convert("RGB").resize((w, h), Image.LANCZOS).save(init_path)
        cmd += (["--mode", "img2img"] if f["mode"] else []) + ["-i", init_path, "--strength", str(strength)]
        if mask is not None:
            mask_path = os.path.join(work, "mask.png"); mask.convert("L").resize((w, h), Image.LANCZOS).save(mask_path); cmd += ["--mask", mask_path]
    for i, r in enumerate((refs or [])[:4]):
        rp = os.path.join(work, f"ref{i}.png"); r = r.convert("RGB"); r.thumbnail((1024, 1024), Image.LANCZOS); r.save(rp); cmd += [f["ref"], rp]
    if control:
        g = control.get("guide", "outline"); cn = addon(g)
        if not cn: raise RuntimeError(f"{ADDON_FILES[g]['label']} isn't downloaded yet (press its Download button)")
        cp = os.path.join(work, "guide.png"); control["image"].convert("RGB").resize((w, h), Image.LANCZOS).save(cp)
        cmd += ["--control-net", cn, "--control-image", cp, "--control-strength", str(control.get("strength", 0.9))]
        if has("--control-type"): cmd += ["--control-type", ADDON_FILES[g]["type"]]
        if control.get("edges"):
            if has("--image-preprocess"): cmd += ["--image-preprocess", "target=control,canny=true"]
            elif has("--canny"): cmd += ["--canny"]
        if mode == "Safe" and has("--control-net-cpu"): cmd += ["--control-net-cpu"]
    if up: cmd += ["--upscale-model", up]
    prev = None
    if preview and _pref("image_live_preview", True) and has("--preview-path"):
        prev = os.path.join(work, "preview.png"); cmd += ["--preview", "proj", "--preview-path", prev, "--preview-interval", "1"]
    return cmd, prev

def paint(prompt, n=1, size="Square 1:1", steps=20, cfg=7.0, seed=None, negative=NEGATIVE, image_model="", init_image=None,
          strength=0.6, mask=None, finish=None, hint=None, on_progress=None, stop=None, model=None, refs=None, control=None,
          sharper=None, upscale=None, preview=None, lora=None, meta_extra=None):
    """paint n pictures in one engine run; each is saved into Images. -> list of saved paths
    model       'zimage' / 'klein' / 'sd15'... (the one chosen in Settings by default)
    size        a size name ('Square 1:1'...) or (w, h)        init_image + strength: repaint a picture (mask: white = repaint)
    refs        up to 4 reference pictures (FLUX.2 Klein): edit them / take people, things and style from them
    control     dict(image=PIL, guide='pose'|'outline'|'depth'|'scribble', strength=0.9, edges=True) - SD 1.5 guides
    sharper     SD: a second, bigger pass (hires fix)        upscale: '2x' / '4x' (+ ' art'), done in the same run
    preview     fn(path): called with a rough picture of the run so far        finish(picture) -> picture before saving"""
    from PIL import Image
    import prefs, brain, jobs
    key = model or choice(); sp = spec(key); k = kind(key)
    if not engine_exe() or not _model_args(key): raise RuntimeError(f"{MODELS.get(key, {}).get('label', 'the image model')} isn't downloaded yet (Settings > AI Models)")
    ok, where = disk_ok()
    if not ok: raise RuntimeError(f"the disk is nearly full ({where}). Free some space and try again")
    if refs and not sp["refs"]: raise RuntimeError("reference pictures need FLUX.2 Klein (Settings > AI Models > Image edits)")
    if control and k not in ("sd15", "file"): raise RuntimeError("the guides (pose, outline, depth, scribble) work with Stable Diffusion 1.5")
    if mask is not None and not _flags()["mask"]: raise RuntimeError("this image engine version can't do inpainting (no --mask option); download the engine again")
    brain.free_card()                                                         # the whole graphics card for the picture
    w, h = pixels(size, key)
    extra, lora_dir = image_model_bits(image_model, key) if lora is None else lora
    if sp["steps"]: steps = sp["steps"].get(steps, steps if steps <= 12 else 8)
    if sp["cfg"] is not None: cfg = sp["cfg"]
    base_seed = random.randint(0, 2 ** 31 - 2) if seed is None else int(seed); last.update(seed=base_seed, note="", model=model_label(key))
    work = os.path.join(ROOT, "image-work"); shutil.rmtree(work, ignore_errors=True); os.makedirs(work, exist_ok=True)
    mode, low_ram, why = plan_mode(w, h, key=key)
    if why and mode != _pref("speed_image", "Balanced"): jobs.note(f"SAVING MEMORY — painting in {mode} mode ({why})")
    up = None
    if upscale:
        up = addon("upscale_art" if "art" in upscale else "upscale_photo") or addon("upscale_photo") or addon("upscale_art")
        if not up: raise RuntimeError("the upscaler isn't downloaded yet (Settings > AI Images > Add-ons)")
    sharper = sharper if sharper is not None else _pref("image_sharper", True)
    out = []; made = []; plain = False
    with _lock:
        try:
            while True:                                                        # retries: Safe, then smaller, then one at a time
                for p in glob.glob(os.path.join(work, "out*.png")): os.remove(p)
                cmd, prev = build_cmd(prompt, w, h, n, steps, cfg, base_seed, negative, key, mode, low_ram, work, extra, lora_dir, init_image,
                                      strength, mask, refs, control, sharper, up, preview, plain)
                code, tail = _run(cmd, n, steps, on_progress, stop, prev, preview)
                made = sorted(glob.glob(os.path.join(work, "out*.png")))
                if stop is not None and stop.is_set(): break
                if code == 0 and made: break
                if _proc["stalled"]: raise RuntimeError(f"the image engine stopped responding for {_pref('image_stall_minutes', 10)} minutes, so it was stopped "
                                                        "(Settings > AI Images sets how long to wait). Try Safe mode or a smaller size")
                bad = LORA_MISFIT.search(tail or "")
                if bad:                                                           # a template / your own model made for another picture model:
                    stem = os.path.splitext(re.split(r"[\\/]", bad.group(1))[-1])[0]   # painted without it, and said so
                    tag = r"\s*<lora:" + re.escape(stem) + r":[^>]*>"                 # (in the words, or in what the template adds to them)
                    trimmed, t_extra = re.sub(tag, "", prompt, flags=re.I), re.sub(tag, "", extra or "", flags=re.I)
                    if trimmed != prompt or t_extra != (extra or ""):
                        prompt, extra = trimmed, ("" if not t_extra.strip(" ,") else t_extra)
                        if "<lora:" not in (prompt + extra).lower(): lora_dir = None
                        last["note"] = f"the {stem} template doesn't fit {model_label(key)}: painted without it"
                        jobs.note(f"THE {stem.upper()} TEMPLATE IS MADE FOR ANOTHER MODEL — painting without it"); continue
                if not OOM.search(tail):
                    if not plain:                                                 # an extra this engine/model doesn't take (preview, speed boost,
                        plain = True; continue                                    # sharper pass): once more without any of them
                    raise RuntimeError("the image engine stopped with an error (details in logs/image_engine.log)")
                if mode != "Safe":
                    mode = "Safe"; jobs.note("OUT OF GRAPHICS MEMORY — painting it again in Safe mode (slower, but it fits)")
                elif (w, h) != _smaller(w, h, key):
                    w, h = _smaller(w, h, key); last["note"] = f"painted at {w} x {h} to fit"
                    jobs.note(f"STILL OUT OF MEMORY — painting it smaller ({w} x {h}) so it fits")
                elif n > 1:
                    n = 1; last["note"] = "painted one at a time to fit"; jobs.note("STILL OUT OF MEMORY — painting one picture instead of several")
                else: raise RuntimeError("the graphics card ran out of memory even in Safe mode at the smallest size. Close other programs and try again")
            if not (stop is not None and stop.is_set()):
                for i, path in enumerate(made[:n]):
                    pic = Image.open(path).convert("RGB")
                    if up and upscale.startswith("2x"): pic = pic.resize((pic.width // 2, pic.height // 2), Image.LANCZOS)     # the x4 result kept at 2x
                    if finish: pic = finish(pic)
                    meta = dict(words=prompt, leave_out="" if sp["dit"] else negative, seed=str(base_seed + i), steps=str(steps), follow=str(cfg),
                                model=image_model or model_label(key), size=f"{pic.width}x{pic.height}", made_by="Instant Easel Pro", **(meta_extra or {}))
                    out.append(prefs.new_image(pic, hint or prompt, meta=meta))
                    if on_progress: on_progress((i + 1) / max(1, n), f"Saved {i + 1} of {n} to Images")
        finally:
            _set(None, "")
    return out

def upscale(path, factor=2, art=False, on_progress=None, stop=None):
    """a bigger, sharper copy of a picture (Real-ESRGAN x4; factor 2 is the x4 result scaled back to twice the size). -> saved path"""
    from PIL import Image
    import prefs, brain
    up = addon("upscale_art" if art else "upscale_photo") or addon("upscale_photo") or addon("upscale_art")
    exe = engine_exe()
    if not exe: raise RuntimeError("the image engine isn't downloaded yet")
    if not up: raise RuntimeError("the upscaler isn't downloaded yet (Settings > AI Images > Add-ons)")
    ok, where = disk_ok(500)
    if not ok: raise RuntimeError(f"the disk is nearly full ({where})")
    brain.free_card()
    work = os.path.join(ROOT, "image-work"); shutil.rmtree(work, ignore_errors=True); os.makedirs(work)
    src = Image.open(path).convert("RGB"); sp = os.path.join(work, "start.png"); src.save(sp); dest = os.path.join(work, "out.png")
    with _lock:
        try:
            code, tail = _run([exe, "-M", "upscale", "--upscale-model", up, "-i", sp, "-o", dest], 1, 1, on_progress, stop, None, None, label="Upscaling")
            if stop is not None and stop.is_set(): return None
            if code != 0 or not os.path.exists(dest):
                if _proc["stalled"]: raise RuntimeError("the upscaler stopped responding, so it was stopped")
                raise RuntimeError("the upscaler stopped with an error (details in logs/image_engine.log)")
            pic = Image.open(dest).convert("RGB")
            if factor == 2: pic = pic.resize((src.width * 2, src.height * 2), Image.LANCZOS)
            meta = dict(prefs.picture_info(path)); meta.update(upscaled=f"{factor}x", size=f"{pic.width}x{pic.height}", made_by="Instant Easel Pro")
            stem = os.path.splitext(os.path.basename(path))[0]
            return prefs.new_image(pic, f"{stem[-30:]}-{factor}x", meta=meta)
        finally: _set(None, "")

def _run(cmd, n, steps, on_progress, stop, prev, preview, label="Painting"):
    """run the engine once with progress, a live preview and a watchdog; -> (exit code, the end of what it printed)"""
    _set("painting", f"{label}…", 0.0); _proc["stalled"] = False
    log = open(paths.log_file("image_engine.log"), "a", encoding="utf-8", errors="replace")
    log.write(f"\n=== {datetime.datetime.now().isoformat(timespec='seconds')} {subprocess.list2cmdline(cmd)}\n"); log.flush()
    p = _proc["p"] = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
                                       cwd=os.path.dirname(cmd[0]), creationflags=0x08000000 if sys.platform == "win32" else 0)
    seen = dict(t=time.time(), prev=0.0, done=0); limit = float(_pref("image_stall_minutes", 10)) * 60
    def watch():                                                               # nothing printed for too long: the engine is stuck
        while p.poll() is None:
            time.sleep(1)
            if time.time() - seen["t"] > limit and p.poll() is None:
                _proc["stalled"] = True
                try: p.kill()
                except Exception: pass
                return
            if prev and preview and os.path.exists(prev):
                try:
                    m = os.path.getmtime(prev)
                    if m > seen["prev"]: seen["prev"] = m; preview(prev)
                except Exception: pass
    threading.Thread(target=watch, name="image engine watch", daemon=True).start()
    buf = ""; tail = ""
    try:
        while True:
            ch = p.stdout.read(1)
            if not ch: break
            seen["t"] = time.time(); log.write(ch); tail = (tail + ch)[-6000:]
            if ch in "\r\n":
                m = re.search(r"(\d+)/(\d+)", buf)
                if m and int(m.group(2)) == steps and steps > 1:
                    i = min(seen["done"], n - 1); s = int(m.group(1))
                    if s == steps: seen["done"] += 1
                    frac = (i + s / steps) / n; _set("painting", f"{label} {i + 1} of {n}: step {s} of {steps}", frac)
                    if on_progress: on_progress(frac, _state["detail"])
                buf = ""
            else: buf = buf[-200:] + ch
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

import atexit; atexit.register(stop_now)                                      # never leave the engine running after the app closes
