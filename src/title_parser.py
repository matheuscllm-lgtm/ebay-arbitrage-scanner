"""Parser de titulos de anuncios do eBay.

Tarefa: a partir do titulo (e da condicao declarada), descobrir com precisao:
1. A grade da carta (RAW, PSA 10, PSA 9, BGS 10, BGS 9.5, CGC 10, CGC 9.5).
2. Se uma carta RAW e Near Mint (invariante do projeto: raw so NM).
3. O idioma (EN / JP).
4. Sinais de risco (proxy, replica, dano, lote, etc).

Filosofia: precisao > cobertura. Na duvida, REJEITA ou manda para REVISAR --
falso positivo custa dinheiro real, falso negativo custa so uma oportunidade.
"""
import re

# --- Grades ---------------------------------------------------------------
# Ordem importa: padroes mais especificos primeiro (9.5 antes de 9).
_GRADE_PATTERNS = [
    (r"\bPSA[\s:-]*10\b", "PSA 10"),
    (r"\bPSA[\s:-]*9(?![\d.])", "PSA 9"),
    (r"\bBGS[\s:-]*10\b", "BGS 10"),
    (r"\bBGS[\s:-]*9\.5\b", "BGS 9.5"),
    (r"\bCGC[\s:-]*10\b", "CGC 10"),
    (r"\bCGC[\s:-]*9\.5\b", "CGC 9.5"),
]

# Grades graduadas FORA do escopo (presenca = rejeitar, nao e raw nem aceita).
_OUT_OF_SCOPE_GRADE = re.compile(
    r"\b(PSA|BGS|CGC|SGC|ACE|TAG|AGS|GMA|HGA)[\s:-]*(\d+(?:\.\d+)?)\b", re.I
)

# --- Condicao de carta raw ------------------------------------------------
_NM_POSITIVE = re.compile(
    r"\b(NM|N/M|near[\s-]*mint|mint|pack[\s-]*fresh|gem[\s-]*mint)\b", re.I
)
_CONDITION_BAD = re.compile(
    r"\b(LP|MP|HP|DMG|lightly\s+played|light\s+play|moderately\s+played|"
    r"played|heavily\s+played|heavy\s+play|damaged|poor|creas\w+|crease|"
    r"scratch\w+|wear|whitening|bend|bent|water\s*damage|swirl)\b", re.I
)

# --- Risco / lixo ----------------------------------------------------------
_REJECT_KEYWORDS = re.compile(
    r"\b(proxy|proxies|replica|reprint|custom|fake|orica|altered|art\s*card|"
    r"goldcard|gold\s+card|metal\s+card|sticker|digital|online\s+code|"
    r"code\s+card|empty|box\s+only|case\s+only|slab\s+only|toploader|"
    r"poker|playing\s+card|acrylic|case\s+card|magnetic\s+case|alloy|"
    r"display|binder|blanket|mystery\s+pack|chase\s+pack|fan\s+art|"
    r"wood(?:en)?|plush|figure|keychain|pin|patch|playmat|sleeve)\b", re.I
)
_LOT_KEYWORDS = re.compile(
    r"\b(lot|bundle|x\s*\d{2,}|\d{2,}\s*x\b|collection|bulk|choose|pick|"
    r"complete\s+set)\b", re.I
)

# --- Idioma ----------------------------------------------------------------
_JP_KEYWORDS = re.compile(r"\b(japanese|japan|jpn|jp)\b|日本", re.I)
_OTHER_LANG = re.compile(
    r"\b(korean|chinese|german|french|italian|spanish|portuguese|"
    r"deutsch|coreana?|kor)\b", re.I
)


def detect_grade(title):
    """Retorna a grade detectada ('RAW' se nenhuma) ou None se fora do escopo.

    Exemplos: 'PSA 10' -> PSA 10; 'PSA 8' -> None (fora do escopo);
    sem mencao de grading -> RAW.
    """
    for pattern, grade in _GRADE_PATTERNS:
        if re.search(pattern, title, re.I):
            return grade
    m = _OUT_OF_SCOPE_GRADE.search(title)
    if m:
        return None  # graduada, mas numa grade/empresa fora do escopo
    return "RAW"


def grade_is_ambiguous(title, detected_grade):
    """True se o titulo menciona OUTRA nota alem da detectada.

    Caso real do 1o scan: 'Charizard BGS 8.5 NM-MINT FRESH GRADE PSA 9' --
    a carta E BGS 8.5; o 'PSA 9' e expectativa do vendedor. Qualquer mencao
    de nota diferente da detectada = ambiguo = fora.
    """
    if detected_grade in (None, "RAW"):
        return False
    expected = detected_grade.replace(" ", "").upper()
    for m in _OUT_OF_SCOPE_GRADE.finditer(title):
        mention = (m.group(1) + m.group(2)).upper()
        if mention != expected:
            return True
    return False


def detect_language(title):
    """EN / JP / OTHER. Sem mencao de idioma = EN (default do eBay US)."""
    if _OTHER_LANG.search(title):
        return "OTHER"
    if _JP_KEYWORDS.search(title):
        return "JP"
    return "EN"


def is_nm_acceptable(title, ebay_condition=""):
    """Para cartas RAW: True somente se ha sinal de NM e nenhum sinal de dano.

    Regra do projeto: raw so Near Mint. Match conservador -- qualquer keyword
    de condicao inferior rejeita, mesmo que 'NM' tambem apareca no titulo
    (ex.: 'NM/LP' rejeita).
    """
    text = f"{title} {ebay_condition}"
    if _CONDITION_BAD.search(text):
        return False
    return bool(_NM_POSITIVE.search(text))


def risk_flags(title, listing=None):
    """Lista de flags de risco baseadas em titulo + dados do anuncio."""
    flags = []
    if _REJECT_KEYWORDS.search(title):
        flags.append("REJEITAR: palavra de proxy/replica/acessorio no titulo")
    if _LOT_KEYWORDS.search(title):
        flags.append("LOTE: anuncio parece ser lote/colecao, nao carta unica")
    if listing is not None:
        if listing.buying_option == "AUCTION":
            flags.append("LEILAO: preco atual pode subir ate o fim")
        if listing.seller_feedback_score < 50:
            flags.append("VENDEDOR: menos de 50 avaliacoes")
        elif listing.seller_feedback_pct and listing.seller_feedback_pct < 98.0:
            flags.append(
                f"VENDEDOR: feedback {listing.seller_feedback_pct:.1f}% (<98%)"
            )
    return flags


def card_matches_title(card, title):
    """Checagem minima de identidade: nome da carta presente no titulo e,
    se houver numero, o numero tambem (evita casar 'Charizard ex' com
    'Charizard VMAX')."""
    t = title.lower()
    if card.name.lower() not in t:
        return False
    for kw in card.exclude_keywords:
        if kw.lower() in t:
            return False
    if card.number:
        num = card.number.lower().lstrip("0") or card.number.lower()
        pattern = r"(?:#|no\.?\s*|\b)0*%s\b" % re.escape(num)
        if not re.search(pattern, t):
            return False
    return True
