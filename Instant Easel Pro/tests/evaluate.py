"""
evaluate.py: robust test suite. The engine paints each subject on its own and is scored against ALL the example images for that
subject, plus the full scene against the author's painting. Results go to logs/scoreboard.json (dated) and the main log, so progress and any
regression are visible over time. Lower = closer.
Photos are scored on texture / stroke direction / light-dark structure only (their colours differ from the book's palette);
colour is scored against the author's own paintings.
"""
import os, sys, glob, json, datetime, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _testlog; HERE = _testlog.start(__file__)   # project folder; results also in the main log
import bench, painter2 as P, draw, test_scene

def score_structure(im, target):
    r = bench.score(im, target); return {k: float(r[k]) for k in ("texture", "strokes", "values")}

def crop_square(im, box):
    w, h = im.size; return im.crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)))

def render_subjects(seed=3):
    sun = (P.W * 0.42, P.H * 0.56); S = P.sky_roles(bench.TARGET); R = P.mountain_roles(bench.TARGET); G = P.ground_roles(bench.TARGET)
    out = {}
    sky = Image.new("RGB", (P.W, P.H)); P.paint_sky2(sky, sun, bench.TARGET, seed); out["sky"] = crop_square(sky, (0, 0, 1, 0.55))
    mt = sky.copy(); P.paint_range(mt, [(0.3, 0.42, 0.4), (0.62, 0.38, 0.45), (0.9, 0.46, 0.35)], P.H * 0.8, R, sun, 12, floor=P.H * 0.62)
    out["mountains"] = crop_square(mt, (0, 0.3, 1, 0.8))
    g = Image.new("RGB", (P.W, P.H), (40, 26, 26)); ridge = np.full(P.W, P.H * 0.05, np.float32)
    P.paint_grass2(g, ridge, sun, G, seed, P.H * 0.05); out["grass"] = crop_square(g, (0, 0.4, 1, 0.95))
    rk = Image.fromarray(np.clip(P.rock_surface(P.W, int(P.H * 0.8), seed, base=tuple(int(c) for c in np.asarray(G["rock"]) * 0.6 + np.array([96, 86, 88]))), 0, 255).astype(np.uint8))
    out["rock"] = rk
    pp = Image.new("L", (1800, 900), 0)
    for i, (x, hair) in enumerate(((300, "short"), (700, "curly"), (1100, "long"), (1500, "tied"))): draw.seated_person(pp, x, 820, 600, hair=hair, seed=i)
    out["people"] = Image.eval(pp, lambda v: 255 - v).convert("RGB")
    out["scene"] = test_scene.render(seed)
    return out

GROUPS = {"sky": "images/Engine Examples/skies", "grass": "images/Engine Examples/grass", "people": "images/Engine Examples/people",
          "rock": ("images/Engine Examples/rocks-mountains", lambda f: f not in ("d.jpg", "dfsfsdfsdfsf.jpg", "dfsdfsfdfs.jpg")),
          "mountains": ("images/Engine Examples/rocks-mountains", lambda f: f in ("d.jpg", "dfsfsdfsdfsf.jpg", "dfsdfsfdfs.jpg"))}

def examples(group):
    spec = GROUPS[group]; folder, keep = (spec, lambda f: True) if isinstance(spec, str) else spec
    return [p for p in sorted(glob.glob(os.path.join(folder, "*"))) if p.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and keep(os.path.basename(p))]

def sheet(name, render, exs, path):
    tw, th = 300, 300; n = min(len(exs), 8); img = Image.new("RGB", ((n + 1) * (tw + 10) + 10, th + 60), (24, 24, 28)); d = ImageDraw.Draw(img)
    f = ImageFont.truetype("fonts/EBGaramond-SemiBold.ttf", 22)
    r = render.copy(); r.thumbnail((tw, th)); img.paste(r, (10, 50)); d.text((10, 14), f"ENGINE: {name}", font=f, fill=(236, 228, 208))
    for i, p in enumerate(exs[:n]):
        e = Image.open(p).convert("RGB"); e.thumbnail((tw, th)); img.paste(e, (10 + (i + 1) * (tw + 10), 50))
    d.text((10 + tw + 10, 14), "your examples", font=f, fill=(180, 180, 190)); img.save(path, quality=85)

if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "/tmp/eval"; os.makedirs(outdir, exist_ok=True)
    rend = render_subjects(); run = {"date": datetime.datetime.now().isoformat(timespec="minutes"), "subjects": {}}
    for name in ("sky", "mountains", "rock", "grass", "people"):
        exs = examples(name); scores = [score_structure(rend[name], e) for e in exs]
        mean = {k: round(float(np.mean([s[k] for s in scores])), 3) for k in scores[0]}; mean["total"] = round(sum(mean.values()), 3)
        best = round(min(sum(s.values()) for s in scores), 3)
        run["subjects"][name] = dict(examples=len(exs), mean=mean, best_match=best)
        sheet(name, rend[name], exs, os.path.join(outdir, f"eval-{name}.jpg"))
    sc = bench.score(rend["scene"]); run["subjects"]["scene"] = dict(examples=1, mean={k: round(float(v), 3) for k, v in sc.items()}, best_match=round(float(sc["total"]), 3))
    sheet("scene", rend["scene"], [bench.TARGET], os.path.join(outdir, "eval-scene.jpg"))
    SB = os.path.join("logs", "scoreboard.json")                                     # test results live in logs/
    board = json.load(open(SB)) if os.path.exists(SB) else []
    board.append(run); json.dump(board, open(SB, "w"), indent=1)
    prev = board[-2]["subjects"] if len(board) > 1 else None
    for name, r in run["subjects"].items():
        trend = ""
        if prev and name in prev: dlt = r["mean"]["total"] - prev[name]["mean"]["total"]; trend = f"  ({'better' if dlt < 0 else 'WORSE' if dlt > 0 else 'same'} {dlt:+.3f})"
        print(f"{name:10s} vs {r['examples']:2d} examples: mean {r['mean']['total']:.3f}  best match {r['best_match']:.3f}{trend}")
