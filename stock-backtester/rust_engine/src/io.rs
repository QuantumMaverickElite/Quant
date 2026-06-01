use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

#[derive(Debug, Clone, Deserialize)]
pub struct Order {
    pub signal_date: String,
    pub entry_date: String,
    pub exit_date: String,
    pub ticker: String,
    #[serde(default = "default_direction")]
    pub direction: String,
    pub adjusted_confidence: f64,
    #[serde(default)]
    pub peer_spread_z: f64,
}

fn default_direction() -> String {
    "long".to_string()
}

#[derive(Debug)]
pub struct PriceMatrix {
    pub dates: Vec<String>,
    pub tickers: Vec<String>,
    pub prices: Vec<f64>,
    pub rows: usize,
    pub cols: usize,
    pub date_to_idx: HashMap<String, usize>,
    pub ticker_to_idx: HashMap<String, usize>,
}

impl PriceMatrix {
    #[inline]
    pub fn price(&self, date_idx: usize, ticker_idx: usize) -> f64 {
        self.prices[date_idx * self.cols + ticker_idx]
    }
}

#[derive(Debug, Deserialize)]
struct PriceMatrixMeta {
    dtype: String,
    rows: usize,
    cols: usize,
    dates: Vec<String>,
    tickers: Vec<String>,
    binary_file: String,
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
    pub direction: String,
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
    let cols = tickers.len();

    let mut dates = Vec::new();
    let mut prices = Vec::new();

    for row in reader.records() {
        let record = row?;

        let date = record.get(0).context("Missing date")?.to_string();
        dates.push(date);

        for i in 1..record.len() {
            let raw = record.get(i).unwrap_or("");
            let value = raw.parse::<f64>().unwrap_or(f64::NAN);
            prices.push(value);
        }

        while prices.len() < dates.len() * cols {
            prices.push(f64::NAN);
        }
    }

    let rows = dates.len();

    build_price_matrix(dates, tickers, prices, rows, cols)
}

pub fn read_prices_binary(meta_path: &PathBuf) -> Result<PriceMatrix> {
    let meta_text = fs::read_to_string(meta_path)
        .with_context(|| format!("Failed to read price matrix metadata: {:?}", meta_path))?;

    let meta: PriceMatrixMeta = serde_json::from_str(&meta_text)
        .with_context(|| format!("Failed to parse price matrix metadata: {:?}", meta_path))?;

    if meta.dates.len() != meta.rows {
        anyhow::bail!(
            "Metadata mismatch: dates len {} != rows {}",
            meta.dates.len(),
            meta.rows
        );
    }

    if meta.tickers.len() != meta.cols {
        anyhow::bail!(
            "Metadata mismatch: tickers len {} != cols {}",
            meta.tickers.len(),
            meta.cols
        );
    }

    let binary_path = meta_path
        .parent()
        .unwrap_or_else(|| std::path::Path::new("."))
        .join(&meta.binary_file);

    let bytes = fs::read(&binary_path)
        .with_context(|| format!("Failed to read price matrix binary: {:?}", binary_path))?;

    let expected_len = match meta.dtype.as_str() {
        "float32" => meta.rows * meta.cols * 4,
        "float64" => meta.rows * meta.cols * 8,
        other => anyhow::bail!("Unsupported matrix dtype: {other}"),
    };

    if bytes.len() != expected_len {
        anyhow::bail!(
            "Binary size mismatch: got {} bytes, expected {} bytes",
            bytes.len(),
            expected_len
        );
    }

    let mut prices = Vec::with_capacity(meta.rows * meta.cols);

    match meta.dtype.as_str() {
        "float32" => {
            for chunk in bytes.chunks_exact(4) {
                prices.push(f32::from_le_bytes([chunk[0], chunk[1], chunk[2], chunk[3]]) as f64);
            }
        }
        "float64" => {
            for chunk in bytes.chunks_exact(8) {
                prices.push(f64::from_le_bytes([
                    chunk[0], chunk[1], chunk[2], chunk[3], chunk[4], chunk[5], chunk[6], chunk[7],
                ]));
            }
        }
        _ => unreachable!(),
    }

    build_price_matrix(meta.dates, meta.tickers, prices, meta.rows, meta.cols)
}

fn build_price_matrix(
    dates: Vec<String>,
    tickers: Vec<String>,
    prices: Vec<f64>,
    rows: usize,
    cols: usize,
) -> Result<PriceMatrix> {
    if dates.len() != rows {
        anyhow::bail!("dates len {} does not match rows {}", dates.len(), rows);
    }

    if tickers.len() != cols {
        anyhow::bail!("tickers len {} does not match cols {}", tickers.len(), cols);
    }

    if prices.len() != rows * cols {
        anyhow::bail!(
            "prices len {} does not match rows*cols {}",
            prices.len(),
            rows * cols
        );
    }

    let ticker_to_idx: HashMap<String, usize> = tickers
        .iter()
        .enumerate()
        .map(|(i, ticker)| (ticker.clone(), i))
        .collect();

    let date_to_idx: HashMap<String, usize> = dates
        .iter()
        .enumerate()
        .map(|(i, date)| (date.clone(), i))
        .collect();

    Ok(PriceMatrix {
        dates,
        tickers,
        prices,
        rows,
        cols,
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
