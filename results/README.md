# `results/` — every reported run

Three trees, one per platform and phase. **i7-2600 and Ryzen 7 5700U results are never pooled**: each folder
belongs to one machine, recorded in every JSON (`maquina.cpu`) and in the manifest.

* `final/` — Intel Core i7-2600: validation of Tables 7–9, calibration grid, exact CP-SAT and CP Optimizer runs on
  Table 10, TW-LNS, native-reservoir baseline.
* `i7/` — Intel Core i7-2600: PT-W (two layouts) and the replica-layout screen.
* `ryzen/` — AMD Ryzen 7 5700U: TW-LNS at 8 and 16 threads, PT-W at 8 and 16 threads, the screen, and the exact and
  native-reservoir baselines at 8 and 16 threads.
* `preflight_desktop-i72600.json`, `preflight_Joubert_vaio.json` — the hardware/software descriptions recorded by
  `experimentos/preflight_maquina.py` on the two machines.
* `TABLES.md` — the output of `python experimentos/analise_campanhas.py`, regenerated from the folders below.

Every schedule in these folders passed the solver-free checker (`rcfjssp_audit.py`, checks A–E). Re-run it on any
folder:

```bash
python rcfjssp_audit.py --results results/ryzen/ptw_8x1
```

## Folder catalogue

| folder | machine | what | runs (JSON) | per-run limit | protocol (manifest hash or model version) |
|---|---|---|---|---|---|
| `final/validacao` | i7 | Tables 7–9 with the four CP-SAT models | 110 | 300 s | `2026-08-14-eq9-literal` |
| `final/cpo_exp123` | i7 | literal model in CP Optimizer 22.2, Tables 7–9 | 110 | 300 s | `2026-09-30-cpo-boxI-literal` |
| `final/calibracao` | i7 | calibration grid, 10 instances × 16 (θ, ρ₀) pairs × 10 runs (`runs/`), chosen pair in `escolha.json` | 1600 | 60 s | `6e0f9f9cd4121379` |
| `final/relato_w8_1800` | i7 | validated CP-SAT model, 8 threads, seeds 1–10, no hint, full solver log | 100 | 1800 s | `a555ffd986c08f2f` |
| `final/cpo_exp4` | i7 | literal model in CP Optimizer 22.2, Table 10, default search, one run | 10 | 1800 s | `2026-09-30-cpo-boxI-literal` |
| `final/heur_lns_janela` | i7 | **TW-LNS** 4 × 2, seeds 1–10 | 100 | T_i | `5997c5e61166605d` |
| `final/reservatorio_w8_TALNS` | i7 | native-reservoir CP-SAT, whole model, 8 threads, seeds 1–10 | 100 | T_i | manifest in folder |
| `i7/ptw_8x1` | i7 | **PT-W** 8 replicas × 1 thread, seeds 1–10 (primary layout) | 100 | T_i | `277dc184d6b8b69c` |
| `i7/ptw_4x2` | i7 | PT-W 4 × 2, seeds 1–10 (secondary layout) | 100 | T_i | manifest in folder |
| `i7/screen_ptw_8x1`, `i7/screen_ptw_4x2` | i7 | replica-layout screen, `lcbrtu_3`, `lcbrtu_5`, `lcbrtu_8`, seeds 1–3 | 9 each | T_i | manifest in folder |
| `ryzen/heur_lns_janela_4x2` | Ryzen | TW-LNS 4 × 2 (8 threads), seeds 1–10 | 100 | T_i | manifest in folder |
| `ryzen/heur_lns_janela_8x2` | Ryzen | TW-LNS 8 × 2 (16 threads), seeds 1–10 | 100 | T_i | manifest in folder |
| `ryzen/ptw_8x1`, `ryzen/ptw_16x1` | Ryzen | PT-W at 8 and 16 threads, seeds 1–10 | 100 each | T_i | manifest in folder |
| `ryzen/screen_ptw_8x1`, `ryzen/screen_ptw_4x2` | Ryzen | replica-layout screen, three instances, seeds 1–3 | 9 each | T_i | manifest in folder |
| `ryzen/relato_w8_1800`, `ryzen/relato_w16_1800` | Ryzen | validated CP-SAT model, 8 and 16 threads, seed 1 | 10 each | 1800 s | manifest in folder |
| `ryzen/cpo_exp4_w8`, `ryzen/cpo_exp4_w16` | Ryzen | literal model in CP Optimizer 22.2, 8 and 16 workers | 10 each | 1800 s | `2026-09-30-cpo-boxI-literal` |
| `ryzen/reservatorio_w8_TALNS`, `ryzen/reservatorio_w16_TALNS` | Ryzen | native-reservoir CP-SAT, whole model, 8 and 16 threads, seeds 1–10 | 100 each | T_i | manifest in folder |

T_i = the per-instance ALNS-CP time of Table 10 (179.86–800.39 s). The seven main configurations (TW-LNS and PT-W
folders with ten seeds) hold 700 schedules; the nine contextual baselines (exact and native-reservoir folders) hold
another 450.

## What a result file contains

```json
{
 "instance": "lcbrtu_0", "experiment": "exp4", "config": "all", "seed": 1,
 "makespan": 341, "lower_bound": 303,
 "status": "FEASIBLE",
 "schedule": [{"op": 0, "job": 0, "index": 0, "machine": 2, "start": 0, "end": 17, "tool": 3}, ...],
 "auditoria": "ok",
 "wall_seconds": 624.6, "orcamento": 623.45, "their_alns": 345,
 "t_construcao": 31.4, "trajetoria": [[t, makespan], ...], "parametros": {...},
 "protocol_hash": "277dc184d6b8b69c",
 "maquina": {"cpu": "Intel(R) Core(TM) i7-2600 CPU @ 3.40GHz", "fios": 8, "sistema": "Windows 11", "host": "...", "maquina_do_paper": true},
 "provenance": {...}
}
```

`lower_bound` and `status` appear where the solver gives them (exact and native-reservoir runs); the heuristics
record the construction time, the improvement trajectory and the parameter set instead. Field names vary slightly
between scripts (`seconds`/`wall_seconds`, `hint`, `solver`); the schedule and makespan fields are the same
everywhere, which is what the checker reads. Exact runs keep the solver log next to the JSON (`*.log` or `logs/`).
The Ryzen JSONs carry `maquina_do_paper: false`, which only records that the CPU is not the i7-2600.

`protocolo.manifest` lists the protocol fields (solver, threads, budget, constants, calibration hash, SHA-256 of the
source files that define the model and the search, CPU) and their hash; the root README lists the source files kept
byte-identical so that these hashes can be recomputed.
