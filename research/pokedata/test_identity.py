"""Regressão offline das regras de identidade e exclusividade do pipeline (sem pickles)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "pipeline"))
from identity import (JP_INTL, JP_UNCHECKED, correspondence_signature, dedupe_ranked,  # noqa: E402
                      number_identity, reclassify_jp_exclusive)


class NumberIdentityTests(unittest.TestCase):
    def test_zero_padding_is_same_card(self):
        self.assertEqual(number_identity("036"), number_identity("36"))

    def test_prefix_and_suffix_are_identity(self):
        # casos reais do snapshot perdidos pelo dedupe antigo
        self.assertNotEqual(number_identity("H3"), number_identity("3"))
        self.assertNotEqual(number_identity("50a"), number_identity("50b"))
        self.assertNotEqual(number_identity("GG01"), number_identity("001"))
        self.assertNotEqual(number_identity("TG01"), number_identity("TG02"))

    def test_denominator_is_never_the_key(self):
        self.assertNotEqual(number_identity("121/106"), number_identity("122/106"))


class DedupeTests(unittest.TestCase):
    def test_only_double_listing_of_same_card_is_dropped(self):
        keys = [(1, "036", "pikachu"), (1, "36", "pikachu"), (1, "GG01", "pikachu"),
                (1, "001", "pikachu"), (1, "26", "glaceonex"), (1, "26", "glaceonexholidaycalendar")]
        self.assertEqual(dedupe_ranked(keys), [keys[0], keys[2], keys[3], keys[4], keys[5]])

    def test_correspondence_signature_keeps_name_and_full_number(self):
        a = correspondence_signature((574, "048", "raikou"), ("j",), ())
        b = correspondence_signature((574, "48", "raikoucosmo"), ("j",), ())
        c = correspondence_signature((574, "48", "raikou"), ("j",), ())
        self.assertNotEqual(a, b)
        self.assertEqual(a, c)


class ExclusivityTests(unittest.TestCase):
    EXC = {"ENGLISH": "não encontrado", "CHINESE": "não encontrado", "geral": "exclusiva"}

    def test_checked_without_international_print_stays_exclusive(self):
        self.assertEqual(reclassify_jp_exclusive(self.EXC, True, [])["geral"], "exclusiva")

    def test_international_print_listed_is_not_exclusive(self):
        out = reclassify_jp_exclusive(self.EXC, True, ["Azumarill (SVBA) #14"])
        self.assertEqual((out["geral"], out["ENGLISH"], out["herdado"]), ("inconclusivo", JP_INTL, "exclusiva"))

    def test_absence_alone_is_not_exclusive(self):
        out = reclassify_jp_exclusive(self.EXC, False, [])
        self.assertEqual((out["geral"], out["ENGLISH"]), ("inconclusivo", JP_UNCHECKED))

    def test_input_not_mutated_and_other_status_untouched(self):
        original = dict(self.EXC)
        reclassify_jp_exclusive(self.EXC, False, [])
        self.assertEqual(self.EXC, original)
        conf = {"ENGLISH": "confirmado", "geral": "confirmado"}
        self.assertEqual(reclassify_jp_exclusive(conf, False, []), conf)


if __name__ == "__main__":
    unittest.main()
