"""Etapa 9d — segunda comparação para uma lista avulsa de pares. Uso: python stage2_pairs.py lim_pairs.pkl s2_LIM.pkl"""
import pickle, json, sys, time, os
from multiprocessing import Pool
from stage2 import verify2
rep = json.load(open('unit_rep.json', encoding="utf-8"))
HAS = {int(f[:-4]) for f in os.listdir('img') if f.endswith('.jpg')}
def cid(k): return rep.get(f"{k[0]}|{k[1]}|{k[2]}")
def work(p):
    a, b = p
    try: r = verify2(cid(a), cid(b))
    except Exception as e: r = dict(n=0, cells=0, ncc=-1.0, ncc0=-1.0, err=str(e))
    return (a, b, r)
if __name__ == '__main__':
    inp, out = sys.argv[1], sys.argv[2]
    sel = [(a, b) for a, b in pickle.load(open(inp, 'rb')) if cid(a) in HAS and cid(b) in HAS]
    t = time.time(); res = {}
    with Pool(2) as p:
        for i, (a, b, r) in enumerate(p.imap_unordered(work, sel, chunksize=40)): res[(a, b)] = r
    pickle.dump(res, open(out, 'wb')); print('DONE', len(res), round(time.time() - t), flush=True)
