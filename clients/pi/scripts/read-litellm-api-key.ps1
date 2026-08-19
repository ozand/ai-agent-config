$ErrorActionPreference = "Stop"

$keyPath = Join-Path $env:USERPROFILE ".pi\agent\.secrets\litellm-api-key"
if (-not (Test-Path -LiteralPath $keyPath -PathType Leaf)) {
    throw "LiteLLM credential file is missing. See docs/secrets.md."
}

$key = (Get-Content -LiteralPath $keyPath -Raw).Trim()
if ([string]::IsNullOrWhiteSpace($key)) {
    throw "LiteLLM credential file is empty."
}

# Pi consumes stdout from the models.json !command resolver. Do not invoke this
# script manually in logs, CI, screenshots, or diagnostics that capture stdout.
[Console]::Out.Write($key)
