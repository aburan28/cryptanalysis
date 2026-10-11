//! **SNFS front end**: special polynomials for `n | c·rᵉ + s`, or an
//! explicit `(f, m)`.
//!
//! For degree `d`, two constructions put `N = c·rᵉ + s` into the form
//! `f(m) ≡ 0 (mod N)` with tiny coefficients:
//!
//! - round `e` **up**: `k = ⌈e/d⌉`, `t = dk − e`, `m = rᵏ`,
//!   `f(x) = c·xᵈ + s·rᵗ` (so `f(m) = rᵗ·N`; monic when `c = 1`);
//! - round `e` **down**: `k = ⌊e/d⌋`, `t = e − dk`, `m = rᵏ`,
//!   `f(x) = c·rᵗ·xᵈ + s` (`f(m) = N`, leading coefficient `c·rᵗ`).
//!
//! Both are scored for every `d ∈ {3, 4, 5, 6}` (or the requested `d`)
//! and the best is sieved.  The norms are what make SNFS fast: the
//! algebraic norm `|c aᵈ + s rᵗ bᵈ|` is tiny next to a base-m
//! polynomial's, so SNFS on a number of difficulty `D` digits costs about
//! what GNFS costs on a number of ~0.7·D digits here (the asymptotic
//! constants are 1.526 vs 1.923).  Parameters default accordingly.
//!
//! Special polynomials are often **reducible** — `x⁴ + 4` is
//! Aurifeuillian, `x⁶ + 1 = (x² + 1)(x⁴ − x² + 1)` — which mirrors the
//! algebraic factors of `rᵉ ± 1`.  A factor `g | f` is found by
//! recombining numerical roots ([`find_integer_factor`]); then either
//! `gcd(g(m), n)` is already a proper factor of `n`, or `n | g(m)` and the
//! sieve continues on the lower-degree `g`.  Polynomials with no inert
//! prime (e.g. `x⁴ + 1`, Galois group `V₄`) cannot use this square root
//! and are skipped.
//!
//! Reference: A. K. Lenstra, H. W. Lenstra Jr., M. S. Manasse and
//! J. M. Pollard, *The factorization of the ninth Fermat number*, Math.
//! Comp. 61 (1993).

use num_bigint::{BigInt, BigUint};
use num_integer::Integer;
use num_traits::{One, Signed, ToPrimitive, Zero};
use serde::Serialize;
use std::time::Instant;

use super::super::arith::{bigint_mod, decimal_digits, secs};
use super::super::ProgressFn;
use super::gnfs::trivial_cases;
use super::poly::{find_integer_factor, IntPoly};
use super::polysel::{find_inert_prime, score, skewness};
use super::{default_bounds, run_core, NfsParams, NfsReport};

/// What SNFS is told about `n`.
#[derive(Clone, Debug, Serialize)]
pub enum SnfsInput {
    /// `n` divides `c·rᵉ + s`.
    Form {
        /// Base `r ≥ 2`.
        r: u64,
        /// Exponent `e ≥ 1`.
        e: u32,
        /// Additive constant `s ≠ 0`.
        s: i64,
        /// Multiplier `c ≥ 1`.
        c: u64,
    },
    /// An explicit polynomial (coefficients lowest first) and root `m`
    /// with `f(m) ≡ 0 (mod n)`.
    Poly {
        /// Coefficients of `f`, lowest degree first.
        #[serde(with = "super::super::serde_big::vec_bigint")]
        coeffs: Vec<BigInt>,
        /// The root `m`.
        #[serde(with = "super::super::serde_big::biguint")]
        m: BigUint,
    },
}

/// Options for [`snfs`].
#[derive(Clone, Debug, Default, Serialize)]
pub struct SnfsParams {
    /// Degree for [`SnfsInput::Form`]; `None` scores 3–6.
    pub degree: Option<usize>,
    /// Sieve and linear-algebra parameters.
    pub nfs: NfsParams,
}

/// SNFS difficulty (digits of `|f(m)|`) → default-parameter size.
fn effective_digits(difficulty: usize) -> usize {
    (difficulty as f64 * 0.7).round() as usize
}

/// The two special polynomials for `c·rᵉ + s` in degree `d`.
fn form_polys(r: u64, e: u32, s: i64, c: u64, d: usize) -> Vec<(IntPoly, BigUint)> {
    let rb = BigInt::from(r);
    let d32 = d as u32;
    let mut out = Vec::new();
    let k_up = e.div_ceil(d32);
    let t_up = d32 * k_up - e;
    let mut f = vec![BigInt::zero(); d + 1];
    f[d] = BigInt::from(c);
    f[0] = BigInt::from(s) * num_traits::pow(rb.clone(), t_up as usize);
    out.push((
        IntPoly::new(f),
        num_traits::pow(BigUint::from(r), k_up as usize),
    ));
    let k_dn = e / d32;
    let t_dn = e - d32 * k_dn;
    if k_dn >= 1 && t_dn > 0 {
        let mut f = vec![BigInt::zero(); d + 1];
        f[d] = BigInt::from(c) * num_traits::pow(rb, t_dn as usize);
        f[0] = BigInt::from(s);
        out.push((
            IntPoly::new(f),
            num_traits::pow(BigUint::from(r), k_dn as usize),
        ));
    }
    out
}

/// Resolve a candidate `(f, m)`: returns a factor of `n`, an irreducible
/// usable polynomial (possibly a factor of `f`), or nothing.
enum Resolved {
    Factor(BigUint),
    Poly(IntPoly),
    Unusable,
}

fn resolve(n: &BigUint, f: IntPoly, m: &BigUint, depth: u32) -> Resolved {
    let mb = BigInt::from(m.clone());
    if f.degree() < 2 || depth > 4 {
        return Resolved::Unusable;
    }
    if let Some(g) = find_integer_factor(&f) {
        let h = f.exact_div(&g).expect("factor divides");
        for part in [g, h] {
            let v = bigint_mod(&part.eval(&mb), n);
            let gg = v.gcd(n);
            if gg > BigUint::one() && &gg < n {
                return Resolved::Factor(gg);
            }
            if v.is_zero() {
                return resolve(n, part, m, depth + 1);
            }
        }
        return Resolved::Unusable;
    }
    if find_inert_prime(&f.monic_transform(), 1 << 20, 400).is_none() {
        return Resolved::Unusable;
    }
    Resolved::Poly(f)
}

/// Factor `n` with the special number field sieve.
pub fn snfs(
    n: &BigUint,
    input: &SnfsInput,
    params: &SnfsParams,
    progress: ProgressFn,
) -> NfsReport {
    let t0 = Instant::now();
    let mut report = NfsReport::new("snfs", n);
    if trivial_cases(&mut report) {
        report.total_seconds = secs(t0);
        return report;
    }
    let candidates: Vec<(IntPoly, BigUint)> = match input {
        SnfsInput::Form { r, e, s, c } => {
            if *r < 2 || *e == 0 || *s == 0 || *c == 0 {
                report.failure = Some("form needs r ≥ 2, e ≥ 1, s ≠ 0, c ≥ 1".into());
                return report;
            }
            let big_n = BigInt::from(*c) * num_traits::pow(BigInt::from(*r), *e as usize) + *s;
            if !bigint_mod(&big_n, n).is_zero() {
                report.failure = Some("n does not divide c·r^e + s".into());
                return report;
            }
            let degrees: Vec<usize> = match params.degree {
                Some(d) => vec![d.max(2)],
                None => (3..=6).collect(),
            };
            degrees
                .into_iter()
                .flat_map(|d| form_polys(*r, *e, *s, *c, d))
                .filter(|(_, m)| m > &BigUint::one())
                .collect()
        }
        SnfsInput::Poly { coeffs, m } => vec![(IntPoly::new(coeffs.clone()), m.clone())],
    };

    // Resolve reducibility, then score what is left.
    let mut best: Option<(f64, IntPoly, BigUint, usize)> = None;
    for (f, m) in candidates {
        let fm = f.eval(&BigInt::from(m.clone()));
        if !bigint_mod(&fm, n).is_zero() {
            continue;
        }
        let f = match resolve(n, f, &m, 0) {
            Resolved::Factor(g) => {
                report.accept(g);
                report.found_in_polyselect = true;
                report.polyselect_seconds = secs(t0);
                report.total_seconds = secs(t0);
                return report;
            }
            Resolved::Unusable => continue,
            Resolved::Poly(f) => f,
        };
        let difficulty = decimal_digits(f.eval(&BigInt::from(m.clone())).magnitude());
        let big_coeffs = f
            .coeffs
            .iter()
            .any(|c| c.abs().to_f64().unwrap_or(f64::MAX) > 1e9);
        let eff = if big_coeffs {
            decimal_digits(n)
        } else {
            effective_digits(difficulty)
        };
        let (rb, ab, area) = default_bounds(eff);
        let (sc, _, _) = score(&f, &m, area, rb, ab);
        if best.as_ref().is_none_or(|b| sc > b.0) {
            best = Some((sc, f, m, eff));
        }
    }
    report.polyselect_seconds = secs(t0);
    let Some((_, f, m, eff)) = best else {
        report.failure = Some("no usable special polynomial (reducible or no inert prime)".into());
        report.total_seconds = secs(t0);
        return report;
    };
    let skew = skewness(&f);
    run_core(&mut report, &f, &m, skew, 1.0, eff, &params.nfs, progress);
    report.total_seconds = secs(t0);
    report
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn snfs_factors_f7() {
        // F7 = 2^128 + 1 = 59649589127497217 · 5704689200685129054721.
        let n = (BigUint::one() << 128) + 1u32;
        let input = SnfsInput::Form {
            r: 2,
            e: 128,
            s: 1,
            c: 1,
        };
        let r = snfs(&n, &input, &SnfsParams::default(), None);
        assert!(r.verified, "{:?}", r.failure);
        assert_eq!(
            r.factor.clone().unwrap(),
            "59649589127497217".parse::<BigUint>().unwrap()
        );
        assert_eq!(r.factor.unwrap() * r.cofactor.unwrap(), n);
    }

    #[test]
    fn snfs_explicit_polynomial() {
        // The same number with f = x^3 + 2, m = 2^43: f(m) = 2·F7.
        let n = (BigUint::one() << 128) + 1u32;
        let input = SnfsInput::Poly {
            coeffs: vec![
                BigInt::from(2),
                BigInt::zero(),
                BigInt::zero(),
                BigInt::one(),
            ],
            m: BigUint::one() << 43,
        };
        let r = snfs(&n, &input, &SnfsParams::default(), None);
        assert!(r.verified, "{:?}", r.failure);
        assert_eq!(r.degree, 3);
    }

    #[test]
    fn snfs_rejects_wrong_form() {
        let n = (BigUint::one() << 128) + 1u32;
        let input = SnfsInput::Form {
            r: 2,
            e: 128,
            s: -1,
            c: 1,
        };
        let r = snfs(&n, &input, &SnfsParams::default(), None);
        assert!(r.factor.is_none());
        assert!(r.failure.unwrap().contains("does not divide"));
    }

    #[test]
    fn aurifeuillian_polynomial_gives_factor_directly() {
        // 2^58 + 1 = 5 · 107367629 · 536903681; with d = 4 the special
        // polynomial is x^4 + 4 (m = 2^14 after rounding up by 2), which
        // factors as (x² + 2x + 2)(x² − 2x + 2): 2^58 + 1 splits as
        // (2^29 − 2^15 + 1)(2^29 + 2^15 + 1).
        let n: BigUint = (BigUint::one() << 58) + 1u32;
        let n = n / 5u32; // strip the small factor
        let input = SnfsInput::Form {
            r: 2,
            e: 58,
            s: 1,
            c: 1,
        };
        let params = SnfsParams {
            degree: Some(4),
            ..Default::default()
        };
        let r = snfs(&n, &input, &params, None);
        assert!(r.verified, "{:?}", r.failure);
        assert!(r.found_in_polyselect);
    }
}
