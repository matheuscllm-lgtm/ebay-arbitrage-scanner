"""Etapa 7 — gera candidatas e faz a primeira comparação. Uso: python match.py ENGLISH JAPANESE

Candidatas de cada carta: as 15 imagens mais parecidas no outro idioma e até 14 cartas de nome compatível.
Rodar para ENGLISH JAPANESE, ENGLISH CHINESE e CHINESE JAPANESE.   Saída: pairs_<XX>_<YY>.pkl
"""
import numpy as np, json, os, sys, time, re, pickle
from collections import defaultdict
from datetime import datetime
from multiprocessing import Pool
from common import *
from feats import verify

sets, cards = load()
units = art_units(cards)
def sdate(s): return datetime.strptime(s['release_date'][5:16], '%d %b %Y')
# features
ids = []; Gs = []; SP = []; SD = []; SO = []; where = {}
for sh in (0, 1):
    i = json.load(open(f'feat_ids_{sh}.json')); o = np.load(f'feat_o_{sh}.npy')
    for n, cid in enumerate(i): where[cid] = (sh, n)
    Gs.append(np.load(f'feat_g_{sh}.npy')); SP.append(np.load(f'feat_p_{sh}.npy', mmap_mode='r')); SD.append(np.load(f'feat_d_{sh}.npy', mmap_mode='r')); SO.append(o)
def sift(cid):
    sh, n = where[cid]; a, b = SO[sh][n], SO[sh][n + 1]
    return np.asarray(SP[sh][a:b]), np.asarray(SD[sh][a:b])
def g(cid):
    sh, n = where[cid]; return Gs[sh][n]
U = []  # unit records with image features
for k, recs in units.items():
    r = rep_image(recs)
    if r is None or r['id'] not in where: continue
    s = sets[k[0]]
    U.append(dict(k=k, cid=r['id'], lang=s['language'], base=recs[0]['_base'] if False else r['_base'], nk=k[2], tok=frozenset(tokens(r['_base'])), date=sdate(s)))
L = {l: [u for u in U if u['lang'] == l] for l in ('ENGLISH', 'JAPANESE', 'CHINESE')}
GM = {l: np.stack([g(u['cid']) for u in L[l]]) for l in L}
TOK = {}
for l in L:
    idx = defaultdict(list)
    for j, u in enumerate(L[l]):
        for t in u['tok']: idx[t].append(j)
    TOK[l] = idx
def name_compat(a, b):
    if a['nk'] == b['nk']: return 2
    ta, tb = a['tok'], b['tok']
    if not ta or not tb: return 0
    if ta <= tb or tb <= ta: return 1
    inter = len(ta & tb)
    return 1 if inter / len(ta | tb) >= 0.6 else 0
def run(args):
    src, tgt, lo, hi = args
    A = L[src][lo:hi]; B = L[tgt]; out = []
    S = GM[src][lo:hi] @ GM[tgt].T
    cache = {}
    def fs(cid):
        if cid not in cache:
            if len(cache) > 4000: cache.clear()
            cache[cid] = sift(cid)
        return cache[cid]
    for i, a in enumerate(A):
        order = np.argsort(-S[i])[:15]
        cand = {int(j) for n, j in enumerate(order) if n < 5 or S[i, j] >= 0.4}
        nc = set()
        for t in a['tok']:
            p = TOK[tgt].get(t, ())
            if len(p) <= 4000: nc.update(p)
        nc = [j for j in nc if name_compat(a, B[j])]
        nc.sort(key=lambda j: -S[i, j])
        cand.update(nc[:14])
        fa = sift(a['cid'])
        for j in cand:
            b = B[j]
            n, M = verify(fa, fs(b['cid']))
            out.append((a['k'], b['k'], n, float(S[i, j]), name_compat(a, b)))
    return out
if __name__ == '__main__':
    src, tgt = sys.argv[1], sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else len(L[src])
    n = min(limit, len(L[src])); step = 400
    jobs = [(src, tgt, lo, min(lo + step, n)) for lo in range(0, n, step)]
    t = time.time(); res = []
    with Pool(2) as p:
        for q, r in enumerate(p.imap_unordered(run, jobs)):
            res += r
            if q % 5 == 0: print(q, len(jobs), len(res), round(time.time() - t), flush=True)
    pickle.dump(res, open(f'pairs_{src[:2]}_{tgt[:2]}.pkl', 'wb'))
    print('DONE', src, tgt, len(res), round(time.time() - t), flush=True)
