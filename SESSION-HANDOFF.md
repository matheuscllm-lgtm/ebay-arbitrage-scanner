# SESSION-HANDOFF — margem bruta, preços pedidos e meses de estoque (2026-09-09)

Estado para quem retomar. Sem resultado de coleta aqui: nenhum preço, nenhuma carta, nenhuma
tabela e nenhum número de funil — `DELIVERY_CHAT.md` proíbe publicar resultado, preço ou log de
coleta no GitHub. Os artefatos ficam **locais**, em `results/`.

## ▶️ Frente ativa — par EN × ZH-S raw no eBay, crivo ≥ 4× (handoff 2026-10-04)

> **Em uma frase:** o operador quer clicar e cair no **anúncio ativo mais barato** do eBay
> da carta em **inglês** e no **anúncio ativo mais barato da mesma impressão em chinês
> simplificado**, só quando **EN ÷ ZH ≥ 4×** — os dois links abertos à venda, nunca item
> vendido/encerrado. Implementado em `tools/zh_ebay_pairs/` com as decisões abaixo aplicadas.

### Decisões fechadas pelo operador (não re-perguntar)

- Comparação **dentro do eBay** (EN × ZH-S), dois anúncios com link clicável. TCGPlayer
  não é referência de preço aqui (serviu só para ordenar a seleção).
- **Só anúncios ativos**, preço fixo; o link tem que estar à venda quando a tabela é
  entregue. **Raw** (sem slab). Preço comparado = item + frete quando conhecido.
- Mostrar **só pares com EN ÷ ZH ≥ 4×** (só chinês; KR/ID saíram do escopo).
- Universo: cartas EN de sets **2017–2025** (2026-10-04: o operador mostrou Gengar & Mimikyu
  GX, Team Up 2019, que a faixa 2022–2025 deixava de fora; 2017 = 1º ano com par no catálogo)
  com market > US$10 e par ZH-S no `src/catalog/zh_identity.json`. `--years` restringe.
- Comparação **NM × NM** (invariante da frota): a busca já pede ao eBay "Near Mint or
  Better" + não graded; sem isso o EN mais barato de carta antiga é cópia jogada e a razão
  cai abaixo de 4× (caso Gengar & Mimikyu: US$120 "Heavily played").
- Entrega = tabela no chat (`DELIVERY_CHAT.md`).

### O que existe (implementado e testado offline; validado em coleta real 2026-10-04)

- `tools/zh_ebay_pairs/guards.py` — guards puros, sem rede, reaproveitando o modo chinês
  PSA 10 (`src/chinese_scan.py`: idioma do título, nome-base + sufixo, lote/réplica):
  variante EN excluída (Master Ball/Poke Ball/stamp…), escolha da impressão ZH (sem Gem
  Pack `CBB*C`; raridade compatível com a EN, depois `tc-jp`; empate = flag), nome com o
  MESMO sufixo (`ex|V|VMAX|VSTAR|GX`), lote (vários "nº/total"), número **e total** da
  fração no título, "à venda" pelo getItem.
- `tools/zh_ebay_pairs/ebay_pair.py N [--offset K] [--years A-B]` — N cartas a partir da
  posição K (market TCGPlayer só ordena), 1 busca Browse API por idioma (EN e ZH-S, filtro
  NM + não graded; guarda os 10 plausíveis mais baratos e a mediana), depois `verify()`:
  nos pares que podem chegar a 4× (mediana EN ÷ ZH mais barato), getItem do mais barato ao
  mais caro até achar, em cada idioma, o 1º anúncio à venda e não jogado (preço renovado; o
  que caiu é declarado fora da tabela). Saída: só pares ≥ 4×, ordenados pela razão, com o funil na 1ª linha. Grava
  `results/zh_ebay_pairs.json` (local); `--render` re-renderiza sem coletar.
- `tools/zh_ebay_pairs/pair_table.py` — tabela de conferência do pareamento (sem eBay).
- Testes: `tests/test_zh_ebay_pairs.py` (offline, entram no `python -m pytest -q`).

### Limites conhecidos (declarar na entrega)

- Título não prova idioma (visto: "S-Chinese" com foto de carta japonesa) → todo par pede
  conferir a FOTO do anúncio ZH-S; a tabela diz isso no cabeçalho.
- Frete desconhecido na busca (frete calculado) conta 0 e a linha leva a flag.
- Guard "abaixo de 50% da mediana dos plausíveis = lixo" vale nos dois idiomas: visto ao
  vivo alt art de ~US$800 anunciada como NM a US$10 e a US$80. Custo: um EN barato legítimo
  abaixo de metade da mediana sai e a razão sobe; um ZH barato legítimo some.
- "Card Condition: Not Specified" fica fora da busca (o filtro NM exige a declaração).
- Impressão ZH de outra família de raridade (EN SIR × ZH SR) = sem par; empate entre
  impressões fica com flag.
- Teto de 500 chamadas por execução: usar **N=150** (300 buscas + folga para o `verify()`,
  ~120 chamadas na coleta de 2026-10-04). São 696 candidatas em 2017–2025: o universo
  inteiro pede 5 execuções (`--offset 0/150/300/450/600`). Cada execução SOBRESCREVE
  `results/zh_ebay_pairs.json`: entregar a tabela de uma fatia antes de rodar a seguinte.

### Decisão e observações

Decisão do operador (2026-10-04): **fica em `tools/`**, rodada sob pedido — não vira modo
do repo nem entra no `ebay_summary.py`. Nada pendente nesta frente.

- Catálogo `zh_identity.json`: problemas abaixo (tarefa de catálogo, não desta frente).

### Problemas do catálogo `zh_identity.json` vistos nesta sessão (para outra tarefa)

- `CS4.1C` repete o mesmo número para cartas EN diferentes (ex.: TG13 de 3 sets).
- Linhas com página 52poke de outro Pokémon (Turtwig GG31 → página Pikachu; Drapion GG49
  → Zoroark; Palkia GG67 → Giratina; Umbreon V TG22 → 亚洛).
- `zh_name`/`en_rar` incoerentes (喷火龙V para VSTAR; 174/172 rainbow marcado "RR").
- `jp` malformado em algumas linhas (ex.: Snom TEF 168 → "sv5k sv5k").
- Achado de anúncio: título "S-Chinese" com foto de carta japonesa — título sozinho não
  prova idioma; preço ZH muito abaixo do EN pede conferência de foto.

### Como retomar

```bash
cd tools/zh_ebay_pairs
python pair_table.py 10 > pairs_audit.md           # conferência do pareamento (sem eBay)
python ebay_pair.py 3                              # teste curto (6 buscas + verificação)
python ebay_pair.py 150                            # cartas 1-150 (~420 chamadas eBay)
python ebay_pair.py 150 --offset 150               # fatia seguinte (151-300), e assim por diante
python ebay_pair.py 150 --render                   # re-render do último JSON local
```

Credenciais: `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET` no ambiente. tcgcsv exige
`User-Agent` (sem ele responde 401).

## ▶️ Frente ativa — modo CHINÊS (handoff 2026-09-27, PR #47)

> **Em uma frase:** o operador pediu "PSA 10 em chinês pelo menos 4× mais barato que a
> versão em inglês, carta acima de US$10, com análise do que sustenta valor de longo
> prazo"; a entrevista (`grill-me`) fechou o escopo abaixo; está **implementado, testado
> e rodado ao vivo** na watchlist inteira em 2026-09-26; o PR #47 (draft) espera merge.
> A próxima sessão retoma pelos comandos da seção "Como retomar", sem re-perguntar o que
> está fechado aqui. Método completo: `docs/CHINESE_PSA10.md`.

### Onde está

- Branch `claude/pokemon-psa10-chinese-analysis-r9f7fe`, a partir de `origin/main`
  (`9a2130a`). PR draft: https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/pull/47
  — **não** subscrito, sem check-in (regra do operador); quem mergeia é ele.
- Código: `chinese_scan.py` (CLI) + `src/chinese_scan.py` (busca, idioma, identidade,
  localizador da página chinesa, evidência, régua LT, `rescore`, `classify`),
  `src/chinese_report.py` (2 tabelas + versão de chat), `ebay_summary.py` (despacho por
  `meta.kind`, `--compact`), `chinese_thesis.py` (consolidação + análise da tese + funil
  do crivo). Testes: `tests/test_chinese_scan.py`, `test_chinese_rescore.py`,
  `test_chinese_setmap.py`, `test_chinese_thesis.py` — suíte inteira verde
  (`python -m pytest -q`, 1159 testes em 2026-09-27).
- Política `longterm`/`slab_strategy` intocada; `slab_strategy.language('Chinese')` segue
  `None`. O modo chinês é um caminho paralelo, não um modo do `main.py`.
- Resultados do scan de 2026-09-26 (JSON, `.md`, `.chat.md`, análise) viveram em
  `results/` do container da nuvem e **não existem mais**: foram entregues no chat.
  Qualquer nova entrega exige **coleta nova** (`DELIVERY_CHAT.md`).

### Decisões fechadas com o operador (2026-09-26) — não re-perguntar

- Tese dele: o mercado em chinês valoriza. A análise do scanner é **independente** e
  separa **simplificado** (`ZH-HANS`, China continental) de **tradicional** (`ZH-HANT`,
  Taiwan/Hong Kong); título sem marcador fica `ZH` (não especificado → validar).
- Crivo de entrada: razão EN÷ZH ≥ **4** (PSA 10 inglês por vendas concluídas ÷ preço
  pedido do slab chinês, sem frete) e item > **US$10**. A razão é só a porta: a revenda de
  um slab chinês se prova com **vendas em chinês** (página chinesa do PriceCharting).
- Vendedor de **qualquer país** (asiático incluído); frete/alfândega ficam **fora** da
  reserva de US$10, por conta do operador.
- **Exclusivas** (marcador de produto sem par EN: promo, Gem Pack, gift box, 25th/30th…)
  saem em **tabela à parte**, nunca misturadas aos pares.
- Universo = a **watchlist eBay existente** (versão chinesa de cada carta EN). Universo
  próprio de exclusivas chinesas é ideia registrada, não pedido.
- Candidata = razão ≥ corte **e** identidade forte (nome + número EN no título, ou nome
  inteiro + set chinês que reimprime o mesmo set EN no mapa curado `ZH_SET_TO_EN`)
  **e** raridade compatível **e** idioma definido **e** ≥ **3** vendas PSA 10 em chinês
  em 90 d. Tudo o mais é ⚠️ validar, com o motivo na linha.
- Régua LT (Personagem + Raridade + Escassez pelo censo chinês + Demanda por vendas/mês)
  é **informativa**, espelha as faixas do outlook e **não** foi recalibrada para chinês.
- Invariantes da frota: nunca inventar preço, nunca recomendar compra, entrega = tabela
  gerada pela ferramenta colada VERBATIM, teto de 200 palavras de prosa.

### O que o scan de 2026-09-26 mostrou (leitura qualitativa; números só no chat)

- Cobertura completa: grupos 1, 2, 3, 10 (em 2 lotes), 11 e 12 da watchlist; nenhum run
  abortado. A versão de chat (`--compact`) foi necessária: a completa passa de 1 MB.
- **Candidatas: pouquíssimas e concentradas em 2 cartas — todas com margem NEGATIVA
  contra a revenda chinesa.** "4× mais barato que o inglês" descreve a diferença
  estrutural de preço entre idiomas, não um anúncio abaixo do valor chinês.
- Simplificado: a **maioria** dos pares pede **mais** que a mediana EN; só uma fração
  pequena passa o crivo de 4×, e dessa fração quase tudo cai na **identidade** (o título
  chinês traz outro número, e o set chinês não está no mapa curado) ou em **set
  divergente** (mesmo nome, outra arte). O gargalo do funil é identidade, não preço.
  Ver `chinese_thesis.py` → seção "Funil do crivo".
- Nas páginas simplificadas líquidas, a **tendência observada** (mediana 90 d vs
  90–365 d) foi positiva na maioria; censo PSA confiável só numa minoria das páginas,
  com pop 10 na casa das centenas (escassez real onde há censo).
- Tradicional: amostra fina demais para concluir (poucas páginas, quase sem censo).
- Exclusivas: mais líquidas que os pares, mas os anúncios pedem acima da revenda
  chinesa na grande maioria; margem positiva é exceção.
- Leitura para a tese: **valorização, sim, nas páginas líquidas; arbitragem contra o
  inglês, não.** Onde há prêmio no chinês é em exclusividade de arte/tiragem, não em
  reimpressão de carta EN.

### Contexto de mercado (pesquisa web de 2026-09-26; o brief completo era local)

- Duas línguas, dois mercados: tradicional (Taiwan/HK) desde 2019-10; simplificado
  (China continental) desde 2022-10, pela Pokémon Shanghai (subsidiária direta da TPC).
- Simplificado nasceu "catch-up": compilações com códigos próprios (CSM/CS/CSV/CBB/151C)
  cujas listas **não coincidem** com JP/EN — por isso a numeração difere e a identidade
  precisa de mapa curado. Primeiro lançamento simultâneo global só em 2026-09 (30th).
- Tradicional espelha o Japão desde a era SV (códigos JP com sufixo F, 3–5 semanas de
  atraso); antes, compilações próprias (AC/AS).
- **Tiragens não divulgadas** em nenhuma das duas; único número público é de uma promo
  de loteria. Reimpressão oficial: não encontrado.
- Demanda doméstica em alta (mercado chinês de TCG crescendo dois dígitos; Pokémon IP
  nº 1 em volume no Xianyu em 2025). Grading local: CGC em Xangai desde 2023-12, PSA com
  centro de submissão em Hong Kong desde 2025-11.
- Topo do mercado chinês = **exclusivos** (arte própria, promos de tiragem fechada);
  reimpressões regulares valem fração das JP/EN.
- Precedente JP/KR: em 7 anos o PSA 10 japonês de modernos **não** convergiu para o
  inglês; coreano ficou abaixo dos dois. Não sustenta convergência automática por idioma.
- Riscos: slabs PSA falsos originados na China (caso 2023), relatos não verificados de
  réplicas de cartas SC, regulação de "blind box"/menores (SAMR 2023, People's Daily
  2025); nenhuma restrição formal de exportação encontrada.
- Fontes-chave (lidas em 2026-09-26): PokeGuardian (lançamento TC 2019 e 5th
  Anniversary TC), 52poke wiki (ginásios oficiais, Gem Pack), d-arts.cn (entrevista
  Pokémon Shanghai), Bang For Your Buck TCG "Simplified Chinese Pokemon: The Third
  Option" (2026-05), PokiPair (set lists SC, Collect 151, 30th), SNKRDUNK "Holy Grails of
  Chinese Pokémon Cards" (2026-08), PriceCharting (consoles `pokemon-chinese-*`), Sina
  Tech (relatório Xianyu 2025), chyxx (mercado TCG China 2025), Xinhua (2025-04), Elite
  Fourum (PSA HK 2025-11; slabs falsos 2023; fakes 2025), CGC (Xangai), SCMP (blind box
  2025), PokemonPriceTracker / Miraj Trading / TCGTalk (JP × EN), Japan-Figure (KR × JP).
  GemRate, PSA Pop Report, Bulbapedia e PokeBeach bloqueiam leitura da nuvem (403).

### Armadilhas já pagas (não re-descobrir)

- **eBay Browse API**: OR é `(a,b)` dentro do `q`; o aspecto `Language` é pouco
  confiável → idioma vem do **título**. 1 chamada por carta; orçamento 500 por execução →
  um grupo por run, grupo 10 em 2 lotes.
- **PriceCharting chinês**: páginas em `/game/pokemon-chinese-<código>/<slug>`; a busca
  devolve hrefs **absolutos** (o regex relativo achava "sem página" em quase tudo);
  promos colam número ao código no slug (`…-330th-p`); Gem Pack cola numerador +
  denominador (`eevee-407` = 4/07); busca específica **redireciona** para a página
  canônica; variante de impressão (holo/reverse) tem página própria; resultado ambíguo
  **não chuta** (`ambigua(n)`). `VGPC.pop_data` (censo) só existe em algumas páginas e é
  mensal; censo total < 25 nunca vira escassez.
- **Outlook reaproveitado** (`OUTLOOK_DIR` ou pasta irmã `../pokemon-longterm-outlook`):
  `notorious.appeal_points` funciona; `psa10.parse_psa10_sales_per_month` **lê errado**
  o layout chinês → demanda usa vendas observadas em 90 d ÷ 3. **GemRate responde 403**
  da nuvem (curl_cffi também).
- **Identidade**: numeração chinesa difere da EN; dono no nome é obrigatório ("N's",
  "Cynthia's"); tag team ("&"/"and") e sufixo colado por hífen (`-GX`) são outra carta;
  famílias de raridade (SIR↔SAR, IR↔AR, HR↔UR…) valem, raridade fora da família não.
  `rescore()` reaplica tudo isso na entrega, então JSON antigo sai com a régua de hoje.
  **Desde 2026-09-27 a identidade é por IMPRESSÃO** (`src/zh_identity.py`,
  `src/catalog/zh_identity.json`, `docs/CHINESE_IDENTITY.md`): a 52poke wiki dá, por
  carta simplificada, o set japonês de origem, a raridade, o ilustrador e a impressão
  EN correspondente; `catalog_identity()` grava `row["zh_catalog"]` e o `classify`
  usa. TCGdex/PTCG-database NÃO servem para simplificado (devolvem o tradicional).
  Ambíguas e "sem par" são o alvo da conferência por imagem (não feita).
- **Volume**: entrega completa da watchlist inteira passa de 1 MB; no chat vai o
  `.chat.md` (`--compact`: candidatas inteiras, validar com evidência agrupado, contagens
  para o resto; URLs eBay sem rastreio).
- **Operacional na nuvem**: `pkill -f`/`pgrep -f` casam o próprio shell da sessão (mata o
  runner); mate por PID. Nada em `results/` sobrevive ao container.

### Próximos passos, em ordem

1. **Merge do PR #47** (operador).
2. **Ampliar `ZH_SET_TO_EN`** com correspondências verificadas (é o gargalo do funil:
   nome sem número + set chinês fora do mapa). Cada correspondência nova precisa de prova
   (lista de cartas do set chinês = reimpressão do set EN), nunca dedução — lição
   ASI-Evolve dos aliases alucinados. Teste em `tests/test_chinese_setmap.py`.
3. **Censo PSA para chinês**: testar GemRate do PC do operador (IP residencial); se
   abrir, portar o leitor do outlook (`outlook/gemrate.py`) com match por set chinês.
4. **Calibrar as faixas LT** para chinês (hoje espelham o outlook EN): precisa de
   snapshots acumulados; sem dado, seguem informativas.
5. **Universo próprio de exclusivas** (Gem Pack, 151 Collect, promos SC/TC) como pedido
   separado do operador — o scan atual só vê exclusivas que aparecem ao buscar cartas EN.
6. Se o operador pedir nova entrega: rodar tudo de novo (abaixo), nunca reaproveitar.

### Como retomar em 4 comandos

```bash
export EBAY_CLIENT_ID=… EBAY_CLIENT_SECRET=…          # só no ambiente, nunca em arquivo
for g in 1 2 3 11 12; do python chinese_scan.py --group $g --out results/chinese-g$g.json; done
python chinese_scan.py --group 10 --max-cards 160 --card-offset 0   --out results/chinese-g10a.json
python chinese_scan.py --group 10 --max-cards 160 --card-offset 160 --out results/chinese-g10b.json
python chinese_thesis.py results/chinese-g*.json --merge-out results/chinese-all.json -o results/analise_tese.md
python ebay_summary.py results/chinese-all.json -o results/chinese-all.md --compact   # cola o .chat.md VERBATIM
```

Um grupo leva de dezenas de minutos a ~1 h (páginas do PriceCharting, até 20 por
carta); rode em background e um grupo por vez. Exit 1 = run abortado (credencial ou
orçamento); o parcial vai para `<out>.aborted.json` e o `chinese_thesis.py` aceita-o.

---

## Onde está o trabalho

- Branch: `feat/margem-bruta-e-demanda`, a partir de `origin/main` (`3bc68ac`, que já contém os
  PRs #32, #33 e #34 mergeados por squash).
- Runner (do diretório do repo):
  `$env:PYTHONIOENCODING='utf-8'; .venv\Scripts\python.exe -m pytest tests\ -q`
- A rodada anterior (coluna "Longo prazo", PR #34) está **mergeada**. A versão anterior deste
  arquivo dizia que o PR-C não tinha sido criado; isso ficou obsoleto.

## O achado que motivou a rodada

Auditoria do run real de 2026-09-09 (grupo 3, 6.104 anúncios, `results/lt-smoke-g3-pos-fix.aborted.json`):

- **Referência de preço existe em só 2,7% das linhas** (165 de 6.104). Quando existe, a mediana
  é de **2 vendas comparáveis**, máximo 6, contra `evidence.min_sales: 3`. 5.939 linhas têm zero.
- **Não existe dado de população PSA no scanner.** O componente do PERFIL chamado "supply" mede
  idade e reimpressão, não estoque.
- O PERFIL correlaciona +0,43 com o preço de referência (n=74 chaves) e ~0 com o prêmio da
  PSA 10 sobre a carta bruta: ele redescobre o preço, não prevê valorização. Na calibração,
  raridade e supply saíram sem variação e a tendência saiu invertida — o PERFIL rodou de fato
  sobre dois dos cinco componentes.
- O gate econômico só chegou a disparar em 251 das 6.104 linhas. **Decidir limiar mexe em 4% do
  run; a fome de referência decide 97%.**

## O que esta rodada entregou

1. **Gate por margem bruta** (`gate_mode: gross_margin`, `min_gross_margin_percent: 43`).
   Regra canônica da frota: só margem bruta, sem taxa. Custos COMC seguem calculados e no JSON
   como informação, fora do veredito. O gate deixou de depender do modelo de custos, que faltava
   em 5.975 das 6.104 linhas. CLI: `--min-gross-margin N`.
2. **Preços pedidos alimentam a coluna nos dois caminhos**, sem tocar veredito: o cálculo foi
   separado do efeito colateral que rebaixava OPORTUNIDADE para REVISAR. O teto `LP2*` da
   política caiu. Custo zero de API — os anúncios já estão em memória.
3. **`estoque-alto`, a 11ª flag de fragilidade**: `listings_same_grade` ÷ `psa10_sales_pm`.
   Primeiro sinal de oferta contra demanda real da régua. Cobertura passa de `k/10` para `k/11`.
4. **Pisos da LP1 viraram config** (`lp1_min_profile_coverage`, `lp1_min_fragility_coverage`).
5. **Cesta legada**: `comparable_sales(..., require_number=)`, desligada por padrão em
   `legacy_reference.require_number_in_sale_title`. Ligar unifica a régua com o caminho vigente,
   mas encolhe a cesta — e a cobertura já é o gargalo. A chave existe para ser reversível.

## Correções da revisão em contexto limpo

`/code-review high` achou 8 defeitos, todos corrigidos. Três mudam comportamento: a ordem
da tabela passou a usar margem bruta (ranqueava por métrica indisponível em quase toda
linha); o "teto de comparação" virou o maior preço que o gate realmente aprova; e margem
absurda voltou a pedir conferência de identidade, com corte próprio do modo
(`suspicious_gross_margin_percent: 150`). Os outros cinco: teto da família de flags que
compartilham insumo, meses de estoque restrito à PSA 10, piso da LP1 de volta a 8, guarda
de drift ancorada, e `--min-gross-margin` deixando de ser aplicada em silêncio.

## Invariantes que a rodada respeita (não quebrar)

1. A coluna **Longo prazo** é informativa: nunca entra em gate, veredito, ranking nem
   recomendação de compra.
2. No caminho da política, `verdict`, `discount_pct`, `roi_pct`, `risk_flags`, `reasons`,
   `strategy` e a ordenação do relatório não mudaram por causa da coluna (há teste).
3. Nunca recomendar compra — capital é decisão do operador.
4. Toda linha entregue carrega os DOIS links: `[oferta]` e `[referência]`.
5. `n/d` nunca vira 0.

## Estado de verificação — o que AINDA não foi feito

- **Nenhum run real com o gate novo.** Todo o trabalho está coberto por teste, não por execução.
  Um run novo só acontece a pedido do operador, e com `max_pages: 1` o orçamento de 500 chamadas
  não cobre as 49 cartas do grupo 3 (o smoke de 2026-09-09 abortou parcial, 453 das 500 chamadas
  gastas em consultas de detalhe). Para entrega de verdade, reduzir escopo.
- **Nada foi validado contra o mercado.** Um snapshot não é backtest. Meses de estoque é
  calibração inicial como o resto da régua.
- 58% dos anúncios baixados são rejeitados por nota/certificadora fora de escopo, gastando
  orçamento de API sem produzir linha avaliável. Não foi atacado.

## Próximo passo acordado com o operador

Ordem: meses de estoque (feito aqui) → **coletor de população PSA** (pop por nota, taxa gem
pop10/pop total, e velocidade da população, que exige duas leituras separadas no tempo) →
recalibrar a régua, trocando o PERFIL de fama (personagem, raridade, faixa de preço) por dois
eixos, escassez e demanda. O coletor de população é a única peça que exige fonte de dado nova;
verificar acesso e limite de requisição da PSA antes de prometer prazo.

> **Atualização 2026-09-21 — o coletor de população JÁ EXISTE, não duplicar aqui.** Foi
> construído no repo `pokemon-longterm-outlook` (PR #27, modo `--lowpop`):
> `outlook/psa10.py::fetch_psa10(nome, set, número)` lê da página da carta no PriceCharting
> (sem navegador, ~3 s/carta, cache em disco de 1 dia) o censo PSA e CGC por nota
> (`pop_psa`/`pop_cgc`, listas 1..10), o preço e as vendas/mês da PSA 10, o preço da crua e o
> `tcg_product_id` (chave de join com o tcgcsv). O eBay foi testado como fonte do mesmo dado e
> **bloqueia requisição sem navegador** — descartado. Taxa gem (pop10 ÷ total) e velocidade
> de população (duas leituras; o censo do PriceCharting é mensal) já estão modeladas lá
> (`ScoredCard.gem_rate`, campos no snapshot diário). Quando este scanner precisar de
> escassez, importe/porte esse módulo; o passo "verificar acesso à PSA" está resolvido.

## Perguntas ao operador ainda em aberto

- Virar `legacy_reference.require_number_in_sale_title` para `true`? Hoje `false`, pelo motivo
  acima. É reversível isoladamente.
- PRs #26 e #28 seguem abertos, só comentados com a evidência (um já contido na `main`, o outro
  superado). Fechar PR não foi autorizado.

## Regras de entrega e de repositório

- `DELIVERY_CHAT.md` manda: coleta nova a cada pedido, tabela do gerador canônico colada
  VERBATIM no chat, preço de referência clicável, todas as linhas, nada publicado no GitHub.
- `results/` e `data/` são locais e estão no `.gitignore`.
- Branch + PR sempre; quem mergeia é o operador.

## Continuação 2026-09-10 — cobertura de identidade

Branch `fix/catalog-identity-coverage`, baseada na branch do PR #36. Corrigidos os
títulos canônicos dos Base Sets modernos; adicionado catálogo EN com as 25
identidades da Classic Collection para proteger seleções parciais. Watchlist
permanece inalterada. Fonte e limitações em `src/catalog/README.md`.

Validação local: 835 testes aprovados; 3 regressões novas reproduziram os defeitos
antes da implementação. Não houve coleta de ofertas ou preços. Nenhum merge foi
executado. Esta atualização complementa, sem substituir, os PRs #36 e #35.

## Continuação 2026-09-10 — retorno e evidência

Branch `fix/gross-return-evidence`, baseada no PR #35. Corrige alerta restrito a
PSA, fallback da coluna/JSON e teto de preço na fronteira estrita. Mantém os
limiares econômicos e as equivalências. “Margem bruta” é nome histórico da coluna;
a legenda agora identifica retorno sobre compra e a base de revenda própria.

Complemento de identidade em PR separado, baseado no #36: catálogo completo de
identidades Classic Collection sem aumentar a watchlist. Nenhum merge nem scan
de ofertas/preços foi executado nesta continuação.
