# Correções de código para o Claude — 05/10/2026

Complementa a revisão `POKEDATA_REVISION_20261005.md`, no PR #53. Implementado e testado offline; não constitui nova validação das correspondências ou das impressões.

## Evidência, decisão e comportamento

| Problema reproduzido | Correção | Arquivos |
| --- | --- | --- |
| Ligação EN–JP–CHS podia promover par fraco a confirmado | Ponte gera somente candidata provável; qualquer avaliação direta existente prevalece, inclusive rejeitada. Nenhuma ponte entra em VIA confirmado. | `assemble.py`, `identity_policy.py` |
| Ranking unia números completos pelo denominador; exportação agrupava unidades distintas | Preservar chave completa set/número/nome. Aliases precisam de prova explícita. | `build_xlsx.py` |
| Lista vazia podia gerar exclusividade | Status automático de exclusiva removido. Ausência, seção ilegível e lista vazia continuam pendências. | `assemble.py`, `limitless_parse.py`, `fetch_limitless.py`, `lim_jp.py` |
| Fila Limitless usava aprovação anterior à exigência de 40 pontos | Fila usa também pontos e compatibilidade de nome. | `limitless_todo.py`, `identity_policy.py` |
| Coleta podia gravar agregado parcial e reutilizar cache inválido | Validar JSON/esquema e set, repetir falhas e interromper agregado incompleto; gravação atômica e manifesto. `common.load()` bloqueia agregado antigo quando manifesto incompleto. | `fetch_cards.py`, `common.py` |

Os arquivos da tabela ficam em `research/pokedata/pipeline/`. O parser marca versão de cache 2; caches Limitless anteriores precisam ser atualizados. Cache sem manifesto permanece aceito para compatibilidade histórica: isso não prova completude nem atualidade. Listas de cartas vazias são aceitas como resposta válida, mas não demonstram inexistência de cartas.

## Validação executada

```
python -m unittest discover -s research/pokedata -p 'test_*.py'
Ran 20 tests
OK
```

Sem testes esperados-falhar. Casos incluem ponte indireta, par direto fraco/rejeitado, números 121/106 e 122/106, limiar 39/40, espécies divergentes, imagem-marcador sintética, seções Limitless ausentes/malformadas/vazias, cache inválido, set errado, IDs duplicados, falha HTTP, preservação do agregado anterior e bloqueio de consumo após coleta incompleta. Os testes de orquestração verificam falha dos processos e segunda montagem após `lim_jp.py`.

Também conferida sintaxe Python e shell. O detector legado emite ResourceWarnings por arquivos sem fechamento explícito; os testes passam. Fixtures controladas, sem coleta externa, sem execução integral das imagens e sem regenerar XLSX/CSV. O CI completo do scanner não foi executado; seu código e regras não foram alterados.

## Próximo passo e limites

1. Reprocessar em ambiente privado com os intermediários de imagens, guardando relatório de cobertura e de coletas incompletas. Contagens da revisão anterior são históricas, não resultado deste código corrigido.
2. Revisar resolução ambígua de referências em `build_xlsx.py` e normalizações de código/número em `compare_pr53.py`; continuam limitações e não foram certificadas por estes testes.
3. Revalidar mesma arte e versão, acabamento, edição e carimbo. Não promover arte confirmada a impressão confirmada.
4. Preservar as 3.490 referências e 116 registros CHT anteriormente auditados; CHS e CHT separados. Nenhum snapshot foi modificado nesta correção.
5. Antes de ampliar publicação de dados, resolver a pendência dos termos da fonte registrada na revisão. Planilha/CSV revisados seguem privados; não remover histórico ou mudar visibilidade automaticamente.

Somente código, testes e documentação nesta entrega. PR atualizado sem merge. Não há equivalência econômica entre idiomas nem mudança da seleção do scanner.
