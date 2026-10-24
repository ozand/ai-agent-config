#!/bin/sh
set -eu

secret_file="${HOME:?HOME must be set}/.pi/agent/.secrets/litellm-api-key"
if [ ! -f "$secret_file" ]; then
    printf '%s\n' 'LiteLLM credential file is missing. See docs/secrets.md.' >&2
    exit 1
fi
if [ ! -s "$secret_file" ]; then
    printf '%s\n' 'LiteLLM credential file is empty.' >&2
    exit 1
fi

# Pi consumes stdout from the models.json !command resolver.
cat "$secret_file"
