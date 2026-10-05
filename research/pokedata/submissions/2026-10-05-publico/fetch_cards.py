"""Etapa 1 — baixa a lista de sets e as cartas de cada set do PokeData.

Saídas (na pasta de trabalho): sets.json, cards/<set_id>.json, all_cards.json
Usa as mesmas listagens públicas que o site carrega (/api/sets e /api/cards?set_id=...).
Ritmo baixo de propósito: 3 conexões e pausa entre pedidos.
"""
import json, os, time, subprocess
from concurrent.futures import ThreadPoolExecutor

BASE = 'https://www.pokedata.io/api'

def curl(url, out):
    r = subprocess.run(['curl', '-sS', '-m', '90', '-o', out, '-w', '%{http_code}', url], capture_output=True, text=True)
    return r.stdout.strip()

if not os.path.exists('sets.json'):
    code = curl(f'{BASE}/sets', 'sets.json')
    assert code == '200', f'falha ao baixar a lista de sets: HTTP {code}'
sets = json.load(open('sets.json'))
os.makedirs('cards', exist_ok=True)

def get(s):
    out = f"cards/{s['id']}.json"
    if os.path.exists(out) and os.path.getsize(out) > 1:
        return s['id'], 'cached'
    code = ''
    for attempt in range(4):
        code = curl(f"{BASE}/cards?set_id={s['id']}", out)
        if code == '200':
            try:
                json.load(open(out)); time.sleep(0.3); return s['id'], 'ok'
            except Exception:
                pass
        time.sleep(2 + attempt * 3)
    if os.path.exists(out): os.remove(out)
    return s['id'], 'FAIL ' + code

with ThreadPoolExecutor(3) as ex:
    res = list(ex.map(get, sets))
fails = [r for r in res if r[1].startswith('FAIL')]
print('sets', len(res), 'falhas', fails)

cards = []
for s in sets:
    p = f"cards/{s['id']}.json"
    if os.path.exists(p): cards += json.load(open(p))
json.dump(cards, open('all_cards.json', 'w'))
print('registros de cartas', len(cards))
