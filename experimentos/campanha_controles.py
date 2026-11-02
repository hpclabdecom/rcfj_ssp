from __future__ import annotations

import argparse
import ctypes
import json
import os
import queue
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import maquina  # noqa: E402
from rcfjssp_lns import T_ALNS  # noqa: E402

PY = sys.executable
S10 = [str(s) for s in range(1, 11)]
S5 = S10[:5]
S3 = S10[:3]
HARD = ["lcbrtu_3", "lcbrtu_5", "lcbrtu_8"]
SCREEN_RULE = "retained if the PT-W median improves the TW-LNS median on >= 2 of the 3 instances and no instance is worse by more than 3"
MEM_LIMIT_GB = 12.0

HOURS_10x10 = sum(T_ALNS.values()) * 10 / 3600
HOURS_HARD5 = sum(T_ALNS[s] for s in HARD) * 5 / 3600


def detect_machine() -> str:
    cpu = maquina.nome_cpu()
    if "i7-2600" in cpu:
        return "i7"
    if "Ryzen" in cpu or "AMD" in cpu:
        return "ryzen"
    if "Xeon" in cpu:
        return "xeon"
    return ""


def heldout_hours(inst_dir: Path, seeds: int) -> float:
    b = json.loads((inst_dir / "budgets.json").read_text(encoding="utf-8"))["seconds"]
    return sum(b.values()) * seeds / 3600


def arm(name, cmd, hours, threads, group="pairs", audit=True, inst_dir=None, needs=None, gate=None):
    return dict(name=name, cmd=cmd, hours=round(hours, 1), threads=threads, group=group,
                audit=audit, inst_dir=inst_dir, needs=needs or [], gate=gate)


def plan(m: str):
    R = ROOT / "results" / m
    Q = ["--qualquer-maquina"]
    HO = ROOT / "instances" / "heldout"
    SC = ROOT / "instances" / "scaled10"
    ctrl_lns = {"i7": ROOT / "results" / "final" / "heur_lns_janela",
                "ryzen": ROOT / "results" / "ryzen" / "heur_lns_janela_4x2",
                "xeon": R / "heur_lns_janela_4x2"}[m]
    ctrl_ptw = R / "ptw_8x1" if m != "i7" else ROOT / "results" / "i7" / "ptw_8x1"

    def lns(folder, walkers, fios, seeds=S10, insts=None):
        c = [PY, str(HERE / "rcfjssp_lns.py"), "--viz", "janela", "--walkers", str(walkers), "--fios", str(fios),
             "--sementes", *seeds, "--saida", str(folder)] + Q
        if insts:
            c += ["--instancias", *insts]
        return c

    def ptw(folder, K, fios, seeds=S10, insts=None, extra=()):
        c = [PY, str(HERE / "rcfjssp_ptw.py"), "--replicas", str(K), "--fios", str(fios), "--sementes", *seeds,
             "--saida", str(folder), "--comparar", str(ctrl_lns)] + Q + list(extra)
        if insts:
            c += ["--instancias", *insts]
        return c

    def ctl(folder, braco, K=8, fios=1, seeds=S10, insts=None, extra=()):
        c = [PY, str(HERE / "rcfjssp_ptw_controls.py"), "--braco", braco, "--replicas", str(K), "--fios", str(fios),
             "--sementes", *seeds, "--saida", str(folder), "--comparar", str(ctrl_ptw)] + Q + list(extra)
        if insts:
            c += ["--instancias", *insts]
        return c

    def ho(folder, metodo, inst_dir, seeds=S10, **kw):
        c = [PY, str(HERE / "rcfjssp_heldout.py"), "--metodo", metodo, "--instancias-dir", str(inst_dir),
             "--sementes", *seeds, "--saida", str(folder)] + Q
        for k, v in kw.items():
            c += [f"--{k}", str(v)]
        return c

    A = []
    if m == "xeon":
        A += [
            arm("memcheck", [PY, str(HERE / "memcheck.py"), "--saida", str(R / "memcheck.json")], 0.2, 32, "solo", audit=False),
            arm("heur_lns_janela_8x2", lns(R / "heur_lns_janela_8x2", 8, 2), HOURS_10x10, 16, "solo"),
            arm("ptw_16x1", ptw(R / "ptw_16x1", 16, 1, extra=["--comparar", str(R / "heur_lns_janela_8x2")]), HOURS_10x10, 16, "solo"),
            arm("heur_lns_janela_16x2", lns(R / "heur_lns_janela_16x2", 16, 2), HOURS_10x10, 32, "solo", gate="mem32"),
            arm("screen_ptw_16x2", ptw(R / "screen_ptw_16x2", 16, 2, S3, HARD, ["--comparar", str(R / "heur_lns_janela_16x2")]), 3 * HOURS_HARD5 / 5, 32, "solo", gate="mem32"),
            arm("screen_ptw_32x1", ptw(R / "screen_ptw_32x1", 32, 1, S3, HARD, ["--comparar", str(R / "heur_lns_janela_16x2")]), 3 * HOURS_HARD5 / 5, 32, "solo", gate="mem32"),
            arm("ptw_32threads", None, HOURS_10x10, 32, "solo", gate="mem32", needs=["screen_ptw_16x2", "screen_ptw_32x1", "heur_lns_janela_16x2"]),
            arm("reservatorio_w32_TALNS", [PY, str(HERE / "x10_reservatorio.py"), "--workers", "32", "--saida", str(R / "reservatorio_w32_TALNS")] + Q, HOURS_10x10, 32, "solo", gate="mem32"),
            arm("relato_w32_1800", [PY, str(HERE / "rcfjssp_final.py"), "--braco", "relato", "--workers", "32", "--limite", "1800", "--sementes", "1", "--saida", str(R)] + Q, 5.0, 32, "solo", gate="mem32"),
            arm("heur_lns_janela_4x2", lns(R / "heur_lns_janela_4x2", 4, 2), HOURS_10x10, 8),
            arm("ptw_8x1", ptw(R / "ptw_8x1", 8, 1), HOURS_10x10, 8),
        ]
    A += [arm("lns_8x1", lns(R / "lns_8x1", 8, 1), HOURS_10x10, 8)]
    A += [
        arm("ptw_8x1_PE_semtroca", ptw(R / "ptw_8x1_PE_semtroca", 8, 1, extra=["--sem-troca"]), HOURS_10x10, 8),
        arm("ptw_8x1_U_nucleo_uniforme", ctl(R / "ptw_8x1_U_nucleo_uniforme", "U"), HOURS_10x10, 8),
    ]
    if m != "xeon":
        A += [arm("ptw_8x1_F_escada_fixa", ctl(R / "ptw_8x1_F_escada_fixa", "F"), HOURS_10x10, 8)]
    A += [arm("ptw_8x1_C_cache_inicial", ctl(R / "ptw_8x1_C_cache_inicial", "C"), HOURS_10x10, 8)]
    if m != "xeon":
        A += [arm("ptw_8x1_PD_alpha0", ptw(R / "ptw_8x1_PD_alpha0", 8, 1, extra=["--alpha-e", "0"]), HOURS_10x10, 8)]
    A += [
        arm("heldout_lns_4x2", ho(R / "heldout_lns_4x2", "lns", HO, walkers=4, fios=2), heldout_hours(HO, 10), 8, inst_dir=HO),
        arm("heldout_ptw_8x1", ho(R / "heldout_ptw_8x1", "ptw", HO, replicas=8, fios=1), heldout_hours(HO, 10), 8, inst_dir=HO),
        arm("heldout_ptw_4x2", ho(R / "heldout_ptw_4x2", "ptw", HO, replicas=4, fios=2), heldout_hours(HO, 10), 8, inst_dir=HO),
        arm("heldout_mono_w8", ho(R / "heldout_mono_w8", "mono", HO, workers=8), heldout_hours(HO, 10), 8, inst_dir=HO),
        arm("ptw_8x1_D_instrumentado", ctl(R / "ptw_8x1_D_instrumentado", "D", seeds=S3), HOURS_10x10 * 0.3, 8),
    ]
    if m != "xeon":
        A += [
            arm("sens_T_x05", ctl(R / "sens_T_x05", "S", seeds=S5, insts=HARD, extra=["--tmin", "0.075", "--tmax", "0.75"]), HOURS_HARD5, 8),
            arm("sens_T_x2", ctl(R / "sens_T_x2", "S", seeds=S5, insts=HARD, extra=["--tmin", "0.3", "--tmax", "3.0"]), HOURS_HARD5, 8),
            arm("sens_delta1_deriva3", ctl(R / "sens_delta1_deriva3", "S", seeds=S5, insts=HARD, extra=["--delta-max", "1", "--deriva", "3"]), HOURS_HARD5, 8),
            arm("sens_delta6_deriva10", ctl(R / "sens_delta6_deriva10", "S", seeds=S5, insts=HARD, extra=["--delta-max", "6", "--deriva", "10"]), HOURS_HARD5, 8),
            arm("sens_subhot2", ctl(R / "sens_subhot2", "S", seeds=S5, insts=HARD, extra=["--sub-hot", "2"]), HOURS_HARD5, 8),
            arm("sens_subhot8", ctl(R / "sens_subhot8", "S", seeds=S5, insts=HARD, extra=["--sub-hot", "8"]), HOURS_HARD5, 8),
            arm("escala10_ptw_8x1", ho(R / "escala10_ptw_8x1", "ptw", SC, S5, replicas=8, fios=1), heldout_hours(SC, 5), 8, inst_dir=SC),
            arm("escala10_lns_4x2", ho(R / "escala10_lns_4x2", "lns", SC, S5, walkers=4, fios=2), heldout_hours(SC, 5), 8, inst_dir=SC),
        ]
    if m == "xeon":
        A += [
            arm("reservatorio_w8_TALNS", [PY, str(HERE / "x10_reservatorio.py"), "--workers", "8", "--saida", str(R / "reservatorio_w8_TALNS")] + Q, HOURS_10x10, 8),
            arm("relato_w8_1800", [PY, str(HERE / "rcfjssp_final.py"), "--braco", "relato", "--workers", "8", "--limite", "1800", "--sementes", "1", "--saida", str(R)] + Q, 5.0, 8),
        ]
    if m == "i7":
        A += [arm("calibracao_janela", [PY, str(HERE / "calibra_lns.py"), "--segundos", "60", "--viz", "janela",
                                        "--saida", str(R / "calibracao_janela")] + Q, 26.7, 8, audit=False)]
    return A


def medians(folder: Path):
    out = {}
    for f in folder.glob("*.json"):
        j = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(j, dict) and j.get("makespan") is not None:
            out.setdefault(j["instance"], []).append(j["makespan"])
    return {k: statistics.median(v) for k, v in out.items()}


def screen_passes(screen: Path, control: Path) -> bool:
    a, c = medians(screen), medians(control)
    if any(s not in a or s not in c for s in HARD):
        return False
    d = [c[s] - a[s] for s in HARD]
    return sum(x > 0 for x in d) >= 2 and min(d) >= -3


class Runner:
    def __init__(self, m, pares, masks, log, status_path, dry):
        self.m, self.pares, self.masks, self.log, self.status_path, self.dry = m, pares, masks, log, status_path, dry
        self.status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
        self.lock = threading.Lock()

    def say(self, msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}"
        print(line, flush=True)
        with self.lock:
            with self.log.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def save(self, name, **kw):
        with self.lock:
            self.status.setdefault(name, {}).update(kw)
            self.status_path.write_text(json.dumps(self.status, indent=1), encoding="utf-8")

    def gate_ok(self, a) -> bool:
        if a["gate"] == "mem32":
            mc = ROOT / "results" / self.m / "memcheck.json"
            if not mc.exists():
                self.say(f"{a['name']}: skipped, memcheck.json missing")
                return False
            ok = json.loads(mc.read_text(encoding="utf-8")).get("ok32", False)
            if not ok:
                self.say(f"{a['name']}: skipped, memory check did not clear 32 threads")
            return ok
        return True

    def resolve(self, a):
        if a["name"] != "ptw_32threads":
            return a["cmd"], a["name"]
        R = ROOT / "results" / self.m
        c16 = R / "heur_lns_janela_16x2"
        if screen_passes(R / "screen_ptw_16x2", c16):
            K, F, name = 16, 2, "ptw_16x2"
        elif screen_passes(R / "screen_ptw_32x1", c16):
            K, F, name = 32, 1, "ptw_32x1"
        else:
            self.say("ptw_32threads: no layout met the screen rule; running the pre-registered default 16x2")
            K, F, name = 16, 2, "ptw_16x2"
        cmd = [PY, str(HERE / "rcfjssp_ptw.py"), "--replicas", str(K), "--fios", str(F), "--sementes", *S10,
               "--saida", str(R / name), "--comparar", str(c16), "--qualquer-maquina"]
        return cmd, name

    def run(self, a, slot=None):
        if not self.gate_ok(a):
            self.save(a["name"], state="skipped")
            return
        cmd, name = self.resolve(a)
        folder = ROOT / "results" / self.m / name
        self.say(f"START {name} (threads {a['threads']}, ~{a['hours']} h, slot {slot}): {' '.join(cmd)}")
        self.save(a["name"], state="running", folder=str(folder), started=time.strftime("%Y-%m-%d %H:%M:%S"))
        if self.dry:
            self.save(a["name"], state="dry")
            return
        t0 = time.time()
        rc = self.spawn(cmd, slot)
        audit = None
        if a["audit"] and folder.exists():
            ac = [PY, str(ROOT / "rcfjssp_audit.py"), "--results", str(folder)]
            if a["inst_dir"]:
                ac += ["--instancias", str(a["inst_dir"])]
            out = subprocess.run(ac, capture_output=True, text=True)
            audit = "ok" if "A-E: nenhum defeito" in out.stdout else "CHECK"
            self.say(f"audit {name}: {audit}")
        self.say(f"END {name}: rc={rc} after {(time.time() - t0) / 3600:.2f} h")
        self.save(a["name"], state="done" if rc == 0 else "failed", rc=rc, audit=audit,
                  finished=time.strftime("%Y-%m-%d %H:%M:%S"))

    def spawn(self, cmd, slot):
        p = subprocess.Popen(cmd, cwd=str(ROOT))
        if slot is not None and self.masks and os.name == "nt":
            try:
                h = int(p._handle)  # noqa: SLF001
                ctypes.windll.kernel32.SetProcessAffinityMask(ctypes.c_void_p(h), ctypes.c_size_t(self.masks[slot]))
                self.say(f"affinity slot {slot}: mask {hex(self.masks[slot])}")
            except Exception as e:  # noqa: BLE001
                self.say(f"affinity not set: {e}")
        return p.wait()

    def run_all(self, arms):
        solo = [a for a in arms if a["group"] == "solo"]
        pairs = [a for a in arms if a["group"] == "pairs"]
        for a in solo:
            self.run(a)
        if self.pares <= 1:
            for a in pairs:
                self.run(a)
            return
        q = queue.Queue()
        for a in pairs:
            q.put(a)

        def worker(slot):
            while True:
                try:
                    a = q.get_nowait()
                except queue.Empty:
                    return
                self.run(a, slot)

        ts = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(self.pares)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Single resumable campaign of controls, held-out and scalability arms per machine")
    ap.add_argument("--maquina", choices=("i7", "ryzen", "xeon"), default=None)
    ap.add_argument("--listar", action="store_true", help="print the plan and the hours, run nothing")
    ap.add_argument("--dry", action="store_true", help="log the commands without running them")
    ap.add_argument("--so", nargs="*", default=None, help="run only these arms (by name)")
    ap.add_argument("--pares", type=int, default=None, help="concurrent 8-thread arms (default: 2 on the Xeon, 1 elsewhere)")
    ap.add_argument("--mascaras", nargs="*", default=None, help="affinity masks per slot, hex (default Xeon: 0xFFFF 0xFFFF0000)")
    a = ap.parse_args(argv)
    m = a.maquina or detect_machine()
    if not m:
        print(f"CPU '{maquina.nome_cpu()}' not recognised; pass --maquina")
        return 2
    for d in ("heldout", "scaled10"):
        if not (ROOT / "instances" / d / "SHA256SUMS").exists():
            print(f"missing instances/{d}: run gera_instancias.py first ({'--escala10' if d == 'scaled10' else ''})")
            return 2
    arms = plan(m)
    if a.so:
        arms = [x for x in arms if x["name"] in a.so]
    pares = a.pares if a.pares is not None else (2 if m == "xeon" else 1)
    masks = [int(x, 16) for x in a.mascaras] if a.mascaras else ([0xFFFF, 0xFFFF0000] if m == "xeon" else None)
    tot = sum(x["hours"] for x in arms)
    print(f"machine {m} ({maquina.nome_cpu()}), {len(arms)} arms, {tot:.0f} machine-hours, "
          f"{pares} concurrent 8-thread arm(s)")
    for x in arms:
        print(f"  [{x['group']:5s} {x['threads']:2d} thr {x['hours']:6.1f} h] {x['name']}")
    if a.listar:
        return 0
    R = ROOT / "results" / m
    R.mkdir(parents=True, exist_ok=True)
    Runner(m, pares, masks, R / "campanha_controles.log", R / "campanha_controles_status.json", a.dry).run_all(arms)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
