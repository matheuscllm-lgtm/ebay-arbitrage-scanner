"""Guards puros (sem rede) do par EN × ZH-S raw no eBay.

Reaproveita o que o modo chinês PSA 10 já testou (`src/chinese_scan.py`): idioma do
título, nome-base + sufixo, lote/réplica. Testes: tests/test_zh_ebay_pairs.py.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import chinese_scan as cs  # noqa: E402

MIN_RATIO = 4.0   # decisão do operador: mostrar só EN ÷ ZH ≥ 4×

# "TAG TEAM" (mecânica da era SM) e "ACE SPEC" são da carta, não certificadoras TAG/ACE.
GRADED = re.compile(r"\b(psa|bgs|cgc|sgc|tag(?!\s*team)|ace(?!\s*spec)|graded|gem mint|slab)\b", re.I)
JUNK = re.compile(r"\bcase\b|skin|metal|insert|custom|display|binder|you pick|pick your|choose|"
                  r"proxy|orica|fan ?art|sticker|playmat|sleeve|toploader|\blots?\b|bundle|poster|"
                  r"acrylic|keychain|\bcoin\b|digital|code card|replica|minimum|extended art|"
                  r"magnetic|frame|\bstand\b|token|jumbo|oversized|empty|art card|reprint|30th|anniversary|"
                  r"celebration|classic collection", re.I)
NON_EN = re.compile(r"japanese|japan|jpn|korean|korea|chinese|indonesia|thai|german|french|"
                    r"italian|italiano|italy|\bita\b|spanish|espa[nñ]ol|portuguese|portugu[eê]s|deutsch|"
                    r"fran[cç]ais|\bfr\b|\bde\b|\bes\b|\bpt\b|\bjp\b|\bkr\b|\bcn\b", re.I)

# --- variante EN ------------------------------------------------------------------
# Produto TCGPlayer cujo anúncio mais barato no eBay é a carta comum de mesmo número
# (Umbreon 059 PRE "Master Ball Pattern" × holo comum): sai da seleção.
_VARIANT_RE = re.compile(
    r"[(\[]([^)\]]*(?:ball|pattern|stamp|cosmos|prerelease|staff|league|winner|exclusive)[^)\]]*)[)\]]", re.I)


def variant_qualifier(product_name: str | None) -> str | None:
    m = _VARIANT_RE.search(product_name or "")
    return m.group(1).strip() if m else None


# --- escolha da impressão ZH ------------------------------------------------------
_GALLERY = {"SAR", "CSR", "CHR", "AR", "SR", "S", "SSR"}
_EN_FAMILIES: tuple[tuple[re.Pattern[str], set[str]], ...] = (
    (re.compile(r"special illustration", re.I), {"SAR"}),
    (re.compile(r"illustration", re.I), {"AR"}),
    (re.compile(r"hyper", re.I), {"UR", "HR"}),
    (re.compile(r"secret", re.I), {"HR", "UR", "SAR", "SR"}),
    (re.compile(r"ultra", re.I), {"SR", "RR", "RRR", "SAR"}),
    (re.compile(r"double", re.I), {"RR"}),
)
_CN_KNOWN = {"SAR", "AR", "SR", "UR", "HR", "RR", "RRR", "CSR", "CHR", "S", "SSR"}


def rarity_fit(en_rarity: str | None, zrow: dict) -> bool | None:
    """True = a raridade chinesa é da família da EN (SIR↔SAR, IR↔AR, HR↔UR…);
    False = é de outra família; None = um dos lados não declara família conhecida."""
    cn = str(zrow.get("cn_rar") or "").upper()
    if cn not in _CN_KNOWN:
        return None
    code = str(zrow.get("en_rar") or "").upper()
    if code.startswith(("RGG", "RTG")):          # Galarian/Trainer Gallery = arte especial
        return cn in _GALLERY
    for rx, family in _EN_FAMILIES:
        if rx.search(en_rarity or ""):
            return cn in family
    return None


def pick_zh_row(zrows: list[dict], en_rarity: str | None) -> tuple[dict | None, bool]:
    """(impressão ZH escolhida, empate?). Gem Pack (`CBB*C`) fica fora: o "nº" ali é
    pacote + posição e casa carta comum do pacote. Ordem: raridade compatível com a EN,
    depois junção `tc-jp`. Empate entre impressões diferentes = flag, nunca chute calado.
    Só sobrou impressão de OUTRA família de raridade (EN SIR × ZH SR) = sem par."""
    rows = [z for z in zrows if not str(z.get("cn_code") or "").upper().startswith("CBB")]
    if not rows:
        return None, False

    def key(z):
        return ({True: 0, None: 1, False: 2}[rarity_fit(en_rarity, z)],
                0 if z.get("how") == "tc-jp" else 1)

    rows.sort(key=key)
    best = rows[0]
    if rarity_fit(en_rarity, best) is False:
        return None, False
    tied = {(z.get("cn_code"), z.get("cn_no")) for z in rows if key(z) == key(best)}
    return best, len(tied) > 1


# --- nome + sufixo ----------------------------------------------------------------
_SUFFIX_AFTER = re.compile(r"[\s\-]*(vmax|vstar|ex|gx|v)(?![a-z0-9])", re.I)
_TAG_AFTER = re.compile(r"\s*(?:&|and\b)", re.I)
_TAG_BEFORE = re.compile(r"(?:&|\band)\s*$", re.I)


def name_ok(en_name: str, title: str | None) -> bool:
    """Nome-base no título com o MESMO sufixo da carta EN: "Pikachu" não casa
    "Pikachu ex" (nem o contrário), "Umbreon V" não casa "Umbreon VMAX"."""
    base, suffix = cs.name_parts(en_name)
    t = (title or "").lower()
    if not base:
        return False
    tag_team = "&" in en_name
    # TAG TEAM: os dois nomes na ordem, com ou sem o "&" ("Gengar Mimikyu-GX")
    core = r"\s*(?:&|and\b|,)?\s*".join(re.escape(p.strip()) for p in base.split("&"))
    for m in re.finditer(r"(?<![a-z])" + core + r"(?![a-z])", t):
        if not tag_team and (_TAG_AFTER.match(t[m.end():]) or _TAG_BEFORE.search(t[:m.start()])):
            continue   # "Charizard & Braixen GX": outra carta com o mesmo nome dentro
        got = _SUFFIX_AFTER.match(t[m.end():])
        if (got.group(1).lower() if got else "") == suffix:
            return True
    return False


# --- lote -------------------------------------------------------------------------
def is_lot(title: str | None) -> bool:
    """Lote, réplica/acessório, ou vários "nº/total" diferentes no mesmo título."""
    t = title or ""
    if cs.lot_or_reject(t) or JUNK.search(t):
        return True
    return len({(int(a), b) for a, b in cs._FRACTION_RE.findall(t)}) > 1


# --- número -----------------------------------------------------------------------
def num_in(title: str, num: str, total: str | None = None) -> bool:
    """Número da carta no título. Havendo fração "nº/total" no título e número puramente
    numérico, o NUMERADOR tem que ser o da carta (199/165 não casa 183/165) e, quando o
    total da carta é conhecido, o DENOMINADOR também (161/131 não casa 161/189)."""
    if total is None and "/" in str(num):
        total = str(num).split("/")[1]
    total = str(total or "").strip()
    num = str(num).split("/")[0].split()[-1].strip().lower()
    t = (title or "").lower()
    m = re.match(r"^([a-z]*)0*(\d+)$", num)
    if not m:
        return num in t
    pre, digits = m.groups()
    if not pre:
        fracs = cs._FRACTION_RE.findall(t)
        if fracs:
            return any(int(a) == int(digits) and (not total.isdigit() or int(b) == int(total))
                       for a, b in fracs)
    return re.search(rf"(?<![a-z0-9]){pre}0*{digits}(?![0-9a-z])", t) is not None


def code_in(title: str, code: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(code.lower())}(?![a-z0-9])", (title or "").lower()) is not None


# --- título EN / ZH ---------------------------------------------------------------
# Carta jogada/danificada declarada no título. "HP" só conta quando não é ponto de vida
# ("240HP", "240 HP", "HP140" são da carta).
PLAYED = re.compile(
    r"(?<!un)(?<!never )\bplayed\b|\bdamaged\b|\bcreas(?:e|ed|es)\b|\bpoor\b|\b(?:mp|lp|dmg)\b|"
    r"(?<!\d)(?<!\d\s)(?<!\d\s\s)(?<!\d-)\bhp\b(?![\s:/-]*\d)", re.I)


def _raw_single(title: str) -> bool:
    return not GRADED.search(title) and not PLAYED.search(title) and not is_lot(title)


def card_condition(payload: dict) -> str | None:
    """Condição pelo getItem: "NM" (Near mint or better) · "OUTRA" (jogada, danificada ou
    graded) · None = o vendedor não informou (não dá para afirmar nem negar)."""
    if str(payload.get("conditionId") or "") == "2750":
        return "OUTRA"
    for desc in payload.get("conditionDescriptors") or []:
        if desc.get("name") == "Card Condition":
            values = [str(v.get("content") or "") for v in desc.get("values") or []]
            if values:
                return "NM" if values[0].lower().startswith("near mint") else "OUTRA"
    return None


def en_title_ok(title: str, en_name: str, num: str) -> bool:
    return (_raw_single(title) and name_ok(en_name, title) and num_in(title, num)
            and not NON_EN.search(title))


def zh_title_ok(title: str, en_name: str, zrow: dict) -> bool:
    """Chinês simplificado (ou "Chinese" sem dizer qual) da impressão escolhida:
    código do set + número no título; tradicional ou outro idioma citado junto = fora."""
    lang, _ = cs.chinese_language(title)
    if cs._HANT_RE.search(title or ""):
        return False
    return (lang in ("ZH-HANS", "ZH") and _raw_single(title) and name_ok(en_name, title)
            and code_in(title, zrow["cn_code"]) and num_in(title, zrow["cn_no"], zrow.get("cn_total")))


# --- crivo ------------------------------------------------------------------------
def total(item: dict) -> float:
    """Item + frete; frete desconhecido (None) conta 0 e a linha leva a flag."""
    return float(item["price"]) + float(item.get("shipping") or 0)


def pair_ratio(en_item: dict, zh_item: dict) -> float | None:
    zh = total(zh_item)
    return total(en_item) / zh if zh > 0 else None


# --- "à venda" na entrega ---------------------------------------------------------
def availability(payload: dict, now: datetime | None = None) -> tuple[bool, str]:
    """(à venda?, motivo) a partir do getItem da Browse API. Sem status de estoque no
    payload = não confirmado (nunca presumir que está à venda)."""
    now = now or datetime.now(timezone.utc)
    if "FIXED_PRICE" not in (payload.get("buyingOptions") or []):
        return False, "nao-e-preco-fixo"
    end = payload.get("itemEndDate")
    if end:
        try:
            if datetime.fromisoformat(end.replace("Z", "+00:00")) <= now:
                return False, "encerrado"
        except ValueError:
            return False, "data-de-fim-ilegivel"
    status = {a.get("estimatedAvailabilityStatus") for a in payload.get("estimatedAvailabilities") or []}
    if status & {"IN_STOCK", "LIMITED_STOCK"}:
        return True, "a-venda"
    if "OUT_OF_STOCK" in status:
        return False, "sem-estoque"
    return False, "disponibilidade-nao-informada"
