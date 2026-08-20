# AI Agent Config

Sanitized, declarative configuration and documentation for Pi and OpenCode.

This repository describes:

- recommended endpoint configuration;
- the current approved model catalog;
- default and fallback routing;
- Pi and OpenCode templates;
- how to create local credential files without putting keys in Git;
- validation, update, and rollback procedures.

It does **not** contain API keys, private runtime state, authenticated API dumps, or live LiteLLM deployment configuration.

## Repository role

This repository is the reusable client-configuration source of truth. It is intentionally separate from infrastructure repositories:

- endpoint deployment remains in the relevant infrastructure repository;
- host-specific activation remains local or declarative in the host-management layer;
- credentials remain local-only;
- this repository stores sanitized policy, templates, and instructions.

## Quick start

### 1. Review the endpoint profile

Start with:

```text
endpoints/litellm-edge.md
endpoints/litellm-edge.yaml
```

The default endpoint profile uses an OpenAI-compatible API root and the provider ID `litellm-edge`.

### 2. Create the local credential file

On Windows, the documented Pi credential path is:

```text
%USERPROFILE%\.pi\agent\.secrets\litellm-api-key
```

Create it locally and protect its ACL. Do not place the real key anywhere in this repository. Full commands are in [`docs/secrets.md`](docs/secrets.md).

OpenCode normally resolves the same endpoint credential through a process environment variable:

```text
LITELLM_EDGE_API_KEY
```

The variable must be supplied by a local secret manager or launcher. Do not store its value in Git or in the template.

### 3. Install or merge client templates

Pi templates:

```text
clients/pi/models.template.json
clients/pi/settings.template.json
```

OpenCode templates:

```text
clients/opencode/opencode.template.jsonc
clients/opencode/dcp.template.jsonc
clients/opencode/agents/
```

Do not blindly overwrite an existing user configuration. Back it up outside Git, compare it with the template, and merge only the intended sections. See [`docs/update-and-rollback.md`](docs/update-and-rollback.md).

### 4. Validate the repository

```powershell
python scripts/check_rendered.py
python -m unittest discover -s tests -v
python scripts/validate.py
```

## Current routing policy

- `an/` — current Claude and Gemini routes;
- `cl/` — GPT-5.6 routes;
- `un/` — approved local and open-weight routes;
- image-generation aliases are preserved separately;
- provider-qualified client references are mandatory.

Recommended defaults:

- interactive: `litellm-edge/cl/gpt-5.6-luna`;
- small/fast: `litellm-edge/an/gemini-3.7-flash-low`;
- reviewer/oracle: `litellm-edge/an/claude-opus-4-6` with Gemini and GPT fallbacks.

## Important Qwen boundary

`un/qwen3.8-27b-gguf` is text-only.

- runtime/catalog context: 98,304 tokens;
- conservative Pi consumer context: 73,728 tokens;
- OpenCode leaves `limit` absent while the output limit remains unknown;
- reasoning levels are qualitative, not exact token budgets.

## Documentation map

- [`SECURITY.md`](SECURITY.md) — non-negotiable secret policy.
- [`docs/architecture.md`](docs/architecture.md) — ownership and data flow.
- [`docs/secrets.md`](docs/secrets.md) — local secret-file and environment setup.
- [`docs/update-and-rollback.md`](docs/update-and-rollback.md) — safe application workflow.
- [`docs/migration-receipt.md`](docs/migration-receipt.md) — sanitized bootstrap provenance.
- [`catalog/README.md`](catalog/README.md) — canonical policy and catalog rules.
- [`endpoints/README.md`](endpoints/README.md) — endpoint-profile contract.

## Status

Initial standalone bootstrap is governed by `ozand/servers_team` Issue #181 and derives current policy boundaries from Issues #143 and #180.
