from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import platform
import random
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from rcfjssp_core import parse
from rcfjssp_reference import CONFIG, TABLE10
import maquina

UP = ROOT / "instances" / "upstream" / "RCFJSSP-main" / "Experiment 4"
OUT = ROOT / "results" / "final" / "heur_lns"
STEMS = [f"lcbrtu_{n}" for n in range(10)]


T_ALNS = {"lcbrtu_0": 623.45, "lcbrtu_1": 179.86, "lcbrtu_2": 476.44,
          "lcbrtu_3": 495.88, "lcbrtu_4": 604.69, "lcbrtu_5": 643.44,
          "lcbrtu_6": 231.97, "lcbrtu_7": 283.92, "lcbrtu_8": 800.39,
          "lcbrtu_9": 206.70}


P = dict(SUB_TIME=3.0, RHO0=0.30, RHO_MIN=0.10, RHO_MAX=0.60, RHO_STEP=1.15,
         CONSTR_FRAC=0.5, W_MIN=0.10, DECAY=0.9, VIZ=("janela", "maquinas",
         "material", "critica"))


def confere_t10() -> List[str]:
    txt = (ROOT / "paper" / "ref" / "kasapidis2025_texto.txt").read_text(encoding="utf-8")
    erros = []
    for stem, t in T_ALNS.items():
        m = re.search(rf"^\s*{stem.replace('_', '')}\s+(.*)$", txt, re.M)
        nums = re.findall(r"\d+\.\d+|\d+", m.group(1)) if m else []
        if not nums or abs(float(nums[-1]) - t) > 1e-6:
            erros.append(f"{stem}: texto {nums[-1:] or '?'} x {t}")
    return erros


def carrega(ref):
    fam, nome = ref
    if fam == "rcfjssp":
        return parse(UP / f"{nome}.fjs"), True, CONFIG[("exp4", "all")]
    import instancias_calibracao as ic
    return ic.carrega(fam, nome)


def extrai(inst, s, st, en, rl, pr) -> List[dict]:
    return [{"op": k, "job": o.job, "index": o.index,
             "machine": next(m for m, _ in o.modes if s.Value(pr[(k, m)])),
             "tool": o.tool, "start": s.Value(st[k]), "end": s.Value(en[k]),
             "release": s.Value(rl[k])} for k, o in enumerate(inst.operations)]


def makespan(sch) -> int:
    return max(e["end"] for e in sch)


def subproblema(inst, mb, inc, livres, teto, tempo, fios, semente):
    from ortools.sat.python import cp_model
    import modelo_reservatorio as mr
    mdl, st, en, rl, pr = mr.build(inst, mb)
    por_maq: Dict[int, list] = {}
    for e in inc:
        k = e["op"]
        mdl.AddHint(st[k], e["start"]); mdl.AddHint(en[k], e["end"])
        mdl.AddHint(rl[k], e["release"])
        for m, _ in inst.operations[k].modes:
            mdl.AddHint(pr[(k, m)], int(m == e["machine"]))
        if k not in livres:
            for m, _ in inst.operations[k].modes:
                mdl.Add(pr[(k, m)] == int(m == e["machine"]))
            por_maq.setdefault(e["machine"], []).append(e)
    for lst in por_maq.values():
        lst.sort(key=lambda e: (e["start"], e["end"]))
        for a, b in zip(lst, lst[1:]):
            mdl.Add(st[b["op"]] >= en[a["op"]])
    mk = mdl.NewIntVar(0, teto, "mk")
    mdl.AddMaxEquality(mk, list(en.values()))
    mdl.Minimize(mk)
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = fios
    s.parameters.max_time_in_seconds = tempo
    s.parameters.random_seed = semente
    r = s.Solve(mdl)
    if r in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return s.StatusName(r), extrai(inst, s, st, en, rl, pr)
    return s.StatusName(r), None


def construcao(inst, mb, fios, limite, semente):
    from ortools.sat.python import cp_model
    import modelo_reservatorio as mr
    mdl, st, en, rl, pr = mr.build(inst, mb)
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = fios
    s.parameters.max_time_in_seconds = limite
    s.parameters.random_seed = semente
    s.parameters.stop_after_first_solution = True
    r = s.Solve(mdl)
    if r in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return extrai(inst, s, st, en, rl, pr)
    return None


def viz_ops(nome, inst, sch, rho, rng) -> set:
    n = len(sch)
    alvo = max(4, int(rho * n))
    mk = makespan(sch)
    if nome == "janela":
        L = max(1, int(mk * rho))
        a = rng.randint(0, max(0, mk - L))
        return {e["op"] for e in sch if e["end"] >= a and e["start"] <= a + L}
    if nome == "maquinas":
        ultimo = max(sch, key=lambda e: e["end"])["machine"]
        maqs = sorted({e["machine"] for e in sch})
        par = rng.choice([m for m in maqs if m != ultimo] or [ultimo])
        ops = [e["op"] for e in sch if e["machine"] in (ultimo, par)]
        rng.shuffle(ops)
        return set(ops[:alvo]) if len(ops) > alvo else set(ops)
    if nome == "material":
        recs = [u for u in inst.nonrenewable]
        jobs = set()
        rng.shuffle(recs)
        for u in recs:
            jobs |= {j for j in range(inst.jobs)
                     if u in inst.required[j] or u in inst.produced[j]}
            if sum(1 for e in sch if e["job"] in jobs) >= alvo:
                break
        return {e["op"] for e in sch if e["job"] in jobs}

    by_op = {e["op"]: e for e in sch}
    pred_job = {}
    for o_k, o in enumerate(inst.operations):
        for o2_k, o2 in enumerate(inst.operations):
            if o2.job == o.job and o2.index == o.index - 1:
                pred_job[o_k] = o2_k
    maq = {}
    for e in sch:
        maq.setdefault(e["machine"], []).append(e)
    pred_maq = {}
    for lst in maq.values():
        lst.sort(key=lambda e: e["start"])
        for a, b in zip(lst, lst[1:]):
            pred_maq[b["op"]] = a["op"]
    cad, fila = set(), [max(sch, key=lambda e: e["end"])["op"]]
    while fila and len(cad) < alvo:
        k = fila.pop()
        if k in cad:
            continue
        cad.add(k)
        s = by_op[k]["start"]
        for p in (pred_job.get(k), pred_maq.get(k)):
            if p is not None and by_op[p]["release"] >= s - 0:
                fila.append(p)
    if len(cad) < alvo:
        resto = sorted((e for e in sch if e["op"] not in cad),
                       key=lambda e: -e["end"])
        cad |= {e["op"] for e in resto[: alvo - len(cad)]}
    return cad


def caminhante(wid, ref, prazo, fios, semente, comp, trava, hist, prm):

    inst, mb, _spec = carrega(ref)
    rng = random.Random(semente * 1000 + wid)
    rho = prm["RHO0"]
    pesos = {v: 1.0 for v in prm["VIZ"]}
    with trava:
        inc = json.loads(comp["sch"])
    while time.time() < prazo - 0.5:
        with trava:
            if comp["mk"] < makespan(inc):
                inc = json.loads(comp["sch"])
        tot = sum(pesos.values())
        x, nome = rng.random() * tot, prm["VIZ"][-1]
        for v, w in pesos.items():
            x -= w
            if x <= 0:
                nome = v
                break
        livres = viz_ops(nome, inst, inc, rho, rng)
        tempo = min(prm["SUB_TIME"], prazo - time.time())
        if tempo < 0.5:
            break
        status, novo = subproblema(inst, mb, inc, livres, makespan(inc), tempo, fios,
                                   rng.randint(0, 10 ** 6))
        if novo is not None:
            mk_novo, mk_velho = makespan(novo), makespan(inc)
            ganho = mk_novo < mk_velho
            inc = novo
            pesos[nome] = max(prm["W_MIN"], pesos[nome] * prm["DECAY"] + (1.0 if ganho else 0.1))
            if ganho:
                with trava:
                    if mk_novo < comp["mk"]:
                        comp["mk"] = mk_novo
                        comp["sch"] = json.dumps(novo)
                        hist.append((round(time.time() - comp["t0"], 1), mk_novo, nome, wid))
            if status == "OPTIMAL" and not ganho:
                rho = min(prm["RHO_MAX"], rho * prm["RHO_STEP"])
        else:
            pesos[nome] = max(prm["W_MIN"], pesos[nome] * prm["DECAY"])
            rho = max(prm["RHO_MIN"], rho / prm["RHO_STEP"])


def executa(ref, semente, walkers, fios, orcamento, prm=None):
    import rcfjssp_audit as aud
    prm = dict(prm or P)
    inst, mb, spec = carrega(ref)
    t0 = time.time()
    prazo = t0 + orcamento
    inc = construcao(inst, mb, walkers * fios, orcamento * prm["CONSTR_FRAC"], semente)
    t_constr = round(time.time() - t0, 1)
    if inc is None:
        return {"makespan": None, "schedule": None, "t_construcao": t_constr}
    ctx = mp.get_context("spawn")
    with ctx.Manager() as man:
        comp = man.dict(mk=makespan(inc), sch=json.dumps(inc), t0=t0)
        hist = man.list([(t_constr, makespan(inc), "construcao", -1)])
        trava = man.Lock()
        procs = [ctx.Process(target=caminhante,
                             args=(w, ref, prazo, fios, semente, comp, trava, hist, prm))
                 for w in range(walkers)]
        for p in procs:
            p.start()
        for p in procs:
            p.join(max(0.1, prazo - time.time() + 15))
            if p.is_alive():
                p.terminate()
        sch = json.loads(comp["sch"])
        trajetoria = list(hist)
    mk = makespan(sch)
    prob = aud.check_schedule(inst, sch, spec, mk)
    return {"makespan": mk, "schedule": sch if not prob else None,
            "auditoria": prob or "ok", "t_construcao": t_constr,
            "wall_seconds": round(time.time() - t0, 1), "trajetoria": trajetoria,
            "parametros": {k: prm[k] for k in prm}}


def protocolo(walkers, fios, escala) -> dict:
    p = {"algoritmo": "cp-lns (X8)", "constantes": P, "walkers": walkers,
         "fios_por_walker": fios, "orcamento": "Tabela 10, ALNS-CP Time(s)",
         "escala_orcamento": escala,
         "sha_script": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16],
         "sha_modelo": hashlib.sha256((HERE / "modelo_reservatorio.py").read_bytes()).hexdigest()[:16],
         "sha_full": hashlib.sha256((ROOT / "rcfjssp_full.py").read_bytes()).hexdigest()[:16],
         "cpu": maquina.nome_cpu()}
    p["hash"] = hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest()[:16]
    return p


def relatorio(pasta: Path) -> None:
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in pasta.glob("lcbrtu_*.json")]
    if not rows:
        print(f"nada em {pasta}")
        return
    print(f"{'inst':>9s} {'n':>3s} {'melhor':>6s} {'mediana':>7s} {'ALNS':>5s} {'T(s)':>6s}  resultado")
    melhores, w = [], [0, 0, 0]
    for stem in STEMS:
        rs = [r["makespan"] for r in rows if r["instance"] == stem and r.get("makespan")]
        if not rs:
            continue
        b, alns = min(rs), TABLE10[stem][2]
        melhores.append(b)
        res = "melhor" if b < alns else "empate" if b == alns else "pior"
        w[["melhor", "empate", "pior"].index(res)] += 1
        print(f"{stem:>9s} {len(rs):3d} {b:6d} {statistics.median(rs):7.1f} {alns:5d} "
              f"{T_ALNS[stem]:6.0f}  {res}")
    if len(melhores) == 10:
        print(f"media melhor {statistics.mean(melhores):.1f} x ALNS-CP 329.0 | "
              f"{w[0]} melhores, {w[1]} empates, {w[2]} piores")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instancias", nargs="*", default=STEMS)
    ap.add_argument("--sementes", type=int, nargs="*", default=[1])
    ap.add_argument("--walkers", type=int, default=4)
    ap.add_argument("--fios", type=int, default=2, help="fios do CP-SAT por caminhante")
    ap.add_argument("--escala", type=float, default=1.0,
                    help="multiplica o orcamento (so para teste; o protocolo e 1.0)")
    ap.add_argument("--viz", nargs="*", default=list(P["VIZ"]),
                    help="vizinhancas usadas (ablacao X8b: --viz janela)")
    ap.add_argument("--calibracao", default=str(ROOT / "results" / "final" / "calibracao" / "escolha.json"),
                    help="parametros escolhidos pelo X9 (calibra_lns.py)")
    ap.add_argument("--sem-calibracao", action="store_true",
                    help="usa as constantes de desenho (so teste: o protocolo exige o X9)")
    ap.add_argument("--saida", default=str(OUT))
    ap.add_argument("--relatorio", action="store_true")
    ap.add_argument("--qualquer-maquina", action="store_true")
    a = ap.parse_args(argv)

    if a.relatorio:
        relatorio(Path(a.saida))
        return 0
    erros = confere_t10()
    if erros:
        print("Tempos da Tabela 10 nao conferem com o artigo:", erros)
        return 1
    maquina.exige_i7(a.qualquer_maquina)
    P["VIZ"] = tuple(a.viz)
    cal = Path(a.calibracao)
    if cal.exists():
        escolha = json.loads(cal.read_text(encoding="utf-8"))
        P.update(escolha["parametros"])
        P["CALIBRACAO"] = escolha.get("hash_campanha", "?")
        print(f"parametros calibrados (X9): {escolha['parametros']}", flush=True)
    elif not a.sem_calibracao:
        print(f"RECUSADO: falta {cal}. O protocolo do X8 exige a calibracao X9 "
              f"(mesmas 10 instancias de calibracao dos autores). Use --sem-calibracao so para teste.")
        return 2
    proto = protocolo(a.walkers, a.fios, a.escala)
    pasta = Path(a.saida)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "protocolo.manifest").write_text(json.dumps(proto, indent=1), encoding="utf-8")
    print(f"protocolo {proto['hash']} -> {pasta}", flush=True)
    for semente in a.sementes:
        for stem in a.instancias:
            alvo = pasta / f"{stem}_s{semente}.json"
            if alvo.exists():
                old = json.loads(alvo.read_text(encoding="utf-8"))
                if old.get("protocol_hash") == proto["hash"] and old.get("schedule"):
                    print(f"{stem} s{semente}: ja feito ({old['makespan']})", flush=True)
                    continue
            orc = T_ALNS[stem] * a.escala
            r = executa(("rcfjssp", stem), semente, a.walkers, a.fios, orc, P)
            r.update(instance=stem, experiment="exp4", config="all", seed=semente,
                     orcamento=orc, their_alns=TABLE10[stem][2], their_cp=TABLE10[stem][1],
                     their_lb=TABLE10[stem][0], protocol_hash=proto["hash"],
                     maquina=maquina.descreve(),
                     provenance={"python": platform.python_version()})
            tmp = alvo.with_suffix(".tmp")
            tmp.write_text(json.dumps(r, indent=1), encoding="utf-8")
            os.replace(tmp, alvo)
            print(f"{stem} s{semente}: UB {r['makespan']} (ALNS-CP {TABLE10[stem][2]}) "
                  f"constr {r['t_construcao']}s, {r.get('wall_seconds')}s, "
                  f"auditoria {r.get('auditoria')}", flush=True)
    relatorio(pasta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
