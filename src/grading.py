"""Nota de slab (carta gradada) a partir do TÍTULO de um anúncio do eBay + allowlist
+ coluna exata do PriceCharting.

Modelo portado de scanner-comc/comc_scanner/grading.py @ dd952ba; parse adaptado a
títulos do eBay. Na COMC a nota vem do SEGMENTO DA URL (``/Graded/<grader>/<nota>``,
dado estruturado); no eBay só existe o título livre escrito pelo vendedor — daí um
parser próprio, com a mesma filosofia do ``title_parser``: precisão > cobertura
(na dúvida, "ambiguous"/"out_of_scope"; falso positivo custa dinheiro real).

Vocabulário (linguagem simples):
- "slab" = carta lacrada em cápsula por uma certificadora (PSA, CGC, BGS/Beckett, SGC,
  TAG) com uma nota de 1 a 10 (meias notas: 8.5, 9.5). PSA não emite 9.5 — "PSA 9.5"
  não existe; o parser lê 9.5 (nunca arredonda para 9) e a allowlist derruba.
- "qualificador" = subcategoria da nota 10 que muda o preço: CGC 10 tem "Pristine"
  (topo) e "Gem Mint"; BGS 10 tem "Black Label" (etiqueta preta, topo) e a 10 comum
  (etiqueta dourada, que a Beckett chama de "Pristine" — por isso "BGS 10 Pristine"
  é a BGS 10 normal, sem qualificador).

Convenções de título do eBay (decisões deste módulo):
- **CGC 10 sem a palavra "Pristine" = GEM MINT.** ⚠️ É o OPOSTO do segmento de URL da
  COMC (lá ``10`` puro = Pristine, ``10_GEM`` = Gem Mint). No eBay a Pristine é rara e
  o vendedor SEMPRE escreve "Pristine" (é o argumento de venda); "CGC 10" seco é, na
  prática, Gem Mint. Assumir Gem é também o lado seguro: a referência Gem é a mais
  baixa das duas, então uma Pristine não anunciada só faz a margem parecer MENOR.
- **BGS 10 só é Black Label** com "black label" ou com "black" colado em "BGS 10"
  (antes da nota, ou logo depois e sem outra palavra na sequência). "Black Kyurem
  BGS 10" é nome de carta; "BGS 10 Black Star/Black Dot" é promo/erro de impressão.
- Toda menção ``<certificadora> <nota>`` conta, inclusive "PSA 10 pop 5" e "compare
  PSA 9" — é isso que gera o status "ambiguous" (mais de uma nota distinta = não dá
  pra saber qual é a carta; caso real: "BGS 8.5 NM-MINT FRESH GRADE PSA 9").
- Número sem certificadora ("10/10 condition", "9.5 x 6", "SWSH 10") não é menção.
- "Tag" solto (sem nota) não é sinal de certificadora — é palavra comum ("Tag Team");
  "TAG 10"/"TAG 9.5" com nota são menções normais.

O que este módulo NÃO decide: lote, proxy, idioma, "PSA 10 potential" (carta crua
anunciada com expectativa de nota) — isso é ``title_parser.risk_flags`` / integração no
scorer. Aqui: quais notas o título cita e se dá pra confiar numa só. Só stdlib.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ── modelo (portado) ─────────────────────────────────────────────────────────

# Certificadoras do escopo: sigla no título → grader canônico.
_GRADER_CANON = {
    "PSA": "PSA", "CGC": "CGC", "BGS": "BGS", "BECKETT": "BGS", "SGC": "SGC", "TAG": "TAG",
}

# Chaves aceitas (formato ``<GRADER> <nota>[ <qualificador>]``).
DEFAULT_GRADED_ALLOW: frozenset[str] = frozenset({
    "PSA 8", "PSA 9", "PSA 10",
    "CGC 9", "CGC 9.5", "CGC 10 GEM", "CGC 10 PRISTINE",
    "BGS 9", "BGS 9.5", "BGS 10", "BGS 10 BLACK",
    "SGC 9", "SGC 9.5", "SGC 10",
    "TAG 9.5", "TAG 10",
})

# Colunas que a página do PriceCharting expõe por nome EXATO ("Full Price Guide").
# Chave da nota → rótulo normalizado da coluna. "Grade 9" / "Grade 9.5" são buckets
# GENÉRICOS (misturam certificadoras) e NUNCA entram aqui. (O original também mapeia
# "ACE 10"; ACE está fora do escopo deste parser, então a entrada seria morta.)
_PC_EXACT_COLUMN = {
    "PSA 10": "PSA 10",
    "BGS 10": "BGS 10",
    "BGS 10 BLACK": "BGS 10 BLACK",
    "CGC 10 PRISTINE": "CGC 10 PRISTINE",
    "CGC 10 GEM": "CGC 10",  # rótulo do PC para CGC Gem Mint 10
    "SGC 10": "SGC 10",
    "TAG 10": "TAG 10",
}
_LABEL_WORDS = {"PRISTINE": "Pristine", "GEM": "Gem Mint", "BLACK": "Black Label"}

STATUSES = ("graded", "raw", "ambiguous", "out_of_scope")


@dataclass(frozen=True, slots=True)
class Grade:
    grader: str          # PSA / CGC / BGS / SGC / TAG
    value: float         # 10.0, 9.5 ...
    qualifier: str = ""  # "PRISTINE" / "GEM" (CGC 10) · "BLACK" (BGS 10 Black Label)

    @property
    def key(self) -> str:
        base = f"{self.grader} {self.value:g}"
        return f"{base} {self.qualifier}" if self.qualifier else base

    @property
    def label(self) -> str:
        """Texto curto para a entrega: 'PSA 10', 'CGC 10 Pristine', 'CGC 10 Gem Mint',
        'BGS 10 Black Label'."""
        base = f"{self.grader} {self.value:g}"
        if not self.qualifier:
            return base
        return f"{base} {_LABEL_WORDS.get(self.qualifier, self.qualifier)}"


@dataclass(frozen=True, slots=True)
class GradeResult:
    grade: Grade | None
    status: str          # graded | raw | ambiguous | out_of_scope
    reason: str = ""


# ── regex (compiladas uma vez) ───────────────────────────────────────────────

_SEP = r"[\s:\-]*"
# Palavras que podem ficar entre a sigla e a nota (ou logo depois da nota) sem
# quebrar a menção: "PSA GEM MT 10", "PSA NM-MT 8", "BGS BLACK LABEL 10",
# "CGC 10 PRISTINE", "PSA graded 10". STAR/DOT entram só para que "Black Star" /
# "Black Dot" sejam lidos junto e descartados por ``mentions_black_label``.
_QUAL_TOKEN = r"(?:GEM|MINT|MT|NM|PRISTINE|BLACK|LABEL|STAR|DOT|GRADED)"
# Notas plausíveis: 1–10 em passos de 0.5. "TAG 33/236" e "PSA 100" não são notas.
_VALUE = r"(?:10|[1-9](?:\.5)?)"
# Depois da nota não pode vir dígito nem ".dígito" — "PSA 9.5" nunca vira "PSA 9";
# "PSA 10." (ponto final) continua valendo.
_AFTER_VALUE = r"(?!\d|\.\d)"

_MENTION_RE = re.compile(
    rf"\b(?P<grader>PSA|CGC|BGS|BECKETT|SGC|TAG)"
    rf"(?P<pre>(?:{_SEP}\b{_QUAL_TOKEN}\b)*)"
    rf"{_SEP}(?P<value>{_VALUE}){_AFTER_VALUE}"
    rf"(?P<post>(?:{_SEP}\b{_QUAL_TOKEN}\b)*)",
    re.I,
)

# Certificadoras FORA do escopo (ou "GRADED 10" sem certificadora nenhuma).
_UNKNOWN_GRADER_RE = re.compile(
    rf"\b(?P<grader>ACE|MNT|GMA|HGA|AGS|KSA|RCG|CSG|GRADED)"
    rf"(?:{_SEP}\b{_QUAL_TOKEN}\b)*{_SEP}(?P<value>{_VALUE}){_AFTER_VALUE}",
    re.I,
)

# Sigla conhecida sem nota nenhuma ("PSA graded card", "CGC slab"). TAG fica de fora
# de propósito: "Tag Team" é nome de mecânica/carta, não certificadora.
_GRADER_ALONE_RE = re.compile(r"\b(PSA|CGC|BGS|BECKETT|SGC)\b", re.I)

_BLACK_NOT_LABEL_RE = re.compile(r"\bblack\s*[-_]?\s*(?:star|dot)\b", re.I)
_BLACK_RE = re.compile(r"\bblack\b", re.I)
_BLACK_LABEL_RE = re.compile(r"\bblack[\s:\-_]*label\b", re.I)
_ENDS_WITH_BLACK_RE = re.compile(r"\bblack[\s:\-]*$", re.I)
_WORD_CONTINUES_RE = re.compile(r"\s*\w")


# ── funções do modelo (portadas) ─────────────────────────────────────────────

def mentions_black_label(text: str | None) -> bool:
    """"black" no texto = etiqueta preta da BGS (Black Label). Ignora "Black Star"
    (promo) e "Black Dot" (erro de impressão), que são nome de carta/variante."""
    text = (text or "").replace("_", " ")
    return _BLACK_RE.search(_BLACK_NOT_LABEL_RE.sub(" ", text)) is not None


def is_allowed(grade: Grade | None,
               allow: frozenset[str] | set[str] = DEFAULT_GRADED_ALLOW) -> bool:
    return grade is not None and grade.key in allow


def pc_price_key(grade: Grade | None) -> str | None:
    """Coluna EXATA do PriceCharting para a nota ("PSA 10", "BGS 10 BLACK", "CGC 10"
    para CGC Gem Mint…) ou None quando a nota não tem coluna própria (PSA 9, BGS 9.5,
    TAG 9.5…). Bucket genérico ("Grade 9", "Grade 9.5") nunca é devolvido."""
    if grade is None:
        return None
    return _PC_EXACT_COLUMN.get(grade.key)


# ── parse do título ──────────────────────────────────────────────────────────

def _qualifier(grader: str, value: float, pre: str, post: str, tail: str) -> str:
    """Qualificador da nota 10 (só CGC e BGS têm). `pre` = palavras entre a sigla e a
    nota; `post` = palavras coladas logo depois da nota; `tail` = resto do título."""
    if value != 10.0 or grader not in ("CGC", "BGS"):
        return ""
    around = f"{pre} {post}"
    if grader == "CGC":
        return "PRISTINE" if "pristine" in around.lower() else "GEM"
    # BGS: "black label" em qualquer posição; "black" seco só antes da nota ou logo
    # depois dela e sem outra palavra na sequência ("BGS 10 Black Kyurem" = carta).
    if _BLACK_LABEL_RE.search(around):
        return "BLACK"
    if mentions_black_label(pre):
        return "BLACK"
    if (mentions_black_label(post) and _ENDS_WITH_BLACK_RE.search(post)
            and not _WORD_CONTINUES_RE.match(tail)):
        return "BLACK"
    return ""


def _grade_from_match(m: re.Match, text: str) -> Grade:
    grader = _GRADER_CANON[m.group("grader").upper()]
    value = float(m.group("value"))
    qualifier = _qualifier(grader, value, m.group("pre"), m.group("post"),
                           text[m.end():])
    return Grade(grader=grader, value=value, qualifier=qualifier)


def _find_mentions(title: str) -> list[tuple[Grade, tuple[int, int]]]:
    return [(_grade_from_match(m, title), m.span()) for m in _MENTION_RE.finditer(title)]


def _unknown_mentions(title: str, taken: list[tuple[int, int]]) -> list[str]:
    """Menções de certificadora fora do escopo ("ACE 10", "GRADED 10"), ignorando as
    que já fazem parte de uma menção do escopo ("PSA graded 10" não é "GRADED 10")."""
    out = []
    for m in _UNKNOWN_GRADER_RE.finditer(title):
        if any(start <= m.start() < end for start, end in taken):
            continue
        key = f"{m.group('grader').upper()} {float(m.group('value')):g}"
        if key not in out:
            out.append(key)
    return out


def grade_mentions(title: str | None) -> set[tuple[str, float, str]]:
    """TODAS as menções ``<certificadora> <nota>`` do título, normalizadas como
    ``(grader canônico, nota, qualificador)``. Beckett → BGS; CGC 10 seco → GEM."""
    return {(g.grader, g.value, g.qualifier) for g, _ in _find_mentions(title or "")}


def grade_from_title(title: str | None,
                     allow: frozenset[str] | set[str] = DEFAULT_GRADED_ALLOW) -> GradeResult:
    """Classifica o título: "graded" (uma nota só, dentro da allowlist), "raw" (nenhuma
    certificadora citada), "ambiguous" (mais de uma nota distinta) ou "out_of_scope"
    (certificadora desconhecida, sigla sem nota, ou nota fora da allowlist — nesse
    último caso ``grade`` vem preenchida para a entrega mostrar o que foi lido)."""
    title = title or ""
    found = _find_mentions(title)
    distinct = {g for g, _ in found}
    foreign = _unknown_mentions(title, [span for _, span in found])

    if len(distinct) > 1:
        keys = ", ".join(sorted(g.key for g in distinct))
        return GradeResult(None, "ambiguous", f"mais de uma nota no título: {keys}")
    if len(distinct) == 1:
        grade = next(iter(distinct))
        if foreign:
            return GradeResult(None, "ambiguous",
                               f"nota de outra certificadora junto com {grade.key}: "
                               f"{', '.join(foreign)}")
        if is_allowed(grade, allow):
            return GradeResult(grade, "graded", f"nota única no título: {grade.key}")
        return GradeResult(grade, "out_of_scope", f"nota fora da allowlist: {grade.key}")
    if foreign:
        return GradeResult(None, "out_of_scope",
                           f"certificadora fora do escopo: {', '.join(foreign)}")
    alone = _GRADER_ALONE_RE.search(title)
    if alone:
        grader = _GRADER_CANON[alone.group(1).upper()]
        return GradeResult(None, "out_of_scope", f"certificadora sem nota: {grader}")
    return GradeResult(None, "raw", "sem menção de certificadora")


def parse_grades_arg(text: str | None,
                     allow: frozenset[str] | set[str] = DEFAULT_GRADED_ALLOW) -> list[str]:
    """'psa10, cgc 10 pristine, bgs 10 black' -> ['PSA 10', 'CGC 10 PRISTINE',
    'BGS 10 BLACK']. Tolerante a grafia informal; "RAW" passa como marcador do funil
    raw. NUNCA aceita nota desconhecida ou fora da allowlist em silêncio — typo tem
    que errar alto, senão o run viraria um scan vazio "verde"."""
    accepted = ", ".join(sorted(allow) + ["RAW"])
    out: list[str] = []
    for tok in (text or "").split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok.upper() == "RAW":
            key = "RAW"
        else:
            m = _MENTION_RE.fullmatch(tok)
            if not m:
                raise ValueError(
                    f"nota desconhecida em --grades: {tok!r} (aceitas: {accepted})")
            key = _grade_from_match(m, tok).key
            if key not in allow:
                raise ValueError(
                    f"nota fora da allowlist em --grades: {key!r} (aceitas: {accepted})")
        if key not in out:
            out.append(key)
    return out
