"""EBAY PSA policy: completed PSA sales, explicit costs, fail-closed decisions.

Pure evaluation. No purchases, vault listing, or remote writes.
Legacy scorer remains only for reading/testing pre-policy artifacts.
"""
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import statistics
import unicodedata

from . import grading, pc_sales, title_parser
from .models import Opportunity


def policy_config(config=None):
    """Missing custom policy loads the versioned defaults, never the legacy engine."""
    import yaml
    cfg = dict(config or {})
    if not isinstance(cfg.get('slab_strategy'), dict):
        with (Path(__file__).resolve().parents[1] / 'config.yaml').open(encoding='utf-8') as f:
            defaults = yaml.safe_load(f)
        cfg['slab_strategy'] = deepcopy(defaults['slab_strategy'])
    cfg['graded_only'] = True
    return cfg


def money(value):
    try:
        n = Decimal(str(value))
        return n if n.is_finite() and n >= 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def amount(value):
    return None if value is None else float(value.quantize(Decimal('0.01')))


_LANGS = {
    'EN': r'\b(?:english|eng|en)\b',
    'JP': r'\b(?:japanese|japan|jpn|jp)\b|日本',
    'ZH': r'\b(?:chinese|china|mandarin|zh|cn)\b|中文',
    'KO': r'\b(?:korean|korea|kor|kr|ko)\b|한국',
    'PT': r'\b(?:portuguese|portugues|português|pt)\b',
    'DE': r'\b(?:german|deutsch|de)\b',
    'FR': r'\b(?:french|francais|français|fr)\b',
    'IT': r'\b(?:italian|italiano|it)\b',
    'ES': r'\b(?:spanish|espanol|español|es)\b',
}


def language(title):
    found = {key for key, pattern in _LANGS.items() if re.search(pattern, title, re.I)}
    return next(iter(found)) if len(found) == 1 else None


def normalized(text):
    return ' '.join(re.findall(r'[a-z0-9]+', unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()))


def identity_matches(card, title):
    """Name + numerator + explicit set; missing identity cannot approve."""
    from dataclasses import replace
    numerator = str(card.number).split('/')[0]
    if not numerator or not card.name or not card.set_name:
        return False
    if not title_parser.card_matches_title(replace(card, number=numerator), title):
        return False
    set_key, title_key = normalized(card.set_name), normalized(title)
    if not re.search(r"(?<![a-z0-9])" + re.escape(set_key) + r"(?![a-z0-9])", title_key):
        return False
    # Longer catalog names identify another set (Base Set 2 vs Base Set).
    from .groups import SCAN_GROUPS
    for group in SCAN_GROUPS.values():
        for other in group.sets:
            other_key = normalized(other)
            if other_key != set_key and set_key in other_key and other_key in title_key:
                return False
    if '/' in str(card.number):
        expected = [pc_sales.norm_number(n) for n in str(card.number).split('/')]
        fractions = re.findall(r'\b([A-Za-z]*\d+)\s*/\s*(\d+)\b', title)
        if fractions and not any([pc_sales.norm_number(n) for n in pair] == expected for pair in fractions):
            return False
    return True


def reference_sales(card, refs, grade, variants, policy, today=None):
    """Individually match sales; a product page alone is not identity evidence."""
    today = today or datetime.now(timezone.utc).date()
    matches, seen = [], set()
    for sale in getattr(refs, '_sales', []) if refs is not None and refs.available else []:
        title = sale.get('title', '')
        parsed = grading.grade_from_title(title)
        price = money(sale.get('price'))
        sale_id = str(sale.get('sale_id', ''))
        if sale.get('source') != 'ebay' or not sale_id.isdigit() or sale_id in seen:
            continue
        try:
            sold_date = date.fromisoformat(str(sale.get('date', '')))
        except ValueError:
            continue
        if sold_date > today or price is None or price <= 0:
            continue
        if parsed.status != 'graded' or parsed.grade != grade:
            continue
        if language(title) != card.language or not identity_matches(card, title):
            continue
        if pc_sales.variant_tokens(title) != variants:
            continue
        if pc_sales._NOISE_SALE_RE.search(title) or re.search(r'best offer|or best|accepted offer', title, re.I):
            continue
        seen.add(sale_id)
        matches.append({'date': sold_date.isoformat(), 'price': float(price), 'title': title,
                        'url': f'https://www.ebay.com/itm/{sale_id}', 'sale_id': sale_id,
                        'language': card.language, 'grade': grade.key})
    minimum = policy['evidence']['min_sales']
    windows = policy['evidence']['windows_days']
    selected, window = [], windows[-1]
    for window in windows:
        selected = [s for s in matches if (today - date.fromisoformat(s['date'])).days <= window]
        if len(selected) >= minimum:
            break
    selected.sort(key=lambda s: (s['date'], s['sale_id']), reverse=True)
    used = selected[:policy['evidence']['median_sample_limit']]
    prices = [money(s['price']) for s in used]
    median = statistics.median(prices) if prices else None
    dispersion = (max(prices) - min(prices)) / median * 100 if prices and median else None
    return {'price': amount(median), 'sales': used, 'n_sales': len(selected), 'n_used': len(used),
            'window_days': window, 'dispersion_percent': amount(dispersion)}


def evaluate(card, listing, fair=None, config=None, refs=None, **kwargs):
    cfg = policy_config(config)
    p = cfg['slab_strategy']
    review, reject = [], []
    gr = grading.grade_from_title(listing.title)
    grade = gr.grade
    opp = Opportunity(card, listing, grade.key if grade else gr.status.upper(), None,
                      0, 0, 'D', 0, 0, 0, verdict='REVISAR', pc_url=card.pc_url)
    details = {'policy_version': p['version'], 'psa_reference_original': None,
               'comparison_reference': None, 'comparison_cap': None, 'adjustments': [],
               'psa_sales': [], 'resale_sales': [], 'resale_estimate': None,
               'profit_estimate': None, 'net_margin_percent': None, 'net_roi_percent': None,
               'investment_total': None, 'investment_known_subtotal': None,
               'costs': {}, 'route': p['logistics']['resale_route'],
               'vault_preferred': p['logistics']['prefer_vault'],
               'vault_confirmed': listing.vault_confirmed,
               'listing_language': language(listing.title),
               'variant': sorted(pc_sales.variant_tokens(listing.title))}
    opp.strategy = details
    opp.discount_pct = opp.gross_margin_pct = opp.spread_usd = None
    details["purchase_currency"] = listing.currency
    details["slab_category"] = "Black Label" if grade and grade.qualifier == "BLACK" else "Pristine" if re.search(r"\bpristine\b", listing.title, re.I) else "regular"
    if gr.status == 'raw':
        reject.append('apenas-cartas-certificadas')
    elif gr.status != 'graded':
        review.append('certificadora-ou-nota-a-confirmar')
    if re.search(r'\bPSA\s*9[.,]5\b', listing.title, re.I):
        reject.append('PSA-nao-possui-nota-9.5')
    if listing.currency != 'USD':
        review.append('moeda-nao-USD-sem-conversao')
    if listing.buying_option != 'FIXED_PRICE':
        reject.append('somente-preco-fixo')
    if not listing.country:
        review.append('pais-do-item-a-confirmar')
    elif listing.country != cfg.get('required_location_country', 'US'):
        reject.append('pais-fora-do-escopo')
    if not listing.url or not listing.item_id:
        review.append('link-ou-identificador-ausente')
    if not identity_matches(card, listing.title):
        review.append('carta-colecao-numero-a-confirmar')
    if details['listing_language'] is None:
        review.append('idioma-nao-confirmado')
    elif details['listing_language'] != card.language:
        reject.append('idioma-diferente-da-referencia')
    if card.language not in p['languages']:
        review.append('idioma-sem-regra-na-configuracao')
    if 'ungraded' in (listing.condition or '').lower() and grade:
        reject.append('titulo-certificado-condicao-ungraded')
    flags = title_parser.risk_flags(listing.title, listing)
    for flag in flags:
        (reject if flag.startswith(('REJEITAR', 'LOTE')) else review).append(flag)
    price = money(listing.price)
    if price is None or price <= 0:
        review.append('preco-invalido')
    elif price < Decimal(str(cfg.get('min_price_usd', 10))):
        reject.append('preco-abaixo-do-piso')
    if grade and cfg.get('allowed_grades') and grade.key not in cfg['allowed_grades']:
        reject.append('nota-fora-do-filtro-da-execucao')
    if grade and cfg.get('graded_allow') and grade.key not in cfg['graded_allow']:
        reject.append('nota-fora-da-configuracao')

    # PSA comparison and actual resale estimate are separate calculations.
    rule = p['graders'].get(grade.grader) if grade else None
    if grade and re.search(r"\bpristine\b", listing.title, re.I) and grade.grader not in ("BGS", "CGC"):
        review.append("categoria-especial-sem-regra")
    if grade and not rule:
        review.append('certificadora-sem-regra')
    mapping = rule.get('grades', {}).get(f'{grade.value:g}') if rule and grade else None
    if grade and not mapping:
        review.append('nota-sem-equivalencia-configurada')
    psa = resale = None
    if mapping and identity_matches(card, listing.title) and details["listing_language"] == card.language:
        ref_grade = grading.Grade('PSA', float(mapping['psa_grade']))
        psa = reference_sales(card, refs, ref_grade, frozenset(details['variant']), p)
        details['psa_evidence'] = psa
        details['psa_sales'] = psa['sales']
        details['psa_reference_original'] = psa['price']
        details['psa_grade'] = ref_grade.key
        factor = Decimal(str(mapping.get('factor', 1)))
        details['adjustments'].append({'rule': 'grade_equivalence', 'factor': float(factor)})
        if psa['price'] is not None:
            comparison = Decimal(str(psa['price'])) * factor
            details['comparison_reference'] = amount(comparison)
            opp.fair_value = amount(comparison)
            if grade.grader == 'BGS':
                premium = rule['max_premium_percent']
                if grade.value == 9.5 and rule.get('combine_9_5_premium') is None:
                    review.append('BGS-9.5-combinacao-percentuais-indefinida')
                else:
                    cap = comparison
                    if grade.value != 9.5 or rule.get('combine_9_5_premium') is True:
                        cap *= 1 + Decimal(str(premium)) / 100
                    details['comparison_cap'] = amount(cap)
                    if price is not None and price > cap:
                        reject.append('preco-acima-do-limite-BGS')
            if price is not None and listing.currency == "USD":
                discount = (comparison - price) / comparison * 100
                opp.discount_pct = float(discount)
                opp.gross_margin_pct = float((comparison-price)/price*100) if price else 0
                opp.spread_usd = amount(comparison-price)
                if discount < Decimal(str(cfg.get('min_discount_percent', 20))):
                    reject.append('desconto-abaixo-do-minimo')
        else:
            review.append('sem-vendas-PSA-comparaveis')
        resale = psa if grade.grader == 'PSA' else reference_sales(
            card, refs, grade, frozenset(details['variant']), p)
        details['resale_evidence'] = resale
        details['resale_sales'] = resale['sales']
        details['resale_estimate'] = resale['price']
        if resale['price'] is None:
            review.append('revenda-sem-vendas-da-certificadora')
        for label, ref in [('PSA', psa), ('revenda', resale)]:
            if ref['n_sales'] < p['evidence']['min_sales']:
                review.append(f'{label}-poucas-vendas({ref["n_sales"]})')
            if ref['window_days'] > p['evidence']['windows_days'][0]:
                review.append(f'{label}-baixa-liquidez({ref["window_days"]}d)')
            limit = p['evidence'].get('max_dispersion_percent')
            if limit is None:
                review.append('limite-de-dispersao-indefinido')
            elif ref['dispersion_percent'] is not None and ref['dispersion_percent'] > limit:
                review.append(f'{label}-precos-dispersos')
        opp.ref_n_sales = psa['n_sales']
        opp.ref_window_days = psa['window_days']
        opp.ref_label = f'vendas {ref_grade.key} {card.language} (n={psa["n_sales"]})'
        opp.ref_source = 'pricecharting-sales-psa'
        opp.grade_label = grade.label
        opp.listing_type = grade.label

    # The $10 reserve is counted ONCE. Its exact coverage needs confirmation.
    costs = p['costs']
    reserve = money(costs.get('per_slab_usd'))
    details['costs'] = {'reserve_usd': amount(reserve), 'covers': costs.get('covers'),
                        'listing_shipping_observed_usd': listing.shipping,
                        'coverage_confirmed': costs.get('coverage_confirmed'),
                        'comc_processing_usd': costs.get('comc_processing_usd'),
                        'comc_storage_usd': costs.get('comc_storage_usd'),
                        'selling_fee_percent': costs.get('selling_fee_percent'),
                        'cashout_fee_percent': costs.get('cashout_fee_percent')}
    if not costs.get('coverage_confirmed'):
        review.append('cobertura-dos-US10-a-confirmar')
    if reserve is None:
        review.append('reserva-por-slab-indefinida')
    fixed = [money(costs.get(key)) for key in ('comc_processing_usd', 'comc_storage_usd')]
    sell, cashout = [money(costs.get(key)) for key in ('selling_fee_percent', 'cashout_fee_percent')]
    if any(v is None for v in fixed) or sell is None or cashout is None:
        review.append('custos-COMC-indefinidos')
    if sell is not None and sell >= 100 or cashout is not None and cashout >= 100:
        review.append('taxas-percentuais-invalidas')
        sell = cashout = None
    if costs.get('fee_basis') != 'sale_then_cashout':
        review.append('base-de-incidencia-das-taxas-indefinida')
    if costs.get('covers') != ['shipping', 'taxes']:
        review.append('cobertura-nao-suportada-configurar-custos-sem-duplicacao')
    if price is not None and reserve is not None and listing.currency == 'USD':
        investment = price + reserve + sum((v for v in fixed if v is not None), Decimal(0))
        details['investment_known_subtotal'] = amount(investment)
        if all(v is not None for v in fixed) and costs.get('coverage_confirmed') and costs.get('covers') == ['shipping', 'taxes']:
            details['investment_total'] = amount(investment)
            if resale and resale['price'] is not None and sell is not None and cashout is not None and costs.get('fee_basis') == 'sale_then_cashout':
                gross = Decimal(str(resale['price']))
                net = gross * (1-sell/100) * (1-cashout/100)
                profit = net-investment
                details.update(profit_estimate=amount(profit), net_margin_percent=amount(profit/gross*100),
                               net_roi_percent=amount(profit/investment*100), net_sale_proceeds=amount(net))
                details['costs']['selling_fee_usd'] = amount(gross*sell/100)
                details['costs']['cashout_fee_usd'] = amount(gross*(1-sell/100)*cashout/100)
                if profit <= 0:
                    reject.append('lucro-nao-positivo')
                for key, actual in [('min_profit_usd', profit), ('min_net_margin_percent', profit/gross*100),
                                    ('min_net_roi_percent', profit/investment*100)]:
                    threshold = money(p['economics'].get(key))
                    if threshold is not None and actual < threshold:
                        reject.append(f'abaixo-de-{key}')
    for key in ('min_profit_usd', 'min_net_margin_percent', 'min_net_roi_percent'):
        if money(p['economics'].get(key)) is None:
            review.append(f'{key}-indefinido')
    if p['logistics'].get('resale_route') != 'COMC' or p['logistics'].get('direct_vault_listing') is not False:
        review.append('rota-operacional-incompativel')
    if listing.seller_feedback_score < cfg.get('trusted_min_feedback', 50) or listing.seller_feedback_pct < cfg.get('trusted_min_feedback_pct', 98):
        review.append('historico-do-vendedor-insuficiente')
    if (opp.gross_margin_pct or 0) > cfg.get('suspicious_margin_percent', 60):
        review.append('desconto-elevado-conferir-identidade')
    opp.reasons = list(dict.fromkeys(reject + review))
    opp.verdict = 'REJEITAR' if reject else 'REVISAR' if review else 'APROVAR'
    details['rejection_reasons'] = reject
    details['review_reasons'] = list(dict.fromkeys(review))
    return opp
