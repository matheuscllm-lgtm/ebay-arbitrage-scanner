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
    # Grupo logico da watchlist (ex.: "chase-en"); vazio = sem grupo.
    # Filtravel via `main.py --group <nome>`; `--list-groups` lista todos.
    group: str = ""
    # Override do nome do set no tcgcsv/TCGplayer quando o nome da watchlist
    # nao bate com o `name` dos groups do tcgcsv (ex.: set: "151" vs
    # tcgcsv "SV: Scarlet & Violet 151"). Vazio = usa `set` direto.
    tcg_set: str = ""
    # Padrão COMC (2026-09-03): Pokémon da carta e rank na lista dos 100 "chases"
    # (comc iconic_pokemon.csv) — usados na coluna Pokémon e no desempate do
    # ranking; rarity/year vêm do catálogo (build_watchlist.py), só informação.
    pokemon: str = ""
    pokemon_rank: int = 9999
    rarity: str = ""
    year: int | None = None

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
    vault_confirmed: bool | None = None  # only verified metadata, never inferred from title
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
    # Referencia TCGplayer (via tcgcsv.com) da carta RAW, quando disponivel.
    # Para listing RAW ela e a referencia PRINCIPAL da margem; para graded e
    # so sanity check (TCGplayer nao tem preco graded).
    tcg_market: float | None = None  # market price TCGplayer (USD) ou None
    tcg_url: str = ""         # URL do produto no TCGplayer (vinda do tcgcsv)
    # Qual fonte foi usada na MARGEM desta linha:
    # "tcgplayer" (raw com TCG market) ou "pricecharting" (graded, ou raw fallback).
    ref_kind: str = "pricecharting"
    # --- Padrão COMC (2026-09-03): métricas e proveniência da referência ---
    # Desconto% = (ref − preço)/ref; Spread$ = ref − preço; ROI bruto% = gross_margin_pct.
    discount_pct: float = 0.0
    spread_usd: float = 0.0
    # Fonte EXATA da referência: "tcgplayer" (raw NM, market) ·
    # "pricecharting-sales" (slab: mediana de vendas da mesma certificadora+nota+variante) ·
    # "pricecharting-sales-lp" (raw LP: mediana de ≥3 vendas LP) ·
    # "pricecharting" (fallback rotulado: coluna Ungraded do PC, raw sem TCG).
    ref_source: str = ""
    ref_label: str = ""        # "TCG market" · "vendas PSA 10 (n=5, 2026-03..2026-08)"
    ref_n_sales: int | None = None
    ref_liquidity: str = ""    # "ok" | "low" | "thin" (só mediana de vendas)
    ref_window_days: int | None = None
    ref_column_price: float | None = None  # coluna exata do PC — só sanidade coluna÷vendas
    condition: str = ""        # raw: "NM" | "LP"; slab: ""
    grade_label: str = ""      # "CGC 10 Gem Mint", "BGS 10 Black Label", "PSA 10"
    listing_type: str = ""     # "Raw NM" | "Raw LP" | grade_label
    pc_url: str = ""           # página da carta no PriceCharting (link [referência])
    reasons: list = field(default_factory=list)  # tags curtas do Status (vendas<3(n=1)…)


    strategy: dict = field(default_factory=dict)  # versioned EBAY PSA calculation/evidence
