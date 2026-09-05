"""Economic regressions and full production-path checks; synthetic sales only."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import json

import pytest
import main
import ebay_summary
from src import scanner, report
from src.models import Listing, WatchCard, FairValue
from src.slab_strategy import evaluate, policy_config, reference_sales, language
from src.grading import Grade

CARD = WatchCard('Charizard', 'Base Set', '4/102', 'EN', 'https://www.pricecharting.com/game/pokemon-base-set/charizard-4')


def listing(grade='PSA 10', **kw):
    values=dict(item_id='999', title=f'Charizard 4/102 Base Set English {grade}', price=75,
                shipping=7, currency='USD', buying_option='FIXED_PRICE', condition='Graded',
                seller_feedback_pct=99.9, seller_feedback_score=1000,
                url='https://www.ebay.com/itm/999', country='US')
    values.update(kw)
    return Listing(**values)


def sales(grade='PSA 10', price=100, n=3, lang='English', start=100, age=2):
    return [dict(date=(datetime.now(timezone.utc).date()-timedelta(days=age+i)).isoformat(),
                 price=price, title=f'Charizard 4/102 Base Set {lang} {grade}',
                 source='ebay', sale_id=str(start+i)) for i in range(n)]


def refs(*groups):
    return SimpleNamespace(available=True, _sales=sum(groups, []))


def cfg():
    c=policy_config({'min_discount_percent':20,'suspicious_margin_percent':60})
    p=c['slab_strategy']
    p['costs'].update(coverage_confirmed=True,comc_processing_usd=1,comc_storage_usd=0,
                      selling_fee_percent=5,cashout_fee_percent=3,fee_basis='sale_then_cashout')
    p['economics'].update(min_profit_usd=0,min_net_margin_percent=0,min_net_roi_percent=0)
    p['evidence']['max_dispersion_percent']=30
    return c


def test_psa_costs_and_metrics_no_shipping_double_count():
    o=evaluate(CARD,listing(),config=cfg(),refs=refs(sales()))
    assert o.verdict=='APROVAR'
    s=o.strategy
    assert s['investment_total']==86  # 75 + 10 + 1, NOT + observed shipping 7
    assert s['net_sale_proceeds']==92.15
    assert s['profit_estimate']==6.15
    assert s['net_margin_percent']==6.15
    assert s['net_roi_percent']==7.15
    assert o.discount_pct==25
    assert s['psa_reference_original']==100
    assert len(s['psa_sales'])==3


def test_defaults_never_approve_or_invent_fees():
    o=evaluate(CARD,listing(),refs=refs(sales()))
    assert o.verdict=='REVISAR'
    assert o.strategy['investment_total'] is None
    assert o.strategy['investment_known_subtotal']==85
    assert o.strategy['profit_estimate'] is None
    assert 'custos-COMC-indefinidos' in o.reasons


@pytest.mark.parametrize('key',['comc_processing_usd','comc_storage_usd','selling_fee_percent','cashout_fee_percent','fee_basis'])
def test_each_missing_cost_blocks_approval(key):
    c=cfg();c['slab_strategy']['costs'][key]=None
    assert evaluate(CARD,listing(),config=c,refs=refs(sales())).verdict=='REVISAR'


@pytest.mark.parametrize('key',['min_profit_usd','min_net_margin_percent','min_net_roi_percent'])
def test_each_missing_economic_gate_blocks_approval(key):
    c=cfg();c['slab_strategy']['economics'][key]=None
    assert evaluate(CARD,listing(),config=c,refs=refs(sales())).verdict=='REVISAR'


def test_tag_equivalence_is_not_resale_value():
    o=evaluate(CARD,listing('TAG 10'),config=cfg(),refs=refs(sales()))
    assert o.strategy['comparison_reference']==100
    assert o.strategy['resale_estimate'] is None
    assert o.verdict=='REVISAR'
    o=evaluate(CARD,listing('TAG 10'),config=cfg(),refs=refs(sales(),sales('TAG 10',80,start=200)))
    assert o.strategy['resale_estimate']==80
    assert o.verdict=='REJEITAR'  # loss after costs despite passing PSA discount
    assert o.strategy['profit_estimate']==-12.28


def test_9_5_uses_psa9_plus_five_not_psa10_or_double_premium():
    o=evaluate(CARD,listing('BGS 9.5'),config=cfg(),refs=refs(sales('PSA 9'),sales('PSA 10',1000,start=200),sales('BGS 9.5',100,start=300)))
    assert o.strategy['psa_reference_original']==100
    assert o.strategy['comparison_reference']==105
    assert o.strategy['comparison_cap'] is None
    assert o.verdict=='REVISAR'
    assert 'BGS-9.5-combinacao-percentuais-indefinida' in o.reasons


@pytest.mark.parametrize('price,exceeds',[(105,False),(105.01,True)])
def test_bgs_cap_boundary_independent_of_profit(price,exceeds):
    c=cfg();c['min_discount_percent']=-20
    o=evaluate(CARD,listing('BGS 10',price=price),config=c,refs=refs(sales(),sales('BGS 10',150,start=200)))
    assert o.strategy['comparison_cap']==105
    assert ('preco-acima-do-limite-BGS' in o.reasons)==exceeds


@pytest.mark.parametrize('grade',['CGC 10','SGC 10','CGC 9.5'])
def test_undefined_grader_is_review(grade):
    o=evaluate(CARD,listing(grade),config=cfg(),refs=refs(sales()))
    assert o.verdict=='REVISAR'
    assert 'certificadora-sem-regra' in o.reasons


@pytest.mark.parametrize('title,verdict',[
 ('Charizard 4/102 Base Set English PSA 9.5','REJEITAR'),
 ('Charizard 4/102 Base Set English','REJEITAR'),
 ('Charizard 4/102 Base Set English PSA 10 BGS 9.5','REVISAR'),
 ('Charizard 4/102 Base Set PSA 10','REVISAR'),
 ('Charizard 4/102 Base Set Japanese PSA 10','REJEITAR'),
 ('Charizard 4/102 Other Set English PSA 10','REVISAR'),
 ('Charizard 4/25 Base Set English PSA 10','REVISAR'),
])
def test_uncertain_identity_never_approves(title,verdict):
    o=evaluate(CARD,listing(title=title),config=cfg(),refs=refs(sales()))
    assert o.verdict==verdict


@pytest.mark.parametrize('lang,code',[('Japanese','JP'),('Chinese','ZH'),('Korean','KO'),('Portuguese','PT'),('English','EN')])
def test_languages_separate_in_both_listing_and_sales(lang,code):
    c=replace(CARD,language=code)
    pool=refs(sales(lang=lang),sales(lang='French',price=1000,start=200))
    o=evaluate(c,listing(title=f'Charizard 4/102 Base Set {lang} PSA 10'),config=cfg(),refs=pool)
    assert o.verdict=='APROVAR'
    assert o.strategy['psa_reference_original']==100
    assert all(s['language']==code for s in o.strategy['psa_sales'])


@pytest.mark.parametrize('mutate',[
 lambda s:s.update(title=s['title'].replace('English','')),
 lambda s:s.update(title=s['title'].replace('Base Set','Base Set 2')),
 lambda s:s.update(title=s['title']+' Reverse Holo'),
 lambda s:s.update(title=s['title'].replace('4/102','5/102')),
 lambda s:s.update(title=s['title']+' Best Offer'),
 lambda s:s.update(date='2099-01-01'),
 lambda s:s.update(date='bad'),
 lambda s:s.update(source='asking'),
 lambda s:s.update(sale_id=''),
 lambda s:s.update(price=float('nan')),
])
def test_invalid_comparables_excluded(mutate):
    rows=sales()
    for row in rows:mutate(row)
    o=evaluate(CARD,listing(),config=cfg(),refs=refs(rows))
    assert o.verdict=='REVISAR'
    assert o.strategy['psa_reference_original'] is None


def test_dedup_thin_and_missing_source_stay_visible():
    for pool in [refs(),refs(sales(n=1)*3),SimpleNamespace(available=False,_sales=sales())]:
        o=evaluate(CARD,listing(),config=cfg(),refs=pool)
        assert o is not None and o.verdict=='REVISAR'


def test_old_sales_and_dispersion_require_review():
    o=evaluate(CARD,listing(),config=cfg(),refs=refs(sales(age=200)))
    assert o.verdict=='REVISAR'
    rows=sales();rows[0]['price']=200
    o=evaluate(CARD,listing(),config=cfg(),refs=refs(rows))
    assert o.verdict=='REVISAR'
    assert 'PSA-precos-dispersos' in o.reasons


def test_black_label_gets_no_psa_premium_and_needs_black_resale():
    o=evaluate(CARD,listing('BGS 10 Black Label'),config=cfg(),refs=refs(sales(),sales('BGS 10',start=200)))
    assert o.strategy['comparison_reference']==100
    assert o.strategy['resale_estimate'] is None
    assert o.verdict=='REVISAR'


def test_artifact_markdown_csv_keep_pending_and_all_verdicts(tmp_path):
    os=[evaluate(CARD,listing(),config=cfg(),refs=refs(sales())),
        evaluate(CARD,listing(),config=cfg(),refs=refs()),
        evaluate(CARD,listing(price=95),config=cfg(),refs=refs(sales()))]
    payload=report.scan_payload(os,1,cfg())
    assert {r['verdict'] for r in payload['rows']}=={'APROVAR','REVISAR','REJEITAR'}
    json.dumps(payload,allow_nan=False)
    md=ebay_summary.build_markdown(payload,sensitivity=[10,20])
    for word in ['APROVAR','REVISAR','REJEITAR','pendente','https://www.ebay.com/itm/100','6.15']:
        assert word in md
    assert 'OPORTUNIDADE' not in md
    report.to_csv(os,str(tmp_path/'out.csv'))
    assert 'profit_estimate' in (tmp_path/'out.csv').read_text()


def test_run_scan_injects_policy_even_with_custom_config(monkeypatch):
    monkeypatch.setattr(scanner,'load_watchlist',lambda path:[CARD])
    monkeypatch.setattr(scanner,'EbayClient',lambda:SimpleNamespace(configured=True))
    def scan(card,ebay,config,**kwargs):
        assert 'slab_strategy' in config
        assert config['graded_only'] is True
        return FairValue(),[evaluate(card,listing(),config=config,refs=refs(sales()))]
    monkeypatch.setattr(scanner,'scan_card',scan)
    _,os,_,_,aborted=scanner.run_scan(config={'graded_only':False},log=lambda *a:None)
    assert not aborted and os[0].verdict=='REVISAR'


def test_scan_card_production_keeps_missing_refs_and_rejections(monkeypatch):
    monkeypatch.setattr(scanner.tcg_reference,'get_tcg_reference',lambda c:pytest.fail('raw source called'))
    ebay=SimpleNamespace(calls=0,search=lambda *a,**k:[listing(),listing(item_id='998',price=99)])
    _,os=scanner.scan_card(CARD,ebay,cfg(),refs=refs(),fair=FairValue(),log=lambda *a:None)
    assert len(os)==2 and all(o.verdict=='REVISAR' for o in os)


def test_raw_cli_rejected():
    with pytest.raises(SystemExit) as e:main.main(['--include-raw'])
    assert e.value.code==2
