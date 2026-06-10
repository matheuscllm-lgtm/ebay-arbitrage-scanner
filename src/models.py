"""Modelos de dados do scanner.

Termos:
- "raw" / "ungraded" = carta solta, sem nota de empresa de avaliacao (PSA/BGS/CGC).
- "graded" = carta lacrada em case com nota (ex.: PSA 10).
- "fair value" = preco justo de mercado, derivado de vendas reais (PriceCharting,
  que agrega os sold listings do eBay).
"""
from dataclasses import dataclass, field


# Grades aceitas pelo escopo do projeto (escopo fixo do operador).
ACCEPTED_GRADES = (
    "RAW",       # ungraded, somente Near Mint
    "PSA 10",
    "PSA 9",
    "BGS 10",
    "BGS 9.5",
    "CGC 10",
    "CGC 9.5",
)


@dataclass
class WatchCard:
    """Uma carta-alvo da watchlist."""
    name: str                 # ex.: "Charizard"
    set_name: str             # ex.: "Base Set"
    number: str               # ex.: "4"
    language: str             # "EN" ou "JP"
    pc_url: str               # URL do produto no PriceCharting (fonte do preco justo)
    ebay_query: str = ""      # query base no eBay; vazio = gerada automaticamente
    # Palavras que indicam OUTRO produto parecido (ex.: reimpressao Celebrations
    # do Charizard Base Set). Titulo contendo qualquer uma = nao e esta carta.
    exclude_keywords: list = field(default_factory=list)

    def default_query(self) -> str:
        return self.ebay_query or f"pokemon {self.name} {self.number} {self.set_name}"


@dataclass
class FairValue:
    """Precos justos por grade + liquidez, vindos do PriceCharting."""
    prices: dict = field(default_factory=dict)        # grade -> preco USD (float)
    deltas: dict = field(default_factory=dict)        # grade -> variacao recente USD (tendencia)
    sales_per_month: dict = field(default_factory=dict)  # grade -> vendas/mes (float)
    source_url: str = ""

    def price(self, grade: str):
        return self.prices.get(grade)


@dataclass
class Listing:
    """Um anuncio ativo no eBay."""
    item_id: str
    title: str
    price: float              # preco do item em USD (sem frete)
    shipping: float           # frete em USD (0.0 se gratis/desconhecido)
    currency: str
    buying_option: str        # FIXED_PRICE ou AUCTION
    condition: str            # texto de condicao do eBay (pode ser vazio)
    seller_feedback_pct: float
    seller_feedback_score: int
    url: str
    image_url: str = ""
    # Protecoes estruturais do eBay:
    # - Authenticity Guarantee: cartas >$250 (EUA) passam por autenticacao
    #   fisica (CGC/PSA) antes de chegar ao comprador.
    # - Top Rated: selo do eBay p/ vendedor com historico + devolucao 30d.
    authenticity_guarantee: bool = False
    top_rated: bool = False
    country: str = ""         # pais onde o item esta (itemLocation.country)


@dataclass
class Opportunity:
    """Resultado avaliado: um anuncio comparado ao preco justo da grade."""
    card: WatchCard
    listing: Listing
    grade: str                # grade detectada no titulo (RAW, PSA 10, ...)
    fair_value: float         # preco justo para essa grade
    gross_margin_pct: float   # (fair - price) / price * 100  -- margem bruta, sem taxas
    liquidity_per_month: float
    liquidity_tier: str       # A / B / C / D
    trend_delta: float        # variacao recente do preco justo (USD)
    spread_psa9_pct: float    # quanto a PSA 9 vale acima do raw (%)  (so p/ RAW)
    spread_psa10_pct: float   # quanto a PSA 10 vale acima do raw (%) (so p/ RAW)
    risk_flags: list = field(default_factory=list)
    score: float = 0.0        # 0-100
    verdict: str = ""         # OPORTUNIDADE / REVISAR / SUSPEITO / REJEITADO
    fair_value_source: str = ""  # URL do PriceCharting (link de referencia)
    median_ask: float = 0.0   # mediana dos anuncios eBay da mesma grade (sanity check)
    trust_score: float = 0.0  # 0-100: confiabilidade do vendedor/anuncio (separado da margem)
