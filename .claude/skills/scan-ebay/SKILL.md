---
name: scan-ebay
description: >-
  Rodar o scan de cartas certificadas (slabs) do eBay — anúncios de preço fixo
  nos EUA comparados com vendas concluídas PSA da mesma carta no PriceCharting,
  pela política 2026-09-05.4 (bloco `slab_strategy` do config.yaml) — e entregar
  a tabela do ebay_summary.py verbatim no chat. Use SEMPRE que o operador pedir
  para rodar o scanner do eBay / "roda o eBay" / "scan eBay" / escanear a
  watchlist do eBay: antes de rodar, PERGUNTE o grupo canônico (1–12, UM por
  vez; --list-groups mostra os títulos) e os ajustes do run (--max-pages,
  --min-discount, --grades) e entregue SEMPRE a saída do ebay_summary.py
  verbatim (2 links em toda linha, todos os candidatos APROVAR / REVISAR /
  REJEITAR, funil no rodapé).
---

REGRA VIGENTE DO OPERADOR: ler DELIVERY_CHAT.md na raiz do repositório. Entrega somente no chat, preço de referência clicável, coleta nova sob demanda; não executar scans no GitHub Actions nem publicar resultados. Esta regra substitui instruções antigas conflitantes.

# Scan do eBay — pergunte, rode, entregue

O scanner compara anúncios ativos de **preço fixo** do eBay (Browse API — a API
oficial de busca; leilão nem entra na busca), **só de cartas certificadas**
(slabs: carta lacrada com nota de PSA / BGS / CGC / TAG — lista `graded_allow` no
config.yaml), com a referência da política 2026-09-05.4 (definição completa em
docs/EBAY_PSA.md):

- **Referência PSA** = mediana (valor do meio) das vendas concluídas PSA da MESMA
  carta + coleção + número + variante + idioma + nota, lidas da página da carta no
  PriceCharting (≥3 vendas em 180 dias = OK; só em 365 dias = REVISAR por baixa
  liquidez; 1–2 vendas = REVISAR). Outras certificadoras são comparadas à PSA
  ajustada (`graders` no config) e a revenda exige vendas da própria certificadora.
- **Regra econômica** = `slab_strategy.economics` do config.yaml:
  `gate_mode: profit_or_discount` — braço `min_profit_usd: 40` OU braço
  `min_discount_percent: 30`, limites estritos, `require_positive_profit: true` —
  com os custos COMC explícitos em `costs`. Nada disso é recomendação: é
  classificação técnica.
- **Carta solta (raw) não entra**: `graded_only: true` é obrigatório e a flag
  antiga de raw é rejeitada pelo `main.py` com erro.
- Vereditos = **APROVAR / REVISAR / REJEITAR**, sempre com motivos e evidências
  (vendas usadas, janela, dispersão). APROVAR é aprovação na análise; nenhuma
  compra é executada nem recomendada.

## Passo 0 — pré-requisitos

- `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` no ambiente (env vars de usuário Windows —
  keyset "MinhaLojaEbay"). Sessão de terminal antiga pode não herdar → rodar pela
  ferramenta PowerShell, que herda as variáveis do usuário. Sem chaves, o run NÃO
  consulta o eBay e NÃO grava artefato. Nunca passar chave inline nem imprimi-la.
- `watchlist.yaml` **já vem no repo** (GERADA por `build_watchlist.py` e
  versionada — decisão do operador 2026-09-03): um clone limpo roda sem preparo.
  Universo = catálogo de 123 sets (`src/catalog/set_catalog.json`, os mesmos 12
  grupos da COMC em `src/groups.py`) × 100 "chases" (`src/catalog/iconic_pokemon.csv`)
  × raridade ≥ Holo Rare × teto 30 cartas por set; `pc_url` = página exata da
  carta no PriceCharting (carta sem página fica fora; nunca se inventa URL).
  **Não editar à mão**; regenerar (`python build_watchlist.py`) só quando o
  catálogo/grupos/chases mudarem — o teste `tests/test_groups.py` falha de
  propósito se o catálogo crescer sem os grupos acompanharem.
- `python main.py --check-config` lista as pendências da política sem rede
  (código 0 = nada pendente; 2 = há pendências, que viram REVISAR nas linhas).

## Passo 1 — perguntar grupo e ajustes (AskUserQuestion) — nunca assumir

1. **Qual grupo canônico rodar (UM por vez)?** Obtenha títulos e contagens
   DINAMICAMENTE (não precisa de chaves eBay):
   ```powershell
   .venv\Scripts\python main.py --list-groups
   ```
   Os 12 grupos são os mesmos da COMC (`src/groups.py`, títulos verbatim):

   | Grupo | Título | Sets |
   |---|---|---|
   | 1 | SV recente | 7 |
   | 2 | SV restante | 6 |
   | 3 | WotC 1999-2000 | 8 |
   | 4 | WotC 2001-2003 | 7 |
   | 5 | EX 2004-2005 | 8 |
   | 6 | EX 2006-2007 + DP 2007 | 8 |
   | 7 | DP/Platinum 2008-2010 | 8 |
   | 8 | HGSS + BW 2010-2013 | 17 |
   | 9 | XY 2014-2016 | 14 |
   | 10 | SM 2017-2019 | 17 |
   | 11 | SWSH 2020-2021 | 12 |
   | 12 | SWSH 2022 + Crown Zenith | 11 |

   (1–2 = SV 2023–25; 3–4 = WotC 1999–2003; 5–10 = EX/DP/Platinum/HGSS/BW/
   XY/SM 2004–19; 11–12 = SWSH + Crown Zenith 2020–23.) `--group` aceita
   `N` | `N-M` | `1,3,10-12` | `all`; número fora de 1–12 erra alto. Apresente
   os grupos com a contagem de cartas que o `--list-groups` imprimiu. Padrão do
   operador = **um grupo por vez** (orçamento `max_ebay_calls: 500` por run e
   cota grátis da Browse API de 5.000 chamadas/dia; a watchlist inteira tem
   ~1.600 cartas).
2. **Ajustes do run** (todos opcionais; o default é a política do config):
   - `--max-pages N` — páginas de 200 anúncios por carta (default 3; os runs
     validados de #29/#30 usaram `--max-pages 1`);
   - `--min-discount N` — inteiro; altera SÓ o braço `min_discount_percent` da
     regra `profit_or_discount` daquele run (nos dois lugares do config);
   - `--min-price USD` — piso do preço do item (default `min_price_usd: 10`);
   - `--grades "PSA 10, CGC 10 Pristine"` — funil restrito a notas; nota
     desconhecida erra alto; RAW é rejeitado;
   - `--confiavel` — compatibilidade (o histórico do vendedor já é sempre
     verificado; todos os candidatos continuam visíveis).
   Orçamento: cada carta gasta 1 busca por página + até
   `max_item_details_per_card: 10` consultas de detalhe (idioma); estourar o teto
   de 500 encerra o run como parcial.

## Passo 2 — rodar (rota determinística local)

```powershell
$env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python main.py --group <N> --max-pages 1 --out results\last_scan_g<N>.json
```

- Estimar antes de rodar: cartas do grupo × (páginas + até 10 detalhes) contra
  o teto de 500 chamadas, e dizer a conta na entrega.
- `--out results\last_scan_g<N>.json` = um artefato por grupo (o run do grupo
  seguinte não sobrescreve o anterior). Sem `--group` = watchlist inteira
  (~1.600 cartas — não cabe na cota; só sob pedido explícito). `--pricing-only`
  mostra só as colunas informativas do PriceCharting (não gera artefato e não
  é evidência de venda).
- **Exit code 1 = run parcial** (`aborted: true`): o artefato vai para
  `<out>.aborted.json` e o `--out` anterior é preservado. A mensagem final diz a
  causa: parada antecipada (autenticação, cota ou API — cartas restantes NÃO
  varridas) ou erros contados no funil com todas as cartas visitadas. Entregar
  assim mesmo, dizendo que é parcial; nunca tratar como scan completo.
- Erro por carta (PriceCharting fora do ar, carta sem vendas comparáveis) NÃO
  derruba o run: conta no funil (`pc_error`, `pc_breaker`, `card_error`) e as
  linhas da carta saem em REVISAR com o motivo.

## Passo 3 — entregar (ritual FIXO, contrato do repo, não negociável)

```powershell
.venv\Scripts\python ebay_summary.py results\last_scan_g<N>.json -o results\ebay-g<N>-<AAAA-MM-DD>.md
```

(Passar `results\last_scan_g<N>.aborted.json` quando o run foi parcial.) O gerador
vigente é `src/slab_report.py` (`render`), chamado pelo `ebay_summary.py` sempre
que o JSON é da política: tabela única com todos os candidatos (Carta / Compra /
Investimento / PSA original / Comparação / Revenda / Desconto / Decisão / Links)
+ uma seção por carta com motivos, variante, idioma, custos e as vendas usadas
na referência.

1. Colar o conteúdo do `.md` **VERBATIM** no chat — **proibido** remontar
   tabela à mão, renomear/reordenar colunas ou dropar link.
2. **Todas as linhas, todos os vereditos** (APROVAR / REVISAR / REJEITAR, cada
   um com motivos). Nunca amostra. `--sensitivity` (faixas de diagnóstico) só
   vale para JSON do motor legado, anterior à política.
3. Toda linha tem os **DOIS links**: `[oferta]` (anúncio eBay) e `[referência]`
   (página da carta no PriceCharting); o preço de referência também é clicável.
   URLs vêm do JSON — nunca inventar.
4. Reportar o rodapé da ferramenta: contagem por veredito e **Funil da busca**
   (inclusive chamadas à API, erros e run parcial).
5. **Sem recomendação de compra** — vereditos são classificação técnica; capital
   é decisão do operador.

## Nota de logística (por que US-only e preço fixo são invariantes)

Compras têm **Ship To = COMC mailbox (Algona, WA 98001-7409, EUA)** — mailbox
de armazenamento do operador. Por isso o filtro `itemLocationCountry: US` da
API + o cinto de segurança no avaliador **não podem ser afrouxados**: item fora
dos EUA não serve mesmo que a diferença de preço pareça ótima. E leilão não entra
(`fixed_price_only: true`): lance atual não é preço.
