"""Etapa 9e — classifica os pares indicados pelo Limitless depois da comparação de imagem.

'conf'   = a arte bateu pelas mesmas regras do restante (rules.rule)
'coarse' = só a semelhança global bateu; vai para os inconclusivos como candidata

Entrada: s2_LIM.pkl, cardback_units.json   Saída: lim_res.pkl
"""
import pickle, json
from collections import Counter, defaultdict
import rules
from coarse import coarse

BAD = {tuple(k) for k in json.load(open('cardback_units.json', encoding="utf-8"))}
s2 = pickle.load(open('s2_LIM.pkl', 'rb'))
res = defaultdict(dict); c = Counter()
for (a, b), r in s2.items():
    if a in BAD or b in BAD: c['imagem-marcador'] += 1; continue
    ch = rules.chroma(a, b); r['ch'] = ch
    ru = rules.rule(r, 2, ch, 'energy' in a[2] or 'energy' in b[2])
    co = coarse(a, b)
    if ru: res[a][b] = ('conf', ru, r, co); c['arte confirmada'] += 1
    elif co['full'] >= 0.6 and co['art'] >= 0.6 and co['ch'] >= 0.75: res[a][b] = ('coarse', None, r, co); c['só semelhança global'] += 1
    else: c['arte diferente'] += 1
pickle.dump(dict(res), open('lim_res.pkl', 'wb'))
print(dict(c))
