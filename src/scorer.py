"""O metodo de avaliacao -- transforma (anuncio + referencia) em veredito.

Padrao COMC (operador, 2026-09-03), regras canonicas:
- Tres metricas, nomeadas assim e so assim (nunca "lucro"):
    Desconto%  = (ref - preco) / ref   -> GATE ajustavel (`min_discount_percent`,
                                          inteiro; `--min-discount` por run)
    Spread$    = ref - preco           -> bruto, sem taxa nenhuma (frete a parte)
    ROI bruto% = (ref - preco) / preco -> `gross_margin_pct` (coluna; SUSPEITO acima
                                          de `suspicious_margin_percent`)
- Referencia de SLAB = mediana de vendas concluidas da MESMA carta, variante,
  certificadora, nota e subcategoria (PriceCharting, `src/pc_sales.py`):
  >=3 vendas em 180 d = OK; >=3 so em 365 d = OK + nota baixa-liquidez; 1-2 =
  REVISAR `vendas<3(n=…)`; 0 = sem referencia (nao vira linha; conta no funil).
  Coluna do PriceCharting e bucket generico ("Grade 9", "Grade 9.5") NUNCA sao
  referencia -- a coluna exata e so sanidade (`coluna÷vendas`).
- Raw NM (opt-in --include-raw) = TCGplayer market (tcgcsv); PriceCharting
  Ungraded e cross-check/fallback ROTULADO. Raw LP = so com LP EXPLICITO no
  titulo/condicao, pre-filtro `preco <= ref NM x (1 - desconto minimo)` e depois
  a SUA referencia (mediana de >=3 vendas LP). Nunca LP vs NM.
- Piso de preco, so item nos EUA, so PRECO FIXO (leilao nao entra).
- O scanner NUNCA recomenda compra. Veredito e classificacao tecnica.

Score (0-100, so ordenacao secundaria/auditoria): margem 45 / liquidez 25 /
tendencia 15 / risco 15. Ranking da entrega = ROI bruto -> desconto -> spread ->
popularidade do Pokemon (`src/report.py`).

Vereditos:
- REJEITADO: flag de rejeicao (proxy/replica/lote), fraude grade x condicao,
  idioma fora do escopo / nomenclatura JP numa watchlist EN.
- SUSPEITO: ROI bruto > `suspicious_margin_percent` (bom demais = golpe/carta
  errada) -- validar manualmente antes de qualquer acao.
- REVISAR: passou o gate mas tem ressalva (vendas<3, coluna÷vendas, referencia
  desalinhada/divergente, vendedor fraco, liquidez D...).
- OPORTUNIDADE: passou em tudo.

`stats` (Counter opcional) recebe o MOTIVO de cada anuncio que NAO vira linha
(funil da entrega): nada some em silencio.
"""
from . import grading, pc_sales, title_parser
from .models import Opportunity
from .report import compute_metrics

DEFAULT_CONFIG = {
    # Gate: Desconto% minimo, percentual INTEIRO (20 = 20%). Diagnostico do
    # operador: --min-discount 10 e depois ebay_summary.py --sensitivity 10,15,20.
    "min_discount_percent": 20,
    "min_price_usd": 10.0,
    "suspicious_margin_percent": 60,   # ROI bruto acima disto = SUSPEITO
    "weights": {"margin": 0.45, "liquidity": 0.25, "trend": 0.15, "risk": 0.15},
    # Entrega na COMC (Algona, WA, EUA): so item localizado nos EUA.
    "required_location_country": "US",
    # Decisao do operador 2026-09-03: so preco fixo (lance de leilao nao e preco).
    "fixed_price_only": True,
    # Decisao do operador 2026-06-10: so graded por default; raw entra por run
    # (--include-raw): NM = TCG market; LP = mediana de vendas LP.
    "graded_only": True,
    "lp_with_reference": True,
    # Allowlist de notas (chaves do grading.py); editavel no config.yaml.
    "graded_allow": grading.DEFAULT_GRADED_ALLOW,
    # Modo confiavel (--confiavel): so anuncios "compraveis de verdade".
    "trusted_mode": False,
    "trusted_min_feedback": 50,
    "trusted_min_feedback_pct": 98.0,
}

# Cross-check RAW: PriceCharting Ungraded vs TCGplayer market divergindo mais que
# isto (fracao do TCG market) -> referencia em duvida -> flag + no maximo REVISAR.
RAW_REF_DIVERGENCE = 0.40
# Coluna exata do PriceCharting (informativa) mais longe que isto da mediana de
# vendas -> sanidade falhou -> REVISAR `coluna÷vendas`.
COLUMN_DEVIATION_MAX = 0.30
MIN_COMPARABLE_SALES = pc_sales.MIN_COMPARABLE_SALES

# Contado pelo scanner DEPOIS da anotacao de referencia (veredito final).
VERDICT_STAT = {"OPORTUNIDADE": "rows_opportunity", "REVISAR": "rows_review",
                "SUSPEITO": "rows_suspect", "REJEITADO": "rows_rejected"}


def _skip(stats, key):
    """Registra no funil por que o anuncio NAO virou linha; devolve None."""
    if stats is not None:
        stats[key] += 1
    return None


def trust_score(listing):
    """Confiabilidade do anuncio (0-100), SEPARADA da margem.

    Mede 'de quem estou comprando e quem garante', nao 'quanto desconto':
    historico do vendedor + selos estruturais do eBay (Authenticity
    Guarantee, Top Rated). Margem gigante nao melhora este score.
    """
    n = listing.seller_feedback_score
    pct = listing.seller_feedback_pct
    if n < 50:
        pts = 10.0
    elif n < 100:
        pts = 35.0
    elif n < 1000:
        pts = 60.0
    else:
        pts = 75.0
    if pct >= 99.5:
        pts += 10
    elif pct >= 99.0:
        pts += 5
    elif pct and pct < 98.0:
        pts -= 25
    if listing.top_rated:
        pts += 10
    if listing.authenticity_guarantee:
        pts += 15
    if listing.buying_option == "AUCTION":
        pts -= 10
    return max(0.0, min(100.0, pts))


def liquidity_tier(sales_per_month):
    if sales_per_month >= 10:
        return "A"
    if sales_per_month >= 3:
        return "B"
    if sales_per_month >= 1:
        return "C"
    return "D"


def _tier_from_ref(ref):
    """Liquidez de uma referencia por vendas: 'ok' com >=10 vendas na janela = A,
    'ok' = B, 'low' (>=3 so em 365 d) = C, 'thin' (1-2) = D."""
    if ref.liquidity == "ok":
        return "A" if (ref.n_sales or 0) >= 10 else "B"
    if ref.liquidity == "low":
        return "C"
    return "D"


def _margin_points(margin_pct, threshold):
    if margin_pct <= threshold:
        return max(0.0, margin_pct / threshold * 50.0) if threshold else 50.0
    # threshold -> 50 pts ... 100% -> 100 pts
    return min(100.0, 50.0 + (margin_pct - threshold) / (100.0 - threshold) * 50.0)


def _trend_points(delta):
    if delta > 0:
        return 100.0
    if delta < 0:
        return 20.0
    return 60.0


def _grade_gate(cfg, listing, allow, stats):
    """Classifica a nota do titulo. Devolve (grade_key, grade_obj) ou None (ja
    contado no funil)."""
    gr = grading.grade_from_title(listing.title, allow)
    allowed = cfg.get("allowed_grades") or []
    if gr.status == "raw":
        if cfg.get("graded_only"):
            return _skip(stats, "skip_raw")
        if allowed and "RAW" not in allowed:
            return _skip(stats, "skip_grade_filtered")
        return "RAW", None
    if gr.status == "graded":
        # Funil restrito por run (--grades): nota conhecida fora da lista sai em
        # silencio -- e escopo pedido, nao rejeicao.
        if allowed and gr.grade.key not in allowed:
            return _skip(stats, "skip_grade_filtered")
        return gr.grade.key, gr.grade
    if gr.status == "ambiguous":
        # Titulo cita mais de uma nota ("BGS 8.5 ... PSA 9" = hype): sem nota
        # unica nao ha referencia comparavel -> fora, contado.
        return _skip(stats, "skip_grade_ambiguous")
    return _skip(stats, "skip_grade_out_of_scope")


def evaluate(card, listing, fair, config=None, tcg_ref=None, refs=None, stats=None):
    """Avalia um anuncio. Retorna Opportunity ou None (motivo em `stats`).

    `fair` (models.FairValue | None): colunas/tendencia/volume da pagina do
    PriceCharting -- so INFORMACAO e fallback raw rotulado; nunca referencia de
    slab. `tcg_ref` (TcgReference | None): market TCGplayer da carta raw EN.
    `refs` (scanner.CardRefs | None): mediana de vendas comparaveis da pagina
    (`refs.slab(grade, variants)` / `refs.lp(variants)`), `refs.available`
    False quando a fonte PriceCharting falhou para a carta.
    """
    cfg = dict(DEFAULT_CONFIG, **(config or {}))
    min_discount = float(cfg.get("min_discount_percent") or 0.0)
    suspicious = float(cfg["suspicious_margin_percent"])
    allow = frozenset(cfg.get("graded_allow") or grading.DEFAULT_GRADED_ALLOW)

    if cfg.get("fixed_price_only", True) and listing.buying_option != "FIXED_PRICE":
        return _skip(stats, "skip_not_fixed_price")
    if listing.price <= 0 or listing.price < float(cfg["min_price_usd"]):
        return _skip(stats, "skip_price_floor")
    required_country = cfg.get("required_location_country")
    if required_country and listing.country and listing.country != required_country:
        return _skip(stats, "skip_country")
    if not title_parser.card_matches_title(card, listing.title):
        return _skip(stats, "skip_no_match")

    gate = _grade_gate(cfg, listing, allow, stats)
    if gate is None:
        return None
    grade, grade_obj = gate

    flags = title_parser.risk_flags(listing.title, listing)
    reasons = []
    rejected = False

    lang = title_parser.detect_language(listing.title)
    if lang == "OTHER":
        flags.append("IDIOMA: fora do escopo (so EN e JP)")
        rejected = True
    elif lang != card.language:
        flags.append(f"IDIOMA: anuncio parece {lang}, watchlist espera {card.language}")
    elif card.language == "EN" and title_parser.jp_nomenclature_hint(listing.title):
        # Caso real 2026-09-01 (Alakazam ex 201 "SAR"): carta JP sem a palavra
        # "japanese" casava com a referencia EN. Prefixo REJEITAR tambem tira a
        # linha da mediana de mercado.
        flags.append("REJEITAR IDIOMA: nomenclatura japonesa no titulo "
                     "(SAR/CHR/CSR ou codigo de set JP) sem 'English' -- "
                     "provavel versao JP; a referencia e da carta EN, a "
                     "margem sairia de produto errado")
        rejected = True

    cond = (listing.condition or "").lower()
    condition = ""
    if grade == "RAW":
        if title_parser.is_nm_acceptable(listing.title, listing.condition):
            condition = "NM"
        elif cfg.get("lp_with_reference", True) and \
                title_parser.is_lp(listing.title, listing.condition):
            condition = "LP"
        else:
            # Raw sem NM explicito (e sem LP explicito): fora, contado. Nunca
            # "NM/LP", nunca condicao ausente.
            return _skip(stats, "skip_condition")
        if "graded" in cond and "ungraded" not in cond:
            flags.append("CONDICAO: campo eBay diz 'Graded' mas o titulo nao traz "
                         "nota -- identidade da carta incerta")
            rejected = True
    elif "ungraded" in cond:
        # Fraude classica do eBay: titulo anuncia "PSA 10" mas o campo de condicao
        # do proprio eBay diz "Ungraded" (carta crua). Caso real 2026-06-10.
        flags.append(f"FRAUDE PROVAVEL: titulo anuncia {grade_obj.label} mas o campo "
                     "condicao do eBay diz UNGRADED (carta crua)")
        rejected = True

    if any(f.startswith("REJEITAR") or f.startswith("LOTE") for f in flags):
        rejected = True

    # ------------------------------------------------------------------ referencia
    variants = pc_sales.variant_tokens(listing.title)
    # O market do TCGplayer tem de ser o do MESMO subtype da listagem: reverse holo
    # tem preco proprio (diagnostico 2026-09-04 -- 37 linhas OPORTUNIDADE eram reverse
    # medidas contra o preco da versao normal). Sem subtype que case: sem referencia.
    tcg_market, tcg_sub = (tcg_ref.market_for(variants) if tcg_ref else (None, ""))
    prices = fair.prices if fair is not None else {}
    deltas = fair.deltas if fair is not None else {}
    volume = fair.sales_per_month if fair is not None else {}
    ref_flags = []
    ref_demote = False
    ref_source = ""
    ref_label = ""
    ref_n = None
    ref_liq = ""
    ref_window = None
    ref_column = None
    delta = 0.0
    liquidity_sales = 0.0

    if grade != "RAW":
        if refs is None or not refs.available:
            return _skip(stats, "ref_unavailable")
        ref = refs.slab(grade_obj, variants)
        if ref is None:
            return _skip(stats, "slab_no_reference")
        fair_price = ref.price
        ref_source = "pricecharting-sales"
        ref_label = ref.label
        ref_n, ref_liq, ref_window, ref_column = (ref.n_sales, ref.liquidity,
                                                  ref.window_days, ref.column_price)
        if ref_n is not None and ref_n < MIN_COMPARABLE_SALES:
            reasons.append(f"vendas<{MIN_COMPARABLE_SALES}(n={ref_n})")
        if ref_column and fair_price > 0 and \
                abs(ref_column - fair_price) / fair_price > COLUMN_DEVIATION_MAX:
            reasons.append(f"coluna÷vendas({ref_column:.2f})")
        if tcg_market and fair_price < tcg_market:
            ref_flags.append(
                f"REF GRADED < RAW TCG (defasada?): mediana {grade_obj.label} "
                f"${fair_price:,.2f} abaixo do market raw TCGplayer "
                f"${tcg_market:,.2f} -- referencia graded provavelmente stale")
            ref_demote = True
        column_key = grading.pc_price_key(grade_obj)
        if column_key:
            delta = deltas.get(column_key, 0.0)
            liquidity_sales = volume.get(column_key, 0.0)
        tier = _tier_from_ref(ref)
    elif condition == "NM":
        pc_raw = prices.get("RAW")
        if "reverse" in variants and not tcg_market:
            # Sem market do subtype Reverse Holofoil nao ha referencia: o Ungraded do
            # PriceCharting e da versao NORMAL, nunca serve de comparavel do reverse.
            return _skip(stats, "raw_variant_no_reference")
        if tcg_market:
            fair_price = tcg_market
            ref_source = "tcgplayer"
            ref_label = ("TCG market (Reverse Holofoil)"
                         if tcg_sub == "Reverse Holofoil" else "TCG market")
            if pc_raw and abs(pc_raw - tcg_market) / tcg_market > RAW_REF_DIVERGENCE:
                ref_flags.append(
                    f"REF RAW DIVERGENTE (PC vs TCG): PriceCharting "
                    f"${pc_raw:,.2f} vs TCGplayer ${tcg_market:,.2f} "
                    f"(> {RAW_REF_DIVERGENCE:.0%}) -- validar a referencia "
                    "antes de confiar na margem")
                ref_demote = True
        elif pc_raw:
            fair_price = pc_raw
            ref_source = "pricecharting"
            ref_label = "PC Ungraded (sem TCG)"
            ref_flags.append(
                "REF: PriceCharting (sem TCG) -- sem market TCGplayer para "
                "esta carta; referencia raw e o Ungraded do PriceCharting")
        else:
            return _skip(stats, "raw_no_reference")
        liquidity_sales = volume.get("RAW", 0.0)
        delta = deltas.get("RAW", 0.0)
        tier = liquidity_tier(liquidity_sales)
    else:  # raw LP: pre-filtro pela referencia NM, depois a SUA referencia (vendas LP)
        nm_ref = tcg_market or prices.get("RAW")
        if nm_ref:
            cap = nm_ref * (1.0 - min_discount / 100.0)
            if listing.price > cap:
                return _skip(stats, "lp_prefilter")
        elif stats is not None:
            stats["lp_no_nm_prefilter"] += 1  # sem teto NM: vai direto as vendas LP
        if refs is None or not refs.available:
            return _skip(stats, "ref_unavailable")
        ref = refs.lp(variants)
        if ref is None:
            return _skip(stats, "lp_no_reference")
        fair_price = ref.price
        ref_source = "pricecharting-sales-lp"
        ref_label = ref.label
        ref_n, ref_liq, ref_window = ref.n_sales, ref.liquidity, ref.window_days
        tier = _tier_from_ref(ref)

    discount_pct, roi_pct, spread_usd = compute_metrics(fair_price, listing.price)
    if discount_pct < min_discount:
        # Abaixo do gate nao interessa -- nem como linha rejeitada (senao a tabela
        # afoga em rejeitados de desconto negativo).
        return _skip(stats, "below_discount")

    if cfg.get("trusted_mode"):
        # Modo confiavel: so o que e compravel de verdade.
        if (listing.seller_feedback_score < int(cfg["trusted_min_feedback"])
                or listing.seller_feedback_pct < float(cfg["trusted_min_feedback_pct"])):
            return _skip(stats, "trusted_filtered")
        if roi_pct > suspicious:
            return _skip(stats, "trusted_filtered")
        if rejected:
            return _skip(stats, "trusted_filtered")

    raw_price = prices.get("RAW") or 0.0
    spread9 = spread10 = 0.0
    if grade == "RAW" and raw_price:
        psa9, psa10 = prices.get("PSA 9"), prices.get("PSA 10")
        spread9 = ((psa9 - raw_price) / raw_price * 100.0) if psa9 else 0.0
        spread10 = ((psa10 - raw_price) / raw_price * 100.0) if psa10 else 0.0

    w = cfg["weights"]
    risk_points = max(0.0, 100.0 - 35.0 * len(flags))
    liq_points = {"A": 100.0, "B": 75.0, "C": 45.0, "D": 15.0}[tier]
    score = (
        w["margin"] * _margin_points(roi_pct, max(min_discount, 1.0))
        + w["liquidity"] * liq_points
        + w["trend"] * _trend_points(delta)
        + w["risk"] * risk_points
    )

    if rejected:
        verdict = "REJEITADO"
        score = 0.0  # rejeitado nao compete no ranking; fica na tabela propria
    elif roi_pct > suspicious:
        verdict = "SUSPEITO"
        flags.append(
            f"MARGEM: ROI bruto {roi_pct:.0f}% acima do normal -- conferir se a "
            "carta/nota e mesmo a esperada antes de qualquer acao")
    elif tier == "D" and grade == "RAW":
        verdict = "REVISAR"
        flags.append("LIQUIDEZ: menos de 1 venda/mes nessa condicao (dificil revender)")
    elif flags or reasons:
        verdict = "REVISAR"
    else:
        verdict = "OPORTUNIDADE"

    # Flags de referencia entram DEPOIS do score (informativas, nao penalizam
    # risco); rebaixamento explicito quando a referencia esta em duvida.
    flags.extend(ref_flags)
    if ref_demote:
        reasons.append("ref-divergente")
        if verdict == "OPORTUNIDADE":
            verdict = "REVISAR"

    grade_label = grade_obj.label if grade_obj else "RAW"
    pc_url = (refs.pc_url if refs is not None and getattr(refs, "pc_url", "") else "") \
        or card.pc_url
    return Opportunity(
        card=card, listing=listing, grade=grade, fair_value=fair_price,
        gross_margin_pct=roi_pct, liquidity_per_month=liquidity_sales,
        liquidity_tier=tier, trend_delta=delta,
        spread_psa9_pct=round(spread9, 0), spread_psa10_pct=round(spread10, 0),
        risk_flags=flags, score=round(score, 1), verdict=verdict,
        fair_value_source=card.pc_url,
        trust_score=round(trust_score(listing), 0),
        tcg_market=tcg_market,
        tcg_url=(tcg_ref.product_url if tcg_ref else ""),
        ref_kind=("tcgplayer" if ref_source == "tcgplayer" else "pricecharting"),
        discount_pct=discount_pct, spread_usd=spread_usd,
        ref_source=ref_source, ref_label=ref_label, ref_n_sales=ref_n,
        ref_liquidity=ref_liq, ref_window_days=ref_window, ref_column_price=ref_column,
        condition=condition, grade_label=grade_label,
        listing_type=(f"Raw {condition}" if grade == "RAW" else grade_label),
        pc_url=pc_url, reasons=reasons,
    )
