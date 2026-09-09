"""Coluna informativa "Longo prazo" -- testes escritos ANTES do codigo (TDD: o teste
que falha vem primeiro; Fase 2 do prompt 2026-09-09). Enquanto `src/longterm.py` nao
existe, cada teste que o usa falha com ModuleNotFoundError (modulo nao existe) --
o motivo certo. Os testes de invariante (10 e 11) podem nascer verdes de proposito:
eles provam que o que JA existe (veredito, metricas, ranking) nao muda.

O que a coluna e (docs/LONGO_PRAZO.md), em linguagem simples: por anuncio, duas
notas 0-100 --

- PERFIL = caracteristicas observadas da carta (personagem, raridade, tempo fora
  de impressao, faixa de preco da coluna PSA 10, tendencia real das vendas);
- FRAGILIDADE DO DADO = quao fragil e o dado que sustenta a linha (referencia com
  poucas vendas, PSA 10 pouco vendida, referencia desalinhada dos anuncios, tiragem
  ambigua, precos dispersos, vendedor fraco, muitos anuncios iguais...);

mais uma CLASSE LP1-LP4 (faixa de qualidade/completude do perfil: forte / medio /
fraco / fragil -- NAO e nota de compra) e as COBERTURAS (quantos insumos existiam
para cada nota: "4/5" = 4 dos 5 componentes do perfil tinham dado).

Regras que estes testes fixam:
- Sem dado = None = "n/d". Nunca zero. Componente ausente sai da soma e reduz a
  cobertura; PERFIL e n/d com menos de 3 de 5 fontes, FRAGILIDADE e n/d com menos
  de 3 de 10 (soma vazia nao e 0).
- A coluna NUNCA muda veredito, Desconto%, ROI bruto%, `risk_flags`, `reasons`,
  `strategy` nem o ranking (`sort_key`, dois ramos). Os motivos `LP:` vivem em
  `longterm_reasons` e so aparecem em Flags (legado) / "Motivos:" (politica).
- Nunca recomputa uma segunda referencia: le `ref_*` (ou `psa_evidence` no caminho
  da politica) e a cesta de vendas ja existente (`refs.sales_history`).
- Limiares = "calibracao inicial, nao validada".

Fixtures no padrao de tests/test_scorer.py (FakeRefs / REF / L / TCG).
"""
import json
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

import ebay_summary
from src import pricecharting, report, scanner, scorer, slab_report
from src.models import FairValue, Listing, Opportunity, WatchCard
from src.slab_strategy import evaluate as slab_evaluate
from tests.test_scorer import REF, TCG, FakeRefs, L
from tests.test_slab_strategy import CARD as PCARD
from tests.test_slab_strategy import cfg as pcfg
from tests.test_slab_strategy import listing as plisting
from tests.test_slab_strategy import refs as prefs
from tests.test_slab_strategy import sales as psales

FIX = Path(__file__).parent / "fixtures"
PC_URL = "https://www.pricecharting.com/game/pokemon-base-set/charizard-4"
EBAY_URL = "https://www.ebay.com/itm/111"
TODAY = date(2026, 9, 9)


def _lt():
    """Import tardio: o modulo ainda nao existe (Fase 2) -> cada teste falha sozinho,
    com ModuleNotFoundError, em vez de derrubar a coleta do arquivo inteiro."""
    from src import longterm
    return longterm


def _ms(y, m, d):
    """Timestamp em milissegundos (formato do `VGPC.chart_data`), 06:00 UTC como a fixture."""
    return int(datetime(y, m, d, 6, tzinfo=timezone.utc).timestamp() * 1000)


def card(**kw):
    """Carta da watchlist com os sinais de custo zero (grupo, rank, raridade, ano)."""
    base = dict(name="Charizard", set_name="Base Set", number="4", language="EN",
                pc_url=PC_URL, group="3", pokemon="Charizard", pokemon_rank=1,
                rarity="Rare Holo", year=1999)
    base.update(kw)
    return WatchCard(**base)


CARD = card()


def fair(**kw):
    """Colunas do PriceCharting (so informacao): PSA 10 US$300 na faixa 120-359,
    5 vendas/mes (>= 3 = liquida)."""
    base = dict(prices={"RAW": 340.0, "PSA 10": 300.0},
                sales_per_month={"RAW": 60.0, "PSA 10": 5.0}, source_url=PC_URL)
    base.update(kw)
    return FairValue(**base)


def sales(price, n=3, age=30, step=7, title="Charizard 4/102 Base Set PSA 10"):
    """Vendas concluidas sinteticas (formato de `pc_sales.parse_sales`), datadas a
    partir de TODAY: age=30 -> janela 0-180 d; age=200 -> janela 180-365 d."""
    return [{"date": (TODAY - timedelta(days=age + i * step)).isoformat(),
             "price": float(price), "title": title,
             "bucket": "completed-auctions-manual-only", "source": "ebay",
             "sale_id": str(1000 + age + i)} for i in range(n)]


class LTRefs(FakeRefs):
    """FakeRefs + o accessor novo `sales_history(grade, variants)` (cesta de vendas
    comparaveis da nota, so leitura -- B5(ii) e `dispersao` no caminho legado)."""

    def __init__(self, slab=None, history=None, **kw):
        super().__init__(slab=slab, **kw)
        self.history = history or {}
        self.history_calls = []

    def sales_history(self, grade, variants=frozenset()):
        self.history_calls.append((grade.key, frozenset(variants)))
        return list(self.history.get(grade.key, []))


def lp1_setup(c=CARD, title="Charizard 4/102 Base Set PSA 10", price=220.0,
              ref=None, fv=None, history=None, tcg=100.0, asks=(230.0, 240.0, 250.0),
              **listing_kw):
    """Anuncio do caminho LEGADO com tudo disponivel: referencia ok (n=5, 180 d),
    vendas da nota exata +30% (3 recentes a 130 vs 3 antigas a 100), asks alinhados
    (ratio 320/240 = 1.33), TCG raw abaixo da referencia (sem 'stale'), vendedor forte."""
    fv = fv if fv is not None else fair()
    refs = LTRefs(slab={"PSA 10": ref or REF(320.0, what="PSA 10"),
                        "PSA 9": REF(3175.04)},
                  history=history if history is not None
                  else {"PSA 10": sales(130.0, age=30) + sales(100.0, age=200)})
    listing = L(title, price, url=EBAY_URL, **listing_kw)
    opp = scorer.evaluate(c, listing, fv, None, tcg_ref=TCG(tcg), refs=refs)
    assert opp is not None, "fixture do caminho legado tem de virar linha"
    if asks:
        scanner._annotate_ref_alignment(opp, {opp.grade: list(asks)})
    return opp, refs, fv


def assess(opp, refs, fv, n_same=1, cfg=None, **kw):
    lt = _lt()
    return lt.assess(opp.card, opp.listing, opp, fv, refs, n_same, cfg or {},
                     today=TODAY, **kw)


def _snapshot(o):
    """Tudo que a coluna NAO pode tocar."""
    return deepcopy((o.verdict, o.discount_pct, o.gross_margin_pct, o.spread_usd,
                     o.fair_value, o.score, o.risk_flags, o.reasons, o.strategy,
                     o.median_ask, o.ref_source, o.ref_n_sales))


def _table_rows(md):
    """Linhas de tabela markdown com rank numerico ('| 1 | ...')."""
    return [ln for ln in md.splitlines() if ln.startswith("| ") and ln[2:].split(" |")[0].isdigit()]


# ── 1-2: perfil completo, cobertura cheia, referencia fragil ──────────────────────

def test_01_lp1_full_profile_and_full_coverage_on_legacy_path():
    lt = _lt()
    opp, refs, fv = lp1_setup()
    assert opp.verdict == "OPORTUNIDADE"  # sanidade da fixture: nada de LP aqui
    iconic = lt.load_iconic_scores()
    assert iconic["charizard"] == 80.1  # `score` do catalogo, lido em tempo de scan
    res = lt.assess(CARD, opp.listing, opp, fv, refs, 1, {}, today=TODAY,
                    iconic_scores=iconic)
    assert res.tier == "LP1"
    assert res.profile == 92.0 and res.fragility == 0.0
    assert res.profile_coverage == (5, 5) and res.fragility_coverage == (10, 10)
    # B1 rank 1 -> 20; B2 "Rare Holo" em era vintage -> 12; B3 27 anos -> 20;
    # B4 coluna PSA 10 US$300 -> 20; B5 +30% em 12 m -> 20  => 92/100
    assert res.profile_points == {"personagem": 20, "raridade": 12, "supply": 20,
                                  "faixa-psa10": 20, "tendencia": 20}
    assert set(res.fragility_points) == set(lt.FRAGILITY_FLAGS)
    assert all(v == 0 for v in res.fragility_points.values())
    assert res.reasons == []  # nada disparou e nada faltou
    s = res.signals
    assert s["pokemon_rank"] == 1 and s["iconic_score"] == 80.1
    assert s["rarity_raw"] == "Rare Holo" and s["rarity_tier"] == "holo-vintage"
    assert s["year"] == 1999 and s["age_years"] == 27 and s["era"] == "vintage"
    assert s["heavy_reprint"] is False
    assert s["psa10_col"] == 300.0 and s["raw_col"] == 340.0 and s["psa10_sales_pm"] == 5.0
    assert s["trend_source"] == "sales_history" and s["trend_12m_pct"] == 30.0
    assert s["trend_36m_pct"] is None
    assert s["ref_liquidity"] == "ok" and s["ref_n_sales"] == 5 and s["ref_window_days"] == 180
    assert s["ref_source"] == "ref_*"
    assert s["dispersion_pct"] == 0.0 and s["dispersion_source"] == "sales_history"
    assert s["ask_ratio"] == round(320.0 / 240.0, 2) and s["ask_n"] is None
    assert s["listings_same_grade"] == 1 and s["trust_score"] == opp.trust_score
    assert s["printing_tokens"] == []
    assert refs.history_calls == [("PSA 10", frozenset())]  # cesta lida, nunca recomputada


def test_02_thin_reference_adds_30_and_flags_ref_fragil():
    opp, refs, fv = lp1_setup(ref=REF(320.0, n=2, liquidity="thin", window=365, what="PSA 10"))
    res = assess(opp, refs, fv)
    assert res.fragility == 30.0
    assert res.fragility_points["ref-fragil"] == 30
    assert res.signals["ref_liquidity"] == "thin" and res.signals["ref_n_sales"] == 2
    assert any(r.startswith("LP:ref-fragil") for r in res.reasons)
    assert res.profile == 92.0  # a outra nota nao muda


# ── 3-4: supply / reprint forte e raridade por era ────────────────────────────────

def test_03_heavy_reprint_caps_supply_at_8_and_flags_reprint_forte():
    lt = _lt()
    # regra sobre o nome do set VERBATIM do tcgcsv (ideia do outlook, nao codigo)
    assert lt.is_heavy_reprint("SV: Prismatic Evolutions") is True   # set especial "SV:"
    assert lt.is_heavy_reprint("SV: Scarlet & Violet 151") is True
    assert lt.is_heavy_reprint("SV: Paldean Fates") is True
    assert lt.is_heavy_reprint("SWSH: Crown Zenith") is True
    assert lt.is_heavy_reprint("Shining Fates") is True
    assert lt.is_heavy_reprint("Champion's Path") is True
    assert lt.is_heavy_reprint("ME: Ascended Heroes") is True
    assert lt.is_heavy_reprint("Celebrations") is True
    assert lt.is_heavy_reprint("Celebrations: Classic Collection") is False  # excecao
    assert lt.is_heavy_reprint("Pokemon 151") is True         # "151" palavra inteira
    assert lt.is_heavy_reprint("Neo Genesis 1510") is False   # "1510" nao e "151"
    assert lt.is_heavy_reprint("SV01: Scarlet & Violet Base Set") is False  # set numerado
    assert lt.is_heavy_reprint("SWSH09: Brilliant Stars") is False
    assert lt.is_heavy_reprint("Base Set") is False
    assert lt.is_heavy_reprint("") is False
    # teto 8 so rebaixa, nunca sobe
    assert lt.supply_points(6, True) == 8 and lt.supply_points(6, False) == 16
    assert lt.supply_points(27, True) == 8 and lt.supply_points(1, True) == 6
    # via assess: set com reprint forte -> B3 no teto + flag de fragilidade
    c = card(set_name="SV: Prismatic Evolutions", group="1", year=2020)
    opp, refs, fv = lp1_setup(c, title="Charizard 4/102 Prismatic Evolutions PSA 10")
    res = assess(opp, refs, fv)
    assert res.signals["heavy_reprint"] is True and res.signals["age_years"] == 6
    assert res.profile_points["supply"] == 8
    assert "LP:reprint-forte" in res.reasons and res.fragility_points["reprint-forte"] == 15
    # Classic Collection NAO e reprint forte
    c2 = card(set_name="Celebrations: Classic Collection", group="11", year=2021)
    opp2, refs2, fv2 = lp1_setup(c2, title="Charizard 4/102 Classic Collection PSA 10")
    res2 = assess(opp2, refs2, fv2)
    assert res2.signals["heavy_reprint"] is False
    assert "LP:reprint-forte" not in res2.reasons and res2.profile_points["supply"] == 16  # 5 anos


def test_04_rarity_points_by_tier_holo_depends_on_era():
    lt = _lt()
    assert lt.rarity_points("Rare Holo", "vintage") == 12
    assert lt.rarity_points("Rare Holo", "middle") == 6
    assert lt.rarity_points("Rare Holo", "recent") == 6
    assert lt.rarity_points("Special Illustration Rare", "recent") == 20
    assert lt.rarity_points("Double Rare", "recent") == 4
    assert lt.rarity_points("Illustration Rare", "recent") == 16
    assert lt.rarity_points("Trainer Gallery Rare Holo", "recent") == 16
    assert lt.rarity_points("Hyper Rare", "recent") == 14
    assert lt.rarity_points("Shiny Ultra Rare", "recent") == 14   # shiny acima de ultra
    assert lt.rarity_points("Ultra Rare", "recent") == 12
    assert lt.rarity_points("Rare Holo EX", "middle") == 12       # "ex" palavra inteira
    assert lt.rarity_points("Rare Holo V", "recent") == 12
    assert lt.rarity_points("Rare Holo VMAX", "recent") == 12
    assert lt.rarity_points("Rare Holo Lv.X", "middle") == 12
    assert lt.rarity_points("Classic Collection", "recent") == 12
    assert lt.rarity_points("Rare", "vintage") == 4
    assert lt.rarity_points("", "vintage") is None
    assert lt.rarity_points(None, "vintage") is None
    assert lt.rarity_tier("Rare Holo", "vintage") == "holo-vintage"
    assert lt.rarity_tier("Rare Holo", "middle") == "holo"
    assert lt.rarity_tier("Special Illustration Rare", "") == "special-illustration"
    assert lt.rarity_tier("", "middle") is None
    # era vem do grupo canonico (src/groups.py), nunca digitada a mao
    assert lt.era_for_group("3") == "vintage" and lt.era_for_group("7") == "middle"
    assert lt.era_for_group("1") == "recent" and lt.era_for_group("12") == "recent"
    assert lt.era_for_group("") is None and lt.era_for_group("chase-en") is None
    # via assess: mesma raridade, grupos diferentes
    opp3, refs3, fv3 = lp1_setup(card(group="3"))
    res3 = assess(opp3, refs3, fv3)
    assert res3.profile_points["raridade"] == 12 and res3.signals["era"] == "vintage"
    opp7, refs7, fv7 = lp1_setup(card(group="7"))
    res7 = assess(opp7, refs7, fv7)
    assert res7.profile_points["raridade"] == 6 and res7.signals["era"] == "middle"


# ── 5-6: coluna PSA 10 ausente / volume ausente -> teto LP2* ──────────────────────

def test_05_missing_psa10_column_drops_b4_and_caps_class_at_lp2_star():
    fv = fair(prices={"RAW": 340.0}, sales_per_month={"RAW": 60.0})
    opp, refs, _ = lp1_setup(fv=fv)
    res = assess(opp, refs, fv)
    assert res.profile_points["faixa-psa10"] is None and res.signals["psa10_col"] is None
    assert res.profile_coverage == (4, 5) and res.profile == 90.0  # (20+12+20+20)/80
    assert "LP:faixa-psa10: n/d" in res.reasons
    assert res.fragility_points["psa10-iliquido"] is None
    assert "LP:psa10-iliquido: n/d" in res.reasons
    assert res.fragility == 0.0 and res.fragility_coverage == (9, 10)
    assert res.tier == "LP2*"  # seria LP1, mas insumo-chave ausente -> asterisco


def test_06_psa10_column_present_but_no_volume_is_never_lp1():
    fv = fair(sales_per_month={"RAW": 60.0})  # coluna existe, volume nao
    opp, refs, _ = lp1_setup(fv=fv)
    res = assess(opp, refs, fv)
    assert res.profile == 92.0 and res.fragility == 0.0
    assert res.profile_coverage == (5, 5) and res.fragility_coverage == (9, 10)
    assert res.signals["psa10_col"] == 300.0 and res.signals["psa10_sales_pm"] is None
    assert "LP:psa10-iliquido: n/d" in res.reasons
    assert res.tier == "LP2*"


# ── 7-9: coberturas minimas e teto 100 ───────────────────────────────────────────

def test_07_profile_needs_three_of_five_sources_else_nd():
    lt = _lt()
    assert lt.profile_score({"personagem": None, "raridade": None, "supply": None,
                             "faixa-psa10": 20, "tendencia": 20}) == (None, (2, 5))
    assert lt.profile_score({"personagem": 20, "raridade": None, "supply": None,
                             "faixa-psa10": 20, "tendencia": 20}) == (100.0, (3, 5))
    assert lt.profile_score({"personagem": 6, "raridade": 4, "supply": 3,
                             "faixa-psa10": None, "tendencia": None}) == (round(13 / 60 * 100, 1), (3, 5))
    c = card(pokemon_rank=9999, rarity="", year=None)  # sem rank, sem raridade, sem ano
    opp, refs, fv = lp1_setup(c)
    res = assess(opp, refs, fv)
    assert res.profile is None and res.profile_coverage == (2, 5)
    assert res.tier == "n/d"
    assert {"LP:personagem: n/d", "LP:raridade: n/d", "LP:supply: n/d"} <= set(res.reasons)
    assert res.fragility == 0.0  # a outra nota nao e afetada


def test_08_fragility_needs_three_of_ten_sources_empty_sum_is_not_zero():
    lt = _lt()
    pts = {flag: None for flag in lt.FRAGILITY_FLAGS}
    pts["tiragem"] = 0
    pts["vendedor-fraco"] = 0
    assert lt.fragility_score(pts) == (None, (2, 10))
    pts["preco-absoluto-alto"] = 0
    assert lt.fragility_score(pts) == (0.0, (3, 10))
    # via assess: anuncio quase sem dado (sem preco, sem set, sem colunas, sem refs)
    c = card(set_name="")
    listing = L("", None, url=EBAY_URL)
    opp = Opportunity(card=c, listing=listing, grade="PSA 10", fair_value=None,
                      gross_margin_pct=0.0, liquidity_per_month=0.0, liquidity_tier="D",
                      trend_delta=0.0, spread_grade9_pct=0, spread_psa10_pct=0)
    res = lt.assess(c, listing, opp, None, None, None, {}, today=TODAY)
    assert res.fragility is None and res.fragility_coverage == (2, 10)
    assert res.tier == "n/d"
    nd = {r for r in res.reasons if r.endswith(": n/d")}
    assert {"LP:ref-fragil: n/d", "LP:psa10-iliquido: n/d", "LP:ref-desalinhada: n/d",
            "LP:reprint-forte: n/d", "LP:preco-absoluto-alto: n/d", "LP:dispersao: n/d",
            "LP:ref-stale: n/d", "LP:concentracao: n/d"} <= nd


def test_09_fragility_sum_is_capped_at_100_and_class_is_lp4():
    lt = _lt()
    full = {"ref-fragil": 30, "psa10-iliquido": 30, "ref-desalinhada": 20,
            "reprint-forte": 15, "preco-absoluto-alto": 15, "vendedor-fraco": 15,
            "tiragem": 10, "dispersao": 10, "ref-stale": 10, "concentracao": 10}
    assert sum(full.values()) == 165
    assert lt.fragility_score(full) == (100.0, (10, 10))
    assert lt.classify(67.5, 100.0, (4, 5), True) == "LP4"
    # via assess (caminho legado) com TUDO disparando
    c = card(set_name="SV: Prismatic Evolutions", group="1", year=2020)
    opp, refs, fv = lp1_setup(
        c, title="Charizard 4/102 Prismatic Evolutions 1st Edition PSA 10", price=950.0,
        ref=REF(1500.0, n=2, liquidity="thin", window=365, what="PSA 10"),
        fv=fair(sales_per_month={"RAW": 60.0, "PSA 10": 0.5}),
        history={"PSA 10": sales(100.0, age=30, n=2) + sales(200.0, age=50, n=1)},
        tcg=5000.0, asks=(100.0, 110.0, 120.0),
        seller_feedback_score=10, seller_feedback_pct=90.0)
    assert any(f.startswith("REF DESALINHADA") for f in opp.risk_flags)
    assert any(f.startswith("REF GRADED < RAW TCG") for f in opp.risk_flags)
    res = assess(opp, refs, fv, n_same=4)
    assert res.fragility == 100.0 and res.fragility_coverage == (10, 10)
    assert all(v > 0 for v in res.fragility_points.values())
    assert res.tier == "LP4"
    assert res.profile == 67.5  # 20 + 6 + 8 + 20 sobre 4 componentes (sem tendencia)
    fired = {r.split("(")[0] for r in res.reasons if not r.endswith(": n/d")}
    assert fired >= {"LP:" + f for f in lt.FRAGILITY_FLAGS}
    assert "1st" in res.signals["printing_tokens"]
    assert res.signals["dispersion_pct"] == 100.0  # (200-100)/100


# ── 10-11: invariantes (podem nascer verdes) ──────────────────────────────────────

def test_10_assess_never_changes_verdict_metrics_flags_reasons_or_strategy():
    lt = _lt()
    # caminho legado
    opp, refs, fv = lp1_setup()
    before = _snapshot(opp)
    res = lt.assess(CARD, opp.listing, opp, fv, refs, 1, {}, today=TODAY)
    lt.annotate(opp, res)
    assert _snapshot(opp) == before
    assert opp.longterm_tier == res.tier and opp.longterm_reasons == res.reasons
    assert "LP:" not in " ".join(opp.risk_flags + opp.reasons)
    # caminho da politica (`strategy` preenchido)
    popp = slab_evaluate(PCARD, plisting(), config=pcfg(), refs=prefs(psales()))
    before = _snapshot(popp)
    res = lt.assess(PCARD, popp.listing, popp, fair(), prefs(psales()), 1, pcfg(), today=TODAY)
    lt.annotate(popp, res)
    assert _snapshot(popp) == before
    assert popp.strategy["psa_reference_original"] == 100
    assert "LP:" not in " ".join(popp.reasons)


def test_11_sort_key_unchanged_in_both_branches_with_longterm_fields_present():
    from tests.test_summary import row
    lp = dict(longterm_profile=95.0, longterm_fragility=5.0, longterm_coverage="5/5·10/10",
              longterm_reasons=[], longterm_signals={}, trend_12m_pct=30.0,
              trend_36m_pct=None, trend_source="sales_history")
    legacy = [
        row(card="A", roi_pct=10.0, discount_pct=9.0, spread_usd=1.0, pokemon_rank=5,
            longterm_tier="LP1", **lp),
        row(card="B", roi_pct=10.0, discount_pct=9.0, spread_usd=1.0, pokemon_rank=1,
            longterm_tier="LP4", **lp),
        row(card="C", roi_pct=30.0, discount_pct=5.0, spread_usd=0.5, pokemon_rank=9,
            longterm_tier="n/d", **lp),
    ]
    assert [r["card"] for r in report.sort_rows(legacy)] == ["C", "B", "A"]
    for r in legacy:
        stripped = {k: v for k, v in r.items()
                    if not k.startswith("longterm_") and not k.startswith("trend_")}
        assert report.sort_key(r) == report.sort_key(stripped)

    def prow(name, verdict, grade, roi, vault, tier):
        return {"card": name, "number": "1", "verdict": verdict, "grade": grade,
                "strategy": {"net_roi_percent": roi, "vault_confirmed": vault},
                "longterm_tier": tier, **lp}

    policy = [prow("A", "REJEITAR", "PSA 10", 50.0, True, "LP1"),
              prow("B", "APROVAR", "CGC 10 GEM", 90.0, True, "LP4"),
              prow("C", "APROVAR", "PSA 9", 5.0, False, "n/d"),
              prow("D", "APROVAR", "PSA 10", 20.0, False, "LP3"),
              prow("E", "REVISAR", "PSA 10", 99.0, True, "LP1")]
    # veredito -> PSA primeiro -> maior ROI liquido -> vault; a classe LP nao entra
    assert [r["card"] for r in report.sort_rows(policy)] == ["D", "C", "B", "E", "A"]
    for r in policy:
        stripped = {k: v for k, v in r.items()
                    if not k.startswith("longterm_") and not k.startswith("trend_")}
        assert report.sort_key(r) == report.sort_key(stripped)


# ── 12-13: serie mensal do PriceCharting e prioridade da tendencia ────────────────

def test_12_chart_data_parsed_from_fixture_zero_means_no_data():
    body = (FIX / "pc_product_charizard_base_4.html").read_text(encoding="utf-8")
    fv = pricecharting.parse_product_page(body, source_url=PC_URL)
    hist = fv.history
    assert set(hist) == {"used", "cib", "new", "graded", "boxonly", "manualonly"}
    assert len(hist["manualonly"]) == 70
    # ultimo `used` = 36625 centavos = coluna Ungraded US$366.25 da MESMA pagina
    assert hist["used"][-1] == (1788242400000, 36625)
    assert fv.prices["RAW"] == 366.25 == 36625 / 100
    # 0 na serie = "sem dado", nunca preco zero -> None
    assert hist["manualonly"][0] == (1606806000000, None)
    assert hist["manualonly"][1][1] is None and hist["manualonly"][2][1] == 980000
    assert all(v is None or v > 0 for series in hist.values() for _, v in series)
    assert pricecharting.parse_chart_data(body)["manualonly"] == hist["manualonly"]
    # pagina sem a serie -> {} (nunca inventa)
    body2 = (FIX / "pc_product_charizard_ex_151.html").read_text(encoding="utf-8")
    assert pricecharting.parse_product_page(body2, source_url="x").history == {}
    assert pricecharting.parse_chart_data(body2) == {}

    lt = _lt()
    manual = hist["manualonly"]
    # 12 m sobre a serie real (hoje = data da fixture): 2025-09-01 1216348 -> 2026-09-01 1315609
    assert round(lt.trend_from_history(manual, date(2026, 9, 3)), 2) == 8.16
    # 36 m so informativo: 2023-09-01 982071 -> 1315609
    assert round(lt.trend_from_history(manual, date(2026, 9, 3), months=36), 2) == 33.96
    # ponto de 12 m atras cai no inicio da serie (0 -> None) -> sem tendencia
    assert lt.trend_from_history(manual, date(2021, 12, 20)) is None
    # "ponto de 12 m" = ultimo ponto <= hoje - 365 d, tolerancia +-31 d; sem ponto -> None
    assert lt.trend_from_history([(_ms(2025, 7, 1), 100), (_ms(2026, 9, 1), 150)],
                                 date(2026, 9, 3)) is None
    assert lt.trend_from_history([(_ms(2025, 8, 15), 100), (_ms(2026, 9, 1), 150)],
                                 date(2026, 9, 3)) == 50.0
    assert lt.trend_from_history([], date(2026, 9, 3)) is None
    # via assess: serie presente mas sem os dois pontos > 0 -> 'chart_data:sem-dado'
    series = [(_ms(2020, 12, 1), None), (_ms(2021, 1, 1), None), (_ms(2021, 6, 1), 900),
              (_ms(2021, 12, 1), 1000)]
    fv2 = fair(history={"manualonly": series})
    opp, refs, _ = lp1_setup(fv=fv2, history={})
    res = lt.assess(CARD, opp.listing, opp, fv2, refs, 1, {}, today=date(2021, 12, 20))
    assert res.signals["trend_12m_pct"] is None and res.signals["trend_36m_pct"] is None
    assert res.signals["trend_source"] == "chart_data:sem-dado"
    assert res.profile_points["tendencia"] is None and "LP:tendencia: n/d" in res.reasons


def test_13_trend_prefers_exact_grade_sales_then_labelled_psa10_proxy():
    lt = _lt()
    series = ([(_ms(2024, m, 1), 1000) for m in range(9, 13)]
              + [(_ms(2025, m, 1), 1000) for m in range(1, 13)]
              + [(_ms(2026, m, 1), 1250) for m in range(1, 10)])  # +25% em 12 m
    fv = fair(history={"manualonly": series})
    # (ii) primeiro: >=3 vendas da nota EXATA em cada janela vencem a serie
    opp, refs, _ = lp1_setup(
        title="Charizard 4/102 Base Set PSA 9", price=2200.0, fv=fv,
        history={"PSA 9": sales(130.0, age=30) + sales(100.0, age=200)})
    res = lt.assess(CARD, opp.listing, opp, fv, refs, 1, {}, today=TODAY)
    assert res.signals["trend_source"] == "sales_history"
    assert res.signals["trend_12m_pct"] == 30.0 and res.profile_points["tendencia"] == 20
    assert refs.history_calls[0] == ("PSA 9", frozenset())
    # sem >=3 em cada janela -> serie PSA 10 como proxy ROTULADO para anuncio que nao e PSA 10
    opp2, refs2, _ = lp1_setup(
        title="Charizard 4/102 Base Set PSA 9", price=2200.0, fv=fv,
        history={"PSA 9": sales(130.0, age=30) + sales(100.0, age=200, n=2)})
    res2 = lt.assess(CARD, opp2.listing, opp2, fv, refs2, 1, {}, today=TODAY)
    assert res2.signals["trend_source"] == "chart_data:psa10-proxy"
    assert res2.signals["trend_12m_pct"] == 25.0 and res2.profile_points["tendencia"] == 20
    # anuncio PSA 10: a serie e da propria nota -> 'chart_data' (sem proxy)
    opp3, refs3, _ = lp1_setup(fv=fv, history={})
    res3 = lt.assess(CARD, opp3.listing, opp3, fv, refs3, 1, {}, today=TODAY)
    assert res3.signals["trend_source"] == "chart_data" and res3.signals["trend_12m_pct"] == 25.0
    # sem serie e sem vendas -> None, n/d
    opp4, refs4, fv4 = lp1_setup(history={})
    res4 = lt.assess(CARD, opp4.listing, opp4, fv4, refs4, 1, {}, today=TODAY)
    assert res4.signals["trend_source"] is None and res4.signals["trend_12m_pct"] is None
    assert res4.profile_points["tendencia"] is None and "LP:tendencia: n/d" in res4.reasons
    # o delta unico da coluna (trend_delta) NUNCA e a tendencia
    assert lt.trend_points(None) is None


# ── 14-16: coluna nos dois geradores, concentracao, serializacao ──────────────────

def test_14_column_before_links_in_both_generators_two_links_per_row():
    from tests.test_summary import payload, row
    # legado: `| ... | Status | Longo prazo | Links | Flags |`, `| Links | Flags |` adjacentes
    p = payload()
    p["rows"] = [
        row(longterm_tier="LP2", longterm_profile=64.0, longterm_fragility=35.0,
            longterm_coverage="4/5·8/10",
            longterm_reasons=["LP:ref-fragil(low)", "LP:tendencia: n/d"]),
        row(card="Blastoise", number="2", grade="PSA 10", listing_type="PSA 10",
            price=500.0, fair_value=700.0, discount_pct=28.57, roi_pct=40.0,
            spread_usd=200.0, margin_pct=40.0, verdict="REJEITADO",
            flags=["FRAUDE PROVAVEL: titulo anuncia PSA 10 mas condicao diz UNGRADED"],
            url="https://www.ebay.com/itm/444", item_id="444",
            longterm_tier="n/d", longterm_profile=None, longterm_fragility=35.0,
            longterm_coverage="2/5·8/10", longterm_reasons=["LP:personagem: n/d"]),
    ]
    md = ebay_summary.build_markdown(p)
    assert "| Tipo | Ref | Vend | Status | Longo prazo | Links | Flags |" in md
    assert "| Links | Flags |" in md
    assert "| LP2 64/35 (4/5·8/10) |" in md
    assert "LP:ref-fragil(low)" in md  # motivos LP: concatenados em Flags
    assert "| # | Carta | Tipo | eBay$ | Motivo | Links |" in md  # tabela dos rejeitados intacta
    rows = _table_rows(md)
    assert len(rows) == 2
    for line in rows:
        assert "[oferta](" in line and "[referência](" in line
    # JSON sem os campos (artefato antigo) -> celula n/d, nunca inventada
    p2 = payload()
    p2["rows"] = [row()]
    assert "| OPORTUNIDADE | n/d | [oferta](" in ebay_summary.build_markdown(p2)
    assert report.longterm_cell({"longterm_tier": "LP2", "longterm_profile": 64.0,
                                 "longterm_fragility": 35.0,
                                 "longterm_coverage": "4/5·8/10"}) == "LP2 64/35 (4/5·8/10)"
    assert report.longterm_cell({}) == "n/d"
    # politica (gerador vigente): `| ... | Decisão | Longo prazo | Links |` + "Motivos: ... LP:"
    popp = slab_evaluate(PCARD, plisting(), config=pcfg(), refs=prefs(psales()))
    prow = report.opportunity_row(popp)
    prow.update(longterm_tier="LP2*", longterm_profile=64.0, longterm_fragility=35.0,
                longterm_coverage="4/5·7/10",
                longterm_reasons=["LP:ref-desalinhada: n/d", "LP:ref-stale: n/d"])
    text = slab_report.render({"rows": [prow], "meta": None})
    header = next(ln for ln in text.splitlines() if ln.startswith("| Carta"))
    assert header.endswith("| Decisão | Longo prazo | Links |")
    line = next(ln for ln in text.splitlines() if ln.startswith("| ["))
    assert "| LP2* 64/35 (4/5·7/10) |" in line
    assert "[oferta](" in line and "[referência](" in line
    motivos = [ln for ln in text.splitlines() if ln.startswith("Motivos:")]
    assert motivos and "LP:ref-desalinhada: n/d" in motivos[0] and "LP:ref-stale: n/d" in motivos[0]
    # mesma saida pela ferramenta canonica (ebay_summary -> slab_report.render)
    md3 = ebay_summary.build_markdown(
        {"meta": {"config": {"slab_strategy": pcfg()["slab_strategy"]}}, "rows": [prow]})
    assert "| Decisão | Longo prazo | Links |" in md3 and "| LP2* 64/35 (4/5·7/10) |" in md3


def test_15_concentration_counts_same_card_and_grade_before_evaluate(monkeypatch):
    monkeypatch.setattr(scanner.tcg_reference, "get_tcg_reference", lambda c: None)
    from tests.test_scan_funnel import FakeEbay
    from tests.test_scan_funnel import L as LF
    refs = LTRefs(slab={"PSA 9": REF(3175.0), "PSA 10": REF(320.0, what="PSA 10")}, pc_url=PC_URL)
    fv = fair()
    prices = [2200.0, 2150.0, 2180.0, 2220.0]  # todos passam o gate (>= 30% de desconto)

    def run(n):
        batch = [LF("Charizard 4/102 Base Set PSA 9", p, str(i))
                 for i, p in enumerate(prices[:n], 1)]
        batch.append(LF("Charizard 4/102 Base Set PSA 10", 200.0, "9"))  # outra nota
        _, opps = scanner.scan_card(CARD, FakeEbay(batch), {"graded_only": True},
                                    log=lambda *a: None, stats=Counter(), refs=refs, fair=fv)
        return opps

    opps = run(4)
    psa9 = [o for o in opps if o.grade == "PSA 9"]
    assert len(psa9) == 4
    # flag na 1a linha (e em todas): a contagem e feita ANTES do loop de evaluate
    assert any(r.startswith("LP:concentracao") for r in psa9[0].longterm_reasons)
    assert all(any(r.startswith("LP:concentracao") for r in o.longterm_reasons) for o in psa9)
    assert all(o.longterm_signals["listings_same_grade"] == 4 for o in psa9)
    psa10 = [o for o in opps if o.grade == "PSA 10"]
    assert psa10 and psa10[0].longterm_signals["listings_same_grade"] == 1
    assert not any(r.startswith("LP:concentracao") for r in psa10[0].longterm_reasons)
    # com 3 anuncios da mesma nota: sem flag
    opps3 = [o for o in run(3) if o.grade == "PSA 9"]
    assert len(opps3) == 3
    assert all(o.longterm_signals["listings_same_grade"] == 3 for o in opps3)
    assert not any(r.startswith("LP:concentracao") for o in opps3 for r in o.longterm_reasons)


def test_16_opportunity_row_serializes_longterm_year_rarity_and_trend():
    lt = _lt()
    opp, refs, fv = lp1_setup()
    lt.annotate(opp, lt.assess(CARD, opp.listing, opp, fv, refs, 1, {}, today=TODAY))
    r = report.opportunity_row(opp)
    assert r["year"] == 1999 and r["rarity"] == "Rare Holo"
    assert r["longterm_tier"] == "LP1"
    assert r["longterm_profile"] == 92.0 and r["longterm_fragility"] == 0.0
    assert r["longterm_coverage"] == "5/5·10/10"
    assert r["longterm_reasons"] == []
    assert r["longterm_signals"]["trend_source"] == "sales_history"
    assert r["longterm_signals"]["ref_source"] == "ref_*"
    assert r["trend_12m_pct"] == 30.0 and r["trend_36m_pct"] is None
    assert r["trend_source"] == "sales_history"
    json.dumps(r, allow_nan=False)  # artefato JSON: nada de set/tupla/NaN
    # Opportunity nunca avaliada pela coluna: defaults, nada inventado
    from tests.test_report import O
    r0 = report.opportunity_row(O())
    assert r0["longterm_profile"] is None and r0["longterm_fragility"] is None
    assert r0["longterm_tier"] == "" and r0["longterm_coverage"] == ""
    assert r0["longterm_reasons"] == [] and r0["longterm_signals"] == {}
    assert r0["trend_12m_pct"] is None and r0["trend_36m_pct"] is None
    assert r0["trend_source"] == ""
    assert r0["year"] is None and r0["rarity"] == ""


# ── 17: caminho da politica (slab_strategy) ──────────────────────────────────────

def test_17_policy_path_reads_psa_evidence_and_marks_asks_and_stale_as_nd():
    lt = _lt()
    pcard = replace(PCARD, group="3", pokemon="Charizard", pokemon_rank=1,
                    rarity="Rare Holo", year=1999)
    rows = psales()
    rows[0]["price"] = 200  # dispersao 100% > 30: a politica ja rebaixa para REVISAR
    popp = slab_evaluate(pcard, plisting(), config=pcfg(), refs=prefs(rows))
    assert "PSA-precos-dispersos" in popp.reasons
    ev = popp.strategy["psa_evidence"]
    assert ev["n_used"] == 3 and ev["window_days"] == 180 and ev["dispersion_percent"] == 100.0
    fv = fair()
    # (a) ref_* preenchidos por slab_strategy.evaluate (:392-393) -> fonte `ref_*`
    res = lt.assess(pcard, popp.listing, popp, fv, prefs(rows), 1, pcfg(), today=TODAY)
    s = res.signals
    assert s["ref_source"] == "ref_*" and s["ref_n_sales"] == 3 and s["ref_window_days"] == 180
    assert res.fragility_points["ref-fragil"] == 0
    assert s["dispersion_source"] == "psa_evidence" and s["dispersion_pct"] == 100.0
    assert res.fragility_points["dispersao"] == 10
    assert any(r.startswith("LP:dispersao") for r in res.reasons)
    # asks = {} nesse caminho (decisao documentada): flag informativa em n/d, nada recomputado
    assert res.fragility_points["ref-desalinhada"] is None
    assert s["ask_ratio"] is None and s["ask_n"] is None
    assert "LP:ref-desalinhada: n/d" in res.reasons
    # cross-check com TCG raw nao existe nesse caminho -> n/d
    assert res.fragility_points["ref-stale"] is None and "LP:ref-stale: n/d" in res.reasons
    assert res.fragility == 10.0 and res.fragility_coverage == (8, 10)
    # perfil forte (90) e fragilidade baixa, mas insumo-chave ausente -> teto LP2*
    assert res.profile == 90.0 and res.profile_coverage == (4, 5)
    assert res.tier == "LP2*"
    # (b) ref_* vazios (Opportunity de slab_strategy.py:230-231) -> le `psa_evidence`
    popp.ref_n_sales = None
    popp.ref_window_days = None
    popp.ref_liquidity = ""
    res2 = lt.assess(pcard, popp.listing, popp, fv, prefs(rows), 1, pcfg(), today=TODAY)
    assert res2.signals["ref_source"] == "psa_evidence"
    assert res2.signals["ref_n_sales"] == 3 and res2.signals["ref_window_days"] == 180
    assert res2.signals["ref_liquidity"] == "ok" and res2.fragility_points["ref-fragil"] == 0
    # evidencia com 2 vendas -> thin (+30)
    popp2 = slab_evaluate(pcard, plisting(), config=pcfg(), refs=prefs(psales(n=2)))
    popp2.ref_n_sales = None
    popp2.ref_window_days = None
    res3 = lt.assess(pcard, popp2.listing, popp2, fv, prefs(psales(n=2)), 1, pcfg(), today=TODAY)
    assert res3.signals["ref_liquidity"] == "thin" and res3.fragility_points["ref-fragil"] == 30
    # sem evidencia nenhuma (identidade nao casou) -> n/d, nunca 0
    popp3 = slab_evaluate(pcard, plisting(title="Charizard 4/102 Other Set English PSA 10"),
                          config=pcfg(), refs=prefs(psales()))
    assert "psa_evidence" not in popp3.strategy and popp3.ref_n_sales is None
    res4 = lt.assess(pcard, popp3.listing, popp3, fv, prefs(psales()), 1, pcfg(), today=TODAY)
    assert res4.fragility_points["ref-fragil"] is None and res4.signals["ref_source"] is None
    assert "LP:ref-fragil: n/d" in res4.reasons
    assert res4.fragility_points["dispersao"] is None and "LP:dispersao: n/d" in res4.reasons


# ── extras (alem dos 18 listados): fronteiras, legenda, config, accessor ──────────

def test_e1_classify_boundaries_follow_the_declared_rule():
    lt = _lt()
    cov = (5, 5)
    assert lt.classify(None, 10.0, cov, True) == "n/d"
    assert lt.classify(80.0, None, cov, True) == "n/d"
    assert lt.classify(80.0, 70.5, cov, True) == "LP4"   # FRAGILIDADE > 70
    assert lt.classify(29.9, 0.0, cov, True) == "LP4"    # PERFIL < 30
    assert lt.classify(70.0, 30.0, cov, True) == "LP1"   # limites inclusivos
    assert lt.classify(70.0, 30.0, (4, 5), True) == "LP1"
    assert lt.classify(70.0, 30.0, (3, 5), True) == "LP2"   # cobertura < 4/5
    assert lt.classify(70.0, 30.0, cov, False) == "LP2*"    # insumo-chave ausente
    assert lt.classify(69.9, 30.0, cov, True) == "LP2"
    assert lt.classify(50.0, 50.0, cov, True) == "LP2"
    assert lt.classify(49.9, 50.0, cov, True) == "LP3"
    assert lt.classify(60.0, 50.1, cov, True) == "LP3"
    assert lt.classify(60.0, 50.1, cov, False) == "LP3"  # asterisco so no caso LP1->LP2


def test_e2_component_point_tables_are_the_declared_initial_calibration():
    lt = _lt()
    assert [lt.character_points(r) for r in (1, 10, 11, 25, 26, 50, 51, 100)] == \
        [20, 20, 16, 16, 12, 12, 6, 6]
    assert lt.character_points(101) is None and lt.character_points(9999) is None
    assert lt.character_points(None) is None and lt.character_points(0) is None
    assert [lt.supply_points(a, False) for a in (10, 9, 5, 4, 3, 2, 1, 0)] == \
        [20, 16, 16, 13, 13, 10, 6, 3]
    assert lt.supply_points(None, False) is None and lt.supply_points(-1, False) is None
    assert [lt.psa10_band_points(p) for p in (14.99, 15, 44.99, 45, 119.99, 120, 359.99, 360, 899.99, 900)] == \
        [4, 10, 10, 16, 16, 20, 20, 14, 14, 8]
    assert lt.psa10_band_points(None) is None and lt.psa10_band_points(0) is None
    assert [lt.trend_points(p) for p in (25, 24.9, 8, 7.9, -8, -8.1, -25, -24.9)] == \
        [20, 16, 16, 10, 10, 5, 2, 5]
    assert lt.trend_points(None) is None
    assert lt.PROFILE_COMPONENTS == ("personagem", "raridade", "supply", "faixa-psa10", "tendencia")
    assert lt.KEY_FRAGILITY_INPUTS == ("ref-fragil", "psa10-iliquido", "ref-desalinhada")
    assert "calibra" in lt.CALIBRATION_NOTE and "validada" in lt.CALIBRATION_NOTE
    assert "calibra" in (lt.__doc__ or "") and "validada" in (lt.__doc__ or "")
    # tendencia por vendas: mediana 0-180 d vs 180-365 d, so com >=3 em cada janela
    assert lt.trend_from_sales(sales(130.0, age=30) + sales(100.0, age=200), TODAY) == 30.0
    assert lt.trend_from_sales(sales(130.0, age=30) + sales(100.0, age=200, n=2), TODAY) is None
    assert lt.trend_from_sales(sales(130.0, age=30, n=2) + sales(100.0, age=200), TODAY) is None
    assert lt.trend_from_sales([], TODAY) is None


def test_e3_footer_explains_scores_class_asterisk_and_calibration_in_both_generators():
    from tests.test_summary import payload, row
    p = payload()
    p["rows"] = [row(longterm_tier="LP1", longterm_profile=90.0, longterm_fragility=10.0,
                     longterm_coverage="5/5·10/10", longterm_reasons=[]),
                 row(card="Mewtwo", number="10", pokemon="Mewtwo", pokemon_rank=6,
                     url="https://www.ebay.com/itm/666", item_id="666",
                     longterm_tier="LP2*", longterm_profile=75.0, longterm_fragility=20.0,
                     longterm_coverage="4/5·7/10", longterm_reasons=["LP:ref-desalinhada: n/d"]),
                 row(card="Gengar", number="94", pokemon="Gengar", pokemon_rank=3,
                     url="https://www.ebay.com/itm/555", item_id="555")]
    md = ebay_summary.build_markdown(p)
    for needle in ("PERFIL", "FRAGILIDADE DO DADO", "classe LP1-LP4", "calibração inicial",
                   "não é previsão", "recomendação", "ranking", "gate"):
        assert needle in md, needle
    assert "classe limitada por dado ausente" in md  # o asterisco explicado no rodape
    head = md.split("## ")[0]
    assert "- Longo prazo: 1 LP1 · 1 LP2 · 0 LP3 · 0 LP4 · 1 n/d" in head  # LP2* conta como LP2
    popp = slab_evaluate(PCARD, plisting(), config=pcfg(), refs=prefs(psales()))
    prow = report.opportunity_row(popp)
    prow.update(longterm_tier="LP2*", longterm_profile=64.0, longterm_fragility=35.0,
                longterm_coverage="4/5·7/10", longterm_reasons=["LP:ref-desalinhada: n/d"])
    text = slab_report.render({"rows": [prow], "meta": None})
    for needle in ("PERFIL", "FRAGILIDADE DO DADO", "classe LP1-LP4",
                   "classe limitada por dado ausente", "calibração inicial",
                   "não é previsão", "recomendação", "ranking", "gate"):
        assert needle in text, needle
    assert "Longo prazo: 0 LP1 · 1 LP2 · 0 LP3 · 0 LP4 · 0 n/d" in text


def test_e4_config_block_has_exactly_the_declared_keys_and_defaults_match():
    import yaml
    lt = _lt()
    wanted = {"enabled": True, "lp1_min_profile": 70, "lp1_max_fragility": 30,
              "lp2_min_profile": 50, "lp2_max_fragility": 50, "lp4_max_profile": 30,
              "lp4_min_fragility": 70, "min_profile_sources": 3, "min_fragility_sources": 3,
              "concentration_min_listings": 4}
    with open(Path(__file__).resolve().parents[1] / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    assert cfg["longterm"] == wanted  # so estas chaves, inteiros (percentuais inteiros)
    assert all(type(v) is int for k, v in cfg["longterm"].items() if k != "enabled")
    assert lt.DEFAULT_CONFIG == wanted
    # gate, politica, piso e ranking intactos: nada muda fora do bloco novo
    assert cfg["min_discount_percent"] == 30 and cfg["min_price_usd"] == 10.0
    assert cfg["slab_strategy"]["economics"]["min_discount_percent"] == 30
    assert cfg["slab_strategy"]["economics"]["gate_mode"] == "profit_or_discount"
    assert cfg["slab_strategy"]["version"] == "2026-09-05.4"


def test_e5_card_refs_sales_history_accessor_reuses_comparable_sales_read_only(monkeypatch):
    import datetime as dt
    from src import grading, pc_sales
    monkeypatch.setattr(pc_sales, "_today", lambda: dt.date(2026, 9, 3))
    body = (FIX / "pc_product_charizard_base_4.html").read_text(encoding="utf-8")
    refs = scanner.CardRefs(card(), body, PC_URL)
    hist = refs.sales_history(grading.Grade("PSA", 8.0))
    assert isinstance(hist, list) and len(hist) >= 3
    assert all({"date", "price", "title"} <= set(s) for s in hist)
    assert hist == pc_sales.comparable_sales(refs._sales, "PSA", 8.0, "", frozenset(), card=refs.card)
    # 1st Edition = outra cesta (mesma regra da referencia)
    first = refs.sales_history(grading.Grade("PSA", 8.0), frozenset({"1st"}))
    assert first != hist
    # e so leitura: a referencia (mediana) continua a mesma de antes
    before = refs.slab(grading.Grade("PSA", 8.0))
    refs.sales_history(grading.Grade("PSA", 8.0))
    assert refs.slab(grading.Grade("PSA", 8.0)) == before


def test_e6_disabled_config_leaves_fields_empty_and_seller_cut_is_the_documented_pair():
    lt = _lt()
    opp, refs, fv = lp1_setup(seller_feedback_score=49, seller_feedback_pct=99.9)
    res = assess(opp, refs, fv)
    # corte documentado no repo: `trusted_min_feedback: 50` / `trusted_min_feedback_pct: 98.0`
    # (config.yaml; slab_strategy 'historico-do-vendedor-insuficiente'); trust_score e so sinal
    assert res.fragility_points["vendedor-fraco"] == 15 and "LP:vendedor-fraco" in res.reasons
    opp2, refs2, fv2 = lp1_setup(seller_feedback_score=500, seller_feedback_pct=97.9)
    assert assess(opp2, refs2, fv2).fragility_points["vendedor-fraco"] == 15
    opp3, refs3, fv3 = lp1_setup(seller_feedback_score=50, seller_feedback_pct=98.0)
    assert assess(opp3, refs3, fv3).fragility_points["vendedor-fraco"] == 0
    # `enabled: false` no bloco `longterm` -> a coluna nao e calculada (campos com default)
    o = slab_evaluate(PCARD, plisting(), config=pcfg(), refs=prefs(psales()))
    assert lt.assess(PCARD, o.listing, o, fair(), prefs(psales()), 1,
                     {"longterm": {"enabled": False}}, today=TODAY) is None
    assert o.longterm_tier == "" and o.longterm_profile is None and o.longterm_reasons == []


# ── revisao do PR-C (2026-09-09): achados confirmados pelos dois revisores ───────
# Cada teste abaixo nasceu VERMELHO: reproduz o defeito relatado antes da correcao.


def test_r1_concentration_counts_only_listings_of_the_same_card(monkeypatch):
    """`LP:concentracao` = "mesma CARTA + mesma nota com >=4 anuncios no run"
    (docs/LONGO_PRAZO.md). A contagem feita ANTES do loop nao pode somar anuncios de
    OUTRAS cartas que a busca do eBay devolveu (eles sao descartados logo depois por
    `skip_no_match`) -- senao a tabela afirma "4 anuncios da mesma carta+nota" quando
    ha 1, e ainda soma +10 na FRAGILIDADE DO DADO."""
    monkeypatch.setattr(scanner.tcg_reference, "get_tcg_reference", lambda c: None)
    from tests.test_scan_funnel import FakeEbay
    from tests.test_scan_funnel import L as LF
    refs = LTRefs(slab={"PSA 9": REF(3175.0), "PSA 10": REF(320.0, what="PSA 10")},
                  pc_url=PC_URL)
    batch = [LF("Charizard 4/102 Base Set PSA 9", 2200.0, "1"),
             LF("Blastoise 2/102 Base Set PSA 9", 2100.0, "2"),
             LF("Venusaur 15/102 Base Set PSA 9", 2150.0, "3"),
             LF("Pikachu 58/102 Base Set PSA 9", 2180.0, "4")]
    stats = Counter()
    _, opps = scanner.scan_card(CARD, FakeEbay(batch), {"graded_only": True},
                                log=lambda *a: None, stats=stats, refs=refs, fair=fair())
    assert len(opps) == 1 and stats["skip_no_match"] == 3
    assert opps[0].longterm_signals["listings_same_grade"] == 1
    assert not any(r.startswith("LP:concentracao") for r in opps[0].longterm_reasons)


def _pc_body(rows):
    """Corpo minimo de pagina do PriceCharting que `pc_sales.parse_sales` le
    (`<div class="completed-auctions-*">` + `<tr id="<fonte>-<id>">`)."""
    trs = "".join(
        f'<tr id="{src}-{sid}"><td class="date">{day}</td>'
        f'<td class="title">{title}</td>'
        f'<td class="js-price">${price:,.2f}</td></tr>'
        for src, sid, day, title, price in rows)
    return f'<div class="completed-auctions-manual-only"><table>{trs}</table></div>'


def test_r2_policy_path_labels_b5_basket_as_its_own_not_the_reference_basket():
    """No caminho da POLITICA a cesta que alimenta B5 (tendencia) NAO e a cesta da
    referencia: `refs.sales_history` usa a nota DO ANUNCIO e filtros mais frouxos,
    enquanto a referencia vem de `slab_strategy.reference_sales` (nota PSA-equivalente,
    exige `source == 'ebay'`, id numerico unico, idioma, sem lote/oferta). O rotulo
    `trend_source` tem de dizer isso -- senao a doc promete "a mesma cesta da
    referencia" e o numero entregue vem de vendas que o motor vigente rejeitou."""
    lt = _lt()
    now = datetime.now(timezone.utc).date()

    def day(n):
        return (now - timedelta(days=n)).isoformat()

    title = "Charizard 4/102 Base Set English PSA 10"
    rows = ([("ebay", 1000 + i, day(30 + i), title, 300.0) for i in range(3)]
            + [("tcgplayer", 2000 + i, day(200 + i), title, 100.0) for i in range(3)])
    refs = scanner.CardRefs(PCARD, _pc_body(rows), PCARD.pc_url)
    popp = slab_evaluate(PCARD, plisting(), config=pcfg(), refs=refs)
    ev = popp.strategy["psa_evidence"]
    # a POLITICA descartou as 3 vendas TCGplayer da cesta da REFERENCIA
    assert ev["excluded_counts"]["origem-id-ou-duplicata"] == 3
    assert [s["sale_id"] for s in ev["sales"]] == ["1000", "1001", "1002"]
    res = lt.assess(PCARD, popp.listing, popp, fair(), refs, 1, pcfg(), today=now)
    # ... mas B5 leu as 6 (300 recentes vs 100 antigas = +200%): cesta PROPRIA
    assert res.signals["trend_12m_pct"] == 200.0
    assert res.signals["trend_source"] == "sales_history:cesta-propria"
    assert {s["sale_id"] for s in ev["sales"]}.isdisjoint({"2000", "2001", "2002"})
    # caminho LEGADO: ali a cesta E a mesma da referencia -> rotulo segue "sales_history"
    opp, lrefs, fv = lp1_setup()
    assert assess(opp, lrefs, fv).signals["trend_source"] == "sales_history"


def test_r3_thin_fragility_coverage_can_never_be_read_as_a_clean_lp1():
    """A FRAGILIDADE DO DADO e uma SOMA: insumo em n/d sai da soma, o que
    aritmeticamente e o mesmo que valer 0. Sem um piso, uma linha em que 7 dos 10
    testes NEM PUDERAM RODAR recebe a mesma nota 0 ("dado impecavel") e a mesma classe
    LP1 ("forte") de uma linha em que os 10 rodaram e passaram limpos -- e como LP4
    exige FRAGILIDADE > 70, dado ausente so podia MELHORAR a classe, nunca piorar."""
    lt = _lt()
    thin = {"ref-fragil": 0, "psa10-iliquido": 0, "ref-desalinhada": 0}
    full = {flag: 0 for flag in lt.FRAGILITY_FLAGS}
    # a soma nao distingue os dois casos (e por isso a COBERTURA vira o piso da classe)
    assert lt.fragility_score(thin) == (0.0, (3, 10))
    assert lt.fragility_score(full) == (0.0, (10, 10))
    assert lt.LP1_MIN_FRAGILITY_COVERAGE == 8   # mesma proporcao do piso do PERFIL (4/5)
    assert lt.classify(92.0, 0.0, (5, 5), True, fragility_coverage=(10, 10)) == "LP1"
    assert lt.classify(92.0, 0.0, (5, 5), True, fragility_coverage=(8, 10)) == "LP1"
    assert lt.classify(92.0, 0.0, (5, 5), True, fragility_coverage=(7, 10)) == "LP2*"
    assert lt.classify(92.0, 0.0, (5, 5), True, fragility_coverage=(3, 10)) == "LP2*"
    # cobertura desconhecida (chamada sem o argumento) segue a regra antiga
    assert lt.classify(92.0, 0.0, (5, 5), True) == "LP1"
    # via assess: insumos-chave presentes, mas 6 das 10 flags sem dado -> LP2*, nao LP1
    c = card(set_name="")                      # reprint-forte -> n/d
    listing = L("Charizard 4/102 Base Set PSA 10", None, url=EBAY_URL,
                seller_feedback_score=None, seller_feedback_pct=None)
    opp = Opportunity(card=c, listing=listing, grade="PSA 10", fair_value=320.0,
                      gross_margin_pct=0.0, liquidity_per_month=0.0, liquidity_tier="D",
                      trend_delta=0.0, spread_grade9_pct=0, spread_psa10_pct=0)
    opp.ref_liquidity, opp.ref_n_sales, opp.ref_window_days = "ok", 5, 180
    opp.median_ask = 240.0
    res = lt.assess(c, listing, opp, fair(), None, None, {}, today=TODAY)
    assert all(res.fragility_points[k] == 0 for k in lt.KEY_FRAGILITY_INPUTS)
    assert res.fragility == 0.0 and res.fragility_coverage == (4, 10)
    assert res.profile == 90.0 and res.profile_coverage == (4, 5)
    assert res.tier == "LP2*"   # "classe limitada por dado ausente", nao "forte"


def test_r5_zero_comparable_sales_is_labelled_sem_vendas_not_thin():
    """Linha SEM NENHUMA venda comparavel recebia o rotulo `thin`, que a regua do
    proprio repo (`src/pc_sales.py`) define como "1-2 vendas em 365 d". O operador lia
    `LP:ref-fragil(thin)` = "poucas vendas" onde nao ha venda nenhuma. Zero venda
    ganha rotulo proprio (`sem-vendas`), com os mesmos 30 pontos."""
    lt = _lt()
    assert lt._liquidity_from(0, 365) == "sem-vendas"
    assert lt._liquidity_from(1, 365) == "thin"
    assert lt._liquidity_from(2, 365) == "thin"
    assert lt._liquidity_from(3, 365) == "low"
    assert lt._liquidity_from(3, 180) == "ok"
    popp = slab_evaluate(PCARD, plisting(), config=pcfg(), refs=prefs())
    assert "sem-vendas-PSA-comparaveis" in popp.reasons
    assert popp.ref_n_sales == 0 and popp.ref_window_days == 365
    res = lt.assess(PCARD, popp.listing, popp, fair(), prefs(), 1, pcfg(), today=TODAY)
    assert res.signals["ref_liquidity"] == "sem-vendas"
    assert res.fragility_points["ref-fragil"] == 30
    assert "LP:ref-fragil(sem-vendas)" in res.reasons
    assert not any("thin" in r for r in res.reasons)


def test_r6_dispersion_flag_uses_the_exact_value_the_policy_compares():
    """O CHANGELOG promete que `dispersao` e "o MESMO valor que ja rebaixa uma linha
    para REVISAR ... uma definicao, um nome". A coluna comparava o valor ARREDONDADO
    (`dispersion_percent`, 2 casas) com o corte, enquanto a politica compara
    `dispersion_exact` como Decimal. Na fronteira os dois discordavam: com dispersao
    real 30,004% a politica rebaixa a linha e a coluna dizia que a dispersao estava
    sob controle."""
    lt = _lt()
    from decimal import Decimal
    from src.slab_strategy import amount
    # precos 42.55 / 50.06 / 57.57 -> (max-min)/mediana = 30,00399...% (corte = 30)
    assert amount(Decimal('30.00399520575309628445864962')) == 30.0   # arredonda PARA 30
    rows = psales(n=3)
    for sale, price in zip(rows, (42.55, 50.06, 57.57)):
        sale["price"] = price
    popp = slab_evaluate(PCARD, plisting(), config=pcfg(), refs=prefs(rows))
    ev = popp.strategy["psa_evidence"]
    assert ev["dispersion_percent"] == 30.0            # o que a celula mostra
    assert Decimal(ev["dispersion_exact"]) > Decimal("30")   # o que a politica compara
    assert "PSA-precos-dispersos" in popp.reasons      # a politica JA rebaixou a linha
    res = lt.assess(PCARD, popp.listing, popp, fair(), prefs(rows), 1, pcfg(), today=TODAY)
    assert res.signals["dispersion_pct"] == 30.0
    assert res.fragility_points["dispersao"] == 10     # a coluna tem de concordar
    assert any(r.startswith("LP:dispersao") for r in res.reasons)


def test_r7_nd_class_cell_is_read_as_nd_not_as_three_glued_nd():
    """Quando a CLASSE e `n/d` (PERFIL ou FRAGILIDADE abaixo do minimo de fontes),
    `longterm_tier` vale a string "n/d", que e verdadeira para o `if`: o guard
    `if not tier` nao pegava e a celula saia `n/d n/d/40 (2/5·8/10)` (ou `n/d n/d/n/d
    (...)`), contra o proprio docstring da funcao e contra docs/LONGO_PRAZO.md
    ("Coluna indisponivel = n/d, nunca 0"). A cobertura fica -- ela explica POR QUE a
    classe esta indisponivel --, mas as duas notas somem junto com a classe."""
    assert report.longterm_cell({"longterm_tier": "n/d", "longterm_profile": None,
                                 "longterm_fragility": 40.0,
                                 "longterm_coverage": "2/5·8/10"}) == "n/d (2/5·8/10)"
    assert report.longterm_cell({"longterm_tier": "n/d", "longterm_profile": None,
                                 "longterm_fragility": None,
                                 "longterm_coverage": "2/5·8/10"}) == "n/d (2/5·8/10)"
    assert report.longterm_cell({"longterm_tier": "n/d"}) == "n/d"
    assert report.longterm_cell({"longterm_tier": "", "longterm_coverage": ""}) == "n/d"
    assert report.longterm_cell({}) == "n/d"
    # a celula normal nao muda
    assert report.longterm_cell({"longterm_tier": "LP2", "longterm_profile": 64.0,
                                 "longterm_fragility": 35.0,
                                 "longterm_coverage": "4/5·8/10"}) == "LP2 64/35 (4/5·8/10)"


def test_r8_duplicate_timestamps_in_the_monthly_series_do_not_raise():
    """`trend_from_history` ordenava a serie pela TUPLA inteira. Como
    `parse_chart_data` deixa `None` onde o mes nao tem dado, dois pontos com o MESMO
    timestamp faziam o Python comparar `None` com um inteiro no segundo elemento e
    levantar TypeError. O `try/except` de `scanner._annotate_longterm` segurava a linha
    (a coluna virava n/d e o erro contava em `longterm_error`), mas a coluna se perdia
    a toa. Nunca reproduzi timestamp repetido numa pagina real -- a correcao e
    defensiva, e ordenar so pelo timestamp e o comportamento certo de qualquer jeito."""
    lt = _lt()
    assert lt.trend_from_history([(1000, None), (1000, 500)], TODAY) is None
    # com timestamp repetido e dado util, o ultimo ponto do mes vale (ordem preservada)
    series = [(_ms(2025, 8, 15), 100), (_ms(2025, 8, 15), 120), (_ms(2026, 9, 1), 150)]
    assert lt.trend_from_history(series, date(2026, 9, 3)) == 25.0
