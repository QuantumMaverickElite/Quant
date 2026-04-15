def volatility_signal_series(price_series, iv_series, engine):
    signals = []

    for i in range(len(price_series)):
        if i < 100:
            signals.append("NO_TRADE")
            continue

        window_prices = price_series.iloc[:i]

        iv = iv_series.iloc[i]

        signal = engine(window_prices, implied_vol=iv)["decision"]

        signals.append(signal)

    return signals
