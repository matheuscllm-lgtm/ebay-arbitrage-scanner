"""Modo CHINÊS: PSA 10 em chinês no eBay × referência PSA 10 em INGLÊS (diagnóstico).

Pedido do operador (2026-09-26, entrevista `grill-me`): para cada carta EN da
watchlist, procurar a versão em CHINÊS certificada PSA 10 no eBay (qualquer país
— vendedor asiático aceito; frete/alfândega ficam FORA da reserva de US$10 e
por conta do operador) que esteja a pelo menos 4× mais barata que o PSA 10 em
inglês, item > US$10. Tese do operador: o mercado em chinês valoriza; a análise
é INDEPENDENTE e separa simplificado (ZH-HANS) de tradicional (ZH-HANT).

Invariantes que este modo respeita (política vigente, `docs/EBAY_PSA.md`):

- Idiomas são identidades separadas. A referência EN é só o CRIVO de entrada
  (a razão EN÷ZH ≥ 4). A revenda de um slab chinês só se prova com vendas
  concluídas da MESMA carta em CHINÊS (página chinesa do PriceCharting):
  candidata exige ≥ `min_zh_sales` (3) vendas PSA 10 em 90 dias.
- Nunca inventa preço: sem página chinesa → "sem referência ZH"; sem vendas →
  `n=0`; censo ausente → `n/d`.
- Nunca recomenda compra. Buckets descrevem evidência, não decisão de capital.
- Não toca `slab_strategy.evaluate` nem `slab_strategy.language` (travados em
  teste): a detecção de chinês vive aqui (`chinese_language`) e o JSON leva
  `meta.kind = "chinese-psa10"` para o `ebay_summary.py` despachar pro
  `src/chinese_report.py`.

Exclusivas (sem par em inglês — promos, Gem Pack, gift box, 25th/30th...) vão
para uma TABELA À PARTE, sem razão EN÷ZH, só com evidência chinesa e a régua de
longo prazo. Detecção por marcador de título (`EXCLUSIVE_RE`), documentada e
extensível; o operador valida.

Régua de longo prazo (coluna informativa `LT`, nunca gate): espelha os
componentes do `pokemon-longterm-outlook` — Personagem (tier S/A/B do
`outlook.notorious`, importado do repo irmão quando disponível), Raridade
(faixas do outlook), Escassez (pop PSA 10 da PÁGINA CHINESA do PriceCharting —
censo mensal que atrasa; GemRate bloqueia sessão de nuvem) e Demanda
(vendas/mês do PSA 10 chinês). Faixas calibradas em cartas EN (2026-09-21),
NÃO recalibradas para chinês — declarado na entrega.
"""
from __future__ import annotations

import os
import re
import statistics
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from . import grading, pc_sales, pricecharting, report, scanner, title_parser
from .ebay_api import EbayApiError, EbayAuthError, EbayBudgetExceeded, EbayClient
from .models import Listing, WatchCard
from .selection import select_batch, validate_batch_options

KIND = "chinese-psa10"
POLICY_VERSION = "2026-09-26.1"

DEFAULT_PARAMS = {
    "min_ratio": 4.0,            # EN PSA 10 ÷ preço pedido do slab chinês (sem frete)
    "near_miss_ratio": 2.0,      # abaixo disso a linha só conta no funil
    "min_price_usd": 10.0,       # piso da frota (preço do item)
    "min_zh_sales": 3,           # vendas PSA 10 em chinês em 90 d para "candidata"
    "evidence_window_days": 90,
    "max_zh_pages_per_card": 20, # páginas chinesas do PriceCharting por carta EN
    "max_ebay_calls": 500,
    "ebay_limit": 200,
    "location_country": "",      # vazio = qualquer país (decisão do operador)
}

# --- idioma -------------------------------------------------------------------
# Marcadores de SIMPLIFICADO (China continental): palavra, abreviação de vendedor
# ("S-Chinese", "CHN"), CJK e códigos de set da linha CS/CSV/CSM/CBB (sufixo "C").
_HANS_RE = re.compile(
    r"\bsimplified\b|\bs[\s.\-]?chinese\b|\bchn\b|简体|"
    r"\b(?:csv|csvl|csm|cbb|cs)\d{1,2}(?:\.\d)?[a-z]?c?\b|\bcsm[a-z]{0,3}c\b|\b151c\b",
    re.I)
# Marcadores de TRADICIONAL (Taiwan/Hong Kong): palavra, "T-Chinese", CJK, praça,
# e códigos que espelham o japonês com sufixo "F" ("sv4aF", "M2 F-Inferno X", "CLL F").
_HANT_RE = re.compile(
    r"\btraditional\b|\bt[\s.\-]?chinese\b|繁體|繁体|\btaiwan\b|\bhong\s*kong\b|"
    r"\b(?:sv|sm|s|m|cll|ac)\d{0,2}[a-z]?\s?f\b|\b[a-z]{1,3}\d{0,2}[a-z]?\s+f-[a-z]",
    re.I)
_GENERIC_ZH_RE = re.compile(r"\bchinese\b|\bchina\b|\bmandarin\b|\bzh\b|\bcn\b|中文", re.I)
_OTHER_LANG_RE = re.compile(
    r"\b(?:japanese|japan|jpn|korean|korea|thai|indonesian|indonesia|english|german|"
    r"french|italian|spanish|portuguese)\b|日本|한국", re.I)


def chinese_language(title: str | None) -> tuple[str | None, str]:
    """('ZH-HANS' | 'ZH-HANT' | 'ZH' | None, evidência).

    'ZH' = chinês sem dizer qual (só "Chinese") — vale como chinês, mas a linha
    pede validação porque simplificado e tradicional são mercados diferentes.
    None = sem marcador de chinês OU outro idioma citado junto (lote, conflito).
    Helper PRÓPRIO: `slab_strategy.language('Chinese')` devolve None por
    contrato (teste travado) e não deve ser afrouxado.
    """
    t = title or ""
    hans = _HANS_RE.search(t) is not None
    hant = _HANT_RE.search(t) is not None
    generic = _GENERIC_ZH_RE.search(t) is not None
    if not (hans or hant or generic):
        return None, "sem-marcador-de-chines"
    if _OTHER_LANG_RE.search(t):
        return None, "outro-idioma-citado-junto"
    if hans and hant:
        return "ZH", "marcadores-simplificado-e-tradicional"
    if hans:
        return "ZH-HANS", "marcador-simplificado"
    if hant:
        return "ZH-HANT", "marcador-tradicional"
    return "ZH", "so-chinese-generico"


# --- identidade ---------------------------------------------------------------
_SUFFIX_RE = re.compile(r"\s+(ex|gx|v|vmax|vstar|lv\.?\s*x)$", re.I)
_OWNER_RE = re.compile(r"^(?:[A-Za-z.]+'s\s+|team\s+rocket'?s\s+)", re.I)


def name_parts(name: str) -> tuple[str, str]:
    """('mewtwo', 'ex') a partir de "Team Rocket's Mewtwo ex" — base sem dono e o
    sufixo que muda a carta (ex/V/VMAX...). Sem sufixo → ''."""
    n = " ".join((name or "").split())
    m = _SUFFIX_RE.search(n)
    suffix = m.group(1).lower() if m else ""
    base = n[: m.start()] if m else n
    base = _OWNER_RE.sub("", base).strip().lower()
    return base, suffix


def discovery_query(card: WatchCard) -> str:
    """Busca por NOME-BASE + sufixo (os títulos chineses raramente trazem o dono
    "Team Rocket's" ou o número EN) + OR dos marcadores de idioma + grafias de
    PSA 10. Sintaxe `(a,b)` = OR da Browse API (provada 2026-09-26)."""
    base, suffix = name_parts(card.name)
    who = (card.pokemon or "").strip().lower() or base
    core = f"{who} {suffix}".strip() if who and who in base else f"{base} {suffix}".strip()
    return f"{core} (chinese,chn,simplified,traditional) (psa 10,psa10)"


def owner_tokens(name: str) -> list[str]:
    """Tokens do "dono" no nome EN ("Team Rocket's Mewtwo ex" → ['rocket'];
    "Cynthia's Garchomp ex" → ['cynthia']). Sem dono → []."""
    m = _OWNER_RE.match(" ".join((name or "").split()))
    if not m:
        return []
    return [tok for tok in re.split(r"[^a-z]+", m.group(0).lower().replace("'s", "")) if tok and tok != "team"]


# Famílias de raridade: raridade EN da watchlist → tokens que os títulos (EN e
# chineses, que usam siglas japonesas SAR/AR/SR/UR/HR/RR/CHR) escrevem.
_RARITY_FAMILIES: tuple[tuple[str, re.Pattern[str], re.Pattern[str]], ...] = (
    ("sir", re.compile(r"special illustration", re.I), re.compile(r"\bsar\b|\bsir\b|special\s+(?:art|illustration)", re.I)),
    ("ir", re.compile(r"^illustration rare$|(?<!special )illustration", re.I), re.compile(r"\bar\b|\bir\b|(?<!special )(?<!special\s)illustration", re.I)),
    ("hr", re.compile(r"hyper|rainbow|secret", re.I), re.compile(r"\bhr\b|\bhyper\b|\brainbow\b|\bgold\b|\bsecret\b", re.I)),
    ("ur", re.compile(r"ultra rare|full art", re.I), re.compile(r"\bsr\b|\bur\b|\bultra\b|full\s*art|\bfa\b", re.I)),
    ("chr", re.compile(r"character|trainer gallery", re.I), re.compile(r"\bchr\b|\bcsr\b|\bcharacter\b", re.I)),
    ("shiny", re.compile(r"shiny", re.I), re.compile(r"\bshiny\b|\bssr\b|\bs\b(?=\s*\d)", re.I)),
    ("amazing", re.compile(r"amazing", re.I), re.compile(r"\bamazing\b", re.I)),
    ("radiant", re.compile(r"radiant", re.I), re.compile(r"\bradiant\b", re.I)),
    ("rr", re.compile(r"double rare", re.I), re.compile(r"\brr\b|double\s+rare", re.I)),
)


def rarity_compatible(en_rarity: str | None, title: str | None) -> bool | None:
    """True = o título traz a família de raridade da carta EN (SIR↔SAR, IR↔AR…);
    False = traz OUTRA família explícita (SR quando a EN é SIR); None = o título
    não declara raridade (nem confirma nem nega)."""
    t = title or ""
    en = en_rarity or ""
    mine = [key for key, en_rx, _ in _RARITY_FAMILIES if en_rx.search(en)]
    found = [key for key, _, t_rx in _RARITY_FAMILIES if t_rx.search(t)]
    if "sir" in found and "ir" in found:
        found.remove("ir")
    if "sir" in mine and "ir" in mine:
        mine.remove("ir")
    if not found:
        return None
    if not mine:
        return None  # raridade EN desconhecida: não dá para contradizer
    return any(key in found for key in mine)


# Lote/deck/produto: nunca é um slab único. NÃO usa `title_parser._LOT_KEYWORDS`
# porque ela contém "collection" e os produtos chineses chamam-se "... Collection".
_LOT_RE = re.compile(
    r"\b(?:lot|bundle|decks?|bulk|choose|pick|complete\s+set|set\s+of\s+\d+|"
    r"x\s*(?:[2-9]|[1-9]\d+)|(?:[2-9]|[1-9]\d+)\s*x|(?:[2-9]|[1-9]\d+)\s+(?:cards|slabs))\b", re.I)


def lot_or_reject(title: str | None) -> str | None:
    t = title or ""
    if title_parser._REJECT_KEYWORDS.search(t):
        return "rejeitar-palavra-de-replica-ou-acessorio"
    if _LOT_RE.search(t):
        return "lote-ou-deck"
    return None


def match_level(card: WatchCard, title: str) -> str | None:
    """'nome+numero' (nome EN inteiro + número EN no título) · 'nome' (nome EN
    inteiro OU base + dono escrito de outro jeito; número diferente/ausente —
    numeração chinesa costuma diferir) · 'nome-base' (só Pokémon + sufixo, sem o
    dono/prefixo EN; aceito só se a raridade do título não contradiz a EN) · None."""
    t = (title or "").lower()
    for kw in card.exclude_keywords:
        if kw.lower() in t:
            return None
    if not title_parser._name_conflicts(card, t):
        return "nome+numero" if title_parser.card_matches_title(card, title) else "nome"
    base, suffix = name_parts(card.name)
    if not base:
        return None
    probe = WatchCard(f"{base} {suffix}".strip(), card.set_name, "", card.language, card.pc_url)
    if title_parser._name_conflicts(probe, t):
        return None
    owners = owner_tokens(card.name)
    if owners and all(re.search(r"\b" + re.escape(o) + r"\b", t) for o in owners):
        return "nome"
    if owners and rarity_compatible(card.rarity, title) is not True:
        return None  # "Garchomp ex" sem "Cynthia" e sem SAR = quase certo outra carta
    return "nome-base"


# --- exclusivas ---------------------------------------------------------------
EXCLUSIVE_RE = re.compile(
    r"\bgem\s*packs?\b|\bcbb\d*c?\b|\bgift\s*box\b|\bpromos?\b|\b[a-z]{1,3}-p\b|"
    r"\ball[\s-]*stars?\s*collection\b|\bclassic\b|\b25th\b|\b30th\b|\bcelebrations?\b|"
    r"\banniversary\b|\bcollection\s*box\b|\bstart(?:er)?\s*deck\b|\btin\b|\bsequential\b",
    re.I)


def exclusive_marker(title: str | None) -> str | None:
    m = EXCLUSIVE_RE.search(title or "")
    return m.group(0).lower() if m else None


# --- página chinesa no PriceCharting -------------------------------------------
_FRACTION_RE = re.compile(r"(?<![\d/])(\d{1,4})\s*/\s*(\d{1,4})(?![\d/])")
_MARKED_RE = re.compile(r"(?:#|\bno\.?\s*)0*(\d{1,4})\b", re.I)
_SET_CODE_RE = re.compile(
    r"\b((?:csvl|csv|csm|cbb|cs|cll|ac|sv|sm|xy|s|m)\d{1,2}(?:\.\d)?[a-z]?[cf]?)\b", re.I)


def zh_fraction_from_title(title: str | None) -> tuple[str | None, str | None]:
    """(numerador, denominador) da fração do título ("145/129" → ("145", "129"));
    número marcado ("#094") → ("94", None); nada → (None, None)."""
    t = title_parser._GRADE_MENTION_STRIP.sub(" ", (title or "").lower())
    t = title_parser._POP_CERT_QTY_RE.sub(" ", t)
    m = _FRACTION_RE.search(t)
    if m:
        return str(int(m.group(1))), m.group(2)   # denominador como impresso ("07")
    m = _MARKED_RE.search(t)
    return (str(int(m.group(1))), None) if m else (None, None)


def zh_number_from_title(title: str | None) -> str | None:
    """Número da carta CHINESA no título: fração ("145/129" → "145") ou marcado
    ("#094" → "94"). Nota do slab ("PSA 10") nunca é número."""
    t = title_parser._GRADE_MENTION_STRIP.sub(" ", (title or "").lower())
    t = title_parser._POP_CERT_QTY_RE.sub(" ", t)
    m = _FRACTION_RE.search(t)
    if m:
        return str(int(m.group(1)))
    m = _MARKED_RE.search(t)
    return str(int(m.group(1))) if m else None


def zh_set_hint(title: str | None) -> str | None:
    """Pista de set para escolher a página chinesa certa: código ("csv5c",
    "sv4af") ou produto ("gem-pack", "151-collect", "30th"). Sem pista → None."""
    t = (title or "").lower()
    if re.search(r"\bgem\s*pack", t):
        return "gem-pack"
    if re.search(r"\b151\b", t) and not re.search(r"\d{1,4}\s*/\s*151\b", t):
        return "151-collect"
    if re.search(r"\b151c\b|/\s*151\b", t):
        return "151-collect"
    if "30th" in t:
        return "30th"
    m = _SET_CODE_RE.search(t)
    return m.group(1).replace(".", "").lower() if m else None


def zh_search_url(base: str, suffix: str, number: str | None, hint: str | None = None) -> str:
    """Busca `pokemon chinese <nome> <número>`; sem número no título, busca pelo
    código de set do título (`hint`) — só então a página pode ser única."""
    q = f"pokemon chinese {base} {suffix} {number or ''}".split()
    if not number and hint:
        q.append(hint.replace("-", " "))
    return "https://www.pricecharting.com/search-products?type=prices&q=" + quote(" ".join(q))


# Resultado de busca do PriceCharting: href ABSOLUTO ("https://www.pricecharting.com/game/…")
# com o texto do link ("Greninja Ex #242"); páginas antigas traziam href relativo.
_ZH_LINK_RE = re.compile(
    r'href="(?:https?://www\.pricecharting\.com)?(/game/pokemon-chinese-([a-z0-9.\-]+)/([a-z0-9.\-]+))"[^>]*>\s*([^<]*)', re.I)


_PRINT_VARIANTS = ("master-ball", "poke-ball", "reverse", "1st", "shadowless", "stamped", "cosmos", "error")


def _title_variants(title: str) -> set[str]:
    t = (title or "").lower()
    return {v for v in _PRINT_VARIANTS if v.replace("-", " ") in t or v.replace("-", "") in t.replace(" ", "")}


def pick_zh_page(body: str, base: str, suffix: str, number: str | None, hint: str | None,
                 title: str = "", denominator: str | None = None) -> tuple[str | None, str]:
    """Escolhe a página chinesa a partir do HTML da busca (função pura).

    Regras: só `/game/pokemon-chinese-*/`; o slug da carta termina no número
    pedido; TODOS os tokens do nome-base (+ sufixo) estão no slug; com pista de
    set, só páginas cujo set contém a pista. Exatamente 1 → URL; 0 → 'sem-pagina';
    >1 → 'ambigua' (nunca chuta). Busca específica pode REDIRECIONAR direto pro
    produto: aí o canonical decide, com as mesmas guardas.
    """
    want = {tok for tok in re.split(r"[^a-z0-9]+", f"{base} {suffix}".lower()) if tok}
    num = str(int(number)) if number and number.isdigit() else (number or "")
    if not num and not hint:
        return None, "sem-numero-e-sem-pista"
    # Gem Pack e afins: o PriceCharting cola numerador+denominador no slug
    # ("11/15" → "eevee-1115"); aceito como forma alternativa do número.
    glued = f"{num}{denominator}" if num and denominator and denominator.isdigit() else ""  # "4"+"07" → "407"
    wanted_variants = _title_variants(title)

    def _ok(card_slug: str, label: str = "") -> bool:
        """Nome inteiro no slug e, com número, o slug termina nele (ou na forma
        colada) OU o texto do link/título traz "#<número>" (promos como
        "squirtle-330th-p" colam o número ao código no slug)."""
        toks = [tok for tok in card_slug.lower().split("-") if tok]
        if not toks or not want.issubset(set(toks)):
            return False
        if not num:
            return True
        if toks[-1].isdigit() and str(int(toks[-1])) in (num, glued):
            return True
        return re.search(r"#\s*0*" + re.escape(num) + r"(?![\d])", label or "") is not None

    def _slug_variants(path: str) -> set[str]:
        slug = path.rstrip("/").split("/")[-1].lower()
        return {v for v in _PRINT_VARIANTS if v in slug}

    candidates: list[tuple[str, str]] = []
    seen = set()
    for path, set_slug, card_slug, label in _ZH_LINK_RE.findall(body):
        if path in seen or not _ok(card_slug, label):
            continue
        seen.add(path)
        # o rótulo do link entra no "set" para a pista casar promos ("#1/30th-P")
        candidates.append((path, set_slug.lower() + " " + label.lower()))
    if not candidates:
        canon = pricecharting.product_url_from_search(body)
        if canon and "/game/pokemon-chinese-" in canon:
            parts = canon.rstrip("/").split("?")[0].split("/")
            title = re.search(r"<title>([^<]*)</title>", body, re.I)
            if len(parts) >= 2 and _ok(parts[-1], title.group(1) if title else ""):
                return canon, "redirect-canonical"
        return None, "sem-pagina"
    if hint:
        h = hint.replace(".", "")
        narrowed = [c for c in candidates if h in c[1].replace(".", "")]
        if narrowed:
            candidates = narrowed
        elif not num:
            return None, "sem-pagina"   # sem número, a pista de set é obrigatória
    if len(candidates) > 1:
        # Variante de impressão: "[Master Ball]"/"[Reverse]" só quando o título pede;
        # sem pedido, fica a página comum (sem variante no slug).
        same = [c for c in candidates if _slug_variants(c[0]) == wanted_variants]
        if len(same) >= 1:
            candidates = same
    if len(candidates) == 1:
        return "https://www.pricecharting.com" + candidates[0][0], "unica"
    return None, f"ambigua({len(candidates)})"


_POP_RE = re.compile(r'VGPC\.pop_data\s*=\s*(\{.*?\})\s*;', re.S)


def parse_pop_data(body: str) -> dict | None:
    """`VGPC.pop_data` da página ({'psa': [g1..g10], 'cgc': [...]}) ou None."""
    m = _POP_RE.search(body or "")
    if not m:
        return None
    try:
        import json
        d = json.loads(m.group(1))
    except ValueError:
        return None
    psa = d.get("psa")
    if not isinstance(psa, list) or len(psa) < 10:
        return None
    try:
        return {"psa": [int(x) for x in psa[:10]], "cgc": [int(x) for x in (d.get("cgc") or [])[:10]]}
    except (TypeError, ValueError):
        return None


def sales_per_month_from_page(body: str) -> float | None:
    """Vendas/mês do PSA 10 conforme a própria página (parser do outlook, repo
    irmão). Sem outlook → None (a evidência observada em 90 d segue no lugar)."""
    ol = _outlook()
    if not ol:
        return None
    try:
        return ol["psa10"].parse_psa10_sales_per_month(body)
    except Exception:  # parser de terceiro: nunca derruba o scan
        return None


def _iso(d: str) -> date | None:
    try:
        return date.fromisoformat(d)
    except (TypeError, ValueError):
        return None


def zh_evidence(body: str, today: date, window_days: int = 90) -> dict:
    """Evidência da carta CHINESA na própria página: vendas concluídas PSA 10 em
    `window_days` (n, meses distintos, mediana), janela anterior (para tendência
    observada), coluna PSA 10 do site (só informativa), vendas/mês do site e
    censo PSA (pop por nota) quando publicado."""
    sales = pc_sales.parse_sales(body)
    kept = []
    for s in sales:
        title = s.get("title") or ""
        if _OTHER_LANG_RE.search(title):
            continue
        g = grading.grade_from_title(title)
        if not g.grade or g.grade.key != "PSA 10":
            continue
        d = _iso(s.get("date", ""))
        price = s.get("price")
        if d is None or d > today or not isinstance(price, (int, float)) or price <= 0:
            continue
        kept.append({"date": d.isoformat(), "price": float(price), "title": title,
                     "url": f"https://www.ebay.com/itm/{s['sale_id']}" if str(s.get("sale_id", "")).isdigit() else ""})
    start = today - timedelta(days=window_days)
    prior_start = today - timedelta(days=365)
    recent = [s for s in kept if date.fromisoformat(s["date"]) >= start]
    prior = [s for s in kept if prior_start <= date.fromisoformat(s["date"]) < start]
    recent.sort(key=lambda s: s["date"], reverse=True)
    median = round(statistics.median(s["price"] for s in recent), 2) if recent else None
    median_prior = round(statistics.median(s["price"] for s in prior), 2) if prior else None
    trend = None
    if len(recent) >= 3 and len(prior) >= 3 and median_prior:
        trend = round((median / median_prior - 1) * 100, 1)
    columns = pc_sales.parse_grade_prices(body)
    pop = parse_pop_data(body)
    spm_site = sales_per_month_from_page(body)
    return {
        "n_sales_90d": len(recent),
        "months_90d": len({s["date"][:7] for s in recent}),
        "median_90d": median,
        "sales_90d": recent[:10],
        "n_sales_prior": len(prior),
        "median_prior": median_prior,
        "trend_observed_pct": trend,
        "psa10_column_usd": columns.get("PSA 10"),
        "sales_per_month_site": spm_site,
        "sales_per_month_observed": round(len(recent) / (window_days / 30.0), 1) if recent else 0.0,
        "pop_psa10": pop["psa"][9] if pop else None,
        "pop_total": sum(pop["psa"]) if pop else None,
    }


# --- referência EN (crivo) -----------------------------------------------------
def en_reference(card: WatchCard, body: str, today: date) -> dict:
    """Mediana das vendas PSA 10 em INGLÊS da carta (página EN da watchlist),
    cesta legada `pc_sales.comparable_sales` (exclui título com outro idioma),
    na menor janela com ≥3 vendas (90/180/365 d). Sem 3 vendas → coluna PSA 10
    do site, ROTULADA 'coluna-PC'. É o CRIVO de entrada (razão ≥4×), nunca a
    revenda do slab chinês."""
    sales = pc_sales.parse_sales(body)
    comps = pc_sales.comparable_sales(sales, "PSA", 10, variants=frozenset(), card=card)
    dated = [(d, s) for s in comps if (d := _iso(s.get("date", ""))) and d <= today and s.get("price", 0) > 0]
    for window in (90, 180, 365):
        sel = [s for d, s in dated if d >= today - timedelta(days=window)]
        if len(sel) >= 3:
            return {"price": round(statistics.median(s["price"] for s in sel), 2), "n": len(sel),
                    "window_days": window, "source": "vendas", "url": card.pc_url}
    column = pc_sales.parse_grade_prices(body).get("PSA 10")
    if column:
        return {"price": float(column), "n": len(dated), "window_days": None,
                "source": "coluna-PC", "url": card.pc_url}
    return {"price": None, "n": len(dated), "window_days": None, "source": "sem-referencia", "url": card.pc_url}


# --- régua de longo prazo (espelho do outlook; informativa) ---------------------
_OUTLOOK: dict | None | bool = None


def _outlook() -> dict | None:
    """Módulos do repo irmão `pokemon-longterm-outlook` (OUTLOOK_DIR ou pasta
    irmã). Ausente → None: a régua degrada para n/d, nunca inventa."""
    global _OUTLOOK
    if _OUTLOOK is not None:
        return _OUTLOOK or None
    here = Path(__file__).resolve()
    candidates = [os.environ.get("OUTLOOK_DIR"), here.parents[2] / "pokemon-longterm-outlook"]
    for c in candidates:
        if c and (Path(c) / "outlook" / "notorious.py").exists():
            if str(c) not in sys.path:
                sys.path.insert(0, str(c))
            try:
                from outlook import notorious, psa10  # type: ignore
                _OUTLOOK = {"notorious": notorious, "psa10": psa10}
                return _OUTLOOK
            except Exception:  # dependência de terceiro faltando etc.
                break
    _OUTLOOK = False
    return None


def character_points(name: str) -> int | None:
    ol = _outlook()
    if not ol:
        return None
    try:
        return int(ol["notorious"].appeal_points(name))
    except Exception:
        return None


def character_tier(points: int | None) -> str:
    return {25: "S", 18: "A", 12: "B"}.get(points, "—" if points is None else "n/l")


_RARITY_RULES = (
    (re.compile(r"special illustration|\bsar\b|\bsir\b", re.I), 25),
    (re.compile(r"illustration|\bar\b|\bir\b", re.I), 20),
    (re.compile(r"trainer gallery|character|\bcsr\b|\bchr\b|\bmega attack\b|\battack\b", re.I), 16),
    (re.compile(r"hyper|secret|rainbow|\bhr\b|\bur\b|\bssr\b|gold|amazing|radiant|shiny", re.I), 14),
    (re.compile(r"vmax|vstar|ultra|\bsr\b|full art|\bfa\b", re.I), 12),
    (re.compile(r"ace spec", re.I), 10),
    (re.compile(r"double rare|\brr\b|rare holo v\b", re.I), 6),
)


def rarity_points(text: str | None) -> int:
    """Faixas de raridade do outlook (`scoring.rarity_points`) + siglas dos
    títulos chineses (SAR/AR/CSR/UR/SSR/SR/RR). Nada reconhecido → 3."""
    t = text or ""
    for rx, pts in _RARITY_RULES:
        if rx.search(t):
            return pts
    return 3


def scarcity_points(pop10: int | None) -> int | None:
    if pop10 is None:
        return None
    for cap, pts in ((50, 25), (500, 22), (2000, 18), (5000, 12), (10000, 7)):
        if pop10 <= cap:
            return pts
    return 3


def demand_points(spm: float | None) -> int | None:
    if spm is None:
        return None
    for floor, pts in ((60, 25), (30, 20), (5, 14), (2, 8)):
        if spm >= floor:
            return pts
    return 3


POP_TOTAL_MIN_TRUST = 25  # espelho do outlook: censo com menos de 25 slabs no total é página fina, não escassez


def longterm(card_name: str, rarity_text: str, zh: dict | None) -> dict:
    """Score 0-100 = soma dos componentes disponíveis; `coverage` = k/4. Componente
    sem dado fica None (nunca zero). Demanda: vendas PSA 10 observadas em 90 d ÷ 3
    (o número do site é só informativo)."""
    ch = character_points(card_name)
    ra = rarity_points(rarity_text)
    pop10 = zh.get("pop_psa10") if zh else None
    pop_total = zh.get("pop_total") if zh else None
    pop_note = None
    if pop10 is not None and (pop_total or 0) < POP_TOTAL_MIN_TRUST:
        # Censo fino (< 25 slabs no total) no PriceCharting = página pouco
        # alimentada, não escassez real → Escassez n/d, com o motivo declarado.
        pop_note = f"censo fino ({pop_total} no total) — escassez n/d"
        pop10 = None
    spm = None
    if zh:
        # Demanda = vendas PSA 10 OBSERVADAS em 90 d na própria página (÷3). O
        # "N sales per month" do site fica só informativo: nas páginas chinesas o
        # layout da tabela muda e o parser do outlook lê a coluna errada/None.
        spm = zh.get("sales_per_month_observed")
        if spm is None:
            spm = zh.get("sales_per_month_site")
    sc = scarcity_points(pop10)
    de = demand_points(spm)
    parts = {"character": ch, "rarity": ra, "scarcity": sc, "demand": de}
    have = [v for v in parts.values() if v is not None]
    return {**parts, "character_tier": character_tier(ch), "pop_psa10": pop10, "sales_per_month": spm,
            "pop_note": pop_note, "score": sum(have), "coverage": f"{len(have)}/4"}


def rescore(payload: dict) -> dict:
    """Recalcula `lt`, `zh_margin_pct` e o bucket de cada linha a partir do que o
    JSON já guarda (sem rede). Idempotente: a entrega sempre sai da régua atual,
    mesmo para um JSON gravado antes de um ajuste de faixa/guarda."""
    params = {**DEFAULT_PARAMS, **((payload.get("meta") or {}).get("params") or {})}
    for r in payload.get("rows") or []:
        zh = r.get("zh") if (r.get("zh") or {}).get("status") == "ok" else None
        r["lt"] = longterm(r.get("card") or "", r.get("rarity") or (r.get("listing") or {}).get("title") or "", zh)
        r["zh_margin_pct"] = zh_margin_pct(r)
        r["bucket"], r["reasons"] = classify(r, params)
    return payload


def zh_margin_pct(row: dict) -> float | None:
    """Margem BRUTA da frota contra a revenda HONESTA do slab chinês:
    (mediana das vendas PSA 10 em chinês em 90 d − preço pedido) ÷ preço pedido.
    Sem mediana (n=0 ou sem página) → None. É informativa: negativa significa que o
    anúncio pede mais do que a carta vem vendendo em chinês."""
    zh = row.get("zh") or {}
    price = (row.get("listing") or {}).get("price")
    median = zh.get("median_90d") if zh.get("status") == "ok" else None
    if not price or median is None:
        return None
    return round((median - price) / price * 100, 1)


# --- classificação --------------------------------------------------------------
def classify(row: dict, params: dict) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if row.get("exclusive"):
        return "exclusiva", reasons
    en = row.get("en_ref") or {}
    ratio = row.get("ratio")
    if en.get("price") is None or ratio is None:
        return "sem-referencia-en", ["sem-referencia-en"]
    if ratio < float(params["min_ratio"]):
        return "abaixo-do-corte", [f"razao<{params['min_ratio']:g}"]
    rc, m = row.get("rarity_check"), row.get("match")
    if m == "nome+numero":
        if rc is False:
            reasons.append("raridade-divergente")
    elif m == "nome" and rc is True:
        pass  # nome inteiro + mesma família de raridade: par forte mesmo sem número
    else:
        reasons.append(f"match-{m}")
        reasons.append("raridade-divergente" if rc is False else "raridade-nao-confirmada")
    if row.get("language") == "ZH":
        reasons.append("idioma-nao-especificado")
    zh = row.get("zh") or {}
    n = zh.get("n_sales_90d")
    if zh.get("status") != "ok":
        reasons.append(f"zh-{zh.get('status') or 'nao-consultada'}")
    elif (n or 0) < int(params["min_zh_sales"]):
        reasons.append(f"evidencia-zh-insuficiente({n or 0}<{params['min_zh_sales']})")
    if en.get("source") == "coluna-PC":
        reasons.append("ref-en-coluna-PC")
    return ("candidata" if not reasons else "validar"), reasons


# --- scan -------------------------------------------------------------------------
class ZhPages:
    """Cache por run de páginas chinesas: (base, sufixo, número, pista) → dict."""

    def __init__(self, fetch, today: date, params: dict, stats: Counter, log=print):
        self.fetch, self.today, self.params, self.stats, self.log = fetch, today, params, stats, log
        self.cache: dict[tuple, dict] = {}

    def lookup(self, base: str, suffix: str, number: str | None, hint: str | None,
               title: str = "", denominator: str | None = None) -> dict:
        if not number and not hint:
            return {"status": "sem-numero-e-sem-pista-no-titulo", "url": ""}
        key = (base, suffix, number or "", hint or "", denominator or "", frozenset(_title_variants(title)))
        if key in self.cache:
            return self.cache[key]
        out = {"status": "", "url": ""}
        try:
            self.stats["pc_fetch"] += 1
            body = self.fetch(zh_search_url(base, suffix, number, hint))
            url, why = pick_zh_page(body, base, suffix, number, hint, title=title, denominator=denominator)
            if url is None:
                out["status"] = why
                self.stats["zh_page_" + ("ambigua" if why.startswith("ambigua") else "ausente")] += 1
            else:
                page = body if why == "redirect-canonical" and "price_data" in body else None
                if page is None:
                    self.stats["pc_fetch"] += 1
                    page = self.fetch(url)
                out = {"status": "ok", "url": url, "pick": why, **zh_evidence(page, self.today, int(self.params["evidence_window_days"]))}
                self.stats["zh_page_ok"] += 1
        except pc_sales.PcError as exc:
            out["status"] = "pc-erro"
            self.stats["pc_error"] += 1
            self.log(f"  AVISO: PriceCharting (chinês) falhou para {base} {suffix} #{number}: {exc}")
        self.cache[key] = out
        return out


def _listing_dict(listing: Listing) -> dict:
    return {"item_id": listing.item_id, "title": listing.title, "price": listing.price,
            "shipping": listing.shipping, "currency": listing.currency, "country": listing.country or "",
            "url": listing.url, "seller_feedback_pct": listing.seller_feedback_pct,
            "seller_feedback_score": listing.seller_feedback_score}


def scan_card(card: WatchCard, ebay, params: dict, *, fetch=pc_sales.fetch_page, today: date | None = None,
              stats: Counter | None = None, log=print, zh_pages: ZhPages | None = None) -> list[dict]:
    """Uma carta EN → linhas (dicts) de anúncios PSA 10 em chinês. 1 chamada eBay;
    página EN do PriceCharting só quando há linha; páginas chinesas só para
    linhas que precisam (razão ≥ corte ou exclusiva), até `max_zh_pages_per_card`."""
    stats = stats if stats is not None else Counter()
    today = today or datetime.utcnow().date()
    zh_pages = zh_pages or ZhPages(fetch, today, params, stats, log)
    q = discovery_query(card)
    before = ebay.calls
    try:
        listings = ebay.search(q, min_price=float(params["min_price_usd"]), limit=int(params["ebay_limit"]),
                               fixed_price_only=True, location_country=params.get("location_country") or None,
                               max_pages=1, graded_only=True)
    finally:
        stats["ebay_calls"] += ebay.calls - before
    stats["cards_scanned"] += 1
    stats["listings_fetched"] += len(listings)
    rows: list[dict] = []
    for lst in listings:
        g = grading.grade_from_title(lst.title)
        if not g.grade or g.grade.key != "PSA 10" or g.status != "graded":
            stats["skip_not_psa10"] += 1
            continue
        lang, lang_ev = chinese_language(lst.title)
        if lang is None:
            stats["skip_" + ("outro-idioma" if lang_ev.startswith("outro") else "sem-marcador")] += 1
            continue
        bad = lot_or_reject(lst.title)
        if bad:
            stats["skip_" + ("lote" if bad.startswith("lote") else "rejeitar")] += 1
            continue
        level = match_level(card, lst.title)
        if level is None:
            stats["skip_name_mismatch"] += 1
            continue
        if lst.price is None or lst.price < float(params["min_price_usd"]):
            stats["skip_below_floor"] += 1
            continue
        marker = exclusive_marker(lst.title)
        rows.append({
            "kind": KIND, "card": card.name, "set": card.set_name, "number": card.number, "group": card.group,
            "pokemon": card.pokemon, "rarity": card.rarity, "year": card.year, "pc_url": card.pc_url,
            "language": lang, "language_evidence": lang_ev, "match": level,
            "rarity_check": rarity_compatible(card.rarity, lst.title), "base_name": name_parts(card.name)[0],
            "exclusive": marker is not None, "exclusive_marker": marker,
            "listing": _listing_dict(lst), "zh_number": zh_number_from_title(lst.title),
            "zh_set_hint": zh_set_hint(lst.title), "en_ref": None, "ratio": None, "zh": None,
        })
    if not rows:
        return rows
    # referência EN (uma página por carta, só quando há linha)
    en = {"price": None, "n": 0, "window_days": None, "source": "sem-referencia", "url": card.pc_url}
    try:
        stats["pc_fetch"] += 1
        en = en_reference(card, fetch(card.pc_url), today)
    except pc_sales.PcError as exc:
        stats["pc_error"] += 1
        log(f"  AVISO: PriceCharting falhou para {card.name} #{card.number}: {exc}")
    stats["en_ref_" + en["source"]] += 1
    base, suffix = name_parts(card.name)
    budget = int(params["max_zh_pages_per_card"])
    used: set[tuple] = set()
    for r in rows:
        r["en_ref"] = None if r["exclusive"] else en
        price = r["listing"]["price"]
        if not r["exclusive"] and en["price"] and price:
            r["ratio"] = round(en["price"] / price, 2)
    # Páginas chinesas: pares ≥ corte primeiro (maior razão antes), depois as
    # exclusivas (mais baratas antes) — o teto por carta não pode ser comido pelas
    # dezenas de promos de um mesmo Pokémon.
    needing = [r for r in rows if r["exclusive"] or (r["ratio"] is not None and r["ratio"] >= float(params["min_ratio"]))]
    needing.sort(key=lambda r: (r["exclusive"], -(r["ratio"] or 0), r["listing"]["price"] or 0))
    for r in needing:
        num, den = zh_fraction_from_title(r["listing"]["title"])
        key = (num, r["zh_set_hint"] or "", den or "", frozenset(_title_variants(r["listing"]["title"])))
        if key in used or len(used) < budget:
            used.add(key)
            r["zh"] = zh_pages.lookup(base, suffix, num, r["zh_set_hint"], title=r["listing"]["title"], denominator=den)
        else:
            r["zh"] = {"status": "teto-de-paginas-por-carta", "url": ""}
            stats["zh_page_teto"] += 1
    for r in rows:
        r["zh_margin_pct"] = zh_margin_pct(r)
        r["lt"] = longterm(card.name, card.rarity or r["listing"]["title"], r["zh"] if r["zh"] and r["zh"].get("status") == "ok" else None)
        r["bucket"], r["reasons"] = classify(r, params)
        stats["rows_" + r["bucket"]] += 1
    return rows


def run_scan(watchlist_path: str = "watchlist.yaml", group: str | None = None, max_cards: int | None = None,
             offset: int = 0, params: dict | None = None, log=print, ebay=None, fetch=pc_sales.fetch_page,
             today: date | None = None) -> dict:
    """Payload {'meta', 'rows'} com `meta.kind = KIND`. Aborta com `aborted=True`
    (e preserva o parcial) em falha de credencial/orçamento do eBay."""
    params = {**DEFAULT_PARAMS, **(params or {})}
    validate_batch_options(max_cards, offset)
    cards = scanner.filter_group(scanner.load_watchlist(watchlist_path), group) if group else scanner.load_watchlist(watchlist_path)
    scheduled, selection = select_batch(cards, max_cards, offset)
    stats: Counter = Counter()
    today = today or datetime.utcnow().date()
    ebay = ebay or EbayClient()
    aborted = False
    rows: list[dict] = []
    if not getattr(ebay, "configured", True):
        log("ERRO: EBAY_CLIENT_ID/EBAY_CLIENT_SECRET ausentes — nada coletado.")
        aborted = True
    else:
        ebay.max_calls = int(params["max_ebay_calls"])
        zh_pages = ZhPages(fetch, today, params, stats, log)
        for i, card in enumerate(scheduled, 1):
            log(f"[{i}/{len(scheduled)}] {card.name} #{card.number} ({card.set_name})")
            try:
                got = scan_card(card, ebay, params, fetch=fetch, today=today, stats=stats, log=log, zh_pages=zh_pages)
            except (EbayBudgetExceeded, EbayAuthError) as exc:
                log(f"ABORTADO: {exc}")
                stats["aborted_ebay"] += 1
                aborted = True
                break
            except EbayApiError as exc:
                stats["ebay_error"] += 1
                log(f"  AVISO: eBay falhou para {card.name}: {exc}")
                if stats["ebay_error"] >= 3:
                    aborted = True
                    break
                continue
            rows.extend(got)
            selection["cards_attempted"] = selection.get("cards_attempted", 0) + 1
            selection["cards_completed"] = selection.get("cards_completed", 0) + 1
    rows.sort(key=lambda r: (_bucket_rank(r["bucket"]), -(r.get("ratio") or 0), -(r.get("lt", {}).get("score") or 0), r["listing"]["price"] or 0))
    meta = {"kind": KIND, "policy_version": POLICY_VERSION, "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "group": group or "", "watchlist_count": len(cards), "scheduled": len(scheduled), "params": params,
            "funnel": dict(stats), "aborted": aborted, "selection": selection,
            "outlook_available": bool(_outlook())}
    return {"meta": meta, "rows": rows}


_BUCKET_ORDER = ("candidata", "validar", "abaixo-do-corte", "sem-referencia-en", "exclusiva")


def _bucket_rank(bucket: str) -> int:
    return _BUCKET_ORDER.index(bucket) if bucket in _BUCKET_ORDER else len(_BUCKET_ORDER)
