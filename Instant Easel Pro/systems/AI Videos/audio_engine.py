"""
audio_engine.py: the audio model. Voices (Kokoro) and sound effects matched to a video (MMAudio), and mixing them into the video.

None of it ships with the app. It all runs in its own Python, downloaded onto the AI drive (my-models/runtime/audio), so the
libraries it needs (some GPL, PyTorch for the effects) stay outside the app:
    voices         kokoro-onnx (Kokoro 82M, Apache-2.0): small; runs on the processor. Weak = the 8-bit file (88 MB), strong = the full one
    sound effects  MMAudio (code MIT, weights CC-BY-NC: non-commercial) on PyTorch: weak = small 16 kHz, strong = large 44.1 kHz v2.
                   A graphics card with CUDA makes it quick; otherwise it runs on the processor (slow, but it finishes)
    mixing         ffmpeg (from imageio-ffmpeg, in the same Python): voice + effects + video -> one .mp4

    import audio_engine as A
    A.have("voices", "weak") / A.install("voices", "weak", report)
    A.speak(text, voice, speed, out_wav, power)
    A.effects(video, prompt, out_wav, power, on_progress, stop)
    A.mix(video, [(wav, volume), ...], out_mp4)
"""
import os, sys, re, json, glob, shutil, zipfile, tarfile, subprocess, threading, time
import paths

KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
VOICE_FILES = {"weak": ("kokoro-v1.0.int8.onnx", 0.09), "strong": ("kokoro-v1.0.onnx", 0.33)}
VOICE_PACK = ("voices-v1.0.bin", 0.03)
EFFECT_MODELS = {"weak": ("small_16k", "MMAudio small 16 kHz", 1.6), "strong": ("large_44k_v2", "MMAudio large 44.1 kHz v2", 5.5)}
MMAUDIO_ZIP = "https://github.com/hkchengrex/MMAudio/archive/refs/heads/main.zip"
PY_VERSION = "3.12.10"                                                  # (Windows: the official Python package from nuget.org)
VOICES = {"American woman: Heart": "af_heart", "American woman: Bella": "af_bella", "American woman: Nicole": "af_nicole",
          "American woman: Sarah": "af_sarah", "American woman: Sky": "af_sky", "American man: Adam": "am_adam",
          "American man: Michael": "am_michael", "American man: Fenrir": "am_fenrir", "American man: Puck": "am_puck",
          "British woman: Emma": "bf_emma", "British woman: Isabella": "bf_isabella", "British man: George": "bm_george",
          "British man: Lewis": "bm_lewis"}
_proc = dict(p=None)


def root():
    d = paths.ai("my-models", "runtime", "audio"); os.makedirs(d, exist_ok=True); return d


def python_exe():
    r = root()
    p = os.path.join(r, "python", "tools", "python.exe") if sys.platform == "win32" else os.path.join(r, "venv", "bin", "python")
    return p if os.path.exists(p) else None


def _run(cmd, report=None, label="", stop=None, cwd=None, timeout_min=60):
    """run a command in the audio Python; its output goes to the log, the last lines to report(text, None). -> (code, tail)"""
    log = open(paths.log_file("audio_engine.log"), "a", encoding="utf-8", errors="replace")
    log.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} {subprocess.list2cmdline(cmd)}\n"); log.flush()
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PIP_DISABLE_PIP_VERSION_CHECK="1", PYTHONNOUSERSITE="1")
    p = _proc["p"] = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", cwd=cwd, env=env,
                                       creationflags=0x08000000 if sys.platform == "win32" else 0)
    tail = ""; seen = dict(t=time.time())
    def watch():
        while p.poll() is None:
            time.sleep(2)
            if (stop is not None and stop.is_set()) or time.time() - seen["t"] > timeout_min * 60:
                try: p.kill()
                except Exception: pass
    threading.Thread(target=watch, daemon=True).start()
    try:
        for line in p.stdout:
            seen["t"] = time.time(); log.write(line); tail = (tail + line)[-5000:]
            l = line.strip()
            if report and l: report(f"{label}{l[:110]}", None)
        p.wait()
    finally:
        log.close(); _proc["p"] = None
    return p.returncode, tail


def stop_now():
    p = _proc["p"]
    if p is not None and p.poll() is None:
        try: p.terminate()
        except Exception: pass


def _fail(what, tail):
    last = [l for l in tail.strip().splitlines() if l.strip()][-2:]
    raise RuntimeError(what + (": " + " / ".join(last)[:300] if last else ""))


# ---------------------------------------------------------------- its own Python
def install_python(report=None):
    if python_exe(): return
    r = root()
    if sys.platform == "win32":
        import brain
        try:
            vs = brain._get_json("https://api.nuget.org/v3-flatcontainer/python/index.json")["versions"]
            v = [x for x in vs if re.fullmatch(r"3\.12\.\d+", x)][-1]
        except Exception: v = PY_VERSION
        pkg = os.path.join(r, "python.zip")
        brain._fetch(f"https://api.nuget.org/v3-flatcontainer/python/{v}/python.{v}.nupkg", pkg, f"Python {v} for the audio model", 0.02e9, report=report)
        with zipfile.ZipFile(pkg) as z:
            for m in z.namelist():
                if m.startswith("tools/"): z.extract(m, os.path.join(r, "python"))
        os.remove(pkg)
    else:                                                                    # (Linux / Mac: a virtual environment from the system's Python 3)
        base = shutil.which("python3.12") or shutil.which("python3") or (sys.executable if not getattr(sys, "frozen", False) else None)
        if not base: raise RuntimeError("this needs Python 3 installed on the PC")
        code, tail = _run([base, "-m", "venv", os.path.join(r, "venv")], report, "Python: ")
        if code: _fail("couldn't make the audio Python", tail)
    py = python_exe()
    if not py: raise RuntimeError("the audio Python didn't unpack")
    code, tail = _run([py, "-m", "pip", "--version"])
    if code:
        code, tail = _run([py, "-m", "ensurepip", "--upgrade"], report, "Python: ")
        if code: _fail("couldn't set up pip in the audio Python", tail)


def pip(*args, report=None, stop=None):
    code, tail = _run([python_exe(), "-m", "pip", "install", "--no-input", *args], report, "Installing: ", stop)
    if code: _fail("couldn't install " + " ".join(a for a in args if not a.startswith("-"))[:80], tail)


def _has_module(*mods):
    py = python_exe()
    if not py: return False
    code, _ = _run([py, "-c", "import " + ", ".join(mods)])
    return code == 0


# ---------------------------------------------------------------- what's here
def _marker(name): return os.path.join(root(), name + ".ok")


def have(kind, power="weak"):
    """kind: 'voices' or 'effects'. power: 'weak' or 'strong'"""
    if not python_exe(): return False
    if kind == "voices":
        f = VOICE_FILES[power][0]
        return os.path.exists(os.path.join(root(), "voices", f)) and os.path.exists(os.path.join(root(), "voices", VOICE_PACK[0])) and os.path.exists(_marker("voices"))
    if kind == "effects": return os.path.exists(_marker("effects")) and os.path.isdir(_mmaudio_dir())
    return False


def downloaded(kind):
    """the powers of this kind that are here, weak first"""
    return [p for p in ("weak", "strong") if have(kind, p)]


def size_gb(kind, power):
    if kind == "voices": return VOICE_FILES[power][1] + (0 if downloaded("voices") else VOICE_PACK[1] + 0.12)
    return EFFECT_MODELS[power][2] + (0 if os.path.exists(_marker("effects")) else 2.5)


def _mmaudio_dir():
    hits = [d for d in glob.glob(os.path.join(root(), "MMAudio*")) if os.path.isdir(d)]
    return hits[0] if hits else os.path.join(root(), "MMAudio-main")


def _nvidia():
    try:
        import hardware; return "nvidia" in str(hardware.pc().get("gpu", "")).lower()
    except Exception: return False


def install(kind, power="weak", report=None, stop=None):
    """download what this needs: the audio Python, its libraries, and the model"""
    import brain
    install_python(report)
    if kind == "voices":
        if not os.path.exists(_marker("voices")):
            pip("kokoro-onnx", "soundfile", "imageio-ffmpeg", report=report, stop=stop); open(_marker("voices"), "w").close()
        d = os.path.join(root(), "voices"); os.makedirs(d, exist_ok=True)
        for name, gb in (VOICE_FILES[power], VOICE_PACK):
            dest = os.path.join(d, name)
            if not os.path.exists(dest): brain._fetch(KOKORO_URL + name, dest, f"the voice model ({name})", gb * 1e9, report=report)
        return
    if kind == "effects":
        if not os.path.exists(_marker("effects")):
            # an NVIDIA card: PyTorch with CUDA. Otherwise the processor build (on Windows PyPI's own torch is that build)
            first = ["--index-url", "https://download.pytorch.org/whl/cu124"] if _nvidia() else ([] if sys.platform == "win32" else
                    ["--index-url", "https://download.pytorch.org/whl/cpu"])
            try: pip("torch", "torchvision", "torchaudio", *first, report=report, stop=stop)
            except RuntimeError:
                if not first: raise
                pip("torch", "torchvision", "torchaudio", report=report, stop=stop)      # (that site unreachable: PyPI's own)
            if not os.path.isdir(_mmaudio_dir()):
                z = os.path.join(root(), "mmaudio.zip"); brain._fetch(MMAUDIO_ZIP, z, "MMAudio", 0.01e9, report=report)
                with zipfile.ZipFile(z) as f: f.extractall(root())
                os.remove(z)
            pip(_mmaudio_dir(), "imageio-ffmpeg", report=report, stop=stop)
            open(_marker("effects"), "w").close()
        # its weights for this size download the first time it runs (they're fetched by MMAudio itself, into its folder)
        return
    raise ValueError(kind)


def remove(kind, power=None):
    if kind == "voices":
        for p in ([power] if power else ["weak", "strong"]):
            try: os.remove(os.path.join(root(), "voices", VOICE_FILES[p][0]))
            except OSError: pass
    elif kind == "effects":
        shutil.rmtree(_mmaudio_dir(), ignore_errors=True)
        try: os.remove(_marker("effects"))
        except OSError: pass


# ---------------------------------------------------------------- voices
SPEAK = r'''
import json, sys
a = json.loads(sys.argv[1])
from kokoro_onnx import Kokoro
import soundfile as sf
k = Kokoro(a["model"], a["voices"])
samples, rate = k.create(a["text"], voice=a["voice"], speed=a["speed"], lang=a["lang"])
sf.write(a["out"], samples, rate)
print("ok", len(samples) / rate)
'''


def speak(text, voice="af_heart", speed=1.0, out=None, power=None):
    """the words, spoken, into out (.wav). -> (path, seconds)"""
    power = power or ("strong" if have("voices", "strong") else "weak")
    if not have("voices", power): raise RuntimeError("download the voice model first (Settings > AI Models > Audio)")
    d = os.path.join(root(), "voices"); out = out or os.path.join(root(), "work", f"voice-{int(time.time())}.wav")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    lang = "en-gb" if voice[:1] == "b" else "en-us"
    arg = json.dumps(dict(model=os.path.join(d, VOICE_FILES[power][0]), voices=os.path.join(d, VOICE_PACK[0]), text=text, voice=voice,
                          speed=float(speed), lang=lang, out=out))
    code, tail = _run([python_exe(), "-c", SPEAK, arg])
    if code or not os.path.exists(out): _fail("the voice didn't come out", tail)
    m = re.search(r"ok ([\d.]+)", tail)
    return out, float(m.group(1)) if m else 0.0


# ---------------------------------------------------------------- sound effects
def effects(video, prompt="", out=None, power=None, seconds=None, on_progress=None, stop=None, seed=42):
    """sound effects that match what happens in the video (and the words, if any), into out (.wav/.flac). -> path"""
    power = power or ("strong" if os.path.exists(_marker("effects")) and _nvidia() else "weak")
    if not have("effects"): raise RuntimeError("download the sound effects model first (Settings > AI Models > Audio)")
    variant = EFFECT_MODELS[power][0]; mm = _mmaudio_dir(); outdir = os.path.join(root(), "work", f"fx-{int(time.time())}")
    os.makedirs(outdir, exist_ok=True)
    seconds = seconds or video_seconds(video) or 8
    cmd = [python_exe(), os.path.join(mm, "demo.py"), "--variant", variant, "--video", video, "--prompt", prompt or "", "--duration", f"{seconds:.2f}",
           "--output", outdir, "--seed", str(seed), "--skip_video_composite"]
    if not _nvidia(): cmd.append("--full_precision")                     # (on the processor: full precision)
    on_progress and on_progress(None, "Making the sound effects (the first time, it downloads its weights)…")
    code, tail = _run(cmd, (lambda t, f: on_progress(None, t)) if on_progress else None, "Sound effects: ", stop, cwd=mm, timeout_min=90)
    got = sorted(glob.glob(os.path.join(outdir, "*.flac")) + glob.glob(os.path.join(outdir, "*.wav")), key=os.path.getmtime)
    if code or not got: _fail("the sound effects didn't come out", tail)
    if out: shutil.move(got[-1], out); shutil.rmtree(outdir, ignore_errors=True); return out
    return got[-1]


# ---------------------------------------------------------------- mixing (ffmpeg)
_ff = {}


def ffmpeg():
    if "exe" in _ff and _ff["exe"] and os.path.exists(_ff["exe"]): return _ff["exe"]
    exe = None
    py = python_exe()
    if py:
        code, tail = _run([py, "-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"])
        if code == 0: exe = tail.strip().splitlines()[-1].strip()
    exe = exe if exe and os.path.exists(exe) else shutil.which("ffmpeg")
    _ff["exe"] = exe; return exe


def video_seconds(path):
    """how long a video is, read by ffmpeg (or counted from the frames)"""
    ff = ffmpeg()
    if ff:
        r = subprocess.run([ff, "-i", path], capture_output=True, text=True, errors="replace",
                           creationflags=0x08000000 if sys.platform == "win32" else 0)
        m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
        if m: return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    try:
        import video_engine as V; return len(V.frames_of(path)) / V.FPS
    except Exception: return 0


def mix(video, tracks, out):
    """the video with these sound tracks [(path, volume 0-2), ...] mixed together, as an .mp4 (H.264 + AAC, plays anywhere). -> out"""
    ff = ffmpeg()
    if not ff: raise RuntimeError("mixing needs ffmpeg: download the voice or sound effects model first")
    tracks = [(p, v) for p, v in tracks if p and os.path.exists(p)]
    cmd = [ff, "-y", "-i", video]
    for p, _ in tracks: cmd += ["-i", p]
    if tracks:
        parts = "".join(f"[{i + 1}:a]volume={v:g},apad[a{i}];" for i, (_, v) in enumerate(tracks))
        cmd += ["-filter_complex", parts + "".join(f"[a{i}]" for i in range(len(tracks))) + f"amix=inputs={len(tracks)}:duration=longest:normalize=0[a]",
                "-map", "0:v", "-map", "[a]", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    longest = max([_secs(p) for p, _ in tracks] or [0]); vlen = video_seconds(video)
    if tracks and vlen and longest > vlen + 0.1:                             # the sound runs longer: the last frame holds until it ends
        cmd += ["-vf", f"tpad=stop_mode=clone:stop_duration={longest - vlen + 0.1:.2f}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "veryfast", out]
    code, tail = _run(cmd)
    if code or not os.path.exists(out): _fail("couldn't mix the sound into the video", tail)
    return out


def _secs(path):
    try:
        import soundfile as sf; return sf.info(path).duration
    except Exception: return video_seconds(path)


def to_mp4(video, out=None):
    """a silent video as an .mp4 that plays anywhere"""
    return mix(video, [], out or os.path.splitext(video)[0] + ".mp4")


def join(videos, out):
    """several videos one after another, as one .mp4"""
    ff = ffmpeg()
    if not ff: raise RuntimeError("joining videos needs ffmpeg: download the voice or sound effects model first")
    lst = out + ".txt"
    with open(lst, "w", encoding="utf-8") as f:
        for v in videos: f.write("file '" + v.replace("'", "'\\''") + "'\n")
    code, tail = _run([ff, "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "veryfast", out])
    os.remove(lst)
    if code or not os.path.exists(out): _fail("couldn't join the clips", tail)
    return out


import atexit; atexit.register(stop_now)
