from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing as mp
import os
import platform
import random
import sys
import time
from pathlib import Path
from typing import Optional, Sequence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import maquina  # noqa: E402
import rcfjssp_lns as L  # noqa: E402
import rcfjssp_ptw as PT  # noqa: E402
from rcfjssp_reference import TABLE10  # noqa: E402

STEMS, T_ALNS = L.STEMS, L.T_ALNS

ARMS = {
    "U": "uniform kernel: every slot uses the slot-0 repair (hint, ceiling C_max, energy objective, 8 s); "
         "temperatures, Metropolis acceptance and exchanges unchanged",
    "F": "fixed ladder: the geometric ladder is never adapted",
    "C": "initialised energy cache: every replica's published energy starts at E(s*) instead of 0",
    "D": "instrumented PT-W: identical search, plus per-move timing, window size and exchange-cache records",
    "S": "sensitivity: PT-W with the constants given on the command line",
}


def subproblema_timed(*args, **kw):
    from ortools.sat.python import cp_model
    import modelo_reservatorio as mr
    inst, mb, inc, livres, teto, tempo, fios, semente, w_mk, pesos_job = args
    inverte = kw.get("inverte", ())
    sem_hint = kw.get("sem_hint", False)
    t0 = time.perf_counter()
    mdl, st, en, rl, pr = mr.build(inst, mb)
    por_maq = {}
    for e in inc:
        k = e["op"]
        if not (sem_hint and k in livres):
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
    for a_, b_, m_ in inverte:
        mdl.Add(pr[(a_, m_)] == 1); mdl.Add(pr[(b_, m_)] == 1)
        mdl.Add(st[a_] >= en[b_])
    mk = mdl.NewIntVar(0, teto, "mk")
    mdl.AddMaxEquality(mk, list(en.values()))
    if not pesos_job:
        mdl.Minimize(mk)
    else:
        obj = [w_mk * mk]
        cj = {}
        for k, o in enumerate(inst.operations):
            if o.job not in cj:
                cj[o.job] = mdl.NewIntVar(0, teto, f"C{o.job}")
            mdl.Add(cj[o.job] >= en[k])
        for j, v in cj.items():
            obj.append(pesos_job[j] * v)
        mdl.Minimize(sum(obj))
    t1 = time.perf_counter()
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = fios
    s.parameters.max_time_in_seconds = tempo
    s.parameters.random_seed = semente
    r = s.Solve(mdl)
    t2 = time.perf_counter()
    if r in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return s.StatusName(r), L.extrai(inst, s, st, en, rl, pr), t1 - t0, t2 - t1
    return s.StatusName(r), None, t1 - t0, t2 - t1


def replica_ctrl(rid, ref, prazo, fios, semente, comp, trava, slot, Ecur, Tl, tryc, accc,
                 tryT, accT, res, prm, braco, Eacc, pubv, accv):
    inst, mb, _ = L.carrega(ref)
    K = len(slot)
    rng = random.Random(semente * 1000 + rid)
    rho = prm["RHO0"]
    with trava:
        sch = json.loads(comp["sch"])
    E = PT.energia(sch, prm["ALPHA_E"])
    z = lambda: [0] * K
    st = dict(igual=z(), prop=z(), acc=z(), melhora=z(), pior_ac=z(), pior_rej=z(), semsol=z(),
              dE_pior=[0.0] * K, trips=0, trocas=0)
    diag = dict(t_build=0.0, t_solve=0.0, t_coord=0.0, movimentos=[], trocas=[])
    ult_ext = None
    nmov = 0
    ciclo = 0
    t_ini = time.time()
    while time.time() < prazo - 0.5:
        tc0 = time.perf_counter()
        with trava:
            s = slot[rid]
            T = Tl[s]
            Ecur[rid] = E
            if braco == "D":
                pubv[rid] += 1
            gm = comp["mk"]
            if s == 0 and gm < L.makespan(sch):
                sch = json.loads(comp["sch"])
                E = PT.energia(sch, prm["ALPHA_E"])
                Ecur[rid] = E
                if braco == "D":
                    Eacc[rid] = E
        diag["t_coord"] += time.perf_counter() - tc0
        if s in (0, K - 1) and K > 1:
            if ult_ext is not None and s != ult_ext:
                st["trips"] += 1
            ult_ext = s
        h = s / (K - 1) if K > 1 else 0.0
        hk = 0.0 if braco == "U" else h
        mk_atual = L.makespan(sch)
        delta, w_mk, pj, _ = PT.objetivo_replica(inst, hk, rng, prm)
        if mk_atual + delta > gm + prm["DERIVA"]:
            delta = max(0, gm + prm["DERIVA"] - mk_atual)
        sub = prm["SUB_TIME"] + (prm["SUB_HOT"] - prm["SUB_TIME"]) * hk
        tempo = min(sub, prazo - time.time())
        if tempo < 0.5:
            break
        livres = L.viz_ops("janela", inst, sch, rho, rng)
        inv = (PT.pares_inversao(sch, livres, max(1, round(hk * prm["FLIPS_MAX"])), rng)
               if hk > 0 and prm["FLIPS_MAX"] > 0 else ())
        status, novo, tb, ts = subproblema_timed(inst, mb, sch, livres, mk_atual + delta, tempo, fios,
                                                 rng.randint(0, 10 ** 6), w_mk, pj, inverte=inv,
                                                 sem_hint=(hk > 0 and prm["SEM_HINT"]))
        diag["t_build"] += tb
        diag["t_solve"] += ts
        nmov += 1
        aceito = False
        dE = None
        if novo is None:
            st["semsol"][s] += 1
            rho = max(prm["RHO_MIN"], rho / prm["RHO_STEP"])
        else:
            En = PT.energia(novo, prm["ALPHA_E"])
            dE = En - E
            mk_novo = L.makespan(novo)
            tc0 = time.perf_counter()
            with trava:
                T = Tl[slot[rid]]
                if mk_novo < comp["mk"]:
                    comp["mk"] = mk_novo
                    comp["sch"] = json.dumps(novo)
                    comp["hist"].append((round(time.time() - comp["t0"], 1), mk_novo,
                                         slot[rid], rid))
                    forca = True
                else:
                    forca = False
            diag["t_coord"] += time.perf_counter() - tc0
            st["prop"][s] += 1
            if all(x["start"] == y["start"] and x["machine"] == y["machine"]
                   for x, y in zip(sorted(sch, key=lambda e: e["op"]),
                                   sorted(novo, key=lambda e: e["op"]))):
                st["igual"][s] += 1
            if dE <= 0 or forca or (T > 0 and rng.random() < math.exp(-dE / T)):
                if dE < 0:
                    st["melhora"][s] += 1
                elif dE > 0:
                    st["pior_ac"][s] += 1
                    st["dE_pior"][s] += dE
                st["acc"][s] += 1
                sch, E = novo, En
                aceito = True
                if braco == "D":
                    with trava:
                        Eacc[rid] = E
                        accv[rid] += 1
            else:
                st["pior_rej"][s] += 1
            if status == "OPTIMAL" and dE >= 0:
                rho = min(prm["RHO_MAX"], rho * prm["RHO_STEP"])
        if braco == "D":
            diag["movimentos"].append([round(time.time() - t_ini, 1), s, round(rho, 3), len(livres),
                                       round(tb, 3), round(ts, 3), status,
                                       None if dE is None else round(dE, 3), int(aceito)])
        if prm["TROCA"] and K > 1 and nmov % prm["EX_EVERY"] == 0:
            ciclo += 1
            tc0 = time.perf_counter()
            with trava:
                Ecur[rid] = E
                if braco == "D":
                    pubv[rid] += 1
                s = slot[rid]
                s2 = s + 1 if (s + ciclo) % 2 == 0 else s - 1
                if 0 <= s2 < K:
                    r2 = next(r for r in range(K) if slot[r] == s2)
                    lo, hi = min(s, s2), max(s, s2)
                    r_lo, r_hi = (rid, r2) if s < s2 else (r2, rid)
                    ex = (1.0 / Tl[lo] - 1.0 / Tl[hi]) * (Ecur[r_lo] - Ecur[r_hi])
                    tryc[lo] += 1; tryT[lo] += 1
                    ok = ex >= 0 or rng.random() < math.exp(ex)
                    if ok:
                        slot[rid], slot[r2] = s2, s
                        accc[lo] += 1; accT[lo] += 1
                        st["trocas"] += 1
                    if braco == "D":
                        diag["trocas"].append([round(time.time() - t_ini, 1), s, s2, int(ok),
                                               int(pubv[r2] == 0), int(Ecur[r2] != Eacc[r2]),
                                               round(Ecur[r2] - Eacc[r2], 3)])
            diag["t_coord"] += time.perf_counter() - tc0
    diag["t_total"] = round(time.time() - t_ini, 1)
    st["ctrl"] = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in diag.items()}
    res[rid] = st


def executa_ctrl(ref, semente, K, fios, orcamento, prm, braco):
    import rcfjssp_audit as aud
    inst, mb, spec = L.carrega(ref)
    t0 = time.time()
    prazo = t0 + orcamento
    inc = L.construcao(inst, mb, K * fios, orcamento * prm["CONSTR_FRAC"], semente)
    t_constr = round(time.time() - t0, 1)
    if inc is None:
        return {"makespan": None, "schedule": None, "t_construcao": t_constr}
    ctx = mp.get_context("spawn")
    ln = math.log(prm["T_MAX"] / prm["T_MIN"]) / max(1, K - 1)
    gaps = [ln] * (K - 1)
    E0 = PT.energia(inc, prm["ALPHA_E"])
    with ctx.Manager() as man:
        comp = man.dict(mk=L.makespan(inc), sch=json.dumps(inc), t0=t0,
                        hist=man.list([(t_constr, L.makespan(inc), -1, -1)]))
        trava = man.Lock()
        slot = man.list(range(K))
        Ecur = man.list([E0 if braco == "C" else 0.0] * K)
        Eacc = man.list([E0] * K)
        pubv = man.list([0] * K)
        accv = man.list([0] * K)
        Tl = man.list(PT.escada(gaps, prm["T_MIN"]) if K > 1 else [prm["T_MIN"]])
        npar = max(1, K - 1)
        tryc, accc = man.list([0] * npar), man.list([0] * npar)
        tryT, accT = man.list([0] * npar), man.list([0] * npar)
        res = man.dict()
        procs = [ctx.Process(target=replica_ctrl,
                             args=(r, ref, prazo, fios, semente, comp, trava, slot, Ecur,
                                   Tl, tryc, accc, tryT, accT, res, prm, braco, Eacc, pubv, accv))
                 for r in range(K)]
        for p in procs:
            p.start()
        prox = time.time() + prm["ADAPTA_CADA"]
        ajustes = []
        while time.time() < prazo + 5 and any(p.is_alive() for p in procs):
            time.sleep(1.0)
            if K > 2 and braco != "F" and time.time() >= prox:
                prox += prm["ADAPTA_CADA"]
                with trava:
                    taxas = [(accc[i] / tryc[i]) if tryc[i] >= 5 else None
                             for i in range(K - 1)]
                    if all(t is not None for t in taxas):
                        for i, t in enumerate(taxas):
                            gaps[i] *= math.exp(0.5 * (t - prm["ALVO_TROCA"]) / prm["ALVO_TROCA"]
                                                if t > 0 else -0.5)
                            gaps[i] = min(max(gaps[i], 0.02), 3.0)
                        tot = sum(gaps)
                        gaps[:] = [g * math.log(prm["T_MAX"] / prm["T_MIN"]) / tot for g in gaps]
                        nova = PT.escada(gaps, prm["T_MIN"])
                        for i, v in enumerate(nova):
                            Tl[i] = v
                        ajustes.append([round(time.time() - t0, 1),
                                        [round(t, 3) for t in taxas]])
                    for i in range(K - 1):
                        tryc[i] = 0; accc[i] = 0
        for p in procs:
            p.join(max(0.1, prazo - time.time() + 15))
            if p.is_alive():
                p.terminate()
        sch = json.loads(comp["sch"])
        hist = list(comp["hist"])
        resp = dict(res)
        diag = dict(taxa_troca=[round(accT[i] / tryT[i], 3) if tryT[i] else None
                                for i in range(K - 1)],
                    tentativas_troca=list(tryT), escada_final=[round(t, 3) for t in Tl],
                    ajustes=ajustes, replicas=resp)
    mk = L.makespan(sch)
    prob = aud.check_schedule(inst, sch, spec, mk)
    return {"makespan": mk, "schedule": sch if not prob else None,
            "auditoria": prob or "ok", "t_construcao": t_constr,
            "wall_seconds": round(time.time() - t0, 1), "trajetoria": hist,
            "diagnostico_pt": diag, "parametros": {k: prm[k] for k in prm}}


def protocolo(K, fios, escala, prm, braco) -> dict:
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]
    p = {"algoritmo": f"ptw-controls {braco}", "braco": braco, "descricao": ARMS[braco],
         "ptw": {k: prm[k] for k in PT.PTW}, "replicas": K, "fios_por_replica": fios,
         "orcamento": "Tabela 10, ALNS-CP Time(s)", "escala_orcamento": escala,
         "calibrados_X9": {k: prm[k] for k in ("SUB_TIME", "RHO0")},
         "sha_script": sha(__file__), "sha_ptw": sha(HERE / "rcfjssp_ptw.py"),
         "sha_lns": sha(HERE / "rcfjssp_lns.py"), "sha_modelo": sha(HERE / "modelo_reservatorio.py"),
         "cpu": maquina.nome_cpu()}
    p["hash"] = hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest()[:16]
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="PT-W controls and diagnostics (derived from the frozen rcfjssp_ptw.py)")
    ap.add_argument("--braco", choices=sorted(ARMS), required=True)
    ap.add_argument("--instancias", nargs="*", default=STEMS)
    ap.add_argument("--sementes", type=int, nargs="*", default=[1])
    ap.add_argument("--replicas", type=int, default=8)
    ap.add_argument("--fios", type=int, default=1)
    ap.add_argument("--escala", type=float, default=1.0)
    ap.add_argument("--calibracao", default=str(ROOT / "results" / "final" / "calibracao" / "escolha.json"))
    ap.add_argument("--saida", required=True)
    ap.add_argument("--comparar", default=None)
    ap.add_argument("--qualquer-maquina", action="store_true")
    ap.add_argument("--tmin", type=float, default=None)
    ap.add_argument("--tmax", type=float, default=None)
    ap.add_argument("--delta-max", type=int, default=None)
    ap.add_argument("--deriva", type=int, default=None)
    ap.add_argument("--sub-hot", type=float, default=None)
    ap.add_argument("--alpha-e", type=float, default=None)
    ap.add_argument("--sem-troca", action="store_true")
    a = ap.parse_args(argv)
    erros = L.confere_t10()
    if erros:
        print("Tempos da Tabela 10 nao conferem:", erros)
        return 1
    maquina.exige_i7(a.qualquer_maquina)
    ptw = dict(PT.PTW)
    if a.tmin: ptw["T_MIN"] = a.tmin
    if a.tmax: ptw["T_MAX"] = a.tmax
    if a.delta_max is not None: ptw["DELTA_MAX"] = a.delta_max
    if a.deriva is not None: ptw["DERIVA"] = a.deriva
    if a.sub_hot is not None: ptw["SUB_HOT"] = a.sub_hot
    if a.alpha_e is not None: ptw["ALPHA_E"] = a.alpha_e
    if a.sem_troca: ptw["TROCA"] = False
    prm = dict(L.P)
    cal = Path(a.calibracao)
    if not cal.exists():
        print(f"RECUSADO: falta {cal} (calibration choice file).")
        return 2
    prm.update(json.loads(cal.read_text(encoding="utf-8"))["parametros"])
    prm.update(ptw)
    proto = protocolo(a.replicas, a.fios, a.escala, prm, a.braco)
    pasta = Path(a.saida)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "protocolo.manifest").write_text(json.dumps(proto, indent=1), encoding="utf-8")
    print(f"protocolo {proto['hash']} ({a.braco}: {ARMS[a.braco]}) -> {pasta}", flush=True)
    for semente in a.sementes:
        for stem in a.instancias:
            alvo = pasta / f"{stem}_s{semente}.json"
            if alvo.exists():
                old = json.loads(alvo.read_text(encoding="utf-8"))
                if old.get("protocol_hash") == proto["hash"] and old.get("schedule"):
                    print(f"{stem} s{semente}: ja feito ({old['makespan']})", flush=True)
                    continue
            orc = T_ALNS[stem] * a.escala
            r = executa_ctrl(("rcfjssp", stem), semente, a.replicas, a.fios, orc, prm, a.braco)
            r.update(instance=stem, experiment="exp4", config="all", seed=semente, braco=a.braco,
                     orcamento=orc, their_alns=TABLE10[stem][2], protocol_hash=proto["hash"],
                     maquina=maquina.descreve(), provenance={"python": platform.python_version()})
            tmp = alvo.with_suffix(".tmp")
            tmp.write_text(json.dumps(r, indent=1), encoding="utf-8")
            os.replace(tmp, alvo)
            d = r.get("diagnostico_pt", {})
            print(f"{stem} s{semente}: UB {r['makespan']} (ALNS-CP {TABLE10[stem][2]}) "
                  f"constr {r['t_construcao']}s, {r.get('wall_seconds')}s, auditoria "
                  f"{r.get('auditoria')}, troca {d.get('taxa_troca')}", flush=True)
    if a.comparar:
        PT.relatorio(pasta, Path(a.comparar))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
