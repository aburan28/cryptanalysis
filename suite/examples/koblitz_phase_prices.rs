//! The two phases this thread has left unpriced, measured.
//!
//! `S` has been reported as a lower bound throughout, because factor-base
//! selection and the linear algebra were null rather than zero.  Under
//! AGENTS.md §8 that blocks an admissible whole-pipeline `S`: "All phases
//! must be priced and final scalar verified before admitting a full-DLP
//! S."  This measures both in the same unit as everything else.
//!
//! Neither phase counts group additions natively, so each needs its own
//! conversion, measured here on the same host and the same instance as
//! the thing it converts — never a factor carried over from another
//! field or another machine.
//!
//! **Selection** spends abscissa draws.  Each is a random `x`, a
//! quadratic solve to lift it to the curve, and on success a cofactor
//! multiplication; new representatives also walk a Frobenius orbit, and
//! the base is rebuilt from the representatives at intervals.  The draw
//! is the unit because it is what the loop repeats.
//!
//! **The linear algebra** spends modular multiply-adds: block Wiedemann
//! does `products` matrix-block products, each touching `core_nonzeros`
//! entries for each of `block_n` vectors.  That count comes straight
//! out of the run's own report, so only the per-operation conversion is
//! measured here.
//!
//!     cargo run --release --example koblitz_phase_prices -- 53 15000
use cryptanalysis_suite::cryptanalysis::koblitz_fast::{BatchScratch, FastCurve, FastPoint};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::*;
use std::time::Instant;

const ADDS: usize = 2_000_000;
const MULMADS: usize = 20_000_000;

fn main() {
    let degree: u32 = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(53);
    let points: usize = std::env::args()
        .nth(2)
        .and_then(|s| s.parse().ok())
        .unwrap_or(15000);
    let seed: u64 = std::env::args()
        .nth(3)
        .and_then(|s| s.parse().ok())
        .unwrap_or(1);
    let kc = KoblitzCurve::new(0, degree).expect("curve");
    let fc = FastCurve::new(&kc.curve).expect("fast curve");
    let r = kc.subgroup_order.to_u64_digits()[0];

    // The unit: a batched affine addition, sharing one inversion across
    // the slice, which is how the walk and the table build both add.
    let g = fc.lift(kc.generator());
    let seedfb = build_subgroup_orbit_factor_base(&kc, seed, 64).expect("seed base");
    let batch: Vec<FastPoint> = (0..1024)
        .map(|i| fc.lift(&seedfb.points[i % seedfb.points.len()]))
        .collect();
    let mut scratch = BatchScratch::default();
    let mut out: Vec<FastPoint> = Vec::with_capacity(batch.len());
    let rounds = ADDS / batch.len();
    let t = Instant::now();
    for _ in 0..rounds {
        out.clear();
        fc.add_many(g, &batch, &mut out, &mut scratch);
    }
    let add_ns = t.elapsed().as_secs_f64() * 1e9 / (rounds * batch.len()) as f64;
    std::hint::black_box(out.len());
    println!("degree {degree}, r = 2^{:.1}", (r as f64).log2());
    println!("unit: one batched group addition = {add_ns:.2} ns");

    // Selection, timed and counted together on the same call.
    let t = Instant::now();
    let (fb, cost) =
        build_subgroup_orbit_factor_base_with_cost(&kc, seed, points).expect("selection");
    let select_s = t.elapsed().as_secs_f64();
    let draws = cost.abscissae_drawn.max(1);
    let select_ns_per_draw = select_s * 1e9 / draws as f64;
    println!(
        "\nselection: {} points, {} orbits in {select_s:.3} s",
        fb.points.len(),
        fb.signed_orbits.len()
    );
    println!("  abscissae drawn        {:>12}", cost.abscissae_drawn);
    println!("  lifts found            {:>12}", cost.lifts_found);
    println!(
        "  cofactor multiplies    {:>12}",
        cost.cofactor_multiplications
    );
    println!("  frobenius squarings    {:>12}", cost.frobenius_squarings);
    println!("  rebuilds               {:>12}", cost.rebuilds);
    println!("  ns a draw              {select_ns_per_draw:>12.1}");
    println!(
        "  adds a draw            {:>12.2}",
        select_ns_per_draw / add_ns
    );
    println!(
        "  SELECTION TOTAL        {:>12.0} group additions",
        draws as f64 * select_ns_per_draw / add_ns
    );
    println!(
        "  (the rebuilds are inside that per-draw figure, which is why it is\n   \
         measured over the whole call rather than modelled as a sum of parts)"
    );

    // The linear algebra's unit: one multiply-add mod r, which is what a
    // sparse matrix-vector product spends per stored entry.
    let modulus = r;
    let mut acc: u64 = 1;
    let mut coeff: u64 = 0x9e37_79b9_7f4a_7c15 % modulus;
    let t = Instant::now();
    for _ in 0..MULMADS {
        acc = ((acc as u128 * coeff as u128 + 1) % modulus as u128) as u64;
        coeff ^= acc >> 7;
        coeff %= modulus;
    }
    let mulmad_ns = t.elapsed().as_secs_f64() * 1e9 / MULMADS as f64;
    std::hint::black_box(acc);
    println!("\nlinear algebra:");
    println!("  ns a multiply-add mod r  {mulmad_ns:>10.2}");
    println!("  adds a multiply-add      {:>10.4}", mulmad_ns / add_ns);
    println!(
        "  a run reports `products`, `core_nonzeros` and `block_n`; the count is\n  \
         products x core_nonzeros x block_n, and this converts it."
    );
}
