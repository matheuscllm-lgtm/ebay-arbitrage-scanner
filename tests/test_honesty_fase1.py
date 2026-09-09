"""Auditoria de honestidade de preco -- Fase 1 (PR-B, 2026-09-09).

Cada teste aqui nasceu VERMELHO (falhando) antes da correcao correspondente e
fixa um rotulo/comportamento da entrega. Vocabulario: "bucket generico" = coluna
do PriceCharting que mistura certificadoras ("Grade 9"); "caminho legado" = motor
antigo (`src/scorer.py`, so testes); "politica" = `src/slab_strategy.py`
(vigente, 2026-09-05.4).
"""
from src import report, scorer
from src.models import FairValue, Opportunity, WatchCard
from tests.test_scorer import CFG_RAW, L, TCG, make_refs

CARD = WatchCard(name="Charizard", set_name="Base Set", number="4/102", language="EN",
                 pc_url="https://www.pricecharting.com/game/pokemon-base-set/charizard-4")


# --- fix 1: a coluna generica "Grade 9" nunca e rotulada "PSA 9" -------------------

def test_fair_value_markdown_labels_generic_grade9_bucket_honestly():
    fair = FairValue(prices={"RAW": 10.0, "GRADE 9": 90.0, "PSA 10": 300.0},
                     deltas={"GRADE 9": 1.0}, sales_per_month={"GRADE 9": 2.0},
                     source_url=CARD.pc_url)
    md = report.fair_value_markdown(CARD, fair)
    assert "| GRADE 9 | $90.00 |" in md
    assert "PSA 9" not in md


def test_raw_spread_reads_generic_grade9_bucket_under_its_own_name():
    # Campo `spread_psa9_pct` (nome enganoso) deixa de existir; o dado vem do
    # bucket generico e se chama assim.
    assert "spread_psa9_pct" not in Opportunity.__dataclass_fields__
    assert "spread_grade9_pct" in Opportunity.__dataclass_fields__
    fair = FairValue(prices={"RAW": 100.0, "GRADE 9": 900.0, "PSA 10": 3000.0})
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set Holo NM", 60.0), fair, CFG_RAW,
                        tcg_ref=TCG(100.0), refs=make_refs())
    assert o is not None
    assert o.spread_grade9_pct == 800 and o.spread_psa10_pct == 2900


# --- fix 3: `--sensitivity` num JSON da politica e declarado, nunca ignorado em silencio --

def _policy_payload(**meta_extra):
    from collections import Counter
    from src.slab_strategy import evaluate, policy_config
    from tests.test_slab_strategy import CARD as PCARD, listing, sales, refs
    c = policy_config()
    opp = evaluate(PCARD, listing(price=50), config=c, refs=refs(sales()))
    funnel = meta_extra.pop("funnel", Counter(seen=1, ebay_calls=2, cards=1))
    return report.scan_payload([opp], meta_extra.pop("watchlist_count", 1), c,
                               funnel=funnel, **meta_extra)


def test_sensitivity_on_policy_json_is_declared_not_silently_ignored():
    import ebay_summary
    payload = _policy_payload()
    plain = ebay_summary.build_markdown(payload)
    noted = ebay_summary.build_markdown(payload, sensitivity=[10, 15, 20])
    assert "--sensitivity" not in plain
    # A tabela e a mesma; so entra um aviso explicito no topo, com os limiares pedidos.
    assert noted.endswith(plain)
    note = noted[: -len(plain)]
    assert "--sensitivity" in note and "ignorad" in note and "10, 15, 20" in note
    assert "legado" in note


