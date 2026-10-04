# PokeData — continuidade EN / JP / CHS / CHT

Atualizado em 2026-10-04. Pedido do operador: registrar contexto para Claude continuar a base de correspondências. Esta frente é pesquisa de identidade, não uma alteração econômica do scanner.

## Leitura inicial
Leia CLAUDE.md, este documento, docs/CHINESE_IDENTITY.md e DELIVERY_CHAT.md.
Base do repositório inspecionada: c1a761769fc331e0a6f1f13cd8881fe4a99bd568.
Reaproveite src/zh_identity.py, zh_catalog.py e src/catalog/zh_identity.json somente após verificar sua compatibilidade com as novas regras de validação. O catálogo atual não é a planilha PokeData.

## Entrada e acesso
Arquivo de entrada: PokeData_correspondencias_JP_CHS_CHT_parcial.xlsx, fornecido pelo operador na conversa.
SHA-256: c3bf41a5b20f09d4546ed0bcc309783ba078b84b99513645fc300bb753f8d513.
A planilha não está neste PR: contém preços e a política do repositório mantém esses dados fora do GitHub. O operador deve anexá-la à sessão Claude. Não presumir acesso ao ChatGPT Library ou a caminhos de outra sessão.
O arquivo separado PokeData_EN_raw_acima_40_USD.xlsx foi citado no histórico, mas não fornecido nem lido nesta rodada. A aba Cobertura EN do anexo contém as referências necessárias para continuar; não reconstruir campos ausentes (por exemplo, era) por suposição.

## O que foi feito e grau de verificação
Histórico informado pelo operador: extração pública do PokeData, sem API, em 183 sets e 36.821 entradas, com 124 entradas sem preço. Esses totais de origem não foram recontados a partir do anexo. A atualização individual das cotações não foi confirmada.
Nesta rodada foram lidas todas as abas e conferidos IDs, corte raw > US$40, contagens por status/idioma, cobertura e integridade das referências. Não houve nova consulta de preços, validação visual das imagens ou ampliação das correspondências.
As contagens abaixo descrevem os status existentes na planilha, não uma nova certificação da qualidade de cada par.

| Indicador | Contagem conferida |
|---|---:|
| Referências EN, IDs únicos e raw estritamente > US$40 | 3490 |
| Registros classificados Confirmada | 388 |
| Referências com confirmação | 178 |
| Referências com os três idiomas confirmados | 49 |
| Registros JP / CHS / CHT | 160 / 112 / 116 |
| Pares únicos ID EN–idioma confirmados | 375 |
| Registros Provável | 1188 |
| Registros Não encontrada | 9036 |
| IDs órfãos nos detalhes e pendências | 0 |

178/3490 = 5,10% das referências têm ao menos uma confirmação. 49/3490 = 1,40% têm os três idiomas.
Existem múltiplas impressões por referência e idioma: não somar linhas como se fossem cartas únicas. Pendências e confirmações podem coexistir para impressões distintas da mesma referência/idioma.
Somente 3 dos 388 registros confirmados têm fonte preenchida para termos observados no eBay; os demais indicam ausência de verificação individual. Sugestões não são observações de anúncios.

## Mapa do arquivo
Cabeçalhos tabulares na linha 4; dados a partir da linha 5, preservando códigos como texto.
- Resumo e método: critérios, limites e fontes. Não tratar texto metodológico como comprovação de uma execução nesta sessão.
- Comparação confirmada: 178 referências, apresentação agrupada.
- Detalhes confirmados: 388 impressões/correspondências com fontes e URLs de imagens.
- Inconclusivas: 10.224 registros, incluindo múltiplos candidatos.
- Buscas eBay: 1.576 registros confirmados/prováveis; termos observados separados de sugestões.
- Cobertura EN: universo completo de 3.490 referências e estado por idioma.

## Método anterior reportado no arquivo
O resumo descreve comparação computacional de ilustração/geometria/cores, revisão visual de 24 pares e 8 pares documentais adicionais. Não estão anexados scripts, parâmetros, logs ou a lista dessa amostra. Não afirmar que toda a base passou por conferência visual manual.
381 registros confirmados usam a descrição genérica de imagem/versão e metadados; 7 citam conferência visual/documental.
O arquivo reporta ligação a catálogo auxiliar para 3.280 referências e 210 sem ligação. Essa divisão não foi reconstruída nesta rodada.
Há campos que dizem expressamente que o acabamento físico não foi detalhado pela fonte. Preservar essa limitação; mesma versão visual não prova textura/acabamento físico idêntico.
As bases auxiliares mencionadas incluem type-null/PTCG-database, duanxr/PTCG-CHS-Datasets, TCGdex, Pokémon Japão/Taiwan e 52poke. URLs específicas estão nas linhas. A restrição ao data_sc do type-null é reportada pelo método anterior e também discutida em docs/CHINESE_IDENTITY.md: não tratar dados tradicionais rotulados como simplificados como CHS.

## Regras obrigatórias
1. Confirmar mesma arte e versão, usando imagem, numeração e metadados. Tradução de nome isoladamente não basta.
2. Preservar edição, acabamento, carimbo, raridade, promo, reverse holo, first edition e shadowless. Não inventar acabamento ausente.
3. Separar JP, CHS e CHT; aceitar sets diferentes quando a impressão for comprovadamente correspondente.
4. Registrar nome local, código completo, set/produto, fontes, método e data de verificação.
5. Separar termos observados em anúncios (com URL e data) de sugestões e romanizações automáticas.
6. Manter Confirmada, Provável e Não encontrada. Só confirmadas integram a comparação final. Não encontrada não significa inexistente. Excluir exclusivas apenas com evidência explícita.
7. Preservar IDs EN, linhas originais e histórico. Rebaixar uma confirmação somente com motivo registrado; nunca apagar silenciosamente.
8. Raw > US$40 seleciona o universo de pesquisa. Não autoriza compra raw, nem modifica limites/idiomas/certificadoras/custos do scanner.
9. Identidade de arte não é equivalência de valor. Referências econômicas continuam dependentes de vendas comparáveis no idioma e nota corretos.

## Próxima tarefa para Claude
1. Abrir o anexo e reproduzir as contagens, incluindo pares únicos e múltiplas impressões.
2. Preservar uma cópia do original; exportar localmente CSV UTF-8 por aba, sem converter códigos em números. Manter preços e resultados fora do Git.
3. Criar registro de auditoria incremental: ID EN, idioma, impressão local, status anterior/novo, motivo, fontes, data, método e responsável pela validação.
4. Revisar a evidência das confirmações herdadas e avançar nos prováveis e não encontrados em lotes declarados. Registrar quais IDs/idiomas foram realmente pesquisados.
5. Usar fontes complementares e comparação de imagens; não concluir inexistência por falha de busca ou bloqueio.
6. Entregar planilha atualizada, cobertura por idioma, novos pares, rebaixamentos fundamentados, pendências e limites. Registrar código/método no Git via branch + PR.
7. Integração no scanner é uma etapa posterior, com mapeamento explícito entre IDs, testes de identidade e validação real separada. Não importar todos os status como correspondências válidas.

## Critérios de conclusão de cada lote
- Nenhuma referência original perdida e nenhum ID órfão.
- Contagens reproduzíveis por registros, pares únicos e referências.
- Cada confirmação nova documenta arte e versão; incerteza de edição fica pendente.
- Sugestões de busca nunca contam como evidência.
- Entrega informa lote realizado, restante e fontes inacessíveis.
- Código, configuração e regras econômicas inalterados nesta transferência de contexto.
