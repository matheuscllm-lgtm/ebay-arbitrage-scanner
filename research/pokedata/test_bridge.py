"""Regressão offline da ponte base parcial -> catálogo completo (sem planilhas)."""
import unittest

from bridge_partial_ids import build_bridge, id_namespace_check, number_key


def cat(pid, set_name, num, printed, name, set_id=1):
    return {"ID PokeData": pid, "Set": set_name, "Número": num, "set_id": set_id,
            "Número impresso": printed, "Nome (PokeData)": name, "Nome base": name}


def ref(rid, name, code, set_name):
    return {"ID EN": rid, "Carta inglesa — referência": name, "Código EN": code, "Set EN": set_name}


CATALOG = [
    cat(1, "Hidden Fates", "55", "55/68", "Holo Brock's Training"),
    cat(521348, "Chaos Rising", "122", "122/106", "Mega Greninja ex"),
    cat(900, "Surging Sparks", "238", "238/191", "Pikachu ex"),
    cat(901, "Surging Sparks", "238", "238/191", "Pikachu ex"),
    cat(950, "Lost Origin", "TG01", "TG01/TG30", "Kricketune"),
    cat(951, "Lost Origin", "001", "001/196", "Kricketune"),
]


class BridgeTests(unittest.TestCase):
    def test_row_number_is_never_used_as_pokedata_id(self):
        # ID EN 1 coincide com o ID PokeData 1, mas é outra carta.
        out = build_bridge([ref(1, "Mega Greninja ex", "122", "Chaos Rising")], CATALOG)
        self.assertEqual(out[0]["status"], "unico")
        self.assertEqual(out[0]["ids_pokedata"], "521348")
        check = id_namespace_check([ref(1, "Mega Greninja ex", "122", "Chaos Rising")], CATALOG)
        self.assertEqual(check, {"numeric_overlap": 1, "overlap_same_set_and_number": 0})

    def test_homonymous_variants_stay_ambiguous(self):
        out = build_bridge([ref(2, "Pikachu ex", "238", "Surging Sparks")], CATALOG)
        self.assertEqual((out[0]["status"], out[0]["ids_pokedata"]), ("ambiguo", "900;901"))

    def test_prefix_is_part_of_identity(self):
        out = build_bridge([ref(3, "Kricketune", "TG01", "Lost Origin"),
                            ref(4, "Kricketune", "1", "Lost Origin")], CATALOG)
        self.assertEqual([o["ids_pokedata"] for o in out], ["950", "951"])

    def test_unmatched_reference_is_kept(self):
        out = build_bridge([ref(5, "Charizard", "4", "Base Set")], CATALOG)
        self.assertEqual((len(out), out[0]["status"], out[0]["ids_pokedata"]), (1, "sem_match", ""))

    def test_gender_symbols_are_identity(self):
        catalog = [cat(29, "Base Set", "29", "29/102", "Nidoran\u2642")]
        out = build_bridge([ref(6, "Nidoran\u2640", "29", "Base Set")], catalog)
        self.assertEqual(out[0]["status"], "sem_match")
        alias = build_bridge([ref(7, "Nidoran M", "29", "Base Set")], catalog)
        self.assertEqual(alias[0]["ids_pokedata"], "29")

    def test_double_listing_resolved_by_literal_number(self):
        # Caso real: o catálogo cadastra a mesma carta como '4' e '004' (IDs 40609 e 82159).
        catalog = [cat(40609, "Miscellaneous Promos", "4", "4", "Charizard Celebrations Metal Card"),
                   cat(82159, "Miscellaneous Promos", "004", "004", "Charizard Celebrations Metal Card")]
        out = build_bridge([ref(1235, "Charizard Celebrations Metal Card", "004", "Miscellaneous Promos"),
                            ref(1236, "Charizard Celebrations Metal Card", "4", "Miscellaneous Promos")], catalog)
        self.assertEqual([(o["status"], o["ids_pokedata"], o["cadastro_duplo"]) for o in out],
                         [("unico_numero_literal", "82159", "40609;82159"),
                          ("unico_numero_literal", "40609", "40609;82159")])

    def test_number_key(self):
        self.assertEqual(number_key("089"), "89")
        self.assertEqual(number_key("089/064"), "089/064")  # nunca corta '/' às cegas
        self.assertEqual(number_key("TG01"), "TG1")
        self.assertEqual(number_key("50a"), "50A")
        self.assertNotEqual(number_key("H3"), number_key("3"))


if __name__ == "__main__":
    unittest.main()
