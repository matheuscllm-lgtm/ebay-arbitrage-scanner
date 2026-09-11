> **Regra vigente de entrega:** [DELIVERY_CHAT.md](DELIVERY_CHAT.md). Resultados somente no chat, referência clicável e coleta nova por solicitação; substitui orientações antigas de entrega via GitHub ou preços reutilizados.

# EBAY PSA — scanner de cartas certificadas

Busca PSA 10 no eBay e compara com vendas concluídas da mesma carta, variante,
idioma e nota. A política padrão separa **tese, entrada e evidência**: margem
bruta sozinha não basta. Classifica OPORTUNIDADE / MONITORAR / REVISAR / REJEITAR,
sem recomendar nem executar compra.

## Estratégia vigente

- Versão 2026-09-11.1, `gate_mode: longterm`: PSA 10, inglês/japonês separados,
  preço fixo, item nos EUA e preço do item até US$500, antes de frete/impostos.
- **Tese:** demanda perene, importância colecionável, oferta e resiliência,
  documentadas em arquivo privado via `--thesis-file`. Exige os quatro sinais
  atuais, pelo menos três favoráveis (incluindo demanda) e nenhum adverso.
- **Entrada:** `min_gross_margin_percent: 20` — **20%**, estritamente acima,
  calculados como `(revenda − item) / item ×100`, não como desconto.
  Além disso, lucro líquido operacional atual positivo e custos completos.
- **Evidência:** identidade exata, vendedor verificável, dispersão aceitável e
  pelo menos 9 vendas comparáveis observadas em 90 dias, em 2 meses-calendário ou
  mais. A contagem vem antes do corte da mediana; não é volume total do eBay.
- US$10 estimados para envios/impostos até COMC, incluindo saída do vault; uma vez.
- COMC: Elite US$2,50, venda 5%, saque informado 10%, armazenamento/segurança por
  120 dias. Isso é uma estimativa de saída atual, não retorno previsto em 3–5 anos.
- Tese boa com entrada fraca fica MONITORAR; ausência de tese/dados fica REVISAR;
  risco estrutural ou tese desfavorável fica REJEITAR. Zero oportunidades é válido.
- `gross_margin`, `profit_or_discount` e `all_minima` continuam disponíveis como
  modos legados explícitos, inclusive regras de outras certificadoras. Não são o padrão.

A tabela mantém a coluna LP **legada e informativa**: `LP2 64/35 (4/5·9/11)`
= classe · PERFIL (características observadas da carta: personagem, raridade, tempo fora de
impressão, faixa da coluna PSA 10, tendência real das vendas) / FRAGILIDADE DO DADO (poucas
vendas na referência, PSA 10 pouco vendida, referência desalinhada, reimpressão, tiragem,
dispersão, vendedor, concentração de anúncios, meses de estoque) · coberturas (`4/5` = 4 dos 5 componentes tinham
dado; ausente é `n/d`, nunca zero). O PERFIL é uma média, então o componente ausente sai da conta;
a FRAGILIDADE é uma soma, então ela mede os problemas **detectados entre os testes que puderam
rodar** — leia-a sempre junto com a cobertura (`0 (3/11)` não é "dado impecável"). As classes vão
de LP1 (forte) a LP4 (frágil), e `LP2*` marca "seria LP1, mas faltou dado" (insumo-chave em `n/d`
ou cobertura da fragilidade abaixo do piso). Essa coluna **não** entra no gate, no veredito,
no ranking nem substitui a tese documentada do novo crivo. Seus
pontos são calibração inicial, ainda não validada contra o mercado. Régua completa em
[docs/LONGO_PRAZO.md](docs/LONGO_PRAZO.md).

As regras detalhadas estão em [docs/EBAY_PSA.md](docs/EBAY_PSA.md), as tarifas
consultadas em [docs/COMC_COSTS.md](docs/COMC_COSTS.md), os parâmetros em
[config.yaml](config.yaml), e as mudanças em [CHANGELOG.md](CHANGELOG.md).

## Executar

Python 3.12:

```bash
python -m pip install -r requirements.txt
python main.py --check-config
python main.py --list-groups
python main.py --group 3 --max-pages 1 --max-cards 25 --card-offset 0 --thesis-file data/theses.yaml --out results/last_scan.json
python ebay_summary.py results/last_scan.json -o results/report.md
python -m pytest -q
```

`--check-config` não acessa a rede: código 0 sem pendências, 2 com pendências;
configuração malformada falha. Null não significa custo zero; no armazenamento,
aciona a projeção parametrizada. Dispersão máxima: 30%; BGS 9,5 sem acumulação.
As escolhas conservadoras foram feitas sob [autonomia delegada](docs/AUTONOMOUS_REVIEW.md).
`--min-gross-margin N` ajusta o piso no modo legado `gross_margin`; no modo
`longterm`, **20%** é fixo e outro valor é rejeitado;
`--min-discount N` só altera o braço de desconto dos modos legados;
`--min-price`, `--grades`, `--group` e `--max-pages` restringem a busca.
`--include-raw` é rejeitado. `--pricing-only` mostra colunas informativas,
sem validar oportunidades. Não usar o modo de colunas como evidência de venda.

`--thesis-file` é opcional: sem ele, a tese fica não confirmada e nenhuma linha
vira OPORTUNIDADE só pela margem. O arquivo é privado e não deve ser versionado.
Datas, fontes e justificativas são preservadas nos resultados locais.

`max_ebay_calls: 500` limita cada execução, incluindo busca, detalhes e novas
tentativas. Esgotar o limite interrompe a execução, preserva resultados anteriores
e grava um JSON parcial. Não equivale à cota diária da conta.

Credenciais: `EBAY_CLIENT_ID` e `EBAY_CLIENT_SECRET` no ambiente; nunca versionar.
Não executar scans nem publicar seus resultados no GitHub. Falta de credencial ou
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

Só fazer validação real quando o operador solicitar coleta; alterações de código
usam testes offline. Workflows históricos não autorizam scans no GitHub Actions.
O JSON distingue `execution_status` e `evidence_status`; ausência de comparáveis
não é rotulada como erro de credencial. A correção dos nomes de coleção foi
validada com 188 anúncios reais e 83 linhas com amostra PSA suficiente;
ver [revisão de execução](docs/RUNTIME_REVIEW.md).

A watchlist é gerada por `build_watchlist.py`: não editar manualmente. A presença
de idiomas na configuração não significa que todas as coleções regionais tenham
catálogo validado. Anúncios sem idioma no título ou atributos explícitos ficam em REVISAR.
Os atuais comparáveis vêm das tabelas públicas do PriceCharting e exigem títulos
explícitos. Não se busca outra língua para preencher lacunas.

## Quantidade de cartas: universo, lote e elegibilidade

Não existe meta de encontrar 100 cartas elegíveis. Os 100 Pokémon no catálogo
são metadados de personagens, não uma quota de compra. O gerador não impõe teto
por set por padrão; retirar o teto não regenera a watchlist já versionada.
Os demais filtros de cobertura do catálogo continuam existindo: não é todo o TCG.

`--max-cards` limita um lote de processamento; `--card-offset` seleciona seu ponto
inicial determinístico. Nenhum deles altera critérios de elegibilidade. O relatório
distingue universo selecionado, cartas processadas e adiadas, inclusive falha parcial.
Uma execução posterior consulta preços novos e usa saída própria, sem reaproveitar
preços do lote anterior. Nunca preencher um Top100 relaxando a régua.

O JSON preserva configuração, cálculo, amostra, janela, links, datas e decisões.
O Markdown mostra todos os candidatos. Relatórios históricos continuam legíveis;
parâmetros antigos de sensibilidade não reclassificam o motor atual.

Estado de testes e busca real: [docs/VALIDATION_EBAY_PSA.md](docs/VALIDATION_EBAY_PSA.md).
Desenvolvimento em branch + PR. Não há compra, merge ou novo agendamento automático.
