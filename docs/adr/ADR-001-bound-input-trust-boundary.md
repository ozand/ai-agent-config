# ADR-001: Restrict reference audits to explicit read-only input roots

**Status**: Proposed
**Date**: 2026-10-18
**Authors**: Pi assistant
**Supersedes**: None
**Related**: Issue #13 (bounded manual pilot), Issue #14 (offline audit CLI)

## Context

Issue #13's bounded manual pilot and independent review distinguish literal path matches, entity-name correspondence, and unchecked references. The pilot does not claim completeness, runtime availability, or portability. Issue #14 proposes a reusable offline CLI; processing arbitrary local files creates a trust boundary not covered by the manual pilot. The repository is public-safe and excludes private paths, inventories, credentials, and runtime state.

### Problem statement

The proposed CLI must inspect user-selected Markdown without silently expanding its authority to unrelated files, executing content, or publishing sensitive paths.

### Prior art

Issue #13 comments #6229422321 and #6229535725 document the explicit-allowlist, no-execution pilot and its limits. They are bounded manual evidence, not proof of implementation behavior.

## Decision

### What this IS

For the proposed CLI, accept only explicitly supplied input roots/files. Treat all source content as untrusted data, never as instructions to the CLI or operator; parsed references are records only and must never trigger tools, commands, or resource loading. Read files as data, with no execution, installation, environment-variable expansion, network access, recursive host discovery, or modification of inputs. Resolve candidate paths only within declared roots; reject symlink traversal that escapes those roots. Bound file size and traversal depth as implementation limits. Classify access and decoding failures without printing sensitive absolute paths. Keep generated/published examples sanitized.

### What this IS NOT

This does not authorize broad crawling, following arbitrary links, executing prompts/extensions/scripts, reading secrets, or claiming that an observed reference is installed, active, permitted, or semantically correct. It does not define an accepted output schema; that is addressed separately by ADR-002.

### Success criteria

- Input enumeration is limited to explicit declared roots.
- Parent traversal and symlink escape cannot cause reads outside those roots.
- No input content or parsed reference is executed, installed, invoked, or sent over the network.
- File-size and traversal-depth limits are enforced.
- Errors and reports do not disclose private absolute paths by default.

## Consequences

### What gets easier

Audits have a reviewable, bounded input scope and can run offline against sanitized fixtures.

### What gets harder

Callers must enumerate roots; symlinked dependencies outside them are rejected, and ambiguous/inaccessible/dynamic references remain unresolved rather than being followed or guessed. Path handling and redaction require explicit tests.

### What does not change

Static references remain evidence about source declarations only. They do not prove runtime loading, activation, permissions, or behavior.

## Alternatives Considered

### Alternative 1 — Scan the whole host or repository automatically

Rejected because it expands scope unpredictably and can collect private or unrelated data; it contradicts Issue #13's bounded allowlist and the repository's sanitization boundary.

### Alternative 2 — Execute or resolve references using environment/runtime state

Rejected because execution and environment expansion turn an offline source audit into runtime behavior with credential and side-effect risks, and exceed the research evidence.

### Alternative 3 — Accept only checked-in sanitized fixtures

This is safer and narrower, but prevents the stated CLI goal of auditing explicitly selected user inputs. Keep as a fallback if safe root containment/redaction cannot be demonstrated by tests.

### Alternative 4 — Do nothing

Leaves the manual pilot non-repeatable; acceptable if the proposed safety contract cannot be implemented and tested.

## Test Contract

| Claim in Decision | Test | Currently |
|---|---|---|
| Only explicit roots are enumerated | `test_explicit_roots_only` | not yet written |
| Parent traversal and symlink escape are rejected before reading | `test_rejects_root_escape_and_symlink_escape` | not yet written |
| Inputs are untrusted data; parsed references never invoke tools, and no network is used | `test_audit_is_read_only_and_offline` | not yet written |
| File-size and traversal-depth limits are enforced | `test_enforces_input_size_and_depth_limits` | not yet written |
| Errors and generated output redact absolute private paths | `test_sanitizes_paths_in_errors_and_outputs` | not yet written |
| Decode/access failures remain distinct from missing targets | `test_classifies_decode_and_access_failures` | not yet written |

## Rollback

Revert this Proposed ADR before acceptance if the owner rejects it. If accepted and implemented, replace the CLI with a follow-up decision and remove the CLI; previously emitted reports cannot be recalled, so outputs must remain caller-controlled and sanitized by default.

## References

- Issue #13 final manual inventory: https://github.com/ozand/ai-agent-config/issues/13#issuecomment-6229422321
- Issue #13 independent review: https://github.com/ozand/ai-agent-config/issues/13#issuecomment-6229535725
- Issue #14: https://github.com/ozand/ai-agent-config/issues/14
