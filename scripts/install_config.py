#!/usr/bin/env python3
"""Safely preview or apply the repository's Pi and OpenCode configuration templates.

The command is deliberately dry-run by default.  It never reads credential files;
secret references in the tracked templates are copied as opaque client-native
references.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import sys
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]

# These are the only settings this tool is allowed to change.  In particular,
# local themes, retry/transport tuning, compaction, sessions and other runtime
# preferences remain owned by the user.
PI_SETTINGS_OWNED = (
    "defaultProvider",
    "defaultModel",
    "defaultThinkingLevel",
    "enabledModels",
    "packages",
    "extensions",
    "subagents",
)
OPENCODE_ROOT_OWNED = {"model", "small_model", "default_agent"}
SENSITIVE_KEY = re.compile(
    r"(?:api[_-]?key|token|secret|password|credential|authorization|cookie)",
    re.IGNORECASE,
)
SECRET_VALUE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{12,}|AIza[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9._~+/=-]{16,})",
    re.IGNORECASE,
)


class InstallerError(Exception):
    """A user-facing, secret-safe installer error."""


@dataclass(frozen=True)
class Plan:
    relative: str
    target: Path
    content: str
    existed: bool
    kind: str


def _jsonc_text(text: str) -> str:
    """Remove JSONC comments and trailing commas without touching strings."""
    out: list[str] = []
    i = 0
    in_string = False
    escaped = False
    while i < len(text):
        char = text[i]
        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            i += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            i += 1
        elif text.startswith("//", i):
            newline = text.find("\n", i)
            if newline < 0:
                break
            out.append("\n")
            i = newline + 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                raise InstallerError("invalid JSONC comment in configuration")
            out.extend("\n" if c == "\n" else " " for c in text[i : end + 2])
            i = end + 2
        else:
            out.append(char)
            i += 1
    without_comments = "".join(out)
    # A comma followed only by whitespace and a closing container is JSONC's
    # trailing-comma form.  The look-ahead does not enter string content.
    return re.sub(r",(\s*[}\]])", r"\1", without_comments)


def load_config(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InstallerError(f"cannot read configuration: {path}") from exc
    try:
        value = json.loads(_jsonc_text(raw))
    except json.JSONDecodeError as exc:
        raise InstallerError(f"invalid JSON/JSONC configuration: {path} (line {exc.lineno})") from None
    if not isinstance(value, dict):
        raise InstallerError(f"configuration root must be an object: {path}")
    return value


def render_config(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def _skip_jsonc(text: str, pos: int) -> int:
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
        elif text.startswith("//", pos):
            end = text.find("\n", pos + 2)
            pos = len(text) if end < 0 else end + 1
        elif text.startswith("/*", pos):
            end = text.find("*/", pos + 2)
            if end < 0:
                raise InstallerError("invalid JSONC comment in configuration")
            pos = end + 2
        else:
            return pos
    return pos


def _json_string_end(text: str, pos: int) -> int:
    pos += 1
    escaped = False
    while pos < len(text):
        if escaped:
            escaped = False
        elif text[pos] == "\\":
            escaped = True
        elif text[pos] == '"':
            return pos + 1
        pos += 1
    raise InstallerError("unterminated JSON string in configuration")


def _json_value_end(text: str, pos: int) -> int:
    pos = _skip_jsonc(text, pos)
    if pos >= len(text):
        raise InstallerError("missing JSON value in configuration")
    if text[pos] == '"':
        return _json_string_end(text, pos)
    if text[pos] not in "[{":
        end = pos
        while end < len(text) and text[end] not in ",}]":
            end += 1
        return end
    opening = text[pos]
    closing = "]" if opening == "[" else "}"
    depth = 0
    in_string = False
    escaped = False
    index = pos
    while index < len(text):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif text.startswith("//", index):
            end = text.find("\n", index + 2)
            index = len(text) if end < 0 else end
        elif text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end < 0:
                raise InstallerError("invalid JSONC comment in configuration")
            index = end + 1
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    raise InstallerError("unterminated JSON container in configuration")


def _json_object_members(text: str, start: int) -> tuple[dict[str, tuple[int, int]], int]:
    start = _skip_jsonc(text, start)
    if start >= len(text) or text[start] != "{":
        raise InstallerError("expected JSON object in configuration")
    members: dict[str, tuple[int, int]] = {}
    pos = start + 1
    while True:
        pos = _skip_jsonc(text, pos)
        if pos >= len(text):
            raise InstallerError("unterminated JSON object in configuration")
        if text[pos] == "}":
            return members, pos
        if text[pos] != '"':
            raise InstallerError("expected JSON object key in configuration")
        key_end = _json_string_end(text, pos)
        key = json.loads(text[pos:key_end])
        pos = _skip_jsonc(text, key_end)
        if pos >= len(text) or text[pos] != ":":
            raise InstallerError("expected colon after JSON object key")
        value_start = _skip_jsonc(text, pos + 1)
        value_end = _json_value_end(text, value_start)
        members[key] = (value_start, value_end)
        pos = _skip_jsonc(text, value_end)
        if pos < len(text) and text[pos] == ",":
            pos += 1
        elif pos < len(text) and text[pos] != "}":
            raise InstallerError("expected comma between JSON members")


def _json_path_span(text: str, path: tuple[str, ...]) -> tuple[int, int] | None:
    start = _skip_jsonc(text, 0)
    for key in path:
        members, _ = _json_object_members(text, start)
        span = members.get(key)
        if span is None:
            return None
        start = span[0]
    return start, _json_value_end(text, start)


def patch_json_sections(raw: str, value: dict[str, Any], paths: Iterable[tuple[str, ...]]) -> str:
    replacements: list[tuple[int, int, str]] = []
    for path in paths:
        span = _json_path_span(raw, path)
        if span is None:
            return render_config(value)
        selected: Any = value
        for key in path:
            selected = selected[key]
        replacements.append((span[0], span[1], json.dumps(selected, indent=2, ensure_ascii=False)))
    for start, end, replacement in sorted(replacements, reverse=True):
        raw = raw[:start] + replacement + raw[end:]
    return raw


def _merge_keys(existing: dict[str, Any], template: dict[str, Any], keys: Iterable[str]) -> dict[str, Any]:
    result = deepcopy(existing)
    for key in keys:
        if key in template:
            result[key] = deepcopy(template[key])
    return result


def _merge_object(existing: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    """Update template keys while retaining unknown local keys recursively."""
    result = deepcopy(existing)
    for key, value in template.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_object(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _merge_named_list(existing: Any, template: Any, key: str = "id") -> Any:
    """Merge named dictionaries, retaining user additions and template order."""
    if not isinstance(existing, list) or not isinstance(template, list):
        return deepcopy(template)
    template_names = {item.get(key) for item in template if isinstance(item, dict)}
    retained = [deepcopy(item) for item in existing if not (isinstance(item, dict) and item.get(key) in template_names)]
    return retained + [deepcopy(item) for item in template]


def _merge_string_list(existing: Any, template: Any) -> Any:
    if not isinstance(existing, list) or not isinstance(template, list):
        return deepcopy(template)
    result = list(existing)
    for item in template:
        if item not in result:
            result.append(deepcopy(item))
    return result


def merge_pi_models(existing: dict[str, Any] | None, template: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(existing or {})
    providers = result.setdefault("providers", {})
    if not isinstance(providers, dict):
        raise InstallerError("Pi models.json providers must be an object")
    managed = template.get("providers", {}).get("litellm-edge")
    if not isinstance(managed, dict):
        raise InstallerError("Pi template is missing the litellm-edge provider")
    current = providers.get("litellm-edge", {})
    if current is not None and not isinstance(current, dict):
        raise InstallerError("Pi litellm-edge provider must be an object")
    # Update the managed provider while retaining unknown provider keys and any
    # locally-added models. Other providers are never inspected or changed.
    merged = _merge_object(current or {}, managed)
    merged["models"] = _merge_named_list((current or {}).get("models"), managed.get("models"))
    providers["litellm-edge"] = merged
    return result


def merge_pi_settings(existing: dict[str, Any] | None, template: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(existing or {})
    for key in PI_SETTINGS_OWNED:
        if key not in template:
            continue
        if key in {"packages", "extensions"}:
            result[key] = _merge_string_list(result.get(key), template[key])
        elif key == "subagents" and isinstance(result.get(key), dict) and isinstance(template[key], dict):
            result[key] = _merge_object(result[key], template[key])
        else:
            result[key] = deepcopy(template[key])
    return result


def merge_opencode(existing: dict[str, Any] | None, template: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(existing or {})
    result = _merge_keys(result, template, OPENCODE_ROOT_OWNED)

    providers = result.setdefault("provider", {})
    if not isinstance(providers, dict):
        raise InstallerError("OpenCode provider must be an object")
    managed = template.get("provider", {}).get("litellm-edge")
    if not isinstance(managed, dict):
        raise InstallerError("OpenCode template is missing the litellm-edge provider")
    current = providers.get("litellm-edge", {})
    if current is not None and not isinstance(current, dict):
        raise InstallerError("OpenCode litellm-edge provider must be an object")
    merged_provider = _merge_object(current or {}, managed)
    current_models = (current or {}).get("models")
    template_models = managed.get("models")
    if isinstance(current_models, dict) and isinstance(template_models, dict):
        merged_provider["models"] = {**deepcopy(current_models), **deepcopy(template_models)}
    providers["litellm-edge"] = merged_provider

    agents = result.setdefault("agent", {})
    template_agents = template.get("agent", {})
    if not isinstance(agents, dict) or not isinstance(template_agents, dict):
        raise InstallerError("OpenCode agent sections must be objects")
    # Existing unrelated agents are retained.  For a named managed agent, the
    # template controls its documented keys while unknown local keys survive.
    for name, config in template_agents.items():
        if not isinstance(config, dict):
            raise InstallerError(f"OpenCode template agent is not an object: {name}")
        current_agent = agents.get(name, {})
        if current_agent is not None and not isinstance(current_agent, dict):
            raise InstallerError(f"OpenCode agent is not an object: {name}")
        agents[name] = _merge_object(current_agent or {}, config)
    return result


def _safe_text(text: str) -> str:
    """Redact secret-bearing JSON values while keeping the diff parseable."""
    try:
        parsed = json.loads(_jsonc_text(text))
    except (InstallerError, json.JSONDecodeError):
        return SECRET_VALUE.sub("<REDACTED>", text)
    return render_config(_redact(parsed))


def _redact(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        return {k: ("<REDACTED>" if SENSITIVE_KEY.search(k) else _redact(v, k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v, key) for v in value]
    if isinstance(value, str) and (SENSITIVE_KEY.search(key) or SECRET_VALUE.search(value)):
        return "<REDACTED>"
    return value


def sanitized_diff(old: str, new: str, label: str) -> str:
    old_safe = _safe_text(old)
    new_safe = _safe_text(new)
    lines = difflib.unified_diff(
        old_safe.splitlines(keepends=True),
        new_safe.splitlines(keepends=True),
        fromfile=f"{label} (current)",
        tofile=f"{label} (planned)",
        lineterm="\n",
    )
    return "".join(lines)


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _assert_outside_repo(path: Path) -> None:
    try:
        path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return
    raise InstallerError("target paths must be outside the repository")


def default_pi_dir() -> Path:
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME")
    if not home:
        raise InstallerError("USERPROFILE or HOME is required to resolve the Pi directory")
    return Path(home) / ".pi" / "agent"


def default_opencode_dir() -> Path:
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME")
    if not home:
        raise InstallerError("USERPROFILE or HOME is required to resolve the OpenCode directory")
    return Path(home) / ".config" / "opencode"


def _validate_secret_values(value: Any, key: str = "") -> None:
    """Refuse likely literal credentials before they can enter a plan or backup."""
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            _validate_secret_values(child_value, child_key)
        return
    if isinstance(value, list):
        for child_value in value:
            _validate_secret_values(child_value, key)
        return
    if not isinstance(value, str):
        return
    if SECRET_VALUE.search(value):
        raise InstallerError("refusing configuration with a recognizable credential value")
    if not SENSITIVE_KEY.search(key):
        return
    if value.startswith("!") or value.startswith("{env:") or value in {"<SET_LOCALLY>", "<REDACTED>"}:
        return
    raise InstallerError(f"refusing configuration with a literal secret-bearing value: {key}")


def _read_or_empty(path: Path) -> tuple[dict[str, Any], str, bool]:
    if not path.exists():
        return {}, "", False
    raw = path.read_text(encoding="utf-8")
    value = load_config(path)
    _validate_secret_values(value)
    return value, raw, True


def _opencode_preserve_content(raw: str, merged: dict[str, Any], template: dict[str, Any]) -> str:
    paths: list[tuple[str, ...]] = [
        ("model",),
        ("small_model",),
        ("default_agent",),
        ("provider", "litellm-edge"),
    ]
    paths.extend(("agent", name) for name in template.get("agent", {}))
    return patch_json_sections(raw, merged, paths)


def build_plans(
    client: str,
    *,
    pi_dir: Path | None = None,
    opencode_dir: Path | None = None,
    include_dcp: bool = False,
    agent_names: Iterable[str] | None = None,
    source_root: Path = ROOT,
) -> list[Plan]:
    plans: list[Plan] = []
    if client in ("pi", "all"):
        target_dir = (pi_dir or default_pi_dir()).expanduser()
        _assert_outside_repo(target_dir)
        models_path = target_dir / "models.json"
        settings_path = target_dir / "settings.json"
        models, _, existed = _read_or_empty(models_path)
        settings, _, settings_existed = _read_or_empty(settings_path)
        model_template = load_config(source_root / "clients/pi/models.template.json")
        settings_template = load_config(source_root / "clients/pi/settings.template.json")
        plans += [
            Plan("pi/models.json", models_path, render_config(merge_pi_models(models, model_template)), existed, "json"),
            Plan("pi/settings.json", settings_path, render_config(merge_pi_settings(settings, settings_template)), settings_existed, "json"),
        ]
        for source_rel, target_rel in (
            ("clients/pi/scripts/read-litellm-api-key.ps1", "scripts/read-litellm-api-key.ps1"),
            ("clients/pi/extensions/auto-compact-272k.ts", "extensions/auto-compact-272k.ts"),
        ):
            source = source_root / source_rel
            target = target_dir / target_rel
            _assert_outside_repo(target)
            plans.append(Plan(f"pi/{target_rel}", target, source.read_text(encoding="utf-8"), target.exists(), "text"))

    if client in ("opencode", "all"):
        target_dir = (opencode_dir or default_opencode_dir()).expanduser()
        _assert_outside_repo(target_dir)
        config_path = target_dir / "opencode.json"
        existing, raw, existed = _read_or_empty(config_path)
        template = load_config(source_root / "clients/opencode/opencode.template.jsonc")
        merged = merge_opencode(existing, template)
        content = _opencode_preserve_content(raw, merged, template) if existed else render_config(merged)
        plans.append(Plan("opencode/opencode.json", config_path, content, existed, "jsonc"))
        if include_dcp:
            dcp_path = target_dir / "dcp.jsonc"
            source = source_root / "clients/opencode/dcp.template.jsonc"
            plans.append(Plan("opencode/dcp.jsonc", dcp_path, source.read_text(encoding="utf-8"), dcp_path.exists(), "text"))
        selected = set(agent_names) if agent_names else None
        source_agents = source_root / "clients/opencode/agents"
        for source in sorted(source_agents.glob("*.md")):
            if selected is not None and source.name not in selected and source.stem not in selected:
                continue
            target = target_dir / "agents" / source.name
            _assert_outside_repo(target)
            plans.append(Plan(f"opencode/agents/{source.name}", target, source.read_text(encoding="utf-8"), target.exists(), "text"))
    return plans


def backup_existing(plans: list[Plan], backup_root: Path, repo_root: Path = ROOT) -> Path:
    backup_root = backup_root.expanduser().resolve()
    try:
        backup_root.relative_to(repo_root.resolve())
    except ValueError:
        pass
    else:
        raise InstallerError("backup directory must be outside the repository")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = backup_root / f"ai-agent-config-{stamp}"
    suffix = 0
    while destination.exists():
        suffix += 1
        destination = backup_root / f"ai-agent-config-{stamp}-{suffix}"
    destination.mkdir(parents=True)
    manifest: list[str] = []
    for plan in plans:
        if not plan.existed:
            continue
        relative = Path(plan.relative)
        out = destination / relative
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(plan.target, out)
        if not out.is_file() or out.read_bytes() != plan.target.read_bytes():
            raise InstallerError("backup verification failed")
        manifest.append(plan.relative)
    (destination / "MANIFEST.txt").write_text("\n".join(manifest) + ("\n" if manifest else ""), encoding="utf-8")
    if not (destination / "MANIFEST.txt").is_file():
        raise InstallerError("backup manifest verification failed")
    return destination


def apply_plans(plans: list[Plan], backup_dir: Path) -> Path | None:
    backup = backup_existing(plans, backup_dir)
    try:
        for plan in plans:
            plan.target.parent.mkdir(parents=True, exist_ok=True)
            plan.target.write_text(plan.content, encoding="utf-8", newline="\n")
            if plan.target.read_text(encoding="utf-8") != plan.content:
                raise InstallerError(f"post-write verification failed: {plan.relative}")
    except (OSError, UnicodeError) as exc:
        raise InstallerError("apply failed after backup creation; restore the verified backup") from exc
    return backup


def print_plan(plans: list[Plan]) -> None:
    print("DRY RUN (no files changed)" if plans else "No changes planned")
    for plan in plans:
        old = plan.target.read_text(encoding="utf-8") if plan.existed else ""
        diff = sanitized_diff(old, plan.content, plan.relative)
        print(f"\nPLAN {plan.relative}: {'update' if plan.existed else 'create'}")
        if diff:
            print(diff, end="" if diff.endswith("\n") else "\n")
        else:
            print("  (content already matches owned sections)")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--client", choices=("pi", "opencode", "all"), default="all")
    p.add_argument("--pi-dir", type=Path)
    p.add_argument("--opencode-dir", type=Path)
    p.add_argument("--backup-dir", type=Path, default=Path(tempfile.gettempdir()) / "ai-agent-config-backups")
    p.add_argument("--include-dcp", action="store_true", help="also manage dcp.jsonc")
    p.add_argument("--agent", action="append", dest="agents", help="limit OpenCode agents by filename or stem")
    p.add_argument("--apply", action="store_true", help="write changes (dry-run is the default)")
    p.add_argument("--confirm-apply", action="store_true", help="required explicit confirmation for --apply")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.confirm_apply and not args.apply:
        print("error: --confirm-apply requires --apply", file=sys.stderr)
        return 2
    if args.apply and not args.confirm_apply:
        print("error: --apply requires --confirm-apply; run a dry-run first", file=sys.stderr)
        return 2
    try:
        plans = build_plans(
            args.client,
            pi_dir=args.pi_dir,
            opencode_dir=args.opencode_dir,
            include_dcp=args.include_dcp,
            agent_names=args.agents,
        )
        if not args.apply:
            print_plan(plans)
        else:
            backup = apply_plans(plans, args.backup_dir)
            print(f"Applied {len(plans)} managed file(s). Backup verified outside repository: {backup}")
        return 0
    except InstallerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (OSError, UnicodeError):
        print("error: filesystem operation failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
