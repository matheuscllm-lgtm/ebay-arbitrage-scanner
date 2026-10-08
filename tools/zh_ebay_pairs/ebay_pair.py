"""Par EN × ZH-S dentro do eBay (menor anúncio ativo, raw, preço fixo), crivo EN ÷ ZH ≥ 4×.

Seleção: cartas EN de sets 2017-2025 (o catálogo ZH-S começa na era Sun & Moon) com market
TCGPlayer > US$10 e par ZH-S no catálogo (zh_identity.json); as TOP_N de maior market entram,
a partir de --offset (TCGPlayer só ORDENA a seleção — todo preço comparado é eBay). Cada idioma = 1 busca Browse API (EBAY_US, vendedor de qualquer
país). Guards em guards.py. Na entrega, cada link dos pares ≥ 4× é reconferido por getItem
(à venda agora); o que caiu é declarado, não mostrado. Nunca inventa: sem anúncio → sem par.

    python ebay_pair.py 200                      # coleta + verificação + tabela (cartas 1-200)
    python ebay_pair.py 200 --offset 200         # fatia seguinte (201-400): teto de 500 chamadas por execução
    python ebay_pair.py 200 --years 2022-2025    # só uma faixa de anos
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
YEARS = (2017, 2025)   # anos de lançamento do set EN; 2017 = 1º ano com par no catálogo ZH-S
NM_ASPECT = "Card Condition:{Near Mint or Better},Graded:{No}"
KEEP = 10              # anúncios plausíveis guardados por idioma (do mais barato ao mais caro)
MAX_WALK = 6           # quantos deles o verify() confere por getItem até achar um NM à venda
BELOW = "abaixo do crivo com os anúncios NM à venda"


def parse_years(text):
    lo, hi = text.split("-")
    return int(lo), int(hi)


def in_years(group, years):
    return years[0] <= int(group["publishedOn"][:4]) <= years[1]


def _shipping(payload):
    """Frete USD da 1ª opção com valor no getItem; None = continua desconhecido."""
    for opt in payload.get("shippingOptions") or []:
        cost = opt.get("shippingCost") or {}
        if cost.get("value") is not None:
            return float(cost["value"]) if cost.get("currency") == "USD" else None
    return None


def plausible(client, query, ok):
    """(até KEEP anúncios plausíveis do mais barato ao mais caro, mediana dos plausíveis, erro, nº bruto)."""
    try:
        # ordem por RELEVÂNCIA (sort=price traz os 200 mais baratos da busca frouxa e perde a carta)
        # NM × NM já na busca: o vendedor declarou "Near Mint or Better" e carta não graded
        # (provado ao vivo 2026-10-04; sem isso o EN mais barato de carta antiga é cópia jogada).
        params = {"q": query, "category_ids": CCG_CATEGORY_ID, "limit": "200",
                  "filter": "price:[1..],priceCurrency:USD,buyingOptions:{FIXED_PRICE}",
                  "aspect_filter": f"categoryId:{CCG_CATEGORY_ID},{NM_ASPECT}"}
        items = parse_search_payload(client._request_search_json(SEARCH_URL + "?" + urllib.parse.urlencode(params)))
    except EbayBudgetExceeded:
        raise
    except Exception as exc:  # erro de fonte: n/d honesto
        return [], None, f"erro: {type(exc).__name__}", 0
    good = [i for i in items if i.price and ok(i.title)]
    good.sort(key=lambda i: i.price + (i.shipping or 0))
    median = None
    if good:
        tots = [i.price + (i.shipping or 0) for i in good]
        median = tots[len(tots) // 2]
        # guard interno ao eBay: com >=3 plausíveis, abaixo de 50% da mediana deles = lixo provável
        # (visto ao vivo: alt art de ~US$800 anunciada a US$10 e a US$80 como "NM"). Vale nos dois
        # idiomas; a condição de verdade (NM) é conferida depois, por getItem, em verify().
        if len(good) >= 3:
            good = [i for i in good if i.price + (i.shipping or 0) >= 0.5 * median]
    return [_item(i) for i in good[:KEEP]], median, None, len(items)


def select(years=YEARS):
    """Candidatas (market desc) + nº de produtos-variante excluídos. tcgcsv, sem eBay."""
    groups = pt.get(f"{pt.BASE}/groups")["results"]
    sets = [g for g in groups if in_years(g, years) and not pt.EXCLUDE.search(g["name"])]
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


def collect(top_n, client, offset=0, years=YEARS):
    cands, variants = select(years)
    sel = cands[offset:offset + top_n]
    rows, stop = [], None
    for usd, g, prod, num, z, multi, fit in sel:
        bn = pt.base_name(prod["name"])
        queries = {"en": f"{bn} {num.split('/')[0]}", "zh": f"{bn} {z['cn_code']} chinese"}
        ok = {"en": lambda t: guards.en_title_ok(t, bn, num),
              "zh": lambda t: guards.zh_title_ok(t, bn, z)}
        res = {}
        try:
            for lang in ("en", "zh"):
                items, median, err, n = plausible(client, queries[lang], ok[lang])
                res[lang] = {"query": queries[lang], "err": err, "n": n, "items": items, "median": median,
                             "item": items[0] if items else None}
        except EbayBudgetExceeded as exc:
            stop = str(exc)
            break
        rows.append({"name": bn, "set": g["name"], "num": num, "how": z["how"], "multi": multi, "fit": fit,
                     "zh": f"{z['cn_code']}-{z['cn_no']}/{z.get('cn_total') or '?'}", "res": res})
    return {"collected": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "calls": client.calls,
            "selected": len(sel), "cands": len(cands), "variants_excluded": variants, "stop": stop, "rows": rows,
            "offset": offset, "years": list(years)}


def _pairs(d):
    out = []
    for r in d["rows"]:
        en, zh = r["res"]["en"]["item"], r["res"]["zh"]["item"]
        if en and zh:
            ratio = guards.pair_ratio(en, zh)
            if ratio is not None:
                out.append((r, en, zh, ratio))
    return out


class _Unverified(Exception):
    pass


def _walk(client, label, items, now):
    """Do mais barato ao mais caro (até MAX_WALK): 1º anúncio à venda cuja condição não é
    "jogada"/graded. → (item | None, motivo do último descarte)."""
    why = "sem anúncio plausível"
    for item in items[:MAX_WALK]:
        try:
            payload, _ = client.get_item(item["item_id"])
        except EbayBudgetExceeded:
            raise
        except Exception as exc:  # só 404 prova que o anúncio saiu; o resto é "não sei"
            if isinstance(exc, EbayApiError) and "HTTP 404" in str(exc):
                why = "anúncio não existe mais (HTTP 404)"
                continue
            raise _Unverified(f"{label} {type(exc).__name__}") from exc
        try:
            ok, reason = guards.availability(payload, now)
            if not ok:
                why = reason
                continue
            cond = guards.card_condition(payload)
            if cond == "OUTRA":
                why = "condição abaixo de NM"
                continue
            price = payload.get("price") or {}
            if price.get("currency") == "USD" and price.get("value") is not None:
                item["price"] = float(price["value"])
            # Frete descoberto agora entra só onde é conservador: no ZH (baixa a razão), ou no
            # EN que já tinha frete na busca. EN escolhido com frete desconhecido fica "frete ?".
            ship = _shipping(payload)
            if ship is not None and (label == "ZH" or item.get("shipping") is not None):
                item["shipping"] = ship
            item["cond"] = cond
            return item, ""
        except Exception as exc:
            raise _Unverified(f"{label} {type(exc).__name__}") from exc
    return None, why


def _candidate(en_items, zh_items, en_median):
    """Vale gastar getItem? O EN NM pode custar mais que o EN mais barato (que pode ser carta
    jogada), então o teto usado é a MEDIANA dos EN plausíveis contra o ZH mais barato."""
    zh_min = guards.total(zh_items[0])
    en_hi = max([en_median or 0] + [guards.total(i) for i in en_items[:MAX_WALK]])
    return zh_min > 0 and en_hi / zh_min >= guards.MIN_RATIO


def verify(d, client, now=None):
    """Para cada par que pode chegar a 4×: getItem do mais barato ao mais caro até achar, em cada
    idioma, o 1º anúncio À VENDA e NM (ou sem condição informada — vira flag). Renova preço.
    Grava `verified`: "a-venda" | BELOW | "caiu: …" | "não verificado: …"."""
    for r in d["rows"]:
        lists = {}
        for lang in ("en", "zh"):
            res = r["res"][lang]
            lists[lang] = res.get("items") or ([res["item"]] if res.get("item") else [])
        if not lists["en"] or not lists["zh"]:
            continue
        if not _candidate(lists["en"], lists["zh"], r["res"]["en"].get("median")):
            continue
        verdict = "a-venda"
        try:
            for lang, label in (("en", "EN"), ("zh", "ZH")):
                item, why = _walk(client, label, lists[lang], now)
                if item is None:
                    verdict = f"caiu: {label} sem anúncio NM à venda ({why})"
                    break
                r["res"][lang]["item"] = item
        except EbayBudgetExceeded:
            verdict = "não verificado: teto de chamadas eBay"
        except _Unverified as exc:
            verdict = f"não verificado: {exc}"
        if verdict == "a-venda" and (guards.pair_ratio(r["res"]["en"]["item"], r["res"]["zh"]["item"]) or 0) \
                < guards.MIN_RATIO:
            verdict = BELOW
        r["verified"] = verdict
    d["verified_at"] = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M UTC")
    d["calls"] = getattr(client, "calls", d.get("calls"))


def _cell(it):
    ship = "frete ?" if it["shipping"] is None else (f"+{it['shipping']:.2f} frete" if it["shipping"] else "frete grátis")
    t = pt.md(it["title"][:70] + ("…" if len(it["title"]) > 70 else ""))
    return f"[US$ {it['price']:,.2f}]({it['url']}) {ship} · {it.get('country') or '?'} — {t}"


def render(d):
    pairs = _pairs(d)
    checked = "verified_at" in d
    if checked:
        shown = [p for p in pairs if p[0].get("verified") == "a-venda"]
        below = sum(1 for r in d["rows"] if r.get("verified") == BELOW)
        dropped = [r for r in d["rows"] if r.get("verified") not in (None, "a-venda", BELOW)]
    else:
        shown, below, dropped = [p for p in pairs if p[3] >= guards.MIN_RATIO], 0, []
    shown.sort(key=lambda p: -p[3])
    no_en = sum(1 for r in d["rows"] if not r["res"]["en"]["item"])
    no_zh = sum(1 for r in d["rows"] if r["res"]["en"]["item"] and not r["res"]["zh"]["item"])
    errs = sum(1 for r in d["rows"] for lang in ("en", "zh") if r["res"][lang].get("err"))
    print(f"Coleta eBay {d['collected']} · {d['calls']} chamadas Browse API · {len(d['rows'])} cartas consultadas "
          f"(posições {d.get('offset', 0) + 1}-{d.get('offset', 0) + len(d['rows'])} por market TCGPlayer entre "
          f"{d['cands']} com par ZH-S, sets {'-'.join(str(y) for y in d.get('years', YEARS))}; {d.get('variants_excluded', 0)} variantes EN "
          f"excluídas) · {len(pairs)} pares com dois anúncios · sem anúncio EN {no_en} · sem anúncio ZH-S {no_zh} · "
          + (f"{errs} busca(s) com erro de fonte · " if errs else "")
          + f"{len(shown)} pares ≥ {guards.MIN_RATIO:g}× · "
          + (f"{below} abaixo do crivo após conferir condição/preço · {len(dropped)} descartado(s) na verificação · "
             f"à venda e condição conferidos em {d['verified_at']}" if checked
             else "links NÃO verificados (à venda e condição não conferidos)")
          + (f" · PARCIAL: {d['stop']}" if d.get("stop") else "")
          + "\n\nComparação NM × NM: em cada idioma, o anúncio mais barato que está à venda e não é carta "
            "jogada/graded.\nTítulo sozinho não prova idioma: todo par abaixo pede conferir a FOTO do anúncio ZH-S.\n")
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
        if checked and (en.get("cond") is None or zh.get("cond") is None):
            flags.append("condição não informada")
        print(f"| {i} | {pt.md(r['name'])} ({pt.md(sname)} · #{r['num']}) | {r['zh']} | {_cell(zh)} | {_cell(en)} | "
              f"{guards.total(en) - guards.total(zh):+,.2f} | {ratio:.1f}× | {'; '.join(flags) or '—'} |")
    if dropped:
        print("\nDescartados na verificação (não entram na tabela):")
        for r in dropped:
            print(f"- {r['name']} (#{r['num']}) — {r.get('verified') or 'não verificado'}")


def main(argv):
    top_n = int(argv[0]) if argv and argv[0].isdigit() else 120
    if "--render" in argv:
        render(json.load(open(OUT, encoding="utf-8")))
        return
    offset = int(argv[argv.index("--offset") + 1]) if "--offset" in argv else 0
    years = parse_years(argv[argv.index("--years") + 1]) if "--years" in argv else YEARS
    client = EbayClient()
    client.max_calls = 500
    d = collect(top_n, client, offset, years)
    OUT.parent.mkdir(exist_ok=True)
    json.dump(d, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)  # coleta salva antes de verificar
    verify(d, client)
    json.dump(d, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    render(d)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
