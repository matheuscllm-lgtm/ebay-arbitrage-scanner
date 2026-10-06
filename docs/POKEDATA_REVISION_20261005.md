# Catálogo de cartas — revisão da versão recebida em 05/10/2026

## Decisão
Atualização de código e documentação no PR #53, sem merge e sem integração no scanner.
A nova planilha e o CSV foram lidos localmente, não publicados nesta atualização.
O estado abaixo prevalece sobre o relatório histórico de 04/10 e sobre alegações de que todos os problemas foram resolvidos.
Base inspecionada: b2ac22c155fc7e188e37ebd3fa2efc9a501cd0ef.

## Proveniência e destino
- Pacote público: pokedata_crossref_publico.zip, SHA-256 89b4f467cf0917c2a7089ee24bf6830b3466d7d24eb265fb2a4ece2f2bf381fb.
- Pacote completo: pokedata_crossref(2).zip, SHA-256 84986e8a42615be92d0b522034445ded2224b6b87dd469de0122850b4f6ad724.
- Os arquivos comuns dos dois pacotes são byte a byte iguais. O completo acrescenta somente o XLSX e docs/comparacao_pr53.csv (além do diretório output).
- Código importado para research/pokedata/pipeline/, já existente, não para uma segunda pasta na raiz.
- Nenhum novo XLSX, CSV de correspondências, ZIP, imagem ou cache foi incluído no Git nesta rodada.
- Os snapshots antigos já publicados em research/pokedata/inputs/ continuam presentes e não são a entrega revisada. Não foram removidos nem houve reescrita do histórico. Decisão sobre retirada/visibilidade depende do operador.

## Auditoria offline executada
audit_revision.py recebeu a planilha revisada, o original do PR53 e o CSV privado:
- 3.490 IDs EN únicos; ID, nome, número e set preservados em relação ao original.
- Status herdados: 2.516 arte confirmada, 323 provável, 479 inconclusivo, 172 não encontrada.
- Dos 2.516, somente 1.640 usam a imagem do registro de referência; 876 são variantes não conferidas.
- 388 registros da comparação correspondem às mesmas chaves ID/idioma/código local do original: 375 pares únicos ID–idioma.
- 116 registros CHT preservam os 11 campos conferidos: referência, identidade local, acabamento, status, método e fonte. Não houve nova validação visual.
- 18.345 linhas na Correspondência representam 18.673 unidades agrupadas. JP 17.707, CHS 7.189, ambos 6.551; inclusão-exclusão confere.
- 13.270 linhas declaram variantes/marcação pendente. As outras 5.075 não são prova de versão física conferida.
- CSV recebido: 210 registros JP/CHS rotulados como mesma arte, 23 prováveis com a mesma candidata, 39 outros casos, além dos 116 CHT. Foram recontados os rótulos, não reexecutado o matching.

A soma fecha; isso não comprova que toda deduplicação é legítima. Imagens, descritores e intermediários não foram fornecidos. As amostras visuais do Claude são reportadas, não reproduzidas nesta sessão.

## Alterações e justificativas para Claude
| Arquivos | Antes → depois | Motivo / verificação |
|---|---|---|
| pipeline/assemble.py e build_xlsx.py | versão antiga → versão revisada recebida | Separa arte de versão, rebaixa faixas fracas e exporta cobertura PR53/CHT; sintaxe conferida, testes de fronteira do status executados. |
| pipeline/lim_jp.py, compare_pr53.py, documentação | ausente/desatualizado → pacote público mais recente | Continuidade e comparação auditável; nenhum cache externo carregado. Persistem os limites metodológicos abaixo. |
| pipeline/run_pipeline.sh | versão recebida tinha wait sem PIDs → mantida correção existente de ambos os PIDs | A importação não pode reintroduzir falha já corrigida. Testada falha de cada shard e sucesso. Preservadas segunda assemble.py após lim_jp.py e passagem opcional da planilha PR53. |
| test_pipeline.py, test_revision.py | 2 testes → 9 testes no total | 7 aprovados e 2 falhas esperadas que reproduzem defeitos abertos, não uma aprovação integral. |
| audit_revision.py | ausente → auditoria read-only | Confere chaves, contagens, comparação e CHT sem imprimir preços, recalcular ou editar planilhas. |
| pipeline/.gitignore e documentos de entrada | proteção parcial → bloqueio local adicional de XLSX/CSV/ZIP | Evitar novos derivados no repositório público. Não remove arquivos já rastreados. |
| CLAUDE.md | orientação histórica → ponte para esta revisão e ESTADO_DO_PROJETO.md | Evitar interpretar pacote recebido como versão validada operacionalmente. |

## Bloqueadores ainda presentes
1. **Exclusividade por ausência.** lim_jp.py inicializa intl=[] e pode preservá-lo mesmo quando a seção HTML não foi localizada. assemble.py trata lista vazia como evidência de exclusividade. Página existente sem links não é comprovação positiva de inexistência. As 319 JP e 21 EN continuam rótulos herdados; não excluir automaticamente. Separar seção ausente, erro de parser e ausência reportada pela fonte.
2. **Ligação via JP ignora GRAY.** assemble.py diz que uma comparação direta fraca prevalece, mas o loop VIA só exclui CONF e PROV. Um par em GRAY pode virar arte confirmada por transitividade. Também falta verificar pares diretamente testados/rejeitados fora desses mapas. Reproduzido com o loop real em teste esperado-falhar.
3. **Deduplicação por denominador.** build_xlsx.rank continua extraindo os dígitos finais: 121/106 e 122/106 colidem. Teste com a função real retorna um candidato em vez de dois. Corrigir identidade preservando número completo/prefixos antes de regenerar; não inferimos quantas linhas do snapshot foram afetadas.
4. **Coleta parcial.** fetch_cards.py agrega arquivos disponíveis após falhas sem obrigar saída de erro. Cache existente não valida schema nem proveniência. Nenhum novo download foi executado.
5. **Busca Limitless usa critério anterior à reclassificação.** limitless_todo.py retira os pares aceitos em rules.classify antes dos rebaixamentos de assemble.py; cartas depois rebaixadas podem não entrar na consulta complementar. Consolidar o critério ou registrar claramente a cobertura.
6. **Imagem-marcador é heurística.** detect_placeholders.py agrupa os primeiros 64 componentes arredondados do descritor em quatro nomes distintos; isso não é hash da imagem completa. O teste sintético confirma comportamento, não precisão sobre todo o catálogo.
7. **Ponte por nome/número requer auditoria de ambiguidade.** compare_pr53.py pode usar todos os candidatos de mesmo set/número se não casar nome, e normaliza prefixos/subprodutos. Cobertura total não comprova identidade de impressão. Não transformar esses vínculos em Confirmada sem validar versão.

## Publicação e termos
O pacote relata restrições dos termos do provedor. Nesta sessão a página oficial de termos não foi acessível pela ferramenta de consulta; essa leitura não foi verificada independentemente. Como medida conservadora, importamos somente a versão pública de scripts/documentação e não repetimos coletas. Isso não é parecer jurídico nem autorização geral de redistribuição.
Há derivados antigos na branch pública. Não alterar visibilidade nem apagar histórico automaticamente. Levar a decisão ao operador.

## Testes e limites
- 25 scripts Python do pacote passaram em análise sintática.
- Shell passou em bash -n.
- test_pipeline.py: 3 testes aprovados (inclui os dois shards e ordem de reclassificação).
- test_revision.py: 4 testes aprovados (39/40 pontos, divergência de espécie e imagem-marcador sintética); 2 falhas esperadas (VIA/GRAY e denominador).
- audit_revision.py: passou com os arquivos privados desta rodada.
- Não rodamos o pipeline de quatro horas, downloads, suíte completa do scanner, recálculo do Excel nem nova validação visual. Nenhum resultado de mercado foi atualizado.
- Testes esperados-falhar deixam os defeitos visíveis, mas não bloqueiam automaticamente CI; não interpretar saída OK como liberação para produção.

## Próxima etapa
Corrigir os bloqueadores com regressões, regenerar em ambiente autorizado e validar arte/versão em amostra rastreável. Preservar o histórico dos status e todo CHT. Só depois propor integração ao scanner, separadamente.

