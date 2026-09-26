"""CLI do modo CHINÊS: PSA 10 em chinês no eBay × PSA 10 em inglês (crivo ≥4×),
com evidência chinesa e régua de longo prazo. Ver `src/chinese_scan.py`.

Uso:
    python chinese_scan.py --group 1 --out results/chinese-g1.json
    python chinese_scan.py --group 11 --max-cards 100 --card-offset 0 --out results/chinese-g11a.json
    python ebay_summary.py results/chinese-g1.json -o results/chinese-g1.md   # entrega (VERBATIM no chat)

Orçamento: 1 chamada eBay por carta (`--max-ebay-calls`, 500 por execução) +
páginas do PriceCharting (EN da carta quando há linha; chinesas só para linhas
que precisam, até `--max-zh-pages-per-card`). Resultados ficam em `results/`
(gitignored) — nunca publicar preço no GitHub.
"""
from __future__ import annotations

import argparse
import io
import os
import sys

from src import chinese_scan, report
from src.chinese_report import render

EXIT_ABORTED = 1


def main(argv=None):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="PSA 10 em chinês × PSA 10 em inglês (eBay + PriceCharting)")
    ap.add_argument("--watchlist", default="watchlist.yaml")
    ap.add_argument("--group", default="", help="grupo(s) da watchlist: '1', '1,2', '11-12'; vazio = todos")
    ap.add_argument("--max-cards", type=int, default=None)
    ap.add_argument("--card-offset", type=int, default=0)
    ap.add_argument("--min-ratio", type=float, default=chinese_scan.DEFAULT_PARAMS["min_ratio"],
                    help="EN PSA 10 ÷ preço do slab chinês (default 4)")
    ap.add_argument("--min-price", type=float, default=chinese_scan.DEFAULT_PARAMS["min_price_usd"])
    ap.add_argument("--min-zh-sales", type=int, default=chinese_scan.DEFAULT_PARAMS["min_zh_sales"])
    ap.add_argument("--max-zh-pages-per-card", type=int, default=chinese_scan.DEFAULT_PARAMS["max_zh_pages_per_card"])
    ap.add_argument("--max-ebay-calls", type=int, default=chinese_scan.DEFAULT_PARAMS["max_ebay_calls"])
    ap.add_argument("--location-country", default="", help="filtro server-side de país do item; vazio = qualquer")
    ap.add_argument("--out", default="results/chinese_scan.json")
    ap.add_argument("--report", default=None, help=".md da entrega (default: <out>.md)")
    args = ap.parse_args(argv)
    if args.min_ratio <= 1:
        ap.error("--min-ratio tem que ser > 1")
    params = {"min_ratio": args.min_ratio, "min_price_usd": args.min_price, "min_zh_sales": args.min_zh_sales,
              "max_zh_pages_per_card": args.max_zh_pages_per_card, "max_ebay_calls": args.max_ebay_calls,
              "location_country": args.location_country}
    payload = chinese_scan.run_scan(args.watchlist, group=args.group or None, max_cards=args.max_cards,
                                    offset=args.card_offset, params=params)
    out = args.out
    if payload["meta"].get("aborted"):
        base, ext = os.path.splitext(out)
        out = f"{base}.aborted{ext or '.json'}"
    report.write_json(payload, out)
    md = render(payload)
    md_path = args.report or (os.path.splitext(out)[0] + ".md")
    os.makedirs(os.path.dirname(md_path) or ".", exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    print(f"\n[JSON: {out} · markdown: {md_path}]", file=sys.stderr)
    return EXIT_ABORTED if payload["meta"].get("aborted") else 0


if __name__ == "__main__":
    sys.exit(main())
