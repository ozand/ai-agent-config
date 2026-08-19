# AGENTS.md — ai-agent-config

## Required reading

Before changing repository content, read:

1. `README.md`
2. `SECURITY.md`
3. `docs/architecture.md`
4. `docs/secrets.md`
5. `catalog/model-policy.yaml`
6. the target client's README under `clients/`

## Project overview

This repository is the sanitized, declarative source of truth for reusable Pi and OpenCode configuration. It documents OpenAI-compatible endpoints, current model policy, client templates, agent routing, secret-file creation, and safe validation.

It must not contain credentials, private runtime state, raw authenticated endpoint responses, host inventories, or private backend filesystem paths.

## File structure

- `catalog/` — canonical client-independent model and routing policy.
- `endpoints/` — sanitized endpoint profiles and connection documentation.
- `profiles/` — recommended operating profiles and defaults.
- `clients/pi/` — Pi templates, helper scripts, and extensions.
- `clients/opencode/` — OpenCode templates, DCP policy, and agent definitions.
- `docs/` — architecture, secret provisioning, update, rollback, and migration documentation.
- `scripts/` — validation and rendering utilities. Scripts must never print secret values.
- `tests/` — Python standard-library tests for policy, templates, and secret safety.

## Environment setup

The repository requires Python 3.11 or newer. It has no third-party runtime dependencies.

```powershell
python -m unittest discover -s tests -v
python scripts/validate.py
```

## Build and test commands

Run from the repository root:

```powershell
python -m unittest discover -s tests -v
python scripts/validate.py
```

The validation script must check strict JSON, required policy/profile markers, model parity, placeholders, provider-qualified routes, stale active generations, and likely secret material without echoing matched values.

## Configuration conventions

### Canonical policy

- Treat `catalog/model-policy.yaml` as the human-readable policy contract.
- Treat `catalog/models.json` as the machine-readable canonical model catalog.
- Keep Pi and OpenCode client catalogs synchronized with `catalog/models.json`.
- Preserve required image-generation route variants independently.
- Do not infer missing limits, capabilities, modalities, or prices.

### Pi

- Store reusable Pi catalog data in `clients/pi/models.template.json`.
- Store non-secret defaults in `clients/pi/settings.template.json`.
- Use `!command` for file-backed credentials where documented.
- Never edit or copy generated `models-store.json`.
- Never track `auth.json`, sessions, trust state, package caches, or OAuth data.

### OpenCode

- Store reusable configuration in `clients/opencode/opencode.template.jsonc`.
- Use `{env:VARIABLE_NAME}` for endpoint credentials.
- Every custom model selection must be provider-qualified.
- Verify configuration precedence before applying a template to a live installation.
- Keep image-generation aliases separate from ordinary image-input chat models.

### Endpoints

- Endpoint profiles contain public/sanitized connection metadata only.
- Document the required secret identifier and expected local file or environment variable, never its value.
- Do not copy live LiteLLM configuration or authenticated API payloads into this repository.
- Separate model registration, discovery, metadata, completion, and client-resolution verification.

## Security considerations

- Never commit API keys, bearer tokens, cookies, OAuth state, private keys, credentials, or private `.env` files.
- Never include real values in examples, comments, fixtures, tests, screenshots, or Git history.
- Secret examples must use obvious placeholders such as `<SET_LOCALLY>` or client-native references.
- Secret readers may print the secret only because the target client consumes stdout; validation and documentation commands must not invoke them in a way that exposes output.
- Review `git diff --cached` and run `python scripts/validate.py` before every commit.

## Change workflow

1. Update the canonical catalog or policy first.
2. Update both Pi and OpenCode templates in the same change when the policy affects both.
3. Update docs and migration notes.
4. Run all tests and validation.
5. Review the staged diff by allowlist.
6. Report unknown metadata and residual drift explicitly.

## Known boundaries

- This repository owns reusable client configuration, not live endpoint deployment.
- Host-specific activation remains outside this repository.
- Current bootstrap provenance is documented in `docs/migration-receipt.md` and references `servers_team` issues #143, #180, and #181.
