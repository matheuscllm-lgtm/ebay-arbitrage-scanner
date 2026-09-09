"""Coluna informativa "Longo prazo" -- perfil da carta / fragilidade do dado.

Por anuncio, duas notas 0-100 e uma classe, so para LEITURA na tabela de entrega
(docs/LONGO_PRAZO.md):

- PERFIL = caracteristicas observadas da carta: personagem (B1), raridade (B2), tempo
  fora de impressao (B3), faixa de preco da coluna PSA 10 do PriceCharting (B4) e
  tendencia real das vendas (B5). Cada componente vale 0-20 pontos ou None (sem dado);
  PERFIL = pontos disponiveis / (20 x componentes disponiveis) x 100.
- FRAGILIDADE DO DADO = quao fragil e o dado que sustenta a linha: referencia com
  poucas vendas, PSA 10 pouco vendida, referencia desalinhada dos anuncios, reprint
  forte (reimpressao que aumenta a oferta), preco absoluto alto, vendedor fraco,
  tiragem (variante de impressao) ambigua, precos dispersos, referencia possivelmente
  defasada e concentracao de anuncios. Dez flags, cada uma com pontos ou None; soma
  com teto 100.
- Classe LP1-LP4 = faixa de qualidade/completude do perfil (forte / medio / fraco /
  fragil). `LP2*` = seria LP1, mas um insumo-chave da fragilidade estava em n/d
  ("classe limitada por dado ausente").

Regras fixas:
- Sem dado = None = "n/d" -- NUNCA zero. Componente ausente sai da soma e reduz a
  cobertura (`k/5`, `k/10`); PERFIL e n/d com menos de 3 de 5 fontes, FRAGILIDADE e
  n/d com menos de 3 de 10 (soma vazia nao e 0).
- `assess` e uma funcao PURA: le `card`, `listing`, `opp`, `fair`, `refs` e nunca os
  altera; `annotate` grava so os campos `longterm_*`/`trend_*` da Opportunity.
  Veredito, Desconto%, ROI bruto%, `risk_flags`, `reasons`, `strategy` e o ranking
  (`report.sort_key`) ficam intocados. A coluna nao e gate (filtro obrigatorio), nao
  e recomendacao, nao ordena a tabela.
- Nunca recomputa uma segunda referencia: le a que ja existe (`opp.ref_*`; no caminho
  da politica `opp.strategy['psa_evidence']`) e a cesta de vendas ja montada
  (`refs.sales_history`, so leitura) -- UMA leitura por avaliacao.
- A cesta de B5 (tendencia) NAO e sempre a cesta da referencia. No caminho LEGADO e a
  mesma (`refs.slab` sai da mesma `pc_sales.comparable_sales`) e o rotulo e
  `trend_source = "sales_history"`. No caminho da POLITICA (vigente) e uma cesta
  PROPRIA, mais frouxa: `refs.sales_history` usa a nota DO ANUNCIO e nao aplica os
  filtros extras de `slab_strategy.reference_sales` (nota PSA-equivalente, so
  `source == "ebay"`, id de venda numerico e unico, idioma da carta, sem lote/"best
  offer"/certificacao incerta). Por isso o rotulo la e
  `trend_source = "sales_history:cesta-propria"` -- e por isso B5 pode se apoiar em
  vendas que a politica descartou da referencia. Nada disso muda a referencia nem o
  veredito: B5 so entra no PERFIL, que e informativo.
- Limiares, pontos e bandas sao calibracao inicial, nao validada (`CALIBRATION_NOTE`):
  a regua foi trazida como ideia do repo pokemon-longterm-outlook, sem codigo copiado,
  e ainda nao foi medida contra o mercado real. Triagem descritiva, nao previsao.
- So biblioteca padrao do Python (stdlib) + modulos irmaos deste repo.
"""
from __future__ import annotations

import csv
import functools
import math
import re
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from . import grading, groups, pc_sales, scorer

CALIBRATION_NOTE = ("calibração inicial, não validada: limiares, pontos e bandas nunca "
                    "foram medidos contra o mercado real (1 snapshot, sem backtest)")

PROFILE_COMPONENTS = ("personagem", "raridade", "supply", "faixa-psa10", "tendencia")
FRAGILITY_FLAGS = ("ref-fragil", "psa10-iliquido", "ref-desalinhada", "reprint-forte",
                   "preco-absoluto-alto", "vendedor-fraco", "tiragem", "dispersao",
                   "ref-stale", "concentracao")
# Sem estes tres em dado, a classe nunca chega a LP1 (vira LP2*).
KEY_FRAGILITY_INPUTS = ("ref-fragil", "psa10-iliquido", "ref-desalinhada")

# Espelho do bloco `longterm:` do config.yaml (inteiros; percentuais 0-100).
DEFAULT_CONFIG = {
    "enabled": True,
    "lp1_min_profile": 70,
    "lp1_max_fragility": 30,
    "lp2_min_profile": 50,
    "lp2_max_fragility": 50,
    "lp4_max_profile": 30,
    "lp4_min_fragility": 70,
    "min_profile_sources": 3,
    "min_fragility_sources": 3,
    "concentration_min_listings": 4,
}

SIGNAL_KEYS = (
    "pokemon_rank", "iconic_score", "rarity_raw", "rarity_tier", "year", "age_years",
    "era", "heavy_reprint", "psa10_col", "raw_col", "psa10_sales_pm", "trend_source",
    "trend_12m_pct", "trend_36m_pct", "ref_liquidity", "ref_n_sales", "ref_window_days",
    "ref_source", "dispersion_pct", "dispersion_source", "ask_ratio", "ask_n",
    "listings_same_grade", "trust_score", "printing_tokens",
)

# --- calibracao inicial (hardcoded de proposito; ver CALIBRATION_NOTE) ------------
MAX_POINTS_PER_COMPONENT = 20
FRAGILITY_CAP = 100
LP1_MIN_PROFILE_COVERAGE = 4          # de 5 componentes
LP1_MIN_FRAGILITY_COVERAGE = 8        # de 10 flags -- mesma proporcao (80%) do piso acima
_RARITY_POINTS = {"special-illustration": 20, "illustration": 16, "hyper-secret": 14,
                  "ultra": 12, "holo-vintage": 12, "holo": 6, "outra": 4}
_REPRINT_SUPPLY_CAP = 8               # reprint forte: teto do B3
_PSA10_BANDS = ((15, 4), (45, 10), (120, 16), (360, 20), (900, 14))  # < limiar -> pontos
_PSA10_TOP_BAND_POINTS = 8            # coluna PSA 10 >= 900
_REF_FRAGILITY_POINTS = {"sem-vendas": 30, "thin": 30, "low": 15, "ok": 0}
_PSA10_ILLIQUID_LOW, _PSA10_ILLIQUID_MID = 1.0, 3.0   # fronteiras C/D e B/C de scorer.liquidity_tier
_PRICE_HIGH_USD, _PRICE_MID_USD = 900.0, 300.0
_DEFAULT_MAX_DISPERSION = 30          # = slab_strategy.evidence.max_dispersion_percent

_HEAVY_REPRINT_PREFIX = re.compile(r"^(?:SV|SWSH|ME):")   # set especial sem numero de era
_HEAVY_REPRINT_NAMES = ("paldean fates", "prismatic evolutions", "champion's path",
                        "shining fates", "crown zenith", "ascended heroes")
_HEAVY_151_RE = re.compile(r"\b151\b")
_CELEBRATIONS_RE = re.compile(r"\bcelebrations\b", re.I)
_CLASSIC_COLLECTION_RE = re.compile(r"\bclassic collection\b", re.I)
_ICONIC_PATH = Path(__file__).resolve().parent / "catalog" / "iconic_pokemon.csv"


@dataclass
class LongTerm:
    """Resultado de `assess` (nunca gravado direto na Opportunity; ver `annotate`)."""
    profile: float | None            # PERFIL 0-100 ou None (n/d)
    fragility: float | None          # FRAGILIDADE DO DADO 0-100 ou None (n/d)
    tier: str                        # "LP1".."LP4", "LP2*", "n/d"
    profile_coverage: tuple          # (disponiveis, 5)
    fragility_coverage: tuple        # (disponiveis, 10)
    reasons: list = field(default_factory=list)     # "LP:<flag>[(detalhe)]" / "LP:<nome>: n/d"
    signals: dict = field(default_factory=dict)     # insumos crus rotulados (proveniencia)
    profile_points: dict = field(default_factory=dict)    # componente -> pontos | None
    fragility_points: dict = field(default_factory=dict)  # flag -> pontos | None


# --- helpers ----------------------------------------------------------------------

def _today():
    return datetime.now(timezone.utc).date()


def _float_or_none(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _int_or_none(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _sale_date(sale):
    try:
        return date.fromisoformat(str(sale.get("date", ""))[:10])
    except (ValueError, AttributeError):
        return None


def _grade_from_key(key):
    """'PSA 10' / 'CGC 10 GEM' -> grading.Grade; 'RAW' e status crus -> None."""
    parts = str(key or "").split()
    if len(parts) < 2:
        return None
    try:
        value = float(parts[1])
    except ValueError:
        return None
    return grading.Grade(parts[0], value, parts[2] if len(parts) > 2 else "")


# --- B1 personagem ----------------------------------------------------------------

def character_points(rank):
    """Rank do Pokemon na lista dos 100 chases: 1-10 -> 20 · 11-25 -> 16 · 26-50 -> 12 ·
    51-100 -> 6 · sem rank (None, 0, 9999...) -> None."""
    r = _int_or_none(rank)
    if r is None or r < 1 or r > 100:
        return None
    if r <= 10:
        return 20
    if r <= 25:
        return 16
    if r <= 50:
        return 12
    return 6


@functools.lru_cache(maxsize=4)
def _iconic_scores_cached(path_text):
    out = {}
    try:
        with open(path_text, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                name = (row.get("pokemon") or "").strip().lower()
                score = _float_or_none(row.get("score"))
                if name and score is not None:
                    out[name] = score
    except OSError:
        return {}
    return out


def load_iconic_scores(path=None):
    """{pokemon minusculo: score} de `src/catalog/iconic_pokemon.csv`, lido em tempo de
    scan (a watchlist nao muda). Arquivo ausente -> {} (sinal fica None)."""
    return dict(_iconic_scores_cached(str(path or _ICONIC_PATH)))


# --- B2 raridade ------------------------------------------------------------------

def era_for_group(group):
    """Era do grupo canonico (src/groups.py): 'vintage' | 'middle' | 'recent'; grupo
    vazio ou nao numerico -> None (nunca digitada a mao)."""
    text = str(group or "").strip()
    if not text.isdigit():
        return None
    definition = groups.SCAN_GROUPS.get(int(text))
    return definition.era if definition else None


def rarity_tier(rarity, era):
    """Tier da raridade (texto cru do tcgcsv), testando do mais alto para o mais baixo
    por substring em minusculas; `ex`/`gx`/`v` so como palavra inteira. None se vazio."""
    text = str(rarity or "").strip().lower()
    if not text:
        return None

    def has(*subs):
        return any(s in text for s in subs)

    def word(*words):
        return any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)

    if has("special illustration", "alternate"):
        return "special-illustration"
    if has("illustration", "trainer gallery", "character"):
        return "illustration"
    if has("hyper", "secret", "rainbow", "shiny", "amazing", "radiant"):
        return "hyper-secret"
    if has("ultra", "vmax", "vstar", "lv.x", "prime", "legend", "prism",
           "classic collection") or word("ex", "gx", "v"):
        return "ultra"
    if has("holo"):
        return "holo-vintage" if era == "vintage" else "holo"
    return "outra"


def rarity_points(rarity, era):
    tier = rarity_tier(rarity, era)
    return None if tier is None else _RARITY_POINTS[tier]


# --- B3 supply --------------------------------------------------------------------

def is_heavy_reprint(set_name):
    """Reprint forte (ideia do outlook, sobre o nome do set VERBATIM do tcgcsv): comeca
    com `SV:`/`SWSH:`/`ME:` (set especial sem numero de era) OU contem Paldean Fates,
    Prismatic Evolutions, Champion's Path, Shining Fates, Crown Zenith, Ascended
    Heroes, "151" como palavra inteira, ou Celebrations -- exceto Classic Collection."""
    text = str(set_name or "").strip().replace("’", "'")
    if not text:
        return False
    if _HEAVY_REPRINT_PREFIX.match(text):
        return True
    low = text.lower()
    if any(name in low for name in _HEAVY_REPRINT_NAMES):
        return True
    if _HEAVY_151_RE.search(text):
        return True
    if _CELEBRATIONS_RE.search(text) and not _CLASSIC_COLLECTION_RE.search(text):
        return True
    return False


def supply_points(age_years, heavy_reprint):
    """Anos fora de impressao: >=10 -> 20 · 5-9 -> 16 · 3-4 -> 13 · 2 -> 10 · 1 -> 6 ·
    0 -> 3; reprint forte -> teto 8 (so rebaixa). Idade ausente/negativa -> None."""
    age = _int_or_none(age_years)
    if age is None or age < 0:
        return None
    if age >= 10:
        pts = 20
    elif age >= 5:
        pts = 16
    elif age >= 3:
        pts = 13
    elif age == 2:
        pts = 10
    elif age == 1:
        pts = 6
    else:
        pts = 3
    return min(pts, _REPRINT_SUPPLY_CAP) if heavy_reprint else pts


# --- B4 faixa de preco PSA 10 (coluna) --------------------------------------------

def psa10_band_points(column_price):
    """Coluna PSA 10 da carta (US$, so informacao): <15 -> 4 · 15-44 -> 10 · 45-119 ->
    16 · 120-359 -> 20 · 360-899 -> 14 · >=900 -> 8 · ausente/zero -> None."""
    price = _float_or_none(column_price)
    if price is None or price <= 0:
        return None
    for limit, pts in _PSA10_BANDS:
        if price < limit:
            return pts
    return _PSA10_TOP_BAND_POINTS


# --- B5 tendencia real ------------------------------------------------------------

def trend_points(pct):
    """Variacao em 12 m: >= +25% -> 20 · +8..+25 -> 16 · -8..+8 -> 10 · -25..-8 -> 5 ·
    <= -25% -> 2 · None -> None."""
    p = _float_or_none(pct)
    if p is None:
        return None
    if p >= 25:
        return 20
    if p >= 8:
        return 16
    if p >= -8:
        return 10
    if p > -25:
        return 5
    return 2


def trend_from_sales(sales, today):
    """Mediana das vendas da nota exata em 0-180 d vs 180-365 d (% com 1 casa), so com
    >=3 vendas em CADA janela; senao None. `sales` = cesta de `refs.sales_history`."""
    recent, older = [], []
    for sale in sales or []:
        day = _sale_date(sale)
        price = _float_or_none(sale.get("price"))
        if day is None or price is None or price <= 0:
            continue
        age = (today - day).days
        if age < 0:
            continue
        if age <= pc_sales.SALES_MAX_AGE_DAYS:
            recent.append(price)
        elif age <= pc_sales.SALES_LOW_LIQUIDITY_MAX_AGE_DAYS:
            older.append(price)
    if len(recent) < pc_sales.MIN_COMPARABLE_SALES or len(older) < pc_sales.MIN_COMPARABLE_SALES:
        return None
    now, then = statistics.median(recent), statistics.median(older)
    if then <= 0:
        return None
    return round((now - then) / then * 100.0, 1)


def _point_at(points, target, tolerance_days):
    """Ultimo ponto da serie com data <= `target`, a no maximo `tolerance_days` dela."""
    best = None
    for ts, value in points:
        day = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc).date()
        if day <= target:
            best = (day, value)
    if best is None or (target - best[0]).days > tolerance_days:
        return None
    return best[1]


def trend_from_history(series, today, months=12, tolerance_days=31):
    """Variacao % (2 casas) da serie mensal `VGPC.chart_data` entre "agora" (ultimo ponto
    <= hoje) e `months` meses atras (ultimo ponto <= hoje - months*365/12 dias), ambos
    a <= `tolerance_days` do alvo e ambos > 0 (0/None na serie = sem dado). Sem os dois
    pontos -> None."""
    if not series:
        return None
    points = sorted((int(ts), value) for ts, value in series)
    now_value = _point_at(points, today, tolerance_days)
    then_value = _point_at(points, today - timedelta(days=months * 365 // 12), tolerance_days)
    if not now_value or not then_value or now_value <= 0 or then_value <= 0:
        return None
    return round((now_value - then_value) / then_value * 100.0, 2)


# --- notas, classe ----------------------------------------------------------------

def profile_score(points, min_sources=3):
    """(PERFIL | None, (disponiveis, 5)): pontos disponiveis / (20 x disponiveis) x 100,
    1 casa; menos de `min_sources` componentes com dado -> None (nunca 0)."""
    available = [points.get(name) for name in PROFILE_COMPONENTS if points.get(name) is not None]
    coverage = (len(available), len(PROFILE_COMPONENTS))
    if len(available) < min_sources:
        return None, coverage
    score = sum(available) / (MAX_POINTS_PER_COMPONENT * len(available)) * 100.0
    return round(score, 1), coverage


def fragility_score(points, min_sources=3):
    """(FRAGILIDADE | None, (disponiveis, 10)): soma das flags com dado, teto 100; menos
    de `min_sources` fontes -> None (soma vazia nunca vira 0).

    LEIA JUNTO COM A COBERTURA: por ser uma SOMA, a nota mede os problemas DETECTADOS
    entre os testes que puderam rodar -- flag em n/d sai da soma, o que aritmeticamente
    e o mesmo que valer 0. Uma FRAGILIDADE 0 com cobertura 3/10 nao e "dado impecavel",
    e "so 3 dos 10 testes rodaram e nenhum acusou problema". Por isso a classe LP1 exige
    `LP1_MIN_FRAGILITY_COVERAGE` (ver `classify`)."""
    available = [points.get(name) for name in FRAGILITY_FLAGS if points.get(name) is not None]
    coverage = (len(available), len(FRAGILITY_FLAGS))
    if len(available) < min_sources:
        return None, coverage
    return float(min(FRAGILITY_CAP, sum(available))), coverage


def classify(profile, fragility, profile_coverage, key_inputs_available, cfg=None, *,
             fragility_coverage=None):
    """Classe, nesta ordem: n/d (nota ausente) -> LP4 (FRAGILIDADE > 70 ou PERFIL < 30)
    -> LP1 (PERFIL >= 70, FRAGILIDADE <= 30, cobertura do perfil >= 4/5, cobertura da
    fragilidade >= 8/10 e os 3 insumos-chave com dado; faltando insumo-chave OU
    cobertura de fragilidade -> LP2*) -> LP2 (PERFIL >= 50 e FRAGILIDADE <= 50) -> LP3.
    `cfg` = bloco `longterm` (limites inclusivos).

    O piso `LP1_MIN_FRAGILITY_COVERAGE` existe porque a FRAGILIDADE e uma SOMA: sem ele,
    uma linha em que 7 dos 10 testes nem puderam rodar sairia com nota 0 e classe LP1
    ("forte") igual a uma linha com os 10 testes limpos -- dado ausente parecendo dado
    impecavel (review do PR-C 2026-09-09). `fragility_coverage=None` (cobertura
    desconhecida, chamada antiga) nao aplica piso nenhum."""
    c = dict(DEFAULT_CONFIG, **(cfg or {}))
    if profile is None or fragility is None:
        return "n/d"
    if fragility > c["lp4_min_fragility"] or profile < c["lp4_max_profile"]:
        return "LP4"
    covered = int(profile_coverage[0]) if profile_coverage else 0
    frag_covered = int(fragility_coverage[0]) if fragility_coverage else None
    thin_fragility = (frag_covered is not None
                      and frag_covered < LP1_MIN_FRAGILITY_COVERAGE)
    if (profile >= c["lp1_min_profile"] and fragility <= c["lp1_max_fragility"]
            and covered >= LP1_MIN_PROFILE_COVERAGE):
        return "LP1" if (key_inputs_available and not thin_fragility) else "LP2*"
    if profile >= c["lp2_min_profile"] and fragility <= c["lp2_max_fragility"]:
        return "LP2"
    return "LP3"


def coverage_text(profile_coverage, fragility_coverage):
    """(4, 5), (8, 10) -> '4/5·8/10' (texto da celula e do JSON)."""
    return f"{profile_coverage[0]}/{profile_coverage[1]}·{fragility_coverage[0]}/{fragility_coverage[1]}"


# --- insumos da fragilidade -------------------------------------------------------

def _liquidity_from(n_sales, window_days):
    """Mesma regua de pc_sales.sales_reference: 1-2 vendas -> thin; >=3 so na janela de
    365 d -> low; senao ok. ZERO venda NAO e "thin" (que na regua do repo quer dizer
    "1-2 vendas em 365 d"): ganha rotulo proprio `sem-vendas`, com os mesmos pontos --
    dizer "poucas vendas" onde nao ha venda nenhuma e mentir para o operador (review do
    PR-C 2026-09-09). Caso real e comum no caminho da politica, que grava
    `opp.ref_n_sales = 0` sempre que nenhuma venda passa nos filtros da referencia."""
    if n_sales <= 0:
        return "sem-vendas"
    if n_sales < pc_sales.MIN_COMPARABLE_SALES:
        return "thin"
    if window_days > pc_sales.SALES_MAX_AGE_DAYS:
        return "low"
    return "ok"


def _reference_inputs(opp):
    """(liquidez, n vendas, janela, fonte) da referencia JA existente -- nunca recomputa.
    Caminho legado / `ref_*` preenchidos pela politica -> fonte 'ref_*'; `ref_*`
    vazios -> `opp.strategy['psa_evidence']` (n_used, window_days) -> 'psa_evidence';
    nada -> (None, None, None, None)."""
    liquidity = str(getattr(opp, "ref_liquidity", "") or "")
    n = _int_or_none(getattr(opp, "ref_n_sales", None))
    window = _int_or_none(getattr(opp, "ref_window_days", None))
    if n is not None and window is not None:
        if liquidity not in _REF_FRAGILITY_POINTS:
            liquidity = _liquidity_from(n, window)
        return liquidity, n, window, "ref_*"
    if liquidity in _REF_FRAGILITY_POINTS:
        return liquidity, n, window, "ref_*"
    evidence = (getattr(opp, "strategy", None) or {}).get("psa_evidence") or {}
    n = _int_or_none(evidence.get("n_used"))
    window = _int_or_none(evidence.get("window_days"))
    if n is not None and window is not None:
        return _liquidity_from(n, window), n, window, "psa_evidence"
    return None, None, None, None


def _exceeds_dispersion(rounded, exact_text, limit):
    """A dispersao passou do corte? Usa o valor EXATO quando ele existe
    (`psa_evidence['dispersion_exact']`, a string do Decimal que a POLITICA compara em
    `slab_strategy`), e so cai no arredondado da celula quando nao ha exato.

    Sem isso a coluna discordava da politica na fronteira: com dispersao real de
    30,004% a politica grava `PSA-precos-dispersos` (rebaixa a linha para REVISAR) e a
    coluna, comparando o arredondado 30,00, dizia que a dispersao estava sob controle --
    duas leituras do MESMO numero na mesma linha (review do PR-C 2026-09-09)."""
    try:
        if exact_text is not None:
            return Decimal(str(exact_text)) > Decimal(str(limit))
    except (InvalidOperation, TypeError, ValueError):
        pass
    return rounded > limit


def _dispersion_from_sales(sales, window_days, today):
    """MESMA formula da politica: (max - min) / mediana x 100 (2 casas) sobre as vendas
    da cesta dentro da janela da referencia, 10 mais recentes. Sem venda -> None."""
    cutoff = today - timedelta(days=int(window_days))
    inside = []
    for sale in sales or []:
        day = _sale_date(sale)
        price = _float_or_none(sale.get("price"))
        if day is None or price is None or price <= 0 or day < cutoff:
            continue
        inside.append((day, price))
    if not inside:
        return None
    prices = [price for _, price in sorted(inside, key=lambda p: p[0], reverse=True)[:pc_sales.SALES_WINDOW]]
    median = statistics.median(prices)
    if median <= 0:
        return None
    return round((max(prices) - min(prices)) / median * 100.0, 2)


def _trend(history, fair, grade_key, today, sales_label="sales_history"):
    """(12 m, 36 m, fonte): (ii) vendas da nota exata primeiro; senao (i) serie PSA 10
    do PriceCharting, rotulada proxy quando o anuncio nao e PSA 10; nada -> None.

    `sales_label` = rotulo honesto da cesta de (ii): "sales_history" so no caminho
    LEGADO, onde ela e a MESMA cesta que gera a referencia; no caminho da POLITICA e
    "sales_history:cesta-propria" (ver docstring do modulo)."""
    pct = trend_from_sales(history, today) if history else None
    if pct is not None:
        return pct, None, sales_label
    series = ((getattr(fair, "history", None) or {}).get("manualonly")) if fair is not None else None
    if series:
        pct = trend_from_history(series, today)
        pct_36 = trend_from_history(series, today, months=36)
        if pct is None:
            return None, pct_36, "chart_data:sem-dado"
        return pct, pct_36, ("chart_data" if grade_key == "PSA 10" else "chart_data:psa10-proxy")
    return None, None, None


# --- avaliacao --------------------------------------------------------------------

def assess(card, listing, opp, fair, refs, listings_same_grade, cfg=None, *,
           today=None, iconic_scores=None):
    """Avalia a coluna "Longo prazo" de UM anuncio ja avaliado (Opportunity), nos dois
    caminhos (legado e `slab_strategy`). Funcao pura: nao altera `opp` nem `refs`.

    `listings_same_grade` = anuncios da mesma carta+nota no run (contados pelo scanner
    ANTES do loop de avaliacao); `cfg` = config do run (bloco `longterm`, cortes de
    vendedor `trusted_min_feedback*`, `slab_strategy.evidence.max_dispersion_percent`).
    Devolve None com `longterm.enabled: false`. Limiares = CALIBRATION_NOTE."""
    cfg = cfg or {}
    lt_cfg = dict(DEFAULT_CONFIG, **(cfg.get("longterm") or {}))
    if not lt_cfg.get("enabled", True):
        return None
    today = today or _today()
    signals = {key: None for key in SIGNAL_KEYS}
    strategy = getattr(opp, "strategy", None) or {}
    risk_flags = [str(f) for f in (getattr(opp, "risk_flags", None) or [])]
    opp_reasons = [str(r) for r in (getattr(opp, "reasons", None) or [])]
    title = str(getattr(listing, "title", "") or "")
    set_name = str(getattr(card, "set_name", "") or "").strip()

    # --- PERFIL (B1-B5) ---
    rank = _int_or_none(getattr(card, "pokemon_rank", None))
    if iconic_scores is None:
        iconic_scores = load_iconic_scores()
    pokemon = str(getattr(card, "pokemon", "") or "").strip().lower()
    era = era_for_group(getattr(card, "group", ""))
    rarity = str(getattr(card, "rarity", "") or "")
    year = _int_or_none(getattr(card, "year", None))
    age_years = (today.year - year) if year is not None else None
    heavy = is_heavy_reprint(set_name) if set_name else None
    prices = (getattr(fair, "prices", None) or {}) if fair is not None else {}
    volume = (getattr(fair, "sales_per_month", None) or {}) if fair is not None else {}
    psa10_col = _float_or_none(prices.get("PSA 10"))
    psa10_pm = _float_or_none(volume.get("PSA 10"))

    grade_obj = _grade_from_key(getattr(opp, "grade", ""))
    variants = pc_sales.variant_tokens(title)
    history = None  # cesta da nota exata: UMA leitura, partilhada por B5 e `dispersao`
    if (grade_obj is not None and refs is not None and getattr(refs, "available", False)
            and hasattr(refs, "sales_history")):
        history = refs.sales_history(grade_obj, variants)
    # Rotulo honesto da cesta de B5: no caminho da POLITICA ela NAO e a cesta da
    # referencia (nota do anuncio, filtros mais frouxos) -- review do PR-C 2026-09-09.
    sales_label = "sales_history:cesta-propria" if strategy else "sales_history"
    trend_12, trend_36, trend_source = _trend(history, fair, getattr(opp, "grade", ""),
                                              today, sales_label)

    signals.update(
        pokemon_rank=rank, iconic_score=(iconic_scores.get(pokemon) if pokemon else None),
        rarity_raw=(rarity or None), rarity_tier=rarity_tier(rarity, era), year=year,
        age_years=age_years, era=era, heavy_reprint=heavy, psa10_col=psa10_col,
        raw_col=_float_or_none(prices.get("RAW")), psa10_sales_pm=psa10_pm,
        trend_source=trend_source, trend_12m_pct=trend_12, trend_36m_pct=trend_36,
    )
    profile_points = {
        "personagem": character_points(rank),
        "raridade": rarity_points(rarity, era),
        "supply": supply_points(age_years, bool(heavy)),
        "faixa-psa10": psa10_band_points(psa10_col),
        "tendencia": trend_points(trend_12),
    }

    # --- FRAGILIDADE DO DADO (10 flags) ---
    details = {}
    ref_liq, ref_n, ref_window, ref_source = _reference_inputs(opp)
    signals.update(ref_liquidity=ref_liq, ref_n_sales=ref_n, ref_window_days=ref_window,
                   ref_source=ref_source)
    ref_fragil = _REF_FRAGILITY_POINTS.get(ref_liq) if ref_liq else None
    if ref_fragil:
        details["ref-fragil"] = ref_liq

    if psa10_pm is None:
        psa10_illiquid = None
    elif psa10_pm < _PSA10_ILLIQUID_LOW:
        psa10_illiquid = 30
    elif psa10_pm < _PSA10_ILLIQUID_MID:
        psa10_illiquid = 20
    else:
        psa10_illiquid = 0
    if psa10_illiquid:
        details["psa10-iliquido"] = f"{psa10_pm:g}/mês"

    # `asks = {}` no caminho da politica (decisao documentada do operador): n/d, nada e
    # recomputado. Legado: flag existente de `scanner._annotate_ref_alignment`.
    ask_ratio = None
    if strategy:
        misaligned = None
    else:
        median_ask = _float_or_none(getattr(opp, "median_ask", None))
        fair_value = _float_or_none(getattr(opp, "fair_value", None))
        if median_ask and median_ask > 0 and fair_value:
            ask_ratio = round(fair_value / median_ask, 2)
        if any(f.startswith("REF DESALINHADA") for f in risk_flags):
            misaligned = 20
            details["ref-desalinhada"] = f"{ask_ratio:g}x" if ask_ratio else ""
        elif median_ask and median_ask > 0:
            misaligned = 0
        else:
            misaligned = None
    signals.update(ask_ratio=ask_ratio, ask_n=None)

    reprint = None if heavy is None else (15 if heavy else 0)

    price = _float_or_none(getattr(listing, "price", None))
    if price is None or price <= 0:
        price_high = None
    elif price >= _PRICE_HIGH_USD:
        price_high = 15
        details["preco-absoluto-alto"] = f"≥{_PRICE_HIGH_USD:g}"
    elif price >= _PRICE_MID_USD:
        price_high = 8
        details["preco-absoluto-alto"] = f"≥{_PRICE_MID_USD:g}"
    else:
        price_high = 0

    feedback = _float_or_none(getattr(listing, "seller_feedback_score", None))
    feedback_pct = _float_or_none(getattr(listing, "seller_feedback_pct", None))
    if feedback is None or feedback_pct is None:
        weak_seller = None
    else:
        # Corte JA documentado no repo (config.yaml `trusted_min_feedback` /
        # `trusted_min_feedback_pct`; politica: 'historico-do-vendedor-insuficiente').
        min_feedback = _float_or_none(cfg.get("trusted_min_feedback"))
        min_pct = _float_or_none(cfg.get("trusted_min_feedback_pct"))
        min_feedback = 50.0 if min_feedback is None else min_feedback
        min_pct = 98.0 if min_pct is None else min_pct
        weak_seller = 15 if (feedback < min_feedback or feedback_pct < min_pct) else 0

    low_title = title.lower()
    printing = sorted(t for t in pc_sales._PRINTING_TOKENS
                      if re.search(rf"\b{re.escape(t)}\b", low_title))
    subset = bool(set_name) and pc_sales._SUBSET_SUFFIX.search(set_name) is not None
    if printing or variants or subset:
        printing_flag = 10
        details["tiragem"] = ", ".join(printing or sorted(variants) or ["subconjunto"])
    else:
        printing_flag = 0

    if strategy:
        evidence = strategy.get("psa_evidence") or {}
        dispersion = _float_or_none(evidence.get("dispersion_percent")) if evidence else None
        # A politica compara o valor EXATO (`dispersion_exact`, Decimal); a celula mostra
        # o arredondado. Comparar o arredondado fazia a coluna discordar da politica na
        # fronteira (review do PR-C 2026-09-09).
        dispersion_exact = evidence.get("dispersion_exact") if evidence else None
        dispersion_source = "psa_evidence" if dispersion is not None else None
    else:
        dispersion = (_dispersion_from_sales(history, ref_window, today)
                      if history is not None and ref_window else None)
        dispersion_exact = None
        dispersion_source = "sales_history" if dispersion is not None else None
    max_dispersion = _float_or_none(((cfg.get("slab_strategy") or {}).get("evidence") or {})
                                    .get("max_dispersion_percent"))
    if max_dispersion is None:
        max_dispersion = float(_DEFAULT_MAX_DISPERSION)
    if dispersion is None:
        dispersed = None
    elif _exceeds_dispersion(dispersion, dispersion_exact, max_dispersion):
        dispersed = 10
        details["dispersao"] = f"{dispersion:g}%"
    else:
        dispersed = 0
    signals.update(dispersion_pct=dispersion, dispersion_source=dispersion_source)

    if strategy or _float_or_none(getattr(opp, "tcg_market", None)) is None:
        stale = None  # sem cross-check com o market raw TCGplayer nesse caminho
    elif any(f.startswith("REF GRADED < RAW TCG") for f in risk_flags) or "ref-divergente" in opp_reasons:
        stale = 10
    else:
        stale = 0

    same_grade = _int_or_none(listings_same_grade)
    if same_grade is None:
        concentration = None
    elif same_grade >= int(lt_cfg["concentration_min_listings"]):
        concentration = 10
        details["concentracao"] = str(same_grade)
    else:
        concentration = 0

    fragility_points = {
        "ref-fragil": ref_fragil, "psa10-iliquido": psa10_illiquid,
        "ref-desalinhada": misaligned, "reprint-forte": reprint,
        "preco-absoluto-alto": price_high, "vendedor-fraco": weak_seller,
        "tiragem": printing_flag, "dispersao": dispersed, "ref-stale": stale,
        "concentracao": concentration,
    }
    try:
        trust = round(scorer.trust_score(listing), 0)
    except (AttributeError, TypeError):
        trust = _float_or_none(getattr(opp, "trust_score", None))
    signals.update(listings_same_grade=same_grade, trust_score=trust, printing_tokens=printing)

    # --- notas, classe, motivos ---
    profile, profile_cov = profile_score(profile_points, int(lt_cfg["min_profile_sources"]))
    fragility, fragility_cov = fragility_score(fragility_points, int(lt_cfg["min_fragility_sources"]))
    key_inputs = all(fragility_points.get(k) is not None for k in KEY_FRAGILITY_INPUTS)
    tier = classify(profile, fragility, profile_cov, key_inputs, lt_cfg,
                    fragility_coverage=fragility_cov)

    reasons = [f"LP:{name}: n/d" for name in PROFILE_COMPONENTS if profile_points.get(name) is None]
    for name in FRAGILITY_FLAGS:
        pts = fragility_points.get(name)
        if pts is None:
            reasons.append(f"LP:{name}: n/d")
        elif pts > 0:
            detail = details.get(name)
            reasons.append(f"LP:{name}({detail})" if detail else f"LP:{name}")

    return LongTerm(profile=profile, fragility=fragility, tier=tier,
                    profile_coverage=profile_cov, fragility_coverage=fragility_cov,
                    reasons=reasons, signals=signals, profile_points=profile_points,
                    fragility_points=fragility_points)


def annotate(opp, result):
    """Grava SO os campos `longterm_*`/`trend_*` da Opportunity (result None = coluna
    desligada: campos ficam nos defaults). Nunca toca veredito, metricas, `risk_flags`,
    `reasons` nem `strategy`."""
    if result is None:
        return opp
    opp.longterm_profile = result.profile
    opp.longterm_fragility = result.fragility
    opp.longterm_tier = result.tier
    opp.longterm_coverage = coverage_text(result.profile_coverage, result.fragility_coverage)
    opp.longterm_reasons = list(result.reasons)
    opp.longterm_signals = dict(result.signals)
    opp.trend_12m_pct = result.signals.get("trend_12m_pct")
    opp.trend_36m_pct = result.signals.get("trend_36m_pct")
    opp.trend_source = result.signals.get("trend_source") or ""
    return opp
