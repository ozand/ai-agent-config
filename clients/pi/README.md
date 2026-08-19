# Pi Configuration

## Target paths

Windows:

```text
%USERPROFILE%\.pi\agent\models.json
%USERPROFILE%\.pi\agent\settings.json
%USERPROFILE%\.pi\agent\scripts\read-litellm-api-key.ps1
%USERPROFILE%\.pi\agent\extensions\auto-compact-272k.ts
```

Linux/macOS equivalents live under `~/.pi/agent/`.

## Files in this directory

- `models.template.json` — sanitized provider and 40-model catalog.
- `settings.template.json` — non-secret defaults and subagent routing.
- `scripts/read-litellm-api-key.ps1` — Windows file-backed credential resolver.
- `extensions/auto-compact-272k.ts` — selective large-context compaction.

## Credential setup

Follow [`../../docs/secrets.md`](../../docs/secrets.md). The model template references the script using Pi's supported `!command` syntax. The script reads:

```text
%USERPROFILE%\.pi\agent\.secrets\litellm-api-key
```

Do not replace the `apiKey` command with a literal credential.

## Safe installation

1. Back up existing Pi files outside the repository.
2. Compare existing providers, packages, extensions, and subagent overrides.
3. Copy the helper script and extension.
4. Merge `models.template.json` into `models.json`.
5. Merge `settings.template.json` into `settings.json`.
6. Preserve unrelated providers and local runtime preferences.

Do not copy or edit:

- `auth.json`;
- `models-store.json`;
- `trust.json`;
- sessions;
- OAuth state;
- package caches.

## Verification

```powershell
pi auth check --provider litellm-edge
pi --list-models
pi --model litellm-edge/cl/gpt-5.6-luna --thinking low -p "Reply with exactly OK"
```

Authentication readiness and a real completion are separate gates. Do not run a Qwen completion while its local backend is known to be unavailable.

## Qwen reasoning mapping

| Pi level | Qwen behavior |
| --- | --- |
| `off` | thinking disabled |
| `low` | `low` |
| `medium` | `medium` |
| `high` | `xhigh` |

No exact thinking-token budgets are configured.
