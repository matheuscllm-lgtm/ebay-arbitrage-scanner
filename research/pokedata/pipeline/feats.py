"""Rotinas de imagem: recorte da área da arte, descritor global (miniatura LAB) e pontos SIFT."""
import numpy as np, cv2, os, sys, json, pickle
W, H = 368, 512
CROP = (int(0.105 * H), int(0.50 * H), int(0.075 * W), int(0.925 * W))  # y0,y1,x0,x1 art region
def load_card(cid):
    im = cv2.imread(f'img/{cid}.jpg')
    if im is None: return None
    return cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA)
def art(im):
    y0, y1, x0, x1 = CROP
    return im[y0:y1, x0:x1]
def gdesc(a):
    # global descriptor: blurred low-res LAB thumbnail, per-channel standardized
    t = cv2.resize(cv2.GaussianBlur(a, (0, 0), 3), (24, 16), interpolation=cv2.INTER_AREA)
    t = cv2.cvtColor(t, cv2.COLOR_BGR2LAB).astype(np.float32)
    g = t[:, :, 0]; g = (g - g.mean()) / (g.std() + 1e-6)
    ab = t[:, :, 1:] - 128.0; ab = ab / (np.abs(ab).mean() + 1e-6) * 0.5
    v = np.concatenate([g.ravel() * 1.0, ab.ravel() * 0.6])
    return (v / (np.linalg.norm(v) + 1e-9)).astype(np.float32)
_sift = None
def sift_feats(a, nmax=350):
    global _sift
    if _sift is None: _sift = cv2.SIFT_create(nfeatures=nmax, contrastThreshold=0.03)
    g = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    kp, des = _sift.detectAndCompute(g, None)
    if des is None or len(kp) == 0:
        return np.zeros((0, 2), np.float32), np.zeros((0, 128), np.uint8)
    pts = np.array([k.pt for k in kp], np.float32)
    # RootSIFT, quantized
    des = des / (des.sum(axis=1, keepdims=True) + 1e-7); des = np.sqrt(des)
    return pts, (des * 255).astype(np.uint8)
def verify(f1, f2, ratio=0.8):
    """returns number of geometric inliers under near-identity similarity transform"""
    p1, d1 = f1; p2, d2 = f2
    if len(d1) < 8 or len(d2) < 8: return 0, None
    a = d1.astype(np.float32); b = d2.astype(np.float32)
    # distances via dot (RootSIFT approx unit norm *255)
    d = (a * a).sum(1)[:, None] + (b * b).sum(1)[None, :] - 2 * a @ b.T
    idx = np.argsort(d, axis=1)[:, :2]
    r = np.arange(len(a))
    best = d[r, idx[:, 0]]; second = d[r, idx[:, 1]]
    good = best < (ratio ** 2) * second
    # mutual check
    back = d.argmin(axis=0)
    good &= back[idx[:, 0]] == r
    if good.sum() < 6: return int(good.sum()), None
    src = p1[good]; dst = p2[idx[good, 0]]
    M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=6.0, maxIters=500, confidence=0.99)
    if M is None: return 0, None
    s = float(np.hypot(M[0, 0], M[1, 0])); rot = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
    tx, ty = float(M[0, 2]), float(M[1, 2])
    n = int(inl.sum())
    ok = 0.8 < s < 1.25 and abs(rot) < 8 and abs(tx) < 60 and abs(ty) < 60
    return (n if ok else 0), (round(s, 3), round(rot, 1), round(tx), round(ty))
if __name__ == '__main__':
    # extract features for all downloaded images (shard by argv)
    shard, nsh = int(sys.argv[1]), int(sys.argv[2])
    ids = sorted(int(f[:-4]) for f in os.listdir('img') if f.endswith('.jpg'))
    ids = [i for i in ids if i % nsh == shard]
    G = np.zeros((len(ids), 24 * 16 * 3), np.float32); F = {}
    for n, cid in enumerate(ids):
        im = load_card(cid)
        if im is None: continue
        a = art(im); G[n] = gdesc(a); F[cid] = sift_feats(a)
        if n % 5000 == 0: print(shard, n, len(ids), flush=True)
    np.save(f'feat_g_{shard}.npy', G); json.dump(ids, open(f'feat_ids_{shard}.json', 'w', encoding="utf-8"))
    pickle.dump(F, open(f'feat_sift_{shard}.pkl', 'wb'), protocol=4)
    print('DONE', shard, flush=True)
