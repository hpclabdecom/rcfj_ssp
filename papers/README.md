# `papers/`

## The benchmark paper

**Kasapidis, G.A., Paraskevopoulos, D.C., Mourtos, I., Repoussis, P.P. (2025).** *A unified solution framework for
flexible job shop scheduling problems with multiple resource constraints.* European Journal of Operational Research
320(3), 479–495. https://doi.org/10.1016/j.ejor.2024.08.010 — file `kasapidis2025_ejor_unified_framework_rcfjssp.pdf`
(open access, CC BY 4.0, © 2024 The Authors; redistributed here under that licence).
Instances: https://github.com/gkasapidis/RCFJSSP.

What the article contains, and where this repository connects to it:

* **Problem (§3).** A flexible job shop in which each operation chooses one of several machines (a *mode*), with five
  kinds of resources handled in one model: limited-capacity machine buffers (an operation that finishes may wait in
  the buffer of its machine or block it), tools (renewable, a fixed number of copies, one per operation), utilities
  (renewable, a rate per mode against a capacity), non-renewable materials produced and consumed by operations (stock
  starts at zero and must never go negative, Eq. 12) and work-in-progress buffers that cap the stock of a group of
  materials (Eq. 13). Objective: makespan.
* **CP model (§4, Box I, Eqs. 1–14).** Interval variables for operations and modes, `Alternative`, `NoOverlap`,
  `Pulse` cumulative functions for tools and utilities, `AlwaysIn` on the buffer occupation during processing,
  `StepAtStart`/`StepAtEnd` for materials. `rcfjssp_buffers.py`, `rcfjssp_cpsat.py`, `rcfjssp_wip.py` and
  `rcfjssp_full.py` are CP-SAT transcriptions of this model for Experiments 1–4; `experimentos/rcfjssp_cpo.py` is a
  primitive-by-primitive transcription for CP Optimizer.
* **ALNS-CP (§4.1, Algorithm 1).** A CP-based adaptive large neighbourhood search: seven constraint-extraction
  operators (time window, block, machine removal, three machine-assignment operators and an operation-removal
  operator), roulette selection, reconstruction by CP with the extracted constraints, an elite set and a trajectory
  list, adaptive window size ρ (Eq. 38) and subproblem time θ. TW-LNS (`experimentos/rcfjssp_lns.py`) keeps the time
  window operator of §4.1.1 (Eqs. 15–19) and the "fix outside, re-optimise inside with CP" principle, and nothing
  else of ALNS-CP; PT-W (`experimentos/rcfjssp_ptw.py`) is parallel tempering with time-window repair over that neighbourhood.
* **Experiments (§5).** CP Optimizer 20.1.0 (C++), Intel Xeon E5-2650, 32 GB. Tables 7–9: 110 small instances solved
  to optimality by CP (values and times); Table 10: ten large instances with CP at 1800 s (one run) and ALNS-CP
  (best of ten runs, with the time of the best run). ALNS-CP was calibrated on ten FJSSP/JSSP instances of the
  literature (`instances/calibracao/`). The protocol of every campaign in this repository is defined relative to
  those tables (`rcfjssp_reference.py`, `EXPERIMENTS.md`).

## Related work used in the study

Parallel tempering:

* Hukushima, K., Nemoto, K. (1996). Exchange Monte Carlo method and application to spin glass simulations. J. Phys.
  Soc. Jpn. 65, 1604–1608. https://doi.org/10.1143/JPSJ.65.1604
* Earl, D.J., Deem, M.W. (2005). Parallel tempering: theory, applications, and new perspectives. Phys. Chem. Chem.
  Phys. 7, 3910–3916. https://doi.org/10.1039/b509983h
* Almeida, A.L.B., de Castro Lima, J., Carvalho, M.A.M. (2025). Revisiting the parallel tempering algorithm:
  high-performance computing and applications in operations research. Computers & Operations Research 178, 107000.
  https://doi.org/10.1016/j.cor.2025.107000
* Almeida, A.L.B., Soares, L.C.R., Carvalho, M.A.M. (2026). Parallel tempering for the job sequencing and tool
  switching problem with non-identical parallel machines. Unpublished manuscript.

Large neighbourhood search and CP:

* Shaw, P. (1998). Using constraint programming and local search methods to solve vehicle routing problems. CP98,
  LNCS 1520, 417–431. https://doi.org/10.1007/3-540-49481-2_30
* Ropke, S., Pisinger, D. (2006). An adaptive large neighborhood search heuristic for the pickup and delivery problem
  with time windows. Transportation Science 40, 455–472. https://doi.org/10.1287/trsc.1050.0135
* Perron, L., Didier, F., Gay, S. (2023). The CP-SAT-LP solver. CP 2023, LIPIcs 280, 3:1–3:2.
  https://doi.org/10.4230/LIPIcs.CP.2023.3
* Google OR-Tools, CP-SAT 9.15. https://github.com/google/or-tools (`ortools==9.15.6755` on PyPI)
* Lan, L., Berkhout, J. (2025). PyJobShop: solving scheduling problems with constraint programming in Python.
  arXiv:2502.13483. https://arxiv.org/abs/2502.13483

Flexible job shops with multiple resources:

* Dauzère-Pérès, S., Ding, J., Shen, L., Tamssaouet, K. (2024). The flexible job shop scheduling problem: a review.
  European Journal of Operational Research 314, 409–432. https://doi.org/10.1016/j.ejor.2023.05.017
* Cheng, W., Zhang, C., Meng, L., Ren, Y., Ullah, S. (2025). Collaborative multi-CP model and meta-feedback
  learning-assisted matheuristic for the FJSSP with sequence-dependent setup times. Swarm and Evolutionary
  Computation 99, 102173. https://doi.org/10.1016/j.swevo.2025.102173
* Xiong, F., Liu, H. (2026). Logic-based Benders decomposition methods for the distributed flexible job shop
  scheduling problem. European Journal of Operational Research 329, 778–797.
  https://doi.org/10.1016/j.ejor.2025.08.039
* Zhou, Y., Du, S., Lv, J., Shen, X., Matta, A., Wang, S. (2025). Flexible pallet automation system scheduling with
  limited fixture-pallets and material-pallets. Journal of Manufacturing Systems 83, 357–371.
  https://doi.org/10.1016/j.jmsy.2025.09.015
* Yuraszeck, F., Montero, E., Rojel, M., Cuneo, N. (2026). The multiresource flexible job-shop scheduling problem
  with early resource release. Mathematics 14, 338. https://doi.org/10.3390/math14020338

LLMs in optimisation and scheduling:

* Fan, Z., Ghaddar, B., Wang, X., Xing, L., Zhang, Y., Zhou, Z. (2026). Artificial intelligence for optimization:
  unleashing the potential of parameter generation, model formulation, and solution methods. European Journal of
  Operational Research 332(1), 1–30. https://doi.org/10.1016/j.ejor.2025.08.029
* Bengio, Y., Lodi, A., Prouvost, A. (2021). Machine learning for combinatorial optimization: a methodological tour
  d'horizon. European Journal of Operational Research 290, 405–421. https://doi.org/10.1016/j.ejor.2020.07.063
* Ahmaditeshnizi, A., Gao, W., Udell, M. (2024). OptiMUS: scalable optimization modeling with (MI)LP solvers and
  large language models. ICML 2024, PMLR 235, 577–596. https://proceedings.mlr.press/v235/ahmaditeshnizi24a.html
* Romera-Paredes, B. et al. (2024). Mathematical discoveries from program search with large language models. Nature
  625, 468–475. https://doi.org/10.1038/s41586-023-06924-6
* Liu, F. et al. (2024). Evolution of heuristics: towards efficient automatic algorithm design using large language
  model. ICML 2024, PMLR 235, 32201–32223. https://proceedings.mlr.press/v235/liu24bs.html
* Ye, H. et al. (2024). ReEvo: large language models as hyper-heuristics with reflective evolution. NeurIPS 37.
  https://doi.org/10.52202/079017-1381
* Abgaryan, H., Harutyunyan, A., Cazenave, T. (2024). LLMs can schedule. arXiv:2408.06993.
  https://arxiv.org/abs/2408.06993
* Abgaryan, H., Cazenave, T., Harutyunyan, A. (2025). Starjob: dataset for LLM-driven job shop scheduling.
  arXiv:2503.01877. https://arxiv.org/abs/2503.01877
* Wang, Z. et al. (2025). MASC: large language model-based multi-agent scheduling chain for flexible job shop
  scheduling problem. Advanced Engineering Informatics 67, 103527. https://doi.org/10.1016/j.aei.2025.103527
* Liao, R., Qiu, J., Chen, X., Li, X. (2025). LLM4EO: large language model for evolutionary optimization in flexible
  job shop scheduling. arXiv:2511.16485. https://arxiv.org/abs/2511.16485
* May, M.C., Salama, S., Pflüger, J., Kaihara, T. (2026). LLM actor–critic based dispatching rule generation for
  dynamic job shop scheduling. CIRP Annals 75, 601–605. https://doi.org/10.1016/j.cirp.2026.04.007

Algorithm engineering:

* Sanders, P. (2009). Algorithm engineering: an attempt at a definition. In: Albers, S., Alt, H., Näher, S. (Eds.),
  Efficient Algorithms, LNCS 5760, 321–340. Springer. https://doi.org/10.1007/978-3-642-03456-5_22

Statistics:

* Mann, H.B., Whitney, D.R. (1947). On a test of whether one of two random variables is stochastically larger than
  the other. Annals of Mathematical Statistics 18, 50–60. https://doi.org/10.1214/aoms/1177730491
* Holm, S. (1979). A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics 6,
  65–70. https://www.jstor.org/stable/4615733
