//! **L0 of the performance plan** (`docs/ic/perf/OPTIMIZATION_PLAN.md`):
//! the `F_2` elimination kernel on its own, head to head with the kernel
//! the Gröbner oracle used before it, on the Macaulay matrices that oracle
//! really reduces.
//!
//! ```bash
//! cargo run --release --example gf2_elim_bench -- [--reps 3] [--out FILE] [--quick]
//! ```
//!
//! Every cell is a frozen decomposition system (`koblitz_bench::
//! decomposition_macaulay`: curve degree `n`, summands `m`, Macaulay
//! degree `d`, target seed) or a frozen random matrix.  Each kernel
//! reduces its own copy to reduced row echelon form, which is unique, so
//! the two results must agree **bit for bit**; a cell where they do not
//! aborts the run, since a speedup on a wrong answer means nothing.
//!
//! Reported per cell: shape, rank, both kernels' best wall time over
//! `--reps` repetitions, their ratio, and both kernels' 64-bit word XORs
//! (the stage's unit; the new kernel's count is lower because a row
//! meets each block once).  This is a kernel diagnostic, not an
//! end-to-end number (`AGENTS.md` §8).

use cryptanalysis_suite::cryptanalysis::gf2_elim;
use cryptanalysis_suite::cryptanalysis::koblitz_bench::{decomposition_macaulay, rref_f2_legacy};
use rand::{rngs::StdRng, Rng, SeedableRng};
use std::time::Instant;

enum Source {
    /// `(n, factor_index, m, degree, seed)`.
    Decomposition(u32, usize, usize, u32, u64),
    /// `(rows, cols, density, seed)`.
    Random(usize, usize, f64, u64),
}

struct Cell {
    name: &'static str,
    source: Source,
    quick: bool,
}

const CELLS: &[Cell] = &[
    Cell {
        name: "K/2^23 m2 d3",
        source: Source::Decomposition(23, 0, 2, 3, 1),
        quick: true,
    },
    Cell {
        name: "K/2^23 m2 d4",
        source: Source::Decomposition(23, 0, 2, 4, 1),
        quick: true,
    },
    Cell {
        name: "K/2^5 m3 d4",
        source: Source::Decomposition(5, 0, 3, 4, 0x5EED),
        quick: true,
    },
    Cell {
        name: "K/2^5 m3 d5",
        source: Source::Decomposition(5, 0, 3, 5, 0x5EED),
        quick: true,
    },
    Cell {
        name: "K/2^5 m3 d6",
        source: Source::Decomposition(5, 0, 3, 6, 0x5EED),
        quick: false,
    },
    Cell {
        name: "K/2^7 m3 d5",
        source: Source::Decomposition(7, 0, 3, 5, 0x5EED),
        quick: false,
    },
    Cell {
        name: "rand 4096² ½",
        source: Source::Random(4096, 4096, 0.5, 1),
        quick: true,
    },
    Cell {
        name: "rand 12000² ½",
        source: Source::Random(12000, 12000, 0.5, 2),
        quick: false,
    },
];

fn random_matrix(rows: usize, cols: usize, density: f64, seed: u64) -> Vec<Vec<u64>> {
    let mut rng = StdRng::seed_from_u64(seed);
    let words = cols.div_ceil(64);
    (0..rows)
        .map(|_| {
            let mut row = vec![0u64; words];
            if density == 0.5 {
                for w in row.iter_mut() {
                    *w = rng.gen();
                }
                if !cols.is_multiple_of(64) {
                    row[words - 1] &= (1u64 << (cols % 64)) - 1;
                }
            } else {
                for c in 0..cols {
                    if rng.gen_bool(density) {
                        row[c / 64] |= 1 << (c % 64);
                    }
                }
            }
            row
        })
        .collect()
}

fn best_of<F: FnMut() -> (f64, usize, u64, Vec<Vec<u64>>)>(
    reps: usize,
    mut f: F,
) -> (f64, usize, u64, Vec<Vec<u64>>) {
    let mut best = f();
    for _ in 1..reps {
        let r = f();
        if r.0 < best.0 {
            best = r;
        }
    }
    best
}

fn main() {
    // The oracle's own caps would refuse the larger cells; this harness
    // measures the kernel, so it lifts them for its own process.
    std::env::set_var("F4_F2_MAX_ROWS", "4000000");
    std::env::set_var("F4_F2_MAX_COLS", "4000000");
    let args: Vec<String> = std::env::args().collect();
    let flag = |name: &str| args.windows(2).find(|w| w[0] == name).map(|w| w[1].clone());
    let reps: usize = flag("--reps").and_then(|v| v.parse().ok()).unwrap_or(3);
    let out = flag("--out");
    let quick = args.iter().any(|a| a == "--quick");

    println!(
        "| cell | rows × cols | rank | legacy ms | new ms | speedup | legacy word XORs | new word XORs |"
    );
    println!("|:--|--:|--:|--:|--:|--:|--:|--:|");
    let mut rows_json = Vec::new();
    for cell in CELLS.iter().filter(|c| !quick || c.quick) {
        let (vars, cols, matrix) = match cell.source {
            Source::Decomposition(n, fi, m, d, seed) => {
                match decomposition_macaulay(n, fi, m, d, seed) {
                    Some(x) => x,
                    None => {
                        println!("| {} | unavailable | | | | | | |", cell.name);
                        continue;
                    }
                }
            }
            Source::Random(r, c, dens, seed) => (0, c, random_matrix(r, c, dens, seed)),
        };
        let rows = matrix.len();
        let legacy = best_of(reps, || {
            let mut m = matrix.clone();
            let mut ops = 0;
            let t = Instant::now();
            let rank = rref_f2_legacy(&mut m, cols, &mut ops);
            (t.elapsed().as_secs_f64() * 1e3, rank, ops, m)
        });
        let new = best_of(reps, || {
            let mut m = matrix.clone();
            let mut ops = 0;
            let t = Instant::now();
            let rank = gf2_elim::rref_counted(&mut m, cols, &mut ops);
            (t.elapsed().as_secs_f64() * 1e3, rank, ops, m)
        });
        let agree = legacy.1 == new.1 && legacy.3 == new.3;
        println!(
            "| {} | {} × {} | {} | {:.1} | {:.1} | {:.2}× | {} | {} |",
            cell.name,
            rows,
            cols,
            new.1,
            legacy.0,
            new.0,
            legacy.0 / new.0,
            legacy.2,
            new.2
        );
        if !agree {
            eprintln!("{}: the kernels disagree — aborting", cell.name);
            std::process::exit(1);
        }
        rows_json.push(format!(
            "{{\"cell\":\"{}\",\"vars\":{},\"rows\":{},\"cols\":{},\"rank\":{},\"legacy_ms\":{:.3},\"new_ms\":{:.3},\"legacy_word_xors\":{},\"new_word_xors\":{}}}",
            cell.name, vars, rows, cols, new.1, legacy.0, new.0, legacy.2, new.2
        ));
    }
    println!();
    println!(
        "AVX-512 row update: {}; tables per pass: {}.  Kernel diagnostic, not an end-to-end number.",
        gf2_elim::simd_available() && gf2_elim::Config::from_env().simd,
        gf2_elim::Config::from_env().tables
    );
    if let Some(path) = out {
        let body = format!(
            "{{\"schema_version\":1,\"operation\":\"gf2_elim_bench\",\"reps\":{reps},\"cells\":[{}]}}\n",
            rows_json.join(",")
        );
        std::fs::write(&path, body).expect("write --out");
        println!("wrote {path}");
    }
}
