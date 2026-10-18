from __future__ import annotations

import argparse
import copy
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from rcfjssp_core import parse
import rcfjssp_buffers as m1
import rcfjssp_cpsat as m2
import rcfjssp_wip as m3
import rcfjssp_full as m4

UP = HERE / "instances" / "upstream" / "RCFJSSP-main"
OUT = HERE / "results" / "final" / "validacao"
LIMIT_CLOSED = 300.0
LIMIT_OPEN = 1800.0


MODEL_VERSION = "2026-08-14-eq9-literal"


def provenance(inst) -> dict:
    import hashlib
    import platform
    try:
        import ortools
        version = getattr(ortools, "__version__", "desconhecida")
    except ImportError:
        version = "ausente"
    return {
        "ortools": version,
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.machine()}",
        "instance_sha256": hashlib.sha256(
            Path(inst.path).read_bytes()).hexdigest()[:32],
        "solver": "cp-sat, parametros de fabrica salvo num_search_workers "
                  "e max_time_in_seconds",
        "deterministic": False,
        "nota": "busca paralela com corte de tempo: o limite inferior nao e "
                "reprodutivel apenas por workers e seconds",
    }


def atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def load(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    if not isinstance(data, dict) or "makespan" not in data:
        return None


    if data["makespan"] is not None and not data.get("schedule"):
        return None
    if data.get("model_version") != MODEL_VERSION:
        return None
    return data


def tasks() -> List[Tuple[str, str, str]]:
    out = []
    for n in range(10):
        for mode in ("declared", "zero", "unlimited"):
            out.append(("exp1", f"lcb{n}", mode))
    for n in range(10):
        for beta in ("10", "25", "50", "75", "100"):
            out.append(("exp2", f"t_{n}", beta))
    for n in range(10):
        for col in ("small", "large", "none"):
            out.append(("exp3", f"r_{n}", col))
    for n in range(10):
        out.append(("exp4", f"lcbrtu_{n}", "all"))
    return out


def execute(experiment: str, stem: str, config: str, workers: int) -> dict:
    started = time.time()
    if experiment == "exp1":
        inst = parse(UP / "Experiment 1" / f"{stem}.fjs")
        row = m1.solve(inst, config, workers, LIMIT_CLOSED)
        row["published"] = m1.PUBLISHED[config][stem]
    elif experiment == "exp2":


        folder = "75" if config == "100" else config
        inst = parse(UP / "Experiment 2" / folder / f"{stem}.fjs")
        row = m2.solve(inst, workers, LIMIT_CLOSED,
                       use_tools=(config != "100"))
        if row.get("schedule"):
            m2.verify(inst, row["schedule"], check_tools=(config != "100"))
        row["published"] = m2.BY_BETA[config][stem]
    elif experiment == "exp3":
        folder = {"small": "50", "large": "100", "none": "50"}[config]
        inst = parse(UP / "Experiment 3" / folder / f"{stem}.fjs")
        if config == "none":
            inst = copy.deepcopy(inst)
            inst.required = [{} for _ in inst.required]
            inst.produced = [{} for _ in inst.produced]
        row = m3.solve(inst, config != "none", False, workers, LIMIT_CLOSED)
        row["published"] = m3.PUBLISHED[
            {"small": "small", "large": "large", "none": "unlimited"}[config]][stem]
    else:
        inst = parse(UP / "Experiment 4" / f"{stem}.fjs")
        row = m4.solve(inst, workers, LIMIT_OPEN, machine_buffers=True)
        lb, cp, alns = m4.PUBLISHED[stem]
        row.update(their_lb=lb, their_cp=cp, their_alns=alns, published=None)

    row.update(experiment=experiment, instance=stem, config=config,
               workers=workers, wall_seconds=round(time.time() - started, 1),
               model_version=MODEL_VERSION, provenance=provenance(inst))
    if row.get("published") is not None:
        row["agrees"] = row["makespan"] == row["published"]
    return row


def published_for(row: dict) -> Optional[int]:
    exp, stem, config = row["experiment"], row["instance"], row["config"]
    if exp == "exp1":
        return m1.PUBLISHED[config][stem]
    if exp == "exp2":
        return m2.BY_BETA[config][stem]
    if exp == "exp3":
        key = {"small": "small", "large": "large", "none": "unlimited"}[config]
        return m3.PUBLISHED[key][stem]
    return None


def report() -> None:
    rows = [d for p in sorted(OUT.glob("*.json")) if (d := load(p))]
    if not rows:
        print(f"nada em {OUT}")
        return
    print(f"{len(rows)} resultados em {OUT}\n")
    for experiment in ("exp1", "exp2", "exp3"):
        group = [r for r in rows if r["experiment"] == experiment]
        for r in group:
            r["published"] = published_for(r)
            r["agrees"] = r["makespan"] == r["published"]
        if not group:
            continue
        ok = sum(1 for r in group if r["agrees"])
        print(f"  {experiment}: {ok}/{len(group)} reproduzem o valor publicado")
        for r in group:
            if not r.get("agrees"):
                print(f"      DIVERGE {r['instance']}/{r['config']}: "
                      f"nosso {r['makespan']} contra {r['published']}")
    four = [r for r in rows if r["experiment"] == "exp4"]
    if four:
        got = [r for r in four if r["makespan"] is not None]
        print(f"\n  exp4: {len(got)}/{len(four)} viaveis, "
              f"{sum(1 for r in got if r['status'] == 'OPTIMAL')} provados otimos")
        print(f"  {'inst':11s} {'nosso UB':>9s} {'nosso LB':>9s}  | "
              f"{'LB deles':>9s} {'CP deles':>9s} {'ALNS':>6s}")
        better = []
        for r in sorted(four, key=lambda x: x["instance"]):
            mark = ""
            if r["makespan"] is not None and r["makespan"] < r["their_alns"]:
                mark = "  <== melhor que o melhor conhecido"
                better.append(r["instance"])
            elif r["lower_bound"] and r["lower_bound"] > r["their_lb"]:
                mark = "  <== limite inferior melhor"
            print(f"  {r['instance']:11s} {str(r['makespan']):>9s} "
                  f"{str(r['lower_bound']):>9s}  | {r['their_lb']:>9d} "
                  f"{r['their_cp']:>9d} {r['their_alns']:>6d}{mark}")
        if got:
            print(f"\n  media nossa {statistics.mean(r['makespan'] for r in got):6.1f}"
                  f"   CP deles 333.6   ALNS-CP deles 329.0")
        if better:
            print(f"\n  ATENCAO: {better} abaixo do melhor conhecido. "
                  f"Verificar antes de reportar.")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 8)
    parser.add_argument("--only", choices=("1", "2", "3", "4"), default=None)
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args(argv)

    if args.report:
        report()
        return 0
    if not UP.exists():
        raise SystemExit(f"instancias nao encontradas em {UP}")

    todo = tasks()
    if args.only:
        todo = [t for t in todo if t[0] == f"exp{args.only}"]
    pending = [t for t in todo
               if load(OUT / f"{t[0]}_{t[1]}_{t[2]}.json") is None]
    estimate = sum(LIMIT_OPEN if t[0] == "exp4" else 20 for t in pending) / 3600
    print(f"{len(todo)} execucoes, {len(pending)} pendentes, "
          f"{args.workers} workers")
    print(f"estimativa de pior caso: {estimate:.1f} h "
          f"(o Experimento 4 domina: 1800 s por instancia)\n")

    for i, (experiment, stem, config) in enumerate(pending, 1):
        row = execute(experiment, stem, config, args.workers)
        atomic_write(OUT / f"{experiment}_{stem}_{config}.json", row)
        flag = ("" if row.get("published") is None
                else "  ok" if row.get("agrees") else "  DIVERGE")
        print(f"[{i:3d}/{len(pending):3d}] {experiment} {stem:10s} {config:10s} "
              f"UB {str(row['makespan']):>6s} LB {str(row['lower_bound']):>6s} "
              f"{row['status']:>9s} {row['wall_seconds']:7.1f}s{flag}", flush=True)

    print()
    report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
