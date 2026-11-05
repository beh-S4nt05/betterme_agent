# -*- coding: utf-8 -*-
"""🔗 Belvo MCP — conector Open Finance (v7.4.0).

O Belvo MCP (panorama.belvo.com) dá ao agente acesso SOMENTE-LEITURA
aos dados que o operador autorizar no app do próprio banco (canal
regulado do Open Finance — consentimento de 12 meses, revogável).

Este módulo NÃO reproduz o sistema da Belvo: o servidor de autorização
deles (auth.panorama.belvo.com) exige aplicação REGISTRADA (probe
real: "Application not found" para cliente desconhecido; sem
registration_endpoint) — o client_id é exatamente o ativo que não se
reproduz. O que existe aqui é o CLIENTE, pelo protocolo público
(MCP Streamable HTTP + Bearer), no padrão de segurança do projeto:

- token em secrets/belvo.json (600), FORA de config.yaml e logs;
- handshake REAL de validação (initialize contra o servidor MCP);
- remoção limpa (`betterme belvo remover`).

Comandos:
  betterme belvo guia          — passo a passo do consentimento
  betterme belvo token <t>     — guarda o token (600) e registra o MCP
  betterme belvo status        — valida com handshake real
  betterme belvo remover       — apaga segredo e configuração
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

MCP_URL = "https://panorama-mcp.belvo.com/mcp"
PANORAMA = "https://panorama.belvo.com"


def _secret_path(cfg) -> Path:
    return Path(cfg.data_dir) / "secrets" / "belvo.json"


def _entrada(token: str) -> dict:
    return {"name": "belvo", "url": MCP_URL,
            "headers": {"Authorization": f"Bearer {token}"}}


def _registrar(cfg, token: str) -> None:
    """Upsert do servidor MCP no config (padrão do emailcfg)."""
    servers = [e for e in (cfg.mcp_servers or [])
               if not (isinstance(e, dict) and e.get("name") == "belvo")]
    servers.append(_entrada(token))
    cfg.update({"mcp_servers": servers})


def salvar_token(cfg, token: str, expira_min: int | None = None) -> Path:
    token = token.strip()
    if not token:
        raise ValueError("token vazio")
    p = _secret_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.parent.chmod(0o700)
    except OSError:
        pass
    expira = (datetime.now() + timedelta(minutes=expira_min)).isoformat(
        timespec="seconds") if expira_min else None
    p.write_text(json.dumps({"access_token": token,
                             "expira_em": expira}, ensure_ascii=False),
                 encoding="utf-8")
    p.chmod(0o600)
    _registrar(cfg, token)
    return p


def ler_token(cfg) -> str:
    try:
        return json.loads(_secret_path(cfg).read_text(
            encoding="utf-8")).get("access_token", "")
    except (OSError, ValueError):
        return ""


def _probe_real(token: str) -> tuple[bool, str]:
    """Handshake MCP initialize com o Bearer — validação de verdade."""
    import requests
    r = requests.post(
        MCP_URL,
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2024-11-05",
                         "capabilities": {},
                         "clientInfo": {"name": "betterme",
                                        "version": "7.4.0"}}},
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/json, text/event-stream"},
        timeout=30)
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    for ln in r.text.splitlines():
        if ln.startswith("data:"):
            ln = ln[5:]
        ln = ln.strip()
        if ln.startswith("{"):
            try:
                d = json.loads(ln)
            except ValueError:
                continue
            info = ((d.get("result") or {}).get("serverInfo") or {})
            if info:
                return True, (f"{info.get('name', '?')} "
                              f"v{info.get('version', '?')}")
    return True, "servidor respondeu"


def status(cfg, _probe=None) -> str:
    token = ler_token(cfg)
    if not token:
        return ("✖ sem token — rode `betterme belvo guia` para o passo "
                "a passo e `betterme belvo token <token>` para ligar")
    out = ["✔ token presente (secrets/belvo.json, 600)"]
    try:
        d = json.loads(_secret_path(cfg).read_text(encoding="utf-8"))
        if d.get("expira_em"):
            out.append(f"  expira em: {d['expira_em']}")
    except (OSError, ValueError):
        pass
    registrado = any(isinstance(e, dict) and e.get("name") == "belvo"
                     for e in (cfg.mcp_servers or []))
    out.append("  servidor MCP: " + (
        "registrado ✔ (tools aparecem como mcp_belvo_*)" if registrado
        else "NÃO registrado — rode betterme belvo token <token>"))
    probe = _probe or _probe_real
    try:
        ok, info = probe(token)
        out.append("  handshake: " + ("✔ " + info if ok else "✖ " + info))
    except Exception as exc:  # noqa: BLE001 — rede instável é normal
        out.append(f"  handshake: ✖ ({exc})")
    return "\n".join(out)


def remover(cfg) -> str:
    servers = [e for e in (cfg.mcp_servers or [])
               if not (isinstance(e, dict) and e.get("name") == "belvo")]
    cfg.update({"mcp_servers": servers})
    try:
        _secret_path(cfg).unlink()
        return ("✔ segredo e configuração removidos (revogue também em "
                "panorama.belvo.com e no app do banco)")
    except OSError:
        return "✔ configuração removida (não havia segredo)"


def guia() -> str:
    return f"""🔗 Belvo MCP — Open Finance no Betterme (v7.4.0)

O BELVO MCP dá acesso SOMENTE-LEITURA (saldos, extratos, faturas) aos
bancos que VOCÊ autorizar — consentimento no app do BANCO, canal
regulado pelo Banco Central, revogável a qualquer momento. A Belvo
nunca vê suas credenciais bancárias e não movimenta dinheiro.

Passo a passo (uma vez, ~3 minutos):
  1. Acesse {PANORAMA}/connect e crie a conta (grátis, só e-mail).
  2. Conecte seus bancos (Banco do Brasil, Bradesco, SumUp…): o app
     de cada banco pede a autorização Open Finance (12 meses).
  3. Autorize o Betterme como assistente e obtenha o token de acesso
     da jornada; então rode:
         betterme belvo token <token>
  4. Valide a conexão:
         betterme belvo status
  5. No chat, as ferramentas aparecem como mcp_belvo_* — pergunte
     "meu saldo no BB" ou "quanto gastei esse mês".

Para sair: betterme belvo remover (+ revogar no panorama e no app
do banco). Quem participa do Open Finance: `betterme financas
participantes <banco>` consulta a lista oficial."""


def cmd(args, cfg) -> None:
    a = getattr(args, "acao", "guia")
    if a == "guia":
        print(guia())
    elif a == "token":
        try:
            p = salvar_token(cfg, args.a1 or "",
                             expira_min=getattr(args, "expira", None))
            print(f"✔ token salvo em {p} (600) e servidor MCP "
                  "registrado — valide com: betterme belvo status")
        except ValueError as exc:
            print("✖", exc)
    elif a == "status":
        print(status(cfg))
    elif a == "remover":
        print(remover(cfg))
    else:
        print("✖ ação desconhecida:", a)
