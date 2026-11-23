"""
glossary.py: words and names the AI doesn't know, looked up once and remembered (my-library/glossary.json), so it learns them.

When a picture request or a chat question has a name or an unusual word in it (a character, a car model, a dish, a brand...), it's
looked up - Wikipedia for names and things, a dictionary for ordinary words - and the short definition goes in with the request,
so the text model writes about the right thing. Every lookup is kept, so the next time it's instant; and each one is also written
into the AI's library (AI Chat and AI Images), so it's part of what the AI knows from then on.

    import glossary
    glossary.lookup("Mustang")                   -> dict(term, text, source, url) or None
    glossary.lookup("Mustang", hint="Ford car")  (a hint picks the right page when a name means several things)
    glossary.for_text("a quokka eating cake")    -> [entry, ...] for the words in it it doesn't already know (up to 4)
    glossary.notes(entries)                      -> the lines that go in with a request
    glossary.teach(term, text)                   your own definition (wins over a looked-up one)
"""
import os, re, json, time, threading, urllib.parse, urllib.request
import paths

UA = "InstantEaselPro/1.0 (personal art app; glossary lookups)"
_lock = threading.Lock(); _cache = None

# the most common English words: these never need looking up (plus anything the AI's own library already explains)
COMMON = set("""a about above across after again against all almost alone along already also although always am among an and another any anyone
anything are around as ask at away back be beautiful because become been before behind being below best better between big black blue body
both bright brown but by can car cat child children city clean close cloud color colour colorful come could cute dark day dog done down draw
drawing each early earth eat eating either else end enough even evening ever every everything eye eyes face fall family far fast few field
find fire first fish flower flowers fly food for forest friend from front full funny garden get girl give glass go gold good great green
ground grow hair half hand happy hard has have he head her here high him his hold home horse house how huge i if in inside into is it its
just keep kind king kitchen lake land large last late leaf left less light like little long look lot love low make man many may me middle
might moon more morning most mother mountain mouth much must my near never new next nice night no not nothing now of off old on once one only
open or orange other our out outside over own paint painting park part people person picture pink place plant play portrait purple queen
quiet rain red right river road rock room round run same sea see shape she ship short should show side sign simple sit sitting sky small
smile snow so soft some something sometimes song soon space standing star still stone street strong summer sun sunny sunset table tall tea
than that the their them then there these they thing think this those through time tiny to today together too top tower town tree trees
under up us very wall want warm water way we wear well were what when where which while white who why wide will wind window winter with
woman wood world would yellow yes you young your cake birthday candle candles happy party photo photograph style cartoon anime realistic
detailed background front close-up wearing holding riding flying swimming running walking standing jumping looking smiling""".split())

def _more_common():
    """the 10,000 commonest English words (common_words.txt beside this file): they don't need looking up"""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "common_words.txt"), encoding="utf-8") as f:
            return {w.strip() for w in f if w.strip()}
    except Exception:
        try:
            with open(os.path.join(paths.APP, "common_words.txt"), encoding="utf-8") as f: return {w.strip() for w in f if w.strip()}
        except Exception: return set()
COMMON |= _more_common()

STOP_CAPS = {"I", "A", "An", "The", "In", "On", "At", "Of", "And", "Make", "Draw", "Paint", "Show", "Create", "Give", "Please"}


def _file(): return paths.ai("my-library", "glossary.json")


def _load():
    global _cache
    if _cache is None:
        try:
            with open(_file(), encoding="utf-8") as f: _cache = json.load(f)
        except Exception: _cache = {}
    return _cache


def _save():
    os.makedirs(os.path.dirname(_file()), exist_ok=True)
    tmp = _file() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(_load(), f, indent=1, ensure_ascii=False)
    os.replace(tmp, _file())


def _key(term): return re.sub(r"\s+", " ", term.strip().lower())


def _get(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read().decode("utf-8", "replace"))


def _wikipedia(term, hint=""):
    """Wikipedia's short summary of the best page for term (hint: what kind of thing, to pick between pages with the same name)"""
    q = f"{term} {hint}".strip()
    hits = _get("https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=5&srsearch=" + urllib.parse.quote(q))
    titles = [h["title"] for h in hits.get("query", {}).get("search", [])]
    tl = term.lower()
    titles.sort(key=lambda t: (tl not in t.lower(), len(t)))                      # (its own page first, not a list it's mentioned in)
    for t in titles[:3]:
        s = _get("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(t.replace(" ", "_")))
        if s.get("type") == "disambiguation" or not s.get("extract"): continue
        text = s["extract"].strip()
        return dict(term=term, text=_short(text), source="Wikipedia: " + s.get("title", t),
                    url=s.get("content_urls", {}).get("desktop", {}).get("page", ""))
    return None


def _dictionary(word):
    d = _get("https://api.dictionaryapi.dev/api/v2/entries/en/" + urllib.parse.quote(word.lower()))
    if not isinstance(d, list) or not d: return None
    defs = []
    for m in d[0].get("meanings", [])[:2]:
        for x in m.get("definitions", [])[:1]: defs.append(f"({m.get('partOfSpeech', '')}) {x.get('definition', '')}")
    return dict(term=word, text=_short(" ".join(defs)), source="Dictionary", url="") if defs else None


def _short(text, n=420):
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= n: return text
    cut = text[:n]; return cut[:cut.rfind(". ") + 1] if ". " in cut else cut + "…"


def known(term):
    e = _load().get(_key(term)); return e if e and e.get("text") else None


def lookup(term, hint="", refresh=False):
    """the definition of term: remembered, else looked up (Wikipedia, then a dictionary) and remembered. None if nothing was found
    (that's remembered for a week too, so it isn't asked again and again)"""
    term = term.strip()
    if not term: return None
    k = _key(term + (" | " + hint if hint else ""))
    with _lock: e = _load().get(k) or (None if hint else _load().get(_key(term)))
    if e and not refresh:
        if e.get("text"): return e
        if time.time() - e.get("when", 0) < 7 * 86400: return None
    found = None
    try:
        found = _wikipedia(term, hint) if (hint or " " in term or term[:1].isupper()) else None
        if not found and " " not in term: found = _dictionary(term)
        if not found and not hint and not term[:1].isupper(): found = _wikipedia(term)
    except Exception: found = None                                                # (offline: just carry on without it)
    entry = dict(found or dict(term=term, text=""), when=time.time(), hint=hint)
    with _lock: _load()[k] = entry; _save()
    if found: _to_library(entry)
    return found


def teach(term, text):
    """your own definition: used instead of any looked-up one"""
    entry = dict(term=term.strip(), text=text.strip(), source="You", url="", when=time.time(), hint="")
    with _lock: _load()[_key(term)] = entry; _save()
    _to_library(entry); return entry


def forget(term):
    with _lock:
        for k in [k for k in _load() if k == _key(term) or k.startswith(_key(term) + " | ")]: _load().pop(k)
        _save()


def entries():
    return sorted((e for e in _load().values() if e.get("text")), key=lambda e: e["term"].lower())


def _to_library(e):
    """into the AI's library, so it knows it from now on (the library is what it reads before answering)"""
    try:
        import brain
        for tab in ("AI Chat", "AI Images"):
            d = os.path.join(brain.library_dir(tab), "glossary"); os.makedirs(d, exist_ok=True)
            name = re.sub(r"[^\w-]+", "_", e["term"]).strip("_")[:60] or "term"
            with open(os.path.join(d, name + ".txt"), "w", encoding="utf-8") as f:
                f.write(f"{e['term']}: {e['text']}\n(Source: {e.get('source', '')} {e.get('url', '')})\n")
    except Exception: pass


def candidates(text):
    """the names and unusual words in text that might need looking up: Capitalised names (one to three words together), and words
    that aren't common English"""
    out = []
    for m in re.finditer(r"(?<![\w'])([A-Z][\w'\-é]+(?:\s+[A-Z][\w'\-é]+){0,2})", text):
        t = m.group(1)
        if t not in STOP_CAPS and t.lower() not in COMMON: out.append(t)
    for w in re.findall(r"[a-zA-Zé][a-zA-Zé'\-]{3,}", text):
        lw = w.lower().strip("'-")
        if lw in COMMON or any(lw in c.lower().split() for c in out): continue
        if lw.endswith("s") and lw[:-1] in COMMON: continue
        if lw.endswith("ing") and (lw[:-3] in COMMON or lw[:-3] + "e" in COMMON): continue
        if lw.endswith("ed") and (lw[:-2] in COMMON or lw[:-1] in COMMON): continue
        out.append(w)
    seen, res = set(), []
    for t in out:
        if t.lower() not in seen: seen.add(t.lower()); res.append(t)
    return res


def for_text(text, limit=4, look_up=True):
    """definitions for the names and unusual words in text: the ones already known straight away; up to `limit` new ones looked up"""
    got = []
    for t in candidates(text):
        e = known(t) or (lookup(t) if look_up and len(got) < limit else None)
        if e: got.append(e)
        if len(got) >= limit: break
    return got


def notes(found):
    """the lines that go in with a request so the text model knows what these words mean"""
    return "\n".join(f"- {e['term']}: {e['text']}" for e in found)
