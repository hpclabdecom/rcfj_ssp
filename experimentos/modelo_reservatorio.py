"""O mesmo modelo do Box I, com as Eqs. (12)-(13) pela restricao nativa de reservatorio.

``rcfjssp_full.build`` codifica os reservatorios com booleanos de ordem par a par
(evento j antes do evento i), quadraticos no numero de eventos. Esta e a
codificacao validada (110/110 nas Tabelas 7-9) e a do exato do paper (X1).

Para a heuristica (X8) usa-se a restricao ``AddReservoirConstraint`` do CP-SAT,
que impoe exatamente o mesmo: o nivel em qualquer instante = soma das variacoes
dos eventos com tempo <= esse instante, dentro de [min, max]. Eq. (12): cada
recurso >= 0 (estoque inicial zero, conferido). Eq. (13): a soma dos recursos
guardados em cada buffer WIP <= capacidade.

Medido em 02/10/2026 (VM de teste, 2 nucleos): primeira solucao viavel em 5-12 s
em lcbrtu_3 e lcbrtu_5, contra NENHUMA em 50 s com a codificacao par a par -- e
nenhuma em 40 s mesmo sem buffers de maquina, mas 3 s sem recursos: o gargalo de
viabilidade e a codificacao dos reservatorios. Os escalonamentos produzidos
passam no auditor sem solver (``rcfjssp_audit.check_schedule``), que e quem
decide se um resultado vale -- nao este arquivo.

O limite inferior desta codificacao e mais fraco (259 x 310 em lcbrtu_3); por
isso ela serve a heuristica e NAO substitui o exato do X1/X2.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import rcfjssp_full as m4          # noqa: E402

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
        for uid, qty in inst.required[job].items():          # consumido no inicio
            per_res.setdefault(uid, []).append((job_start[job], -qty))
        for uid, qty in inst.produced[job].items():          # produzido no fim
            per_res.setdefault(uid, []).append((job_end[job], +qty))

    for uid, ev in per_res.items():                           # Eq. (12)
        if inst.nonrenewable[uid][1] != 0:
            raise ValueError("estoque inicial != 0: o artigo supoe zero (sec. 3.1)")
        model.AddReservoirConstraint([t for t, _ in ev], [d for _, d in ev], 0, BIG)
    for buf, cap in inst.wip.items():                         # Eq. (13)
        ev = [e for uid, lst in per_res.items()
              if inst.nonrenewable[uid][0] == buf for e in lst]
        if ev:
            model.AddReservoirConstraint([t for t, _ in ev], [d for _, d in ev], -BIG, cap)
    return model, starts, ends, release, presence
