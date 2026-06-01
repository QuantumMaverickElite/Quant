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
use std::collections::{HashMap, HashSet};
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

    #[arg(long, default_value_t = false)]
    ticker_exclusion: bool,

    #[arg(long, default_value_t = false)]
    year_exclusion: bool,

    #[arg(long, default_value_t = false)]
    top_winner_exclusion: bool,

    #[arg(long, default_value = "1,3,5,10")]
    top_winner_counts: String,
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

#[derive(Debug, Serialize)]
struct ExclusionRow {
    exclusion_type: String,
    excluded: String,
    remaining_orders: usize,
    final_equity: f64,
    total_return: f64,
    max_drawdown: f64,
    win_rate: f64,
    sharpe_like: f64,
    avg_daily_return: f64,
    daily_vol: f64,
}

#[derive(Debug, Serialize)]
struct WinnerContributorRow {
    ticker: String,
    total_pnl: f64,
    trade_count: usize,
    avg_trade_pnl: f64,
    avg_trade_return: f64,
}

#[derive(Debug, Serialize)]
struct TopWinnerExclusionRow {
    excluded_top_n: usize,
    excluded_tickers: String,
    remaining_orders: usize,
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

    if args.ticker_exclusion {
        return run_ticker_exclusion(&args, &orders, &prices);
    }

    if args.year_exclusion {
        return run_year_exclusion(&args, &orders, &prices);
    }

    if args.top_winner_exclusion {
        return run_top_winner_exclusion(&args, &orders, &prices);
    }

    run_monte_carlo_controls(&args, &orders, &prices)
}

fn build_config(args: &Args) -> PortfolioConfig {
    PortfolioConfig {
        initial_capital: args.initial_capital,
        max_gross_exposure: args.max_gross_exposure,
        target_new_basket_exposure: args.target_new_basket_exposure,
        max_position_weight: args.max_position_weight,
        fee_bps: args.fee_bps,
    }
}

fn run_monte_carlo_controls(
    args: &Args,
    orders: &[io::Order],
    prices: &io::PriceMatrix,
) -> Result<()> {
    let config = build_config(args);

    let actual = run_daily_portfolio(
        orders,
        prices,
        &config,
        "actual".to_string(),
        0,
    );

    let same_date_order_sets =
        randomize_tickers_same_dates(orders, prices, args.runs, args.seed);

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

    let random_date_order_sets =
        randomize_tickers_and_dates(orders, prices, args.runs, args.seed);

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
    println!(
        "Target new basket exposure: {:.3}",
        args.target_new_basket_exposure
    );
    println!("Max position weight: {:.3}", args.max_position_weight);
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
            "gross={:.2}, basket={:.3}, pos={:.3} | final={:.2}, ret={:.4}, dd={:.4}, win={:.4}, sharpe={:.4}",
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

fn run_ticker_exclusion(
    args: &Args,
    orders: &[io::Order],
    prices: &io::PriceMatrix,
) -> Result<()> {
    let config = build_config(args);

    let mut tickers: Vec<String> = orders.iter().map(|o| o.ticker.clone()).collect();
    tickers.sort();
    tickers.dedup();

    let mut rows: Vec<ExclusionRow> = tickers
        .into_par_iter()
        .map(|excluded| {
            let filtered: Vec<io::Order> = orders
                .iter()
                .filter(|o| o.ticker != excluded)
                .cloned()
                .collect();

            let result = run_daily_portfolio(
                &filtered,
                prices,
                &config,
                "ticker_exclusion".to_string(),
                0,
            );

            ExclusionRow {
                exclusion_type: "ticker".to_string(),
                excluded,
                remaining_orders: filtered.len(),
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

    rows.sort_by(|a, b| {
        a.total_return
            .partial_cmp(&b.total_return)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    write_csv(args.out_dir.join("ticker_exclusion_summary.csv"), &rows)?;

    println!();
    println!("================================================================================");
    println!("Rust Ticker Exclusion Stress");
    println!("================================================================================");
    println!("Tickers tested: {}", rows.len());
    println!("Saved: {:?}", args.out_dir.join("ticker_exclusion_summary.csv"));

    println!();
    println!("Worst results after excluding ticker:");
    for row in rows.iter().take(20) {
        println!(
            "exclude={} | remaining_orders={} | final={:.2}, ret={:.4}, dd={:.4}, win={:.4}, sharpe={:.4}",
            row.excluded,
            row.remaining_orders,
            row.final_equity,
            row.total_return,
            row.max_drawdown,
            row.win_rate,
            row.sharpe_like
        );
    }

    println!();
    println!("Best results after excluding ticker:");
    for row in rows.iter().rev().take(20) {
        println!(
            "exclude={} | remaining_orders={} | final={:.2}, ret={:.4}, dd={:.4}, win={:.4}, sharpe={:.4}",
            row.excluded,
            row.remaining_orders,
            row.final_equity,
            row.total_return,
            row.max_drawdown,
            row.win_rate,
            row.sharpe_like
        );
    }

    Ok(())
}

fn run_year_exclusion(
    args: &Args,
    orders: &[io::Order],
    prices: &io::PriceMatrix,
) -> Result<()> {
    let config = build_config(args);

    let mut years: Vec<String> = orders
        .iter()
        .filter_map(|o| o.signal_date.get(0..4).map(|s| s.to_string()))
        .collect();

    years.sort();
    years.dedup();

    let mut rows: Vec<ExclusionRow> = years
        .into_par_iter()
        .map(|excluded_year| {
            let filtered: Vec<io::Order> = orders
                .iter()
                .filter(|o| !o.signal_date.starts_with(&excluded_year))
                .cloned()
                .collect();

            let result = run_daily_portfolio(
                &filtered,
                prices,
                &config,
                "year_exclusion".to_string(),
                0,
            );

            ExclusionRow {
                exclusion_type: "year".to_string(),
                excluded: excluded_year,
                remaining_orders: filtered.len(),
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

    rows.sort_by(|a, b| {
        a.total_return
            .partial_cmp(&b.total_return)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    write_csv(args.out_dir.join("year_exclusion_summary.csv"), &rows)?;

    println!();
    println!("================================================================================");
    println!("Rust Year Exclusion Stress");
    println!("================================================================================");
    println!("Years tested: {}", rows.len());
    println!("Saved: {:?}", args.out_dir.join("year_exclusion_summary.csv"));

    println!();
    println!("Worst results after excluding year:");
    for row in rows.iter().take(20) {
        println!(
            "exclude={} | remaining_orders={} | final={:.2}, ret={:.4}, dd={:.4}, win={:.4}, sharpe={:.4}",
            row.excluded,
            row.remaining_orders,
            row.final_equity,
            row.total_return,
            row.max_drawdown,
            row.win_rate,
            row.sharpe_like
        );
    }

    println!();
    println!("Best results after excluding year:");
    for row in rows.iter().rev().take(20) {
        println!(
            "exclude={} | remaining_orders={} | final={:.2}, ret={:.4}, dd={:.4}, win={:.4}, sharpe={:.4}",
            row.excluded,
            row.remaining_orders,
            row.final_equity,
            row.total_return,
            row.max_drawdown,
            row.win_rate,
            row.sharpe_like
        );
    }

    Ok(())
}

fn run_top_winner_exclusion(
    args: &Args,
    orders: &[io::Order],
    prices: &io::PriceMatrix,
) -> Result<()> {
    let config = build_config(args);

    let actual = run_daily_portfolio(
        orders,
        prices,
        &config,
        "actual_for_winner_ranking".to_string(),
        0,
    );

    let mut by_ticker: HashMap<String, Vec<(f64, f64)>> = HashMap::new();

    for trade in &actual.trades {
        by_ticker
            .entry(trade.ticker.clone())
            .or_default()
            .push((trade.pnl, trade.trade_return));
    }

    let mut contributors: Vec<WinnerContributorRow> = by_ticker
        .into_iter()
        .map(|(ticker, vals)| {
            let trade_count = vals.len();
            let total_pnl = vals.iter().map(|(pnl, _)| *pnl).sum::<f64>();
            let avg_trade_pnl = total_pnl / trade_count as f64;
            let avg_trade_return =
                vals.iter().map(|(_, r)| *r).sum::<f64>() / trade_count as f64;

            WinnerContributorRow {
                ticker,
                total_pnl,
                trade_count,
                avg_trade_pnl,
                avg_trade_return,
            }
        })
        .collect();

    contributors.sort_by(|a, b| {
        b.total_pnl
            .partial_cmp(&a.total_pnl)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    let counts = parse_usize_list(&args.top_winner_counts)?;

    let rows: Vec<TopWinnerExclusionRow> = counts
        .into_par_iter()
        .map(|top_n| {
            let excluded: Vec<String> = contributors
                .iter()
                .take(top_n)
                .map(|row| row.ticker.clone())
                .collect();

            let excluded_set: HashSet<String> = excluded.iter().cloned().collect();

            let filtered: Vec<io::Order> = orders
                .iter()
                .filter(|order| !excluded_set.contains(&order.ticker))
                .cloned()
                .collect();

            let result = run_daily_portfolio(
                &filtered,
                prices,
                &config,
                "top_winner_exclusion".to_string(),
                0,
            );

            TopWinnerExclusionRow {
                excluded_top_n: top_n,
                excluded_tickers: excluded.join("|"),
                remaining_orders: filtered.len(),
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
    sorted_rows.sort_by(|a, b| a.excluded_top_n.cmp(&b.excluded_top_n));

    write_csv(
        args.out_dir.join("top_winner_contributors.csv"),
        &contributors,
    )?;

    write_csv(
        args.out_dir.join("top_winner_exclusion_summary.csv"),
        &sorted_rows,
    )?;

    println!();
    println!("================================================================================");
    println!("Rust Top-Winner Exclusion Stress");
    println!("================================================================================");
    println!("Base final equity: {:.2}", actual.summary.final_equity);
    println!("Base total return: {:.4}", actual.summary.total_return);
    println!("Base max drawdown: {:.4}", actual.summary.max_drawdown);
    println!("Base Sharpe-like: {:.4}", actual.summary.sharpe_like);
    println!("Winner tickers ranked: {}", contributors.len());
    println!(
        "Saved: {:?}",
        args.out_dir.join("top_winner_exclusion_summary.csv")
    );
    println!(
        "Saved: {:?}",
        args.out_dir.join("top_winner_contributors.csv")
    );

    println!();
    println!("Top PnL contributors:");
    for row in contributors.iter().take(20) {
        println!(
            "{} | total_pnl={:.2}, trades={}, avg_pnl={:.2}, avg_return={:.4}",
            row.ticker,
            row.total_pnl,
            row.trade_count,
            row.avg_trade_pnl,
            row.avg_trade_return
        );
    }

    println!();
    println!("Top-winner exclusion results:");
    for row in &sorted_rows {
        println!(
            "exclude_top_n={} [{}] | remaining_orders={} | final={:.2}, ret={:.4}, dd={:.4}, win={:.4}, sharpe={:.4}",
            row.excluded_top_n,
            row.excluded_tickers,
            row.remaining_orders,
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

fn parse_usize_list(raw: &str) -> Result<Vec<usize>> {
    let values: Vec<usize> = raw
        .split(',')
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .map(|s| {
            s.parse::<usize>()
                .with_context(|| format!("Failed to parse usize value: {s}"))
        })
        .collect::<Result<Vec<_>>>()?;

    if values.is_empty() {
        anyhow::bail!("usize list cannot be empty.");
    }

    Ok(values)
}
