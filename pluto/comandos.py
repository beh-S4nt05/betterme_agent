"""⌘ /comandos do chat — dispatcher único (v7.0.0).

Padrão do Claude Code (104 slash commands como superfície de comando),
adaptado: UM lugar resolve os comandos que não passam pelo pipeline
(zero tokens de modelo). Usado pela GUI (/api/chat/command) e pelo
terminal (pluto chat). Retorna str (resposta pronta) ou None
(não é comando meu — segue o fluxo normal).

  /dossie <tid>   dossiê da task: plano, evidência, entrega
  /prazo <min>    modo prazo: contagem + revisão apertada + estado do
                  roteador (nuvem quando o local não dá conta)
  /ajuda          lista completa (inclui os comandos históricos)
"""
from __future__ import annotations

AJUDA = (
    "comandos do chat (CLI e GUI — zero tokens, respondidos na hora):\n"
    "  /goal <texto>   — objetivo da sessão (o orquestrador usa em cada task)\n"
    "  missão: <texto> — modo missão: subtasks em sequência com validação\n"
    "  /dossie <tid>   — dossiê da task: PLANO · EVIDÊNCIA · ENTREGA\n"
    "  /prazo <min>    — modo prazo: mostra contagem, aperta a revisão e\n"
    "                    informa se o cérebro está na nuvem (/prazo off limpa)\n"
    "  /tasks          — últimas tasks do orquestrador\n"
    "  /skills         — skills ativas (aplicadas automaticamente)\n"
    "  /tools          — ferramentas disponíveis ao agente\n"
    "  /memoria        — o que o agente lembra de você\n"
    "  /autonomia [n]  — nível de autonomia (colaborador/supervisor/autônomo)\n"
    "  /provider       — estado do roteador de provedores\n"
    "  /reset          — limpa o objetivo da sessão\n"
    "  /ajuda          — esta lista\n"
    "anexos com @ (o agente lê o conteúdo REAL do disco):\n"
    "  @arquivo.md @pasta/ @/caminho/absoluto @~/arquivo — no meio do pedido:\n"
    "  “revise @src/app.py e corrija o @README.md”"
)


def executar(cfg, cmd: str, args: str, session_id: str = "cli") -> str | None:
    """Responde o comando (str) ou devolve None se não for deste módulo."""
    cmd = (cmd or "").lower().strip()
    args = (args or "").strip()

    if cmd in ("/ajuda", "/help", "/?"):
        return AJUDA

    if cmd in ("/dossie", "/dossier", "/dossiê"):
        from .dossie import ler
        from .orchestrator import list_tasks

        tid = args.split()[0] if args.split() else ""
        if tid:
            texto = ler(cfg, tid)
            if texto:
                return texto
        tasks = list_tasks(cfg, limit=6)
        if not tasks:
            return ("nenhuma task ainda — peça uma ação no chat "
                    "(depois: /dossie T0001)")
        linhas = "\n".join(
            f"  {t['id']} [{t.get('status')}] {t.get('objetivo', '')[:70]}"
            for t in tasks)
        return (f"sem dossiê para “{tid or '—'}” — tasks recentes:\n" + linhas)

    if cmd in ("/prazo", "/deadline"):
        from . import orchestrator as orc

        baixo = args.lower()
        if baixo in ("off", "0", "cancela", "cancelar", "limpa", "remover"):
            orc.set_prazo(session_id, 0)
            return "⏱ prazo limpo — execução volta ao padrão (revisão completa)."
        if not args:
            rest = orc.prazo_restante(session_id)
            if rest <= 0:
                return ("nenhum prazo ativo — use: /prazo <minutos> "
                        "(ex.: /prazo 15)")
            return (f"⏱ prazo ativo: {int(rest // 60)} min restantes "
                    f"({int(rest)}s)")
        try:
            minutos = float(args.split()[0].replace(",", "."))
        except ValueError:
            return "uso: /prazo <minutos> · /prazo off"
        if minutos <= 0:
            orc.set_prazo(session_id, 0)
            return "⏱ prazo limpo — execução volta ao padrão."
        orc.set_prazo(session_id, minutos)
        # estado do roteador: local vs nuvem (o objetivo é não ser
        # limitado pelo hardware)
        nuvem = ""
        try:
            from .llm_providers import melhor_provedor
            prov = melhor_provedor(cfg)
            usa = (prov and getattr(cfg, "auto_provider", True)
                   and str(getattr(cfg, "llm_provider", "local")) == "local")
            if prov and usa:
                nuvem = f"\n🧠 roteador: cérebro na nuvem ({prov}) — " \
                        "fallback local na falha."
            elif prov:
                nuvem = f"\n🧠 há chave de {prov} guardada mas o roteador " \
                        "está desligado (pluto provider set " + prov + ")."
            else:
                nuvem = ("\n🧠 sem provider online guardado — o cérebro é o "
                         "Ollama local. Para prazos curtos, guarde uma chave "
                         "grátis: pluto provider guia (2 min).")
        except Exception:  # noqa: BLE001
            pass
        return (f"⏱ prazo definido: {minutos:g} min. Neste prazo: revisão "
                "apertada (sem refazer se reprovar — entrega com ressalva) "
                "e etapas focadas quando a task for complexa." + nuvem)

    return None
