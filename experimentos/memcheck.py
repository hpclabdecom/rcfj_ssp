from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LIMIT_GB = 12.0


def committed_gb() -> float:
    if os.name == "nt":
        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MS(); m.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return (m.ullTotalPhys - m.ullAvailPhys) / 2 ** 30
    info = {}
    for line in open("/proc/meminfo", encoding="utf-8"):
        k, v = line.split(":")
        info[k] = int(v.split()[0])
    return (info["MemTotal"] - info["MemAvailable"]) / 2 ** 20


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="peak system memory while PT-W runs with the 32-thread layout")
    ap.add_argument("--saida", default=str(ROOT / "results" / "memcheck.json"))
    ap.add_argument("--replicas", type=int, default=16)
    ap.add_argument("--fios", type=int, default=2)
    ap.add_argument("--escala", type=float, default=0.05)
    ap.add_argument("--limite-gb", type=float, default=LIMIT_GB)
    a = ap.parse_args(argv)
    base = committed_gb()
    cmd = [sys.executable, str(HERE / "rcfjssp_ptw.py"), "--replicas", str(a.replicas), "--fios", str(a.fios),
           "--instancias", "lcbrtu_8", "--sementes", "1", "--escala", str(a.escala), "--qualquer-maquina",
           "--saida", str(ROOT / "results" / "_local" / "memcheck")]
    samples = []
    stop = threading.Event()

    def sampler():
        while not stop.is_set():
            samples.append(committed_gb())
            time.sleep(1.0)

    t = threading.Thread(target=sampler, daemon=True)
    t.start()
    rc = subprocess.run(cmd, cwd=str(ROOT)).returncode
    stop.set(); t.join()
    peak = max(samples) if samples else base
    out = {"layout": f"{a.replicas}x{a.fios}", "escala": a.escala, "baseline_used_gb": round(base, 2),
           "peak_used_gb": round(peak, 2), "delta_gb": round(peak - base, 2), "limit_gb": a.limite_gb,
           "ok32": bool(rc == 0 and peak < a.limite_gb), "rc": rc, "samples": len(samples)}
    Path(a.saida).parent.mkdir(parents=True, exist_ok=True)
    Path(a.saida).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
