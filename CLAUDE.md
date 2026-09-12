> **Regra vigente de entrega:** [DELIVERY_CHAT.md](DELIVERY_CHAT.md). Resultados somente no chat, referência clicável e coleta nova por solicitação; substitui orientações antigas de entrega via GitHub ou preços reutilizados.

# Instruções de desenvolvimento — EBAY PSA

As instruções do projeto EBAY PSA de 2026-09-11 substituem as regras econômicas
anteriores deste arquivo. O histórico integral permanece no Git. Leia
[`docs/EBAY_PSA.md`](docs/EBAY_PSA.md), [`config.yaml`](config.yaml) e os testes
antes de alterar regras. O código, a configuração e os testes demonstram o que
está implementado; a documentação registra a intenção.

- No modo padrão `longterm`, apenas PSA 10, EN/JP, preço fixo, item nos EUA e
  preço do item até US$500. Não reativar raw por argumento CLI.
- Referência: vendas concluídas PSA da mesma carta, coleção, número, variante,
  idioma e nota correspondente. Não usar preços pedidos como prova de revenda.
- Modos econômicos legados preservam outras certificadoras/notas. Neles, BGS:
  teto configurado de PSA +5%; nota 9,5 usa PSA 9 +5%, sem acumular ajustes
  quando a combinação estiver indefinida. PSA não possui 9,5.
- TAG 10 equivale a PSA 10 para comparação estratégica. Revenda em outra
  certificadora depende de vendas próprias; categorias especiais ficam separadas.
- CGC: preço do item até 40% da referência PSA ajustada (confirmado).
- Regra vigente: `gate_mode: longterm`, três eixos separados — tese, entrada e
  evidência. Margem bruta mínima configurada **20%**, estritamente acima:
  `(revenda comprovada − preço do item) / preço do item ×100`. Não é desconto.
  Margem sozinha não aprova; exige tese favorável, evidência adequada e lucro
  líquido operacional atual positivo com custos completos.
- Tese vem de arquivo privado `--thesis-file`, com demanda, importância
  colecionável, oferta e resiliência documentadas por fonte, data e justificativa.
  Falta de tese é REVISAR; LP1, preço baixo, SIR e raw ×3 não suprem evidência.
- Evidência adicional: ≥9 vendas comparáveis nos últimos 90 dias, distribuídas
  em ≥2 meses-calendário, contadas antes do limite de 10 vendas da mediana.
  Não apresentar essa amostra observada como o mercado eBay inteiro.
- US$10 estimam envios/impostos até COMC. Elite US$2,50; venda 5%; saque 10%
  informado pelo operador; horizonte 120 dias (faixa solicitada 90–120).
- Armazenamento calculado com carência; segurança adicional sem carência.
- Dispersão máxima 30%; BGS 9,5 sem acumulação (PSA 9 ×1,05). Decisões delegadas
  pelo operador, registradas em docs/AUTONOMOUS_REVIEW.md. Null externo exige REVISAR.
- Idiomas separados; não presumir inglês nem equivalência entre idiomas asiáticos.
- Reserva US$10 por carta, contabilizada uma vez, com cobertura explícita.
- Separar compra, custos, investimento, referência, revenda e lucro; distinguir
  desconto, margem sobre a venda e retorno sobre o investimento.
- Comprar no vault é compatível e preferencial quando confirmado. Revenda COMC;
  nunca depender de listarmos diretamente no vault.
- No modo `longterm`: OPORTUNIDADE / MONITORAR / REVISAR / REJEITAR, sempre com
  motivos e os três eixos. OPORTUNIDADE é classificação analítica, sem recomendar
  ou executar compra. Modos legados mantêm APROVAR / REVISAR / REJEITAR.
- Custo de saída em 120 dias não é previsão financeira para 3–5 anos. Não gerar
  cenários de preço nem probabilidades de valorização sem modelo validado.
- Manter links, datas, contagem de vendas, diferenças relevantes e baixa liquidez.
- Mudanças econômicas exigem testes de regressão; registrar a alteração no changelog.
- Distinguir planejado, implementado, testado e validado em execução real.
- Consolidar regras, implementar, testar, validar busca real e só então automatizar.

A coluna LP (`src/longterm.py`) permanece **diagnóstico legado informativo**, sem
decidir gate, veredito ou ranking. A análise vigente de investimento
(`src/investment.py`, [`docs/LONGO_PRAZO.md`](docs/LONGO_PRAZO.md)) é distinta: tese,
entrada e evidência participam da classificação. Não converter a média LP normalizada
por componentes disponíveis em confiança ou tese favorável. A escada de popularidade
de `src/scorer.py` também é legada. Nenhuma dessas réguas recomenda compra.

## Repositório e operação

- Fluxo padrão: branch + PR, nunca push direto em main.
- Repositório independente dos scanners irmãos; não mudar seus parâmetros aqui.
- Não versionar credenciais ou dados de scans. `data/` e `results/` são locais.
- As regras solicitadas pelo operador ficam versionadas em config, docs e testes.
- `watchlist.yaml` é gerada e versionada: não editar manualmente. As entradas de
  catálogo são públicas e têm origem registrada em `src/catalog/README.md`.
- Não há quota Top100 de cartas elegíveis. Os 100 personagens do catálogo são
  metadados, não uma meta de oportunidades. O gerador não limita cartas por set por
  padrão; `--max-cards` e `--card-offset` limitam apenas o processamento do scan.
  Declarar seleção adiada e resultado parcial; nunca completar a lista afrouxando critérios.
- Teses privadas, fontes de análise, preços e alvos do operador não entram no Git.
  Não regenerar catálogo nem fazer coleta de mercado em uma tarefa apenas de código.
- Percentuais inteiros: 20 significa 20%; null é pendência, nunca zero.
- Credenciais são `EBAY_CLIENT_ID` e `EBAY_CLIENT_SECRET`, somente no ambiente.
- CI offline: `python -m pytest -q`. Busca real: `python main.py --group 3`.
- Limite de 500 chamadas eBay por execução; esgotamento interrompe com resultado parcial.
- Gerar relatório com `python ebay_summary.py results/last_scan.json -o results/report.md`.
- Orientações antigas em comandos/skills históricos não podem reativar raw,
  retirar custos ou substituir as regras desta versão. Consulte o README atual.
