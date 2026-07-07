# CLAUDE.md — eBay Pokémon TCG Arbitrage Scanner

Instruções para qualquer sessão Claude (local ou nuvem) que trabalhe neste repo.

## 🛰️ Convenções da frota (cross-scanner)

> **Manual completo** (repo privado): https://github.com/matheuscllm-lgtm/scanners-commons — erros comuns, referências de preço, chaves, GitHub Actions e modelo de entrega de TODOS os scanners. Cópia-mestra local: `C:\Users\mathe\scanners-commons\`.

Invariantes que valem para TODOS os scanners:
- **Margem BRUTA, mínimo 30%** — só `(revenda − compra)/compra`, sem taxa embutida; piso de relevância R$50 (~US$10).
- **Só Near Mint** — condição por match EXATO `== "NM"`, nunca substring (já vazou SP).
- **Nunca inventar preço** — fonte falhou → marca fallback/erro e segue; jamais fabrica número.
- **Entrega = tabela markdown no chat** (nunca XLSX por padrão), gerada pela ferramenta do repo, mostrando TODAS as linhas (aprovadas + rejeitadas). Coluna `Carta` = nome + número; coluna `Links` combinada = `[oferta](url) · [TCG/referência](url)`.
- ⚠️ **Convenção de threshold:** percentual inteiro (`30`) = MYP, Liga, eBay; fração (`0.30`) = CardTrader, COMC, Selados. (Neste repo o eBay usa `min_gross_margin_percent: 30` — ver Regra inviolável nº 5.)

Erros recorrentes (3 famílias — detalhe no manual):
1. **Segredo/ambiente:** BOM/zero-width numa chave → crash latin-1 no header → scan "verde mas vazio". Setar sem BOM (`printf '%s' 'KEY' | gh secret set`) **e** sanitizar ao ler no código (`.strip()` NÃO tira BOM).
2. **Git:** galho ou `main` local defasado por squash-merge PARECE pendência. O teste real de "já mergeado" é `git diff --stat origin/main <galho>` estar vazio (não `git merge-base`).
3. **Honestidade de preço:** inflação de referência, fallback tratado como real, NM frouxo → sempre validar versão/condição e rotular fallback.

**Este scanner:** referência de preço em 2 trilhos — **graded** = PriceCharting por grade (TCGplayer não tem preço graded; guarda de referência desalinhada + sanity check contra o market raw TCG); **raw NM** (opt-in `--include-raw`) = **TCGplayer market via tcgcsv.com** (`src/tcg_reference.py`, mesma fonte real do MYP v5.15+) com PriceCharting Ungraded como cross-check (divergência >40% = flag + REVISAR) e fallback PriceCharting **rotulado** (`REF: PriceCharting (sem TCG)`) quando o tcgcsv não cobre a carta. Listings via eBay Browse API; chaves = `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET`/`EBAY_DEV_ID`/`EBAY_ENV`/`EBAY_MARKETPLACE_ID`/`EBAY_SCOPE` (secrets no repo, Actions+Codespaces; CI é offline).

## O que é

Scanner de oportunidades em cartas Pokémon no eBay (raw NM + PSA 9/10,
BGS 9.5/10, CGC 9.5/10; EN e JP), comparando anúncios ativos com o preço justo
derivado de vendas reais. Projeto independente dos scanners irmãos (CardTrader,
MYP, Liga, sealed, PSA Arbitrage) — não compartilha código com eles.

## Regras invioláveis (herdadas do operador, cross-scanner)

1. **Nunca recomendar compra.** Claude é técnico (código/auditoria/dados);
   capital é decisão do operador. Vereditos são classificação técnica.
2. **Margem bruta pura, threshold 30%.** `(justo − preço)/preço`, ZERO taxa
   embutida. Piso USD 10.
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
5. **Threshold deste repo é percentual INTEIRO** (`min_gross_margin_percent: 30`).
   Atenção: CT usa fração (0.30), MYP/Liga usam inteiro — aqui é inteiro,
   nomeado explicitamente para não haver pegadinha.
6. **Só vendedor com item nos EUA.** A entrega é na COMC (Algona, WA
   98001-7409, EUA — mailbox de armazenamento). Filtro `itemLocationCountry:US`
   na API + checagem no scorer. Cartas JP da watchlist = vendedores
   americanos vendendo carta japonesa, nunca vendedor no Japão.

## Como rodar

> 🎯 **Skill `scan-ebay`** (`.claude/skills/scan-ebay/SKILL.md`): quando o
> operador pedir pra "rodar o eBay", o agente **pergunta o escopo** (qual
> grupo da watchlist via `--list-groups` + qual funil: graded-only default /
> `--include-raw` / `--confiavel`), roda o scan com `--out` e entrega SEMPRE
> via `ebay_summary.py` — verbatim.

```powershell
cd C:\Users\mathe\ebay-arbitrage-scanner
.venv\Scripts\python -m pytest tests/ -q        # 110 testes (offline)
.venv\Scripts\python main.py --list-groups      # grupos da watchlist (sem chaves)
.venv\Scripts\python main.py --pricing-only     # sem credenciais (PriceCharting apenas)
.venv\Scripts\python main.py                    # scan completo (exige EBAY_CLIENT_ID/SECRET)
.venv\Scripts\python main.py --group chase-en   # so as cartas do grupo `chase-en`
.venv\Scripts\python main.py --include-raw      # inclui raw NM NESTE run (ref = TCGplayer)
.venv\Scripts\python main.py --confiavel        # so vendedores >=50 avals/98%+, margem 30-60%
```

O scan grava um **artefato JSON** (`--out`, default `results/last_scan.json`,
gitignored) com TODAS as linhas avaliadas (inclusive REJEITADO). A **entrega**
sai dele:

```powershell
.venv\Scripts\python ebay_summary.py results\last_scan.json -o results\ebay-<AAAA-MM-DD>.md
```

Credenciais: env vars de USUARIO Windows desde 2026-06-10 (keyset "MinhaLojaEbay").
Sessao de terminal antiga pode nao herdar -- passar inline se `ausentes`.

Venv local em `.venv` (Python 3.12). Na nuvem: `python -m venv .venv` +
`pip install -r requirements.txt`.

## 📤 Entrega de resultados — via `ebay_summary.py`, NUNCA tabela à mão

**Um caminho só** (mesmo contrato do MYP/`myp_summary.py`): rode
`ebay_summary.py` sobre o JSON do scan e **cole o markdown VERBATIM** no chat.
Proibido remontar/reformatar a tabela, renomear/reordenar colunas ou dropar o
link de referência "pra economizar largura".

O que a ferramenta gera (e você entrega assim, sem mexer):

- Cabeçalho com data, nº de cartas, contagem por veredito e a linha
  **"Cobertura de referência"** (X graded PriceCharting · Y raw c/ TCGplayer
  real · Z raw só PriceCharting — honestidade de fonte, sempre reportar).
- **4 seções, SEMPRE todas as linhas**, ordenadas por score:
  🟢 OPORTUNIDADE · ⚠️ REVISAR (validar manualmente) · 🚨 SUSPEITO (margem
  alta demais — validar) · ⛔ REJEITADO (com motivo).
- Coluna `Carta` = nome + número; coluna `Links` = `[oferta](url_eBay) ·
  [TCG](url_TCGplayer)` quando a referência da margem é TCGplayer, ou
  `[oferta](url_eBay) · [ref](url_PriceCharting)` quando é PriceCharting.
  **Os dois links em TODA linha de TODO bucket**; URLs lidas do JSON, nunca
  inventadas — se faltar uma URL, a célula mostra só o link que existe.

A formatação canônica vive em `src/report.py` (helpers `links_cell`,
`carta_label`, `escape_md`) e é consumida por `ebay_summary.py` — fonte única,
não duplicar formato. Sem recomendação de compra, nunca.

## Fontes de dados (todas gratuitas)

- **tcgcsv.com** (referência TCGplayer real p/ RAW): dump diário público dos
  preços do TCGplayer (categoria 3 = Pokémon), cliente stdlib em
  `src/tcg_reference.py` com cache 24h em `data/cache/tcgcsv/`. Mesma fonte
  que o MYP scanner usa no CI (v5.15+). Só `marketPrice` conta (subtype
  Normal→Holofoil→Reverse Holofoil); sem marketPrice/sem match = None e o
  raw cai no fallback PriceCharting ROTULADO. Set resolvido por match exato
  do nome (`tcg_set:` na watchlist quando o nome não bate). ⚠️ User-Agent é
  obrigatório (sem ele = 401). **TCGplayer não tem preço graded** — por isso
  graded segue PriceCharting.
- **PriceCharting** (preço justo/tendência/liquidez): scrape público com
  urllib + cache 24h em `data/cache/`. Validado 2026-06-09 (HTTP 200).
  A tabela principal usa ids herdados de video game:
  `used_price`=RAW, `complete_price`=Grade 7, `new_price`=Grade 8,
  `graded_price`=PSA 9, `box_only_price`=Grade 9.5, `manual_only_price`=PSA 10.
  BGS/CGC/SGC vêm da seção `#full-prices`.
- **eBay Browse API** (anúncios ativos): OAuth client-credentials com
  `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` (env vars de usuário Windows).
  **Scraping direto do eBay NÃO funciona** (403 com urllib e cloudscraper,
  testado 2026-06-09) — não tente "consertar" voltando a scraping.
  A API de sold/completed do eBay (Marketplace Insights) é restrita —
  o agregado de vendidos vem do PriceCharting.

## Armadilhas conhecidas

- `qualifiedPrograms` (Authenticity Guarantee) NAO vem no endpoint de busca
  da Browse API, so no de detalhe. O flag AG e calculado por politica do eBay:
  carta >= $250 localizada nos EUA = AG automatico. Nao "consertar" tentando
  ler o campo da busca.

- PSA 9.5 não existe; o regex de PSA 9 usa `(?![\d.])` para não casar "9.5".
- O parser de volume do PriceCharting depende da ORDEM das células de volume
  na tabela principal (mesma ordem das colunas de preço).
- Sinal "+" da tendência vem como `&#43;` no HTML.
- Fixture de teste: `tests/fixtures/pc_charizard_base.html` (página real).
