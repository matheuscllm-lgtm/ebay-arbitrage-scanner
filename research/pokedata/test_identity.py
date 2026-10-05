"""Regressão offline das correções C1, C2 e C4 e da conciliação dos pares (sem planilhas)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))

import bridge_partial_ids  # noqa: E402
import revise_snapshot as rs  # noqa: E402
from identity import CANDIDATE, match_level, number_key, print_key, single_language  # noqa: E402

NONE_FOUND = {"ENGLISH": "não encontrado", "CHINESE": "não encontrado"}


class NumberKeyTests(unittest.TestCase):
    def test_full_number_is_identity(self):
        cases = {"001": "1", "36": "36", "GG01": "GG1", "TG01": "TG1", "H3": "H3",
                 "50a": "50A", "121/106": "121", "SV-P": "SV-P"}
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(number_key(raw), expected)
                self.assertEqual(bridge_partial_ids.number_key(raw), expected)


class PrintKeyTests(unittest.TestCase):
    def test_double_listing_of_same_card_merges(self):
        self.assertEqual(print_key((506, "036", "spinarak")), print_key((506, "36", "spinarak")))

    def test_distinct_prints_in_same_set_stay_apart(self):
        # antes: dígitos finais → GG01×001 e H3×3 colidiam; 50a×50b só pelo inteiro
        for a, b in ((("506", "GG01", "hisuianvoltorb"), ("506", "001", "oddish")),
                     ((7, "H3", "ariados"), (7, "3", "ariados")),
                     ((9, "50a", "golduck"), (9, "50b", "golduck")),
                     ((9, "12", "glaceonex"), (9, "12", "glaceonexholidaycalendar"))):
            with self.subTest(a=a, b=b):
                self.assertNotEqual(print_key(a), print_key(b))


class SingleLanguageTests(unittest.TestCase):
    def test_confirmed_wins(self):
        self.assertEqual(single_language("JAPANESE", {"ENGLISH": "confirmado", "CHINESE": "não encontrado"}),
                         ("confirmado", ""))

    def test_absence_in_catalogue_is_only_a_candidate(self):
        status, reason = single_language("JAPANESE", dict(NONE_FOUND))
        self.assertEqual(status, "inconclusivo")
        self.assertTrue(reason.startswith(CANDIDATE))
        self.assertIn("CHT: não pesquisado", reason)
        self.assertIn("ausência não comprova", reason)

    def test_limitless_absence_without_cht_is_not_exclusive(self):
        status, reason = single_language("JAPANESE", dict(NONE_FOUND), {"ENGLISH": "ausente"})
        self.assertEqual(status, "inconclusivo")
        self.assertIn("EN: ausência confirmada por fonte externa", reason)

    def test_english_card_with_limitless_check(self):
        st = {"JAPANESE": "exclusiva: sem impressão japonesa (Limitless)", "CHINESE": "não encontrado"}
        status, reason = single_language("ENGLISH", st, {"JAPANESE": "ausente"})
        self.assertEqual(status, "inconclusivo")
        self.assertIn("JP: ausência confirmada", reason)

    def test_international_print_found_removes_candidate(self):
        # antes: build_xlsx mantinha 'exclusiva' quando o lim_jp achava impressão internacional
        status, reason = single_language("JAPANESE", dict(NONE_FOUND), {"ENGLISH": ["Pikachu (SVI) #25"]})
        self.assertEqual(status, "inconclusivo")
        self.assertFalse(reason.startswith(CANDIDATE))
        self.assertIn("Pikachu (SVI) #25", reason)

    def test_exclusive_requires_proof_in_every_target(self):
        ev = {"ENGLISH": "ausente", "CHINESE": "ausente", "CHINESE_T": "ausente"}
        self.assertEqual(single_language("JAPANESE", dict(NONE_FOUND), ev)[0], "exclusiva")

    def test_other_inconclusive_reason_is_not_a_candidate(self):
        st = {"ENGLISH": "inconclusivo: carta sem imagem no PokeData", "CHINESE": "não encontrado"}
        self.assertEqual(single_language("JAPANESE", st), ("inconclusivo", ""))


class MatchLevelTests(unittest.TestCase):
    def test_art_level_and_print_never_checked(self):
        self.assertEqual(match_level([40, 55]), ("confirmada", "não conferida"))
        self.assertEqual(match_level([39, 80]), ("provável", "não conferida"))
        self.assertEqual(match_level(["", None]), ("confirmada", "não conferida"))


class SnapshotRevisionTests(unittest.TestCase):
    def test_inherited_exclusives_never_stay_exclusive(self):
        for lang, crit in (("ENGLISH", "Sem impressão japonesa segundo o Limitless e sem equivalente chinês no PokeData"),
                           ("JAPANESE", "Arte sem equivalente em inglês nem em chinês simplificado no PokeData"),
                           ("JAPANESE", "Arte sem equivalente ...; Limitless também não lista impressão internacional")):
            with self.subTest(crit=crit):
                status, reason = rs.reclassify_exclusive(lang, crit)
                self.assertEqual(status, "inconclusivo")
                self.assertTrue(reason.startswith(CANDIDATE))

    def test_old_key_drops_distinct_print_new_key_keeps_it(self):
        row = {"set_id": 7, "Nome base": "Ariados", "Códigos equivalentes": "JP: SV1 003 | CN: CSV1C 003"}
        a, b = dict(row, **{"Número": "H3"}), dict(row, **{"Número": "3"})
        self.assertEqual(rs.old_sig(a), rs.old_sig(b))
        self.assertNotEqual(rs.new_sig(a), rs.new_sig(b))
        dup = dict(row, **{"Número": "003"})
        self.assertEqual(rs.new_sig(b), rs.new_sig(dup))

    def test_local_code_notation(self):
        cases = {"M4 114/083": ("M4", "114"), "SM4p 120/114": ("SM4P", "120"), "SM4+ 120": ("SM4P", "120"),
                 "PROMOSV08 092/SV-P": ("SV-P", "92"), "SV-P 092": ("SV-P", "92"),
                 "CBB5C 08 07/07": ("CBB5C", "807"), "CBB5C 0807": ("CBB5C", "807"),
                 "CSV9.5C 239/208": ("CSV9.5C", "239")}
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(rs.local_code(raw), expected)

    def test_same_print(self):
        codes = {("151C", "152"), ("SV4A", "210")}
        self.assertEqual(rs.same_print(("SV4A", "210"), codes), "igual")
        self.assertEqual(rs.same_print(("151C4", "152"), codes), "subproduto")
        self.assertIsNone(rs.same_print(("CSM2CC", "71"), {("CSM2DC", "195")}))

    def test_cht_pairs_are_preserved(self):
        pair = {"Idioma": "Chinês tradicional", "Código local completo": "M4 114/083"}
        self.assertTrue(rs.reconcile(pair, {"status": "unico"}, {}).startswith("preservado"))


class PipelineWiringTests(unittest.TestCase):
    """As etapas do pipeline usam as regras corrigidas (não rodam: dependem de dados baixados)."""

    def test_scripts_import_identity_rules(self):
        pipeline = ROOT / "pipeline"
        build = (pipeline / "build_xlsx.py").read_text(encoding="utf-8")
        self.assertIn("sig = print_key(b)", build)
        self.assertIn("sig = (print_key(k),", build)
        self.assertNotIn("re.search(r'(\\d+)$', b[1])", build)
        self.assertIn("single_language(LANG[k], per_lang", build)
        self.assertIn("single_language(L, dict(st), ev)", (pipeline / "assemble.py").read_text(encoding="utf-8"))
        self.assertIn("startswith(CANDIDATE)", (pipeline / "lim_jp.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
