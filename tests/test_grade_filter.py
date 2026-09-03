"""Funil restrito por nota (--grades), sufixos de busca, retry de rede do
PriceCharting (cliente de colunas) e guarda de nomenclatura japonesa.

O caso que motivou o --grades (operador, 2026-09-01): "vamos apenas procurar
dentro do ambito PSA 10". O funil restrito tem que (a) validar a nota pedida em
voz alta (typo nao pode virar scan vazio "verde"), (b) filtrar as demais notas
em silencio -- escopo pedido, nao rejeicao.
"""
import urllib.error

import pytest

from src import pricecharting, scanner, scorer
from src.models import FairValue, WatchCard
from tests.test_scorer import L, REF, FakeRefs, ev


# ── parse_grades_arg (via grading) ───────────────────────────────────────────

def test_parse_aceita_grafia_informal():
    assert scanner.parse_grades_arg("psa10") == ["PSA 10"]
    assert scanner.parse_grades_arg("PSA 10, cgc 10") == ["PSA 10", "CGC 10 GEM"]
    assert scanner.parse_grades_arg("cgc 10 pristine") == ["CGC 10 PRISTINE"]
    assert scanner.parse_grades_arg("bgs-9.5") == ["BGS 9.5"]
    assert scanner.parse_grades_arg("bgs 10 black") == ["BGS 10 BLACK"]
    assert scanner.parse_grades_arg("tag 9.5, sgc 10, psa 8") == ["TAG 9.5", "SGC 10", "PSA 8"]
    assert scanner.parse_grades_arg("raw") == ["RAW"]


def test_parse_deduplica():
    assert scanner.parse_grades_arg("psa10, PSA 10") == ["PSA 10"]


def test_parse_erra_alto_em_nota_fora_da_allowlist():
    for bad in ("PSA 7", "ACE 10", "cgc 8", "PSA 9.5", "bgs 8.5", "tag 9"):
        with pytest.raises(ValueError):
            scanner.parse_grades_arg(bad)


def test_parse_respeita_allowlist_do_config():
    with pytest.raises(ValueError):
        scanner.parse_grades_arg("PSA 9", allow=frozenset({"PSA 10"}))
    assert scanner.parse_grades_arg("PSA 10", allow=frozenset({"PSA 10"})) == ["PSA 10"]


# ── query_suffixes ───────────────────────────────────────────────────────────

def test_default_e_uma_query_generica_por_carta():
    assert scanner.query_suffixes({"graded_only": True}) == [""]
    assert scanner.query_suffixes({"graded_only": False}) == [""]
    assert scanner.query_suffixes({"allowed_grades": ["PSA 10"]}) == [""]


def test_sufixos_legados_por_certificadora():
    legacy = {"grade_query_suffixes": True}
    assert scanner.query_suffixes(dict(legacy, graded_only=True)) == scanner.GRADED_ONLY_SUFFIXES
    assert scanner.query_suffixes(dict(legacy, graded_only=False)) == scanner.GRADE_QUERY_SUFFIXES
    assert scanner.query_suffixes(dict(legacy, graded_only=True,
                                       allowed_grades=["PSA 10"])) == [" psa"]
    assert scanner.query_suffixes(dict(legacy, graded_only=True,
                                       allowed_grades=["PSA 10", "CGC 10 GEM", "TAG 10"])) \
        == [" psa", " cgc", " tag"]
    assert scanner.query_suffixes(dict(legacy, graded_only=False,
                                       allowed_grades=["RAW", "PSA 10"])) == ["", " psa"]


# ── scorer: filtro de nota ───────────────────────────────────────────────────

CFG_PSA10 = {"allowed_grades": ["PSA 10"]}


def test_psa10_passa_no_funil_restrito():
    o = ev("Charizard 4 Base Set PSA 10", 5000.0, cfg=CFG_PSA10)
    assert o is not None and o.grade == "PSA 10"


def test_psa9_sai_em_silencio_no_funil_psa10():
    assert ev("Charizard 4/102 Base Set PSA 9", 2200.0, cfg=CFG_PSA10) is None


def test_nota_fora_do_escopo_nunca_vira_linha():
    # Sem nota unica dentro da allowlist nao ha venda comparavel -> funil, nao linha.
    assert ev("Charizard 4/102 Base Set PSA 7", 500.0, cfg=CFG_PSA10) is None


# ── pricecharting.fetch_page (cliente de colunas): retry em erro transitorio ─

class _FakeResponse:
    headers = {}

    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_fetch_page_sobrevive_a_timeout_transitorio(tmp_path, monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(req, timeout=30):
        calls["n"] += 1
        if calls["n"] < 3:
            raise TimeoutError("_ssl.c:999: The handshake operation timed out")
        return _FakeResponse(b"<html>ok</html>")

    monkeypatch.setattr(pricecharting.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(pricecharting.time, "sleep", lambda s: None)
    body = pricecharting.fetch_page("https://example.test/x", cache_dir=str(tmp_path))
    assert body == "<html>ok</html>"
    assert calls["n"] == 3


def test_fetch_page_desiste_depois_das_tentativas(tmp_path, monkeypatch):
    def fake_urlopen(req, timeout=30):
        raise TimeoutError("handshake timeout")

    monkeypatch.setattr(pricecharting.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(pricecharting.time, "sleep", lambda s: None)
    with pytest.raises(TimeoutError):
        pricecharting.fetch_page("https://example.test/y", cache_dir=str(tmp_path))


def test_fetch_page_nao_repete_erro_definitivo(tmp_path, monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(req, timeout=30):
        calls["n"] += 1
        raise urllib.error.HTTPError("u", 404, "not found", {}, None)

    monkeypatch.setattr(pricecharting.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(pricecharting.time, "sleep", lambda s: None)
    with pytest.raises(urllib.error.HTTPError):
        pricecharting.fetch_page("https://example.test/z", cache_dir=str(tmp_path))
    assert calls["n"] == 1


# ── nomenclatura japonesa sem "japanese" no titulo (caso Alakazam SAR) ───────

ALAKAZAM = WatchCard(
    name="Alakazam ex", set_name="Scarlet & Violet 151", number="201", language="EN",
    pc_url="https://www.pricecharting.com/game/pokemon-scarlet-violet-151/alakazam-ex-201")
REFS_ALAKAZAM = FakeRefs(slab={"PSA 10": REF(317.0, what="PSA 10")},
                         pc_url=ALAKAZAM.pc_url)
FAIR_ALAKAZAM = FairValue(prices={"PSA 10": 317.0}, sales_per_month={"PSA 10": 30.0})


def test_titulo_com_sar_e_rejeitado_na_watchlist_en():
    # Titulo REAL do scan de 2026-09-01: carta JAPONESA (SAR) sem a palavra
    # "japanese" -- saia como SUSPEITO com margem falsa de 81% contra a
    # referencia EN. Tem que ser REJEITADO com motivo de idioma.
    o = scorer.evaluate(
        ALAKAZAM,
        L("2023 Pokemon Alakazam ex 201/165 Sv: Scarlet & Violet 151 Holo SAR PSA 10", 175.0),
        FAIR_ALAKAZAM, refs=REFS_ALAKAZAM)
    assert o is not None and o.verdict == "REJEITADO"
    assert any("IDIOMA" in f and f.startswith("REJEITAR") for f in o.risk_flags)


def test_sir_em_ingles_nao_dispara_o_guard():
    o = scorer.evaluate(
        ALAKAZAM, L("Alakazam ex 201/165 Scarlet & Violet 151 SIR PSA 10", 220.0),
        FAIR_ALAKAZAM, refs=REFS_ALAKAZAM)
    assert o is not None
    assert not any(f.startswith("REJEITAR IDIOMA") for f in o.risk_flags)


def test_english_explicito_desarma_o_indicio():
    from src import title_parser
    assert title_parser.jp_nomenclature_hint("Alakazam SAR PSA 10")
    assert not title_parser.jp_nomenclature_hint("Alakazam SAR English PSA 10")
    assert title_parser.jp_nomenclature_hint("Charizard sv2a 201/165 PSA 10")
    assert not title_parser.jp_nomenclature_hint("Charizard ex Obsidian Flames 223 PSA 10")


def test_sar_sai_da_mediana_de_mercado():
    listings = [
        L("Alakazam ex 201/165 SAR PSA 10", 175.0),
        L("Alakazam ex 201/165 SIR PSA 10", 300.0, item_id="2"),
    ]
    asks = scanner._clean_ask_prices(ALAKAZAM, listings)
    assert asks.get("PSA 10") == [300.0]
