"""Campanha FINAL do Experimento 4 (Tabela 10), sob protocolo unico. Experimentos X1 e X2.

Por que refazer
---------------
Os numeros do Experimento 4 hoje vem de **tres** execucoes diferentes, com
arquivos em tres lugares:

* ``results/campaign/exp4_*``        -- campanha de 14/08, modelo literal, 1 semente;
* ``results/auditor_literal_exp4.json`` -- execucao do auditor, com *hints* dos
  incumbentes, e **sem escalonamento gravado** em 9 das 10 instancias;
* ``results/ab_invariance/*``        -- o experimento pareado da invariancia
  (braco ``baseline`` = modelo literal, sem janelas).

O "melhor UB" do README e o maximo entre elas, e dois valores citados
(``lcbrtu_3`` = 388 e 387) **nao tem escalonamento em disco** -- o melhor
certificado hoje e 395. E o mesmo problema que o Set-I do SSP-NPM teve e resolveu
com uma campanha de protocolo unico e hash: e o que este script faz.

Os dois bracos
--------------
``--braco relato`` (X1)  o numero que vai para a Tabela do paper. Sem *hint*,
    sem cota superior, sem janela; CP-SAT de fabrica exceto ``workers``,
    ``max_time_in_seconds`` e ``random_seed``. 1800 s -- o limite da coluna CP do
    artigo (secao 5.2). ``--sementes 10`` da tres leituras honestas:
      * a semente 1 sozinha   -> comparavel a coluna CP deles (uma execucao);
      * o melhor das 10       -> comparavel ao ALNS-CP (melhor de 10 execucoes);
      * media e desvio        -> o que um parecerista vai pedir.

``--braco fecho`` (X2)   so para limites e provas. Parte do melhor escalonamento
    **certificado** (auditado sem solver) como *hint*. Nunca entra na coluna de
    UB do relato; entra, declarado, na coluna de LB/otimalidade.

Cada execucao grava o log completo do CP-SAT (``log_search_progress``) -- o que o
parecer de 14/08 exigiu para que um LB possa ser citado -- e um manifesto do
protocolo com o hash deste script, do modelo e da instancia.

Maquina: SO o i7-2600 (decisao de 30/09). O script recusa outra CPU, salvo com
``--qualquer-maquina`` (teste), e grava a CPU no hash do protocolo.

Uso (i7-2600, 4 nucleos / 8 fios; ~5 h por semente nas 10 instancias)
--------------------------------------------------------------------
    python experimentos/rcfjssp_final.py --braco relato --sementes 1 2 3 4 5 6 7 8 9 10
    python experimentos/rcfjssp_final.py --braco fecho  --instancias lcbrtu_0 lcbrtu_3 lcbrtu_5 lcbrtu_7 lcbrtu_8
    python experimentos/rcfjssp_final.py --relatorio
    python rcfjssp_audit.py --results results/final/relato_w8_1800

O fecho (X2) parte SO de escalonamentos do proprio i7 (do X1 ou do X6): rode-o
depois do X1.

O tempo e de relogio de parede (1800 s por execucao), entao o custo nao depende
da maquina; o que depende e a qualidade do resultado em 1800 s.

Retomavel: o que ja existe com o mesmo hash de protocolo e escalonamento gravado
nao e refeito; o que diverge e recomputado, nunca misturado.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from rcfjssp_core import parse                     # noqa: E402
from rcfjssp_reference import TABLE10              # noqa: E402

sys.path.insert(0, str(HERE))
import maquina                                     # noqa: E402

UP = ROOT / "instances" / "upstream" / "RCFJSSP-main" / "Experiment 4"
# Tudo que vai para o paper sai do i7-2600. A pasta continua results/final --
# e onde o X1 ja em curso no i7 (30/09) esta gravando; muda-la faria a retomada
# nao enxergar o que ja foi feito.
OUT = ROOT / "results" / "final"
STEMS = [f"lcbrtu_{n}" for n in range(10)]

# Onde procurar escalonamentos certificados para o braco "fecho": SO os do i7.
# As campanhas de agosto (mini-PC Ryzen) nao entram no paper -- nem como hint,
# porque um LB provado a partir delas dependeria de uma execucao que o texto
# nao pode citar. --aceita-historico as inclui, apenas para teste.
CERT_GLOBS_I7 = ["results/final/relato_*/*.json",
                 "results/final/cpo_exp4/*.json"]
CERT_GLOBS_HISTORICO = ["results/campaign/exp4_*_all.json",
                        "results/ab_invariance/*.json"]
CERT_GLOBS = list(CERT_GLOBS_I7)


def sha(path: Path, n: int = 16) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:n]


def protocol(braco: str, workers: int, limit: float) -> dict:
    p = {"braco": braco, "workers": workers, "max_time_in_seconds": limit,
         "solver": "OR-Tools CP-SAT, parametros de fabrica salvo workers, "
                   "tempo e semente",
         "hint": braco == "fecho",
         "modelo": "rcfjssp_full.build(inst, machine_buffers=True, windows=None)",
         "sha_rcfjssp_full": sha(ROOT / "rcfjssp_full.py"),
         "sha_rcfjssp_core": sha(ROOT / "rcfjssp_core.py"),
         "sha_script": sha(Path(__file__)),
         # a CPU entra no hash: execucoes de maquinas diferentes nunca se misturam
         "cpu": maquina.nome_cpu(),
         # De onde o fecho tira o hint. E substantivo: em 02/10 o X2 rodou com a
         # versao de 30/09, que ainda aceitava escalonamentos do Ryzen (o 339 de
         # lcbrtu_0). Com este campo, aquelas execucoes deixam de ser compativeis
         # e sao refeitas, em vez de aceitas como "ja feito".
         "hint_fontes": list(CERT_GLOBS) if braco == "fecho" else None}
    p["hash"] = hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest()[:16]
    return p


# O que define o NUMERO de uma execucao. sha_script fica de fora de proposito: o
# script muda por relatorio, guarda de maquina, mensagens -- nada disso muda o
# que o solver resolve. A versao de 30/09 incluia sha_script no hash, e o X1 ja
# comecou com ela; sem esta chave, qualquer edicao do script faria a retomada
# refazer 50 h de execucoes validas.
SUBSTANTIVOS = ("braco", "workers", "max_time_in_seconds", "hint", "modelo",
                "sha_rcfjssp_full", "sha_rcfjssp_core", "hint_fontes")


def compativeis(a: dict, b: dict) -> bool:
    return all(a.get(k) == b.get(k) for k in SUBSTANTIVOS)


def certified_best(stem: str) -> Optional[dict]:
    """Menor makespan com escalonamento gravado E aprovado pelo auditor sem solver."""
    import rcfjssp_audit as audit
    from rcfjssp_reference import CONFIG
    inst = parse(UP / f"{stem}.fjs")
    best = None
    for pat in CERT_GLOBS:
        for f in glob.glob(str(ROOT / pat)):
            data = json.loads(Path(f).read_text(encoding="utf-8"))
            rows = data if isinstance(data, list) else [data]
            for row in rows:
                if row.get("instance") != stem or not row.get("schedule"):
                    continue
                problems = audit.check_schedule(inst, row["schedule"],
                                                CONFIG[("exp4", "all")],
                                                row["makespan"])
                if problems:
                    continue
                if best is None or row["makespan"] < best["makespan"]:
                    best = {"makespan": row["makespan"], "schedule": row["schedule"],
                            "source": os.path.relpath(f, ROOT)}
    return best


def run(stem: str, seed: int, braco: str, workers: int, limit: float,
        folder: Path, proto: dict) -> dict:
    from ortools.sat.python import cp_model
    import ortools
    import rcfjssp_full as m4

    inst = parse(UP / f"{stem}.fjs")
    model, starts, ends, release, presence = m4.build(inst, True, None)
    hint_src = None
    if braco == "fecho":
        cert = certified_best(stem)
        if cert:
            hint_src = {"makespan": cert["makespan"], "source": cert["source"]}
            for row in cert["schedule"]:
                k = row["op"]
                model.AddHint(starts[k], row["start"])
                model.AddHint(ends[k], row["end"])
                model.AddHint(release[k], row["release"])
                for m, _d in inst.operations[k].modes:
                    model.AddHint(presence[(k, m)], int(m == row["machine"]))

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = workers
    solver.parameters.max_time_in_seconds = limit
    solver.parameters.random_seed = seed
    solver.parameters.log_search_progress = True
    solver.parameters.log_to_stdout = False
    logdir = folder / "logs"
    logdir.mkdir(parents=True, exist_ok=True)
    logfile = logdir / f"{stem}_s{seed}.log"
    with logfile.open("w", encoding="utf-8") as fh:
        solver.log_callback = lambda line: fh.write(line + "\n")
        started = time.perf_counter()
        status = solver.Solve(model)
        seconds = round(time.perf_counter() - started, 1)

    ok = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    schedule = None
    if ok:
        schedule = []
        for k, op in enumerate(inst.operations):
            machine = next(m for m, _d in op.modes if solver.Value(presence[(k, m)]))
            schedule.append({"op": k, "job": op.job, "index": op.index,
                             "machine": machine, "tool": op.tool,
                             "start": solver.Value(starts[k]),
                             "end": solver.Value(ends[k]),
                             "release": solver.Value(release[k])})
    lb, cp, alns = TABLE10[stem]
    return {"instance": stem, "experiment": "exp4", "config": "all",
            "seed": seed, "braco": braco, "status": solver.StatusName(status),
            "makespan": int(solver.ObjectiveValue()) if ok else None,
            "lower_bound": int(solver.BestObjectiveBound()) if ok else None,
            "seconds": seconds, "schedule": schedule, "hint": hint_src,
            "their_lb": lb, "their_cp": cp, "their_alns": alns,
            "protocol_hash": proto["hash"],
            "log": os.path.relpath(logfile, ROOT),
            "maquina": maquina.descreve(),
            "provenance": {"ortools": getattr(ortools, "__version__", "?"),
                           "python": platform.python_version(),
                           "platform": f"{platform.system()} {platform.machine()}",
                           "instance_sha256": sha(UP / f"{stem}.fjs", 32)}}


def report(root: Path = OUT) -> None:
    for folder in sorted(root.glob("*")):
        rows = [json.loads(p.read_text(encoding="utf-8"))
                for p in folder.glob("lcbrtu_*.json")]
        if not rows:
            continue
        print(f"\n== {folder.name}  ({len(rows)} execucoes)")
        cpus = sorted({(r.get("maquina") or {}).get("cpu")
                       or (r.get("provenance") or {}).get("cpu", "?") for r in rows})
        print(f"   CPU(s): {'; '.join(cpus)}")
        if any((r.get("maquina") or {}).get("maquina_do_paper") is False for r in rows):
            print("   ATENCAO: ha execucoes fora do i7-2600 nesta pasta -- nao citar.")
        sem = [f"{r['instance']}/s{r['seed']}" for r in rows if r["makespan"] is None]
        if sem:
            print(f"   sem solucao em 1800 s: {', '.join(sem)}")
        print(f"{'inst':>9s} {'n':>3s} {'s1':>5s} {'melhor':>6s} {'media':>7s} "
              f"{'dp':>5s} {'LBmax':>6s} {'opt':>4s} | {'LBd':>4s} {'CPd':>4s} {'ALNSd':>5s}")
        tot = {"s1": [], "best": [], "cp": [], "alns": []}
        for stem in STEMS:
            rs = [r for r in rows if r["instance"] == stem and r["makespan"] is not None]
            if not rs:
                continue
            ub = [r["makespan"] for r in rs]
            s1 = next((r["makespan"] for r in rs if r["seed"] == 1), None)
            lbs = [r["lower_bound"] for r in rs]
            opt = sum(r["status"] == "OPTIMAL" for r in rs)
            lb, cp, alns = TABLE10[stem]
            dp = statistics.pstdev(ub) if len(ub) > 1 else 0.0
            print(f"{stem:>9s} {len(rs):3d} {str(s1):>5s} {min(ub):6d} "
                  f"{statistics.mean(ub):7.1f} {dp:5.1f} {max(lbs):6d} {opt:4d} | "
                  f"{lb:4d} {cp:4d} {alns:5d}")
            if s1 is not None:
                tot["s1"].append(s1)
            tot["best"].append(min(ub)); tot["cp"].append(cp); tot["alns"].append(alns)
        if len(tot["best"]) == 10:
            print(f"{'media':>9s}     {statistics.mean(tot['s1']) if len(tot['s1']) == 10 else float('nan'):5.1f} "
                  f"{statistics.mean(tot['best']):6.1f}   (CP deles {statistics.mean(tot['cp']):.1f}, "
                  f"ALNS-CP {statistics.mean(tot['alns']):.1f})")


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--braco", choices=("relato", "fecho"), default="relato")
    p.add_argument("--sementes", type=int, nargs="*", default=[1])
    p.add_argument("--instancias", nargs="*", default=STEMS)
    # 8 = os fios do i7-2600 (4 nucleos / 8 fios) em que a campanha final roda.
    # E tambem o numero de nucleos do Xeon E5-2650 dos autores.
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--limite", type=float, default=1800.0)
    p.add_argument("--tag", default="", help="sufixo da pasta (ex.: _w8 para a ablacao)")
    p.add_argument("--saida", default=str(OUT),
                   help="raiz de saida (padrao results/i7/final; use outra para fumaca)")
    p.add_argument("--relatorio", action="store_true")
    p.add_argument("--certificados", action="store_true",
                   help="so lista o melhor escalonamento certificado por instancia")
    p.add_argument("--qualquer-maquina", action="store_true",
                   help="roda fora do i7-2600 (so teste; resultado marcado)")
    p.add_argument("--aceita-historico", action="store_true",
                   help="inclui as campanhas de agosto (Ryzen) como fonte de hint/certificado")
    args = p.parse_args(argv)

    if args.aceita_historico:
        CERT_GLOBS.extend(CERT_GLOBS_HISTORICO)

    if args.relatorio:
        report(Path(args.saida))
        return 0
    if args.certificados:
        for stem in args.instancias:
            c = certified_best(stem)
            print(f"{stem:>9s}  {c['makespan'] if c else None!s:>5s}  "
                  f"{c['source'] if c else '-'}")
        return 0

    maquina.exige_i7(args.qualquer_maquina)
    proto = protocol(args.braco, args.workers, args.limite)
    folder = Path(args.saida) / f"{args.braco}_w{args.workers}_{int(args.limite)}{args.tag}"
    folder.mkdir(parents=True, exist_ok=True)
    # Hashes aceitos na retomada: o atual e os de manifestos anteriores desta
    # pasta que coincidem nos campos substantivos (ver SUBSTANTIVOS).
    aceitos = {proto["hash"]}
    manifest = folder / "protocolo.manifest"
    history = folder / "protocolos_anteriores.jsonl"
    olds = []
    if history.exists():
        olds += [json.loads(l) for l in history.read_text(encoding="utf-8").splitlines() if l.strip()]
    if manifest.exists():
        prev = json.loads(manifest.read_text(encoding="utf-8"))
        if prev.get("hash") != proto["hash"]:
            olds.append(prev)
            with history.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(prev) + "\n")
    for prev in olds:
        if compativeis(prev, proto):
            aceitos.add(prev["hash"])
        else:
            print(f"AVISO: protocolo anterior {prev.get('hash')} difere em campo "
                  f"substantivo; suas execucoes serao REFEITAS, nao misturadas.", flush=True)
    # Extensao .manifest de proposito: o auditor le todo *.json da pasta.
    manifest.write_text(json.dumps(proto, indent=1), encoding="utf-8")
    print(f"protocolo {proto['hash']} -> {os.path.relpath(folder, ROOT)}", flush=True)

    for seed in args.sementes:
        for stem in args.instancias:
            target = folder / f"{stem}_s{seed}.json"
            if target.exists():
                old = json.loads(target.read_text(encoding="utf-8"))
                # Feito = mesmo protocolo e (solucao gravada, ou os 1800 s gastos
                # sem solucao). Sem a segunda condicao, um UNKNOWN honesto seria
                # refeito para sempre a cada retomada.
                spent = (old.get("seconds") or 0) >= 0.99 * args.limite
                if old.get("protocol_hash") in aceitos and (old.get("schedule") or spent):
                    print(f"{stem} s{seed}: ja feito ({old['makespan']})", flush=True)
                    continue
            if args.braco == "fecho" and certified_best(stem) is None:
                print(f"{stem}: sem escalonamento certificado do i7 para usar de hint "
                      f"-- rode o X1 antes do X2. Pulando.", flush=True)
                continue
            row = run(stem, seed, args.braco, args.workers, args.limite, folder, proto)
            tmp = target.with_suffix(".tmp")
            tmp.write_text(json.dumps(row, indent=1), encoding="utf-8")
            os.replace(tmp, target)
            print(f"{stem} s{seed}: {row['status']} UB {row['makespan']} "
                  f"LB {row['lower_bound']} {row['seconds']}s "
                  f"(ALNS-CP {row['their_alns']}, LB deles {row['their_lb']})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
