from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from rcfjssp_core import Instance, parse
from rcfjssp_reference import CONFIG, TABLE10, published_for
import maquina

UP = ROOT / "instances" / "upstream" / "RCFJSSP-main"
MODEL_VERSION = "2026-09-30-cpo-boxI-literal"

STEMS = {"1": [f"lcb{n}" for n in range(10)],
         "2": [f"t_{n}" for n in range(10)],
         "3": [f"r_{n}" for n in range(10)],
         "4": [f"lcbrtu_{n}" for n in range(10)]}
CONFIGS = {"1": ("declared", "zero", "unlimited"),
           "2": ("10", "25", "50", "75", "100"),
           "3": ("small", "large", "none"),
           "4": ("all",)}


LEITURAS = {
    "fiel":              "literal Box I with the transcription decisions documented in the README",
    "max_recurso":       "alternative reading: the max field bounds each resource (level <= max)",
    "maq_buffers_exp3":  "alternative reading: machine buffers also applied in Experiment 3",
    "pasta25_small":     "alternative reading: 'Small buffers' read as the folder 25",
    "eq12_sem_wip":      "alternative reading: 'unlimited WIP' (Eq. 12 kept, Eq. 13 removed)",
    "buffer_restritivo": "alternative reading: blocking if y_k = 0, waiting <= y_k at every instant if y_k > 0",
    "buffer_global":     "alternative reading: Eq. (9) without the interval, Y_k <= y_k at every instant, also with y_k = 0 (no-wait)",
}


def spec_for(exp: str, config: str, leitura: str) -> dict:
    spec = dict(CONFIG[(f"exp{exp}", config)])
    if exp == "3" and leitura == "maq_buffers_exp3":
        spec["machine_buffers"] = "declared"
    if exp == "3" and leitura == "pasta25_small" and config == "small":
        spec["folder"] = "Experiment 3/25"
    if exp == "3" and leitura == "eq12_sem_wip" and config == "none":
        spec["resources"], spec["wip"] = True, False
    spec["leitura"] = leitura
    return spec


def load_instance(exp: str, stem: str, config: str, spec: Optional[dict] = None) -> Instance:
    spec = spec or CONFIG[(f"exp{exp}", config)]
    inst = parse(UP / spec["folder"] / f"{stem}.fjs")
    if not spec["resources"]:
        inst = copy.deepcopy(inst)
        inst.required = [{} for _ in inst.required]
        inst.produced = [{} for _ in inst.produced]
    return inst


def build(inst: Instance, spec: dict):
    from docplex.cp.model import CpoModel
    import docplex.cp.modeler as cm

    mdl = CpoModel(name=Path(inst.path).stem)
    horizon = inst.horizon() * 2
    mb = spec["machine_buffers"]

    tau: Dict[int, object] = {}
    phi: Dict[tuple, object] = {}
    phib: Dict[tuple, object] = {}
    by_machine: Dict[int, list] = {}
    util: Dict[int, list] = {}
    tool_pulses: Dict[int, list] = {}

    for i, op in enumerate(inst.operations):
        tau[i] = mdl.interval_var(end=(0, horizon), name=f"tau_{i}")
        modes = []
        for slot, (k, eta) in enumerate(op.modes):
            a = mdl.interval_var(size=eta, optional=True, end=(0, horizon),
                                 name=f"phi_{i}_{k}")
            phi[(i, k)] = a
            modes.append(a)
            by_machine.setdefault(k, []).append(a)
            if spec["utilities"]:
                for uid, rate in op.rates[slot]:
                    if rate:
                        util.setdefault(uid, []).append(cm.pulse(a, rate))
            if mb in ("declared", "zero"):
                b = mdl.interval_var(optional=True, end=(0, horizon),
                                     name=f"phib_{i}_{k}")
                phib[(i, k)] = b
                mdl.add(cm.presence_of(b) == cm.presence_of(a))
                mdl.add(cm.start_at_end(b, a))
        mdl.add(cm.alternative(tau[i], modes))
        if spec["tools"] and op.tool is not None and op.tool in inst.tools:
            tool_pulses.setdefault(op.tool, []).append(cm.pulse(tau[i], 1))

    index = {(o.job, o.index): n for n, o in enumerate(inst.operations)}
    first, last = {}, {}
    for job in range(inst.jobs):
        chain = sorted(o.index for o in inst.ops_of_job(job))
        for a, b in zip(chain, chain[1:]):
            i, j = index[(job, a)], index[(job, b)]
            mdl.add(cm.end_before_start(tau[i], tau[j]))
            for k, _eta in inst.operations[i].modes:
                if (i, k) in phib:
                    mdl.add(cm.end_at_start(phib[(i, k)], tau[j]))
        first[job] = index[(job, chain[0])]
        last[job] = index[(job, chain[-1])]

    for k, ivs in by_machine.items():
        mdl.add(cm.no_overlap(mdl.sequence_var(ivs, name=f"sigma_{k}")))

    for uid, pulses in util.items():
        mdl.add(cm.sum(pulses) <= inst.utilities[uid])

    for r, pulses in tool_pulses.items():
        mdl.add(cm.sum(pulses) <= inst.tools[r])

    if mb in ("declared", "zero"):
        for k in by_machine:
            y_k = inst.buffers[k - 1] if mb == "declared" else 0
            members = [phib[(i, kk)] for (i, kk) in phib if kk == k]
            if not members:
                continue
            Y_k = cm.sum([cm.pulse(b, 1) for b in members])
            leitura = spec.get("leitura")
            if leitura == "buffer_global" or (leitura == "buffer_restritivo" and y_k > 0):
                mdl.add(cm.always_in(Y_k, (0, horizon), 0, y_k))
                continue
            for (i, kk), a in phi.items():
                if kk == k:
                    mdl.add(cm.always_in(Y_k, a, 0, y_k))

    if spec["resources"]:
        level = {}
        for r, (_z, start, _top) in inst.nonrenewable.items():
            terms = []
            for job in range(inst.jobs):
                q = inst.produced[job].get(r)
                if q:
                    terms.append(cm.step_at_end(tau[last[job]], q))
                q = inst.required[job].get(r)
                if q:
                    terms.append(-cm.step_at_start(tau[first[job]], q))
            if not terms:
                continue
            f = cm.sum(terms)
            if start:


                raise ValueError(f"{inst.path}: estoque inicial {start} != 0")
            level[r] = f
            mdl.add(f >= 0)
            if spec.get("leitura") == "max_recurso" and _top > 0:
                mdl.add(f <= _top)
        if spec["wip"]:
            for z, cap in inst.wip.items():
                stored = [level[r] for r, (zz, _s, _t) in inst.nonrenewable.items()
                          if zz == z and r in level]
                if stored:
                    mdl.add(cm.sum(stored) <= cap)

    cmax = cm.max([cm.end_of(tau[i]) for i in tau])
    mdl.add(cm.minimize(cmax))
    return mdl, tau, phi, phib


def find_cpo_exe(explicit: Optional[str] = None) -> Optional[str]:
    import glob
    import shutil
    if explicit:
        return explicit
    if os.environ.get("CPO_EXE"):
        return os.environ["CPO_EXE"]
    pats = [r"C:\Program Files\IBM\ILOG\CPLEX_Studio*\cpoptimizer\bin\x64_win64\cpoptimizer.exe",
            "/opt/ibm/ILOG/CPLEX_Studio*/cpoptimizer/bin/x86-64_linux/cpoptimizer",
            "/Applications/CPLEX_Studio*/cpoptimizer/bin/*/cpoptimizer"]
    for pat in pats:
        hits = sorted(glob.glob(pat))


        full = [h for h in hits if "community" not in h.lower()]
        if full:
            return full[-1]
        if hits:
            return hits[-1]
    return shutil.which("cpoptimizer")


CPO_EXE: Optional[str] = None


def prepara_ambiente(exe: Optional[str]) -> None:
    if not exe:
        return
    p = Path(exe)
    if len(p.parents) < 4:
        return
    studio = p.parents[3]
    sub = p.parent.name
    dirs = [studio / "cplex" / "bin" / sub, studio / "cpoptimizer" / "bin" / sub,
            studio / "opl" / "bin" / sub]
    atual = os.environ.get("PATH", "")
    novos = [str(d) for d in dirs if d.is_dir() and str(d) not in atual.split(os.pathsep)]
    if novos:
        os.environ["PATH"] = os.pathsep.join(novos + [atual])


def solve(inst: Instance, spec: dict, limit: float, workers: Optional[int],
          log_path: Optional[Path]) -> dict:
    prepara_ambiente(CPO_EXE)
    mdl, tau, phi, phib = build(inst, spec)
    params = dict(TimeLimit=limit, LogVerbosity="Terse" if log_path else "Quiet")
    if workers:
        params["Workers"] = workers
    extra = {"execfile": CPO_EXE} if CPO_EXE else {}
    started = time.perf_counter()
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as fh:
            sol = mdl.solve(log_output=fh, **extra, **params)
    else:
        sol = mdl.solve(log_output=None, **extra, **params)
    seconds = round(time.perf_counter() - started, 1)


    status = str(sol.get_solve_status()).upper() if sol else "UNKNOWN"
    schedule = None
    makespan = lb = raw_bound = None
    if sol and sol.is_solution():
        schedule = []
        index = {(o.job, o.index): n for n, o in enumerate(inst.operations)}
        succ = {}
        for job in range(inst.jobs):
            chain = sorted(o.index for o in inst.ops_of_job(job))
            for a, b in zip(chain, chain[1:]):
                succ[index[(job, a)]] = index[(job, b)]
        starts = {i: sol.get_var_solution(tau[i]).get_start() for i in tau}
        for i, op in enumerate(inst.operations):
            t = sol.get_var_solution(tau[i])
            machine = next(k for k, _e in op.modes
                           if sol.get_var_solution(phi[(i, k)]).is_present())
            release = starts[succ[i]] if i in succ else t.get_end()
            schedule.append({"op": i, "job": op.job, "index": op.index,
                             "machine": machine, "tool": op.tool,
                             "start": t.get_start(), "end": t.get_end(),
                             "release": release})
        makespan = int(sol.get_objective_values()[0])
        bounds = sol.get_objective_bounds()
        raw_bound = bounds[0] if bounds else None


        lb = int(round(raw_bound)) if raw_bound is not None else None
        if status == "OPTIMAL":
            lb = makespan

    info = dict(sol.get_solver_infos()) if sol else {}
    pinfo = dict(sol.get_process_infos()) if sol else {}
    return {"instance": Path(inst.path).stem, "schedule": schedule,
            "status": str(status), "makespan": makespan, "lower_bound": lb,
            "seconds": seconds, "cpo_raw_bound": raw_bound,


            "solve_time": (sol.get_solve_time() if sol else None),
            "total_time": info.get("TotalTime"),
            "solver": {"name": "IBM CP Optimizer",
                       "version": str(pinfo.get("SolverVersion", "?")),
                       "community_edition": pinfo.get("CommunityEdition"),
                       "params": params,
                       "workers_used": info.get("EffectiveWorkers")}}


def provenance(inst: Instance) -> dict:
    return {"python": platform.python_version(),
            "platform": f"{platform.system()} {platform.machine()}",
            "instance_sha256": hashlib.sha256(
                Path(inst.path).read_bytes()).hexdigest()[:32],
            "script_sha256": hashlib.sha256(
                Path(__file__).read_bytes()).hexdigest()[:16],
            "deterministic": False}


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--exp", choices=("1", "2", "3", "4"), required=True)
    p.add_argument("--config", default=None, help="padrao: todas do experimento")
    p.add_argument("--stems", nargs="*", default=None)
    p.add_argument("--limit", type=float, default=None,
                   help="padrao: 300 s (Exp. 1-3), 1800 s (Exp. 4, como o artigo)")
    p.add_argument("--workers", type=int, default=None,
                   help="padrao: o do CP Optimizer (o que os autores usaram)")
    p.add_argument("--out", default=None, help="pasta de saida (um JSON por celula)")
    p.add_argument("--check", action="store_true",
                   help="compara com as Tabelas 7-9 e sai 1 se divergir")
    p.add_argument("--leitura", choices=sorted(LEITURAS), default="fiel",
                   help="X5: leitura alternativa a testar (padrao: fiel)")
    p.add_argument("--cpo-exe", default=None,
                   help="caminho do cpoptimizer(.exe); padrao: CPO_EXE, depois o CPLEX Studio")
    p.add_argument("--qualquer-maquina", action="store_true",
                   help="roda fora do i7-2600 (so teste; resultado marcado)")
    p.add_argument("--permite-community", action="store_true",
                   help="aceita a edicao Community (so serve para fumaca dos Exps. 1-3)")
    args = p.parse_args(argv)

    maquina.exige_i7(args.qualquer_maquina)
    global CPO_EXE
    CPO_EXE = find_cpo_exe(args.cpo_exe)
    print(f"cpoptimizer: {CPO_EXE}", flush=True)

    limit = args.limit or (1800.0 if args.exp == "4" else 300.0)
    configs = [args.config] if args.config else list(CONFIGS[args.exp])
    stems = args.stems or STEMS[args.exp]
    out = Path(args.out) if args.out else None
    version = MODEL_VERSION + ("" if args.leitura == "fiel" else f"+{args.leitura}")
    suffix = "" if args.leitura == "fiel" else f"__{args.leitura}"
    bad = inconclusive = 0
    for config in configs:
        spec = spec_for(args.exp, config, args.leitura)
        for stem in stems:
            name = f"exp{args.exp}_{stem}_{config}{suffix}"
            target = out / f"{name}.json" if out else None
            if target and target.exists():
                old = json.loads(target.read_text(encoding="utf-8"))
                if old.get("model_version") == version and old.get("schedule"):
                    print(f"{stem:>9s} {config:>9s}  ja feito: {old['makespan']}")
                    continue
            inst = load_instance(args.exp, stem, config, spec)
            log = (out / "logs" / f"{name}.log") if out else None
            try:
                row = solve(inst, spec, limit, args.workers, log)
            except Exception as exc:
                if "size limit" in str(exc):
                    print(f"\nERRO: o cpoptimizer usado ({CPO_EXE}) e a edicao Community.\n"
                          "Aponte para o do CPLEX Optimization Studio: --cpo-exe ou "
                          "set CPO_EXE=...\\cpoptimizer\\bin\\x64_win64\\cpoptimizer.exe")
                    return 2
                if "not accessible" in str(exc) or "start failure" in str(exc):
                    print(f"\nERRO: o cpoptimizer ({CPO_EXE}) nao conseguiu iniciar -- em\n"
                          "geral a DLL do CPLEX nao foi achada. Feche este terminal, abra\n"
                          "um NOVO (para pegar o PATH da instalacao) e tente de novo. Se\n"
                          "persistir, rode o cpoptimizer.exe direto num terminal: o Windows\n"
                          "mostra o nome da DLL que falta.")
                    return 3
                raise
            if row["solver"].get("community_edition") and not args.permite_community:
                print(f"\nERRO: {CPO_EXE} e a edicao Community. Resultado descartado.\n"
                      "Use o do CPLEX Optimization Studio (--cpo-exe / CPO_EXE), ou "
                      "--permite-community para fumaca dos Exps. 1-3.")
                return 2
            pub = published_for(f"exp{args.exp}", stem, config)
            row.update(experiment=f"exp{args.exp}", config=config,
                       leitura=args.leitura, leitura_descricao=LEITURAS[args.leitura],
                       model_version=version, provenance=provenance(inst),
                       maquina=maquina.descreve(),
                       published=pub)
            if args.exp == "4":
                lb_, cp_, alns_ = TABLE10[stem]
                row.update(their_lb=lb_, their_cp=cp_, their_alns=alns_)
            flag = ""
            if pub is not None:


                if row["makespan"] == pub:
                    flag = "confere"
                elif row["status"] == "OPTIMAL":
                    flag = f"DIVERGE (publicado {pub})"
                    bad += 1
                else:
                    flag = f"INCONCLUSIVO, sem prova (publicado {pub})"
                    inconclusive += 1
            print(f"{stem:>9s} {config:>9s}  {row['status']:>10s}  "
                  f"UB {row['makespan']}  LB {row['lower_bound']}  "
                  f"{row['seconds']:7.1f}s  {flag}", flush=True)
            if target:
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp = target.with_suffix(".tmp")
                tmp.write_text(json.dumps(row, indent=1), encoding="utf-8")
                os.replace(tmp, target)
    if args.check:
        print(f"\nleitura '{args.leitura}': {bad} divergencia(s) provada(s), "
              f"{inconclusive} inconclusiva(s) por tempo")
        return 1 if (bad or inconclusive) else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
