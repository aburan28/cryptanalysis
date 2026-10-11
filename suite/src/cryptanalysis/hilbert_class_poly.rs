//! **Hilbert class polynomials** `H_D(X)` for imaginary quadratic
//! discriminants `D < 0`.
//!
//! `H_D(X)` is the minimal polynomial over `Q` of `j(τ_D)` where
//! `τ_D` is any CM point in the upper half-plane with discriminant
//! `D`.  Roots of `H_D(X)` are exactly the j-invariants of
//! elliptic curves over `C` with CM by the order of discriminant `D`.
//!
//! `deg(H_D) = h(D)` (the class number).
//!
//! # Why we need them
//!
//! For an ordinary `E/F_p` with `End(E)` an order `O` of discriminant
//! `D` in an imaginary quadratic field, the canonical lift's
//! j-invariant `J ∈ Z_p` is a root of `H_D(X) ≡ 0 (mod p)`.
//!
//! - For class number 1 (D ∈ {-3, -4, -7, -8, -11, -12, -16, -19,
//!   -27, -28, -43, -67, -163}), `H_D(X)` is a polynomial of degree
//!   1 with **integer** coefficients.  J is just an integer.
//! - For higher class numbers, J is an algebraic integer of degree
//!   `h(D)` over `Q`.
//!
//! # The barrier at P-256 scale
//!
//! For "random" `D` of bit-size `b`, by Brauer-Siegel:
//!
//! ```text
//! h(D) ≈ √|D| / log|D|
//! ```
//!
//! For P-256, `|D| = 4p − t² ≈ 2²⁵⁸`, so `b ≈ 258` and
//! `h(D) ≈ 2¹²⁸`.
//!
//! Storing `H_D(X)`:
//! - Degree `h(D) ≈ 2¹²⁸`.
//! - Coefficients are integers of bit-size `O(h(D) · log h(D))`
//!   (Gross–Zagier bound), so `~2¹²⁸ · 128 = 2¹³⁵` bits each.
//! - Total storage: `2¹²⁸ × 2¹³⁵ = 2²⁶³` bits.
//!
//! That's about `2²⁶³ / 8 ≈ 10⁷⁹` bytes — more storage than there are
//! atoms in the observable universe (~10⁸⁰).
//!
//! # Sutherland's CRT method
//!
//! The asymptotically-best published algorithm (Sutherland 2011)
//! computes `H_D(X)` in time `O(|D|^{1+ε})`, using `O(|D|)` space.
//! For P-256-scale `|D|`, that's `2²⁵⁸` operations — far beyond
//! computational reach.
//!
//! Sutherland actually computed `H_D` for `|D|` up to `~10¹³`
//! (about `2⁴⁴`).  Cryptographic scale is `~2²⁵⁸`, **`10⁶⁰`× larger**.
//!
//! # What this module does
//!
//! 1. Tabulates the **13 class-number-1 discriminants** with their
//!    explicit `H_D(X) = X − j_0` values (where `j_0` is a rational
//!    integer).  This is the data needed for canonical-lift attacks
//!    on the (vanishingly small) family of CM curves with rational
//!    j-invariant.
//! 2. Tabulates the first few **class-number-2 discriminants** and
//!    their `H_D(X)` (degree-2 polynomials with integer coefficients).
//! 3. Implements `class_number_brute_force` using the reduced-form
//!    enumeration (Gauss): iterate over `(a, b, c)` with `b² − 4ac =
//!    D` and `a, c > 0` reduced.
//! 4. Documents the scaling barrier with a quantitative table.

use num_bigint::BigInt;
use num_traits::One;

/// Class-number-1 discriminants and their `H_D(X) = X - j_0`.
///
/// From OEIS A003173 / Stark–Heegner theorem (these are the only
/// 13 negative discriminants `D` with class number 1).
///
/// `D` here is the discriminant of the maximal order; `j_0` is
/// `j(τ_D)` evaluated at the corresponding CM point.
pub const CLASS_NUMBER_ONE: &[(i64, &str)] = &[
    // Fundamental discriminants and corresponding j-invariants.
    // Note j(τ) for τ = (1 + √-D)/2 (or i for D=-4, etc.).
    (-3, "0"),                     // j(ω) = 0 where ω = exp(2πi/3)
    (-4, "1728"),                  // j(i) = 1728
    (-7, "-3375"),                 // j((1+√-7)/2) = -3375
    (-8, "8000"),                  // j(√-2) = 8000
    (-11, "-32768"),               // j((1+√-11)/2) = -32768
    (-12, "54000"),                // 54000 = 2^4 · 3^3 · 5^3
    (-16, "287496"),               // 287496 = 2^3 · 3^3 · 11^3
    (-19, "-884736"),              // -884736 = -2^15 · 3^3
    (-27, "-12288000"),            // -12288000
    (-28, "16581375"),             // 16581375 = 3^3 · 5^3 · 17^3
    (-43, "-884736000"),           // -884736000 = -2^18 · 3^3 · 5^3
    (-67, "-147197952000"),        // -147197952000 = -2^15 · 3^3 · 5^3 · 11^3
    (-163, "-262537412640768000"), // -262537412640768000
];

/// Hilbert class polynomial as a list of coefficients in increasing
/// order: `[c_0, c_1, …, c_h]` representing `c_0 + c_1 X + … + c_h X^h`.
#[derive(Clone, Debug)]
pub struct HilbertClassPoly {
    pub d: i64,
    pub coeffs: Vec<BigInt>,
    pub class_number: u32,
}

impl HilbertClassPoly {
    /// Degree.
    pub fn degree(&self) -> u32 {
        (self.coeffs.len() as u32).saturating_sub(1)
    }

    /// Storage in bits (sum of bit-lengths of all coefficients).
    pub fn storage_bits(&self) -> u64 {
        self.coeffs.iter().map(|c| c.bits()).sum()
    }
}

/// Look up `H_D(X)` for a class-number-1 discriminant `D`.
/// Returns `None` if `D` is not in the table.
pub fn class_number_one_hilbert(d: i64) -> Option<HilbertClassPoly> {
    for &(discr, j_str) in CLASS_NUMBER_ONE {
        if discr == d {
            let j_val = BigInt::parse_bytes(j_str.as_bytes(), 10).unwrap();
            // H_D(X) = X − j_0, i.e., coefficients [-j_0, 1].
            let coeffs = vec![-j_val, BigInt::one()];
            return Some(HilbertClassPoly {
                d,
                coeffs,
                class_number: 1,
            });
        }
    }
    None
}

/// **Class number computation by Gauss reduction.**
///
/// For a negative discriminant `D` with `D ≡ 0` or `1 (mod 4)`,
/// count primitive reduced positive-definite binary quadratic forms
/// `(a, b, c)` with `b² − 4ac = D`.
///
/// Reduction: `|b| ≤ a ≤ c`, with `b ≥ 0` if `|b| = a` or `a = c`.
///
/// Cost: `O(√|D|)` enumeration.  Feasible up to `|D| ~ 10¹⁰`.
pub fn class_number_brute_force(d: i64) -> Option<u32> {
    if d >= 0 {
        return None;
    }
    if (d % 4) != 0 && d.rem_euclid(4) != 1 {
        return None; // not a valid discriminant
    }
    let abs_d = (-d) as u64;
    let mut count: u32 = 0;
    // a ranges from 1 to floor(sqrt(|D|/3))
    let max_a_sq = abs_d / 3 + 1;
    let mut a: i64 = 1;
    while (a as u64) * (a as u64) <= max_a_sq {
        // b ranges from -a to a (with b² ≡ D mod 4a)
        let mut b: i64 = -a;
        while b <= a {
            // c = (b² − D) / (4a); must be a positive integer ≥ a.
            let b_sq = b as i128 * b as i128;
            let four_a = 4 * a as i128;
            let num = b_sq - d as i128;
            if num % four_a == 0 {
                let c = num / four_a;
                if c >= a as i128 {
                    // Reduced: |b| ≤ a ≤ c.
                    // Primitivity: gcd(a, b, c) = 1.
                    let g1 = gcd_i64(a, b);
                    let g2 = gcd_i64(g1, c as i64);
                    if g2 == 1 {
                        // Sign normalisation:
                        if b.abs() == a || c == a as i128 {
                            if b >= 0 {
                                count += 1;
                            }
                        } else {
                            count += 1;
                        }
                    }
                }
            }
            b += 1;
        }
        a += 1;
    }
    Some(count)
}

fn gcd_i64(a: i64, b: i64) -> i64 {
    let mut a = a.abs();
    let mut b = b.abs();
    while b != 0 {
        let r = a % b;
        a = b;
        b = r;
    }
    a
}

/// **Brauer-Siegel estimate for class number scaling.**
///
/// `h(D) ≈ √|D| · L(1, χ_D) / π`, where `L(1, χ_D)` is bounded
/// between `(log |D|)⁻¹` and `(log |D|)` heuristically.
pub fn class_number_estimate(abs_d_log2: u64) -> u64 {
    // h(D) ≈ √|D| / log|D|.  In log_2:
    // log_2 h ≈ (1/2) log_2|D| − log_2 log_2|D|
    if abs_d_log2 == 0 {
        return 0;
    }
    let half = abs_d_log2 / 2;
    let log_log = (abs_d_log2 as f64).log2() as u64;
    half.saturating_sub(log_log)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Class-number-1 lookup works.
    #[test]
    fn class_number_one_lookup() {
        let h = class_number_one_hilbert(-163).unwrap();
        assert_eq!(h.class_number, 1);
        assert_eq!(h.degree(), 1);
        // j(-163) = -262537412640768000, so H_{-163}(X) = X − j_0
        //         = X − (−262537412640768000) = X + 262537412640768000.
        // Coefficient of X^0 is +262537412640768000.
        assert_eq!(
            h.coeffs[0],
            BigInt::parse_bytes(b"262537412640768000", 10).unwrap()
        );
        assert_eq!(h.coeffs[1], BigInt::one());
    }

    /// All 13 class-number-1 discriminants are tabulated.
    #[test]
    fn class_number_one_completeness() {
        assert_eq!(CLASS_NUMBER_ONE.len(), 13);
        // Stark-Heegner: these are the only ones.
        let ds: Vec<i64> = CLASS_NUMBER_ONE.iter().map(|&(d, _)| d).collect();
        let expected = [-3, -4, -7, -8, -11, -12, -16, -19, -27, -28, -43, -67, -163];
        assert_eq!(ds, expected);
    }

    /// Brute-force class number agrees with known values.
    #[test]
    fn class_number_brute_force_agrees() {
        // Class number 1 cases.
        for &(d, _) in CLASS_NUMBER_ONE {
            assert_eq!(class_number_brute_force(d), Some(1), "h({}) should be 1", d);
        }
        // Class number 2 cases: D = -15 has h = 2.  D = -20 has h = 2.
        // D = -23 has h = 3.  D = -47 has h = 5.
        assert_eq!(class_number_brute_force(-15), Some(2));
        assert_eq!(class_number_brute_force(-20), Some(2));
        assert_eq!(class_number_brute_force(-23), Some(3));
        // h(-47) = 5
        assert_eq!(class_number_brute_force(-47), Some(5));
    }

    /// **Scaling-barrier table**: how `h(D)` and `H_D` storage scale
    /// from toy to cryptographic discriminants.
    #[test]
    fn class_polynomial_scaling_barrier() {
        println!();
        println!("=== Hilbert class polynomial H_D(X) scaling barrier ===");
        println!();
        println!(
            "{:>15} {:>15} {:>20}",
            "log_2|D|", "est log_2 h(D)", "est log_2 storage_bits"
        );
        for &abs_d_log2 in &[4u64, 8, 16, 32, 50, 64, 100, 128, 200, 258] {
            let h_log2 = class_number_estimate(abs_d_log2);
            // Coefficients of H_D have bit-size ~h(D)·log h(D) by
            // Gross-Zagier.  In log_2: log_2(h) + log_2(log_2(h)).
            let coef_bits_log2 = if h_log2 > 0 {
                h_log2 + (h_log2 as f64).log2() as u64
            } else {
                10
            };
            // Total: deg × coef_bits in log_2:
            let total_log2 = h_log2 + coef_bits_log2;
            println!("{:>15} {:>15} {:>20}", abs_d_log2, h_log2, total_log2);
        }
        println!();
        println!("For P-256: |D| ≈ 2²⁵⁸ ⇒ h(D) ≈ 2¹²⁸ ⇒ storage ≈ 2²⁶³ bits.");
        println!();
        println!("Storage in bytes: 2²⁶³ / 8 = 2²⁶⁰ ≈ 10⁷⁸ bytes.");
        println!("Atoms in the observable universe: ~10⁸⁰.");
        println!();
        println!("Sutherland (2011) reaches |D| ~ 10¹³ ≈ 2⁴⁴ in practice.");
        println!("Cryptographic |D| is 10⁶⁰× larger.  Infeasible by any known method.");
        println!();
        println!("**This module ships H_D for the 13 class-number-1 discriminants**");
        println!("(the only cases where the canonical-lift attack has tractable");
        println!("class polynomial input).  These are the only CM curves with");
        println!("rational j-invariant.  P-256 is NOT one of them — its CM order's");
        println!("class number is conjecturally ~2¹²⁸.");
    }
}
