#!/usr/bin/env python3
"""Render canonical catalog metadata into client model templates.

The renderer updates model catalog sections only. It never reads or writes secret
values and never writes to a live user configuration directory.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "catalog/models.json"
PI_PATH = ROOT / "clients/pi/models.template.json"
OPENCODE_PATH = ROOT / "clients/opencode/opencode.template.jsonc"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def pi_model(model: dict) -> dict:
    result = {"id": model["id"], "name": model["name"]}
    for source, target in (
        ("reasoning", "reasoning"),
        ("input", "input"),
        ("contextWindow", "contextWindow"),
        ("maxTokens", "maxTokens"),
    ):
        if source in model:
            result[target] = model[source]

    if "costPerMillion" in model:
        cost = model["costPerMillion"]
        result["cost"] = {
            "input": cost["input"],
            "output": cost["output"],
            "cacheRead": cost.get("cacheRead", 0.0),
            "cacheWrite": cost.get("cacheWrite", 0.0),
        }

    if model["id"] == "un/qwen3.8-27b-gguf":
        result.update(
            {
                "reasoning": True,
                "thinkingLevelMap": {
                    "minimal": None,
                    "low": "low",
                    "medium": "medium",
                    "high": "xhigh",
                    "xhigh": None,
                    "max": None,
                },
                "input": ["text"],
                "contextWindow": model["piContextWindow"],
                "compat": {
                    "thinkingFormat": "qwen",
                    "supportsReasoningEffort": True,
                },
            }
        )
    return result


def opencode_model(model: dict) -> dict:
    result = {"name": model["name"]}
    if "reasoning" in model:
        result["reasoning"] = model["reasoning"]
    if "contextWindow" in model and "maxTokens" in model:
        result["limit"] = {
            "context": model["contextWindow"],
            "output": model["maxTokens"],
        }
    if "input" in model or "output" in model:
        result["modalities"] = {}
        if "input" in model:
            result["modalities"]["input"] = model["input"]
        if "output" in model:
            result["modalities"]["output"] = model["output"]
    if "costPerMillion" in model and model["id"] != "un/qwen3.8-27b-gguf":
        cost = model["costPerMillion"]
        result["cost"] = {"input": cost["input"], "output": cost["output"]}
        if "cacheRead" in cost:
            result["cost"]["cache_read"] = cost["cacheRead"]
        if "cacheWrite" in cost:
            result["cost"]["cache_write"] = cost["cacheWrite"]
    if "reasoningVariants" in model:
        result["variants"] = {
            variant: {"reasoningEffort": variant}
            for variant in model["reasoningVariants"]
        }
    if model["id"] == "un/qwen3.8-27b-gguf":
        result = {
            "name": model["name"],
            "reasoning": True,
            "modalities": {"input": ["text"]},
        }
    return result


def main() -> None:
    catalog = read_json(CATALOG_PATH)["models"]
    pi = read_json(PI_PATH)
    opencode = read_json(OPENCODE_PATH)

    pi["providers"]["litellm-edge"]["models"] = [pi_model(model) for model in catalog]
    opencode["provider"]["litellm-edge"]["models"] = {
        model["id"]: opencode_model(model) for model in catalog
    }

    write_json(PI_PATH, pi)
    write_json(OPENCODE_PATH, opencode)
    print(f"Rendered {len(catalog)} models into Pi and OpenCode templates")


if __name__ == "__main__":
    main()
