mod controls;
mod io;
mod portfolio;
mod stats;

use anyhow::{Context, Result};
use clap::Parser;
use controls::{randomize_tickers_and_dates, randomize_tickers_same_dates};
use io::{read_orders, read_prices, write_csv};
use portfolio::{run_daily_portfolio, PortfolioConfig};
use rayon::prelude::*;
use serde::Serialize;
use stats::{summarize_distribution, PathSummary};
use std::fs;
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(name = "stress_mc")]
#[command(about = "Rust realistic daily portfolio stress engine")]
struct Args {
    #[arg(long)]
    orders_csv: PathBuf,

    #[arg(long)]
    prices_csv: PathBuf,

    #[arg(long)]
    out_dir: PathBuf,

    #[arg(long, default_value_t = 10_000.0)]
    initial_capital: f64,

    #[arg(long, default_value_t = 1000)]
    runs: usize,

    #[arg(long, default_value_t = 5.0)]
    fee_bps: f64,

    #[arg(long, default_value_t = 1.0)]
    max_gross_exposure: f64,

    #[arg(long, default_value_t = 0.20)]
    target_new_basket_exposure: f64,

    #[arg(long, default_value_t = 0.10)]
    max_position_weight: f64,

    #[arg(long, default_value_t = 42)]
    seed: u64,

    #[arg(long, default_value_t = false)]
    save_runs: bool,

    #[arg(long, default_value_t = false)]
    sweep: bool,

    #[arg(long, default_value = "1.0")]
    sweep_max_gross: String,

    #[arg(long, default_value = "0.20")]
    sweep_basket_exposure: String,

    #[arg(long, default_value = "0.10")]
    sweep_position_weight: String,
}

#[derive(Debug, Serialize)]
struct SweepRow {
    max_gross_exposure: f64,
    target_new_basket_exposure: f64,
    max_position_weight: f64,
    final_equity: f64,
    total_return: f64,
    max_drawdown: f64,
    win_rate: f64,
    sharpe_like: f64,
    avg_daily_return: f64,
    daily_vol: f64,
}

fn main() -> Result<()> {
    let args = Args::parse();

    fs::create_dir_all(&args.out_dir)
        .with_context(|| format!("Failed to create output dir: {:?}", args.out_dir))?;

    let orders = read_orders(&args.orders_csv)?;
    let prices = read_prices(&args.prices_csv)?;

    if orders.is_empty() {
        anyhow::bail!("No orders loaded.");
    }

    if args.sweep {
        return run_parameter_sweep(&args, &orders, &prices);
    }

    run_monte_carlo_controls(&args, &orders, &prices)
}

fn run_monte_carlo_controls(
    args: &Args,
    orders: &[io::Order],
    prices: &io::PriceMatrix,
) -> Result<()> {
    let config = PortfolioConfig {
        initial_capital: args.initial_capital,
        max_gross_exposure: args.max_gross_exposure,
        target_new_basket_exposure: args.target_new_basket_exposure,
        max_position_weight: args.max_position_weight,
        fee_bps: args.fee_bps,
    };

    let actual = run_daily_portfolio(
        orders,
        prices,
        &config,
        "actual".to_string(),
        0,
    );

    let same_date_order_sets = randomize_tickers_same_dates(
        orders,
        prices,
        args.runs,
        args.seed,
    );

    let same_date_summaries: Vec<PathSummary> = same_date_order_sets
        .into_par_iter()
        .enumerate()
        .map(|(run, randomized_orders)| {
            run_daily_portfolio(
                &randomized_orders,
                prices,
                &config,
                "same_dates_random_tickers".to_string(),
                run,
            )
            .summary
        })
        .collect();

    let random_date_order_sets = randomize_tickers_and_dates(
        orders,
        prices,
        args.runs,
        args.seed,
    );

    let random_date_summaries: Vec<PathSummary> = random_date_order_sets
        .into_par_iter()
        .enumerate()
        .map(|(run, randomized_orders)| {
            run_daily_portfolio(
                &randomized_orders,
                prices,
                &config,
                "random_dates_random_tickers".to_string(),
                run,
            )
            .summary
        })
        .collect();

    let mut all_mc = Vec::with_capacity(same_date_summaries.len() + random_date_summaries.len());
    all_mc.extend(same_date_summaries);
    all_mc.extend(random_date_summaries);

    let dist = summarize_distribution(&all_mc, actual.summary.total_return);

    write_csv(args.out_dir.join("actual_summary.csv"), &[actual.summary.clone()])?;
    write_csv(args.out_dir.join("actual_equity.csv"), &actual.equity)?;
    write_csv(args.out_dir.join("actual_closed_trades.csv"), &actual.trades)?;
    write_csv(args.out_dir.join("monte_carlo_summary.csv"), &dist)?;

    if args.save_runs {
        write_csv(args.out_dir.join("monte_carlo_runs.csv"), &all_mc)?;
    }

    println!();
    println!("================================================================================");
    println!("Rust Realistic Daily Portfolio Stress Test");
    println!("================================================================================");
    println!("Orders: {}", orders.len());
    println!("Price dates: {}", prices.dates.len());
    println!("Universe tickers: {}", prices.tickers.len());
    println!("Runs per control: {}", args.runs);
    println!("Initial capital: {:.2}", args.initial_capital);
    println!("Max gross exposure: {:.2}", args.max_gross_exposure);
    println!("Target new basket exposure: {:.2}", args.target_new_basket_exposure);
    println!("Max position weight: {:.2}", args.max_position_weight);
    println!("Fee bps one-way: {:.2}", args.fee_bps);

    println!();
    println!("Actual realistic daily portfolio:");
    println!(
        "  final_equity={:.2}, total_return={:.4}, max_drawdown={:.4}, win_rate={:.4}, sharpe_like={:.4}",
        actual.summary.final_equity,
        actual.summary.total_return,
        actual.summary.max_drawdown,
        actual.summary.win_rate,
        actual.summary.sharpe_like
    );

    println!();
    println!("Monte Carlo controls:");
    for row in &dist {
        println!(
            "  {} | prob_random_beats_actual={:.4} | actual_percentile={:.4} | mc_median={:.4} | mc_p95={:.4}",
            row.test,
            row.prob_random_beats_actual,
            row.actual_percentile,
            row.mc_median_total_return,
            row.mc_p95_total_return
        );
    }

    println!();
    println!("Saved outputs to {:?}", args.out_dir);

    Ok(())
}

fn run_parameter_sweep(
    args: &Args,
    orders: &[io::Order],
    prices: &io::PriceMatrix,
) -> Result<()> {
    let max_gross_values = parse_float_list(&args.sweep_max_gross)?;
    let basket_exposure_values = parse_float_list(&args.sweep_basket_exposure)?;
    let position_weight_values = parse_float_list(&args.sweep_position_weight)?;

    let mut configs = Vec::new();

    for &max_gross in &max_gross_values {
        for &basket_exposure in &basket_exposure_values {
            for &position_weight in &position_weight_values {
                configs.push(PortfolioConfig {
                    initial_capital: args.initial_capital,
                    max_gross_exposure: max_gross,
                    target_new_basket_exposure: basket_exposure,
                    max_position_weight: position_weight,
                    fee_bps: args.fee_bps,
                });
            }
        }
    }

    let rows: Vec<SweepRow> = configs
        .into_par_iter()
        .map(|config| {
            let result = run_daily_portfolio(
                orders,
                prices,
                &config,
                "sweep".to_string(),
                0,
            );

            SweepRow {
                max_gross_exposure: config.max_gross_exposure,
                target_new_basket_exposure: config.target_new_basket_exposure,
                max_position_weight: config.max_position_weight,
                final_equity: result.summary.final_equity,
                total_return: result.summary.total_return,
                max_drawdown: result.summary.max_drawdown,
                win_rate: result.summary.win_rate,
                sharpe_like: result.summary.sharpe_like,
                avg_daily_return: result.summary.avg_daily_return,
                daily_vol: result.summary.daily_vol,
            }
        })
        .collect();

    let mut sorted_rows = rows;

    sorted_rows.sort_by(|a, b| {
        b.sharpe_like
            .partial_cmp(&a.sharpe_like)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    write_csv(args.out_dir.join("sweep_summary.csv"), &sorted_rows)?;

    println!();
    println!("================================================================================");
    println!("Rust Parameter Sweep");
    println!("================================================================================");
    println!("Orders: {}", orders.len());
    println!("Price dates: {}", prices.dates.len());
    println!("Universe tickers: {}", prices.tickers.len());
    println!("Configs tested: {}", sorted_rows.len());
    println!("Fee bps one-way: {:.2}", args.fee_bps);
    println!("Saved: {:?}", args.out_dir.join("sweep_summary.csv"));

    println!();
    println!("Top configs by Sharpe-like score:");
    for row in sorted_rows.iter().take(20) {
        println!(
            "gross={:.2}, basket={:.2}, pos={:.2} | final={:.2}, ret={:.4}, dd={:.4}, win={:.4}, sharpe={:.4}",
            row.max_gross_exposure,
            row.target_new_basket_exposure,
            row.max_position_weight,
            row.final_equity,
            row.total_return,
            row.max_drawdown,
            row.win_rate,
            row.sharpe_like
        );
    }

    Ok(())
}

fn parse_float_list(raw: &str) -> Result<Vec<f64>> {
    let values: Vec<f64> = raw
        .split(',')
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .map(|s| {
            s.parse::<f64>()
                .with_context(|| format!("Failed to parse float value: {s}"))
        })
        .collect::<Result<Vec<_>>>()?;

    if values.is_empty() {
        anyhow::bail!("Float list cannot be empty.");
    }

    Ok(values)
}
