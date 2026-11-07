"""Configuração da Agenda (Google Calendar) — leitura E escrita.

v8.5.0 — REVERSÃO de decisão documentada: até a v8.4.x o módulo era
SOMENTE LEITURA (escopo único calendar.readonly; nenhuma ferramenta
escrevia). A pedido do operador ("vinculação com contas externas" +
liberar criação/edição), o escopo passou a ser calendar.events e a
tool nativa `agenda_criar` cria eventos. Limites que SEGUEM valendo:
- APENAS CRIAÇÃO de eventos (POST) — nada de apagar/mover em lote;
- contas vinculadas antes da v8.5.0 continuam calendar.readonly: para
  escrever, reconecte a conta (o escopo novo pede novo consentimento);
- credenciais (refresh_token) em <data_dir>/secrets/agenda.json (600,
  fora do workspace), lidas DIRETO pelo servidor MCP e pela tool —
  nunca passam pelo modelo, nunca aparecem em logs, auditoria ou
  respostas.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

from .emailcfg import OAUTH_PROVIDERS, oauth_device_flow, refresh_access_token

CAL_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
# v8.5.0: leitura + criação/edição de EVENTOS (sem tocar calendários)
CAL_SCOPE_RW = "https://www.googleapis.com/auth/calendar.events"
API_BASE = "https://www.googleapis.com/calendar/v3"


def secrets_path(cfg) -> Path:
    return cfg.data_dir / "secrets" / "agenda.json"


def load(cfg) -> dict:
    p = secrets_path(cfg)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("accounts"), list):
            return data
    except (OSError, ValueError):
        pass
    return {"accounts": [], "default": None}


def save(cfg, data: dict) -> None:
    p = secrets_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(p.parent, 0o700)
    except OSError:
        pass
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


def _api_get(acc: dict, path: str, params: dict | None = None,
            api_base: str = "") -> dict:
    """GET autenticado na API do Calendar (único verbo usado — leitura)."""
    token = refresh_access_token(acc)
    url = (api_base or API_BASE) + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            detalhe = exc.read().decode(errors="replace")[:160]
        except Exception:  # noqa: BLE001
            detalhe = str(exc)
        raise RuntimeError(f"Calendar API HTTP {exc.code}: {detalhe}") from exc


def _api_send(acc: dict, path: str, body: dict) -> dict:
    """POST autenticado na API do Calendar (v8.5.0: criar evento)."""
    token = refresh_access_token(acc)
    req = urllib.request.Request(
        API_BASE + path, data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            detalhe = exc.read().decode(errors="replace")[:200]
        except Exception:  # noqa: BLE001
            detalhe = str(exc)
        raise RuntimeError(f"Calendar API HTTP {exc.code}: {detalhe}") from exc


def _pode_escrever(acc: dict) -> bool:
    """Conta com escopo de escrita? (readonly antigo → aviso honesto)"""
    return "calendar.events" in (acc.get("oauth_scopes") or "")


def criar_evento(cfg, account: str, titulo: str, inicio: str,
                 fim: str = "", descricao: str = "", local: str = "",
                 convidados: list | None = None) -> dict:
    """v8.5.0: cria um evento no calendário primary da conta.

    inicio/fim: 'AAAA-MM-DD HH:MM' (horário) ou 'AAAA-MM-DD' (dia
    inteiro). Sem fim → +1h (horário) ou +1 dia (inteiro)."""
    data = load(cfg)
    acc = next((a for a in data["accounts"]
                if a.get("id") == account or a.get("user") == account),
               None)
    if acc is None:
        return {"erro": f"agenda '{account}' não encontrada — veja: "
                        "pluto agenda status"}
    if not _pode_escrever(acc):
        return {"erro": f"a conta {acc.get('user')} foi vinculada no modo "
                        "somente leitura (antes da v8.5.0) — reconecte-a "
                        "na página Contas para liberar a escrita"}

    def _offset_local() -> str:
        import time as _t
        o = _t.strftime("%z")                 # ex.: -0400 (fuso da MÁQUINA)
        return (o[:3] + ":" + o[3:]) if o else "-04:00"

    def _parse(txt: str):
        txt = str(txt or "").strip().replace("T", " ")
        try:
            if len(txt) == 10:                     # só data → dia inteiro
                d = datetime.strptime(txt, "%Y-%m-%d")
                return ("date", d.strftime("%Y-%m-%d"))
            d = datetime.strptime(txt[:16], "%Y-%m-%d %H:%M")
            return ("dateTime",
                    d.strftime("%Y-%m-%dT%H:%M:00") + _offset_local())
        except ValueError as exc:
            raise ValueError(
                f"data/hora inválida: {txt!r} (use AAAA-MM-DD HH:MM "
                "ou AAAA-MM-DD)") from exc

    tipo_i, val_i = _parse(inicio)
    if fim:
        tipo_f, val_f = _parse(fim)
        if tipo_i != tipo_f:              # início dia inteiro + fim com hora
            tipo_f, val_f = ("date", val_f[:10])
    else:
        if tipo_i == "date":
            fim_dt = datetime.strptime(val_i, "%Y-%m-%d") + timedelta(days=1)
            tipo_f, val_f = "date", fim_dt.strftime("%Y-%m-%d")
        else:
            ini_dt = datetime.strptime(val_i[:19], "%Y-%m-%dT%H:%M:%S")
            fim_dt = ini_dt + timedelta(hours=1)
            tipo_f, val_f = ("dateTime",
                             fim_dt.strftime("%Y-%m-%dT%H:%M:00")
                             + _offset_local())
    body = {"summary": str(titulo)[:200],
            "start": {tipo_i: val_i}, "end": {tipo_f: val_f}}
    if descricao:
        body["description"] = str(descricao)[:2000]
    if local:
        body["location"] = str(local)[:300]
    if convidados:
        body["attendees"] = [{"email": e} for e in convidados[:20]]
    ev = _api_send(acc, "/calendars/primary/events", body)
    return {"ok": True, "id": ev.get("id", ""),
            "link": ev.get("htmlLink", ""),
            "resumo": fmt_event(ev)}


def fmt_event(ev: dict) -> str:
    """Uma linha legível: 📅 18/10 14:00–15:00 · Título — 📍 Local · 3 participantes."""
    s = ev.get("start") or {}
    e = ev.get("end") or {}
    try:
        if s.get("dateTime"):
            d1 = datetime.fromisoformat(s["dateTime"])
            d2 = datetime.fromisoformat(e["dateTime"]) if e.get("dateTime") else d1
            quando = d1.strftime("%d/%m %H:%M")
            quando += ("–" + d2.strftime("%H:%M") if d2.date() == d1.date()
                       else "–" + d2.strftime("%d/%m %H:%M"))
        elif s.get("date"):
            quando = date.fromisoformat(s["date"]).strftime("%d/%m") + " (dia inteiro)"
        else:
            quando = "(horário?)"
    except Exception:  # noqa: BLE001
        quando = "(horário?)"
    titulo = ev.get("summary") or "(sem título)"
    extra = []
    if ev.get("location"):
        extra.append("📍 " + str(ev["location"])[:60])
    if ev.get("hangoutLink"):
        extra.append("🎥 reunião online")
    n = len(ev.get("attendees") or [])
    if n:
        extra.append(f"{n} participante(s)")
    return f"📅 {quando} · {titulo}" + (" — " + " · ".join(extra) if extra else "")


def list_events(cfg, account: str | None = None, dias: int = 7,
                limit: int = 20, a_partir_de_agora: bool = False) -> str:
    """Lista eventos (somente leitura) de uma conta da agenda."""
    data = load(cfg)
    accs = data.get("accounts") or []
    if not accs:
        raise RuntimeError("nenhuma agenda configurada — rode: pluto agenda oauth")
    acc = accs[0]
    if account:
        for a in accs:
            if a.get("id") == account or a.get("user") == account:
                acc = a
                break
        else:
            raise RuntimeError(f"agenda '{account}' não encontrada — veja: pluto agenda status")
    params = {"singleEvents": "true", "orderBy": "startTime",
              "maxResults": max(1, min(int(limit), 50))}
    agora = datetime.now().astimezone()
    if a_partir_de_agora:
        params["timeMin"] = agora.isoformat()
    else:
        hoje0 = agora.replace(hour=0, minute=0, second=0, microsecond=0)
        params["timeMin"] = hoje0.isoformat()
        params["timeMax"] = (hoje0 + timedelta(days=max(1, int(dias)))).isoformat()
    resp = _api_get(acc, "/calendars/primary/events", params)
    itens = [e for e in (resp.get("items") or [])
             if e.get("status") != "cancelled"]
    if not itens:
        return f"agenda de {acc.get('user')}: nenhum evento no período"
    cab = (f"🗓 eventos a partir de agora — {acc.get('user')} "
           f"({len(itens)}):" if a_partir_de_agora else
           f"🗓 próximos {dias} dia(s) — {acc.get('user')} ({len(itens)}):")
    return cab + "\n" + "\n".join(fmt_event(e) for e in itens)


def add_account(cfg, user: str, client_id: str, client_secret: str = "",
                print_fn=print, on_code=None) -> tuple[dict, str]:
    """Adiciona a agenda de uma conta Google via device code (2FA do
    provedor, sem senha). v8.5.0: escopo calendar.events (leitura E
    escrita — reversão da decisão somente-leitura a pedido do
    operador; ver docstring do módulo)."""
    import time as _time
    tok = oauth_device_flow("google", client_id, client_secret, print_fn,
                            scopes=CAL_SCOPE_RW, on_code=on_code)
    acc = {
        "id": (user.split("@")[0].replace(".", "_") + "_gcal").lower()[:24],
        "user": user, "provider": "google",
        "client_id": client_id, "client_secret": client_secret,
        "refresh_token": tok["refresh_token"],
        "oauth_scopes": CAL_SCOPE_RW,
        "token_endpoint": OAUTH_PROVIDERS["google"]["token_endpoint"],
        "access_token": tok.get("access_token"),
        "token_expires": _time.time() + int(tok.get("expires_in", 3600)) - 120,
    }
    cal = _api_get(acc, "/calendars/primary")
    data = load(cfg)
    data["accounts"] = [a for a in data["accounts"] if a.get("id") != acc["id"]] + [acc]
    if not data.get("default"):
        data["default"] = acc["id"]
    save(cfg, data)
    register_mcp(cfg)
    return acc, (f"Agenda OK — “{cal.get('summary') or user}” ({user}) · "
                 f"escopo {CAL_SCOPE_RW} (leitura e escrita de eventos)")


def register_mcp(cfg) -> None:
    """Registra o servidor MCP 'agenda' (secrets via env — nada no config)."""
    script = Path(__file__).resolve().parent.parent / "mcp-servers" / "agenda_server.py"
    env = {"PLUTO_AGENDA_SECRETS": str(secrets_path(cfg))}
    _api = (os.environ.get("PLUTO_AGENDA_API")          # v8.3.0: legado
            or os.environ.get("BETTERME_AGENDA_API"))    # BETTERME_* vale
    if _api:  # teste/diagnóstico: API falsa
        env["PLUTO_AGENDA_API"] = _api
    entry = {
        "name": "agenda",
        "command": sys.executable or "python3",
        "args": [str(script)],
        "env": env,
    }
    servers = [s for s in (cfg.mcp_servers or [])
               if not (isinstance(s, dict) and s.get("name") == "agenda")]
    servers.append(entry)
    cfg.update({"mcp_servers": servers})


def status(cfg) -> dict:
    data = load(cfg)
    return {
        "secrets_file": str(secrets_path(cfg)),
        "exists": secrets_path(cfg).exists(),
        "mode": oct(stat.S_IMODE(secrets_path(cfg).stat().st_mode))
                if secrets_path(cfg).exists() else None,
        "accounts": [{"id": a.get("id"), "user": a.get("user"),
                      "provider": a.get("provider", "google"),
                      "scope": a.get("oauth_scopes", CAL_SCOPE)}
                     for a in data.get("accounts", [])],
        "default": data.get("default"),
        "mcp_registered": any(isinstance(s, dict) and s.get("name") == "agenda"
                              for s in (cfg.mcp_servers or [])),
    }


def setup_interactive(cfg) -> None:
    """`pluto agenda oauth` — assistente device code (uma vez por conta)."""
    import getpass

    print("\n🗓 Agenda Google — acesso SOMENTE LEITURA (visualizar eventos)")
    print("─" * 56)
    print("  O que o agente ganha: listar/ler seus eventos (hoje, próximos")
    print("  dias, próximo compromisso). O que ele NUNCA faz: criar, mover")
    print("  ou apagar — o escopo OAuth é 'calendar.readonly' e não existe")
    print("  ferramenta de escrita no servidor.")
    print("  O refresh_token fica em:", secrets_path(cfg), "(600, fora do workspace)")
    print("─" * 56)
    print("  ⚠ Requer um client_id Google (uma vez; o MESMO do e-mail serve):")
    print("    console.cloud.google.com → APIs e serviços → Credenciais →")
    print("    'Criar credenciais' → 'ID do cliente OAuth' → tipo")
    print("    'App para TV e dispositivos de entrada limitada'.")
    while True:
        user = input("\n  e-mail da conta Google (vazio encerra): ").strip()
        if not user:
            break
        client_id = input("  client_id: ").strip()
        client_secret = getpass.getpass("  client_secret (não aparece): ").strip()
        if not (user and client_id and client_secret):
            print("  ✖ dados incompletos")
            continue
        try:
            acc, report = add_account(cfg, user, client_id, client_secret)
        except (ValueError, TimeoutError, RuntimeError) as exc:
            print(f"  ✖ {exc}")
            continue
        print(f"  ✔ agenda '{acc['id']}' salva — {report}")
    st = status(cfg)
    if st["accounts"]:
        print("\n  agendas configuradas:")
        for a in st["accounts"]:
            marca = " (padrão)" if a["id"] == st["default"] else ""
            print(f"    · {a['user']} [{a['id']}]{marca} — {a['scope']}")
        print(f"\n  servidor MCP 'agenda' registrado: {'sim' if st['mcp_registered'] else 'NÃO'}")
        print("  reinicie o `pluto server` e peça, por exemplo:")
        print('    "o que tenho na agenda hoje?" ou "qual meu próximo compromisso?"')
    else:
        print("\n  nenhuma agenda configurada.")
