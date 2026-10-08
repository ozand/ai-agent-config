---
description: Explain the current project's goals, purpose, and the agent's role
---
Analyze the current project and produce a clear overview.

Actions:
1. Summarize the directory structure using names only. Do not recursively read or summarize arbitrary files. Exclude service/heavy directories such as `.git`, `node_modules`, build artifacts, and caches, and skip any directory that appears private, generated, user data, or runtime state.
2. Locate root-level `README.md` and `AGENTS.md` files case-insensitively.
3. Read and parse both files completely. If either file is missing, state that explicitly and continue using the available information.
4. If `docs/adr/` or `docs/adrs/` exists, read its `INDEX.md` and list the currently binding decisions (`Accepted`, `Accepted — Implemented`). Superseded and withdrawn ADRs are history, not constraints — do not present them as current.
5. Do not expose secrets, keys, tokens, private data, personal information, hostnames, absolute paths, or sensitive values. If `README.md`, `AGENTS.md`, or the ADR index contains such data, omit or redact it and flag the issue rather than repeating it.
6. Do not modify any files.

Begin with a concise summary of the directory structure, then use these sections:
1. **Project Goals** — the intended outcomes and objectives defined by the documentation.
2. **Repository Purpose** — what this repository or workspace contains, what it supports, and what it is not.
3. **Binding Decisions** — the accepted ADRs that constrain future work, one line each: number, decision, status. If no ADR series exists, write "No ADR series present."
4. **Your Assigned Role and Capabilities** — the agent's responsibilities, available actions, and operating constraints.

## Evidence labelling

Do not use a plain confirmed/inferred split. Label every non-trivial claim with the strength of what actually backs it:

- **verified** — I executed or read it directly in this session.
- **measured** — observed once, not repeated or reproduced.
- **reported** — the documentation or a third party asserts it; I did not check.
- **theory** — follows by sound reasoning from verified facts.
- **hypothesis** — plausible, consistent with what I see, unverified.
- **speculation** — a guess; flag it as such or omit it.

Prefer omitting a claim to presenting speculation. Never invent missing information.

## Documentation drift

Report every place where `README.md`, `AGENTS.md`, or the ADR index contradicts the files actually present — a referenced path that no longer exists, a stated fact that the repository disproves, a binding ADR whose decision the code no longer follows. List each as: claim, observed reality, evidence label. If there is no drift, write "No drift detected."
