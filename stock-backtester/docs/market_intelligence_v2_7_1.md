# Market Intelligence v2.7.1

This patch adds entity-grounded scope correction on top of semantic event
classification.

## Why

The semantic classifier improved event type classification, but scope can still
drift when a sentence is short or vague. For example, a Palantir price-action
sentence could be classified as `commodity` or `peer_group` because embeddings
only see semantic similarity, not ticker identity.

## What changed

- Adds `grounded_scope`.
- Uses ticker/entity aliases to correct low-confidence or incompatible semantic
  scopes.
- Preserves the raw semantic scope in `raw_semantic_scope`.

## Example

`Palantir shares hit a 52-week low...`

Can now be grounded back to:

- `scope=ticker`
- `raw_semantic_scope=peer_group`

This gives us better features while keeping an audit trail.
