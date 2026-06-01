use crate::io::{Order, PriceMatrix};
use rand::prelude::*;
use std::collections::HashSet;

pub fn randomize_tickers_same_dates_one(
    orders: &[Order],
    prices: &PriceMatrix,
    seed: u64,
    run: usize,
) -> Vec<Order> {
    let mut rng = StdRng::seed_from_u64(seed + run as u64);
    randomize_order_tickers(orders, &prices.tickers, &mut rng)
}

pub fn randomize_tickers_and_dates_one(
    orders: &[Order],
    prices: &PriceMatrix,
    seed: u64,
    run: usize,
) -> Vec<Order> {
    let mut rng = StdRng::seed_from_u64(seed + 1_000_000 + run as u64);

    let mut randomized = randomize_order_tickers(orders, &prices.tickers, &mut rng);

    randomize_dates_in_place(&mut randomized, prices, &mut rng);

    randomized
}

pub fn randomize_tickers_same_dates_excluding_selected_one(
    orders: &[Order],
    prices: &PriceMatrix,
    seed: u64,
    run: usize,
) -> Vec<Order> {
    let mut rng = StdRng::seed_from_u64(seed + 2_000_000 + run as u64);
    let replacement_universe = replacement_universe_excluding_selected(orders, prices);

    randomize_order_tickers(orders, &replacement_universe, &mut rng)
}

pub fn randomize_tickers_and_dates_excluding_selected_one(
    orders: &[Order],
    prices: &PriceMatrix,
    seed: u64,
    run: usize,
) -> Vec<Order> {
    let mut rng = StdRng::seed_from_u64(seed + 3_000_000 + run as u64);
    let replacement_universe = replacement_universe_excluding_selected(orders, prices);

    let mut randomized = randomize_order_tickers(orders, &replacement_universe, &mut rng);

    randomize_dates_in_place(&mut randomized, prices, &mut rng);

    randomized
}

pub fn replacement_universe_excluding_selected(
    orders: &[Order],
    prices: &PriceMatrix,
) -> Vec<String> {
    let selected: HashSet<String> = orders.iter().map(|order| order.ticker.clone()).collect();

    let replacements: Vec<String> = prices
        .tickers
        .iter()
        .filter(|ticker| !selected.contains(*ticker))
        .cloned()
        .collect();

    if replacements.is_empty() {
        prices.tickers.clone()
    } else {
        replacements
    }
}

fn randomize_order_tickers(
    orders: &[Order],
    replacement_universe: &[String],
    rng: &mut StdRng,
) -> Vec<Order> {
    orders
        .iter()
        .map(|order| {
            let idx = rng.gen_range(0..replacement_universe.len());
            let mut new_order = order.clone();
            new_order.ticker = replacement_universe[idx].clone();
            new_order
        })
        .collect()
}

fn randomize_dates_in_place(orders: &mut [Order], prices: &PriceMatrix, rng: &mut StdRng) {
    for order in orders.iter_mut() {
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
}
