"""
crash.py: Instant Easel's crash logging, crash recovery and crash protection (nothing is sent anywhere; it's all files beside the app).

  instant_easel_errors.log    every Python error, with its full traceback (kept under ~1 MB: the older half rolls to .1.log)
  instant_easel_crash.log     hard crashes Python can't catch (a fault inside Tk, numpy or Pillow): the stack of every thread
  instant_easel_freezes.log   times the window stopped responding for a while, with what it was doing at that moment
  instant_easel_session.json  "the app is running" marker: still there at the next start = the last session didn't close normally
  recovery/                   autosaved work (the drawing; the Editing settings) to offer back after a crash

    import crash
    info = crash.start(home, log_error)    # first thing: hooks, crash log, session marker; tells you if the last run crashed
    crash.running()                         # once the window is up and working
    crash.beat()                            # called every half second by the window (the freeze watchdog listens for it)
    crash.clean_exit()                      # on a normal quit: marker and recovery files removed
"""
import os, sys, json, time, threading, traceback, faulthandler, shutil

_home = None; _log = None; _crash_file = None; _last_beat = [time.monotonic()]; _session = None
SAFE_MODE_AFTER = 2                                  # this many failed starts in a row: the next start is in safe mode
FREEZE_SECONDS = 8                                   # the window not answering this long is written to the freezes log


def _path(name):
    """.json files go in .json/, logs in logs/, the rest (the recovery folder) in the data folder"""
    import paths
    if name.endswith(".json"): return paths.json_file(name)
    if name.endswith(".log"): return paths.log_file(name)
    return os.path.join(_home or paths.HOME, name)
def recovery_dir(): d = _path("recovery"); os.makedirs(d, exist_ok=True); return d


def _pid_alive(pid):
    """is another copy of the app still running under that process id?"""
    if not pid or pid == os.getpid(): return False
    try:
        if sys.platform == "win32":
            import ctypes
            k = ctypes.windll.kernel32; h = k.OpenProcess(0x1000, False, int(pid))          # PROCESS_QUERY_LIMITED_INFORMATION
            if not h: return False
            code = ctypes.c_ulong(); ok = k.GetExitCodeProcess(h, ctypes.byref(code)); k.CloseHandle(h)
            return bool(ok) and code.value == 259                                             # STILL_ACTIVE
        os.kill(int(pid), 0); return True
    except Exception: return False


def _write_session(d):
    try:
        tmp = _path("instant_easel_session.json.tmp")
        with open(tmp, "w") as f: json.dump(d, f)
        os.replace(tmp, _path("instant_easel_session.json"))
    except Exception: pass


def start(home, log_error):
    """install every safety net and read how the last session ended -> dict(crashed, during_start, safe_mode, failures)"""
    global _home, _log, _crash_file, _session
    _home, _log = home, log_error
    # hard crashes (inside Tk / numpy / Pillow): Python writes the stack of every thread here before the process dies
    try:
        _crash_file = open(_path("instant_easel_crash.log"), "a", encoding="utf-8")
        _crash_file.write(f"\n=== session started {time.strftime('%Y-%m-%dT%H:%M:%S')} (pid {os.getpid()}) ===\n"); _crash_file.flush()
        faulthandler.enable(file=_crash_file, all_threads=True)
    except Exception: pass
    # errors in background threads and in clean-up code are logged too (before, they vanished)
    def thread_hook(a):
        if a.exc_type is SystemExit: return
        log_error(a.exc_type, a.exc_value, a.exc_traceback)
    threading.excepthook = thread_hook
    sys.unraisablehook = lambda u: log_error(type(u.exc_value), u.exc_value, u.exc_traceback) if u.exc_value is not None else None
    # how did the last session end?
    prev = {}
    try:
        with open(_path("instant_easel_session.json")) as f: prev = json.load(f)
    except Exception: pass
    other_copy = _pid_alive(prev.get("pid"))
    crashed = bool(prev) and not other_copy
    during_start = crashed and prev.get("state") == "starting"
    failures = (int(prev.get("start_failures", 0)) + 1) if during_start else 0
    if crashed: log_error(RuntimeError, RuntimeError("the previous session did not close normally" + (" (it failed while starting)" if during_start else "")), None)
    _session = dict(pid=os.getpid(), started=time.time(), state="starting", start_failures=failures)
    if not other_copy: _write_session(_session)
    _start_watchdog()
    return dict(crashed=crashed, during_start=during_start, failures=failures, safe_mode=failures >= SAFE_MODE_AFTER, other_copy=other_copy)


def start_failed():
    """the app couldn't start: count it (two in a row = safe mode next time)"""
    if _session is not None: _session["state"] = "starting"; _write_session(_session)


def running():
    """the window is up and working: a crash from now on is not a start-up failure"""
    if _session is not None: _session.update(state="running", start_failures=0); _write_session(_session)


def clean_exit():
    """normal quit: nothing to recover next time"""
    try: os.remove(_path("instant_easel_session.json"))
    except OSError: pass
    shutil.rmtree(_path("recovery"), ignore_errors=True)


# ---------------- freeze watchdog: the window says "still here" every half second; if it goes quiet, note what it was doing
def beat(): _last_beat[0] = time.monotonic()

def _start_watchdog():
    def watch():
        reported = False
        while True:
            time.sleep(1.0)
            quiet = time.monotonic() - _last_beat[0]
            if quiet < FREEZE_SECONDS: reported = False; continue
            if reported: continue
            reported = True
            try:
                with open(_path("instant_easel_freezes.log"), "a", encoding="utf-8") as f:
                    f.write(f"\n=== {time.strftime('%Y-%m-%dT%H:%M:%S')}: the window hasn't responded for {quiet:.0f} s "
                            f"(a file dialog or message box being open also pauses it). What each part was doing: ===\n")
                    for tid, frame in sys._current_frames().items():
                        name = next((t.name for t in threading.enumerate() if t.ident == tid), str(tid))
                        f.write(f"--- {name} ---\n" + "".join(traceback.format_stack(frame)))
            except Exception: pass
    threading.Thread(target=watch, daemon=True, name="FreezeWatchdog").start()


# ---------------- error pop-ups: the same error over and over shows one pop-up, not a wall of them
_shown = {}; _popup_open = [False]

def should_popup(exc, tb):
    """True if this error deserves a pop-up now (every error is logged either way)"""
    if _popup_open[0]: return False                                            # one pop-up at a time
    frames = traceback.extract_tb(tb) if tb else []
    key = (getattr(exc, "__name__", str(exc)), (frames[-1].filename, frames[-1].lineno) if frames else None)
    now = time.monotonic()
    if now - _shown.get(key, -1e9) < 60: return False                          # same error within a minute: logged only
    _shown[key] = now; return True

class popup_guard:
    def __enter__(self): _popup_open[0] = True
    def __exit__(self, *a): _popup_open[0] = False
