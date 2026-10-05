"""Etapa 11 — confere no Limitless as cartas japonesas (2010 em diante) candidatas a exclusiva.

Se a página japonesa lista uma impressão internacional, a carta não é exclusiva.   Entrada: result.pkl   Saída: lim_jp.pkl
"""
import json, re, os, time, html, requests, pickle
from collections import Counter
from common import *
from identity import CANDIDATE
sets, cards = load(); units = art_units(cards)
R = pickle.load(open('result.pkl', 'rb')); ST = R['STATUS']
rows_, uinfo = pickle.load(open('catalog.pkl', 'rb'))
ERAS = {'Black & White', 'XY', 'Sun & Moon', 'Sword & Shield', 'Scarlet & Violet', 'MEGA'}
def lcode(c):
    c = c.replace('+', 'p')
    m = {'SM-P': 'SMP', 'XY-P': 'XYP', 'BW-P': 'BWP', 'S-P': 'SP', 'SV-P': 'SVP', 'M-P': 'MP'}
    return m.get(c, c)
todo = [k for k, s in ST.items() if s.get('motivo', '').startswith(CANDIDATE) and sets[k[0]]['language'] == 'JAPANESE' and sets[k[0]]['series'] in ERAS and sets[k[0]]['code'] and re.search(r'\d+$', k[1])]
print('todo', len(todo), Counter(sets[k[0]]['code'] for k in todo).most_common(12), flush=True)
os.makedirs('ext/limitless', exist_ok=True)
s_ = requests.Session(); out = {}; c = Counter()
for k in todo:
    lc = lcode(sets[k[0]]['code']); num = str(int(re.search(r'(\d+)$', k[1]).group(1)))
    f = f"ext/limitless/jp_{lc.replace('/', '_')}_{num}.json"
    if os.path.exists(f): r = json.load(open(f))
    else:
        r = dict(status=0, title='', intl=[])
        for cand in (lc, lc.upper(), lc.lower()):
            try: q = s_.get(f"https://limitlesstcg.com/cards/jp/{cand}/{num}", timeout=40)
            except Exception: continue
            r['status'] = q.status_code
            if q.status_code == 200:
                h = q.text; t = re.search(r'<title>(.*?)</title>', h, re.S); r['title'] = html.unescape(t.group(1)).strip() if t else ''
                i = h.find('Int. Prints'); j = h.find('JP. Prints', i if i > 0 else 0)
                if i > 0:
                    seg = h[i:(j if j > i else h.find('</table>', i))]
                    r['intl'] = [(x, y, html.unescape(z).strip()) for x, y, z in re.findall(r'href="/cards/([A-Za-z0-9\-]+)/([^"/]+)"\s*>\s*([^<]+?)\s*<span', seg) if x.lower() != 'jp']
                break
            time.sleep(0.2)
        json.dump(r, open(f, 'w')); time.sleep(0.3)
    if r['status'] != 200: c['sem página'] += 1; continue
    t0 = r['title'].split(' - ')[0]; tk = key(t0)
    okname = bool(tk and (tk in k[2] or k[2] in tk or tk[:6] == k[2][:6]))
    if not okname and not t0.isascii():
        nat = re.sub(r'\s+', '', uinfo[k]['nome_nativo'] or ''); t1 = re.sub(r'\s+', '', t0)
        base_nat = re.sub(r'(ex|EX|GX|V|VMAX|VSTAR|BREAK)$', '', nat)
        okname = (not nat) or (base_nat and base_nat in t1) or (t1 in nat)
    if not okname: c['página de outra carta'] += 1; continue
    if r['intl']: c['tem impressão internacional'] += 1; out[k] = [f"{z} ({x}) #{y}" for x, y, z in r['intl']]
    else: c['sem impressão internacional'] += 1; out[k] = []
print(c)
pickle.dump(out, open('lim_jp.pkl', 'wb'))
ex = [(sets[k[0]]['code'], k[1], units[k][0]['_base'], v[:3]) for k, v in out.items() if v][:25]
for e in ex: print(e)
