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
