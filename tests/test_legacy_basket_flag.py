"""Chave `legacy_reference.require_number_in_sale_title` na cesta do caminho LEGADO.

Existem duas réguas para montar a cesta de vendas comparáveis:

- caminho VIGENTE (`slab_strategy.reference_sales` -> `identity_matches`): exige o
  NÚMERO da carta no título da venda (fail-closed);
- caminho LEGADO (`pc_sales.comparable_sales`): aceita a venda a menos que o título
  CONTRADIGA a identidade (`title_parser.sale_contradicts_card`) — falta de número
  não elimina.

Unificar as duas deixa a cesta MENOR, e a cobertura de referência já é o gargalo do
scanner. Por isso a unificação entra como parâmetro keyword-only `require_number`,
DESLIGADO por padrão e reversível. Estes testes fixam os dois lados da chave.
"""
import inspect

import pytest

from src import pc_sales as pc
from src.models import WatchCard


CARD = WatchCard(name="Charizard", set_name="Base Set", number="4", language="EN",
                 pc_url="https://www.pricecharting.com/game/pokemon-base-set/charizard-4")

# Venda da PRÓPRIA carta cujo título não cita o número: hoje entra na cesta legada.
NO_NUMBER = {"title": "Pokemon Charizard Base Set Holo Rare PSA 9", "price": 100.0,
             "date": "2026-09-01"}
# Mesma carta com o número explícito (fração e marcador "#").
WITH_FRACTION = {"title": "Pokemon Charizard 4/102 Base Set Holo PSA 9", "price": 110.0,
                 "date": "2026-09-01"}
WITH_HASH = {"title": "Pokemon Charizard #4 Base Set Holo PSA 9", "price": 120.0,
             "date": "2026-09-01"}
# Zero à esquerda é a MESMA carta ("004/102" == "4/102").
WITH_PADDED = {"title": "Pokemon Charizard 004/102 Base Set Holo PSA 9", "price": 130.0,
               "date": "2026-09-01"}
# Contradições de identidade: número explícito DIFERENTE e outro nome.
OTHER_NUMBER = {"title": "Pokemon Charizard 11/102 Base Set Holo PSA 9", "price": 900.0,
                "date": "2026-09-01"}
OTHER_NAME = {"title": "Pokemon Blastoise 4/102 Base Set Holo PSA 9", "price": 800.0,
              "date": "2026-09-01"}

ALL_SALES = [NO_NUMBER, WITH_FRACTION, WITH_HASH, WITH_PADDED, OTHER_NUMBER, OTHER_NAME]


def _prices(rows):
    return [r["price"] for r in rows]


# ── assinatura: o parâmetro é keyword-only e o padrão é False ─────────────────

def test_require_number_is_keyword_only_and_defaults_to_false():
    params = inspect.signature(pc.comparable_sales).parameters
    assert "require_number" in params, "comparable_sales precisa do parâmetro require_number"
    assert params["require_number"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["require_number"].default is False
    assert params["card"].kind is inspect.Parameter.KEYWORD_ONLY
    # Ordem posicional intocada (chamadores antigos continuam válidos).
    positional = [n for n, p in params.items()
                  if p.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD]
    assert positional == ["sales", "grader", "value", "qualifier", "variants"]


def test_require_number_cannot_be_passed_positionally():
    with pytest.raises(TypeError):
        pc.comparable_sales(ALL_SALES, "PSA", 9.0, "", frozenset(), CARD, True)


# ── padrão False: cesta de hoje, byte a byte ─────────────────────────────────

def test_default_preserves_todays_basket():
    """Sem a chave (e com ela em False) a cesta é a de hoje: a venda SEM número
    continua dentro, porque falta de número nunca foi contradição."""
    default = pc.comparable_sales(ALL_SALES, "PSA", 9.0, card=CARD)
    explicit = pc.comparable_sales(ALL_SALES, "PSA", 9.0, card=CARD, require_number=False)
    assert default == explicit
    assert _prices(default) == [100.0, 110.0, 120.0, 130.0]


def test_default_without_card_is_unchanged():
    assert (pc.comparable_sales(ALL_SALES, "PSA", 9.0)
            == pc.comparable_sales(ALL_SALES, "PSA", 9.0, require_number=False))


# ── True: passa a exigir o número no título ──────────────────────────────────

def test_require_number_drops_sale_without_number_in_title():
    got = pc.comparable_sales(ALL_SALES, "PSA", 9.0, card=CARD, require_number=True)
    assert NO_NUMBER not in got
    assert 100.0 not in _prices(got)


def test_require_number_keeps_sale_with_the_right_number():
    got = pc.comparable_sales(ALL_SALES, "PSA", 9.0, card=CARD, require_number=True)
    assert _prices(got) == [110.0, 120.0, 130.0]


def test_require_number_only_shrinks_the_basket():
    on = pc.comparable_sales(ALL_SALES, "PSA", 9.0, card=CARD, require_number=True)
    off = pc.comparable_sales(ALL_SALES, "PSA", 9.0, card=CARD, require_number=False)
    assert all(sale in off for sale in on)
    assert len(on) < len(off)


# ── card=None: não há número esperado, então não filtra ──────────────────────

def test_require_number_without_card_does_not_filter():
    """Sem `card` não há número esperado para exigir: a chave não pode inventar
    filtro (e não pode zerar a cesta)."""
    assert (pc.comparable_sales(ALL_SALES, "PSA", 9.0, card=None, require_number=True)
            == pc.comparable_sales(ALL_SALES, "PSA", 9.0, card=None))


# ── a guarda de contradição continua valendo nos DOIS modos ──────────────────

@pytest.mark.parametrize("require_number", [False, True])
def test_contradiction_guard_applies_in_both_modes(require_number):
    got = pc.comparable_sales(ALL_SALES, "PSA", 9.0, card=CARD,
                              require_number=require_number)
    assert OTHER_NUMBER not in got, "número explícito diferente contradiz a identidade"
    assert OTHER_NAME not in got, "outro nome contradiz a identidade"


@pytest.mark.parametrize("require_number", [False, True])
def test_grade_and_variant_guards_still_apply(require_number):
    sales = [WITH_FRACTION,
             {"title": "Pokemon Charizard 4/102 Base Set 1st Edition PSA 9",
              "price": 5000.0, "date": "2026-09-01"},
             {"title": "Pokemon Charizard 4/102 Base Set Holo PSA 10",
              "price": 9000.0, "date": "2026-09-01"}]
    got = pc.comparable_sales(sales, "PSA", 9.0, card=CARD, require_number=require_number)
    assert _prices(got) == [110.0]
