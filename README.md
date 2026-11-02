# RCFJ-SSP — TW-LNS, PT-W and audited results on the Kasapidis et al. (2025) benchmark

Replication package of

> Lima, J.C., Vieira, M.P.R., Alem, B.C., Soares, L.C.R., Almeida, A.L.B., Carvalho, M.A.M.
> *Strengthening the baseline before a new optimization method: a large-language-model-assisted
> algorithm-engineering case study in multi-resource flexible job shops.* 2026.

The problem is the **resource-constrained flexible job shop scheduling problem (RCFJ-SSP)** of Kasapidis,
Paraskevopoulos, Mourtos and Repoussis, *European Journal of Operational Research* 320(3), 479–495, 2025
([doi:10.1016/j.ejor.2024.08.010](https://doi.org/10.1016/j.ejor.2024.08.010)), whose benchmark instances are
published at **https://github.com/gkasapidis/RCFJSSP** (instances only; their code is not public).

What is here:

* an open transcription of their constraint programming model (Eqs. 1–14) in **OR-Tools CP-SAT** and, in the
  literal interval-variable form, in **IBM CP Optimizer**, validated against all 110 published optimal values of their
  Tables 7–9;
* **TW-LNS** (`experimentos/rcfjssp_lns.py`; folders `heur_lns_janela*`): the time-window large-neighbourhood search
  that keeps the authors' time-window operator (§4.1.1) and CP reconstruction, with a native reservoir encoding;
* **PT-W** (`experimentos/rcfjssp_ptw.py`; folders `ptw_*`): parallel tempering with time-window repair, the
  parallel-tempering architecture of the group over the same neighbourhood;
* the calibration grids, the replica-layout screens, the exact-solver and monolithic CP-SAT baselines;
* the pre-registered controls of PT-W (same geometry, no exchanges, uniform kernel, fixed ladder, initialised cache,
  α = 0, instrumented run), fifteen independent instances with their generator, ×10-scaled instances and the
  sensitivity arms of the thermal controls;
* the **solver-free checker** (`rcfjssp_audit.py`, checks A–E) that re-verifies every reported schedule;
* **every result file** of the reported campaigns on three platforms (Intel Core i7-2600, AMD Ryzen 7 5700U and
  Intel Xeon E5-2696 v4): JSON with the full schedule, protocol manifests with hashes, solver logs, hardware
  descriptions;
* the generated tables (`results/TABLES.md`), the benchmark instances with their SHA-256 (`instances/SHA256SUMS`),
  the ten calibration instances, the authors' article (CC BY 4.0) and the related-work list.

The protocol, the hardware and the numbers are described in **[EXPERIMENTS.md](EXPERIMENTS.md)**.

## Repository map

| path | what it holds | details |
|---|---|---|
| `rcfjssp_core.py` | `.fjs` parser with exact token accounting; `Instance`/`Operation` data classes | [core modules](#core-modules) |
| `rcfjssp_reference.py` | the published Tables 7–10 (values, times, lower bounds) and the per-experiment configurations | |
| `rcfjssp_buffers.py`, `rcfjssp_cpsat.py`, `rcfjssp_wip.py`, `rcfjssp_full.py` | CP-SAT models for Experiments 1, 2, 3 and 4 | |
| `rcfjssp_campaign.py` | runs the four models over the whole benchmark and reports agreement with the published tables | |
| `rcfjssp_audit.py` | solver-free checker (A–E) over any results folder | |
| `preflight.py` | end-to-end check of interpreter, solver, instances and models | |
| `experimentos/` | campaign scripts, TW-LNS, PT-W, controls, calibration, analysis, Windows `.bat` entry points; `PREREGISTRATION.md` | [experimentos/README.md](experimentos/README.md) |
| `instances/` | the authors' instances (mirror, with `SHA256SUMS`) and the ten calibration instances | [instances/README.md](instances/README.md) |
| `results/` | every reported run, plus `TABLES.md` generated from them | [results/README.md](results/README.md) |
| `papers/` | the authors' article and the related work | [papers/README.md](papers/README.md) |
| `instances/heldout/`, `instances/scaled10/` | fifteen independent combined-resource instances (hashes and budgets committed before any run) and three ×10-scaled benchmark instances | [instances/heldout/README.md](instances/heldout/README.md), [experimentos/PREREGISTRATION.md](experimentos/PREREGISTRATION.md) |
| `paper/ref/` | plain-text extraction of the authors' article, read by the campaign scripts to cross-check Table 10 | [paper/ref/README.md](paper/ref/README.md) |

Method names versus names in the code and in the result folders:

| name | in the code / results |
|---|---|
| TW-LNS | `rcfjssp_lns.py --viz janela`; folders `heur_lns_janela` (i7), `heur_lns_janela_4x2`, `_8x2`, `_16x2`; code name `X8b` |
| TW-LNS 8×1 (same geometry as PT-W 8×1) | `rcfjssp_lns.py --viz janela --walkers 8 --fios 1`; folder `lns_8x1` |
| PT-W | `rcfjssp_ptw.py`; folders `ptw_8x1`, `ptw_4x2`, `ptw_16x1`, `ptw_16x2`; code name `PTW` / `X12` |
| PT-W controls PE, U, F, C, PD, D | `rcfjssp_ptw.py --sem-troca` / `--alpha-e 0` and `rcfjssp_ptw_controls.py --braco U/F/C/D`; folders `ptw_8x1_PE_semtroca`, `ptw_8x1_U_nucleo_uniforme`, `ptw_8x1_F_escada_fixa`, `ptw_8x1_C_cache_inicial`, `ptw_8x1_PD_alpha0`, `ptw_8x1_D_instrumentado` |
| independent instances, ×10 instances, sensitivity | `rcfjssp_heldout.py`, `rcfjssp_ptw_controls.py --braco S`; folders `heldout_*`, `escala10_*`, `sens_*` |
| replica-layout screen | `screen_ptw_8x1`, `screen_ptw_4x2` (i7, Ryzen); `screen_ptw_16x2`, `screen_ptw_32x1` (Xeon) |
| calibration grid (θ, ρ₀) | `calibra_lns.py`; folder `final/calibracao` (development runner) and `i7/calibracao_janela` (window-only rerun); code name `X9` |
| native-reservoir CP-SAT at T_i | `x10_reservatorio.py`; folders `reservatorio_w8_TALNS`, `_w16_TALNS`, `_w32_TALNS`; code name `X10` |
| validated CP-SAT model, 1800 s | `rcfjssp_final.py --braco relato`; folders `relato_w8_1800`, `_w16_1800`, `_w32_1800`; code name `X1` |
| CP Optimizer 22.2, literal model, 1800 s | `rcfjssp_cpo.py --exp 4`; folders `cpo_exp4`, `cpo_exp4_w8`, `cpo_exp4_w16`; code name `X6b` |
| validation of Tables 7–9 | `rcfjssp_valida_i7.py` (CP-SAT, folder `validacao`, `X4`) and `rcfjssp_cpo.py --exp 1/2/3` (folder `cpo_exp123`, `X6a`) |

## Quick start

Requirements: Python ≥ 3.11 (the campaigns ran on 3.13.13 and 3.14.7 under Windows 11; Linux works for everything
that does not need CP Optimizer) and `ortools==9.15.6755`, the exact release used in every campaign.

```bash
git clone https://github.com/hpclabdecom/rcfj_ssp.git
cd rcfj_ssp
pip install -r requirements.txt
python preflight.py                      # interpreter, solver, instances, one small instance end to end
```

Verify the reported schedules without running any solver (seconds per folder):

```bash
python rcfjssp_audit.py --results results/final/heur_lns_janela     # TW-LNS, i7, 100 runs
python rcfjssp_audit.py --results results/i7/ptw_8x1               # PT-W, i7, 100 runs
python rcfjssp_audit.py --results results/ryzen/ptw_8x1
python rcfjssp_audit.py --results results/xeon/heldout_ptw_8x1 --instancias instances/heldout
```

Regenerate `results/TABLES.md` from the result files (no solver; the exact tests take a few minutes):

```bash
python experimentos/analise_campanhas.py > results/TABLES.md
python rcfjssp_campaign.py --report                                 # agreement of results/final/validacao with Tables 7-9
```

Reproduce the 110 published optimal values of Tables 7–9 with CP-SAT (about 15 minutes with 8 threads; the 300-s
limit per cell was set for 8 threads):

```bash
python experimentos/rcfjssp_valida_i7.py --workers 8 --qualquer-maquina --saida results/_local/validacao
```

Run TW-LNS and PT-W on one instance at a tenth of the budget (a few minutes each):

```bash
python experimentos/rcfjssp_lns.py --viz janela --walkers 4 --fios 2 --instancias lcbrtu_3 --sementes 1 --escala 0.1 --saida results/_local/lns --qualquer-maquina
python experimentos/rcfjssp_ptw.py --replicas 8 --fios 1 --instancias lcbrtu_3 --sementes 1 --escala 0.1 --saida results/_local/ptw --comparar results/_local/lns --qualquer-maquina
python rcfjssp_audit.py --results results/_local/ptw
```

Full campaigns are launched by the `.bat` files in `experimentos/` (Windows) or by the equivalent Python commands
listed in [experimentos/README.md](experimentos/README.md). Budgets are the per-instance ALNS-CP times of the
authors' Table 10 (179.86–800.39 s per run), so a full 10-instance × 10-seed campaign takes about 12.6 hours; the
controls, held-out and scalability arms of one machine (`experimentos/CAMPANHA_CONTROLES.bat`) take 200–275 hours.

### The machine guard

The campaign scripts record the CPU in every result and refuse to run on a CPU other than the i7-2600 unless
`--qualquer-maquina` ("any machine") is passed (`experimentos/maquina.py`); the result is then written with
`maquina_do_paper: false`, which only records that the CPU is not the i7-2600. The `.bat` files detect any other CPU
and pass the flag automatically; all Ryzen and Xeon folders carry it.

### CP Optimizer (optional)

Only `experimentos/rcfjssp_cpo.py` (folders `cpo_exp123`, `cpo_exp4`, `cpo_exp4_w8`, `cpo_exp4_w16`) needs IBM
CP Optimizer. It calls the `cpoptimizer` executable of CPLEX Studio through `docplex`; Experiment 4 instances exceed
the size limit of the Community edition, so the full (academic) edition is required for those. Pass `--cpo-exe <path>`
or set the environment variable `CPO_EXE`. Everything else runs on CP-SAT alone.

### Language of the code

Identifiers, command-line flags and console messages are in Portuguese. The flags you will meet:

| flag | meaning | flag | meaning |
|---|---|---|---|
| `--sementes` | seeds | `--saida` | output folder |
| `--instancias` | instance stems | `--comparar` | control folder to compare against |
| `--fios` | CP-SAT threads per walker/replica | `--relatorio` | print the report of a finished folder |
| `--walkers` / `--replicas` | parallel walkers (TW-LNS) / replicas (PT-W) | `--escala` | budget scale (1.0 = protocol) |
| `--limite` / `--limit` | wall-clock limit in seconds | `--braco` | arm of a campaign (`relato` = from scratch) |
| `--viz` | neighbourhoods (`janela` = time window) | `--calibracao` | path to the calibration choice file |
| `--qualquer-maquina` | disable the machine guard | `--workers` | CP-SAT threads of a monolithic run |

## Core modules

* **`rcfjssp_core.py`** parses the authors' `.fjs` format. Per mode the files carry `2 + 2|U|` numbers (machine id,
  processing time, then `(utility id, rate)` pairs); the parser accounts for every token and recomputes the header
  flexibility from the modes read, so a wrong layout is rejected rather than silently misread. Tool id `-1` (and
  utility id `0`) mean "none"; tools declared with zero copies have no users in any instance.
* **`rcfjssp_reference.py`** holds the published values of Tables 7–10 and the mapping from each table column to a
  folder and a configuration (which resource constraints are active). Every comparison in the repository goes through
  this file.
* **`rcfjssp_buffers.py`** (Experiment 1: limited-capacity machine buffers), **`rcfjssp_cpsat.py`** (Experiment 2:
  tools as renewable resources with a fixed number of copies; `β = 100 %` is the constraint removed),
  **`rcfjssp_wip.py`** (Experiment 3: non-renewable resources with zero initial stock, Eq. 12, and WIP buffers,
  Eq. 13; "No buffers" is the model without Eqs. 12–13) and **`rcfjssp_full.py`** (Experiment 4: all resources). All
  four share the `Alternative`/`NoOverlap`/`Cumulative` encoding of CP-SAT; Eqs. 12–13 are encoded with ordering
  booleans in `rcfjssp_full.py` and natively (`AddReservoirConstraint`) in `experimentos/modelo_reservatorio.py`, the
  model used by TW-LNS, PT-W and the native-reservoir baseline.
* **`rcfjssp_campaign.py`** runs the four models over the 90 instances with the configurations of the tables and
  reports agreement with the published values; `experimentos/rcfjssp_valida_i7.py` is the protocol wrapper used for
  `results/final/validacao`.
* **`rcfjssp_audit.py`** reads a results folder and, for every JSON with a schedule, re-checks without any solver:
  (A) the parsed instance is consistent with its header; (B) every operation appears once, on an eligible machine,
  with the duration of that mode, a non-negative start and the stored job, index and tool identifiers; (C) job
  precedence and the release relations between consecutive operations; (D) every active resource constraint of that
  configuration (machine processing and blocking, machine buffers, tools, utilities, materials, WIP) at every event
  time; (E) the makespan recomputed from the schedule equals the reported one. It imports neither OR-Tools nor IBM
  software.

## Provenance of the code and of the results

Every result folder carries a `protocolo.manifest` whose `hash` is the SHA-256 of the fields that define the number
(solver, budget, parameters, instances, and the SHA-256 of the source files that define the model and the search).
Each JSON records that hash, the CPU, and the solver version where the script wrote it. For the hashes to remain
checkable, the following files are kept **byte-for-byte identical** to the versions that ran the campaigns, comments
included; their SHA-256 (first 16 hex digits) is the one found in the manifests:

| file | SHA-256 (16) | recorded in |
|---|---|---|
| `rcfjssp_core.py` | `3b1a84cdb95da205` | native-reservoir baseline manifests |
| `rcfjssp_full.py` | `cf271870e97653d1` | TW-LNS, native-reservoir baseline |
| `experimentos/modelo_reservatorio.py` | `ecbf9c1de11ebee6` | TW-LNS, PT-W, native-reservoir baseline |
| `experimentos/rcfjssp_lns.py` | `dc4dda1f6bae91c3` | TW-LNS, PT-W, calibration |
| `experimentos/rcfjssp_ptw.py` | `e1e033dbb8f92554` | PT-W |
| `experimentos/rcfjssp_final.py` | `d6e0c3d23082936f` | exact CP-SAT runs (provenance field) |
| `experimentos/rcfjssp_cpo.py` | `c6d01349a95ff7bd` | CP Optimizer runs (provenance field) |
| `experimentos/x10_reservatorio.py` | `c67276b639a24cc5` | native-reservoir baseline (provenance field) |
| `experimentos/instancias_calibracao.py` | `d3dbc24fabdbd2f0` | calibration |

All other source files had their comments and docstrings removed for publication; their behaviour is documented in
the README of each folder. `.gitattributes` sets `* -text` so that no line-ending conversion alters these files on
checkout. `instances/SHA256SUMS` lists the SHA-256 of every instance file (`sha256sum -c SHA256SUMS` inside
`instances/`).

## Citing

Cite the benchmark paper of Kasapidis et al. (2025) for the problem and the instances, and the article above for
TW-LNS, PT-W and the results in this repository.

## License

* Code (`*.py`, `*.bat`): MIT License (see `LICENSE`).
* Result files, documentation and the tables derived from them: Creative Commons Attribution 4.0 (CC BY 4.0).
* `instances/upstream/`: the benchmark instances of Kasapidis et al., redistributed unchanged from
  https://github.com/gkasapidis/RCFJSSP with attribution; `instances/calibracao/`: public instances of Brandimarte,
  Dauzère-Pérès & Paulli and Lawrence, see `instances/README.md`.
* `papers/` and `paper/ref/`: the authors' article is distributed under its own CC BY 4.0 licence.
