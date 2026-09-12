"""Collect fresh PSA 10 evidence before spending time on theses or eBay calls."""
import argparse
import json
from pathlib import Path
from uuid import uuid4

from main import _load_config
from src import preselection, scanner


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watchlist', default='watchlist.yaml')
    parser.add_argument('--config', default='config.yaml')
    parser.add_argument('--group')
    parser.add_argument('--max-cards', type=int, default=25,
                        help='work budget, not an eligibility quota (default: 25)')
    parser.add_argument('--card-offset', type=int, default=0)
    parser.add_argument('--out', help='new private JSON within results/ or private/')
    args = parser.parse_args(argv)
    try:
        root = Path(__file__).resolve().parent
        target = Path(args.out) if args.out else root / 'results' / f'preselection-{uuid4().hex}.json'
        target = target.resolve()
        if target.suffix != '.json' or not any(target.is_relative_to(root / d) for d in ('results', 'private')):
            raise ValueError('output must be a JSON inside repository results/ or private/')
        if target.exists():
            raise ValueError('output already exists; use a new path for this collection')
        cfg = _load_config(args.config)
        cards = scanner.filter_group(scanner.load_watchlist(args.watchlist), args.group)
        payload = preselection.collect(cards, cfg, max_cards=args.max_cards, offset=args.card_offset)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive create: never overwrite a previous complete run with partial data.
        with target.open('x', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        print(preselection.render(payload))
        print(f'Arquivo privado de apoio: {target}')
        return 1 if payload['meta']['incomplete'] else 0
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    raise SystemExit(main())
