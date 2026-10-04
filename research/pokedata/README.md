# PokeData — anexos para revisão

Entrada canônica desta revisão: [docs/POKEDATA_REVIEW.md](../../docs/POKEDATA_REVIEW.md).
Contexto anterior: [docs/POKEDATA_PROJECT_STATE.md](../../docs/POKEDATA_PROJECT_STATE.md).

Os cinco anexos recebidos foram preservados; nomes originais, destinos e SHA-256 estão em [inputs/manifest.json](inputs/manifest.json).
A planilha completa está dentro de `inputs/pokedata_crossref.zip`, no membro `pokedata_crossref/output/PokeData_catalogo_correspondencia.xlsx`, com bytes idênticos ao anexo separado. A parcial com CHT do PR anterior continua em `PokeData_correspondencias_JP_CHS_CHT_parcial.xlsx`; o anexo parcial desta rodada está em `inputs/`. Os universos e critérios são diferentes e não foram fundidos.

O XLSX completo é disponibilizado pelo ZIP porque seu envio avulso em base64 excede o limite de 16 MiB da conexão GitHub. A auditoria lê o membro do ZIP diretamente e confere o hash do anexo original. Seus scripts estão expandidos em `pipeline/` para revisão por linha. Documentos dentro dessa pasta e em `inputs/` são registros da entrega anterior; conflitos devem ser avaliados conforme a revisão acima.

```bash
python research/pokedata/audit_inputs.py
python research/pokedata/test_pipeline.py
```

As verificações são offline. Não executar `pipeline/run_pipeline.sh` para uma simples revisão: ele baixa fontes e processa o catálogo completo. O pipeline ainda tem achados pendentes e não está integrado ao scanner.
