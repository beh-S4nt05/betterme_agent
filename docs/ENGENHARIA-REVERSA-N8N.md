# 🔬 Engenharia Reversa — n8n

> **ER completa do n8n pelo método REA** (5 passos: uma função ·
> ferramenta pelo tipo · resumo primeiro · **visto/inferido/
> desconhecido** · reconstruir e testar) — [REA do INEMA, MIT](https://github.com/inematds/rea-engenharia-reversa).
> out/2026 · n8n embutido no Betterme desde a PR#11 (installer SUL,
> templates tpl-eco/tpl-gat, `betterme fluxos`) · complementa o
> `N8N_PASSOAPASSO.md` (passo a passo de uso) e o
> `docs/COMPARATIVO-AGENTES.md`.

---

## 0. Método, alvo e limites

- **Função estudada (passo 1 — UMA função):** *como o n8n executa um
  workflow* — do JSON do grafo até o efeito no mundo. É a função que
  importa para o Betterme (nós orquestramos o n8n por API e geramos
  workflows nativos).
- **Ferramentas (passo 2 — pelo tipo):** alvo é **código aberto**
  (fair-code) → leitura de fontes/documentação pública + **experiência
  real de campo** do projeto Betterme (instalação, API, execução,
  templates). Sem descompilação, sem Ghidra.
- **Rótulos (passo 4):** `[visto]` = evidência deste projeto (comando
  executado, arquivo observado, resposta de API) ou doc oficial
  citada · `[inferido]` = dedução com raciocínio declarado ·
  `[desconhecido]` = admitido.
- **Licença (cuidado REA):** n8n é **fair-code** (Sustainable Use
  License + Apache-2.0 nos módulos) — NÃO é OSI open source; self-host
  e uso interno são o terreno seguro em que o Betterme está.

## 1. Resumo primeiro (passo 3) — o mapa em 8 linhas

O n8n é um **interpretador de grafos dirigidos persistentes**: um
workflow é um JSON com `nodes[]` (parâmetros + credenciais + posição)
e `connections{}` (arestas tipadas). Um **gatilho** (webhook, polling,
cron) inicia uma **execução**; o motor percorre o grafo nó a nó,
cada nó recebe **itens** (pares chave-valor + binários), transforma e
emite itens para as arestas de saída. Estado de cada execução é
persistido (SQLite por padrão) — por isso dá para retomar, auditar e
reexecutar. A UI (porta 5678) é só um cliente; **tudo que a UI faz
com workflow/credencial/execução passa pela API**, e é por essa porta
que o Betterme automatiza (chave `X-N8N-API-KEY`).

## 2. Evidência (o que foi examinado de verdade)

1. **Instalação embutida no projeto** (PR#11): installer "SUL" baixa e
   instala o n8n local — observado em campo em máquina real do
   operador; porta padrão **5678**. `[visto]`
2. **Uso da API pública por automação**: comandos `betterme fluxos`
   (listar/executar/apikey) conversam com a API do n8n local usando a
   chave de API — requests reais executados e documentados no
   `N8N_PASSOAPASSO.md`. `[visto]`
3. **Geração de workflows por template**: os templates `tpl-eco` e
   `tpl-gat` criam workflows n8n prontos via API — o formato JSON do
   grafo foi escrito e ACEITO pelo n8n (validação real do modelo de
   dados). `[visto]`
4. **Persistência no data dir**: instalação local mantém banco SQLite
   no diretório de dados do usuário (observado no provisionamento).
   `[visto]`
5. Documentação pública do n8n (arquitetura, API v1, node
   development) — consultada para o que o campo não cobria. `[visto,
   fonte declarada]`

## 3. Mapa — como o n8n executa um workflow

### 3.1 O grafo (modelo de dados)

- Workflow = JSON: `nodes: [{id, name, type, typeVersion, position,
  parameters, credentials?}]` + `connections: {"Nome do nó":
  {"main": [[{node, type, index}]]}}` — a lista de listas codifica
  **múltiplas saídas e múltiplos ramos** por nó. `[visto — é o
  formato que os templates enviam e o n8n aceita]`
- `type` referencia um pacote de nós (`n8n-nodes-base.httpRequest`,
  `@n8n/n8n-nodes-langchain.*`); `typeVersion` versiona o SCHEMA do
  nó — o mesmo `type` evolui sem quebrar workflows antigos. `[inferido
  do formato + docs de node development]`
- Cada nó se descreve **declarativamente** (propriedades, credenciais
  que aceita, entradas/saídas) — a UI monta o editor a partir dessa
  descrição, sem código de UI por nó. `[inferido das docs]`

### 3.2 A execução (a função estudada)

1. Um **Trigger** acorda: Webhook (caminho registrado), Polling
   (intervalo), Cron/Agenda, ou chamada manual/API. `[inferido das
   docs; webhook e execução manual exercitados em campo]`
2. O motor cria uma **execução** (registro persistido ANTES de
   rodar — auditoria desde o início). `[inferido]`
3. Percorre o grafo a partir do gatilho, em ordem de dependência:
   cada nó recebe **itens** (`[{json: {...}, binary?: {...}}]`),
   executa sua lógica (chamada HTTP, código, transformação…) e emite
   itens de saída para as arestas. `[inferido das docs + comportamento
   observado dos templates]`
4. Ramificações: um nó pode emitir para várias arestas; `index`
   seleciona a SAÍDA do nó de origem (ex.: saída "true"/"false" do
   IF). `[inferido do formato das connections]`
5. Erro de nó → a execução marca o falho; políticas de retry/erro
   por nó decidem continuar ou abortar. `[inferido das docs]`
6. Fim: status final + dados de cada nó persistidos (é o que a tela
   de execução mostra). `[inferido]`

### 3.3 Modos de operação

- **Regular** (padrão, o nosso): tudo num processo — API, editor e
  executor juntos. Simples, ótimo para agente pessoal. `[visto — é o
  que o instalador provisiona]`
- **Queue mode**: worker(s) separados puxando filas (Bull/Redis) para
  escalar horizontalmente. `[inferido das docs]`
- **Task runners** (código do nó Code em processo filho isolado).
  `[inferido das docs]`

### 3.4 Segurança e credenciais

- Credenciais são criptografadas EM REPOUSO com chave guardada no
  data dir (perder a chave = perder as credenciais). `[inferido das
  docs; o data dir isolado foi observado]`
- A API pública (v1) autentica por **chave de API** (header
  `X-N8N-API-KEY`) com escopos por recurso — é o contrato que o
  Betterme usa; a chave NUNCA passa pelo chat do agente. `[visto +
  regra D2 do projeto]`

## 4. Lições aplicadas no Betterme (a ER virou produto)

| Achado da ER | Onde vive no Betterme |
|---|---|
| Tudo que a UI faz passa pela API | `betterme fluxos` automatiza por API — sem raspar tela |
| Workflow = JSON declarativo versionado | templates `tpl-eco`/`tpl-gat` geram grafo por API |
| Execução persistida = auditável | filosofia herdada no **dossiê de task** (v6.8.0): PLANO/EVIDÊNCIA/ENTREGA |
| Itens fluem nó a nó com contexto | **etapas focadas com contexto acumulado** (v6.6.0, N2) |
| `typeVersion` preserva compatibilidade | contratos versionados (`contratos.py`) |
| Chave de API fora do chat | chave em `secrets/`, D2 preservada |

## 5. Limites

- Versão/alvo: **n8n self-hosted** embutido pelo installer do projeto
  (a versão flutua com a instalação — o mapa tem data de validade,
  cuidado nº 3 do REA).
- Não executamos carga, nem queue mode, nem task runners em campo —
  esses pontos são `[inferido]` de documentação.
- A UI (Vue) e o editor visual não foram dissecados — o Betterme
  usa a API, não a UI.

## 6. Desconhecidos declarados

1. **Formato interno do banco** (tabelas/índices exatos do SQLite) —
   verificaria com `sqlite3 <data>/database.sqlite '.schema'` numa
   instalação de teste.
2. **Comportamento exato do retry por nó** (backoff, `onError`
   continue) — verificaria com workflow de teste que falha.
3. **Limites de tamanho de execução** (truncamento de itens grandes)
   — verificaria com payload progressivo via API.
4. **Overhead real do queue mode** para 1 máquina — irrelevante para
   o caso de uso (agente pessoal), por isso não cavado.

## 7. Reconstrução e teste (passo 5 — a prova)

A reconstrução da função estudada já existe E foi testada em campo:
o **motor de etapas focadas do Betterme** (v6.6.0) reimplementa, em
escala de agente, o padrão *grafo → execução nó a nó com contexto →
auditoria persistida* — com `decompor()` (o grafo), `_ciclo_etapas`
(o percurso com contexto acumulado) e o dossiê (a execução
auditável). Os templates n8n (grafo JSON aceito pelo motor real do
n8n) e o `N8N_PASSOAPASSO.md` (execuções reais) são os testes da
integração. O que NÃO reconstruímos: gatilhos webhook/polling como
serviço — para isso o Betterme usa o próprio n8n embutido (integração
em vez de imitação, decisão ADR-001-style).

---

*Crédito de método: [REA — Reverse Engineer Anything](https://github.com/inematds/rea-engenharia-reversa)
(INEMA, MIT). Padrões reimplementados com nossas palavras; nada
copiado do produto fechado de terceiros.*
