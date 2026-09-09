"""Correcoes da revisao em contexto limpo do PR `feat/margem-bruta-e-demanda`.

Oito achados; cada um nasce vermelho aqui antes da correcao. Em linguagem simples:

1. A ORDEM da tabela usava uma metrica que o gate novo deixou quase sempre indisponivel.
2. O "teto de comparacao" impresso por carta prometia um preco que o gate rejeita.
3. `estoque-alto` contava DE NOVO os mesmos dois numeros que outras duas flags contam.
4. Meses de estoque dividia anuncios de uma nota pelas vendas de OUTRA nota.
5. O piso da LP1 subiu de 8 para 9 e rebaixava linhas sem nenhuma evidencia nova.
6. A checagem de margem absurda (referencia errada) morria justo no modo em que a
   margem e o unico criterio.
7. A guarda de drift nova quebrava com qualquer fracao entre parenteses.
8. `--min-gross-margin` era aplicada em modo que a ignora, sem avisar.
"""
from copy import deepcopy

import pytest

from src import longterm, report
from src.slab_strategy import evaluate
from tests.test_longterm import assess, fair, lp1_setup
from tests.test_longterm_demand import pol_cfg
from tests.test_slab_strategy import CARD, cfg, refs, sales
from tests.test_slab_strategy import listing as plisting


def gm_cfg(threshold=43):
    c = cfg()
    c['slab_strategy']['economics'] = dict(c['slab_strategy']['economics'],
                                           gate_mode='gross_margin',
                                           min_gross_margin_percent=threshold)
    return c


def test_1_policy_ranking_uses_the_metric_that_decides():
    """`net_roi_percent` so existe quando o modelo de CUSTO esta completo, o que quase
    nunca acontece. Ordenar por ele deixa a tabela em ordem de insercao, e uma linha de
    44% pode sair acima de uma de 300% -- na tabela colada VERBATIM para o operador."""
    def row(margin):
        return {'verdict': 'APROVAR', 'grade': 'PSA 10', 'margin_pct': margin,
                'strategy': {'net_roi_percent': None, 'vault_confirmed': None,
                             'economic_gate': {'mode': 'gross_margin',
                                               'gross_margin_percent': margin}}}
    assert report.sort_key(row(300.0)) < report.sort_key(row(44.0))


def test_1b_ranking_falls_back_to_net_roi_when_there_is_no_gross_margin():
    def row(roi):
        return {'verdict': 'APROVAR', 'grade': 'PSA 10',
                'strategy': {'net_roi_percent': roi, 'vault_confirmed': None}}
    assert report.sort_key(row(80.0)) < report.sort_key(row(10.0))


def test_2_comparison_cap_is_the_highest_price_the_gate_actually_approves():
    """Com referencia 100 e limiar 43%, o gate so aprova abaixo de 100/1,43 = 69,93.
    Imprimir 100,00 como "teto" promete um preco que sai REJEITAR."""
    o = evaluate(CARD, plisting(price=50), config=gm_cfg(), refs=refs(sales()))
    cap = o.strategy['comparison_cap']
    comparison = o.strategy['comparison_reference']
    assert cap is not None and comparison is not None
    assert cap == pytest.approx(comparison / 1.43, rel=1e-6)


def test_2b_the_printed_cap_is_a_price_the_gate_really_approves():
    """O teto publicado nao pode prometer nem um centavo a mais do que o gate aceita:
    exatamente no teto tem de passar, e um centavo acima tem de reprovar."""
    cap = evaluate(CARD, plisting(price=50), config=gm_cfg(),
                   refs=refs(sales())).strategy['comparison_cap']
    no_teto = evaluate(CARD, plisting(price=cap), config=gm_cfg(), refs=refs(sales()))
    acima = evaluate(CARD, plisting(price=cap + 0.01), config=gm_cfg(), refs=refs(sales()))
    assert 'abaixo-da-margem-bruta-minima' not in (no_teto.strategy['rejection_reasons'] or [])
    assert 'abaixo-da-margem-bruta-minima' in (acima.strategy['rejection_reasons'] or [])


def test_4_months_of_supply_is_nd_for_grades_whose_demand_was_never_measured():
    """O PriceCharting so traz volume por certificadora na PSA 10. As outras notas caem
    no balde generico `GRADE 9`, que MISTURA certificadoras e que este repo proibe
    rotular como PSA. Dividir anuncios PSA 9 por vendas PSA 10 nao e meses de estoque
    de coisa nenhuma."""
    fv = fair(sales_per_month={'PSA 10': 0.5})
    o, refs, fv = lp1_setup(title='Charizard 4/102 Base Set PSA 9', fv=fv)
    r = assess(o, refs, fv, n_same=12, cfg=pol_cfg())
    assert r.signals['months_of_supply'] is None


def test_4b_months_of_supply_still_works_on_psa10():
    fv = fair(sales_per_month={'PSA 10': 0.5})
    o, refs, fv = lp1_setup(fv=fv)
    r = assess(o, refs, fv, n_same=12, cfg=pol_cfg())
    assert r.signals['months_of_supply'] == 24.0


def test_3_the_three_flags_that_share_inputs_do_not_triple_count():
    """`psa10-iliquido` (vendas/mes), `concentracao` (numero de anuncios) e
    `estoque-alto` (a divisao dos dois) leem os MESMOS dois numeros. Somados cheios,
    uma observacao vira 60 pontos e joga a linha para LP4 com a mesma evidencia que
    dava LP2 na main."""
    pontos = {f: 0 for f in longterm.FRAGILITY_FLAGS}
    pontos.update({'psa10-iliquido': 30, 'concentracao': 10, 'estoque-alto': 20})
    score, cobertura = longterm.fragility_score(pontos)
    assert score == longterm.SHARED_SUPPLY_CAP, (
        f'familia somou {score}; teto e {longterm.SHARED_SUPPLY_CAP}')
    # O teto NAO pode mexer na cobertura: as tres flags rodaram, e isso continua fato.
    assert cobertura == (len(longterm.FRAGILITY_FLAGS), len(longterm.FRAGILITY_FLAGS))


def test_3b_flags_outside_the_family_still_add_normally():
    pontos = {f: None for f in longterm.FRAGILITY_FLAGS}
    pontos.update({'psa10-iliquido': 30, 'concentracao': 10, 'estoque-alto': 20,
                   'ref-fragil': 30, 'tiragem': 10})
    score, _ = longterm.fragility_score(pontos)
    assert score == longterm.SHARED_SUPPLY_CAP + 40


def test_5_lp1_fragility_floor_stays_at_the_absolute_count_it_had():
    """Subir de 8 para 9 rebaixa para `LP2*` linhas que antes davam LP1, sem nenhuma
    evidencia nova -- so porque entrou uma 11a flag que e a MENOS disponivel."""
    assert longterm.DEFAULT_CONFIG['lp1_min_fragility_coverage'] == 8


def test_6_absurd_gross_margin_still_asks_for_an_identity_check():
    """O gate `gross_margin` so tem piso. Margem de centenas de por cento e assinatura
    classica de referencia errada ou carta trocada, e chegava a APROVAR sem ressalva.
    A checagem existe no config (`suspicious_margin_percent: 60`) e estava inerte.
    Ela REVISA, nunca rejeita."""
    o = evaluate(CARD, plisting(price=1), config=gm_cfg(), refs=refs(sales()))
    assert 'desconto-elevado-conferir-identidade' in (o.strategy['review_reasons'] or [])
    assert o.verdict != 'APROVAR'


def test_6b_normal_margin_is_not_flagged():
    # Referencia 100: preco 69 da 44,93% de margem -- acima do piso de 43 e abaixo do
    # corte de suspeita de 60. E a faixa em que o gate aprova sem ressalva.
    o = evaluate(CARD, plisting(price=69), config=gm_cfg(), refs=refs(sales()))
    assert o.verdict == 'APROVAR'
    assert 'desconto-elevado-conferir-identidade' not in (o.strategy['review_reasons'] or [])


def test_7_drift_guard_ignores_fractions_that_are_not_fragility_coverage(tmp_path):
    """A guarda casava QUALQUER `(a/b)`: a cobertura do perfil `(4/5)` ou um `(1/2)`
    solto quebravam o teste sem nada ter mudado."""
    import tests.test_docs_drift as drift
    n = len(longterm.FRAGILITY_FLAGS)
    text = (f'cobertura do perfil (4/5) e metade (1/2); fragilidade 0 (3/{n}) '
            f'com {n} flags e celula 4/5·{n}/{n}.')
    assert drift.stale_fragility_counts(text, n) == []


def test_7b_drift_guard_still_catches_a_real_stale_count():
    import tests.test_docs_drift as drift
    n = len(longterm.FRAGILITY_FLAGS)
    assert drift.stale_fragility_counts('celula 4/5·8/10 com 8 das 10 flags', n)


def test_8_min_gross_margin_is_ignored_loudly_in_a_legacy_mode(capsys):
    import main
    c = cfg()
    c['slab_strategy']['economics'] = dict(c['slab_strategy']['economics'],
                                           gate_mode='profit_or_discount')
    before = deepcopy(c['slab_strategy']['economics'])
    main.apply_cli_overrides(c, min_gross_margin=60)
    assert c['slab_strategy']['economics'] == before
    assert 'gross_margin' in capsys.readouterr().out


def test_8b_min_gross_margin_applies_in_its_own_mode():
    import main
    c = gm_cfg()
    main.apply_cli_overrides(c, min_gross_margin=60)
    assert c['slab_strategy']['economics']['min_gross_margin_percent'] == 60
