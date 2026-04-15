import yfinance as yf
from datetime import datetime


def get_atm_iv(ticker_symbol: str):
    ticker = yf.Ticker(ticker_symbol)

    expirations = ticker.options
    if not expirations:
        return None

    # target ~30 days out
    today = datetime.today()

    def days_to_expiry(exp):
        exp_date = datetime.strptime(exp, "%Y-%m-%d")
        return abs((exp_date - today).days - 30)

    expiry = min(expirations, key=days_to_expiry)

    opt_chain = ticker.option_chain(expiry)
    calls = opt_chain.calls

    spot = ticker.history(period="1d")["Close"].iloc[-1]

    calls["diff"] = (calls["strike"] - spot).abs()
    atm_call = calls.sort_values("diff").iloc[0]

    return float(atm_call["impliedVolatility"])
