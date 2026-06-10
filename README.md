# eBay Pokémon TCG Arbitrage Scanner

**Versão: v0.1**

Scanner que procura cartas Pokémon **subvalorizadas no eBay** — tanto cartas
soltas ("raw") quanto cartas avaliadas por empresas de grading (PSA 10, PSA 9,
BGS 9.5/10, CGC 9.5/10) — comparando o preço pedido com o **preço justo de
mercado** (o que as cartas realmente vendem, segundo o histórico de vendas
concluídas do próprio eBay).

Projeto **independente** dos outros scanners (CardTrader, MYP, Liga, sealed,
PSA). Custo de operação: **zero** — nenhuma assinatura paga.

> **O scanner não decide compra.** Ele pontua e classifica tecnicamente
> (OPORTUNIDADE / REVISAR / SUSPEITO / REJEITADO). Quem decide o capital é o
> operador. O método completo está em [METODO.md](METODO.md).

## Como funciona (visão geral)

1. **Watchlist** (`watchlist.yaml`): a lista de cartas que o scanner vigia.
   Cada carta aponta para sua página exata no PriceCharting — isso garante
   precisão (nada de adivinhar qual carta é a partir do título do anúncio).
2. **Preço justo** (grátis): o PriceCharting agrega as vendas concluídas do
   eBay e publica o preço por grade (raw, PSA 9, PSA 10, BGS, CGC...), a
   variação recente (tendência) e o volume de vendas (liquidez = facilidade
   de revender).
3. **Anúncios ativos** (grátis): a API oficial do eBay (Browse API) devolve
   o que está à venda agora, com preço, frete, vendedor e condição.
4. **Avaliação**: cada anúncio é comparado ao preço justo da grade detectada
   no título. Margem bruta ≥ 30% entra na tabela; flags de risco acompanham
   cada linha.

## Escopo fixo

- Apenas Pokémon TCG (categoria 183454 do eBay — cartas avulsas de TCG).
- Grades aceitas: raw (somente Near Mint), PSA 10, PSA 9, BGS 9.5/10,
  CGC 9.5/10. Qualquer outra grade/empresa é rejeitada.
- Idiomas: inglês (EN) e japonês (JP). Outros idiomas são rejeitados.
- Piso de preço: USD 10 (~R$50). Margem mínima: 30% **bruta** (sem nenhuma
  taxa embutida — frete, taxas de importação e câmbio o operador calcula por
  fora; o frete aparece em coluna separada, informativo).

## Como rodar

```powershell
cd C:\Users\mathe\ebay-arbitrage-scanner
.venv\Scripts\python main.py                  # scan completo (precisa das chaves eBay)
.venv\Scripts\python main.py --pricing-only   # só preço justo (funciona sem chave nenhuma)
```

A entrega do resultado é **tabela markdown no chat** (todas as linhas, com flag
por linha). O CSV em `data/last_scan.csv` é só registro local.

## Chaves do eBay (uma vez, grátis, ~5 minutos)

A única configuração necessária para o scan completo:

1. Entre em <https://developer.ebay.com> e crie uma conta de desenvolvedor
   (pode usar sua conta eBay normal; é gratuito).
2. No painel, abra **Application Keys** e crie um keyset de **Production**.
3. Anote o **App ID (Client ID)** e o **Cert ID (Client Secret)**.
4. No Windows, defina as variáveis de ambiente do usuário:
   - `EBAY_CLIENT_ID` = App ID
   - `EBAY_CLIENT_SECRET` = Cert ID

O limite gratuito é 5.000 chamadas/dia — um scan da watchlist usa ~4 chamadas
por carta, então sobra folga enorme.

## Estrutura

| Arquivo | O que faz |
|---|---|
| `main.py` | linha de comando (CLI) |
| `watchlist.yaml` | cartas vigiadas |
| `config.yaml` | thresholds (margem 30 = 30%, **percentual inteiro**) |
| `src/pricecharting.py` | preço justo, tendência e liquidez (scrape público com cache 24h) |
| `src/ebay_api.py` | anúncios ativos (Browse API oficial) |
| `src/title_parser.py` | detecta grade, idioma, condição NM e riscos no título |
| `src/scorer.py` | o método: margem, liquidez, tendência, risco → score e veredito |
| `src/report.py` | tabela markdown (entrega) + CSV (registro) |
| `METODO.md` | o método de avaliação explicado por extenso |

## Testes

```powershell
.venv\Scripts\python -m pytest tests/ -q
```

38 testes cobrindo parser de título (grades, NM, idioma, riscos), scoring e
parsing do PriceCharting (com página real salva como fixture).
