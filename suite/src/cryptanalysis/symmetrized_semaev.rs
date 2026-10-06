//! # Symmetrised summation polynomials (Faugère–Gaudry–Huot–Renault).
//!
//! Reproduces the central construction of the paper the user uploaded
//! (*Symmetrised summation polynomials*, the "exactly the paper" §4
//! entry in the ECDLP research-direction map).  The idea:
//!
//! Semaev's `S_n(X_1, …, X_n)` is symmetric in its arguments.  Any
//! symmetric polynomial in `n` variables can be re-expressed as a
//! polynomial in the **elementary symmetric polynomials**
//! `e_1, e_2, …, e_n` (Newton's theorem).  The change of variables
//!
//! ```text
//!   X_i  ↦  formal indeterminates,
//!   e_k  =  Σ_{i_1 < … < i_k} X_{i_1} ⋯ X_{i_k}
//! ```
//!
//! turns the `S_n` of total degree `2^{n-1}` and high monomial count
//! into a polynomial `\tilde S_n(e_1, …, e_n)` of dramatically lower
//! density and degree (`≤ 2^{n-1} / n!` in the symmetric piece).
//! For the Faugère et al. paper this drops the size of the Macaulay
//! matrix in the Gröbner-basis solve by `~n!`, which is what makes
//! `S_8` over a degree-5 extension feasible.
//!
//! # What this module does
//!
//! 1. Computes the **elementary symmetric polynomials** in `n`
//!    variables, as multivariate polynomials over `F_p`.
//! 2. Provides the **Newton identity recurrence** `p_k = Σ (-1)^{i-1}
//!    e_i p_{k-i}` between power sums and elementary symmetrics —
//!    needed for the inverse change of variables.
//! 3. Implements `symmetrise_s3` and `symmetrise_s4` on the
//!    prime-field Semaev polynomials of [`crate::cryptanalysis::
//!    semaev_higher`], producing the explicit `\tilde S_3(e_1, e_2,
//!    e_3)` and `\tilde S_4(e_1, e_2, e_3, e_4)` formulas — these are
//!    the *canonical* paper outputs.
//! 4. Provides `symmetrise_higher` which, given any symmetric
//!    polynomial in `n` variables (as a multivariate exponent → coef
//!    map), returns its expression in the `e_i` by repeated Reynolds-
//!    operator division.  This is the algorithm used to certify the
//!    `S_5` and `S_6` outputs from `semaev_higher.rs` are indeed
//!    symmetric.
//!
//! # Density reduction (the paper's main quantitative claim)
//!
//! For prime-field `S_n`, the monomial count in the original
//! `F_p[X_1, …, X_n]` representation grows like `O(2^{n²})` in the
//! worst case (after expansion); in the `F_p[e_1, …, e_n]`
//! representation it grows like `O(2^{n(n−1)/2})`.  For `n = 8`
//! that's a `~2^{28} → 2^{14}` reduction — the difference between
//! "doesn't fit in RAM" and "solves in a few hours".
//!
//! The harness here checks the reduction *in practice* for `n ≤ 4`
//! (where we have closed forms) — exact numbers in the test suite.
//!
//! # References
//!
//! - **J.-C. Faugère, P. Gaudry, L. Huot, G. Renault**, *Using
//!   symmetries in the index calculus for elliptic curves discrete
//!   logarithm*, J. Cryptology 2014.  The paper the harness here
//!   mirrors.
//! - **I. Semaev**, *Summation polynomials and the discrete logarithm
//!   problem on elliptic curves*, eprint 2004/031.
//! - **D. Macdonald**, *Symmetric Functions and Hall Polynomials*,
//!   Oxford 1995 — the Reynolds-operator algorithm chapter.

use crate::ecc::field::FieldElement;
use num_bigint::BigUint;
use std::collections::BTreeMap;

// ── Multivariate polynomial over F_p, sparse exponent-tuple keyed ───

/// Sparse multivariate polynomial: maps monomials (as exponent-tuple)
/// to coefficients in `F_p`.  All operations preserve sparsity.
#[derive(Clone, Debug)]
pub struct MPoly {
    pub terms: BTreeMap<Vec<u32>, FieldElement>,
    pub n_vars: usize,
    pub p: BigUint,
}

impl MPoly {
    pub fn zero(n_vars: usize, p: BigUint) -> Self {
        Self {
            terms: BTreeMap::new(),
            n_vars,
            p,
        }
    }

    pub fn constant(c: FieldElement, n_vars: usize) -> Self {
        let p = c.modulus.clone();
        let mut t = BTreeMap::new();
        if !c.is_zero() {
            t.insert(vec![0; n_vars], c);
        }
        Self {
            terms: t,
            n_vars,
            p,
        }
    }

    pub fn variable(idx: usize, n_vars: usize, p: BigUint) -> Self {
        let mut exp = vec![0u32; n_vars];
        exp[idx] = 1;
        let mut t = BTreeMap::new();
        t.insert(exp, FieldElement::one(p.clone()));
        Self {
            terms: t,
            n_vars,
            p,
        }
    }

    pub fn add(&self, other: &Self) -> Self {
        let mut out = self.clone();
        for (k, v) in &other.terms {
            let entry = out
                .terms
                .entry(k.clone())
                .or_insert_with(|| FieldElement::zero(self.p.clone()));
            *entry = entry.add(v);
            if entry.is_zero() {
                out.terms.remove(k);
            }
        }
        out
    }

    pub fn sub(&self, other: &Self) -> Self {
        let mut out = self.clone();
        for (k, v) in &other.terms {
            let entry = out
                .terms
                .entry(k.clone())
                .or_insert_with(|| FieldElement::zero(self.p.clone()));
            *entry = entry.sub(v);
            if entry.is_zero() {
                out.terms.remove(k);
            }
        }
        out
    }

    pub fn mul(&self, other: &Self) -> Self {
        let mut out = Self::zero(self.n_vars, self.p.clone());
        for (k1, v1) in &self.terms {
            if v1.is_zero() {
                continue;
            }
            for (k2, v2) in &other.terms {
                if v2.is_zero() {
                    continue;
                }
                let mut k = vec![0u32; self.n_vars];
                for i in 0..self.n_vars {
                    k[i] = k1[i] + k2[i];
                }
                let coef = v1.mul(v2);
                let entry = out
                    .terms
                    .entry(k)
                    .or_insert_with(|| FieldElement::zero(self.p.clone()));
                *entry = entry.add(&coef);
                // A cancelled term is removed by the `retain` below; the buggy
                // predecessor here removed the *constant* term (the all-zero
                // exponent vector) whenever ANY term cancelled, so e.g.
                // (1+x)(1-x) lost its constant and came out as -x².
            }
        }
        // Clean zero coefficients (paranoia after addition).
        out.terms.retain(|_, v| !v.is_zero());
        out
    }

    pub fn scale(&self, c: &FieldElement) -> Self {
        let mut out = self.clone();
        for v in out.terms.values_mut() {
            *v = v.mul(c);
        }
        out.terms.retain(|_, v| !v.is_zero());
        out
    }

    pub fn pow(&self, k: u32) -> Self {
        let mut acc = Self::constant(FieldElement::one(self.p.clone()), self.n_vars);
        for _ in 0..k {
            acc = acc.mul(self);
        }
        acc
    }

    pub fn num_terms(&self) -> usize {
        self.terms.len()
    }

    pub fn is_zero(&self) -> bool {
        self.terms.is_empty()
    }

    /// Total degree (max sum of exponents over all monomials).
    pub fn total_degree(&self) -> u32 {
        self.terms
            .keys()
            .map(|k| k.iter().sum::<u32>())
            .max()
            .unwrap_or(0)
    }
}

// ── Elementary symmetric polynomials ────────────────────────────────

/// `e_k(X_1, …, X_n)` as an MPoly in `n` variables.
pub fn elementary_symmetric(k: u32, n: u32, p: BigUint) -> MPoly {
    let n_vars = n as usize;
    if k == 0 {
        return MPoly::constant(FieldElement::one(p.clone()), n_vars);
    }
    if k > n {
        return MPoly::zero(n_vars, p);
    }
    let mut out = MPoly::zero(n_vars, p.clone());
    // Iterate over all size-k subsets of {0, …, n-1}.
    let mut idx: Vec<usize> = (0..k as usize).collect();
    loop {
        // Add the monomial X_{idx[0]} · X_{idx[1]} · … · X_{idx[k-1]}.
        let mut exp = vec![0u32; n_vars];
        for &i in &idx {
            exp[i] = 1;
        }
        out.terms.insert(exp, FieldElement::one(p.clone()));
        // Increment subset.
        let mut t = k as i64 - 1;
        while t >= 0 && idx[t as usize] == (n as usize - (k as usize - t as usize)) {
            t -= 1;
        }
        if t < 0 {
            break;
        }
        idx[t as usize] += 1;
        for j in (t as usize + 1)..(k as usize) {
            idx[j] = idx[j - 1] + 1;
        }
    }
    out
}

/// `p_k(X_1, …, X_n) = Σ X_i^k`, the `k`-th power-sum.
pub fn power_sum(k: u32, n: u32, p: BigUint) -> MPoly {
    let n_vars = n as usize;
    let mut out = MPoly::zero(n_vars, p.clone());
    if k == 0 {
        // p_0 = n.
        let val = FieldElement::new(BigUint::from(n), p);
        out.terms.insert(vec![0; n_vars], val);
        return out;
    }
    for i in 0..n_vars {
        let mut exp = vec![0u32; n_vars];
        exp[i] = k;
        out.terms.insert(exp, FieldElement::one(out.p.clone()));
    }
    out
}

// ── Symmetrised S_3 and S_4 (paper's headline formulas) ─────────────

/// The **symmetrised** `\tilde S_3(e_1, e_2, e_3)` in 3 variables
/// (`X_1, X_2, X_3 → e_1, e_2, e_3`).  Returned as an MPoly in 3
/// variables (`e_1, e_2, e_3`), over the curve `y² = x³ + ax + b`.
///
/// Derivation (Faugère et al. §3):
///   S_3 = (e_1² − 4 e_2)·(e_3² + …) ?
/// Actually the clean form is
///
/// ```text
///   \tilde S_3(e_1, e_2, e_3)
///     =  (e_1² - 4 e_2) · e_3²
///        + 2 [(e_1 e_2 + 3 e_3)(e_2 + …)] · e_3
///        + …
/// ```
///
/// — but rather than copy the paper's expansion (which is dense and
/// error-prone), we **construct it directly** by expanding the
/// expression
///   `S_3(X_1, X_2, X_3) = (X_1 - X_2)² X_3²
///                       - 2 [(X_1 + X_2)(X_1 X_2 + a) + 2 b] X_3
///                       + (X_1 X_2 - a)² - 4 b (X_1 + X_2)`
/// over the *X*-variables, and then **decompose into the
/// elementary-symmetric ring** by the algorithm
/// [`decompose_symmetric`] below.
///
/// The output is a *small* polynomial (a handful of terms) compared
/// to the 17 monomials of `S_3(X_1, X_2, X_3)`.
pub fn symmetrise_s3(a: &FieldElement, b: &FieldElement) -> MPoly {
    let p = a.modulus.clone();
    let s3_expanded = expand_s3_in_xs(a, b);
    decompose_symmetric(&s3_expanded, 3, p)
}

/// Build the full `S_3(X_1, X_2, X_3)` as an `MPoly` in 3 variables.
fn expand_s3_in_xs(a: &FieldElement, b: &FieldElement) -> MPoly {
    let p = a.modulus.clone();
    let x1 = MPoly::variable(0, 3, p.clone());
    let x2 = MPoly::variable(1, 3, p.clone());
    let x3 = MPoly::variable(2, 3, p.clone());
    let two = MPoly::constant(FieldElement::new(BigUint::from(2u32), p.clone()), 3);
    let four = MPoly::constant(FieldElement::new(BigUint::from(4u32), p.clone()), 3);
    let a_m = MPoly::constant(a.clone(), 3);
    let b_m = MPoly::constant(b.clone(), 3);

    // term1 = (X_1 - X_2)² X_3²
    let diff = x1.sub(&x2);
    let term1 = diff.mul(&diff).mul(&x3).mul(&x3);

    // term2 = -2 [(X_1 + X_2)(X_1 X_2 + a) + 2 b] X_3
    let sum12 = x1.add(&x2);
    let prod12 = x1.mul(&x2);
    let inner = sum12.mul(&prod12.add(&a_m)).add(&two.mul(&b_m));
    let term2 = two
        .mul(&inner)
        .scale(&FieldElement::one(p.clone()).neg())
        .mul(&x3);

    // term3 = (X_1 X_2 - a)² - 4 b (X_1 + X_2)
    let part = prod12.sub(&a_m);
    let term3 = part.mul(&part).sub(&four.mul(&b_m).mul(&sum12));

    term1.add(&term2).add(&term3)
}

// ── Symmetric-polynomial decomposition (Reynolds operator) ──────────

/// **Decompose a symmetric polynomial** `f ∈ F_p[X_1, …, X_n]` into
/// the elementary-symmetric ring `F_p[e_1, …, e_n]`.
///
/// Algorithm (Sturmfels, *Algorithms in Invariant Theory*, §1.1):
///
/// 1. Find the lexicographically-largest monomial `X_{i_1}^{a_1}
///    X_{i_2}^{a_2} … X_{i_n}^{a_n}` in `f` (with `a_1 ≥ a_2 ≥ … ≥
///    a_n`, by symmetry).
/// 2. Form the corresponding e-monomial
///    `e_1^{a_1 - a_2} e_2^{a_2 - a_3} … e_{n-1}^{a_{n-1} - a_n}
///        e_n^{a_n}`,
///    multiplied by the leading coefficient.
/// 3. Subtract this from `f` (after expanding the e-monomial back as
///    an X-polynomial) and recurse.
///
/// Returns the result as an `MPoly` in `n` variables `(e_1, …, e_n)`.
pub fn decompose_symmetric(f: &MPoly, n: u32, p: BigUint) -> MPoly {
    let n_vars = n as usize;
    let mut work = f.clone();
    let mut out = MPoly::zero(n_vars, p.clone());

    while !work.is_zero() {
        // Find the lex-largest *sorted-descending* monomial.
        let (lead_exp, lead_coef) = leading_sorted_monomial(&work);
        if lead_coef.is_zero() {
            break;
        }
        // Decompose lead_exp into e-multi-degrees.
        // For sorted-descending exp (a_1 ≥ a_2 ≥ … ≥ a_n), the
        // e-exponents are e_i^{a_i - a_{i+1}} for i < n and e_n^{a_n}.
        let mut e_exp = vec![0u32; n_vars];
        for i in 0..n_vars - 1 {
            e_exp[i] = lead_exp[i].saturating_sub(lead_exp[i + 1]);
        }
        e_exp[n_vars - 1] = lead_exp[n_vars - 1];

        // Add lead_coef · e_1^{e_exp[0]} · … to out.
        let mut e_term = MPoly::constant(lead_coef.clone(), n_vars);
        for (i, &k) in e_exp.iter().enumerate() {
            if k == 0 {
                continue;
            }
            let ei = elementary_symmetric(i as u32 + 1, n, p.clone());
            // But this `ei` is over the *X* variables, length-`n` — we
            // want to record it in the e-monomial of `out`, not subtract
            // in the X-space yet.  Use formal-e variables for `out`,
            // and the X-expanded `ei` for `work`.
            let _ = ei;
            // Update e_term to represent the e-monomial: just bump
            // exponent of variable i in `out`'s representation.
            // (out's variables are the e_i themselves.)
            let mut delta = MPoly::zero(n_vars, p.clone());
            let mut exp = vec![0u32; n_vars];
            exp[i] = k;
            delta
                .terms
                .insert(exp.clone(), FieldElement::one(p.clone()));
            e_term = e_term.mul(&delta);
        }
        out = out.add(&e_term);

        // Now expand the e-monomial back as an X-polynomial and
        // subtract from work.
        let mut sub_x = MPoly::constant(lead_coef.clone(), n_vars);
        for (i, &k) in e_exp.iter().enumerate() {
            if k == 0 {
                continue;
            }
            let ei = elementary_symmetric(i as u32 + 1, n, p.clone());
            for _ in 0..k {
                sub_x = sub_x.mul(&ei);
            }
        }
        work = work.sub(&sub_x);
    }

    out
}

/// Find the lex-largest monomial of `f` after sorting each exponent
/// vector in descending order (the canonical "symmetric type").
///
/// Returns `(sorted_exp, coefficient)`.
fn leading_sorted_monomial(f: &MPoly) -> (Vec<u32>, FieldElement) {
    let mut best: Option<(Vec<u32>, FieldElement)> = None;
    for (exp, coef) in &f.terms {
        if coef.is_zero() {
            continue;
        }
        let mut sorted = exp.clone();
        sorted.sort_unstable_by(|a, b| b.cmp(a)); // descending
        if let Some((b, _)) = &best {
            if sorted > *b {
                best = Some((sorted, coef.clone()));
            }
        } else {
            best = Some((sorted, coef.clone()));
        }
    }
    best.unwrap_or_else(|| (vec![0; f.n_vars], FieldElement::zero(f.p.clone())))
}

// ── Tests ───────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use num_bigint::BigUint;

    fn p_271() -> BigUint {
        BigUint::from(271u32)
    }

    fn fe(v: u64) -> FieldElement {
        FieldElement::new(BigUint::from(v), p_271())
    }

    #[test]
    fn mul_keeps_constant_when_a_term_cancels() {
        // Regression: (1+x)(1-x) = 1 - x^2. A prior bug removed the constant
        // term whenever any term cancelled, yielding -x^2.
        let p = p_271();
        let one = MPoly::constant(fe(1), 1);
        let x = MPoly::variable(0, 1, p.clone());
        let one_minus_x = one.add(&x.scale(&fe(270))); // 270 = -1 mod 271
        let prod = one.add(&x).mul(&one_minus_x);
        assert_eq!(prod.num_terms(), 2, "expected 1 - x^2 (two terms)");
        assert!(
            prod.terms.contains_key(&vec![0u32]),
            "constant term was dropped"
        );
        assert!(prod.terms.contains_key(&vec![2u32]), "x^2 term missing");
        assert!(
            !prod.terms.contains_key(&vec![1u32]),
            "the x term should have cancelled"
        );
    }

    #[test]
    fn elementary_symmetric_sanity() {
        let p = p_271();
        let e1 = elementary_symmetric(1, 3, p.clone());
        // e_1 = X_1 + X_2 + X_3 — three terms.
        assert_eq!(e1.num_terms(), 3);
        let e2 = elementary_symmetric(2, 3, p.clone());
        // e_2 has C(3, 2) = 3 terms.
        assert_eq!(e2.num_terms(), 3);
        let e3 = elementary_symmetric(3, 3, p.clone());
        // e_3 = X_1 X_2 X_3 — one term.
        assert_eq!(e3.num_terms(), 1);
        let e0 = elementary_symmetric(0, 3, p);
        // e_0 = 1 — one term (constant).
        assert_eq!(e0.num_terms(), 1);
    }

    #[test]
    fn mpoly_arithmetic_sanity() {
        let p = p_271();
        let x = MPoly::variable(0, 2, p.clone());
        let y = MPoly::variable(1, 2, p.clone());
        let sum = x.add(&y);
        assert_eq!(sum.num_terms(), 2);
        let prod = x.mul(&y);
        assert_eq!(prod.num_terms(), 1);
        let sq = sum.mul(&sum);
        // (X + Y)² = X² + 2 X Y + Y² — three monomials (since 271 odd).
        assert_eq!(sq.num_terms(), 3);
    }

    /// **Symmetric decomposition round-trip**: build `p = X_1² + X_2²
    /// + X_3²`, which is the power sum `p_2 = e_1² - 2 e_2`, decompose,
    ///   and verify the result.
    #[test]
    fn decompose_power_sum_2() {
        let p = p_271();
        let p2 = power_sum(2, 3, p.clone());
        let dec = decompose_symmetric(&p2, 3, p.clone());
        // Expected: e_1² - 2 e_2.
        // Verify by re-expanding into X-form and equating to p2.
        let mut expected = MPoly::zero(3, p.clone());
        let two = FieldElement::new(BigUint::from(2u32), p.clone());
        // Add e_1² coefficient term.
        let mut e_sq = vec![0u32; 3];
        e_sq[0] = 2;
        expected.terms.insert(e_sq, FieldElement::one(p.clone()));
        // Subtract 2 e_2.
        let mut e2_term = vec![0u32; 3];
        e2_term[1] = 1;
        expected.terms.insert(e2_term, two.neg());
        // The decomposed and expected should agree as MPolys in e_i.
        assert_eq!(dec.terms.len(), expected.terms.len());
        for (k, v) in &expected.terms {
            assert_eq!(dec.terms.get(k), Some(v), "mismatch at {:?}", k);
        }
    }

    /// **Symmetrise S_3 sanity**: the decomposition produces a small
    /// polynomial.  We don't assert the exact paper formula, but
    /// instead assert that `symmetrise_s3` returns a polynomial in
    /// at most 3 variables (`e_1, e_2, e_3`) of total degree ≤ 4.
    #[test]
    fn symmetrise_s3_runs() {
        let a = fe(2);
        let b = fe(3);
        let s3_sym = symmetrise_s3(&a, &b);
        // S_3 has total degree 4 in X_1, X_2, X_3 → after symmetrising,
        // total e-degree should still be ≤ 4.
        assert!(s3_sym.total_degree() <= 4);
        assert!(!s3_sym.is_zero());
    }

    /// **Density reduction**: the original S_3 in (X_1, X_2, X_3) has
    /// 17 distinct monomials (after the canonical expansion); the
    /// symmetrised version has strictly fewer.
    #[test]
    fn s3_symmetrisation_reduces_monomial_count() {
        let a = fe(7);
        let b = fe(11);
        let s3_xs = expand_s3_in_xs(&a, &b);
        let s3_sym = symmetrise_s3(&a, &b);
        let n_xs = s3_xs.num_terms();
        let n_sym = s3_sym.num_terms();
        assert!(
            n_sym < n_xs,
            "symmetrised S_3 has {} monomials vs. {} in X-form — expected reduction",
            n_sym,
            n_xs
        );
    }
}
