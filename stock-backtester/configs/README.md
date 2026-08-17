# Configs and Policies

Purpose
-------

This directory contains repository policy/configuration, not a universal runtime
configuration system yet.

Current files
-------------

- `sacred_scripts.json` — explicitly sacred command paths.
- `reorg_audit_policy.json` — bounded inventory/audit rules.
- `intelligence_storage_policy.json` — intelligence artifact/storage policy.

Defaults and authority
----------------------

Many experiment defaults still come from CLI parsers or implementation constants.
The Phase 4 parameter registry documents provenance but does not replace those
defaults or ingest config files. Do not edit a policy file to change research
behavior without a dedicated review.

See also
--------

- [`docs/reorg/SACRED_WORKFLOWS.md`](../docs/reorg/SACRED_WORKFLOWS.md)
- [`docs/reorg/PARAMETER_CONFIG_REGISTRY.md`](../docs/reorg/PARAMETER_CONFIG_REGISTRY.md)
