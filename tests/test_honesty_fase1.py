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




# --- fix 4: funil da entrega da politica com rotulos humanos e vocabulario da politica --

def test_policy_report_prints_funnel_with_human_labels_and_policy_verdicts():
    from collections import Counter
    from src import slab_report
    payload = _policy_payload(funnel=Counter(seen=7, skip_raw=2, rows_opportunity=1,
                                             rows_review=2, rows_rejected=3, weird=1))
    text = slab_report.render(payload)
    tail = text.split("Funil da busca:")[1]
    assert "Anúncios analisados (após dedupe): 7" in tail
    assert "escopo exclusivo de slabs): 2" in tail
    assert "Linhas APROVAR: 1" in tail and "Linhas REVISAR: 2" in tail
    assert "Linhas REJEITAR (com motivo): 3" in tail
    assert "outros: weird=1" in tail            # contador sem rotulo nunca some
    assert '{"seen"' not in text                 # nao e mais JSON cru
    assert "OPORTUNIDADE" not in text and "REJEITADO" not in text


def test_console_funnel_uses_policy_labels_when_policy_is_active(monkeypatch, tmp_path, capsys):
    from collections import Counter
    import main
    from src import scanner
    from src.slab_strategy import evaluate, policy_config
    from tests.test_slab_strategy import CARD as PCARD, listing, sales, refs
    opp = evaluate(PCARD, listing(price=50), config=policy_config(), refs=refs(sales()))
    monkeypatch.setattr(scanner, "load_watchlist", lambda *a, **k: [PCARD])
    monkeypatch.setattr(scanner, "run_scan",
                        lambda **kw: ({}, [opp], False, Counter(seen=1, rows_opportunity=1), False))
    assert main.main(["--out", str(tmp_path / "o.json"), "--csv", str(tmp_path / "o.csv")]) == 0
    out = capsys.readouterr().out
    assert "Linhas APROVAR: 1" in out
    assert "OPORTUNIDADE" not in out.split("Funil:")[1]


def test_legacy_funnel_labels_unchanged_for_legacy_json():
    lines = report.funnel_lines({"seen": 3, "rows_opportunity": 1, "rows_rejected": 1})
    assert any(line.startswith("Linhas OPORTUNIDADE: 1") for line in lines)
    assert any(line.startswith("Linhas REJEITADO (com motivo): 1") for line in lines)




# --- fix 5: cabecalho da entrega da politica diz QUANDO, O QUE e COM QUAL REGRA coletou --

def test_policy_report_header_states_collection_time_scope_and_policy_keys():
    from collections import Counter
    from src import slab_report
    payload = _policy_payload(group="3", watchlist_count=3,
                              funnel=Counter(seen=7, ebay_calls=5, cards=3))
    text = slab_report.render(payload)
    head = text.split("| Carta")[0]
    stamp = payload["meta"]["timestamp"][:16].replace("T", " ")
    assert stamp in head and "UTC" in head
    assert "grupo `3`" in head and "3 carta(s)" in head
    assert "2026-09-05.4" in head
    for key in ("gate_mode: gross_margin", "min_profit_usd: 40",
                "min_discount_percent: 30", "min_price_usd: 10"):
        assert key in head, key
    assert "chamadas à Browse API: 5" in head and "max_ebay_calls: 500" in head
    assert "max_pages: 3" in head


def test_policy_report_without_meta_says_nd_instead_of_inventing():
    from src import slab_report
    text = slab_report.render({"rows": []})
    head = text.split("|---")[0]
    assert "Coleta: n/d" in head
    assert "None" not in head


def test_policy_report_banner_says_why_the_run_is_partial():
    from collections import Counter
    from src import slab_report
    early = slab_report.render(_policy_payload(aborted=True, funnel=Counter(seen=1, stopped_early=1)))
    visited = slab_report.render(_policy_payload(aborted=True, funnel=Counter(seen=1, pc_error=1)))
    assert "cartas restantes NÃO foram varridas" in early.split("| Carta")[0]
    assert "todas as cartas foram visitadas" in visited.split("| Carta")[0]
