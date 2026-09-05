"""eBay Pokemon TCG Arbitrage Scanner -- CLI (padrao COMC, metricas ajustaveis).

Uso:
  python main.py                              # scan completo (precisa das chaves eBay)
  python main.py --group 3 --min-price 5 --min-discount 10   # diagnostico (grupo 3)
  python main.py --pricing-only               # so referencias da watchlist (sem chaves)
  python main.py --watchlist w.yaml           # watchlist alternativa
  python main.py --list-groups                # lista os grupos da watchlist e sai
  python main.py --check-config               # regras e pendências, sem rede
  python main.py --grades "PSA 10, CGC 10 Pristine"   # funil restrito a notas
  python main.py --out results/last_scan.json # artefato JSON (default)

Depois do scan, a ENTREGA canonica sai de:
  python ebay_summary.py results/last_scan.json -o results/ebay-<data>.md \
      [--sensitivity 10,15,20]

Convencao de threshold deste repo: percentuais INTEIROS (20 = 20%).
`--min-discount` altera o braço de desconto da regra lucro OU desconto.
Lucro estimado, margem e ROI líquidos consideram custos COMC explícitos.
"""
import argparse
import io
import os
import sys

import yaml

from src import report, scanner

EXIT_ABORTED = 1


def _print_groups(cards):
    counts = scanner.group_counts(cards)
    print(f"Grupos da watchlist ({len(cards)} cartas):")
    for name, n in counts.items():
        title = ""
        if name.isdigit() and int(name) in scanner.groups.SCAN_GROUPS:
            title = f" — {scanner.groups.SCAN_GROUPS[int(name)].title}"
        print(f"  {name}{title}: {n} carta(s)")
    print("Use --group N | N-M | 1,3,10-12 | all (grupos canonicos) ou o nome literal.")


def _load_config(path):
    try:
        with open(path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError as exc:
        raise ValueError(f'Configuração não encontrada: {path}') from exc
    if "min_discount_percent" not in config and "min_gross_margin_percent" in config:
        # Config antigo (gate por ROI bruto): o gate agora e Desconto% (padrao
        # COMC). Nao converter em silencio -- avisar alto e usar o default.
        print("AVISO: config.yaml usa `min_gross_margin_percent` (ROI bruto), que "
              "deixou de ser o gate; use `min_discount_percent` (Desconto%). "
              f"Usando o default {scanner.scorer.DEFAULT_CONFIG['min_discount_percent']}%.")
    # O gate efetivo vai SEMPRE explicito no config (e no artefato JSON), nunca
    # implicito no default do scorer -- a entrega mostra o valor real usado.
    config.setdefault("min_discount_percent", scanner.scorer.DEFAULT_CONFIG["min_discount_percent"])
    from src.slab_strategy import policy_config
    return policy_config(config)


def main(argv=None):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    ap = argparse.ArgumentParser(description="eBay Pokemon TCG arbitrage scanner")
    ap.add_argument("--watchlist", default="watchlist.yaml")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument('--check-config', action='store_true', help='verifica regras e lista pendências sem consultar fontes')
    ap.add_argument("--pricing-only", action="store_true",
                    help="so referencias da watchlist (PriceCharting); nao consulta eBay")
    ap.add_argument("--confiavel", action="store_true",
                    help="compatibilidade: o histórico do vendedor é sempre verificado; todos os candidatos permanecem visíveis")
    ap.add_argument("--include-raw", action="store_true",
                    help="opcao legada: rejeitada; o projeto aceita apenas cartas certificadas")
    ap.add_argument("--grades", default="",
                    help='restringe o funil DESTE run a notas especificas, separadas '
                         'por virgula (ex.: --grades "PSA 10, CGC 10 Pristine, BGS 10 '
                         'Black"). RAW so tem efeito com --include-raw. Nota fora da '
                         'allowlist erra ALTO')
    ap.add_argument("--min-discount", type=int, default=None, metavar="N",
                    help="Desconto%% minimo (INTEIRO) deste run; sobrescreve "
                         "min_discount_percent do config (diagnostico: 10)")
    ap.add_argument("--min-price", type=float, default=None, metavar="USD",
                    help="piso de preco deste run; sobrescreve min_price_usd (diagnostico: 5)")
    ap.add_argument("--max-pages", type=int, default=None, metavar="N",
                    help="paginas de 200 anuncios por busca na Browse API (default 3)")
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
    args = ap.parse_args(argv)

    if args.list_groups:
        _print_groups(scanner.load_watchlist(args.watchlist))
        return 0

    try:
        config = _load_config(args.config)
    except (ValueError, yaml.YAMLError) as exc:
        ap.error(str(exc))
    if args.check_config:
        from src.policy_validation import pending_config
        pending = pending_config(config)
        print(f'Política {config["slab_strategy"]["version"]}: estrutura válida.')
        for item in pending:
            print(f'REVISAR: {item}')
        return 2 if pending else 0
    if args.confiavel:
        config["trusted_mode"] = True
    if args.include_raw:
        ap.error("EBAY PSA aceita apenas cartas certificadas; --include-raw foi removido da estrategia")
    if args.min_discount is not None:
        config["min_discount_percent"] = int(args.min_discount)
        if config['slab_strategy']['economics'].get('gate_mode') == 'profit_or_discount':
            config['slab_strategy']['economics']['min_discount_percent'] = int(args.min_discount)
    if args.min_price is not None:
        config["min_price_usd"] = float(args.min_price)
    if args.max_pages is not None:
        config["max_pages"] = int(args.max_pages)
    from src.policy_validation import validate_config
    try:
        validate_config(config)
    except ValueError as exc:
        ap.error(str(exc))
    if args.grades:
        try:
            config["allowed_grades"] = scanner.parse_grades_arg(
                args.grades, config.get("graded_allow"))
            if 'RAW' in config['allowed_grades']:
                ap.error('RAW não pertence à estratégia de cartas certificadas')
        except ValueError as e:
            sys.exit(f"ERRO: {e}")
    if not config.get("graded_allow"):
        config["graded_allow"] = sorted(scanner.grading.DEFAULT_GRADED_ALLOW)

    try:
        cards_in_scope = scanner.filter_group(
            scanner.load_watchlist(args.watchlist), args.group)
    except ValueError as e:  # grupo fora de 1-12 / spec invalida: erro ALTO, nunca traceback
        sys.exit(f"ERRO: {e}")

    fair_values, opportunities, effective_pricing_only, stats, aborted = scanner.run_scan(
        watchlist_path=args.watchlist, config=config,
        pricing_only=args.pricing_only, group=args.group,
    )

    print()
    if args.pricing_only or not opportunities:
        print("## Referencias por carta (PriceCharting -- colunas informativas)\n")
        for card, fair in fair_values.values():
            print(report.fair_value_markdown(card, fair))
            print()
    if opportunities:
        print("## Candidatos avaliados — APROVAR / REJEITAR / REVISAR\n")
        print(report.to_markdown(opportunities))
        path = report.to_csv(opportunities, args.csv)
        print(f"\nRegistro local: {path} ({len(opportunities)} linhas)")
    print("Funil: " + " · ".join(report.funnel_lines(stats)))

    if effective_pricing_only and not args.pricing_only:
        # Scan degradou (EBAY_CLIENT_ID/SECRET ausentes): gravar um artefato
        # com 0 rows aqui sobrescreveria o ultimo scan REAL no path default e
        # a entrega sairia "verde mas vazia". Nao gravar e avisar alto.
        print("AVISO: busca real indisponivel (chaves eBay ausentes; pricing-only nao executado) "
              f"-- artefato JSON NAO gravado ({args.out} preservado). "
              "Configure EBAY_CLIENT_ID/SECRET e rode de novo.")
    if not effective_pricing_only:
        payload = report.scan_payload(
            opportunities, watchlist_count=len(cards_in_scope), config=config,
            include_raw=args.include_raw, group=args.group, funnel=stats,
            aborted=aborted,
        )
        out = args.out
        if aborted:
            # Scan parcial NUNCA sobrescreve o ultimo scan completo no path
            # default (mesma protecao do run degradado): vai para um arquivo
            # irmao, marcado aborted=true.
            base, ext = os.path.splitext(args.out)
            out = f"{base}.aborted{ext or '.json'}"
        out_path = report.write_json(payload, out)
        print(f"Artefato JSON: {out_path} ({len(payload['rows'])} rows) -- "
              f"entrega: python ebay_summary.py {out_path} -o results/ebay-<data>.md")
    if aborted and not effective_pricing_only:
        print("RUN ABORTADO antes do fim -- as cartas restantes NAO foram varridas "
              f"(artefato parcial gravado a parte, marcado aborted=true; {args.out} "
              "preservado).")
    if aborted:
        return EXIT_ABORTED
    return 0


if __name__ == "__main__":
    sys.exit(main())
