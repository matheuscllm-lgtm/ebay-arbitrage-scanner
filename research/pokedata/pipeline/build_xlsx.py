"""Etapa 12 — monta a planilha de entrega. Uso: python build_xlsx.py saida.xlsx [planilha do PR #53]

Entrada: catalog.pkl, result.pkl   Saída: planilha (11 abas; 13 com a planilha do PR #53) e tables.pkl
Com a planilha do PR #53, acrescenta a cobertura das referências dela e os registros em chinês tradicional.
Depois de gerar, recalcular as fórmulas no LibreOffice ou abrir e salvar no Excel.
"""
import pickle, json, re, os, sys
from collections import defaultdict, Counter
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from common import *
from reference_match import number_norm, resolve_reference

OUT = sys.argv[1] if len(sys.argv) > 1 else 'PokeData_catalogo_correspondencia.xlsx'
PR53 = sys.argv[2] if len(sys.argv) > 2 else None
rows, uinfo = pickle.load(open('catalog.pkl', 'rb'))
R = pickle.load(open('result.pkl', 'rb')); CONF, PROV, GRAY, VIA, STATUS, LIM = R['CONF'], R['PROV'], R['GRAY'], R['VIA'], R['STATUS'], R['LIM']
OK, PR, NE = 'arte confirmada', 'provável', 'não encontrada'
sets, cards = load(); units = art_units(cards)
LANG = {k: sets[k[0]]['language'] for k in units}
def sdate(k): return datetime.strptime(sets[k[0]]['release_date'][5:16], '%d %b %Y')
def revd(D):
    out = {t: defaultdict(dict) for t in D}
    for t in D:
        for a, c in D[t].items():
            for b, v in c.items(): out[t][b][a] = v
    return out
REV = revd(CONF); REVP = revd(PROV); REVG = revd(GRAY)
REVVIA = defaultdict(dict)
for a, c in VIA.items():
    for cn, j in c.items(): REVVIA[cn][a] = j
def rank(a, cands):
    da = sdate(a)
    def sc(item):
        b, v = item
        nc = v[1] if isinstance(v, tuple) else 1; ni = v[0].get('n_in', 0) if isinstance(v, tuple) else 0
        dd = (da - sdate(b)).days
        return (0 if nc >= 1 else 1, abs(dd) if dd >= -60 else abs(dd) + 400, -ni)
    out = []; seen = set()
    for b, _ in sorted(cands.items(), key=sc):
        sig = b  # Full art-unit key: set, full number and name. No guessed alias merge.
        if sig in seen: continue
        seen.add(sig); out.append(b)
    return out
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
LANGS = ('ENGLISH', 'JAPANESE', 'CHINESE')
EQ = {k: {T: rank(k, partners(k, T)[0]) for T in LANGS if T != LANG[k]} for k in units}    # arte confirmada
EQP = {k: {T: rank(k, partners(k, T)[1]) for T in LANGS if T != LANG[k]} for k in units}   # provável

main_row = {}
for r in rows:
    k = r['_uk']
    if k not in main_row or (bool(r['variante']), len(r['nome'])) < (bool(main_row[k]['variante']), len(main_row[k]['nome'])): main_row[k] = r
def nm(k):
    u = main_row[k]; return u.get('nome_oficial') or u['nome_base']
def code(k):
    u = main_row[k]; return f"{u['set_codigo'] or u['set_nome']} {u['numero']}"
VAR_RX = re.compile(r'\s+(?:Reverse Holo|1st Edition|Shadowless|Prerelease Staff|Prerelease|Staff|Cosmos Holo|Cracked Ice Holo|Stamped)(?=\s|$)')
def busca(k):
    s = main_row[k]['ebay_principal']
    while VAR_RX.search(s): s = VAR_RX.sub('', s)
    return s.strip()
tags_by_unit = defaultdict(list); recs_by_unit = defaultdict(list)
for r in rows:
    recs_by_unit[r['_uk']].append(r)
    if r['variante']: tags_by_unit[r['_uk']].append(r['variante'])
def variants(k): return ', '.join(dict.fromkeys(tags_by_unit.get(k, [])))
# registro cuja imagem entrou na comparação (um por carta única); os outros registros da carta são variantes não comparadas
rep = json.load(open('unit_rep.json'))
def rep_row(k):
    cid = rep.get(f"{k[0]}|{k[1]}|{k[2]}")
    for r in recs_by_unit[k]:
        if r['pokedata_id'] == cid: return r
    return None
SEM = 'sem marcação'
def comparado(k):
    r = rep_row(k); return (r['variante'] or SEM) if r else 'sem imagem'
def outras(k):
    r = rep_row(k)
    return ', '.join(dict.fromkeys((x['variante'] or SEM) for x in recs_by_unit[k] if x is not r))
def unico(k): return len(recs_by_unit[k]) == 1 and not recs_by_unit[k][0]['variante']
V_UNICO = 'registro único e sem marcação em todos os idiomas da linha'
V_CONF = 'há variantes ou marcação de edição/acabamento: conferir a versão'
PT = {'ENGLISH': 'Inglês', 'JAPANESE': 'Japonês', 'CHINESE': 'Chinês simplificado'}
ABR = {'ENGLISH': 'EN', 'JAPANESE': 'JP', 'CHINESE': 'CN'}
ERA_ORDER = {}
for s in sets.values():
    d = datetime.strptime(s['release_date'][5:16], '%d %b %Y'); kq = (s['language'], s['series'])
    if kq not in ERA_ORDER or d > ERA_ORDER[kq]: ERA_ORDER[kq] = d
def numsort(n):
    m = re.search(r'(\d+)', n); return (int(m.group(1)) if m else 10 ** 6, n)
def ukey(k): return (LANGS.index(LANG[k]), -ERA_ORDER[(LANG[k], sets[k[0]]['series'])].timestamp(), -sdate(k).timestamp(), sets[k[0]]['name'], numsort(k[1]), k[2])

wb = Workbook()
wb._named_styles['Normal'].font = Font(name='Arial', size=10)
HF = Font(name='Arial', size=10, bold=True, color='FFFFFF'); HFILL = PatternFill('solid', fgColor='1F3864')
def sheet(name, header, data, widths=None, freeze='A2'):
    ws = wb.create_sheet(name)
    ws.append(header)
    for c in ws[1]: c.font = HF; c.fill = HFILL; c.alignment = Alignment(vertical='center', wrap_text=True)
    for row in data: ws.append(row)
    ws.freeze_panes = freeze
    ws.auto_filter.ref = f"A1:{get_column_letter(len(header))}{max(len(data) + 1, 2)}"
    for i, h in enumerate(header, 1):
        ws.column_dimensions[get_column_letter(i)].width = (widths or {}).get(h, max(11, min(40, len(h) + 4)))
    return ws

# ---------------- catalogs
CAT_H = ['set_id', 'Idioma', 'Era', 'Set', 'Código do set', 'Nome nativo do set', 'Lançamento', 'Número', 'Número impresso', 'Nome (PokeData)', 'Nome base', 'Nome oficial (EN)', 'Variante / acabamento', 'Raridade', 'Fonte da raridade', 'Secreta', 'Nome no idioma original', 'Ilustrador', 'Busca eBay principal', 'Buscas eBay alternativas', 'Carta única', 'Situação geral', 'Equivalente EN', 'Equivalente JP', 'Equivalente CN simplificado', 'Códigos equivalentes', 'Candidatas prováveis', 'Imagem comparada', 'ID PokeData', 'ID TCGplayer', 'Imagem']
COL = {h: get_column_letter(i) for i, h in enumerate(CAT_H, 1)}
CAT_W = {'Set': 34, 'Nome (PokeData)': 34, 'Nome base': 28, 'Busca eBay principal': 46, 'Buscas eBay alternativas': 70, 'Códigos equivalentes': 50, 'Imagem': 30, 'Nome no idioma original': 22, 'Nome nativo do set': 22, 'Variante / acabamento': 20, 'Equivalente EN': 30, 'Equivalente JP': 30, 'Equivalente CN simplificado': 30, 'Situação geral': 16, 'Candidatas prováveis': 40, 'Imagem comparada': 34}
def eqcodes(k, E=EQ):
    parts = []
    for T in LANGS:
        e = E[k].get(T, [])
        if e: parts.append(f"{ABR[T]}: " + '; '.join(code(x) for x in e[:6]) + (f" (+{len(e) - 6})" if len(e) > 6 else ''))
    return ' | '.join(parts)
def alcance(k, r):
    """diz se a imagem deste registro foi a comparada; os demais registros da carta são variantes não conferidas"""
    if STATUS[k]['geral'] not in (OK, PR): return ''
    if rep_row(k) is r: return 'sim'
    return 'não: variante da mesma carta; edição e acabamento não conferidos'
def st(k, T): return '—' if T == LANG[k] else STATUS[k].get(T, '')
cat = defaultdict(list)
for r in sorted(rows, key=lambda r: ukey(r['_uk']) + (r['nome'],)):
    k = r['_uk']
    cat[r['_lang']].append([k[0], r['idioma'], r['era'], r['set_nome'], r['set_codigo'], r['set_nome_nativo'], r['set_data'], r['numero'], r['numero_impresso'], r['nome'], r['nome_base'], r.get('nome_oficial', ''), r['variante'], r['raridade'], r['fonte_raridade'], r['secreta'], r['nome_nativo'], r['ilustrador'], r['ebay_principal'], r['ebay_alternativos'], 1 if main_row[k] is r else 0, STATUS[k]['geral'], st(k, 'ENGLISH'), st(k, 'JAPANESE'), st(k, 'CHINESE'), eqcodes(k), eqcodes(k, EQP), alcance(k, r), r['pokedata_id'], r['tcgplayer_id'], r['imagem']])

# ---------------- correspondence (EN anchored): só equivalentes com arte confirmada
COR_H = ['Era (EN)', 'Set (EN)', 'Código (EN)', 'Número (EN)', 'Nome (EN)', 'Raridade (EN)', 'Busca eBay (EN)',
         'Situação JP', 'Set (JP)', 'Código (JP)', 'Número (JP)', 'Nome no PokeData (JP)', 'Nome japonês', 'Raridade (JP)', 'Busca eBay (JP)', 'Outras impressões JP com a mesma arte',
         'Situação CN simplificado', 'Set (CN)', 'Código (CN)', 'Número (CN)', 'Nome no PokeData (CN)', 'Nome chinês', 'Busca eBay (CN)', 'Outras impressões CN com a mesma arte', 'Observações',
         'Pontos coincidentes JP', 'Pontos coincidentes CN', 'Versão', 'Registro comparado (EN)', 'Outras variantes (EN)', 'Registro comparado (JP)', 'Outras variantes (JP)', 'Registro comparado (CN)', 'Outras variantes (CN)', 'Cartas do PokeData nesta linha']
groups = {}
for k in sorted([k for k in units if LANG[k] == 'ENGLISH'], key=ukey):
    e = EQ[k]
    if not e['JAPANESE'] and not e['CHINESE']: continue
    # Preserve unidades distintas; aliases precisam de validação explícita.
    sig = k  # Keep distinct source units until an explicit alias map is validated.
    groups.setdefault(sig, []).append(k)
cor = []
for sig, ks in groups.items():
    k = ks[0]; e = EQ[k]
    u = main_row[k]; obs = []
    row = [u['era'], u['set_nome'], u['set_codigo'], u['numero_impresso'], nm(k), u['raridade'], busca(k)]
    pj = pc = ''; j = c = None
    if e['JAPANESE']:
        j = e['JAPANESE'][0]; ju = main_row[j]; v = CONF['EN_JA'][k][j]
        row += [OK, ju['set_nome'], ju['set_codigo'], ju['numero_impresso'], ju['nome_base'], ju['nome_nativo'], ju['raridade'], busca(j), '; '.join(code(x) for x in e['JAPANESE'][1:])]
        pj = v[0].get('n_in', 0)
    else: row += [STATUS[k]['JAPANESE'], '', '', '', '', '', '', '', '']
    if e['CHINESE']:
        c = e['CHINESE'][0]; cu = main_row[c]; v = CONF['EN_CH'].get(k, {}).get(c)
        row += [OK, cu['set_nome'], cu['set_codigo'], cu['numero_impresso'], cu['nome_base'], cu['nome_nativo'], busca(c), '; '.join(code(x) for x in e['CHINESE'][1:])]
        if v: pc = v[0].get('n_in', 0)
        else: obs.append('CN ligado por meio da carta japonesa (sem comparação direta EN-CN)')
    else: row += [STATUS[k]['CHINESE'], '', '', '', '', '', '', '']
    vt = variants(k)
    if re.search(r'Prerelease|Staff|Stamped|Pokemon Center|Trophy', vt): obs.append('EN também existe com carimbo: ' + vt)
    if len(ks) > 1: obs.append('PokeData repete esta carta neste set: ' + '; '.join(f"{x[1]} {main_row[x]['nome_base']}" for x in ks[1:]))
    lados = [k] + ([j] if j else []) + ([c] if c else [])
    row += ['; '.join(obs), pj, pc, V_UNICO if all(unico(x) for x in lados) else V_CONF,
            comparado(k), outras(k), comparado(j) if j else '', outras(j) if j else '', comparado(c) if c else '', outras(c) if c else '', len(ks)]
    cor.append(row)

# ---------------- prováveis: pares aprovados pela imagem, mas fora do critério de arte confirmada
PRV_H = ['Par', 'Era (A)', 'Set (A)', 'Código (A)', 'Número (A)', 'Nome (A)', 'Set (B)', 'Código (B)', 'Número (B)', 'Nome no PokeData (B)', 'Nome no idioma original (B)',
         'Motivo', 'Pontos coincidentes', 'Nomes compatíveis', 'A já tem arte confirmada neste idioma', 'Registro comparado (A)', 'Registro comparado (B)', 'Busca eBay (A)', 'Busca eBay (B)']
PAR = {'EN_JA': 'Inglês → Japonês', 'EN_CH': 'Inglês → Chinês simplificado', 'CH_JA': 'Chinês simplificado → Japonês'}
TGT = {'EN_JA': 'JAPANESE', 'EN_CH': 'CHINESE', 'CH_JA': 'JAPANESE'}
prv = []
for t in ('EN_JA', 'EN_CH', 'CH_JA'):
    for a in sorted(PROV[t], key=ukey):
        au = main_row[a]
        for b in rank(a, PROV[t][a]):
            v = PROV[t][a][b]; bu = main_row[b]
            prv.append([PAR[t], au['era'], au['set_nome'], au['set_codigo'], au['numero_impresso'], nm(a), bu['set_nome'], bu['set_codigo'], bu['numero_impresso'], bu['nome_base'], bu['nome_nativo'],
                        v[3], v[0].get('n_in', '') if v[2] != 'via' else '', 'sim' if v[1] >= 1 else 'não', 'sim' if EQ[a][TGT[t]] else 'não', comparado(a), comparado(b), busca(a), busca(b)])

# ---------------- JP-CN pairs without an English card
JC_H = ['Era (JP)', 'Set (JP)', 'Código (JP)', 'Número (JP)', 'Nome no PokeData (JP)', 'Nome japonês', 'Busca eBay (JP)', 'Set (CN)', 'Código (CN)', 'Número (CN)', 'Nome no PokeData (CN)', 'Nome chinês', 'Busca eBay (CN)', 'Outras impressões CN', 'Situação em inglês']
jc = []
for j in sorted([k for k in units if LANG[k] == 'JAPANESE'], key=ukey):
    e = EQ[j]
    if e['ENGLISH'] or not e['CHINESE']: continue
    ju = main_row[j]; c = e['CHINESE'][0]; cu = main_row[c]
    jc.append([ju['era'], ju['set_nome'], ju['set_codigo'], ju['numero_impresso'], ju['nome_base'], ju['nome_nativo'], busca(j), cu['set_nome'], cu['set_codigo'], cu['numero_impresso'], cu['nome_base'], cu['nome_nativo'], busca(c), '; '.join(code(x) for x in e['CHINESE'][1:]), STATUS[j]['ENGLISH']])

# ---------------- inconclusive and exclusive
INC_H = ['Idioma', 'Era', 'Set', 'Código', 'Número', 'Nome', 'Situação geral', 'Situação em inglês', 'Situação em japonês', 'Situação em chinês simplificado', 'Candidata mais próxima', 'Pontos coincidentes', 'Semelhança da arte (0–1)', 'Impressões japonesas segundo o Limitless', 'Busca eBay']
EXC_H = ['Idioma', 'Era', 'Set', 'Código', 'Lançamento', 'Número', 'Nome', 'Nome no idioma original', 'Raridade', 'Variantes', 'Critério', 'Cartas de mesmo nome comparadas (EN)', 'Cartas de mesmo nome comparadas (JP)', 'Cartas de mesmo nome comparadas (CN)', 'Busca eBay']
HASIMG = {int(f[:-4]) for f in os.listdir('img') if f.endswith('.jpg')}
BAD = {tuple(k) for k in json.load(open('cardback_units.json'))}
BYNAME = defaultdict(lambda: defaultdict(int))
for k in units:
    if rep.get(f"{k[0]}|{k[1]}|{k[2]}") in HASIMG and k not in BAD: BYNAME[LANG[k]][k[2]] += 1
inc = []; exc = []
for k in sorted(units, key=ukey):
    u = main_row[k]; stt = STATUS[k]
    if stt['geral'] in ('inconclusivo', NE):
        best = None
        for T in LANGS:
            if T == LANG[k]: continue
            for b, v in partners(k, T)[2].items():
                if best is None or v[0].get('n_in', 0) > best[1][0].get('n_in', 0): best = (b, v)
        cand = pts = sim = ''
        if best:
            b, v = best; cand = f"{ABR[LANG[b]]} {code(b)} {main_row[b]['nome_base']}"; pts = v[0].get('n_in', 0); sim = round(max(v[0].get('ncc', 0), 0), 2)
        lim = LIM.get(k); limtxt = ''
        if lim and lim['kind'] == 'impressão japonesa': limtxt = '; '.join((lim['outside'] + lim['inside'])[:6])
        inc.append([PT[LANG[k]], u['era'], u['set_nome'], u['set_codigo'], u['numero_impresso'], nm(k), stt['geral'], st(k, 'ENGLISH'), st(k, 'JAPANESE'), st(k, 'CHINESE'), cand, pts, sim, limtxt, busca(k)])
    elif stt['geral'] == 'exclusiva':
        crit = stt['criterio']
        exc.append([PT[LANG[k]], u['era'], u['set_nome'], u['set_codigo'], u['set_data'], u['numero_impresso'], nm(k), u['nome_nativo'], u['raridade'], variants(k), crit] + [(BYNAME[T][k[2]] if LANG[k] != T else '—') for T in LANGS] + [busca(k)])

# ---------------- referências e chinês tradicional do PR #53 (opcional)
COV_H = ['ID EN (PR #53)', 'Carta inglesa — referência', 'Código EN', 'Set EN', 'Localização neste catálogo', 'Variante da referência', 'Imagem comparada',
         'Situação geral (esta rodada)', 'Situação JP (esta rodada)', 'Código JP', 'Pontos JP', 'Situação CN simplificado (esta rodada)', 'Código CN', 'Pontos CN', 'Versão',
         'Status JP (PR #53)', 'Status simplificado (PR #53)', 'Status tradicional (PR #53)']
CHT_H = ['ID EN (PR #53)', 'Carta inglesa — referência', 'Código EN', 'Set EN', 'Nome local (繁體)', 'Código local completo', 'Set / produto local', 'Raridade e acabamento',
         'Status (PR #53)', 'Como foi validada (PR #53)', 'Fonte local', 'Situação JP nesta rodada', 'Código JP nesta rodada', 'Origem']
cov = []; cht = []
if PR53:
    from openpyxl import load_workbook
    wbp = load_workbook(PR53, read_only=True, data_only=True)
    def table(name):
        hdr = None; out = []
        for row in wbp[name].iter_rows(min_row=4, values_only=True):
            if hdr is None: hdr = [str(h) for h in row]; continue
            if row[0] is not None: out.append(dict(zip(hdr, row)))
        return out
    by_num = defaultdict(list)
    for r in rows:
        if r['_lang'] != 'ENGLISH': continue
        by_num[(r['set_nome'].lower(), number_norm(r['numero']))].append(r)
    def locate(d):
        """registro deste catálogo que corresponde à referência do PR #53 (que é um registro do PokeData, com variante).
        Sem desempate às cegas: mais de um candidato vira 'ambíguo'; nome contido ou diferente não localiza
        (antes, o primeiro candidato era escolhido e herdava a situação de outra carta). Regras em reference_match.py."""
        cands = [dict(id=x['pokedata_id'], nome=x['nome'], unidade=x['_uk'], numero=x['numero'], row=x)
                 for x in by_num.get((str(d['Set EN']).lower(), number_norm(d['Código EN'])), [])]
        uk, c, how = resolve_reference(d['Carta inglesa — referência'], d['Código EN'], cands)
        if uk is None: return None, False, how
        if c is not None: return c['row'], True, how
        return main_row[uk], False, how
    def lado(k, T):
        c, pv, _ = partners(k, T)
        if EQ[k][T]:
            x = EQ[k][T][0]; v = c[x]; return STATUS[k][T], code(x), (v[0].get('n_in', '') if isinstance(v, tuple) else ''), x
        if EQP[k][T]:
            x = EQP[k][T][0]; v = pv[x]; return STATUS[k][T], code(x), (v[0].get('n_in', '') if v[2] != 'via' else ''), None
        return STATUS[k][T], '', '', None
    for d in table('Cobertura EN'):
        r, exato, how = locate(d)
        base = [d['ID EN'], d['Carta inglesa — referência'], d['Código EN'], d['Set EN'], how]
        fim = [d['Status JP'], d['Status simplificado'], d['Status tradicional']]
        if r is None: cov.append(base + ['', '', how.split(':')[0], '', '', '', '', '', '', ''] + fim); continue
        k = r['_uk']; sj, cj, pj, xj = lado(k, 'JAPANESE'); sc, cc, pc, xc = lado(k, 'CHINESE')
        lados = [k] + [x for x in (xj, xc) if x]
        ver = '' if len(lados) == 1 else (V_UNICO if all(unico(x) for x in lados) else V_CONF)
        comp = '' if not exato else ('sim' if rep_row(k) is r else 'não: variante da mesma carta; edição e acabamento não conferidos')
        cov.append(base + [(r['variante'] or SEM) if exato else '', comp, STATUS[k]['geral'], sj, cj, pj, sc, cc, pc, ver] + fim)
    for d in table('Detalhes confirmados'):
        if d['Idioma'] != 'Chinês tradicional': continue
        r, exato, how = locate(d)
        sj, cj = ('', '')
        if r is not None: sj, cj, _, _ = lado(r['_uk'], 'JAPANESE')
        cht.append([d['ID EN'], d['Carta inglesa — referência'], d['Código EN'], d['Set EN'], d['Nome local'], d['Código local completo'], d['Set / produto local'], d['Raridade e acabamento'],
                    d['Status'], d['Como foi validada'], d['Fonte local e complemento'], sj, cj, 'PR #53; não revalidado nesta rodada (o PokeData não tem chinês tradicional)'])

# ---------------- sets and traditional chinese reference
SET_H = ['set_id', 'Idioma', 'Era', 'Set', 'Código', 'Nome nativo', 'Lançamento', 'Registros', 'Cartas únicas', 'Arte confirmada', 'Prováveis', 'Inconclusivas', 'Não encontradas', 'Exclusivas']
BUCKETS = (OK, PR, 'inconclusivo', NE, 'exclusiva')
SHN = {'ENGLISH': 'Catálogo EN', 'JAPANESE': 'Catálogo JP', 'CHINESE': 'Catálogo CN'}
setnat = {}
for r in rows: setnat[r['_uk'][0]] = r['set_nome_nativo']
srows = []
for s in sorted(sets.values(), key=lambda s: (LANGS.index(s['language']), -ERA_ORDER[(s['language'], s['series'])].timestamp(), -datetime.strptime(s['release_date'][5:16], '%d %b %Y').timestamp())):
    srows.append([s['id'], PT[s['language']], s['series'], s['name'], s['code'] or '', setnat.get(s['id'], ''), datetime.strptime(s['release_date'][5:16], '%d %b %Y').strftime('%Y-%m-%d')] + [None] * 7)

wb.remove(wb.active)
ws0 = wb.create_sheet('Leia-me')
ws_sets = sheet('Sets', SET_H, srows, {'Set': 44, 'Nome nativo': 26})
for lang in LANGS: sheet(SHN[lang], CAT_H, cat[lang], CAT_W)
A, U_, G_ = COL['set_id'], COL['Carta única'], COL['Situação geral']
for i, s in enumerate(srows, start=2):
    sh = SHN[{v: k for k, v in PT.items()}[s[1]]]
    ws_sets[f'H{i}'] = f"=COUNTIF('{sh}'!${A}:${A},A{i})"
    ws_sets[f'I{i}'] = f"=COUNTIFS('{sh}'!${A}:${A},A{i},'{sh}'!${U_}:${U_},1)"
    for col, val in zip('JKLMN', BUCKETS):
        ws_sets[f'{col}{i}'] = f"=COUNTIFS('{sh}'!${A}:${A},A{i},'{sh}'!${U_}:${U_},1,'{sh}'!${G_}:${G_},\"{val}\")"
sheet('Correspondência', COR_H, cor, {'Set (EN)': 30, 'Nome (EN)': 28, 'Busca eBay (EN)': 42, 'Set (JP)': 30, 'Nome no PokeData (JP)': 26, 'Busca eBay (JP)': 42, 'Outras impressões JP com a mesma arte': 40, 'Set (CN)': 30, 'Nome no PokeData (CN)': 26, 'Busca eBay (CN)': 42, 'Outras impressões CN com a mesma arte': 40, 'Observações': 40, 'Situação JP': 26, 'Situação CN simplificado': 26, 'Versão': 50, 'Outras variantes (EN)': 26, 'Outras variantes (JP)': 26, 'Outras variantes (CN)': 26}, freeze='F2')
sheet('Prováveis', PRV_H, prv, {'Par': 28, 'Set (A)': 30, 'Nome (A)': 28, 'Set (B)': 30, 'Nome no PokeData (B)': 26, 'Motivo': 70, 'Busca eBay (A)': 42, 'Busca eBay (B)': 42})
sheet('JP-CN sem inglês', JC_H, jc, {'Set (JP)': 30, 'Busca eBay (JP)': 42, 'Set (CN)': 30, 'Busca eBay (CN)': 42, 'Situação em inglês': 40})
sheet('Inconclusivos', INC_H, inc, {'Set': 34, 'Nome': 28, 'Situação geral': 16, 'Situação em inglês': 44, 'Situação em japonês': 44, 'Situação em chinês simplificado': 44, 'Candidata mais próxima': 40, 'Impressões japonesas segundo o Limitless': 60, 'Busca eBay': 44})
sheet('Exclusivas', EXC_H, exc, {'Set': 34, 'Nome': 28, 'Critério': 70, 'Busca eBay': 44})
tw = json.load(open('ext/tcgdex_sets_zh-tw.json')); jpcodes = {key(s['code']): s for s in sets.values() if s['language'] == 'JAPANESE' and s['code']}
twr = []
for t in tw:
    if t['id'].upper().startswith('CS'): continue
    name = t['name'] if not (t['name'] == '三連音爆' and t['id'] != 'SV1a') else ''
    j = jpcodes.get(key(t['id']))
    twr.append([t['id'], name, (t.get('cardCount') or {}).get('total', ''), j['name'] if j else '', (j['code'] if j else ''), 'TCGdex (fora do PokeData; não verificado por imagem)'])
sheet('Ref. chinês tradicional', ['Código (tradicional)', 'Nome do set (繁體)', 'Cartas', 'Set japonês correspondente no PokeData', 'Código JP', 'Fonte'], twr, {'Nome do set (繁體)': 30, 'Set japonês correspondente no PokeData': 44, 'Fonte': 50})
if PR53:
    sheet('Cobertura PR53', COV_H, cov, {'Carta inglesa — referência': 34, 'Set EN': 28, 'Localização neste catálogo': 30, 'Imagem comparada': 30, 'Situação JP (esta rodada)': 40, 'Situação CN simplificado (esta rodada)': 40, 'Versão': 50})
    sheet('CHT PR53', CHT_H, cht, {'Carta inglesa — referência': 30, 'Set EN': 26, 'Nome local (繁體)': 22, 'Código local completo': 20, 'Set / produto local': 30, 'Raridade e acabamento': 40, 'Como foi validada (PR #53)': 50, 'Fonte local': 50, 'Situação JP nesta rodada': 30, 'Origem': 60})

# ---------------- Leia-me with formula summaries
ws0.column_dimensions['A'].width = 52
for c in 'BCDEFGHIJ': ws0.column_dimensions[c].width = 17
B = Font(name='Arial', size=10, bold=True)
def head(r, hdr):
    for j, h in enumerate(hdr): c = ws0.cell(row=r, column=1 + j, value=h); c.font = HF; c.fill = HFILL; c.alignment = Alignment(wrap_text=True)
def title(r, t): ws0[f'A{r}'] = t; ws0[f'A{r}'].font = B
ws0['A1'] = 'PokeData — catálogo EN / JP / CN e correspondência entre idiomas'; ws0['A1'].font = Font(name='Arial', size=14, bold=True)
ws0['A2'] = 'Dados extraídos do PokeData (pokedata.io) em 04/10/2026. "Arte confirmada" = mesma ilustração, por comparação de imagem. Edição, acabamento e carimbo não foram conferidos.'
info = [('Sets', 'Um set por linha, com contagens calculadas a partir dos catálogos.'),
        ('Catálogo EN / JP / CN', 'Uma linha por registro do PokeData (cada acabamento é um registro). "Carta única" = 1 marca a linha principal de cada carta. "Imagem comparada" diz qual registro teve a imagem comparada.'),
        ('Correspondência', 'Cartas em inglês com equivalente de arte confirmada em japonês e/ou chinês simplificado. A coluna Versão mostra onde há variantes a conferir.'),
        ('Prováveis', 'Pares que a imagem aprovou, mas que ficam fora da Correspondência: menos de 40 pontos coincidentes, ou nome divergente entre os idiomas.'),
        ('JP-CN sem inglês', 'Pares japonês ↔ chinês simplificado com arte confirmada, sem carta em inglês confirmada.'),
        ('Inconclusivos', 'Cartas sem equivalente confirmado nem provável: "inconclusivo" (há um motivo ou uma candidata fraca) e "não encontrada" (nada achado; não quer dizer exclusiva).'),
        ('Exclusivas', 'Só cartas com fonte externa dizendo que não há impressão em outro idioma, com o critério de cada uma.'),
        ('Ref. chinês tradicional', 'Sets em chinês tradicional listados pelo TCGdex. O PokeData só tem chinês simplificado.')]
if PR53:
    info += [('Cobertura PR53', 'As referências em inglês da planilha do PR #53, com a situação de cada uma nesta rodada. Sem preços.'),
             ('CHT PR53', 'Correspondências em chinês tradicional confirmadas no PR #53, preservadas como vieram. Não foram revalidadas aqui.')]
title(4, 'Abas')
for i, (a, b) in enumerate(info, start=5): ws0[f'A{i}'] = a; ws0[f'B{i}'] = b
r0 = 6 + len(info)
title(r0, 'Totais por idioma (cartas únicas)')
head(r0 + 1, ['Idioma', 'Sets', 'Registros', 'Cartas únicas', 'Arte confirmada', 'Prováveis', 'Inconclusivas', 'Não encontradas', 'Exclusivas', 'Conferência (soma)'])
for i, lang in enumerate(LANGS):
    rr = r0 + 2 + i; sh = SHN[lang]
    ws0.cell(row=rr, column=1, value=PT[lang])
    ws0.cell(row=rr, column=2, value=f"=COUNTIF(Sets!$B:$B,A{rr})")
    ws0.cell(row=rr, column=3, value=f"=COUNTA('{sh}'!${A}:${A})-1")
    ws0.cell(row=rr, column=4, value=f"=COUNTIF('{sh}'!${U_}:${U_},1)")
    for col, val in zip(range(5, 10), BUCKETS):
        ws0.cell(row=rr, column=col, value=f"=COUNTIFS('{sh}'!${U_}:${U_},1,'{sh}'!${G_}:${G_},\"{val}\")")
    ws0.cell(row=rr, column=10, value=f"=SUM(E{rr}:I{rr})-D{rr}")
# conferência entre cartas confirmadas e linhas da Correspondência
CL = {h: get_column_letter(i) for i, h in enumerate(COR_H, 1)}
rc = r0 + 6
title(rc, 'Conferência: cartas em inglês × linhas da aba Correspondência')
cq = [('Cartas únicas em inglês com arte confirmada', f"=COUNTIFS('Catálogo EN'!${U_}:${U_},1,'Catálogo EN'!${G_}:${G_},\"{OK}\")"),
      ('Linhas na aba Correspondência', "=COUNTA('Correspondência'!$A:$A)-1"),
      ('Cartas somadas nessas linhas (última coluna da aba)', f"=SUM('Correspondência'!${CL['Cartas do PokeData nesta linha']}:${CL['Cartas do PokeData nesta linha']})"),
      ('Diferença entre cartas e linhas: cartas que o PokeData repete no mesmo set e número', f"=B{rc + 1}-B{rc + 2}"),
      ('Conferência: cartas confirmadas menos cartas somadas (deve ser 0)', f"=B{rc + 1}-B{rc + 3}"),
      ('Linhas com japonês', f"=COUNTIF('Correspondência'!${CL['Situação JP']}:${CL['Situação JP']},\"{OK}\")"),
      ('Linhas com chinês simplificado', f"=COUNTIF('Correspondência'!${CL['Situação CN simplificado']}:${CL['Situação CN simplificado']},\"{OK}\")"),
      ('Linhas com os dois', f"=COUNTIFS('Correspondência'!${CL['Situação JP']}:${CL['Situação JP']},\"{OK}\",'Correspondência'!${CL['Situação CN simplificado']}:${CL['Situação CN simplificado']},\"{OK}\")"),
      ('Linhas com registro único e sem marcação em todos os idiomas', f"=COUNTIF('Correspondência'!${CL['Versão']}:${CL['Versão']},\"{V_UNICO}\")"),
      ('Linhas com variantes ou marcação de edição/acabamento a conferir', f"=COUNTIF('Correspondência'!${CL['Versão']}:${CL['Versão']},\"{V_CONF}\")"),
      ('Pares na aba Prováveis', "=COUNTA('Prováveis'!$A:$A)-1")]
for i, (a, f) in enumerate(cq, start=rc + 1): ws0[f'A{i}'] = a; ws0[f'B{i}'] = f
r1 = rc + len(cq) + 2
title(r1, 'Cartas em inglês por era')
head(r1 + 1, ['Era', 'Cartas únicas', 'Arte confirmada JP', 'Arte confirmada CN', 'Arte confirmada (JP ou CN)', '% com arte confirmada', 'Prováveis', 'Inconclusivas', 'Não encontradas', 'Exclusivas'])
eras = [e for (l, e), d in sorted(ERA_ORDER.items(), key=lambda kv: -kv[1].timestamp()) if l == 'ENGLISH']
sh = 'Catálogo EN'; E_, J_, C_ = COL['Era'], COL['Equivalente JP'], COL['Equivalente CN simplificado']
for i, e in enumerate(eras):
    rr = r1 + 2 + i
    ws0.cell(row=rr, column=1, value=e)
    ws0.cell(row=rr, column=2, value=f"=COUNTIFS('{sh}'!${E_}:${E_},A{rr},'{sh}'!${U_}:${U_},1)")
    ws0.cell(row=rr, column=3, value=f"=COUNTIFS('{sh}'!${E_}:${E_},A{rr},'{sh}'!${U_}:${U_},1,'{sh}'!${J_}:${J_},\"{OK}\")")
    ws0.cell(row=rr, column=4, value=f"=COUNTIFS('{sh}'!${E_}:${E_},A{rr},'{sh}'!${U_}:${U_},1,'{sh}'!${C_}:${C_},\"{OK}\")")
    ws0.cell(row=rr, column=5, value=f"=COUNTIFS('{sh}'!${E_}:${E_},A{rr},'{sh}'!${U_}:${U_},1,'{sh}'!${G_}:${G_},\"{OK}\")")
    ws0.cell(row=rr, column=6, value=f"=IF(B{rr}=0,0,E{rr}/B{rr})"); ws0.cell(row=rr, column=6).number_format = '0.0%'
    for col, val in zip(range(7, 11), BUCKETS[1:]):
        ws0.cell(row=rr, column=col, value=f"=COUNTIFS('{sh}'!${E_}:${E_},A{rr},'{sh}'!${U_}:${U_},1,'{sh}'!${G_}:${G_},\"{val}\")")
r2 = r1 + 3 + len(eras)
if PR53:
    VL = {h: get_column_letter(i) for i, h in enumerate(COV_H, 1)}
    def cv(h): return f"'Cobertura PR53'!${VL[h]}:${VL[h]}"
    title(r2, 'Cobertura das referências em inglês do PR #53 (aba Cobertura PR53)')
    G1, J1, C1 = cv('Situação geral (esta rodada)'), cv('Situação JP (esta rodada)'), cv('Situação CN simplificado (esta rodada)')
    pq = [('Referências', f"=COUNTA({cv('ID EN (PR #53)')})-1"),
          ('Não localizadas neste catálogo', f"=COUNTIF({cv('Localização neste catálogo')},\"não localizado*\")"),
          ('Com arte confirmada em japonês ou chinês simplificado', f"=COUNTIF({G1},\"{OK}\")"),
          ('— em japonês', f"=COUNTIF({J1},\"{OK}\")"),
          ('— em chinês simplificado', f"=COUNTIF({C1},\"{OK}\")"),
          ('Só prováveis', f"=COUNTIF({G1},\"{PR}\")"),
          ('Inconclusivas', f"=COUNTIF({G1},\"inconclusivo\")"),
          ('Não encontradas', f"=COUNTIF({G1},\"{NE}\")"),
          ('Exclusivas', f"=COUNTIF({G1},\"exclusiva\")"),
          ('% com arte confirmada', f"=IF(B{r2 + 1}=0,0,B{r2 + 3}/B{r2 + 1})"),
          ('Com arte confirmada aqui, em que a referência é o registro da imagem comparada', f"=COUNTIFS({G1},\"{OK}\",{cv('Imagem comparada')},\"sim\")"),
          ('Com arte confirmada aqui, em que a referência é uma variante não conferida', f"=COUNTIFS({G1},\"{OK}\",{cv('Imagem comparada')},\"não*\")"),
          ('Com confirmação em japonês no PR #53', f"=COUNTIF({cv('Status JP (PR #53)')},\"Confirmada\")"),
          ('Com confirmação em chinês simplificado no PR #53', f"=COUNTIF({cv('Status simplificado (PR #53)')},\"Confirmada\")"),
          ('Com confirmação em chinês tradicional no PR #53', f"=COUNTIF({cv('Status tradicional (PR #53)')},\"Confirmada\")"),
          ('Arte confirmada aqui em japonês, sem confirmação em japonês no PR #53', f"=COUNTIFS({J1},\"{OK}\",{cv('Status JP (PR #53)')},\"<>Confirmada\")"),
          ('Arte confirmada aqui em chinês simplificado, sem confirmação no PR #53', f"=COUNTIFS({C1},\"{OK}\",{cv('Status simplificado (PR #53)')},\"<>Confirmada\")"),
          ('Registros em chinês tradicional preservados (aba CHT PR53)', "=COUNTA('CHT PR53'!$A:$A)-1"),
          ('Ambíguas: mais de um registro possível, nenhum escolhido', f"=COUNTIF({cv('Localização neste catálogo')},\"ambíguo*\")")]
    for i, (a, f) in enumerate(pq, start=r2 + 1): ws0[f'A{i}'] = a; ws0[f'B{i}'] = f
    ws0[f'B{r2 + 10}'].number_format = '0.0%'
    r2 += len(pq) + 2
notes = ['Notas',
         'Arte confirmada: a ilustração coincidiu na comparação de imagem, com 40 pontos coincidentes ou mais dentro da arte, cores compatíveis e nome compatível entre os idiomas.',
         'Arte confirmada não é versão confirmada. A comparação usa uma imagem por carta; edição (1st Edition, Unlimited, Shadowless), acabamento (holo, reverse, padrão de Poké Ball) e carimbo não foram conferidos.',
         'Coluna Versão (aba Correspondência): indica se as cartas da linha têm um único registro sem marcação ou se há variantes a conferir. As colunas ao lado dizem qual registro teve a imagem comparada.',
         'Provável: a imagem coincidiu, mas com menos de 40 pontos, ou com nome divergente entre os idiomas. Fica fora da Correspondência até conferência visual.',
         'Inconclusivo: há um motivo que impede a comparação (por exemplo, carta sem imagem) ou uma candidata abaixo do limite. O motivo aparece na coluna de situação de cada idioma.',
         'Não encontrada: nenhuma candidata nos catálogos consultados. Não quer dizer que a carta seja exclusiva.',
         'Exclusiva: só com fonte externa. Inglês: o Limitless lista a carta sem impressão japonesa. Japonês: a página japonesa do Limitless não lista nenhuma impressão internacional.',
         'Raridade: o PokeData não publica raridade. Inglês vem de pokemon-tcg-data; japonês vem do TCGdex (cobertura parcial); chinês simplificado não tem fonte confiável.',
         'Nomes japoneses e chineses: TCGdex quando disponível; nos demais casos, nome oficial do Pokémon (PokeAPI). Treinadores e Energias sem fonte ficam só em inglês.',
         'Fontes: pokedata.io · github.com/PokemonTCG/pokemon-tcg-data · tcgdex.dev · github.com/PokeAPI/pokeapi · limitlesstcg.com']
for i, t in enumerate(notes): ws0[f'A{r2 + i}'] = t
ws0[f'A{r2}'].font = B
wb.save(OUT)
print('saved', OUT, 'cor', len(cor), 'cartas na cor', sum(r[-1] for r in cor), 'prv', len(prv), 'jc', len(jc), 'inc', len(inc), 'exc', len(exc), 'cov', len(cov), 'cht', len(cht), {l: len(v) for l, v in cat.items()})
pickle.dump(dict(cor=cor, prv=prv, jc=jc, inc=inc, exc=exc, cov=cov, cht=cht, COR_H=COR_H, PRV_H=PRV_H, INC_H=INC_H, EXC_H=EXC_H, JC_H=JC_H, COV_H=COV_H, CHT_H=CHT_H), open('tables.pkl', 'wb'))
