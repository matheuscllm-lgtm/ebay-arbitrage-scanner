# SESSION-HANDOFF — margem bruta, preços pedidos e meses de estoque (2026-09-09)

Estado para quem retomar. Sem resultado de coleta aqui: nenhum preço, nenhuma carta, nenhuma
tabela e nenhum número de funil — `DELIVERY_CHAT.md` proíbe publicar resultado, preço ou log de
coleta no GitHub. Os artefatos ficam **locais**, em `results/`.

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
