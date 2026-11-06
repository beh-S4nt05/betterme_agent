# ◈ Pluto Agente

**Agente pessoal que opera seu dispositivo — Windows | macOS | Linux (x86-64 e
ARM64) — via terminal, GUI web, Telegram e WhatsApp, com cérebro local
(Ollama + hermes3) e roteador opcional de provedores grátis.**

O Pluto conversa, diagnostica e opera sua máquina executando comandos,
lendo/gravando arquivos e inspecionando o sistema. **Local-first**: memória e
dados pessoais ficam na sua máquina, sempre. Se você guardar uma chave de
provedor grátis (Groq, Mistral, Gemini…), o **roteador automático** usa o
cérebro rápido por padrão com fallback local — e código/segredos nunca saem
(regra D2, DLP no transporte).

A **GUI web** liga/desliga agente e Ollama com um clique, mostra log ao vivo,
chat com ferramentas visíveis na hora, tarefas agendadas, memória, skills,
receitas, doctor e editor de automações n8n.

**v8.3.0** · 236 testes · CHANGELOG com todo o histórico. Limites calibráveis: POLITICAS.md.

```
                        ┌─────────────────────────────┐
   navegador ──────────►│  GUI web (Flask)  :8080     │
   (qualquer aparelho)  │  ▸ liga/desliga agentes     │
                        │  ▸ log ao vivo · chat       │
                        │  ▸ fila de tarefas · ajustes│
                        └──────────┬──────────────────┘
                                   │ gerencia (spawn/signals)
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
   ┌────────────────────┐ ┌──────────────────┐ ┌─────────────────┐
   │ agent daemon       │ │ CLI terminal     │ │ Ollama          │
   │ ▸ fila de tarefas  │ │ pluto chat/run  │ │ ollama serve    │
   │ ▸ heartbeat+log    │ │ pluto agent …   │ │ modelo: hermes3 │
   └─────────┬──────────┘ └────────┬─────────┘ └────────▲────────┘
             │      ferramentas (bash, arquivos, diagnóstico)
             └──────────► seu dispositivo ◄──────────────┘
```

---

## ⚡ Início rápido

```bash
python3 install.py          # qualquer SO: venv + CLI + guia do Ollama
pluto doctor             # checa dispositivo, cérebro, modelo, segurança
pluto server             # GUI em http://127.0.0.1:8080
```

**Tudo de uma vez** (ditado por voz, WhatsApp, Ollama, modelo e n8n):

```bash
python3 install.py --full   # +--skip-stt/--skip-n8n/--skip-playwright
```

Acesso de outros aparelhos na rede (**sempre com senha!**):

```bash
pluto server --host 0.0.0.0 --port 8080 --token minha-senha-segura
```

Para instalar como serviço que sobe junto do sistema:

```bash
./install.sh --with-systemd        # pluto-server + pluto-agent no systemd
```

### Requisitos

| Item | Valor |
|---|---|
| SO | Windows · macOS · Linux (x86-64 e ARM64; systemd quando disponível) |
| Python | 3.9+ |
| RAM | 8 GB (`hermes3:3b`) · 12 GB+ (`hermes3:8b`) · 64 GB+ (`hermes3:70b`) |
| Disco | ~5 GB (modelo 8b) + 1 GB (Pluto) |

### Instalação universal (qualquer dispositivo — Windows | macOS | Linux)

```bash
python3 install.py    # venv + pip/setuptools + pluto + guia do Ollama
pluto doctor       # checa dispositivo (SO, arquitetura, RAM), Ollama, modelo
pluto server       # GUI em http://127.0.0.1:8080
```

`install.py` é Python puro — roda em PC, notebook, Mac (Intel/Apple
Silicon), mini PC e Raspberry Pi (ARM64). O Ollama, se faltar, é
orientado por SO:

| Sistema | Ollama |
|---|---|
| Linux | `curl -fsSL https://ollama.com/install.sh \| sh` |
| macOS | `brew install ollama` (ou o app de ollama.com) |
| Windows | `OllamaSetup.exe` de ollama.com (ou `winget install Ollama.Ollama`) |

No Linux o `install.sh` clássico (com systemd opcional) segue
disponível. Instalação manual: `python3 -m venv .venv` →
`pip install --upgrade pip setuptools` → `pip install -e .`.

---

## 🧠 Cérebro com roteador automático (v6.3+)

Guarde uma chave grátis (`pluto provider set groq` + chave) e o agente
**usa o provedor rápido por padrão** — com fallback local se falhar.
Pedido com código/segredo? Fica no Ollama local (regra D2: análise de
código nunca sai). `pluto provider off` = 100% local. Cada resposta
registra no log qual cérebro usou; `pluto doctor` mostra o estado.

**Sem chave nenhuma?** Dois caminhos: `pluto provider guia` (onde pegar
cada chave grátis em 2 min) e **`pluto omniroute setup && pluto
omniroute start`** — gateway local open-source que roteia para pools
gratuitos keyless (requer Node 23+ e onboarding 1× no dashboard).
**Valide tudo com `pluto provider test`** — 1 completion real por
provedor, com latência e veredito. Provedores com rate limit têm
**retry automático com backoff** (v7.2.0) — rajadas de 429/5xx não
derrubam mais a tarefa para o fallback local.

Peça **"engenharia reversa de X"** e o agente segue o método REA
(rótulos *visto/inferido/desconhecido*, entrega com evidência, mapa,
limites e desconhecidos) — o estudo completo do n8n está em
`docs/ENGENHARIA-REVERSA-N8N.md`.

No chat (GUI e terminal) use **@ e /**: `revise @src/app.py e o
@README.md` anexa o conteúdo REAL dos arquivos ao pedido; `/prazo 15`
liga o modo prazo (contagem + revisão apertada + estado do roteador
nuvem/local); `/dossie T0012` abre o artefato da task; `/ajuda`
lista tudo.

## 🧩 Orquestração inteligente (v6.6+) · plano VERIFICADO (v7.5.0)

Cadeia completa com loop de melhoria em cada ponto (inspirada no
Elephant-Goldfish Model do Google): **orquestrador → decisão/escopo →
task → realização → verificação → resultado real**. O plano passa por
um GATE antes de virar task — estrutural (0 tokens) para toda execução
e revisão goldfish (contexto zero, 1 chamada pequena) para criações;
plano reprovado é replanejado 1× ANTES da execução. O revisor de
resultado já era goldfish (prompt fresco: objetivo + critérios +
resultado, sem histórico). Pedidos simples seguem na fast lane (0
chamadas extras) — como o próprio EGM recomenda. Desligue com
`pluto config set planejamento_verificado false`.

**Camada de certeza (v7.6.0, conceito ponytail)**: pergunta repetida
com resposta já validada é respondida com **0 chamadas ao modelo**
(nota 🐴 no chat) — cache local conservador (só 1º turno, pergunta
estável de 8–80 chars, resposta sem ferramentas, LRU 200/TTL 30 d;
perguntas voláteis como "que horas são" nunca cacheiam). Junto, regra
dura de **CONCISÃO** no prompt: resposta no tamanho do pedido, sem
preâmbulo — listas em vez de prosa. `config set certeza_on false`
desliga.

Toda tarefa passa pelo **fluxo adaptativo de 3 níveis**: conversa →
resposta direta (1 chamada ao cérebro, planejamento pulado); tarefa →
planner → executor → revisão; **complexa → decomposta em etapas
focadas** com contexto acumulado e 1 revisão única no consolidado
(padrão Plandex, nativo).

- **🗂️ Dossiê de task** — cada task produz um artefato auditável em
  `~/.pluto/dossies/T000N.md`: **PLANO** (aprovado antes de
  executar) · **EVIDÊNCIA** (cada ferramenta com hora) · **ENTREGA**
  (veredito do revisor + texto final). Consulta: `pluto dossie
  T0001` ou `/dossie T0001` no chat (modelo Antigravity).
- **⏱ Modo prazo** — `/prazo 15` no chat: contagem visível, estado do
  roteador (nuvem/local) e revisão apertada em prazos curtos
  (reprovação entrega com ressalva honesta, sem refazer).
- **📎 @menções** — `revise @src/app.py e o @README.md (código anexado fica no cérebro local — regra D2; texto vai ao externo)`: o conteúdo
  REAL dos arquivos é lido do disco e anexado ao pedido (padrão
  Cursor/OpenCode). `/ajuda` lista todos os comandos.
- **🔬 Engenharia reversa com método** — peça "engenharia reversa de
  X" e o agente segue o método REA (rótulos *visto/inferido/
  desconhecido*, entrega com evidência·mapa·limites·desconhecidos).
  O estudo completo do n8n: `docs/ENGENHARIA-REVERSA-N8N.md`.
- **✦ Skills de processo** — `spec-driven` (SPEC→PLANO→TASKS antes de
  codar, do spec-kit da GitHub), `disciplina-agente` (as 7 regras dos
  agentes de código de produção), `engenharia-reversa` (método REA).

## ⚙ Automações com n8n (v6.3+)

`pluto fluxos setup|start` sobe um n8n **local** (grátis, uso
pessoal). Do chat: "quais são meus fluxos?" e "dispare o X". Do n8n: POST
em `/api/hooks/<id>` dispara o agente. Guia completo com templates
prontos: **N8N_PASSOAPASSO.md**.

## 📚 Notebook — clone local do NotebookLM + OCR (v8.1.0 · v8.2.0 nativo)

Passe ensino/conhecimento para a IA usar nos seus processos:

```bash
pluto notebook add manual.pdf      # PDF, scan (OCR), .md, .txt
pluto notebook add pasta/          # lote inteiro
pluto notebook perguntar "o que é CAVOK?"   # o CÉREBRO DO APP
                                      # responde com citação [n] +
                                      # rodapé de fontes (nativo)
pluto notebook perguntar "..." --raw        # só os trechos verbatim
pluto notebook material guia metar # GERA com o cérebro (CBTA) e
                                      # SALVA em notebook/materiais/
pluto notebook materiais           # lista os materiais salvos
pluto notebook listar|remover|status
```

- **Nativo de verdade (v8.2.0)**: `perguntar` e `material` usam o
  cérebro do próprio app (Agent + skills) — nada de "copie e cole no
  chat". Cérebro indisponível? Fallback honesto: trechos verbatim +
  aviso explícito, nunca resposta inventada nem erro salvo como
  material.
- **RAG determinístico** (mesmo da biblioteca, TF-IDF stdlib) —
  citação é a lei: o que não está nas fontes, o agente DIZ que não
  está (skill `notebook`, 50ª + tool `notebook_buscar`).
- **OCR sem limites**: engine **unlimited-ocr** (baidu/Unlimited-OCR,
  MIT — PDF inteiro multi-página numa passada, contexto cruzado) quando
  instalado (`ocr_unlimited_dir`); degrada para **tesseract** (leve,
  CPU); sem nenhum, instruções exatas de instalação. PDFs com camada
  de texto nem usam OCR (pdftotext direto).
- **Instalador nativo (v8.2.0)**: `pluto ocr instalar tesseract`
  detecta o gestor de pacotes (apt/dnf/pacman/brew), mostra o comando
  e só roda com confirmação [s/N]; `pluto ocr instalar unlimited`
  avisa os ~2–6 GB antes de clonar. Nunca nada silencioso.
- Sem "áudio overview" do NotebookLM (fase futura: TTS local).

## 🧰 Paridade de agente completo (v8.0.0)

O orquestrador ganha o padrão de funcionamento dos agentes de ponta —
29 ferramentas, mecanismos no código e **política em flags**
(`POLITICAS.md` cataloga cada limite, por que existe e como calibrar):

- **`edit_file`** — edição cirúrgica (casa o trecho exato ou
  tolerante a indentação; backup automático; 1ª ocorrência)
- **`proc_start` / `proc_logs` / `proc_stop`** — processos em
  background (servidor, watcher, suíte longa) sem travar o agente;
  log em memória + arquivo; teto 5; mesma denylist do run_command
- **`perguntar_operador`** — pergunta ESTRUTURADA com opções quando o
  pedido é ambíguo, bloqueia pela resposta (evento no chat;
  `pluto responder <id> <texto>` ou `POST /api/pergunta/<id>`);
  sem resposta → segue com a suposição DECLARADA
- **Estrutura completa** do que existe × o que faltava:
  `docs/V8-AGENTE-PARIDADE.md` (inventário + especificações + fase 2)

## 🗄️ Vault Obsidian + ensino CBTA (v7.7.0)

**Memória de longo prazo em ARQUIVOS, não em RAM**: `pluto vault
usar ~/Obsidian/SeuVault` liga o vault — o agente passa a guardar
conhecimento duradouro em `.md` organizado por **escopos**
(`memoria` · `projetos` · `conhecimento` · `aprendizado`), com
frontmatter, tags e índice MOC com wikilinks (nativo do Obsidian —
você lê e edita tudo). Tools `vault_salvar` / `vault_buscar` (busca
devolve trecho VERBATIM com fonte). Prefere Notion? O mesmo modelo
cabe no Notion MCP (`mcp_servers`).

**Skill `ensino-cbta` (49ª)**: explicações no modelo de treinamento
por competências (CBTA / IS 141-007 ANAC-OACI) com **teor 75%** —
competência primeiro ("ao final você saberá ___"), blocos lógicos de
conhecimento, evidência de domínio e nível de proficiência adaptado
(PP = fundamentos · PLA = técnico-operacional), SEM burocracia:
termo técnico exato uma vez, exemplo antes de teoria longa, zero
cerimônia. Progresso de estudo vai pro escopo `aprendizado` do
vault — a próxima sessão continua de onde parou.

## 💰 Finanças — controle de gastos (v7.3.0)

Livro-caixa LOCAL (`<data_dir>/financas/`, nunca no repo) para PF e PJ:

```bash
pluto financas                      # painel do mês: entradas, saídas,
                                       # saldo, top categorias, faturas
pluto financas lancar 35 "almoço"   # registro manual (ou no chat:
                                       # "gastei 35 no almoço")
pluto financas importar bb.csv --conta bb     # extrato CSV do BB,
                                       # Bradesco ou SumUp (formatos por
                                       # família de coluna; reimportar
                                       # não duplica — id estável)
pluto financas fatura 1850 15/11 bradesco    # vencimento no painel
pluto financas sumup setup <api-key>         # uma vez (secrets/ 600)
pluto financas participantes sumup   # quem participa do Open
                                       # Finance? (lista OFICIAL, com
                                       # papel da instituição, cache 24 h)
pluto belvo guia                     # Open Finance só-leitura via
pluto belvo token <t>                # Belvo MCP (grátis, regulado)
pluto financas sumup sync           # vendas → entradas (API titular)
```

No chat, o agente registra com as tools `financas_lancar` /
`financas_painel` (números com Decimal — o modelo nunca calcula).
Extrato do SumUp **+** sync da API dobra entradas → importe com
`--so-saidas`. O `belvo status` valida a conexão com handshake MCP REAL
(`initialize` contra o servidor da Belvo). Nota: o acesso pelo Belvo
exige conta grátis + consentimento no app do banco (12 meses,
revogável) — o servidor de autorização deles só aceita aplicações
registradas, por isso o token vem da jornada do próprio operador.
Meios por banco: SumUp = API de vendas + extrato CSV ·
BB = API de extrato (portal do desenvolvedor) · Bradesco PF = extrato
CSV + e-mail da fatura · limites de cartão/DDA do BB sem via limpa:
registro manual ou agregador MCP (ex.: Belvo MCP, grátis/leitura).

## 🖥 CLI (terminal)

| Comando | O que faz |
|---|---|
| `pluto chat` | chat interativo com o agente no terminal |
| `pluto run "tarefa"` | executa uma tarefa única (ex.: `pluto run "mostre uso de disco"`) |
| `pluto server` | sobe a GUI web (`--host --port --token`) |
| `pluto daemon` | roda o daemon do agente em primeiro plano |
| `pluto status` | status do agente + Ollama |
| `pluto agent start\|stop\|restart\|status` | **liga/desliga** o agente |
| `pluto ollama start\|stop\|status` | **liga/desliga** o servidor Ollama |
| `pluto ollama pull [modelo]` | baixa um modelo |
| `pluto models` | lista modelos locais |
| `pluto tasks` | fila de tarefas e resultados |
| `pluto doctor` | diagnóstico do ambiente (dispositivo, cérebro, n8n…) |
| `pluto provider list\|set\|test\|guia\|off` | chaves grátis, roteador e **teste real** de cada provedor |
| `pluto omniroute status\|setup\|start` | gateway local de LLMs grátis (keyless) |
| `pluto dossie T0001` | dossiê da task: plano, evidência e entrega |
| `pluto fluxos setup\|start\|listar` | automações n8n locais |
| `pluto autonomia [nível]` | cauteloso · padrao · autonomo |
| `pluto varredura` | caça segredos/dados no projeto (pré-push) |
| `pluto update` | atualiza a partir das tags do GitHub |
| `pluto config show\|set\|edit` | configuração |

E também: `skills` · `memoria` · `rag` · `vida` · `arena` · `audio` ·
`conversas` · `aprender` · `grafo` — `pluto --help` mostra tudo.

Flags globais: `--data-dir DIR` (diretório de dados, padrão `~/.pluto`) e
`--mock` (modo demonstração com Ollama simulado).

## 🌐 GUI web

Abra `http://localhost:8080` (ou `host:porta` que você escolheu).

- **▤ Painel** — cartões do **Agente** e do **Ollama** com estado em tempo real,
  botões ▶ Ligar / ■ Desligar / ⟳ Reiniciar, e **log ao vivo** (SSE).
- **◈ Chat** — converse com o agente; as chamadas de ferramenta aparecem na
  hora (🔧 comando, argumentos, saída) antes da resposta final.
- **☑ Tarefas** — enfileira tarefas para o daemon executar em sequência
  (funciona até com o chat fechado; histórico com resultados).
- **⚙ Ajustes** — troca de modelo, prompt de sistema, limites, sandbox e token
  de acesso, salvos em `~/.pluto/config.yaml`.

## 🔌 API REST (usada pela GUI)

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/status` | status consolidado (agente, Ollama, config) |
| POST | `/api/agent/start·stop·restart` | liga/desliga/reinicia o agente |
| POST | `/api/ollama/start·stop` | liga/desliga o Ollama |
| GET | `/api/logs?lines=300` | últimas linhas do log |
| GET | `/api/logs/stream` | log ao vivo (SSE) |
| POST | `/api/chat` | conversa (stream NDJSON de eventos) |
| GET/POST | `/api/tasks` (+`/clear`) | fila de tarefas |
| GET/POST | `/api/settings` | configuração |

Autenticação (quando houver token): header `X-Pluto-Token: <token>` ou
`?token=<token>`.

Exemplo:

```bash
curl -s localhost:8080/api/agent/start -X POST | jq
curl -N localhost:8080/api/logs/stream          # log ao vivo no terminal
```

## ⏰ Tarefas agendadas

Deixe pedidos para executarem sozinhos em horários específicos — o
agendador roda **dentro do `pluto server`** (mantenha a GUI aberta):

```bash
pluto schedule add "resuma meus e-mails e as atividades do classroom" "diário 07:30"
pluto schedule add "relatório de uso de disco" "seg,sex 18:00"
pluto schedule add "limpeza de backups antigos" "domingo 03:00"
pluto schedule list
```

Ou pela GUI → aba **Tarefas → ⏰ Tarefas agendadas**. Formatos aceitos:
`diário 07:30` · `todo dia às 8` · `seg,qua 14:00` · `amanhã 09:00` ·
`uma vez 2026-10-05 08:00` · `a cada 30m`.

As tarefas agendadas rodam **sem confirmação interativa** (nada as barra),
mas a denylist de segurança permanece: comandos destrutivos continuam
bloqueados. Resultados ficam no histórico da aba Tarefas.

**E-mail/Classroom**: adicione o conector Gmail (MCP oficial do Google) no
`config.yaml` e a skill `resumo-inbox` guia o agente no relatório diário:

```yaml
mcp_servers:
  - name: gmail
    url: https://gmailmcp.googleapis.com/mcp/v1   # requer OAuth (Google Cloud)
```

## 🛠 Ferramentas do agente direto na GUI

A aba **Ferramentas** dá acesso manual às funções padrão dos agentes:
terminal rápido (com a mesma denylist de segurança), arquivos do workspace
(listar/ler/gravar), diagnóstico da máquina e o catálogo de funções
(nativas + MCP). Use sem passar pelo chat.

## 🔌 Dois agentes: Pluto e Claude Code

No chat, o seletor no topo escolhe quem responde:

- **◈ Pluto (Ollama)** — o agente padrão deste projeto;
- **🔌 Claude Code** — a CLI `claude` da sua máquina, com as funções padrão
  do Claude (bash, leitura/edição de arquivos, busca…), **integrada ao
  Ollama automaticamente**: o Pluto lança o `claude` apontando para o mesmo
  servidor Ollama (variáveis `ANTHROPIC_*` aplicadas sozinhas — não é
  preciso exportar nada). Ajustável em ⚙ Ajustes (`claude_use_ollama`,
  `claude_model`).

  ```bash
  curl -fsSL https://claude.ai/install.sh | bash   # instala a CLI (uma vez)
  ollama launch claude --model llama3.2:3b         # teste via Ollama (use um modelo instalado!)
  # ⚠ sem --model ele tenta "claude-opus-…", que NÃO existe no Ollama
  ```

As tarefas agendadas também têm seletor de agente (Pluto ou Claude Code).

## 🎤 Ditar pelo microfone (Whisper local)

Botão **🎤** no chat: fale, pare a gravação e o **Whisper local** transcreve —
o texto é enviado ao agente, que interpreta e executa (dite "mostre informações
do sistema"). Requer uma vez:

```bash
./.venv/bin/pip install faster-whisper "av<19"   # modelo 'base' baixa no 1º uso
```

100% local, sem API. Modelo e idioma ajustáveis em ⚙ Ajustes; microfone exige
`http://127.0.0.1:8080` ou HTTPS.

## 🌐 Acesso à web

O **próprio agente** pesquisa na internet e lê páginas quando precisa — no
chat e nas tarefas agendadas (a skill `pesquisa-web` o guia em pesquisas,
monitoramentos e relatórios diários; uso manual opcional na aba
**Ferramentas → 🌐 Web**):

- `web_search`: busca no DuckDuckGo (sem chave de API) com títulos, endereços
  e resumos;
- `web_fetch`: abre qualquer endereço http(s) e devolve o texto limpo.

O modelo é instruído a **citar as fontes**. Para desligar (agente offline):
⚙ Ajustes → "🌐 acesso à web".

## 📚 Baixar modelos (LMMs) pela GUI

Na aba **Ollama → Modelos**, busque na biblioteca oficial (ollama.com) ou na
curadoria popular ("qwen", "visão", "código"…) e baixe com um clique; o
download mostra progresso e pode ser **cancelado**. Para tags específicas
(ex.: `qwen2.5:7b`), use o campo manual.

## 💬 Gerenciar conversas

- **＋ nova** — começa uma conversa limpa (a anterior continua salva);
- **🕘 conversas → 🔍** — busca dentro de TODAS as conversas salvas e abre a
  conversa que contém o texto;
- **abrir** — retoma qualquer conversa anterior exatamente de onde parou.

## 👁 Acompanhando uma tarefa ao vivo

Ao disparar uma tarefa agendada ("▶ agora" na aba Tarefas), a GUI abre um
console que mostra a execução em tempo real: passos, comandos rodados com
sucesso/erro, tokens sendo gerados e a resposta final. O mesmo botão "👁 ao
vivo" aparece enquanto a tarefa roda — útil para conferir o agente trabalhando
no horário agendado.

## 📔 Memória do agente

O Pluto lembra de você entre conversas, reinícios e tarefas agendadas.
Na prática:

- No chat, conte algo ("lembre que meu curso é X") e o agente salva com a
  ferramenta `lembrar` — ou esquece com `esquecer`;
- Na aba **📔 Memória** você vê, adiciona, edita e apaga fatos diretamente;
- Tudo o que está lá é usado em **qualquer** conversa e nas tarefas agendadas
  (ex.: o resumo diário de e-mail já sai do jeito que você prefere).

Os fatos ficam em `data/memory.json` — é só backupar esse arquivo junto com o
resto do `data/`.

## 🧠 Gerenciando o Ollama pela GUI (o "app desktop" do Linux)

A aba **Ollama** dá a visibilidade de processo que no Windows fica na bandeja:

- **Servidor**: estado, versão, **PID, tempo ligado, memória RSS**, quem gerencia
  (systemd/Pluto/externo), modelos carregados em memória/VRAM e botões
  ▶ Ligar / ■ Desligar / ⟳ Reiniciar / ⚙ **iniciar com o sistema** (systemd).
- **Conexão**: edite o endereço da API (`ollama_url`), ative o **arranjo
  automático** (o agente sobe o Ollama sozinho quando precisar) e rode o
  **🔍 testar conexão** — validação passo a passo: instalação → serviço/API →
  modelos instalados → modelo configurado → **geração de teste real com
  latência medida**. Use isso sempre antes de começar a trabalhar.
- **Modelos**: lista com tamanho/data, definir o modelo em uso, **baixar com
  barra de progresso** (`ollama pull` via GUI) e remover do disco.

> É a mesma coisa que trocar o terminal pela GUI: chat, tarefas, ligar/desligar,
> Ollama, modelos, skills, MCP e ajustes — tudo pela interface web. A CLI
> continua disponível para quem preferir.

## 🔌 Conectores MCP

O Pluto é um **cliente MCP** (Model Context Protocol): servidores externos
(Figma, GitHub, bancos, automação) aparecem para o agente como ferramentas
extras `mcp_<servidor>_<ferramenta>`. Configure em `config.yaml`:

```yaml
mcp_servers:
  # Figma via API REST (Framelink) — token em figma.com → Settings → Security
  - name: figma
    command: npx
    args: ["-y", "figma-developer-mcp", "--figma-api-key=SEU-TOKEN", "--stdio"]

  # Figma Dev Mode (app desktop: Preferences → Enable local MCP Server)
  - name: figma-devmode
    url: http://127.0.0.1:3845/mcp

  # Demonstração incluída no projeto (sem token)
  - name: figma-demo
    command: python3
    args: ["mcp-servers/figma_demo_server.py"]
```

Transportes: **stdio** (`command`/`args`) e **Streamable HTTP** (`url`).
Na GUI: Painel → *Servidores MCP* (ativar/reiniciar, ferramentas por servidor).
Qualquer servidor MCP da comunidade funciona — veja
[awesome-mcp-servers](https://github.com/wong2/awesome-mcp-servers).

## ✦ Skills (SKILL.md)

Skills são pacotes de instruções que o agente carrega sob demanda: o catálogo
(nome + descrição) entra no prompt de sistema e o conteúdo é lido com
`read_file` só quando a tarefa combina (*progressive disclosure*, formato
aberto [agentskills.io](https://agentskills.io)).

**Incluídas** (47 na pasta `skills/`), destaques recentes:
`spec-driven` (desenvolvimento guiado por especificação — SPEC→PLANO→
TASKS antes de codar), `disciplina-agente` (as 7 regras dos agentes de
código de produção), `engenharia-reversa` (método REA com rótulos
visto/inferido/desconhecido), `codigo-verificado` (código que não rodou
não é entrega) e `tdd`; e as de design: `figma-design`,
`ui-design-system`, `app-prototyping`.

**Instalar do GitHub** — GUI → aba *Skills* (ex.: `anthropics/skills`,
subpasta `skills/pdf`) ou via API:

```bash
curl -X POST localhost:8080/api/skills/install \
  -H 'Content-Type: application/json' -d '{"repo":"anthropics/skills","subpath":"skills/docx"}'
```

**Criar suas próprias**: pasta com `SKILL.md` (frontmatter `name` +
`description` + instruções em Markdown) em `~/.pluto/skills/` — o próprio
agente pode criar skills com a ferramenta `write_file`.

## 🛡 Segurança

O agente executa comandos na máquina — trate-o como um shell com assistência:

- **Sempre** use `--token` se a GUI escutar em `0.0.0.0` (a GUI avisa quando
  estiver aberta sem senha).
- Comandos destrutivos (`rm -rf /`, `mkfs`, `dd` para disco, `shutdown`,
  `curl … | sh`, fork bomb…) são **bloqueados por denylist** em qualquer modo.
- `sandbox: true` restringe leitura/escrita de arquivos ao workspace
  (`~/.pluto/workspace`).
- No terminal, comandos arriscados pedem confirmação
  (`confirm_dangerous: true`).
- Todo comando tem timeout (`cmd_timeout`) e saída truncada.
- Prefira manter a GUI em `127.0.0.1` e acessar via SSH/túnel quando possível.

## 📁 Onde ficam os dados (`~/.pluto`)

```
~/.pluto/
├── config.yaml          configuração (editável pela GUI/CLI)
├── heartbeat.json       estado do agente (pid, status) — usado pelo ligar/desligar
├── workspace/           sandbox de arquivos do agente
├── logs/agent.log       log unificado do agente
├── tasks/               fila de tarefas (spool) + tasks/done/ resultados
└── conversations/       histórico dos chats (JSONL por dia)
```

## 🧪 Modo demonstração (sem Ollama)

Sem Ollama instalado (ou com `--mock`), o Pluto entra em **modo demonstração**:
um Ollama simulado responde localmente, o loop de ferramentas é real e a GUI
funciona por completo — útil para avaliar antes de baixar modelos. As respostas
deixam claro que são simuladas.

## 🧩 Modelos

Qualquer tag do Ollama funciona; o padrão é o Pluto:

```bash
ollama pull hermes3:3b     # leve (~2 GB, 8 GB RAM)
ollama pull hermes3:8b     # padrão (~4,7 GB, 12 GB RAM) — recomendado
ollama pull hermes3:70b    # servidor (~40 GB)
pluto config set model hermes3:3b
```

## ❓ Problemas comuns

| Sintoma | Solução |
|---|---|
| “não consegui falar com o Ollama” | `pluto ollama status` → `pluto ollama start` |
| “modelo não encontrado” | `pluto ollama pull` (baixa o modelo da config) |
| GUI não abre de outro aparelho | liberar a porta no firewall e usar `--host 0.0.0.0` |
| Respostas lentas | guarde uma chave grátis (`pluto provider set groq`) — o roteador usa o provedor rápido · ou use `hermes3:3b` |
| Agente “sem heartbeat” | processo travado → `pluto agent restart` |

---

Feito com ◈ · [Ollama](https://ollama.com) · [Hermes 3 — Nous Research](https://ollama.com/library/hermes3) · Flask · n8n

## 🗺 Versões e branches de fase

O projeto evolui em fases — cada uma tem uma branch com o código do marco:

| Branch | Fase |
|---|---|
| `v1.x` | 🖥 O agente de terminal (v1.1.0 → v1.5.0) |
| `v2.x` | 🌐 GUI web + Claude Code (v2.0.0 → v2.2.8) |
| `v3.0.x` | 🏗 A plataforma: auditoria, backups, skills (v3.0.x) |
| `v3.1.x` | 📧 E-mail (OAuth 2FA) + agenda somente leitura (v3.1.x) |
| `main` | 🚀 v4.x: especialistas + autonomia · v5.x: vida/skills/n8n · v6.x: universal, performance, roteador, omniroute · v7.x: fluxo adaptativo, dossiê, @/comandos, prazo, ER (→ v8.1.0) |

Detalhe versão a versão: [`docs/HISTORICO-DE-VERSOES.md`](docs/HISTORICO-DE-VERSOES.md) · tags de todas as releases na aba **Tags**.
