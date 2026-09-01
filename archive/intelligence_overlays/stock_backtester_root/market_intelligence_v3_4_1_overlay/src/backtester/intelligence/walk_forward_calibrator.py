from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .calibration_dataset import feature_columns
from .candidates import detect_date_column, detect_ticker_column, read_table, write_table
from .weight_calibrator import logistic_fit, ridge_fit, sigmoid


@dataclass(frozen=True)
class WalkForwardConfig:
    target_col: str
    date_col: str
    ticker_col: str
    baseline_confidence_col: str = "allocator_confidence_pre_intelligence"
    heuristic_confidence_col: str = "allocator_confidence_intelligence_adjusted"
    model_type: str = "logistic"
    alpha: float = 10.0
    train_days: int = 252
    test_days: int = 5
    step_days: int = 5
    embargo_days: int = 20
    min_train_rows: int = 200
    min_test_rows: int = 5
    min_multiplier: float = 0.70
    max_multiplier: float = 1.15
    rolling_train: bool = False


BASELINE_CONFIDENCE_CANDIDATES = (
    "allocator_confidence_pre_intelligence",
    "adjusted_confidence_pre_intelligence",
    "adjusted_confidence",
    "confidence",
)

HEURISTIC_CONFIDENCE_CANDIDATES = (
    "allocator_confidence_intelligence_adjusted",
    "adjusted_confidence_intelligence_adjusted",
    "allocator_confidence_pre_intelligence",
    "adjusted_confidence_pre_intelligence",
    "adjusted_confidence",
    "confidence",
)


def resolve_confidence_column(df: pd.DataFrame, requested: str | None, candidates: tuple[str, ...], label: str) -> str:
    if requested:
        if requested not in df.columns:
            raise ValueError(f"{label} confidence column not found: {requested}")
        return requested
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    raise ValueError(f"Could not detect {label} confidence column. Tried: {', '.join(candidates)}")


def _numeric_series(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce")


def _fit_feature_transform(train: pd.DataFrame, features: list[str]) -> tuple[list[str], dict[str, float], dict[str, float], dict[str, float]]:
    kept: list[str] = []
    impute: dict[str, float] = {}
    mean: dict[str, float] = {}
    std: dict[str, float] = {}

    for feature in features:
        series = _numeric_series(train, feature)
        if series.notna().sum() == 0:
            continue
        fill = float(series.median())
        if np.isnan(fill):
            fill = 0.0
        filled = series.fillna(fill)
        mu = float(filled.mean())
        sigma = float(filled.std(ddof=0))
        if not sigma or np.isnan(sigma):
            sigma = 1.0
        kept.append(feature)
        impute[feature] = fill
        mean[feature] = mu
        std[feature] = sigma
    return kept, impute, mean, std


def _transform(df: pd.DataFrame, features: list[str], impute: dict[str, float], mean: dict[str, float], std: dict[str, float]) -> np.ndarray:
    cols: list[np.ndarray] = []
    for feature in features:
        values = _numeric_series(df, feature).fillna(impute[feature]).to_numpy(dtype=float)
        cols.append((values - mean[feature]) / std[feature])
    if not cols:
        return np.empty((len(df), 0), dtype=float)
    return np.column_stack(cols)


def _fit_fold(train: pd.DataFrame, features: list[str], cfg: WalkForwardConfig) -> dict | None:
    train = train.dropna(subset=[cfg.target_col]).copy()
    if len(train) < cfg.min_train_rows:
        return None

    kept, impute, mean, std = _fit_feature_transform(train, features)
    if not kept:
        return None

    x_std = _transform(train, kept, impute, mean, std)
    x = np.column_stack([np.ones(len(x_std)), x_std])
    y = _numeric_series(train, cfg.target_col).to_numpy(dtype=float)

    if cfg.model_type == "ridge":
        beta = ridge_fit(x, y, alpha=cfg.alpha)
        train_score = x @ beta
        center = float(np.nanmean(train_score))
        scale = float(np.nanstd(train_score)) or 1.0
        train_probability = sigmoid((train_score - center) / scale)
    else:
        beta = logistic_fit(x, y, alpha=cfg.alpha)
        train_score = x @ beta
        train_probability = sigmoid(train_score)
        center = float(np.nanmean(train_probability))
        scale = 1.0

    return {
        "features": kept,
        "impute": impute,
        "mean": mean,
        "std": std,
        "beta": beta,
        "center": center,
        "scale": scale,
        "target_mean": float(np.nanmean(y)),
        "train_rows": int(len(train)),
    }


def _predict_fold(test: pd.DataFrame, fit: dict, cfg: WalkForwardConfig) -> pd.DataFrame:
    out = test.copy()
    x_std = _transform(out, fit["features"], fit["impute"], fit["mean"], fit["std"])
    x = np.column_stack([np.ones(len(x_std)), x_std])
    raw_score = x @ fit["beta"]

    if cfg.model_type == "ridge":
        centered_score = (raw_score - fit["center"]) / fit["scale"]
        probability = sigmoid(centered_score)
        centered = centered_score
    else:
        probability = sigmoid(raw_score)
        centered = probability - fit["center"]

    multiplier = np.clip(1.0 + 0.10 * centered, cfg.min_multiplier, cfg.max_multiplier)
    base = _numeric_series(out, cfg.baseline_confidence_col).fillna(0.0)
    out["walk_forward_ml_raw_score"] = raw_score
    out["walk_forward_ml_probability"] = probability
    out["walk_forward_ml_multiplier"] = multiplier
    out["allocator_confidence_walk_forward_ml_adjusted"] = base * multiplier
    out["walk_forward_train_rows"] = fit["train_rows"]
    out["walk_forward_target_mean"] = fit["target_mean"]
    out["walk_forward_feature_count"] = len(fit["features"])
    return out


def walk_forward_predict(
    df: pd.DataFrame,
    cfg: WalkForwardConfig,
    features: list[str] | None = None,
) -> pd.DataFrame:
    data = df.copy()
    data["_wf_date"] = pd.to_datetime(data[cfg.date_col], errors="coerce")
    data = data.dropna(subset=["_wf_date"]).sort_values("_wf_date")
    if cfg.target_col not in data.columns:
        raise ValueError(f"Target column not found: {cfg.target_col}")
    if cfg.baseline_confidence_col not in data.columns:
        raise ValueError(f"Baseline confidence column not found: {cfg.baseline_confidence_col}")

    features = features or feature_columns(data)
    features = [feature for feature in features if feature in data.columns and feature != cfg.target_col]
    if not features:
        raise ValueError("No usable candidate feature columns.")

    min_date = data["_wf_date"].min().normalize()
    max_date = data["_wf_date"].max().normalize()
    first_test_start = min_date + pd.Timedelta(days=cfg.train_days + cfg.embargo_days)

    predictions: list[pd.DataFrame] = []
    fold_id = 0
    test_start = first_test_start
    while test_start <= max_date:
        test_end = test_start + pd.Timedelta(days=cfg.test_days)
        train_end = test_start - pd.Timedelta(days=cfg.embargo_days)
        if cfg.rolling_train:
            train_start = train_end - pd.Timedelta(days=cfg.train_days)
            train = data[(data["_wf_date"].ge(train_start)) & (data["_wf_date"].lt(train_end))]
        else:
            train = data[data["_wf_date"].lt(train_end)]
        test = data[(data["_wf_date"].ge(test_start)) & (data["_wf_date"].lt(test_end))]

        if len(test) >= cfg.min_test_rows:
            fit = _fit_fold(train, features, cfg)
            if fit is not None:
                pred = _predict_fold(test, fit, cfg)
                pred["walk_forward_fold"] = fold_id
                pred["walk_forward_train_end"] = train_end
                pred["walk_forward_test_start"] = test_start
                pred["walk_forward_test_end"] = test_end
                predictions.append(pred)
                fold_id += 1

        test_start += pd.Timedelta(days=cfg.step_days)

    if not predictions:
        return pd.DataFrame(columns=list(df.columns) + ["walk_forward_fold"])
    return pd.concat(predictions, ignore_index=True).drop(columns=["_wf_date"], errors="ignore")


def ranking_summary(
    predictions: pd.DataFrame,
    *,
    date_col: str,
    ticker_col: str,
    return_col: str,
    top_ns: tuple[int, ...],
    cash: float = 10_000.0,
    baseline_confidence_col: str = "allocator_confidence_pre_intelligence",
    heuristic_confidence_col: str = "allocator_confidence_intelligence_adjusted",
    ml_confidence_col: str = "allocator_confidence_walk_forward_ml_adjusted",
    drawdown_col: str | None = None,
) -> pd.DataFrame:
    if predictions.empty:
        return pd.DataFrame()
    if return_col not in predictions.columns:
        raise ValueError(f"Return column not found: {return_col}")

    data = predictions.copy()
    data["_rank_date"] = pd.to_datetime(data[date_col], errors="coerce")
    data["_rank_return"] = pd.to_numeric(data[return_col], errors="coerce")
    rankings = [
        ("baseline", baseline_confidence_col),
        ("heuristic_nlp", heuristic_confidence_col),
        ("walk_forward_ml", ml_confidence_col),
    ]
    rows: list[dict] = []
    for top_n in top_ns:
        per_ranking: dict[str, list[dict]] = {name: [] for name, _ in rankings}
        for _, day in data.dropna(subset=["_rank_date"]).groupby("_rank_date"):
            for name, rank_col in rankings:
                if rank_col not in day.columns:
                    continue
                picks = (
                    day.sort_values(rank_col, ascending=False)
                    .drop_duplicates(ticker_col)
                    .head(top_n)
                    .copy()
                )
                if picks.empty:
                    continue
                item = {
                    "mean_return": float(picks["_rank_return"].mean()),
                    "hit_rate": float((picks["_rank_return"] > 0).mean()),
                    "selection_count": int(len(picks)),
                }
                if drawdown_col and drawdown_col in picks.columns:
                    item["avg_drawdown"] = float(pd.to_numeric(picks[drawdown_col], errors="coerce").mean())
                per_ranking[name].append(item)

        baseline_return = np.nan
        for name, _ in rankings:
            items = per_ranking.get(name, [])
            if not items:
                continue
            mean_return = float(np.nanmean([x["mean_return"] for x in items]))
            if name == "baseline":
                baseline_return = mean_return
            row = {
                "return_col": return_col,
                "top_n": top_n,
                "ranking": name,
                "test_windows": len(items),
                "mean_return": mean_return,
                "cash_pnl": cash * mean_return,
                "vs_baseline_cash": cash * (mean_return - baseline_return) if not np.isnan(baseline_return) else 0.0,
                "hit_rate": float(np.nanmean([x["hit_rate"] for x in items])),
                "avg_selection_count": float(np.nanmean([x["selection_count"] for x in items])),
            }
            if drawdown_col and any("avg_drawdown" in x for x in items):
                avg_drawdown = float(np.nanmean([x.get("avg_drawdown", np.nan) for x in items]))
                row["avg_drawdown"] = avg_drawdown
                row["cash_avg_drawdown"] = cash * avg_drawdown
            rows.append(row)
    return pd.DataFrame(rows)


def run_walk_forward_calibration(
    *,
    dataset_path: str | Path,
    predictions_out: str | Path,
    summary_out: str | Path | None,
    target_col: str,
    return_cols: tuple[str, ...],
    top_ns: tuple[int, ...],
    cash: float = 10_000.0,
    ticker_col: str | None = None,
    date_col: str | None = None,
    baseline_confidence_col: str | None = None,
    heuristic_confidence_col: str | None = None,
    model_type: str = "logistic",
    alpha: float = 10.0,
    train_days: int = 252,
    test_days: int = 5,
    step_days: int = 5,
    embargo_days: int = 20,
    min_train_rows: int = 200,
    min_test_rows: int = 5,
    rolling_train: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = read_table(dataset_path)
    ticker = detect_ticker_column(df, ticker_col)
    date = detect_date_column(df, date_col)
    if date is None:
        raise ValueError("Could not detect date column.")
    baseline_col = resolve_confidence_column(df, baseline_confidence_col, BASELINE_CONFIDENCE_CANDIDATES, "baseline")
    heuristic_col = resolve_confidence_column(df, heuristic_confidence_col, HEURISTIC_CONFIDENCE_CANDIDATES, "heuristic")

    cfg = WalkForwardConfig(
        target_col=target_col,
        date_col=date,
        ticker_col=ticker,
        baseline_confidence_col=baseline_col,
        heuristic_confidence_col=heuristic_col,
        model_type=model_type,
        alpha=alpha,
        train_days=train_days,
        test_days=test_days,
        step_days=step_days,
        embargo_days=embargo_days,
        min_train_rows=min_train_rows,
        min_test_rows=min_test_rows,
        rolling_train=rolling_train,
    )
    predictions = walk_forward_predict(df, cfg)
    write_table(predictions, predictions_out)

    drawdown_col = None
    for candidate in ("max_drawdown_next_10d", "max_drawdown_next_20d", "max_drawdown_next_5d"):
        if candidate in predictions.columns:
            drawdown_col = candidate
            break

    summaries = [
        ranking_summary(
            predictions,
            date_col=date,
            ticker_col=ticker,
            return_col=return_col,
            top_ns=top_ns,
            cash=cash,
            baseline_confidence_col=baseline_col,
            heuristic_confidence_col=heuristic_col,
            drawdown_col=drawdown_col,
        )
        for return_col in return_cols
        if return_col in predictions.columns
    ]
    summary = pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame()
    if summary_out:
        write_table(summary, summary_out)
    return predictions, summary
