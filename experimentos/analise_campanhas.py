from __future__ import annotations
import glob, itertools, json, random, statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "results"
INST = [f"lcbrtu_{i}" for i in range(10)]
SCREEN = ["lcbrtu_3", "lcbrtu_5", "lcbrtu_8"]


def load(d):
    out, meta = {}, set()
    for f in glob.glob(str(R / d / "*.json")):
        j = json.load(open(f, encoding="utf-8"))
        if not isinstance(j, dict) or j.get("makespan") is None:
            continue
        out.setdefault(j["instance"], {})[j.get("seed", 1)] = j["makespan"]
        m = j.get("maquina", {})
        meta.add(str(m.get("cpu") or m.get("processor") or "?"))
    return out, meta


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
    tot = sum(rk)
    mu = n * tot / N
    obs = abs(sum(rk[:n]) - mu)
    c = t = 0
    for comb in itertools.combinations(range(N), n):
        s = sum(rk[i] for i in comb)
        t += 1
        if abs(s - mu) >= obs - 1e-9:
            c += 1
    return c / t


def holm(ps):
    idx = [i for i, p in enumerate(ps) if p is not None]
    m = len(idx)
    out = [None] * len(ps)
    order = sorted(idx, key=lambda i: ps[i])
    run = 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (m - k) * ps[i]))
        out[i] = run
    return out


def strat_perm(pairs, n=20000, seed=11, onesided=True):
    rnd = random.Random(seed)
    obs = sum(st.mean(c) - st.mean(a) for a, c in pairs) / len(pairs)
    cnt = 0
    for _ in range(n):
        t = 0.0
        for a, c in pairs:
            p = a + c
            rnd.shuffle(p)
            t += st.mean(p[len(a):]) - st.mean(p[:len(a)])
        t /= len(pairs)
        if (t >= obs - 1e-9) if onesided else (abs(t) >= abs(obs) - 1e-9):
            cnt += 1
    return obs, cnt / n


def fmt_p(p):
    if p is None:
        return "–"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def compare(title, control, arm, insts=INST, seeds=None):
    A, ma = load(arm)
    C, mc = load(control)
    print(f"\n#### {title}\n")
    print(f"Arm `{arm}` ({'; '.join(sorted(ma))}) against control `{control}` ({'; '.join(sorted(mc))}). "
          "Effect = median(control) − median(arm); **positive = the arm is better**.\n")
    print("| instance | arm best / median / mean | control best / median / mean | effect (median) | exact p | Holm p |")
    print("|---|---|---|---:|---:|---:|")
    rows, ps = [], []
    for i in insts:
        ks = sorted(set(A.get(i, {})) & set(C.get(i, {}))) if seeds is None else [k for k in seeds if k in A.get(i, {}) and k in C.get(i, {})]
        if not ks:
            continue
        a = [A[i][k] for k in ks]
        c = [C[i][k] for k in ks]
        rows.append((i, a, c))
        ps.append(mw_exact(a, c))
    hs = holm(ps)
    w = l = t = 0
    pairs = [(a, c) for _, a, c in rows]
    for (i, a, c), p, h in zip(rows, ps, hs):
        d = st.median(c) - st.median(a)
        w += d > 0
        l += d < 0
        t += d == 0
        print(f"| {i} | {min(a)} / {st.median(a):g} / {st.mean(a):.1f} (n={len(a)}) | "
              f"{min(c)} / {st.median(c):g} / {st.mean(c):.1f} (n={len(c)}) | {d:+g} | {fmt_p(p)} | {fmt_p(h)} |")
    obs, p = strat_perm(pairs)
    print(f"\nInstances with a better / equal / worse median in the arm: **{w} / {t} / {l}**. "
          f"Stratified permutation test (20 000 resamples, one-sided): mean difference of means **{obs:+.2f}**, p {fmt_p(p)}.")
    print(f"Sum of the best values: arm {sum(min(a) for _, a, c in rows)} vs control {sum(min(c) for _, a, c in rows)}.")
    return obs, p


def platform_tables(b):
    cfg = [("TW-LNS 4×2", "final/heur_lns_janela", "i7"), ("PT-W 8×1", "i7/ptw_8x1", "i7"), ("PT-W 4×2", "i7/ptw_4x2", "i7"),
           ("TW-LNS 4×2", "ryzen/heur_lns_janela_4x2", "ryzen"), ("TW-LNS 8×2", "ryzen/heur_lns_janela_8x2", "ryzen"),
           ("PT-W 8×1", "ryzen/ptw_8x1", "ryzen"), ("PT-W 16×1", "ryzen/ptw_16x1", "ryzen")]
    for plat in ("i7", "ryzen"):
        name = "Intel Core i7-2600" if plat == "i7" else "AMD Ryzen 7 5700U"
        print(f"\n## {name}\n\n#### Platform table — best / median / mean over ten seeds\n")
        cs = [(n, d) for n, d, p in cfg if p == plat]
        D = {n: load(d)[0] for n, d in cs}
        print("| instance | published ALNS-CP | " + " | ".join(n for n, _ in cs) + " |")
        print("|---|---:|" + "---:|" * len(cs))
        for i in INST:
            print(f"| {i} | {b[i]} | " + " | ".join(
                f"{min(D[n][i].values())} / {st.median(D[n][i].values()):g} / {st.mean(D[n][i].values()):.1f}" for n, _ in cs) + " |")
        print("| **mean of medians** | " + f"{sum(b.values())/10:.2f} | " + " | ".join(
            f"{sum(st.median(D[n][i].values()) for i in INST)/10:.2f}" for n, _ in cs) + " |")
        print("| best of ten below published ALNS-CP | – | " + " | ".join(
            f"{sum(min(D[n][i].values()) < b[i] for i in INST)}/10" for n, _ in cs) + " |")
        print("| median below / equal / above published ALNS-CP | – | " + " | ".join(
            f"{sum(st.median(D[n][i].values()) < b[i] for i in INST)}/"
            f"{sum(st.median(D[n][i].values()) == b[i] for i in INST)}/"
            f"{sum(st.median(D[n][i].values()) > b[i] for i in INST)}" for n, _ in cs) + " |")


def contextual(b):
    cfg = [("i7, 8", "native-reservoir CP-SAT at T_i, 10 seeds", "final/reservatorio_w8_TALNS"),
           ("Ryzen, 8", "native-reservoir CP-SAT at T_i, 10 seeds", "ryzen/reservatorio_w8_TALNS"),
           ("Ryzen, 16", "native-reservoir CP-SAT at T_i, 10 seeds", "ryzen/reservatorio_w16_TALNS"),
           ("i7, 8", "validated CP-SAT model, 1800 s, 10 seeds", "final/relato_w8_1800"),
           ("Ryzen, 8", "validated CP-SAT model, 1800 s, 1 run", "ryzen/relato_w8_1800"),
           ("Ryzen, 16", "validated CP-SAT model, 1800 s, 1 run", "ryzen/relato_w16_1800"),
           ("i7, 8", "CP Optimizer 22.2, literal model, 1800 s, 1 run", "final/cpo_exp4"),
           ("Ryzen, 8", "CP Optimizer 22.2, literal model, 1800 s, 1 run", "ryzen/cpo_exp4_w8"),
           ("Ryzen, 16", "CP Optimizer 22.2, literal model, 1800 s, 1 run", "ryzen/cpo_exp4_w16")]
    print("\n## Contextual solver baselines\n")
    print("Best of the runs (or the single run) against the published ALNS-CP best; medians only where ten seeds exist.\n")
    print("| platform, threads | configuration | folder | mean best | mean median | wins/ties/losses vs ALNS-CP |")
    print("|---|---|---|---:|---:|---|")
    for plat, name, d in cfg:
        D, _ = load(d)
        best = {i: min(D[i].values()) for i in INST}
        multi = all(len(D[i]) > 1 for i in INST)
        med = f"{sum(st.median(D[i].values()) for i in INST)/10:.2f}" if multi else "–"
        w = sum(best[i] < b[i] for i in INST); t = sum(best[i] == b[i] for i in INST); l = 10 - w - t
        print(f"| {plat} | {name} | `{d}` | {sum(best.values())/10:.2f} | {med} | {w}/{t}/{l} |")


def screen():
    print("\n## Replica-layout screen (three instances, seeds 1–3)\n")
    print("Rule fixed before running: a layout is retained if its median improves the TW-LNS median on at least two of the three "
          "instances and no instance deteriorates by more than three makespan units.\n")
    for plat, ctrl in (("i7", "final/heur_lns_janela"), ("ryzen", "ryzen/heur_lns_janela_4x2")):
        C, _ = load(ctrl)
        for lay in ("8x1", "4x2"):
            A, _ = load(f"{plat}/screen_ptw_{lay}")
            if not A:
                continue
            wins = worst = 0
            cells = []
            for i in SCREEN:
                a = list(A[i].values()); c = list(C[i].values())
                d = st.median(c) - st.median(a)
                wins += d > 0
                worst = min(worst, d)
                cells.append(f"{i}: PT-W {min(a)}/{st.median(a):g} vs TW-LNS {min(c)}/{st.median(c):g} (effect {d:+g})")
            verdict = "retained" if wins >= 2 and worst >= -3 else "not retained"
            print(f"* **{plat}, PT-W {lay.replace('x', '×')}** — " + "; ".join(cells) + f" — {verdict}.")


def main():
    b = alns_cp()
    print("# Campaign tables (generated by `experimentos/analise_campanhas.py` from the files in `results/`)\n")
    print("Two platforms, never pooled. Budget per instance = the ALNS-CP time of Table 10 of Kasapidis et al. (2025), wall clock, "
          "construction included; ten seeds per configuration; every schedule passed the solver-free checker.\n")
    platform_tables(b)
    print("\n## PT-W against TW-LNS, same platform and same number of threads\n")
    compare("i7: PT-W 8×1 vs TW-LNS 4×2 (eight threads)", "final/heur_lns_janela", "i7/ptw_8x1")
    compare("i7: PT-W 4×2 vs TW-LNS 4×2 (eight threads, same layout)", "final/heur_lns_janela", "i7/ptw_4x2")
    compare("Ryzen: PT-W 8×1 vs TW-LNS 4×2 (eight threads)", "ryzen/heur_lns_janela_4x2", "ryzen/ptw_8x1")
    compare("Ryzen: PT-W 16×1 vs TW-LNS 8×2 (sixteen threads)", "ryzen/heur_lns_janela_8x2", "ryzen/ptw_16x1")
    print("\n## Exploratory cross-platform comparison (eight threads)\n")
    compare("TW-LNS 4×2: Ryzen (arm) vs i7 (control)", "final/heur_lns_janela", "ryzen/heur_lns_janela_4x2")
    compare("PT-W 8×1: Ryzen (arm) vs i7 (control)", "i7/ptw_8x1", "ryzen/ptw_8x1")
    contextual(b)
    screen()


if __name__ == "__main__":
    main()
