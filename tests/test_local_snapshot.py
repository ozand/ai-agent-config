import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('renderer', ROOT / 'scripts/render_clients.py')
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


class LocalSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / 'catalog/models.json').read_text())
        self.pi = json.loads((ROOT / 'clients/pi/models.template.json').read_text())

    def test_snapshot_pi_parity(self):
        expected = [m['piModel'] for m in self.catalog['models']]
        self.assertEqual(self.pi['providers']['litellm-edge']['models'], expected)
        self.assertEqual(len(expected), 49)
        manifest = json.loads((ROOT / 'docs/model-snapshot-digests.json').read_text())
        for provider in ['litellm-edge', 'local']:
            entries = self.pi['providers'][provider]['models']
            digest = hashlib.sha256(json.dumps(entries, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
            self.assertEqual(digest, manifest['providers'][provider]['sha256'])
        self.assertEqual(self.pi['providers']['local']['models'], self.catalog['additionalProviders']['local']['models'])
        for mid in ['un/qwen3.6-27b-mtp', 'cl/gpt-5.5', 'om/glm-ocr-q8', 'om/qwen3-embedding-4b']:
            self.assertIn(mid, [m['id'] for m in expected])

    def test_mismatched_model_ids_rejected(self):
        import sys
        from unittest.mock import patch
        sys.path.insert(0, str(ROOT / 'scripts'))
        import validate
        bad = copy.deepcopy(self.catalog)
        bad['models'][0]['piModel']['id'] = 'different/route'
        with patch.object(validate, 'load_json', return_value=bad):
            with self.assertRaisesRegex(AssertionError, 'IDs differ'):
                validate.validate_catalog_parity()

    def test_unknown_pi_field_preserved(self):
        entry = copy.deepcopy(self.catalog['models'][0])
        entry['piModel']['futureField'] = {'nested': [None, 0, False]}
        self.assertEqual(renderer.pi_model(entry), entry['piModel'])
        self.assertEqual(renderer.pi_model(entry)['futureField']['nested'], [None, 0, False])

    def test_opencode_projection(self):
        qwen = next(m for m in self.catalog['models'] if m['id'] == 'un/qwen3.6-27b-mtp')
        projected = renderer.opencode_model(qwen)
        self.assertNotIn('limit', projected)  # Output limit absent, not invented.
        self.assertNotIn('compat', projected)
        self.assertNotIn('thinkingLevelMap', projected)
        self.assertEqual(projected['cost']['input'], qwen['piModel']['cost']['input'])

    def test_local_provider_placeholder(self):
        config = self.pi['providers']['local']
        self.assertEqual(config['baseUrl'], 'http://localhost:1234/v1')
        self.assertEqual(config['apiKey'], 'LOCAL_CONFIGURE_ME')


if __name__ == '__main__':
    unittest.main()
