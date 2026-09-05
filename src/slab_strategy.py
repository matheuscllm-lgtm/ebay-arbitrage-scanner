"""EBAY PSA policy: completed PSA sales, explicit costs, fail-closed decisions.

Pure evaluation. No purchases, vault listing, or remote writes.
Legacy scorer remains only for reading/testing pre-policy artifacts.
"""
from copy import deepcopy
from collections import Counter
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
    if config is not None and not isinstance(config, dict):
        raise ValueError('Configuração deve ser um objeto YAML')
    cfg = deepcopy(config or {})
    with (Path(__file__).resolve().parents[1] / 'config.yaml').open(encoding='utf-8') as f:
        defaults = yaml.safe_load(f)
    if 'slab_strategy' not in cfg:
        cfg['slab_strategy'] = deepcopy(defaults['slab_strategy'])
    cfg.setdefault('graded_allow', defaults['graded_allow'])
    cfg['graded_only'] = True
    from .policy_validation import validate_config
    return validate_config(cfg)


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
    'ZH-HANS': r'\b(?:simplified chinese|chinese simplified|zh-hans)\b|简体',
    'ZH-HANT': r'\b(?:traditional chinese|chinese traditional|zh-hant)\b|繁體|繁体',
    'KO': r'\b(?:korean|korea|kor|kr|ko)\b|한국',
    'PT': r'\b(?:portuguese|portugues|português|pt)\b',
    'DE': r'\b(?:german|deutsch|de)\b',
    'FR': r'\b(?:french|francais|français|fr)\b',
    'IT': r'\b(?:italian|italiano|it)\b',
    'ES': r'\b(?:spanish|espanol|español|es)\b',
}


def language(title):
    found = {key for key, pattern in _LANGS.items() if re.search(pattern, title, re.I)}
    if re.search(r'\b(?:chinese|china|mandarin|zh|cn)\b|中文', title, re.I) and not found.intersection({'ZH-HANS', 'ZH-HANT'}):
        return None
    return next(iter(found)) if len(found) == 1 else None


def listing_language(listing):
    """Explicit title or explicit Language aspect; conflict is never resolved by guessing."""
    title_lang = language(listing.title)
    aspect_values = listing.item_aspects.get('Language', [])
    codes = {language(str(value)) for value in aspect_values}
    if aspect_values and (None in codes or len(codes) != 1):
        return None, 'conflito-ou-aspecto-ambiguo'
    aspect_lang = next(iter(codes)) if codes else None
    if title_lang and aspect_lang and title_lang != aspect_lang:
        return None, 'conflito-titulo-aspecto'
    if aspect_lang:
        # A title naming multiple languages or unqualified Chinese remains uncertain.
        mentions = sum(bool(re.search(pattern, listing.title, re.I)) for pattern in _LANGS.values())
        if mentions > 1 or (title_lang is None and re.search(r'\b(?:chinese|china|mandarin)\b', listing.title, re.I)):
            return None, 'titulo-ambiguo'
        return aspect_lang, 'ebay-getItem-localizedAspects.Language'
    return title_lang, 'titulo-explicito' if title_lang else 'nao-confirmado'


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
    # 'Mew' must not match 'Mewtwo'; card suffixes are part of identity.
    name_key = normalized(card.name)
    if not re.search(r'(?<![a-z0-9])' + re.escape(name_key) + r'(?![a-z0-9])', normalized(title)):
        return False
    suffixes = r'(?:ex|gx|vmax|vstar|v|lv\s*x)'
    if not re.search(r'\b' + suffixes + r'$', name_key) and re.search(
            r'\b' + re.escape(name_key) + r'\s+' + suffixes + r'\b', normalized(title)):
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
        fractions = title_parser._FRACTION_RE.findall(title)
        if fractions and any([pc_sales.norm_number(n) for n in pair] != expected for pair in fractions):
            return False
    return True


def reference_sales(card, refs, grade, variants, policy, today=None):
    """Individually match sales; a product page alone is not identity evidence."""
    today = today or datetime.now(timezone.utc).date()
    matches, seen, excluded = [], set(), Counter()
    pool = getattr(refs, '_sales', []) if refs is not None and refs.available else []
    for sale in pool:
        title = sale.get('title', '')
        parsed = grading.grade_from_title(title)
        price = money(sale.get('price'))
        sale_id = str(sale.get('sale_id', ''))
        if sale.get('source') != 'ebay' or not sale_id.isdigit() or sale_id in seen:
            excluded['origem-id-ou-duplicata'] += 1
            continue
        try:
            sold_date = date.fromisoformat(str(sale.get('date', '')))
        except ValueError:
            excluded['data-invalida'] += 1
            continue
        if sold_date > today or price is None or price <= 0:
            excluded['data-futura-ou-preco-invalido'] += 1
            continue
        if parsed.status != 'graded' or parsed.grade != grade:
            excluded['certificadora-nota-ou-categoria'] += 1
            continue
        if language(title) != card.language:
            excluded['idioma-ausente-ou-diferente'] += 1
            continue
        if not identity_matches(card, title):
            excluded['carta-colecao-ou-numero'] += 1
            continue
        if pc_sales.variant_tokens(title) != variants:
            excluded['variante-diferente'] += 1
            continue
        if (pc_sales._NOISE_SALE_RE.search(title) or title_parser.risk_flags(title)
                or re.search(r'best offer|or best|accepted offer|offer accepted|\b(?:potential|candidate|possibly|qualifiers?|OC|MC|ST|MK|PD)\b', title, re.I)
                or pc_sales._is_ambiguous_black_sale(title)):
            excluded['oferta-lote-ou-certificacao-incerta'] += 1
            continue
        seen.add(sale_id)
        matches.append({'date': sold_date.isoformat(), 'price': float(price), 'title': title,
                        'url': f'https://www.ebay.com/itm/{sale_id}', 'sale_id': sale_id,
                        'language': card.language, 'grade': grade.key,
                        'price_exact': str(price), 'source_url': getattr(refs, 'url', card.pc_url)})
    minimum = policy['evidence']['min_sales']
    windows = policy['evidence']['windows_days']
    selected, window = [], windows[-1]
    for window in windows:
        selected = [s for s in matches if (today - date.fromisoformat(s['date'])).days <= window]
        if len(selected) >= minimum:
            break
    selected.sort(key=lambda s: (s['date'], s['sale_id']), reverse=True)
    used = selected[:policy['evidence']['median_sample_limit']]
    prices = [money(s['price_exact']) for s in used]
    median = statistics.median(prices) if prices else None
    dispersion = (max(prices) - min(prices)) / median * 100 if prices and median else None
    excluded['fora-da-janela'] += len(matches) - len(selected)
    return {'price': amount(median), 'price_exact': str(median) if median is not None else None,
            'sales': used, 'n_sales': len(selected), 'n_used': len(used),
            'window_days': window, 'dispersion_percent': amount(dispersion),
            'dispersion_exact': str(dispersion) if dispersion is not None else None,
            'source_sales_count': len(pool), 'excluded_counts': dict(excluded),
            'as_of_date': today.isoformat()}


def evaluate(card, listing, fair=None, config=None, refs=None, **kwargs):
    cfg = policy_config(config)
    p = cfg['slab_strategy']
    observed_language, language_source = listing_language(listing)
    review, reject = [], []
    gr = grading.grade_from_title(listing.title, allow=frozenset(cfg['graded_allow']))
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
               'listing_language': observed_language,
               'language_source': language_source,
               'item_aspects': listing.item_aspects,
               'details_url': listing.details_url,
               'variant': sorted(pc_sales.variant_tokens(listing.title))}
    opp.strategy = details
    opp.discount_pct = opp.gross_margin_pct = opp.spread_usd = None
    details["purchase_currency"] = listing.currency
    details["slab_category"] = "Black Label" if grade and grade.qualifier == "BLACK" else "Pristine" if re.search(r"\bpristine\b", listing.title, re.I) else "regular"
    if gr.status == 'raw':
        reject.append('apenas-cartas-certificadas')
    elif gr.status != 'graded':
        review.append('certificadora-ou-nota-a-confirmar')
    if gr.status == 'out_of_scope' and 'sem nota' not in gr.reason:
        reject.append('certificadora-ou-nota-fora-do-escopo')
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
    if listing.details_error:
        review.append(listing.details_error)
    if not identity_matches(card, listing.title):
        review.append('carta-colecao-numero-a-confirmar')
    for value in listing.item_aspects.get('Set', []):
        if normalized(str(value)) != normalized(card.set_name):
            review.append('colecao-do-aspecto-a-confirmar')
    for value in listing.item_aspects.get('Card Number', []):
        expected = [title_parser._norm_num_token(n) for n in str(card.number).split('/')]
        observed = [title_parser._norm_num_token(n) for n in str(value).split('/')]
        if observed[0] != expected[0] or (len(expected) > 1 and len(observed) > 1 and observed != expected):
            review.append('numero-conflitante-no-aspecto')
    if grade:
        for value in listing.item_aspects.get('Professional Grader', []):
            known = {'PSA': r'\bpsa\b|professional sports authenticator', 'CGC': r'\bcgc\b',
                     'BGS': r'\bbgs\b|beckett', 'TAG': r'\btag\b|technical authentication'}
            found = {g for g, pattern in known.items() if re.search(pattern, str(value), re.I)}
            if found != {grade.grader}:
                review.append('certificadora-conflitante-no-aspecto')
        for value in listing.item_aspects.get('Grade', []):
            numbers = re.findall(r'(?<![\d.])(?:10|[1-9](?:[.,]5)?)(?![\d.])', str(value))
            if len(numbers) != 1 or Decimal(numbers[0].replace(',', '.')) != Decimal(str(grade.value)):
                review.append('nota-conflitante-no-aspecto')
    if details['listing_language'] is None:
        review.append('idioma-nao-confirmado')
    elif details['listing_language'] != card.language:
        reject.append('idioma-diferente-da-referencia')
    if card.language not in p['languages']:
        review.append('idioma-sem-regra-na-configuracao')
    if 'ungraded' in (listing.condition or '').lower() and grade:
        reject.append('titulo-certificado-condicao-ungraded')
    elif grade and not listing.condition:
        review.append('condicao-certificada-a-confirmar')
    if re.search(r'\b(?:potential|candidate|possibly|qualifiers?|OC|MC|ST|MK|PD)\b', listing.title, re.I):
        review.append('certificacao-potencial-ou-qualificada')
    if grade and (grade.qualifier in ('BLACK', 'PRISTINE') or re.search(r'\bpristine\b', listing.title, re.I)):
        review.append('categoria-especial-sem-regra')
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
            comparison = Decimal(psa['price_exact']) * factor
            details['comparison_reference'] = amount(comparison)
            details['comparison_reference_exact'] = str(comparison)
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
                    if price is not None and listing.currency == 'USD' and price > cap:
                        reject.append('preco-acima-do-limite-BGS')
            elif grade.grader in ('CGC', 'TAG'):
                max_percent = money(rule.get('max_reference_percent'))
                if max_percent is None:
                    review.append('limite-da-certificadora-indefinido')
                else:
                    cap = comparison * max_percent / 100
                    details['comparison_cap'] = amount(cap)
                    details['comparison_cap_exact'] = str(cap)
                    details['comparison_cap_exact'] = str(cap)
                    if price is not None and listing.currency == 'USD' and price > cap:
                        reject.append(f'preco-acima-do-limite-{grade.grader}')
            if price is not None and listing.currency == "USD":
                discount = (comparison - price) / comparison * 100
                opp.discount_pct = float(discount)
                opp.gross_margin_pct = float((comparison-price)/price*100) if price else 0
                opp.spread_usd = amount(comparison-price)
                if grade.grader == 'PSA' and p['economics'].get('gate_mode') != 'profit_or_discount' and discount < Decimal(str(cfg.get('min_discount_percent', 20))):
                    reject.append('desconto-abaixo-do-minimo')
                if grade.grader == 'PSA':
                    cap = comparison if p['economics'].get('gate_mode') == 'profit_or_discount' else comparison * (1 - Decimal(str(cfg.get('min_discount_percent', 20))) / 100)
                    details['comparison_cap'] = amount(cap)
                    details['comparison_cap_exact'] = str(cap)
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
            elif ref['dispersion_exact'] is not None and Decimal(ref['dispersion_exact']) > Decimal(str(limit)):
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
    if fixed[1] is None and costs.get('storage_horizon_days') is not None:
        from .comc_costs import estimate_storage
        fixed[1], forecast = estimate_storage(costs, money(resale['price_exact']) if resale else None)
        details['costs']['storage_forecast'] = forecast
        details['costs']['comc_storage_usd'] = amount(fixed[1])
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
                gross = Decimal(resale['price_exact'])
                net = gross * (1-sell/100) * (1-cashout/100)
                profit = net-investment
                details.update(profit_estimate=amount(profit), net_margin_percent=amount(profit/gross*100),
                               net_roi_percent=amount(profit/investment*100), net_sale_proceeds=amount(net))
                details['costs']['selling_fee_usd'] = amount(gross*sell/100)
                details['costs']['cashout_fee_usd'] = amount(gross*(1-sell/100)*cashout/100)
                if profit <= 0:
                    reject.append('lucro-nao-positivo')
                if p['economics'].get('gate_mode') == 'profit_or_discount':
                    profit_min = money(p['economics'].get('min_profit_usd'))
                    discount_min = money(p['economics'].get('min_discount_percent'))
                    comparison = money(details.get('comparison_reference_exact'))
                    discount = (comparison - price) / comparison * 100 if comparison else None
                    profit_pass = profit_min is not None and profit > profit_min
                    discount_pass = discount_min is not None and discount is not None and discount > discount_min
                    details['economic_gate'] = {'mode': 'profit_or_discount', 'profit_pass': profit_pass,
                                                'discount_pass': discount_pass, 'strictly_above': True}
                    if profit_min is not None and discount_min is not None and not (profit_pass or discount_pass):
                        reject.append('nao-atende-lucro-ou-desconto-minimo')
                else:
                    for key, actual in [('min_profit_usd', profit), ('min_net_margin_percent', profit/gross*100),
                                        ('min_net_roi_percent', profit/investment*100)]:
                        threshold = money(p['economics'].get(key))
                        if threshold is not None and actual < threshold:
                            reject.append(f'abaixo-de-{key}')
    economic_keys = ('min_profit_usd', 'min_discount_percent') if p['economics'].get('gate_mode') == 'profit_or_discount' else ('min_profit_usd', 'min_net_margin_percent', 'min_net_roi_percent')
    for key in economic_keys:
        if money(p['economics'].get(key)) is None:
            review.append(f'{key}-indefinido')
    if p['logistics'].get('resale_route') != 'COMC' or p['logistics'].get('direct_vault_listing') is not False:
        review.append('rota-operacional-incompativel')
    if listing.seller_feedback_score < cfg.get('trusted_min_feedback', 50) or listing.seller_feedback_pct < cfg.get('trusted_min_feedback_pct', 98):
        review.append('historico-do-vendedor-insuficiente')
    if p['economics'].get('gate_mode') != 'profit_or_discount' and grade and grade.grader == 'PSA' and (opp.gross_margin_pct or 0) > cfg.get('suspicious_margin_percent', 60):
        review.append('desconto-elevado-conferir-identidade')
    opp.reasons = list(dict.fromkeys(reject + review))
    opp.verdict = 'REJEITAR' if reject else 'REVISAR' if review else 'APROVAR'
    details['rejection_reasons'] = reject
    details['review_reasons'] = list(dict.fromkeys(review))
    return opp
