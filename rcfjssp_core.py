from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass
class Operation:
    job: int
    index: int
    tool: Optional[int]
    modes: List[Tuple[int, int]]
    rates: List[List[int]] = field(default_factory=list)


@dataclass
class Instance:
    path: str
    jobs: int
    machines: int
    flexibility: float
    buffers: List[int]
    utilities: Dict[int, int]
    tools: Dict[int, int]
    wip: Dict[int, int]
    nonrenewable: Dict[int, Tuple[int, int, int]]
    operations: List[Operation]
    required: List[Dict[int, int]]
    produced: List[Dict[int, int]]

    @property
    def n_operations(self) -> int:
        return len(self.operations)

    def ops_of_job(self, job: int) -> List[Operation]:
        return [o for o in self.operations if o.job == job]

    def users_of_tool(self, tool: int) -> List[Operation]:
        return [o for o in self.operations if o.tool == tool]

    def horizon(self) -> int:
        return sum(max(t for _m, t in o.modes) for o in self.operations)


def parse(path: str | Path) -> Instance:
    text = Path(path).read_text(encoding="utf-8")
    tokens = text.split()
    pos = 0

    def take(count: int = 1) -> List[int]:
        nonlocal pos
        chunk = tokens[pos:pos + count]
        if len(chunk) != count:
            raise ValueError(f"{path}: ran out of tokens at {pos}")
        pos += count
        return [int(float(x)) for x in chunk]

    n_jobs, n_machines = take(2)
    flexibility = float(tokens[pos]); pos += 1
    n_util, n_tool, n_wip, n_res = take(4)
    take(2)

    buffers = take(n_machines)
    utilities = {uid: cap for uid, cap in (take(2) for _ in range(n_util))}
    tools = {uid: copies for uid, copies in (take(2) for _ in range(n_tool))}
    wip = {uid: cap for uid, cap in (take(2) for _ in range(n_wip))}
    nonrenewable = {}
    for _ in range(n_res):
        uid, buf, start, top = take(4)
        nonrenewable[uid] = (buf, start, top)

    operations: List[Operation] = []
    required: List[Dict[int, int]] = []
    produced: List[Dict[int, int]] = []
    for job in range(n_jobs):
        (count,) = take(1)
        required.append({uid: qty for uid, qty in (take(2) for _ in range(count))})
        (count,) = take(1)
        produced.append({uid: qty for uid, qty in (take(2) for _ in range(count))})
        (n_ops,) = take(1)
        for index in range(n_ops):
            tool, n_modes = take(2)
            if tool < 0:
                tool = None
            modes, rates = [], []
            for _ in range(n_modes):
                machine, duration = take(2)
                modes.append((machine, duration))

                pairs = [tuple(take(2)) for _ in range(n_util)]
                for uid, _rate in pairs:
                    if uid not in utilities:
                        raise ValueError(f"{path}: utility {uid} not declared "
                                         f"-- the per-mode layout is wrong")
                rates.append(pairs)
            operations.append(Operation(job, index, tool, modes, rates))


    if pos != len(tokens):
        raise ValueError(f"{path}: {len(tokens) - pos} tokens left unread "
                         f"-- the per-machine layout is not what was assumed")

    return Instance(str(path), n_jobs, n_machines, flexibility, buffers,
                    utilities, tools, wip, nonrenewable, operations,
                    required, produced)


def summarise(inst: Instance) -> str:
    zero = [uid for uid, copies in inst.tools.items() if copies == 0]
    unused = [uid for uid in inst.tools if not inst.users_of_tool(uid)]
    return (f"{Path(inst.path).name:10s} jobs {inst.jobs:2d} machines "
            f"{inst.machines:2d} ops {inst.n_operations:3d} "
            f"tools {len(inst.tools):2d} flex {inst.flexibility:.2f} "
            f"horizon {inst.horizon():4d}"
            + (f"  copias=0: {zero}" if zero else "")
            + (f"  sem uso: {unused}" if unused else ""))


if __name__ == "__main__":
    import sys
    folder = Path(sys.argv[1] if len(sys.argv) > 1
                  else Path(__file__).parent / "instances" / "beta10")
    for f in sorted(folder.glob("*.fjs")):
        print(summarise(parse(f)))
