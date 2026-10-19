# ADR-002: Emit a versioned JSON report with deterministic human projections

**Status**: Accepted
**Accepted**: 2026-10-18 (Issue #14 owner approval)
**Date**: 2026-10-18
**Authors**: Pi assistant
**Supersedes**: None
**Related**: ADR-001, Issue #13, Issue #14

## Context

Issue #13 produced a bounded manual inventory with distinct occurrence and unique-target denominators. Its independent review emphasized that counts are bookkeeping, not extraction accuracy or proof of runtime availability. Issue #14 currently asks for deterministic JSON, table, and Mermaid output with counts derived from the same records. A serialized format would become a public contract, while limiting output to human-readable forms avoids that compatibility obligation.

### Problem statement

The CLI needs a deterministic way to represent each extracted reference once and derive all requested views and counts without implying more evidence than was collected.

### Prior art

Issue #13's final inventory and review (#6229422321, #6229535725) demonstrate separate manual accounting views and explicitly bounded evidence. They do not define a machine-readable schema.

## Decision

### What this IS

**Proposed option A:** emit a versioned JSON record set to stdout as the canonical report; derive deterministic human-readable table and Mermaid entity-graph projections and counts from those same records. Include source-relative location, observed target text, relation, requirement strength, exact-path resolution, entity correspondence, binding, evidence, and bounded search scope as distinct fields. Sort records and graph elements deterministically. Do not write report files by default.

### What this IS NOT

This is not an accepted schema or implementation authorization. JSON does not certify extraction completeness, accuracy, portability, runtime activation, permission, or semantic identity. It does not permit publishing private source text or absolute paths. Choosing human-only table/Mermaid output instead is a viable owner alternative, but would narrow Issue #14's current acceptance scope and must be explicitly decided before implementation.

### Success criteria

- One canonical versioned record set drives JSON, table, Mermaid, and all counts.
- Identical sanitized inputs yield byte-stable JSON and stable projections.
- Resolution, entity correspondence, binding, requirement strength, and evidence cannot be conflated.
- Reports default to stdout and omit private absolute paths/source contents.

## Consequences

### What gets easier

Consumers can inspect the same bounded records in machine-readable and human-readable forms; arithmetic and graph/table projections can be checked against one source.

### What gets harder

A versioned public contract requires compatibility discipline, schema validation, deterministic serialization, and migration rules. Sanitization must be tested for every projection; stdout can still be redirected by callers, so the tool cannot control downstream retention.

### What does not change

The CLI remains offline, read-only, and bounded by ADR-001. Static report fields describe source evidence only; unknown/out-of-scope does not mean globally missing.

## Alternatives Considered

### Alternative 1 — Table and Mermaid only; no JSON contract

Would avoid schema/versioning cost, but fails Issue #14's currently stated JSON acceptance criterion and limits reuse by other tools. Choose only through an explicit owner scope decision.

### Alternative 2 — Persist reports automatically

Rejected for v1: creates retention, path disclosure, and overwrite/cleanup obligations without a demonstrated need. Callers may redirect stdout deliberately.

### Alternative 3 — Do nothing

Leaves counts and graph as manually maintained prose, with no deterministic shared record source. Acceptable if a safe, stable contract cannot be tested.

## Test Contract

| Claim in Decision | Test | Currently |
|---|---|---|
| JSON, table, graph and counts derive from one record set | `test_all_views_derive_from_canonical_records` | not yet written |
| Same inputs yield stable serialized and projected output | `test_report_outputs_are_deterministic` | not yet written |
| Dimension fields remain separate and unknowns are not promoted | `test_report_dimensions_and_unknown_statuses` | not yet written |
| Default output contains no private absolute paths/source contents | `test_default_report_is_sanitized` | not yet written |
| JSON version is explicit and rejects unsupported versions | `test_report_schema_version` | not yet written |

## Rollback

Revert this Proposed ADR if the owner selects human-only output. If accepted and implemented, a later incompatible schema change requires a versioned migration or a superseding ADR; already redirected output cannot be recalled.

## References

- ADR-001: bounded read-only input trust boundary
- Issue #13 final manual inventory: https://github.com/ozand/ai-agent-config/issues/13#issuecomment-6229422321
- Issue #13 independent review: https://github.com/ozand/ai-agent-config/issues/13#issuecomment-6229535725
- Issue #14: https://github.com/ozand/ai-agent-config/issues/14
