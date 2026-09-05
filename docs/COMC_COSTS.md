# Custos COMC — fontes consultadas em 2026-09-05

Esta tabela documenta tarifas públicas, não comprova o plano contratado ou a taxa
particular da conta do operador. Dados indefinidos continuam bloqueando APROVAR.

| Despesa | Evidência pública | Aplicação no scanner |
|---|---|---|
| Venda em preço fixo | 5% do preço de venda | `selling_fee_percent: 5` |
| Saque | 10% base, com adicional internacional | operador informou 10%; configurado |
| Processamento de slab comum | Elite US$2,50; Select US$1,50; Standard US$1,25 | Elite confirmado: US$2,50 |
| Armazenamento | US$0,01 por item/mês quando preço pedido >US$0,75; isenções | projeção de 120 dias, faixa informada 90–120 |
| Segurança adicional | US$0,01 por US$1.000 de preço listado/dia acima de US$50; sem carência | deve integrar `comc_storage_usd` |

A tabela de consignação informa mínimos de lote de US$3 no Select e US$65 no
Standard. Não dividir esses mínimos sem conhecer o tamanho do lote. Select/Standard
limitam a listagem a US$100 e podem sofrer upgrade cobrado. Elite não possui esse
mínimo de lote na tabela publicada. Cartas oversized têm outras tarifas.

Fontes oficiais:

- [Comissões e saque](https://comc.zendesk.com/hc/en-us/articles/360053737993-What-are-the-commission-fees): venda de preço fixo e observação sobre saque internacional.
- [Consignação](https://comc.zendesk.com/hc/en-us/articles/360054029273-What-are-the-Consignment-Fees): tabela atualizada em 2026-08-10.
- [Armazenamento e segurança](https://comc.zendesk.com/hc/en-us/articles/360052957434-What-are-the-Storage-Fees-Enhanced-Security-Fees): armazenamento, isenções e segurança separados.
- [Saque internacional](https://comc.zendesk.com/hc/en-us/articles/10425159147035-Fee-Chart-for-International-Users): adicional sobre 10%.
- [PayPal e moeda de recebimento](https://comc.zendesk.com/hc/en-us/articles/9820353778459-Requesting-COMC-Credit-as-a-PayPal-Deposit): eventual adicional de moeda mostrado na conta.

Para fechar uma avaliação: definir serviço e custo de processamento por carta,
custo total de armazenamento **incluindo segurança adicional durante o prazo
estimado**, e taxa efetiva de saque/recebimento. Os US$10 confirmados pelo operador
cobrem envios/impostos de compra até a COMC, e não essas despesas COMC.

As fórmulas trabalham em USD. Conversão posterior a BRL e obrigações tributárias
pessoais não são conhecidas pelo scanner; não rotular o resultado como valor final
líquido recebido em reais.

Referências técnicas da busca:
- [eBay: filtros Browse](https://developer.ebay.com/api-docs/buy/static/ref-buy-browse-filters.html).
- [eBay: condição Graded 2750](https://developer.ebay.com/api-docs/sell/static/metadata/condition-id-values.html).

## Decisões do operador nesta revisão

- Serviço Elite confirmado: processamento de slab comum **US$2,50**.
- Saque efetivo informado pelo operador: **10%**. Este valor informado é o que
  rege a simulação; não afirmamos que ele foi lido da conta nem o substituímos
  por uma taxa internacional presumida.
- Prazo de 90–120 dias: a projeção usa **120 dias**, extremo superior informado.
- A projeção conta as datas de cobrança no primeiro dia do mês após a carência
  de 90 dias; a segurança é diária desde o início. Pressupõe carta consignada
  pelo operador, disponível para venda pelo período projetado e preço estimado
  constante. É uma estimativa, não uma fatura.
- A base de segurança usa preço pedido estimado +US$2 de acréscimo de envio ao
  comprador da carta certificada. O acréscimo **não é receita do vendedor** e
  **não é adicionado novamente** aos US$10 de aquisição.
  [Fonte oficial do acréscimo](https://comc.zendesk.com/hc/en-us/articles/1260804004650-Flat-Rate-shipping-and-per-item-shipping-fees-explainer).
- Se a carta permanecer mais tempo, se o preço listado mudar ou se a conta cobrar
  outra tarifa, reconfigurar e recalcular. Sem referência de revenda não há base
  para segurança: custo total continua pendente.
