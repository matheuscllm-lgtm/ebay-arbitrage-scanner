# Chinês simplificado × inglês — carta solta, preço de mercado (`zh_gap.py`)

Data: 2026-10-07. Status: implementado, testado offline (`tests/test_zh_gap.py`) e validado em
coleta real (sets CSV10C e 151C; depois a coleta completa da sessão de 07/10).

## Pergunta que responde

Pedido do operador (07/10/2026): *quais cartas em chinês simplificado estão mais descontadas em
relação à MESMA carta em inglês?* Preço de mercado da carta **solta** (raw), sem exigir PSA, com
um piso mínimo de valor. É um **ranking diagnóstico**: não é o gate do scanner, não altera a
política `longterm` (PSA 10, `docs/EBAY_PSA.md`) nem o modo chinês de slabs
(`docs/CHINESE_PSA10.md`). Nenhuma recomendação de compra — a decisão de capital é do operador.

## Como calcula

| Peça | Fonte | Observação |
|---|---|---|
| Par chinês → inglês | `src/catalog/zh_identity.json` (52poke wiki, [CHINESE_IDENTITY.md](CHINESE_IDENTITY.md)) | só linhas com `how` definido; `ambigua`/`sem-par` ficam fora; `how` vira a coluna **Match** (exata / forte / fraca). O título da página chinesa ainda tem de trazer nome-base + sufixo (ex/GX/V/VMAX…) da carta EN (`title_matches_en`): o PriceCharting repete número entre produtos ("Calyrex #162" e "Calyrex VMAX #162") e o `set+rar` do catálogo trocou Dusk Mane ↔ Dawn Wings Necrozma na coleta de 07/10 |
| Preço chinês (raw, Grade 9, PSA 10) | página de **set** do PriceCharting `/console/pokemon-chinese-<set>` | 150 cartas por página, paginação `?cursor=`; 1 página ≈ 1 crédito Firecrawl pela rota reserva (`src/cf_fallback.py`) |
| Preço inglês | TCGplayer market via tcgcsv (`src/tcg_reference.py`) | referência canônica da frota para singles raw; sem match exato de set + número + nome → carta fora (funil `en-sem-referencia-tcg`) |
| Oferta | eBay Browse API, anúncio ativo mais barato, preço fixo, qualquer país | só título **chinês** (simplificado ou "Chinese"), carta **solta** (`grading.grade_from_title` = raw: nenhuma certificadora citada, nem ACE/AGS/"PSA graded"), nome-base por palavra inteira + número chinês (zeros à esquerda e formatos de Gem Pack aceitos), código de set do título igual ao da linha, sem lote/réplica (`pick_offer`). Frete calculado no checkout vem `None` → `frete n/d`, razão marcada `(sem frete)`; nunca vira zero |

`Razão = EN market ÷ ZH raw` · `Desconto = 1 − ZH ÷ EN`. Piso padrão: EN market ≥ US$10 (piso da
frota, R$50) — `--min-en`. A versão para o chat (`<out>.chat.md`) corta em `--min-ratio` (padrão 3×);
o `.md` completo e o JSON trazem todas as linhas acima do piso.

Impressões paralelas da página chinesa (`[Reverse]`, `[Master Ball]`, `[Poke Ball]`…) são ignoradas
(funil `pc-variante-ignorada`): o catálogo descreve a impressão base e a referência EN é a carta normal.

## Uso

```bash
python zh_gap.py --out results/zh-gap-2026-10-07.json          # todos os sets com ≥20 pares (--min-pairs)
python zh_gap.py --sets CSV10C,151C --no-ebay --out results/zh-gap-teste.json
```

Saídas locais (nunca versionadas): `<out>.json`, `<out>.md`, `<out>.chat.md`. Páginas do PriceCharting
ficam em `--cache-dir/<dia>/` (padrão `data/cache/pc/zh_gap/`, estável entre execuções: rodar de novo no
mesmo dia não gasta crédito; coleta nova no dia seguinte). Erro numa página mantém as páginas já lidas e o
set sai marcado como parcial. Orçamento eBay: `--max-ebay-calls` (padrão 300, teto do cliente 500); erro
numa busca marca só a linha (`busca falhou`) e segue; três erros seguidos param as buscas.

## Limites conhecidos

- O preço raw chinês do PriceCharting vem de poucas vendas em muitas cartas: a coluna pode ser rala
  ou velha. A coluna `ZH PSA 10` e o link `ref ZH` estão na linha para o operador conferir.
- `30th Celebration` e promos EN (`SVP Black Star Promos`…) não resolvem no tcgcsv por nome exato →
  ficam fora até alguém mapear o grupo.
- Os anexos do provedor de catálogo (frente PokeData) **não** são usados aqui: seguem bloqueados pela
  decisão de termos ([POKEDATA_HANDOFF.md](POKEDATA_HANDOFF.md)). O pareamento vem só da 52poke wiki.
