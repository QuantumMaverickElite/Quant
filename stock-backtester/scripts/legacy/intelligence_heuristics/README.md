# Legacy Intelligence Heuristic Scorers

These scripts were created during the first worker/news intelligence experiments.

They are preserved for reference only.

They should not be used as allocator-facing intelligence because they mix:

- relevance scoring
- heuristic signal usefulness
- allocation-like judgment

The new architecture is:

event facts
-> time-safe outcome labels
-> event impact dataset
-> ML-learned usefulness
-> bounded allocator overlay
