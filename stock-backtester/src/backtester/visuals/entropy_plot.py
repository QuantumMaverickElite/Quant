from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_price_and_entropy(
    df: pd.DataFrame,
    ticker: str | None = None,
    price_col: str = "close",
    entropy_col: str = "normalized_entropy",
    percentile_col: str = "entropy_percentile",
    output_path: str | Path | None = None,
):
    if price_col not in df.columns:
        raise ValueError(f"Missing required price column: {price_col}")

    if entropy_col not in df.columns:
        raise ValueError(f"Missing required entropy column: {entropy_col}")

    if percentile_col not in df.columns:
        raise ValueError(f"Missing required percentile column: {percentile_col}")

    plot_df = df[[price_col, entropy_col, percentile_col]].dropna().copy()

    if plot_df.empty:
        raise ValueError("No non-null rows available for entropy plotting.")

    fig, (ax_price, ax_entropy, ax_percentile) = plt.subplots(
        3,
        1,
        figsize=(13, 9),
        sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1, 1]},
    )

    title = f"{ticker} Price and Entropy" if ticker else "Price and Entropy"

    # -----------------------------
    # Top panel: price
    # -----------------------------
    ax_price.plot(plot_df.index, plot_df[price_col])
    ax_price.set_title(title)
    ax_price.set_ylabel("Price")
    ax_price.grid(True, alpha=0.3)

    # -----------------------------
    # Middle panel: normalized entropy
    # -----------------------------
    ax_entropy.plot(plot_df.index, plot_df[entropy_col])
    ax_entropy.set_ylabel("Normalized\nEntropy")
    ax_entropy.set_ylim(0, 1)
    ax_entropy.grid(True, alpha=0.3)

    # -----------------------------
    # Bottom panel: entropy percentile
    # -----------------------------
    ax_percentile.axhspan(0.00, 0.25, alpha=0.10, label="LOW")
    ax_percentile.axhspan(0.25, 0.75, alpha=0.05, label="NORMAL")
    ax_percentile.axhspan(0.75, 0.90, alpha=0.10, label="HIGH")
    ax_percentile.axhspan(0.90, 1.00, alpha=0.15, label="EXTREME")

    ax_percentile.plot(plot_df.index, plot_df[percentile_col])

    ax_percentile.axhline(0.25, linestyle="--", linewidth=1)
    ax_percentile.axhline(0.75, linestyle="--", linewidth=1)
    ax_percentile.axhline(0.90, linestyle="--", linewidth=1)

    ax_percentile.set_ylabel("Entropy\nPercentile")
    ax_percentile.set_xlabel("Date")
    ax_percentile.set_ylim(0, 1)
    ax_percentile.grid(True, alpha=0.3)

    ax_percentile.text(
        plot_df.index[-1],
        0.125,
        "LOW",
        va="center",
        ha="right",
        fontsize=8,
    )

    ax_percentile.text(
        plot_df.index[-1],
        0.50,
        "NORMAL",
        va="center",
        ha="right",
        fontsize=8,
    )

    ax_percentile.text(
        plot_df.index[-1],
        0.825,
        "HIGH",
        va="center",
        ha="right",
        fontsize=8,
    )

    ax_percentile.text(
        plot_df.index[-1],
        0.95,
        "EXTREME",
        va="center",
        ha="right",
        fontsize=8,
    )

    fig.tight_layout()

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches="tight")

    return fig
