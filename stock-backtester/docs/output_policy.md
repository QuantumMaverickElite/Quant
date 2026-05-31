# Output Policy

Generated outputs are ignored by Git.

The main repo should store:

```text
source code
scripts
documentation
configuration
small curated examples if needed
```

The main repo should not store:

```text
large Monte Carlo outputs
per-run folders
spaghetti plots from every experiment
temporary debug outputs
large intermediate matrices
```

## Ignored Output Folders

Common ignored folders include:

```text
outputs/
results/
archive/old_backtests/
src/outputs/
wheelhouse/
__pycache__/
*.egg-info/
```

## Save Modes

The preferred save behavior is:

```text
--save-mode none:
    no files; console output only

--save-mode compact:
    summary CSV + trial CSV + small metadata

--save-mode plots:
    compact files + selected plots

--save-mode full:
    full curves/spaghetti outputs; use intentionally
```

## Disk Rule

The project should optimize algorithms before adding caches.

Caching large arrays should not be the default. With limited disk space, caching can quietly destroy the laptop.

Use this rule:

```text
Optimize algorithm first.
Save compact summaries by default.
Archive important baselines externally.
Only cache large outputs when explicitly needed.
```

## Local Cleanup Commands

Check disk usage:

```bash
du -h outputs --max-depth=3 | sort -h | tail -50
df -h .
```

Remove Python caches:

```bash
find . -type d -name "__pycache__" -prune -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

Check repo status:

```bash
gst
```
