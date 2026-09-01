from __future__ import annotations

from pathlib import Path

import pandas as pd

from .candidates import read_table


DEFAULT_SCORE_COLS = [
    "allocator_confidence_pre_intelligence",
    "allocator_confidence_intelligence_adjusted",
    "adjusted_confidence",
    "adjusted_confidence_intelligence_adjusted",
]


def evaluated_rows(df: pd.DataFrame) -> pd.DataFrame:
    if "intelligence_action_label" not in df.columns:
        return df.copy()
    return df[
        ~df["intelligence_action_label"].isin(
            ["not_evaluated_historical_row", "intelligence_missing_not_evaluated"]
        )
    ].copy()


def _first_existing(df: pd.DataFrame, cols: list[str]) -> str | None:
    return next((col for col in cols if col in df.columns), None)


def allocator_summary(
    *,
    signals_path: str | Path,
    top_n: int = 25,
    return_col: str | None = None,
) -> dict[str, pd.DataFrame | pd.Series | str | None]:
    df = read_table(signals_path)
    evaluated = evaluated_rows(df)

    pre_col = _first_existing(
        evaluated,
        ["allocator_confidence_pre_intelligence", "adjusted_confidence"],
    )
    post_col = _first_existing(
        evaluated,
        ["allocator_confidence_intelligence_adjusted", "adjusted_confidence_intelligence_adjusted"],
    )
    if pre_col is None or post_col is None:
        raise ValueError("Could not find pre/post allocator confidence columns")

    cols = [
        col
        for col in [
            "date",
            "ticker",
            "intelligence_action_label",
            pre_col,
            post_col,
            "allocator_confidence_delta",
            "regime_break_score",
            "price_action_risk",
            "sentiment_score",
            "event_opportunity_score",
            "event_downside_risk_score",
            "event_opportunity_multiplier",
            "event_downside_multiplier",
            "net_event_multiplier",
            "dominant_pressure",
        ]
        if col in evaluated.columns
    ]

    top_pre = evaluated.sort_values(pre_col, ascending=False).head(top_n)[cols]
    top_post = evaluated.sort_values(post_col, ascending=False).head(top_n)[cols]

    boosted = evaluated[evaluated.get("net_event_multiplier", 1.0) > 1.0]
    boosted = boosted.sort_values("net_event_multiplier", ascending=False).head(top_n)[cols]

    penalized = evaluated[evaluated.get("net_event_multiplier", 1.0) < 1.0]
    penalized = penalized.sort_values("net_event_multiplier", ascending=True).head(top_n)[cols]

    action_counts = (
        evaluated["intelligence_action_label"].value_counts(dropna=False)
        if "intelligence_action_label" in evaluated.columns
        else pd.Series(dtype="int64")
    )

    diagnostics: dict[str, pd.DataFrame | pd.Series | str | None] = {
        "pre_col": pre_col,
        "post_col": post_col,
        "action_counts": action_counts,
        "top_pre": top_pre,
        "top_post": top_post,
        "boosted": boosted,
        "penalized": penalized,
        "return_compare": None,
    }

    if return_col and return_col in evaluated.columns:
        diagnostics["return_compare"] = compare_topn_return(
            evaluated,
            pre_col=pre_col,
            post_col=post_col,
            return_col=return_col,
            top_n=top_n,
        )

    return diagnostics


def compare_topn_return(
    df: pd.DataFrame,
    *,
    pre_col: str,
    post_col: str,
    return_col: str,
    top_n: int,
) -> pd.DataFrame:
    group_cols = ["date"] if "date" in df.columns else []

    if not group_cols:
        pre = df.sort_values(pre_col, ascending=False).head(top_n)
        post = df.sort_values(post_col, ascending=False).head(top_n)
        return pd.DataFrame(
            [
                {
                    "portfolio": "pre_intelligence",
                    "rows": len(pre),
                    "mean_forward_return": pre[return_col].mean(),
                    "median_forward_return": pre[return_col].median(),
                },
                {
                    "portfolio": "post_intelligence",
                    "rows": len(post),
                    "mean_forward_return": post[return_col].mean(),
                    "median_forward_return": post[return_col].median(),
                },
            ]
        )

    rows = []
    for date, sub in df.groupby(group_cols[0], dropna=False):
        pre = sub.sort_values(pre_col, ascending=False).head(top_n)
        post = sub.sort_values(post_col, ascending=False).head(top_n)
        rows.append(
            {
                "date": date,
                "pre_return": pre[return_col].mean(),
                "post_return": post[return_col].mean(),
                "pre_count": len(pre),
                "post_count": len(post),
            }
        )

    out = pd.DataFrame(rows).sort_values("date")
    if len(out) > 0:
        out["post_minus_pre"] = out["post_return"] - out["pre_return"]
        out["pre_equity"] = (1.0 + out["pre_return"].fillna(0.0)).cumprod()
        out["post_equity"] = (1.0 + out["post_return"].fillna(0.0)).cumprod()
        out["pre_drawdown"] = out["pre_equity"] / out["pre_equity"].cummax() - 1.0
        out["post_drawdown"] = out["post_equity"] / out["post_equity"].cummax() - 1.0
    return out


def write_text_report(diagnostics: dict[str, pd.DataFrame | pd.Series | str | None], path: str | Path) -> None:
    lines: list[str] = []
    lines.append("Allocator Intelligence Diagnostics")
    lines.append("")
    lines.append(f"Pre column: {diagnostics['pre_col']}")
    lines.append(f"Post column: {diagnostics['post_col']}")
    lines.append("")

    action_counts = diagnostics.get("action_counts")
    if isinstance(action_counts, pd.Series) and len(action_counts):
        lines.append("Action Counts")
        lines.append(action_counts.to_string())
        lines.append("")

    for title, key in [
        ("Top Pre-Intelligence", "top_pre"),
        ("Top Post-Intelligence", "top_post"),
        ("Largest Event Boosts", "boosted"),
        ("Largest Event Penalties", "penalized"),
        ("Return Comparison", "return_compare"),
    ]:
        value = diagnostics.get(key)
        if isinstance(value, pd.DataFrame) and len(value):
            lines.append(title)
            lines.append(value.to_string(index=False))
            lines.append("")

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")
