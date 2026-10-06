"""Regressão offline da resolução de referências e das normalizações de código (issue #56).

Casos reais dos snapshots: cadastro duplo '4'/'004', H3×3, 50a×50b, GG01×001,
151C4×151C, PROMOSV…/SV-P, pacote de gemas 'CBB5C 08 07/07' e Nidoran♀×♂.
"""
import ast
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "pipeline"
sys.path.insert(0, str(ROOT))
from common import key  # noqa: E402
from reference_match import (local_code, number_norm, resolve_reference,  # noqa: E402
                             same_print, set_norm)


def cand(pid, nome, numero, unit_name=None, set_id=1):
    return {"id": pid, "nome": nome, "numero": numero,
            "unidade": (set_id, numero, key(unit_name or nome))}


class NormalizationTests(unittest.TestCase):
    def test_number_keeps_prefix_and_suffix(self):
        self.assertEqual(number_norm("036"), number_norm("36"))
        self.assertEqual(number_norm("TG01"), "TG1")
        self.assertNotEqual(number_norm("H05"), number_norm("5"))
        self.assertNotEqual(number_norm("50a"), number_norm("50b"))
        self.assertNotEqual(number_norm("GG01"), number_norm("001"))
        self.assertEqual(number_norm("121/106"), "121/106")  # denominador nunca vira chave

    def test_set_codes(self):
        self.assertEqual(set_norm("SM4+"), set_norm("SM4p"))
        self.assertEqual(set_norm("SV-P"), "SVP")
        self.assertNotEqual(set_norm("151C4"), set_norm("151C"))

    def test_local_code_notation(self):
        cases = {"M4 114/083": ("M4", "114"), "SM4+ 120/114": ("SM4P", "120"),
                 "PROMOSV08 092/SV-P": ("SVP", "92"), "PROMOSV151m3 099/SV-P": ("SVP", "99"),
                 "S-P 210/S-P": ("SP", "210"), "CBB5C 08 07/07": ("CBB5C", "807"),
                 "SV2a F 170/165": ("SV2AF", "170"), "CSV9.5C 239/208": ("CSV95C", "239"),
                 "SV4a TG05/TG30": ("SV4A", "TG5"), "lixo": None}
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(local_code(raw), expected)

    def test_same_print(self):
        codes = {("SV4A", "210"), ("151C", "152")}
        self.assertEqual(same_print(("SV4A", "210"), codes), "igual")
        self.assertEqual(same_print(("151C4", "152"), codes), "subproduto")
        self.assertIsNone(same_print(("SV11W", "102"), {("SV1", "102")}))  # outro set, não subproduto
        self.assertIsNone(same_print(("CSM2CC", "71"), {("CSM2DC", "71")}))
        self.assertIsNone(same_print(None, codes))

    def test_gender_is_identity(self):
        self.assertNotEqual(key("Nidoran♀"), key("Nidoran♂"))
        self.assertEqual(key("Team Rocket's Nidoran♀"), key("Team Rocket's Nidoran F"))


class ResolveReferenceTests(unittest.TestCase):
    def test_exact_record(self):
        unit, rec, how = resolve_reference("Mew ex", "151", [cand(1, "Mew ex", "151"), cand(2, "Mewtwo ex", "151")])
        self.assertEqual((rec["id"], how), (1, "registro exato"))

    def test_double_listing_tie_broken_by_literal_number(self):
        cands = [cand(40609, "Charizard Metal", "4"), cand(82159, "Charizard Metal", "004")]
        self.assertEqual(resolve_reference("Charizard Metal", "004", cands)[1]["id"], 82159)
        self.assertEqual(resolve_reference("Charizard Metal", "4", cands)[1]["id"], 40609)

    def test_double_listing_without_literal_is_ambiguous(self):
        cands = [cand(1, "Pikachu", "58"), cand(2, "Pikachu", "58", set_id=2)]
        self.assertEqual(resolve_reference("Pikachu", "058", cands)[:2], (None, None))
        self.assertTrue(resolve_reference("Pikachu", "058", cands)[2].startswith("ambíguo"))

    def test_variant_resolves_to_unit_only(self):
        cands = [cand(1, "Gengar Cosmos Holo", "60", "Gengar")]
        unit, rec, how = resolve_reference("Gengar Reverse Holo", "60", cands)
        self.assertEqual((unit, rec, how), ((1, "60", "gengar"), None, "mesma carta, registro aproximado"))

    def test_two_units_same_base_name_is_ambiguous(self):
        cands = [cand(1, "Raikou", "48"), cand(2, "Raikou", "048", "Raikou")]
        unit, rec, how = resolve_reference("Raikou Reverse Holo", "48", cands)
        self.assertIsNone(unit)
        self.assertTrue(how.startswith("ambíguo: 2 cartas"))

    def test_contained_or_different_name_does_not_locate(self):
        # Antes: 'mew' contido em 'mewtwoex' localizava a carta errada; o único candidato
        # de nome diferente também era aceito e herdava a situação de outra carta.
        for cands in ([cand(1, "Mewtwo ex", "151")], [cand(1, "Gengar", "60"), cand(2, "Haunter", "60")]):
            unit, rec, how = resolve_reference("Mew", "151" if cands[0]["nome"] == "Mewtwo ex" else "60", cands)
            self.assertIsNone(unit)
            self.assertTrue(how.startswith("não localizado"))
        self.assertEqual(resolve_reference("Mew", "1", []), (None, None, "não localizado"))


class RankRegressionTests(unittest.TestCase):
    """O rank real de build_xlsx.py mantém impressões distintas que a chave antiga fundia."""

    def setUp(self):
        tree = ast.parse((ROOT / "build_xlsx.py").read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "rank")
        scope = {"sdate": lambda k: datetime(2020, 1, 1)}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "build_xlsx.py", "exec"), scope)
        self.rank = scope["rank"]

    def test_snapshot_cases_stay_apart(self):
        for a, b in ((("3", "ariados"), ("H3", "ariados")), (("50a", "golduck"), ("50b", "golduck")),
                     (("001", "pikachu"), ("GG01", "pikachu")),
                     (("26", "glaceonex"), ("26", "glaceonexholidaycalendar"))):
            with self.subTest(a=a, b=b):
                cands = {(1,) + a: ({"n_in": 80}, 2, "A1"), (1,) + b: ({"n_in": 70}, 2, "A1")}
                self.assertEqual(len(self.rank((2, "1", "src"), cands)), 2)


if __name__ == "__main__":
    unittest.main()
