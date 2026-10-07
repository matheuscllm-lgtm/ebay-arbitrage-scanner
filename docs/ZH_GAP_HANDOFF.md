# Handoff — ranking chinês simplificado × inglês (`zh_gap.py`)

Data: 2026-10-07 (fechamento da sessão). Leia junto com [ZH_GAP.md](ZH_GAP.md) (método) e
[POKEDATA_HANDOFF.md](POKEDATA_HANDOFF.md) (frente de catálogo, pendência de termos).

## Estado

- **Objetivo fechado com o operador (07/10):** ranking das cartas em chinês simplificado mais
  descontadas em relação à MESMA carta em inglês, carta solta, sem exigir PSA, pisos EN ≥ US$10 e
  raw chinês ≥ US$10. Operador aprovou o resultado ("a ideia é essa mesma").
- **Código:** branch `claude/zh-gap-ranking` (main `7a44c33` + 9 commits, publicada; **PR não aberto**
  — bloqueio de permissão da sessão; abrir pelo GitHub). `src/zh_gap.py`, `zh_gap.py`,
  `tests/test_zh_gap.py` (68 testes), fixture real, `docs/ZH_GAP.md`, nota no `CLAUDE.md`.
- **Revisão independente** (contexto limpo, páginas reais) aplicada: frete desconhecido = `n/d`;
  junção exige nome-base + sufixo no título da página chinesa; oferta só carta solta; número com
  fronteira de palavra; cache estável; erro por linha. Suíte completa passou antes dos 3 últimos
  commits (`a6b3499`, `c161266`, `3e5bc25`); re-rodar antes do PR.
- **Coleta de 07/10 (local, `results/`, nunca versionar):** 52 consoles, 69 páginas, 191 cartas acima
  dos dois pisos, 56 com razão ≥ 3×, 49 com oferta raw no eBay. Prismatic Evolutions (CSV9.5C)
  concentra o topo.
- **Também nesta sessão:** PR #68 (rota reserva Firecrawl para o desafio Cloudflare do PriceCharting)
  mesclado com "autorizo"; PR #66 (GPT) fechado sem merge.

## Decisões

- Ranking é **diagnóstico de mercado**, não gate: não altera `longterm`, `slab_strategy` nem o modo
  chinês de slabs (`chinese_scan.py`).
- Nunca chutar par: `par-ambiguo`, `pc-titulo-nao-casa`, variantes `[Reverse]/[Master Ball]` e cartas
  sem referência TCGplayer ficam fora, contadas no funil.
- Entrega = `<out>.chat.md` colado verbatim (dois links por linha; `[oferta]` quando há).

## Pendências

1. `python -m pytest -q` (foreground) → abrir PR → "autorizo" do operador.
2. Dudunsparce 229 e Noivern V 196 fora por grafia/omissão do PriceCharting; avaliar tolerância.
3. Variantes da página chinesa ignoradas (1.341 linhas) — parear com EN se o operador quiser.
4. Promos EN e 30th Celebration não resolvem no tcgcsv por nome exato.
5. Termos do PokeData (operador); anexos não usados aqui.

## Como retomar (prompt)

> Repo matheuscllm-lgtm/ebay-arbitrage-scanner, local `~/ebay-arbitrage-scanner`, venv
> `.venv\Scripts\python`, `PYTHONIOENCODING=utf-8 PYTHONUTF8=1`. Faça `git fetch`; branch
> `claude/zh-gap-ranking` (sem PR). Leia `docs/ZH_GAP_HANDOFF.md`, `docs/ZH_GAP.md`, `DELIVERY_CHAT.md`
> e `CLAUDE.md`. 1) Rode a suíte completa em foreground; verde → abra o PR da branch (título:
> "feat(zh_gap): ranking chinês simplificado × inglês de carta solta"; corpo: motivo, arquivos,
> validação, pendências do handoff; termine com a URL da sessão) e peça "autorizo" — merge só com ele.
> 2) Se eu pedir coleta nova: `python zh_gap.py --out results/zh-gap-<data>.json` (~70 créditos
> Firecrawl, ~60 chamadas eBay) e cole `results/zh-gap-<data>.chat.md` verbatim. Nada de preços,
> planilhas ou derivados no GitHub; sem acompanhamento automático de PR; resposta ≤ 200 palavras
> (Objetivo / Feito / Pendências), tabela fora do teto.

## Custos observados

- Firecrawl: 1 crédito por página de set do PriceCharting (~70 por coleta completa); ~80 créditos
  gastos em 07/10 (incluindo testes); reruns no mesmo dia custam 0 (cache `data/cache/pc/zh_gap/<dia>/`).
- eBay: 1 chamada por linha com razão ≥ 3× (56 na coleta final; teto 300 por execução).
