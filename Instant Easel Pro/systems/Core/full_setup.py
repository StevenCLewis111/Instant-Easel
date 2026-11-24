"""
full_setup.py: Download Everything. One download that puts every part of Pro on the AI drive (Settings > AI Storage):

    drawing AI         the Drawing tab's smart tools (Select Subject, Object Selection, Magic Remove, AI Upscale)
    the engines        llama.cpp (text) and stable-diffusion.cpp (pictures)
    text models        every core model and every coding model, in every size: the ones this PC runs now, the smaller ones, and the
                       big ones for a bigger graphics card later (the app picks the size that suits the PC it's on)
    picture models     Z-Image Turbo and FLUX.2 Klein in every size, Stable Diffusion 1.5 and XL
    picture add-ons    the upscalers and the guides (pose, outline, depth, scribble), and every style add-on
    the video model    Wan 2.2 5B for the AI Videos tab
    code checkers      Node.js, TypeScript, GCC (C / C++), Java and Go, so AI Coding can check its code (Windows)

What's already here is skipped. A file that stops halfway carries on from where it stopped next time. One thing failing doesn't stop
the rest: it's listed at the end and tried again next time.

    import full_setup
    full_setup.items()          -> [Item] (group, label, size GB, have(), install(report))
    full_setup.start(on_done)   runs everything missing, in the background; full_setup.state has its progress; full_setup.stop()
"""
import os, sys, re, json, shutil, threading, zipfile, tarfile, urllib.request
import paths


class Item:
    def __init__(self, group, label, gb, have, install, note=""):
        self.group, self.label, self.gb, self.have, self.install, self.note = group, label, gb, have, install, note

    def here(self):
        try: return bool(self.have())
        except Exception: return False


class Stopped(Exception): pass


state = dict(running=False, item="", text="", fraction=0.0, done=0, total=0, failed=[], finished=[], stop=False)


# ---------------------------------------------------------------- the code checkers (Windows: portable, unpacked into Code Tools)
def _tools(): d = os.path.join(paths.ai_root(), "Code Tools"); os.makedirs(d, exist_ok=True); return d


def _tool_here(*names):
    import code_helpers as CH
    return all(CH._which(n) for n in names)


def _unpack_into(url, name, label, gb, report, subdir=None):
    """download an archive into Code Tools and unpack it there (into subdir when given)"""
    import brain
    tools = _tools(); arc = os.path.join(tools, name)
    brain._fetch(url, arc, label, gb * 1e9, report=report)
    dest = os.path.join(tools, subdir) if subdir else tools; os.makedirs(dest, exist_ok=True)
    try:
        if name.endswith(".zip"):
            with zipfile.ZipFile(arc) as z: z.extractall(dest)
        else:
            with tarfile.open(arc) as t: t.extractall(dest, filter="data")
    finally:
        try: os.remove(arc)
        except OSError: pass
    import code_helpers as CH; CH.rescan()


def _node(report):
    import brain
    rel = next(r for r in brain._get_json("https://nodejs.org/dist/index.json") if r.get("lts"))
    v = rel["version"]; name = f"node-{v}-win-x64.zip"
    _unpack_into(f"https://nodejs.org/dist/{v}/{name}", name, f"Node.js {v}", 0.035, report)


def _typescript(report):
    """TypeScript 7 is a native program, one package per platform: that package's tsc goes in Code Tools/typescript/bin"""
    import brain, platform as P
    arch = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(P.machine().lower(), "x64")
    plat = {"win32": "win32", "darwin": "darwin"}.get(sys.platform, "linux")
    info = brain._get_json(f"https://registry.npmjs.org/@typescript/typescript-{plat}-{arch}/latest")
    home = os.path.join(_tools(), "typescript"); shutil.rmtree(home, ignore_errors=True)
    _unpack_into(info["dist"]["tarball"], "typescript.tgz", f"TypeScript {info['version']}", 0.03, report, subdir="typescript")
    lib = os.path.join(home, "package", "lib"); binp = os.path.join(home, "bin")
    if not os.path.isdir(lib): raise RuntimeError("the TypeScript download didn't have its compiler in it")
    shutil.move(lib, binp)
    if sys.platform != "win32":
        for f in os.listdir(binp): os.chmod(os.path.join(binp, f), 0o755)
    import code_helpers as CH; CH.rescan()


def _ts_here(): return _tool_here("tsc")


def _gcc(report):
    import brain
    rels = brain._get_json("https://api.github.com/repos/brechtsanders/winlibs_mingw/releases?per_page=15")
    for rel in rels:
        if rel.get("draft") or rel.get("prerelease") or "snapshot" in rel.get("tag_name", ""): continue
        for a in rel.get("assets", []):
            n = a["name"].lower()
            if n.startswith("winlibs-x86_64-posix-seh-gcc") and "ucrt" in n and n.endswith(".zip") and "llvm" not in n:
                return _unpack_into(a["browser_download_url"], a["name"], "GCC (C and C++)", a.get("size", 0) / 1e9, report)
    raise RuntimeError("no GCC download found in winlibs' recent releases")


def _java(report):
    url = "https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/eclipse"
    _unpack_into(url, "jdk21.zip", "Java (Temurin JDK 21)", 0.2, report)


def _go(report):
    import brain
    rel = next(r for r in brain._get_json("https://go.dev/dl/?mode=json") if r.get("stable"))
    f = next(x for x in rel["files"] if x.get("os") == "windows" and x.get("arch") == "amd64" and x.get("kind") == "archive")
    _unpack_into("https://go.dev/dl/" + f["filename"], f["filename"], f"Go {rel['version']}", f.get("size", 0) / 1e9, report)


# ---------------------------------------------------------------- everything
def _note(e, min_v):
    """'for a bigger PC' when this model, or this size of it, is meant for more than this PC has"""
    import catalog, hardware
    if not catalog.fits(e): return "for a bigger PC"
    try: vram = float(hardware.pc().get("vram_gb") or 0)
    except Exception: vram = 0
    return f"for cards with {min_v} GB+" if min_v and vram < min_v else ""


def items():
    import brain, catalog, imaging, style_addons
    out = []
    add = lambda *a, **k: out.append(Item(*a, **k))
    import ai_cutout as AI
    for kind, (name, _) in AI.KINDS.items():
        size = sum((AI.MODELS[k][1] or AI.MODELS[k][5]) for k in AI.NEEDS[kind]) / 1e9
        add("Drawing AI", name, size, lambda k=kind: AI.have(k), lambda r, k=kind, n=name: AI.ensure(k, lambda d, t: r(f"Downloading the {n} model", d / t if t else 0)))
    add("Engines", "Text engine (llama.cpp)", 0.1, brain.server_exe, lambda r: brain._install_runtime(report=r))
    add("Engines", "Picture engine (stable-diffusion.cpp)", 0.1, imaging.engine_exe, lambda r: imaging._install_runtime(report=r))

    for area, group in (("core", "Text models"), ("AI Coding", "Coding models")):
        for e in catalog.LADDERS[area]:
            for min_v, quant, gb in e.get("variants", []):
                add(group, f"{e['label']} ({quant})", gb, lambda k=e["key"], q=quant: brain.have_variant(k, q),
                    lambda r, k=e["key"], q=quant: brain._install_model(k, q, report=r, strict=True),
                    note="; ".join(x for x in (_note(e, min_v), "non-commercial licence" if e.get("licence") == "non-commercial" else "") if x))

    for key, folder, prefix, plan_of, cfg in (("zimage", imaging.ZDIR, "z_image", imaging.zimage_download_plan, imaging.ZIMAGE),
                                              ("klein", imaging.KDIR, "flux2-klein", imaging.klein_download_plan, imaging.KLEIN)):
        e = catalog.entry("AI Images", key) or catalog.entry("Image edits", key)
        for min_v, quant, total in e["variants"]:
            label, repo, q, local, gb = plan_of(quant)[0]
            add("Picture models", f"{e['label']} ({quant})", gb, lambda f=folder, p=prefix, q=quant: imaging.have_file(f, p, q),
                lambda r, f=folder, p=prefix, step=plan_of(quant)[0], c=cfg: imaging._install_parts(f, [step], c["vae_file"], c["llm_repo"], p, r),
                note=_note(e, min_v))
        readers = {}
        for _, quant, _ in e["variants"]:                                       # (the biggest size reads with Q8_0, the others with Q4_K_M)
            step = plan_of(quant)[1]; readers.setdefault(step[2], step)
        for llm_q, step in readers.items():
            gb = step[4]
            add("Picture models", f"{e['label']}: text reader ({llm_q})", gb, lambda f=folder, q=llm_q: imaging.have_file(f, "qwen3", q),
                lambda r, f=folder, s=step, c=cfg, p=prefix: imaging._install_parts(f, [s], c["vae_file"], c["llm_repo"], p, r))
        vae = plan_of()[2]
        add("Picture models", f"{e['label']}: picture decoder", vae[4], lambda f=folder, n=vae[3]: os.path.exists(os.path.join(f, n)),
            lambda r, f=folder, s=vae, c=cfg, p=prefix: imaging._install_parts(f, [s], c["vae_file"], c["llm_repo"], p, r))
    add("Picture models", "Stable Diffusion 1.5", imaging.SD15["size"] / 1e9, lambda: imaging.model_file("sd15"),
        lambda r: imaging._get(f"https://huggingface.co/{imaging.SD15['repo']}/resolve/main/{imaging.SD15['file']}",
                               os.path.join(imaging.IMAGE, imaging.SD15["file"]), imaging.SD15["label"], imaging.SD15["size"] / 1e9, r))
    add("Picture models", "Stable Diffusion XL", imaging.SDXL["size"], lambda: os.path.exists(os.path.join(imaging.IMAGE, imaging.SDXL["file"])),
        lambda r: imaging.install_sdxl(r), note=_note(catalog.entry("AI Images", "sdxl"), 0))

    for key, a in imaging.ADDON_FILES.items():
        url = a.get("url") or f"https://huggingface.co/{imaging.GUIDE_REPO}/resolve/main/{a['file']}"
        add("Picture add-ons", a["label"][0].upper() + a["label"][1:], a["size"], lambda k=key: imaging.addon(k),
            lambda r, u=url, a=a: imaging._get(u, os.path.join(imaging.ADDONS, a["file"]), a["label"], a["size"], r))
    for style in style_addons.CATALOG:
        add("Style add-ons", f"{style} style", 0.17, lambda s=style: style_addons.installed(s), lambda r, s=style: style_addons.fetch(s, r))

    for quant in ("Q8_0", "Q4_K_M"):
        add("Video model", f"Wan 2.2 5B ({quant})", imaging.WAN["sizes"][quant], lambda q=quant: imaging.have_file(imaging.VDIR, "wan2.2", q),
            lambda r, q=quant: imaging.install_video_part("diffusion", q, r), note=("for Fast on a 16 GB+ card" if quant == "Q8_0" else ""))
        add("Video model", f"Wan 2.2: text reader ({quant})", imaging.WAN["t5_sizes"][quant], lambda q=quant: imaging.have_file(imaging.VDIR, "umt5", q),
            lambda r, q=quant: imaging.install_video_part("t5", q, r))
    add("Video model", "Wan 2.2: video decoder", imaging.WAN["vae_size"],
        lambda: imaging.have_file(imaging.VDIR, "wan2.2_vae", ends=(".safetensors",)), lambda r: imaging.install_video_part("vae", None, r))

    if sys.platform == "win32":
        add("Code checkers", "Node.js (checks JavaScript)", 0.035, lambda: _tool_here("node"), _node)
        add("Code checkers", "TypeScript", 0.023, _ts_here, _typescript)
        add("Code checkers", "GCC (checks C and C++)", 0.3, lambda: _tool_here("gcc", "g++"), _gcc)
        add("Code checkers", "Java JDK 21 (checks Java)", 0.2, lambda: _tool_here("javac"), _java)
        add("Code checkers", "Go (checks Go)", 0.08, lambda: _tool_here("gofmt"), _go)
    return out


def summary(its=None):
    """(GB still to download, GB in all, how many are missing)"""
    its = its if its is not None else items()
    miss = [i for i in its if not i.here()]
    return sum(i.gb for i in miss), sum(i.gb for i in its), len(miss)


def start(on_done=None, on_step=None, only_groups=None):
    """download everything that's missing, one at a time, in the background. on_step() after each change; on_done(finished, failed)"""
    if state["running"]: return False
    state.update(running=True, item="", text="Looking at what's already here…", fraction=0.0, done=0, total=0, failed=[], finished=[], stop=False)

    def report(text, frac):
        if state["stop"]: raise Stopped()
        state.update(text=text, fraction=frac or 0.0); on_step and on_step()

    def work():
        try:
            todo = [i for i in items() if (not only_groups or i.group in only_groups) and not i.here()]
            state["total"] = len(todo)
            import storage
            need = sum(i.gb for i in todo) * 1e9; free, _ = storage.drive_free()
            if free and need > free:
                state["failed"].append(("Not enough room", f"needs {need / 1e9:.0f} GB, the AI drive has {free / 1e9:.0f} GB free")); return
            have = storage.used("Shared models"); budget = storage.budget_gb("Shared models") * 1e9
            if have + need > budget:                                             # (make the shared models' portion big enough for it all)
                storage.set_budget_gb("Shared models", int((have + need) / 1e9) + 20)
            for n, it in enumerate(todo, 1):
                if state["stop"]: break
                state.update(item=f"{n} of {len(todo)}: {it.label}", text="Starting…", fraction=0.0); on_step and on_step()
                try:
                    it.install(report); state["finished"].append(it.label)
                except Stopped: break
                except Exception as e: state["failed"].append((it.label, str(e)[:300]))
                state["done"] = n; on_step and on_step()
        except Exception as e:
            state["failed"].append(("Download Everything", str(e)[:300]))
        finally:
            try:
                import imaging; imaging._set(None, "")
            except Exception: pass
            state.update(running=False, text="Stopped — press Download Everything to carry on" if state["stop"] else "Done")
            on_done and on_done(list(state["finished"]), list(state["failed"]))

    threading.Thread(target=work, name="download everything", daemon=True).start(); return True


def stop(): state["stop"] = True
