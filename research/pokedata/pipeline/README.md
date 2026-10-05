# Catálogo de cartas EN / JP / CN e correspondência entre idiomas

> Importado para revisão no PR #53. Antes de usar, leia
> [a revisão vigente](../../../docs/POKEDATA_REVIEW.md): os status abaixo são
> herdados e há achados pendentes. O XLSX completo está no ZIP original
> `../inputs/pokedata_crossref.zip`, membro
> `pokedata_crossref/output/PokeData_catalogo_correspondencia.xlsx`.
> Nesta cópia, `run_pipeline.sh` foi corrigido para interromper em falha de
> qualquer processo de extração; o snapshot original não foi regenerado.
> Revisão Claude (issue #56): `build_xlsx.py` passou a usar `identity.py` para
> exclusividade JP com evidência positiva e deduplicação por número completo + nome.
> Testado só com fixtures; o snapshot não foi regenerado.

Cruza as cartas em inglês do PokeData com as equivalentes em japonês e chinês simplificado.
A equivalência é confirmada por comparação de imagem da ilustração, não por nome ou código.

Extração feita em 04/10/2026. Resultado completo em `output/PokeData_catalogo_correspondencia.xlsx`.

## Resultado

| Idioma | Sets | Cartas únicas | Confirmadas | Inconclusivas | Exclusivas |
| --- | --- | --- | --- | --- | --- |
| Inglês | 183 | 23.047 | 19.794 | 3.232 | 21 |
| Japonês | 394 | 30.188 | 25.660 | 3.574 | 954 |
| Chinês simplificado | 117 | 11.006 | 9.946 | 1.060 | 0 |

- 86% das cartas em inglês têm equivalente confirmado em japonês ou chinês simplificado.
- A aba Correspondência tem 19.433 linhas: 19.100 com japonês, 7.598 com chinês simplificado, 7.265 com os dois.
- O PokeData só tem chinês simplificado. Não há chinês tradicional no site.

Detalhes, critérios e limitações: [docs/ENTREGA.md](docs/ENTREGA.md).
Estado do projeto e próximos passos: [docs/ESTADO_DO_PROJETO.md](docs/ESTADO_DO_PROJETO.md).

## Conteúdo da pasta

| Caminho | O que é |
| --- | --- |
| `output/PokeData_catalogo_correspondencia.xlsx` | Planilha final, 10 abas, sem preços |
| `docs/ENTREGA.md` | Documento de entrega: método, números, inconclusivos, exclusivas |
| `docs/ESTADO_DO_PROJETO.md` | O que foi feito, contagens verificadas, limitações, próximos passos |
| `run_pipeline.sh` | Ordem completa de execução |
| `*.py` | Scripts de cada etapa (tabela abaixo) |

Não entram no repositório: imagens (3,6 GB), descritores (2,5 GB), JSON baixados do PokeData e das fontes externas, e arquivos intermediários `.pkl`. Tudo isso é refeito pelos scripts.

## Etapas

Rodar a partir de uma pasta de trabalho vazia (os scripts leem e gravam na pasta atual):

```bash
mkdir trabalho && cd trabalho
bash ../run_pipeline.sh
```

| Etapa | Script | Entrada → saída | Tempo* |
| --- | --- | --- | --- |
| 1 | `fetch_cards.py` | PokeData → `sets.json`, `cards/`, `all_cards.json` | 5 min |
| 2 | `fetch_external.py`, `fetch_tcgdex.py` | pokemon-tcg-data, TCGdex, PokeAPI → `ext/` | 5 min |
| 3 | `catalog.py` | catálogo com raridade, nome nativo, buscas do eBay → `catalog.pkl` | 2 min |
| 4 | `dl_images.py` | uma imagem por carta única → `img/`, `unit_rep.json` | 15 min |
| 5 | `extract.py` | descritores das imagens → `feat_*` | 25 min |
| 6 | `detect_placeholders.py` | cartas com imagem-marcador → `cardback_units.json` | 1 min |
| 7 | `match.py` | candidatas e primeira comparação → `pairs_*.pkl` | 90 min |
| 8 | `stage2_run.py` | segunda comparação → `s2_*.pkl` | 100 min |
| 9 | `limitless_todo.py`, `fetch_limitless.py`, `limitless_pairs.py`, `stage2_pairs.py`, `limitless_classify.py` | checagem externa das cartas sem par → `lim_res.pkl` | 15 min |
| 10 | `assemble.py` | classificação final → `result.pkl` | 3 min |
| 11 | `lim_jp.py` | checagem externa das exclusivas japonesas → `lim_jp.pkl` | 5 min |
| 12 | `build_xlsx.py` | planilha de entrega | 1 min |
| — | `validate_lim.py`, `sheet.py` | validação por amostra e folhas de contato para conferência visual | — |

\* Em uma máquina de 2 núcleos e 8 GB de memória. O total fica perto de 4 horas e 7 GB de disco.

Requisitos: Python 3.10 ou mais novo, `curl`, e os pacotes de `requirements.txt`. As fórmulas da planilha precisam ser recalculadas depois de gerada: abrir e salvar no Excel, ou recalcular com o LibreOffice.

## Como a equivalência é decidida

1. **Cartas únicas.** Registros do mesmo set, número e nome viram uma carta; Reverse Holo, 1st Edition e semelhantes são variantes.
2. **Candidatas.** Para cada carta, as 15 imagens mais parecidas no outro idioma e até 14 cartas de nome compatível.
3. **Confirmação.** Pontos SIFT na área da arte, com alinhamento. Confirma com 12 pontos coincidentes ou mais dentro da arte e cores compatíveis.
4. **Versões recoloridas.** Rainbow, shiny e dourada compartilham o traço da arte normal. São separadas pela cor e descartadas quando há um par mais forte no mesmo set.
5. **Pares fracos** (12 a 39 pontos) só valem se os dois sets já tiverem outros pares fortes entre si ou se a carta inteira também bater em baixa resolução. Na planilha aparecem como confiança média.
6. **Exclusiva** só com indício positivo. "Não encontrei" vai para os inconclusivos.

As regras estão em `rules.py` e `assemble.py`.

## Cuidados

- **Termos de uso do PokeData.** O texto fica em página externa que não foi possível ler. Conferir antes de tornar o repositório público ou redistribuir a planilha.
- **Ritmo de acesso.** Os scripts usam poucas conexões e pausas. Não aumentar.
- **Preços.** Nenhum arquivo daqui contém preços.
- **Confiança média.** As 1.370 linhas com menos de 40 pontos pedem conferência visual antes de uso em venda. Em 112 pares conferidos lado a lado, os 2 erros estavam nessa faixa.

## Fontes

- [PokeData](https://www.pokedata.io/sets): sets, cartas e imagens.
- [pokemon-tcg-data](https://github.com/PokemonTCG/pokemon-tcg-data): raridade, ilustrador e nome oficial em inglês.
- [TCGdex](https://tcgdex.dev): raridade e nomes em japonês; sets em chinês tradicional.
- [PokeAPI](https://github.com/PokeAPI/pokeapi): nome de cada Pokémon em japonês e chinês.
- [Limitless TCG](https://limitlesstcg.com/cards): impressões japonesas e internacionais de cada carta, de 2011 em diante.
