from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rcfjssp_core import Instance, parse

from ortools.sat.python import cp_model

from rcfjssp_reference import TABLE9 as PUBLISHED, TABLE9_AVERAGES as AVERAGES


def solve(inst: Instance, wip: bool = True, machine_buffers: bool = True,
          workers: int = 8, limit: float = 300.0) -> Dict[str, object]:
    model = cp_model.CpModel()
    horizon = inst.horizon()

    starts, ends, release, presence = {}, {}, {}, {}
    by_machine: Dict[int, list] = {}
    by_buffer: Dict[int, list] = {}
    for k, op in enumerate(inst.operations):
        starts[k] = model.NewIntVar(0, horizon, f"s{k}")
        ends[k] = model.NewIntVar(0, horizon, f"e{k}")
        release[k] = model.NewIntVar(0, horizon, f"r{k}")
        model.Add(release[k] >= ends[k])
        lits = []
        for machine, duration in op.modes:
            lit = model.NewBoolVar(f"x{k}_{machine}")
            cap = inst.buffers[machine - 1] if machine_buffers else None
            by_machine.setdefault(machine, []).append(
                model.NewOptionalIntervalVar(starts[k], duration, ends[k],
                                             lit, f"i{k}_{machine}"))
            if cap is not None:

                by_buffer.setdefault(machine, []).append(
                    model.NewOptionalIntervalVar(
                        starts[k], model.NewIntVar(0, horizon, f"o{k}_{machine}"),
                        release[k], lit, f"occ{k}_{machine}"))
            lits.append(lit)
            presence[(k, machine)] = lit
        model.AddExactlyOne(lits)
        model.Add(ends[k] - starts[k] == sum(
            d * presence[(k, m)] for m, d in op.modes))
    for machine, intervals in by_machine.items():
        model.AddNoOverlap(intervals)
    for machine, intervals in by_buffer.items():
        model.AddCumulative(intervals, [1] * len(intervals),
                            inst.buffers[machine - 1] + 1)

    index = {(o.job, o.index): k for k, o in enumerate(inst.operations)}
    job_start, job_end = {}, {}
    for job in range(inst.jobs):
        chain = sorted(o.index for o in inst.ops_of_job(job))
        for a, b in zip(chain, chain[1:]):
            model.Add(starts[index[(job, b)]] >= ends[index[(job, a)]])
            model.Add(release[index[(job, a)]] == starts[index[(job, b)]])
        model.Add(release[index[(job, chain[-1])]] == ends[index[(job, chain[-1])]])
        job_start[job] = starts[index[(job, chain[0])]]
        job_end[job] = ends[index[(job, chain[-1])]]


    events = []
    for job in range(inst.jobs):
        for uid, qty in inst.required[job].items():
            events.append((job_start[job], uid, -qty))
        for uid, qty in inst.produced[job].items():
            events.append((job_end[job], uid, +qty))

    if events:
        times = [t for t, _u, _d in events]


        before = {}
        for i, (ti, _ui, _di) in enumerate(events):
            for j, (tj, _uj, _dj) in enumerate(events):
                if i == j:
                    continue
                b = model.NewBoolVar(f"b{j}_{i}")
                model.Add(tj <= ti).OnlyEnforceIf(b)
                model.Add(tj > ti).OnlyEnforceIf(b.Not())
                before[(j, i)] = b

        for i, (_ti, _ui, _di) in enumerate(events):
            for uid, (buf, start, top) in inst.nonrenewable.items():
                terms = [d * before[(j, i)] for j, (_t, u, d) in enumerate(events)
                         if u == uid and j != i]
                own = [d for j, (_t, u, d) in enumerate(events)
                       if u == uid and j == i]

                model.Add(sum(terms) + sum(own) + start >= 0)

            if wip:
                for buf, capacity in inst.wip.items():
                    members = {uid for uid, (b, _s, _m) in
                               inst.nonrenewable.items() if b == buf}
                    if not members:
                        continue
                    terms = [d * before[(j, i)]
                             for j, (_t, u, d) in enumerate(events)
                             if u in members and j != i]
                    own = [d for j, (_t, u, d) in enumerate(events)
                           if u in members and j == i]
                    base = sum(s for uid, (b, s, _m) in
                               inst.nonrenewable.items() if b == buf)
                    model.Add(sum(terms) + sum(own) + base <= capacity)

    makespan = model.NewIntVar(0, horizon, "makespan")
    model.AddMaxEquality(makespan, list(ends.values()))
    model.Minimize(makespan)

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = workers
    solver.parameters.max_time_in_seconds = limit
    status = solver.Solve(model)
    ok = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    schedule = None
    if ok:
        schedule = []
        for k, op in enumerate(inst.operations):
            machine = next(m for m, _d in op.modes
                           if solver.Value(presence[(k, m)]))
            schedule.append({"op": k, "job": op.job, "index": op.index,
                             "machine": machine, "tool": op.tool,
                             "start": solver.Value(starts[k]),
                             "end": solver.Value(ends[k]),
                             "release": solver.Value(release[k])})
    return {"instance": Path(inst.path).stem,
            "schedule": schedule,
            "folder": Path(inst.path).parent.name,
            "wip": wip, "machine_buffers": machine_buffers, "status": solver.StatusName(status),
            "makespan": int(solver.ObjectiveValue()) if ok else None,
            "lower_bound": int(solver.BestObjectiveBound()) if ok else None,
            "seconds": round(solver.WallTime(), 2)}


def main(argv: Optional[Sequence[str]] = None) -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(here / "instances" / "upstream" / "RCFJSSP-main" / "Experiment 3"))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=float, default=120.0)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    rows = []
    print(f"{'arquivo':22s} {'buffers':>8s} {'nosso':>6s} {'LB':>5s} "
          f"{'status':>10s} {'s':>7s}")
    for path in sorted(Path(args.root).rglob("*.fjs")):
        inst = parse(path)
        for wip in (True, False):
            out = solve(inst, wip, True, args.workers, args.limit)
            rows.append(out)
            print(f"{out['folder'] + '/' + out['instance']:22s} "
                  f"{str(wip):>8s} {str(out['makespan']):>6s} "
                  f"{str(out['lower_bound']):>5s} {out['status']:>10s} "
                  f"{out['seconds']:7.2f}")
    out_path = here / "results" / "cpsat_wip.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"-> {out_path}")
    if args.check:
        print("\nAlvos da Tabela 9 (medias): "
              + "  ".join(f"{k} {v}" for k, v in AVERAGES.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
