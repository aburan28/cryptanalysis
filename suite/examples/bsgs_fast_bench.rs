//! Measure the fast baby-step / giant-step solver against the general one.
//!
//! ```sh
//! cargo run --release --example bsgs_fast_bench
//! ```
//!
//! Two questions, kept apart because they have different answers:
//!
//! 1. **How much does the representation buy?**  Both
//!    [`cryptanalysis_suite::cryptanalysis::bsgs_fast`] and
//!    [`cryptanalysis_suite::cryptanalysis::ecdlp_variants::bsgs`] solve the same
//!    instance by the same algorithm, so running them on one curve with
//!    one target isolates `BigUint` + `HashMap` against one word and a
//!    flat table.  Reported as a wall-clock ratio over many repetitions,
//!    because at these sizes a single solve is shorter than the timer's
//!    noise.
//! 2. **What does a solve cost?**  In `S = operations / √width`, the unit
//!    the repository's ECDLP threads report in, so these rows sit in the
//!    same table as the GPU engine's and as Pollard rho's.  Wall-clock is
//!    a practicality note; operation counts are the metric, because they
//!    survive the hardware.
//!
//! The general solver is only run where it finishes in reasonable time.
//! Its cost is the same `√n` in operations -- the gap below is constant
//! factors, not exponents, and is reported as such.

use std::time::Instant;

use num_bigint::BigUint;

use cryptanalysis_suite::cryptanalysis::bsgs_fast::{
    cost_ratio, toy40, BsgsFast, BsgsFastPlan, BsgsFastStats, FastCurve, FastPoint,
};
use cryptanalysis_suite::cryptanalysis::ecdlp_variants::{bsgs as slow, EcGroup};
use cryptanalysis_suite::ecc::curve::CurveParams;

fn demo_small() -> CurveParams {
    CurveParams {
        name: "demo-10007",
        p: BigUint::from(10_007u32),
        a: BigUint::from(3u32),
        b: BigUint::from(6u32),
        gx: BigUint::from(0u32),
        gy: BigUint::from(1973u32),
        n: BigUint::from(10_039u32),
        h: 1,
    }
}

fn demo_mid() -> CurveParams {
    CurveParams {
        name: "demo-99013",
        p: BigUint::from(99_013u32),
        a: BigUint::from(6u32),
        b: BigUint::from(4u32),
        gx: BigUint::from(0u32),
        gy: BigUint::from(2u32),
        n: BigUint::from(98_893u32),
        h: 1,
    }
}

struct Rng(u64);
impl Rng {
    fn next(&mut self) -> u64 {
        let mut x = self.0;
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.0 = x;
        x
    }
}

/// Both solvers on one instance, `reps` targets each.
fn head_to_head(params: &CurveParams, reps: usize) {
    let curve = FastCurve::from_params(params).expect("single-word curve");
    let group = EcGroup::from_curve(params);
    let n = curve.n;
    let mut rng = Rng(0xc0ff_ee00_1234_5678);
    let secrets: Vec<u64> = (0..reps).map(|_| rng.next() % n).collect();

    // The fast solver rebuilds its table per target here, so the two are
    // doing the identical amount of algorithmic work -- amortising the
    // table is measured separately below.
    let fast_qs: Vec<FastPoint> = secrets
        .iter()
        .map(|&x| curve.scalar_mul(curve.g, x))
        .collect();
    let t0 = Instant::now();
    let mut checked = 0usize;
    for (q, &x) in fast_qs.iter().zip(&secrets) {
        let plan = BsgsFastPlan::new(n, 0, true, 1, 8);
        let mut s = BsgsFast::build(curve, plan);
        assert_eq!(s.solve(q), Some(x), "fast solver missed {x}");
        checked += 1;
    }
    let fast = t0.elapsed().as_secs_f64() / reps as f64;

    let slow_qs: Vec<_> = secrets
        .iter()
        .map(|&x| group.mul_setup(&BigUint::from(x)))
        .collect();
    let t0 = Instant::now();
    for (q, &x) in slow_qs.iter().zip(&secrets) {
        let got = slow::bsgs_negation(&group, q).expect("general solver");
        assert_eq!(got.x, BigUint::from(x), "general solver missed {x}");
        checked += 1;
    }
    let slow_t = t0.elapsed().as_secs_f64() / reps as f64;

    println!(
        "  {:<12} n = {:<9} {reps} targets, {checked} verified: \
         general {:>9.1} us, fast {:>8.1} us  -> {:>6.1}x",
        params.name,
        n,
        slow_t * 1e6,
        fast * 1e6,
        slow_t / fast
    );
}

/// Fast solver alone, at a size the general one cannot reach.
fn fast_only(label: &str, width: u64, x0: u64, targets: usize, threads: usize) {
    let curve = toy40();
    let plan = BsgsFastPlan::new(width, x0, true, threads, 8);
    let table_mb = plan.table_bytes() as f64 / 1e6;
    let (m, stride) = (plan.m, plan.stride);

    let t0 = Instant::now();
    let mut solver = BsgsFast::build(curve, plan);
    let build = t0.elapsed().as_secs_f64();
    let build_steps = solver.stats().baby_steps;

    let mut rng = Rng(0x9e37_79b9_7f4a_7c15);
    let secrets: Vec<u64> = (0..targets).map(|_| x0 + rng.next() % width).collect();
    let qs: Vec<FastPoint> = secrets
        .iter()
        .map(|&x| curve.scalar_mul(curve.g, x))
        .collect();

    let t0 = Instant::now();
    let got = solver.solve_many(&qs);
    let search = t0.elapsed().as_secs_f64();
    let solved = got
        .iter()
        .zip(&secrets)
        .filter(|(g, &x)| **g == Some(x))
        .count();
    assert_eq!(solved, targets, "every target must verify");

    let st: BsgsFastStats = solver.stats();
    let sqrt_w = (width as f64).sqrt();
    let amortised = cost_ratio(&st, width, targets as u64);
    let cold = (build_steps as f64 + st.giant_steps as f64 / targets as f64) / sqrt_w;
    let total_steps = st.baby_steps + st.giant_steps;

    println!(
        "  {label}: width 2^{:.0}, m = {m}, stride = {stride}, table {table_mb:.1} MB",
        (width as f64).log2()
    );
    println!(
        "    table {build_steps} steps in {:.3}s ({:.1} Mstep/s); \
         search {} steps over {targets} target(s) in {:.3}s ({:.1} Mstep/s)",
        build,
        build_steps as f64 / build / 1e6,
        st.giant_steps,
        search,
        st.giant_steps as f64 / search / 1e6
    );
    println!(
        "    {solved}/{targets} verified, {} candidates ({} false); \
         S = {cold:.3} cold, {amortised:.3} amortised; {:.1} Mstep/s overall",
        st.candidates,
        st.false_candidates,
        total_steps as f64 / (build + search) / 1e6
    );
}

fn main() {
    println!("baby-step giant-step: fast single-word vs general BigUint");
    println!(
        "threads available to rayon: {}",
        rayon::current_num_threads()
    );

    println!("\n[head to head] same curve, same targets, same algorithm");
    head_to_head(&demo_small(), 200);
    head_to_head(&demo_mid(), 60);

    println!("\n[fast only] toy40, n = 0x973a97e2f1 (~2^39.2)");
    let threads = rayon::current_num_threads();
    // Several targets per row: the giant phase stops at the first hit, so
    // a single solve samples a uniform variable once and says little about
    // the mean.  The "cold" column is the table plus the *average* search.
    fast_only("interval 2^30", 1u64 << 30, 0x10_0000_0000, 32, threads);
    let n = toy40().n;
    fast_only("full group", n, 0, 24, threads);

    println!(
        "\nS is operations / sqrt(width): table build + search + one verification\n\
         per candidate.  The layout predicts 1.00 cold and 0.50 for the search\n\
         alone, so amortised cost falls towards 0.50 as the batch grows.\n\
         Pollard rho on the same curve costs S = 0.85 and needs no table;\n\
         what this buys instead is determinism and a table many targets share."
    );
}
