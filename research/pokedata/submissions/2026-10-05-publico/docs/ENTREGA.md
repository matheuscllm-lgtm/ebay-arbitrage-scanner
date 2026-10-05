# PokeData — Catálogo EN / JP / CN e correspondência entre idiomas

Documento de entrega. Dados extraídos do PokeData em 04/10/2026.

## Resumo

81% das cartas em inglês do PokeData (18.673 de 23.047) têm equivalente com a arte confirmada por imagem em japonês ou em chinês simplificado. Outras 1.121 têm equivalente provável, 2.747 ficaram inconclusivas, 485 não foram encontradas e 21 são exclusivas do inglês.

| Idioma | Sets | Cartas únicas | Arte confirmada | Prováveis | Inconclusivas | Não encontradas | Exclusivas |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Inglês | 183 | 23.047 | 18.673 | 1.121 | 2.747 | 485 | 21 |
| Japonês | 394 | 30.188 | 24.158 | 1.502 | 3.574 | 635 | 319 |
| Chinês simplificado | 117 | 11.006 | 9.606 | 340 | 963 | 97 | 0 |

- **Chinês.** Todos os sets "Chinese" do PokeData são de chinês simplificado. O site não tem chinês tradicional.
- **Arte, não versão.** "Arte confirmada" quer dizer mesma ilustração. Edição, acabamento e carimbo não foram conferidos; a planilha mostra onde há variantes.
- **Provável.** A imagem coincidiu, mas com menos de 40 pontos ou com nome divergente entre os idiomas. Fica fora da tabela de correspondência.
- **Exclusiva.** Só com fonte externa dizendo que não há impressão em outro idioma. "Não encontrada" não quer dizer exclusiva.
- **Maior limite.** O PokeData não tem imagem de 3.756 cartas, quase todas japonesas e chinesas. Isso explica mais da metade dos inconclusivos em inglês.
- **Dados completos.** As 83.653 linhas do catálogo e as 18.345 da correspondência estão em `output/PokeData_catalogo_correspondencia.xlsx`.

## Metodologia e fontes

A arte de uma equivalência só foi marcada como confirmada quando a ilustração da carta em inglês coincidiu, por comparação de imagem, com a da carta japonesa ou chinesa. Nome e código serviram para achar candidatas e para barrar pares incoerentes, nunca para confirmar sozinhos.

1. **Extração.** 694 sets e 83.653 registros de cartas lidos das listagens públicas do PokeData em 04/10/2026.
2. **Cartas únicas.** Registros do mesmo set, número e nome viraram uma carta só; Reverse Holo, 1st Edition, Master Ball e semelhantes ficaram como variantes. Resultado: 64.241 cartas únicas. Delas, 3.756 não têm imagem utilizável, porque o site mostra o verso da carta ou um marcador.
3. **Candidatas.** Para cada carta em inglês, entraram as cartas japonesas e chinesas de nome compatível e as 15 de imagem mais parecida, mesmo com nome, código ou set diferentes.
4. **Comparação.** A área da ilustração das duas cartas foi comparada ponto a ponto, com uma imagem por carta única. Versões recoloridas da mesma arte (rainbow, shiny, dourada) são separadas pela cor.
5. **Arte confirmada.** 40 pontos coincidentes ou mais dentro da arte, cores compatíveis e nome compatível entre os idiomas.
6. **Provável.** A imagem aprovou o par, mas com 12 a 39 pontos, ou com nome divergente entre os idiomas. Fica fora da tabela de correspondência, com o motivo registrado.
7. **Classificação.** Cada carta ficou como arte confirmada, provável, inconclusiva, não encontrada ou exclusiva. Exclusiva exige fonte externa: para cartas de 2011 em diante, o Limitless diz se existe impressão em outro idioma.

Conferência do resultado:

- **Fonte externa.** 389 pares sorteados foram comparados com o Limitless: 372 confirmados pela fonte (mesmo set e número), 0 contraditos e 17 sem fonte, porque o Limitless não lista aqueles números.
- **Lado a lado, antes da reclassificação.** 112 pares vistos: 2 erros, os dois com menos de 40 pontos coincidentes.
- **Nomes divergentes.** A análise dos nomes achou erros também acima de 40 pontos: 28 pares inglês–japonês em que um dos idiomas traz o nome de outro Pokémon (nome ou imagem errados no PokeData) e cartas de desenho quase igual trocadas entre si (as Memory de Silvally).
- **Lado a lado, depois da reclassificação.** 48 pares da faixa de arte confirmada, 24 sorteados no total e 24 na parte mais fraca da faixa: os 48 têm a mesma ilustração. Em pelo menos 6 deles o acabamento ou o carimbo é visivelmente diferente.

Por causa desses erros, as duas faixas (menos de 40 pontos e nome divergente) saíram da tabela de correspondência e viraram "provável".

**Arte × versão.** A comparação prova que a ilustração é a mesma. Não prova que edição (1st Edition, Unlimited, Shadowless), acabamento (holo, reverse, padrão de Poké Ball) e carimbo coincidem. Exemplo: as quatro edições em inglês do Charizard de Base Set (1st Edition, Shadowless, Unlimited e Base Set 2) apontam para a mesma carta japonesa, Expansion Pack 006. Na planilha:

- A coluna Versão da aba Correspondência diz se as cartas da linha têm registro único e sem marcação, ou se há variantes a conferir.
- As colunas "Registro comparado" dizem de qual registro veio a imagem usada em cada idioma.
- Nos catálogos, a coluna "Imagem comparada" marca os registros que são variantes não conferidas.

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

A aba Correspondência tem 18.345 linhas, só com equivalentes de arte confirmada: 17.707 com japonês, 7.189 com chinês simplificado e 6.551 com os dois.

As 18.345 linhas reúnem as 18.673 cartas em inglês com arte confirmada. A diferença de 328 são cartas que o PokeData repete no mesmo set e número (número escrito como 058 e 58, ou o mesmo número com o nome grafado de dois jeitos). Cada repetição fica na linha da carta original, e a última coluna da aba diz quantas cartas a linha reúne.

| Era (inglês) | Cartas únicas | Arte confirmada JP | Arte confirmada CN | JP ou CN | % | Prováveis | Inconclusivas | Não encontradas | Exclusivas |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Mega Evolution | 1.374 | 927 | 46 | 941 | 68% | 53 | 349 | 17 | 14 |
| Scarlet & Violet | 3.828 | 3.132 | 2.303 | 3.452 | 90% | 138 | 233 | 4 | 1 |
| Sword & Shield | 3.872 | 3.340 | 3.186 | 3.558 | 92% | 203 | 97 | 9 | 5 |
| Sun & Moon | 3.000 | 2.656 | 1.451 | 2.721 | 91% | 165 | 113 | 1 | 0 |
| XY | 2.005 | 1.831 | 8 | 1.833 | 91% | 54 | 109 | 8 | 1 |
| Black & White | 1.478 | 1.292 | 0 | 1.292 | 87% | 54 | 130 | 2 | 0 |
| Call of Legends | 106 | 36 | 0 | 36 | 34% | 4 | 47 | 19 | 0 |
| HeartGold SoulSilver | 1.134 | 834 | 243 | 862 | 76% | 47 | 171 | 54 | 0 |
| Platinum | 550 | 473 | 0 | 473 | 86% | 21 | 37 | 19 | 0 |
| Diamond & Pearl | 957 | 301 | 0 | 301 | 31% | 37 | 604 | 15 | 0 |
| EX Ruby & Sapphire | 1.905 | 1.456 | 34 | 1.456 | 76% | 124 | 145 | 180 | 0 |
| e-Card | 534 | 455 | 6 | 455 | 85% | 42 | 16 | 21 | 0 |
| Legendary Collection | 110 | 94 | 0 | 94 | 85% | 14 | 2 | 0 | 0 |
| Neo | 748 | 469 | 4 | 469 | 63% | 69 | 154 | 56 | 0 |
| Gym | 528 | 31 | 0 | 31 | 6% | 3 | 454 | 40 | 0 |
| Base | 918 | 699 | 0 | 699 | 76% | 93 | 86 | 40 | 0 |

As eras com percentual baixo não indicam cartas exclusivas. Em Gym, Diamond & Pearl, Neo e Call of Legends, o PokeData não tem imagem dos sets japoneses de origem, então não há como confirmar. Em Mega Evolution, os produtos japoneses de origem (30th Celebration e Starter Decks 100 Battle Collection) não estão no site. A era HeartGold SoulSilver tem chinês porque o PokeData guarda ali o set Miscellaneous Promos, que inclui promos recentes.

Amostra:

| Carta em inglês | Japonês | Chinês simplificado |
| --- | --- | --- |
| Pikachu ex · Surging Sparks 238/191 | SV8 132/106 · ピカチュウex | Inconclusiva: candidata sem imagem |
| Umbreon VMAX · Evolving Skies 215/203 | S6a 095/069 · ブラッキーVMAX | CS4aC 173/132 · 月亮伊布VMAX |
| Charizard ex · Obsidian Flames 223/197 | SV3 134/108 · リザードンex | CSV5C 155/129 · 喷火龙 |
| Charizard ex · Pokemon Card 151 199/165 | SV2a 201/165 · リザードンex | CSVL1C 120 · 喷火龙ex |
| Giratina V · Lost Origin 186/196 | S11 111/100 · ギラティナV | CS6bC 150/131 · 骑拉帝纳V |
| Lugia V · Silver Tempest 186/195 | S12 110/098 · ルギアV | CS6aC 146/131 · 洛奇亚V |
| Mewtwo & Mew-GX · Unified Minds 71/236 | SM11 029/094 · ミュウツー&ミュウGX | Provável: nome divergente no PokeData |
| Pikachu VMAX · Vivid Voltage 044/185 | S4 031/100 · ピカチュウVMAX | CS1aC 029/135 · 皮卡丘VMAX |
| Pikachu · Cosmic Eclipse 241/236 | SM11b 054/049 · ピカチュウ | CSM2aC 153/150 · 皮卡丘 |
| Eevee · Twilight Masquerade 188/167 | SV5a 078/066 · イーブイ | CBB4C 0407 · 伊布 |
| Umbreon ex · Prismatic Evolutions 161/131 | SV8a 217/187 · ブラッキーex | Não encontrada |
| Charizard · Base Set Unlimited 4 | Expansion Pack 006 · リザードン | Não encontrada |

- **Versão.** 5.075 linhas têm registro único e sem marcação em todos os idiomas. Nas outras 13.270 há variantes ou marcação de edição e acabamento a conferir.
- **Prováveis.** A aba Prováveis lista 4.111 pares fora desta tabela: 3.134 com menos de 40 pontos, 921 com nome divergente entre os idiomas, 49 com nome de outro Pokémon e 7 ligados só por meio da carta japonesa.
- **Japonês e chinês sem inglês.** A aba JP-CN sem inglês lista 346 pares de arte confirmada entre japonês e chinês simplificado que não têm carta em inglês confirmada.

## Cobertura das 3.490 referências do PR #53

As 3.490 referências em inglês da planilha do PR #53 foram todas localizadas neste catálogo. A aba Cobertura PR53 traz a situação de cada uma, sem preços.

| Situação nesta rodada | Referências |
| --- | --- |
| Arte confirmada em japonês ou chinês simplificado | 2.516 (72%) |
| — em japonês | 2.473 |
| — em chinês simplificado | 294 |
| Só provável | 323 |
| Inconclusiva | 479 |
| Não encontrada | 172 |

- **Versão.** Em 1.640 das 2.516, a referência é o próprio registro cuja imagem foi comparada. Nas outras 876 ela é uma variante não conferida, quase sempre Reverse Holo.
- **Candidatas novas.** Há arte confirmada em japonês para 2.339 referências sem confirmação em japonês no PR #53, e em chinês simplificado para 224. Pela regra do PR #53, só viram "Confirmada" depois de conferida a versão.
- **Chinês tradicional.** Os 116 registros confirmados no PR #53 estão na aba CHT PR53 como vieram, sem revalidação, com a situação do japonês correspondente ao lado.

## Prováveis, inconclusivas e não encontradas

Nenhuma destas cartas entrou na tabela de correspondência.

- **Prováveis.** 2.963 cartas têm só equivalente provável: 1.121 em inglês, 1.502 em japonês e 340 em chinês simplificado. Os pares estão na aba Prováveis, com o motivo e os pontos.
- **Inconclusivas e não encontradas.** 8.501 cartas estão na aba Inconclusivos: 7.284 inconclusivas (há um motivo ou uma candidata fraca) e 1.217 não encontradas (nada achado nos catálogos consultados).

Cartas em inglês (2.747 inconclusivas e 485 não encontradas), pelo resultado da busca em japonês:

| Motivo | Cartas | O que significa |
| --- | --- | --- |
| Candidata japonesa de mesmo nome sem imagem no PokeData | 1.589 | O site mostra o verso da carta ou um marcador no lugar da imagem japonesa |
| Não encontrada | 490 | Quase todas anteriores a 2011, onde não há fonte externa para checar |
| Impressão japonesa existe fora do catálogo do PokeData | 404 | O Limitless lista a carta em produtos que o site não tem, como Battle Academy e Starter Decks 100 |
| Imagem parecida, abaixo do limite de confirmação | 292 | Artes texturizadas ou escaneadas com brilho; a candidata está indicada |
| Mesma carta existe em japonês no PokeData, arte não confirmada | 260 | Mesmo texto de jogo, mas a ilustração não bateu |
| Carta em inglês sem imagem no PokeData | 156 | Não há o que comparar |
| Energia básica, versão diferente e outros | 41 | Desenho repetido em muitas impressões ou variante recolorida |

| Idioma | Inconclusivas | Sem imagem no PokeData | Demais motivos | Não encontradas |
| --- | --- | --- | --- | --- |
| Japonês | 3.574 | 2.814 | 760 | 635 |
| Chinês simplificado | 963 | 786 | 177 | 97 |

Cartas japonesas de sets lançados nos últimos cinco meses (111) ficaram como inconclusivas: a versão em inglês pode ainda não ter saído.

## Edições exclusivas de um idioma

340 cartas foram tratadas como exclusivas e ficaram fora da comparação: 319 japonesas e 21 em inglês. Só entra aqui a carta com fonte externa dizendo que não há impressão em outro idioma. Não aparecer nos catálogos não basta: as 635 cartas japonesas que estavam nesta lista só por esse motivo passaram para "não encontrada".

| Idioma | Exclusivas | Critério | Conferência |
| --- | --- | --- | --- |
| Japonês | 319 | A página japonesa da carta no Limitless não lista nenhuma impressão internacional, e a arte não aparece em inglês nem em chinês simplificado no PokeData | 392 cartas de 2010 em diante consultadas: 319 com página e sem impressão internacional; 73 sem página, que ficaram como não encontradas |
| Inglês | 21 | O Limitless lista a carta sem impressão japonesa, e não há equivalente em chinês simplificado no PokeData | Listadas abaixo |
| Chinês simplificado | 0 | Nenhuma marcada: não há fonte externa para o chinês simplificado | As 97 não encontradas estão na aba Inconclusivos |

O Limitless registra impressões da carta, não de uma arte específica. A evidência vale para "esta carta não saiu em outro idioma".

As 21 exclusivas em inglês:

- 14 promos Mega Evolution com os iniciais de cada geração (entre MEP 046 e 063, de Chikorita a Quaxly).
- 5 promos Sword & Shield: Dragapult SWSH132, Zacian LV.X SWSH135, Light Toxtricity SWSH137, Hydreigon C SWSH138 e Greninja Star SWSH144.
- Oddish SVP 102 e Pikachu-EX XY174.

Onde se concentram as exclusivas japonesas:

| Set japonês | Era | Exclusivas |
| --- | --- | --- |
| XY Promos | XY | 63 |
| SM-P Promos | Sun & Moon | 56 |
| Everyone's Exciting Battle | Black & White | 42 |
| Black & White Promos | Black & White | 26 |
| XY Beginning Set | XY | 22 |
| S-P Promos | Sword & Shield | 14 |
| Ash vs Team Rocket Deck Kit | Sun & Moon | 13 |
| SV-P Promos | Scarlet & Violet | 11 |

As 635 japonesas não encontradas ficam em eras sem fonte externa: Web & VS (174), PCG (152), e-Card (81), Platinum (37) e Original (37) somam três quartos delas.

"Exclusiva" vale para os três idiomas do PokeData. Uma carta japonesa desta lista pode existir em chinês tradicional, coreano ou tailandês, que o site não cataloga.

## Planilha

| Aba | Linhas | Conteúdo |
| --- | --- | --- |
| Leia-me | – | Totais por idioma e por era, conferência entre cartas e linhas, cobertura do PR #53; tudo por fórmula |
| Sets | 694 | Idioma, era, código, nome nativo, data e contagens de cada set |
| Catálogo EN | 36.821 | Uma linha por registro: nome, número, raridade, variante, buscas do eBay, situação, códigos equivalentes, candidatas prováveis e se a imagem do registro foi a comparada |
| Catálogo JP | 31.631 | Igual, com nome em japonês |
| Catálogo CN | 15.201 | Igual, com nome em chinês simplificado |
| Correspondência | 18.345 | Inglês → japonês → chinês simplificado, só arte confirmada, com colunas de versão |
| Prováveis | 4.111 | Pares aprovados pela imagem, fora do critério de arte confirmada, com motivo e pontos |
| JP-CN sem inglês | 346 | Pares japonês e chinês de arte confirmada sem carta em inglês confirmada |
| Inconclusivos | 8.501 | Inconclusivas e não encontradas: motivo, candidata mais próxima e impressões japonesas indicadas pelo Limitless |
| Exclusivas | 340 | Critério usado em cada carta |
| Ref. chinês tradicional | 83 | Sets em chinês tradicional listados pelo TCGdex, fora do PokeData |
| Cobertura PR53 | 3.490 | Situação, nesta rodada, de cada referência em inglês do PR #53; sem preços |
| CHT PR53 | 116 | Correspondências em chinês tradicional do PR #53, preservadas sem revalidação |

## Pendências

- [ ] Conferir a versão (edição, acabamento, carimbo) antes de tratar uma arte confirmada como a mesma carta para preço: 13.270 linhas da Correspondência têm variantes.
- [ ] Conferir visualmente os 4.111 pares prováveis.
- [ ] Reprocessar as 3.756 cartas sem imagem quando o PokeData publicar as imagens; a falta se concentra nos sets japoneses das eras Diamond & Pearl, Gym e Neo.
- [ ] Buscar fonte externa para as 1.217 cartas não encontradas; antes de 2011 não há nenhuma.
- [ ] Revalidar por imagem o chinês tradicional do PR #53 e buscar fonte para o restante: o TCGdex tem só parte das cartas.
- [ ] Completar a raridade, em branco no chinês simplificado e em 65% dos registros japoneses.
- [x] Termos de uso do PokeData lidos em 04/10/2026: proíbem copiar, baixar, compartilhar e publicar o conteúdo, salvo para uso pessoal e não comercial, com atribuição. A planilha e os dados extraídos ficam fora de repositório público.
