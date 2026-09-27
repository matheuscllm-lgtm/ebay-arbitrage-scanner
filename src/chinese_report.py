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
    ("rescore_outra_carta", "Descartados na entrega: outra carta (tag team / sufixo colado)"),
    ("ebay_error", "eBay: erros"),
    ("aborted_ebay", "Abortado (credencial/orçamento eBay)"),
)

_PAIR_HEADER = ("| # | Razão EN÷ZH | ZH US$ | Frete | EN PSA 10 US$ (n) | ZH PSA 10 vendas US$ (n/90 d) | Margem vs revenda ZH | Carta | Set EN | "
                "Raridade EN | Idioma | Match | País | Pop10 ZH | Vendas/mês ZH | LT | Motivos | Links |")
_PAIR_SEP = "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
_EXCL_HEADER = ("| # | LT | ZH US$ | Frete | ZH PSA 10 vendas US$ (n/90 d) | Margem vs revenda ZH | Tend. obs. | Carta | Título do anúncio | "
                "Idioma | País | Pop10 ZH | Vendas/mês ZH | Marcador | Motivos | Links |")
_EXCL_SEP = "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
_COMPACT_HEADER = "| Carta EN | Anúncios | Razão EN÷ZH (mín–máx) | Menor ZH US$ | Idiomas | Países | Menor anúncio |"
_COMPACT_SEP = "|---|---|---|---|---|---|---|"

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
    ("validar", "⚠️ Validar manualmente — razão ≥ corte, mas match só por nome, catálogo diz outra carta/sem par EN, idioma não especificado, evidência chinesa insuficiente ou referência EN pela coluna"),
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
        window = f", {en['window_days']} d" if en.get("window_days") else ""
        label = f"{_usd(en['price'])} (n={en.get('n', 0)}{window})"
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


def short_ebay_url(url: str | None) -> str:
    """URL do anúncio SEM os parâmetros de rastreio (`?_skw=…&hash=…`): mesmo item,
    mesma origem, um terço do tamanho — a tabela do chat tem milhares de links."""
    u = str(url or "")
    if "ebay." in u and "/itm/" in u:
        return u.split("?")[0]
    return u


def _links(row: dict) -> str:
    lst = row.get("listing") or {}
    en = row.get("en_ref") or {}
    zh = row.get("zh") or {}
    parts = []
    if lst.get("url"):
        parts.append(f"[oferta]({report.md_url(short_ebay_url(lst['url']))})")
    if en.get("url"):
        parts.append(f"[ref EN]({report.md_url(en['url'])})")
    if zh.get("url"):
        parts.append(f"[ref ZH]({report.md_url(zh['url'])})")
    return " · ".join(parts) if parts else "—"


def _margin(row: dict) -> str:
    v = row.get("zh_margin_pct")
    if v is None:
        from .chinese_scan import zh_margin_pct
        v = zh_margin_pct(row)
    return "n/d" if v is None else f"{v:+.0f}%"


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
        _en_cell(r.get("en_ref")), _zh_cell(zh), _margin(r),
        report.escape_md(report.carta_label(r.get("card"), r.get("number"))),
        report.escape_md(r.get("set") or "—"), report.escape_md(r.get("rarity") or "—"),
        LANG_LABEL.get(r.get("language"), r.get("language") or "—"), r.get("match") or "—",
        lst.get("country") or "—", _pop_cell(zh, lt),
        _spm(lt.get("sales_per_month")), _lt_cell(lt),
        report.escape_md(", ".join(r.get("reasons") or []) or "—"), _links(r),
    ]
    return "| " + " | ".join(cells) + " |"


def _pop_cell(zh: dict, lt: dict) -> str:
    if zh.get("status") != "ok" or zh.get("pop_psa10") is None:
        return "n/d"
    if lt.get("pop_note"):
        return f"{_int(zh.get('pop_psa10'))} (censo fino: {_int(zh.get('pop_total'))} no total — não conta)"
    return f"{_int(zh.get('pop_psa10'))} / {_int(zh.get('pop_total'))}"


def _excl_row(i: int, r: dict) -> str:
    lst = r.get("listing") or {}
    zh = r.get("zh") or {}
    lt = r.get("lt") or {}
    title = (lst.get("title") or "")[:90]
    cells = [
        str(i), _lt_cell(lt), _usd(lst.get("price")), _shipping(lst.get("shipping")), _zh_cell(zh), _margin(r), _trend(zh),
        report.escape_md(report.carta_label((r.get("pokemon") or r.get("base_name") or r.get("card") or "").title(), r.get("zh_number") or "")),
        report.escape_md(title), LANG_LABEL.get(r.get("language"), r.get("language") or "—"),
        lst.get("country") or "—", _pop_cell(zh, lt),
        _spm(lt.get("sales_per_month")), report.escape_md(r.get("exclusive_marker") or "—"),
        report.escape_md(", ".join(r.get("reasons") or []) or "—"), _links(r),
    ]
    return "| " + " | ".join(cells) + " |"


COMPACT_THRESHOLD = 40  # acima disto, no modo compacto, validar/exclusivas saem agrupadas
_GROUP_HEADER = ("| Carta EN | Set EN | Idioma | Match | ZH nº · set | Anúncios | ZH US$ mín – mediana | Razão EN÷ZH (no mín.) | "
                 "ZH PSA 10 vendas US$ (n/90 d) | Margem vs revenda ZH (no mín.) | LT | Motivos | Links (mais barato) |")
_GROUP_SEP = "|---|---|---|---|---|---|---|---|---|---|---|---|---|"
_EXCL_GROUP_HEADER = ("| Carta (ZH) | Idioma | Anúncios | ZH US$ mín – mediana | ZH PSA 10 vendas US$ (n/90 d) | "
                      "Margem vs revenda ZH (no mín.) | Tend. obs. | Pop10 ZH | LT | Marcador | Links (mais barato) |")
_EXCL_GROUP_SEP = "|---|---|---|---|---|---|---|---|---|---|---|"


def _median(vals: list[float]) -> float | None:
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def _best_zh(rs: list[dict]) -> dict:
    ok = [r["zh"] for r in rs if (r.get("zh") or {}).get("status") == "ok"]
    return ok[0] if ok else ((rs[0].get("zh") or {}) if rs else {})


def _grouped_pairs(rows: list[dict]) -> list[str]:
    groups: dict[tuple, list] = {}
    for r in rows:
        groups.setdefault((r.get("card"), r.get("number"), r.get("set"), r.get("zh_number") or "", r.get("zh_set_hint") or "",
                           r.get("language"), r.get("match")), []).append(r)
    out = [_GROUP_HEADER, _GROUP_SEP]
    for key, rs in sorted(groups.items(), key=lambda kv: -max(x.get("ratio") or 0 for x in kv[1])):
        card, number, set_name, zh_num, hint, lang, match = key
        rs.sort(key=lambda x: (x.get("listing") or {}).get("price") or 0)
        cheap = rs[0]
        prices = [(x.get("listing") or {}).get("price") for x in rs]
        zh = _best_zh(rs)
        lt = max((x.get("lt") or {}).get("score", 0) for x in rs)
        cov = next((x.get("lt") or {}).get("coverage", "0/4") for x in rs if (x.get("lt") or {}).get("score", 0) == lt)
        reasons = sorted({w for x in rs for w in (x.get("reasons") or [])})
        out.append("| " + " | ".join([
            report.escape_md(report.carta_label(card, number)), report.escape_md(set_name or "—"),
            LANG_LABEL.get(lang, lang or "—"), match or "—", report.escape_md(f"{zh_num or '?'} · {hint or '—'}"), str(len(rs)),
            f"{_usd(min(prices))} – {_usd(_median(prices))}", _ratio(cheap.get("ratio")), _zh_cell(zh),
            _margin({"listing": cheap.get("listing"), "zh": zh}), f"{lt} ({cov})",
            report.escape_md(", ".join(reasons) or "—"), _links({"listing": cheap.get("listing"), "en_ref": cheap.get("en_ref"), "zh": zh}),
        ]) + " |")
    return out


_CARD_COUNT_HEADER = "| Carta EN | Set EN | Anúncios | Idiomas | Razão EN÷ZH máx. | Menor ZH US$ (link) | Motivos mais comuns |"
_CARD_COUNT_SEP = "|---|---|---|---|---|---|---|"


def _card_counts(rows: list[dict]) -> list[str]:
    """Uma linha por carta EN: contagem, idiomas, melhor razão, menor anúncio (link) e
    motivos — para os baldes grandes na versão de chat."""
    groups: dict[tuple, list] = {}
    for r in rows:
        groups.setdefault((r.get("card"), r.get("number"), r.get("set")), []).append(r)
    out = [_CARD_COUNT_HEADER, _CARD_COUNT_SEP]
    for (card, number, set_name), rs in sorted(groups.items(), key=lambda kv: -max(x.get("ratio") or 0 for x in kv[1])):
        rs.sort(key=lambda x: (x.get("listing") or {}).get("price") or 0)
        cheap = rs[0]
        langs = sorted({LANG_LABEL.get(x.get("language"), x.get("language") or "—") for x in rs})
        why = [k for k, _ in __import__("collections").Counter(w for x in rs for w in (x.get("reasons") or [])).most_common(3)]
        out.append("| " + " | ".join([
            report.escape_md(report.carta_label(card, number)), report.escape_md(set_name or "—"), str(len(rs)), ", ".join(langs),
            _ratio(max(x.get("ratio") or 0 for x in rs)),
            f"[{_usd((cheap.get('listing') or {}).get('price'))}]({report.md_url(short_ebay_url((cheap.get('listing') or {}).get('url')))})",
            report.escape_md(", ".join(why) or "—")]) + " |")
    return out


def _grouped_exclusives(rows: list[dict]) -> list[str]:
    groups: dict[tuple, list] = {}
    for r in rows:
        groups.setdefault(((r.get("pokemon") or r.get("base_name") or r.get("card") or "").title(), r.get("zh_number") or "",
                           r.get("zh_set_hint") or "", r.get("language")), []).append(r)
    out = [_EXCL_GROUP_HEADER, _EXCL_GROUP_SEP]
    for key, rs in sorted(groups.items(), key=lambda kv: (-max((x.get("lt") or {}).get("score", 0) for x in kv[1]),
                                                          min((x.get("listing") or {}).get("price") or 0 for x in kv[1]))):
        name, zh_num, hint, lang = key
        rs.sort(key=lambda x: (x.get("listing") or {}).get("price") or 0)
        cheap = rs[0]
        prices = [(x.get("listing") or {}).get("price") for x in rs]
        zh = _best_zh(rs)
        lt_row = max(rs, key=lambda x: (x.get("lt") or {}).get("score", 0))
        lt = lt_row.get("lt") or {}
        out.append("| " + " | ".join([
            report.escape_md(report.carta_label(name, zh_num) + (f" · {hint}" if hint else "")), LANG_LABEL.get(lang, lang or "—"),
            str(len(rs)), f"{_usd(min(prices))} – {_usd(_median(prices))}", _zh_cell(zh),
            _margin({"listing": cheap.get("listing"), "zh": zh}), _trend(zh), _pop_cell(zh, lt), _lt_cell(lt),
            report.escape_md(cheap.get("exclusive_marker") or "—"), _links({"listing": cheap.get("listing"), "zh": zh}),
        ]) + " |")
    return out


def render(payload: dict, compact: bool = False) -> str:
    """Markdown da entrega. `compact=True` = versão para o CHAT: os baldes ⚠️ validar e
    exclusivas com mais de COMPACT_THRESHOLD linhas saem AGRUPADOS por carta chinesa
    (contagem, preço mínimo/mediano, evidência, margem no mínimo, LT, link do mais
    barato); 🟢 candidatas sempre inteiras. A versão completa (todas as linhas) é o
    mesmo JSON renderizado com compact=False."""
    from .chinese_scan import rescore
    payload = rescore(payload)
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
    near = float(params.get("near_miss_ratio", 2.0))
    for bucket, title in BUCKET_TITLES:
        sub = [r for r in pairs if r.get("bucket") == bucket]
        lines.append(f"### {title.format(n=min_sales, ratio=ratio)} — {len(sub)}")
        lines.append("")
        if not sub:
            lines += ["_nenhuma linha_", ""]
            continue
        full, compact_rows = sub, []
        if bucket == "abaixo-do-corte":
            full = [r for r in sub if (r.get("ratio") or 0) >= near]
            compact_rows = [r for r in sub if (r.get("ratio") or 0) < near]
        if compact and bucket == "validar" and len(full) > COMPACT_THRESHOLD:
            strong = [r for r in full if (r.get("zh") or {}).get("status") == "ok" and (r.get("zh") or {}).get("n_sales_90d", 0) >= min_sales]
            rest = [r for r in full if r not in strong]
            lines.append(f"Versão para o chat: {len(strong)} anúncios COM evidência chinesa (≥{min_sales} vendas PSA 10 em 90 d — só a identidade "
                         f"ficou por confirmar) agrupados por carta chinesa; os outros {len(rest)} (sem evidência ou sem página) saem como "
                         "contagem por carta EN. Todas as linhas estão no `.md` completo e no JSON.")
            lines.append("")
            if strong:
                lines += _grouped_pairs(strong)
                lines.append("")
            if rest:
                if len(rest) <= COMPACT_THRESHOLD:
                    lines += _card_counts(rest)
                else:
                    lines.append(f"Sem evidência chinesa: {len(rest)} anúncios de "
                                 f"{len({(x.get('card'), x.get('number'), x.get('set')) for x in rest})} cartas EN — só no `.md` completo e no JSON.")
                lines.append("")
            full = []
        elif compact and bucket == "abaixo-do-corte" and len(full) > COMPACT_THRESHOLD:
            lines.append(f"Quase ({near:g}×–{ratio:g}×): {len(full)} anúncios de {len({(x.get('card'), x.get('number'), x.get('set')) for x in full})} "
                         "cartas EN — diagnóstico, só no `.md` completo e no JSON.")
            lines.append("")
            full = []
        if full:
            lines += [_PAIR_HEADER, _PAIR_SEP]
            for i, r in enumerate(full, 1):
                lines.append(_pair_row(i, r))
            lines.append("")
        if compact_rows and compact:
            lines.append(f"Razão < {near:g}× (anúncio chinês vale mais da metade do PSA 10 inglês): {len(compact_rows)} linhas em "
                         f"{len({(r.get('card'), r.get('number'), r.get('set')) for r in compact_rows})} cartas EN — só no `.md` completo e no JSON "
                         "(diagnóstico: não há desconto relevante).")
            lines.append("")
            compact_rows = []
        if compact_rows:
            lines.append(f"Razão < {near:g}× (anúncio chinês vale mais da metade do PSA 10 inglês): {len(compact_rows)} linhas, "
                         f"agrupadas por carta EN — cada linha continua no JSON; o link é o anúncio mais barato do grupo.")
            lines.append("")
            lines += [_COMPACT_HEADER, _COMPACT_SEP]
            groups: dict[tuple, list] = {}
            for r in compact_rows:
                groups.setdefault((r.get("card"), r.get("number"), r.get("set")), []).append(r)
            for (card, number, set_name), rs in sorted(groups.items(), key=lambda kv: -max(x.get("ratio") or 0 for x in kv[1])):
                rs.sort(key=lambda x: (x.get("listing") or {}).get("price") or 0)
                cheapest = rs[0]
                ratios = [x.get("ratio") or 0 for x in rs]
                langs = sorted({LANG_LABEL.get(x.get("language"), x.get("language") or "—") for x in rs})
                countries = sorted({(x.get("listing") or {}).get("country") or "—" for x in rs})
                lines.append("| " + " | ".join([
                    report.escape_md(report.carta_label(card, number)) + f" ({report.escape_md(set_name or '—')})", str(len(rs)),
                    f"{min(ratios):.1f}×–{max(ratios):.1f}×", _usd((cheapest.get("listing") or {}).get("price")),
                    ", ".join(langs), ", ".join(countries), _links(cheapest)]) + " |")
            lines.append("")
    lines.append(f"## 2. Exclusivas chinesas — sem par em inglês, só evidência chinesa ({len(excl)} linhas)")
    lines.append("")
    if not excl:
        lines += ["_nenhuma linha_", ""]
    elif compact and len(excl) > COMPACT_THRESHOLD:
        with_page = [r for r in excl if (r.get("zh") or {}).get("status") == "ok"]
        without = [r for r in excl if (r.get("zh") or {}).get("status") != "ok"]
        lines.append(f"Versão para o chat: {len(with_page)} anúncios COM página chinesa encontrada, agrupados por carta chinesa "
                     f"(número · código de set · idioma); os {len(without)} sem página (sem evidência de revenda) saem só como contagem "
                     "por Pokémon abaixo. Todas as linhas estão no `.md` completo e no JSON.")
        lines.append("")
        if with_page:
            lines += _grouped_exclusives(with_page)
            lines.append("")
        if without:
            lines.append("| Pokémon (exclusivas sem página chinesa) | Anúncios | Idiomas | Menor US$ (link) | Motivos mais comuns |")
            lines.append("|---|---|---|---|---|")
            groups: dict[str, list] = {}
            for r in without:
                groups.setdefault((r.get("pokemon") or r.get("base_name") or r.get("card") or "").title(), []).append(r)
            for name, rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
                rs.sort(key=lambda x: (x.get("listing") or {}).get("price") or 0)
                cheap = rs[0]
                langs = sorted({LANG_LABEL.get(x.get("language"), x.get("language") or "—") for x in rs})
                why = sorted({(x.get("zh") or {}).get("status") or "não consultada" for x in rs})
                lines.append("| " + " | ".join([report.escape_md(name), str(len(rs)), ", ".join(langs),
                                                f"[{_usd((cheap.get('listing') or {}).get('price'))}]({report.md_url(short_ebay_url((cheap.get('listing') or {}).get('url')))})",
                                                report.escape_md(", ".join(why)[:120])]) + " |")
            lines.append("")
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
        "**Margem vs revenda ZH** = (mediana das vendas PSA 10 em chinês em 90 d − preço pedido) ÷ preço pedido: a margem bruta da "
        "frota contra a revenda honesta do slab chinês (negativa = o anúncio pede mais do que a carta vende em chinês). "
        "**Vendas/mês ZH** = vendas PSA 10 observadas em 90 d ÷ 3 na página chinesa. "
        "`n/d` nunca é zero. Frete = valor do anúncio quando informado (frete internacional pode diferir).",
        "",
    ]
    return "\n".join(lines)
