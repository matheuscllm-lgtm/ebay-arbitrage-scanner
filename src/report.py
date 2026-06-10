"""Saida do scanner.

Regra canonica de entrega: TABELA MARKDOWN NO CHAT, todas as linhas (nao
amostra curada), com flag por linha. Arquivo (CSV local) e so registro;
planilha so se o operador pedir explicitamente.
"""
import csv
import os


def _trend_arrow(delta):
    if delta > 0:
        return f"+${delta:,.2f}"
    if delta < 0:
        return f"-${abs(delta):,.2f}"
    return "estavel"


def to_markdown(opportunities):
    """Tabela markdown com TODOS os resultados, ordenada por score."""
    if not opportunities:
        return "_Nenhum anuncio passou do threshold neste scan._"
    rows = sorted(opportunities, key=lambda o: -o.score)
    header = (
        "| Carta | Grade | Preco | Frete | Preco justo | Margem | Liq/mes | Tier "
        "| Tendencia | Spread PSA9 | Spread PSA10 | Score | Veredito | Flags | Link |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    lines = []
    for o in rows:
        c, l = o.card, o.listing
        spread9 = f"+{o.spread_psa9_pct:.0f}%" if o.spread_psa9_pct else "-"
        spread10 = f"+{o.spread_psa10_pct:.0f}%" if o.spread_psa10_pct else "-"
        flags = "; ".join(o.risk_flags) if o.risk_flags else "-"
        lines.append(
            f"| {c.name} #{c.number} ({c.set_name}, {c.language}) | {o.grade} "
            f"| ${l.price:,.2f} | ${l.shipping:,.2f} | ${o.fair_value:,.2f} "
            f"| {o.gross_margin_pct:.0f}% | {o.liquidity_per_month:g} | {o.liquidity_tier} "
            f"| {_trend_arrow(o.trend_delta)} | {spread9} | {spread10} "
            f"| {o.score:.0f} | {o.verdict} | {flags} | [eBay]({l.url}) |"
        )
    return header + "\n".join(lines)


def to_csv(opportunities, path):
    """Registro local em CSV (nao e a entrega; entrega = tabela no chat)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fields = [
        "card", "number", "set", "language", "grade", "price_usd", "shipping_usd",
        "fair_value_usd", "gross_margin_pct", "sales_per_month", "liquidity_tier",
        "trend_delta_usd", "spread_psa9_pct", "spread_psa10_pct", "score",
        "verdict", "flags", "seller_feedback_pct", "seller_feedback_score",
        "buying_option", "title", "url", "fair_value_source",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        for o in sorted(opportunities, key=lambda x: -x.score):
            c, l = o.card, o.listing
            writer.writerow([
                c.name, c.number, c.set_name, c.language, o.grade, l.price,
                l.shipping, o.fair_value, o.gross_margin_pct,
                o.liquidity_per_month, o.liquidity_tier, o.trend_delta,
                o.spread_psa9_pct, o.spread_psa10_pct, o.score, o.verdict,
                "; ".join(o.risk_flags), l.seller_feedback_pct,
                l.seller_feedback_score, l.buying_option, l.title, l.url,
                getattr(o, "fair_value_source", ""),
            ])
    return path


def fair_value_markdown(card, fair):
    """Tabela de preco justo por grade (modo --pricing-only)."""
    lines = [
        f"**{card.name} #{card.number} ({card.set_name}, {card.language})** "
        f"— [PriceCharting]({fair.source_url})",
        "",
        "| Grade | Preco justo | Tendencia | Vendas/mes | Liquidez |",
        "|---|---|---|---|---|",
    ]
    for grade in ["RAW", "GRADE 7", "GRADE 8", "PSA 9", "GRADE 9.5",
                  "PSA 10", "BGS 10", "CGC 10"]:
        price = fair.prices.get(grade)
        if price is None:
            continue
        delta = fair.deltas.get(grade)
        sales = fair.sales_per_month.get(grade)
        tier = "-"
        if sales is not None:
            from .scorer import liquidity_tier
            tier = liquidity_tier(sales)
        lines.append(
            f"| {grade} | ${price:,.2f} "
            f"| {_trend_arrow(delta) if delta is not None else '-'} "
            f"| {sales if sales is not None else '-'} | {tier} |"
        )
    return "\n".join(lines)
