"""BOM/zero-width na credencial eBay -> sanitizada ao ler (erro recorrente nº1).

Uma EBAY_CLIENT_ID / EBAY_CLIENT_SECRET colada com BOM (U+FEFF) ou zero-width
(U+200B) -- comum ao copiar de alguns editores -- geraria um header
Authorization Basic invalido (-> eBay 401, "configurado mas nao autentica").
O cliente limpa esses caracteres ao ler do ambiente; `.strip()` sozinho NAO
remove BOM/zero-width (nao sao whitespace).

Usa chr(0xFEFF)/chr(0x200B) -- NUNCA o caractere literal no fonte do teste.
"""
from src.ebay_api import EbayClient, _clean_secret

BOM = chr(0xFEFF)    # U+FEFF byte order mark
ZWSP = chr(0x200B)   # U+200B zero-width space


def test_clean_secret_strips_bom_and_zero_width():
    assert _clean_secret(BOM + "abc123") == "abc123"
    assert _clean_secret("abc123" + ZWSP) == "abc123"
    assert _clean_secret(BOM + " abc " + ZWSP) == "abc"


def test_clean_secret_only_invisible_becomes_empty():
    # Chave que e SO BOM/zero-width/espaco -> vazia. Assim ela cai limpo no
    # modo pricing-only em vez de passar como "configurada" e tomar 401.
    assert _clean_secret(BOM + ZWSP + "  ") == ""
    assert _clean_secret("") == ""
    assert _clean_secret(None) == ""


def test_clean_secret_preserves_normal_key():
    assert _clean_secret("MyApp-PRD-1a2b3c4d") == "MyApp-PRD-1a2b3c4d"


def test_client_sanitizes_constructor_args():
    c = EbayClient(client_id=BOM + "id-1", client_secret="secret-1" + ZWSP)
    assert c.client_id == "id-1"
    assert c.client_secret == "secret-1"
    assert c.configured is True


def test_client_sanitizes_env_vars(monkeypatch):
    monkeypatch.setenv("EBAY_CLIENT_ID", BOM + "envid")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "envsecret" + ZWSP)
    c = EbayClient()
    assert c.client_id == "envid"
    assert c.client_secret == "envsecret"
    assert c.configured is True


def test_client_bom_only_credential_not_configured(monkeypatch):
    # Credencial que e SO um invisivel -> apos limpar, vazia -> nao configurado
    # -> modo pricing-only limpo, sem 401 confuso.
    monkeypatch.setenv("EBAY_CLIENT_ID", BOM)
    monkeypatch.setenv("EBAY_CLIENT_SECRET", ZWSP)
    c = EbayClient()
    assert c.client_id == ""
    assert c.client_secret == ""
    assert c.configured is False
