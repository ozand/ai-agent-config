---
description: Execute an approved implementation plan safely
argument-hint: "[plan or plan file]"
---
Execute the plan identified by ${ARGUMENTS:-the current session only if the user explicitly approved it}. If the plan's approval is not explicit in the user's instructions, stop and ask for approval before implementation.

1. Read repository instructions and the relevant plan before editing. Confirm the target repository and inspect its current status; preserve unrelated work.
2. Follow the explicitly approved plan narrowly. For routine, reversible implementation and validation steps within that plan, proceed without repeated confirmation. Keep changes focused and follow existing patterns.
3. Stop and report before expanding scope, changing public behavior beyond the plan, exposing sensitive data, or taking risky/irreversible actions (including external delivery, destructive operations, commits, pushes, merges, or deployments) unless specifically authorized.
4. Run relevant project-scoped checks. Distinguish checks actually run from recommendations; report failures and uncertainty without claiming success.
5. Review the diff and secret-safety implications. Do not stage, commit, or publish unless explicitly requested and authorized.
6. Summarize changes, validation, remaining risks, and next steps with concrete evidence.

This prompt is advisory text only. It cannot enforce tool permissions, repository policy, approval gates, or a local delivery gate; obey the active environment and user instructions.
