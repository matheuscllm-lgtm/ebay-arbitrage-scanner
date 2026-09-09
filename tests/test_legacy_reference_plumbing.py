"""Encanamento da chave `legacy_reference.require_number_in_sale_title`.

`pc_sales.comparable_sales` ganhou o parametro `require_number` (regua do caminho
VIGENTE: o titulo da venda tem de NOMEAR o numero da carta). O parametro so vale
alguma coisa se alguem o LIGAR a partir do config -- senao a chave existe no
`config.yaml` e nao faz nada, que e pior do que nao existir.

A chave vale para a cesta da REFERENCIA legada (`CardRefs.slab`). NAO vale para
`CardRefs.sales_history`, que alimenta a tendencia (B5) da coluna informativa: o
nome da chave e `legacy_reference`, e apertar a cesta da tendencia mudaria a coluna
sem que ninguem tenha pedido.
"""
from src import pc_sales, scanner
from src.models import WatchCard

PC_URL = "https://www.pricecharting.com/game/pokemon-base-set/charizard-4"
CARD = WatchCard(name="Charizard", set_name="Base Set", number="4", language="EN",
                 pc_url=PC_URL)

# Duas vendas PSA 9 da Charizard: uma NOMEIA o numero (4/102), a outra nao.
_COM_NUMERO = "1999 Pokemon Base Set Charizard 4/102 Holo PSA 9"
_SEM_NUMERO = "1999 Pokemon Base Set Charizard Holo PSA 9"


def _body():
    rows = [("ebay", "111", "2026-08-01", _COM_NUMERO, 900.0),
            ("ebay", "222", "2026-08-05", _SEM_NUMERO, 800.0),
            ("ebay", "333", "2026-08-09", _COM_NUMERO, 950.0)]
    trs = "".join(
        f'<tr id="{src}-{sid}"><td class="date">{day}</td>'
        f'<td class="title">{title}</td>'
        f'<td class="js-price">${price:,.2f}</td></tr>'
        for src, sid, day, title, price in rows)
    return f'<div class="completed-auctions-manual-only"><table>{trs}</table></div>'


def _grade():
    from src import grading
    return grading.Grade("PSA", 9.0)


def test_default_keeps_the_sale_without_the_number_in_the_legacy_basket():
    """Sem a chave, a regua legada nao muda: falta de numero NAO elimina a venda."""
    refs = scanner.CardRefs(CARD, _body(), PC_URL)
    comps = pc_sales.comparable_sales(refs._sales, "PSA", 9.0, "", frozenset(),
                                      card=CARD, require_number=False)
    assert sorted(s["title"] for s in comps) == sorted(
        [_COM_NUMERO, _SEM_NUMERO, _COM_NUMERO])


def test_card_refs_accepts_require_number_and_applies_it_to_the_reference_basket():
    """`CardRefs(require_number=True)` aperta a cesta da REFERENCIA: a venda sem
    numero no titulo sai."""
    refs = scanner.CardRefs(CARD, _body(), PC_URL, require_number=True)
    ref = refs.slab(_grade())
    assert ref is not None, "a cesta apertada ainda tem duas vendas; nao pode zerar"
    assert ref.n_sales == 2, f"esperado 2 vendas com numero, veio {ref.n_sales}"


def test_card_refs_default_is_the_loose_basket():
    refs = scanner.CardRefs(CARD, _body(), PC_URL)
    ref = refs.slab(_grade())
    assert ref is not None and ref.n_sales == 3


def test_require_number_does_not_touch_the_trend_basket():
    """`sales_history` alimenta a coluna informativa (B5) e NAO e a referencia:
    a chave `legacy_reference` nao pode encolher essa cesta."""
    refs = scanner.CardRefs(CARD, _body(), PC_URL, require_number=True)
    assert len(refs.sales_history(_grade())) == 3


def test_load_card_page_reads_the_flag_from_config(monkeypatch):
    """O encanamento de verdade: `load_card_page` le
    `legacy_reference.require_number_in_sale_title` e repassa para `CardRefs`."""
    monkeypatch.setattr(pc_sales, "fetch_page", lambda *a, **k: _body())
    _, refs_on = scanner.load_card_page(
        CARD, {"legacy_reference": {"require_number_in_sale_title": True}}, log=lambda *a: None)
    _, refs_off = scanner.load_card_page(CARD, {}, log=lambda *a: None)
    assert refs_on.slab(_grade()).n_sales == 2
    assert refs_off.slab(_grade()).n_sales == 3
