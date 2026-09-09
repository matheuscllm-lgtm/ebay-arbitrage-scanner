# Coluna "Longo prazo" — perfil da carta / fragilidade do dado

Coluna **informativa** que acompanha cada anúncio na tabela de entrega (nos dois
geradores: `src/slab_report.render`, vigente, e a tabela legada de `src/report.py`).
Ela descreve a carta e a qualidade do dado que sustenta a linha. **Não decide nada**:
não muda veredito, não entra no gate (filtro obrigatório que decide se um anúncio
entra na tabela), não entra no ranking, não recomenda. Capital é decisão do operador.

Limiares e pontos são **calibração inicial, não validada** (nunca medidos contra o
mercado real — como o outlook, que tem 1 snapshot só). Triagem descritiva, não previsão.

## Como ler a célula

`LP2 64/35 (4/5·8/10)` = **classe** · **PERFIL/FRAGILIDADE** · (cobertura do perfil ·
cobertura da fragilidade).

- **PERFIL** (0-100) = características observadas da carta: personagem, raridade,
  tempo fora de impressão, faixa de preço da coluna PSA 10, tendência real das vendas.
- **FRAGILIDADE DO DADO** (0-100) = quão frágil é o dado da linha: referência com
  poucas vendas, PSA 10 pouco vendida, referência desalinhada dos anúncios, tiragem
  (variante de impressão) ambígua, preços dispersos, vendedor fraco, muitos anúncios
  iguais no mesmo run.
- **Classe LP1-LP4** = faixa de qualidade/completude do perfil: LP1 forte · LP2 médio ·
  LP3 fraco · LP4 frágil. Não é nota de compra e não ordena a tabela.
- **Cobertura** `4/5` = 4 dos 5 componentes do perfil tinham dado; `8/10` = 8 das 10
  fontes de fragilidade existiam. Sem dado = `n/d`, nunca um zero inventado, e cada
  ausência sai escrita como `LP:<nome>: n/d` nos motivos.
  - No **PERFIL**, que é uma MÉDIA, o componente ausente realmente sai da conta: 90 com
    4/5 quer dizer "média dos 4 que existiam".
  - Na **FRAGILIDADE**, que é uma SOMA, sair da soma é aritmeticamente o mesmo que valer
    zero. Por isso a leitura honesta da nota é **"problemas DETECTADOS entre os testes
    que puderam rodar"**, e não "fragilidade estimada": `0 (3/10)` significa "só 3 dos 10
    testes rodaram e nenhum acusou problema" — não "dado impecável". A cobertura ao lado
    da nota é parte da leitura, não enfeite, e a classe LP1 tem piso de cobertura
    (abaixo dele vira `LP2*`, ver "Classe").
- **Asterisco** (`LP2*`) = classe limitada por dado ausente: seria LP1, mas um dos três
  insumos-chave da fragilidade (`ref-fragil`, `psa10-iliquido`, `ref-desalinhada`)
  estava em `n/d`, **ou** a cobertura da fragilidade ficou abaixo do piso de LP1.
- **Cabeçalho e rodapé da entrega**: o cabeçalho traz a contagem por classe
  (`report.longterm_counts_line`, no formato `n LP1 · n LP2 · n LP3 · n LP4 · n n/d`, onde
  `LP2*` conta como LP2 e linha sem a coluna — JSON anterior a ela — conta como `n/d`); o
  rodapé traz a legenda única dos dois geradores (`report.LONGTERM_LEGEND`).
- **Coluna indisponível = `n/d`, nunca 0.** A célula sai `n/d` (sem as duas notas) tanto quando
  a linha não tem a coluna — JSON anterior a ela, coluna desligada, erro interno — quanto quando
  a CLASSE foi calculada como `n/d`; nesse segundo caso a cobertura fica junto
  (`n/d (2/5·8/10)`), porque ela explica por que a classe está indisponível.
  Com `longterm.enabled: false` a avaliação nem roda e todas as linhas saem `n/d`. Erro interno na coluna não derruba a linha nem a carta: a
  célula fica `n/d`, o erro vai para o log e é contado no funil como `longterm_error`
  ("Linhas mantidas com a coluna Longo prazo em n/d por erro interno"). `longterm.assess` é
  função pura (não altera `Opportunity` nem a referência) e `longterm.annotate` grava só os
  campos `longterm_*` / `trend_*`.
- Os motivos `LP:` (cada flag que disparou e cada insumo em `n/d`) aparecem na coluna
  `Flags` (tabela legada) ou na linha "Motivos:" da seção por carta (política). Nunca
  entram em `risk_flags` nem em `reasons`, que alimentam veredito e score.

## PERFIL = pontos disponíveis ÷ (20 × componentes disponíveis) × 100

`n/d` com menos de 3 dos 5 componentes. Fontes = sinais que o run já tem (custo zero).

| # | Componente | Fonte | Régua inicial (pontos) |
|---|---|---|---|
| B1 | Personagem | `pokemon_rank` da watchlist (lista dos 100 chases); `score` de `src/catalog/iconic_pokemon.csv` só como sinal | rank 1-10 → 20 · 11-25 → 16 · 26-50 → 12 · 51-100 → 6 · sem rank → `n/d` |
| B2 | Raridade | `rarity` (texto do tcgcsv), por substring do tier mais alto para o mais baixo; `ex`/`gx`/`v` só como palavra inteira | special illustration / alternate → 20 · illustration / trainer gallery / character → 16 · hyper / secret / rainbow / shiny / amazing / radiant → 14 · ultra / vmax / vstar / ex / gx / lv.x / prime / legend / prism / classic collection → 12 · holo em era vintage (grupos 3-4) → 12, em outra era → 6 · resto → 4 · vazio → `n/d` |
| B3 | Supply (tempo fora de impressão) | idade = ano corrente − `year` da watchlist; era pelo grupo canônico (`src/groups.py`) | ≥10 anos → 20 · 5-9 → 16 · 3-4 → 13 · 2 → 10 · 1 → 6 · 0 → 3 · **reprint forte** (reimpressão que aumenta a oferta) → teto 8 · sem ano → `n/d` |
| B4 | Faixa de preço PSA 10 | **coluna PSA 10** da página do PriceCharting (`fair.prices`), só informação — nunca a referência, nunca o preço do anúncio | <15 → 4 · 15-44 → 10 · 45-119 → 16 · 120-359 → 20 · 360-899 → 14 · ≥900 → 8 · sem coluna → `n/d` |
| B5 | Tendência real (12 m) | (ii) primeiro: mediana das vendas da **nota do anúncio** 0-180 d vs 180-365 d, só com ≥3 vendas em cada janela (`refs.sales_history`, só leitura). **Qual cesta é essa:** no caminho LEGADO é a MESMA cesta que gera a referência (`trend_source = sales_history`); no caminho da POLÍTICA (vigente) é uma cesta PRÓPRIA, mais frouxa — a referência da política (`slab_strategy.reference_sales`) usa a nota PSA-equivalente e ainda exige fonte eBay, id de venda numérico e único, idioma da carta e nada de lote/"best offer"/certificação incerta, filtros que esta cesta não aplica. Por isso o rótulo lá é `trend_source = sales_history:cesta-propria`, e B5 pode se apoiar em vendas que a política descartou da referência (não muda referência nem veredito: B5 só entra no PERFIL, informativo); senão (i) série mensal `VGPC.chart_data` do PriceCharting, bucket `manualonly` (PSA 10) — anúncio que não é PSA 10 recebe `trend_source = chart_data:psa10-proxy`. Na série, **0 = sem dado** → `n/d`. Ponto "de 12 m atrás" = último ponto ≤ hoje − 365 d, tolerância ±31 d. 36 m só informativo. O delta único da coluna nunca é tendência | ≥ +25% → 20 · +8..+25 → 16 · −8..+8 → 10 · −25..−8 → 5 · ≤ −25% → 2 |

Reprint forte (ideia do outlook, sobre o nome do set verbatim do tcgcsv): nome começa
com `SV:`, `SWSH:` ou `ME:` (set especial sem número de era) OU contém Paldean Fates,
Prismatic Evolutions, Champion's Path, Shining Fates, Crown Zenith, Ascended Heroes,
"151" como palavra inteira, ou Celebrations — exceto "Classic Collection".

Valores em dólares nas faixas de B4 são o preço da coluna PSA 10 (US$); "Double Rare"
fica em 4 por decisão da calibração inicial.

## FRAGILIDADE DO DADO = soma das flags, teto 100

`n/d` com menos de 3 das 10 fontes; ausência vira `LP:<flag>: n/d` nos motivos, nunca 0
em silêncio. Como é soma e não média, a nota mede **problemas detectados entre os testes
que rodaram** — leia sempre junto com a cobertura `k/10` (ver "Como ler a célula").

| Flag `LP:` | Fonte (caminho legado / caminho da política) | Pontos |
|---|---|---|
| `ref-fragil` | régua de `pc_sales.sales_reference`: **0 venda → `sem-vendas` +30** (rótulo próprio: "poucas vendas" onde não há venda nenhuma seria mentira) · 1-2 vendas → `thin` +30 · ≥3 só na janela de 365 d → `low` +15 · `ok` 0. Insumo: `ref_liquidity`; senão `ref_n_sales`/`ref_window_days`; senão `opp.strategy['psa_evidence']` (`n_used`, `window_days`); sem nenhum → `n/d`. O sinal `ref_source` diz de onde veio (`ref_*`, `psa_evidence`) | 0-30 |
| `psa10-iliquido` | `fair.sales_per_month['PSA 10']`: <1/mês +30 · <3 +20 · ≥3 0 · ausente → `n/d` (corte 3 = fronteira B/C da liquidez do scorer) | 0-30 |
| `ref-desalinhada` | legado: flag existente `REF DESALINHADA` (referência ÷ mediana dos anúncios limpos >1.5 ou <0.6; `ask_ratio` no sinal). **Política: `n/d` nesta rodada** — `asks = {}` é decisão documentada do operador; nada é recomputado | +20 |
| `reprint-forte` | mesma regra de B3 | +15 |
| `preco-absoluto-alto` | preço do anúncio ≥900 +15 · 300-899 +8 · <300 0 (só o limiar, sem juízo) | 0-15 |
| `vendedor-fraco` | corte já documentado no repo: `seller_feedback_score < trusted_min_feedback` (50) ou `seller_feedback_pct < trusted_min_feedback_pct` (98) — o mesmo par que a política usa em `historico-do-vendedor-insuficiente`; `trust_score` (0-100) vai só como sinal | +15 |
| `tiragem` | título com token de tiragem (reverse, 1st, edition, shadowless, unlimited, promo), `variant_tokens` não vazio, ou set de subconjunto (Shiny Vault, Galarian Gallery, Classic Collection, Radiant Collection, Trainer Gallery) | +10 |
| `dispersao` | **o mesmo valor que já rebaixa para REVISAR na política**: (máx − mín) ÷ mediana × 100 das vendas usadas na referência, corte `evidence.max_dispersion_percent` (30). Política: valor mostrado = `psa_evidence.dispersion_percent` (arredondado), mas a comparação com o corte usa `psa_evidence.dispersion_exact` — **o mesmo Decimal que a política compara** —, senão os dois discordariam na fronteira (dispersão real de 30,004% rebaixa a linha e arredonda para 30,00); legado: a mesma fórmula sobre `refs.sales_history` (janela da referência, 10 vendas mais recentes). Uma definição, um nome. Ressalva: a coluna olha só a cesta PSA, enquanto a política checa dispersão também na cesta de `revenda` (relevante só em anúncio que não é PSA) | +10 |
| `ref-stale` | legado: flags existentes `REF GRADED < RAW TCG` / `ref-divergente` (disponível só quando há market TCG para conferir). Política: `n/d` | +10 |
| `concentracao` | mesma carta + mesma nota com ≥4 anúncios no mesmo run (`concentration_min_listings`), contados antes da avaliação e aplicados a todas as linhas daquela carta+nota, inclusive as primeiras. Só entram na contagem os anúncios cujo TÍTULO é mesmo daquela carta (mesma guarda de identidade — `title_parser.card_matches_title` — que `_clean_ask_prices` já usava): a busca do eBay devolve anúncios de outras cartas junto, e eles são descartados logo depois (`skip_no_match`) | +10 |

## Classe (avaliar nesta ordem)

1. `n/d` se PERFIL ou FRAGILIDADE é `n/d`.
2. **LP4** se FRAGILIDADE > 70 ou PERFIL < 30.
3. **LP1** se PERFIL ≥ 70, FRAGILIDADE ≤ 30, cobertura do perfil ≥ 4/5, cobertura da
   fragilidade ≥ 8/10 (`LP1_MIN_FRAGILITY_COVERAGE`, mesma proporção de 80% do piso do
   perfil) **e** os três insumos-chave (`ref-fragil`, `psa10-iliquido`,
   `ref-desalinhada`) disponíveis. O piso de cobertura da fragilidade existe porque a
   nota é uma soma: sem ele, uma linha em que 7 dos 10 testes nem puderam rodar sairia
   com nota 0 e classe "forte" igual a uma linha com os 10 testes limpos.
4. **LP2** se PERFIL ≥ 50 e FRAGILIDADE ≤ 50 — inclui o caso que seria LP1 mas tem
   insumo-chave em `n/d` ou cobertura de fragilidade abaixo do piso → **`LP2*`**.
5. **LP3** caso contrário.

Consequência declarada: no caminho da política (`slab_strategy`, vigente), o teto
nesta rodada é **`LP2*`**, porque `ref-desalinhada` é `n/d` (`asks = {}`) até o operador
decidir sobre o cálculo dos asks só para a flag informativa.

## O que NÃO é

Não é previsão de preço, não é conselho, não é gate, não é ranking, não é
"oportunidade" nem recomendação de compra. Não cria uma segunda referência: lê a
que já existe (`ref_*` / `psa_evidence`) e a cesta de vendas já montada — mas a cesta
lida por B5 no caminho da política é mais frouxa que a da referência e vai rotulada
como `sales_history:cesta-propria` (ver B5 acima).
"Valorização" (subida de preço ao longo do tempo) **não é medida** aqui — a coluna
descreve características e fragilidade de dado, e a calibração transversal (comparar
cartas de hoje entre si) não é prova de valorização futura.

## Links e configuração

- `[oferta]` = página do anúncio no eBay (onde se compra); `[referência]` = página da
  carta no PriceCharting (onde se valida o preço). Toda linha traz os dois; nenhuma URL
  é inventada.
- Bloco `longterm:` do `config.yaml` (inteiros): `enabled`, `lp1_min_profile: 70`,
  `lp1_max_fragility: 30`, `lp2_min_profile: 50`, `lp2_max_fragility: 50`,
  `lp4_max_profile: 30`, `lp4_min_fragility: 70`, `min_profile_sources: 3`,
  `min_fragility_sources: 3`, `concentration_min_listings: 4`. Pontos por componente e
  bandas ficam no código (`src/longterm.py`) como calibração inicial. Nada muda no
  gate, na política, no piso, nos pesos do score nem no ranking.

## Validação mínima (`longterm_validate.py`)

Sobre o JSON de um scan: agrega por chave (carta, número, nota) **antes** de qualquer
estatística (11 anúncios do mesmo item contam 1 — evita pseudo-replicação); exige
n ≥ 30 chaves; Spearman (ρ, correlação de postos) de B1, B2, B3, B5 e do PERFIL-sem-B4
contra `fair_value` e contra o prêmio PSA 10 ÷ RAW; **B4 excluído** (é derivado de preço,
seria circular). Rótulos: ρ > 0.1 ✅ · −0.1..0.1 ⚠️ fraco · ≤ −0.1 ❌ invertido. Com
n < 30: "n insuficiente (k cartas)", sem inventar ρ. Snapshot datado em
`results/snapshots/longterm_AAAA-MM-DD.csv` (local, nunca no GitHub) — insumo de um
backtest futuro só com ≥ 2 snapshots com ≥ 21 dias de intervalo.

## Limitações conhecidas

- Bandas de B4 = faixas raw ×3, calibradas em n = 25 (dispersão p25 2,5× / p75 5,4×).
- `chart_data` tem 6 buckets (Ungraded, Grade 7, 8, 9, 9.5, PSA 10): sem série própria
  de BGS/CGC/SGC/TAG — por isso o proxy PSA 10 é rotulado.
- Histórico diário do tcgcsv por productId (market de carta solta EN) fica no backlog.
- `pop_data` (população gradada) não é lida nesta rodada.
- Nenhuma validação empírica ainda: 1 snapshot, backtest não roda.
