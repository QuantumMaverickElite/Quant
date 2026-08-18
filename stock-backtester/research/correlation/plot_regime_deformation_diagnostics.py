# research/correlation/plot_regime_deformation_diagnostics.py

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot regime-correlation deformation diagnostics."
    )

    parser.add_argument(
        "--deformation",
        default="outputs/correlation/regime_market_deformation.csv",
        help="Market deformation time-series CSV.",
    )

    parser.add_argument(
        "--h5",
        default="outputs/reports/mean_reversion_by_deformation_h5.csv",
        help="5-day deformation-state performance summary.",
    )
    parser.add_argument(
        "--h10",
        default="outputs/reports/mean_reversion_by_deformation_h10.csv",
        help="10-day deformation-state performance summary.",
    )
    parser.add_argument(
        "--h20",
        default="outputs/reports/mean_reversion_by_deformation_h20.csv",
        help="20-day deformation-state performance summary.",
    )

    parser.add_argument(
        "--yearly-h20",
        default="outputs/reports/mean_reversion_by_deformation_yearly_h20.csv",
        help="20-day yearly deformation-state performance summary.",
    )

    parser.add_argument(
        "--bucket-h20",
        default="outputs/reports/mean_reversion_by_compression_bucket_h20.csv",
        help="20-day compression-bucket performance summary.",
    )
    parser.add_argument(
        "--bucket-yearly-h20",
        default="outputs/reports/mean_reversion_by_compression_bucket_h20_by_year.csv",
        help="20-day yearly compression-bucket performance summary.",
    )

    parser.add_argument(
        "--out-dir",
        default="outputs/reports/plots/regime_deformation",
        help="Directory for generated plots.",
    )

    return parser.parse_args()


def save_market_compression_plot(
    deformation: pd.DataFrame,
    out_dir: Path,
) -> None:
    df = deformation.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    plt.figure(figsize=(14, 6))
    plt.plot(df["date"], df["market_compression_score"], linewidth=1.5)
    plt.axhline(0.0, linewidth=1)
    plt.axhline(0.05, linestyle="--", linewidth=1)
    plt.axhline(-0.05, linestyle="--", linewidth=1)
    plt.title("Market Correlation Deformation Over Time")
    plt.xlabel("Date")
    plt.ylabel("Market Compression Score")
    plt.tight_layout()

    out_path = out_dir / "market_compression_score_over_time.png"
    plt.savefig(out_path, dpi=160)
    plt.close()

    print(f"Saved {out_path}")


def save_state_counts_plot(
    deformation: pd.DataFrame,
    out_dir: Path,
) -> None:
    counts = deformation["compression_state"].value_counts().sort_values(ascending=True)

    plt.figure(figsize=(10, 6))
    plt.barh(counts.index.astype(str), counts.values)
    plt.title("Compression State Counts")
    plt.xlabel("Observation Count")
    plt.ylabel("Compression State")
    plt.tight_layout()

    out_path = out_dir / "compression_state_counts.png"
    plt.savefig(out_path, dpi=160)
    plt.close()

    print(f"Saved {out_path}")


def save_horizon_bar_plot(
    h5: pd.DataFrame,
    h10: pd.DataFrame,
    h20: pd.DataFrame,
    out_dir: Path,
) -> None:
    frames: list[pd.DataFrame] = []

    for horizon, df in [(5, h5), (10, h10), (20, h20)]:
        temp = df[
            [
                "compression_state",
                "avg_return",
                "win_rate",
                "trades",
            ]
        ].copy()
        temp["horizon"] = horizon
        frames.append(temp)

    combined = pd.concat(frames, ignore_index=True)

    pivot = combined.pivot(
        index="compression_state",
        columns="horizon",
        values="avg_return",
    )

    preferred_order = [
        "BROAD_COMPRESSION",
        "MODERATE_COMPRESSION",
        "STABLE",
        "MODERATE_FRAGMENTATION",
        "BROAD_FRAGMENTATION",
    ]

    pivot = pivot.reindex([state for state in preferred_order if state in pivot.index])

    ax = pivot.plot(kind="bar", figsize=(12, 6))
    ax.axhline(0.0, linewidth=1)
    ax.set_title("Mean-Reversion Average Return by Deformation State")
    ax.set_xlabel("Compression State")
    ax.set_ylabel("Average Strategy Return")
    plt.xticks(rotation=35, ha="right")
    plt.tight_layout()

    out_path = out_dir / "avg_return_by_deformation_state_horizons.png"
    plt.savefig(out_path, dpi=160)
    plt.close()

    print(f"Saved {out_path}")


def save_yearly_h20_plot(
    yearly: pd.DataFrame,
    out_dir: Path,
) -> None:
    df = yearly.copy()

    pivot = df.pivot(
        index="year",
        columns="compression_state",
        values="avg_return",
    )

    preferred_cols = [
        "BROAD_COMPRESSION",
        "MODERATE_COMPRESSION",
        "STABLE",
        "MODERATE_FRAGMENTATION",
        "BROAD_FRAGMENTATION",
    ]

    pivot = pivot[[col for col in preferred_cols if col in pivot.columns]]

    ax = pivot.plot(kind="bar", figsize=(14, 7))
    ax.axhline(0.0, linewidth=1)
    ax.set_title("20-Day Mean-Reversion Average Return by Year and Deformation State")
    ax.set_xlabel("Year")
    ax.set_ylabel("Average Strategy Return")
    plt.xticks(rotation=0)
    plt.tight_layout()

    out_path = out_dir / "yearly_h20_avg_return_by_deformation_state.png"
    plt.savefig(out_path, dpi=160)
    plt.close()

    print(f"Saved {out_path}")


def save_bucket_h20_plot(
    bucket_h20: pd.DataFrame,
    out_dir: Path,
) -> None:
    df = bucket_h20.copy()
    df = df.sort_values("avg_return", ascending=True)

    labels = [
        f"{row.compression_bucket}\nN={int(row.trades)}"
        for row in df.itertuples(index=False)
    ]

    plt.figure(figsize=(10, 6))
    plt.barh(labels, df["avg_return"])
    plt.axvline(0.0, linewidth=1)
    plt.title("20-Day Mean-Reversion Return by Compression Bucket")
    plt.xlabel("Average Strategy Return")
    plt.ylabel("Compression Bucket")
    plt.tight_layout()

    out_path = out_dir / "h20_avg_return_by_compression_bucket.png"
    plt.savefig(out_path, dpi=160)
    plt.close()

    print(f"Saved {out_path}")


def save_yearly_bucket_h20_plot(
    yearly_bucket_h20: pd.DataFrame,
    out_dir: Path,
) -> None:
    df = yearly_bucket_h20.copy()

    pivot = df.pivot(
        index="year",
        columns="compression_bucket",
        values="avg_return",
    )

    preferred_cols = [
        "COMPRESSION",
        "STABLE",
        "FRAGMENTATION",
    ]

    pivot = pivot[[col for col in preferred_cols if col in pivot.columns]]

    ax = pivot.plot(kind="bar", figsize=(14, 7))
    ax.axhline(0.0, linewidth=1)
    ax.set_title("20-Day Mean-Reversion Return by Year and Compression Bucket")
    ax.set_xlabel("Year")
    ax.set_ylabel("Average Strategy Return")
    plt.xticks(rotation=0)
    plt.tight_layout()

    out_path = out_dir / "yearly_h20_avg_return_by_compression_bucket.png"
    plt.savefig(out_path, dpi=160)
    plt.close()

    print(f"Saved {out_path}")


def save_yearly_bucket_trade_count_plot(
    yearly_bucket_h20: pd.DataFrame,
    out_dir: Path,
) -> None:
    df = yearly_bucket_h20.copy()

    pivot = df.pivot(
        index="year",
        columns="compression_bucket",
        values="trades",
    )

    preferred_cols = [
        "COMPRESSION",
        "STABLE",
        "FRAGMENTATION",
    ]

    pivot = pivot[[col for col in preferred_cols if col in pivot.columns]]

    ax = pivot.plot(kind="bar", figsize=(14, 7))
    ax.set_title("20-Day Trade Counts by Year and Compression Bucket")
    ax.set_xlabel("Year")
    ax.set_ylabel("Trade Count")
    plt.xticks(rotation=0)
    plt.tight_layout()

    out_path = out_dir / "yearly_h20_trade_counts_by_compression_bucket.png"
    plt.savefig(out_path, dpi=160)
    plt.close()

    print(f"Saved {out_path}")


def save_bucket_win_rate_plot(
    bucket_h20: pd.DataFrame,
    out_dir: Path,
) -> None:
    df = bucket_h20.copy()
    df = df.sort_values("win_rate", ascending=True)

    labels = [
        f"{row.compression_bucket}\nN={int(row.trades)}"
        for row in df.itertuples(index=False)
    ]

    plt.figure(figsize=(10, 6))
    plt.barh(labels, df["win_rate"])
    plt.axvline(0.5, linewidth=1)
    plt.title("20-Day Win Rate by Compression Bucket")
    plt.xlabel("Win Rate")
    plt.ylabel("Compression Bucket")
    plt.tight_layout()

    out_path = out_dir / "h20_win_rate_by_compression_bucket.png"
    plt.savefig(out_path, dpi=160)
    plt.close()

    print(f"Saved {out_path}")


def main() -> None:
    args = parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    deformation = pd.read_csv(args.deformation)

    h5 = pd.read_csv(args.h5)
    h10 = pd.read_csv(args.h10)
    h20 = pd.read_csv(args.h20)

    yearly_h20 = pd.read_csv(args.yearly_h20)

    bucket_h20 = pd.read_csv(args.bucket_h20)
    bucket_yearly_h20 = pd.read_csv(args.bucket_yearly_h20)

    save_market_compression_plot(deformation, out_dir)
    save_state_counts_plot(deformation, out_dir)

    save_horizon_bar_plot(h5, h10, h20, out_dir)
    save_yearly_h20_plot(yearly_h20, out_dir)

    save_bucket_h20_plot(bucket_h20, out_dir)
    save_bucket_win_rate_plot(bucket_h20, out_dir)
    save_yearly_bucket_h20_plot(bucket_yearly_h20, out_dir)
    save_yearly_bucket_trade_count_plot(bucket_yearly_h20, out_dir)


if __name__ == "__main__":
    main()
