# Combined-signal research

This family compares allocator and signal behavior across baseline, heuristic
intelligence, ML intelligence, ranking, and related adjustment layers. It is
research analysis, not reusable implementation or allocator authority.

Current scripts:

- `compare_allocator_intelligence.py` — compares pre/post intelligence
  top-N allocator results.
- `compare_allocator_rankings.py` — compares arbitrary ranking columns across
  return horizons and portfolio sizes.
- `diagnose_allocator_intelligence.py` — writes a focused pre/post allocator
  diagnostic report.

Future combined-signal ablations may join this directory after their output and
command contracts are verified.
