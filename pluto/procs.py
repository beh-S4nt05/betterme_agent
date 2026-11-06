# -*- coding: utf-8 -*-
"""⚙️ Processos em background do agente — v8.0.0.

O gap de paridade: `run_command` é síncrono (limite 600 s) — servidor
de dev, watcher ou suíte longa travava o agente. Este módulo dá o
trio completo (start/logs/stop), no padrão do projeto:

- guarda de segurança IGUAL à do run_command (denylist de comandos
  perigosos + segredos) antes de nascer o processo;
- teto de 5 processos simultâneos por agente;
- log em memória (deque, 400 linhas) E em arquivo
  `<data_dir>/procs/<nome>.log` — nada se perde;
- processos em sessão própria (killpg derruba filhos também);
- atexit: nada sobrevive ao app morrer.
"""
from __future__ import annotations

import atexit
import re
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

MAX_PROCS = 5
_LOG_MAX = 400
_LOCK = threading.Lock()
_PROCS: dict[str, dict] = {}
_RE_NOME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,30}$")


def _log_dir(cfg) -> Path:
    return Path(cfg.data_dir) / "procs"


def _leitor(nome: str, p: subprocess.Popen, caminho: Path) -> None:
    try:
        with caminho.open("ab") as f:      # binário: ln é bytes
            for ln in p.stdout:
                try:
                    f.write(ln)
                    f.flush()
                except OSError:
                    pass
                with _LOCK:
                    reg = _PROCS.get(nome)
                    if reg:
                        reg["log"].append(
                            ln.decode("utf-8", "replace").rstrip("\n"))
    except Exception:  # noqa: BLE001 — leitor é best-effort
        pass


def status() -> list[dict]:
    out = []
    with _LOCK:
        for nome, reg in sorted(_PROCS.items()):
            out.append({"nome": nome, "cmd": reg["cmd"],
                        "pid": reg["p"].pid,
                        "vivo": reg["p"].poll() is None,
                        "desde": reg["t0"]})
    return out


def start(cfg, nome: str, command: str, cwd: str = "") -> dict:
    from .tools import is_dangerous, touches_secrets

    nome = (nome or "").strip().lower()
    command = str(command or "").strip()
    if not _RE_NOME.match(nome):
        return {"erro": "nome inválido (a-z, 0-9, -, _; até 31 chars)"}
    if not command:
        return {"erro": "comando vazio"}
    if touches_secrets(command):
        return {"erro": "BLOQUEADO: comando acessa credenciais (secrets)"}
    if is_dangerous(command):
        return {"erro": "BLOQUEADO: comando perigoso (padrão run_command)"}
    with _LOCK:
        if any(nome in _PROCS and r["p"].poll() is None
               for r in [_PROCS.get(nome)] if r):
            return {"erro": f"já existe processo vivo chamado '{nome}' — "
                            "use proc_logs/proc_stop ou outro nome"}
        vivos = [n for n, r in _PROCS.items() if r["p"].poll() is None]
        if len(vivos) >= MAX_PROCS:
            return {"erro": f"limite de {MAX_PROCS} processos ativos "
                            f"({', '.join(vivos)}) — pare um antes"}
    try:
        _log_dir(cfg).mkdir(parents=True, exist_ok=True)
        p = subprocess.Popen(
            command, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=(cwd or None), start_new_session=True,
            text=False)
    except OSError as exc:
        return {"erro": f"falha ao iniciar: {exc}"}
    with _LOCK:
        _PROCS[nome] = {"p": p, "cmd": command, "t0": time.time(),
                        "log": deque(maxlen=_LOG_MAX)}
    t = threading.Thread(target=_leitor, args=(nome, p,
                                               _log_dir(cfg) / f"{nome}.log"),
                         daemon=True)
    t.start()
    return {"ok": True, "nome": nome, "pid": p.pid,
            "log": str(_log_dir(cfg) / f"{nome}.log")}


def logs(nome: str, tail: int = 30) -> dict:
    with _LOCK:
        reg = _PROCS.get((nome or "").strip().lower())
        if not reg:
            return {"erro": f"processo '{nome}' não existe — "
                            f"vivos: "
                            f"{', '.join(n for n, r in _PROCS.items() if r['p'].poll() is None) or 'nenhum'}"}
        linhas = list(reg["log"])[-max(1, min(int(tail or 30), 200)):]
        vivo = reg["p"].poll() is None
    return {"linhas": linhas, "vivo": vivo, "cmd": reg["cmd"]}


def stop(nome: str) -> dict:
    import signal
    with _LOCK:
        reg = _PROCS.get((nome or "").strip().lower())
        if not reg:
            return {"erro": f"processo '{nome}' não existe"}
    p = reg["p"]
    if p.poll() is not None:
        with _LOCK:
            _PROCS.pop(nome, None)
        return {"ok": True, "ja_morto": True, "exit": p.returncode}
    try:
        import os
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        p.terminate()
    try:
        p.wait(timeout=8)
    except subprocess.TimeoutExpired:
        try:
            import os
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except OSError:
            p.kill()
        p.wait(timeout=5)
    with _LOCK:
        _PROCS.pop(nome, None)
    return {"ok": True, "exit": p.returncode}


def _parar_todos() -> None:
    for n in list(_PROCS):
        try:
            stop(n)
        except Exception:  # noqa: BLE001
            pass


atexit.register(_parar_todos)
