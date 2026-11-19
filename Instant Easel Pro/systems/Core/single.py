"""
single.py: only one copy of the app at a time. Two copies would fight over the graphics card, the AI jobs line and the settings file.

    if not single.claim(on_show=lambda: ...): ...    # False: another copy is already open (it's asked to come to the front)

How: the first copy listens on a private local port worked out from the app's folder (so a second install elsewhere doesn't clash).
The port is released by the system the moment the app closes or crashes, so it can never get stuck.
"""
import socket, threading, hashlib, os, sys

_sock = [None]

def _port():
    import paths; return 41000 + int(hashlib.md5(os.path.abspath(paths.HOME).lower().encode()).hexdigest(), 16) % 8000

def claim(on_show=None):
    """True if this is the only copy (it now holds the lock); False if another copy is open (that one is asked to show itself)"""
    if os.environ.get("INSTANT_EASEL_ALLOW_SECOND"): return True               # tests that open the app twice
    port = _port(); s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"): s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try: s.bind(("127.0.0.1", port)); s.listen(2)
    except OSError:
        s.close()
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2) as c: c.sendall(b"show")
        except OSError: return True                                            # nobody answered: whatever held it isn't us; carry on
        return False
    _sock[0] = s
    def serve():
        while True:
            try:
                c, _ = s.accept()
                with c:
                    if c.recv(16) == b"show" and on_show: on_show()
            except OSError: return
    threading.Thread(target=serve, name="single copy", daemon=True).start()
    return True
