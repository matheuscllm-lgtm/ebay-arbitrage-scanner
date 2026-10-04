"""Etapa 12 — monta a planilha de entrega. Uso: python build_xlsx.py saida.xlsx

Entrada: catalog.pkl, result.pkl, lim_jp.pkl   Saída: planilha com 10 abas e tables.pkl
Depois de gerar, recalcular as fórmulas no LibreOffice ou abrir e salvar no Excel.
"""
import pickle, json, re, os, sys
from collections import defaultdict, Counter
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from common import *

OUT = sys.argv[1] if len(sys.argv) > 1 else 'PokeData_catalogo_correspondencia.xlsx'
rows, uinfo = pickle.load(open('catalog.pkl', 'rb'))
R = pickle.load(open('result.pkl', 'rb')); CONF, GRAY, VIA, STATUS, LIM = R['CONF'], R['GRAY'], R['VIA'], R['STATUS'], R['LIM']
sets, cards = load(); units = art_units(cards)
LANG = {k: sets[k[0]]['language'] for k in units}
def sdate(k): return datetime.strptime(sets[k[0]]['release_date'][5:16], '%d %b %Y')
REV = {t: defaultdict(dict) for t in CONF}; REVG = {t: defaultdict(dict) for t in GRAY}
for t in CONF:
    for a, c in CONF[t].items():
        for b, v in c.items(): REV[t][b][a] = v
for t in GRAY:
    for a, c in GRAY[t].items():
        for b, v in c.items(): REVG[t][b][a] = v
def rank(a, cands):
    da = sdate(a)
    def sc(item):
        b, v = item
        nc = v[1] if isinstance(v, tuple) else 1; ni = v[0].get('n_in', 0) if isinstance(v, tuple) else 0
        dd = (da - sdate(b)).days
        return (0 if nc >= 1 else 1, abs(dd) if dd >= -60 else abs(dd) + 400, -ni)
    out = []; seen = set()
    for b, _ in sorted(cands.items(), key=sc):
        m = re.search(r'(\d+)$', b[1]); sig = (b[0], int(m.group(1)) if m else b[1])
        if sig in seen: continue           # PokeData lists some cards twice (036 and 36)
        seen.add(sig); out.append(b)
    return out
def partners(k, T):
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
        if v2[0].get('n_in', 0) < 40: continue
        for e, v1 in REV['EN_JA'].get(j, {}).items():
            if v1[0].get('n_in', 0) >= 40: d.setdefault(e, 'via')
    return d, REVG['EN_CH'].get(k, {})
LANGS = ('ENGLISH', 'JAPANESE', 'CHINESE')
EQ = {k: {T: rank(k, partners(k, T)[0]) for T in LANGS if T != LANG[k]} for k in units}

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
tags_by_unit = defaultdict(list)
for r in rows:
    if r['variante']: tags_by_unit[r['_uk']].append(r['variante'])
def variants(k): return ', '.join(dict.fromkeys(tags_by_unit.get(k, [])))
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
CAT_H = ['set_id', 'Idioma', 'Era', 'Set', 'Código do set', 'Nome nativo do set', 'Lançamento', 'Número', 'Número impresso', 'Nome (PokeData)', 'Nome base', 'Nome oficial (EN)', 'Variante / acabamento', 'Raridade', 'Fonte da raridade', 'Secreta', 'Nome no idioma original', 'Ilustrador', 'Busca eBay principal', 'Buscas eBay alternativas', 'Carta única', 'Situação geral', 'Equivalente EN', 'Equivalente JP', 'Equivalente CN simplificado', 'Códigos equivalentes', 'ID PokeData', 'ID TCGplayer', 'Imagem']
COL = {h: get_column_letter(i) for i, h in enumerate(CAT_H, 1)}
CAT_W = {'Set': 34, 'Nome (PokeData)': 34, 'Nome base': 28, 'Busca eBay principal': 46, 'Buscas eBay alternativas': 70, 'Códigos equivalentes': 50, 'Imagem': 30, 'Nome no idioma original': 22, 'Nome nativo do set': 22, 'Variante / acabamento': 20, 'Equivalente EN': 30, 'Equivalente JP': 30, 'Equivalente CN simplificado': 30, 'Situação geral': 16}
def eqcodes(k):
    parts = []
    for T in LANGS:
        e = EQ[k].get(T, [])
        if e: parts.append(f"{ABR[T]}: " + '; '.join(code(x) for x in e[:6]) + (f" (+{len(e) - 6})" if len(e) > 6 else ''))
    return ' | '.join(parts)
def st(k, T): return '—' if T == LANG[k] else STATUS[k].get(T, '')
cat = defaultdict(list)
for r in sorted(rows, key=lambda r: ukey(r['_uk']) + (r['nome'],)):
    k = r['_uk']
    cat[r['_lang']].append([k[0], r['idioma'], r['era'], r['set_nome'], r['set_codigo'], r['set_nome_nativo'], r['set_data'], r['numero'], r['numero_impresso'], r['nome'], r['nome_base'], r.get('nome_oficial', ''), r['variante'], r['raridade'], r['fonte_raridade'], r['secreta'], r['nome_nativo'], r['ilustrador'], r['ebay_principal'], r['ebay_alternativos'], 1 if main_row[k] is r else 0, STATUS[k]['geral'], st(k, 'ENGLISH'), st(k, 'JAPANESE'), st(k, 'CHINESE'), eqcodes(k), r['pokedata_id'], r['tcgplayer_id'], r['imagem']])

# ---------------- correspondence (EN anchored)
COR_H = ['Era (EN)', 'Set (EN)', 'Código (EN)', 'Número (EN)', 'Nome (EN)', 'Raridade (EN)', 'Busca eBay (EN)',
         'Situação JP', 'Set (JP)', 'Código (JP)', 'Número (JP)', 'Nome no PokeData (JP)', 'Nome japonês', 'Raridade (JP)', 'Busca eBay (JP)', 'Outras impressões JP com a mesma arte',
         'Situação CN simplificado', 'Set (CN)', 'Código (CN)', 'Número (CN)', 'Nome no PokeData (CN)', 'Nome chinês', 'Busca eBay (CN)', 'Outras impressões CN com a mesma arte', 'Observações', 'Confiança', 'Pontos coincidentes JP', 'Pontos coincidentes CN']
cor = []; seen = set()
for k in sorted([k for k in units if LANG[k] == 'ENGLISH'], key=ukey):
    e = EQ[k]
    if not e['JAPANESE'] and not e['CHINESE']: continue
    sig = (k[0], numsort(k[1])[0], tuple(e['JAPANESE'][:1]), tuple(e['CHINESE'][:1]))
    if sig in seen: continue
    seen.add(sig)
    u = main_row[k]; obs = []
    row = [u['era'], u['set_nome'], u['set_codigo'], u['numero_impresso'], nm(k), u['raridade'], busca(k)]
    pj = pc = ''
    if e['JAPANESE']:
        j = e['JAPANESE'][0]; ju = main_row[j]; v = CONF['EN_JA'][k][j]
        row += ['confirmado', ju['set_nome'], ju['set_codigo'], ju['numero_impresso'], ju['nome_base'], ju['nome_nativo'], ju['raridade'], busca(j), '; '.join(code(x) for x in e['JAPANESE'][1:])]
        pj = v[0].get('n_in', 0)
        if v[1] == 0: obs.append('nome diferente entre EN e JP no PokeData')
    else: row += [STATUS[k]['JAPANESE'], '', '', '', '', '', '', '', '']
    if e['CHINESE']:
        c = e['CHINESE'][0]; cu = main_row[c]; v = CONF['EN_CH'].get(k, {}).get(c)
        row += ['confirmado', cu['set_nome'], cu['set_codigo'], cu['numero_impresso'], cu['nome_base'], cu['nome_nativo'], busca(c), '; '.join(code(x) for x in e['CHINESE'][1:])]
        if v:
            pc = v[0].get('n_in', 0)
            if v[1] == 0: obs.append('nome diferente entre EN e CN no PokeData')
        else: obs.append('CN confirmado por meio da carta japonesa')
    else: row += [STATUS[k]['CHINESE'], '', '', '', '', '', '', '']
    vt = variants(k)
    if re.search(r'Prerelease|Staff|Stamped|Pokemon Center|Trophy', vt): obs.append('EN também existe com carimbo: ' + vt)
    pts = [p for p in (pj, pc) if p != '']
    row += ['; '.join(obs), 'alta' if (not pts or min(pts) >= 40) else 'média', pj, pc]
    cor.append(row)

# ---------------- JP-CN pairs without an English card
JC_H = ['Era (JP)', 'Set (JP)', 'Código (JP)', 'Número (JP)', 'Nome no PokeData (JP)', 'Nome japonês', 'Busca eBay (JP)', 'Set (CN)', 'Código (CN)', 'Número (CN)', 'Nome no PokeData (CN)', 'Nome chinês', 'Busca eBay (CN)', 'Outras impressões CN', 'Situação em inglês']
jc = []
for j in sorted([k for k in units if LANG[k] == 'JAPANESE'], key=ukey):
    e = EQ[j]
    if e['ENGLISH'] or not e['CHINESE']: continue
    ju = main_row[j]; c = e['CHINESE'][0]; cu = main_row[c]
    jc.append([ju['era'], ju['set_nome'], ju['set_codigo'], ju['numero_impresso'], ju['nome_base'], ju['nome_nativo'], busca(j), cu['set_nome'], cu['set_codigo'], cu['numero_impresso'], cu['nome_base'], cu['nome_nativo'], busca(c), '; '.join(code(x) for x in e['CHINESE'][1:]), STATUS[j]['ENGLISH']])

# ---------------- inconclusive and exclusive
INC_H = ['Idioma', 'Era', 'Set', 'Código', 'Número', 'Nome', 'Situação em inglês', 'Situação em japonês', 'Situação em chinês simplificado', 'Candidata mais próxima', 'Pontos coincidentes', 'Semelhança da arte (0–1)', 'Impressões japonesas segundo o Limitless', 'Busca eBay']
EXC_H = ['Idioma', 'Era', 'Set', 'Código', 'Lançamento', 'Número', 'Nome', 'Nome no idioma original', 'Raridade', 'Variantes', 'Critério', 'Cartas de mesmo nome comparadas (EN)', 'Cartas de mesmo nome comparadas (JP)', 'Cartas de mesmo nome comparadas (CN)', 'Busca eBay']
HASIMG = {int(f[:-4]) for f in os.listdir('img') if f.endswith('.jpg')}
BAD = {tuple(k) for k in json.load(open('cardback_units.json'))}
rep = json.load(open('unit_rep.json'))
BYNAME = defaultdict(lambda: defaultdict(int))
for k in units:
    if rep.get(f"{k[0]}|{k[1]}|{k[2]}") in HASIMG and k not in BAD: BYNAME[LANG[k]][k[2]] += 1
LJP = pickle.load(open('lim_jp.pkl', 'rb')) if os.path.exists('lim_jp.pkl') else {}
inc = []; exc = []
for k in sorted(units, key=ukey):
    u = main_row[k]; stt = STATUS[k]
    if stt['geral'] == 'inconclusivo':
        best = None
        for T in LANGS:
            if T == LANG[k]: continue
            for b, v in partners(k, T)[1].items():
                if best is None or v[0].get('n_in', 0) > best[1][0].get('n_in', 0): best = (b, v)
        cand = pts = sim = ''
        if best:
            b, v = best; cand = f"{ABR[LANG[b]]} {code(b)} {main_row[b]['nome_base']}"; pts = v[0].get('n_in', 0); sim = round(max(v[0].get('ncc', 0), 0), 2)
        lim = LIM.get(k); limtxt = ''
        if lim and lim['kind'] == 'impressão japonesa': limtxt = '; '.join((lim['outside'] + lim['inside'])[:6])
        inc.append([PT[LANG[k]], u['era'], u['set_nome'], u['set_codigo'], u['numero_impresso'], nm(k), st(k, 'ENGLISH'), st(k, 'JAPANESE'), st(k, 'CHINESE'), cand, pts, sim, limtxt, busca(k)])
    elif stt['geral'] == 'exclusiva':
        crit = 'Sem impressão japonesa segundo o Limitless e sem equivalente chinês no PokeData' if LANG[k] == 'ENGLISH' else ('Arte sem equivalente em inglês nem em chinês simplificado no PokeData' + ('; Limitless também não lista impressão internacional' if (k in LJP and not LJP[k]) else ''))
        exc.append([PT[LANG[k]], u['era'], u['set_nome'], u['set_codigo'], u['set_data'], u['numero_impresso'], nm(k), u['nome_nativo'], u['raridade'], variants(k), crit] + [(BYNAME[T][k[2]] if LANG[k] != T else '—') for T in LANGS] + [busca(k)])

# ---------------- sets and traditional chinese reference
SET_H = ['set_id', 'Idioma', 'Era', 'Set', 'Código', 'Nome nativo', 'Lançamento', 'Registros', 'Cartas únicas', 'Confirmadas', 'Inconclusivas', 'Exclusivas']
SHN = {'ENGLISH': 'Catálogo EN', 'JAPANESE': 'Catálogo JP', 'CHINESE': 'Catálogo CN'}
setnat = {}
for r in rows: setnat[r['_uk'][0]] = r['set_nome_nativo']
srows = []
for s in sorted(sets.values(), key=lambda s: (LANGS.index(s['language']), -ERA_ORDER[(s['language'], s['series'])].timestamp(), -datetime.strptime(s['release_date'][5:16], '%d %b %Y').timestamp())):
    srows.append([s['id'], PT[s['language']], s['series'], s['name'], s['code'] or '', setnat.get(s['id'], ''), datetime.strptime(s['release_date'][5:16], '%d %b %Y').strftime('%Y-%m-%d'), None, None, None, None, None])

wb.remove(wb.active)
ws0 = wb.create_sheet('Leia-me')
ws_sets = sheet('Sets', SET_H, srows, {'Set': 44, 'Nome nativo': 26})
for lang in LANGS: sheet(SHN[lang], CAT_H, cat[lang], CAT_W)
A, U_, G_ = COL['set_id'], COL['Carta única'], COL['Situação geral']
for i, s in enumerate(srows, start=2):
    sh = SHN[{v: k for k, v in PT.items()}[s[1]]]
    ws_sets[f'H{i}'] = f"=COUNTIF('{sh}'!${A}:${A},A{i})"
    ws_sets[f'I{i}'] = f"=COUNTIFS('{sh}'!${A}:${A},A{i},'{sh}'!${U_}:${U_},1)"
    for col, val in (('J', 'confirmado'), ('K', 'inconclusivo'), ('L', 'exclusiva')):
        ws_sets[f'{col}{i}'] = f"=COUNTIFS('{sh}'!${A}:${A},A{i},'{sh}'!${U_}:${U_},1,'{sh}'!${G_}:${G_},\"{val}\")"
sheet('Correspondência', COR_H, cor, {'Set (EN)': 30, 'Nome (EN)': 28, 'Busca eBay (EN)': 42, 'Set (JP)': 30, 'Nome no PokeData (JP)': 26, 'Busca eBay (JP)': 42, 'Outras impressões JP com a mesma arte': 40, 'Set (CN)': 30, 'Nome no PokeData (CN)': 26, 'Busca eBay (CN)': 42, 'Outras impressões CN com a mesma arte': 40, 'Observações': 40, 'Situação JP': 26, 'Situação CN simplificado': 26}, freeze='F2')
sheet('JP-CN sem inglês', JC_H, jc, {'Set (JP)': 30, 'Busca eBay (JP)': 42, 'Set (CN)': 30, 'Busca eBay (CN)': 42, 'Situação em inglês': 40})
sheet('Inconclusivos', INC_H, inc, {'Set': 34, 'Nome': 28, 'Situação em inglês': 44, 'Situação em japonês': 44, 'Situação em chinês simplificado': 44, 'Candidata mais próxima': 40, 'Impressões japonesas segundo o Limitless': 60, 'Busca eBay': 44})
sheet('Exclusivas', EXC_H, exc, {'Set': 34, 'Nome': 28, 'Critério': 60, 'Busca eBay': 44})
tw = json.load(open('ext/tcgdex_sets_zh-tw.json')); jpcodes = {key(s['code']): s for s in sets.values() if s['language'] == 'JAPANESE' and s['code']}
twr = []
for t in tw:
    if t['id'].upper().startswith('CS'): continue
    name = t['name'] if not (t['name'] == '三連音爆' and t['id'] != 'SV1a') else ''
    j = jpcodes.get(key(t['id']))
    twr.append([t['id'], name, (t.get('cardCount') or {}).get('total', ''), j['name'] if j else '', (j['code'] if j else ''), 'TCGdex (fora do PokeData; não verificado por imagem)'])
sheet('Ref. chinês tradicional', ['Código (tradicional)', 'Nome do set (繁體)', 'Cartas', 'Set japonês correspondente no PokeData', 'Código JP', 'Fonte'], twr, {'Nome do set (繁體)': 30, 'Set japonês correspondente no PokeData': 44, 'Fonte': 50})

# ---------------- Leia-me with formula summaries
ws0.column_dimensions['A'].width = 36
for c in 'BCDEFGH': ws0.column_dimensions[c].width = 18
B = Font(name='Arial', size=10, bold=True)
ws0['A1'] = 'PokeData — catálogo EN / JP / CN e correspondência entre idiomas'; ws0['A1'].font = Font(name='Arial', size=14, bold=True)
ws0['A2'] = 'Dados extraídos do PokeData (pokedata.io) em 04/10/2026. Equivalências confirmadas por comparação de imagem da ilustração.'
info = [('Sets', 'Um set por linha, com contagens calculadas a partir dos catálogos.'),
        ('Catálogo EN / JP / CN', 'Uma linha por registro do PokeData (cada acabamento é um registro). "Carta única" = 1 marca a linha principal de cada carta.'),
        ('Correspondência', 'Cartas em inglês com equivalente confirmado em japonês e/ou chinês simplificado (mesma ilustração).'),
        ('JP-CN sem inglês', 'Pares japonês ↔ chinês simplificado confirmados que não têm carta em inglês confirmada.'),
        ('Inconclusivos', 'Cartas que não puderam ser confirmadas nem dadas como exclusivas; não entram na Correspondência.'),
        ('Exclusivas', 'Cartas de um único idioma, com o critério usado em cada caso.'),
        ('Ref. chinês tradicional', 'Sets em chinês tradicional listados pelo TCGdex. O PokeData só tem chinês simplificado.')]
ws0['A4'] = 'Abas'; ws0['A4'].font = B
for i, (a, b) in enumerate(info, start=5): ws0[f'A{i}'] = a; ws0[f'B{i}'] = b
r0 = 14
ws0[f'A{r0}'] = 'Totais por idioma (cartas únicas)'; ws0[f'A{r0}'].font = B
hdr = ['Idioma', 'Sets', 'Registros', 'Cartas únicas', 'Confirmadas', 'Inconclusivas', 'Exclusivas']
for j, h in enumerate(hdr): c = ws0.cell(row=r0 + 1, column=1 + j, value=h); c.font = HF; c.fill = HFILL; c.alignment = Alignment(wrap_text=True)
for i, lang in enumerate(LANGS):
    rr = r0 + 2 + i; sh = SHN[lang]
    ws0.cell(row=rr, column=1, value=PT[lang])
    ws0.cell(row=rr, column=2, value=f"=COUNTIF(Sets!$B:$B,A{rr})")
    ws0.cell(row=rr, column=3, value=f"=COUNTA('{sh}'!${A}:${A})-1")
    ws0.cell(row=rr, column=4, value=f"=COUNTIF('{sh}'!${U_}:${U_},1)")
    for col, val in ((5, 'confirmado'), (6, 'inconclusivo'), (7, 'exclusiva')):
        ws0.cell(row=rr, column=col, value=f"=COUNTIFS('{sh}'!${U_}:${U_},1,'{sh}'!${G_}:${G_},\"{val}\")")
r1 = r0 + 7
ws0[f'A{r1}'] = 'Cartas em inglês por era'; ws0[f'A{r1}'].font = B
hdr = ['Era', 'Cartas únicas', 'Com equivalente JP', 'Com equivalente CN', 'Com JP ou CN', '% com equivalente', 'Inconclusivas', 'Exclusivas']
for j, h in enumerate(hdr): c = ws0.cell(row=r1 + 1, column=1 + j, value=h); c.font = HF; c.fill = HFILL; c.alignment = Alignment(wrap_text=True)
eras = [e for (l, e), d in sorted(ERA_ORDER.items(), key=lambda kv: -kv[1].timestamp()) if l == 'ENGLISH']
sh = 'Catálogo EN'; E_, J_, C_ = COL['Era'], COL['Equivalente JP'], COL['Equivalente CN simplificado']
for i, e in enumerate(eras):
    rr = r1 + 2 + i
    ws0.cell(row=rr, column=1, value=e)
    ws0.cell(row=rr, column=2, value=f"=COUNTIFS('{sh}'!${E_}:${E_},A{rr},'{sh}'!${U_}:${U_},1)")
    ws0.cell(row=rr, column=3, value=f"=COUNTIFS('{sh}'!${E_}:${E_},A{rr},'{sh}'!${U_}:${U_},1,'{sh}'!${J_}:${J_},\"confirmado\")")
    ws0.cell(row=rr, column=4, value=f"=COUNTIFS('{sh}'!${E_}:${E_},A{rr},'{sh}'!${U_}:${U_},1,'{sh}'!${C_}:${C_},\"confirmado\")")
    ws0.cell(row=rr, column=5, value=f"=COUNTIFS('{sh}'!${E_}:${E_},A{rr},'{sh}'!${U_}:${U_},1,'{sh}'!${G_}:${G_},\"confirmado\")")
    ws0.cell(row=rr, column=6, value=f"=IF(B{rr}=0,0,E{rr}/B{rr})"); ws0.cell(row=rr, column=6).number_format = '0.0%'
    ws0.cell(row=rr, column=7, value=f"=COUNTIFS('{sh}'!${E_}:${E_},A{rr},'{sh}'!${U_}:${U_},1,'{sh}'!${G_}:${G_},\"inconclusivo\")")
    ws0.cell(row=rr, column=8, value=f"=COUNTIFS('{sh}'!${E_}:${E_},A{rr},'{sh}'!${U_}:${U_},1,'{sh}'!${G_}:${G_},\"exclusiva\")")
r2 = r1 + 3 + len(eras)
notes = ['Notas',
         'Confirmado: a ilustração coincidiu na comparação de imagem (mínimo de 12 pontos coincidentes dentro da arte, com cores compatíveis).',
         'Confiança na aba Correspondência: alta = 40 pontos coincidentes ou mais; média = entre 12 e 39. As linhas de confiança média merecem conferência visual antes de uma venda.',
         'Inconclusivo: há indício de equivalente, mas sem confirmação por imagem. O motivo aparece na coluna de situação de cada idioma.',
         'Exclusiva (inglês): carta de 2011 em diante sem impressão japonesa no banco do Limitless e sem equivalente chinês no PokeData.',
         'Exclusiva (japonês): arte que não aparece em nenhuma carta em inglês nem em chinês simplificado do PokeData. O catálogo em inglês do site é quase completo, por isso o critério vale nesse sentido.',
         'Chinês simplificado sem equivalente fica como inconclusivo: o catálogo japonês do PokeData não tem vários decks e promos de onde essas cartas podem ter vindo.',
         'Raridade: o PokeData não publica raridade. Inglês vem de pokemon-tcg-data; japonês vem do TCGdex (cobertura parcial); chinês simplificado não tem fonte confiável.',
         'Nomes japoneses e chineses: TCGdex quando disponível; nos demais casos, nome oficial do Pokémon (PokeAPI). Treinadores e Energias sem fonte ficam só em inglês.',
         '"Mesma versão" = mesma ilustração e mesma carta. Acabamento (holo, reverse, padrão de Poké Ball) não entra na comparação.',
         'Fontes: pokedata.io · github.com/PokemonTCG/pokemon-tcg-data · tcgdex.dev · github.com/PokeAPI/pokeapi · limitlesstcg.com']
for i, t in enumerate(notes): ws0[f'A{r2 + i}'] = t
ws0[f'A{r2}'].font = B
wb.save(OUT)
print('saved', OUT, 'cor', len(cor), 'jc', len(jc), 'inc', len(inc), 'exc', len(exc), {l: len(v) for l, v in cat.items()})
pickle.dump(dict(cor=cor, jc=jc, inc=inc, exc=exc, COR_H=COR_H, INC_H=INC_H, EXC_H=EXC_H, JC_H=JC_H), open('tables.pkl', 'wb'))
