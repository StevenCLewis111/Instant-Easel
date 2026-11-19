"""
pc_models_test.py: the PC check, which models each kind of PC is offered, the AI jobs line, and the memory guard.
No models are downloaded and nothing is painted: the engines' decisions are checked, not their pictures.   Run:  python tests/pc_models_test.py
"""
import os, sys, json, time, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _testlog; ROOT = _testlog.start(__file__)
import atexit
_SETTINGS = os.path.join(ROOT, ".json", "instant_easel_settings.json"); _KEEP = open(_SETTINGS, "rb").read() if os.path.exists(_SETTINGS) else None
def _restore():                                                                  # your settings exactly as they were
    if _KEEP is not None: open(_SETTINGS, "wb").write(_KEEP)
    for ext in (".bak", ".tmp"):
        try: os.remove(_SETTINGS + ext)
        except OSError: pass
atexit.register(_restore)
import hardware, catalog, jobs

steps = []
def check(name, ok, got=""):
    steps.append(("ok   " if ok else "FAIL ") + name + ("" if ok else f"   (got: {got})"))

def as_pc(d):
    os.environ["INSTANT_EASEL_FAKE_PC"] = json.dumps(d); hardware._pc.clear(); return hardware.pc()

YOURS = dict(cpu="12th Gen Intel(R) Core(TM) i5-12400", cores=6, threads=12, ghz_max=2.5, ram_gb=32, vram_free_gb=5.6,
             gpus=[dict(name="Intel(R) UHD Graphics 730", vram_gb=0.1), dict(name="Intel(R) Arc(TM) A380 Graphics", vram_gb=6.0)])
WEAK = dict(cpu="Intel Core i3", cores=2, threads=4, ram_gb=8, gpus=[dict(name="Intel(R) UHD Graphics 620", vram_gb=0.1)])
BIG = dict(cpu="AMD Ryzen 9", cores=16, threads=32, ram_gb=64, vram_free_gb=23.0, gpus=[dict(name="NVIDIA GeForce RTX 4090", vram_gb=24.0)])
keys = lambda area: [e["key"] for e in catalog.options(area)]

# ---- the real scan on this machine
os.environ.pop("INSTANT_EASEL_FAKE_PC", None); real = hardware.scan()
check("scan: this machine's processor, cores, memory", real["cores"] > 0 and real["ram_gb"] > 0, real)
check("free memory reading", hardware.free_ram_gb() > 0, hardware.free_ram_gb())

# ---- your PC: i5-12400, 32 GB, Arc A380 6 GB (+ UHD 730, which doesn't count)
pc = as_pc(YOURS)
check("your PC: the Arc is the AI card (integrated UHD ignored)", pc["gpu"].startswith("Intel(R) Arc") and pc["vram_gb"] == 6.0, pc["gpu"])
check("your PC: core text models 9B (best), 4B, 2B — no 27B", keys("core") == ["9b", "4b", "2b"], keys("core"))
check("your PC: 9B runs with part in PC memory", catalog.options("core")[0]["fit"] == "card+ram", catalog.options("core")[0]["fit"])
check("your PC: coding 7B (best), 3B — no 14B", keys("AI Coding") == ["coder7b", "coder3b"], keys("AI Coding"))
check("your PC: images Z-Image Turbo (best), FLUX.2 Klein, Stable Diffusion 1.5 — no SDXL", keys("AI Images") == ["zimage", "klein", "sd15"], keys("AI Images"))
check("your PC: image edits FLUX.2 Klein (part in PC memory)", keys("Image edits") == ["klein"] and catalog.options("Image edits")[0]["fit"] == "card+ram", catalog.options("Image edits"))
check("your PC: Z-Image download is the Q4 size for a 6 GB card", catalog.variant(catalog.entry("AI Images", "zimage"))[0] == "Q4_K",
      catalog.variant(catalog.entry("AI Images", "zimage")))
check("your PC: no video model fits -> AI Videos tab and Video Learning hidden", catalog.hidden_tabs() == ({"AI Videos"}, {"Video Learning"}), catalog.hidden_tabs())
import features
check("your PC: the tab row has no AI Videos", "AI Videos" not in [m for m, _, _ in features.visible_menus()])
check("your PC: one line description", "6 cores / 12 threads" in hardware.describe() and "A380" in hardware.describe(), hardware.describe())
check("your PC: engines get the 6 real cores", hardware.threads_for_ai() == 6, hardware.threads_for_ai())

# ---- a weak laptop: no graphics card for AI, 8 GB
as_pc(WEAK)
check("weak PC: text 4B and 2B on the processor", keys("core") == ["4b", "2b"] and catalog.options("core")[0]["fit"] == "processor", catalog.options("core"))
check("weak PC: images only Stable Diffusion 1.5", keys("AI Images") == ["sd15"], keys("AI Images"))

# ---- a big PC: 24 GB card, 64 GB
as_pc(BIG)
check("big PC: 27B is the best core model", keys("core")[0] == "27b", keys("core"))
check("big PC: Z-Image gets the Q8 file, fully on the card", catalog.variant(catalog.entry("AI Images", "zimage"))[0] == "Q8_0" and catalog.options("AI Images")[0]["fit"] == "card")
check("big PC: AI Videos is shown", catalog.hidden_tabs() == (set(), set()), catalog.hidden_tabs())

# ---- the memory guard's choices (your PC)
import imaging, brain, prefs
as_pc(YOURS); prefs.set("model_AI_Images", "zimage")
os.makedirs(imaging.ZDIR, exist_ok=True); made = []
for n, gb in (("z_image_turbo-Q4_K.gguf", 4.9), ("qwen3-4b-instruct-2507-Q4_K_M.gguf", 2.5), ("ae.safetensors", 0.33)):
    p = os.path.join(imaging.ZDIR, n)
    if not os.path.exists(p):
        with open(p, "wb") as f: f.truncate(int(gb * 2 ** 30))                   # empty stand-ins of the right size (no disk space used)
        made.append(p)
try:
    check("Z-Image chosen and its three files found", imaging.kind() == "zimage" and imaging.zimage_parts() is not None, imaging.zimage_parts())
    check("Z-Image paints at 1024 x 1024 (Square)", imaging.pixels("Square") == (1024, 1024) and imaging.pixels("Square 512 x 512") == (1024, 1024))
    mode, low, why = imaging.plan_mode(1024, 1024, "Fast")
    check("guard: Fast on a 6 GB card -> stepped down (it wouldn't fit)", mode in ("Balanced", "Safe") and "free on the card" in why, (mode, why))
    os.environ["INSTANT_EASEL_FAKE_PC"] = json.dumps(dict(YOURS, vram_free_gb=1.5)); hardware._pc.clear()
    check("guard: card almost full -> Safe", imaging.plan_mode(1024, 1024, "Balanced")[0] == "Safe", imaging.plan_mode(1024, 1024, "Balanced"))
    check("guard: smaller size after Safe runs out", imaging._smaller(1024, 1024) == (768, 768), imaging._smaller(1024, 1024))
    check("out-of-memory messages are recognised", all(imaging.OOM.search(t) for t in ("ggml_vulkan: Device memory allocation of size 4831838208 failed",
          "ErrorOutOfDeviceMemory", "vk::DeviceLostError")))
finally:
    for p in made: os.remove(p)
    try: os.rmdir(imaging.ZDIR)
    except OSError: pass
as_pc(YOURS)
f9 = os.path.join(brain.TEXT, "9b", "test-Q4_K_M.gguf"); os.makedirs(os.path.dirname(f9), exist_ok=True)
with open(f9, "wb") as f: f.truncate(int(5.7 * 2 ** 30))
try:
    check("text guard: Fast 9B on a 6 GB card -> Balanced (the engine fits it)", brain._plan("9b", f9, "Fast")[0] == "Balanced", brain._plan("9b", f9, "Fast"))
    check("text guard: then Safe, then the processor", brain._plan("9b", f9, "Balanced") == ["Balanced", "Safe", "processor"], brain._plan("9b", f9, "Balanced"))
finally:
    os.remove(f9)
    try: os.rmdir(os.path.dirname(f9))
    except OSError: pass

# ---- the AI jobs line
order, live, peak = [], [0], [0]; lk = threading.Lock(); gate = threading.Event()
def work(name, secs=0.3):
    def fn(job):
        with lk: live[0] += 1; peak[0] = max(peak[0], live[0])
        if name == "first": gate.wait(5)
        time.sleep(secs); order.append(name)
        with lk: live[0] -= 1
        return name
    return fn
done = []
j1 = jobs.submit("AI Images", "first", work("first"), kind="image", page="p1", engine="image", on_done=done.append)
time.sleep(0.2)
j2 = jobs.submit("AI Chat", "chat", work("chat"), page="p2", engine="4b", on_done=done.append)
j3 = jobs.submit("AI Images", "second picture", work("picture2"), kind="image", page="p3", engine="image", on_done=done.append)
j4 = jobs.submit("AI Coding", "cancel me", work("never"), page="p4", engine="coder7b")
check("jobs: the first runs, the rest wait in order", j1.place() == 0 and j2.place() == 1 and j3.place() == 2, (j1.place(), j2.place(), j3.place()))
check("jobs: busy() per page", jobs.busy("p2") is j2 and jobs.busy("nothing") is None)
check("jobs: where() says the place", jobs.where(j3) == "waiting: 2nd in line", jobs.where(j3))
jobs.cancel(j4); gate.set()
t0 = time.time()
while len(done) < 3 and time.time() - t0 < 10: time.sleep(0.05)
check("jobs: only one ran at a time", peak[0] == 1, peak[0])
check("jobs: pipelining — the second picture went before the chat (image engine already in use)", order == ["first", "picture2", "chat"], order)
check("jobs: a cancelled waiting job never runs", "never" not in order and j4.state == "cancelled", (order, j4.state))
check("jobs: the line is empty afterwards", jobs.snapshot() == [] and jobs.busy("p1") is None)

os.environ.pop("INSTANT_EASEL_FAKE_PC", None); hardware._pc.clear()
fails = [s for s in steps if s.startswith("FAIL")]
print("\n".join(steps)); print(f"\n{len(steps) - len(fails)} of {len(steps)} passed")
sys.exit(1 if fails else 0)
