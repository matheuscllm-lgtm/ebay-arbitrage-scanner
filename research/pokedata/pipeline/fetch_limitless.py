"""Etapa 9b — consulta no Limitless as cartas listadas em limitless_todo.json.

Guarda, por carta, as impressões japonesas listadas na página.   Saída: ext/limitless/<SET>_<num>.json, limitless_jobs.json
"""
import json, re, os, time, html, requests, threading
from concurrent.futures import ThreadPoolExecutor
from common import *
from limitless_parse import parse_prints
sets, cards = load(); units = art_units(cards)
T = json.load(open('limitless_todo.json', encoding="utf-8")); code = {int(k): v for k, v in T['code'].items()}
PROMO = {'Scarlet & Violet Promos': 'SVP', 'Sword & Shield Promo': 'SP', 'Sun & Moon Black Star Promo': 'SMP', 'XY Black Star Promos': 'XYP', 'Black and White Promos': 'BWP', 'Mega Evolution Promos': 'MEP'}
SKIP = {'Alternate Art Promos', 'Trading Card Game Classic', '30th Celebration Classic Collection', 'Celebrations: Classic Collection'}
jobs = {}
for k in T['todo']:
    k = tuple(k); s = sets[k[0]]
    if s['name'] in SKIP or s['name'].startswith('McDonald') or s['name'].startswith('Mcdonald') or s['name'].startswith('Trick or Trade'): continue
    lc = PROMO.get(s['name']) or code.get(k[0]) or s['code']
    if not lc or lc.startswith('PR-'): continue
    m = re.search(r'(\d+)$', k[1])
    if not m: continue
    if not re.fullmatch(r'(?:[A-Z]{2,4})?\d+', k[1]): continue
    jobs.setdefault((lc, str(int(m.group(1)))), []).append(k)
os.makedirs('ext/limitless', exist_ok=True)
print('jobs', len(jobs), flush=True)
tl = threading.local()
def get(job):
    (lc, num), ks = job
    out = f"ext/limitless/{lc}_{num}.json"
    if os.path.exists(out):
        try:
            if json.load(open(out, encoding="utf-8")).get('parse_version') == 2: return
        except (ValueError, OSError): pass
    if not hasattr(tl, 's'): tl.s = requests.Session()
    for a in range(3):
        try:
            r = tl.s.get(f"https://limitlesstcg.com/cards/{lc}/{num}", timeout=40)
            if r.status_code in (200, 404): break
        except Exception: pass
        time.sleep(2 + 2 * a)
    else:
        return
    res = dict(status=r.status_code, title='', jp=[], intl=[], jp_section_valid=False, parse_version=2)
    if r.status_code == 200:
        h = r.text
        t = re.search(r'<title>(.*?)</title>', h, re.S); res['title'] = html.unescape(t.group(1)).strip() if t else ''
        prints = parse_prints(h, japanese=True)
        res['jp_section_valid'] = prints is not None
        res['jp'] = prints or []
        i0 = h.find('prints-table') 
        res['has_prints_table'] = i0 > 0
    json.dump(res, open(out, 'w', encoding="utf-8"), ensure_ascii=False)
    time.sleep(0.35)
with ThreadPoolExecutor(3) as ex: list(ex.map(get, jobs.items()))
json.dump({f"{lc}_{num}": [list(k) for k in ks] for (lc, num), ks in jobs.items()}, open('limitless_jobs.json', 'w', encoding="utf-8"))
print('DONE', len([f for f in os.listdir('ext/limitless') if f.endswith('.json')]), flush=True)
