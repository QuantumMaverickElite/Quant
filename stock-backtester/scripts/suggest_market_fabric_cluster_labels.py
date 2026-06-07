#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import math
import re
from collections import Counter
from pathlib import Path

import pandas as pd


THEME_MAP = {
    "Semis / Hardware": {"NVDA","AMD","MU","AVGO","QCOM","TXN","AMAT","LRCX","KLAC","INTC","ON","MCHP","ADI","MRVL","SMCI","DELL","HPQ","WDC","STX","ASML","TSM","ENTG","MKSI","LSCC","SLAB"},
    "Software / Cloud": {"MSFT","CRM","NOW","ADBE","ORCL","SNOW","DDOG","NET","PANW","CRWD","ZS","MDB","TEAM","SHOP","HUBS","WDAY","ADSK","HUBS","PLTR"},
    "Mega Cap / Internet": {"AAPL","GOOGL","GOOG","META","AMZN","NFLX","UBER","ABNB","BKNG","EXPE","TSLA"},
    "Banks / Financials": {"JPM","BAC","WFC","GS","MS","C","USB","PNC","TFC","SCHW","AXP","COF","DFS","BLK","BK","STT","BNY","NWBI"},
    "Energy / Materials": {"XOM","CVX","COP","OXY","MPC","VLO","PSX","EOG","SLB","HAL","KOS","CDE","FCX","NEM","AA","CLF","CTRA","DVN","FANG"},
    "Healthcare / Pharma": {"LLY","UNH","JNJ","MRK","PFE","ABBV","ABT","TMO","DHR","BMY","AMGN","GILD","CVS","HUM","CI","MOH","CNC","ZBH","ALNY"},
    "Consumer / Retail": {"WMT","COST","TGT","HD","LOW","MCD","SBUX","NKE","LULU","TJX","ROST","ORLY","AZO","YUM","CMG","TXRH"},
    "Industrials / Transport": {"CAT","DE","GE","HON","RTX","BA","LMT","NOC","UNP","CSX","NSC","FDX","UPS","URI","PH","EMR","ETN","CACI","LDOS","SAIC"},
    "Utilities / Defensive": {"DUK","SO","NEE","AEP","EXC","XEL","ED","PEG","PPL","WEC","CMS","AEE","EVRG","ATO"},
    "REITs / Yield": {"O","SPG","AMT","PLD","EQIX","PSA","CCI","DLR","VTR","WELL","NNN","GTY","SKT","HST"},
    "Biotech / High Beta": {"MRNA","BNTX","NVAX","INO","BEAM","CRSP","EDIT","NTLA","DNA","SAVA","VKTX","CELH","BLUE","SRPT"},
}


BAD_TOKENS = {
    "NAN", "NONE", "NULL", "TRUE", "FALSE", "LONG", "SHORT", "TICKER",
    "TOP", "STRESS", "DATE", "FRAME", "CLUSTER", ""
}


def extract_tickers_from_value(x: object) -> list[str]:
    if x is None:
        return []

    if isinstance(x, float) and math.isnan(x):
        return []

    s = str(x).strip()
    if not s or s.upper() in BAD_TOKENS:
        return []

    items = []

    # Try parsing Python-list-looking values.
    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, (list, tuple, set)):
            for y in parsed:
                items.extend(extract_tickers_from_value(y))
            return items
    except Exception:
        pass

    # Pull ticker-like tokens from messy text.
    tokens = re.findall(r"\b[A-Z][A-Z0-9.\-]{0,6}\b", s.upper())
    out = []
    for t in tokens:
        t = t.replace(".", "-").strip()
        if t in BAD_TOKENS:
            continue
        if len(t) < 1 or len(t) > 7:
            continue
        # Avoid pure numbers.
        if t.isdigit():
            continue
        out.append(t)

    return out


def best_theme(tickers: list[str]) -> tuple[str, int]:
    s = set(tickers)
    best = "Mixed Market"
    best_hits = 0

    for theme, members in THEME_MAP.items():
        hits = len(s.intersection(members))
        if hits > best_hits:
            best = theme
            best_hits = hits

    return best, best_hits


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--cluster-summary", required=True)
    p.add_argument("--out-json", required=True)
    p.add_argument("--out-csv", required=True)
    p.add_argument("--top-tickers", type=int, default=20)
    args = p.parse_args()

    df = pd.read_csv(args.cluster_summary)

    cluster_col = "cluster_id" if "cluster_id" in df.columns else "cluster"

    source_cols = [
        c for c in [
            "top_tickers_by_stress",
            "top_longs",
            "top_shorts",
            "ticker",
            "tickers",
            "members",
        ]
        if c in df.columns
    ]

    if not source_cols:
        raise ValueError(f"No ticker-like columns found. Columns: {df.columns.tolist()}")

    rows = []

    for cid, g in df.groupby(cluster_col):
        counter = Counter()

        for _, row in g.iterrows():
            for col in source_cols:
                for t in extract_tickers_from_value(row.get(col)):
                    counter[t] += 1

        top = [t for t, _ in counter.most_common(args.top_tickers)]
        theme, hits = best_theme(top)

        # If theme hit count is weak, keep mixed but still show tickers.
        label_theme = theme if hits >= 2 else "Mixed / " + (theme if hits == 1 else "Unlabeled")
        label = f"C{cid}: {label_theme}"

        rows.append({
            "cluster": int(cid),
            "label": label,
            "theme": label_theme,
            "theme_hits": hits,
            "top_tickers": ", ".join(top),
        })

    out = pd.DataFrame(rows).sort_values("cluster")
    label_map = {str(r["cluster"]): r["label"] for _, r in out.iterrows()}

    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(label_map, indent=2))
    out.to_csv(args.out_csv, index=False)

    print(f"Saved label map -> {args.out_json}")
    print(f"Saved label csv -> {args.out_csv}")
    print()
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
