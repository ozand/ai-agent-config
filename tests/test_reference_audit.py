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
        self.assertIn("| Source ID | Source path |", a.stdout)
        self.assertIn("```mermaid", a.stdout)
        table = reference_audit.render_table(data)
        self.assertEqual(len(table.splitlines()), 2 + len(data["records"]))
        self.assertTrue(table.splitlines()[1].startswith("|---|"))
        self.assertEqual(data["sources"][data["records"][0]["source"]], "index.md")
        graph = reference_audit.render_mermaid(data)
        self.assertEqual(len(graph.splitlines()), 1 + len(data["records"]))
        self.assertEqual(sum(data["counts"]["exact_path"].values()), len(data["records"]))

    def test_sanitize_preserves_relative_url_and_dynamic_slashes(self):
        import reference_audit
        self.assertEqual(reference_audit.sanitize("docs/guide.md"), "docs/guide.md")
        self.assertEqual(reference_audit.sanitize("https://example.test/a"), "https://example.test/a")
        self.assertEqual(reference_audit.sanitize("${ROOT}/guide.md"), "${ROOT}/guide.md")
        self.assertEqual(reference_audit.sanitize("C:/private/file.md"), "[PATH]")
        self.assertEqual(reference_audit.sanitize("/private/file.md"), "[PATH]")
        self.assertEqual(reference_audit.sanitize("file:///private/team/hidden.md"), "[PATH]")

    def test_targets_dynamic_fragments_duplicates_and_candidate_ids(self):
        import reference_audit
        self.write("docs/guide.md", "guide\n")
        target_a = self.write("a/guide.md", "[self](guide.md)\n")
        target_b = self.write("b/guide.md", "[self](guide.md)\n")
        source = self.write("index.md", "[relative](docs/guide.md) [web](https://example.test/a?q=1)\n[local](docs/guide.md#part?mode=x) [name](guide.md)\n[static](docs/guide.md) and [dynamic](${ROOT}/guide.md)\nexample.md is required\n")
        result = self.cli("--format", "json", str(source), str(source), str(target_a), str(target_b))
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(result.stdout)["records"]
        self.assertEqual(len(rows), 9)
        self.assertIn("docs/guide.md", [r["target"] for r in rows])
        self.assertIn("https://example.test/a?q=1", [r["target"] for r in rows])
        self.assertEqual(sum(r["relation"] == "path_candidate" for r in rows), 1)
        self.assertEqual(next(r for r in rows if r["relation"] == "path_candidate")["target"], "example.md")
        fragment = next(r for r in rows if r["target"] == "docs/guide.md#part?mode=x")
        self.assertEqual(fragment["exact_path"], "exact_path")
        fragment_only = self.write("fragment.md", "[section](#intro)\n")
        fragment_result = self.cli("--format", "json", str(fragment_only))
        self.assertEqual(json.loads(fragment_result.stdout)["records"][0]["exact_path"], "unchecked")
        static = next(r for r in rows if r["target"] == "docs/guide.md" and r["line"] == 3)
        dynamic = next(r for r in rows if r["target"] == "${ROOT}/guide.md")
        self.assertEqual(static["binding"], "relative")
        self.assertEqual(dynamic["binding"], "dynamic")
        self.assertEqual(next(r for r in rows if r["line"] == 4)["requirement"], "unknown")
        ambiguous = next(r for r in rows if r["target"] == "guide.md" and r["line"] == 2)
        self.assertEqual(ambiguous["entity_match"], "ambiguous")
        data = json.loads(result.stdout)
        for candidate in ambiguous["candidates"]:
            self.assertIn(candidate, data["sources"])
        self.assertEqual({data["sources"][candidate] for candidate in ambiguous["candidates"]}, {"a/guide.md", "b/guide.md"})
        for view in ("table", "mermaid", "all"):
            projected = self.cli("--format", view, str(source), str(target_a), str(target_b))
            self.assertEqual(projected.returncode, 0, projected.stderr)
            self.assertIn("docs/guide.md", projected.stdout)
            self.assertIn("https://example.test/a?q=1", projected.stdout)
            self.assertNotIn("\\\\n", projected.stdout)

    def test_plain_uri_path_is_not_invented_but_neighbor_reference_remains(self):
        import reference_audit
        records = list(reference_audit.extract("https://example.com/docs/a.md and see local.md"))
        self.assertEqual([row[1] for row in records], ["local.md"])
        self.assertEqual(records[0][2], "path_candidate")

    def test_markdown_optional_quoted_titles_resolve_destination(self):
        target = self.write("guide.md", "content\n")
        source = self.write("index.md", '[double](guide.md "A title") and [single](<guide.md> \'A title\')\n')
        result = self.cli("--format", "json", str(source), str(target))
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(result.stdout)["records"]
        self.assertEqual([row["target"] for row in rows], ["guide.md", "guide.md"])
        self.assertEqual([row["exact_path"] for row in rows], ["exact_path", "exact_path"])
        self.assertEqual([row["relation"] for row in rows], ["markdown_link", "markdown_link"])

    def test_reference_symlink_containment_without_target_read(self):
        target = self.write("target.md", "TARGET_CONTENT_SENTINEL\n")
        link = self.allowed / "inside.md"
        outside = self.base / "outside.md"
        outside.write_text("OUTSIDE_SENTINEL", encoding="utf-8")
        try:
            link.symlink_to(target)
            escape = self.allowed / "escape.md"
            escape.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unsupported")
        source = self.write("index.md", "[inside](inside.md) [outside](escape.md)\n")
        result = self.cli("--format", "json", str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(result.stdout)["records"]
        self.assertEqual({row["target"]: row["exact_path"] for row in rows},
                         {"inside.md": "exact_path", "escape.md": "out_of_scope"})
        self.assertNotIn("TARGET_CONTENT_SENTINEL", result.stdout)
        self.assertNotIn("OUTSIDE_SENTINEL", result.stdout)

    def test_root_input_and_posix_fifo_are_rejected_without_blocking(self):
        import os
        root_as_file = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.allowed), "--format", "json", str(self.allowed)], text=True, capture_output=True, timeout=3)
        self.assertEqual(root_as_file.returncode, 2)
        self.assertNotIn("Traceback", root_as_file.stderr)
        if os.name != "nt" and hasattr(os, "mkfifo"):
            fifo = self.allowed / "pipe.md"
            os.mkfifo(fifo)
            result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.allowed), "--format", "json", str(fifo)], text=True, capture_output=True, timeout=3)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("Traceback", result.stderr)

    def test_directory_targets_remain_unchecked(self):
        import reference_audit
        self.write("docs/index.md", "index\n")
        source = self.write("source.md", "[docs](docs/)\n")
        result = self.cli("--format", "json", str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        row = json.loads(result.stdout)["records"][0]
        self.assertEqual(row["exact_path"], "unchecked")

    def test_uri_schemes_are_external_and_not_path_candidates(self):
        import reference_audit
        samples = ["mailto:alice@example.com", "ftp://host/file.md", "HTTPS://host/file.md", "file:///private/team/hidden.md"]
        for sample in samples:
            records = list(reference_audit.extract(f"[link]({sample})"))
            self.assertEqual(len(records), 1)
            self.assertNotEqual(records[0][2], "path_candidate")
            self.assertEqual(reference_audit.classify_binding(records[0][1]), "external")
        source = self.write("uri.md", "[private](file:///private/team/hidden.md)\n")
        for view in ("json", "table", "mermaid", "all"):
            result = self.cli("--format", view, str(source))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("/private/team/hidden.md", result.stdout)

    def test_entity_match_does_not_imply_exact_path(self):
        target = self.write("skill.md", "content\n")
        source = self.write("index.md", "Use alias skill.md by name.\n")
        result = self.cli("--format", "json", str(source), str(target))
        self.assertEqual(result.returncode, 0, result.stderr)
        row = json.loads(result.stdout)["records"][0]
        self.assertEqual(row["entity_match"], "entity_match")
        self.assertEqual(row["exact_path"], "not_found_in_scope")

    def test_secret_source_locator_is_redacted_but_traceable(self):
        secret_name = "ghp_" + "Q" * 24 + ".md"
        source = self.write(secret_name, "See [x](https://example.test)\n")
        result = self.cli("--format", "json", str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertNotIn(secret_name, result.stdout)
        self.assertIn("[REDACTED].md", data["sources"].values())

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
        self.assertEqual(table.splitlines()[-1].count("|"), 11)
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
