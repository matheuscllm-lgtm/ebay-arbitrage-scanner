# CLAUDE.md — eBay Pokémon TCG Arbitrage Scanner

Instruções para qualquer sessão Claude (local ou nuvem) que trabalhe neste repo.

## 🛰️ Convenções da frota (cross-scanner)

> **Manual completo** (repo privado): https://github.com/matheuscllm-lgtm/scanners-commons — erros comuns, referências de preço, chaves, GitHub Actions e modelo de entrega de TODOS os scanners. Cópia-mestra local: `C:\Users\mathe\scanners-commons\`.

Invariantes que valem para TODOS os scanners:
- **Margem BRUTA, mínimo 30%** — só `(revenda − compra)/compra`, sem taxa embutida; piso de relevância R$50 (~US$10).
- **Só Near Mint** — condição por match EXATO `== "NM"`, nunca substring (já vazou SP).
- **Nunca inventar preço** — fonte falhou → marca fallback/erro e segue; jamais fabrica número.
- **Entrega = tabela markdown no chat** (nunca XLSX por padrão), gerada pela ferramenta do repo, mostrando TODAS as linhas (aprovadas + rejeitadas). Coluna `Carta` = nome + número; coluna `Links` combinada = `[oferta](url) · [TCG/referência](url)`.
- ⚠️ **Convenção de threshold:** MYP **e eBay** = percentual inteiro (`30`); CardTrader/COMC = fração (`0.30`). (Neste repo é `min_gross_margin_percent: 30` — ver Regra inviolável nº 5.)

Erros recorrentes (3 famílias — detalhe no manual):
1. **Segredo/ambiente:** BOM/zero-width numa chave → crash latin-1 no header → scan "verde mas vazio". Setar sem BOM (`printf '%s' 'KEY' | gh secret set`) **e** sanitizar ao ler no código (`.strip()` NÃO tira BOM).
2. **Git:** galho ou `main` local defasado por squash-merge PARECE pendência. O teste real de "já mergeado" é `git diff --stat origin/main <galho>` estar vazio (não `git merge-base`).
3. **Honestidade de preço:** inflação de referência, fallback tratado como real, NM frouxo → sempre validar versão/condição e rotular fallback.

**Este scanner:** referência de preço = PriceCharting (valor justo raw NM + graded); listings via eBay Browse API; chaves = `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` (no PC; CI é offline).

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
3. **Só graded (2026-06-10):** PSA 9/10, BGS 9.5/10, CGC 9.5/10. Raw está
   fora do funil (`graded_only: true`). A lógica de raw NM-only segue no
   código (testada via `CFG_RAW` nos testes) caso o operador reverta — se
   reverter: raw só Near Mint, match conservador ("NM/LP" → rejeita).
4. **Entrega = tabela markdown no chat**, todas as linhas, flag por linha.
   Nunca arquivo/planilha por padrão (só se o operador pedir).
5. **Threshold deste repo é percentual INTEIRO** (`min_gross_margin_percent: 30`).
   Atenção: CT usa fração (0.30), MYP/Liga usam inteiro — aqui é inteiro,
   nomeado explicitamente para não haver pegadinha.
6. **Só vendedor com item nos EUA.** A entrega é na COMC (Algona, WA
   98001-7409, EUA — mailbox de armazenamento). Filtro `itemLocationCountry:US`
   na API + checagem no scorer. Cartas JP da watchlist = vendedores
   americanos vendendo carta japonesa, nunca vendedor no Japão.

## Como rodar

```powershell
cd C:\Users\mathe\ebay-arbitrage-scanner
.venv\Scripts\python -m pytest tests/ -q        # 65 testes
.venv\Scripts\python main.py --pricing-only     # sem credenciais (PriceCharting apenas)
.venv\Scripts\python main.py                    # scan completo (exige EBAY_CLIENT_ID/SECRET)
.venv\Scripts\python main.py --confiavel        # so vendedores >=50 avals/98%+, margem 30-60%
```

Credenciais: env vars de USUARIO Windows desde 2026-06-10 (keyset "MinhaLojaEbay").
Sessao de terminal antiga pode nao herdar -- passar inline se `ausentes`.

Venv local em `.venv` (Python 3.12). Na nuvem: `python -m venv .venv` +
`pip install -r requirements.txt`.

## Fontes de dados (ambas gratuitas)

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
