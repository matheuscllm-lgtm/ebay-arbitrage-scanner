# Registro de validação — EBAY PSA

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

Validação local: suíte completa, compilação e git diff --check serão conferidos
antes do commit. A validação remota desta revisão será registrada após a execução;
não presumir sucesso a partir dos registros de 38005d0.
