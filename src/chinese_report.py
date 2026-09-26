"""Entrega do modo CHINÊS (`meta.kind == "chinese-psa10"`): markdown canônico da
frota, colado VERBATIM no chat pelo `ebay_summary.py`.

Duas tabelas, TODAS as linhas (nunca amostra):

1. **Pares** — anúncio PSA 10 em chinês de uma carta EN da watchlist, em 4 baldes:
   🟢 candidata (razão EN÷ZH ≥ corte, nome+número, idioma definido e ≥3 vendas PSA 10
   em chinês em 90 d) · ⚠️ validar (razão ≥ corte mas algo falta) · 🔎 abaixo do corte
   (diagnóstico) · ❌ sem referência EN.
2. **Exclusivas** — sem par em inglês (marcador no título): só evidência chinesa +
   régua LT, ordenadas por LT.

Toda linha tem `[oferta]` (eBay) e a referência EN clicável (`[US$ … (n)](pc_url)`)
quando existe, e `[ref ZH]` (página chinesa no PriceCharting) quando encontrada.
URLs lidas do JSON, nunca inventadas. Nenhuma recomendação de compra.
"""
from __future__ import annotations

from . import report
from .chat_format import reference_price

KIND = "chinese-psa10"

FUNNEL_LABELS = (
    ("cards_scanned", "Cartas EN consultadas"),
    ("ebay_calls", "Chamadas eBay"),
    ("listings_fetched", "Anúncios baixados"),
    ("skip_not_psa10", "Descartados: não é PSA 10 (ou nota ambígua)"),
    ("skip_sem-marcador", "Descartados: sem marcador de chinês no título"),
    ("skip_outro-idioma", "Descartados: outro idioma citado junto"),
    ("skip_name_mismatch", "Descartados: outra carta (nome/dono/raridade não casa)"),
    ("skip_lote", "Descartados: lote/deck"),
    ("skip_rejeitar", "Descartados: réplica/acessório"),
    ("skip_below_floor", "Descartados: abaixo do piso de preço"),
    ("rows_candidata", "Linhas 🟢 candidata"),
    ("rows_validar", "Linhas ⚠️ validar"),
    ("rows_abaixo-do-corte", "Linhas 🔎 abaixo do corte"),
    ("rows_sem-referencia-en", "Linhas ❌ sem referência EN"),
    ("rows_exclusiva", "Linhas exclusivas (tabela 2)"),
    ("pc_fetch", "Páginas PriceCharting baixadas"),
    ("pc_error", "PriceCharting: erros"),
    ("en_ref_vendas", "Referência EN por vendas (≥3)"),
    ("en_ref_coluna-PC", "Referência EN pela coluna do site (<3 vendas)"),
    ("en_ref_sem-referencia", "Referência EN ausente"),
    ("zh_page_ok", "Páginas chinesas encontradas"),
    ("zh_page_ausente", "Páginas chinesas: sem resultado"),
    ("zh_page_ambigua", "Páginas chinesas: resultado ambíguo (não chuta)"),
    ("zh_page_teto", "Páginas chinesas: teto por carta atingido"),
    ("ebay_error", "eBay: erros"),
    ("aborted_ebay", "Abortado (credencial/orçamento eBay)"),
)

_PAIR_HEADER = ("| # | Razão EN÷ZH | ZH US$ | Frete | EN PSA 10 US$ (n) | ZH PSA 10 vendas US$ (n/90 d) | Carta | Set EN | "
                "Raridade EN | Idioma | Match | País | Pop10 ZH | Vendas/mês ZH | LT | Motivos | Links |")
_PAIR_SEP = "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
_EXCL_HEADER = ("| # | LT | ZH US$ | Frete | ZH PSA 10 vendas US$ (n/90 d) | Tend. obs. | Carta | Título do anúncio | "
                "Idioma | País | Pop10 ZH | Vendas/mês ZH | Marcador | Motivos | Links |")
_EXCL_SEP = "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"

def funnel_lines(counts: dict) -> list[str]:
    """'rótulo: N' só dos contadores > 0; chave sem rótulo sai como 'outros: k=v'
    (nunca some). Próprio deste modo: `report.funnel_lines` compara com as chaves
    do modo política e repetiria tudo em 'outros'."""
    counts = counts or {}
    known = {k for k, _ in FUNNEL_LABELS}
    out = [f"{label}: {int(counts[key])}" for key, label in FUNNEL_LABELS if counts.get(key)]
    extra = {k: v for k, v in counts.items() if k not in known and v}
    if extra:
        out.append("outros: " + ", ".join(f"{k}={v}" for k, v in sorted(extra.items())))
    return out


BUCKET_TITLES = (
    ("candidata", "🟢 Candidatas — razão ≥ corte, nome+número, idioma definido e ≥{n} vendas PSA 10 em chinês (90 d)"),
    ("validar", "⚠️ Validar manualmente — razão ≥ corte, mas match só por nome, idioma não especificado, evidência chinesa insuficiente ou referência EN pela coluna"),
    ("abaixo-do-corte", "🔎 Abaixo do corte (razão < {ratio:g}×) — diagnóstico, não candidata"),
    ("sem-referencia-en", "❌ Sem referência PSA 10 em inglês — razão não calculável"),
)

LANG_LABEL = {"ZH-HANS": "simplificado", "ZH-HANT": "tradicional", "ZH": "chinês (não especificado)"}


def _usd(v) -> str:
    if v is None:
        return "n/d"
    try:
        return f"US${float(v):,.2f}"
    except (TypeError, ValueError):
        return "n/d"


def _ratio(v) -> str:
    return "n/d" if v is None else f"{float(v):.1f}×"


def _int(v) -> str:
    return "n/d" if v is None else f"{int(v):,}"


def _spm(v) -> str:
    return "n/d" if v is None else f"{float(v):.1f}"


def _shipping(v) -> str:
    return "n/d" if v is None else _usd(v)


def _en_cell(en: dict | None) -> str:
    if not en or en.get("price") is None:
        return "n/d"
    if en.get("source") == "vendas":
        label = f"{_usd(en['price'])} (n={en.get('n', 0)}, {en.get('window_days')} d)"
    else:
        label = f"{_usd(en['price'])} (coluna PC, n={en.get('n', 0)})"
    return reference_price(label, en.get("url"))


def _zh_cell(zh: dict | None) -> str:
    if not zh:
        return "n/d (não consultada)"
    if zh.get("status") != "ok":
        return f"n/d ({zh.get('status')})"
    n = zh.get("n_sales_90d", 0)
    if not n:
        label = f"sem venda em 90 d (coluna PC {_usd(zh.get('psa10_column_usd'))})"
        return reference_price(label, zh.get("url"))
    return reference_price(f"{_usd(zh.get('median_90d'))} (n={n}/{zh.get('months_90d', 0)} m)", zh.get("url"))


def _lt_cell(lt: dict | None) -> str:
    if not lt:
        return "n/d"
    return f"{lt.get('score', 0)} ({lt.get('coverage', '0/4')}; {lt.get('character_tier', '—')})"


def _links(row: dict) -> str:
    lst = row.get("listing") or {}
    en = row.get("en_ref") or {}
    zh = row.get("zh") or {}
    parts = []
    if lst.get("url"):
        parts.append(f"[oferta]({report.md_url(lst['url'])})")
    if en.get("url"):
        parts.append(f"[ref EN]({report.md_url(en['url'])})")
    if zh.get("url"):
        parts.append(f"[ref ZH]({report.md_url(zh['url'])})")
    return " · ".join(parts) if parts else "—"


def _trend(zh: dict | None) -> str:
    if not zh or zh.get("status") != "ok" or zh.get("trend_observed_pct") is None:
        return "n/d"
    return f"{zh['trend_observed_pct']:+.0f}% (90 d vs 90–365 d)"


def _pair_row(i: int, r: dict) -> str:
    lst = r.get("listing") or {}
    zh = r.get("zh") or {}
    lt = r.get("lt") or {}
    cells = [
        str(i), _ratio(r.get("ratio")), _usd(lst.get("price")), _shipping(lst.get("shipping")),
        _en_cell(r.get("en_ref")), _zh_cell(zh),
        report.escape_md(report.carta_label(r.get("card"), r.get("number"))),
        report.escape_md(r.get("set") or "—"), report.escape_md(r.get("rarity") or "—"),
        LANG_LABEL.get(r.get("language"), r.get("language") or "—"), r.get("match") or "—",
        lst.get("country") or "—", _int(zh.get("pop_psa10") if zh.get("status") == "ok" else None),
        _spm(lt.get("sales_per_month")), _lt_cell(lt),
        report.escape_md(", ".join(r.get("reasons") or []) or "—"), _links(r),
    ]
    return "| " + " | ".join(cells) + " |"


def _excl_row(i: int, r: dict) -> str:
    lst = r.get("listing") or {}
    zh = r.get("zh") or {}
    lt = r.get("lt") or {}
    title = (lst.get("title") or "")[:90]
    cells = [
        str(i), _lt_cell(lt), _usd(lst.get("price")), _shipping(lst.get("shipping")), _zh_cell(zh), _trend(zh),
        report.escape_md(report.carta_label((r.get("pokemon") or r.get("base_name") or r.get("card") or "").title(), r.get("zh_number") or "")),
        report.escape_md(title), LANG_LABEL.get(r.get("language"), r.get("language") or "—"),
        lst.get("country") or "—", _int(zh.get("pop_psa10") if zh.get("status") == "ok" else None),
        _spm(lt.get("sales_per_month")), report.escape_md(r.get("exclusive_marker") or "—"),
        report.escape_md(", ".join(r.get("reasons") or []) or "—"), _links(r),
    ]
    return "| " + " | ".join(cells) + " |"


def render(payload: dict) -> str:
    meta = payload.get("meta") or {}
    rows = payload.get("rows") or []
    params = meta.get("params") or {}
    ratio = float(params.get("min_ratio", 4.0))
    min_sales = int(params.get("min_zh_sales", 3))
    group = meta.get("group") or "todos"
    lines = [
        f"# PSA 10 em chinês × PSA 10 em inglês — grupo {group} — {meta.get('timestamp', 'n/d')}",
        "",
        f"Crivo: preço pedido do slab chinês (sem frete) ≤ PSA 10 inglês ÷ {ratio:g} · item ≥ US${float(params.get('min_price_usd', 10)):g} · "
        f"vendedor de qualquer país (frete/alfândega FORA da reserva de US$10, por conta do operador) · "
        f"candidata exige ≥{min_sales} vendas PSA 10 da carta em CHINÊS em {params.get('evidence_window_days', 90)} d.",
        "Fontes: eBay Browse API (anúncios ativos, preço fixo, graded) · referência EN = vendas concluídas PSA 10 na página EN da "
        "watchlist (PriceCharting; coluna do site só quando <3 vendas, rotulado) · evidência ZH = vendas concluídas PSA 10 na página "
        "CHINESA do PriceCharting (censo PSA `Pop10` quando o site publica; é mensal e atrasa).",
        f"LT = régua de longo prazo INFORMATIVA (nunca gate): Personagem + Raridade + Escassez (pop PSA 10 chinês) + Demanda "
        f"(vendas/mês do PSA 10 chinês), 0–100, `k/4` = componentes com dado; faixas espelham o outlook (calibradas em cartas EN, "
        f"não recalibradas para chinês)"
        + ("." if meta.get("outlook_available", True) else "; outlook indisponível neste ambiente → Personagem n/d."),
        "Idiomas são identidades separadas: a razão EN÷ZH é só o crivo de entrada; a revenda de um slab chinês se prova com vendas "
        "em chinês. Nenhuma recomendação de compra — a decisão de capital é do operador.",
        "",
    ]
    if meta.get("aborted"):
        lines += ["> ⚠️ **Run ABORTADO/PARCIAL** (credencial, orçamento ou fonte). As linhas abaixo são o que foi coletado até a parada.", ""]
    sel = meta.get("selection") or {}
    if sel:
        lines.append(f"Cobertura: {sel.get('cards_completed', 0)}/{meta.get('scheduled', 0)} cartas do lote concluídas "
                     f"(escopo do grupo: {meta.get('watchlist_count', 0)}; adiadas: {sel.get('cards_deferred', 0)}).")
    fl = funnel_lines(meta.get("funnel") or {})
    if fl:
        lines += ["", "Funil: " + " · ".join(fl), ""]

    pairs = [r for r in rows if not r.get("exclusive")]
    excl = [r for r in rows if r.get("exclusive")]
    lines.append(f"## 1. Pares — mesma carta EN da watchlist, versão em chinês ({len(pairs)} linhas)")
    lines.append("")
    for bucket, title in BUCKET_TITLES:
        sub = [r for r in pairs if r.get("bucket") == bucket]
        lines.append(f"### {title.format(n=min_sales, ratio=ratio)} — {len(sub)}")
        lines.append("")
        if not sub:
            lines += ["_nenhuma linha_", ""]
            continue
        lines += [_PAIR_HEADER, _PAIR_SEP]
        for i, r in enumerate(sub, 1):
            lines.append(_pair_row(i, r))
        lines.append("")
    lines.append(f"## 2. Exclusivas chinesas — sem par em inglês, só evidência chinesa ({len(excl)} linhas)")
    lines.append("")
    if not excl:
        lines += ["_nenhuma linha_", ""]
    else:
        lines += [_EXCL_HEADER, _EXCL_SEP]
        for i, r in enumerate(sorted(excl, key=lambda r: (-(r.get("lt") or {}).get("score", 0), (r.get("listing") or {}).get("price") or 0)), 1):
            lines.append(_excl_row(i, r))
        lines.append("")
    lines += [
        "Legenda: **Match** `nome+numero` = nome EN inteiro e número EN no título (par forte) · `nome` = nome EN inteiro, "
        "número diferente/ausente (numeração chinesa costuma diferir → conferir a arte) · `nome-base` = só Pokémon+sufixo "
        "(dono/prefixo EN ausente). **Idioma** vem do título (aspecto `Language` do eBay é pouco confiável); "
        "`chinês (não especificado)` pede confirmação simplificado × tradicional. **Exclusiva** = marcador de produto sem par EN "
        "(promo, Gem Pack, gift box, 25th/30th…): heurística documentada em `src/chinese_scan.py::EXCLUSIVE_RE`. "
        "`n/d` nunca é zero. Frete = valor do anúncio quando informado (frete internacional pode diferir).",
        "",
    ]
    return "\n".join(lines)
