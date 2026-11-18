"""(older test from an earlier version of the app: it points at a folder and screens that no longer exist, kept for reference)"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _testlog; _testlog.start(__file__)
import os, sys, subprocess, time
sys.path.insert(0, "/home/claude/books/tools/art"); os.chdir("/home/claude/books/tools/art")
import main as M, language
def shot(n): subprocess.run(["import", "-window", "root", f"/tmp/ui/m{n}.png"]); print("shot", n, flush=True)
h = M.Home(); h.geometry("1280x800+0+0")
def s1(): shot("1-home"); g = M.GeneratorWindow(h); g.geometry("1280x800+0+0"); h.g = g
def s2():
    g = h.g; g.prompt.delete("1.0", "end"); g.prompt.insert("1.0", 'a lonely wanderer standing under a starry night sky, jagged peaks, no rocks, "Somebody had to remember"'); g.generate()
    h.after(1000, wait)
def wait():
    g = h.g
    if str(g.gen_btn["state"]) == "disabled" or g.result is None: h.after(1000, wait); return
    h.after(600, lambda: (shot("2-generator"), print("understood:", g.und.get(), "| unknown:", g.unk.get(), flush=True), s3()))
def s3():
    language.teach("wanderer", {"figures": 1, "pose": "standing"}, M.home_dir())          # what the Teach dialog saves
    o, u, k = language.understand("a lonely wanderer standing under a starry night sky", M.home_dir()); print("after teaching:", u, "| unknown:", k, flush=True)
    h.g.destroy(); t = M.TrainingWindow(h); t.geometry("1280x800+0+0"); h.t = t; h.after(1200, s4)
def s4():
    shot("3-training-images"); nb = [c for c in h.t.winfo_children() if c.winfo_class() == "TNotebook"][0]
    nb.select(1); h.t.refresh_words(); h.t.test.set("a lonely wanderer at golden hour"); h.t.test_words(); h.after(800, lambda: (shot("4-training-words"), s5(nb)))
def s5(nb):
    nb.select(2); h.after(800, lambda: (shot("5-training-styles"), s6()))
def s6():
    h.t.destroy(); import app as A; c = A.App(h); c.geometry("1280x800+0+0"); h.after(1500, lambda: (shot("6-classic"), h.destroy()))
h.after(1500, s1); h.after(3000, s2); h.mainloop(); print("MAIN UI TEST FINISHED")
