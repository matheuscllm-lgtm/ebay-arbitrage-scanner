
## 2026-09-11 — tese, entrada e evidência; elegibilidade sem quota

- Política padrão `longterm` (2026-09-11.1): PSA 10 EN/JP, preço fixo nos EUA,
  item até US$500. Margem bruta estritamente acima de **20%**, exibida com seu
  denominador, mais lucro líquido operacional atual positivo; margem sozinha
  deixa de aprovar.
- Teses privadas por `--thesis-file`: demanda, importância colecionável, oferta
  e resiliência com direção, fonte, data, justificativa e condição de invalidação.
  Não transforma LP1 ou preço raw em tese; fonte ausente ou antiga exige revisão.
- Evidência adicional exige ≥9 vendas exatas observadas em 90 dias, em ≥2
  meses-calendário, contadas antes do limite de amostra da mediana.
- OPORTUNIDADE / MONITORAR / REVISAR / REJEITAR separados dos modos econômicos
  legados, que continuam disponíveis explicitamente. Sem compras automáticas ou
  cenários de preço futuro; custo COMC de 120 dias não modela retorno de 3–5 anos.
- Sem meta Top100: os 100 personagens são metadados. Gerador sem teto por set
  por padrão; `--max-cards` e `--card-offset` limitam somente processamento,
  com adiados/parcialidade explícitos e saídas de lote separadas. Catálogo não
  regenerado nesta alteração.
- Implementação e regressões offline; nenhuma coleta de mercado executada nesta
  tarefa. Teses, alvos, preços, resultados e credenciais não são publicados.

As entradas abaixo descrevem políticas históricas, não o padrão atual.

## 2026-09-09 (3) — identidade por edição e ano (`fix/identidade-edicao-e-ano`)

Achado no PRIMEIRO run real do grupo 3: anúncios da Celebrations: Classic Collection
(2021) casaram como Base Set (1999) e a linha saiu com margem absurda contra a
referência da carta ERRADA. A reimpressão repete nome e número, e o título traz "Base
Set" porque é o que está estampado na carta.

O mecanismo de defesa (`exclude_keywords`) já existia, já tinha teste verde desde o 1º
scan real — e a watchlist de produção tinha ZERO carta preenchida. Teste alimentado à
mão não prova comportamento de produção; por isso os testes novos assertam sobre a
WATCHLIST REAL e há guarda de drift exigindo que toda carta em colisão declare suas
edições colidentes.

Três faixas por força de evidência (`outra-edicao`, `conflito-de-ano`, `edicao-ambigua`),
com a colisão DERIVADA da watchlist (58 pares nome+número em mais de uma edição). Na
cesta de vendas só contradição exclui: ambiguidade não amputa venda legítima, erro já
registrado no PR #32.

Medido sobre um run local do grupo 3 (artefato fica em `results/`, gitignored): a
guarda marca três faixas em ordem de milhares de linhas, e as linhas que perdem a
comparação automática são exatamente as de retorno absurdo mais uma de carta japonesa
que passara por baixo do filtro de idioma. 828 testes verdes (798 na base + 30 novos).

Limitação conhecida e medida: a faixa 3 só existe quando AS DUAS edições estão na
watchlist. A Classic Collection tem 25 cartas e a watchlist tem 15, então as originais
das 10 ausentes seguem sem essa rede — a faixa 1 (alias no título) continua valendo.

## 2026-09-09 (2) — gate por MARGEM BRUTA, preços pedidos na coluna e sinal de MESES DE ESTOQUE

Rodada decidida pelo operador em cima da auditoria do run real de 2026-09-09 (grupo 3, 6.104
anúncios). Três mudanças de comportamento e duas de configurabilidade.

### 1. O gate econômico passa a usar SÓ margem bruta

Regra canônica da frota: **margem bruta, sem taxa nenhuma**. Antes, a política aprovava por
`profit_or_discount` — lucro líquido acima de US$40 (com taxa de venda e de saque modeladas) OU
desconto acima de 30% sobre a referência. Lucro líquido contradizia a regra da frota; foi
autorizado em sessão autônoma anterior, não pelo operador.

- `economics.gate_mode: gross_margin`, `min_gross_margin_percent: 43`, limite estrito.
- Margem bruta = (referência − preço) / **preço** ×100, comparada em `Decimal` exato.
- 43 preserva a fronteira do desconto de 30% sobre a referência (30/(100−30) = 42,857…%) e
  respeita a convenção do repo de percentual INTEIRO, com 0,14 p.p. a mais de rigor.
- **O gate deixou de depender do modelo de custos.** Antes, toda a avaliação econômica vivia
  dentro de um `if` que exigia o custo completo; no run de 2026-09-09, 5.975 de 6.104 linhas
  não tinham base de custo (`armazenamento-sem-base-de-revenda`), então um gate preso ao custo
  simplesmente não tinha opinião sobre elas.
- Custos COMC continuam calculados e no JSON (`profit_estimate`, `net_margin_percent`,
  `net_roi_percent`, `costs`) como INFORMAÇÃO. Não decidem mais veredito: em `gross_margin` os
  rejeitos `lucro-nao-positivo`, `nao-atende-lucro-ou-desconto-minimo`, `desconto-abaixo-do-minimo`
  e `abaixo-de-min_net_*` não disparam, e a marcação `suspicious_margin_percent` (60) também
  não — ela contradiz um gate que aprova a partir de 43%.
- Modos legados (`profit_or_discount`, `all_minima`) seguem no código e nos testes.
- CLI: `--min-gross-margin N` (inteiro). `--min-discount` passa a valer só nos modos legados.

### 2. Preços pedidos passam a alimentar a coluna, sem tocar veredito

`_annotate_ref_alignment` fazia duas coisas ao mesmo tempo: calculava a mediana dos preços
pedidos E rebaixava o veredito de OPORTUNIDADE para REVISAR. Por isso o caminho da política
mantinha `asks = {}`, e a flag `ref-desalinhada` ficava em `n/d`, travando a classe em `LP2*`.

As duas responsabilidades foram separadas: o CÁLCULO roda nos dois caminhos (custo zero de API,
os anúncios já estão em memória); o EFEITO NO VEREDITO continua só no legado. O teto `LP2*` da
política caiu.

### 3. "Meses de estoque" — o primeiro sinal de oferta contra demanda da régua

A coluna não tinha nenhum sinal de estoque real: o componente B3, apesar de se chamar "supply",
mede idade e reimpressão. A auditoria do snapshot mostrou que o PERFIL correlaciona com o
PREÇO de referência e não com o prêmio da PSA 10 — ou seja, ele estava redescobrindo o preço
que já aparece na linha ao lado.

Nova flag de FRAGILIDADE `estoque-alto`, a 11ª: `listings_same_grade` ÷ `psa10_sales_pm`.
≥ `supply_months_high` (24) +20 · ≥ `supply_months_mid` (12) +10 · abaixo 0 · `n/d` quando falta
insumo ou quando as vendas por mês ficam abaixo de `supply_min_sales_pm` (0.05), onde a divisão
fica instável. Os dois insumos já eram coletados e nunca tinham sido combinados. A cobertura da
fragilidade passa de `k/10` para `k/11`.

### 4. Pisos de cobertura da LP1 viraram configuração

`LP1_MIN_PROFILE_COVERAGE` e `LP1_MIN_FRAGILITY_COVERAGE` eram constantes no código, escolhidas
por proporção e não por medição. Agora são `longterm.lp1_min_profile_coverage` (4 de 5) e
`longterm.lp1_min_fragility_coverage` (9 de 11).

### 5. Cesta legada: chave existe, desligada por padrão

`pc_sales.comparable_sales` ganhou `require_number` (keyword-only, default `False`). Com `True`
a cesta legada passa a exigir o número da carta no título da venda, como o caminho vigente já
faz, reutilizando `title_parser.card_matches_title` via a mesma chamada de
`slab_strategy.identity_matches` — uma régua, não duas. `legacy_reference.require_number_in_sale_title`
fica em `false`: unificar encolhe a cesta, e a cobertura de referência já é o gargalo (só 2,7%
das linhas do run tiveram referência, com mediana de 2 vendas quando havia). Carta de watchlist
sem número é fail-closed com `True`, igual ao caminho vigente.

### Guardas de drift novas

`tests/test_docs_drift.py` passa a exigir que a skill e `docs/EBAY_PSA.md` nomeiem o `gate_mode`
que está de fato no `config.yaml` (e o limiar daquele modo, que tem de ser inteiro), e que toda
cobertura `k/N` escrita em docs use o N real de `longterm.FRAGILITY_FLAGS`.

### Correções da revisão em contexto limpo (2026-09-09)

Oito achados, todos corrigidos com teste vermelho antes. Três mudam comportamento e valem
atenção do operador.

1. **A ordem da tabela usava uma métrica quase sempre indisponível.** `sort_key` ranqueava
   por `net_roi_percent`, que só existe com o modelo de custo completo — ausente em 5.975
   das 6.104 linhas do run real. O termo colapsava para zero em todas e a tabela saía em
   ordem de inserção: uma linha de 44% podia aparecer acima de uma de 300%. Agora a
   **margem bruta entra na ordenação**, antes do ROI líquido, lida do mesmo
   `economic_gate` que a tabela exibe.
2. **O "teto de comparação" prometia um preço que o gate rejeita.** Em `gross_margin` o
   teto virava a referência crua, mas o gate exige `preço < referência/1,43`. Com
   referência US$100 a entrega dizia "teto US$100,00" enquanto US$70 já sai REJEITAR.
   O teto passa a ser o maior preço que o modo aprova, arredondado para BAIXO ao centavo.
3. **`estoque-alto` contava três vezes a mesma observação.** Ela, `psa10-iliquido` e
   `concentracao` leem os mesmos dois números. Somadas cheias, uma leitura virava 60
   pontos e jogava a linha para LP4 com a evidência que dava LP2. A família passa a ter
   teto de 30, o que a leitura mais forte dela já contribuía sozinha. Não mexe na cobertura.
4. **Meses de estoque dividia anúncios de uma nota pelas vendas de outra.** O
   PriceCharting só dá volume por certificadora na coluna PSA 10; as demais notas caem no
   balde genérico `GRADE 9`, que mistura certificadoras e que este repo proíbe rotular
   como PSA. A flag passa a valer **só em linhas PSA 10**; fora disso é `n/d`.
5. **O piso da LP1 voltou de 9 para 8.** Subir junto com a 11ª flag rebaixava para `LP2*`
   linhas que davam LP1 sem nenhuma evidência nova, e `estoque-alto` é a menos disponível
   das onze. A contagem absoluta foi preservada.
6. **Margem absurda voltou a pedir conferência de identidade.** O gate `gross_margin` só
   tem piso, então uma linha de centenas de por cento — assinatura clássica de referência
   errada ou carta trocada — chegava a APROVAR sem ressalva. A checagem existia no config
   e estava inerte. Ela ganhou corte próprio do modo,
   `economics.suspicious_gross_margin_percent: 150`, porque os 60% do topo foram
   calibrados para o gate antigo e, sob um gate que aprova a partir de 43%, engoliriam
   negócio normal. REVISA, nunca rejeita.
7. **A guarda de drift nova passava por vacuidade e depois quebrava demais.** Foi ancorada
   nas três formas reais em que a contagem aparece.
8. **`--min-gross-margin` era aplicada em modo que a ignora, em silêncio.** Agora o config
   fica intacto e o aviso é impresso, como o repo já faz com `--confiavel`.

Fixtures de `test_catalog_identity` usavam preço com 300% de margem como atalho para
APROVAR; passaram a usar 60%, dentro da faixa normal. Os testes são sobre identidade de
catálogo, não sobre economia.

### A margem bruta passou a ser medida contra a REVENDA, não contra a referência PSA

Achado ao responder "por que 150%?" — e mais grave que a pergunta.

O gate `gross_margin` media a margem contra `comparison_reference`, que para CGC, TAG e
BGS é a **referência PSA ajustada**: um valor que aquele slab nunca alcança. O gate
anterior (`profit_or_discount`) usava `resale['price_exact']`, as vendas da própria
certificadora. Trocar para margem bruta trocou a base em silêncio, só para não PSA.

Concreto, com referência PSA US$1.000: uma CGC 10 vale no máximo 40% disso
(`max_reference_percent`), ou seja US$400. Um anúncio a US$350 dava **186% de margem**
contra a referência PSA e passava folgado num gate de 43%, quando a margem honesta contra
a revenda CGC é **14%** — abaixo do gate. O teto da certificadora barrava o prejuízo
declarado, mas não tornava a margem honesta.

No run real de 2026-09-09, as **7 únicas linhas acima de 100% de margem eram todas CGC 10
GEM**, comparadas contra preços de PSA 10 (item a US$80 contra "referência" US$3.552).
Corrigida a base, seis delas somem.

- A base agora é `resale_evidence.price_exact` sempre. Para PSA nada muda: `resale` É a
  evidência PSA.
- Sem vendas da própria certificadora não há margem honesta a calcular: o gate fica calado
  e **nunca aprova por margem** (fail-closed). A linha já carrega
  `revenda-sem-vendas-da-certificadora`.
- `economic_gate` passa a publicar `margin_base` e `margin_base_source`, para o JSON dizer
  qual número decidiu.
- O teto publicado (`comparison_cap`) passa a ser o **menor** entre o teto da certificadora
  e o teto do gate (revenda ÷ 1,43): as duas regras valem juntas.
- O ramo BGS gravava `comparison_cap` sem o par `_exact`; corrigido.

**O que a medição diz sobre o corte de 150%.** Com a base corrigida, sobre 129 linhas com
revenda e preço: a mediana fica em −20% (o anúncio típico custa MAIS que a revenda), o
p99 é 50%, e existe **uma** linha acima disso, a 1793%. Qualquer corte entre 51% e 1793%
pega exatamente a mesma linha. Os 60% originais ficariam a 10 pontos do teto real
observado e passariam a marcar negócio legítimo. Continua sendo calibração sobre um run,
não backtest.

### Limitações que continuam de pé

Nada aqui foi validado contra o mercado: um snapshot não é backtest. Não existe dado de
população PSA no scanner, então escassez real (pop por nota, taxa gem, velocidade da população)
segue fora da régua — é o próximo passo e exige um coletor novo. Meses de estoque é o
substituto barato e parcial, não o completo.


## 2026-09-09 — coluna informativa "Longo prazo" (PR-C `feat/longterm-risk-benefit`)

Nova coluna na tabela de entrega dos DOIS geradores (`src/slab_report.render`, vigente, e a
tabela legada de `src/report.py`), posicionada logo antes de `Links`. Ela descreve a CARTA e a
QUALIDADE DO DADO que sustenta aquela linha — e só isso.

**O que ela NÃO é** (invariante desta rodada): não é gate (filtro obrigatório que decide se um
anúncio entra na tabela), não é veredito, não é ranking (a ordem em que as linhas saem) e não é
recomendação de compra. O veredito e a ordem continuam vindo só da política `slab_strategy`
(chaves `slab_strategy.economics.gate_mode`, `.min_profit_usd`, `.min_discount_percent`,
`.require_positive_profit` e `slab_strategy.evidence.*`), que NÃO foi tocada: `src/slab_strategy.py`
e o bloco `slab_strategy` do `config.yaml` têm diff vazio contra a `main`. A cesta de vendas que
alimenta a referência também não muda: a coluna só LÊ a referência e a cesta já montadas
(`ref_*`, `psa_evidence`, `refs.sales_history`) e nunca cria uma segunda referência. Os motivos
`LP:` aparecem só na coluna `Flags` (tabela legada) ou na linha "Motivos:" da seção por carta
(política); nunca entram em `risk_flags` nem em `reasons`, que são o que alimenta veredito e score.

- **Como a célula é lida.** `LP2 64/35 (4/5·8/10)` = classe · PERFIL/FRAGILIDADE DO DADO ·
  (cobertura do perfil · cobertura da fragilidade). O cabeçalho da entrega ganha a contagem por
  classe (`LP2*` conta como LP2) e o rodapé ganha a legenda única dos dois geradores
  (`report.LONGTERM_LEGEND`).
- **PERFIL (0-100)** = média dos pontos dos componentes QUE TÊM DADO, em cinco eixos, todos lidos
  de sinal que o run já tinha (custo zero: nenhuma consulta nova à rede). B1 personagem
  (`pokemon_rank` da watchlist, a lista dos 100 "chases" — as cartas mais procuradas; o `score` de
  `src/catalog/iconic_pokemon.csv` entra só como sinal de proveniência). B2 raridade (texto cru
  `rarity` do tcgcsv, classificado por faixa). B3 supply (anos desde o `year` da watchlist, com
  teto quando o nome do set indica reimpressão forte — reimpressão que aumenta a oferta). B4 faixa
  de preço da COLUNA PSA 10 do PriceCharting (só informação: nunca é a referência nem o preço do
  anúncio). B5 tendência real de 12 meses.
- **B5 (tendência) tem duas fontes, nesta ordem.** Primeiro a mediana (valor do meio) das vendas
  da nota DO ANÚNCIO em 0-180 dias contra 180-365 dias, só com ao menos três vendas em cada
  janela (`refs.sales_history`, só leitura). Essa cesta é a MESMA da referência apenas no caminho
  LEGADO; no caminho da POLÍTICA (vigente) ela é uma cesta PRÓPRIA e mais frouxa — a referência da
  política (`slab_strategy.reference_sales`) usa a nota PSA-equivalente e ainda exige venda de
  fonte eBay, id de venda numérico e único, idioma da carta e nada de lote/"best offer"/
  certificação incerta, filtros que a cesta da tendência não aplica. Por isso o sinal
  `trend_source` vale `sales_history` no legado e `sales_history:cesta-propria` na política: B5
  pode se apoiar em vendas que a política descartou da referência, e o rótulo diz isso em vez de
  prometer "a mesma cesta". Nada disso muda a referência, o veredito nem o ranking — B5 só entra
  no PERFIL, que é informativo. Se não houver, a série
  mensal do PriceCharting (`VGPC.chart_data`, leitura nova em `src/pricecharting.py`), bucket
  PSA 10 — anúncio de outra nota recebe o rótulo `chart_data:psa10-proxy` no sinal `trend_source`,
  porque a série PSA 10 não é a série daquela nota. Na série, zero significa "sem dado", nunca
  preço zero.
- **FRAGILIDADE DO DADO (0-100)** = soma de dez sinais de fragilidade, com teto 100: `ref-fragil`
  (poucas vendas sustentando a referência, pela mesma régua de `pc_sales.sales_reference`),
  `psa10-iliquido` (vendas por mês da coluna PSA 10), `ref-desalinhada`, `reprint-forte`,
  `preco-absoluto-alto`, `vendedor-fraco` (os MESMOS cortes `trusted_min_feedback` e
  `trusted_min_feedback_pct` do config que a política já usa), `tiragem` (variante de impressão
  ambígua), `dispersao` (o MESMO valor que já rebaixa uma linha para REVISAR, pelo corte
  `slab_strategy.evidence.max_dispersion_percent` — uma definição, um nome: a célula mostra o
  valor arredondado, mas a comparação com o corte usa o valor EXATO `dispersion_exact`, o mesmo
  que a política compara, senão os dois discordariam na fronteira; a coluna olha a cesta PSA,
  enquanto a política checa dispersão também na cesta de `revenda`), `ref-stale` e
  `concentracao` (mesma carta e mesma nota com muitos anúncios no run, corte
  `longterm.concentration_min_listings`, contado ANTES do loop de avaliação e aplicado também às
  primeiras linhas daquela carta+nota).
- **Classe LP1-LP4** = faixa de qualidade/completude do perfil (forte / médio / fraco / frágil),
  pelos limites do bloco `longterm:` do `config.yaml`. Não ordena a tabela e não é nota de compra.
  O asterisco (`LP2*`) marca "seria LP1, mas faltou dado": um dos três insumos-chave da
  fragilidade (`ref-fragil`, `psa10-iliquido`, `ref-desalinhada`) estava em `n/d`, ou a
  cobertura da fragilidade ficou abaixo de 8 das 10 flags (`LP1_MIN_FRAGILITY_COVERAGE`, a
  mesma proporção de 80% do piso que o PERFIL já tinha). Esse piso existe porque a FRAGILIDADE é
  uma SOMA: sem ele, uma linha em que 7 dos 10 testes nem puderam rodar sairia com nota 0 e
  classe "forte" — a mesma de uma linha com os 10 testes rodados e limpos.
- **`n/d` nunca vira zero — e como ler a FRAGILIDADE.** No PERFIL, que é uma MÉDIA, o componente
  sem dado sai mesmo da conta e reduz a cobertura. Na FRAGILIDADE, que é uma SOMA, sair da soma é
  aritmeticamente o mesmo que valer zero; por isso a leitura honesta da nota é "problemas
  DETECTADOS entre os testes que puderam rodar", e não "fragilidade estimada" — `0 (3/10)`
  significa "só 3 dos 10 testes rodaram e nenhum acusou problema". A cobertura ao lado da nota é
  parte da leitura, e o piso de cobertura da classe LP1 impede que dado ausente vire dado limpo.
  Abaixo de `longterm.min_profile_sources` /
  `longterm.min_fragility_sources` a nota inteira fica `n/d`, e a classe também. Cada ausência sai
  escrita como `LP:<nome>: n/d` nos motivos — nada some em silêncio.
- **O que fica `n/d` em cada caminho, e por quê.** No caminho da POLÍTICA (vigente):
  `ref-desalinhada` fica `n/d` porque a política deixa `asks = {}` (decisão documentada do
  operador) e nada é recomputado só para uma flag informativa; `ref-stale` fica `n/d` porque
  nesse caminho não há cross-check com o market de carta solta do TCGplayer. Consequência
  declarada: nesta rodada o teto da classe no caminho da política é `LP2*`. No caminho LEGADO,
  `ref-desalinhada` reaproveita a flag existente `REF DESALINHADA`, `ref-stale` só existe quando
  há market TCG para conferir, e a `dispersao` é calculada pela MESMA fórmula sobre a cesta já
  lida. Nos dois caminhos, insumo ausente na fonte (sem `pokemon_rank`, sem `rarity`, sem `year`,
  sem coluna PSA 10, sem série mensal e sem vendas suficientes) vira `n/d` naquele componente.
- **Erro interno na coluna nunca derruba a linha nem a carta**: a coluna fica `n/d`, o erro é
  logado e contado no funil com rótulo humano (`longterm_error`). `longterm.assess` é função pura
  (não altera a `Opportunity` nem a referência) e `longterm.annotate` grava só os campos novos
  `longterm_*` / `trend_*`.
- **Configuração**: bloco novo `longterm:` no `config.yaml`, dez chaves inteiras (`enabled`,
  limites das classes, coberturas mínimas e `concentration_min_listings`). Nenhuma chave já
  existente foi alterada. `longterm.enabled: false` desliga a coluna (todas as linhas ficam
  `n/d`) sem mexer em mais nada.
- **Calibração inicial, NÃO validada** (`longterm.CALIBRATION_NOTE`): os pontos por componente,
  as bandas e os limiares nunca foram medidos contra o mercado real — não há backtest (teste
  contra o passado) e existe um único snapshot. É triagem descritiva, não previsão de preço;
  "valorização" (subida de preço ao longo do tempo) não é medida aqui. Por isso os pontos ficam
  no código, e não no config: mexer neles é recalibrar, não configurar.
- **Validação transversal** (`longterm_validate.py`, ferramenta separada que roda sobre o JSON de
  um scan, sem rede): agrega por chave (carta, número, nota) ANTES de qualquer estatística —
  vários anúncios do mesmo item contam como um, para não inflar o resultado por pseudo-replicação
  (contar o mesmo item várias vezes) —, exige um número mínimo de chaves (`--min-keys`) e calcula
  Spearman (correlação de postos: compara a ORDEM dos itens, não o valor) de B1, B2, B3, B5 e do
  PERFIL-sem-B4 contra o valor de referência e contra o prêmio de nota. B4 fica DE FORA das
  correlações por circularidade: é derivado de preço, e correlacionar preço com preço não prova
  nada. Abaixo do mínimo a ferramenta escreve "n insuficiente" e não inventa correlação. O
  snapshot em CSV é local, sob `results/` (fora do GitHub por `DELIVERY_CHAT.md`).
- Régua completa, tabela por tabela, em [`docs/LONGO_PRAZO.md`](docs/LONGO_PRAZO.md).

### Correções da revisão do PR-C (mesma data, dois revisores independentes)

Nenhuma delas muda veredito, gate, ranking ou preço de referência — todas ficam dentro da coluna
informativa e da sua documentação. `src/slab_strategy.py` continua com diff vazio contra a `main`
e o bloco `slab_strategy` do `config.yaml` também. Cada correção nasceu de um teste que falhava
antes dela (arquivo `tests/test_longterm.py`, seção "revisão do PR-C").

1. **`LP:concentracao` contava anúncios de OUTRAS cartas.** A contagem feita antes do laço somava
   tudo que a busca do eBay devolveu; uma busca com 1 Charizard e 3 anúncios de outras cartas
   imprimia "4 anúncios da mesma carta+nota" onde havia 1, e somava +10 na fragilidade. Agora usa
   a mesma guarda de identidade que a função irmã `_clean_ask_prices` já tinha.
2. **Rótulo honesto da cesta que alimenta a tendência (B5).** Quatro textos afirmavam que B5 lê "a
   mesma cesta da referência"; no caminho da política ela lê uma cesta própria e mais frouxa, e
   pode se apoiar em vendas que a política descartou. O sinal passa a sair como
   `sales_history:cesta-propria` nesse caminho, e os quatro textos foram corrigidos.
3. **Dado ausente não pode virar "dado impecável".** Novo piso `LP1_MIN_FRAGILITY_COVERAGE` (8 de
   10, a mesma proporção do piso que o PERFIL já tinha): abaixo dele a classe não chega a LP1 e
   vira `LP2*`. A leitura da FRAGILIDADE foi corrigida na documentação (é soma, mede problemas
   detectados entre os testes que rodaram).
4. **Zero venda comparável não é `thin`.** Ganhou rótulo próprio `sem-vendas`, com os mesmos
   pontos: "poucas vendas" onde não há venda nenhuma era falso.
5. **`LP:dispersao` agora compara o valor EXATO** (`dispersion_exact`), o mesmo que a política
   compara — antes discordavam na fronteira (dispersão real de 30,004% rebaixava a linha e a
   coluna dizia que estava sob controle).
6. **Célula da classe `n/d`** saía grudada (`n/d n/d/40 (2/5·8/10)`); agora sai `n/d (2/5·8/10)`.
7. **Série mensal com timestamp repetido** derrubava a coluna para `n/d` por erro interno
   (`TypeError`); agora a série é ordenada só pelo timestamp. Correção defensiva: o crash está
   provado, a ocorrência numa página real não.
8. **Coerência entre os três geradores.** A coluna passou a aparecer também no balde REJEITADO da
   entrega legada (cujo cabeçalho já contava aquelas linhas) e a legenda passou a sair também no
   console legado (`report.to_markdown`), que já tinha a coluna.
9. **Coluna `Flags` da tabela legada** só concatena os motivos `LP:` que dispararam; as ausências
   (até 15 por linha) seguem no JSON e resumidas na cobertura, em vez de empurrar para longe o
   sinal de risco real numa tabela colada verbatim no chat.

## 2026-09-09 — auditoria do sistema de honestidade de preço (PR-B `fix/honestidade-fase1`, depende do PR-A #32)

Revisão de TODO caminho que leva um número até a tabela do operador, nos dois motores
(política `slab_strategy` 2026-09-05.4 = vigente; `scorer` = legado, só testes/artefatos
antigos) e em todos os baldes (APROVAR/REVISAR/REJEITAR + funil; SUSPEITO só no legado).
Teto de 5 correções; nada muda em `src/slab_strategy.py` nem no bloco `slab_strategy` do
`config.yaml` (achados lá viram pergunta ao operador, sem código); a cesta de vendas que
alimenta a referência não muda. Cada correção nasceu de um teste vermelho (que falha antes
do código) e foi conferida por mutation-check (desfazer a correção faz o teste falhar).

- Rótulo enganoso (classe iii): a coluna "Grade 9" do PriceCharting é um bucket GENÉRICO
  (mistura certificadoras: PSA, BGS, CGC…) e `src/pricecharting.py` a chamava de "PSA 9" —
  o nome errado chegava ao operador em `--pricing-only` e em runs sem linha
  (`report.fair_value_markdown`). Agora a chave é `GRADE 9`, a mesma que `src/pc_sales.py`
  já usava para a mesma coluna; o campo `Opportunity.spread_psa9_pct` (legado, só raw)
  virou `spread_grade9_pct`. Nenhuma referência de preço muda: essa coluna nunca foi
  referência (só informação).
- Ponto cego de documentação (classe iii): a skill `.claude/skills/scan-ebay/SKILL.md`, a
  docstring e o `--help` do `main.py` e a docstring do `ebay_summary.py` ainda ofereciam o
  "modo diagnóstico" com carta solta e piso 5 (`--min-price 5 --include-raw`, rejeitado desde a política
  2026-09-05.4), o gate `min_discount_percent: 20` (histórico pré-#29; o config diz 30) e a
  entrega em 4 baldes do motor legado (OPORTUNIDADE/SUSPEITO). Reescritos para a política
  vigente, descrita por chave de config (`slab_strategy.economics`: `gate_mode:
  profit_or_discount`, `min_profit_usd`, `min_discount_percent: 30`; `graded_only: true`;
  link para docs/EBAY_PSA.md), com o gerador vigente (`src/slab_report.render`) e
  `--sensitivity` declarado como só-legado. `main.py` deixa de passar `include_raw` (flag
  rejeitada) ao artefato. `tests/test_docs_drift.py` fixa que a skill só usa flags que a
  CLI aceita e não reoferece o modo removido.
- Sinal descartado (classe iv): `ebay_summary.py --sensitivity` num JSON da política era aceito
  e ignorado em silêncio — a tabela saía sem as faixas e sem aviso, e o operador podia achar que
  as faixas tinham sido aplicadas. Agora a entrega ganha um aviso explícito no topo ("ignorado:
  as faixas só existem para JSON do motor legado") e a tabela segue idêntica; nada muda na
  política nem nos vereditos.
- Rótulo enganoso (classe iii) e "nada some em silêncio" (invariante do funil): a entrega da
  política (`src/slab_report.render`) imprimia o funil como JSON cru (chaves internas, sem os
  rótulos humanos de `FUNNEL_LABELS`), e os rótulos dos baldes eram os do motor legado —
  `scorer.VERDICT_STAT` manda APROVAR para `rows_opportunity` e REJEITAR para `rows_rejected`,
  então o console do `main.py` dizia "Linhas OPORTUNIDADE" para linhas APROVAR. Agora existem
  `report.POLICY_FUNNEL_LABELS` / `policy_funnel_lines` (APROVAR / REVISAR / REJEITAR), usados
  pelo `render` e pelo console quando a política está ativa; contador sem rótulo continua saindo
  em "outros: …" e o JSON legado mantém os rótulos antigos.
- Ponto cego na entrega (classe iii; DELIVERY_CHAT.md pede horário da coleta e regra
  identificados): a tabela da política não dizia QUANDO, O QUE nem COM QUAL REGRA foi coletado.
  `src/slab_report.render` ganha a linha "Coleta:", lida só de `meta` do JSON (data/hora UTC,
  grupo, cartas da watchlist, versão da política e chaves `gate_mode` / `min_profit_usd` /
  `min_discount_percent`, `min_price_usd`, `max_pages`, chamadas à Browse API usadas e
  `max_ebay_calls`; ausente = n/d, nunca inventado), e o aviso de execução abortada passa a
  dizer a causa (parada antecipada = cartas restantes não varridas × todas as cartas visitadas
  com erros contados no funil).

Correções da revisão do PR #33 (dois pareceres independentes, veredito "corrigir"; nada muda
em `src/slab_strategy.py`, `config.yaml`, veredito, gate, cesta ou ranking):

- Console do `main.py` com a política ativa imprimia o relatório SEM os metadados do JSON:
  "Coleta:" toda n/d e funil "analisados: 0" (zero inventado a partir de um dict vazio).
  O artefato JSON é montado antes de imprimir e o console usa o MESMO `meta` da entrega;
  sem meta/funil o relatório diz n/d.
- Três contadores que só o caminho da política produz (`item_details_fetched`,
  `item_details_error`, `ebay_budget_exhausted`) não tinham rótulo e saíam como chave crua em
  "outros:"; ganharam rótulo humano, e um teste varre `src/scanner.py`/`src/scorer.py` para
  garantir que todo contador incrementado tem rótulo.
- A linha "Coleta:" declara `--grades` (notas do run) e `--confiavel`; com a política ativa o
  `main.py` avisa que `--confiavel` não tem efeito (a política nunca lê `trusted_mode`);
  as chaves do gate seguem o `gate_mode` (em `all_minima` valem `min_net_margin_percent`,
  `min_net_roi_percent` e o `min_discount_percent` de topo); data/hora lida com
  `datetime.fromisoformat` (sem fuso = dito; ilegível = n/d).
- Texto operacional: `--sensitivity` no `--help` do `ebay_summary.py` marcado como só-legado;
  `--pricing-only` e o cabeçalho impresso deixam de chamar coluna de "referência"; a skill
  separa o destino de cada erro por carta (PriceCharting fora do ar = linhas em REVISAR;
  `card_error`/`ebay_error` = carta pulada sem linhas; todos = run parcial) e cita as 12
  colunas do `render`; docstrings de `src/report.py`/`src/models.py` descrevem os dois
  caminhos (política = vigente); constante morta `ACCEPTED_GRADES` removida.

## 2026-09-09 — porte do diff local pré-#29 sobre #31 (PR-A `fix/port-local-diff`)

- Resgate: o trabalho local não commitado (13 arquivos + `tests/test_slabs_regressions.py`)
  foi congelado na branch `wip/local-slabs-diff-2026-09-04` (cópia de segurança; não
  mergear) e portado aqui por hunk (trecho de diff), nunca por arquivo inteiro.
- Identidade da venda usada na referência (caminho legado): `pc_sales.comparable_sales(...,
  card=)` descarta, antes da mediana (valor do meio), venda cujo título CONTRADIZ a
  carta (`title_parser.sale_contradicts_card`: outro nome, prefixo/sufixo que muda a
  carta — "Dark Charizard", "Charizard ex" —, palavra de exclusão, fração ou "#N" com
  outro número). A AUSÊNCIA de número no título não exclui (a venda está na página da
  própria carta): no fixture real da Charizard 4/102 as cestas PSA 9 / PSA 10 / BGS 9.5 /
  CGC 9 ficam iguais às de antes e só as 2 vendas de outra carta (#39/#40 de 165) saem.
  `CardRefs.slab` e `graded_reference` passam a carta; preço não finito (NaN/infinito)
  também fica fora. O matcher de NOTA da cesta (`_grade_mentions` + `_CGC_PRISTINE_RE`)
  é o de antes: nesta rodada a cesta só muda por identidade (review do PR #32 — a troca
  pelo parser dos anúncios movia referências no fixture e foi revertida; unificar os dois
  matchers, com a evidência, é decisão do operador para o PR-B). Raw LP (`lp_sales`,
  `CardRefs.lp`) NÃO recebe guarda de identidade nem checagem de preço finito — caminho
  morto (`--include-raw` rejeitado), declarado aqui e não coberto.
  **Pergunta ao operador:** manter "só contradição" (cesta igual à de antes) ou exigir o
  número no título da venda, como a política já faz (fail-closed, cesta menor)?
  **Ressalva:** a guarda cobre SÓ o caminho legado — `src/slab_strategy.py` monta a
  própria cesta de vendas e não chama `comparable_sales` (0 ocorrências); replicar a
  guarda lá é pergunta ao operador (backlog), nada foi tocado nesse módulo.
- Parser de nota compartilhado (`grading.grade_from_title`, usado nos DOIS caminhos):
  CGC "Pristine" ANTES da sigla ("Pristine CGC 10") é CGC 10 PRISTINE. Efeito na
  política também: o anúncio "Pristine CGC 10" deixa de ser classificado CGC 10 GEM, e
  em `slab_strategy.reference_sales` uma venda assim sai da cesta de revenda CGC 10 GEM
  e entra na PRISTINE (teste `test_policy_resale_basket_reads_pristine_before_the_grader`
  fixa isso; o módulo `slab_strategy` não foi tocado).
- Identidade do anúncio (`title_parser.card_matches_title`, função usada nos dois
  caminhos): nome como palavra inteira ("Mew" não casa "Mewtwo"); prefixo/sufixo que
  mudam a carta ("Dark Charizard", "Charizard ex") não casam; número completo com
  denominador quando a watchlist o traz. A chamada com nome vazio (é como
  `slab_strategy.identity_matches` a usa) confere só número e exclusões, mas a leitura
  do NÚMERO mudou nos DOIS caminhos (declarado após o review do PR #32): "pop/cert/qty +
  número" nunca conta como número da carta ("pop 12" não identifica a carta 12 —
  `identity_matches` também); código de série + número ("SM12", "SWSH 45") é o set, não
  a carta, exceto quando vem uma fração logo depois ("SM 150/147") ou quando o número
  esperado tem esse prefixo (promo "SM211"); número alfanumérico com zero à esquerda
  casa com e sem o zero ("H02" = "H2", "TG03" = "TG3", "SV049" = "SV49" — regressão do
  review: 32 cartas da watchlist deixavam de casar).
- Funil da coleta nos DOIS caminhos (contagem de por que cada anúncio foi descartado):
  `fetched` (recebidos da API antes de qualquer filtro), `skip_invalid_payload` (item com
  estrutura ilegível), `skip_fetch_error` (páginas já concluídas descartadas quando a busca
  estoura no meio) e `skip_evaluation_error` (erro interno ao avaliar UM anúncio, que não
  derruba a carta inteira e marca o run como parcial, como já fazia `card_error`).
  `invalid_reference` (referência ausente/NaN/infinita/≤0) e `below_discount` só existem
  no caminho legado; a política (`slab_strategy`) rejeita com motivos próprios.
- Fase de detalhes da política (`get_item`, review do PR #32): payload de detalhe
  ilegível não derruba mais a carta — o anúncio segue com os dados da busca, marcado
  `detalhes-do-anuncio-ilegiveis` (REVISAR) e contado em `item_details_error`. Cota ou
  autenticação estourando NO MEIO da carta: as linhas já avaliadas que se perdem contam em
  `rows_lost_abort` (não em `rows_*`, que só contam linhas que chegam ao artefato) e os
  anúncios não avaliados em `skip_details_abort` — `seen` volta a ser a soma dos baldes.
- Preço do anúncio AUSENTE (`None`) conta em `skip_no_price` ("sem preço legível");
  NaN/infinito/≤0 contam em `skip_price_floor` (caminho legado). A mediana dos preços
  pedidos (`_clean_ask_prices`, legado) ignora esses anúncios em vez de derrubar a carta.
  `report.sort_key` tolera rank infinito (OverflowError = número grande demais); rótulo do
  funil `skip_raw` diz "escopo exclusivo de slabs" (o texto antigo sugeria `--include-raw`,
  que a base atual rejeita).
- Run parcial com a CAUSA na mensagem: `stopped_early` marca parada antecipada
  (autenticação, cota, erros seguidos da API — "cartas restantes NÃO foram varridas");
  sem ele, o console e o cabeçalho do `ebay_summary` dizem "todas as cartas foram
  visitadas, mas houve erros contados no funil". A entrega da política
  (`slab_report.render`) segue imprimindo o funil como JSON cru — rótulos humanos novos
  não chegam lá (fora desta rodada).
- Gate em Decimal (aritmética exata) **não portado**: o gate vigente compara o Desconto%
  já arredondado a 2 casas (`report.compute_metrics`); com centavos reais um caso de
  fronteira mudaria de lado (29,996% é admitido hoje como 30,00% e seria rejeitado em
  aritmética exata). Freio (f)7 do prompt: pergunta ao operador; teste de fronteira em
  `tests/test_slabs_regressions.py`. Limiar 30/30 e bloco `slab_strategy` do config
  intactos (diff vazio).
- Bloco "somente slabs" do diff local descartado (`scan_config`, `parse_grades_arg`
  rejeitando RAW, `GRADED_CONDITION_ID`, README/config): já coberto pela política
  2026-09-05.4 com outro mecanismo (`slab_strategy`, `conditionIds:{2750}`, `--include-raw`
  rejeitado no CLI) — ver `docs/EBAY_PSA.md` e a seção 2026-09-05 abaixo. Das 17 funções
  de teste do arquivo local, 3 (bloco 1) e 2 (Decimal) não foram portadas; 12
  sobreviveram adaptadas à base #31 (preço ilegível vira `price=None`, não descarte na
  coleta) + 4 testes novos (nome vazio, preço `None`, fronteira do gate, run parcial).
- Correções órfãs do PR #27 (sem entrada própria até aqui): reverse holo sem market do
  subtipo conta como `raw_variant_no_reference`; jumbo/metal/oversize saem do funil como
  outro produto; em "11/25" o denominador nunca é lido como número da carta.
- PR #26 já contido na `main` (cherry-pick vazio; patch aplica ao contrário limpo) e
  PR #28 superado por #29 (regressão do catálogo já na `main`): comentados com
  evidência, sem fechar (decisão do operador). Cópia do `/auto` do eBay já em sincronia.
- 735 testes locais (682 no PR original + 53 da rodada de review). Em
  `tests/test_slabs_regressions.py`, 9 testes nascem verdes contra a `main` (guarda de
  comportamento vigente, não prova de correção): `test_card_identity_with_empty_name_...`,
  `test_pricecharting_breaker_opens_on_fifth_consecutive_failure`,
  `test_discount_gate_boundary_at_30_percent` ×3,
  `test_discount_gate_compares_rounded_percent_today` ×2,
  `test_invalid_listing_price_never_emits_row[-1|0]`; idem
  `test_policy_resale_basket_reads_pristine_before_the_grader` (fixa o efeito do hunk
  Pristine na política).
- **Pergunta ao operador (política, sem código):** `slab_strategy.reference_sales` lê a
  nota da venda só por `grading.grade_from_title`; "Black Label" ANTES da sigla
  ("Charizard Black Label BGS 10") vira BGS 10 comum e entra na cesta de revenda do BGS 10
  regular (o legado cobre via `_is_black_label_sale`). Opções: (a) reconhecer "black label"
  antes da sigla em `grading._grade_from_match` (mesmo desenho do hunk Pristine; efeito
  declarado nos dois caminhos + teste) ou (b) backlog. Conservador = (b).

## 2026-09-05 — revisão de execução, política 2026-09-05.4

- Corrigida identidade de coleções com códigos de catálogo e grafias com apóstrofos/LV.X.
- Mantidas as separações por número, subconjunto, variante, idioma e nota.
- Separado estado de execução do estado de evidência; parâmetros operacionais no JSON.
- Validação manual parametrizada por grupo/nota/amostra, sem rotina recorrente.
- CSV de execução parcial preserva o último completo; aviso abre o relatório.
- 646 testes locais; validação real com sucesso: 188 anúncios, 83 referências
  suficientes e nenhuma aprovação artificial (lucro não positivo).
- Outra amostra moderna: 29 anúncios, 24 referências suficientes. Auditoria
  independente dos 107 cálculos reais: zero divergências. Grupo antigo mantém
  resultado parcial por dados insuficientes, sem erro de fonte.
- Nomes oficiais com Collection não são lotes; lotes pequenos (x2, set of 2,
  2 cards) e quantidades maiores continuam excluídos de anúncios e comparáveis.
- Diagnóstico e evidências em `docs/RUNTIME_REVIEW.md`.

## 2026-09-05 — autonomia delegada, política 2026-09-05.3

- Dispersão máxima 30%; BGS 9,5 sem acumular os dois acréscimos de 5%.
- Configuração completa, com escolhas do agente e autorização registradas.
- Teto de 500 chamadas eBay por execução, inclusive detalhes e retentativas;
  esgotamento interrompe com resultado parcial e preserva cartas já concluídas.
- 620 testes locais passaram. Amostra ampliada PSA 9: 115 anúncios, 104 REVISAR,
  11 REJEITAR e zero APROVAR. Duas vendas estritas sustentam o cálculo de nove
  anúncios, mas não atendem ao mínimo de três. Validação de evidência parcial.

## 2026-09-05 — revisão consolidada, política 2026-09-05.2

- Regra econômica: lucro líquido estimado >US$40 OU desconto >30%, com lucro
  positivo, custos completos e limites independentes por certificadora.
- CGC até 40% da PSA; US$10 cobrem envio/impostos até COMC uma única vez.
- Elite US$2,50, saque informado 10%, venda 5%, projeção de armazenamento e
  segurança por 120 dias (prazo informado de 90–120 dias).
- Comparações Decimal, identidade e idiomas mais estritos, diagnósticos de
  exclusão, configuração validada e gravação atômica dos resultados.
- Busca apenas Graded e consulta limitada de atributos getItem; a validação
  usa idioma e ano do catálogo para reduzir reimpressões na amostra.
- 612 testes locais e remotos passaram. Busca real final: 13 anúncios, 8 chamadas,
  13 REVISAR e zero APROVAR; evidência PSA insuficiente, resultado parcial.
- Dispersão máxima e combinação BGS 9,5 continuam pendentes. Sem novo agendamento.
  Evidências completas em `docs/VALIDATION_EBAY_PSA.md`.

## Histórico anterior — ligar validação aos secrets existentes

- Workflow de validação pontual no GitHub usa EBAY_CLIENT_ID/SECRET apenas
  na etapa de busca; nenhum valor é copiado para a conversa.
- Limite de uma carta/uma página; relatório em artefato, sem agendamento.
- Distingue sucesso técnico, falta de comparáveis e falhas de fonte/autenticação.
- Sete regressões novas para isolamento dos secrets e estados da validação.

# EBAY PSA — 2026-09-05 (proposto em PR)

- Nova política versionada de slabs: PSA como referência, BGS +5%, nota 9,5
  como PSA 9 +5%, TAG 10 equivalente na comparação e CGC indefinido em REVISAR.
- Referência PSA separada de revenda da certificadora, custos Decimal,
  investimento/lucro/margem/ROI e US$10 sem cobrança duplicada de frete.
- Identidade das vendas e idiomas explícitos; datas, links, amostra e dispersão
  no JSON e relatório. Sem referência permanece visível como REVISAR.
- Três decisões APROVAR/REJEITAR/REVISAR. CLI raw rejeitada; ausência de
  credenciais encerra com código 1 sem sobrescrever resultados.
- Configuração e instruções antigas reconciliadas com o projeto EBAY PSA.
- Dependência do catálogo do PR #28 incorporada (`07f11a8`); não há merge.
- 541 testes locais passaram (46 novos de estratégia + regressão de catálogo).
  Busca real bloqueada por credenciais ausentes; ver docs/VALIDATION_EBAY_PSA.md.

# Changelog

Todas as mudanças relevantes deste repo. Formato inspirado em
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões seguem
[SemVer](https://semver.org/lang/pt-BR/). Não há string de versão no código —
a versão vive aqui e no `main` mergeado.

Linguagem acessível (regra do operador): termo técnico vem com explicação
curta. "Slab" = carta lacrada com nota por uma certificadora; "raw" = carta
solta; "mediana" = valor do meio de uma lista ordenada; "gate" = filtro que
decide se o anúncio vira linha; "funil" = contagem de para onde foi cada
anúncio; "Browse API" = a API oficial de busca do eBay.

## 0.5.1 — 2026-09-03

PR B (decisão do operador, 2026-09-03): a watchlist deixa de ser feita à mão e
passa a ser GERADA do catálogo e VERSIONADA; o scan roda por grupo canônico
(os mesmos 12 grupos da COMC). 494 testes offline (17 arquivos).

### Adicionado

- `build_watchlist.py`: gera `watchlist.yaml` de forma reproduzível.
  Universo = catálogo de **123 sets** (`src/catalog/set_catalog.json`, nomes
  do tcgcsv) nos **mesmos 12 grupos da COMC** × **100 "chases"**
  (`src/catalog/iconic_pokemon.csv` — Pokémon mais cobiçados, com `rank` de
  popularidade) × **raridade ≥ Holo Rare** (campo `Rarity` do tcgcsv; lista
  `RARITY_ALLOW` — Rare não-holo, Common/Uncommon e Code Card ficam fora) ×
  **teto `--cap 30`** cartas por set (as mais caras pelo market do TCGplayer).
  `pc_url` (página da carta no PriceCharting) resolvida por nome+número+set
  com o **mesmo matcher exato** do scan (`pc_sales.product_page_url`); carta
  sem página **não entra** e sai no relatório (`sem PC: …`) — nunca se inventa
  URL; 5 erros seguidos do PriceCharting abrem o breaker. Flags `--groups
  all|3|5-8|1,3,10-12`, `--cap`, `--out`, `--no-pc`, `--pc-cache-dir`.
  Relatório final: total, por grupo, sem página PC, erros PC, sets no teto,
  sets sem grupo no tcgcsv. Medido pelo operador: **~1.600 cartas**.
- `src/groups.py` (portado de `scanner-comc/comc_scanner/groups.py` @
  dd952ba): `SCAN_GROUPS` com os 12 grupos canônicos (número, título, era,
  sets verbatim do catálogo — 1–2 SV 2023–25; 3–4 WotC 1999–2003; 5–10 EX/DP/
  Platinum/HGSS/BW/XY/SM 2004–19; 11–12 SWSH + Crown Zenith 2020–23),
  `parse_group_arg` (`N` | `N-M` | `1,3,10-12` | `all`; grupo fora de 1–12
  erra alto), `is_group_spec`, `describe_groups`, `catalog`, `set_group`.
- `src/catalog/set_catalog.json` (123 sets com ano) e
  `src/catalog/iconic_pokemon.csv` (100 chases com rank).
- `main.py --group` aceita a spec numérica dos grupos canônicos (`3`, `5-8`,
  `1,3,10-12`, `all`) além do nome literal do campo `group:`
  (`scanner.filter_group`); `--list-groups` mostra o título de cada grupo
  canônico ao lado da contagem.
- `tests/test_groups.py`: **invariante** — a união dos 12 grupos é EXATAMENTE
  o catálogo (123 sets), sem sobreposição; catálogo novo faz o teste falhar de
  propósito (lembrete de atualizar grupos + regenerar a watchlist + skill).
  `tests/test_build_watchlist.py`: geração da watchlist a partir do catálogo.
- Diagnóstico do operador (padrão COMC) documentado: um grupo por vez —
  `python main.py --group <N> --min-price 5 --min-discount 10 --include-raw
  --out results/last_scan_g<N>.json` (cota da Browse API 5.000/dia, ~1–3
  chamadas por carta) → `python ebay_summary.py results/last_scan_g<N>.json -o
  results/ebay-g<N>-<data>.md --sensitivity 10,15,20`, entrega verbatim.
  Comercial: `--min-discount 20`.

### Mudado

- `watchlist.yaml` passa a ser **VERSIONADA** (saiu do `.gitignore`): um clone
  limpo já roda. Não editar à mão (o cabeçalho gerado avisa); regenerar só
  quando catálogo, grupos ou chases mudarem. Campo `group` = número canônico
  1–12; `pokemon`/`pokemon_rank`/`rarity`/`year` vêm do catálogo.
- `watchlist.example.yaml` vira modelo apenas para lista alternativa feita à
  mão (`--watchlist <arquivo>`).
- Documentação (`CLAUDE.md`, `README.md`, skill `scan-ebay`) atualizada: setup
  sem watchlist manual, tabela dos 12 grupos, run por grupo com artefato
  `results/last_scan_g<N>.json`.

### Corrigido

Fixes do PR #24 (review Codex, 2026-09-03) já em `main` e ainda não
registrados no 0.5.0:

- 401/403 **na busca** da Browse API (não só no token) aborta o run
  (`EbayAuthError`) em vez de seguir com scan vazio.
- Duplicados **entre páginas** da busca (mesmo `itemId`) são contados no funil
  (`dedup_dropped`), não descartados em silêncio.
- Vendas de **lote/pack/playset/selado/"escolha"** ficam fora das medianas de
  vendas do PriceCharting (`pc_sales`, regex de venda não-unitária; "pack
  fresh" continua sendo carta única).
- A **nota** do slab nunca casa com o **número da carta** no título (ex.: "10"
  de "10/102" não vira "PSA 10").
- Certificadoras **GMA/HGA** entram na regex de fora-de-escopo
  (`skip_grade_out_of_scope`), em vez de passarem como raw.
- O **veredito final** (após anotação de referência) é o que conta no funil,
  não o provisório.
- Chamadas à Browse API são contadas **também quando dão erro** (`ebay_calls`
  inclui tentativas repetidas e falhas) — a cota consumida aparece de verdade.
- O **gate** efetivo (`min_discount_percent`) vai sempre explícito no config e
  no artefato JSON, nunca implícito no default do scorer.
- Anúncio com **preço ≤ 0** é descartado no piso (`skip_min_price`), não vira
  Desconto%/ROI absurdo.
- Raw **LP sem referência NM** disponível vai direto às vendas LP do
  PriceCharting (antes ficava sem referência por falta do pré-filtro NM).

Fixes do review limpo do PR B (2026-09-03):

- `--group` fora de 1–12, spec inválida ou grupo/nome **sem cartas na
  watchlist** erra ALTO (`ERRO: …`, exit ≠ 0) — antes `--group 13` derrubava
  com traceback e `--group x` virava scan de 0 cartas "bem-sucedido".
- Resolvedor do PriceCharting (`pc_sales`), após sondagem real do site: números
  **com letras** mantêm o prefixo (`SV49`, `TG23`, `H29`, `AR1`, `SL10` — o
  slug do PC é `charizard-gx-sv49`; antes viravam `49`, `23`…, e nunca
  casavam); **subconjuntos** (Shiny Vault, Trainer Gallery, Galarian Gallery,
  Classic Collection, Radiant Collection) são procurados no console do
  **set-pai** (`pc_console_label`, ex.: `pokemon-hidden-fates`); nomes **Tag
  Team** (`mewtwo-&-mew-gx-242`) e **Lv.X** (`gengar-lv-x-97`) casam; nome
  tcgcsv com número colado (`Mimikyu -160/091`) é limpo. Sem isso, 298 das
  1.673 candidatas da watchlist ficavam "sem PC" e fora do universo.

Backport do review da COMC (2026-09-04), os dois no mesmo resolvedor:

- **Venda "BGS 10 Black &lt;texto&gt;" não entra em cesta nenhuma.** O texto depois de
  "Black" tanto pode ser o nome da carta ("BGS 10 Black Kyurem EX") quanto o resto
  do título de uma etiqueta preta escrita sem a palavra "Label" ("BGS 10 Black Base
  Set 4/102"). Antes a segunda caía na cesta do **BGS 10 comum** e envenenava a
  mediana (uma venda de US$ 90 mil entre duas de US$ 1,5 mil). Mesma política do
  título que cita duas notas: no escuro, não conta. Custo: carta cujo nome começa
  com "Black" perde as vendas escritas nessa ordem.
- **Dono com duas palavras** no nome da carta ("Lt. Surge's Electabuzz", Gym Heroes
  e Gym Challenge): a 2ª tentativa sem o dono agora roda para eles também.

## 0.5.0 — 2026-09-03

Padrão COMC (decisão do operador, 2026-09-03): o scanner passa a usar o mesmo
método, métricas e layout de entrega do scanner irmão `scanner-comc`.
434 testes offline.

### Adicionado

- `src/grading.py` (portado de `scanner-comc` @ dd952ba, parse adaptado a
  títulos do eBay): allowlist de notas aceitas (`DEFAULT_GRADED_ALLOW` — PSA
  8/9/10, CGC 9/9.5/10 Gem Mint/10 Pristine, BGS 9/9.5/10/10 Black Label, SGC
  9/9.5/10, TAG 9.5/10; editável em `graded_allow` no `config.yaml`), status
  do título (`graded` / `raw` / `ambiguous` / `out_of_scope`), CGC 10 sem
  "Pristine" = Gem Mint, BGS 10 Black Label, `pc_price_key` (coluna exata do
  PriceCharting, nunca bucket genérico), `parse_grades_arg` (base do
  `--grades`).
- `src/pc_sales.py` (portado de `scanner-comc` @ dd952ba): vendas concluídas
  da página pública do PriceCharting como referência de slab — mediana das 10
  vendas mais recentes da MESMA carta + variante + certificadora + nota +
  subcategoria; ≥3 vendas em 180 dias = `ok`, ≥3 só em 365 dias = `low`
  (nota `baixa-liquidez(365d)`), 1–2 = `thin` (REVISAR `vendas<3(n=…)`), 0 =
  sem referência. Vendas LP explícitas para raw LP. Cache **do dia** em
  `data/cache/pc/<AAAA-MM-DD>/`, retry 3× em 429/5xx/rede, `PcError` para
  falha de fonte (distinta de "sem venda"), busca de página por
  nome+número+set (`product_page_url`).
- Raw **LP** com referência própria (opt-in junto com `--include-raw`): só com
  LP explícito no título ou no campo de condição do eBay, pré-filtro
  `preço ≤ ref NM × (1 − desconto mínimo)`, referência = mediana de ≥3 vendas
  LP. Nunca LP vs NM; "NM/LP" fica fora. `lp_with_reference: true` no config.
- Flags de run: `--min-discount N` (gate Desconto%, inteiro), `--min-price USD`
  (piso), `--max-pages N` (páginas de 200 na Browse API).
- Funil completo (`src/report.py` `FUNNEL_LABELS`) gravado no artefato JSON e
  impresso no cabeçalho da entrega: chamadas à API, analisados, duplicados,
  ignorados (leilão, piso, país, carta errada, raw, nota fora do funil/escopo/
  ambígua, sem NM/LP explícito), sem referência (slab/LP/raw), erro e breaker
  do PriceCharting, abaixo do desconto, linhas por veredito, modo confiável,
  erro por carta, erro na API, run abortado. Nada some em silêncio.
- Breaker do PriceCharting (`PcBreaker`): 5 falhas seguidas suspendem a fonte
  no run (`pc_breaker`) em vez de martelar o site.
- Abort do run: falha de autenticação no eBay ou 3 erros seguidos da Browse
  API param o scan (`aborted`), o artefato sai marcado `aborted: true`, a
  entrega mostra "RUN ABORTADO" e `main.py` sai com exit code 1.
- Browse API: paginação (`limit` 200 × `max_pages` 3, para em página curta ou
  `offset ≥ total`), dedupe por `itemId` entre páginas, retry em 429/5xx/rede
  (2s/4s), contador de chamadas `EbayClient.calls` (cota grátis 5.000/dia) →
  funil `ebay_calls`, `last_total`, `parse_search_payload` puro (testável
  offline), `EbayAuthError` / `EbayApiError`.
- `ebay_summary.py --sensitivity 10,15,20` (modo diagnóstico, portado do
  `comc_summary.py`): o maior limiar é o operacional (≥20% = candidato
  comercial); faixas 15–19,99% e 10–14,99% saem como "NÃO é oportunidade",
  com todas as linhas; tabela de contagens por limiar; aviso quando o scan
  rodou com desconto mínimo maior que o menor limiar.
- Cabeçalho da entrega: linha "Parâmetros" (desconto mínimo, piso, só preço
  fixo, só EUA, slabs aceitos), linha "Cobertura de referência" nova (slabs
  por mediana · raw NM c/ TCGplayer · raw LP · raw só PriceCharting · sem
  referência) e linha "Funil".
- Watchlist: campos opcionais `pokemon`, `pokemon_rank` (desempate final do
  ranking; sem rank = 9999), `rarity`, `year` (`WatchCard`,
  `load_watchlist`, `watchlist.example.yaml`).
- Fixtures reais: `tests/fixtures/ebay_search_charizard_base_psa.json`
  (payload da Browse API, 2026-09-03), `pc_product_charizard_base_4.html`,
  `pc_product_charizard_ex_151.html` (páginas de produto com vendas
  concluídas), `pc_search_charizard_ex_151.html` (página de busca).
  `.gitignore` ganha a exceção `!tests/fixtures/*.json`.
- Este `CHANGELOG.md`.

### Mudado

- **Gate = Desconto%** = `(referência − preço eBay) / referência`, percentual
  inteiro, `min_discount_percent: 20` no config (diagnóstico: `--min-discount
  10`). **ROI bruto%** = `(ref − preço) / preço` continua como coluna
  (`suspicious_margin_percent: 60` → SUSPEITO); **Spread$** = `ref − preço`.
  Nunca "lucro". `main.py` avisa alto se o config ainda tiver
  `min_gross_margin_percent` e usa o default (não converte em silêncio).
- **Só preço fixo** (`fixed_price_only: true`): o filtro
  `buyingOptions:{FIXED_PRICE}` vai na própria busca da Browse API (leilão nem
  entra); o scorer ainda conta qualquer leilão que escape
  (`skip_not_fixed_price`).
- **Referência de slab** = mediana de vendas concluídas (`src/pc_sales.py`).
  Coluna do PriceCharting e buckets genéricos "Grade 9"/"Grade 9.5" NUNCA são
  referência; a coluna exata da nota é só sanidade (`coluna÷vendas` quando
  fica >30% da mediana). Nota sem coluna própria (PSA 9, BGS 9.5, TAG 9.5…)
  tem referência só pelas vendas.
- Regras de título de slab: mais de uma nota = ambíguo = funil; certificadora
  desconhecida (ACE/MNT/GMA/…) = funil; "PSA 9.5" lido como 9.5 e derrubado
  pela allowlist (nunca arredondado para 9).
- Raw sem NM nem LP explícito = funil (`skip_condition`), não vira linha
  REJEITADO. Raw NM segue TCGplayer market (tcgcsv) com PriceCharting Ungraded
  como cross-check/fallback rotulado.
- Busca na Browse API: **1 query genérica por carta**, paginada, `sort=price`.
  Sufixos por certificadora (" psa"/" bgs"/" cgc"/" sgc"/" tag") viraram
  legado, só com `grade_query_suffixes: true`.
- Uma única página do PriceCharting por carta alimenta colunas (informação) e
  vendas (referência) — `scanner.load_card_page` / `CardRefs`.
- Entrega no layout COMC: colunas `# | Desconto% | ROI bruto% | eBay$ | Ref$ |
  Spread$ | Pokémon | Carta | Set | Tipo | Ref | Vend | Status | Links |
  Flags`; REJEITADO em tabela própria `# | Carta | Tipo | eBay$ | Motivo |
  Links`; ranking ROI bruto → desconto → spread → popularidade do Pokémon.
- Link `[referência]` = página da carta no PriceCharting SEMPRE que existir,
  também para raw (o preço raw continua TCGplayer; a coluna `Ref` diz a fonte);
  `[TCG]` só sem página PC.
- `run_scan` devolve `(fair_values, opportunities, pricing_only, stats,
  aborted)`; `scorer.evaluate` recebe `refs` (`CardRefs`) e `stats`
  (`Counter`) e devolve `None` com o motivo contado.
- `--confiavel`: filtro passa a ser ROI bruto abaixo do teto de suspeita (60)
  em vez de faixa fixa 30–60%; sem linha SUSPEITO/REJEITADO.
- tcgcsv: dois produtos com o mesmo número no set ("Charizard" vs "Charizard
  (Black Dot Error)") → o nome exato desempata; sem nome exato → sem
  referência TCG (caso real do smoke 2026-09-03).
- `title_parser`: "gold foil" / "gold plated" / "24k" / "metal card" =
  `REJEITAR` (carta falsa ou de metal).
- Documentação (`CLAUDE.md`, `README.md`, skill `scan-ebay`,
  `watchlist.example.yaml`) reescrita para o padrão COMC; run padrão da skill
  = `--group <grupo> --min-discount 20` (comercial) ou `--min-price 5
  --min-discount 10 --include-raw` + `--sensitivity 10,15,20` (diagnóstico).

### Removido

- Gate por ROI bruto (`min_gross_margin_percent`; era 30, depois 15 desde
  2026-09-01). A chave no config agora só gera aviso.
- Referência de slab pela coluna do PriceCharting e a nota "REF 9.5 = bucket
  genérico GRADE 9.5" (não existe mais: BGS/CGC 9.5 só por vendas comparáveis).
- Leilão no funil (só preço fixo).

## Antes de 0.5.0 (sem número de versão)

Histórico reconstruído a partir da documentação; a fonte de verdade era o
`main` mergeado.

- **2026-09-01** — threshold de ROI bruto 30% → 15% (decisão do operador);
  retry automático do PriceCharting (3 tentativas, backoff 2s/4s); flag
  `--grades` (funil restrito a notas, typo erra alto); guard de nomenclatura
  japonesa (SAR/CHR/CSR, códigos de set JP) em watchlist EN.
- **2026-07 (#18)** — padrão /myp-scan: `ebay_summary.py`, grupos na watchlist
  (`--group`/`--list-groups`), skill `scan-ebay`; referência raw via
  TCGplayer market (tcgcsv.com, `src/tcg_reference.py`).
- **PR #19** — run degradado (chaves eBay ausentes) não sobrescreve o
  artefato; carta não-EN nunca ganha referência TCG.
- **2026-06-10** — graded-only por default com reversão por run
  (`--include-raw`); modo confiável 50 avaliações / 98%; credenciais como env
  vars de usuário Windows; detecção de fraude "PSA 10" no título com
  condição "Ungraded" no eBay.
- **2026-06-09** — primeira versão: watchlist list-driven, PriceCharting por
  grade, eBay Browse API (scraping direto do eBay dá 403), scorer com
  vereditos OPORTUNIDADE/REVISAR/SUSPEITO/REJEITADO, filtro só EUA (entrega na
  COMC), sanitização de segredo (BOM/zero-width).


## Revisão de precisão — 2026-09-05 (esta branch)

- Base revisada: `86b8324`. CGC até 40% confirmado; lucro >US$40 OU desconto >30%
  substitui filtro global antigo. Margem e ROI permanecem informativos.
- Cobertura dos US$10 confirmada até COMC, incluindo eventual saída do vault.
  Elite US$2,50, venda 5%, saque 10% informado; armazenamento estimado para
  120 dias, incluindo carência e segurança sem carência. Fontes versionadas.
- Busca aplica Graded 2750; anúncios com IDs distintos não são descartados só
  porque têm preço/título iguais. Garantia de autenticidade não é presumida.
- Moeda/frete/preço desconhecidos continuam desconhecidos; erros não produzem
  execução completa. JSON atômico impede sobrescrever resultado com NaN/Infinity.
- Comparação distingue regiões chinesas, nomes/sufixos, denominadores, categorias
  especiais e ofertas sem preço efetivo. Medianas não são arredondadas antes dos limites.
- Relatórios exibem idioma observado, vault, projeção COMC e exclusões de vendas.
- Validação local e remota documentada em docs/VALIDATION_EBAY_PSA.md.

- Busca real de 3deee2b isolou títulos sem idioma como gargalo. getItem agora
  fornece Language explícito com limite de 10 detalhes por carta. Conflitos
  entre título e atributos continuam em REVISAR, com proveniência no relatório.

## 2026-09-10 — catálogo de identidade independente da seleção de busca

- A proteção contra colisões combina watchlist e metadados das 25 cartas da
  Celebrations: Classic Collection, com fonte TCGCSV/TCGplayer e IDs de produto.
  Nenhum alvo foi adicionado à watchlist e não há nova chamada de mercado no scan.
- Chaves de colisão respeitam o idioma. O catálogo inglês não identifica a
  população japonesa nem implica cobertura de todas as reimpressões.
- Títulos canônicos de SM/XY/SWSH Base Set deixam de se contradizer com o trecho
  genérico “Base Set”. Menções a outra expansão continuam sendo rejeitadas.
- Regressões verificam todas as identidades canônicas da watchlist e a proteção
  com uma seleção reduzida a uma carta, inclusive fora dos Pokémon selecionados.
- Reshiram & Charizard GX não consta entre os 25 produtos desta Classic Collection;
  não foi acrescentada uma colisão sem suporte no catálogo.

## 2026-09-10 — retorno coerente com a evidência de revenda

- No modo `gross_margin`, alerta de retorno elevado usa o Decimal exato do gate
  para todas as certificadoras, com motivo `retorno-elevado-conferir-identidade`.
  Regras legadas conservam seu comportamento. Os limiares configurados não mudam.
- JSON publica o retorno contra revenda, ou null quando indisponível. A coluna da
  política não usa fallback contra referência PSA, inclusive em artefatos antigos.
- A legenda esclarece que o denominador é compra (retorno bruto), não receita
  (margem sobre venda). O cabeçalho e chaves históricos são mantidos por compatibilidade.
- O teto de compra publicado fica um centavo abaixo quando a fronteira estrita
  cai exatamente num centavo; não promete um preço rejeitado pelo próprio gate.
- Testes cobrem certificadoras, origem do dado, ausência, renderização, reprovação
  com retorno disponível e limites antes de arredondamento. Sem coleta de mercado.
