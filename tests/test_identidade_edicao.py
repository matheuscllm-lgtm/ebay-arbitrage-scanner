"""Identidade por EDICAO e ANO.

Contexto (run real de 2026-09-09, grupo 3): anuncios de Celebrations: Classic
Collection (2021) casaram como Base Set (1999) porque a reimpressao repete nome e
NUMERO da carta e o vendedor escreve "Base Set" no titulo -- e o que esta estampado
na carta. Resultado: margem publicada de 2801% contra a referencia da carta errada.

O mecanismo de defesa (`exclude_keywords`) ja existia e ja tinha teste
(`test_title_parser.test_celebrations_reprint_excluded`), mas o teste alimentava as
palavras A MAO e a watchlist de producao tinha ZERO carta preenchida. Verde no teste,
errado no scan. Por isso os testes abaixo assertam sobre a WATCHLIST REAL sempre que a
pergunta e "producao esta protegida?".

Faixas de tratamento (definidas pelo operador):
  1. alias inequivoco de outra edicao   -> rejeita a associacao
  2. ano incompativel com a edicao      -> sem aprovacao automatica
  3. colisao conhecida, sem ano e sem alias -> identidade insuficiente
  4. carta sem colisao                  -> nada muda
"""
import pytest

from src import scanner, slab_strategy, title_parser
from src.models import WatchCard

# Titulos VERBATIM do run real (results/trial-g3-gm-2026-09-09.aborted.json).
CELEBRATIONS_REAIS = [
    "Charizard PSA 9 Celebrations Classic 4/102 Holo Base Set 2021 Pokemon",
    "2021 Pokemon Celebrations Charizard Holo Classic Coll Base Set #4 PSA",
    "Pokemon Charizard Celebrations Classic Coll.-Base Set Holo #4 PSA",
]
VENUSAUR_2021 = "2021 Pokemon Venusaur 15/102 Base Set Holo CGC 10 Gem Mint"

BASE_ZARD = WatchCard(name="Charizard", set_name="Base Set", number="4",
                      language="EN", pc_url="", year=1999)
BASE_VENU = WatchCard(name="Venusaur", set_name="Base Set", number="15",
                      language="EN", pc_url="", year=1999)
# Jungle #11 nao colide com nenhuma outra edicao da watchlist.
JUNGLE_SNORLAX = WatchCard(name="Snorlax", set_name="Jungle", number="11",
                           language="EN", pc_url="", year=1999)


def _real(name, set_name, number):
    """Carta da WATCHLIST REAL -- e ela que roda em producao."""
    for card in scanner.load_watchlist("watchlist.yaml"):
        if (card.name == name and card.set_name == set_name
                and str(card.number) == str(number)):
            return card
    raise AssertionError(f"carta ausente da watchlist: {name} {number} {set_name}")


# --- ano: extrair sem confundir com fracao, certificado ou numero solto ---

def test_ano_no_inicio_do_titulo():
    assert 2021 in title_parser.card_year_candidates(VENUSAUR_2021)

def test_fracao_nao_e_ano():
    assert title_parser.card_year_candidates("Charizard 4/102 Base Set Holo") == frozenset()

def test_numero_de_certificado_nao_e_ano():
    # Cert PSA de 8 digitos contem "1999" no meio; nao e ano da carta.
    assert title_parser.card_year_candidates("Charizard Base Set PSA 9 cert 21999456") == frozenset()

def test_intervalo_traz_os_dois_anos():
    anos = title_parser.card_year_candidates("1999-2000 WOTC Pokemon Charizard Base Set")
    assert {1999, 2000} <= anos

def test_ano_fora_da_era_pokemon_ignorado():
    assert 1850 not in title_parser.card_year_candidates("Charizard 1850 Base Set")


# --- camada 1: alias inequivoco de outra edicao rejeita a associacao ---

@pytest.mark.parametrize("titulo", CELEBRATIONS_REAIS)
def test_celebrations_nao_casa_com_base_set_na_watchlist_real(titulo):
    assert not slab_strategy.identity_matches(_real("Charizard", "Base Set", "4"), titulo)

def test_venusaur_2021_nao_e_comparado_com_base_set_1999():
    """Ano incompativel nao rejeita a identidade -- o anuncio segue visivel -- mas
    impede a comparacao automatica. Era daqui que saia a margem de 2431% do run."""
    assert slab_strategy.edition_conflict(
        _real("Venusaur", "Base Set", "15"), VENUSAUR_2021) == "conflito-de-ano"

def test_celebrations_casa_com_a_propria_edicao():
    zard = _real("Charizard", "Celebrations: Classic Collection", "4")
    assert slab_strategy.identity_matches(
        zard, "2021 Pokemon Celebrations Classic Collection Charizard 4/102 PSA 10")

def test_evidencia_especifica_vence_expressao_generica():
    # "Celebrations" e especifico; "Base Set" no mesmo titulo e o que vem estampado.
    assert slab_strategy.edition_conflict(
        BASE_ZARD, "Charizard Celebrations Classic Coll.-Base Set Holo #4") == "outra-edicao"


# --- camada 2: ano incompativel nao aprova sozinho, mas nao rejeita em silencio ---

def test_ano_incompativel_vira_conflito_de_ano():
    assert slab_strategy.edition_conflict(
        BASE_ZARD, "2004 Pokemon Charizard 4/102 Base Set Holo PSA 9") == "conflito-de-ano"

def test_ano_compativel_nao_gera_conflito():
    assert slab_strategy.edition_conflict(
        BASE_ZARD, "1999 Pokemon Charizard 4/102 Base Set Holo PSA 9") is None

def test_conflito_de_ano_nao_rejeita_a_identidade():
    # Camada 2 tira a aprovacao automatica; quem decide olhando e o operador.
    assert slab_strategy.identity_matches(
        BASE_ZARD, "2004 Pokemon Charizard 4/102 Base Set Holo PSA 9")


# --- camada 3: colisao conhecida sem nenhuma evidencia de edicao ---

def test_colisao_sem_ano_e_sem_alias_fica_ambigua():
    zard = _real("Charizard", "Base Set", "4")
    assert slab_strategy.edition_conflict(
        zard, "Charizard 4/102 Base Set Holo Pokemon CGC 10 Gem Mint") == "edicao-ambigua"

def test_ambiguidade_nao_rejeita_a_identidade():
    zard = _real("Charizard", "Base Set", "4")
    assert slab_strategy.identity_matches(
        zard, "Charizard 4/102 Base Set Holo Pokemon CGC 10 Gem Mint")


# --- camada 4: carta sem colisao nao muda de comportamento ---

def test_carta_sem_colisao_sem_ano_nao_gera_conflito():
    assert slab_strategy.edition_conflict(
        JUNGLE_SNORLAX, "Snorlax 11/64 Jungle Holo Pokemon PSA 9") is None

def test_carta_sem_colisao_continua_casando():
    assert slab_strategy.identity_matches(
        JUNGLE_SNORLAX, "Snorlax 11/64 Jungle Holo Pokemon PSA 9")


# --- watchlist real: a colisao tem que estar declarada, senao a defesa nao roda ---

def test_watchlist_declara_edicoes_colidentes():
    zard = _real("Charizard", "Base Set", "4")
    outras = {s.lower() for s in zard.colliding_editions}
    assert "celebrations: classic collection" in outras
    assert "base set 2" in outras

def test_watchlist_nao_inventa_colisao_onde_nao_ha():
    assert _real("Snorlax", "Jungle", "11").colliding_editions == ()

def test_toda_carta_com_homonimo_de_numero_declara_a_colisao():
    """Guarda de drift: a defesa vive de dado, e dado apodrece em silencio."""
    cards = scanner.load_watchlist("watchlist.yaml")
    porta = {}
    for card in cards:
        porta.setdefault((card.name.strip().lower(), str(card.number).strip()), []).append(card)
    faltando = [f"{c.name} {c.number} ({c.set_name})"
                for grupo in porta.values() if len(grupo) > 1
                for c in grupo if not c.colliding_editions]
    assert not faltando, f"cartas em colisao sem edicoes declaradas: {faltando[:5]}"


# --- cesta de vendas: a mesma guarda vale para a venda de referencia ---

def test_venda_de_outra_edicao_nao_entra_na_cesta():
    zard = _real("Charizard", "Base Set", "4")
    assert not slab_strategy.identity_matches(
        zard, "2021 Pokemon Celebrations Charizard Classic Collection 4/102 PSA 10")

def test_venda_legitima_sem_ano_continua_na_cesta():
    # O PR #32 ja tinha registrado: exigir dado extra da venda amputa a cesta e move a
    # mediana. Ambiguidade (camada 3) NUNCA pode virar exclusao de venda.
    zard = _real("Charizard", "Base Set", "4")
    assert slab_strategy.identity_matches(zard, "Pokemon Charizard Base Set Holo 4/102 PSA 9")


def test_venda_com_ano_contraditorio_nao_entra_na_cesta():
    """Venda de 2021 na pagina do Base Set 1999 puxaria a mediana para a reimpressao."""
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    hoje = datetime.now(timezone.utc).date()
    def venda(sale_id, titulo, preco, dias):
        return dict(date=(hoje - timedelta(days=dias)).isoformat(), price=preco,
                    title=titulo, source='ebay', sale_id=str(sale_id))
    zard = _real("Charizard", "Base Set", "4")
    pool = [venda(101, "1999 Pokemon Charizard 4/102 Base Set English PSA 9", 900, 3),
            venda(102, "Pokemon Charizard 4/102 Base Set English PSA 9", 950, 4),
            venda(103, "2021 Pokemon Charizard 4/102 Base Set English PSA 9", 120, 5)]
    refs = SimpleNamespace(available=True, _sales=pool)
    politica = slab_strategy.policy_config({})['slab_strategy']
    cesta = slab_strategy.reference_sales(
        zard, refs, __import__('src.grading', fromlist=['x']).Grade('PSA', 9.0),
        frozenset(), politica)
    titulos = [s['title'] for s in cesta['sales']]
    assert not any('2021' in t for t in titulos), titulos
    assert len(titulos) == 2
