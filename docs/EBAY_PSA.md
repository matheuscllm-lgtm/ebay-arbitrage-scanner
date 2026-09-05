# Estratégia EBAY PSA — 2026-09-05

Fonte: instruções do projeto fornecidas pelo operador. Implementação inicial
baseada na main `2ed6cc76027e40ba9c96eea45cf31d4ae3fff6fc` do
`matheuscllm-lgtm/ebay-arbitrage-scanner`. O scanner PSA-Arbitrage-Scanner citado
em histórico é outro projeto; não foi alterado.

## Fontes e identidade

O eBay Browse fornece anúncios ativos de preço fixo. O parser existente lê as
tabelas de vendas concluídas do PriceCharting; o novo motor usa apenas registros
identificados como vendas eBay, com ID, data não futura e preço positivo finito.
Preços de anúncios ativos e colunas genéricas não são referência de venda.
Títulos com indicação de oferta aceita, sem preço efetivo verificável, são excluídos.
Os links eBay são construídos a partir dos IDs de venda presentes na fonte.

Cada venda precisa confirmar nome, coleção, número, variante, idioma, certificadora,
nota e categoria identificável. Página do produto não substitui identidade da venda.
Coleções mais longas, como Base Set 2, não podem casar com Base Set. Denominadores
diferentes de uma fração informada não podem casar. Títulos incompletos ou aliases
não reconhecidos reduzem cobertura e ficam sem referência; não são inferidos.

EN, JP, ZH, KO, PT, DE, FR, IT e ES são códigos separados. O idioma tem de ser
explícito no título tanto do anúncio quanto da venda. Mais de um idioma ou idioma
ausente não confirma a comparação. Não há equivalência entre idiomas asiáticos
nem pressuposto de valorização da versão inglesa.

São preservados da versão anterior: mínimo de 3 vendas, janela primária de 180 dias,
janela ampliada de 365 dias e mediana das 10 mais recentes. O artefato distingue
quantidade na janela e quantidade usada na mediana. IDs duplicados contam uma vez.
A janela ampliada gera REVISAR por baixa liquidez; 1–2 vendas também. Dispersão é
`(máximo − mínimo)/mediana × 100`, calculada sobre a amostra da mediana. Seu limite
não foi definido pelo operador: fica null, exige REVISAR e aparece no relatório.

## Referência PSA e revenda

| Certificação | Referência econômica | Limite / ressalva |
|---|---|---|
| PSA 8/9/10 | PSA da mesma nota | Vendas da mesma carta, variante e idioma |
| BGS 9/10 | PSA da mesma nota | Compra ≤ referência ×1,05; filtros econômicos adicionais |
| BGS 9,5 | PSA 9 ×1,05 | Combinação com adicional BGS indefinida: REVISAR |
| TAG 10 | PSA 10 | Equivalência estratégica; não garante revenda TAG a esse preço |
| TAG 9,5 | PSA 9 ×1,05 | Regra geral da nota 9,5 |
| CGC | Regra ausente | REVISAR |
| Outras certificadoras/notas | Sem equivalência configurada | REVISAR ou REJEITAR por escopo explícito |

PSA não possui 9,5: esse título recebe REJEITAR. BGS Black Label e categorias
Pristine são identificadas e reportadas, sem prêmio automático. Black Label exige
vendas Black Label para estimar revenda; BGS 10 comum não substitui essa categoria.

Para BGS 9,5, `combine_9_5_premium: null` bloqueia aprovação e mantém o teto
indefinido. Uma decisão futura explícita `false` representa teto PSA 9 ×1,05;
`true` representa teto PSA 9 ×1,05 ×1,05. Nenhuma das opções foi presumida.

O limite de compra BGS considera o preço do item; custos são tratados à parte.
TAG/BGS usam vendas da própria certificadora/nota/categoria para estimar revenda.
O JSON separa PSA original, referência ajustada, teto e vendas de revenda.

## Custos e fórmulas reproduzíveis

A reserva é de US$10 por carta, uma única vez. `covers: [shipping, taxes]` declara
a categoria agregada definida pelo operador; `coverage_confirmed: false` registra
que seus trechos de envio e tributos exatos ainda precisam ser confirmados. O frete
observado no anúncio é mostrado e não somado novamente. Até a confirmação, somente
um subtotal conhecido é apresentado; investimento completo e lucro ficam pendentes.
Outra composição de cobertura exige adaptação explícita, nunca soma silenciosa.

Processamento e armazenamento COMC são campos separados, ainda indefinidos.
Taxas de venda e saque também permanecem null. Zero só é válido quando explicitamente
configurado. Não foram copiadas taxas Probstein, pois são outra rota operacional.

Quando a cobertura, todos os custos e a incidência estiverem definidos:

- Investimento = compra + reserva de US$10 + processamento + armazenamento.
- No modelo suportado `sale_then_cashout`: líquido da venda = revenda ×
  (1 − taxa de venda/100) × (1 − taxa de saque/100).
- Lucro = líquido da venda − investimento.
- Margem líquida sobre a venda = lucro / revenda bruta ×100.
- ROI líquido = lucro / investimento ×100.
- Desconto = (referência PSA ajustada − compra) / referência PSA ajustada ×100.

Os cálculos usam Decimal e comparam limites antes do arredondamento de exibição.
Desconto mínimo de 20%, piso de US$10, país US e preço fixo vêm da configuração
anterior. Os limites mínimos de lucro, margem líquida e ROI não estão definidos:
null bloqueia APROVAR. Lucro não positivo é REJEITAR quando todos os custos necessários
estão presentes. Desconto suficiente sozinho não comprova rentabilidade.

## Operação, resultados e continuidade

Compra pode ocorrer no vault, preferencial quando confirmada por metadados confiáveis.
O adaptador Browse atual não confirma vault; `vault_confirmed` fica null. Um título
mencionando vault não é prova. O desempate prioriza vault confirmado entre candidatos
com mesma decisão, prioridade PSA e ROI. A rota de revenda é COMC; não há criação
de anúncio no vault, compra automática, transferência ou envio de mensagens.

APROVAR é classificação analítica; REJEITAR tem regra violada; REVISAR tem pendência.
Uma violação confirmada prevalece sobre dados faltantes, mas ambos os motivos são
registrados. Candidatos sem referência permanecem na entrega. Não se usa pontuação
de confiança para aprovar. O limiar anterior de ROI bruto elevado sinaliza REVISAR.

O fluxo de produção `main → run_scan → scan_card → scorer.evaluate` recebe sempre
`slab_strategy`, inclusive com arquivo de configuração alternativo sem essa seção.
O código antigo de scorer permanece para testes históricos e leitura de artefatos;
o entrypoint de produção não pode selecionar o método antigo por ausência de política.
A análise da mediana de preços pedidos do fluxo antigo não modifica o novo motor.

Ordem de evolução: consolidar regras → implementar → testar → validar uma busca real
→ automatizar. A configuração incompleta não impede desenvolvimento ou revisão do PR;
impede APROVAR oportunidades. Não há novo agendamento nesta implementação.
