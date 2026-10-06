# Catálogo de cartas — handoff da frente (nome fixo; atualizar a cada sessão)

Última atualização: **06/10/2026, fim da sessão da rodada 4**. **A frente está na `main`** (#53 mesclado em `ffb5cb2`; #64, #65 depois). Pesquisa concluída e validada; a próxima sessão é de **entrega de resultados** (ver "Como retomar"). Este arquivo
substitui estados descritos em handoffs anteriores desta frente. Fonte de verdade: o código
da branch e os documentos listados abaixo. Este texto é só o mapa.

## Em uma frase

Pesquisa de correspondência entre cartas em inglês, japonês, chinês simplificado e chinês
tradicional (EN, JP, CHS e CHT), feita a partir de snapshots e scripts recebidos (fonte PokeData e externas). **Não está
integrada ao scanner** e não altera nenhuma regra econômica. O GPT e o Claude revisam juntos,
com o operador decidindo.

## Onde está

| Item | Estado em 06/10 |
|---|---|
| Repositório | `matheuscllm-lgtm/ebay-arbitrage-scanner` |
| Branch | **`main`** (PR [#53](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/pull/53) mesclado em `ffb5cb2`, 06/10, por decisão do operador). `docs/pokedata-claude-handoff` não recebe mais trabalho; novas branches partem da `main` |
| PR [#54](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/pull/54) (Claude) | **Mesclado** na branch da frente (`f8a19b1`), com CI verde |
| PR [#57](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/pull/57) (GPT) | **Mesclado** dentro do #54 (`840e482`) |
| PRs #55 e #58 | **Fechados** em 06/10 como superados (a pedido do operador) |
| PR [#60](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/pull/60) (Claude) | **Mesclado** (`24e83c1`): validação do handoff no Windows |
| PR [#61](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/pull/61) (Claude) | **Mesclado** (`87c8fb0`): rodada 4, reprocessamento executado na máquina privada |
| PR [#63](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/pull/63) (GPT) | **Mesclado** (`2aa6b68`): UTF-8 no pipeline, IDs validados, XLSX literal, aceite com 7 verificações, `POKEDATA_TERMOS.md` |
| PRs [#64](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/pull/64), [#65](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/pull/65) (Claude) | **Mesclados** na `main`: handoff pós-#63 e decisão T9; revalidação visual, T5 e fechamentos |
| PR [#66](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/pull/66) (GPT) | Aberto, **superado** pelo #65 (T5 já fechada); conflita nos 3 documentos. Fechar sem merge: operador |
| PR #52 | Outra frente (zh-pairs); sem relação |
| Canal GPT ↔ Claude | `docs/COMUNICACAO_GPT_CLAUDE.md` (quadro + turnos) e issue [#56](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/issues/56) para o histórico. **P56-8 e P56-9 fechados.** Nada pendente do GPT |
| Saídas privadas da rodada 4 | Máquina do operador: `C:\Users\mathe\pokedata-front\research\pokedata\pipeline\trabalho\` (`catalogo.xlsx` 13 abas, `comparacao_pr53.csv`, `aceite*.json`, `revalidacao_*.jpg`, imagens, descritores, `*.pkl`; ~7 GB) e `trabalho/entrega_0510/` (pacote de 05/10). **Nunca versionar nem publicar** |

## Ordem de leitura

1. `CLAUDE.md`, seções "Catálogo de cartas…" e "Atualização da revisão — 05/10/2026".
2. [`POKEDATA_REVISION_20261005.md`](POKEDATA_REVISION_20261005.md), GPT: revisão do pacote recebido em 05/10 e bloqueadores.
3. [`POKEDATA_FIXES_20261005.md`](POKEDATA_FIXES_20261005.md), GPT: correções e próximos passos que geraram a rodada 3.
4. [`POKEDATA_REVIEW.md`](POKEDATA_REVIEW.md): seções do Claude ("Revisão independente", "rodada 2", "Rodada 3") e a do GPT.
5. [`POKEDATA_REPROCESSAMENTO.md`](POKEDATA_REPROCESSAMENTO.md): roteiro preparado e **não executado**.
6. [`POKEDATA_PROJECT_STATE.md`](POKEDATA_PROJECT_STATE.md) e `research/pokedata/pipeline/docs/ESTADO_DO_PROJETO.md`: histórico.

## Estado por item

| Item | Planejado | Implementado | Testado | Validado em execução real |
|---|---|---|---|---|
| Ponte de IDs da base parcial (`bridge_partial_ids.py`) | ✔ | ✔ | ✔ (7 testes) | sobre os snapshots de 04/10 |
| Resolução de referências e normalização de códigos (`pipeline/reference_match.py`) | ✔ | ✔ | ✔ (12 testes) | não: `build_xlsx`/`compare_pr53` dependem de `*.pkl` ausentes |
| Conciliação dos 375 pares (`reconcile_partial.py`) | ✔ | ✔ | contra o #55, números idênticos | sobre o snapshot de 04/10 |
| Sem `exclusiva` automática; chave completa no `rank` (GPT, `0fb962b`) | ✔ | ✔ | ✔ (20 testes do GPT) | não |
| Coleta robusta: manifesto, cache validado (GPT) | ✔ | ✔ | ✔ | não |
| Pré-checagem (`pipeline/preflight.py`, etapa 0) | ✔ | ✔ | ✔ (6 testes) | rodou e bloqueou corretamente neste container |
| Testes de pesquisa no CI (com `numpy`) | ✔ | ✔ | CI verde, 45 testes no log | — |
| Reprocessamento | ✔ (roteiro) | ✔ | — | **executado em 06/10** na máquina do operador (Windows): coleta completa (694 sets, 83.653 registros), `catalogo.xlsx` e `comparacao_pr53.csv` gerados; detalhes em `POKEDATA_REVIEW.md`, "Rodada 4" |
| Conferências de aceite sem contagens fixas (`accept_run.py`) | ✔ | ✔ | ✔ (11 testes) | 6 de 6 OK sobre a planilha de 06/10 |
| Coleta tolerante a HTTP 429 (`fetch_cards.py`) | ✔ | ✔ | ✔ (3 testes) | recuperou os 60 sets que falharam na 1ª tentativa |
| Revalidação visual (arte × impressão) | ✔ (`sample_pr53.py`) | ✔ | — | **conferida em resolução plena (06/10): 18/18 + 48/48 com a mesma ilustração**; impressão (edição, acabamento, carimbo) só onde visível na imagem; detalhe em `POKEDATA_REVIEW.md`, rodada 4 |

## Decisões fechadas: não reabrir sem evidência nova

- `ID EN` da base parcial é o **número da linha** (1..3490), não um ID do catálogo. A ponte usa set, número e nome. Os 21 cadastros duplos do catálogo (`4` × `004`) são resolvidos pela grafia literal do número.
- **Ausência não prova exclusividade.** Não há `exclusiva` automática (GPT, #57 e `identity_policy.overall_status`).
- A chave de identidade usa set_id, número completo e nome. **Não há fusão de aliases**: `036` e `36` ficam separados até haver prova.
- **Arte confirmada ≠ impressão confirmada** (edição, acabamento, carimbo). Nunca promover uma à outra.
- `reference_match.py` é a fonte única de normalização. Um candidato só é escolhido se for único. Subproduto (`151C4` × `151C`) nunca conta como "igual". ♀/♂ viram `f`/`m` no `common.key`.
- `identity.py` foi removido por ter sido superado. O #58 não entra (duplicata). Do #55 entrou só a conciliação.
- **#53 → `main`:** (2) reprocessamento feito (rodada 4). (1) **Decisão do operador em 06/10:** a questão dos termos fica para um segundo momento; os anexos já públicos na branch **permanecem como estão** e o operador contata o provedor por e-mail (opção A de `POKEDATA_TERMOS.md`). O merge na `main` continua dependendo de palavra explícita do operador.
- `research/pokedata/inputs/` fica preservado byte a byte (manifesto SHA-256). Os 116 CHT são preservados como vieram. CHS e CHT ficam separados.

## Números de referência (agregados; servem para conferir, não são entrega)

- Base parcial: 3.490 referências; 388 registros confirmados; 375 pares ID–idioma; 116 CHT.
- Ponte: **3.469 `unico` + 21 `unico_numero_literal`**, 0 sem match. Das 1.785 coincidências numéricas de ID, só 2 são a mesma carta.
- Conciliação com o snapshot de 04/10: **JP 152 iguais e 8 sem equivalente**; **CHS 76 iguais, 5 subprodutos, 2 divergentes (IDs EN 417 e 423) e 29 sem equivalente**; CHT 116 preservados.
- Testes: `unittest` de pesquisa **61 OK** (45 + 5 do 429 + 11 do aceite); `pytest` **1181 passed**.
- Rodada 4 (06/10, execução real): Cobertura PR53 **3.490 = base parcial, 0 ambíguas, 0 não localizadas**; Correspondência **18.723** linhas (JP 18.170, CHS 7.270, ambos 6.717); exclusivas **0**; comparação com a base parcial: **JP 143 igual + 9 provável + 1 inconclusiva + 7 set fora; CHS 69 igual + 5 subprodutos + 7 provável + 1 inconclusiva + 12 sem imagem + 18 set fora**; os IDs 417 e 423 deixaram de divergir (provável com a mesma candidata).
- Conferido em 06/10 numa máquina Windows (Python 3.12): ponte, conciliação, `pytest` e `audit_inputs.py` batem com os valores acima.

## Pendências (dono → o que bloqueia)

1. **Operador:** termos de uso adiados (06/10): anexos ficam públicos por ora; e-mail ao provedor em andamento. Nenhum derivado novo (planilha, CSV, imagens) é publicado até a resposta.
2. ~~Reprocessar~~ **Feito em 06/10** (rodada 4). Os intermediários (`trabalho/`, 7 GB) ficam na máquina do operador; para refazer, o roteiro continua valendo.
3. ~~Conferência visual~~ **Feita em 06/10** (18/18 + 48/48). Para as linhas que forem usadas comercialmente, a impressão (edição, acabamento, carimbo) continua exigindo a carta física ou outra fonte.
4. **GPT:** responder P56-8 (`resolve_reference` deixou de localizar algum "registro aproximado" legítimo da entrega de 05/10?) e P56-9 (`audit_revision.py` precisa de um modo sem contagens fixas?).
5. ~~Fechar #55 e #58~~ **Feito em 06/10**, a pedido do operador.
6. **Operador:** protocolo "bastão" GPT ↔ Claude, **proposto e não aprovado**. Uma issue por frente, com o estado no corpo; cada comentário é um turno com formato fixo e termina com "Vez de: GPT | Claude | Operador"; o operador só repassa a vez.

## Armadilhas já pagas

- Os testes de pesquisa precisam de `numpy` (`research/pokedata/requirements-test.txt`, já no CI). Os scripts de auditoria, ponte e conciliação precisam de `openpyxl`, que não está no `requirements.txt` do scanner.
- **Cada sessão Claude recebe uma branch própria:** trabalhe nela e abra PR para `docs/pokedata-claude-handoff`. Nunca dê push em `gpt/*` nem direto na branch do #53.
- O GPT envia commits com frequência. **Antes de trabalhar:** `git fetch` e merge de `origin/docs/pokedata-claude-handoff` na sua branch. Os conflitos típicos ficam no fim do `POKEDATA_REVIEW.md` (os dois acrescentam seção): mantenha as duas.
- Os dois agentes postam pela **mesma conta GitHub**: assine os comentários.
- A pré-checagem **bloqueia num container de nuvem** (sem `cv2`/`PIL`, raiz versionável). Isso é o esperado; não instale nada só para passar, porque coleta não roda na nuvem.
- `audit_revision.py` tem contagens fixas da entrega privada de 05/10 e não valida uma execução nova.
- O sistema pode criar assinatura de PR sozinho: **cancele** (regra do operador de 12/09). Merge só com autorização explícita do operador.
- Nada de preço, resultado ou derivado no GitHub (`DELIVERY_CHAT.md`). Respostas no chat em até 200 palavras (`CLAUDE.md`).
- **Windows (pago em 06/10):** com `core.autocrlf=true`, o checkout convertia `inputs/manifest.json` e `inputs/ENTREGA_CATALOGO_ORIGINAL.md` para CRLF e `audit_inputs.py` falhava na conferência de bytes. O `.gitattributes` da raiz (`research/pokedata/inputs/** -text`, `*.sh text eol=lf`) resolve; num checkout anterior a ele, apague esses dois arquivos e rode `git checkout -- research/pokedata/inputs research/pokedata/pipeline/run_pipeline.sh`. Leitura de texto sem `encoding="utf-8"` quebra com cp1252: corrigido nos testes e no `audit_inputs.py`, **não** nos scripts de `pipeline/` (dezenas de `open()` sem encoding). Os testes que executam `run_pipeline.sh` são pulados no Windows porque o `bash` que o Python encontra no PATH é o lançador do WSL. Reprocessar no Windows só via WSL ou Linux, como o roteiro já diz.

## Como retomar

Canal de trabalho com o GPT: `docs/COMUNICACAO_GPT_CLAUDE.md` (quadro de tarefas + registro de turnos; atualizar a cada turno).

**Estado ao fechar a sessão de 06/10:** T1–T8 e T10–T13 feitas (reprocessamento, aceite 7/7,
revalidação visual, P56-8/P56-9, portabilidade, termos documentados). Pendência única da frente:
resposta do PokeData sobre os termos (T9, e-mail do operador); até lá, nenhum derivado novo
(planilha, CSV, imagem) é publicado; os anexos já públicos permanecem.

**Próxima sessão: entrega de resultados.** Regra vigente: [`DELIVERY_CHAT.md`](../DELIVERY_CHAT.md)
(resultado só no chat, tabela do gerador canônico, dois links por linha, coleta nova a cada pedido,
nada de preço no GitHub) e o contrato de entrega do `CLAUDE.md`. O catálogo de cartas **não está
integrado ao scanner**: se a entrega for do scanner eBay, ele roda como sempre; se for do catálogo,
a planilha fica local e a entrega são agregados e linhas sem preço, no chat, respeitando os termos.

```bash
cd ebay-arbitrage-scanner
git fetch origin && git checkout -B <branch-da-sessão> origin/main
pip install -r requirements.txt -r research/pokedata/requirements-test.txt
python -m pytest -q                                               # esperado: 1181 passed
python -m unittest discover -s research/pokedata -p 'test_*.py'   # esperado: 71 OK (Windows: skipped=4)
# validação do catálogo sobre a saída privada (só na máquina do operador; PYTHONUTF8=1 no Windows):
T=research/pokedata/pipeline/trabalho
python research/pokedata/accept_run.py $T $T/catalogo.xlsx research/pokedata/inputs/PokeData_correspondencias_JP_CHS_CHT_parcial_recebido.xlsx $T/comparacao_pr53.csv   # esperado: rc=0, 7/7 ok
```

No Windows, o venv do pipeline fica em `research/pokedata/pipeline/.venv` e o shim `python3` em
`pipeline/trabalho/bin/`; `fetch_cards.py` ainda usa o encoding do sistema, então exportar
`PYTHONUTF8=1` antes de qualquer script do pipeline.

## Prompt de abertura da próxima sessão

```
Repo matheuscllm-lgtm/ebay-arbitrage-scanner. Faça fetch e parta de origin/main (a frente
"catálogo de cartas" já está mesclada). Leia docs/POKEDATA_HANDOFF.md (estado, pendência única:
termos do PokeData), DELIVERY_CHAT.md e CLAUDE.md (contrato de entrega). Esta sessão é de entrega
de resultados: siga o contrato (tabela do gerador canônico, verbatim, dois links por linha, só no
chat, coleta nova). Não publique preços, planilhas ou derivados no GitHub; não ative
acompanhamento de PR; merge só com meu "autorizo". Antes de agir, me diga em até 200 palavras o
que vai rodar e o que espera entregar.
```
