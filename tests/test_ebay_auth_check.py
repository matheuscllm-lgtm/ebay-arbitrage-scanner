"""ebay_auth_check: só booleanos/contagens no log público, nunca preço nem mensagem."""
import json

import ebay_auth_check
from src.ebay_api import EbayApiError, EbayAuthError, EbayClient

ALLOWED_KEYS = {"credentials_present", "token_ok", "search_ok", "items_received",
                "search_calls", "error_type"}


def _client(monkeypatch, token=None, search=None):
    client = EbayClient(client_id="id", client_secret="secret")
    monkeypatch.setattr(client, "_get_token", token or (lambda: "tok"))

    def fake_search(query, limit, max_pages):
        assert limit == 1 and max_pages == 1
        client.calls += 1
        if search:
            search()
        client.fetched = 1
        return []

    monkeypatch.setattr(client, "search", fake_search)
    return client


def test_success_reports_only_booleans(monkeypatch):
    result, code = ebay_auth_check.check(_client(monkeypatch))
    assert code == 0
    assert set(result) == ALLOWED_KEYS
    assert result == {"credentials_present": True, "token_ok": True, "search_ok": True,
                      "items_received": True, "search_calls": 1, "error_type": None}


def test_missing_credentials_makes_no_call(monkeypatch):
    monkeypatch.delenv("EBAY_CLIENT_ID", raising=False)
    monkeypatch.delenv("EBAY_CLIENT_SECRET", raising=False)
    result, code = ebay_auth_check.check(EbayClient())
    assert code == 1
    assert result["error_type"] == "MissingCredentials" and result["search_calls"] == 0


def test_auth_error_hides_message(monkeypatch, capsys):
    def refuse():
        raise EbayAuthError("HTTP 401 SECRET-ish detail https://api.ebay.com/x?q=1")

    monkeypatch.setattr(ebay_auth_check, "EbayClient",
                        lambda: _client(monkeypatch, token=refuse))
    assert ebay_auth_check.main() == 1
    out = capsys.readouterr().out
    assert "SECRET" not in out and "http" not in out
    assert json.loads(out)["error_type"] == "EbayAuthError"


def test_search_error_after_token_is_code_2(monkeypatch):
    def boom():
        raise EbayApiError("HTTP 500 em https://api.ebay.com/...")

    result, code = ebay_auth_check.check(_client(monkeypatch, search=boom))
    assert code == 2
    assert result["token_ok"] and not result["search_ok"]
    assert result["error_type"] == "EbayApiError"
