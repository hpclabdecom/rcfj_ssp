from __future__ import annotations

import os
import platform
import subprocess

ALVO = "i7-2600"


def nome_cpu() -> str:
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                return str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    try:
        return subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                              capture_output=True, text=True).stdout.strip() or "?"
    except OSError:
        return platform.processor() or "?"


def e_a_do_paper() -> bool:
    return ALVO in nome_cpu()


def descreve() -> dict:
    return {"cpu": nome_cpu(), "fios": os.cpu_count(),
            "sistema": f"{platform.system()} {platform.release()}",
            "host": platform.node(), "maquina_do_paper": e_a_do_paper()}


def exige_i7(qualquer_maquina: bool = False) -> None:
    if e_a_do_paper():
        return
    msg = (f"Esta maquina e '{nome_cpu()}', nao a plataforma de referencia {ALVO}.")
    if qualquer_maquina:
        print(f"AVISO: {msg} Seguindo por --qualquer-maquina; o resultado sai "
              f"marcado maquina_do_paper=false.", flush=True)
        return
    raise SystemExit(f"RECUSADO: {msg} Use --qualquer-maquina so para teste.")
