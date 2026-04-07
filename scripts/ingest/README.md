# Ingest adapters

Add a module under `adapters/` exporting:

- `id`, `label`, **`CONFIG_SCHEMA`** — document `api_key_env`, `requires`, or `notes` for the integrations wizard (`llm-wiki integrations wizard`).
- `Adapter` subclass with `run(vault, cfg, argv)`
- Optional `setup_checks(cls, cfg_slice) -> list[str]`

Register the class in `adapters/__init__.py` `ADAPTERS`.

Enable/disable in `llm-wiki/config.json` → `integrations.<id>.enabled`.

**Ingestion security** runs after a successful write when `ingestion_security.enabled` in config (`scripts/ingest/security.py`). **`llm-wiki security scan <file>`** re-runs heuristics without re-fetching.
