use crate::io::{ClosedTradeRow, EquityRow, Order, PriceMatrix};
use crate::stats::{summarize_daily_returns, PathSummary};
use std::collections::HashMap;

#[derive(Debug, Clone)]
struct OpenPosition {
    signal_date: String,
    entry_date: String,
    exit_date: String,
    ticker: String,
    ticker_idx: usize,
    shares: f64,
    entry_price: f64,
    entry_value: f64,
    adjusted_confidence: f64,
    peer_spread_z: f64,
}

#[derive(Debug, Clone)]
pub struct PortfolioConfig {
    pub initial_capital: f64,
    pub max_gross_exposure: f64,
    pub target_new_basket_exposure: f64,
    pub max_position_weight: f64,
    pub fee_bps: f64,
}

pub struct PortfolioResult {
    pub summary: PathSummary,
    pub equity: Vec<EquityRow>,
    pub trades: Vec<ClosedTradeRow>,
}

pub fn run_daily_portfolio(
    orders: &[Order],
    prices: &PriceMatrix,
    config: &PortfolioConfig,
    test_name: String,
    run: usize,
) -> PortfolioResult {
    let fee_rate = config.fee_bps / 10_000.0;

    let mut orders_by_entry: HashMap<String, Vec<Order>> = HashMap::new();

    for order in orders {
        orders_by_entry
            .entry(order.entry_date.clone())
            .or_default()
            .push(order.clone());
    }

    for group in orders_by_entry.values_mut() {
        group.sort_by(|a, b| {
            b.adjusted_confidence
                .partial_cmp(&a.adjusted_confidence)
                .unwrap()
        });
    }

    let mut cash = config.initial_capital;
    let mut open_positions: Vec<OpenPosition> = Vec::new();

    let mut equity_rows = Vec::with_capacity(prices.dates.len());
    let mut trade_rows = Vec::new();

    let mut prev_equity = config.initial_capital;
    let mut running_max = config.initial_capital;

    for (date_idx, date) in prices.dates.iter().enumerate() {
        let mut remaining = Vec::new();

        for pos in open_positions.drain(..) {
            if pos.exit_date == *date {
                let exit_price = prices.prices[date_idx][pos.ticker_idx];

                if exit_price.is_finite() && exit_price > 0.0 {
                    let exit_value_before_fee = pos.shares * exit_price;
                    let exit_fee = exit_value_before_fee * fee_rate;
                    let exit_value = exit_value_before_fee - exit_fee;

                    cash += exit_value;

                    let pnl = exit_value - pos.entry_value;
                    let trade_return = if pos.entry_value > 0.0 {
                        pnl / pos.entry_value
                    } else {
                        f64::NAN
                    };

                    trade_rows.push(ClosedTradeRow {
                        signal_date: pos.signal_date,
                        entry_date: pos.entry_date,
                        exit_date: pos.exit_date,
                        ticker: pos.ticker,
                        entry_price: pos.entry_price,
                        exit_price,
                        entry_value: pos.entry_value,
                        exit_value,
                        pnl,
                        trade_return,
                        adjusted_confidence: pos.adjusted_confidence,
                        peer_spread_z: pos.peer_spread_z,
                    });
                }
            } else {
                remaining.push(pos);
            }
        }

        open_positions = remaining;

        let open_value_before = mark_to_market(&open_positions, prices, date_idx);
        let equity_before_entries = cash + open_value_before;

        if equity_before_entries > 0.0 {
            let current_gross = open_value_before / equity_before_entries;

            if let Some(todays_orders) = orders_by_entry.get(date) {
                let available_exposure = (config.max_gross_exposure - current_gross).max(0.0);
                let basket_exposure = config.target_new_basket_exposure.min(available_exposure);

                if basket_exposure > 0.0 {
                    enter_orders(
                        todays_orders,
                        prices,
                        date_idx,
                        date,
                        basket_exposure,
                        equity_before_entries,
                        fee_rate,
                        config.max_position_weight,
                        &mut cash,
                        &mut open_positions,
                    );
                }
            }
        }

        let open_value = mark_to_market(&open_positions, prices, date_idx);
        let equity = cash + open_value;

        if equity > running_max {
            running_max = equity;
        }

        let daily_return = if prev_equity > 0.0 {
            equity / prev_equity - 1.0
        } else {
            0.0
        };

        let drawdown = if running_max > 0.0 {
            equity / running_max - 1.0
        } else {
            0.0
        };

        let gross_exposure = if equity > 0.0 {
            open_value / equity
        } else {
            0.0
        };

        equity_rows.push(EquityRow {
            date: date.clone(),
            cash,
            open_value,
            equity,
            gross_exposure,
            open_positions: open_positions.len(),
            daily_return,
            drawdown,
        });

        prev_equity = equity;
    }

    let daily_returns: Vec<f64> = equity_rows.iter().map(|r| r.daily_return).collect();

    let summary = summarize_daily_returns(
        test_name,
        run,
        &daily_returns,
        config.initial_capital,
    );

    PortfolioResult {
        summary,
        equity: equity_rows,
        trades: trade_rows,
    }
}

fn enter_orders(
    orders: &[Order],
    prices: &PriceMatrix,
    date_idx: usize,
    date: &str,
    basket_exposure: f64,
    equity_before_entries: f64,
    fee_rate: f64,
    max_position_weight: f64,
    cash: &mut f64,
    open_positions: &mut Vec<OpenPosition>,
) {
    let raw_sum: f64 = orders
        .iter()
        .map(|o| o.adjusted_confidence.max(0.0))
        .sum();

    if raw_sum <= 0.0 {
        return;
    }

    let mut target_weights = Vec::new();

    for order in orders {
        let raw = order.adjusted_confidence.max(0.0);
        let weight = (basket_exposure * raw / raw_sum).min(max_position_weight);
        target_weights.push(weight);
    }

    let capped_sum: f64 = target_weights.iter().sum();

    if capped_sum > basket_exposure && capped_sum > 0.0 {
        for w in target_weights.iter_mut() {
            *w *= basket_exposure / capped_sum;
        }
    }

    for (order, target_weight) in orders.iter().zip(target_weights.iter()) {
        let Some(&ticker_idx) = prices.ticker_to_idx.get(&order.ticker) else {
            continue;
        };

        let entry_price = prices.prices[date_idx][ticker_idx];

        if !entry_price.is_finite() || entry_price <= 0.0 {
            continue;
        }

        let mut desired_value = equity_before_entries * target_weight;
        let mut entry_fee = desired_value * fee_rate;
        let mut total_required = desired_value + entry_fee;

        if total_required > *cash {
            desired_value = *cash / (1.0 + fee_rate);
            entry_fee = desired_value * fee_rate;
            total_required = desired_value + entry_fee;
        }

        if desired_value <= 0.0 || total_required <= 0.0 {
            continue;
        }

        let shares = desired_value / entry_price;

        *cash -= total_required;

        open_positions.push(OpenPosition {
            signal_date: order.signal_date.clone(),
            entry_date: date.to_string(),
            exit_date: order.exit_date.clone(),
            ticker: order.ticker.clone(),
            ticker_idx,
            shares,
            entry_price,
            entry_value: desired_value,
            adjusted_confidence: order.adjusted_confidence,
            peer_spread_z: order.peer_spread_z,
        });
    }
}

fn mark_to_market(positions: &[OpenPosition], prices: &PriceMatrix, date_idx: usize) -> f64 {
    let mut total = 0.0;

    for pos in positions {
        let price = prices.prices[date_idx][pos.ticker_idx];

        if price.is_finite() && price > 0.0 {
            total += pos.shares * price;
        } else {
            total += pos.shares * pos.entry_price;
        }
    }

    total
}
