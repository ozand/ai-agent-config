from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "reference_audit.py"


class ReferenceAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.allowed = self.base / "allowed"
        self.allowed.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name: str, text: str) -> Path:
        path = self.allowed / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def cli(self, *args: str):
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.allowed), *args],
                              text=True, capture_output=True, check=False)

    def test_exact_relative_markdown_link_and_deterministic_views(self):
        self.write("docs/guide.md", "# Guide\n")
        source = self.write("index.md", "See [guide](docs/guide.md).\n")
        a = self.cli("--format", "all", str(source))
        b = self.cli("--format", "all", str(source))
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertEqual(a.stdout, b.stdout)
        data = json.loads(a.stdout.split("\n\n", 1)[0])
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["records"][0]["exact_path"], "exact_path")
        self.assertIn("| ID | Source |", a.stdout)
        self.assertIn("```mermaid", a.stdout)
        self.assertEqual(sum(data["counts"]["exact_path"].values()), len(data["records"]))

    def test_entity_match_does_not_imply_exact_path(self):
        target = self.write("skill.md", "content\n")
        source = self.write("index.md", "Use alias skill.md by name.\n")
        result = self.cli("--format", "json", str(source), str(target))
        self.assertEqual(result.returncode, 0, result.stderr)
        row = json.loads(result.stdout)["records"][0]
        self.assertEqual(row["entity_match"], "entity_match")
        self.assertEqual(row["exact_path"], "not_found_in_scope")

    def test_root_escape_and_symlink_escape_rejected_without_path_leak(self):
        outside = self.base / "secret-outside.md"
        outside.write_text("do not echo", encoding="utf-8")
        direct = self.cli("--format", "json", str(outside))
        self.assertEqual(direct.returncode, 2)
        self.assertNotIn(str(outside), direct.stderr)
        link = self.allowed / "escape.md"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unsupported")
        result = self.cli("--format", "json", str(link))
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(str(outside), result.stderr)

    def test_parent_traversal_never_resolves_outside(self):
        outside = self.base / "outside.md"
        outside.write_text("outside-secret", encoding="utf-8")
        source = self.write("index.md", "See ../outside.md\n")
        result = self.cli("--format", "json", str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertNotIn("outside-secret", result.stdout)
        self.assertNotIn("exact_path", [r["exact_path"] for r in data["records"]])

    def test_size_limit_and_invalid_utf8_fail_closed(self):
        large = self.write("large.md", "x" * 1_000_001)
        self.assertEqual(self.cli("--format", "json", str(large)).returncode, 2)
        bad = self.allowed / "bad.md"
        bad.write_bytes(b"\xff")
        self.assertEqual(self.cli("--format", "json", str(bad)).returncode, 2)

    def test_secret_and_absolute_path_redaction_in_all_views(self):
        source = self.write("index.md", "See C:/private/local.md and sk-" + "A" * 20 + "\n")
        result = self.cli("--format", "all", str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("C:/private/local.md", result.stdout)
        self.assertNotIn("sk-", result.stdout)

    def test_frontmatter_and_unsupported_dynamic_target(self):
        source = self.write("prompt.md", "---\ninclude: ./guide.md\n---\nUse ${ROOT}/other.md\n")
        self.write("guide.md", "guide\n")
        result = self.cli("--format", "json", str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(result.stdout)["records"]
        self.assertIn("frontmatter_candidate", [r["relation"] for r in rows])
        self.assertIn("dynamic", [r["binding"] for r in rows])


if __name__ == "__main__":
    unittest.main()
