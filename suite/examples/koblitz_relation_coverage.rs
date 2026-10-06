//! What the relation count is actually buying: coverage, or rank?
//!
//! Collection is the dominant phase, and its cost is proportional to the
//! number of relations banked, so the question of *why* a run needs 407
//! relations for 192 columns decides whether there is anything left to
//! win.  Two candidate answers, and they call for opposite fixes:
//!
//!   * **rank** — the relations are dependent, and the excess is the
//!     price of independence.  Nothing to do but collect more.
//!   * **coverage** — a column whose log is never mentioned cannot be
//!     solved for, and relations arrive at uniformly random columns, so
//!     the last few columns cost a coupon-collector tail.  That tail is
//!     addressable: aim the scan window at the columns still missing.
//!
//! This replays a finished run's relations in arrival order and reports
//! the relation index at which each condition is first met.  It computes
//! nothing new about the run; it re-reads what the run already banked.
//!
//!     cargo run --release --example koblitz_relation_coverage -- \
//!         41 1 15300 <run-dir>/relations
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;
use num_bigint::BigUint;
use std::collections::BTreeSet;

/// Rank over `Z/rZ` by Gaussian elimination, `r` prime (a subgroup
/// order), carried incrementally so each new row is cheap.
struct Rank {
    r: u64,
    /// Reduced rows, keyed by pivot column.
    rows: Vec<Option<Vec<u64>>>,
}

fn mulmod(a: u64, b: u64, m: u64) -> u64 {
    ((a as u128 * b as u128) % m as u128) as u64
}

fn powmod(mut a: u64, mut e: u64, m: u64) -> u64 {
    let mut acc = 1u64;
    while e > 0 {
        if e & 1 == 1 {
            acc = mulmod(acc, a, m);
        }
        a = mulmod(a, a, m);
        e >>= 1;
    }
    acc
}

impl Rank {
    fn new(r: u64, cols: usize) -> Self {
        Self {
            r,
            rows: vec![None; cols],
        }
    }

    /// Insert a row; returns true when it raised the rank.
    fn insert(&mut self, mut row: Vec<u64>) -> bool {
        for c in 0..row.len() {
            if row[c] == 0 {
                continue;
            }
            match &self.rows[c] {
                None => {
                    let inv = powmod(row[c], self.r - 2, self.r);
                    for v in row.iter_mut() {
                        *v = mulmod(*v, inv, self.r);
                    }
                    self.rows[c] = Some(row);
                    return true;
                }
                Some(pivot) => {
                    let f = row[c];
                    for (v, p) in row.iter_mut().zip(pivot.iter()) {
                        *v = (*v + self.r - mulmod(f, *p, self.r)) % self.r;
                    }
                }
            }
        }
        false
    }

    fn rank(&self) -> usize {
        self.rows.iter().filter(|x| x.is_some()).count()
    }

    /// Whether this column carries a pivot.  A column without one is a
    /// direction the system has not pinned down, so it is exactly what a
    /// rank-limited run would want to aim at.
    fn has_pivot(&self, c: usize) -> bool {
        self.rows.get(c).map(Option::is_some).unwrap_or(false)
    }
}

fn main() {
    let mut args = std::env::args().skip(1);
    let degree: u32 = args.next().and_then(|s| s.parse().ok()).expect("degree");
    let seed: u64 = args.next().and_then(|s| s.parse().ok()).expect("seed");
    let points: usize = args.next().and_then(|s| s.parse().ok()).expect("points");
    let dir = args.next().expect("relations dir");

    let kc = KoblitzCurve::new(0, degree).expect("curve");
    let r = kc.subgroup_order.to_u64_digits()[0];
    let fb = build_subgroup_orbit_factor_base(&kc, seed, points).expect("factor base");
    let cols = fb.signed_orbits.len();
    println!(
        "base {} points, {} columns, r = 2^{:.1}",
        fb.points.len(),
        cols,
        (r as f64).log2()
    );

    // lambda^k mod r, for every rotation a signed orbit can carry.
    let lam = (&kc.lambda % BigUint::from(r))
        .to_u64_digits()
        .first()
        .copied()
        .unwrap_or(0);
    let mut lampow = vec![1u64; 2 * degree as usize + 1];
    for k in 1..lampow.len() {
        lampow[k] = mulmod(lampow[k - 1], lam, r);
    }

    // Relations in arrival order: unit files in index order, and within
    // a unit the trials are already sorted.
    let mut files: Vec<_> = std::fs::read_dir(&dir)
        .expect("relations dir")
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().map(|x| x == "json").unwrap_or(false))
        .collect();
    files.sort();

    let mut seen: BTreeSet<usize> = BTreeSet::new();
    let mut rank = Rank::new(r, cols);
    let (mut covered_at, mut ranked_at) = (None, None);
    // Coverage and rank after each relation, so the two can be read
    // against each other rather than only at their completion points.
    let mut curve: Vec<(usize, usize)> = Vec::new();
    let mut total = 0usize;
    for f in &files {
        let text = std::fs::read_to_string(f).expect("read unit");
        let doc: serde_json::Value = serde_json::from_str(&text).expect("parse unit");
        for rel in doc["relations"].as_array().expect("relations").iter() {
            total += 1;
            let mut row = vec![0u64; cols];
            for idx in rel["points"].as_array().expect("points") {
                let i = idx.as_u64().expect("index") as usize;
                let (c, k, neg) = fb.signed_orbit_of[i];
                seen.insert(c);
                let coeff = lampow[k as usize % lampow.len()];
                row[c] = if neg {
                    (row[c] + r - coeff) % r
                } else {
                    (row[c] + coeff) % r
                };
            }
            rank.insert(row);
            curve.push((seen.len(), rank.rank()));
            if covered_at.is_none() && seen.len() == cols {
                covered_at = Some(total);
            }
            if ranked_at.is_none() && rank.rank() == cols {
                ranked_at = Some(total);
            }
        }
    }
    println!("relations banked          {total}");
    println!("columns covered           {}/{cols}", seen.len());
    println!("final rank                {}/{cols}", rank.rank());
    match covered_at {
        Some(n) => println!("all columns covered after {n} relations"),
        None => println!("all columns covered after  never"),
    }
    match ranked_at {
        Some(n) => println!("full rank reached after   {n} relations"),
        None => println!("full rank reached after    never"),
    }
    // Where the two diverge is the whole question: a run whose rank
    // tracks its coverage is coverage-limited and can be helped by
    // aiming the scan; one whose rank lags is rank-limited, and no
    // choice of which summands to scan can lower its relation count.
    println!("\nrelations   columns covered   rank");
    let mut marks: Vec<usize> = vec![cols / 2, cols, cols * 5 / 4, cols * 3 / 2, cols * 7 / 4];
    if let Some(c) = covered_at {
        marks.push(c);
    }
    marks.push(total);
    marks.sort();
    marks.dedup();
    for m in marks {
        if m == 0 || m > curve.len() {
            continue;
        }
        let (seen_n, rank_n) = curve[m - 1];
        println!(
            "{m:>9}   {seen_n:>15}   {rank_n:>4}{}",
            if seen_n == cols && rank_n < cols {
                "   <- covered, not yet full rank"
            } else {
                ""
            }
        );
    }
    // What the columns without a pivot look like at the moment the row
    // count first reaches the column count — the earliest a system can
    // possibly have full rank.  If they are the columns mentioned
    // fewest times, a multiplicity counter is enough to aim at them and
    // no linear algebra is needed to find them.
    if curve.len() >= cols {
        let mut rank2 = Rank::new(r, cols);
        let mut mult = vec![0usize; cols];
        let mut n = 0usize;
        'outer: for f in &files {
            let text = std::fs::read_to_string(f).expect("read unit");
            let doc: serde_json::Value = serde_json::from_str(&text).expect("parse unit");
            for rel in doc["relations"].as_array().expect("relations").iter() {
                let mut row = vec![0u64; cols];
                for idx in rel["points"].as_array().expect("points") {
                    let i = idx.as_u64().expect("index") as usize;
                    let (c, k, neg) = fb.signed_orbit_of[i];
                    mult[c] += 1;
                    let coeff = lampow[k as usize % lampow.len()];
                    row[c] = if neg {
                        (row[c] + r - coeff) % r
                    } else {
                        (row[c] + coeff) % r
                    };
                }
                rank2.insert(row);
                n += 1;
                if n == cols {
                    break 'outer;
                }
            }
        }
        let pivotless: Vec<usize> = (0..cols).filter(|&c| !rank2.has_pivot(c)).collect();
        let mut hist = std::collections::BTreeMap::new();
        for &m in &mult {
            *hist.entry(m).or_insert(0usize) += 1;
        }
        println!("\nat {n} relations (= columns), rank {}", rank2.rank());
        println!("  mention counts per column: {hist:?}");
        println!("  columns without a pivot: {} of {cols}", pivotless.len());
        let mut worst: Vec<(usize, usize)> = pivotless.iter().map(|&c| (mult[c], c)).collect();
        worst.sort();
        let shown: Vec<String> = worst
            .iter()
            .take(12)
            .map(|(m, c)| format!("col {c} mentioned {m}x"))
            .collect();
        println!("  {}", shown.join(", "));
        let least = mult.iter().copied().min().unwrap_or(0);
        let starved: Vec<usize> = (0..cols).filter(|&c| mult[c] == least).collect();
        println!(
            "  least-mentioned columns ({least}x): {} of them; {} of those lack a pivot",
            starved.len(),
            starved.iter().filter(|&&c| !rank2.has_pivot(c)).count()
        );
    }
    if let (Some(c), Some(k)) = (covered_at, ranked_at) {
        println!(
            "\ncoverage is the binding constraint: {}",
            if c >= k {
                "yes"
            } else {
                "no -- rank lags coverage"
            }
        );
        println!(
            "coupon-collector tail = {} relations ({:.0}% of the run)",
            c.max(k),
            100.0 * c.max(k) as f64 / total as f64
        );
    }
}
