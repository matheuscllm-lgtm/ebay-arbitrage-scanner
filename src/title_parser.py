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

from . import grading

# --- Grades ---------------------------------------------------------------
# A leitura da nota vive em src/grading.py (PSA 8-10, CGC 9-10 Gem/Pristine,
# BGS 9-10 (+Black Label), SGC 9-10, TAG 9.5/10; ambiguidade; fora do escopo).
# Fonte unica das notas aceitas (validacao do --grades):
KNOWN_GRADES = tuple(sorted(grading.DEFAULT_GRADED_ALLOW))

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
    r"goldcard|gold\s+card|gold\s+foil|gold\s+plated|24k|metal\s+card|"
    r"metal\s+foil|gold\s+metal|jumbo|oversiz(?:e|ed)|"
    r"sticker|digital|online\s+code|"
    r"code\s+card|empty|box\s+only|case\s+only|slab\s+only|toploader|"
    r"poker|playing\s+card|acrylic|case\s+card|magnetic\s+case|alloy|"
    r"display|binder|blanket|mystery\s+pack|chase\s+pack|fan\s+art|"
    r"wood(?:en)?|plush|figure|keychain|pin|patch|playmat|sleeve)\b", re.I
)
_LOT_KEYWORDS = re.compile(
    r"\b(lot|bundle|x\s*(?:[2-9]|[1-9]\d+)|(?:[2-9]|[1-9]\d+)\s*x\b|collection|bulk|choose|pick|"
    r"complete\s+set|set\s+of\s+\d+|(?:[2-9]|[1-9]\d+)\s+(?:cards|slabs))\b", re.I
)

# --- Idioma ----------------------------------------------------------------
_JP_KEYWORDS = re.compile(r"\b(japanese|japan|jpn|jp)\b|日本", re.I)
_OTHER_LANG = re.compile(
    r"\b(korean|chinese|german|french|italian|spanish|portuguese|"
    r"deutsch|coreana?|kor)\b", re.I
)

# Nomenclatura de raridade/set JAPONESA sem a palavra "japanese" no titulo.
# Caso real 2026-09-01: "Alakazam ex 201/165 ... Holo SAR PSA 10" a $175 era a
# versao JAPONESA (SAR = Special Art Rare, codigo do mercado JP; em EN a
# raridade e SIR) -- detect_language dizia EN e a margem de 81% saia comparando
# a carta JP com a referencia EN ($317), ou seja, produto errado. SAR/CHR/CSR
# sao codigos de raridade exclusivos do mercado JP; sv2a/s4a/sm12a etc. sao
# codigos de SET japoneses (numero + letra minuscula no fim).
_JP_NOMENCLATURE = re.compile(
    r"\b(SAR|CHR|CSR)\b|\b(?:s|sv|sm)\d{1,2}[ab]\b", re.I)
_EN_EXPLICIT = re.compile(r"\benglish\b", re.I)


def jp_nomenclature_hint(title):
    """True se o titulo usa nomenclatura do mercado JP sem dizer 'English'.

    Nao e prova de carta japonesa -- e indicio forte o bastante para, numa
    watchlist EN, rejeitar com motivo visivel (precisao > cobertura: margem
    contra referencia do produto errado custa dinheiro real)."""
    return bool(_JP_NOMENCLATURE.search(title)) and not _EN_EXPLICIT.search(title)


def classify_grade(title, allow=None):
    """grading.GradeResult do titulo: status graded / raw / ambiguous / out_of_scope."""
    return grading.grade_from_title(title or "", allow or grading.DEFAULT_GRADED_ALLOW)


def detect_grade(title, allow=None):
    """Chave da nota detectada ('PSA 10', 'CGC 10 GEM', 'BGS 10 BLACK'...), 'RAW'
    se nenhuma certificadora e citada, ou None se ambiguo / fora do escopo.

    Exemplos: 'PSA 10' -> 'PSA 10'; 'PSA 7' -> None (fora da allowlist);
    'CGC 10 Pristine' -> 'CGC 10 PRISTINE'; sem mencao de grading -> 'RAW'.
    """
    r = classify_grade(title, allow)
    if r.status == "raw":
        return "RAW"
    if r.status == "graded":
        return r.grade.key
    return None


def grade_is_ambiguous(title, detected_grade=None):
    """True se o titulo menciona mais de uma nota distinta.

    Caso real do 1o scan: 'Charizard BGS 8.5 NM-MINT FRESH GRADE PSA 9' --
    a carta E BGS 8.5; o 'PSA 9' e expectativa do vendedor. Mais de uma nota
    = ambiguo = fora (sem nota unica nao ha venda comparavel).
    """
    return classify_grade(title).status == "ambiguous"


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


# LP EXPLICITO (titulo ou campo de condicao do eBay: "Lightly Played (Excellent)").
_LP_POSITIVE = re.compile(
    r"\bLP\b|\blightly[\s-]+played\b|\blight(?:ly)?[\s-]+play\b", re.I)
# Qualquer sinal de condicao PIOR que LP desqualifica (nunca "LP/MP").
_WORSE_THAN_LP = re.compile(
    r"\b(MP|HP|DMG|moderately\s+played|heavily\s+played|heavy\s+play|damaged|"
    r"poor|creas\w+|crease|scratch\w+|whitening|bend|bent|water\s*damage|swirl)\b", re.I)


def is_lp(title, ebay_condition=""):
    """Para cartas RAW: True somente se a condicao LP e EXPLICITA (titulo ou
    campo do eBay diz LP / Lightly Played), sem sinal de NM ("NM/LP" e ambiguo
    -> nao) e sem condicao pior. So entao a carta procura a SUA referencia
    (mediana de >=3 vendas LP) -- nunca e comparada com o preco NM."""
    text = f"{title} {ebay_condition or ''}"
    if not _LP_POSITIVE.search(text):
        return False
    if _NM_POSITIVE.search(text):
        return False
    if _WORSE_THAN_LP.search(text):
        return False
    return True


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


# Mencao de nota ("PSA 10", "CGC 9.5 Pristine", "BGS gem mint 9.5") -- removida do
# titulo antes de procurar o NUMERO da carta: carta nº 10 nao casa "Mewtwo VSTAR
# PSA 10" (review Codex 2026-09-03).
_GRADE_MENTION_STRIP = re.compile(
    r"\b(psa|bgs|beckett|cgc|sgc|tag|ace|mnt|gma|hga|ags)\b[\s:\-]*"
    r"(?:(?:gem\s*m(?:in)?t|mint|pristine|nm-?mt|black\s*label|graded)\s*)?\d{1,2}(?:\.5)?\b", re.I)


# "004/102", "SV49/SV94", "TG04/TG30", "#11 /25": (numerador, denominador).
_FRACTION_RE = re.compile(r"([a-z]{0,3}\d{1,4}[a-z]?)\s*/\s*([a-z]{0,3}\d{1,4}[a-z]?)", re.I)


def _norm_num_token(tok):
    """'004' -> '4'; 'SV049' -> 'sv49'; 'TG04' -> 'tg4'. Numero de carta comparavel."""
    m = re.match(r"^([a-z]*)0*(\d+)([a-z]?)$", str(tok).strip().lower())
    return (m.group(1) + m.group(2) + m.group(3)) if m else str(tok).strip().lower()


_NAME_PREFIX_CONFLICT = re.compile(r"\b(?:dark|shining|radiant|light|mega|primal)\s*$")
_NAME_SUFFIX_CONFLICT = re.compile(r"\s+(?:ex|gx|v|vmax|vstar|lv\.?\s*x)\b")
_POP_CERT_QTY_RE = re.compile(r"\b(?:pop(?:ulation)?|cert(?:ificate)?|qty)\s*[:#-]?\s*\d+\b")
# "#4", "#H02", "no. 4": numero de carta com marcador explicito.
_MARKED_NUMBER_RE = re.compile(r"(?:#|\bno\.?)\s*([a-z]{0,3}\d{1,4}[a-z]?)\b")


def _name_conflicts(card, t):
    """True se o NOME da carta nao esta no titulo (palavra inteira) ou esta com
    prefixo/sufixo que muda a carta ("Dark Charizard", "Charizard ex"). Nome vazio
    = o chamador confere o nome por conta propria (`slab_strategy.identity_matches`)."""
    name = card.name.lower().strip()
    if not name:
        return False
    # Nome como palavra inteira (limite de palavra): "Mew" nao casa "Mewtwo".
    name_match = re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", t)
    if not name_match:
        return True
    # Prefixo que muda a carta ("Dark Charizard" nao e "Charizard") e sufixo
    # que muda a carta ("Charizard ex" nao e "Charizard"): outra referencia.
    if _NAME_PREFIX_CONFLICT.search(t[:name_match.start()]):
        return True
    return _NAME_SUFFIX_CONFLICT.match(t[name_match.end():]) is not None


def _number_context(card, t):
    """(numero esperado normalizado, partes prefixo/digitos/sufixo, denominador
    esperado ou None, titulo limpo de tudo que NAO e numero de carta)."""
    expected = str(card.number).lower().split("/")
    num = _norm_num_token(expected[0])
    parts = re.match(r"^([a-z]*)(\d+)([a-z]?)$", num)
    prefix = parts.group(1) if parts else ""
    clean = _GRADE_MENTION_STRIP.sub(" ", t)
    # "pop 12" (populacao), "cert 12" (certificado) e "qty 2" nunca sao o
    # numero da carta. Vale para os DOIS caminhos (a politica chama esta
    # funcao com nome vazio) -- declarado no CHANGELOG do PR #32.
    clean = _POP_CERT_QTY_RE.sub(" ", clean)
    # Codigo de serie + numero ("SM12", "SWSH 45") e o SET, nao a carta --
    # exceto (a) quando o numero esperado tem esse prefixo (promo "SM211",
    # "SWSH050") e (b) quando vem uma fracao logo depois ("SM 150/147": a
    # fracao e o numero da carta). Review do PR #32.
    series = [code for code in ("swsh", "sm", "xy") if code != prefix]
    clean = re.sub(r"\b(?:%s)\s*[:#-]?\s*\d+\b(?!\s*/)" % "|".join(series), " ", clean)
    denominator = _norm_num_token(expected[1]) if len(expected) > 1 else None
    return num, parts, denominator, clean


def _fraction_matches(fracs, num, denominator):
    # Em "11/25" o DENOMINADOR e o tamanho do set, nunca a carta. Sem isto,
    # "Mew #11 /25" casava o card numero 25 (o Secret Rare, caro) e a referencia
    # saia da carta errada -- achado do review, 2026-09-04 (49 linhas afetadas).
    return any(_norm_num_token(a) == num and
               (denominator is None or _norm_num_token(b) == denominator)
               for a, b in fracs)


def card_matches_title(card, title):
    """Checagem minima de identidade: nome da carta presente no titulo e,
    se houver numero, o numero tambem (evita casar 'Charizard ex' com
    'Charizard VMAX'). A nota do slab nunca conta como numero."""
    t = title.lower()
    if _name_conflicts(card, t):
        return False
    for kw in card.exclude_keywords:
        if kw.lower() in t:
            return False
    if card.number:
        num, parts, denominator, clean = _number_context(card, t)
        fracs = _FRACTION_RE.findall(clean)
        if fracs:
            return _fraction_matches(fracs, num, denominator)
        # Zero a esquerda opcional ENTRE o prefixo de letras e os digitos: "H02"
        # e "H2", "TG03" e "TG3", "SV049" e "SV49" sao a mesma carta (review do
        # PR #32: o zero nunca vem antes do prefixo, e 32 cartas da watchlist com
        # numero alfanumerico deixavam de casar o titulo com o zero).
        if parts:
            pattern = r"(?:#|no\.?\s*|\b)%s0*%s%s\b" % (
                re.escape(parts.group(1)), parts.group(2), re.escape(parts.group(3)))
        else:
            pattern = r"(?:#|no\.?\s*|\b)0*%s\b" % re.escape(num)
        if not re.search(pattern, clean):
            return False
    return True


def sale_contradicts_card(card, title):
    """True se o titulo de uma VENDA (na pagina da propria carta no PriceCharting)
    CONTRADIZ a identidade: outro nome, prefixo/sufixo que muda a carta, palavra
    de exclusao, ou numero explicito diferente (fracao "39/165" ou "#14"). A
    AUSENCIA de numero nao e contradicao: "1999 Pokemon Charizard Base Set Holo
    PSA 9" na pagina da Charizard 4/102 continua na cesta (review do PR #32:
    exigir numero amputava vendas da propria carta e movia a mediana). Um numero
    solto sem marcador (ano "1999", "1st") nunca e evidencia contra."""
    t = title.lower()
    if _name_conflicts(card, t):
        return True
    for kw in card.exclude_keywords:
        if kw.lower() in t:
            return True
    if card.number:
        num, _parts, denominator, clean = _number_context(card, t)
        fracs = _FRACTION_RE.findall(clean)
        if fracs:
            return not _fraction_matches(fracs, num, denominator)
        marked = _MARKED_NUMBER_RE.search(clean)
        if marked:
            return _norm_num_token(marked.group(1)) != num
    return False


# --- ano de lancamento citado no titulo (guarda de edicao) --------------------
# Nao e "qualquer sequencia de 4 digitos": fracao ("4/102"), numero de certificado
# (PSA tem 8 digitos, CGC 10-11) e numero solto ficam de fora. Confundir um deles
# com ano REJEITARIA carta legitima, que e o erro caro aqui.
_CARD_YEAR_RE = re.compile(r"(?<![\d/])(199[6-9]|20[0-3]\d)(?![\d/])")


def card_year_candidates(title):
    """Anos de lancamento plausiveis citados no titulo, como frozenset de int.

    Intervalo ("1999-2000 WOTC") devolve os dois anos: o anuncio nao esta se
    contradizendo, esta cobrindo a era. Ausencia de ano devolve conjunto vazio --
    que NAO e evidencia de nada, so falta de evidencia.
    """
    return frozenset(int(y) for y in _CARD_YEAR_RE.findall(title or ""))
