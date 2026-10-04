"""Etapa 9a — lista as cartas em inglês (2011 em diante) ainda sem equivalente japonês confirmado.

Essas cartas são consultadas no Limitless (fetch_limitless.py) para saber se existe
impressão japonesa fora do catálogo do PokeData ou se a carta é exclusiva do inglês.

Entrada: pairs_EN_JA.pkl, s2_EN_JA.pkl, cardback_units.json, ext/ptcg   Saída: limitless_todo.json
"""
import pickle, json
from collections import Counter, defaultdict
import catalog as C          # reaproveita o cruzamento com pokemon-tcg-data (código PTCGO de cada set)
import rules
from common import *

units, sets = C.units, C.sets
BAD = {tuple(k) for k in json.load(open('cardback_units.json'))}
conf, gray, _ = rules.classify(pickle.load(open('pairs_EN_JA.pkl', 'rb')), pickle.load(open('s2_EN_JA.pkl', 'rb')), BAD)

votes = defaultdict(Counter)
for c in C.cards:
    s = sets[c['set_id']]
    if s['language'] != 'ENGLISH': continue
    b = C.en_lookup(c, s, key(c['_base']))
    if b and b[1].get('ptcgoCode'): votes[c['set_id']][b[1]['ptcgoCode']] += 1
code = {sid: v.most_common(1)[0][0] for sid, v in votes.items()}

ERAS = {'Black & White', 'XY', 'Sun & Moon', 'Sword & Shield', 'Scarlet & Violet', 'Mega Evolution'}
todo = [k for k in units if sets[k[0]]['language'] == 'ENGLISH' and sets[k[0]]['series'] in ERAS and k not in conf]
json.dump({'code': {str(k): v for k, v in code.items()}, 'todo': [list(k) for k in todo]}, open('limitless_todo.json', 'w'))
print('cartas em inglês (2011+) sem japonês confirmado:', len(todo))
