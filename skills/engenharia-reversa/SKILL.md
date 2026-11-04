---
name: engenharia-reversa
description: Engenharia reversa com método — entender como um app, protocolo, formato ou sistema funciona por dentro antes de reimplementar ou integrar. Método REA de 5 passos com rótulos honestos visto, inferido e desconhecido. Use quando a tarefa envolver engenharia reversa, reverse engineer, desmontar, decompilar, como funciona por dentro, mecanismo interno, arquitetura de um app, formato de arquivo, protocolo, API não documentada, asar, binário, analisar aplicativo, reimplementar, clonar comportamento ou reconstruir um sistema.
---

# Engenharia reversa com método (REA — 5 passos)

Adaptação nativa do método do [REA — Reverse Engineer Anything](https://github.com/inematds/rea-engenharia-reversa)
(INEMA, MIT): engenharia reversa com agentes, **uma função por vez**,
ferramenta certa para o tipo de alvo e — o coração do método —
**rótulos de honestidade epistêmica**: tudo que você afirma é
`[visto]`, `[inferido]` ou `[desconhecido]`. Nunca chute disfarçado
de fato.

## Os 5 passos

1. **UMA função por vez.** Não tente entender o app inteiro de uma
   vez. Escolha a função que importa para o pedido (busca, sincronização,
   roteamento…) e siga só ela até o fim.
2. **Ferramenta pelo tipo de alvo.** App Electron/JS → análise estática
   do `.asar`/fonte (sem executar). Binário nativo → descompilador
   (Ghidra é grátis). Protocolo → captura de tráfego. Serviço web →
   documentação pública + endpoints reais. Código aberto → leia o
   código-fonte (o caso mais comum e mais barato).
3. **Resumo primeiro.** Antes de mergulhar nos detalhes, escreva o
   mapa em 5–10 linhas do que o alvo é e como a função estudada se
   comporta. O resumo guia onde cavar.
4. **Rotule tudo: visto / inferido / desconhecido.**
   - `[visto]` — você tem EVIDÊNCIA REAL (arquivo:linha, comando
     executado com a saída colada, captura, doc oficial citada).
   - `[inferido]` — dedução sua, com a linha de raciocínio declarada.
   - `[desconhecido]` — não sabe e admite. Desconhecido declarado
     vale mais que palpite confiante.
5. **Reconstruir e testar.** A prova da engenharia reversa é a
   reconstrução: reimplemente a função (ou o pedaço que importa) e
   TESTE contra o original. Reconstrução sem teste é hipótese.

## Formato da entrega

**evidência · mapa · limites · desconhecidos** — na ordem:

1. **Evidência** — o que foi examinado de verdade (caminhos, comandos,
   saídas, docs citadas com link).
2. **Mapa** — como a função funciona, passo a passo, cada afirmação
   rotulada `[visto]`/`[inferido]`.
3. **Limites** — até onde o estudo vale (versão examinada, o que não
   foi executado, o que muda entre versões).
4. **Desconhecidos** — lista honesta do que ficou sem resposta e como
   verificaria (comando/experiência que faltou).

## Cuidados (do REA, valem sempre)

- **Lei e licença**: muitas licenças proíbem ER. Terreno seguro:
  programas seus, código aberto, e o que você tem autorização para
  estudar. Reimplemente *padrões* com suas palavras — nunca copie
  código ou prompts de produto fechado.
- **Não é sandbox**: se executar o alvo, ele roda com as permissões do
  operador. Binário estranho pode enganar o agente — máquina isolada.
- **Muda todo dia**: declare a versão examinada; em alvo vivo, o mapa
  tem data de validade.

## Verificação

- A entrega tem as 4 seções (evidência, mapa, limites, desconhecidos)?
- Toda afirmação do mapa está rotulada [visto] (com evidência citada)
  ou [inferido] (com raciocínio declarado)?
- A versão/ambiente examinado está declarado nos limites?
- A função estudada foi UMA (não "o app inteiro")?
- Se houve reconstrução, ela foi testada e a saída real está colada?
- Nada foi copiado verbatim de produto fechado (padrões, com nossas palavras)?
