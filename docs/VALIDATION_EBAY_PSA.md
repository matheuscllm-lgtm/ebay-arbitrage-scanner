# Registro de validação — EBAY PSA

## Estado atual — política 2026-09-05.4

A comparação de coleções com códigos administrativos e a normalização de grafia
foram corrigidas. [Execução real 33949437501](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/actions/runs/33949437501):
**success**, 188 anúncios, 33 chamadas, 83 candidatos com amostra PSA suficiente,
105 REVISAR e 83 REJEITAR; nenhum APROVAR devido aos custos e preços observados.
A validação completa do fluxo foi obtida sem reduzir as exigências. 646 testes
locais passaram. Detalhes em [RUNTIME_REVIEW.md](RUNTIME_REVIEW.md).

Os registros abaixo permanecem como histórico; não representam o resultado mais recente.

## Estado atual — política 2026-09-05.3

As definições pendentes nos registros históricos abaixo foram resolvidas sob
autonomia delegada: dispersão máxima 30%, BGS 9,5 sem acumulação. Configuração
válida e sem pendências. Revisão local: 620 testes passaram, incluindo o limite
de chamadas da API. Ver [AUTONOMOUS_REVIEW.md](AUTONOMOUS_REVIEW.md).

Amostra ampliada em [33948543640](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/actions/runs/33948543640):
115 anúncios, 33 chamadas, 104 REVISAR e 11 REJEITAR. Nove candidatos chegaram ao
cálculo com duas vendas PSA 9 estritas, ainda abaixo das três exigidas. Zero
APROVAR; resultado parcial por evidência insuficiente, sem falha das fontes.

## Histórico da revisão

Data: 2026-09-05. Base auditada: `2ed6cc7`.

## Testes locais

- Base intacta: **491 passaram, 3 falharam** pela ausência de
  `src/catalog/set_catalog.json`.
- Incluída a correção de catálogo já proposta no PR #28, commit `07f11a8`,
  com CSV, origem documentada, exceções de gitignore e regressão correspondente.
- Implementação EBAY PSA: **541 testes passaram** com Python 3.12,
  `python -m pytest -q` (1,76 s na última execução completa).
- São **46 casos novos** de estratégia e integração, além do teste de catálogo.
- A regressão de ausência de credenciais agora espera código 1, mantendo a
  exigência de preservar o último artefato de busca real.
- `python -m compileall -q src main.py ebay_summary.py`: passou.

Os novos testes cobrem reserva de US$10 sem frete duplicado, taxas sequenciais,
lucro/margem/ROI, perdas apesar de desconto, TAG sem preço de revenda próprio,
BGS 9,5 sem dupla aplicação, limite BGS em US$105/105,01 sobre PSA US$100,
CGC indefinido, PSA 9,5 inválido, idiomas separados, número/coleção/variante,
datas futuras, títulos de oferta aceita, deduplicação, baixa liquidez, dispersão,
Black Label, decisões no JSON/Markdown/CSV e uso obrigatório da política pelo
entrypoint de produção. Dados sintéticos não representam oportunidades reais.

## Tentativa de busca real

Comando:

```bash
python main.py --group 3 --max-pages 1 --out results/validation-2026-09-05.json
```

Resultado: grupo de 49 cartas identificado; `EBAY_CLIENT_ID` e
`EBAY_CLIENT_SECRET` ausentes. Código de saída 1, **zero anúncios consultados**,
nenhum JSON de scan gravado e resultado anterior preservado. Nenhum segredo foi
exibido ou incluído no repositório.

**Não validado em execução real.** Credenciais precisam estar disponíveis em
um ambiente autorizado para repetir a busca. Metadados de vault ainda não são
fornecidos pelo adaptador Browse atual; presença no vault não foi confirmada.

## CI e aprovação operacional

A suíte do GitHub Actions verifica push na main e pull requests, sem credenciais.
Este registro descreve execução local; a execução remota deve ser conferida no PR.
As pendências da configuração continuam bloqueando APROVAR, mesmo com CI verde.
Não foi criado agendamento, executada compra ou feito merge na main.

## Uso dos secrets já cadastrados no GitHub

O operador confirmou por imagem que `EBAY_CLIENT_ID` e `EBAY_CLIENT_SECRET`
já existem como repository secrets. A ausência constatada anteriormente era
somente no ambiente local da conversa, não uma verificação de ausência no GitHub.

O workflow `.github/workflows/validate-ebay.yml` passa esses dois secrets apenas
à etapa `python validate_live.py --group 3 --limit 1`. Instalação e testes não
recebem as chaves. Permissão do token GitHub: somente leitura de conteúdo.

A validação inicial é disparada por alteração desta ligação na branch
`feat/ebay-psa-slab-policy`; não há cron, execução periódica ou trigger de PR com
secrets. O workflow também declara disparo manual para uso após estar disponível
na branch padrão. Uma carta e uma página (até 200 anúncios, fora retentativas)
limitam o consumo. `EBAY_DEV_ID`, `EBAY_ENV`, `EBAY_MARKETPLACE_ID` e `EBAY_SCOPE`
não são necessários ao código atual, que usa Production/EBAY_US/scope de leitura.

O resultado fica no artefato `ebay-live-validation-<run_id>` por 7 dias. Somente
presença das chaves, contagens, códigos HTTP e relatório de anúncios são
registrados; não há valores de secrets, tokens ou dump do ambiente.

Código 0 exige anúncios reais e vendas PSA comparáveis processados; código 2
indica anúncios reais sem referência PSA estrita; código 1 indica bloqueio,
falha de fonte ou ausência de anúncios. Sucesso técnico não aprova uma compra
nem elimina as pendências econômicas. O resultado remoto deve ser conferido na
execução do GitHub Actions, não presumido a partir da presença dos secrets.

## Resultado confirmado no GitHub Actions — 2026-09-05 04:47 UTC

Commit executado: `38005d0957eae5d9fb84ada9af2b1d2219987dbe`.
Execução: https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/actions/runs/33945477409

- Secrets disponíveis no job: sim (somente presença verificada).
- Autenticação e consulta eBay funcionaram: **1 chamada, 198 anúncios**.
- Carta da amostra: Charizard #4, Base Set, EN.
- **197 REJEITAR, 1 REVISAR, 0 APROVAR**.
- **0 candidatos com referência PSA estrita**. O processo retornou código 2,
  status `partial`, motivo `live_listings_received_but_no_strict_psa_comparables`.
- O workflow aparece com falha porque exige validação completa; isso NÃO indica
  falha das credenciais. O relatório foi preservado como artefato da execução.
- Os **548 testes offline passaram**, também na CI separada (run 33945479315).

A pendência de acesso às chaves está resolvida para o GitHub Actions. Falta obter
comparáveis PSA que atendam aos critérios e concluir as definições econômicas.
Esta amostra não valida a qualidade de todas as referências nem autoriza compras.

## Revisão atual — base 86b8324, 2026-09-05

A revisão amplia os testes e substitui as regras econômicas anteriores conforme
as novas respostas do operador. Os registros acima são históricos, de commits
anteriores, e não representam execução da versão revisada.

Validação local concluída: 612 testes passaram, e `git diff --check` não apontou
erros. Os resultados remotos desta revisão estão abaixo; os registros anteriores
permanecem apenas como histórico.

### Validação real de 3deee2b e correção derivada

[Execução 33947693117](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/actions/runs/33947693117):
597 testes passaram; 1 chamada de busca, 50 anúncios, 39 REVISAR, 11 REJEITAR,
zero APROVAR e zero linhas com referência PSA suficiente. 43 títulos não
informavam idioma. Resultado parcial, código 2. A fonte pública de vendas
funcionou; a identificação dos anúncios impediu chegar à comparação.

Correção implementada: consultar o atributo Language de getItem para anúncios
certificados com identidade compatível e idioma ausente. Até 10 consultas por
carta, contadas na API; nenhuma inferência de inglês. Divergências entre título
e atributos geram REVISAR. A validação seguinte está registrada abaixo.

### Resultado de 0c3a52b — consulta dos detalhes

[Execução 33947960679](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/actions/runs/33947960679):
611 testes passaram; 50 anúncios, 11 chamadas eBay (1 busca e 10 detalhes),
39 REVISAR, 11 REJEITAR, zero APROVAR. Os detalhes confirmaram idioma em 10
anúncios, mas eram reimpressões Celebrations/Classic, incompatíveis com as vendas
da variante original. Resultado parcial, código 2, sem falha de autenticação.

### Resultado final da revisão de código — a084652, 05:50 UTC

[Execução 33948217352](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/actions/runs/33948217352):
consulta `pokemon Charizard 4 Base Set 1999 English PSA 10`. O ano vem do catálogo;
não substitui as verificações de identidade, idioma ou variante.

- **612 testes passaram** no job e na [CI separada](https://github.com/matheuscllm-lgtm/ebay-arbitrage-scanner/actions/runs/33948218791).
- **13 anúncios, 8 chamadas eBay** (1 busca e 7 detalhes).
- **13 REVISAR, zero REJEITAR, zero APROVAR**.
- Os anúncios da variante comum que chegaram aos detalhes não continham Language.
  Os dois com idioma confirmado eram Shadowless/1st Edition; nenhuma venda do
  conjunto público atendia à combinação estrita de variante, idioma e nota.
- A página pública foi processada com **375 registros de vendas**. Isso não
  equivale a 375 comparáveis: o JSON explica as exclusões em cada candidato.
- **Zero candidatos com ao menos três vendas PSA aceitas**; status `partial`,
  código 2. O workflow aparece com falha por evidência insuficiente, sem erro de API.
- Relatório e JSON preservados no artefato `ebay-live-validation-33948217352`.

Conclusão: implementação e testes concluídos nesta revisão; a validação de ponta
a ponta permanece parcial por ausência de identificação/comparáveis suficientes
na amostra. Não representa validação dos 12 grupos, nem oportunidade de compra.
Não se alteraram critérios para obter sucesso artificial.

`--check-config` confirma estrutura válida e duas definições pendentes:
`evidence.max_dispersion_percent` e `graders.BGS.combine_9_5_premium` (somente BGS
9,5). Elite, saque de 10%, prazo de 120 dias e cobertura dos US$10 estão definidos.
Sem limite de dispersão, APROVAR permanece bloqueado. Nenhum novo agendamento foi
criado; a ativação deve vir após fechar as regras e obter validação suficiente.
