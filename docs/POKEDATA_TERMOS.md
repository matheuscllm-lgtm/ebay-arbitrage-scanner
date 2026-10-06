# PokeData — leitura operacional dos termos (T6)

Leitura em **06/10/2026**, para decisão do operador sobre o PR #53 → `main`.
Não é parecer jurídico nem autorização de publicação.

## Fontes verificadas

- [Termos do site](https://www.pokedata.io/termsandconditions), que apontam para
  [iubenda 81884871](https://www.iubenda.com/terms-and-conditions/81884871).
  Texto extraído via Tavily; rodapé confirmado: atualização de **12/12/2025**.
  Provedor: pokedata (Browse LLC), contato `info@pokedata.io`.
- [Termos da API](https://www.pokedata.io/api-terms), incorporados por referência
  nos termos gerais e lidos nesta sessão. A página não informa data de versão.

## O que permite e o que restringe

| Tema | Leitura do texto oficial | Consequência para esta frente |
|---|---|---|
| Uso do serviço | Deve respeitar sua finalidade, os termos e direitos de terceiros. | Acesso público ao site não equivale a licença de coleta/publicação. |
| Conteúdo — “Rights regarding content … All rights reserved” | Copiar, baixar, compartilhar, modificar, traduzir, transformar, publicar e criar derivados são restringidos. A exceção pessoal/não comercial exige permissão explicitamente indicada para o conteúdo e atribuições. Exceções legais permanecem ressalvadas. | “Privado + atribuição” sozinho não demonstra permissão. Corrige a síntese incompleta do README. |
| API | A oferta Platinum permite usos pessoais não comerciais, como planilha, alertas e pesquisa pessoal; acesso limitado às APIs documentadas. Há restrições a exploração econômica e competição. | Não certifica os endpoints usados por `fetch_cards.py`; não validamos contrato, assinatura nem autorização da execução. |
| Redistribuição — termos da API | Proíbe redistribuir dados da API, site ou aplicativo. Exceções para criadores de conteúdo devem ser obtidas por escrito. | Publicar os anexos ou um catálogo derivado requer autorização adequada; comprar acesso não basta. |
| Terceiros | Fontes externas têm seus próprios termos/direitos. | Uma permissão do PokeData não libera automaticamente imagens Pokémon ou outras bases. |

Código próprio e documentação de método podem ser separados dos dados da fonte; essa é uma
opção técnica de entrega, não uma licença concedida pelo PokeData aos scripts recebidos.
Agregados do relatório não substituem a decisão sobre os anexos nem autorizam dados detalhados.

## Opções concretas para o operador (T9)

| Opção | Próximo passo concreto | Efeito sobre #53 e anexos |
|---|---|---|
| A. Obter autorização escrita | Pedir ao provedor permissão para os endpoints, finalidade da pesquisa, derivados, dados já publicados e redistribuição pública no GitHub. Incluir terceiros e atribuição no escopo. | Manter #53 em rascunho enquanto aguarda. Só liberar a publicação coberta pela resposta. |
| B. Publicar apenas código/método | Preparar PR separado removendo anexos da árvore pública proposta e adaptando auditorias/testes que dependem dos snapshots para fixtures sintéticas. Manter os originais e hashes em armazenamento privado autorizado. | Permite propor uma entrega de código para revisão. Remover arquivos no próximo commit não retira cópias do histórico da branch nem decide a legitimidade do uso privado. |
| C. Trocar a fonte | Usar entradas próprias/licenciadas ou bases cuja licença cubra coleta, derivados e redistribuição. Validar cada fonte e regenerar em ambiente autorizado. | Os snapshots PokeData não passam a ter nova licença; definir seu destino separadamente. |

**Recomendação operacional:** manter bloqueado o #53 → `main` no estado atual; escolher A,
ou preparar B/C antes de propor merge. A decisão final é do operador. A rodada 4 resolveu o
reprocessamento; não resolveu permissões de uso/publicação.

## Anexos já versionados

O inventário fica em `research/pokedata/inputs/manifest.json` e
`docs/POKEDATA_REVIEW.md`. Há ZIP com catálogo e XLSX em `inputs/`, além das planilhas
históricas em `research/pokedata/` fora dessa pasta. A avaliação de retirada precisa incluir
todas essas cópias, não somente o CSV/XLSX da rodada nova (que continuam privados).

Antes de retirar anexos, preservar os originais byte a byte e o manifesto em local privado.
Depois, preparar a remoção da árvore e adaptar as ferramentas afetadas em PR próprio.
Se o operador optar por retirar também do histórico público, planejar a reescrita de refs,
PRs e clones e a eventual solicitação de limpeza de caches ao GitHub. Isso é uma operação
separada, com autorização explícita; não elimina cópias já baixadas.

Nesta sessão **nenhum anexo foi modificado, apagado ou novamente publicado**, nenhum histórico
foi reescrito e nenhuma mensagem foi enviada ao provedor.
