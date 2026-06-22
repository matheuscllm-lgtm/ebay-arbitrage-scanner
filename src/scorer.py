"""O metodo de avaliacao -- transforma (anuncio + preco justo) em veredito.

Regras canonicas do operador (cross-scanner):
- Margem BRUTA pura: (preco_justo - preco_do_anuncio) / preco_do_anuncio.
  ZERO taxas embutidas (sem fee, frete, cartao, IOF, FX) -- operador calcula
  taxas por fora. Frete aparece em coluna separada, informativo.
- Threshold de margem: 30% (inteiro percentual no config, sem pegadinha de fracao).
- Piso de preco: USD 10 (~R$50) -- carta abaixo disso nao vale o esforco.
- O scanner NUNCA recomenda compra. Veredito e classificacao tecnica;
  decisao de capital e do operador.

Componentes do score (0-100):
- Margem (peso 45): 30% de margem = 50 pts; 100%+ = 100 pts (linear no meio).
- Liquidez (peso 25): vendas/mes da grade no PriceCharting.
    Tier A >= 10/mes (100 pts) | B >= 3 (75) | C >= 1 (45) | D < 1 (15).
- Tendencia (peso 15): variacao recente do preco justo (delta PriceCharting).
    Subindo = 100, estavel = 60, caindo = 20.
- Risco (peso 15): comeca em 100, cada flag tira 35 pts (minimo 0).

Vereditos:
- REJEITADO: flag de rejeicao (proxy/replica/lote), grade fora do escopo,
  raw sem NM confirmado, ou idioma fora do escopo.
- SUSPEITO: margem > 60% (bom demais costuma ser scam/carta errada) ou
  vendedor de risco alto. Validar manualmente antes de qualquer acao.
- OPORTUNIDADE: margem >= threshold, liquidez tier A-C, sem flag grave.
- REVISAR: o resto que passou do threshold mas tem alguma ressalva.
"""
from .models import Opportunity
from . import title_parser

DEFAULT_CONFIG = {
    "min_gross_margin_percent": 30,   # percentual INTEIRO (30 = 30%)
    "min_price_usd": 10.0,
    "suspicious_margin_percent": 60,
    "weights": {"margin": 0.45, "liquidity": 0.25, "trend": 0.15, "risk": 0.15},
    # Entrega na COMC (Algona, WA, EUA): so item localizado nos EUA.
    "required_location_country": "US",
    # Decisao do operador 2026-06-10: scanner e SO para graded cards
    # (PSA 9/10, BGS 9.5/10, CGC 9.5/10). Raw fica fora do funil -- a nota
    # de terceiro e verificavel (cert lookup); condicao de raw nao e.
    "graded_only": True,
    # Modo confiavel (--confiavel): so anuncios "compraveis de verdade".
    "trusted_mode": False,
    "trusted_min_feedback": 50,       # vendedor com >= 50 transacoes
    "trusted_min_feedback_pct": 98.0, # e >= 98% de feedback positivo
}


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


def _margin_points(margin_pct, threshold):
    if margin_pct <= threshold:
        return max(0.0, margin_pct / threshold * 50.0)
    # 30% -> 50 pts ... 100% -> 100 pts
    return min(100.0, 50.0 + (margin_pct - threshold) / (100.0 - threshold) * 50.0)


def _trend_points(delta):
    if delta > 0:
        return 100.0
    if delta < 0:
        return 20.0
    return 60.0


def evaluate(card, listing, fair, config=None):
    """Avalia um anuncio contra o preco justo. Retorna Opportunity ou None.

    None = nem vale linha na tabela (carta nao casa, abaixo do piso, etc).
    """
    cfg = dict(DEFAULT_CONFIG, **(config or {}))
    threshold = float(cfg["min_gross_margin_percent"])

    if listing.price < float(cfg["min_price_usd"]):
        return None
    # Localizacao: entrega e na COMC (EUA) -- item fora dos EUA nao serve
    # (a API ja filtra server-side; isto e o cinto de seguranca).
    required_country = cfg.get("required_location_country")
    if required_country and listing.country and listing.country != required_country:
        return None
    if not title_parser.card_matches_title(card, listing.title):
        return None

    grade = title_parser.detect_grade(listing.title)
    if cfg.get("graded_only") and grade == "RAW":
        return None  # escopo atual: so graded (PSA 9/10, BGS 9.5/10, CGC 9.5/10)

    flags = title_parser.risk_flags(listing.title, listing)
    rejected = False

    if grade is None:
        grade = "FORA DO ESCOPO"
        flags.append("GRADE: empresa/nota fora do escopo (so PSA 9/10, BGS 9.5/10, CGC 9.5/10)")
        rejected = True
    elif title_parser.grade_is_ambiguous(listing.title, grade):
        flags.append("GRADE AMBIGUA: titulo menciona mais de uma nota -- "
                     "provavel hype do vendedor, conferir foto do slab")
        rejected = True

    lang = title_parser.detect_language(listing.title)
    if lang == "OTHER":
        flags.append("IDIOMA: fora do escopo (so EN e JP)")
        rejected = True
    elif lang != card.language:
        flags.append(f"IDIOMA: anuncio parece {lang}, watchlist espera {card.language}")

    if grade == "RAW" and not title_parser.is_nm_acceptable(listing.title, listing.condition):
        flags.append("CONDICAO: raw sem NM confirmado (invariante: raw so Near Mint)")
        rejected = True

    # Fraude classica do eBay: titulo anuncia "PSA 10" mas o campo de condicao
    # do proprio eBay diz "Ungraded" (carta crua). Caso real: Moonbreon "PSA 10"
    # a $1.800, vendedor 0 feedback, Estado = "Nao classificado" (2026-06-10).
    cond = (listing.condition or "").lower()
    if grade != "RAW" and "ungraded" in cond:
        flags.append(f"FRAUDE PROVAVEL: titulo anuncia {grade} mas o campo "
                     "condicao do eBay diz UNGRADED (carta crua)")
        rejected = True
    elif grade == "RAW" and "graded" in cond and "ungraded" not in cond:
        flags.append("CONDICAO: campo eBay diz 'Graded' mas o titulo nao traz "
                     "nota -- identidade da carta incerta")
        rejected = True

    if any(f.startswith("REJEITAR") or f.startswith("LOTE") for f in flags):
        rejected = True

    fair_price = fair.price(grade)
    if not fair_price:
        return None  # sem preco justo para essa grade, nao da pra avaliar

    margin_pct = (fair_price - listing.price) / listing.price * 100.0
    if margin_pct < threshold:
        # Abaixo do threshold nao interessa -- nem como linha rejeitada
        # (senao a tabela afoga em rejeitados de margem negativa).
        return None

    if cfg.get("trusted_mode"):
        # Modo confiavel: so o que e compravel de verdade.
        # 1) Vendedor com historico real (golpista nao tem 50 avaliacoes a 98%).
        if (listing.seller_feedback_score < int(cfg["trusted_min_feedback"])
                or listing.seller_feedback_pct < float(cfg["trusted_min_feedback_pct"])):
            return None
        # 2) Faixa de margem saudavel: desconto acima do limite de suspeita e
        #    quase sempre golpe/carta errada -- fora do modo confiavel.
        if margin_pct > float(cfg["suspicious_margin_percent"]):
            return None
        # 3) Nada de linha rejeitada: a tabela confiavel e 100% acionavel.
        if rejected:
            return None

    sales = fair.sales_per_month.get(grade, 0.0)
    tier = liquidity_tier(sales)
    delta = fair.deltas.get(grade, 0.0)

    raw_price = fair.price("RAW") or 0.0
    spread9 = spread10 = 0.0
    if grade == "RAW" and raw_price:
        psa9, psa10 = fair.price("PSA 9"), fair.price("PSA 10")
        spread9 = ((psa9 - raw_price) / raw_price * 100.0) if psa9 else 0.0
        spread10 = ((psa10 - raw_price) / raw_price * 100.0) if psa10 else 0.0

    w = cfg["weights"]
    risk_points = max(0.0, 100.0 - 35.0 * len(flags))
    liq_points = {"A": 100.0, "B": 75.0, "C": 45.0, "D": 15.0}[tier]
    score = (
        w["margin"] * _margin_points(margin_pct, threshold)
        + w["liquidity"] * liq_points
        + w["trend"] * _trend_points(delta)
        + w["risk"] * risk_points
    )

    if rejected:
        verdict = "REJEITADO"
        score = 0.0  # rejeitado nao compete no ranking; fica no fim da tabela
    elif margin_pct > float(cfg["suspicious_margin_percent"]):
        verdict = "SUSPEITO"
        flags.append(
            f"MARGEM: {margin_pct:.0f}% acima do normal -- conferir se a carta/grade "
            "e mesmo a esperada antes de qualquer acao"
        )
    elif tier == "D":
        verdict = "REVISAR"
        flags.append("LIQUIDEZ: menos de 1 venda/mes nessa grade (dificil revender)")
    elif flags:
        verdict = "REVISAR"
    else:
        verdict = "OPORTUNIDADE"

    return Opportunity(
        card=card, listing=listing, grade=grade, fair_value=fair_price,
        gross_margin_pct=round(margin_pct, 1), liquidity_per_month=sales,
        liquidity_tier=tier, trend_delta=delta,
        spread_psa9_pct=round(spread9, 0), spread_psa10_pct=round(spread10, 0),
        risk_flags=flags, score=round(score, 1), verdict=verdict,
        trust_score=round(trust_score(listing), 0),
    )
