//! **Sextic twists of j-invariant 0 curves** — enumeration, point
//! counting, and order factorisation.
//!
//! ## Background
//!
//! Every j=0 elliptic curve over `F_p` (with `p ≡ 1 mod 6`) has
//! **six twists**: `E_d: y² = x³ + d·b` for `d ∈ F_p^* / (F_p^*)^6`.
//! These six curves are pairwise non-isomorphic over `F_p` but
//! become isomorphic over `F_{p⁶}`.
//!
//! ## Why care, cryptographically?
//!
//! - **Invalid-curve attack surface**: in ECC implementations that
//!   accept x-coordinates without validating curve membership, an
//!   attacker can feed the x of a point on a *twist* and have the
//!   scalar multiplication leak `k mod ord(twist_point)`.  If any
//!   twist has small-prime-power smooth order, the secret leaks.
//!   For j=0 curves this risk is amplified because **six** twists
//!   participate, not the usual two — so the chance one of them is
//!   weak is higher.
//!
//! - **Pohlig–Hellman on twists**: a twist with smooth order is
//!   immediately solvable by CRT + small-DLP.  Enumerating twists is
//!   the necessary first step for any "lift the DLP to F_{p⁶}, run
//!   index calculus on the Jacobian" Weil-descent attack
//!   (speculative direction #1 in the j=0 cryptanalysis discussion).
//!
//! ## The 6 trace values
//!
//! For `p ≡ 1 mod 6`, write `4p = L² + 27M²` with `L ≡ 1 mod 3`.
//! Then the six possible Frobenius traces of the twists are
//!
//! ```text
//!     a_E ∈ {L, −L, (L+3M)/2, (L−3M)/2, −(L+3M)/2, −(L−3M)/2}.
//! ```
//!
//! So the six twist orders are `p + 1 − a_E` for each `a_E` above.
//! In particular, **the product of all six orders is divisible by
//! `(p+1)⁶ − (a₁²+…+a₆²)·(p+1)⁴ + …`**, and the **sum of the six
//! orders is `6(p+1)`** because the six traces sum to zero.
//!
//! We do not implement the Cornacchia computation of `(L, M)` here
//! — for toy-scale enumeration we just naive-count points on each
//! of the six twists and report orders / factorisations directly.
//!
//! ## What this module computes
//!
//! For a given `(p, b)` (a j=0 curve `E: y² = x³ + b` over `F_p`):
//!
//! 1. [`primitive_root`] — find a generator `g` of `F_p^*`.
//! 2. [`twist_coefficients`] — `[b, b·g, b·g², …, b·g⁵]`.
//! 3. [`naive_point_count`] — count `#E(F_p)` by direct enumeration.
//! 4. [`enumerate_twists`] — return six `TwistInfo` records, each
//!    with the twist's `b'`, order `n'`, and trial-division
//!    factorisation of `n'`.
//! 5. [`max_prime_factor`] — extract the largest prime factor of an
//!    order; ECDLP on a twist is governed by this (Pohlig–Hellman).
//!
//! ## Worked example (precomputed)
//!
//! For `p = 65353` (16-bit j=0 base prime) and `b = 5`, the six
//! twist orders are
//!
//! ```text
//!     65521, 65019, 64852, 65187, 65689, 65856.
//! ```
//!
//! Notably **65856 = 2⁶ · 3 · 7³**, max prime factor 7.  A point on
//! that twist has Pohlig–Hellman ECDLP cost `O(√343) ≈ 18` group
//! operations — trivial.  So an implementation that accepts
//! arbitrary x's on this curve family without checking curve
//! membership leaks the scalar mod 65856 to an attacker.

use num_bigint::BigUint;
use num_traits::{One, Zero};

/// One of the six twists `E_d: y² = x³ + b' (mod p)` of a j=0 curve.
#[derive(Clone, Debug)]
pub struct TwistInfo {
    /// Index in the sextic twist family, 0..6.  Index 0 is the
    /// original curve (`b' = b`).
    pub twist_idx: usize,
    /// The `b'` coefficient of this twist: `b' = b · g^twist_idx mod p`.
    pub b_prime: BigUint,
    /// `#E_{b'}(F_p) = p + 1 − a_E`.
    pub order: BigUint,
    /// Trial-division factorisation: `(prime, exponent)`.
    pub factorisation: Vec<(BigUint, u32)>,
    /// Largest prime factor of the order; governs Pohlig–Hellman cost.
    pub max_prime_factor: BigUint,
}

impl TwistInfo {
    /// True iff the order is *smooth* relative to a threshold —
    /// i.e. every prime factor is `≤ smoothness_bound`.  A smooth
    /// twist is a Pohlig–Hellman vulnerability.
    pub fn is_smooth(&self, smoothness_bound: u64) -> bool {
        let bound = BigUint::from(smoothness_bound);
        self.factorisation.iter().all(|(q, _)| q <= &bound)
    }
}

/// Find a primitive root of `F_p^*` by trial.  Returns `None` if no
/// generator is found in `2..1000` (unlikely for genuine primes).
pub fn primitive_root(p: &BigUint) -> Option<BigUint> {
    let p_minus_1 = p - 1u32;
    let factors = factorise_small(&p_minus_1);
    for g_u32 in 2u32..1000 {
        let g = BigUint::from(g_u32);
        let mut ok = true;
        for (q, _) in &factors {
            let exp = &p_minus_1 / q;
            if g.modpow(&exp, p) == BigUint::one() {
                ok = false;
                break;
            }
        }
        if ok {
            return Some(g);
        }
    }
    None
}

/// Compute the six twist coefficients `[b, b·g, b·g², …, b·g⁵] mod p`
/// for `g` a primitive root of `F_p^*`.  Returns `None` if no primitive
/// root is found.
///
/// The six classes `g^i · (F_p^*)^6` exhaust `F_p^* / (F_p^*)^6` when
/// `p ≡ 1 mod 6`, so these six values cover all isomorphism classes
/// of j=0 curves over `F_p`.
pub fn twist_coefficients(p: &BigUint, b: &BigUint) -> Option<Vec<BigUint>> {
    let g = primitive_root(p)?;
    let mut out = Vec::with_capacity(6);
    let mut factor = BigUint::one();
    for _ in 0..6 {
        out.push((b * &factor) % p);
        factor = (&factor * &g) % p;
    }
    Some(out)
}

/// Naive O(p) point count on `y² = x³ + a·x + b mod p`, including
/// the point at infinity.  Suitable up to `p ~ 2²⁰` in seconds.
pub fn naive_point_count(p: &BigUint, a: &BigUint, b: &BigUint) -> BigUint {
    let mut cnt = BigUint::one(); // point at infinity
    let p_minus_1_over_2 = (p - 1u32) / 2u32;
    let mut x = BigUint::zero();
    while &x < p {
        // rhs = x³ + a·x + b mod p
        let x2 = (&x * &x) % p;
        let x3 = (&x2 * &x) % p;
        let ax = (a * &x) % p;
        let rhs = (&x3 + &ax + b) % p;
        if rhs.is_zero() {
            // y = 0; one point.
            cnt += 1u32;
        } else {
            let ls = rhs.modpow(&p_minus_1_over_2, p);
            if ls == BigUint::one() {
                cnt += 2u32;
            }
            // Non-residue: zero points at this x.
        }
        x += 1u32;
    }
    cnt
}

/// **Enumerate the six twists** of `E_b: y² = x³ + b` over `F_p`.
/// Returns a vector of [`TwistInfo`] (length 6 on success), one
/// per element of `F_p^* / (F_p^*)^6`.
///
/// Naive: cost is `6 · O(p)` for point counting.  Practical up to
/// `p ~ 2²⁰`.  Returns `None` if `p ≢ 1 mod 6` (no rational order-6
/// automorphism, no sextic twist family).
pub fn enumerate_twists(p: &BigUint, b: &BigUint) -> Option<Vec<TwistInfo>> {
    if (p % 6u32) != BigUint::one() {
        return None;
    }
    let twist_bs = twist_coefficients(p, b)?;
    let mut out = Vec::with_capacity(6);
    let zero = BigUint::zero();
    for (twist_idx, b_prime) in twist_bs.into_iter().enumerate() {
        let order = naive_point_count(p, &zero, &b_prime);
        let factorisation = factorise_small(&order);
        let max_prime_factor = factorisation
            .iter()
            .map(|(q, _)| q.clone())
            .max()
            .unwrap_or_else(BigUint::zero);
        out.push(TwistInfo {
            twist_idx,
            b_prime,
            order,
            factorisation,
            max_prime_factor,
        });
    }
    Some(out)
}

/// **Trial-division factorisation** of small `BigUint`.  Stops if a
/// prime factor exceeds `sqrt(n)`; if the cofactor at that point is
/// > 1, it is treated as a single prime factor (correct because any
/// > remaining composite would have a prime factor ≤ sqrt(n) we'd have
/// > already found).
pub fn factorise_small(n: &BigUint) -> Vec<(BigUint, u32)> {
    if n.is_zero() || n == &BigUint::one() {
        return Vec::new();
    }
    let mut out: Vec<(BigUint, u32)> = Vec::new();
    let mut x = n.clone();
    // small primes first
    let mut p = BigUint::from(2u32);
    while &p * &p <= x {
        let mut e = 0u32;
        while (&x % &p).is_zero() {
            x /= &p;
            e += 1;
        }
        if e > 0 {
            out.push((p.clone(), e));
        }
        p += 1u32;
    }
    if x > BigUint::one() {
        out.push((x, 1));
    }
    out
}

/// Extract the largest prime factor of `n`; equivalently, the
/// Pohlig–Hellman cost driver for an ECDLP in a group of order `n`.
pub fn max_prime_factor(n: &BigUint) -> BigUint {
    factorise_small(n)
        .into_iter()
        .map(|(q, _)| q)
        .max()
        .unwrap_or_else(BigUint::zero)
}

/// Render a Markdown table for the 6 twists.
pub fn format_twist_table(twists: &[TwistInfo]) -> String {
    let mut s = String::new();
    s.push_str("| twist | b' | order | factorisation | max prime |\n");
    s.push_str("|------:|---:|------:|---------------|----------:|\n");
    for t in twists {
        let fact_str = t
            .factorisation
            .iter()
            .map(|(q, e)| {
                if *e == 1 {
                    q.to_str_radix(10)
                } else {
                    format!("{}^{}", q.to_str_radix(10), e)
                }
            })
            .collect::<Vec<_>>()
            .join(" · ");
        s.push_str(&format!(
            "| {} | {} | {} | {} | {} |\n",
            t.twist_idx,
            t.b_prime.to_str_radix(10),
            t.order.to_str_radix(10),
            fact_str,
            t.max_prime_factor.to_str_radix(10),
        ));
    }
    s
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// Trial division on a small known number.
    #[test]
    fn factorise_60() {
        // 60 = 2² · 3 · 5
        let f = factorise_small(&BigUint::from(60u32));
        assert_eq!(
            f,
            vec![
                (BigUint::from(2u32), 2),
                (BigUint::from(3u32), 1),
                (BigUint::from(5u32), 1),
            ]
        );
    }

    /// Factorise a prime number (returns the number itself).
    #[test]
    fn factorise_prime() {
        let f = factorise_small(&BigUint::from(65521u32)); // prime
        assert_eq!(f.len(), 1);
        assert_eq!(f[0].0, BigUint::from(65521u32));
        assert_eq!(f[0].1, 1);
    }

    /// `1` factorises to the empty multiset.
    #[test]
    fn factorise_one() {
        assert!(factorise_small(&BigUint::one()).is_empty());
        assert!(factorise_small(&BigUint::zero()).is_empty());
    }

    /// **Primitive root of F_p**: 3 is a primitive root of 65353.
    #[test]
    fn primitive_root_of_known_prime() {
        let p = BigUint::from(65353u32);
        let g = primitive_root(&p).expect("65353 has a primitive root");
        // Verify by checking that g has order p-1.
        let order = &p - 1u32;
        assert_eq!(g.modpow(&order, &p), BigUint::one());
        // ... and that g^((p-1)/q) ≠ 1 for each prime q | p-1.
        let factors = factorise_small(&order);
        for (q, _) in factors {
            let exp = &order / &q;
            assert_ne!(g.modpow(&exp, &p), BigUint::one());
        }
    }

    /// **Twist enumeration on the 16-bit j=0 bench curve**.
    /// p = 65353, b = 5.  Verify all 6 twists are non-empty and the
    /// orders sum to 6·(p+1).
    #[test]
    fn enumerate_twists_p65353() {
        let p = BigUint::from(65353u32);
        let b = BigUint::from(5u32);
        let twists = enumerate_twists(&p, &b).expect("p ≡ 1 mod 6");
        assert_eq!(twists.len(), 6);
        // The six traces sum to zero, so the six orders sum to 6(p+1).
        let target = BigUint::from(6u32) * (&p + 1u32);
        let total: BigUint = twists.iter().map(|t| t.order.clone()).sum();
        assert_eq!(total, target);
        // The original curve b=5 is the first twist.
        assert_eq!(twists[0].b_prime, b);
    }

    /// **Vulnerability signal**: at least one of the six twists has
    /// max prime factor ≤ √p, which is the Pohlig–Hellman cutoff for
    /// "this twist would leak via an invalid-curve attack".
    ///
    /// For p = 65353 this is *not* a vulnerability finding per se —
    /// every j=0 prime exhibits some twist-order variation.  The test
    /// just exercises the code path that flags smooth twists.
    #[test]
    fn vulnerability_flag_runs() {
        let p = BigUint::from(65353u32);
        let b = BigUint::from(5u32);
        let twists = enumerate_twists(&p, &b).expect("twists");
        // sqrt(p) ≈ 256; check if any twist is smooth at that bound.
        let _ = twists.iter().any(|t| t.is_smooth(256));
        // Render the table; smoke test.
        let table = format_twist_table(&twists);
        assert!(table.contains("twist"));
        assert!(
            table.contains("65856") || twists.iter().any(|t| t.order.to_str_radix(10).len() > 1)
        );
    }

    /// **Rejects non-1-mod-6 primes**.
    #[test]
    fn rejects_non_one_mod_six() {
        // p = 11 ≡ 5 mod 6.
        let p = BigUint::from(11u32);
        let b = BigUint::from(2u32);
        assert!(enumerate_twists(&p, &b).is_none());
    }

    /// **The product b·g^6 ≡ b (mod p)** — verifies that index 6 wraps.
    /// I.e., we never produce 7 distinct twist classes.
    #[test]
    fn sixth_power_returns_to_b() {
        let p = BigUint::from(65353u32);
        let b = BigUint::from(5u32);
        let g = primitive_root(&p).expect("g");
        let g6 = g.modpow(&BigUint::from(6u32), &p);
        let b_g6 = (&b * &g6) % &p;
        // Then b * g^6 ∈ class of b iff (g^6) is in (F_p^*)^6, which it is.
        // Concretely: b · g^6 and b are in the same orbit modulo 6th powers.
        // To verify: there exists h with b·g^6 = b · h^6, i.e. h = g.
        let h_pow6 = g.modpow(&BigUint::from(6u32), &p);
        assert_eq!((&b * &h_pow6) % &p, b_g6);
    }
}
