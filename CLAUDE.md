# CLAUDE.md — ebay-arbitrage-scanner

Instruções para qualquer sessão Claude Code (local ou nuvem) que trabalhe neste repo.

Scanner de oportunidades em cartas Pokémon no eBay (graded: PSA 9/10, BGS 9.5/10,
CGC 9.5/10; EN e JP — raw NM existe no código mas está fora do funil, ver Regra 3),
comparando anúncios ativos com o preço justo derivado de vendas reais. Projeto
independente dos scanners irmãos (CardTrader, MYP, Liga, sealed, PSA Arbitrage) —
não compartilha código com eles.

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

**Este scanner:** referência de preço = PriceCharting (valor justo raw NM + graded; guarda de referência desalinhada) com listings via eBay Browse API; chaves que o CÓDIGO lê = `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` (`src/ebay_api.py` — marketplace default `EBAY_US` e scope OAuth são hardcoded no código; `EBAY_DEV_ID`/`EBAY_ENV`/`EBAY_MARKETPLACE_ID`/`EBAY_SCOPE`, se existirem como secrets do GitHub, não são consumidas por nenhum arquivo do repo). CI é offline e não usa nenhum secret.

> **Reconciliação NM × graded-only (não há contradição):** o invariante "Só Near
> Mint" da frota vale para o caminho **RAW** deste scanner — que está **fora do
> funil** desde 2026-06-10 (`graded_only: true`), mas segue vivo e testado no
> código (`CFG_RAW = {"graded_only": False}` em `tests/test_scorer.py`) caso o
> operador reverta. Se reverter: raw só Near Mint, match conservador
> ("NM/LP" → rejeita). Detalhe na Regra inviolável nº 3.

## Regras invioláveis deste repo (herdadas do operador, cross-scanner)

1. **Nunca recomendar compra.** O agente é técnico (código/auditoria/dados);
   capital é decisão do operador. Vereditos são classificação técnica
   (OPORTUNIDADE / REVISAR / SUSPEITO / REJEITADO — ver `src/scorer.py`).
2. **Margem bruta pura, threshold 30%.** `(justo − preço)/preço`, ZERO taxa
   embutida. Mesma base da fórmula da frota `(revenda − compra)/compra` — aqui
   "justo" é a revenda esperada e "preço" é a compra (o preço do anúncio);
   implementação em `src/scorer.py`. Piso USD 10 (`min_price_usd: 10.0`).
3. **Só graded (decisão do operador 2026-06-10):** PSA 9/10, BGS 9.5/10,
   CGC 9.5/10. Raw está fora do funil (`graded_only: true` em `config.yaml`;
   corte em `src/scorer.py`). Racional: nota de terceiro é verificável por cert
   lookup; condição de raw não é. A lógica de raw NM-only segue no código
   (testada via `CFG_RAW` nos testes) caso o operador reverta — se reverter:
   raw só Near Mint, match conservador ("NM/LP" → rejeita).
4. **Entrega = tabela markdown no chat**, todas as linhas, flag por linha.
   Nunca arquivo/planilha por padrão (só se o operador pedir). Ferramenta
   canônica e detalhe na seção 📤 abaixo.
5. **Threshold deste repo é percentual INTEIRO** (`min_gross_margin_percent: 30`
   em `config.yaml`). Atenção: CT usa fração (0.30), MYP/Liga usam inteiro —
   aqui é inteiro, nomeado explicitamente para não haver pegadinha.
6. **Só vendedor com item nos EUA.** A entrega é na COMC (Algona, WA
   98001-7409, EUA — mailbox de armazenamento). Filtro `itemLocationCountry:US`
   na API + checagem-cinto-de-segurança no scorer
   (`required_location_country: US`). Cartas JP da watchlist = vendedores
   americanos vendendo carta japonesa, nunca vendedor no Japão.

## Como rodar

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
.venv\Scripts\python -m pytest tests/ -q        # 75 testes, offline
.venv\Scripts\python main.py --pricing-only     # sem credenciais (PriceCharting apenas)
.venv\Scripts\python main.py                    # scan completo (exige EBAY_CLIENT_ID/SECRET)
.venv\Scripts\python main.py --confiavel        # so vendedores >=50 avals/98%+, margem 30-60%
```

Na nuvem/Linux, os mesmos comandos com `python`/`.venv/bin/python`.

**Flags do CLI (`main.py`):**

- `--watchlist` (default `watchlist.yaml`) — watchlist alternativa.
- `--config` (default `config.yaml`) — configuração alternativa.
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

## 📤 Entrega de resultados (MANDATÓRIO)

- **Entrega = tabela markdown no chat**, com **TODAS** as linhas (não amostra
  curada), ordenadas por score, **flag por linha**, links
  `[oferta](url) · [referência](url)`.
- **A tabela é gerada pela ferramenta do repo — nunca montada à mão:**
  `src/report.py::to_markdown` (oportunidades) e
  `src/report.py::fair_value_markdown` (modo `--pricing-only`), impressas
  automaticamente pelo `main.py` no fim de todo run. Cole o que o programa
  imprimiu.
- O CSV (`data/last_scan.csv`) é **registro local**, não entrega. Arquivo/
  planilha só se o operador pedir explicitamente.
- Vereditos são classificação técnica; **nunca recomendar compra**.

## Testes e CI

```bash
python -m pytest -q          # canônico (pytest.ini já escopa testpaths=tests)
```

No PC do operador: `.venv\Scripts\python -m pytest tests/ -q`. São 75 testes,
todos offline (sem rede, sem credenciais).

CI: `.github/workflows/tests.yml` — job `pytest` em `ubuntu-latest`,
Python 3.12, dispara em push na `main`, em todo PR e por `workflow_dispatch`.
Totalmente offline e **sem nenhum secret** (repo público, runner grátis).

## Fontes de dados (ambas gratuitas)

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

## Arquitetura

```
main.py                CLI: watchlist + config -> run_scan -> entrega markdown + CSV de registro
config.yaml            threshold/piso/graded_only/modo confiavel/pais exigido (comentados)
watchlist.example.yaml modelo da watchlist (copiar p/ watchlist.yaml, local-only)
src/scanner.py         orquestrador: watchlist -> preco justo -> anuncios (dedupe por id E
                       titulo+preco) -> avaliacao; sufixos de query por grade (graded-only
                       busca " psa"/" bgs"/" cgc"); guarda REF DESALINHADA (justo vs mediana
                       dos anuncios limpos da mesma grade, 1.5x/0.6x, min. 3 amostras)
src/ebay_api.py        cliente Browse API: OAuth client-credentials, _clean_secret (BOM/
                       zero-width), categoria 183454 (CCG Individual Cards), filtro
                       itemLocationCountry, flag AG calculado (ver Armadilhas)
src/pricecharting.py   scrape do preco justo/tendencia/volume + cache 24h em data/cache/
src/title_parser.py    identidade da carta no titulo, grade, idioma, NM aceitavel, risk flags
src/scorer.py          avaliacao -> Opportunity: margem bruta, score 0-100 (margem 45 /
                       liquidez 25 / tendencia 15 / risco 15), trust_score separado da
                       margem, vereditos OPORTUNIDADE/REVISAR/SUSPEITO/REJEITADO
src/report.py          ENTREGA canonica (to_markdown / fair_value_markdown) + to_csv (registro)
src/models.py          dataclasses (WatchCard, Listing, FairValue, Opportunity)
tests/                 75 testes offline (pricecharting parse, report, scanner ref, scorer,
                       sanitizacao de segredo, title parser) + fixture real
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
- O parser de volume do PriceCharting depende da ORDEM das células de volume
  na tabela principal (mesma ordem das colunas de preço).
- Sinal "+" da tendência vem como `&#43;` no HTML.
- Fixture de teste: `tests/fixtures/pc_charizard_base.html` (página real).

## Fluxo de desenvolvimento e segurança

- **Branch + PR, nunca push direto em `main`** — é o fluxo padrão do repo.
- **Repo público e discreto**: dados de scan NUNCA entram no repo. Gitignored:
  `data/` (cache + CSVs), `*.csv`/`*.xlsx`/`*.json`, `watchlist.yaml` e
  `METODO.md` (lista de alvos e método são locais), `.env`, `.venv/`.
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
- Decisões do operador em vigor: graded-only e parâmetros do modo confiável
  50/98 (ambas 2026-06-10), credenciais como env vars de usuário Windows
  (2026-06-10). Validações históricas de rede: PriceCharting HTTP 200 e
  eBay 403 a scraping (2026-06-09).
