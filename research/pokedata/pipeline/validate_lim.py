"""Validação — sorteia 400 pares confirmados inglês-japonês e compara com as impressões listadas no Limitless."""
import json, re, os, time, html, requests, random, pickle
from collections import Counter
from datetime import datetime
from common import *
sets, cards = load(); units = art_units(cards)
R = pickle.load(open('result.pkl', 'rb')); CONF = R['CONF']
T = json.load(open('limitless_todo.json', encoding="utf-8")); code = {int(k): v for k, v in T['code'].items()}
PROMO = {'Scarlet & Violet Promos': 'SVP', 'Sword & Shield Promo': 'SP', 'Sun & Moon Black Star Promo': 'SMP', 'XY Black Star Promos': 'XYP', 'Black and White Promos': 'BWP', 'Mega Evolution Promos': 'MEP'}
ERAS = {'Black & White', 'XY', 'Sun & Moon', 'Sword & Shield', 'Scarlet & Violet', 'Mega Evolution'}
def sdate(k): return datetime.strptime(sets[k[0]]['release_date'][5:16], '%d %b %Y')
def nk(c): return key(c.replace('+', 'p'))
pool = []
for a, c in CONF['EN_JA'].items():
    s = sets[a[0]]
    if s['series'] not in ERAS: continue
    lc = PROMO.get(s['name']) or code.get(a[0])
    if not lc or lc.startswith('PR-') or s['name'].startswith(('McDonald', 'Mcdonald', 'Trick or Trade', 'Alternate', 'Trading Card Game Classic', 'Celebrations: Classic', '30th Celebration Classic')): continue
    if not re.fullmatch(r'(?:[A-Z]{2,4})?\d+', a[1]): continue
    if 'energy' in a[2]: continue
    pool.append((a, lc, str(int(re.search(r'(\d+)$', a[1]).group(1)))))
random.seed(42); sm = random.sample(pool, 400)
os.makedirs('ext/limitless', exist_ok=True)
s_ = requests.Session(); res = Counter(); bad = []
for a, lc, num in sm:
    out = f"ext/limitless/v_{lc}_{num}.json"
    if os.path.exists(out): r = json.load(open(out, encoding="utf-8"))
    else:
        try: q = s_.get(f"https://limitlesstcg.com/cards/{lc}/{num}", timeout=40)
        except Exception: res['fetch error'] += 1; continue
        r = dict(status=q.status_code, title='', jp=[])
        if q.status_code == 200:
            h = q.text; t = re.search(r'<title>(.*?)</title>', h, re.S); r['title'] = html.unescape(t.group(1)).strip() if t else ''
            i = h.find('JP. Prints'); j = h.find('</table>', i if i > 0 else 0)
            if i > 0: r['jp'] = [(x, y, html.unescape(z).strip()) for x, y, z in re.findall(r'href="/cards/jp/([^/"]+)/([^"/]+)"\s*>\s*([^<]+?)\s*<span', h[i:j])]
        json.dump(r, open(out, 'w', encoding="utf-8")); time.sleep(0.3)
    if r['status'] != 200: res['no page'] += 1; continue
    tk = key(r['title'].split(' - ')[0])
    if not (tk and (tk in a[2] or a[2] in tk or tk[:6] == a[2][:6])): res['page is another card'] += 1; continue
    if not r['jp']: res['limitless lists no JP print'] += 1; bad.append((sets[a[0]]['code'], a[1], a[2], 'NO JP in limitless', [(sets[b[0]]['code'], b[1]) for b in CONF['EN_JA'][a]])); continue
    lim = {(nk(x), int(re.search(r'(\d+)', y).group(1))) for x, y, z in r['jp'] if re.search(r'(\d+)', y)}
    mine = {(nk(sets[b[0]]['code'] or ''), int(re.search(r'(\d+)$', b[1]).group(1))) for b in CONF['EN_JA'][a] if re.search(r'(\d+)$', b[1])}
    if mine & lim: res['agree'] += 1
    elif {n for c, n in mine} & {n for c, n in lim}: res['same number, set code written differently'] += 1
    else:
        mx = max(n for c, n in lim)
        if all(n > mx for c, n in mine): res['my match is a higher secret number not listed by Limitless'] += 1
        else: res['disagree'] += 1
        bad.append((sets[a[0]]['code'], a[1], a[2], sorted(lim)[:5], sorted(mine)[:5]))
print(res)
for b in bad[:40]: print(b)
