"""Collect validated public catalog lists; refuse incomplete aggregate output."""
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

BASE = 'https://www.pokedata.io/api'
RATE_LIMIT_BACKOFF = (30, 60, 120, 240)  # HTTP 429: a fonte pede calma; bem mais que os 2-11 s dos erros comuns
SERIAL_RETRY_PAUSE = 5                   # entre sets refeitos um a um depois da passada paralela


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False))
    os.replace(temporary, path)


def validate_sets(value):
    if not isinstance(value, list) or not value:
        raise ValueError('Empty or invalid set catalog')
    seen = set()
    for row in value:
        if not isinstance(row, dict) or not {'id', 'name', 'language', 'series', 'code', 'release_date'} <= row.keys():
            raise ValueError('Invalid set schema')
        if type(row['id']) is not int or row['id'] < 0 or row['id'] in seen:
            raise ValueError('Invalid or duplicate set ID')
        seen.add(row['id'])


def validate_cards(value, set_id):
    if not isinstance(value, list):
        raise ValueError('Invalid card list')
    seen = set()
    for row in value:
        if not isinstance(row, dict) or not {'id', 'set_id', 'name', 'num', 'img_url', 'secret'} <= row.keys():
            raise ValueError('Invalid card schema')
        if type(row['id']) is not int or row['id'] in seen or row['set_id'] != set_id:
            raise ValueError('Wrong set or duplicate card ID')
        if not all(isinstance(row[k], str) for k in ('name', 'num', 'img_url')) or not row['name'].strip():
            raise ValueError('Invalid card identity')
        seen.add(row['id'])


def curl(url, out):
    result = subprocess.run(['curl', '-sS', '-m', '90', '-o', str(out), '-w', '%{http_code}', url], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else 'transport-error'


def fetch_json(url, path, validator, download=curl, pause=time.sleep):
    path = Path(path)
    try:
        value = json.loads(path.read_text())
        validator(value)
        return value, 'cached'
    except (OSError, ValueError, TypeError, KeyError):
        pass
    temporary = path.with_suffix(path.suffix + '.download')
    error = 'unknown error'
    errors = limits = 0
    try:
        while errors < 4 and limits <= len(RATE_LIMIT_BACKOFF):
            try:
                code = download(url, temporary)
                if code == '429':
                    # Limite de ritmo, não falha definitiva: espera longa e crescente, sem contar como erro comum.
                    error = 'HTTP 429'
                    limits += 1
                    if limits <= len(RATE_LIMIT_BACKOFF):
                        pause(RATE_LIMIT_BACKOFF[limits - 1])
                    continue
                if code != '200':
                    raise ValueError(f'HTTP {code}')
                value = json.loads(temporary.read_text())
                validator(value)
                atomic_json(path, value)
                pause(0.3)
                return value, 'downloaded'
            except (OSError, ValueError, TypeError, KeyError) as exc:
                error = str(exc)
                errors += 1
                pause(2 + errors * 3)
        raise RuntimeError(f'Failed to collect {url}: {error}')
    finally:
        temporary.unlink(missing_ok=True)


def collect(root=Path('.'), fetch=fetch_json, pause=time.sleep):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    manifest = {'started_at': datetime.now(timezone.utc).isoformat(), 'complete': False, 'sets': [], 'error': None}
    atomic_json(root / 'collection_manifest.json', manifest)
    try:
        sets, _ = fetch(f'{BASE}/sets', root / 'sets.json', validate_sets)
        (root / 'cards').mkdir(exist_ok=True)
        def get(row):
            sid = row['id']
            try:
                cards, status = fetch(f'{BASE}/cards?set_id={sid}', root / 'cards' / f'{sid}.json', lambda v: validate_cards(v, sid))
                return {'id': sid, 'status': status, 'count': len(cards)}, cards
            except Exception as exc:
                return {'id': sid, 'status': 'failed', 'error': str(exc)}, []
        with ThreadPoolExecutor(3) as executor:
            results = list(executor.map(get, sets))
        # Segunda passada, um set por vez e com pausa: o que falhou em paralelo costuma ser limite de ritmo.
        for index, (report, _) in enumerate(results):
            if report['status'] == 'failed':
                pause(SERIAL_RETRY_PAUSE)
                results[index] = get(sets[index])
        manifest['sets'] = [report for report, _ in results]
        failed = [r['id'] for r in manifest['sets'] if r['status'] == 'failed']
        if failed:
            raise RuntimeError(f'Incomplete collection; failed sets: {failed}')
        cards = [card for _, rows in results for card in rows]
        if len({c['id'] for c in cards}) != len(cards):
            raise RuntimeError('Duplicate card IDs across sets')
        atomic_json(root / 'all_cards.json', cards)
        manifest.update(complete=True, cards=len(cards))
        return cards
    except Exception as exc:
        manifest['error'] = str(exc)
        raise
    finally:
        manifest['finished_at'] = datetime.now(timezone.utc).isoformat()
        atomic_json(root / 'collection_manifest.json', manifest)


if __name__ == '__main__':
    print('registros de cartas', len(collect()))
