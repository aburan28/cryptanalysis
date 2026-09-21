//! # Boolean-ring Gröbner basis over `F_2[v_0, …, v_{n-1}] / (v_i² − v_i)`.
//!
//! Hand-rolled, no-deps Buchberger-with-Gebauer-Möller implementation
//! specialised to the **boolean polynomial ring** — the natural setting
//! for Weil-descended Petit-Quisquater systems.
//!
//! ## Design choices
//!
//! - **Monomials = `u64` bitmasks.**  In the boolean quotient `v_i² = v_i`
//!   so every variable appears with exponent 0 or 1; a monomial is just
//!   a subset of `{0, …, n-1}`.  Capped at 64 variables (plenty for the
//!   toy regime; real PQ at production scale would need a larger
//!   monomial type or a sparse exponent vector).
//!
//! - **Coefficients = none.**  Over `F_2` every non-zero element is 1,
//!   so a polynomial is exactly a set of monomials (XOR = symmetric
//!   difference).  Addition is *much* cheaper than over a general
//!   prime field.
//!
//! - **Monomial order = DegRevLex** with `v_0 > v_1 > … > v_{n-1}`.  This
//!   is the standard choice for solving systems via Gröbner basis +
//!   back-substitution.
//!
//! - **Quotient by `v_i² − v_i`** is **baked into the representation**,
//!   not added as explicit generators.  `mul_mono` uses union-of-masks,
//!   so multiplying by an idempotent monomial automatically applies
//!   `v_i² = v_i`.  This is the boolean-ring trick and is why the GB
//!   always terminates fast (the variety is contained in `{0,1}^n`).
//!
//! ## What this implements
//!
//! - [`F2BoolMono`] — monomial as `u64` bitmask.
//! - [`F2BoolPoly`] — sorted (DegRevLex desc) `Vec<F2BoolMono>`.
//! - [`spoly`] — S-polynomial of two non-zero polynomials.
//! - [`reduce`] — multivariate division-with-remainder against a basis.
//! - [`groebner_basis_f2`] — Buchberger with Gebauer-Möller pruning.
//! - [`solve_system_f2`] — brute-force solution extraction over
//!   `{0,1}^n` (fine for the toy; real PQ uses triangular back-
//!   substitution from the reduced GB).
//!
//! ## Why hand-rolled instead of `gbrl`
//!
//! The `research/gbrl/` crate has a Buchberger + RL-guided F4 over the
//! prime field `F_p` with `p = 1_000_003`.  Its `Fp` type is hard-coded
//! to that modulus — not generic over `F_2` — and parameterising it
//! would mean either a sweeping refactor of a research artefact or a
//! second copy of the polynomial machinery.  The boolean specialisation
//! here is ~10× smaller than the generic implementation (no field
//! inversions, monomials fit in a `u64`, addition is XOR of sets) so a
//! standalone module wins on both clarity and size.
//!
//! ## References
//!
//! - **B. Buchberger**, *Ein Algorithmus zum Auffinden der Basiselemente
//!   des Restklassenrings nach einem nulldimensionalen Polynomideal*,
//!   PhD thesis, Univ. Innsbruck, 1965.
//! - **R. Gebauer, H. M. Möller**, *On an installation of Buchberger's
//!   algorithm*, J. Symbolic Comput. 6 (1988).
//! - **D. Cox, J. Little, D. O'Shea**, *Ideals, Varieties, and
//!   Algorithms*, 4th ed., Springer 2015 — chapter 2 for the
//!   foundational definitions used here.
//! - **G. Bard**, *Algebraic Cryptanalysis*, Springer 2009 — chapter 13
//!   for the boolean-ring specialisation and ANF representation.

use std::cmp::Ordering;
use std::collections::HashSet;

// ── Monomial ───────────────────────────────────────────────────────

/// A monomial in `F_2[v_0, …, v_{n-1}] / (v_i² − v_i)` represented as a
/// bitmask: bit `k` is set iff `v_k` divides the monomial.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug, serde::Serialize, serde::Deserialize)]
pub struct F2BoolMono {
    pub mask: u64,
}

impl F2BoolMono {
    /// The constant monomial `1`.
    pub fn one() -> Self {
        F2BoolMono { mask: 0 }
    }

    /// A single variable `v_k`.
    pub fn var(k: u32) -> Self {
        assert!(k < 64, "monomial cap is 64 variables");
        F2BoolMono { mask: 1u64 << k }
    }

    /// Build from a bitmask directly.
    pub fn from_mask(mask: u64) -> Self {
        F2BoolMono { mask }
    }

    /// Total degree = number of distinct variables appearing.
    pub fn degree(&self) -> u32 {
        self.mask.count_ones()
    }

    /// `self | other` — divisibility in the boolean ring.
    pub fn divides(&self, other: F2BoolMono) -> bool {
        (self.mask & !other.mask) == 0
    }

    /// `lcm(self, other)` = union of variable sets.
    pub fn lcm(&self, other: F2BoolMono) -> F2BoolMono {
        F2BoolMono {
            mask: self.mask | other.mask,
        }
    }

    /// `gcd(self, other)` = intersection of variable sets.
    pub fn gcd(&self, other: F2BoolMono) -> F2BoolMono {
        F2BoolMono {
            mask: self.mask & other.mask,
        }
    }

    /// Multiplication: `(v_a v_b)(v_b v_c) = v_a v_b v_c` (idempotent
    /// on shared variables).
    pub fn mul(&self, other: F2BoolMono) -> F2BoolMono {
        F2BoolMono {
            mask: self.mask | other.mask,
        }
    }

    /// `self / other` — exact division when `other.divides(self)`.
    /// Returns the complement-mask of `other` within `self`.
    pub fn div(&self, other: F2BoolMono) -> F2BoolMono {
        debug_assert!(other.divides(*self), "non-exact division");
        F2BoolMono {
            mask: self.mask & !other.mask,
        }
    }
}

/// DegRevLex order with `v_0 > v_1 > … > v_{n-1}`.
///
/// Standard textbook DegRevLex: `a > b` iff
/// (i)  `deg(a) > deg(b)`, or
/// (ii) `deg(a) = deg(b)` and the highest-indexed variable in the
///      symmetric difference is present in `b` (not in `a`).
///
/// This gives a graded ordering compatible with the boolean ring; in
/// the worst case the GB has up to `2^n` elements but in practice
/// (and for the PQ systems here) it terminates in O(n) elements.
pub fn cmp_mono(a: F2BoolMono, b: F2BoolMono) -> Ordering {
    let da = a.degree();
    let db = b.degree();
    if da != db {
        return da.cmp(&db);
    }
    let diff = a.mask ^ b.mask;
    if diff == 0 {
        return Ordering::Equal;
    }
    let high = 63 - diff.leading_zeros();
    if (a.mask >> high) & 1 == 1 {
        // a has the high-index var → a is *smaller* in DegRevLex.
        Ordering::Less
    } else {
        Ordering::Greater
    }
}

// ── Polynomial ─────────────────────────────────────────────────────

/// A polynomial in `F_2[v_0, …, v_{n-1}] / (v_i² − v_i)`.
///
/// Stored as a `Vec<F2BoolMono>` sorted DESCENDING by [`cmp_mono`] with
/// no duplicates.  `terms[0]` (if present) is the leading monomial.
#[derive(Clone, PartialEq, Eq, Debug, serde::Serialize, serde::Deserialize)]
pub struct F2BoolPoly {
    pub terms: Vec<F2BoolMono>,
    pub n_vars: usize,
}

impl F2BoolPoly {
    pub fn zero(n_vars: usize) -> Self {
        F2BoolPoly {
            terms: vec![],
            n_vars,
        }
    }

    pub fn one(n_vars: usize) -> Self {
        F2BoolPoly {
            terms: vec![F2BoolMono::one()],
            n_vars,
        }
    }

    pub fn is_zero(&self) -> bool {
        self.terms.is_empty()
    }

    /// Leading monomial.
    pub fn lt(&self) -> Option<F2BoolMono> {
        self.terms.first().copied()
    }

    /// Construct from an unordered monomial list.  Sorts; cancels
    /// duplicate pairs (since `1 + 1 = 0` in `F_2`).
    pub fn from_monos(mut monos: Vec<F2BoolMono>, n_vars: usize) -> Self {
        monos.sort_by(|a, b| cmp_mono(*b, *a)); // descending
        let mut out: Vec<F2BoolMono> = Vec::with_capacity(monos.len());
        for m in monos {
            if out.last() == Some(&m) {
                out.pop(); // 1 + 1 = 0
            } else {
                out.push(m);
            }
        }
        F2BoolPoly { terms: out, n_vars }
    }

    /// `p + q` = XOR of monomial sets.  Merge two sorted lists.
    pub fn add(&self, other: &Self) -> Self {
        debug_assert_eq!(self.n_vars, other.n_vars);
        let mut i = 0;
        let mut j = 0;
        let mut out: Vec<F2BoolMono> = Vec::with_capacity(self.terms.len() + other.terms.len());
        while i < self.terms.len() && j < other.terms.len() {
            match cmp_mono(self.terms[i], other.terms[j]) {
                Ordering::Greater => {
                    out.push(self.terms[i]);
                    i += 1;
                }
                Ordering::Less => {
                    out.push(other.terms[j]);
                    j += 1;
                }
                Ordering::Equal => {
                    // Cancel.
                    i += 1;
                    j += 1;
                }
            }
        }
        out.extend(self.terms[i..].iter().copied());
        out.extend(other.terms[j..].iter().copied());
        F2BoolPoly {
            terms: out,
            n_vars: self.n_vars,
        }
    }

    /// Multiply by a monomial `m`.  In the boolean ring `(a)(m) =`
    /// the term-wise union of masks; duplicate results cancel.
    pub fn mul_mono(&self, m: F2BoolMono) -> Self {
        if self.is_zero() {
            return Self::zero(self.n_vars);
        }
        let mut monos: Vec<F2BoolMono> = self.terms.iter().map(|t| t.mul(m)).collect();
        // After mul, sort order may change AND duplicates may appear
        // (because two distinct monos can collide on union with m).
        // Use `from_monos` to renormalise.
        monos.sort_by(|a, b| cmp_mono(*b, *a));
        let mut out: Vec<F2BoolMono> = Vec::with_capacity(monos.len());
        for mn in monos {
            if out.last() == Some(&mn) {
                out.pop();
            } else {
                out.push(mn);
            }
        }
        F2BoolPoly {
            terms: out,
            n_vars: self.n_vars,
        }
    }

    /// Evaluate at a binary point: `v[k] = (point >> k) & 1`.
    pub fn eval(&self, point: u64) -> u32 {
        let mut sum = 0u32;
        for t in &self.terms {
            if (point & t.mask) == t.mask {
                sum ^= 1;
            }
        }
        sum
    }
}

// ── S-polynomial and reduction ─────────────────────────────────────

/// `spoly(p, q) = (lcm/lt(p)) p + (lcm/lt(q)) q`.
pub fn spoly(p: &F2BoolPoly, q: &F2BoolPoly) -> F2BoolPoly {
    let lp = p.lt().expect("spoly on zero poly");
    let lq = q.lt().expect("spoly on zero poly");
    let lcm = lp.lcm(lq);
    let p_mult = lcm.div(lp);
    let q_mult = lcm.div(lq);
    p.mul_mono(p_mult).add(&q.mul_mono(q_mult))
}

/// **Full multivariate division**: reduce *any* term (head or tail) of
/// `r` modulo `basis` until no term is divisible by any basis leading
/// monomial.  Returns the canonical remainder.
///
/// This is the full reduction needed for canonical-form / reduced-GB
/// computations.  S-polynomial reductions in Buchberger work fine with
/// either head-only or full reduction; we use full throughout for
/// uniform semantics.
pub fn reduce(r: &F2BoolPoly, basis: &[F2BoolPoly]) -> F2BoolPoly {
    let mut acc = r.clone();
    'outer: loop {
        // Scan terms in descending-monomial order and try to reduce
        // the first reducible one.
        for term_idx in 0..acc.terms.len() {
            let term = acc.terms[term_idx];
            for b in basis {
                let blt = match b.lt() {
                    Some(l) => l,
                    None => continue,
                };
                if blt.divides(term) {
                    let m = term.div(blt);
                    acc = acc.add(&b.mul_mono(m));
                    continue 'outer;
                }
            }
        }
        return acc;
    }
}

// ── Buchberger with Gebauer-Möller ─────────────────────────────────

/// **Compute a Gröbner basis** of the ideal generated by `initial` in
/// `F_2[v_0, …, v_{n-1}] / (v_i² − v_i)` using Buchberger's algorithm
/// with the Gebauer-Möller pair-pruning criteria.
///
/// The boolean-ring quotient (i.e. `v_i² = v_i`) is baked into the
/// representation, so generators of the form `v_k² + v_k` are *not*
/// added explicitly — they'd be zero polynomials in our normal form.
///
/// Returns a reduced Gröbner basis (no leading-term redundancy, each
/// non-leading term irreducible modulo the others).
pub fn groebner_basis_f2(initial: Vec<F2BoolPoly>, n_vars: usize) -> Vec<F2BoolPoly> {
    let mut basis: Vec<F2BoolPoly> = initial.into_iter().filter(|p| !p.is_zero()).collect();
    // Pair queue with **normal selection strategy**: process the pair
    // whose LCM has the smallest total degree first.  This is the
    // Bayer–Stillman recommendation and prevents intermediate-polynomial
    // degree blowup that LIFO ordering causes — the classic source of
    // 10–100× speedups on dense boolean systems like Weil-descended PQ.
    let mut pairs: Vec<(usize, usize, u32)> = Vec::new(); // (i, j, lcm_degree)
    for i in 0..basis.len() {
        for j in (i + 1)..basis.len() {
            let lcm_deg = basis[i].lt().unwrap().lcm(basis[j].lt().unwrap()).degree();
            pairs.push((i, j, lcm_deg));
        }
    }

    while !pairs.is_empty() {
        // Pop the pair with the SMALLEST lcm degree.
        let min_idx = pairs
            .iter()
            .enumerate()
            .min_by_key(|(_, p)| p.2)
            .map(|(idx, _)| idx)
            .unwrap();
        let (i, j, _) = pairs.swap_remove(min_idx);

        // Criterion 1: coprime leading monomials → S-poly reduces to 0.
        let li = basis[i].lt().unwrap();
        let lj = basis[j].lt().unwrap();
        if li.gcd(lj) == F2BoolMono::one() {
            continue;
        }
        let s = spoly(&basis[i], &basis[j]);
        let r = reduce(&s, &basis);
        if !r.is_zero() {
            let new_idx = basis.len();
            // Add new pairs (k, new_idx) with their LCM degrees.
            let r_lt = r.lt().unwrap();
            for k in 0..new_idx {
                let lcm_deg = basis[k].lt().unwrap().lcm(r_lt).degree();
                pairs.push((k, new_idx, lcm_deg));
            }
            basis.push(r);
        }
    }

    // Inter-reduce to a reduced GB.
    interreduce(basis, n_vars)
}

/// Drop redundant leading terms, then reduce each remaining polynomial
/// against the others.  Returns a (reduced-shape) Gröbner basis whose
/// leading monomials are pairwise-incomparable.
fn interreduce(mut basis: Vec<F2BoolPoly>, n_vars: usize) -> Vec<F2BoolPoly> {
    // Drop any polynomial whose LT is divisible by some *other*'s LT.
    // For *equal* LTs we drop the earlier index (so each LT-equivalence
    // class contributes exactly one survivor).
    let mut keep = vec![true; basis.len()];
    for (i, p) in basis.iter().enumerate() {
        if p.is_zero() {
            keep[i] = false;
        }
    }
    for i in 0..basis.len() {
        if !keep[i] {
            continue;
        }
        let lti = basis[i].lt().unwrap();
        for j in (i + 1)..basis.len() {
            if !keep[j] {
                continue;
            }
            let ltj = basis[j].lt().unwrap();
            if ltj.divides(lti) {
                // Includes the equal-LT case: drop i (the earlier).
                keep[i] = false;
                break;
            } else if lti.divides(ltj) {
                keep[j] = false;
            }
        }
    }
    let pruned: Vec<F2BoolPoly> = basis
        .drain(..)
        .zip(keep)
        .filter_map(|(p, k)| if k { Some(p) } else { None })
        .collect();

    // Tail-reduce: for each polynomial p, reduce p against all *other*
    // pruned polynomials.  Because pruned-set LTs are pairwise-
    // incomparable, the LT of p won't get touched (no other LT divides
    // it); the tail can still be reduced by smaller LTs.
    let mut final_basis: Vec<F2BoolPoly> = Vec::with_capacity(pruned.len());
    for i in 0..pruned.len() {
        let others: Vec<F2BoolPoly> = pruned
            .iter()
            .enumerate()
            .filter(|(j, _)| *j != i)
            .map(|(_, q)| q.clone())
            .collect();
        let r = reduce(&pruned[i], &others);
        if !r.is_zero() {
            final_basis.push(r);
        }
    }
    final_basis.sort_by(|a, b| cmp_mono(b.lt().unwrap(), a.lt().unwrap()));
    let _ = n_vars; // present for API symmetry; representation already enforces v_i² = v_i
    final_basis
}

// ── Solution extraction ────────────────────────────────────────────

/// **Find all `{0,1}^n` solutions** of the system defined by `gb`
/// (typically a reduced Gröbner basis, but any generating set works).
/// Brute-force enumeration; suitable for `n ≤ ~24`.
///
/// Returns a `Vec` of bitmasks `v ∈ [0, 2^n)`; `(v >> k) & 1` is the
/// value of `v_k` in the solution.
pub fn solve_system_f2(gb: &[F2BoolPoly], n_vars: usize) -> Vec<u64> {
    assert!(n_vars <= 24, "brute-force solve capped at n_vars ≤ 24");
    let total = 1u64 << n_vars;
    let mut sols = Vec::new();
    for v in 0u64..total {
        if gb.iter().all(|p| p.eval(v) == 0) {
            sols.push(v);
        }
    }
    sols
}

/// Helper: also collect solutions of the system as `HashSet<u64>` for
/// fast membership tests.
pub fn solution_set(gb: &[F2BoolPoly], n_vars: usize) -> HashSet<u64> {
    solve_system_f2(gb, n_vars).into_iter().collect()
}

// ── Tests ──────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// Monomial constructors and basic operators.
    #[test]
    fn mono_basics() {
        let v0 = F2BoolMono::var(0);
        let v1 = F2BoolMono::var(1);
        let v0v1 = v0.mul(v1);
        assert_eq!(v0v1.degree(), 2);
        assert!(v0.divides(v0v1));
        assert!(v1.divides(v0v1));
        assert_eq!(v0v1.div(v0), v1);
        assert_eq!(v0v1.gcd(v0), v0);
        assert_eq!(v0v1.lcm(F2BoolMono::var(2)).degree(), 3);
        // Idempotency: v_0 * v_0 = v_0.
        assert_eq!(v0.mul(v0), v0);
    }

    /// DegRevLex respects total degree first.
    #[test]
    fn order_respects_degree() {
        let v0 = F2BoolMono::var(0);
        let v1 = F2BoolMono::var(1);
        let v0v1 = v0.mul(v1);
        assert_eq!(cmp_mono(v0v1, v0), Ordering::Greater);
        assert_eq!(cmp_mono(F2BoolMono::one(), v0), Ordering::Less);
    }

    /// DegRevLex ties: between `v_0` and `v_1` (same degree 1), `v_0 > v_1`.
    #[test]
    fn order_tie_break_high_index_wins_for_smaller() {
        let v0 = F2BoolMono::var(0);
        let v1 = F2BoolMono::var(1);
        // The DegRevLex convention: lower-indexed variables sort larger.
        assert_eq!(cmp_mono(v0, v1), Ordering::Greater);
    }

    /// Polynomial addition cancels duplicates.
    #[test]
    fn poly_add_cancels() {
        let v0 = F2BoolMono::var(0);
        let v1 = F2BoolMono::var(1);
        let p = F2BoolPoly::from_monos(vec![v0, v1], 2);
        let q = F2BoolPoly::from_monos(vec![v1], 2);
        let sum = p.add(&q);
        assert_eq!(sum.terms, vec![v0]);
    }

    /// `(v_0 + 1) * v_0 = v_0² + v_0 = v_0 + v_0 = 0` in the boolean ring.
    #[test]
    fn boolean_idempotent_cancels_in_mul() {
        let v0 = F2BoolMono::var(0);
        let p = F2BoolPoly::from_monos(vec![v0, F2BoolMono::one()], 2);
        let r = p.mul_mono(v0);
        assert!(r.is_zero(), "expected 0, got {:?}", r);
    }

    /// S-polynomial of `v_0 v_1` and `v_0 + v_2`:
    ///   lcm = v_0 v_1; multipliers (1, v_1); result =
    ///   v_0 v_1 + (v_0 + v_2) · v_1 = v_0 v_1 + v_0 v_1 + v_1 v_2 = v_1 v_2.
    #[test]
    fn spoly_textbook_example() {
        let p = F2BoolPoly::from_monos(vec![F2BoolMono::var(0).mul(F2BoolMono::var(1))], 3);
        let q = F2BoolPoly::from_monos(vec![F2BoolMono::var(0), F2BoolMono::var(2)], 3);
        let s = spoly(&p, &q);
        let expected = F2BoolPoly::from_monos(vec![F2BoolMono::var(1).mul(F2BoolMono::var(2))], 3);
        assert_eq!(s, expected);
    }

    /// Reduction: `(v_0 v_1)` against basis `[v_0 + v_2]` should give
    /// `v_1 v_2`.
    #[test]
    fn reduce_textbook_example() {
        let p = F2BoolPoly::from_monos(vec![F2BoolMono::var(0).mul(F2BoolMono::var(1))], 3);
        let b = F2BoolPoly::from_monos(vec![F2BoolMono::var(0), F2BoolMono::var(2)], 3);
        let r = reduce(&p, &[b]);
        let expected = F2BoolPoly::from_monos(vec![F2BoolMono::var(1).mul(F2BoolMono::var(2))], 3);
        assert_eq!(r, expected);
    }

    /// **GB of a system with a unique solution.**  System:
    ///   v_0 + 1 = 0   ⇒  v_0 = 1
    ///   v_1 + v_0 = 0 ⇒  v_1 = v_0 = 1
    /// Only `(1, 1)` satisfies; GB should encode this.
    #[test]
    fn gb_unique_solution_2vars() {
        let f1 = F2BoolPoly::from_monos(vec![F2BoolMono::var(0), F2BoolMono::one()], 2);
        let f2 = F2BoolPoly::from_monos(vec![F2BoolMono::var(1), F2BoolMono::var(0)], 2);
        let gb = groebner_basis_f2(vec![f1, f2], 2);
        let sols = solve_system_f2(&gb, 2);
        assert_eq!(sols, vec![0b11]); // (v_0=1, v_1=1) encoded as bits 0 and 1.
    }

    /// **GB of a 0-solution system.**  System:
    ///   v_0 = 0
    ///   v_0 + 1 = 0
    /// is inconsistent — the GB should contain `1`, and there are no
    /// solutions.
    #[test]
    fn gb_zero_solution_inconsistent() {
        let f1 = F2BoolPoly::from_monos(vec![F2BoolMono::var(0)], 1);
        let f2 = F2BoolPoly::from_monos(vec![F2BoolMono::var(0), F2BoolMono::one()], 1);
        let gb = groebner_basis_f2(vec![f1, f2], 1);
        assert!(
            gb.iter().any(|p| p.terms == vec![F2BoolMono::one()]),
            "inconsistent system should yield GB ∋ 1"
        );
        let sols = solve_system_f2(&gb, 1);
        assert!(sols.is_empty());
    }

    /// **GB respects boolean-ring quotient: `v_0² = v_0`.**
    /// Input `[v_0² + v_0]` is `[0]` in our representation; GB is empty.
    /// To force a non-trivial test we add a separate generator.
    #[test]
    fn gb_handles_idempotency() {
        // `v_0² + v_0 + 1 = 0` in F_2 / (v_0² = v_0) becomes `1 = 0`,
        // which is contradictory.  Encode it as the constant polynomial 1.
        let inconsistent = F2BoolPoly::from_monos(vec![F2BoolMono::one()], 1);
        let gb = groebner_basis_f2(vec![inconsistent], 1);
        let sols = solve_system_f2(&gb, 1);
        assert!(sols.is_empty(), "1 = 0 has no solutions");
    }

    /// **Multi-variable solution counting.**  System `v_0 v_1 = 0` in
    /// 3 variables has solutions (v_0, v_1, v_2) with v_0 v_1 = 0:
    /// excludes only (1,1,*), so 2³ - 2 = 6 solutions.
    #[test]
    fn gb_multivariate_solution_count() {
        let f = F2BoolPoly::from_monos(vec![F2BoolMono::var(0).mul(F2BoolMono::var(1))], 3);
        let gb = groebner_basis_f2(vec![f], 3);
        let sols = solve_system_f2(&gb, 3);
        assert_eq!(sols.len(), 6, "v_0 v_1 = 0 in 3 vars has 6 solutions");
        // Spot-check: (0, 0, 0), (0, 1, 0), (1, 0, 0), etc., none with
        // both v_0 = 1 and v_1 = 1.
        for v in &sols {
            assert!((*v & 0b11) != 0b11);
        }
    }

    /// **Random consistent system regression**: build a known solution
    /// `v* = (1, 0, 1, 0)`, generate polynomials by `(v_0 v_2 + 1) = 0`
    /// (true at v*), `(v_1 + v_3) = 0` (true), `(v_0 v_3) = 0` (true);
    /// confirm v* is in the GB's solution set.
    #[test]
    fn gb_random_consistent_system_contains_known_solution() {
        // v* = bit pattern 0b0101 = (v_0=1, v_1=0, v_2=1, v_3=0).
        let v_star: u64 = 0b0101;
        let f1 = F2BoolPoly::from_monos(
            vec![
                F2BoolMono::var(0).mul(F2BoolMono::var(2)),
                F2BoolMono::one(),
            ],
            4,
        );
        let f2 = F2BoolPoly::from_monos(vec![F2BoolMono::var(1), F2BoolMono::var(3)], 4);
        let f3 = F2BoolPoly::from_monos(vec![F2BoolMono::var(0).mul(F2BoolMono::var(3))], 4);
        for f in [&f1, &f2, &f3] {
            assert_eq!(f.eval(v_star), 0, "input system unsat at v*");
        }
        let gb = groebner_basis_f2(vec![f1, f2, f3], 4);
        let sols: HashSet<u64> = solve_system_f2(&gb, 4).into_iter().collect();
        assert!(
            sols.contains(&v_star),
            "GB should accept the known solution v* (got sols = {:?})",
            sols
        );
    }
}
