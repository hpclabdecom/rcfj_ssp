from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from rcfjssp_core import Instance, parse
from rcfjssp_reference import CONFIG, TABLE10, published_for

UP = HERE / "instances" / "upstream" / "RCFJSSP-main"
CAMPAIGN = HERE / "results" / "final" / "validacao"


def check_parse(inst: Instance) -> List[str]:
    problems = []
    calc = statistics.mean(len(o.modes) for o in inst.operations)
    if abs(calc - inst.flexibility) >= 0.005:
        problems.append(f"A: flexibilidade {calc:.3f} contra {inst.flexibility} "
                        f"no cabecalho")
    return problems


def check_schedule(inst: Instance, schedule: Sequence[dict], spec: dict,
                   reported: int) -> List[str]:
    problems = []
    n = len(inst.operations)
    if len(schedule) != n:
        return [f"B: {len(schedule)} entradas para {n} operacoes"]
    seen = {e["op"] for e in schedule}
    if seen != set(range(n)):
        return [f"B: operacoes ausentes ou repetidas: "
                f"{sorted(set(range(n)) - seen)[:5]}"]

    by_op = {e["op"]: e for e in schedule}
    for k, op in enumerate(inst.operations):
        e = by_op[k]
        allowed = dict(op.modes)
        if e["machine"] not in allowed:
            problems.append(f"B: op {k} na maquina {e['machine']}, permitidas "
                            f"{sorted(allowed)}")
            continue
        if e["end"] - e["start"] != allowed[e["machine"]]:
            problems.append(f"B: op {k} dura {e['end'] - e['start']}, "
                            f"deveria durar {allowed[e['machine']]}")
        if e["start"] < 0:
            problems.append(f"B: op {k} comeca em {e['start']}")


        if e.get("tool") != op.tool:
            problems.append(f"B: op {k} declara ferramenta {e.get('tool')}, "
                            f"a instancia exige {op.tool}")
        if e.get("job") != op.job or e.get("index") != op.index:
            problems.append(f"B: op {k} declara job/index "
                            f"{e.get('job')}/{e.get('index')}, "
                            f"a instancia diz {op.job}/{op.index}")


    index = {(o.job, o.index): k for k, o in enumerate(inst.operations)}
    for job in range(inst.jobs):
        chain = sorted(o.index for o in inst.ops_of_job(job))
        for a, b in zip(chain, chain[1:]):
            ea, eb = by_op[index[(job, a)]], by_op[index[(job, b)]]
            if eb["start"] < ea["end"]:
                problems.append(f"C: job {job}, op {a} termina em {ea['end']} "
                                f"e op {b} comeca em {eb['start']}")

            if "release" in ea and ea["release"] != eb["start"]:
                problems.append(f"C: job {job}, op {a} libera em "
                                f"{ea['release']}, sucessora comeca em "
                                f"{eb['start']} (Eq. 11)")
        last = by_op[index[(job, chain[-1])]]
        if "release" in last and last["release"] != last["end"]:
            problems.append(f"C: job {job}, ultima op libera em "
                            f"{last['release']}, termina em {last['end']}")


    def overlaps(entries, key_s="start", key_e="end"):
        entries = sorted(entries, key=lambda e: e[key_s])
        return [(a, b) for a, b in zip(entries, entries[1:])
                if b[key_s] < a[key_e]]

    blocking = spec["machine_buffers"] in ("declared", "zero")
    for machine in range(1, inst.machines + 1):
        on_it = [e for e in schedule if e["machine"] == machine]
        cap = (0 if spec["machine_buffers"] == "zero"
               else inst.buffers[machine - 1] if spec["machine_buffers"] == "declared"
               else None)
        if blocking and cap == 0:
            clash = overlaps(on_it, "start", "release")
            if clash:
                problems.append(f"D: maquina {machine} com bloqueio, "
                                f"ops {clash[0][0]['op']} e {clash[0][1]['op']} "
                                f"se sobrepoem")
        else:
            clash = overlaps(on_it)
            if clash:
                problems.append(f"D: maquina {machine}, ops "
                                f"{clash[0][0]['op']} e {clash[0][1]['op']} "
                                f"se sobrepoem")
            if blocking and cap is not None:


                events = []
                for e in on_it:
                    events += [(e["start"], +1), (e["release"], -1)]
                level = peak = 0
                for _t, d in sorted(events):
                    level += d
                    peak = max(peak, level)
                if peak > cap + 1:
                    problems.append(f"D: ocupacao da maquina {machine} chega a "
                                    f"{peak}, limite Eq.(9) e {cap + 1}")

    if spec["tools"]:
        for tool, copies in inst.tools.items():
            if not copies:
                continue
            users = [e for e in schedule if e["tool"] == tool]
            events = []
            for e in users:
                events += [(e["start"], +1), (e["end"], -1)]
            level = peak = 0
            for _t, d in sorted(events):
                level += d
                peak = max(peak, level)
            if peak > copies:
                problems.append(f"D: ferramenta {tool} usada {peak} vezes ao "
                                f"mesmo tempo, {copies} copias")

    if spec["utilities"]:
        for uid, ceiling in inst.utilities.items():
            events = []
            for k, op in enumerate(inst.operations):
                e = by_op[k]
                slot = next(i for i, (m, _d) in enumerate(op.modes)
                            if m == e["machine"])
                rate = dict(op.rates[slot]).get(uid, 0)
                if rate:
                    events += [(e["start"], rate), (e["end"], -rate)]
            level = peak = 0
            for _t, d in sorted(events):
                level += d
                peak = max(peak, level)
            if peak > ceiling:
                problems.append(f"D: utilidade {uid} chega a {peak}, "
                                f"teto {ceiling}")

    if spec["resources"] or spec["wip"]:
        job_start = {j: min(by_op[index[(j, o.index)]]["start"]
                            for o in inst.ops_of_job(j)) for j in range(inst.jobs)}
        job_end = {j: max(by_op[index[(j, o.index)]]["end"]
                          for o in inst.ops_of_job(j)) for j in range(inst.jobs)}
        events = []
        for job in range(inst.jobs):
            for uid, qty in inst.required[job].items():
                events.append((job_start[job], uid, -qty))
            for uid, qty in inst.produced[job].items():
                events.append((job_end[job], uid, +qty))
        levels = {uid: start for uid, (_b, start, _m)
                  in inst.nonrenewable.items()}
        for t in sorted({e[0] for e in events}):
            for _t, uid, delta in [e for e in events if e[0] == t]:
                levels[uid] = levels.get(uid, 0) + delta
            if spec["resources"]:
                for uid, level in levels.items():
                    if level < 0:
                        problems.append(f"D: recurso {uid} negativo ({level}) "
                                        f"em t={t}")
            if spec["wip"]:
                for buf, capacity in inst.wip.items():
                    total = sum(v for uid, v in levels.items()
                                if inst.nonrenewable[uid][0] == buf)
                    if total > capacity:
                        problems.append(f"D: buffer WIP {buf} em {total}, "
                                        f"capacidade {capacity} (t={t})")


    computed = max(e["end"] for e in schedule)
    if computed != reported:
        problems.append(f"E: makespan recalculado {computed}, reportado {reported}")
    return problems


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default=str(CAMPAIGN))
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--instancias", default=None,
                        help="folder holding <instance>.fjs when the results are not on the upstream benchmark")
    args = parser.parse_args(argv)
    inst_dir = Path(args.instancias) if args.instancias else None

    files = sorted(Path(args.results).glob("*.json"))
    if not files:
        print(f"nada em {args.results}")
        return 1

    counts = defaultdict(int)
    failures: List[str] = []
    mismatches: List[str] = []
    no_schedule: List[str] = []

    for path in files:
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            failures.append(f"{path.name}: nao e JSON valido")
            continue
        if not isinstance(row, dict) or "instance" not in row:
            counts["ignorados (nao e resultado de uma execucao)"] += 1
            continue
        key = (row.get("experiment"), row.get("config"))
        spec = CONFIG.get(key)
        if spec is None:
            failures.append(f"{path.name}: configuracao desconhecida {key}")
            continue
        inst = parse((inst_dir or (UP / spec["folder"])) / f"{row['instance']}.fjs")

        for problem in check_parse(inst):
            failures.append(f"{path.name}: {problem}")

        if row.get("makespan") is None:
            counts["sem solucao"] += 1
            continue
        schedule = row.get("schedule")
        if not schedule:
            no_schedule.append(path.name)
        else:
            problems = check_schedule(inst, schedule, spec, row["makespan"])
            for problem in problems:
                failures.append(f"{path.name}: {problem}")
            counts["verificados" if not problems else "com defeito"] += 1

        target = published_for(row["experiment"], row["instance"], row["config"])
        if target is not None:
            counts["comparados"] += 1
            if row["makespan"] == target:
                counts["conferem"] += 1
            else:
                mismatches.append(f"{path.name}: nosso {row['makespan']}, "
                                  f"publicado {target}")
        if args.verbose:
            print(f"  {path.name:34s} mk {row['makespan']:>5} "
                  f"{'ok' if not failures else ''}")

    print(f"\n{len(files)} arquivos lidos")
    for key in ("verificados", "com defeito", "comparados", "conferem",
                "sem solucao"):
        if counts[key]:
            print(f"  {key:14s} {counts[key]}")
    if no_schedule:
        print(f"\n  {len(no_schedule)} sem escalonamento gravado -- viabilidade "
              f"NAO auditada:\n    {', '.join(no_schedule[:6])}"
              f"{' ...' if len(no_schedule) > 6 else ''}")

    if failures:
        print(f"\nDEFEITOS (A-E) -- {len(failures)}:")
        for f in failures[:25]:
            print(f"  {f}")
    elif counts["verificados"]:
        print(f"\nA-E: nenhum defeito em {counts['verificados']} escalonamentos. "
              f"Todos viaveis, makespan confere com o reportado.")
    else:
        print("\nA-E: NADA foi verificado -- nenhum resultado trazia "
              "escalonamento. A ausencia de defeito aqui nao significa nada.")


    duals = [r for r in [json.loads(p.read_text(encoding="utf-8"))
                         for p in files]
             if isinstance(r, dict) and r.get("lower_bound") is not None]
    claimed_opt = [r for r in duals if r.get("status") == "OPTIMAL"]
    inconsistent = [r for r in claimed_opt
                    if r["lower_bound"] != r["makespan"]]
    print(f"\nDUAL -- o que este script NAO verifica")
    print(f"  {len(duals)} limites inferiores declarados; nenhum e recalculado "
          f"aqui.")
    print(f"  {len(claimed_opt)} declaram OPTIMAL; a unica checagem possivel "
          f"sem solver e LB = UB.")
    if inconsistent:
        print(f"  INCONSISTENTE em {len(inconsistent)}: "
              f"{[r['instance'] for r in inconsistent][:5]}")
        failures.append("dual: OPTIMAL com LB != UB")
    else:
        print("  LB = UB em todos os que se declaram OPTIMAL.")
    print("  Isso NAO e prova de otimalidade: 'status' e 'lower_bound' sao")
    print("  campos gravados pelo mesmo processo que os produziu. Para tratar")
    print("  um limite como resultado, reexecute o modelo e registre solver,")
    print("  versao, parametros e log -- ver results/README.md.")

    if mismatches:
        print(f"\nDIVERGENCIAS COM O ARTIGO (F) -- {len(mismatches)}:")
        for f in mismatches:
            print(f"  {f}")
        print("\n  Uma divergencia aqui tem tres causas possiveis e este script")
        print("  nao as distingue: (i) nosso modelo esta errado, (ii) a")
        print("  transcricao das Tabelas 7-9 esta errada, (iii) o artigo esta")
        print("  errado. Conferir a transcricao contra o PDF e a primeira coisa.")
    else:
        print("F: todo resultado com alvo publicado reproduz o alvo.")


    return 1 if (failures or mismatches) else 0


if __name__ == "__main__":
    raise SystemExit(main())
