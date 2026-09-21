//! EXP-G — widen the algebraic discriminator (P3-alg) into a correlation
//! curve.
//!
//! Iteration 5 (EXP-F in `ffd_breakthrough_loop`) found a perfect inverse
//! rank order between the early Macaulay rank defect `δ` and the refutation
//! degree `D*` — but over only **3 cells** at a single operating point. A
//! perfect ρ_s on three points is suggestive, not a law. EXP-G pools
//! `(early_defect, D*)` cell-means across **many** `(n,n')` operating points
//! (every `n' | n` in range, so the subfield exists) and all three families,
//! with several reseeded Random cells per point, then computes ONE Spearman
//! and OLS slope over the whole cloud.
//!
//! Each cell = mean over `trials` random `(b, x₃)`. Output: a per-cell table,
//! the pooled correlation, and a JSON snapshot to `experiments/`.
//!
//! Run: `cargo run --release --example ffd_expg_curve`

use cryptanalysis_suite::binary_ecc::F2mElement;
use cryptanalysis_suite::cryptanalysis::descent_algebraic::{early_defect, rank_profile};
use cryptanalysis_suite::cryptanalysis::descent_expansion::enumerate_irreducibles;
use cryptanalysis_suite::cryptanalysis::descent_lowgamma::{
    descend_on_subspace, measure_on_subspace, BasisFamily, FactorSubspace,
};
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use std::time::{SystemTime, UNIX_EPOCH};

struct Cell {
    n: u32,
    n_sub: u32,
    family: BasisFamily,
    tag: String,
    early_defect: f64,
    dstar: f64,
    n_trials: u32,
    censored: u32,
}

fn rand_nz(rng: &mut StdRng, n: u32) -> F2mElement {
    loop {
        let bits: Vec<u32> = (0..n).filter(|_| rng.gen::<bool>()).collect();
        let e = F2mElement::from_bit_positions(&bits, n);
        if !e.is_zero() {
            return e;
        }
    }
}

/// One cell: average early-defect (cutoff 3) and D* over `trials` targets for
/// a fixed subspace `v`. Returns `None` if no target produced a D*.
fn run_cell(
    n: u32,
    n_sub: u32,
    family: BasisFamily,
    tag: String,
    v: &FactorSubspace,
    irr: &cryptanalysis_suite::binary_ecc::IrreduciblePoly,
    trials: u32,
    d_cap: u32,
    rng: &mut StdRng,
) -> Option<Cell> {
    // The early defect only needs degrees ≤ cutoff(3); cap the profile so it
    // is cheap even at large 2n'. The refutation scan is capped at `d_cap`:
    // targets that have not refuted by then are *censored* (counted, not
    // averaged). Censoring drops the highest-D* targets, so it can only make
    // the negative defect↔D* correlation harder to see — never inflate it.
    let prof_dmax = (3).min(2 * n_sub);
    let scan_dmax = d_cap.min(2 * n_sub + 2);
    let mut de = Vec::new();
    let mut ds = Vec::new();
    let mut censored = 0u32;
    for _ in 0..trials {
        let b = rand_nz(rng, n);
        let x3 = rand_nz(rng, n);
        let eqs = descend_on_subspace(n, v, irr, &b, &x3);
        let prof = rank_profile(&eqs, 2 * n_sub, n, prof_dmax);
        de.push(early_defect(&prof, 3));
        let pt = measure_on_subspace(n, v, irr, &b, &x3, scan_dmax);
        match pt.refutation_degree {
            Some(d) => ds.push(d as f64),
            None => censored += 1,
        }
    }
    if ds.is_empty() || de.is_empty() {
        return None;
    }
    Some(Cell {
        n,
        n_sub,
        family,
        tag,
        early_defect: de.iter().sum::<f64>() / de.len() as f64,
        dstar: ds.iter().sum::<f64>() / ds.len() as f64,
        n_trials: trials,
        censored,
    })
}

/// Spearman rank correlation (average-rank ties); `None` if degenerate.
fn spearman(xs: &[f64], ys: &[f64]) -> Option<f64> {
    let rank = |v: &[f64]| -> Vec<f64> {
        let mut idx: Vec<usize> = (0..v.len()).collect();
        idx.sort_by(|&a, &b| v[a].partial_cmp(&v[b]).unwrap());
        let mut r = vec![0.0; v.len()];
        let mut i = 0;
        while i < idx.len() {
            let mut j = i;
            while j + 1 < idx.len() && v[idx[j + 1]] == v[idx[i]] {
                j += 1;
            }
            let avg = (i + j) as f64 / 2.0 + 1.0;
            for &k in &idx[i..=j] {
                r[k] = avg;
            }
            i = j + 1;
        }
        r
    };
    let (rx, ry) = (rank(xs), rank(ys));
    let n = rx.len() as f64;
    let mx = rx.iter().sum::<f64>() / n;
    let my = ry.iter().sum::<f64>() / n;
    let mut num = 0.0;
    let mut dx = 0.0;
    let mut dy = 0.0;
    for i in 0..rx.len() {
        num += (rx[i] - mx) * (ry[i] - my);
        dx += (rx[i] - mx).powi(2);
        dy += (ry[i] - my).powi(2);
    }
    if dx == 0.0 || dy == 0.0 {
        return None;
    }
    Some(num / (dx * dy).sqrt())
}

/// OLS slope of y on x (D* per unit defect).
fn ols_slope(xs: &[f64], ys: &[f64]) -> f64 {
    let n = xs.len() as f64;
    let sx: f64 = xs.iter().sum();
    let sy: f64 = ys.iter().sum();
    let sxx: f64 = xs.iter().map(|x| x * x).sum();
    let sxy: f64 = xs.iter().zip(ys).map(|(x, y)| x * y).sum();
    let denom = n * sxx - sx * sx;
    if denom.abs() < 1e-12 {
        0.0
    } else {
        (n * sxy - sx * sy) / denom
    }
}

fn pearson(xs: &[f64], ys: &[f64]) -> Option<f64> {
    let n = xs.len() as f64;
    let mx = xs.iter().sum::<f64>() / n;
    let my = ys.iter().sum::<f64>() / n;
    let mut num = 0.0;
    let mut dx = 0.0;
    let mut dy = 0.0;
    for i in 0..xs.len() {
        num += (xs[i] - mx) * (ys[i] - my);
        dx += (xs[i] - mx).powi(2);
        dy += (ys[i] - my).powi(2);
    }
    if dx == 0.0 || dy == 0.0 {
        return None;
    }
    Some(num / (dx * dy).sqrt())
}

fn main() {
    let seed = std::env::args()
        .nth(1)
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(0xE6C0);
    // Operating points with n' | n (so the subfield factor base exists).
    // The reach extension (iteration 7): the wall is NOT raw 2n' — refuting
    // targets resolve at low degree even at 2n'=14; it is the non-refuting
    // targets that ran the scan to the exponential tail. With the single-pass
    // rank+refute and a `d_cap` (censoring), the big critical points
    // (12,6)→2n'=12 and (14,7)→2n'=14 become affordable. `(trials, d_cap)`
    // per point: fewer trials + tighter cap as the cost grows.
    let points: &[(u32, u32, u32, u32)] = &[
        // (n, n', trials, d_cap)
        (4, 2, 20, 8),
        (6, 2, 20, 8),
        (6, 3, 20, 8),
        (8, 2, 20, 8),
        (8, 4, 20, 8),
        (9, 3, 20, 8),
        (10, 2, 20, 8),
        (10, 5, 20, 7),
        (12, 6, 12, 6), // 2n'=12, extended reach
        (14, 7, 8, 6),  // 2n'=14, extended reach
    ];
    let random_reseeds = 3u32; // distinct Random bases per point → more cloud points

    let mut cells: Vec<Cell> = Vec::new();
    let mut rng = StdRng::seed_from_u64(seed);

    for &(n, n_sub, trials, d_cap) in points {
        let Some(irr) = enumerate_irreducibles(n, 1).into_iter().next() else {
            continue;
        };
        // Subfield (unique) — exists because n_sub | n by construction.
        if let Some(v) = FactorSubspace::build(BasisFamily::Subfield, n, n_sub, &irr, 0) {
            if let Some(c) = run_cell(
                n,
                n_sub,
                BasisFamily::Subfield,
                "subfield".into(),
                &v,
                &irr,
                trials,
                d_cap,
                &mut rng,
            ) {
                cells.push(c);
            }
        }
        // Coordinate (unique baseline).
        if let Some(v) = FactorSubspace::build(BasisFamily::Coordinate, n, n_sub, &irr, 0) {
            if let Some(c) = run_cell(
                n,
                n_sub,
                BasisFamily::Coordinate,
                "coord".into(),
                &v,
                &irr,
                trials,
                d_cap,
                &mut rng,
            ) {
                cells.push(c);
            }
        }
        // Several reseeded Random bases.
        for r in 0..random_reseeds {
            let bseed = seed ^ ((n as u64) << 16) ^ ((n_sub as u64) << 8) ^ r as u64 ^ 0x7000;
            if let Some(v) = FactorSubspace::build(BasisFamily::Random, n, n_sub, &irr, bseed) {
                if let Some(c) = run_cell(
                    n,
                    n_sub,
                    BasisFamily::Random,
                    format!("rand{r}"),
                    &v,
                    &irr,
                    trials,
                    d_cap,
                    &mut rng,
                ) {
                    cells.push(c);
                }
            }
        }
    }

    // ── Report ──
    println!("════════════════════════════════════════════════════════════════");
    println!("EXP-G — algebraic discriminator curve (defect ↔ D*), seed={seed}");
    let total_censored: u32 = cells.iter().map(|c| c.censored).sum();
    println!(
        "  {} cells over {} operating points; {total_censored} censored targets (D*>d_cap, dropped)",
        cells.len(),
        points.len()
    );
    println!(
        "  {:>4} {:>4} {:<10} {:>13} {:>9} {:>6}",
        "n", "n'", "family", "early-defect", "D* mean", "cens"
    );
    for c in &cells {
        println!(
            "  {:>4} {:>4} {:<10} {:>13.4} {:>9.3} {:>4}/{}",
            c.n, c.n_sub, c.tag, c.early_defect, c.dstar, c.censored, c.n_trials
        );
    }

    let xs: Vec<f64> = cells.iter().map(|c| c.early_defect).collect();
    let ys: Vec<f64> = cells.iter().map(|c| c.dstar).collect();
    let rho = spearman(&xs, &ys);
    let r = pearson(&xs, &ys);
    let slope = ols_slope(&xs, &ys);

    println!("\n  pooled Spearman ρ_s = {}", fmt_opt(rho));
    println!("  pooled Pearson  r   = {}", fmt_opt(r));
    println!("  OLS slope dD*/d(defect) = {slope:+.3}");

    // Within-operating-point check: does the ordering hold at EACH point,
    // controlling for n? (defect should still beat random within a point).
    let mut within_ok = 0usize;
    let mut within_total = 0usize;
    for &(n, n_sub, _, _) in points {
        let grp: Vec<&Cell> = cells
            .iter()
            .filter(|c| c.n == n && c.n_sub == n_sub)
            .collect();
        if grp.len() < 2 {
            continue;
        }
        within_total += 1;
        let gx: Vec<f64> = grp.iter().map(|c| c.early_defect).collect();
        let gy: Vec<f64> = grp.iter().map(|c| c.dstar).collect();
        if let Some(gr) = spearman(&gx, &gy) {
            if gr <= -0.5 {
                within_ok += 1;
            }
        }
    }
    println!(
        "  within-(n,n') inverse ordering holds at {within_ok}/{within_total} multi-cell points"
    );

    // Regime split. The over-determined points (2n' ≪ n) floor D* at 2 by
    // the Nullstellensatz collapse (P6) — defect varies but D* is saturated,
    // so they cannot show the law. The CRITICAL operating point 2n'=n (the
    // ECDLP-relevant regime) is where D* has room to move and the law should
    // be cleanest. Report both.
    let crit: Vec<&Cell> = cells.iter().filter(|c| 2 * c.n_sub == c.n).collect();
    let over: Vec<&Cell> = cells.iter().filter(|c| 2 * c.n_sub < c.n).collect();
    let sub_split = |g: &[&Cell]| -> (Option<f64>, f64) {
        let gx: Vec<f64> = g.iter().map(|c| c.early_defect).collect();
        let gy: Vec<f64> = g.iter().map(|c| c.dstar).collect();
        (spearman(&gx, &gy), ols_slope(&gx, &gy))
    };
    let (crit_rho, crit_slope) = sub_split(&crit);
    let (over_rho, over_slope) = sub_split(&over);
    println!(
        "\n  CRITICAL regime (2n'=n, {} cells): ρ_s = {}, slope {crit_slope:+.3}",
        crit.len(),
        fmt_opt(crit_rho)
    );
    println!(
        "  OVER-determined (2n'<n, {} cells): ρ_s = {}, slope {over_slope:+.3}  (D* floored at 2 by P6)",
        over.len(),
        fmt_opt(over_rho)
    );

    let verdict = match rho {
        Some(rr) if rr <= -0.6 => "SUPPORTED (pooled ρ_s ≤ −0.6: the defect↔D* law holds across operating points, not just one)",
        Some(rr) if rr.abs() < 0.2 => "KILLED (pooled correlation vanished once points were pooled)",
        Some(_) => "INCONCLUSIVE (suggestive but below the −0.6 bar)",
        None => "BLOCKED (degenerate)",
    };
    println!("\n  GATE G-P3-alg (pooled): {verdict}");

    // ── Snapshot ──
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let cell_json = |c: &Cell| {
        format!(
            "{{\"n\":{},\"n_sub\":{},\"family\":\"{:?}\",\"tag\":\"{}\",\"early_defect\":{:.5},\"dstar\":{:.4},\"trials\":{},\"censored\":{}}}",
            c.n, c.n_sub, c.family, c.tag, c.early_defect, c.dstar, c.n_trials, c.censored
        )
    };
    let arr = cells.iter().map(cell_json).collect::<Vec<_>>().join(",");
    let json = format!(
        "{{\n  \"schema\": \"ffd_expg_curve/v3\",\n  \"seed\": {seed},\n  \"generated_at\": {ts},\n  \"total_censored\": {total_censored},\n  \"n_cells\": {},\n  \"spearman_rho\": {},\n  \"pearson_r\": {},\n  \"ols_slope_dstar_per_defect\": {:.5},\n  \"within_point_ordering\": \"{within_ok}/{within_total}\",\n  \"critical_regime\": {{\"cells\": {}, \"spearman_rho\": {}, \"ols_slope\": {:.5}}},\n  \"overdetermined_regime\": {{\"cells\": {}, \"spearman_rho\": {}, \"ols_slope\": {:.5}}},\n  \"cells\": [{arr}]\n}}\n",
        cells.len(),
        rho.map(|v| format!("{v:.5}")).unwrap_or_else(|| "null".into()),
        r.map(|v| format!("{v:.5}")).unwrap_or_else(|| "null".into()),
        slope,
        crit.len(),
        crit_rho.map(|v| format!("{v:.5}")).unwrap_or_else(|| "null".into()),
        crit_slope,
        over.len(),
        over_rho.map(|v| format!("{v:.5}")).unwrap_or_else(|| "null".into()),
        over_slope,
    );
    let path = "experiments/ffd_expg_curve.json";
    match std::fs::write(path, &json) {
        Ok(_) => println!("\n[snapshot] wrote {path}"),
        Err(e) => println!("\n[snapshot] FAILED to write {path}: {e}"),
    }
    println!("════════════════════════════════════════════════════════════════");
}

fn fmt_opt(v: Option<f64>) -> String {
    v.map(|x| format!("{x:+.4}")).unwrap_or_else(|| "—".into())
}
