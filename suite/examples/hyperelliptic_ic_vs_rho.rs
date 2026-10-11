//! Index calculus vs Pollard rho on the same hyperelliptic Jacobian.
//!
//! One table, one unit: `S = total group operations / sqrt(N)`, with
//! every cost each side incurs inside it — precomputation, relation
//! search, and the linear algebra converted to group-operation
//! equivalents by a factor measured at run time.
//!
//! ```sh
//! cargo run --release --example hyperelliptic_ic_vs_rho
//! ```

use std::io::{self, Write};

use num_bigint::BigUint;
use num_traits::{One, Zero};

use cryptanalysis_suite::cryptanalysis::hyperelliptic_ic_bench::{
    head_to_head, HeadToHeadTrials, RhoVariant,
};
use cryptanalysis_suite::cryptanalysis::hyperelliptic_index_calculus::{
    build_factor_base, divisor_order_bsgs, hasse_interval, largest_prime_factor,
    HecIndexCalculusParams, LinearAlgebra, RelationSearch, SmoothnessTest,
};
use cryptanalysis_suite::prime_hyperelliptic::{FpPoly, HyperellipticCurveP, MumfordDivisorP};

/// Genus 2: `C : y² = x⁵ + 3x³ + 2x² + x + c`.
/// Genus 3: `C : y² = x⁷ + x³ + c x + 1`.
fn curve_over(p: u64, c: u64, genus: u32) -> HyperellipticCurveP {
    let p = BigUint::from(p);
    // Degree 2g+1 in every case, so the curve has one point at infinity and
    // Cantor arithmetic applies uniformly.  Genus 4 needs degree 9; the
    // earlier `else` branch hardcoded degree 7 and so silently produced a
    // genus-3 curve whatever `genus` said.
    let coeffs = match genus {
        2 => vec![
            BigUint::from(c) % &p,
            BigUint::from(1u32),
            BigUint::from(2u32),
            BigUint::from(3u32),
            BigUint::zero(),
            BigUint::from(1u32),
        ],
        3 => vec![
            BigUint::one(),
            BigUint::from(c) % &p,
            BigUint::zero(),
            BigUint::one(),
            BigUint::zero(),
            BigUint::zero(),
            BigUint::zero(),
            BigUint::one(),
        ],
        4 => vec![
            BigUint::one(),
            BigUint::from(c) % &p,
            BigUint::zero(),
            BigUint::one(),
            BigUint::zero(),
            BigUint::zero(),
            BigUint::zero(),
            BigUint::zero(),
            BigUint::zero(),
            BigUint::one(),
        ],
        g => panic!("no model for genus {g}; degree must be 2g+1"),
    };
    let f = FpPoly::from_coeffs(coeffs, p.clone());
    HyperellipticCurveP::new(p, f, genus)
}

/// `f` squarefree ⟺ `gcd(f, f') = 1`.  A singular curve would run
/// Cantor's algorithm outside its hypotheses and quietly mis-measure
/// both algorithms, so such a `c` is skipped rather than used.
fn is_squarefree(curve: &HyperellipticCurveP) -> bool {
    let p = &curve.p;
    let d: Vec<BigUint> = curve
        .f
        .coeffs
        .iter()
        .enumerate()
        .skip(1)
        .map(|(i, c)| (c * BigUint::from(i as u64)) % p)
        .collect();
    let deriv = FpPoly::from_coeffs(d, p.clone());
    if deriv.is_zero() {
        return false;
    }
    curve.f.gcd(&deriv).degree() == Some(0)
}

/// The comparison is only meaningful in a subgroup large enough that
/// rho's fixed costs do not dominate its walk, so pick, for each `p`,
/// the first `c` whose Jacobian has a prime factor carrying most of the
/// group.  Scanning `c` rather than fixing it is a choice about the
/// *instance*, made before either algorithm runs and reported in the
/// table.
fn pick_instance(
    p: u64,
    genus: u32,
) -> Option<(HyperellipticCurveP, MumfordDivisorP, BigUint, u64)> {
    for c in 1..p.min(60) {
        let curve = curve_over(p, c, genus);
        if !is_squarefree(&curve) {
            continue;
        }
        let fb = build_factor_base(&curve, usize::MAX);
        for e in fb.entries.iter().take(8) {
            // The order comes from BSGS over the Hasse-Weil interval,
            // not from an L-polynomial: that route is genus-2 only, and
            // the comparison has to run at genus 3 too.
            let order = match divisor_order_bsgs(&curve, &e.divisor, 200_000) {
                Some(o) => o,
                None => continue,
            };
            let l = largest_prime_factor(&order);
            // The subgroup must carry most of the Jacobian, or the
            // comparison measures the instance rather than the
            // algorithms: rho searches the subgroup while index
            // calculus pays for a factor base sized by the whole curve.
            // No point count is needed for this — the Hasse-Weil lower
            // bound is enough.
            let (lo, _hi) = hasse_interval(&curve)?;
            if l < BigUint::from(1000u32) || &l * BigUint::from(4u32) < BigUint::from(lo) {
                continue;
            }
            let d1 = e.divisor.scalar_mul(&(&order / &l), &curve);
            if divisor_order_bsgs(&curve, &d1, 200_000).as_ref() != Some(&l) {
                continue;
            }
            return Some((curve, d1, l, c));
        }
    }
    None
}

fn main() {
    // Squarefree f is required; a p where f has a repeated root is
    // skipped rather than silently mis-measured.
    let primes2 = [41u64, 61, 101, 151, 211, 251];
    // Genus 3 reaches the same group size at a much smaller p, since
    // #Jac ~ p^3.  Round five extends this upward: the pre-registered
    // exponent test needs at least four p per genus, and the two rows that
    // fell below 1 were the only ones with N > 10^5.
    let primes3 = [23u64, 31, 41, 61, 101, 151, 211];
    // Genus 4: #Jac ~ p^4, so these are already the largest groups measured
    // anywhere in this note.
    let primes4 = [17u64, 23, 31, 41, 61];

    println!(
        "Genus 2: C : y^2 = x^5 + 3x^3 + 2x^2 + x + c.  Genus 3: y^2 = x^7 + x^3 + cx + 1;\n\
         c the first value yielding a prime-order subgroup above 1000,\n\
         chosen before either algorithm runs; the order comes from BSGS over\n\
         the Hasse-Weil interval, not from a genus-2 L-polynomial.\n\
         Unit: S = total group operations / sqrt(N), N = prime order of D1.\n\
         Index calculus carries its linear algebra, converted at the measured\n\
         mul-mods-per-group-op factor shown in the last column.\n"
    );
    let trials = HeadToHeadTrials::default();
    println!(
        "Each row averages {} index-calculus runs and {} rho runs on the same instance.\n",
        trials.ic, trials.rho
    );

    println!(
        "{:>5} {:>9} {:>8} {:>6} {:>10} {:>10} {:>9} {:>9} {:>8} {:>8} {:>7}",
        "p",
        "search",
        "N",
        "m",
        "IC ops",
        "rho ops",
        "S_ic",
        "S_rho",
        "S_ic/S_rho",
        "S_walk",
        "IC/flr"
    );

    for (genus, primes) in [
        (2u32, &primes2[..]),
        (3u32, &primes3[..]),
        (4u32, &primes4[..]),
    ] {
        println!("\n--- genus {genus} ---");
        for &p in primes {
            // Flushed per line: this example is long-running and its
            // output is usually redirected, where block buffering makes
            // a slow stage look like a hung one.
            io::stdout().flush().ok();
            let (curve, d1, n, c) = match pick_instance(p, genus) {
                Some(v) => v,
                None => {
                    println!("{p:>5}   skipped: no usable prime-order subgroup found");
                    continue;
                }
            };
            let m = build_factor_base(&curve, usize::MAX).len();

            let k = &n / BigUint::from(3u32) + BigUint::from(7u32);
            let d2 = d1.scalar_mul(&k, &curve);

            for (label, search, la, oracle) in [
                (
                    "baseline",
                    RelationSearch::Random,
                    LinearAlgebra::Dense,
                    SmoothnessTest::Scan,
                ),
                (
                    "optimised",
                    RelationSearch::walk(),
                    LinearAlgebra::Sparse,
                    SmoothnessTest::Gcd,
                ),
            ] {
                let params = HecIndexCalculusParams {
                    fb_size: usize::MAX,
                    extra_relations: 8,
                    max_trials: 5_000_000,
                    seed: 20260916,
                    search,
                    linear_algebra: la,
                    smoothness: oracle,
                };
                let row = head_to_head(
                    &curve,
                    &d1,
                    &d2,
                    &n,
                    &params,
                    0xC0FFEE,
                    200_000_000,
                    &k,
                    &trials,
                    &RhoVariant::DistinguishedPoints,
                );

                // A row without a verified answer on both sides is not
                // a result.
                let mark = match (row.ic_correct, row.rho_correct) {
                    (true, true) => "",
                    (false, true) => "  [IC UNSOLVED - not a result]",
                    (true, false) => "  [rho UNSOLVED - not a result]",
                    (false, false) => "  [both UNSOLVED - not a result]",
                };

                println!(
                    "{:>5} {:>9} {:>8} {:>6} {:>10.0} {:>10.0} {:>9.2} {:>9.2} {:>8.2} {:>8.2} {:>7.2}{}",
                    p,
                    label,
                    row.n,
                    m,
                    row.ic_total_group_ops,
                    row.rho_group_ops,
                    row.ic_s,
                    row.rho_s,
                    row.ratio_to_reference(),
                    row.rho_walk_s,
                    row.ratio_to_floor(),
                    mark
                );
                io::stdout().flush().ok();
                println!(
                    "        c = {}, relation stage {:.0} ops ({:.0} precompute, {:.2} ops/trial) \
                     + oracle {:.0} mul-mods ({:.0} equiv) + linear algebra {:.0} mul-mods \
                     ({:.0} equiv), conv {:.0}; smoothness {:.3}; IC floor S = {:.2}; \
                     wall {:.0} ms IC vs {:.0} ms rho",
                    c,
                    row.ic_relation_ops,
                    row.ic_precompute_ops,
                    row.ic_ops_per_trial,
                    row.ic_oracle_modmuls,
                    row.ic_oracle_group_equiv,
                    row.ic_la_modmuls,
                    row.ic_la_group_equiv,
                    row.modmuls_per_group_op,
                    row.ic_smoothness_rate,
                    row.ic_floor_s,
                    row.ic_wall_ms,
                    row.rho_wall_ms,
                );
            }
        }
    }

    println!(
        "\nS_walk is rho's walk alone (S_rho also carries the 16-branch\n\
         precomputation, a fixed cost that does not scale with sqrt(N) and so\n\
         inflates S_rho at these toy sizes). The collision itself arrives after\n\
         about sqrt(pi*N/2) = 1.25*sqrt(N) distinct points, but Floyd's cycle\n\
         finding spends 3 group operations per iteration, so S_walk ~ 3 is this\n\
         reference at its own optimum. A distinguished-point rho would cut that\n\
         by roughly 3x -- which widens the gap below, it does not close it.\n\
         S_ic/S_rho below 1 would mean index calculus won that instance."
    );
}
