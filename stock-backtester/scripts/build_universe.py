# scripts/build_universe.py

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build stock universe files for quant research."
    )

    parser.add_argument(
        "--mode",
        choices=["market", "exchange", "random", "sampled-market", "file"],
        required=True,
    )

    parser.add_argument("--exchange", choices=["NASDAQ", "NYSE", "AMEX"], default=None)
    parser.add_argument("--n", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--input-file", default=None)
    parser.add_argument("--out", required=True)

    parser.add_argument("--exclude-etfs", action="store_true")
    parser.add_argument("--exclude-test-issues", action="store_true", default=True)

    parser.add_argument(
        "--common-only-ish",
        action="store_true",
        help="Remove obvious warrants, units, rights, preferreds, notes, and unusual suffixes.",
    )

    parser.add_argument(
        "--common-stock-only",
        action="store_true",
        help="Stricter filter for common-stock-like securities. Removes funds, trusts, notes, income products, preferreds, warrants, units, rights, and many structured products.",
    )

    parser.add_argument("--min-symbol-len", type=int, default=1)
    parser.add_argument("--max-symbol-len", type=int, default=5)

    return parser.parse_args()


def clean_symbol(symbol: str) -> str:
    return str(symbol).strip().upper().replace(".", "-")


def read_nasdaq_listed() -> pd.DataFrame:
    df = pd.read_csv(NASDAQ_LISTED_URL, sep="|")

    df = df[df["Symbol"].notna()].copy()
    df = df[~df["Symbol"].astype(str).str.startswith("File Creation Time")].copy()

    out = pd.DataFrame(
        {
            "ticker": df["Symbol"].map(clean_symbol),
            "name": df.get("Security Name", "").astype(str),
            "exchange": "NASDAQ",
            "etf": df.get("ETF", "N"),
            "test_issue": df.get("Test Issue", "N"),
        }
    )

    return out


def read_other_listed() -> pd.DataFrame:
    df = pd.read_csv(OTHER_LISTED_URL, sep="|")

    df = df[df["ACT Symbol"].notna()].copy()
    df = df[~df["ACT Symbol"].astype(str).str.startswith("File Creation Time")].copy()

    exchange_map = {
        "N": "NYSE",
        "A": "AMEX",
        "P": "NYSE_ARCA",
        "Z": "BATS",
        "V": "IEXG",
    }

    exchange_raw = df.get("Exchange", "")

    out = pd.DataFrame(
        {
            "ticker": df["ACT Symbol"].map(clean_symbol),
            "name": df.get("Security Name", "").astype(str),
            "exchange": exchange_raw.map(exchange_map).fillna(exchange_raw),
            "etf": df.get("ETF", "N"),
            "test_issue": df.get("Test Issue", "N"),
        }
    )

    return out


def load_market_universe() -> pd.DataFrame:
    nasdaq = read_nasdaq_listed()
    other = read_other_listed()

    df = pd.concat([nasdaq, other], ignore_index=True)

    df = df.dropna(subset=["ticker"]).copy()
    df["ticker"] = df["ticker"].map(clean_symbol)
    df["name"] = df["name"].astype(str)

    df = df[df["ticker"] != ""].copy()
    df = df.drop_duplicates(subset=["ticker"], keep="first").copy()

    return df


def apply_filters(df: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    frame = df.copy()

    if args.exclude_etfs and "etf" in frame.columns:
        frame = frame[frame["etf"].astype(str).str.upper() != "Y"].copy()

    if args.exclude_test_issues and "test_issue" in frame.columns:
        frame = frame[frame["test_issue"].astype(str).str.upper() != "Y"].copy()

    frame = frame[
        frame["ticker"].str.len().between(args.min_symbol_len, args.max_symbol_len)
    ].copy()

    bad_markers = ["+", "^", "/", "$", "="]
    for marker in bad_markers:
        frame = frame[~frame["ticker"].str.contains(marker, regex=False)].copy()

    if args.common_only_ish or args.common_stock_only:
        frame = apply_common_only_filter(frame)

    if args.common_stock_only:
        frame = apply_common_stock_only_filter(frame)

    frame = frame.sort_values("ticker").reset_index(drop=True)

    return frame


def apply_common_only_filter(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()

    ticker = frame["ticker"].astype(str)
    name = frame["name"].astype(str).str.upper()

    bad_ticker_suffixes = (
        "W",  # warrants often end W
        "WS",
        "WT",
        "R",  # rights
        "U",  # units
        "UN",
        "P",  # preferred-ish
        "PR",
        "L",  # notes / special securities often end L
    )

    frame = frame[
        ~((ticker.str.len() >= 4) & ticker.str.endswith(bad_ticker_suffixes))
    ].copy()

    name = frame["name"].astype(str).str.upper()

    bad_name_words = [
        "WARRANT",
        "RIGHT",
        "RIGHTS",
        "UNIT",
        "UNITS",
        "PREFERRED",
        "PREFERENCE",
        "DEPOSITARY",
        "NOTE",
        "NOTES",
        "BOND",
        "DEBENTURE",
        "REDEEMABLE",
        "ACQUISITION CORP. RIGHT",
        "ACQUISITION CORP. UNIT",
    ]

    mask = pd.Series(False, index=frame.index)

    for word in bad_name_words:
        mask = mask | name.str.contains(word, regex=False)

    frame = frame[~mask].copy()
    frame = frame[frame["ticker"].str.match(r"^[A-Z]{1,5}$")].copy()

    return frame


def apply_common_stock_only_filter(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()

    name = frame["name"].astype(str).str.upper()

    bad_name_words = [
        # Funds / ETFs / ETNs / closed-end funds
        "FUND",
        "ETF",
        "ETN",
        "EXCHANGE TRADED",
        "CLOSED END",
        "CLOSED-END",
        "CLOSED END FUND",
        "INDEX FUND",
        "INCOME FUND",
        "MUNICIPAL",
        "MUNI",
        "BOND",
        "TREASURY",
        "HIGH YIELD",
        "FLOATING RATE",
        "TERM TRUST",
        "TRUST",
        "ROYALTY TRUST",
        "INVESTMENT TRUST",
        "UNIT TRUST",
        "ADVANTAGED",
        "OPPORTUNITY FUND",
        "STRATEGIC INCOME",
        "TAXABLE",
        "TAX-FREE",
        "DURATION",
        "LOAN",
        "CREDIT",
        "CLO",
        "CLO ",
        "MORTGAGE",
        "REAL ESTATE INVESTMENT TRUST",
        # Preferreds / notes / structured products
        "PREFERRED",
        "PREFERENCE",
        "DEPOSITARY",
        "DEPOSITARY SHARES",
        "NOTE",
        "NOTES",
        "SENIOR NOTE",
        "SUBORDINATED",
        "DEBENTURE",
        "BABY BOND",
        "REDEEMABLE",
        "CONVERTIBLE",
        # SPAC-like / non-operating forms
        "WARRANT",
        "RIGHT",
        "RIGHTS",
        "UNIT",
        "UNITS",
        "ACQUISITION",
        "SPAC",
        "BLANK CHECK",
        # Commodity / crypto / derivative products
        "GOLD SHARES",
        "SILVER",
        "BITCOIN",
        "ETHER",
        "2X",
        "3X",
        "ULTRA",
        "INVERSE",
        "LEVERAGED",
    ]

    mask = pd.Series(False, index=frame.index)

    for word in bad_name_words:
        mask = mask | name.str.contains(word, regex=False)

    frame = frame[~mask].copy()

    # Extra ticker-level cleanup for common fund/CEF/ETN names that survive by vague metadata.
    known_non_common_like = {
        "ADX",
        "ASA",
        "CET",
        "ETO",
        "HQH",
        "HQL",
        "SOR",
        "TY",
        "GLU",
        "BST",
        "CSQ",
        "QQQX",
        "FFA",
        "EOI",
        "NIE",
        "JCE",
        "GLQ",
        "ETG",
        "ETB",
        "SPXX",
        "BCX",
        "FNGO",
        "DGP",
        "BAR",
        "AMUB",
        "MLPB",
        "PDI",
        "PTY",
        "PDO",
        "BME",
        "BMEZ",
        "BUI",
        "UTF",
        "UTG",
        "USA",
        "ASG",
        "GAM",
        "RVT",
        "RMT",
        "RGT",
        "CLM",
        "CRF",
        "OXLC",
        "ECC",
        "OCCI",
        "PSEC",
        "MAIN",
        "ARCC",
        "OBDC",
        "FSK",
        "HTGC",
    }

    frame = frame[~frame["ticker"].isin(known_non_common_like)].copy()
    leaked = sorted(set(frame["ticker"]) & known_non_common_like)
    if leaked:
        raise RuntimeError(f"Known non-common tickers survived filter: {leaked}")
    # Keep only simple alphabetic symbols after all name filters.
    frame = frame[frame["ticker"].str.match(r"^[A-Z]{1,5}$")].copy()

    return frame


def load_file_universe(path: str) -> pd.DataFrame:
    p = Path(path)

    if not p.exists():
        raise FileNotFoundError(p)

    tickers = [
        clean_symbol(line)
        for line in p.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    return pd.DataFrame(
        {
            "ticker": sorted(set(tickers)),
            "exchange": "FILE",
            "name": "",
            "etf": "N",
            "test_issue": "N",
        }
    )


def main() -> None:
    args = parse_args()

    if args.mode == "file":
        if not args.input_file:
            raise ValueError("--input-file is required for --mode file")
        df = load_file_universe(args.input_file)
    else:
        df = load_market_universe()
        df = apply_filters(df, args)

    if args.mode == "exchange":
        if not args.exchange:
            raise ValueError("--exchange is required for --mode exchange")
        df = df[df["exchange"] == args.exchange].copy()

    if args.mode in {"random", "sampled-market"}:
        if args.n is None:
            raise ValueError("--n is required for random/sample modes")

        if args.n > len(df):
            raise ValueError(
                f"Requested n={args.n}, but universe only has {len(df)} tickers"
            )

        rng = np.random.default_rng(args.seed)
        idx = rng.choice(len(df), size=args.n, replace=False)
        df = df.iloc[idx].copy()
        df = df.sort_values("ticker").reset_index(drop=True)

    if args.mode == "market" and args.n is not None:
        df = df.head(args.n).copy()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    tickers = df["ticker"].drop_duplicates().sort_values().tolist()
    out_path.write_text("\n".join(tickers) + "\n")

    print(f"Saved universe: {out_path}")
    print(f"Tickers: {len(tickers):,}")

    if "exchange" in df.columns:
        print()
        print(df["exchange"].value_counts().to_string())

    print()
    print("First 30 tickers:")
    print(" ".join(tickers[:30]))


if __name__ == "__main__":
    main()
