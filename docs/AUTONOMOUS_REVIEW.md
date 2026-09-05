# Revisão com autonomia delegada — 2026-09-05

Após a entrega parcial, o operador autorizou seguir sem aguardar respostas,
avaliar as melhores decisões pendentes e fazer merge se necessário. A política
2026-09-05.3 registra duas escolhas do agente sob essa autorização:

- Dispersão máxima de 30%, calculada por (máximo − mínimo)/mediana ×100. Acima
  disso, REVISAR. Trata-se de limite operacional conservador, não de garantia
  estatística nem de percentual explicitamente escolhido pelo operador.
- BGS 9,5 sem acumulação: referência e teto PSA 9 ×1,05. Com PSA 9 de US$100,
  teto de US$105. Essa escolha evita ampliar a exposição pelo segundo adicional.

Os testes cobrem ambos os limites, custos COMC completos e os casos ainda
indefinidos quando uma configuração externa fornecer null. As tarifas e o prazo
de 120 dias continuam os já registrados. Categorias especiais ou falta de
identificação/comparáveis permanecem REVISAR.

A validação ampliada consulta três cartas da watchlist, uma página por carta e
PSA 9, mantendo nota, idioma e variante exatos na avaliação. A mudança de nota
é uma ampliação da amostra; não permite usar PSA 10 como referência para PSA 9.

## Revisão operacional e resultado

Adicionado teto de 500 chamadas Browse por execução (incluindo detalhes e
retentativas). Não é declaração da cota contratada. O esgotamento interrompe o
scan com estado parcial e mantém os resultados das cartas já concluídas.

[Amostra real 33948543640](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/actions/runs/33948543640),
commit 6170fa7: Charizard, Blastoise e Venusaur Base Set 1999; 115 anúncios e
33 chamadas eBay. Resultado: 104 REVISAR, 11 REJEITAR e zero APROVAR. Nove anúncios
de Blastoise puderam ser comparados a duas vendas PSA 9 em inglês: US$1.150 em
01/09/2026 e US$936 em 24/08/2026, mediana US$1.043. Nenhum foi aprovado: a amostra
é inferior às três vendas exigidas e o cálculo também apontou lucro não positivo.
Os respectivos IDs, links e custos estão nos artefatos da execução.

A implementação funciona com as regras configuradas; a cobertura de evidência
pública segue limitada. Não reduzir o mínimo de vendas nem presumir idioma para
gerar aprovações. O merge pode integrar esse comportamento conservador com CI
aprovada, mantendo explícita a validação real parcial.

Uma tentativa de criar acompanhamento horário nesta tarefa foi rejeitada pela
revisão automática de permissões por falta de autorização específica da cadência.
Nenhum acompanhamento recorrente foi criado; esta revisão ocorre na execução
ativa. O workflow pontual continua disponível para acionamento manual.
