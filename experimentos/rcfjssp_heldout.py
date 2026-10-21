from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Optional, Sequence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import maquina  # noqa: E402
import rcfjssp_lns as L  # noqa: E402
import rcfjssp_ptw as PT  # noqa: E402
from rcfjssp_core import parse  # noqa: E402
from rcfjssp_reference import CONFIG  # noqa: E402

ENV = "RCFJ_INST_DIR"


def aplica(inst_dir: Path) -> dict:
    budgets = json.loads((inst_dir / "budgets.json").read_text(encoding="utf-8"))["seconds"]
    L.UP = inst_dir
    L.T_ALNS.update(budgets)
    return budgets


if os.environ.get(ENV):
    aplica(Path(os.environ[ENV]))


def monolitico(stem, seed, workers, orcamento, logf: Path):
    from ortools.sat.python import cp_model
    import modelo_reservatorio as mr
    import rcfjssp_audit as aud
    inst = parse(L.UP / f"{stem}.fjs")
    m, st, en, rl, pr = mr.build(inst, True)
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = workers
    s.parameters.max_time_in_seconds = orcamento
    s.parameters.random_seed = seed
    s.parameters.log_search_progress = True
    s.parameters.log_to_stdout = False
    logf.parent.mkdir(parents=True, exist_ok=True)
    with logf.open("w", encoding="utf-8") as fh:
        s.log_callback = lambda line: fh.write(line + "\n")
        t0 = time.perf_counter(); r = s.Solve(m); w = round(time.perf_counter() - t0, 1)
    ok = r in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    sch = L.extrai(inst, s, st, en, rl, pr) if ok else None
    mk = max(e["end"] for e in sch) if sch else None
    prob = aud.check_schedule(inst, sch, CONFIG[("exp4", "all")], mk) if sch else ["sem solucao"]
    return {"status": s.StatusName(r), "makespan": mk,
            "lower_bound": int(s.BestObjectiveBound()) if ok else None, "seconds": w,
            "schedule": sch if not prob else None, "auditoria": prob or "ok",
            "log": str(logf.name)}


def protocolo(a, inst_dir: Path, prm) -> dict:
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]
    gen = inst_dir / "GENERATION.json"
    p = {"algoritmo": {"lns": "TW-LNS (rcfjssp_lns.py, --viz janela)", "ptw": "PT-W (rcfjssp_ptw.py)",
                       "mono": "native-reservoir CP-SAT, whole model"}[a.metodo],
         "conjunto": inst_dir.name, "sha_instancias": sha(inst_dir / "SHA256SUMS"),
         "sha_geracao": sha(gen) if gen.exists() else None,
         "orcamento": json.loads((inst_dir / "budgets.json").read_text(encoding="utf-8"))["rule"],
         "escala_orcamento": a.escala,
         "walkers": a.walkers, "replicas": a.replicas, "fios": a.fios, "workers": a.workers,
         "parametros": {k: prm[k] for k in prm} if prm else None,
         "sha_script": sha(__file__), "sha_lns": sha(HERE / "rcfjssp_lns.py"),
         "sha_ptw": sha(HERE / "rcfjssp_ptw.py"), "sha_modelo": sha(HERE / "modelo_reservatorio.py"),
         "cpu": maquina.nome_cpu()}
    p["hash"] = hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest()[:16]
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="TW-LNS, PT-W and the monolithic CP-SAT baseline on an instance "
                                             "folder outside the benchmark (held-out or scaled instances)")
    ap.add_argument("--metodo", choices=("lns", "ptw", "mono"), required=True)
    ap.add_argument("--instancias-dir", required=True, help="folder with <stem>.fjs, budgets.json and SHA256SUMS")
    ap.add_argument("--instancias", nargs="*", default=None)
    ap.add_argument("--sementes", type=int, nargs="*", default=[1])
    ap.add_argument("--walkers", type=int, default=4)
    ap.add_argument("--replicas", type=int, default=8)
    ap.add_argument("--fios", type=int, default=None, help="CP-SAT threads per walker/replica (lns: 2, ptw: 1)")
    ap.add_argument("--workers", type=int, default=8, help="CP-SAT threads of the monolithic run")
    ap.add_argument("--escala", type=float, default=1.0)
    ap.add_argument("--calibracao", default=str(ROOT / "results" / "final" / "calibracao" / "escolha.json"))
    ap.add_argument("--saida", required=True)
    ap.add_argument("--qualquer-maquina", action="store_true")
    a = ap.parse_args(argv)
    inst_dir = Path(a.instancias_dir).resolve()
    os.environ[ENV] = str(inst_dir)
    budgets = aplica(inst_dir)
    maquina.exige_i7(a.qualquer_maquina)
    if a.fios is None:
        a.fios = 2 if a.metodo == "lns" else 1
    stems = a.instancias or sorted(budgets)
    prm = None
    if a.metodo in ("lns", "ptw"):
        prm = dict(L.P)
        cal = Path(a.calibracao)
        if not cal.exists():
            print(f"RECUSADO: falta {cal} (calibration choice file).")
            return 2
        prm.update(json.loads(cal.read_text(encoding="utf-8"))["parametros"])
        if a.metodo == "lns":
            prm["VIZ"] = ("janela",)
        else:
            prm.update(PT.PTW)
    proto = protocolo(a, inst_dir, prm)
    pasta = Path(a.saida)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "protocolo.manifest").write_text(json.dumps(proto, indent=1), encoding="utf-8")
    print(f"protocolo {proto['hash']} ({proto['algoritmo']}, {inst_dir.name}) -> {pasta}", flush=True)
    for semente in a.sementes:
        for stem in stems:
            alvo = pasta / f"{stem}_s{semente}.json"
            if alvo.exists():
                old = json.loads(alvo.read_text(encoding="utf-8"))
                if old.get("protocol_hash") == proto["hash"] and old.get("schedule"):
                    print(f"{stem} s{semente}: ja feito ({old['makespan']})", flush=True)
                    continue
            orc = budgets[stem] * a.escala
            if a.metodo == "lns":
                r = L.executa(("rcfjssp", stem), semente, a.walkers, a.fios, orc, prm)
            elif a.metodo == "ptw":
                r = PT.executa(("rcfjssp", stem), semente, a.replicas, a.fios, orc, prm)
            else:
                r = monolitico(stem, semente, a.workers, orc, pasta / "logs" / f"{stem}_s{semente}.log")
            r.update(instance=stem, experiment="exp4", config="all", conjunto=inst_dir.name, seed=semente,
                     orcamento=orc, protocol_hash=proto["hash"], maquina=maquina.descreve(),
                     provenance={"python": platform.python_version()})
            tmp = alvo.with_suffix(".tmp")
            tmp.write_text(json.dumps(r, indent=1), encoding="utf-8")
            os.replace(tmp, alvo)
            print(f"{stem} s{semente}: UB {r['makespan']} em {r.get('wall_seconds', r.get('seconds'))}s "
                  f"(orcamento {orc:.0f}s), auditoria {r.get('auditoria')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
