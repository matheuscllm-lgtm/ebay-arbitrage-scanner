"""Etapa 8 — segunda comparação dos pares promissores. Uso: python stage2_run.py EN_JA (ou EN_CH, CH_JA)

Entrada: pairs_<tag>.pkl   Saída: s2_<tag>.pkl
"""
import pickle, json, sys, time
from multiprocessing import Pool
from stage2 import verify2
rep = json.load(open('unit_rep.json'))
def cid(k): return rep[f"{k[0]}|{k[1]}|{k[2]}"]
def work(p):
    a, b = p
    try: r = verify2(cid(a), cid(b))
    except Exception as e: r = dict(n=0, cells=0, ncc=-1.0, ncc0=-1.0, err=str(e))
    return (a, b, r)
if __name__ == '__main__':
    tag = sys.argv[1]
    pairs = pickle.load(open(f'pairs_{tag}.pkl', 'rb'))
    sel = sorted({(x[0], x[1]) for x in pairs if x[2] >= 8 or x[3] >= 0.8})
    print(tag, 'pairs', len(pairs), 'selected', len(sel), flush=True)
    t = time.time(); out = {}
    with Pool(2) as p:
        for i, (a, b, r) in enumerate(p.imap_unordered(work, sel, chunksize=50)):
            out[(a, b)] = r
            if i % 5000 == 0: print(i, round(time.time() - t), flush=True)
    pickle.dump(out, open(f's2_{tag}.pkl', 'wb'))
    print('DONE', tag, len(out), round(time.time() - t), flush=True)
