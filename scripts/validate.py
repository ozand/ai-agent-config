#!/usr/bin/env python3
"""Validate catalog parity, policy safety, JSON syntax, and secret hygiene."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

JSON_FILES = [
    ROOT / "catalog/models.json",
    ROOT / "clients/pi/models.template.json",
    ROOT / "clients/pi/settings.template.json",
    ROOT / "clients/opencode/opencode.template.jsonc",
]

TEXT_SUFFIXES = {".json", ".jsonc", ".yaml", ".yml", ".md", ".ps1", ".py", ".ts"}
EXCLUDED_PARTS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache"}

STALE_ACTIVE = (
    "gpt-5.3",
    "gpt-5.4",
    "gpt-5.5",
    "gemini-3.5",
    "gemini-3.6",
    "qwen3.6",
    "sol1",
)

SECRET_PATTERNS = {
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "Google API key": re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b"),
    "bearer token": re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{24,}", re.IGNORECASE),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}

ALLOWED_SECRET_REFERENCES = (
    "{env:LITELLM_EDGE_API_KEY}",
    "$USERPROFILE/.pi/agent/scripts/read-litellm-api-key.ps1",
    "$LITELLM_API_KEY",
    "<SET_LOCALLY>",
)


def fail(message: str) -> None:
    raise AssertionError(message)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"Invalid JSON: {path.relative_to(ROOT)} ({error.__class__.__name__})")


def iter_text_files() -> list[Path]:
    paths = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        paths.append(path)
    return paths


def model_ids() -> tuple[set[str], set[str], set[str]]:
    canonical = load_json(ROOT / "catalog/models.json")
    pi = load_json(ROOT / "clients/pi/models.template.json")
    opencode = load_json(ROOT / "clients/opencode/opencode.template.jsonc")

    canonical_ids = {model["id"] for model in canonical["models"]}
    pi_ids = {
        model["id"]
        for model in pi["providers"]["litellm-edge"]["models"]
    }
    opencode_ids = set(opencode["provider"]["litellm-edge"]["models"])
    return canonical_ids, pi_ids, opencode_ids


def validate_catalog_parity() -> None:
    canonical_ids, pi_ids, opencode_ids = model_ids()
    if len(canonical_ids) != 40:
        fail(f"Canonical catalog must contain 40 unique IDs, found {len(canonical_ids)}")
    if canonical_ids != pi_ids or canonical_ids != opencode_ids:
        fail("Canonical, Pi, and OpenCode model ID sets differ")


def validate_defaults() -> None:
    pi = load_json(ROOT / "clients/pi/settings.template.json")
    opencode = load_json(ROOT / "clients/opencode/opencode.template.jsonc")

    if pi["defaultProvider"] != "litellm-edge":
        fail("Pi default provider must be litellm-edge")
    if pi["defaultModel"] != "cl/gpt-5.6-luna":
        fail("Pi default model must be cl/gpt-5.6-luna")
    if opencode["model"] != "litellm-edge/cl/gpt-5.6-luna":
        fail("OpenCode default model must be provider-qualified Luna")
    if opencode["small_model"] != "litellm-edge/an/gemini-3.7-flash-low":
        fail("OpenCode small model must be Gemini 3.7 Flash Low")


def validate_routes() -> None:
    opencode = load_json(ROOT / "clients/opencode/opencode.template.jsonc")
    references = [opencode["model"], opencode["small_model"]]
    references.extend(
        config["model"]
        for config in opencode.get("agent", {}).values()
        if "model" in config
    )

    for path in (ROOT / "clients/opencode/agents").glob("*.md"):
        match = re.search(
            r"^model:\s*(\S+)\s*$",
            path.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        )
        if match:
            references.append(match.group(1))

    for reference in references:
        if not reference.startswith("litellm-edge/"):
            fail("Every reusable OpenCode model reference must use litellm-edge/")
        if any(stale in reference for stale in STALE_ACTIVE):
            fail("A stale generation is used by an active client reference")


def validate_qwen() -> None:
    canonical = load_json(ROOT / "catalog/models.json")
    pi = load_json(ROOT / "clients/pi/models.template.json")
    opencode = load_json(ROOT / "clients/opencode/opencode.template.jsonc")

    canonical_qwen = next(
        model for model in canonical["models"] if model["id"] == "un/qwen3.8-27b-gguf"
    )
    pi_qwen = next(
        model
        for model in pi["providers"]["litellm-edge"]["models"]
        if model["id"] == "un/qwen3.8-27b-gguf"
    )
    oc_qwen = opencode["provider"]["litellm-edge"]["models"]["un/qwen3.8-27b-gguf"]

    if canonical_qwen["runtimeContextWindow"] != 98304:
        fail("Canonical Qwen runtime context must be 98304")
    if pi_qwen["contextWindow"] != 73728 or pi_qwen["input"] != ["text"]:
        fail("Pi Qwen must be text-only with a 73728 context window")
    if "limit" in oc_qwen:
        fail("OpenCode Qwen limit must remain absent until output limit is known")
    if oc_qwen.get("modalities", {}).get("input") != ["text"]:
        fail("OpenCode Qwen must be text-only")


def validate_policy_documents() -> None:
    required_markers = {
        "catalog/model-policy.yaml": (
            "interactive: litellm-edge/cl/gpt-5.6-luna",
            "small_fast: litellm-edge/an/gemini-3.7-flash-low",
            "runtime_context_window: 98304",
            "pi_context_window: 73728",
        ),
        "catalog/agent-routing.yaml": (
            "primary: litellm-edge/an/claude-opus-4-6",
            "orchestrator: litellm-edge/cl/gpt-5.6-luna",
        ),
        "profiles/default.yaml": (
            "interactive_model: litellm-edge/cl/gpt-5.6-luna",
            "small_model: litellm-edge/an/gemini-3.7-flash-low",
        ),
        "profiles/local-first.yaml": (
            "interactive_model: litellm-edge/un/qwen3.8-27b-gguf",
            "pi_context_window: 73728",
            "runtime_context_window: 98304",
        ),
    }
    for relative, markers in required_markers.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        if not text.strip() or not re.search(r"^schema_version:\s*1\s*$", text, re.MULTILINE):
            fail(f"Policy/profile header is invalid: {relative}")
        for marker in markers:
            if marker not in text:
                fail(f"Required policy/profile marker missing in {relative}")


def validate_secret_references() -> None:
    pi = load_json(ROOT / "clients/pi/models.template.json")
    opencode = load_json(ROOT / "clients/opencode/opencode.template.jsonc")
    pi_key = pi["providers"]["litellm-edge"]["apiKey"]
    oc_key = opencode["provider"]["litellm-edge"]["options"]["apiKey"]

    if not pi_key.startswith("!powershell.exe "):
        fail("Pi must use the documented file-backed command resolver")
    if oc_key != "{env:LITELLM_EDGE_API_KEY}":
        fail("OpenCode must use the environment reference")


def validate_secret_hygiene() -> None:
    findings: list[str] = []
    for path in iter_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT)} ({name})")

    if findings:
        fail("Likely secret material found in: " + ", ".join(findings))

    combined = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in iter_text_files()
    )
    for reference in ALLOWED_SECRET_REFERENCES:
        if reference not in combined:
            fail(f"Required sanitized secret reference is missing: {reference}")


def main() -> int:
    for path in JSON_FILES:
        load_json(path)
    validate_catalog_parity()
    validate_defaults()
    validate_routes()
    validate_qwen()
    validate_policy_documents()
    validate_secret_references()
    validate_secret_hygiene()
    print("Validation passed: JSON, catalog parity, routing, Qwen policy, and secret hygiene")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as error:
        print(f"Validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
