---
name: financas
description: Controlar os gastos e finanças do operador (PF e PJ) — registrar gastos e entradas, importar extratos CSV (Banco do Brasil, Bradesco, SumUp), sincronizar vendas do SumUp, registrar faturas a vencer e mostrar o painel do mês com saldos, gastos por categoria e prazos. Use quando o pedido envolver "gastei", "recebi", "paguei", "quanto gastei", "meus gastos", "finanças", "extrato", "fatura", "boleto", "orçamento" ou "controle de gastos".
---

# Finanças — livro-caixa local

## Regras duras

1. **NUNCA invente** valor, data, categoria ou lançamento — números vêm
   do operador ou do arquivo, sempre.
2. **Cálculos são da ferramenta** (Decimal): nunca some na mão; para
   qualquer pergunta de totais, chame `financas_painel` e responda COM
   o painel.
3. Dados financeiros ficam em `<data_dir>/financas/` — **nunca** no
   repo, nunca em log, nunca em commit.
4. Pedidos que expõem dados bancários (extratos, faturas): prefira o
   **cérebro local** (privacidade — mesma lógica da regra D2).
5. Extrato CSV do SumUp **+** sync da API dobra as entradas: se o
   operador sincroniza a API, importe o extrato com `--so-saidas`.

## Ferramentas do agente

- `financas_lancar` (valor, descricao, tipo, categoria?, conta?) —
  "gastei 35 no almoço" → saida 35,00, categoria inferida
  (alimentacao), conta manual. "recebi 500 da consultoria" →
  tipo **entrada**.
- `financas_painel` (mes?) — painel do mês: entradas, saídas, saldo,
  top gastos por categoria e faturas a vencer com dias restantes.

## Importar extrato (via run_command)

```
pluto financas importar <arquivo.csv> --conta bb|bradesco|sumup [--so-saidas]
```

Formatos aceitos por FAMÍLIA de coluna (delimitador `;`, `,` ou tab):
`Data;Histórico;...;Valor` (valor assinado) OU
`Data;Histórico;...;Crédito;Débito;Saldo` (Bradesco). Reimportar o
mesmo arquivo **não duplica** nada (id estável). Se o formato não for
reconhecido, a saída mostra as colunas lidas — reporte-as ao operador.

## SumUp — entradas automáticas (uma vez)

1. `pluto financas sumup setup <api-key>` — chave em
   developer.sumup.com (Settings → API key); fica em secrets/ 600.
2. `pluto financas sumup sync` — vendas `SUCCESSFUL` viram entradas
   (conta sumup-vendas); falhadas/canceladas são ignoradas (nunca
   tocaram a conta); repasses são só informativos (a venda já entrou).

## Faturas e boletos

- `pluto financas fatura <valor> <dd/mm/aaaa> <conta>` — o painel
  avisa vencimento e dias restantes (🔴 HOJE no dia).
- Boletos no DDA sem via automática: o operador informa ("boleto da
  luz vence 10/12, R$ 230") → registre como fatura.

## Quem participa do Open Finance

`pluto financas participantes <banco>` responde com a lista
OFICIAL (cache 24 h) — use antes de prometer acesso automático a
uma instituição. Papel "detentora de conta" = pode compartilhar
dados da conta; instituição fora da lista = só via registro manual,
extrato CSV ou API própria.

## Responder

Quando o operador perguntar "quanto gastei", "como estão as finanças",
mostre o painel e destaque o que importa (saldo, top categorias,
faturas próximas) — sem recalcular nada por conta própria.
