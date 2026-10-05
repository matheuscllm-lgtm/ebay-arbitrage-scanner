# Catálogo de cartas — conferência da entrega pública

Recebido em 2026-10-05. Complemento de revisão aos PRs #53, #54 e #57 e à issue #56.

## Origem e escopo

- Pacote público: `pokedata_crossref_publico.zip`, SHA256 `89b4f467cf0917c2a7089ee24bf6830b3466d7d24eb265fb2a4ece2f2bf381fb`.
- Pacote completo recebido para consulta, não adicionado nesta entrega: SHA256 `84986e8a42615be92d0b522034445ded2224b6b87dd469de0122850b4f6ad724`. É idêntico ao ZIP completo anterior.
- Os 31 arquivos do pacote público são idênticos aos membros correspondentes do completo. Incluem 25 scripts Python, shell, requirements, gitignore, README e dois documentos; não incluem planilha, CSV de correspondências, imagens ou intermediários.
- Conteúdo original em `research/pokedata/submissions/2026-10-05-publico/`, com manifesto de tamanho e SHA256 por arquivo. Fontes e atribuições preservadas. Os títulos internos dos documentos são os do material recebido, não uma nova marca do projeto.

## Justificativa ao Claude

Antes: esta nova entrega estava somente no anexo. Depois: cópia textual íntegra disponível para revisão no GitHub, isolada do pipeline revisado. Isso permite comparar a reclassificação recebida sem substituir as correções de #54/#57 nem executar uma segunda reclassificação. Os documentos recebidos registram as conclusões do autor; sua inclusão não as transforma em conclusões validadas pelo GPT.

## Divergências pendentes de conciliação

1. `assemble.py` ainda conserva exclusividade JP quando a lista do Limitless está vazia. A mudança de #57 exige status inconclusivo para ausência nas fontes consultadas. As 340 exclusividades relatadas não estão comprovadas por esse critério.
2. `build_xlsx.py` ainda usa os dígitos finais em `rank` e `numsort(k[1])[0]` no agrupamento da Correspondência, sem o nome na chave. A conferência aritmética por fórmula não comprova identidade da impressão. Preservar a correção de #54 na futura integração.
3. `run_pipeline.sh` contém `wait` sem verificar individualmente os dois processos de extração. Preservar o tratamento de falhas já testado no pipeline do repositório.
4. Separação arte/versão, 4.111 pares prováveis, 2.516 referências com arte confirmada e conferência visual de 48 pares são resultados declarados pelo autor. Não foram reproduzidos nesta revisão; intermediários e imagens não foram fornecidos. Não usar as novas contagens como regeneração do pipeline corrigido.

## Validação e limites

Conferidos: igualdade byte a byte dos arquivos entre os ZIPs, 25 scripts com sintaxe Python válida, shell válido em `bash -n`, inventário e hashes. Não executado: pipeline com coleta, reclassificação, regeneração ou auditoria visual. Esta importação não modifica o scanner ou as regras revisadas. Nenhum teste de comportamento novo foi necessário para a cópia dos arquivos.

Pendente: conciliar as três divergências antes de integrar a entrega; recuperar intermediários; revisar evidência de exclusividade EN/JP, arte versus impressão, ambiguidades e pares anteriores. O pacote público desta rodada não remove os dados que já estavam presentes nas branches anteriores. Sem merge nem acompanhamento automático.
