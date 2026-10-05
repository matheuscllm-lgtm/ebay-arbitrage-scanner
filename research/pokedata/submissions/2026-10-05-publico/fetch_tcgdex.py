"""Etapa 2b — baixa do TCGdex as cartas com raridade, ilustrador e nome nativo (ja, zh-cn, zh-tw, en). Saída: ext/tcgdex_cards_<idioma>.json"""
import json, requests, time, sys
import os
os.makedirs('ext', exist_ok=True)
s = requests.Session()
Q = '{ cards(filters:{}, pagination:{page:%d, itemsPerPage:%d}) @locale(lang:"%s") { id localId name rarity illustrator category image dexId hp stage suffix regulationMark set { id name } } }'
for lang in ['ja', 'zh-cn', 'zh-tw', 'en']:
    if os.path.exists(f'ext/tcgdex_cards_{lang}.json'): continue
    allc = []; page = 1; per = 250
    while True:
        for a in range(4):
            try:
                r = s.post('https://api.tcgdex.net/v2/graphql', json={'query': Q % (page, per, lang)}, timeout=120)
                d = r.json(); break
            except Exception as e:
                print('retry', lang, page, e, flush=True); time.sleep(3 + 3 * a); d = None
        if not d or 'data' not in d or d['data'] is None:
            print('ERR', lang, page, str(d)[:300], flush=True); break
        cs = d['data']['cards'] or []
        allc += cs
        if len(cs) < per: break
        page += 1
        if page % 10 == 0: print(lang, page, len(allc), flush=True)
        time.sleep(0.2)
    json.dump(allc, open(f'ext/tcgdex_cards_{lang}.json', 'w'), ensure_ascii=False)
    print('DONE', lang, len(allc), flush=True)
