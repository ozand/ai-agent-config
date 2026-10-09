# Pi slash-command prompts

This directory contains reviewed, reusable Pi prompt templates. Each direct `.md` file is exposed by filename as a slash command when copied into Pi's prompt directory. These templates are examples and instructions; they do not install tools or grant project trust.

## Included commands

- `/git-sync-status [remote]` — fetch and report synchronization state without pulling, pushing, merging, or rebasing.
- `/status-ru` — write a concise, verified project status report in Russian.
- `/project-overview` — summarize the current repository from its instructions and documentation without modifying files.
- `/capture-learnings [context]` — review completed work and record reusable, evidence-labeled learnings through the project's established memory mechanism.

Before using a project-scoped prompt, review it and grant project trust only to content you trust. After installation or changes, run `/reload` and verify the command in the active Pi `/` menu.

See [`../../../docs/pi-prompt-sharing.md`](../../../docs/pi-prompt-sharing.md) for the curation policy and local/private exclusions.
