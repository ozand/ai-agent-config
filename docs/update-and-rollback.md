# Update and Rollback Workflow

## Update

1. Start from a clean repository state.
2. Collect fresh endpoint evidence outside Git.
3. Update `catalog/models.json` and policy files first.
4. Update Pi and OpenCode templates in the same change.
5. Update endpoint and migration documentation.
6. Run tests and validation.
7. Review the diff and commit by allowlist.
8. Apply templates locally only after repository verification passes.

## Apply to a local client

Before changing a live user configuration:

1. identify the active file and configuration precedence;
2. create a timestamped backup outside this repository;
3. validate the backup exists and is readable;
4. produce a dry-run diff;
5. merge only intended sections;
6. parse the result;
7. verify model listing;
8. run one minimal completion on a healthy representative route.

Do not overwrite Pi or OpenCode configuration wholesale when it contains unrelated local providers, MCP servers, plugins, permissions, packages, extensions, or runtime preferences.

## Rollback

If parsing, model resolution, authentication, or completion fails:

1. preserve the failed file for diagnosis without committing secrets;
2. restore the exact pre-change backup;
3. parse the restored configuration;
4. verify the previous default model resolves;
5. keep endpoint service state unchanged unless a separate operational plan authorizes mutation.

## Generated caches

Never restore a configuration by editing generated client caches:

- Pi `models-store.json` is generated;
- OpenCode cache/model databases are generated;
- sessions and account state are runtime data.

Restore source configuration, then let the client refresh its caches.

## Policy rollback

A repository rollback should revert the policy, both client templates, tests, and docs together. Do not roll back only one client and leave catalog drift hidden.
