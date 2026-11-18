"""(older test from an earlier version of the app: it points at a folder and screens that no longer exist, kept for reference)"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _testlog; _testlog.start(__file__)
import os, sys, subprocess, math
sys.path.insert(0, "/home/claude/books/Instant Easel"); os.chdir("/home/claude/books/Instant Easel")
import main as M, numpy as np
a = M.InstantEasel(); a.geometry("1560x920+0+0")
def shot(n): subprocess.run(["import", "-window", "root", f"/tmp/ui/draw-{n}.png"]); print("shot", n, flush=True)
ev = lambda S, x, y: type("E", (), {"x": S._geom()[0] + x * S._geom()[2], "y": S._geom()[1] + y * S._geom()[2]})()
def stroke(S, pts):
    S.down(ev(S, *pts[0]))
    for p in pts[1:]: S.drag(ev(S, *p))
    S.up(ev(S, *pts[-1]))
def go():
    a.tabs.select("Editing"); sec = a.pages["Editing"]; sec.select("Draw"); S = sec.pages["Draw"]
    a.after(4000, lambda: draw(S))                                                      # let the brush previews fill in
def draw(S):
    S.fit(); S.set_brush("oil"); S.set_size(60); S.set_color((196, 92, 44))
    stroke(S, [(150 + t * 900, 300 + math.sin(t * 6) * 120) for t in np.linspace(0, 1, 40)])
    S.mirror.set(True); S.set_brush("watercolor"); S.set_size(80); S.set_color((40, 90, 170))
    stroke(S, [(120 + t * 500, 700 + math.cos(t * 5) * 80) for t in np.linspace(0, 1, 30)]); S.mirror.set(False)
    S.add_layer(); S.mode.set("multiply"); S.set_brush("ink pen"); S.set_size(10); S.set_color((90, 40, 120))
    for tool, a_, b_ in (("rect", (300, 450), (700, 900)), ("oval", (900, 450), (1350, 900))):
        S.set_tool(tool); S.down(ev(S, *a_)); S.drag(ev(S, *b_)); S.up(ev(S, *b_))
    S.set_tool("fill"); S.set_color((250, 205, 90)); S.down(ev(S, 1120, 680))
    S.set_tool("text"); S.set_size(40); S.set_color((30, 30, 40)); S._snap(); S._text((520, 120, 1), "Instant Easel"); S.refresh()
    S.set_tool("pick"); S.down(ev(S, 400, 300)); print("eyedropper picked:", S.color, flush=True)
    n0 = len(S.undo_stack); S.undo(); S.redo(); print("undo/redo stack ok:", len(S.undo_stack) == n0, flush=True)
    print("layers:", [(L.name, L.mode) for L in S.layers], flush=True)
    a.after(1200, lambda: (shot("1-studio"), send(S)))
def send(S):
    S.send(); a.after(1200, lambda: (shot("2-sent-to-editing"), a.destroy()))
a.after(1200, go); a.mainloop(); print("DRAW TEST FINISHED")
