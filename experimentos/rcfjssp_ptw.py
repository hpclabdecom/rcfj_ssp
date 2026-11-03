from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing as mp
import os
import platform
import random
import statistics
import sys
import time
from pathlib import Path
from typing import List, Optional, Sequence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import maquina
import rcfjssp_lns as L
from rcfjssp_reference import TABLE10

OUT = ROOT / "results" / "final" / "ptw"
STEMS, T_ALNS = L.STEMS, L.T_ALNS


PTW = dict(
    ALPHA_E=0.05,
    ALPHA_P=0.05,
    T_MIN=0.15, T_MAX=1.5,
    DELTA_MAX=3,
    SIGMA=1.0,
    SUB_HOT=4.0,
    SEM_HINT=True,
    FLIPS_MAX=0,
    DERIVA=5,
    EX_EVERY=2,
    ALVO_TROCA=0.23,
    ADAPTA_CADA=60.0,
    TROCA=True,
)


def termos(sch) -> dict:
    c = {}
    for e in sch:
        c[e["job"]] = max(c.get(e["job"], 0), e["end"])
    return c


def energia(sch, alpha) -> float:
    mk = L.makespan(sch)
    if alpha == 0:
        return float(mk)
    c = termos(sch)
    return mk + alpha * sum(c.values()) / len(c)


def subproblema_pt(inst, mb, inc, livres, teto, tempo, fios, semente, w_mk, pesos_job,
                   inverte=(), sem_hint=False):
    from ortools.sat.python import cp_model
    import modelo_reservatorio as mr
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
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = fios
    s.parameters.max_time_in_seconds = tempo
    s.parameters.random_seed = semente
    r = s.Solve(mdl)
    if r in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return s.StatusName(r), L.extrai(inst, s, st, en, rl, pr)
    return s.StatusName(r), None


def objetivo_replica(inst, h, rng, prm):
    nj = inst.jobs
    esc = 1000
    if h <= 0:
        a = prm["ALPHA_E"]
        if a == 0:
            return 0, esc, {}, 1.0
        return 0, esc * nj, {j: int(round(esc * a)) for j in range(nj)}, 1.0
    delta = int(round(h * prm["DELTA_MAX"]))
    w_mk = max(1, int(round(esc * nj * (1.0 - 0.8 * h))))
    a = prm["ALPHA_P"]
    pj = {j: max(1, int(round(esc * a * math.exp(prm["SIGMA"] * h * rng.gauss(0, 1)))))
          for j in range(nj)}
    return delta, w_mk, pj, 1.0


def pares_inversao(sch, livres, n, rng):
    por_maq = {}
    for e in sorted(sch, key=lambda e: (e["start"], e["end"])):
        por_maq.setdefault(e["machine"], []).append(e)
    cand = [(x["op"], y["op"], m) for m, lst in por_maq.items()
            for x, y in zip(lst, lst[1:]) if x["op"] in livres and y["op"] in livres]
    rng.shuffle(cand)
    usados, out = set(), []
    for a, b, m in cand:
        if a in usados or b in usados:
            continue
        usados |= {a, b}
        out.append((a, b, m))
        if len(out) == n:
            break
    return out


def replica(rid, ref, prazo, fios, semente, comp, trava, slot, Ecur, Tl, tryc, accc,
            tryT, accT, res, prm):
    inst, mb, _ = L.carrega(ref)
    K = len(slot)
    rng = random.Random(semente * 1000 + rid)
    rho = prm["RHO0"]
    with trava:
        sch = json.loads(comp["sch"])
    E = energia(sch, prm["ALPHA_E"])
    z = lambda: [0] * K
    st = dict(igual=z(), prop=z(), acc=z(), melhora=z(), pior_ac=z(), pior_rej=z(), semsol=z(),
              dE_pior=[0.0] * K, trips=0, trocas=0)
    ult_ext = None
    nmov = 0
    ciclo = 0
    while time.time() < prazo - 0.5:
        with trava:
            s = slot[rid]
            T = Tl[s]
            Ecur[rid] = E
            gm = comp["mk"]
            if s == 0 and gm < L.makespan(sch):
                sch = json.loads(comp["sch"])
                E = energia(sch, prm["ALPHA_E"])
                Ecur[rid] = E
        if s in (0, K - 1) and K > 1:
            if ult_ext is not None and s != ult_ext:
                st["trips"] += 1
            ult_ext = s
        h = s / (K - 1) if K > 1 else 0.0
        mk_atual = L.makespan(sch)
        delta, w_mk, pj, _ = objetivo_replica(inst, h, rng, prm)
        if mk_atual + delta > gm + prm["DERIVA"]:
            delta = max(0, gm + prm["DERIVA"] - mk_atual)
        sub = prm["SUB_TIME"] + (prm["SUB_HOT"] - prm["SUB_TIME"]) * h
        tempo = min(sub, prazo - time.time())
        if tempo < 0.5:
            break
        livres = L.viz_ops("janela", inst, sch, rho, rng)
        inv = (pares_inversao(sch, livres, max(1, round(h * prm["FLIPS_MAX"])), rng)
               if h > 0 and prm["FLIPS_MAX"] > 0 else ())
        status, novo = subproblema_pt(inst, mb, sch, livres, mk_atual + delta, tempo, fios,
                                      rng.randint(0, 10 ** 6), w_mk, pj, inv,
                                      sem_hint=(h > 0 and prm["SEM_HINT"]))
        nmov += 1
        if novo is None:
            st["semsol"][s] += 1
            rho = max(prm["RHO_MIN"], rho / prm["RHO_STEP"])
        else:
            En = energia(novo, prm["ALPHA_E"])
            dE = En - E
            mk_novo = L.makespan(novo)
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
            else:
                st["pior_rej"][s] += 1
            if status == "OPTIMAL" and dE >= 0:
                rho = min(prm["RHO_MAX"], rho * prm["RHO_STEP"])

        if prm["TROCA"] and K > 1 and nmov % prm["EX_EVERY"] == 0:
            ciclo += 1
            with trava:
                Ecur[rid] = E
                s = slot[rid]
                s2 = s + 1 if (s + ciclo) % 2 == 0 else s - 1
                if 0 <= s2 < K:
                    r2 = next(r for r in range(K) if slot[r] == s2)
                    lo, hi = min(s, s2), max(s, s2)
                    r_lo, r_hi = (rid, r2) if s < s2 else (r2, rid)
                    ex = (1.0 / Tl[lo] - 1.0 / Tl[hi]) * (Ecur[r_lo] - Ecur[r_hi])
                    tryc[lo] += 1; tryT[lo] += 1
                    if ex >= 0 or rng.random() < math.exp(ex):
                        slot[rid], slot[r2] = s2, s
                        accc[lo] += 1; accT[lo] += 1
                        st["trocas"] += 1
    res[rid] = st


def escada(gaps, tmin):
    T = [tmin]
    for g in gaps:
        T.append(T[-1] * math.exp(g))
    return T


def executa(ref, semente, K, fios, orcamento, prm, inicial=None):
    import rcfjssp_audit as aud
    inst, mb, spec = L.carrega(ref)
    t0 = time.time()
    prazo = t0 + orcamento
    if inicial is not None:
        inc = inicial
    else:
        inc = L.construcao(inst, mb, K * fios, orcamento * prm["CONSTR_FRAC"], semente)
    t_constr = round(time.time() - t0, 1)
    if inc is None:
        return {"makespan": None, "schedule": None, "t_construcao": t_constr}
    ctx = mp.get_context("spawn")
    ln = math.log(prm["T_MAX"] / prm["T_MIN"]) / max(1, K - 1)
    gaps = [ln] * (K - 1)
    with ctx.Manager() as man:
        comp = man.dict(mk=L.makespan(inc), sch=json.dumps(inc), t0=t0,
                        hist=man.list([(t_constr, L.makespan(inc), -1, -1)]))
        trava = man.Lock()
        slot = man.list(range(K))
        Ecur = man.list([0.0] * K)
        Tl = man.list(escada(gaps, prm["T_MIN"]) if K > 1 else [prm["T_MIN"]])
        npar = max(1, K - 1)
        tryc, accc = man.list([0] * npar), man.list([0] * npar)
        tryT, accT = man.list([0] * npar), man.list([0] * npar)
        res = man.dict()
        procs = [ctx.Process(target=replica,
                             args=(r, ref, prazo, fios, semente, comp, trava, slot, Ecur,
                                   Tl, tryc, accc, tryT, accT, res, prm)) for r in range(K)]
        for p in procs:
            p.start()
        prox = time.time() + prm["ADAPTA_CADA"]
        ajustes = []
        while time.time() < prazo + 5 and any(p.is_alive() for p in procs):
            time.sleep(1.0)
            if K > 2 and time.time() >= prox:
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
                        nova = escada(gaps, prm["T_MIN"])
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


def protocolo(K, fios, escala, prm) -> dict:
    p = {"algoritmo": "ptw (X12)", "ptw": {k: PTW[k] for k in PTW}, "replicas": K,
         "fios_por_replica": fios, "orcamento": "Tabela 10, ALNS-CP Time(s)",
         "escala_orcamento": escala,
         "calibrados_X9": {k: prm[k] for k in ("SUB_TIME", "RHO0")},
         "sha_script": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16],
         "sha_lns": hashlib.sha256((HERE / "rcfjssp_lns.py").read_bytes()).hexdigest()[:16],
         "sha_modelo": hashlib.sha256((HERE / "modelo_reservatorio.py").read_bytes()).hexdigest()[:16],
         "cpu": maquina.nome_cpu()}
    p["hash"] = hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest()[:16]
    return p


def le(pasta: Path, stem):
    return sorted(json.loads(p.read_text(encoding="utf-8"))["makespan"]
                  for p in pasta.glob(f"{stem}_s*.json")
                  if json.loads(p.read_text(encoding="utf-8")).get("makespan"))


def relatorio(pasta: Path, comparar: Optional[Path]) -> None:
    print(f"{'inst':>9s} {'n':>3s} {'melhor':>6s} {'mediana':>7s} | "
          f"{'X8b n':>5s} {'melhor':>6s} {'mediana':>7s} | dif.mediana  veredito")
    vitorias, derrotas, pior = 0, 0, 0
    for stem in STEMS:
        a = le(pasta, stem)
        if not a:
            continue
        b = le(comparar, stem) if comparar and comparar.exists() else []
        ma = statistics.median(a)
        if b:
            mb_ = statistics.median(b)
            d = ma - mb_
            v = "PTW melhor" if d < 0 else "empate" if d == 0 else "PTW pior"
            vitorias += d < 0; derrotas += d > 0; pior = max(pior, d)
            print(f"{stem:>9s} {len(a):3d} {min(a):6d} {ma:7.1f} | {len(b):5d} {min(b):6d} "
                  f"{mb_:7.1f} | {d:+8.1f}    {v}")
        else:
            print(f"{stem:>9s} {len(a):3d} {min(a):6d} {ma:7.1f} |  (sem comparacao)")
    if comparar:
        print(f"\nRegra do smoke (fixada antes de rodar): PROMISSOR se PTW vence em mediana em "
              f">=2 instancias e nenhuma perde por mais de 3. Aqui: {vitorias} vitorias, "
              f"{derrotas} derrotas, pior diferenca {pior:+.1f}.")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instancias", nargs="*", default=STEMS)
    ap.add_argument("--sementes", type=int, nargs="*", default=[1])
    ap.add_argument("--replicas", type=int, default=8, help="K; K*fios = fios da maquina")
    ap.add_argument("--fios", type=int, default=1, help="fios do CP-SAT por replica")
    ap.add_argument("--escala", type=float, default=1.0)
    ap.add_argument("--calibracao", default=str(ROOT / "results" / "final" / "calibracao" / "escolha.json"))
    ap.add_argument("--sem-calibracao", action="store_true")
    ap.add_argument("--saida", default=str(OUT))
    ap.add_argument("--comparar", default=str(ROOT / "results" / "final" / "heur_lns_janela"))
    ap.add_argument("--relatorio", action="store_true")
    ap.add_argument("--qualquer-maquina", action="store_true")
    ap.add_argument("--alpha-e", type=float, default=None, help="ablacao: 0 => E = makespan")
    ap.add_argument("--sem-troca", action="store_true", help="ablacao: replicas independentes")
    ap.add_argument("--tmin", type=float, default=None)
    ap.add_argument("--tmax", type=float, default=None)
    ap.add_argument("--delta-max", type=int, default=None)
    ap.add_argument("--inicial", default=None,
                    help="pasta com <inst>_s<semente>.json: parte do escalonamento ali (sem construcao)")
    a = ap.parse_args(argv)
    if a.relatorio:
        relatorio(Path(a.saida), Path(a.comparar))
        return 0
    erros = L.confere_t10()
    if erros:
        print("Tempos da Tabela 10 nao conferem:", erros)
        return 1
    maquina.exige_i7(a.qualquer_maquina)
    if a.alpha_e is not None:
        PTW["ALPHA_E"] = a.alpha_e
    if a.sem_troca:
        PTW["TROCA"] = False
    if a.tmin: PTW["T_MIN"] = a.tmin
    if a.tmax: PTW["T_MAX"] = a.tmax
    if a.delta_max is not None: PTW["DELTA_MAX"] = a.delta_max
    prm = dict(L.P)
    cal = Path(a.calibracao)
    if cal.exists():
        prm.update(json.loads(cal.read_text(encoding="utf-8"))["parametros"])
    elif not a.sem_calibracao:
        print(f"RECUSADO: falta {cal} (X9). --sem-calibracao so para teste.")
        return 2
    prm.update(PTW)
    proto = protocolo(a.replicas, a.fios, a.escala, prm)
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
            ini = None
            if a.inicial:
                f = Path(a.inicial) / f"{stem}_s{semente}.json"
                ini = json.loads(f.read_text(encoding="utf-8"))["schedule"]
            r = executa(("rcfjssp", stem), semente, a.replicas, a.fios, orc, prm, ini)
            r.update(instance=stem, experiment="exp4", config="all", seed=semente,
                     orcamento=orc, their_alns=TABLE10[stem][2], protocol_hash=proto["hash"],
                     maquina=maquina.descreve(), provenance={"python": platform.python_version()})
            tmp = alvo.with_suffix(".tmp")
            tmp.write_text(json.dumps(r, indent=1), encoding="utf-8")
            os.replace(tmp, alvo)
            d = r.get("diagnostico_pt", {})
            print(f"{stem} s{semente}: UB {r['makespan']} (ALNS-CP {TABLE10[stem][2]}) "
                  f"constr {r['t_construcao']}s, {r.get('wall_seconds')}s, auditoria "
                  f"{r.get('auditoria')}, troca {d.get('taxa_troca')}", flush=True)
    relatorio(pasta, Path(a.comparar))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
