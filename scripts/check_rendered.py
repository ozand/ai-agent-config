#!/usr/bin/env python3
"""Fail when client templates differ from canonical renderer output."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDERED_FILES = (
    ROOT / "clients/pi/models.template.json",
    ROOT / "clients/opencode/opencode.template.jsonc",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    before = {path: digest(path) for path in RENDERED_FILES}
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/render_clients.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print("Renderer execution failed", file=sys.stderr)
        return 1

    changed = [path.relative_to(ROOT) for path in RENDERED_FILES if before[path] != digest(path)]
    if changed:
        print("Rendered client templates are stale:", file=sys.stderr)
        for path in changed:
            print(f"- {path}", file=sys.stderr)
        print("Run: python scripts/render_clients.py", file=sys.stderr)
        return 1

    print("Rendered client templates are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
