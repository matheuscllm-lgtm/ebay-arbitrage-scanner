# Instruções de desenvolvimento — EBAY PSA

As instruções do projeto EBAY PSA de 2026-09-05 substituem as regras econômicas
anteriores deste arquivo. O histórico integral permanece no Git. Leia
[`docs/EBAY_PSA.md`](docs/EBAY_PSA.md), [`config.yaml`](config.yaml) e os testes
antes de alterar regras. O código, a configuração e os testes demonstram o que
está implementado; a documentação registra a intenção.

- Apenas cartas já certificadas, priorizando PSA. Não reativar raw por argumento CLI.
- Referência: vendas concluídas PSA da mesma carta, coleção, número, variante,
  idioma e nota correspondente. Não usar preços pedidos como prova de revenda.
- BGS: teto configurado de PSA +5%; nota 9,5 usa PSA 9 +5%, sem acumular ajustes
  quando a combinação estiver indefinida. PSA não possui 9,5.
- TAG 10 equivale a PSA 10 para comparação estratégica. Revenda em outra
  certificadora depende de vendas próprias; categorias especiais ficam separadas.
- CGC: preço do item até 40% da referência PSA ajustada (confirmado).
- Regra econômica: lucro estimado >US$40 OU desconto >30%, preservando lucro positivo.
- US$10 cobrem envios/impostos até COMC. Elite US$2,50; venda 5%; saque 10%
  informado pelo operador; horizonte 120 dias (faixa solicitada 90–120).
- Armazenamento calculado com carência; segurança adicional sem carência.
- Limite de dispersão e combinação BGS 9,5 indefinidos ficam em REVISAR.
- Idiomas separados; não presumir inglês nem equivalência entre idiomas asiáticos.
- Reserva US$10 por carta, contabilizada uma vez, com cobertura explícita.
- Separar compra, custos, investimento, referência, revenda e lucro; distinguir
  desconto, margem sobre a venda e retorno sobre o investimento.
- Comprar no vault é compatível e preferencial quando confirmado. Revenda COMC;
  nunca depender de listarmos diretamente no vault.
- APROVAR / REJEITAR / REVISAR, sempre com motivos e evidências. APROVAR é
  aprovação na análise, sem executar compra. Falta de informação não aprova.
- Manter links, datas, contagem de vendas, diferenças relevantes e baixa liquidez.
- Mudanças econômicas exigem testes de regressão; registrar a alteração no changelog.
- Distinguir planejado, implementado, testado e validado em execução real.
- Consolidar regras, implementar, testar, validar busca real e só então automatizar.

## Repositório e operação

- Fluxo padrão: branch + PR, nunca push direto em main.
- Repositório independente dos scanners irmãos; não mudar seus parâmetros aqui.
- Não versionar credenciais ou dados de scans. `data/` e `results/` são locais.
- As regras solicitadas pelo operador ficam versionadas em config, docs e testes.
- `watchlist.yaml` é gerada e versionada: não editar manualmente. As entradas de
  catálogo são públicas e têm origem registrada em `src/catalog/README.md`.
- Percentuais inteiros: 20 significa 20%; null é pendência, nunca zero.
- Credenciais são `EBAY_CLIENT_ID` e `EBAY_CLIENT_SECRET`, somente no ambiente.
- CI offline: `python -m pytest -q`. Busca real: `python main.py --group 3`.
- Gerar relatório com `python ebay_summary.py results/last_scan.json -o results/report.md`.
- Orientações antigas em comandos/skills históricos não podem reativar raw,
  retirar custos ou substituir as regras desta versão. Consulte o README atual.
