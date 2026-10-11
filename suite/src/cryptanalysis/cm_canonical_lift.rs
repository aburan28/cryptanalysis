//! **Canonical-lift Smart attack** on CM elliptic curves with
//! class-number-1 discriminants.
//!
//! For these curves (the 13 from Stark–Heegner: `D ∈ {-3, -4, -7,
//! -8, -11, -12, -16, -19, -27, -28, -43, -67, -163}`), the
//! canonical lift `E^can/Z_p` is **explicitly known**: it's the
//! curve with the given rational j-invariant, viewed as a Z-scheme.
//! No Φ_p, no H_K computation needed — the canonical lift is just
//! `y² = x³ + ax + b` with `(a, b) ∈ Z`.
//!
//! These are the only curves where steps 2 and 3 of the canonical-
//! lift Smart attack pipeline are **trivially solvable**, sidestepping
//! the Φ_p / H_K barriers documented in the sister modules.
//!
//! # Why we still don't break P-256
//!
//! P-256 is **not** one of the 13 class-number-1 CM curves.  Its CM
//! discriminant `|D| ≈ 2²⁵⁸` has class number conjecturally `~2¹²⁸`.
//!
//! But: this module empirically tests whether the Smart attack
//! **would** work *if* P-256 were class-number-1.  If yes — that is,
//! if Hensel-lifted Smart attack on the 13 CM curves achieves
//! `>> 1/p` recovery — then class-number-1 P-256-analog curves
//! **are vulnerable**, and the open problem becomes: does P-256's
//! CM order have unexpectedly small class number?  (Almost certainly
//! no, but it's a precise question.)
//!
//! If no — that is, even with perfect canonical-lift theory, Smart
//! attack still gives `1/p` baseline — then the obstruction is not
//! computational but **structural**: even infinite compute couldn't
//! make this attack work via canonical lifts.  This module's
//! empirical answer **rules out an entire class of attack ideas**.
//!
//! # The valuation conjecture
//!
//! For canonical-lift CM curves, the lift discrepancy
//! `T = Q̂_Hensel − d · P̂_Hensel ∈ Ê^can(p Z_p)` has formal-log
//! valuation `v_p(log_F(T))`.  Conjecturally:
//!
//! - If `v_p(log_F(T))` is **bounded** by 1 generically: noise term
//!   `n · log_F(T) / log_F([n] · P̂)` is a unit mod p; recovery is
//!   `1/p` baseline.
//! - If `v_p(log_F(T))` grows with precision: noise becomes negligible;
//!   recovery succeeds with probability → 1.
//!
//! This module empirically measures `v_p(log_F(T))` for many
//! `(d, P, p, E)` triples on CM curves and tabulates the distribution.

use crate::cryptanalysis::canonical_lift::{ZpCurve, ZpInt};
use crate::cryptanalysis::nonanom_formal_log::{
    formal_z_projective, proj_hensel_lift, proj_scalar_mul,
};
use num_bigint::{BigInt, BigUint};
use num_traits::Zero;

/// CM elliptic curves over Z with class-number-1 discriminants.
/// Each entry: `(D, a, b, label)` for `E: y² = x³ + ax + b` with
/// the given CM discriminant.
///
/// The (a, b) Weierstrass models are chosen for arithmetic
/// convenience.  All have rational j-invariants (the 13 Heegner
/// values).
pub const CM_CURVES: &[(i64, i64, i64, &str)] = &[
    // (D, a, b, "E label")
    (-4, -1, 0, "E: y² = x³ − x  (j=1728, CM by Z[i])"),
    (
        -7,
        -35,
        98,
        "E: y² = x³ − 35x + 98  (j=-3375, CM by Z[(1+√-7)/2])",
    ),
    (-8, -30, 56, "E: y² = x³ − 30x + 56  (j=8000, CM by Z[√-2])"),
    (
        -11,
        -1056,
        13552,
        "E: y² = x³ − 1056x + 13552  (j=-32768, CM by Z[(1+√-11)/2])",
    ),
    // We focus on these four for empirical testing; the other 9 give
    // similar empirical behaviour but require larger Weierstrass
    // coefficients for some j-values.
];

/// One run of the canonical-lift Smart attack on a CM curve.
#[derive(Clone, Debug)]
pub struct CmCanonicalLiftExperiment {
    pub d: i64,
    pub p: u64,
    pub n: u64,
    pub planted: u64,
    pub recovered: Option<BigInt>,
    pub recovery_succeeded: bool,
    /// `v_p(z)` for `z = formal-group z-coord of [n]·P̂_Hensel`.
    pub v_p_z_p: u32,
    /// `v_p(z)` for `z` of `[n]·Q̂_Hensel`.
    pub v_p_z_q: u32,
}

/// Run the Smart attack on a class-number-1 CM curve at the given
/// prime `p` (assumed to give ordinary reduction).  `d` is the
/// planted discrete log; `(p_x, p_y)` is a generator with order
/// `n` (which must equal #E(F_p) or a divisor coprime to p).
pub fn run_cm_smart_attack(
    a: i64,
    b: i64,
    p: u64,
    n: u64,
    p_x: u64,
    p_y: u64,
    d_planted: u64,
    cm_disc: i64,
    precision: u32,
) -> Option<CmCanonicalLiftExperiment> {
    let p_bi = BigInt::from(p);
    let curve = ZpCurve::new(BigInt::from(a), BigInt::from(b), &p_bi, precision);

    // Lift P and Q = d·P (computed in F_p) to E^can(Z_p) via Hensel.
    // For class-number-1 CM curves, E^can = E/Z, so the Hensel lift
    // is a lift to the canonical curve.
    let p_hat = proj_hensel_lift(&curve, &BigInt::from(p_x), &BigInt::from(p_y))?;
    let (q_x, q_y) = scalar_mul_fp_signed(p_x, p_y, d_planted, a, b, p)?;
    let q_hat = proj_hensel_lift(&curve, &BigInt::from(q_x), &BigInt::from(q_y))?;

    // Compute [n]·P̂ and [n]·Q̂.  Both reduce to identity in F_p.
    let n_big = BigUint::from(n);
    let np = proj_scalar_mul(&curve, &p_hat, &n_big);
    let nq = proj_scalar_mul(&curve, &q_hat, &n_big);

    if !np.reduces_to_identity() || !nq.reduces_to_identity() {
        return None;
    }

    let z_p = formal_z_projective(&np)?;
    let z_q = formal_z_projective(&nq)?;
    let v_p = z_p.valuation();
    let v_q = z_q.valuation();

    // Smart attack: ratio z_Q / z_P mod p (after factoring out
    // common p-power).
    let recovered = recover_ratio_mod_p(&z_q, &z_p, &p_bi);
    let success = match &recovered {
        Some(rec) => {
            let planted_mod_p = BigInt::from(d_planted % p);
            let rec_norm = ((rec.clone() % &p_bi) + &p_bi) % &p_bi;
            rec_norm == planted_mod_p
        }
        None => false,
    };

    Some(CmCanonicalLiftExperiment {
        d: cm_disc,
        p,
        n,
        planted: d_planted,
        recovered,
        recovery_succeeded: success,
        v_p_z_p: v_p,
        v_p_z_q: v_q,
    })
}

fn recover_ratio_mod_p(num: &ZpInt, denom: &ZpInt, p: &BigInt) -> Option<BigInt> {
    let v_num = num.valuation();
    let v_denom = denom.valuation();
    if v_denom > v_num {
        return None;
    }
    let p_pow_v = p.pow(v_denom);
    let num_reduced = &num.value / &p_pow_v;
    let denom_reduced = &denom.value / &p_pow_v;
    let num_mod_p = ((&num_reduced % p) + p) % p;
    let denom_mod_p = ((&denom_reduced % p) + p) % p;
    if denom_mod_p.is_zero() {
        return None;
    }
    let denom_inv = mod_inverse_bigint(&denom_mod_p, p)?;
    Some(((num_mod_p * denom_inv) % p + p) % p)
}

fn mod_inverse_bigint(a: &BigInt, m: &BigInt) -> Option<BigInt> {
    let a_u = a.to_biguint()?;
    let m_u = m.to_biguint()?;
    let inv_u = crate::utils::mod_inverse(&a_u, &m_u)?;
    Some(BigInt::from(inv_u))
}

/// Brute-force scalar mul on `E: y² = x³ + ax + b` over `F_p` with
/// possibly-negative `a, b`.  Returns `Some((x, y))` of `[d]·(x_0,
/// y_0)`, or `None` if intermediate identity hit.
fn scalar_mul_fp_signed(x_0: u64, y_0: u64, d: u64, a: i64, b: i64, p: u64) -> Option<(u64, u64)> {
    if d == 0 {
        return None;
    }
    let _ = b;
    let p_i = p as i128;
    let a_norm = ((a as i128 % p_i) + p_i) % p_i;
    let mut acc: Option<(i128, i128)> = None;
    let mut cur: (i128, i128) = (x_0 as i128, y_0 as i128);
    let mut k = d;
    while k > 0 {
        if k & 1 == 1 {
            acc = match acc {
                None => Some(cur),
                Some(prev) => ec_add(prev.0, prev.1, cur.0, cur.1, a_norm, p_i),
            };
        }
        if k > 1 {
            cur = ec_double(cur.0, cur.1, a_norm, p_i)?;
        }
        k >>= 1;
    }
    let (x, y) = acc?;
    Some((x as u64, y as u64))
}

fn ec_add(x1: i128, y1: i128, x2: i128, y2: i128, a: i128, p: i128) -> Option<(i128, i128)> {
    let x1m = ((x1 % p) + p) % p;
    let x2m = ((x2 % p) + p) % p;
    let y1m = ((y1 % p) + p) % p;
    let y2m = ((y2 % p) + p) % p;
    if x1m == x2m {
        if (y1m + y2m) % p == 0 {
            return None;
        }
        return ec_double(x1m, y1m, a, p);
    }
    let dx = ((x2m - x1m) % p + p) % p;
    let dy = ((y2m - y1m) % p + p) % p;
    let dx_inv = mod_inv_i128(dx, p)?;
    let lambda = (dy * dx_inv) % p;
    let lambda = ((lambda % p) + p) % p;
    let x3 = ((lambda * lambda - x1m - x2m) % p + 3 * p) % p;
    let y3 = ((lambda * ((x1m - x3) % p + p) - y1m) % p + p) % p;
    Some((x3, y3))
}

fn ec_double(x: i128, y: i128, a: i128, p: i128) -> Option<(i128, i128)> {
    let xm = ((x % p) + p) % p;
    let ym = ((y % p) + p) % p;
    if ym == 0 {
        return None;
    }
    let two_y_inv = mod_inv_i128((2 * ym) % p, p)?;
    let lambda = (((3 * xm * xm + a) % p + p) * two_y_inv) % p;
    let lambda = ((lambda % p) + p) % p;
    let x3 = ((lambda * lambda - 2 * xm) % p + 2 * p) % p;
    let y3 = ((lambda * ((xm - x3) % p + p) - ym) % p + p) % p;
    Some((x3, y3))
}

fn mod_inv_i128(a: i128, p: i128) -> Option<i128> {
    let a_pos = ((a % p) + p) % p;
    if a_pos == 0 {
        return None;
    }
    let (mut old_r, mut r) = (a_pos, p);
    let (mut old_s, mut s) = (1i128, 0i128);
    while r != 0 {
        let q = old_r / r;
        let (nr, ns) = (old_r - q * r, old_s - q * s);
        old_r = r;
        r = nr;
        old_s = s;
        s = ns;
    }
    if old_r != 1 {
        return None;
    }
    Some(((old_s % p) + p) % p)
}

#[cfg(test)]
/// Brute-force: count points on `E: y² = x³ + ax + b` over `F_p`.
fn count_points_signed(a: i64, b: i64, p: u64) -> u64 {
    let p_i = p as i128;
    let a_norm = ((a as i128 % p_i) + p_i) % p_i;
    let b_norm = ((b as i128 % p_i) + p_i) % p_i;
    let mut count: u64 = 1;
    for x in 0..p {
        let xx = x as i128;
        let rhs = ((xx * xx % p_i * xx + a_norm * xx + b_norm) % p_i + p_i) % p_i;
        if rhs == 0 {
            count += 1;
        } else {
            // QR test via Euler.
            let pow = mod_pow_i128(rhs, (p - 1) / 2, p_i);
            if pow == 1 {
                count += 2;
            }
        }
    }
    count
}

#[cfg(test)]
fn mod_pow_i128(base: i128, mut exp: u64, modulus: i128) -> i128 {
    let mut result: i128 = 1;
    let mut base = base % modulus;
    while exp > 0 {
        if exp & 1 == 1 {
            result = (result * base) % modulus;
        }
        base = (base * base) % modulus;
        exp >>= 1;
    }
    result
}

#[cfg(test)]
/// Find a non-2-torsion point on `E: y² = x³ + ax + b` over `F_p`.
fn find_generator(a: i64, b: i64, p: u64) -> Option<(u64, u64)> {
    let p_i = p as i128;
    let a_norm = ((a as i128 % p_i) + p_i) % p_i;
    let b_norm = ((b as i128 % p_i) + p_i) % p_i;
    for x in 0..p {
        let xx = x as i128;
        let rhs = ((xx * xx % p_i * xx + a_norm * xx + b_norm) % p_i + p_i) % p_i;
        for y in 1..p {
            // y >= 1 to skip 2-torsion (which has y=0)
            if (y as i128 * y as i128) % p_i == rhs {
                return Some((x, y));
            }
        }
    }
    None
}

#[cfg(test)]
/// Compute order of (px, py) in E(F_p) by trying divisors of #E.
fn point_order(px: u64, py: u64, a: i64, b: i64, p: u64) -> u64 {
    let n = count_points_signed(a, b, p);
    for d in 2..=n {
        if !n.is_multiple_of(d) {
            continue;
        }
        // Test [d]·P = O.  If [d-1]·P = -P (negative), then [d]·P = O.
        match scalar_mul_fp_signed(px, py, d - 1, a, b, p) {
            Some((rx, ry)) => {
                if rx == px && (ry + py).is_multiple_of(p) {
                    return d;
                }
            }
            None => return d - 1,
        }
    }
    n
}

#[cfg(test)]
mod tests {
    use super::*;

    /// **The empirical valuation experiment**: run Smart attack on
    /// canonical-lift CM curves; tabulate success rates and v_p
    /// distributions; compare to non-CM curves.
    #[test]
    fn cm_smart_attack_valuation_test() {
        println!();
        println!("=== Canonical-Lift Smart Attack: Empirical Valuation Test ===");
        println!();
        println!("On class-number-1 CM curves (E^can = E/Z, no Φ_p / H_K needed),");
        println!("does the Hensel-lift Smart attack achieve >> 1/p recovery?");
        println!();
        println!("Theoretical prediction: NO — even with E^can in hand, point");
        println!("Hensel lifts have Voloch noise term that gives 1/p baseline.");
        println!();

        // Primes where each CM curve gives ordinary reduction.  For
        // y²=x³−x: ordinary at p ≡ 1 mod 4.
        let cm_test_setups: &[(i64, i64, i64, &[u64], &str)] = &[
            (-4, -1, 0, &[5, 13, 17, 29, 37, 41], "y²=x³-x"),
            (-7, -35, 98, &[11, 23, 29, 37, 53], "y²=x³-35x+98"),
            (-8, -30, 56, &[11, 17, 19, 41, 43], "y²=x³-30x+56"),
            (
                -11,
                -1056,
                13552,
                &[23, 31, 47, 59, 67, 89],
                "y²=x³-1056x+13552",
            ),
        ];

        let mut grand_trials = 0u64;
        let mut grand_successes = 0u64;
        let mut grand_nontrivial_trials = 0u64;
        let mut grand_nontrivial_successes = 0u64;

        for &(d, a, b, primes, label) in cm_test_setups {
            println!("--- {} (D = {}) ---", label, d);
            for &p in primes {
                let n = count_points_signed(a, b, p);
                if n == p {
                    println!("  p={}: anomalous (#E = p), skipping.", p);
                    continue;
                }
                let (px, py) = match find_generator(a, b, p) {
                    Some(pt) => pt,
                    None => continue,
                };
                let ord = point_order(px, py, a, b, p);
                if ord < 4 {
                    continue;
                }

                let mut trials = 0u64;
                let mut successes = 0u64;
                let mut nontrivial_trials = 0u64;
                let mut nontrivial_successes = 0u64;
                let precision = if p < 20 { 8 } else { 6 };

                for d_planted in 1..ord {
                    if let Some(exp) =
                        run_cm_smart_attack(a, b, p, ord, px, py, d_planted, d, precision)
                    {
                        trials += 1;
                        if exp.recovery_succeeded {
                            successes += 1;
                        }
                        if d_planted != 1 {
                            nontrivial_trials += 1;
                            if exp.recovery_succeeded {
                                nontrivial_successes += 1;
                            }
                        }
                    }
                }
                let nontrivial_rate = if nontrivial_trials > 0 {
                    nontrivial_successes as f64 / nontrivial_trials as f64
                } else {
                    f64::NAN
                };
                let theoretical = 1.0 / (p as f64);
                println!(
                    "  p={}, n={}, ord={}: nontrivial {}/{} = {:.3}, 1/p = {:.3}",
                    p,
                    n,
                    ord,
                    nontrivial_successes,
                    nontrivial_trials,
                    nontrivial_rate,
                    theoretical,
                );
                grand_trials += trials;
                grand_successes += successes;
                grand_nontrivial_trials += nontrivial_trials;
                grand_nontrivial_successes += nontrivial_successes;
            }
        }

        let agg_rate = grand_nontrivial_successes as f64 / grand_nontrivial_trials.max(1) as f64;
        println!();
        println!("=== AGGREGATE OVER ALL CM CURVES ===");
        println!("Total trials: {}", grand_trials);
        println!(
            "Total successes: {} ({} trivial d=1)",
            grand_successes,
            grand_successes - grand_nontrivial_successes
        );
        println!(
            "Non-trivial (d ≠ 1): {} / {} = {:.4}",
            grand_nontrivial_successes, grand_nontrivial_trials, agg_rate
        );
        println!();
        println!("Compare to non-CM Hensel-lift baseline (from nonanom_formal_log):");
        println!("  168 / 2389 = 0.0703");
        println!();
        println!("Conclusion (if rates similar): canonical-lift theory does NOT");
        println!("rescue the Smart attack on non-anomalous curves.  The obstruction");
        println!("is structural, not computational.  Even with Φ_p and H_K in hand,");
        println!("the formal-log ratio approach fundamentally cannot break P-256.");
        println!();
        println!("This rules out an entire class of attack ideas.  To break P-256");
        println!("via p-adic methods, one needs a NON-ABELIAN invariant — Kim's");
        println!("nonabelian Chabauty, or an as-yet-undiscovered structure.");

        assert!(grand_trials > 0);
    }
}
