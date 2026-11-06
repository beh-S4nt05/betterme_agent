# 🛡️ POLÍTICAS E LIMITES — catálogo e calibragem

> V8.0.0 · Mecanismo ≠ política: os MECANISMOS ficam no código; os
> LIMITES são flags que VOCÊ calibra. Cada linha abaixo diz o que faz,
> por que existe (muitas nasceram de falha real observada em campo) e
> o risco de afrouxar.

## Regras de segurança (NÃO são flags — são lei)

| Regra | O que faz | Por quê |
|---|---|---|
| Denylist de comandos (`is_dangerous`) | bloqueia `rm -rf /`, mkfs, dd p/ disco, shutdown, `curl\|sh`… | destruição irreversível |
| `touches_secrets` | comando/tool não lê `secrets/` | senhas nunca passam pelo modelo |
| D2 (`payload_sensivel`) | código/segredo no pedido → cérebro LOCAL | vazamento de propriedade |
| `_SCOPE_DENY` | task não põe workspace em /tmp, /proc, /etc… | sistema operacional |
| Backup antes de sobrescrever | toda escrita tem volta | retrabalho zero |
| Sandbox de kernel (bwrap+seccomp) | comandos rodam enjaulados quando disponível | defesa em profundidade |

## Flags calibráveis (config.yaml / `pluto config set`)

| Flag | Padrão | Faz | Nasceu de | Risco de afrouxar |
|---|---|---|---|---|
| `creation_approval` | true | aprovação do plano antes de task de criação | retrabalho do operador | execução sem revisão humana |
| `planejamento_verificado` | true | gate do plano (estrutural + goldfish) antes de virar task | EGM/plano torto vira execução | escopo errado vira task |
| `reviewer_on` | true | revisor sênior do resultado | entrega fraca passando | sem controle de qualidade |
| `orchestrator_on` | true | planejador decide rota | tudo virava task | pedidos simples custam caro |
| `fluxo_leve` | true | conversa pura pula planejamento+revisão | latência de "oi" | - |
| `certeza_on` | true | cache 🐴 de resposta validada | custo de pergunta repetida | resposta stale (TTL 30 d) |
| `review_fast_lane` | true | revisor não re-revisa fast lane | - | - |
| `confirm_dangerous` | true | comando arriscado pede confirmação na TUI | acidente | comando destrutivo sem freio |
| `sandbox` | true | bwrap+seccomp nos comandos | fuga de escopo | comando solto na máquina |
| `sandbox_home_read` | false | leitura da HOME dentro do sandbox | privacidade | agente lê documentos pessoais |
| `web_access` | true | tools web_search/web_fetch | - | - |
| `max_tool_calls` | 12 | orçamento de ferramentas por passo | loop infinito (T08) | custo/tempo sem teto |
| `max_steps` | - | passos do loop do agente | loop infinito | idem |
| `cmd_timeout` | - | teto do run_command (máx 600 s) | hang | - |
| `num_ctx` | - | contexto do modelo (use 8192 p/ modelos pequenos!) | prompt de pipeline > 4096 | modelo "trava" sem gerar |
| `auto_provider` | true | roteador usa provedor com chave | - | - |

## Achados de campo que VIRARAM portões (não desligue por sporte)

1. **Entrega vazia aprovada** (bateria de uso) → `entrega_vazia`
2. **Tool call impressa como TEXTO** (T0013 + bateria) → portão v6.6.1
3. **429 de rajada derrubava provedor** (llm7 real) → retry/backoff v7.2.0
4. **@menção de texto casava como código** (D2 falsa) → v7.2.1
5. **"gastei X, registre" era conversa** (tester real) → v7.6.1
6. **Cache gravava erro como certeza** (tester real) → v7.6.1
7. **Modelo manda frase em `command`** (audit real) → parser v7.6.1
8. **`Path("")` = CWD** (T224) → sentinel None no vault

## Para operar "sem os meus limites"

O operador que quiser autonomia máxima calibra: `creation_approval
false` + `confirm_dangerous false` + `sandbox false` + orçamentos
altos. Os portões de HONESTIDADE (entrega vazia, tool-texto, erro em
cache) não têm flag de propósito: eles não limitam o poder, limitam a
MENTIRA. Recomendação: mantenha-os sempre.
