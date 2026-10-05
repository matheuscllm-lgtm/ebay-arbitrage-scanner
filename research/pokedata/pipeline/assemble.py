"""Etapa 10 — classifica cada carta única: equivalente confirmado, inconclusiva ou exclusiva.

Entrada: pairs_*.pkl, s2_*.pkl, lim_res.pkl, limitless_jobs.json, catalog.pkl   Saída: result.pkl
"""
import pickle, json, re, os
from collections import defaultdict, Counter
from datetime import datetime
from common import *
import rules
from coarse import coarse
from identity import single_language

rows, uinfo = pickle.load(open('catalog.pkl', 'rb'))
sets, cards = load(); units = art_units(cards)
rep = json.load(open('unit_rep.json'))
HAS = {int(f[:-4]) for f in os.listdir('img') if f.endswith('.jpg')}
BAD = {tuple(k) for k in json.load(open('cardback_units.json'))}
def has_img(k):
    c = rep.get(f"{k[0]}|{k[1]}|{k[2]}"); return c is not None and c in HAS and k not in BAD
def sdate(k): return datetime.strptime(sets[k[0]]['release_date'][5:16], '%d %b %Y')
LANG = {k: sets[k[0]]['language'] for k in units}
BASIC = re.compile(r'^(basic)?(grass|fire|water|lightning|psychic|fighting|darkness|metal|fairy|dragon|colorless)energy')
def is_energy(k): return bool(BASIC.match(k[2]))

# ---------------------------------------------------------------- pairwise evidence
CONF = {}; GRAY = {}
for tag in ('EN_JA', 'EN_CH', 'CH_JA'):
    pairs = pickle.load(open(f'pairs_{tag}.pkl', 'rb')); s2 = pickle.load(open(f's2_{tag}.pkl', 'rb'))
    conf, gray, npr = rules.classify(pairs, s2, BAD)
    # coarse whole-image fallback for same-name pairs that SIFT could not settle (textured full arts, foil scans)
    hasB = {b for c in conf.values() for b in c}
    nfb = 0
    for a, b, n, sim, nc in pairs:
        if nc < 1 or sim < 0.3 or a in BAD or b in BAD or is_energy(a) or is_energy(b): continue
        if (a in conf and b in hasB) or b in conf.get(a, {}) or b in gray.get(a, {}): continue
        co = coarse(a, b)
        if (co['full'] >= 0.6 and co['art'] >= 0.6 and co['ch'] >= 0.75) or (co['full'] >= 0.5 and co['art'] >= 0.45 and co['ch'] >= 0.85) or (co['ch'] >= 0.9 and sim >= 0.5):
            r = dict(s2.get((a, b), {})); r.setdefault('n_in', 0); r['ncc'] = co['art']
            gray[a][b] = (r, nc, 'semelhança global, sem pontos suficientes'); nfb += 1
    CONF[tag] = conf; GRAY[tag] = gray
    print(tag, 'units with confirmed', len(conf), 'pairs', sum(len(v) for v in conf.values()), 'pruned', npr, 'fallback gray', nfb, flush=True)

# ---------------------------------------------------------------- Limitless (EN -> JP, BW era onward)
LIM = {}
if os.path.exists('limitless_jobs.json'):
    J = json.load(open('limitless_jobs.json'))
    def nk(c): return key(c.replace('+', 'p'))
    jpsets = defaultdict(list)
    for s in sets.values():
        if s['language'] == 'JAPANESE' and s['code']: jpsets[nk(s['code'])].append(s['id'])
    jpu = defaultdict(list)
    for k in units:
        if LANG[k] == 'JAPANESE':
            m = re.search(r'(\d+)$', k[1])
            if m: jpu[(k[0], int(m.group(1)))].append(k)
    for name, ks in J.items():
        p = f'ext/limitless/{name}.json'
        if not os.path.exists(p): continue
        r = json.load(open(p))
        for k in ks:
            k = tuple(k)
            if r['status'] != 200: LIM[k] = dict(kind='sem página'); continue
            tk = key(r['title'].split(' - ')[0])
            if not (tk and (tk in k[2] or k[2] in tk or tk[:6] == k[2][:6])): LIM[k] = dict(kind='sem página'); continue
            if not r['jp']: LIM[k] = dict(kind='sem impressão japonesa'); continue
            inside = []; outside = []
            for code, num, sname in r['jp']:
                n = re.search(r'(\d+)', num)
                hit = [u for sid in jpsets.get(nk(code), []) for u in jpu.get((sid, int(n.group(1))), [])] if n else []
                (inside if hit else outside).append(f"{sname} ({code}) #{num}")
            LIM[k] = dict(kind='impressão japonesa', inside=inside, outside=outside)
    # targeted image checks of the listed JP prints that PokeData does have
    if os.path.exists('lim_res.pkl'):
        for a, d in pickle.load(open('lim_res.pkl', 'rb')).items():
            for b, v in d.items():
                r = dict(v[2]); ru = rules.rule(r, 2, r.get('ch', 0), is_energy(a)) if 'ch' in r else None
                strong = ru in ('A1', 'A6', 'A4') or (ru == 'A2' and r.get('n_in', 0) >= 30)
                if strong:
                    CONF['EN_JA'].setdefault(a, {})[b] = (r, 2, 'L' + ru)
                elif not is_energy(a) and b not in CONF['EN_JA'].get(a, {}) and (ru or v[0] == 'coarse'):
                    r['ncc'] = v[3]['art']
                    GRAY['EN_JA'].setdefault(a, {})[b] = (r, 2, 'semelhança global, sem pontos suficientes')
    print('Limitless:', Counter(v['kind'] for v in LIM.values()))

# ---------------------------------------------------------------- helpers
def rank(a, cands):
    da = sdate(a)
    def sc(item):
        b, v = item
        nc = v[1] if isinstance(v, tuple) else 1; ni = v[0].get('n_in', 0) if isinstance(v, tuple) else 0
        dd = (da - sdate(b)).days
        return (0 if nc >= 1 else 1, abs(dd) if dd >= -60 else abs(dd) + 400, -ni)
    return [b for b, _ in sorted(cands.items(), key=sc)]
# basic energy: keep the single nearest match (same design is reprinted endlessly)
for tag in CONF:
    for a in list(CONF[tag]):
        c = CONF[tag][a]
        if is_energy(a) and len(c) > 1:
            best = rank(a, c)[0]; CONF[tag][a] = {best: c[best]}
REV = {t: defaultdict(dict) for t in CONF}; REVG = {t: defaultdict(dict) for t in GRAY}
for t in CONF:
    for a, c in CONF[t].items():
        for b, v in c.items(): REV[t][b][a] = v
for t in GRAY:
    for a, c in GRAY[t].items():
        for b, v in c.items(): REVG[t][b][a] = v
# EN -> CN through the Japanese card
VIA = defaultdict(dict)
def strong(v): return v[0].get('n_in', 0) >= 40
for a, c in CONF['EN_JA'].items():
    for j, v1 in c.items():
        if not strong(v1): continue
        for cn, v2 in REV['CH_JA'].get(j, {}).items():
            if strong(v2) and cn not in CONF['EN_CH'].get(a, {}): VIA[a][cn] = j

def partners(k, T):
    """(confirmed dict, gray dict) of unit k towards language T"""
    L = LANG[k]
    if L == 'ENGLISH':
        if T == 'JAPANESE': return CONF['EN_JA'].get(k, {}), GRAY['EN_JA'].get(k, {})
        d = dict(CONF['EN_CH'].get(k, {}))
        for cn, j in VIA.get(k, {}).items(): d.setdefault(cn, 'via')
        return d, GRAY['EN_CH'].get(k, {})
    if L == 'JAPANESE':
        if T == 'ENGLISH': return REV['EN_JA'].get(k, {}), REVG['EN_JA'].get(k, {})
        return REV['CH_JA'].get(k, {}), REVG['CH_JA'].get(k, {})
    if T == 'JAPANESE': return CONF['CH_JA'].get(k, {}), GRAY['CH_JA'].get(k, {})
    d = dict(REV['EN_CH'].get(k, {}))
    for j, v2 in CONF['CH_JA'].get(k, {}).items():
        if not strong(v2): continue
        for e, v1 in REV['EN_JA'].get(j, {}).items():
            if strong(v1): d.setdefault(e, 'via')
    return d, REVG['EN_CH'].get(k, {})

# cards of the same name that cannot be checked because PokeData has no image for them
NOIMG = defaultdict(lambda: defaultdict(list))
for k in units:
    if not has_img(k): NOIMG[LANG[k]][k[2]].append(k)
ORDER = {'JAPANESE': 0, 'ENGLISH': 1, 'CHINESE': 2}   # usual release order
def noimg_cands(k, T):
    out = []
    for c in NOIMG[T].get(k[2], ()):
        first, second = (k, c) if ORDER[LANG[k]] < ORDER[T] else (c, k)
        dd = (sdate(second) - sdate(first)).days       # later-language release minus earlier-language release
        hi = 2600 if 'CHINESE' in (LANG[k], T) else 1100
        if -400 <= dd <= hi: out.append(c)
    return out
LATEST = {L: max(sdate((s['id'],)) for s in sets.values() if s['language'] == L) for L in ORDER}
PRE_BW = {'Call of Legends', 'HeartGold SoulSilver', 'Platinum', 'Diamond & Pearl', 'EX Ruby & Sapphire', 'e-Card', 'Legendary Collection', 'Neo', 'Gym', 'Base'}

STATUS = {}
for k in units:
    L = LANG[k]; st = {}
    for T in ORDER:
        if T == L: continue
        c, g = partners(k, T)
        if c: st[T] = 'confirmado'
        elif not has_img(k): st[T] = 'inconclusivo: carta sem imagem no PokeData'
        elif g:
            why = max(g.values(), key=lambda v: v[0].get('n_in', 0))[2]
            st[T] = 'inconclusivo: ' + ('mesma arte provável, versão ou impressão diferente' if why == 'versão diferente provável' else 'imagem parecida, abaixo do limite de confirmação')
        elif noimg_cands(k, T): st[T] = 'inconclusivo: candidata de mesmo nome sem imagem no PokeData'
        elif is_energy(k): st[T] = 'inconclusivo: energia básica, desenho repetido em muitas impressões'
        else: st[T] = 'não encontrado'
    # language-specific refinements
    if L == 'ENGLISH' and st['JAPANESE'] == 'não encontrado':
        lim = LIM.get(k)
        if lim and lim['kind'] == 'impressão japonesa':
            st['JAPANESE'] = 'inconclusivo: impressão japonesa existe fora do catálogo do PokeData' if not lim['inside'] else 'inconclusivo: mesma carta existe em japonês no PokeData, arte não confirmada'
        elif lim and lim['kind'] == 'sem impressão japonesa':
            st['JAPANESE'] = 'exclusiva: sem impressão japonesa (Limitless)'
        else:
            st['JAPANESE'] = 'inconclusivo: não encontrada no PokeData, exclusividade não comprovada'
    if L == 'JAPANESE' and st['ENGLISH'] == 'não encontrado' and (LATEST['ENGLISH'] - sdate(k)).days < 150:
        st['ENGLISH'] = 'inconclusivo: set recente, versão em inglês pode ainda não ter saído'
    if L == 'CHINESE' and st['JAPANESE'] == 'não encontrado':
        st['JAPANESE'] = 'inconclusivo: não encontrada no PokeData, exclusividade não comprovada'
    # overall bucket: exclusiva only with proven absence in every target language
    # (identity.single_language); absence in the catalogue makes a candidate, not an exclusive
    ev = {T: 'ausente' for T, v in st.items() if v.startswith('exclusiva')}
    st['geral'], st['motivo'] = single_language(L, dict(st), ev)
    STATUS[k] = st

pickle.dump(dict(CONF={t: dict(v) for t, v in CONF.items()}, GRAY={t: dict(v) for t, v in GRAY.items()}, VIA=dict(VIA), STATUS=STATUS, LIM=LIM), open('result.pkl', 'wb'))
c = Counter((LANG[k], st['geral']) for k, st in STATUS.items())
for x in sorted(c): print(x, c[x])
c = Counter()
for k, st in STATUS.items():
    if st['geral'] != 'confirmado':
        for T, v in st.items():
            if T != 'geral': c[(LANG[k][:2], T[:2], v)] += 1
for x in sorted(c): print(x, c[x])
