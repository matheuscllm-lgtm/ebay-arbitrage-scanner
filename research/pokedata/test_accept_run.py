"""Testes offline das conferências de aceite de uma execução nova (accept_run.py)."""
import unittest

from accept_run import (check_comparison, check_correspondence, check_coverage, check_cht,
                        check_exclusives, check_manifest)


def ref(i, nome='Pikachu', cod='25/102', st='Base Set'):
    return {'ID EN': i, 'Carta inglesa — referência': nome, 'Código EN': cod, 'Set EN': st}


def cov(i, loc='único', geral='arte confirmada', **kw):
    row = {'ID EN (PR #53)': i, 'Carta inglesa — referência': 'Pikachu', 'Código EN': '25/102', 'Set EN': 'Base Set',
           'Localização neste catálogo': loc, 'Situação geral (esta rodada)': geral}
    row.update(kw)
    return row


class ManifestTests(unittest.TestCase):
    def test_complete_without_failures(self):
        ok, info = check_manifest({'complete': True, 'sets': [{'status': 'cached'}, {'status': 'downloaded'}], 'cards': 2})
        self.assertTrue(ok); self.assertEqual(info['sets'], 2)

    def test_incomplete_or_failed(self):
        self.assertFalse(check_manifest({'complete': False, 'sets': []})[0])
        self.assertFalse(check_manifest({'complete': True, 'sets': [{'status': 'failed'}]})[0])
        self.assertFalse(check_manifest(None)[0])


class ExclusiveTests(unittest.TestCase):
    def test_no_automatic_exclusive(self):
        catalogs = {'EN': [{'Carta única': 1, 'Situação geral': 'arte confirmada'}]}
        ok, info = check_exclusives(catalogs, [])
        self.assertTrue(ok); self.assertEqual(info['exclusivas'], 0)

    def test_exclusive_flagged(self):
        catalogs = {'JP': [{'Carta única': 1, 'Situação geral': 'exclusiva'}]}
        ok, info = check_exclusives(catalogs, [{'Critério': 'x'}])
        self.assertFalse(ok); self.assertEqual(info['exclusivas'], 1)


class CoverageTests(unittest.TestCase):
    def test_same_references_and_counts(self):
        original = [ref(1), ref(2, 'Raichu', '26/102')]
        rows = [cov(1), cov(2, loc='ambíguo: 2 registros', geral='')]
        rows[1].update({'Carta inglesa — referência': 'Raichu', 'Código EN': '26/102'})
        ok, info = check_coverage(rows, original)
        self.assertTrue(ok)
        self.assertEqual(info['referencias'], 2)
        self.assertEqual(info['ambiguas'], [2]); self.assertEqual(info['nao_localizadas'], [])
        self.assertEqual(info['situacao_geral'], {'arte confirmada': 1, '': 1})

    def test_reference_mismatch_fails(self):
        ok, info = check_coverage([cov(1)], [ref(1, nome='Outra')])
        self.assertFalse(ok)

    def test_duplicate_id_fails(self):
        ok, _ = check_coverage([cov(1), cov(1)], [ref(1), ref(1)])
        self.assertFalse(ok)


class ChtTests(unittest.TestCase):
    def test_preserved_fields(self):
        pair = {'ID EN': 1, 'Carta inglesa — referência': 'Pikachu', 'Código EN': '25/102', 'Set EN': 'Base Set',
                'Idioma': 'Chinês tradicional', 'Nome local': '皮卡丘', 'Código local completo': 'CS1a 1', 'Set / produto local': 'CS1a',
                'Raridade e acabamento': 'C', 'Status': 'Confirmada', 'Como foi validada': 'foto', 'Fonte local e complemento': 'loja'}
        row = {'ID EN (PR #53)': 1, 'Carta inglesa — referência': 'Pikachu', 'Código EN': '25/102', 'Set EN': 'Base Set',
               'Nome local (繁體)': '皮卡丘', 'Código local completo': 'CS1a 1', 'Set / produto local': 'CS1a', 'Raridade e acabamento': 'C',
               'Status (PR #53)': 'Confirmada', 'Como foi validada (PR #53)': 'foto', 'Fonte local': 'loja'}
        ok, info = check_cht([row], [pair, dict(pair, Idioma='Japonês')])
        self.assertTrue(ok); self.assertEqual(info['cht'], 1)
        self.assertFalse(check_cht([dict(row, **{'Nome local (繁體)': 'x'})], [pair])[0])


class ComparisonTests(unittest.TestCase):
    def test_same_pairs_and_summary(self):
        pairs = [{'ID EN': 1, 'Idioma': 'Japonês', 'Código local completo': 'SV1 1'},
                 {'ID EN': 1, 'Idioma': 'Chinês simplificado', 'Código local completo': 'CS1 1'}]
        compared = [{'id_en': '1', 'idioma': 'JP', 'codigo_pr53': 'SV1 1', 'resultado': 'igual (arte confirmada aqui)'},
                    {'id_en': '1', 'idioma': 'CHS', 'codigo_pr53': 'CS1 1', 'resultado': 'sem confirmação aqui: x'}]
        ok, info = check_comparison(compared, pairs)
        self.assertTrue(ok)
        self.assertEqual(info['registros'], 2)
        self.assertEqual(info['resultado']['JP | igual (arte confirmada aqui)'], 1)
        self.assertFalse(check_comparison(compared[:1], pairs)[0])


class CorrespondenceTests(unittest.TestCase):
    def test_identity_holds(self):
        cross = [{'Situação JP': 'arte confirmada', 'Situação CN simplificado': '', 'Cartas do PokeData nesta linha': 2},
                 {'Situação JP': 'arte confirmada', 'Situação CN simplificado': 'arte confirmada', 'Cartas do PokeData nesta linha': 1},
                 {'Situação JP': '', 'Situação CN simplificado': 'arte confirmada', 'Cartas do PokeData nesta linha': 1}]
        ok, info = check_correspondence(cross)
        self.assertTrue(ok)
        self.assertEqual((info['linhas'], info['jp'], info['chs'], info['ambos'], info['cartas']), (3, 2, 2, 1, 4))

    def test_row_without_confirmed_side_fails(self):
        ok, _ = check_correspondence([{'Situação JP': 'provável', 'Situação CN simplificado': '', 'Cartas do PokeData nesta linha': 1}])
        self.assertFalse(ok)


if __name__ == '__main__':
    unittest.main()
