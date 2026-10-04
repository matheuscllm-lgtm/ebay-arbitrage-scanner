# PokeData — Catálogo EN / JP / CN e correspondência entre idiomas

Documento de entrega. Dados extraídos do PokeData em 04/10/2026.

## Resumo

86% das cartas em inglês do PokeData (19.794 de 23.047) têm equivalente confirmado por imagem em japonês ou em chinês simplificado. Outras 3.232 ficaram inconclusivas e 21 são exclusivas do inglês.

| Idioma | Sets | Cartas únicas | Confirmadas | Inconclusivas | Exclusivas |
| --- | --- | --- | --- | --- | --- |
| Inglês | 183 | 23.047 | 19.794 | 3.232 | 21 |
| Japonês | 394 | 30.188 | 25.660 | 3.574 | 954 |
| Chinês simplificado | 117 | 11.006 | 9.946 | 1.060 | 0 |

- **Chinês.** Todos os sets "Chinese" do PokeData são de chinês simplificado. O site não tem chinês tradicional.
- **Equivalência.** Confirmada só quando a ilustração coincide na comparação de imagem. Em 389 pares conferidos numa fonte externa, nenhum estava errado.
- **Maior limite.** O PokeData não tem imagem de 3.756 cartas, quase todas japonesas e chinesas. Isso explica mais da metade dos inconclusivos em inglês.
- **Dados completos.** As 83.653 linhas do catálogo e as 19.433 da correspondência estão em `output/PokeData_catalogo_correspondencia.xlsx`.

## Metodologia e fontes

Uma equivalência só foi marcada como confirmada quando a ilustração da carta em inglês coincidiu, por comparação de imagem, com a da carta japonesa ou chinesa. Nome e código serviram para achar candidatas, nunca para confirmar sozinhos.

1. **Extração.** 694 sets e 83.653 registros de cartas lidos das listagens públicas do PokeData em 04/10/2026.
2. **Cartas únicas.** Registros do mesmo set, número e nome viraram uma carta só; Reverse Holo, 1st Edition, Master Ball e semelhantes ficaram como variantes. Resultado: 64.241 cartas únicas. Delas, 3.756 não têm imagem utilizável, porque o site mostra o verso da carta ou um marcador.
3. **Candidatas.** Para cada carta em inglês, entraram as cartas japonesas e chinesas de nome compatível e as 15 de imagem mais parecida, mesmo com nome, código ou set diferentes.
4. **Confirmação.** A área da ilustração das duas cartas foi comparada ponto a ponto. Vale como confirmada com pelo menos 12 pontos coincidentes dentro da arte e cores compatíveis. Versões recoloridas da mesma arte (rainbow, shiny, dourada) são separadas pela cor.
5. **Classificação.** Cada carta ficou como confirmada, inconclusiva ou exclusiva. Para cartas de 2011 em diante, o Limitless serviu para separar a carta exclusiva daquela que tem equivalente fora do PokeData.

Conferência do resultado: 389 pares sorteados foram comparados com o Limitless. 372 batem em set e número; os outros 17 são números de cartas secretas que o Limitless não lista. Em 112 pares vistos lado a lado, os 2 erros estavam entre os pares com menos de 40 pontos coincidentes, e por isso essa faixa aparece como confiança média.

"Mesma versão" aqui significa mesma ilustração e mesma carta. O acabamento (holo, reverse, padrão de Poké Ball) não entra na comparação, porque os idiomas usam acabamentos diferentes para a mesma carta.

O PokeData não publica raridade, ilustrador nem nome no idioma original, e escreve os nomes japoneses e chineses em inglês. Esses campos vieram de fora:

| Campo | Fonte | Cobertura |
| --- | --- | --- |
| Raridade e ilustrador, inglês | pokemon-tcg-data | 34.814 de 36.821 registros |
| Raridade, nome e set em japonês | TCGdex | 11.188 de 31.631 registros, 111 sets |
| Nome do Pokémon em japonês e chinês | PokeAPI | Todas as cartas de Pokémon; Treinador e Energia ficam só em inglês |
| Raridade, chinês simplificado | Sem fonte confiável | Só a marcação de carta secreta do PokeData |

## Inglês

183 sets em 16 eras, com 23.047 cartas únicas e 36.821 registros (cada acabamento conta como um registro).

| Era | Sets | Cartas únicas | Registros | Anos |
| --- | --- | --- | --- | --- |
| Mega Evolution | 9 | 1.374 | 2.069 | 2025–2026 |
| Scarlet & Violet | 21 | 3.828 | 6.435 | 2023–2025 |
| Sword & Shield | 23 | 3.872 | 5.955 | 2019–2023 |
| Sun & Moon | 20 | 3.000 | 4.942 | 2016–2019 |
| XY | 20 | 2.005 | 3.336 | 2013–2016 |
| Black & White | 16 | 1.478 | 2.643 | 2011–2013 |
| Call of Legends | 1 | 106 | 201 | 2011 |
| HeartGold SoulSilver | 6 | 1.134 | 1.520 | 2010 |
| Platinum | 6 | 550 | 1.011 | 2009 |
| Diamond & Pearl | 11 | 957 | 1.800 | 2007–2008 |
| EX Ruby & Sapphire | 22 | 1.905 | 3.493 | 2003–2007 |
| e-Card | 3 | 534 | 999 | 2002–2003 |
| Legendary Collection | 1 | 110 | 220 | 2002 |
| Neo | 9 | 748 | 748 | 2000–2002 |
| Gym | 4 | 528 | 528 | 2000 |
| Base | 11 | 918 | 921 | 1999–2000 |

## Japonês

394 sets em 15 eras, com 30.188 cartas únicas e 31.631 registros. Os nomes das cartas vêm em inglês no PokeData, e 97 sets antigos não têm código de set.

| Era | Sets | Cartas únicas | Registros | Anos |
| --- | --- | --- | --- | --- |
| MEGA | 9 | 1.171 | 1.315 | 2025–2026 |
| Scarlet & Violet | 26 | 3.957 | 4.644 | 2022–2025 |
| Sword & Shield | 66 | 5.546 | 5.770 | 2019–2023 |
| Sun & Moon | 54 | 4.455 | 4.530 | 2016–2019 |
| XY | 38 | 3.500 | 3.504 | 2013–2016 |
| Black & White | 48 | 2.660 | 2.660 | 2010–2013 |
| LEGEND | 13 | 855 | 1.155 | 2009–2010 |
| Platinum | 23 | 1.068 | 1.068 | 2008–2009 |
| Diamond & Pearl | 32 | 1.400 | 1.400 | 2005–2008 |
| PCG | 43 | 2.435 | 2.442 | 2004–2006 |
| ADV | 7 | 745 | 745 | 2003–2004 |
| e-Card | 9 | 954 | 956 | 2001–2002 |
| Web & VS | 2 | 247 | 247 | 2001 |
| Neo | 6 | 382 | 382 | 2000–2001 |
| Original | 18 | 813 | 813 | 1996–1999 |

Três sets japoneses aparecem vazios no PokeData: Beginning Set (Oshawott), (Tepig) e (Snivy).

## Chinês: simplificado × tradicional

Os 117 sets "Chinese" do PokeData são todos de chinês simplificado (China continental); o site não cataloga nenhum set em chinês tradicional (Taiwan e Hong Kong). A conferência foi feita pelos códigos dos sets e pelo texto impresso em cartas de seis sets diferentes.

| Era (simplificado) | Sets | Cartas únicas | Registros | Anos |
| --- | --- | --- | --- | --- |
| Scarlet & Violet | 38 | 3.922 | 6.046 | 2023–2026 |
| Sword & Shield | 46 | 4.502 | 5.799 | 2021–2026 |
| Sun & Moon | 33 | 2.582 | 3.356 | 2022–2023 |

| | Simplificado | Tradicional |
| --- | --- | --- |
| Mercado | China continental | Taiwan e Hong Kong |
| Código de set | Próprio, começa com C: CSM1aC, CS4.5C, CSV1C, CBB1C | Espelha o japonês, em geral com sufixo F: SV2a → SV2aF |
| Texto na carta | 宝可梦, 进化, 竞技场 | 寶可夢, 進化, 競技場 |
| Numeração | Própria, diferente da japonesa | Igual à do set japonês de origem |
| No PokeData | 117 sets, 11.006 cartas únicas | Ausente |

O PokeData data o set Start Deck 100 Chinese (CS4DaC) em 2021, mas as cartas trazem copyright de 2024; a data do site parece errada.

## Termos de busca no eBay

Cada registro do catálogo traz uma busca principal e até quatro alternativas. A combinação que mais filtra é nome em inglês + número impresso + código do set + idioma.

| Idioma | Busca principal | Alternativas na planilha | Exemplo |
| --- | --- | --- | --- |
| Inglês | Nome oficial + número/total + nome do set | Código do set + número; sigla de raridade (SIR, IR, Full Art) | Pikachu ex 238/191 Surging Sparks |
| Japonês | Nome em inglês + número/total + código + "Japanese" | Nome em japonês + código; nome do set em inglês e em japonês; sigla (SAR, AR, SR, UR) | Pikachu ex 132/106 SV8 Japanese · ピカチュウex SV8 132/106 |
| Chinês simplificado | Nome em inglês + número/total + código + "Chinese" | "S-Chinese" ou "Simplified"; nome em chinês + código + 简体中文; nome do set em chinês | Umbreon VMAX 173/132 CS4aC Chinese · 月亮伊布VMAX CS4aC 173/132 简体中文 |
| Chinês tradicional (fora do PokeData) | Nome em inglês + número + código japonês + "Traditional Chinese" | "T-Chinese"; 繁體中文; código com F (SV2aF) | Sem exemplo: não há cartas no PokeData |

- O total impresso (o "/106") só entra quando há fonte confiável. Sem isso, a busca usa só o número.
- O PokeData às vezes encurta o nome: em Surging Sparks, "Pikachu ex" aparece como "Pikachu". A busca em inglês usa o nome oficial.
- Sets japoneses antigos não têm código. A busca usa o nome do set: Charizard 006 Expansion Pack Japanese.
- Acabamentos entram no fim da busca do registro: Reverse Holo, 1st Edition, Prerelease, Staff.

## Tabela de correspondência

A aba Correspondência tem 19.433 linhas, uma por carta em inglês com equivalente confirmado: 19.100 com japonês, 7.598 com chinês simplificado e 7.265 com os dois. Cartas sem equivalente confirmado não entram.

| Era (inglês) | Cartas únicas | Com japonês | Com chinês simplificado | Com algum equivalente | % | Inconclusivas | Exclusivas |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Mega Evolution | 1.374 | 980 | 47 | 994 | 72% | 366 | 14 |
| Scarlet & Violet | 3.828 | 3.348 | 2.408 | 3.590 | 94% | 237 | 1 |
| Sword & Shield | 3.872 | 3.715 | 3.359 | 3.761 | 97% | 106 | 5 |
| Sun & Moon | 3.000 | 2.871 | 1.575 | 2.886 | 96% | 114 | 0 |
| XY | 2.005 | 1.887 | 9 | 1.887 | 94% | 117 | 1 |
| Black & White | 1.478 | 1.346 | 0 | 1.346 | 91% | 132 | 0 |
| Call of Legends | 106 | 40 | 0 | 40 | 38% | 66 | 0 |
| HeartGold SoulSilver | 1.134 | 884 | 261 | 909 | 80% | 225 | 0 |
| Platinum | 550 | 494 | 0 | 494 | 90% | 56 | 0 |
| Diamond & Pearl | 957 | 338 | 0 | 338 | 35% | 619 | 0 |
| EX Ruby & Sapphire | 1.905 | 1.580 | 35 | 1.580 | 83% | 325 | 0 |
| e-Card | 534 | 497 | 6 | 497 | 93% | 37 | 0 |
| Legendary Collection | 110 | 108 | 0 | 108 | 98% | 2 | 0 |
| Neo | 748 | 538 | 4 | 538 | 72% | 210 | 0 |
| Gym | 528 | 34 | 0 | 34 | 6% | 494 | 0 |
| Base | 918 | 792 | 0 | 792 | 86% | 126 | 0 |

As eras com percentual baixo não indicam cartas exclusivas. Em Gym, Diamond & Pearl, Neo e Call of Legends, o PokeData não tem imagem dos sets japoneses de origem, então não há como confirmar. Em Mega Evolution, os produtos japoneses de origem (30th Celebration e Starter Decks 100 Battle Collection) não estão no site. A era HeartGold SoulSilver tem chinês porque o PokeData guarda ali o set Miscellaneous Promos, que inclui promos recentes.

Amostra:

| Carta em inglês | Japonês | Chinês simplificado |
| --- | --- | --- |
| Pikachu ex · Surging Sparks 238/191 | SV8 132/106 · ピカチュウex | Sem equivalente confirmado |
| Umbreon VMAX · Evolving Skies 215/203 | S6a 095/069 · ブラッキーVMAX | CS4aC 173/132 · 月亮伊布VMAX |
| Charizard ex · Obsidian Flames 223/197 | SV3 134/108 · リザードンex | CSV5C 155/129 · 喷火龙 |
| Charizard ex · Pokemon Card 151 199/165 | SV2a 201/165 · リザードンex | CSVL1C 120 · 喷火龙ex |
| Giratina V · Lost Origin 186/196 | S11 111/100 · ギラティナV | CS6bC 150/131 · 骑拉帝纳V |
| Lugia V · Silver Tempest 186/195 | S12 110/098 · ルギアV | CS6aC 146/131 · 洛奇亚V |
| Mewtwo & Mew-GX · Unified Minds 71/236 | SM11 029/094 · ミュウツー&ミュウGX | CSM2bC 034/150 · 超梦&梦幻GX |
| Pikachu VMAX · Vivid Voltage 044/185 | S4 031/100 · ピカチュウVMAX | CS1aC 029/135 · 皮卡丘VMAX |
| Pikachu · Cosmic Eclipse 241/236 | SM11b 054/049 · ピカチュウ | CSM2aC 153/150 · 皮卡丘 |
| Eevee · Twilight Masquerade 188/167 | SV5a 078/066 · イーブイ | CBB4C 0407 · 伊布 |
| Umbreon ex · Prismatic Evolutions 161/131 | SV8a 217/187 · ブラッキーex | Sem equivalente confirmado |
| Charizard · Base Set 4/102 | Expansion Pack 006 · リザードン | Sem equivalente confirmado |

- **Confiança.** 18.063 linhas têm confiança alta (40 pontos coincidentes ou mais). As outras 1.370 têm confiança média e pedem uma olhada na imagem antes de uma venda.
- **Nomes diferentes.** Em 262 linhas a arte é a mesma, mas o PokeData usa nomes diferentes em cada idioma, como Yell Horn em inglês e Cheering Y Horn em japonês.
- **Japonês e chinês sem inglês.** A aba JP-CN sem inglês lista 211 pares confirmados entre japonês e chinês simplificado que não têm carta em inglês confirmada.

## Casos inconclusivos

7.866 cartas ficaram inconclusivas e estão na aba Inconclusivos, cada uma com o motivo e, quando existe, a candidata mais próxima. Nenhuma delas entrou na tabela de correspondência.

Cartas em inglês (3.232), pelo motivo da busca em japonês:

| Motivo | Cartas | O que significa |
| --- | --- | --- |
| Candidata japonesa de mesmo nome sem imagem no PokeData | 1.589 | O site mostra o verso da carta ou um marcador no lugar da imagem japonesa |
| Não encontrada, exclusividade não comprovada | 490 | Quase todas anteriores a 2011, onde não há fonte externa para checar |
| Impressão japonesa existe fora do catálogo do PokeData | 404 | O Limitless lista a carta em produtos que o site não tem, como Battle Academy e Starter Decks 100 |
| Imagem parecida, abaixo do limite de confirmação | 292 | Artes texturizadas ou escaneadas com brilho; a candidata está indicada |
| Mesma carta existe em japonês no PokeData, arte não confirmada | 260 | Mesmo texto de jogo, mas a ilustração não bateu |
| Carta em inglês sem imagem no PokeData | 156 | Não há o que comparar |
| Energia básica, versão diferente e outros | 41 | Desenho repetido em muitas impressões ou variante recolorida |

| Idioma | Inconclusivas | Sem imagem no PokeData | Demais motivos |
| --- | --- | --- | --- |
| Japonês | 3.574 | 2.814 | 760 |
| Chinês simplificado | 1.060 | 786 | 274 |

Cartas japonesas de sets lançados nos últimos cinco meses (111) também ficaram aqui: a versão em inglês pode ainda não ter saído.

## Edições exclusivas de um idioma

975 cartas foram tratadas como exclusivas e ficaram fora da comparação: 954 japonesas e 21 em inglês. Uma carta só entrou aqui com indício positivo de que não existe nos outros idiomas; "não encontrei" sozinho foi para os inconclusivos.

| Idioma | Exclusivas | Critério | Conferência |
| --- | --- | --- | --- |
| Japonês | 954 | A arte não aparece em nenhuma carta em inglês nem em chinês simplificado do PokeData. O catálogo em inglês do site é quase completo e tem imagem em 99% das cartas | Das 394 cartas de 2010 em diante, 319 têm página no Limitless e nenhuma lista impressão internacional |
| Inglês | 21 | Carta de 2011 em diante sem impressão japonesa no Limitless e sem equivalente chinês | Listadas abaixo |
| Chinês simplificado | 0 | Nenhuma marcada: o catálogo japonês do PokeData não tem vários decks e promos de onde essas cartas podem ter vindo | As 108 sem equivalente estão nos inconclusivos |

As 21 exclusivas em inglês:

- 14 promos Mega Evolution com os iniciais de cada geração (entre MEP 046 e 063, de Chikorita a Quaxly).
- 5 promos Sword & Shield: Dragapult SWSH132, Zacian LV.X SWSH135, Light Toxtricity SWSH137, Hydreigon C SWSH138 e Greninja Star SWSH144.
- Oddish SVP 102 e Pikachu-EX XY174.

Onde se concentram as exclusivas japonesas:

| Set japonês | Era | Exclusivas |
| --- | --- | --- |
| Pokémon VS | Web & VS | 134 |
| XY Promos | XY | 64 |
| SM-P Promos | Sun & Moon | 56 |
| PCG-P Promos | PCG | 48 |
| Everyone's Exciting Battle | Black & White | 42 |
| Pokémon Web | Web & VS | 40 |
| P Promos | e-Card | 37 |
| Black & White Promos | Black & White | 29 |

"Exclusiva" vale para os três idiomas do PokeData. Uma carta japonesa desta lista pode existir em chinês tradicional, coreano ou tailandês, que o site não cataloga.

## Planilha

| Aba | Linhas | Conteúdo |
| --- | --- | --- |
| Leia-me | – | Totais por idioma e por era, calculados por fórmula a partir dos catálogos |
| Sets | 694 | Idioma, era, código, nome nativo, data e contagens de cada set |
| Catálogo EN | 36.821 | Uma linha por registro: nome, número, raridade, variante, buscas do eBay, situação e códigos equivalentes |
| Catálogo JP | 31.631 | Igual, com nome em japonês |
| Catálogo CN | 15.201 | Igual, com nome em chinês simplificado |
| Correspondência | 19.433 | Inglês → japonês → chinês simplificado, só equivalentes confirmados |
| JP-CN sem inglês | 211 | Pares japonês e chinês sem carta em inglês confirmada |
| Inconclusivos | 7.866 | Motivo, candidata mais próxima e impressões japonesas indicadas pelo Limitless |
| Exclusivas | 975 | Critério usado em cada carta |
| Ref. chinês tradicional | 83 | Sets em chinês tradicional listados pelo TCGdex, fora do PokeData |

## Pendências

- [ ] Conferir visualmente as 1.370 linhas de confiança média antes de usá-las em venda.
- [ ] Reprocessar as 3.756 cartas sem imagem quando o PokeData publicar as imagens; a falta se concentra nos sets japoneses das eras Diamond & Pearl, Gym e Neo.
- [ ] Buscar outra fonte para chinês tradicional: o TCGdex tem só parte das cartas.
- [ ] Completar a raridade, em branco no chinês simplificado e em 65% dos registros japoneses.
- [ ] Ler os termos de uso do PokeData antes de redistribuir os dados.
