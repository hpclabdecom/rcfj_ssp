# `experimentos/` — campaign scripts, TW-LNS, PT-W, calibration and analysis

Every script in this folder is run from the repository root (`python experimentos/<script>.py ...`); each inserts the
root and this folder in `sys.path`, imports the core modules, and writes one JSON per (instance, seed) plus a
`protocolo.manifest` into its output folder.

| script | what it runs | output folders |
|---|---|---|
| `maquina.py` | machine guard and CPU/RAM/OS description written into every result | — |
| `preflight_maquina.py` | checks CPU, RAM, Python, OR-Tools, docplex and the `cpoptimizer` executable; solves one Experiment-4 instance for a few seconds with each solver | `results/preflight_<host>.json` |
| `rcfjssp_valida_i7.py` | Tables 7–9 (110 cells) with the four CP-SAT models, 300 s per cell (`--saida`, default `results/_local/validacao`); `python rcfjssp_campaign.py --report` prints the agreement of `results/final/validacao` | `results/final/validacao` |
| `rcfjssp_cpo.py` | literal interval-variable model in CP Optimizer: `--exp 1/2/3 --check` for Tables 7–9, `--exp 4 --limit 1800` for Table 10 | `results/final/cpo_exp123`, `cpo_exp4`; `results/ryzen/cpo_exp4_w8`, `cpo_exp4_w16` |
| `rcfjssp_final.py` | exact CP-SAT on the validated full model of Experiment 4, 1800 s per run, with solver log; arm `relato` = from scratch, seeds 1–10 | `results/final/relato_w8_1800`; `results/ryzen/relato_w8_1800`, `relato_w16_1800` |
| `instancias_calibracao.py`, `calibra_lns.py` | parser for the FJSSP/JSSP calibration instances; 4 × 4 grid of (θ, ρ₀) × 10 instances × 10 runs × 60 s; writes the chosen pair to `escolha.json` | `results/final/calibracao/{runs,escolha.json}` |
| `modelo_reservatorio.py` | the full model with Eqs. 12–13 as native CP-SAT reservoir constraints; used by TW-LNS, PT-W and `x10_reservatorio.py` | — |
| `rcfjssp_lns.py` | **TW-LNS** (`--viz janela`) | `results/final/heur_lns_janela`; `results/ryzen/heur_lns_janela_4x2`, `heur_lns_janela_8x2` |
| `rcfjssp_ptw.py` | **PT-W** | `results/i7/ptw_8x1`, `ptw_4x2`; `results/ryzen/ptw_8x1`, `ptw_16x1`; the screen folders `screen_ptw_*` |
| `x10_reservatorio.py` | CP-SAT on the whole model with the reservoir encoding, at the per-instance ALNS-CP budget, 10 seeds (native-reservoir baseline) | `results/final/reservatorio_w8_TALNS`; `results/ryzen/reservatorio_w8_TALNS`, `reservatorio_w16_TALNS` |
| `analise_campanhas.py` | reads `results/` (no solver) and prints, in Markdown, the platform tables, the four matched PT-W × TW-LNS comparisons with exact Mann–Whitney p-values, Holm correction and stratified permutation tests, the exploratory cross-platform comparison, the contextual baselines and the replica-layout screen | stdout (`results/TABLES.md`) |

Windows entry points, all run from the repository root:

| file | what it launches |
|---|---|
| `RODA.bat <id>` | the i7 campaigns: `PRE` (preflight), `X0` (checker over `results/final`), `X1` (exact CP-SAT, 1800 s, seeds 1–10; `X1a`/`X1b` halves), `X4` (Tables 7–9, CP-SAT), `X6a`/`X6b` (CP Optimizer, Tables 7–9 / Table 10), `X9` (calibration), `X8b` (TW-LNS 4×2), `X10` (native-reservoir baseline) |
| `RYZEN.bat <id>` | the Ryzen baselines: `R1`/`R1b` TW-LNS 4×2 / 8×2; `R2`/`R2b` native-reservoir CP-SAT at 8 / 16 threads; `R3`/`R3b` CP Optimizer at 8 / 16 workers; `R4`/`R4b` exact CP-SAT at 8 / 16 threads |
| `CAMPANHA_FINAL.bat <id>` | PT-W on either machine: `P8` (8×1), `P8C` (4×2), `P16` (16×1); `TODOS` runs the sequence used on the detected machine; `status` counts the files per folder |
| `SCREEN_PTW.bat B|C` | the replica-layout screen: `B` = 8×1, `C` = 4×2, on `lcbrtu_3`, `lcbrtu_5`, `lcbrtu_8`, seeds 1–3 |
| `TESTA_CPO.bat` | CP Optimizer licence check through `preflight_maquina.py` |

They detect an AMD CPU and add `--qualquer-maquina`; on the i7 they run without it. Each one runs a campaign, then
the solver-free checker on the output folder.

## Common conventions

* **Budget.** Experiment-4 heuristics use, per instance, the ALNS-CP time of the authors' Table 10 (`T_ALNS` in
  `rcfjssp_lns.py`; 179.86–800.39 s), wall clock, construction included. The deadline is set before construction
  and process creation; worker termination and result collection may add one or two seconds to the recorded wall
  time. `--escala x` multiplies the budget, is recorded in the protocol hash (`escala_orcamento`) and is meant for
  functional tests only.
* **Seeds.** `--sementes 1 2 ... 10`. Output file `<instance>_s<seed>.json`.
* **Resuming.** A run whose JSON already exists in the output folder with the same protocol hash is skipped, so an
  interrupted campaign is resumed by repeating the command; `x10_reservatorio.py` moves files of a different hash to
  a `_DESCARTADO_<hash>/` subfolder instead of overwriting them.
* **Every JSON** carries: instance, seed, makespan, the full schedule (`op`, `job`, `index`, `machine`, `start`,
  `end`, `tool`), the solver status and lower bound where the solver gives one, wall time, the protocol hash, the
  machine description and, for the heuristics, the trajectory of improvements and the parameter set.
* **Checker.** `python rcfjssp_audit.py --results <folder>` after every campaign.
* **Article text.** `rcfjssp_lns.py` reads `paper/ref/kasapidis2025_texto.txt` to confirm the Table 10 budgets
  before running; keep that file in place.
* **Reports.** `rcfjssp_lns.py --relatorio --saida <folder>` and `rcfjssp_ptw.py --relatorio --saida <folder>
  --comparar <control>` print the per-instance summary of a finished folder. `rcfjssp_final.py --relatorio` expects a
  parent folder holding only exact-model subfolders (`--saida <folder>`); the file is kept byte-identical for its
  recorded hash, so use `analise_campanhas.py` for the exact-model tables.

## TW-LNS (`rcfjssp_lns.py --viz janela`)

The run deadline is set before construction. A first feasible schedule is obtained from the complete native-reservoir
model with all allocated CP-SAT workers and at most half the budget. Then `W` walkers (processes with `F` CP-SAT
threads each; `4 × 2` on eight threads) repeat until the deadline: adopt the shared incumbent if it has a smaller
makespan than the walker's own schedule; draw a time window of width ρ·C_max at a random offset; free the operations
that intersect the window and fix the machine and the relative machine order of the others (the authors' window
operator, §4.1.1, Eqs. 15–19); solve the subproblem with CP-SAT for at most θ = 8 s (or the time remaining), hinted
with the current schedule and with the current makespan as a ceiling; the returned schedule becomes the local state
(equal or better by construction) and is published if it improves the incumbent. ρ starts at 0.25, is multiplied by
1.15 (up to 0.60) after an optimal repair that does not reduce the local makespan, and divided by 1.15 (down to 0.10)
when the solver returns no schedule. θ = 8 s and ρ₀ = 0.25 come from the calibration grid
(`results/final/calibracao/escolha.json`, read through `--calibracao`); the other constants are design values.

`rcfjssp_lns.py` also contains three further neighbourhoods (`maquinas`, `material`, `critica`) that were part of
the development runner in which the calibration grid was executed; TW-LNS is the `--viz janela` configuration, and
all reported TW-LNS folders use it.

## PT-W (`rcfjssp_ptw.py`)

`K` replicas (processes, `F` threads each) start from the same constructed schedule and occupy the slots 0, …, K−1
of a geometric temperature ladder from 0.15 to 1.5 (makespan units). Energy E(s) = C_max(s) + 0.05 · mean job
completion time. A move is a time-window subproblem as in TW-LNS, but the kernel depends on the slot's heat
h = slot/(K−1): at h = 0 the kernel is the TW-LNS kernel on E; for h > 0 the hint is omitted for the operations in the
window, the ceiling is min{C_max(s_r) + ⌊3h⌉, max[C_max(s_r), C_max(s*) + 5]}, the objective is
(1−0.8h)·|J|·C_max + 0.05·Σ u_j C_j with u_j = exp(h·z_j), z_j ~ N(0,1), and the subproblem limit decreases linearly
from 8 s at h = 0 to 4 s at h = 1. Acceptance within a replica is Metropolis at the slot temperature; a proposal that
strictly improves the shared global makespan is always accepted and published. After every two proposals a replica
attempts an exchange of slots with an adjacent one (alternating parity) with probability
min{1, exp((1/T_i − 1/T_j)(E_i − E_j))}, reading the neighbour's last published energy under the shared lock. Every
60 s the parent process rescales the logarithmic gaps of the ladder by exp{0.5(a_p − 0.23)/0.23}, where a_p is the
exchange acceptance rate of pair p over the period (only when every pair has at least five attempts), clips them to
[0.02, 3] and renormalises so that the endpoints stay at 0.15 and 1.5; counters are reset at every check. Only the
replica in slot 0 adopts the global incumbent. Layouts run: `8 × 1` and `4 × 2` (i7), `8 × 1` and `16 × 1` (Ryzen).
The constants are in the `ptw` block of every manifest.

## Reproducing a campaign elsewhere

```bash
# TW-LNS, protocol budget, 10 seeds, 8 threads (about 12.6 h)
python experimentos/rcfjssp_lns.py --viz janela --walkers 4 --fios 2 --sementes 1 2 3 4 5 6 7 8 9 10 \
       --saida results/_local/heur_lns_janela --qualquer-maquina
# PT-W, same budget
python experimentos/rcfjssp_ptw.py --replicas 8 --fios 1 --sementes 1 2 3 4 5 6 7 8 9 10 \
       --saida results/_local/ptw_8x1 --comparar results/_local/heur_lns_janela --qualquer-maquina
# check and report
python rcfjssp_audit.py --results results/_local/ptw_8x1
python experimentos/rcfjssp_ptw.py --relatorio --saida results/_local/ptw_8x1 --comparar results/_local/heur_lns_janela
```

`results/_local/` is ignored by git. The number of CP-SAT threads per process times the number of processes should
not exceed the logical threads of the machine.
