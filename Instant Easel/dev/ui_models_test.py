import os, sys, subprocess, glob
sys.path.insert(0, "/home/claude/books/Instant Easel"); os.chdir("/home/claude/books/Instant Easel")
import main as M, prefs, models as MD, learn, language
from PIL import Image
prefs.set("confirm_exit", False)
a = M.InstantEasel(); a.geometry("1560x920+0+0"); a.deiconify()
def shot(n): subprocess.run(["import", "-window", "root", f"/tmp/ui/mod-{n}.png"]); print("shot", n, flush=True)
M.T.popup = lambda *x, **k: (x[3][0][0] if len(x) > 3 and x[3] else "OK")       # auto-answer confirmations with the first (action) button
def go():
    MD.create("Mountain Moods", "Landscapes", "Moody alpine light"); MD.create("Night Painter", "Night scenes", "Moonlit scenes")
    a.refresh_models(); print("models:", MD.names(), "| Image settings model list:", a.settings_panel.model_choice.choices, flush=True)
    sec = a.pages["Training"]; sec.select("Models"); a.tabs.select("Training"); mp = sec.pages["Models"]; mp.train("Mountain Moods")
    tr = sec.pages["Learn from Images"]; print("training target:", tr.target.get(), flush=True)
    print("before correction, guess for a mountain photo:", learn.guess_label("examples/rocks-mountains/d.jpg")[:2], flush=True)
    win = tr.review(sorted(glob.glob("examples/skies/*.jpg"))[:4] + ["examples/rocks-mountains/d.jpg"])
    rows = [w for w in win.winfo_children()]                                                  # set the mountain photo's label to mountains, then Add
    for path, v in [(p, v) for p, v in [(r[0], r[1]) for r in getattr(tr, "_rows", [])]]: pass
    a.after(600, lambda: fix(tr, win))
def fix(tr, win):
    choices = [w for w in walk(win) if isinstance(w, M.T.Choice)]
    choices[-1].var.set("mountains")                                                          # correct the last image's guess
    add = [w for w in walk(win) if isinstance(w, M.T.Button) and w.cget("text") == "Add to library"][0]; add.invoke()
    print("after Add:", tr.msg.cget("text"), flush=True)
    print("after correction, guess for the same photo:", learn.guess_label("examples/rocks-mountains/d.jpg")[:2], flush=True)
    tr.learn(); a.after(4000, lambda: second(tr))
def walk(w):
    for c in w.winfo_children(): yield c; yield from walk(c)
def second(tr):
    print("train 1:", tr.msg.cget("text").split(".")[0], "| stats:", MD.stats("Mountain Moods"), flush=True)
    import shutil
    for f in sorted(glob.glob("examples/grass/*.jpg"))[:3]: d = os.path.join(tr.folder(), "grass"); os.makedirs(d, exist_ok=True); shutil.copy(f, d)
    tr.learn(); a.after(4000, lambda: third(tr))
def third(tr):
    s = MD.stats("Mountain Moods"); vs = MD.versions("Mountain Moods"); print("train 2 stats:", s, "| versions:", len(vs), flush=True)
    MD.rollback("Mountain Moods", vs[-1]); print("rolled back to the first version ->", MD.stats("Mountain Moods")["subjects"], flush=True)
    mp = a.pages["Training"].pages["Models"]; MD.rename("Mountain Moods", "Alpine Moods"); a.refresh_models(); mp.select("Alpine Moods")
    print("renamed + selected ->", a.gen["model"].get(), "| active:", prefs.get("active_model"), flush=True)
    language.teach("alpenglow", {"time": "sunset", "tint": "pink"}, MD.folder("Alpine Moods"))
    o1, u1, k1 = language.understand("alpenglow over peaks", M.home_dir(), MD.folder("Alpine Moods")); o2, u2, k2 = language.understand("alpenglow over peaks", M.home_dir())
    print("'alpenglow' with Alpine Moods:", u1, "| with Core only, unknown:", k2, flush=True)
    a.tabs.select("Images"); a.pages["Images"].select("Image to Image"); p = a.pages["Images"].pages["Image to Image"]; p.load(Image.open("examples/rocks-mountains/dfsdfsfdfs.jpg")); p.run()
    a.after(800, lambda: paint(p))
def paint(p):
    if not p.go.enabled or not p.results: return a.after(500, lambda: paint(p))
    print("painted with the model:", p.notes.cget("text")[:90], flush=True)
    MD.delete("Night Painter"); a.refresh_models(); print("after delete:", MD.names(), "| Image settings list:", a.settings_panel.model_choice.choices, flush=True)
    a.tabs.select("Training"); a.pages["Training"].select("Models"); a.after(800, lambda: (shot("models-page"), a.destroy()))
a.after(1200, go); a.mainloop(); print("MODELS TEST FINISHED")
