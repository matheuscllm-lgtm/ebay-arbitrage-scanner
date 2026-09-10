# SESSION-HANDOFF — rodada da coluna "Longo prazo" (2026-09-09)

Estado para quem retomar. Sem resultado de coleta aqui: nenhum preço, nenhuma carta, nenhuma
tabela e nenhum número de funil — `DELIVERY_CHAT.md` proíbe publicar resultado, preço ou log de
coleta no GitHub. Os artefatos ficam **locais**, nos caminhos indicados abaixo.

## Onde está o trabalho

- Branch: `feat/longterm-risk-benefit`. Base: `origin/main` (PR-A #32 e PR-B #33 já mergeados
  por squash). PR do PR-C **não foi criado** — o operador cria e mergeia.
- Runner de teste (PowerShell, do diretório do repo):
  `$env:PYTHONIOENCODING='utf-8'; .venv\Scripts\python.exe -m pytest tests\ -q`.

## O que cada fase entregou

1. **PR-A #32 (mergeado)** — porte do diff local pré-#29: identidade da venda usada na
   referência (checar se a venda é da mesma carta) e funil da coleta (contagem de por que cada
   anúncio foi descartado) nos dois caminhos.
2. **PR-B #33 (mergeado)** — auditoria do SISTEMA de honestidade de preço: todos os baldes, os
   dois motores (política `slab_strategy` = vigente; `scorer` = legado).
3. **PR-C (esta branch)** — coluna informativa **Longo prazo**:
   - `src/longterm.py` — PERFIL (0-100, cinco componentes) e FRAGILIDADE DO DADO (0-100, dez
     sinais), classe LP1-LP4, asterisco `LP2*`, coberturas. Só biblioteca padrão.
   - `src/pricecharting.py` — série mensal a partir de `VGPC.chart_data`.
   - `src/models.py` — campos `longterm_*` / `trend_*` com default; `CardRefs.sales_history`.
   - `src/scanner.py` — plug em `scan_card` nos dois caminhos; contagem de anúncios por nota
     feita ANTES do loop de avaliação.
   - `src/report.py`, `src/slab_report.py`, `ebay_summary.py` — coluna antes de `Links`,
     motivos `LP:`, contagem por classe no cabeçalho, legenda no rodapé.
   - `config.yaml` — bloco novo `longterm:` (dez chaves inteiras). Nenhuma chave existente
     alterada.
   - `longterm_validate.py` — validação transversal (compara as cartas de um run entre si).
   - Docs: `docs/LONGO_PRAZO.md`, `CHANGELOG.md`, `README.md`, `CLAUDE.md`,
     `.claude/skills/scan-ebay/SKILL.md`, este arquivo.

## Invariantes que a rodada respeita (não quebrar)

1. A coluna **Longo prazo** é informativa: nunca entra em gate, veredito, ranking nem
   recomendação de compra.
2. `src/slab_strategy.py` e o bloco `slab_strategy` do `config.yaml` **não foram tocados**
   (diff vazio contra a `main`). Conferir com `git diff origin/main -- src/slab_strategy.py`.
3. A cesta de vendas que alimenta a referência não muda: a coluna só lê o que já existe.
4. Nunca recomendar compra — capital é decisão do operador.
5. Toda linha entregue carrega os DOIS links: `[oferta]` e `[referência]`.
6. `n/d` nunca vira 0.

## Estado de verificação — o que AINDA não foi feito

- **Nenhum run real com a coluna.** Os artefatos locais em `results/last_scan_g*.json` e os
  relatórios `results/ebay-g*-*.md` são de **2026-09-04**, anteriores à coluna: nenhum deles
  tem campo `longterm_tier`. Ou seja, a coluna está coberta por teste, e **não** por execução
  real. Para ver a coluna é preciso um run novo (`main.py --group <N> --out results\...json`,
  entrega por `ebay_summary.py`), e um run novo só acontece a pedido do operador.
- **`longterm_validate.py` nunca rodou com dado suficiente.** Ele exige um mínimo de chaves
  (carta, número, nota) agregadas — `--min-keys`; abaixo disso escreve "n insuficiente" e não
  inventa correlação. Não existe `results/snapshots/` ainda, então também não há os dois
  snapshots com intervalo mínimo que um backtest exigiria.
- **Calibração da coluna é inicial e não validada**: pontos, bandas e limiares nunca foram
  medidos contra o mercado real.
- Contagens do funil de um run: ler `meta.funnel` do JSON em `results/` (chaves `cards`,
  `ebay_calls`, `fetched`, `seen`, `dedup_dropped`, `skip_*`, `*_error`, `longterm_error`).
  Ficam **só locais / no chat** — não entram neste arquivo nem em nenhum outro do repositório.

## Perguntas ao operador em aberto (herdadas das fases anteriores)

- `ref-desalinhada` na política: calcular os preços pedidos (`asks`) só para alimentar essa
  flag informativa, ou manter `n/d` (o que trava o teto da classe em `LP2*` nesse caminho)?
- Cesta legada: manter "só contradição de identidade" ou exigir o número no título da venda,
  como a política já faz (fail-closed, cesta menor)?
- Replicar a guarda de identidade dentro de `src/slab_strategy.py`, que monta a própria cesta
  e não chama `pc_sales.comparable_sales`? Nada foi tocado nesse módulo.

## Regras de entrega e de repositório (relembrar antes de qualquer entrega)

- `DELIVERY_CHAT.md` manda: coleta nova a cada pedido, tabela do gerador canônico colada
  VERBATIM no chat, preço de referência clicável, todas as linhas, nada publicado no GitHub.
- `results/` e `data/` são locais e estão no `.gitignore`; nada de resultado, preço ou
  credencial em commit.
- Branch + PR sempre; quem mergeia é o operador.
## Continuação 2026-09-10 — cobertura de identidade

Branch `fix/catalog-identity-coverage`, baseada na branch do PR #36. Corrigidos os
títulos canônicos dos Base Sets modernos; adicionado catálogo EN com as 25
identidades da Classic Collection para proteger seleções parciais. Watchlist
permanece inalterada. Fonte e limitações em `src/catalog/README.md`.

Validação local: 835 testes aprovados; 3 regressões novas reproduziram os defeitos
antes da implementação. Não houve coleta de ofertas ou preços. Nenhum merge foi
executado. Esta atualização complementa, sem substituir, os PRs #36 e #35.
