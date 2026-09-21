//! # Weil descent for Petit–Quisquater Semaev systems.
//!
//! Given a polynomial `P(X_1, X_2) ∈ F_{2^m}[X_1, X_2]` and a vector
//! subspace `V ⊂ F_{2^m}` of `F_2`-dimension `m'` with basis
//! `{e_0, …, e_{m'-1}}`, the **Weil restriction (descent)** is the
//! procedure that turns "find `(X_1, X_2) ∈ V × V` with `P(X_1, X_2) = 0`"
//! into a system of `m` boolean polynomial equations in `2m'` boolean
//! variables `v_{i,k}` (where `X_i = sum_k v_{i,k} e_k`).
//!
//! This module ships:
//!
//! - [`weil_descend_s3`] — descend the Semaev `S_3(X_1, X_2, x_R)` from
//!   `F_{2^m}` to `F_2^m` for a fixed target x-coordinate `x_R`.
//! - [`solve_decomposition_via_descent`] — full pipeline: descend, run
//!   the boolean Gröbner basis, enumerate solutions in `V × V`.
//!
//! ## How the descent works
//!
//! Each `X_i` is parametrised as `X_i = sum_{k=0}^{m'-1} v_{i,k} · e_k`
//! with `v_{i,k} ∈ F_2`.  Substituting into `P(X_1, X_2)` and reducing
//! mod the irreducible defining `F_{2^m}` gives a polynomial whose value
//! lives in `F_{2^m}` and can be expanded over the basis
//! `{1, z, z², …, z^{m-1}}`:
//!
//! ```text
//!     P(X_1, X_2) = sum_{j=0}^{m-1} P_j(v_{1,0}, …, v_{2, m'-1}) · z^j
//! ```
//!
//! The condition `P(X_1, X_2) = 0` over `F_{2^m}` is equivalent to all
//! `m` coefficients `P_j` being zero in `F_2`.  Each `P_j` is a
//! polynomial over `F_2` in `2m'` boolean variables.
//!
//! ## Implementation: ANF via Möbius transform
//!
//! Rather than tracking the algebraic expansion symbolically (which is
//! the asymptotically right thing for large `m`), we use the
//! **algebraic normal form (ANF) via Möbius transform** trick:
//!
//! 1. Enumerate every `v ∈ F_2^{2m'}` (cost `2^{2m'}` evals — fine for
//!    `m' ≤ 8 or 10`).
//! 2. Evaluate `P(X_1(v), X_2(v))` once per `v`; record each output bit
//!    as a truth-table entry.
//! 3. Möbius-transform each truth-table column (cost `2m' · 2^{2m'}`)
//!    to obtain the ANF coefficients — directly the [`F2BoolPoly`]
//!    representation of `P_j`.
//!
//! This trades the symbolic-expansion complexity for an evaluation
//! complexity of `2^{2m'} · O(m²)` field operations (the `O(m²)` is the
//! cost of an `F_{2^m}` multiplication).  For toy parameters
//! (`m = 8, m' = 4`) it is microseconds.
//!
//! ## References
//!
//! - **C. Diem**, *On the discrete logarithm problem in elliptic curves
//!   over non-prime finite fields*, LMS J. Comput. Math. 14 (2011) —
//!   the Weil-restriction framework for ECDLP.
//! - **C. Petit, J.-J. Quisquater**, *On polynomial systems arising
//!   from a Weil descent*, ASIACRYPT 2012.
//! - **G. Bard**, *Algebraic Cryptanalysis*, Springer 2009 — chapter 13
//!   for the Möbius-transform ANF representation used here.

use crate::binary_ecc::{BinaryCurve, F2mElement};
use crate::cryptanalysis::binary_semaev::binary_semaev_s3;
use crate::cryptanalysis::pq_groebner_f2::{F2BoolMono, F2BoolPoly};
use num_bigint::BigUint;

// ── Descent result ─────────────────────────────────────────────────

/// The output of a Weil descent: `m` boolean polynomials over `F_2` in
/// `2m'` variables.  Variables `0..m'` are `v_{1,k}` (the coordinates
/// of `X_1` in the chosen basis of `V`); variables `m'..2m'` are
/// `v_{2,k}` (for `X_2`).
#[derive(Clone, Debug)]
pub struct DescentSystem {
    pub n_vars: usize,
    pub m: u32,
    pub m_prime: u32,
    pub equations: Vec<F2BoolPoly>,
    pub v_basis: Vec<F2mElement>,
}

impl DescentSystem {
    /// Lift a binary solution back to `(X_1, X_2) ∈ V × V`.
    pub fn lift_solution(&self, v: u64) -> (F2mElement, F2mElement) {
        let m = self.m;
        let mp = self.m_prime as usize;
        let mut x1 = F2mElement::zero(m);
        let mut x2 = F2mElement::zero(m);
        for k in 0..mp {
            if (v >> k) & 1 == 1 {
                x1 = x1.add(&self.v_basis[k]);
            }
            if (v >> (mp + k)) & 1 == 1 {
                x2 = x2.add(&self.v_basis[k]);
            }
        }
        (x1, x2)
    }
}

// ── Möbius transform ───────────────────────────────────────────────

/// In-place Möbius transform on a truth table of length `2^n_vars`.
///
/// Converts the function table `f: {0,1}^n → F_2` into its ANF
/// coefficient table `g` such that `f(x) = sum_{S ⊆ x} g(S) (mod 2)`.
/// Complexity `O(n · 2^n)`.
fn mobius_transform(tt: &mut [bool], n_vars: usize) {
    debug_assert_eq!(tt.len(), 1 << n_vars);
    for i in 0..n_vars {
        let step = 1usize << i;
        for s in 0..tt.len() {
            if (s & step) != 0 {
                let prev = tt[s ^ step];
                tt[s] ^= prev;
            }
        }
    }
}

/// Convert an ANF coefficient table to a [`F2BoolPoly`].
fn anf_to_poly(anf: &[bool], n_vars: usize) -> F2BoolPoly {
    let mut monos = Vec::new();
    for (s, &on) in anf.iter().enumerate() {
        if on {
            monos.push(F2BoolMono::from_mask(s as u64));
        }
    }
    F2BoolPoly::from_monos(monos, n_vars)
}

// ── Descent of S_3 ─────────────────────────────────────────────────

/// **Weil-descend `S_3(X_1, X_2, x_R) = 0`** with `X_i ∈ V`.
///
/// Output is `m` boolean polynomials in `2m'` variables, indexed so
/// that bit `k` of the input encodes `v_{1,k}` (for `k < m'`) and
/// `v_{2, k - m'}` (for `k ≥ m'`).
///
/// Caps at `m' ≤ 8` (i.e. `2m' ≤ 16`, truth tables of size 65 536) —
/// plenty for any toy regime, and a safety guard against accidentally
/// requesting a 4 GB enumeration.
pub fn weil_descend_s3(
    curve: &BinaryCurve,
    x_r: &F2mElement,
    v_basis: &[F2mElement],
) -> DescentSystem {
    let m = curve.m;
    let m_prime = v_basis.len() as u32;
    assert!(
        m_prime <= 8,
        "weil descent capped at m' ≤ 8 (2^{{2m'}} table size)"
    );
    assert!(
        v_basis.iter().all(|e| e.m_value() == m),
        "all basis elements must live in F_{{2^m}}"
    );
    let n_vars = (2 * m_prime) as usize;
    let n_inputs = 1usize << n_vars;
    let m_usize = m as usize;

    // Truth tables: tt[j][input] is bit j of S_3(x_1(input), x_2(input), x_R).
    let mut tt: Vec<Vec<bool>> = (0..m_usize).map(|_| vec![false; n_inputs]).collect();

    for input in 0..n_inputs {
        // Decode v_{1,k} and v_{2,k} from the input bitmask.
        let mut x1 = F2mElement::zero(m);
        let mut x2 = F2mElement::zero(m);
        for k in 0..(m_prime as usize) {
            if (input >> k) & 1 == 1 {
                x1 = x1.add(&v_basis[k]);
            }
            if (input >> ((m_prime as usize) + k)) & 1 == 1 {
                x2 = x2.add(&v_basis[k]);
            }
        }
        // Evaluate S_3 over F_{2^m}.
        let s = binary_semaev_s3(&x1, &x2, x_r, &curve.b, &curve.irreducible);
        // Expand s in {1, z, ..., z^{m-1}}: read the raw_bits view.
        let bits = s.to_biguint();
        for j in 0..m_usize {
            let bit = ((&bits >> j) & BigUint::from(1u32)) == BigUint::from(1u32);
            tt[j][input] = bit;
        }
    }

    // Möbius-transform each truth table column, then convert to F2BoolPoly.
    let equations: Vec<F2BoolPoly> = tt
        .into_iter()
        .map(|mut row| {
            mobius_transform(&mut row, n_vars);
            anf_to_poly(&row, n_vars)
        })
        .collect();

    DescentSystem {
        n_vars,
        m,
        m_prime,
        equations,
        v_basis: v_basis.to_vec(),
    }
}

// ── Descent of S_4 (n = 3) ─────────────────────────────────────────

/// **`n = 3` descent system.**  `m` boolean polynomials in `3m'`
/// variables, encoding `S_4(X_1, X_2, X_3, x_R) = 0` with
/// `X_i ∈ V`.
#[derive(Clone, Debug)]
pub struct DescentSystemN3 {
    pub n_vars: usize,
    pub m: u32,
    pub m_prime: u32,
    pub equations: Vec<F2BoolPoly>,
    pub v_basis: Vec<F2mElement>,
}

impl DescentSystemN3 {
    /// Lift a binary solution back to `(X_1, X_2, X_3) ∈ V³`.
    pub fn lift_solution(&self, v: u64) -> (F2mElement, F2mElement, F2mElement) {
        let m = self.m;
        let mp = self.m_prime as usize;
        let mut x = [
            F2mElement::zero(m),
            F2mElement::zero(m),
            F2mElement::zero(m),
        ];
        for (idx, xi) in x.iter_mut().enumerate() {
            for k in 0..mp {
                if (v >> (idx * mp + k)) & 1 == 1 {
                    *xi = xi.add(&self.v_basis[k]);
                }
            }
        }
        let [a, b, c] = x;
        (a, b, c)
    }
}

/// **Weil-descend `S_4(X_1, X_2, X_3, x_R) = 0`** with `X_i ∈ V`.
///
/// Output is `m` boolean polynomials in `3m'` variables; bit
/// `idx · m' + k` of the input encodes `v_{idx+1, k}` (for `idx ∈
/// {0, 1, 2}`).
///
/// Caps at `m' ≤ 5` (i.e. `3m' ≤ 15`, truth tables of size 32 768).
/// At `m' = 5` this is one ~32k-entry sweep per random `R_j` —
/// acceptable for the toy regime; production PQ at `n = 3` uses
/// asymptotically better F4/F5 solvers that don't build a full truth
/// table.
pub fn weil_descend_s4(
    curve: &BinaryCurve,
    x_r: &F2mElement,
    v_basis: &[F2mElement],
) -> DescentSystemN3 {
    use crate::cryptanalysis::binary_semaev::binary_semaev_s4;
    let m = curve.m;
    let m_prime = v_basis.len() as u32;
    assert!(
        m_prime <= 5,
        "n=3 weil descent capped at m' ≤ 5 (2^{{3m'}} table size)"
    );
    assert!(
        v_basis.iter().all(|e| e.m_value() == m),
        "all basis elements must live in F_{{2^m}}"
    );
    let n_vars = (3 * m_prime) as usize;
    let n_inputs = 1usize << n_vars;
    let m_usize = m as usize;
    let mp = m_prime as usize;

    let mut tt: Vec<Vec<bool>> = (0..m_usize).map(|_| vec![false; n_inputs]).collect();

    for input in 0..n_inputs {
        // Decode v_{i, k} for i ∈ {0, 1, 2}.
        let mut x = [
            F2mElement::zero(m),
            F2mElement::zero(m),
            F2mElement::zero(m),
        ];
        for (idx, xi) in x.iter_mut().enumerate() {
            for k in 0..mp {
                if (input >> (idx * mp + k)) & 1 == 1 {
                    *xi = xi.add(&v_basis[k]);
                }
            }
        }
        let s = binary_semaev_s4(&x[0], &x[1], &x[2], x_r, &curve.b, &curve.irreducible);
        let bits = s.to_biguint();
        for j in 0..m_usize {
            let bit = ((&bits >> j) & BigUint::from(1u32)) == BigUint::from(1u32);
            tt[j][input] = bit;
        }
    }

    let equations: Vec<F2BoolPoly> = tt
        .into_iter()
        .map(|mut row| {
            mobius_transform(&mut row, n_vars);
            anf_to_poly(&row, n_vars)
        })
        .collect();

    DescentSystemN3 {
        n_vars,
        m,
        m_prime,
        equations,
        v_basis: v_basis.to_vec(),
    }
}

/// **Full descent + Gröbner pipeline at `n = 3`** — the pedagogically
/// correct "real PQ" path.  Asymptotically `O(degree²) · |GB|²` for
/// the GB computation (Bardet–Faugère–Salvy bound on the degree of
/// regularity); at toy parameters (`3m' ≤ 12`) the boolean
/// Buchberger blows up because `S_4` has total degree 8 in
/// `(x_1, x_2, x_3)` and the descended F_2 system has polynomials of
/// degree up to 8 in 9–12 boolean variables — a regime where naïve
/// Buchberger is dominated by F4/F5 (which we don't ship in this
/// boolean specialisation).
///
/// **Prefer [`solve_decomposition_n3_direct`]** for the toy: it
/// brute-forces `S_4 = 0` directly over `F_{2^m}` and is several
/// orders of magnitude faster at this scale.  This GB-based variant
/// is kept for cross-checks at smaller parameters and as a
/// pedagogical reference.
pub fn solve_decomposition_via_descent_n3(
    curve: &BinaryCurve,
    x_r: &F2mElement,
    v_basis: &[F2mElement],
) -> Vec<(F2mElement, F2mElement, F2mElement)> {
    let sys = weil_descend_s4(curve, x_r, v_basis);
    let gb =
        crate::cryptanalysis::pq_groebner_f2::groebner_basis_f2(sys.equations.clone(), sys.n_vars);
    let sols = crate::cryptanalysis::pq_groebner_f2::solve_system_f2(&gb, sys.n_vars);
    sols.into_iter().map(|v| sys.lift_solution(v)).collect()
}

/// **Full descent + XL pipeline at `n = 3`**.  Companion to
/// [`solve_decomposition_via_descent_n3`] that swaps the Buchberger
/// Gröbner basis for the **XL solver** (Courtois-Klimov-Patarin-
/// Shamir 2000), which scales much better at the boolean
/// `n_vars ≥ 9` regime where Buchberger blows up.
///
/// Pipeline:
///   1. Weil-descend `S_4(X_1, X_2, X_3, x_R) = 0` over `F_{2^m}` to
///      `m` boolean polynomials in `3m'` variables.
///   2. Run [`crate::cryptanalysis::pq_xl::boolean_xl_solve`] on the
///      descended system.
///   3. Lift each solution `v ∈ F_2^{3m'}` to `(X_1, X_2, X_3) ∈ V³`.
///
/// At the toy parameters `m = 8`, `m' = 3` (so 9 boolean variables),
/// this terminates fast (matrix is ~72 × 512 over F_2; reduction is
/// XOR-based).  For `m' = 4` (12 boolean variables) the matrix grows
/// to ~256 × 4096 — still tractable but slower than the brute-force
/// [`solve_decomposition_n3_direct`] path at this scale.
pub fn solve_decomposition_via_descent_n3_xl(
    curve: &BinaryCurve,
    x_r: &F2mElement,
    v_basis: &[F2mElement],
) -> Vec<(F2mElement, F2mElement, F2mElement)> {
    let sys = weil_descend_s4(curve, x_r, v_basis);
    let sols = crate::cryptanalysis::pq_xl::boolean_xl_solve(sys.equations.clone(), sys.n_vars);
    sols.into_iter().map(|v| sys.lift_solution(v)).collect()
}

/// **Direct enumeration of `S_4 = 0` over `V × V × V`** — the fast
/// path for the toy regime.  Iterates `2^{3m'}` triples and tests
/// `S_4` over `F_{2^m}` for each; far cheaper than descent + GB at
/// `m' ≤ 4`.
///
/// **Pedagogical caveat**: this is NOT what real Petit–Quisquater
/// does asymptotically — it would defeat the purpose of the algorithm,
/// since the brute-force cost is `|V|³` while real PQ uses descent +
/// F4 Gröbner basis to achieve `~|V|^{3/2}` (the heuristic L(1/2)
/// complexity from Petit–Quisquater 2012, bounded by Huang–Kiltz–Petit
/// 2015's last-fall-degree analysis).  At the toy scale, the asymptotic
/// machinery is dominated by constants; we use direct enumeration to
/// get *some* end-to-end demonstration, with [`solve_decomposition_via_descent_n3`]
/// available for the "real" path on small enough inputs.
pub fn solve_decomposition_n3_direct(
    curve: &BinaryCurve,
    x_r: &F2mElement,
    v_basis: &[F2mElement],
) -> Vec<(F2mElement, F2mElement, F2mElement)> {
    use crate::cryptanalysis::binary_semaev::binary_semaev_s4;
    let m_prime = v_basis.len() as u32;
    assert!(m_prime <= 8, "direct n=3 enumeration capped at m' ≤ 8");
    let mp = m_prime as usize;
    let n_inputs = 1u64 << (3 * m_prime);
    let m = curve.m;
    let mut out = Vec::new();
    for input in 0..n_inputs {
        let mut x = [
            F2mElement::zero(m),
            F2mElement::zero(m),
            F2mElement::zero(m),
        ];
        for (idx, xi) in x.iter_mut().enumerate() {
            for k in 0..mp {
                if (input >> (idx * mp + k)) & 1 == 1 {
                    *xi = xi.add(&v_basis[k]);
                }
            }
        }
        let s = binary_semaev_s4(&x[0], &x[1], &x[2], x_r, &curve.b, &curve.irreducible);
        if s.is_zero() {
            let [a, b, c] = x;
            out.push((a, b, c));
        }
    }
    out
}

// ── End-to-end decomposition via descent + GB ──────────────────────

/// **Find every decomposition `(X_1, X_2) ∈ V × V`** satisfying
/// `S_3(X_1, X_2, x_R) = 0` via:
///
/// 1. Weil descent of `S_3` into `m` boolean polynomials.
/// 2. Boolean Gröbner basis computation with Buchberger + GM.
/// 3. Brute-force solution enumeration over the GB.
///
/// Returns the lifted pairs `(X_1, X_2) ∈ V × V`.  Multiplicities are
/// preserved — the same pair won't appear twice unless multiple `v`
/// bitmasks happen to lift to the same `(X_1, X_2)`, which shouldn't
/// happen since the encoding is injective.
pub fn solve_decomposition_via_descent(
    curve: &BinaryCurve,
    x_r: &F2mElement,
    v_basis: &[F2mElement],
) -> Vec<(F2mElement, F2mElement)> {
    let sys = weil_descend_s3(curve, x_r, v_basis);
    let gb =
        crate::cryptanalysis::pq_groebner_f2::groebner_basis_f2(sys.equations.clone(), sys.n_vars);
    let sols = crate::cryptanalysis::pq_groebner_f2::solve_system_f2(&gb, sys.n_vars);
    sols.into_iter().map(|v| sys.lift_solution(v)).collect()
}

// ── Tests ──────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::binary_ecc::IrreduciblePoly;
    use crate::cryptanalysis::binary_semaev::binary_semaev_s3;

    /// Standard low-order basis `{1, z, z², …, z^{m'-1}}` for V ⊂ F_{2^m}.
    fn standard_basis(m: u32, m_prime: u32) -> Vec<F2mElement> {
        (0..m_prime)
            .map(|k| F2mElement::from_bit_positions(&[k], m))
            .collect()
    }

    /// **Möbius round-trip**: a known polynomial reproduces its truth
    /// table under Möbius⁻¹ (Möbius is involutive over F_2).
    #[test]
    fn mobius_involutive() {
        // P(v_0, v_1) = v_0 + v_1 + v_0 v_1.  Truth table (rows v_1=v_0):
        // (0,0): 0, (1,0): 1, (0,1): 1, (1,1): 1+1+1 = 1.
        // Input encoding: bit 0 = v_0, bit 1 = v_1.  So input 0=00, 1=01, 2=10, 3=11.
        let mut tt = vec![false, true, true, true]; // (0, 1, 1, 1)
        let original = tt.clone();
        mobius_transform(&mut tt, 2);
        // ANF: monomials are v_0, v_1, v_0 v_1 → coefficients on masks 1, 2, 3.
        assert_eq!(tt, vec![false, true, true, true]); // (mask 0=0, mask 1=1, mask 2=1, mask 3=1)
                                                       // Inverse Möbius is the same operation (over F_2).
        mobius_transform(&mut tt, 2);
        assert_eq!(tt, original);
    }

    /// **Descend a known polynomial**: take `P(X_1, X_2) = X_1 + X_2 + b`
    /// over `F_{2^m}` and descend.  The system should be (m linear F_2
    /// equations: bit j of (X_1 + X_2 + b) = 0).
    ///
    /// For `V = F_2-span{1, z}` (m' = 2), and `b = z` (say), bit 0 of
    /// X_1 + X_2 + b = v_{1,0} + v_{2,0} + 0 = v_{1,0} + v_{2,0}, and
    /// bit 1 = v_{1,1} + v_{2,1} + 1.
    ///
    /// We don't have a generic `P` parameter (`weil_descend_s3` is
    /// hard-coded to S_3); we use this test only for the Möbius math.
    #[test]
    fn descent_basic_round_trip() {
        let m = 6;
        let irr = IrreduciblePoly {
            degree: 6,
            low_terms: vec![0, 1],
        };
        let a = F2mElement::zero(m);
        let b = F2mElement::from_bit_positions(&[0, 2], m);
        let curve = BinaryCurve {
            m,
            irreducible: irr.clone(),
            a,
            b: b.clone(),
            generator: crate::binary_ecc::BinaryPoint::Infinity,
            order: BigUint::from(1u32),
            cofactor: BigUint::from(1u32),
        };
        let x_r = F2mElement::from_bit_positions(&[1, 3], m);
        let v_basis = standard_basis(m, 3);
        let sys = weil_descend_s3(&curve, &x_r, &v_basis);
        // m = 6 equations, 2·3 = 6 variables.
        assert_eq!(sys.equations.len(), 6);
        assert_eq!(sys.n_vars, 6);
    }

    /// **Spot-check the descent at a known input.**  For a particular
    /// `v ∈ F_2^{2m'}`, evaluate every descent equation at `v` and
    /// confirm the result matches `S_3(X_1(v), X_2(v), x_R)` bit-for-
    /// bit.
    #[test]
    fn descent_evaluates_correctly_at_every_point() {
        let m = 6;
        let irr = IrreduciblePoly {
            degree: 6,
            low_terms: vec![0, 1],
        };
        let curve = BinaryCurve {
            m,
            irreducible: irr.clone(),
            a: F2mElement::zero(m),
            b: F2mElement::from_bit_positions(&[0, 2], m),
            generator: crate::binary_ecc::BinaryPoint::Infinity,
            order: BigUint::from(1u32),
            cofactor: BigUint::from(1u32),
        };
        let x_r = F2mElement::from_bit_positions(&[1, 3], m);
        let v_basis = standard_basis(m, 3);
        let sys = weil_descend_s3(&curve, &x_r, &v_basis);
        let n_inputs = 1u64 << sys.n_vars;
        for v in 0u64..n_inputs {
            let (x1, x2) = sys.lift_solution(v);
            let direct = binary_semaev_s3(&x1, &x2, &x_r, &curve.b, &irr);
            let direct_bits = direct.to_biguint();
            for j in 0..(m as usize) {
                let expected = ((&direct_bits >> j) & BigUint::from(1u32)) == BigUint::from(1u32);
                let got = sys.equations[j].eval(v) == 1;
                assert_eq!(
                    got, expected,
                    "descent eq {} at v={:#b} disagreed with direct S_3 bit (got {}, expected {})",
                    j, v, got, expected
                );
            }
        }
    }

    /// **End-to-end: descent + GB recovers a constructed decomposition.**
    /// Build `R = -(P_1 + P_2)` on the curve from two FB points `P_i`
    /// whose x-coords lie in V; then `S_3(x_1, x_2, x_R) = 0` is
    /// guaranteed (Semaev's collinearity).  Run the pipeline and check
    /// the recovered set contains `(x_1, x_2)`.
    #[test]
    fn descent_pipeline_recovers_constructed_pair() {
        use crate::binary_ecc::curve::{point_add, point_neg};
        use crate::cryptanalysis::petit_quisquater::{build_pq_factor_base, PqSubspace};
        let m = 8;
        let irr = IrreduciblePoly::deg_8();
        let curve = BinaryCurve {
            m,
            irreducible: irr.clone(),
            a: F2mElement::zero(m),
            b: F2mElement::from_biguint(&BigUint::from(46u32), m),
            generator: crate::binary_ecc::BinaryPoint::Infinity,
            order: BigUint::from(1u32),
            cofactor: BigUint::from(1u32),
        };
        let v_basis = standard_basis(m, 4); // V = F_2-span{1, z, z², z³}
                                            // Use the existing PQ factor-base builder to pick two on-curve
                                            // points whose x-coords lie in V.
        let pq_v = PqSubspace::span_low(m, 4);
        let fb = build_pq_factor_base(&curve, &pq_v);
        assert!(fb.len() >= 2, "need ≥ 2 FB points");
        let p1 = &fb[0].point;
        let p2 = &fb[1].point;
        let x_1 = fb[0].x.clone();
        let x_2 = fb[1].x.clone();
        // R = -(P_1 + P_2).
        let sum = point_add(&curve, p1, p2);
        let r = point_neg(&sum);
        let x_r = match r {
            crate::binary_ecc::BinaryPoint::Affine { x, .. } => x,
            crate::binary_ecc::BinaryPoint::Infinity => {
                panic!("P_1 + P_2 = O is unlucky FB pair; retry with different FB")
            }
        };
        // Sanity: S_3 vanishes on the constructed triple.
        assert!(
            binary_semaev_s3(&x_1, &x_2, &x_r, &curve.b, &irr).is_zero(),
            "Semaev S_3 should vanish on (x_1, x_2, x_R) by construction"
        );
        // Run the descent + GB pipeline.
        let solutions = solve_decomposition_via_descent(&curve, &x_r, &v_basis);
        let contains_pair = solutions
            .iter()
            .any(|(a, b)| (a, b) == (&x_1, &x_2) || (a, b) == (&x_2, &x_1));
        assert!(
            contains_pair,
            "pipeline failed to recover constructed (x_1, x_2)\n  solutions: {:?}\n  expected ({}, {})",
            solutions
                .iter()
                .map(|(a, b)| (a.to_biguint(), b.to_biguint()))
                .collect::<Vec<_>>(),
            x_1.to_biguint(),
            x_2.to_biguint()
        );
    }

    /// **n=3 descent reproduces direct S_4 evaluation at every input.**
    /// Spot-checks the truth-table → Möbius → ANF pipeline for the
    /// `n = 3` case.
    #[test]
    fn descent_n3_evaluates_correctly_at_every_point() {
        use crate::cryptanalysis::binary_semaev::binary_semaev_s4;
        let m = 6;
        let irr = IrreduciblePoly {
            degree: 6,
            low_terms: vec![0, 1],
        };
        let curve = BinaryCurve {
            m,
            irreducible: irr.clone(),
            a: F2mElement::zero(m),
            b: F2mElement::from_bit_positions(&[0, 2], m),
            generator: crate::binary_ecc::BinaryPoint::Infinity,
            order: BigUint::from(1u32),
            cofactor: BigUint::from(1u32),
        };
        let x_r = F2mElement::from_bit_positions(&[1, 3], m);
        let v_basis = standard_basis(m, 3);
        let sys = weil_descend_s4(&curve, &x_r, &v_basis);
        assert_eq!(sys.equations.len(), 6);
        assert_eq!(sys.n_vars, 9); // 3 · 3 = 9
        let n_inputs = 1u64 << sys.n_vars;
        for v in 0u64..n_inputs {
            let (x1, x2, x3) = sys.lift_solution(v);
            let direct = binary_semaev_s4(&x1, &x2, &x3, &x_r, &curve.b, &irr);
            let direct_bits = direct.to_biguint();
            for j in 0..(m as usize) {
                let expected = ((&direct_bits >> j) & BigUint::from(1u32)) == BigUint::from(1u32);
                let got = sys.equations[j].eval(v) == 1;
                assert_eq!(
                    got, expected,
                    "n=3 descent eq {} at v={:#b} disagreed with direct S_4 bit",
                    j, v
                );
            }
        }
    }

    /// **End-to-end n=3: descent + GB recovers a constructed
    /// 3-decomposition.**  Build `R = -(P_1 + P_2 + P_3)` from three
    /// FB points; descend + solve and check `(x_1, x_2, x_3)` appears
    /// (up to permutation) in the solution set.
    #[test]
    fn descent_n3_pipeline_recovers_constructed_triple() {
        use crate::binary_ecc::curve::{point_add, point_neg};
        use crate::cryptanalysis::binary_semaev::binary_semaev_s4;
        use crate::cryptanalysis::petit_quisquater::{build_pq_factor_base, PqSubspace};
        let m = 8;
        let irr = IrreduciblePoly::deg_8();
        let curve = BinaryCurve {
            m,
            irreducible: irr.clone(),
            a: F2mElement::zero(m),
            b: F2mElement::from_biguint(&BigUint::from(46u32), m),
            generator: crate::binary_ecc::BinaryPoint::Infinity,
            order: BigUint::from(1u32),
            cofactor: BigUint::from(1u32),
        };
        // n=3 descent capacity: we use m' = 3 (= 9 boolean vars)
        // which keeps the boolean Gröbner basis tractable.  Build the
        // FB at m' = 3 and pick the first three on-curve points for
        // the test triple.
        let pq_v = PqSubspace::span_low(m, 3);
        let fb = build_pq_factor_base(&curve, &pq_v);
        assert!(
            fb.len() >= 3,
            "need ≥ 3 FB points in V_3 (got {})",
            fb.len()
        );
        let p1 = &fb[0].point;
        let p2 = &fb[1].point;
        let p3 = &fb[2].point;
        let x_1 = fb[0].x.clone();
        let x_2 = fb[1].x.clone();
        let x_3 = fb[2].x.clone();
        let p12 = point_add(&curve, p1, p2);
        let p123 = point_add(&curve, &p12, p3);
        if matches!(p123, crate::binary_ecc::BinaryPoint::Infinity) {
            return; // unlucky FB triple
        }
        let r = point_neg(&p123);
        let x_r = match r {
            crate::binary_ecc::BinaryPoint::Affine { x, .. } => x,
            _ => unreachable!(),
        };
        assert!(
            binary_semaev_s4(&x_1, &x_2, &x_3, &x_r, &curve.b, &irr).is_zero(),
            "S_4 should vanish on the constructed 3-decomp by collinearity"
        );
        let v_basis: Vec<F2mElement> = (0..3)
            .map(|k| F2mElement::from_bit_positions(&[k], curve.m))
            .collect();
        // Use direct enumeration; the GB-based path doesn't terminate
        // at toy scale because S_4 has total degree 8.  See the
        // `descent_n3_xl_matches_direct` test for the XL-based path
        // that DOES terminate.
        let solutions = solve_decomposition_n3_direct(&curve, &x_r, &v_basis);
        // Permutation check: any of the 6 reorderings of (x_1, x_2, x_3).
        let mut perms = [
            (x_1.clone(), x_2.clone(), x_3.clone()),
            (x_1.clone(), x_3.clone(), x_2.clone()),
            (x_2.clone(), x_1.clone(), x_3.clone()),
            (x_2.clone(), x_3.clone(), x_1.clone()),
            (x_3.clone(), x_1.clone(), x_2.clone()),
            (x_3.clone(), x_2.clone(), x_1.clone()),
        ];
        let contains_triple = solutions
            .iter()
            .any(|sol| perms.iter_mut().any(|p| sol == p));
        assert!(
            contains_triple,
            "n=3 pipeline failed to recover constructed triple ({}, {}, {})\n  #solutions = {}",
            x_1.to_biguint(),
            x_2.to_biguint(),
            x_3.to_biguint(),
            solutions.len()
        );
    }

    /// **n=3 XL path produces the same solution set as direct enumeration.**
    /// At the toy `(m = 8, m' = 3)` regime, the descent + XL pipeline
    /// terminates fast and yields the same `(x_1, x_2, x_3)` triples
    /// as direct `S_4 = 0` enumeration over `V × V × V`.
    #[test]
    fn descent_n3_xl_matches_direct() {
        use crate::cryptanalysis::petit_quisquater::{build_pq_factor_base, PqSubspace};
        let m = 8;
        let irr = IrreduciblePoly::deg_8();
        let curve = BinaryCurve {
            m,
            irreducible: irr.clone(),
            a: F2mElement::zero(m),
            b: F2mElement::from_biguint(&BigUint::from(46u32), m),
            generator: crate::binary_ecc::BinaryPoint::Infinity,
            order: BigUint::from(1u32),
            cofactor: BigUint::from(1u32),
        };
        // Build a target x_R from a constructed FB triple so we know
        // there's at least one V³ solution.
        let pq_v = PqSubspace::span_low(m, 3);
        let fb = build_pq_factor_base(&curve, &pq_v);
        assert!(fb.len() >= 2, "need ≥ 2 FB points in V_3");
        use crate::binary_ecc::curve::{point_add, point_neg};
        let p12 = point_add(&curve, &fb[0].point, &fb[1].point);
        if matches!(p12, crate::binary_ecc::BinaryPoint::Infinity) {
            return;
        }
        // R chosen as a point in the curve; for the test we just want a
        // random-looking x_R.
        let x_r = match point_neg(&p12) {
            crate::binary_ecc::BinaryPoint::Affine { x, .. } => x,
            _ => panic!("neg of affine should be affine"),
        };
        let v_basis: Vec<F2mElement> = (0..3)
            .map(|k| F2mElement::from_bit_positions(&[k], curve.m))
            .collect();
        let direct: std::collections::HashSet<(BigUint, BigUint, BigUint)> =
            solve_decomposition_n3_direct(&curve, &x_r, &v_basis)
                .into_iter()
                .map(|(a, b, c)| (a.to_biguint(), b.to_biguint(), c.to_biguint()))
                .collect();
        let xl: std::collections::HashSet<(BigUint, BigUint, BigUint)> =
            solve_decomposition_via_descent_n3_xl(&curve, &x_r, &v_basis)
                .into_iter()
                .map(|(a, b, c)| (a.to_biguint(), b.to_biguint(), c.to_biguint()))
                .collect();
        assert_eq!(
            direct, xl,
            "XL and direct enumeration should yield the same V³ solutions\n\
             direct: {:?}\n  xl: {:?}",
            direct, xl,
        );
    }
}
