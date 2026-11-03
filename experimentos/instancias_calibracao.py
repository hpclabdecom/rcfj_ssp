from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rcfjssp_core import Instance, Operation

DIR = ROOT / "instances" / "calibracao"


CALIBRACAO: List[Tuple[str, str, str]] = [
    ("mk06", "fjssp", "mk06.fjs"), ("mk10", "fjssp", "mk10.fjs"),
    ("16a", "fjssp", "16a.fjs"), ("17a", "fjssp", "17a.fjs"), ("18a", "fjssp", "18a.fjs"),
    ("la18", "bjssp", "la18.txt"), ("la25", "bjssp", "la25.txt"), ("la30", "bjssp", "la30.txt"),
    ("la35", "bjssp", "la35.txt"), ("la38", "bjssp", "la38.txt"),
]


SPEC = {
    "fjssp": dict(folder="calibracao", machine_buffers="off", tools=False,
                  utilities=False, resources=False, wip=False),
    "bjssp": dict(folder="calibracao", machine_buffers="zero", tools=False,
                  utilities=False, resources=False, wip=False),
}


def _nums(path: Path) -> List[int]:
    toks = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or not (s[0].isdigit()):
            continue
        toks += [int(float(x)) for x in s.split()]
    return toks


def _inst(path, jobs, machines, ops, buffers) -> Instance:
    flex = sum(len(o.modes) for o in ops) / len(ops)
    return Instance(path=str(path), jobs=jobs, machines=machines, flexibility=flex,
                    buffers=buffers, utilities={}, tools={}, wip={}, nonrenewable={},
                    operations=ops, required=[{} for _ in range(jobs)],
                    produced=[{} for _ in range(jobs)])


def le_fjssp(path: Path) -> Instance:
    linhas = [l.split() for l in path.read_text(encoding="utf-8", errors="ignore").splitlines()
              if l.strip() and l.strip()[0].isdigit()]
    jobs, machines = int(linhas[0][0]), int(linhas[0][1])
    brutos = []
    for row in linhas[1:1 + jobs]:
        t = [int(float(x)) for x in row]
        p, ops_job = 1, []
        for _ in range(t[0]):
            k = t[p]; p += 1
            modes = [(t[p + 2 * q], t[p + 2 * q + 1]) for q in range(k)]
            p += 2 * k
            ops_job.append(modes)
        if p != len(t):
            raise ValueError(f"{path}: job com {len(t) - p} numeros sobrando -- formato errado")
        brutos.append(ops_job)
    if len(linhas) != 1 + jobs:
        raise ValueError(f"{path}: {len(linhas) - 1} linhas de job para {jobs} jobs")
    base = 0 if any(m == 0 for job in brutos for modes in job for m, _ in modes) else 1
    ops: List[Operation] = []
    for j, job in enumerate(brutos):
        for i, modes in enumerate(job):
            mm = [(m - base + 1, d) for m, d in modes]
            ops.append(Operation(job=j, index=i, tool=None, modes=mm, rates=[[] for _ in mm]))
    maxm = max(m for o in ops for m, _ in o.modes)
    return _inst(path, jobs, max(machines, maxm), ops, [0] * max(machines, maxm))


def le_jssp_bloqueio(path: Path) -> Instance:
    t = _nums(path)
    jobs, machines = t[0], t[1]
    pos = 2
    ops: List[Operation] = []
    for j in range(jobs):
        for i in range(machines):
            m, d = t[pos], t[pos + 1]; pos += 2
            ops.append(Operation(job=j, index=i, tool=None, modes=[(m + 1, d)],
                                 rates=[[]]))
    if pos != len(t):
        raise ValueError(f"{path}: {len(t) - pos} numeros sobrando -- formato errado")
    return _inst(path, jobs, machines, ops, [0] * machines)


def carrega(familia: str, arquivo: str):
    p = Path(arquivo) if Path(arquivo).is_absolute() else DIR / arquivo
    if familia == "fjssp":
        return le_fjssp(p), False, SPEC["fjssp"]
    if familia == "bjssp":
        return le_jssp_bloqueio(p), True, SPEC["bjssp"]
    raise ValueError(familia)


if __name__ == "__main__":
    falta = [a for _, _, a in CALIBRACAO if not (DIR / a).exists()]
    if falta:
        print(f"faltam em {DIR}: {falta}")
        raise SystemExit(1)
    for nome, fam, arq in CALIBRACAO:
        inst, mb, _ = carrega(fam, arq)
        print(f"{nome:5s} {fam}: {inst.jobs} jobs, {inst.machines} maquinas, "
              f"{inst.n_operations} operacoes, flexibilidade {inst.flexibility:.2f}")
