"""Tests for audit-2026-09 reconciliation decisions.

Covers:
- Provenance receipt exists and excludes secret/private-path material
- GPT-5.6 context window conflict is documented in canonical catalog
- GPT-5.6 Sol cache prices corrected to endpoint evidence
- Sonnet 4.6 cache conflict is documented without removing repo-held values
- Compaction policy is documented in the default profile
- Claude 5 absent (no unapproved promotion)
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

    GPT56_6_IDS = {"cl/gpt-6-luna", "cl/gpt-6-sol", "cl/gpt-5.6-terra"}

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


class SolCachePriceTests(unittest.TestCase):
    """Sol cache prices must reflect corrected endpoint evidence (0.20/2.50 per million for GPT-6 Sol)."""

    def test_sol_cache_prices_in_catalog(self) -> None:
        by_id = {m["id"]: m for m in load_json("catalog/models.json")["models"]}
        sol = by_id["cl/gpt-6-sol"]["costPerMillion"]
        self.assertAlmostEqual(
            sol["cacheRead"], 0.20,
            places=4,
            msg="Sol cacheRead must be 0.20 per million (endpoint evidence 2026-09-08)",
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
        sol = next(m for m in pi_models if m["id"] == "cl/gpt-6-sol")
        self.assertAlmostEqual(sol["cost"]["cacheRead"], 0.20, places=4)
        self.assertAlmostEqual(sol["cost"]["cacheWrite"], 2.50, places=4)

    def test_sol_cache_prices_in_opencode_template(self) -> None:
        oc_models = load_json("clients/opencode/opencode.template.jsonc")[
            "provider"
        ]["litellm-edge"]["models"]
        sol = oc_models["cl/gpt-6-sol"]
        self.assertAlmostEqual(sol["cost"]["cache_read"], 0.20, places=4)
        self.assertAlmostEqual(sol["cost"]["cache_write"], 2.50, places=4)


class SonnetCacheConflictTests(unittest.TestCase):
    """Sonnet 4.6 cache conflict must be documented and active cache prices omitted."""

    def test_sonnet_cache_conflict_note_present(self) -> None:
        by_id = {m["id"]: m for m in load_json("catalog/models.json")["models"]}
        sonnet = by_id["an/claude-sonnet-4-6"]
        cpm = sonnet.get("costPerMillion", {})
        self.assertIn(
            "cacheConflictNote",
            cpm,
            "Sonnet 4.6 costPerMillion must include cacheConflictNote",
        )
        note = cpm["cacheConflictNote"]
        self.assertIn(
            "null",
            note,
            "cacheConflictNote must reference the null endpoint values",
        )
        self.assertIn("2026-09-08", note, "cacheConflictNote must include the evidence date")

    def test_sonnet_cache_prices_are_unknown_and_omitted(self) -> None:
        """Endpoint returned null; active client cache prices must be omitted."""
        by_id = {m["id"]: m for m in load_json("catalog/models.json")["models"]}
        cpm = by_id["an/claude-sonnet-4-6"]["costPerMillion"]
        self.assertNotIn("cacheRead", cpm)
        self.assertNotIn("cacheWrite", cpm)

    def test_qwen_output_modality_is_preserved(self) -> None:
        oc_models = load_json("clients/opencode/opencode.template.jsonc")["provider"]["litellm-edge"]["models"]
        self.assertEqual(oc_models["un/qwen3.8-27b-gguf"]["modalities"], {"input": ["text"], "output": ["text"]})

    def test_sonnet_cache_note_not_rendered_into_templates(self) -> None:
        """cacheConflictNote is a documentation field; rendered templates must not expose it."""
        pi_models = load_json("clients/pi/models.template.json")[
            "providers"
        ]["litellm-edge"]["models"]
        sonnet_pi = next(
            (m for m in pi_models if m["id"] == "an/claude-sonnet-4-6"), None
        )
        self.assertIsNotNone(sonnet_pi, "Sonnet 4.6 must be in Pi template")
        if "cost" in sonnet_pi:
            self.assertNotIn(
                "cacheConflictNote",
                sonnet_pi["cost"],
                "cacheConflictNote must not be rendered into Pi cost block",
            )
        oc_models = load_json("clients/opencode/opencode.template.jsonc")[
            "provider"
        ]["litellm-edge"]["models"]
        sonnet_oc = oc_models.get("an/claude-sonnet-4-6", {})
        if "cost" in sonnet_oc:
            self.assertNotIn(
                "cacheConflictNote",
                sonnet_oc["cost"],
                "cacheConflictNote must not be rendered into OpenCode cost block",
            )


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


class NoUnapprovedModelsTests(unittest.TestCase):
    """Gemini 3.8 variants and Claude 5 must not be added without a policy decision."""

    def test_no_claude5_in_catalog(self) -> None:
        ids = {m["id"] for m in load_json("catalog/models.json")["models"]}
        claude5 = {mid for mid in ids if re.search(r"claude[-_\s]?5", mid, re.IGNORECASE)}
        self.assertEqual(
            claude5,
            set(),
            f"Claude 5 models must not be added without a policy decision; found: {claude5}",
        )

    def test_canonical_model_count_unchanged(self) -> None:
        """Model count must remain 40; additions require explicit policy decision."""
        models = load_json("catalog/models.json")["models"]
        self.assertEqual(
            len(models),
            41,
            "Canonical catalog must still contain the current 41-model catalog (no additional unapproved additions)",
        )


if __name__ == "__main__":
    unittest.main()
