"""Cliente do PriceCharting (fonte gratuita de preco justo).

O PriceCharting agrega as vendas concluidas do eBay por grade. A pagina publica
de cada carta traz:
- preco justo por grade (Ungraded, Grade 1-9.5, PSA 10, BGS 10, CGC 10, SGC 10...)
- variacao recente do preco (tendencia)
- volume de vendas por grade (liquidez)

Scrape leve com urllib (validado 2026-06-09: HTTP 200 sem bloqueio), com cache
em disco de 24h para nao martelar o site.
"""
import gzip
import html as html_mod
import json
import os
import re
import time
import urllib.parse
import urllib.request

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip",
}

CACHE_TTL_SECONDS = 24 * 3600
REQUEST_GAP_SECONDS = 2.0  # pausa entre requisicoes (educacao com o site)

# A tabela principal (#price_data) usa ids herdados de video game; em cartas
# eles significam grades:
MAIN_TABLE_GRADE_BY_ID = {
    "used_price": "RAW",        # Ungraded
    "complete_price": "GRADE 7",
    "new_price": "GRADE 8",
    "graded_price": "PSA 9",    # "Grade 9"
    "box_only_price": "GRADE 9.5",
    "manual_only_price": "PSA 10",
}

# Normalizacao dos rotulos da tabela "Full Price Guide".
FULL_TABLE_GRADE_BY_LABEL = {
    "Ungraded": "RAW",
    "Grade 7": "GRADE 7",
    "Grade 8": "GRADE 8",
    "Grade 9": "PSA 9",
    "Grade 9.5": "GRADE 9.5",
    "PSA 10": "PSA 10",
    "BGS 10": "BGS 10",
    "CGC 10": "CGC 10",
    "SGC 10": "SGC 10",
    "BGS 10 Black": "BGS 10 BLACK",
    "CGC 10 Pristine": "CGC 10 PRISTINE",
}

_last_request_at = [0.0]


def _money(text):
    text = text.replace(",", "").replace("$", "").strip()
    if not text or text.upper() == "N/A":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def fetch_page(url, cache_dir="data/cache"):
    """Baixa uma pagina do PriceCharting com cache em disco (24h)."""
    os.makedirs(cache_dir, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", url.lower())[-120:]
    cache_path = os.path.join(cache_dir, slug + ".html")
    if os.path.exists(cache_path):
        if time.time() - os.path.getmtime(cache_path) < CACHE_TTL_SECONDS:
            with open(cache_path, encoding="utf-8") as f:
                return f.read()

    wait = REQUEST_GAP_SECONDS - (time.time() - _last_request_at[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
    _last_request_at[0] = time.time()
    body = data.decode("utf-8", errors="replace")
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(body)
    return body


def parse_product_page(body, source_url=""):
    """Extrai precos por grade, tendencia e volume de vendas de uma pagina de carta.

    Retorna um models.FairValue.
    """
    from .models import FairValue

    fv = FairValue(source_url=source_url)

    # 1) Tabela completa de precos (todas as grades, incluindo BGS/CGC/SGC).
    m = re.search(r'id="full-prices">.*?<table>(.*?)</table>', body, re.S)
    if m:
        rows = re.findall(
            r"<tr>\s*<td>\s*([^<]+?)\s*</td>\s*<td[^>]*>\s*(?:<span[^>]*>)?\s*"
            r"\$?([\d,]+\.\d{2}|N/A)",
            m.group(1),
        )
        for label, price_text in rows:
            grade = FULL_TABLE_GRADE_BY_LABEL.get(label.strip())
            price = _money(price_text)
            if grade and price is not None:
                fv.prices[grade] = price

    # 2) Tabela principal: precos com variacao recente (tendencia) + volume.
    m = re.search(r'<table[^>]*id="price_data".*?</table>', body, re.S)
    if m:
        table = m.group(0)
        for cell_id, grade in MAIN_TABLE_GRADE_BY_ID.items():
            cm = re.search(
                r'id="%s".{0,300}?\$([\d,]+\.\d{2}).{0,300}?class="change"[^>]*>'
                r"\s*(-|&#43;|\+)\s*<span[^>]*>\s*\$([\d,]+\.\d{2})" % cell_id,
                table,
                re.S,
            )
            if cm:
                price = _money(cm.group(1))
                delta = _money(cm.group(3)) or 0.0
                if cm.group(2) == "-":
                    delta = -delta
                if price is not None:
                    fv.prices.setdefault(grade, price)
                    fv.deltas[grade] = delta

        # Volume: as celulas de volume aparecem na MESMA ordem das colunas de preco.
        cells = re.findall(r"<td[^>]*>(.*?)</td>", table, re.S)
        grade_order = list(MAIN_TABLE_GRADE_BY_ID.values())
        vol_idx = 0
        seen = set()
        for cell in cells:
            text = " ".join(
                html_mod.unescape(re.sub(r"<[^>]+>", " ", cell)).split()
            )
            vm = re.search(r"([\d,]+)\s+sales?\s+per\s+(day|week|month|year)", text)
            if vm and vol_idx < len(grade_order):
                grade = grade_order[vol_idx]
                vol_idx += 1
                if grade in seen:
                    continue
                seen.add(grade)
                n = float(vm.group(1).replace(",", ""))
                per = vm.group(2)
                per_month = {"day": n * 30, "week": n * 4.33,
                             "month": n, "year": n / 12}[per]
                fv.sales_per_month[grade] = round(per_month, 1)

    return fv


def get_fair_value(pc_url, cache_dir="data/cache"):
    """Atalho: baixa e parseia a pagina de uma carta."""
    body = fetch_page(pc_url, cache_dir=cache_dir)
    return parse_product_page(body, source_url=pc_url)


def search_product(query, cache_dir="data/cache"):
    """Busca uma carta no PriceCharting e retorna a URL do primeiro resultado.

    Util quando a watchlist nao traz pc_url explicita (mas URL explicita e
    sempre mais precisa).
    """
    q = urllib.parse.quote(query)
    url = f"https://www.pricecharting.com/search-products?q={q}&type=prices"
    body = fetch_page(url, cache_dir=cache_dir)
    m = re.search(r'href="(/game/[^"]+)"', body)
    if m:
        return "https://www.pricecharting.com" + m.group(1)
    return None
