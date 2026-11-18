import os, sys, subprocess
sys.path.insert(0, "/home/claude/books/Instant Easel"); os.chdir("/home/claude/books/Instant Easel")
import main as M
a = M.InstantEasel(); a.geometry("1560x920+0+0")
def go(): a.tabs.select("Videos"); a.pages["Videos"].select("Text to Video"); a.after(800, lambda: (subprocess.run(["import", "-window", "root", "/tmp/ui/video-tab.png"]), a.destroy()))
a.after(1200, go); a.mainloop(); print("VIDEO TAB OK")
