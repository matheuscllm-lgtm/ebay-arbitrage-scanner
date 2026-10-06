"""Etapa 9c — cruza as impressões japonesas que o Limitless lista com as cartas japonesas do PokeData.

O Limitless agrupa impressões da mesma carta de jogo (mesmo texto), não da mesma arte.
Por isso cada par encontrado ainda passa pela comparação de imagem (stage2_pairs.py).

Entrada: limitless_jobs.json, ext/limitless/*.json   Saída: lim_pairs.pkl
"""
import json, os, re, pickle
from collections import Counter, defaultdict
from common import *

sets, cards = load(); units = art_units(cards)
J = json.load(open('limitless_jobs.json', encoding="utf-8"))
def nk(c): return key(c.replace('+', 'p'))
jpsets = defaultdict(list)
for s in sets.values():
    if s['language'] == 'JAPANESE' and s['code']: jpsets[nk(s['code'])].append(s['id'])
jpu = defaultdict(list)
for k in units:
    if sets[k[0]]['language'] == 'JAPANESE':
        m = re.search(r'(\d+)$', k[1])
        if m: jpu[(k[0], int(m.group(1)))].append(k)

c = Counter(); todo = []
for name, ks in J.items():
    p = f'ext/limitless/{name}.json'
    if not os.path.exists(p): continue
    r = json.load(open(p, encoding="utf-8"))
    if r['status'] != 200 or not r['jp']: continue
    tk = key(r['title'].split(' - ')[0]); k0 = ks[0]
    if not (tk and (tk in k0[2] or k0[2] in tk or tk[:6] == k0[2][:6])): continue   # página de outra carta
    found = []
    for code, num, sname in r['jp']:
        n = re.search(r'(\d+)', num)
        if n: found += [u for sid in jpsets.get(nk(code), []) for u in jpu.get((sid, int(n.group(1))), [])]
    c['com impressão japonesa no PokeData' if found else 'impressão japonesa só fora do PokeData'] += 1
    for k in ks:
        for b in found: todo.append((tuple(k), b))
todo = sorted(set(todo))
pickle.dump(todo, open('lim_pairs.pkl', 'wb'))
print(dict(c), '| pares para conferir por imagem:', len(todo))
