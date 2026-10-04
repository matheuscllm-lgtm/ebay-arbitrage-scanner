"""Etapa 4 — baixa uma imagem por carta única (reduzida a 512 px de altura).

Saída: img/<id>.jpg, unit_rep.json (carta única -> id da imagem), img_fail.log
"""
import json, os, io, sys, time, threading
import requests
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from common import *
sets, cards = load()
units = art_units(cards)
os.makedirs('img', exist_ok=True)
jobs = []
for k, recs in units.items():
    r = rep_image(recs)
    if r is None: continue
    jobs.append((r['id'], r['img_url']))
json.dump({f"{k[0]}|{k[1]}|{k[2]}": (rep_image(v)['id'] if rep_image(v) else None) for k, v in units.items()}, open('unit_rep.json', 'w'))
print('jobs', len(jobs), flush=True)
tl = threading.local()
def sess():
    if not hasattr(tl, 's'):
        tl.s = requests.Session()
    return tl.s
cnt = {'ok': 0, 'fail': 0}
def dl(job):
    cid, url = job
    out = f"img/{cid}.jpg"
    if os.path.exists(out): cnt['ok'] += 1; return
    for a in range(3):
        try:
            r = sess().get(url, timeout=40)
            if r.status_code == 200:
                im = Image.open(io.BytesIO(r.content)).convert('RGBA')
                bg = Image.new('RGB', im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[3])
                w, h = bg.size
                if h > 512: bg = bg.resize((round(w * 512 / h), 512), Image.LANCZOS)
                bg.save(out + '.tmp', 'JPEG', quality=90); os.replace(out + '.tmp', out)
                cnt['ok'] += 1; return
            if r.status_code == 404: break
        except Exception as e:
            time.sleep(1 + a)
    cnt['fail'] += 1
    with open('img_fail.log', 'a') as f: f.write(f"{cid}\t{url}\n")
t = time.time()
with ThreadPoolExecutor(12) as ex:
    for i, _ in enumerate(ex.map(dl, jobs)):
        if i % 2000 == 0: print(i, cnt, round(time.time() - t), flush=True)
print('DONE', cnt, round(time.time() - t), flush=True)
