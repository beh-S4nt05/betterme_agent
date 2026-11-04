# Comparativo dos clientes de Agente de IA — pontos-chave × Betterme

Pesquisa de out/2026 (v7.0.0): o que cada client líder faz de melhor,
e onde cada ponto vive no Betterme. Regra: **padrão, não produto** —
extraímos a engenharia, mantemos local-first e MIT.

Legenda: ✅ já existia · 🆕 entrou na v7.0.0 · ➖ fora de escopo (com motivo)

| Client | Pontos-chave | No Betterme |
|---|---|---|
| **Claude Code** (Anthropic) | 104 slash commands como superfície de comando; hooks; subagents; Agent Skills; modos de permissão + sandbox; memória automática (notas de projeto/usuário) | 🆕 dispatcher único de `/comandos` (comandos.py) · ✅ portões+revisor como hooks · ✅ specialists.py (subagents) · ✅ skills (46) · ✅ sandbox D2 · ✅ learning.py + memória |
| **Codex CLI** (OpenAI) | sandbox por padrão (3 modos × política de aprovação); AGENTS.md; MCP; cloud paralelo | ✅ sandbox + portões · ✅ HERMES.md (init) · ✅ mcp_client · ➖ cloud próprio (usamos providers/omniroute em vez de nuvem proprietária) |
| **Cursor** | **@menções** de arquivo/pasta; Composer multi-arquivo; modos Plan/Ask/Agent; auto-rota multi-modelo | 🆕 **@menções** (mencoes.py — lê o disco e anexa) · ✅ etapas focadas + portão de plano · ✅ roteador multi-provider |
| **Cline** | modos **Plan/Act**; BYOK 30+ providers + local; auto-approve configurável; subagentes paralelos | ✅ portão do plano (Plan) → executor (Act) · ✅ BYOK + Ollama · ✅ autonomia em 3 níveis · ✅ specialists |
| **Aider** | git-nativo (auto-commit); **repo-map** do codebase; lint/teste após cada mudança com auto-correção | ✅ grafo.py (mapa AST do repo) · ✅ skill codigo-verificado (roda, lê saída, corrige) · ✅ contratos/commits disciplinados |
| **OpenCode** | agente Plan **read-only** vs Build; **subagents invocados com @**; LSP + MCP; 75+ providers; `opencode serve` | ✅ TIPO_LEITURA no plano · 🆕 @ (menções) · ✅ MCP · ✅ providers+omniroute · ✅ `betterme server` (GUI+API) |
| **Goose** (Block/LF) | MCP-nativo (70+ extensões); 15+ providers; recipes (templates YAML); CLI+desktop+API; agente universal (além de código) | ✅ MCP · ✅ providers · ✅ skills+fluxos n8n como recipes · ✅ CLI+GUI+API · ✅ tarefas de sistema, não só código |
| **Gemini CLI** (Google) | tier grátis (60 rpm/1k dia); Search grounding; MCP; modo não-interativo p/ scripts | ✅ gemini no roteador (1.500/dia grátis) + llm7 sem chave + omniroute keyless · ✅ web_search/fetch · ✅ `betterme run` headless |
| **Antigravity** (Google) | a unidade de revisão é o **artefato**: plano antes de executar, evidência, entrega auditável | ✅ v6.8.0 — dossiê de task (PLANO/EVIDÊNCIA/ENTREGA) + portão de plano |
| **Plandex** | **decomposição** da task em partes reguladas; sandbox de diff; 2M ctx | ✅ v6.6.0 — fluxo leve N2 (etapas focadas, 1 revisão no consolidado) · ➖ diff sandbox (nosso portão de entrega cobre o mesmo risco) |
| **spec-kit** (GitHub) | SDD: SPEC → plano → tasks → implementar → verificar | ✅ v6.7.0 — skill spec-driven (RFs com critério de aceite verificável) |

## O objetivo do operador, traduzido em arquitetura

> "Não quero ser limitado pelo meu hardware… realizar tarefas quaisquer
> e entregar em tempo hábil (prazos curtos), entendendo a atividade por
> completo, parametrizando e gerando as atividades."

1. **Não ser limitado pelo hardware** = roteador cérebro (v6.3.0):
   chave grátis guardada → nuvem automática com fallback local;
   sem chave → llm7 anônimo/omniroute keyless (`provider guia`).
2. **Prazos curtos** = 🆕 `/prazo <min>` (v7.0.0): contagem visível,
   revisão apertada abaixo de 10 min (sem refazer — entrega com
   ressalva honesta) e estado do roteador sempre informado.
3. **Entender por completo + parametrizar** = skill spec-driven
   (v6.7.0): SPEC com RFs e critérios de aceite ANTES de codar.
4. **Gerar as atividades** = fluxo leve N2 (v6.6.0): decomposição em
   etapas focadas com contexto acumulado.
5. **@ e /** = 🆕 v7.0.0: anexos reais no pedido e comandos de
   zero-token — a interface dos clientes líderes.

## O que ficou de fora (honestidade)

- **Nuvem proprietária de execução** (Codex cloud, Cursor cloud agents):
  o código e os dados ficam na máquina do operador (local-first, D1).
- **IDE própria**: o Betterme é CLI+GUI+API, não um fork de editor.
- **Auto-commit em toda edição** (Aider): commit disciplinado fica a
  cargo do operador/contratos (single-writer).

*Fontes: documentação pública e comparações 2026 (toolsbase.dev,
pinggy.io, ayautomate.com, o-mega.ai, aipromptshub.co) + leitura
direta dos repositórios (spec-kit, Plandex, prompts patterns).*
