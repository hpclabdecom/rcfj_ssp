from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import maquina
import rcfjssp_campaign as camp

OUT = ROOT / "results" / "_local" / "validacao"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--qualquer-maquina", action="store_true")
    ap.add_argument("--saida", default=str(OUT))
    a = ap.parse_args()
    maquina.exige_i7(a.qualquer_maquina)

    out = Path(a.saida)
    camp.OUT = out
    out.mkdir(parents=True, exist_ok=True)
    (out / "maquina.manifest").write_text(
        json.dumps(maquina.descreve(), indent=1, ensure_ascii=False), encoding="utf-8")
    rc = 0
    for exp in ("1", "2", "3"):
        rc |= camp.main(["--only", exp, "--workers", str(a.workers)])

    info = maquina.descreve()
    for p in out.glob("exp*.json"):
        row = json.loads(p.read_text(encoding="utf-8"))
        if "maquina" not in row:
            row["maquina"] = info
            p.write_text(json.dumps(row, indent=1), encoding="utf-8")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
