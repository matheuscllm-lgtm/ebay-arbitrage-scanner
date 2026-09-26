# Modo CHINÊS — PSA 10 em chinês × PSA 10 em inglês

Pedido do operador (2026-09-26, fechado por entrevista `grill-me`): procurar, para as
cartas EN da watchlist, a versão em **chinês** certificada **PSA 10** no eBay que esteja
**pelo menos 4× mais barata** que o PSA 10 em inglês, com item **acima de US$10**, e
medir o **potencial de longo prazo** dessas cartas. Tese do operador: o mercado em
chinês valoriza. A análise é **independente** da tese e separa **simplificado**
(China continental, `ZH-HANS`) de **tradicional** (Taiwan/Hong Kong, `ZH-HANT`).

Este documento fixa o método. Resultado (linhas, preços) nunca entra no repositório
([DELIVERY_CHAT.md](../DELIVERY_CHAT.md)): fica em `results/` e vai ao chat VERBATIM.

## Como rodar

```bash
python chinese_scan.py --group 1 --out results/chinese-g1.json        # 1 chamada eBay por carta
python chinese_scan.py --group 11 --max-cards 100 --card-offset 0 --out results/chinese-g11a.json
python ebay_summary.py results/chinese-g1.json -o results/chinese-g1.md   # entrega (o JSON leva meta.kind)
```

Flags: `--group`, `--max-cards`/`--card-offset` (lote, como no `main.py`), `--min-ratio`
(default **4**), `--min-price` (default **10**, preço do item), `--min-zh-sales` (default
**3**), `--max-zh-pages-per-card` (default **20**), `--max-ebay-calls` (500 por execução),
`--location-country` (vazio = **qualquer país**; decisão do operador: vendedor asiático
aceito, frete/alfândega **fora** da reserva de US$10 e por conta dele). Exit 1 = run
abortado (credencial/orçamento); o parcial vai para `<out>.aborted.json`.

## O que o scan faz, por carta EN da watchlist

1. **Busca eBay** (Browse API, 1 chamada, até 200 anúncios, preço fixo, categoria graded,
   ordenado por preço): `"<pokémon> <sufixo> (chinese,chn,simplified,traditional) (psa 10,psa10)"`.
   Busca pelo **nome-base** porque os títulos chineses raramente trazem o dono
   ("Team Rocket's") ou o número EN. Sintaxe `(a,b)` = OR (provada em 2026-09-26).
2. **Filtros de anúncio** (cada descarte conta no funil): nota lida do título tem que ser
   exatamente PSA 10 (`grading.grade_from_title`); título com palavra de réplica/acessório
   ou lote/deck sai (`lot_or_reject`; a lista de lote é própria porque a do repo contém
   "collection" e os produtos chineses chamam-se "... Collection"); preço ≥ piso.
3. **Idioma pelo título** (`chinese_language`): o aspecto `Language` do eBay é pouco
   confiável (vendedor preenche errado). Marcadores de simplificado: "Simplified",
   "S-Chinese", "CHN", `简体`, códigos CS/CSV/CSM/CBB (sufixo C). Tradicional:
   "Traditional", "T-Chinese", `繁體`, Taiwan/Hong Kong, códigos com sufixo F
   (`sv4aF`, `M2 F-…`, `CLL F`). Só "Chinese" = `ZH` (chinês sem dizer qual → validar).
   Outro idioma citado junto (lote misto) → descartado. `slab_strategy.language` **não**
   foi alterada (contrato travado em teste).
4. **Identidade** (`match_level`): `nome+numero` = nome EN inteiro e número EN no
   título (par forte; só acontece em sets com numeração espelhada); `nome` = nome EN
   inteiro, ou base + dono escrito de outro jeito ("Rocket's Mewtwo ex"), número
   diferente/ausente; `nome-base` = só Pokémon + sufixo, aceito **apenas** se a
   raridade do título é da mesma família da EN (SIR↔SAR, IR↔AR, HR↔UR/gold…); sem
   isso é quase certo outra carta e sai (`skip_name_mismatch`). Sufixo/prefixo que
   muda a carta (ex/V/VMAX, Mega/Dark) nunca casa.
5. **Exclusivas** (`exclusive_marker`): promo (`-P`), Gem Pack/CBB, gift box,
   25th/30th/anniversary, Classic, All Stars Collection, tin, starter deck… vão para a
   **tabela 2**, sem razão EN÷ZH. Heurística de título, documentada e extensível.
6. **Referência EN = crivo** (`en_reference`): mediana das vendas concluídas PSA 10 na
   página EN da carta (PriceCharting, `pc_url` da watchlist; cesta legada
   `pc_sales.comparable_sales`, que exclui título com outro idioma), na menor janela com
   ≥3 vendas (90/180/365 d). Com <3 vendas cai na coluna PSA 10 do site, **rotulada**
   `coluna-PC` (e a linha nunca vira candidata). Razão = EN ÷ preço pedido do slab
   chinês, **sem frete**.
7. **Evidência chinesa** (`zh_evidence`), só para linhas que precisam (razão ≥ corte ou
   exclusiva; teto por carta): localiza a página `pokemon-chinese-*` no PriceCharting
   pela busca `pokemon chinese <nome> <número do título>` (`pick_zh_page`: slug termina
   no número, todos os tokens do nome no slug, pista de set quando o título tem código;
   sem número no título, só o código de set do título pode tornar a página única;
   resultado ambíguo **não chuta**). Da página: vendas concluídas PSA 10 em 90 d (n,
   meses distintos, mediana, links das vendas), janela 90–365 d (tendência observada),
   coluna PSA 10 do site (informativa), vendas/mês do site (parser do outlook) e censo
   PSA `VGPC.pop_data` quando publicado.

## Buckets da entrega (tabela 1, pares)

| Bucket | Regra |
|---|---|
| 🟢 candidata | razão ≥ corte **e** identidade forte (`nome+numero`, ou `nome` com raridade compatível) **e** idioma definido (HANS/HANT) **e** ≥3 vendas PSA 10 em chinês em 90 d **e** referência EN por vendas |
| ⚠️ validar | razão ≥ corte, mas falta algo — motivo por linha (`match-nome`, `raridade-nao-confirmada`, `raridade-divergente`, `idioma-nao-especificado`, `evidencia-zh-insuficiente(n<3)`, `zh-sem-pagina`/`zh-ambigua(...)`, `ref-en-coluna-PC`) |
| 🔎 abaixo do corte | razão < corte — diagnóstico; linhas com razão ≥ 2× saem inteiras, as com razão < 2× (anúncio vale mais da metade do PSA 10 inglês) saem agrupadas por carta EN com contagem, faixa de razão e o link do anúncio mais barato — todas continuam no JSON |
| ❌ sem referência EN | página EN sem venda e sem coluna |

Tabela 2 (exclusivas): todas as linhas com marcador, ordenadas pela régua LT, com
evidência chinesa, tendência observada e o título do anúncio para o operador validar.

Candidata sem número igual exige ainda que a página chinesa reimprima o **mesmo set
EN** (tabela curada `ZH_SET_TO_EN`: 151 Collect ↔ SV 151, sv8a ↔ Prismatic Evolutions,
s8a ↔ Celebrations…); compilação simplificada (CS/CSV/CSM/CBB), promo ou Gem Pack não
tem correspondência → `validar` com `set-zh-sem-correspondencia` (a arte pode ser de
outro set EN).

**Duas versões do markdown** (mesmo JSON, mesma régua): `<out>.md` completo (todas as
linhas) e `<out>.chat.md` (`ebay_summary.py --compact`) para o chat — quando um balde
⚠️ validar ou a tabela de exclusivas passa de 40 linhas, sai **agrupado por carta
chinesa** (contagem, preço mínimo/mediano, evidência, margem no mínimo, LT, link do
mais barato); 🟢 candidatas saem sempre inteiras. Um grupo SV gera milhares de
anúncios (dezenas do mesmo promo em preços diferentes) e o chat não comporta a
tabela completa — ela fica no `.md`/JSON local.

Toda linha tem `[oferta]` (eBay) e, quando existem, a referência EN **clicável** com
n e janela, e `[ref ZH]` (página chinesa). URLs vêm do JSON, nunca inventadas.

## Régua de longo prazo (coluna `LT`, informativa — nunca gate, nunca recomendação)

Espelha os 4 componentes do `pokemon-longterm-outlook` (0–25 cada, soma 0–100,
`k/4` = componentes com dado; ausente é `n/d`, nunca zero):

| Componente | O que mede aqui | Fonte | Faixa |
|---|---|---|---|
| Personagem | apelo perene do Pokémon/treinador da carta EN | `outlook.notorious` (repo irmão; ausente → n/d) | S 25 · A 18 · B 12 · fora 8 |
| Raridade | família colecionável | raridade EN da watchlist (pares) ou siglas do título (exclusivas: SAR/AR/CSR/UR/SSR/SR/RR) | SIR/SAR 25 · IR/AR 20 · CHR/TG 16 · HR/UR/gold/shiny 14 · SR/FA/VMAX 12 · ACE 10 · RR 6 · resto 3 |
| Escassez | nº de **PSA 10 do slab chinês** | censo da página chinesa do PriceCharting (mensal, atrasa; GemRate bloqueia sessão de nuvem) | ≤50 25 · ≤500 22 · ≤2.000 18 · ≤5.000 12 · ≤10.000 7 · acima 3 |
| Demanda | **vendas/mês do PSA 10 chinês** | vendas PSA 10 observadas em 90 d na página chinesa ÷ 3 (o "N sales per month" do site fica só informativo: o layout da tabela chinesa desalinha o parser) | ≥60 25 · ≥30 20 · ≥5 14 · ≥2 8 · abaixo 3 |

Colunas de apoio: **Margem vs revenda ZH** = (mediana das vendas PSA 10 em chinês em
90 d − preço pedido) ÷ preço pedido — a margem bruta da frota contra a revenda honesta
do slab chinês (negativa = o anúncio pede mais do que a carta vem vendendo em chinês);
**Razão EN÷ZH** (prêmio do inglês sobre o chinês; o crivo),
**Tend. obs.** (mediana 90 d vs 90–365 d das vendas chinesas, só com ≥3 em cada
janela), **Pop10 ZH**, **Vendas/mês ZH**. As faixas foram calibradas em 2026-09-21
sobre cartas **EN** (ver o outlook) e **não** foram recalibradas para chinês — os
censos chineses são ordens de grandeza menores, então Escassez sai alta por
construção; leia-a junto com Demanda.

## Parâmetros que sustentam (ou derrubam) valor de longo prazo — o que medir

Método fixado para a análise independente da tese (números só no chat/`results/`):

1. **Escassez real** — censo PSA 10 do slab chinês e sua velocidade (duas leituras;
   a 1ª é este run). Tiragens oficiais não são publicadas; o censo é a única proxy.
2. **Demanda observada** — vendas/mês de PSA 10 em chinês onde o operador consegue
   vender (eBay US/COMC), não a demanda doméstica chinesa (Xianyu/Dewu), que não
   se captura daqui.
3. **Prêmio EN÷ZH hoje e sua direção** — razão por carta e tendência observada das
   vendas chinesas; a tese exige que a razão encolha por **alta do chinês**, não por
   queda do inglês.
4. **Exclusividade de arte/tiragem** — o precedente JP/KR (7 anos) não mostrou
   convergência de idioma não-inglês em reimpressões; o que valorizou foram promos
   e artes exclusivas de tiragem fechada. Por isso a tabela 2 existe.
5. **Identidade/liquidez de saída** — match forte, idioma definido e ≥3 vendas em
   90 d são o piso; abaixo disso o operador fica preso na carta.
6. **Riscos estruturais** — fake slabs e réplicas vindas da China (PSA 2023, CGC 2026),
   regulação de "blind box"/menores, alfândega/frete fora da reserva, sets
   "catch-up" com listas próprias (baixa comparabilidade com EN/JP).

## Limites honestos

- Numeração chinesa costuma diferir da EN: sem número igual, a identidade fica em
  `nome`/`nome-base` e pede conferência da arte (link da oferta + páginas de
  referência estão na linha).
- O censo do PriceCharting não existe em toda página chinesa e atrasa meses; GemRate
  (pop oficial da PSA) responde 403 fora do PC do operador.
- 1 página por busca eBay (200 anúncios mais baratos): cartas com centenas de
  anúncios chineses podem ter linhas fora da janela — o funil mostra `total`.
- Vendas/mês "do site" é o número do PriceCharting; "observadas" é a contagem em
  90 d na própria página. Nenhum dos dois é o mercado eBay inteiro.
