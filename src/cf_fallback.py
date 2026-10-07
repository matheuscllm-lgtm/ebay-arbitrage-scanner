"""Rota reserva para páginas atrás de desafio JavaScript do Cloudflare.

Desde 06/10/2026 o PriceCharting devolve HTTP 403 "Just a moment..." (cabeçalho
``cf-mitigated: challenge``) para urllib, curl e clientes com TLS de navegador.
O Firecrawl (``/v2/scrape`` com ``rawHtml``) resolve o desafio e devolve o HTML
original — os parsers de ``pc_sales``/``pricecharting`` leem a página sem mudança.

Custo: 1 crédito por página. A rota só entra quando a requisição direta recebe
403 e ``FIRECRAWL_API_KEY`` está no ambiente; sem chave, o comportamento antigo
(falha imediata) é mantido. A chave nunca aparece em mensagens de erro.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

API_URL = "https://api.firecrawl.dev/v2/scrape"
ENV_KEY = "FIRECRAWL_API_KEY"
TIMEOUT_SECONDS = 90
MIN_PAGE_BYTES = 2000  # corpo menor = erro/vazio (mesmo piso de pc_sales)
_BLOCK_TITLE_RE = re.compile(r"<title>\s*(?:Just a moment|Attention Required|Access denied)", re.I)


class FirecrawlError(RuntimeError):
    """Falha da rota reserva (quota, HTTP, resposta sem rawHtml)."""


def available() -> bool:
    return bool(os.environ.get(ENV_KEY))


def fetch_raw_html(url: str, timeout: int = TIMEOUT_SECONDS) -> str:
    """HTML bruto de ``url`` via Firecrawl (``maxAge=0``: sempre coleta nova)."""
    key = os.environ.get(ENV_KEY)
    if not key:
        raise FirecrawlError(f"{ENV_KEY} ausente")
    payload = json.dumps({"url": url, "formats": ["rawHtml"], "maxAge": 0}).encode()
    req = urllib.request.Request(API_URL, data=payload, method="POST", headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        raise FirecrawlError(f"Firecrawl HTTP {exc.code} em {url}") from None
    except (OSError, ValueError) as exc:
        raise FirecrawlError(f"Firecrawl indisponível ({type(exc).__name__}) em {url}") from None
    if not isinstance(body, dict) or not body.get("success"):
        raise FirecrawlError(f"Firecrawl respondeu sem sucesso em {url}")
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    status = meta.get("statusCode", 200)
    if status != 200:
        # 404/403 renderizado nunca pode virar "sem vendas": preserva a distinção erro × vazio.
        raise FirecrawlError(f"Firecrawl: alvo devolveu HTTP {status} em {url}")
    html = data.get("rawHtml")
    if not isinstance(html, str) or len(html) < MIN_PAGE_BYTES or _BLOCK_TITLE_RE.search(html):
        raise FirecrawlError(f"Firecrawl devolveu página de bloqueio/vazia ({len(html) if isinstance(html, str) else 0} B) em {url}")
    return html
