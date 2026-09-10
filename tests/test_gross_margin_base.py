"""A margem bruta tem de ser medida contra o que o SLAB REALMENTE VENDE.

Achado ao responder "por que 150%?" (2026-09-09). No run real, as 7 unicas linhas acima
de 100% de margem eram todas CGC 10 GEM, com numeros implausiveis (item a US$80 contra
"referencia" US$3.552). A causa nao era o corte de suspeita: e que o gate `gross_margin`
media a margem contra `comparison_reference`, que para CGC/TAG/BGS e a referencia PSA
AJUSTADA -- um valor que aquele slab nunca alcanca.

O gate anterior (`profit_or_discount`) usava `resale['price_exact']`, as vendas da
PROPRIA certificadora. Trocar para margem bruta trocou a base em silencio, so para nao
PSA. Para PSA nada muda: `resale` E a evidencia PSA.

Consequencia concreta: com referencia PSA 1000, uma CGC 10 vale no maximo 40% disso
(`max_reference_percent`), ou seja 400. Um anuncio a 350 dava 186% de margem contra a
referencia PSA e passava folgado num gate de 43%, quando a margem honesta contra a
revenda CGC e 14% -- abaixo do gate.
"""
import pytest

from src.slab_strategy import evaluate
from tests.test_slab_strategy import CARD, cfg, listing, refs, sales


def gm(threshold=43, **eco):
    c = cfg()
    c['slab_strategy']['economics'].update(gate_mode='gross_margin',
                                           min_gross_margin_percent=threshold,
                                           suspicious_gross_margin_percent=150, **eco)
    return c


def cgc_refs(psa_price=1000, cgc_price=400):
    """Vendas PSA 10 (referencia) + vendas da PROPRIA CGC 10 Gem (revenda)."""
    return refs(sales(grade='PSA 10', price=psa_price, start=100),
                sales(grade='CGC 10 Gem', price=cgc_price, start=200))


def test_non_psa_margin_uses_the_graders_own_resale_not_the_psa_reference():
    """Preco 350: 186% contra a referencia PSA, 14% contra a revenda CGC. O gate de 43%
    tem de REPROVAR, porque 14% e a margem que existe de verdade."""
    c = gm()
    o = evaluate(CARD, listing(grade='CGC 10 Gem', price=350), config=c, refs=cgc_refs())
    gate = o.strategy['economic_gate']
    assert gate['gross_margin_percent'] == pytest.approx(14.29, abs=0.05), gate
    assert gate['margin_pass'] is False
    assert 'abaixo-da-margem-bruta-minima' in (o.strategy['rejection_reasons'] or [])


def test_the_gate_says_which_base_it_used():
    c = gm()
    o = evaluate(CARD, listing(grade='CGC 10 Gem', price=350), config=c, refs=cgc_refs())
    gate = o.strategy['economic_gate']
    assert gate['margin_base_source'] == 'resale'
    assert float(gate['margin_base']) == pytest.approx(400.0)


def test_psa_is_unchanged_because_its_resale_is_its_own_reference():
    c = gm()
    o = evaluate(CARD, listing(grade='PSA 10', price=50), config=c,
                 refs=refs(sales(grade='PSA 10', price=100)))
    gate = o.strategy['economic_gate']
    assert gate['gross_margin_percent'] == 100.0
    assert float(gate['margin_base']) == pytest.approx(100.0)


def test_without_a_resale_base_the_gate_does_not_approve():
    """Sem vendas da propria certificadora nao ha margem honesta a calcular. O gate fica
    calado (a linha ja carrega `revenda-sem-vendas-da-certificadora`) e NUNCA aprova por
    margem -- fail-closed, em vez de aprovar contra um numero de outra nota."""
    c = gm()
    o = evaluate(CARD, listing(grade='CGC 10 Gem', price=50), config=c,
                 refs=refs(sales(grade='PSA 10', price=1000)))
    gate = o.strategy.get('economic_gate') or {}
    assert gate.get('margin_pass') is not True
    assert o.verdict != 'APROVAR'
    assert 'revenda-sem-vendas-da-certificadora' in (o.strategy['review_reasons'] or [])


def test_the_printed_ceiling_respects_both_the_grader_rule_and_the_gate():
    """`comparison_cap` e o maior preco ainda aceitavel. Para CGC valem DUAS regras: o
    teto da certificadora (40% da referencia PSA = 400) e o teto do gate (revenda/1,43 =
    279,72). O publicado tem de ser o menor dos dois."""
    c = gm()
    o = evaluate(CARD, listing(grade='CGC 10 Gem', price=350), config=c, refs=cgc_refs())
    assert o.strategy['comparison_cap'] == pytest.approx(279.72, abs=0.01)
