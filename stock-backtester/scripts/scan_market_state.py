from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf
from tabulate import tabulate

from backtester.analytics.entropy import EntropyConfig, compute_entropy_metrics
from backtester.decision.entropy_decision import (
    apply_entropy_decision_columns,
    latest_entropy_decision,
)
from backtester.decision.market_state import build_market_state
from backtester.decision.volatility_decision import make_volatility_decision


def import_compute_garch_metrics():
    try:
        from backtester.analytics.garch import compute_garch_metrics

        return compute_garch_metrics
    except ImportError:
        pass

    try:
        from backtester.analytics.garch_metrics import compute_garch_metrics

        return compute_garch_metrics
    except ImportError:
        pass

    try:
        from backtester.analytics.volatility import compute_garch_metrics

        return compute_garch_metrics
    except ImportError:
        pass

    raise ImportError(
        "Could not import compute_garch_metrics. "
        "Check src/backtester/analytics and update this script."
    )


def clean_yfinance_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)

    out.columns = [str(col).lower() for col in out.columns]
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan current volatility + entropy MarketState for multiple tickers."
    )

    parser.add_argument(
        "--tickers",
        "-t",
        nargs="+",
        default=["SPY", "QQQ", "NVDA", "JPM", "XOM"],
        help="Ticker symbols to scan.",
    )

    parser.add_argument(
        "--start",
        default="2018-01-01",
        help="Start date. Default: 2018-01-01",
    )

    parser.add_argument(
        "--end",
        default=None,
        help="Optional end date. Default: latest available data.",
    )

    parser.add_argument(
        "--entropy-window",
        type=int,
        default=60,
        help="Rolling entropy window. Default: 60",
    )

    parser.add_argument(
        "--zscore-window",
        type=int,
        default=252,
        help="Rolling z-score / percentile window. Default: 252",
    )

    parser.add_argument(
        "--bins",
        type=int,
        default=10,
        help="Number of bins for return entropy. Default: 10",
    )

    parser.add_argument(
        "--output",
        default="outputs/market_state/market_state_scan.csv",
        help="CSV output path.",
    )

    return parser.parse_args()


def scan_one_ticker(
    ticker: str,
    start: str,
    end: str | None,
    entropy_config: EntropyConfig,
) -> dict:
    compute_garch_metrics = import_compute_garch_metrics()

    df = yf.download(
        ticker,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
    )

    if df.empty:
        raise ValueError(f"No data returned for ticker {ticker}")

    prices = clean_yfinance_columns(df)

    if "close" not in prices.columns:
        raise ValueError(f"{ticker}: missing close column. Got {list(prices.columns)}")

    latest_close = float(prices["close"].dropna().iloc[-1])

    # ------------------------------------------------------------
    # 1. Volatility state
    # ------------------------------------------------------------
    vol_price_series = prices[["close"]].copy()
    vol_metrics = compute_garch_metrics(vol_price_series)

    if vol_metrics.empty:
        raise ValueError(f"{ticker}: volatility metrics returned empty DataFrame.")

    latest_vol_row = vol_metrics.dropna().iloc[-1]
    volatility_decision = make_volatility_decision(latest_vol_row)

    # ------------------------------------------------------------
    # 2. Entropy state
    # ------------------------------------------------------------
    entropy_metrics = compute_entropy_metrics(prices, entropy_config)
    entropy_metrics = apply_entropy_decision_columns(entropy_metrics)

    entropy_decision = latest_entropy_decision(entropy_metrics)

    # ------------------------------------------------------------
    # 3. Combined MarketState
    # ------------------------------------------------------------
    market_state = build_market_state(
        entropy_decision=entropy_decision,
        volatility_decision=volatility_decision,
    )

    return {
        "ticker": ticker,
        "close": latest_close,
        "vol_regime": volatility_decision.vol_regime,
        "vol_risk_multiplier": volatility_decision.risk_multiplier,
        "allow_options": volatility_decision.allow_options,
        "allow_new_equity_positions": volatility_decision.allow_new_equity_positions,
        "preferred_strategy": volatility_decision.preferred_strategy,
        "return_entropy_regime": entropy_decision.entropy_regime,
        "direction_entropy_regime": entropy_decision.direction_entropy_regime,
        "entropy_state": entropy_decision.entropy_state,
        "entropy_percentile": entropy_decision.entropy_percentile,
        "direction_entropy_percentile": entropy_decision.direction_entropy_percentile,
        "signal_trust_multiplier": entropy_decision.signal_trust_multiplier,
        "combined_multiplier": market_state.combined_multiplier,
        "capital_posture": market_state.capital_posture,
        "market_state_reason": market_state.reason,
        "entropy_state_description": entropy_decision.entropy_state_description,
        "error": None,
    }


def _yn(value) -> str:
    if pd.isna(value):
        return "?"
    return "Y" if bool(value) else "N"


def build_terminal_summary(result: pd.DataFrame) -> pd.DataFrame:
    summary = result.copy()

    if "error" in summary.columns:
        ok_rows = summary["error"].isna()
    else:
        ok_rows = pd.Series(True, index=summary.index)

    if "close" in summary.columns:
        summary["close"] = pd.to_numeric(summary["close"], errors="coerce").round(2)

    for col in [
        "vol_risk_multiplier",
        "signal_trust_multiplier",
        "combined_multiplier",
        "entropy_percentile",
        "direction_entropy_percentile",
    ]:
        if col in summary.columns:
            summary[col] = pd.to_numeric(summary[col], errors="coerce").round(2)

    if "allow_new_equity_positions" in summary.columns:
        summary["allow_new_equity_positions"] = summary[
            "allow_new_equity_positions"
        ].apply(_yn)

    if "allow_options" in summary.columns:
        summary["allow_options"] = summary["allow_options"].apply(_yn)

    rename_map = {
        "ticker": "Ticker",
        "close": "Close",
        "vol_regime": "Vol",
        "return_entropy_regime": "RetEnt",
        "direction_entropy_regime": "DirEnt",
        "entropy_percentile": "RetPct",
        "direction_entropy_percentile": "DirPct",
        "vol_risk_multiplier": "Risk",
        "signal_trust_multiplier": "Trust",
        "combined_multiplier": "Combo",
        "allow_new_equity_positions": "Eq",
        "allow_options": "Opt",
        "capital_posture": "Posture",
        "preferred_strategy": "Strategy",
        "error": "Error",
    }

    summary = summary.rename(columns=rename_map)

    terminal_cols = [
        "Ticker",
        "Close",
        "Vol",
        "RetEnt",
        "DirEnt",
        "RetPct",
        "DirPct",
        "Risk",
        "Trust",
        "Combo",
        "Eq",
        "Opt",
        "Posture",
        "Strategy",
        "Error",
    ]

    terminal_cols = [col for col in terminal_cols if col in summary.columns]

    # Keep failed rows visible, but sort successful rows by most actionable cases.
    if "Error" in summary.columns:
        failed = summary[summary["Error"].notna()]
        successful = summary[summary["Error"].isna()]
    else:
        failed = summary.iloc[0:0]
        successful = summary

    if not successful.empty:
        posture_rank = {
            "RESTRICTED": 0,
            "CAPITAL_PRESERVATION": 1,
            "DEFENSIVE": 2,
            "CAUTIOUS": 3,
            "NORMAL": 4,
            "EXPANSIVE": 5,
        }

        if "Posture" in successful.columns:
            successful = successful.copy()
            successful["_posture_rank"] = (
                successful["Posture"].map(posture_rank).fillna(99)
            )

            sort_cols = ["_posture_rank"]
            ascending = [True]

            if "Combo" in successful.columns:
                sort_cols.append("Combo")
                ascending.append(True)

            if "Ticker" in successful.columns:
                sort_cols.append("Ticker")
                ascending.append(True)

            successful = successful.sort_values(sort_cols, ascending=ascending)
            successful = successful.drop(columns=["_posture_rank"])

    summary = pd.concat([successful, failed], ignore_index=True)

    return summary[terminal_cols]


def print_market_state_summary(result: pd.DataFrame) -> None:
    terminal_summary = build_terminal_summary(result)

    print("\nMarket State Scan:")
    print(
        tabulate(
            terminal_summary,
            headers="keys",
            tablefmt="github",
            showindex=False,
        )
    )


def print_posture_breakdown(result: pd.DataFrame) -> None:
    if "capital_posture" not in result.columns:
        return

    counts = result["capital_posture"].value_counts(dropna=False)

    print("\nPosture Breakdown:")
    for posture, count in counts.items():
        print(f"  {posture}: {count}")


def main() -> None:
    args = parse_args()

    tickers = [ticker.upper() for ticker in args.tickers]

    entropy_config = EntropyConfig(
        price_col="close",
        entropy_window=args.entropy_window,
        zscore_window=args.zscore_window,
        n_bins=args.bins,
    )

    rows = []

    print("\nScanning MarketState for tickers:")
    print(", ".join(tickers))

    for ticker in tickers:
        print(f"Scanning {ticker}...")

        try:
            row = scan_one_ticker(
                ticker=ticker,
                start=args.start,
                end=args.end,
                entropy_config=entropy_config,
            )
            rows.append(row)
        except Exception as exc:
            rows.append(
                {
                    "ticker": ticker,
                    "error": str(exc),
                }
            )
            print(f"  {ticker} failed: {exc}")

    result = pd.DataFrame(rows)

    print_market_state_summary(result)
    print_posture_breakdown(result)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)

    print(f"\nSaved full scan to: {output_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
