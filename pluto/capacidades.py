"""V9.0.0 (P7 · T249): capacidades do cérebro ATIVO — o Princípio 0.

> **O MODELO É A BASE, NÃO O LIMITADOR.** (diretiva do operador)

Este é o ÚNICO lugar do código que sabe "que cérebro está rodando".
Todo o resto (verificação de 2ª passada, autoavaliação, carregador de
skills, autonomia, escalonamento) consulta os PORTÕES daqui — nenhum
módulo pergunta "que modelo é?" de forma espalhada. Trocar o cérebro
no config.yaml (provider, modelo, num_ctx) muda perfil e portões no
próximo boot, SEM refatorar nada. O hermes3:8b é o PISO de hoje, não
o teto do projeto.

Perfis (o cérebro define o NÍVEL de execução, nunca a EXISTÊNCIA de
uma capacidade — toda capacidade nasce atrás de um portão):

- ``leve``   — modelo pequeno local (ex.: hermes3:8b). Verificação em
  passada única com checklist; skills essenciais PT-BR.
- ``rapido`` — provedor externo veloz (groq/flash/instant…) ou modelo
  local médio. Verificação completa (a 2ª passada fica imperceptível).
- ``forte``  — modelo grande. Tudo: skills avançadas, ctx longo,
  computer-use (quando o sandbox P6 existir), autonomia estendida.

Uso::

    from .capacidades import capacidades
    cap = capacidades(cfg)
    if cap.aberto("verificacao_completa"): ...
"""
from __future__ import annotations

import re

# portões conhecidos — a lista é o contrato (consumidores usam .aberto())
PORTOES = ("verificacao_completa", "skills_avancadas", "ctx_longo",
           "computer_use", "autonomia_estendida")

# níveis de skill no frontmatter do SKILL.md (default: leve = sempre carrega)
NIVEIS_SKILL = ("leve", "rapido", "forte")

_NIVEL = {"leve": 1, "rapido": 2, "forte": 3}

# heurísticas de nomes (honestas, não mágicas): o nome do modelo é o
# que o config/REGISTRY declara — padrões conhecidos, default honesto
_FORTE = ("pro", "max", "gpt-5", "gpt-4", "o3", "o4", "claude", "70b",
          "90b", "120b", "235b", "405b", "deepseek", "-r1")
_RAPIDO = ("flash", "instant", "mini", "small", "haiku", "turbo",
           "nano", ":free", "8b", "7b", "9b", "3b", "1b")
_RE_PARAMS = re.compile(r"(\d+(?:\.\d+)?)\s*b\b", re.I)


class Capacidades:
    """Perfil + portões do cérebro ativo (valor, não referência)."""

    __slots__ = ("perfil", "provedor", "modelo", "num_ctx", "fonte",
                 "portoes")

    def __init__(self, perfil: str, provedor: str, modelo: str,
                 num_ctx: int, fonte: str, portoes: dict):
        self.perfil = perfil
        self.provedor = provedor
        self.modelo = modelo
        self.num_ctx = num_ctx
        self.fonte = fonte
        self.portoes = dict(portoes)

    @property
    def nivel(self) -> int:
        return _NIVEL.get(self.perfil, 1)

    def aberto(self, portao: str) -> bool:
        """Um portão está aberto para o cérebro ATIVO?"""
        if portao not in PORTOES:
            raise KeyError(f"portão desconhecido: {portao!r} "
                           f"(válidos: {', '.join(PORTOES)})")
        return bool(self.portoes.get(portao))

    def __eq__(self, other) -> bool:
        if not isinstance(other, Capacidades):
            return NotImplemented
        return all(getattr(self, a) == getattr(other, a)
                   for a in Capacidades.__slots__)

    def __repr__(self) -> str:
        return (f"Capacidades(perfil={self.perfil!r}, "
                f"provedor={self.provedor!r}, modelo={self.modelo!r}, "
                f"num_ctx={self.num_ctx}, fonte={self.fonte!r})")


def _params_do_nome(modelo: str) -> int | None:
    """Parâmetros (em bilhões) declarados no nome: 'hermes3:8b' → 8."""
    m = _RE_PARAMS.search(modelo or "")
    return int(float(m.group(1))) if m else None


def _perfil_local(modelo: str) -> str:
    """Ollama local: o tamanho DECLARADO no nome dá o nível."""
    p = _params_do_nome(modelo)
    if p is None:
        return "leve"                    # sem tamanho no nome → piso honesto
    if p >= 70:
        return "forte"
    if p >= 14:
        return "rapido"
    return "leve"


def _perfil_externo(modelo: str) -> str:
    """Provedor externo: padrões do nome; desconhecido → rapido
    (meio honesto: externo é ao menos rápido e verificável)."""
    nome = (modelo or "").lower()
    if any(p in nome for p in _FORTE):
        return "forte"
    if any(p in nome for p in _RAPIDO):
        return "rapido"
    return "rapido"


def cerebro_ativo(cfg) -> tuple[str, str, str]:
    """(provedor, modelo, fonte) — a MESMA decisão do agente real:
    provider fixado no config > roteador automático (chave guardada)
    > Ollama local. Espelha comandos.py; nunca inventa cérebro."""
    prov = str(getattr(cfg, "llm_provider", "local") or "local")
    if prov != "local":
        try:
            from .llm_providers import REGISTRY
            modelo = str(getattr(cfg, "llm_model", "")
                         or REGISTRY.get(prov, {}).get("model") or "")
        except Exception:  # noqa: BLE001
            modelo = str(getattr(cfg, "llm_model", "") or "")
        return prov, modelo, "config (provider fixado)"
    try:
        if getattr(cfg, "auto_provider", True):
            from .llm_providers import melhor_provedor
            melhor = melhor_provedor(cfg)
            if melhor:
                from .llm_providers import REGISTRY
                modelo = str(getattr(cfg, "llm_model", "")
                             or REGISTRY.get(melhor, {}).get("model") or "")
                return melhor, modelo, "roteador automático (chave guardada)"
    except Exception:  # noqa: BLE001
        pass                    # ambiente sem secrets legível → fica local
    return ("local", str(getattr(cfg, "model", "") or ""), "ollama local")


def capacidades(cfg) -> Capacidades:
    """Perfil e portões do cérebro ATIVO (determinístico, sem rede)."""
    provedor, modelo, fonte = cerebro_ativo(cfg)
    override = str(getattr(cfg, "capacidades_perfil", "") or "").strip().lower()
    if override in _NIVEL:
        perfil, fonte = override, "override do config (capacidades_perfil)"
    elif provedor == "local":
        perfil = _perfil_local(modelo)
    else:
        perfil = _perfil_externo(modelo)
    try:
        ctx = int(getattr(cfg, "num_ctx", 8192) or 8192)
    except (TypeError, ValueError):
        ctx = 8192
    portoes = {
        # verificação é ARQUITETURA (sempre existe); o perfil calibra a
        # PROFUNDIDADE — leve: passada única com checklist
        "verificacao_completa": perfil in ("rapido", "forte"),
        # catálogo expandido / skills externas completas
        "skills_avancadas": perfil == "forte",
        # janela que comporta prompts longos (skills densas, PRDs)
        "ctx_longo": ctx >= 32768,
        # integrado via MCP (cua) quando o sandbox P6 existir
        "computer_use": perfil == "forte",
        # cadeias longas sem confirmar cada passo — só com verificação
        "autonomia_estendida": perfil == "forte",
    }
    return Capacidades(perfil, provedor, modelo, ctx, fonte, portoes)


def solicitar_escalada(cfg, tarefa: str, motivo: str = "") -> dict:
    """Pede AVAL do operador para escalar UMA tarefa a um cérebro forte.

    NUNCA silenciosa: devolve o pedido pronto (a entrega no canal do
    operador — Telegram — chega na P4) e NÃO muda cérebro nenhum.
    A tarefa não vaza no log de auditoria (só o tamanho, padrão D2).
    """
    cap = capacidades(cfg)
    if cap.perfil == "forte":
        return {"ok": False,
                "msg": "cérebro ativo já é forte — nada a escalar"}
    pedido = {
        "ok": True,
        "tipo": "escalada",
        "de": cap.perfil,
        "para": "forte",
        "tarefa_chars": len(tarefa or ""),
        "motivo": (motivo or "").strip()[:200],
        "aprovado": None,        # só o OPERADOR decide
        "msg": (f"🔁 ESCALADA SOLICITADA — tarefa crítica com cérebro "
                f"{cap.perfil} ativo ({cap.provedor}/{cap.modelo or '?'}). "
                "Aprovar exige o aval do operador; nada muda sozinho."),
    }
    try:
        from . import activity
        activity.log(cfg, "escalada",
                     f"🔁 solicitada ({cap.perfil}→forte) · tarefa "
                     f"{pedido['tarefa_chars']} chars · aval do operador")
    except Exception:  # noqa: BLE001
        pass
    return pedido
