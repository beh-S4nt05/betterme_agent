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
    # v8.4.0: regra do USUÁRIO vence (ele ensina); senão embutido
    cat = (categoria or _cat_com_regras(cfg, descricao)
           or ("entrada" if tipo == "entrada"
               else categorizar(descricao)))
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
        return {"erro": "sem chave — pluto financas sumup setup <key>"}
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
        return ("✖ informe o nome: pluto financas participantes "
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


# ── v8.4.0: GESTOR COMPLETO — contas, transferências, edição, ───
#    regras de categoria, orçamentos, recorrentes e resumo.

def _arquivo_contas(cfg) -> Path:
    return _dir(cfg) / "contas.json"


def _arquivo_orcamentos(cfg) -> Path:
    return _dir(cfg) / "orcamentos.json"


def _arquivo_regras(cfg) -> Path:
    return _dir(cfg) / "regras.json"


def _ler_json(caminho: Path, default):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _gravar_json(caminho: Path, dados) -> None:
    """Escrita atômica (tmp+replace) — crash nunca corrompe."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    tmp.replace(caminho)


_TIPOS_CONTA = ("corrente", "poupanca", "cartao", "dinheiro",
                "investimento", "outros")


def _tipo_conta_adivinha(nome: str) -> str:
    n = _norm(nome)
    if "cartao" in n or "credito" in n:
        return "cartao"
    if "poupan" in n:
        return "poupanca"
    if "dinheiro" in n or "especie" in n:
        return "dinheiro"
    if "invest" in n:
        return "investimento"
    return "corrente"


def contas(cfg) -> list[dict]:
    """Contas do gestor: registry (contas.json) + IMPLÍCITAS (strings
    já usadas em lançamentos/faturas sem registro) — nada se perde na
    migração; lançamentos antigos aparecem em contas implícitas."""
    regs = [dict(c) for c in _ler_json(_arquivo_contas(cfg), [])]
    conhecidas = {c["nome"] for c in regs}
    em_uso = ({l.get("conta", "manual") for l in _todos(cfg)}
              | {f.get("conta", "cartao") for f in _faturas(cfg)
                 if _faturas(cfg)})
    for nome in sorted(em_uso - conhecidas - {""}):
        regs.append({"id": _id_de(f"conta|{nome}"), "nome": nome,
                     "tipo": _tipo_conta_adivinha(nome),
                     "saldo_inicial": "0", "cor": None,
                     "implicita": True})
    return regs


def _conta_reg(cfg, nome: str) -> dict | None:
    return next((c for c in _ler_json(_arquivo_contas(cfg), [])
                 if c["nome"] == nome), None)


def criar_conta(cfg, nome: str, tipo: str = "corrente",
                saldo_inicial="0", cor: str | None = None) -> dict:
    nome = str(nome or "").strip()
    if not nome:
        return {"erro": "nome da conta é obrigatório"}
    if _conta_reg(cfg, nome) or any(
            c["nome"] == nome for c in contas(cfg)):
        return {"erro": f"já existe conta '{nome}'"}
    if tipo not in _TIPOS_CONTA:
        return {"erro": f"tipo inválido — use {'|'.join(_TIPOS_CONTA)}"}
    reg = {"id": uuid.uuid4().hex[:16], "nome": nome, "tipo": tipo,
           "saldo_inicial": str(_moeda(saldo_inicial)), "cor": cor,
           "arquivada": False}
    regs = _ler_json(_arquivo_contas(cfg), [])
    regs.append(reg)
    _gravar_json(_arquivo_contas(cfg), regs)
    return reg


def salvar_conta(cfg, id_conta: str, **campos) -> dict:
    regs = _ler_json(_arquivo_contas(cfg), [])
    alvo = next((c for c in regs if c["id"] == id_conta), None)
    if not alvo:
        return {"erro": "conta não encontrada"}
    if "tipo" in campos and campos["tipo"] not in _TIPOS_CONTA:
        return {"erro": "tipo inválido"}
    if "saldo_inicial" in campos:
        campos["saldo_inicial"] = str(_moeda(campos["saldo_inicial"]))
    alvo.update({k: v for k, v in campos.items()
                 if k in ("nome", "tipo", "saldo_inicial", "cor",
                          "arquivada")})
    _gravar_json(_arquivo_contas(cfg), regs)
    return alvo


def saldo_conta(cfg, nome: str) -> Decimal:
    """Saldo ATUAL: saldo_inicial + entradas − saídas ± transferências
    (transferência NÃO é receita nem despesa — só move dinheiro)."""
    reg = _conta_reg(cfg, nome) or {}
    s = Decimal(str(reg.get("saldo_inicial", "0")))
    for l in _todos(cfg):
        v = Decimal(l["valor"])
        if l.get("conta") == nome:
            if l["tipo"] == "entrada":
                s += v
            elif l["tipo"] == "saida":
                s -= v
            elif l["tipo"] == "transferencia":
                s -= v                      # saiu desta conta
        if (l["tipo"] == "transferencia"
                and l.get("para") == nome and l.get("conta") != nome):
            s += v                          # entrou nesta conta
    return s


def transferir(cfg, de: str, para: str, valor, quando=None,
               descricao: str = "") -> dict:
    """Move dinheiro ENTRE contas — fora de receita/despesa (padrão
    Belvo: transferência não infla gasto)."""
    if _norm(de) == _norm(para):
        return {"erro": "conta de origem e destino são a mesma"}
    v = _moeda(valor)
    if v <= 0:
        return {"erro": "valor deve ser positivo"}
    q = (_data(quando) if quando else date.today()).isoformat()
    reg = {"id": uuid.uuid4().hex[:16], "quando": q, "valor": str(v),
           "tipo": "transferencia", "categoria": "transferencia",
           "descricao": str(descricao or f"transferência {de} → {para}"
                           )[:120], "conta": de, "para": para,
           "fonte": "manual"}
    _dir(cfg).mkdir(parents=True, exist_ok=True)
    with _arquivo(cfg).open("a", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")
    return {"id": reg["id"], "novo": True, **reg}


def editar(cfg, id_lanc: str, **campos) -> dict:
    """Edita um lançamento (descrição/categoria/conta/data/valor/tipo)
    — reescrita atômica do livro-caixa."""
    todos = _todos(cfg)
    alvo = next((l for l in todos if l["id"] == id_lanc), None)
    if not alvo:
        return {"erro": "lançamento não encontrado"}
    if "valor" in campos:
        v = _moeda(campos["valor"])
        if v <= 0:
            return {"erro": "valor deve ser positivo"}
        campos["valor"] = str(v)
    if "tipo" in campos and campos["tipo"] not in (
            "entrada", "saida", "transferencia"):
        return {"erro": "tipo inválido"}
    if "quando" in campos:
        campos["quando"] = _data(campos["quando"]).isoformat()
    alvo.update({k: v for k, v in campos.items()
                 if k in ("descricao", "categoria", "conta", "quando",
                          "valor", "tipo")})
    _gravar_jsonl(cfg, todos)
    return alvo


def remover(cfg, id_lanc: str) -> dict:
    todos = _todos(cfg)
    if not any(l["id"] == id_lanc for l in todos):
        return {"erro": "lançamento não encontrado"}
    _gravar_jsonl(cfg, [l for l in todos if l["id"] != id_lanc])
    return {"ok": True, "removido": id_lanc}


def _gravar_jsonl(cfg, lancamentos: list[dict]) -> None:
    """Reescrita atômica do livro-caixa (editar/remover)."""
    _dir(cfg).mkdir(parents=True, exist_ok=True)
    tmp = _arquivo(cfg).with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(l, ensure_ascii=False) + "\n"
                           for l in lancamentos), encoding="utf-8")
    tmp.replace(_arquivo(cfg))


# ── regras de categoria (o usuário ensina; vale antes do embutido) ──
def regras(cfg) -> list[dict]:
    return _ler_json(_arquivo_regras(cfg), [])


def add_regra(cfg, padrao: str, categoria: str) -> dict:
    padrao = _norm(padrao).strip()
    categoria = _norm(categoria).strip()
    if not padrao or not categoria:
        return {"erro": "padrão e categoria são obrigatórios"}
    regs = [r for r in regras(cfg) if r["padrao"] != padrao]
    regs.append({"padrao": padrao, "categoria": categoria})
    _gravar_json(_arquivo_regras(cfg), regs)
    return {"padrao": padrao, "categoria": categoria}


def del_regra(cfg, padrao: str) -> dict:
    regs = regras(cfg)
    if not any(r["padrao"] == _norm(padrao) for r in regs):
        return {"erro": "regra não encontrada"}
    _gravar_json(_arquivo_regras(cfg),
                 [r for r in regs if r["padrao"] != _norm(padrao)])
    return {"ok": True}


def _cat_com_regras(cfg, descricao: str) -> str | None:
    d = _norm(descricao)
    for r in regras(cfg):
        if r["padrao"] in d:
            return r["categoria"]
    return None


# ── orçamentos ──────────────────────────────────────────────────
def orcamentos(cfg) -> list[dict]:
    return _ler_json(_arquivo_orcamentos(cfg), [])


def set_orcamento(cfg, categoria: str, limite, mes: str | None = None
                  ) -> dict:
    categoria = _norm(categoria).strip()
    v = _moeda(limite)
    if not categoria:
        return {"erro": "categoria é obrigatória"}
    regs = [o for o in orcamentos(cfg)
            if not (o["categoria"] == categoria and o.get("mes") == mes)]
    if v > 0:
        regs.append({"categoria": categoria, "mes": mes,
                     "limite": str(v)})
    _gravar_json(_arquivo_orcamentos(cfg), regs)
    return {"categoria": categoria, "mes": mes, "limite": str(v)}


# ── recorrentes (detecção por repetição mensal) ─────────────────
def recorrentes(cfg, _hoje: date | None = None) -> list[dict]:
    """>=3 saídas com a mesma assinatura (categoria + 1ªs palavras) e
    intervalo ~mensal (15–60 d) → recorrente estimado."""
    hoje = _hoje or date.today()
    grupos: dict[str, list[dict]] = {}
    for l in _todos(cfg):
        if l["tipo"] != "saida":
            continue
        palavras = [p for p in _norm(l["descricao"]).split()
                    if len(p) > 2][:3]
        if not palavras:
            continue
        chave = l["categoria"] + "|" + " ".join(palavras)
        grupos.setdefault(chave, []).append(l)
    out = []
    for chave, ls in grupos.items():
        ds = sorted(_data(l["quando"]) for l in ls)
        gaps = [(b - a).days for a, b in zip(ds, ds[1:])]
        if len(ds) < 3 or not gaps:
            continue
        if not all(15 <= g <= 60 for g in gaps):
            continue
        vals = [Decimal(l["valor"]) for l in ls]
        freq = round(sum(gaps) / len(gaps))
        ultima = ds[-1]
        out.append({"chave": chave,
                    "categoria": ls[0]["categoria"],
                    "descricao": ls[0]["descricao"][:60],
                    "n": len(ls), "media": str(sum(vals) / len(vals)),
                    "ultima": ultima.isoformat(),
                    "frequencia_dias": freq,
                    "proxima": (ultima.fromordinal(
                        ultima.toordinal() + freq)).isoformat(),
                    "atrasada": ultima < hoje
                    and (hoje - ultima).days > freq + 10})
    return sorted(out, key=lambda r: r["ultima"], reverse=True)


# ── resumo — tudo que o dashboard precisa, numa chamada ────────
def resumo(cfg, mes: str | None = None, _hoje: date | None = None) -> dict:
    hoje = _hoje or date.today()
    mes = mes or hoje.strftime("%Y-%m")
    todos = _todos(cfg)

    def _do_mes(m):
        ls = [l for l in todos if l["quando"].startswith(m)]
        ent = sum((Decimal(l["valor"]) for l in ls
                   if l["tipo"] == "entrada"), Decimal(0))
        sai = sum((Decimal(l["valor"]) for l in ls
                   if l["tipo"] == "saida"), Decimal(0))
        return ent, sai

    ent, sai = _do_mes(mes)
    cats: dict[str, Decimal] = {}
    for l in todos:
        if l["quando"].startswith(mes) and l["tipo"] == "saida":
            cats[l["categoria"]] = cats.get(l["categoria"],
                                            Decimal(0)) + Decimal(l["valor"])
    evolucao = []
    for i in range(5, -1, -1):
        y, mth = hoje.year, hoje.month - i
        while mth <= 0:
            mth += 12
            y -= 1
        e, s = _do_mes(f"{y:04d}-{mth:02d}")
        evolucao.append({"mes": f"{y:04d}-{mth:02d}",
                         "entradas": str(e), "saidas": str(s)})
    orcs = []
    for o in orcamentos(cfg):
        if o.get("mes") and o["mes"] != mes:
            continue
        gasto = cats.get(o["categoria"], Decimal(0))
        lim = Decimal(o["limite"])
        pct = int(gasto / lim * 100) if lim > 0 else 0
        orcs.append({"categoria": o["categoria"], "mes": o.get("mes"),
                     "limite": o["limite"], "gasto": str(gasto),
                     "pct": pct, "alerta": pct >= 80})
    futs = sorted((f for f in _faturas(cfg)
                   if _data(f["vencimento"]) >= hoje),
                  key=lambda f: f["vencimento"])
    cts = [{"nome": c["nome"], "tipo": c["tipo"],
            "cor": c.get("cor"), "implicita": c.get("implicita", False),
            "saldo": str(saldo_conta(cfg, c["nome"]))}
           for c in contas(cfg)]
    return {
        "mes": mes,
        "saldo_total": str(sum((Decimal(c["saldo"]) for c in cts
                                if cts), Decimal(0))),
        "contas": cts,
        "entradas": str(ent), "saidas": str(sai),
        "saldo_mes": str(ent - sai),
        "por_categoria": [{"categoria": k, "total": str(v)}
                          for k, v in sorted(cats.items(),
                                             key=lambda kv: -kv[1])],
        "evolucao": evolucao,
        "orcamentos": orcs,
        "recorrentes": recorrentes(cfg, _hoje=hoje),
        "faturas": [{"conta": f["conta"], "valor": f["valor"],
                     "vencimento": f["vencimento"]} for f in futs],
        "n_lancamentos": len(todos),
    }
