"""
pen_input.py: real pen pressure from a drawing tablet or a pen screen (Wacom, XP-Pen, Huion, Surface Pen...), on Windows.

Tk only ever sees a pen as a mouse (no pressure), so this listens to Windows' own pen messages (the Windows Ink / "Pointer
Input" ones every current pen driver sends: WM_POINTERUPDATE with GetPointerPenInfo, pressure 0-1024) on the widgets you
attach it to, notes the pressure, and lets everything carry on as normal: Windows then turns the same pen movement into the
mouse events Tk already uses. Nothing else changes, and a mouse is left alone.

  pen = attach(widget)      -> a PenState (or a dead one on other systems, or if Windows says no)
  pen.live()                -> a pen is touching (or just was: within a quarter of a second)
  pen.pressure              -> 0-1 (1 if the pen doesn't report pressure)
  pen.eraser                -> the pen's eraser end is the one being used
  pen.seen                  -> a pen has been used here at all (Settings > Pen & Tablet shows it)

Photoshop does the same by default (Windows Ink); Krita offers it as "Windows 8+ Pointer Input". A tablet whose driver has
Windows Ink switched off (WinTab only) won't give pressure here: turn Windows Ink back on in its driver.
"""
import sys, time

class PenState:
    def __init__(self, ok=False, why=""):
        self.ok, self.why = ok, why
        self.pressure, self.tilt, self.eraser, self.seen, self.touching, self.t = 1.0, (0, 0), False, False, False, 0.0
        self.listeners = []
    def live(self): return self.ok and (self.touching or time.time() - self.t < 0.25) and self.seen
    def _update(self, pressure, touching, eraser, tilt):
        self.pressure, self.touching, self.eraser, self.tilt, self.seen, self.t = pressure, touching, eraser, tilt, True, time.time()
        for fn in list(self.listeners):
            try: fn(self)
            except Exception: pass


_keep = {}                                                        # (the window procedures must stay alive while the window does)


def attach(widget):
    """listen for pen messages on widget (and only it). Never fails: on anything but Windows 8+ it returns a PenState that
    simply never sees a pen"""
    if sys.platform != "win32": return PenState(False, "pen pressure is read on Windows only")
    try: return _attach_win(widget)
    except Exception as ex: return PenState(False, f"couldn't listen for the pen: {ex!r}")


def _attach_win(widget):
    import ctypes
    from ctypes import wintypes as W
    u32 = ctypes.WinDLL("user32", use_last_error=True)
    if not hasattr(u32, "GetPointerPenInfo"): return PenState(False, "this Windows has no pen messages (needs Windows 8 or later)")
    LRESULT, WPARAM, LPARAM = ctypes.c_ssize_t, ctypes.c_size_t, ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, WPARAM, LPARAM)

    class PT(ctypes.Structure): _fields_ = [("x", ctypes.c_int32), ("y", ctypes.c_int32)]

    class POINTER_INFO(ctypes.Structure):
        _fields_ = [("pointerType", ctypes.c_uint32), ("pointerId", ctypes.c_uint32), ("frameId", ctypes.c_uint32), ("pointerFlags", ctypes.c_uint32),
                    ("sourceDevice", ctypes.c_void_p), ("hwndTarget", ctypes.c_void_p), ("ptPixelLocation", PT), ("ptHimetricLocation", PT),
                    ("ptPixelLocationRaw", PT), ("ptHimetricLocationRaw", PT), ("dwTime", W.DWORD), ("historyCount", ctypes.c_uint32),
                    ("InputData", ctypes.c_int32), ("dwKeyStates", W.DWORD), ("PerformanceCount", ctypes.c_uint64), ("ButtonChangeType", ctypes.c_int)]

    class POINTER_PEN_INFO(ctypes.Structure):
        _fields_ = [("pointerInfo", POINTER_INFO), ("penFlags", ctypes.c_uint32), ("penMask", ctypes.c_uint32), ("pressure", ctypes.c_uint32),
                    ("rotation", ctypes.c_uint32), ("tiltX", ctypes.c_int32), ("tiltY", ctypes.c_int32)]

    want = 120 if ctypes.sizeof(ctypes.c_void_p) == 8 else 104                     # (POINTER_PEN_INFO's size in Windows' own headers)
    if ctypes.sizeof(POINTER_PEN_INFO) != want: return PenState(False, f"unexpected pen data layout ({ctypes.sizeof(POINTER_PEN_INFO)})")
    u32.GetPointerType.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]; u32.GetPointerType.restype = W.BOOL
    u32.GetPointerPenInfo.argtypes = [ctypes.c_uint32, ctypes.POINTER(POINTER_PEN_INFO)]; u32.GetPointerPenInfo.restype = W.BOOL
    u32.CallWindowProcW.argtypes = [ctypes.c_void_p, W.HWND, W.UINT, WPARAM, LPARAM]; u32.CallWindowProcW.restype = LRESULT
    set_proc = getattr(u32, "SetWindowLongPtrW", None) or u32.SetWindowLongW
    set_proc.argtypes = [W.HWND, ctypes.c_int, ctypes.c_void_p]; set_proc.restype = ctypes.c_void_p

    WM_POINTERUPDATE, WM_POINTERDOWN, WM_POINTERUP, WM_NCDESTROY = 0x0245, 0x0246, 0x0247, 0x0082
    PT_PEN, POINTER_FLAG_INCONTACT, PEN_MASK_PRESSURE, PEN_FLAG_INVERTED, PEN_FLAG_ERASER = 3, 0x4, 0x1, 0x2, 0x4
    hwnd = int(widget.winfo_id()); st = PenState(True); old = [None]

    def proc(h, msg, wp, lp):
        try:
            if msg in (WM_POINTERUPDATE, WM_POINTERDOWN, WM_POINTERUP):
                pid = wp & 0xFFFF; kind = ctypes.c_uint32(0)
                if u32.GetPointerType(pid, ctypes.byref(kind)) and kind.value == PT_PEN:
                    info = POINTER_PEN_INFO()
                    if u32.GetPointerPenInfo(pid, ctypes.byref(info)):
                        touching = bool(info.pointerInfo.pointerFlags & POINTER_FLAG_INCONTACT) and msg != WM_POINTERUP
                        pr = info.pressure / 1024.0 if info.penMask & PEN_MASK_PRESSURE else 1.0
                        st._update(min(1.0, max(0.0, pr)), touching, bool(info.penFlags & (PEN_FLAG_INVERTED | PEN_FLAG_ERASER)), (info.tiltX, info.tiltY))
            elif msg == WM_NCDESTROY:
                r = u32.CallWindowProcW(old[0], h, msg, wp, lp); _keep.pop(hwnd, None); return r
        except Exception: pass
        return u32.CallWindowProcW(old[0], h, msg, wp, lp)           # (then on as usual: Windows makes the mouse events from it)

    cb = WNDPROC(proc); _keep[hwnd] = (cb, st)
    ctypes.set_last_error(0); prev = set_proc(hwnd, -4, ctypes.cast(cb, ctypes.c_void_p))   # GWLP_WNDPROC
    if not prev:
        _keep.pop(hwnd, None); return PenState(False, f"Windows wouldn't let us listen (error {ctypes.get_last_error()})")
    old[0] = prev; return st


def feel(pressure, how="Normal"):
    """Settings > Pen & Tablet > Pressure feel: Soft (light touches already count a lot), Normal, Firm (press harder)"""
    g = {"Soft": 0.6, "Normal": 1.0, "Firm": 1.6}.get(how, 1.0)
    return max(0.02, min(1.0, pressure ** g))
