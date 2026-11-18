"""(older test from an earlier version of the app: it points at a folder and screens that no longer exist, kept for reference)"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _testlog; _testlog.start(__file__)
import os, sys, subprocess
sys.path.insert(0, "/home/claude/books/Instant Easel"); os.chdir("/home/claude/books/Instant Easel")
import main as M
def shot(n): subprocess.run(["import", "-window", "root", f"/tmp/ui/brand-{n}.png"]); print("shot", n, flush=True)
a = M.InstantEasel(); a.geometry("1560x920+0+0"); a.withdraw(); M.splash(a, ms=2500)
a.after(900, lambda: shot("1-splash"))
def main_win():
    shot("2-header"); a.tabs.select("Settings"); a.pages["Settings"].select("About"); a.after(800, lambda: (shot("3-about"), a.destroy()))
a.after(3600, main_win); a.mainloop(); print("BRAND TEST FINISHED")
