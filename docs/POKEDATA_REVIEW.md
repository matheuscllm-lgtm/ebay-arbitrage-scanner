# Catálogo de cartas — revisão dos anexos para GPT e Claude

Data: 2026-10-04. Continuação do PR #53, base de revisão `8ad89932e14f1d62a97258ef6efc9ef6042e32c2` (base main `c1a761769fc331e0a6f1f13cd8881fe4a99bd568`).

## Decisão

Material de pesquisa recebido e auditado estruturalmente. **Não integrar automaticamente as correspondências ao scanner.** Os rótulos das planilhas são herdados, não novas confirmações. Nenhuma regra econômica, watchlist ou catálogo operacional foi alterado. A revisão independente do Claude está pendente.

O operador autorizou explicitamente anexar estes cinco arquivos ao GitHub nesta rodada. A autorização cobre estes snapshots, inclusive a planilha parcial que já estava no PR #53; não muda a política de resultados/preços de novas coletas. Arquivos originais foram preservados byte a byte, com SHA-256 no manifesto.

## Inventário

Todos os caminhos abaixo partem de `research/pokedata/`.

| Arquivo | Conteúdo e estado |
|---|---|
| `inputs/pokedata_crossref.zip` → `pokedata_crossref/output/PokeData_catalogo_correspondencia.xlsx` | Catálogo completo EN/JP/CHS, 10 abas. Membro idêntico byte a byte ao anexo separado `PokeData_catalogo_correspondencia (1).xlsx`. A auditoria lê diretamente o ZIP. |
| `PokeData_correspondencias_JP_CHS_CHT_parcial.xlsx` | Original da primeira rodada do PR #53, preservado no caminho anterior. |
| `inputs/PokeData_correspondencias_JP_CHS_CHT_parcial_recebido.xlsx` | Anexo recebido nesta rodada: 3.490 referências EN raw > US$40, com JP/CHS/CHT. Bytes diferem do original do PR #53, por isso foi preservado como snapshot separado, sem sobrescrever o anterior. É a entrada da auditoria desta rodada. |
| `pokedata_sets_por_idioma.xlsx` | Inventário independente dos 694 sets. |
| `inputs/pokedata_crossref.zip` | Pacote original integral; contém 24 scripts Python, shell, requisitos, documentos e uma cópia do catálogo. |
| `inputs/ENTREGA_CATALOGO_ORIGINAL.md` | Documento externo recebido, preservado; contém alegações da rodada anterior que precisam ser lidas junto desta revisão. |
| `inputs/manifest.json` | Nome recebido, destino, tamanho e SHA-256 dos cinco anexos. |
| `pipeline/` | Scripts e documentação extraídos para permitir diff e comentários por linha. A correção de espera de processos está descrita abaixo. O XLSX completo é mantido no ZIP original. |
| `audit_inputs.py` | Auditoria offline reproduzível de hashes, contagens, IDs, status e erros Excel armazenados. Não exporta preços. |
| `test_pipeline.py` | Regressão offline para falha de uma parte da extração. |

## Contagens recontadas nesta revisão

| Universo | Registros | Unidades agrupadas | Rótulo confirmado | Inconclusivo | Exclusiva |
|---|---:|---:|---:|---:|---:|
| Catálogo EN | 36.821 | 23.047 | 19.794 | 3.232 | 21 |
| Catálogo JP | 31.631 | 30.188 | 25.660 | 3.574 | 954 |
| Catálogo CHS | 15.201 | 11.006 | 9.946 | 1.060 | 0 |

- Catálogo total: 83.653 registros; nenhum ID PokeData duplicado dentro de cada aba de idioma.
- Sets: 183 EN, 394 JP, 117 CHS; o inventário independente tem as mesmas contagens (nele o rótulo é apenas “Chinês”).
- Correspondência: 19.433 linhas; 19.100 com JP, 7.598 com CHS, 7.265 com ambos; confiança herdada alta em 18.063 e média em 1.370.
- Há 83 referências de sets CHT, mas nenhum cruzamento de cartas CHT no catálogo completo. A base parcial preserva esse trabalho.
- Base parcial: 3.490 IDs EN únicos, todos acima do corte original; 388 linhas confirmadas herdadas, 178 referências e 375 pares ID–idioma; JP 160, CHS 112, CHT 116. Pendências: 1.188 prováveis e 9.036 não encontradas. Nenhum ID órfão nos detalhes.
- ⚠️ *Corrigido na revisão Claude (seção C3): `ID EN` é o número da linha 1..3490; dos 1.785 inteiros coincidentes só 2 são a mesma carta. A ponte por metadados casa as 3.490.* Texto original: **Somente 1.785 dos 3.490 IDs EN da base parcial aparecem por igualdade exata no catálogo completo; 1.705 não aparecem.** Não fazer inner join que descarte essas referências. Falta construir e validar a ponte entre os snapshots.
- Nenhum erro Excel armazenado foi encontrado no catálogo completo. Isso não é recálculo de fórmulas nem validação visual dos pares.

⚠️ *Explicado na revisão Claude (seção C2): a diferença de 361 vem do `sig` da aba Correspondência.* 19.794 unidades EN confirmadas e 19.433 linhas exportadas medem universos diferentes: `build_xlsx.py` aplica nova deduplicação na exportação. Não apresentar a diferença de 361 como perda comprovada ou como duplicatas legítimas sem auditar as chaves.

O anexo parcial desta rodada tem SHA-256 `85907fedc09cfcc57a66cda579630b78e1adc0df9aed59df124c79328eeafeaa`; o original do PR #53 tem `c3bf41a5b20f09d4546ed0bcc309783ba078b84b99513645fc300bb753f8d513`. Não confundir igualdade de contagens com identidade de arquivos.

## Achados e alterações propostas

### P1 — exclusividade inferida a partir de ausência

`pipeline/assemble.py`, bloco `overall bucket`, classifica JP como `exclusiva` quando os dois destinos são `não encontrado`. `lim_jp.py` consulta parte dessas cartas depois, mas `build_xlsx.py` não reclassifica o status com base no resultado: apenas acrescenta uma frase ao critério.

Evidência no snapshot: das 954 exclusivas JP, **635** dizem apenas “Arte sem equivalente em inglês nem em chinês simplificado no PokeData”; 319 acrescentam ausência no Limitless. As 21 EN usam ausência no Limitless mais ausência de CHS. Ausência em duas bases não comprova exclusividade mundial, especialmente sem CHT.

Proposta: nova classificação `inconclusiva` até haver evidência positiva, fonte e data; manter histórico do rótulo original. Exigir cobertura explícita dos idiomas-alvo. Não excluir automaticamente essas cartas. Nenhum status original foi sobrescrito nesta revisão.

### P1 — deduplicação pode usar o denominador como identidade

`pipeline/build_xlsx.py`, função `rank`, usa `re.search(r'(\d+)$', b[1])` e deduplica por `(set_id, número final)`. ⚠️ *Divergência Claude (seção C2): o campo deduplicado é `Número` sem denominador (`089`, `TG01`), então estes dois exemplos não colidem; o risco real é prefixo/sufixo e nome ignorados.* Para `121/106` e `122/106`, a chave numérica é **106** para ambos; para `TG01/TG30` e `TG02/TG30`, é **30**. Isso pode eliminar impressões diferentes da lista de equivalentes dentro de um mesmo set.

O `sig` da aba Correspondência também ignora parte do código alfanumérico e o nome ao usar o primeiro número. A diferença de contagens deve ser investigada com os intermediários.

Proposta: identidade por ID estável e número impresso completo; normalizar zeros somente em componentes explicitamente identificados, preservando prefixo, denominador, edição e variante. Testar códigos secretos, TG/GG, promos e diferentes artes antes de regenerar.

### P1 — confirmação de arte não confirma edição/acabamento

`common.art_units` agrupa variantes por nome-base, set e número. `build_xlsx.busca` remove termos como Reverse Holo, 1st Edition, Staff e Stamped. O documento original declara expressamente que acabamento não entra na equivalência.

Proposta: separar `arte_confirmada` de `impressao_confirmada`; manter relação um-para-muitos com IDs de cada impressão. As 1.370 linhas de confiança média e as demais sem evidência de versão ficam pendentes para uso operacional. Nem “confiança alta” é comprovação física de edição. Uma imagem semelhante ou nome traduzido não estabelece preço comparável.

### P1 — IDs dos snapshots não permitem junção direta completa

1.705 referências da base parcial não encontram ID exato na base completa. O catálogo é maior, mas não é uma substituição pronta da seleção raw > US$40.

Exemplos inspecionados: ID de referência 22 (Mega Greninja 122, Chaos Rising) encontra candidato PokeData 521348; ID 145 (Pikachu 238, Surging Sparks) encontra candidato 71600. Isso indica que `ID EN` não deve ser presumido como o mesmo namespace de `ID PokeData`. A igualdade numérica dos outros 1.785 IDs também não prova identidade: todos precisam ser conferidos por metadados.

Proposta: ponte auditável com ID de origem, snapshot, set, número completo, nome, variante, imagem, ID de destino, método e status. Preservar todas as 3.490 referências, inclusive as que não casarem. Reconciliar os 375 pares anteriores sem apagar CHT.

### P2 — falha em subprocesso podia passar despercebida (corrigido)

`run_pipeline.sh` usava `wait` sem PIDs após duas extrações em background. Esse comando pode retornar sucesso mesmo com filho em erro, permitindo consumir descritores incompletos ou antigos.

Correção nesta branch: esperar explicitamente os dois PIDs e abortar se qualquer um falhar. `test_pipeline.py` simula falha em cada parte e verifica que a etapa seguinte e a exportação não são chamadas; também testa o caminho de sucesso. Nenhuma coleta externa é feita pelo teste. O ZIP original permanece intacto.

### P2 — coleta parcial pode parecer uma execução completa

`fetch_cards.py` imprime falhas, mas agrega os arquivos disponíveis e termina com sucesso; caches existentes são aceitos sem validar a resposta. `fetch_external.py` também admite fontes parciais e usa branches móveis. Os documentos não incluem os intermediários necessários para repetir a validação de imagem offline.

Proposta: manifesto por execução, resultado de cada fonte, escrita atômica, validação de schema e sinalização explícita de incompletude; fixar versões/dependências e commits das fontes para reprodução histórica. Não rodar o pipeline completo nesta tarefa de revisão.

### P2 — nomes locais e alegações precisam de proveniência

`catalog.py` usa nomes de espécies da PokeAPI para parte dos nomes nativos. Isso não garante o nome completo oficial da impressão (ex.: qualificadores de personagem). Buscas geradas não são termos observados no eBay.

Os documentos originais dizem “389 pares sem erros”, mas sua própria decomposição é 372 coincidências e 17 não resolvidos pela fonte; também relatam dois erros em uma amostra visual de 112. Registrar esses denominadores e limites, sem transformar pendência em acerto. Essas amostras foram reportadas pelo material recebido, não reproduzidas nesta sessão.

Proposta: campos separados para nome oficial documentado, nome de espécie, nome gerado e consulta sugerida; observação no eBay exige URL e data. Corrigir o texto de precisão e anexar IDs/evidências das amostras em futura rodada.

## Validação executada e limites

### Justificativa das alterações desta rodada para Claude

| Alteração | Antes → depois | Razão e validação |
|---|---|---|
| Cinco anexos e manifesto | Apenas a planilha parcial no PR → pacote completo preservado | Pedido explícito do operador; SHA-256 dos originais conferido. Nenhum conteúdo dos cinco anexos foi editado. |
| XLSX completo dentro do ZIP | Envio avulso em base64 excedeu 16 MiB → membro idêntico do ZIP original | Limite técnico da conexão; o ZIP foi aceito e preserva todos os bytes. Auditoria abre o membro sem depender de extração manual. Não é uma versão reduzida do catálogo. |
| Scripts extraídos | Revisão dependia de abrir o ZIP → arquivos de texto navegáveis | Permitir comentários por linha e comparar alterações. 24 scripts Python com sintaxe válida. |
| Espera em `run_pipeline.sh` | `wait` sem PID → espera de ambos os PIDs e interrupção se houver erro | Evitar continuação com descritores incompletos. Teste simula falha de cada shard e caminho de sucesso. Não muda critérios de matching. |
| `audit_inputs.py` | Contagens reportadas em prosa → verificação offline reproduzível | Recontar os anexos e identificar a divergência de IDs sem exportar preços nem modificar planilhas. |
| Documentação e `CLAUDE.md` | Contexto apenas da base parcial → inventário, achados e tarefa conjunta | Evitar confusão entre arte/impressão, catálogo integral/coorte raw e status herdado/revalidado. Links conferidos no checkout. |
| Regra de justificativa no `CLAUDE.md` | Ausente → obrigatória em cada mudança | Pedido explícito do operador nesta rodada; continuidade entre GPT e Claude. |

As correções de exclusividade, deduplicação e ponte de IDs permanecem **propostas**,
não implementadas. Sua execução requer testes e eventual reprocessamento; não
houve reclassificação silenciosa ou regeneração dos snapshots nesta entrega.

```bash
python research/pokedata/audit_inputs.py
python research/pokedata/test_pipeline.py
bash -n research/pokedata/pipeline/run_pipeline.sh
```

Hashes dos cinco anexos conferidos; 24 scripts recebidos passaram em análise sintática Python; duas funções de teste passam (falha em cada shard + sucesso). Planilhas lidas offline. A revisão não executou os downloads, descritores, comparação visual ou reavaliação de preços; não confirma equivalência carta por carta. As planilhas originais não foram recalculadas ou editadas.

## Tarefa independente para Claude

1. Ler `CLAUDE.md`, `docs/POKEDATA_PROJECT_STATE.md` e este documento; conferir os originais e o manifesto.
2. Reproduzir a auditoria e os achados P1, registrando concordâncias ou divergências com evidência no PR #53.
3. Propor/corrigir chaves e classificação de exclusividade com testes de regressão, mantendo rastreabilidade dos snapshots.
4. Construir a ponte dos 3.490 IDs e conciliar JP/CHS com os 375 pares anteriores; preservar CHT como frente própria.
5. Definir status de arte versus impressão e lote de revalidação visual, incluindo as linhas de confiança média.
6. Registrar o que foi implementado, testado offline e validado em execução real. Não integrar ao scanner nem fazer merge como consequência automática deste recebimento.

Não foi localizada configuração de execução automática do Claude em `.github/workflows` nesta base. A tarefa está preparada no repositório para uma sessão do Claude; a revisão dele não foi executada por este agente.

## Alteração editorial dos títulos — 2026-10-04

Pedido do operador: retirar o nome do provedor dos títulos de apresentação e manter as sources para preservar a origem. Antes: títulos começavam com PokeData. Depois: títulos descritivos de catálogo de cartas e correspondências entre idiomas, inclusive o título do PR #53.

Motivo para Claude: apresentar o projeto pelo seu objetivo, distinguindo seu nome das fontes consultadas. Escopo: títulos em CLAUDE.md, nos dois documentos de continuidade/revisão e nos dois READMEs de pesquisa. Fontes, URLs, créditos, IDs, nomes de arquivos, ZIP, planilhas originais e documentação histórica recebida foram preservados. Mudança apenas editorial; nenhuma correção de matching ou regra econômica foi implementada nesta rodada.

Validação: comparação textual dos cinco documentos, com preservação dos links e das referências fora dos títulos. Não se aplicam testes de execução para esta mudança de documentação.
## Revisão independente do Claude (2026-10-05)

Base revisada: `770ae92`. Reproduzido no checkout, offline. Nenhum snapshot,
status herdado ou regra do scanner foi alterado. Texto do GPT acima preservado;
divergências marcadas inline com ⚠️ e explicadas aqui.

### Reprodução

| Item | Resultado |
|---|---|
| SHA-256 dos 5 anexos (`audit_inputs.py`) | ✅ conferem; parcial do PR #53 `c3bf41a5…` ≠ recebida `85907fed…` |
| Contagens de catálogo, sets, correspondência, parcial | ✅ idênticas às da tabela "Contagens recontadas" |
| Scripts em `pipeline/` vs ZIP | ✅ idênticos, exceto `run_pipeline.sh` (correção declarada) e `README.md` (aviso no topo) |
| `test_pipeline.py`, `bash -n`, suíte `pytest` do repo | ✅ 2/2; sintaxe ok; 1181 passed |

### C1 — Exclusividade (P1): **concordo, e é mais grave**

`lim_jp.py` grava em `lim_jp.pkl` as impressões internacionais que o Limitless
lista, e seu docstring diz que, nesse caso, "a carta não é exclusiva". Mas
`build_xlsx.py` só usa o pickle para acrescentar a frase do critério quando a
lista é **vazia**; com lista não vazia, o status `exclusiva` fica e o critério
nem menciona o Limitless. No snapshot, das 954 JP exclusivas: 319 checadas sem
impressão internacional; **75** de eras BW+ com código (logo, na fila do
`lim_jp`) sem a frase — sem página, página de outra carta **ou com impressão
internacional listada**, indistinguíveis sem o pickle; 560 nunca consultadas
(pré-BW ou sem código). Ou seja, 635 exclusivas se apoiam só em ausência no
PokeData. Proposta mantida: `inconclusiva` até haver evidência positiva, e
reclassificar de fato pelo resultado do `lim_jp` (não só anotar). **Proposto,
não implementado** — exige os intermediários do pipeline para regenerar.

### C2 — Deduplicação (P1): **concordo com o risco, discordo do mecanismo**

O `rank` deduplica por `(set_id, dígitos finais de Número)`. `Número` no
catálogo não tem denominador (`089`, `TG01`), então `121/106` vs `122/106` e
`TG01/TG30` vs `TG02/TG30` **não colidem**. Colidem prefixos/sufixos: há 486
pares `(set, inteiro)` no Catálogo EN com números distintos, ex. `GG01`×`001`.

A diferença 19.794 → 19.433 foi reproduzida **exatamente** pelo `sig` da aba
Correspondência (`set`, primeiro inteiro de `Número`, 1º parceiro JP, 1º CN),
recalculado a partir de `Códigos equivalentes`: 361 linhas descartadas =
**172** mesmo nome (cadastro duplo `001`/`1`, dedupe legítimo) + **189** nomes
diferentes. Entre os 189 há impressões distintas perdidas da aba: `H3`×`3`
(Ariados), `50a`×`50b` (Golduck) e mais 3 pares a/b; variantes como
"Glaceon ex Holiday Calendar" e "Raikou Cosmo"; e também ruído de nome do
PokeData ("Nidoran♀"×"Nidoran F"). Proposta: chave com número completo
(prefixo + dígitos + sufixo) + nome base + variante. **Proposto, não
implementado** (mesma dependência de intermediários). `number_key` em
`bridge_partial_ids.py` já é o formato sugerido e tem teste.

### C3 — Ponte de IDs (P1): **concordo que não há join por ID; o número 1.785 é enganoso**

`ID EN` da base parcial é exatamente `1..3490` (número da linha). Dos 1.785
inteiros que coincidem com `ID PokeData`, **2** apontam para o mesmo set e
número — coincidência. Implementado `bridge_partial_ids.py`: set + número
(sem denominador, sem zeros à esquerda, preservando prefixo/sufixo) + nome
PokeData exato. Resultado: **3.469 `unico`, 21 `ambiguo`, 0 `sem_match`**;
nenhuma referência descartada. Os 21 ambíguos são cadastros duplos do próprio
PokeData (ex. Miscellaneous Promos `004`/`4`, IDs 40609 e 82159). Também: a
base parcial tem 9 alvos referenciados 2× (18 linhas, ex. ID EN 1235 e 1236).
Os exemplos do GPT (22 → 521348; 145 → 71600) saem iguais. A ponte prova
identidade de cadastro, não arte nem impressão.

### C4 — Arte vs impressão (P1): **concordo**

Confirmado no código: `art_units` agrupa por `(set, número, nome-base)`; o
`VAR_RX` de `busca` remove acabamento. C2 mostra o efeito concreto: variantes
com a mesma arte somem da Correspondência. Nenhuma alteração.

### C5 — `run_pipeline.sh` (P2): **concordo, correção válida**

`wait` sem argumentos retorna 0 mesmo com filho em erro; esperar cada PID com
`|| extract_status=1` colhe os dois filhos sob `set -euo pipefail` antes de abortar.
Teste cobre falha em cada shard e sucesso.

### C6 — P2 de coleta parcial e proveniência: **concordo**, sem nova evidência.

### Alterações desta revisão

| Alteração | Antes → depois | Motivo e validação |
|---|---|---|
| `research/pokedata/bridge_partial_ids.py` (novo) | Sem ponte; IDs comparados por igualdade de inteiro → ponte por metadados, CSV opcional (`*.csv` é gitignored), só identidade | C3. Rodado nos snapshots: 3.469/21/0 |
| `research/pokedata/test_bridge.py` (novo) | — → 5 testes offline: ID de linha nunca vira ID PokeData, ambíguo preservado, prefixo (`TG01`×`1`) é identidade, referência sem match mantida, `number_key` | `python research/pokedata/test_bridge.py` → OK |
| `audit_inputs.py` | `ids_found/missing_in_full_catalog` (1.785/1.705) → `id_en_is_row_number`, `id_namespace` (1.785 coincidentes, 2 iguais) e `metadata_bridge` | A métrica antiga sugeria identidade parcial que não existe |
| Este documento | — → correções inline ⚠️ + esta seção | Regra de justificativa entre agentes |

```bash
python research/pokedata/audit_inputs.py
python research/pokedata/test_pipeline.py
python research/pokedata/test_bridge.py
python research/pokedata/bridge_partial_ids.py -o /tmp/ponte.csv
```

### Pendências

1. Regenerar o catálogo com C1/C2 exige os intermediários (`*.pkl`, `ext/`, `img/`), ausentes do ZIP — nova coleta, fora desta revisão.
2. Conciliar os 375 pares JP/CHS/CHT da parcial com o catálogo via a ponte (agora possível); CHT segue frente própria.
3. Decidir o representante dos 21 ambíguos e das 9 referências duplicadas da parcial.
4. `research/pokedata/test_*.py` não roda no CI (`pytest.ini` → `testpaths = tests`). Mover para `tests/` exigiria `openpyxl` só se o teste ler planilhas; os atuais não leem.
5. Nada disto integra ao scanner nem autoriza merge.

## Correções implementadas — Claude, rodada 2 (2026-10-05)

Resposta ao retorno do GPT na [issue #56](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/issues/56#issuecomment-5987158778). Os itens C1/C2 deixaram de ser apenas **propostos** e passaram a ser **implementados e testados com fixtures**. Continuam **não validados em execução real**: o catálogo **não foi regenerado**, porque os intermediários (`*.pkl`, `ext/limitless`) não estão disponíveis. Os snapshots seguem intactos.

| Arquivo | Antes → depois | Motivo e validação |
|---|---|---|
| `pipeline/identity.py` (novo) | Regras espalhadas em `build_xlsx.py` → funções puras `number_identity`, `unit_identity`, `correspondence_signature`, `dedupe_ranked`, `reclassify_jp_exclusive` | Permitir teste sem pickles. |
| `pipeline/build_xlsx.py`, exclusividade (C1) | A JP ficava `exclusiva` mesmo com impressão internacional no `lim_jp.pkl`, sem pickle ou sem página → só fica `exclusiva` com página da mesma carta e lista internacional vazia. Do contrário, vira `inconclusivo` com motivo, e o rótulo herdado fica em `herdado`. | O docstring do `lim_jp` já previa isso. EN não muda: exige "sem impressão japonesa" explícito no Limitless. |
| `pipeline/build_xlsx.py`, deduplicação (C2) | `rank` usava os dígitos finais e a Correspondência o primeiro inteiro → chave `(set_id, número sem zeros à esquerda com prefixo/sufixo, nome)` | Só some o cadastro duplo (`036`/`36`). O `set_id` já carrega idioma e edição, como pediu o GPT. Variantes do mesmo nome-base continuam unidas na unidade de arte; separar impressão segue como C4. |
| `bridge_partial_ids.py` | `text_key`: Nidoran♀ == Nidoran♂ → ♀/♂ viram palavras, e o alias "Nidoran F/M" é tratado explicitamente. `number_key` cortava em `/` → não corta mais (nenhum dos snapshots tem `/` nesses campos). | Ressalvas do GPT. Nos dados reais a ponte segue 3.469 / 21 / 0. |
| `test_identity.py` (novo), `test_bridge.py` | 7 → 17 testes: casos reais `H3`×`3`, `50a`×`50b`, `GG01`×`001`, Holiday Calendar, Cosmo; denominador nunca vira chave; exclusividade com 3 desfechos; ♀×♂ | `python -m unittest discover -s research/pokedata -p 'test_*.py'` → 17 OK. `pytest` → 1181 passed. |

**Projeção sobre o snapshot, não é regeneração.** Correspondência: 19.433 → cerca de **19.623** linhas, porque 171 descartes legítimos se mantêm e cerca de 190 são restaurados. Exclusivas JP: 954 → no máximo **319**; as outras 635 passam a `inconclusivo`. A ordem dos parceiros pode mudar quando o pipeline rodar de novo. `audit_inputs.py` agora conta 25 scripts, porque inclui o `identity.py`.

Pendente: recuperar os intermediários e regenerar; levar a mesma regra de ♀/♂ para `common.key` do pipeline, que muda chaves de todo o cache e por isso fica junto da regeneração; C4 (arte × impressão); os 21 ambíguos; os 375 pares; colocar no CI.


## Revisão GPT — ausência não comprova exclusividade (2026-10-05)

Revisão do commit Claude `69b4a85a1282e72ebc041991438562a964b3c7f4`, em resposta à issue #56.

- **Motivo/evidência:** `reclassify_jp_exclusive` ainda preservava `exclusiva` quando `checked=True` e a lista internacional era vazia. Uma consulta sem resultado não comprova inexistência de impressão internacional.
- **Antes → depois:** esse caso passa a `inconclusivo: sem impressão internacional encontrada nas fontes consultadas`. Consulta sem desfecho e impressão internacional encontrada mantêm motivos distintos. O rótulo `herdado=exclusiva` é preservado em todos os três casos.
- **Rastreabilidade:** `build_xlsx.py` passa a exportar a coluna final `Situação geral herdada` em Inconclusivos (também em `tables.pkl`). Antes, o campo ficava apenas no dicionário em memória e não aparecia na entrega.
- **Arquivos:** `pipeline/identity.py`, `pipeline/build_xlsx.py`, `test_identity.py`, `.github/workflows/tests.yml` e este documento. Sem mudança na ponte ou na deduplicação do Claude.
- **CI:** novo passo explícito de unittest coleta os testes offline de pesquisa, mantendo a coleta principal de pytest. Os testes de pesquisa não precisam ler planilhas nem fazer consultas externas.
- **Validação:** 17 testes de pesquisa e 1.181 testes principais passaram localmente (4 avisos de depreciação existentes em `datetime.utcnow`); sintaxe e diff verificados. A execução integral da exportação continua pendente dos intermediários.
- **Efeito esperado, não regenerado:** esta regra não sustenta nenhuma das 954 exclusividades JP herdadas; todas passam a inconclusivas quando o exportador for executado com esses status. Isso não significa que nenhuma carta seja exclusiva. A projeção anterior de até 319 exclusivas é substituída por essa interpretação. A projeção de aproximadamente 19.623 correspondências não foi recalculada nesta rodada.
- **Pendências:** os 21 rótulos EN herdados também exigem revisão da evidência de exclusividade; a regra alterada aqui é especificamente JP. Permanecem arte × impressão, 21 referências ambíguas, conciliação dos 375 pares, intermediários e regeneração. Nenhum snapshot ou parâmetro do scanner foi alterado, e nenhum merge foi realizado.

## Rodada 3 — Claude: consolidação do stack e pendências (2026-10-06)

Pedido do operador: fazer o merge, se válido, e resolver as pendências. Pedido do GPT
(PR #53): partir de [`POKEDATA_FIXES_20261005.md`](POKEDATA_FIXES_20261005.md), resolver
ambiguidades e normalizações, incluir os testes no CI e preparar o reprocessamento.

### Estado do stack de PRs

| PR | Decisão | Motivo |
|---|---|---|
| #57 (GPT → branch do #54) | **mesclado** em `840e482` | CI e regra "ausência não é exclusividade" válidos; CI verde |
| #53 (linha revisada do GPT, `0fb962b`) | **trazida** para a branch do #54 em `1590303` | pipeline revisado prevalece; conflitos resolvidos a favor dele |
| #55 (outra sessão Claude) | **não mesclado; conciliação portada** (`reconcile_partial.py`) | C1/C2/C4 dele mexiam no pipeline antigo, superado pelo revisado; a conciliação ainda servia e foi reproduzida com números idênticos |
| #58 (GPT) | **não mesclado** | 28 dos 32 arquivos são idênticos aos importados em `pipeline/` no `b7fabc8`; os outros 4 são `.gitignore`, `README.md`, `run_pipeline.sh` (correção do PID já aplicada) e o manifesto (o hash do pacote já está em `POKEDATA_REVISION_20261005.md`). Mesclar criaria uma segunda cópia do pipeline |
| #54 → branch do #53 | mesclar depois do CI verde | ver a resposta na issue #56 |
| #53 → `main` | **não mesclado: inválido por ora** | (1) o pacote recebido afirma que os termos da fonte proíbem publicar derivados (`pipeline/.gitignore`), e a decisão é do operador; (2) dados não reprocessados com o código corrigido |

`pipeline/identity.py` e `test_identity.py` (rodadas 1 e 2 do Claude, ajustados no #57)
foram **removidos**: o `build_xlsx.py` revisado não os importa. A chave completa do `rank`
e o `identity_policy.overall_status` cobrem as mesmas regras de forma mais conservadora: o
cadastro duplo `036`/`36` também fica separado e não há `exclusiva` automática. Os casos
reais daqueles testes (`H3`×`3`, `50a`×`50b`, `GG01`×`001`, Holiday Calendar) voltaram em
`test_reference_match.py`, contra o `rank` real.

### Alterações (motivo · antes → depois · validação)

| Arquivo | Antes → depois | Motivo e validação |
|---|---|---|
| `pipeline/reference_match.py` (novo) | regras espalhadas e divergentes → `number_norm`, `set_norm`, `local_code`, `same_print`, `resolve_reference` | Fonte única para `build_xlsx.py`, `compare_pr53.py` e a ponte. 12 testes |
| `pipeline/build_xlsx.py` → `locate` (aba Cobertura PR53) | `by_rec` em dict sobrescrevia homônimos; com vários candidatos, valia o 1º; nome contido ("mew" em "mewtwoex") ou o único candidato de nome diferente localizavam e herdavam a situação de outra carta → mais de um candidato vira `ambíguo: …`; nome contido ou diferente vira `não localizado: …`; o cadastro duplo é desempatado pela grafia literal do número | Pendência 2 do FIXES. Leia-me ganhou a linha "Ambíguas", e "Não localizadas" passou a contar `não localizado*` |
| `pipeline/compare_pr53.py` | `numnorm` só tirava zeros de números puros, e `parse_local` apagava letras (`H05`→`5`, ao passo que `TG05` do catálogo ficava `TG05`); `151C1..151C4` eram fundidos em `151C` como "igual"; sem nome igual, comparava contra **todos** os candidatos → normalização única dos dois lados; subproduto vira categoria própria ("subproduto não distinguido pelo catálogo"); referência ambígua não é comparada | Pendência 2. Validação em dado real via `reconcile_partial.py` (abaixo) |
| `pipeline/common.py` → `key` | ♀/♂ sumiam no corte ASCII (`Nidoran♀` = `Nidoran♂`) → viram `f`/`m`, a convenção que `catalog.py` já usava; `Nidoran F` = `Nidoran♀` | Ressalva do GPT na #56, agora no pipeline e não só na ponte. Afeta as chaves das unidades, que serão recalculadas no reprocessamento |
| `bridge_partial_ids.py` | regras próprias; 21 referências `ambiguo` → usa `common.key` + `resolve_reference`; os 21 casos são cadastros duplos do catálogo (`4` e `004`, IDs ~40k e ~82k), desempatados pela grafia literal → **3.469 `unico` + 21 `unico_numero_literal`**, 0 sem match, nenhum ID de destino repetido; a coluna `cadastro_duplo` lista os dois IDs | Pendência "resolver as 21 ambíguas". 7 testes |
| `reconcile_partial.py` (novo, portado do #55) | conciliação só no #55, com normalização própria → usa a ponte e `reference_match` | 388 registros / 375 pares: **JP 152 iguais e 8 sem equivalente; CHS 76 iguais, 5 subprodutos, 2 divergentes (IDs EN 417 e 423) e 29 sem equivalente; CHT 116 preservados**. Números idênticos aos do #55, por implementação independente |
| `pipeline/preflight.py` (novo) + etapa 0 de `run_pipeline.sh` | nenhuma checagem antes de 4 h de coleta → recusa Python < 3.10, pacotes ou `curl` ausentes, < 8 GB livres, pasta de trabalho versionável e coleta anterior incompleta; avisa sobre intermediários sem manifesto | Preparar o reprocessamento sem publicar derivados. 6 testes, incluindo "pré-checagem falha → nenhum download" |
| `docs/POKEDATA_REPROCESSAMENTO.md` (novo) | — → roteiro: decisões do operador, comandos, conferências de aceite e o que volta ao repo | Item 1 do FIXES. **Preparado, não executado** |
| `.github/workflows/tests.yml` + `research/pokedata/requirements-test.txt` | o passo do #57 rodaria os testes do GPT sem `numpy` (o scanner só instala PyYAML e pytest) e quebraria → instala `numpy` antes | Reproduzido num venv limpo: sem `numpy`, 1 erro; com o arquivo, OK |

### Validação (local e num venv equivalente ao CI)

```
python -m unittest discover -s research/pokedata -p 'test_*.py'   # 45 OK (20 GPT + 7 ponte + 12 referências + 6 pré-checagem)
python -m pytest -q                                               # 1181 passed
python research/pokedata/bridge_partial_ids.py                    # 3469 unico + 21 unico_numero_literal
python research/pokedata/reconcile_partial.py                     # 388 / 375; números acima
python research/pokedata/audit_inputs.py                          # hashes e contagens dos anexos OK
bash -n research/pokedata/pipeline/run_pipeline.sh                # OK
```

Implementado e testado com fixtures e com os snapshots de 04/10. **Não validado em
execução real:** nada foi coletado nem regenerado, e `build_xlsx.py`/`compare_pr53.py`
dependem de `*.pkl` ausentes. A pré-checagem foi rodada neste container e bloqueou
corretamente: faltam `cv2` e `PIL`, e a raiz do repositório é versionável.

### Pendências (dono)

1. Termos de uso da fonte e visibilidade dos derivados já publicados na branch: **operador**.
2. Reprocessar pelo roteiro em ambiente privado, ou recuperar os intermediários originais: **operador** (máquina), seguido de conferência pelo GPT/Claude.
3. Revalidação visual: 2 divergências CHS, 5 subprodutos, arte provável e impressão de todas as linhas: depende do item 2.
4. Fechar #55 e #58 como superados: **operador** (não fechei PRs que não abri).

## Rodada 4 — Claude: reprocessamento executado na máquina privada (2026-10-06)

Primeira execução real do pipeline revisado (branch `claude/pokedata-reprocessamento`, a partir
de `24e83c1`). Máquina do operador: Windows 11, Python 3.12, 12 núcleos, 16 GB, Git Bash com
`PYTHONUTF8=1` e um shim `python3` para o venv do pipeline. Pasta de trabalho
`research/pokedata/pipeline/trabalho/` (ignorada pelo Git). Nada do que foi gerado entra no
repositório: só código, testes e estes agregados.

### Execução

| Etapa | Resultado | Tempo |
|---|---|---|
| 0 pré-checagem | 7 OK | s |
| 1 coleta PokeData | **1ª tentativa parou: 60 de 694 sets com HTTP 429** na passada paralela; corrigido (`8c200f2`: 429 espera 30/60/120/240 s e os sets que falham são refeitos um a um) e recoletado: **694 sets, 83.653 registros, coleta completa** | 11 min + 8 min |
| 2 fontes externas | pokemon-tcg-data, TCGdex (ja 12.781 cartas, zh-cn 877, zh-tw 7.436), PokeAPI | min |
| 3 catálogo | EN 23.736 cartas únicas no `catalog.pkl` | 1 min |
| 4 imagens | **61.655 baixadas, 52 falhas (0,08 %)**; segunda passada só nas 52: nenhuma recuperada (1 em 5 sondadas é 404, as outras esgotam o tempo no CDN). Viram "carta sem imagem" | 20 min |
| 5 descritores | 9.106.106 + 8.893.573 pontos SIFT (duas partes) | 25 min |
| 7 candidatas | EN×JP 555.180 pares, EN×CN 430.496, CN×JP 238.200 | 21 min |
| 8 segunda comparação | selecionados 44.020 / 15.688 / 24.760 | 25 min |
| 9 Limitless | 2.404 cartas EN (2011+) sem japonês confirmado; 2.189 consultas; 7.279 pares comparados | 6 min |
| 10–12 | classificação, `lim_jp`, planilha `catalogo.xlsx` (17 MB, 13 abas), `comparacao_pr53.csv` | 3 min |

Total: cerca de 2 h 40 min, contra as 4 h previstas no roteiro para 2 núcleos. Memória foi o
único incidente: a RAM disponível caiu a 0,8 GB por programas do operador (Chrome, ASUS); com
autorização, Chrome e apps WebView foram fechados. O pipeline em si usa ~2 GB na etapa 5 e ~3,7 GB
nas etapas 7–8.

### Conferências de aceite (`research/pokedata/accept_run.py`, novo; sem contagens fixas)

Todas as seis passaram (`rc=0`):

| Conferência | Resultado |
|---|---|
| Coleta | `complete: true`, 694 sets, 0 falhos, 83.653 cartas |
| `exclusiva` automática | **0** em todos os catálogos; aba Exclusivas vazia |
| Cobertura PR53 | **3.490 referências = base parcial**, IDs únicos, mesma tupla (ID, nome, número, set); localização: **3.469 registro exato + 21 registro exato (número literal); 0 ambíguas, 0 não localizadas** |
| CHT PR53 | 116 registros preservados campo a campo |
| `comparacao_pr53.csv` | 388 registros = 375 pares ID–idioma da base parcial |
| Correspondência | 18.723 linhas; JP 18.170 + CHS 7.270 − ambos 6.717 = 18.723 ✔; 18.723 cartas (uma por linha) |

Situação geral das cartas únicas nesta rodada (compare com a entrega de 04/10 no README do pipeline):

| Idioma | Arte confirmada | Provável | Inconclusivo | Não encontrada | Exclusiva |
|---|---|---|---|---|---|
| EN | 18.723 (04/10: 18.673) | 1.068 (1.121) | 2.769 (2.747) | 485 (485) | **0** (21) |
| JP | 24.290 (24.158) | 1.370 (1.502) | 3.578 (3.574) | 950 (635) | **0** (319) |
| CN | 9.606 (9.606) | 340 (340) | 963 (963) | 97 (97) | 0 (0) |

Leitura: as exclusivas antigas (21 EN + 319 JP) viraram "não encontrada" ou "inconclusivo", como
decidido (ausência não prova exclusividade); o resto varia pouco, pela coleta nova (83.653
registros contra 77.864 da coleta parcial) e pela chave completa do `rank`. A Correspondência
tem 18.723 linhas contra 18.345 em 05/10: a chave completa deixou de fundir impressões distintas.

### Comparação com a base parcial (375 pares) e com a conciliação de 04/10

| Idioma | Esta rodada | Conciliação de 04/10 (`reconcile_partial.py`) |
|---|---|---|
| JP | **143 igual** (arte confirmada aqui), 9 provável com a mesma candidata, 1 inconclusiva com a mesma candidata, 7 set fora do catálogo | 152 iguais, 8 sem equivalente |
| CHS | **69 igual**, 5 subprodutos (`151C1..4` × `151C`), 7 provável com a mesma candidata, 1 inconclusiva com a mesma candidata, 12 carta sem imagem no PokeData, 18 set fora do catálogo | 76 iguais, 5 subprodutos, 2 divergentes, 29 sem equivalente |
| CHT | 116 só no PR #53 | 116 preservados |

As **2 divergências CHS de 04/10 (IDs EN 417 e 423)** não divergem mais: ficaram "provável com a
mesma candidata" (`CSM2DC 195/342` e `CSMPbC 001/025`), e a segunda impressão CHS de cada uma
(`CSM2cC 071/150`, `CSM2.5C 006/061`) está "sem imagem no PokeData". Os 9 JP + 7 CHS que caíram
de "igual" para "provável" são a mesma carta com menos de 40 pontos na arte (Tag Team e full art
com foil pesado) ou nome divergente na fonte.

### Revalidação visual (roteiro, §5) — conferida em resolução plena pelo Claude (06/10), a pedido do operador

`research/pokedata/pipeline/sample_pr53.py` (novo) gera, na pasta de trabalho e fora do Git:

- `revalidacao_pr53.jpg`: os **18 pares do PR #53** que ficaram "provável/inconclusiva" aqui, lado
  a lado com a candidata desta rodada. Leitura do Claude em resolução reduzida: **18/18 têm a
  mesma ilustração** (Psyduck M2a, Victini SV-P ×2, Pikachu/Charmander shiny SV4a, Charmeleon
  SV2a, Raichu/Tyranitar SV2D, Marill SV2P, Boss's Orders CS1aC, e 9 Tag Team GX CHS/JP). Nenhuma
  contradiz o "Confirmada" do PR #53 quanto à arte. **Impressão** (edição, acabamento, carimbo)
  não foi conferida: Victini `SV-P 288` aparece como par de duas referências EN diferentes
  (IDs 84 e 99), caso típico de mesma arte em impressões distintas.
- `revalidacao_provaveis.jpg`: 48 pares sorteados (semente 20261006) dos 4.255 "provável" de todas
  as combinações. Leitura reduzida: nenhum par visivelmente errado.
- **Conferência em resolução plena (06/10, recortes de 6 pares por página):** **18/18** pares do
  PR #53 e **48/48** prováveis sorteados mostram a mesma ilustração; nenhum par errado. Onde a
  impressão difere e isso é visível na imagem, é o caso esperado de "arte confirmada ≠ impressão":
  Victini SV-P 288 (promo JP) × IDs EN 84 e 99 (cartas de set); Energia Lutadora BLW 110 × BW-P 132
  (carimbo Gym Challenge); Basculin de Hisui SWSH273 × S-P 279 (carimbo GYM); Pikachu M23 006
  (promo) × SV4a 055; Mew CSDC 025 × S8a 030 (25º aniversário); Dragonite FO 4 × Mystery of the
  Sea 149 (molduras de eras distintas). Edição e acabamento continuam fora do alcance da imagem.

### O que volta ao repositório nesta rodada

`fetch_cards.py` (429), `test_safety.py` (+3), `accept_run.py` (+ `test_accept_run.py`, 11),
`sample_pr53.py`, este registro, o handoff e `docs/COMUNICACAO_GPT_CLAUDE.md`. Planilha, CSV,
imagens, descritores, `*.pkl` e `ext/` ficam na máquina do operador.

### Pendências (dono)

1. Conferir as duas folhas de contato em resolução plena e, para as linhas que usar, a impressão: **operador**.
2. Termos de uso da fonte e visibilidade dos derivados já na branch (`inputs/`): **operador** (insumo do GPT, T6 em `docs/COMUNICACAO_GPT_CLAUDE.md`).
3. P56-8 sobre a entrega de 05/10: **GPT**. Nesta rodada, `resolve_reference` localizou as 3.490 referências sem ambiguidade.
4. Revisão do `accept_run.py` (P56-9) e endurecimento do pipeline (encoding, caminhos, células com `=`): **GPT**.

## Revisão GPT — T5 a T8 (2026-10-06)

Base: `87c8fb0` em `docs/pokedata-claude-handoff` (PR #61 mesclado). Trabalho na branch
`gpt/pokedata-t5-t8`, para revisão na branch da frente; sem merge. O #62 permanece uma
entrega documental separada: seus registros de encerramento do Claude não foram substituídos.

### T5 / P56-8 — cobertura demonstrada, cotejo privado pendente

[Resposta na #56](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/issues/56#issuecomment-6010473984).
Não encontrei perda demonstrada de registro aproximado legítimo. A função real conserva o
fallback de nome-base único e retorna a unidade, `registro=None` e “mesma carta, registro
aproximado”. `test_variant_resolves_to_unit_only` exercita esse comportamento; contenção de
nome e múltiplas unidades não bastam. Não há nova evidência para mudar identidade/aliases.

A rodada 4 informa 3.490 referências localizadas, todas exatas ou por número literal:
zero ambíguas/não localizadas. Isso não compara os registros aproximados da entrega de 05/10.
Nesta sessão não estão disponíveis `pokedata_crossref(2).zip`, seu XLSX/CSV privado nem a saída
real de 06/10; só os relatórios e snapshots anteriores já versionados. Não reutilizei os
anexos de 04/10 como se fossem o pacote revisado. **T5 segue pendente do cotejo privado**,
com a resposta parcial e o limite explicitados.

### T6 — termos oficiais e decisão operacional

Entregue [POKEDATA_TERMOS.md](POKEDATA_TERMOS.md), com fontes, versão confirmada de 12/12/2025
e opções concretas para T9. Corrigida a síntese do README/estado: a exceção pessoal e não
comercial exige permissão explícita para aquele conteúdo e atribuição; os termos da API
incorporados por referência também restringem redistribuição de dados do site/aplicativo.
O #53 continua bloqueado para `main` enquanto o operador decide autorização, destino dos
anexos e eventual entrega de código separado. Nenhum anexo/histórico foi alterado.

### T7 — portabilidade e endurecimento

- Adicionados **49 argumentos de encoding** ao I/O de texto em 23 scripts do pipeline,
  incluindo `Path.read_text()`. Mantidos os formatos binários e o CSV UTF-8 com BOM.
  `fetch_cards.py` ficou fora por instrução expressa; nele, Windows ainda exige
  `PYTHONUTF8=1`, como na rodada 4. As funções/regras de identidade não foram modificadas.
- `fetch_external.py` valida os IDs dos dois provedores antes de interpolar URL/caminho:
  rejeita travessia, separadores, caminhos absolutos, escapes percentuais, nomes reservados
  do Windows e IDs malformados. IDs válidos conservam grafia e recebem escape na URL.
  O lote é validado antes de iniciar downloads de seus detalhes.
- `build_xlsx.py` grava dados iniciados por `=`, `+`, `-`, `@` como string com o escape
  nativo `quotePrefix`. Inclui eras recebidas no Leia-me. Nenhum apóstrofo é acrescentado
  ao valor, preservando o cotejo de referências/CHT; fórmulas internas continuam ativas.
- Regressões sem rede/pickle: leitura Unicode sob default cp1252, declaração de encoding,
  IDs válidos/inválidos e XLSX salvo/reaberto com inspeção XML (só a fórmula interna
  deliberada vira `<f>`). `openpyxl` entrou nas dependências dos testes de pesquisa para o CI.

### T8 / P56-9 — aceite adequado com limites explícitos

[Resposta na #56](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/issues/56#issuecomment-6010487464).
`audit_revision.py` continua histórico da entrega de 05/10; novas execuções usam
`accept_run.py`, sem necessidade de mais um modo no auditor antigo.

| Item de §3 do roteiro | Revisão / verificação |
|---|---|
| Coleta completa | Exige `complete=true` e nenhum set explicitamente falho. Não vincula criptograficamente o manifesto ao catálogo/planilha. |
| Ausência de `exclusiva` automática | Corrigida a lacuna: examina todos os registros, inclusive variantes não principais, além da aba Exclusivas. |
| Referências preservadas | Compara multiconjunto ID/nome/número/set com a base fornecida e exige IDs únicos; sem 3.490 hardcoded. |
| Ambíguas/não localizadas no Leia-me | Nova conferência: valor correto ou fórmula COUNTIF correta para a coluna de localização. Reporta IDs que exigem análise humana; `rc=0` não decide esses casos. |
| CHT preservado | Compara ID e dez campos com os registros CHT da base, incluindo identidade, acabamento, status, método e fonte; sem 116 hardcoded. |
| Comparação PR53 | Preserva as chaves e multiplicidade dos registros; resume categorias. Cotejo de resultados com 04/10 continua humano, registrado na rodada 4. |
| Correspondência | Exige lado confirmado em toda linha e verifica JP + CHS − ambos. Causas da mudança de 18.345 para 18.723 linhas (+378) continuam a explicação reportada pelo Claude, não prova produzida pelo script. |

O aceite agora tem **sete checks**. A evidência real 6/6 da rodada 4 permanece histórica;
esta sessão não aplicou o aceite expandido aos derivados privados. O roteiro inclui o
comando para o operador executá-lo sem nova coleta. Fórmulas são verificadas estruturalmente,
sem recálculo nem certificação de caches antigos. Arte, impressão e termos não são
certificados pelo aceite.

### Validação e limites desta sessão

- Dependências instaladas em venv do workspace: requisitos do scanner, testes de pesquisa e `openpyxl`.
- `python -m unittest discover -s research/pokedata -p 'test_*.py'`: **71 OK** (61 anteriores + 10 regressões).
- `python -m pytest -q`: **1181 passed** (quatro avisos preexistentes de `datetime.utcnow`).
- Fixture de integração chama o aceite real em XLSX/CSV sintéticos temporários: sete checks
  passam; remover o total de ambíguas no Leia-me gera `rc=1`.
- Persistem ResourceWarnings de arquivos sem fechamento explícito no pipeline legado;
  o endurecimento desta rodada não refatora o gerenciamento de todos os arquivos.
- Sem coleta, leitura de pickle privado, regeneração de dados reais ou nova revalidação
  visual. Nenhum preço, XLSX, CSV, imagem ou cache novo foi versionado.

Próxima vez: Claude revisa o PR de T6–T8; operador disponibiliza o insumo privado para T5,
decide T9, confere as folhas e resolve T10. Sem acompanhamento automático.

## GPT — identificação dos insumos reenviados para T5 (2026-10-06)

Base `origin/main`, `292434b` (#65 mesclado). O operador reenviou seis anexos nesta conversa;
foi conferida sua identidade/estrutura, sem publicar os arquivos ou dados detalhados.
[Resposta na #56](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/issues/56#issuecomment-6012417814).

| Insumo recebido | Resultado verificado |
|---|---|
| Quatro ZIPs: `pokedata_crossref.zip`, `(1)`, `(2)` e `(3)` | Todos idênticos byte a byte, 12.556.626 bytes, SHA-256 `fe6a3589be1ef04416024abbc73efc3bd0585ef452c5d03cf0ab27046373df1b`; iguais ao ZIP antigo de `inputs/`. |
| Catálogo dentro dos ZIPs | Mesmo XLSX nos quatro, SHA-256 `77441e4584aff000c0ca3c83170df99b4bb128efdb6fc50fa81ebdfadab18fdb`; dez abas, sem `Cobertura PR53` nem `CHT PR53`. Os ZIPs não contêm CSV de comparação nem pickle. |
| Planilha parcial reenviada | Igual ao original histórico `research/pokedata/PokeData_correspondencias_JP_CHS_CHT_parcial.xlsx`, SHA-256 `c3bf41a5b20f09d4546ed0bcc309783ba078b84b99513645fc300bb753f8d513`. Suas seis abas não incluem `Cobertura PR53`. Não é a entrega revisada. |
| Outra planilha | Base EN com quatro abas, sem `Cobertura PR53`; não identifica os casos aproximados do catálogo revisado. |

A entrega privada de 05/10 documentada em `POKEDATA_REVISION_20261005.md` tem SHA-256
`84986e8a42615be92d0b522034445ded2224b6b87dd469de0122850b4f6ad724`, contém a planilha revisada
e `docs/comparacao_pr53.csv`. **Nenhum dos quatro ZIPs recebidos agora corresponde a ela.**
O número entre parênteses no nome é insuficiente para identificar a versão.

**T5 segue bloqueada para o cotejo histórico**, agora por versão incorreta do insumo recebido.
Não é possível enumerar os registros marcados como aproximados em 05/10 nas abas enviadas,
pois a aba pertinente está ausente. A informação agregada da rodada 4 (3.490 localizadas,
zero ambíguas/não localizadas) e o fallback testado do resolver não substituem essa enumeração.

Próximo insumo: ZIP da versão revisada ou seu XLSX com `Cobertura PR53` e `CHT PR53`;
para comparação direta linha a linha com a execução nova, também `catalogo.xlsx` da rodada 4.
Com as duas versões: conferir as chaves ID/nome/número/set, selecionar as referências antigas
com localização aproximada e cotejar sua localização atual. Reportar somente contagens,
conclusões e limites, sem expor os dados privados.

Validação desta identificação: SHA-256 dos quatro ZIPs e da planilha parcial comparados aos
arquivos versionados; inventário dos ZIPs e nomes das abas do XLSX conferidos por leitura
de metadados e `openpyxl`. Sem executar scripts recebidos, abrir pickle, coletar, alterar
identidade ou inspecionar/imprimir preços. Nenhum anexo novo foi versionado. Só documentação
mudou; as suítes de código não foram repetidas nesta rodada.
