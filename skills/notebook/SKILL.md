---
name: notebook
description: Usar o notebook do operador (clone local do NotebookLM) — as fontes que ele passou (PDFs, scans via OCR, .md, .txt) como base do conhecimento. Responder fundamentado nas fontes com citação [n], gerar materiais de estudo (resumo, FAQ, guia, flashcards) e ensinar com a skill ensino-cbta. Use quando o pedido mencionar "notebook", "minhas fontes", "nas fontes", "no material", "meus documentos", "resuma o pdf", "flashcards", "guia de estudo" ou estudar o que o operador adicionou.
---

# Notebook — o conhecimento que o operador passou

O notebook é onde o operador deposita conhecimento para você USAR:
`betterme notebook add <arquivo>` (PDF, imagem escaneada, .md, .txt —
OCR automático quando precisar).

## Regras duras

1. **Citação é a lei**: responda sobre conteúdo do notebook SÓ com
   `notebook_buscar` — trecho verbatim + fonte, citando [n]. Algo que
   não está nas fontes → diga "não está nas fontes" (nunca invente).
2. **Fontes antes da web**: se o operador ensinou o assunto, o
   conhecimento DELE tem prioridade sobre conhecimento geral.
3. Ao adicionar fontes novas, o índice é refeito — nada se perde.

## Materiais (estruturas prontas)

`betterme notebook material resumo|faq|guia|flashcards [tema]` monta
o pedido com o contexto embutido. Ao gerar, siga a estrutura e a
REGRAS da skill ensino-cbta (competência primeiro, teor 75%,
exemplo antes de teoria longa):

- **resumo**: ideia central + até 5 blocos + 3 pontos de verificação
- **faq**: 6–10 perguntas reais de quem estuda, resposta curta com [n]
- **guia**: competência final + rota em 3–5 sessões + critério de
  domínio por sessão (PP → PLA)
- **flashcards**: 10–15 cartões "P: ... / R: ..." com [n]

## OCR (entrada de scans)

Imagens e PDFs escaneados viram texto no `add`: engine
**unlimited-ocr** (baidu/Unlimited-OCR — PDF inteiro numa passada,
multi-página com contexto cruzado) quando instalado; senão
**tesseract** (leve, CPU). Sem nenhum, o `add` devolve as instruções
exatas de instalação — repasse-as ao operador.
