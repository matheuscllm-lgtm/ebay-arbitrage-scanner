"""Cliente da eBay Browse API (src/ebay_api.py) -- offline.

Cobre: parse puro de um payload REAL (fixture sanitizada, ver abaixo), filtro
default de preco fixo, paginacao por offset com dedupe de itemId, paradas
(pagina curta / offset >= total / max_pages), validacao de limit, retry em
429/5xx com backoff, erro 4xx imediato e o contador de chamadas (orcamento
gratis da Browse API: 5.000/dia).

Fixture `tests/fixtures/ebay_search_charizard_base_psa.json`: captura REAL da
Browse API em 2026-09-03 (query "pokemon charizard 4/102 base set psa",
limit=50, preco fixo, EUA), cortada para 25 itens; `seller.username` foi
substituido por `seller_<n>`. Estrutura e demais campos estao intactos.

Rede e token sao SEMPRE monkeypatchados: nenhum teste aqui toca a internet.
"""
import json
import urllib.error
import urllib.parse
from pathlib import Path

import pytest

from src import ebay_api
from src.ebay_api import (EbayApiError, EbayAuthError, EbayClient,
                          parse_search_payload)

FIXTURE = Path(__file__).parent / "fixtures" / "ebay_search_charizard_base_psa.json"


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ── infra de fake ────────────────────────────────────────────────────────────

class _FakeResponse:
    def __init__(self, payload):
        self._body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _item(item_id, price=100.0, country="US", **extra):
    d = {
        "itemId": item_id,
        "title": f"Charizard {item_id}",
        "price": {"value": f"{price:.2f}", "currency": "USD"},
        "buyingOptions": ["FIXED_PRICE"],
        "condition": "Graded",
        "conditionId": "2750",
        "itemLocation": {"postalCode": "981**", "country": country},
        "seller": {"username": "seller_x", "feedbackPercentage": "99.5",
                   "feedbackScore": 100},
        "itemWebUrl": f"https://www.ebay.com/itm/{item_id}",
        "shippingOptions": [{"shippingCost": {"value": "0.00", "currency": "USD"}}],
    }
    d.update(extra)
    return d


def _page(items, total, limit=200, offset=0):
    return {"href": "https://api.ebay.com/x", "total": total, "limit": limit,
            "offset": offset, "itemSummaries": items}


def _query(url):
    return {k: v[0] for k, v in
            urllib.parse.parse_qs(urllib.parse.urlparse(url).query).items()}


def _install(monkeypatch, handler):
    """Instala urlopen falso. handler(offset, url) -> payload (ou levanta).

    Devolve a lista de URLs requisitadas, na ordem.
    """
    urls = []

    def fake_urlopen(req, timeout=30):
        url = req.full_url
        urls.append(url)
        assert req.get_header("Authorization") == "Bearer tok"
        offset = int(_query(url).get("offset", "0"))
        return _FakeResponse(handler(offset, url))

    monkeypatch.setattr(ebay_api.urllib.request, "urlopen", fake_urlopen)
    return urls


@pytest.fixture
def client(monkeypatch):
    c = EbayClient(client_id="id", client_secret="secret")
    monkeypatch.setattr(EbayClient, "_get_token", lambda self: "tok")
    monkeypatch.setattr(ebay_api.time, "sleep", lambda s: None)
    return c


# ── parse puro da fixture REAL ───────────────────────────────────────────────

def test_fixture_is_sanitized():
    p = load_fixture()
    items = p["itemSummaries"]
    assert 0 < len(items) <= 25
    assert all(i["seller"]["username"].startswith("seller_") for i in items)
    assert not any("sellerAccountType" in i["seller"] for i in items)


def test_fixture_top_level_structure():
    p = load_fixture()
    assert p["total"] == 349
    assert p["limit"] == 50
    assert p["offset"] == 0
    assert "next" in p and "offset=50" in p["next"]


def test_parse_fixture_count_and_first_item():
    p = load_fixture()
    listings = parse_search_payload(p)
    assert len(listings) == len(p["itemSummaries"]) == 25
    first = listings[0]
    assert first.item_id == "v1|257719387397|0"
    assert first.title.startswith("Pokemon TCG Charizard 4/102")
    assert first.price == 195.0
    assert first.shipping == 6.99
    assert first.currency == "USD"
    assert first.buying_option == "FIXED_PRICE"
    assert first.condition == "Graded"
    assert first.country == "US"
    assert first.seller_feedback_pct == 100.0
    assert first.seller_feedback_score == 309
    assert first.url.startswith("https://www.ebay.com/itm/257719387397")
    assert first.image_url.startswith("https://i.ebayimg.com/")
    assert first.top_rated is False
    # $195 < $250 -> fora do Authenticity Guarantee por politica.
    assert first.authenticity_guarantee is False


def test_parse_fixture_all_us_fixed_price_graded():
    listings = parse_search_payload(load_fixture())
    assert all(l.country == "US" for l in listings)
    assert all(l.buying_option == "FIXED_PRICE" for l in listings)
    assert all(l.condition == "Graded" for l in listings)
    assert len({l.item_id for l in listings}) == 25


def test_parse_fixture_ag_requires_explicit_metadata():
    listings = parse_search_payload(load_fixture())
    for l in listings:
        assert l.authenticity_guarantee is False


def test_parse_shipping_missing_cost_stays_unknown():
    listings = parse_search_payload(load_fixture())
    no_cost = [i for i in load_fixture()["itemSummaries"]
               if not (i["shippingOptions"][0].get("shippingCost") or {}).get("value")]
    assert len(no_cost) == 6
    by_id = {l.item_id: l for l in listings}
    assert all(by_id[i["itemId"]].shipping is None for i in no_cost)


def test_parse_ag_from_qualified_programs_or_policy():
    payload = _page([
        _item("us-cheap", price=100.0),
        _item("us-expensive", price=300.0),
        _item("gb-expensive", price=300.0, country="GB"),
        _item("us-flagged", price=50.0,
              qualifiedPrograms=["AUTHENTICITY_GUARANTEE"]),
    ], total=4)
    ag = {l.item_id: l.authenticity_guarantee
          for l in parse_search_payload(payload)}
    assert ag == {"us-cheap": False, "us-expensive": False,
                  "gb-expensive": False, "us-flagged": True}


def test_parse_auction_and_top_rated():
    payload = _page([
        _item("a", buyingOptions=["AUCTION"], topRatedBuyingExperience=True),
        _item("b", buyingOptions=["FIXED_PRICE", "BEST_OFFER"]),
    ], total=2)
    a, b = parse_search_payload(payload)
    assert a.buying_option == "AUCTION" and a.top_rated is True
    assert b.buying_option == "FIXED_PRICE" and b.top_rated is False


def test_parse_empty_payload():
    assert parse_search_payload({}) == []
    assert parse_search_payload({"total": 0, "itemSummaries": []}) == []


# ── montagem da requisicao ───────────────────────────────────────────────────

def test_search_default_filter_is_fixed_price_us(client, monkeypatch):
    urls = _install(monkeypatch, lambda off, url: _page([_item("x")], total=1))
    client.search("pokemon charizard", min_price=10.0)
    q = _query(urls[0])
    assert urls[0].startswith(ebay_api.SEARCH_URL + "?")
    filters = q["filter"].split(",")
    assert "buyingOptions:{FIXED_PRICE}" in filters
    assert "itemLocationCountry:US" in filters
    assert "price:[10..]" in filters
    assert "priceCurrency:USD" in filters
    assert q["limit"] == "200"
    assert q["offset"] == "0"
    assert q["sort"] == "price"
    assert q["category_ids"] == ebay_api.CCG_CATEGORY_ID
    assert q["q"] == "pokemon charizard"


def test_search_fixed_price_only_false_omits_filter(client, monkeypatch):
    urls = _install(monkeypatch, lambda off, url: _page([], total=0))
    client.search("q", fixed_price_only=False)
    assert "buyingOptions" not in _query(urls[0])["filter"]


def test_search_min_max_price_and_country(client, monkeypatch):
    urls = _install(monkeypatch, lambda off, url: _page([], total=0))
    client.search("q", min_price=25.0, max_price=500.0, location_country="")
    filters = _query(urls[0])["filter"].split(",")
    assert "price:[25..500]" in filters
    assert not any(f.startswith("itemLocationCountry") for f in filters)


def test_search_limit_over_200_raises(client, monkeypatch):
    urls = _install(monkeypatch, lambda off, url: _page([], total=0))
    with pytest.raises(ValueError):
        client.search("q", limit=201)
    with pytest.raises(ValueError):
        client.search("q", limit=0)
    assert urls == []
    assert client.calls == 0


def test_search_scanner_compat_signature(client, monkeypatch):
    # scanner.py chama search(query, min_price=...) -- tem que seguir valendo.
    _install(monkeypatch, lambda off, url: _page([_item("x", price=42.0)], total=1))
    listings = client.search("pokemon charizard 4 base set psa", min_price=10.0)
    assert [l.price for l in listings] == [42.0]


# ── paginacao ────────────────────────────────────────────────────────────────

def test_search_paginates_offsets_and_dedupes(client, monkeypatch):
    pages = {
        0: [_item(f"a{i}") for i in range(200)],
        # "a5" repetido entre paginas (a ordenacao por preco pode deslocar
        # itens entre requisicoes) -> deve entrar UMA vez so.
        200: [_item(f"b{i}") for i in range(199)] + [_item("a5")],
        400: [_item(f"c{i}") for i in range(50)],
    }
    urls = _install(monkeypatch,
                    lambda off, url: _page(pages[off], total=450, offset=off))
    listings = client.search("q", limit=200, max_pages=3)
    assert [int(_query(u)["offset"]) for u in urls] == [0, 200, 400]
    assert client.calls == 3
    assert client.last_total == 450
    ids = [l.item_id for l in listings]
    assert len(ids) == 449
    assert len(set(ids)) == 449
    assert ids.count("a5") == 1


def test_search_stops_on_short_page(client, monkeypatch):
    urls = _install(monkeypatch,
                    lambda off, url: _page([_item(f"s{i}") for i in range(30)],
                                           total=1000))
    listings = client.search("q", limit=200, max_pages=3)
    assert len(listings) == 30
    assert len(urls) == 1
    assert client.calls == 1


def test_search_stops_when_offset_reaches_total(client, monkeypatch):
    # 2 paginas cheias e total=400 -> offset 400 >= total -> nao pede a 3a.
    urls = _install(monkeypatch,
                    lambda off, url: _page([_item(f"p{off}-{i}") for i in range(200)],
                                           total=400, offset=off))
    listings = client.search("q", limit=200, max_pages=3)
    assert len(listings) == 400
    assert [int(_query(u)["offset"]) for u in urls] == [0, 200]
    assert client.calls == 2


def test_search_respects_max_pages(client, monkeypatch):
    urls = _install(monkeypatch,
                    lambda off, url: _page([_item(f"p{off}-{i}") for i in range(200)],
                                           total=10000, offset=off))
    listings = client.search("q", limit=200, max_pages=2)
    assert len(listings) == 400
    assert len(urls) == 2
    assert client.calls == 2
    client.search("q", limit=200, max_pages=1)
    assert client.calls == 3


def test_search_uses_limit_in_pagination(client, monkeypatch):
    urls = _install(monkeypatch,
                    lambda off, url: _page([_item(f"p{off}-{i}") for i in range(50)],
                                           total=349, offset=off))
    listings = client.search("q", limit=50, max_pages=3)
    assert [int(_query(u)["offset"]) for u in urls] == [0, 50, 100]
    assert all(_query(u)["limit"] == "50" for u in urls)
    assert len(listings) == 150
    assert client.last_total == 349


# ── retry / erros ────────────────────────────────────────────────────────────

def _http_error(code, msg="err"):
    return urllib.error.HTTPError("https://api.ebay.com/x", code, msg, {}, None)


def test_search_retries_on_429_then_succeeds(client, monkeypatch):
    sleeps = []
    monkeypatch.setattr(ebay_api.time, "sleep", lambda s: sleeps.append(s))
    n = {"i": 0}

    def handler(off, url):
        n["i"] += 1
        if n["i"] == 1:
            raise _http_error(429, "Too Many Requests")
        return _page([_item("ok")], total=1)

    _install(monkeypatch, handler)
    listings = client.search("q")
    assert [l.item_id for l in listings] == ["ok"]
    assert client.calls == 2          # a tentativa que falhou tambem gastou cota
    assert sleeps == [2]


def test_search_5xx_persistent_raises_api_error(client, monkeypatch):
    sleeps = []
    monkeypatch.setattr(ebay_api.time, "sleep", lambda s: sleeps.append(s))

    def handler(off, url):
        raise _http_error(503, "Service Unavailable")

    _install(monkeypatch, handler)
    with pytest.raises(EbayApiError):
        client.search("q")
    assert client.calls == 3
    assert sleeps == [2, 4]


def test_search_other_4xx_raises_immediately(client, monkeypatch):
    sleeps = []
    monkeypatch.setattr(ebay_api.time, "sleep", lambda s: sleeps.append(s))

    def handler(off, url):
        raise _http_error(400, "Bad Request")

    _install(monkeypatch, handler)
    with pytest.raises(EbayApiError) as ei:
        client.search("q")
    assert "400" in str(ei.value)
    assert client.calls == 1
    assert sleeps == []


def test_search_transient_network_error_retries(client, monkeypatch):
    n = {"i": 0}

    def handler(off, url):
        n["i"] += 1
        if n["i"] < 3:
            raise TimeoutError("_ssl.c:999: The handshake operation timed out")
        return _page([_item("late")], total=1)

    _install(monkeypatch, handler)
    listings = client.search("q")
    assert [l.item_id for l in listings] == ["late"]
    assert client.calls == 3


def test_api_error_is_not_auth_error():
    assert not issubclass(EbayApiError, EbayAuthError)
    assert not issubclass(EbayAuthError, EbayApiError)


def test_token_401_raises_auth_error(monkeypatch):
    c = EbayClient(client_id="id", client_secret="secret")

    def fake_urlopen(req, timeout=30):
        assert req.full_url == ebay_api.TOKEN_URL
        raise _http_error(401, "Unauthorized")

    monkeypatch.setattr(ebay_api.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(EbayAuthError):
        c.search("q")
    assert c.calls == 0   # token nao e chamada de busca


def test_calls_counter_accumulates_across_searches(client, monkeypatch):
    _install(monkeypatch, lambda off, url: _page([_item("x")], total=1))
    assert client.calls == 0
    client.search("a")
    client.search("b")
    assert client.calls == 2
    assert client.last_total == 1


def test_search_401_raises_auth_error(client, monkeypatch):
    # Review Codex 2026-09-03: 401/403 na BUSCA e credencial invalida -> aborta,
    # nao "1 erro transitorio de 3".
    def handler(offset, url):
        raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, None)
    _install(monkeypatch, handler)
    with pytest.raises(ebay_api.EbayAuthError):
        client.search("q")
    assert client.calls == 1


def test_search_counts_cross_page_duplicates(client, monkeypatch):
    def handler(offset, url):
        if offset == 0:
            return _page([_item(str(i)) for i in range(200)], 400, offset=0)
        return _page([_item("199")] + [_item(str(i)) for i in range(200, 299)], 400, offset=200)
    _install(monkeypatch, handler)
    out = client.search("q", limit=200, max_pages=3)
    assert len(out) == 299
    assert client.dedup_dropped == 1
