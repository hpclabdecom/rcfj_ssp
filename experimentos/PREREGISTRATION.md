# Pre-registered campaign of controls, held-out and scalability arms (written before any run; 21 October 2026)

*Context sentences and file names in this document were edited after the campaign for neutral wording; the arms,
hypotheses, decision rules, budgets and statistics are unchanged since the commit of 21 October 2026 that preceded
the first run.*

This document fixes, before execution, the arms, hypotheses, decision rules and analysis of the campaign that
isolates the mechanisms of PT-W, evaluates both methods on independent instances and studies scalability. It is
committed together with the scripts and the instance files it refers to; the commit hash is the time stamp. Nothing in TW-LNS or PT-W changes:
the frozen files keep their recorded SHA-256 (`README.md`, "Provenance"), and every control is a derived script
(`rcfjssp_ptw_controls.py`, `rcfjssp_heldout.py`) that imports them and records both hashes in its manifest.

## 1. Platforms, execution and common rules

* Platforms: Intel Core i7-2600 (8 threads), AMD Ryzen 7 5700U (16 threads), Intel Xeon E5-2696 v4 (22 cores,
  44 threads, 16 GB). The i7 and the Ryzen are the reference platforms of the main campaign; the Xeon is a third platform and
  the only one where layouts above 16 threads are run. Results of different machines are never pooled.
* One resumable campaign per machine: `python experimentos/campanha_controles.py` (`CAMPANHA_CONTROLES.bat`). Every arm
  writes one JSON per (instance, seed) with a protocol hash; an interrupted campaign is resumed by relaunching the
  same command, which skips finished runs. On the Xeon, 8-thread arms run two at a time on disjoint sets of eight
  physical cores (affinity masks `0xFFFF` and `0xFFFF0000`); every 8-thread arm of the Xeon, including its own
  TW-LNS and PT-W references, runs under this same condition. Arms of 16 and 32 threads run alone.
* Budgets: the per-instance Table 10 times T_i for the benchmark instances; `4 s × number of operations` for the
  held-out instances (the mean of T_i divided by the number of operations over Table 10 is 3.7 s per operation,
  rounded up); the unscaled T_i for the ×10 instances.
* Seeds 1–10 for every main arm; seeds 1–5 for the sensitivity arms (three instances); seeds 1–3 for the
  instrumented arm and the Xeon layout screen.
* Software fixed: `ortools==9.15.6755`; Python 3.13/3.14. The solver-free checker runs on every folder; a run whose
  construction fails inside T/2 is recorded as a run without result and reported, never rerun with other settings.
* The 32-thread layouts on the Xeon run only if `memcheck.py` records a peak system memory below 12 GB during a
  short PT-W 16×2 run (`results/xeon/memcheck.json`, field `ok32`); otherwise they are reported as not executable on
  that machine.

## 2. Statistics (identical for every comparison)

* Per instance: exact two-sided Mann–Whitney U test (average ranks, full enumeration), Holm correction over the
  non-degenerate instances of the same comparison.
* Across instances: stratified permutation test on the mean of the per-instance differences of means (labels
  permuted within instance, N = 20 000, fixed seed), p = (c + 1)/(N + 1), one-sided where a direction is
  pre-specified below and two-sided otherwise.
* Effect sizes with 95 % confidence intervals: paired-by-instance bootstrap (10 000 resamples of seeds within each
  instance) of the mean difference of medians and of the mean difference of means.
* Win/tie/loss counts are defined from the two per-instance medians.
* "No detectable difference" is reported only when the 95 % CI of the mean difference of medians lies within
  ±1.0 makespan units; otherwise the result is reported as inconclusive or as a difference, according to p.
* Global p-values of different comparisons are not adjusted across comparisons; the number of comparisons is stated.

## 3. Arms, hypotheses and decision rules

Reference on each machine: PT-W 8×1 (`ptw_8x1`) and TW-LNS 4×2 (`heur_lns_janela*`), ten seeds, already published
for the i7 and the Ryzen and run anew on the Xeon.

### A'. Same geometry (`lns_8x1`)
Eight TW-LNS walkers with one thread each, ten instances, ten seeds. Direction: PT-W 8×1 better. Isolates the whole
PT layer (energy, heterogeneous kernels, Metropolis acceptance, exchanges, ladder) from the process layout.

### B. Mechanisms of PT-W, all 8×1, ten instances, ten seeds (i7 and Ryzen; PE, U and C also on the Xeon)
| arm | folder | what changes | question answered |
|---|---|---|---|
| PE | `ptw_8x1_PE_semtroca` | no slot exchanges (`--sem-troca`) | does replica interaction contribute beyond heterogeneous searches? |
| U | `ptw_8x1_U_nucleo_uniforme` | every slot uses the slot-0 repair kernel; temperatures, acceptance and exchanges unchanged | does kernel heterogeneity contribute beyond exchanged replicas with uniform repairs? |
| F | `ptw_8x1_F_escada_fixa` | the ladder is never adapted | does ladder adaptation matter? |
| C | `ptw_8x1_C_cache_inicial` | published energies start at E(s*) instead of 0 | does the initial cache value affect results? |
| PD | `ptw_8x1_PD_alpha0` | α = 0 (energy = makespan) | does the secondary energy term matter? |

Each arm is compared with PT-W 8×1 of the same machine (two-sided; direction not pre-specified). A mechanism is
reported as contributing if the arm without it is worse with global p < 0.05 and the CI of the effect excludes zero;
as not detectable under the rule of Section 2; otherwise inconclusive. The earlier three-instance, five-seed checks of the same mechanisms are superseded by these arms.

### C. Scale and robustness of the thermal controls (three instances `lcbrtu_3`, `_5`, `_8`; seeds 1–5; i7 and Ryzen)
Variants of PT-W 8×1: temperature endpoints halved (0.075–0.75) and doubled (0.3–3.0); relaxation and drift
(Δ_max, drift) = (1, 3) and (6, 10); hottest-slot subproblem limit 2 s and 8 s; and PT-W 8×1 and TW-LNS 4×2 on
`lcbrtu_3/5/8` with all processing times multiplied by 10 at the unscaled budget (`instances/scaled10`). Each variant
is compared with PT-W 8×1 seeds 1–5 (two-sided). The thermal controls are reported as robust on the tested range if
no variant differs from PT-W by more than 2 units in the mean of medians with p < 0.05; the ×10 arm reports the
observed dependence on the time scale (both methods, same instances), without a pass/fail rule.

### D. Instrumented PT-W (`ptw_8x1_D_instrumentado`, ten instances, seeds 1–3, all machines)
Identical search with per-move records: time to build the CP model, time in the solver, time under the shared lock,
window size ρ, status, ΔE, acceptance; per exchange attempt: slots, acceptance, whether the neighbour had not yet
published an energy, whether its published energy differed from its last accepted one. Reported: the three time
shares; ρ trajectories; the fraction of exchange attempts with an unpublished or stale neighbour energy; proposals,
acceptances, accepted deteriorations and sources of global improvements per slot (the latter are already in every
PT-W JSON of the main campaigns and are also reported from them). The arm's makespans are checked against PT-W 8×1
(same seeds) to confirm that instrumentation did not change the search materially.

### E. Scalability (Xeon only)
* `heur_lns_janela_8x2` and `ptw_16x1` (16 threads on 16 physical cores). H-E1 (one-sided): PT-W 16×1 improves the
  medians of TW-LNS 8×2.
* If the memory check passes: `heur_lns_janela_16x2`, the layout screen `screen_ptw_16x2` / `screen_ptw_32x1`
  (three instances, seeds 1–3, rule: retained if the PT-W median improves the TW-LNS 16×2 median on at least two of
  the three instances and no instance is worse by more than three units; pre-registered primary 16×2, i.e. one
  replica per physical core with two solver threads; 32×1 is run only if 16×2 fails the rule and 32×1 passes), then
  the full campaign of the chosen layout. H-E2 (one-sided): PT-W at 32 threads improves the medians of TW-LNS 16×2.
  H-E3 (descriptive, directional): the effect at 32 threads is larger than the effect of PT-W 8×1 vs TW-LNS 4×2 on
  the same machine; reported with the two bootstrap CIs, without a significance claim on their difference.
* Monolithic baselines at 32 threads (`reservatorio_w32_TALNS`, `relato_w32_1800`) and at 8 threads, descriptive.

### G. Held-out instances (`instances/heldout`; i7, Ryzen and Xeon)
Fifteen new combined-resource instances generated by `gera_instancias.py` (seed 20261021) from the ranges of §5.4.4
of Kasapidis et al. and the structure observed in `lcbrtu_0`–`lcbrtu_9` (`instances/heldout/README.md`): ten of
98–156 operations (`rcfj_h_0`–`rcfj_h_9`) and five of 200–300 operations (`rcfj_hl_0`–`rcfj_hl_4`). Their SHA-256
(`instances/heldout/SHA256SUMS`) and budgets (`budgets.json`) are committed before the first run. Arms, ten seeds:
`heldout_lns_4x2`, `heldout_ptw_8x1`, `heldout_ptw_4x2`, `heldout_mono_w8`.
* H-G1 (primary, one-sided): PT-W 8×1 improves the medians of TW-LNS 4×2 on the held-out set; reported for the
  fifteen instances and separately for the two size classes.
* H-G2 (two-sided): PT-W 4×2 vs PT-W 8×1 on the held-out set, the layout question asked on data not used to select
  the layout.
* The monolithic native-reservoir CP-SAT at the same budget is the contextual control; its best and median are
  reported, together with the gap of every method to the best solver bound found in those runs.
* No parameter of either method is changed for these instances.

### H. Transfer of the calibrated pair (i7 only, `calibracao_janela`)
The 4×4 grid of (θ, ρ₀) is rerun with the time-window-only runner on the ten calibration instances of Kasapidis et
al. (ten runs × 60 s per cell, 4×2). Rule: the transfer of (8 s, 0.25) is reported as supported if that pair is
among the two best by mean RPD or its mean RPD is within one percentage point of the best; otherwise the best pair of
the window-only grid is reported and the consequence discussed (no rerun of the main campaigns with other values).

## 4. What is reported without new runs
Paired bootstrap CIs and the p-value convention above for the four matched comparisons of the main campaign; residual
gaps to the best known bounds; per-slot activity and sources of global improvements from the existing PT-W JSON
files; time–quality trajectories of TW-LNS and PT-W from `trajetoria`; a direct-effect figure; a table linking each
contextual baseline to its encoding, budget convention, replication and machine.

## 5. Order of execution and estimated machine time
i7: A' → B (PE, U, F, C, PD) → G → D → C → H (≈ 230 h). Ryzen: A' → B → G → D → C (≈ 205 h). Xeon: memory check →
E (16 threads) → E (32 threads, if cleared) → 32-thread baselines → then, in pairs: references, A', B (PE, U, C),
G, D, 8-thread baselines (≈ 275 machine-hours, ≈ 170 h wall). `campanha_controles.py --listar` prints the plan of the
machine it runs on.
