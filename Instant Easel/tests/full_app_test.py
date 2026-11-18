"""
full_app_test.py: opens the real drawing app and works through both tabs and every page, every drawing tool, layers, colour,
zoom / pan, theme sliders, window modes and zoom changes. Prints ok / FAIL for each step (also written to the main log).
Your settings and theme are put back exactly as they were afterwards.   Run:  python tests/full_app_test.py
"""
import os, sys, shutil; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _testlog; ROOT = _testlog.start(__file__)
_BACKUP = {}
for _f in ("instant_easel_settings.json", "instant_easel_theme.json"):
    _p = os.path.join(ROOT, ".json", _f)
    if os.path.exists(_p): _BACKUP[_p] = open(_p, "rb").read()
_LOG = os.path.join(ROOT, "logs", "instant_easel_errors.log"); _LOG0 = os.path.getsize(_LOG) if os.path.exists(_LOG) else 0
import sys, types, time
import main
T = main.T; E = types.SimpleNamespace; T.popup = lambda *a, **k: "OK"
app = main.InstantEasel(); app.withdraw(); app.restore_window(); app.show_window()
steps = []
def step(name, fn):
    try: fn(); app.update(); steps.append(f"ok   {name}")
    except Exception as e: import traceback; steps.append(f"FAIL {name}: {e!r}\n{traceback.format_exc()[-600:]}")
def run():
    ds = app.pages["Drawing"].pages["Draw"]
    def draw_all():
        app.show("Drawing"); app.update(); ds.fit(); app.update(); cx, cy = ds.cv.winfo_width() // 2, ds.cv.winfo_height() // 2
        for tool in ("brush", "eraser", "line", "rect", "oval", "fill", "pick"):
            ds.set_tool(tool); ds.down(E(x=cx - 30, y=cy - 20))
            for i in range(10): ds.drag(E(x=cx - 30 + i * 6, y=cy - 20 + i * 4))
            ds.up(E(x=cx + 30, y=cy + 20)); app.update()
        ds.mirror.set(True); ds.set_tool("brush"); ds.down(E(x=cx, y=cy)); ds.drag(E(x=cx + 20, y=cy)); ds.up(E(x=cx + 20, y=cy)); ds.mirror.set(False)
        for _ in range(4): ds.undo()
        for _ in range(2): ds.redo()
        ds.add_layer(); ds.down(E(x=cx, y=cy)); ds.drag(E(x=cx + 25, y=cy + 5)); ds.up(E(x=cx + 25, y=cy + 5))
        ds.dup_layer(); ds._toggle_vis(ds.li); ds.lop_s.command(0.4); ds.mode.set("multiply"); ds.move_layer(-1); ds.merge_down(); ds.del_layer()
        for k in range(10): ds._wheel_pick(E(x=95 + k, y=95)); app.update()
        ds.set_size(80); ds.zoom_by(1.5); ds._pan_start(E(x=10, y=10)); ds._pan_move(E(x=40, y=30)); app.update(); time.sleep(0.2); app.update()
        assert ds.flatten().size == tuple(ds.size_wh)
    step("standalone: only Drawing + Settings, no AI or Editing buttons", lambda: (
        None if list(app.pages) == ["Drawing", "Settings"] and not any(k in ("picture", "send") for _, _, k in getattr(ds, "_tb", [])) else 1 / 0))
    step("Draw: every tool, mirror, undo/redo, layers, colour, zoom, pan", draw_all)
    step("Theme sliders", lambda: [app.pages["Settings"].pages["Theme"].change("bg", v / 20) or app.update() for v in range(20)])
    for tab in ("Drawing", "Settings"):
        sec = app.pages[tab]
        for name in sec.pages: step(f"{tab} > {name}", lambda s=sec, n=name, t=tab: (app.show(t), s.select(n), app.update()))
    step("window: maximized -> full screen -> fixed -> maximized", lambda: (app._to_maximized(), app.update(), app._to_fullscreen(), app.update(), app._to_fixed(), app.update(), app.apply_window_mode(), app.update()))
    step("zoom changes", lambda: [main.zoom_to(app, z) or app.update() for z in (1.2, 0.7, 0.78)])
    app.after(2500, done)
def done():
    print("\n".join(steps))
    new = open(_LOG, encoding="utf-8", errors="replace").read()[_LOG0:] if os.path.exists(_LOG) else ""
    errs = [l for l in new.splitlines() if l.startswith("=== 20") or l.startswith("Traceback")]   # app errors (not this test's own lines)
    print("ERRORS LOGGED:", "none" if not errs else f"{len(errs)} (see logs/instant_easel_errors.log)")
    for p, b in _BACKUP.items(): open(p, "wb").write(b)                     # your settings and theme, back as they were
    if any(l.startswith("FAIL") for l in steps) or errs: sys.excepthook(AssertionError, AssertionError("some steps failed"), None)
    app.destroy()
app.after(1500, run); app.mainloop()
