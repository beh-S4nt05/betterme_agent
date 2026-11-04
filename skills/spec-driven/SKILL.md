---
name: spec-driven
description: Desenvolvimento guiado por especificação (adaptação nativa do spec-kit da GitHub, MIT) — SPEC com requisitos e critérios de aceite ANTES de codar, depois plano técnico, depois checklist de tasks numeradas, implementar na ordem e verificar no fim. Use quando a tarefa envolver projeto, app, aplicativo, software, funcionalidade, feature, api, website, serviço, módulo, biblioteca, crie, criar, construa, construir, monte, desenvolva, desenvolver, implemente, implementar, refatore, refatorar, arquitetura, especificação, requisitos, codebase, multi-arquivo, nova versão, typescript, javascript ou entrega de código com vários arquivos.
---

# Spec-driven: spec → plano → tasks → código verificado (spec-kit)

Adaptação nativa do Spec-Driven Development do [github/spec-kit](https://github.com/github/spec-kit)
(MIT) para o fluxo do Betterme. A regra de ouro: **código sem spec é
palpite caro** — primeiro o QUE e o PORQUÊ, depois o COMO, por último
o código.

## Quando usar o fluxo completo vs. leve

- **Task de projeto multi-arquivo / nova funcionalidade** → fluxo
  completo com artefatos gravados no projeto.
- **Task pequena (1 arquivo, 1 função)** → fluxo INLINE: monte
  spec→plano→tasks dentro da própria resposta (3–6 linhas) e execute.
  Não grave arquivos de processo para tarefas de 5 minutos.

## Fluxo completo (projeto/funcionalidade)

1. **SPEC** — grave `SPEC.md` no diretório do projeto com: objetivo em
   1 frase · requisitos funcionais numerados (RF-1, RF-2…) cada um com
   **critério de aceite verificável** (comando/entrada + saída
   esperada) · fora de escopo (o que NÃO será feito) · riscos.
   Ambiguidade crítica? Declare a suposição adotada em vez de parar.
2. **PLANO** — ANTES de decidir a técnica, examine o que já existe
   (list_dir + read_file nos arquivos-chave). Grave `PLANO.md`:
   arquivos a criar/alterar (caminho real) · decisões técnicas com
   1 justificativa · convenções do projeto que vai seguir.
3. **TASKS** — grave `TASKS.md`: checklist numerado em ordem de
   dependência (o que bloqueia o que vem antes), cada task pequena o
   bastante para caber numa execução, cada uma com a forma de
   verificação (`python3 x.py`, `node x.js`, `npm test`…).
4. **IMPLEMENTE** na ordem do checklist, riscando cada task concluída
   (`[x]`) e colando a evidência real de cada verificação.
5. **VERIFICAÇÃO FINAL** — rode o projeto inteiro de ponta a ponta com
   um exemplo real e cole a saída. Spec sem execução é papel.

## Regras do spec-kit que valem sempre

- Requisito sem critério de aceite verificável não é requisito — é
  desejo. Todo RF responde a "como eu PROVO que está pronto?".
- Plano que ignora o código existente é ficção — leia antes.
- Task grande demais vira duas tasks. Task sem verificação vira
  verificação adicionada antes de implementar.
- Escopo protegido: o que está no "fora de escopo" do SPEC não é
  tocado nem "por acidente" de refatoração.

## Verificação

- O SPEC foi gravado (ou montado inline) com RFs numerados e critério
  de aceite verificável em cada um?
- O PLANO cita arquivos REAIS do projeto (existentes ou criados)?
- O TASKS.md (ou checklist inline) foi executado na ordem, com
  marcação de progresso?
- A verificação final de ponta a ponta rodou e a saída real está
  colada na entrega?
- Nada do "fora de escopo" foi alterado?
