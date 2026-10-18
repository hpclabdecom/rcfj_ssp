"""[PROPOSTO -- NAO rodado no i7.] X10: CP-SAT no modelo INTEIRO com a codificacao nativa de
reservatorio (modelo_reservatorio.build, a mesma da heuristica), 8 fios, no tempo T_i do ALNS-CP
(Tabela 10), 10 sementes. Separa 'ganho da LNS' de 'ganho da codificacao' em X8/X8b x ALNS-CP.

Instalar como experimentos/x10_reservatorio.py e rodar da raiz do projeto, no i7:
    python experimentos\\x10_reservatorio.py
    python rcfjssp_audit.py --results results\\final\\reservatorio_w8_TALNS
Custo: 10 sementes x soma(T_ALNS) = 10 x 4546,74 s = 12,6 h.

Protocolo: grava <saida>/protocolo.manifest com um hash que cobre versao do OR-Tools, workers,
escala, orcamento por instancia, SHA de modelo_reservatorio.py, rcfjssp_full.py e rcfjssp_core.py,
e a CPU. O SHA deste script fica FORA do hash (so proveniencia), como em rcfjssp_final.py.
Cada execucao grava o log completo do CP-SAT em <saida>/logs/. Se o manifesto existente tiver
outro hash, ele e arquivado em protocolos_anteriores.jsonl; JSONs (e logs) de outro protocolo sao
MOVIDOS para <saida>/_DESCARTADO_<hash>/ -- nunca sobrescritos. A retomada pula so o protocolo
atual. No fim, falha (rc 1) se a pasta tiver JSON de mais de um hash. --escala != 1 so e aceito
com --saida (para nunca misturar teste com a pasta do paper).

Testes (NAO sao resultado; em todos, 8 workers pedidos sobre 2 CPUs logicas):
  * esta versao (rodada 3 da auditoria): conteiner (Xeon 2,1 GHz, maquina.fios = 2), OR-Tools
    9.15.6755 no scratch, --qualquer-maquina, --saida <scratch>/x10b: (T1) --escala 0.02 em
    lcbrtu_9 s1 (4,1 s) e lcbrtu_1 s1 (3,6 s); (T2) retomada pula as 2; (T3) --escala 0.021:
    manifesto antigo arquivado, as 2 execucoes antigas MOVIDAS para _DESCARTADO_<hash>/, lcbrtu_9
    refeito (4,3 s); (T4) editar o script nao muda o hash (retomada pula); (T5) JSON com hash
    estranho e movido para _DESCARTADO_intruso/; recusa sem --saida; auditor sem solver ok;
  * versao da rodada 2 (manifesto e logs, mas sobrescrevia em silencio): conteiner, --escala 0.02,
    lcbrtu_9 s1 4,1 s e lcbrtu_1 s1 3,6 s; o arquivo de lcbrtu_9 que sobrou e o da reexecucao com
    --escala 0.021 (4,4 s), que sobrescreveu o primeiro -- o defeito corrigido nesta versao;
  * 1a versao (sem manifesto nem logs): 2 execucoes no VM do laptop do usuario (Ryzen 7 5700U),
    fora da pasta dele ($HOME/x10test), --escala 0.1: lcbrtu_9 s1 20,7 s e lcbrtu_3 s1 49,6 s.
    Segundo o parecer, os 2 JSONs registram maquina.fios = 2 (nao reverifiquei: o dispositivo
    ficou fora do escopo das rodadas 2-3).
"""
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
import ortools                                               # noqa: E402
from ortools.sat.python import cp_model                      # noqa: E402
from rcfjssp_core import parse                               # noqa: E402
from rcfjssp_reference import CONFIG, TABLE10                # noqa: E402
import maquina, modelo_reservatorio as mr, rcfjssp_audit as aud   # noqa: E402,E401
from rcfjssp_lns import T_ALNS                               # noqa: E402

maquina.exige_i7(a.qualquer_maquina)
UP = ROOT / "instances" / "upstream" / "RCFJSSP-main" / "Experiment 4"
OUT = Path(a.saida) if a.saida else ROOT / "results" / "final" / "reservatorio_w8_TALNS"
(OUT / "logs").mkdir(parents=True, exist_ok=True)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]
# O hash cobre SO o que define o numero (como SUBSTANTIVOS em rcfjssp_final.py:121-128).
# sha_script fica FORA do hash e vai so como proveniencia: editar mensagens do script nao
# invalida execucoes ja feitas.
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
    """Move JSONs (e seus logs) de outro protocolo para _DESCARTADO_<hash>/ -- nunca sobrescreve."""
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
        if alvo.exists():      # so pode ser do protocolo atual: os outros foram movidos acima
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
