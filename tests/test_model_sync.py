"""Regression checks for the bounded model routing synchronization."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ModelSyncTests(unittest.TestCase):
    def test_pi_roles_resolve_without_removed_fallbacks(self):
        settings = json.loads((ROOT / 'clients/pi/settings.template.json').read_text())
        catalog = json.loads((ROOT / 'catalog/models.json').read_text())
        ids = {'litellm-edge/' + m['id'] for m in catalog['models']}
        roles = settings['subagents']['agentOverrides']
        for role, config in roles.items():
            self.assertIn(config['model'], ids, role)
            self.assertNotIn('fallbackModels', config, role)
        self.assertEqual(roles['worker']['model'], 'litellm-edge/cl/gpt-6-luna')
        self.assertEqual(roles['reviewer'], {'model': 'litellm-edge/cl/gpt-6-luna', 'thinking': 'high'})
        self.assertEqual(roles['oracle'], {'model': 'litellm-edge/cl/gpt-6.1-sol', 'thinking': 'high'})

    def test_active_gemini_policy_matches_catalog(self):
        paths = [ROOT / 'catalog/model-policy.yaml', ROOT / 'catalog/agent-routing.yaml', ROOT / 'clients/pi/settings.template.json', ROOT / 'clients/opencode/opencode.template.jsonc', ROOT / 'clients/opencode/dcp.template.jsonc']
        paths.extend((ROOT / 'clients/opencode/agents').glob('*.md'))
        paths.extend((ROOT / 'profiles').glob('*.yaml'))
        for path in paths:
            self.assertNotIn('gemini-3.7', path.read_text(), str(path))
        routing = (ROOT / 'catalog/agent-routing.yaml').read_text().split('opencode:')[0]
        self.assertNotIn('fallbacks:', routing)


if __name__ == '__main__':
    unittest.main()
