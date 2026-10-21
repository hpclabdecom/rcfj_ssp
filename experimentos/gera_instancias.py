from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from rcfjssp_core import parse  # noqa: E402

UPSTREAM4 = ROOT / "instances" / "upstream" / "RCFJSSP-main" / "Experiment 4"
HELDOUT = ROOT / "instances" / "heldout"
SCALED = ROOT / "instances" / "scaled10"

RULES = dict(
    jobs_small=(10, 15), machines_small=(5, 10),
    jobs_large=(20, 27), machines_large=(8, 12), ops_large=(200, 300),
    ops_per_job=(8, 12), modes=(2, 4), processing=(5, 20),
    utilities=(1, 3), utility_cap=(80, 90, 100), rate=(1, 5),
    tools=(1, 5), tool_copies_fraction=0.25,
    buffer=(0, 3),
    resources=8, wip_buffers=2, stage1_resources=(1, 4),
    quantity_step=10, produce_qty=(50, 250), consume_min=40,
    wip_cap_fraction=(0.25, 0.40),
    budget_seconds_per_operation=4,
)


def rnd_qty(rng, lo, hi, step=10):
    return step * rng.randint(lo // step, hi // step)


def split_total(rng, total, parts, step, minimum):
    if total < parts * minimum:
        raise ValueError("total too small to split")
    units = total // step
    base = minimum // step
    free = units - parts * base
    cuts = sorted(rng.randint(0, free) for _ in range(parts - 1))
    shares = [b - a for a, b in zip([0] + cuts, cuts + [free])]
    return [step * (base + s) for s in shares]


def generate(rng, large: bool, seed_pair):
    R = RULES
    while True:
        jobs = rng.randint(*(R["jobs_large"] if large else R["jobs_small"]))
        machines = rng.randint(*(R["machines_large"] if large else R["machines_small"]))
        ops_per_job = [rng.randint(*R["ops_per_job"]) for _ in range(jobs)]
        n_ops = sum(ops_per_job)
        if not large or R["ops_large"][0] <= n_ops <= R["ops_large"][1]:
            break
    n_util = rng.randint(*R["utilities"])
    n_tool = rng.randint(*R["tools"])
    utilities = {u: rng.choice(R["utility_cap"]) for u in range(1, n_util + 1)}
    buffers = [rng.randint(*R["buffer"]) for _ in range(machines)]
    operations = []
    tool_users = {t: 0 for t in range(1, n_tool + 1)}
    for j in range(jobs):
        for _ in range(ops_per_job[j]):
            tool = rng.randint(1, n_tool)
            tool_users[tool] += 1
            k = rng.randint(*R["modes"])
            ms = rng.sample(range(1, machines + 1), k)
            modes = [(m, rng.randint(*R["processing"]),
                      [(u, rng.randint(*R["rate"])) for u in range(1, n_util + 1)]) for m in ms]
            operations.append((j, tool, modes))
    tools = {t: math.ceil(R["tool_copies_fraction"] * n) for t, n in tool_users.items()}
    flex = statistics.mean(len(m) for _, _, m in operations)

    k1 = rng.randint(*R["stage1_resources"])
    stage1 = list(range(1, k1 + 1))
    stage2 = list(range(k1 + 1, R["resources"] + 1))
    nA = round(jobs / 3)
    nB = round(jobs / 3)
    nC = jobs - nA - nB
    tierA = list(range(0, nA))
    tierB = list(range(nA, nA + nB))
    tierC = list(range(nA + nB, jobs))
    required = [dict() for _ in range(jobs)]
    produced = [dict() for _ in range(jobs)]
    step, (qlo, qhi), cmin = R["quantity_step"], R["produce_qty"], R["consume_min"]
    totals = {}
    for r in stage1:
        for j in tierA:
            produced[j][r] = rnd_qty(rng, qlo, qhi, step)
        totals[r] = sum(produced[j][r] for j in tierA)
        for j, q in zip(tierB, split_total(rng, totals[r], len(tierB), step, cmin)):
            required[j][r] = q
    for r in stage2:
        for j in tierB:
            produced[j][r] = rnd_qty(rng, qlo, qhi, step)
        totals[r] = sum(produced[j][r] for j in tierB)
        for j, q in zip(tierC, split_total(rng, totals[r], len(tierC), step, cmin)):
            required[j][r] = q
    nonrenewable = {r: (1 if r in stage1 else 2, 0, totals[r]) for r in range(1, R["resources"] + 1)}
    wip = {}
    for b, (rs, producers) in {1: (stage1, tierA), 2: (stage2, tierB)}.items():
        flow = sum(totals[r] for r in rs)
        frac = rng.uniform(*R["wip_cap_fraction"])
        single = max(sum(produced[j][r] for r in rs) for j in producers)
        wip[b] = max(step * math.ceil(frac * flow / step), single)

    lines = [f"{jobs} {machines} {flex:.2f} {n_util} {n_tool} {R['wip_buffers']} {R['resources']} "
             f"{seed_pair[0]} {seed_pair[1]}",
             " ".join(map(str, buffers))]
    lines += [f"{u} {c}" for u, c in utilities.items()]
    lines += [f"{t} {c}" for t, c in tools.items()]
    lines += [f"{b} {c}" for b, c in wip.items()]
    lines += [f"{r} {b} {s} {m}" for r, (b, s, m) in nonrenewable.items()]
    for j in range(jobs):
        parts = [str(len(required[j]))]
        for r, q in required[j].items():
            parts += [str(r), str(q)]
        parts.append(str(len(produced[j])))
        for r, q in produced[j].items():
            parts += [str(r), str(q)]
        ops = [o for o in operations if o[0] == j]
        parts.append(str(len(ops)))
        for _, tool, modes in ops:
            parts += [str(tool), str(len(modes))]
            for m, pt, rates in modes:
                parts += [str(m), str(pt)]
                for u, rt in rates:
                    parts += [str(u), str(rt)]
        lines.append(" ".join(parts))
    return "\n".join(lines) + "\n", n_ops


def feasible_first_solution(path: Path, seconds: float, workers: int) -> bool:
    import rcfjssp_lns as L
    inst = parse(path)
    return L.construcao(inst, True, workers, seconds, 1) is not None


def write_set(out: Path, seed: int, verify_seconds: float, workers: int):
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    budgets, rows = {}, []
    specs = [(f"rcfj_h_{i}", False) for i in range(10)] + [(f"rcfj_hl_{i}", True) for i in range(5)]
    for stem, large in specs:
        attempt = 0
        while True:
            attempt += 1
            seed_pair = (rng.randint(1000, 9999), rng.randint(1000, 9999))
            text, n_ops = generate(rng, large, seed_pair)
            path = out / f"{stem}.fjs"
            path.write_text(text, encoding="utf-8", newline="\n")
            inst = parse(path)
            assert inst.n_operations == n_ops and abs(inst.flexibility - statistics.mean(
                len(o.modes) for o in inst.operations)) < 0.005
            ok = feasible_first_solution(path, verify_seconds, workers) if verify_seconds > 0 else True
            if ok:
                break
            print(f"{stem}: attempt {attempt} had no first feasible solution in {verify_seconds} s; resampling",
                  flush=True)
        budgets[stem] = RULES["budget_seconds_per_operation"] * n_ops
        rows.append((stem, inst.jobs, inst.machines, n_ops, inst.flexibility, len(inst.utilities),
                     len(inst.tools), budgets[stem]))
        print(f"{stem}: jobs {inst.jobs} machines {inst.machines} ops {n_ops} flex {inst.flexibility:.2f} "
              f"budget {budgets[stem]} s", flush=True)
    (out / "budgets.json").write_text(json.dumps(
        {"rule": f"T = {RULES['budget_seconds_per_operation']} s x number of operations",
         "seconds": budgets}, indent=1), encoding="utf-8", newline="\n")
    sums = []
    for f in sorted(out.glob("*.fjs")) + [out / "budgets.json"]:
        sums.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}")
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8", newline="\n")
    (out / "GENERATION.json").write_text(json.dumps(
        {"generator_seed": seed, "rules": RULES, "verification_seconds": verify_seconds,
         "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16],
         "instances": [dict(zip(("stem", "jobs", "machines", "operations", "flexibility",
                                 "utilities", "tools", "budget_s"), r)) for r in rows]},
        indent=1), encoding="utf-8", newline="\n")


def write_scaled(out: Path, factor: int, stems):
    out.mkdir(parents=True, exist_ok=True)
    import rcfjssp_lns as L
    budgets = {}
    for stem in stems:
        inst = parse(UPSTREAM4 / f"{stem}.fjs")
        tokens = (UPSTREAM4 / f"{stem}.fjs").read_text(encoding="utf-8").split()
        pos = 0
        pos += 9 + inst.machines + 2 * len(inst.utilities) + 2 * len(inst.tools) + 2 * len(inst.wip) \
            + 4 * len(inst.nonrenewable)
        nu = len(inst.utilities)
        for j in range(inst.jobs):
            pos += 1 + 2 * len(inst.required[j]) + 1 + 2 * len(inst.produced[j])
            n_ops = int(tokens[pos]); pos += 1
            for _ in range(n_ops):
                n_modes = int(tokens[pos + 1]); pos += 2
                for _ in range(n_modes):
                    tokens[pos + 1] = str(int(tokens[pos + 1]) * factor)
                    pos += 2 + 2 * nu
        assert pos == len(tokens)
        new = f"{stem}_x{factor}"
        (out / f"{new}.fjs").write_text(" ".join(tokens) + "\n", encoding="utf-8", newline="\n")
        chk = parse(out / f"{new}.fjs")
        assert all(t % factor == 0 for o in chk.operations for _, t in o.modes)
        budgets[new] = L.T_ALNS[stem]
        print(f"{new}: processing times x{factor}, budget {budgets[new]} s", flush=True)
    (out / "budgets.json").write_text(json.dumps(
        {"rule": "same Table 10 budget as the unscaled instance", "seconds": budgets}, indent=1),
        encoding="utf-8", newline="\n")
    sums = [f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}" for f in sorted(out.glob("*"))
            if f.name != "SHA256SUMS"]
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8", newline="\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default=str(HELDOUT))
    ap.add_argument("--seed", type=int, default=20261021)
    ap.add_argument("--verificar", type=float, default=60.0,
                    help="seconds given to CP-SAT to find a first feasible schedule of each instance (0 = skip)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--escala10", action="store_true",
                    help="instead of the held-out set, write lcbrtu_3/5/8 with processing times x10")
    a = ap.parse_args(argv)
    if a.escala10:
        write_scaled(SCALED, 10, ["lcbrtu_3", "lcbrtu_5", "lcbrtu_8"])
    else:
        write_set(Path(a.saida), a.seed, a.verificar, a.workers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
