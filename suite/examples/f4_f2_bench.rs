//! Wall-clock benchmark for the Boolean-ring F4 (`cryptanalysis::pq_f4_f2`)
//! and matrix-F5 steps (`cryptanalysis::matrix_f5_f2`)
//! on random quadratic systems with a planted solution, fixed seeds.
//!
//! Prints one JSON line per case: median wall time over `repeats` runs, the
//! build/eliminate split, the counted units, and a fingerprint of the
//! reduced basis so two revisions can be compared for identical output.
//!
//! ```text
//! cargo run --release --example f4_f2_bench -- [repeats]
//! ```

use cryptanalysis_suite::cryptanalysis::matrix_f5_f2::matrix_f5_f2;
use cryptanalysis_suite::cryptanalysis::pq_f4_f2::groebner_basis_f4;
use cryptanalysis_suite::cryptanalysis::pq_groebner_f2::{
    groebner_basis_f2_stats, F2BoolMono, F2BoolPoly,
};
use serde_json::json;
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};

fn system(n: usize, m: usize, seed: u64) -> Vec<F2BoolPoly> {
    let mut s = seed | 1;
    let mut rnd = move || {
        s ^= s << 13;
        s ^= s >> 7;
        s ^= s << 17;
        s
    };
    let planted = rnd() & ((1u64 << n) - 1);
    let mut monos: Vec<u64> = vec![0];
    for i in 0..n {
        monos.push(1 << i);
        for j in i + 1..n {
            monos.push((1 << i) | (1 << j));
        }
    }
    (0..m)
        .map(|_| {
            let chosen: Vec<u64> = monos.iter().copied().filter(|_| rnd() & 1 == 1).collect();
            // fix the constant so the planted point is a zero
            let val = chosen.iter().filter(|&&t| t & planted == t).count() & 1;
            let mut terms: Vec<F2BoolMono> =
                chosen.into_iter().map(F2BoolMono::from_mask).collect();
            if val == 1 {
                // toggles the constant term: `from_monos` cancels pairs
                terms.push(F2BoolMono::from_mask(0));
            }
            F2BoolPoly::from_monos(terms, n)
        })
        .collect()
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
    // optional: skip cases with more than this many variables
    let max_n: usize = std::env::args()
        .nth(2)
        .map(|s| s.parse().expect("max_n"))
        .unwrap_or(usize::MAX);
    for &(n, m) in &[
        (12usize, 12usize),
        (14, 14),
        (16, 16),
        (16, 24),
        (18, 18),
        (20, 20),
        (20, 30),
    ] {
        if n > max_n {
            continue;
        }
        let sys = system(n, m, 0x2545_f491_4f6c_dd1d ^ ((n * 64 + m) as u64));
        let mut walls = Vec::new();
        let mut last = None;
        for _ in 0..repeats {
            let (gb, st) = groebner_basis_f4(sys.clone(), n, None);
            walls.push(st.wall_ns as f64 / 1e6);
            last = Some((gb, st));
        }
        let (gb, st) = last.unwrap();
        let mut h = DefaultHasher::new();
        for p in &gb {
            for t in &p.terms {
                t.mask.hash(&mut h);
            }
            u64::MAX.hash(&mut h);
        }
        println!(
            "{}",
            json!({
                "case": format!("n{n}_m{m}"), "wall_ms": median(walls),
                "build_ms": st.build_ns as f64 / 1e6, "eliminate_ms": st.eliminate_ns as f64 / 1e6,
                "word_xors": st.word_xors, "divisor_tests": st.divisor_tests,
                "steps": st.steps, "basis_len": st.basis_len, "basis_fp": format!("{:016x}", h.finish()),
            })
        );
    }
    // Buchberger (the reference engine) on the smaller systems
    for &(n, m) in &[(8usize, 8usize), (10, 10), (12, 12), (12, 16), (14, 14)] {
        if n > max_n {
            continue;
        }
        let sys = system(n, m, 0x2545_f491_4f6c_dd1d ^ ((n * 64 + m) as u64));
        let mut walls = Vec::new();
        let mut last = None;
        for _ in 0..repeats {
            let (gb, st) = groebner_basis_f2_stats(sys.clone(), n);
            walls.push(st.wall_ns as f64 / 1e6);
            last = Some((gb, st));
        }
        let (gb, st) = last.unwrap();
        let mut h = DefaultHasher::new();
        for p in &gb {
            for t in &p.terms {
                t.mask.hash(&mut h);
            }
            u64::MAX.hash(&mut h);
        }
        println!(
            "{}",
            json!({
                "case": format!("bb_n{n}_m{m}"), "wall_ms": median(walls),
                "mono_ops": st.mono_ops, "reduction_steps": st.reduction_steps,
                "spolys": st.spolys, "pairs_chain_skipped": st.pairs_chain_skipped,
                "field_pairs": st.field_pairs, "basis_len": st.basis_len,
                "basis_fp": format!("{:016x}", h.finish()),
            })
        );
    }
    // matrix-F5 steps (criterion + elimination) on the same systems
    for &(n, m, degree) in &[
        (12usize, 12usize, 4u32),
        (16, 16, 3),
        (16, 16, 4),
        (20, 20, 3),
        (20, 20, 4),
        (24, 24, 3),
        (24, 24, 4),
    ] {
        if n > max_n {
            continue;
        }
        let sys = system(n, m, 0x2545_f491_4f6c_dd1d ^ ((n * 64 + m) as u64));
        let mut walls = Vec::new();
        let mut last = None;
        for _ in 0..repeats {
            let t = std::time::Instant::now();
            let r = matrix_f5_f2(&sys, n, degree).expect("within size limits");
            walls.push(t.elapsed().as_secs_f64() * 1e3);
            last = Some(r);
        }
        let (rows, rep) = last.unwrap();
        let mut h = DefaultHasher::new();
        for p in &rows {
            for t in &p.terms {
                t.mask.hash(&mut h);
            }
            u64::MAX.hash(&mut h);
        }
        println!(
            "{}",
            json!({
                "case": format!("f5_n{n}_m{m}_d{degree}"), "wall_ms": median(walls),
                "criterion_word_ops": rep.criterion_word_ops, "reduce_word_ops": rep.reduce_word_ops,
                "rows_pruned": rep.rows_pruned, "rank": rep.rank, "rows_fp": format!("{:016x}", h.finish()),
            })
        );
    }
}
