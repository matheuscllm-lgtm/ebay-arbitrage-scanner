# Estado do projeto — cruzamento PokeData (rodada do Claude)

Atualizado em 04/10/2026. Este arquivo registra o que foi feito na rodada do Claude, o que está verificado, o que falta e como isso se liga ao trabalho registrado pelo GPT no PR #53.

## O que foi feito

1. **Extração completa do PokeData**: 694 sets e 83.653 registros de cartas em inglês, japonês e chinês.
2. **Catálogo por idioma → era → set → carta**, com número impresso, raridade (quando há fonte), nome no idioma original e buscas prontas para o eBay.
3. **Separação do chinês**: os 117 sets "Chinese" do site são todos de chinês simplificado. Chinês tradicional não existe no PokeData.
4. **Correspondência entre idiomas por imagem**: 61.657 imagens baixadas e comparadas. O inglês é a referência.
5. **Classificação de cada carta** em confirmada, inconclusiva ou exclusiva, com o motivo registrado.
6. **Checagem externa no Limitless** para cartas de 2011 em diante: separa carta exclusiva de carta cujo equivalente existe fora do PokeData.
7. **Planilha de entrega** com 10 abas e fórmulas de conferência, sem preços.

## Contagens verificadas

Conferidas contra a planilha recalculada (aba Leia-me) e contra os arquivos gerados pelos scripts.

| Item | Valor |
| --- | --- |
| Sets (EN / JP / CN simplificado) | 183 / 394 / 117 |
| Registros | 36.821 / 31.631 / 15.201 |
| Cartas únicas | 23.047 / 30.188 / 11.006 |
| Confirmadas | 19.794 / 25.660 / 9.946 |
| Inconclusivas | 3.232 / 3.574 / 1.060 |
| Exclusivas | 21 / 954 / 0 |
| Linhas na aba Correspondência | 19.433 |
| — com japonês / com chinês / com os dois | 19.100 / 7.598 / 7.265 |
| — confiança alta / média | 18.063 / 1.370 |
| Pares japonês–chinês sem inglês | 211 |
| Cartas sem imagem utilizável no PokeData | 3.756 (EN 156, JP 2.814, CN 786) |

Validação:

- 389 pares confirmados sorteados e comparados com o Limitless: 372 batem em set e número, 17 são números de cartas secretas que o Limitless não lista, nenhum indica carta errada.
- 112 pares vistos lado a lado: 2 erros, os dois com menos de 40 pontos coincidentes (um deles de uma regra para energias que depois foi removida).
- 319 das 394 exclusivas japonesas de 2010 em diante têm página no Limitless; nenhuma lista impressão internacional.

## Limitações conhecidas

- **Variantes de traço igual.** Cartas douradas ou pretas com o mesmo traço da arte colorida podem passar como equivalentes na faixa de confiança média. Foi o erro visto na amostra (Zacian V dourada).
- **Artes texturizadas.** Full arts fotografadas com textura dão poucos pontos coincidentes e caem nos inconclusivos mesmo sendo a mesma carta (exemplo: Dragonite-GX, Dragon Majesty 67/70).
- **Catálogo japonês do PokeData incompleto.** Faltam decks e promos (Battle Academy, Starter Decks 100, 30th Celebration japonês). Cartas em inglês vindas desses produtos ficam inconclusivas.
- **Sem imagem.** Sets japoneses das eras Diamond & Pearl, Gym e Neo mostram o verso da carta no lugar da imagem.
- **Raridade.** O PokeData não publica. Japonês tem raridade em 35% dos registros; chinês simplificado não tem.
- **Cartas anteriores a 2011 sem par** (490 em inglês) não têm fonte externa para dizer se são exclusivas.
- **Termos de uso do PokeData** não foram lidos (página externa inacessível).

## Relação com o PR #53 (trabalho do GPT)

O que se sabe do PR #53, pela descrição recebida na conversa (os arquivos do PR ainda não foram lidos nesta rodada):

- Branch `docs/pokedata-claude-handoff`, sem merge.
- `CLAUDE.md` com orientação de leitura e `docs/POKEDATA_PROJECT_STATE.md` com o estado daquele trabalho.
- Planilha `PokeData_correspondencias_JP_CHS_CHT_parcial.xlsx`: 3.490 referências em inglês e cruzamento parcial com japonês, chinês simplificado e chinês tradicional.
- 388 registros confirmados na planilha, que correspondem a 375 pares únicos carta–idioma. As imagens não foram revalidadas naquela rodada.
- Regra do repositório: planilha com preços fica fora do GitHub. Nenhuma regra do scanner foi alterada.

Como os dois trabalhos se completam:

| | Rodada do GPT (PR #53) | Rodada do Claude (esta pasta) |
| --- | --- | --- |
| Referências em inglês | 3.490 | 23.047 (catálogo inteiro do PokeData) |
| Pares confirmados | 375 pares carta–idioma | 19.433 linhas, 26.698 pares carta–idioma |
| Critério de confirmação | Descrito em `docs/POKEDATA_PROJECT_STATE.md` | Comparação de imagem da ilustração |
| Chinês tradicional | Incluído (CHT) | Ausente: não existe no PokeData |
| Preços | Fora do GitHub | Nenhum |

## Próximos passos

- [ ] Ler `CLAUDE.md` e `docs/POKEDATA_PROJECT_STATE.md` do PR #53 e ajustar este arquivo ao que estiver lá.
- [ ] Comparar os 375 pares do GPT com a aba Correspondência: quantos coincidem, quantos divergem e por quê.
- [ ] Trazer o chinês tradicional da planilha do GPT como coluna nova da Correspondência, marcando a fonte.
- [ ] Decidir qual planilha fica como a oficial do projeto e apontar o `CLAUDE.md` para ela.
- [ ] Filtrar a Correspondência para as 3.490 referências que o scanner usa, se esse for o recorte de trabalho.
- [ ] Conferir visualmente as 1.370 linhas de confiança média.
- [ ] Reprocessar quando o PokeData publicar as imagens que faltam.
