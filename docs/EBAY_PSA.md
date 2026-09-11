# Estratégia EBAY PSA — versão 2026-09-11.1

O código, a configuração e os testes demonstram a implementação. As decisões do
operador nesta revisão substituem o gate exclusivamente de margem bruta.

## Regras confirmadas

- Modo padrão `longterm`: apenas PSA 10, EN/JP, preço fixo, item nos EUA e preço
  do item até US$500, antes de frete/impostos. Análise, nunca compra automática.
- Condição de busca eBay `2750` (Graded), repetindo as verificações no avaliador.
- Referência: vendas concluídas PSA da mesma carta, coleção, número, variante,
  idioma e nota. Preços pedidos e colunas de estimativas não substituem vendas.
- Os modos legados explícitos preservam as regras abaixo para outras notas e
  certificadoras; elas não ampliam o escopo PSA 10 do modo `longterm`.
- PSA não possui 9,5. Outras notas 9,5 usam PSA 9 ×1,05, sem conversão a PSA 10.
- BGS: preço do item até PSA +5%. BGS 9,5 usa PSA 9 ×1,05 como referência e teto,
  sem acumular outro adicional, conforme decisão sob autonomia delegada.
- CGC: preço do item até 40% da referência PSA ajustada, confirmado pelo operador.
- TAG 10: comparação 1:1 com PSA 10; TAG 9,5 usa a regra geral PSA 9 ×1,05.
- Pristine e Black Label permanecem REVISAR sem regra específica. A identificação
  da categoria e suas vendas próprias são preservadas; não há prêmio pelo nome.
- Compra no vault é preferencial quando confirmada. Saída operacional: COMC.
  O scanner não depende de listar no vault e não executa compras ou transferências.

## Crivo vigente: tese, entrada e evidência

O modo padrão é `economics.gate_mode: longterm`, com
`min_gross_margin_percent: 20`: **20%**, limite estrito; exatamente 20% não satisfaz.
A margem continua visível para comparabilidade histórica, mas **não aprova sozinha**.

| Eixo | Exigência para OPORTUNIDADE | Quando não atende |
|---|---|---|
| Tese | Quatro sinais documentados e atuais; ≥3 favoráveis, incluindo demanda, sem adversos | Tese neutra: MONITORAR; desfavorável: REJEITAR; ausente/incompleta: REVISAR |
| Entrada | Margem bruta >20%, lucro líquido operacional atual positivo e custos completos | Preço insuficientemente atrativo: MONITORAR; custos desconhecidos: REVISAR |
| Evidência | Comparáveis exatos, vendedor verificável, dispersão aceitável e recorrência observada | Dúvida ou baixa cobertura: REVISAR; incompatibilidade estrutural: REJEITAR |

São exigências conjuntas, não uma soma em que popularidade compensa falta de
liquidez. Uma restrição de identidade/segurança prevalece sobre margem ou tese.
OPORTUNIDADE é classificação técnica, não recomendação ou ordem de compra.

Teses vêm de arquivo privado via `--thesis-file`: demanda, importância
colecionável, oferta e resiliência devem ter direção (`supportive`, `neutral` ou
`adverse`), fonte, data e justificativa. Prazo padrão de revisão: 180 dias.
LP1, raridade SIR, idade do set, população baixa ou multiplicador raw ×3 não
substituem esses dados. Esquema e limitações em [LONGO_PRAZO.md](LONGO_PRAZO.md).

### Entrada e custos: denominadores explícitos

- Margem bruta = (**revenda comprovada da própria certificadora** − preço do item)
  / preço do item ×100. A base é `resale_evidence`, nunca preço pedido nem
  referência de outra certificadora usada como revenda automática.
- Desconto do item = (referência comparativa − preço do item) / referência ×100.
  Não confundir o piso de margem de **20%** com desconto de 20%.
- O teto US$500 incide sobre o item. O investimento inclui os custos abaixo;
  uma referência sem custos completos não permite afirmar entrada líquida positiva.

- Investimento = compra + US$10 + processamento COMC + armazenamento/segurança.
- Líquido da venda = revenda ×(1 − taxa de venda/100) ×(1 − taxa de saque/100).
- Lucro = líquido da venda − investimento.
- Margem líquida sobre a venda = lucro / revenda bruta ×100.
- ROI líquido = lucro / investimento ×100.

O modelo de custos em 120 dias testa a viabilidade de saída aos preços atuais;
**não é previsão de retorno líquido em 3–5 anos**. Não são gerados cenários de
preços conservador/base/otimista nem probabilidades artificiais de valorização.

**Dois tetos distintos, nenhum deles uma recomendação all-in:**

- `comparison_cap` é o teto de comparação da certificadora; no modo legado
  `gross_margin`, incorpora o limite desse gate. No modo `longterm`, não indica
  por si só uma entrada elegível.
- `entry_item_cap`, exibido como **Teto condicional do item**, é o menor limite
  compatível com margem bruta >20%, lucro líquido operacional positivo e item
  até US$500. A margem exige `preço < revenda / 1,20`; a condição líquida também
  é estrita, respeitando o centavo. Esse teto ainda depende de tese favorável e
  evidência adequada: nunca compensa tese ausente ou evidência fraca.

**Margem absurda pede conferência de identidade.** O gate só tem piso, então uma margem de
centenas de por cento — assinatura clássica de referência errada ou carta trocada — chegaria
a uma classificação indevida. `economics.suspicious_gross_margin_percent: 150` marca essas linhas
como REVISAR (nunca REJEITAR por margem elevada, isoladamente). É alerta de possível
erro de identidade/referência, não prova de fraude.

### Compatibilidade histórica

`gross_margin` continua disponível explicitamente: aplica só o piso de margem e
mantém custos informativos, conforme a política anterior. `profit_or_discount`
(`min_profit_usd` OU `min_discount_percent`) e `all_minima` (`min_net_*`) também
continuam no código. Apenas o modo configurado decide a execução; não misturar
suas fórmulas. A versão anterior usava 43%; o padrão desta revisão usa **20%**.

Os limites entre certificadoras são independentes da regra econômica: um CGC
acima de 40% da PSA é REJEITAR mesmo se o lucro projetado for alto. Cumprir um
limite entre certificadoras não satisfaz, sozinho, os demais requisitos do modo.
`--min-discount` só atua nos modos legados que usam desconto;
`--min-gross-margin` altera o piso apenas em `gross_margin`; `longterm` mantém
**20%** e rejeita outro valor. Os modos legados preservam
APROVAR / REVISAR / REJEITAR; APROVAR é somente aprovação analítica.

PSA é referência comparativa; revenda de CGC, BGS ou TAG exige vendas da própria
certificadora, nota, idioma e categoria. Não usar o valor PSA como revenda automática.
Valores são comparados em Decimal antes de arredondar. O JSON preserva a mediana e
a referência ajustada exatas, além dos valores arredondados de exibição.

## Custos confirmados e pendências

Os US$10 são **estimativa**, uma única vez, para todos os envios e impostos de compra
até a COMC, inclusive eventual saída do vault. Cobertura confirmada pelo operador.
Não representam gasto efetivamente realizado. Frete observado é informativo e não
é somado novamente; ausência de frete é `null`, nunca frete grátis.

Processamento, armazenamento/segurança, venda e saque COMC ficam separados dessa
estimativa. Elite custa US$2,50 por slab comum; o operador informou saque de 10%.
A venda de preço fixo usa 5% conforme fonte oficial. O prazo informado de 90–120
dias é calculado pelo extremo superior, 120 dias, incluindo segurança adicional.
Detalhes, hipóteses e fontes em [COMC_COSTS.md](COMC_COSTS.md).

O subtotal conhecido é exibido mesmo com pendências. Investimento completo só é
exibido com todos os custos de entrada; lucro só com revenda e custos de saída.
O resultado é denominado estimativa operacional em USD, não lucro realizado em BRL.

## Identificação e qualidade da evidência

Nome, coleção, número e denominador devem ser compatíveis. Mew não casa com Mewtwo;
cartas ex/V/GX etc. não casam com nomes sem esses sufixos. Base Set 2 não é Base Set.
Variantes devem ter os mesmos modificadores em anúncio e venda. Lotes, réplicas,
acessórios e certificação apenas potencial não podem aprovar.

Códigos administrativos de catálogo (SV10:, SWSH09: etc.) não são parte do nome
da coleção. São removidos para descoberta e comparação, sem remover nomes de
subconjuntos. Apóstrofos e LV.X/LVX são normalizados; número e sufixo da carta
continuam obrigatórios. Evidência de execução em [RUNTIME_REVIEW.md](RUNTIME_REVIEW.md).

Idioma deve ser explícito no título ou no atributo Language retornado pelo eBay;
não assumir inglês por ausência de informação ou pela
localização do vendedor. EN e JP são identidades distintas no padrão atual.
Os idiomas dos modos legados, incluindo ZH-HANS (simplificado) e ZH-HANT
(tradicional), também permanecem separados. Chinês genérico é ambíguo.
A configuração não garante cobertura do catálogo: a watchlist atual e os títulos
disponíveis limitam quais idiomas/cartas realmente podem ser avaliados.

Reimpressão repete NOME e NÚMERO da carta original, e o vendedor escreve no título
o set ESTAMPADO na carta — a Celebrations: Classic Collection (2021) reimprime o Base
Set inteiro mantendo #4/102. Por isso nome + número + "Base Set" NÃO identificam
edição. As edições que colidem são DERIVADAS da watchlist (`colliding_editions`,
preenchido em `scanner.load_watchlist`), nunca lista mantida à mão: carta nova entra
já protegida. Três faixas, por força da evidência:

| Evidência no anúncio | Tratamento | Motivo |
|---|---|---|
| Alias inequívoco de outra tiragem ("Celebrations", "Classic Coll") | rejeita a associação | `outra-edicao` |
| Ano citado incompatível com a edição candidata | sem aprovação automática; sem comparação | `conflito-de-ano` |
| Colide com reimpressão que estampa o mesmo set, sem ano e sem alias | identidade insuficiente | `edicao-ambigua` |
| Carta que não colide com nenhuma outra edição | nada muda | — |

O termo mais LONGO vence o mais curto: "Celebrations Classic" e "Base Set 2" ganham
de "Base Set". No EMPATE de comprimento ganha a edição da própria carta — sem essa
regra o alias `celebrations` (da Classic Collection) empatava com o rótulo do set-pai
homônimo `Celebrations` e rejeitava as 14 cartas dele, junto com a cesta de vendas
delas. Há varredura de título canônico em teste para essa classe inteira de erro. `EDITION_ALIASES` só aceita apelido comprovado em anúncio real;
alias por hipótese rejeita carta legítima, que é o dano caro. Ano vem de
`title_parser.card_year_candidates`, que ignora fração ("4/102"), número de
certificado e sequência dentro de dígitos — confundir um deles com ano rejeitaria
carta boa. Na CESTA DE VENDAS só contradição exclui (`outra-edicao`,
`conflito-de-ano`); ambiguidade nunca exclui venda, porque a venda legítima que apenas
não cita o ano é a maioria da cesta e tirá-la moveria a mediana.

Cada venda precisa ter origem eBay, ID, preço positivo e data válida não futura.
Oferta aceita sem preço efetivo confirmado fica fora. Vendas repetidas contam uma
vez. Anúncios com IDs diferentes permanecem visíveis mesmo se título/preço coincidirem.
Ausência de garantia de autenticidade ou metadados de vault não é confirmação;
não deduzir esses recursos pelo preço do anúncio.

Para formar a referência, mínimo de 3 vendas em 180 dias; na falta delas, janela
de 365 dias com REVISAR por baixa liquidez. Uma ou duas vendas também exigem
REVISAR. O crivo `longterm` exige adicionalmente ≥9 vendas comparáveis observadas
em 90 dias, em ≥2 meses-calendário, antes de limitar a amostra da mediana.
Isso aproxima o corte de 3 vendas/mês sem afirmar cobertura integral do eBay ou
contagem de compradores únicos. A mediana usa até 10
vendas mais recentes. Dispersão = (máximo − mínimo)/mediana ×100, calculada antes
do arredondamento. Limite de dispersão indefinido exige REVISAR.

Anúncios elegíveis sem idioma no título recebem consulta getItem limitada a 10
por carta (limite operacional configurável). Todas as chamadas contam na cota.
Somente atributos selecionados são guardados. Conflitos de idioma, coleção,
número, certificadora ou nota exigem REVISAR. Os atributos são declarações do
vendedor; não são verificação independente do certificado. O idioma das vendas
continua exigindo título explícito; não se presume idioma pela página agregadora.

O JSON registra vendas incluídas, IDs, links, datas, amostra, janela, dispersão,
data de avaliação e contagens por motivo de exclusão. O relatório mostra todos os
candidatos, idioma do alvo separado do idioma identificado e vault não confirmado.

## Universo e processamento sem quota

Não há requisito de encontrar 100 cartas elegíveis. A lista de 100 personagens
do catálogo não é Top100 de investimento. O gerador da watchlist deixa de impor
teto por set por padrão; o catálogo versionado não é regenerado nesta alteração.
Seu universo continua condicionado aos filtros e metadados disponíveis.

`--max-cards` é orçamento opcional de processamento; `--card-offset` seleciona
o início do lote em ordem determinística. Não alteram elegibilidade, não
completam uma quota e não tornam dados ausentes favoráveis. Quantidades adiadas
e resultado parcial são explícitos. Lotes usam saídas próprias; consultas
posteriores renovam preços, sem retomar preços de scans antigos.

## Execução e falhas

`main → run_scan → scan_card → evaluate` aplica a política atual. A compatibilidade
com cálculos históricos existe para testes/artefatos antigos, não é o padrão CLI.
Configuração malformada falha antes de acessar fontes. Arquivo solicitado inexistente
não carrega defaults silenciosamente. `python main.py --check-config` lista pendências.

Falhas de fonte ou processamento tornam a execução parcial, inclusive quando outras
cartas puderam ser processadas. JSON é gravado de modo atômico e rejeita NaN/Infinity.
Busca parcial não sobrescreve o último resultado completo. Ausência de credenciais
não executa consulta nem sobrescreve o último resultado. `--include-raw` é rejeitado.
CSV parcial também usa arquivo `.aborted.csv`; o aviso de busca parcial abre o relatório.

A validação pontual usa uma carta, uma página e query PSA 10 com idioma e ano do catálogo,
para exercitar ambos os coletores. Não representa o universo inteiro do scanner.
`--general-query` testa a consulta geral. Sucesso técnico exige anúncios reais e pelo
menos 3 vendas PSA aceitas em uma linha; não significa oportunidade aprovada.

Ordem: consolidar regras → implementar → testar → validar busca real → automatizar.
Não há novo agendamento nem merge automático. O PR registra separadamente testes
locais, CI e validação real em [VALIDATION_EBAY_PSA.md](VALIDATION_EBAY_PSA.md).

## Decisões sob autonomia delegada

Dispersão máxima de 30% e BGS 9,5 sem acumular acréscimos foram escolhidos pelo
agente sob a autorização posterior do operador. Justificativa e resultados em
[AUTONOMOUS_REVIEW.md](AUTONOMOUS_REVIEW.md). A configuração padrão está completa;
dados ausentes de anúncios/vendas continuam exigindo REVISAR. O teto operacional
é 500 chamadas eBay por execução, incluindo detalhes e retentativas. Ao esgotar,
a execução fica parcial, sem substituir o último JSON completo.
