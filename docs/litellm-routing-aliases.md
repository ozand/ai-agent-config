# LiteLLM legacy model routing

The central LiteLLM deployment maintains `router_settings.model_group_alias` so
older client configurations continue to work after model upgrades. These routes
are rewrites at the LiteLLM edge, not client-side fallback chains.

## Verified aliases (2026-10-04)

| Legacy request ID | Current LiteLLM route | Verification |
| --- | --- | --- |
| `gpt-5.6-sol`, `cl/gpt-5.6-sol`, `openai/gpt-5.6-sol` | `cl/gpt-6.1-sol` | Completion returned HTTP 200 for the legacy forms and the current route. |
| `gpt-6-sol`, `cl/gpt-6-sol`, `openai/gpt-6-sol` | `cl/gpt-6.1-sol` | Completion returned HTTP 200 for the legacy forms and the current route. |
| `claude-sonnet-4-6`, `openai/claude-sonnet-4-6`, `an/claude-sonnet-4-6`, `cl/claude-sonnet-4-6` | `an/claude-sonnet-5-5-high` | Alias entries and target completion were verified; API response preserves the requested model name, so it does not independently prove which deployment served a legacy-name request. |

The Sonnet target is Antigravity's `claude-sonnet-5-5-high` route. LiteLLM's
tracked catalog should advertise the target under its canonical ID
`an/claude-sonnet-5-5-high`; legacy IDs in this document are compatibility
inputs and should not be selected for new client configuration.

## Ownership and caveats

- This repository records the sanitized consumer-facing routing contract. The
  live deployment configuration and any LiteLLM database-stored deployment
  records remain owned by the infrastructure deployment.
- A successful response using an old ID is not sufficient proof of rewrite if
  the API echoes the requested ID. Where possible, verify deployment selection
  using safe LiteLLM request metadata/logs.
- Do not configure automatic fallback chains as a substitute for aliases when
  a model has been superseded. Fallbacks and aliases have different semantics.
- Never store credentials, authenticated payloads, or live infrastructure
  configuration in this repository.
