"""
image_generator_test.py: the whole image generator with a stand-in engine (no graphics card or downloads needed).

A small fake sd-cli takes the same options as the real one, writes pictures and progress lines, and can pretend to run out of
memory or freeze. Checked: styles, sizes, the engine commands each section builds (models, reference pictures, guides, upscaling,
batches), out-of-memory retries, the frozen-engine watchdog, and every one of the 10 AI Images sections painting through the
AI jobs line inside the real app window. Everything goes into a temporary folder; your pictures and models aren't touched.
    Run:  python tests/image_generator_test.py
"""
import os, sys, json, time, shutil, tempfile, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _testlog; ROOT = _testlog.start(__file__)
os.environ.setdefault("INSTANT_EASEL_FAKE_PC", json.dumps(dict(cpu="i5-12400", cores=6, threads=12, ram_gb=32, vram_free_gb=5.6,
                      gpus=[dict(name="Intel(R) Arc(TM) A380 Graphics", vram_gb=6.0)])))
os.environ["INSTANT_EASEL_ALLOW_SECOND"] = "1"
TMP = tempfile.mkdtemp(prefix="ie-imagegen-")
import atexit
_SETTINGS = os.path.join(ROOT, ".json", "instant_easel_settings.json")
_KEEP = open(_SETTINGS, "rb").read() if os.path.exists(_SETTINGS) else None
def _restore():                                                                  # your settings, exactly as they were (even if the test fails)
    if _KEEP is not None: open(_SETTINGS, "wb").write(_KEEP)
    for ext in (".bak", ".tmp"):
        try: os.remove(_SETTINGS + ext)
        except OSError: pass
    shutil.rmtree(TMP, ignore_errors=True)
atexit.register(_restore)
steps = []
def check(name, ok, got=""): steps.append(("ok   " if ok else "FAIL ") + name + ("" if ok else f"   (got: {got})"))

FAKE = r'''#!/usr/bin/env python3
import sys, os, json, time, zlib, struct
a = sys.argv[1:]; here = os.path.dirname(os.path.abspath(__file__))
if "--help" in a:
    print("usage: sd-cli -W, --width -H, --height -n, --negative-prompt --mode img_gen img2img --mask --ref-image --offload-to-cpu --vae-tiling "
          "--clip-on-cpu --vae-on-cpu --threads --cache-mode --hires --control-net --control-image --control-strength --control-type "
          "--image-preprocess --upscale-model --preview --preview-path --preview-interval --batch-count --control-net-cpu "
          "path to write result image to. you can use printf-style %d format specifiers"); sys.exit(0)
log = os.path.join(here, "calls.jsonl"); open(log, "a").write(json.dumps(a) + "\n")
def val(k, d=None): return a[a.index(k) + 1] if k in a else d
def png(path, w, h):
    raw = b"".join(b"\x00" + bytes([90, 140, 200]) * w for _ in range(h))
    ch = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw, 1)) + ch(b"IEND", b""))
behave = open(os.path.join(here, "behave.txt")).read().strip() if os.path.exists(os.path.join(here, "behave.txt")) else ""
if behave == "oom-unless-offload" and "--offload-to-cpu" not in a or behave == "oom-always":
    print("ggml_vulkan: Device memory allocation of size 4831838208 failed. ErrorOutOfDeviceMemory"); sys.exit(1)
if behave == "freeze": time.sleep(60)
if behave == "no-preview" and "--preview-path" in a: print("error: unknown preview method for this model"); sys.exit(2)
if "-M" in a and val("-M") == "upscale":
    from_ = val("-i"); out = val("-o"); png(out, 64, 64); print("upscale done"); sys.exit(0)
w, h = int(val("-W", 64)), int(val("-H", 64)); n = int(val("-b", 1)); steps = int(val("--steps", 4)); out = val("-o")
if "--upscale-model" in a: w, h = w * 4, h * 4
w, h = max(8, w // 16), max(8, h // 16)          # small pictures keep the test quick (the size asked for is checked in the command)
for i in range(n):
    for s in range(1, steps + 1):
        print(f"  |====| {s}/{steps} - 0.01s/it", flush=True)
        if "--preview-path" in a: png(val("--preview-path"), 16, 16)
    png(out.replace("%03d", f"{i:03d}") if "%03d" in out else (out if i == 0 else out.replace(".png", f"_{i + 1}.png")), w, h)
print("save result image", flush=True)
'''

import prefs, imaging, hardware, styles, jobs, brain
prefs.set("work_folder", os.path.join(TMP, "work")); prefs.set("image_live_preview", True); prefs.set("image_stall_minutes", 10)
_base = os.path.dirname(imaging.ROOT)
_new = {name: os.path.join(TMP, "models", os.path.relpath(getattr(imaging, name), _base)) for name in ("ROOT", "IMAGE", "ZDIR", "KDIR", "ADDONS", "RUNTIME")}
for name, v in _new.items():                                                    # every path worked out first, then all moved to the temporary folder
    assert v.startswith(TMP), v; setattr(imaging, name, v)
os.makedirs(imaging.RUNTIME, exist_ok=True); exe = os.path.join(imaging.RUNTIME, "sd-cli"); open(exe, "w").write(FAKE); os.chmod(exe, 0o755)
CALLS = os.path.join(imaging.RUNTIME, "calls.jsonl"); BEHAVE = os.path.join(imaging.RUNTIME, "behave.txt")
def touch(p, mb=1):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f: f.truncate(mb * 1024 * 1024)
for d, files in ((imaging.ZDIR, ["z_image_turbo-Q4_K.gguf", "qwen3-4b-instruct-2507-Q4_K_M.gguf", "ae.safetensors"]),
                 (imaging.KDIR, ["flux2-klein-4b-Q4_K.gguf", "qwen3-4b-Q4_K_M.gguf", "flux2-vae.safetensors"]), (imaging.IMAGE, [imaging.SD15["file"]])):
    for f in files: touch(os.path.join(d, f))
for k, a in imaging.ADDON_FILES.items(): touch(os.path.join(imaging.ADDONS, a["file"]))
def calls():
    try: return [json.loads(l) for l in open(CALLS)]
    except FileNotFoundError: return []
def reset(behave=""):
    if os.path.exists(CALLS): os.remove(CALLS)
    open(BEHAVE, "w").write(behave)
from PIL import Image
pic = Image.new("RGB", (640, 480), (200, 120, 60))

# ---- models, sizes, styles
prefs.set("model_AI_Images", "zimage")
check("models found: Z-Image, FLUX.2 Klein, SD 1.5 and every add-on", imaging.have("zimage") and imaging.have("klein") and imaging.have("sd15") and all(imaging.addon(k) for k in imaging.ADDON_FILES))
check("sizes follow the model: Z-Image square 1024, SD 1.5 512, cinema 16:9", imaging.pixels("Square 1:1") == (1024, 1024) and imaging.pixels("Square 1:1", "sd15") == (512, 512)
      and imaging.pixels("Cinema 16:9")[0] > imaging.pixels("Cinema 16:9")[1], (imaging.pixels("Square 1:1"), imaging.pixels("Cinema 16:9")))
check("old saved size names still work", imaging.pixels("Square 512 x 512") == (1024, 1024) and imaging.pixels("Tall") == imaging.pixels("Tall 2:3"))
names = styles.names()
check("built-in styles include Cartoon, Anime, Realistic photo, Black & white", all(s in names for s in ("Cartoon", "Anime", "Realistic photo", "Black & white", "Watercolor", "Pixel art")), names)
z = styles.resolve("Anime", "a cat", "zimage"); s15 = styles.resolve("Anime", "a cat", "sd15")
check("a style is a sentence for Z-Image (no leave-out words)", "anime illustration" in z["prompt"].lower() and z["negative"] == "", z)
check("the same style is tags + leave-out words for SD 1.5", "anime style" in s15["prompt"] and "photo" in s15["negative"], s15)
check("a style as an edit says 'make it look like…'", "Make it look like" in styles.resolve("Watercolor", "add a boat", "klein", editing=True)["prompt"])
import image_models as IM
IM.root = lambda: (os.makedirs(os.path.join(TMP, "image-models"), exist_ok=True) or os.path.join(TMP, "image-models"))
IM.create("Sunny"); IM.update("Sunny", style_words="bright pastel colours, rounded shapes")
lab = os.path.join(IM.pictures_dir("Sunny"), "flower"); os.makedirs(lab, exist_ok=True)
for i in range(3): pic.save(os.path.join(lab, f"p{i}.png"))
own = styles.resolve(styles.YOURS + "Sunny", "a house", "zimage")
check("your own model works without training: its pictures + words through FLUX.2 Klein", own["model"] == "klein" and len(own["refs"]) == 3 and "pastel" in own["prompt"], own)
check("…and words only where the page can't switch model", styles.resolve(styles.YOURS + "Sunny", "a house", "sd15", allow_switch=False)["model"] == "sd15")

# ---- the engine commands
reset(); out = imaging.paint("a red shoe", n=2, size="Wide 3:2", steps=20, model="zimage")
c = calls()[-1] if calls() else []
check("Z-Image: 2 pictures in ONE engine run (-b 2), saved with their details", len(out) == 2 and c.count("-b") == 1 and c[c.index("-b") + 1] == "2"
      and prefs.picture_info(out[0]).get("model") == "Z-Image Turbo", (out, c))
check("Z-Image: its own steps (8) and CFG 1, no leave-out words, no sampler", c[c.index("--steps") + 1] == "8" and c[c.index("--cfg-scale") + 1] == "1.0" and "-n" not in c and "--sampling-method" not in c, c)
check("Z-Image: three model files passed", "--diffusion-model" in c and "--llm" in c and "--vae" in c)
check("the engine gets the 6 real cores", c[c.index("-t") + 1] == "6", c)
reset(); imaging.paint("make it night", model="klein", refs=[pic, pic], size=imaging.fit_size(pic, key="klein"))
c = calls()[-1]
check("FLUX.2 Klein edit: 2 reference pictures, 4 steps, euler", c.count("--ref-image") == 2 and c[c.index("--steps") + 1] == "4" and "euler" in c, c)
reset(); imaging.paint("a dancer", model="sd15", size="Tall 2:3", control=dict(image=pic, guide="pose", strength=0.85))
c = calls()[-1]
check("pose guide: control net, image, strength and type openpose on SD 1.5", "--control-net" in c and c[c.index("--control-type") + 1] == "openpose" and "-m" in c, c)
reset(); imaging.paint("a house", model="sd15", control=dict(image=pic, guide="outline", edges=True))
check("outline guide asks the engine to find the edges", "target=control,canny=true" in calls()[-1])
reset(); r = imaging.paint("a cat", model="sd15", upscale="2x")
check("upscale happens in the same run; kept at 2x", "--upscale-model" in calls()[-1] and Image.open(r[0]).width == (512 * 4 // 16) // 2, Image.open(r[0]).size)
seen = []
reset(); imaging.paint("a fox", model="zimage", preview=lambda p: seen.append(p))
time.sleep(1.2)
check("live preview: the engine writes it and the page is told", "--preview-path" in calls()[-1] and seen, seen)
try: imaging.paint("x", model="sd15", refs=[pic]); bad = False
except RuntimeError as e: bad = "FLUX.2 Klein" in str(e)
check("reference pictures on a model that can't use them: a clear message", bad)
reset(); up = imaging.upscale(r[0], 2)
check("Upscale a picture: saved as a new picture with its details", up and os.path.exists(up) and prefs.picture_info(up).get("upscaled") == "2x", up)

# ---- robustness
reset("oom-unless-offload"); notes = []; real_note = jobs.note; jobs.note = lambda t, k="busy": notes.append(t)
out = imaging.paint("a big castle", model="sd15", n=1)
check("out of graphics memory -> painted again in Safe mode, and you're told", len(out) == 1 and len(calls()) == 2 and "--offload-to-cpu" in calls()[-1]
      and any("OUT OF GRAPHICS MEMORY" in n for n in notes), (len(calls()), notes))
reset("oom-always"); notes.clear()
try: imaging.paint("a big castle", model="zimage", n=2); ok = False
except RuntimeError as e: ok = "even in Safe mode" in str(e)
check("still out of memory -> Safe, smaller, one at a time, then a clear message", ok and len(calls()) >= 4 and any("smaller" in n for n in notes), (len(calls()), notes))
jobs.note = real_note
reset("no-preview"); out = imaging.paint("a fox", model="zimage", preview=lambda p: None)
check("an extra the engine rejects (preview) -> painted again without the extras", len(out) == 1 and len(calls()) == 2 and "--preview-path" not in calls()[-1], len(calls()))
reset("freeze"); prefs.set("image_stall_minutes", 0.05); t0 = time.time()
try: imaging.paint("x", model="sd15"); froze = False
except RuntimeError as e: froze = "stopped responding" in str(e)
check("a frozen engine is stopped by the watchdog (not hanging the line)", froze and time.time() - t0 < 20, time.time() - t0)
prefs.set("image_stall_minutes", 10); reset()

# ---- the 10 sections inside the app
import tkinter as tk, main, image_pages as IP
IP.chars_root = lambda: (os.makedirs(os.path.join(TMP, "characters"), exist_ok=True) or os.path.join(TMP, "characters"))
app = main.InstantEasel(); app.withdraw(); app.update()
banners = []; real_banner = IP.T.banner
IP.T.banner = lambda w, text, kind="error": (banners.append((kind, text)), real_banner(w, text, kind))
sec = app.pages["AI Images"].pages
def run_page(title, setup, expect=1):
    app.show("AI Images"); app.pages["AI Images"].select(title); app.update(); pg = sec[title]; banners.clear(); reset()
    setup(pg); pg.go(); t0 = time.time()
    while (pg.job is None or pg.job.state in ("waiting", "running")) and time.time() - t0 < 30: app.update(); time.sleep(0.05)
    for _ in range(10): app.update(); time.sleep(0.02)
    errs = [t for k, t in banners if k == "error"]; n = len([w for w in pg.results.winfo_children()]) if title != "Inpainting" else 1
    ok = pg.job is not None and pg.job.state == "done" and not errs and len(calls()) == 1
    check(f"section {title}: paints through the AI line", ok, (pg.job and pg.job.state, errs, len(calls())))
    return calls()[-1] if calls() else []
def words(pg, t): pg.prompt.delete("1.0", "end"); pg.prompt.insert("1.0", t)
c = run_page("Text to Image", lambda pg: (words(pg, "a lighthouse"), pg.style.set("Cartoon"), pg.improve.set(False)))
check("  Text to Image uses the chosen style", "cartoon" in " ".join(c).lower())
c = run_page("Image to Image", lambda pg: (pg.slot.set(pic), words(pg, "make it autumn")))
check("  Image to Image repaints the start picture", "-i" in c and "--strength" in c)
c = run_page("Prompt to Edit", lambda pg: (pg.slot.set(pic), words(pg, "make it night")))
check("  Prompt to Edit uses FLUX.2 Klein with the picture as reference", "--ref-image" in c and any("klein" in x for x in c))
c = run_page("Multi-Image Fusion", lambda pg: (pg.slots[0].set(pic), pg.slots[1].set(pic), words(pg, "the cat from picture 1 on the sofa from picture 2")))
check("  Multi-Image Fusion sends both pictures", c.count("--ref-image") == 2)
def char(pg):
    IP.char_save("Mia", dict(name="Mia", description="red hair, green coat")); IP.char_add_picture("Mia", pic); pg._names_changed("Mia"); words(pg, "at the beach")
c = run_page("Consistent Character", char)
check("  Consistent Character uses Mia's picture and description", "--ref-image" in c and any("green coat" in x for x in c))
c = run_page("Depth to Image", lambda pg: (pg.slot.set(pic), pg.method.set("Its outlines"), words(pg, "a log cabin")))
check("  Depth to Image keeps the outlines with the edge guide", "--control-net" in c and "canny" in " ".join(c))
c = run_page("Sketch to Image", lambda pg: (pg.slot.set(pic), pg.amount.set("Follow my lines exactly"), words(pg, "a dragon")))
check("  Sketch to Image follows the lines with the scribble guide", "scribble" in " ".join(c))
c = run_page("Pose to Image", lambda pg: (pg.pose_name.set("Waving"), words(pg, "a knight")))
check("  Pose to Image sends the posed figure to the pose guide", "openpose" in c)
def inpaint(pg):
    pg.receive_img = None; pg.pad.set_picture(pic); pg.pad.mask.paste(255, (100, 100, 200, 200)); words(pg, "a red balloon")
c = run_page("Inpainting", inpaint)
check("  Inpainting paints only the brushed part (sharper detail mode)", "--mask" in c)
pg = sec["Inpainting"]; pg.pad.set_picture(pic); pg.pad.extend(["right"])
check("  Inpainting: Extend makes the picture wider and marks the new strip", pg.pad.pic.width == 800 and pg.pad.has_mask(), pg.pad.pic.size)
c = run_page("Image Prompting", lambda pg: (pg.slots[0].set(pic), pg.take.set("Style and feel"), words(pg, "a lighthouse")))
check("  Image Prompting sends the reference picture", "--ref-image" in c)
pg = sec["Text to Image"]
check("results: every section can send a picture on (Prompt to Edit takes it)", (IP.send_to(app, "Prompt to Edit", os.path.join(prefs.save_folder(), os.listdir(prefs.save_folder())[0])) or True)
      and sec["Prompt to Edit"].slot.image is not None)
app.destroy()

shutil.rmtree(TMP, ignore_errors=True)
fails = [s for s in steps if s.startswith("FAIL")]
print("\n".join(steps)); print(f"\n{len(steps) - len(fails)} of {len(steps)} passed")
sys.exit(1 if fails else 0)
