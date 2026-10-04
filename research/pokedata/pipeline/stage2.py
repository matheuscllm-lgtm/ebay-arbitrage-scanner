"""Comparação detalhada de um par: pontos coincidentes dentro da arte, espalhamento e correlação após alinhar."""
import numpy as np, cv2
from feats import *
def verify2(cidA, cidB, ratio=0.8):
    """detailed verification: inliers, spatial spread (cells of a 6x4 grid), aligned dense NCC on the art interior"""
    A = art(load_card(cidA)); B = art(load_card(cidB))
    p1, d1 = sift_feats(A, 500); p2, d2 = sift_feats(B, 500)
    res = dict(n=0, cells=0, ncc=-1.0, ncc0=-1.0)
    gA = cv2.cvtColor(A, cv2.COLOR_BGR2GRAY).astype(np.float32); gB = cv2.cvtColor(B, cv2.COLOR_BGR2GRAY).astype(np.float32)
    h, w = gA.shape
    def ncc(x, y):
        m = 0.12
        x = cv2.GaussianBlur(x, (0, 0), 2)[int(h * m):int(h * (1 - m)), int(w * m):int(w * (1 - m))]
        y = cv2.GaussianBlur(y, (0, 0), 2)[int(h * m):int(h * (1 - m)), int(w * m):int(w * (1 - m))]
        x = x - x.mean(); y = y - y.mean()
        return float((x * y).sum() / (np.sqrt((x * x).sum() * (y * y).sum()) + 1e-6))
    res['ncc0'] = ncc(gA, gB)
    if len(d1) < 8 or len(d2) < 8: return res
    a = d1.astype(np.float32); b = d2.astype(np.float32)
    d = (a * a).sum(1)[:, None] + (b * b).sum(1)[None, :] - 2 * a @ b.T
    idx = np.argsort(d, axis=1)[:, :2]; r = np.arange(len(a))
    good = d[r, idx[:, 0]] < (ratio ** 2) * d[r, idx[:, 1]]
    good &= d.argmin(axis=0)[idx[:, 0]] == r
    if good.sum() < 6: return res
    src = p1[good]; dst = p2[idx[good, 0]]
    M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=5.0, maxIters=1000, confidence=0.995)
    if M is None: return res
    s = float(np.hypot(M[0, 0], M[1, 0])); rot = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
    if not (0.8 < s < 1.25 and abs(rot) < 8 and abs(M[0, 2]) < 60 and abs(M[1, 2]) < 60): return res
    inl = inl.ravel().astype(bool); pts = src[inl]
    res['n'] = int(inl.sum())
    res['cells'] = len({(int(x * 6 / w), int(y * 4 / h)) for x, y in pts})
    # interior inliers (exclude 10% border band)
    res['n_in'] = int(((pts[:, 0] > w * .1) & (pts[:, 0] < w * .9) & (pts[:, 1] > h * .12) & (pts[:, 1] < h * .9)).sum())
    Bw = cv2.warpAffine(gB, cv2.invertAffineTransform(M), (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    res['ncc'] = ncc(gA, Bw)
    return res
