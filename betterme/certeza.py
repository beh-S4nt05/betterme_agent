# -*- coding: utf-8 -*-
"""🐴 Camada de certeza — v7.6.0 (conceito ponytail, pedido do
operador).

"Se a IA já souber algo com 100% de certeza, use; se não souber,
pesquise/gera de outra forma." A parte de saber já estava na skill
`caminho-curto` (texto); agora é CÓDIGO: pergunta repetida com
resposta já validada responde com ZERO chamadas ao modelo.

Conservador por desenho (só entra no cache o que é seguro repetir):
- apenas o 1º turno da conversa (pergunta que se sustenta sozinha);
- pergunta de tamanho são (8–80 chars normalizados — saudação não
  é certeza) e SEM palavras voláteis
  (hora, hoje, clima, saldo, preço, versão, gastei…);
- resposta de tamanho são (20–600 chars) e gerada SEM ferramentas
  (o modelo apenas sabia — não consultou nada que muda);
- LRU de 200 entradas + TTL de 30 dias; arquivo local
  `<data_dir>/certezas.json` (nunca no repo).
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from pathlib import Path

_MAX = 200
_TTL_S = 30 * 24 * 3600

# perguntas cuja resposta MUDA com o tempo — nunca cachear
_RE_VOLATIL = re.compile(
    r"\b(hora|horas|data|hoje|ontem|amanha|agora|clima|tempo|chov|"
    r"cotac|preco|valor do|saldo|disponivel|disco|espaco livre|"
    r"memoria|status|versao|versoes|ultima|ultimo|ultimas|ultimos|"
    r"fatura|boleto|gastei|pag[aei]|recebi|quanto (gastei|tenho)|"
    r"pendente|pendente s|agendad)\b", re.I)


def _norm(txt: str) -> str:
    s = unicodedata.normalize("NFKD", str(txt or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _arq(cfg) -> Path:
    return Path(cfg.data_dir) / "certezas.json"


def chave(txt: str) -> str:
    return _norm(txt)


def volatil(txt: str) -> bool:
    return bool(_RE_VOLATIL.search(_norm(txt)))


def cacheavel(msg: str, resposta: str) -> bool:
    n = _norm(msg)
    return (8 <= len(n) <= 80        # "oi"/"bom dia" não é certeza
            and not volatil(n)
            and 20 <= len(str(resposta or "").strip()) <= 600)


def _carregar(cfg) -> dict:
    try:
        return json.loads(_arq(cfg).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _gravar(cfg, dados: dict) -> None:
    p = _arq(cfg)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(dados, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(p)
    except OSError:
        pass                      # cache é otimização, nunca bloqueio


def buscar(cfg, msg: str) -> str | None:
    """Resposta certa já validada, ou None. TTL expirado → limpa."""
    d = _carregar(cfg)
    item = d.get(chave(msg))
    if not item:
        return None
    if time.time() - float(item.get("ts", 0)) > _TTL_S:
        d.pop(chave(msg), None)
        _gravar(cfg, d)
        return None
    return str(item.get("r", "")) or None


def guardar(cfg, msg: str, resposta: str) -> bool:
    """Grava SE (e só se) for seguro repetir. Retorna se gravou."""
    if not cacheavel(msg, resposta):
        return False
    d = _carregar(cfg)
    d[chave(msg)] = {"r": str(resposta).strip(), "ts": time.time()}
    if len(d) > _MAX:                        # LRU: evicta os mais velhos
        for k in sorted(d, key=lambda k: d[k].get("ts", 0))[:len(d) - _MAX]:
            d.pop(k, None)
    _gravar(cfg, d)
    return True


def tamanho(cfg) -> int:
    return len(_carregar(cfg))
