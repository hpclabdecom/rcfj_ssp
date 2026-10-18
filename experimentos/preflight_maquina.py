from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

OK, AVISO, FALHA = "OK   ", "AVISO", "FALHA"
report: list = []


def say(level: str, item: str, detail: str) -> None:
    report.append({"nivel": level.strip(), "item": item, "detalhe": detail})
    print(f"[{level}] {item}: {detail}", flush=True)


def cpu_info() -> dict:
    info = {"processor": platform.processor(), "logical": os.cpu_count()}
    if os.name == "nt":
        ps = ("Get-CimInstance Win32_Processor | Select-Object Name,"
              "NumberOfCores,NumberOfLogicalProcessors | ConvertTo-Json")
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                                 capture_output=True, text=True, timeout=60).stdout
            data = json.loads(out)
            data = data[0] if isinstance(data, list) else data
            info.update(name=data.get("Name", "").strip(),
                        cores=data.get("NumberOfCores"),
                        logical=data.get("NumberOfLogicalProcessors"))
        except Exception as exc:
            info["erro"] = str(exc)
    else:
        try:
            txt = Path("/proc/cpuinfo").read_text()
            names = [l.split(":", 1)[1].strip() for l in txt.splitlines()
                     if l.startswith("model name")]
            cores = {l for l in txt.splitlines() if l.startswith("core id")}
            info.update(name=names[0] if names else "?", cores=len(cores) or None)
        except OSError:
            pass
    return info


def ram_gb() -> float:
    if os.name == "nt":
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        ms = MS()
        ms.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
        return ms.ullTotalPhys / 2**30
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemTotal"):
            return int(line.split()[1]) / 2**20
    return 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpo-exe", default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--segundos-cpsat", type=float, default=60.0)
    ap.add_argument("--segundos-cpo", type=float, default=30.0)
    a = ap.parse_args()


    cpu = cpu_info()
    say(OK, "CPU", f"{cpu.get('name') or cpu.get('processor')}  "
                   f"nucleos={cpu.get('cores')}  fios={cpu.get('logical')}")
    import maquina
    if maquina.e_a_do_paper():
        say(OK, "maquina do paper", f"{maquina.nome_cpu()} -- resultados podem ir para o paper")
    else:
        say(AVISO, "maquina do paper",
            f"{maquina.nome_cpu()} NAO e o {maquina.ALVO}: os scripts de campanha "
            f"recusam rodar aqui (so com --qualquer-maquina, para teste)")
    if cpu.get("logical") and cpu["logical"] < a.workers:
        say(AVISO, "workers", f"{a.workers} pedidos, {cpu['logical']} fios: use "
                              f"--workers {cpu['logical']}")
    gb = ram_gb()
    say(OK if gb >= 12 else AVISO, "RAM", f"{gb:.1f} GB")
    say(OK, "Python", f"{platform.python_version()} ({platform.system()} {platform.release()})")


    if "onedrive" in str(ROOT).lower():
        say(AVISO, "pasta", f"{ROOT} esta no OneDrive: copie para fora (ex.: C:\\RCFJSSP)")
    else:
        say(OK, "pasta", str(ROOT))


    try:
        import ortools
        from ortools.sat.python import cp_model
        v = getattr(ortools, "__version__", "?")
        say(OK if v == "9.15.6755" else AVISO, "OR-Tools",
            v + ("" if v == "9.15.6755" else "  (campanhas usaram 9.15.6755)"))
        from rcfjssp_core import parse
        import rcfjssp_full as m4
        inst = parse(ROOT / "instances" / "upstream" / "RCFJSSP-main" /
                     "Experiment 4" / "lcbrtu_9.fjs")
        model, *_ = m4.build(inst, True, None)
        s = cp_model.CpSolver()
        s.parameters.num_search_workers = a.workers
        s.parameters.max_time_in_seconds = a.segundos_cpsat
        t = time.perf_counter()
        st = s.Solve(model)
        ok = st in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        say(OK, "CP-SAT no Exp. 4",
            f"lcbrtu_9, {a.workers} workers, {a.segundos_cpsat:.0f} s: {s.StatusName(st)}"
            + (f", UB {int(s.ObjectiveValue())}, LB {int(s.BestObjectiveBound())}" if ok else
               " (sem solucao em tempo curto nao e defeito; o binario rodou)")
            + f"  [{time.perf_counter() - t:.0f} s]")
    except Exception as exc:
        say(FALHA, "OR-Tools", f"{type(exc).__name__}: {exc}")


    try:
        from importlib.metadata import version as pkgver, PackageNotFoundError
        try:
            say(AVISO, "pacote cplex (pip)",
                f"{pkgver('cplex')} instalado: traz um cpoptimizer Community. "
                "Com o Studio, 'pip uninstall cplex' ou fixe CPO_EXE.")
        except PackageNotFoundError:
            say(OK, "pacote cplex (pip)", "ausente (bom: nao ha Community concorrendo)")
        say(OK, "docplex", pkgver("docplex"))
    except Exception as exc:
        say(FALHA, "docplex", f"{exc}  ->  pip install docplex")

    try:
        import rcfjssp_cpo as cpo
        exe = cpo.find_cpo_exe(a.cpo_exe)
        if not exe or not Path(exe).exists():
            say(FALHA, "cpoptimizer", f"nao encontrado ({exe}). Passe --cpo-exe ou "
                "defina CPO_EXE com o caminho do cpoptimizer.exe do CPLEX Studio")
        else:
            say(OK, "cpoptimizer", exe)
            cpo.CPO_EXE = exe
            inst = cpo.load_instance("4", "lcbrtu_9", "all")
            spec = cpo.CONFIG[("exp4", "all")]
            t = time.perf_counter()
            try:
                row = cpo.solve(inst, spec, a.segundos_cpo, None, None)
                sv = row["solver"]
                comm = sv.get("community_edition")
                say(FALHA if comm else OK, "licenca do CP Optimizer",
                    f"versao {sv.get('version')}, Community={comm}, workers={sv.get('workers_used')}; "
                    f"Exp. 4 lcbrtu_9 em {a.segundos_cpo:.0f} s: {row['status']} "
                    f"UB {row['makespan']} LB {row['lower_bound']}  [{time.perf_counter() - t:.0f} s]")
            except Exception as exc:
                msg = str(exc)
                if "size limit" in msg:
                    say(FALHA, "licenca do CP Optimizer",
                        "este executavel e a edicao Community (recusou o Exp. 4). "
                        "Aponte para o do CPLEX Optimization Studio.")
                else:
                    say(FALHA, "CP Optimizer", f"{type(exc).__name__}: {msg[:300]}")
    except Exception as exc:
        say(FALHA, "CP Optimizer", f"{type(exc).__name__}: {exc}")

    host = platform.node() or "maquina"
    out = ROOT / "results" / f"preflight_{host}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"quando": time.strftime("%Y-%m-%d %H:%M:%S"),
                               "cpu": cpu, "ram_gb": round(gb, 1),
                               "itens": report}, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    falhas = [r for r in report if r["nivel"] == "FALHA"]
    print(f"\n{'PRONTA' if not falhas else 'NAO PRONTA'}: {len(falhas)} falha(s), "
          f"{sum(r['nivel'] == 'AVISO' for r in report)} aviso(s). Gravado em {out}")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
