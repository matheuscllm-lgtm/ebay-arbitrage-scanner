# Catálogo de cartas — roteiro de reprocessamento

Preparado em 06/10/2026 (revisão Claude, issue #56). **Não executado.** Atende ao item 1 de
[`POKEDATA_FIXES_20261005.md`](POKEDATA_FIXES_20261005.md): reprocessar em ambiente privado,
guardando relatório de cobertura e de coletas incompletas. As contagens dos snapshots de
04/10 e da entrega privada de 05/10 são históricas; nenhuma foi produzida pelo código atual.

## 1. Decisões antes de rodar (do operador)

1. **Termos de uso da fonte.** O pacote recebido afirma que os termos proíbem publicar
   derivados (`research/pokedata/pipeline/.gitignore`); a revisão de 05/10 não conseguiu
   confirmar. Enquanto não houver decisão, a saída fica só na máquina de quem roda.
2. **Intermediários.** Recuperar os da execução original, se ainda existirem (mais barato),
   ou reconstruir com nova coleta: cerca de 4 horas e 7 GB em 2 núcleos e 8 GB de RAM.
3. **Onde rodar.** Na máquina do operador ou noutra privada. Nunca no GitHub Actions: o
   repositório é público, e artifacts e logs seriam publicação (`DELIVERY_CHAT.md`).

## 2. Execução

O pipeline é bash; no Windows, usar Git Bash ou WSL.

```bash
cd research/pokedata/pipeline
python -m venv .venv && .venv/bin/pip install -r requirements.txt
mkdir -p trabalho && cd trabalho                     # pasta ignorada pelo Git
P=../../inputs/PokeData_correspondencias_JP_CHS_CHT_parcial_recebido.xlsx
python ../preflight.py "$P"                          # precisa terminar sem FALHA
bash ../run_pipeline.sh catalogo.xlsx "$P"           # a etapa 0 repete a pré-checagem
python ../compare_pr53.py "$P" comparacao_pr53.csv
```

A pré-checagem (`preflight.py`) recusa: Python < 3.10, pacotes ou `curl` ausentes, menos de
8 GB livres, pasta de trabalho versionável num repositório e coleta anterior marcada como
incompleta. Intermediários sem manifesto geram aviso: o pipeline retoma downloads, mas eles
não comprovam completude nem atualidade.

## 3. Conferências de aceite (na máquina privada)

| Conferência | Esperado | Por quê |
|---|---|---|
| `collection_manifest.json` | `"complete": true` | `fetch_cards.py` recusa agregado parcial |
| Status `exclusiva` gerado automaticamente | nenhum | `identity_policy.overall_status`: ausência não é prova |
| Aba Cobertura PR53 | 3.490 referências com ID, nome, número e set iguais aos da base parcial | mesma regra de `audit_revision.py` |
| Cobertura PR53 → `ambíguo*` e `não localizado*` | contados na aba Leia-me; revisar cada um | `reference_match.resolve_reference` não escolhe às cegas |
| Aba CHT PR53 | 116 registros preservados | o catálogo não tem chinês tradicional |
| `comparacao_pr53.csv` | cotejar com `reconcile_partial.py` (snapshot de 04/10: JP 152 iguais; CHS 76 iguais, 5 subprodutos, 2 divergentes, 29 sem equivalente) | detecta mudança de método e de dados ao mesmo tempo |
| Correspondência | sem número fixo: explicar a diferença frente às 18.345 linhas da entrega de 05/10 | a chave completa separa impressões que antes eram fundidas; os rebaixamentos para provável tiram linhas |

`audit_revision.py` valida a entrega privada de 05/10 com contagens fixas; para uma nova
execução, servem as conferências da tabela, não aquelas contagens.

## 4. O que volta ao repositório

Volta só código, testes e conclusões agregadas (contagens, categorias e decisões), registrados
em `docs/POKEDATA_REVIEW.md` ou na issue da frente. Nunca XLSX, CSV, imagens, descritores,
`*.pkl` nem `ext/`: o `.gitignore` do pipeline bloqueia, e a pré-checagem recusa pasta versionável.

## 5. Depois: revalidação visual

Montar uma amostra rastreável (`sheet.py`) com:
- as 2 divergências CHS (IDs EN 417 e 423);
- os 5 subprodutos (`151C4` × `151C`);
- os pares de arte provável;
- e, para toda linha, a impressão: edição, acabamento e carimbo.

Arte confirmada não é impressão confirmada.
