# Security Policy

## Repository classification

This is a public-safe configuration repository. Assume every tracked byte may become public.

## Never track

- API keys or bearer tokens;
- OAuth tokens, cookies, or account data;
- `.env` files with values;
- Pi `auth.json`, `models-store.json`, sessions, trust state, or package caches;
- OpenCode account/auth state, caches, or private runtime databases;
- private keys, certificates, credential exports, or password-manager payloads;
- authenticated endpoint response dumps;
- live LiteLLM deployment configuration;
- private backend filesystem paths or host inventories.

## Allowed secret references

Tracked templates may contain only client-native references or obvious placeholders:

```text
{env:LITELLM_EDGE_API_KEY}
!powershell.exe ... read-litellm-api-key.ps1
<SET_LOCALLY>
```

A reference describes where the client obtains a secret. It is not permission to store the secret in the repository.

## Local secret storage

The current Windows Pi pattern uses:

```text
%USERPROFILE%\.pi\agent\.secrets\litellm-api-key
```

The file is local-only, should contain only the credential plus an optional final newline, and must have a user-only ACL. The helper script under `clients/pi/scripts/` reads this file for Pi's `!command` resolver.

OpenCode uses an environment reference in its template. Supply `LITELLM_EDGE_API_KEY` through a local secret manager or launcher. Do not put the value in `opencode.json`, PowerShell profile examples, issue comments, or documentation.

## Required checks before commit

```powershell
python scripts/check_rendered.py
python scripts/validate.py
python -m unittest discover -s tests -v
git diff --cached --check
git diff --cached
```

Stage by explicit allowlist. Never use generated or secret-bearing directories as staging roots.

## Incident response

If a credential is committed:

1. Treat it as compromised immediately.
2. Revoke or rotate it at the provider.
3. Remove it from the working tree and Git history using an approved history-rewrite procedure.
4. Audit forks, CI logs, artifacts, issue comments, and release assets.
5. Add a regression rule or test without preserving the leaked value.

Deleting the file in a later commit is not sufficient.
