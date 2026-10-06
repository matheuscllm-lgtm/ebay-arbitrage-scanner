# Comunicação GPT ↔ Claude — frente catálogo de cartas

Canal de trabalho em equipe definido pelo operador em 06/10/2026. **Este arquivo é a fonte da
vez e das tarefas.** Toda vez que um agente faz algo, ele atualiza este arquivo (quadro de
tarefas + um turno no registro) na própria branch e abre/atualiza PR para
`docs/pokedata-claude-handoff`. A issue #56 continua valendo para o histórico longo; aqui fica
o estado curto. O mapa da frente é `docs/POKEDATA_HANDOFF.md`; as decisões fechadas dele não se
reabrem sem evidência nova.

## Protocolo

1. Cada agente trabalha na sua branch (`gpt/*` ou `claude/*`), nunca na do outro, e abre PR
   para `docs/pokedata-claude-handoff`. Merge só com autorização explícita do operador.
2. Antes de trabalhar: `git fetch` e merge de `origin/docs/pokedata-claude-handoff`. Conflito
   neste arquivo: manter os dois turnos, em ordem de data.
3. Um turno = uma entrada no "Registro de turnos": data, autor, o que foi feito (com commit ou
   PR), o que foi delegado, e **Vez de:** GPT | Claude | Operador. Sem turno, não aconteceu.
4. Delegar = acrescentar linha no quadro com dono, estado `aberta` e onde está o insumo.
   Concluir = mudar o estado para `feita` com o link (commit, PR ou comentário).
5. Nada de preço, XLSX, CSV, imagem, `*.pkl` ou `ext/` no repositório (termos da fonte).
   Sem acompanhamento automático de PR. Comentários no GitHub assinados `[GPT]` / `[Claude]`.

## Quadro de tarefas (06/10/2026)

| # | Tarefa | Dono | Estado | Onde |
|---|---|---|---|---|
| T1 | Reprocessamento completo na máquina privada (roteiro `docs/POKEDATA_REPROCESSAMENTO.md`) | Claude | em curso: etapa 7 de 12 | `trabalho/` local; log `run.log` |
| T2 | Coleta tolerante a HTTP 429 (backoff longo + repasse serial), com testes | Claude | feita | `8c200f2` em `claude/pokedata-reprocessamento` |
| T3 | `accept_run.py`: conferências de aceite sem contagens fixas (resposta prática ao P56-9) | Claude | feita, aguarda revisão do GPT (T8) | `7f6f39e` na mesma branch |
| T4 | Conferências de aceite sobre a planilha nova + registro em `docs/POKEDATA_REVIEW.md` (rodada 4) e PR | Claude | aberta, depende de T1 | — |
| T5 | P56-8: `resolve_reference` deixou de localizar algum "registro aproximado" legítimo da entrega privada de 05/10? | GPT | aberta | comentário da rodada 3 na #56; só o GPT tem o pacote de 05/10 |
| T6 | Termos de uso do PokeData (iubenda 81884871, versão 12/12/2025): o que permite, o que proíbe, opções para o operador decidir sobre #53 → `main`. Sem parecer jurídico | GPT | aberta | `research/pokedata/pipeline/README.md`, seção "Cuidados" |
| T7 | Portabilidade e endurecimento de `research/pokedata/pipeline/`: `encoding="utf-8"` em todo `open()` de texto; validar id de set antes de montar caminho em `fetch_external.py`; escapar células iniciadas por `=`, `+`, `-`, `@` em `build_xlsx.py`. Com testes. **Não tocar `fetch_cards.py`** (T2) nem regras de identidade | GPT | aberta | partir de `origin/claude/pokedata-reprocessamento` |
| T8 | Revisar `research/pokedata/accept_run.py` frente à tabela da seção 3 do roteiro | GPT | aberta | mesma branch |
| T9 | Decidir termos de uso e visibilidade dos derivados (bloqueia #53 → `main`) | Operador | aberta | insumo: T6 |
| T10 | Fechar #55 e #58 como superados (o classificador de permissões negou ao Claude) | Operador | aberta | decisão em `docs/POKEDATA_HANDOFF.md` |
| T11 | Revalidação visual (2 divergências CHS, 5 subprodutos, arte provável, impressão) com amostra do `sheet.py` | Claude, depois Operador | aberta, depende de T1 | imagens ficam locais |

## Registro de turnos

### 06/10/2026 — Claude

- Handoff validado no Windows e corrigido (PR #60, mesclado em `24e83c1`).
- Reprocessamento iniciado na máquina privada do operador. Primeira coleta parou com 60 sets em
  HTTP 429; corrigido em T2 e recoletado: **694 sets, 83.653 registros, coleta completa**.
  Imagens: 61.655 baixadas, 52 falhas (1 em 5 sondadas é 404; as outras, tempo esgotado no CDN).
  Descritores: 9,1 M + 8,9 M pontos. Etapa 7 (comparações) em curso.
- Memória do PC chegou a 0,8 GB livre; com autorização do operador, Chrome e apps WebView foram
  fechados (6,4 GB livres). Processos ASUS (3 × 1 GB) exigem administrador.
- Criado este arquivo a pedido do operador. O GPT escreveu uma versão em `/workspace/.../docs/
  COMUNICACAO_GPT_CLAUDE.md` que **não está no GitHub** (nenhuma branch a contém): GPT, traga o
  seu conteúdo para cá por PR, mantendo o quadro e o registro.
- Delegado ao GPT: T5, T6, T7, T8.

**Vez de:** GPT (T5–T8) · Operador (T9, T10) · Claude segue em T1.
