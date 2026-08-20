from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install_config.py"


def run_tool(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class InstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.pi = self.root / "pi"
        self.oc = self.root / "opencode"
        self.pi.mkdir()
        self.oc.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def test_dry_run_is_default_and_does_not_mutate(self) -> None:
        models = self.pi / "models.json"
        settings = self.pi / "settings.json"
        self.write_json(models, {"providers": {"other": {"token": "<SET_LOCALLY>"}}})
        self.write_json(settings, {"theme": "user-theme", "defaultModel": "old/model"})
        before = {path: path.read_bytes() for path in (models, settings)}

        result = run_tool("--client", "pi", "--pi-dir", str(self.pi))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY RUN", result.stdout)
        self.assertEqual(before, {path: path.read_bytes() for path in (models, settings)})
        self.assertNotIn("do-not-print", result.stdout)
        self.assertNotIn("do-not-print", result.stdout)

    def test_pi_merge_preserves_unrelated_provider_and_local_models(self) -> None:
        self.write_json(
            self.pi / "models.json",
            {
                "providers": {
                    "other": {"baseUrl": "https://local.example", "models": [{"id": "local"}]},
                    "litellm-edge": {
                        "localSetting": True,
                        "models": [{"id": "local/private-model", "name": "Private"}],
                    },
                },
            },
        )
        self.write_json(
            self.pi / "settings.json",
            {"theme": "user-theme", "packages": ["npm:local-plugin@1"]},
        )

        result = run_tool("--client", "pi", "--pi-dir", str(self.pi), "--apply", "--confirm-apply", "--backup-dir", str(self.root / "backup"))

        self.assertEqual(result.returncode, 0, result.stderr)
        models = json.loads((self.pi / "models.json").read_text(encoding="utf-8"))
        self.assertEqual(models["providers"]["other"], {"baseUrl": "https://local.example", "models": [{"id": "local"}]})
        self.assertTrue(models["providers"]["litellm-edge"]["localSetting"])
        self.assertIn({"id": "local/private-model", "name": "Private"}, models["providers"]["litellm-edge"]["models"])
        settings = json.loads((self.pi / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["theme"], "user-theme")
        self.assertIn("npm:local-plugin@1", settings["packages"])
        self.assertTrue(list((self.root / "backup").glob("ai-agent-config-*/MANIFEST.txt")))

    def test_opencode_preserves_unrelated_sections_and_agents(self) -> None:
        self.write_json(
            self.oc / "opencode.json",
            {
                "plugin": ["local-plugin"],
                "mcp": {"local": {"command": "local"}},
                "provider": {"other": {"options": {"private": True}}},
                "agent": {"local-agent": {"model": "local/model", "custom": 1}},
            },
        )
        result = run_tool("--client", "opencode", "--opencode-dir", str(self.oc), "--agent", "docs-writer")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY RUN", result.stdout)
        self.assertIn("opencode/opencode.json", result.stdout)
        self.assertIn("opencode/agents/docs-writer.md", result.stdout)
        self.assertNotIn("local-plugin", result.stdout)  # only appears in unchanged context if diff requires it

        result = run_tool("--client", "opencode", "--opencode-dir", str(self.oc), "--agent", "docs-writer", "--apply", "--confirm-apply", "--backup-dir", str(self.root / "backup"))
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads((self.oc / "opencode.json").read_text(encoding="utf-8"))
        self.assertEqual(config["plugin"], ["local-plugin"])
        self.assertEqual(config["mcp"]["local"]["command"], "local")
        self.assertEqual(config["provider"]["other"]["options"]["private"], True)
        self.assertEqual(config["agent"]["local-agent"]["custom"], 1)
        self.assertIn('"plugin":', (self.oc / "opencode.json").read_text(encoding="utf-8"))

    def test_apply_requires_explicit_confirmation(self) -> None:
        result = run_tool("--client", "pi", "--pi-dir", str(self.pi), "--apply")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--confirm-apply", result.stderr)
        self.assertFalse((self.pi / "models.json").exists())

    def test_backup_is_readable_and_outside_repository(self) -> None:
        self.write_json(self.pi / "models.json", {"providers": {"local": {"enabled": True}}})
        self.write_json(self.pi / "settings.json", {"theme": "local"})
        backup = self.root / "backups"
        result = run_tool("--client", "pi", "--pi-dir", str(self.pi), "--apply", "--confirm-apply", "--backup-dir", str(backup))
        self.assertEqual(result.returncode, 0, result.stderr)
        manifests = list(backup.glob("ai-agent-config-*/MANIFEST.txt"))
        self.assertEqual(len(manifests), 1)
        self.assertIn("pi/models.json", manifests[0].read_text(encoding="utf-8"))
        self.assertNotIn(str(ROOT), result.stdout)

    def test_secret_reference_is_preserved_and_not_printed(self) -> None:
        self.write_json(
            self.pi / "models.json",
            {"providers": {"litellm-edge": {"apiKey": "!local-secret-reader", "models": []}}},
        )
        result = run_tool("--client", "pi", "--pi-dir", str(self.pi))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("!local-secret-reader", result.stdout)
        self.assertNotIn("<LOCAL_SECRET_VALUE>", result.stdout)

    def test_invalid_json_fails_before_apply_or_backup(self) -> None:
        (self.pi / "models.json").write_text("{ invalid", encoding="utf-8")
        backup = self.root / "backups"
        result = run_tool("--client", "pi", "--pi-dir", str(self.pi), "--apply", "--confirm-apply", "--backup-dir", str(backup))
        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid JSON", result.stderr)
        self.assertFalse(backup.exists())

    def test_windows_style_userprofile_resolution(self) -> None:
        env = os.environ.copy()
        env["USERPROFILE"] = str(self.root / "windows-home")
        env.pop("HOME", None)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--client", "pi"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("pi/models.json", result.stdout)
        self.assertIn("PLAN pi/models.json", result.stdout)


if __name__ == "__main__":
    unittest.main()
