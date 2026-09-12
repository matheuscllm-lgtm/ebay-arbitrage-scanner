"""Evidence-first curation queue, never an investment or purchase verdict.

Uses the production PSA 10 comparable-sales matcher. No raw multiplier, price
column, popularity score, thesis inference or target count participates here.
"""
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from tempfile import TemporaryDirectory

from . import grading, pc_sales, scanner
from .selection import select_batch
from .slab_strategy import money, policy_config, reference_sales


def watch_entry(card):
    entry = asdict(card)
    entry['set'] = entry.pop('set_name')
    entry['colliding_editions'] = list(card.colliding_editions)
    return entry


def scope_reasons(card):
    if card.language not in ('EN', 'JP'):
        return ['idioma-fora-do-escopo']
    if not all(str(x).strip() for x in (card.name, card.set_name, card.number, card.pc_url)):
        return ['identidade-ou-fonte-incompleta']
    return []


def assess_card(card, refs, config, *, today=None):
    """One row per observed variant; all baskets retain exact sales provenance."""
    entry = watch_entry(card)
    base = {'card': entry, 'grade': 'PSA 10', 'reference_currency': 'USD',
            'thesis_status': 'not_assessed', 'entry_status': 'not_assessed',
            'purchase_recommendation': False}
    reasons = scope_reasons(card)
    if reasons:
        return [dict(base, variants=[], status='FORA_DO_ESCOPO', reasons=reasons, evidence=None)]
    if refs is None or not refs.available:
        return [dict(base, variants=[], status='REVISAR', reasons=['fonte-indisponivel'], evidence=None)]
    variants = {frozenset()}
    for sale in getattr(refs, '_sales', []):
        parsed = grading.grade_from_title(sale.get('title', ''))
        if parsed.status == 'graded' and parsed.grade == grading.Grade('PSA', 10):
            variants.add(pc_sales.variant_tokens(sale.get('title', '')))
    policy, inv = config['slab_strategy'], config['investment']
    rows = []
    for variant in sorted(variants, key=lambda v: tuple(sorted(v))):
        evidence = reference_sales(card, refs, grading.Grade('PSA', 10), variant, policy, today=today)
        # A token found in an unrelated sale is not an observed variant of this card.
        if variant and not evidence['n_sales']:
            continue
        reasons = []
        if money(evidence['price_exact']) is None:
            reasons.append('sem-referencia-comparavel')
        if evidence['n_sales'] < policy['evidence']['min_sales']:
            reasons.append('poucas-vendas-na-janela')
        if evidence['window_days'] > policy['evidence']['windows_days'][0]:
            reasons.append('janela-ampliada')
        if evidence['sales_90d'] < inv['min_sales_90d']:
            reasons.append('poucas-vendas-em-90d')
        if evidence['active_months_90d'] < inv['min_active_months_90d']:
            reasons.append('recorrencia-insuficiente')
        dispersion = money(evidence['dispersion_exact'])
        limit = money(policy['evidence'].get('max_dispersion_percent'))
        if dispersion is None or limit is None:
            reasons.append('dispersao-nao-confirmada')
        elif dispersion > limit:
            reasons.append('precos-dispersos')
        # The budget applies to future ASK prices, not this sold-price reference.
        rows.append(dict(base, variants=sorted(variant), evidence=evidence,
                         status='REVISAR' if reasons else 'CANDIDATA', reasons=reasons))
    return rows


def collect(cards, config, *, max_cards=None, offset=0, log=print, loader=None):
    """Fresh bounded collection without constructing an eBay client.

    A failed card is retained, processing continues until the existing source
    breaker opens, and the run is explicitly incomplete. Batch limits are work
    limits only. Exported cards require fresh references in the downstream scan.
    """
    cfg = policy_config(config)
    if cfg['slab_strategy']['economics']['gate_mode'] != 'longterm':
        raise ValueError('preselection requires gate_mode: longterm')
    selected, coverage = select_batch(cards, max_cards, offset)
    loader = loader or scanner.load_card_page
    rows, candidates, stats = [], [], Counter()
    breaker = scanner.PcBreaker()
    failures = []
    started = datetime.now(timezone.utc).isoformat()
    # Ignore any cache path inherited from a prior execution, including same-day runs.
    with TemporaryDirectory(prefix='pokemon-preselect-') as cache:
        cfg['pc_cache_dir'] = cache
        for index, card in enumerate(selected):
            if breaker.down:
                break
            coverage['cards_attempted'] += 1
            log(f'Pré-seleção {index + 1}/{len(selected)}: {card.name} #{card.number}')
            try:
                refs = None
                if not scope_reasons(card):
                    _, refs = loader(card, cfg, stats=stats, breaker=breaker, log=log)
                result = assess_card(card, refs, cfg)
                if any('fonte-indisponivel' in r['reasons'] for r in result):
                    failures.append(offset + index)
                else:
                    coverage['cards_completed'] += 1
            except Exception as exc:
                # Do not dump potentially private/provider exception contents.
                stats['processing_error'] += 1
                breaker.record_error()
                failures.append(offset + index)
                result = [{'card': watch_entry(card), 'grade': 'PSA 10', 'variants': [],
                           'status': 'REVISAR', 'reasons': ['erro-de-processamento'],
                           'error_type': type(exc).__name__, 'evidence': None,
                           'purchase_recommendation': False}]
            rows.extend(result)
            if any(r['status'] == 'CANDIDATA' for r in result):
                candidates.append(watch_entry(card))
    incomplete = bool(failures or coverage['cards_attempted'] < coverage['cards_scheduled'])
    return {'meta': {'kind': 'psa10-evidence-preselection', 'version': 1,
                     'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
                     'selection': coverage, 'incomplete': incomplete,
                     'failed_offsets': failures, 'source_breaker_open': breaker.down,
                     'stats': dict(stats), 'candidate_cards': len(candidates),
                     'investment_eligibility': 'not_assessed', 'fresh_scan_required': True,
                     'thresholds': {'min_sales_90d': cfg['investment']['min_sales_90d'],
                                    'min_active_months_90d': cfg['investment']['min_active_months_90d'],
                                    'max_dispersion_percent': cfg['slab_strategy']['evidence']['max_dispersion_percent']},
                     'automatic_purchase': False}, 'cards': candidates, 'rows': rows}


def render(payload):
    """Canonical chat table; all rows, missing prices explicit, references clickable."""
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')

    meta, lines = payload['meta'], []
    coverage = meta['selection']
    lines += [f"Pré-seleção PSA 10 — {meta['finished_at']}", '',
              f"Concluídas: {coverage['cards_completed']}/{coverage['cards_scheduled']}; "
              f"adiadas: {coverage['cards_deferred']}; candidatas à curadoria: {meta['candidate_cards']}.",
              f"Falha/incompleta: {'sim' if meta['incomplete'] else 'não'}; "
              f"escopo limitado: {'sim' if coverage['scope_limited'] else 'não'}.", '',
              'CANDIDATA significa evidência para curadoria, não investimento aprovado. '
              'Tese, anúncios, custos e teto de entrada: não avaliados. '
              'Vendas observadas no agregador não representam o mercado eBay inteiro.', '',
              '| Carta / set / idioma | Variante | Mediana das vendas USD | Vendas 90d | Meses | Dispersão | Fila | Motivos |',
              '|---|---|---:|---:|---:|---:|---|---|']
    for row in payload['rows']:
        card, ev = row['card'], row.get('evidence') or {}
        price = ev.get('price')
        url = card['pc_url']
        # Catalog URLs are data; only emit a Markdown link for HTTPS, safely escaped.
        label = f'${Decimal(str(price)):.2f}' if price is not None else 'n/d'
        reference = f'[{label}]({url.replace("(", "%28").replace(")", "%29")})' if price is not None and url.startswith('https://') and not any(c.isspace() for c in url) else label
        fields = [f"{card['name']} #{card['number']} / {card['set']} / {card['language']}",
                  ', '.join(row['variants']) or 'sem modificador detectado', reference,
                  ev.get('sales_90d', 'n/d'), ev.get('active_months_90d', 'n/d'),
                  ev.get('dispersion_percent', 'n/d'), row['status'], ', '.join(row['reasons']) or 'crivo de evidência atendido']
        lines.append('| ' + ' | '.join(cell(x) for x in fields) + ' |')
    return '\n'.join(lines) + '\n'
