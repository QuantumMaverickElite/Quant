# Market Intelligence v5.2.1 - SEC Official Source Policy

This small overlay extends v5.2 provider policy so SEC EDGAR filings are treated as official high-trust sources.

## What Changed

- `src/backtester/intelligence/provider_policy.py`
  - Adds `is_official_source` to `ProviderPolicy`.
  - Adds `sec_edgar_submissions` as an official provider.
  - Adds aliases: `sec`, `sec_edgar`, `edgar`.
  - Adds `company_investor_relations` as a future official provider.

- `src/backtester/intelligence/sec_source_collector.py`
  - Writes provider-policy metadata into newly fetched SEC JSONL rows.

## Apply

```bash
cp market_intelligence_v5_2_1_sec_policy_overlay/src/backtester/intelligence/provider_policy.py src/backtester/intelligence/provider_policy.py
cp market_intelligence_v5_2_1_sec_policy_overlay/src/backtester/intelligence/sec_source_collector.py src/backtester/intelligence/sec_source_collector.py
cp market_intelligence_v5_2_1_sec_policy_overlay/docs/market_intelligence_v5_2_1_sec_policy.md docs/market_intelligence_v5_2_1_sec_policy.md
python -m compileall -q src/backtester/intelligence/provider_policy.py src/backtester/intelligence/sec_source_collector.py
```

## Expected Policy

- SEC EDGAR: allowed for `ml_training`, `backtesting`, `live_scoring`, and `storage`.
- SEC EDGAR: `is_official_source=true`.
- GDELT: still blocked from `ml_training` by default.
- NewsAPI: still blocked from `ml_training` by default unless you intentionally change the policy for a licensed plan.
