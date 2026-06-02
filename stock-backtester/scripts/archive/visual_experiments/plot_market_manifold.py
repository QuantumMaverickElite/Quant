# scripts/plot_market_manifold.py

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create static 3D market manifold snapshots. "
            "Rolling correlations define the moving fabric; peer-spread signals become valleys/spikes."
        )
    )
    parser.add_argument("--returns-meta", required=True)
    parser.add_argument("--signals", required=True)
    parser.add_argument("--date", required=True, help="Snapshot date, YYYY-MM-DD. Uses nearest prior signal date.")
    parser.add_argument("--out-dir", required=True)

    parser.add_argument("--lookback", type=int, default=126)
    parser.add_argument("--forward-days", type=int, default=60)
    parser.add_argument("--top-signals", type=int, default=8)
    parser.add_argument("--max-nodes", type=int, default=120)
    parser.add_argument("--min-edge-corr", type=float, default=0.65)
    parser.add_argument(
        "--z-mode",
        choices=["peer_spread_z", "forward_return"],
        default="peer_spread_z",
        help="3D height. peer_spread_z shows signal valleys/spikes; forward_return shows realized payoff surface.",
    )
    return parser.parse_args()


def load_returns(meta_path: Path) -> tuple[np.ndarray, dict]:
    meta = json.loads(meta_path.read_text())
    dtype = np.float32 if meta["dtype"] == "float32" else np.float64
    arr = np.fromfile(meta_path.parent / meta["binary_file"], dtype=dtype)
    arr = arr.reshape(int(meta["rows"]), int(meta["cols"])).astype(np.float32, copy=False)
    return arr, meta


def nearest_prior_date(dates: pd.Series, requested: pd.Timestamp) -> pd.Timestamp:
    eligible = dates[dates <= requested]
    if eligible.empty:
        raise ValueError(f"No signal dates on or before {requested.date()}.")
    return eligible.max()


def classical_mds_from_corr(corr: np.ndarray, dims: int = 2) -> np.ndarray:
    corr = np.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0)
    corr = np.clip(corr, -0.999, 0.999)

    dist = np.sqrt(0.5 * (1.0 - corr))
    dist2 = dist ** 2

    n = dist.shape[0]
    center = np.eye(n) - np.ones((n, n)) / n
    gram = -0.5 * center @ dist2 @ center

    vals, vecs = np.linalg.eigh(gram)
    order = np.argsort(vals)[::-1]
    vals = vals[order]
    vecs = vecs[:, order]

    vals = np.maximum(vals[:dims], 0.0)
    coords = vecs[:, :dims] * np.sqrt(vals + 1e-12)
    return coords


def build_node_set(signals_on_date: pd.DataFrame, top_signals: int, max_nodes: int) -> tuple[list[str], set[str]]:
    selected = (
        signals_on_date.sort_values("adjusted_confidence", ascending=False)
        .head(top_signals)
        .copy()
    )

    signal_tickers = set(selected["ticker"].astype(str).str.upper())
    nodes: list[str] = []

    def add(ticker: str) -> None:
        ticker = str(ticker).upper()
        if ticker and ticker not in nodes:
            nodes.append(ticker)

    for _, row in selected.iterrows():
        add(row["ticker"])
        peers = str(row.get("peer_list", "")).split("|")
        for peer in peers:
            add(peer)

    return nodes[:max_nodes], signal_tickers


def main() -> None:
    args = parse_args()

    returns_meta = Path(args.returns_meta)
    signals_path = Path(args.signals)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    returns, meta = load_returns(returns_meta)
    all_dates = pd.to_datetime(meta["dates"])
    tickers = [str(t).upper() for t in meta["tickers"]]
    ticker_to_idx = {t: i for i, t in enumerate(tickers)}

    signals = pd.read_parquet(signals_path)
    signals["date"] = pd.to_datetime(signals["date"])
    signals["ticker"] = signals["ticker"].astype(str).str.upper()

    requested = pd.Timestamp(args.date)
    snapshot_date = nearest_prior_date(signals["date"], requested)
    signals_on_date = signals[signals["date"] == snapshot_date].copy()

    nodes, signal_tickers = build_node_set(signals_on_date, args.top_signals, args.max_nodes)
    nodes = [t for t in nodes if t in ticker_to_idx]

    if len(nodes) < 5:
        raise RuntimeError(f"Too few nodes after filtering: {len(nodes)}")

    date_idx_matches = np.where(all_dates == snapshot_date)[0]
    if len(date_idx_matches) == 0:
        eligible = np.where(all_dates <= snapshot_date)[0]
        if len(eligible) == 0:
            raise RuntimeError(f"No return dates on or before {snapshot_date.date()}.")
        date_idx = int(eligible[-1])
    else:
        date_idx = int(date_idx_matches[0])

    start_idx = max(0, date_idx - args.lookback + 1)
    node_indices = [ticker_to_idx[t] for t in nodes]
    window = returns[start_idx : date_idx + 1, :][:, node_indices]

    finite_rate = np.isfinite(window).mean(axis=0)
    keep = finite_rate >= 0.80

    nodes = [node for node, k in zip(nodes, keep) if k]
    node_indices = [idx for idx, k in zip(node_indices, keep) if k]
    finite_rate = finite_rate[keep]
    window = window[:, keep]

    if len(nodes) < 5:
        raise RuntimeError(f"Too few nodes after valid-data filtering: {len(nodes)}")

    clean_window = np.where(np.isfinite(window), window, np.nan)
    col_means = np.nanmean(clean_window, axis=0)
    clean_window = np.where(np.isfinite(clean_window), clean_window, col_means)

    corr = np.corrcoef(clean_window, rowvar=False)
    coords = classical_mds_from_corr(corr, dims=2)

    signal_map = (
        signals_on_date.sort_values("adjusted_confidence", ascending=False)
        .drop_duplicates("ticker")
        .set_index("ticker")
    )

    z = np.zeros(len(nodes), dtype=float)
    confidence = np.zeros(len(nodes), dtype=float)
    is_signal = np.array([node in signal_tickers for node in nodes], dtype=bool)

    if args.z_mode == "peer_spread_z":
        for i, node in enumerate(nodes):
            if node in signal_map.index:
                z[i] = float(signal_map.loc[node, "peer_spread_z"])
                confidence[i] = float(signal_map.loc[node, "adjusted_confidence"])
    else:
        future_end = min(returns.shape[0], date_idx + args.forward_days + 1)
        future = returns[date_idx + 1 : future_end, :][:, node_indices]
        z = np.nansum(future, axis=0)
        for i, node in enumerate(nodes):
            if node in signal_map.index:
                confidence[i] = float(signal_map.loc[node, "adjusted_confidence"])

    sizes = np.where(is_signal, 80.0 + 50.0 * np.maximum(confidence, 0.0), 25.0)

    fig = plt.figure(figsize=(15, 10))
    ax = fig.add_subplot(111, projection="3d")

    x = coords[:, 0]
    y = coords[:, 1]

    edge_count = 0
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            if corr[i, j] >= args.min_edge_corr:
                ax.plot([x[i], x[j]], [y[i], y[j]], [z[i], z[j]], linewidth=0.4, alpha=0.25)
                edge_count += 1

    scatter = ax.scatter(x, y, z, c=z, s=sizes, alpha=0.9)

    for i, node in enumerate(nodes):
        if is_signal[i]:
            ax.text(x[i], y[i], z[i], node, fontsize=8)

    ax.set_title(
        f"Market Manifold Snapshot | {snapshot_date.date()} | "
        f"lookback={args.lookback} | z={args.z_mode} | nodes={len(nodes)} | edges={edge_count}"
    )
    ax.set_xlabel("Correlation fabric X")
    ax.set_ylabel("Correlation fabric Y")
    ax.set_zlabel(args.z_mode)

    fig.colorbar(scatter, ax=ax, shrink=0.65, label=args.z_mode)
    plt.tight_layout()

    safe_date = str(snapshot_date.date())
    out = out_dir / f"market_manifold_{safe_date}_{args.z_mode}.png"
    plt.savefig(out, dpi=170)
    plt.close()

    summary = pd.DataFrame(
        {
            "date": snapshot_date,
            "ticker": nodes,
            "is_signal": is_signal,
            "x": x,
            "y": y,
            "z": z,
            "confidence": confidence,
            "finite_rate": finite_rate,
        }
    )
    summary_out = out_dir / f"market_manifold_{safe_date}_{args.z_mode}_nodes.csv"
    summary.to_csv(summary_out, index=False)

    print("saved:", out)
    print("saved:", summary_out)
    print("snapshot_date:", snapshot_date.date())
    print("nodes:", len(nodes))
    print("signal_nodes:", int(is_signal.sum()))
    print("edges:", edge_count)
    print()
    print("signal rows:")
    print(
        summary[summary["is_signal"]]
        .sort_values("confidence", ascending=False)
        .head(20)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
