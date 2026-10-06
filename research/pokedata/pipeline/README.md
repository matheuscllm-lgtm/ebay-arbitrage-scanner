# Catálogo de cartas — correspondências entre idiomas

> Leia primeiro [a revisão técnica de 05/10/2026](../../../docs/POKEDATA_REVISION_20261005.md). Há bloqueadores de integração. A planilha revisada e o CSV descritos abaixo pertencem ao pacote privado, não a esta pasta pública. Os dados em inputs/ são snapshots históricos.

Cruza as cartas em inglês do PokeData com as equivalentes em japonês e chinês simplificado.
A arte é confirmada por comparação de imagem da ilustração, não por nome ou código.
"Arte confirmada" não é versão confirmada: edição, acabamento e carimbo não são conferidos.

Extração feita em 04/10/2026. Resultado completo em `output/PokeData_catalogo_correspondencia.xlsx`.

## Resultado

| Idioma | Sets | Cartas únicas | Arte confirmada | Prováveis | Inconclusivas | Não encontradas | Exclusivas |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Inglês | 183 | 23.047 | 18.673 | 1.121 | 2.747 | 485 | 21 |
| Japonês | 394 | 30.188 | 24.158 | 1.502 | 3.574 | 635 | 319 |
| Chinês simplificado | 117 | 11.006 | 9.606 | 340 | 963 | 97 | 0 |

- 81% das cartas em inglês têm equivalente com arte confirmada em japonês ou chinês simplificado.
- A aba Correspondência tem 18.345 linhas: 17.707 com japonês, 7.189 com chinês simplificado, 6.551 com os dois.
- Das 3.490 referências em inglês do PR #53, 2.516 (72%) têm arte confirmada aqui.
- O PokeData só tem chinês simplificado. Os 116 registros em chinês tradicional do PR #53 estão preservados na planilha.

Detalhes, critérios e limitações: [docs/ENTREGA.md](docs/ENTREGA.md).
Estado do projeto, resposta à crítica do GPT e próximos passos: [docs/ESTADO_DO_PROJETO.md](docs/ESTADO_DO_PROJETO.md).

## Conteúdo da pasta

| Caminho | O que é |
| --- | --- |
| `output/PokeData_catalogo_correspondencia.xlsx` | Planilha final, 13 abas, sem preços |
| `docs/ENTREGA.md` | Documento de entrega: método, números, inconclusivos, exclusivas |
| `docs/ESTADO_DO_PROJETO.md` | O que foi feito, contagens verificadas, limitações, próximos passos |
| `docs/comparacao_pr53.csv` | Os 388 registros confirmados do PR #53 comparados com esta rodada, sem preços |
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
| 0 | `preflight.py` | checagem offline: dependências, disco, pasta não versionada, coleta anterior; falha interrompe | segundos |
| 1 | `fetch_cards.py` | PokeData → `sets.json`, `cards/`, `all_cards.json` | 5 min |
| 2 | `fetch_external.py`, `fetch_tcgdex.py` | pokemon-tcg-data, TCGdex, PokeAPI → `ext/` | 5 min |
| 3 | `catalog.py` | catálogo com raridade, nome nativo, buscas do eBay → `catalog.pkl` | 2 min |
| 4 | `dl_images.py` | uma imagem por carta única → `img/`, `unit_rep.json` | 15 min |
| 5 | `extract.py` | descritores das imagens → `feat_*` | 25 min |
| 6 | `detect_placeholders.py` | cartas com imagem-marcador → `cardback_units.json` | 1 min |
| 7 | `match.py` | candidatas e primeira comparação → `pairs_*.pkl` | 90 min |
| 8 | `stage2_run.py` | segunda comparação → `s2_*.pkl` | 100 min |
| 9 | `limitless_todo.py`, `fetch_limitless.py`, `limitless_pairs.py`, `stage2_pairs.py`, `limitless_classify.py` | checagem externa das cartas sem par → `lim_res.pkl` | 15 min |
| 10 | `assemble.py` | classificação → `result.pkl` | 3 min |
| 11 | `lim_jp.py`, depois `assemble.py` de novo | evidência externa das exclusivas japonesas → `lim_jp.pkl`; a segunda passada aplica | 8 min |
| 12 | `build_xlsx.py` | planilha de entrega; com a planilha do PR #53 como segundo argumento, acrescenta a cobertura das referências e o chinês tradicional | 1 min |
| — | `validate_lim.py`, `sheet.py` | validação por amostra e folhas de contato para conferência visual | — |
| — | `compare_pr53.py` | compara a planilha do PR #53 com o resultado desta rodada → `comparacao_pr53.csv` | 1 min |
| — | `sample_pr53.py` | folhas de contato para a revalidação visual: pares do PR #53 que ficaram "provável/inconclusiva" e amostra dos prováveis → `revalidacao_*.jpg` (locais) | 1 min |
| — | `../accept_run.py` | conferências de aceite de uma execução nova, sem contagens fixas (roteiro, §3) | 1 min |

\* Em uma máquina de 2 núcleos e 8 GB de memória. O total fica perto de 4 horas e 7 GB de disco.

Requisitos: Python 3.10 ou mais novo, `curl`, e os pacotes de `requirements.txt`. As fórmulas da planilha precisam ser recalculadas depois de gerada: abrir e salvar no Excel, ou recalcular com o LibreOffice.

## Como a equivalência é decidida

1. **Cartas únicas.** Registros do mesmo set, número e nome viram uma carta; Reverse Holo, 1st Edition e semelhantes são variantes. A comparação usa uma imagem por carta.
2. **Candidatas.** Para cada carta, as 15 imagens mais parecidas no outro idioma e até 14 cartas de nome compatível.
3. **Comparação.** Pontos SIFT na área da arte, com alinhamento e checagem de cor.
4. **Versões recoloridas.** Rainbow, shiny e dourada compartilham o traço da arte normal. São separadas pela cor e descartadas quando há um par mais forte no mesmo set.
5. **Arte confirmada.** 40 pontos coincidentes ou mais dentro da arte, cores compatíveis e nome compatível entre os idiomas.
6. **Provável.** Par aprovado pela imagem com 12 a 39 pontos, ou com nome divergente entre os idiomas. Fica fora da Correspondência, na aba Prováveis, com o motivo.
7. **Exclusiva** só com fonte externa dizendo que não há impressão em outro idioma. "Não encontrada" é outro status e não quer dizer exclusiva.

As regras estão em `rules.py` e `assemble.py`.

## Cuidados

- **Termos de uso do PokeData.** Releitura oficial em 06/10/2026 ([texto](https://www.iubenda.com/terms-and-conditions/81884871), versão de 12/12/2025; [API](https://www.pokedata.io/api-terms), incorporada por referência). A exceção pessoal/não comercial depende de permissão explícita para aquele conteúdo e atribuição; não é uma autorização geral. Os termos da API também proíbem redistribuir dados da API, site ou aplicativo. `output/` e `docs/comparacao_pr53.csv` continuam privados. Opções para #53 e anexos já públicos: [T6](../../../docs/POKEDATA_TERMOS.md). Código/método separado dos dados é uma opção de entrega a revisar, não uma licença da fonte. Sem parecer jurídico.
- **Portabilidade (T7).** I/O de texto declara UTF-8 (CSV de comparação conserva UTF-8 com BOM). `fetch_cards.py` ficou fora desta alteração por instrução do operador: nele, continuar usando `PYTHONUTF8=1` no Windows até correção pelo dono de T2. IDs externos inválidos falham antes de montar caminhos. Dados iniciados por `=`, `+`, `-`, `@` são texto literal com `quotePrefix` no XLSX; as fórmulas internas continuam ativas e os valores originais são preservados.
- **Arte confirmada é mesma ilustração.** Reverse Holo, 1st Edition, Unlimited, Shadowless e carimbos são variantes da mesma carta, e a versão não é conferida. A coluna Versão da Correspondência mostra as 13.270 linhas em que há variantes.
- **Ritmo de acesso.** Os scripts usam poucas conexões e pausas. Não aumentar.
- **Preços.** Nenhum arquivo daqui contém preços.
- **Prováveis.** Os 4.111 pares da aba Prováveis pedem conferência visual. Em 112 pares vistos lado a lado antes da reclassificação, os 2 erros tinham menos de 40 pontos; entre os de nome divergente há registros do PokeData com nome ou imagem de outra carta.

## Fontes

- [PokeData](https://www.pokedata.io/sets): sets, cartas e imagens.
- [pokemon-tcg-data](https://github.com/PokemonTCG/pokemon-tcg-data): raridade, ilustrador e nome oficial em inglês.
- [TCGdex](https://tcgdex.dev): raridade e nomes em japonês; sets em chinês tradicional.
- [PokeAPI](https://github.com/PokeAPI/pokeapi): nome de cada Pokémon em japonês e chinês.
- [Limitless TCG](https://limitlesstcg.com/cards): impressões japonesas e internacionais de cada carta, de 2011 em diante.
