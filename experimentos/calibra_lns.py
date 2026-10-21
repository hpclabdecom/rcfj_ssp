from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import statistics
import sys
from pathlib import Path
from typing import Optional, Sequence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import maquina
import rcfjssp_lns as lns
from instancias_calibracao import CALIBRACAO, DIR

OUT = ROOT / "results" / "_local" / "calibracao"
GRADE = {"SUB_TIME": (1.5, 3.0, 5.0, 8.0), "RHO0": (0.15, 0.25, 0.35, 0.45)}


def combos():
    return [dict(zip(GRADE, v)) for v in itertools.product(*GRADE.values())]


def nome_combo(c) -> str:
    return "_".join(f"{k}{v}" for k, v in c.items())


def protocolo(segundos, walkers, fios) -> dict:
    p = {"x": "X9 calibracao", "grade": GRADE, "execucoes": 10,
         "instancias": [n for n, _, _ in CALIBRACAO], "segundos": segundos,
         "walkers": walkers, "fios": fios, "fixas": {k: v for k, v in lns.P.items()
                                                     if k not in GRADE},
         "sha_lns": hashlib.sha256((HERE / "rcfjssp_lns.py").read_bytes()).hexdigest()[:16],
         "sha_inst": hashlib.sha256((HERE / "instancias_calibracao.py").read_bytes()).hexdigest()[:16],
         "cpu": maquina.nome_cpu()}
    p["hash"] = hashlib.sha256(json.dumps(p, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return p


def resumo(pasta: Path, grava: bool = True) -> Optional[dict]:
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in (pasta / "runs").glob("*.json")]
    rows = [r for r in rows if r.get("makespan") and r.get("auditoria") == "ok"]
    if not rows:
        print("nada rodado ainda")
        return None
    best = {}
    for r in rows:
        best[r["instancia"]] = min(best.get(r["instancia"], 10 ** 9), r["makespan"])
    tab = {}
    for r in rows:
        rpd = 100.0 * (r["makespan"] - best[r["instancia"]]) / best[r["instancia"]]
        tab.setdefault(r["combo"], []).append(rpd)
    total = len(CALIBRACAO) * 10
    print(f"{'combinacao':32s} {'n':>4s} {'RPD medio %':>11s}")
    linhas = sorted(tab.items(), key=lambda kv: statistics.mean(kv[1]))
    for c, v in linhas:
        print(f"{c:32s} {len(v):4d} {statistics.mean(v):11.3f}")
    completos = [(c, v) for c, v in linhas if len(v) == total]
    if len(completos) < len(combos()):
        print(f"\n{len(completos)}/{len(combos())} combinacoes completas -- escolha so ao final.")
        return None
    c, v = completos[0]
    escolha = next(x for x in combos() if nome_combo(x) == c)
    out = {"parametros": escolha, "rpd_medio": statistics.mean(v),
           "melhor_por_instancia": best,
           "hash_campanha": json.loads((pasta / "protocolo.manifest").read_text())["hash"]}
    if grava:
        (pasta / "escolha.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(f"\nESCOLHA: {escolha} (RPD medio {out['rpd_medio']:.3f}%) -> {pasta / 'escolha.json'}")
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--segundos", type=float, default=60.0)
    ap.add_argument("--walkers", type=int, default=4)
    ap.add_argument("--fios", type=int, default=2)
    ap.add_argument("--saida", default=str(OUT))
    ap.add_argument("--resumo", action="store_true")
    ap.add_argument("--qualquer-maquina", action="store_true")
    ap.add_argument("--viz", nargs="*", default=None,
                    help="neighbourhoods of the runner (default: the four of the development runner; 'janela' = time window only)")
    a = ap.parse_args(argv)
    if a.viz:
        lns.P["VIZ"] = tuple(a.viz)
    pasta = Path(a.saida)
    if a.resumo:
        resumo(pasta)
        return 0
    falta = [f for _, _, f in CALIBRACAO if not (DIR / f).exists()]
    if falta:
        print(f"faltam as instancias de calibracao em {DIR}: {falta} (ver LEIAME.md la)")
        return 1
    maquina.exige_i7(a.qualquer_maquina)
    proto = protocolo(a.segundos, a.walkers, a.fios)
    (pasta / "runs").mkdir(parents=True, exist_ok=True)
    man = pasta / "protocolo.manifest"
    if man.exists() and json.loads(man.read_text())["hash"] != proto["hash"]:
        print("AVISO: protocolo mudou; execucoes antigas com outro hash serao refeitas.")
    man.write_text(json.dumps(proto, indent=1, default=str), encoding="utf-8")
    print(f"protocolo {proto['hash']}: 16 combinacoes x 10 instancias x 10 execucoes x {a.segundos:.0f} s")


    for semente in range(1, 11):
        for c in combos():
            for nome, fam, arq in CALIBRACAO:
                alvo = pasta / "runs" / f"{nome_combo(c)}__{nome}__s{semente}.json"
                if alvo.exists():
                    old = json.loads(alvo.read_text(encoding="utf-8"))
                    if old.get("protocol_hash") == proto["hash"] and old.get("makespan"):
                        continue
                prm = dict(lns.P); prm.update(c)
                r = lns.executa((fam, str(DIR / arq)), semente, a.walkers, a.fios, a.segundos, prm)
                r.pop("schedule", None)
                r.update(instancia=nome, familia=fam, combo=nome_combo(c), seed=semente,
                         protocol_hash=proto["hash"], maquina=maquina.descreve())
                tmp = alvo.with_suffix(".tmp")
                tmp.write_text(json.dumps(r), encoding="utf-8")
                os.replace(tmp, alvo)
                print(f"s{semente} {nome_combo(c)} {nome}: {r['makespan']} "
                      f"(auditoria {r.get('auditoria')})", flush=True)
    resumo(pasta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
