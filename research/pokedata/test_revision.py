"""Offline checks of inherited classification and two documented blockers.

Expected failures reproduce known defects; they do not validate those behaviors.
AST extraction runs the actual pure code without loading private pickle caches.
"""
import ast
from collections import defaultdict
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent / 'pipeline'

def load_function(filename, name, namespace=None):
    tree = ast.parse((ROOT / filename).read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = namespace or {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), filename, 'exec'), scope)
    return scope[name]

class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.reason = load_function('assemble.py', 'motivo', {
            'uinfo': {'a': {'_dex': 1}, 'b': {'_dex': 2}},
            'M_ESP': 'species', 'M_NOME': 'name', 'M_PTS': 'points'})

    def test_39_points_is_probable(self):
        self.assertEqual(self.reason('a', 'b', ({'n_in': 39}, 2, 'A2')), 'points')

    def test_40_points_passes_art_tier_only(self):
        self.assertEqual(self.reason('a', 'b', ({'n_in': 40}, 2, 'A1')), '')

    def test_different_species_demoted_even_with_high_score(self):
        self.assertEqual(self.reason('a', 'b', ({'n_in': 150}, 0, 'C1')), 'species')

    def test_placeholder_four_names_and_three_name_control(self):
        import numpy as np
        import runpy
        import sys
        import tempfile
        import types
        import json
        import os
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            units = {(i, str(i), f'name{i}'): [] for i in range(7)}
            rep = {f'{i}|{i}|name{i}': i for i in range(7)}
            (root / 'unit_rep.json').write_text(json.dumps(rep))
            (root / 'feat_ids_0.json').write_text(json.dumps(list(range(7))))
            (root / 'feat_ids_1.json').write_text('[]')
            g = np.zeros((7, 64)); g[4:, :] = 1
            np.save(root / 'feat_g_0.npy', g)
            np.save(root / 'feat_g_1.npy', np.empty((0, 64)))
            common = types.ModuleType('common')
            common.load = lambda: ({}, [])
            common.art_units = lambda cards: units
            old = sys.modules.get('common'); cwd = os.getcwd()
            try:
                sys.modules['common'] = common; os.chdir(root)
                runpy.run_path(str(ROOT / 'detect_placeholders.py'), run_name='__main__')
                bad = json.loads((root / 'cardback_units.json').read_text())
                self.assertEqual({row[0] for row in bad}, {0, 1, 2, 3})
            finally:
                os.chdir(cwd)
                if old is None: sys.modules.pop('common', None)
                else: sys.modules['common'] = old

    @unittest.expectedFailure
    def test_bridge_must_not_override_gray_direct_pair(self):
        tree = ast.parse((ROOT / 'assemble.py').read_text())
        loop = next(n for n in tree.body if isinstance(n, ast.For)
                    and ast.unparse(n.iter) == "CONF['EN_JA'].items()")
        scope = dict(CONF={'EN_JA': {'en': {'jp': {}}}, 'EN_CH': {}},
                     REV={'CH_JA': {'jp': {'cn': {}}}}, PROV={'EN_CH': {}},
                     GRAY={'EN_CH': {'en': {'cn': ({}, 2, 'weak')}}},
                     VIA=defaultdict(dict), name_compat=lambda a, b: 2, M_VIA='via')
        exec(compile(ast.Module(body=[loop], type_ignores=[]), 'assemble.py', 'exec'), scope)
        self.assertNotIn('cn', scope['VIA'].get('en', {}))

    @unittest.expectedFailure
    def test_full_card_numbers_must_not_collapse_to_denominator(self):
        import re
        from datetime import datetime
        rank = load_function('build_xlsx.py', 'rank',
                             {'re': re, 'sdate': lambda k: datetime(2020, 1, 1)})
        candidates = {(1, '121/106', 'card_a'): ({'n_in': 80}, 2, 'A1'),
                      (1, '122/106', 'card_b'): ({'n_in': 70}, 2, 'A1')}
        self.assertEqual(len(rank((2, '1', 'source'), candidates)), 2)

if __name__ == '__main__':
    unittest.main()
