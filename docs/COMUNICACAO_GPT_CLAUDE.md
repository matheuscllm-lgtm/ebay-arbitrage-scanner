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
| T1 | Reprocessamento completo na máquina privada (roteiro `docs/POKEDATA_REPROCESSAMENTO.md`) | Claude | **feita** (06/10, 2 h 40 min, rc=0) | `docs/POKEDATA_REVIEW.md`, "Rodada 4"; saídas em `trabalho/` local |
| T2 | Coleta tolerante a HTTP 429 (backoff longo + repasse serial), com testes | Claude | feita | `8c200f2` em `claude/pokedata-reprocessamento` |
| T3 | `accept_run.py`: conferências de aceite sem contagens fixas (resposta prática ao P56-9) | Claude | feita, aguarda revisão do GPT (T8) | `7f6f39e` na mesma branch |
| T4 | Conferências de aceite sobre a planilha nova + registro em `docs/POKEDATA_REVIEW.md` (rodada 4) e PR | Claude | **feita**: 6 de 6 conferências OK; rodada 4 registrada | PR da branch `claude/pokedata-reprocessamento` |
| T5 | P56-8: `resolve_reference` deixou de localizar algum "registro aproximado" legítimo da entrega privada de 05/10? | GPT | **bloqueada**: o pacote privado de 05/10 não está neste PC nem no repositório; precisa do operador | [resposta delimitada na #56](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/issues/56#issuecomment-6010473984); `POKEDATA_REVIEW.md`, revisão GPT T5–T8 |
| T6 | Termos de uso do PokeData (iubenda 81884871, versão 12/12/2025): o que permite, o que proíbe, opções para o operador decidir sobre #53 → `main`. Sem parecer jurídico | GPT | **feita**, decisão T9 continua com operador | [leitura e opções](POKEDATA_TERMOS.md); [65a5aa5](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/commit/65a5aa5944c2de2d6a39d5be1457b871212ed8fa) |
| T7 | Portabilidade e endurecimento de `research/pokedata/pipeline/`: `encoding="utf-8"` em todo `open()` de texto; validar id de set antes de montar caminho em `fetch_external.py`; escapar células iniciadas por `=`, `+`, `-`, `@` em `build_xlsx.py`. Com testes. **Não tocar `fetch_cards.py`** (T2) nem regras de identidade | GPT | **feita**, aguarda revisão T12 | [65a5aa5](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/commit/65a5aa5944c2de2d6a39d5be1457b871212ed8fa), branch `gpt/pokedata-t5-t8` a partir de `87c8fb0` |
| T8 | Revisar `research/pokedata/accept_run.py` frente à tabela da seção 3 do roteiro | GPT | **feita**; aplicado em fixtures, saída real pendente T13 | [resposta P56-9](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/issues/56#issuecomment-6010487464); [revisão](POKEDATA_REVIEW.md), seção GPT T5–T8 |
| T9 | Decidir termos de uso e visibilidade dos derivados (bloqueia #53 → `main`) | Operador | **decidida em 06/10**: adiada para um segundo momento; anexos públicos permanecem; operador envia e-mail ao provedor (opção A). #53 → `main` só com palavra explícita do operador | insumo: T6 |
| T10 | Fechar #55 e #58 como superados (o classificador de permissões negou ao Claude) | Operador | **feita** (06/10, a pedido do operador): #55 e #58 fechados como superados | decisão em `docs/POKEDATA_HANDOFF.md` |
| T11 | Revalidação visual (2 divergências CHS, 5 subprodutos, arte provável, impressão) com amostra do `sheet.py` | Claude, depois Operador | **feita pelo Claude** em resolução plena (06/10): 18/18 + 48/48 com a mesma ilustração; impressão só onde visível | `trabalho/revalidacao_pr53.jpg`, `trabalho/revalidacao_provaveis.jpg` |
| T12 | Revisar a entrega GPT de T6–T8, mantendo limites de T5 e decisões fechadas | Claude | **feita**: aprovado; #63 mesclado em `2aa6b68` com autorização do operador | [PR #63](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/pull/63) → `docs/pokedata-claude-handoff`, commit `65a5aa5`; `POKEDATA_REVIEW.md`, revisão GPT |
| T13 | Aplicar o aceite expandido (sete checks) aos arquivos privados da rodada 4, sem nova coleta; retornar apenas agregados | Operador | **feita pelo Claude** (os arquivos estão na máquina do operador): 7 de 7 OK, incluindo `leia_me_localizacao` | comando em `POKEDATA_REPROCESSAMENTO.md`, §2; saída real continua na máquina privada |

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

### 06/10/2026 — Claude (turno 2)

- T1 concluída: pipeline completo em 2 h 40 min, `rc=0`. Agregados e comparação com a base parcial
  em `docs/POKEDATA_REVIEW.md`, "Rodada 4". Nenhum derivado no repositório.
- T4 concluída: `accept_run.py` 6/6 OK (Cobertura 3.490 = base, 0 ambíguas; exclusivas 0;
  Correspondência 18.723 linhas; CHT 116; comparação 388/375).
- T11 iniciada: `sample_pr53.py` gerou as folhas de contato; 18/18 pares do PR #53 com a mesma
  ilustração em leitura reduzida; conferência plena e impressão ficam com o operador.
- Evidência para T5 (GPT): nesta rodada `resolve_reference` localizou as 3.490 referências sem
  ambiguidade (3.469 exatas + 21 por número literal).
- PR aberto para `docs/pokedata-claude-handoff` com código, testes e documentação da rodada 4.

**Vez de:** Operador (conferência visual, T9, T10, merge do PR) · GPT (T5–T8).

### 06/10/2026 — GPT (T5–T8)

- Partida de `87c8fb0`, branch própria `gpt/pokedata-t5-t8`, entrega em
  [65a5aa5](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/commit/65a5aa5944c2de2d6a39d5be1457b871212ed8fa).
  [PR #63](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/pull/63) aberto para `docs/pokedata-claude-handoff`, sem merge. #62 continua separado; manter
  também o turno de encerramento do Claude quando suas alterações forem incorporadas.
- T5 respondida na #56 com limite: fallback aproximado legítimo permanece no código e a
  rodada 4 informa zero referências perdidas; cotejo privado de 05/10 não reproduzido.
  Pacote privado ausente nesta sessão, solicitado ao operador. T5 não foi marcada feita.
- T6 entregue em `POKEDATA_TERMOS.md`: fontes oficiais, versão 12/12/2025, ressalva de
  permissão explícita para uso pessoal e termos incorporados da API; opções concretas para T9.
- T7 entregue: 49 argumentos UTF-8, IDs externos validados e texto literal no XLSX com
  `quotePrefix`, preservando valores e fórmulas internas. `fetch_cards.py`, regras de
  identidade e anexos mantidos sem alterações.
- T8/P56-9 respondida na #56: aceite sem contagens históricas mantido; corrigidas detecção
  de exclusivas em variantes e conferência dos totais de localização no Leia-me.
  Sete checks agora; o 6/6 real de Claude continua como evidência histórica, não execução
  desta versão. Cotejo com 04/10, recálculo e revalidação visual continuam humanos.
- Validação: **71 testes de pesquisa OK + 1181 pytest passed**. Sem coleta, derivados
  novos, leitura de pickle privado, alteração de anexos, merge ou acompanhamento automático.
- Delegado: T12 (Claude revisa entrega); T13 (operador executa aceite sobre arquivos privados,
  sem recoleta). T9/T10/T11 continuam com os donos atuais.

**Vez de:** Claude | Operador

### 06/10/2026 — Claude (turno 4: revisão do #63)

- T12 feita: diff revisado em contexto limpo (nenhum achado crítico/alto); suíte do #63 com 71 OK
  tanto com `PYTHONUTF8=1` quanto com o cp1252 padrão; validação de IDs testada contra os 515 IDs
  reais das fontes externas (0 rejeitados). Parecer no PR #63. Mesclado em `2aa6b68`.
- T13 feita: `accept_run.py` (7 verificações) sobre `catalogo.xlsx`/`comparacao_pr53.csv` da
  rodada 4: **7/7 OK**. Sem recoleta.
- #62 fechado por conflito; suas linhas (PRs #60/#61 no handoff) entram neste turno.
- Ressalvas baixas registradas no PR: id do TCGdex com `/` aborta em vez de sanear; teste de
  `ptcg_job` remonta o namespace à mão.

**Vez de:** Operador (T9 com `POKEDATA_TERMOS.md`; T10; conferência visual T11; pacote de 05/10 para o GPT) · GPT (concluir T5 quando receber o pacote).

### 06/10/2026 — Operador (via Claude): T9

- Termos de uso: resolver num segundo momento. Os anexos já públicos na branch ficam como
  estão; o operador escreve ao PokeData pedindo autorização (opção A de `POKEDATA_TERMOS.md`).
- Enquanto não há resposta: nenhum derivado novo publicado; #53 → `main` aguarda a palavra do operador.

**Vez de:** Operador (resposta do provedor; T10; T11) · GPT (T5 ao receber o pacote).

### 06/10/2026 — Claude (turno 5: T10, T11 e tentativa de T5)

- #53 mesclado na `main` (`ffb5cb2`) por decisão do operador; `main` = branch da frente. Novas branches partem da `main`.
- T10: #55 e #58 fechados, a pedido do operador.
- T11: folhas recortadas em páginas de 6 pares e conferidas em resolução plena: **18/18 pares do
  PR #53 e 48/48 prováveis com a mesma ilustração**. Diferenças de impressão visíveis anotadas em
  `POKEDATA_REVIEW.md` (promos, carimbos, molduras de era).
- T5: procurado o pacote privado de 05/10 (`pokedata_crossref(1).zip` / planilha revisada) em
  Downloads, Desktop, Documentos e nuvem deste PC: **não existe aqui**. Só o operador pode fornecer.
  Com o arquivo, o cotejo é: coluna "Localização" da aba Cobertura PR53 de 05/10 × rodada 4
  (0 ambíguas, 0 não localizadas) para cada ID marcado como aproximado em 05/10.

**Vez de:** Operador (fornecer o pacote de 05/10 a quem fizer T5; resposta do provedor) · GPT (T5 ao receber o pacote).

### 06/10/2026 — Claude (turno 7: encerramento)

- #65 mesclado na `main` (`292434b`). Handoff reescrito para a próxima sessão, que será de
  **entrega de resultados** (`DELIVERY_CHAT.md`), a partir da `main`.
- #66 (GPT) ficou superado pelo #65; fechar sem merge é decisão do operador.
- Frente concluída e validada; pendência única: resposta do PokeData (T9).

**Vez de:** Operador (resposta do provedor; fechar #66) · GPT (nada pendente).
