"""Ferramenta CANONICA de entrega do scan eBay (espelho do myp_summary.py).

Le o artefato JSON gravado pelo `main.py --out` e gera a tabela markdown de
entrega -- grava em `-o` (obrigatorio) e imprime no stdout. O agente cola o
`.md` VERBATIM no chat: nunca remontar tabela a mao, nunca dropar link.

Contrato da frota (nao negociavel):
- TODAS as linhas de TODOS os buckets (OPORTUNIDADE / REVISAR / SUSPEITO /
  REJEITADO com motivo) -- nunca amostra.
- Toda linha tem os DOIS links: `[oferta]` (anuncio eBay, onde comprar) e
  `[TCG]`/`[ref]` (referencia de preco, onde validar). URLs lidas do JSON,
  NUNCA inventadas; sem URL -> a celula mostra so o link que existe.
- Vereditos sao classificacao tecnica; nenhuma recomendacao de compra.

Uso:
    python ebay_summary.py results/last_scan.json -o results/ebay-2026-07-06.md
"""
import argparse
import io
import json
import os
import sys

from src.report import carta_label, escape_md, links_cell, trend_arrow

VERDICTS = ("OPORTUNIDADE", "REVISAR", "SUSPEITO", "REJEITADO")

SECTION_TITLES = {
    "OPORTUNIDADE": "## 🟢 OPORTUNIDADE",
    "REVISAR": "## ⚠️ REVISAR (validar manualmente)",
    "SUSPEITO": "## 🚨 SUSPEITO (margem alta demais — validar)",
    "REJEITADO": "## ⛔ REJEITADO",
}

MAIN_HEADER = ("| # | Margem % | Preço US$ | Ref US$ | Dif US$ | Carta | Grade "
               "| Liq/mês | Tend | Score | Conf | Links |")
MAIN_SEP = "|---|---|---|---|---|---|---|---|---|---|---|---|"
FLAGGED_HEADER = MAIN_HEADER + " Flags |"
FLAGGED_SEP = MAIN_SEP + "---|"
REJECTED_HEADER = "| # | Carta | Grade | Preço US$ | Motivo | Links |"
REJECTED_SEP = "|---|---|---|---|---|---|"


def _usd(value):
    if value is None:
        return "—"
    return f"${float(value):,.2f}"


def _row_links(row):
    """Links da linha, com a REFERENCIA usada na margem: `[TCG]` quando
    ref_kind=tcgplayer, `[ref]` quando pricecharting. URLs so do JSON."""
    if row.get("ref_kind") == "tcgplayer":
        return links_cell(row.get("url"), row.get("tcg_url"),
                          ref_label="TCG", keep_placeholders=False)
    return links_cell(row.get("url"), row.get("ref_url"),
                      ref_label="ref", keep_placeholders=False)


def _carta(row):
    return escape_md(carta_label(row.get("card"), row.get("number")))


def _main_cells(i, row):
    price = float(row.get("price") or 0.0)
    fair = row.get("fair_value")
    dif = (float(fair) - price) if fair is not None else None
    return [
        str(i),
        f"{float(row.get('margin_pct') or 0.0):.0f}%",
        _usd(price),
        _usd(fair),
        _usd(dif),
        _carta(row),
        escape_md(row.get("grade")),
        f"{float(row.get('liquidity_per_month') or 0.0):g}",
        trend_arrow(float(row.get("trend") or 0.0)),
        f"{float(row.get('score') or 0.0):.0f}",
        f"{float(row.get('trust_score') or 0.0):.0f}",
        _row_links(row),
    ]


def _flags_cell(row):
    flags = row.get("flags") or []
    return escape_md("; ".join(flags)) if flags else "-"


def coverage_line(rows):
    """Cobertura de referencia: honestidade sobre a fonte de cada linha."""
    graded = sum(1 for r in rows if r.get("grade") != "RAW")
    raw_tcg = sum(1 for r in rows
                  if r.get("grade") == "RAW" and r.get("ref_kind") == "tcgplayer")
    raw_pc = sum(1 for r in rows
                 if r.get("grade") == "RAW" and r.get("ref_kind") != "tcgplayer")
    return (f"Cobertura de referência: {graded} graded (PriceCharting) · "
            f"{raw_tcg} raw c/ TCGplayer real · {raw_pc} raw só PriceCharting")


def build_markdown(payload):
    """JSON do scan -> markdown de entrega (todas as linhas, 4 buckets)."""
    meta = payload.get("meta") or {}
    rows = payload.get("rows") or []
    by_verdict = {v: [] for v in VERDICTS}
    for row in rows:
        verdict = row.get("verdict")
        if verdict not in by_verdict:
            verdict = "REVISAR"  # nunca dropar linha: veredito estranho -> revisar
        by_verdict[verdict].append(row)
    for bucket in by_verdict.values():
        bucket.sort(key=lambda r: -float(r.get("score") or 0.0))

    date = (meta.get("timestamp") or "")[:10] or "?"
    scope = f" · grupo `{meta['group']}`" if meta.get("group") else ""
    modes = []
    if meta.get("include_raw"):
        modes.append("raw NM incluído (--include-raw)")
    if meta.get("trusted_mode"):
        modes.append("modo confiável (--confiavel)")
    counts = " · ".join(f"{len(by_verdict[v])} {v}" for v in VERDICTS)

    lines = [
        f"# Scan eBay — {date}",
        "",
        f"- Watchlist: {meta.get('watchlist_count', '?')} carta(s){scope}"
        + (f" · {' · '.join(modes)}" if modes else ""),
        f"- Vereditos: {counts}",
        f"- {coverage_line(rows)}",
        "- Vereditos são classificação técnica — decisão de capital é do operador.",
        "",
    ]

    for verdict in VERDICTS:
        bucket = by_verdict[verdict]
        lines.append(SECTION_TITLES[verdict])
        lines.append("")
        if not bucket:
            lines.append("_Nenhuma linha neste bucket._")
            lines.append("")
            continue
        if verdict == "REJEITADO":
            lines.append(REJECTED_HEADER)
            lines.append(REJECTED_SEP)
            for i, row in enumerate(bucket, 1):
                cells = [str(i), _carta(row), escape_md(row.get("grade")),
                         _usd(row.get("price")), _flags_cell(row),
                         _row_links(row)]
                lines.append("| " + " | ".join(cells) + " |")
        else:
            flagged = verdict in ("REVISAR", "SUSPEITO")
            lines.append(FLAGGED_HEADER if flagged else MAIN_HEADER)
            lines.append(FLAGGED_SEP if flagged else MAIN_SEP)
            for i, row in enumerate(bucket, 1):
                cells = _main_cells(i, row)
                if flagged:
                    cells.append(_flags_cell(row))
                lines.append("| " + " | ".join(cells) + " |")
        lines.append("")

    return "\n".join(lines)


def main(argv=None):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    ap = argparse.ArgumentParser(
        description="Gera a entrega canonica (markdown) do scan eBay")
    ap.add_argument("scan_json", help="artefato JSON do scan (main.py --out)")
    ap.add_argument("-o", "--output", required=True,
                    help="arquivo .md de saida (obrigatorio)")
    args = ap.parse_args(argv)

    with open(args.scan_json, encoding="utf-8") as f:
        payload = json.load(f)

    md = build_markdown(payload)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    print(f"\n[gravado em {args.output}]", file=sys.stderr)


if __name__ == "__main__":
    main()
