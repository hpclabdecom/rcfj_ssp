# `paper/ref/`

`kasapidis2025_texto.txt` is the plain-text extraction (`pdftotext -layout`) of the accepted manuscript of
Kasapidis, Paraskevopoulos, Mourtos and Repoussis (2025), as deposited in City Research Online (CC BY 4.0). It is
read by `experimentos/rcfjssp_lns.py` (and therefore by PT-W, which imports it) to confirm the Table 10 budgets
against the article text before every run. The path is fixed by `rcfjssp_lns.py`, which is kept byte-identical for
its recorded SHA-256 (see the root README), so this folder keeps its original name. The published version of the
article is in `papers/`.
