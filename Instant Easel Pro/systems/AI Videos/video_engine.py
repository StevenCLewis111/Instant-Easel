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
# the video models, weak to strong. LTX-2.3 makes the sound too (LTX-2 Community License: free under $10M a year in revenue)
MODELS = {"wan22": dict(label="Wan 2.2 5B", power="weak", sound=False),
          "ltx2": dict(label="LTX-2.3 22B (with sound)", power="strong", sound=True)}
LTX = dict(repo="unsloth/LTX-2.3-GGUF", llm_repo="unsloth/gemma-3-12b-it-qat-GGUF", llm_file="gemma-3-12b-it-qat-UD-Q4_K_XL.gguf",
           vae="vae/ltx-2.3-22b-dev_video_vae.safetensors", audio_vae="vae/ltx-2.3-22b-dev_audio_vae.safetensors",
           sizes=dict(diffusion=13.5, llm=7.3, vae=1.5, audio_vae=0.4))


def _im(): import imaging; return imaging


def ltx_dir():
    d = os.path.join(_im().ROOT, "video", "ltx23"); os.makedirs(d, exist_ok=True); return d


def ltx_parts():
    """{part: path} of LTX-2.3's files, or None"""
    d = ltx_dir(); fs = os.listdir(d); out = {}
    for part, test in (("diffusion", lambda f: f.startswith("ltx-2.3") and f.endswith(".gguf")), ("llm", lambda f: f.startswith("gemma-3") and f.endswith(".gguf")),
                       ("vae", lambda f: f.endswith("_video_vae.safetensors")), ("audio_vae", lambda f: f.endswith("_audio_vae.safetensors"))):
        hit = sorted(f for f in fs if test(f.lower()))
        if not hit: return None
        out[part] = os.path.join(d, hit[0])
    return out


def ltx_missing():
    out = []
    if not _im().engine_exe(): out.append("the picture engine")
    if not ltx_parts(): out.append("the LTX-2.3 model")
    return out


def install_ltx(report=None, part=None):
    """LTX-2.3: the distilled model (8 steps: the quick one), its video and audio decoders and its Gemma 3 text reader. part: just one of them"""
    im = _im(); d = ltx_dir(); have = os.listdir(d)
    if not im.engine_exe() and part is None: im._install_runtime(report=report)
    want = [part] if part else ["diffusion", "llm", "vae", "audio_vae"]
    if "diffusion" in want and not any(f.lower().startswith("ltx-2.3") and f.endswith(".gguf") for f in have):
        fs = im._hf_files(LTX["repo"])
        pick = ([f for f in fs if "/" not in f and "distilled" in f and "UD-Q4_K_M" in f and "1.1" not in f] or
                [f for f in fs if "/" not in f and "distilled" in f and "Q4_K_M" in f] or [f for f in fs if "/" not in f and "Q4_K_M" in f])
        if not pick: raise RuntimeError("no LTX-2.3 model file found to download")
        im._get(f"https://huggingface.co/{LTX['repo']}/resolve/main/{pick[0]}", os.path.join(d, os.path.basename(pick[0])), "LTX-2.3 (video + sound)", LTX["sizes"]["diffusion"], report)
    if "llm" in want and not any(f.lower().startswith("gemma-3") for f in have):
        im._get(f"https://huggingface.co/{LTX['llm_repo']}/resolve/main/{LTX['llm_file']}", os.path.join(d, LTX["llm_file"]), "LTX-2.3's text reader (Gemma 3 12B)", LTX["sizes"]["llm"], report)
    for k in ("vae", "audio_vae"):
        if k in want and not os.path.exists(os.path.join(d, os.path.basename(LTX[k]))):
            im._get(f"https://huggingface.co/{LTX['repo']}/resolve/main/{LTX[k]}", os.path.join(d, os.path.basename(LTX[k])),
                    "LTX-2.3's " + ("video" if k == "vae" else "sound") + " decoder", LTX["sizes"][k], report)


def downloaded_models():
    """the video models that are here, weak to strong"""
    return [k for k in MODELS if (k == "wan22" and _have_model() and not [m for m in missing() if "engine" not in m]) or (k == "ltx2" and ltx_parts())]


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


def plan_speed(wanted, w, h, frames, model="wan22"):
    """(Fast / Slow, why) from what's free right now. Fast needs the model, the text reader and the frames' working memory on the card"""
    if wanted == "Slow": return "Slow", ""
    try:
        import hardware
        pc = hardware.pc()
        if not pc.get("vram_gb"): return "Slow", "no graphics card for AI: made on the processor (very slow)"
        if wanted == "Auto" and float(pc["vram_gb"]) < 12: return "Slow", f"a {float(pc['vram_gb']):g} GB card: the slow way (the model waits in PC memory)"
        free = hardware.free().get("vram_gb", 0)
    except Exception: return "Slow", ""
    p = (ltx_parts() if model == "ltx2" else parts()) or {}
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


def build_ltx_cmd(prompt, w, h, frames, steps, seed, negative, speed, work, image=None, lora_dir=None, safest=False):
    im = _im(); p = ltx_parts(); fl = im._flags()
    cmd = [im.engine_exe(), "-M", "vid_gen", "--diffusion-model", p["diffusion"], "--vae", p["vae"], "--audio-vae", p["audio_vae"], "--llm", p["llm"],
           "-p", prompt, fl["width"], str(w), fl["height"], str(h), "--video-frames", str(frames), "--fps", str(FPS),
           "--steps", str(max(8, steps // 2)), "--cfg-scale", "1.0", "--sampling-method", "euler", "-s", str(seed), "-o", os.path.join(work, "video.webm")]
    if negative: cmd += [fl["negative"], negative]
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
         lora=None, on_progress=None, stop=None, meta=None, model="wan22", resolution=1.0, save=True):
    """make one video. -> dict(video (.avi, or .webm with sound from LTX), frames (count), fps, seconds, speed, folder). Raises when it can't"""
    im = _im(); ltx = model == "ltx2"
    miss = ltx_missing() if ltx else missing()
    if miss: raise RuntimeError("download first: " + ", ".join(miss))
    w, h = SIZES.get(size, (832, 480)) if isinstance(size, str) else size; frames = LENGTHS.get(seconds, 49) if isinstance(seconds, str) else int(seconds)
    if resolution != 1.0: w, h = max(256, round(w * resolution / 32) * 32), max(256, round(h * resolution / 32) * 32)
    steps = QUALITY.get(quality, 20)
    seed = random.randint(0, 2 ** 31 - 1) if seed in (None, "", "random") else int(seed)
    try:
        import brain                                                             # (the card can't hold the text model and the video model at once)
        if brain.ready(): brain.stop()
    except Exception: pass
    mode, why = plan_speed(speed, w, h, frames, model)
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
        cmd = (build_ltx_cmd(full, w, h, frames, steps, seed, negative, m, work, start, lora_dir, safest) if ltx else
               build_cmd(full, w, h, frames, steps, seed, negative, m, work, start, lora_dir, safest))
        code, tail = _run(cmd, int(cmd[cmd.index("--steps") + 1]), on_progress, stop, stall if not safest else 120)
        if stop is not None and stop.is_set(): raise RuntimeError("stopped")
        out = _result(work)
        if code == 0 and out: mode = m; break
        if not _oom(tail): break
    out = _result(work)
    if not out:
        last = [l for l in tail.strip().splitlines() if l.strip()][-3:]
        raise RuntimeError("the engine didn't make a video" + (": " + " / ".join(last)[:300] if last else ""))
    info = dict(meta or {}, prompt=full, seed=seed, size=f"{w}x{h}", frames=frames, steps=steps, speed=mode, start_picture=bool(image), model=model)
    if save: dest = _save(out, prompt, meta=info); shutil.rmtree(work, ignore_errors=True)
    else: dest = out                                                         # (Long Video: the clip stays in the work folder until it's joined)
    on_progress and on_progress(1.0, "Done")
    return dict(video=dest, frames=frames, fps=FPS, seconds=round(frames / FPS, 1), speed=mode, seed=seed, folder=os.path.dirname(dest), sound=ltx)


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
    if not out:                                                              # (.webm / .mp4: read with ffmpeg, from the audio model's Python or the PC)
        try:
            import audio_engine as A, tempfile, subprocess as sp
            ff = A.ffmpeg()
            if ff:
                d = tempfile.mkdtemp(prefix="ie-frames-")
                sp.run([ff, "-loglevel", "error", "-i", path, "-vf", "scale='min(960,iw)':-2", os.path.join(d, "f%05d.jpg")],
                       creationflags=0x08000000 if sys.platform == "win32" else 0)
                for f in sorted(glob.glob(os.path.join(d, "f*.jpg")))[:limit or None]:
                    with Image.open(f) as im: out.append(im.convert("RGB").copy())
                shutil.rmtree(d, ignore_errors=True)
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


def jpeg_frames(path):
    """the engine's .avi frames as the JPEG bytes they're stored as (nothing decoded: joining long videos stays light)"""
    data = open(path, "rb").read(); out = []; i = 0
    while True:
        a = data.find(b"\xff\xd8\xff", i)
        if a < 0: break
        b = data.find(b"\xff\xd9", a + 3)
        if b < 0: break
        out.append(data[a:b + 2]); i = b + 2
    return out


def write_avi(frames, path, fps=FPS, quality=92):
    """frames (PIL images, or JPEG bytes from jpeg_frames) -> an MJPEG .avi (plays in Windows' player and VLC; what the engine writes)"""
    import struct
    from PIL import Image
    if not frames: raise RuntimeError("no frames")
    if isinstance(frames[0], bytes):
        jpgs = list(frames)
        with Image.open(io.BytesIO(jpgs[0])) as im: w, h = im.size
    else:
        w, h = frames[0].size; jpgs = []
        for f in frames:
            b = io.BytesIO(); (f if f.size == (w, h) else f.resize((w, h))).convert("RGB").save(b, "JPEG", quality=quality); jpgs.append(b.getvalue())
    def chunk(tag, data): return tag + struct.pack("<I", len(data)) + data + (b"\0" if len(data) % 2 else b"")
    def lst(tag, data): return b"LIST" + struct.pack("<I", len(data) + 4) + tag + data
    n = len(jpgs); big = max(len(j) for j in jpgs)
    avih = struct.pack("<14I", int(1e6 / fps), big * fps, 0, 0x10, n, 0, 1, big, w, h, 0, 0, 0, 0)
    strh = struct.pack("<4s4sIHHIIIIIIIIhhhh", b"vids", b"MJPG", 0, 0, 0, 0, 1, fps, 0, n, big, 0xFFFFFFFF, 0, 0, 0, w, h)
    strf = struct.pack("<IiiHH4sIiiII", 40, w, h, 1, 24, b"MJPG", w * h * 3, 0, 0, 0, 0)
    hdrl = lst(b"hdrl", chunk(b"avih", avih) + lst(b"strl", chunk(b"strh", strh) + chunk(b"strf", strf)))
    movi_items = b""; idx = b""; off = 4
    for j in jpgs:
        c = chunk(b"00dc", j); idx += struct.pack("<4sIII", b"00dc", 0x10, off, len(j)); movi_items += c; off += len(c)
    body = b"AVI " + hdrl + lst(b"movi", movi_items) + chunk(b"idx1", idx)
    with open(path, "wb") as f: f.write(b"RIFF" + struct.pack("<I", len(body)) + body)
    return path


def last_frame(path, dest=None):
    """the video's last frame as a picture (to carry on from it, or keep)"""
    frames = frames_of(path)
    if not frames: raise RuntimeError("couldn't read the video's frames")
    dest = dest or os.path.splitext(path)[0] + "-last.png"; frames[-1].save(dest); return dest
