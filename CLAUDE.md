# CLAUDE.md — eBay Pokémon TCG Arbitrage Scanner

Instruções para qualquer sessão Claude (local ou nuvem) que trabalhe neste repo.

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
3. **Raw só Near Mint.** Match conservador: qualquer sinal de condição
   inferior rejeita, mesmo com "NM" presente ("NM/LP" → rejeita).
4. **Entrega = tabela markdown no chat**, todas as linhas, flag por linha.
   Nunca arquivo/planilha por padrão (só se o operador pedir).
5. **Threshold deste repo é percentual INTEIRO** (`min_gross_margin_percent: 30`).
   Atenção: CT usa fração (0.30), MYP/Liga usam inteiro — aqui é inteiro,
   nomeado explicitamente para não haver pegadinha.

## Como rodar

```powershell
cd C:\Users\mathe\ebay-arbitrage-scanner
.venv\Scripts\python -m pytest tests/ -q        # 38 testes
.venv\Scripts\python main.py --pricing-only     # sem credenciais (PriceCharting apenas)
.venv\Scripts\python main.py                    # scan completo (exige EBAY_CLIENT_ID/SECRET)
```

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

- PSA 9.5 não existe; o regex de PSA 9 usa `(?![\d.])` para não casar "9.5".
- O parser de volume do PriceCharting depende da ORDEM das células de volume
  na tabela principal (mesma ordem das colunas de preço).
- Sinal "+" da tendência vem como `&#43;` no HTML.
- Fixture de teste: `tests/fixtures/pc_charizard_base.html` (página real).
