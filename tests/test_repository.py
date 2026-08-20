from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class RepositoryPolicyTests(unittest.TestCase):
    def test_rendered_templates_are_current(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/check_rendered.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Rendered client templates are current", result.stdout)

    def test_validate_script_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/validate.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Validation passed", result.stdout)

    def test_model_catalogs_match(self) -> None:
        canonical = {model["id"] for model in load_json("catalog/models.json")["models"]}
        pi = {
            model["id"]
            for model in load_json("clients/pi/models.template.json")["providers"]["litellm-edge"]["models"]
        }
        opencode = set(
            load_json("clients/opencode/opencode.template.jsonc")["provider"]["litellm-edge"]["models"]
        )
        self.assertEqual(len(canonical), 40)
        self.assertEqual(canonical, pi)
        self.assertEqual(canonical, opencode)

    def test_shared_defaults(self) -> None:
        pi = load_json("clients/pi/settings.template.json")
        opencode = load_json("clients/opencode/opencode.template.jsonc")
        self.assertEqual(pi["defaultModel"], "cl/gpt-5.6-luna")
        self.assertEqual(opencode["model"], "litellm-edge/cl/gpt-5.6-luna")
        self.assertEqual(
            opencode["small_model"],
            "litellm-edge/an/gemini-3.7-flash-low",
        )

    def test_secret_references_are_not_literals(self) -> None:
        pi = load_json("clients/pi/models.template.json")
        opencode = load_json("clients/opencode/opencode.template.jsonc")
        self.assertTrue(
            pi["providers"]["litellm-edge"]["apiKey"].startswith("!powershell.exe")
        )
        self.assertEqual(
            opencode["provider"]["litellm-edge"]["options"]["apiKey"],
            "{env:LITELLM_EDGE_API_KEY}",
        )

    def test_qwen_boundaries(self) -> None:
        canonical = next(
            model
            for model in load_json("catalog/models.json")["models"]
            if model["id"] == "un/qwen3.8-27b-gguf"
        )
        pi = next(
            model
            for model in load_json("clients/pi/models.template.json")["providers"]["litellm-edge"]["models"]
            if model["id"] == "un/qwen3.8-27b-gguf"
        )
        opencode = load_json("clients/opencode/opencode.template.jsonc")["provider"]["litellm-edge"]["models"]["un/qwen3.8-27b-gguf"]
        self.assertEqual(canonical["runtimeContextWindow"], 98304)
        self.assertEqual(pi["contextWindow"], 73728)
        self.assertEqual(pi["input"], ["text"])
        self.assertNotIn("limit", opencode)
        self.assertEqual(opencode["modalities"]["input"], ["text"])

    def test_all_agent_models_are_provider_qualified(self) -> None:
        pattern = re.compile(r"^litellm-edge/(?:an|cl|un)/")
        for path in (ROOT / "clients/opencode/agents").glob("*.md"):
            match = re.search(
                r"^model:\s*(\S+)\s*$",
                path.read_text(encoding="utf-8"),
                flags=re.MULTILINE,
            )
            self.assertIsNotNone(match, path)
            self.assertRegex(match.group(1), pattern, path)

    def test_policy_and_profiles_reference_current_defaults(self) -> None:
        policy = (ROOT / "catalog/model-policy.yaml").read_text(encoding="utf-8")
        default_profile = (ROOT / "profiles/default.yaml").read_text(encoding="utf-8")
        local_profile = (ROOT / "profiles/local-first.yaml").read_text(encoding="utf-8")
        self.assertIn("interactive: litellm-edge/cl/gpt-5.6-luna", policy)
        self.assertIn(
            "small_fast: litellm-edge/an/gemini-3.7-flash-low",
            policy,
        )
        self.assertIn(
            "interactive_model: litellm-edge/cl/gpt-5.6-luna",
            default_profile,
        )
        self.assertIn("pi_context_window: 73728", local_profile)
        self.assertIn("runtime_context_window: 98304", local_profile)

    def test_runtime_files_are_ignored(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for required in ("auth.json", "models-store.json", "sessions/", "secrets/"):
            self.assertIn(required, ignore)


if __name__ == "__main__":
    unittest.main()
