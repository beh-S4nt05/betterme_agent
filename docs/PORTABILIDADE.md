# 🧭 PORTABILIDADE — dívida rastreada da suíte (Windows · macOS)

> **Contexto:** a suíte rodou pela 1ª vez em Windows e macOS no dia
> 07/11/2026, pelo CI recém-criado da V9.0.0 (run 42340204729, commit
> 96fa483). Em 103 tags manuais ela só tinha rodado em Linux — o CI
> expôs **43 testes** que assumem POSIX (38 no Windows, 5 no macOS).
>
> **Filosofia:** o mesmo "degradação honesta" do produto. Nenhum teste
> falha em silêncio e nenhum é escondido: os não-portados pulam
> **contados** (linha `RESULTADO: … · N pulado(s)`) e estão listados em
> `_NAO_PORTADOS` no `tests/run_all.py`. **Queimar a dívida = corrigir
> e remover da lista**; o CI nas 3 plataformas é a prova.

## Como portar (receita)

1. Corrija o teste (ou o produto, quando o defeito é real — ver tabela);
2. remova o nome de `_NAO_PORTADOS` em `tests/run_all.py`;
3. `pluto gates` local + push → o CI revalida nos 3 SOs.

O runner tem um guarda: nome na lista que não existe mais na suíte
**falha o pipeline** (dívida com nome de teste apagado = lista mentindo).

## Windows — 38 testes

Causas confirmadas na 1ª execução (log do job), agrupadas:

### A. Binários fake não executáveis — `WinError 193` (5)
O Windows só executa PE (.exe/.cmd/.bat); os fakes da suíte são scripts.
| Teste | Evidência |
|---|---|
| T164_multimodal_pipeline_com_binarios_fake | `ffmpeg falhou: [WinError 193] %1 is not a valid Win32 application` |
| T165_transcricao_indexada_e_citada_no_rag | idem |
| T171_fluxos_start_stop_com_n8n_fake | idem (n8n fake) |
| T170_fluxos_node_check_e_setup_honesto | Node ausente + dica de instalação POSIX (apt/nvm) |
| T227_procs_background | processos em background |

**Porta:** gerar `.cmd` wrapper no Windows (`@python fake.py %*`) ou
chamar via `[sys.executable, fake]`.

### B. Caminhos POSIX / backslash (≈10)
| Teste | Evidência |
|---|---|
| T17_claude_modo_leve_e_fallback_de_cli_antiga | `args.log` não achado em `C:\Users\RUNNER~1\…` |
| T151_arena_nao_escreve_no_disco | `'logs\\agent.log'` |
| T197_escopo_sticky_sessao · T202_mencoes_arroba · T209_mencoes_x_d2_falso_positivo · T29_watch_valida_e_persiste_campos · T41_secrets_protegidos_contra_o_agente · T108 · T109 · T116 · T120 | separador/normalização de caminho |

### C. Prompts e fixtures com exemplo POSIX (3)
| Teste | Evidência |
|---|---|
| T120_perguntar_caminho_do_projeto | espera `ex.: /media/Arquivos/projetos/…` |
| T121_mission_subtasks_sequenciais | idem no prompt do orquestrador |
| T113_folego_para_tarefas_de_projeto | `'budget'` (formato de saída) |

### D. Autostart / SO (4) — **defeito de produto a corrigir**
| Teste | Situação |
|---|---|
| T174_boot_autostart_nos_tres_sos | Windows usa Registro/Agendador, não systemd — boot deve instalar honestamente ou orientar |
| T98_diagnostico_em_uma_chamada | diagnóstico depende de `top`/`free` (Linux) — no Windows: `tasklist`/`wmic` |
| T166_sem_binario_nao_quebra_e_orienta | orientação assume gestor de pacote POSIX |
| T188_nunca_mudo_e_dados_reais | superfície muda de comportamento |

### E. Guards do Claude Code (2)
T38_guard_retry_modelo_recupera_e_executa · T39_guard_teimoso_hermes_executa_no_lugar
— mensagens/fluxo com `claude` ausente diferem no Windows.

### F. Update/instalação (3)
T81_update_end_to_end_v3110_local (`não consegui consultar o GitHub`) ·
T177_update_garante_comando_betterme · T178_instalacao_editavel_robusta.

### G. Demais (11) — triar na 1ª porta
T55 · T65 · T124 · T141 · T142 · T172 · T183 · T192 · T213 · T216 · T236.

## macOS — 5 testes

| Teste | Causa | Tipo |
|---|---|---|
| **T107_detectar_pasta_do_projeto** | `/etc` é symlink → `/private/etc`: o caminho RESOLVIDO escapa do `_SCOPE_DENY` (tools.py L767) — **o deny precisa resolver o caminho antes de checar (bug real, relevante p/ segurança)** | 🐛 produto |
| **T174_boot_autostart_nos_tres_sos** | macOS usa launchd, não systemd — boot deve degradar honestamente | 🐛 produto |
| **T98_diagnostico_em_uma_chamada** | Darwin não tem `free`; `top` é interativo (precisa `top -l 1`) | 🐛 produto |
| T166_sem_binario_nao_quebra_e_orienta | orientação POSIX (brew existe, mas a mensagem/detecção difere) | triar |
| T188_nunca_mudo_e_dados_reais | triar | triar |

**Overlaps** (falham nos dois SOs — portar primeiro, maior retorno):
T98 · T166 · T174 · T188.

## Prioridade sugerida

1. **T107 (macOS)** — bug de segurança do deny-list (produto);
2. **T174 · T98** — defeitos de produto nos 2 SOs;
3. Grupo A do Windows (WinError 193) — destrava 5 testes de uma vez;
4. Grupo B/C — normalização de caminho e fixtures;
5. O resto, queimando em ordem de overlap.

*docs/PORTABILIDADE.md · V9.0.0 P0 · fonte: run 42340204729 (logs dos
jobs windows-latest/macos-latest, 07/11/2026). Atualizar a cada porta.*
