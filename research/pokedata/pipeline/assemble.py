"""Etapa 10 — classifica cada carta única: arte confirmada, provável, inconclusiva, não encontrada.

"Arte confirmada" quer dizer mesma ilustração. Edição, acabamento e carimbo não são conferidos aqui.
Roda duas vezes: antes e depois de lim_jp.py, que consulta listas externas de impressões japonesas.

Entrada: pairs_*.pkl, s2_*.pkl, lim_res.pkl, limitless_jobs.json, catalog.pkl, lim_jp.pkl (se existir)   Saída: result.pkl
"""
import pickle, json, re, os
from collections import defaultdict, Counter
from datetime import datetime
from common import *
import rules
from coarse import coarse
from identity_policy import add_bridge_candidates, overall_status

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
CONF = {}; GRAY = {}; DIRECT_EN_CH = set()
for tag in ('EN_JA', 'EN_CH', 'CH_JA'):
    pairs = pickle.load(open(f'pairs_{tag}.pkl', 'rb')); s2 = pickle.load(open(f's2_{tag}.pkl', 'rb'))
    if tag == 'EN_CH': DIRECT_EN_CH = set(s2)
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
            if not r['jp']:
                LIM[k] = dict(kind='sem impressão japonesa' if r.get('jp_section_valid') is True else 'seção japonesa não validada')
                continue
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

# ---------------------------------------------------------------- faixas: arte confirmada x provável
# Um par aprovado pelas regras de imagem só conta como "arte confirmada" com 40 pontos coincidentes ou mais
# e nomes compatíveis. Os demais ficam como "provável", com o motivo registrado.
M_PTS = 'menos de 40 pontos coincidentes na arte'
M_NOME = 'imagem coincide, mas o nome diverge entre os idiomas no PokeData (tradução diferente ou erro da fonte)'
M_ESP = 'imagem coincide, mas um dos idiomas traz o nome de outro Pokémon (erro de nome ou de imagem no PokeData)'
M_VIA = 'ligada só por meio da carta japonesa, com nome divergente'
def motivo(a, b, v):
    if v[1] == 0:
        da, db = uinfo[a].get('_dex'), uinfo[b].get('_dex')
        return M_ESP if (da and db and da != db) else M_NOME
    if v[0].get('n_in', 0) < 40: return M_PTS
    return ''
PROV = {t: defaultdict(dict) for t in CONF}
for t in CONF:
    for a in list(CONF[t]):
        for b in list(CONF[t][a]):
            v = CONF[t][a][b]; m = motivo(a, b, v)
            if m:
                PROV[t][a][b] = (v[0], v[1], v[2], m); del CONF[t][a][b]
        if not CONF[t][a]: del CONF[t][a]
    print(t, 'arte confirmada:', sum(len(v) for v in CONF[t].values()), 'pares | provável:', Counter(v[3] for d in PROV[t].values() for v in d.values()))

def revd(D):
    out = {t: defaultdict(dict) for t in D}
    for t in D:
        for a, c in D[t].items():
            for b, v in c.items(): out[t][b][a] = v
    return out
REV = revd(CONF); REVP = revd(PROV); REVG = revd(GRAY)

# EN -> CN por meio da carta japonesa: as duas ligações precisam ser "arte confirmada" e não pode haver
# comparação direta EN-CN (se houve e ficou fraca, vale o resultado direto)
TOK = {}
def tok(k):
    if k not in TOK: TOK[k] = set(tokens(units[k][0]['_base']))
    return TOK[k]
def name_compat(a, b):
    if a[2] == b[2]: return 2
    ta, tb = tok(a), tok(b)
    if not ta or not tb: return 0
    if ta <= tb or tb <= ta: return 1
    return 1 if len(ta & tb) / len(ta | tb) >= 0.6 else 0
VIA = defaultdict(dict)
# Preserve the output schema, but indirect links are never confirmations.
add_bridge_candidates(CONF, REV, PROV, GRAY, DIRECT_EN_CH)
REVP = revd(PROV)
REVVIA = defaultdict(dict)
for a, c in VIA.items():
    for cn, j in c.items(): REVVIA[cn][a] = j

def partners(k, T):
    """(arte confirmada, provável, candidatas abaixo do limite) da carta k no idioma T"""
    L = LANG[k]
    if L == 'ENGLISH':
        if T == 'JAPANESE': return CONF['EN_JA'].get(k, {}), PROV['EN_JA'].get(k, {}), GRAY['EN_JA'].get(k, {})
        d = dict(CONF['EN_CH'].get(k, {}))
        for cn in VIA.get(k, {}): d.setdefault(cn, 'via')
        return d, PROV['EN_CH'].get(k, {}), GRAY['EN_CH'].get(k, {})
    if L == 'JAPANESE':
        if T == 'ENGLISH': return REV['EN_JA'].get(k, {}), REVP['EN_JA'].get(k, {}), REVG['EN_JA'].get(k, {})
        return REV['CH_JA'].get(k, {}), REVP['CH_JA'].get(k, {}), REVG['CH_JA'].get(k, {})
    if T == 'JAPANESE': return CONF['CH_JA'].get(k, {}), PROV['CH_JA'].get(k, {}), GRAY['CH_JA'].get(k, {})
    d = dict(REV['EN_CH'].get(k, {}))
    for e in REVVIA.get(k, {}): d.setdefault(e, 'via')
    return d, REVP['EN_CH'].get(k, {}), REVG['EN_CH'].get(k, {})

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

# Listas externas são pistas de cobertura, nunca prova de exclusividade.
LJP = pickle.load(open('lim_jp.pkl', 'rb')) if os.path.exists('lim_jp.pkl') else {}
OK, PR, NE = 'arte confirmada', 'provável', 'não encontrada'

STATUS = {}
for k in units:
    L = LANG[k]; st = {}
    for T in ORDER:
        if T == L: continue
        c, p, g = partners(k, T)
        if c: st[T] = OK
        elif p: st[T] = PR + ': ' + max(p.values(), key=lambda v: v[0].get('n_in', 0))[3]
        elif not has_img(k): st[T] = 'inconclusivo: carta sem imagem no PokeData'
        elif g:
            why = max(g.values(), key=lambda v: v[0].get('n_in', 0))[2]
            st[T] = 'inconclusivo: ' + ('mesma arte provável, versão ou impressão diferente' if why == 'versão diferente provável' else 'imagem parecida, abaixo do limite de confirmação')
        elif noimg_cands(k, T): st[T] = 'inconclusivo: candidata de mesmo nome sem imagem no PokeData'
        elif is_energy(k): st[T] = 'inconclusivo: energia básica, desenho repetido em muitas impressões'
        else: st[T] = NE
    # language-specific refinements
    if L == 'ENGLISH' and st['JAPANESE'] == NE:
        lim = LIM.get(k)
        if lim and lim['kind'] == 'impressão japonesa':
            st['JAPANESE'] = 'inconclusivo: impressão japonesa existe fora do catálogo do PokeData' if not lim['inside'] else 'inconclusivo: mesma carta existe em japonês no PokeData, arte não confirmada'
        elif lim and lim['kind'] == 'sem impressão japonesa':
            st['JAPANESE'] = 'inconclusivo: Limitless não lista impressão japonesa; exclusividade não comprovada'
        elif lim and lim['kind'] == 'seção japonesa não validada':
            st['JAPANESE'] = 'inconclusivo: seção de impressões japonesas ausente ou ilegível'
    if L == 'JAPANESE' and st['ENGLISH'] == NE and (LATEST['ENGLISH'] - sdate(k)).days < 150:
        st['ENGLISH'] = 'inconclusivo: set recente, versão em inglês pode ainda não ter saído'
    # overall bucket. "Não encontrada" não é "exclusiva": exclusiva exige fonte externa dizendo que não há outra impressão.
    vals = list(st.values()); crit = ''
    ov = overall_status(vals)
    if L == 'JAPANESE' and k in LJP and not LJP[k]:
        crit = 'Limitless sem impressão internacional listada; exclusividade não comprovada'
    st['geral'] = ov; st['criterio'] = crit
    STATUS[k] = st

pickle.dump(dict(CONF={t: dict(v) for t, v in CONF.items()}, PROV={t: dict(v) for t, v in PROV.items()}, GRAY={t: dict(v) for t, v in GRAY.items()}, VIA=dict(VIA), STATUS=STATUS, LIM=LIM), open('result.pkl', 'wb'))
c = Counter((LANG[k], st['geral']) for k, st in STATUS.items())
for x in sorted(c): print(x, c[x])
c = Counter()
for k, st in STATUS.items():
    if st['geral'] != OK:
        for T, v in st.items():
            if T in ORDER: c[(LANG[k][:2], T[:2], v)] += 1
for x in sorted(c): print(x, c[x])
