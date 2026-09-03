---
name: scan-ebay
description: >-
  Rodar o scan de arbitragem do eBay (anúncios de preço fixo vs referência —
  slab = mediana de vendas concluídas no PriceCharting; raw NM = TCGplayer
  market) e entregar via ebay_summary.py no layout COMC. Use SEMPRE que o
  operador pedir para rodar o scanner do eBay / "roda o eBay" / "scan eBay" /
  escanear a watchlist do eBay: antes de rodar, PERGUNTE o grupo
  (--list-groups) e o modo (comercial = --min-discount 20; diagnóstico =
  --min-price 5 --min-discount 10 --include-raw + --sensitivity 10,15,20) e
  entregue SEMPRE a saída do ebay_summary.py verbatim (2 links em toda linha,
  todos os buckets, funil no cabeçalho).
---

# Scan do eBay — pergunte, rode, entregue

O scanner compara anúncios ativos de **preço fixo** do eBay (Browse API — a API
oficial de busca; leilão nem entra na busca) com uma referência honesta, no
**padrão COMC** (operador, 2026-09-03):

- **slab** (carta lacrada com nota: PSA 8/9/10, CGC 9/9.5/10 Gem Mint/10
  Pristine, BGS 9/9.5/10/10 Black Label, SGC 9/9.5/10, TAG 9.5/10) → mediana
  (valor do meio) de vendas concluídas da MESMA carta+variante+certificadora+
  nota no PriceCharting; ≥3 vendas = OK, 1–2 = REVISAR, 0 = sem referência;
- **raw NM** (carta solta quase perfeita; só com `--include-raw`) → market do
  TCGplayer (via tcgcsv.com), PriceCharting como cross-check rotulado;
- **raw LP** (leve desgaste, só com LP explícito no anúncio) → mediana de ≥3
  vendas LP; nunca comparado ao preço NM.

Gate (filtro que decide se vira linha) = **Desconto%** = (referência − preço)/
referência, percentual INTEIRO (`min_discount_percent: 20` no config;
`--min-discount N` por run). ROI bruto% e Spread$ são colunas. Nunca "lucro".

## Passo 0 — pré-requisitos

- `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` no ambiente (env vars de usuário
  Windows — keyset "MinhaLojaEbay"; sessão de terminal antiga pode não herdar
  → passar inline se "ausentes"). Sem chaves, o run degrada para pricing-only
  e NÃO grava artefato.
- `watchlist.yaml` na raiz do repo. É local-only (gitignored): **um clone limpo
  ainda precisa dela** — hoje se copia `watchlist.example.yaml` e preenche; o
  PR B vai gerá-la a partir do catálogo (campos `pokemon`/`pokemon_rank`/
  `rarity`/`year`). Sem watchlist o run falha antes de começar.

## Passo 1 — perguntar grupo e modo (AskUserQuestion) — nunca assumir

1. **Qual grupo da watchlist rodar?** Obtenha as opções DINAMICAMENTE (não
   precisa de chaves eBay):
   ```powershell
   .venv\Scripts\python main.py --list-groups
   ```
   Apresente os grupos com a contagem de cartas + a opção "todas as cartas"
   (sem `--group`).
2. **Qual modo?**
   - **Comercial** (default): `--min-discount 20` (= default do config), só
     slabs, piso US$10. Entrega em 4 buckets por veredito.
   - **Diagnóstico** (operador 2026-09-03): `--min-price 5 --min-discount 10
     --include-raw`. Entrega com `--sensitivity 10,15,20` — só a faixa ≥20% é
     candidato comercial; 15–19,99% e 10–14,99% são diagnóstico, NÃO
     oportunidade.
   - Opcionais em qualquer modo: `--grades "PSA 10, CGC 10 Pristine"` (funil
     restrito a notas; nota desconhecida erra alto) e `--confiavel` (só
     vendedores ≥50 avaliações/≥98%, sem SUSPEITO/REJEITADO — tabela 100%
     acionável).

## Passo 2 — rodar (rota determinística local)

```powershell
$env:PYTHONIOENCODING="utf-8"
# comercial
.venv\Scripts\python main.py --group <g> --min-discount 20 --out results\last_scan.json
# diagnóstico
.venv\Scripts\python main.py --group <g> --min-price 5 --min-discount 10 --include-raw --out results\last_scan.json
```

- Sem `--group` = watchlist inteira. `--pricing-only` não gera artefato JSON
  (não há anúncios avaliados).
- Cota da Browse API: 5.000 chamadas/dia grátis; cada carta gasta até
  `max_pages` (3) chamadas de 200 anúncios. O funil da entrega mostra
  "Chamadas à Browse API" — reportar.
- **Exit code 1 = run abortado** (falha de autenticação no eBay ou 3 erros
  seguidos da API): o artefato sai marcado `aborted: true` e a entrega mostra
  "RUN ABORTADO — cartas restantes não varridas". Entregar assim mesmo, dizendo
  que é parcial; nunca tratar como scan completo.
- Erro por carta (PriceCharting fora do ar, carta sem vendas comparáveis) NÃO
  derruba o run: é contado no funil (`pc_error`, `pc_breaker`, `card_error`,
  "sem referência") e aparece no cabeçalho.

## Passo 3 — entregar (ritual FIXO, contrato do repo, não negociável)

```powershell
# comercial
.venv\Scripts\python ebay_summary.py results\last_scan.json -o results\ebay-<AAAA-MM-DD>.md
# diagnóstico
.venv\Scripts\python ebay_summary.py results\last_scan.json -o results\ebay-<AAAA-MM-DD>.md --sensitivity 10,15,20
```

1. Colar o conteúdo do `.md` **VERBATIM** no chat — **proibido** remontar
   tabela à mão, renomear/reordenar colunas ou dropar o link de referência.
2. **Todas as linhas, todos os buckets.** Comercial: 🟢 OPORTUNIDADE / ⚠️
   REVISAR / 🚨 SUSPEITO / ⛔ REJEITADO (tabela própria, com motivo).
   Diagnóstico: faixa ≥20% (candidato comercial + REVISAR/SUSPEITO), faixas
   🔬 15–19,99% e 10–14,99% ("NÃO é oportunidade"), tabela de contagens por
   limiar, REJEITADO de todas as faixas. Nunca amostra.
3. Toda linha tem os **DOIS links**: `[oferta]` (anúncio eBay) e
   `[referência]` (página da carta no PriceCharting — também para raw; `[TCG]`
   só quando não há página PC). URLs vêm do JSON — nunca inventar.
4. Reportar as linhas do cabeçalho: **Parâmetros**, **Cobertura de
   referência** (slabs por mediana · raw NM c/ TCG · raw LP · raw só PC · sem
   referência) e **Funil** (inclusive chamadas à API e erros/breaker).
5. **Sem recomendação de compra** — vereditos são classificação técnica;
   capital é decisão do operador. Faixas de diagnóstico não são oportunidade.

## Nota de logística (por que US-only e preço fixo são invariantes)

Compras têm **Ship To = COMC mailbox (Algona, WA 98001-7409, EUA)** — mailbox
de armazenamento do operador. Por isso o filtro `itemLocationCountry: US` da
API + o cinto de segurança no scorer **não podem ser afrouxados**: item fora
dos EUA não serve mesmo que a margem pareça ótima. E leilão não entra
(`fixed_price_only: true`): lance atual não é preço.
