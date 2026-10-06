"""Funções comuns: leitura dos dados, separação de nome base e variante, agrupamento em cartas únicas."""
import json, re, unicodedata
from collections import defaultdict
from pathlib import Path

BALLS = r'(?:Poke ?[Bb]all|Master ?[Bb]all|Dusk Ball|Love Ball|Quick Ball|Friend Ball)'
STRIP = [
    (r'\[(?:non-holofoil|reverse holofoil|holofoil)\]', None),
    (r'\b(?:Team Rocket )?Reverse Holo(?:foil)?(?: Ditto)?$', 'Reverse Holo'),
    (r'\bReverse$', 'Reverse Holo'),
    (r'\bEnergy Symbol Pattern(?: Holofoil)?$', 'Energy Symbol Pattern'),
    (r'\bMirror Foil(?: Holofoil)?$', 'Mirror Foil'),
    (BALLS + r'(?: Pattern)?(?: Reverse)? Holo(?:foil)?$', 'Ball Pattern'),
    (r'(?<=\S )' + BALLS + r'(?: Pattern)?$', 'Ball Pattern'),
    (r'\bCracked Ice Holo(?: Holofoil)?$', 'Cracked Ice Holo'),
    (r'\bCo(?:smos|smo|mos) Holo(?:foil)?$', 'Cosmos Holo'),
    (r'\bGlossy Finish$', 'Glossy'),
    (r'\bHolofoil$', 'Holo'),
    (r'\bHolo$', 'Holo'),
    (r'\b1st Edition$', '1st Edition'),
    (r'\bUnlimited$', 'Unlimited'),
    (r'\bShadowless$', 'Shadowless'),
    (r'\b(?:Staff Prerelease|Prerelease Staff)$', 'Prerelease Staff'),
    (r'\bPrerelease$', 'Prerelease'),
    (r'\b(?:World Championships |Worlds \d+ )?Staff$', 'Staff'),
    (r'\bStamped$', 'Stamped'),
    (r'\bPokemon Center(?: Exclusive)?(?: NY)?$', 'Pokemon Center'),
    (r'\b(?:Worlds \d+ )?(?:Quarter Finalist|Semi Finalist|Finalist|Champion|Top Sixteen|Top Thirty Two|Top Thirty|Top 16|Top 32|Winner)$', 'Trophy'),
    (r'\bSecret$', 'Secret'),
]
STRIP = [(re.compile(p, re.I), tag) for p, tag in STRIP]

def split_name(name):
    """return (base_name, [variant tags])"""
    n = name.strip()
    tags = []
    m = re.search(r'\[(non-holofoil|reverse holofoil|holofoil)\]', n, re.I)
    if m:
        tags.append({'non-holofoil': 'Non-Holo', 'reverse holofoil': 'Reverse Holo', 'holofoil': 'Holo'}[m.group(1).lower()])
        n = re.sub(r'\s*\[(non-holofoil|reverse holofoil|holofoil)\]\s*', ' ', n, flags=re.I).strip()
    changed = True
    while changed:
        changed = False
        for rx, tag in STRIP[1:]:
            m = rx.search(n)
            if m and m.start() > 0:
                rest = n[:m.start()].strip()
                if rest:
                    n = rest; tags.append(tag); changed = True
    return re.sub(r'\s+', ' ', n).strip(), list(dict.fromkeys(tags[::-1]))

def key(s):
    # ♀/♂ são identidade (Nidoran♀ ≠ Nidoran♂) e somem no corte ASCII; viram 'f'/'m',
    # a mesma convenção de catalog.py, então 'Nidoran F' == 'Nidoran♀' (cadastro duplo).
    s = s.replace('\u2640', 'f').replace('\u2642', 'm')
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = s.lower().replace('&', 'and')
    return re.sub(r'[^a-z0-9]', '', s)

STOP = {'the','of','and','s'}
def tokens(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    s = s.replace("'s", '').replace('’s', '')
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return [t for t in s.split() if t not in STOP]

def load():
    manifest = Path('collection_manifest.json')
    if manifest.exists() and json.loads(manifest.read_text(encoding="utf-8")).get('complete') is not True:
        raise RuntimeError('Incomplete collection: refusing stale all_cards.json')
    sets = {s['id']: s for s in json.load(open('sets.json', encoding="utf-8"))}
    cards = json.load(open('all_cards.json', encoding="utf-8"))
    return sets, cards

def art_units(cards):
    """group records into art units keyed by (set_id, num, name key)"""
    units = defaultdict(list)
    for c in cards:
        base, tags = split_name(c['name'])
        c['_base'] = base; c['_tags'] = tags
        units[(c['set_id'], c['num'], key(base))].append(c)
    return units

def rep_image(recs):
    ok = [r for r in recs if 'placeholder' not in r['img_url']]
    if not ok: return None
    def score(r):
        u = r['img_url']
        pen = 0
        if re.search(r'(r|--\d+)\.webp$', u): pen += 2
        if r['_tags']: pen += 1
        return (pen, len(r['name']))
    return min(ok, key=score)

