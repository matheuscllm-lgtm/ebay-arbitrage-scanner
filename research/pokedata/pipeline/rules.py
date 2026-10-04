"""Regras de decisão: quando um par é confirmado, quando vai para os inconclusivos e quando é descartado como versão recolorida."""
import json, numpy as np
rep = json.load(open('unit_rep.json'))
_ids = {}; _G = []
for sh in (0, 1):
    for n, c in enumerate(json.load(open(f'feat_ids_{sh}.json'))): _ids[c] = (sh, n)
    _G.append(np.load(f'feat_g_{sh}.npy'))
def _g(k):
    sh, n = _ids[rep[f"{k[0]}|{k[1]}|{k[2]}"]]; return _G[sh][n]
def chroma(a, b):
    x = _g(a)[384:]; y = _g(b)[384:]
    return float(x @ y / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-9))
def rule(r, nc, ch, energy):
    ni = r.get('n_in', 0); ce = r['cells']; ncc = r['ncc']; n = r['n']
    if nc == 2:
        if ni >= 40 and ch >= 0.75: return 'A1'
        if ni >= 60 and ncc >= 0.75: return 'A6'
        if ni >= 20 and ch >= 0.75: return 'A2'
        if 12 <= ni < 20 and ch >= 0.75 and (ncc >= 0.45 or ch >= 0.9): return 'A3'
        if ni >= 25 and ncc >= 0.85 and ch >= 0.55: return 'A4'
        return None
    if nc == 1:
        if ch >= 0.75 and ni >= 40: return 'B1'
        if ni >= 60 and ncc >= 0.75: return 'B6'
        if ch >= 0.75 and ni >= 20 and ce >= 8: return 'B2'
        if ch >= 0.75 and ni >= 12 and ncc >= 0.85 and ce >= 7: return 'B3'
        return None
    if (not energy) and ni >= 50 and ce >= 14 and ncc >= 0.8 and ch >= 0.8: return 'C1'
    return None

def gray_rule(r, nc, ch, energy):
    ni = r.get('n_in', 0); ce = r['cells']; ncc = r['ncc']
    if nc >= 1: return (ni >= 12 and ch >= 0.6) or (ni >= 6 and ch >= 0.8)
    return (not energy) and ni >= 30 and ce >= 10 and ch >= 0.75 and ncc >= 0.6
def classify(pairs, s2, BAD):
    """returns conf[a][b] = (r, nc, rule), gray[a][b] = (r, nc, why)"""
    from collections import defaultdict
    conf = defaultdict(dict); gray = defaultdict(dict)
    for a, b, n, sim, nc in pairs:
        r = s2.get((a, b))
        if not r or a in BAD or b in BAD: continue
        ch = chroma(a, b); r['ch'] = ch; energy = ('energy' in a[2]) or ('energy' in b[2])
        ru = rule(r, nc, ch, energy)
        if ru: conf[a][b] = (r, nc, ru)
        elif gray_rule(r, nc, ch, energy): gray[a][b] = (r, nc, 'abaixo do limite')
    # weaker tiers need support: either the two sets are a known pair (several strong matches between them)
    # or the whole image also agrees at coarse scale. Otherwise the pair goes to the inconclusive list.
    from coarse import coarse
    from collections import Counter
    lineage = Counter()
    for a, c in conf.items():
        for b, v in c.items():
            if v[0].get('n_in', 0) >= 60: lineage[(a[0], b[0])] += 1
    weak = []
    for a, c in conf.items():
        for b, v in c.items():
            ni = v[0].get('n_in', 0)
            if v[2] in ('A3', 'B3', 'B2', 'A5') or (v[2] == 'A2' and ni < 30):
                if lineage[(a[0], b[0])] >= 5: continue
                co = coarse(a, b)
                if co['full'] >= 0.6 and co['art'] >= 0.6 and co['ch'] >= 0.75: continue
                weak.append((a, b))
    for a, b in weak:
        v = conf[a].pop(b); gray[a][b] = (v[0], v[1], 'abaixo do limite')
        if not conf[a]: del conf[a]
    # prune a weak match when a much stronger one exists in the same set on either side:
    # that pattern is a recoloured / alternate version of the art (shiny, rainbow, V-UNION piece), not the same card
    byB = defaultdict(dict)
    for a, c in conf.items():
        for b, v in c.items(): byB[b][a] = v
    drop = []
    for a, c in conf.items():
        for b, v in c.items():
            ni = v[0].get('n_in', 0)
            if v[0]['ncc'] >= 0.9 and v[0]['ch'] >= 0.9 and ni >= 40: continue
            strongA = any(b2 != b and b2[0] == b[0] and v2[0].get('n_in', 0) >= 2.5 * max(ni, 1) for b2, v2 in c.items())
            strongB = any(a2 != a and a2[0] == a[0] and v2[0].get('n_in', 0) >= 2.5 * max(ni, 1) for a2, v2 in byB[b].items())
            if strongA or strongB: drop.append((a, b))
    for a, b in drop:
        v = conf[a].pop(b); gray[a][b] = (v[0], v[1], 'versão diferente provável')
        if not conf[a]: del conf[a]
    return conf, gray, len(drop) + len(weak)
