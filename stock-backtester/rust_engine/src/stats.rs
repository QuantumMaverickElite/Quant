use serde::Serialize;

#[derive(Debug, Serialize, Clone)]
pub struct PathSummary {
    pub test: String,
    pub run: usize,
    pub num_days: usize,
    pub final_equity: f64,
    pub total_return: f64,
    pub max_drawdown: f64,
    pub win_rate: f64,
    pub avg_daily_return: f64,
    pub daily_vol: f64,
    pub sharpe_like: f64,
}

#[derive(Debug, Serialize)]
pub struct DistributionSummary {
    pub test: String,
    pub runs: usize,
    pub actual_total_return: f64,
    pub mc_mean_total_return: f64,
    pub mc_median_total_return: f64,
    pub mc_p05_total_return: f64,
    pub mc_p95_total_return: f64,
    pub actual_percentile: f64,
    pub prob_random_beats_actual: f64,
}

pub fn summarize_daily_returns(
    test: String,
    run: usize,
    daily_returns: &[f64],
    initial_capital: f64,
) -> PathSummary {
    if daily_returns.is_empty() {
        return PathSummary {
            test,
            run,
            num_days: 0,
            final_equity: initial_capital,
            total_return: 0.0,
            max_drawdown: 0.0,
            win_rate: 0.0,
            avg_daily_return: 0.0,
            daily_vol: 0.0,
            sharpe_like: f64::NAN,
        };
    }

    let mut equity = initial_capital;
    let mut running_max = initial_capital;
    let mut max_drawdown = 0.0;
    let mut wins = 0usize;

    for &r in daily_returns {
        if r > 0.0 {
            wins += 1;
        }

        equity *= 1.0 + r;

        if equity > running_max {
            running_max = equity;
        }

        let drawdown = equity / running_max - 1.0;

        if drawdown < max_drawdown {
            max_drawdown = drawdown;
        }
    }

    let mean = daily_returns.iter().sum::<f64>() / daily_returns.len() as f64;

    let variance = if daily_returns.len() > 1 {
        daily_returns
            .iter()
            .map(|r| {
                let diff = r - mean;
                diff * diff
            })
            .sum::<f64>()
            / (daily_returns.len() as f64 - 1.0)
    } else {
        0.0
    };

    let daily_vol = variance.sqrt();

    let sharpe_like = if daily_vol > 0.0 {
        mean / daily_vol * 252.0_f64.sqrt()
    } else {
        f64::NAN
    };

    PathSummary {
        test,
        run,
        num_days: daily_returns.len(),
        final_equity: equity,
        total_return: equity / initial_capital - 1.0,
        max_drawdown,
        win_rate: wins as f64 / daily_returns.len() as f64,
        avg_daily_return: mean,
        daily_vol,
        sharpe_like,
    }
}

pub fn summarize_distribution(
    runs: &[PathSummary],
    actual_total_return: f64,
) -> Vec<DistributionSummary> {
    use std::collections::HashMap;

    let mut by_test: HashMap<String, Vec<f64>> = HashMap::new();

    for run in runs {
        by_test
            .entry(run.test.clone())
            .or_default()
            .push(run.total_return);
    }

    let mut rows = Vec::new();

    for (test, mut vals) in by_test {
        vals.sort_by(|a, b| a.partial_cmp(b).unwrap());

        let n = vals.len();

        let mean = vals.iter().sum::<f64>() / n as f64;
        let median = percentile(&vals, 0.50);
        let p05 = percentile(&vals, 0.05);
        let p95 = percentile(&vals, 0.95);

        let below_actual = vals.iter().filter(|&&v| v < actual_total_return).count();
        let beats_actual = vals.iter().filter(|&&v| v >= actual_total_return).count();

        rows.push(DistributionSummary {
            test,
            runs: n,
            actual_total_return,
            mc_mean_total_return: mean,
            mc_median_total_return: median,
            mc_p05_total_return: p05,
            mc_p95_total_return: p95,
            actual_percentile: below_actual as f64 / n as f64,
            prob_random_beats_actual: beats_actual as f64 / n as f64,
        });
    }

    rows.sort_by(|a, b| a.test.cmp(&b.test));
    rows
}

fn percentile(sorted_vals: &[f64], q: f64) -> f64 {
    if sorted_vals.is_empty() {
        return f64::NAN;
    }

    let idx = ((sorted_vals.len() - 1) as f64 * q).round() as usize;
    sorted_vals[idx]
}
