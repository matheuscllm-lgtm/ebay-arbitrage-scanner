"""EBAY PSA -- scanner de cartas certificadas (slabs) -- CLI.

Uso:
  python main.py --group 3 --max-pages 1 --out results/last_scan_g3.json   # um grupo por vez
  python main.py --check-config               # regras e pendências da política, sem rede
  python main.py --list-groups                # lista os grupos da watchlist e sai
  python main.py --pricing-only               # so colunas informativas do PriceCharting (sem chaves)
  python main.py --grades "PSA 10"           # único grade do modo longterm
  python main.py --thesis-file private/theses.yaml --max-cards 25
  python main.py --watchlist w.yaml           # watchlist alternativa

Depois do scan, a ENTREGA canonica sai de:
  python ebay_summary.py results/last_scan_g3.json -o results/ebay-<data>.md
  (JSON da política -> `src/slab_report.render`; `--sensitivity` so vale para JSON legado)

Convencao de threshold deste repo: percentuais INTEIROS (20 = 20%).
Política vigente = bloco `slab_strategy` do config.yaml (docs/EBAY_PSA.md):
`economics.gate_mode: longterm`: tese, entrada e evidência independentes.
Piso fixo de 20% de margem bruta (revenda - item)/item, estritamente acima,
mais proteção de entrada após custos. Sem tese documentada: REVISAR.
`--min-gross-margin` só altera o piso em gross_margin legado; longterm mantém 20%.
`--min-discount` só tem efeito nos modos legados. Apenas cartas já certificadas.
"""
import argparse
import io
import os
import sys

import yaml

from src import report, scanner
from src.selection import select_batch, validate_batch_options

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


def apply_cli_overrides(config, *, min_gross_margin=None, log=print):
    """Sobrescritas de CLI que dependem do MODO do gate.

    `--min-gross-margin` so significa alguma coisa com `gate_mode: gross_margin`. Nos
    modos legados ela era aplicada assim mesmo e nao mudava nada, em silencio -- o
    mesmo tipo de mentira que o repo ja trata alto para `--confiavel` (revisao em
    contexto limpo, 2026-09-09). Aqui o config fica INTACTO e o aviso e impresso.
    """
    if min_gross_margin is None:
        return config
    economics = (config.get('slab_strategy') or {}).get('economics')
    if economics is None:
        return config
    if economics.get('gate_mode') == 'longterm':
        if min_gross_margin != 20:
            raise ValueError('longterm mantém margem mínima de 20%; alteração não aplicada')
        return config
    if economics.get('gate_mode') != 'gross_margin':
        log(f"AVISO: --min-gross-margin sem efeito com gate_mode "
            f"{economics.get('gate_mode')!r}: o limiar de margem bruta so decide no modo "
            f"gross_margin. Config inalterado.")
        return config
    economics['min_gross_margin_percent'] = int(min_gross_margin)
    return config


def main(argv=None):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    ap = argparse.ArgumentParser(description="eBay Pokemon TCG arbitrage scanner")
    ap.add_argument("--watchlist", default="watchlist.yaml")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument('--thesis-file', default=None,
                    help='YAML privado de teses documentadas; sem arquivo, tese não confirmada')
    ap.add_argument('--check-config', action='store_true', help='verifica regras e lista pendências sem consultar fontes')
    ap.add_argument("--pricing-only", action="store_true",
                    help="so colunas informativas do PriceCharting por carta (nao sao referencia "
                         "nem evidencia de venda); nao consulta eBay")
    ap.add_argument("--confiavel", action="store_true",
                    help="compatibilidade: o histórico do vendedor é sempre verificado; todos os candidatos permanecem visíveis")
    ap.add_argument("--include-raw", action="store_true",
                    help="opcao legada: rejeitada; o projeto aceita apenas cartas certificadas")
    ap.add_argument("--grades", default="",
                    help='longterm admite só PSA 10; modos legados aceitam outras notas '
                         'da allowlist, separadas por vírgula')
    ap.add_argument("--min-gross-margin", type=int, default=None, metavar="N",
                    help="Margem bruta%% minima (INTEIRO) deste run; sobrescreve "
                         "min_gross_margin_percent no modo legado; longterm mantém 20%%")
    ap.add_argument("--min-discount", type=int, default=None, metavar="N",
                    help="Desconto%% minimo (INTEIRO) deste run; sobrescreve "
                         "min_discount_percent do config (so tem efeito nos modos legados)")
    ap.add_argument("--min-price", type=float, default=None, metavar="USD",
                    help="piso de preco (US$) deste run; sobrescreve min_price_usd")
    ap.add_argument("--max-pages", type=int, default=None, metavar="N",
                    help="paginas de 200 anuncios por busca na Browse API (default 3)")
    ap.add_argument("--max-cards", type=int, default=None, metavar="N",
                    help="limite operacional de cartas neste lote; não é quota de elegibilidade "
                         "(padrão: todo o escopo)")
    ap.add_argument("--card-offset", type=int, default=None, metavar="N",
                    help="posição inicial no catálogo após filtro de grupo (zero-based); "
                         "não reutilizar após mudar catálogo/ordem/grupo")
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
        if args.max_cards is not None:
            config['max_cards'] = args.max_cards
        if args.card_offset is not None:
            config['card_offset'] = args.card_offset
        validate_batch_options(config.get('max_cards'), config.get('card_offset', 0))
        if args.thesis_file:
            from src.investment import load_profiles
            try:
                config['thesis_profiles'] = load_profiles(args.thesis_file)
            except OSError:
                raise ValueError('Arquivo privado de teses indisponível; nenhuma fonte consultada') from None
    except (ValueError, yaml.YAMLError) as exc:
        ap.error(str(exc))
    if args.check_config:
        from src.policy_validation import pending_config
        pending = pending_config(config)
        print(f'Política {config["slab_strategy"]["version"]}: estrutura válida.')
        for item in pending:
            print(f'REVISAR: {item}')
        if config['slab_strategy']['economics'].get('gate_mode') == 'longterm':
            print('Crivo: tese + entrada + evidência; margem mínima 20% (limite estrito).')
            if not config.get('thesis_profiles'):
                print('Teses documentadas não carregadas: candidatos ficarão em REVISAR; LP não substitui tese.')
            else:
                # Guard against a thesis that matches no card: the scan would silently
                # leave that card in REVISAR (thesis unconfirmed). Counts only — no
                # private identity is printed.
                from src.investment import watchlist_coverage
                try:
                    cards = scanner.load_watchlist(args.watchlist)
                except OSError:
                    print('Watchlist indisponível: cobertura das teses não conferida.')
                else:
                    cov = watchlist_coverage(config['thesis_profiles'], cards)
                    print(f"Teses: {cov['profiles']} carregadas · {cov['matched']} com carta na watchlist · "
                          f"{cov['unmatched']} sem carta correspondente "
                          "(identidade exata: nome, set, número, idioma).")
                    if cov['unmatched']:
                        print(f"REVISAR: {cov['unmatched']} tese(s) sem carta correspondente na watchlist "
                              "informada; no scan essas cartas ficariam em REVISAR (tese não confirmada). "
                              "Nenhuma identidade é impressa.")
        return 2 if pending else 0
    if args.confiavel:
        config["trusted_mode"] = True
        if "slab_strategy" in config:
            # A politica nunca le `trusted_mode` (review do PR #33): dizer alto, em vez
            # de aceitar a flag em silencio. O historico do vendedor e verificado sempre.
            print("AVISO: --confiavel sem efeito na política vigente (o histórico do vendedor "
                  "já é verificado em toda linha); a flag fica registrada no meta do JSON.")
    if args.include_raw:
        ap.error("EBAY PSA aceita apenas cartas certificadas; --include-raw foi removido da estrategia")
    try:
        apply_cli_overrides(config, min_gross_margin=args.min_gross_margin)
    except ValueError as exc:
        ap.error(str(exc))
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
        validate_config(config)  # includes the --grades scope, before any network call
    except ValueError as exc:
        ap.error(str(exc))

    try:
        cards_in_scope = scanner.filter_group(
            scanner.load_watchlist(args.watchlist), args.group)
        _, batch = select_batch(cards_in_scope, config.get('max_cards'),
                                config.get('card_offset', 0))
    except ValueError as e:  # grupo fora de 1-12 / spec invalida: erro ALTO, nunca traceback
        sys.exit(f"ERRO: {e}")

    fair_values, opportunities, effective_pricing_only, stats, aborted = scanner.run_scan(
        watchlist_path=args.watchlist, config=config,
        pricing_only=args.pricing_only, group=args.group,
    )
    scope_limited = bool(batch['scope_limited'])
    if scope_limited:
        print(f"LOTE LIMITADO: {batch['cards_scheduled']} de {batch['cards_in_scope']} "
              f"cartas programadas; {batch['cards_deferred']} fora deste lote. "
              "Não representa coleta do catálogo inteiro nem quantidade de cartas elegíveis.")

    # O artefato JSON (meta + funil + rows) e montado ANTES de imprimir: o console
    # da politica usa o MESMO meta da entrega canonica (review do PR #33 -- sem
    # meta o relatorio saia com "Coleta: n/d" e um funil zerado inventado).
    payload = None
    if not effective_pricing_only:
        payload = report.scan_payload(
            opportunities, watchlist_count=len(cards_in_scope), config=config,
            group=args.group, funnel=stats,
            aborted=aborted,
        )

    print()
    if args.pricing_only or not opportunities:
        print("## Colunas informativas do PriceCharting por carta (nao sao referencia)\n")
        for card, fair in fair_values.values():
            print(report.fair_value_markdown(card, fair))
            print()
    if opportunities:
        print("## Candidatos avaliados — classificação técnica, não recomendação\n")
        print(report.to_markdown(opportunities, meta=payload["meta"] if payload else None))
        csv_path = args.csv
        if aborted:
            base, ext = os.path.splitext(csv_path)
            csv_path = f"{base}.aborted{ext or '.csv'}"
        elif scope_limited:
            base, ext = os.path.splitext(csv_path)
            csv_path = f"{base}.batch{ext or '.csv'}"
        path = report.to_csv(opportunities, csv_path)
        print(f"\nRegistro local: {path} ({len(opportunities)} linhas)")
    # Rotulos do funil no vocabulario do motor ativo (politica: APROVAR/REJEITAR).
    funnel = (report.policy_funnel_lines(stats, mode=config['slab_strategy']['economics'].get('gate_mode')) if "slab_strategy" in config
              else report.funnel_lines(stats))
    print("Funil: " + " · ".join(funnel))

    if effective_pricing_only and not args.pricing_only:
        # Scan degradou (EBAY_CLIENT_ID/SECRET ausentes): gravar um artefato
        # com 0 rows aqui sobrescreveria o ultimo scan REAL no path default e
        # a entrega sairia "verde mas vazia". Nao gravar e avisar alto.
        print("AVISO: busca real indisponivel (chaves eBay ausentes; pricing-only nao executado) "
              f"-- artefato JSON NAO gravado ({args.out} preservado). "
              "Configure EBAY_CLIENT_ID/SECRET e rode de novo.")
    if payload is not None:
        out = args.out
        if aborted:
            # Scan parcial NUNCA sobrescreve o ultimo scan completo no path
            # default (mesma protecao do run degradado): vai para um arquivo
            # irmao, marcado aborted=true.
            base, ext = os.path.splitext(args.out)
            out = f"{base}.aborted{ext or '.json'}"
        elif scope_limited:
            base, ext = os.path.splitext(args.out)
            out = f"{base}.batch{ext or '.json'}"
        out_path = report.write_json(payload, out)
        print(f"Artefato JSON: {out_path} ({len(payload['rows'])} rows) -- "
              f"entrega: python ebay_summary.py {out_path} -o results/ebay-<data>.md")
    if aborted and not effective_pricing_only:
        # Mensagem por CAUSA (review #32): parada antecipada x erros contados.
        if stats.get("stopped_early"):
            print("RUN ABORTADO antes do fim -- as cartas restantes NAO foram varridas "
                  f"(artefato parcial gravado a parte, marcado aborted=true; {args.out} "
                  "preservado).")
        else:
            print("RUN ABORTADO (cobertura parcial) -- todas as cartas foram visitadas, "
                  "mas houve erros contados no funil (carta, anuncio ou fonte); "
                  f"artefato parcial gravado a parte, marcado aborted=true; {args.out} "
                  "preservado.")
    if aborted:
        return EXIT_ABORTED
    return 0


if __name__ == "__main__":
    sys.exit(main())
