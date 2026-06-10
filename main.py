"""eBay Pokemon TCG Arbitrage Scanner -- CLI.

Uso:
  python main.py                      # scan completo (precisa das chaves eBay)
  python main.py --pricing-only       # so preco justo da watchlist (sem chaves)
  python main.py --watchlist w.yaml   # watchlist alternativa
  python main.py --csv out.csv        # tambem grava CSV local

Convencao de threshold deste repo: min_gross_margin_percent e percentual
INTEIRO (30 = 30%). Sem fracao, sem pegadinha.
"""
import argparse
import io
import sys

import yaml

from src import report, scanner


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    ap = argparse.ArgumentParser(description="eBay Pokemon TCG arbitrage scanner")
    ap.add_argument("--watchlist", default="watchlist.yaml")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--pricing-only", action="store_true",
                    help="so busca preco justo (PriceCharting); nao consulta eBay")
    ap.add_argument("--confiavel", action="store_true",
                    help="modo confiavel: so vendedores com historico (>=100 "
                         "avaliacoes, >=99%%) e margem na faixa saudavel "
                         "(30-60%%); tabela 100%% acionavel")
    ap.add_argument("--csv", default="data/last_scan.csv",
                    help="caminho do CSV de registro local")
    args = ap.parse_args()

    try:
        with open(args.config, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        config = {}
    if args.confiavel:
        config["trusted_mode"] = True

    fair_values, opportunities = scanner.run_scan(
        watchlist_path=args.watchlist, config=config,
        pricing_only=args.pricing_only,
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


if __name__ == "__main__":
    main()
