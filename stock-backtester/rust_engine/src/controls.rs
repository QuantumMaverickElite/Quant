use crate::io::{Order, PriceMatrix};
use rand::prelude::*;

pub fn randomize_tickers_same_dates_one(
    orders: &[Order],
    prices: &PriceMatrix,
    seed: u64,
    run: usize,
) -> Vec<Order> {
    let mut rng = StdRng::seed_from_u64(seed + run as u64);
    randomize_order_tickers(orders, prices, &mut rng)
}

pub fn randomize_tickers_and_dates_one(
    orders: &[Order],
    prices: &PriceMatrix,
    seed: u64,
    run: usize,
) -> Vec<Order> {
    let mut rng = StdRng::seed_from_u64(seed + 1_000_000 + run as u64);

    let mut randomized = randomize_order_tickers(orders, prices, &mut rng);

    for order in randomized.iter_mut() {
        let Some(entry_idx) = prices.date_to_idx.get(&order.entry_date).copied() else {
            continue;
        };

        let Some(exit_idx) = prices.date_to_idx.get(&order.exit_date).copied() else {
            continue;
        };

        if exit_idx <= entry_idx {
            continue;
        }

        let hold_len = exit_idx - entry_idx;

        if prices.dates.len() <= hold_len + 1 {
            continue;
        }

        let max_start = prices.dates.len() - hold_len - 1;
        let new_signal_idx = rng.gen_range(0..max_start);
        let new_entry_idx = new_signal_idx + 1;
        let new_exit_idx = new_entry_idx + hold_len;

        order.signal_date = prices.dates[new_signal_idx].clone();
        order.entry_date = prices.dates[new_entry_idx].clone();
        order.exit_date = prices.dates[new_exit_idx].clone();
    }

    randomized
}

fn randomize_order_tickers(orders: &[Order], prices: &PriceMatrix, rng: &mut StdRng) -> Vec<Order> {
    let tickers = &prices.tickers;

    orders
        .iter()
        .map(|order| {
            let idx = rng.gen_range(0..tickers.len());
            let mut new_order = order.clone();
            new_order.ticker = tickers[idx].clone();
            new_order
        })
        .collect()
}
