# Sanitized Migration Receipt

## Bootstrap

- Local repository: `T:/Code/ai-agent-config`
- Remote repository: `https://github.com/ozand/ai-agent-config`
- Default branch: `main`
- Bootstrap governance: `ozand/servers_team` Issue #181 (completed and closed)
- Native follow-up governance: `ozand/ai-agent-config` Issue #1
- Pi credential/model boundary: `ozand/servers_team` Issue #143
- OpenCode/Pi catalog synchronization boundary: `ozand/servers_team` Issue #180

## Migrated policy

The standalone repository records:

- provider priority: `an/` for Claude/Gemini, `cl/` for GPT-5.6, `un/` for approved local/open-weight routes;
- shared Luna interactive default;
- Gemini 3.7 Flash small route;
- Opus reviewer/oracle routing with Gemini and GPT fallbacks;
- matching 40-model Pi/OpenCode endpoint catalogs;
- preserved image-generation aliases;
- Qwen text-only and layered context policy;
- verified selected model pricing and limits;
- file-backed Pi credential instructions and OpenCode environment references.

## Explicitly not migrated

- credential values;
- Pi `auth.json`, `models-store.json`, sessions, trust state, or caches;
- OpenCode account/auth state, caches, or private databases;
- raw `/v1/models` or `/v1/model/info` payloads;
- live LiteLLM configuration;
- private backend paths, inventories, logs, or runtime evidence;
- host-specific Home Manager activation state.

## Ownership after bootstrap

- This repository owns reusable sanitized client policy, templates, validation, and future client-configuration issues.
- `servers_team` retains infrastructure deployment and historical bootstrap issues.
- Local secret files and activated user configs remain local-only.
- GitHub Actions validates rendered-template freshness, policy, catalog parity, tests, and secret hygiene on pushes and pull requests.

## Rollback

Deleting this repository does not remove or alter active Pi/OpenCode configuration. Local activation is an explicit separate step and must use backups as documented in `docs/update-and-rollback.md`.
