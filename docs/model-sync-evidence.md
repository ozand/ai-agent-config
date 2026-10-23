# Model routing synchronization evidence

Observed at 2026-10-23T01:32:00.999163+00:00 (UTC).

Scope: ai-agent-config #16 and pi-config #69. This is sanitized derived evidence, not an authenticated response dump.

Authenticated GETs to `https://litellm.ayga.tech/v1/models` and `/v1/model/info` both returned HTTP 200 during this increment. Registered routes include `cl/gpt-6-luna`, `cl/gpt-6.1-sol`, `cl/gpt-5.6-terra`, Gemini 3.8 Flash high/medium/low and `un/qwen3.8-27b-gguf`.

| Route | Reported input | Reported output | USD / 1M input | output | cache read | cache creation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cl/gpt-6-luna | 922000 | 128000 | 2 | 12 | 0.01 | 0.125 |
| cl/gpt-6.1-sol | 922000 | 128000 | 2 | 10 | 0.1 | 2.5 |
| cl/gpt-5.6-terra | 922000 | 128000 | 2 | 12 | 0.2 | 2.5 |
| un/qwen3.8-27b-gguf | 98304 | unknown | proxy reports 0 | proxy reports 0 | unknown | unknown |

GPT metadata matches the canonical catalog. Pi backup configuration receives the same Luna/Sol/Terra fields from the existing renderer. No unrelated aliases are deleted. Qwen runtime input is confirmed, but the Pi consumer limit remains the existing conservative policy of 73728; this is not a claim that the endpoint reports 73728. Unknown local operating cost is omitted, not set to zero. Qwen output remains unknown. No Qwen inference or image probe was run.

Pi worker/reviewer select Luna, reviewer thinking high; oracle selects Sol, thinking high. Other role primaries and each client's interactive default are preserved. Gemini 3.7 references are aligned to registered 3.8. OpenCode plan/agent selections and its fallback mechanisms are not changed apart from the stale Gemini generation reference.

Installed pi-subagents documentation states one model per launch and no provider-error fallback. Its agent override parser explicitly rejects the removed `fallbackModels` field. Pi templates therefore omit it, and canonical Pi role routing no longer advertises automatic fallback. This does not modify LiteLLM server routing. Existing package pins are not updated by this increment.

Local application and active-session verification are distinct from repository publication. No restart, reload, package install, server edit or failed-task retry is authorized by this receipt.
