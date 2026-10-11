//! **All BSGS-family and Gaudry–Schost ECDLP variants, side by side.**
//!
//! Reproduces the structure of the algorithm table in Galbraith, Wang
//! & Zhang, "Computing Elliptic Curve Discrete Logarithms with
//! Improved Baby-step Giant-step Algorithm" (Adv. Math. Commun. 2017)
//! by running every variant on the same small curve over a batch of
//! random targets and reporting the *measured* average cost.
//!
//! Curve: `y² = x³ + 6x + 4` over `F_99013`, generator `(0,2)` of prime
//! order `n = 98893` (`√n ≈ 314.5`).
//!
//! Run with:
//!   cargo run --release --example ecdlp_bsgs_gs_variants

use cryptanalysis_suite::cryptanalysis::ecdlp_variants::{
    bsgs_average_case, bsgs_interleaving, bsgs_interleaving_block, bsgs_interleaving_negation,
    bsgs_negation, bsgs_textbook, demo_group_mid, gaudry_schost, gaudry_schost_montgomery,
    gaudry_schost_negation, grumpy_giants, grumpy_giants_block, grumpy_giants_negation,
    DlpSolution, EcGroup, GaudrySchostOptions,
};
use cryptanalysis_suite::ecc::point::Point;
use num_bigint::BigUint;

const N: u64 = 98_893; // subgroup order
const BLOCK: usize = 32; // Montgomery-trick block width

fn secrets() -> Vec<u64> {
    // 96 well-spread, deterministic targets in [1, n).
    (0..96).map(|i| 1 + (i * 9_871 + 1_234) % (N - 1)).collect()
}

struct Row {
    name: &'static str,
    ops: f64,
    inv: f64,
    table: f64,
    ok: bool,
}

/// Average a solver's measured cost over all targets.
fn bench<F>(name: &'static str, group: &EcGroup, mut solve: F) -> Row
where
    F: FnMut(&EcGroup, &Point) -> Result<DlpSolution, &'static str>,
{
    let (mut ops, mut inv, mut table) = (0u64, 0u64, 0usize);
    let mut ok = true;
    let xs = secrets();
    for &x in &xs {
        let q = group.mul_setup(&BigUint::from(x));
        match solve(group, &q) {
            Ok(s) => {
                ok &= s.x == BigUint::from(x);
                ops += s.group_ops;
                inv += s.field_inversions;
                table += s.table_size;
            }
            Err(_) => ok = false,
        }
    }
    let k = xs.len() as f64;
    Row {
        name,
        ops: ops as f64 / k,
        inv: inv as f64 / k,
        table: table as f64 / k,
        ok,
    }
}

fn gs_opts(seed: u64) -> GaudrySchostOptions {
    GaudrySchostOptions {
        dp_bits: 4,
        num_jumps: 32,
        block: BLOCK,
        seed: Some(seed),
        ..Default::default()
    }
}

fn print_block(title: &str, rows: &[Row], sqrt_n: f64) {
    println!("\n{title}");
    println!(
        "  {:<34} {:>9} {:>8} {:>10} {:>8}  ok",
        "algorithm", "ops", "ops/√n", "inv", "table"
    );
    for r in rows {
        println!(
            "  {:<34} {:>9.0} {:>8.3} {:>10.1} {:>8.0}  {}",
            r.name,
            r.ops,
            r.ops / sqrt_n,
            r.inv,
            r.table,
            if r.ok { "✓" } else { "✗" }
        );
    }
}

fn main() {
    let g = demo_group_mid();
    let sqrt_n = (N as f64).sqrt();
    println!("ECDLP variant comparison — curve order n = {N}, √n ≈ {sqrt_n:.1}");
    println!("(averaged over {} random targets)", secrets().len());

    let base = [
        bench("textbook BSGS (#1)", &g, bsgs_textbook),
        bench("avg-case BSGS (#2)", &g, bsgs_average_case),
        bench("interleaving BSGS (#3)", &g, bsgs_interleaving),
        bench("grumpy giants (#4)", &g, grumpy_giants),
        bench("Gaudry–Schost (#6)", &g, |grp, q| {
            gaudry_schost(grp, q, &gs_opts(0x6))
        }),
    ];
    print_block(
        "── base ─────────────────────────────────────────────",
        &base,
        sqrt_n,
    );

    let neg = [
        bench("BSGS + negation (#7)", &g, bsgs_negation),
        bench(
            "interleaving + negation (#8)",
            &g,
            bsgs_interleaving_negation,
        ),
        bench("grumpy + negation (#9)", &g, grumpy_giants_negation),
        bench("Gaudry–Schost + negation (#11)", &g, |grp, q| {
            gaudry_schost_negation(grp, q, &gs_opts(0xB))
        }),
    ];
    print_block(
        "── with negation map ────────────────────────────────",
        &neg,
        sqrt_n,
    );

    let block = [
        bench("interleaving BSGS + block (#12)", &g, |grp, q| {
            bsgs_interleaving_block(grp, q, BLOCK)
        }),
        bench("grumpy giants + block (#13)", &g, |grp, q| {
            grumpy_giants_block(grp, q, BLOCK)
        }),
        bench("Gaudry–Schost + Montgomery (#15)", &g, |grp, q| {
            gaudry_schost_montgomery(grp, q, &gs_opts(0x15))
        }),
    ];
    print_block(
        "── with block computation / Montgomery trick (B = 32) ",
        &block,
        sqrt_n,
    );

    println!(
        "\nNotes:\n  • ops/√n is the empirical leading constant (paper targets: 1.5, 1.41, 1.33, 1.25, 1.66 …).\n  • avg-case < textbook, interleaving < avg-case, and the negation map drops every\n    BSGS row to ≈ 1.0 — the structural improvements all show up.\n  • Grumpy's *plain* row (#4) carries the 3-walk overhead at an untuned √n giant\n    step; its advantage lands under negation (#9 leads the table at ≈ 1.0).\n  • 'inv' collapses to ≈ ops/{BLOCK} in the block / Montgomery rows — the point of that column.\n  • 'table' shrinks under the negation map (x-coordinate folding).\n  • All 'ok' must be ✓: each variant recovered every planted discrete log."
    );
}
