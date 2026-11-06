# -*- coding: utf-8 -*-
"""📚 Notebook — clone local do NotebookLM (v8.1.0, pedido do
operador) com integração NATIVA do cérebro (v8.2.0).

O conceito do NotebookLM, no padrão local-first do Betterme:

- **FONTES**: você joga conhecimento (PDF, imagem escaneada, .md,
  .txt) — `betterme notebook add` extrai o texto (OCR se precisar) e
  indexa com o MESMO RAG determinístico da biblioteca (TF-IDF, stdlib
  pura — reuso, zero duplicação).
- **RESPOSTAS FUNDAMENTADAS**: o agente (tool `notebook_buscar`) e o
  CLI (`notebook perguntar`) respondem fundamentados nas fontes —
  v8.2.0: o CÉREBRO DO APP responde (citação [n] + rodapé de fontes);
  `--raw` devolve os trechos verbatim puros; sem cérebro, fallback
  verbatim honesto. Alucinação é impossível por construção.
- **MATERIAIS**: `notebook material resumo|faq|guia|flashcards` GERA
  com o cérebro do app (skill ensino-cbta) e SALVA em
  `<data>/notebook/materiais/` — nativo, nada de copiar-e-colar.

Diferenças honestas vs. NotebookLM: sem "visão geral em áudio"
(fase futura: TTS local) e o índice é TF-IDF local (não embeddings
de LLM) — determinístico e privado.
"""
from __future__ import annotations

import re
import time
import unicodedata
from pathlib import Path

from . import knowledge

_MATERIAIS = ("resumo", "faq", "guia", "flashcards")
_RE_HEADER = re.compile(r"<!--.*?-->\s*", re.S)   # cabeçalho interno


def _limpo(txt: str) -> str:
    return _RE_HEADER.sub("", str(txt or "")).strip()


def _slug(txt: str) -> str:
    s = unicodedata.normalize("NFKD", str(txt or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s or "fonte")[:60]


def dir_notebook(cfg) -> Path:
    return Path(cfg.data_dir) / "notebook"


def dir_fontes(cfg) -> Path:
    d = dir_notebook(cfg) / "fontes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def dir_materiais(cfg) -> Path:
    d = dir_notebook(cfg) / "materiais"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _gerar(cfg, system: str, user: str, _brain=None) -> str:
    """v8.2.0: roda o CÉREBRO DO APP (Agent com skills) uma vez —
    nativo, nada de copiar-e-colar. `_brain(system, user)` é injetável
    p/ teste; falha devolve '' (quem chama decide o fallback)."""
    if _brain is not None:
        try:
            return _brain(system, user).strip()
        except Exception:  # noqa: BLE001
            return ""
    try:
        from .agent import Agent
        ag = Agent(cfg)
        resp = ag.run([{"role": "system", "content": system},
                       {"role": "user", "content": user}])
    except Exception:  # noqa: BLE001 — sem cérebro → fallback honesto
        return ""
    resp = (resp or "").strip()
    # Agent engole falhas do provedor e devolve "[erro] ..." (agent.py
    # devolve erro como string) — isso é cérebro INDISPONÍVEL, nunca
    # resposta: devolver '' dispara o fallback honesto de quem chama.
    return "" if resp.startswith("[erro]") else resp


def adicionar(cfg, caminho: str, _ocr=None) -> dict:
    """Adiciona fonte(s): arquivo único ou pasta inteira. Extrai
    texto (OCR quando precisar), grava .md normalizado na pasta de
    fontes e (re)indexa."""
    from .ocr import extrair
    p = Path(caminho).expanduser()
    if not p.exists():
        return {"erro": f"caminho não encontrado: {p}"}
    alvos = sorted(q for q in (p.rglob("*") if p.is_dir() else [p])
                   if q.is_file())[:200]
    if not alvos:
        return {"erro": "nada para adicionar"}
    adicionadas, notas = [], []
    for arq in alvos:
        if arq.parent == dir_fontes(cfg):
            continue                      # já é fonte do notebook
        res = (_ocr(cfg, str(arq)) if _ocr else extrair(cfg, str(arq)))
        texto = (res.get("texto") or "").strip()
        if not texto:
            notas.append(f"{arq.name}: sem texto "
                         + ("; ".join(res.get("notas") or []) or
                            "(arquivo vazio?)")[:120])
            continue
        dest = dir_fontes(cfg) / f"{_slug(arq.stem)}.md"
        cab = [f"<!-- fonte: {arq.name}",
               f"     adicionada: {time.strftime('%Y-%m-%d %H:%M')}",
               f"     engine: {res.get('engine', '?')} -->", ""]
        dest.write_text("\n".join(cab) + texto + "\n", encoding="utf-8")
        adicionadas.append(dest.name)
    est = knowledge.indexar(cfg, pasta=dir_fontes(cfg))
    out = {"adicionadas": adicionadas, "notas": notas,
           "total_fontes": est["livros"], "total_blocos": est["blocos"]}
    return out


def remover(cfg, nome: str) -> dict:
    alvo = dir_fontes(cfg) / f"{_slug(nome)}.md"
    if not alvo.exists():
        stuns = [p.stem for p in dir_fontes(cfg).glob("*.md")]
        parecidos = ", ".join(stuns[:20]) or "(vazio)"
        return {"erro": f"fonte '{nome}' não existe — fontes: {parecidos}"}
    alvo.unlink()
    est = knowledge.indexar(cfg, pasta=dir_fontes(cfg))
    return {"ok": True, "removida": alvo.name,
            "total_fontes": est["livros"], "total_blocos": est["blocos"]}


def listar(cfg) -> list[dict]:
    out = []
    for p in sorted(dir_fontes(cfg).glob("*.md")):
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = re.search(r"fonte: (.+)", txt)
        e = re.search(r"engine: (.+?) -->", txt)
        out.append({"nome": p.stem, "arquivo": str(p),
                    "chars": len(txt),
                    "origem": m.group(1).strip() if m else "?",
                    "engine": e.group(1).strip() if e else "?"})
    return out


def _contexto(cfg, consulta: str, k: int):
    """Busca os trechos e devolve (achados, ctx [n] + verbatim)."""
    achados = knowledge.buscar(cfg, consulta, k=k,
                               pasta=dir_fontes(cfg))
    blocos = [f"[{i}] 📄 {a['fonte']}\n\"\"\"{_limpo(a['texto'])}\"\"\""
              for i, a in enumerate(achados, 1)]
    return achados, "\n".join(blocos)


def perguntar(cfg, consulta: str, k: int = 4, gerar: bool = False,
              _brain=None, bruto: bool = False) -> str:
    """Resposta GROUNDED. gerar=False (padrão): trechos verbatim +
    fonte. gerar=True (v8.2.0, CLI): o CÉREBRO DO APP responde com
    citação [n] — nativo; sem cérebro → fallback verbatim honesto.
    bruto=True (CLI --raw): SÓ os trechos, sem aviso nem instrução."""
    achados, ctx = _contexto(cfg, consulta, k)
    if not achados:
        return ("ℹ nada no notebook sobre isso. Adicione fontes com "
                "`betterme notebook add <arquivo>` — ou refine a pergunta.")
    if bruto:
        return (f"📚 Notebook — {len(achados)} trecho(s) de "
                f"{len({a['fonte'] for a in achados})} fonte(s):\n{ctx}")
    if gerar:
        system = (
            "Você responde EXCLUSIVAMENTE com os trechos do notebook do "
            "operador fornecidos abaixo. Cite [n] a cada afirmação. "
            "Responda em português, no tamanho da pergunta. O que não "
            "estiver nos trechos: diga 'não está nas fontes' — NUNCA "
            "invente.")
        resp = _gerar(cfg, system,
                      f"PERGUNTA: {consulta}\n\nTRECHOS:\n\n{ctx}",
                      _brain=_brain)
        if resp:
            fontes = ", ".join(
                f"[{i}] {Path(a['fonte']).name}"
                for i, a in enumerate(achados, 1))
            return f"{resp}\n\n📚 Fontes: {fontes}"
    linhas = [f"📚 Notebook — {len(achados)} trecho(s) de "
              f"{len({a['fonte'] for a in achados})} fonte(s):"]
    linhas.append(ctx)
    linhas.append("\n⚠ Responda APENAS com o que está nos trechos acima "
                  "(cite [n]); se não bastar, diga o que falta.")
    if gerar:
        linhas.append("ℹ cérebro indisponível — trechos verbatim acima "
                      "(inicie o provedor: betterme ollama status).")
    return "\n".join(linhas)


def materiais(cfg) -> list[dict]:
    """v8.2.0: materiais GERADOS e salvos em materiais/."""
    out = []
    for arq in sorted(dir_materiais(cfg).glob("*.md")):
        cab = arq.read_text(encoding="utf-8")[:300]
        m = re.search(r"material: ([a-z]+) · tema: ([^·]+) ·", cab)
        if not m:
            continue
        out.append({"tipo": m.group(1),
                    "tema": m.group(2).strip() or "-",
                    "arquivo": arq.name,
                    "chars": arq.stat().st_size})
    return out


def material(cfg, tipo: str, tema: str = "", gerar: bool = False,
             _brain=None) -> str:
    """Monta o pedido de material COM contexto embutido. gerar=True
    (v8.2.0, CLI): o CÉREBRO DO APP gera (skill ensino-cbta aplica)
    e SALVA em <data>/notebook/materiais/ — nativo, sem colar nada."""
    if tipo not in _MATERIAIS:
        return (f"✖ material inválido: {tipo!r} — use "
                f"{'|'.join(_MATERIAIS)}")
    consulta = tema or " ".join(tipo)
    achados = knowledge.buscar(cfg, consulta, k=6,
                               pasta=dir_fontes(cfg))
    if not achados:
        return ("ℹ sem fontes para esse tema — adicione com "
                "`betterme notebook add <arquivo>`")
    ctx = "\n\n".join(f"[{i}] {Path(a['fonte']).name}: "
                      f"{_limpo(a['texto'])}"
                      for i, a in enumerate(achados, 1))
    pedido = {
        "resumo": (
            "Produza o RESUMO das fontes abaixo (estrutura CBTA leve): "
            "1) 🎯 a ideia central em uma frase; 2) 📚 até 5 blocos de "
            "conhecimento com um exemplo cada; 3) ✅ 3 pontos que quem "
            "leu deve saber verificar que entendeu. Cite [n] a cada "
            "afirmação."),
        "faq": (
            "Produza o FAQ das fontes abaixo: 6 a 10 perguntas que "
            "alguém que ESTUDA esse material faria, com respostas de "
            "2 a 4 linhas CITANDO [n]. Pergunta sem resposta nas "
            "fontes: responda 'não está nas fontes'."),
        "guia": (
            "Produza o GUIA DE ESTUDO das fontes abaixo (CBTA, teor "
            "75%): 🎯 competência final observável; rota de estudo em "
            "3–5 sessões com o que fazer em cada; ✅ critério de domínio "
            "por sessão; 🎚️ profundidade PP no início, PLA no final. "
            "Cite [n]."),
        "flashcards": (
            "Produza FLASHCARDS das fontes abaixo: 10 a 15 cartões no "
            "formato 'P: ... / R: ...' (frente pergunta curta, verso "
            "resposta de 1–2 linhas com [n]). Cubra o essencial, não "
            "detalhe obscuro."),
    }[tipo]
    prompt = (f"🗂️ MATERIAL: {tipo.upper()}"
              + (f" — {tema}" if tema else "")
              + f"\n\n{pedido}\n\nFONTES (trechos verbatim):\n\n{ctx}")
    if not gerar:
        return prompt
    resp = _gerar(cfg,
                  "Você é instrutor CBTA (skill ensino-cbta): siga a "
                  "estrutura pedida, teor 75%, cite [n] das fontes.",
                  prompt, _brain=_brain)
    if not resp:
        return (prompt + "\n\n⚠ cérebro indisponível — prompt pronto "
                "(inicie o Ollama/provedor e rode de novo)")
    arq = dir_materiais(cfg) / f"{tipo}-{_slug(tema or 'fontes')}.md"
    arq.write_text(
        f"<!-- material: {tipo} · tema: {tema or '-'} · "
        f"gerado: {time.strftime('%Y-%m-%d %H:%M')} -->\n\n"
        + resp + "\n", encoding="utf-8")
    return (f"✔ material GERADO e salvo em {arq}\n\n{resp}")


def status(cfg) -> str:
    from .ocr import disponiveis
    fontes = listar(cfg)
    eng = disponiveis(cfg)
    ocr = ("unlimited-ocr (baidu) ✔" if eng["unlimited"] else
           "tesseract ✔" if eng["tesseract"] else
           "✖ nenhum — veja `betterme notebook add` com um PDF "
           "escaneado para as instruções")
    return (f"📚 Notebook — {len(fontes)} fonte(s) · "
            f"{knowledge.status(cfg, pasta=dir_fontes(cfg))['blocos']} "
            f"bloco(s) indexados\n  OCR: {ocr} · "
            f"materiais: {len(materiais(cfg))} material(is) salvo(s)"
            "\n  fontes: "
            + ("; ".join(f["nome"] for f in fontes[:8]) or "(vazio)"))


def cmd(args, cfg) -> None:
    a = getattr(args, "acao", "status")
    try:
        if a == "add":
            r = adicionar(cfg, args.a1)
            if r.get("erro"):
                print("✖", r["erro"])
            else:
                print(f"✔ {len(r['adicionadas'])} fonte(s) adicionada(s) "
                      f"· notebook: {r['total_fontes']} fonte(s), "
                      f"{r['total_blocos']} bloco(s)")
                for n in r["notas"]:
                    print("  ⚠", n)
        elif a == "listar":
            for f in listar(cfg):
                print(f"  📄 {f['nome']} ({f['chars']} chars · "
                      f"{f['engine']}) ← {f['origem']}")
            else:
                pass
            if not listar(cfg):
                print("  (vazio — betterme notebook add <arquivo>)")
        elif a == "remover":
            r = remover(cfg, args.a1 or "")
            print("✔ removida: " + r["removida"] if r.get("ok")
                  else f"✖ {r.get('erro')}")
        elif a == "perguntar":
            print(perguntar(cfg, " ".join(filter(None, [args.a1,
                                                        getattr(args, "a2", "")])),
                           gerar=not getattr(args, "raw", False),
                           bruto=getattr(args, "raw", False)))
        elif a == "material":
            print(material(cfg, (args.a1 or "").lower(),
                           getattr(args, "a2", "") or "", gerar=True))
        elif a == "materiais":
            mats = materiais(cfg)
            if not mats:
                print("  (nenhum — betterme notebook material "
                      "resumo|faq|guia|flashcards [tema])")
            for m in mats:
                print(f"  🗂️ {m['arquivo'][:-3]} ({m['tipo']} · "
                      f"{m['tema']} · {m['chars']} chars)")
        elif a == "status":
            print(status(cfg))
        else:
            print("✖ ação desconhecida:", a)
    except (ValueError, OSError) as exc:
        print("✖", exc)
