"""
_testlog.py: shared start for every test in tests/.

    import _testlog; _testlog.start(__file__)

  * the app's scripts are found from here (the project folder, and every folder under systems/)
  * the working folder is the project folder
  * everything the test prints is also written to the app's main log, logs/instant_easel_errors.log, between a
    "TEST <name> started" line and a "TEST <name> PASSED / FAILED" line, so all results end up in one place
"""
import os, sys, atexit, datetime, traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "logs", "instant_easel_errors.log")

def _paths():
    sys.path.insert(0, ROOT)
    for d, dirs, files in os.walk(os.path.join(ROOT, "systems")):
        dirs[:] = sorted(x for x in dirs if not x.startswith((".", "__")))
        if any(f.endswith(".py") for f in files) and d not in sys.path: sys.path.insert(1, d)

class _Tee:
    def __init__(self, stream, log): self.stream, self.log = stream, log
    def write(self, s):
        self.stream.write(s)
        try: self.log.write(s); self.log.flush()
        except Exception: pass
        return len(s)
    def flush(self):
        self.stream.flush()
        try: self.log.flush()
        except Exception: pass
    def __getattr__(self, k): return getattr(self.stream, k)

def start(test_file):
    """call first thing in a test"""
    _paths(); os.chdir(ROOT); os.makedirs(os.path.dirname(LOG), exist_ok=True)
    name = os.path.splitext(os.path.basename(test_file))[0]; log = open(LOG, "a", encoding="utf-8")
    stamp = lambda: datetime.datetime.now().isoformat(timespec="seconds")
    log.write(f"\n=== TEST {name} started {stamp()} ===\n"); log.flush()
    sys.stdout, sys.stderr = _Tee(sys.stdout, log), _Tee(sys.stderr, log)
    failed = []
    old_hook = sys.excepthook
    def hook(t, v, tb): failed.append(1); old_hook(t, v, tb)
    sys.excepthook = hook
    def end():
        try: log.write(f"=== TEST {name} {'FAILED' if failed else 'PASSED'} {stamp()} ===\n"); log.close()
        except Exception: pass
    atexit.register(end)
    return ROOT
