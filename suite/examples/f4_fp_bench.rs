//! Wall-clock benchmark for the degree-bounded F4 over `F_p`
//! (`cryptanalysis::f4_fp`): random dense systems, fixed seeds.
//!
//! Prints one JSON line per case with the median time over `repeats`
//! runs and a fingerprint of the output basis, so two revisions of the
//! engine can be compared for speed *and* for identical output.
//!
//! ```text
//! cargo run --release --example f4_fp_bench -- [repeats]
//! ```

use cryptanalysis_suite::cryptanalysis::f4_fp::{f4, solve, F4Options, Ordering, Poly, Verdict};
use serde_json::json;
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};

fn monomials(n: usize, d: u32) -> Vec<Vec<u32>> {
    fn rec(n: usize, d: u32, cur: &mut Vec<u32>, out: &mut Vec<Vec<u32>>) {
        if cur.len() == n {
            out.push(cur.clone());
            return;
        }
        let used: u32 = cur.iter().sum();
        for k in 0..=d - used {
            cur.push(k);
            rec(n, d, cur, out);
            cur.pop();
        }
    }
    let mut out = Vec::new();
    rec(n, d, &mut Vec::new(), &mut out);
    out
}

fn system(n: usize, m: usize, d: u32, p: u64, seed: u64) -> Vec<Poly> {
    let mut s = seed | 1;
    let mut rnd = move || {
        s ^= s << 13;
        s ^= s >> 7;
        s ^= s << 17;
        s
    };
    let monos = monomials(n, d);
    (0..m)
        .map(|_| monos.iter().map(|e| (e.clone(), rnd() % p)).collect())
        .collect()
}

fn fingerprint<T: Hash>(x: &T) -> String {
    let mut h = DefaultHasher::new();
    x.hash(&mut h);
    format!("{:016x}", h.finish())
}

fn median(mut v: Vec<f64>) -> f64 {
    v.sort_by(|a, b| a.total_cmp(b));
    v[v.len() / 2]
}

fn main() {
    let repeats: usize = std::env::args()
        .nth(1)
        .map(|s| s.parse().expect("repeats"))
        .unwrap_or(3);
    // (name, n, m, deg, p, max_degree, solve?)
    let cases: &[(&str, usize, usize, u32, u64, u32, bool)] = &[
        ("quad_n4_p31", 4, 4, 2, 31, 12, true),
        ("quad_n5_p31", 5, 5, 2, 31, 12, false),
        ("quad_n6_p65521", 6, 6, 2, 65521, 12, false),
        ("quad_n7_p65521", 7, 7, 2, 65521, 12, false),
        ("cubic_n3_p29", 3, 3, 3, 29, 12, true),
        ("cubic_n4_p31", 4, 4, 3, 31, 14, false),
        ("quart_n3_p31", 3, 3, 4, 31, 16, true),
        ("overdet_n6_m9_p101", 6, 9, 2, 101, 10, false),
    ];
    for &(name, n, m, d, p, dmax, do_solve) in cases {
        let sys = system(
            n,
            m,
            d,
            p,
            0x9e37_79b9_7f4a_7c15 ^ (n as u64 * 131 + d as u64),
        );
        let opts = F4Options::new(Ordering::Grevlex, dmax);
        let mut times = Vec::new();
        let mut fp = String::new();
        let mut shape = (0, 0, 0, 0);
        for _ in 0..repeats {
            let r = f4(&sys, n, p, &opts);
            times.push(r.ms);
            fp = fingerprint(&r.basis);
            shape = (r.steps, r.max_rows, r.max_cols, r.basis.len());
        }
        let mut line = json!({
            "case": name, "f4_ms": median(times), "basis_fp": fp,
            "steps": shape.0, "max_rows": shape.1, "max_cols": shape.2, "basis_len": shape.3,
        });
        if do_solve {
            let mut times = Vec::new();
            let mut sols = 0;
            let mut sfp = String::new();
            for _ in 0..repeats {
                let s = solve(&sys, n, p, &opts);
                times.push(s.ms);
                if let Verdict::Solutions(v) = &s.verdict {
                    sols = v.len();
                }
                sfp = fingerprint(&format!("{:?}", s.verdict));
            }
            line["solve_ms"] = json!(median(times));
            line["solutions"] = json!(sols);
            line["solve_fp"] = json!(sfp);
        }
        println!("{line}");
    }
}
