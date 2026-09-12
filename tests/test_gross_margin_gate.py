"""Gate economico `gross_margin`: SO margem bruta, sem taxa nenhuma.

Regra canonica do operador (2026-09-09): o veredito economico usa
`(referencia - preco) / preco * 100` em Decimal exato, aprovado ESTRITAMENTE
acima de `economics.min_gross_margin_percent`. Os custos de intermediacao
continuam sendo calculados e reportados, mas nao decidem veredito.

Nenhum teste fixa o literal do limiar de producao: quando precisa do valor
vigente le de `config.yaml` via `policy_config()`; nos casos de fronteira usa um
limiar proprio do teste.
"""
from decimal import Decimal, ROUND_DOWN

import pytest

import main
from src.policy_validation import PolicyError, pending_config, validate_config
from src.slab_strategy import evaluate, policy_config
from tests.test_slab_strategy import CARD, listing, refs, sales

THRESHOLD = 40  # limiar do teste, independente do config de producao


def gm_cfg(threshold=THRESHOLD, **economics):
    """Custos completos, gate em gross_margin, limiar explicito do teste."""
    c = policy_config({'min_discount_percent': 20, 'suspicious_margin_percent': 60})
    p = c['slab_strategy']
    p['costs'].update(coverage_confirmed=True, comc_processing_usd=1, comc_storage_usd=0,
                      selling_fee_percent=5, cashout_fee_percent=3, fee_basis='sale_then_cashout')
    p['economics'].clear()
    p['economics'].update(gate_mode='gross_margin', min_gross_margin_percent=threshold)
    p['economics'].update(economics)
    p['evidence']['max_dispersion_percent'] = 30
    return c


def evaluate_margin(reference, price=100, cfg=None):
    """Margem bruta = (reference - price)/price*100, pela mediana das vendas PSA."""
    return evaluate(CARD, listing(price=price), config=cfg or gm_cfg(),
                    refs=refs(sales(price=reference)))


# --- o modo existe, valida e e o vigente no config de producao -----------------------

def test_config_defaults_to_longterm_but_accepts_legacy_gross_margin_mode():
    c = policy_config()
    assert c['slab_strategy']['economics']['gate_mode'] == 'longterm'
    threshold = c['slab_strategy']['economics']['min_gross_margin_percent']
    assert threshold == 20
    c['slab_strategy']['economics']['gate_mode'] = 'gross_margin'
    validate_config(c)


def test_config_validation_rejects_unknown_mode_and_bad_threshold():
    c = policy_config()
    c['slab_strategy']['economics']['gate_mode'] = 'typo'
    with pytest.raises(PolicyError):
        validate_config(c)
    c = policy_config()
    c['slab_strategy']['economics']['min_gross_margin_percent'] = 'muito'
    with pytest.raises(PolicyError):
        validate_config(c)


def test_pending_config_lists_the_key_of_the_active_gate():
    c = gm_cfg()  # legacy mode still permits a pending/undefined floor
    c['slab_strategy']['economics']['min_gross_margin_percent'] = None
    pending = pending_config(c)
    assert 'economics.min_gross_margin_percent' in pending
    assert not any(item.startswith('economics.min_net') for item in pending)
    assert 'economics.min_profit_usd' not in pending


def test_main_check_config_accepts_the_new_mode(capsys):
    code = main.main(['--check-config'])
    out = capsys.readouterr().out
    assert 'estrutura' in out and 'lida' in out
    assert 'gate_mode' not in out
    assert code in (0, 2)


# --- fronteira: estritamente acima ---------------------------------------------------

def test_strictly_above_threshold_approves():
    o = evaluate_margin(140.01)
    assert o.verdict == 'APROVAR', o.reasons
    assert o.strategy['economic_gate']['margin_pass'] is True


def test_exactly_at_threshold_rejects():
    o = evaluate_margin(140)
    assert o.verdict == 'REJEITAR'
    assert 'abaixo-da-margem-bruta-minima' in o.reasons
    assert o.strategy['economic_gate']['margin_pass'] is False


@pytest.mark.parametrize('reference,expected', [
    (Decimal('139.9999'), 'REJEITAR'),
    (Decimal('140.0001'), 'APROVAR'),
])
def test_comparison_is_exact_not_rounded(reference, expected):
    o = evaluate_margin(reference)
    assert o.verdict == expected, o.reasons
    assert o.strategy['economic_gate']['gross_margin_percent'] == float(THRESHOLD)


def test_economic_gate_payload_shape():
    o = evaluate_margin(150)
    gate = o.strategy['economic_gate']
    assert gate['mode'] == 'gross_margin'
    assert gate['gross_margin_percent'] == 50.0
    assert Decimal(gate['gross_margin_percent_exact']) == Decimal(50)
    assert gate['threshold'] == float(THRESHOLD)
    assert gate['margin_pass'] is True
    assert gate['strictly_above'] is True
    # `margin_base`/`margin_base_source` entraram em 2026-09-09: o gate passou a medir
    # contra a REVENDA da propria certificadora, e publicar QUAL numero usou faz parte
    # de nao mentir sobre a conta que decidiu.
    assert gate['margin_base_source'] == 'resale'
    assert set(gate) == {'mode', 'gross_margin_percent', 'gross_margin_percent_exact',
                         'margin_base', 'margin_base_source',
                         'threshold', 'margin_pass', 'strictly_above'}


# --- o gate roda SEM base de custo ---------------------------------------------------

def _no_cost_cfg(threshold=THRESHOLD):
    c = gm_cfg(threshold)
    c['slab_strategy']['costs'].update(comc_processing_usd=None, comc_storage_usd=None,
                                       storage_horizon_days=None, coverage_confirmed=False)
    return c


def test_gate_runs_without_any_cost_model_and_can_reject():
    o = evaluate(CARD, listing(price=100), config=_no_cost_cfg(), refs=refs(sales(price=120)))
    assert o.strategy['profit_estimate'] is None
    assert o.strategy['economic_gate']['margin_pass'] is False
    assert 'abaixo-da-margem-bruta-minima' in o.strategy['rejection_reasons']
    assert o.verdict == 'REJEITAR'


def test_gate_runs_without_any_cost_model_and_can_pass():
    o = evaluate(CARD, listing(price=100), config=_no_cost_cfg(), refs=refs(sales(price=200)))
    assert o.strategy['profit_estimate'] is None
    assert o.strategy['economic_gate']['margin_pass'] is True
    assert o.strategy['rejection_reasons'] == []
    assert o.verdict == 'REVISAR'


def test_storage_without_resale_base_still_gets_a_verdict_from_the_gate():
    c = gm_cfg()
    c['slab_strategy']['costs'].update(comc_storage_usd=None, storage_horizon_days=120)
    o = evaluate(CARD, listing(price=100), config=c, refs=refs(sales(price=200)))
    assert o.strategy['economic_gate']['margin_pass'] is True
    assert 'abaixo-da-margem-bruta-minima' not in o.reasons


# --- as 6 armadilhas do ramo legado --------------------------------------------------

def test_trap1_legacy_discount_reject_never_fires():
    c = gm_cfg()
    c['min_discount_percent'] = 40
    o = evaluate(CARD, listing(price=100), config=c, refs=refs(sales(price=150)))
    assert 'desconto-abaixo-do-minimo' not in o.reasons
    assert o.verdict == 'APROVAR', o.reasons


def test_trap2_comparison_cap_is_the_highest_price_the_gate_approves():
    """REVISADO (revisao em contexto limpo, 2026-09-09): o teto NAO e a referencia crua.
    O teto e o MAIOR preco que o modo ainda aprova, e em `gross_margin` isso e
    `referencia / (1 + limiar/100)`, arredondado para BAIXO ao centavo. Imprimir a
    referencia crua no bloco por carta ("Teto de comparacao") prometia um preco que o
    proprio gate rejeita: com referencia 150 e limiar 43%, qualquer preco a partir de
    104,90 sai REJEITAR, mas a entrega dizia "teto US$ 150,00".

    O que a armadilha original queria proteger continua valendo: o teto NAO pode usar
    a formula do desconto legado (`min_discount_percent`)."""
    c = gm_cfg()
    c['min_discount_percent'] = 40   # regua legada: nao pode influenciar nada aqui
    o = evaluate(CARD, listing(price=100), config=c, refs=refs(sales(price=150)))
    limiar = Decimal(str(c['slab_strategy']['economics']['min_gross_margin_percent']))
    esperado = (Decimal('150') / (1 + limiar / 100)).quantize(Decimal('0.01'),
                                                              rounding=ROUND_DOWN)
    assert o.strategy['comparison_reference'] == 150
    assert Decimal(o.strategy['comparison_cap_exact']) == esperado
    # E nao e o teto da regua legada (150 x (1 - 40/100) = 90).
    assert o.strategy['comparison_cap'] != 90


def test_trap3_non_positive_profit_never_rejects():
    c = gm_cfg()
    c['slab_strategy']['costs']['per_slab_usd'] = 60
    o = evaluate(CARD, listing(price=100), config=c, refs=refs(sales(price=150)))
    assert o.strategy['profit_estimate'] < 0
    assert 'lucro-nao-positivo' not in o.reasons
    assert o.verdict == 'APROVAR', o.reasons


def test_trap4_min_net_rejects_never_fire():
    c = gm_cfg(min_profit_usd=999, min_net_margin_percent=999, min_net_roi_percent=999)
    o = evaluate(CARD, listing(price=100), config=c, refs=refs(sales(price=150)))
    assert not [r for r in o.reasons if r.startswith('abaixo-de-min_net')]
    assert 'abaixo-de-min_profit_usd' not in o.reasons
    assert o.verdict == 'APROVAR', o.reasons


def test_trap5_economic_keys_are_the_gross_margin_ones():
    o = evaluate_margin(150)
    assert not [r for r in o.reasons if r.endswith('-indefinido')], o.reasons
    o = evaluate_margin(150, cfg=gm_cfg(threshold=None))
    assert 'min_gross_margin_percent-indefinido' in o.reasons
    assert 'abaixo-da-margem-bruta-minima' not in o.reasons
    assert o.verdict == 'REVISAR'


def test_trap6_suspicious_margin_uses_the_cut_of_its_own_mode():
    """REVISADO (revisao em contexto limpo, 2026-09-09): a checagem de margem absurda
    NAO pode ficar inerte no modo `gross_margin`. O gate so tem PISO, entao sem ela uma
    linha de centenas de por cento -- assinatura classica de referencia errada ou carta
    trocada -- chegava a APROVAR sem nenhuma ressalva, justo no modo em que a margem e
    o unico criterio.

    A armadilha original estava certa em UMA coisa: o corte de 60% do topo do config
    foi calibrado para o gate antigo e, sob um gate que aprova a partir de 43%, ficaria
    logo acima do limiar e engoliria negocio normal. Por isso o modo tem corte proprio
    (`economics.suspicious_gross_margin_percent`), e o de 60% do topo NAO e usado aqui.
    Ela REVISA, nunca rejeita."""
    # `gm_cfg` zera o bloco `economics`, entao o corte proprio do modo entra explicito.
    # Ausente, o codigo cai no corte legado de 60 (fail-safe: revisa MAIS, nunca menos).
    corte = 150
    c = gm_cfg(suspicious_gross_margin_percent=corte)
    # 200% de margem: acima do corte proprio -> pede conferencia de identidade.
    o = evaluate(CARD, listing(price=100), config=c, refs=refs(sales(price=300)))
    assert o.gross_margin_pct == 200 and 200 > corte
    assert 'retorno-elevado-conferir-identidade' in o.reasons
    assert o.verdict == 'REVISAR', o.reasons
    # 66,7% de margem: acima do corte LEGADO de 60, mas dentro do normal neste modo.
    ok = evaluate(CARD, listing(price=60), config=c, refs=refs(sales(price=100)))  # 66,7%
    assert ok.gross_margin_pct > c.get('suspicious_margin_percent', 60)
    assert 'retorno-elevado-conferir-identidade' not in ok.reasons
    assert ok.verdict == 'APROVAR', ok.reasons


# --- custos continuam informativos ---------------------------------------------------

def test_costs_and_net_metrics_stay_populated_as_information():
    o = evaluate(CARD, listing(price=100), config=gm_cfg(), refs=refs(sales(price=150)))
    s = o.strategy
    assert s['investment_total'] == 111
    assert s['profit_estimate'] is not None and s['net_margin_percent'] is not None
    assert s['net_roi_percent'] is not None and s['net_sale_proceeds'] is not None
    assert s['costs']['selling_fee_usd'] is not None and s['costs']['cashout_fee_usd'] is not None


# --- modos antigos intactos ----------------------------------------------------------

def legacy_cfg(mode):
    c = policy_config({'min_discount_percent': 20, 'suspicious_margin_percent': 60})
    p = c['slab_strategy']
    p['costs'].update(coverage_confirmed=True, comc_processing_usd=1, comc_storage_usd=0,
                      selling_fee_percent=5, cashout_fee_percent=3, fee_basis='sale_then_cashout')
    p['economics'].clear()
    if mode == 'profit_or_discount':
        p['economics'].update(gate_mode='profit_or_discount', min_profit_usd=40,
                              min_discount_percent=30, require_positive_profit=True)
    else:
        p['economics'].update(gate_mode='all_minima', min_profit_usd=0,
                              min_net_margin_percent=0, min_net_roi_percent=0)
    p['evidence']['max_dispersion_percent'] = 30
    return c


def test_profit_or_discount_mode_unchanged():
    o = evaluate(CARD, listing(price=100), config=legacy_cfg('profit_or_discount'),
                 refs=refs(sales(price=150)))
    gate = o.strategy['economic_gate']
    assert gate['mode'] == 'profit_or_discount'
    assert set(gate) == {'mode', 'profit_pass', 'discount_pass', 'strictly_above'}
    assert o.strategy['comparison_cap'] == 150
    assert 'desconto-abaixo-do-minimo' not in o.reasons


def test_all_minima_mode_unchanged():
    c = legacy_cfg('all_minima')
    c['min_discount_percent'] = 40
    o = evaluate(CARD, listing(price=100), config=c, refs=refs(sales(price=150)))
    assert 'desconto-abaixo-do-minimo' in o.reasons
    assert o.strategy['comparison_cap'] == 90
    assert 'economic_gate' not in o.strategy


def test_all_minima_still_rejects_non_positive_profit_and_min_net():
    c = legacy_cfg('all_minima')
    c['slab_strategy']['economics'].update(min_net_margin_percent=10, min_net_roi_percent=10)
    c['slab_strategy']['costs']['per_slab_usd'] = 60
    o = evaluate(CARD, listing(price=100), config=c, refs=refs(sales(price=150)))
    assert 'lucro-nao-positivo' in o.reasons
    assert 'abaixo-de-min_net_margin_percent' in o.reasons


def test_all_minima_still_reviews_suspicious_margin():
    o = evaluate(CARD, listing(price=100), config=legacy_cfg('all_minima'),
                 refs=refs(sales(price=300)))
    assert 'desconto-elevado-conferir-identidade' in o.reasons
