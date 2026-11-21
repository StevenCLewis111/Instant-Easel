"""
ai_cutout.py: the AI behind the cut-out tools, run on your own PC (onnxruntime; no account, nothing sent anywhere).

  subject(rgb)            Select Subject: the main subject of the picture (ISNet / DIS, Apache 2.0), a soft 0-1 matte
  Sam().set_image(rgb)    Object Selection / Quick Selection: Segment Anything (Meta, Apache 2.0), prompted by clicks,
  Sam().mask(...)         brush strokes or a box; set_image is the slow part and is kept until the picture changes
  refine(rgb, m, ...)     Refine Edge: an edge-aware matte (guided filter) for hair and fur, then Smooth / Feather /
                          Contrast / Shift Edge, like Photoshop's Select and Mask
  foreground(rgb, a)      Decontaminate Colors: the subject's own colours at its soft edges, without the old background's fringe

The models are built into the app (the Windows build packs them inside the .exe: my-models/cutout/) and loaded while the
splash screen shows (preload()). Run from the source code without them, they're downloaded once, the first time a tool needs
one (ensure(), after asking), and checked against their SHA-256; if that isn't possible the colour-based tools are used.
"""
import os, hashlib, threading, urllib.request
import numpy as np

_REL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/"      # (the ONNX exports hosted with rembg, MIT)
MODELS = {
    # (BiRefNet looked best on paper, but even its light version needs over 6 GB of memory: ISNet runs in under 1 GB)
    "subject": ("isnet-general-use.onnx", 178648008, "60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a"),
    "sam_enc": ("vit_b-encoder-quant.onnx", 99827815, "cf99a3b79eea0ac4f7c9b06cdce5b2763ff41a3f631213c748d497cba233df6a"),
    "sam_dec": ("vit_b-decoder-quant.onnx", 8742591, "40b02c2f694bb87b8360bb04ad8aaa84eab9673f4092b4911e0513890812b42e"),
}
NEEDS = {"subject": ["subject"], "sam": ["sam_enc", "sam_dec"]}
_dir = None


def model_dir():
    """the models built into the app if they're there; otherwise my-models/cutout next to the app (downloaded ones)"""
    global _dir
    if _dir is None:
        try:
            import paths
            inside = os.path.join(paths.APP, "my-models", "cutout")             # (packed inside the .exe by the build)
            if all(os.path.exists(os.path.join(inside, MODELS[k][0])) for k in MODELS): _dir = inside; return _dir
            _dir = paths.data("my-models", "cutout")                            # (with the app's other downloaded models; never uploaded)
        except Exception: _dir = os.path.join(os.path.expanduser("~"), ".instant_easel_models")
    os.makedirs(_dir, exist_ok=True); return _dir


def set_model_dir(d):
    global _dir; _dir = d


def _path(key): return os.path.join(model_dir(), MODELS[key][0])


def have(kind):
    """the models for 'subject' or 'sam' are already on this PC"""
    return all(os.path.exists(_path(k)) and os.path.getsize(_path(k)) == MODELS[k][1] for k in NEEDS[kind])


def runtime_ok():
    try:
        import onnxruntime  # noqa: F401
        return True
    except Exception: return False


def download_size(kind): return sum(MODELS[k][1] for k in NEEDS[kind] if not (os.path.exists(_path(k)) and os.path.getsize(_path(k)) == MODELS[k][1]))


def ensure(kind, progress=None, cancel=None):
    """download what 'kind' needs (once). progress(done_bytes, total_bytes); cancel() -> True stops it. Raises on failure"""
    todo = [k for k in NEEDS[kind] if not (os.path.exists(_path(k)) and os.path.getsize(_path(k)) == MODELS[k][1])]
    total = sum(MODELS[k][1] for k in todo); done = 0
    for k in todo:
        name, size, sha = MODELS[k]; dst = _path(k); part = dst + ".part"; h = hashlib.sha256()
        with urllib.request.urlopen(_REL + name, timeout=60) as r, open(part, "wb") as out:
            while True:
                if cancel and cancel(): raise RuntimeError("cancelled")
                b = r.read(1 << 20)
                if not b: break
                out.write(b); h.update(b); done += len(b)
                if progress: progress(done, total)
        if h.hexdigest() != sha:
            os.remove(part); raise RuntimeError(f"{name} didn't download correctly (checksum)")
        os.replace(part, dst)


_sessions = {}
_lock = threading.Lock()


def preload():
    """load the models that are here, so the first cut-out is quick (the splash screen calls this). Returns what was loaded"""
    done = []
    if not runtime_ok(): return done
    for kind, keys in NEEDS.items():
        if have(kind):
            for k in keys: _session(k); done.append(k)
    return done


def _session(key):
    with _lock:
        if key not in _sessions:
            import onnxruntime as ort
            o = ort.SessionOptions(); o.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL; o.enable_cpu_mem_arena = False   # (less memory held)
            _sessions[key] = ort.InferenceSession(_path(key), o, providers=["CPUExecutionProvider"])
        return _sessions[key]


def _resize(a, w, h):
    from PIL import Image
    if a.ndim == 2: return np.asarray(Image.fromarray(a.astype(np.float32), "F").resize((w, h), Image.BILINEAR), np.float32)
    return np.asarray(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).resize((w, h), Image.BILINEAR), np.float32)


# ------------------------------------------------------------------ Select Subject
def subject(rgb):
    """the main subject: a 0-1 matte the size of rgb (H x W x 3, 0-255)"""
    H, W = rgb.shape[:2]
    x = _resize(rgb, 1024, 1024) / 255.0 - 0.5
    out = _session("subject").run(None, {"input_image": x.transpose(2, 0, 1)[None].astype(np.float32)})[0][0, 0]
    lo, hi = float(out.min()), float(out.max()); out = (out - lo) / max(1e-6, hi - lo)
    return np.clip(_resize(out, W, H), 0, 1)


# ------------------------------------------------------------------ Segment Anything
class Sam:
    """one picture's embedding (slow: a few seconds), then any number of quick masks from points / a box"""
    def __init__(self): self.key = None; self.emb = None; self.scale = 1.0; self.size = (0, 0); self._subj = None

    def subject_of(self, rgb):
        """the subject model's matte of this same picture (worked out once)"""
        if self._subj is None or self._subj.shape != rgb.shape[:2]: self._subj = subject(rgb)
        return self._subj

    def set_image(self, rgb, key=None):
        if key is not None and key == self.key and self.emb is not None: return
        H, W = rgb.shape[:2]; s = 1024 / max(H, W); w, h = int(W * s + 0.5), int(H * s + 0.5)
        x = (_resize(rgb, w, h) - np.array([123.675, 116.28, 103.53], np.float32)) / np.array([58.395, 57.12, 57.375], np.float32)
        pad = np.zeros((1024, 1024, 3), np.float32); pad[:h, :w] = x
        self.emb = _session("sam_enc").run(None, {"x": pad.transpose(2, 0, 1)[None]})[0]
        self.scale = s; self.size = (H, W); self.key = key; self._subj = None

    def mask(self, pos=(), neg=(), box=None, prev=None):
        """pos / neg: (x, y) points on / off the object; box: (x0, y0, x1, y1); prev: low-res logits from the last call (refines it).
        Returns (0-1 soft mask the picture's size, low-res logits for the next call)"""
        pts = [p for p in pos] + [p for p in neg]; lab = [1] * len(pos) + [0] * len(neg)
        if box is not None: pts += [(box[0], box[1]), (box[2], box[3])]; lab += [2, 3]
        else: pts += [(0, 0)]; lab += [-1]                                              # (no box: the padding point)
        c = np.array(pts, np.float32)[None] * self.scale; l = np.array(lab, np.float32)[None]
        mi = np.zeros((1, 1, 256, 256), np.float32) if prev is None else prev.astype(np.float32)
        H, W = self.size
        m, iou, low = _session("sam_dec").run(None, {"image_embeddings": self.emb, "point_coords": c, "point_labels": l, "mask_input": mi,
                                                      "has_mask_input": np.array([0.0 if prev is None else 1.0], np.float32),
                                                      "orig_im_size": np.array([H, W], np.float32)})
        k = int(np.argmax(iou[0])) if m.shape[1] > 1 else 0
        logit = m[0, k]; return 1 / (1 + np.exp(-np.clip(logit, -30, 30))), low[:, k:k + 1]


def object_mask(rgb, sam, pos=(), neg=(), box=None, use_subject=True):
    """Object Selection: Segment Anything finds WHICH object (from clicks / a box), then the subject model draws its outline
    sharply on a crop around it - kept only if the two agree on the shape (else Segment Anything's own region is used).
    Returns a 0-1 matte the picture's size (the edge still to be refined)"""
    from scipy import ndimage as ndi
    m, low = sam.mask(pos, neg, box)
    m, _ = sam.mask(pos, neg, box, prev=low)                                    # a second pass, fed its own result: cleaner
    hard = m > 0.5
    if not hard.any(): return np.zeros(m.shape, np.float32)
    if use_subject and have("subject") and pos and box is None:                  # a click: inside a whole object the subject model
        sal = sam.subject_of(rgb) > 0.5                                         # found? then that whole object (Segment Anything can
        lab, _ = ndi.label(sal); x, y = int(pos[0][0]), int(pos[0][1])            # pick just a part of it, like an elephant's head)
        if 0 <= y < lab.shape[0] and 0 <= x < lab.shape[1] and lab[y, x]:
            comp = lab == lab[y, x]
            for q in neg:
                qx, qy = int(q[0]), int(q[1])
                if 0 <= qy < lab.shape[0] and 0 <= qx < lab.shape[1] and comp[qy, qx]: comp = None; break   # (you said part of it isn't wanted)
            if comp is not None and (hard & comp).sum() >= 0.6 * hard.sum() and comp.sum() < 0.9 * comp.size:
                return np.where(ndi.binary_dilation(comp, iterations=3), sam.subject_of(rgb), 0.0).astype(np.float32)
    H, W = hard.shape; ys, xs = np.where(hard); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    py, px = max(8, (y1 - y0) // 6), max(8, (x1 - x0) // 6)
    y0, y1, x0, x1 = max(0, y0 - py), min(H, y1 + py), max(0, x0 - px), min(W, x1 + px)
    out = hard.astype(np.float32)
    if use_subject and have("subject") and (y1 - y0) > 16 and (x1 - x0) > 16:
        s = subject(rgb[y0:y1, x0:x1]); h = hard[y0:y1, x0:x1]; sb = s > 0.5
        iou = (sb & h).sum() / max(1, (sb | h).sum())
        if iou >= 0.6:                                                           # same thing: its sharp outline, kept near the object
            near = ndi.binary_dilation(h, iterations=max(4, int(0.015 * max(y1 - y0, x1 - x0))))
            out[y0:y1, x0:x1] = np.where(near, s, 0.0)
    return out


# ------------------------------------------------------------------ Refine Edge
def _box(a, r):
    """mean over a (2r+1) square (summed-area table): fast at any radius"""
    if r < 1: return a
    from scipy.ndimage import uniform_filter
    return uniform_filter(a, size=2 * r + 1, mode="reflect")


def guided(I, p, r, eps):
    """the guided filter (He et al.): p made to follow I's edges. I: H x W x 3 (0-1), p: H x W"""
    mI = _box(I, r) if I.ndim == 2 else np.dstack([_box(I[..., c], r) for c in range(3)])
    mp = _box(p, r)
    if I.ndim == 2:
        a = (_box(I * p, r) - mI * mp) / (_box(I * I, r) - mI * mI + eps); b = mp - a * mI
        return _box(a, r) * I + _box(b, r)
    cov = np.dstack([_box(I[..., c] * p, r) - mI[..., c] * mp for c in range(3)])
    S = np.empty(I.shape[:2] + (3, 3), np.float32)
    for i in range(3):
        for j in range(i, 3):
            S[..., i, j] = S[..., j, i] = _box(I[..., i] * I[..., j], r) - mI[..., i] * mI[..., j]
    S += eps * np.eye(3, dtype=np.float32)
    a = np.linalg.solve(S, cov[..., None])[..., 0]; b = mp - (a * mI).sum(2)
    return (np.dstack([_box(a[..., c], r) for c in range(3)]) * I).sum(2) + _box(b, r)


def refine(rgb, m, radius=8, hair=True, smooth=0, feather=0.0, contrast=0, shift=0):
    """Refine Edge on a 0-1 mask m (Photoshop's Select and Mask controls):
    radius: how far either side of the edge is looked at again; hair: an edge-aware matte there (fine hair and fur);
    smooth 0-100: rounds off jagged outlines; feather (px): softens; contrast 0-100: hardens; shift -100..100 %: moves the edge in / out"""
    from scipy import ndimage as ndi
    m = np.clip(np.asarray(m, np.float32), 0, 1); H, W = m.shape
    if hair and radius > 0:
        hard = m > 0.5
        band = ndi.binary_dilation(hard, iterations=int(radius)) & ~ndi.binary_erosion(hard, iterations=int(radius))   # the unsure strip
        if band.any():
            I = rgb.astype(np.float32) / 255.0
            s = 1.0 if max(H, W) <= 1600 else 1600 / max(H, W)                          # (big pictures: worked out smaller, then scaled back)
            if s < 1:
                Is = _resize(rgb, int(W * s), int(H * s)) / 255.0; ms = _resize(m, int(W * s), int(H * s))
                q = _resize(guided(Is, ms, max(2, int(radius * s)), 1e-4), W, H)
            else: q = guided(I, m, max(2, int(radius)), 1e-4)
            fine = guided(I if s == 1 else I, np.clip(q, 0, 1), 2, 1e-5) if s == 1 else q
            m = np.where(band, np.clip(fine, 0, 1), m)
    if smooth > 0:                                                                       # rounder outline (blur, re-threshold, keep softness)
        r = 1 + smooth / 100 * 6; sm = ndi.gaussian_filter(m, r)
        m = np.where((m > 0.02) & (m < 0.98), m, np.clip((sm - 0.5) * 6 + 0.5, 0, 1))
    if shift:                                                                            # Shift Edge: grow / shrink by a share of the radius
        px = abs(shift) / 100 * max(2, radius)
        d = ndi.distance_transform_edt(m < 0.5) if shift > 0 else ndi.distance_transform_edt(m >= 0.5)
        m = np.clip(m + (1 if shift > 0 else -1) * np.clip(px - d + 1, 0, 1) * (1 - m if shift > 0 else m), 0, 1)
    if feather > 0: m = ndi.gaussian_filter(m, feather / 2)
    if contrast > 0:
        k = 1 + contrast / 100 * 12; m = np.clip((m - 0.5) * k + 0.5, 0, 1)
    return m.astype(np.float32)


def foreground(rgb, a, r=24):
    """Decontaminate Colors: the subject's colour at each soft edge pixel, as if the background weren't mixed in.
    (blur-fusion foreground estimation, Germer et al. 2020: two passes of guided box blurs)"""
    I = rgb.astype(np.float32) / 255.0; a = np.clip(a, 0, 1)[..., None]
    def blur(x, rr): return np.dstack([_box(x[..., c], rr) for c in range(x.shape[2])]) if x.ndim == 3 else _box(x, rr)
    def once(F, B, rr):
        ba = blur(a, rr); bF = blur(F * a, rr) / (ba + 1e-5); bB = blur(B * (1 - a), rr) / (blur(1 - a, rr) + 1e-5)
        F2 = bF + a * (I - a * bF - (1 - a) * bB); return np.clip(F2, 0, 1), bB
    F, B = I.copy(), I.copy()
    F, B = once(F, B, r); F, B = once(F, B, max(1, r // 8))
    out = np.where(a > 0.99, I, F); return (out * 255).astype(np.float32)
