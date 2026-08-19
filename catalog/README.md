# Model Catalog

## Sources of truth

- `models.json` is the machine-readable catalog used by validation and rendering tools.
- `model-policy.yaml` records human-readable selection and metadata rules.
- `agent-routing.yaml` records role-specific primary and fallback models.

## Update rules

1. Collect fresh authenticated endpoint metadata without storing raw responses.
2. Normalize only public model IDs and explicitly reported metadata.
3. Update `models.json`.
4. Regenerate or update both client templates.
5. Update policy documentation when defaults, exclusions, or routing change.
6. Run `python scripts/validate.py` and the unit tests.

## Capability states

Treat endpoint capability data as three-state:

- `true` — explicitly reported or verified;
- `false` — explicitly unsupported or disproven;
- absent — unknown.

Do not translate absent metadata to `false`, `0`, or a guessed neighboring-model value.

## Image routes

Image-generation routes are individually routable aliases. Keep resolution and aspect-ratio variants even when they share the same family name. Do not mark them as image-input chat models unless the endpoint reports that capability separately.
