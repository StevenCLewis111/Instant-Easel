"""
language.py: understands what you ask for in plain English and turns it into a painting.

    from language import understand
    opts, understood, unknown = understand("two people sitting on a hill at sunset, tall mountains, lots of clouds, no rocks")

It knows the vocabulary of painting (synonyms, numbers, negatives like "no rocks", positions like "sun on the left",
amounts like "lots of clouds", sizes, poses, colour moods, and captions in quotes). It learns new words: teach("golden hour",
{"time": "sunset", "sun_height": "low"}) and they're saved to vocab.json next to the app.
"""
import json, os, re

NUMBERS = {"no": 0, "zero": 0, "none": 0, "a": 1, "an": 1, "one": 1, "single": 1, "lone": 1, "solitary": 1, "two": 2, "pair": 2,
           "couple": 2, "both": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "few": 3, "several": 4,
           "many": 6, "lots": 6}

# phrase -> settings it implies. Longer phrases are matched first.
BUILTIN = {
    # time of day
    "sunset": {"time": "sunset"}, "sundown": {"time": "sunset"}, "dusk": {"time": "sunset"}, "evening": {"time": "sunset"},
    "golden hour": {"time": "sunset", "tint": "golden"}, "twilight": {"time": "sunset", "tint": "cool"}, "sunrise": {"time": "sunset", "tint": "pink"},
    "dawn": {"time": "sunset", "tint": "pink"}, "morning": {"time": "sunset", "tint": "pink"},
    "night": {"time": "night"}, "nighttime": {"time": "night"}, "midnight": {"time": "night"}, "moonlight": {"time": "night"},
    "moonlit": {"time": "night"}, "starry": {"time": "night"}, "stars": {"time": "night"}, "moon": {"time": "night"},
    # sky / clouds
    "clear sky": {"clouds": "few"}, "clear": {"clouds": "few"}, "cloudless": {"clouds": "few"}, "few clouds": {"clouds": "few"},
    "some clouds": {"clouds": "normal"}, "clouds": {"clouds": "normal"}, "cloudy": {"clouds": "many"}, "lots of clouds": {"clouds": "many"},
    "many clouds": {"clouds": "many"}, "dramatic sky": {"clouds": "many", "tint": "fiery"}, "overcast": {"clouds": "many"},
    "stormy": {"clouds": "many", "tint": "cool"}, "storm": {"clouds": "many", "tint": "cool"},
    # sun position / height
    "sun on the left": {"sun_x": 0.25}, "sun left": {"sun_x": 0.25}, "sun on the right": {"sun_x": 0.75}, "sun right": {"sun_x": 0.75},
    "sun in the middle": {"sun_x": 0.5}, "sun in the center": {"sun_x": 0.5}, "sun in the centre": {"sun_x": 0.5}, "centered sun": {"sun_x": 0.5},
    # mountains
    "mountains": {"mountains": True}, "mountain": {"mountains": True}, "peaks": {"mountains": True}, "range": {"mountains": True},
    "alps": {"mountains": True, "height": 0.9}, "tall mountains": {"height": 0.9}, "high mountains": {"height": 0.9},
    "huge mountains": {"height": 1.0}, "towering": {"height": 1.0}, "jagged": {"height": 0.85, "peaks": 6},
    "small mountains": {"height": 0.3}, "low mountains": {"height": 0.3}, "rolling hills": {"height": 0.2, "peaks": 5},
    "hills": {"height": 0.25}, "no mountains": {"mountains": False}, "flat": {"mountains": False},
    "canyon": {"canyon": True}, "valley": {"canyon": True}, "gorge": {"canyon": True},
    # ground
    "rocks": {"rocks": True}, "rocky": {"rocks": True}, "boulders": {"rocks": True}, "stones": {"rocks": True},
    "grass": {"grass": True}, "grassy": {"grass": True}, "meadow": {"grass": True}, "field": {"grass": True},
    "hill": {}, "hilltop": {}, "rise": {}, "summit": {}, "ridge": {},
    # people
    "person": {"figures": 1}, "people": {"figures": 2}, "man": {"figures": 1}, "woman": {"figures": 1}, "figure": {"figures": 1},
    "figures": {"figures": 2}, "friends": {"figures": 2}, "father and son": {"figures": 2}, "mother and daughter": {"figures": 2},
    "couple": {"figures": 2}, "kael and oren": {"figures": 2}, "nobody": {"figures": 0}, "no people": {"figures": 0}, "empty": {"figures": 0},
    "alone": {"figures": 1}, "sitting": {"pose": "seated"}, "seated": {"pose": "seated"}, "sit": {"pose": "seated"},
    "standing": {"pose": "standing"}, "stand": {"pose": "standing"}, "watching": {}, "looking": {},
    # colour mood
    "warm": {"tint": "golden"}, "golden": {"tint": "golden"}, "fiery": {"tint": "fiery"}, "red": {"tint": "fiery"}, "orange": {"tint": "golden"},
    "pink": {"tint": "pink"}, "purple": {"tint": "cool"}, "violet": {"tint": "cool"}, "cool": {"tint": "cool"}, "blue": {"tint": "cool"},
    "calm": {"clouds": "few"}, "peaceful": {"clouds": "few"}, "moody": {"clouds": "many", "tint": "cool"},
    # filler words it knows (so they aren't reported as unknown)
    "on": {}, "the": {}, "of": {}, "with": {}, "and": {}, "at": {}, "in": {}, "a": {}, "an": {}, "under": {}, "over": {}, "behind": {},
    "sky": {}, "landscape": {}, "scene": {}, "painting": {}, "picture": {}, "image": {}, "paint": {}, "draw": {}, "make": {},
    "show": {}, "me": {}, "please": {}, "some": {}, "big": {}, "beautiful": {}, "lots": {}, "of": {}, "very": {}, "top": {},
    "from": {}, "to": {}, "into": {}, "near": {}, "front": {}, "far": {}, "distance": {}, "background": {}, "foreground": {}, "two": {},
    "together": {}, "next": {}, "their": {}, "his": {}, "her": {}, "is": {}, "are": {}, "it": {}, "that": {}, "this": {}, "sun": {},
    "light": {}, "glow": {}, "glowing": {}, "caption": {}, "captioned": {}, "titled": {}, "saying": {}, "text": {}, "words": {},
}
NEGATORS = ("no", "without", "not", "zero", "none")
# ---- extended vocabulary (language skills) ----
BUILTIN.update({
    # people
    "lonely": {"figures": 1}, "lone": {"figures": 1}, "solitary": {"figures": 1}, "single person": {"figures": 1},
    "wanderer": {"figures": 1, "pose": "standing"}, "traveler": {"figures": 1, "pose": "standing"}, "traveller": {"figures": 1, "pose": "standing"},
    "hiker": {"figures": 1, "pose": "standing"}, "explorer": {"figures": 1, "pose": "standing"}, "climber": {"figures": 1, "pose": "standing"},
    "child": {"figures": 1}, "kid": {"figures": 1}, "boy": {"figures": 1}, "girl": {"figures": 1}, "old man": {"figures": 1}, "old woman": {"figures": 1},
    "family": {"figures": 2}, "group": {"figures": 2}, "crowd": {"figures": 2}, "siblings": {"figures": 2}, "brothers": {"figures": 2},
    "sisters": {"figures": 2}, "lovers": {"figures": 2}, "companions": {"figures": 2}, "two friends": {"figures": 2},
    "resting": {"pose": "seated"}, "meditating": {"pose": "seated"}, "relaxing": {"pose": "seated"}, "waiting": {"pose": "seated"},
    "walking": {"pose": "standing"}, "hiking": {"pose": "standing"}, "gazing": {}, "staring": {}, "admiring": {}, "contemplating": {},
    # landforms
    "snowy peaks": {"height": 0.95}, "snow capped": {"height": 0.95}, "snowcapped": {"height": 0.95}, "cliffs": {"height": 0.8, "peaks": 5},
    "highlands": {"height": 0.45}, "foothills": {"height": 0.3}, "plains": {"mountains": False}, "prairie": {"mountains": False},
    "steppe": {"mountains": False}, "mesa": {"height": 0.35, "peaks": 3}, "volcano": {"height": 0.9, "peaks": 3},
    "massive": {"height": 1.0}, "gentle": {"height": 0.25}, "distant mountains": {"height": 0.4}, "far mountains": {"height": 0.4},
    "ravine": {"canyon": True}, "pass": {"canyon": True}, "dale": {"canyon": True}, "glen": {"canyon": True},
    "pebbles": {"rocks": True}, "rubble": {"rocks": True}, "stone": {"rocks": True}, "crag": {"rocks": True}, "crags": {"rocks": True},
    "grassland": {"grass": True}, "wildflowers": {"grass": True}, "tall grass": {"grass": True}, "weeds": {"grass": True}, "bare": {"grass": False},
    # light, time, sky
    "afterglow": {"time": "sunset", "tint": "pink"}, "late afternoon": {"time": "sunset", "tint": "golden"}, "evening glow": {"time": "sunset", "tint": "golden"},
    "first light": {"time": "sunset", "tint": "pink"}, "daybreak": {"time": "sunset", "tint": "pink"}, "blue hour": {"time": "night", "clouds": "few"},
    "full moon": {"time": "night"}, "crescent": {"time": "night"}, "milky way": {"time": "night", "clouds": "few"}, "night sky": {"time": "night"},
    "dark": {"time": "night"}, "darkness": {"time": "night"}, "nocturnal": {"time": "night"},
    "thunderstorm": {"clouds": "many", "tint": "cool"}, "tempest": {"clouds": "many", "tint": "cool"}, "gloomy": {"clouds": "many", "tint": "cool"},
    "billowing": {"clouds": "many"}, "fluffy clouds": {"clouds": "normal"}, "wispy": {"clouds": "few"}, "scattered clouds": {"clouds": "normal"},
    "sunny": {"clouds": "few", "tint": "golden"}, "bright": {"tint": "golden"}, "dim": {"tint": "cool"},
    # colour and mood
    "crimson": {"tint": "fiery"}, "scarlet": {"tint": "fiery"}, "blazing": {"tint": "fiery"}, "burning": {"tint": "fiery"}, "amber": {"tint": "golden"},
    "honey": {"tint": "golden"}, "yellow": {"tint": "golden"}, "rose": {"tint": "pink"}, "pastel": {"tint": "pink"}, "magenta": {"tint": "pink"},
    "lavender": {"tint": "cool"}, "indigo": {"tint": "cool"}, "teal": {"tint": "cool"}, "icy": {"tint": "cool"}, "cold": {"tint": "cool"},
    "melancholy": {"tint": "cool", "clouds": "many"}, "sad": {"tint": "cool"}, "hopeful": {"tint": "golden"}, "joyful": {"tint": "golden", "clouds": "few"},
    "serene": {"clouds": "few"}, "tranquil": {"clouds": "few"}, "quiet": {"clouds": "few"}, "dramatic": {"clouds": "many", "tint": "fiery"},
    "epic": {"clouds": "many", "height": 0.95}, "majestic": {"height": 0.9}, "ominous": {"clouds": "many", "tint": "cool"},
    "nostalgic": {"tint": "golden"}, "dreamy": {"tint": "pink"}, "mystical": {"tint": "cool"}, "magical": {"tint": "pink"},
    # positions
    "sun low on the left": {"sun_x": 0.25}, "sun low on the right": {"sun_x": 0.75}, "left": {}, "right": {}, "middle": {}, "center": {}, "centre": {},
    # more filler words it knows
    "lonely": {"figures": 1}, "way": {}, "edge": {}, "end": {}, "day": {}, "world": {}, "while": {}, "as": {}, "by": {}, "up": {}, "down": {},
    "across": {}, "toward": {}, "towards": {}, "above": {}, "below": {}, "beneath": {}, "around": {}, "out": {}, "one": {}, "old": {}, "small": {},
    "tiny": {}, "huge": {}, "vast": {}, "wide": {}, "open": {}, "long": {}, "high": {}, "low": {}, "deep": {}, "soft": {}, "warmly": {},
    "colors": {}, "colours": {}, "style": {}, "oil": {}, "painted": {}, "artwork": {}, "art": {}, "view": {}, "vista": {}, "horizon": {},
    "silhouette": {}, "silhouettes": {}, "shadow": {}, "shadows": {}, "lit": {}, "sunlight": {}, "sunlit": {}, "rays": {}, "beams": {}, "who": {},
})

BUILTIN.update({   # mediums for image to image
    "oil": {"medium": "oil"}, "oil painting": {"medium": "oil"}, "oils": {"medium": "oil"}, "impasto": {"medium": "oil"}, "painterly": {"medium": "oil"},
    "watercolor": {"medium": "watercolor"}, "watercolour": {"medium": "watercolor"}, "watercolors": {"medium": "watercolor"}, "wash": {"medium": "watercolor"},
    "pastel": {"medium": "pastel"}, "pastels": {"medium": "pastel"}, "chalk": {"medium": "pastel"}, "crayon": {"medium": "pastel"},
    "ink": {"medium": "ink sketch"}, "sketch": {"medium": "ink sketch"}, "ink sketch": {"medium": "ink sketch"}, "pencil": {"medium": "ink sketch"},
    "pencil sketch": {"medium": "ink sketch"}, "drawing": {"medium": "ink sketch"}, "line art": {"medium": "ink sketch"}, "charcoal": {"medium": "ink sketch"},
    "turn": {}, "into": {}, "make": {}, "it": {}, "like": {}, "as": {}, "photo": {}, "my": {},
})

BUILTIN.update({   # art styles
    "painterly": {"medium": "Painterly"}, "realism": {"medium": "Realism"}, "realistic": {"medium": "Realism"}, "photorealistic": {"medium": "Realism"},
    "oil painting": {"medium": "Oil Painting"}, "oil": {"medium": "Oil Painting"}, "watercolor": {"medium": "Watercolor"}, "watercolour": {"medium": "Watercolor"},
    "pastel": {"medium": "Pastel"}, "pencil": {"medium": "Pencil Sketch"}, "sketch": {"medium": "Pencil Sketch"}, "pencil sketch": {"medium": "Pencil Sketch"},
    "ink sketch": {"medium": "Pencil Sketch"}, "charcoal": {"medium": "Pencil Sketch"}, "drawing": {"medium": "Pencil Sketch"},
    "black and white": {"medium": "Black and White"}, "monochrome": {"medium": "Black and White"}, "b&w": {"medium": "Black and White"}, "noir": {"medium": "Black and White"},
    "cartoon": {"medium": "Cartoon"}, "cartoony": {"medium": "Cartoon"}, "toon": {"medium": "Cartoon"},
    "anime": {"medium": "Anime"}, "manga": {"medium": "Anime"}, "ghibli": {"medium": "Anime"}, "cel shaded": {"medium": "Anime"},
    "comic": {"medium": "Comic Book"}, "comic book": {"medium": "Comic Book"}, "graphic novel": {"medium": "Comic Book"},
    "pop art": {"medium": "Pop Art"}, "warhol": {"medium": "Pop Art"}, "lichtenstein": {"medium": "Pop Art"},
    "street art": {"medium": "Street Art"}, "graffiti": {"medium": "Street Art"}, "mural": {"medium": "Street Art"}, "banksy": {"medium": "Street Art"},
    "pixel art": {"medium": "Pixel Art"}, "pixel": {"medium": "Pixel Art"}, "8 bit": {"medium": "Pixel Art"}, "8bit": {"medium": "Pixel Art"}, "retro game": {"medium": "Pixel Art"},
    "abstract": {"medium": "Abstract"}, "kandinsky": {"medium": "Abstract"},
    "impressionist": {"medium": "Impressionist"}, "impressionism": {"medium": "Impressionist"}, "monet": {"medium": "Impressionist"},
    "stained glass": {"medium": "Stained Glass"}, "woodblock": {"medium": "Woodblock Print"}, "woodblock print": {"medium": "Woodblock Print"},
    "ukiyo e": {"medium": "Woodblock Print"}, "neon": {"medium": "Neon"}, "synthwave": {"medium": "Neon"}, "vaporwave": {"medium": "Neon"}, "cyberpunk": {"medium": "Neon"},
    "low poly": {"medium": "Low Poly"}, "lowpoly": {"medium": "Low Poly"}, "polygon": {"medium": "Low Poly"}, "style": {}, "styled": {},
})

def _stem(w):
    for suf in ("ing", "es", "s", "y", "ed"):
        if w.endswith(suf) and len(w) - len(suf) >= 3: return w[: -len(suf)]
    return w


def _vocab_path(folder=None):
    import paths
    if not folder or os.path.abspath(folder) == os.path.abspath(paths.HOME): return paths.json_file("vocab.json")   # the app's own words: .json/
    return os.path.join(folder, "vocab.json")                                                                     # a model's words: in its folder

def load_vocab(folder=None, model_folder=None):
    v = dict(BUILTIN); p = _vocab_path(folder)
    if os.path.exists(p):
        try: v.update(json.load(open(p)))
        except Exception: pass
    if model_folder:                                                      # a model's own words, on top of the Core's
        mp = os.path.join(model_folder, "vocab.json")
        if os.path.exists(mp):
            try: v.update(json.load(open(mp)))
            except Exception: pass
    return v

def teach(phrase, meaning, folder=None):
    """teach a word or phrase: teach('golden hour', {'time': 'sunset', 'tint': 'golden'})"""
    p = _vocab_path(folder); learned = json.load(open(p)) if os.path.exists(p) else {}
    learned[phrase.lower().strip()] = meaning; json.dump(learned, open(p, "w"), indent=1)

def taught_words(folder=None):
    p = _vocab_path(folder); return json.load(open(p)) if os.path.exists(p) else {}

def understand(text, folder=None, model_folder=None):
    """-> (options for landscape.render, list of what it understood, list of words it doesn't know)"""
    vocab = load_vocab(folder, model_folder); opts = {}; understood = []; unknown = []; fixes = []
    m = re.search(r'["“](.+?)["”]', text)                                         # a caption in quotes
    if m: opts["caption"] = m.group(1); understood.append(f'caption: "{m.group(1)}"'); text = text.replace(m.group(0), " ")
    t = " " + re.sub(r"[^a-z0-9' ]", " ", text.lower()) + " "
    t = re.sub(r"\s+", " ", t)
    phrases = sorted(vocab, key=lambda s: -len(s))
    words = t.split(); i = 0; used = [False] * len(words)
    while i < len(words):
        matched = False
        for ph in phrases:
            pw = ph.split(); n = len(pw)
            if words[i:i + n] == pw:
                meaning = dict(vocab[ph]); neg = i > 0 and words[i - 1] in NEGATORS
                if neg:                                                            # "no rocks", "without grass", "not cloudy"
                    for k, v in list(meaning.items()):
                        if isinstance(v, bool): meaning[k] = not v
                        elif k == "figures": meaning[k] = 0
                        elif k == "clouds": meaning[k] = "few"
                    if meaning: understood.append(f"no {ph}")
                elif meaning: understood.append(ph)
                prev = words[i - 1] if i > 0 else ""
                if "figures" in meaning and not neg and prev in NUMBERS and prev not in NEGATORS \
                        and not (prev in ("a", "an") and meaning["figures"] >= 2):                      # "a couple" stays two
                    meaning["figures"] = max(0, min(NUMBERS[prev], 2)); understood[-1] = f"{prev} {ph}"
                for k, v in meaning.items():
                    if k == "figures" and "figures" in opts and not neg: opts[k] = max(opts[k], v)
                    else: opts[k] = v
                for k in range(i, i + n): used[k] = True
                if neg and i > 0: used[i - 1] = True
                i += n; matched = True; break
        if not matched:
            w = words[i]
            if w in NUMBERS or w in NEGATORS: used[i] = True
            elif len(w) > 3:                                                   # word forms and misspellings
                singles = [p for p in vocab if " " not in p and len(p) > 3]
                stem = _stem(w); cand = [p for p in singles if _stem(p) == stem]
                if not cand:
                    import difflib; cand = difflib.get_close_matches(w, singles, n=1, cutoff=0.82)
                if cand:
                    words[i] = cand[0]; fixes.append(f"{w} → {cand[0]}"); continue   # re-read it as the known word
            i += 1
    for w, u in zip(words, used):
        if not u and len(w) > 2 and w not in unknown: unknown.append(w)
    # sensible defaults the words imply
    if opts.get("time") == "night" and "clouds" not in opts: opts["clouds"] = "few"
    if opts.get("figures", 2) > 2: understood.append("(up to two figures can be painted for now)")
    if fixes: understood.append("read as: " + "; ".join(fixes))
    return opts, understood, unknown

if __name__ == "__main__":
    import sys; print(understand(" ".join(sys.argv[1:]) or "two people sitting on a hill at sunset, tall mountains, lots of clouds, no rocks"))
