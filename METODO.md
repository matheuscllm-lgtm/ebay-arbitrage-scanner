# O Método — comprar com precisão para lucratividade

Este documento explica como o scanner decide o que entra na tabela e com qual
veredito. A filosofia em uma frase: **precisão acima de cobertura** — um falso
positivo custa dinheiro real; um falso negativo custa só uma oportunidade.

## 1. Por que watchlist (e não "escanear o eBay inteiro")

O maior erro em arbitragem de cartas é **identificar errado a carta** — pagar
preço de Charizard alt-art num Charizard comum, ou de PSA 10 numa PSA 8. Em vez
de tentar adivinhar qual carta cada anúncio é, o scanner parte da carta certa
(com a URL exata do PriceCharting) e busca anúncios **dela**. O título do
anúncio ainda precisa confirmar nome **e número** da carta para contar.

## 2. Preço justo (a régua)

O preço justo vem do PriceCharting, que agrega as **vendas concluídas do
eBay** — ou seja, o que as pessoas de fato pagaram, não o que vendedores
pedem. Por grade: raw (ungraded), Grade 7, 8, PSA 9, 9.5, PSA 10, BGS 10,
CGC 10. Isso cobre o requisito de "comparar com eBay sold/completed listings"
sem precisar de acesso pago (a API de vendidos do eBay é restrita; o
PriceCharting publica o agregado de graça).

## 3. Os cinco componentes da avaliação

### 3.1 Margem bruta (o desconto)

```
margem = (preço_justo − preço_do_anúncio) / preço_do_anúncio × 100
```

Regra canônica cross-scanner: margem **bruta pura** — zero taxa embutida (sem
frete, taxa de importação, câmbio, fee de venda). O operador calcula custos por
fora. O frete do anúncio aparece em coluna separada, informativo.

- Abaixo de **30%**: não reporta.
- 30–60%: candidata real.
- Acima de **60%**: vira **SUSPEITO** — no eBay, desconto bom demais quase
  sempre é carta errada, grade errada, foto de estoque ou golpe.

### 3.2 Liquidez (consigo revender?)

Vendas por mês daquela grade, do PriceCharting:

| Tier | Vendas/mês | Leitura |
|---|---|---|
| A | ≥ 10 | revende em dias |
| B | 3–9 | revende em semanas |
| C | 1–2 | revende em 1–2 meses |
| D | < 1 | pode encalhar — sempre vira REVISAR |

### 3.3 Tendência (valorização)

A variação recente do preço justo (delta do PriceCharting). Preço subindo
reforça a tese (a margem tende a crescer enquanto a carta está em mãos);
preço caindo é alerta — a margem de hoje pode evaporar.

### 3.4 Spread raw → PSA 9 → PSA 10 (potencial de grading)

Para cartas raw NM, a tabela mostra quanto a mesma carta vale em PSA 9 e
PSA 10 (em % acima do raw). Spread alto = candidata a grading. **Este scanner
só mostra o spread** — a matemática de probabilidade de nota e EV de grading é
domínio do projeto PSA Arbitrage (não duplicamos aqui).

### 3.5 Risco (as flags)

Cada linha carrega suas ressalvas:

- **REJEITAR**: proxy/réplica/reprint/custom, code card, slab vazio, etc.
- **LOTE**: anúncio de lote/coleção (preço não compara com carta única).
- **LEILÃO**: preço atual pode subir até o fim.
- **VENDEDOR**: menos de 50 avaliações, ou feedback < 98%.
- **CONDIÇÃO**: raw sem NM confirmado → rejeita (invariante: raw só Near
  Mint; na dúvida, fora — "NM/LP" no título rejeita).
- **IDIOMA**: fora de EN/JP → rejeita.
- **GRADE fora do escopo**: PSA 8, SGC, ACE etc. → rejeita.

## 4. Score (0–100)

Pesos: margem 45% · liquidez 25% · tendência 15% · risco 15%.

- Margem: 30% → 50 pts; 100%+ → 100 pts (linear no meio).
- Liquidez: A=100, B=75, C=45, D=15.
- Tendência: subindo=100, estável=60, caindo=20.
- Risco: 100 − 35 por flag (mínimo 0).

O score serve para **ordenar a tabela**, não para decidir compra.

## 5. Vereditos

| Veredito | Significado |
|---|---|
| OPORTUNIDADE | margem ≥ 30%, liquidez A–C, nenhuma ressalva |
| REVISAR | passou do threshold mas tem ressalva (leilão, liquidez D, idioma divergente...) |
| SUSPEITO | margem > 60% ou risco alto — conferir manualmente antes de qualquer coisa |
| REJEITADO | violou regra dura (condição, escopo, proxy) — listado só para auditoria |

## 6. Checklist manual antes de qualquer compra (operador)

O scanner não enxerga fotos. Antes de agir numa linha da tabela:

1. Abrir o anúncio e **conferir a foto**: é a carta certa? Número do set
   visível? No caso de slab, o número de certificação aparece?
2. PSA/BGS/CGC: conferir o certificado no site da empresa (cert lookup).
3. Raw: avaliar condição pelas fotos (cantos, superfície, centralização) —
   título dizendo "NM" não é garantia.
4. Vendedor: histórico de vendas de cartas (não só feedback genérico).
5. Recalcular o custo real: preço + frete + importação/impostos + câmbio.
6. Conferir o preço justo ao vivo no link do PriceCharting da linha.

## 7. Identificação de cartas subvalorizadas (camada de tese)

A watchlist é onde entra a tese de investimento (personagem, raridade, set,
arte, supply, tendência). O fluxo: adicionar à watchlist as cartas que a tese
indica (ex.: alt-arts de Eeveelutions, promos de museu, Charizards de era
clássica), e deixar o scanner vigiar os preços delas. Expandir a watchlist é
barato — cada carta custa ~4 chamadas de API por scan.
