"""Saida do scanner.

Regra canonica de entrega: TABELA MARKDOWN NO CHAT, todas as linhas (nao
amostra curada), com flag por linha, gerada pela FERRAMENTA do repo
(`ebay_summary.py` sobre o JSON do scan). Arquivo (CSV/JSON local) e so
registro; planilha so se o operador pedir explicitamente.

Este modulo e a FONTE UNICA da formatacao canonica compartilhada (coluna
`Carta`, coluna `Links`, tabela de linhas, escape de `|`): tanto o modo
console rapido (`to_markdown`) quanto a entrega canonica (`ebay_summary.py`)
usam os helpers daqui -- nunca duplicar o formato.

Padrao COMC (operador, 2026-09-03) -- tres metricas, nomeadas assim e so assim:
- Desconto%   = (ref - preco) / ref x 100   -> gate ajustavel (`--min-discount`)
- Spread$     = ref - preco                 -> diferenca bruta, sem taxa nenhuma
- ROI bruto%  = (ref - preco) / preco x 100 -> retorno bruto sobre o capital
Ranking: maior ROI bruto -> maior desconto -> maior spread -> Pokemon mais
popular (rank menor na lista dos 100 chases). Nunca "lucro".
"""
import csv
import json
import os
import tempfile
from datetime import datetime, timezone
from urllib.parse import quote

UNRANKED = 9999                 # Pokemon fora da lista dos 100 chases
MIN_COMPARABLE_SALES = 3        # mediana de vendas vale como referencia OK so com >=3
COLUMN_DEVIATION_MAX = 0.30     # coluna exata do PC >30% longe da mediana -> revisar
_URL_SAFE = "%/?&=:+,*"         # percent-encoding sem re-encodar %XX existente


# --- helpers de celula ---------------------------------------------------------

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


def md_url(url):
    """URL percent-encodada para `[label](url)`: espaco/aspas/parenteses crus
    quebram o link em varios renderizadores (`)` fecha o link no primeiro
    parentese); `%XX` existente NAO e re-encodado (operador 2026-08-04)."""
    return quote(str(url), safe=_URL_SAFE) if url else ""


def links_cell(offer_url, ref_url, ref_label="referência", keep_placeholders=True):
    """Coluna canonica `Links`: '[oferta](url) · [<ref_label>](url)'.

    URLs vem SEMPRE da fonte (listing/JSON do scan) -- nunca inventadas.
    - keep_placeholders=True: lado ausente vira '—' (modo console legado).
    - keep_placeholders=False: lado ausente e omitido; a celula mostra so o
      link que existe ('—' apenas se nenhum existir).
    """
    offer = f"[oferta]({md_url(offer_url)})" if offer_url else ("—" if keep_placeholders else "")
    ref = f"[{ref_label}]({md_url(ref_url)})" if ref_url else ("—" if keep_placeholders else "")
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
    """(url, label) do link de REFERENCIA da linha.

    Decisao do operador (COMC, 2026-09-02; eBay, 2026-09-03): o link
    `[referência]` e a pagina da carta no PriceCharting SEMPRE que ela existir
    (vendas eBay, grafico, PSA 10/9 -- mais informativa), tambem para raw cuja
    MARGEM veio do TCGplayer market; a coluna `Ref` diz qual fonte foi usada
    no preco. Sem pagina PC, cai no TCGplayer (`[TCG]`); nunca inventa URL."""
    pc = o.pc_url or o.fair_value_source
    if pc:
        return pc, "referência"
    if o.tcg_url:
        return o.tcg_url, "TCG"
    return "", "referência"


# --- metricas e ranking (padrao COMC) ------------------------------------------

def compute_metrics(reference, price):
    """(discount_pct, roi_pct, spread_usd) arredondados a 2 casas."""
    spread = float(reference) - float(price)
    discount = (spread / reference * 100.0) if reference and reference > 0 else float("-inf")
    roi = (spread / price * 100.0) if price and price > 0 else float("inf")
    return round(discount, 2), round(roi, 2), round(spread, 2)


def _f(row, key):
    try:
        return float(row.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def sort_key(row):
    """Chave para sorted(): menor = melhor (negativos nas metricas).
    JSON antigo (sem `roi_pct`) usa `margin_pct`, que e a mesma grandeza."""
    if row.get("strategy"):
        s = row["strategy"]
        return ({"APROVAR": 0, "REVISAR": 1, "REJEITAR": 2}.get(row.get("verdict"), 1),
                0 if row.get("grade", "").startswith("PSA ") else 1,
                -(s.get("net_roi_percent") or 0),
                0 if s.get("vault_confirmed") is True else 1)
    roi = _f(row, "roi_pct") if row.get("roi_pct") is not None else _f(row, "margin_pct")
    try:
        rank = int(row.get("pokemon_rank") or UNRANKED)
    except (TypeError, ValueError):
        rank = UNRANKED
    return (-roi, -_f(row, "discount_pct"), -_f(row, "spread_usd"), rank)


def sort_rows(rows):
    return sorted(rows, key=sort_key)


# --- funil ---------------------------------------------------------------------

# Rotulos do funil (ordem logica: coleta -> triagem -> referencia -> gate -> baldes).
FUNNEL_LABELS = [
    ("cards", "Cartas da watchlist no escopo"),
    ("ebay_calls", "Chamadas à Browse API (cota grátis 5.000/dia)"),
    ("seen", "Anúncios analisados (após dedupe)"),
    ("dedup_dropped", "Duplicados removidos (mesmo item/título+preço)"),
    ("skip_not_fixed_price", "Ignorados: leilão (só preço fixo)"),
    ("skip_price_floor", "Ignorados: abaixo do piso US$"),
    ("skip_country", "Ignorados: item fora dos EUA"),
    ("skip_no_match", "Ignorados: título não é a carta da watchlist"),
    ("skip_raw", "Ignorados: carta solta (graded-only; use --include-raw)"),
    ("skip_grade_filtered", "Ignorados: nota fora do funil pedido (--grades)"),
    ("skip_grade_out_of_scope", "Ignorados: certificadora/nota fora do escopo"),
    ("skip_grade_ambiguous", "Ignorados: título cita mais de uma nota (ambíguo)"),
    ("ref_unavailable", "Slabs/LP pulados por fonte PriceCharting indisponível na carta"),
    ("skip_condition", "Ignorados: raw sem NM explícito (e sem LP explícito)"),
    ("slab_no_reference", "Slabs sem vendas comparáveis (mesma certificadora+nota+variante) — sem referência"),
    ("lp_prefilter", "Raw LP acima do pré-filtro (preço > ref NM × (1 − desconto mín.))"),
    ("lp_no_nm_prefilter", "Raw LP avaliadas sem pré-filtro (sem referência NM para o teto)"),
    ("lp_no_reference", "Raw LP sem ≥3 vendas LP comparáveis — sem referência"),
    ("raw_no_reference", "Raw NM sem referência (sem TCG market nem Ungraded do PC)"),
    ("raw_variant_no_reference", "Raw reverse holo sem market do subtype Reverse Holofoil (o Ungraded do PriceCharting é da versão normal) — sem referência"),
    ("pc_error", "Cartas com ERRO na fonte PriceCharting (rede/bloqueio/layout)"),
    ("pc_breaker", "Cartas puladas com o PriceCharting suspenso (5 falhas seguidas)"),
    ("below_discount", "Descartados: desconto abaixo do mínimo"),
    ("rows_opportunity", "Linhas OPORTUNIDADE"),
    ("rows_review", "Linhas REVISAR"),
    ("rows_suspect", "Linhas SUSPEITO"),
    ("rows_rejected", "Linhas REJEITADO (com motivo)"),
    ("trusted_filtered", "Descartados pelo modo confiável (--confiavel)"),
    ("card_error", "Cartas com erro interno (puladas — ver log)"),
    ("ebay_error", "Cartas com erro na Browse API (puladas)"),
    ("aborted", "RUN ABORTADO (autenticação eBay / API indisponível) — cartas restantes não varridas"),
]
_KNOWN_FUNNEL_KEYS = {k for k, _ in FUNNEL_LABELS}


def funnel_lines(counts):
    """Linhas 'rotulo: N' do funil (so as com valor > 0, mais 'analisados');
    contadores sem rotulo conhecido aparecem como 'outros: k=v' (nunca somem)."""
    counts = counts or {}
    out = []
    for key, label in FUNNEL_LABELS:
        n = int(counts.get(key, 0) or 0)
        if n or key == "seen":
            out.append(f"{label}: {n}")
    extra = {k: v for k, v in counts.items() if k not in _KNOWN_FUNNEL_KEYS and v}
    if extra:
        out.append("outros: " + ", ".join(f"{k}={v}" for k, v in sorted(extra.items())))
    return out


# --- status / referencia / tabela canonica --------------------------------------

def row_notes(row):
    """Notas que NAO mudam o status: `baixa-liquidez(365d)` quando a mediana so
    juntou >=3 vendas na janela de 365 dias (`ref_liquidity == "low"`)."""
    notes = []
    if str(row.get("ref_liquidity") or "") == "low":
        notes.append("baixa-liquidez(365d)")
    return notes


def status_cell(row):
    """`<veredito> · <motivos> · <notas>` -- motivos curtos gravados pelo scan
    (`reasons`: vendas<3(n=1), coluna÷vendas(c), ref-desalinhada, ...)."""
    parts = [str(row.get("verdict") or "REVISAR")]
    parts.extend(str(r) for r in (row.get("reasons") or []) if r)
    parts.extend(row_notes(row))
    return " · ".join(parts)


def ref_label_cell(row):
    """Coluna `Ref`: fonte USADA no preco de referencia. "PC vendas PSA 10
    (n=5, 2026-03..2026-08)" (mediana de vendas), "TCG market" (TCGplayer) ou
    "PC Ungraded (sem TCG)" (fallback rotulado)."""
    label = str(row.get("ref_label") or "").strip()
    source = str(row.get("ref_source") or row.get("ref_kind") or "")
    if source.startswith("pricecharting-sales"):
        return f"PC {label}" if label else "PC vendas"
    if source == "tcgplayer":
        return label or "TCG market"
    if source == "pricecharting":
        return label or "PC Ungraded (sem TCG)"
    return label or "—"


def listing_type_cell(row):
    """Coluna `Tipo`: "Raw NM" / "Raw LP" / nota do slab ("CGC 10 Gem Mint")."""
    lt = str(row.get("listing_type") or "").strip()
    if lt:
        return lt
    grade = str(row.get("grade") or "")
    if grade == "RAW":
        cond = str(row.get("condition") or "NM")
        return f"Raw {cond}"
    return str(row.get("grade_label") or grade or "—")


def _row_links(row):
    """Links da linha: `[oferta]` (anuncio eBay) e `[referência]` (pagina do
    PriceCharting; `[TCG]` so quando nao ha pagina PC). URLs so do JSON."""
    pc = row.get("pc_url") or ""
    if pc:
        return links_cell(row.get("url"), pc, ref_label="referência", keep_placeholders=False)
    ref = row.get("ref_url") or ""
    label = "TCG" if (ref and "tcgplayer.com" in ref) else "referência"
    if not ref and row.get("tcg_url"):
        ref, label = row.get("tcg_url"), "TCG"
    return links_cell(row.get("url"), ref, ref_label=label, keep_placeholders=False)


def _num(value, digits=2):
    if value is None or value == "":
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return escape_md(value)
    if v in (float("inf"), float("-inf")):
        return "∞" if v > 0 else "-∞"
    return f"{v:.{digits}f}"


TABLE_COLS = [
    ("rank", "#"),
    ("discount_pct", "Desconto%"),
    ("roi_pct", "ROI bruto%"),
    ("price", "eBay$"),
    ("fair_value", "Ref$"),
    ("spread_usd", "Spread$"),
    ("pokemon", "Pokémon"),
    ("carta", "Carta"),
    ("set", "Set"),
    ("listing_type", "Tipo"),
    ("ref", "Ref"),
    ("trust_score", "Vend"),
    ("status", "Status"),
    ("links", "Links"),
    ("flags", "Flags"),
]
REJECTED_COLS = [
    ("rank", "#"),
    ("carta", "Carta"),
    ("listing_type", "Tipo"),
    ("price", "eBay$"),
    ("motivo", "Motivo"),
    ("links", "Links"),
]
_MAXW = {"carta": 40, "set": 30, "listing_type": 22, "pokemon": 16}


def _cell(key, value):
    if key == "links":
        return "" if value is None else str(value)
    s = "" if value is None else str(value)
    w = _MAXW.get(key)
    if w and len(s) > w:
        s = s[: w - 1] + "…"
    return escape_md(s) if key not in ("flags", "motivo") else s


def _cells_for(row, rank):
    roi = row.get("roi_pct") if row.get("roi_pct") is not None else row.get("margin_pct")
    flags = row.get("flags") or []
    flags_txt = escape_md("; ".join(str(f) for f in flags)) if flags else "-"
    return {
        "rank": str(rank),
        "discount_pct": _num(row.get("discount_pct")),
        "roi_pct": _num(roi),
        "price": _num(row.get("price")),
        "fair_value": _num(row.get("fair_value")),
        "spread_usd": _num(row.get("spread_usd")),
        "pokemon": row.get("pokemon") or "",
        "carta": carta_label(row.get("card"), row.get("number")),
        "set": row.get("set") or "",
        "listing_type": listing_type_cell(row),
        "ref": ref_label_cell(row),
        "trust_score": _num(row.get("trust_score"), 0),
        "status": status_cell(row),
        "links": _row_links(row),
        "flags": flags_txt,
        "motivo": flags_txt,
    }


def table_header_lines(cols=TABLE_COLS):
    header = "| " + " | ".join(label for _, label in cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    return [header, sep]


def render_row_line(row, rank, cols=TABLE_COLS):
    cells = _cells_for(row, rank)
    return "| " + " | ".join(_cell(k, cells.get(k, "")) for k, _ in cols) + " |"


def render_rows_table(rows, cols=TABLE_COLS):
    """Tabela canonica (uma linha por row, ja na ordem recebida)."""
    lines = table_header_lines(cols)
    lines.extend(render_row_line(row, rank, cols) for rank, row in enumerate(rows, 1))
    return "\n".join(lines)


def render_rejected_table(rows):
    """Tabela dos REJEITADO (com motivo) -- mesmos dois links por linha."""
    return render_rows_table(rows, REJECTED_COLS)


def to_markdown(opportunities):
    if any(o.strategy for o in opportunities):
        from .slab_report import render
        return render({"rows": sort_rows([opportunity_row(o) for o in opportunities])})

    """Modo console: TODAS as linhas na tabela canonica, ordem do ranking."""
    if not opportunities:
        return "_Nenhum anuncio passou do desconto minimo neste scan._"
    rows = sort_rows([opportunity_row(o) for o in opportunities])
    return render_rows_table(rows)


# --- registro local -------------------------------------------------------------

def sort_rows_opps(opportunities):
    """Opportunities na ordem do ranking (mesma chave das rows)."""
    return sorted(opportunities, key=lambda o: sort_key(opportunity_row(o)))


def to_csv(opportunities, path):
    if any(o.strategy for o in opportunities):
        import json
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        rows = [opportunity_row(o) for o in opportunities]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            for row in rows:
                writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k,v in row.items()})
        return path

    """Registro local em CSV (nao e a entrega; entrega = tabela no chat)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fields = [
        "card", "number", "set", "language", "pokemon", "grade", "listing_type",
        "price_usd", "shipping_usd", "fair_value_usd", "discount_pct", "roi_pct",
        "spread_usd", "ref_source", "ref_label", "ref_n_sales", "ref_liquidity",
        "median_ask_usd", "score", "trust_score", "authenticity_guarantee",
        "top_rated", "verdict", "reasons", "flags", "seller_feedback_pct",
        "seller_feedback_score", "buying_option", "title", "url", "pc_url",
        "tcg_url",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        for o in sort_rows_opps(opportunities):
            c, lst = o.card, o.listing
            writer.writerow([
                c.name, c.number, c.set_name, c.language, c.pokemon, o.grade,
                o.listing_type, lst.price, lst.shipping, o.fair_value,
                o.discount_pct, o.gross_margin_pct, o.spread_usd, o.ref_source,
                o.ref_label, o.ref_n_sales, o.ref_liquidity, o.median_ask,
                o.score, o.trust_score, lst.authenticity_guarantee, lst.top_rated,
                o.verdict, "; ".join(o.reasons), "; ".join(o.risk_flags),
                lst.seller_feedback_pct, lst.seller_feedback_score,
                lst.buying_option, lst.title, lst.url, o.pc_url, o.tcg_url,
            ])
    return path


# --- artefato JSON do scan ------------------------------------------------------

def opportunity_row(o):
    """Serializa uma Opportunity para o artefato JSON do scan (uma row).

    Tudo vem do objeto avaliado -- nenhum preco/URL fabricado; campo sem
    fonte fica None/vazio (o consumidor rotula, nunca preenche)."""
    c, lst = o.card, o.listing
    ref_url, _ = reference_link(o)
    protections = [b for b, on in (("AG", lst.authenticity_guarantee),
                                   ("TR", lst.top_rated)) if on]
    return {
        **({"strategy": o.strategy} if o.strategy else {}),
        "card": c.name,
        "set": c.set_name,
        "number": c.number,
        "language": c.language,
        "group": c.group,
        "pokemon": c.pokemon,
        "pokemon_rank": c.pokemon_rank,
        "grade": o.grade,
        "grade_label": o.grade_label,
        "condition": o.condition,
        "listing_type": o.listing_type or listing_type_cell(
            {"grade": o.grade, "condition": o.condition, "grade_label": o.grade_label}),
        "price": lst.price,
        "shipping": lst.shipping,
        "fair_value": o.fair_value,
        "discount_pct": o.discount_pct,
        "roi_pct": o.gross_margin_pct,
        "spread_usd": o.spread_usd,
        "margin_pct": o.gross_margin_pct,
        "ref_kind": o.ref_kind,
        "ref_source": o.ref_source or o.ref_kind,
        "ref_label": o.ref_label,
        "ref_n_sales": o.ref_n_sales,
        "ref_liquidity": o.ref_liquidity,
        "ref_window_days": o.ref_window_days,
        "ref_column_price": o.ref_column_price,
        "ref_url": ref_url,
        "pc_url": o.pc_url or o.fair_value_source,
        "tcg_market": o.tcg_market,
        "tcg_url": o.tcg_url,
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
        "reasons": list(o.reasons),
        "flags": list(o.risk_flags),
        "url": lst.url,
        "item_id": lst.item_id,
        "title": lst.title,
    }


def scan_payload(opportunities, watchlist_count, config, include_raw=False,
                 group=None, funnel=None, aborted=False):
    """Monta o artefato JSON do scan: meta (+ funil) + TODAS as rows avaliadas
    (inclusive REJEITADO), na ordem do ranking -- insumo do `ebay_summary.py`."""
    meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "watchlist_count": watchlist_count,
        "group": group or "",
        "include_raw": bool(include_raw),
        "trusted_mode": bool(config.get("trusted_mode", False)),
        "aborted": bool(aborted),
        "config": {
            "slab_strategy": config.get("slab_strategy"),
            "min_discount_percent": config.get("min_discount_percent"),
            "min_gross_margin_percent": config.get("min_gross_margin_percent"),
            "min_price_usd": config.get("min_price_usd", 10.0),
            "suspicious_margin_percent": config.get("suspicious_margin_percent", 60),
            "graded_only": config.get("graded_only", True),
            "allowed_grades": list(config.get("allowed_grades") or []),
            "graded_allow": sorted(config.get("graded_allow") or []),
            "required_location_country": config.get("required_location_country", "US"),
            "fixed_price_only": bool(config.get("fixed_price_only", True)),
        },
        "funnel": dict(funnel or {}),
    }
    rows = sort_rows([opportunity_row(o) for o in opportunities])
    return {"meta": meta, "rows": rows}


def write_json(payload, path):
    """Grava o artefato JSON do scan (registro local, gitignored)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=os.path.dirname(path) or '.', delete=False) as f:
        temp_path = f.name
        f.write(text)
    try:
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    return path


def fair_value_markdown(card, fair):
    """Tabela de preco justo por grade (modo --pricing-only). As colunas do
    PriceCharting sao INFORMATIVAS: a referencia de slab e a mediana de vendas
    comparaveis, nunca a coluna (padrao COMC)."""
    lines = [
        f"**{card.name} #{card.number} ({card.set_name}, {card.language})** "
        f"— [PriceCharting]({md_url(fair.source_url)})",
        "",
        "| Grade (coluna PC, informativa) | Preco | Tendencia | Vendas/mes | Liquidez |",
        "|---|---|---|---|---|",
    ]
    for grade in ["RAW", "GRADE 7", "GRADE 8", "PSA 9", "GRADE 9.5",
                  "PSA 10", "BGS 10", "BGS 10 BLACK", "CGC 10", "CGC 10 PRISTINE",
                  "SGC 10", "TAG 10"]:
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
