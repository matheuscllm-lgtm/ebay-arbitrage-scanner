"""Contrato de product_url_from_search (resolucao de URL na busca do PriceCharting).

Offline: os corpos abaixo reproduzem os DOIS casos reais observados no site em
2026-08-30 (ver docstring da funcao). Nada de rede.
"""
from src.pricecharting import product_url_from_search

PRODUTO = (
    '<html><head><title>Charizard ex #223 Prices | Pokemon Obsidian Flames</title>'
    '<link rel="canonical" href="https://www.pricecharting.com/game/'
    'pokemon-obsidian-flames/charizard-ex-223" /></head><body></body></html>'
)

BUSCA_AMBIGUA = (
    '<html><head><link rel="canonical" href="https://www.pricecharting.com/'
    'search-products?q=pokemon&#43;charizard&amp;type=prices" /></head>'
    '<body><table id="games_table"><thead><tr><th>Title</th></tr></thead>'
    '<tbody></tbody></table></body></html>'
)

LINK_DIRETO = (
    '<html><body><a href="/game/pokemon-evolving-skies/umbreon-vmax-215">x</a>'
    '</body></html>'
)


def test_busca_especifica_redireciona_resolve_pelo_canonical():
    assert product_url_from_search(PRODUTO) == (
        "https://www.pricecharting.com/game/pokemon-obsidian-flames/charizard-ex-223")


def test_busca_ambigua_nao_chuta_resultado():
    # tbody vazio (resultados por JS) + canonical apontando pra propria busca:
    # precisao > cobertura, devolve None em vez de inventar identidade.
    assert product_url_from_search(BUSCA_AMBIGUA) is None


def test_fallback_link_de_resultado_direto():
    assert product_url_from_search(LINK_DIRETO) == (
        "https://www.pricecharting.com/game/pokemon-evolving-skies/umbreon-vmax-215")


def test_corpo_sem_nada_devolve_none():
    assert product_url_from_search("<html><body>nada</body></html>") is None


CANONICAL_COM_ENTIDADE = (
    '<html><head><link rel="canonical" href="https://www.pricecharting.com/game/'
    'pokemon-scarlet-&amp;-violet/gardevoir-ex-245" /></head></html>'
)


def test_canonical_vem_html_escapado_e_precisa_desescapar():
    # Set com "&" no nome (Scarlet & Violet, Sword & Shield): o href chega com
    # &amp; e a URL escapada nao baixa. Contrato: a funcao devolve desescapado.
    assert product_url_from_search(CANONICAL_COM_ENTIDADE) == (
        "https://www.pricecharting.com/game/pokemon-scarlet-&-violet/gardevoir-ex-245")
