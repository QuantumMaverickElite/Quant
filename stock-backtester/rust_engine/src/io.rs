use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;

#[derive(Debug, Clone, Deserialize)]
pub struct Order {
    pub signal_date: String,
    pub entry_date: String,
    pub exit_date: String,
    pub ticker: String,
    pub adjusted_confidence: f64,
    #[serde(default)]
    pub peer_spread_z: f64,
}

#[derive(Debug)]
pub struct PriceMatrix {
    pub dates: Vec<String>,
    pub tickers: Vec<String>,
    pub prices: Vec<Vec<f64>>,
    pub date_to_idx: HashMap<String, usize>,
    pub ticker_to_idx: HashMap<String, usize>,
}

#[derive(Debug, Serialize)]
pub struct EquityRow {
    pub date: String,
    pub cash: f64,
    pub open_value: f64,
    pub equity: f64,
    pub gross_exposure: f64,
    pub open_positions: usize,
    pub daily_return: f64,
    pub drawdown: f64,
}

#[derive(Debug, Serialize)]
pub struct ClosedTradeRow {
    pub signal_date: String,
    pub entry_date: String,
    pub exit_date: String,
    pub ticker: String,
    pub entry_price: f64,
    pub exit_price: f64,
    pub entry_value: f64,
    pub exit_value: f64,
    pub pnl: f64,
    pub trade_return: f64,
    pub adjusted_confidence: f64,
    pub peer_spread_z: f64,
}

pub fn read_orders(path: &PathBuf) -> Result<Vec<Order>> {
    let mut reader = csv::Reader::from_path(path)
        .with_context(|| format!("Failed to open orders CSV: {:?}", path))?;

    let mut orders = Vec::new();

    for row in reader.deserialize() {
        let order: Order = row?;

        if order.adjusted_confidence.is_finite() && order.adjusted_confidence > 0.0 {
            orders.push(order);
        }
    }

    Ok(orders)
}

pub fn read_prices(path: &PathBuf) -> Result<PriceMatrix> {
    let mut reader = csv::Reader::from_path(path)
        .with_context(|| format!("Failed to open prices CSV: {:?}", path))?;

    let headers = reader.headers()?.clone();

    if headers.len() < 2 {
        anyhow::bail!("prices CSV must contain date plus ticker columns.");
    }

    let tickers: Vec<String> = headers.iter().skip(1).map(|s| s.to_string()).collect();

    let ticker_to_idx: HashMap<String, usize> = tickers
        .iter()
        .enumerate()
        .map(|(i, ticker)| (ticker.clone(), i))
        .collect();

    let mut dates = Vec::new();
    let mut prices = Vec::new();

    for row in reader.records() {
        let record = row?;

        let date = record.get(0).context("Missing date")?.to_string();
        dates.push(date);

        let mut vals = Vec::with_capacity(tickers.len());

        for i in 1..record.len() {
            let raw = record.get(i).unwrap_or("");
            let value = raw.parse::<f64>().unwrap_or(f64::NAN);
            vals.push(value);
        }

        while vals.len() < tickers.len() {
            vals.push(f64::NAN);
        }

        prices.push(vals);
    }

    let date_to_idx: HashMap<String, usize> = dates
        .iter()
        .enumerate()
        .map(|(i, date)| (date.clone(), i))
        .collect();

    Ok(PriceMatrix {
        dates,
        tickers,
        prices,
        date_to_idx,
        ticker_to_idx,
    })
}

pub fn write_csv<T: Serialize>(path: PathBuf, rows: &[T]) -> Result<()> {
    let mut writer = csv::Writer::from_path(&path)
        .with_context(|| format!("Failed to create CSV: {:?}", path))?;

    for row in rows {
        writer.serialize(row)?;
    }

    writer.flush()?;
    Ok(())
}
