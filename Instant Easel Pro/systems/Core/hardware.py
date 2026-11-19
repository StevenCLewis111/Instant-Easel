"""
hardware.py: what this PC has, so every AI tab offers only models that will really run on it.

    scan()        the full check (a second or two): processor, cores / threads, PC memory, graphics cards and their memory,
                  power plan and battery (throttling). Saved in .json/pc_scan.json, so the app starts at once next time.
    pc()          the last scan (scans the first time). The app re-scans in the background each time it opens.
    free()        what is free right now: dict(ram_gb, vram_gb) - checked before every AI run.
    describe()    one line for people: "Intel Core i5-12400 · 6 cores / 12 threads · 32 GB · Intel Arc A380 (6 GB)"

Graphics memory comes from the driver's 64-bit value in the registry (Windows' usual video-card list stops at 4 GB, so a 6 GB card
would read as 4). When the text engine is downloaded, its own device list (Vulkan) gives the exact total and what is free.
Integrated graphics (Intel UHD / Iris, AMD "Radeon Graphics") borrow PC memory and are far too slow for AI, so they don't count.

Testing: INSTANT_EASEL_FAKE_PC='{"ram_gb": 32, "gpus": [{"name": "Intel Arc A380", "vram_gb": 6}]}' (or a path to such a file)
pretends to be that PC.
"""
import os, sys, re, json, time, subprocess, threading, platform
import paths

CACHE = paths.json_file("pc_scan.json")
_pc = {}; _lock = threading.Lock()
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
INTEGRATED = re.compile(r"\b(UHD|Iris|HD Graphics|Radeon\(TM\) Graphics|Radeon Graphics|Vega \d+ Graphics|Microsoft Basic|Remote Display|"
                        r"Parsec|Virtual|llvmpipe|SwiftShader)\b", re.I)

# ---------------------------------------------------------------- the scan
_PS = r"""
$ErrorActionPreference = 'SilentlyContinue'
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1 Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed, CurrentClockSpeed
$ram = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory
$vc = @(Get-CimInstance Win32_VideoController | ForEach-Object { [pscustomobject]@{ Name = $_.Name; Ram = [int64]$_.AdapterRAM } })
$reg = @(Get-ItemProperty 'HKLM:\SYSTEM\ControlSet001\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0*' | ForEach-Object {
    $m = $_.'HardwareInformation.qwMemorySize'
    if ($m -is [byte[]]) { $m = [BitConverter]::ToInt64($m, 0) }
    if (-not $m) { $m = $_.'HardwareInformation.MemorySize'; if ($m -is [byte[]]) { $m = [BitConverter]::ToUInt32($m, 0) } }
    [pscustomobject]@{ Name = $_.DriverDesc; Mem = [int64]$m } })
$bat = @(Get-CimInstance Win32_Battery | Select-Object BatteryStatus, EstimatedChargeRemaining)
$plan = (powercfg /getactivescheme) -join ' '
@{ cpu = $cpu; ram = $ram; vc = $vc; reg = $reg; bat = $bat; plan = $plan } | ConvertTo-Json -Depth 4 -Compress
"""

def _windows():
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", _PS], capture_output=True, text=True,
                       timeout=40, creationflags=NO_WINDOW)
    d = json.loads(r.stdout.strip() or "{}"); cpu = d.get("cpu") or {}
    as_list = lambda x: x if isinstance(x, list) else ([x] if x else [])
    reg = {(g.get("Name") or "").strip(): g.get("Mem") or 0 for g in as_list(d.get("reg"))}
    gpus = []
    for g in as_list(d.get("vc")):
        name = (g.get("Name") or "").strip()
        if not name: continue
        mem = max(reg.get(name, 0) or 0, g.get("Ram") or 0)                      # the registry's 64-bit size beats the 4 GB-capped one
        gpus.append(dict(name=name, vram_gb=round(mem / 2 ** 30, 1)))
    bat = as_list(d.get("bat")); plan = d.get("plan") or ""
    m = re.search(r"\(([^)]+)\)\s*$", plan.strip())
    return dict(cpu=(cpu.get("Name") or "").strip(), cores=int(cpu.get("NumberOfCores") or 0), threads=int(cpu.get("NumberOfLogicalProcessors") or 0),
                ghz_max=round((cpu.get("MaxClockSpeed") or 0) / 1000, 2), ghz_now=round((cpu.get("CurrentClockSpeed") or 0) / 1000, 2),
                ram_gb=round((d.get("ram") or 0) / 2 ** 30), gpus=gpus, power_plan=m.group(1) if m else "",
                on_battery=bool(bat) and any((b.get("BatteryStatus") or 2) == 1 for b in bat),     # 1 = running on the battery
                battery=bat[0].get("EstimatedChargeRemaining") if bat else None)

def _other():
    """Linux / macOS (and the fallback if the Windows check fails)"""
    cores = threads = os.cpu_count() or 1; name = platform.processor() or platform.machine(); ram = 0; ghz = 0.0
    try:
        txt = open("/proc/cpuinfo").read()
        name = (re.search(r"model name\s*:\s*(.+)", txt) or re.search(r"Hardware\s*:\s*(.+)", txt) or [None, name])[1]
        phys = {(a, b) for a, b in re.findall(r"physical id\s*:\s*(\d+).*?core id\s*:\s*(\d+)", txt, re.S)}
        cores = len(phys) or cores
        mhz = re.findall(r"cpu MHz\s*:\s*([\d.]+)", txt); ghz = round(max(map(float, mhz)) / 1000, 2) if mhz else 0.0
    except Exception: pass
    try: ram = round(int(re.search(r"MemTotal:\s*(\d+)", open("/proc/meminfo").read())[1]) / 2 ** 20)
    except Exception:
        try: ram = round(int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout) / 2 ** 30)
        except Exception: pass
    return dict(cpu=str(name).strip(), cores=cores, threads=threads, ghz_max=ghz, ghz_now=ghz, ram_gb=ram, gpus=[], power_plan="", on_battery=False, battery=None)

def _vulkan_devices():
    """the text engine's own list of graphics cards: [(name, total GB, free GB)] - exact, and includes what is free right now"""
    try:
        import brain
        exe = brain.server_exe()
        if not exe: return []
        r = subprocess.run([exe, "--list-devices"], capture_output=True, text=True, timeout=30, cwd=os.path.dirname(exe), creationflags=NO_WINDOW)
        out = []
        for name, tot, fr in re.findall(r"^\s*\w+\d+:\s*(.+?)\s*\((\d+)\s*MiB,\s*(\d+)\s*MiB free\)", r.stdout + r.stderr, re.M):
            out.append((name.strip(), round(int(tot) / 1024, 1), round(int(fr) / 1024, 1)))
        return out
    except Exception: return []

def _fake():
    v = os.environ.get("INSTANT_EASEL_FAKE_PC")
    if not v: return None
    d = json.loads(open(v).read() if os.path.exists(v) else v)
    base = dict(cpu="Test PC", cores=4, threads=8, ghz_max=3.0, ghz_now=3.0, ram_gb=16, gpus=[], power_plan="Balanced", on_battery=False, battery=None)
    base.update(d); return base

def scan():
    """check the PC now (slow-ish: run it off the main thread when you can) and remember the result"""
    pc = _fake()
    if pc is None:
        try: pc = _windows() if sys.platform == "win32" else _other()
        except Exception: pc = _other()
        for name, tot, _ in _vulkan_devices():                                    # the engine's exact sizes beat the registry's
            for g in pc["gpus"]:
                if _same(g["name"], name): g["vram_gb"] = tot; break
            else: pc["gpus"].append(dict(name=name, vram_gb=tot))
    for g in pc["gpus"]: g["integrated"] = bool(INTEGRATED.search(g["name"])) or g.get("vram_gb", 0) < 1.0
    best = max((g for g in pc["gpus"] if not g["integrated"]), key=lambda g: g["vram_gb"], default=None)
    pc.update(gpu=best["name"] if best else "", vram_gb=best["vram_gb"] if best else 0.0, when=time.strftime("%Y-%m-%d %H:%M"))
    pc["throttled"] = _throttle(pc)
    with _lock: _pc.clear(); _pc.update(pc)
    if not os.environ.get("INSTANT_EASEL_FAKE_PC"):                                 # a pretend PC (tests) is never saved as this one
        try:
            with open(CACHE, "w") as f: json.dump(pc, f, indent=1)
        except Exception: pass
    return dict(pc)

def _same(a, b):
    w = lambda s: set(re.findall(r"[a-z0-9]+", s.lower())) - {"intel", "r", "tm", "graphics", "corporation", "nvidia", "amd", "geforce", "radeon"}
    return bool(w(a) & w(b))

def _throttle(pc):
    """why the PC may be held back right now ('' if it isn't): battery, a power-saving plan, or the processor running well under speed"""
    why = []
    if pc.get("on_battery"): why.append("running on the battery")
    if re.search(r"saver|power saving|eco", pc.get("power_plan", ""), re.I): why.append(f"power plan '{pc['power_plan']}'")
    if pc.get("ghz_max") and pc.get("ghz_now") and pc["ghz_now"] < 0.6 * pc["ghz_max"]:
        why.append(f"processor at {pc['ghz_now']:.1f} of {pc['ghz_max']:.1f} GHz")
    return ", ".join(why)

def pc():
    """the last scan; scans the first time (the app also re-scans in the background each time it opens)"""
    with _lock:
        if _pc: return dict(_pc)
    if not os.environ.get("INSTANT_EASEL_FAKE_PC"):
        try:
            d = json.load(open(CACHE))
            if d.get("ram_gb") is not None:
                with _lock: _pc.update(d)
                return dict(d)
        except Exception: pass
    return scan()

def rescan_async(on_done=None):
    def work():
        old = pc(); new = scan()
        if on_done: on_done(old, new)
    threading.Thread(target=work, name="PC scan", daemon=True).start()

# ---------------------------------------------------------------- what is free right now
def free_ram_gb():
    try:
        if sys.platform == "win32":
            import ctypes
            class MS(ctypes.Structure):
                _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong), ("avail", ctypes.c_ulonglong),
                            ("tpage", ctypes.c_ulonglong), ("apage", ctypes.c_ulonglong), ("tvirt", ctypes.c_ulonglong), ("avirt", ctypes.c_ulonglong),
                            ("ext", ctypes.c_ulonglong)]
            m = MS(); m.len = ctypes.sizeof(MS); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)); return round(m.avail / 2 ** 30, 1)
        return round(int(re.search(r"MemAvailable:\s*(\d+)", open("/proc/meminfo").read())[1]) / 2 ** 20, 1)
    except Exception: return float(pc().get("ram_gb") or 0) / 2

def free_vram_gb():
    """free memory on the AI graphics card right now (the engine's own Vulkan reading; else the card's size less a little)"""
    p = pc()
    if not p.get("vram_gb"): return 0.0
    if os.environ.get("INSTANT_EASEL_FAKE_PC"): return float(p.get("vram_free_gb", p["vram_gb"] - 0.3))
    for name, tot, fr in _vulkan_devices():
        if _same(name, p["gpu"]) or abs(tot - p["vram_gb"]) < 0.6: return fr
    return round(p["vram_gb"] - 0.4, 1)

def free(): return dict(ram_gb=free_ram_gb(), vram_gb=free_vram_gb())

def threads_for_ai():
    """processor threads to give an engine: the physical cores (hyper-threads don't help these engines)"""
    p = pc(); return max(1, int(p.get("cores") or os.cpu_count() or 2))

def describe(p=None):
    p = p or pc(); bits = []
    if p.get("cpu"): bits.append(re.sub(r"\s+", " ", re.sub(r"\((R|TM)\)|®|™|\bCPU\b|@.*$|\d+(th|st|nd|rd) Gen", "", p["cpu"])).strip())
    if p.get("cores"): bits.append(f"{p['cores']} cores / {p['threads']} threads")
    if p.get("ghz_max"): bits.append(f"{p['ghz_max']:.1f} GHz")
    bits.append(f"{p.get('ram_gb', 0)} GB memory")
    bits.append(f"{_short(p['gpu'])} ({p['vram_gb']:g} GB)" if p.get("gpu") else "no graphics card for AI (it runs on the processor)")
    return " · ".join(bits)

def _short(name): return re.sub(r"\s+", " ", re.sub(r"\((R|TM)\)|®|™|\bGraphics\b|\bCorporation\b", "", name)).strip()
