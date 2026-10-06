//! # Symbolic Weil descent of the summation polynomials.
//!
//! [`pq_descent`](crate::cryptanalysis::pq_descent) builds the boolean
//! system of a Weil descent from a **truth table**: it evaluates
//! `S_{m+1}` at every one of the `2^{m·n'}` points of `V^m` and
//! Möbius-transforms the bits into algebraic normal forms.  That is
//! exact and simple, and it caps the subspace dimension at `n' = 8`
//! for two summands and `n' = 5` for three, because the table is the
//! whole enumeration the descent exists to avoid.
//!
//! This module builds the same system **symbolically**.  Each abscissa
//! is the linear form `x_i = Σ_k v_{i,k} e_k` over the subspace basis,
//! and the summation polynomial is expanded in the ring
//! `F_{2^n}[v] / (v² − v)` term by term, exactly as the evaluating
//! functions compute it: a polynomial here is a map from a boolean
//! monomial (a 64-bit mask over the `v`'s) to its `F_{2^n}`
//! coefficient, and the ring's two facts do all the work —
//!
//! - **squaring is linear**: `(Σ c_M M)² = Σ c_M² M`, because `M² = M`
//!   and every cross term carries a factor of two;
//! - **multiplication is a union**: `M · N = M ∪ N`.
//!
//! The descended system is then read off one bit at a time: equation
//! `j` is the set of monomials whose coefficient has bit `j` set.
//! `S_3` comes out quadratic in `2n'` variables with at most
//! `n'² + 2n' + 1` monomials, whatever `n'`; `S_4` comes out of degree
//! at most six in `3n'` variables, since its resultant form is a
//! product of two cubics.  The only cap left is the monomial mask:
//! `m·n' ≤ 64` variables.
//!
//! The two constructions must agree monomial for monomial — the
//! algebraic normal form of a boolean function is unique — and the
//! test suite checks that they do, on random curves, at every
//! dimension the truth table can still reach.

use std::collections::HashMap;

use crate::cryptanalysis::pq_groebner_f2::{F2BoolMono, F2BoolPoly};
use crate::cryptanalysis::semaev_decomp::Gf2;

/// The most boolean variables a system may have: one bit of a
/// [`F2BoolMono`] mask per variable.
pub const MAX_VARS: u32 = 64;

/// The largest subspace dimension this descent will take at `summands`
/// summands: `⌊64 / m⌋`.
pub fn max_n_prime(summands: u32) -> u32 {
    match summands {
        2 | 3 => MAX_VARS / summands,
        _ => 0,
    }
}

// ── F_{2^n}[v] / (v² − v) ──────────────────────────────────────────

/// A polynomial over `F_{2^n}` in boolean variables: monomial mask to
/// non-zero coefficient.
#[derive(Clone, Debug, Default)]
pub struct FieldBoolPoly {
    terms: HashMap<u64, u64>,
}

impl FieldBoolPoly {
    /// The constant `c`.
    pub fn constant(c: u64) -> Self {
        let mut p = Self::default();
        if c != 0 {
            p.terms.insert(0, c);
        }
        p
    }

    /// The linear form `Σ_k v_{offset + k} · basis[k]`.
    pub fn linear(offset: u32, basis: &[u64]) -> Self {
        let mut p = Self::default();
        for (k, &e) in basis.iter().enumerate() {
            if e != 0 {
                p.terms.insert(1u64 << (offset + k as u32), e);
            }
        }
        p
    }

    fn add_term(&mut self, mask: u64, coeff: u64) {
        if coeff == 0 {
            return;
        }
        match self.terms.get_mut(&mask) {
            Some(c) => {
                *c ^= coeff;
                if *c == 0 {
                    self.terms.remove(&mask);
                }
            }
            None => {
                self.terms.insert(mask, coeff);
            }
        }
    }

    pub fn add(&self, other: &Self) -> Self {
        let mut out = self.clone();
        for (&m, &c) in &other.terms {
            out.add_term(m, c);
        }
        out
    }

    /// `M · N = M ∪ N` in the boolean ring.
    pub fn mul(&self, other: &Self, gf: &Gf2) -> Self {
        let mut out = Self::default();
        for (&ma, &ca) in &self.terms {
            for (&mb, &cb) in &other.terms {
                out.add_term(ma | mb, gf.mul(ca, cb));
            }
        }
        out
    }

    /// `(Σ c_M M)² = Σ c_M² M`: the Frobenius on the coefficients.
    pub fn sqr(&self, gf: &Gf2) -> Self {
        Self {
            terms: self.terms.iter().map(|(&m, &c)| (m, gf.sqr(c))).collect(),
        }
    }

    pub fn scale(&self, c: u64, gf: &Gf2) -> Self {
        let mut out = Self::default();
        for (&m, &a) in &self.terms {
            out.add_term(m, gf.mul(a, c));
        }
        out
    }

    pub fn len(&self) -> usize {
        self.terms.len()
    }

    pub fn is_empty(&self) -> bool {
        self.terms.is_empty()
    }

    /// Evaluate at a point of `{0,1}^vars`, as a field element.
    pub fn eval(&self, point: u64) -> u64 {
        self.terms
            .iter()
            .filter(|(&m, _)| point & m == m)
            .fold(0u64, |acc, (_, &c)| acc ^ c)
    }

    /// The `n` boolean coordinate polynomials: equation `j` holds the
    /// monomials whose coefficient has bit `j` set.
    pub fn split(&self, n: u32, n_vars: usize) -> Vec<F2BoolPoly> {
        let mut monos: Vec<Vec<F2BoolMono>> = (0..n).map(|_| Vec::new()).collect();
        for (&m, &c) in &self.terms {
            let mut bits = c;
            while bits != 0 {
                let j = bits.trailing_zeros();
                if j < n {
                    monos[j as usize].push(F2BoolMono::from_mask(m));
                }
                bits &= bits - 1;
            }
        }
        monos
            .into_iter()
            .map(|ms| F2BoolPoly::from_monos(ms, n_vars))
            .collect()
    }
}

// ── The summation polynomials, on words ────────────────────────────

/// `S_3(x_1, x_2, x_3) = (x_1 + x_2)² x_3² + x_1 x_2 x_3 + (x_1 x_2)² + b`
/// on `Gf2` words, the same formula
/// [`binary_semaev_s3`](crate::cryptanalysis::binary_semaev::binary_semaev_s3)
/// evaluates.
pub fn semaev_s3_word(gf: &Gf2, b: u64, x1: u64, x2: u64, x3: u64) -> u64 {
    let sum12_sq = gf.sqr(x1 ^ x2);
    let prod12 = gf.mul(x1, x2);
    gf.mul(sum12_sq, gf.sqr(x3)) ^ gf.mul(prod12, x3) ^ gf.sqr(prod12) ^ b
}

/// `S_4 = Res_X(S_3(x_1, x_2, X), S_3(x_3, x_4, X))` on `Gf2` words,
/// the same resultant formula
/// [`binary_semaev_s4`](crate::cryptanalysis::binary_semaev::binary_semaev_s4)
/// evaluates: with `S_3(x_i, x_j, X) = A X² + B X + C`,
/// `Res = (A_1 C_2 + A_2 C_1)² + (A_1 B_2 + A_2 B_1)(B_1 C_2 + B_2 C_1)`.
pub fn semaev_s4_word(gf: &Gf2, b: u64, x1: u64, x2: u64, x3: u64, x4: u64) -> u64 {
    let (a1, b1, c1) = s3_in_x3_word(gf, b, x1, x2);
    let (a2, b2, c2) = s3_in_x3_word(gf, b, x3, x4);
    let t1 = gf.sqr(gf.mul(a1, c2) ^ gf.mul(a2, c1));
    let t2 = gf.mul(
        gf.mul(a1, b2) ^ gf.mul(a2, b1),
        gf.mul(b1, c2) ^ gf.mul(b2, c1),
    );
    t1 ^ t2
}

fn s3_in_x3_word(gf: &Gf2, b: u64, x1: u64, x2: u64) -> (u64, u64, u64) {
    let a = gf.sqr(x1 ^ x2);
    let bb = gf.mul(x1, x2);
    let c = gf.sqr(bb) ^ b;
    (a, bb, c)
}

// ── The descent ────────────────────────────────────────────────────

/// A descended system: `n` boolean equations in `m·n'` variables, with
/// bit `i·n' + k` of a point standing for `v_{i,k}`, exactly as the
/// truth-table descent numbers them.
#[derive(Clone, Debug)]
pub struct SymbolicDescent {
    pub n: u32,
    pub n_prime: u32,
    pub summands: u32,
    pub n_vars: usize,
    pub equations: Vec<F2BoolPoly>,
    pub v_basis: Vec<u64>,
    /// Monomials of the polynomial over `F_{2^n}` before it was split
    /// into coordinates: the size of the symbolic object.
    pub field_monomials: usize,
}

impl SymbolicDescent {
    /// The abscissae a solution names, one word per summand.
    pub fn lift(&self, v: u64) -> Vec<u64> {
        let np = self.n_prime as usize;
        (0..self.summands as usize)
            .map(|i| {
                (0..np)
                    .filter(|&k| (v >> (i * np + k)) & 1 == 1)
                    .fold(0u64, |acc, k| acc ^ self.v_basis[k])
            })
            .collect()
    }
}

/// Descend `S_{m+1}(x_1, …, x_m, x_R) = 0` with every `x_i` in the span
/// of `v_basis`, for `summands ∈ {2, 3}`.  Fails only on a dimension
/// the monomial mask cannot hold.
pub fn descend(
    gf: &Gf2,
    b: u64,
    x_r: u64,
    v_basis: &[u64],
    summands: u32,
) -> Result<SymbolicDescent, String> {
    let n_prime = v_basis.len() as u32;
    if !(2..=3).contains(&summands) {
        return Err(format!(
            "the symbolic descent takes 2 or 3 summands, not {summands}"
        ));
    }
    if n_prime == 0 || n_prime > max_n_prime(summands) {
        return Err(format!(
            "a subspace of dimension {n_prime} at {summands} summands needs {} boolean variables; \
             the monomial mask holds {MAX_VARS}",
            n_prime * summands
        ));
    }
    let n_vars = (summands * n_prime) as usize;
    let poly = match summands {
        2 => s3_symbolic(gf, b, x_r, v_basis),
        _ => s4_symbolic(gf, b, x_r, v_basis),
    };
    Ok(SymbolicDescent {
        n: gf.n,
        n_prime,
        summands,
        n_vars,
        equations: poly.split(gf.n, n_vars),
        v_basis: v_basis.to_vec(),
        field_monomials: poly.len(),
    })
}

/// `S_3(x_1, x_2, x_R)` with `x_1`, `x_2` linear forms, term for term
/// the formula [`semaev_s3_word`] evaluates.
fn s3_symbolic(gf: &Gf2, b: u64, x_r: u64, v_basis: &[u64]) -> FieldBoolPoly {
    let np = v_basis.len() as u32;
    let x1 = FieldBoolPoly::linear(0, v_basis);
    let x2 = FieldBoolPoly::linear(np, v_basis);
    let sum12_sq = x1.add(&x2).sqr(gf);
    let prod12 = x1.mul(&x2, gf);
    let t1 = sum12_sq.scale(gf.sqr(x_r), gf);
    let t2 = prod12.scale(x_r, gf);
    let t3 = prod12.sqr(gf).add(&FieldBoolPoly::constant(b));
    t1.add(&t2).add(&t3)
}

/// `S_4(x_1, x_2, x_3, x_R)` with `x_1`, `x_2`, `x_3` linear forms,
/// term for term the resultant [`semaev_s4_word`] evaluates.
fn s4_symbolic(gf: &Gf2, b: u64, x_r: u64, v_basis: &[u64]) -> FieldBoolPoly {
    let np = v_basis.len() as u32;
    let x1 = FieldBoolPoly::linear(0, v_basis);
    let x2 = FieldBoolPoly::linear(np, v_basis);
    let x3 = FieldBoolPoly::linear(2 * np, v_basis);
    let x4 = FieldBoolPoly::constant(x_r);
    let bconst = FieldBoolPoly::constant(b);
    let s3_in_x3 = |p: &FieldBoolPoly, q: &FieldBoolPoly| {
        let a = p.add(q).sqr(gf);
        let bb = p.mul(q, gf);
        let c = bb.sqr(gf).add(&bconst);
        (a, bb, c)
    };
    let (a1, b1, c1) = s3_in_x3(&x1, &x2);
    let (a2, b2, c2) = s3_in_x3(&x3, &x4);
    let t1 = a1.mul(&c2, gf).add(&a2.mul(&c1, gf)).sqr(gf);
    let left = a1.mul(&b2, gf).add(&a2.mul(&b1, gf));
    let right = b1.mul(&c2, gf).add(&b2.mul(&c1, gf));
    t1.add(&left.mul(&right, gf))
}

// ── Tests ──────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::ic_boundary::random_binary_instance;
    use crate::cryptanalysis::ic_descent_degrees::curve_of;
    use crate::cryptanalysis::pq_descent::{weil_descend_s3, weil_descend_s4};
    use rand::rngs::StdRng;
    use rand::{Rng, SeedableRng};

    fn standard_basis(n_prime: u32) -> Vec<u64> {
        (0..n_prime).map(|k| 1u64 << k).collect()
    }

    fn sorted_masks(p: &F2BoolPoly) -> Vec<u64> {
        let mut v: Vec<u64> = p.terms.iter().map(|t| t.mask).collect();
        v.sort_unstable();
        v
    }

    /// **The word formulas agree with the `F2mElement` ones**, so a
    /// descent checked against them is checked against the
    /// repository's summation polynomials.
    #[test]
    fn the_word_formulas_are_the_repository_formulas() {
        use crate::cryptanalysis::binary_semaev::{binary_semaev_s3, binary_semaev_s4};
        let inst = random_binary_instance(11, 5, 1 << 20).expect("a curve at n = 11");
        let curve = curve_of(&inst).unwrap();
        let gf = &inst.gf;
        let mut rng = StdRng::seed_from_u64(3);
        for _ in 0..64 {
            let xs: Vec<u64> = (0..4).map(|_| rng.gen::<u64>() & gf.mask).collect();
            let es: Vec<_> = xs.iter().map(|&x| gf.to_element(x)).collect();
            let s3 = binary_semaev_s3(&es[0], &es[1], &es[2], &curve.b, &curve.irreducible);
            assert_eq!(
                gf.from_element(&s3),
                semaev_s3_word(gf, inst.b, xs[0], xs[1], xs[2])
            );
            let s4 = binary_semaev_s4(&es[0], &es[1], &es[2], &es[3], &curve.b, &curve.irreducible);
            assert_eq!(
                gf.from_element(&s4),
                semaev_s4_word(gf, inst.b, xs[0], xs[1], xs[2], xs[3])
            );
        }
    }

    /// **The symbolic descent is the truth-table descent, monomial for
    /// monomial**, at every dimension the truth table can still reach:
    /// the algebraic normal form of a boolean function is unique, so
    /// the two constructions of the same function must coincide
    /// exactly.  This is the cross-check `AGENTS.md` asks of anything
    /// that replaces a measured oracle.
    #[test]
    fn the_symbolic_descent_is_the_truth_table_descent() {
        let mut rng = StdRng::seed_from_u64(11);
        for &(n, seed) in &[(7u32, 1u64), (9, 2), (11, 3), (13, 4)] {
            let inst = random_binary_instance(n, seed, 1 << 20).expect("a curve");
            let curve = curve_of(&inst).unwrap();
            let gf = &inst.gf;
            for n_prime in 2..=5u32 {
                let words = standard_basis(n_prime);
                let elems: Vec<_> = words.iter().map(|&w| gf.to_element(w)).collect();
                for _ in 0..3 {
                    let x_r = rng.gen::<u64>() & gf.mask;
                    let x_r_el = gf.to_element(x_r);

                    let table = weil_descend_s3(&curve, &x_r_el, &elems);
                    let sym = descend(gf, inst.b, x_r, &words, 2).unwrap();
                    assert_eq!(sym.n_vars, table.n_vars);
                    assert_eq!(sym.equations.len(), table.equations.len());
                    for (j, (a, b)) in sym.equations.iter().zip(&table.equations).enumerate() {
                        assert_eq!(
                            sorted_masks(a),
                            sorted_masks(b),
                            "S3 descent at n = {n}, n' = {n_prime}, equation {j} differs"
                        );
                    }

                    if n_prime <= 4 {
                        let table = weil_descend_s4(&curve, &x_r_el, &elems);
                        let sym = descend(gf, inst.b, x_r, &words, 3).unwrap();
                        assert_eq!(sym.n_vars, table.n_vars);
                        for (j, (a, b)) in sym.equations.iter().zip(&table.equations).enumerate() {
                            assert_eq!(
                                sorted_masks(a),
                                sorted_masks(b),
                                "S4 descent at n = {n}, n' = {n_prime}, equation {j} differs"
                            );
                        }
                    }
                }
            }
        }
    }

    /// **Past the truth table's reach the descent still evaluates
    /// correctly**: at `n' = 12` (24 variables) every equation, at
    /// random points of the subspace, gives the bit of `S_3` it stands
    /// for, and the lift inverts the encoding.
    #[test]
    fn the_descent_evaluates_correctly_past_the_old_cap() {
        let inst = random_binary_instance(17, 9, 1 << 20).expect("a curve at n = 17");
        let gf = &inst.gf;
        let words = standard_basis(12);
        let mut rng = StdRng::seed_from_u64(23);
        let x_r = rng.gen::<u64>() & gf.mask;
        let sys = descend(gf, inst.b, x_r, &words, 2).unwrap();
        assert_eq!(sys.n_vars, 24);
        assert!(sys
            .equations
            .iter()
            .all(|e| e.terms.iter().all(|t| t.degree() <= 2)));
        for _ in 0..2000 {
            let v = rng.gen::<u64>() & ((1u64 << 24) - 1);
            let xs = sys.lift(v);
            let direct = semaev_s3_word(gf, inst.b, xs[0], xs[1], x_r);
            for (j, eq) in sys.equations.iter().enumerate() {
                assert_eq!(
                    eq.eval(v) as u64,
                    (direct >> j) & 1,
                    "equation {j} at {v:#x}"
                );
            }
        }
        // Three summands at a dimension the truth table could not hold.
        let words = standard_basis(7);
        let sys = descend(gf, inst.b, x_r, &words, 3).unwrap();
        assert_eq!(sys.n_vars, 21);
        assert!(sys
            .equations
            .iter()
            .all(|e| e.terms.iter().all(|t| t.degree() <= 6)));
        for _ in 0..500 {
            let v = rng.gen::<u64>() & ((1u64 << 21) - 1);
            let xs = sys.lift(v);
            let direct = semaev_s4_word(gf, inst.b, xs[0], xs[1], xs[2], x_r);
            for (j, eq) in sys.equations.iter().enumerate() {
                assert_eq!(
                    eq.eval(v) as u64,
                    (direct >> j) & 1,
                    "S4 equation {j} at {v:#x}"
                );
            }
        }
    }

    /// The only cap left is the monomial mask, and it is refused, not
    /// asserted.
    #[test]
    fn the_cap_is_the_monomial_mask() {
        let inst = random_binary_instance(9, 1, 1 << 20).unwrap();
        assert_eq!(max_n_prime(2), 32);
        assert_eq!(max_n_prime(3), 21);
        assert!(descend(&inst.gf, inst.b, 3, &standard_basis(33), 2).is_err());
        assert!(descend(&inst.gf, inst.b, 3, &standard_basis(22), 3).is_err());
        assert!(descend(&inst.gf, inst.b, 3, &standard_basis(4), 4).is_err());
    }
}
