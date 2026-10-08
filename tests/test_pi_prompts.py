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

    def test_validator_detects_common_github_token_prefixes(self) -> None:
        from scripts.validate_pi_prompts import ABSOLUTE_PATH, PRIVATE_TOOL_REFERENCES, SECRET_PATTERNS

        self.assertTrue(any(pattern.search("github_pat_" + "A" * 30) for pattern in SECRET_PATTERNS))
        self.assertTrue(any(pattern.search("ghp_" + "A" * 30) for pattern in SECRET_PATTERNS))
        self.assertIsNotNone(ABSOLUTE_PATH.search(r"D:\\Projects\\private\\prompt.md"))
        self.assertIsNotNone(ABSOLUTE_PATH.search(r"\\\\server\\share\\prompt.md"))
        self.assertIsNotNone(PRIVATE_TOOL_REFERENCES.search("github-issue-steward"))

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
