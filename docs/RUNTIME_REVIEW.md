# Revisão de execução — 2026-09-05

Base: main c0cacf3, 620 testes aprovados. A revisão não altera os limites econômicos.

## Defeitos identificados e correções

- O comparador exigia prefixos administrativos do catálogo, como `SV10:` e
  `SWSH09:`, nos títulos das vendas. Agora usa o nome legível da coleção na busca,
  nos atributos e na comparação; preserva subconjuntos e edições distintas.
- A pré-checagem de nome por substring impedia normalização de apóstrofos e
  `LV.X`/`LVX`. Número e exclusões continuam verificados no título original;
  o nome usa grafia normalizada com limites de palavra e sufixos de carta.
- Validação passa a separar `execution_status` de `evidence_status`. O status
  geral e os códigos de saída continuam exigindo evidência suficiente para sucesso;
  uma busca completa sem comparáveis não é apresentada como erro de credencial.
- O JSON passa a preservar limites de consultas e critérios de vendedor, para
  permitir reproduzir a configuração da execução.
- Workflow de validação agora é somente manual, com grupo, nota e amostra de até
  três cartas configuráveis. Parâmetros são variáveis de ambiente entre aspas,
  sem interpolação direta no código shell; secrets somente na etapa de consulta.

## Diagnóstico de cobertura

Sondagem pública da primeira carta de sete grupos, sem usar preços pedidos:
Team Rocket's Mewtwo ex #231 passou de zero para seis vendas PSA 10 estritas;
Gengar ex #193 passou de duas para onze. A mudança resulta de identidade de coleção
e grafia, sem supor idioma nem reduzir o mínimo de vendas. Outras cartas continuam
com cobertura baixa; essa limitação deve permanecer visível.

Os testes cobrem casos positivos e negativos, Base Set vs Base Set 2/Sword &
Shield, subconjuntos, número divergente, Mew vs Mewtwo e sufixos ex/LV.X.
## Validação real da correção

[Execução 33949437501](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/actions/runs/33949437501),
commit aaac3e1: grupo 1, três cartas PSA 10, uma página por carta. Resultado
**success**, execução completa e amostra suficiente; **188 anúncios, 33 chamadas,
83 linhas com pelo menos três vendas PSA aceitas**, 105 REVISAR e 83 REJEITAR.
Zero APROVAR: nos 83 candidatos com referência, o lucro após custos era não positivo.
Este é o primeiro teste real desta revisão que completou coleta, identificação,
referência, custos, cálculo e decisão com evidência suficiente.

## Proteção e apresentação de resultados

- Corrigido o CSV da CLI: execuções abortadas agora gravam `.aborted.csv`, assim
  como o JSON, preservando os últimos resultados completos.
- Aviso de execução parcial aparece antes da tabela; vendas PSA compartilhadas
  entre comparação e revenda são detalhadas uma única vez no relatório.
- Sem preço de revenda, a impossibilidade de estimar armazenamento é distinguida
  de tarifa COMC ainda não configurada. Dados e cálculos continuam pendentes.
- 632 testes locais passaram, incluindo preservação de arquivos e limites de
  identidade. Os limites econômicos permanecem os confirmados anteriormente.
