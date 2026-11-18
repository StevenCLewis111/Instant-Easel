import os, sys, subprocess
sys.path.insert(0, "/home/claude/books/Instant Easel"); os.chdir("/home/claude/books/Instant Easel")
import main as M
a = M.InstantEasel(); a.geometry("1560x920+0+0")
def shot(n): subprocess.run(["import", "-window", "root", f"/tmp/ui/tabs-{n}.png"]); print("shot", n, flush=True)
def gen():
    p = a.pages["Images"].pages["Text to Image"]; p.prompt.delete("1.0", "end"); p.prompt.insert("1.0", "a lone hiker on snowy peaks at golden hour"); p.generate()
    a.after(1000, lambda: wait(p))
def wait(p):
    if not p.gen_btn.enabled or not p.results: a.after(1000, lambda: wait(p)); return
    shot("1-images"); a.tabs.select("Editing"); sec = a.pages["Editing"]; sec.select("Light"); L = sec.pages["Light"]; L.last(); L.change("exposure", 0.6)
    a.after(900, lambda: (shot("2-editing-last-created"), a.destroy()))
a.after(1200, gen); a.mainloop(); print("TABS TEST FINISHED")
