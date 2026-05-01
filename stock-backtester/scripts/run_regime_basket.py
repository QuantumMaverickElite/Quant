import argparse
import subprocess
import sys

DEFAULT_TICKERS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA"]


def run_command(cmd: list[str]) -> None:
    print("\n" + " ".join(cmd))
    result = subprocess.run(cmd)

    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run regime backtests across a basket of tickers."
    )
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS)
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default="2024-12-31")

    args = parser.parse_args()

    modes = [
        [],
        ["--use-regime-router"],
        ["--use-regime-router", "--use-options-overlay"],
    ]

    for ticker in args.tickers:
        for mode in modes:
            cmd = [
                sys.executable,
                "-m",
                "backtester.cli",
                "--ticker",
                ticker,
                "--strategy",
                "regime",
                "--start",
                args.start,
                "--end",
                args.end,
            ]

            cmd.extend(mode)
            run_command(cmd)


if __name__ == "__main__":
    main()
