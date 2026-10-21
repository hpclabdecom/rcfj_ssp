# `instances/heldout/` — independent combined-resource instances

Fifteen instances generated on 21 October 2026 by `experimentos/gera_instancias.py` (generator seed
20261021; generator SHA-256 `7c57feceae859d33`), committed with their hashes (`SHA256SUMS`) and
budgets (`budgets.json`) **before any method was run on them**. They were not used to design, calibrate or select
anything: TW-LNS, PT-W and their parameters are the ones frozen for the benchmark instances.

| instance | jobs | machines | operations | flexibility | utilities | tools | budget (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `rcfj_h_0` | 14 | 5 | 139 | 3.06 | 1 | 4 | 556 |
| `rcfj_h_1` | 15 | 6 | 148 | 2.90 | 2 | 1 | 592 |
| `rcfj_h_2` | 15 | 8 | 147 | 3.05 | 2 | 5 | 588 |
| `rcfj_h_3` | 11 | 9 | 107 | 3.05 | 1 | 5 | 428 |
| `rcfj_h_4` | 13 | 8 | 123 | 2.97 | 1 | 1 | 492 |
| `rcfj_h_5` | 13 | 5 | 129 | 2.93 | 1 | 5 | 516 |
| `rcfj_h_6` | 11 | 8 | 111 | 3.02 | 2 | 5 | 444 |
| `rcfj_h_7` | 15 | 7 | 155 | 3.00 | 1 | 1 | 620 |
| `rcfj_h_8` | 11 | 9 | 115 | 3.10 | 1 | 1 | 460 |
| `rcfj_h_9` | 12 | 9 | 126 | 2.95 | 2 | 3 | 504 |
| `rcfj_hl_0` | 24 | 8 | 232 | 3.09 | 1 | 5 | 928 |
| `rcfj_hl_1` | 21 | 9 | 208 | 2.93 | 3 | 2 | 832 |
| `rcfj_hl_2` | 20 | 9 | 203 | 3.00 | 3 | 2 | 812 |
| `rcfj_hl_3` | 21 | 11 | 207 | 3.01 | 3 | 4 | 828 |
| `rcfj_hl_4` | 20 | 10 | 204 | 3.00 | 3 | 2 | 816 |

## Generation rules

The generator follows the parameter ranges of §5.4.4 of Kasapidis et al. (2025) where they are stated and the
structure observed in the published files `lcbrtu_0`–`lcbrtu_9` where they are not (the published ranges for tool
copies and utility capacities differ from the files; the files were followed).

* Size: 10–15 jobs and 5–10 machines (`rcfj_h_*`); 20–27 jobs and 8–12 machines, resampled until the instance has
  200–300 operations (`rcfj_hl_*`). 8–12 operations per job; every operation has 2–4 eligible machines (flexibility
  ≈ 3) with processing times in 5–20.
* Machine buffers: capacity 0–3 per machine.
* Utilities: 1–3, capacity 80, 90 or 100; every mode of every operation has a rate in 1–5 for each utility.
* Tools: 1–5 types; every operation requires exactly one; copies = ⌈0.25 × number of operations that use the
  tool⌉, as in the published files.
* Materials and WIP: 8 non-renewable resources in two WIP buffers, as in all published instances. 1–4 resources are
  stage-1 (buffer 1), the rest stage-2 (buffer 2). Jobs are split in three tiers of about equal size: tier A jobs
  produce every stage-1 resource (quantities 50–250, multiples of 10); tier B jobs consume stage-1 resources and
  produce every stage-2 resource; tier C jobs consume stage-2 resources. Consumption of each resource equals its
  total production (initial stock 0; the file field `max` equals the total flow, as in the published files). The
  WIP capacity of each buffer is a fraction 0.25–0.40 of the total flow through it, rounded to tens, and never below
  the largest single-job production into that buffer.
* Budget: `T = 4 s × number of operations` (the mean of the Table 10 ALNS-CP times per operation over the ten
  benchmark instances is 3.7 s; rounded up).
* Validation: the parser (`rcfjssp_core.py`) accepts each file with exact token accounting; the complete
  native-reservoir CP-SAT model finds a first feasible schedule of every instance within 60 s on two threads
  (`GENERATION.json`, `verification_seconds`); no instance had to be resampled.

Check the files with `sha256sum -c SHA256SUMS` inside this folder. Results on these instances are produced by
`experimentos/rcfjssp_heldout.py` and checked by `python rcfjssp_audit.py --results <folder> --instancias instances/heldout`.
