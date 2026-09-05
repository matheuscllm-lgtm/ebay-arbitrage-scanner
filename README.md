# EBAY PSA — scanner de cartas certificadas

Compara anúncios de preço fixo do eBay com **vendas concluídas PSA** da mesma
carta, coleção, número, variante e idioma. Calcula custos, investimento, revenda,
lucro, margem líquida e ROI. Cada candidato recebe **APROVAR**, **REJEITAR** ou
**REVISAR**, com motivos e vendas rastreáveis. Nenhuma compra é executada.

A configuração canônica é [`config.yaml`](config.yaml); as regras e fórmulas
estão em [`docs/EBAY_PSA.md`](docs/EBAY_PSA.md). O histórico está no
[`CHANGELOG.md`](CHANGELOG.md). As regras de 2026-09-05 substituem o método
anterior de spread bruto e a opção de cartas sem certificação.

## Regras principais

- Somente cartas certificadas; PSA tem prioridade.
- BGS: teto de compra de PSA comparável +5%, além dos filtros econômicos.
- Nota 9,5: referência PSA 9 ×1,05; nunca PSA 10. A combinação desse ajuste
  com o adicional BGS permanece indefinida, portanto BGS 9,5 exige REVISAR.
- TAG 10 = PSA 10 para comparação. Revenda TAG/BGS exige vendas da própria
  certificadora; equivalência não garante o mesmo valor de revenda.
- CGC sem regra: REVISAR. Categorias especiais não ganham prêmio automático.
- Idiomas separados. Idioma ausente não é interpretado como inglês.
- US$10 por slab como reserva de envio/taxas, contabilizada uma vez.
- Compra no vault preferencial quando confirmada; revenda pela COMC.
  O scanner não depende de listagem direta no vault.

**Pendências explícitas:** cobertura detalhada dos US$10, custos de processamento,
armazenamento, venda e saque COMC e sua base de incidência; limites de lucro,
margem, ROI e dispersão; regra CGC e combinação dos percentuais BGS 9,5.
Enquanto faltarem dados necessários, o resultado será REVISAR (ou REJEITAR
quando uma regra já for violada). Não há custos zero presumidos.

## Executar

Python 3.12:

```bash
python -m pip install -r requirements.txt
python main.py --list-groups
python main.py --group 3 --max-pages 1 --out results/last_scan.json
python ebay_summary.py results/last_scan.json -o results/report.md
python -m pytest -q
```

As variáveis `EBAY_CLIENT_ID` e `EBAY_CLIENT_SECRET` devem estar disponíveis
no ambiente. Nunca versionar credenciais; ver [`SECURITY.md`](SECURITY.md).
Sem elas, a busca real encerra com código 1 e preserva o resultado anterior.
`--pricing-only` consulta apenas colunas informativas; não valida oportunidades.
`--include-raw` é rejeitado. Os filtros `--group`, `--grades`, `--min-discount`,
`--min-price` e `--max-pages` permanecem disponíveis.

O JSON guarda configuração, decisões, custos, ajustes, quantidade de vendas,
janela, dispersão e links/data/preço de cada venda usada na mediana. O relatório
mostra todos os candidatos avaliados, inclusive sem referência e abaixo do filtro.
Relatórios antigos continuam legíveis pelo `ebay_summary.py`; a sensibilidade
legada não reclassifica decisões do novo motor.

## Catálogo e validação

A watchlist versionada é gerada por `build_watchlist.py` a partir do catálogo de
123 coleções e 100 Pokémon, em 12 grupos. Não editar `watchlist.yaml` manualmente.
A cobertura atual da lista não implica cobertura de todos os idiomas: acrescentar
alvos e páginas corretas quando necessário, mantendo cada idioma separado.

```bash
python build_watchlist.py --groups 3-4 --cap 30
```

As fixtures e os testes econômicos são offline. Ver
[`docs/VALIDATION_EBAY_PSA.md`](docs/VALIDATION_EBAY_PSA.md) para distinguir testes
locais, verificação em CI e validação de busca real.
