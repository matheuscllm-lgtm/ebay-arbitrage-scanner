"""Par EN × ZH-S dentro do eBay (menor anúncio ativo, raw, preço fixo), crivo EN ÷ ZH ≥ 4×.

Seleção: cartas EN 2022-2025 com market TCGPlayer > US$10 e par ZH-S no catálogo
(zh_identity.json); as TOP_N de maior market entram (TCGPlayer só ORDENA a seleção — todo
preço comparado é eBay). Cada idioma = 1 busca Browse API (EBAY_US, vendedor de qualquer
país). Guards em guards.py. Na entrega, cada link dos pares ≥ 4× é reconferido por getItem
(à venda agora); o que caiu é declarado, não mostrado. Nunca inventa: sem anúncio → sem par.

    python ebay_pair.py 200            # coleta + verificação + tabela
    python ebay_pair.py 200 --render   # re-renderiza o último JSON local (sem eBay)
"""
import json
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "zh_ebay_pairs.json"  # local, gitignored
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.ebay_api import (EbayClient, EbayApiError, EbayBudgetExceeded, SEARCH_URL,  # noqa: E402
                          CCG_CATEGORY_ID, parse_search_payload)
import guards  # noqa: E402
import pair_table as pt  # noqa: E402

MIN_USD = 10.0


def _shipping(payload):
    """Frete USD da 1ª opção com valor no getItem; None = continua desconhecido."""
    for opt in payload.get("shippingOptions") or []:
        cost = opt.get("shippingCost") or {}
        if cost.get("value") is not None:
            return float(cost["value"]) if cost.get("currency") == "USD" else None
    return None


def cheapest(client, query, ok, drop_low_outliers=False):
    try:
        # ordem por RELEVÂNCIA (sort=price traz os 200 mais baratos da busca frouxa e perde a carta)
        params = {"q": query, "category_ids": CCG_CATEGORY_ID, "limit": "200",
                  "filter": "price:[1..],priceCurrency:USD,buyingOptions:{FIXED_PRICE}"}
        items = parse_search_payload(client._request_search_json(SEARCH_URL + "?" + urllib.parse.urlencode(params)))
    except EbayBudgetExceeded:
        raise
    except Exception as exc:  # erro de fonte: n/d honesto
        return None, f"erro: {type(exc).__name__}", 0
    good = [i for i in items if i.price and ok(i.title)]
    good.sort(key=lambda i: i.price + (i.shipping or 0))
    # guard interno ao eBay: com >=3 anúncios plausíveis, abaixo de 50% da mediana deles = lixo provável.
    # Só no lado ZH (conservador: sobe o preço chinês). No EN tiraria o mais barato de verdade e
    # INFLARIA a razão EN ÷ ZH.
    if drop_low_outliers and len(good) >= 3:
        tots = sorted(i.price + (i.shipping or 0) for i in good)
        med = tots[len(tots) // 2]
        good = [i for i in good if i.price + (i.shipping or 0) >= 0.5 * med]
    return (good[0] if good else None), None, len(items)


def select():
    """Candidatas (market desc) + nº de produtos-variante excluídos. tcgcsv, sem eBay."""
    groups = pt.get(f"{pt.BASE}/groups")["results"]
    sets = [g for g in groups if "2022" <= g["publishedOn"][:4] <= "2025" and not pt.EXCLUDE.search(g["name"])]
    zh = json.load(open(pt.ZH, encoding="utf-8"))
    by_en = {}
    for r in zh["rows"]:
        if r.get("en_set") and r.get("en_no"):
            by_en.setdefault((r["en_set"], pt.norm_no(r["en_no"])), []).append(r)
    cands, variants = [], 0
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
            if not ext.get("Rarity") or not usd or usd <= MIN_USD:
                continue
            num = str(ext.get("Number") or "").strip()
            zrows = by_en.get((g["name"], pt.norm_no(num)), [])
            if not zrows:
                continue
            if guards.variant_qualifier(prod["name"]):
                variants += 1
                continue
            z, multi = guards.pick_zh_row(list(zrows), ext.get("Rarity"))
            if z is None:
                continue
            cands.append((usd, g, prod, num, z, multi, guards.rarity_fit(ext.get("Rarity"), z)))
    cands.sort(key=lambda c: -c[0])
    return cands, variants


def _item(listing):
    if not listing:
        return None
    return {"item_id": listing.item_id, "price": listing.price, "shipping": listing.shipping,
            "url": listing.url.split("?")[0], "title": listing.title, "country": listing.country}


def collect(top_n, client):
    cands, variants = select()
    sel = cands[:top_n]
    rows, stop = [], None
    for usd, g, prod, num, z, multi, fit in sel:
        bn = pt.base_name(prod["name"])
        queries = {"en": f"{bn} {num.split('/')[0]}", "zh": f"{bn} {z['cn_code']} chinese"}
        ok = {"en": lambda t: guards.en_title_ok(t, bn, num),
              "zh": lambda t: guards.zh_title_ok(t, bn, z)}
        res = {}
        try:
            for lang in ("en", "zh"):
                listing, err, n = cheapest(client, queries[lang], ok[lang], drop_low_outliers=(lang == "zh"))
                res[lang] = {"query": queries[lang], "err": err, "n": n, "item": _item(listing)}
        except EbayBudgetExceeded as exc:
            stop = str(exc)
            break
        rows.append({"name": bn, "set": g["name"], "num": num, "how": z["how"], "multi": multi, "fit": fit,
                     "zh": f"{z['cn_code']}-{z['cn_no']}/{z.get('cn_total') or '?'}", "res": res})
    return {"collected": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "calls": client.calls,
            "selected": len(sel), "cands": len(cands), "variants_excluded": variants, "stop": stop, "rows": rows}


def _pairs(d):
    out = []
    for r in d["rows"]:
        en, zh = r["res"]["en"]["item"], r["res"]["zh"]["item"]
        if en and zh:
            ratio = guards.pair_ratio(en, zh)
            if ratio is not None:
                out.append((r, en, zh, ratio))
    return out


def verify(d, client, now=None):
    """getItem em cada link dos pares ≥ 4×: confirma "à venda" e renova o preço do item.
    Grava `verified` na linha: "a-venda" | "caiu: …" | "não verificado: …"."""
    for r, en, zh, ratio in _pairs(d):
        if ratio < guards.MIN_RATIO:
            continue
        verdict = "a-venda"
        for label, item in (("EN", en), ("ZH", zh)):
            try:
                payload, _ = client.get_item(item["item_id"])
            except EbayBudgetExceeded:
                verdict = "não verificado: teto de chamadas eBay"
                break
            except Exception as exc:  # só 404 prova que o anúncio saiu; o resto é "não sei"
                gone = isinstance(exc, EbayApiError) and "HTTP 404" in str(exc)
                verdict = (f"caiu: {label} anúncio não existe mais (HTTP 404)" if gone
                           else f"não verificado: {label} {type(exc).__name__}")
                break
            try:
                ok, why = guards.availability(payload, now)
                if not ok:
                    verdict = f"caiu: {label} {why}"
                    break
                price = payload.get("price") or {}
                if price.get("currency") == "USD" and price.get("value") is not None:
                    item["price"] = float(price["value"])
                # Frete descoberto agora entra só onde é conservador: no ZH (baixa a razão), ou no
                # EN que já tinha frete na busca. EN escolhido com frete desconhecido fica "frete ?".
                ship = _shipping(payload)
                if ship is not None and (label == "ZH" or item.get("shipping") is not None):
                    item["shipping"] = ship
            except Exception as exc:
                verdict = f"não verificado: {label} {type(exc).__name__}"
                break
        if verdict == "a-venda" and (guards.pair_ratio(en, zh) or 0) < guards.MIN_RATIO:
            verdict = "caiu: razão abaixo do crivo com o preço atual"
        r["verified"] = verdict
    d["verified_at"] = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M UTC")
    d["calls"] = getattr(client, "calls", d.get("calls"))


def _cell(it):
    ship = "frete ?" if it["shipping"] is None else (f"+{it['shipping']:.2f} frete" if it["shipping"] else "frete grátis")
    t = pt.md(it["title"][:70] + ("…" if len(it["title"]) > 70 else ""))
    return f"[US$ {it['price']:,.2f}]({it['url']}) {ship} · {it.get('country') or '?'} — {t}"


def render(d):
    pairs = _pairs(d)
    hits = [p for p in pairs if p[3] >= guards.MIN_RATIO]
    checked = "verified_at" in d
    shown = [p for p in hits if p[0].get("verified") == "a-venda"] if checked else hits
    dropped = [p for p in hits if p[0].get("verified") != "a-venda"] if checked else []
    shown.sort(key=lambda p: -p[3])
    no_en = sum(1 for r in d["rows"] if not r["res"]["en"]["item"])
    no_zh = sum(1 for r in d["rows"] if r["res"]["en"]["item"] and not r["res"]["zh"]["item"])
    errs = sum(1 for r in d["rows"] for lang in ("en", "zh") if r["res"][lang].get("err"))
    print(f"Coleta eBay {d['collected']} · {d['calls']} chamadas Browse API · {len(d['rows'])} cartas consultadas "
          f"(top por market TCGPlayer entre {d['cands']} com par ZH-S; {d.get('variants_excluded', 0)} variantes EN "
          f"excluídas) · {len(pairs)} pares com dois anúncios · sem anúncio EN {no_en} · sem anúncio ZH-S {no_zh} · "
          + (f"{errs} busca(s) com erro de fonte · " if errs else "")
          + f"{len(hits)} pares ≥ {guards.MIN_RATIO:g}× · "
          + (f"{len(dropped)} descartado(s) na verificação · à venda conferido em {d['verified_at']}" if checked
             else "links NÃO verificados (à venda não conferido)")
          + (f" · PARCIAL: {d['stop']}" if d.get("stop") else "")
          + "\n\nTítulo sozinho não prova idioma: todo par abaixo pede conferir a FOTO do anúncio ZH-S.\n")
    print("| # | Carta (set · nº EN) | Impressão ZH-S | Anúncio ZH-S (oferta) | Anúncio EN (referência) | "
          "Dif. US$ (EN − ZH, c/ frete) | EN ÷ ZH | Flags |")
    print("|---|---|---|---|---|---|---|---|")
    for i, (r, en, zh, ratio) in enumerate(shown, 1):
        sname = re.sub(r"^(SV\d*|SWSH\d*|ME\d*|SV|SWSH|ME):\s*", "", r["set"])
        flags = []
        if r["how"] != "tc-jp":
            flags.append("🟡 junção fraca")
        if r["multi"]:
            flags.append("⚠️ +1 impressão ZH")
        if r.get("fit") is False:
            flags.append("⚠️ raridade ZH difere da EN")
        if en.get("shipping") is None or zh.get("shipping") is None:
            flags.append("frete desconhecido")
        print(f"| {i} | {pt.md(r['name'])} ({pt.md(sname)} · #{r['num']}) | {r['zh']} | {_cell(zh)} | {_cell(en)} | "
              f"{guards.total(en) - guards.total(zh):+,.2f} | {ratio:.1f}× | {'; '.join(flags) or '—'} |")
    if dropped:
        print("\nDescartados na verificação (não entram na tabela):")
        for r, _en, _zh, _ratio in dropped:
            print(f"- {r['name']} (#{r['num']}) — {r.get('verified') or 'não verificado'}")


def main(argv):
    top_n = int(argv[0]) if argv else 120
    if "--render" in argv:
        render(json.load(open(OUT, encoding="utf-8")))
        return
    client = EbayClient()
    client.max_calls = 500
    d = collect(top_n, client)
    OUT.parent.mkdir(exist_ok=True)
    json.dump(d, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)  # coleta salva antes de verificar
    verify(d, client)
    json.dump(d, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    render(d)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
