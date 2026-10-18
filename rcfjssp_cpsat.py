from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rcfjssp_core import Instance, parse, summarise

from ortools.sat.python import cp_model

from rcfjssp_reference import TABLE8 as BY_BETA
PUBLISHED_BETA10 = BY_BETA["10"]
PUBLISHED_BETA100 = BY_BETA["100"]


def solve(inst: Instance, workers: int = 8, limit: float = 300.0,
          use_tools: bool = True, unused_zero_is_free: bool = True
          ) -> Dict[str, object]:
    model = cp_model.CpModel()
    horizon = inst.horizon()

    starts, ends, presence = {}, {}, {}
    by_machine: Dict[int, list] = {}
    by_tool: Dict[int, list] = {}

    for k, op in enumerate(inst.operations):
        start = model.NewIntVar(0, horizon, f"s{k}")
        end = model.NewIntVar(0, horizon, f"e{k}")
        starts[k], ends[k] = start, end
        literals = []
        for machine, duration in op.modes:
            lit = model.NewBoolVar(f"x{k}_{machine}")
            interval = model.NewOptionalIntervalVar(
                start, duration, end, lit, f"i{k}_{machine}")
            by_machine.setdefault(machine, []).append(interval)
            literals.append(lit)
        model.AddExactlyOne(literals)
        for lit, (machine, duration) in zip(literals, op.modes):
            presence[(k, machine)] = lit

        if use_tools and op.tool is not None:


            by_tool.setdefault(op.tool, []).append(
                model.NewIntervalVar(start, model.NewIntVar(0, horizon, f"d{k}"),
                                     end, f"t{k}"))
            model.Add(ends[k] - starts[k] == sum(
                duration * presence[(k, machine)]
                for machine, duration in op.modes))
        else:
            model.Add(ends[k] - starts[k] == sum(
                duration * presence[(k, machine)]
                for machine, duration in op.modes))


    index = {}
    for k, op in enumerate(inst.operations):
        index[(op.job, op.index)] = k
    for job in range(inst.jobs):
        chain = sorted(o.index for o in inst.ops_of_job(job))
        for a, b in zip(chain, chain[1:]):
            model.Add(starts[index[(job, b)]] >= ends[index[(job, a)]])

    for machine, intervals in by_machine.items():
        model.AddNoOverlap(intervals)

    if use_tools:
        for tool, intervals in by_tool.items():
            copies = inst.tools.get(tool, 1)
            if copies == 0:


                if not unused_zero_is_free:
                    model.Add(sum(1 for _ in intervals) == 0)
                continue
            if copies == 1:
                model.AddNoOverlap(intervals)
            else:
                model.AddCumulative(intervals, [1] * len(intervals), copies)

    makespan = model.NewIntVar(0, horizon, "makespan")
    model.AddMaxEquality(makespan, [ends[k] for k in range(len(inst.operations))])
    model.Minimize(makespan)

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = workers
    solver.parameters.max_time_in_seconds = limit
    started = time.perf_counter()
    status = solver.Solve(model)
    elapsed = time.perf_counter() - started

    out: Dict[str, object] = {
        "instance": Path(inst.path).stem,
        "status": solver.StatusName(status),
        "optimal": status == cp_model.OPTIMAL,
        "makespan": int(solver.ObjectiveValue()) if status in
        (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
        "lower_bound": int(solver.BestObjectiveBound()) if status in
        (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
        "seconds": round(elapsed, 2),
        "tools_modelled": use_tools,
    }
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        schedule = []
        for k, op in enumerate(inst.operations):
            machine = next(m for m, _d in op.modes
                           if solver.Value(presence[(k, m)]))
            schedule.append({"op": k, "job": op.job, "index": op.index,
                             "machine": machine, "tool": op.tool,
                             "start": solver.Value(starts[k]),
                             "end": solver.Value(ends[k])})
        out["schedule"] = schedule
    return out


def verify(inst: Instance, schedule: Sequence[dict],
           check_tools: bool = True) -> None:
    by_op = {e["op"]: e for e in schedule}
    for k, op in enumerate(inst.operations):
        entry = by_op[k]
        duration = dict(op.modes)[entry["machine"]]
        assert entry["end"] - entry["start"] == duration, f"op {k}: duration"
    for job in range(inst.jobs):
        chain = sorted((o.index for o in inst.ops_of_job(job)))
        idx = {(o.job, o.index): i for i, o in enumerate(inst.operations)}
        for a, b in zip(chain, chain[1:]):
            assert by_op[idx[(job, a)]]["end"] <= by_op[idx[(job, b)]]["start"], \
                f"job {job}: precedence {a}->{b}"

    def overlapping(entries):
        entries = sorted(entries, key=lambda e: e["start"])
        return [(a, b) for a, b in zip(entries, entries[1:]) if b["start"] < a["end"]]

    for machine in range(1, inst.machines + 1):
        clash = overlapping([e for e in schedule if e["machine"] == machine])
        assert not clash, f"machine {machine}: overlap {clash[:1]}"
    if not check_tools:
        return
    for tool, copies in inst.tools.items():
        users = [e for e in schedule if e["tool"] == tool]
        if copies == 1 and users:
            clash = overlapping(users)
            assert not clash, f"tool {tool}: overlap {clash[:1]}"


def main(argv: Optional[Sequence[str]] = None) -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", default=str(here / "instances" / "upstream" / "RCFJSSP-main" / "Experiment 2" / "10"))
    parser.add_argument("--instance")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=float, default=300.0)
    parser.add_argument("--check", action="store_true",
                        help="compare with Table 8 of the paper")
    parser.add_argument("--no-tools", action="store_true",
                        help="drop the tool constraints (diagnostic)")
    args = parser.parse_args(argv)

    files = ([Path(args.instance)] if args.instance
             else sorted(Path(args.folder).glob("*.fjs")))
    rows, agree = [], 0
    print(f"{'instancia':10s} {'nosso':>6s} {'LB':>5s} {'status':>10s} "
          f"{'s':>7s}   {'publicado':>9s}  {'confere':>8s}")
    for path in files:
        inst = parse(path)
        out = solve(inst, args.workers, args.limit, use_tools=not args.no_tools)
        if "schedule" in out:
            verify(inst, out["schedule"], check_tools=not args.no_tools)
        table = PUBLISHED_BETA100 if args.no_tools else PUBLISHED_BETA10
        published = table.get(out["instance"])
        same = published is not None and out["makespan"] == published
        agree += bool(same)
        rows.append(out)
        mark = "sim" if same else ("NAO" if published is not None else "-")
        print(f"{out['instance']:10s} {str(out['makespan']):>6s} "
              f"{str(out['lower_bound']):>5s} {out['status']:>10s} "
              f"{out['seconds']:7.2f}   {str(published):>9s}  {mark:>8s}")

    if args.check:
        table = PUBLISHED_BETA100 if args.no_tools else PUBLISHED_BETA10
        total = sum(1 for r in rows if table.get(r["instance"]))
        print(f"\n{agree}/{total} reproduzem o ótimo publicado (Tabela 8, beta=10%)")
        ours = [r["makespan"] for r in rows if r["makespan"] is not None]
        if ours:
            print(f"  média nossa {sum(ours) / len(ours):.1f}   "
                  f"média publicada {103.4 if args.no_tools else 111.5}")
        below = [r["instance"] for r in rows
                 if table.get(r["instance"]) is not None
                 and r["makespan"] < table[r["instance"]]]
        if below:
            print(f"  ABAIXO do publicado em {below} -- falta restrição no "
                  f"modelo (buffers de máquina?)")
    out_path = here / "results" / (
        "cpsat_no_tools.json" if args.no_tools else "cpsat_beta10.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(
        [{k: v for k, v in r.items() if k != "schedule"} for r in rows],
        indent=1), encoding="utf-8")
    print(f"-> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
