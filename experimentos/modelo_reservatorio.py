from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import rcfjssp_full as m4

BIG = 10 ** 9


def build(inst, machine_buffers: bool = True):
    bare = copy.deepcopy(inst)
    bare.required = [{} for _ in inst.required]
    bare.produced = [{} for _ in inst.produced]
    model, starts, ends, release, presence = m4.build(bare, machine_buffers, None)

    index = {(o.job, o.index): k for k, o in enumerate(inst.operations)}
    job_start, job_end = {}, {}
    for job in range(inst.jobs):
        chain = sorted(o.index for o in inst.ops_of_job(job))
        job_start[job] = starts[index[(job, chain[0])]]
        job_end[job] = ends[index[(job, chain[-1])]]

    per_res = {}
    for job in range(inst.jobs):
        for uid, qty in inst.required[job].items():
            per_res.setdefault(uid, []).append((job_start[job], -qty))
        for uid, qty in inst.produced[job].items():
            per_res.setdefault(uid, []).append((job_end[job], +qty))

    for uid, ev in per_res.items():
        if inst.nonrenewable[uid][1] != 0:
            raise ValueError("estoque inicial != 0: o artigo supoe zero (sec. 3.1)")
        model.AddReservoirConstraint([t for t, _ in ev], [d for _, d in ev], 0, BIG)
    for buf, cap in inst.wip.items():
        ev = [e for uid, lst in per_res.items()
              if inst.nonrenewable[uid][0] == buf for e in lst]
        if ev:
            model.AddReservoirConstraint([t for t, _ in ev], [d for _, d in ev], -BIG, cap)
    return model, starts, ends, release, presence
