# -*- coding: utf-8 -*-
"""🗄️ Vault Obsidian — memória de longo prazo em ARQUIVOS locais
(v7.7.0, pedido do operador).

O problema: conhecimento guardado "em variáveis e RAM" morre com a
conversa; memory.json é curto por desenho (teto de prompt). A solução
é externa: um VAULT Obsidian — pastas de .md no disco do operador.

- **Escopos** (pastas): `memoria/` (fatos longos sobre o operador),
  `projetos/<nome>/`, `conhecimento/<dominio>/` e `aprendizado/`
  (progresso CBTA — níveis de proficiência e evidências).
- Zero RAM: nada fica em memória — o agente LÊ o arquivo quando
  precisa (mesmo padrão das skills/biblioteca) e o humano lê/edita
  no Obsidian (arquivos .md puros, frontmatter YAML, wikilinks).
- Notion, se o operador preferir: o mesmo modelo cabe no Notion MCP
  (mcp_servers) — mas o vault local é o padrão (local-first).
- Desligado por padrão: `pluto vault usar <caminho>` liga.

Anti-invenção: `vault_buscar` devolve TRECHO verbatim do arquivo com
a fonte — nunca paráfrase do modelo.
"""
from __future__ import annotations

import re
import time
import unicodedata
from pathlib import Path

ESCOPOS = ("memoria", "projetos", "conhecimento", "aprendizado")


def _slug(txt: str) -> str:
    s = unicodedata.normalize("NFKD", str(txt or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s or "nota")[:60]


def _dir_vault(cfg) -> Path | None:
    """Path do vault ou None (vazio NÃO é '.' — pegue pelo T224:
    Path('') vira CWD e o vault 'desligado' escrevia no repo)."""
    v = str(getattr(cfg, "vault_dir", "") or "").strip()
    return Path(v).expanduser() if v else None


def ativo(cfg) -> bool:
    v = _dir_vault(cfg)
    return v is not None and v.is_dir()


def _dir_escopo(cfg, escopo: str) -> Path:
    v = _dir_vault(cfg)
    assert v is not None, "vault ativo é pré-condição"
    return v / "Pluto" / _slug(escopo)


def salvar(cfg, escopo: str, titulo: str, conteudo: str,
           tags: str = "") -> dict:
    """Grava/atualiza a nota no escopo e mantém o índice (MOC) do
    escopo com wikilinks — o padrão Obsidian de navegação."""
    escopo = _slug(escopo)
    if escopo not in ESCOPOS:
        return {"erro": f"escopo inválido: {escopo!r} — use "
                        f"{'|'.join(ESCOPOS)}"}
    if not str(titulo or "").strip() or not str(conteudo or "").strip():
        return {"erro": "informe 'titulo' e 'conteudo'"}
    if not ativo(cfg):
        return {"erro": "vault não configurado — pluto vault usar "
                        "<caminho> (pasta do vault Obsidian)"}
    d = _dir_escopo(cfg, escopo)
    d.mkdir(parents=True, exist_ok=True)
    arq = d / f"{_slug(titulo)}.md"
    novo = not arq.exists()
    tags_l = [t.strip() for t in re.split(r"[;,]", tags or "") if t.strip()]
    fm = ["---", f"titulo: {str(titulo).strip()[:80]}",
          f"escopo: {escopo}",
          f"tags: [{', '.join(tags_l)}]" if tags_l else "tags: []",
          f"atualizado: {time.strftime('%Y-%m-%d %H:%M')}",
          "origem: pluto-agent", "---", ""]
    arq.write_text("\n".join(fm) + str(conteudo).strip() + "\n",
                   encoding="utf-8")
    _atualizar_moc(cfg, escopo)
    return {"ok": True, "arquivo": str(arq), "novo": novo}


def _atualizar_moc(cfg, escopo: str) -> None:
    d = _dir_escopo(cfg, escopo)
    notas = sorted(p.stem for p in d.glob("*.md") if p.stem != "_indice")
    linhas = [f"# 🗂️ {escopo} — índice (MOC)", "",
              "Notas mantidas pelo Pluto (edite à vontade no Obsidian):",
              ""]
    linhas += [f"- [[{n}]]" for n in notas] or ["- (vazio)"]
    (d / "_indice.md").write_text("\n".join(linhas) + "\n",
                                  encoding="utf-8")


def buscar(cfg, termo: str, escopo: str = "") -> dict:
    """Busca verbatim nos .md do vault (ou de UM escopo). Devolve
    trecho + fonte — anti-alucinação por construção."""
    if not str(termo or "").strip():
        return {"erro": "informe 'termo'"}
    if not ativo(cfg):
        return {"erro": "vault não configurado — pluto vault usar "
                        "<caminho>"}
    base = _dir_vault(cfg) / "Pluto"
    alvo = (_dir_escopo(cfg, escopo) if escopo
            and _slug(escopo) in ESCOPOS else base)
    t = _slug(termo).replace("-", " ")
    achados = []
    for p in sorted(alvo.rglob("*.md")):
        try:
            texto = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if t in texto.lower() or t in _slug(p.stem).replace("-", " "):
            i = texto.lower().find(t)
            trecho = texto[max(0, i - 60):i + 160].strip() if i >= 0 else \
                texto[:200].strip()
            achados.append({"nota": p.stem, "arquivo": str(p),
                            "trecho": trecho})
        if len(achados) >= 8:
            break
    return {"achados": achados, "total": len(achados)}


def status(cfg) -> str:
    v = _dir_vault(cfg)
    if v is None:
        return ("✖ vault desligado — `pluto vault usar <caminho>` "
                "aponta para a pasta do seu vault Obsidian (ou crie "
                "uma: `pluto vault usar ~/Obsidian/Mente`). Notion? "
                "adicione o servidor MCP do Notion no config.yaml.")
    if not v.is_dir():
        return f"✖ {v} não existe — crie a pasta (mkdir -p) e tente de novo"
    n = len(list((v / "Pluto").rglob("*.md"))) if (v / "Pluto").is_dir() else 0
    return (f"✔ vault ativo: {v} · {n} nota(s) em Pluto/"
            f"{' · '.join(ESCOPOS)} · humano lê/edita no Obsidian")


def cmd(args, cfg) -> None:
    a = getattr(args, "acao", "status")
    if a == "status":
        print(status(cfg))
    elif a == "usar":
        caminho = getattr(args, "a1", "") or ""
        if not caminho:
            print("✖ informe o caminho: pluto vault usar ~/Obsidian/Vault")
            return
        p = Path(caminho).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        cfg.update({"vault_dir": str(p)})
        for e in ESCOPOS:
            (p / "Pluto" / e).mkdir(parents=True, exist_ok=True)
            _atualizar_moc(cfg, e)
        print(f"✔ vault ligado: {p} (escopos: {' · '.join(ESCOPOS)}) "
              "— abra a pasta no Obsidian")
    else:
        print("✖ ação desconhecida:", a)
