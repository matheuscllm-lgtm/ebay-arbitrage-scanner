"""Etapa 3 — monta o catálogo: raridade, nome nativo, total impresso e buscas do eBay de cada registro.

Entrada: sets.json, all_cards.json, ext/   Saída: catalog.pkl
"""
import json, re, csv, os, pickle
from collections import defaultdict, Counter
from datetime import datetime
from common import *

sets, cards = load()
units = art_units(cards)
def sdate(s): return datetime.strptime(s['release_date'][5:16], '%d %b %Y')
def numkey(n):
    n = str(n).strip().upper()
    m = re.match(r'^0*(\d+)$', n)
    return m.group(1) if m else re.sub(r'^([A-Z\-]+?)0+(\d)', r'\1\2', n)

# ---------- species dictionary
sp = defaultdict(dict)
for r in csv.DictReader(open('ext/species_names.csv', encoding='utf-8')): sp[int(r['pokemon_species_id'])][int(r['local_language_id'])] = r['name']
SPK = {}
for i, d in sp.items():
    en = d.get(9)
    if en: SPK[key(en)] = i
SPK.update({'nidoranf': 29, 'nidoranm': 32, 'mrmime': 122, 'mimejr': 439, 'farfetchd': 83, 'sirfetchd': 865, 'hooh': 250, 'porygon2': 233, 'porygonz': 474, 'typenull': 772, 'flabebe': 669, 'mrrime': 866})
REGION = {'alolan': ('アローラ', '阿罗拉', '阿羅拉'), 'galarian': ('ガラル', '伽勒尔', '伽勒爾'), 'hisuian': ('ヒスイ', '洗翠', '洗翠'), 'paldean': ('パルデア', '帕底亚', '帕底亞')}
SUFFIX = ['vmax', 'vstar', 'v-union', 'vunion', 'gx', 'ex', 'v', 'break', 'lv.x', 'lvx', 'legend', 'prime', 'star']
def species_of(base):
    toks = tokens(base.replace('♀', ' f').replace('♂', ' m'))
    best = None
    for n in (3, 2, 1):
        for i in range(len(toks) - n + 1):
            k = ''.join(toks[i:i + n])
            if k in SPK:
                if best is None: best = (SPK[k], i, n)
        if best: break
    return best, toks
def native_one(base):
    """returns (ja, zh_hans, zh_hant) names for a pokemon card or (None,)*3"""
    b, toks = species_of(base)
    if not b: return None, None, None, None
    sid, i, n = b
    d = sp[sid]
    pre = toks[:i]; post = toks[i + n:]
    reg = next((REGION[t] for t in pre if t in REGION), ('', '', ''))
    mega = 'mega' in pre or (pre and pre[-1] == 'm')
    suf = ''
    raw = base
    m = re.search(r'(?:[\s\-])(VMAX|VSTAR|V-UNION|GX|EX|ex|V|BREAK|LV\.?X|Lv\.?X|LEGEND)\b', raw)
    if m: suf = m.group(1)
    xy = ''
    if mega:
        for t in post:
            if t in ('x', 'y'): xy = t.upper()
    ja = reg[0] + ('メガ' if mega else '') + d.get(1, '') + xy + ((' ' + suf) if suf.upper() in ('GX', 'EX', 'BREAK', 'LEGEND') and suf != 'ex' else suf)
    hs = reg[1] + ('超级' if mega else '') + d.get(12, '') + xy + suf
    ht = reg[2] + ('超級' if mega else '') + d.get(4, '') + xy + suf
    return ja.strip(), hs.strip(), ht.strip(), sid

def native(base):
    """native names; tag-team style names (A & B) translate each Pokémon"""
    if '&' in base or ' and ' in base.lower():
        parts = [p.strip() for p in re.split(r'\s*&\s*|\s+and\s+', base, flags=re.I) if p.strip()]
        res = [native_one(p) for p in parts]
        if len(parts) >= 2 and all(r[3] for r in res):
            suf = re.search(r'(GX|ex|EX|V)$', re.sub(r'\s*(Tag Team|TAG TEAM)\s*$', '', base).strip())
            strip = lambda t: re.sub(r'\s*(GX|ex|EX|V)$', '', t)
            sfx = suf.group(1) if suf else ('GX' if re.search(r'tag team', base, re.I) else '')
            return ('&'.join(strip(r[0]) for r in res) + sfx, '&'.join(strip(r[1]) for r in res) + sfx, '&'.join(strip(r[2]) for r in res) + sfx, res[0][3])
    return native_one(base)

# ---------- EN enrichment (pokemon-tcg-data)
P = json.load(open('ext/ptcg_sets_en.json'))
pidx = defaultdict(list)
for p in P:
    pd = datetime.strptime(p['releaseDate'], '%Y/%m/%d')
    for x in json.load(open(f"ext/ptcg/{p['id']}.json")):
        pidx[numkey(x['number'])].append((p, pd, x, key(x['name'])))
def en_lookup(c, s, nk_):
    best = None
    for p, pd, x, kx in pidx.get(numkey(c['num']), ()):
        if abs((pd - sdate(s)).days) > 120: continue
        if kx == nk_ or kx in nk_ or nk_ in kx:
            sc = (kx == nk_, -abs((pd - sdate(s)).days))
            if best is None or sc > best[0]: best = (sc, p, x)
    return best

# ---------- JP enrichment (TCGdex) : set mapping by date + species agreement
ja = [c for c in json.load(open('ext/tcgdex_cards_ja.json')) if c]
tmeta = {}
for st in json.load(open('ext/tcgdex_sets_ja.json')):
    p = f"ext/tcgdex_sets/ja__{st['id'].replace('/', '_')}.json"
    if os.path.exists(p):
        d = json.load(open(p)); tmeta[st['id']] = d
tj = defaultdict(list)
for c in ja: tj[c['set']['id']].append(c)
bys = defaultdict(list)
for c in cards: bys[c['set_id']].append(c)
jp_map = {}; jp_mode = {}
JSP = {d.get(1): i for i, d in sp.items() if d.get(1)}
def tdex(x):
    if x.get('dexId'): return x['dexId'][0]
    n = x.get('name') or ''
    best = None
    for jn, i in JSP.items():
        if jn in n and (best is None or len(jn) > len(best[0])): best = (jn, i)
    return best[1] if best else None
for tid in tj:
    for x in tj[tid]: x['_dex'] = tdex(x)
for sid, s in sets.items():
    if s['language'] != 'JAPANESE': continue
    mine = defaultdict(list); myspecies = Counter()
    for c in bys[sid]:
        kb = key(split_name(c['name'])[0]); mine[numkey(c['num'])].append(kb)
    for k_ in {(c['num'], key(split_name(c['name'])[0])) for c in bys[sid]}:
        b, _ = species_of(k_[1]) if False else (None, None)
    best = None
    for tid, tc in tj.items():
        rd = tmeta.get(tid, {}).get('releaseDate')
        if not rd: continue
        dd = abs((datetime.strptime(rd, '%Y-%m-%d') - sdate(s)).days)
        samecode = key(s['code'] or '') == key(tid) or key((s['code'] or '').replace('+', 'p')) == key(tid)
        if dd > 45 and not (samecode and dd < 500): continue
        hit = tot = 0
        for x in tc:
            if not x['_dex']: continue
            en = key(sp[x['_dex']].get(9, ''))
            k = numkey(x['localId'])
            if k in mine:
                tot += 1
                if any(en and en in m for m in mine[k]): hit += 1
        if tot >= 3 and hit / tot >= 0.9 and (best is None or hit > best[1]): best = (tid, hit, tot, 'num')
        elif dd <= 10 and best is None:
            # species-only agreement (vintage sets numbered differently)
            ts = Counter(key(sp[x['_dex']].get(9, '')) for x in tc if x['_dex'])
            ms = [m for v in mine.values() for m in v]
            h = sum(1 for t in ts if any(t in m for m in ms))
            if len(ts) >= 10 and h / len(ts) >= 0.85: best = (tid, h, len(ts), 'species')
    if best: jp_map[sid] = best[0]; jp_mode[sid] = best[3]
tjidx = {tid: {numkey(x['localId']): x for x in tc} for tid, tc in tj.items()}
tjsp = {}
for tid, tc in tj.items():
    cnt = Counter(x['_dex'] for x in tc if x['_dex'])
    tjsp[tid] = {x['_dex']: x for x in tc if x['_dex'] and cnt[x['_dex']] == 1}
TW = {st['id']: st['name'] for st in json.load(open('ext/tcgdex_sets_zh-tw.json'))}
CNSET = {st['id']: st['name'] for st in json.load(open('ext/tcgdex_sets_zh-cn.json')) if st['id'].startswith('C')}
CNSET['CS1aC'] = '极巨争锋 雷'; CNSET['CSV1C'] = '亘古开来'; CNSET['CBB1C'] = '宝石包 Vol.1'
RAR_JP = {'Common': 'C', 'Uncommon': 'U', 'Rare': 'R', 'Double rare': 'RR', 'Triple Rare': 'RRR', 'Illustration rare': 'AR', 'Special illustration rare': 'SAR', 'Character Rare': 'CHR', 'Character Super Rare': 'CSR', 'Shiny rare': 'S', 'Shiny Ultra Rare': 'SSR', 'ACE SPEC Rare': 'ACE', 'Radiant Rare': 'K', 'Ultra Rare': 'SR', 'Hyper rare': 'UR/HR', 'Mega Hyper Rare': 'MUR', 'Black White Rare': 'BWR', 'Promo': 'PROMO'}
RAR_EN = {'Special Illustration Rare': 'SIR', 'Illustration Rare': 'IR', 'Hyper Rare': 'Gold', 'Rare Rainbow': 'Rainbow', 'Rare Secret': 'Secret', 'Trainer Gallery Rare Holo': 'TG', 'Rare Holo VMAX': 'VMAX', 'Rare Holo V': 'V', 'Rare Ultra': 'Full Art', 'Ultra Rare': 'Full Art', 'Double Rare': 'Double Rare', 'ACE SPEC Rare': 'ACE SPEC', 'Shiny Rare': 'Shiny', 'Shiny Ultra Rare': 'Shiny Full Art', 'Rare Shiny': 'Shiny', 'Amazing Rare': 'Amazing Rare', 'Radiant Rare': 'Radiant', 'Rare Holo': 'Holo'}

# ---------- per-set printed total
def set_total(sid):
    sec = [int(c['num']) for c in bys[sid] if c['secret'] and re.fullmatch(r'\d+', str(c['num']))]
    return (min(sec) - 1) if sec and min(sec) > 1 else None
TOTAL = {sid: set_total(sid) for sid in sets}
for sid, tid in jp_map.items():
    off = (tmeta.get(tid, {}).get('cardCount') or {}).get('official')
    if off and jp_mode.get(sid) == 'num': TOTAL[sid] = off
LANGPT = {'ENGLISH': 'Inglês', 'JAPANESE': 'Japonês', 'CHINESE': 'Chinês simplificado'}

def build():
    rows = []; uinfo = {}
    stats = Counter()
    votes = defaultdict(Counter)
    for c in cards:
        s = sets[c['set_id']]
        if s['language'] != 'ENGLISH' or not str(c['num']).isdigit(): continue
        b = en_lookup(c, s, key(c['_base']))
        if b and b[1].get('printedTotal'): votes[c['set_id']][b[1]['printedTotal']] += 1
    for sid, v in votes.items(): TOTAL[sid] = v.most_common(1)[0][0]
    for c in cards:
        s = sets[c['set_id']]; lang = s['language']
        base, tags = c['_base'], c['_tags']
        nk_ = key(base); uk = (c['set_id'], c['num'], nk_)
        code = s['code'] or ''
        rar = ''; rar_src = ''; ill = ''; nat = ''; setnat = ''; oficial = ''; alt_code = ''
        num = str(c['num']); code = s['code'] or ''; jp_abbr = ''
        ja_n, hs_n, ht_n, dex = native(base)
        if lang == 'ENGLISH':
            b = en_lookup(c, s, nk_)
            if b:
                rar = b[2].get('rarity', '') or ''; ill = b[2].get('artist', '') or ''; rar_src = 'pokemon-tcg-data'; stats['en_rar'] += 1
                oficial = b[2]['name']; alt_code = b[1].get('ptcgoCode') or ''
        elif lang == 'JAPANESE':
            tid = jp_map.get(c['set_id'])
            if tid:
                if jp_mode.get(c['set_id']) == 'species':
                    x = tjsp[tid].get(dex) if dex and sum(1 for o in bys[c['set_id']] if native(split_name(o['name'])[0])[3] == dex and o['num'] != num) == 0 else None
                else:
                    x = tjidx[tid].get(numkey(num))
                if x:
                    en = key(sp[x['_dex']].get(9, '')) if x.get('_dex') else None
                    if en is None or en in nk_:
                        if x.get('rarity') and x['rarity'] != 'None':
                            rr = x['rarity']; mega = s['series'] == 'MEGA'; sv = s['series'] == 'Scarlet & Violet'
                            ab = RAR_JP.get(rr, '')
                            if rr == 'Mega Hyper Rare': ab = 'MUR' if mega else 'UR'; rr = 'Mega Hyper Rare' if mega else 'Ultra Rare, ouro'
                            if rr == 'Hyper rare': ab = 'UR' if (sv or mega) else 'HR'
                            jp_abbr = ab
                            rar = f"{ab} ({rr})" if ab and ab != 'PROMO' else rr; rar_src = 'TCGdex'; stats['jp_rar'] += 1
                        ill = x.get('illustrator') or ''; nat = x.get('name') or ''
                setnat = tmeta.get(tid, {}).get('name', '')
            if not nat and ja_n: nat = ja_n
        else:
            setnat = CNSET.get(code, '')
            if hs_n: nat = hs_n
        tot = TOTAL.get(c['set_id'])
        num = str(c['num'])
        promo = code.upper().endswith('-P') or 'promo' in s['name'].lower()
        mp = re.match(r'^([A-Za-z&]+-P)\b', s['name'])
        pcode = code if code.upper().endswith('-P') else (mp.group(1) if mp else '')
        if promo: numtxt = f"{num}/{pcode}" if (pcode and lang != 'ENGLISH') else num
        elif tot and num.isdigit() and tot >= int(num) * 0 and (lang != 'JAPANESE' or code): numtxt = f"{num}/{str(tot).zfill(len(num))}"
        else: numtxt = num
        # eBay terms
        variant = ' '.join(t for t in tags if t in ('Reverse Holo', '1st Edition', 'Shadowless', 'Prerelease', 'Staff', 'Prerelease Staff', 'Cosmos Holo', 'Cracked Ice Holo', 'Stamped'))
        if lang == 'ENGLISH':
            sname = oficial or base
            main = ' '.join(x for x in [sname, numtxt, s['name'], variant] if x)
            alts = [' '.join(x for x in [sname, code, num, variant] if x)] if code else []
            if oficial and key(oficial) != nk_: alts.append(' '.join(x for x in [base, num, s['name']] if x))
            if alt_code and alt_code.upper() != code.upper(): alts.append(' '.join(x for x in [sname, alt_code, num] if x))
            if rar in RAR_EN and RAR_EN[rar].lower() not in sname.lower().split(): alts.append(f"{sname} {RAR_EN[rar]} {s['name']}")
        elif lang == 'JAPANESE':
            dup = bool(code) and numtxt.endswith('/' + code)
            main = ' '.join(x for x in [base, numtxt, '' if dup else (code or s['name']), 'Japanese', variant] if x)
            alts = [f"{base} {s['name']} Japanese {num}".strip()]
            if nat: alts.append(' '.join(x for x in [nat, '' if dup else (code or setnat), numtxt] if x))
            if jp_abbr and jp_abbr != 'PROMO': alts.append(f"{base} {jp_abbr} {code} Japanese".replace('  ', ' '))
            if setnat: alts.append(f"{setnat} {num}")
        else:
            dup = bool(code) and numtxt.endswith('/' + code)
            main = ' '.join(x for x in [base, numtxt, '' if dup else code, 'Chinese', variant] if x)
            alts = [f"{base} {num} S-Chinese Simplified {s['name']}", ]
            if nat: alts.append(' '.join(x for x in [nat, code, numtxt, '简体中文'] if x))
            if setnat: alts.append(f"{setnat} {num} 简中")
        row = dict(idioma=LANGPT[lang], era=s['series'], set_nome=s['name'], set_codigo=code, set_data=sdate(s).strftime('%Y-%m-%d'), set_nome_nativo=setnat,
                   numero=num, numero_impresso=numtxt, nome=c['name'], nome_base=base, variante=' + '.join(tags), raridade=rar, fonte_raridade=rar_src, secreta='sim' if c['secret'] else '',
                   nome_nativo=nat, nome_oficial=oficial, ilustrador=ill, ebay_principal=re.sub(r'\s+', ' ', main).replace('Japanese Japanese', 'Japanese').strip(), ebay_alternativos=' | '.join(dict.fromkeys(re.sub(r'\s+', ' ', a).replace('Japanese Japanese', 'Japanese').strip() for a in alts if a)),
                   pokedata_id=c['id'], tcgplayer_id=c.get('tcgplayer_id') or '', imagem='' if 'placeholder' in c['img_url'] else c['img_url'], _uk=uk, _lang=lang, _dex=dex)
        rows.append(row)
        if uk not in uinfo or (not uinfo[uk]['variante'] is False and len(row['nome']) < len(uinfo[uk]['nome'])): uinfo[uk] = row
    return rows, uinfo, stats
if __name__ == '__main__':
    rows, uinfo, stats = build()
    pickle.dump((rows, uinfo), open('catalog.pkl', 'wb'))
    print(len(rows), len(uinfo), stats, 'jp sets mapped', len(jp_map))
    c = Counter((r['idioma'], bool(r['raridade'])) for r in rows); print(c)
    c = Counter((r['idioma'], bool(r['nome_nativo'])) for r in rows); print('native', c)
    import random; random.seed(7)
    for r in random.sample(rows, 14): print({k: v for k, v in r.items() if k in ('idioma', 'set_codigo', 'numero_impresso', 'nome', 'raridade', 'nome_nativo', 'ebay_principal', 'ebay_alternativos')})
    print([(sets[k]['name'], sets[k]['code'], v) for k, v in list(jp_map.items())[:200] if key(sets[k]['code'] or '') != key(v)])
