from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PiPromptValidationTests(unittest.TestCase):
    def test_shareable_prompts_pass_safety_validator(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/validate_pi_prompts.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("passed structure and secret-safety checks", result.stdout)

    def test_personal_prompt_directory_is_ignored(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".pi/agent/prompts/", ignore)

    def test_public_prompt_directory_is_documented(self) -> None:
        readme = (ROOT / "clients/pi/README.md").read_text(encoding="utf-8")
        self.assertIn("prompts/", readme)
        docs = (ROOT / "docs/pi-prompt-sharing.md").read_text(encoding="utf-8")
        self.assertIn("local or private", docs.lower())
        self.assertIn("project trust", docs.lower())


if __name__ == "__main__":
    unittest.main()
