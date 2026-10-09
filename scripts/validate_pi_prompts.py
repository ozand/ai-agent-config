#!/usr/bin/env python3
"""Validate shareable Pi slash-command templates for basic safety and structure."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "clients/pi/prompts"
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*[\"']?[A-Za-z0-9_./+~=-]{16,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{24,}", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
ABSOLUTE_PATH = re.compile(
    r"(?:[A-Z]:(?:\\|/)(?!/)[^\s`\"<>]+|/(?!/)[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+|\\\\[^\\\s]+\\[^\s`\"<>]+)",
    re.IGNORECASE,
)
PRIVATE_TOOL_REFERENCES = re.compile(r"\b(?:github-issue-steward|code-reviewer|context-mode)\b", re.IGNORECASE)
REQUIRED = {"README.md", "git-sync-status.md", "status-ru.md", "project-overview.md", "capture-learnings.md"}


def fail(message: str) -> None:
    raise AssertionError(message)


def validate() -> None:
    files = sorted(PROMPTS.glob("*.md"))
    if not REQUIRED.issubset({p.name for p in files}):
        fail("Shareable Pi prompt directory is missing required prompt files")
    for path in files:
        text = path.read_text(encoding="utf-8")
        if path.name != "README.md":
            if not text.startswith("---\n") or "\n---\n" not in text[4:]:
                fail(f"Prompt frontmatter is missing or malformed: {path.relative_to(ROOT)}")
            frontmatter = text[4:text.index("\n---\n", 4)]
            if not re.search(r"^description:\s*\S", frontmatter, re.MULTILINE):
                fail(f"Prompt frontmatter needs a description: {path.relative_to(ROOT)}")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                fail(f"Likely secret material found in: {path.relative_to(ROOT)}")
        if path.name != "README.md" and ABSOLUTE_PATH.search(text):
            fail(f"Machine-specific absolute path found in: {path.relative_to(ROOT)}")
        if PRIVATE_TOOL_REFERENCES.search(text):
            fail(f"Private agent/tool dependency found in shareable prompt: {path.relative_to(ROOT)}")
        if "~/.pi/agent/prompts" in text:
            fail(f"Personal prompt directory reference leaked into shareable prompt: {path.relative_to(ROOT)}")


def main() -> int:
    try:
        validate()
    except (AssertionError, OSError, UnicodeError) as exc:
        print(f"Pi prompt validation failed: {exc}", file=sys.stderr)
        return 1
    print("Pi prompt templates passed structure and secret-safety checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
