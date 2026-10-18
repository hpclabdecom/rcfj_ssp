from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rcfjssp_core import Instance, parse

from ortools.sat.python import cp_model

from rcfjssp_reference import TABLE7 as PUBLISHED, TABLE7_AVERAGES as AVERAGES


def solve(inst: Instance, mode: str = "declared", workers: int = 8,
          limit: float = 300.0) -> Dict[str, object]:
    model = cp_model.CpModel()
    horizon = inst.horizon() * 2

    capacity = {k: (inst.buffers[k - 1] if mode == "declared"
                    else 0 if mode == "zero" else None)
                for k in range(1, inst.machines + 1)}

    starts, ends, release = {}, {}, {}
    machine_of: Dict[int, int] = {}
    for k, op in enumerate(inst.operations):
        assert len(op.modes) == 1, "Experiment 1 is a job shop, flexibility 1.0"
        machine, duration = op.modes[0]
        machine_of[k] = machine
        starts[k] = model.NewIntVar(0, horizon, f"s{k}")
        ends[k] = model.NewIntVar(0, horizon, f"e{k}")
        release[k] = model.NewIntVar(0, horizon, f"r{k}")
        model.Add(ends[k] == starts[k] + duration)
        model.Add(release[k] >= ends[k])

    index = {(o.job, o.index): k for k, o in enumerate(inst.operations)}
    last_of_job = {}
    for job in range(inst.jobs):
        chain = sorted(o.index for o in inst.ops_of_job(job))
        last_of_job[job] = index[(job, chain[-1])]
        for a, b in zip(chain, chain[1:]):
            ka, kb = index[(job, a)], index[(job, b)]
            model.Add(starts[kb] >= ends[ka])

            model.Add(release[ka] == starts[kb])
    for job, k in last_of_job.items():
        model.Add(release[k] == ends[k])

    by_machine: Dict[int, list] = {}
    by_occupancy: Dict[int, list] = {}
    for k, op in enumerate(inst.operations):
        machine = machine_of[k]
        cap = capacity[machine]
        by_machine.setdefault(machine, []).append(
            model.NewIntervalVar(starts[k],
                                 model.NewIntVar(0, horizon, f"p{k}"),
                                 ends[k], f"prc{k}"))
        if cap is not None:

            by_occupancy.setdefault(machine, []).append(
                model.NewIntervalVar(starts[k],
                                     model.NewIntVar(0, horizon, f"o{k}"),
                                     release[k], f"occ{k}"))

    for machine, intervals in by_machine.items():
        model.AddNoOverlap(intervals)
    for machine, intervals in by_occupancy.items():
        model.AddCumulative(intervals, [1] * len(intervals),
                            capacity[machine] + 1)

    makespan = model.NewIntVar(0, horizon, "makespan")
    model.AddMaxEquality(makespan, [ends[k] for k in range(len(inst.operations))])
    model.Minimize(makespan)

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = workers
    solver.parameters.max_time_in_seconds = limit
    status = solver.Solve(model)
    ok = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    schedule = None
    if ok:
        schedule = [{"op": k, "job": inst.operations[k].job,
                     "index": inst.operations[k].index,
                     "machine": machine_of[k], "tool": inst.operations[k].tool,
                     "start": solver.Value(starts[k]),
                     "end": solver.Value(ends[k]),
                     "release": solver.Value(release[k])}
                    for k in range(len(inst.operations))]
    return {"instance": Path(inst.path).stem, "mode": mode,
            "schedule": schedule,
            "status": solver.StatusName(status),
            "makespan": int(solver.ObjectiveValue()) if ok else None,
            "lower_bound": int(solver.BestObjectiveBound()) if ok else None,
            "seconds": round(solver.WallTime(), 2)}


def main(argv: Optional[Sequence[str]] = None) -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", default=str(here / "instances" / "upstream" / "RCFJSSP-main" / "Experiment 1"))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=float, default=120.0)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    files = sorted(Path(args.folder).glob("*.fjs"))
    rows = []
    print(f"{'instancia':10s} " + "  ".join(f"{m:>22s}" for m in PUBLISHED))
    print(f"{'':10s} " + "  ".join(f"{'nosso':>7s}{'publ.':>8s}{'':>7s}"
                                   for _ in PUBLISHED))
    agree = total = 0
    for path in files:
        inst = parse(path)
        line, cells = f"{Path(path).stem:10s} ", []
        for mode in PUBLISHED:
            out = solve(inst, mode, args.workers, args.limit)
            rows.append(out)
            pub = PUBLISHED[mode].get(out["instance"])
            same = out["makespan"] == pub
            agree += bool(same); total += 1
            cells.append(f"{str(out['makespan']):>7s}{str(pub):>8s}"
                         f"{('  ok' if same else ' NAO'):>7s}")
        print(line + "  ".join(cells))

    import statistics
    print()
    for mode in PUBLISHED:
        ours = [r["makespan"] for r in rows if r["mode"] == mode]
        print(f"  {mode:10s} media nossa {statistics.mean(ours):6.1f}   "
              f"publicada {AVERAGES[mode]:6.1f}")
    if args.check:
        print(f"\n{agree}/{total} reproduzem o ótimo publicado (Tabela 7)")
    out_path = here / "results" / "cpsat_buffers.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"-> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
