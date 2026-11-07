# -*- coding: utf-8 -*-
"""🔌 Contas — vinculações com serviços externos, num lugar só (v8.5.0).

Pedido do operador: "vinculação com contas externas — Google,
Calendário, etc.". O Pluto JÁ tinha 9 vinculações funcionando, mas
espalhadas em comandos CLI. Este módulo é o REGISTRO UNIFICADO:

- `listar(cfg)` — status de todas (conectado? quais contas?);
- `conectar(cfg, id, campos)` — fluxo nativo: OAuth device (Google
  Calendar/Gmail: código + URL, autoriza no SEU navegador com 2FA),
  token/chave (Telegram, Belvo, n8n, SumUp, provedores IA), caminho
  (vault);
- `estado(cfg, id)` — progresso do OAuth pendente (a GUI mostra o
  código enquanto a thread espera o consentimento);
- `desconectar(cfg, id)` — remove as credenciais (sempre com aviso);
- `testar(cfg, id)` — prova real onde é barato (Telegram getMe,
  Calendar primary, probe Belvo).

Princípios que seguem valendo: credenciais em <data_dir>/secrets/
(600) ou config local — NUNCA no repo, nunca no modelo, nunca em log.
"""
from __future__ import annotations

import threading
from pathlib import Path

# OAuth device em andamento: id → {url, user_code, expires_min,
# done, ok, erro, inicio}
_PENDENTES: dict[str, dict] = {}
_LOCK = threading.Lock()


# ── status por vinculação ───────────────────────────────────────
def _st_calendar(cfg) -> dict:
    from . import agendacfg as A
    data = A.load(cfg)
    accs = data.get("accounts", [])
    return {"ok": bool(accs),
            "contas": [a.get("user", "?") for a in accs],
            "detalhe": ("escrita liberada" if accs and A._pode_escrever(accs[0])
                        else "somente leitura (pré-v8.5.0)" if accs
                        else "nenhuma conta Google conectada")}


def _st_gmail(cfg) -> dict:
    from . import emailcfg
    accs = emailcfg.load(cfg).get("accounts", [])
    return {"ok": bool(accs),
            "contas": [a.get("user", "?") for a in accs],
            "detalhe": (f"{len(accs)} conta(s) — envio: "
                        + ("sim" if any(not a.get("readonly", True)
                                        for a in accs) else "não"))}


def _st_telegram(cfg) -> dict:
    from . import telegram_gw
    tok = telegram_gw.token(cfg)
    return {"ok": bool(tok), "contas": ["bot"] if tok else [],
            "detalhe": "bot com token válido" if tok
            else "sem token — crie o bot com @BotFather"}


def _st_whatsapp(cfg) -> dict:
    from . import whatsapp_gw
    ok = whatsapp_gw.playwright_ok() and whatsapp_gw.perfil_dir(cfg).exists()
    return {"ok": ok, "contas": ["sessão"] if ok else [],
            "detalhe": ("sessão ativa" if ok else
                        "vincula por QR Code no terminal: "
                        "pluto whatsapp start")}


def _st_sumup(cfg) -> dict:
    from .llm_providers import api_key
    ok = bool(api_key(cfg, "sumup"))
    return {"ok": ok, "contas": ["titular"] if ok else [],
            "detalhe": "API de titular (vendas → finanças)" if ok
            else "sem chave — Developers no app SumUp"}


def _st_belvo(cfg) -> dict:
    from . import belvo
    ok = bool(belvo.ler_token(cfg))
    return {"ok": ok, "contas": ["API"] if ok else [],
            "detalhe": "hook pronto p/ Open Finance (B2B)" if ok
            else "sem token — exige conta Belvo"}


def _st_ia(cfg) -> dict:
    from .llm_providers import REGISTRY, api_key
    com = [p for p in REGISTRY if api_key(cfg, p)]
    return {"ok": bool(com), "contas": com,
            "detalhe": (f"{len(com)} de {len(REGISTRY)} com chave"
                        if com else "nenhuma chave salva "
                        "(pluto provider set <nome>)")}


def _st_n8n(cfg) -> dict:
    from . import fluxos
    ok = bool(fluxos.ler_apikey(cfg))
    return {"ok": ok, "contas": ["instância local"] if ok else [],
            "detalhe": "editor local de automações" if ok
            else "sem chave — n8n local → Settings → API"}


def _st_vault(cfg) -> dict:
    v = str(getattr(cfg, "vault_dir", "") or "")
    ok = bool(v) and Path(v).expanduser().is_dir()
    return {"ok": ok, "contas": [v] if ok else [],
            "detalhe": "memória externa em .md (Obsidian)" if ok
            else "sem vault configurado"}


# ── catálogo (ordem = ordem na página) ──────────────────────────
CATALOGO = [
    {"id": "google_calendar", "nome": "Google Calendar", "icone": "📅",
     "categoria": "Google", "tipo": "oauth_device",
     "campos": [("user", "e-mail da conta Google"),
                ("client_id", "client_id (console.cloud.google.com)"),
                ("client_secret", "client_secret (Google exige)")],
     "status": _st_calendar,
     "nota": "app OAuth 'TV e dispositivos de entrada limitada'. "
             "v8.5.0: leitura E criação de eventos (calendar.events)."},
    {"id": "gmail", "nome": "Gmail / E-mail", "icone": "✉️",
     "categoria": "Google", "tipo": "oauth_device",
     "campos": [("user", "e-mail da conta"),
                ("provedor", "google|microsoft"),
                ("client_id", "client_id do aplicativo"),
                ("client_secret", "client_secret (se exigir)")],
     "status": _st_gmail,
     "nota": "OAuth device (2FA normal, sem senha aqui). Leitura por "
             "padrão; envio você libera depois (pluto email modo)."},
    {"id": "telegram", "nome": "Telegram", "icone": "✈️",
     "categoria": "Mensageria", "tipo": "token",
     "campos": [("token", "token do @BotFather")],
     "status": _st_telegram,
     "nota": "o bot fala com você de qualquer lugar."},
    {"id": "whatsapp", "nome": "WhatsApp", "icone": "💬",
     "categoria": "Mensageria", "tipo": "cli",
     "campos": [],
     "status": _st_whatsapp,
     "nota": "vinculação por QR Code — precisa do terminal: "
             "pluto whatsapp start"},
    {"id": "sumup", "nome": "SumUp", "icone": "💳",
     "categoria": "Financeiro", "tipo": "api_key",
     "campos": [("key", "API key de titular")],
     "status": _st_sumup,
     "nota": "vendas sincronizam como entradas nas Finanças."},
    {"id": "belvo", "nome": "Belvo (Open Finance)", "icone": "🏦",
     "categoria": "Financeiro", "tipo": "token",
     "campos": [("token", "token da API Belvo")],
     "status": _st_belvo,
     "nota": "exige conta B2B no Belvo — o hook já está pronto."},
    {"id": "ia", "nome": "Provedores IA (cérebro rápido)", "icone": "🧠",
     "categoria": "Inteligência", "tipo": "api_key_multi",
     "campos": [("provedor", "groq|mistral|gemini|…"),
                ("key", "chave da API")],
     "status": _st_ia,
     "nota": "chaves ficam em secrets/ (600); memória NUNCA sai (D2)."},
    {"id": "n8n", "nome": "n8n (automações)", "icone": "⛓",
     "categoria": "Integração", "tipo": "api_key",
     "campos": [("key", "API key do n8n local")],
     "status": _st_n8n,
     "nota": "editor local de fluxos: /fluxos na GUI."},
    {"id": "vault", "nome": "Vault Obsidian", "icone": "🗄",
     "categoria": "Memória", "tipo": "path",
     "campos": [("caminho", "caminho da pasta do vault")],
     "status": _st_vault,
     "nota": "memória de longo prazo em .md com escopos."},
]
_POR_ID = {v["id"]: v for v in CATALOGO}


def listar(cfg) -> list[dict]:
    out = []
    for v in CATALOGO:
        st = v["status"](cfg)
        out.append({"id": v["id"], "nome": v["nome"], "icone": v["icone"],
                    "categoria": v["categoria"], "tipo": v["tipo"],
                    "campos": [{"chave": c, "rotulo": r}
                               for c, r in v["campos"]],
                    "nota": v["nota"], **st})
    return out


# ── OAuth device (thread + estado p/ a GUI) ─────────────────────
def _rodar_device(vinculo_id: str, alvo) -> None:
    with _LOCK:
        _PENDENTES[vinculo_id] = {"pendente": True, "done": False,
                                  "ok": False, "erro": "", "url": "",
                                  "user_code": ""}
    def _on_code(url, code, expires_min):
        with _LOCK:
            _PENDENTES[vinculo_id].update(
                {"url": url, "user_code": code, "expires_min": expires_min})
    try:
        alvo(_on_code)
        with _LOCK:
            _PENDENTES[vinculo_id].update({"done": True, "ok": True})
    except Exception as exc:  # noqa: BLE001 — a GUI precisa do erro
        with _LOCK:
            _PENDENTES[vinculo_id].update(
                {"done": True, "ok": False, "erro": str(exc)[:300]})


def _iniciar_device(vinculo_id: str, alvo) -> dict:
    th = threading.Thread(target=_rodar_device,
                          args=(vinculo_id, alvo), daemon=True)
    th.start()
    return {"pendente": True,
            "msg": "autorize no navegador — o código aparece aqui"}


def estado(vinculo_id: str) -> dict:
    with _LOCK:
        st = dict(_PENDENTES.get(vinculo_id) or {})
    return st or {"pendente": False}


# ── conectar / desconectar / testar ─────────────────────────────
def conectar(cfg, vinculo_id: str, campos: dict) -> dict:
    v = _POR_ID.get(vinculo_id)
    if not v:
        return {"erro": f"vinculação desconhecida: {vinculo_id}"}
    c = {str(k).strip(): str(val).strip() for k, val in (campos or {}).items()}

    if vinculo_id == "google_calendar":
        if not c.get("user") or not c.get("client_id"):
            return {"erro": "informe user e client_id"}
        from . import agendacfg as A
        return _iniciar_device(
            vinculo_id,
            lambda on_code: A.add_account(
                cfg, c["user"], c["client_id"],
                c.get("client_secret", ""), print_fn=lambda *a: None,
                on_code=on_code))

    if vinculo_id == "gmail":
        if not c.get("user") or not c.get("client_id"):
            return {"erro": "informe user e client_id"}
        prov = (c.get("provedor") or "google").lower()
        if prov not in ("google", "microsoft"):
            return {"erro": "provedor deve ser google ou microsoft"}
        from . import emailcfg
        return _iniciar_device(
            vinculo_id,
            lambda on_code: emailcfg.add_oauth_account(
                cfg, c["user"], prov, c["client_id"],
                c.get("client_secret", ""), print_fn=lambda *a: None,
                on_code=on_code))

    if vinculo_id == "telegram":
        if not c.get("token"):
            return {"erro": "informe o token do bot"}
        from . import telegram_gw
        telegram_gw.salvar_token(cfg, c["token"])
        return {"ok": True, "msg": "token salvo — rode pluto telegram start"}

    if vinculo_id == "whatsapp":
        return {"erro": "WhatsApp vincula por QR Code no terminal — "
                        "rode: pluto whatsapp start"}

    if vinculo_id == "sumup":
        if not c.get("key"):
            return {"erro": "informe a API key"}
        from . import financas as FIN
        return {"ok": True, "msg": FIN.setup_sumup(cfg, c["key"])}

    if vinculo_id == "belvo":
        if not c.get("token"):
            return {"erro": "informe o token"}
        from . import belvo
        belvo.salvar_token(cfg, c["token"])
        return {"ok": True, "msg": "token Belvo salvo"}

    if vinculo_id == "ia":
        prov, key = c.get("provedor", "").lower(), c.get("key", "")
        from .llm_providers import REGISTRY, salvar_key
        if prov not in REGISTRY:
            return {"erro": f"provedor inválido — use: "
                            f"{'|'.join(sorted(REGISTRY))}"}
        if not key:
            return {"erro": "informe a chave"}
        salvar_key(cfg, prov, key)
        return {"ok": True, "msg": f"chave {prov} salva"}

    if vinculo_id == "n8n":
        if not c.get("key"):
            return {"erro": "informe a API key"}
        from . import fluxos
        fluxos.salvar_apikey(cfg, c["key"])
        return {"ok": True, "msg": "API key n8n salva"}

    if vinculo_id == "vault":
        caminho = c.get("caminho", "")
        p = Path(caminho).expanduser() if caminho else None
        if not p or not p.is_dir():
            return {"erro": f"pasta não encontrada: {caminho}"}
        cfg.update({"vault_dir": str(p)})
        return {"ok": True, "msg": f"vault: {p}"}

    return {"erro": "vinculação sem fluxo de conexão"}


def desconectar(cfg, vinculo_id: str) -> dict:
    v = _POR_ID.get(vinculo_id)
    if not v:
        return {"erro": f"vinculação desconhecida: {vinculo_id}"}
    if vinculo_id == "google_calendar":
        from . import agendacfg as A
        A.save(cfg, {"accounts": [], "default": None})
    elif vinculo_id == "gmail":
        from . import emailcfg
        emailcfg.save(cfg, {"accounts": []})
    elif vinculo_id == "telegram":
        from . import telegram_gw
        telegram_gw.salvar_token(cfg, "")
    elif vinculo_id == "whatsapp":
        import shutil
        from . import whatsapp_gw
        shutil.rmtree(whatsapp_gw.perfil_dir(cfg), ignore_errors=True)
    elif vinculo_id == "sumup":
        from .llm_providers import salvar_key
        salvar_key(cfg, "sumup", "")
    elif vinculo_id == "belvo":
        from . import belvo
        belvo.remover(cfg)
    elif vinculo_id == "ia":
        from .llm_providers import REGISTRY, api_key, salvar_key
        for prov in [p for p in REGISTRY if api_key(cfg, p)]:
            salvar_key(cfg, prov, "")
    elif vinculo_id == "n8n":
        from . import fluxos
        fluxos.salvar_apikey(cfg, "")
    elif vinculo_id == "vault":
        cfg.update({"vault_dir": ""})
    with _LOCK:
        _PENDENTES.pop(vinculo_id, None)
    return {"ok": True, "msg": f"{v['nome']} desconectado"}


def testar(cfg, vinculo_id: str) -> dict:
    """Prova REAL onde é barato; nos demais, status honesto."""
    v = _POR_ID.get(vinculo_id)
    if not v:
        return {"erro": f"vinculação desconhecida: {vinculo_id}"}
    if vinculo_id == "telegram":
        from . import telegram_gw
        tok = telegram_gw.token(cfg)
        if not tok:
            return {"ok": False, "erro": "sem token"}
        try:
            import json as _json
            import urllib.request as _rq
            req = _rq.Request(
                f"https://api.telegram.org/bot{tok}/getMe")
            with _rq.urlopen(req, timeout=15) as r:
                d = _json.loads(r.read().decode())
            nome = (d.get("result") or {}).get("username", "bot")
            return {"ok": True, "msg": f"bot @{nome} respondeu"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "erro": str(exc)[:200]}
    if vinculo_id == "google_calendar":
        from . import agendacfg as A
        data = A.load(cfg)
        if not data.get("accounts"):
            return {"ok": False, "erro": "nenhuma conta"}
        try:
            cal = A._api_get(data["accounts"][0], "/calendars/primary")
            return {"ok": True,
                    "msg": f"calendário “{cal.get('summary', '?')}” acessível"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "erro": str(exc)[:200]}
    if vinculo_id == "belvo":
        from . import belvo
        tok = belvo.ler_token(cfg)
        if not tok:
            return {"ok": False, "erro": "sem token"}
        ok, detalhe = belvo._probe_real(tok)
        return {"ok": ok, "msg": detalhe} if ok else {"ok": False,
                                                      "erro": detalhe}
    st = v["status"](cfg)
    return {"ok": st["ok"], "msg": st["detalhe"]}
