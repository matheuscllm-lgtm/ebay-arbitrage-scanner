"""Nota de slab a partir do TITULO do anuncio (src/grading.py).

Modelo portado do scanner-comc (allowlist / chave / coluna PriceCharting);
parse adaptado a titulos livres do eBay. Tudo offline.
"""
import dataclasses
import re

import pytest

from src import grading as g
from src.grading import Grade, GradeResult


# ── provenance ───────────────────────────────────────────────────────────────

def test_cabecalho_declara_origem_do_modelo():
    assert "Modelo portado de scanner-comc/comc_scanner/grading.py @ dd952ba" in g.__doc__


# ── Grade: key / label ───────────────────────────────────────────────────────

@pytest.mark.parametrize("grade,key,label", [
    (Grade("PSA", 10.0), "PSA 10", "PSA 10"),
    (Grade("PSA", 9.0), "PSA 9", "PSA 9"),
    (Grade("CGC", 10.0, "GEM"), "CGC 10 GEM", "CGC 10 Gem Mint"),
    (Grade("CGC", 10.0, "PRISTINE"), "CGC 10 PRISTINE", "CGC 10 Pristine"),
    (Grade("BGS", 10.0, "BLACK"), "BGS 10 BLACK", "BGS 10 Black Label"),
    (Grade("BGS", 10.0), "BGS 10", "BGS 10"),
    (Grade("TAG", 9.5), "TAG 9.5", "TAG 9.5"),
    (Grade("SGC", 9.5), "SGC 9.5", "SGC 9.5"),
])
def test_key_e_label(grade, key, label):
    assert grade.key == key
    assert grade.label == label


def test_grade_e_imutavel():
    grade = Grade("PSA", 10.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        grade.value = 9.0


# ── allowlist ────────────────────────────────────────────────────────────────

def test_allowlist_default():
    assert g.DEFAULT_GRADED_ALLOW == frozenset({
        "PSA 8", "PSA 9", "PSA 10",
        "CGC 9", "CGC 9.5", "CGC 10 GEM", "CGC 10 PRISTINE",
        "BGS 9", "BGS 9.5", "BGS 10", "BGS 10 BLACK",
        "SGC 9", "SGC 9.5", "SGC 10",
        "TAG 9.5", "TAG 10",
    })


def test_is_allowed():
    assert g.is_allowed(Grade("PSA", 10.0))
    assert g.is_allowed(Grade("CGC", 10.0, "GEM"))
    assert not g.is_allowed(Grade("PSA", 7.0))
    assert not g.is_allowed(Grade("CGC", 10.0))       # CGC 10 sem qualificador nao e chave
    assert not g.is_allowed(None)
    assert g.is_allowed(Grade("PSA", 7.0), allow=frozenset({"PSA 7"}))
    assert not g.is_allowed(Grade("PSA", 10.0), allow=frozenset({"PSA 9"}))


# ── pc_price_key: coluna EXATA do PriceCharting ou None ──────────────────────

@pytest.mark.parametrize("grade,column", [
    (Grade("PSA", 10.0), "PSA 10"),
    (Grade("BGS", 10.0), "BGS 10"),
    (Grade("BGS", 10.0, "BLACK"), "BGS 10 BLACK"),
    (Grade("CGC", 10.0, "PRISTINE"), "CGC 10 PRISTINE"),
    (Grade("CGC", 10.0, "GEM"), "CGC 10"),   # rotulo do PC para CGC Gem Mint 10
    (Grade("SGC", 10.0), "SGC 10"),
    (Grade("TAG", 10.0), "TAG 10"),
    # sem coluna propria -> None (nunca bucket generico "Grade 9"/"Grade 9.5")
    (Grade("PSA", 9.0), None),
    (Grade("PSA", 8.0), None),
    (Grade("BGS", 9.5), None),
    (Grade("CGC", 9.5), None),
    (Grade("CGC", 9.0), None),
    (Grade("SGC", 9.5), None),
    (Grade("TAG", 9.5), None),
])
def test_pc_price_key(grade, column):
    assert g.pc_price_key(grade) == column


def test_pc_price_key_nunca_devolve_bucket_generico():
    for grade_key, column in g._PC_EXACT_COLUMN.items():
        assert not re.match(r"grade\b", column, re.I), (grade_key, column)


# ── mentions_black_label ─────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("BGS 10 Black Label", True),
    ("bgs 10 black", True),
    ("BLACK_LABEL", True),
    ("Black Star Promo", False),
    ("Black-Star Promo", False),
    ("Black Dot error", False),
    ("Charizard PSA 10", False),
    ("", False),
    (None, False),
])
def test_mentions_black_label(text, expected):
    assert g.mentions_black_label(text) is expected


# ── grade_mentions: TODAS as mencoes <certificadora> <nota> normalizadas ─────

PSA10 = {("PSA", 10.0, "")}

@pytest.mark.parametrize("title,expected", [
    # PSA — separadores e ordem das palavras
    ("Charizard 4/102 PSA 10", PSA10),
    ("Charizard PSA-10", PSA10),
    ("Charizard PSA:10", PSA10),
    ("Charizard PSA10", PSA10),
    ("Charizard PSA 10 GEM MINT", PSA10),
    ("Charizard PSA GEM MT 10", PSA10),
    ("Charizard PSA GEM MINT 10", PSA10),
    ("Charizard PSA Graded 10", PSA10),
    ("Charizard PSA 10.", PSA10),                       # ponto final nao derruba
    ("Charizard PSA MINT 9", {("PSA", 9.0, "")}),
    ("Charizard PSA NM-MT 8", {("PSA", 8.0, "")}),
    ("Umbreon VMAX PSA 9 Alt Art", {("PSA", 9.0, "")}),
    # PSA nao emite 9.5: "PSA 9.5" NAO vira PSA 9 (vira 9.5 e cai na allowlist)
    ("Card PSA 9.5", {("PSA", 9.5, "")}),
    # CGC — 10 sem "Pristine" = GEM (convencao de titulo do eBay)
    ("Pikachu CGC 10 PRISTINE", {("CGC", 10.0, "PRISTINE")}),
    ("Pikachu CGC PRISTINE 10", {("CGC", 10.0, "PRISTINE")}),
    ("Pikachu CGC 10 GEM MINT", {("CGC", 10.0, "GEM")}),
    ("Pikachu CGC GEM MINT 10", {("CGC", 10.0, "GEM")}),
    ("Pikachu CGC 10", {("CGC", 10.0, "GEM")}),
    ("Pikachu CGC 9.5", {("CGC", 9.5, "")}),
    ("Pikachu CGC 9", {("CGC", 9.0, "")}),
    # BGS / Beckett — 10 so e BLACK com "black label" ou "black" colado
    ("Lugia BGS 10 BLACK LABEL", {("BGS", 10.0, "BLACK")}),
    ("Lugia BGS BLACK LABEL 10", {("BGS", 10.0, "BLACK")}),
    ("Lugia BGS 10 Black", {("BGS", 10.0, "BLACK")}),
    ("Lugia BGS 10 Black - Neo Genesis", {("BGS", 10.0, "BLACK")}),
    ("Lugia BGS BLACK 10", {("BGS", 10.0, "BLACK")}),
    ("Lugia Beckett Black Label 10", {("BGS", 10.0, "BLACK")}),
    ("Lugia BGS PRISTINE 10", {("BGS", 10.0, "")}),
    ("Lugia BGS 10 PRISTINE", {("BGS", 10.0, "")}),
    ("Lugia BGS 10", {("BGS", 10.0, "")}),
    ("Lugia BGS 9.5 GEM MINT", {("BGS", 9.5, "")}),
    ("Lugia Beckett 9.5", {("BGS", 9.5, "")}),
    ("Lugia BGS 8.5", {("BGS", 8.5, "")}),
    ("Black Kyurem EX BGS 10", {("BGS", 10.0, "")}),        # nome da carta != etiqueta
    ("BGS 10 Black Kyurem EX 95/149", {("BGS", 10.0, "")}), # "black" seguido de palavra
    ("Pikachu BGS 10 Black Star Promo", {("BGS", 10.0, "")}),
    ("Pikachu BGS 10 Black Dot Error", {("BGS", 10.0, "")}),
    # TAG / SGC
    ("Charizard TAG 10", {("TAG", 10.0, "")}),
    ("Charizard TAG 9.5", {("TAG", 9.5, "")}),
    ("Charizard SGC 10", {("SGC", 10.0, "")}),
    ("Charizard SGC 10 GEM MT", {("SGC", 10.0, "")}),
    ("Charizard SGC 9.5", {("SGC", 9.5, "")}),
    # mencoes "de comparacao" continuam sendo mencoes (e isso que gera ambiguidade)
    ("Charizard PSA 10 pop 5", PSA10),
    ("Charizard raw, compare PSA 9", {("PSA", 9.0, "")}),
    ("Charizard PSA 10 Base Set PSA 10", PSA10),           # duplicada = uma so
    ("Charizard PSA 10 GEM MINT 10", PSA10),               # "10" solto nao repete
    ("Charizard 4/102 Holo BGS 8.5 NM-MINT FRESH GRADE PSA 9",
     {("BGS", 8.5, ""), ("PSA", 9.0, "")}),
    ("Charizard PSA 9 & PSA 10 lot", {("PSA", 9.0, ""), ("PSA", 10.0, "")}),
    ("Charizard CGC 10 GEM MINT PSA 10", {("CGC", 10.0, "GEM"), ("PSA", 10.0, "")}),
    # NAO sao mencoes
    ("Charizard 10/10 condition", set()),
    ("Charizard 9.5 x 6", set()),
    ("Pikachu SWSH 10", set()),
    ("Pikachu & Zekrom GX Tag Team 33/181 NM", set()),
    ("Charizard 4/102 Base Set Holo NM", set()),
    ("Charizard PSA graded card", set()),                  # certificadora sem nota
    ("Charizard PSA", set()),
    ("Charizard ACE 10", set()),                           # certificadora desconhecida
    ("Charizard GRADED 10", set()),
    ("Pikachu TAG 33/236", set()),                         # nota impossivel (1-10)
    ("Charizard PSA 100", set()),
    ("Charizard PSA 9.8", set()),
    ("Charizard PSAX 10", set()),
    ("", set()),
])
def test_grade_mentions(title, expected):
    assert g.grade_mentions(title) == expected


def test_grade_mentions_aceita_none():
    assert g.grade_mentions(None) == set()


# ── grade_from_title ─────────────────────────────────────────────────────────

def test_graded_psa10():
    r = g.grade_from_title("Charizard Base Set 4/102 PSA 10 GEM MINT")
    assert isinstance(r, GradeResult)
    assert r.status == "graded"
    assert r.grade == Grade("PSA", 10.0)
    assert r.grade.key == "PSA 10"


def test_graded_psa8_esta_na_allowlist():
    r = g.grade_from_title("Charizard PSA 8")
    assert r.status == "graded"
    assert r.grade.key == "PSA 8"


def test_cgc10_sem_pristine_e_gem_por_default():
    r = g.grade_from_title("Pikachu CGC 10")
    assert r.status == "graded"
    assert r.grade.key == "CGC 10 GEM"
    assert r.grade.label == "CGC 10 Gem Mint"


def test_cgc10_pristine():
    r = g.grade_from_title("Pikachu CGC 10 Pristine")
    assert r.status == "graded"
    assert r.grade.key == "CGC 10 PRISTINE"


def test_bgs10_black_label():
    r = g.grade_from_title("Lugia BGS 10 Black Label")
    assert r.status == "graded"
    assert r.grade.key == "BGS 10 BLACK"


def test_raw_sem_mencao():
    r = g.grade_from_title("Charizard 4/102 Base Set Holo NM")
    assert r.status == "raw"
    assert r.grade is None
    assert r.reason


def test_raw_tag_team_nao_e_certificadora():
    # "Tag" e palavra comum (Tag Team) — sozinha, sem nota, nao e sinal de slab.
    r = g.grade_from_title("Pikachu & Zekrom GX Tag Team 33/181 NM")
    assert r.status == "raw"


def test_ambiguous_caso_real_bgs85_psa9():
    r = g.grade_from_title(
        "Charizard 4/102 Holo BGS 8.5 NM-MINT FRESH GRADE PSA 9")
    assert r.status == "ambiguous"
    assert r.grade is None
    assert "BGS 8.5" in r.reason and "PSA 9" in r.reason


def test_ambiguous_duas_notas_psa():
    r = g.grade_from_title("Charizard PSA 9 & PSA 10")
    assert r.status == "ambiguous"


def test_ambiguous_nota_conhecida_mais_certificadora_desconhecida():
    r = g.grade_from_title("Charizard PSA 10 vs ACE 10")
    assert r.status == "ambiguous"
    assert "ACE 10" in r.reason


def test_psa_graded_10_nao_e_ambiguo():
    # "graded" e palavra-ponte de "PSA graded 10"; nao pode ser lida como
    # certificadora desconhecida "GRADED 10" ao mesmo tempo.
    r = g.grade_from_title("Charizard PSA Graded 10")
    assert r.status == "graded"
    assert r.grade.key == "PSA 10"


def test_grader_conhecido_sem_ambiguidade_por_nome_solto():
    # "BGS" solto (sem nota) nao concorre com a nota unica encontrada.
    r = g.grade_from_title("Charizard PSA 10 crossover BGS")
    assert r.status == "graded"
    assert r.grade.key == "PSA 10"


@pytest.mark.parametrize("title,key", [
    ("Charizard PSA 7", "PSA 7"),
    ("Charizard CGC 8", "CGC 8"),
    ("Charizard BGS 8.5", "BGS 8.5"),
    ("Charizard TAG 9", "TAG 9"),
    ("Card PSA 9.5", "PSA 9.5"),
    ("Charizard PSA 1.5", "PSA 1.5"),
])
def test_out_of_scope_nota_fora_da_allowlist(title, key):
    r = g.grade_from_title(title)
    assert r.status == "out_of_scope"
    assert key in r.reason
    assert r.grade is not None and r.grade.key == key   # nota lida fica visivel


@pytest.mark.parametrize("title,grader", [
    ("Charizard ACE 10", "ACE"),
    ("Charizard MNT 10", "MNT"),
    ("Charizard GMA 10", "GMA"),
    ("Charizard HGA 9.5", "HGA"),
    ("Charizard AGS 10", "AGS"),
    ("Charizard GRADED 10 Gem Mint", "GRADED"),
])
def test_out_of_scope_certificadora_desconhecida(title, grader):
    r = g.grade_from_title(title)
    assert r.status == "out_of_scope"
    assert r.grade is None
    assert grader in r.reason


@pytest.mark.parametrize("title,grader", [
    ("Charizard PSA graded card", "PSA"),
    ("Charizard PSA", "PSA"),
    ("Charizard CGC slab", "CGC"),
    ("Charizard Beckett", "BGS"),
    ("Gem Mint 10 PSA", "PSA"),          # nota antes da sigla: nao suportado
])
def test_out_of_scope_certificadora_sem_nota(title, grader):
    r = g.grade_from_title(title)
    assert r.status == "out_of_scope"
    assert r.grade is None
    assert "sem nota" in r.reason
    assert grader in r.reason


def test_allow_customizada():
    r = g.grade_from_title("Charizard PSA 8", allow=frozenset({"PSA 10"}))
    assert r.status == "out_of_scope"
    r = g.grade_from_title("Charizard PSA 7", allow=frozenset({"PSA 7"}))
    assert r.status == "graded"


def test_status_sempre_no_vocabulario():
    for title in ["PSA 10", "NM", "PSA 9 PSA 10", "ACE 10", "PSA", "TAG 9"]:
        assert g.grade_from_title(title).status in {
            "graded", "raw", "ambiguous", "out_of_scope"}


def test_grade_from_title_aceita_none():
    assert g.grade_from_title(None).status == "raw"


# ── parse_grades_arg ─────────────────────────────────────────────────────────

def test_parse_grafia_informal():
    assert g.parse_grades_arg("psa10") == ["PSA 10"]
    assert g.parse_grades_arg("PSA 10, cgc 10") == ["PSA 10", "CGC 10 GEM"]
    assert g.parse_grades_arg("cgc 10 pristine") == ["CGC 10 PRISTINE"]
    assert g.parse_grades_arg("cgc 10 gem mint") == ["CGC 10 GEM"]
    assert g.parse_grades_arg("bgs 10 black") == ["BGS 10 BLACK"]
    assert g.parse_grades_arg("bgs 10 black label") == ["BGS 10 BLACK"]
    assert g.parse_grades_arg("bgs 10") == ["BGS 10"]
    assert g.parse_grades_arg("tag 9.5") == ["TAG 9.5"]
    assert g.parse_grades_arg("bgs-9.5") == ["BGS 9.5"]
    assert g.parse_grades_arg("beckett 9.5") == ["BGS 9.5"]
    assert g.parse_grades_arg("sgc:10") == ["SGC 10"]


def test_parse_raw_passa_como_marcador():
    # RAW nao e nota; e o marcador do funil raw (so tem efeito com --include-raw).
    assert g.parse_grades_arg("raw") == ["RAW"]
    assert g.parse_grades_arg("RAW, psa10") == ["RAW", "PSA 10"]


def test_parse_deduplica_e_ignora_vazios():
    assert g.parse_grades_arg("psa10, PSA 10, ,psa-10") == ["PSA 10"]
    assert g.parse_grades_arg("") == []


@pytest.mark.parametrize("arg", [
    "PSA 7",        # nota fora da allowlist
    "SGC 8",
    "PSA 9.5",      # PSA nao emite 9.5
    "ACE 10",       # certificadora fora do escopo
    "PSA",          # sem nota
    "foo",
    "cgc 10 perfect",   # "perfect" nao e qualificador reconhecido
])
def test_parse_erra_alto(arg):
    with pytest.raises(ValueError) as exc:
        g.parse_grades_arg(arg)
    assert "--grades" in str(exc.value)


def test_parse_erro_cita_o_token_e_as_aceitas():
    with pytest.raises(ValueError) as exc:
        g.parse_grades_arg("PSA 7")
    msg = str(exc.value)
    assert "PSA 7" in msg
    assert "PSA 10" in msg


def test_parse_allow_customizada():
    assert g.parse_grades_arg("psa 7", allow=frozenset({"PSA 7"})) == ["PSA 7"]


# ── contrato do modulo ───────────────────────────────────────────────────────

def test_regexes_compiladas_no_modulo():
    assert isinstance(g._MENTION_RE, re.Pattern)
    assert isinstance(g._UNKNOWN_GRADER_RE, re.Pattern)


def test_sem_dependencia_fora_da_stdlib():
    import inspect
    src = inspect.getsource(g)
    for line in src.splitlines():
        line = line.strip()
        if line.startswith(("import ", "from ")):
            mod = line.split()[1].split(".")[0]
            assert mod in {"re", "dataclasses", "__future__"}, line
