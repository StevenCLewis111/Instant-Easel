"""
catalog.py: every model the app can download, best first, with what each needs - and what fits THIS PC (hardware.py).

Each AI area has a ladder of models. The app offers the best one that fits the PC ("best for your PC") and every one below it,
never one above it. A tab whose area has nothing that fits (AI Videos on a small graphics card) isn't shown at all.

    catalog.options("AI Images")      -> [entry, ...] that fit, best first (each with .fit = "card" | "card+ram" | "processor")
    catalog.best("AI Images")         -> the best entry that fits (or None)
    catalog.fits(entry)               -> "card" | "card+ram" | "processor" | None
    catalog.variant(entry)            -> the download that suits this PC best (e.g. the Q8 file on a big card, Q4 on a 6 GB card)
    catalog.can("AI Videos")          -> False when nothing fits (the tab is hidden)

An entry's "runs" says how it can run, in order of preference:
    dict(vram=8)                 fits fully on a graphics card with 8 GB (fast)
    dict(vram=6, ram=16)         on a 6 GB card with 16 GB PC memory: part of it waits in PC memory (slower)
    dict(ram=8)                  no suitable card: runs on the processor with 8 GB PC memory (slow)
"""
import hardware

FIT_WORDS = {"card": "runs fully on your graphics card (fast)",
             "card+ram": "runs on your graphics card with part of it in PC memory (slower)",
             "processor": "runs on the processor (slow)"}

# ---------------------------------------------------------------- the ladders (best first)
LADDERS = {
 "core": [
  dict(key="27b", label="Qwen3.5 27B", repo="bartowski/Qwen_Qwen3.5-27B-GGUF", size=16.7, layers=99, runs=[dict(vram=20)],
       variants=[(24, "Q5_K_M", 19.5), (0, "Q4_K_M", 16.7)],
       note="The smartest core model. Needs a 20 GB+ graphics card."),
  dict(key="9b", label="Qwen3.5 9B", repo="bartowski/Qwen_Qwen3.5-9B-GGUF", size=5.7, layers=24, runs=[dict(vram=8), dict(vram=6, ram=16)],
       variants=[(12, "Q8_0", 9.5), (0, "Q4_K_M", 5.7)],
       note="Smarter than 4B. On a 6 GB card part of it waits in PC memory, so answers come slower."),
  dict(key="4b", label="Qwen3.5 4B", repo="bartowski/Qwen_Qwen3.5-4B-GGUF", size=3.0, layers=99, runs=[dict(vram=4), dict(ram=8)],
       variants=[(8, "Q8_0", 4.5), (0, "Q4_K_M", 3.0)],
       note="Quick and good for everyday help; fits fully on a 4 GB+ card."),
  dict(key="2b", label="Qwen3.5 2B", repo="bartowski/Qwen_Qwen3.5-2B-GGUF", size=1.3, layers=99, runs=[dict(vram=2), dict(ram=4)],
       variants=[(4, "Q8_0", 2.1), (0, "Q4_K_M", 1.3)],
       note="Small and quick: for PCs without much memory. Simpler answers."),
 ],
 "AI Coding": [
  dict(key="coder14b", label="Qwen2.5 Coder 14B", repo="bartowski/Qwen2.5-Coder-14B-Instruct-GGUF", size=9.0, layers=99,
       runs=[dict(vram=12), dict(vram=8, ram=16)], variants=[(0, "Q4_K_M", 9.0)], note="The strongest coding model for a home PC."),
  dict(key="coder7b", label="Qwen2.5 Coder 7B", repo="bartowski/Qwen2.5-Coder-7B-Instruct-GGUF", size=4.7, layers=99,
       runs=[dict(vram=6), dict(vram=4, ram=16), dict(ram=16)], variants=[(10, "Q8_0", 8.1), (0, "Q4_K_M", 4.7)], note="Made for code."),
  dict(key="coder3b", label="Qwen2.5 Coder 3B", repo="bartowski/Qwen2.5-Coder-3B-Instruct-GGUF", size=1.9, layers=99,
       runs=[dict(vram=3), dict(ram=8)], variants=[(6, "Q8_0", 3.3), (0, "Q4_K_M", 1.9)], note="A small coding model for smaller PCs. Licence: non-commercial only (Qwen Research License) - fine for personal use, not for selling.",
       licence="non-commercial"),
 ],
 "AI Images": [
  dict(key="zimage", label="Z-Image Turbo", kind="zimage", size=8.0, runs=[dict(vram=10, ram=16), dict(vram=4, ram=16)],
       variants=[(12, "Q8_0", 11.0), (6, "Q4_K", 7.9), (0, "Q3_K", 6.6)],
       note="The best picture quality that fits a home PC (close to Flux). Paints at 1024 pixels in 8 steps. "
            "Your own image models (Cartoon, Fashion...) are trained for Stable Diffusion 1.5, so they don't switch on with it."),
  dict(key="klein", label="FLUX.2 Klein 4B", kind="klein", size=5.3, runs=[dict(vram=8, ram=16), dict(vram=4, ram=16), dict(ram=16)],
       variants=[(12, "Q8_0", 9.0), (0, "Q4_K", 5.3)],
       note="The editor: changes pictures from words and uses up to 4 reference pictures (people, things, style). Also paints, "
            "very fast (4 steps). Your own style models use it with their pictures."),
  dict(key="sdxl", label="Stable Diffusion XL", kind="sd", size=6.9, manual=True, runs=[dict(vram=8)],
       note="Sharper than 1.5. Add the model file with Add manually, or get it with Settings > Download Everything."),
  dict(key="sd15", label="Stable Diffusion 1.5", kind="sd", size=2.1, runs=[dict(vram=2), dict(ram=8)],
       note="Quick, small and the base your own image models (Cartoon, Fashion...) train on."),
 ],
 "Image edits": [
  dict(key="klein", label="FLUX.2 Klein 4B", kind="klein", size=5.3, runs=[dict(vram=8, ram=16), dict(vram=4, ram=16), dict(ram=16)],
       variants=[(12, "Q8_0", 9.0), (0, "Q4_K", 5.3)],
       note="The editor: changes pictures from words and uses up to 4 reference pictures (people, things, style). Also paints, "
            "very fast (4 steps). Your own style models use it with their pictures."),
 ],
 "AI Videos": [
  dict(key="wan22", label="Wan 2.2 5B", kind="video", size=10.0, runs=[dict(vram=16, ram=32), dict(vram=6, ram=24), dict(ram=32)],
       variants=[(16, "Q8_0", 12.8), (0, "Q4_K_M", 8.5)],
       note="The best free video model that fits a home PC. Fast on a 16 GB+ card; Slow on smaller cards (the model waits in PC memory)."),
 ],
}
TABS = {"AI Images": "AI Images", "Image edits": "Image edits", "AI Videos": "AI Videos", "AI Coding": "AI Coding", "AI Chat": "core", "core": "core"}

def ladder(area): return LADDERS.get(TABS.get(area, area), [])
def entry(area, key): return next((e for e in ladder(area) if e["key"] == key), None)

def fits(e, pc=None):
    """how this model would run on the PC: "card", "card+ram", "processor" or None (it doesn't fit)"""
    pc = pc or hardware.pc(); vram, ram = float(pc.get("vram_gb") or 0), float(pc.get("ram_gb") or 0)
    for r in e.get("runs", []):
        need_v, need_r = r.get("vram", 0), r.get("ram", 0)
        if need_v and vram >= need_v and ram >= need_r: return "card" if r is e["runs"][0] else "card+ram"
        if not need_v and ram >= need_r: return "processor"
    return None

def options(area, pc=None):
    """the models of an area that fit this PC, best first, each with its fit"""
    out = []
    for e in ladder(area):
        f = fits(e, pc)
        if f: out.append(dict(e, fit=f))
    return out

def best(area, pc=None, downloadable=True):
    for e in options(area, pc):
        if not (downloadable and e.get("manual")): return e
    return None

def can(area, pc=None): return bool(options(area, pc))

def variant(e, pc=None):
    """the download that suits this PC: (quant, size GB) - the highest quality whose card size this PC reaches"""
    pc = pc or hardware.pc(); vram = float(pc.get("vram_gb") or 0)
    for min_v, quant, size in e.get("variants", []):
        if vram >= min_v: return quant, size
    v = e.get("variants") or [(0, None, e.get("size", 0))]; return v[-1][1], v[-1][2]

def describe_fit(e): return FIT_WORDS.get(e.get("fit") or fits(e), "doesn't fit this PC")

def hidden_tabs(pc=None):
    """tabs (and pages) this PC can't use, so they aren't shown"""
    tabs, pages = set(), set()
    if not can("AI Videos", pc): tabs.add("AI Videos"); pages.add("Video Learning")
    return tabs, pages
