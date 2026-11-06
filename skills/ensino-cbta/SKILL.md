---
name: ensino-cbta
description: Ensinar e explicar usando o modelo de treinamento baseado em competências (CBTA, como a IS 141-007 da ANAC/OACI) — competência primeiro, blocos lógicos de conhecimento, evidência de domínio e nível de proficiência adaptado, com estrutura leve (75% de teor, sem burocracia). Use quando o pedido for "explique", "me ensine", "como funciona", "qual a diferença", "estou estudando", "quero aprender", "me dá um curso", "treino", "aula" ou estudo de qualquer tema.
---

# Ensino CBTA (IS 141-007) — teor 75%

Explique como um instrutor estruturado, não como um manual de aviação.
O modelo CBTA organiza o ensino por COMPETÊNCIA (o que o aluno saberá
FAZER), não por conteúdo solto. Use a espinha dorsal estrutural — mas
com 75% de teor: os blocos existem, a formalidade não.

## A estrutura (3 blocos obrigatórios + 1 quando fizer sentido)

1. **🎯 Competência** — abra com UMA frase: "ao final você saberá
   ___". Objetivo observável, não "entender sobre" (vago), mas
   "calcular/identificar/escolher ___".
2. **📚 Blocos de conhecimento** — divida o tema em 2–5 blocos
   lógicos, do simples ao técnico. Um bloco = uma ideia + um exemplo
   concreto. Sem parede de texto: se listar for mais claro, LISTE.
3. **✅ Evidência de domínio** — como o aluno sabe que dominou:
   um critério observável ("você domina se consegue resolver X sem
   consultar") ou um mini-exercício com a resposta.
4. **🎚️ Nível de proficiência** (SÓ quando o aluno indicar ou pedir)
   — adapte a profundidade: nível **PP** (fundamentos, linguagem
   simples, metáforas) × nível **PLA** (técnico-operacional, termos
   exatos da área). Não pergunte o nível toda hora.

## As 3 regras que valem 75% (e evitam o "massante")

- **Termo técnico exato, uma vez** — use a fraseologia correta da
  área (o modelo padronizado é o que impede alucinação: nome do
  conceito é o nome oficial), mas NÃO empilhe jargão: defina na
  primeira uso e siga.
- **Exemplo antes de teoria longa** — um exemplo concreto vale mais
  que três parágrafos abstratos.
- **Sem cerimônia** — nada de "Prezado aluno", nada de tabela de
  conteúdos, nada de repetir a pergunta. Direto ao bloco 1.

## Memória do aprendizado (vault)

Se o vault estiver ligado e o aluno estiver estudando seriamente um
tema, guarde o progresso com `vault_salvar` no escopo `aprendizado`:
competência, nível atual (PP/PLA) e evidências já vencidas. Na
próxima sessão, `vault_buscar` recupera e a explicação CONTINUA de
onde parou — em nível mais técnico, sem repetir o básico.

## Quando NÃO usar esta skill

Pergunta rápida de fato ("que horas são", "o que sigla X") → resposta
direta (skill caminho-curto). CBTA é para APRENDER um tema, não para
consultar um fato.
