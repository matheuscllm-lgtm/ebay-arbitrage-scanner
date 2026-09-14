---
name: scan-ebay
description: >-
  Rodar o scanner eBay sob demanda e entregar o Markdown canônico no chat.
  Política padrão 2026-09-11.1: PSA 10 EN/JP, preço fixo nos EUA, três eixos
  (tese, entrada, evidência), margem bruta mínima de 20% e nenhuma quota Top100.
  Use quando o operador pedir para rodar o scanner do eBay / "roda o eBay" /
  "scan eBay" / escanear a watchlist do eBay. Antes de rodar, confirme o grupo
  canônico e os ajustes do lote; entregue todas as linhas e o funil gerados pelo
  ebay_summary.py, sem recomendação de compra ou publicação no GitHub.
---

# Scan do eBay — confirmar, coletar, entregar

Leia `DELIVERY_CHAT.md`, `docs/EBAY_PSA.md` e `config.yaml`. Uma solicitação de
revisão/implementação de código **não autoriza coleta de mercado**. Resultados,
preços, teses privadas e logs não entram em commits, PRs, issues, comentários,
Pages, Actions artifacts ou job summaries. Entrega de resultados somente no chat.

## Regra vigente

`slab_strategy.economics` usa `gate_mode: longterm`, com
`min_gross_margin_percent: 20`: **20%**, limite estrito. Apenas PSA 10, EN/JP
separados, preço fixo, item nos EUA e preço do item até US$500. O orçamento de
US$500 é antes de frete/impostos; investimento e custos aparecem separadamente.

- **Tese:** quatro sinais documentados e atuais (demanda, importância colecionável,
  oferta, resiliência). Para favorável, pelo menos três `supportive`, incluindo
  demanda, e nenhum `adverse`. Cada sinal tem fonte, data e justificativa; exige
  também condição de invalidação da tese. Fonte é curadoria do operador, não
  verificação independente feita pelo scanner. Mais de 180 dias ou data futura
  tornam o sinal não confirmado por padrão. Sem tese privada, REVISAR.
- **Entrada:** margem bruta = `(revenda comprovada − item) / item ×100`,
  estritamente acima de **20%**, mais lucro líquido operacional atual positivo
  com custos completos. Não confundir margem com desconto ou retorno all-in.
  Uma boa tese não compensa preço excessivo. O teto do item é condicional aos
  demais eixos; não é recomendação de compra nem preço futuro estimado.
- **Evidência:** mesma carta, coleção, número, variante, idioma e nota nas vendas.
  Mediana com ≥3 vendas em 180 dias; só em 365 dias implica REVISAR. Além disso,
  `longterm` exige ≥9 comparáveis observados em 90 dias, em ≥2 meses-calendário,
  contados antes do limite de 10 vendas da mediana. Dispersão máxima 30%,
  vendedor verificável, sem duplicatas nem best offer de preço não confirmado.
  Não chamar essa amostra de todas as vendas ou compradores do eBay.
- **Custos:** reserva estimada única de US$10 para envios/impostos até COMC;
  Elite US$2,50; venda 5%; saque informado 10%; armazenamento/segurança em 120
  dias. É teste de saída aos preços atuais, não custódia/retorno de 3–5 anos.
  Não inventar preço, usar raw ×3 nem gerar cenários de valorização.
- **Classificação:** OPORTUNIDADE exige os três eixos favoráveis/adequados;
  MONITORAR mantém tese neutra/favorável com evidência suficiente, mas entrada
  fraca ou sem convergência completa; REVISAR para incerteza; REJEITAR para
  restrição estrutural ou tese desfavorável. Demanda adversa ou ≥2 sinais
  adversos, com todos documentados, tornam a tese desfavorável. Um alerta de
  margem excessiva pede revisão de identidade, não prova fraude.

`gross_margin`, `profit_or_discount` e `all_minima` permanecem modos legados
explícitos, com APROVAR / REVISAR / REJEITAR e regras próprias de outras notas e
certificadoras. Não mudar para esses modos em silêncio. `gross_margin` usa só
margem e custos informativos; isso não descreve o padrão `longterm`.

## 1. Preparar sem rede e confirmar o lote

- Chaves `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET` somente no ambiente; nunca
  imprimir nem passar inline. Sem chaves, não consultar eBay nem sobrescrever scan.
- `watchlist.yaml` é catálogo gerado e versionado; não editar manualmente.
  `build_watchlist.py` não impõe teto por set por padrão. Os 100 personagens
  em `src/catalog/iconic_pokemon.csv` são metadados, não quota de elegíveis.
  A mudança no gerador não regenera o catálogo existente automaticamente.
- Teses são arquivo privado via `--thesis-file`, com esquema documentado em
  `docs/LONGO_PRAZO.md`. Se não houver arquivo, declarar tese não confirmada;
  não fabricar fonte ou tese para produzir oportunidades.

```powershell
.venv\Scripts\python main.py --check-config
.venv\Scripts\python main.py --list-groups
```

`--check-config` não acessa rede; código 0 sem pendências, 2 com pendências.
Configuração malformada falha antes da coleta. Obtenha os títulos e contagens de
grupos dinamicamente com `--list-groups`; não reutilize contagem de scan anterior.

Confirme **um grupo canônico por vez** e os ajustes desejados. `--group` aceita
um número, intervalo, lista ou `all`, mas não presumir busca do catálogo inteiro.
Sem ajustes, vale a configuração. Opções relevantes:

- `--max-pages N`: páginas por carta; padrão 3.
- `--max-cards N`: limite opcional do lote de processamento, não de elegibilidade.
- `--card-offset N`: início determinístico do lote no universo selecionado.
- `--thesis-file CAMINHO`: arquivo privado de teses; ausência não aprova pela margem.
- `--min-gross-margin N`: ajusta o piso inteiro apenas no modo legado
  `gross_margin`; em `longterm`, **20%** é fixo e outro valor é rejeitado.
- `--min-discount N`: só tem efeito nos modos legados que usam desconto.
- `--min-price USD`, `--grades "PSA 10"`: restringem o funil; raw é rejeitado.
  No modo `longterm`, selecionar outra certificadora não amplia a elegibilidade.
- `--confiavel`: compatibilidade; histórico do vendedor já é verificado.

Não buscar "até encontrar 100" nem afrouxar critérios para completar quantidade.
Zero oportunidades é resultado válido. A watchlist pode conter mais cartas que
o lote, e cartas adiadas não são rejeitadas nem avaliadas.

## 1b. Pré-seleção de candidatas (opcional; consulta só o PriceCharting)

`preselect.py` consulta apenas a referência de vendas PSA 10 — sem credenciais
eBay, sem tese, sem preço de anúncio — e gera uma fila privada de curadoria:
CANDIDATA / REVISAR / FORA_DO_ESCOPO. **CANDIDATA é candidata à curadoria de
tese**, nunca elegibilidade de investimento nem oportunidade. Também é coleta de
mercado: só quando o operador solicitar, nunca por tarefa de código.

```powershell
.venv\Scripts\python preselect.py --group 3 --max-cards 25 --card-offset 0 --out results\preselection-run-01.json
```

- Mesmo comparador e pisos do modo `longterm` (≥9 vendas em 90 dias, ≥2
  meses-calendário, dispersão ≤30%). O lote limita trabalho, não elegíveis;
  referência acima de US$500 não exclui a carta — o teto vale para o preço do
  anúncio, avaliado no scan seguinte.
- O JSON gerado (privado, `results/` ou `private/`, nunca sobrescrito) pode ser
  passado a `main.py --watchlist`; o scan seguinte renova os preços. Todas as
  linhas ficam na tabela impressa; só candidatas entram em `cards`. Falha ou
  lote parcial: código 1 e `meta.incomplete: true`; lista vazia não prova ausência.
- Entregar no chat a tabela impressa pelo próprio `preselect.py`; o arquivo é
  apoio privado e não entra em commit, PR ou comentário.
- Depois da pré-seleção: gerar `private/theses.yaml` como esqueleto (identidade copiada
  do JSON, sinais em `null`), o operador preenche sinais e fontes, e
  `main.py --check-config --thesis-file private/theses.yaml --watchlist <json>` confere
  a cobertura tese × watchlist antes do scan (`docs/LONGO_PRAZO.md`).

## 2. Coletar somente quando solicitado

Exemplo operacional; substitua grupo, lote e caminho por escolhas confirmadas:

```powershell
$env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python main.py --group 3 --max-pages 1 --max-cards 25 --card-offset 0 --thesis-file data\theses.yaml --out results\last_scan_g3.json
```

- Estime cartas do lote × (páginas + até `max_item_details_per_card: 10`
  detalhes) contra `max_ebay_calls: 500`. Detalhes e retentativas entram no teto.
- Cada lote tem saída própria. Não mesclar nem reaproveitar preços de outra
  coleta. Uma execução posterior renova ofertas e referências.
- Diferencie lote concluído de universo concluído. Preserve no relatório a
  contagem de cartas selecionadas, processadas e adiadas, e qualquer parcialidade.
- Autenticação, cota, fonte ou processamento com falha tornam a coleta parcial;
  JSON parcial usa `.aborted.json`, CSV parcial `.aborted.csv`, sem substituir
  o último scan completo (`aborted: true`). Use o caminho efetivamente informado
  pela execução.
- PriceCharting indisponível (`pc_error`, `pc_breaker`) mantém anúncios em
  REVISAR quando possível, com `sem-vendas-PSA-comparaveis`; não usar preços antigos.
  Erro interno por carta (`card_error`) ou da API (`ebay_error`) pode resultar em
  carta pulada, sem linhas e com erro contado no funil. Nos dois casos a execução
  é parcial. Falta de comparáveis não é erro de credencial.
- `--pricing-only` mostra colunas informativas, não evidência de venda nem scan
  validado. Não apresenta oportunidades confirmadas.

## 3. Entregar a tabela canônica, sem remontá-la

```powershell
.venv\Scripts\python ebay_summary.py results\last_scan_g3.json -o results\ebay-g3.md
```

O gerador vigente é `src/slab_report.py` (`render`). Para lote/parcial, passe o
arquivo efetivamente produzido, não um resultado anterior com nome parecido.
São 17 colunas no modo `longterm`, incluindo Tese / Entrada / Evidência; os modos
econômicos legados mantêm 14 colunas. O diagnóstico LP permanece separado.

1. Colar o Markdown **verbatim** no chat, com cabeçalho Coleta, todas as linhas,
   todos os vereditos, seções por carta e funil. Se longo, dividir sem omitir linhas.
2. Manter compra, investimento, referência, revenda, lucro, desconto, margem
   bruta, margem líquida e ROI diferenciados, além dos três eixos. Não renomear
   uma estimativa operacional atual como projeção de retorno em 3–5 anos.
3. Preservar `[oferta]` e `[referência]`; preço da referência também clicável,
   com URL da própria evidência. Fonte ausente é n/d, nunca busca genérica.
4. Reportar data/hora UTC, universo/lote, versão da política, **20%** quando
   esse for o piso utilizado, API usada/teto e causas de parcialidade.
5. Nenhuma compra, transferência ou recomendação é executada. Não publicar
   tabela, arquivo de teses ou dados de scan no GitHub.

`--sensitivity` só vale para artefatos do motor legado. Em JSON da política,
preservar o aviso do gerador; não reclassificar manualmente.

## Diagnóstico LP legado

A coluna LP de `src/longterm.py` permanece **informativa**, separada da tese do
novo crivo. `LP2 64/35 (4/5·9/11)` é classe · perfil/fragilidade · cobertura.
Ela não decide gate, veredito ou ranking. LP1 não equivale a tese favorável.
Perfil normalizado pelos componentes disponíveis pode parecer alto com lacunas;
fragilidade `0 (3/11)` significa nenhum problema detectado em só 3 testes,
não evidência impecável. Ausência é n/d; LP2* sinaliza limitação de cobertura.
Entregar a legenda original e os motivos, sem converter notas em probabilidades.

## Logística invariável

Item nos EUA e preço fixo são obrigatórios: destino operacional COMC mailbox,
Algona, WA. Lance atual de leilão não é preço de aquisição. Vault só é confirmado
com metadados; não deduzir autenticação ou vault pelo valor anunciado.
