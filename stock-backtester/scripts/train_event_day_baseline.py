#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import json
import pandas as pd
import numpy as np

IN = Path("outputs/intelligence/event_day_impact_dataset.parquet")
OUT_DIR = Path("outputs/intelligence/baseline_reports")
OUT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_parquet(IN).copy()
df = df.sort_values(["event_base_date", "ticker"]).reset_index(drop=True)

target = "target_forward_alpha"

exclude = {
    "ticker",
    "event_base_date",
    "target_forward_alpha",
    "target_forward_return",
    "target_forward_drawdown",
    "target_forward_volatility",
    "target_positive_alpha",
    "target_horizon_days",
}

feature_cols = []
for c in df.columns:
    if c in exclude:
        continue
    if pd.api.types.is_numeric_dtype(df[c]):
        feature_cols.append(c)

work = df.dropna(subset=[target]).copy()
X = work[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
y = work[target].astype(float)

report = {
    "rows": int(len(work)),
    "features": feature_cols,
    "target": target,
    "date_min": str(work["event_base_date"].min()),
    "date_max": str(work["event_base_date"].max()),
    "target_mean": float(y.mean()),
    "target_std": float(y.std()),
}

print("== event-day baseline smoke test ==")
print(f"rows: {len(work)}")
print(f"features: {len(feature_cols)}")
print(f"date range: {report['date_min']} -> {report['date_max']}")
print(f"target mean: {report['target_mean']:.6f}")
print(f"target std: {report['target_std']:.6f}")

corrs = []
for c in feature_cols:
    x = X[c]
    if x.nunique(dropna=True) <= 1:
        continue
    corr = x.corr(y, method="spearman")
    if pd.notna(corr):
        corrs.append((c, float(corr)))

corr_df = pd.DataFrame(corrs, columns=["feature", "spearman_corr"])
corr_df["abs_corr"] = corr_df["spearman_corr"].abs()
corr_df = corr_df.sort_values("abs_corr", ascending=False)

print()
print("== top simple feature correlations ==")
print(corr_df.head(20).to_string(index=False))

corr_path = OUT_DIR / "event_day_feature_correlations.csv"
corr_df.to_csv(corr_path, index=False)
report["correlation_report"] = str(corr_path)

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_absolute_error
    from sklearn.dummy import DummyRegressor

    # Time split, not random split.
    split = max(1, int(len(work) * 0.7))
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    if len(X_test) < 10:
        raise RuntimeError("not enough test rows for meaningful model smoke test")

    dummy = DummyRegressor(strategy="mean")
    dummy.fit(X_train, y_train)
    dummy_pred = dummy.predict(X_test)

    model = RandomForestRegressor(
        n_estimators=80,
        max_depth=3,
        min_samples_leaf=5,
        random_state=42,
    )
    model.fit(X_train, y_train)
    pred = model.predict(X_test)

    dummy_mae = mean_absolute_error(y_test, dummy_pred)
    model_mae = mean_absolute_error(y_test, pred)

    importances = pd.DataFrame({
        "feature": feature_cols,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=False)

    pred_df = work.iloc[split:][["ticker", "event_base_date", target]].copy()
    pred_df["predicted_alpha"] = pred
    pred_df["dummy_predicted_alpha"] = dummy_pred

    pred_path = OUT_DIR / "event_day_baseline_predictions.csv"
    imp_path = OUT_DIR / "event_day_baseline_feature_importance.csv"

    pred_df.to_csv(pred_path, index=False)
    importances.to_csv(imp_path, index=False)

    report.update({
        "sklearn_available": True,
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "dummy_mae": float(dummy_mae),
        "model_mae": float(model_mae),
        "prediction_report": str(pred_path),
        "feature_importance_report": str(imp_path),
    })

    print()
    print("== tiny model smoke test ==")
    print(f"train rows: {len(X_train)}")
    print(f"test rows: {len(X_test)}")
    print(f"dummy MAE: {dummy_mae:.6f}")
    print(f"model MAE: {model_mae:.6f}")
    print()
    print("top feature importances:")
    print(importances.head(20).to_string(index=False))

except Exception as e:
    report.update({
        "sklearn_available": False,
        "model_smoke_error": str(e),
    })
    print()
    print("== model smoke skipped ==")
    print(str(e))

report_path = OUT_DIR / "event_day_baseline_report.json"
report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

print()
print(f"wrote {report_path}")
print(f"wrote {corr_path}")
