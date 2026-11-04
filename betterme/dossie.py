"""🗂️ Dossiê de task — o modelo Antigravity (Google), nativo (v6.8.0).

No Antigravity, a unidade de revisão é o ARTEFATO, não o chat: o
plano antes de executar, a evidência da execução e a entrega
auditável, tudo anexado à TASK. Aqui o mesmo contrato, local-first:

  data_dir/dossies/T000N.md
    ## PLANO      — objetivo, tipo, passos, critérios, skills, pedido
    ## EVIDÊNCIA  — cada ferramenta executada (append, com hora)
    ## ENTREGA    — veredito do revisor, status, duração, texto final

Consumo: `betterme dossie T000N` (CLI) e
`GET /api/orchestrator/dossie/<tid>` (GUI). Tudo best-effort: o
dossiê NUNCA quebra o pipeline (append falho = dossiê incompleto,
task intacta).
"""
from __future__ import annotations

import time
from pathlib import Path

_MAX_LINHA = 240        # linha de evidência: curta e útil
_MAX_ENTREGA = 4000     # texto final (completo vive na conversa)


def caminho(cfg, tid: str) -> Path:
    """Arquivo do dossiê (data_dir/dossies/T000N.md)."""
    return cfg.data_dir / "dossies" / f"{(tid or 'T0000').strip()}.md"


def _append(cfg, tid: str, texto: str) -> None:
    p = caminho(cfg, tid)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(texto)


def abrir_plano(cfg, tid: str, *, message: str, objetivo: str, tipo: str,
                passos: list[str], criterios: list[str],
                skills: list[str]) -> None:
    """Cria o dossiê com o PLANO da task (na criação, antes do portão)."""
    linhas = [
        f"# 🗂️ Dossiê da task {tid}",
        "",
        f"*Aberto em {time.strftime('%Y-%m-%d %H:%M:%S')} — revisão por "
        "artefatos (modelo Antigravity, nativo).*",
        "",
        "## PLANO",
        "",
        f"- **objetivo**: {objetivo}",
        f"- **tipo**: {tipo}",
    ]
    if passos:
        linhas.append("- **passos**:")
        linhas += [f"  {i}. {p}" for i, p in enumerate(passos, 1)]
    if criterios:
        linhas.append("- **critérios que o revisor vai cobrar**:")
        linhas += [f"  - {c}" for c in criterios]
    if skills:
        linhas.append(f"- **skills**: {', '.join(skills)}")
    linhas += ["", f"> pedido original: {(message or '')[:400]}", "",
               "## EVIDÊNCIA", ""]
    _append(cfg, tid, "\n".join(linhas) + "\n")


def nota(cfg, tid: str, texto: str) -> None:
    """Linha de andamento do processo (aprovação, edição, cancelamento)."""
    _append(cfg, tid,
            f"\n> {time.strftime('%H:%M:%S')} · {str(texto)[:_MAX_LINHA]}\n")


def evidencia(cfg, tid: str, evento: dict) -> None:
    """Anexa UMA linha de evidência (tool_start/error do executor)."""
    msg = str(evento.get("message") or evento.get("content") or "").strip()
    if not msg:
        return
    _append(cfg, tid, f"{time.strftime('%H:%M:%S')} · {msg[:_MAX_LINHA]}\n")


def fechar(cfg, tid: str, *, veredito: str, problema: str, status: str,
           execucoes: int, dur, entrega: str, entregue: str = "") -> None:
    """Fecha o dossiê com a seção ENTREGA (veredito + texto auditável)."""
    txt = str(entrega or "").strip()
    trunc = txt[:_MAX_ENTREGA]
    if len(txt) > _MAX_ENTREGA:
        trunc += "\n…(entrega truncada — texto completo na conversa)"
    linhas = [
        "",
        "## ENTREGA",
        "",
        f"- **veredito do revisor**: {veredito}"
        + (f" — {str(problema)[:200]}" if problema else ""),
        f"- **status**: {status} · {execucoes} execução(ões) · {dur}s"
        + (f" · entrega {entregue}" if entregue else ""),
        "",
        "```",
        trunc,
        "```",
        "",
    ]
    _append(cfg, tid, "\n".join(linhas))


def ler(cfg, tid: str) -> str:
    """Dossiê completo ("" se a task não tiver — tasks antigas, p.ex.)."""
    try:
        return caminho(cfg, tid).read_text(encoding="utf-8")
    except OSError:
        return ""
