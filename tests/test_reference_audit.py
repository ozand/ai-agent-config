from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "reference_audit.py"
sys.path.insert(0, str(ROOT / "scripts"))


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
        import os
        supported = os.name == "nt" or (hasattr(os, "O_NOFOLLOW") and os.open in os.supports_dir_fd)
        if not supported and self._testMethodName != "test_platform_without_secure_open_primitives_fails_closed":
            self.skipTest("secure bounded file opening is unsupported on this platform")
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
        import reference_audit
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["records"][0]["exact_path"], "exact_path")
        self.assertIn("| ID | Source |", a.stdout)
        self.assertIn("```mermaid", a.stdout)
        table = reference_audit.render_table(data)
        self.assertEqual(len(table.splitlines()), 2 + len(data["records"]))
        self.assertTrue(table.splitlines()[1].startswith("|---|"))
        graph = reference_audit.render_mermaid(data)
        self.assertEqual(len(graph.splitlines()), 1 + len(data["records"]))
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

    def test_input_symlink_swap_between_validation_and_open_fails_closed(self):
        import os
        import reference_audit
        if os.name == "nt" or not hasattr(os, "O_NOFOLLOW") or not reference_audit.HAS_SECURE_POSIX_OPEN:
            self.skipTest("POSIX descriptor-relative no-follow open required")
        source = self.write("input.md", "contents that must be read\n")
        outside = self.base / "outside.md"
        outside.write_text("OUTSIDE_SENTINEL", encoding="utf-8")
        real_open = os.open
        swapped = False
        def swapping_open(path, flags, *args, **kwargs):
            nonlocal swapped
            if path == "input.md" and kwargs.get("dir_fd") is not None and not swapped:
                source.unlink()
                source.symlink_to(outside)
                swapped = True
            return real_open(path, flags, *args, **kwargs)
        from unittest import mock
        with mock.patch("reference_audit.os.open", side_effect=swapping_open):
            with self.assertRaises(OSError):
                reference_audit.build_records([source], [self.allowed])
        self.assertTrue(swapped)
        self.assertEqual(outside.read_text(encoding="utf-8"), "OUTSIDE_SENTINEL")

    def test_symlink_reference_outside_root_is_explicitly_unresolved(self):
        outside = self.base / "outside.md"
        outside.write_text("OUTSIDE_SENTINEL", encoding="utf-8")
        target = self.allowed / "escape.md"
        try:
            target.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unsupported")
        source = self.write("index.md", "See [outside](escape.md)\n")
        result = self.cli("--format", "json", str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads(result.stdout)["records"][0]
        self.assertEqual(record["exact_path"], "out_of_scope")
        self.assertEqual(record["entity_match"], "unchecked")
        self.assertNotIn("OUTSIDE_SENTINEL", result.stdout)

    def test_parent_traversal_never_resolves_outside(self):
        outside = self.base / "outside.md"
        outside.write_text("outside-secret", encoding="utf-8")
        source = self.write("index.md", "See ../outside.md\n")
        result = self.cli("--format", "json", str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertNotIn("outside-secret", result.stdout)
        self.assertNotIn("exact_path", [r["exact_path"] for r in data["records"]])

    def test_table_projection_normalizes_control_lines(self):
        import reference_audit
        data = {"records": [{"id": "R1", "source": "S1", "line": 1,
            "target": "first\r\nsecond", "relation": "markdown_link",
            "exact_path": "unchecked", "entity_match": "unchecked",
            "binding": "relative", "requirement": "unknown"}]}
        table = reference_audit.render_table(data)
        self.assertNotIn("\r", table)
        self.assertEqual(len(table.splitlines()), 3)
        self.assertEqual(table.splitlines()[-1].count("|"), 10)
        self.assertIn("first  second", table)
        self.assertIn("first  second", table)

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
        self.write("other.md", "target\n")
        result = self.cli("--format", "json", str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(result.stdout)["records"]
        self.assertIn("frontmatter_candidate", [r["relation"] for r in rows])
        dynamic = next(r for r in rows if r["binding"] == "dynamic")
        self.assertEqual(dynamic["entity_match"], "unchecked")
        self.assertEqual(dynamic["exact_path"], "unchecked")

    def test_sensitive_filename_is_not_emitted_in_any_view(self):
        secret_name = "ghp_" + "Q" * 24 + ".md"
        target = self.write(secret_name, "target\n")
        source = self.write("source.md", f"See [{secret_name}]({secret_name})\n")
        for view in ("json", "table", "mermaid", "all"):
            result = self.cli("--format", view, str(source), str(target))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(secret_name, result.stdout)
            self.assertNotIn("sk-" + "Z" * 20, result.stdout)

    def test_github_token_filename_is_redacted_across_all_views(self):
        secret_name = "ghp_" + "Q" * 24 + ".md"
        source = self.write("source.md", f"[secret]({secret_name})\\n")
        target = self.write(secret_name, "candidate\\n")
        for view in ("json", "table", "mermaid", "all"):
            result = self.cli("--format", view, str(source), str(target))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(secret_name, result.stdout)
            self.assertNotIn("ghp_", result.stdout)

    def test_mermaid_filename_cannot_inject_graph_structure(self):
        name = "source.md"
        source = self.write(name, 'See [x](target.md\"]\n  X --> Y\n  Z[\".md)\n')
        target = self.write("target.md", "target\n")
        result = self.cli("--format", "mermaid", str(source), str(target))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('X --> Y', result.stdout)
        self.assertNotIn('Z["', result.stdout)



if __name__ == "__main__":
    unittest.main()
