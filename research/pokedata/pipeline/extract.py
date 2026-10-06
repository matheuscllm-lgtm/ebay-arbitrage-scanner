"""Etapa 5 — extrai os descritores de todas as imagens. Uso: python extract.py <parte> <total de partes>

Rodar uma parte por núcleo, por exemplo: extract.py 0 2 e extract.py 1 2.
Saída: feat_g_*.npy (miniaturas), feat_p_*/feat_d_*/feat_o_* (pontos SIFT), feat_ids_*.json
"""
import numpy as np, os, sys, json
from feats import *
shard, nsh = int(sys.argv[1]), int(sys.argv[2])
ids = sorted(int(f[:-4]) for f in os.listdir('img') if f.endswith('.jpg'))
ids = [i for i in ids if i % nsh == shard]
G = np.zeros((len(ids), 24 * 16 * 3), np.float32)
P = []; D = []; off = [0]
for n, cid in enumerate(ids):
    im = load_card(cid)
    if im is None:
        off.append(off[-1]); continue
    a = art(im); G[n] = gdesc(a); p, d = sift_feats(a, 300)
    P.append(p); D.append(d); off.append(off[-1] + len(p))
    if n % 5000 == 0: print(shard, n, len(ids), flush=True)
np.save(f'feat_g_{shard}.npy', G); json.dump(ids, open(f'feat_ids_{shard}.json', 'w', encoding="utf-8"))
np.save(f'feat_p_{shard}.npy', np.concatenate(P)); np.save(f'feat_d_{shard}.npy', np.concatenate(D)); np.save(f'feat_o_{shard}.npy', np.array(off, np.int64))
print('DONE', shard, off[-1], flush=True)
