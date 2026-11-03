from __future__ import annotations
import collections, glob, itertools, json, random, statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "results"
INST = [f"lcbrtu_{i}" for i in range(10)]
SCREEN = ["lcbrtu_3", "lcbrtu_5", "lcbrtu_8"]
HELD = [f"rcfj_h_{i}" for i in range(10)] + [f"rcfj_hl_{i}" for i in range(5)]
SCALED = ["lcbrtu_3_x10", "lcbrtu_5_x10", "lcbrtu_8_x10"]
PLAT = {"i7": "Intel Core i7-2600 (4 cores / 8 threads)", "ryzen": "AMD Ryzen 7 5700U (8 cores / 16 threads)",
        "xeon": "Intel Xeon E5-2696 v4 (22 cores / 44 threads)"}
N_PERM, N_BOOT, SEED = 20000, 10000, 11


def load(d, field="makespan"):
    out = {}
    for f in glob.glob(str(R / d / "*.json")):
        j = json.load(open(f, encoding="utf-8"))
        if not isinstance(j, dict) or j.get(field) is None:
            continue
        out.setdefault(j["instance"], {})[j.get("seed", 1)] = j[field]
    return out


def exists(d):
    return bool(glob.glob(str(R / d / "*.json")))


def alns_cp():
    r = {}
    for f in glob.glob(str(R / "final" / "heur_lns_janela" / "*.json")):
        j = json.load(open(f, encoding="utf-8"))
        r[j["instance"]] = j["their_alns"]
    return r


def ranks(vals):
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    rk = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        for k in range(i, j + 1):
            rk[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return rk


def mw_exact(a, b):
    pool = a + b
    if len(set(pool)) == 1:
        return None
    rk = ranks(pool)
    n, N = len(a), len(pool)
    mu = n * sum(rk) / N
    obs = abs(sum(rk[:n]) - mu)
    c = t = 0
    for comb in itertools.combinations(range(N), n):
        t += 1
        if abs(sum(rk[i] for i in comb) - mu) >= obs - 1e-9:
            c += 1
    return c / t


def holm(ps):
    idx = [i for i, p in enumerate(ps) if p is not None]
    m = len(idx)
    out = [None] * len(ps)
    run = 0.0
    for k, i in enumerate(sorted(idx, key=lambda i: ps[i])):
        run = max(run, min(1.0, (m - k) * ps[i]))
        out[i] = run
    return out


def strat_perm(pairs, onesided=True):
    rnd = random.Random(SEED)
    obs = sum(st.mean(c) - st.mean(a) for a, c in pairs) / len(pairs)
    cnt = 0
    for _ in range(N_PERM):
        t = 0.0
        for a, c in pairs:
            p = a + c
            rnd.shuffle(p)
            t += st.mean(p[len(a):]) - st.mean(p[:len(a)])
        t /= len(pairs)
        if (t >= obs - 1e-9) if onesided else (abs(t) >= abs(obs) - 1e-9):
            cnt += 1
    return obs, (cnt + 1) / (N_PERM + 1)


def boot_ci(pairs):
    rnd = random.Random(SEED)
    dm, dmean = [], []
    for _ in range(N_BOOT):
        sm = smean = 0.0
        for a, c in pairs:
            a2 = [rnd.choice(a) for _ in a]
            c2 = [rnd.choice(c) for _ in c]
            sm += st.median(c2) - st.median(a2)
            smean += st.mean(c2) - st.mean(a2)
        dm.append(sm / len(pairs))
        dmean.append(smean / len(pairs))
    dm.sort(); dmean.sort()
    lo, hi = int(0.025 * N_BOOT), int(0.975 * N_BOOT) - 1
    return (dm[lo], dm[hi]), (dmean[lo], dmean[hi])


def fmt_p(p):
    if p is None:
        return "–"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def compare(title, control, arm, insts=INST, seeds=None, onesided=True):
    if not (exists(arm) and exists(control)):
        return None
    A, C = load(arm), load(control)
    side = "one-sided, direction: arm better" if onesided else "two-sided"
    print(f"\n#### {title}\n")
    print(f"Arm `{arm}` against control `{control}`. Effect = median(control) − median(arm); positive = the arm is "
          f"better. Exact Mann–Whitney per instance, Holm over the non-degenerate instances; stratified permutation "
          f"test ({side}); paired bootstrap 95 % CIs.\n")
    print("| instance | arm best / median / mean | control best / median / mean | effect (median) | exact p | Holm p |")
    print("|---|---|---|---:|---:|---:|")
    rows, ps = [], []
    for i in insts:
        ks = sorted(set(A.get(i, {})) & set(C.get(i, {})))
        if seeds:
            ks = [k for k in ks if k in seeds]
        if not ks:
            continue
        a = [A[i][k] for k in ks]
        c = [C[i][k] for k in ks]
        rows.append((i, a, c))
        ps.append(mw_exact(a, c))
    if not rows:
        print("(no common runs)")
        return None
    hs = holm(ps)
    w = l = t = 0
    for (i, a, c), p, h in zip(rows, ps, hs):
        d = st.median(c) - st.median(a)
        w += d > 0; l += d < 0; t += d == 0
        print(f"| {i} | {min(a)} / {st.median(a):g} / {st.mean(a):.1f} (n={len(a)}) | "
              f"{min(c)} / {st.median(c):g} / {st.mean(c):.1f} (n={len(c)}) | {d:+g} | {fmt_p(p)} | {fmt_p(h)} |")
    pairs = [(a, c) for _, a, c in rows]
    obs, p = strat_perm(pairs, onesided)
    (lo, hi), (lo2, hi2) = boot_ci(pairs)
    mm = sum(st.median(c) - st.median(a) for a, c in pairs) / len(pairs)
    print(f"\nInstances with a better / equal / worse median in the arm: **{w} / {t} / {l}**. "
          f"Mean difference of medians **{mm:+.2f}** (95 % CI [{lo:+.2f}, {hi:+.2f}]); mean difference of means "
          f"**{obs:+.2f}** (95 % CI [{lo2:+.2f}, {hi2:+.2f}]); stratified permutation p = {fmt_p(p)} "
          f"(p = (c + 1)/(N + 1), N = {N_PERM}).")
    print(f"Mean of medians: arm {sum(st.median(a) for a, _ in pairs)/len(pairs):.2f} vs control "
          f"{sum(st.median(c) for _, c in pairs)/len(pairs):.2f}. Sum of the best values: arm "
          f"{sum(min(a) for a, _ in pairs)} vs control {sum(min(c) for _, c in pairs)}.")
    return mm, (lo, hi), obs, p


def platform_table(plat, cfg, insts=INST):
    cs = [(n, d) for n, d in cfg if exists(d)]
    if not cs:
        return
    D = {n: load(d) for n, d in cs}
    print(f"\n#### {PLAT[plat]} — best / median / mean over the seeds\n")
    print("| instance | " + " | ".join(n for n, _ in cs) + " |")
    print("|---|" + "---:|" * len(cs))
    for i in insts:
        print(f"| {i} | " + " | ".join(
            f"{min(D[n][i].values())} / {st.median(D[n][i].values()):g} / {st.mean(D[n][i].values()):.1f}"
            if i in D[n] else "–" for n, _ in cs) + " |")
    print("| **mean of medians** | " + " | ".join(
        f"{sum(st.median(D[n][i].values()) for i in insts if i in D[n]) / len(insts):.2f}" for n, _ in cs) + " |")
    print("| **sum of the best values** | " + " | ".join(
        f"{sum(min(D[n][i].values()) for i in insts if i in D[n])}" for n, _ in cs) + " |")


def main_tables(b):
    print("\n## 1. Benchmark instances, main configurations (ten seeds)\n")
    print("| instance | published ALNS-CP (best of 10) | published LB | published CP (1800 s) |")
    print("|---|---:|---:|---:|")
    their = {}
    for f in glob.glob(str(R / "final" / "heur_lns_janela" / "*.json")):
        j = json.load(open(f, encoding="utf-8"))
        their[j["instance"]] = (j["their_lb"], j["their_cp"], j["their_alns"])
    for i in INST:
        print(f"| {i} | {their[i][2]} | {their[i][0]} | {their[i][1]} |")
    platform_table("i7", [("TW-LNS 4×2", "final/heur_lns_janela"), ("TW-LNS 8×1", "i7/lns_8x1"),
                          ("PT-W 8×1", "i7/ptw_8x1"), ("PT-W 4×2", "i7/ptw_4x2")])
    platform_table("ryzen", [("TW-LNS 4×2", "ryzen/heur_lns_janela_4x2"), ("TW-LNS 8×1", "ryzen/lns_8x1"),
                             ("PT-W 8×1", "ryzen/ptw_8x1"), ("TW-LNS 8×2", "ryzen/heur_lns_janela_8x2"),
                             ("PT-W 16×1", "ryzen/ptw_16x1")])
    platform_table("xeon", [("TW-LNS 4×2", "xeon/heur_lns_janela_4x2"), ("TW-LNS 8×1", "xeon/lns_8x1"),
                            ("PT-W 8×1", "xeon/ptw_8x1"), ("TW-LNS 8×2", "xeon/heur_lns_janela_8x2"),
                            ("PT-W 16×1", "xeon/ptw_16x1"), ("TW-LNS 16×2", "xeon/heur_lns_janela_16x2"),
                            ("PT-W 16×2", "xeon/ptw_16x2")])
    print("\nOn the Xeon the 8-thread configurations ran two at a time on disjoint sets of eight physical cores "
          "(affinity masks 0xFFFF and 0xFFFF0000); the 16- and 32-thread configurations ran alone.")


def matched(b):
    print("\n## 2. PT-W against TW-LNS, same platform and same number of threads\n")
    compare("i7: PT-W 8×1 vs TW-LNS 4×2 (eight threads)", "final/heur_lns_janela", "i7/ptw_8x1")
    compare("i7: PT-W 4×2 vs TW-LNS 4×2 (eight threads, same layout)", "final/heur_lns_janela", "i7/ptw_4x2")
    compare("Ryzen: PT-W 8×1 vs TW-LNS 4×2 (eight threads)", "ryzen/heur_lns_janela_4x2", "ryzen/ptw_8x1")
    compare("Ryzen: PT-W 16×1 vs TW-LNS 8×2 (sixteen threads)", "ryzen/heur_lns_janela_8x2", "ryzen/ptw_16x1")
    e8 = compare("Xeon: PT-W 8×1 vs TW-LNS 4×2 (eight threads)", "xeon/heur_lns_janela_4x2", "xeon/ptw_8x1")
    e16 = compare("Xeon: PT-W 16×1 vs TW-LNS 8×2 (sixteen threads)", "xeon/heur_lns_janela_8x2", "xeon/ptw_16x1")
    e32 = compare("Xeon: PT-W 16×2 vs TW-LNS 16×2 (thirty-two threads)", "xeon/heur_lns_janela_16x2", "xeon/ptw_16x2")
    if e8 and e16 and e32:
        print("\nXeon, effect (mean difference of medians, 95 % CI) by thread count: "
              f"8 threads {e8[0]:+.2f} [{e8[1][0]:+.2f}, {e8[1][1]:+.2f}]; 16 threads {e16[0]:+.2f} "
              f"[{e16[1][0]:+.2f}, {e16[1][1]:+.2f}]; 32 threads {e32[0]:+.2f} [{e32[1][0]:+.2f}, {e32[1][1]:+.2f}].")


def same_geometry():
    print("\n## 3. Same geometry: PT-W 8×1 against eight TW-LNS walkers of one thread\n")
    for plat, ctl in (("i7", "i7/lns_8x1"), ("ryzen", "ryzen/lns_8x1"), ("xeon", "xeon/lns_8x1")):
        compare(f"{PLAT[plat].split(' (')[0]}: PT-W 8×1 vs TW-LNS 8×1", ctl, f"{plat}/ptw_8x1")


def mechanisms():
    print("\n## 4. Mechanism controls, all 8×1, ten seeds (two-sided)\n")
    print("Each control removes or changes one mechanism of PT-W; the control folders are listed in "
          "`experimentos/README.md`.\n")
    arms = [("PE", "ptw_8x1_PE_semtroca", "no slot exchanges"), ("U", "ptw_8x1_U_nucleo_uniforme", "uniform repair kernel"),
            ("F", "ptw_8x1_F_escada_fixa", "fixed ladder"), ("C", "ptw_8x1_C_cache_inicial", "exchange cache initialised to E(s*)"),
            ("PD", "ptw_8x1_PD_alpha0", "α = 0 (energy = makespan)")]
    for plat in ("i7", "ryzen", "xeon"):
        for code, folder, what in arms:
            compare(f"{PLAT[plat].split(' (')[0]}: PT-W 8×1 vs {code} ({what})", f"{plat}/{folder}", f"{plat}/ptw_8x1",
                    onesided=False)
    print("\n#### Combined control F+PD (fixed ladder and α = 0 together), Ryzen, four open instances, ten seeds\n")
    print("Run after the pre-registered campaign, with the same statistics, on the instances that are not solved to a "
          "proved optimum (`lcbrtu_0`, `_3`, `_5`, `_8`): exchanges, geometric ladder, Metropolis acceptance and "
          "slot-dependent kernels unchanged; the ladder is never adapted and the energy is the makespan.\n")
    compare("AMD Ryzen 7 5700U: PT-W 8×1 vs F+PD (fixed ladder, α = 0), four open instances",
            "ryzen/ptw_8x1_FPD_escada_fixa_alpha0", "ryzen/ptw_8x1", ["lcbrtu_0", "lcbrtu_3", "lcbrtu_5", "lcbrtu_8"],
            onesided=False)


def heldout():
    print("\n## 5. Independent instances (`instances/heldout`), ten seeds, budget 4 s × operations\n")
    gen = json.loads((ROOT / "instances" / "heldout" / "GENERATION.json").read_text(encoding="utf-8"))
    ops = {r["stem"]: r["operations"] for r in gen["instances"]}
    bud = {r["stem"]: r["budget_s"] for r in gen["instances"]}
    for plat in ("i7", "ryzen", "xeon"):
        cfg = [("TW-LNS 4×2", f"{plat}/heldout_lns_4x2"), ("PT-W 8×1", f"{plat}/heldout_ptw_8x1"),
               ("PT-W 4×2", f"{plat}/heldout_ptw_4x2"), ("CP-SAT w8, whole model", f"{plat}/heldout_mono_w8")]
        cs = [(n, d) for n, d in cfg if exists(d)]
        if not cs:
            continue
        D = {n: load(d) for n, d in cs}
        LB = load(f"{plat}/heldout_mono_w8", "lower_bound")
        print(f"\n#### {PLAT[plat]} — best / median over ten seeds; bound = best solver bound of the whole-model runs\n")
        print("| instance | operations | budget (s) | " + " | ".join(n for n, _ in cs) + " | best bound | gap of the best value (%) |")
        print("|---|---:|---:|" + "---:|" * len(cs) + "---:|---:|")
        for i in HELD:
            best = min(min(D[n][i].values()) for n, _ in cs if i in D[n])
            lb = max(LB[i].values()) if i in LB else None
            gap = f"{100 * (best - lb) / lb:.1f}" if lb else "–"
            print(f"| {i} | {ops[i]} | {bud[i]} | " + " | ".join(
                f"{min(D[n][i].values())} / {st.median(D[n][i].values()):g}" if i in D[n] else "–" for n, _ in cs)
                  + f" | {lb if lb else '–'} | {gap} |")
        for name, ins in (("fifteen instances", HELD), ("ten instances of 98–156 operations", HELD[:10]),
                          ("five instances of 200–232 operations", HELD[10:])):
            compare(f"{PLAT[plat].split(' (')[0]}, {name}: PT-W 8×1 vs TW-LNS 4×2", f"{plat}/heldout_lns_4x2",
                    f"{plat}/heldout_ptw_8x1", ins)
        compare(f"{PLAT[plat].split(' (')[0]}, fifteen instances: PT-W 4×2 vs PT-W 8×1 (two-sided)",
                f"{plat}/heldout_ptw_8x1", f"{plat}/heldout_ptw_4x2", HELD, onesided=False)
        compare(f"{PLAT[plat].split(' (')[0]}, fifteen instances: PT-W 8×1 vs CP-SAT on the whole model (8 workers)",
                f"{plat}/heldout_mono_w8", f"{plat}/heldout_ptw_8x1", HELD)
        compare(f"{PLAT[plat].split(' (')[0]}, fifteen instances: TW-LNS 4×2 vs CP-SAT on the whole model (8 workers)",
                f"{plat}/heldout_mono_w8", f"{plat}/heldout_lns_4x2", HELD)


def sensitivity():
    print("\n## 6. Sensitivity of the thermal controls (lcbrtu_3, _5, _8; seeds 1–5; two-sided against PT-W 8×1)\n")
    arms = [("sens_T_x05", "temperature endpoints halved (0.075–0.75)"), ("sens_T_x2", "temperature endpoints doubled (0.3–3.0)"),
            ("sens_delta1_deriva3", "Δ_max = 1, drift = 3"), ("sens_delta6_deriva10", "Δ_max = 6, drift = 10"),
            ("sens_subhot2", "hottest-slot subproblem limit 2 s"), ("sens_subhot8", "hottest-slot subproblem limit 8 s")]
    for plat in ("i7", "ryzen"):
        for folder, what in arms:
            compare(f"{PLAT[plat].split(' (')[0]}: PT-W 8×1 vs {what}", f"{plat}/{folder}", f"{plat}/ptw_8x1", SCREEN,
                    seeds=[1, 2, 3, 4, 5], onesided=False)
    print("\n#### Processing times multiplied by ten (`instances/scaled10`), unscaled budget, seeds 1–5\n")
    print("| platform | instance | TW-LNS 4×2 best / median (×10) | PT-W 8×1 best / median (×10) | TW-LNS 4×2 best / median (original, seeds 1–5) | PT-W 8×1 best / median (original, seeds 1–5) |")
    print("|---|---|---|---|---|---|")
    for plat in ("i7", "ryzen"):
        L10, P10 = load(f"{plat}/escala10_lns_4x2"), load(f"{plat}/escala10_ptw_8x1")
        L1 = load("final/heur_lns_janela" if plat == "i7" else "ryzen/heur_lns_janela_4x2")
        P1 = load(f"{plat}/ptw_8x1")
        if not L10 or not P10:
            continue
        for i in SCALED:
            o = i[:-4]
            l1 = [L1[o][k] for k in range(1, 6)]; p1 = [P1[o][k] for k in range(1, 6)]
            print(f"| {plat} | {i} | {min(L10[i].values())} / {st.median(L10[i].values()):g} | "
                  f"{min(P10[i].values())} / {st.median(P10[i].values()):g} | {min(l1)} / {st.median(l1):g} | "
                  f"{min(p1)} / {st.median(p1):g} |")


def calibration():
    d = R / "i7" / "calibracao_janela"
    if not d.exists():
        return
    print("\n## 7. Calibration grid rerun with the time-window-only search (i7, ten calibration instances, ten runs × 60 s, 4×2)\n")
    runs = [json.load(open(f, encoding="utf-8")) for f in glob.glob(str(d / "runs" / "*.json"))]
    best = {}
    for r in runs:
        best[r["instancia"]] = min(best.get(r["instancia"], 10 ** 9), r["makespan"])
    tab = collections.defaultdict(list)
    for r in runs:
        tab[r["combo"]].append(100.0 * (r["makespan"] - best[r["instancia"]]) / best[r["instancia"]])
    rows = sorted(((st.mean(v), k, len(v)) for k, v in tab.items()))
    orig = json.loads((R / "final" / "calibracao" / "escolha.json").read_text(encoding="utf-8"))
    print("| cell (SUB_TIME, RHO0) | runs | mean RPD (%) |")
    print("|---|---:|---:|")
    for m, k, n in rows:
        print(f"| {k.replace('SUB_TIME', '').replace('_RHO0', ', ')} | {n} | {m:.2f} |")
    print(f"\nBest cell of the window-only grid: {rows[0][1]} ({rows[0][0]:.2f} %). The pair used by all campaigns, "
          f"SUB_TIME = {orig['parametros']['SUB_TIME']}, RHO0 = {orig['parametros']['RHO0']} (chosen on the "
          f"four-neighbourhood grid, `results/final/calibracao`), has mean RPD "
          f"{st.mean(tab['SUB_TIME8.0_RHO00.25']):.2f} % on the window-only grid.")


def diagnostics():
    print("\n## 8. Search diagnostics from the PT-W 8×1 result files (ten seeds)\n")
    print("Per slot, summed over the ten instances, ten seeds and the replicas that occupied the slot: proposals "
          "returned by the solver, accepted proposals, accepted deteriorations, subproblems without a solution, and "
          "global improvements (new best makespan) first found in the slot.\n")
    for plat in ("i7", "ryzen", "xeon"):
        d = f"{plat}/ptw_8x1"
        if not exists(d):
            continue
        agg = collections.defaultdict(lambda: [0, 0, 0, 0, 0])
        ex_rate, trips = [], []
        for f in glob.glob(str(R / d / "*.json")):
            j = json.load(open(f, encoding="utf-8"))
            dg = j.get("diagnostico_pt", {})
            for stt in dg.get("replicas", {}).values():
                for s in range(len(stt["prop"])):
                    agg[s][0] += stt["prop"][s]; agg[s][1] += stt["acc"][s]; agg[s][2] += stt["pior_ac"][s]
                    agg[s][3] += stt["semsol"][s]
                trips.append(stt.get("trips", 0))
            for t, mk, s, rid in j.get("trajetoria", []):
                if s is not None and s >= 0:
                    agg[s][4] += 1
            ex_rate += [x for x in dg.get("taxa_troca", []) if x is not None]
        print(f"\n#### {PLAT[plat].split(' (')[0]}\n")
        print("| slot | proposals | accepted | accepted deteriorations | without solution | global improvements |")
        print("|---:|---:|---:|---:|---:|---:|")
        for s in sorted(agg):
            v = agg[s]
            print(f"| {s} | {v[0]} | {v[1]} | {v[2]} | {v[3]} | {v[4]} |")
        print(f"\nExchange acceptance rate per pair, mean over runs: {st.mean(ex_rate):.3f}; round trips "
              f"(replica visiting both ends of the ladder), mean per replica: {st.mean(trips):.2f}.")


def instrumented():
    print("\n## 9. Instrumented PT-W 8×1 (seeds 1–3): time shares and exchange bookkeeping\n")
    for plat in ("i7", "ryzen", "xeon"):
        d = f"{plat}/ptw_8x1_D_instrumentado"
        if not exists(d):
            continue
        compare(f"{PLAT[plat].split(' (')[0]}: instrumented run vs PT-W 8×1 (seeds 1–3, two-sided)", f"{plat}/ptw_8x1", d,
                seeds=[1, 2, 3], onesided=False)
        tb = ts = tc = tt = 0.0
        nmov = nex = ok = unpub = stale = 0
        slot = collections.defaultdict(lambda: [0, 0, 0, 0, 0.0])
        for f in glob.glob(str(R / d / "*.json")):
            j = json.load(open(f, encoding="utf-8"))
            for stt in j.get("diagnostico_pt", {}).get("replicas", {}).values():
                c = stt.get("ctrl", {})
                tb += c.get("t_build", 0); ts += c.get("t_solve", 0); tc += c.get("t_coord", 0); tt += c.get("t_total", 0)
                for m in c.get("movimentos", []):
                    nmov += 1; s = m[1]
                    slot[s][0] += 1; slot[s][1] += m[8]
                    if m[7] is not None and m[7] > 0 and m[8]:
                        slot[s][2] += 1
                    if m[7] is None:
                        slot[s][3] += 1
                    slot[s][4] += m[3]
                for e in c.get("trocas", []):
                    nex += 1; ok += bool(e[3]); unpub += bool(e[4]); stale += bool(e[5])
        if not nmov:
            continue
        other = tt - tb - ts - tc
        print(f"\nMoves: {nmov}. Time in the solver {ts / tt:.1%}, building CP models {tb / tt:.1%}, under the shared "
              f"lock {tc / tt:.1%}, other (neighbourhood, energy, bookkeeping) {other / tt:.1%} of {tt:.0f} s of replica time.")
        print(f"Exchange attempts: {nex}; accepted {ok / nex:.1%}; neighbour without a published energy "
              f"{unpub / nex:.2%}; published energy older than the neighbour's last acceptance {stale / nex:.2%}.")
        print("\n| slot | moves | accepted | accepted deteriorations | without solution | mean window size |")
        print("|---:|---:|---:|---:|---:|---:|")
        for s in sorted(slot):
            v = slot[s]
            print(f"| {s} | {v[0]} | {v[1]} | {v[2]} | {v[3]} | {v[4] / v[0]:.0f} |")


def trajectories():
    print("\n## 10. Time–quality: median best makespan at fractions of the budget (ten seeds)\n")
    fr = (0.1, 0.25, 0.5, 0.75, 1.0)
    pairs = [("i7", "TW-LNS 4×2", "final/heur_lns_janela"), ("i7", "PT-W 8×1", "i7/ptw_8x1"),
             ("ryzen", "TW-LNS 4×2", "ryzen/heur_lns_janela_4x2"), ("ryzen", "PT-W 8×1", "ryzen/ptw_8x1"),
             ("xeon", "TW-LNS 4×2", "xeon/heur_lns_janela_4x2"), ("xeon", "PT-W 8×1", "xeon/ptw_8x1")]
    print("| platform | configuration | instance | " + " | ".join(f"{int(x * 100)} % of T" for x in fr) + " |")
    print("|---|---|---|" + "---:|" * len(fr))
    for plat, name, d in pairs:
        if not exists(d):
            continue
        per = collections.defaultdict(lambda: collections.defaultdict(list))
        for f in glob.glob(str(R / d / "*.json")):
            j = json.load(open(f, encoding="utf-8"))
            T = j["orcamento"]
            tr = j["trajetoria"]
            for x in fr:
                vals = [h[1] for h in tr if h[0] <= x * T + 1e-9]
                per[j["instance"]][x].append(min(vals) if vals else None)
        for i in INST:
            if i not in per:
                continue
            cells = []
            for x in fr:
                v = [y for y in per[i][x] if y is not None]
                cells.append(f"{st.median(v):g}" if len(v) == len(per[i][x]) and v else "–")
            print(f"| {plat} | {name} | {i} | " + " | ".join(cells) + " |")


def bounds():
    print("\n## 11. Best values and best solver bounds per benchmark instance over all audited runs in `results/`\n")
    best = {}
    where = {}
    lbs = collections.defaultdict(list)
    for f in glob.glob(str(R / "*" / "*" / "*.json")):
        j = json.load(open(f, encoding="utf-8"))
        if not isinstance(j, dict) or j.get("instance") not in INST or j.get("experiment") != "exp4":
            continue
        if j.get("makespan") and j.get("schedule"):
            if j["makespan"] < best.get(j["instance"], 10 ** 9):
                best[j["instance"]] = j["makespan"]
                where[j["instance"]] = str(Path(f).relative_to(R).parent)
        if j.get("lower_bound"):
            lbs[j["instance"]].append((j["lower_bound"], str(Path(f).relative_to(R).parent)))
    their = {}
    for f in glob.glob(str(R / "final" / "heur_lns_janela" / "*.json")):
        j = json.load(open(f, encoding="utf-8"))
        their[j["instance"]] = (j["their_lb"], j["their_alns"])
    print("| instance | published LB | published ALNS-CP | best audited value | folder | best solver bound | folder |")
    print("|---|---:|---:|---:|---|---:|---|")
    for i in INST:
        lb = max(lbs[i]) if lbs[i] else (None, "–")
        print(f"| {i} | {their[i][0]} | {their[i][1]} | {best[i]} | `{where[i]}` | {lb[0] if lb[0] else '–'} | `{lb[1]}` |")
    print("\nSolver bounds are those declared by CP-SAT or CP Optimizer in the run that produced them; folders named "
          "`reservatorio_*` use the native-reservoir encoding, the others the validated pairwise encoding.")


def contextual(b):
    cfg = [("i7, 8", "native-reservoir CP-SAT at T_i, 10 seeds", "final/reservatorio_w8_TALNS"),
           ("Ryzen, 8", "native-reservoir CP-SAT at T_i, 10 seeds", "ryzen/reservatorio_w8_TALNS"),
           ("Ryzen, 16", "native-reservoir CP-SAT at T_i, 10 seeds", "ryzen/reservatorio_w16_TALNS"),
           ("Xeon, 8", "native-reservoir CP-SAT at T_i, 10 seeds", "xeon/reservatorio_w8_TALNS"),
           ("Xeon, 32", "native-reservoir CP-SAT at T_i, 10 seeds", "xeon/reservatorio_w32_TALNS"),
           ("i7, 8", "validated CP-SAT model, 1800 s, 10 seeds", "final/relato_w8_1800"),
           ("Ryzen, 8", "validated CP-SAT model, 1800 s, 1 run", "ryzen/relato_w8_1800"),
           ("Ryzen, 16", "validated CP-SAT model, 1800 s, 1 run", "ryzen/relato_w16_1800"),
           ("Xeon, 8", "validated CP-SAT model, 1800 s, 1 run", "xeon/relato_w8_1800"),
           ("Xeon, 32", "validated CP-SAT model, 1800 s, 1 run", "xeon/relato_w32_1800"),
           ("i7, 8", "CP Optimizer 22.2, literal model, 1800 s, 1 run", "final/cpo_exp4"),
           ("Ryzen, 8", "CP Optimizer 22.2, literal model, 1800 s, 1 run", "ryzen/cpo_exp4_w8"),
           ("Ryzen, 16", "CP Optimizer 22.2, literal model, 1800 s, 1 run", "ryzen/cpo_exp4_w16")]
    print("\n## 12. Contextual solver baselines\n")
    print("| platform, threads | configuration | folder | encoding | budget | runs | mean best | mean median | wins/ties/losses vs published ALNS-CP |")
    print("|---|---|---|---|---|---:|---:|---:|---|")
    for plat, name, d in cfg:
        if not exists(d):
            continue
        D = load(d)
        best = {i: min(D[i].values()) for i in INST}
        multi = all(len(D[i]) > 1 for i in INST)
        med = f"{sum(st.median(D[i].values()) for i in INST) / 10:.2f}" if multi else "–"
        enc = "native reservoir" if "reservatorio" in d else ("literal Box I" if "cpo" in d else "pairwise (validated)")
        bud = "T_i of Table 10" if "TALNS" in d else "1800 s"
        runs = "10 seeds" if multi else "1"
        w = sum(best[i] < b[i] for i in INST); t = sum(best[i] == b[i] for i in INST)
        print(f"| {plat} | {name} | `{d}` | {enc} | {bud} | {runs} | {sum(best.values()) / 10:.2f} | {med} | {w}/{t}/{10 - w - t} |")


def screen():
    print("\n## 13. Replica-layout screens (three instances, seeds 1–3)\n")
    print("Rule fixed before running: a layout is retained if its median improves the TW-LNS median of the same thread "
          "count on at least two of the three instances and no instance deteriorates by more than three makespan units.\n")
    for plat, ctrl, lays in (("i7", "final/heur_lns_janela", ("8x1", "4x2")), ("ryzen", "ryzen/heur_lns_janela_4x2", ("8x1", "4x2")),
                             ("xeon", "xeon/heur_lns_janela_16x2", ("16x2", "32x1"))):
        if not exists(ctrl):
            continue
        C = load(ctrl)
        for lay in lays:
            A = load(f"{plat}/screen_ptw_{lay}")
            if not A:
                continue
            wins = worst = 0
            cells = []
            for i in SCREEN:
                a = list(A[i].values()); c = list(C[i].values())
                d = st.median(c) - st.median(a)
                wins += d > 0; worst = min(worst, d)
                cells.append(f"{i}: PT-W {min(a)}/{st.median(a):g} vs TW-LNS {min(c)}/{st.median(c):g} (effect {d:+g})")
            verdict = "retained" if wins >= 2 and worst >= -3 else "not retained"
            print(f"* **{plat}, PT-W {lay.replace('x', '×')}** against `{ctrl}` — " + "; ".join(cells) + f" — {verdict}.")
    mc = R / "xeon" / "memcheck.json"
    if mc.exists():
        m = json.loads(mc.read_text(encoding="utf-8"))
        print(f"\nXeon memory check before the 32-thread layouts: peak used memory {m['peak_used_gb']} GB "
              f"(limit {m['limit_gb']} GB, `ok32` = {m['ok32']}).")


def main():
    b = alns_cp()
    print("# Campaign tables (generated by `experimentos/analise_campanhas.py` from the files in `results/`)\n")
    print("Three platforms, never pooled. Budget per benchmark instance = the ALNS-CP time of Table 10 of Kasapidis et "
          "al. (2025), wall clock, construction included; held-out instances use 4 s × operations. Every schedule "
          "behind every number passed the solver-free checker (`rcfjssp_audit.py`). Statistics: exact two-sided "
          "Mann–Whitney per instance with Holm correction; stratified permutation test on the mean of per-instance "
          f"differences of means (N = {N_PERM}, seed {SEED}, p = (c + 1)/(N + 1)); paired-by-instance bootstrap "
          f"({N_BOOT} resamples) for the 95 % CIs.\n")
    main_tables(b)
    matched(b)
    same_geometry()
    mechanisms()
    heldout()
    sensitivity()
    calibration()
    diagnostics()
    instrumented()
    trajectories()
    bounds()
    contextual(b)
    screen()


if __name__ == "__main__":
    main()
