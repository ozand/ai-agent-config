"""Tests for audit-2026-09 reconciliation decisions.

Covers:
- Provenance receipt exists and excludes secret/private-path material
- GPT-5.6 context window conflict is documented in canonical catalog
- GPT-5.6 Sol cache prices corrected to endpoint evidence
- Sonnet 5.5 High pricing is current and rendered into both client catalogs
- Compaction policy is documented in the default profile
- Current Sonnet and GPT Sol generations are approved
- Canonical model count has not silently changed
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class ProvenanceReceiptTests(unittest.TestCase):
    """Evidence receipt file must exist, be sanitized, and omit secrets/private paths."""

    RECEIPT_PATH = ROOT / "docs/endpoint-evidence-receipt-2026-09-08.md"

    def test_receipt_file_exists(self) -> None:
        self.assertTrue(
            self.RECEIPT_PATH.exists(),
            f"Provenance receipt must exist at {self.RECEIPT_PATH}",
        )

    def test_receipt_contains_required_fields(self) -> None:
        text = self.RECEIPT_PATH.read_text(encoding="utf-8")
        self.assertIn("2026-09-08", text, "Receipt must include evidence date")
        self.assertIn("litellm.ayga.tech", text, "Receipt must document endpoint hostname")
        self.assertIn("116", text, "Receipt must document public model count")
        self.assertIn("118", text, "Receipt must document model_info record count")

    def test_receipt_has_no_secrets_or_private_paths(self) -> None:
        text = self.RECEIPT_PATH.read_text(encoding="utf-8")
        # No bearer tokens or API-key patterns
        self.assertIsNone(
            re.search(r"Bearer\s+\S+", text),
            "Receipt must not include raw Bearer tokens",
        )
        self.assertIsNone(
            re.search(r"sk-[A-Za-z0-9\-]{16,}", text),
            "Receipt must not include API key material",
        )
        # No private Windows-style backend paths (e.g. absolute path to local GGUF)
        self.assertIsNone(
            re.search(r"C:\\Users\\", text, re.IGNORECASE),
            "Receipt must not include private filesystem paths",
        )
        self.assertIsNone(
            re.search(r"openai/C:", text, re.IGNORECASE),
            "Receipt must not include backend model paths with local drive letters",
        )

    def test_receipt_does_not_expose_account_identifiers(self) -> None:
        text = self.RECEIPT_PATH.read_text(encoding="utf-8")
        # «backend_model» field values from the live response must not appear verbatim
        self.assertNotIn("openai/claude-sonnet-4-6", text)
        self.assertNotIn("openai/gpt-5.6-sol", text)
        self.assertNotIn("openai/C:", text)


class ContextWindowConflictTests(unittest.TestCase):
    """GPT-5.6 family must carry explicit context window conflict documentation."""

    GPT56_6_IDS = {"cl/gpt-6-luna", "cl/gpt-5.6-terra"}

    def _catalog_by_id(self) -> dict:
        return {
            m["id"]: m for m in load_json("catalog/models.json")["models"]
        }

    def test_gpt56_context_window_conflict_is_documented(self) -> None:
        by_id = self._catalog_by_id()
        for mid in self.GPT56_6_IDS:
            with self.subTest(model=mid):
                model = by_id[mid]
                self.assertIn(
                    "contextWindowConflict",
                    model,
                    f"{mid} must have a contextWindowConflict field documenting the endpoint discrepancy",
                )
                note = model["contextWindowConflict"]
                self.assertIn(
                    "922000",
                    note,
                    "contextWindowConflict must mention the endpoint-reported value 922000",
                )
                self.assertIn(
                    "1050000",
                    note,
                    "contextWindowConflict must mention the provider reference value 1050000",
                )
                self.assertEqual(model["contextWindow"], 922000)
                self.assertEqual(model["providerContextWindow"], 1050000)

    def test_gpt56_client_limit_is_proxy_safe_and_provider_limit_retained(self) -> None:
        """Clients use the authenticated proxy limit; provider context remains separate."""
        by_id = self._catalog_by_id()
        for mid in self.GPT56_6_IDS:
            with self.subTest(model=mid):
                self.assertEqual(by_id[mid]["contextWindow"], 922000)
                self.assertEqual(by_id[mid]["providerContextWindow"], 1050000)

    def test_gpt61_sol_uses_only_verified_proxy_context(self) -> None:
        by_id = self._catalog_by_id()
        self.assertEqual(by_id["cl/gpt-6.1-sol"]["contextWindow"], 922000)
        self.assertNotIn("providerContextWindow", by_id["cl/gpt-6.1-sol"])


class SolCachePriceTests(unittest.TestCase):
    """GPT-6.1 Sol cache prices must match official pricing (0.10/2.50 per million)."""

    def test_sol_cache_prices_in_catalog(self) -> None:
        by_id = {m["id"]: m for m in load_json("catalog/models.json")["models"]}
        sol = by_id["cl/gpt-6.1-sol"]["costPerMillion"]
        self.assertAlmostEqual(
            sol["cacheRead"], 0.10,
            places=4,
            msg="GPT-6.1 Sol cacheRead must be 0.10 per million (official pricing)",
        )
        self.assertAlmostEqual(
            sol["cacheWrite"], 2.50,
            places=4,
            msg="Sol cacheWrite must be 2.50 per million (endpoint evidence 2026-09-08)",
        )

    def test_sol_cache_prices_in_pi_template(self) -> None:
        pi_models = load_json("clients/pi/models.template.json")[
            "providers"
        ]["litellm-edge"]["models"]
        sol = next(m for m in pi_models if m["id"] == "cl/gpt-6.1-sol")
        self.assertAlmostEqual(sol["cost"]["cacheRead"], 0.10, places=4)
        self.assertAlmostEqual(sol["cost"]["cacheWrite"], 2.50, places=4)

    def test_sol_cache_prices_in_opencode_template(self) -> None:
        oc_models = load_json("clients/opencode/opencode.template.jsonc")[
            "provider"
        ]["litellm-edge"]["models"]
        sol = oc_models["cl/gpt-6.1-sol"]
        self.assertAlmostEqual(sol["cost"]["cache_read"], 0.10, places=4)
        self.assertAlmostEqual(sol["cost"]["cache_write"], 2.50, places=4)


class SonnetCacheConflictTests(unittest.TestCase):
    """Sonnet 5.5 High active pricing must match official LiteLLM metadata."""

    def test_sonnet_5_5_high_prices_match_official_metadata(self) -> None:
        by_id = {m["id"]: m for m in load_json("catalog/models.json")["models"]}
        cost = by_id["an/claude-sonnet-5-5-high"]["costPerMillion"]
        self.assertEqual(cost, {"input": 2.0, "output": 10.0, "cacheRead": 0.2, "cacheWrite": 2.5})
        sonnet = by_id["an/claude-sonnet-5-5-high"]
        self.assertEqual(sonnet["contextWindow"], 1000000)
        self.assertEqual(sonnet["maxTokens"], 128000)

    def test_qwen_output_modality_is_preserved(self) -> None:
        oc_models = load_json("clients/opencode/opencode.template.jsonc")["provider"]["litellm-edge"]["models"]
        self.assertEqual(oc_models["un/qwen3.8-27b-gguf"]["modalities"], {"input": ["text"], "output": ["text"]})

    def test_sonnet_5_5_high_prices_are_rendered(self) -> None:
        pi_models = load_json("clients/pi/models.template.json")["providers"]["litellm-edge"]["models"]
        sonnet_pi = next(m for m in pi_models if m["id"] == "an/claude-sonnet-5-5-high")
        self.assertEqual(sonnet_pi["cost"], {"input": 2.0, "output": 10.0, "cacheRead": 0.2, "cacheWrite": 2.5})
        oc_models = load_json("clients/opencode/opencode.template.jsonc")["provider"]["litellm-edge"]["models"]
        sonnet_oc = oc_models["an/claude-sonnet-5-5-high"]
        self.assertEqual(sonnet_oc["cost"], {"input": 2.0, "output": 10.0, "cache_read": 0.2, "cache_write": 2.5})


class CompactionPolicyTests(unittest.TestCase):
    """Pi compaction threshold and OpenCode DCP strategy must be explicitly documented."""

    def test_default_profile_documents_compaction_threshold(self) -> None:
        text = (ROOT / "profiles/default.yaml").read_text(encoding="utf-8")
        self.assertIn(
            "272000",
            text,
            "Default profile must document the Pi compaction threshold (272000)",
        )
        # Must explain it is intentional / conservative
        self.assertIn(
            "compaction",
            text.lower(),
            "Default profile must reference compaction policy",
        )
        self.assertIn("context window", text.lower())
        extension = (ROOT / "clients/pi/extensions/auto-compact-272k.ts").read_text(encoding="utf-8")
        self.assertIn("contextWindow <= COMPACT_THRESHOLD_TOKENS", extension)
        self.assertIn("pi_reserve_tokens: 16384", text)
        self.assertIn("pi_keep_recent_tokens: 20000", text)

    def test_default_profile_documents_client_strategy_difference(self) -> None:
        """Pi threshold vs OpenCode DCP must be documented as intentionally different."""
        text = (ROOT / "profiles/default.yaml").read_text(encoding="utf-8")
        self.assertIn(
            "OpenCode",
            text,
            "Default profile must mention OpenCode to distinguish client strategies",
        )


class CurrentGenerationApprovalTests(unittest.TestCase):
    """Approved current generations must replace obsolete interactive defaults."""

    def test_current_sonnet_and_gpt_sol_ids_are_canonical(self) -> None:
        ids = {m["id"] for m in load_json("catalog/models.json")["models"]}
        self.assertIn("an/claude-sonnet-5-5-high", ids)
        self.assertIn("cl/gpt-6.1-sol", ids)
        self.assertNotIn("an/claude-sonnet-4-6", ids)
        self.assertNotIn("cl/gpt-6-sol", ids)

    def test_canonical_model_count_unchanged(self) -> None:
        """Model count remains stable because two superseded IDs were replaced."""
        models = load_json("catalog/models.json")["models"]
        self.assertEqual(
            len(models),
            41,
            "Canonical catalog must contain 41 approved current model IDs",
        )


if __name__ == "__main__":
    unittest.main()
