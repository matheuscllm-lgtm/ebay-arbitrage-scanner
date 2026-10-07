"""Ranking chinês simplificado × inglês (carta solta, preço de mercado).

    python zh_gap.py --out results/zh-gap-2026-10-07.json
    python zh_gap.py --sets CSV10C,151C --no-ebay --out results/zh-gap-teste.json

Saídas (locais, nunca versionadas): <out>.json · <out>.md (todas as linhas acima do piso)
· <out>.chat.md (só razão ≥ --min-ratio, para colar no chat). Páginas do PriceCharting ficam
em --cache-dir/<dia> (padrão data/cache/pc/zh_gap): rodar de novo no mesmo dia não gasta crédito.
"""
from __future__ import annotations

import argparse
import collections
import datetime as _dt
import io
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import ebay_api, pc_sales, zh_gap, zh_identity  # noqa: E402

DEFAULT_CACHE_DIR = os.path.join("data", "cache", "pc", "zh_gap")


def main(argv=None) -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="Chinês simplificado × inglês — carta solta, preço de mercado")
    ap.add_argument("--catalog", default=zh_identity.CATALOG_PATH)
    ap.add_argument("--sets", default="", help="códigos 52poke (CSV10C,151C,...); vazio = todos com ≥ --min-pairs pares")
    ap.add_argument("--min-pairs", type=int, default=zh_gap.DEFAULT_PARAMS["min_pairs_per_set"])
    ap.add_argument("--min-en", type=float, default=zh_gap.DEFAULT_PARAMS["min_en_usd"], help="piso: EN market >= US$")
    ap.add_argument("--min-zh", type=float, default=zh_gap.DEFAULT_PARAMS["min_zh_usd"],
                    help="piso: raw chinês (PriceCharting) >= US$ (operador 07/10: sinal de chase)")
    ap.add_argument("--min-ratio", type=float, default=zh_gap.DEFAULT_PARAMS["min_ratio"], help="corte da versão para o chat")
    ap.add_argument("--max-pages-per-set", type=int, default=zh_gap.DEFAULT_PARAMS["max_pages_per_set"])
    ap.add_argument("--no-ebay", action="store_true", help="não buscar ofertas no eBay")
    ap.add_argument("--max-ebay-calls", type=int, default=zh_gap.DEFAULT_PARAMS["max_ebay_calls"])
    ap.add_argument("--ebay-limit", type=int, default=zh_gap.DEFAULT_PARAMS["ebay_limit"])
    ap.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR,
                    help="cache das páginas do PriceCharting (subpasta do dia; estável entre execuções)")
    ap.add_argument("--out", default="results/zh_gap.json")
    args = ap.parse_args(argv)

    t0 = time.time()
    catalog = zh_identity.Catalog.from_file(args.catalog)
    counts = collections.Counter(r["cn_code"] for r in catalog.rows
                                 if r.get("how") and r.get("en_set") and not r.get("en_set_unresolved"))
    if args.sets:
        codes = [c.strip() for c in args.sets.split(",") if c.strip()]
    else:
        codes = [c for c, n in counts.most_common() if n >= args.min_pairs]
    slugs: dict[str, list[str]] = {}
    for c in codes:
        s = zh_gap.console_slug(c)
        if s:
            slugs.setdefault(s, []).append(c)
    print(f"Catálogo: {len(catalog)} impressões · {len(codes)} códigos → {len(slugs)} consoles do PriceCharting")

    pc_rows: dict[str, list[dict]] = {}
    pages = 0
    partial_sets: list[str] = []
    for i, (slug, cs) in enumerate(slugs.items(), 1):
        try:
            rows, n, partial = zh_gap.fetch_console_rows(slug, cache_dir=args.cache_dir,
                                                         max_pages=args.max_pages_per_set)
        except pc_sales.PcError as exc:
            print(f"[{i}/{len(slugs)}] {slug} ({','.join(cs)}): FALHOU — {exc}")
            continue
        pages += n
        pc_rows[slug] = rows
        if partial:
            partial_sets.append(slug)
        priced = sum(1 for r in rows if r.get("ungraded"))
        print(f"[{i}/{len(slugs)}] {slug} ({','.join(cs)}): {len(rows)} cartas, {priced} com preço raw, {n} pág."
              + (" (parcial)" if partial else ""))

    memo: dict[tuple, object] = {}

    def en_lookup(pair):
        key = (pair["en_set"], str(pair["en_no"]), pair["en_name"])
        if key not in memo:
            memo[key] = zh_gap.en_reference(pair)
        return memo[key]

    rows, funnel = zh_gap.build_rows(catalog, pc_rows, en_lookup, {"min_en_usd": args.min_en, "min_zh_usd": args.min_zh})
    print("Funil: " + " · ".join(f"{k}: {v}" for k, v in funnel.items()))

    ebay_calls = 0
    if not args.no_ebay and rows:
        targets = [r for r in rows if r["ratio"] >= args.min_ratio]
        client = ebay_api.EbayClient()
        ebay_calls = zh_gap.attach_offers(targets, client.search, max_calls=args.max_ebay_calls,
                                          limit=args.ebay_limit)
        found = sum(1 for r in targets if r.get("offer"))
        print(f"eBay: {ebay_calls} chamadas · {found} ofertas raw chinesas em {len(targets)} linhas (razão ≥ {args.min_ratio:g}×)")

    meta = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "params": {"min_en_usd": args.min_en, "min_zh_usd": args.min_zh, "min_ratio": args.min_ratio,
                   "min_pairs_per_set": args.min_pairs},
        "codes": codes, "sets": len(pc_rows), "pages": pages, "partial_sets": partial_sets,
        "ebay_calls": ebay_calls, "funnel": funnel, "elapsed_s": round(time.time() - t0, 1),
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    base = args.out[:-5] if args.out.endswith(".json") else args.out
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(zh_gap.to_json(rows, meta))
    with open(base + ".md", "w", encoding="utf-8") as fh:
        fh.write(zh_gap.render_markdown(rows, meta))
    with open(base + ".chat.md", "w", encoding="utf-8") as fh:
        fh.write(zh_gap.render_markdown(rows, meta, min_ratio=args.min_ratio))
    print(f"OK: {len(rows)} linhas acima do piso · {sum(1 for r in rows if r['ratio'] >= args.min_ratio)} com razão ≥ "
          f"{args.min_ratio:g}× · {meta['elapsed_s']} s → {args.out} / {base}.md / {base}.chat.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
