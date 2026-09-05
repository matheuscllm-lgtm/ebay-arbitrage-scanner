# EBAY PSA — scanner de cartas certificadas

Busca cartas certificadas no eBay e compara com vendas concluídas PSA da mesma
carta, variante, idioma e nota. Mostra compra, custos, investimento, revenda, lucro,
desconto, margem e ROI. Classifica APROVAR / REJEITAR / REVISAR sem executar compra.

## Estratégia vigente

- Regra econômica: **lucro estimado acima de US$40 OU desconto superior a 30%**
  sobre a referência PSA ajustada. Lucro deve ser positivo e os custos conhecidos.
- BGS até PSA +5%; CGC até 40% da PSA; TAG 10 equivale a PSA 10 na comparação.
  Os limites por certificadora são sobre o preço do item e continuam obrigatórios.
- Nota 9,5 usa PSA 9 ×1,05. BGS 9,5 não acumula outro adicional. PSA 9,5 não existe.
- US$10 estimados para envios/impostos até COMC, incluindo saída do vault; uma vez.
- COMC: Elite US$2,50, venda 5%, saque informado 10%, armazenamento/segurança por
  120 dias (extremo superior do prazo informado de 90–120 dias).
- Revenda de outra certificadora exige vendas próprias.
- Idiomas e variantes separados, incluindo chinês simplificado/tradicional.
- Preço fixo, item nos EUA, somente certificado. Vault preferencial quando confirmado.
- Falta de evidência não aprova. Categorias especiais sem regra ficam em REVISAR.

As regras detalhadas estão em [docs/EBAY_PSA.md](docs/EBAY_PSA.md), as tarifas
consultadas em [docs/COMC_COSTS.md](docs/COMC_COSTS.md), os parâmetros em
[config.yaml](config.yaml), e as mudanças em [CHANGELOG.md](CHANGELOG.md).

## Executar

Python 3.12:

```bash
python -m pip install -r requirements.txt
python main.py --check-config
python main.py --list-groups
python main.py --group 3 --max-pages 1 --out results/last_scan.json
python ebay_summary.py results/last_scan.json -o results/report.md
python -m pytest -q
```

`--check-config` não acessa a rede: código 0 sem pendências, 2 com pendências;
configuração malformada falha. Null não significa custo zero; no armazenamento,
aciona a projeção parametrizada. Dispersão máxima: 30%; BGS 9,5 sem acumulação.
As escolhas conservadoras foram feitas sob [autonomia delegada](docs/AUTONOMOUS_REVIEW.md).
`--min-discount N` altera o braço de desconto da regra OR daquela execução;
`--min-price`, `--grades`, `--group` e `--max-pages` restringem a busca.
`--include-raw` é rejeitado. `--pricing-only` mostra colunas informativas,
sem validar oportunidades. Não usar o modo de colunas como evidência de venda.

`max_ebay_calls: 500` limita cada execução, incluindo busca, detalhes e novas
tentativas. Esgotar o limite interrompe a execução, preserva resultados anteriores
e grava um JSON parcial. Não equivale à cota diária da conta.

Credenciais: `EBAY_CLIENT_ID` e `EBAY_CLIENT_SECRET` no ambiente; nunca versionar.
No GitHub, a validação utiliza os secrets já cadastrados. Falta de credencial ou
falha de fonte retorna código diferente de zero e preserva o último scan completo.
Ver [SECURITY.md](SECURITY.md).

## Validação real e limites de cobertura

```bash
python validate_live.py --group 3 --limit 1
python validate_live.py --group 3 --limit 1 --general-query
python validate_live.py --group 3 --limit 3 --psa-grade 9
```

A primeira consulta foca PSA 10 com idioma e ano do catálogo para testar anúncio e vendas.
A segunda usa a query geral do scanner. São buscas pequenas de validação, não um
scan completo dos 12 grupos. O relatório registra os motivos de exclusão de vendas.
Código 0 exige anúncios reais e ao menos 3 vendas PSA aceitas; 2 indica evidência
parcial; 1 indica bloqueio/falha. Sucesso técnico não equivale a aprovação de compra.

No GitHub Actions, `Validate eBay credentials and sample` permite escolher grupo,
nota PSA e até três cartas em Run workflow. É execução manual, sem agendamento.
O JSON distingue `execution_status` e `evidence_status`; ausência de comparáveis
não é rotulada como erro de credencial. A correção dos nomes de coleção foi
validada com 188 anúncios reais e 83 linhas com amostra PSA suficiente;
ver [revisão de execução](docs/RUNTIME_REVIEW.md).

A watchlist é gerada por `build_watchlist.py`: não editar manualmente. A presença
de idiomas na configuração não significa que todas as coleções regionais tenham
catálogo validado. Anúncios sem idioma no título ou atributos explícitos ficam em REVISAR.
Os atuais comparáveis vêm das tabelas públicas do PriceCharting e exigem títulos
explícitos. Não se busca outra língua para preencher lacunas.

O JSON preserva configuração, cálculo, amostra, janela, links, datas e decisões.
O Markdown mostra todos os candidatos. Relatórios históricos continuam legíveis;
parâmetros antigos de sensibilidade não reclassificam o motor atual.

Estado de testes e busca real: [docs/VALIDATION_EBAY_PSA.md](docs/VALIDATION_EBAY_PSA.md).
Desenvolvimento em branch + PR. Não há compra, merge ou novo agendamento automático.
