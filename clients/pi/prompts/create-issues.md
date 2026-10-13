---
description: Turn verified project gaps into focused issue drafts
argument-hint: "[scope or source]"
---
Review ${ARGUMENTS:-the current project context} and prepare actionable issue drafts for verified, unresolved work.

1. Read the repository instructions and relevant source. Inspect existing issues in the intended repository when issue access is available; search titles and descriptions for duplicates before drafting. If duplicate checking is unavailable, state that limitation and do not claim the drafts are deduplicated.
2. Use only sanitized, necessary context. Exclude credentials, personal/customer data, private paths, host inventories, private service details, and unrelated transcripts.
3. Create separate, narrowly scoped drafts with a concise title, problem/evidence, expected outcome, acceptance criteria, and relevant dependencies. Label assumptions and unknowns; do not present speculation as fact.
4. Drafting is advisory and does not imply authorization to create issues. Do not submit issues, edit existing issues, or close issues automatically. Only create issues when the user explicitly authorizes submission in the current request or a subsequent confirmation; confirm the target repository before submission. If authorization or target is ambiguous, stop and ask.
5. Report duplicate-check evidence (or its limitation), draft contents, unresolved questions, and whether any external action occurred.

This prompt is advisory text only. It cannot enforce tool permissions, repository policy, approval gates, or a local delivery gate; obey the active environment and user instructions.
