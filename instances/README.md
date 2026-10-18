# `instances/`

## `upstream/RCFJSSP-main/` — the authors' benchmark, mirrored

The 90 instances of Kasapidis, Paraskevopoulos, Mourtos and Repoussis (2025), copied unchanged from
**https://github.com/gkasapidis/RCFJSSP** (their `Readme.md` is included). The authors published instances only; the
models and search procedures in this repository were written from the equations of the article.
`SHA256SUMS` lists the SHA-256 of every file under `upstream/` and `calibracao/`; check with `sha256sum -c SHA256SUMS`
from inside `instances/`.

| folder | article | instances | resources present | published results |
|---|---|---|---|---|
| `Experiment 1/` | §5.4.1, Table 7 | `lcb0`–`lcb9` (4 jobs, 5 machines, job shop) | limited-capacity machine buffers (`0 ≤ y_k ≤ 1`) | three columns: declared buffers, zero buffers (blocking), unlimited |
| `Experiment 2/{10,25,50,75}/` | §5.4.2, Table 8 | `t_0`–`t_9` × four values of β | tools (renewable, fixed number of copies) | β ∈ {10, 25, 50, 75, 100} %; β = 100 % is the constraint removed, not a folder |
| `Experiment 3/{25,50,100}/` | §5.4.3, Table 9 | `r_0`–`r_9` × three WIP capacities | non-renewable (material) resources and WIP buffers | "Small" = folder `50`, "Large" = folder `100`, "No buffers" = Eqs. 12–13 removed; folder `25` is not reported in the article |
| `Experiment 4/` | §5.4.4, Table 10 | `lcbrtu_0`–`lcbrtu_9` (98–156 operations) | all of the above, machine buffers `0 ≤ y_k ≤ 3` | CP Optimizer 20.1 at 1800 s (one run) and ALNS-CP (best of ten, with time) |

The column-to-folder mapping above is the one under which the four CP-SAT models and the CP Optimizer transcription
reproduce the 110 published optimal values (`rcfjssp_reference.py`, `results/final/validacao`,
`results/final/cpo_exp123`).

### File format, as read by `rcfjssp_core.py`

Header: jobs, machines, flexibility, |U| utilities, |T| tools, |W| WIP buffers, |R| non-renewable resources, two
generator seeds. Then the resource section (machine buffer capacities; one line per utility `id capacity`; per tool
`id copies`; per WIP buffer and per non-renewable resource its capacity/`max` field and the operations that produce or
consume it), then one line per job: number of operations and, per operation, the tool id (`-1` = none), the number
of eligible machines and, per eligible machine, **`2 + 2|U|` numbers**: machine id, processing time and `|U|` pairs
`(utility id, rate)`. The authors' README states `1 + |U|` numbers per machine; the parser checks the total token count
and recomputes the header flexibility from the modes read, and refuses any other layout. Tools declared with zero
copies (`t_7`: tool 5, `t_9`: tool 2) are used by no operation. The `max` field of a non-renewable resource is not a
constraint in Eq. 12 (stock starts at zero and must stay non-negative); imposing it changes no published value.
Observed ranges in Experiment 4 differ from the ones printed in §5.4.4 of the article (tool copies 6–39 and utility
capacities 80–100 in the files); the files are what every result here refers to.

## `calibracao/` — the ten calibration instances of the authors (§5.2)

Used by the calibration grid (`experimentos/calibra_lns.py`, folder `results/final/calibracao`) to choose θ and ρ₀
on instances outside the benchmark, as the authors did for ALNS-CP. Downloaded on 2 October 2026; the files are byte-identical to the sources
below (`experimentos/instancias_calibracao.py` checks the token accounting).

| file | family | source | bytes | SHA-256 (16) | URL |
|---|---|---|---:|---|---|
| `mk06.fjs`, `mk10.fjs` | FJSSP (BRData), Brandimarte (1993) | SchedulingLab/fjsp-instances | 2296, 3853 | `3630268312e16f17`, `9602d49ab54bb816` | https://github.com/SchedulingLab/fjsp-instances/tree/main/brandimarte |
| `16a.fjs`, `17a.fjs`, `18a.fjs` | FJSSP (DPData), Dauzère-Pérès & Paulli (1997) | SchedulingLab/fjsp-instances | 3430, 6620, 10546 | `6f1819a42d66d35f`, `3a8039fbaa421d9b`, `48944f76c2550b47` | https://github.com/SchedulingLab/fjsp-instances/tree/main/dauzere |
| `la18.txt`, `la25.txt`, `la30.txt`, `la35.txt`, `la38.txt` | JSSP, Lawrence (1984), solved as blocking job shop with swaps (`y_k = 0`) | tamy0612/JSPLIB | — | — | https://github.com/tamy0612/JSPLIB/tree/master/instances |

Formats: FJSSP files start with `jobs machines [mean flexibility]` and give, per job, the number of operations and
for each operation `k` followed by `k` pairs `machine(1-based) time`; JSSP files start with `jobs machines` and give,
per job, `machine(0-based) time` per operation.
