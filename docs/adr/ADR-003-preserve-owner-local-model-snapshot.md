# ADR-003: Preserve owner-local model entries without curation

**Status**: Accepted
**Date**: 2026-11-04
**Authors**: Pi assistant, recording the owner's explicit local-authority instruction
**Supersedes**: None
**Related**: Issues #16 and ozand/pi-config#69

## Context

The owner explicitly selected the current local Pi model configuration as authoritative for model lists and every model-entry parameter. Prior curated templates silently changed context windows, omitted configured zero costs and excluded older model IDs. This conflicts with the requested replication result. Existing ADR-001/002 govern offline reference auditing and are unaffected.

## Decision

Catalog schemaVersion 2 retains the existing model metadata envelopes, but adds an exact `piModel` object per entry. The ordered `models` array belongs to litellm-edge; `additionalProviders` contains sanitized provider templates with exact ordered model entries. The Pi renderer copies these objects verbatim, not inferred metadata. Zero costs are configured values, not measured operating cost. Prior catalog fields remain historical reference metadata where retained and never override piModel.

OpenCode projects supported fields from piModel (limits only when both input/output limits exist; reasoning, modalities, cost and reasoning variants). Pi-specific fields such as thinkingLevelMap and compat stay losslessly available in piModel and the Pi template; they must not be injected as unsupported OpenCode fields. Local provider addresses use a non-routable placeholder. Credentials use existing client-native references, never literal keys. No endpoint requests are necessary to replicate configuration.

This changes catalog serialization and renderer precedence, not provider runtime, credentials, local configuration, model availability, agent roles or task authority. Snapshot parity is not evidence of verified model capabilities or measured prices.

## Consequences

### What gets easier
Exact ordered Pi equality can be asserted, including newly introduced fields without extending a whitelist.

### What gets harder
The catalog contains Pi-specific authoritative data alongside historical reference metadata. OpenCode is a documented projection, not byte-equivalent Pi configuration. Consumers must recognize schemaVersion 2.

### What does not change
Secret safety, unrelated provider/runtime settings, independent review and explicit publication controls remain effective. Host-local provider activation is not automatic.

## Alternatives Considered

- Continue curated rendering: rejected by explicit owner instruction because it changes local settings.
- Copy only generated Pi JSON: rejected because subsequent rendering would revert it.
- Emit Pi fields unchanged into OpenCode: rejected because the clients have different supported schemas.

## Test Contract

| Claim | Test | Currently |
| --- | --- | --- |
| Exact ordered Pi model parity for both providers | test_snapshot_pi_parity | planned |
| New fields survive renderer without whitelisting | test_unknown_pi_field_preserved | planned |
| OpenCode supported projection and unknown output limits preserved | test_opencode_projection | planned |
| Host-local provider has only safe placeholder | test_local_provider_placeholder | planned |

## Rollback

Revert this bounded catalog/renderer increment together; never modify the live host during rollback. Prior evidence remains historical, not current authority.

## References

- #16: owner-corrected scope and source snapshot digest
- ozand/pi-config#69: corresponding Pi backup replication
