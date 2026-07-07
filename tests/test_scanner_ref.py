from src import scanner
from src.models import WatchCard, Listing, Opportunity, FairValue


CARD = WatchCard(name="Umbreon VMAX", set_name="Evolving Skies", number="215",
                 language="EN", pc_url="")


def L(title, price, condition="Ungraded - Near Mint or better", item_id=None):
    return Listing(item_id=title+str(price) if item_id is None else item_id,
                   title=title, price=price,
                   shipping=0.0, currency="USD", buying_option="FIXED_PRICE",
                   condition=condition, seller_feedback_pct=99.9,
                   seller_feedback_score=900, url="u")


def O(grade, fair, verdict="OPORTUNIDADE"):
    return Opportunity(card=CARD, listing=L("t", 1.0), grade=grade,
                       fair_value=fair, gross_margin_pct=50.0,
                       liquidity_per_month=30.0, liquidity_tier="A",
                       trend_delta=0.0, spread_psa9_pct=0, spread_psa10_pct=0,
                       verdict=verdict)


def test_clean_asks_exclude_accessories_and_non_nm():
    listings = [
        L("Umbreon VMAX 215/203 Evolving Skies NM", 2000.0),
        L("Umbreon VMAX 215/203 Evolving Skies Near Mint", 2100.0),
        L("ACRYLIC CASE Umbreon VMAX 215 Evolving Skies", 12.0),     # acessorio
        L("Umbreon VMAX 215/203 Evolving Skies HP damaged", 800.0),  # nao-NM
    ]
    asks = scanner._clean_ask_prices(CARD, listings)
    assert asks["RAW"] == [2000.0, 2100.0]


def test_ref_inflated_flag_and_downgrade():
    opp = O("RAW", fair=4000.0)
    scanner._annotate_ref_alignment(opp, {"RAW": [2000.0, 2100.0, 2050.0]})
    assert any("REF DESALINHADA" in f for f in opp.risk_flags)
    assert opp.verdict == "REVISAR"
    assert opp.median_ask == 2050.0


def test_ref_aligned_no_flag():
    opp = O("RAW", fair=2048.0)
    scanner._annotate_ref_alignment(opp, {"RAW": [2000.0, 2100.0, 2050.0]})
    assert not any("REF" in f for f in opp.risk_flags)
    assert opp.verdict == "OPORTUNIDADE"


def test_ref_needs_min_samples():
    opp = O("PSA 10", fair=9999.0)
    scanner._annotate_ref_alignment(opp, {"PSA 10": [100.0, 110.0]})
    assert opp.risk_flags == []


# --- dedupe do scan_card --------------------------------------------------------
# Regressao: item_id VAZIO entrava no set de dedupe; o 1o anuncio sem id fazia
# todos os seguintes sem id (conteudo distinto) sumirem silenciosamente do scan.

CARD_CHZ = WatchCard(name="Charizard", set_name="Base Set", number="4",
                     language="EN", pc_url="")


class _FakeEbay:
    """Devolve o lote so na 1a chamada (as demais queries por sufixo vem vazias)."""
    def __init__(self, batch):
        self.batch = batch
        self.calls = 0

    def search(self, query, min_price=10.0):
        self.calls += 1
        return self.batch if self.calls == 1 else []


def test_scan_card_dedupe_ignores_empty_item_id(monkeypatch):
    fair = FairValue(prices={"PSA 9": 3175.0}, deltas={},
                     sales_per_month={"PSA 9": 30.0})
    monkeypatch.setattr(scanner.pricecharting, "get_fair_value",
                        lambda url, cache_dir="data/cache": fair)
    batch = [
        L("Charizard 4/102 Base Set PSA 9", 2000.0,
          condition="Graded", item_id="1"),
        # id duplicado -> dropado
        L("Charizard 4/102 Base Set PSA 9 mint", 1990.0,
          condition="Graded", item_id="1"),
        # fingerprint (titulo+preco) duplicado -> dropado
        L("Charizard 4/102 Base Set PSA 9", 2000.0,
          condition="Graded", item_id="2"),
        # sem item_id, conteudos DISTINTOS -> ambos devem sobreviver
        L("Charizard #4 Base Set PSA 9 slabbed", 2100.0,
          condition="Graded", item_id=""),
        L("Charizard 4/102 Base PSA 9 gem", 2050.0,
          condition="Graded", item_id=""),
    ]
    _, opps = scanner.scan_card(CARD_CHZ, _FakeEbay(batch),
                                {"graded_only": True}, log=lambda *a: None)
    assert sorted(o.listing.price for o in opps) == [2000.0, 2050.0, 2100.0]
