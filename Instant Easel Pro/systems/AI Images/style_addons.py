"""
style_addons.py: Templates — ready-made styles (LoRAs) made by other people for an image or video model, one per style, downloaded from Hugging
Face when you ask (Settings > Templates). When a style has its add-on and Z-Image paints, the add-on is switched
on with its trigger words; otherwise the style's own words do the job, as before. Your own can be added from a Hugging Face link.

    import style_addons as SA
    SA.CATALOG                      the built-in list: style -> dict(repo, trigger, weight, hint, note)
    SA.installed(style)             -> path of its file, or None
    SA.download(style, on_done)     in the background (needs the image engine's downloader)
    SA.lora_for(style)              -> (text added to the prompt, folder) or None: what styles.resolve hands the engine
    SA.add_own(style, repo_or_link, trigger, weight)   your own pick from Hugging Face

Each add-on is made for one picture model (its "base"): the built-in ones for Z-Image Turbo; yours can be for any of BASES (from
Hugging Face or a Civitai link, where the base is read from the page). An add-on is only used when its own model paints, and only when
it's switched on (Settings > Templates: SA.enabled / SA.set_enabled).
"""
import os, re, json, threading

# style: the Hugging Face repo, the words that switch it on, how strong (0-1.2), part of the file's name if the repo holds several
CATALOG = {
    "Anime":                     dict(repo="artificialguybr/ANIME-REDMOND-ZIMAGE", trigger="Anime, AnimedREDAF", weight=0.9,
                                      note="Anime style, very consistent (artificialguybr, Apache 2.0)."),
    "Line art / colouring page": dict(repo="artificialguybr/COLORINGBOOK-REDMOND-ZIMAGE", trigger="Coloring Book, ColoringBookAF", weight=0.9,
                                      note="Clean colouring-book line art (artificialguybr, Apache 2.0)."),
    "Pixel art":                 dict(repo="reverentelusarca/elusarca-pixel-art-style-lora-zimage-turbo", trigger="pixel art", weight=0.9,
                                      note="More detailed pixel art."),
    "Pencil sketch":             dict(repo="Ttio2/Z-Image-Turbo-pencil-sketch", trigger="pencil sketch", weight=0.9,
                                      note="Graphite pencil drawings."),
    "Black & white":             dict(repo="frankbarbs/darkroom-noir-zimage", trigger="drkrm style", weight=0.8,
                                      note="Darkroom black and white, film-noir light."),
    "Vintage photo":             dict(repo="renderartist/Technically-Color-Z-Image-Turbo", trigger="t3chnic4lly", weight=0.8,
                                      note="Classic 1950s-60s Technicolor film look (renderartist, Apache 2.0)."),
    "Minimal / flat":            dict(repo="oshi-pog/zimage-flat-color-v2-1", trigger="", weight=1.0,
                                      note="Flat colour illustration (motimalu)."),
    "Oil painting":              dict(repo="Zuellni/Z-Image-LoRAs", hint="oil", trigger="oil painting", weight=0.9,
                                      note="Oil painting on canvas (Zuellni)."),
    "Digital painting":          dict(repo="Zuellni/Z-Image-LoRAs", hint="digital_painting", trigger="digital painting", weight=0.9,
                                      note="Painterly digital art (Zuellni)."),
    "Realistic photo":           dict(repo="suayptalha/Z-Image-Turbo-Realism-LoRA", trigger="", weight=0.7,
                                      note="More natural, less 'AI-smooth' photos."),
}


BASES = {"zimage": "Z-Image Turbo", "klein": "FLUX.2 Klein", "sdxl": "SDXL", "sd15": "SD 1.5", "wan22": "Wan 2.2 (video)", "ltx2": "LTX-2.3 (video)"}


def base_of(e): return (e or {}).get("base", "zimage")


def base_from_civitai(name):
    """Civitai's 'baseModel' -> one of BASES ('' when Pro has no engine for it)"""
    n = (name or "").lower().replace(" ", "").replace("-", "").replace("_", "")
    if "zimage" in n: return "zimage"
    if "klein" in n or "flux.2" in n or "flux2" in n: return "klein"
    if any(k in n for k in ("sdxl", "pony", "illustrious", "noobai")): return "sdxl"
    if n.startswith("sd1") or "sd1.5" in n: return "sd15"
    if "wan" in n and "2.2" in n and "5b" in n: return "wan22"
    if "ltx" in n and "2.3" in n: return "ltx2"
    return ""


def enabled(style):
    import prefs
    return style not in (prefs.get("addons_off") or [])


def set_enabled(style, on):
    import prefs
    off = [s for s in (prefs.get("addons_off") or []) if s != style]
    if not on: off.append(style)
    prefs.set("addons_off", off)


def folder():
    import imaging
    return os.path.join(imaging.IMAGE, "style-addons")


def _own_file(): return os.path.join(folder(), "your-addons.json")


def _own():
    try:
        with open(_own_file()) as f: return json.load(f)
    except Exception: return {}


def entries():
    """every style add-on: the built-in ones, then yours (yours win when both name a style)"""
    out = dict(CATALOG); out.update(_own()); return out


def slug(style): return re.sub(r"[^a-z0-9]+", "-", style.lower()).strip("-") or "style"


def installed(style):
    p = os.path.join(folder(), slug(style) + ".safetensors"); return p if os.path.exists(p) else None


def lora_for(style, model_kind="zimage"):
    """(text for the prompt, folder) when this style's add-on is here, switched on, and made for the model that's painting; else None"""
    e = entries().get(style)
    if not e or not installed(style) or not enabled(style) or base_of(e) != model_kind: return None
    trig = e.get("trigger", "").strip(); w = float(e.get("weight", 0.9))
    return (f", {trig}" if trig else "") + f" <lora:{slug(style)}:{w:g}>", folder()


def _pick_file(repo, hint=""):
    """the add-on file in a Hugging Face repo: one whose name holds the hint, else the biggest .safetensors at the top level"""
    import brain
    info = brain._get_json(f"https://huggingface.co/api/models/{repo}?blobs=true")
    files = [(s["rfilename"], s.get("size") or 0) for s in info.get("siblings", []) if s["rfilename"].lower().endswith(".safetensors")]
    if not files: raise RuntimeError(f"{repo} has no .safetensors add-on file")
    if hint:
        hit = [f for f in files if hint.lower() in f[0].lower()]
        if hit: files = hit
    top = [f for f in files if "/" not in f[0]] or files
    name, size = max(top, key=lambda f: f[1]); return name, size


def _repo_of(link):
    """'owner/repo' from a Hugging Face link or 'owner/repo' itself"""
    link = link.strip()
    m = re.search(r"huggingface\.co/([^/\s]+/[^/\s?#]+)", link)
    if m: return m.group(1)
    if re.fullmatch(r"[\w.-]+/[\w.-]+", link): return link
    raise RuntimeError("that isn't a Hugging Face link or 'owner/name'")


def fetch(style, report=None):
    """fetch this style's add-on now (on this thread)"""
    import imaging
    e = entries().get(style)
    if not e: raise RuntimeError(f"no add-on is listed for {style}")
    dest = os.path.join(folder(), slug(style) + ".safetensors")
    if e.get("local"):
        if os.path.exists(dest): return
        raise RuntimeError(f"your {style} file was removed: add it again with Add your own")
    if e.get("url"):                                                       # (from Civitai: some files need your Civitai key)
        import prefs
        url = e["url"]; key = (prefs.get("civitai_key") or "").strip()
        if key: url += ("&" if "?" in url else "?") + "token=" + key
        return imaging._get(url, dest, f"the {style} add-on", max(e.get("size", 0), 5e7) / 1e9, report)
    name, size = _pick_file(e["repo"], e.get("hint", ""))
    imaging._get(f"https://huggingface.co/{e['repo']}/resolve/main/{name}", dest, f"the {style} add-on", max(size, 5e7) / 1e9, report)


def download(style, on_done=None):
    """fetch this style's add-on in the background; on_done(ok, message)"""
    import imaging
    e = entries().get(style)
    if not e: on_done and on_done(False, f"no add-on is listed for {style}"); return
    def work():
        try:
            fetch(style); imaging._set(None, "")
            on_done and on_done(True, f"the {style} add-on is ready — it switches on when {BASES.get(base_of(e), 'its model')} paints in {style}")
        except Exception as ex:
            imaging._set(None, ""); on_done and on_done(False, str(ex))
    threading.Thread(target=work, daemon=True, name="style add-on " + style).start()


def remove(style):
    p = installed(style)
    if p: os.remove(p)


def civitai_info(link):
    """from a Civitai link: dict(url, size, base, trigger, name). The model page's chosen version (?modelVersionId=) or its newest"""
    import brain
    m = re.search(r"civitai\.com/models/(\d+)", link); v = re.search(r"modelVersionId=(\d+)", link)
    if not m: raise RuntimeError("that isn't a Civitai model link (civitai.com/models/...)")
    info = brain._get_json(f"https://civitai.com/api/v1/models/{m.group(1)}")
    vers = info.get("modelVersions") or []
    ver = next((x for x in vers if v and str(x.get("id")) == v.group(1)), vers[0] if vers else None)
    if not ver: raise RuntimeError("that Civitai page has no files")
    files = [f for f in ver.get("files", []) if f.get("name", "").lower().endswith(".safetensors")]
    if not files: raise RuntimeError("that Civitai version has no .safetensors file")
    f = next((x for x in files if x.get("primary")), files[0])
    return dict(url=f["downloadUrl"], size=(f.get("sizeKB") or 0) * 1024, base=base_from_civitai(ver.get("baseModel", "")),
                base_name=ver.get("baseModel", ""), trigger=", ".join(ver.get("trainedWords") or []), name=info.get("name", ""), kind=info.get("type", ""))


def add_own(style, link, trigger="", weight=0.9, base=None):
    """your own pick for a style (a built-in style name, or a new one) from a Hugging Face or Civitai link: kept in your-addons.json.
    base: which picture model it's for (read from Civitai's page when not given; Z-Image for Hugging Face)"""
    os.makedirs(folder(), exist_ok=True); own = _own(); style = style.strip()
    if "civitai.com" in link:
        c = civitai_info(link)
        if c["kind"] and c["kind"].lower() not in ("lora", "locon", "dora", "lycoris"):
            raise RuntimeError(f"that's a {c['kind']}, not an add-on (LoRA). A whole model goes in with Settings > AI Models > Add manually")
        b = base or c["base"]
        if not b: raise RuntimeError(f"it's made for {c['base_name'] or 'a model'}, which Pro doesn't run")
        own[style] = dict(url=c["url"], size=c["size"], trigger=(trigger or c["trigger"]).strip(), weight=float(weight), base=b,
                          note=f"Your pick ({c['name']}, Civitai).", own=True)
    else:
        repo = _repo_of(link)
        own[style] = dict(repo=repo, trigger=trigger.strip(), weight=float(weight), base=base or "zimage", note=f"Your pick ({repo}).", own=True)
    with open(_own_file(), "w") as f: json.dump(own, f, indent=1)
    if installed(style): remove(style)                                    # (the old file was a different add-on)
    return own[style].get("repo") or own[style]["url"]


def add_file(style, path, trigger="", weight=0.9, base="zimage"):
    """your own template from a file you already have (a LoRA .safetensors): copied in, nothing to download"""
    import shutil
    if not os.path.isfile(path): raise RuntimeError("that file isn't there")
    if not path.lower().endswith(".safetensors"): raise RuntimeError("a template is a .safetensors file")
    if os.path.getsize(path) > 3e9: raise RuntimeError("that's too big for a template: a whole model goes in with Settings > AI Models > Add manually")
    os.makedirs(folder(), exist_ok=True); own = _own(); style = style.strip()
    dest = os.path.join(folder(), slug(style) + ".safetensors")
    if os.path.abspath(path) != os.path.abspath(dest): shutil.copyfile(path, dest)
    own[style] = dict(local=True, trigger=trigger.strip(), weight=float(weight), base=base or "zimage",
                      note=f"Your file ({os.path.basename(path)}).", own=True)
    with open(_own_file(), "w") as f: json.dump(own, f, indent=1)
    return dest


def forget_own(style):
    own = _own()
    if style in own:
        own.pop(style); remove(style)
        with open(_own_file(), "w") as f: json.dump(own, f, indent=1)
