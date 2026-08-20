# Architecture and Ownership

## Purpose

`ai-agent-config` is the reusable configuration layer between endpoint infrastructure and local AI clients.

```text
Endpoint infrastructure
        │
        │ public model IDs + sanitized metadata
        ▼
ai-agent-config
  catalog + policy + templates
        │
        │ local merge or declarative activation
        ▼
Pi / OpenCode user configuration
        │
        │ secret reference only
        ▼
Local secret file or secret manager
```

## Ownership boundaries

### This repository owns

- sanitized endpoint profiles;
- current approved model catalog;
- provider-priority and fallback policy;
- Pi and OpenCode templates;
- secret-location and provisioning instructions;
- validation and drift checks;
- migration and rollback documentation.

### Endpoint infrastructure owns

- live LiteLLM deployment configuration;
- provider credentials and service keys;
- backend mappings;
- container/service lifecycle;
- databases, logs, and runtime health.

### Local host configuration owns

- real secret values;
- active user-specific merged configuration;
- Pi/OpenCode auth state and caches;
- sessions and runtime preferences;
- activation and rollback execution.

## Canonical data flow

1. Authenticate to the endpoint outside this repository.
2. Derive only approved public IDs and explicitly reported metadata.
3. Update `catalog/models.json`.
4. Update the human-readable policy files.
5. Synchronize both client templates.
6. Validate model parity and secret safety.
7. Apply locally through a controlled merge.

## Cost schema

The catalog distinguishes two cost fields:

- **`localCostPerMillion`** — verified local operating cost (power, tariff,
  throughput, hardware amortization). Set to `null` explicitly until local
  evidence is collected. Never substitute a hosted provider price here. Rendered
  client templates omit the cost field when this is null.
- **`hostedReferenceCostPerMillion`** — observed hosted/provider pricing, stored
  for comparison only. Must include `source` (URL) and `retrievedDate`. Must
  never be propagated into rendered Pi or OpenCode templates.

Use `costPerMillion` only on models where verified local cost is equal to
hosted price (rare; document the reason). For open-weight self-hosted models
(provider `un/`), local and hosted costs are categorically different.

To supply real local cost data for a `un/` model, update `localCostPerMillion`
with concrete values and document the measurement method in the catalog entry.

## Why templates are not symlinked directly

Pi and OpenCode files commonly contain unrelated local plugins, providers, trust state, and runtime preferences. Direct symlinking can overwrite local intent or couple one machine to repository layout. The default workflow is explicit merge or a future renderer with backups and a dry-run diff.

## Verification layers

Keep these gates separate:

- configuration parses;
- credential resolves;
- model is listed;
- metadata is reported;
- completion succeeds;
- the intended client route is selected.

Passing one layer does not prove the others.
