//! # The exact size of an ordinary isogeny class.
//!
//! §2 of this thread first bounded the class size by pigeonhole — `2(2^n
//! − 1)` curves into `4·2^{n/2} + 1` Hasse-admissible traces gives a
//! *mean* class of `2^{n/2 − 1}`.  The exhaustive census then showed
//! why that is the wrong model for **this** class: at `n = 13` the
//! ECC2K-130 analogue's class has exactly **one** member, because its
//! Frobenius discriminant is `−7` on the nose.  A mean is not a bound on
//! a particular class.
//!
//! The right statement is exact.  By Deuring and Waterhouse (see Schoof
//! 1987, Thm 4.6), the number of `F_q`-isomorphism classes of elliptic
//! curves with `q + 1 − t` points, `p ∤ t`, is the **Kronecker class
//! number**
//!
//! ```text
//!     H(Δ) = Σ_{f' | f} h(f'² · D_K),      Δ = t² − 4q = f² · D_K,
//! ```
//!
//! `D_K` the fundamental discriminant and `f` the conductor of `Z[π]`
//! in `O_K` — one term per order `Z[π] ⊆ O ⊆ O_K`, i.e. one per level of
//! the isogeny volcano.  For a non-maximal order the class number is
//!
//! ```text
//!     h(f'² D_K) = h(D_K) · f' · Π_{p | f'} (1 − (D_K/p)/p) / [O_K^× : O^×].
//! ```
//!
//! ## Why this is computable for ECC2K-130
//!
//! Koblitz curves make `D_K` trivial to find.  The Frobenius of
//! `y² + xy = x³ + 1` over `F_2` satisfies `τ² + τ + 2 = 0`, so
//! `K = Q(√−7)`, `D_K = −7`, `h(D_K) = 1`, and the unit index is `1`
//! because `D_K < −4`.  Over `F_{2^n}` the Frobenius is `τ^n`, so
//!
//! ```text
//!     Δ_n = s_n² − 4·2^n = f_n² · (−7),
//! ```
//!
//! and everything reduces to factoring the single integer `f_n`.  At
//! `n = 131`, `f = 38 531 015 900 842 053 623 = 263 · 146 505 763 881 528 721`
//! — 66 bits, and trivially factored.
//!
//! ## The check that licenses the extrapolation
//!
//! [`koblitz_class_size`] is compared against the **exhaustive
//! Kloosterman census** at every `n` the census reaches.  The two agree
//! exactly (`n = 7 → 8`, `9 → 19`, `11 → 23`, `13 → 1`, …), so the
//! `n = 131` value is an evaluation of a validated formula rather than
//! an extrapolation of a trend.

use num_bigint::{BigInt, BigUint};
use num_integer::Integer;
use num_traits::{One, Zero};

/// Fundamental discriminant of the CM field of every Koblitz curve:
/// `τ² + τ + 2 = 0` generates `Q(√−7)`.
pub const KOBLITZ_D_K: i64 = -7;

/// Class number of `Q(√−7)`.
pub const KOBLITZ_H_DK: u64 = 1;

// ── Integer factorisation, enough for a 66-bit conductor ───────────

/// `a · b mod m`, correct for any `m < 2^64`.
fn mulmod(a: u64, b: u64, m: u64) -> u64 {
    ((a as u128 * b as u128) % m as u128) as u64
}

fn powmod(mut a: u64, mut e: u64, m: u64) -> u64 {
    let mut r = 1u64;
    a %= m;
    while e > 0 {
        if e & 1 == 1 {
            r = mulmod(r, a, m);
        }
        a = mulmod(a, a, m);
        e >>= 1;
    }
    r
}

/// Deterministic Miller–Rabin for `n < 2^64`.
pub fn is_prime_u64(n: u64) -> bool {
    if n < 2 {
        return false;
    }
    for p in [2u64, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37] {
        if n.is_multiple_of(p) {
            return n == p;
        }
    }
    let mut d = n - 1;
    let mut r = 0u32;
    while d.is_multiple_of(2) {
        d /= 2;
        r += 1;
    }
    'outer: for a in [2u64, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37] {
        let mut x = powmod(a, d, n);
        if x == 1 || x == n - 1 {
            continue;
        }
        for _ in 0..r - 1 {
            x = mulmod(x, x, n);
            if x == n - 1 {
                continue 'outer;
            }
        }
        return false;
    }
    true
}

/// Brent's variant of Pollard's rho.  Deterministic: the polynomial's
/// shift walks `1, 2, 3, …` rather than being drawn at random, so a
/// reported factorisation is reproducible.
fn pollard_rho(n: u64) -> u64 {
    if n.is_multiple_of(2) {
        return 2;
    }
    for c in 1u64.. {
        let f = |x: u64| (mulmod(x, x, n) + c) % n;
        let (mut x, mut y, mut d) = (2u64, 2u64, 1u64);
        while d == 1 {
            x = f(x);
            y = f(f(y));
            d = x.abs_diff(y).gcd(&n);
        }
        if d != n {
            return d;
        }
    }
    unreachable!()
}

/// Prime factorisation of `n`, as sorted `(prime, exponent)` pairs.
pub fn factor_u64(mut n: u64) -> Vec<(u64, u32)> {
    let mut out: Vec<(u64, u32)> = Vec::new();
    let push = |out: &mut Vec<(u64, u32)>, p: u64| match out.iter_mut().find(|e| e.0 == p) {
        Some(e) => e.1 += 1,
        None => out.push((p, 1)),
    };
    for p in 2u64..100_000 {
        if p * p > n {
            break;
        }
        while n.is_multiple_of(p) {
            push(&mut out, p);
            n /= p;
        }
    }
    let mut stack = if n > 1 { vec![n] } else { vec![] };
    while let Some(m) = stack.pop() {
        if m == 1 {
            continue;
        }
        if is_prime_u64(m) {
            push(&mut out, m);
            continue;
        }
        let d = pollard_rho(m);
        stack.push(d);
        stack.push(m / d);
    }
    out.sort_unstable();
    out
}

/// Prime factorisation of a `BigUint` that fits the conductor range:
/// small primes are stripped first, and the cofactor must then fit
/// `u64`.  Returns `None` if it does not — which never happens for the
/// discriminants this thread computes, and is reported rather than
/// guessed at if it ever does.
pub fn factor_conductor(f: &BigUint) -> Option<Vec<(u64, u32)>> {
    let mut rest = f.clone();
    let mut out: Vec<(u64, u32)> = Vec::new();
    for p in 2u64..100_000 {
        let pb = BigUint::from(p);
        if &pb * &pb > rest {
            break;
        }
        let mut e = 0u32;
        while (&rest % &pb).is_zero() {
            rest /= &pb;
            e += 1;
        }
        if e > 0 {
            out.push((p, e));
        }
    }
    if rest.is_one() {
        out.sort_unstable();
        return Some(out);
    }
    let small: u64 = rest.try_into().ok()?;
    for (p, e) in factor_u64(small) {
        match out.iter_mut().find(|q| q.0 == p) {
            Some(q) => q.1 += e,
            None => out.push((p, e)),
        }
    }
    out.sort_unstable();
    Some(out)
}

// ── Kronecker symbol and class numbers ─────────────────────────────

/// `(d / p)` for a prime `p`, including `p = 2`.
pub fn kronecker_symbol(d: i64, p: u64) -> i32 {
    if p == 2 {
        if d % 2 == 0 {
            return 0;
        }
        return if d.rem_euclid(8) == 1 || d.rem_euclid(8) == 7 {
            1
        } else {
            -1
        };
    }
    let a = d.rem_euclid(p as i64) as u64;
    if a == 0 {
        return 0;
    }
    if powmod(a, (p - 1) / 2, p) == 1 {
        1
    } else {
        -1
    }
}

/// `h(f² · D_K)` for an imaginary quadratic `D_K < −4`, where the unit
/// index is `1`:
///
/// ```text
///     h(f² D_K) = h(D_K) · f · Π_{p | f} (1 − (D_K/p)/p).
/// ```
///
/// Computed as `h(D_K) · (f / Π p) · Π (p − (D_K/p))`, which is integral
/// at every step.
pub fn order_class_number(h_dk: u64, d_k: i64, f: &BigUint, f_primes: &[u64]) -> BigUint {
    let mut num = BigUint::from(h_dk) * f;
    for &p in f_primes {
        num /= BigUint::from(p);
    }
    for &p in f_primes {
        let chi = kronecker_symbol(d_k, p);
        let term = (p as i64 - chi as i64) as u64;
        num *= BigUint::from(term);
    }
    num
}

/// Every divisor of `f`, from its factorisation.
pub fn divisors(factors: &[(u64, u32)]) -> Vec<BigUint> {
    let mut out = vec![BigUint::one()];
    for &(p, e) in factors {
        let mut next = Vec::with_capacity(out.len() * (e as usize + 1));
        for d in &out {
            let mut cur = d.clone();
            for _ in 0..=e {
                next.push(cur.clone());
                cur *= BigUint::from(p);
            }
        }
        out = next;
    }
    out.sort();
    out.dedup();
    out
}

/// The size and shape of one ordinary isogeny class.
#[derive(Clone, Debug)]
pub struct IsogenyClassSize {
    /// `Δ = t² − 4q`.
    pub disc: BigInt,
    /// Fundamental discriminant `D_K`.
    pub d_k: i64,
    /// Conductor `f` of `Z[π]` in `O_K`.
    pub conductor: BigUint,
    /// Factorisation of `f` — one volcano level per divisor.
    pub conductor_factors: Vec<(u64, u32)>,
    /// Number of orders `Z[π] ⊆ O ⊆ O_K`, i.e. divisors of `f`.
    pub orders: usize,
    /// `h(Δ)` — the class number of `Z[π]` itself, the volcano floor.
    pub floor_class_number: BigUint,
    /// `H(Δ) = Σ_{f'|f} h(f'² D_K)` — **the exact number of
    /// `F_q`-isomorphism classes in the isogeny class**.
    pub class_size: BigUint,
}

impl IsogenyClassSize {
    /// `log2` of the class size.
    pub fn log2(&self) -> f64 {
        super::cost::log2_big(&self.class_size)
    }
}

/// The conductor `f` of `Z[π]` in `O_K`, for a Koblitz discriminant
/// `Δ = f²·(−7)`.
///
/// `None` if `Δ` does not have that shape, which for a Koblitz curve
/// means the caller passed something that is not a Koblitz trace.
pub fn koblitz_conductor(disc: &BigInt) -> Option<BigUint> {
    if disc.sign() != num_bigint::Sign::Minus {
        return None;
    }
    let magnitude = disc.magnitude().clone();
    let seven = BigUint::from(7u32);
    if !(&magnitude % &seven).is_zero() {
        return None;
    }
    let m = &magnitude / &seven;
    let f = m.sqrt();
    (&f * &f == m).then_some(f)
}

/// The primes dividing the conductor of `Z[π]` in `O_K`.
pub fn koblitz_conductor_primes(disc: &BigInt) -> Option<Vec<u64>> {
    let f = koblitz_conductor(disc)?;
    Some(factor_conductor(&f)?.into_iter().map(|(p, _)| p).collect())
}

/// **The exact isogeny class size** for a Koblitz curve over `F_{2^n}`,
/// from its trace.
///
/// `Δ = t² − 2^{n+2}` must equal `f² · (−7)`; that it does is checked,
/// not assumed, and a failure means the caller passed a trace that is
/// not a Koblitz trace.
pub fn koblitz_class_size(t: i128, n: u32) -> Option<IsogenyClassSize> {
    let q = BigInt::one() << n;
    let disc = BigInt::from(t) * BigInt::from(t) - BigInt::from(4) * &q;
    let f = koblitz_conductor(&disc)?;
    let conductor_factors = factor_conductor(&f)?;
    let primes: Vec<u64> = conductor_factors.iter().map(|(p, _)| *p).collect();
    let floor_class_number = order_class_number(KOBLITZ_H_DK, KOBLITZ_D_K, &f, &primes);

    let divs = divisors(&conductor_factors);
    let mut class_size = BigUint::zero();
    for d in &divs {
        let d_primes: Vec<u64> = primes
            .iter()
            .copied()
            .filter(|p| (d % BigUint::from(*p)).is_zero())
            .collect();
        class_size += order_class_number(KOBLITZ_H_DK, KOBLITZ_D_K, d, &d_primes);
    }

    Some(IsogenyClassSize {
        disc,
        d_k: KOBLITZ_D_K,
        conductor: f,
        orders: divs.len(),
        conductor_factors,
        floor_class_number,
        class_size,
    })
}

/// The ECC2K-130 isogeny class, exactly.
pub fn ecc2k130_class_size() -> IsogenyClassSize {
    let t = super::census::koblitz_trace_recurrence(-1, 131);
    koblitz_class_size(t, 131).expect("ECC2K-130's Frobenius has discriminant f²·(−7)")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::isogeny_degree_search::census::{
        koblitz_trace_recurrence, IsogenyCensus,
    };
    use crate::cryptanalysis::koblitz_index_calculus::find_irreducible;

    /// The class-number formula must reproduce the **exhaustive**
    /// census, curve for curve, at every `n` the census reaches.  This
    /// is what licenses evaluating it at `n = 131`.
    #[test]
    fn class_number_formula_matches_the_exhaustive_census() {
        for n in [5u32, 7, 9, 11, 13, 15, 17] {
            let irr = find_irreducible(n).unwrap();
            let census = IsogenyCensus::build(n, &irr);
            let measured = census.koblitz_class().len();
            let t = koblitz_trace_recurrence(-1, n);
            let predicted =
                koblitz_class_size(t, n).unwrap_or_else(|| panic!("n = {n}: Δ must be f²·(−7)"));
            assert_eq!(
                BigUint::from(measured),
                predicted.class_size,
                "n = {n}: census counted {measured}, H(Δ) says {}",
                predicted.class_size
            );
        }
    }

    /// ECC2K-130's class, exactly.  `Δ = f²·(−7)` with a 66-bit
    /// conductor that splits into two primes, so the volcano has four
    /// levels and the class holds ≈ 2^65 curves.
    #[test]
    fn ecc2k130_class_is_two_to_the_sixty_five() {
        let c = ecc2k130_class_size();
        assert_eq!(c.d_k, -7);
        assert_eq!(
            c.conductor.to_string(),
            "38531015900842053623",
            "conductor of Z[π] in Z[(1+√−7)/2]"
        );
        assert_eq!(
            c.conductor_factors,
            vec![(263u64, 1u32), (146_505_763_881_528_721u64, 1u32)]
        );
        assert_eq!(c.orders, 4, "one order per divisor of f");
        assert_eq!(
            c.class_size.to_string(),
            "38531015900842054149",
            "exact number of curves isogenous to ECC2K-130"
        );
        assert!(
            (c.log2() - 65.06).abs() < 0.01,
            "log2 class size = {}",
            c.log2()
        );
    }

    /// Sanity: the conductor really does satisfy `Δ = f²·D_K`.
    #[test]
    fn conductor_squares_back_to_the_discriminant() {
        let c = ecc2k130_class_size();
        let rebuilt = BigInt::from(c.conductor.clone())
            * BigInt::from(c.conductor.clone())
            * BigInt::from(-7);
        assert_eq!(rebuilt, c.disc);
    }

    /// Factorisation must be right, including on a hard-ish semiprime.
    #[test]
    fn factorisation_is_correct() {
        assert_eq!(factor_u64(146_505_763_881_528_721).len(), 1, "prime");
        assert!(is_prime_u64(146_505_763_881_528_721));
        let n = 1_000_003u64 * 1_000_033u64;
        assert_eq!(factor_u64(n), vec![(1_000_003, 1), (1_000_033, 1)]);
        assert_eq!(factor_u64(720), vec![(2, 4), (3, 2), (5, 1)]);
    }
}
