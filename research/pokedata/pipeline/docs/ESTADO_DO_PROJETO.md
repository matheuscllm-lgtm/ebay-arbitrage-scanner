# Estado do projeto — cruzamento PokeData (rodada do Claude)

Atualizado em 04/10/2026. Este arquivo registra o que foi feito na rodada do Claude, o que está verificado, o que falta e como isso se liga ao trabalho registrado pelo GPT no PR #53.

## O que foi feito

1. **Extração completa do PokeData**: 694 sets e 83.653 registros de cartas em inglês, japonês e chinês.
2. **Catálogo por idioma → era → set → carta**, com número impresso, raridade (quando há fonte), nome no idioma original e buscas prontas para o eBay.
3. **Separação do chinês**: os 117 sets "Chinese" do site são todos de chinês simplificado. Chinês tradicional não existe no PokeData.
4. **Correspondência entre idiomas por imagem**: 61.657 imagens baixadas e comparadas. O inglês é a referência.
5. **Classificação de cada carta** em arte confirmada, provável, inconclusiva, não encontrada ou exclusiva, com o motivo registrado.
6. **Checagem externa no Limitless** para cartas de 2011 em diante: separa carta exclusiva de carta cujo equivalente existe fora do PokeData.
7. **Planilha de entrega** com 13 abas e fórmulas de conferência, sem preços.
8. **Reclassificação depois da crítica do GPT** (seção abaixo): só houve rebaixamentos; nenhum par novo foi confirmado.

## Crítica do GPT e o que mudou

A crítica chegou resumida em sete pontos. Todos foram tratados nesta rodada.

| Ponto | Avaliação | O que mudou |
| --- | --- | --- |
| "Confirmada" significava só mesma arte | Procede | O status virou "arte confirmada". A planilha ganhou a coluna Versão e as colunas "Registro comparado" e "Imagem comparada" |
| Validação descrita como "nenhum errado" | Procede | Redação corrigida: 372 confirmados por fonte externa, 0 contraditos, 17 sem fonte; 2 erros em 112 pares vistos lado a lado |
| Confiança média tratada como confirmada | Procede | Pares com menos de 40 pontos viraram "provável" e saíram da Correspondência |
| Cobertura das 3.490 referências não demonstrada | Procede | Aba Cobertura PR53: 2.516 com arte confirmada (72%), 323 prováveis, 479 inconclusivas, 172 não encontradas |
| Chinês tradicional ausente | Procede | Os 116 registros do PR #53 foram preservados na aba CHT PR53, sem revalidação |
| Exclusivas sem evidência positiva | Procede em parte | Exclusiva só com fonte externa: 319 japonesas ficaram, 635 passaram para "não encontrada" |
| 19.794 cartas contra 19.433 linhas | Explicado | A diferença de 361 eram cartas que o PokeData repete no mesmo set e número; a planilha agora confere isso por fórmula |

Dois achados além da crítica:

- **Erros acima de 40 pontos.** A análise dos nomes achou pares fortes em que um idioma traz o nome de outro Pokémon (nome ou imagem errados no PokeData) e cartas de desenho quase igual trocadas entre si (as Memory de Silvally). Por isso todo par de nome divergente também virou "provável".
- **As 361 cartas.** 172 tinham o número escrito de duas formas (058 e 58), 120 tinham o mesmo número com o nome grafado de dois jeitos e 69 tinham as duas coisas. Depois da reclassificação a diferença é de 328.

## Contagens verificadas

Conferidas contra a planilha recalculada (aba Leia-me) e contra os arquivos gerados pelos scripts.

| Item | Inglês | Japonês | Chinês simplificado |
| --- | --- | --- | --- |
| Sets | 183 | 394 | 117 |
| Registros | 36.821 | 31.631 | 15.201 |
| Cartas únicas | 23.047 | 30.188 | 11.006 |
| Arte confirmada | 18.673 | 24.158 | 9.606 |
| Prováveis | 1.121 | 1.502 | 340 |
| Inconclusivas | 2.747 | 3.574 | 963 |
| Não encontradas | 485 | 635 | 97 |
| Exclusivas | 21 | 319 | 0 |
| Sem imagem utilizável no PokeData | 156 | 2.814 | 786 |

| Item | Valor |
| --- | --- |
| Linhas na aba Correspondência | 18.345 |
| — com japonês / com chinês / com os dois | 17.707 / 7.189 / 6.551 |
| — cartas em inglês reunidas nessas linhas | 18.673 |
| — com registro único e sem marcação em todos os idiomas | 5.075 |
| — com variantes ou marcação a conferir | 13.270 |
| Pares na aba Prováveis | 4.111 |
| Pares japonês–chinês sem inglês | 346 |

Movimento da reclassificação, em cartas únicas:

| Idioma | Confirmado → arte confirmada | Confirmado → provável | Exclusiva → exclusiva | Exclusiva → não encontrada | Inconclusivo → inconclusivo | Inconclusivo → não encontrada |
| --- | --- | --- | --- | --- | --- | --- |
| Inglês | 18.673 | 1.121 | 21 | 0 | 2.747 | 485 |
| Japonês | 24.158 | 1.502 | 319 | 635 | 3.574 | 0 |
| Chinês simplificado | 9.606 | 340 | 0 | 0 | 963 | 97 |

Validação:

- **Fonte externa.** 389 pares sorteados e comparados com o Limitless: 372 confirmados pela fonte, 0 contraditos, 17 sem fonte (números que o Limitless não lista). A amostra é anterior à reclassificação.
- **Lado a lado, antes.** 112 pares vistos: 2 erros, os dois com menos de 40 pontos (um deles de uma regra para energias que depois foi removida).
- **Lado a lado, depois.** 48 pares da faixa de arte confirmada (24 sorteados no total, 24 na parte mais fraca): 48 com a mesma ilustração; em pelo menos 6 o acabamento ou o carimbo difere.
- **Exclusivas japonesas.** 392 cartas de 2010 em diante consultadas no Limitless: 319 com página e sem impressão internacional; 73 sem página.

## Limitações conhecidas

- **Versão não conferida.** Arte confirmada não garante mesma edição, acabamento ou carimbo. A comparação usa uma imagem por carta única; Reverse Holo, 1st Edition, Unlimited, Shadowless e carimbos são variantes não comparadas.
- **Erros de nome e de imagem no PokeData.** Há registros com o nome de outro Pokémon e registros com a imagem de outra carta. Os casos detectados estão na aba Prováveis; pode haver outros entre os pares de nome compatível.
- **Variantes de traço igual.** Cartas douradas ou pretas com o mesmo traço da arte colorida podem passar como equivalentes na faixa provável. Foi o erro visto na amostra (Zacian V dourada).
- **Artes texturizadas.** Full arts fotografadas com textura dão poucos pontos coincidentes e caem nos prováveis ou inconclusivos mesmo sendo a mesma carta (exemplo: Dragonite-GX, Dragon Majesty 67/70).
- **Catálogo japonês do PokeData incompleto.** Faltam decks e promos (Battle Academy, Starter Decks 100, 30th Celebration japonês). Cartas em inglês vindas desses produtos ficam inconclusivas.
- **Sem imagem.** Sets japoneses das eras Diamond & Pearl, Gym e Neo mostram o verso da carta no lugar da imagem.
- **Raridade.** O PokeData não publica. Japonês tem raridade em 35% dos registros; chinês simplificado não tem.
- **Não encontradas sem fonte.** As 1.217 cartas não encontradas não têm fonte externa que diga se são exclusivas; antes de 2011 não há nenhuma.
- **Exclusividade pelo Limitless.** O Limitless registra impressões da carta, não de uma arte específica.
- **Termos de uso do PokeData** ([texto](https://www.iubenda.com/terms-and-conditions/81884871), versão de 12/12/2025, lidos em 04/10/2026): proíbem copiar, baixar, compartilhar e publicar o conteúdo, salvo para uso pessoal e não comercial, com atribuição. A planilha e os dados extraídos não devem ir para repositório público. Leitura sem valor de parecer jurídico.

## Relação com o PR #53 (trabalho do GPT)

Lidos em 04/10/2026, na branch `docs/pokedata-claude-handoff` (commit 8ad8993): `CLAUDE.md`, `docs/POKEDATA_PROJECT_STATE.md` e a planilha `research/pokedata/PokeData_correspondencias_JP_CHS_CHT_parcial.xlsx`.

| | Rodada do GPT (PR #53) | Rodada do Claude (esta pasta) |
| --- | --- | --- |
| Referências em inglês | 3.490 (raw acima de US$40) | 23.047 (catálogo inteiro do PokeData) |
| Confirmações | 388 registros, 375 pares únicos carta–idioma | 18.345 linhas de arte confirmada na aba Correspondência; 4.111 pares prováveis à parte |
| Critério | Mesma arte e mesma versão: edição, acabamento, carimbo, raridade | Arte confirmada: mesma ilustração, 40 pontos ou mais, nome compatível. Versão não conferida |
| Chinês tradicional | Incluído: 116 registros | Não existe no PokeData; os 116 do PR #53 foram preservados na aba CHT PR53 |
| Scripts e parâmetros | Não anexados | Nesta pasta |
| Preços | Coluna "Raw EN (USD)" na planilha | Nenhum |

### Comparação dos 388 registros confirmados

Gerada por `compare_pr53.py`; resultado linha a linha em `docs/comparacao_pr53.csv`.

| Idioma | Registros | Arte confirmada aqui | Provável aqui, mesma candidata | Inconclusiva aqui, mesma candidata | Carta sem imagem no PokeData | Set fora do catálogo do PokeData |
| --- | --- | --- | --- | --- | --- | --- |
| Japonês | 160 | 136 | 16 | 1 | 0 | 7 |
| Chinês simplificado | 112 | 74 | 7 | 1 | 12 | 18 |
| Chinês tradicional | 116 | fora do alcance | – | – | – | – |

- Dos 272 registros em japonês e chinês simplificado, 210 têm a mesma carta com arte confirmada aqui, 23 têm a mesma candidata como provável e nenhum é contradito.
- Os 39 restantes vêm de lacunas do PokeData: sets ausentes do site (japonês MC e SVG; chinês CSV9C, CSV9.5C, CSV10C, CBB6C, CSVNC), cartas sem imagem e 2 candidatas abaixo do limite.
- Os 116 registros em chinês tradicional só existem no PR #53.

### Cobertura das 3.490 referências

Todas localizadas neste catálogo (aba Cobertura PR53, sem preços).

| Situação nesta rodada | Referências |
| --- | --- |
| Arte confirmada em japonês ou chinês simplificado | 2.516 (72%) |
| — em japonês / em chinês simplificado | 2.473 / 294 |
| Só provável | 323 |
| Inconclusiva | 479 |
| Não encontrada | 172 |

- Em 1.640 das 2.516 a referência é o registro cuja imagem foi comparada; nas outras 876 é uma variante não conferida, quase sempre Reverse Holo.
- Há arte confirmada em japonês para 2.339 referências sem confirmação em japonês no PR #53, e em chinês simplificado para 224.

### Dois pontos de atenção

1. **Critério diferente.** A regra 2 do PR #53 exige preservar edição, acabamento, carimbo, reverse holo, first edition e shadowless. Esta rodada confirma só a ilustração. Uma "arte confirmada" daqui só vira "Confirmada" na base do PR #53 depois de conferida a versão; até lá entra como "Provável".
2. **Repositório público.** Os termos do PokeData proíbem publicar o conteúdo, e o `CLAUDE.md` do repositório diz que preços não entram no Git. A planilha do PR #53 já está na branch pública e tem a coluna "Raw EN (USD)". A decisão de mantê-la ou retirá-la é do operador.

## Próximos passos

- [x] Ler `CLAUDE.md` e `docs/POKEDATA_PROJECT_STATE.md` do PR #53.
- [x] Comparar os registros confirmados do PR #53 com esta rodada.
- [x] Reclassificar depois da crítica do GPT: arte × versão, prováveis, exclusivas com evidência, cobertura das 3.490 referências, chinês tradicional preservado.
- [ ] Decidir o que vai para o repositório público: recomendação é scripts e documentação, com planilhas fora do Git.
- [ ] Conferir a versão das 2.516 referências com arte confirmada, começando pelas 1.640 em que a referência é o registro comparado.
- [ ] Conferir visualmente os 4.111 pares prováveis.
- [ ] Revalidar por imagem o chinês tradicional do PR #53.
- [ ] Buscar fonte para os sets que faltam no PokeData (japonês MC e SVG; chinês CSV9C em diante).
- [ ] Reprocessar quando o PokeData publicar as imagens que faltam.
