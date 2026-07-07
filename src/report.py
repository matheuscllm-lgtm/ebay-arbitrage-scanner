"""Saida do scanner.

Regra canonica de entrega: TABELA MARKDOWN NO CHAT, todas as linhas (nao
amostra curada), com flag por linha, gerada pela FERRAMENTA do repo
(`ebay_summary.py` sobre o JSON do scan). Arquivo (CSV/JSON local) e so
registro; planilha so se o operador pedir explicitamente.

Este modulo e a FONTE UNICA da formatacao canonica compartilhada (coluna
`Carta`, coluna `Links`, seta de tendencia, escape de `|`): tanto o modo
console rapido (`to_markdown`) quanto a entrega canonica (`ebay_summary.py`)
usam os helpers daqui -- nunca duplicar o formato.
"""
import csv
import json
import os
from datetime import datetime, timezone


def escape_md(text):
    """Escapa `|` para celulas de tabela markdown (e normaliza quebras)."""
    return str(text or "").replace("|", "\\|").replace("\n", " ").strip()


def carta_label(name, number=""):
    """Coluna `Carta` = nome + numero ('Charizard 4/102'), sem duplicar o
    numero quando ja esta embutido no nome."""
    name = (name or "").strip()
    number = str(number or "").strip()
    if number and number.lower() not in name.lower().split():
        return f"{name} {number}".strip()
    return name


def links_cell(offer_url, ref_url, ref_label="referência", keep_placeholders=True):
    """Coluna canonica `Links`: '[oferta](url) · [<ref_label>](url)'.

    URLs vem SEMPRE da fonte (listing/JSON do scan) -- nunca inventadas.
    - keep_placeholders=True: lado ausente vira '—' (modo console legado).
    - keep_placeholders=False: lado ausente e omitido; a celula mostra so o
      link que existe ('—' apenas se nenhum existir).
    """
    offer = f"[oferta]({offer_url})" if offer_url else ("—" if keep_placeholders else "")
    ref = f"[{ref_label}]({ref_url})" if ref_url else ("—" if keep_placeholders else "")
    parts = [p for p in (offer, ref) if p]
    return " · ".join(parts) if parts else "—"


def _trend_arrow(delta):
    if delta > 0:
        return f"+${delta:,.2f}"
    if delta < 0:
        return f"-${abs(delta):,.2f}"
    return "estavel"


def trend_arrow(delta):
    """Formato canonico da tendencia (+$x.xx / -$x.xx / estavel)."""
    return _trend_arrow(delta)


def reference_link(o):
    """(url, label) do link de REFERENCIA da linha -- a fonte usada na margem.

    ref_kind=tcgplayer -> URL do produto TCGplayer (tcg_url, vinda do tcgcsv);
    senao -> URL do PriceCharting (fair_value_source). Nunca inventa URL nem
    troca de fonte no link: se a margem veio do TCGplayer mas o tcgcsv nao
    trouxe URL, o lado da referencia fica VAZIO (a celula omite/traceja) --
    mostrar o link do PriceCharting rotulado de 'referência' seria apontar
    pra fonte que NAO foi usada na margem (fix do review do PR #18)."""
    if o.ref_kind == "tcgplayer":
        return o.tcg_url, "TCG"
    return o.fair_value_source, "referência"


def to_markdown(opportunities):
    """Tabela markdown com TODOS os resultados, ordenada por score."""
    if not opportunities:
        return "_Nenhum anuncio passou do threshold neste scan._"
    rows = sorted(opportunities, key=lambda o: -o.score)
    header = (
        "| Carta | Grade | Preco | Frete | Preco justo | Mediana eBay | Margem "
        "| Liq/mes | Tier | Tendencia | Score "
        "| Conf | Protecao | Veredito | Flags | Links |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    lines = []
    for o in rows:
        c, lst = o.card, o.listing
        flags = "; ".join(o.risk_flags) if o.risk_flags else "-"
        median = f"${o.median_ask:,.2f}" if o.median_ask else "-"
        # Link de referencia da linha = a fonte USADA na margem: TCGplayer
        # (raw c/ tcgcsv) ou PriceCharting (graded / raw fallback).
        ref_url, ref_label = reference_link(o)
        links = links_cell(lst.url, ref_url, ref_label=ref_label)
        badges = "+".join(
            b for b, on in (("AG", lst.authenticity_guarantee), ("TR", lst.top_rated))
            if on) or "-"
        lines.append(
            f"| {c.name} #{c.number} ({c.set_name}, {c.language}) | {o.grade} "
            f"| ${lst.price:,.2f} | ${lst.shipping:,.2f} | ${o.fair_value:,.2f} "
            f"| {median} | {o.gross_margin_pct:.0f}% "
            f"| {o.liquidity_per_month:g} | {o.liquidity_tier} "
            f"| {_trend_arrow(o.trend_delta)} "
            f"| {o.score:.0f} | {o.trust_score:.0f} | {badges} "
            f"| {o.verdict} | {flags} | {links} |"
        )
    return header + "\n".join(lines)


def to_csv(opportunities, path):
    """Registro local em CSV (nao e a entrega; entrega = tabela no chat)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fields = [
        "card", "number", "set", "language", "grade", "price_usd", "shipping_usd",
        "fair_value_usd", "median_ask_usd", "gross_margin_pct", "sales_per_month",
        "liquidity_tier", "trend_delta_usd", "spread_psa9_pct", "spread_psa10_pct",
        "score", "trust_score", "authenticity_guarantee", "top_rated", "verdict",
        "flags", "seller_feedback_pct", "seller_feedback_score",
        "buying_option", "title", "url", "fair_value_source",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        for o in sorted(opportunities, key=lambda x: -x.score):
            c, lst = o.card, o.listing
            writer.writerow([
                c.name, c.number, c.set_name, c.language, o.grade, lst.price,
                lst.shipping, o.fair_value, o.median_ask, o.gross_margin_pct,
                o.liquidity_per_month, o.liquidity_tier, o.trend_delta,
                o.spread_psa9_pct, o.spread_psa10_pct, o.score, o.trust_score,
                lst.authenticity_guarantee, lst.top_rated, o.verdict,
                "; ".join(o.risk_flags), lst.seller_feedback_pct,
                lst.seller_feedback_score, lst.buying_option, lst.title, lst.url,
                o.fair_value_source,
            ])
    return path


def opportunity_row(o):
    """Serializa uma Opportunity para o artefato JSON do scan (uma row).

    Tudo vem do objeto avaliado -- nenhum preco/URL fabricado; campo sem
    fonte fica None/vazio (o consumidor rotula, nunca preenche)."""
    c, lst = o.card, o.listing
    ref_url, _ = reference_link(o)
    protections = [b for b, on in (("AG", lst.authenticity_guarantee),
                                   ("TR", lst.top_rated)) if on]
    return {
        "card": c.name,
        "set": c.set_name,
        "number": c.number,
        "language": c.language,
        "group": c.group,
        "grade": o.grade,
        "price": lst.price,
        "shipping": lst.shipping,
        "fair_value": o.fair_value,
        "ref_kind": o.ref_kind,
        "ref_url": ref_url,
        "tcg_market": o.tcg_market,
        "tcg_url": o.tcg_url,
        "margin_pct": o.gross_margin_pct,
        "ebay_median": o.median_ask,
        "liquidity_per_month": o.liquidity_per_month,
        "tier": o.liquidity_tier,
        "trend": o.trend_delta,
        "score": o.score,
        "trust_score": o.trust_score,
        "seller_feedback": lst.seller_feedback_score,
        "seller_feedback_pct": lst.seller_feedback_pct,
        "protections": protections,
        "verdict": o.verdict,
        "flags": list(o.risk_flags),
        "url": lst.url,
        "item_id": lst.item_id,
        "title": lst.title,
    }


def scan_payload(opportunities, watchlist_count, config, include_raw=False,
                 group=None):
    """Monta o artefato JSON do scan: meta + TODAS as rows avaliadas
    (inclusive REJEITADO) -- e o insumo canonico do `ebay_summary.py`."""
    meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "watchlist_count": watchlist_count,
        "group": group or "",
        "include_raw": bool(include_raw),
        "trusted_mode": bool(config.get("trusted_mode", False)),
        "config": {
            "min_gross_margin_percent": config.get("min_gross_margin_percent", 30),
            "min_price_usd": config.get("min_price_usd", 10.0),
            "suspicious_margin_percent": config.get("suspicious_margin_percent", 60),
            "graded_only": config.get("graded_only", True),
            "required_location_country": config.get("required_location_country", "US"),
        },
    }
    rows = [opportunity_row(o)
            for o in sorted(opportunities, key=lambda x: -x.score)]
    return {"meta": meta, "rows": rows}


def write_json(payload, path):
    """Grava o artefato JSON do scan (registro local, gitignored)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
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
