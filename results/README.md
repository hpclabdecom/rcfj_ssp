# `results/` — every reported run

Four trees: one per platform, plus the first i7 phase. **Results of different machines are never pooled**: each
folder belongs to one machine, recorded in every JSON (`maquina.cpu`) and in the manifest.

* `final/` — Intel Core i7-2600: validation of Tables 7–9, calibration grid, exact CP-SAT and CP Optimizer runs on
  Table 10, TW-LNS 4×2, native-reservoir baseline.
* `i7/` — Intel Core i7-2600: PT-W (two layouts), the replica-layout screen, the same-geometry and mechanism
  controls, the held-out and ×10 instances, the sensitivity arms, the instrumented run and the window-only
  calibration grid.
* `ryzen/` — AMD Ryzen 7 5700U: TW-LNS and PT-W at 8 and 16 threads, the screen, the exact and native-reservoir
  baselines at 8 and 16 threads, the controls, the held-out and ×10 instances, the sensitivity arms and the
  instrumented run.
* `xeon/` — Intel Xeon E5-2696 v4: TW-LNS and PT-W at 8, 16 and 32 threads, the 32-thread layout screen, the
  memory check, the controls, the held-out instances, the instrumented run, and the exact and native-reservoir
  baselines at 8 and 32 threads.
* `preflight_desktop-i72600.json`, `preflight_Joubert_vaio.json` — the hardware/software descriptions recorded by
  `experimentos/preflight_maquina.py` on the i7 and on the Ryzen.
* `TABLES.md` — the output of `python experimentos/analise_campanhas.py`, regenerated from the folders below.

Every schedule in these folders passed the solver-free checker (`rcfjssp_audit.py`, checks A–E). Re-run it on any
folder (`--instancias` points the checker at instance files outside the benchmark tree):

```bash
python rcfjssp_audit.py --results results/ryzen/ptw_8x1
python rcfjssp_audit.py --results results/xeon/heldout_ptw_8x1 --instancias instances/heldout
python rcfjssp_audit.py --results results/i7/escala10_ptw_8x1 --instancias instances/scaled10
```

## Folder catalogue

T_i = the per-instance ALNS-CP time of Table 10 (179.86–800.39 s). Held-out budgets are 4 s × operations
(`instances/heldout/budgets.json`); the ×10 instances use the unscaled T_i. "Seeds 1–10" means ten runs per instance.

### Main configurations and baselines

| folder | machine | what | runs | limit |
|---|---|---|---:|---|
| `final/validacao`, `final/cpo_exp123` | i7 | Tables 7–9 (110 cells) with the four CP-SAT models and with the literal CP Optimizer model | 110 + 110 | 300 s |
| `final/calibracao` | i7 | calibration grid of the development runner (four neighbourhoods): θ ∈ {1.5, 3, 5, 8} s × ρ₀ ∈ {0.15, 0.25, 0.35, 0.45}, ten calibration instances, 10 runs each, 4×2 (`runs/`, chosen pair in `escolha.json`) | 1600 | 60 s |
| `i7/calibracao_janela` | i7 | the same grid rerun with the time-window-only search | 1600 | 60 s |
| `final/heur_lns_janela`; `ryzen/heur_lns_janela_4x2`; `xeon/heur_lns_janela_4x2` | i7, Ryzen, Xeon | **TW-LNS** 4×2 (8 threads), seeds 1–10 | 100 each | T_i |
| `ryzen/heur_lns_janela_8x2`; `xeon/heur_lns_janela_8x2` | Ryzen, Xeon | TW-LNS 8×2 (16 threads) | 100 each | T_i |
| `xeon/heur_lns_janela_16x2` | Xeon | TW-LNS 16×2 (32 threads) | 100 | T_i |
| `i7/ptw_8x1`; `ryzen/ptw_8x1`; `xeon/ptw_8x1` | i7, Ryzen, Xeon | **PT-W** 8×1 (8 threads), seeds 1–10 (primary layout) | 100 each | T_i |
| `i7/ptw_4x2` | i7 | PT-W 4×2 (secondary layout) | 100 | T_i |
| `ryzen/ptw_16x1`; `xeon/ptw_16x1` | Ryzen, Xeon | PT-W 16×1 (16 threads) | 100 each | T_i |
| `xeon/ptw_16x2` | Xeon | PT-W 16×2 (32 threads) | 100 | T_i |
| `i7/screen_ptw_{8x1,4x2}`, `ryzen/screen_ptw_{8x1,4x2}` | i7, Ryzen | replica-layout screen, 8×1 and 4×2, `lcbrtu_3/5/8`, seeds 1–3 | 9 each | T_i |
| `xeon/screen_ptw_{16x2,32x1}`, `xeon/memcheck.json` | Xeon | 32-thread layout screen (same rule) and the memory check that gates the 32-thread arms | 9 each | T_i |
| `final/reservatorio_w8_TALNS`; `ryzen/reservatorio_w{8,16}_TALNS`; `xeon/reservatorio_w{8,32}_TALNS` | i7, Ryzen, Xeon | native-reservoir CP-SAT on the whole model, seeds 1–10 | 100 each | T_i |
| `final/relato_w8_1800`; `ryzen/relato_w{8,16}_1800`; `xeon/relato_w{8,32}_1800` | i7, Ryzen, Xeon | validated CP-SAT model, 1800 s, with solver log: seeds 1–10 (i7), one run elsewhere | 100; 10 each | 1800 s |
| `final/cpo_exp4`; `ryzen/cpo_exp4_w{8,16}` | i7, Ryzen | literal CP Optimizer 22.2 model, default search, one run | 10 each | 1800 s |

### Controls of PT-W (all 8×1, seeds 1–10, same budgets)

| folder (under `i7/`, `ryzen/`, `xeon/`) | what changes | machines |
|---|---|---|
| `lns_8x1` | TW-LNS with eight walkers of one thread (same process geometry as PT-W 8×1) | i7, Ryzen, Xeon |
| `ptw_8x1_PE_semtroca` | PT-W without slot exchanges | i7, Ryzen, Xeon |
| `ptw_8x1_U_nucleo_uniforme` | every slot uses the slot-0 repair kernel; temperatures, acceptance and exchanges unchanged | i7, Ryzen, Xeon |
| `ptw_8x1_F_escada_fixa` | the ladder is never adapted | i7, Ryzen |
| `ptw_8x1_C_cache_inicial` | the exchange energy cache starts at E(s*) instead of 0 | i7, Ryzen, Xeon |
| `ptw_8x1_PD_alpha0` | α = 0 (energy = makespan) | i7, Ryzen |
| `ptw_8x1_FPD_escada_fixa_alpha0` | F and PD combined: the ladder is never adapted and α = 0; exploratory, run after the pre-registered campaign on the five open instances (`lcbrtu_0`, `_3`, `_5`, `_7`, `_8`), seeds 1–10 | Ryzen |
| `ptw_8x1_D_instrumentado` | PT-W with per-move and per-exchange records (seeds 1–3) | i7, Ryzen, Xeon |

### Independent instances, scale and sensitivity

| folder | machines | what | runs |
|---|---|---|---:|
| `heldout_lns_4x2`, `heldout_ptw_8x1`, `heldout_ptw_4x2`, `heldout_mono_w8` | i7, Ryzen, Xeon | TW-LNS 4×2, PT-W 8×1, PT-W 4×2 and CP-SAT on the whole model (8 workers) on the fifteen instances of `instances/heldout`, seeds 1–10 | 150 each |
| `escala10_lns_4x2`, `escala10_ptw_8x1` | i7, Ryzen | TW-LNS 4×2 and PT-W 8×1 on `instances/scaled10` (processing times ×10, unscaled budget), seeds 1–5 | 15 each |
| `sens_T_x05`, `sens_T_x2`, `sens_delta1_deriva3`, `sens_delta6_deriva10`, `sens_subhot2`, `sens_subhot8` | i7, Ryzen | PT-W 8×1 with one thermal control changed (temperature endpoints halved / doubled; Δ_max and drift (1, 3) / (6, 10); hottest-slot limit 2 s / 8 s), `lcbrtu_3/5/8`, seeds 1–5 | 15 each |

On the Xeon the 8-thread folders were produced two at a time on disjoint sets of eight physical cores (affinity
masks 0xFFFF and 0xFFFF0000), including the TW-LNS 4×2 and PT-W 8×1 references of that machine; the 16- and
32-thread folders ran alone.

## What a result file contains

```json
{
 "instance": "lcbrtu_0", "experiment": "exp4", "config": "all", "seed": 1,
 "makespan": 341, "lower_bound": 303,
 "status": "FEASIBLE",
 "schedule": [{"op": 0, "job": 0, "index": 0, "machine": 2, "start": 0, "end": 17, "tool": 3}, ...],
 "auditoria": "ok",
 "wall_seconds": 624.6, "orcamento": 623.45, "their_alns": 345,
 "t_construcao": 31.4, "trajetoria": [[t, makespan, slot, replica], ...], "parametros": {...},
 "diagnostico_pt": {"taxa_troca": [...], "escada_final": [...], "ajustes": [...], "replicas": {...}},
 "protocol_hash": "277dc184d6b8b69c",
 "maquina": {"cpu": "Intel(R) Core(TM) i7-2600 CPU @ 3.40GHz", "fios": 8, "sistema": "Windows 11", "host": "...", "maquina_do_paper": true},
 "provenance": {...}
}
```

`lower_bound` and `status` appear where the solver gives them (exact, native-reservoir and whole-model held-out
runs); the heuristics record the construction time, the improvement trajectory (time, makespan and, for PT-W, the
slot and replica that found it) and the parameter set instead. PT-W files also carry `diagnostico_pt`: exchange
acceptance per pair, final ladder, ladder adjustments and per-replica counters (proposals, acceptances, accepted
deteriorations, subproblems without solution, end-to-end transitions between the extreme slots, stored as `trips`); the instrumented folders add `ctrl` with one record
per move and per exchange attempt. Held-out and ×10 files carry `conjunto` with the instance folder. Field names vary
slightly between scripts (`seconds`/`wall_seconds`, `hint`, `solver`); the schedule and makespan fields are the same
everywhere, which is what the checker reads. Exact runs keep the solver log next to the JSON (`*.log` or `logs/`).
`maquina_do_paper` only records whether the CPU is the i7-2600.
The CP Optimizer files carry `leitura` and `leitura_descricao`, the name and description of the reading of the source
formulation used by `experimentos/rcfjssp_cpo.py`; every archived run uses the literal reading (`fiel`), whose
transcription decisions are the ones documented in the root `README.md`.

`protocolo.manifest` lists the protocol fields (solver, threads, budget, constants, calibration hash, SHA-256 of the
source files that define the model and the search, CPU) and their hash; the root README lists, for each source file that defines the model and the search, the SHA-256 recorded in the manifests (the file as executed) and the SHA-256 of the published copy, which has comments and docstrings removed. The control scripts record the hash of the frozen scripts
they import as well as their own.
