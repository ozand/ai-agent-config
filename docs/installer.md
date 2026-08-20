# Safe client installer/merger

`scripts/install_config.py` applies the tracked Pi and OpenCode templates without replacing whole user configuration files. It is **dry-run by default**.

The tool uses only Python's standard library and never opens a credential file. Secret references in the templates are copied as opaque client-native strings.

## Dry run

From the repository root:

```powershell
python scripts/install_config.py --client all
```

For a sanitized temporary fixture or an explicit client directory:

```powershell
python scripts/install_config.py `
  --client pi `
  --pi-dir "$env:USERPROFILE\.pi\agent"

python scripts/install_config.py `
  --client opencode `
  --opencode-dir "$env:USERPROFILE\.config\opencode" `
  --agent docs-writer
```

A dry run prints a deterministic plan and sanitized unified diff. It does not create directories or modify files. Run it and inspect the result before applying.

## Managed sections

Pi:

- `models.json`: the `litellm-edge` provider and its tracked model catalog; other providers, provider extension keys, and locally-added models remain intact;
- `settings.json`: repository-owned defaults, enabled model patterns, required packages/extensions, and subagent overrides; unrelated runtime settings remain intact. On a first install, missing files are seeded from the template, including non-owned runtime defaults; later runs do not update those non-owned keys;
- the tracked credential-reader helper and auto-compact extension (copied as files, without reading the local secret).

OpenCode:

- `opencode.json`: top-level `model`, `small_model`, and `default_agent`; the `litellm-edge` provider; and the named agents from the template. Other providers, plugins, MCP servers, permissions, and unknown keys remain intact;
- `agents/`: only selected tracked agent Markdown files when `--agent` is supplied; without `--agent`, all tracked agent files are managed;
- `dcp.jsonc` is not managed unless `--include-dcp` is explicitly supplied.

The tool does not modify Pi auth/state/cache files, OpenCode auth/state/cache data, endpoint deployment, credentials, or canonical templates.

## Apply

Apply requires both flags as an explicit confirmation guard:

```powershell
python scripts/install_config.py `
  --client all `
  --backup-dir "$env:TEMP\ai-agent-config-backups" `
  --apply `
  --confirm-apply
```

Before writing, the tool validates and parses every target configuration, creates a timestamped backup **outside the repository**, verifies the backup contents and manifest, and then writes the managed files. It verifies each write by reading it back. If apply fails after backup creation, stop and restore that verified backup.

The backup contains only pre-change files that existed and a `MANIFEST.txt`; it does not contain secret files. Choose a backup directory with suitable local permissions and do not commit it.

## Rollback

If parsing, model resolution, authentication, or completion fails:

1. preserve the failed configuration outside Git if diagnosis is needed;
2. restore the exact pre-change files from the timestamped backup;
3. parse the restored JSON/JSONC configuration;
4. verify the previous client default and model listing;
5. do not restore generated caches or auth/session state.

The installer is intentionally not a deployment or authentication check. A successful merge proves only that the local source configuration was parsed and written.

## Platform behavior and limitations

- Windows is the primary documented platform: `USERPROFILE` is preferred for default paths, with `HOME` as a portable fallback.
- Paths can be overridden with `--pi-dir` and `--opencode-dir`; target and backup locations must be outside this repository.
- JSONC comments and trailing commas are accepted for existing OpenCode files. The output is normalized JSON, so formatting/comments outside the managed sections are not preserved byte-for-byte.
- Existing unknown object keys are retained recursively. Existing local models and package/extension entries are retained; tracked entries are updated to the template.
- The tool cannot merge concurrent edits. Re-run the dry run and create a new backup before a second apply.
