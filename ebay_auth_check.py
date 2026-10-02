"""Verificação mínima das credenciais eBay, segura para log público do GitHub Actions.

Faz no máximo 1 token OAuth + 1 busca na Browse API (limit=1, 1 página) e imprime
apenas booleanos, contagem de chamadas e o tipo do erro. Nunca imprime preço, título,
itemId, URL, token, credencial nem mensagem de erro (que pode conter a URL da busca).
Não grava arquivo: o resultado é só o código de saída e a linha JSON no log.

Códigos de saída: 0 = token e busca OK; 1 = credencial ausente ou recusada;
2 = token OK, busca falhou.
"""
import json
import sys

from src.ebay_api import EbayApiError, EbayAuthError, EbayClient

QUERY = "pokemon psa 10"


def check(client=None):
    client = client or EbayClient()
    result = {
        "credentials_present": client.configured,
        "token_ok": False,
        "search_ok": False,
        "items_received": False,
        "search_calls": 0,
        "error_type": None,
    }
    if not client.configured:
        result["error_type"] = "MissingCredentials"
        return result, 1
    client.max_calls = 1
    try:
        client._get_token()
        result["token_ok"] = True
        client.search(QUERY, limit=1, max_pages=1)
        result["search_ok"] = True
        result["items_received"] = client.fetched > 0
        code = 0
    except EbayAuthError:
        result["error_type"] = "EbayAuthError"
        code = 1
    except EbayApiError as exc:
        result["error_type"] = type(exc).__name__
        code = 2
    except Exception as exc:  # rede/parse inesperado: só o tipo, nunca a mensagem
        result["error_type"] = type(exc).__name__
        code = 2 if result["token_ok"] else 1
    result["search_calls"] = client.calls
    return result, code


def main():
    result, code = check()
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
