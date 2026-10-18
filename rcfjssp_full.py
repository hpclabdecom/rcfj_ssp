"""All resource types at once -- Experiment 4, the only one still open.

Tables 7-9 are closed: every instance proven optimal in seconds.  Table 10 is
not.  The authors' CP model runs 1800 s and proves nothing (average gap 19.11%
against its own bound), and their ALNS-CP closes it only to 17.43%, with
47.27% left on ``lcbrtu8``.  This is where an exact invariance would pay, and
the only place in the benchmark where anything can be gained.

The model is the union of the three validated ones, each already checked
against its own published table:

    Eq. (4)      one NoOverlap per machine
    Eq. (5)      utilities: Pulse over the machine interval, rate u_{i,k,r}
    Eq. (6)      tools: Pulse over the operation, capacity = number of copies
    Eqs. (7)-(11) machine buffers, blocking when y_k = 0
    Eq. (12)     resource level non-negative -- no upper bound per resource
    Eq. (13)     WIP buffer caps the total of the resources it stores

Because nothing here is proven optimal upstream, "validation" means something
weaker and must be stated as such: the model is *consistent* with Table 10 if
our upper bound is at or above their lower bound and our lower bound is at or
below their best known.  A model that is too loose shows up as an upper bound
below their best known that no verifier accepts; a model that is too tight
shows up as a lower bound above their best known, which would be a proof that
one of us is wrong.

Usage:
    cd RCFJSSP && python rcfjssp_full.py --instances 2 --limit 300
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rcfjssp_core import Instance, parse

from ortools.sat.python import cp_model

from rcfjssp_reference import TABLE10 as PUBLISHED


def build(inst: Instance, machine_buffers: bool = True,
          windows: Optional[Dict[int, tuple]] = None):
    model = cp_model.CpModel()
    horizon = inst.horizon()

    starts, ends, release, presence = {}, {}, {}, {}
    by_machine: Dict[int, list] = {}
    by_buffer: Dict[int, list] = {}
    util_terms: Dict[int, list] = {}          # uid -> [(interval, rate)]
    by_tool: Dict[int, list] = {}

    for k, op in enumerate(inst.operations):
        starts[k] = model.NewIntVar(0, horizon, f"s{k}")
        ends[k] = model.NewIntVar(0, horizon, f"e{k}")
        release[k] = model.NewIntVar(0, horizon, f"r{k}")
        model.Add(release[k] >= ends[k])
        lits = []
        for slot, (machine, duration) in enumerate(op.modes):
            lit = model.NewBoolVar(f"x{k}_{machine}")
            lits.append(lit)
            presence[(k, machine)] = lit
            cap = inst.buffers[machine - 1] if machine_buffers else None
            work = model.NewOptionalIntervalVar(starts[k], duration, ends[k],
                                                lit, f"i{k}_{machine}")
            by_machine.setdefault(machine, []).append(work)
            if cap is not None:
                # Eq. (9), literal: occupancy [start, release), cap y_k + 1.
                # See rcfjssp_buffers for why the earlier encoding was tighter.
                by_buffer.setdefault(machine, []).append(
                    model.NewOptionalIntervalVar(
                        starts[k], model.NewIntVar(0, horizon, f"o{k}_{machine}"),
                        release[k], lit, f"occ{k}_{machine}"))
            # Eq. (5): utilities are consumed while the machine is working
            for uid, rate in op.rates[slot]:
                if rate:
                    util_terms.setdefault(uid, []).append((work, rate))
        model.AddExactlyOne(lits)
        model.Add(ends[k] - starts[k] == sum(
            d * presence[(k, m)] for m, d in op.modes))

        if op.tool is not None and inst.tools.get(op.tool):
            by_tool.setdefault(op.tool, []).append(
                model.NewIntervalVar(starts[k],
                                     model.NewIntVar(0, horizon, f"td{k}"),
                                     ends[k], f"t{k}"))

    for machine, intervals in by_machine.items():
        model.AddNoOverlap(intervals)
    for machine, intervals in by_buffer.items():
        model.AddCumulative(intervals, [1] * len(intervals),
                            inst.buffers[machine - 1] + 1)
    for uid, pairs in util_terms.items():                       # Eq. (5)
        model.AddCumulative([iv for iv, _r in pairs],
                            [r for _iv, r in pairs], inst.utilities[uid])
    for tool, intervals in by_tool.items():                     # Eq. (6)
        copies = inst.tools[tool]
        if copies == 1:
            model.AddNoOverlap(intervals)
        else:
            model.AddCumulative(intervals, [1] * len(intervals), copies)

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

    # Eqs. (12)-(13): reservoirs and WIP buffers
    events = []
    for job in range(inst.jobs):
        for uid, qty in inst.required[job].items():
            events.append((job_start[job], uid, -qty))
        for uid, qty in inst.produced[job].items():
            events.append((job_end[job], uid, +qty))
    before = {}
    for i, (ti, _u, _d) in enumerate(events):
        for j, (tj, _u2, _d2) in enumerate(events):
            if i == j:
                continue
            b = model.NewBoolVar(f"p{j}_{i}")
            model.Add(tj <= ti).OnlyEnforceIf(b)
            model.Add(tj > ti).OnlyEnforceIf(b.Not())
            before[(j, i)] = b
    for i in range(len(events)):
        for uid, (buf, start, _top) in inst.nonrenewable.items():
            level = sum(d * before[(j, i)] for j, (_t, u, d) in enumerate(events)
                        if u == uid and j != i) \
                + sum(d for j, (_t, u, d) in enumerate(events)
                      if u == uid and j == i) + start
            model.Add(level >= 0)
        for buf, capacity in inst.wip.items():
            members = {uid for uid, (b, _s, _m) in inst.nonrenewable.items()
                       if b == buf}
            if not members:
                continue
            level = sum(d * before[(j, i)] for j, (_t, u, d) in enumerate(events)
                        if u in members and j != i) \
                + sum(d for j, (_t, u, d) in enumerate(events)
                      if u in members and j == i) \
                + sum(s for uid, (b, s, _m) in inst.nonrenewable.items()
                      if b == buf)
            model.Add(level <= capacity)

    if windows:
        # Domain reductions licensed by Invariance I (rcfjssp_invariance.py):
        # the resource constraints see only job windows, so bounds proved on
        # the window relaxation are valid here.  These are redundant -- they
        # cut no feasible schedule -- and exist to help propagation reach a
        # conclusion the order-boolean encoding reaches slowly on its own.
        for job, (lo, hi) in windows.items():
            chain = sorted(o.index for o in inst.ops_of_job(job))
            if lo:
                model.Add(starts[index[(job, chain[0])]] >= lo)
            model.Add(ends[index[(job, chain[-1])]] <= hi)

    makespan = model.NewIntVar(0, horizon, "makespan")
    model.AddMaxEquality(makespan, list(ends.values()))
    model.Minimize(makespan)
    return model, starts, ends, release, presence


def solve(inst: Instance, workers: int = 8, limit: float = 300.0,
          machine_buffers: bool = True,
          windows: Optional[Dict[int, tuple]] = None) -> Dict[str, object]:
    model, starts, ends, release, presence = build(inst, machine_buffers,
                                                   windows)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = workers
    solver.parameters.max_time_in_seconds = limit
    started = time.perf_counter()
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
            "status": solver.StatusName(status),
            "makespan": int(solver.ObjectiveValue()) if ok else None,
            "lower_bound": int(solver.BestObjectiveBound()) if ok else None,
            "seconds": round(time.perf_counter() - started, 1),
            "machine_buffers": machine_buffers}


def main(argv: Optional[Sequence[str]] = None) -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(
        here / "instances" / "upstream" / "RCFJSSP-main" / "Experiment 4"))
    parser.add_argument("--instances", type=int, default=10)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=float, default=300.0)
    parser.add_argument("--no-machine-buffers", action="store_true")
    args = parser.parse_args(argv)

    rows = []
    print(f"{'instancia':11s} {'nosso UB':>9s} {'nosso LB':>9s} {'s':>6s}  | "
          f"{'LB deles':>9s} {'CP deles':>9s} {'ALNS deles':>11s}  situacao")
    for path in sorted(Path(args.root).glob("*.fjs"))[:args.instances]:
        inst = parse(path)
        out = solve(inst, args.workers, args.limit,
                    not args.no_machine_buffers)
        rows.append(out)
        lb, cp, alns = PUBLISHED.get(out["instance"], (None, None, None))
        note = ""
        if out["makespan"] is not None and alns:
            if out["makespan"] < alns:
                note = f"MELHOR que o melhor conhecido ({alns})"
            elif out["lower_bound"] and out["lower_bound"] > alns:
                note = "LB acima do melhor conhecido -- modelo apertado demais"
            elif out["lower_bound"] and lb and out["lower_bound"] > lb:
                note = f"LB melhor que o deles ({lb})"
        print(f"{out['instance']:11s} {str(out['makespan']):>9s} "
              f"{str(out['lower_bound']):>9s} {out['seconds']:6.0f}  | "
              f"{str(lb):>9s} {str(cp):>9s} {str(alns):>11s}  {note}")

    out_path = here / "results" / "cpsat_full.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"-> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
