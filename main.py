"""eBay Pokemon TCG Arbitrage Scanner -- CLI.

Uso:
  python main.py                      # scan completo (precisa das chaves eBay)
  python main.py --pricing-only       # so preco justo da watchlist (sem chaves)
  python main.py --watchlist w.yaml   # watchlist alternativa
  python main.py --group chase-en     # so as cartas do grupo `chase-en`
  python main.py --list-groups        # lista os grupos da watchlist e sai
  python main.py --include-raw        # inclui o funil raw NM neste run
  python main.py --csv out.csv        # tambem grava CSV local
  python main.py --out results/last_scan.json   # artefato JSON (default)

Depois do scan, a ENTREGA canonica sai de:
  python ebay_summary.py results/last_scan.json -o results/ebay-<data>.md

Convencao de threshold deste repo: min_gross_margin_percent e percentual
INTEIRO (30 = 30%). Sem fracao, sem pegadinha.
"""
import argparse
import io
import sys

import yaml

from src import report, scanner


def _print_groups(cards):
    counts = scanner.group_counts(cards)
    print(f"Grupos da watchlist ({len(cards)} cartas):")
    for name, n in counts.items():
        print(f"  {name}: {n} carta(s)")


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    ap = argparse.ArgumentParser(description="eBay Pokemon TCG arbitrage scanner")
    ap.add_argument("--watchlist", default="watchlist.yaml")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--pricing-only", action="store_true",
                    help="so busca preco justo (PriceCharting); nao consulta eBay")
    ap.add_argument("--confiavel", action="store_true",
                    help="modo confiavel: so vendedores com historico (>=50 "
                         "avaliacoes, >=98%%) e margem na faixa saudavel "
                         "(30-60%%); tabela 100%% acionavel")
    ap.add_argument("--include-raw", action="store_true",
                    help="inclui o funil raw NM NESTE run (referencia raw = "
                         "TCGplayer market via tcgcsv; PriceCharting vira "
                         "cross-check). Nao altera o default graded-only do "
                         "config -- e uma reversao sancionada por-run")
    ap.add_argument("--group", default="",
                    help="escaneia so as cartas do grupo indicado "
                         "(campo `group:` da watchlist); vazio = todas")
    ap.add_argument("--list-groups", action="store_true",
                    help="lista os grupos da watchlist (com contagem) e sai; "
                         "nao precisa das chaves eBay")
    ap.add_argument("--csv", default="data/last_scan.csv",
                    help="caminho do CSV de registro local")
    ap.add_argument("--out", default="results/last_scan.json",
                    help="artefato JSON do scan (insumo do ebay_summary.py)")
    args = ap.parse_args()

    if args.list_groups:
        _print_groups(scanner.load_watchlist(args.watchlist))
        return

    try:
        with open(args.config, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        config = {}
    if args.confiavel:
        config["trusted_mode"] = True
    if args.include_raw:
        # Habilita raw NM SO neste run (o default `graded_only: true` do
        # config e decisao de escopo do operador e continua intacto).
        config["graded_only"] = False

    cards_in_scope = scanner.filter_group(
        scanner.load_watchlist(args.watchlist), args.group)

    fair_values, opportunities = scanner.run_scan(
        watchlist_path=args.watchlist, config=config,
        pricing_only=args.pricing_only, group=args.group,
    )

    print()
    if args.pricing_only or not opportunities:
        print("## Preco justo por carta (PriceCharting)\n")
        for card, fair in fair_values.values():
            print(report.fair_value_markdown(card, fair))
            print()
    if opportunities:
        print("## Oportunidades (todas as linhas, ordenadas por score)\n")
        print(report.to_markdown(opportunities))
        path = report.to_csv(opportunities, args.csv)
        print(f"\nRegistro local: {path} ({len(opportunities)} linhas)")

    if not args.pricing_only:
        payload = report.scan_payload(
            opportunities, watchlist_count=len(cards_in_scope), config=config,
            include_raw=args.include_raw, group=args.group,
        )
        out_path = report.write_json(payload, args.out)
        print(f"Artefato JSON: {out_path} ({len(payload['rows'])} rows) -- "
              f"entrega: python ebay_summary.py {out_path} -o results/ebay-<data>.md")


if __name__ == "__main__":
    main()
