# CLAUDE.md — ebay-arbitrage-scanner

Instruções para qualquer sessão Claude Code (local ou nuvem) que trabalhe neste repo.

Scanner de oportunidades em cartas Pokémon no eBay (graded: PSA 9/10, BGS 9.5/10,
CGC 9.5/10; EN e JP — raw NM existe no código e entra por opt-in `--include-raw`,
ver Regra 3), comparando anúncios ativos com o preço justo derivado de vendas
reais. Projeto independente dos scanners irmãos (CardTrader, MYP, Liga, sealed,
PSA Arbitrage) — não compartilha código com eles.

## 🛰️ Convenções da frota (cross-scanner)

> **Manual completo** (repo privado): https://github.com/matheuscllm-lgtm/scanners-commons — erros comuns, referências de preço, chaves, GitHub Actions e modelo de entrega de TODOS os scanners. Cópia-mestra local (PC do operador): `C:\Users\mathe\scanners-commons\`.

Invariantes que valem para TODOS os scanners:

- **Margem BRUTA, mínimo 30%** — só `(revenda − compra)/compra`, sem nenhuma taxa embutida (frete, cartão, IOF — o operador calcula por fora).
- **Piso de relevância R$50 (~US$10) — SÓ para cartas avulsas (singles).** Produtos SELADOS não têm piso (decisão do operador, 2026-06-27); lá o único critério é a margem ≥30%.
- **Só Near Mint** — condição por match EXATO `== "NM"`, nunca substring (já vazou SP).
- **Nunca inventar preço** — fonte falhou → marca fallback/erro e segue; jamais fabrica número.
- **Nunca recomendar compra** — o scanner reporta margem, flags e fontes; a decisão de capital é do operador.
- **Entrega = tabela markdown no chat** (nunca XLSX/CSV por padrão), gerada pela ferramenta do repo — nunca montada à mão —, mostrando TODAS as linhas (aprovadas + rejeitadas). Coluna `Carta` = nome + número; coluna `Links` combinada = `[oferta](url) · [TCG/referência](url)`.
- ⚠️ **Convenção de threshold:** percentual inteiro (`30`) = MYP, Liga, eBay; fração (`0.30`) = CardTrader, COMC, Selados.

Erros recorrentes (3 famílias — detalhe no manual):

1. **Segredo/ambiente:** BOM/zero-width numa chave → crash latin-1 no header → scan "verde mas vazio". Setar sem BOM (`printf '%s' 'KEY' | gh secret set`) **e** sanitizar ao ler no código (`.strip()` NÃO tira BOM).
2. **Git:** branch ou `main` local defasado por squash-merge PARECE pendência. O teste real de "já mergeado" é `git diff --stat origin/main <branch>` estar vazio (não `git merge-base`).
3. **Honestidade de preço:** inflação de referência, fallback tratado como real, NM frouxo → sempre validar versão/condição e rotular fallback.

**Este scanner:** referência de preço em 2 trilhos — **graded** = PriceCharting por grade (TCGplayer não tem preço graded; guarda de referência desalinhada + sanity check contra o market raw TCG); **raw NM** (opt-in `--include-raw`) = **TCGplayer market via tcgcsv.com** (`src/tcg_reference.py`, mesma fonte real do MYP v5.15+) com PriceCharting Ungraded como cross-check (divergência >40% = flag + REVISAR) e fallback PriceCharting **rotulado** (`REF: PriceCharting (sem TCG)`) quando o tcgcsv não cobre a carta **ou quando a carta não é EN** (a categoria 3 do tcgcsv é o catálogo INGLÊS do TCGplayer — carta JP nunca ganha referência TCG, senão a margem sairia do produto errado; PR #19). Listings via eBay Browse API; chaves que o CÓDIGO lê = `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` (`src/ebay_api.py`; marketplace `EBAY_US` e scope OAuth são hardcoded). `EBAY_DEV_ID`/`EBAY_ENV`/`EBAY_MARKETPLACE_ID`/`EBAY_SCOPE` existem como secrets do repo (Actions+Codespaces) mas não são consumidas por nenhum arquivo. CI é offline e não usa secret.

> **Reconciliação NM × graded-only (não há contradição):** o invariante "Só Near
> Mint" da frota vale para o caminho **RAW** deste scanner — que está **fora do
> funil por default** desde 2026-06-10 (`graded_only: true`), mas segue vivo e
> testado no código (`CFG_RAW = {"graded_only": False}` em `tests/test_scorer.py`)
> e é ligado por run com `--include-raw`. No caminho raw: só Near Mint, match
> conservador ("NM/LP" → rejeita), referência = TCGplayer market (tcgcsv) com
> PriceCharting como cross-check/fallback rotulado. Detalhe na Regra inviolável nº 3.

## Regras invioláveis deste repo (herdadas do operador, cross-scanner)

1. **Nunca recomendar compra.** O agente é técnico (código/auditoria/dados);
   capital é decisão do operador. Vereditos são classificação técnica
   (OPORTUNIDADE / REVISAR / SUSPEITO / REJEITADO — ver `src/scorer.py`).
2. **Margem bruta pura, threshold 30%.** `(justo − preço)/preço`, ZERO taxa
   embutida. Mesma base da fórmula da frota `(revenda − compra)/compra` — aqui
   "justo" é a revenda esperada e "preço" é a compra (o preço do anúncio);
   implementação em `src/scorer.py`. Piso USD 10 (`min_price_usd: 10.0`).
3. **Só graded por default (2026-06-10):** PSA 9/10, BGS 9.5/10, CGC 9.5/10.
   Raw está fora do funil default (`graded_only: true` no config — decisão de
   escopo do operador, não mexer). O caminho SANCIONADO de reversão é
   **por-run**: `python main.py --include-raw` liga o funil raw NM só naquele
   scan, sem alterar o config. Raw = só Near Mint, match conservador
   ("NM/LP" → rejeita); referência raw = TCGplayer market (tcgcsv), com
   PriceCharting como cross-check/fallback rotulado.
4. **Entrega = tabela markdown no chat**, todas as linhas (todos os buckets,
   inclusive REJEITADO com motivo), flag por linha, **gerada pelo
   `ebay_summary.py`** e colada VERBATIM (ver seção 📤 abaixo). Nunca
   arquivo/planilha por padrão (só se o operador pedir).
5. **Threshold deste repo é percentual INTEIRO** (`min_gross_margin_percent: 30`
   em `config.yaml`). Atenção: CT usa fração (0.30), MYP/Liga usam inteiro —
   aqui é inteiro, nomeado explicitamente para não haver pegadinha.
6. **Só vendedor com item nos EUA.** A entrega é na COMC (Algona, WA
   98001-7409, EUA — mailbox de armazenamento). Filtro `itemLocationCountry:US`
   na API + checagem-cinto-de-segurança no scorer
   (`required_location_country: US`). Cartas JP da watchlist = vendedores
   americanos vendendo carta japonesa, nunca vendedor no Japão.

## Como rodar

> 🎯 **Skill `scan-ebay`** (`.claude/skills/scan-ebay/SKILL.md`): quando o
> operador pedir pra "rodar o eBay", o agente **pergunta o escopo** (qual
> grupo da watchlist via `--list-groups` + qual funil: graded-only default /
> `--include-raw` / `--confiavel`), roda o scan com `--out` e entrega SEMPRE
> via `ebay_summary.py` — verbatim.

**Setup (1ª vez, qualquer ambiente):** o run exige uma watchlist, que é
local-only (gitignored) e NÃO vem num clone limpo:

```bash
python -m venv .venv    # PC do operador: Python 3.12
# Windows: .venv\Scripts\python -m pip install -r requirements.txt
# Linux/nuvem: source .venv/bin/activate && pip install -r requirements.txt
cp watchlist.example.yaml watchlist.yaml   # e preencher com os itens reais
```

**Dia a dia (PC do operador, PowerShell):**

```powershell
cd C:\Users\mathe\ebay-arbitrage-scanner
.venv\Scripts\python -m pytest tests/ -q        # 117 testes, offline
.venv\Scripts\python main.py --list-groups      # grupos da watchlist (sem chaves)
.venv\Scripts\python main.py --pricing-only     # sem credenciais (PriceCharting apenas)
.venv\Scripts\python main.py                    # scan completo (exige EBAY_CLIENT_ID/SECRET)
.venv\Scripts\python main.py --group chase-en   # só as cartas do grupo `chase-en`
.venv\Scripts\python main.py --include-raw      # inclui raw NM NESTE run (ref = TCGplayer)
.venv\Scripts\python main.py --confiavel        # só vendedores >=50 avals/98%+, margem 30-60%
```

Na nuvem/Linux, os mesmos comandos com `python`/`.venv/bin/python`.

O scan grava um **artefato JSON** (`--out`, default `results/last_scan.json`,
gitignored) com TODAS as linhas avaliadas (inclusive REJEITADO). ⚠️ **Run
degradado não grava artefato** (PR #19): se as chaves eBay faltarem, o scan
vira pricing-only, avisa alto e **preserva** o `last_scan.json` do último scan
real — nunca sobrescreve com um relatório vazio "verde". A **entrega** sai dele:

```powershell
.venv\Scripts\python ebay_summary.py results\last_scan.json -o results\ebay-<AAAA-MM-DD>.md
```

**Flags do CLI (`main.py`):**

- `--watchlist` (default `watchlist.yaml`) — watchlist alternativa.
- `--config` (default `config.yaml`) — configuração alternativa.
- `--list-groups` — lista os grupos da watchlist (sem chaves) e sai.
- `--group <nome>` — roda só as cartas do grupo nomeado (ex.: `chase-en`).
- `--include-raw` — inclui o funil raw NM NESTE run (referência = TCGplayer via
  tcgcsv); sem a flag, raw fica fora (`graded_only: true`).
- `--pricing-only` — só preço justo da watchlist (PriceCharting); não consulta
  o eBay, não precisa de credencial. Sem credenciais configuradas, o scan
  completo cai neste modo sozinho, com aviso.
- `--confiavel` — modo confiável: só vendedores com histórico
  (`trusted_min_feedback: 50` avaliações e `trusted_min_feedback_pct: 98.0`,
  em `config.yaml`) e margem na faixa saudável 30–60% (acima de
  `suspicious_margin_percent: 60` sai do modo); nenhuma linha rejeitada —
  tabela 100% acionável. Decisão do operador 2026-06-10: 50/98 em vez de
  100/99 (abre funil pro vendedor médio honesto; golpista tem 0–9 avals);
  96% foi avaliado e rejeitado (nível de conta comprada/sequestrada).
- `--out` (default `results/last_scan.json`) — artefato JSON de onde a entrega
  (`ebay_summary.py`) é gerada.
- `--csv` (default `data/last_scan.csv`) — caminho do CSV de registro local
  (registro, não entrega).

**Credenciais:** env vars de USUÁRIO Windows desde 2026-06-10 (keyset
"MinhaLojaEbay" em developer.ebay.com). Sessão de terminal antiga pode não
herdar — passar inline se aparecerem como ausentes. O código sanitiza
BOM/zero-width ao ler (`_clean_secret` em `src/ebay_api.py`) — defesa contra o
erro recorrente nº 1 da frota.

**Skill `/auto`** (`.claude/commands/auto.md`): agente master autônomo da
frota, sincronizado entre os repos — modo de execução ponta a ponta quando o
operador o invoca.

## 📤 Entrega de resultados — via `ebay_summary.py`, NUNCA tabela à mão (MANDATÓRIO)

**Um caminho só** (mesmo contrato do MYP/`myp_summary.py`): rode
`ebay_summary.py` sobre o JSON do scan e **cole o markdown VERBATIM** no chat.
Proibido remontar/reformatar a tabela, renomear/reordenar colunas ou dropar o
link de referência "pra economizar largura". Nunca arquivo/planilha por padrão
(só se o operador pedir explicitamente); o CSV (`data/last_scan.csv`) é
registro local, não entrega.

O que a ferramenta gera (e você entrega assim, sem mexer):

- Cabeçalho com data, nº de cartas, contagem por veredito e a linha
  **"Cobertura de referência"** (X graded PriceCharting · Y raw c/ TCGplayer
  real · Z raw só PriceCharting · N sem referência — honestidade de fonte,
  sempre reportar; só conta linhas cuja margem USOU uma referência).
- **4 seções, SEMPRE todas as linhas**, ordenadas por score:
  🟢 OPORTUNIDADE · ⚠️ REVISAR (validar manualmente) · 🚨 SUSPEITO (margem
  alta demais — validar) · ⛔ REJEITADO (com motivo).
- Coluna `Carta` = nome + número; coluna `Links` = `[oferta](url_eBay) ·
  [TCG](url_TCGplayer)` quando a referência da margem é TCGplayer, ou
  `[oferta](url_eBay) · [ref](url_PriceCharting)` quando é PriceCharting.
  **Os dois links em TODA linha de TODO bucket**; URLs lidas do JSON, nunca
  inventadas — se faltar uma URL, a célula mostra só o link que existe.

A formatação canônica vive em `src/report.py` (helpers `links_cell`,
`carta_label`, `escape_md`, além de `to_markdown`/`fair_value_markdown`) e é
consumida por `ebay_summary.py` — fonte única, não duplicar formato. Vereditos
são classificação técnica; **nunca recomendar compra**.

## Fontes de dados (todas gratuitas)

- **tcgcsv.com** (referência TCGplayer real p/ RAW): dump diário público dos
  preços do TCGplayer (categoria 3 = Pokémon), cliente stdlib em
  `src/tcg_reference.py` com cache 24h em `data/cache/tcgcsv/`. Mesma fonte
  que o MYP scanner usa no CI (v5.15+). Só `marketPrice` conta (subtype
  Normal→Holofoil→Reverse Holofoil); sem marketPrice/sem match = None e o
  raw cai no fallback PriceCharting ROTULADO. **Carta não-EN = sempre None**
  (catálogo tcgcsv é inglês; carta JP casaria com o produto EN homônimo —
  guard do PR #19). Set resolvido por match exato
  do nome (`tcg_set:` na watchlist quando o nome não bate). ⚠️ User-Agent é
  obrigatório (sem ele = 401). **TCGplayer não tem preço graded** — por isso
  graded segue PriceCharting.
- **PriceCharting** (preço justo/tendência/liquidez): scrape público com
  urllib + cache 24h em `data/cache/` (`src/pricecharting.py`). Validado
  2026-06-09 (HTTP 200). A tabela principal usa ids herdados de video game:
  `used_price`=RAW, `complete_price`=Grade 7, `new_price`=Grade 8,
  `graded_price`=PSA 9, `box_only_price`=Grade 9.5, `manual_only_price`=PSA 10.
  BGS/CGC/SGC vêm da seção `#full-prices`.
- **eBay Browse API** (anúncios ativos): OAuth client-credentials com
  `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` (5.000 chamadas/dia grátis; setup ~5
  min descrito no topo de `src/ebay_api.py`). **Scraping direto do eBay NÃO
  funciona** (403 com urllib e cloudscraper, testado 2026-06-09) — não tente
  "consertar" voltando a scraping. A API de sold/completed do eBay
  (Marketplace Insights) é restrita — o agregado de vendidos vem do
  PriceCharting.

## Testes e CI

```bash
python -m pytest -q          # canônico (pytest.ini já escopa testpaths=tests)
```

No PC do operador: `.venv\Scripts\python -m pytest tests/ -q`. São 117 testes
(verificado 2026-07-07 via `pytest --collect-only`), todos offline (sem rede,
sem credenciais).

CI: `.github/workflows/tests.yml` — job `pytest` em `ubuntu-latest`,
Python 3.12, dispara em push na `main`, em todo PR e por `workflow_dispatch`.
Totalmente offline e **sem nenhum secret** (repo público, runner grátis).

## Arquitetura

```
main.py                CLI: watchlist + config -> run_scan -> entrega markdown + JSON (--out) + CSV de registro
config.yaml            threshold/piso/graded_only/modo confiavel/pais exigido (comentados)
watchlist.example.yaml modelo da watchlist (copiar p/ watchlist.yaml, local-only); grupos de cartas
src/scanner.py         orquestrador: watchlist -> preco justo -> anuncios (dedupe por id E
                       titulo+preco) -> avaliacao; sufixos de query por grade (graded-only
                       busca " psa"/" bgs"/" cgc"); guarda REF DESALINHADA (justo vs mediana
                       dos anuncios limpos da mesma grade, 1.5x/0.6x, min. 3 amostras)
src/ebay_api.py        cliente Browse API: OAuth client-credentials, _clean_secret (BOM/
                       zero-width), categoria 183454 (CCG Individual Cards), filtro
                       itemLocationCountry, flag AG calculado (ver Armadilhas)
src/tcg_reference.py   referência TCGplayer real p/ RAW via tcgcsv.com (cache 24h; marketPrice;
                       User-Agent obrigatório) — mesma fonte real do MYP v5.15+
src/pricecharting.py   scrape do preco justo/tendencia/volume + cache 24h em data/cache/
src/title_parser.py    identidade da carta no titulo, grade, idioma, NM aceitavel, risk flags
src/scorer.py          avaliacao -> Opportunity: margem bruta, score 0-100 (margem 45 /
                       liquidez 25 / tendencia 15 / risco 15), trust_score separado da
                       margem, vereditos OPORTUNIDADE/REVISAR/SUSPEITO/REJEITADO
src/report.py          ENTREGA canonica (to_markdown / fair_value_markdown / links_cell /
                       carta_label / escape_md) + to_csv (registro)
src/models.py          dataclasses (WatchCard, Listing, FairValue, Opportunity)
ebay_summary.py        ENTREGA ao operador: JSON do scan (--out) -> markdown (4 buckets +
                       linha de cobertura de referência); espelho do myp_summary.py
tests/                 117 testes offline (pricecharting parse, report, scanner ref, scorer,
                       tcg_reference, summary, watchlist groups, sanitizacao de segredo,
                       title parser) + fixture real
```

A watchlist é **list-driven de propósito**: casar item a partir de título
arbitrário é a maior fonte de erro; partir de item conhecido (com URL de
referência exata) e buscar anúncios DAQUELE item inverte o problema e dá
precisão (ver comentário em `watchlist.example.yaml`).

## Armadilhas conhecidas

- `qualifiedPrograms` (Authenticity Guarantee) NÃO vem no endpoint de busca
  da Browse API, só no de detalhe. O flag AG é calculado por política do eBay:
  carta ≥ $250 localizada nos EUA = AG automático. Não "consertar" tentando
  ler o campo da busca.
- PSA 9.5 não existe; o regex de PSA 9 usa `(?![\d.])` para não casar "9.5".
- O PriceCharting NÃO tem coluna separada para BGS 9.5 / CGC 9.5 — o preço
  justo dessas grades usa o bucket genérico "GRADE 9.5" (agrega PSA/BGS/CGC =
  aproximação). Sem esse mapeamento no scorer a oferta sumiria em silêncio;
  a linha sai com flag `REF 9.5` para o operador conferir.
- Referência raw via tcgcsv exige **User-Agent** (sem ele = 401); sem
  marketPrice/sem match, o raw cai no fallback PriceCharting **rotulado**
  (`REF: PriceCharting (sem TCG)`) — nunca preço inventado.
- O parser de volume do PriceCharting depende da ORDEM das células de volume
  na tabela principal (mesma ordem das colunas de preço).
- Sinal "+" da tendência vem como `&#43;` no HTML.
- Fixture de teste: `tests/fixtures/pc_charizard_base.html` (página real).

## Fluxo de desenvolvimento e segurança

- **Branch + PR, nunca push direto em `main`** — é o fluxo padrão do repo.
- **Repo público e discreto**: dados de scan NUNCA entram no repo. Gitignored:
  `data/` (cache + CSVs), `results/` (JSON de scan), `*.csv`/`*.xlsx`/`*.json`,
  `watchlist.yaml` e `METODO.md` (lista de alvos e método são locais), `.env`,
  `.venv/`.
- **Credenciais nunca versionadas** — só env vars / `.env` local / secrets do
  GitHub. Procedimento de report e rotação (regenerar Cert ID em
  developer.ebay.com → Application Keys): `SECURITY.md`. Checklist de
  publicação: `PUBLIC-RELEASE-CHECKLIST.md`.
- A sanitização de segredo da frota está implementada localmente
  (`_clean_secret` em `src/ebay_api.py`) e travada por
  `tests/test_secret_sanitization.py`.

## Estado e histórico

- Sem versionamento formal (não há `CHANGELOG.md` nem string de versão); a
  fonte de verdade é o `main` mergeado.
- Decisões do operador em vigor: graded-only por default + reversão por-run via
  `--include-raw`, parâmetros do modo confiável 50/98 (ambas 2026-06-10),
  credenciais como env vars de usuário Windows (2026-06-10). Referência raw via
  TCGplayer/tcgcsv + padrão /myp-scan (ebay_summary.py, grupos, skill scan-ebay)
  adicionados em 2026-07 (#18). Validações históricas de rede: PriceCharting
  HTTP 200 e eBay 403 a scraping (2026-06-09).
