"""Small live validation. Credentials stay in the runner; output contains no env."""
import argparse
from collections import Counter
from dataclasses import asdict
import json
import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml
from main import _load_config
from src import report, scanner
from src.ebay_api import EbayClient


def validate(group='3', limit=1, out_dir='results/live-validation', focus_psa10=True):
    if limit not in (1, 2, 3):
        raise ValueError('validation supports 1 to 3 cards')
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    config = _load_config('config.yaml')
    config['max_pages'] = 1
    config['grade_query_suffixes'] = False
    # No credential, OAuth token, env dump or raw HTTP response is persisted.
    summary = {'commit': os.environ.get('GITHUB_SHA'), 'group': group,
               'max_cards': limit, 'max_pages_per_card': 1,
               'credentials_present': EbayClient().configured,
               'status': 'blocked', 'reason': '', 'funnel': {}, 'verdicts': {}}
    summary['validation_scope'] = 'PSA 10 com idioma explícito' if focus_psa10 else 'consulta geral'
    payload = None
    code = 1
    if not summary['credentials_present']:
        summary['reason'] = 'required_github_secrets_not_available_to_job'
    else:
        cards = scanner.filter_group(scanner.load_watchlist(), group)[:limit]
        summary['cards_selected'] = [f'{c.name} #{c.number} ({c.set_name}, {c.language})' for c in cards]
        # Generate an ephemeral subset without editing the canonical watchlist.
        entries = []
        for card in cards:
            entry = asdict(card)
            entry['set'] = entry.pop('set_name')
            if focus_psa10:
                language_term = {'EN': 'English', 'JP': 'Japanese', 'KO': 'Korean', 'ZH-HANS': 'Simplified Chinese', 'ZH-HANT': 'Traditional Chinese'}.get(card.language, card.language)
                entry['ebay_query'] = f'{card.default_query()} {language_term} PSA 10'
            entries.append(entry)
        diagnostics = []
        def source_status(message):
            # Only fixed source labels and HTTP status numbers leave the process.
            source = 'pricecharting' if 'PriceCharting' in message else 'ebay' if 'eBay' in message or 'Browse' in message else 'scanner'
            for status in re.findall(r'HTTP (\d{3})', message):
                diagnostics.append({'source': source, 'http_status': int(status)})
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'watchlist.yaml'
            path.write_text(yaml.safe_dump({'cards': entries}), encoding='utf-8')
            _, opps, pricing_only, stats, aborted = scanner.run_scan(
                watchlist_path=str(path), config=config, log=source_status)
        summary['diagnostics'] = diagnostics
        summary['ebay_live_listings_received'] = bool(stats['seen'])
        summary['funnel'] = dict(stats)
        summary['verdicts'] = dict(Counter(o.verdict for o in opps))
        source_failed = any(stats[k] for k in ('pc_error','pc_breaker','ebay_error','card_error'))
        usable_psa = sum(o.strategy.get('psa_evidence', {}).get('n_used', 0) >= config['slab_strategy']['evidence']['min_sales'] for o in opps)
        summary['rows_with_psa_sales'] = usable_psa
        summary['candidate_review_reasons'] = dict(Counter(reason for o in opps for reason in o.strategy.get('review_reasons', [])))
        summary['candidate_rejection_reasons'] = dict(Counter(reason for o in opps for reason in o.strategy.get('rejection_reasons', [])))
        summary['policy_version'] = config['slab_strategy']['version']
        if aborted or pricing_only:
            summary['reason'] = 'authentication_or_api_failure'
        elif source_failed:
            summary['reason'] = 'source_or_processing_failure'
        elif not stats['seen']:
            summary['reason'] = 'no_live_listings_returned'
        elif not usable_psa:
            summary['status'] = 'partial'
            summary['reason'] = 'live_listings_received_but_no_strict_psa_comparables'
            code = 2
        else:
            summary['status'] = 'success'
            summary['reason'] = 'live_listings_and_psa_sales_processed_not_purchase_approval'
            code = 0
        payload = report.scan_payload(opps, len(cards), config, group=group,
                                      funnel=stats, aborted=bool(aborted or source_failed))
    if payload is not None:
        report.write_json(payload, str(target / 'scan.json'))
        from ebay_summary import build_markdown
        (target / 'report.md').write_text(build_markdown(payload), encoding='utf-8')
    text = json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False)
    (target / 'validation.json').write_text(text+'\n', encoding='utf-8')
    print(text)
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', default='3')
    parser.add_argument('--limit', type=int, choices=(1,2,3), default=1)
    parser.add_argument('--general-query', action='store_true', help='valida consulta geral, sem foco PSA 10 e idioma')
    args = parser.parse_args(argv)
    return validate(args.group, args.limit, focus_psa10=not args.general_query)


if __name__ == '__main__':
    raise SystemExit(main())
