"""Comparação com a planilha do PR #53 (PokeData_correspondencias_JP_CHS_CHT_parcial.xlsx).

Para cada correspondência "Confirmada" daquela planilha (aba Detalhes confirmados), procura a mesma
carta em inglês neste trabalho e diz se o código local coincide com algum equivalente confirmado aqui.
Uso: python compare_pr53.py <planilha do PR #53> <saida.csv>
Entrada local: result.pkl, catalog.pkl. A saída não contém preços.
"""
import sys, re, csv, pickle
from collections import Counter, defaultdict
from datetime import datetime
from openpyxl import load_workbook
from common import *
from reference_match import local_code, number_norm, resolve_reference, same_print, set_norm

src, out = sys.argv[1], sys.argv[2]
rows_, uinfo = pickle.load(open('catalog.pkl', 'rb'))
R = pickle.load(open('result.pkl', 'rb')); CONF, PROV, VIA, STATUS, GRAY = R['CONF'], R['PROV'], R['VIA'], R['STATUS'], R['GRAY']
sets, cards = load(); units = art_units(cards)
LANG = {k: sets[k[0]]['language'] for k in units}
# Normalização e resolução de referências: reference_match.py (revisão Claude, issue #56).
# Antes: numnorm só tirava zeros de números puramente numéricos e parse_local apagava letras
# ('H05' virava '5'); 151C1..151C4 eram fundidos em 151C; sem nome igual, valiam todos os
# candidatos do mesmo set/número. Agora prefixo/sufixo são preservados dos dois lados,
# subproduto é categoria própria e referência ambígua não é comparada.
en_by = defaultdict(list)
for k in units:
    if LANG[k] == 'ENGLISH': en_by[(sets[k[0]]['name'].lower(), number_norm(k[1]))].append(k)
REV_CJ = defaultdict(dict)
for a, c in CONF['CH_JA'].items():
    for b, v in c.items(): REV_CJ[b][a] = v
def mine(k, lang):
    """equivalentes desta rodada (arte confirmada, prováveis, candidatas abaixo do limite), como (código do set, número)"""
    t = 'EN_JA' if lang == 'Japonês' else 'EN_CH'
    conf = list(CONF[t].get(k, {})) + (list(VIA.get(k, {})) if t == 'EN_CH' else [])
    f = lambda u: (set_norm(sets[u[0]]['code'] or ''), number_norm(u[1]), sets[u[0]]['name'])
    return [f(u) for u in conf], [f(u) for u in PROV[t].get(k, {})], [f(u) for u in GRAY[t].get(k, {})]
HAS = None
def catalog_state(lang, lc, ln):
    """onde o código do PR #53 cai no catálogo do PokeData usado nesta rodada"""
    L = 'JAPANESE' if lang == 'Japonês' else 'CHINESE'
    sids = [s['id'] for s in sets.values() if s['language'] == L
            and same_print((lc, ln), {(set_norm(s['code'] or ''), ln)}) is not None]
    if not sids: return 'set fora do catálogo do PokeData'
    us = [k for k in units if k[0] in sids and number_norm(k[1]) == ln]
    if not us: return 'número fora do catálogo do PokeData'
    if all(STATUS[k].get('ENGLISH', '').startswith('inconclusivo: carta sem imagem') for k in us): return 'carta sem imagem no PokeData'
    return 'carta presente com imagem, arte não bateu: revisar'

ws = load_workbook(src, read_only=True, data_only=True)['Detalhes confirmados']
hdr = None; res = []; c = Counter()
for row in ws.iter_rows(min_row=4, values_only=True):
    if hdr is None: hdr = [str(h) for h in row]; continue
    if row[0] is None: continue
    d = dict(zip(hdr, row))
    lang = d['Idioma']; idioma = {'Japonês': 'JP', 'Chinês simplificado': 'CHS', 'Chinês tradicional': 'CHT'}.get(lang, lang)
    base = dict(id_en=d['ID EN'], carta_en=d['Carta inglesa — referência'], codigo_en=d['Código EN'], set_en=d['Set EN'], idioma=idioma, codigo_pr53=d['Código local completo'], nome_local=d['Nome local'])
    if idioma == 'CHT':
        res.append(dict(base, resultado='só no PR #53: chinês tradicional não existe no PokeData', codigos_claude='')); c[(idioma, 'só no PR #53 (CHT)')] += 1; continue
    cands = [dict(id=x['id'], nome=x['name'], unidade=k, numero=k[1])
             for k in en_by.get((str(d['Set EN']).lower(), number_norm(d['Código EN'])), []) for x in units[k]]
    uk, _, how = resolve_reference(d['Carta inglesa — referência'], d['Código EN'], cands)
    if uk is None:
        tag = 'EN ambígua' if how.startswith('ambíguo') else 'EN não localizada'
        res.append(dict(base, resultado=f'carta em inglês {how}', codigos_claude='')); c[(idioma, tag)] += 1; continue
    loc = local_code(d['Código local completo'])
    if loc is None:
        res.append(dict(base, resultado='código local ilegível', codigos_claude='')); c[(idioma, 'código local ilegível')] += 1; continue
    lc, ln = loc
    conf, prov, gray = mine(uk, lang)
    txt = '; '.join(sorted({f"{(x[0] or x[2]).upper() if x[0] else x[2]} {x[1]}" for x in conf}))
    same = lambda xs: any(x[1] == ln and (x[0] == lc or not x[0]) for x in xs)
    match = same_print(loc, {(x[0], x[1]) for x in conf if x[0]})
    if match == 'igual': r = 'igual (arte confirmada aqui)'
    elif match == 'subproduto': r = 'mesmo número; subproduto não distinguido pelo catálogo'
    elif any(x[1] == ln and not x[0] for x in conf): r = 'mesmo número; PokeData não traz o código do set'
    elif same(prov) and conf: r = 'provável aqui, com a mesma candidata'
    elif conf: r = 'outra impressão confirmada aqui; a do PR #53: ' + catalog_state(lang, lc, ln)
    elif same(prov): r = 'provável aqui, com a mesma candidata'
    elif same(gray): r = 'inconclusiva aqui, com a mesma candidata'
    else: r = 'sem confirmação aqui: ' + catalog_state(lang, lc, ln)
    res.append(dict(base, resultado=r, codigos_claude=txt)); c[(idioma, r)] += 1
with open(out, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['id_en', 'carta_en', 'codigo_en', 'set_en', 'idioma', 'codigo_pr53', 'nome_local', 'resultado', 'codigos_claude'])
    w.writeheader(); w.writerows(res)
print('registros confirmados no PR #53:', len(res))
for k in sorted(c): print(f'  {k[0]:4} {c[k]:4}  {k[1]}')
