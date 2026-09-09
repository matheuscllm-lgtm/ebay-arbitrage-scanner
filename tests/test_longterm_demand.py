"""Coluna "Longo prazo" -- oferta/demanda real e pisos configuraveis (prompt 2026-09-09,
fase (a)/(b)/(c)). Testes escritos ANTES do codigo: cada um nasce VERMELHO.

O que muda aqui, em linguagem simples:

- (a) PRECOS PEDIDOS ALIMENTAM A COLUNA TAMBEM NO CAMINHO DA POLITICA. O calculo da
  mediana dos anuncios (`opp.median_ask`) e da razao referencia/mediana passa a rodar
  nos DOIS caminhos; o EFEITO NO VEREDITO (rebaixar OPORTUNIDADE -> REVISAR, escrever
  `risk_flags`/`reasons`) continua so no caminho LEGADO. Com isso a flag
  `ref-desalinhada` deixa de ser n/d na politica -- e a classe deixa de travar em LP2*
  por falta desse insumo-chave. Veredito, Desconto%, ROI bruto%, `risk_flags`,
  `reasons`, `strategy` e a ordem do relatorio ficam IDENTICOS.

- (b) OS PISOS DE COBERTURA DA LP1 VIRAM CHAVE DE CONFIG (`lp1_min_profile_coverage`,
  `lp1_min_fragility_coverage`), com as constantes do modulo como valor padrao.

- (c) "MESES DE ESTOQUE" VIRA A 11a FLAG DE FRAGILIDADE (`estoque-alto`): anuncios
  ativos da mesma nota no run dividido pelas vendas PSA 10 por mes. E o unico sinal de
  OFERTA x DEMANDA real da coluna (o componente "supply" do PERFIL mede idade e
  reimpressao, nao estoque). Sem demanda medivel (< `supply_min_sales_pm`) ou sem a
  contagem de anuncios, a flag e n/d -- NUNCA 0.
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import yaml

from src import report, scanner
from src.slab_strategy import evaluate as slab_evaluate
from tests.test_longterm import _lt, assess, fair, lp1_setup
from tests.test_slab_strategy import CARD as PCARD
from tests.test_slab_strategy import listing as plisting
from tests.test_slab_strategy import refs as prefs
from tests.test_slab_strategy import sales as psales

ROOT = Path(__file__).resolve().parents[1]


def pol_cfg():
    """Config do caminho da POLITICA montada direto do `config.yaml`, SEM passar por
    `slab_strategy.policy_config` -- a validacao do repo (`src/policy_validation.py`,
    fora do escopo deste PR) ainda nao aceita o `gate_mode` novo do config.yaml, e
    esta suite nao pode depender disso. Mesmos ajustes de `tests/test_slab_strategy.cfg`."""
    with (ROOT / "config.yaml").open(encoding="utf-8") as f:
        defaults = yaml.safe_load(f)
    cfg = {"min_discount_percent": 20, "suspicious_margin_percent": 60,
           "graded_only": True, "graded_allow": defaults["graded_allow"],
           "slab_strategy": deepcopy(defaults["slab_strategy"]),
           "longterm": deepcopy(defaults["longterm"])}
    p = cfg["slab_strategy"]
    p["costs"].update(coverage_confirmed=True, comc_processing_usd=1, comc_storage_usd=0,
                      selling_fee_percent=5, cashout_fee_percent=3,
                      fee_basis="sale_then_cashout")
    p["economics"].update(gate_mode="all_minima", min_profit_usd=0,
                          min_net_margin_percent=0, min_net_roi_percent=0)
    p["evidence"]["max_dispersion_percent"] = 30
    return cfg


def _fake_ebay(batch):
    return SimpleNamespace(calls=0, search=lambda *a, **k: list(batch))


def _policy_scan(batch, rows=None, cfg=None):
    """`scan_card` no caminho da POLITICA (config com `slab_strategy`)."""
    rows = psales() if rows is None else rows
    cfg = cfg or pol_cfg()
    _, opps = scanner.scan_card(PCARD, _fake_ebay(batch), cfg, log=lambda *a: None,
                                stats=Counter(), refs=prefs(rows), fair=fair())
    return opps


# ── (c) meses de estoque: a 11a flag de FRAGILIDADE ──────────────────────────────

def test_c1_months_of_supply_is_listings_of_the_same_grade_over_psa10_sales_per_month():
    """`estoque-alto` = anuncios ativos da mesma nota no run / vendas PSA 10 por mes.
    35 anuncios contra 1 venda/mes = 35 meses de estoque: oferta parada em cima de
    demanda fina -- 20 pontos de FRAGILIDADE e o motivo com o valor (`LP:estoque-alto(35m)`)."""
    lt = _lt()
    fv = fair(sales_per_month={"RAW": 60.0, "PSA 10": 1.0})
    opp, refs, _ = lp1_setup(fv=fv)
    res = assess(opp, refs, fv, n_same=35)
    assert res.signals["months_of_supply"] == 35.0
    assert res.fragility_points["estoque-alto"] == 20
    assert "LP:estoque-alto(35m)" in res.reasons
    # a nota do PERFIL nao muda: `estoque-alto` e FRAGILIDADE DO DADO, nao perfil
    assert res.profile == 92.0
    assert "estoque-alto" not in lt.PROFILE_COMPONENTS


def test_c2_three_point_bands_follow_the_declared_config_thresholds():
    """>= 24 meses -> 20 · >= 12 -> 10 · abaixo -> 0. Fronteiras inclusivas."""
    lt = _lt()
    assert [lt.stock_points(m) for m in (24, 23.9, 12, 11.9, 0)] == [20, 10, 10, 0, 0]
    assert lt.stock_points(None) is None
    assert lt.months_of_supply(35, 1.0) == 35.0
    assert lt.months_of_supply(6, 4.0) == 1.5
    assert lt.months_of_supply(0, 4.0) == 0.0     # zero anuncio e um NUMERO, nao n/d
    # cortes vindos do config (nao ha 24/12/0,05 escrito na mao no chamador)
    assert lt.stock_points(13, high=13, mid=5) == 20
    assert lt.stock_points(6, high=13, mid=5) == 10


def test_c3_missing_inputs_are_nd_and_nd_never_becomes_zero():
    """Sem vendas PSA 10 medidas (ou com demanda fina demais para a divisao) e sem a
    contagem de anuncios, a flag e n/d -- nunca 0, que significaria "estoque saudavel"."""
    lt = _lt()
    assert lt.months_of_supply(35, None) is None      # sem demanda
    assert lt.months_of_supply(None, 1.0) is None     # sem contagem de anuncios
    assert lt.months_of_supply(35, 0.0) is None       # divisao por zero jamais
    assert lt.months_of_supply(35, 0.04) is None      # abaixo de supply_min_sales_pm
    assert lt.months_of_supply(35, 0.05) == 700.0     # no corte, ja calcula
    # via assess: coluna PSA 10 sem volume -> n/d (e a flag entra na lista de ausencias)
    fv = fair(sales_per_month={"RAW": 60.0})
    opp, refs, _ = lp1_setup(fv=fv)
    res = assess(opp, refs, fv, n_same=35)
    assert res.signals["months_of_supply"] is None
    assert res.fragility_points["estoque-alto"] is None
    assert "LP:estoque-alto: n/d" in res.reasons
    assert not any(r.startswith("LP:estoque-alto(") for r in res.reasons)
    # sem a contagem de anuncios do run -> n/d tambem
    fv2 = fair(sales_per_month={"RAW": 60.0, "PSA 10": 1.0})
    opp2, refs2, _ = lp1_setup(fv=fv2)
    res2 = assess(opp2, refs2, fv2, n_same=None)
    assert res2.signals["months_of_supply"] is None
    assert res2.fragility_points["estoque-alto"] is None


def test_c4_flag_list_grows_to_eleven_and_key_inputs_stay_the_same_three():
    lt = _lt()
    assert len(lt.FRAGILITY_FLAGS) == 11
    assert "estoque-alto" in lt.FRAGILITY_FLAGS
    assert lt.KEY_FRAGILITY_INPUTS == ("ref-fragil", "psa10-iliquido", "ref-desalinhada")
    assert "months_of_supply" in lt.SIGNAL_KEYS
    # a soma continua com teto 100 mesmo com a flag nova
    full = {flag: 30 for flag in lt.FRAGILITY_FLAGS}
    assert lt.fragility_score(full) == (100.0, (11, 11))


def test_c5_coverage_denominator_comes_from_the_flag_list_never_from_a_hardcoded_ten():
    """A cobertura da FRAGILIDADE e `k/len(FRAGILITY_FLAGS)`. Um `10` escrito na mao
    passaria a mentir na celula, no JSON e no relatorio de calibracao."""
    import longterm_validate
    lt = _lt()
    n = len(lt.FRAGILITY_FLAGS)
    assert lt.fragility_score({flag: 0 for flag in lt.FRAGILITY_FLAGS})[1] == (n, n)
    assert lt.fragility_score({})[1] == (0, n)
    assert lt.coverage_text((5, 5), (n, n)) == f"5/5·{n}/{n}"
    # LP1 com tudo medido e limpo continua LP1 (o piso novo nao fecha a porta)
    opp, refs, fv = lp1_setup()
    res = assess(opp, refs, fv, n_same=1)
    assert res.fragility_coverage == (n, n) and res.fragility == 0.0
    assert res.tier == "LP1"
    assert res.signals["months_of_supply"] == round(1 / 5.0, 1)
    # texto do relatorio de calibracao: nunca "/10" fixo
    rows = [{"card": "Charizard", "number": "4", "grade": "PSA 10", "price": 100.0,
             "fair_value": 200.0, "longterm_tier": "LP1", "longterm_profile": 90.0,
             "longterm_fragility": 10.0, "longterm_coverage": f"4/5·{n}/{n}",
             "longterm_reasons": [], "longterm_signals": {}, "strategy": {}}]
    text = longterm_validate.calibration_report(rows, min_keys=1)
    assert f"fragilidade {float(n):.1f}/{n}" in text


# ── (b) pisos de cobertura da LP1 vindos do config ───────────────────────────────

def test_b1_lp1_coverage_floors_are_config_keys_with_the_module_constants_as_default():
    lt = _lt()
    n = len(lt.FRAGILITY_FLAGS)
    assert lt.LP1_MIN_PROFILE_COVERAGE == 4
    assert lt.LP1_MIN_FRAGILITY_COVERAGE == 9      # ~80% de 11 flags
    assert lt.DEFAULT_CONFIG["lp1_min_profile_coverage"] == lt.LP1_MIN_PROFILE_COVERAGE
    assert lt.DEFAULT_CONFIG["lp1_min_fragility_coverage"] == lt.LP1_MIN_FRAGILITY_COVERAGE
    # sem cfg: os pisos sao os do modulo
    assert lt.classify(92.0, 0.0, (5, 5), True, fragility_coverage=(9, n)) == "LP1"
    assert lt.classify(92.0, 0.0, (5, 5), True, fragility_coverage=(8, n)) == "LP2*"
    assert lt.classify(92.0, 0.0, (4, 5), True, fragility_coverage=(9, n)) == "LP1"
    assert lt.classify(92.0, 0.0, (3, 5), True, fragility_coverage=(9, n)) == "LP2"
    # com cfg: a chave manda (e um piso mais frouxo libera LP1)
    loose = {"lp1_min_fragility_coverage": 3, "lp1_min_profile_coverage": 3}
    assert lt.classify(92.0, 0.0, (3, 5), True, loose, fragility_coverage=(3, n)) == "LP1"
    strict = {"lp1_min_fragility_coverage": n, "lp1_min_profile_coverage": 5}
    assert lt.classify(92.0, 0.0, (5, 5), True, strict, fragility_coverage=(10, n)) == "LP2*"
    assert lt.classify(92.0, 0.0, (4, 5), True, strict, fragility_coverage=(n, n)) == "LP2"


def test_b2_config_yaml_carries_the_five_new_keys_and_defaults_mirror_them():
    lt = _lt()
    with (ROOT / "config.yaml").open(encoding="utf-8") as f:
        block = yaml.safe_load(f)["longterm"]
    for key in ("lp1_min_profile_coverage", "lp1_min_fragility_coverage",
                "supply_months_high", "supply_months_mid", "supply_min_sales_pm"):
        assert key in block, key
        assert lt.DEFAULT_CONFIG[key] == block[key], key
    assert block["lp1_min_profile_coverage"] == 4 and block["lp1_min_fragility_coverage"] == 9
    assert block["supply_months_high"] == 24 and block["supply_months_mid"] == 12
    assert block["supply_min_sales_pm"] == 0.05
    assert lt.DEFAULT_CONFIG == dict(lt.DEFAULT_CONFIG, **block)


def test_b3_assess_reads_the_floors_and_the_supply_thresholds_from_the_run_config():
    """Os cortes chegam pelo `cfg` do run, nao por constante fixa no meio de `assess`."""
    lt = _lt()
    fv = fair(sales_per_month={"RAW": 60.0, "PSA 10": 1.0})
    opp, refs, _ = lp1_setup(fv=fv)
    tight = {"longterm": {"supply_months_high": 3, "supply_months_mid": 2}}
    assert assess(opp, refs, fv, n_same=4, cfg=tight).fragility_points["estoque-alto"] == 20
    loose = {"longterm": {"supply_months_high": 100, "supply_months_mid": 50}}
    assert assess(opp, refs, fv, n_same=4, cfg=loose).fragility_points["estoque-alto"] == 0
    blind = {"longterm": {"supply_min_sales_pm": 5.0}}
    res = assess(opp, refs, fv, n_same=4, cfg=blind)
    assert res.fragility_points["estoque-alto"] is None
    assert res.signals["months_of_supply"] is None


# ── (a) precos pedidos alimentam a coluna tambem no caminho da politica ──────────

def test_a1_median_ask_calculation_is_split_from_the_verdict_effect():
    """`_annotate_median_ask` faz SO a conta (mediana + razao) e devolve a razao;
    `_annotate_ref_alignment` continua fazendo a conta E o efeito no veredito."""
    opp, refs, fv = lp1_setup(asks=None)
    assert opp.verdict == "OPORTUNIDADE" and opp.median_ask == 0.0
    ratio = scanner._annotate_median_ask(opp, {opp.grade: [100.0, 100.0, 100.0]})
    assert opp.median_ask == 100.0
    assert round(ratio, 4) == round(opp.fair_value / 100.0, 4)
    # a conta sozinha NUNCA rebaixa nem escreve flag/motivo, mesmo desalinhada (3.2x)
    assert opp.verdict == "OPORTUNIDADE"
    assert not any(f.startswith("REF DESALINHADA") for f in opp.risk_flags)
    assert not any(r.startswith("ref-desalinhada") for r in opp.reasons)
    # o legado (conta + efeito) segue igual
    opp2, _, _ = lp1_setup(asks=None)
    scanner._annotate_ref_alignment(opp2, {opp2.grade: [100.0, 100.0, 100.0]})
    assert opp2.median_ask == 100.0 and opp2.verdict == "REVISAR"
    assert any(f.startswith("REF DESALINHADA") for f in opp2.risk_flags)
    assert opp2.reasons == ["ref-desalinhada(3.2x)"]
    # amostra pequena demais: nem mediana, nem razao
    opp3, _, _ = lp1_setup(asks=None)
    assert scanner._annotate_median_ask(opp3, {opp3.grade: [100.0, 100.0]}) is None
    assert opp3.median_ask == 0.0


def test_a2_ref_desalinhada_stops_being_nd_on_the_policy_path():
    """Com os precos pedidos calculados tambem na politica, o insumo-chave
    `ref-desalinhada` sai de n/d: a classe deixa de travar em LP2* por falta dele."""
    lt = _lt()
    # referencia 100 (3 vendas PSA 10 a 100) contra mediana dos anuncios 80 -> 1.25x: alinhada
    opps = _policy_scan([plisting(item_id=str(i), price=p)
                         for i, p in enumerate((75, 80, 85), 1)])
    assert len(opps) == 3
    assert all(o.median_ask == 80.0 for o in opps)
    for o in opps:
        assert o.longterm_signals["ask_ratio"] == 1.25
        assert "LP:ref-desalinhada: n/d" not in o.longterm_reasons
        assert not any(r.startswith("LP:ref-desalinhada") for r in o.longterm_reasons)
    # anuncios muito abaixo da referencia -> razao 3.33x: DESALINHADA (so informa)
    low = _policy_scan([plisting(item_id=str(i), price=30) for i in (1, 2, 3)])
    assert all(o.median_ask == 30.0 for o in low)
    for o in low:
        assert o.longterm_signals["ask_ratio"] == 3.33
        assert "LP:ref-desalinhada(3.33x)" in o.longterm_reasons
        # informativa: nada de flag de risco nem rebaixamento vindo daqui
        assert not any("REF DESALINHADA" in f for f in o.risk_flags)
        assert not any(r.startswith("ref-desalinhada") for r in o.reasons)
    # menos de 3 anuncios limpos: sem mediana -> a flag volta a ser n/d, nunca 0
    thin = _policy_scan([plisting(item_id="1", price=75), plisting(item_id="2", price=80)])
    assert all(o.median_ask == 0.0 for o in thin)
    assert all(o.longterm_signals["ask_ratio"] is None for o in thin)
    assert all("LP:ref-desalinhada: n/d" in o.longterm_reasons for o in thin)


def test_a3_policy_verdict_metrics_flags_reasons_strategy_and_order_are_identical():
    """INVARIANTE do item (a) -- nasce VERDE de proposito: prova que ligar os precos
    pedidos na politica nao move NADA do que decide. Referencia = o motor da politica
    chamado direto, que nunca ve `asks`."""
    cfg = pol_cfg()
    rows = psales()
    batch = [plisting(item_id=str(i), price=p) for i, p in enumerate((75, 80, 85), 1)]
    opps = _policy_scan(batch, rows=rows, cfg=cfg)
    expected = [slab_evaluate(PCARD, item, config=cfg, refs=prefs(rows)) for item in batch]
    assert len(opps) == len(expected) == 3
    for got, exp in zip(opps, expected):
        assert got.verdict == exp.verdict
        assert got.discount_pct == exp.discount_pct
        assert got.gross_margin_pct == exp.gross_margin_pct
        assert got.spread_usd == exp.spread_usd
        assert got.fair_value == exp.fair_value
        assert got.risk_flags == exp.risk_flags
        assert got.reasons == exp.reasons
        assert got.strategy == exp.strategy
        assert "LP:" not in " ".join(got.risk_flags + got.reasons)
    rows_got = report.sort_rows([report.opportunity_row(o) for o in opps])
    rows_exp = report.sort_rows([report.opportunity_row(o) for o in expected])
    assert [r["item_id"] for r in rows_got] == [r["item_id"] for r in rows_exp]
    # o que MUDA: so a mediana informativa e os campos `longterm_*`
    assert all(o.median_ask == 80.0 for o in opps)
    assert all(o.median_ask == 0.0 for o in expected)
    assert all(o.longterm_tier and not e.longterm_tier for o, e in zip(opps, expected))


def test_a4_ratio_cutoffs_of_the_column_mirror_the_scanner_thresholds():
    """A coluna compara a razao com os MESMOS cortes do scanner. Espelhados no modulo
    (`longterm` nao pode importar `scanner`: e `scanner` que importa `longterm`), e
    este teste existe para que os dois nunca divirjam em silencio."""
    lt = _lt()
    assert lt._REF_HIGH_RATIO == scanner.REF_HIGH_RATIO
    assert lt._REF_LOW_RATIO == scanner.REF_LOW_RATIO
    assert lt._REF_MIN_SAMPLES == scanner.REF_MIN_SAMPLES


def test_a6_policy_line_without_reference_still_gets_the_median_but_never_a_ratio():
    """Regressao: no caminho da POLITICA a Opportunity nasce com `fair_value = None`
    sempre que nao ha vendas PSA comparaveis (veredito REVISAR). Dividir a referencia
    ausente pela mediana derrubava a CARTA INTEIRA com TypeError; inventar um numero ali
    seria pior. A mediana dos anuncios e um fato e fica gravada; a razao e n/d."""
    opps = _policy_scan([plisting(item_id=str(i), price=p)
                         for i, p in enumerate((75, 80, 85), 1)], rows=[])
    assert len(opps) == 3
    assert all(o.fair_value is None and o.verdict == "REVISAR" for o in opps)
    assert all(o.median_ask == 80.0 for o in opps)          # o fato continua la
    for o in opps:
        assert o.longterm_signals["ask_ratio"] is None      # a razao, nao
        assert o.longterm_signals["months_of_supply"] is not None
        assert "LP:ref-desalinhada: n/d" in o.longterm_reasons
    # e a funcao devolve None em vez de estourar
    assert scanner._annotate_median_ask(opps[0], {opps[0].grade: [10.0, 10.0, 10.0]}) is None
    assert opps[0].median_ask == 10.0


def test_a5_legacy_path_keeps_the_downgrade_and_the_flag_text():
    """O caminho LEGADO nao muda: mediana + razao + `risk_flags`/`reasons` +
    rebaixamento de OPORTUNIDADE para REVISAR."""
    lt = _lt()
    opp, refs, fv = lp1_setup(asks=(100.0, 100.0, 100.0))
    assert opp.verdict == "REVISAR"
    assert opp.reasons == ["ref-desalinhada(3.2x)"]
    res = assess(opp, refs, fv)
    assert res.fragility_points["ref-desalinhada"] == 20
    assert res.signals["ask_ratio"] == 3.2
    assert "LP:ref-desalinhada(3.2x)" in res.reasons
    # alinhado: 0 pontos, sem motivo, veredito intacto
    opp2, refs2, fv2 = lp1_setup()
    assert opp2.verdict == "OPORTUNIDADE"
    res2 = assess(opp2, refs2, fv2)
    assert res2.fragility_points["ref-desalinhada"] == 0
    assert not any(r.startswith("LP:ref-desalinhada") for r in res2.reasons)
