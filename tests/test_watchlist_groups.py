"""Testes de grupos na watchlist (--group / --list-groups)."""
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


def test_load_watchlist_reads_group_and_tcg_set(tmp_path):
    cards = scanner.load_watchlist(write_watchlist(tmp_path))
    assert [c.group for c in cards] == ["chase-en", "chase-en", "vintage-jp", ""]
    assert cards[0].tcg_set == "Base Set"
    assert cards[1].tcg_set == ""  # opcional: ausente = vazio


def test_filter_group(tmp_path):
    cards = scanner.load_watchlist(write_watchlist(tmp_path))
    chase = scanner.filter_group(cards, "chase-en")
    assert [c.name for c in chase] == ["Charizard", "Umbreon VMAX"]
    # Sem grupo = todas as cartas (backward compat).
    assert scanner.filter_group(cards, "") == cards
    assert scanner.filter_group(cards, None) == cards
    # Grupo inexistente = lista vazia (nunca cai pra "todas" silenciosamente).
    assert scanner.filter_group(cards, "nope") == []


def test_group_counts_includes_ungrouped(tmp_path):
    cards = scanner.load_watchlist(write_watchlist(tmp_path))
    counts = scanner.group_counts(cards)
    assert counts == {"chase-en": 2, "vintage-jp": 1, "(sem grupo)": 1}


def test_list_groups_cli_no_keys_needed(tmp_path, monkeypatch, capsys):
    # --list-groups nao pode exigir chave eBay nem tocar rede.
    path = write_watchlist(tmp_path)
    monkeypatch.delenv("EBAY_CLIENT_ID", raising=False)
    monkeypatch.delenv("EBAY_CLIENT_SECRET", raising=False)
    monkeypatch.setattr(sys, "argv",
                        ["main.py", "--watchlist", path, "--list-groups"])
    main_mod.main()
    out = capsys.readouterr().out
    assert "chase-en: 2" in out
    assert "vintage-jp: 1" in out
    assert "(sem grupo): 1" in out


def test_run_scan_pricing_only_respects_group(tmp_path, monkeypatch):
    # pricing-only + group: so as cartas do grupo sao consultadas.
    path = write_watchlist(tmp_path)
    asked = []

    def fake_fair_value(url, cache_dir="data/cache"):
        asked.append(url)
        return scanner.pricecharting.parse_product_page("", source_url=url)

    monkeypatch.setattr(scanner.pricecharting, "get_fair_value", fake_fair_value)
    fair_values, opps, effective_pricing_only = scanner.run_scan(
        watchlist_path=path, pricing_only=True,
        log=lambda *a, **k: None, group="vintage-jp")
    assert asked == ["https://example.com/pikachu"]
    assert opps == []
    assert effective_pricing_only is True


class _UnconfiguredEbay:
    configured = False


def test_run_scan_reports_degraded_mode(tmp_path, monkeypatch):
    # Sem EBAY_CLIENT_ID/SECRET o run degrada para pricing-only e o retorno
    # DIZ isso (3o elemento True) -- o caller nao pode tratar como scan real.
    path = write_watchlist(tmp_path)
    monkeypatch.setattr(scanner, "EbayClient", _UnconfiguredEbay)
    monkeypatch.setattr(
        scanner.pricecharting, "get_fair_value",
        lambda url, cache_dir="data/cache":
            scanner.pricecharting.parse_product_page("", source_url=url))
    _, opps, effective_pricing_only = scanner.run_scan(
        watchlist_path=path, pricing_only=False, log=lambda *a, **k: None)
    assert opps == []
    assert effective_pricing_only is True


def test_degraded_scan_never_overwrites_artifact(tmp_path, monkeypatch, capsys):
    # Guarda anti "verde mas vazio": run degradado (sem chaves) NAO pode
    # sobrescrever o artefato JSON do ultimo scan real com 0 rows.
    path = write_watchlist(tmp_path)
    out = tmp_path / "last_scan.json"
    out.write_text('{"meta": {"real": true}, "rows": [{"x": 1}]}',
                   encoding="utf-8")
    monkeypatch.delenv("EBAY_CLIENT_ID", raising=False)
    monkeypatch.delenv("EBAY_CLIENT_SECRET", raising=False)
    monkeypatch.setattr(
        scanner.pricecharting, "get_fair_value",
        lambda url, cache_dir="data/cache":
            scanner.pricecharting.parse_product_page("", source_url=url))
    monkeypatch.setattr(sys, "argv",
                        ["main.py", "--watchlist", path, "--out", str(out)])
    main_mod.main()
    console = capsys.readouterr().out
    assert "NAO gravado" in console
    # O artefato anterior segue intacto.
    assert '"real": true' in out.read_text(encoding="utf-8")
