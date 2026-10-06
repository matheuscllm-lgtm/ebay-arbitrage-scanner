"""Etapa 6 — acha as cartas cuja "imagem" no PokeData é só um marcador.

O site usa o verso da carta (ou outra imagem genérica) quando não tem a foto real.
Critério: a mesma imagem aparece em pelo menos 4 cartas de nomes diferentes.
Essas cartas são tratadas como "sem imagem" na comparação.

Entrada: unit_rep.json, feat_ids_*.json, feat_g_*.npy   Saída: cardback_units.json
"""
import json
import numpy as np
from collections import defaultdict
from common import *

sets, cards = load(); units = art_units(cards)
rep = json.load(open('unit_rep.json', encoding="utf-8"))
ids = {}; G = []
for sh in (0, 1):
    for n, c in enumerate(json.load(open(f'feat_ids_{sh}.json', encoding="utf-8"))): ids[c] = (sh, n)
    G.append(np.load(f'feat_g_{sh}.npy'))

groups = defaultdict(list)
for k in units:
    c = rep.get(f"{k[0]}|{k[1]}|{k[2]}")
    if c in ids:
        sh, n = ids[c]
        groups[G[sh][n][:64].round(2).tobytes()].append(k)
bad = [k for v in groups.values() if len({x[2] for x in v}) >= 4 for k in v]
json.dump([list(k) for k in bad], open('cardback_units.json', 'w', encoding="utf-8"))
print('cartas com imagem-marcador:', len(bad))
