"""Tabela de conferência do pareamento EN ↔ ZH-S ↔ JP/KR/ID (sets EN 2022-2025, market > US$ min).

Preço: dump tcgcsv do dia (TCGPlayer market, melhor variante não-reverse).
Par ZH-S: src/catalog/zh_identity.json (ebay-arbitrage-scanner), junção por (en_set, en_no).
JP/KR/ID: derivados do código JP da linha ZH (KR e ID espelham a numeração JP) — candidato a conferir.
"""
import json
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import quote, quote_plus

import requests
from pathlib import Path

BASE = "https://tcgcsv.com/tcgplayer/3"
ZH = Path(__file__).resolve().parents[2] / "src" / "catalog" / "zh_identity.json"
MIN_USD = float(sys.argv[1]) if __name__ == "__main__" and len(sys.argv) > 1 else 10.0
EXCLUDE = re.compile(r"Promo|McDonald|Trick or Trade|Battle Academy|Prize Pack|Southeast Asia|"
                     r"My First Battle|Classic|Energies", re.I)
STRENGTH = {"tc-jp": "✅ tc-jp", "set+illus+rar": "🟡 set+ilus+rar",
            "set+rar": "🟠 set+rar", "illus+rar": "🟠 ilus+rar"}


def get(url):
    for i in range(4):
        r = requests.get(url, timeout=60, headers={"User-Agent": "pokemon-longterm-outlook/0.1"})
        if r.status_code == 200:
            return r.json()
        time.sleep(2 ** i)
    raise RuntimeError(f"HTTP {r.status_code} {url}")


def norm_no(n):
    n = str(n or "").split("/")[0].strip()
    m = re.match(r"^([A-Za-z]*)0*(\d+)([A-Za-z]*)$", n)
    return f"{m.group(1).upper()}{m.group(2)}{m.group(3).lower()}" if m else n.upper()


def ebay(q):
    return f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(q)}"


def base_name(name):
    name = re.sub(r"\s*\(.*?\)", "", name).strip()
    return re.sub(r"\s*-\s*[A-Z]*\d+/[A-Z]*\d+$", "", name).strip()


def md(s):
    return str(s).replace("|", "\\|")


def main():
    groups = get(f"{BASE}/groups")["results"]
    sets = [g for g in groups if "2022" <= g["publishedOn"][:4] <= "2025"
            and not EXCLUDE.search(g["name"])]
    sets.sort(key=lambda g: g["publishedOn"])

    zh = json.load(open(ZH, encoding="utf-8"))
    by_en = {}
    for r in zh["rows"]:
        if r.get("en_set") and r.get("en_no"):
            by_en.setdefault((r["en_set"], norm_no(r["en_no"])), []).append(r)

    out, stats = [], {"cartas": 0, "com_zh": 0, "tc-jp": 0, "fraco": 0}
    for g in sets:
        prods = get(f"{BASE}/{g['groupId']}/products")["results"]
        prices = get(f"{BASE}/{g['groupId']}/prices")["results"]
        best = {}
        for p in prices:
            if "reverse" in (p.get("subTypeName") or "").lower():
                continue
            m = p.get("marketPrice")
            if isinstance(m, (int, float)) and m > best.get(p["productId"], 0):
                best[p["productId"]] = float(m)
        for prod in prods:
            ext = {e["name"]: e.get("value") for e in prod.get("extendedData") or []}
            if not ext.get("Rarity"):
                continue
            usd = best.get(prod["productId"])
            if not usd or usd <= MIN_USD:
                continue
            num = str(ext.get("Number") or "").strip()
            stats["cartas"] += 1
            zrows = by_en.get((g["name"], norm_no(num)), [])
            out.append((g, prod, ext, num, usd, zrows))
            if zrows:
                stats["com_zh"] += 1
                hows = {z["how"] for z in zrows}
                stats["tc-jp" if hows == {"tc-jp"} else "fraco"] += 1

    dump = requests.get("https://tcgcsv.com/last-updated.txt", headers={"User-Agent": "pokemon-longterm-outlook/0.1"}).text.strip()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"Coleta {now} · tcgcsv dump {dump} · "
          f"catálogo ZH {zh['_meta']['generated_on']} · {len(sets)} sets EN 2022-2025 · "
          f"market > US$ {MIN_USD:.0f}: {stats['cartas']} cartas · com par ZH-S: {stats['com_zh']} "
          f"(só tc-jp: {stats['tc-jp']}, com junção fraca: {stats['fraco']}) · "
          f"sem par: {stats['cartas'] - stats['com_zh']}\n")
    print("| # | Set EN | Carta EN (nº) | Raridade | Market US$ | ZH-S (eBay) | Junção | Fonte ZH | JP nº → KR · ID (eBay) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for i, (g, prod, ext, num, usd, zrows) in enumerate(out, 1):
        bn = base_name(prod["name"])
        tcg = f"https://www.tcgplayer.com/product/{prod['productId']}"
        en = f"[{md(bn)} #{num}]({tcg})"
        price = f"[{usd:,.2f}]({tcg})"
        if not zrows:
            zcell, how, src, jkid = "n/d (sem par no catálogo)", "—", "—", "n/d"
        else:
            zc, hs, ss, jps = [], [], [], []
            for z in zrows:
                zc.append(f"[{z['cn_code']}-{z['cn_no']} {z['cn_rar']}]"
                          f"({ebay(bn + ' ' + z['cn_code'] + ' ' + z['cn_no'])})")
                hs.append(STRENGTH.get(z["how"], z["how"]))
                ss.append(f"[52poke](https://wiki.52poke.com/wiki/{z['page'].replace(' ', '_').replace('(', '%28').replace(')', '%29')})")
                if z.get("jp"):
                    code, no = z["jp"].split()[0].upper(), z["jp"].split()[-1]
                    no3 = no.zfill(3) if no.isdigit() else no
                    j = (f"{code} {no3}: [KR]({ebay(bn + ' ' + code + ' ' + no3 + ' korean')}) · "
                         f"[ID]({ebay(bn + ' ' + code + ' ' + no3 + ' indonesia')})")
                    if j not in jps:
                        jps.append(j)
            zcell, how, src = "<br>".join(zc), "<br>".join(dict.fromkeys(hs)), " ".join(dict.fromkeys(ss))
            jkid = "<br>".join(jps) or "n/d (sem JP na linha)"
        sname = re.sub(r"^(SV\d*|SWSH\d*|ME\d*|SV|SWSH|ME):\s*", "", g["name"])
        print(f"| {i} | {md(sname)} | {en} | {md(ext.get('Rarity'))} | {price} | {zcell} | {how} | {src} | {jkid} |")


if __name__ == "__main__":
    main()
