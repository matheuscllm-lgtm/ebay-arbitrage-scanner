import json
from collections import Counter
import main
from src import scanner, report, slab_report
from src.slab_strategy import evaluate, policy_config
from tests.test_slab_strategy import CARD, listing, sales, refs


def test_interrupted_scan_preserves_csv_as_well_as_json(monkeypatch, tmp_path, capsys):
    csv = tmp_path / 'last.csv'
    out = tmp_path / 'last.json'
    csv.write_text('previous complete csv', encoding='utf-8')
    out.write_text('previous complete json', encoding='utf-8')
    opp = evaluate(CARD, listing(price=50), config=policy_config(), refs=refs(sales()))
    monkeypatch.setattr(scanner, 'load_watchlist', lambda *a: [CARD])
    monkeypatch.setattr(scanner, 'run_scan', lambda **kw: ({}, [opp], False, Counter(seen=1, aborted=1), True))
    assert main.main(['--out',str(out),'--csv',str(csv)]) == 1
    assert csv.read_text() == 'previous complete csv'
    assert out.read_text() == 'previous complete json'
    assert (tmp_path/'last.aborted.csv').exists()
    assert json.loads((tmp_path/'last.aborted.json').read_text(encoding='utf-8'))['meta']['aborted']


def test_incomplete_banner_precedes_opportunities_and_shared_evidence_is_not_duplicated():
    c = policy_config()
    opp = evaluate(CARD, listing(price=50), config=c, refs=refs(sales()))
    payload = report.scan_payload([opp], 1, c, aborted=True)
    text = slab_report.render(payload)
    assert text.index('EXECUÇÃO ABORTADA') < text.index('| Carta')
    # One clickable price in the table plus one sale in the evidence section. A coluna
    # informativa `Longo prazo` (antes de `Links`) nunca carrega URL.
    assert '| Decisão | Tese | Entrada | Evidência | Longo prazo | Links |' in text
    assert text.count('https://www.ebay.com/itm/100)') == 2
    assert 'mesma amostra PSA' in text
    saved = payload['meta']['config']
    assert saved['max_ebay_calls'] == 500 and saved['trusted_min_feedback'] == 50


def test_missing_resale_is_not_reported_as_missing_fee_configuration():
    opp = evaluate(CARD, listing(price=50), config=policy_config(), refs=refs())
    assert 'armazenamento-sem-base-de-revenda' in opp.reasons
    assert 'custos-COMC-indefinidos' not in opp.reasons
    assert opp.verdict == 'REVISAR'


def test_gate_keys_header_names_the_threshold_that_actually_decides():
    """Cabecalho da entrega da politica: no `gate_mode: gross_margin` quem decide e
    `min_gross_margin_percent`. Antes nao havia ramo para esse modo -- o cabecalho caia
    no `else` e anunciava `min_profit_usd` e `min_discount_percent` (chaves dos modos
    LEGADOS, sem efeito nenhum) como se fossem a regra em vigor. As duas continuam
    impressas, porque estao no config e o operador as ve la, mas ROTULADAS como sem
    efeito neste modo -- o que decide vem primeiro e sozinho."""
    cfg = {'min_discount_percent': 30}
    eco = {'gate_mode': 'gross_margin', 'min_gross_margin_percent': 43,
           'min_profit_usd': 40, 'min_discount_percent': 30}
    items = slab_report._gate_keys(cfg, eco)
    text = ' · '.join(items)
    assert items[0] == '`gate_mode: gross_margin`'
    assert items[1] == '`min_gross_margin_percent: 43`'
    assert 'sem efeito neste modo' in text
    assert text.index('min_gross_margin_percent') < text.index('sem efeito neste modo')
    assert text.index('sem efeito neste modo') < text.index('min_profit_usd')
    # chave ausente no config sai n/d, nunca um numero inventado
    assert '`min_gross_margin_percent: n/d`' in ' · '.join(
        slab_report._gate_keys(cfg, {'gate_mode': 'gross_margin'}))
    # os modos legados seguem exatamente como estavam
    legacy = ' · '.join(slab_report._gate_keys(
        cfg, {'gate_mode': 'profit_or_discount', 'min_profit_usd': 40,
              'min_discount_percent': 30}))
    assert legacy == '`gate_mode: profit_or_discount` · `min_profit_usd: 40` · `min_discount_percent: 30`'
    assert 'sem efeito neste modo' not in legacy
    minima = ' · '.join(slab_report._gate_keys(
        cfg, {'gate_mode': 'all_minima', 'min_profit_usd': 40,
              'min_net_margin_percent': 5, 'min_net_roi_percent': 6}))
    assert minima == ('`gate_mode: all_minima` · `min_profit_usd: 40` · '
                      '`min_net_margin_percent: 5` · `min_net_roi_percent: 6` · '
                      '`min_discount_percent: 30` (topo do config)')
