# -*- coding: utf-8 -*-
"""🔍 OCR — v8.1.0, com o Unlimited-OCR do Baidu (MIT).

"GitHub - OCR sem limites" = baidu/Unlimited-OCR: one-shot
long-horizon parsing — o PDF INTEIRO, multi-página, numa passada só
(contexto visual até 32k tokens), evolução do DeepSeek-OCR. Pesado
(torch + pesos de GB) — por isso a ARQUITETURA DE ENGINES, com
degradação honesta:

- engine `unlimited`: clone do repo com venv em
  `ocr_unlimited_dir` (config) — inferência multi-página num só
  pedido (cross-page context), como o repo documenta;
- engine `tesseract`: binário local (CPU, leve, offline) — página a
  página via pdftoppm para PDFs escaneados;
- `auto` (padrão): unlimited se instalado → tesseract → instruções
  claras de como instalar.

PDFs com camada de texto: pdftotext direto (OCR só quando precisa).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_EXT_IMG = {".png", ".jpg", ".jpeg", ".webp", ".tiff", ".tif", ".bmp",
            ".pnm", ".pgm"}

_RUNNER = """
import sys
from transformers import AutoModel, AutoTokenizer
tok = AutoTokenizer.from_pretrained("baidu/Unlimited-OCR")
model = AutoModel.from_pretrained("baidu/Unlimited-OCR", trust_remote_code=True)
texto, _ = model.infer_multi(tok, image_files=sys.argv[1:],
                             save_results=False)
sys.stdout.write(texto or "")
"""


def _run(argv: list[str], timeout: int = 300) -> str:
    try:
        r = subprocess.run(argv, capture_output=True, text=True,
                           timeout=timeout, check=False)
        return (r.stdout or "") if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _venv_python(d: Path) -> Path | None:
    for cand in (d / ".venv" / "bin" / "python",
                 d / "venv" / "bin" / "python"):
        if cand.exists():
            return cand
    return None


def unlimited_ok(cfg) -> bool:
    d = str(getattr(cfg, "ocr_unlimited_dir", "") or "").strip()
    if not d:
        return False
    p = Path(d).expanduser()
    return p.is_dir() and _venv_python(p) is not None


def tesseract_ok() -> bool:
    return shutil.which("tesseract") is not None


def disponiveis(cfg) -> dict:
    return {"unlimited": unlimited_ok(cfg),
            "tesseract": tesseract_ok()}


def _ocr_tesseract(img: Path, lang: str) -> str:
    return _run(["tesseract", str(img), "stdout", "-l", lang], timeout=120)


def _ocr_unlimited(cfg, imgs: list[Path]) -> str:
    d = Path(str(getattr(cfg, "ocr_unlimited_dir", ""))).expanduser()
    py = _venv_python(d)
    if py is None:
        return ""
    return _run([str(py), "-c", _RUNNER] + [str(i) for i in imgs],
                timeout=1800)


def _pdf_imgs(pdf: Path, destino: Path) -> list[Path]:
    """PDF → imagens por página (pdftoppm do poppler)."""
    if not shutil.which("pdftoppm"):
        return []
    destino.mkdir(parents=True, exist_ok=True)
    _run(["pdftoppm", "-r", "200", "-png", str(pdf),
          str(destino / "pg")], timeout=600)
    return sorted(destino.glob("pg-*.png"))


def extrair(cfg, caminho: str, _engines=None) -> dict:
    """Texto de um arquivo (txt/md direto; pdf com camada de texto;
    imagem/PDF escaneado via OCR). Devolve {texto, engine, notas} —
    nunca lança; sem engine, devolve instruções de instalação."""
    p = Path(caminho).expanduser()
    res = {"texto": "", "engine": "", "notas": []}
    if not p.exists():
        res["notas"].append(f"arquivo não encontrado: {p}")
        return res
    ext = p.suffix.lower()
    engines = _engines or disponiveis(cfg)
    lang = str(getattr(cfg, "ocr_lang", "por+eng") or "por+eng")
    pref = str(getattr(cfg, "ocr_engine", "auto") or "auto")

    if ext in (".txt", ".md", ".markdown", ".csv", ".log", ""):
        try:
            res["texto"] = p.read_text(encoding="utf-8",
                                       errors="replace")
            res["engine"] = "texto"
        except OSError as exc:
            res["notas"].append(str(exc))
        return res

    if ext == ".pdf":
        if shutil.which("pdftotext"):
            txt = _run(["pdftotext", "-layout", str(p), "-"], timeout=120)
            if len(txt.strip()) >= 80:        # tem camada de texto
                res["texto"], res["engine"] = txt, "pdftotext"
                return res
            res["notas"].append("PDF sem camada de texto — indo para OCR")
        tmp = p.parent / f".{p.stem}-ocr"
        imgs = _pdf_imgs(p, tmp)
        if not imgs:
            res["notas"].append("pdftoppm ausente — instale poppler "
                                "(apt install poppler-utils)")
            return res
    elif ext in _EXT_IMG:
        imgs = [p]
    else:
        res["notas"].append(f"extensão sem suporte: {ext}")
        return res

    if pref in ("unlimited", "auto") and engines.get("unlimited"):
        txt = _ocr_unlimited(cfg, imgs)
        if txt.strip():
            res["texto"], res["engine"] = txt, "unlimited-ocr (baidu)"
            return res
        res["notas"].append("unlimited-ocr não retornou texto — "
                            "verifique pesos/dependências do clone")
    if pref != "unlimited" and engines.get("tesseract"):
        pedaços = [_ocr_tesseract(i, lang) for i in imgs]
        txt = "\n\n".join(x for x in pedaços if x.strip())
        if txt.strip():
            res["texto"], res["engine"] = txt, "tesseract"
            return res
    res["notas"].append(
        "nenhum engine de OCR disponível. Unlimited-OCR (recomendado): "
        "git clone https://github.com/baidu/Unlimited-OCR && cd "
        "Unlimited-OCR && python -m venv .venv && .venv/bin/pip install "
        "torch torchvision transformers Pillow pymupdf einops — e aponte "
        "betterme config set ocr_unlimited_dir <pasta>. Leve: apt install "
        "tesseract-ocr tesseract-ocr-por poppler-utils.")
    return res


# ── v8.2.0: instaladores NATIVOS (o app instala, com confirmação) ─────────

_GESTORES = {                       # gestor → comando de instalação
    "apt-get": "sudo apt-get install -y tesseract-ocr "
               "tesseract-ocr-por poppler-utils",
    "dnf": "sudo dnf install -y tesseract tesseract-langpack-por "
           "poppler-utils",
    "pacman": "sudo pacman -S --noconfirm tesseract tesseract-data-por "
              "poppler",
    "brew": "brew install tesseract tesseract-lang poppler",
}


def _pergunta(pergunta: str) -> str:
    """Confirmação [s/N] — o padrão é NÃO: nada roda silencioso."""
    try:
        return input(f"{pergunta}\n[s/N] ").strip().lower()
    except EOFError:
        return "n"


def _exec_cmd(comando: list):
    r = subprocess.run(comando, capture_output=True, text=True,
                       check=False)
    return r.returncode, ((r.stdout or "") + (r.stderr or ""))


def instalar_tesseract(_which=None, _confirm=None, _exec=None) -> dict:
    """v8.2.0: instalador NATIVO do tesseract — detecta o gestor de
    pacotes (apt-get/dnf/pacman/brew), mostra o comando exato e SÓ
    roda com confirmação [s/N]. Nunca silencioso; falha devolve o
    comando manual. Tudo injetável p/ teste."""
    _which = _which or shutil.which
    _confirm = _confirm or _pergunta
    _exec = _exec or _exec_cmd
    if _which("tesseract") and _which("pdftoppm"):
        return {"ok": True, "ja_instalado": True}
    gestor = next((g for g in _GESTORES if _which(g)), None)
    if not gestor:
        return {"erro": "gestor de pacotes não detectado "
                "(apt-get/dnf/pacman/brew) — instale manualmente: "
                "tesseract + dados de português + poppler-utils"}
    cmd = _GESTORES[gestor]
    if _confirm(f"Instalar tesseract via {gestor}?\n  $ {cmd}") != "s":
        return {"cancelado": True, "comando": cmd}
    rc, saida = _exec(cmd.split())
    if rc != 0:
        return {"erro": f"falha ao instalar (rc={rc}) — rode "
                f"manualmente: {cmd}\n{saida.strip()[:400]}"}
    return {"ok": True, "executado": True, "comando": cmd}


def instalar_unlimited(cfg, destino: str = "", _confirm=None,
                       _exec=None) -> dict:
    """v8.2.0: instalador NATIVO do unlimited-ocr (baidu/Unlimited-OCR,
    MIT): clone + venv + deps pinned. AVISA os ~2–6 GB antes e só roda
    com confirmação; ao concluir registra `ocr_unlimited_dir`."""
    import sys as _sys
    _confirm = _confirm or _pergunta
    _exec = _exec or _exec_cmd
    destino = str(destino or
                  Path(cfg.data_dir) / "engines" / "unlimited-ocr")
    pergunta = (f"Instalar unlimited-ocr (baidu/Unlimited-OCR) em "
                f"{destino}?\n  ⚠ baixa ~2–6 GB (repo + deps; pesos "
                "baixam no 1º uso) e leva vários minutos")
    if _confirm(pergunta) != "s":
        return {"cancelado": True,
                "nota": "dica: o tesseract é leve e já cobre bastante "
                "— betterme ocr instalar tesseract"}
    passos = [
        ["git", "clone", "https://github.com/baidu/Unlimited-OCR.git",
         destino],
        [_sys.executable, "-m", "venv", f"{destino}/.venv"],
        [f"{destino}/.venv/bin/pip", "install",
         "torch==2.10.0", "torchvision==0.25.0", "transformers==4.57.1",
         "Pillow==12.1.1", "pymupdf", "einops"],
    ]
    for passo in passos:
        rc, saida = _exec(passo)
        if rc != 0:
            return {"erro": f"falha no passo `{' '.join(passo)}` "
                    f"(rc={rc}) — rode manualmente e repita\n"
                    f"{saida.strip()[:400]}"}
    cfg.update({"ocr_unlimited_dir": destino})
    return {"ok": True, "destino": destino}
