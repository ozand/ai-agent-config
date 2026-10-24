from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READER = ROOT / "clients/pi/scripts/read-litellm-api-key.sh"


class PiSecretReaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name) / "synthetic-home"
        self.secret_dir = self.home / ".pi" / "agent" / ".secrets"
        self.secret_dir.mkdir(parents=True)
        self.secret_file = self.secret_dir / "litellm-api-key"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_reader(self) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        return subprocess.run(
            ["sh", str(READER)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_success_writes_only_file_content_to_stdout(self) -> None:
        self.secret_file.write_text("synthetic-fixture-value", encoding="utf-8")
        result = self.run_reader()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "synthetic-fixture-value")
        self.assertEqual(result.stderr, "")

    def test_missing_file_fails_without_secret_output(self) -> None:
        result = self.run_reader()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("credential file is missing", result.stderr)
        self.assertNotIn("synthetic-fixture-value", result.stderr)

    def test_empty_file_fails_without_secret_output(self) -> None:
        self.secret_file.touch()
        result = self.run_reader()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("credential file is empty", result.stderr)
        self.assertNotIn("synthetic-fixture-value", result.stderr)

    def test_provisioning_permissions_are_user_only(self) -> None:
        if os.name != "posix":
            self.skipTest("POSIX permission bits are not available on this platform")
        self.secret_file.write_text("synthetic-fixture-value", encoding="utf-8")
        self.secret_dir.chmod(0o700)
        self.secret_file.chmod(0o600)
        self.assertEqual(self.secret_dir.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.secret_file.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
