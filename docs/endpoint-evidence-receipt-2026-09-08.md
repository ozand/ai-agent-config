# Endpoint Evidence Receipt — 2026-09-08 UTC

## Source and scope

- **Collection date**: 2026-09-08 UTC
- **Endpoint class**: authenticated public LiteLLM edge proxy (OpenAI-compatible)
- **Base URL**: `https://litellm.ayga.tech/v1` (documented in `endpoints/litellm-edge.md`)
- **Collection method**: authenticated HTTP; no credentials or private backend paths recorded here

This document records sanitized field-level findings from a fresh audit.
It does not contain credentials, raw API payloads, private backend model names, private filesystem paths, or account identifiers.

## Endpoint status

| Route | Status | Count |
|---|---|---|
| `GET /models` | HTTP 200 | 116 public IDs |
| `GET /model/info` | HTTP 200 | 118 records / 116 normalized unique IDs |

Two records in `/model/info` failed to normalize to unique IDs
(duplicate metadata entries for the same route). All 116 public IDs are present in both responses.

## Canonical ID parity

Repository canonical catalog at time of audit: **41 models** (approved subset of available routes).

Policy retains the current repository-approved Gemini 3.8 tiers and GPT-6 Astra already present before this reconciliation. No additional endpoint routes are promoted by this issue. Claude 5 IDs observed in the endpoint are not added without a policy decision.
See `catalog/model-policy.yaml` for the approved family list.

## Field-level findings

### GPT-5.6 family (cl/gpt-5.6-luna, cl/gpt-5.6-sol, cl/gpt-5.6-terra)

| Field | Endpoint reports | Repository has | Status |
|---|---|---|---|
| `max_input_tokens` | 922,000 | `contextWindow: 922,000`; `providerContextWindow: 1,050,000` | **Client-safe limit adopted; provider limit retained separately** |
| `max_output_tokens` | 128,000 | `maxTokens: 128,000` | Confirmed |

**Context window conflict (GPT-5.6 family):**
The endpoint reports `max_input_tokens = 922,000` for all three GPT-5.6 routes.
The provider-documented value is 1,050,000. The repository records
`contextWindow = 922,000` for client safety and retains `providerContextWindow = 1,050,000`
for the upstream reference:

- Clients must not advertise or plan above 922,000 tokens at this proxy.
- The provider reference remains available for future deployment-specific reconciliation.
- A future evidence collection that confirms a higher operative proxy limit may revise the client field.

### GPT-5.6 Sol cache price conflict

| Field | Endpoint reports | Repository had | Resolution |
|---|---|---|---|
| `cache_read_input_token_cost` | 0.40 | 0.50 | **Updated in catalog** |
| `cache_creation_input_token_cost` | 5.00 | 6.25 | **Updated in catalog** |

The LiteLLM proxy reports endpoint billing prices for Sol cache operations.
Repository policy (`metadata_policy.source_order`) places `authenticated_endpoint`
first. Sol is a hosted provider route; endpoint billing applies.
The catalog has been corrected to 0.40 and 5.00 respectively.

### GPT-5.6 Luna and Terra: cache prices

| Field | Endpoint reports | Repository has | Status |
|---|---|---|---|
| Luna `cache_read_input_token_cost` | 0.02 | 0.02 | Confirmed |
| Luna `cache_creation_input_token_cost` | 0.25 | 0.25 | Confirmed |
| Terra `cache_read_input_token_cost` | 0.20 | 0.20 | Confirmed |
| Terra `cache_creation_input_token_cost` | 2.50 | 2.50 | Confirmed |

### Claude Sonnet 4.6 (an/claude-sonnet-4-6)

| Field | Endpoint reports | Repository has | Status |
|---|---|---|---|
| `max_input_tokens` | 200,000 | `contextWindow: 200,000` | Confirmed |
| `max_output_tokens` | 64,000 | `maxTokens: 64,000` | Confirmed |
| `input_cost_per_token` (×1M) | 3.0 | `costPerMillion.input: 3.0` | Confirmed |
| `output_cost_per_token` (×1M) | 15.0 | `costPerMillion.output: 15.0` | Confirmed |
| `cache_read_input_token_cost` | null / absent | omitted | **Unknown — not rendered** |
| `cache_creation_input_token_cost` | null / absent | omitted | **Unknown — not rendered** |
| `supports_vision` | true | `input: ["text","image"]` | Confirmed |
| `supports_reasoning` / `thinking` | true | `reasoning: true` | Confirmed |

**Sonnet 4.6 cache pricing:**
The endpoint does not report cache read/write prices for `an/claude-sonnet-4-6`.
Those fields remain unknown and are omitted from the active catalog cost and rendered
client templates. Published provider pricing may be recorded separately in a future
hosted-reference field with URL and retrieval date, but is not active route billing.

### Qwen 3.8 27B GGUF (un/qwen3.8-27b-gguf)

| Field | Endpoint reports | Repository has | Status |
|---|---|---|---|
| `max_input_tokens` | 98,304 | `runtimeContextWindow: 98304` | Confirmed |
| `max_output_tokens` | null / absent | `maxTokens: absent` | Confirmed (unknown) |
| `input_cost_per_token` | 0.0 | `localCostPerMillion: null` | Consistent (local cost unknown, 0.0 is proxy default) |
| `output_cost_per_token` | 0.0 | — | Consistent |
| `supports_reasoning` | true | `reasoning: true` | Confirmed |

The proxy-reported 0.0 cost for Qwen reflects that the proxy does not bill for local
inference. Repository policy correctly keeps `localCostPerMillion: null` because actual
local operating cost (power, tariff, hardware amortization) is unknown.

### Gemini 3.7 tiers (an/gemini-3.7-flash-low/medium/high)

| Field | Endpoint reports | Repository has | Status |
|---|---|---|---|
| `input_cost_per_token` (×1M) | 0.75 | `costPerMillion.input: 0.75` (low only) | Confirmed (low) |
| `output_cost_per_token` (×1M) | 3.75 | `costPerMillion.output: 3.75` (low only) | Confirmed (low) |
| `max_input_tokens` | absent | absent | Confirmed absent — limits unknown from endpoint |
| `max_output_tokens` | absent | absent | Confirmed absent |

Context/output limits for Gemini 3.7 tiers remain unknown from this endpoint.
Do not infer limits. High/medium tiers lack pricing in the repository and endpoint;
this is consistent with policy (no price inference).

## Compaction policy audit

Pi client uses a fixed 272,000-token auto-compaction threshold (extension
`~/.pi/agent/extensions/auto-compact-272k.ts`) for models whose context window
exceeds the threshold, with `reserveTokens: 16,384` and `keepRecentTokens: 20,000`.
Smaller-context models are intentionally skipped. This is an intentional conservative choice.

OpenCode uses agent-specific DCP (Dynamic Context Pruning) ranges that vary
by model capability. These are model-specific client strategies, not conflicting global settings.

The live runtime was observed to have a 560,000-token compaction threshold for some
routes. **Repository templates do not adopt this value**: Pi's 272k threshold is
an explicitly conservative strategy documented in `profiles/default.yaml` and
`clients/pi/settings.template.json`. Do not replace it with the live runtime value
without a deliberate policy decision and documented rationale.

See test `test_compaction_policy_documented` for enforcement.

## Approved catalog reconciliation matrix

Every approved canonical ID was checked against the fresh endpoint listing. All current approved IDs were listed. Endpoint fields not reported remain unknown; image aliases are intentionally preserved; Qwen and GPT-5.6 exceptions are documented above.

| ID | Status |
|---|---|
| `an/claude-haiku-4-5-20251001` | listed; curated approved route |
| `an/claude-opus-4-6` | listed; curated approved route |
| `an/claude-sonnet-4-6` | listed; curated approved route |
| `an/gemini-3-pro-image` | listed; curated approved route |
| `an/gemini-3-pro-image-16x9` | listed; curated approved route |
| `an/gemini-3-pro-image-1x1` | listed; curated approved route |
| `an/gemini-3-pro-image-21x9` | listed; curated approved route |
| `an/gemini-3-pro-image-2k` | listed; curated approved route |
| `an/gemini-3-pro-image-2k-16x9` | listed; curated approved route |
| `an/gemini-3-pro-image-2k-1x1` | listed; curated approved route |
| `an/gemini-3-pro-image-2k-21x9` | listed; curated approved route |
| `an/gemini-3-pro-image-2k-3x4` | listed; curated approved route |
| `an/gemini-3-pro-image-2k-4x3` | listed; curated approved route |
| `an/gemini-3-pro-image-2k-9x16` | listed; curated approved route |
| `an/gemini-3-pro-image-3x4` | listed; curated approved route |
| `an/gemini-3-pro-image-4k` | listed; curated approved route |
| `an/gemini-3-pro-image-4k-16x9` | listed; curated approved route |
| `an/gemini-3-pro-image-4k-1x1` | listed; curated approved route |
| `an/gemini-3-pro-image-4k-21x9` | listed; curated approved route |
| `an/gemini-3-pro-image-4k-3x4` | listed; curated approved route |
| `an/gemini-3-pro-image-4k-4x3` | listed; curated approved route |
| `an/gemini-3-pro-image-4k-9x16` | listed; curated approved route |
| `an/gemini-3-pro-image-4x3` | listed; curated approved route |
| `an/gemini-3-pro-image-9x16` | listed; curated approved route |
| `an/gemini-3.1-flash-image` | listed; curated approved route |
| `an/gemini-3.1-pro` | listed; curated approved route |
| `an/gemini-3.1-pro-high` | listed; curated approved route |
| `an/gemini-3.1-pro-low` | listed; curated approved route |
| `an/gemini-3.8-flash-high` | listed; curated approved route |
| `an/gemini-3.8-flash-low` | listed; curated approved route |
| `an/gemini-3.8-flash-medium` | listed; curated approved route |
| `an/gpt-oss-120b-medium` | listed; curated approved route |
| `cl/gemini-3.1-flash-image` | listed; curated approved route |
| `cl/gpt-5.6-luna` | listed; curated approved route |
| `cl/gpt-5.6-sol` | listed; curated approved route |
| `cl/gpt-5.6-terra` | listed; curated approved route |
| `cl/gpt-6-astra` | listed; curated approved route |
| `cl/gpt-image-1.5` | listed; curated approved route |
| `cl/gpt-image-2` | listed; curated approved route |
| `un/gpt-oss-20b-GGUF` | listed; curated approved route |
| `un/qwen3.8-27b-gguf` | listed; curated approved route |

## What was not recorded


- Raw HTTP response payloads
- Private backend model names or internal routing metadata
- Account identifiers or API key values
- Private filesystem paths on the proxy host
- No additional Gemini 3.8 IDs beyond the existing approved catalog
- Claude 5 IDs (present in endpoint, not added without policy decision)

## Governance reference

- Issue: `ozand/ai-agent-config` Issue #3
- Repository: `ozand/ai-agent-config`
- Prior receipt: `docs/migration-receipt.md`


## Historical migration to GPT-6 Luna and GPT-6 Sol (2026-09-09)

This is historical evidence. The current Sol route is GPT-6.1 Sol; see [`litellm-routing-aliases.md`](litellm-routing-aliases.md) for the current compatibility mapping.

The LiteLLM edge proxy (`https://litellm.ayga.tech/v1`) initially updated upstream routing to redirect `gpt-5.6-luna` and `gpt-5.6-sol` requests to `cl/gpt-6-luna` and `cl/gpt-6-sol` via `model_group_alias`. Both endpoints were active and verified then:

| Model ID | Input Cost (×1M) | Output Cost (×1M) | Cache Read (×1M) | Cache Creation (×1M) | Context Limit (Proxy) | Provider Limit |
|---|---|---|---|---|---|---|
| `cl/gpt-6-luna` | 2.0 | 12.0 | 0.01 | 0.125 | 922,000 | 1,050,000 |
| `cl/gpt-6-sol` | 5.0 | 30.0 | 0.20 | 2.50 | 922,000 | 1,050,000 |

Client templates, default profiles, agent routing, and validation suites were updated to target these routes directly at that time. Current reusable client configuration uses `cl/gpt-6-luna` and `cl/gpt-6.1-sol`.
