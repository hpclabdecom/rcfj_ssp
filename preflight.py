from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

FAIL = []


def ok(label, detail=""):
    print(f"  [ok]   {label}{'  ' + detail if detail else ''}")


def bad(label, remedy):
    print(f"  [FALHA] {label}")
    print(f"          -> {remedy}")
    FAIL.append(label)


def main() -> int:
    print("Preflight RCFJSSP\n")

    version = sys.version_info
    label = f"Python {version.major}.{version.minor}.{version.micro}"
    if version < (3, 8):
        bad(label, "instale Python 3.10 ou superior de python.org")
    elif version < (3, 9):
        ok(label, "(3.8 e antigo: o pip vai instalar um ortools mais velho, "
                  "o que funciona; se der erro, instale Python 3.12)")
    else:
        ok(label)

    try:
        from ortools.sat.python import cp_model
        import ortools
        ok("ortools", getattr(ortools, "__version__", "versao desconhecida"))
    except ImportError:
        bad("ortools nao instalado", "python -m pip install ortools")
        print("\nInterrompido: sem o solver nada mais pode ser checado.")
        return 1

    up = HERE / "instances" / "upstream" / "RCFJSSP-main"
    if not up.exists():
        bad(f"instancias ausentes em {up}",
            "extraia RCFJSSP-main.zip dentro de instances/upstream/")
        return 1
    counts = {}
    for name, pattern, expected in (
            ("Experimento 1", "Experiment 1/*.fjs", 10),
            ("Experimento 2", "Experiment 2/*/*.fjs", 40),
            ("Experimento 3", "Experiment 3/*/*.fjs", 30),
            ("Experimento 4", "Experiment 4/*.fjs", 10)):
        found = len(list(up.glob(pattern)))
        counts[name] = found
        (ok if found == expected else
         lambda l, r: bad(l, r))(f"{name}: {found} instancias",
                                 f"esperava {expected}")

    try:
        from rcfjssp_core import parse
        import rcfjssp_buffers as m1
        import rcfjssp_cpsat as m2
        import rcfjssp_wip as m3
        import rcfjssp_full as m4
        ok("modulos importam")
    except Exception as error:
        bad(f"import falhou: {error}", "arquivo faltando ou corrompido")
        return 1


    bad_parse = []
    for path in sorted(up.rglob("*.fjs")):
        try:
            parse(path)
        except Exception as error:
            bad_parse.append(f"{path.name}: {error}")
    if bad_parse:
        bad(f"{len(bad_parse)} instancias nao parseiam",
            f"primeira: {bad_parse[0]}")
    else:
        ok(f"{sum(counts.values())} instancias parseiam com contagem exata")


    inst = parse(up / "Experiment 1" / "lcb0.fjs")
    row = m1.solve(inst, "zero", workers=2, limit=60)
    target = m1.PUBLISHED["zero"]["lcb0"]
    if row["makespan"] == target:
        ok(f"solve de teste: lcb0/zero = {row['makespan']}, confere com a Tabela 7")
    else:
        bad(f"solve de teste deu {row['makespan']}, esperado {target}",
            "o modelo ou a transcricao mudou; nao rode a campanha assim")
    if not row.get("schedule"):
        bad("solve nao devolveu escalonamento",
            "sem isso a auditoria nao verifica viabilidade")
    else:
        ok(f"escalonamento gravado ({len(row['schedule'])} operacoes)")

    import os
    print(f"\n  nucleos disponiveis: {os.cpu_count()}")
    print(f"  sugestao: --workers {os.cpu_count()}")

    if FAIL:
        print(f"\n{len(FAIL)} problema(s). Resolva antes de rodar a campanha.")
        return 1
    print("\nTudo certo. Agora:")
    print(f"  python rcfjssp_campaign.py --workers {os.cpu_count()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
