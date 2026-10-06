"""Offline regression fixtures; never downloads catalog data."""
import collections
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent / 'pipeline'
sys.path.insert(0, str(ROOT))
from identity_policy import add_bridge_candidates, art_eligible, overall_status
from limitless_parse import parse_prints
from fetch_cards import collect, fetch_json, validate_cards, validate_sets
import common

class PolicyTests(unittest.TestCase):
    def test_bridge_only_candidate(self):
        conf = {'EN_JA': {'en': {'jp': {}}}, 'EN_CH': {}}
        probable = {'EN_CH': {}}
        add_bridge_candidates(conf, {'CH_JA': {'jp': {'cn': {}}}}, probable, {'EN_CH': {}}, set())
        self.assertIn('cn', probable['EN_CH']['en'])
        self.assertEqual(conf['EN_CH'], {})

    def test_rejected_direct_pair_not_resurrected(self):
        conf = {'EN_JA': {'en': {'jp': {}}}, 'EN_CH': {}}
        probable = {'EN_CH': {}}
        add_bridge_candidates(conf, {'CH_JA': {'jp': {'cn': {}}}}, probable, {'EN_CH': {}}, {('en', 'cn')})
        self.assertEqual(probable['EN_CH'], {})

    def test_no_automatic_exclusivity(self):
        self.assertEqual(overall_status(['não encontrada', 'não encontrada']), 'não encontrada')
        self.assertEqual(overall_status(['inconclusivo', 'não encontrada']), 'inconclusivo')

    def test_todo_art_gate(self):
        self.assertFalse(art_eligible(({'n_in': 39}, 2, 'A2')))
        self.assertFalse(art_eligible(({'n_in': 80}, 0, 'A1')))
        self.assertTrue(art_eligible(({'n_in': 40}, 1, 'A1')))

    def test_missing_malformed_empty_sections(self):
        self.assertIsNone(parse_prints('No section', True))
        self.assertIsNone(parse_prints('JP. Prints', True))
        self.assertIsNone(parse_prints('JP. Prints <a href="/cards/jp/SV/1">bad</a></table>', True))
        self.assertEqual(parse_prints('JP. Prints </table>', True), [])

    def test_valid_print_sections(self):
        self.assertEqual(parse_prints('JP. Prints <a href="/cards/jp/SV/1">Set &amp; One<span></span></a></table>', True), [('SV', '1', 'Set & One')])
        self.assertEqual(parse_prints('Int. Prints <a href="/cards/SV/2">Set<span></span></a></table>', False), [('SV', '2', 'Set')])

class CollectionTests(unittest.TestCase):
    def test_invalid_cache_refetched(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'cards.json'; path.write_text('{')
            def download(url, target):
                target.write_text('[]'); return '200'
            value, status = fetch_json('fixture', path, lambda v: validate_cards(v, 1), download, lambda _: None)
            self.assertEqual((value, status), ([], 'downloaded'))
            self.assertEqual(json.loads(path.read_text()), [])

    def test_wrong_set_and_duplicate_rejected(self):
        row = dict(id=1, set_id=1, name='Card', num='TG01/TG30', img_url='image', secret=False)
        for rows, sid in [([row], 2), ([row, row], 1), ([{}], 1)]:
            with self.assertRaises(ValueError): validate_cards(rows, sid)
        with self.assertRaises(ValueError): validate_sets([])

    def test_failed_download_preserves_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'cards.json'; path.write_text('invalid')
            with self.assertRaises(RuntimeError):
                fetch_json('fixture', path, lambda v: validate_cards(v, 1), lambda u, p: '503', lambda _: None)
            self.assertEqual(path.read_text(), 'invalid')
            self.assertFalse(path.with_suffix('.json.download').exists())

    def test_incomplete_collection_preserves_aggregate_and_blocks_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'all_cards.json').write_text('["previous"]')
            def fetch(url, path, validator):
                if url.endswith('/sets'): return [{'id': 1}, {'id': 2}], 'fixture'
                if 'set_id=2' in url: raise RuntimeError('fixture failure')
                return [], 'fixture'
            with self.assertRaises(RuntimeError): collect(root, fetch, pause=lambda _: None)
            self.assertEqual(json.loads((root / 'all_cards.json').read_text()), ['previous'])
            self.assertFalse(json.loads((root / 'collection_manifest.json').read_text())['complete'])
            cwd = os.getcwd()
            try:
                os.chdir(root)
                with self.assertRaisesRegex(RuntimeError, 'Incomplete collection'): common.load()
            finally: os.chdir(cwd)

    def test_complete_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            def fetch(url, path, validator):
                return ([{'id': 1}], 'fixture') if url.endswith('/sets') else ([], 'fixture')
            self.assertEqual(collect(Path(tmp), fetch), [])
            self.assertTrue(json.loads((Path(tmp) / 'collection_manifest.json').read_text())['complete'])

    def test_rate_limit_backs_off_longer_and_retries(self):
        """HTTP 429 não é falha definitiva: espera bem mais que os 2-11 s dos erros comuns e tenta de novo."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'cards.json'
            codes = iter(['429', '429', '200'])
            def download(url, target):
                code = next(codes)
                if code == '200': target.write_text('[]')
                return code
            pauses = []
            value, status = fetch_json('fixture', path, lambda v: validate_cards(v, 1), download, pauses.append)
            self.assertEqual((value, status), ([], 'downloaded'))
            self.assertGreaterEqual(min(pauses[:2]), 30)

    def test_rate_limit_eventually_gives_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'cards.json'
            with self.assertRaisesRegex(RuntimeError, 'HTTP 429'):
                fetch_json('fixture', path, lambda v: validate_cards(v, 1), lambda u, p: '429', lambda _: None)

    def test_failed_sets_retried_serially_before_giving_up(self):
        """Depois da passada paralela, os sets que falharam são refeitos um a um antes de declarar coleta incompleta."""
        with tempfile.TemporaryDirectory() as tmp:
            calls = collections.Counter()
            def fetch(url, path, validator):
                if url.endswith('/sets'): return [{'id': 1}, {'id': 2}], 'fixture'
                calls[url] += 1
                if url.endswith('set_id=2') and calls[url] == 1: raise RuntimeError('HTTP 429')
                return [], 'fixture'
            self.assertEqual(collect(Path(tmp), fetch, pause=lambda _: None), [])
            manifest = json.loads((Path(tmp) / 'collection_manifest.json').read_text())
            self.assertTrue(manifest['complete'])
            self.assertEqual(sum(v for u, v in calls.items() if u.endswith('set_id=2')), 2)
            self.assertEqual([r['status'] for r in manifest['sets']], ['fixture', 'fixture'])

if __name__ == '__main__': unittest.main()
