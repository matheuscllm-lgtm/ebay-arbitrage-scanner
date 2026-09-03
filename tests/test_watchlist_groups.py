"""Testes de grupos na watchlist (--group / --list-groups) e run degradado."""
import sys

import main as main_mod
from src import scanner

WATCHLIST_YAML = """\
cards:
  - name: Charizard
    set: Base Set
    number: 4
    language: EN
    pc_url: https://example.com/charizard
    group: chase-en
    tcg_set: "Base Set"
    pokemon: Charizard
    pokemon_rank: 1
    rarity: Holo Rare
    year: 1999
  - name: Umbreon VMAX
    set: Evolving Skies
    number: 215
    language: EN
    pc_url: https://example.com/umbreon
    group: chase-en
  - name: Pikachu
    set: Jungle
    number: 60
    language: JP
    pc_url: https://example.com/pikachu
    group: vintage-jp
  - name: Blastoise
    set: Base Set
    number: 2
    language: EN
    pc_url: https://example.com/blastoise
"""


def write_watchlist(tmp_path):
    path = tmp_path / "watchlist.yaml"
    path.write_text(WATCHLIST_YAML, encoding="utf-8")
    return str(path)


def _no_pc(monkeypatch):
    """PriceCharting offline nos testes: pagina vazia (sem rede)."""
    monkeypatch.setattr(scanner.pc_sales, "fetch_page", lambda url, cache_dir=None: "")


def test_load_watchlist_reads_group_tcg_set_and_comc_fields(tmp_path):
    cards = scanner.load_watchlist(write_watchlist(tmp_path))
    assert [c.group for c in cards] == ["chase-en", "chase-en", "vintage-jp", ""]
    assert cards[0].tcg_set == "Base Set"
    assert cards[1].tcg_set == ""  # opcional: ausente = vazio
    assert cards[0].pokemon == "Charizard" and cards[0].pokemon_rank == 1
    assert cards[0].rarity == "Holo Rare" and cards[0].year == 1999
    assert cards[1].pokemon == "" and cards[1].pokemon_rank == 9999 and cards[1].year is None


def test_filter_group(tmp_path):
    cards = scanner.load_watchlist(write_watchlist(tmp_path))
    chase = scanner.filter_group(cards, "chase-en")
    assert [c.name for c in chase] == ["Charizard", "Umbreon VMAX"]
    assert scanner.filter_group(cards, "") == cards
    assert scanner.filter_group(cards, None) == cards
    assert scanner.filter_group(cards, "nope") == []


def test_group_counts_includes_ungrouped(tmp_path):
    cards = scanner.load_watchlist(write_watchlist(tmp_path))
    counts = scanner.group_counts(cards)
    assert counts == {"chase-en": 2, "vintage-jp": 1, "(sem grupo)": 1}


def test_list_groups_cli_no_keys_needed(tmp_path, monkeypatch, capsys):
    path = write_watchlist(tmp_path)
    monkeypatch.delenv("EBAY_CLIENT_ID", raising=False)
    monkeypatch.delenv("EBAY_CLIENT_SECRET", raising=False)
    monkeypatch.setattr(sys, "argv", ["main.py", "--watchlist", path, "--list-groups"])
    main_mod.main()
    out = capsys.readouterr().out
    assert "chase-en: 2" in out
    assert "vintage-jp: 1" in out
    assert "(sem grupo): 1" in out


def test_run_scan_pricing_only_respects_group(tmp_path, monkeypatch):
    path = write_watchlist(tmp_path)
    asked = []

    def fake_fetch(url, cache_dir=None):
        asked.append(url)
        return ""

    monkeypatch.setattr(scanner.pc_sales, "fetch_page", fake_fetch)
    fair_values, opps, effective_pricing_only, stats, aborted = scanner.run_scan(
        watchlist_path=path, pricing_only=True, log=lambda *a, **k: None,
        group="vintage-jp")
    assert asked == ["https://example.com/pikachu"]
    assert opps == [] and effective_pricing_only is True and aborted is False
    assert stats["cards"] == 1


class _UnconfiguredEbay:
    configured = False


def test_run_scan_reports_degraded_mode(tmp_path, monkeypatch):
    path = write_watchlist(tmp_path)
    monkeypatch.setattr(scanner, "EbayClient", _UnconfiguredEbay)
    _no_pc(monkeypatch)
    _, opps, effective_pricing_only, _, _ = scanner.run_scan(
        watchlist_path=path, pricing_only=False, log=lambda *a, **k: None)
    assert opps == []
    assert effective_pricing_only is True


def test_degraded_scan_never_overwrites_artifact(tmp_path, monkeypatch, capsys):
    path = write_watchlist(tmp_path)
    out = tmp_path / "last_scan.json"
    out.write_text('{"meta": {"real": true}, "rows": [{"x": 1}]}', encoding="utf-8")
    monkeypatch.delenv("EBAY_CLIENT_ID", raising=False)
    monkeypatch.delenv("EBAY_CLIENT_SECRET", raising=False)
    _no_pc(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["main.py", "--watchlist", path, "--out", str(out)])
    assert main_mod.main() == 0
    console = capsys.readouterr().out
    assert "NAO gravado" in console
    assert '"real": true' in out.read_text(encoding="utf-8")


def test_filter_group_accepts_numeric_spec(tmp_path):
    path = tmp_path / "w.yaml"
    path.write_text(WATCHLIST_YAML.replace("group: chase-en", "group: '3'", 1)
                    .replace("group: chase-en", "group: '11'").replace("group: vintage-jp", "group: '4'"),
                    encoding="utf-8")
    cards = scanner.load_watchlist(str(path))
    assert [c.name for c in scanner.filter_group(cards, "3")] == ["Charizard"]
    assert [c.name for c in scanner.filter_group(cards, "3-4")] == ["Charizard", "Pikachu"]
    assert [c.name for c in scanner.filter_group(cards, "all")] == ["Charizard", "Umbreon VMAX", "Pikachu"]
    assert scanner.filter_group(cards, "1,2") == []

