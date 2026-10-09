---
description: Review an iteration and record reusable learnings in project memory
argument-hint: "[iteration context]"
---
Conduct a post-iteration review. Additional context: ${ARGUMENTS:-use the current session and project changes}.

Tasks:
1. Review the completed work, changed files, validation results, failures, and relevant discussion from the current session.
2. Extract only valuable, reusable learnings, including:
   - bug root causes and resolutions;
   - architectural insights, decisions, and constraints;
   - process, testing, and delivery improvements;
   - important warnings and ways to prevent recurrence.
3. Do not record generic knowledge, temporary details, secrets, personal data, or unsupported assumptions.
4. Find and follow the project's established knowledge-base or memory mechanism. If no project-local mechanism exists, use an available global memory mechanism. Do not invent a new format unnecessarily.
5. Check for equivalent existing entries before writing. Update an existing entry instead of creating a duplicate.
6. If no suitable writable memory mechanism exists, or a change requires my decision, do not improvise; report exactly what is missing.

## Evidence label on every learning

Each recorded learning carries the strength of its backing, written into the entry itself:

- **verified** — reproduced or executed directly this session.
- **measured** — observed once, not repeated.
- **reported** — asserted by a tool, log, or document; not independently checked.
- **theory** — reasoned from verified facts.
- **hypothesis** — plausible, unverified.

Do not record speculation. A learning that cannot carry at least **theory** is not yet a learning — note it as an open question instead, or drop it.

An unlabelled entry is worse than no entry: a future session will treat a guess as established fact.

## ADR check

An architectural decision does not belong in memory as a note. If this iteration produced a decision that changed architecture, a public contract, a security or trust boundary, a data format, a dependency, or a deployment target — or that rejected a seriously considered alternative — it requires an ADR.

Apply the reversal test: if this were reversed in six months, would someone need to know why it was chosen?

- ADR already written this iteration → record its number in the memory entry and do not duplicate its reasoning into memory.
- ADR required but missing → read the `adr` skill's `SKILL.md`, write it, and report the number. Do not silently record the decision as a memory note.
- No architectural decision occurred → state "No ADR required."

## Output

After recording, output a brief bulleted summary containing only what was actually saved:

- **Recorded:** ... *(each with its evidence label)*
- **Location:** exact file, section, or memory identifier
- **ADR:** number and status, or "No ADR required"
- **Open questions:** anything too weak to record, and what would settle it

If there is nothing worth recording, state: "No new reusable learnings were identified."
