"""Parser for the RCFJSSP ``.fjs`` format of Kasapidis et al. (EJOR 2025).

The repository README describes the per-machine layout incorrectly, in two
ways.  It says that for every available machine ``1 + |U|`` numbers are given
(the processing time and the utility rates).  The files carry the **machine
identifier** first, and the rates come as **(utility uid, rate) pairs**::

    <tool uid> <#machines>  [ <machine> <time> (<utility uid> <rate>) * |U| ] * #machines

so a mode costs ``2 + 2|U|`` numbers, not ``1 + |U|``.  The two errors hide
each other on Experiment 2, where ``|U| = 0`` and both readings would demand a
different count than the true one; only Experiment 4 exercises the rates.

Reading it the README's way silently misaligns every operation after the first
and still consumes a plausible number of tokens, so the mistake does not
announce itself.  :func:`parse` therefore asserts that the token stream is
consumed **exactly**, which is what makes the layout falsifiable rather than
merely plausible -- it is what rejected the first reading on Experiment 4.

A second, independent check: the third header field is the instance
flexibility, the mean number of machines per operation.  Recomputing it from
the parsed modes and comparing pins the layout without reference to any
solution.  It was that number, not inspection, that gave away ``2 + 2|U|``:
``2 + |U|`` implied a flexibility of 6.0 against a declared 3.02.

Header (nine numbers)::

    jobs  machines  flexibility  |U|  |T|  |W|  |R|  seed1  seed2

then one line of per-machine buffer capacities, then ``|U|`` utility lines
(id, ceiling), ``|T|`` tool lines (id, number of copies), ``|W|`` WIP buffer
lines (id, capacity) and ``|R|`` non-renewable lines (id, buffer, initial,
maximum).  Each job line is::

    <#required> [uid qty]*  <#produced> [uid qty]*  <#operations>  <operations>

**Tools with zero copies.**  Two of the ten beta=10% instances declare a tool
with ``0`` copies -- tool 5 of ``t_7`` and tool 2 of ``t_9``.  Taken literally
that forbids every operation needing it and the instance is infeasible, so
``0`` cannot mean zero.  The generator sets copies from a fraction beta of the
operations that require the tool, and rounds down; ``0`` is what a tool used by
few operations gets.  The reading that survives is *unconstrained*, and it is
not assumed here: :mod:`rcfjssp_cpsat` solves both readings and only one
reproduces the published optimum.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass
class Operation:
    job: int
    index: int                       # position within the job
    tool: Optional[int]              # tool uid, or None when unconstrained
    modes: List[Tuple[int, int]]     # (machine, processing time)
    rates: List[List[int]] = field(default_factory=list)   # per mode, per utility


@dataclass
class Instance:
    path: str
    jobs: int
    machines: int
    flexibility: float
    buffers: List[int]                       # per machine
    utilities: Dict[int, int]                # uid -> ceiling
    tools: Dict[int, int]                    # uid -> copies as declared
    wip: Dict[int, int]                      # uid -> capacity
    nonrenewable: Dict[int, Tuple[int, int, int]]   # uid -> (buffer, start, max)
    operations: List[Operation]
    required: List[Dict[int, int]]           # per job
    produced: List[Dict[int, int]]           # per job

    @property
    def n_operations(self) -> int:
        return len(self.operations)

    def ops_of_job(self, job: int) -> List[Operation]:
        return [o for o in self.operations if o.job == job]

    def users_of_tool(self, tool: int) -> List[Operation]:
        return [o for o in self.operations if o.tool == tool]

    def horizon(self) -> int:
        """Sum of the longest mode of every operation -- a safe upper bound."""
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
    take(2)                                   # generator seeds

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
            if tool < 0:                 # -1 = operation requires no tool
                tool = None
            modes, rates = [], []
            for _ in range(n_modes):
                machine, duration = take(2)
                modes.append((machine, duration))
                # (utility uid, rate) pairs -- see the module docstring
                pairs = [tuple(take(2)) for _ in range(n_util)]
                for uid, _rate in pairs:
                    if uid not in utilities:
                        raise ValueError(f"{path}: utility {uid} not declared "
                                         f"-- the per-mode layout is wrong")
                rates.append(pairs)
            operations.append(Operation(job, index, tool, modes, rates))

    # The layout is only established if nothing is left over: a wrong reading
    # of the per-machine block leaves a remainder or runs short.
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
