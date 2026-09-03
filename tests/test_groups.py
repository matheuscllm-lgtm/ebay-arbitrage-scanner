"""Grupos canonicos 1-12 (portados da COMC) e o catalogo de 123 sets."""
import pytest

from src import groups


def test_union_of_groups_is_exactly_the_catalog_without_overlap():
    seen = []
    for g in groups.SCAN_GROUPS.values():
        seen.extend(g.sets)
    assert len(seen) == len(set(seen)), "set em mais de um grupo"
    assert set(seen) == groups.validated_catalog_sets()
    assert len(seen) == 123
    assert groups.VALID_GROUP_NUMBERS == tuple(range(1, 13))


def test_set_group_lookup():
    assert groups.set_group("Base Set") == 3
    assert groups.set_group("SV: Scarlet & Violet 151") == 2
    assert groups.set_group("nope") is None


def test_parse_group_arg():
    assert groups.parse_group_arg("all") == list(range(1, 13))
    assert groups.parse_group_arg("3") == [3]
    assert groups.parse_group_arg("5-8") == [5, 6, 7, 8]
    assert groups.parse_group_arg("1,3,10-12") == [1, 3, 10, 11, 12]
    assert groups.parse_group_arg("3,3") == [3]
    for bad in ("0", "13", "8-5", "x", "", "1-"):
        with pytest.raises(ValueError):
            groups.parse_group_arg(bad)


def test_is_group_spec():
    assert groups.is_group_spec("all") and groups.is_group_spec("5-8")
    assert groups.is_group_spec("1,3") and groups.is_group_spec("12")
    assert not groups.is_group_spec("chase-en") and not groups.is_group_spec("")


def test_catalog_has_years():
    cat = groups.catalog()
    assert cat["Base Set"]["year"] == "1999"
    assert groups.describe_groups().startswith("Grupos canonicos")
