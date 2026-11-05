# -*- coding: utf-8 -*-
"""💰 Finanças — livro-caixa local (v7.3.0, pedido do operador).

Controle de gastos/entradas de PF e PJ com os meios que existem de
verdade: API de titular (SumUp), extratos CSV (BB, Bradesco, SumUp),
registro manual (chat/WhatsApp) e faturas a vencer — tudo num
livro-caixa LOCAL (`<data_dir>/financas/`), nunca no repo.

Princípios duros (herdados do projeto):
- Números com Decimal — a ferramenta calcula; LLM nunca soma na mão.
- Segredo (API key do SumUp) em secrets/ 600 (helpers de
  llm_providers), FORA de config/logs; a denylist protege o caminho.
- Dedup por id estável: importar/sincronizar 2× não duplica NADA
  (id = hash de data+valor+descrição+conta; SumUp = id da transação).
- Extrato CSV do SumUp + sync da API dobra as entradas? → importe
  com --so-saidas (o importar avisa quando detectar o risco).
- Parsers determinísticos por FAMÍLIAS de coluna (header muda com
  idioma/país — família aceita, lista fechada não).
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

BASE_SUMUP = "https://api.sumup.com"

# ── categorias por palavra-chave (normalizado: sem acento/minúsculo)
_CATEGORIAS = [
    ("mercado", ["mercado", "supermercado", "atacad", "hortifruti",
                 "hortifrut"]),
    ("alimentacao", ["ifood", "restaurante", "restaur", "lanche", "lanch",
                     "padaria", "padari", "cafe", "pizzaria", "bar ",
                     "almoço", "almoco", "jantar"]),
    ("transporte", ["uber", "99 app", "combustivel", "combust", "posto",
                    "estacion", "pedagio", "pedag", "taxi", "onibus",
                    "uber "]),
    ("casa", ["aluguel", "alug", "energia", "luz ", "eletric", "agua",
              "internet", "gas ", "condominio", "condomin", "net ", "vivo ",
              "claro ", "oi "]),
    ("saude", ["farmacia", "farmac", "drogaria", "drogar", "medicamento",
               "medic", "hospital", "consulta", "dentista", "dentist",
               "plano de saude", "unimed", "amil"]),
    ("lazer", ["netflix", "spotify", "streaming", "cinema", "jogo", "game",
               "show ", "teatro"]),
    ("servicos", ["assinatura", "seguro", "plano", "servico", "taxa",
                  "tarifa", "boleto", "mensalidade"]),
    ("educacao", ["curso", "livraria", "livro", "escola", "faculdade",
                  "udemy", "alura"]),
]


def _dir(cfg) -> Path:
    return Path(cfg.data_dir) / "financas"


def _arquivo(cfg) -> Path:
    return _dir(cfg) / "lancamentos.jsonl"


def _arquivo_faturas(cfg) -> Path:
    return _dir(cfg) / "faturas.jsonl"


def _norm(txt: str) -> str:
    s = unicodedata.normalize("NFKD", str(txt or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _br(d: Decimal) -> str:
    s = f"{d:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _moeda(txt) -> Decimal:
    """'R$ 1.234,56' / '-1234.56' / '35,00' → Decimal (sinal preservado)."""
    s = re.sub(r"[R$\s]", "", str(txt)).strip()
    neg = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    s = s.strip("-()")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    else:
        p = s.split(".")
        if len(p) == 2 and len(p[1]) == 3:      # 1.234 → milhar
            s = s.replace(".", "")
    try:
        d = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"valor inválido: {txt!r}") from exc
    return -d if neg else d


def _data(txt) -> date:
    s = str(txt or "").strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"data inválida: {txt!r} (use dd/mm/aaaa)")


def _id_de(chave: str) -> str:
    return hashlib.sha1(chave.encode("utf-8")).hexdigest()[:16]


def categorizar(descricao: str) -> str:
    d = _norm(descricao)
    for cat, chaves in _CATEGORIAS:
        if any(k in d for k in chaves):
            return cat
    return "outros"


# ── lançamentos ────────────────────────────────────────────────
def _todos(cfg) -> list[dict]:
    try:
        linhas = _arquivo(cfg).read_text(
            encoding="utf-8").splitlines()
        return [json.loads(l) for l in linhas if l.strip()]
    except OSError:
        return []


def lancar(cfg, valor, descricao: str, categoria: str = "",
           tipo: str = "saida", conta: str = "manual", quando: str | None = None,
           fonte: str = "manual", _id: str | None = None) -> dict:
    """Lança no livro-caixa. `_id` dado → dedup (import/sync);
    sem `_id` → id aleatório (registros manuais podem repetir)."""
    v = _moeda(valor)
    if v <= 0:
        raise ValueError("valor deve ser positivo (use tipo entrada/saida)")
    if tipo not in ("entrada", "saida"):
        raise ValueError("tipo deve ser 'entrada' ou 'saida'")
    q = (_data(quando) if quando else date.today()).isoformat()
    cat = categoria or (categorizar(descricao) if tipo == "saida"
                        else "entrada")
    novo_id = _id_de(_id) if _id else uuid.uuid4().hex[:16]
    if _id:
        if any(l["id"] == novo_id for l in _todos(cfg)):
            return {"id": novo_id, "novo": False, "duplicado": True}
    reg = {"id": novo_id, "quando": q, "valor": str(v), "tipo": tipo,
           "categoria": cat, "descricao": str(descricao)[:120],
           "conta": conta, "fonte": fonte}
    _dir(cfg).mkdir(parents=True, exist_ok=True)
    with _arquivo(cfg).open("a", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")
    return {"id": novo_id, "novo": True, **reg}


# ── importação de extrato CSV ──────────────────────────────────
_FAM = {
    "data": ("data", "date"),
    "descricao": ("historico", "descr", "lancamento", "descricao",
                  "detalhe", "title", "memo"),
    "valor": ("valor", "amount", "montant"),
    "credito": ("credito", "credit", "entrada"),
    "debito": ("debito", "debit", "saida"),
}


def _familia(header: str) -> str | None:
    h = _norm(header)
    if "saldo" in h:
        return None
    for fam, chaves in _FAM.items():
        if any(ch in h for ch in chaves):
            return fam
    return None


def importar_csv(cfg, caminho: str, conta: str = "extrato",
                 so_saidas: bool = False) -> dict:
    """Extrato CSV → lançamentos. Detecta delimitador (; , tab) e
    formato por FAMÍLIA de coluna: 'Valor' assinado OU colunas
    'Crédito'/'Débito' separadas (Bradesco). Dedup por id estável."""
    try:
        texto = Path(caminho).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        texto = Path(caminho).read_text(encoding="latin-1")
    linhas = [l for l in texto.splitlines() if l.strip()]
    if len(linhas) < 2:
        return {"erro": "arquivo sem lançamentos"}
    delim = ";" if linhas[0].count(";") >= max(
        linhas[0].count(","), linhas[0].count("\t")) else (
        "," if linhas[0].count(",") >= linhas[0].count("\t") else "\t")

    import csv as _csv
    leitor = list(_csv.reader(linhas, delimiter=delim))
    mapa: dict[str, int] = {}
    for i, cel in enumerate(leitor[0]):
        fam = _familia(cel)
        if fam and fam not in mapa:
            mapa[fam] = i
    if "data" not in mapa or not ({"valor", "credito"} & set(mapa)):
        return {"erro": f"formato não reconhecido — colunas lidas: "
                        f"{leitor[0]!r}", "colunas": leitor[0]}

    novos, dup, ign = [], 0, 0
    for row in leitor[1:]:
        try:
            if len(row) <= max(mapa.values()):
                continue
            q = _data(row[mapa["data"]])
            desc = (row[mapa["descricao"]]
                    if "descricao" in mapa else "extrato")
            if "credito" in mapa and "debito" in mapa:
                cred = _moeda(row[mapa["credito"]] or 0)
                deb = _moeda(row[mapa["debito"]] or 0)
                if cred:
                    v, tp = abs(cred), "entrada"
                elif deb:
                    v, tp = abs(deb), "saida"   # pode vir com sinal (abs)
                else:
                    ign += 1
                    continue
            else:
                v = _moeda(row[mapa["valor"]])
                tp = "entrada" if v > 0 else "saida"
                v = abs(v)
            if so_saidas and tp == "entrada":
                ign += 1
                continue
            r = lancar(cfg, v, desc, tipo=tp, conta=conta, quando=q,
                       fonte="csv",
                       _id=f"{q}|{v}|{desc[:60]}|{conta}|{tp}")
            (novos if r.get("novo") else None)
            if r.get("novo"):
                novos.append(r["id"])
            else:
                dup += 1
        except (ValueError, KeyError):
            ign += 1
            continue
    res = {"novos": len(novos), "duplicados": dup, "ignorados": ign,
           "conta": conta}
    if conta == "sumup" and not so_saidas and any(
            l["fonte"] == "sumup" for l in _todos(cfg)):
        res["aviso"] = ("você já sincroniza a API do SumUp (entradas) — "
                        "importe o extrato com --so-saidas para não dobrar")
    return res


# ── faturas ────────────────────────────────────────────────────
def fatura(cfg, valor, vencimento: str, conta: str = "cartao") -> dict:
    v = _moeda(valor)
    if v <= 0:
        raise ValueError("valor da fatura deve ser positivo")
    venc = _data(vencimento)
    reg = {"id": uuid.uuid4().hex[:16], "conta": conta,
           "valor": str(v), "vencimento": venc.isoformat()}
    _dir(cfg).mkdir(parents=True, exist_ok=True)
    with _arquivo_faturas(cfg).open("a", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")
    return reg


def _faturas(cfg) -> list[dict]:
    try:
        return [json.loads(l) for l in
                _arquivo_faturas(cfg).read_text(
                    encoding="utf-8").splitlines() if l.strip()]
    except OSError:
        return []


# ── painel ─────────────────────────────────────────────────────
def painel(cfg, mes: str | None = None,
           _hoje: date | None = None) -> str:
    hoje = _hoje or date.today()
    mes = mes or hoje.strftime("%Y-%m")
    lanc = [l for l in _todos(cfg) if l["quando"].startswith(mes)]
    ent = sum((Decimal(l["valor"]) for l in lanc if l["tipo"] == "entrada"),
              Decimal(0))
    sai = sum((Decimal(l["valor"]) for l in lanc if l["tipo"] == "saida"),
              Decimal(0))
    out = [f"💰 Finanças — {mes} ({len(lanc)} lançamento(s))"]
    if not lanc:
        out.append("  (nada lançado ainda — 'gastei 35 no almoço' "
                   "registra o primeiro)")
        return "\n".join(out)
    out += [f"Entradas: R$ {_br(ent)}",
            f"Saídas:    R$ {_br(sai)}",
            f"Saldo:     {'+' if ent >= sai else '-'} "
            f"R$ {_br(abs(ent - sai))}"]
    cats: dict[str, Decimal] = {}
    for l in lanc:
        if l["tipo"] == "saida":
            cats[l["categoria"]] = cats.get(
                l["categoria"], Decimal(0)) + Decimal(l["valor"])
    if cats:
        top = sorted(cats.items(), key=lambda kv: -kv[1])[:4]
        out.append("Top gastos: " + " · ".join(
            f"{c} R$ {_br(v)}" for c, v in top))
    fut = sorted((f for f in _faturas(cfg)
                  if _data(f["vencimento"]) >= hoje),
                 key=lambda f: f["vencimento"])
    if fut:
        out.append("Faturas a vencer:")
        for f in fut:
            dias = (_data(f["vencimento"]) - hoje).days
            quando = ("🔴 HOJE" if dias == 0 else
                      f"em {dias} dia(s)" if dias == 1 else
                      f"em {dias} dias")
            out.append(f"  • {f['conta']} R$ {_br(Decimal(f['valor']))} — "
                       f"{_data(f['vencimento']).strftime('%d/%m')}"
                       f" ({quando})")
    return "\n".join(out)


# ── SumUp (API de titular — entradas de vendas) ────────────────
def setup_sumup(cfg, key: str) -> str:
    from .llm_providers import salvar_key
    p = salvar_key(cfg, "sumup", key)
    return f"✔ chave SumUp salva em {p} (600)"


def _get_real(caminho: str, key: str):
    import requests
    r = requests.get(BASE_SUMUP + caminho,
                     headers={"Authorization": f"Bearer {key}"},
                     timeout=30)
    r.raise_for_status()
    return r.json()


def sync_sumup(cfg, _get=None) -> dict:
    """Vendas SUCCESSFUL → entradas ('sumup-vendas'). Repasses NÃO são
    lançados — são a MESMA dinheiro da venda indo pra conta (lançar os
    dois dobraria). Saldo real do banco: extrato CSV."""
    from .llm_providers import api_key
    key = api_key(cfg, "sumup")
    if not key:
        return {"erro": "sem chave — betterme financas sumup setup <key>"}
    get = _get or _get_real
    txs = get("/v0.1/me/transactions", key) or []
    if isinstance(txs, dict):
        txs = txs.get("items", [])
    novas = 0
    for tx in txs:
        if str(tx.get("payment_status", "")).upper() != "SUCCESSFUL":
            continue                      # falhou/cancelou: não tocou a conta
        v = _moeda(str(tx.get("amount", 0)))
        if v <= 0:
            continue
        q = str(tx.get("timestamp", ""))[:10] or date.today().isoformat()
        tid = str(tx.get("id") or tx.get("tx_code") or
                  f"{q}|{v}|{tx.get('payment_type', '')}")
        r = lancar(cfg, v,
                   f"venda {tx.get('payment_type', 'cartao')} sumup",
                   tipo="entrada", conta="sumup-vendas", quando=q,
                   fonte="sumup", _id=f"sumup|{tid}")
        if r.get("novo"):
            novas += 1
    try:
        payouts = get("/v0.1/me/payouts", key) or []
    except Exception:  # noqa: BLE001 — payout é informativo
        payouts = []
    return {"novas_entradas": novas, "transacoes_lidas": len(txs),
            "repasses_informativos": len(payouts),
            "nota": "repasses não são lançados (a venda já entrou)"}


# ── Open Finance: lista oficial de participantes ────────────────
URL_PARTICIPANTES = "https://openfinancebrasil.org.br/quem-participa/"
_RE_MARCA = re.compile(
    r'data-marca="([^"]+)"(?s:.{0,2500}?)data-modalidades="([^"]*)"')
_RE_ATUALIZADO = re.compile(r"Atualizado em\s*([0-9/]+)")


def _fetch_participantes() -> str:
    import requests
    r = requests.get(URL_PARTICIPANTES, timeout=30)
    r.raise_for_status()
    return r.text


def participantes(cfg, termo: str, _fetch=None) -> str:
    """v7.4.0: a instituição X participa do Open Finance? Consulta a
    lista OFICIAL (openfinancebrasil.org.br) com cache local de 24 h
    e mostra o PAPEL (detentora de conta, transmissora/receptora,
    iniciação de pagamentos). Regulatório: participação é obrigatória
    p/ grandes instituições (S1/S2) e voluntária para as demais."""
    termo = _norm(termo or "").strip()
    if not termo:
        return ("✖ informe o nome: betterme financas participantes "
                "<banco> (ex.: sumup, bradesco)")
    cache = _dir(cfg) / "participantes.json"
    fetch = _fetch or _fetch_participantes
    dados = None
    try:
        dados = json.loads(cache.read_text(encoding="utf-8"))
        idade = ((datetime.now() - datetime.fromisoformat(
            dados["quando"])).total_seconds() / 3600)
        if idade > 24:
            dados = None
    except (OSError, ValueError, KeyError):
        dados = None
    if dados is None:
        try:
            html = fetch()
        except Exception as exc:  # noqa: BLE001 — sem rede é normal
            return f"✖ sem rede para buscar a lista oficial ({exc})"
        pares = [(m, mod.strip()) for m, mod in _RE_MARCA.findall(html)]
        m_at = _RE_ATUALIZADO.search(html)
        dados = {"quando": datetime.now().isoformat(timespec="seconds"),
                 "atualizado_em": m_at.group(1) if m_at else "?",
                 "total": len(pares), "pares": pares}
        try:
            _dir(cfg).mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(dados, ensure_ascii=False),
                             encoding="utf-8")
        except OSError:
            pass
    achados = [(m, mod) for m, mod in dados["pares"]
               if termo in _norm(m)]
    cab = (f"📋 Open Finance Brasil — {dados['total']} participantes "
           f"(lista oficial, atualizada em {dados['atualizado_em']})")
    if not achados:
        return (cab + f"\n✖ '{termo}' NÃO está na lista de "
                "participantes — confira o nome exato em "
                "openfinancebrasil.org.br/quem-participa")
    linhas = [cab]
    for m, mod in achados[:6]:
        papeis = " · ".join(p.strip() for p in
                            re.split(r"<br\s*/?>", mod) if p.strip())
        linhas.append(f"✔ {m} — {papeis}")
    return "\n".join(linhas)


# ── CLI ────────────────────────────────────────────────────────
def cmd(args, cfg) -> None:
    a = getattr(args, "acao", "painel")
    try:
        if a in ("painel", "mes"):
            print(painel(cfg, getattr(args, "a1", None)
                         if a == "mes" else None))
        elif a == "lancar":
            r = lancar(cfg, args.a1, args.a2 or "lançamento",
                       categoria=getattr(args, "categoria", "") or "",
                       tipo=getattr(args, "tipo", "saida"),
                       conta=getattr(args, "conta", "") or "manual")
            print(f"✔ {r['tipo']} R$ {_br(Decimal(r['valor']))} — "
                  f"{r['descricao']} [{r['categoria']}|{r['conta']}] "
                  f"(id {r['id']})")
        elif a == "importar":
            res = importar_csv(cfg, args.a1,
                               conta=getattr(args, "conta", "") or "extrato",
                               so_saidas=getattr(args, "so_saidas", False))
            if res.get("erro"):
                print("✖", res["erro"])
                if res.get("colunas"):
                    print("  colunas lidas:", res["colunas"])
            else:
                print(f"✔ {res['novos']} novos · {res['duplicados']} "
                      f"duplicados · {res['ignorados']} ignorados "
                      f"(conta {res['conta']})")
                if res.get("aviso"):
                    print("⚠", res["aviso"])
        elif a == "fatura":
            f = fatura(cfg, args.a1, args.a2,
                       conta=args.a3 or "cartao")
            print(f"✔ fatura {f['conta']} R$ {_br(Decimal(f['valor']))} "
                  f"vence {f['vencimento']}")
        elif a == "participantes":
            print(participantes(cfg, args.a1 or ""))
        elif a == "sumup":
            sub = args.a1 or "status"
            if sub == "setup":
                print(setup_sumup(cfg, args.a2))
            elif sub == "sync":
                res = sync_sumup(cfg)
                if res.get("erro"):
                    print("✖", res["erro"])
                else:
                    print(f"✔ {res['novas_entradas']} novas entradas · "
                          f"{res['transacoes_lidas']} transações lidas · "
                          f"{res['repasses_informativos']} repasses (info)")
                    print("ℹ", res["nota"])
            else:
                from .llm_providers import api_key
                print("chave SumUp:", "configurada ✔" if api_key(
                    cfg, "sumup") else "ausente — sumup setup <key>")
        else:
            print("✖ ação desconhecida:", a)
    except (ValueError, OSError) as exc:
        print("✖", exc)
