# Artifact Policy

Research artifacts should be treated separately from source code.

## Recommended Split

```text
Main code repo:
    code
    scripts
    docs
    configs
    small examples

Private artifact storage:
    compressed baseline archives
    important plots
    selected CSV summaries
    experiment manifests
```

## What To Save

Save important baseline artifacts:

```text
threshold_summary.csv
threshold_trials.csv
selected comparison plots
important spaghetti plots
experiment manifest
input file hashes
dependency versions
code commit hash
```

Do not archive every temporary debug run.

Save only experiments that are meaningful enough to become future baselines.

## Compression Workflow

Example:

```bash
mkdir -p ~/quant_artifacts_to_save

tar -czf ~/quant_artifacts_to_save/rebalance_frequency_baselines_2026-05-31.tar.gz \
  outputs/research/rebalance_frequency \
  outputs/threshold_rebalance/weekly_check_sample24_port5_v1 \
  outputs/threshold_rebalance/weekly_check_sample24_port8_v1 \
  outputs/threshold_rebalance/weekly_check_sample24_port12_v1

du -sh ~/quant_artifacts_to_save/*
```

After confirming the archive is saved externally, remove the local raw folders if needed.

## Storage Targets

Good targets:

```text
private GitHub artifact repo for small archives
Google Drive
external SSD
object storage
```

For large artifacts, avoid dumping everything into the main Git repo.
