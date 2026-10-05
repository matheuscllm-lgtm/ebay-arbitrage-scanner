"""Regressão offline da ponte base parcial -> catálogo completo (sem planilhas)."""
import unittest

from bridge_partial_ids import build_bridge, id_namespace_check, number_key


def cat(pid, set_name, num, printed, name):
    return {"ID PokeData": pid, "Set": set_name, "Número": num,
            "Número impresso": printed, "Nome (PokeData)": name}


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

    def test_number_key(self):
        self.assertEqual(number_key("089/064"), "89")
        self.assertEqual(number_key("TG01/TG30"), "TG1")
        self.assertEqual(number_key("50a"), "50A")
        self.assertNotEqual(number_key("H3"), number_key("3"))


if __name__ == "__main__":
    unittest.main()
