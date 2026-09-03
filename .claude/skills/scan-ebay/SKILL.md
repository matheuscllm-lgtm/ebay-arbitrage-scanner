---
name: scan-ebay
description: >-
  Rodar o scan de arbitragem do eBay (anúncios de preço fixo vs referência —
  slab = mediana de vendas concluídas no PriceCharting; raw NM = TCGplayer
  market) e entregar via ebay_summary.py no layout COMC. Use SEMPRE que o
  operador pedir para rodar o scanner do eBay / "roda o eBay" / "scan eBay" /
  escanear a watchlist do eBay: antes de rodar, PERGUNTE o grupo canônico
  (1–12, UM por vez; --list-groups mostra os títulos) e o modo (comercial =
  --min-discount 20; diagnóstico =
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
- `watchlist.yaml` **já vem no repo** (GERADA por `build_watchlist.py` e
  versionada — decisão do operador 2026-09-03): um clone limpo roda sem
  preparo. Universo = catálogo de 123 sets (`src/catalog/set_catalog.json`,
  os mesmos 12 grupos da COMC em `src/groups.py`) × 100 "chases"
  (`src/catalog/iconic_pokemon.csv`) × raridade ≥ Holo Rare × teto 30 cartas
  por set; `pc_url` = página exata da carta no PriceCharting (carta sem
  página fica fora; nunca se inventa URL). **Não editar à mão**; regenerar
  (`python build_watchlist.py`) só quando o catálogo/grupos/chases mudarem —
  o teste `tests/test_groups.py` falha de propósito se o catálogo crescer sem
  os grupos acompanharem.

## Passo 1 — perguntar grupo e modo (AskUserQuestion) — nunca assumir

1. **Qual grupo canônico rodar (UM por vez)?** Obtenha títulos e contagens
   DINAMICAMENTE (não precisa de chaves eBay):
   ```powershell
   .venv\Scripts\python main.py --list-groups
   ```
   Os 12 grupos são os mesmos da COMC (`src/groups.py`, títulos verbatim):

   | Grupo | Título | Sets |
   |---|---|---|
   | 1 | SV recente | 7 |
   | 2 | SV restante | 6 |
   | 3 | WotC 1999-2000 | 8 |
   | 4 | WotC 2001-2003 | 7 |
   | 5 | EX 2004-2005 | 8 |
   | 6 | EX 2006-2007 + DP 2007 | 8 |
   | 7 | DP/Platinum 2008-2010 | 8 |
   | 8 | HGSS + BW 2010-2013 | 17 |
   | 9 | XY 2014-2016 | 14 |
   | 10 | SM 2017-2019 | 17 |
   | 11 | SWSH 2020-2021 | 12 |
   | 12 | SWSH 2022 + Crown Zenith | 11 |

   (1–2 = SV 2023–25; 3–4 = WotC 1999–2003; 5–10 = EX/DP/Platinum/HGSS/BW/
   XY/SM 2004–19; 11–12 = SWSH + Crown Zenith 2020–23.) `--group` aceita
   `N` | `N-M` | `1,3,10-12` | `all`; número fora de 1–12 erra alto. Apresente
   os grupos com a contagem de cartas que o `--list-groups` imprimiu. Padrão do
   operador = **um grupo por vez** (cota da Browse API: 5.000 chamadas/dia,
   ~1–3 chamadas por carta; a watchlist inteira tem ~1.600 cartas).
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
# comercial (um grupo por vez; artefato nomeado pelo grupo)
.venv\Scripts\python main.py --group <N> --min-discount 20 --out results\last_scan_g<N>.json
# diagnóstico (padrão COMC do operador, 2026-09-03)
.venv\Scripts\python main.py --group <N> --min-price 5 --min-discount 10 --include-raw --out results\last_scan_g<N>.json
```

- `--out results\last_scan_g<N>.json` = um artefato por grupo (o run do grupo
  seguinte não sobrescreve o anterior). Sem `--group` = watchlist inteira
  (~1.600 cartas — não cabe na cota diária; só sob pedido explícito).
  `--pricing-only` não gera artefato JSON (não há anúncios avaliados).
- Cota da Browse API: 5.000 chamadas/dia grátis; cada carta gasta ~1–3
  chamadas (1 busca paginada, até `max_pages` = 3 páginas de 200 anúncios).
  O funil da entrega mostra "Chamadas à Browse API" — reportar.
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
.venv\Scripts\python ebay_summary.py results\last_scan_g<N>.json -o results\ebay-g<N>-<AAAA-MM-DD>.md
# diagnóstico
.venv\Scripts\python ebay_summary.py results\last_scan_g<N>.json -o results\ebay-g<N>-<AAAA-MM-DD>.md --sensitivity 10,15,20
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
