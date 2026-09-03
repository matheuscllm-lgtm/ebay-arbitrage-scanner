# CLAUDE.md — ebay-arbitrage-scanner

Instruções para qualquer sessão Claude Code (local ou nuvem) que trabalhe neste repo.

Scanner de oportunidades em cartas Pokémon no eBay, no **padrão COMC** (mesmo
método do scanner irmão `scanner-comc`, decisão do operador 2026-09-03):
compara anúncios ativos de **preço fixo** com uma referência de preço honesta e
entrega tabela com **Desconto% / ROI bruto% / Spread$**. Escopo default =
**slabs** (carta lacrada em cápsula por uma certificadora, com nota): PSA 8/9/10,
CGC 9/9.5/10 Gem Mint/10 Pristine, BGS 9/9.5/10/10 Black Label, SGC 9/9.5/10,
TAG 9.5/10. Carta **raw** (solta, sem nota) só entra por run com `--include-raw`.
Projeto independente dos scanners irmãos (CardTrader, MYP, Liga, sealed, PSA
Arbitrage, COMC) — não compartilha código com eles (o `src/pc_sales.py`, o
`src/grading.py` e o `src/groups.py` foram **portados** da COMC, não importados).

> **Linguagem acessível (regra permanente do operador, 2026-09-02):** todo termo
> técnico aqui e no chat vem com explicação curta. Mini-glossário do repo:
> **slab** = carta gradada (lacrada com nota); **raw** = carta solta;
> **NM / LP** = Near Mint (quase perfeita) / Lightly Played (leve desgaste);
> **referência** = preço "justo" com que comparamos o anúncio; **mediana** =
> valor do meio de uma lista ordenada (ignora um outlier caro ou barato);
> **gate** = filtro que decide se o anúncio vira linha na entrega;
> **funil** = contagem de para onde foi cada anúncio (visto → descartado por X →
> virou linha); **Browse API** = a API oficial de busca do eBay; **paginação** =
> pedir a busca em várias páginas de 200 itens; **dedupe** = remover
> duplicados; **breaker** ("disjuntor") = após N falhas seguidas de uma fonte,
> parar de chamá-la no run; **allowlist** = lista do que é aceito;
> **fixture** = arquivo real salvo em `tests/fixtures/` para testar offline;
> **opt-in** = só liga se pedir explicitamente; **watchlist** = lista de
> cartas-alvo que o scan varre (`watchlist.yaml`); **catálogo** = os 123 sets
> validados em `src/catalog/set_catalog.json`; **chase** = carta cobiçada de um
> Pokémon popular (os 100 de `src/catalog/iconic_pokemon.csv`, com `rank`);
> **grupo canônico** = fatia numerada 1–12 do catálogo (a mesma divisão da COMC).

## 🛰️ Convenções da frota (cross-scanner)

> **Manual completo** (repo privado): https://github.com/matheuscllm-lgtm/scanners-commons — erros comuns, referências de preço, chaves, GitHub Actions e modelo de entrega de TODOS os scanners. Cópia-mestra local (PC do operador): `C:\Users\mathe\scanners-commons\`.

Invariantes que valem para TODOS os scanners:

- **Margem BRUTA** — só `(revenda − compra)/base`, sem nenhuma taxa embutida (frete, cartão, IOF — o operador calcula por fora). A frota usa piso 30% de margem; **neste scanner o gate é Desconto% ≥ 20** (padrão COMC — divergência declarada, ver Regra 2).
- **Piso de relevância R$50 (~US$10) — SÓ para cartas avulsas (singles).** Produtos SELADOS não têm piso (decisão do operador, 2026-06-27).
- **Só Near Mint** para raw — condição por match EXATO, nunca substring (já vazou SP). Neste scanner o raw **LP explícito** também entra, mas com a SUA referência (vendas LP), nunca comparado ao preço NM (ver Regra 3).
- **Nunca inventar preço** — fonte falhou → marca fallback/erro e segue; jamais fabrica número.
- **Nunca recomendar compra** — o scanner reporta métricas, flags e fontes; a decisão de capital é do operador.
- **Entrega = tabela markdown no chat** (nunca XLSX/CSV por padrão), gerada pela ferramenta do repo — nunca montada à mão —, mostrando TODAS as linhas (aprovadas + rejeitadas). Coluna `Carta` = nome + número; coluna `Links` combinada = `[oferta](url) · [referência](url)`.
- ⚠️ **Convenção de threshold:** percentual inteiro (`20`) = MYP, Liga, eBay, COMC; fração (`0.30`) = CardTrader, Selados.

Erros recorrentes (3 famílias — detalhe no manual):

1. **Segredo/ambiente:** BOM/zero-width numa chave → crash latin-1 no header → scan "verde mas vazio". Setar sem BOM (`printf '%s' 'KEY' | gh secret set`) **e** sanitizar ao ler no código (`.strip()` NÃO tira BOM).
2. **Git:** branch ou `main` local defasado por squash-merge PARECE pendência. O teste real de "já mergeado" é `git diff --stat origin/main <branch>` estar vazio (não `git merge-base`).
3. **Honestidade de preço:** inflação de referência, fallback tratado como real, NM frouxo → sempre validar versão/condição e rotular fallback.

**Este scanner — referência de preço em 3 trilhos (fonte da verdade: `src/scorer.py`):**

- **Slab** = **mediana de vendas concluídas** (vendas reais já fechadas no eBay,
  agregadas pelo PriceCharting) da MESMA carta + variante + certificadora + nota +
  subcategoria (`src/pc_sales.py`, portado da COMC). ≥3 vendas em 180 dias = OK;
  ≥3 só em 365 dias = OK com nota `baixa-liquidez(365d)`; 1–2 vendas = REVISAR
  `vendas<3(n=…)`; 0 = sem referência (a carta não vira linha; conta no funil).
  As **colunas** de preço do PriceCharting e os buckets genéricos "Grade 9"/
  "Grade 9.5" (que misturam certificadoras) **NUNCA** são referência — a coluna
  exata da nota é só sanidade (`coluna÷vendas` quando fica >30% longe da mediana).
- **Raw NM** (opt-in `--include-raw`) = **TCGplayer market via tcgcsv.com**
  (`src/tcg_reference.py`, mesma fonte real do MYP v5.15+); PriceCharting
  Ungraded é cross-check (divergência >40% = flag + REVISAR) e fallback
  **rotulado** (`PC Ungraded (sem TCG)`) quando o tcgcsv não cobre a carta ou
  quando ela não é EN (o catálogo do tcgcsv é inglês; carta JP nunca ganha
  referência TCG — PR #19).
- **Raw LP** (opt-in, junto com `--include-raw`) = mediana de ≥3 vendas LP
  **explícitas** no PriceCharting; só entra com LP explícito no título ou no
  campo de condição do eBay, e só depois do pré-filtro
  `preço ≤ ref NM × (1 − desconto mínimo)`. Nunca LP vs NM.

Listings via eBay Browse API; chaves que o CÓDIGO lê = `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` (`src/ebay_api.py`; marketplace `EBAY_US` e scope OAuth são hardcoded). `EBAY_DEV_ID`/`EBAY_ENV`/`EBAY_MARKETPLACE_ID`/`EBAY_SCOPE` existem como secrets do repo (Actions+Codespaces) mas não são consumidas por nenhum arquivo. CI é offline e não usa secret.

> **Reconciliação NM × graded-only (não há contradição):** o invariante "Só Near
> Mint" da frota vale para o caminho **RAW** deste scanner — que está **fora do
> funil por default** desde 2026-06-10 (`graded_only: true`), mas segue vivo e
> testado no código e é ligado por run com `--include-raw`. No caminho raw: NM
> explícito → referência TCGplayer market; LP explícito → referência própria
> (vendas LP); "NM/LP", condição ausente ou pior que LP → fora (contado no funil
> como `skip_condition`, não vira linha REJEITADO). Detalhe na Regra 3.

## Regras invioláveis deste repo (herdadas do operador, cross-scanner)

1. **Nunca recomendar compra.** O agente é técnico (código/auditoria/dados);
   capital é decisão do operador. Vereditos são classificação técnica
   (OPORTUNIDADE / REVISAR / SUSPEITO / REJEITADO — ver `src/scorer.py`).
2. **Gate = Desconto%, padrão COMC (operador, 2026-09-03).** Três métricas,
   nomeadas assim e só assim — **nunca "lucro"**:
   - **Desconto%** = `(referência − preço eBay) / referência` → é o **gate**
     (`min_discount_percent: 20` no `config.yaml`; `--min-discount N` por run;
     diagnóstico do operador = 10).
   - **ROI bruto%** = `(referência − preço) / preço` → coluna (retorno bruto sobre
     o capital); acima de `suspicious_margin_percent: 60` vira SUSPEITO.
   - **Spread$** = `referência − preço` → diferença bruta em dólar, sem taxa
     nenhuma (frete à parte).
   Piso USD 10 (`min_price_usd: 10.0`; `--min-price` por run). O antigo
   `min_gross_margin_percent` (gate por ROI bruto, 15% desde 2026-09-01) **deixou
   de ser gate**: `main.py` avisa alto se o config ainda tiver a chave e usa o
   default 20% de desconto — nunca converte em silêncio.
3. **Só slab por default (2026-06-10), allowlist explícita (2026-09-03):**
   PSA 8/9/10, CGC 9/9.5/10 Gem Mint/10 Pristine, BGS 9/9.5/10/10 Black Label,
   SGC 9/9.5/10, TAG 9.5/10 (`graded_allow` no config; chaves em
   `src/grading.py`). Referência de slab = mediana de vendas concluídas da MESMA
   carta+variante+certificadora+nota+subcategoria (nota vizinha, coluna do
   PriceCharting ou bucket genérico NUNCA são proxy). Regras de título: CGC 10
   sem "Pristine" = Gem Mint; título com mais de uma nota = ambíguo = funil;
   certificadora desconhecida (ACE/MNT/GMA…) = funil. Raw está fora do funil
   default (`graded_only: true` — decisão de escopo do operador, não mexer); a
   reversão SANCIONADA é por run: `python main.py --include-raw` (NM = TCG
   market; LP explícito = mediana de vendas LP; nunca LP vs NM; "NM/LP" = fora).
4. **Entrega = tabela markdown no chat**, todas as linhas (todos os buckets,
   inclusive REJEITADO com motivo), flag por linha, **gerada pelo
   `ebay_summary.py`** e colada VERBATIM (ver seção 📤 abaixo). Nunca
   arquivo/planilha por padrão (só se o operador pedir).
5. **Threshold deste repo é percentual INTEIRO** (`min_discount_percent: 20`
   em `config.yaml`, desde 2026-09-03; `--min-discount 10` = 10%). Atenção: CT
   usa fração (0.30), MYP/Liga/COMC usam inteiro — aqui é inteiro, nomeado
   explicitamente para não haver pegadinha.
6. **Só vendedor com item nos EUA.** A entrega é na COMC (Algona, WA
   98001-7409, EUA — mailbox de armazenamento). Filtro `itemLocationCountry:US`
   na API + checagem-cinto-de-segurança no scorer
   (`required_location_country: US`). Cartas JP da watchlist = vendedores
   americanos vendendo carta japonesa, nunca vendedor no Japão.
7. **Só preço fixo (operador, 2026-09-03).** Lance atual de leilão não é preço.
   `fixed_price_only: true` no config → o filtro `buyingOptions:{FIXED_PRICE}`
   já vai na busca da Browse API (leilão nem entra), e o scorer ainda conta
   qualquer leilão que escape como `skip_not_fixed_price` no funil.

## Como rodar

> 🎯 **Skill `scan-ebay`** (`.claude/skills/scan-ebay/SKILL.md`): quando o
> operador pedir pra "rodar o eBay", PERGUNTE o grupo canônico (1–12, UM por
> vez; `--list-groups` mostra o título de cada um) e o
> modo: **comercial** = `--group <N> --min-discount 20` (default do config)
> ou **diagnóstico** = `--group <N> --min-price 5 --min-discount 10
> --include-raw` + entrega com `--sensitivity 10,15,20`. Entrega SEMPRE via
> `ebay_summary.py` — verbatim.

**Setup (1ª vez, qualquer ambiente):** só o venv. A `watchlist.yaml` é
**GERADA** por `build_watchlist.py` e **VERSIONADA** no repo (decisão do
operador 2026-09-03; deixou de ser gitignored) — um clone limpo já roda.

```bash
python -m venv .venv    # PC do operador: Python 3.12
# Windows: .venv\Scripts\python -m pip install -r requirements.txt
# Linux/nuvem: source .venv/bin/activate && pip install -r requirements.txt
```

**Watchlist gerada (PR B, 2026-09-03):** `python build_watchlist.py` monta a
lista de cartas-alvo a partir do catálogo, sem nada digitado à mão:

- **Universo** = catálogo de **123 sets** (`src/catalog/set_catalog.json`, nomes
  do tcgcsv) dividido nos **mesmos 12 grupos da COMC** (`src/groups.py`) ×
  **100 "chases"** (`src/catalog/iconic_pokemon.csv` — Pokémon mais cobiçados,
  com `rank` de popularidade) × **raridade ≥ Holo Rare** (campo `Rarity` do
  tcgcsv; lista `RARITY_ALLOW` no script — Rare não-holo, Common/Uncommon e
  Code Card ficam fora) × **teto `--cap 30`** cartas por set (as mais caras
  pelo market do TCGplayer).
- **`pc_url`** (página da carta no PriceCharting = referência de vendas) é
  resolvida por nome+número+set com o **mesmo matcher exato** do scan
  (`pc_sales.product_page_url`). **Carta sem página no PriceCharting NÃO
  entra** (sem referência possível) e sai listada no relatório do script
  (`sem PC: …`) — **nunca se inventa URL**. 5 erros seguidos do PriceCharting
  abrem o breaker (`ERRO PC: … breaker`) e o restante fica de fora → regenerar.
- Flags: `--groups all|3|5-8|1,3,10-12` (default `all`), `--cap N` (default
  30; 0 = sem teto), `--out` (default `watchlist.yaml`), `--no-pc` (só
  catálogo, `pc_url` vazio — o scan NÃO roda com ela; serve para inspecionar
  candidatas), `--pc-cache-dir` (cache das páginas do PriceCharting entre
  execuções).
- Tamanho medido pelo operador (2026-09-03, `--cap 30`, todos os grupos):
  **~1.600 cartas**. O relatório final do script imprime o total real, por
  grupo, quantas ficaram sem página PC, sets no teto e sets sem grupo no tcgcsv.
- **Quando regenerar:** só quando catálogo, grupos ou chases mudarem (ou para
  refazer `pc_url`). Editar `watchlist.yaml` à mão é proibido (o cabeçalho do
  arquivo avisa); regenere e versione junto no PR.
- Lista alternativa feita à mão (teste, carta avulsa): use
  `watchlist.example.yaml` como modelo e passe `--watchlist <arquivo>`.

**Dia a dia (PC do operador, PowerShell):**

```powershell
cd C:\Users\mathe\ebay-arbitrage-scanner
$env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python -m pytest tests/ -q        # 459 testes, offline
.venv\Scripts\python main.py --list-groups      # grupos c/ título e contagem (sem chaves)
.venv\Scripts\python main.py --pricing-only     # sem credenciais (só PriceCharting)

# Run COMERCIAL (gate 20% de desconto = default do config), UM grupo por vez:
.venv\Scripts\python main.py --group <N> --min-discount 20 --out results\last_scan_g<N>.json

# Run DIAGNÓSTICO (operador 2026-09-03, padrão COMC): piso US$5, gate 10%, raw incluído,
# um grupo por vez, artefato nomeado pelo grupo (não sobrescreve o run anterior)
.venv\Scripts\python main.py --group <N> --min-price 5 --min-discount 10 --include-raw --out results\last_scan_g<N>.json

.venv\Scripts\python main.py --grades "PSA 10, CGC 10 Pristine"   # funil restrito a notas
.venv\Scripts\python main.py --confiavel        # só vendedores >=50 avals/98%+, sem SUSPEITO/REJEITADO
```

Na nuvem/Linux, os mesmos comandos com `python`/`.venv/bin/python`.

**Por que um grupo por vez:** a cota grátis da Browse API é **5.000
chamadas/dia** e cada carta gasta **~1–3 chamadas** (1 busca paginada, até
`max_pages` 3 páginas de 200 anúncios). Com ~1.600 cartas, a watchlist inteira
não cabe com folga num dia; rodar `--group <N>` (6 a 17 sets por grupo) mantém
o run dentro da cota e o funil da entrega mostra "Chamadas à Browse API".

**Grupos canônicos (12, os mesmos da COMC — `src/groups.py`; títulos verbatim,
`era` = campo do código):**

| Grupo | Título | era | Sets |
|---|---|---|---|
| 1 | SV recente | recent | 7 |
| 2 | SV restante | recent | 6 |
| 3 | WotC 1999-2000 | vintage | 8 |
| 4 | WotC 2001-2003 | vintage | 7 |
| 5 | EX 2004-2005 | middle | 8 |
| 6 | EX 2006-2007 + DP 2007 | middle | 8 |
| 7 | DP/Platinum 2008-2010 | middle | 8 |
| 8 | HGSS + BW 2010-2013 | middle | 17 |
| 9 | XY 2014-2016 | middle | 14 |
| 10 | SM 2017-2019 | middle | 17 |
| 11 | SWSH 2020-2021 | recent | 12 |
| 12 | SWSH 2022 + Crown Zenith | recent | 11 |

Faixas: 1–2 = SV (2023–2025); 3–4 = WotC (1999–2003); 5–10 = EX / DP /
Platinum / HGSS / BW / XY / SM (2004–2019); 11–12 = SWSH + Crown Zenith
(2020–2023). **Invariante travado por `tests/test_groups.py`:** a união dos 12
grupos é EXATAMENTE o catálogo (123 sets), sem sobreposição. Catálogo novo →
o teste FALHA de propósito → atualizar `src/groups.py`, regenerar
`watchlist.yaml` e atualizar a skill `scan-ebay`.

O scan grava um **artefato JSON** (`--out`, default `results/last_scan.json`,
gitignored) com TODAS as linhas avaliadas (inclusive REJEITADO), o funil e os
parâmetros do run. ⚠️ **Run degradado não grava artefato** (PR #19): se as
chaves eBay faltarem, o scan vira pricing-only, avisa alto e **preserva** o
`last_scan.json` do último scan real. ⚠️ **Run abortado** (falha de
autenticação no eBay ou 3 erros seguidos da Browse API): grava o artefato
marcado `aborted: true`, avisa alto e sai com **exit code 1** — a entrega mostra
"RUN ABORTADO" e as cartas restantes NÃO foram varridas (scan parcial nunca
passa por completo). A **entrega** sai do artefato:

```powershell
# comercial (4 buckets por veredito)
.venv\Scripts\python ebay_summary.py results\last_scan_g<N>.json -o results\ebay-g<N>-<AAAA-MM-DD>.md
# diagnóstico (faixas por limiar de desconto; só a faixa >=20% é candidato comercial)
.venv\Scripts\python ebay_summary.py results\last_scan_g<N>.json -o results\ebay-g<N>-<AAAA-MM-DD>.md --sensitivity 10,15,20
```

**Flags do CLI (`main.py`; `--help` é a fonte da verdade):**

- `--watchlist` (default `watchlist.yaml`) — watchlist alternativa.
- `--config` (default `config.yaml`) — configuração alternativa.
- `--list-groups` — lista os grupos da watchlist com contagem e, para grupo
  canônico, o título (`3 — WotC 1999-2000: <n> carta(s)`) e sai; sem chaves.
- `--group <spec>` — roda só as cartas do(s) grupo(s). Aceita a spec numérica
  dos grupos canônicos `N` | `N-M` | `1,3,10-12` | `all`
  (`src/groups.py` `parse_group_arg`; grupo fora de 1–12 erra ALTO — typo
  nunca vira scan vazio) **ou** o nome literal do campo `group:` (watchlist
  alternativa feita à mão).
- `--min-discount N` — Desconto% mínimo (INTEIRO) deste run; sobrescreve
  `min_discount_percent` (diagnóstico: 10).
- `--min-price USD` — piso de preço deste run; sobrescreve `min_price_usd`
  (diagnóstico: 5).
- `--max-pages N` — páginas de 200 anúncios por busca na Browse API (default
  3 = até 600 anúncios por carta).
- `--include-raw` — inclui cartas soltas NESTE run (NM = TCGplayer market via
  tcgcsv; LP explícito = mediana de ≥3 vendas LP); sem a flag, raw fica fora
  (`graded_only: true`). Não altera o config.
- `--grades "PSA 10, CGC 10 Pristine, BGS 10 Black"` — restringe o funil DESTE
  run a notas específicas (aceita grafia informal: `psa10` = `PSA 10`). Nota
  conhecida fora da lista sai do funil em silêncio (`skip_grade_filtered` —
  escopo, não rejeição); nota desconhecida ou fora da allowlist erra ALTO
  (typo não vira scan vazio). `RAW` na lista só tem efeito com `--include-raw`.
  O cabeçalho da entrega declara o funil restrito.
- `--pricing-only` — só referência da watchlist (PriceCharting); não consulta
  o eBay, não precisa de credencial. Sem credenciais configuradas, o scan
  completo cai neste modo sozinho, com aviso.
- `--confiavel` — modo confiável: só vendedores com histórico
  (`trusted_min_feedback: 50` avaliações e `trusted_min_feedback_pct: 98.0`)
  e ROI bruto abaixo do teto de suspeita (`suspicious_margin_percent: 60`);
  nenhuma linha SUSPEITO/REJEITADO — tabela 100% acionável. Decisão do
  operador 2026-06-10: 50/98 em vez de 100/99 (golpista tem 0–9 avals; 96%
  foi avaliado e rejeitado).
- `--out` (default `results/last_scan.json`) — artefato JSON de onde a entrega
  (`ebay_summary.py`) é gerada.
- `--csv` (default `data/last_scan.csv`) — CSV de registro local (não é entrega).

**Credenciais:** env vars de USUÁRIO Windows desde 2026-06-10 (keyset
"MinhaLojaEbay" em developer.ebay.com). Sessão de terminal antiga pode não
herdar — passar inline se aparecerem como ausentes. O código sanitiza
BOM/zero-width ao ler (`_clean_secret` em `src/ebay_api.py`) — defesa contra o
erro recorrente nº 1 da frota.

**Skill `/auto`** (`.claude/commands/auto.md`): agente master autônomo da
frota, sincronizado entre os repos — modo de execução ponta a ponta quando o
operador o invoca.

## 📤 Entrega de resultados — via `ebay_summary.py`, NUNCA tabela à mão (MANDATÓRIO)

**Um caminho só** (mesmo contrato do MYP/`myp_summary.py` e da COMC/
`comc_summary.py`): rode `ebay_summary.py` sobre o JSON do scan e **cole o
markdown VERBATIM** no chat. Proibido remontar/reformatar a tabela,
renomear/reordenar colunas ou dropar o link de referência "pra economizar
largura". Nunca arquivo/planilha por padrão (só se o operador pedir
explicitamente); o CSV (`data/last_scan.csv`) é registro local, não entrega.

O que a ferramenta gera (e você entrega assim, sem mexer):

- **Cabeçalho** com data, nº de cartas + grupo + modos do run (`--grades`,
  `--include-raw`, `--confiavel`), a linha **"Parâmetros"** (desconto mínimo,
  piso, só preço fixo, só EUA, slabs aceitos), contagem por veredito, a linha
  **"Cobertura de referência"** (`X slabs (mediana de vendas PC) · Y raw NM c/
  TCGplayer market · Z raw LP (vendas LP PC) · W raw só PriceCharting (fallback
  rotulado) · N sem referência` — honestidade de fonte; só conta linhas cuja
  métrica USOU uma referência) e a linha **"Funil"** (todos os contadores >0,
  rótulos em `src/report.py` `FUNNEL_LABELS`: chamadas à API, analisados,
  duplicados, ignorados por leilão/piso/país/carta errada/raw/nota, sem
  referência, erro/breaker do PriceCharting, abaixo do desconto, linhas por
  veredito, erro por carta, `RUN ABORTADO`). Nada some em silêncio.
- **Layout COMC.** Tabela principal (OPORTUNIDADE / REVISAR / SUSPEITO):
  `# | Desconto% | ROI bruto% | eBay$ | Ref$ | Spread$ | Pokémon | Carta | Set |
  Tipo | Ref | Vend | Status | Links | Flags`. `Tipo` = `PSA 10` / `CGC 10 Gem
  Mint` / `Raw NM` / `Raw LP`; `Ref` = fonte USADA no preço (`PC vendas PSA 10
  (n=5, 2026-03..2026-08)`, `TCG market`, `PC Ungraded (sem TCG)`); `Vend` =
  confiança do vendedor/anúncio 0–100 (separada da margem); `Status` =
  `<veredito> · <motivos> · <notas>` (`vendas<3(n=…)`, `coluna÷vendas(c)`,
  `ref-desalinhada(x)`, `ref-divergente`, `baixa-liquidez(365d)`).
  **REJEITADO** sai em tabela própria: `# | Carta | Tipo | eBay$ | Motivo | Links`.
- **Ranking** (todas as tabelas): maior ROI bruto → maior Desconto% → maior
  Spread$ → Pokémon mais popular (`pokemon_rank` menor = mais alto na lista
  dos 100 chases; sem rank = 9999).
- **Modo comercial** (sem `--sensitivity`): 4 seções, SEMPRE todas as linhas —
  🟢 OPORTUNIDADE · ⚠️ REVISAR (validar manualmente) · 🚨 SUSPEITO (ROI alto
  demais — validar) · ⛔ REJEITADO (com motivo).
- **Modo diagnóstico** (`--sensitivity 10,15,20`, padrão COMC): o MAIOR limiar
  é o operacional — faixa **≥20% = candidato comercial** (OPORTUNIDADE, e
  REVISAR/SUSPEITO em seção própria); faixas **15–19,99%** e **10–14,99%** são
  **só diagnóstico, NÃO são oportunidade** (título da seção já diz isso), com
  TODAS as linhas e status na coluna; mais uma **tabela de contagens por
  limiar** (`| Limiar | OPORTUNIDADE | REVISAR/SUSPEITO | Total |`) e REJEITADO
  de todas as faixas no fim. Se o scan rodou com desconto mínimo maior que o
  menor limiar, a ferramenta avisa que as faixas de baixo ficam vazias por
  construção.
- Coluna `Carta` = nome + número; coluna `Links` = `[oferta](url_eBay) ·
  [referência](url_PriceCharting)` — o link `[referência]` é a **página da
  carta no PriceCharting SEMPRE que existir**, também para raw cuja métrica
  veio do TCGplayer (a página tem vendas, gráfico, PSA 10/9 — mais informativa;
  a coluna `Ref` diz qual preço foi usado). `[TCG](url_TCGplayer)` só quando
  não há página PC. **Os dois links em TODA linha de TODO bucket**; URLs lidas
  do JSON, nunca inventadas — se faltar uma URL, a célula mostra só o link que
  existe.
- Rodapé fixo explicando status, métricas e ranking; **nunca recomendação de
  compra**.

A formatação canônica vive em `src/report.py` (`TABLE_COLS`, `REJECTED_COLS`,
`FUNNEL_LABELS`, `compute_metrics`, `sort_key`, `links_cell`, `carta_label`,
`status_cell`, `ref_label_cell`, `escape_md`) e é consumida por
`ebay_summary.py` — fonte única, não duplicar formato.

## Fontes de dados (todas gratuitas)

- **PriceCharting — vendas concluídas** (`src/pc_sales.py`, portado de
  `scanner-comc/comc_scanner/pricecharting_client.py` @ dd952ba): UMA página
  pública por carta (`pc_url` da watchlist), com cache **do dia** em
  `data/cache/pc/<AAAA-MM-DD>/` (o operador exige dado de hoje; o cache só
  evita repetir a mesma carta dentro do run). Da página saem (a) as tabelas
  `completed-auctions-*` (vendas: data, título, preço) → `comparable_sales`
  (mesma certificadora+nota+qualificador+variante; `variant_tokens`: reverse,
  1st, shadowless, staff, prerelease, cosmos, error, signed, promo — e os NÃO
  comparáveis metal/classic/jumbo/custom) e `lp_sales` (LP explícito, sem nota,
  sem outra condição) → `sales_reference` (mediana das 10 vendas mais recentes
  da janela; ≥3/180 d = `ok`, ≥3/365 d = `low`, 1–2 = `thin` só para slab);
  (b) a tabela "Full Price Guide" (`parse_grade_prices`) — colunas exatas
  (`PSA 10`, `BGS 10 Black`, `CGC 10 Pristine`…) só como sanidade
  `column_price`. Rede/bloqueio/página sem tabela → `PcError` (contado como
  `pc_error`, distinto de "sem venda"); retry 3× em 429/5xx/rede (backoff 2s/4s
  — caso real 2026-09-01: handshake TLS pendurado derrubou uma carta); página de
  bloqueio nunca é cacheada. **Breaker:** 5 falhas seguidas suspendem a fonte
  no run (`pc_breaker`) em vez de martelar o site. Também resolve URL da carta
  por nome+número+set pela busca do site (`product_page_url` — fixture
  `pc_search_charizard_ex_151.html`; guarda de set bidirecional, sem chute).
- **PriceCharting — colunas** (`src/pricecharting.py`): lê a mesma página
  (tabela principal com ids herdados de videogame: `used_price`=RAW,
  `complete_price`=Grade 7, `new_price`=Grade 8, `graded_price`=Grade 9,
  `box_only_price`=Grade 9.5, `manual_only_price`=PSA 10; BGS/CGC/SGC/TAG na
  seção `#full-prices`) para tendência, vendas/mês e o `Ungraded` (fallback raw
  rotulado). **Só informação** — nunca referência de slab (padrão COMC).
- **tcgcsv.com** (referência TCGplayer real p/ RAW NM): dump diário público
  dos preços do TCGplayer (categoria 3 = Pokémon), cliente stdlib em
  `src/tcg_reference.py` com cache 24h em `data/cache/tcgcsv/`. Só
  `marketPrice` conta (subtype Normal→Holofoil→Reverse Holofoil); sem
  marketPrice/sem match = None e o raw cai no fallback PriceCharting ROTULADO.
  **Carta não-EN = sempre None** (guard do PR #19). Set resolvido por match
  exato do nome (`tcg_set:` na watchlist quando o nome não bate); dois produtos
  com o MESMO número no set ("Charizard" vs "Charizard (Black Dot Error)",
  004/102 Base Set — smoke 2026-09-03) → o nome EXATO desempata; sem nome
  exato → None. ⚠️ User-Agent é obrigatório (sem ele = 401). **TCGplayer não
  tem preço de slab** — por isso slab segue PriceCharting.
- **eBay Browse API** (anúncios ativos, `src/ebay_api.py`): OAuth
  client-credentials com `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` (cota grátis
  **5.000 chamadas/dia**; setup ~5 min no topo do arquivo). **1 busca genérica
  por carta** (`pokemon <nome> <número> <set>`, categoria 183454 = CCG
  Individual Cards, `sort=price`), **paginada**: `limit` 200 × `max_pages` 3
  (para antes se a página vier curta ou `offset ≥ total`), filtros
  server-side `itemLocationCountry:US`, `priceCurrency:USD`,
  `buyingOptions:{FIXED_PRICE}` e piso de preço. Dedupe por `itemId` (na API)
  e por id E título+preço (no scanner, `dedup_dropped`). Retry 3× em
  429/5xx/rede (2s/4s); outro 4xx = `EbayApiError` (carta contada em
  `ebay_error`); 401/403 no token = `EbayAuthError` (aborta o run). **Contador
  de chamadas** (`EbayClient.calls`, inclui tentativas repetidas) vai ao funil
  como `ebay_calls`. Sufixos de busca por certificadora (" psa"/" bgs"/…) são
  **legado**, só com `grade_query_suffixes: true` no config. **Scraping direto
  do eBay NÃO funciona** (403 com urllib e cloudscraper, 2026-06-09) — não
  tente "consertar" voltando a scraping. A API de sold/completed do eBay
  (Marketplace Insights) é restrita — o agregado de vendidos vem do
  PriceCharting.

## Testes e CI

```bash
python -m pytest -q          # canônico (pytest.ini já escopa testpaths=tests)
```

No PC do operador: `.venv\Scripts\python -m pytest tests/ -q`. São **459
testes** (verificado 2026-09-03), todos offline (sem rede, sem credenciais),
em 17 arquivos: `test_groups` (invariante união dos 12 grupos == catálogo de
123 sets sem sobreposição; `parse_group_arg`/`is_group_spec`),
`test_build_watchlist` (geração da watchlist a partir do catálogo),
`test_ebay_api` (parse do payload real, paginação, retry,
contador), `test_grading` (allowlist e regras de título), `test_pc_sales`
(vendas comparáveis, janelas, variantes, LP), `test_scan_funnel` (funil,
breaker, abort), `test_scorer`, `test_report`, `test_summary` (layout COMC,
`--sensitivity`), `test_scanner_ref`, `test_grade_filter`, `test_tcg_reference`,
`test_pricecharting_parse`, `test_pricecharting_search`, `test_title_parser`,
`test_watchlist_groups`, `test_secret_sanitization`.

CI: `.github/workflows/tests.yml` — job `pytest` em `ubuntu-latest`,
Python 3.12, dispara em push na `main`, em todo PR e por `workflow_dispatch`.
Totalmente offline e **sem nenhum secret** (repo público, runner grátis).

## Arquitetura

```
main.py                CLI: watchlist + config -> run_scan -> markdown console + JSON (--out) +
                       CSV de registro; --min-discount/--min-price/--max-pages por run; aviso se o
                       config ainda tiver min_gross_margin_percent; exit 1 quando o run aborta;
                       --group N | N-M | 1,3,10-12 | all (canonicos) ou nome literal; --list-groups
                       mostra o titulo de cada grupo canonico
build_watchlist.py     GERA watchlist.yaml (versionada): catalogo 123 sets x 100 chases x raridade
                       >= Holo Rare x teto --cap 30 por set (market TCGplayer); pc_url via
                       pc_sales.product_page_url (sem pagina = fora + relatorio; nunca inventa URL);
                       flags --groups/--cap/--out/--no-pc/--pc-cache-dir
config.yaml            gate Desconto% (inteiro)/piso/fixed_price_only/graded_only/graded_allow/
                       lp_with_reference/max_pages/modo confiavel/pais exigido (comentados)
watchlist.yaml         GERADA e versionada (nao editar a mao; regenerar so quando o catalogo mudar);
                       campo group = numero canonico 1-12; pokemon/pokemon_rank/rarity/year do catalogo
watchlist.example.yaml modelo p/ lista alternativa feita a mao (--watchlist <arquivo>)
src/groups.py          (portado da COMC @ dd952ba) 12 grupos canonicos: SCAN_GROUPS (numero, titulo,
                       era, sets verbatim do catalogo), parse_group_arg (N | N-M | 1,3,10-12 | all),
                       is_group_spec, describe_groups; invariante uniao == catalogo (test_groups)
src/catalog/           set_catalog.json (123 sets c/ ano) + iconic_pokemon.csv (100 chases c/ rank)
src/scanner.py         orquestrador: por carta, 1 pagina do PriceCharting (CardRefs = medianas de
                       vendas por nota/variante/LP; PcBreaker = 5 falhas seguidas suspendem a fonte)
                       + referencia TCG + 1 busca paginada na Browse API (dedupe id E titulo+preco)
                       -> scorer.evaluate com Counter `stats` (funil); run_scan devolve
                       (fair_values, opportunities, pricing_only, stats, aborted); guarda REF
                       DESALINHADA (ref vs mediana dos anuncios limpos da mesma nota, 1.5x/0.6x,
                       min. 3 amostras); load_watchlist le os campos novos; filter_group aceita spec
                       numerica (groups.parse_group_arg) ou nome literal do campo group:
src/grading.py         (portado da COMC) nota do slab a partir do TITULO: allowlist
                       DEFAULT_GRADED_ALLOW, Grade/GradeResult (graded/raw/ambiguous/out_of_scope),
                       CGC 10 seco = Gem Mint, BGS 10 Black Label, PSA 9.5 nao existe,
                       pc_price_key (coluna exata do PC, nunca bucket generico), parse_grades_arg
src/pc_sales.py        (portado da COMC) vendas concluidas do PriceCharting: fetch_page (cache do
                       dia, retry, PcError), parse_sales, comparable_sales/lp_sales, variant_tokens,
                       sales_reference (janelas 180/365 d, >=3 vendas), parse_grade_prices,
                       product_page_url (busca por nome+numero+set)
src/pricecharting.py   parse das COLUNAS da pagina (tendencia/vendas por mes/Ungraded) -- so
                       informacao e fallback raw rotulado; busca de produto (product_url_from_search)
src/ebay_api.py        cliente Browse API: OAuth client-credentials, _clean_secret (BOM/zero-width),
                       categoria 183454, filtros US/USD/FIXED_PRICE, paginacao 200 x max_pages,
                       retry 429/5xx, contador `calls`, `last_total`, parse_search_payload (puro),
                       flag AG calculado (ver Armadilhas); EbayAuthError/EbayApiError
src/tcg_reference.py   referencia TCGplayer real p/ RAW NM via tcgcsv.com (cache 24h; marketPrice;
                       User-Agent obrigatorio; nome exato desempata numero repetido)
src/title_parser.py    identidade da carta no titulo, idioma, NM/LP explicitos, risk flags
                       (proxy/replica/gold foil/lote), nomenclatura JP
src/scorer.py          evaluate -> Opportunity ou None (motivo em `stats`): gates (preco fixo, piso,
                       pais, carta, nota), 3 trilhos de referencia, Desconto%/ROI bruto%/Spread$,
                       vereditos OPORTUNIDADE/REVISAR/SUSPEITO/REJEITADO, trust_score separado,
                       score 0-100 (margem 45 / liquidez 25 / tendencia 15 / risco 15) so como
                       ordenacao secundaria/auditoria
src/report.py          ENTREGA canonica: TABLE_COLS/REJECTED_COLS, FUNNEL_LABELS, compute_metrics,
                       sort_key (ROI -> desconto -> spread -> pokemon_rank), links_cell/carta_label/
                       status_cell/ref_label_cell, scan_payload (meta + funil + rows), to_csv
src/models.py          dataclasses (WatchCard c/ pokemon/pokemon_rank/rarity/year, Listing, FairValue,
                       Opportunity c/ discount_pct/spread_usd/ref_source/ref_n_sales/...)
ebay_summary.py        ENTREGA ao operador: JSON do scan -> markdown layout COMC (4 buckets ou
                       --sensitivity 10,15,20 com faixas + contagens por limiar); espelho do
                       comc_summary.py / myp_summary.py
tests/                 459 testes offline + fixtures reais (ver Armadilhas)
```

A watchlist é **list-driven de propósito**: casar item a partir de título
arbitrário é a maior fonte de erro; partir de item conhecido (com URL de
referência exata) e buscar anúncios DAQUELE item inverte o problema e dá
precisão (ver comentário em `watchlist.example.yaml`).

## Armadilhas conhecidas

- **`conditionDescriptors` NÃO vem na busca da Browse API** (spike 2026-09-03,
  fixture `ebay_search_charizard_base_psa.json`): a busca só traz `condition`
  = "Graded" / "Ungraded - …". A condição fina (Near Mint, Lightly Played) e a
  nota do slab têm que vir do TÍTULO (ou do texto de `condition` quando ele
  diz "Lightly Played"). Não "consertar" tentando ler o campo da busca.
- `qualifiedPrograms` (Authenticity Guarantee) idem: só no endpoint de
  detalhe. O flag AG é calculado por política do eBay: carta ≥ $250 localizada
  nos EUA = AG automático.
- **PSA 9.5 não existe**: o parser lê 9.5 (nunca arredonda para 9) e a
  allowlist derruba (`out_of_scope`).
- **Bucket genérico "Grade 9"/"Grade 9.5" do PriceCharting NUNCA é referência**
  (mistura PSA/BGS/CGC). Nota sem coluna própria (PSA 9, BGS 9.5, TAG 9.5…)
  tem referência só pela mediana de vendas comparáveis; `pc_price_key` devolve
  None e não há sanidade `coluna÷vendas` para ela. (A nota antiga "REF 9.5 =
  bucket genérico" deixou de existir em 0.5.0.)
- **CGC 10 sem "Pristine" no título = Gem Mint** (oposto do segmento de URL da
  COMC, onde `10` puro = Pristine). Assumir Gem é o lado seguro: é a referência
  mais baixa das duas.
- **Título com mais de uma nota** ("BGS 8.5 … PSA 9", "PSA 10 pop 5 compare
  PSA 9") = ambíguo = funil (`skip_grade_ambiguous`); certificadora fora do
  escopo (ACE/MNT/GMA/HGA/…, ou "GRADED 10" sem sigla) = `skip_grade_out_of_scope`.
- **"gold foil" / "gold plated" / "24k" / "metal card" = carta falsa ou de
  metal** → flag `REJEITAR` no `title_parser` (linha REJEITADO se passar o gate
  de desconto; também sai da mediana de anúncios).
- **tcgcsv com dois produtos de mesmo número** ("Charizard" vs "Charizard
  (Black Dot Error)" no Base Set): o nome EXATO normalizado desempata; sem
  nome exato → sem referência TCG (fallback rotulado). Nunca chuta.
- Referência raw via tcgcsv exige **User-Agent** (sem ele = 401); sem
  marketPrice/sem match, o raw cai no fallback PriceCharting **rotulado**
  (`PC Ungraded (sem TCG)`) — nunca preço inventado.
- O parser de volume do PriceCharting depende da ORDEM das células de volume
  na tabela principal (mesma ordem das colunas de preço). Sinal "+" da
  tendência vem como `&#43;` no HTML.
- Cache do PriceCharting é **do dia** (`data/cache/pc/<AAAA-MM-DD>/`): página
  de bloqueio/erro/vazia (<2.000 bytes ou `<title>` de "Just a moment"/"Access
  denied") nunca é cacheada, senão seria re-servida o dia inteiro.
- **`.gitignore` ignora `*.json` mas tem a exceção `!tests/fixtures/*.json`**
  — a fixture real da Browse API precisa estar versionada; ao adicionar outra
  fixture JSON, conferir que o `git add` não a ignorou.
- **Fixtures reais** (`tests/fixtures/`): `ebay_search_charizard_base_psa.json`
  (payload da Browse API, 2026-09-03), `pc_product_charizard_base_4.html` e
  `pc_product_charizard_ex_151.html` (páginas de produto do PriceCharting com
  vendas concluídas), `pc_search_charizard_ex_151.html` (página de busca do
  PriceCharting), `pc_charizard_base.html` (página real de 2026-06-09, parser
  de colunas).

## Fluxo de desenvolvimento e segurança

- **Branch + PR, nunca push direto em `main`** — é o fluxo padrão do repo.
  Processo: planejar → teste vermelho → correção → `/code-review` em contexto
  limpo → PR (ver `~/.claude/CLAUDE.md`).
- **Repo público e discreto**: dados de scan NUNCA entram no repo. Gitignored:
  `data/` (cache + CSVs), `results/` (JSON de scan), `*.csv`/`*.xlsx`/`*.json`
  (exceto `tests/fixtures/*.json`), `METODO.md` (o método é local), `.env`,
  `.venv/`. **`watchlist.yaml` é VERSIONADA desde 0.5.1** (gerada do catálogo
  público pelo `build_watchlist.py`; não é dado de scan nem contém preço).
- **Credenciais nunca versionadas** — só env vars / `.env` local / secrets do
  GitHub. Procedimento de report e rotação (regenerar Cert ID em
  developer.ebay.com → Application Keys): `SECURITY.md`. Checklist de
  publicação: `PUBLIC-RELEASE-CHECKLIST.md`.
- A sanitização de segredo da frota está implementada localmente
  (`_clean_secret` em `src/ebay_api.py`) e travada por
  `tests/test_secret_sanitization.py`.

## Estado e histórico

- **Versão atual: 0.5.1 (2026-09-03)** — watchlist gerada do catálogo +
  grupos canônicos (PR B), sobre o padrão COMC da 0.5.0. Histórico em
  `CHANGELOG.md` (criado nesta versão; não há string de versão no código — a
  fonte de verdade continua sendo o `main` mergeado + o CHANGELOG).
- Decisões do operador em vigor: **gate = Desconto% ≥ 20, só preço fixo,
  allowlist de slabs, referência de slab = mediana de vendas, raw LP com
  referência própria, entrega layout COMC com `--sensitivity`** (todas
  2026-09-03); graded-only por default + reversão por run via `--include-raw`,
  parâmetros do modo confiável 50/98, credenciais como env vars de usuário
  Windows (2026-06-10); só item nos EUA (entrega na COMC).
- Substituídas em 0.5.0: gate por ROI bruto (`min_gross_margin_percent`, 30 →
  15 em 2026-09-01 → deixou de ser gate); referência de slab pela coluna do
  PriceCharting e bucket genérico "Grade 9.5"; sufixos de busca por
  certificadora (viraram legado `grade_query_suffixes`); leilão no funil.
- Anteriores: referência raw via TCGplayer/tcgcsv + padrão /myp-scan
  (`ebay_summary.py`, grupos, skill scan-ebay) em 2026-07 (#18); run degradado
  não grava artefato + guard JP no tcgcsv (#19); retry do PriceCharting e
  `--grades` (2026-09-01). Validações históricas de rede: PriceCharting HTTP
  200 e eBay 403 a scraping (2026-06-09).
- **0.5.1 (PR B, 2026-09-03):** `watchlist.yaml` GERADA por
  `build_watchlist.py` (catálogo 123 sets × 100 chases × raridade ≥ Holo Rare
  × teto 30/set; `pc_url` exata ou a carta fica fora) e VERSIONADA;
  `src/groups.py` com os 12 grupos da COMC; `--group N|N-M|1,3,10-12|all`;
  `--list-groups` com título; fixes do PR #24 (Codex) registrados no CHANGELOG.
- **Pendente:** smoke ao vivo do run diagnóstico por grupo com `--include-raw`
  (`--group <N> --min-price 5 --min-discount 10 --include-raw`).
