"""
video_engine.py: short videos with Wan 2.2 5B on the picture engine (stable-diffusion.cpp's video mode), from words or from a picture.

Two speeds, so any PC that can hold the model can make videos, a smaller one just takes longer:
    Fast    the video model stays on the graphics card (a 16 GB+ card)
    Slow    the model waits in PC memory and only the part working right now goes to the card; the text reader runs on the
            processor. Fits a 6-8 GB card with 24 GB+ of PC memory. If it still runs out of memory, it's tried again with the
            picture decoder on the processor too (slowest, but it finishes). With no graphics card for AI it all runs on the processor.

    import video_engine as V
    V.ready() / V.missing()                  are the engine and the model's three files here?
    V.make(prompt, seconds=2, size="Wide 832×480", quality="Normal", speed="Auto", image=None, ...) -> dict(video, frames, fps, ...)
    V.frames_of(path)                        the video's frames (PIL images), for the player and for saving as GIF / WebP
"""
import os, sys, re, io, time, json, glob, shutil, threading, subprocess, datetime, random
import paths

FPS = 24                                                                # Wan 2.2 5B makes 24 frames a second
LENGTHS = {"1 second": 25, "2 seconds": 49, "3 seconds": 73, "5 seconds": 121}   # (frames: 4 x n + 1)
SIZES = {"Wide 832×480": (832, 480), "Tall 480×832": (480, 832), "Square 512×512": (512, 512),
         "HD wide 1280×704": (1280, 704), "HD tall 704×1280": (704, 1280)}
QUALITY = {"Draft": 12, "Normal": 20, "Best": 30}                      # steps
SPEEDS = ["Auto", "Fast", "Slow"]
CFG = 5.0; FLOW_SHIFT = 3.0
NEGATIVE = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，"
            "画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走")
# (Wan's own standard 'leave out' list, in the language it was trained with: oversaturated, static, blurry, subtitles, worst quality,
#  JPEG artifacts, extra fingers, bad hands and faces, deformed limbs, frozen frames, cluttered background, three legs, crowds, walking backwards)

_proc = dict(p=None)


def _im(): import imaging; return imaging


def parts(): return _im().video_parts()


def _have_model():
    im = _im()
    return os.path.isdir(im.VDIR) and any(f.lower().startswith("wan2.2") and f.lower().endswith(".gguf") for f in os.listdir(im.VDIR))


def missing():
    """what still has to be downloaded, in words ([] when it can make videos)"""
    im = _im(); out = []
    if not im.engine_exe(): out.append("the picture engine")
    if not _have_model(): out.append("the Wan 2.2 video model")
    if not im.have_file(im.VDIR, "umt5"): out.append("its text reader")
    if not im.have_file(im.VDIR, "wan2.2_vae", ends=(".safetensors",)): out.append("its video decoder")
    return out


def ready(): return not missing()


def download(report=None):
    """get what's missing: the engine, then the model in the size that suits this PC, its text reader and decoder"""
    im = _im(); q = "Q8_0" if _vram() >= 16 else "Q4_K_M"
    if not im.engine_exe(): im._install_runtime(report=report)
    if not _have_model(): im.install_video_part("diffusion", q, report)
    if not im.have_file(im.VDIR, "umt5"): im.install_video_part("t5", q, report)
    im.install_video_part("vae", None, report)


def _vram():
    try: import hardware; return float(hardware.pc().get("vram_gb") or 0)
    except Exception: return 0


def plan_speed(wanted, w, h, frames):
    """(Fast / Slow, why) from what's free right now. Fast needs the model, the text reader and the frames' working memory on the card"""
    if wanted == "Slow": return "Slow", ""
    try:
        import hardware
        pc = hardware.pc()
        if not pc.get("vram_gb"): return "Slow", "no graphics card for AI: made on the processor (very slow)"
        if wanted == "Auto" and float(pc["vram_gb"]) < 12: return "Slow", f"a {float(pc['vram_gb']):g} GB card: the slow way (the model waits in PC memory)"
        free = hardware.free().get("vram_gb", 0)
    except Exception: return "Slow", ""
    p = parts() or {}
    files = sum(os.path.getsize(f) for f in p.values() if os.path.exists(f)) / 2 ** 30 if p else 10
    work = 1.5 + 2.5 * (w * h * frames) / (832 * 480 * 49)
    if free >= files + work: return "Fast", ""
    return "Slow", (f"only {free:.1f} GB free on the card: " if wanted == "Fast" else "") + "the slow way (the model waits in PC memory)"


def _speed_flags(speed, safest=False):
    im = _im(); h = im._help_text(); out = []
    want = ["--diffusion-fa"]
    if speed == "Slow": want += ["--offload-to-cpu", "--clip-on-cpu", "--vae-conv-direct"]
    if safest: want += ["--vae-on-cpu", "--temporal-tiling"]
    for f in want:
        if f in h or not h: out.append(f)
    if speed == "Slow" and "--clip-on-cpu" not in h and "--backend" in h: out += ["--backend", "te=cpu" + (",vae=cpu" if safest else "")]
    if "--threads" in h:
        try: import hardware; out += ["-t", str(hardware.threads_for_ai())]
        except Exception: pass
    return out


def build_cmd(prompt, w, h, frames, steps, seed, negative, speed, work, image=None, lora_dir=None, safest=False, cfg=CFG):
    im = _im(); p = parts(); fl = im._flags()
    cmd = [im.engine_exe(), "-M", "vid_gen", "--diffusion-model", p["diffusion"], "--vae", p["vae"], "--t5xxl", p["t5"],
           "-p", prompt, fl["negative"], negative or NEGATIVE, fl["width"], str(w), fl["height"], str(h),
           "--video-frames", str(frames), "--steps", str(steps), "--cfg-scale", f"{cfg:g}", "--sampling-method", "euler",
           "--flow-shift", f"{FLOW_SHIFT:g}", "-s", str(seed), "-o", os.path.join(work, "video.avi")]
    if "--fps" in im._help_text(): cmd += ["--fps", str(FPS)]
    if image: cmd += ["-i", image]
    if lora_dir: cmd += ["--lora-model-dir", lora_dir]
    return cmd + _speed_flags(speed, safest)


def _fit(image, w, h, dest):
    """the start picture cropped to the video's shape and sized to it"""
    from PIL import Image, ImageOps
    with Image.open(image) as im: im = ImageOps.exif_transpose(im).convert("RGB"); im = ImageOps.fit(im, (w, h), Image.LANCZOS); im.save(dest)
    return dest


def _run(cmd, steps, on_progress, stop, stall_minutes):
    """run the engine once with progress and a watchdog; -> (exit code, the end of what it printed)"""
    log = open(paths.log_file("video_engine.log"), "a", encoding="utf-8", errors="replace")
    log.write(f"\n=== {datetime.datetime.now().isoformat(timespec='seconds')} {subprocess.list2cmdline(cmd)}\n"); log.flush()
    p = _proc["p"] = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
                                       cwd=os.path.dirname(cmd[0]), creationflags=0x08000000 if sys.platform == "win32" else 0)
    seen = dict(t=time.time(), stalled=False); t0 = time.time()
    def watch():
        while p.poll() is None:
            time.sleep(2)
            if time.time() - seen["t"] > stall_minutes * 60 and p.poll() is None:
                seen["stalled"] = True
                try: p.kill()
                except Exception: pass
    threading.Thread(target=watch, daemon=True, name="video engine watch").start()
    buf = ""; tail = ""; phase = "Reading the words"
    try:
        while True:
            ch = p.stdout.read(1)
            if not ch: break
            seen["t"] = time.time(); log.write(ch); tail = (tail + ch)[-6000:]
            if ch in "\r\n":
                low = buf.lower()
                if "decod" in low and "vae" in low: phase = "Turning it into frames"
                m = re.search(r"(\d+)/(\d+)", buf)
                if m and int(m.group(2)) == steps:
                    s = int(m.group(1)); took = time.time() - t0
                    left = took / max(s, 1) * (steps - s) if s else 0
                    eta = f" — about {_mins(left)} left" if s >= 1 and s < steps else ""
                    on_progress and on_progress(0.92 * s / steps, f"Making the video: step {s} of {steps}{eta}")
                elif phase == "Turning it into frames": on_progress and on_progress(0.95, "Turning it into frames…")
                buf = ""
            else: buf = buf[-300:] + ch
            if stop is not None and stop.is_set(): p.terminate(); break
        p.wait()
    finally:
        log.close(); _proc["p"] = None
    if seen["stalled"]: tail += "\n(stalled: nothing printed for too long)"
    return p.returncode, tail


def _mins(sec):
    sec = int(sec)
    return f"{sec // 60} min" if sec >= 120 else f"{sec} s"


def stop_now():
    p = _proc["p"]
    if p is not None and p.poll() is None:
        try: p.terminate()
        except Exception: pass

import atexit; atexit.register(stop_now)


def _oom(tail):
    t = tail.lower()
    return any(k in t for k in ("out of memory", "outofmemory", "failed to allocate", "vk_error_out_of_device_memory", "cudamalloc", "stalled"))


def make(prompt, seconds="2 seconds", size="Wide 832×480", quality="Normal", speed="Auto", image=None, seed=None, negative="",
         lora=None, on_progress=None, stop=None, meta=None):
    """make one video. -> dict(video (the .avi), frames (count), fps, seconds, speed, folder). Raises when it can't"""
    im = _im()
    if missing(): raise RuntimeError("download first: " + ", ".join(missing()))
    w, h = SIZES.get(size, (832, 480)); frames = LENGTHS.get(seconds, 49); steps = QUALITY.get(quality, 20)
    seed = random.randint(0, 2 ** 31 - 1) if seed in (None, "", "random") else int(seed)
    try:
        import brain                                                             # (the card can't hold the text model and the video model at once)
        if brain.ready(): brain.stop()
    except Exception: pass
    mode, why = plan_speed(speed, w, h, frames)
    if why and on_progress: on_progress(0.0, why[0].upper() + why[1:])
    work = os.path.join(paths.ai("my-models", "runtime", "video-work"), datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(work, exist_ok=True)
    start = _fit(image, w, h, os.path.join(work, "start.png")) if image else None
    extra, lora_dir = lora if lora else ("", None)
    full = (prompt or "").strip() + (extra or "")
    stall = 15 if mode == "Fast" else 60
    tries = [(mode, False)] + ([("Slow", False)] if mode == "Fast" else []) + [("Slow", True)]
    tail = ""
    for i, (m, safest) in enumerate(tries):
        if stop is not None and stop.is_set(): raise RuntimeError("stopped")
        for f in glob.glob(os.path.join(work, "video*")): os.remove(f)
        if i and on_progress: on_progress(0.0, "Ran out of memory — trying again " + ("the slow way" if not safest else "the slowest, safest way") + "…")
        code, tail = _run(build_cmd(full, w, h, frames, steps, seed, negative, m, work, start, lora_dir, safest), steps, on_progress, stop, stall if not safest else 120)
        if stop is not None and stop.is_set(): raise RuntimeError("stopped")
        out = _result(work)
        if code == 0 and out: mode = m; break
        if not _oom(tail): break
    out = _result(work)
    if not out:
        last = [l for l in tail.strip().splitlines() if l.strip()][-3:]
        raise RuntimeError("the engine didn't make a video" + (": " + " / ".join(last)[:300] if last else ""))
    dest = _save(out, prompt, meta=dict(meta or {}, prompt=full, seed=seed, size=f"{w}x{h}", frames=frames, steps=steps, speed=mode,
                                         start_picture=bool(image)))
    shutil.rmtree(work, ignore_errors=True)
    on_progress and on_progress(1.0, "Done")
    return dict(video=dest, frames=frames, fps=FPS, seconds=round(frames / FPS, 1), speed=mode, seed=seed, folder=os.path.dirname(dest))


def _result(work):
    """the video the engine wrote: video.avi (or another video file), else its frames as numbered pictures turned into one"""
    for ext in (".avi", ".mp4", ".webm", ".webp", ".gif"):
        hit = [f for f in glob.glob(os.path.join(work, "video*" + ext))]
        if hit: return max(hit, key=os.path.getsize)
    frames = sorted(glob.glob(os.path.join(work, "video*.png")), key=lambda f: [int(x) for x in re.findall(r"\d+", os.path.basename(f))] or [0])
    if len(frames) > 1:
        from PIL import Image
        ims = [Image.open(f).convert("RGB") for f in frames]; dest = os.path.join(work, "video.webp")
        ims[0].save(dest, save_all=True, append_images=ims[1:], duration=int(1000 / FPS), loop=0, quality=90); return dest
    return None


def videos_folder():
    import prefs
    try: d = prefs.work_folder("videos")
    except Exception: d = os.path.join(prefs.save_folder(), "Videos")
    os.makedirs(d, exist_ok=True); return d


def _save(src, prompt, meta=None):
    words = re.sub(r"[^\w]+", "-", (prompt or "video").lower()).strip("-")[:40] or "video"
    base = os.path.join(videos_folder(), f"{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}-{words}")
    dest = base + os.path.splitext(src)[1]; shutil.move(src, dest)
    try:
        with open(base + ".json", "w", encoding="utf-8") as f: json.dump(meta or {}, f, indent=1, ensure_ascii=False)
    except Exception: pass
    return dest


# ---------------------------------------------------------------- reading it back: the player and saving as GIF / WebP
def frames_of(path, limit=None):
    """the video's frames as PIL images. The engine's .avi holds one JPEG per frame, read straight out of it"""
    from PIL import Image
    if path.lower().endswith((".webp", ".gif")):
        out = []
        with Image.open(path) as im:
            try:
                while True:
                    out.append(im.convert("RGB").copy()); im.seek(im.tell() + 1)
                    if limit and len(out) >= limit: break
            except EOFError: pass
        return out
    data = open(path, "rb").read(); out = []; i = 0
    while True:
        a = data.find(b"\xff\xd8\xff", i)
        if a < 0: break
        b = data.find(b"\xff\xd9", a + 3)
        if b < 0: break
        try:
            im = Image.open(io.BytesIO(data[a:b + 2])); im.load(); out.append(im.convert("RGB"))
        except Exception: pass
        i = b + 2
        if limit and len(out) >= limit: break
    if not out:
        try:
            import imageio.v3 as iio; out = [Image.fromarray(f) for f in iio.imread(path)]
        except Exception: pass
    return out


def save_as(path, kind, fps=FPS):
    """another copy of the video for sharing: 'gif' or 'webp' (both play anywhere, even in a browser); -> its path"""
    frames = frames_of(path)
    if not frames: raise RuntimeError("couldn't read the video's frames")
    dest = os.path.splitext(path)[0] + "." + kind
    if kind == "gif":
        small = [f.copy() for f in frames]
        if max(small[0].size) > 640:
            k = 640 / max(small[0].size); small = [f.resize((int(f.width * k), int(f.height * k))) for f in small]
        small[0].save(dest, save_all=True, append_images=small[1:], duration=int(1000 / fps), loop=0, optimize=True)
    else: frames[0].save(dest, save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0, quality=88)
    return dest


def last_frame(path, dest=None):
    """the video's last frame as a picture (to carry on from it, or keep)"""
    frames = frames_of(path)
    if not frames: raise RuntimeError("couldn't read the video's frames")
    dest = dest or os.path.splitext(path)[0] + "-last.png"; frames[-1].save(dest); return dest
