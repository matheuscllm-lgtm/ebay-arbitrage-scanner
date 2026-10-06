"""Etapa 2 — baixa as fontes externas usadas para completar o que o PokeData não publica.

- pokemon-tcg-data (GitHub): raridade, ilustrador e nome oficial das cartas em inglês
- TCGdex: listas de sets (en, ja, zh-tw, zh-cn) e detalhe de cada set
- PokeAPI: nome de cada Pokémon em japonês e chinês

Saídas em ext/. As cartas do TCGdex (raridade e nome japonês) vêm de fetch_tcgdex.py.
"""
import json, os, re, time, urllib.parse
import requests
from concurrent.futures import ThreadPoolExecutor

os.makedirs('ext/ptcg', exist_ok=True); os.makedirs('ext/tcgdex_sets', exist_ok=True)
S = requests.Session()

def validated_set_id(sid):
    """IDs externos são componentes de arquivo, nunca caminhos (inclusive no Windows)."""
    if (not isinstance(sid, str) or not 1 <= len(sid) <= 100
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]*', sid)
            or '..' in sid or sid.endswith('.')
            or re.match(r'(?i)^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', sid)):
        raise ValueError('Invalid external set ID')
    return sid

def ptcg_job(p):
    sid = validated_set_id(p['id'])
    return f"{RAW}/cards/en/{urllib.parse.quote(sid, safe='')}.json", f"ext/ptcg/{sid}.json"

def tcgdex_job(lang, sid):
    if lang not in ('ja', 'zh-cn', 'zh-tw'):
        raise ValueError('Invalid TCGdex language')
    sid = validated_set_id(sid)
    return f"https://api.tcgdex.net/v2/{lang}/sets/{urllib.parse.quote(sid, safe='')}", f"ext/tcgdex_sets/{lang}__{sid}.json"

def save(url, out):
    if os.path.exists(out) and os.path.getsize(out) > 0: return True
    for a in range(3):
        try:
            r = S.get(url, timeout=60)
            if r.status_code == 200:
                open(out, 'wb').write(r.content); return True
            if r.status_code == 404: return False
        except Exception:
            pass
        time.sleep(2 + 2 * a)
    return False

# TCGdex: listas de sets por idioma
for lang in ('en', 'ja', 'zh-tw', 'zh-cn'):
    save(f'https://api.tcgdex.net/v2/{lang}/sets', f'ext/tcgdex_sets_{lang}.json')

# pokemon-tcg-data: sets e cartas em inglês
RAW = 'https://raw.githubusercontent.com/PokemonTCG/pokemon-tcg-data/master'
save(f'{RAW}/sets/en.json', 'ext/ptcg_sets_en.json')
psets = json.load(open('ext/ptcg_sets_en.json', encoding="utf-8"))
pjobs = [ptcg_job(p) for p in psets]  # validate all IDs before starting card downloads
with ThreadPoolExecutor(4) as ex:
    ok = list(ex.map(lambda job: save(*job), pjobs))
print('pokemon-tcg-data:', sum(ok), 'de', len(psets), 'sets')

# PokeAPI: nomes das espécies por idioma
PAPI = 'https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv'
save(f'{PAPI}/pokemon_species_names.csv', 'ext/species_names.csv')
save(f'{PAPI}/languages.csv', 'ext/languages.csv')

# TCGdex: detalhe de cada set (nome nativo, data de lançamento, total oficial)
jobs = [tcgdex_job(lang, st['id']) for lang in ('ja', 'zh-cn', 'zh-tw') for st in json.load(open(f'ext/tcgdex_sets_{lang}.json', encoding="utf-8"))]
def one(j):
    return save(*j)
with ThreadPoolExecutor(4) as ex:
    ok = list(ex.map(one, jobs))
print('TCGdex sets:', sum(ok), 'de', len(jobs))
