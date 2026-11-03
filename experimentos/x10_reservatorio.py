import argparse, hashlib, json, os, platform, sys, time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--raiz", default=None, help="raiz do projeto (padrao: pai da pasta deste arquivo)")
ap.add_argument("--saida", default=None, help="pasta de saida (obrigatoria se --escala != 1)")
ap.add_argument("--sementes", type=int, nargs="*", default=list(range(1, 11)))
ap.add_argument("--instancias", nargs="*", default=[f"lcbrtu_{i}" for i in range(10)])
ap.add_argument("--workers", type=int, default=8)
ap.add_argument("--escala", type=float, default=1.0, help="so teste; o protocolo e 1.0")
ap.add_argument("--qualquer-maquina", action="store_true")
a = ap.parse_args()
if a.escala != 1.0 and not a.saida:
    sys.exit("RECUSADO: --escala != 1 exige --saida (a pasta do paper so recebe o protocolo 1.0)")

ROOT = Path(a.raiz).resolve() if a.raiz else Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "experimentos"))
import ortools
from ortools.sat.python import cp_model
from rcfjssp_core import parse
from rcfjssp_reference import CONFIG, TABLE10
import maquina, modelo_reservatorio as mr, rcfjssp_audit as aud
from rcfjssp_lns import T_ALNS

maquina.exige_i7(a.qualquer_maquina)
UP = ROOT / "instances" / "upstream" / "RCFJSSP-main" / "Experiment 4"
OUT = Path(a.saida) if a.saida else ROOT / "results" / "final" / "reservatorio_w8_TALNS"
(OUT / "logs").mkdir(parents=True, exist_ok=True)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


proto = {"x": "X10 reservatorio nativo, modelo inteiro", "ortools": ortools.__version__,
         "workers": a.workers, "escala": a.escala,
         "orcamento": {s: T_ALNS[s] * a.escala for s in sorted(T_ALNS)},
         "solver": "CP-SAT de fabrica salvo workers, tempo e semente",
         "sha_modelo_reservatorio": sha(ROOT / "experimentos" / "modelo_reservatorio.py"),
         "sha_rcfjssp_full": sha(ROOT / "rcfjssp_full.py"), "sha_rcfjssp_core": sha(ROOT / "rcfjssp_core.py"),
         "cpu": maquina.nome_cpu()}
proto["hash"] = hashlib.sha256(json.dumps(proto, sort_keys=True).encode()).hexdigest()[:16]
proveniencia_script = sha(__file__)


def descarta(paths, h):
    dest = OUT / f"_DESCARTADO_{h}"
    (dest / "logs").mkdir(parents=True, exist_ok=True)
    for pth in paths:
        os.replace(pth, dest / pth.name)
        lg = OUT / "logs" / (pth.stem + ".log")
        if lg.exists():
            os.replace(lg, dest / "logs" / lg.name)
    print(f"AVISO: {len(paths)} execucao(oes) do protocolo {h} movidas para {dest.name}/", flush=True)


man = OUT / "protocolo.manifest"
if man.exists():
    prev = json.loads(man.read_text(encoding="utf-8"))
    if prev.get("hash") != proto["hash"]:
        with (OUT / "protocolos_anteriores.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(prev) + "\n")
        print(f"AVISO: manifesto anterior {prev.get('hash')} arquivado em protocolos_anteriores.jsonl", flush=True)
por_hash = {}
for pth in OUT.glob("lcbrtu_*.json"):
    h = json.loads(pth.read_text(encoding="utf-8")).get("protocol_hash")
    if h != proto["hash"]:
        por_hash.setdefault(h, []).append(pth)
for h, paths in por_hash.items():
    descarta(paths, h)
man.write_text(json.dumps(dict(proto, sha_script_proveniencia=proveniencia_script), indent=1), encoding="utf-8")
print("protocolo", proto["hash"], "->", OUT, flush=True)

for seed in a.sementes:
    for stem in a.instancias:
        alvo = OUT / f"{stem}_s{seed}.json"
        if alvo.exists():
            old = json.loads(alvo.read_text(encoding="utf-8"))
            assert old.get("protocol_hash") == proto["hash"]
            print(stem, seed, "ja feito", old.get("makespan"), flush=True)
            continue
        inst = parse(UP / f"{stem}.fjs")
        m, st, en, rl, pr = mr.build(inst, True)
        s = cp_model.CpSolver()
        s.parameters.num_search_workers = a.workers
        s.parameters.max_time_in_seconds = T_ALNS[stem] * a.escala
        s.parameters.random_seed = seed
        s.parameters.log_search_progress = True
        s.parameters.log_to_stdout = False
        logf = OUT / "logs" / f"{stem}_s{seed}.log"
        with logf.open("w", encoding="utf-8") as fh:
            s.log_callback = lambda line: fh.write(line + "\n")
            t0 = time.perf_counter(); r = s.Solve(m); w = round(time.perf_counter() - t0, 1)
        ok = r in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        sch = [{"op": k, "job": o.job, "index": o.index,
                "machine": next(mm for mm, _ in o.modes if s.Value(pr[(k, mm)])),
                "tool": o.tool, "start": s.Value(st[k]), "end": s.Value(en[k]),
                "release": s.Value(rl[k])} for k, o in enumerate(inst.operations)] if ok else None
        mk = max(e["end"] for e in sch) if sch else None
        prob = aud.check_schedule(inst, sch, CONFIG[("exp4", "all")], mk) if sch else ["sem solucao"]
        row = {"instance": stem, "experiment": "exp4", "config": "all", "seed": seed,
               "status": s.StatusName(r), "makespan": mk,
               "lower_bound": int(s.BestObjectiveBound()) if ok else None,
               "seconds": w, "orcamento": T_ALNS[stem] * a.escala,
               "schedule": sch if not prob else None, "auditoria": prob or "ok",
               "their_alns": TABLE10[stem][2], "protocol_hash": proto["hash"],
               "log": str(logf.relative_to(OUT)), "maquina": maquina.descreve(),
               "provenance": {"ortools": ortools.__version__, "python": platform.python_version(),
                              "sha_script": proveniencia_script}}
        tmp = alvo.with_suffix(".tmp"); tmp.write_text(json.dumps(row, indent=1), encoding="utf-8"); os.replace(tmp, alvo)
        print(stem, seed, row["status"], mk, row["lower_bound"], w, row["auditoria"], flush=True)

hs = {json.loads(p_.read_text(encoding="utf-8")).get("protocol_hash") for p_ in OUT.glob("lcbrtu_*.json")}
if hs != {proto["hash"]}:
    sys.exit(f"ERRO: a pasta {OUT} tem hashes {hs}; esperado so {proto['hash']}")
print("ok: todos os JSON da pasta tem o protocolo", proto["hash"], flush=True)
