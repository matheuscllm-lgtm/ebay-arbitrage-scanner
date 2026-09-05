# Estratégia EBAY PSA — versão 2026-09-05.2

O código, a configuração e os testes demonstram a implementação. As decisões do
operador nesta revisão substituem os filtros antigos. Base revisada: `86b8324`.

## Regras confirmadas

- Apenas cartas certificadas, com prioridade PSA, preço fixo e item nos EUA.
- Condição de busca eBay `2750` (Graded), repetindo as verificações no avaliador.
- Referência: vendas concluídas PSA da mesma carta, coleção, número, variante,
  idioma e nota. Preços pedidos e colunas de estimativas não substituem vendas.
- PSA não possui 9,5. Outras notas 9,5 usam PSA 9 ×1,05, sem conversão a PSA 10.
- BGS: preço do item até PSA ajustado +5%. A combinação BGS 9,5 permanece
  pendente até decisão explícita; não acumular percentuais silenciosamente.
- CGC: preço do item até 40% da referência PSA ajustada, confirmado pelo operador.
- TAG 10: comparação 1:1 com PSA 10; TAG 9,5 usa a regra geral PSA 9 ×1,05.
- Pristine e Black Label permanecem REVISAR sem regra específica. A identificação
  da categoria e suas vendas próprias são preservadas; não há prêmio pelo nome.
- Compra no vault é preferencial quando confirmada. Saída operacional: COMC.
  O scanner não depende de listar no vault e não executa compras ou transferências.

## Aprovação econômica: lucro OU desconto

O operador definiu: lucro estimado **acima de US$40 OU desconto superior a 30%**.
Os limites são estritos: exatamente US$40 ou 30% não satisfazem aquele braço da regra.
Margem e ROI são informativos, sem mínimos adicionais. O modo atual é
`economics.gate_mode: profit_or_discount`.

- Desconto = (referência PSA ajustada − preço de compra) / referência ×100.
- Investimento = compra + US$10 + processamento COMC + armazenamento/segurança.
- Líquido da venda = revenda ×(1 − taxa de venda/100) ×(1 − taxa de saque/100).
- Lucro = líquido da venda − investimento.
- Margem líquida sobre a venda = lucro / revenda bruta ×100.
- ROI líquido = lucro / investimento ×100.

Os limites entre certificadoras são independentes da regra econômica: um CGC
acima de 40% da PSA é REJEITAR mesmo se o lucro projetado for alto. Cumprir um
limite entre certificadoras não satisfaz, sozinho, as exigências de lucro/evidência.
O filtro global antigo de 20% e o alerta genérico de ROI elevado não atuam no modo
atual. `--min-discount` altera o braço de desconto da regra OR para aquela execução.

Mesmo passando pelo desconto, lucro não positivo é REJEITAR. Custos ausentes,
revenda não comprovada ou outra dúvida relevante exigem REVISAR. APROVAR indica
somente aprovação analítica. Não é promessa de preço futuro nem compra executada.

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

Idioma deve ser explícito no título ou no atributo Language retornado pelo eBay;
não assumir inglês por ausência de informação ou pela
localização do vendedor. EN, JP, KO, PT, DE, FR, IT, ES, ZH-HANS (simplificado) e
ZH-HANT (tradicional) são identidades distintas. Chinês genérico é ambíguo.
A configuração não garante cobertura do catálogo: a watchlist atual e os títulos
disponíveis limitam quais idiomas/cartas realmente podem ser avaliados.

Cada venda precisa ter origem eBay, ID, preço positivo e data válida não futura.
Oferta aceita sem preço efetivo confirmado fica fora. Vendas repetidas contam uma
vez. Anúncios com IDs diferentes permanecem visíveis mesmo se título/preço coincidirem.
Ausência de garantia de autenticidade ou metadados de vault não é confirmação;
não deduzir esses recursos pelo preço do anúncio.

Mínimo de 3 vendas em 180 dias; na falta delas, janela de 365 dias com REVISAR por
baixa liquidez. Uma ou duas vendas também exigem REVISAR. A mediana usa até 10
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

## Execução e falhas

`main → run_scan → scan_card → evaluate` aplica a política atual. A compatibilidade
com cálculos históricos existe para testes/artefatos antigos, não é o padrão CLI.
Configuração malformada falha antes de acessar fontes. Arquivo solicitado inexistente
não carrega defaults silenciosamente. `python main.py --check-config` lista pendências.

Falhas de fonte ou processamento tornam a execução parcial, inclusive quando outras
cartas puderam ser processadas. JSON é gravado de modo atômico e rejeita NaN/Infinity.
Busca parcial não sobrescreve o último resultado completo. Ausência de credenciais
não executa consulta nem sobrescreve o último resultado. `--include-raw` é rejeitado.

A validação pontual usa uma carta, uma página e query PSA 10 com idioma e ano do catálogo,
para exercitar ambos os coletores. Não representa o universo inteiro do scanner.
`--general-query` testa a consulta geral. Sucesso técnico exige anúncios reais e pelo
menos 3 vendas PSA aceitas em uma linha; não significa oportunidade aprovada.

Ordem: consolidar regras → implementar → testar → validar busca real → automatizar.
Não há novo agendamento nem merge automático. O PR registra separadamente testes
locais, CI e validação real em [VALIDATION_EBAY_PSA.md](VALIDATION_EBAY_PSA.md).

## Definições ainda ausentes

`max_dispersion_percent` segue null e impede APROVAR até definição do operador.
A combinação dos percentuais BGS 9,5 também segue null; afeta essa nota, sem
autorizar acumular os dois acréscimos. Casos sem referência de revenda continuam
sem base para estimar segurança e lucro, mesmo com as tarifas já configuradas.
