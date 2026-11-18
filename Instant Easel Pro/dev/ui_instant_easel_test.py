import os, sys, subprocess
sys.path.insert(0, "/home/claude/books/tools/art"); os.chdir("/home/claude/books/tools/art")
import main as M
def shot(n): subprocess.run(["import", "-window", "root", f"/tmp/ui/ie-{n}.png"]); print("shot", n, flush=True)
a = M.InstantEasel(); a.geometry("1280x860+0+0")
def gen():
    g = a.pages["Generate"]; g.prompt.delete("1.0", "end"); g.prompt.insert("1.0", 'a lonely wanderer standing under a starry night sky, jagged peaks, "Somebody had to remember"'); g.generate(); a.after(1000, wait)
def wait():
    g = a.pages["Generate"]
    if not g.gen_btn.enabled or g.result is None: a.after(1000, wait); return
    a.after(500, lambda: (shot("1-generate"), step(1)))
seq = ["Train", "Words", "Paint", "Theme"]
def step(i):
    if i <= len(seq):
        n = seq[i - 1]; a.tabs.select(n)
        if n == "Words": a.pages["Words"].do_test()
        a.after(700, lambda: (shot(f"{i + 1}-{n.lower()}"), step(i + 1)))
    else:
        th = a.pages["Theme"]; th.change("border", 0.58); th.change("bg", 0.83)        # recolour live, like the Theme tab sliders
        a.tabs.select("Generate"); a.after(800, lambda: (shot("6-recoloured"), teach()))
def teach():
    th = a.pages["Theme"]; th.reset(); d = M.TeachDialog(a, "wanderer"); d.geometry("+300+120"); a.after(900, lambda: (shot("7-teach-dialog"), d.destroy(), a.destroy()))
a.after(1200, gen); a.mainloop(); print("INSTANT EASEL UI TEST FINISHED")
