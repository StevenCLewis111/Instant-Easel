"""
learn.py: the engine learns a style from a library of images (any number).
For every image it measures: sky / mountain / ground colour roles, brushwork (stroke direction, length, texture),
value structure (light and dark, top to bottom), and cuts texture patches. It then combines them into a style profile.

    python3 learn.py my-library            # learns from every image in the folder -> my-library/profile.json
"""
import os, sys, json, glob
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import painter2

EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".avif", ".gif", ".tif", ".tiff")

def image_features(path):
    im = Image.open(path).convert("RGB"); small = np.asarray(im.resize((300, 450)), dtype=np.float32) / 255
    g = small.mean(2); gy, gx = np.gradient(g); mag = np.hypot(gx, gy); ang = np.arctan2(gy, gx) % np.pi
    strong = mag > 0.02
    orient = np.histogram(ang[strong], bins=12, range=(0, np.pi), weights=mag[strong])[0]
    orient = (orient / (orient.sum() + 1e-9)).tolist()
    f = dict(
        file=os.path.basename(path),
        sky=painter2.sky_roles(path), mountains=painter2.mountain_roles(path), ground=painter2.ground_roles(path),
        values=[float(g[int(450 * i / 6):int(450 * (i + 1) / 6)].mean()) for i in range(6)],
        texture=float(mag.mean()), detail=float((mag > 0.05).mean()), orientation=orient,
        mean=small.reshape(-1, 3).mean(0).tolist())
    for k in ("sky", "mountains", "ground"): f[k] = {r: [float(x) for x in v] for r, v in f[k].items()}
    return f

def cut_patches(path, outdir, n=3):
    """texture bank: sky from the top, rock from the middle, ground from the bottom (centre avoided: figures live there)"""
    im = Image.open(path).convert("RGB"); w, h = im.size; base = os.path.splitext(os.path.basename(path))[0]; out = []
    for band, (y0, y1) in (("sky", (0.0, 0.45)), ("rock", (0.45, 0.68)), ("ground", (0.8, 1.0))):
        for i, (x0, x1) in enumerate(((0.0, 0.35), (0.65, 1.0))[:n]):
            p = os.path.join(outdir, f"{band}-{base}-{i}.jpg")
            im.crop((int(w * x0), int(h * y0), int(w * x1), int(h * y1))).save(p, quality=88); out.append(p)
    return out

def _wavg(old, new, n_old, n_new):
    """blend learned numbers (lists, dicts of lists, or numbers) weighted by how many images each came from"""
    if old is None or n_old <= 0: return new
    if isinstance(new, dict): return {k: _wavg(old.get(k), v, n_old, n_new) for k, v in new.items()}
    o, n = np.asarray(old, dtype=np.float64), np.asarray(new, dtype=np.float64)
    if o.shape != n.shape: return new
    r = (o * n_old + n * n_new) / (n_old + n_new)
    return r.tolist() if isinstance(new, (list, tuple)) else float(r)

def _fingerprint(p):
    import hashlib; return hashlib.md5(open(p, "rb").read()).hexdigest()

def _discard(paths, keep):
    """after learning, the app's copies are deleted (the user's originals were never touched)"""
    if keep: return 0
    n = 0
    for p in paths:
        try: os.remove(p); n += 1
        except OSError: pass
    return n

def learn(folder, texture_bank=False, keep_images=False):
    """scene-level learning; cumulative: new images blend into what was learned before, then the images are deleted"""
    prev = load(folder) or {}; seen = set(prev.get("seen", []))
    imgs = sorted(p for p in glob.glob(os.path.join(folder, "*")) if p.lower().endswith(EXT))
    new, done = [], []
    for p in imgs:
        fp = _fingerprint(p)
        if fp in seen: done.append(p); continue                                  # already learned this picture
        try:
            new.append(image_features(p)); seen.add(fp); done.append(p)
            if texture_bank: os.makedirs(os.path.join(folder, "patches"), exist_ok=True); cut_patches(p, os.path.join(folder, "patches"))
        except Exception as e:
            print(f"  skipped {os.path.basename(p)}: {e}")
    if not new and not prev: raise SystemExit(f"no images in {folder}")
    if new:
        med = lambda key, role: [float(x) for x in np.median([f[key][role] for f in new], 0)]
        batch = dict(sky={r: med("sky", r) for r in new[0]["sky"]}, mountains={r: med("mountains", r) for r in new[0]["mountains"]},
                     ground={r: med("ground", r) for r in new[0]["ground"]}, values=np.median([f["values"] for f in new], 0).tolist(),
                     texture=float(np.median([f["texture"] for f in new])), detail=float(np.median([f["detail"] for f in new])),
                     orientation=np.mean([f["orientation"] for f in new], 0).tolist())
        n_old = int(prev.get("images", 0)); profile = {k: _wavg(prev.get(k), v, n_old, len(new)) for k, v in batch.items()}
        profile.update(images=n_old + len(new), per_image=prev.get("per_image", []) + new, seen=sorted(seen),
                       subjects=prev.get("subjects", {}), images_kept=bool(keep_images))
        json.dump(profile, open(os.path.join(folder, "profile.json"), "w"), indent=1)
    else: profile = prev
    gone = _discard(done, keep_images)
    print(f"learned {len(new)} new images (total {profile.get('images', 0)}); {gone} library copies deleted")
    return profile

def load(folder):
    p = os.path.join(folder, "profile.json")
    return json.load(open(p)) if os.path.exists(p) else None

def closest(profile, folder, image):
    """the library image closest in mood, or None once images have been deleted after learning (callers fall back)"""
    if not any(os.path.exists(os.path.join(folder, f.get("file", ""))) for f in (profile or {}).get("per_image", [])): return None
    return _closest(profile, folder, image)

def _closest(profile, folder, image):
    """the library image whose overall colour is nearest the picture being painted (used as its style reference)"""
    m = np.asarray(image.convert("RGB").resize((60, 90)), dtype=np.float32).reshape(-1, 3).mean(0) / 255
    pool = [f for f in profile["per_image"] if os.path.exists(os.path.join(folder, f.get("file", "")))]
    best = min(pool, key=lambda f: float(((np.array(f["mean"]) - m) ** 2).sum()))
    return os.path.join(folder, best["file"])

if __name__ == "__main__":
    learn(sys.argv[1] if len(sys.argv) > 1 else __import__("paths").data("my-library"))

# ---------------- labelled learning: guess what an image shows, then learn that subject from it ----------------
LABELS = ("sky", "mountains", "rock", "grass", "people", "scene")

def image_stats(path):
    im = Image.open(path).convert("RGB"); a = np.asarray(im.resize((200, 200)), dtype=np.float32) / 255
    import colorsys
    g = a.mean(2); gy, gx = np.gradient(g); mag = np.hypot(gx, gy); ang = np.abs(np.arctan2(gy, gx))
    mx, mn = a.max(2), a.min(2); sat = np.where(mx > 0, (mx - mn) / (mx + 1e-6), 0)
    strong = mag > 0.03
    vertical_strokes = float(((np.abs(ang - 0) < 0.45) | (np.abs(ang - np.pi) < 0.45))[strong].mean()) if strong.any() else 0   # gradient across x = upright edges
    r, gg, b = [float(a[..., i].mean()) for i in range(3)]
    return dict(
        texture=float(mag.mean()), edges=float(strong.mean()), vertical=vertical_strokes, sat=float(sat.mean()),
        green=gg - (r + b) / 2, blue=b - (r + gg) / 2, warm=r - b,
        top_bottom=float(g[:60].mean() - g[-60:].mean()),           # skies are lighter at the top than the bottom of a landscape
        dark=float((g < 0.12).mean()), light=float((g > 0.88).mean()), spread=float(g.std()))

STAT_KEYS = ("texture", "edges", "vertical", "sat", "green", "blue", "warm", "top_bottom", "dark", "light", "spread")
STAT_SCALE = dict(texture=0.05, edges=0.15, vertical=0.3, sat=0.2, green=0.1, blue=0.1, warm=0.1, top_bottom=0.15, dark=0.15, light=0.15, spread=0.1)

def stat_vector(s): return [float(s[k]) for k in STAT_KEYS]

def guess_label(path):
    """simple, explainable guesses from colour and texture, improved by the Core's memory of your corrections"""
    s = image_stats(path); score = {}
    try:
        import models
        best, label = 1e9, None
        for c in models.corrections():                                     # closest picture you've corrected before (measurements only)
            d = sum(abs(a - b) / STAT_SCALE[k] for k, a, b in zip(STAT_KEYS, stat_vector(s), c["v"]))
            if d < best: best, label = d, c["label"]
        if label and best < 1.2: return label, "sure", s
    except Exception: pass
    score["people"] = 2.5 * (s["dark"] > 0.12) + 2.5 * (s["light"] > 0.25) + 2 * (s["sat"] < 0.12) - 2 * s["texture"] * 10 \
                      + 4 * (s["light"] + s["dark"] > 0.45)                       # silhouettes: pure dark on pure light
    score["grass"] = 3 * (s["green"] > 0.05) + (2 * s["vertical"] + 1.5 * (s["edges"] > 0.25)) * (s["green"] > 0.0) + 1 * (s["sat"] > 0.3) \
                     - 3 * (s["green"] <= -0.01)                                 # upright strokes only count when there's green
    score["rock"] = 2.5 * (s["sat"] < 0.3) + 2.5 * (s["edges"] > 0.3) + 1.5 * (s["texture"] > 0.06) - 2 * (s["green"] > 0.05) - 1.5 * (s["light"] > 0.25)
    score["sky"] = 2.5 * (s["edges"] < 0.15) + 1.5 * (s["texture"] < 0.03) + 1 * (abs(s["blue"]) > 0.05 or s["warm"] > 0.1) + 1 * (s["sat"] > 0.25) \
                   + 1.5 * (s["sat"] > 0.3 and (s["blue"] > 0.02 or s["warm"] > 0.15))
    score["mountains"] = 2 * (s["top_bottom"] > 0.08) + 1.5 * (0.12 < s["edges"] < 0.35) + 1 * (s["blue"] > 0.03)
    score["scene"] = 1.5 * (s["top_bottom"] > 0.05) + 1 * (0.1 < s["edges"] < 0.3)
    best = max(score, key=score.get); ranked = sorted(score.values(), reverse=True)
    confidence = "sure" if ranked[0] - ranked[1] > 1.5 else "unsure"
    return best, confidence, s

def learn_subject(label, paths):
    """what each subject teaches the engine"""
    if label in ("sky",):
        return {"roles": {k: [float(x) for x in v] for k, v in _median_roles([painter2.sky_roles(p) for p in paths]).items()}}
    if label in ("mountains",):
        return {"roles": {k: [float(x) for x in v] for k, v in _median_roles([painter2.mountain_roles(p) for p in paths]).items()}}
    stats = [image_stats(p) for p in paths]
    pal = np.median([painter2.kmeans_colors(p, (0, 0, 1, 1), k=6) for p in paths], 0)
    pal = sorted(pal.tolist(), key=lambda c: c[0] * .3 + c[1] * .59 + c[2] * .11)
    out = {"palette": pal, "texture": float(np.median([s["texture"] for s in stats])), "edges": float(np.median([s["edges"] for s in stats]))}
    if label == "grass": out["upright"] = float(np.median([s["vertical"] for s in stats]))
    if label == "rock": out["crack_density"] = float(np.median([s["dark"] for s in stats]))
    return out

def _median_roles(list_of_roles):
    return {k: np.median([r[k] for r in list_of_roles], 0) for k in list_of_roles[0]}

def _unique(paths):
    """deduplicate by file fingerprint: an image repeated in the library is counted once"""
    import hashlib; seen, out = set(), []
    for p in paths:
        h = hashlib.md5(open(p, "rb").read()).hexdigest()
        if h not in seen: seen.add(h); out.append(p)
    return out

def learn_labelled(folder, keep_images=False):
    """folder/<label>/images -> profile.json, one section per subject. Cumulative: each subject blends new images into what
    it learned before (weighted by image count). Pictures already learned are recognised by fingerprint. Afterwards the
    library copies are deleted unless keep_images (the user's originals are never touched). A dated copy goes to history/."""
    prof = load(folder) or {}; prof.setdefault("subjects", {}); seen = set(prof.get("seen", [])); report = {}
    for label in LABELS:
        if label == "scene": continue
        sub = os.path.join(folder, label)
        paths = sorted(p for p in glob.glob(os.path.join(sub, "*")) if p.lower().endswith(EXT))
        if not paths: continue
        fresh, already = [], []
        for p in paths:
            fp = _fingerprint(p)
            (already if fp in seen else fresh).append(p); seen.add(fp)
        fresh = _unique(fresh)
        if fresh:
            new = learn_subject(label, fresh); old = prof["subjects"].get(label); n_old = int(old.get("images", 0)) if old else 0
            merged = {k: _wavg((old or {}).get(k), v, n_old, len(fresh)) for k, v in new.items()}
            merged["images"] = n_old + len(fresh); prof["subjects"][label] = merged
            print(f"  {label}: learned {len(fresh)} new images (total {merged['images']})")
        report[label] = len(fresh)
        _discard(paths, keep_images)
    prof["seen"] = sorted(seen); prof["images_kept"] = bool(keep_images)
    if prof["subjects"].get("sky"): prof["sky"] = prof["subjects"]["sky"]["roles"]
    if prof["subjects"].get("mountains"): prof["mountains"] = prof["subjects"]["mountains"]["roles"]
    json.dump(prof, open(os.path.join(folder, "profile.json"), "w"), indent=1)
    import datetime; hist = os.path.join(folder, "history"); os.makedirs(hist, exist_ok=True)      # versions, like checkpoints
    json.dump(prof, open(os.path.join(hist, "profile-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".json"), "w"), indent=1)
    prof["_last_report"] = report
    return prof

def waiting(folder):
    """images added to the library but not learned yet"""
    return {lab: len([f for f in glob.glob(os.path.join(folder, lab, "*")) if f.lower().endswith(EXT)]) for lab in LABELS}
