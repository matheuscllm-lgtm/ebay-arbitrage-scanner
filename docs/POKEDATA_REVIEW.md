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
- **Somente 1.785 dos 3.490 IDs EN da base parcial aparecem por igualdade exata no catálogo completo; 1.705 não aparecem.** Não fazer inner join que descarte essas referências. Falta construir e validar a ponte entre os snapshots.
- Nenhum erro Excel armazenado foi encontrado no catálogo completo. Isso não é recálculo de fórmulas nem validação visual dos pares.

19.794 unidades EN confirmadas e 19.433 linhas exportadas medem universos diferentes: `build_xlsx.py` aplica nova deduplicação na exportação. Não apresentar a diferença de 361 como perda comprovada ou como duplicatas legítimas sem auditar as chaves.

O anexo parcial desta rodada tem SHA-256 `85907fedc09cfcc57a66cda579630b78e1adc0df9aed59df124c79328eeafeaa`; o original do PR #53 tem `c3bf41a5b20f09d4546ed0bcc309783ba078b84b99513645fc300bb753f8d513`. Não confundir igualdade de contagens com identidade de arquivos.

## Achados e alterações propostas

### P1 — exclusividade inferida a partir de ausência

`pipeline/assemble.py`, bloco `overall bucket`, classifica JP como `exclusiva` quando os dois destinos são `não encontrado`. `lim_jp.py` consulta parte dessas cartas depois, mas `build_xlsx.py` não reclassifica o status com base no resultado: apenas acrescenta uma frase ao critério.

Evidência no snapshot: das 954 exclusivas JP, **635** dizem apenas “Arte sem equivalente em inglês nem em chinês simplificado no PokeData”; 319 acrescentam ausência no Limitless. As 21 EN usam ausência no Limitless mais ausência de CHS. Ausência em duas bases não comprova exclusividade mundial, especialmente sem CHT.

Proposta: nova classificação `inconclusiva` até haver evidência positiva, fonte e data; manter histórico do rótulo original. Exigir cobertura explícita dos idiomas-alvo. Não excluir automaticamente essas cartas. Nenhum status original foi sobrescrito nesta revisão.

### P1 — deduplicação pode usar o denominador como identidade

`pipeline/build_xlsx.py`, função `rank`, usa `re.search(r'(\d+)$', b[1])` e deduplica por `(set_id, número final)`. Para `121/106` e `122/106`, a chave numérica é **106** para ambos; para `TG01/TG30` e `TG02/TG30`, é **30**. Isso pode eliminar impressões diferentes da lista de equivalentes dentro de um mesmo set.

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
