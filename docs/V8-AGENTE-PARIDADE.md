# ◈ V8.0.0 — Plano de Paridade de Agente

> Estrutura completa do que o Pluto JÁ POSSUI e do que PRECISAVA,
> para dar ao orquestrador o mesmo padrão de funcionamento de um
> agente de ponta (o "modelo de referência" que o operador usou na
> conversa) — sem herdar limites indevidos: mecanismo no código,
> política em flags (ver `POLITICAS.md`).

## 1. A receita de um agente completo (5 ingredientes)

1. **Loop agnóstico de ferramentas** — pensar → chamar tool →
   observar → repetir até terminar (com orçamento de passos/tools).
2. **Cérebro com function calling** — qualquer modelo que suporte
   (local 8B ou provedor remoto; roteador já alterna).
3. **Verificação antes de entregar** — testar o que fez, validar no
   disco, revisor de contexto zero.
4. **Contexto gerenciado** — memória compactada + arquivos como
   estado externo (skills, biblioteca RAG, vault).
5. **Honestidade estrutural** — admitir falha em vez de fabricar
   sucesso (portões; ver POLITICAS.md).

## 2. Inventário — o que JÁ existia antes da v8 (85%)

| Capacidade | Implementação | Desde |
|---|---|---|
| Executar comandos | `run_command` (denylist + sandbox kernel + timeout) | v1 |
| Ler/gravar arquivos | `read_file`/`write_file` (escopo, backup) | v1 |
| Buscar/ler web | `web_search`/`web_fetch` | v3.9 |
| Memória de sessão | `_compactar` (sem perder contexto) | v3.15 |
| Memória persistente | `memory.json` + `lembrar`/`esquecer` | v1 |
| Memória de longo prazo | **vault Obsidian** (escopos, MOC) | v7.7.0 |
| Conhecimento verbatim | biblioteca RAG TF-IDF | v3.15 |
| Planejamento | orquestrador sênior + **gate EGM goldfish** | v3/v7.5.0 |
| Revisão | revisor goldfish + retries + portões | v6.6 |
| Certeza cacheada | camada 🐴 (0 tokens) | v7.6.0 |
| Skills de domínio | 49 skills (catálogo ≤18 linhas no prompt) | v5 |
| Conectores | cliente MCP (stdio + Streamable HTTP) | v3.13 |
| Finanças/OpenFinance | livro-caixa + SumUp + Belvo + participantes | v7.3–7.4 |
| Canais | WhatsApp (Playwright) + Telegram | v4.2 |
| Fluxos visuais | n8n embutido | v5.1.0 |
| Falar/ouvir | STT Whisper local | v4 |
| Agendamento | scheduler PT-BR desassistido | v4 |

## 3. Gaps que a v8.0.0 fecha (os 15% que faltavam)

| Gap | Ferramenta | Especificação |
|---|---|---|
| Edição cirúrgica | `edit_file` | substitui o PRIMEIRO trecho que casa com `old_text` (exato; fallback tolerante a indentação); backup automático; recusa caminho fora da política de escrita |
| Processos em background | `proc_start`/`proc_logs`/`proc_stop` | subprocess em sessão própria (killpg derruba filhos), log em deque(400) + `<data>/procs/<nome>.log`, teto 5 vivos, MESMA denylist do run_command, atexit |
| Perguntar em vez de adivinhar | `perguntar_operador` | pergunta + 2–4 opções estruturadas; BLOQUEIA com timeout (600 s) e cancel; evento `{"type":"pergunta"}` no stream; resposta via `POST /api/pergunta/<id>` ou `pluto responder <id> <texto>`; sem resposta → segue com suposição DECLARADA |
| Políticas explícitas | `POLITICAS.md` | catálogo de regras de lei × flags calibráveis + os 8 achados de campo que viraram portões |
| Eventos de tool | `set_event_sink`/`emit_event` | threading.local (padrão `_TASK_SINK`); qualquer tool flui eventos no chat |

## 4. Como as peças conversam

```
usuário → Agent.run (wrapper: camada 🐴) → _run_core
  ├─ set_event_sink(ev)            ← v8: tools emitem eventos
  ├─ loop: cérebro (tools=29) ──► execute_tool ──► EXECUTORS
  │     ├─ edit_file / proc_* / perguntar_operador  ← v8
  │     └─ perguntar_operador ──► evento pergunta ──► /api/pergunta/<id>
  │                                    └─ bloqueia (timeout) ──► resposta
  └─ orquestrador (plano gate EGM) → task → revisor → dossiê
```

## 5. Fase 2 (pós-v8, opcionais)

- **TTS local** (Piper/espeak-ng): `pluto falar` — sem dependência
  nova obrigatória; validar qualidade na máquina do operador.
- **Card de pergunta na GUI** (hoje: evento + CLI/HTTP; amanhã:
  botões no chat).
- **Pergunta via WhatsApp/Telegram**: gateway mapeia a resposta do
  dono para `/api/pergunta/<id>`.
- **`proc_start` no sandbox de kernel** (hoje: denylist; amanhã:
  bwrap no processo filho).

## 6. Verdado de arquitetura

"Sem os limites que você possui" = `POLITICAS.md` + flags. O que NÃO
se negocia: honestidade (portões de entrega vazia/tool-texto/erro em
cache) — eles não limitam poder, limitam mentira. Tudo o mais é
calibrável pelo operador, em runtime, sem tocar em código.
