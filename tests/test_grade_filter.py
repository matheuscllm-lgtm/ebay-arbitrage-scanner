"""Funil restrito por grade (--grades) + retry de rede do PriceCharting.

O caso que motivou tudo (operador, 2026-09-01): "vamos apenas procurar dentro
do ambito PSA 10". O funil restrito tem que (a) validar a grade pedida em voz
alta (typo nao pode virar scan vazio "verde"), (b) buscar so a empresa pedida
(PSA-10-only nao gasta query com bgs/cgc) e (c) filtrar as demais grades em
silencio -- escopo pedido, nao rejeicao.
"""
import urllib.error

import pytest

from src import pricecharting, scanner, scorer
from src.models import FairValue, WatchCard
from tests.test_scorer import CARD, FAIR, L


# ── parse_grades_arg ─────────────────────────────────────────────────────────

def test_parse_aceita_grafia_informal():
    assert scanner.parse_grades_arg("psa10") == ["PSA 10"]
    assert scanner.parse_grades_arg("PSA 10, cgc 10") == ["PSA 10", "CGC 10"]
    assert scanner.parse_grades_arg("bgs-9.5") == ["BGS 9.5"]
    assert scanner.parse_grades_arg("raw") == ["RAW"]


def test_parse_deduplica():
    assert scanner.parse_grades_arg("psa10, PSA 10") == ["PSA 10"]


def test_parse_erra_alto_em_grade_desconhecida():
    with pytest.raises(ValueError):
        scanner.parse_grades_arg("PSA 8")   # fora do funil do scanner
    with pytest.raises(ValueError):
        scanner.parse_grades_arg("SGC 10")  # empresa fora do escopo


# ── query_suffixes ───────────────────────────────────────────────────────────

def test_suffixes_psa_only_nao_gasta_query_com_bgs_cgc():
    assert scanner.query_suffixes(
        {"graded_only": True, "allowed_grades": ["PSA 10"]}) == [" psa"]


def test_suffixes_duas_empresas():
    assert scanner.query_suffixes(
        {"graded_only": True, "allowed_grades": ["PSA 10", "CGC 10"]}) \
        == [" psa", " cgc"]


def test_suffixes_sem_filtro_mantem_comportamento_atual():
    assert scanner.query_suffixes({"graded_only": True}) \
        == scanner.GRADED_ONLY_SUFFIXES
    assert scanner.query_suffixes({"graded_only": False}) \
        == scanner.GRADE_QUERY_SUFFIXES


def test_suffixes_raw_no_funil_inclui_query_generica():
    assert scanner.query_suffixes(
        {"graded_only": False, "allowed_grades": ["RAW", "PSA 10"]}) \
        == ["", " psa"]


# ── scorer: filtro de grade ──────────────────────────────────────────────────

CFG_PSA10 = {"allowed_grades": ["PSA 10"]}


def test_psa10_passa_no_funil_restrito():
    o = scorer.evaluate(CARD, L("Charizard 4 Base Set PSA 10", 5000.0),
                        FAIR, CFG_PSA10)
    assert o is not None
    assert o.grade == "PSA 10"


def test_psa9_sai_em_silencio_no_funil_psa10():
    # PSA 9 com margem boa (44%) entraria no funil normal; com --grades
    # "PSA 10" e escopo fora do pedido -> None, nao linha rejeitada.
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set PSA 9", 2200.0),
                        FAIR, CFG_PSA10)
    assert o is None


def test_grade_desconhecida_continua_rejeicao_visivel():
    # Grade None (SGC etc.) e sinal de risco, nao de escopo: continua
    # aparecendo como REJEITADO mesmo com funil restrito.
    o = scorer.evaluate(CARD, L("Charizard 4/102 Base Set PSA 8", 500.0),
                        FAIR, CFG_PSA10)
    assert o is None or o.verdict == "REJEITADO"


# ── pricecharting.fetch_page: retry em erro transitorio ──────────────────────

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
    body = pricecharting.fetch_page("https://example.test/x",
                                    cache_dir=str(tmp_path))
    assert body == "<html>ok</html>"
    assert calls["n"] == 3


def test_fetch_page_desiste_depois_das_tentativas(tmp_path, monkeypatch):
    def fake_urlopen(req, timeout=30):
        raise TimeoutError("handshake timeout")

    monkeypatch.setattr(pricecharting.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(pricecharting.time, "sleep", lambda s: None)
    with pytest.raises(TimeoutError):
        pricecharting.fetch_page("https://example.test/y",
                                 cache_dir=str(tmp_path))


def test_fetch_page_nao_repete_erro_definitivo(tmp_path, monkeypatch):
    # 404 nao e transitorio: repetir so martelaria o site a toa.
    calls = {"n": 0}

    def fake_urlopen(req, timeout=30):
        calls["n"] += 1
        raise urllib.error.HTTPError("u", 404, "not found", {}, None)

    monkeypatch.setattr(pricecharting.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(pricecharting.time, "sleep", lambda s: None)
    with pytest.raises(urllib.error.HTTPError):
        pricecharting.fetch_page("https://example.test/z",
                                 cache_dir=str(tmp_path))
    assert calls["n"] == 1


# ── nomenclatura japonesa sem "japanese" no titulo (caso Alakazam SAR) ───────

ALAKAZAM = WatchCard(name="Alakazam ex", set_name="Scarlet & Violet 151",
                     number="201", language="EN", pc_url="")
FAIR_ALAKAZAM = FairValue(prices={"PSA 10": 317.0},
                          sales_per_month={"PSA 10": 30.0})


def test_titulo_com_sar_e_rejeitado_na_watchlist_en():
    # Titulo REAL do scan de 2026-09-01: carta JAPONESA (SAR) sem a palavra
    # "japanese" -- saia como SUSPEITO com margem falsa de 81% contra a
    # referencia EN. Tem que ser REJEITADO com motivo de idioma.
    o = scorer.evaluate(
        ALAKAZAM,
        L("2023 Pokemon Alakazam ex 201/165 Sv: Scarlet & Violet 151 Holo "
          "SAR PSA 10", 175.0),
        FAIR_ALAKAZAM)
    assert o is not None
    assert o.verdict == "REJEITADO"
    assert any("IDIOMA" in f and f.startswith("REJEITAR") for f in o.risk_flags)


def test_sir_em_ingles_nao_dispara_o_guard():
    o = scorer.evaluate(
        ALAKAZAM,
        L("Alakazam ex 201/165 Scarlet & Violet 151 SIR PSA 10", 220.0),
        FAIR_ALAKAZAM)
    assert o is not None
    assert not any(f.startswith("REJEITAR IDIOMA") for f in o.risk_flags)


def test_english_explicito_desarma_o_indicio():
    from src import title_parser
    assert title_parser.jp_nomenclature_hint("Alakazam SAR PSA 10")
    assert not title_parser.jp_nomenclature_hint("Alakazam SAR English PSA 10")
    assert title_parser.jp_nomenclature_hint("Charizard sv2a 201/165 PSA 10")
    assert not title_parser.jp_nomenclature_hint("Charizard ex Obsidian Flames 223 PSA 10")


def test_sar_sai_da_mediana_de_mercado():
    # O prefixo REJEITAR tambem exclui a linha da mediana usada no sanity
    # check da referencia (senao preco JP poluiria a mediana EN).
    from src import scanner as scn
    listings = [
        L("Alakazam ex 201/165 SAR PSA 10", 175.0),
        L("Alakazam ex 201/165 SIR PSA 10", 300.0, item_id="2"),
    ]
    asks = scn._clean_ask_prices(ALAKAZAM, listings)
    assert asks.get("PSA 10") == [300.0]
