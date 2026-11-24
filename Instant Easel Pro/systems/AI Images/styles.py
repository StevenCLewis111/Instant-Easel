"""
styles.py: the style models every image page offers - built-in ones (Realistic photo, Cartoon, Anime, Black & white...) and your own
from AI Training > Image Learning.

A built-in style needs no download: it's the right wording for each kind of picture model (research: Z-Image and FLUX.2 want
plain sentences and ignore "leave out" words; Stable Diffusion wants short comma tags plus things to leave out), so the same style
looks right whichever model paints it.

Your own image model (made in AI Training > Image Learning) works straight away, without training:
    - its style words (what it should look like) go into every request
    - with FLUX.2 Klein downloaded, up to 4 of its pictures go in as reference pictures, so the result follows their look
    - a trained add-on (a LoRA for Stable Diffusion 1.5) is used too when it has one
Training a LoRA on your PC needs a GPU training kit the app doesn't have yet; a LoRA trained elsewhere can be added in Image Learning.

    import styles
    styles.names()                       -> ["None", "Realistic photo", ..., "Your models: Cartoon"...]
    styles.resolve("Anime", "a cat", model="zimage")  -> dict(prompt, negative, refs, lora, model, note)
"""
import os, random

# name: (sentence for DiT models, tags for Stable Diffusion, things to leave out (SD), how an edit says it)
BUILT_IN = {
    "None": ("", "", "", ""),
    "Realistic photo": ("A realistic, high-resolution photograph with natural lighting, true-to-life colours and sharp focus.",
                        "photo, realistic, natural light, sharp focus, detailed, 35mm", "painting, drawing, cartoon, 3d render, plastic",
                        "a realistic photograph"),
    "Cinematic": ("A cinematic film still with dramatic lighting, shallow depth of field and rich colour grading.",
                  "cinematic film still, dramatic lighting, shallow depth of field, color graded, anamorphic", "flat lighting, cartoon",
                  "a cinematic film still with dramatic lighting"),
    "Portrait": ("A professional portrait photograph, soft studio light, the face in sharp focus, gently blurred background.",
                 "portrait photo, studio lighting, sharp face, bokeh background, 85mm", "deformed face, extra eyes, cartoon",
                 "a professional studio portrait"),
    "Black & white": ("A black and white photograph with strong contrast, deep shadows and fine grain. No colour at all.",
                      "black and white photo, monochrome, high contrast, film grain", "color, colorful, saturated",
                      "a black and white photograph with strong contrast"),
    "Vintage photo": ("A faded vintage photograph from the 1970s, warm tones, soft film grain and slightly washed-out colours.",
                      "vintage photo, 1970s, faded film, warm tones, film grain", "modern, digital, sharp",
                      "a faded 1970s vintage photograph"),
    "Cartoon": ("A clean cartoon illustration with bold outlines, bright flat colours and simple friendly shapes.",
                "cartoon illustration, bold outlines, flat bright colors, simple shapes", "photo, realistic, 3d, gritty",
                "a clean cartoon with bold outlines and flat bright colours"),
    "Anime": ("An anime illustration with clean line art, cel shading, expressive eyes and vivid colours.",
              "anime style, cel shading, clean line art, vivid colors, detailed eyes", "photo, realistic, 3d render, western cartoon",
              "an anime illustration with cel shading"),
    "Comic book": ("A comic book panel with heavy ink outlines, halftone dot shading and punchy colours.",
                   "comic book art, ink outlines, halftone shading, bold colors", "photo, realistic, blurry",
                   "a comic book panel with ink outlines and halftone shading"),
    "Storybook": ("A warm children's storybook illustration, soft gouache textures, gentle colours and a friendly mood.",
                  "children's book illustration, gouache, soft colors, whimsical, warm", "dark, scary, photo, realistic",
                  "a warm children's storybook illustration"),
    "Watercolor": ("A loose watercolour painting on textured paper, soft bleeding edges and transparent washes of colour.",
                   "watercolor painting, paper texture, soft edges, washes", "photo, sharp, digital, 3d",
                   "a loose watercolour painting"),
    "Oil painting": ("A classical oil painting on canvas with rich colour and thick, visible brush strokes.",
                     "oil painting, canvas texture, visible brush strokes, rich colors", "photo, digital, flat",
                     "a classical oil painting with visible brush strokes"),
    "Digital painting": ("A detailed digital painting, painterly brushwork, vivid colours and dramatic light.",
                         "digital painting, painterly, detailed, vivid colors, concept art", "photo, blurry, low detail",
                         "a detailed digital painting"),
    "Pencil sketch": ("A graphite pencil sketch on white paper, fine hatching and soft shading, no colour.",
                      "pencil sketch, graphite, hatching, white paper, monochrome", "color, photo, painting",
                      "a graphite pencil sketch"),
    "Line art / colouring page": ("Clean black line art on a plain white background, no shading or colour, like a colouring book page.",
                                  "line art, black and white, coloring book page, clean lines, no shading", "color, shading, gray, photo",
                                  "clean black line art like a colouring book page"),
    "3D render": ("A polished 3D render with soft global illumination, smooth materials and a clean studio backdrop.",
                  "3d render, octane, soft lighting, smooth materials, studio backdrop", "photo, drawing, flat, sketch",
                  "a polished 3D render"),
    "Pixel art": ("Retro 16-bit pixel art with a limited colour palette and crisp square pixels.",
                  "pixel art, 16-bit, retro game, limited palette, crisp pixels", "blurry, smooth, photo, realistic",
                  "retro 16-bit pixel art"),
    "Fantasy art": ("Epic fantasy art with magical glowing light, rich detail and a sense of wonder.",
                    "fantasy art, magical, glowing light, epic, highly detailed", "modern, mundane, photo",
                    "epic fantasy art with magical light"),
    "Neon / cyberpunk": ("A neon-lit cyberpunk scene at night, glowing pink and cyan signs reflecting on wet streets.",
                         "cyberpunk, neon lights, night, pink and cyan glow, wet streets", "daylight, rustic, pastel",
                         "a neon cyberpunk scene at night"),
    "Minimal / flat": ("A minimal flat vector illustration with simple geometric shapes, a few solid colours and lots of space.",
                       "flat vector illustration, minimal, geometric shapes, solid colors", "detailed, texture, photo, 3d",
                       "a minimal flat vector illustration"),
}
YOURS = "Your model: "

def _addon_styles():
    """styles you added an add-on for under a new name (Settings > Templates)"""
    try:
        import style_addons as SA; return [s for s in SA.entries() if s not in BUILT_IN]
    except Exception: return []

def names():
    """every style for a page's style list: the built-in ones, your own add-on styles, then your own image models"""
    out = list(BUILT_IN) + _addon_styles()
    try:
        import image_models as IM; out += [YOURS + n for n in IM.names()]
    except Exception: pass
    return out

def own_name(style): return style[len(YOURS):] if style and style.startswith(YOURS) else ""

def reference_pictures(name, k=4):
    """up to k of your model's pictures (its chosen ones first, else a spread across its labels), opened"""
    from PIL import Image
    import image_models as IM
    chosen = [p for p in IM.info(name).get("references", []) if os.path.exists(p)]
    if not chosen:
        d = IM.pictures_dir(name); per = []
        for lab in sorted(os.listdir(d)):
            fs = sorted(os.path.join(d, lab, f) for f in os.listdir(os.path.join(d, lab)) if f.lower().endswith(IM.EXT)) if os.path.isdir(os.path.join(d, lab)) else []
            if fs: per.append(fs)
        rnd = random.Random(name)
        while per and len(chosen) < k:                                          # one from each label in turn, so it isn't all one thing
            for fs in list(per):
                if len(chosen) >= k: break
                p = fs.pop(rnd.randrange(len(fs))); chosen.append(p)
                if not fs: per.remove(fs)
    out = []
    for p in chosen[:k]:
        try: out.append(Image.open(p).convert("RGB"))
        except Exception: pass
    return out

def resolve(style, prompt, model, editing=False, use_refs=True, allow_switch=True):
    """turn a request + style into what the engine needs for `model` ('zimage', 'klein', 'sd15'...).
    allow_switch: your own model may move the job to FLUX.2 Klein so its pictures guide the look (not on guide pages)
    editing: the request is an instruction to change a picture (Prompt to Edit...) -> the style is said as 'make it look like...'
    -> dict(prompt, negative (extra things to leave out), refs (reference pictures), lora ((text, folder) or None), model, note)"""
    import imaging
    dit = imaging.spec(model)["dit"]; prompt = (prompt or "").strip(); out = dict(prompt=prompt, negative="", refs=[], lora=None, model=model, note="")
    mine = own_name(style)
    if mine:
        import image_models as IM
        info = IM.info(mine); words = (info.get("style_words") or info.get("description") or "").strip()
        refs = reference_pictures(mine) if use_refs else []
        if refs and imaging.have("klein") and (model == "klein" or allow_switch):
            out.update(model="klein", refs=refs)
            lead = (f"Make it in the visual style of the {len(refs)} reference pictures" if editing
                    else f"In the visual style of the {len(refs)} reference pictures (their colours, look and technique)")
            out["prompt"] = f"{prompt}. {lead}" + (f": {words}." if words else ".")
            out["note"] = f"{mine}: using {len(refs)} of its pictures as references (FLUX.2 Klein)"
        else:
            out["prompt"] = f"{prompt}, {words}" if words else prompt
            bits = imaging.image_model_bits(mine, model)
            if bits[1]: out["lora"] = bits; out["note"] = f"{mine}: its trained add-on is on"
            elif refs and not imaging.have("klein"):
                out["note"] = f"{mine}: style words only — download FLUX.2 Klein (Settings > AI Models > Image edits) so its pictures guide the look"
        return out
    sentence, tags, leave, edit = BUILT_IN.get(style or "None", BUILT_IN["None"] if style not in _addon_styles() else ("", "", "", ""))
    if style and style != "None":                                              # an add-on for this style made for the model that's painting (style_addons)
        try:
            import style_addons as SA; bits = SA.lora_for(style, imaging.kind(model))
            if bits: out["lora"] = bits; out["note"] = f"{style}: its add-on is on"
        except Exception: pass
    if editing and edit: out["prompt"] = f"{prompt}. Make it look like {edit}." if prompt else f"Turn this picture into {edit}, keeping its subject and layout."
    elif dit and sentence: out["prompt"] = f"{prompt}. {sentence}" if prompt else sentence
    elif tags: out["prompt"] = f"{prompt}, {tags}" if prompt else tags
    if not dit: out["negative"] = leave
    return out
