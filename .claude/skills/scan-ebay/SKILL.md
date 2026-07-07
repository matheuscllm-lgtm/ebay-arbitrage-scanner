---
name: scan-ebay
description: >-
  Rodar o scan de arbitragem do eBay (anúncios eBay vs referência
  PriceCharting/TCGplayer) e entregar via ebay_summary.py. Use SEMPRE que o
  operador pedir para rodar o scanner do eBay / "roda o eBay" / "scan eBay" /
  escanear a watchlist do eBay: antes de rodar, PERGUNTE o escopo (qual grupo
  da watchlist e qual funil — graded-only default, raw NM via --include-raw,
  ou --confiavel) e entregue SEMPRE a saída do ebay_summary.py verbatim
  (2 links em toda linha, todos os buckets).
---

# Scan do eBay — pergunte, rode, entregue

O scanner compara anúncios ativos do eBay (Browse API) com o preço justo:
**graded** (PSA 9/10, BGS 9.5/10, CGC 9.5/10) contra PriceCharting por grade;
**raw NM** (opt-in por run) contra o **market do TCGplayer** (via tcgcsv.com),
com PriceCharting como cross-check rotulado.

## Passo 1 — SEMPRE perguntar o escopo (AskUserQuestion)

Ao ser invocado, **pergunte ao operador** — nunca assuma:

1. **Qual grupo da watchlist rodar?** Obtenha as opções DINAMICAMENTE (não
   precisa de chaves eBay):
   ```powershell
   .venv\Scripts\python main.py --list-groups
   ```
   Apresente os grupos com a contagem de cartas + a opção "todas as cartas"
   (sem `--group`).
2. **Qual funil?**
   - **graded-only** (default do config — decisão de escopo do operador);
   - **incluir raw NM** (`--include-raw` — reversão sancionada POR RUN, não
     mexe no config);
   - **modo confiável** (`--confiavel` — só vendedores ≥50 avaliações/≥98%,
     margem 30–60%, tabela 100% acionável).

## Passo 2 — rodar (rota determinística local)

```powershell
$env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python main.py --group <g> [--include-raw] [--confiavel] --out results\last_scan.json
```

- Exige `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` no ambiente (já persistidas
  como env vars de usuário Windows — keyset "MinhaLojaEbay"; sessão de
  terminal antiga pode não herdar → passar inline se "ausentes").
- Sem `--group` = watchlist inteira. `--pricing-only` não gera artefato JSON
  (não há anúncios avaliados).
- Threshold do repo é percentual INTEIRO (`min_gross_margin_percent: 30`).

## Passo 3 — entregar (ritual FIXO, contrato do repo, não negociável)

```powershell
.venv\Scripts\python ebay_summary.py results\last_scan.json -o results\ebay-<AAAA-MM-DD>.md
```

1. Colar o conteúdo do `.md` **VERBATIM** no chat — **proibido** remontar
   tabela à mão, renomear/reordenar colunas ou dropar o link de referência.
2. **Todos os buckets** (🟢 OPORTUNIDADE / ⚠️ REVISAR / 🚨 SUSPEITO /
   ⛔ REJEITADO com motivo), todas as linhas — nunca amostra.
3. Toda linha tem os **DOIS links**: `[oferta]` (anúncio eBay) e
   `[TCG]`/`[ref]` (referência de preço). URLs vêm do JSON — nunca inventar.
4. Reportar a linha "Cobertura de referência" (graded PC · raw TCG real ·
   raw só PC · sem referência).
5. **Sem recomendação de compra** — vereditos são classificação técnica;
   capital é decisão do operador.

## Nota de logística (por que US-only é invariante)

Compras têm **Ship To = COMC mailbox (Algona, WA 98001-7409, EUA)** — mailbox
de armazenamento do operador. Por isso o filtro `itemLocationCountry: US` da
API + o cinto de segurança no scorer **não podem ser afrouxados**: item fora
dos EUA não serve mesmo que a margem pareça ótima.
