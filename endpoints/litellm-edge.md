# LiteLLM Edge Endpoint

## Connection

| Field | Value |
| --- | --- |
| Provider ID | `litellm-edge` |
| API style | OpenAI-compatible |
| Base URL | `https://litellm.ayga.tech/v1` |
| Credential name | `LITELLM_EDGE_API_KEY` |
| Interactive model | `cl/gpt-5.6-luna` |
| Small/fast model | `an/gemini-3.7-flash-low` |

The credential value is never stored in this repository.

## Raw API model reference

Direct API requests use the public LiteLLM model ID:

```text
cl/gpt-5.6-luna
```

Client model selectors include the client provider ID:

```text
litellm-edge/cl/gpt-5.6-luna
```

These are not interchangeable with a direct provider route such as `openai/gpt-5.6-luna`; each route can use different credentials and failure domains.

## Safe model discovery

List models without printing the credential:

```powershell
$headers = @{ Authorization = "Bearer $env:LITELLM_EDGE_API_KEY" }
Invoke-RestMethod -Headers $headers -Uri "https://litellm.ayga.tech/v1/models"
```

Do not paste the resulting raw payload into Git. Normalize only approved public IDs and explicitly reported metadata into `catalog/models.json`.

## Minimal completion check

```powershell
$headers = @{
  Authorization = "Bearer $env:LITELLM_EDGE_API_KEY"
  "Content-Type" = "application/json"
}
$body = @{
  model = "cl/gpt-5.6-luna"
  messages = @(@{ role = "user"; content = "Reply with exactly OK" })
  max_tokens = 16
} | ConvertTo-Json -Depth 4
Invoke-RestMethod -Method Post -Headers $headers -Body $body `
  -Uri "https://litellm.ayga.tech/v1/chat/completions"
```

Do not include headers, keys, or full sensitive responses in reports.

## Separate verification gates

A valid endpoint profile does not prove runtime success. Verify separately:

1. credential resolution;
2. `/v1/models` discovery;
3. `/v1/model/info` metadata;
4. representative completion;
5. client-specific model resolution.

The local Qwen runtime recovery is a separate operational concern and must not be inferred from catalog presence.
