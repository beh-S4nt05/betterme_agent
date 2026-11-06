"""📎 @menções — anexos reais no chat (v7.0.0).

Padrão do Cursor/OpenCode ("@file" para dar contexto), adaptado: o
Pluto LÊ o conteúdo real do disco e anexa ao pedido da task — o
modelo não precisa adivinhar nem gastar ferramentas para "ver" o que
o operador já apontou.

  "revise @src/app.py e corrija @README.md"
  "resuma a estrutura @docs/ e o @package.json"

Regras (orçamento para não estourar o prompt):
  - @caminho de arquivo  → conteúdo (até 10 KB por arquivo)
  - @pasta               → listagem em árvore (2 níveis, 30 entradas)
  - e-mail (user@host)   → NÃO é menção
  - máx. 6 menções · 25 KB total · binário vira "[binário]"
  - caminho inexistente  → nota "(não encontrado)" quando houver outro
    anexo válido; sozinho, é ignorado (o chat segue normal)
"""
from __future__ import annotations

import re
from pathlib import Path

_MENCAO_RE = re.compile(r"(?<![\w@.-])@(~?[/\w.-]*)")
_MAX_MENCOES = 6
_MAX_ARQUIVO = 10_000          # bytes lidos por arquivo
_MAX_BLOCO = 25_000            # chars do bloco total
_EXT_BINARIO = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
                ".zip", ".gz", ".tar", ".mp3", ".mp4", ".wav", ".ogg",
                ".sqlite", ".db", ".exe", ".dll", ".so", ".pyc", ".lock"}
# v7.2.1 (6º achado): código/config anexado usa CERCAS — a D2 mantém a
# análise no local (lei) e o DLP mascara no transporte. Texto puro NÃO
# usa cercas (indentação): ata/.md/.csv anexados não são "código".
_EXT_CODIGO = {".py", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".java", ".c",
               ".h", ".cpp", ".hpp", ".cs", ".go", ".rs", ".rb", ".php",
               ".sh", ".bash", ".zsh", ".ps1", ".sql", ".vue", ".svelte",
               ".kt", ".kts", ".swift", ".scala", ".r", ".pl", ".lua",
               ".hs", ".ex", ".exs", ".clj", ".dart", ".m", ".gradle",
               ".env", ".ini", ".cfg", ".conf", ".yaml", ".yml", ".tf",
               ".dockerfile", ".makefile", ".mk"}


def _resolver(token: str) -> Path | None:
    t = token.rstrip(".,;:!?)")
    if not t or len(t) < 2:
        return None
    if t.startswith("~/"):
        return Path.home() / t[2:]
    if t.startswith("/"):
        return Path(t)
    return (Path.cwd() / t).resolve()


def _ler_arquivo(p: Path) -> str:
    try:
        if p.suffix.lower() in _EXT_BINARIO:
            return "[arquivo binário — não anexado como texto]"
        dados = p.read_bytes()
        if b"\x00" in dados[:1024]:
            return "[arquivo binário — não anexado como texto]"
        tam = len(dados)
        texto = dados[:_MAX_ARQUIVO].decode("utf-8", errors="replace")
        if tam > _MAX_ARQUIVO:
            texto += f"\n…[truncado — arquivo tem {tam} bytes]"
        return texto
    except OSError as exc:
        return f"[erro ao ler: {exc}]"


def _listar_pasta(p: Path) -> str:
    linhas: list[str] = []
    try:
        for i, item in enumerate(sorted(p.iterdir(),
                                        key=lambda x: (x.is_file(), x.name))):
            if i >= 30:
                linhas.append("…(+mais entradas)")
                break
            barra = "/" if item.is_dir() else ""
            linhas.append(f"{item.name}{barra}")
            if item.is_dir() and len(linhas) < 40:
                try:
                    subs = sorted(x.name for x in item.iterdir())[:6]
                    if subs:
                        linhas += [f"  · {s}" for s in subs]
                except OSError:
                    pass
        return "\n".join(linhas) or "(pasta vazia)"
    except OSError as exc:
        return f"[erro ao listar: {exc}]"


def expandir(cfg, texto: str) -> str:
    """Bloco de anexos para a mensagem ("" se não há menções válidas)."""
    tokens: list[str] = []
    for m in _MENCAO_RE.finditer(texto or ""):
        tok = m.group(1)
        if tok and tok not in tokens:
            tokens.append(tok)
    if not tokens:
        return ""
    partes: list[str] = []
    nao_encontrados: list[str] = []
    usados = 0
    for tok in tokens[:_MAX_MENCOES]:
        p = _resolver(tok)
        if p is None or not p.exists():
            nao_encontrados.append(tok)
            continue
        if usados >= _MAX_BLOCO:
            partes.append(f"### @{tok} — [orçamento de anexos esgotado]")
            continue
        try:
            if p.is_dir():
                corpo = _listar_pasta(p)
                partes.append(f"### @{tok} — pasta\n```\n{corpo}\n```")
                usados += len(corpo)
            else:
                corpo = _ler_arquivo(p)
                if p.suffix.lower() in _EXT_CODIGO:
                    partes.append(f"### @{tok} — arquivo\n```\n{corpo}\n```")
                else:   # v7.2.1: texto puro SEM cercas (indentação) —
                        # não dispara D2/DLP como se fosse código
                    ind = "\n".join("    " + ln if ln.strip() else ""
                                    for ln in corpo.splitlines())
                    partes.append(f"### @{tok} — arquivo (texto)\n{ind}")
                usados += len(corpo)
        except Exception:  # noqa: BLE001
            nao_encontrados.append(tok)
    if not partes:
        return ""            # nada válido: o chat segue como conversa normal
    if nao_encontrados:
        partes.append("⚠ não encontrados: "
                      + ", ".join(f"@{t}" for t in nao_encontrados))
    return ("\n\n[📎 ANEXOS @ — conteúdo REAL lido do disco pelo Pluto]\n"
            + "\n".join(partes))
