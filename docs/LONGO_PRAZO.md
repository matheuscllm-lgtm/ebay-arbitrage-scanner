# Longo prazo — tese, entrada e evidência

## Crivo vigente (`src/investment.py`)

O modo `slab_strategy.economics.gate_mode: longterm` separa três eixos, sem
esconder incerteza em uma nota média e sem produzir cenários de preço futuro.
Ele considera apenas PSA 10 EN/JP, preço fixo, item nos EUA e preço do item até
US$500. Capital e decisão final continuam com o operador.

| Eixo | Estados | Informação que decide |
|---|---|---|
| Tese | `favorable`, `neutral`, `unfavorable`, `unconfirmed` | Quatro sinais documentados e atuais, independentes do preço do anúncio |
| Entrada | `attractive`, `unattractive`, `unconfirmed` | Margem bruta estritamente acima de **20%** e lucro líquido operacional atual positivo com custos completos |
| Evidência | `adequate`, `insufficient` | Identidade, vendedor, comparáveis, dispersão e recorrência observada |

O critério de dois meses-calendário é um indício fraco de distribuição, não
prova recorrência: vendas concentradas na virada de um mês podem satisfazê-lo.
A curadoria de demanda e resiliência deve verificar esse risco de pico temporário.

OPORTUNIDADE exige tese favorável, entrada atrativa e evidência adequada ao mesmo
tempo. MONITORAR mantém uma tese neutra/favorável com dados suficientes, mas sem
convergência completa para oportunidade, inclusive preço alto. REVISAR significa
incerteza de dados ou referência; REJEITAR, restrição estrutural ou tese
desfavorável. Nenhuma classe é recomendação de compra.

### Tese documentada: convergência, não previsão

Cada carta tem quatro sinais: `demand` (demanda perene), `collectibility`
(importância da carta/arte), `supply` (oferta efetiva e provável) e `resilience`
(resistência a hype e substitutos). Cada sinal exige direção, fonte HTTPS, data
ISO e justificativa. Também se registra a condição que invalidaria a tese.

- **Favorável:** os quatro sinais confirmados, demanda `supportive`, pelo menos
  três sinais `supportive` e nenhum `adverse`.
- **Desfavorável:** os quatro confirmados e demanda `adverse` ou pelo menos dois
  sinais `adverse`.
- **Neutra:** quatro confirmados, mas sem atender às duas regras anteriores.
- **Não confirmada:** sinal ausente, data futura ou evidência com mais de
  `max_thesis_age_days` (180 dias por padrão). Não vira favorável pela média dos
  sinais restantes. Omitir `--thesis-file` é permitido, mas não aprova
  oportunidades; informar caminho inexistente falha explicitamente.

A validade formal de uma URL não prova seu conteúdo. Trata-se de curadoria manual
do operador: o scanner não busca nem verifica automaticamente as fontes da tese.
Popularidade, primeira aparição e arte relevante são argumentos possíveis, não
pontuação automática. População baixa sem demanda não comprova escassez econômica;
set fora de impressão não prova queda da oferta futura de PSA 10. População e
ritmo de novas graduações precisam de fontes próprias quando usados na tese.

### Arquivo privado de teses

Carregar com `--thesis-file data/theses.yaml`. Formato abaixo é **sintético**, não
uma carta nem uma oportunidade real; datas e fontes devem ser substituídas por
evidência válida. Não versionar este arquivo preenchido nem seus resultados.

```yaml
version: 1
cards:
  - name: Example Card
    set: Example Set
    number: "1/100"
    language: EN
    grade: PSA 10
    variants: []
    invalidation: "Descrever o fato observável que invalidaria esta tese."
    signals:
      demand:
        direction: supportive
        source: https://example.test/demand
        as_of: "2026-09-11"
        reason: "Justificativa documentada da demanda."
      collectibility:
        direction: supportive
        source: https://example.test/collectibility
        as_of: "2026-09-11"
        reason: "Justificativa da importância colecionável."
      supply:
        direction: neutral
        source: https://example.test/supply
        as_of: "2026-09-11"
        reason: "Oferta conhecida, sem vantagem clara."
      resilience:
        direction: supportive
        source: https://example.test/resilience
        as_of: "2026-09-11"
        reason: "Justificativa além de hype de curto prazo."
```

Direções aceitas: `supportive`, `neutral`, `adverse`. A identidade combina nome,
set, número, idioma, nota e variantes explícitas; não há wildcard nem equivalência
entre EN e JP. Duplicatas ou esquema inválido falham sem imprimir o conteúdo
privado. Fontes, datas, justificativas e invalidação são preservadas no resultado
local para auditoria. O cadastro não fornece preço justo nem altera vendas.

Prática validada em 2026-09-12 (piloto): gere o arquivo como **esqueleto** — identidade
copiada do JSON de pré-seleção (`name`, `set`, `number`, `language`, `grade: PSA 10`,
`variants: []`) e todo o resto em `null`. O loader recusa o arquivo inteiro
(`Invalid thesis field: cards[i].<campo>`) até o último campo ser preenchido — use isso
como checklist; **nunca** use URL/data de exemplo como placeholder, porque uma URL válida
de exemplo viraria sinal "confirmado". O `set` tem de ser a string **exata** da watchlist
(`SV: Paldean Fates`, não `Paldean Fates`): identidade diferente não casa nenhum anúncio e
a carta cai em REVISAR como tese não confirmada. Confira antes do scan:
`python main.py --check-config --thesis-file private/theses.yaml --watchlist <json da pré-seleção>`
imprime quantas teses têm carta correspondente (só contagens, nunca identidades).

### Entrada e evidência

`min_gross_margin_percent: 20` significa **20%** sobre o preço do item:
`(revenda comprovada − item) / item ×100`. Exatamente 20% não passa; a comparação
é feita antes de arredondar. Não é desconto sobre a referência nem retorno all-in.
No modo `longterm`, o piso de 20% é fixo; CLI/config com outro valor são rejeitados.
Lucro líquido atual positivo também é obrigatório para OPORTUNIDADE, após a
estimativa de custos existente. Os 120 dias do modelo COMC **não modelam custódia
de 3–5 anos** e não permitem anunciar retorno líquido futuro.

O eixo de evidência exige pelo menos `min_sales_90d: 9` vendas exatas observadas
nos últimos 90 dias, distribuídas em `min_active_months_90d: 2` meses-calendário
ou mais. Contar antes do corte das 10 vendas usadas na mediana evita truncar a
liquidez. A referência mantém as janelas de 180/365 dias, guardas de identidade,
exclusão de duplicatas/best offer sem preço confirmado e dispersão máxima de 30%.
Recorrência aproximada de 3 vendas/mês não significa todos os negócios do eBay,
compradores únicos ou liquidez garantida. Os limiares ainda exigem calibração
empírica; não representam probabilidade de sucesso.

### Sem Top100 de elegíveis

O universo pesquisável e o lote operacional são diferentes de elegibilidade.
Nenhuma quantidade mínima de oportunidades é exigida; zero é válido. Os 100
personagens do catálogo não são 100 cartas para comprar. O gerador não limita
cartas por set por padrão, mas mantém os outros filtros e a cobertura disponível.
`--max-cards`/`--card-offset` recortam apenas o processamento e reportam adiados;
não afrouxam a tese, a margem ou a evidência para preencher vagas.

## Diagnóstico legado LP (`src/longterm.py`)

A coluna LP **informativa** acompanha cada anúncio na tabela de entrega (nos dois
geradores: `src/slab_report.render`, vigente, e a tabela legada de `src/report.py`).
Ela descreve a carta e a qualidade do dado que sustenta a linha. **Não decide nada**:
não muda veredito, não entra no gate (filtro obrigatório que decide se um anúncio
entra na tabela), não entra no ranking, não recomenda. É separada do crivo de
investimento acima: uma LP1 não equivale a `thesis.status: favorable`.

Limiares e pontos são **calibração inicial, não validada** (nunca medidos contra o
mercado real). Triagem descritiva, não previsão. As seções abaixo documentam esse
diagnóstico legado; suas heurísticas não preenchem os sinais da tese nova.

## Como ler a célula

`LP2 64/35 (4/5·9/11)` = **classe** · **PERFIL/FRAGILIDADE** · (cobertura do perfil ·
cobertura da fragilidade).

- **PERFIL** (0-100) = características observadas da carta: personagem, raridade,
  tempo fora de impressão, faixa de preço da coluna PSA 10, tendência real das vendas.
- **FRAGILIDADE DO DADO** (0-100) = quão frágil é o dado da linha: referência com
  poucas vendas, PSA 10 pouco vendida, referência desalinhada dos anúncios, tiragem
  (variante de impressão) ambígua, preços dispersos, vendedor fraco, muitos anúncios
  iguais no mesmo run e meses de estoque altos (`estoque-alto`).
- **Classe LP1-LP4** = faixa de qualidade/completude do perfil: LP1 forte · LP2 médio ·
  LP3 fraco · LP4 frágil. Não é nota de compra e não ordena a tabela.
- **Cobertura** `4/5` = 4 dos 5 componentes do perfil tinham dado; `9/11` = 9 das 11
  fontes de fragilidade existiam. Sem dado = `n/d`, nunca um zero inventado, e cada
  ausência sai escrita como `LP:<nome>: n/d` nos motivos.
  - No **PERFIL**, que é uma MÉDIA, o componente ausente realmente sai da conta: 90 com
    4/5 quer dizer "média dos 4 que existiam".
  - Na **FRAGILIDADE**, que é uma SOMA, sair da soma é aritmeticamente o mesmo que valer
    zero. Por isso a leitura honesta da nota é **"problemas DETECTADOS entre os testes
    que puderam rodar"**, e não "fragilidade estimada": `0 (3/11)` significa "só 3 dos 11
    testes rodaram e nenhum acusou problema" — não "dado impecável". A cobertura ao lado
    da nota é parte da leitura, não enfeite, e a classe LP1 tem piso de cobertura
    (abaixo dele vira `LP2*`, ver "Classe").
- **Asterisco** (`LP2*`) = classe limitada por dado ausente: seria LP1, mas um dos três
  insumos-chave da fragilidade (`ref-fragil`, `psa10-iliquido`, `ref-desalinhada`)
  estava em `n/d`, **ou** a cobertura da fragilidade ficou abaixo do piso de LP1.
- **Cabeçalho e rodapé da entrega**: o cabeçalho traz a contagem por classe
  (`report.longterm_counts_line`, no formato `n LP1 · n LP2 · n LP3 · n LP4 · n n/d`, onde
  `LP2*` conta como LP2 e linha sem a coluna — JSON anterior a ela — conta como `n/d`); o
  rodapé traz a legenda única (`report.LONGTERM_LEGEND`). Os **três** geradores são
  coerentes: a coluna aparece em TODOS os baldes (inclusive o REJEITADO da entrega legada,
  que a contagem do cabeçalho já somava) e a legenda vai no rodapé de todos, inclusive do
  console legado (`report.to_markdown`), cuja tabela também é colada verbatim no chat.
- **Coluna indisponível = `n/d`, nunca 0.** A célula sai `n/d` (sem as duas notas) tanto quando
  a linha não tem a coluna — JSON anterior a ela, coluna desligada, erro interno — quanto quando
  a CLASSE foi calculada como `n/d`; nesse segundo caso a cobertura fica junto
  (`n/d (2/5·9/11)`), porque ela explica por que a classe está indisponível.
  Com `longterm.enabled: false` a avaliação nem roda e todas as linhas saem `n/d`. Erro interno na coluna não derruba a linha nem a carta: a
  célula fica `n/d`, o erro vai para o log e é contado no funil como `longterm_error`
  ("Linhas mantidas com a coluna Longo prazo em n/d por erro interno"). `longterm.assess` é
  função pura (não altera `Opportunity` nem a referência) e `longterm.annotate` grava só os
  campos `longterm_*` / `trend_*`.
- Os motivos `LP:` aparecem na coluna `Flags` (tabela legada) ou na linha "Motivos:" da
  seção por carta (política). Nunca entram em `risk_flags` nem em `reasons`, que
  alimentam veredito e score. Na coluna `Flags` entram **só os que dispararam**: os
  `LP:<nome>: n/d` podem ser 15 numa linha e empurrariam para longe o sinal de risco real
  (FRAUDE PROVÁVEL, REF DESALINHADA…) numa tabela que é colada verbatim no chat. Nada se
  perde — as ausências seguem inteiras no JSON (`longterm_reasons`), resumidas na
  cobertura `k/5·k/11` da célula, e a linha "Motivos:" da política continua listando-as.

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

`n/d` com menos de 3 das 11 fontes; ausência vira `LP:<flag>: n/d` nos motivos, nunca 0
em silêncio. Como é soma e não média, a nota mede **problemas detectados entre os testes
que rodaram** — leia sempre junto com a cobertura `k/11` (ver "Como ler a célula").

| Flag `LP:` | Fonte (caminho legado / caminho da política) | Pontos |
|---|---|---|
| `ref-fragil` | régua de `pc_sales.sales_reference`: **0 venda → `sem-vendas` +30** (rótulo próprio: "poucas vendas" onde não há venda nenhuma seria mentira) · 1-2 vendas → `thin` +30 · ≥3 só na janela de 365 d → `low` +15 · `ok` 0. Insumo: `ref_liquidity`; senão `ref_n_sales`/`ref_window_days`; senão `opp.strategy['psa_evidence']` (`n_used`, `window_days`); sem nenhum → `n/d`. O sinal `ref_source` diz de onde veio (`ref_*`, `psa_evidence`) | 0-30 |
| `psa10-iliquido` | `fair.sales_per_month['PSA 10']`: <1/mês +30 · <3 +20 · ≥3 0 · ausente → `n/d` (corte 3 = fronteira B/C da liquidez do scorer) | 0-30 |
| `ref-desalinhada` | referência ÷ mediana dos anúncios limpos da mesma nota >1.5 ou <0.6 (`ask_ratio` no sinal). Disponível nos DOIS caminhos desde 2026-09-09: os preços pedidos passaram a ser calculados também na política, a partir dos anúncios que o run já baixou (custo zero de API). O CÁLCULO roda nos dois; o EFEITO NO VEREDITO (rebaixar OPORTUNIDADE para REVISAR, `risk_flags`, `reasons`) continua **só no legado**, porque a coluna não pode tocar veredito | +20 |
| `reprint-forte` | mesma regra de B3 | +15 |
| `preco-absoluto-alto` | preço do anúncio ≥900 +15 · 300-899 +8 · <300 0 (só o limiar, sem juízo) | 0-15 |
| `vendedor-fraco` | corte já documentado no repo: `seller_feedback_score < trusted_min_feedback` (50) ou `seller_feedback_pct < trusted_min_feedback_pct` (98) — o mesmo par que a política usa em `historico-do-vendedor-insuficiente`; `trust_score` (0-100) vai só como sinal | +15 |
| `tiragem` | título com token de tiragem (reverse, 1st, edition, shadowless, unlimited, promo), `variant_tokens` não vazio, ou set de subconjunto (Shiny Vault, Galarian Gallery, Classic Collection, Radiant Collection, Trainer Gallery) | +10 |
| `dispersao` | **o mesmo valor que já rebaixa para REVISAR na política**: (máx − mín) ÷ mediana × 100 das vendas usadas na referência, corte `evidence.max_dispersion_percent` (30). Política: valor mostrado = `psa_evidence.dispersion_percent` (arredondado), mas a comparação com o corte usa `psa_evidence.dispersion_exact` — **o mesmo Decimal que a política compara** —, senão os dois discordariam na fronteira (dispersão real de 30,004% rebaixa a linha e arredonda para 30,00); legado: a mesma fórmula sobre `refs.sales_history` (janela da referência, 10 vendas mais recentes). Uma definição, um nome. Ressalva: a coluna olha só a cesta PSA, enquanto a política checa dispersão também na cesta de `revenda` (relevante só em anúncio que não é PSA) | +10 |
| `ref-stale` | legado: flags existentes `REF GRADED < RAW TCG` / `ref-divergente` (disponível só quando há market TCG para conferir). Política: `n/d` | +10 |
| `concentracao` | mesma carta + mesma nota com ≥4 anúncios no mesmo run (`concentration_min_listings`), contados antes da avaliação e aplicados a todas as linhas daquela carta+nota, inclusive as primeiras. Só entram na contagem os anúncios cujo TÍTULO é mesmo daquela carta (mesma guarda de identidade — `title_parser.card_matches_title` — que `_clean_ask_prices` já usava): a busca do eBay devolve anúncios de outras cartas junto, e eles são descartados logo depois (`skip_no_match`) | +10 |
| `estoque-alto` | **meses de estoque** = `listings_same_grade` (anúncios ativos da mesma carta+nota no run) ÷ `psa10_sales_pm` (vendas PSA 10 por mês, do PriceCharting). **Só em linhas PSA 10**: o PriceCharting traz volume por certificadora apenas nessa coluna, e as demais notas caem no balde genérico `GRADE 9`, que mistura certificadoras e que este repo proíbe rotular como PSA — dividir anúncios PSA 9 por vendas PSA 10 não é meses de estoque de coisa nenhuma. ≥ `supply_months_high` (24) +20 · ≥ `supply_months_mid` (12) +10 · abaixo 0. `n/d` fora da PSA 10, sem anúncio contado, ou com `psa10_sales_pm < supply_min_sales_pm` (0.05), onde a divisão fica instável. É o ÚNICO sinal de oferta contra demanda real da régua: o componente B3, apesar do nome "supply", mede idade e reimpressão, não estoque | 0-20 |

### Teto da família que compartilha insumo

`psa10-iliquido` (vendas/mês), `concentracao` (nº de anúncios) e `estoque-alto` (a divisão
dos dois) leem os **mesmos dois números**. Somadas cheias, uma única observação viraria 60
pontos e jogaria a linha para LP4 com a mesma evidência que dava LP2 antes da 11ª flag
existir. Por isso a família inteira (`SHARED_SUPPLY_FLAGS`) contribui no máximo
`SHARED_SUPPLY_CAP` = 30, que é o que a leitura mais forte dela já contribuía sozinha. O
teto **não** mexe na cobertura: cada flag continua contando como fonte que rodou.

## Classe (avaliar nesta ordem)

1. `n/d` se PERFIL ou FRAGILIDADE é `n/d`.
2. **LP4** se FRAGILIDADE > 70 ou PERFIL < 30.
3. **LP1** se PERFIL ≥ 70, FRAGILIDADE ≤ 30, cobertura do perfil ≥ `lp1_min_profile_coverage`
   (4 de 5), cobertura da fragilidade ≥ `lp1_min_fragility_coverage` (**8** de 11 — a
   contagem absoluta que já valia quando eram 10 flags; subir para 9 rebaixaria linhas
   que davam LP1 sem nenhuma evidência nova, só porque entrou a 11ª)
   **e** os três insumos-chave (`ref-fragil`, `psa10-iliquido`, `ref-desalinhada`)
   disponíveis. Os dois pisos eram constantes no código e viraram chave do bloco
   `longterm:` do config.yaml em 2026-09-09. O piso de cobertura da fragilidade existe
   porque a nota é uma soma: sem ele, uma linha em que 8 dos 11 testes nem puderam rodar
   sairia com nota 0 e classe "forte" igual a uma linha com os 11 testes limpos.
4. **LP2** se PERFIL ≥ 50 e FRAGILIDADE ≤ 50 — inclui o caso que seria LP1 mas tem
   insumo-chave em `n/d` ou cobertura de fragilidade abaixo do piso → **`LP2*`**.
5. **LP3** caso contrário.

Desde a revisão de 2026-09-09, `ref-desalinhada` é calculada também no caminho da
política, com os anúncios já coletados. Não existe teto universal `LP2*`; a
limitação depende dos dados e da cobertura daquela linha.

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

- Bandas históricas de B4 derivaram de faixas raw ×3. Isso não é estimador válido
  de PSA 10 e não pode preencher preço, referência ou tese do crivo vigente.
- `chart_data` tem 6 buckets (Ungraded, Grade 7, 8, 9, 9.5, PSA 10): sem série própria
  de BGS/CGC/SGC/TAG — por isso o proxy PSA 10 é rotulado.
- Histórico diário do tcgcsv por productId (market de carta solta EN) fica no backlog.
- `pop_data` (população gradada) não é lida nesta rodada.
- Nenhuma validação empírica ainda: 1 snapshot, backtest não roda.
