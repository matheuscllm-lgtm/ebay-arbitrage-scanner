"""Ranking chinês simplificado × inglês — preço de MERCADO da carta solta (raw).

Pergunta do operador (2026-10-07): quais cartas em chinês simplificado estão mais
descontadas em relação à MESMA carta em inglês? Sem exigir PSA; com piso de preço.
Este módulo responde só isso — nenhum veredito, nenhuma recomendação de compra.

Fontes (cada uma rotulada na tabela):
- Pares chinês → inglês: ``src/catalog/zh_identity.json`` (52poke wiki, ver
  docs/CHINESE_IDENTITY.md). Só linhas com ``how`` definido (identidade por impressão);
  ``ambigua``/``sem-par`` ficam fora. O campo ``how`` vai na coluna "Match".
- Preço chinês: página de SET do PriceCharting (``/console/pokemon-chinese-<set>``):
  150 cartas por página, colunas Ungraded (raw) / Grade 9 / PSA 10; paginação ``?cursor=``.
  Uma página por 150 cartas em vez de uma página por carta (custo Firecrawl ÷ 150).
- Preço inglês: TCGplayer market via tcgcsv (``src/tcg_reference``) — a referência
  canônica da frota para singles raw. Sem match exato de set + número + nome → sem
  referência (a carta fica fora, contada no funil; nunca chuta outro produto).
- Oferta: anúncio ATIVO mais barato no eBay (Browse API, preço fixo, qualquer país) cujo
  título diga chinês e NÃO cite nota de gradação — a carta solta, como o ranking compara.

Razão = EN market ÷ ZH raw · Desconto = 1 − ZH ÷ EN. Piso: EN market ≥ ``min_en_usd``.
"""
from __future__ import annotations

import html
import json
import re
from types import SimpleNamespace

from . import chinese_scan, grading, pc_sales, tcg_reference, zh_identity

PC_CONSOLE_URL = "https://www.pricecharting.com/console/pokemon-chinese-{slug}"
PAGE_SIZE = 150          # linhas por página do console (observado 2026-10-07)

DEFAULT_PARAMS = {
    "min_en_usd": 10.0,       # piso da frota para singles (R$50 ≈ US$10)
    "min_ratio": 3.0,         # linhas do chat: chinês pelo menos 3× mais barato
    "min_pairs_per_set": 20,  # sets chineses com menos pares no catálogo não são baixados
    "max_pages_per_set": 8,   # guarda: 8 × 150 = 1.200 cartas
    "max_ebay_calls": 300,
    "ebay_limit": 50,
}

MATCH_LABEL = {
    "tc-jp": "exata",                 # mesma impressão via tradicional ↔ japonês
    "set+illus+rar": "forte",         # set JP→EN + ilustrador + família de raridade
    "set+rar": "fraca (set+rar)",     # sem ilustrador na wiki
    "illus+rar": "fraca (illus+rar)", # sem set JP no mapa
}

# --- console do PriceCharting -------------------------------------------------------
_PROMO_CODES = {"sv-p", "s-p", "sm-p", "m-p"}


def console_slug(cn_code: str | None) -> str | None:
    """Código 52poke → slug do console ``pokemon-chinese-<slug>`` (inverso de
    ``zh_identity.cn_key_from_pc_url``). None = código vazio."""
    code = zh_identity.norm_code(cn_code)
    if not code:
        return None
    if code in _PROMO_CODES:
        return "promo"
    if code == "151c":
        return "151-collect"
    m = re.fullmatch(r"cbb(\d)c", code)
    if m:
        return "gem-pack" if m.group(1) == "1" else f"gem-pack-{m.group(1)}"
    if code.startswith("30th"):
        return "30th-celebration"
    return code


def console_url(slug: str, cursor: int = 0) -> str:
    base = PC_CONSOLE_URL.format(slug=slug)
    return f"{base}?cursor={cursor}" if cursor else base


_ROW_RE = re.compile(r'<tr id="product-(\d+)"(.*?)</tr>', re.S)
_TITLE_RE = re.compile(r'<td class="title"[^>]*>\s*<a href="([^"]+)">(.*?)</a>', re.S)
_CELL_RE = {
    "ungraded": re.compile(r'class="price numeric used_price"[^>]*>(.*?)</td>', re.S),
    "grade9": re.compile(r'class="price numeric cib_price"[^>]*>(.*?)</td>', re.S),
    "psa10": re.compile(r'class="price numeric new_price"[^>]*>(.*?)</td>', re.S),
}
_JS_PRICE_RE = re.compile(r'class="js-price"[^>]*>\s*\$([\d,]+\.\d{2})')
_VARIANT_RE = re.compile(r"\[[^\]]+\]")


def _cell_price(cell_html: str | None) -> float | None:
    if not cell_html:
        return None
    m = _JS_PRICE_RE.search(cell_html)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_console_page(body: str) -> list[dict]:
    """Linhas ``<tr id="product-N">`` → [{url, title, ungraded, grade9, psa10, variant}].
    Preço ausente = None (nunca 0). ``variant`` = título com "[Reverse]", "[Master Ball]"…
    (impressão paralela; o catálogo descreve a impressão base)."""
    rows = []
    for _pid, inner in _ROW_RE.findall(body or ""):
        t = _TITLE_RE.search(inner)
        if not t:
            continue
        title = " ".join(html.unescape(t.group(2)).split())
        cells = {k: _cell_price(m.group(1) if (m := rx.search(inner)) else None)
                 for k, rx in _CELL_RE.items()}
        rows.append({"url": html.unescape(t.group(1)), "title": title,
                     "variant": _VARIANT_RE.search(title) is not None, **cells})
    return rows


def fetch_console_rows(slug: str, fetch=pc_sales.fetch_page, cache_dir: str | None = None,
                       max_pages: int = DEFAULT_PARAMS["max_pages_per_set"], log=print) -> tuple[list[dict], int]:
    """Todas as linhas de um console, página a página (``cursor`` = 0, 150, 300…).
    Para quando a página vem curta (< PAGE_SIZE). Devolve (linhas, páginas baixadas)."""
    rows: list[dict] = []
    pages = 0
    for page in range(max_pages):
        body = fetch(console_url(slug, page * PAGE_SIZE), cache_dir=cache_dir)
        pages += 1
        got = parse_console_page(body)
        rows.extend(got)
        if len(got) < PAGE_SIZE:
            break
    else:
        log(f"  aviso: {slug} atingiu o teto de {max_pages} páginas; pode haver cartas fora")
    return rows, pages


# --- referência EN (TCGplayer via tcgcsv) --------------------------------------------
def en_reference(pair: dict, cache_dir: str = tcg_reference.DEFAULT_CACHE_DIR):
    """TcgReference (market USD + URL do produto) da carta EN do par, ou None quando o
    tcgcsv não resolve set/carta sem ambiguidade (nunca chuta)."""
    card = SimpleNamespace(name=pair.get("en_name") or "", number=str(pair.get("en_no") or ""),
                           set_name=pair.get("en_set") or "", tcg_set="", language="EN")
    return tcg_reference.get_tcg_reference(card, cache_dir=cache_dir)


def pairs_for(catalog: zh_identity.Catalog, pc_url: str) -> tuple[list[dict], str | None]:
    """Pares do catálogo para a página chinesa: (lista, motivo quando vazia)."""
    key = zh_identity.cn_key_from_pc_url(pc_url)
    if not key:
        return [], "pc-sem-chave"
    pairs = [p for p in catalog.by_cn(*key)
             if p.get("how") and p.get("en_set") and p.get("en_no") and not p.get("en_set_unresolved")]
    if not pairs:
        return [], "sem-par-no-catalogo"
    if len({(p["en_set"], str(p["en_no"])) for p in pairs}) > 1:
        return [], "par-ambiguo"
    return pairs, None


def build_rows(catalog: zh_identity.Catalog, pc_rows_by_slug: dict[str, list[dict]], en_lookup,
               params: dict | None = None) -> tuple[list[dict], dict]:
    """Junta página chinesa × catálogo × referência EN; aplica o piso; ordena por razão
    (maior desconto primeiro). Devolve (linhas, funil)."""
    p = {**DEFAULT_PARAMS, **(params or {})}
    funnel: dict[str, int] = {"pc-linhas": 0, "pc-variante-ignorada": 0, "pc-sem-chave": 0,
                              "sem-par-no-catalogo": 0, "par-ambiguo": 0, "zh-sem-preco-raw": 0,
                              "en-sem-referencia-tcg": 0, "en-abaixo-do-piso": 0, "linhas": 0}
    rows: list[dict] = []
    for slug, pc_rows in pc_rows_by_slug.items():
        for pr in pc_rows:
            funnel["pc-linhas"] += 1
            if pr.get("variant"):
                funnel["pc-variante-ignorada"] += 1
                continue
            pairs, why = pairs_for(catalog, pr["url"])
            if why:
                funnel[why] += 1
                continue
            pair = pairs[0]
            zh = pr.get("ungraded")
            if not zh or zh <= 0:
                funnel["zh-sem-preco-raw"] += 1
                continue
            ref = en_lookup(pair)
            if ref is None or not getattr(ref, "market_usd", None):
                funnel["en-sem-referencia-tcg"] += 1
                continue
            en = float(ref.market_usd)
            if en < p["min_en_usd"]:
                funnel["en-abaixo-do-piso"] += 1
                continue
            rows.append({
                "en_name": pair["en_name"], "en_set": pair["en_set"], "en_no": str(pair["en_no"]),
                "en_rar": pair.get("en_rar") or "", "cn_code": pair["cn_code"], "cn_no": pair["cn_no"],
                "cn_rar": pair.get("cn_rar") or "", "zh_name": pair.get("zh_name") or "",
                "how": pair["how"], "match": MATCH_LABEL.get(pair["how"], pair["how"]),
                "zh_url": pr["url"], "zh_title": pr["title"], "zh_ungraded": zh,
                "zh_grade9": pr.get("grade9"), "zh_psa10": pr.get("psa10"),
                "en_market": en, "en_url": ref.product_url, "en_group": getattr(ref, "group_name", ""),
                "ratio": en / zh, "discount": 1.0 - zh / en, "slug": slug, "offer": None,
            })
            funnel["linhas"] += 1
    rows.sort(key=lambda r: (-r["ratio"], -r["en_market"]))
    return rows, funnel


# --- oferta no eBay (carta solta, em chinês) -------------------------------------------
_LOT_RE = re.compile(r"\b(?:lot|bundle|bulk|set of|playset|x\s?\d{1,2}|\d{1,2}\s?x)\b|\bdeck\b|booster|\bbox\b|\bpack\b", re.I)
_PROXY_RE = re.compile(r"\bproxy\b|\bcustom\b|\breplica\b|\bfake\b|\bsticker\b|\bmetal\b", re.I)


def _gem_pack(cn_no: str) -> tuple[int, int] | None:
    """Gem Pack: "04 07" (pacote 4, carta 07) → (4, 7). Outros formatos → None."""
    parts = (cn_no or "").split()
    if len(parts) == 2 and all(p.isdigit() for p in parts):
        return int(parts[0]), int(parts[1])
    return None


def _cn_number_token(cn_no: str) -> str:
    """"245/208" → "245". Gem Pack não tem número único: ver `_gem_pack`."""
    s = (cn_no or "").strip().split("/")[0]
    return str(int(s)) if s.isdigit() else s


def _gem_pack_re(pack: int, num: int) -> re.Pattern[str]:
    # "4/07", "04/07", "4-07", "04 07" — pacote/carta como os títulos escrevem
    return re.compile(rf"(?<!\d)0?{pack}\s*[/\-]\s*0?{num}(?!\d)|(?<!\d){pack:02d}\s+{num:02d}(?!\d)")


def offer_query(row: dict) -> str:
    base, suffix = chinese_scan.name_parts(row["en_name"])
    core = f"{base} {suffix}".strip()
    gp = _gem_pack(row["cn_no"])
    if gp:
        return f"{core} gem pack {gp[0]}/{gp[1]:02d} (chinese,chn,simplified,中文,简体)"
    return f"{core} {_cn_number_token(row['cn_no'])} (chinese,chn,simplified,中文,简体)"


def pick_offer(listings, row: dict) -> dict | None:
    """Anúncio mais barato (item + frete) que seja: chinês (simplificado ou só "Chinese"),
    SEM nota de gradação no título (carta solta), com o nome-base e o número chinês no
    título, e não lote/réplica. None = nenhum serve."""
    base, _suffix = chinese_scan.name_parts(row["en_name"])
    gp = _gem_pack(row["cn_no"])
    if gp:
        num_re = _gem_pack_re(*gp)   # exige "pacote/carta" no título (um "7" solto é outra carta)
    else:
        num_re = re.compile(rf"(?<![\d/]){re.escape(_cn_number_token(row['cn_no']))}(?![\d])")
    best = None
    for l in listings:
        title = l.title or ""
        lang, _why = chinese_scan.chinese_language(title)
        if lang not in ("ZH-HANS", "ZH"):
            continue
        if grading.grade_mentions(title) or grading.mentions_black_label(title):
            continue
        if _LOT_RE.search(title) or _PROXY_RE.search(title):
            continue
        if base not in title.lower() or not num_re.search(title):
            continue
        total = float(l.price) + float(l.shipping or 0.0)
        cand = {"price": float(l.price), "shipping": float(l.shipping or 0.0), "total": total,
                "url": l.url, "title": title, "country": getattr(l, "country", "") or "",
                "language": "simplificado" if lang == "ZH-HANS" else "chinês (não especificado)"}
        if best is None or total < best["total"]:
            best = cand
    return best


def attach_offers(rows: list[dict], search, max_calls: int, limit: int, log=print) -> int:
    """Uma busca por linha, na ordem do ranking, até ``max_calls``. Devolve chamadas feitas."""
    calls = 0
    for r in rows:
        if calls >= max_calls:
            break
        r.setdefault("offer", None)
        try:
            listings = search(offer_query(r), min_price=1.0, limit=limit, fixed_price_only=True,
                              location_country="", max_pages=1)
        except Exception as exc:  # orçamento/rede: o ranking não depende da oferta
            log(f"  eBay falhou em {r['en_name']} {r['en_no']}: {exc}")
            break
        calls += 1
        r["offer"] = pick_offer(listings, r)
        r["offer_searched"] = True
    return calls


# --- entrega -----------------------------------------------------------------------
def _usd(v: float | None) -> str:
    return "n/d" if v is None else f"US${v:,.2f}"


def _row_md(i: int, r: dict) -> str:
    o = r.get("offer")
    if o:
        offer = f"{_usd(o['price'])} + {_usd(o['shipping'])} ({o['language']})"
        offer_ratio = f"{r['en_market'] / o['total']:.1f}×" if o.get("total") else "n/d"
        country = o.get("country") or "n/d"
        links = f"[oferta]({o['url']}) · [ref EN]({r['en_url']}) · [ref ZH]({r['zh_url']})"
    else:
        offer = "sem anúncio raw chinês no eBay" if r.get("offer_searched") else "não buscado"
        offer_ratio = "—"
        country = "—"
        links = f"[ref EN]({r['en_url']}) · [ref ZH]({r['zh_url']})"
    return (f"| {i} | {r['ratio']:.1f}× | {r['discount']*100:.0f}% | {_usd(r['en_market'])} | "
            f"{_usd(r['zh_ungraded'])} | {_usd(r.get('zh_psa10'))} | {r['en_name']} {r['en_no']} | {r['en_set']} | "
            f"{r['en_rar'] or 'n/d'} | {r['cn_no']} · {r['cn_code']} | {r['match']} | {offer} | {offer_ratio} | {country} | {links} |")


_HEADER = ("| # | Razão EN÷ZH | Desconto | EN market US$ (TCGplayer) | ZH raw US$ (PC) | ZH PSA 10 US$ (PC) | "
           "Carta EN | Set EN | Raridade EN | Carta ZH (nº · set) | Match | Oferta eBay (item + frete) | Razão EN÷oferta | País | Links |\n"
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")


def render_markdown(rows: list[dict], meta: dict, min_ratio: float | None = None) -> str:
    """Tabela do ranking. ``min_ratio`` corta as linhas (versão para o chat); None = todas."""
    p = meta.get("params", {})
    shown = [r for r in rows if min_ratio is None or r["ratio"] >= min_ratio]
    f = meta.get("funnel", {})
    out = [f"# Chinês simplificado × inglês — carta solta, preço de mercado — {meta.get('generated_at', '')}", ""]
    out.append(f"Razão = TCGplayer market da carta EN ÷ preço raw (Ungraded) da MESMA carta em chinês simplificado no "
               f"PriceCharting. Desconto = 1 − ZH÷EN. Piso: EN market ≥ US${p.get('min_en_usd', 0):g}. "
               f"Pares pelo catálogo 52poke (`Match`: exata = mesma impressão via japonês; forte = set + ilustrador + "
               f"raridade; fraca = só dois desses). Oferta = anúncio ativo mais barato no eBay (preço fixo, qualquer país) "
               f"com título chinês e SEM nota de gradação; `ZH PSA 10` é só informação. Nenhuma recomendação de compra.")
    out.append("")
    out.append(f"Sets chineses baixados: {meta.get('sets', 0)} · páginas PriceCharting: {meta.get('pages', 0)} · "
               f"chamadas eBay: {meta.get('ebay_calls', 0)}")
    out.append("Funil: " + " · ".join(f"{k}: {v}" for k, v in f.items()))
    out.append("")
    title = (f"## Ranking — razão ≥ {min_ratio:g}× — {len(shown)} linhas (todas as {len(rows)} acima do piso no `.md` completo e no JSON)"
             if min_ratio is not None else f"## Ranking — {len(shown)} linhas acima do piso")
    out.append(title)
    out.append("")
    if not shown:
        out.append("_nenhuma linha_")
    else:
        out.append(_HEADER)
        out.extend(_row_md(i, r) for i, r in enumerate(shown, 1))
    out.append("")
    out.append("Legenda: **EN market** = TCGplayer market price (tcgcsv, NM) · **ZH raw** = coluna Ungraded da página "
               "chinesa do PriceCharting (vendas de carta solta; pode ser rala — conferir a página) · **Oferta** = item + "
               "frete informado pelo anúncio · **Razão EN÷oferta** = EN market ÷ (item + frete) do anúncio achado, a razão "
               "contra um preço que dá para pagar hoje; `sem anúncio raw chinês no eBay` = a busca voltou só gradadas, lotes ou outro "
               "idioma · `não buscado` = fora do orçamento de chamadas · `n/d` nunca é zero.")
    return "\n".join(out) + "\n"


def to_json(rows: list[dict], meta: dict) -> str:
    return json.dumps({"meta": meta, "rows": rows}, ensure_ascii=False, indent=1)
