"""Apoio — monta folhas de contato (pares lado a lado) para conferência visual."""
import json, sys
from PIL import Image, ImageDraw
rep = json.load(open('unit_rep.json', encoding="utf-8"))
def cid(k): return rep[f"{k[0]}|{k[1]}|{k[2]}"]
def sheet(pairs, out, labels=None, cols=4, h=300):
    w = int(h * 368 / 512)
    rows = (len(pairs) + cols - 1) // cols
    S = Image.new('RGB', (cols * (2 * w + 14), rows * (h + 22)), 'white'); d = ImageDraw.Draw(S)
    for i, (a, b) in enumerate(pairs):
        x = (i % cols) * (2 * w + 14); y = (i // cols) * (h + 22)
        for j, k in enumerate((a, b)):
            try: im = Image.open(f"img/{cid(k)}.jpg").resize((w, h))
            except Exception: im = Image.new('RGB', (w, h), 'gray')
            S.paste(im, (x + j * w, y + 20))
        d.text((x + 2, y + 4), (labels[i] if labels else str(i))[:70], fill='black')
    S.save(out, quality=85)
