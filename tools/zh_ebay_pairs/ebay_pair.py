"""Comparação EN × ZH-S × KR × ID dentro do eBay (menor anúncio ativo, raw, preço fixo).

Seleção: cartas EN 2022-2025 com par ZH-S + nº JP no catálogo (zh_identity.json); as TOP_N
de maior market TCGPlayer entram (TCGPlayer só ORDENA a seleção — todo preço comparado é eBay).
Cada idioma = 1 busca Browse API (EBAY_US marketplace, vendedor de qualquer país).
Guards: título sem marcador de graded; nº da impressão no título; marcador do idioma
no título (ZH/KR/ID) e, no EN, ausência de marcador não-EN. Nunca inventa: sem anúncio → n/d.
"""
import json
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus

from pathlib import Path  # noqa: E402
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "zh_ebay_pairs.json"  # local, gitignored
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import urllib.parse  # noqa: E402
from src.ebay_api import (EbayClient, EbayBudgetExceeded, SEARCH_URL, CCG_CATEGORY_ID,  # noqa: E402
                          parse_search_payload)
import pair_table as pt  # noqa: E402

TOP_N = int(sys.argv[1]) if len(sys.argv) > 1 else 120
GRADED = re.compile(r"\b(psa|bgs|cgc|sgc|tag|ace|graded|gem mint|slab)\b", re.I)
LANG = {
    "zh": re.compile(r"chinese|s-chinese|simplified|中文|简体|簡體", re.I),
    "kr": re.compile(r"korean|korea|한국", re.I),
    "id": re.compile(r"indonesia", re.I),
}
JUNK = re.compile(r"\bcase\b|skin|metal|insert|custom|display|binder|you pick|pick your|choose|"
                  r"proxy|orica|fan ?art|sticker|playmat|sleeve|toploader|\blots?\b|bundle|poster|"
                  r"acrylic|keychain|\bcoin\b|digital|code card|replica|minimum|extended art|"
                  r"magnetic|frame|\bstand\b|token|jumbo|oversized|empty|art card|reprint|30th|anniversary|"
                  r"celebration|classic collection", re.I)
NON_EN = re.compile(r"japanese|japan|jpn|korean|korea|chinese|indonesia|thai|german|french|"
                    r"italian|italiano|italy|\bita\b|spanish|espa[nñ]ol|portuguese|portugu[eê]s|deutsch|"
                    r"fran[cç]ais|\bfr\b|\bde\b|\bes\b|\bpt\b|\bjp\b|\bkr\b|\bcn\b", re.I)


def num_in(title, num):
    num = str(num).split("/")[0].strip().lower()
    m = re.match(r"^([a-z]*)0*(\d+)$", num)
    if not m:
        return num in title.lower()
    pre, digits = m.groups()
    return re.search(rf"(?<![a-z0-9]){pre}0*{digits}(?![0-9])", title.lower()) is not None


def code_in(title, code):
    return re.search(rf"(?<![a-z0-9]){re.escape(code.lower())}(?![a-z0-9])", title.lower()) is not None


def ebay_search_url(q):
    return f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(q)}&_sacat=183454&LH_BIN=1"


def name_in(title, bn):
    word = re.sub(r"'s$", "", bn.split()[0]).lower()
    return word in title.lower()


def cheapest(client, query, ok):
    try:
        # ordem por RELEVÂNCIA (sort=price traz os 200 mais baratos da busca frouxa e perde a carta)
        params = {"q": query, "category_ids": CCG_CATEGORY_ID, "limit": "200",
                  "filter": "price:[1..],priceCurrency:USD,buyingOptions:{FIXED_PRICE}"}
        items = parse_search_payload(client._request_search_json(SEARCH_URL + "?" + urllib.parse.urlencode(params)))
    except EbayBudgetExceeded:
        raise
    except Exception as exc:  # erro de fonte: n/d honesto
        return None, f"erro: {type(exc).__name__}", 0
    good = [i for i in items if i.price and not GRADED.search(i.title) and not JUNK.search(i.title)
            and ok(i.title)]
    good.sort(key=lambda i: i.price + (i.shipping or 0))
    # guard interno ao eBay: com >=3 anúncios plausíveis, abaixo de 50% da mediana deles = lixo provável
    if len(good) >= 3:
        tots = sorted(i.price + (i.shipping or 0) for i in good)
        med = tots[len(tots) // 2]
        good = [i for i in good if i.price + (i.shipping or 0) >= 0.5 * med]
    return (good[0] if good else None), None, len(items)


def main():
    # catálogo + preços TCGPlayer só para ORDENAR a seleção (mesma coleta do pair_table)
    groups = pt.get(f"{pt.BASE}/groups")["results"]
    sets = [g for g in groups if "2022" <= g["publishedOn"][:4] <= "2025" and not pt.EXCLUDE.search(g["name"])]
    zh = json.load(open(pt.ZH))
    by_en = {}
    for r in zh["rows"]:
        if r.get("en_set") and r.get("en_no"):
            by_en.setdefault((r["en_set"], pt.norm_no(r["en_no"])), []).append(r)
    cands = []
    for g in sets:
        prods = pt.get(f"{pt.BASE}/{g['groupId']}/products")["results"]
        prices = pt.get(f"{pt.BASE}/{g['groupId']}/prices")["results"]
        best = {}
        for p in prices:
            if "reverse" in (p.get("subTypeName") or "").lower():
                continue
            m = p.get("marketPrice")
            if isinstance(m, (int, float)) and m > best.get(p["productId"], 0):
                best[p["productId"]] = float(m)
        for prod in prods:
            ext = {e["name"]: e.get("value") for e in prod.get("extendedData") or []}
            usd = best.get(prod["productId"])
            if not ext.get("Rarity") or not usd or usd <= 10:
                continue
            num = str(ext.get("Number") or "").strip()
            zrows = [z for z in by_en.get((g["name"], pt.norm_no(num)), [])
                     if z.get("jp") and re.match(r"^\S+ \d+$", z["jp"])]
            if not zrows:
                continue
            z = next((z for z in zrows if z["how"] == "tc-jp"), zrows[0])
            cands.append((usd, g, prod, num, z, len({x['jp'] for x in zrows}) > 1))
    cands.sort(key=lambda c: -c[0])
    sel = cands[:TOP_N]

    client = EbayClient()
    client.max_calls = 500
    rows, stop = [], None
    for usd, g, prod, num, z, multi in sel:
        bn = pt.base_name(prod["name"])
        jcode, jno = z["jp"].split()[0].upper(), z["jp"].split()[1]
        jno3 = jno.zfill(3)
        q = {
            "en": f"{bn} {num}",
            "zh": f"{bn} {z['cn_code']} chinese",
            "kr": f"{bn} {jcode} korean",
            "id": f"{bn} {jcode} indonesia",
        }
        ok = {
            "en": lambda t: name_in(t, bn) and num_in(t, num) and not NON_EN.search(t),
            "zh": lambda t: name_in(t, bn) and LANG["zh"].search(t) and code_in(t, z["cn_code"]) and num_in(t, z["cn_no"].split()[-1] if " " in z["cn_no"] else z["cn_no"]),
            "kr": lambda t: name_in(t, bn) and LANG["kr"].search(t) and code_in(t, jcode) and num_in(t, jno),
            "id": lambda t: name_in(t, bn) and LANG["id"].search(t) and code_in(t, jcode) and num_in(t, jno),
        }
        res = {}
        try:
            for lang in ("en", "zh", "kr", "id"):
                res[lang] = cheapest(client, q[lang], ok[lang]) + (q[lang],)
        except EbayBudgetExceeded as exc:
            stop = str(exc)
            break
        rows.append((usd, g, prod, num, z, multi, res))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    dump = {"collected": now, "calls": client.calls, "selected": len(sel), "cands": len(cands),
            "stop": stop, "rows": []}
    for usd, g, prod, num, z, multi, res in rows:
        dump["rows"].append({
            "name": pt.base_name(prod["name"]), "set": g["name"], "num": num, "how": z["how"],
            "multi": multi, "zh": f"{z['cn_code']}-{z['cn_no']}/{z.get('cn_total') or '?'}",
            "jp": f"{z['jp'].split()[0].upper()} {z['jp'].split()[1].zfill(3)}",
            "res": {l: {"query": r[3], "err": r[1], "n": r[2],
                        "item": None if not r[0] else {"price": r[0].price, "shipping": r[0].shipping,
                                                       "url": r[0].url.split("?")[0], "title": r[0].title,
                                                       "country": r[0].country}}
                    for l, r in res.items()}})
    OUT.parent.mkdir(exist_ok=True)
    json.dump(dump, open(OUT, "w"), ensure_ascii=False, indent=1)
    render(dump)


def render(d):
    LBL = {"zh": "ZH-S", "kr": "KR", "id": "ID"}
    def item_cell(it):
        tot = it["price"] + (it["shipping"] or 0)
        ship = "frete ?" if it["shipping"] is None else (f"+{it['shipping']:.2f} frete" if it["shipping"] else "frete grátis")
        t = pt.md(it["title"][:70] + ("…" if len(it["title"]) > 70 else ""))
        return f"[US$ {it['price']:,.2f}]({it['url']}) {ship} · {it.get('country') or '?'} — {t}", tot
    pairs, missing = [], {"zh": 0, "kr": 0, "id": 0}
    no_en = 0
    for r in d["rows"]:
        en = r["res"]["en"]["item"]
        if not en:
            no_en += 1
            continue
        for l in ("zh", "kr", "id"):
            o = r["res"][l]["item"]
            if not o:
                missing[l] += 1
                continue
            pairs.append((r, l, en, o))
    print(f"Coleta eBay {d['collected']} · {d['calls']} chamadas Browse API · {len(d['rows'])}/{d['selected']} cartas "
          f"(top por preço entre {d['cands']} com par ZH-S + nº JP) · {len(pairs)} pares EN × idioma com DOIS anúncios · "
          f"sem par de anúncio: ZH-S {missing['zh']} · KR {missing['kr']} · ID {missing['id']}"
          + (f" · sem anúncio EN: {no_en}" if no_en else "") + (f" · PARCIAL: {d['stop']}" if d["stop"] else "") + "\n")
    print("| # | Carta (set · nº EN) | Idioma (impressão) | Anúncio EN | Anúncio no outro idioma | Dif. US$ (EN − outro, c/ frete) | EN ÷ outro | Flags |")
    print("|---|---|---|---|---|---|---|---|")
    for i, (r, l, en, o) in enumerate(pairs, 1):
        sname = re.sub(r"^(SV\d*|SWSH\d*|ME\d*|SV|SWSH|ME):\s*", "", r["set"])
        ec, et = item_cell(en)
        oc, ot = item_cell(o)
        imp = r["zh"] if l == "zh" else r["jp"]
        flags = []
        if ot < 0.3 * et:
            flags.append("⚠️ <30% do EN: conferir foto/idioma")
        if r["how"] != "tc-jp":
            flags.append("🟡 junção fraca")
        if r["multi"]:
            flags.append("⚠️ +1 impressão ZH")
        if en.get("shipping") is None or o.get("shipping") is None:
            flags.append("frete desconhecido")
        print(f"| {i} | {pt.md(r['name'])} ({pt.md(sname)} · #{r['num']}) | {LBL[l]} ({imp}) | {ec} | {oc} | "
              f"{et - ot:+,.2f} | {et / ot:.1f}× | {'; '.join(flags) or '—'} |")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[2] == "--render":
        render(json.load(open(OUT)))
    else:
        main()
