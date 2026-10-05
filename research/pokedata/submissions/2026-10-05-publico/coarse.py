"""Semelhança global da carta inteira em baixa resolução: usada como apoio para artes texturizadas."""
import numpy as np, cv2, json
rep = json.load(open('unit_rep.json'))
_cache = {}
def small(k):
    cid = rep[f"{k[0]}|{k[1]}|{k[2]}"]
    if cid in _cache: return _cache[cid]
    im = cv2.imread(f'img/{cid}.jpg')
    im = cv2.resize(im, (92, 128), interpolation=cv2.INTER_AREA)
    g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 2.0)
    lab = cv2.cvtColor(cv2.GaussianBlur(im, (0, 0), 2.0), cv2.COLOR_BGR2LAB).astype(np.float32)[:, :, 1:] - 128.0
    if len(_cache) > 20000: _cache.clear()
    _cache[cid] = (g, lab); return _cache[cid]
def _ncc(x, y):
    x = x - x.mean(); y = y - y.mean()
    return float((x * x).sum() ** -0.5 * (y * y).sum() ** -0.5 * (x * y).sum()) if x.std() > 1e-3 and y.std() > 1e-3 else 0.0
def coarse(a, b):
    """coarse whole-card and art-area correlation with a small shift search, plus chroma agreement of the art area"""
    ga, la = small(a); gb, lb = small(b)
    best = (-1, 0, 0)
    for dy in (-3, -1, 0, 1, 3):
        for dx in (-3, -1, 0, 1, 3):
            A = ga[8 + max(dy, 0):120 + min(dy, 0), 8 + max(dx, 0):84 + min(dx, 0)]
            B = gb[8 - min(dy, 0):120 - max(dy, 0), 8 - min(dx, 0):84 - max(dx, 0)]
            v = _ncc(A, B)
            if v > best[0]: best = (v, dy, dx)
    v, dy, dx = best
    # art area rows 14..62 (of 128)
    A = ga[14 + max(dy, 0):62 + min(dy, 0), 8 + max(dx, 0):84 + min(dx, 0)]; B = gb[14 - min(dy, 0):62 - max(dy, 0), 8 - min(dx, 0):84 - max(dx, 0)]
    art = _ncc(A, B)
    A = la[14 + max(dy, 0):62 + min(dy, 0), 8 + max(dx, 0):84 + min(dx, 0)].ravel(); B = lb[14 - min(dy, 0):62 - max(dy, 0), 8 - min(dx, 0):84 - max(dx, 0)].ravel()
    ch = float(A @ B / (np.linalg.norm(A) * np.linalg.norm(B) + 1e-6))
    # centred chroma correlation (sensitive to recolouring of the subject)
    chc = _ncc(A, B)
    return dict(full=v, art=art, ch=ch, chc=chc)
