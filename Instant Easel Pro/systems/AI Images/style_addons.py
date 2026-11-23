"""
style_addons.py: ready-made style add-ons (LoRAs) made by other people for Z-Image Turbo, one per style, downloaded from Hugging
Face when you ask (Settings > AI Images > Style add-ons). When a style has its add-on and Z-Image paints, the add-on is switched
on with its trigger words; otherwise the style's own words do the job, as before. Your own can be added from a Hugging Face link.

    import style_addons as SA
    SA.CATALOG                      the built-in list: style -> dict(repo, trigger, weight, hint, note)
    SA.installed(style)             -> path of its file, or None
    SA.download(style, on_done)     in the background (needs the image engine's downloader)
    SA.lora_for(style)              -> (text added to the prompt, folder) or None: what styles.resolve hands the engine
    SA.add_own(style, repo_or_link, trigger, weight)   your own pick from Hugging Face

They're Z-Image Turbo add-ons: they don't fit Stable Diffusion 1.5 or FLUX.2 Klein, so they're only used when Z-Image paints.
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


def lora_for(style):
    """(text for the prompt, folder) when this style's add-on is here, else None"""
    e = entries().get(style)
    if not e or not installed(style): return None
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


def download(style, on_done=None):
    """fetch this style's add-on in the background; on_done(ok, message)"""
    import imaging
    e = entries().get(style)
    if not e: on_done and on_done(False, f"no add-on is listed for {style}"); return
    def work():
        try:
            name, size = _pick_file(e["repo"], e.get("hint", ""))
            dest = os.path.join(folder(), slug(style) + ".safetensors")
            url = f"https://huggingface.co/{e['repo']}/resolve/main/{name}"
            imaging._get(url, dest, f"the {style} add-on", max(size, 5e7) / 1e9)
            imaging._set(None, ""); on_done and on_done(True, f"the {style} add-on is ready — it switches on when Z-Image paints in {style}")
        except Exception as ex:
            imaging._set(None, ""); on_done and on_done(False, str(ex))
    threading.Thread(target=work, daemon=True, name="style add-on " + style).start()


def remove(style):
    p = installed(style)
    if p: os.remove(p)


def add_own(style, link, trigger="", weight=0.9):
    """your own pick from Hugging Face for a style (a built-in style name, or a new one): kept in your-addons.json"""
    repo = _repo_of(link); os.makedirs(folder(), exist_ok=True); own = _own()
    own[style.strip()] = dict(repo=repo, trigger=trigger.strip(), weight=float(weight), note=f"Your pick ({repo}).", own=True)
    with open(_own_file(), "w") as f: json.dump(own, f, indent=1)
    if installed(style): remove(style)                                    # (the old file was a different add-on)
    return repo


def forget_own(style):
    own = _own()
    if style in own:
        own.pop(style); remove(style)
        with open(_own_file(), "w") as f: json.dump(own, f, indent=1)
