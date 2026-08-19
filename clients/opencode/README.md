# OpenCode Configuration

## Target paths

Global Windows configuration:

```text
%USERPROFILE%\.config\opencode\opencode.json
%USERPROFILE%\.config\opencode\dcp.jsonc
%USERPROFILE%\.config\opencode\agents\
```

Global Linux/macOS configuration:

```text
~/.config/opencode/opencode.json
~/.config/opencode/dcp.jsonc
~/.config/opencode/agents/
```

Project-level `opencode.json` and `.opencode/` resources can override or extend global configuration. Inspect effective precedence before applying changes.

## Credential setup

The template uses:

```json
"apiKey": "{env:LITELLM_EDGE_API_KEY}"
```

Supply this variable through a local secret manager or launcher. Do not replace it with a literal key.

## Safe installation

1. Back up the active configuration outside Git.
2. Check `OPENCODE_CONFIG`, `OPENCODE_CONFIG_DIR`, and `OPENCODE_CONFIG_CONTENT` overrides.
3. Merge the `litellm-edge` provider and selected agent sections.
4. Preserve unrelated plugins, MCP servers, permissions, and providers.
5. Copy only the desired agent Markdown files.
6. Apply `dcp.template.jsonc` only when the DCP plugin is installed.

## Verification

```powershell
opencode debug config
opencode models litellm-edge
opencode run --model litellm-edge/cl/gpt-5.6-luna "Reply with exactly OK"
```

Expected defaults:

```text
model: litellm-edge/cl/gpt-5.6-luna
small_model: litellm-edge/an/gemini-3.7-flash-low
```

## Qwen schema boundary

OpenCode's `limit` object requires both context and output limits. The Qwen output limit is currently unknown, so the template intentionally leaves `limit` absent. It declares only verified reasoning and text-input modality metadata.
