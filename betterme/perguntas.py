# -*- coding: utf-8 -*-
"""❓ Perguntas estruturadas ao operador — v8.0.0.

O maior gap de paridade: quando o pedido é ambíguo, o agente
ADIVINHAVA. Agora ele PERGUNTA com opções estruturadas e espera a
resposta (bloqueante com timeout) — o mesmo padrão que o próprio
operador experimentou ao usar agentes de verdade.

Mecanismo (desacoplado de canal — serve chat, CLI, API, WhatsApp):
- `perguntar()` registra a pergunta, emite evento {"type":
  "pergunta", id, pergunta, opcoes} no fluxo de eventos e BLOQUEIA
  até: resposta chegar · timeout (padrão 600 s) · cancelamento.
- Sem resposta → retorna instruindo o agente a seguir com a
  suposição DECLARADA (nunca trava a tarefa).
- Canais de resposta: `betterme responder <id> <texto>` (CLI) e
  POST /api/pergunta/<id> (HTTP). GUI/WhatsApp: follow-up.
"""
from __future__ import annotations

import threading
import time
import uuid

_LOCK = threading.Lock()
_PERGUNTAS: dict[str, dict] = {}
TIMEOUT_S = 600


def _limpar_antigas() -> None:
    agora = time.time()
    with _LOCK:
        for k in [k for k, v in _PERGUNTAS.items()
                  if agora - v["ts"] > 4 * 60 * 60]:
            _PERGUNTAS.pop(k, None)


def perguntar(pergunta: str, opcoes: list[dict] | None = None,
              timeout: float = TIMEOUT_S, on_event=None,
              cancel=None) -> str:
    """Bloqueia até o operador responder. Devolve a resposta ou a
    instrução de seguir com suposição declarada (timeout/cancel)."""
    pid = "q" + uuid.uuid4().hex[:8]
    opcoes = [{"id": o.get("id", f"op{i+1}"),
               "label": str(o.get("label", ""))[:80],
               "descricao": str(o.get("descricao", ""))[:160]}
              for i, o in enumerate(opcoes or [])][:4]
    _limpar_antigas()
    with _LOCK:
        _PERGUNTAS[pid] = {"event": threading.Event(), "resposta": None,
                           "pergunta": str(pergunta)[:400], "opcoes": opcoes,
                           "ts": time.time()}
    if on_event:
        try:
            on_event({"type": "pergunta", "id": pid,
                      "pergunta": str(pergunta)[:400], "opcoes": opcoes})
        except Exception:  # noqa: BLE001 — evento é best-effort
            pass
    limite = time.time() + max(10.0, float(timeout or TIMEOUT_S))
    while time.time() < limite:
        if cancel is not None and cancel.is_set():
            _PERGUNTAS.pop(pid, None)
            return ("⏹ cancelado antes da resposta do operador — pare a "
                    "tarefa com um resumo honesto do estado.")
        with _LOCK:
            reg = _PERGUNTAS.get(pid)
        if reg is None or reg["resposta"] is not None:
            break
        if reg:
            reg["event"].wait(0.25)
    with _LOCK:
        reg = _PERGUNTAS.pop(pid, None)
    if reg and reg["resposta"] is not None:
        return (f"✅ resposta do operador: {reg['resposta']}")
    return ("⏱ o operador não respondeu em tempo hábil — SIGA com a "
            "suposição mais razoável, DECLARE explicitamente que foi uma "
            "escolha sua e qual foi, e ofereça corrigir depois.")


def responder(pid: str, resposta: str) -> dict:
    with _LOCK:
        reg = _PERGUNTAS.get((pid or "").strip())
        if not reg:
            return {"erro": f"pergunta '{pid}' não está mais pendente "
                            "(expirou ou já foi respondida)"}
        reg["resposta"] = str(resposta).strip()[:600]
        reg["event"].set()
    return {"ok": True, "id": pid}


def pendentes() -> list[dict]:
    _limpar_antigas()
    with _LOCK:
        return [{"id": k, "pergunta": v["pergunta"], "opcoes": v["opcoes"]}
                for k, v in sorted(_PERGUNTAS.items())]
