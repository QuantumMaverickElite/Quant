# scripts/generate_peer_basket_spreads.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from backtester.correlation.peer_spreads import (
    build_peer_map,
    compute_one_ticker,
    cumulative_spread_from_valid_relative,
    dtype_from_name,
    filter_spread_candidates,
    load_peers,
    load_returns,
    peer_weights,
    rolling_mean_std_count,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate large-universe peer-basket spread features from returns and peer maps."
    )

    parser.add_argument("--returns-meta", required=True, help="Path to returns_meta.json.")
    parser.add_argument("--peers", required=True, help="Path to peers.parquet or peers.csv.")
    parser.add_argument("--out", required=True, help="Output parquet/csv path.")

    parser.add_argument("--spread-window", type=int, default=100)
    parser.add_argument(
        "--min-spread-observations",
        type=int,
        default=80,
        help="Minimum valid relative-return observations required inside the rolling spread window.",
    )
    parser.add_argument("--min-peer-corr", type=float, default=0.30)
    parser.add_argument("--min-avg-peer-corr", type=float, default=0.35)
    parser.add_argument("--min-peer-count", type=int, default=3)
    parser.add_argument(
        "--min-daily-valid-peers",
        type=int,
        default=3,
        help="Minimum peers with finite returns required on a date.",
    )
    parser.add_argument("--max-peers", type=int, default=10)
    parser.add_argument("--weighting", choices=["equal", "corr"], default="equal")
    parser.add_argument("--min-abs-z", type=float, default=0.0)
    parser.add_argument(
        "--side",
        choices=["long", "short", "both"],
        default="long",
        help=(
            "Which peer-spread tail to export. "
            "long keeps negative z-scores, short keeps positive z-scores, "
            "and both keeps both tails."
        ),
    )
    parser.add_argument(
        "--long-only-candidates",
        action="store_true",
        help="Deprecated alias for --side long with --long-z threshold.",
    )
    parser.add_argument("--long-z", type=float, default=-2.0)
    parser.add_argument("--horizon", type=int, default=100)

    parser.add_argument(
        "--save-all-rows",
        action="store_true",
        help="Save all valid z-score rows. By default, only rows passing filters are saved if --min-abs-z or --long-only-candidates are used.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    returns_meta_path = Path(args.returns_meta)
    peers_path = Path(args.peers)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print()
    print("=" * 80)
    print("Large-Universe Peer-Basket Spread Generation")
    print("=" * 80)

    returns, meta = load_returns(returns_meta_path)
    tickers = [str(t).upper() for t in meta["tickers"]]
    dates = list(meta["dates"])

    if len(dates) != returns.shape[0]:
        raise RuntimeError(f"Date count mismatch: {len(dates)} dates, {returns.shape[0]} return rows.")

    print(f"Returns matrix: {returns.shape[0]:,} rows x {returns.shape[1]:,} tickers")
    print(f"Returns meta: {returns_meta_path}")

    peers = load_peers(peers_path)
    print(f"Peer rows loaded: {len(peers):,}")

    ticker_to_idx = {ticker: i for i, ticker in enumerate(tickers)}

    peers = peers[
        peers["ticker"].isin(ticker_to_idx)
        & peers["peer"].isin(ticker_to_idx)
    ].copy()

    peers["ticker_idx"] = peers["ticker"].map(ticker_to_idx).astype(int)
    peers["peer_idx"] = peers["peer"].map(ticker_to_idx).astype(int)

    peer_map = build_peer_map(
        peers,
        ticker_to_idx,
        min_peer_corr=args.min_peer_corr,
        max_peers=args.max_peers,
    )

    print(f"Tickers with usable peer groups: {len(peer_map):,}")
    print(f"min_peer_corr={args.min_peer_corr:.4f}")
    print(f"min_avg_peer_corr={args.min_avg_peer_corr:.4f}")
    print(f"min_peer_count={args.min_peer_count}")
    print(f"min_daily_valid_peers={args.min_daily_valid_peers}")
    print(f"spread_window={args.spread_window}")
    print(f"min_spread_observations={args.min_spread_observations}")
    print(f"weighting={args.weighting}")
    print(f"side={args.side}")
    print(f"min_abs_z={args.min_abs_z:.4f}")

    frames: list[pd.DataFrame] = []

    for n, (ticker, group) in enumerate(peer_map.items(), start=1):
        ticker_idx = ticker_to_idx[ticker]

        out = compute_one_ticker(
            ticker,
            ticker_idx,
            group,
            returns,
            dates,
            spread_window=args.spread_window,
            min_spread_observations=args.min_spread_observations,
            weighting=args.weighting,
            min_avg_peer_corr=args.min_avg_peer_corr,
            min_peer_count=args.min_peer_count,
            min_daily_valid_peers=args.min_daily_valid_peers,
            horizon=args.horizon,
        )

        if out is not None and not out.empty:
            frames.append(out)

        if n % 250 == 0 or n == len(peer_map):
            print(f"Processed {n:,}/{len(peer_map):,} peer groups")

    if frames:
        result = pd.concat(frames, ignore_index=True)
    else:
        result = pd.DataFrame()

    result = filter_spread_candidates(
        result,
        min_abs_z=args.min_abs_z,
        side=args.side,
        long_only_candidates=args.long_only_candidates,
        long_z=args.long_z,
    )

    if out_path.suffix.lower() == ".parquet":
        result.to_parquet(out_path, index=False)
    elif out_path.suffix.lower() == ".csv":
        result.to_csv(out_path, index=False)
    else:
        raise ValueError("Output path must end in .parquet or .csv")

    print()
    print("=" * 80)
    print("Peer-basket spread export complete")
    print("=" * 80)
    print(f"Saved: {out_path}")
    print(f"Rows: {len(result):,}")
    print(f"Unique tickers: {result['ticker'].nunique() if not result.empty else 0:,}")

    if not result.empty:
        print()
        print("Most extreme negative z-scores:")
        print(result.sort_values("peer_spread_z").head(20).to_string(index=False))

        print()
        print("Most extreme positive z-scores:")
        print(result.sort_values("peer_spread_z", ascending=False).head(20).to_string(index=False))


if __name__ == "__main__":
    main()
