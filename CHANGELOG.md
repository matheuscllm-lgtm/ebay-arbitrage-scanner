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
(os mesmos 12 grupos da COMC). 470 testes offline (17 arquivos).

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
