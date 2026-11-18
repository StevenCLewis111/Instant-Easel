import sys; sys.path.insert(0, "."); from painter2 import *; import bench
def render(seed=3, style=None):
    """the reference test composition (kept for the bench and scoreboard): the terrace scene, via the scene builder"""
    import landscape
    return landscape.render(dict(seed=seed, caption="Come back sometimes. Appreciate the view.",       # fixed layout: the test must not change
        main_peaks=[(0.08, 0.6, 0.4), (0.5, 0.465, 0.46), (0.78, 0.535, 0.36), (1.0, 0.585, 0.34)],
        far_peaks=[(0.12, 0.56, 0.42), (0.38, 0.545, 0.38), (0.66, 0.55, 0.38), (0.92, 0.565, 0.42)], sun_range=(0.22, 0.44)), style=style)

if __name__ == "__main__":
    import os, json
    prof = json.load(open(os.environ['PROFILE'])) if os.environ.get('PROFILE') else None
    n = sys.argv[1]; im = render(style=prof); out = os.environ.get("CMP", "cmp"); os.makedirs(out, exist_ok=True); im.save(f"{out}/pass{n}.jpg", quality=90)
    r = bench.score(im); print(f"PASS {n} score:", {k: round(float(v), 3) for k, v in r.items()})
    bench.compare(im, f"PASS {n}: " + " ".join(sys.argv[2:]), f"{out}/pass{n}-compare.jpg")
