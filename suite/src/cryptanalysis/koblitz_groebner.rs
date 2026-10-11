//! # Semaev polynomial systems for Koblitz-curve index calculus, solved by Gröbner basis.
//!
//! The decomposition oracle behind
//! [`crate::cryptanalysis::koblitz_index_calculus`].  Its question is
//!
//! > given `R ∈ E(F_{2^n})`, is `R = P_1 + … + P_m` with every `P_i` in
//! > the Frobenius-invariant factor base `F`?
//!
//! Galbraith–Granger–Merz–Petit answer it the way every index calculus
//! on elliptic curves since Gaudry and Diem does: write the condition
//! as a **Semaev summation polynomial**, restrict the unknowns to the
//! factor base (here, to an `F_2`-subspace `V ⊆ F_{2^n}`), take the Weil
//! restriction of the single `F_{2^n}`-equation down to `n` equations
//! over `F_2`, and hand the resulting Boolean system to a Gröbner-basis
//! engine.  This module is that pipeline; the caller keeps its
//! exhaustive-search oracle as a cross-check.
//!
//! ## The system
//!
//! For `m = 2` and `E : y² + xy = x³ + a x² + b`, the third summation
//! polynomial is (see [`crate::cryptanalysis::binary_semaev`])
//!
//! ```text
//!     S₃(x₁, x₂, x₃) = (x₁+x₂)² x₃² + x₁x₂ x₃ + (x₁x₂)² + b,
//! ```
//!
//! which vanishes exactly when some choice of `y`-coordinates makes
//! `±P₁ ± P₂ ± P₃ = O`.  Setting `x₃ := x(R)` and requiring
//! `x₁, x₂ ∈ V` gives one equation in two `V`-valued unknowns.  For
//! `m ≥ 3` the polynomial is **chained** rather than resolved — `S_{k}`
//! has degree `2^{k−2}` per variable and is impractical past `k = 3` —
//! so `m` summands become `m − 1` links of `S₃` joined by `m − 2`
//! intermediate unknowns ranging over the whole field:
//!
//! ```text
//!     S₃(x₁, x₂, e₁) = S₃(e₁, x₃, e₂) = … = S₃(e_{m−2}, x_m, x(R)) = 0.
//! ```
//!
//! ## Why the system stays low-degree
//!
//! Writing `x_i = Σ_t u_{i,t} · b_t` over an `F_2`-basis `b_t` of `V`
//! makes each `x_i` **linear** in the Boolean unknowns.  Squaring is
//! `F_2`-linear in characteristic 2 — and in the Boolean quotient
//! `v² = v` a polynomial satisfies `p² = p`, so a symbolic square costs
//! a permutation of coordinates and nothing else — while `x₁x₂` is
//! bilinear.
//!
//! For `m = 2` the third argument of `S₃` is the *known* `x(R)`, so
//! every term has degree ≤ 2: the Weil restriction is a **quadratic**
//! system of `n` equations in `2ℓ` unknowns — the shape Faugère et al.
//! analyse.  For `m ≥ 3` the chain's intermediate points are unknowns
//! too, and the term `x₁x₂·e` makes the system **cubic** in
//! `m·ℓ + (m−2)·n` unknowns.  Degree 3 is why the `m ≥ 3` instances
//! cost so much more here, in both engines.
//!
//! Restricting the unknowns to `V` is what keeps the degree this low at
//! all, and it is the property the linearised-polynomial factor base
//! has and a weight-bounded one does not.
//!
//! ## What the Gröbner step buys
//!
//! The exhaustive oracle costs `|F|^{m−1}` group operations per target
//! whether or not a decomposition exists.  Here, an **unsolvable**
//! target is usually rejected by the Gröbner computation alone: the
//! basis reduces to `{1}`, no search happens.  Solvable targets are
//! read off the basis by splitting (below).  The cost is governed by
//! the degree of regularity of the system rather than by `|F|`, which
//! is what makes the real algorithm sub-exponential.
//!
//! ## Solving the Boolean system
//!
//! [`groebner_basis_f2`] returns a DegRevLex basis, not a triangular
//! one, and this module deliberately does **not** call the brute-force
//! `solve_system_f2` extractor that would defeat the point.  Instead
//! [`solve_boolean_system`] runs the standard *Gröbner-with-splitting*
//! (`DPLL(GB)`) loop: compute a basis; if it contains the constant `1`
//! the branch is infeasible; propagate every basis element that has
//! collapsed to `v_i` or `v_i + 1`; otherwise split on the lowest free
//! variable and recurse.  Every branch is bounded by a node budget, and
//! solutions are verified against the original system before they are
//! returned.
//!
//! ## The engines
//!
//! [`SolverEngine`] selects what reduces the system at a node:
//!
//! - `MatrixF4`: the degree-bounded Macaulay matrix of every product
//!   `t·f_i`, row-reduced from scratch at every node ([`matrix_f4_f2`]).
//! - `MatrixF5`: the same matrix with the rows the F5 criterion predicts
//!   to reduce to zero left out ([`crate::cryptanalysis::matrix_f5_f2`]);
//!   same row space.  On the quadratic systems here the trivial syzygies
//!   first appear at degree 4, so at degree 3 it prunes only what linear
//!   equations allow.
//! - `InheritedF4` (the default): the root reduces as `MatrixF4` does and
//!   every descendant specialises its parent's reduced basis by the
//!   assigned variable ([`crate::cryptanalysis::inherited_f4`]); same row
//!   space at every node, no matrix built below the root.
//! - `Buchberger`: the textbook reference
//!   ([`crate::cryptanalysis::pq_groebner_f2`]), kept so the matrix engines
//!   can be tested against it.
//!
//! ## Honest scope
//!
//! - The toy parameters (`m·ℓ + (m−2)·n ≤ 64` unknowns, and in practice
//!   far fewer) are set by the `u64` monomial representation; nothing here
//!   bears on the oracle's cost at `n = 131`, which is bounded by the
//!   counting argument in
//!   `research/notes/ecc2k130/RESEARCH_ECC2K130_DECOMPOSITION.md`.
//! - `S₃` is a *necessary* condition on `x`-coordinates only.  A root
//!   fixes the summands up to sign, so each candidate is lifted to
//!   actual points and the group identity `P_1 + … + P_m = R` is
//!   re-checked before a relation is emitted.  No false relation can
//!   escape.
//!
//! ## References
//!
//! - S. D. Galbraith, R. Granger, S.-P. Merz, C. Petit, *On index
//!   calculus algorithms for subfield curves*, SAC 2020.
//! - I. Semaev, *Summation polynomials and the discrete logarithm
//!   problem on elliptic curves*, ePrint 2004/031.
//! - C. Diem, *On the discrete logarithm problem in elliptic curves*,
//!   Compositio Math. 147 (2011).
//! - J.-C. Faugère, L. Perret, C. Petit, G. Renault, *Improving the
//!   complexity of index calculus algorithms in elliptic curves over
//!   binary fields*, EUROCRYPT 2012 — the Weil-restriction-to-Boolean
//!   -system analysis this module implements.
//! - G. Bard, *Algebraic Cryptanalysis*, Springer 2009, ch. 13 — the
//!   Boolean-ring representation.

use crate::binary_ecc::{F2mElement, IrreduciblePoly};
use crate::cryptanalysis::f4_gf2::{self, MacaulayCaps};
use crate::cryptanalysis::inherited_f4::{ChildSystem, InheritCost, ReducedBasis};
use crate::cryptanalysis::matrix_f5_f2::F5Criterion;
use crate::cryptanalysis::pq_groebner_f2::{
    cmp_mono, groebner_basis_f2, mono_key, F2BoolMono, F2BoolPoly,
};

/// Hard cap: Boolean monomials are `u64` bitmasks in
/// [`crate::cryptanalysis::pq_groebner_f2`].
pub const MAX_VARS: usize = 64;

// ── Symbolic F_{2^n} arithmetic ────────────────────────────────────

/// Multiplication table of the polynomial basis `1, z, …, z^{n−1}`:
/// `reduced[i][j]` is the bit pattern of `z^i · z^j mod f(z)`.
///
/// This is all a symbolic multiplication needs: the coordinates of a
/// product are `F_2`-bilinear in the coordinates of the operands, with
/// these structure constants.
#[derive(Clone, Debug, serde::Serialize, serde::Deserialize)]
pub struct FieldStructure {
    /// Extension degree.
    pub n: u32,
    /// `reduced[i][j] = z^{i+j} mod f`, as a bitmask.
    pub reduced: Vec<Vec<u64>>,
    /// `squares[k] = z^{2k} mod f`, as a bitmask — the coordinate
    /// permutation-with-reduction that implements symbolic squaring.
    pub squares: Vec<u64>,
}

impl FieldStructure {
    /// Tabulate the structure constants of `F_2[z]/(f)`.
    pub fn new(n: u32, irr: &IrreduciblePoly) -> Self {
        let bits = |e: &F2mElement| e.raw_bits().first().copied().unwrap_or(0);
        let mono = |k: u32| F2mElement::from_bit_positions(&[k], n);
        let mut reduced = vec![vec![0u64; n as usize]; n as usize];
        for i in 0..n as usize {
            for j in 0..n as usize {
                reduced[i][j] = bits(&mono(i as u32).mul(&mono(j as u32), irr));
            }
        }
        let squares = (0..n).map(|k| reduced[k as usize][k as usize]).collect();
        Self {
            n,
            reduced,
            squares,
        }
    }
}

/// An element of `F_{2^n}` whose coordinates are Boolean polynomials —
/// i.e. a symbolic field element in the Weil restriction.
#[derive(Clone, Debug, serde::Serialize, serde::Deserialize)]
pub struct SymElement {
    /// `coords[k]` multiplies `z^k`.  Length `n`.
    pub coords: Vec<F2BoolPoly>,
}

/// Product of two Boolean polynomials (the engine ships `mul_mono`
/// only; `p·q` is the sum of `p·m` over the monomials `m` of `q`).
pub fn poly_mul(p: &F2BoolPoly, q: &F2BoolPoly) -> F2BoolPoly {
    if p.is_zero() || q.is_zero() {
        return F2BoolPoly::zero(p.n_vars);
    }
    let (p, q) = if p.terms.len() <= q.terms.len() {
        (p, q)
    } else {
        (q, p)
    };
    let mut acc = F2BoolPoly::zero(p.n_vars);
    for m in &q.terms {
        acc = acc.add(&p.mul_mono(*m));
    }
    acc
}

impl SymElement {
    /// The zero element.
    pub fn zero(n: u32, n_vars: usize) -> Self {
        Self {
            coords: (0..n).map(|_| F2BoolPoly::zero(n_vars)).collect(),
        }
    }

    /// A known field element, lifted to a constant symbolic one.
    pub fn constant(v: &F2mElement, n: u32, n_vars: usize) -> Self {
        let bits = v.raw_bits().first().copied().unwrap_or(0);
        let coords = (0..n)
            .map(|k| {
                if (bits >> k) & 1 == 1 {
                    F2BoolPoly::one(n_vars)
                } else {
                    F2BoolPoly::zero(n_vars)
                }
            })
            .collect();
        Self { coords }
    }

    /// An unknown ranging over the `F_2`-span of `basis`, using the
    /// Boolean variables `offset … offset + basis.len() − 1`:
    /// `x = Σ_t v_{offset+t} · basis[t]`.
    ///
    /// This is where the factor base enters the algebra — restricting
    /// the unknowns to the Frobenius-invariant subspace `V` is exactly
    /// what makes the system solvable at all.
    pub fn from_subspace_vars(basis: &[F2mElement], offset: usize, n: u32, n_vars: usize) -> Self {
        let mut coords = vec![Vec::new(); n as usize];
        for (t, b) in basis.iter().enumerate() {
            let bits = b.raw_bits().first().copied().unwrap_or(0);
            for k in 0..n as usize {
                if (bits >> k) & 1 == 1 {
                    coords[k].push(F2BoolMono::var((offset + t) as u32));
                }
            }
        }
        Self {
            coords: coords
                .into_iter()
                .map(|ms| F2BoolPoly::from_monos(ms, n_vars))
                .collect(),
        }
    }

    /// A wholly unknown field element on variables `offset … offset+n−1`
    /// — used for the intermediate points of a chained `S₃`.
    pub fn from_free_vars(offset: usize, n: u32, n_vars: usize) -> Self {
        Self {
            coords: (0..n as usize)
                .map(|k| F2BoolPoly::from_monos(vec![F2BoolMono::var((offset + k) as u32)], n_vars))
                .collect(),
        }
    }

    /// Coordinate-wise sum (char 2: also the difference).
    pub fn add(&self, other: &Self) -> Self {
        Self {
            coords: self
                .coords
                .iter()
                .zip(&other.coords)
                .map(|(a, b)| a.add(b))
                .collect(),
        }
    }

    /// Field multiplication via the structure constants.
    pub fn mul(&self, other: &Self, st: &FieldStructure) -> Self {
        let n = st.n as usize;
        let n_vars = self.coords[0].n_vars;
        // Cross products a_i · b_j, computed once.
        let mut prod = vec![vec![F2BoolPoly::zero(n_vars); n]; n];
        for i in 0..n {
            if self.coords[i].is_zero() {
                continue;
            }
            for j in 0..n {
                if other.coords[j].is_zero() {
                    continue;
                }
                prod[i][j] = poly_mul(&self.coords[i], &other.coords[j]);
            }
        }
        let mut coords = vec![F2BoolPoly::zero(n_vars); n];
        for i in 0..n {
            for j in 0..n {
                if prod[i][j].is_zero() {
                    continue;
                }
                let red = st.reduced[i][j];
                for (k, coord) in coords.iter_mut().enumerate() {
                    if (red >> k) & 1 == 1 {
                        *coord = coord.add(&prod[i][j]);
                    }
                }
            }
        }
        Self { coords }
    }

    /// Field squaring — an `F_2`-linear map, so it never raises the
    /// degree of the Boolean system.
    ///
    /// In characteristic 2, `(Σ_k a_k z^k)² = Σ_k a_k² z^{2k}`, and in
    /// the Boolean quotient `p² = p` for every polynomial `p` (the
    /// cross terms cancel in pairs and `v² = v`).  So squaring just
    /// re-indexes coordinates through `z^{2k} mod f`.
    pub fn square(&self, st: &FieldStructure) -> Self {
        let n = st.n as usize;
        let n_vars = self.coords[0].n_vars;
        let mut coords = vec![F2BoolPoly::zero(n_vars); n];
        for (k, c) in self.coords.iter().enumerate() {
            if c.is_zero() {
                continue;
            }
            let sq = st.squares[k];
            for (t, coord) in coords.iter_mut().enumerate() {
                if (sq >> t) & 1 == 1 {
                    *coord = coord.add(c);
                }
            }
        }
        Self { coords }
    }

    /// Evaluate at a Boolean assignment, giving a concrete field element.
    pub fn eval(&self, point: u64, n: u32) -> F2mElement {
        let mut positions = Vec::new();
        for (k, c) in self.coords.iter().enumerate() {
            if c.eval(point) == 1 {
                positions.push(k as u32);
            }
        }
        F2mElement::from_bit_positions(&positions, n)
    }
}

// ── The Semaev system ──────────────────────────────────────────────

/// Symbolic `S₃(x₁, x₂, x₃) = (x₁+x₂)² x₃² + x₁x₂ x₃ + (x₁x₂)² + b`.
///
/// Returns the `n` Boolean coordinate equations of the single
/// `F_{2^n}`-equation `S₃ = 0`.
pub fn sym_semaev_s3(
    x1: &SymElement,
    x2: &SymElement,
    x3: &SymElement,
    b: &F2mElement,
    st: &FieldStructure,
) -> Vec<F2BoolPoly> {
    let n_vars = x1.coords[0].n_vars;
    let sum_sq = x1.add(x2).square(st);
    let x3_sq = x3.square(st);
    let prod = x1.mul(x2, st);

    let mut acc = sum_sq.mul(&x3_sq, st);
    acc = acc.add(&prod.mul(x3, st));
    acc = acc.add(&prod.square(st));
    acc = acc.add(&SymElement::constant(b, st.n, n_vars));
    acc.coords
}

/// **The symmetrised fourth summation polynomial**, Weil-restricted.
///
/// Returns the `n` Boolean coordinates of
///
/// ```text
///   f₃ = x_R⁴ + e₁⁴ + e₃⁴ + e₂⁴x_R⁴ + e₃³x_R + e₃e₂²x_R³ + e₃e₁²x_R
///        + e₃x_R³ + e₁²e₃²x_R² + e₃²x_R⁴ + e₃² + e₂²x_R²
/// ```
///
/// where `e₁, e₂, e₃` are the elementary symmetric functions of `x₁,
/// x₂, x₃`.  It vanishes exactly when some choice of signs makes
/// `±P₁ ± P₂ ± P₃ ± R = O`, so unlike the chained `S₃` of
/// [`build_decomposition_system`] it needs **no intermediate unknowns**
/// — which is the whole reason it is here.  Fixing `x₁` to a constant
/// leaves a system in the `2ℓ` unknowns of `x₂` and `x₃` alone, and
/// that is the object
/// [`research/notes/index-calculus/RESEARCH_SEMAEV_DECOMPOSITION.md`](../../research/notes/index-calculus/RESEARCH_SEMAEV_DECOMPOSITION.md)
/// names as the one route to a sub-`2^{2ℓ}` decomposition oracle.
///
/// Any of `x₁, x₂, x₃` may be a [`SymElement::constant`]; the degree of
/// the result in the Boolean unknowns drops accordingly.
///
/// Specialised to `b = 1` (the Koblitz curve `y² + xy = x³ + x² + 1`),
/// which is what the twelve constants above are folded for.
pub fn sym_semaev_s4(
    x1: &SymElement,
    x2: &SymElement,
    x3: &SymElement,
    x_r: &F2mElement,
    st: &FieldStructure,
) -> Vec<F2BoolPoly> {
    let n_vars = x1.coords[0].n_vars;
    let n = st.n;

    let e1 = x1.add(x2).add(x3);
    let p12 = x1.mul(x2, st);
    let e2 = p12.add(&x1.mul(x3, st)).add(&x2.mul(x3, st));
    let e3 = p12.mul(x3, st);

    let e1_sq = e1.square(st);
    let e2_sq = e2.square(st);
    let e3_sq = e3.square(st);

    // Powers of the known target, as constants.
    let xr1 = SymElement::constant(x_r, n, n_vars);
    let xr2 = xr1.square(st);
    let xr3 = xr2.mul(&xr1, st);
    let xr4 = xr2.square(st);

    let mut acc = xr4.clone();
    acc = acc.add(&e1_sq.square(st)); // e₁⁴
    acc = acc.add(&e3_sq.square(st)); // e₃⁴
    acc = acc.add(&e2_sq.square(st).mul(&xr4, st)); // e₂⁴x_R⁴
    acc = acc.add(&e3_sq.mul(&e3, st).mul(&xr1, st)); // e₃³x_R
    acc = acc.add(&e3.mul(&e2_sq, st).mul(&xr3, st)); // e₃e₂²x_R³
    acc = acc.add(&e3.mul(&e1_sq, st).mul(&xr1, st)); // e₃e₁²x_R
    acc = acc.add(&e3.mul(&xr3, st)); // e₃x_R³
    acc = acc.add(&e1_sq.mul(&e3_sq, st).mul(&xr2, st)); // e₁²e₃²x_R²
    acc = acc.add(&e3_sq.mul(&xr4, st)); // e₃²x_R⁴
    acc = acc.add(&e3_sq); // e₃²
    acc = acc.add(&e2_sq.mul(&xr2, st)); // e₂²x_R²
    acc.coords
}

/// The Boolean system whose roots are the `m`-point decompositions of a
/// target with abscissa `x_r` over the subspace spanned by `basis`.
#[derive(Clone, Debug, serde::Serialize, serde::Deserialize)]
pub struct DecompositionSystem {
    /// The equations, `n` per `S₃` link.
    pub equations: Vec<F2BoolPoly>,
    /// Total Boolean unknowns.
    pub n_vars: usize,
    /// Unknowns per summand (`ℓ = dim V`).
    pub ell: usize,
    /// Number of summands.
    pub m: usize,
}

impl DecompositionSystem {
    /// The `x`-coordinate that Boolean assignment `point` gives to
    /// summand `i`, as an element of the subspace.
    pub fn summand_x(&self, basis: &[F2mElement], point: u64, i: usize, n: u32) -> F2mElement {
        let mut positions = Vec::new();
        for t in 0..self.ell {
            if (point >> (i * self.ell + t)) & 1 == 1 {
                let bits = basis[t].raw_bits().first().copied().unwrap_or(0);
                for k in 0..n {
                    if (bits >> k) & 1 == 1 {
                        positions.push(k);
                    }
                }
            }
        }
        // XOR-fold: a coordinate hit twice cancels.
        let mut acc = F2mElement::zero(n);
        for k in positions {
            acc = acc.add(&F2mElement::from_bit_positions(&[k], n));
        }
        acc
    }
}

/// **Build the decomposition system** for `R = P_1 + … + P_m`, all
/// `x(P_i)` constrained to the `F_2`-span of `basis`.
///
/// Variable layout: `m · ℓ` subspace coordinates first (summand `i`
/// owns `[i·ℓ, (i+1)·ℓ)`), then `(m − 2)·n` coordinates for the
/// intermediate points of the chain.
///
/// Returns `None` if the layout would exceed [`MAX_VARS`] or if
/// `m < 2`.
pub fn build_decomposition_system(
    basis: &[F2mElement],
    x_r: &F2mElement,
    b: &F2mElement,
    m: usize,
    st: &FieldStructure,
) -> Option<DecompositionSystem> {
    if m < 2 {
        return None;
    }
    let ell = basis.len();
    let n = st.n;
    let n_vars = m * ell + m.saturating_sub(2) * n as usize;
    if n_vars > MAX_VARS {
        return None;
    }

    let summands: Vec<SymElement> = (0..m)
        .map(|i| SymElement::from_subspace_vars(basis, i * ell, n, n_vars))
        .collect();
    let target = SymElement::constant(x_r, n, n_vars);

    let mut equations = Vec::new();
    if m == 2 {
        equations.extend(sym_semaev_s3(&summands[0], &summands[1], &target, b, st));
    } else {
        // Chain: S₃(x₁, x₂, e₁), S₃(e_i, x_{i+2}, e_{i+1}), …, last
        // link closes on x(R).
        let inter: Vec<SymElement> = (0..m - 2)
            .map(|i| SymElement::from_free_vars(m * ell + i * n as usize, n, n_vars))
            .collect();
        equations.extend(sym_semaev_s3(&summands[0], &summands[1], &inter[0], b, st));
        for i in 0..m - 3 {
            equations.extend(sym_semaev_s3(
                &inter[i],
                &summands[i + 2],
                &inter[i + 1],
                b,
                st,
            ));
        }
        equations.extend(sym_semaev_s3(
            &inter[m - 3],
            &summands[m - 1],
            &target,
            b,
            st,
        ));
    }

    Some(DecompositionSystem {
        equations,
        n_vars,
        ell,
        m,
    })
}

// ── Block structure ────────────────────────────────────────────────

impl DecompositionSystem {
    /// The **block partition** the variables fall into: one block of
    /// `ℓ` per summand, then one block of `n` per intermediate point of
    /// the chain, in the layout order
    /// [`build_decomposition_system`] uses.
    ///
    /// The system is *multilinear* with respect to this partition —
    /// degree at most one in each block — which is a much stronger
    /// statement than its total degree.  For `m = 2` the single `S₃`
    /// link is `(x₁+x₂)²x_R² + x₁x₂x_R + (x₁x₂)² + b`: every term is
    /// bilinear in the two summand blocks, because squaring is
    /// `F_2`-linear and `x₁x₂` is bilinear.  For `m ≥ 3` the chained
    /// links keep the property with the intermediate blocks joining in,
    /// so the system is total-degree 3 but multidegree `(1,1,…,1)`.
    ///
    /// That is what [`matrix_f4_f2_blocked`] exploits.
    pub fn blocks(&self, n: u32) -> Vec<usize> {
        let mut v = vec![self.ell; self.m];
        v.extend(std::iter::repeat_n(n as usize, self.m.saturating_sub(2)));
        v
    }

    /// The **interleaved solve order** of a chain, as a permutation
    /// `perm[old] = new` of the variables: `x₁, x₂, e₁, x₃, e₂, …, e_{m−2},
    /// x_m` from the lowest index to the highest, each block keeping its
    /// internal order.  The identity for `m = 2`.
    ///
    /// [`SplitRule::HighestFree`] splits on the highest-indexed free
    /// variable, so under this order the solver fixes the last summand
    /// `x_m` first.  Once it is fixed, the last link `S₃(e_{m−2}, x_m,
    /// x_R)` is `F_2`-linear in `e_{m−2}`'s coordinates (squaring is
    /// linear), the intermediate point is eliminated rather than split
    /// on, and the link before it is bilinear in `(e_{m−3}, x_{m−1})` —
    /// the same step one link further in, down to an `m = 2` system in
    /// `x₁, x₂`.  Under the layout order the solver splits on the `n`
    /// coordinates of `e_{m−2}` first, the least constrained unknowns in
    /// the system (`RESEARCH_CHAIN_SPLIT_ORDER.md`).
    pub fn interleaved_order(&self, n: u32) -> Vec<u32> {
        let (ell, m, n) = (self.ell, self.m, n as usize);
        let summand = |i: usize| i * ell..(i + 1) * ell;
        let inter = |j: usize| m * ell + j * n..m * ell + (j + 1) * n;
        let mut order: Vec<usize> = Vec::with_capacity(self.n_vars);
        order.extend(summand(0));
        if m >= 2 {
            order.extend(summand(1));
        }
        for i in 2..m {
            order.extend(inter(i - 2));
            order.extend(summand(i));
        }
        debug_assert_eq!(order.len(), self.n_vars);
        let mut perm = vec![0u32; self.n_vars];
        for (new, &old) in order.iter().enumerate() {
            perm[old] = new as u32;
        }
        perm
    }
}

/// Rename the variables of `p` by `perm[old] = new`.
pub fn permute_poly(p: &F2BoolPoly, perm: &[u32]) -> F2BoolPoly {
    F2BoolPoly::from_monos(
        p.terms
            .iter()
            .map(|t| F2BoolMono::from_mask(permute_mask(t.mask, perm)))
            .collect(),
        p.n_vars,
    )
}

/// Rename the variables of a monomial or point mask by `perm[old] = new`.
pub fn permute_mask(mask: u64, perm: &[u32]) -> u64 {
    let mut out = 0u64;
    let mut bits = mask;
    while bits != 0 {
        let v = bits.trailing_zeros() as usize;
        bits &= bits - 1;
        out |= 1u64 << perm[v];
    }
    out
}

/// The inverse of a permutation `perm[old] = new`.
pub fn invert_permutation(perm: &[u32]) -> Vec<u32> {
    let mut inverse = vec![0u32; perm.len()];
    for (old, &new) in perm.iter().enumerate() {
        inverse[new as usize] = old as u32;
    }
    inverse
}

/// Whether the decomposition oracle solves a chain in
/// [`DecompositionSystem::interleaved_order`] when the solve splits on the
/// highest free variable: yes unless `KIC_CHAIN_ORDER=layout`, the
/// retained control that restores the layout order.
pub fn chain_order_interleaved(split_rule: SplitRule) -> bool {
    split_rule == SplitRule::HighestFree
        && std::env::var("KIC_CHAIN_ORDER").as_deref() != Ok("layout")
}

/// Per-block degree of a Boolean monomial under a block partition.
///
/// `blocks` gives block sizes in variable-index order, so block `i`
/// owns a contiguous range of variables.
pub fn block_degrees(mask: u64, blocks: &[usize]) -> Vec<u32> {
    let mut out = Vec::with_capacity(blocks.len());
    let mut lo = 0usize;
    for &w in blocks {
        let hi = (lo + w).min(64);
        let window = if lo >= 64 {
            0
        } else if hi - lo >= 64 {
            u64::MAX
        } else {
            ((1u64 << (hi - lo)) - 1) << lo
        };
        out.push((mask & window).count_ones());
        lo = hi;
    }
    out
}

/// Largest per-block degree over the terms of a polynomial.
pub fn poly_block_degrees(p: &F2BoolPoly, blocks: &[usize]) -> Vec<u32> {
    let mut out = vec![0u32; blocks.len()];
    for t in &p.terms {
        for (o, d) in out.iter_mut().zip(block_degrees(t.mask, blocks)) {
            *o = (*o).max(d);
        }
    }
    out
}

/// **Matrix-F4 with a multidegree bound** instead of a total-degree one.
///
/// The ordinary [`matrix_f4_f2`] shifts every input polynomial by every
/// monomial that keeps the *total* degree within `degree`.  On a system
/// that is multilinear with respect to a block partition that is
/// wasteful: it spends most of its columns on monomials with a high
/// degree inside one block, and those are precisely the monomials the
/// structure says cannot help.
///
/// This bounds the degree **per block** instead.  A shift is kept only
/// when every term of the product stays inside the bounds, so every row
/// is still an honest multiple of an input polynomial and a returned
/// constant `1` is still a genuine certificate of infeasibility — the
/// row space is a subspace of the total-degree one, never larger.
///
/// The column count goes from `C(v, ≤D)` to `Π_i C(v_i, ≤d_i)`, which
/// on the decomposition systems is where the saving is.
///
/// Returns the reduced rows and the 64-bit word XORs the elimination
/// performed, or `None` if the matrix would exceed the size limits.
pub fn matrix_f4_f2_blocked(
    polys: &[F2BoolPoly],
    n_vars: usize,
    blocks: &[usize],
    bounds: &[u32],
) -> Option<(Vec<F2BoolPoly>, u64)> {
    let row_cap = max_f4_rows();
    if polys.is_empty() || blocks.len() != bounds.len() {
        return Some((Vec::new(), 0));
    }
    let within = |mask: u64| -> bool {
        block_degrees(mask, blocks)
            .iter()
            .zip(bounds)
            .all(|(d, b)| d <= b)
    };

    // Candidate shifts: monomials already inside the bounds.  A shift
    // that breaks a bound on its own can only break it further after
    // multiplication.
    let total_bound: u32 = bounds.iter().sum();
    let mut rows_monos: Vec<Vec<u64>> = Vec::new();
    for p in polys {
        for mult in monomials_up_to(n_vars, total_bound) {
            if !within(mult) {
                continue;
            }
            let row = {
                let mut all: Vec<u64> = p.terms.iter().map(|t| t.mask | mult).collect();
                all.sort_unstable();
                let mut row: Vec<u64> = Vec::with_capacity(all.len());
                let mut i = 0;
                while i < all.len() {
                    let mut j = i;
                    while j < all.len() && all[j] == all[i] {
                        j += 1;
                    }
                    if (j - i) % 2 == 1 {
                        row.push(all[i]);
                    }
                    i = j;
                }
                row
            };
            // Every term must stay inside the bounds, or the row would
            // need a column the bound excludes and truncating it would
            // leave the ideal.
            if row.is_empty() || !row.iter().all(|&m| within(m)) {
                continue;
            }
            rows_monos.push(row);
            if rows_monos.len() > row_cap {
                return None;
            }
        }
    }
    if rows_monos.is_empty() {
        return Some((Vec::new(), 0));
    }

    let mut cols: Vec<u64> = rows_monos.iter().flatten().copied().collect();
    cols.sort_unstable();
    cols.dedup();
    if cols.len() > max_f4_cols() {
        return None;
    }
    cols.sort_by(|a, b| cmp_mono(F2BoolMono::from_mask(*a), F2BoolMono::from_mask(*b)).reverse());
    let index: std::collections::HashMap<u64, usize> =
        cols.iter().enumerate().map(|(i, m)| (*m, i)).collect();

    let words = cols.len().div_ceil(64);
    let mut matrix: Vec<Vec<u64>> = rows_monos
        .iter()
        .map(|monos| {
            let mut row = vec![0u64; words];
            for m in monos {
                let c = index[m];
                row[c / 64] |= 1 << (c % 64);
            }
            row
        })
        .collect();

    let mut word_ops = 0u64;
    let rank = rref_f2_counted(&mut matrix, cols.len(), &mut word_ops);
    charge_word_ops(word_ops);

    let n_vars_out = polys[0].n_vars;
    let mut out = Vec::with_capacity(rank);
    for row in matrix.iter().take(rank) {
        let monos: Vec<F2BoolMono> = (0..cols.len())
            .filter(|c| row[c / 64] & (1u64 << (c % 64)) != 0)
            .map(|c| F2BoolMono::from_mask(cols[c]))
            .collect();
        if !monos.is_empty() {
            out.push(F2BoolPoly::from_monos(monos, n_vars_out));
        }
    }
    Some((out, word_ops))
}

// ── Matrix-F4 over the Boolean ring ────────────────────────────────

/// All monomials of degree `≤ deg` over `n_vars` Boolean variables, as
/// masks.  (In the Boolean ring a monomial is a subset of variables.)
fn monomials_up_to(n_vars: usize, deg: u32) -> Vec<u64> {
    let mut out = vec![0u64];
    let mut level = vec![0u64];
    for _ in 0..deg {
        let mut next = Vec::new();
        for &m in &level {
            let top = 64 - m.leading_zeros();
            for v in top..n_vars as u32 {
                next.push(m | (1u64 << v));
            }
        }
        out.extend(next.iter().copied());
        level = next;
        if level.is_empty() {
            break;
        }
    }
    out
}

pub(crate) fn monomials_up_to_mask(variable_mask: u64, degree: u32) -> Vec<u64> {
    let variables: Vec<u64> = (0..64)
        .filter(|bit| variable_mask & (1u64 << bit) != 0)
        .map(|bit| 1u64 << bit)
        .collect();
    let mut out = vec![0u64];
    let mut level = vec![(0u64, 0usize)];
    for _ in 0..degree {
        let mut next = Vec::new();
        for &(monomial, start) in &level {
            for (index, &variable) in variables.iter().enumerate().skip(start) {
                next.push((monomial | variable, index + 1));
            }
        }
        out.extend(next.iter().map(|(monomial, _)| *monomial));
        level = next;
        if level.is_empty() {
            break;
        }
    }
    out
}

fn cached_monomials_up_to_mask(variable_mask: u64, degree: u32) -> std::rc::Rc<[u64]> {
    use std::cell::RefCell;
    use std::collections::HashMap;
    use std::rc::Rc;

    thread_local! {
        static CACHE: RefCell<HashMap<(u64, u32), Rc<[u64]>>> = RefCell::new(HashMap::new());
    }
    static DISABLED: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    let disabled = *DISABLED
        .get_or_init(|| std::env::var("KIC_F4_DISABLE_SCHEDULE_CACHE").as_deref() == Ok("1"));
    let cacheable = degree <= 2 && !disabled;
    if !cacheable {
        return monomials_up_to_mask(variable_mask, degree).into();
    }
    CACHE.with(|cache| {
        let mut cache = cache.borrow_mut();
        if let Some(schedule) = cache.get(&(variable_mask, degree)) {
            return schedule.clone();
        }
        let schedule: Rc<[u64]> = monomials_up_to_mask(variable_mask, degree).into();
        if cache.len() >= 128 {
            cache.clear();
        }
        cache.insert((variable_mask, degree), schedule.clone());
        schedule
    })
}

pub(crate) fn all_variable_mask(n_vars: usize) -> u64 {
    if n_vars >= 64 {
        u64::MAX
    } else {
        (1u64 << n_vars) - 1
    }
}

/// Macaulay size caps — 20 000 rows and 40 000 columns, so a too-large
/// system degrades to splitting instead of exhausting memory —
/// overridable for experiments through the `F4_F2_MAX_ROWS` /
/// `F4_F2_MAX_COLS` environment variables.
pub(crate) fn f4_caps() -> MacaulayCaps {
    f4_gf2::default_caps()
}

/// Row cap of [`f4_caps`].
fn max_f4_rows() -> usize {
    f4_caps().max_rows
}

/// Column cap of [`f4_caps`].
fn max_f4_cols() -> usize {
    f4_caps().max_cols
}

/// Which implementation reduces the Boolean Macaulay matrices.
///
/// Both give the same answers: [`F4Kernel::Fast`] returns the reference
/// reduced rows bit-for-bit from [`matrix_f4_f2`], and the splitting
/// solver draws the same refutations and forced assignments from it.  They
/// differ in cost, and in the word XORs [`F4Profile`] reports, which are
/// each kernel's own.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum F4Kernel {
    /// The hash-indexed build over all variables with the row reduction
    /// of `matrix_f4_f2_counted_impl` (M4RI, flat matrices, cached
    /// layouts, the solver's linear-tail readback): the implementation
    /// this module grew upstream, kept as the paired control.
    Reference,
    /// [`super::f4_gf2`]: a rank-indexed build over the occurring
    /// variables, bucketed elimination, and — in the solver — the
    /// decision read off the linear block without a full reduction.
    Fast,
}

/// The kernel in use, fixed for the process: `F4_F2_RREF=reference`
/// selects [`F4Kernel::Reference`], anything else [`F4Kernel::Fast`].
pub fn f4_kernel() -> F4Kernel {
    static KERNEL: std::sync::OnceLock<F4Kernel> = std::sync::OnceLock::new();
    *KERNEL.get_or_init(|| match std::env::var("F4_F2_RREF").as_deref() {
        Ok("reference") => F4Kernel::Reference,
        _ => F4Kernel::Fast,
    })
}

/// **Matrix-F4 step over `F_2`**: multiply every input polynomial by
/// every monomial that keeps the degree `≤ degree`, row-reduce the
/// resulting Macaulay matrix, and return the reduced rows as
/// polynomials.
///
/// This is F4's engine — Buchberger's S-pair reductions replaced by one
/// linear-algebra pass over all products at a bounded degree — without
/// the symbolic preprocessing that chooses a minimal row set.  Every
/// returned polynomial lies in the ideal generated by `polys` (it is an
/// `F_2`-combination of multiples of them), so a returned constant `1`
/// is a genuine certificate of infeasibility.
///
/// Returns `None` if the matrix would exceed the size limits.
pub fn matrix_f4_f2(polys: &[F2BoolPoly], n_vars: usize, degree: u32) -> Option<Vec<F2BoolPoly>> {
    matrix_f4_f2_counted(polys, n_vars, degree).map(|(rows, _)| rows)
}

/// As [`matrix_f4_f2`], but also returns the number of 64-bit word XORs
/// the row reduction performed.
///
/// The count exists so an F4 reduction can be priced in the same unit as
/// the other engines that solve these systems — notably
/// [`crate::cryptanalysis::crossbred`], whose preprocessing is the same
/// kind of elimination on the same kind of matrix.  It measures the
/// elimination only: building the matrix and reading the rows back out
/// are not counted, because they are linear in the matrix size and the
/// elimination is not.
pub fn matrix_f4_f2_counted(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
) -> Option<(Vec<F2BoolPoly>, u64)> {
    match f4_kernel() {
        F4Kernel::Reference => {
            matrix_f4_f2_counted_impl(polys, n_vars, degree, false, RowCriterion::None)
        }
        F4Kernel::Fast => {
            let (rows, counters) = f4_gf2::matrix_rows(polys, n_vars, degree, f4_caps());
            f4_profile_add_kernel(&counters);
            rows.map(|r| (r, counters.word_ops))
        }
    }
}

/// The [`F4Kernel::Reference`] computation with explicit caps: the reduced
/// rows and, when a nonempty matrix was built, its `(rows, cols)`.  The
/// oracle the fast kernels are tested against.
#[cfg(test)]
pub(crate) fn matrix_f4_f2_reference(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    caps: MacaulayCaps,
) -> Option<(Vec<F2BoolPoly>, Option<(u64, u64)>)> {
    if polys.is_empty() {
        return Some((Vec::new(), None));
    }
    let rows_monos = macaulay_rows_monos_capped(polys, n_vars, degree, caps.max_rows)?;
    if rows_monos.is_empty() {
        return Some((Vec::new(), None));
    }
    let cols = macaulay_columns_capped(&rows_monos, caps.max_cols)?;
    let index: std::collections::HashMap<u64, usize> =
        cols.iter().enumerate().map(|(i, m)| (*m, i)).collect();
    let words = cols.len().div_ceil(64);
    let mut matrix: Vec<Vec<u64>> = rows_monos
        .iter()
        .map(|monos| {
            let mut row = vec![0u64; words];
            for m in monos {
                let c = index[m];
                row[c / 64] |= 1 << (c % 64);
            }
            row
        })
        .collect();
    let rank = rref_f2(&mut matrix, cols.len());
    let n_vars_out = polys[0].n_vars;
    let out = matrix
        .iter()
        .take(rank)
        .map(|row| {
            let monos: Vec<F2BoolMono> = (0..cols.len())
                .filter(|c| row[c / 64] & (1u64 << (c % 64)) != 0)
                .map(|c| F2BoolMono::from_mask(cols[c]))
                .collect();
            F2BoolPoly::from_monos(monos, n_vars_out)
        })
        .filter(|p| !p.is_zero())
        .collect();
    Some((out, Some((rows_monos.len() as u64, cols.len() as u64))))
}

/// Add one [`f4_gf2`] call to the profile, in the fields the reference
/// kernel fills, and charge its word XORs to the process and thread
/// totals ([`f4_word_ops_total`], [`f4_word_ops_thread`]).
pub(crate) fn f4_profile_add_kernel(k: &f4_gf2::KernelCounters) {
    if k.oversize {
        f4_profile_add(|p| {
            p.oversize += 1;
            p.build_ns += k.build_ns;
        });
    } else if k.built {
        charge_word_ops(k.word_ops);
        f4_profile_add(|p| {
            p.calls += 1;
            p.build_ns += k.build_ns;
            p.reduce_ns += k.reduce_ns;
            p.readback_ns += k.readback_ns;
            p.rows += k.rows;
            p.cols += k.cols;
            p.eliminated_rows += k.eliminated_rows;
            p.eliminated_cols += k.eliminated_cols;
            p.f5_skipped += k.f5_skipped;
            p.word_ops += k.word_ops;
        });
    }
}

/// As [`matrix_f4_f2_counted`], with the rows selected by `criterion`.
/// Under [`RowCriterion::F5`] the returned count includes the word XORs
/// the criterion spent, so the two variants are priced on the same
/// footing.
pub fn matrix_f4_f2_counted_with(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    criterion: RowCriterion,
) -> Option<(Vec<F2BoolPoly>, u64)> {
    matrix_f4_f2_counted_impl(polys, n_vars, degree, false, criterion)
}

/// Solver-specialized F4 step. The recursive solver only consumes rows that
/// refute the branch or force one variable, so avoid materializing every
/// nonlinear reduced row back into a polynomial. At 24 or more variables it
/// also multiplies only by variables still occurring in the specialised
/// system and computes only the linear-tail row-space intersection. A variable
/// absent from every generator cannot create a consequence without that
/// variable, so those omitted multiples do not change the decisive tail;
/// `KIC_F4_ACTIVE_MULTIPLIERS=0|1` overrides the multiplier schedule,
/// and exact support-verified column layouts are reused by active mask and
/// degree (`KIC_F4_DISABLE_LAYOUT_CACHE=1` disables that cache). Multiplier
/// schedules of degree at most two are cached per thread as well
/// (`KIC_F4_DISABLE_SCHEDULE_CACHE=1` disables them),
/// `KIC_F4_SOLVER_LINEAR_TAIL=0|1` overrides that selection and
/// `KIC_F4_FLAT_MATRIX=0|1` controls the contiguous solver matrix,
/// `KIC_F4_SOLVER_FULL_READBACK=1` restores the complete legacy readback.
fn matrix_f4_f2_solver_consequences(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    criterion: RowCriterion,
) -> Option<Vec<F2BoolPoly>> {
    matrix_f4_f2_counted_impl(polys, n_vars, degree, true, criterion).map(|(rows, _)| rows)
}

enum F4PackedMatrix {
    Nested(Vec<Vec<u64>>),
    Flat(FlatF2Matrix),
}

impl F4PackedMatrix {
    fn rows(&self) -> usize {
        match self {
            Self::Nested(matrix) => matrix.len(),
            Self::Flat(matrix) => matrix.rows,
        }
    }
}

fn matrix_f4_f2_counted_impl(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    decisive_only: bool,
    criterion: RowCriterion,
) -> Option<(Vec<F2BoolPoly>, u64)> {
    if polys.is_empty() {
        return Some((Vec::new(), 0));
    }
    let t_build = std::time::Instant::now();
    let active_multipliers = decisive_only
        && match std::env::var("KIC_F4_ACTIVE_MULTIPLIERS").as_deref() {
            Ok("1") => true,
            Ok("0") => false,
            _ => n_vars >= 24,
        };
    let multiplier_mask = if active_multipliers {
        occurring_vars(polys)
    } else {
        all_variable_mask(n_vars)
    };
    let reuse_layout =
        active_multipliers && std::env::var("KIC_F4_DISABLE_LAYOUT_CACHE").as_deref() != Ok("1");
    // At this width the solver spends more on clearing nonlinear pivots above
    // their blocks than on the useful row-space intersection. Keep the small
    // systems on the historical full RREF path and expose both sides for
    // retained controls.
    let use_linear_tail = decisive_only
        && match std::env::var("KIC_F4_SOLVER_LINEAR_TAIL").as_deref() {
            Ok("1") => true,
            Ok("0") => false,
            _ => n_vars >= 24,
        };
    let use_flat = use_linear_tail
        && match std::env::var("KIC_F4_FLAT_MATRIX").as_deref() {
            Ok("1") => true,
            Ok("0") => false,
            _ => n_vars >= 24,
        };
    let built = if use_flat {
        build_macaulay_flat_with_multiplier_mask(
            polys,
            n_vars,
            degree,
            multiplier_mask,
            reuse_layout,
            criterion,
        )
        .map(|b| {
            (
                b.columns,
                F4PackedMatrix::Flat(b.matrix),
                b.rows_pruned,
                b.criterion_word_ops,
            )
        })
    } else {
        build_macaulay_with_multiplier_mask(
            polys,
            n_vars,
            degree,
            multiplier_mask,
            reuse_layout,
            criterion,
        )
        .map(|b| {
            (
                b.columns,
                F4PackedMatrix::Nested(b.matrix),
                b.rows_pruned,
                b.criterion_word_ops,
            )
        })
    };
    let build_ns = t_build.elapsed().as_nanos();
    let (cols, mut matrix, rows_pruned, criterion_word_ops) = match built {
        Some(b) => b,
        None => {
            f4_profile_add(|p| {
                p.oversize += 1;
                p.build_ns += build_ns;
            });
            return None;
        }
    };
    if matrix.rows() == 0 {
        f4_profile_add(|p| {
            p.calls += 1;
            p.build_ns += build_ns;
            p.rows_pruned += rows_pruned;
            p.criterion_word_ops += criterion_word_ops;
            p.word_ops += criterion_word_ops;
        });
        charge_word_ops(criterion_word_ops);
        return Some((Vec::new(), criterion_word_ops));
    }
    // The criterion's echelons are elimination work in the same unit; the
    // step is priced as a whole, so they enter the count before the
    // reduction's own XORs.
    let mut word_ops = criterion_word_ops;
    let t_reduce = std::time::Instant::now();
    let mut linear_tail = None;
    let rank = if use_linear_tail {
        let low_start = cols
            .iter()
            .position(|mask| mask.count_ones() <= 1)
            .unwrap_or(cols.len());
        let (low, low_rank) = match &mut matrix {
            F4PackedMatrix::Nested(matrix) => {
                f4_solver_linear_tail(matrix, cols.len(), low_start, &mut word_ops)
            }
            F4PackedMatrix::Flat(matrix) => {
                f4_solver_linear_tail_flat(matrix, cols.len(), low_start, &mut word_ops)
            }
        };
        linear_tail = Some((low, low_rank, low_start));
        0
    } else {
        let F4PackedMatrix::Nested(matrix) = &mut matrix else {
            unreachable!("flat matrices are selected only for the linear-tail solver")
        };
        rref_f2_counted(matrix, cols.len(), &mut word_ops)
    };
    let reduce_ns = t_reduce.elapsed().as_nanos();
    charge_word_ops(word_ops);

    let n_vars_out = polys[0].n_vars;
    let t_read = std::time::Instant::now();
    let mut out = Vec::with_capacity(if decisive_only { n_vars + 1 } else { rank });
    if let Some((low, low_rank, low_start)) = linear_tail {
        for row in low.iter().take(low_rank) {
            let mut monos = Vec::new();
            for (word_index, &packed) in row.iter().enumerate() {
                let mut bits = packed;
                while bits != 0 {
                    let bit = bits.trailing_zeros() as usize;
                    bits &= bits - 1;
                    let column = low_start + word_index * 64 + bit;
                    debug_assert!(column < cols.len());
                    monos.push(F2BoolMono::from_mask(cols[column]));
                }
            }
            let poly = F2BoolPoly::from_monos(monos, n_vars_out);
            if is_constant_one(&poly) || forced_assignment(&poly).is_some() {
                out.push(poly);
            }
        }
    } else {
        let F4PackedMatrix::Nested(matrix) = &matrix else {
            unreachable!("flat solver matrices always return a linear tail")
        };
        for row in matrix.iter().take(rank) {
            if decisive_only {
                let mut monos = Vec::with_capacity(3);
                'words: for (word_index, &packed) in row.iter().enumerate() {
                    let mut bits = packed;
                    while bits != 0 {
                        let c = word_index * 64 + bits.trailing_zeros() as usize;
                        debug_assert!(c < cols.len());
                        monos.push(F2BoolMono::from_mask(cols[c]));
                        if monos.len() > 2 {
                            break 'words;
                        }
                        bits &= bits - 1;
                    }
                }
                if monos.len() <= 2 {
                    let poly = F2BoolPoly::from_monos(monos, n_vars_out);
                    if is_constant_one(&poly) || forced_assignment(&poly).is_some() {
                        out.push(poly);
                    }
                }
            } else {
                let monos: Vec<F2BoolMono> = (0..cols.len())
                    .filter(|c| row[c / 64] & (1u64 << (c % 64)) != 0)
                    .map(|c| F2BoolMono::from_mask(cols[c]))
                    .collect();
                if !monos.is_empty() {
                    out.push(F2BoolPoly::from_monos(monos, n_vars_out));
                }
            }
        }
    }
    let readback_ns = t_read.elapsed().as_nanos();
    let matrix_rows = matrix.rows() as u64;
    f4_profile_add(|p| {
        p.calls += 1;
        p.build_ns += build_ns;
        p.reduce_ns += reduce_ns;
        p.readback_ns += readback_ns;
        p.rows += matrix_rows;
        p.cols += cols.len() as u64;
        p.eliminated_rows += matrix_rows;
        p.eliminated_cols += cols.len() as u64;
        p.word_ops += word_ops;
        p.rows_pruned += rows_pruned;
        p.criterion_word_ops += criterion_word_ops;
    });
    Some((out, word_ops))
}

/// Echelonise only the high-degree columns and return the fully reduced
/// linear/constant tail. The tail is exactly the intersection of the row
/// space with those low columns; high pivot rows cannot contribute a vector
/// supported wholly in the tail because their leading columns are distinct.
fn f4_solver_linear_tail(
    matrix: &mut [Vec<u64>],
    n_cols: usize,
    low_start: usize,
    word_ops: &mut u64,
) -> (Vec<Vec<u64>>, usize) {
    let words = n_cols.div_ceil(64);
    let mut pivot_row = 0usize;
    for column in 0..low_start {
        f4_echelon_column(matrix, &mut pivot_row, column, words, word_ops);
        if pivot_row == matrix.len() {
            break;
        }
    }

    f4_linear_tail_from_echelon(matrix, pivot_row, n_cols, low_start, word_ops)
}

fn f4_solver_linear_tail_flat(
    matrix: &mut FlatF2Matrix,
    n_cols: usize,
    low_start: usize,
    word_ops: &mut u64,
) -> (Vec<Vec<u64>>, usize) {
    let words = matrix.words;
    let mut pivot_row = 0usize;
    for column in 0..low_start {
        let (word, bit) = (column / 64, 1u64 << (column % 64));
        let Some(pivot) =
            (pivot_row..matrix.rows).find(|&row| matrix.data[row * words + word] & bit != 0)
        else {
            continue;
        };
        if pivot != pivot_row {
            for index in 0..words {
                matrix
                    .data
                    .swap(pivot_row * words + index, pivot * words + index);
            }
        }
        let split = (pivot_row + 1) * words;
        let (head, tail) = matrix.data.split_at_mut(split);
        let pivot = &head[pivot_row * words..(pivot_row + 1) * words];
        for row in tail.chunks_exact_mut(words) {
            if row[word] & bit != 0 {
                for (target, &source) in row[word..].iter_mut().zip(&pivot[word..]) {
                    *target ^= source;
                }
                *word_ops += (words - word) as u64;
            }
        }
        pivot_row += 1;
        if pivot_row == matrix.rows {
            break;
        }
    }

    let low_width = n_cols - low_start;
    let low_words = low_width.div_ceil(64).max(1);
    let mut low = Vec::with_capacity(matrix.rows - pivot_row);
    for source in matrix.data[pivot_row * words..].chunks_exact(words) {
        let mut row = vec![0u64; low_words];
        for column in low_start..n_cols {
            if source[column / 64] & (1u64 << (column % 64)) != 0 {
                let target = column - low_start;
                row[target / 64] |= 1u64 << (target % 64);
            }
        }
        if row.iter().any(|&word| word != 0) {
            low.push(row);
        }
    }
    let rank = rref_f2_counted(&mut low, low_width, word_ops);
    (low, rank)
}

fn f4_echelon_column(
    matrix: &mut [Vec<u64>],
    pivot_row: &mut usize,
    column: usize,
    words: usize,
    word_ops: &mut u64,
) -> bool {
    let (word, bit) = (column / 64, 1u64 << (column % 64));
    let Some(pivot) = (*pivot_row..matrix.len()).find(|&row| matrix[row][word] & bit != 0) else {
        return false;
    };
    matrix.swap(*pivot_row, pivot);
    let (head, tail) = matrix.split_at_mut(*pivot_row + 1);
    let pivot = &head[*pivot_row];
    for row in tail {
        if row[word] & bit != 0 {
            for (target, &source) in row[word..words].iter_mut().zip(&pivot[word..words]) {
                *target ^= source;
            }
            *word_ops += (words - word) as u64;
        }
    }
    *pivot_row += 1;
    true
}

fn f4_linear_tail_from_echelon(
    matrix: &[Vec<u64>],
    pivot_row: usize,
    n_cols: usize,
    low_start: usize,
    word_ops: &mut u64,
) -> (Vec<Vec<u64>>, usize) {
    let low_width = n_cols - low_start;
    let low_words = low_width.div_ceil(64).max(1);
    let mut low = Vec::with_capacity(matrix.len() - pivot_row);
    for source in &matrix[pivot_row..] {
        let mut row = vec![0u64; low_words];
        for column in low_start..n_cols {
            if source[column / 64] & (1u64 << (column % 64)) != 0 {
                let target = column - low_start;
                row[target / 64] |= 1u64 << (target % 64);
            }
        }
        if row.iter().any(|&word| word != 0) {
            low.push(row);
        }
    }
    let rank = rref_f2_counted(&mut low, low_width, word_ops);
    (low, rank)
}

// ── F4 stage profile ───────────────────────────────────────────────

/// Where the time and the work inside the F4 stage actually go.
///
/// Counters are process-wide and cumulative since the last
/// [`f4_profile_reset`], so a profile covers a parallel run (`ic run
/// --batch N` decomposes on several threads) and not just the thread
/// that asks for it.  A caller that wants a scoped measurement resets
/// first and reads after, with no solving in between.
///
/// The stage is three phases — building the Macaulay matrix, reducing
/// it, and reading the reduced rows back as polynomials — and only the
/// middle one is counted by `word_ops`.  Optimising the stage without
/// knowing the split between them is how a round spends itself on the
/// phase that was never the cost, so the split is measured rather than
/// assumed.  The cost is one relaxed atomic add per nonzero counter per
/// F4 call, plus three `Instant::now()` pairs, all far below the call.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct F4Profile {
    /// Calls to [`matrix_f4_f2_counted`] that built a matrix.
    pub calls: u64,
    /// Calls that returned `None` because the matrix exceeded the caps.
    pub oversize: u64,
    /// Nanoseconds in `build_macaulay`.
    pub build_ns: u128,
    /// Nanoseconds in the row reduction.
    pub reduce_ns: u128,
    /// Nanoseconds turning reduced rows back into polynomials.
    pub readback_ns: u128,
    /// Rows summed over all calls, counted as the reference builder does:
    /// every nonempty product over all `n_vars` variables.
    pub rows: u64,
    /// Columns summed over all calls, in the same reference units.
    pub cols: u64,
    /// Rows the kernel actually eliminated.  Equal to `rows` on the
    /// reference kernel; smaller on [`F4Kernel::Fast`], which does not
    /// build rows shifted by variables the system no longer contains.
    #[serde(default)]
    pub eliminated_rows: u64,
    /// Columns the kernel actually eliminated.
    #[serde(default)]
    pub eliminated_cols: u64,
    /// Nonempty rows the F5 criteria left out of elimination
    /// ([`f4_gf2::KernelOptions::f5`]); they are counted in `rows`.
    #[serde(default)]
    pub f5_skipped: u64,
    /// 64-bit word XORs performed by the reductions — including, under
    /// [`RowCriterion::F5`], the XORs the criterion's lower-degree
    /// echelons performed (`criterion_word_ops`), so this is the step's
    /// whole elimination cost whichever criterion selected the rows.
    pub word_ops: u64,
    /// Rows (multipliers) the F5 criterion removed before building.
    /// Zero under [`RowCriterion::None`].
    #[serde(default)]
    pub rows_pruned: u64,
    /// Word XORs spent evaluating the F5 criterion; a component of
    /// `word_ops`, broken out so the criterion's own cost is visible.
    #[serde(default)]
    pub criterion_word_ops: u64,
    /// Word reads and writes performed by [`SolverEngine::InheritedF4`]'s
    /// specialisations; a component of `word_ops`, broken out because it
    /// is the part of that engine's cost the from-scratch path never pays.
    #[serde(default)]
    pub specialise_word_ops: u64,
}

mod f4_counters {
    use std::sync::atomic::AtomicU64;
    pub(super) static CALLS: AtomicU64 = AtomicU64::new(0);
    pub(super) static OVERSIZE: AtomicU64 = AtomicU64::new(0);
    pub(super) static BUILD_NS: AtomicU64 = AtomicU64::new(0);
    pub(super) static REDUCE_NS: AtomicU64 = AtomicU64::new(0);
    pub(super) static READBACK_NS: AtomicU64 = AtomicU64::new(0);
    pub(super) static ROWS: AtomicU64 = AtomicU64::new(0);
    pub(super) static COLS: AtomicU64 = AtomicU64::new(0);
    pub(super) static ELIMINATED_ROWS: AtomicU64 = AtomicU64::new(0);
    pub(super) static ELIMINATED_COLS: AtomicU64 = AtomicU64::new(0);
    pub(super) static F5_SKIPPED: AtomicU64 = AtomicU64::new(0);
    pub(super) static WORD_OPS: AtomicU64 = AtomicU64::new(0);
    pub(super) static ROWS_PRUNED: AtomicU64 = AtomicU64::new(0);
    pub(super) static CRITERION_WORD_OPS: AtomicU64 = AtomicU64::new(0);
    pub(super) static SPECIALISE_WORD_OPS: AtomicU64 = AtomicU64::new(0);

    pub(super) fn all() -> [&'static AtomicU64; 14] {
        [
            &CALLS,
            &OVERSIZE,
            &BUILD_NS,
            &REDUCE_NS,
            &READBACK_NS,
            &ROWS,
            &COLS,
            &ELIMINATED_ROWS,
            &ELIMINATED_COLS,
            &F5_SKIPPED,
            &WORD_OPS,
            &ROWS_PRUNED,
            &CRITERION_WORD_OPS,
            &SPECIALISE_WORD_OPS,
        ]
    }
}

/// The F4 stage profile since the last [`f4_profile_reset`].
pub fn f4_profile() -> F4Profile {
    use std::sync::atomic::Ordering::Relaxed;
    F4Profile {
        calls: f4_counters::CALLS.load(Relaxed),
        oversize: f4_counters::OVERSIZE.load(Relaxed),
        build_ns: f4_counters::BUILD_NS.load(Relaxed) as u128,
        reduce_ns: f4_counters::REDUCE_NS.load(Relaxed) as u128,
        readback_ns: f4_counters::READBACK_NS.load(Relaxed) as u128,
        rows: f4_counters::ROWS.load(Relaxed),
        cols: f4_counters::COLS.load(Relaxed),
        eliminated_rows: f4_counters::ELIMINATED_ROWS.load(Relaxed),
        eliminated_cols: f4_counters::ELIMINATED_COLS.load(Relaxed),
        f5_skipped: f4_counters::F5_SKIPPED.load(Relaxed),
        word_ops: f4_counters::WORD_OPS.load(Relaxed),
        rows_pruned: f4_counters::ROWS_PRUNED.load(Relaxed),
        criterion_word_ops: f4_counters::CRITERION_WORD_OPS.load(Relaxed),
        specialise_word_ops: f4_counters::SPECIALISE_WORD_OPS.load(Relaxed),
    }
}

/// Clear the F4 stage profile.  Not synchronised against concurrent
/// solving: reset before the work, read after it.
pub fn f4_profile_reset() {
    for counter in f4_counters::all() {
        counter.store(0, std::sync::atomic::Ordering::Relaxed);
    }
}

fn f4_profile_add(f: impl FnOnce(&mut F4Profile)) {
    use std::sync::atomic::Ordering::Relaxed;
    let mut delta = F4Profile::default();
    f(&mut delta);
    let pairs: [(&std::sync::atomic::AtomicU64, u64); 14] = [
        (&f4_counters::CALLS, delta.calls),
        (&f4_counters::OVERSIZE, delta.oversize),
        (&f4_counters::BUILD_NS, delta.build_ns as u64),
        (&f4_counters::REDUCE_NS, delta.reduce_ns as u64),
        (&f4_counters::READBACK_NS, delta.readback_ns as u64),
        (&f4_counters::ROWS, delta.rows),
        (&f4_counters::COLS, delta.cols),
        (&f4_counters::ELIMINATED_ROWS, delta.eliminated_rows),
        (&f4_counters::ELIMINATED_COLS, delta.eliminated_cols),
        (&f4_counters::F5_SKIPPED, delta.f5_skipped),
        (&f4_counters::WORD_OPS, delta.word_ops),
        (&f4_counters::ROWS_PRUNED, delta.rows_pruned),
        (&f4_counters::CRITERION_WORD_OPS, delta.criterion_word_ops),
        (&f4_counters::SPECIALISE_WORD_OPS, delta.specialise_word_ops),
    ];
    for (counter, delta) in pairs {
        if delta != 0 {
            counter.fetch_add(delta, Relaxed);
        }
    }
}

/// The Macaulay rows of `polys` at `degree`, as monomial masks: every
/// product `p · m` with `deg(p·m) ≤ degree`, each row the set of
/// monomials occurring in it.  Columns are not assigned here — see
/// [`macaulay_columns`].  `None` if the row count would exceed the size
/// limits.
///
/// Shared by the dense [`build_macaulay`] and the sparse
/// [`build_macaulay_sparse`] so the two cannot drift: any difference
/// between the dense and sparse solving-degree paths would otherwise be
/// indistinguishable from a difference in the matrix they were handed.
pub(crate) fn macaulay_rows_monos(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
) -> Option<Vec<Vec<u64>>> {
    macaulay_rows_monos_with_mask(polys, n_vars, degree, all_variable_mask(n_vars), None)
}

/// The Macaulay rows at `degree` with the F5 criterion applied: every
/// product `t · f_i` the criterion does not prune.  The row space is the
/// same as [`macaulay_rows_monos`]'s; see
/// [`crate::cryptanalysis::matrix_f5_f2`] for the argument.
pub(crate) fn f5_rows_monos_with_mask(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    multiplier_mask: u64,
    criterion: &F5Criterion,
) -> Option<Vec<Vec<u64>>> {
    macaulay_rows_monos_with_mask(polys, n_vars, degree, multiplier_mask, Some(criterion))
}

/// Pack monomial rows as bit-rows over `cols` (descending monomial order).
pub(crate) fn pack_rows(rows_monos: &[Vec<u64>], cols: &[u64]) -> Vec<Vec<u64>> {
    let index: crate::cryptanalysis::fx_hash::MaskMap<usize> =
        cols.iter().enumerate().map(|(i, m)| (*m, i)).collect();
    let words = cols.len().div_ceil(64).max(1);
    let pack = |monos: &Vec<u64>| {
        let mut row = vec![0u64; words];
        for m in monos {
            let c = index[m];
            row[c / 64] |= 1u64 << (c % 64);
        }
        row
    };
    if rows_monos.len() * words >= M4RI_PARALLEL_WORDS {
        use rayon::prelude::*;
        rows_monos.par_iter().map(pack).collect()
    } else {
        rows_monos.iter().map(pack).collect()
    }
}

pub(crate) fn macaulay_rows_monos_with_mask(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    multiplier_mask: u64,
    criterion: Option<&F5Criterion>,
) -> Option<Vec<Vec<u64>>> {
    let mut rows_monos: Vec<Vec<u64>> = Vec::new();
    visit_macaulay_rows(polys, n_vars, degree, multiplier_mask, criterion, |row| {
        rows_monos.push(row.to_vec())
    })?;
    Some(rows_monos)
}

/// [`macaulay_rows_monos`] with an explicit row cap.
#[cfg(test)]
fn macaulay_rows_monos_capped(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    max_rows: usize,
) -> Option<Vec<Vec<u64>>> {
    let mut rows_monos: Vec<Vec<u64>> = Vec::new();
    visit_macaulay_rows_capped(
        polys,
        n_vars,
        degree,
        all_variable_mask(n_vars),
        None,
        max_rows,
        |row| rows_monos.push(row.to_vec()),
    )?;
    Some(rows_monos)
}

/// The number of rows [`macaulay_rows_monos`] would return, without
/// materialising them: `None` exactly when it would be `None`.
pub(crate) fn macaulay_row_count(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
) -> Option<usize> {
    visit_macaulay_rows(
        polys,
        n_vars,
        degree,
        all_variable_mask(n_vars),
        None,
        |_| {},
    )
}

/// Hand every non-empty Macaulay row (ascending monomial masks, odd
/// multiplicities kept) to `visit`, in generator-then-multiplier order;
/// returns the row count, or `None` once it exceeds the size limits.
fn visit_macaulay_rows(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    multiplier_mask: u64,
    criterion: Option<&F5Criterion>,
    visit: impl FnMut(&[u64]),
) -> Option<usize> {
    // Read once per build, not once per row: the cap is an environment
    // lookup, and the loop below runs once per Macaulay row.
    let row_cap = max_f4_rows();
    visit_macaulay_rows_capped(
        polys,
        n_vars,
        degree,
        multiplier_mask,
        criterion,
        row_cap,
        visit,
    )
}

/// [`visit_macaulay_rows`] with an explicit row cap.
fn visit_macaulay_rows_capped(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    multiplier_mask: u64,
    criterion: Option<&F5Criterion>,
    row_cap: usize,
    mut visit: impl FnMut(&[u64]),
) -> Option<usize> {
    let mut count = 0usize;
    let mut schedules: Vec<Option<std::rc::Rc<[u64]>>> = vec![None; degree as usize + 1];
    let mut all: Vec<u64> = Vec::new();
    let mut row: Vec<u64> = Vec::new();
    for (i, p) in polys.iter().enumerate() {
        let pdeg = p
            .terms
            .iter()
            .map(|t| t.mask.count_ones())
            .max()
            .unwrap_or(0);
        if pdeg > degree {
            continue;
        }
        let gap = (degree - pdeg) as usize;
        let multipliers = schedules[gap].get_or_insert_with(|| {
            if multiplier_mask == all_variable_mask(n_vars) {
                monomials_up_to_mask(multiplier_mask, gap as u32).into()
            } else {
                cached_monomials_up_to_mask(multiplier_mask, gap as u32)
            }
        });
        for &mult in multipliers.iter() {
            if criterion.is_some_and(|c| c.prunes(i, mult)) {
                continue;
            }
            // Multiplying by a monomial is a union of masks, so two
            // distinct terms of `p` can collide — and collide means
            // cancel, in characteristic 2.  Keep the odd multiplicities.
            all.clear();
            all.extend(p.terms.iter().map(|t| t.mask | mult));
            all.sort_unstable();
            row.clear();
            let mut i = 0;
            while i < all.len() {
                let mut j = i;
                while j < all.len() && all[j] == all[i] {
                    j += 1;
                }
                if (j - i) % 2 == 1 {
                    row.push(all[i]);
                }
                i = j;
            }
            if !row.is_empty() {
                visit(&row);
                count += 1;
            }
            if count > row_cap {
                return None;
            }
        }
    }
    Some(count)
}

/// Column masks of the Macaulay matrix at `degree`, in descending
/// monomial order.
///
/// Because [`cmp_mono`] orders by total degree first, descending order
/// puts the **highest-degree monomials in the leading columns** and the
/// constant monomial last.  Both elimination paths depend on that: it is
/// what makes "leading column index ≥ the degree-≤1 boundary" equivalent
/// to "this row is a linear consequence".
pub(crate) fn macaulay_columns(rows_monos: &[Vec<u64>]) -> Option<Vec<u64>> {
    macaulay_columns_capped(rows_monos, max_f4_cols())
}

/// [`macaulay_columns`] with an explicit column cap.
fn macaulay_columns_capped(rows_monos: &[Vec<u64>], max_cols: usize) -> Option<Vec<u64>> {
    let mut cols: Vec<u64> = rows_monos.iter().flatten().copied().collect();
    cols.sort_unstable();
    cols.dedup();
    if cols.len() > max_cols {
        return None;
    }
    // `mono_key` orders exactly as `cmp_mono`; the masks are distinct
    cols.sort_unstable_by_key(|&m| std::cmp::Reverse(mono_key(F2BoolMono::from_mask(m))));
    Some(cols)
}

/// Sparse Macaulay matrix: column masks, plus one ascending list of
/// column indices per row.
///
/// A row is one polynomial times one monomial, so it carries exactly as
/// many nonzeros as that polynomial has terms — a handful, against tens
/// of thousands of columns.  The dense form spends a kilobyte per row
/// representing twenty bits.
pub(crate) fn build_macaulay_sparse(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
) -> Option<(Vec<u64>, Vec<Vec<u32>>)> {
    let rows_monos = macaulay_rows_monos(polys, n_vars, degree)?;
    if rows_monos.is_empty() {
        return Some((Vec::new(), Vec::new()));
    }
    let cols = macaulay_columns(&rows_monos)?;
    let index: std::collections::HashMap<u64, u32> = cols
        .iter()
        .enumerate()
        .map(|(i, m)| (*m, i as u32))
        .collect();
    let rows: Vec<Vec<u32>> = rows_monos
        .iter()
        .map(|monos| {
            let mut r: Vec<u32> = monos.iter().map(|m| index[m]).collect();
            r.sort_unstable();
            r
        })
        .collect();
    Some((cols, rows))
}

/// Build the dense Macaulay matrix: every product `p · m` with
/// `deg(p·m) ≤ degree`, as bit-rows over the monomials that occur.
///
/// Returns the column monomials (DegRevLex descending) and the rows.
/// `None` if the matrix would exceed the size limits.  For the sparse
/// form of the same matrix see [`build_macaulay_sparse`].
pub(crate) fn build_macaulay(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
) -> Option<(Vec<u64>, Vec<Vec<u64>>)> {
    build_macaulay_with_multiplier_mask(
        polys,
        n_vars,
        degree,
        all_variable_mask(n_vars),
        false,
        RowCriterion::None,
    )
    .map(|built| (built.columns, built.matrix))
}

/// Build an inherited-F4 root with exact column-layout reuse.  A cached
/// layout is accepted only when packing observes every cached column and no
/// product falls outside it; otherwise the ordinary support build replaces
/// the cache entry. The default applies to quadratic generators, whose root
/// support repeats across targets; `KIC_F4_INHERIT_LAYOUT_CACHE=0|1` disables
/// or forces it as a same-binary control, and
/// `KIC_F4_DISABLE_INHERIT_FUSED_PACK=1` retains materialized sparse rows on
/// layout hits.
pub(crate) fn build_inherited_macaulay(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    multiplier_mask: u64,
    quadratic_generators: bool,
) -> Option<(Vec<u64>, Vec<Vec<u64>>)> {
    static REUSE_LAYOUT: std::sync::OnceLock<Option<bool>> = std::sync::OnceLock::new();
    let override_policy = *REUSE_LAYOUT.get_or_init(|| {
        match std::env::var("KIC_F4_INHERIT_LAYOUT_CACHE").as_deref() {
            Ok("0") => Some(false),
            Ok("1") => Some(true),
            _ => None,
        }
    });
    let reuse_layout = override_policy.unwrap_or(quadratic_generators);
    build_inherited_macaulay_with_layout(polys, n_vars, degree, multiplier_mask, reuse_layout)
}

/// [`build_inherited_macaulay`] with **support-local multipliers**: each
/// generator `f` is multiplied only by the monomials of degree at most
/// `degree − deg f` in the variables of `multiplier_mask ∩ supp(f)`.  Where
/// every generator's support already contains `multiplier_mask` — a
/// quadratic system in all its unknowns — the rows are exactly
/// [`build_inherited_macaulay`]'s and that path, with its layout cache, is
/// taken, so such a root is built identically.
pub(crate) fn build_inherited_macaulay_support_local(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    multiplier_mask: u64,
    quadratic_generators: bool,
) -> Option<(Vec<u64>, Vec<Vec<u64>>)> {
    let support = |p: &F2BoolPoly| p.terms.iter().fold(0u64, |acc, t| acc | t.mask);
    if polys.iter().all(|p| multiplier_mask & !support(p) == 0) {
        return build_inherited_macaulay(
            polys,
            n_vars,
            degree,
            multiplier_mask,
            quadratic_generators,
        );
    }
    let mut rows_monos: Vec<Vec<u64>> = Vec::new();
    for p in polys {
        let rows = macaulay_rows_monos_with_mask(
            std::slice::from_ref(p),
            n_vars,
            degree,
            multiplier_mask & support(p),
            None,
        )?;
        rows_monos.extend(rows);
        if rows_monos.len() > max_f4_rows() {
            return None;
        }
    }
    if rows_monos.is_empty() {
        return Some((Vec::new(), Vec::new()));
    }
    let columns = macaulay_columns(&rows_monos)?;
    let matrix = pack_rows(&rows_monos, &columns);
    Some((columns, matrix))
}

fn build_inherited_macaulay_with_layout(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    multiplier_mask: u64,
    reuse_layout: bool,
) -> Option<(Vec<u64>, Vec<Vec<u64>>)> {
    static FUSED_PACK: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    let fused = reuse_layout
        && *FUSED_PACK.get_or_init(|| {
            std::env::var("KIC_F4_DISABLE_INHERIT_FUSED_PACK").as_deref() != Ok("1")
        });
    if fused {
        let layout_key = (multiplier_mask, degree, false);
        let cached = cached_f4_layout(layout_key);
        if let Some(layout) = cached {
            if let Some(matrix) =
                pack_polynomials_nested_fused(polys, n_vars, degree, multiplier_mask, &layout)
            {
                F4_LAYOUT_HITS.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                return Some((layout.columns.clone(), matrix));
            }
            F4_LAYOUTS.with(|layouts| {
                layouts.borrow_mut().remove(&layout_key);
            });
        }
    }
    build_macaulay_with_multiplier_mask(
        polys,
        n_vars,
        degree,
        multiplier_mask,
        reuse_layout,
        RowCriterion::None,
    )
    .map(|built| (built.columns, built.matrix))
}

/// Which rows of the Macaulay matrix a step builds.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RowCriterion {
    /// Every product `t · f_i` with `deg(t · f_i) ≤ degree` — plain F4.
    None,
    /// Products the F5 criterion does not predict to reduce to zero
    /// ([`crate::cryptanalysis::matrix_f5_f2`]).  Same row space.
    F5,
}

impl RowCriterion {
    /// The criterion the `KIC_F4_CRITERION` environment variable selects
    /// (`f5` or `none`), or `default` when it is unset.
    fn from_env_or(default: Self) -> Self {
        match std::env::var("KIC_F4_CRITERION").as_deref() {
            Ok("f5") => Self::F5,
            Ok("none") => Self::None,
            _ => default,
        }
    }
}

/// A packed Macaulay matrix together with what selecting its rows cost.
struct BuiltMacaulay<P> {
    columns: Vec<u64>,
    matrix: P,
    /// Rows the F5 criterion removed (0 under [`RowCriterion::None`]).
    rows_pruned: u64,
    /// Word XORs the criterion spent on its lower-degree echelons.
    criterion_word_ops: u64,
}

fn pack_rows_with_layout(
    rows_monos: &[Vec<u64>],
    layout: &F4ColumnLayout,
    verify_exact_support: bool,
) -> Option<Vec<Vec<u64>>> {
    let words = layout.columns.len().div_ceil(64);
    let mut seen = verify_exact_support.then(|| vec![false; layout.columns.len()]);
    let mut matrix = Vec::with_capacity(rows_monos.len());
    for monos in rows_monos {
        let mut row = vec![0u64; words];
        for monomial in monos {
            let &column = layout.index.get(monomial)?;
            row[column / 64] |= 1 << (column % 64);
            if let Some(seen) = &mut seen {
                seen[column] = true;
            }
        }
        matrix.push(row);
    }
    if seen
        .as_ref()
        .is_some_and(|seen| seen.iter().any(|present| !present))
    {
        return None;
    }
    Some(matrix)
}

#[derive(Default)]
struct FlatF2Matrix {
    data: Vec<u64>,
    rows: usize,
    words: usize,
}

fn pack_rows_flat_with_layout(
    rows_monos: &[Vec<u64>],
    layout: &F4ColumnLayout,
    verify_exact_support: bool,
) -> Option<FlatF2Matrix> {
    let words = layout.columns.len().div_ceil(64);
    let mut seen = verify_exact_support.then(|| vec![false; layout.columns.len()]);
    let mut data = vec![0u64; rows_monos.len() * words];
    for (row_index, monos) in rows_monos.iter().enumerate() {
        let row = &mut data[row_index * words..(row_index + 1) * words];
        for monomial in monos {
            let &column = layout.index.get(monomial)?;
            row[column / 64] |= 1 << (column % 64);
            if let Some(seen) = &mut seen {
                seen[column] = true;
            }
        }
    }
    if seen
        .as_ref()
        .is_some_and(|seen| seen.iter().any(|present| !present))
    {
        return None;
    }
    Some(FlatF2Matrix {
        data,
        rows: rows_monos.len(),
        words,
    })
}

fn pack_polynomials_flat_fused(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    multiplier_mask: u64,
    layout: &F4ColumnLayout,
) -> Option<FlatF2Matrix> {
    let words = layout.columns.len().div_ceil(64);
    let mut schedules: Vec<Option<std::rc::Rc<[u64]>>> = vec![None; degree as usize + 1];
    let mut gaps = Vec::with_capacity(polys.len());
    let mut estimated_rows = 0usize;
    for polynomial in polys {
        let polynomial_degree = polynomial
            .terms
            .iter()
            .map(|term| term.mask.count_ones())
            .max()
            .unwrap_or(0);
        if polynomial_degree > degree {
            gaps.push(None);
            continue;
        }
        let gap = (degree - polynomial_degree) as usize;
        let multipliers = schedules[gap].get_or_insert_with(|| {
            if multiplier_mask == all_variable_mask(n_vars) {
                monomials_up_to_mask(multiplier_mask, gap as u32).into()
            } else {
                cached_monomials_up_to_mask(multiplier_mask, gap as u32)
            }
        });
        estimated_rows = estimated_rows.saturating_add(multipliers.len());
        gaps.push(Some(gap));
    }
    let mut seen = vec![false; layout.columns.len()];
    let row_cap = max_f4_rows();
    let mut data = Vec::with_capacity(estimated_rows.min(row_cap) * words);
    let mut rows = 0usize;
    for (polynomial, gap) in polys.iter().zip(gaps) {
        let Some(gap) = gap else {
            continue;
        };
        let multipliers = schedules[gap].as_ref().unwrap();
        let mut product = Vec::with_capacity(polynomial.terms.len());
        for &multiplier in multipliers.iter() {
            product.clear();
            product.extend(polynomial.terms.iter().map(|term| term.mask | multiplier));
            product.sort_unstable();
            let mut read = 0usize;
            let mut write = 0usize;
            while read < product.len() {
                let mut end = read + 1;
                while end < product.len() && product[end] == product[read] {
                    end += 1;
                }
                if (end - read) % 2 == 1 {
                    product[write] = product[read];
                    write += 1;
                }
                read = end;
            }
            if write == 0 {
                continue;
            }
            if rows == row_cap {
                return None;
            }
            let start = data.len();
            data.resize(start + words, 0);
            let row = &mut data[start..start + words];
            for monomial in &product[..write] {
                let &column = layout.index.get(monomial)?;
                row[column / 64] |= 1 << (column % 64);
                seen[column] = true;
            }
            rows += 1;
        }
    }
    if seen.iter().any(|present| !present) {
        return None;
    }
    Some(FlatF2Matrix { data, rows, words })
}

fn pack_polynomials_nested_fused(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    multiplier_mask: u64,
    layout: &F4ColumnLayout,
) -> Option<Vec<Vec<u64>>> {
    let words = layout.columns.len().div_ceil(64);
    let mut schedules: Vec<Option<std::rc::Rc<[u64]>>> = vec![None; degree as usize + 1];
    let mut gaps = Vec::with_capacity(polys.len());
    let mut estimated_rows = 0usize;
    for polynomial in polys {
        let polynomial_degree = polynomial
            .terms
            .iter()
            .map(|term| term.mask.count_ones())
            .max()
            .unwrap_or(0);
        if polynomial_degree > degree {
            gaps.push(None);
            continue;
        }
        let gap = (degree - polynomial_degree) as usize;
        let multipliers = schedules[gap].get_or_insert_with(|| {
            if multiplier_mask == all_variable_mask(n_vars) {
                monomials_up_to_mask(multiplier_mask, gap as u32).into()
            } else {
                cached_monomials_up_to_mask(multiplier_mask, gap as u32)
            }
        });
        estimated_rows = estimated_rows.saturating_add(multipliers.len());
        gaps.push(Some(gap));
    }
    let mut seen = vec![false; layout.columns.len()];
    let row_cap = max_f4_rows();
    let mut matrix = Vec::with_capacity(estimated_rows.min(row_cap));
    let max_terms = polys
        .iter()
        .map(|polynomial| polynomial.terms.len())
        .max()
        .unwrap_or(0);
    let mut product = Vec::with_capacity(max_terms);
    for (polynomial, gap) in polys.iter().zip(gaps) {
        let Some(gap) = gap else {
            continue;
        };
        let multipliers = schedules[gap].as_ref().unwrap();
        for &multiplier in multipliers.iter() {
            product.clear();
            product.extend(polynomial.terms.iter().map(|term| term.mask | multiplier));
            product.sort_unstable();
            let mut read = 0usize;
            let mut write = 0usize;
            while read < product.len() {
                let mut end = read + 1;
                while end < product.len() && product[end] == product[read] {
                    end += 1;
                }
                if (end - read) % 2 == 1 {
                    product[write] = product[read];
                    write += 1;
                }
                read = end;
            }
            if write == 0 {
                continue;
            }
            if matrix.len() == row_cap {
                return None;
            }
            let mut row = vec![0u64; words];
            for monomial in &product[..write] {
                let &column = layout.index.get(monomial)?;
                row[column / 64] |= 1 << (column % 64);
                seen[column] = true;
            }
            matrix.push(row);
        }
    }
    if seen.iter().any(|present| !present) {
        return None;
    }
    Some(matrix)
}

fn build_macaulay_with_multiplier_mask(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    multiplier_mask: u64,
    reuse_layout: bool,
    criterion: RowCriterion,
) -> Option<BuiltMacaulay<Vec<Vec<u64>>>> {
    build_macaulay_packed(
        polys,
        n_vars,
        degree,
        multiplier_mask,
        reuse_layout,
        criterion,
        pack_rows_with_layout,
    )
}

fn build_macaulay_flat_with_multiplier_mask(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    multiplier_mask: u64,
    reuse_layout: bool,
    criterion: RowCriterion,
) -> Option<BuiltMacaulay<FlatF2Matrix>> {
    // The fused packer builds every product straight into the cached
    // layout, so it applies only to the plain row set: the F5 criterion
    // selects rows through `build_macaulay_packed` and must go that way.
    let fused = reuse_layout
        && criterion == RowCriterion::None
        && std::env::var("KIC_F4_DISABLE_FUSED_PACK").as_deref() != Ok("1");
    if fused {
        let layout_key = (multiplier_mask, degree, false);
        let cached = cached_f4_layout(layout_key);
        if let Some(layout) = cached {
            if let Some(matrix) =
                pack_polynomials_flat_fused(polys, n_vars, degree, multiplier_mask, &layout)
            {
                F4_LAYOUT_HITS.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                return Some(BuiltMacaulay {
                    columns: layout.columns.clone(),
                    matrix,
                    rows_pruned: 0,
                    criterion_word_ops: 0,
                });
            }
            F4_LAYOUTS.with(|layouts| {
                layouts.borrow_mut().remove(&layout_key);
            });
        }
    }
    build_macaulay_packed(
        polys,
        n_vars,
        degree,
        multiplier_mask,
        reuse_layout,
        criterion,
        pack_rows_flat_with_layout,
    )
}

fn build_macaulay_packed<P: Default>(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    multiplier_mask: u64,
    reuse_layout: bool,
    criterion: RowCriterion,
    pack: impl Fn(&[Vec<u64>], &F4ColumnLayout, bool) -> Option<P>,
) -> Option<BuiltMacaulay<P>> {
    let subprofile = std::env::var("KIC_F4_BUILD_SUBPROFILE").as_deref() == Ok("1");
    let rows_started = subprofile.then(std::time::Instant::now);
    let f5 = match criterion {
        RowCriterion::None => None,
        RowCriterion::F5 => Some(F5Criterion::new(polys, n_vars, degree, multiplier_mask)),
    };
    // Pruned *multipliers*: a pruned product that would have been the
    // empty row (possible in the Boolean ring, rare) is counted too, since
    // deciding that would cost the row construction the criterion saves.
    let (rows_pruned, criterion_word_ops) = f5
        .as_ref()
        .map(|c| (c.pruned_count(), c.word_ops()))
        .unwrap_or((0, 0));
    let rows_monos =
        macaulay_rows_monos_with_mask(polys, n_vars, degree, multiplier_mask, f5.as_ref())?;
    if let Some(started) = rows_started {
        F4_BUILD_ROWS_NS.fetch_add(
            started.elapsed().as_nanos() as u64,
            std::sync::atomic::Ordering::Relaxed,
        );
    }
    let finish = |columns: Vec<u64>, matrix: P| BuiltMacaulay {
        columns,
        matrix,
        rows_pruned,
        criterion_word_ops,
    };
    if rows_monos.is_empty() {
        return Some(finish(Vec::new(), P::default()));
    }
    let pack_started = subprofile.then(std::time::Instant::now);

    let layout_key = (multiplier_mask, degree, criterion == RowCriterion::F5);
    if reuse_layout {
        let cached = cached_f4_layout(layout_key);
        if let Some(layout) = cached {
            if let Some(matrix) = pack(&rows_monos, &layout, true) {
                F4_LAYOUT_HITS.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                if let Some(started) = pack_started {
                    F4_BUILD_PACK_NS.fetch_add(
                        started.elapsed().as_nanos() as u64,
                        std::sync::atomic::Ordering::Relaxed,
                    );
                }
                return Some(finish(layout.columns.clone(), matrix));
            }
        }
        F4_LAYOUT_MISSES.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
    }

    let cols: Vec<u64> = macaulay_columns(&rows_monos)?;
    let layout = std::rc::Rc::new(F4ColumnLayout::new(cols));
    let matrix = pack(&rows_monos, &layout, false)?;
    if reuse_layout {
        F4_LAYOUTS.with(|layouts| {
            let mut layouts = layouts.borrow_mut();
            let retained_columns: usize = layouts.values().map(|layout| layout.columns.len()).sum();
            if layouts.len() >= 128
                || retained_columns.saturating_add(layout.columns.len()) > 200_000
            {
                layouts.clear();
            }
            layouts.insert(layout_key, layout.clone());
        });
    }
    if let Some(started) = pack_started {
        F4_BUILD_PACK_NS.fetch_add(
            started.elapsed().as_nanos() as u64,
            std::sync::atomic::Ordering::Relaxed,
        );
    }
    Some(finish(layout.columns.clone(), matrix))
}

/// Reduced row echelon form over `F_2`; returns the rank, with the
/// pivot rows moved to the front of `matrix`.
/// Process-wide total of 64-bit word XORs performed by every Boolean
/// Macaulay reduction, counted or not.  It exists so a caller that
/// drives a whole splitting solve through [`solve_boolean_system`] —
/// which reduces at every node without returning a count — can still
/// price the solve exactly: read it before and after.
pub static F4_WORD_OPS_TOTAL: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);

static F4_LAYOUT_HITS: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
static F4_LAYOUT_MISSES: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
static F4_BUILD_ROWS_NS: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
static F4_BUILD_PACK_NS: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
struct F4ColumnLayout {
    columns: Vec<u64>,
    index: F4ColumnIndex,
}

impl F4ColumnLayout {
    fn new(columns: Vec<u64>) -> Self {
        let index = if std::env::var("KIC_F4_STD_COLUMN_HASH").as_deref() == Ok("1") {
            F4ColumnIndex::Standard(
                columns
                    .iter()
                    .enumerate()
                    .map(|(column, &monomial)| (monomial, column))
                    .collect(),
            )
        } else {
            let mut index = FastColumnMap::with_capacity_and_hasher(
                columns.len(),
                std::hash::BuildHasherDefault::default(),
            );
            index.extend(
                columns
                    .iter()
                    .enumerate()
                    .map(|(column, &monomial)| (monomial, column)),
            );
            F4ColumnIndex::Fast(index)
        };
        Self { columns, index }
    }
}

enum F4ColumnIndex {
    Standard(std::collections::HashMap<u64, usize>),
    Fast(FastColumnMap),
}

impl F4ColumnIndex {
    fn get(&self, monomial: &u64) -> Option<&usize> {
        match self {
            Self::Standard(index) => index.get(monomial),
            Self::Fast(index) => index.get(monomial),
        }
    }
}

type FastColumnMap = crate::cryptanalysis::fx_hash::MaskMap<usize>;
thread_local! {
    /// Keyed by multiplier mask, degree and whether the F5 criterion
    /// selected the rows: pruning changes which monomials occur.
    static F4_LAYOUTS: std::cell::RefCell<std::collections::HashMap<
        (u64, u32, bool),
        std::rc::Rc<F4ColumnLayout>,
    >> = std::cell::RefCell::new(std::collections::HashMap::new());
}

/// A cached layout must obey the current column cap just like a fresh one.
/// Reject only the cache entry: a changed system may have smaller support
/// that the ordinary builder can still accept under the new cap.
fn cached_f4_layout(key: (u64, u32, bool)) -> Option<std::rc::Rc<F4ColumnLayout>> {
    let column_cap = max_f4_cols();
    F4_LAYOUTS.with(|layouts| {
        layouts
            .borrow()
            .get(&key)
            .filter(|layout| layout.columns.len() <= column_cap)
            .cloned()
    })
}

/// Exact column-layout reuse counts since the last reset.
pub fn f4_layout_stats() -> (u64, u64) {
    use std::sync::atomic::Ordering::Relaxed;
    (F4_LAYOUT_HITS.load(Relaxed), F4_LAYOUT_MISSES.load(Relaxed))
}

pub fn f4_layout_stats_reset() {
    use std::sync::atomic::Ordering::Relaxed;
    F4_LAYOUT_HITS.store(0, Relaxed);
    F4_LAYOUT_MISSES.store(0, Relaxed);
    F4_LAYOUTS.with(|layouts| layouts.borrow_mut().clear());
}

pub fn f4_build_subprofile() -> (u64, u64) {
    use std::sync::atomic::Ordering::Relaxed;
    (
        F4_BUILD_ROWS_NS.load(Relaxed),
        F4_BUILD_PACK_NS.load(Relaxed),
    )
}

pub fn f4_build_subprofile_reset() {
    use std::sync::atomic::Ordering::Relaxed;
    F4_BUILD_ROWS_NS.store(0, Relaxed);
    F4_BUILD_PACK_NS.store(0, Relaxed);
}

/// The current value of [`F4_WORD_OPS_TOTAL`].
pub fn f4_word_ops_total() -> u64 {
    F4_WORD_OPS_TOTAL.load(std::sync::atomic::Ordering::Relaxed)
}

thread_local! {
    static F4_WORD_OPS_THREAD: std::cell::Cell<u64> = const { std::cell::Cell::new(0) };
}

/// Charge `word_ops` to the process-wide total and to the calling
/// thread's own total.
fn charge_word_ops(word_ops: u64) {
    F4_WORD_OPS_TOTAL.fetch_add(word_ops, std::sync::atomic::Ordering::Relaxed);
    F4_WORD_OPS_THREAD.with(|c| c.set(c.get().wrapping_add(word_ops)));
}

/// Word operations charged by Boolean Macaulay reductions **on the calling
/// thread** since it started.  The process-wide counters serve a run that
/// solves on several threads; this one serves a scoped measurement — read
/// before and after — that must not see other threads' work, such as a
/// test binary running its cases in parallel.
pub fn f4_word_ops_thread() -> u64 {
    F4_WORD_OPS_THREAD.with(|c| c.get())
}

/// Word XORs the F4 reductions on the calling thread have performed so far
/// — the same counter as [`f4_word_ops_thread`], under the name the suite
/// introduced for it.
///
/// Unlike [`f4_profile`], no other thread's solving reaches it, so a caller
/// that solves on its own thread — `groebner_decompose` does — can price
/// exactly its own work while the rest of the process keeps solving.
pub fn f4_thread_word_ops() -> u64 {
    f4_word_ops_thread()
}

pub(crate) fn rref_f2(matrix: &mut [Vec<u64>], n_cols: usize) -> usize {
    let mut count = 0u64;
    let rank = rref_f2_counted(matrix, n_cols, &mut count);
    charge_word_ops(count);
    rank
}

/// [`rref_f2`], accumulating the 64-bit word XORs it performs into
/// `word_ops`.
fn rref_f2_suffix_counted(matrix: &mut [Vec<u64>], n_cols: usize, word_ops: &mut u64) -> usize {
    echelon_f2_suffix_counted(matrix, n_cols, word_ops, true)
}

/// Column-at-a-time elimination.  With `reduce_above` the result is the
/// reduced row echelon form; without it, rows already holding a pivot are
/// left alone and the result is a row echelon form — distinct leading
/// columns, no back-substitution — at roughly half the XORs.
fn echelon_f2_suffix_counted(
    matrix: &mut [Vec<u64>],
    n_cols: usize,
    word_ops: &mut u64,
    reduce_above: bool,
) -> usize {
    let words = n_cols.div_ceil(64);
    let mut pivot_row = 0usize;
    for c in 0..n_cols {
        let (w, bit) = (c / 64, 1u64 << (c % 64));
        let piv = (pivot_row..matrix.len()).find(|&r| matrix[r][w] & bit != 0);
        let piv = match piv {
            Some(p) => p,
            None => continue,
        };
        matrix.swap(pivot_row, piv);
        // Earlier columns of this pivot row are zero: previous pivots
        // eliminated them, and skipped columns were zero in all remaining
        // rows. Whole words before w therefore need no XOR. Separating the
        // pivot borrow also lets LLVM vectorize the contiguous suffix.
        let (before, rest) = matrix.split_at_mut(pivot_row);
        let (pivot, after) = rest.split_first_mut().unwrap();
        let above = if reduce_above { before.len() } else { 0 };
        for row in before[..above].iter_mut().chain(after.iter_mut()) {
            if row[w] & bit != 0 {
                for (dst, &src) in row[w..words].iter_mut().zip(&pivot[w..words]) {
                    *dst ^= src;
                }
                *word_ops += (words - w) as u64;
            }
        }
        pivot_row += 1;
        if pivot_row == matrix.len() {
            break;
        }
    }
    pivot_row
}

/// Method of Four Russians elimination over `F_2`. A small pivot block is
/// reduced together; its row combinations are materialized once, then each
/// non-pivot row clears the whole block with one suffix XOR. The default block
/// width is four and `KIC_F4_M4RI_BLOCK` permits bounded ablation runs. Pivot
/// rows and combination tables reuse a per-thread arena;
/// `KIC_F4_DISABLE_M4RI_SCRATCH=1` limits reuse to one matrix, while
/// `KIC_F4_M4RI_ALLOCATING=1` restores the allocating implementation.
fn rref_f2_m4ri_counted(matrix: &mut [Vec<u64>], n_cols: usize, word_ops: &mut u64) -> usize {
    echelon_f2_m4ri_counted(matrix, n_cols, word_ops, true)
}

/// Four Russians elimination; `reduce_above` selects the reduced form
/// (every row cleared on the block's pivot columns) or the plain row
/// echelon form (only the rows below the block are cleared).
fn echelon_f2_m4ri_counted(
    matrix: &mut [Vec<u64>],
    n_cols: usize,
    word_ops: &mut u64,
    reduce_above: bool,
) -> usize {
    static BLOCK_WIDTH: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
    let block_width = *BLOCK_WIDTH.get_or_init(|| {
        std::env::var("KIC_F4_M4RI_BLOCK")
            .ok()
            .and_then(|value| value.parse::<usize>().ok())
            .unwrap_or(4)
            .clamp(2, 10)
    });
    if std::env::var("KIC_F4_M4RI_ALLOCATING").as_deref() == Ok("1") {
        return echelon_f2_m4ri_allocating_counted(
            matrix,
            n_cols,
            word_ops,
            block_width,
            reduce_above,
        );
    }
    if std::env::var("KIC_F4_DISABLE_M4RI_SCRATCH").as_deref() == Ok("1") {
        let mut scratch = F4M4riScratch::default();
        return echelon_f2_m4ri_arena_counted(
            matrix,
            n_cols,
            word_ops,
            block_width,
            reduce_above,
            &mut scratch,
        );
    }
    F4_M4RI_SCRATCH.with(|scratch| {
        let mut scratch = scratch.borrow_mut();
        echelon_f2_m4ri_arena_counted(
            matrix,
            n_cols,
            word_ops,
            block_width,
            reduce_above,
            &mut scratch,
        )
    })
}

#[derive(Default)]
struct F4M4riScratch {
    pivot_columns: Vec<usize>,
    block_pivots: Vec<Vec<u64>>,
    table: Vec<u64>,
}

thread_local! {
    static F4_M4RI_SCRATCH: std::cell::RefCell<F4M4riScratch> =
        std::cell::RefCell::new(F4M4riScratch::default());
}

/// Target-row words per block below which the Four Russians table is
/// applied on one thread.
const M4RI_PARALLEL_WORDS: usize = 1 << 20;

fn echelon_f2_m4ri_arena_counted(
    matrix: &mut [Vec<u64>],
    n_cols: usize,
    word_ops: &mut u64,
    block_width: usize,
    reduce_above: bool,
    scratch: &mut F4M4riScratch,
) -> usize {
    echelon_f2_m4ri_arena_counted_with(
        matrix,
        n_cols,
        word_ops,
        block_width,
        reduce_above,
        scratch,
        M4RI_PARALLEL_WORDS,
    )
}

/// [`echelon_f2_m4ri_arena_counted`] with the parallel threshold as a
/// parameter, so a test can force the parallel table application on a
/// small matrix.
fn echelon_f2_m4ri_arena_counted_with(
    matrix: &mut [Vec<u64>],
    n_cols: usize,
    word_ops: &mut u64,
    block_width: usize,
    reduce_above: bool,
    scratch: &mut F4M4riScratch,
    parallel_words: usize,
) -> usize {
    let words = n_cols.div_ceil(64);
    let rows = matrix.len();
    scratch.pivot_columns.resize(block_width, 0);
    scratch.block_pivots.resize_with(block_width, Vec::new);
    for pivot in &mut scratch.block_pivots {
        pivot.resize(words, 0);
    }
    scratch.table.resize((1usize << block_width) * words, 0);
    let F4M4riScratch {
        pivot_columns,
        block_pivots,
        table,
    } = scratch;

    let mut pivot_row = 0usize;
    let mut column = 0usize;
    while pivot_row < rows && column < n_cols {
        let block_start = pivot_row;
        let mut block_rows = 0usize;
        while block_rows < block_width && pivot_row < rows && column < n_cols {
            let next_pivot = block_start + block_rows;
            let (word, bit) = (column / 64, 1u64 << (column % 64));
            let mut found = None;
            for row in next_pivot..rows {
                for (index, &pivot_column) in pivot_columns[..block_rows].iter().enumerate() {
                    let (pivot_word, pivot_bit) = (pivot_column / 64, 1u64 << (pivot_column % 64));
                    if matrix[row][pivot_word] & pivot_bit != 0 {
                        for (target, &source) in matrix[row][pivot_word..words]
                            .iter_mut()
                            .zip(&block_pivots[index][pivot_word..words])
                        {
                            *target ^= source;
                        }
                        *word_ops += (words - pivot_word) as u64;
                    }
                }
                if matrix[row][word] & bit != 0 {
                    found = Some(row);
                    break;
                }
            }
            if let Some(found) = found {
                matrix.swap(next_pivot, found);
                block_pivots[block_rows].copy_from_slice(&matrix[next_pivot]);
                let (previous_pivots, current_pivots) = block_pivots.split_at_mut(block_rows);
                let pivot = &current_pivots[0];
                for previous in block_start..next_pivot {
                    if matrix[previous][word] & bit != 0 {
                        let block_index = previous - block_start;
                        for (target, &source) in matrix[previous][word..words]
                            .iter_mut()
                            .zip(&pivot[word..words])
                        {
                            *target ^= source;
                        }
                        for (target, &source) in previous_pivots[block_index][word..words]
                            .iter_mut()
                            .zip(&pivot[word..words])
                        {
                            *target ^= source;
                        }
                        *word_ops += 2 * (words - word) as u64;
                    }
                }
                pivot_columns[block_rows] = column;
                block_rows += 1;
            }
            column += 1;
        }
        if block_rows == 0 {
            break;
        }

        let first_word = pivot_columns[0] / 64;
        let suffix_words = words - first_word;
        let combinations = 1usize << block_rows;
        table[..suffix_words].fill(0);
        for mask in 1..combinations {
            let bit_index = mask.trailing_zeros() as usize;
            let previous = mask & (mask - 1);
            let pivot = &block_pivots[bit_index][first_word..words];
            let target_offset = mask * suffix_words;
            let source_offset = previous * suffix_words;
            for index in 0..suffix_words {
                table[target_offset + index] = table[source_offset + index] ^ pivot[index];
            }
            *word_ops += suffix_words as u64;
        }

        let first_target = if reduce_above {
            0
        } else {
            block_start + block_rows
        };
        // Each target row clears the whole block with one XOR of a table
        // row chosen by its own bits: independent across rows, so large
        // blocks run in parallel.  The XORs, and the count, are the same.
        let clear = |row: &mut Vec<u64>| -> u64 {
            let mut pattern = 0usize;
            for (index, &pivot_column) in pivot_columns[..block_rows].iter().enumerate() {
                if row[pivot_column / 64] & (1u64 << (pivot_column % 64)) != 0 {
                    pattern |= 1usize << index;
                }
            }
            if pattern == 0 {
                return 0;
            }
            let table_offset = pattern * suffix_words;
            for (target, &source) in row[first_word..words]
                .iter_mut()
                .zip(&table[table_offset..table_offset + suffix_words])
            {
                *target ^= source;
            }
            suffix_words as u64
        };
        let (head, tail) = matrix.split_at_mut(block_start);
        let above = &mut head[first_target.min(block_start)..];
        let below = &mut tail[block_rows..];
        if (above.len() + below.len()) * suffix_words >= parallel_words {
            use rayon::prelude::*;
            *word_ops += above
                .par_iter_mut()
                .chain(below.par_iter_mut())
                .map(clear)
                .sum::<u64>();
        } else {
            *word_ops += above
                .iter_mut()
                .chain(below.iter_mut())
                .map(clear)
                .sum::<u64>();
        }
        pivot_row += block_rows;
    }
    pivot_row
}

/// Retained same-binary control for the pre-arena implementation.
fn echelon_f2_m4ri_allocating_counted(
    matrix: &mut [Vec<u64>],
    n_cols: usize,
    word_ops: &mut u64,
    block_width: usize,
    reduce_above: bool,
) -> usize {
    let words = n_cols.div_ceil(64);
    let rows = matrix.len();
    let mut pivot_row = 0usize;
    let mut column = 0usize;
    while pivot_row < rows && column < n_cols {
        let block_start = pivot_row;
        let mut pivot_columns = Vec::with_capacity(block_width);
        let mut block_pivots: Vec<Vec<u64>> = Vec::with_capacity(block_width);
        while pivot_columns.len() < block_width && pivot_row < rows && column < n_cols {
            let next_pivot = block_start + pivot_columns.len();
            let (word, bit) = (column / 64, 1u64 << (column % 64));
            let mut found = None;
            for row in next_pivot..rows {
                for (index, &pivot_column) in pivot_columns.iter().enumerate() {
                    let (pivot_word, pivot_bit) = (pivot_column / 64, 1u64 << (pivot_column % 64));
                    if matrix[row][pivot_word] & pivot_bit != 0 {
                        for (target, source) in matrix[row][pivot_word..words]
                            .iter_mut()
                            .zip(&block_pivots[index][pivot_word..words])
                        {
                            *target ^= *source;
                        }
                        *word_ops += (words - pivot_word) as u64;
                    }
                }
                if matrix[row][word] & bit != 0 {
                    found = Some(row);
                    break;
                }
            }
            if let Some(found) = found {
                matrix.swap(next_pivot, found);
                let pivot = matrix[next_pivot].clone();
                for previous in block_start..next_pivot {
                    if matrix[previous][word] & bit != 0 {
                        let block_index = previous - block_start;
                        for (target, source) in matrix[previous][word..words]
                            .iter_mut()
                            .zip(&pivot[word..words])
                        {
                            *target ^= *source;
                        }
                        for (target, source) in block_pivots[block_index][word..words]
                            .iter_mut()
                            .zip(&pivot[word..words])
                        {
                            *target ^= *source;
                        }
                        *word_ops += 2 * (words - word) as u64;
                    }
                }
                pivot_columns.push(column);
                block_pivots.push(pivot);
            }
            column += 1;
        }
        if pivot_columns.is_empty() {
            break;
        }

        let block_rows = pivot_columns.len();
        let first_word = pivot_columns[0] / 64;
        let suffix_words = words - first_word;
        let combinations = 1usize << block_rows;
        let mut table = vec![0u64; combinations * suffix_words];
        for mask in 1..combinations {
            let bit = mask.trailing_zeros() as usize;
            let previous = mask & (mask - 1);
            let pivot = &block_pivots[bit][first_word..words];
            let target_offset = mask * suffix_words;
            let source_offset = previous * suffix_words;
            for index in 0..suffix_words {
                table[target_offset + index] = table[source_offset + index] ^ pivot[index];
            }
            *word_ops += suffix_words as u64;
        }

        let first_target = if reduce_above {
            0
        } else {
            block_start + block_rows
        };
        for row in first_target..rows {
            if (block_start..block_start + block_rows).contains(&row) {
                continue;
            }
            let mut pattern = 0usize;
            for (index, &pivot_column) in pivot_columns.iter().enumerate() {
                if matrix[row][pivot_column / 64] & (1u64 << (pivot_column % 64)) != 0 {
                    pattern |= 1usize << index;
                }
            }
            if pattern != 0 {
                let table_offset = pattern * suffix_words;
                for (target, source) in matrix[row][first_word..words]
                    .iter_mut()
                    .zip(&table[table_offset..table_offset + suffix_words])
                {
                    *target ^= *source;
                }
                *word_ops += suffix_words as u64;
            }
        }
        pivot_row += block_rows;
    }
    pivot_row
}

/// `KIC_F4_RREF_SUFFIX=1` pins the column-at-a-time kernel; read once, since
/// every tail reduction of the inherited engine passes through here.
fn suffix_kernel_forced() -> bool {
    static FORCED: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    *FORCED.get_or_init(|| std::env::var("KIC_F4_RREF_SUFFIX").as_deref() == Ok("1"))
}

/// `KIC_F4_KERNEL=legacy` keeps the reduced row echelon form on the
/// kernels below instead of [`crate::cryptanalysis::gf2_elim`]; read
/// once, as a same-binary control for the kernel swap.
fn legacy_rref_kernel() -> bool {
    static LEGACY: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    *LEGACY.get_or_init(|| std::env::var("KIC_F4_KERNEL").as_deref() == Ok("legacy"))
}

/// Reduced row echelon form, which is unique: whichever kernel runs, the
/// matrix comes back the same, and only the time and the word XORs
/// charged differ.  Matrices of at least 128 rows and 256 columns go to
/// the Four Russians kernel of [`crate::cryptanalysis::gf2_elim`]
/// (`gf2_elim_bench` has it 1.5–4.5× faster on the oracle's own Macaulay
/// matrices); smaller ones stay on the column-at-a-time kernel, where a
/// table would cost more to build than it saves.
pub(crate) fn rref_f2_counted(matrix: &mut [Vec<u64>], n_cols: usize, word_ops: &mut u64) -> usize {
    if !legacy_rref_kernel() && !suffix_kernel_forced() && matrix.len() >= 128 && n_cols >= 256 {
        return crate::cryptanalysis::gf2_elim::rref_counted(matrix, n_cols, word_ops);
    }
    rref_f2_legacy_counted(matrix, n_cols, word_ops)
}

/// The reduced row echelon form as it was computed before
/// [`crate::cryptanalysis::gf2_elim`]: the column-at-a-time kernel on
/// small or wide matrices, block-width-4 Four Russians otherwise.
pub(crate) fn rref_f2_legacy_counted(
    matrix: &mut [Vec<u64>],
    n_cols: usize,
    word_ops: &mut u64,
) -> usize {
    if suffix_kernel_forced()
        || matrix.len() < 128
        || n_cols < 256
        || n_cols > matrix.len().saturating_mul(4)
    {
        rref_f2_suffix_counted(matrix, n_cols, word_ops)
    } else {
        rref_f2_m4ri_counted(matrix, n_cols, word_ops)
    }
}

/// Row echelon form over `F_2` — distinct leading columns, no
/// back-substitution — with the pivot rows moved to the front; returns the
/// rank.  Same shape selection as [`rref_f2_counted`], same unit.  This is
/// all an inherited basis needs, and it is the cheaper half of an RREF.
pub(crate) fn echelon_f2_counted(
    matrix: &mut [Vec<u64>],
    n_cols: usize,
    word_ops: &mut u64,
) -> usize {
    if suffix_kernel_forced()
        || matrix.len() < 128
        || n_cols < 256
        || n_cols > matrix.len().saturating_mul(4)
    {
        echelon_f2_suffix_counted(matrix, n_cols, word_ops, false)
    } else {
        echelon_f2_m4ri_counted(matrix, n_cols, word_ops, false)
    }
}

#[cfg(test)]
#[path = "f4_rref_tests.rs"]
mod rref_tests;

// ── Macaulay profile / first fall degree ───────────────────────────

/// Rank measurement of one Macaulay matrix.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct MacaulayProfile {
    /// Degree the matrix was built at.
    pub degree: u32,
    /// Rows actually constructed.
    pub rows: usize,
    /// Distinct monomials occurring, i.e. columns.
    pub cols: usize,
    /// Rank over `F_2`.
    pub rank: usize,
}

impl MacaulayProfile {
    /// `rows − rank`: the number of independent syzygies among the
    /// Macaulay-shifted equations at this degree.
    pub fn syzygies(&self) -> usize {
        self.rows.saturating_sub(self.rank)
    }
}

/// Rank profile of the Macaulay matrix of `polys` at one degree.
pub fn macaulay_profile(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
) -> Option<MacaulayProfile> {
    let (cols, mut matrix) = build_macaulay(polys, n_vars, degree)?;
    let rows = matrix.len();
    let rank = if matrix.is_empty() {
        0
    } else {
        rref_f2(&mut matrix, cols.len())
    };
    Some(MacaulayProfile {
        degree,
        rows,
        cols: cols.len(),
        rank,
    })
}

/// [`macaulay_profile`] via structured sparse elimination.
///
/// Same rank, different representation.  This matters more than the
/// solving-degree path does: the first fall degree is swept to `d_max`
/// whatever the system does, so it pays for the *highest* degree
/// requested rather than stopping at the one that resolves.  On the
/// `n = 5, m = 3` cell at `d_max = 7` that is 32 140 × 41 226 against
/// the 8 340 × 21 778 the solving degree stops at — about fourteen times
/// the dense work, and enough to dominate a sweep whose other half has
/// already been made fast.
pub fn macaulay_profile_sparse(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
) -> Option<MacaulayProfile> {
    use crate::cryptanalysis::sparse_macaulay::{eliminate_high_columns, low_column_start};

    let (cols, rows) = build_macaulay_sparse(polys, n_vars, degree)?;
    let n_cols = cols.len();
    let n_rows = rows.len();
    if n_cols == 0 {
        return Some(MacaulayProfile {
            degree,
            rows: 0,
            cols: 0,
            rank: 0,
        });
    }

    let low_start = low_column_start(&cols);
    let elim = eliminate_high_columns(rows, n_cols, low_start);

    let low_width = n_cols - low_start;
    let words = low_width.div_ceil(64).max(1);
    let mut low: Vec<Vec<u64>> = elim
        .linear_rows
        .iter()
        .map(|r| {
            let mut row = vec![0u64; words];
            for &c in r {
                let k = c as usize - low_start;
                row[k / 64] |= 1 << (k % 64);
            }
            row
        })
        .collect();
    let low_rank = if low.is_empty() {
        0
    } else {
        rref_f2(&mut low, low_width)
    };

    Some(MacaulayProfile {
        degree,
        rows: n_rows,
        cols: n_cols,
        rank: elim.high_rank + low_rank,
    })
}

/// **First fall degree** of `polys`: the smallest `D ≥ 2` whose Macaulay
/// matrix has `rank < rows` *and* `rank < cols` — a non-trivial syzygy
/// appears and the system has not saturated.
///
/// This is the same operational definition
/// [`crate::cryptanalysis::ffd_harness`] uses for the full-field
/// Weil descent of `S₃`, so the numbers are directly comparable: that
/// harness measures the `2n`-variable system, this one the system
/// restricted to a Frobenius-invariant subspace, which is the version
/// the subfield-curve attack actually solves.
///
/// Returns the fall degree (if any up to `d_max`) and the per-degree
/// profiles.  A profile is omitted for degrees whose matrix exceeded
/// the size limits.
pub fn first_fall_degree(
    polys: &[F2BoolPoly],
    n_vars: usize,
    d_max: u32,
) -> (Option<u32>, Vec<MacaulayProfile>) {
    let mut fall = None;
    let mut profiles = Vec::new();
    for d in 2..=d_max {
        let prof = match f4_kernel() {
            F4Kernel::Fast => macaulay_profile_fast(polys, n_vars, d),
            F4Kernel::Reference => macaulay_profile_sparse(polys, n_vars, d),
        };
        let prof = match prof {
            Some(p) => p,
            None => break,
        };
        if fall.is_none() && prof.rank < prof.rows && prof.rank < prof.cols {
            fall = Some(d);
        }
        profiles.push(prof);
    }
    (fall, profiles)
}

// ── Solving degree ─────────────────────────────────────────────────

/// What the reduced Macaulay rows at one degree actually *determine*.
///
/// [`MacaulayProfile`] records rank; this records whether that rank is
/// enough to finish.  The distinction is the whole point: the first
/// fall degree is where the rank first drops below generic, and the
/// solving degree is where linear algebra alone pins every unknown.
/// Complexity claims for Semaev systems are stated in terms of the
/// first and assume it tracks the second, which is precisely the
/// assumption Kosters–Yeo (arXiv:1503.08001) show can fail.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SolvingProfile {
    /// Degree the matrix was built at.
    pub degree: u32,
    /// Rows constructed.
    pub rows: usize,
    /// Distinct monomials occurring, i.e. columns.
    pub cols: usize,
    /// Rank over `F_2`.
    pub rank: usize,
    /// Variables pinned outright by a reduced row of the form `v` or
    /// `v + 1`.
    pub vars_determined: usize,
    /// Variables actually occurring in the input system.  A variable
    /// that never occurs is free and can never be pinned, so it is
    /// excluded from the target rather than counted as a failure.
    pub vars_occurring: usize,
    /// A reduced row is the constant `1`: the system is refuted at this
    /// degree, which resolves it just as decisively as pinning every
    /// variable.
    pub refuted: bool,
}

impl SolvingProfile {
    /// Whether degree-`degree` linear algebra resolves the system with
    /// no splitting: either a refutation, or every occurring variable
    /// pinned.
    pub fn resolves(&self) -> bool {
        self.refuted || (self.vars_occurring > 0 && self.vars_determined == self.vars_occurring)
    }
}

/// Variables occurring in `polys`, as a bitmask.
pub(crate) fn occurring_vars(polys: &[F2BoolPoly]) -> u64 {
    polys
        .iter()
        .flat_map(|p| p.terms.iter())
        .fold(0u64, |acc, t| acc | t.mask)
}

/// Total degree of a boolean system.
pub fn system_degree(polys: &[F2BoolPoly]) -> u32 {
    // Called at every node of the solver, and `count_ones` on the baseline
    // x86-64 target is a dozen-instruction bit trick; where the CPU has
    // `popcnt`, run the same scan compiled with it.  The loop is written
    // out so it is compiled inside the feature-enabled function (an
    // iterator chain compiles to a separate generic `fold` that would not
    // inherit the feature).  The result is identical either way.
    #[cfg(target_arch = "x86_64")]
    {
        if std::arch::is_x86_feature_detected!("popcnt") {
            // SAFETY: the feature was just detected on this CPU.
            return unsafe { system_degree_popcnt(polys) };
        }
    }
    system_degree_body(polys)
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "popcnt")]
unsafe fn system_degree_popcnt(polys: &[F2BoolPoly]) -> u32 {
    system_degree_body(polys)
}

#[inline(always)]
fn system_degree_body(polys: &[F2BoolPoly]) -> u32 {
    let mut degree = 0u32;
    for p in polys {
        for t in &p.terms {
            degree = degree.max(t.mask.count_ones());
        }
    }
    degree
}

/// Build the Macaulay matrix of `polys` at `degree`, reduce it, and
/// report what the reduced rows determine.
///
/// `None` means the matrix exceeded the size caps (exactly as for
/// [`macaulay_profile`]), **or** that `degree` is below the system's own
/// total degree.
///
/// That second guard is not a convenience.  `build_macaulay` skips
/// input polynomials whose degree exceeds the degree requested, so at
/// `degree < system_degree(polys)` the rows describe a strict
/// *subsystem* — the cubic equations of a chained `m ≥ 3` system simply
/// vanish.  Pinning every variable of a subsystem says nothing about
/// the system, and the brute-force gate in this module's tests catches
/// it as "every variable pinned but 2 solutions exist".  It is the same
/// trap `macaulay_rows_may_be_added_but_never_substituted` pins for the
/// solver: implied rows may be added, never substituted.
///
/// A refutation below the system degree would in fact be sound — fewer
/// equations admit more solutions, so an infeasible subsystem forces an
/// infeasible system — but reporting one would make the returned degree
/// mean two different things, so the guard applies to both.
pub fn solving_profile(polys: &[F2BoolPoly], n_vars: usize, degree: u32) -> Option<SolvingProfile> {
    if degree < system_degree(polys) {
        return None;
    }
    let (cols, mut matrix) = build_macaulay(polys, n_vars, degree)?;
    let rows = matrix.len();
    let n_cols = cols.len();
    let rank = if matrix.is_empty() {
        0
    } else {
        rref_f2(&mut matrix, n_cols)
    };

    let occurring = occurring_vars(polys);
    let mut determined = 0u64;
    let mut refuted = false;

    // `rref_f2` moves the pivot rows to the front, so only the first
    // `rank` rows carry information.
    for row in matrix.iter().take(rank) {
        let mut support: Vec<u64> = Vec::new();
        for (c, mono) in cols.iter().enumerate().take(n_cols) {
            if row[c / 64] >> (c % 64) & 1 == 1 {
                support.push(*mono);
            }
            if support.len() > 2 {
                break;
            }
        }
        match support.len() {
            // The constant `1` alone: `1 = 0`, a refutation.
            1 if support[0] == 0 => refuted = true,
            // A bare variable `v = 0`.
            1 if support[0].count_ones() == 1 => determined |= support[0],
            // `v + 1 = 0`, i.e. `v = 1`.
            2 if support.contains(&0) => {
                let v = support[0] | support[1];
                if v.count_ones() == 1 {
                    determined |= v;
                }
            }
            _ => {}
        }
    }

    Some(SolvingProfile {
        degree,
        rows,
        cols: n_cols,
        rank,
        vars_determined: (determined & occurring).count_ones() as usize,
        vars_occurring: occurring.count_ones() as usize,
        refuted,
    })
}

/// [`solving_profile`] via structured sparse elimination.
///
/// Identical semantics, different representation: the high-degree
/// columns are eliminated sparsely and only the resulting linear block —
/// at most `n_vars + 1` columns wide — is reduced densely.  See
/// [`crate::cryptanalysis::sparse_macaulay`] for why that is equivalent
/// and why a Krylov method is the wrong tool for this particular
/// question.
///
/// `solving_profile_agrees_with_sparse` holds the two paths to the same
/// answers, so this is an optimisation rather than a second opinion.
pub fn solving_profile_sparse(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
) -> Option<SolvingProfile> {
    use crate::cryptanalysis::sparse_macaulay::{eliminate_high_columns, low_column_start};

    if degree < system_degree(polys) {
        return None;
    }
    let (cols, rows) = build_macaulay_sparse(polys, n_vars, degree)?;
    let n_cols = cols.len();
    let n_rows = rows.len();
    if n_cols == 0 {
        return Some(SolvingProfile {
            degree,
            rows: 0,
            cols: 0,
            rank: 0,
            vars_determined: 0,
            vars_occurring: occurring_vars(polys).count_ones() as usize,
            refuted: false,
        });
    }

    let low_start = low_column_start(&cols);
    let elim = eliminate_high_columns(rows, n_cols, low_start);

    // The surviving linear consequences span `cols[low_start..]` only.
    // Echelon form is not enough to read off a pinned variable — `{v+w,
    // w}` must reduce to `{v, w}` first — so reduce this block densely.
    // It is at most `n_vars + 1` columns wide.
    let low_width = n_cols - low_start;
    let words = low_width.div_ceil(64).max(1);
    let mut low: Vec<Vec<u64>> = elim
        .linear_rows
        .iter()
        .map(|r| {
            let mut row = vec![0u64; words];
            for &c in r {
                let k = c as usize - low_start;
                row[k / 64] |= 1 << (k % 64);
            }
            row
        })
        .collect();
    let low_rank = if low.is_empty() {
        0
    } else {
        rref_f2(&mut low, low_width)
    };

    let occurring = occurring_vars(polys);
    let mut determined = 0u64;
    let mut refuted = false;
    for row in low.iter().take(low_rank) {
        let mut support: Vec<u64> = Vec::new();
        for k in 0..low_width {
            if row[k / 64] >> (k % 64) & 1 == 1 {
                support.push(cols[low_start + k]);
            }
            if support.len() > 2 {
                break;
            }
        }
        match support.len() {
            1 if support[0] == 0 => refuted = true,
            1 if support[0].count_ones() == 1 => determined |= support[0],
            2 if support.contains(&0) => {
                let v = support[0] | support[1];
                if v.count_ones() == 1 {
                    determined |= v;
                }
            }
            _ => {}
        }
    }

    Some(SolvingProfile {
        degree,
        rows: n_rows,
        cols: n_cols,
        rank: elim.high_rank + low_rank,
        vars_determined: (determined & occurring).count_ones() as usize,
        vars_occurring: occurring.count_ones() as usize,
        refuted,
    })
}

/// **Solving degree** of `polys`: the smallest `D ≥ 1` at which the
/// reduced Macaulay matrix resolves the system outright — a refutation,
/// or every occurring variable pinned by a linear row.
///
/// This is the degree that governs cost: the Macaulay matrix at `D` has
/// `Θ(binom(n_vars, D))` columns, so an attack's exponent is set by the
/// solving degree, not by the first fall degree.  Compare against
/// [`first_fall_degree`] on the same system — the gap between them is
/// the quantity the first-fall-degree assumption asserts is small.
///
/// Returns the solving degree (if reached at or below `d_max`) and the
/// per-degree profiles.
pub fn solving_degree(
    polys: &[F2BoolPoly],
    n_vars: usize,
    d_max: u32,
) -> (Option<u32>, Vec<SolvingProfile>) {
    let mut solved = None;
    let mut profiles = Vec::new();
    // Below the system's own degree the Macaulay matrix drops equations
    // rather than relaxing them; see [`solving_profile`].
    for d in system_degree(polys).max(1)..=d_max {
        let prof = match f4_kernel() {
            F4Kernel::Fast => solving_profile_fast(polys, n_vars, d),
            F4Kernel::Reference => solving_profile_sparse(polys, n_vars, d),
        };
        let prof = match prof {
            Some(p) => p,
            None => break,
        };
        if solved.is_none() && prof.resolves() {
            solved = Some(d);
        }
        profiles.push(prof);
        if solved.is_some() {
            break;
        }
    }
    (solved, profiles)
}

/// [`solving_profile`] on the [`f4_gf2`] kernel (F5 pruning included, per
/// [`f4_gf2::default_options`]): the same profile, field for field, from
/// forward elimination over the high columns and a reduction of the linear
/// block, with no full reduction.  `solving_profile_agrees_with_fast` holds
/// the two to that.
pub fn solving_profile_fast(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
) -> Option<SolvingProfile> {
    if degree < system_degree(polys) {
        return None;
    }
    let (profile, counters) =
        f4_gf2::profile_with(polys, n_vars, degree, f4_caps(), f4_gf2::default_options());
    f4_profile_add_kernel(&counters);
    let p = profile?;
    let occurring = occurring_vars(polys);
    let determined = p.forced.iter().fold(0u64, |acc, &(v, _)| acc | 1u64 << v);
    Some(SolvingProfile {
        degree,
        rows: counters.rows as usize,
        cols: counters.cols as usize,
        rank: p.rank as usize,
        vars_determined: (determined & occurring).count_ones() as usize,
        vars_occurring: occurring.count_ones() as usize,
        refuted: p.refuted,
    })
}

/// [`macaulay_profile`] on the [`f4_gf2`] kernel.
pub fn macaulay_profile_fast(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
) -> Option<MacaulayProfile> {
    let (profile, counters) =
        f4_gf2::profile_with(polys, n_vars, degree, f4_caps(), f4_gf2::default_options());
    f4_profile_add_kernel(&counters);
    let p = profile?;
    Some(MacaulayProfile {
        degree,
        rows: counters.rows as usize,
        cols: counters.cols as usize,
        rank: p.rank as usize,
    })
}

// ── Gröbner solve with splitting ───────────────────────────────────

/// Specialise `p` by setting variable `var` to `value`.
pub(crate) fn substitute(p: &F2BoolPoly, var: u32, value: bool) -> F2BoolPoly {
    p.substitute(var, value)
}

/// Specialise `p` by setting variable `var` to `value`, inside a solve
/// whose inputs were checked canonical (`canonical`), which then skips the
/// per-call order check.
fn substitute_in_solve(p: &F2BoolPoly, var: u32, value: bool, canonical: bool) -> F2BoolPoly {
    if canonical {
        p.substitute_canonical(var, value)
    } else {
        p.substitute(var, value)
    }
}

/// A basis element that has collapsed to `v_i` or `v_i + 1` forces its
/// variable; return `(var, value)` if `p` has that shape.
fn forced_assignment(p: &F2BoolPoly) -> Option<(u32, bool)> {
    let (mut var, mut has_const) = (None, false);
    for t in &p.terms {
        if t.mask == 0 {
            has_const = true;
        } else if t.mask.count_ones() == 1 && var.is_none() {
            var = Some(t.mask.trailing_zeros());
        } else {
            return None;
        }
    }
    // p = v  ⇒ v = 0;  p = v + 1 ⇒ v = 1.
    var.map(|v| (v, has_const))
}

/// Which algebraic engine reduces the system at each node.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SolverEngine {
    /// Boolean matrix-F4 ([`matrix_f4_f2`]) through `max_degree`. Systems with
    /// at least 24 variables go directly to that degree because its row space
    /// contains every lower-degree row; smaller systems retain the historical
    /// degree ladder. `KIC_F4_MAX_DEGREE_ONLY=0|1` overrides the policy.
    MatrixF4 {
        /// Highest Macaulay degree to build before splitting.
        max_degree: u32,
    },
    /// Boolean matrix-F5: the same Macaulay matrices as `MatrixF4`, with
    /// the rows the F5 criterion predicts to reduce to zero left out
    /// ([`crate::cryptanalysis::matrix_f5_f2`]).  Identical row space,
    /// hence identical consequences, verdicts and splitting tree; only
    /// the work per node changes, and the criterion's own elimination is
    /// charged into the same word-XOR count.
    MatrixF5 {
        /// Highest Macaulay degree to build before splitting.
        max_degree: u32,
    },
    /// Inherited matrix-F4 ([`crate::cryptanalysis::inherited_f4`]): the
    /// root of the splitting tree reduces its Macaulay matrices as
    /// `MatrixF4` does, and every descendant *specialises* its parent's
    /// reduced basis by the assigned variable instead of building and
    /// reducing a matrix of its own.  Same row space at every node, hence
    /// the same tail, verdicts and splitting tree; the work per node is
    /// the re-reduction of the rows whose pivot contained the variable,
    /// plus the specialisation itself, all charged in word operations.
    /// Runs best under [`SplitRule::HighestFree`], which [`SplitRule::Auto`]
    /// selects for it; `KIC_F4_INHERIT=1|0` forces or disables inheriting.
    /// The same tree holds with linear elimination off
    /// (`KIC_LINEAR_ELIM=0`); by default this engine also eliminates a
    /// node's linear generators (`eliminate_linear_generators`), which
    /// changes the tree and keeps every root.
    InheritedF4 {
        /// Highest Macaulay degree to build before splitting.
        max_degree: u32,
    },
    /// Full Buchberger Gröbner basis
    /// ([`crate::cryptanalysis::pq_groebner_f2::groebner_basis_f2`]) at
    /// every node.  The reference engine: same answers, far slower on
    /// dense systems, kept so the fast path can be tested against a
    /// textbook one.
    Buchberger,
}

impl Default for SolverEngine {
    /// Inherited matrix-F4 through degree 3.  Under the same split rule and
    /// with `KIC_LINEAR_ELIM=0` it decides every target of the frozen
    /// Gröbner-stage ladder and its holdout identically to
    /// `MatrixF4 { max_degree: 3 }` (the default before it) for a fraction
    /// of the word operations; with [`SplitRule::Auto`] it also splits on
    /// the smallest free variable — see
    /// `research/notes/ecc2k130/RESEARCH_INHERITED_F4.md`.  Since
    /// 2026-09-24 it also eliminates linear generators, and the
    /// decomposition oracle hands it a chain in the interleaved order
    /// (`research/notes/ecc2k130/RESEARCH_CHAIN_SPLIT_ORDER.md`): the same
    /// decompositions found, on a different tree.  It builds every basis
    /// with support-local multipliers
    /// (`research/notes/ecc2k130/RESEARCH_SUPPORT_LOCAL_MULTIPLIERS.md`;
    /// `KIC_F4_MULTIPLIERS=occurring` restores the from-scratch step's
    /// policy).  `KIC_F4_INHERIT=0`
    /// restores the from-scratch engine, and with it the historical split
    /// rule and no elimination, as a retained control.
    fn default() -> Self {
        SolverEngine::InheritedF4 { max_degree: 3 }
    }
}

impl SolverEngine {
    /// The engine a solve actually runs, after the `KIC_F4_INHERIT`
    /// override: `1` turns `MatrixF4` into `InheritedF4`, `0` turns
    /// `InheritedF4` back into `MatrixF4`.  Retained controls can A/B the
    /// two on a harness that only knows [`SolverEngine::default`].
    ///
    /// An earlier revision routed cubic systems to `MatrixF4` because the
    /// inherited engine lost on them under the `LowestFree` split rule,
    /// which displaces half the basis per level deep in the tree.  Under
    /// [`SplitRule::HighestFree`] — what [`SplitRule::Auto`] resolves to
    /// for this engine — inheriting wins on the cubic cells as well
    /// (`RESEARCH_INHERITED_F4.md` §3.5), so the engine inherits on every
    /// degree.
    pub fn effective(self) -> Self {
        match (self, std::env::var("KIC_F4_INHERIT").as_deref()) {
            (SolverEngine::MatrixF4 { max_degree }, Ok("1")) => {
                SolverEngine::InheritedF4 { max_degree }
            }
            (SolverEngine::InheritedF4 { max_degree }, Ok("0")) => {
                SolverEngine::MatrixF4 { max_degree }
            }
            (engine, _) => engine,
        }
    }

    /// The Macaulay degree ladder this engine runs on a system whose
    /// generators have total degree `system_degree`: from the system's own
    /// degree (at least 2) up to `max_degree`, or the top degree alone for
    /// wide systems, as the `MatrixF4` policy has always done.
    fn degree_ladder(
        self,
        system_degree: u32,
        n_vars: usize,
    ) -> Option<std::ops::RangeInclusive<u32>> {
        let max_degree = match self {
            SolverEngine::MatrixF4 { max_degree }
            | SolverEngine::MatrixF5 { max_degree }
            | SolverEngine::InheritedF4 { max_degree } => max_degree,
            SolverEngine::Buchberger => return None,
        };
        let base = system_degree.max(2);
        let top = max_degree.max(base);
        // A higher-degree Macaulay matrix includes the lower-degree rows,
        // so this changes work scheduling rather than the ideal or roots.
        static HIGHEST_ONLY: std::sync::OnceLock<Option<bool>> = std::sync::OnceLock::new();
        let forced = *HIGHEST_ONLY.get_or_init(|| {
            match std::env::var("KIC_F4_MAX_DEGREE_ONLY").as_deref() {
                Ok("1") => Some(true),
                Ok("0") => Some(false),
                _ => None,
            }
        });
        let highest_only = forced.unwrap_or(n_vars >= 24);
        let first = if highest_only { top } else { base };
        Some(first..=top)
    }
}

/// Knobs for [`solve_boolean_system`].
#[derive(Clone, Copy, Debug)]
pub struct SolveOptions {
    /// Reduction engine.
    pub engine: SolverEngine,
    /// Stop after this many solutions.
    pub max_solutions: usize,
    /// Cap on algebraic reductions (one per splitting node, plus one
    /// per propagation round).
    pub node_budget: usize,
    /// How the splitter picks its variable when the algebra stalls.
    pub split_rule: SplitRule,
}

/// Which free variable the splitter branches on.
///
/// Every rule picks *some* unassigned variable, so the search stays
/// exhaustive whichever is chosen; they differ only in how quickly the
/// branch closes.  `LowestFree` is the historical behaviour and stays
/// the default so existing measurements keep their meaning.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum SplitRule {
    /// Lowest-indexed unassigned variable.  On the descent systems the
    /// variable index runs point by point, so this fixes one summand's
    /// bits before touching the next.
    #[default]
    LowestFree,
    /// The free variable occurring in the most monomials of the current
    /// system.  Substituting it removes the most terms.
    MostFrequent,
    /// Occurrences weighted by `2^{1-d}` for a degree-`d` monomial, so a
    /// variable sitting in short monomials outranks one buried in long
    /// ones (the classic MOM rule).  A short monomial is closer to
    /// forcing an assignment, so this favours propagation over bulk
    /// term removal.
    MinTermWeight,
    /// Highest-indexed unassigned variable that still occurs in the
    /// system — the *smallest* variable under the DegRevLex order the
    /// Macaulay columns use.  A reduced row's pivot is its largest
    /// monomial, so pivots are biased toward the large variables; the
    /// smallest free variable sits in the fewest pivots and displaces the
    /// fewest rows of an inherited basis ([`SolverEngine::InheritedF4`]).
    /// Measured on the frozen ladder (`RESEARCH_INHERITED_F4.md` §3.5):
    /// halves the inherited engine's work at every rung with a tree and
    /// turns its cubic-system loss into a win, while costing the
    /// from-scratch engine 25% more on the quadratic rungs.
    HighestFree,
    /// The rule the engine runs best with, resolved once the engine is
    /// known ([`SolveOptions::resolve`]): `HighestFree` under
    /// `InheritedF4`, `LowestFree` otherwise — so the pre-round default
    /// configuration, selected with `KIC_F4_INHERIT=0`, still walks the
    /// tree every earlier measurement walked.
    Auto,
}

/// The splitting rule the decomposition entry points use when their
/// caller does not build [`SolveOptions`] itself, overridable through
/// the `SOLVER_SPLIT_RULE` environment variable (`auto`, `lowest`,
/// `highest`, `frequent`, `mom`).  Unset means [`SplitRule::Auto`].
pub fn split_rule_default() -> SplitRule {
    match std::env::var("SOLVER_SPLIT_RULE").ok().as_deref() {
        Some("frequent") => SplitRule::MostFrequent,
        Some("mom") => SplitRule::MinTermWeight,
        Some("highest") => SplitRule::HighestFree,
        Some("lowest") => SplitRule::LowestFree,
        _ => SplitRule::Auto,
    }
}

/// Pick the variable to split on among those still unassigned.
///
/// Returns `None` only when every variable is assigned.  A free
/// variable that no longer occurs in the system is a don't-care: the
/// occurrence-based rules score it zero, and the lowest such variable
/// is taken when nothing scores higher.
pub(crate) fn choose_split(
    system: &[F2BoolPoly],
    assignment: &[Option<bool>],
    rule: SplitRule,
) -> Option<usize> {
    let lowest = assignment.iter().position(|a| a.is_none())?;
    // `Auto` is resolved by `SolveOptions::resolve` before the solve; an
    // unresolved one behaves as the historical rule.
    if matches!(rule, SplitRule::LowestFree | SplitRule::Auto) {
        return Some(lowest);
    }
    if rule == SplitRule::HighestFree {
        let occurring = occurring_vars(system);
        return Some(
            (0..assignment.len())
                .rev()
                .find(|&v| assignment[v].is_none() && occurring & (1u64 << v) != 0)
                .unwrap_or(lowest),
        );
    }
    let mut score = vec![0f64; assignment.len()];
    for p in system {
        for t in &p.terms {
            let d = t.mask.count_ones();
            if d == 0 {
                continue;
            }
            let w = match rule {
                SplitRule::MinTermWeight => (2.0f64).powi(1 - d as i32),
                _ => 1.0,
            };
            let mut m = t.mask;
            while m != 0 {
                let v = m.trailing_zeros() as usize;
                m &= m - 1;
                if v < score.len() && assignment[v].is_none() {
                    score[v] += w;
                }
            }
        }
    }
    // Highest score wins; ties go to the lowest index, so the rule is
    // deterministic and degrades to LowestFree on an empty system.
    let best = score
        .iter()
        .enumerate()
        .filter(|(v, _)| assignment[*v].is_none())
        .fold(
            (lowest, 0f64),
            |(bv, bs), (v, &sc)| {
                if sc > bs {
                    (v, sc)
                } else {
                    (bv, bs)
                }
            },
        );
    Some(best.0)
}

impl Default for SolveOptions {
    fn default() -> Self {
        Self {
            engine: SolverEngine::default(),
            max_solutions: 32,
            node_budget: 4096,
            split_rule: SplitRule::default(),
        }
    }
}

impl SolveOptions {
    /// The options a solve actually runs with: the engine after its
    /// environment override, and [`SplitRule::Auto`] resolved for it.
    pub fn resolve(&self) -> Self {
        let engine = self.engine.effective();
        let split_rule = match self.split_rule {
            SplitRule::Auto => match engine {
                SolverEngine::InheritedF4 { .. } => SplitRule::HighestFree,
                _ => SplitRule::LowestFree,
            },
            rule => rule,
        };
        Self {
            engine,
            split_rule,
            ..*self
        }
    }
}

/// Statistics from a solve, so callers can report what the algebra
/// actually cost.
#[derive(Clone, Debug, Default)]
pub struct SolveStats {
    /// Algebraic reductions performed (F4 passes or Gröbner bases).
    pub reductions: usize,
    /// Branches closed by the reduction producing the constant `1` —
    /// the infeasibility certificates that replace exhaustive search.
    pub infeasible_branches: usize,
    /// Variables fixed by propagation rather than by splitting.
    pub propagations: usize,
    /// Splitting decisions made.
    pub splits: usize,
    /// True if the node budget ran out, so results may be incomplete.
    pub exhausted: bool,
    /// Highest Macaulay degree whose matrix was actually built.
    pub max_degree_built: u32,
    /// Reductions at which the next Macaulay matrix exceeded the size
    /// caps (the engine then split on what it had).
    pub oversize: usize,
    /// Variables linear elimination defined by an affine form in others
    /// rather than fixed (`eliminate_linear_generators`); those it fixed
    /// outright are counted as propagations.
    pub eliminated: usize,
}

/// What one algebraic reduction settled: whether the ideal contains `1`,
/// and the variables pinned by rows of the form `v` or `v + 1`, in the
/// order those rows appear.
struct Reduction {
    refuted: bool,
    forced: Vec<(u32, bool)>,
}

impl Reduction {
    fn from_rows(rows: &[F2BoolPoly]) -> Self {
        Reduction {
            refuted: rows.iter().any(is_constant_one),
            forced: rows.iter().filter_map(forced_assignment).collect(),
        }
    }
}

/// Reduce `system` and report what the reduction settles.  `None` means
/// the F4 matrix would have been too large.
fn reduce_system(
    system: &[F2BoolPoly],
    n_vars: usize,
    engine: SolverEngine,
    stats: &mut SolveStats,
) -> Option<Reduction> {
    use crate::cryptanalysis::algebra_cache::{self, Layer};
    if !algebra_cache::enabled(Layer::ExactReduction) {
        return reduce_system_uncached(system, n_vars, engine, stats);
    }
    let key = serde_json::to_vec(&(n_vars, format!("{engine:?}"), system)).unwrap();
    let mut miss_oversize = 0;
    let value: Option<(Vec<F2BoolPoly>, u32, usize)> =
        algebra_cache::memoize(Layer::ExactReduction, &key, || {
            let mut measured = SolveStats::default();
            let rows = reduce_system_rows(system, n_vars, engine, &mut measured);
            // Preserve the metadata even when no reduction could be computed.
            stats.max_degree_built = stats.max_degree_built.max(measured.max_degree_built);
            miss_oversize = measured.oversize;
            rows.map(|r| (r, measured.max_degree_built, measured.oversize))
        });
    stats.reductions += 1;
    if value.is_none() {
        stats.oversize += miss_oversize;
    }
    value.map(|(rows, degree, oversize)| {
        stats.oversize += oversize;
        stats.max_degree_built = stats.max_degree_built.max(degree);
        Reduction::from_rows(&rows)
    })
}

/// Append one JSON line per solver reduction to `KIC_F4_NODE_DUMP` when that
/// variable names a file: the node system exactly as the engine receives it.
/// A diagnostic for probes that need the real node systems (row-space
/// checks, criterion counts) rather than a synthetic corpus; off by default.
fn dump_node_system(system: &[F2BoolPoly], n_vars: usize, engine: SolverEngine) {
    let Ok(path) = std::env::var("KIC_F4_NODE_DUMP") else {
        return;
    };
    use std::io::Write;
    let Ok(mut file) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
    else {
        return;
    };
    let line = serde_json::json!({
        "n_vars": n_vars,
        "engine": format!("{engine:?}"),
        "system": system,
    });
    let _ = writeln!(file, "{line}");
}

/// Whether the solver's matrix-F4 reductions run on the [`F4Kernel::Fast`]
/// decision path: the fast kernel is selected and neither the F5 row
/// criterion (`KIC_F4_CRITERION`) nor the full-readback control
/// (`KIC_F4_SOLVER_FULL_READBACK`) asks for the reference reduction.
pub(crate) fn fast_decisions() -> bool {
    f4_kernel() == F4Kernel::Fast
        && RowCriterion::from_env_or(RowCriterion::None) == RowCriterion::None
        && std::env::var("KIC_F4_SOLVER_FULL_READBACK").as_deref() != Ok("1")
}

/// The Macaulay degree ladder `engine` runs on `system`; see
/// [`SolverEngine::degree_ladder`].
pub(crate) fn solver_degree_ladder(
    engine: SolverEngine,
    system: &[F2BoolPoly],
    n_vars: usize,
) -> Option<std::ops::RangeInclusive<u32>> {
    engine.degree_ladder(system_degree(system), n_vars)
}

/// [`reduce_system`] without the cache.  The matrix-F4 engine on the
/// [`F4Kernel::Fast`] kernel ([`fast_decisions`]) decides straight from the
/// linear block of each matrix; everything else reduces to rows first.
fn reduce_system_uncached(
    system: &[F2BoolPoly],
    n_vars: usize,
    engine: SolverEngine,
    stats: &mut SolveStats,
) -> Option<Reduction> {
    let max_degree = match engine {
        SolverEngine::MatrixF4 { max_degree } | SolverEngine::InheritedF4 { max_degree }
            if fast_decisions() =>
        {
            max_degree
        }
        _ => {
            return reduce_system_rows(system, n_vars, engine, stats)
                .map(|r| Reduction::from_rows(&r))
        }
    };
    stats.reductions += 1;
    dump_node_system(system, n_vars, engine);
    let ladder = solver_degree_ladder(SolverEngine::MatrixF4 { max_degree }, system, n_vars)
        .expect("matrix engines have a ladder");
    let caps = f4_caps();
    let mut best: Option<f4_gf2::Decision> = None;
    for d in ladder {
        let (decision, counters) = f4_gf2::decide(system, n_vars, d, caps);
        f4_profile_add_kernel(&counters);
        match decision {
            Some(decision) => {
                stats.max_degree_built = stats.max_degree_built.max(d);
                let decisive = decision.is_decisive();
                best = Some(decision);
                if decisive {
                    break;
                }
            }
            None => {
                stats.oversize += 1;
                break;
            }
        }
    }
    best.map(|d| Reduction {
        refuted: d.refuted,
        forced: d.forced,
    })
}

/// Reduce `system` to polynomials in the same ideal — a Gröbner basis or
/// the reduced Macaulay rows of the highest degree built.
fn reduce_system_rows(
    system: &[F2BoolPoly],
    n_vars: usize,
    engine: SolverEngine,
    stats: &mut SolveStats,
) -> Option<Vec<F2BoolPoly>> {
    stats.reductions += 1;
    dump_node_system(system, n_vars, engine);
    // Reached with `InheritedF4` only when a caller bypasses the solver's
    // basis state (the cached path, or a direct call): reduce as MatrixF4.
    let engine = match engine {
        SolverEngine::InheritedF4 { max_degree } => SolverEngine::MatrixF4 { max_degree },
        other => other,
    };
    match engine {
        SolverEngine::Buchberger => Some(groebner_basis_f2(system.to_vec(), n_vars)),
        SolverEngine::InheritedF4 { .. } => unreachable!("mapped to MatrixF4 above"),
        SolverEngine::MatrixF4 { .. } | SolverEngine::MatrixF5 { .. } => {
            let criterion = RowCriterion::from_env_or(match engine {
                SolverEngine::MatrixF5 { .. } => RowCriterion::F5,
                _ => RowCriterion::None,
            });
            let ladder = engine
                .degree_ladder(system_degree(system), n_vars)
                .expect("matrix engines have a ladder");
            let mut best: Option<Vec<F2BoolPoly>> = None;
            for d in ladder {
                // Retained legacy control. Production only consumes a
                // contradiction or a forced variable, never the nonlinear
                // reduced rows themselves.
                let full_readback =
                    std::env::var("KIC_F4_SOLVER_FULL_READBACK").as_deref() == Ok("1");
                let reduced = if full_readback {
                    matrix_f4_f2_counted_with(system, n_vars, d, criterion).map(|(rows, _)| rows)
                } else {
                    matrix_f4_f2_solver_consequences(system, n_vars, d, criterion)
                };
                match reduced {
                    Some(rows) => {
                        stats.max_degree_built = stats.max_degree_built.max(d);
                        let decisive = rows.iter().any(is_constant_one)
                            || rows.iter().any(|p| forced_assignment(p).is_some());
                        best = Some(rows);
                        if decisive {
                            break;
                        }
                    }
                    None => {
                        // matrix too large: use what we have
                        stats.oversize += 1;
                        break;
                    }
                }
            }
            best
        }
    }
}

/// Is `p` the constant `1` — the infeasibility certificate?
pub(crate) fn is_constant_one(p: &F2BoolPoly) -> bool {
    p.terms.len() == 1 && p.terms[0].mask == 0
}

/// Per-node state of [`SolverEngine::InheritedF4`]: the reduced Macaulay
/// bases of the node's current system, one per degree the ladder has
/// reached, kept in step with every substitution the solver applies.
#[derive(Clone, Default)]
struct InheritedBases {
    bases: Vec<ReducedBasis>,
}

impl InheritedBases {
    fn position(&self, degree: u32) -> Option<usize> {
        self.bases.iter().position(|b| b.degree == degree)
    }

    /// The bases of `system|_{var = value}`, given `substituted` — the
    /// solver's own image of the node's system, aligned generator for
    /// generator with the bases' (the solver substitutes it anyway, so the
    /// bases do not substitute it again).  Specialisation replaces the
    /// child's matrix build, so its wall time is charged to the build
    /// phase; its word operations enter the stage unit.
    ///
    /// The system is taken by value: with bases, the child system is built
    /// from it by move and handed back, zeros dropped, for the solver to
    /// keep — one copy of the generators per node instead of two.  Without
    /// bases it comes back as it went in.
    ///
    /// Under `policy`, a child is not specialised at all when a generator's
    /// degree dropped ([`InheritPolicy::rebuild_on_drop`]) or when it has a
    /// linear generator the solver will eliminate
    /// ([`InheritPolicy::linear_elimination`]): its bases come back empty and
    /// its first reduction builds them from its own system, as a root does.
    fn specialise_owned(
        &self,
        var: u32,
        value: bool,
        substituted: Vec<F2BoolPoly>,
        policy: InheritPolicy,
    ) -> (Self, std::rc::Rc<Vec<F2BoolPoly>>) {
        let Some(first) = self.bases.first() else {
            return (Self::default(), std::rc::Rc::new(substituted));
        };
        let started = std::time::Instant::now();
        let mut total = InheritCost::default();
        let child = ChildSystem::from_owned(first.generator_degrees(), substituted);
        if (policy.rebuild_on_drop && child.has_dropped())
            || (policy.linear_elimination && child.system().iter().any(is_linear_generator))
        {
            f4_profile_add(|p| p.build_ns += started.elapsed().as_nanos());
            return (Self::default(), child.system().clone());
        }
        let bases = self
            .bases
            .iter()
            .map(|b| {
                let (next, cost) = b.specialise_shared(var, value, &child);
                total.reduce_word_ops += cost.reduce_word_ops;
                total.specialise_word_ops += cost.specialise_word_ops;
                next
            })
            .collect();
        let word_ops = total.word_ops();
        charge_word_ops(word_ops);
        f4_profile_add(|p| {
            p.build_ns += started.elapsed().as_nanos();
            p.word_ops += word_ops;
            p.specialise_word_ops += total.specialise_word_ops;
        });
        (Self { bases }, child.system().clone())
    }
}

/// How the solver treats the inherited bases at a node, resolved once per
/// solve from the engine and the environment.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
struct InheritPolicy {
    /// Rebuild a child's bases from its own system when a generator's
    /// degree dropped, instead of specialising the parent's and inserting
    /// completion rows (`KIC_F4_DROP=rebuild`; completion, the engine's
    /// rule since it was introduced, is the default).  The rebuilt basis
    /// is the from-scratch step's row space `V_occurring(S')`, one end of
    /// the sandwich `ReducedBasis::specialise` completes into, so the tail
    /// — and with it every decision the solver takes — is the same.
    rebuild_on_drop: bool,
    /// Eliminate linear generators by substitution before any Macaulay
    /// work at a node (`KIC_LINEAR_ELIM=1|0`); see
    /// [`eliminate_linear_generators`].
    linear_elimination: bool,
    /// Build every basis with support-local multipliers
    /// (`KIC_F4_MULTIPLIERS=support|occurring`); see
    /// [`ReducedBasis::from_system_with`].
    support_local: bool,
}

impl InheritPolicy {
    /// The policy of a solve with `engine` (already resolved): linear
    /// elimination and support-local multipliers on under
    /// [`SolverEngine::InheritedF4`] and off otherwise, so the from-scratch
    /// reference (`KIC_F4_INHERIT=0`) walks the tree it always walked, and
    /// completion on a degree drop; each can be set from the environment.
    fn resolve(engine: SolverEngine) -> Self {
        static OVERRIDES: std::sync::OnceLock<(bool, Option<bool>, bool)> =
            std::sync::OnceLock::new();
        let &(rebuild, linear, occurring) = OVERRIDES.get_or_init(|| {
            (
                std::env::var("KIC_F4_DROP").as_deref() == Ok("rebuild"),
                match std::env::var("KIC_LINEAR_ELIM").as_deref() {
                    Ok("1") => Some(true),
                    Ok("0") => Some(false),
                    _ => None,
                },
                std::env::var("KIC_F4_MULTIPLIERS").as_deref() == Ok("occurring"),
            )
        });
        let inherited = matches!(engine, SolverEngine::InheritedF4 { .. });
        Self {
            rebuild_on_drop: inherited && rebuild,
            linear_elimination: linear.unwrap_or(inherited),
            support_local: inherited && !occurring,
        }
    }
}

/// Whether a solve with the (resolved) `engine` eliminates linear
/// generators at each node; see [`InheritPolicy::linear_elimination`].
pub(crate) fn linear_elimination_enabled(engine: SolverEngine) -> bool {
    InheritPolicy::resolve(engine).linear_elimination
}

/// Drop the zero generators, cloning the shared system only if it has any.
fn drop_zeros(system: &mut std::rc::Rc<Vec<F2BoolPoly>>) {
    if system.iter().any(|p| p.is_zero()) {
        std::rc::Rc::make_mut(system).retain(|p| !p.is_zero());
    }
}

/// Rounds of degree-fall closure the inherited engine runs per node on its
/// top-degree basis (`KIC_F4_CLOSURE_ROUNDS`, `0` for none).
fn closure_rounds() -> u32 {
    static ROUNDS: std::sync::OnceLock<u32> = std::sync::OnceLock::new();
    *ROUNDS.get_or_init(|| {
        std::env::var("KIC_F4_CLOSURE_ROUNDS")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(0)
    })
}

/// The inherited engine's reduction: read the decisive rows off the node's
/// bases, building a basis from scratch only for a degree no ancestor has
/// reached.  Mirrors `reduce_system_uncached`'s ladder, decisiveness test
/// and counters so a solve is comparable call for call.
fn reduce_inherited(
    system: &[F2BoolPoly],
    canonical: bool,
    n_vars: usize,
    engine: SolverEngine,
    support_local: bool,
    bases: &mut InheritedBases,
    stats: &mut SolveStats,
) -> Option<Vec<F2BoolPoly>> {
    stats.reductions += 1;
    dump_node_system(system, n_vars, engine);
    // A canonical polynomial lists its terms highest degree first, so its
    // degree is its first term's; otherwise scan every term.
    let degree = if canonical {
        debug_assert!(system.iter().all(F2BoolPoly::is_canonical));
        system
            .iter()
            .filter_map(|p| p.terms.first())
            .map(|t| t.degree())
            .max()
            .unwrap_or(0)
    } else {
        system_degree(system)
    };
    let ladder = engine.degree_ladder(degree, n_vars)?;
    let top = *ladder.end();
    let mut best: Option<Vec<F2BoolPoly>> = None;
    for d in ladder {
        if system.is_empty() {
            best = Some(Vec::new());
            break;
        }
        let index = match bases.position(d) {
            Some(i) => i,
            None => {
                let started = std::time::Instant::now();
                let rounds = if d == top { closure_rounds() } else { 0 };
                match ReducedBasis::from_system_closed_with(
                    system,
                    n_vars,
                    d,
                    rounds,
                    support_local,
                ) {
                    Some((basis, cost)) => {
                        let word_ops = cost.word_ops();
                        charge_word_ops(word_ops);
                        f4_profile_add(|p| {
                            p.build_ns += started.elapsed().as_nanos();
                            p.word_ops += word_ops;
                        });
                        bases.bases.push(basis);
                        bases.bases.len() - 1
                    }
                    None => {
                        stats.oversize += 1;
                        f4_profile_add(|p| p.oversize += 1);
                        break;
                    }
                }
            }
        };
        let basis = &mut bases.bases[index];
        debug_assert_eq!(
            basis.system.as_slice(),
            system,
            "basis out of step with the node system"
        );
        let started = std::time::Instant::now();
        let mut cost = InheritCost::default();
        let rows = basis.decisive_rows(&mut cost);
        let word_ops = cost.word_ops();
        charge_word_ops(word_ops);
        let (rank, columns) = (basis.rank() as u64, basis.columns() as u64);
        f4_profile_add(|p| {
            p.calls += 1;
            p.reduce_ns += started.elapsed().as_nanos();
            p.rows += rank;
            p.cols += columns;
            p.word_ops += word_ops;
        });
        stats.max_degree_built = stats.max_degree_built.max(d);
        let decisive =
            rows.iter().any(is_constant_one) || rows.iter().any(|p| forced_assignment(p).is_some());
        best = Some(rows);
        if decisive {
            break;
        }
    }
    best
}

/// Is `p` a linear generator — degree one, with at least one variable?
fn is_linear_generator(p: &F2BoolPoly) -> bool {
    p.terms.iter().any(|t| t.mask != 0) && p.terms.iter().all(|t| t.mask.count_ones() <= 1)
}

/// What [`eliminate_linear_generators`] did to a node's system.
enum LinearElimination {
    /// No generator is linear.
    Nothing,
    /// The linear generators are inconsistent: the node is refuted.
    Refuted,
    /// The linear generators were solved for their pivots and substituted
    /// away.
    Substituted {
        /// The remaining generators, rewritten; zeros dropped.
        system: Vec<F2BoolPoly>,
        /// Pivots the linear generators fix outright, `v = c`.
        forced: Vec<(u32, bool)>,
        /// Pivots defined by the rest, `v = Σ_{u ∈ rest} u + c`, as
        /// `(v, rest, c)`: `rest` holds no pivot, and no variable in it is
        /// defined by a later entry of the same call.
        defined: Vec<(u32, u64, bool)>,
    },
}

/// **Linear elimination at a node.**  Gauss–Jordan the node's degree-one
/// generators, pivoting each on its largest variable (the lowest index,
/// as a reduced Macaulay row's pivot is its largest monomial), and
/// substitute every pivot `v := Σ rest + c` into the other generators.
///
/// Substituting an affine form for a variable is a ring homomorphism of
/// the Boolean ring (an affine form is idempotent), so the rewritten
/// system has exactly the roots of the original restricted to the affine
/// subspace the linear generators cut out, and each root of it extends to
/// exactly one root of the original through the definitions.  It needs no
/// Macaulay matrix: a linear generator is already in the tail every
/// reduction would read, so the step only acts earlier and without the
/// products of the linear generators by every monomial of degree
/// `D − 1` that the node's matrices would otherwise carry.  Where the
/// forms define every pivot outright the step is propagation; where some
/// pivot is defined by other variables it removes a variable the splitter
/// would otherwise branch on.
///
/// Charged in the stage unit: one word operation per row operation of the
/// elimination (each row is one 64-bit mask) and one per monomial the
/// substitution writes.
fn eliminate_linear_generators(system: &[F2BoolPoly], word_ops: &mut u64) -> LinearElimination {
    if !system.iter().any(is_linear_generator) {
        return LinearElimination::Nothing;
    }
    let mut rows: Vec<(u64, bool)> = system
        .iter()
        .filter(|p| is_linear_generator(p))
        .map(|p| {
            p.terms.iter().fold((0u64, false), |(mask, c), t| {
                if t.mask == 0 {
                    (mask, !c)
                } else {
                    (mask ^ t.mask, c)
                }
            })
        })
        .collect();
    let mut pivots: Vec<(u32, u64, bool)> = Vec::new();
    while let Some((mask, c)) = rows.pop() {
        if mask == 0 {
            if c {
                return LinearElimination::Refuted;
            }
            continue;
        }
        let v = mask.trailing_zeros();
        let bit = 1u64 << v;
        for row in rows.iter_mut().filter(|row| row.0 & bit != 0) {
            row.0 ^= mask;
            row.1 ^= c;
            *word_ops += 1;
        }
        for pivot in pivots.iter_mut().filter(|pivot| pivot.1 & bit != 0) {
            pivot.1 ^= mask;
            pivot.2 ^= c;
            *word_ops += 1;
        }
        pivots.push((v, mask & !bit, c));
    }
    let n_vars = system[0].n_vars;
    let pivot_mask = pivots.iter().fold(0u64, |acc, p| acc | (1u64 << p.0));
    let definition = |v: u32| pivots.iter().find(|p| p.0 == v).expect("a pivot");
    let mut expansion: Vec<u64> = Vec::new();
    let rewritten: Vec<F2BoolPoly> = system
        .iter()
        .filter(|p| !is_linear_generator(p))
        .filter_map(|p| {
            let mut terms: Vec<u64> = Vec::with_capacity(p.terms.len());
            for t in &p.terms {
                let hit = t.mask & pivot_mask;
                if hit == 0 {
                    terms.push(t.mask);
                    continue;
                }
                // t = base · Π_{v ∈ hit} (Σ rest_v + c_v), expanded one
                // pivot at a time; every monomial written is charged.
                expansion.clear();
                expansion.push(t.mask & !hit);
                let mut left = hit;
                while left != 0 {
                    let &(_, rest, c) = definition(left.trailing_zeros());
                    left &= left - 1;
                    let before = expansion.len();
                    for k in 0..before {
                        let base = expansion[k];
                        let mut r = rest;
                        while r != 0 {
                            expansion.push(base | (1u64 << r.trailing_zeros()));
                            r &= r - 1;
                        }
                    }
                    if !c {
                        expansion.drain(..before);
                    }
                    *word_ops += expansion.len() as u64;
                }
                terms.extend_from_slice(&expansion);
            }
            let q = F2BoolPoly::from_monos(
                terms.into_iter().map(F2BoolMono::from_mask).collect(),
                n_vars,
            );
            (!q.is_zero()).then_some(q)
        })
        .collect();
    let (forced, defined): (Vec<_>, Vec<_>) = pivots.into_iter().partition(|p| p.1 == 0);
    LinearElimination::Substituted {
        system: rewritten,
        forced: forced.into_iter().map(|(v, _, c)| (v, c)).collect(),
        defined,
    }
}

/// The point an assignment denotes, each eliminated variable recovered
/// from its definition, the latest definition first (an earlier one may
/// name a variable a later one defines, never the reverse).
fn point_with_definitions(assignment: &[Option<bool>], defined: &[(u32, u64, bool)]) -> u64 {
    let mut point = 0u64;
    for (variable, value) in assignment.iter().enumerate() {
        if *value == Some(true) {
            point |= 1u64 << variable;
        }
    }
    for &(v, rest, c) in defined.iter().rev() {
        let value = ((point & rest).count_ones() & 1 == 1) ^ c;
        point = (point & !(1u64 << v)) | ((value as u64) << v);
    }
    point
}

/// **Solve a Boolean system** by algebraic reduction plus splitting.
///
/// At each node the system is reduced ([`matrix_f4_f2`] by default,
/// Buchberger on request).  A reduction that yields the constant `1`
/// closes the branch — no search happens at all, which is the whole
/// point of doing algebra instead of enumeration.  Rows that have
/// collapsed to `v_i` or `v_i + 1` are propagated; when the algebra
/// stalls, the solver splits on the lowest free variable and recurses.
///
/// Every returned assignment is verified against the original
/// equations, so no spurious root can escape.
pub fn solve_boolean_system(
    equations: &[F2BoolPoly],
    n_vars: usize,
    opts: &SolveOptions,
) -> (Vec<u64>, SolveStats) {
    solve_boolean_system_filtered(equations, n_vars, opts, |_| false)
}

/// As [`solve_boolean_system`], but `accept` is called on each verified
/// solution as it is found; returning `true` stops the search
/// immediately (used to stop at the first root that lifts to a real
/// point decomposition).
pub fn solve_boolean_system_filtered(
    equations: &[F2BoolPoly],
    n_vars: usize,
    opts: &SolveOptions,
    accept: impl FnMut(u64) -> bool,
) -> (Vec<u64>, SolveStats) {
    let opts = opts.resolve();
    solve_with_policy(
        equations,
        n_vars,
        &opts,
        InheritPolicy::resolve(opts.engine),
        accept,
    )
}

/// [`solve_boolean_system_filtered`] with resolved options and an explicit
/// [`InheritPolicy`] — the environment is not read, so tests can run both
/// policies side by side.
fn solve_with_policy(
    equations: &[F2BoolPoly],
    n_vars: usize,
    opts: &SolveOptions,
    policy: InheritPolicy,
    mut accept: impl FnMut(u64) -> bool,
) -> (Vec<u64>, SolveStats) {
    let mut stats = SolveStats::default();
    let mut out = Vec::new();
    let mut stop = false;
    // Every polynomial the solve substitutes is an input equation or the
    // result of a substitution, which is canonical; so when the inputs
    // are, the order check can be done once here instead of per call.
    let canonical = equations.iter().all(F2BoolPoly::is_canonical);
    solve_rec(
        equations.to_vec(),
        canonical,
        equations,
        vec![None; n_vars],
        n_vars,
        opts,
        policy,
        &mut stats,
        &mut out,
        &mut accept,
        &mut stop,
        None,
        Vec::new(),
    );
    (out, stats)
}

#[allow(clippy::too_many_arguments)]
fn solve_rec(
    system: Vec<F2BoolPoly>,
    canonical: bool,
    original: &[F2BoolPoly],
    mut assignment: Vec<Option<bool>>,
    n_vars: usize,
    opts: &SolveOptions,
    policy: InheritPolicy,
    stats: &mut SolveStats,
    out: &mut Vec<u64>,
    accept: &mut impl FnMut(u64) -> bool,
    stop: &mut bool,
    parent: Option<(&InheritedBases, u32, bool)>,
    mut defined: Vec<(u32, u64, bool)>,
) {
    if *stop || out.len() >= opts.max_solutions {
        return;
    }
    // A fully assigned branch needs no further Macaulay matrix. Verify the
    // complete point directly against the untouched equations.
    if assignment.iter().all(Option::is_some) {
        let point = point_with_definitions(&assignment, &defined);
        if original.iter().all(|equation| equation.eval(point) == 0) {
            out.push(point);
            if accept(point) {
                *stop = true;
            }
        }
        return;
    }
    if stats.reductions >= opts.node_budget {
        stats.exhausted = true;
        return;
    }

    // Under the inherited engine the node's bases are its parent's,
    // specialised by the branch assignment; the root starts with none and
    // builds them at its first reduction.  A system that already contains
    // the constant `1` is refuted below without reducing, so nothing is
    // specialised for it either.
    let (mut bases, mut system) = match parent {
        Some((bases, var, value))
            if matches!(opts.engine, SolverEngine::InheritedF4 { .. })
                && !system.iter().any(is_constant_one) =>
        {
            bases.specialise_owned(var, value, system, policy)
        }
        _ => (InheritedBases::default(), std::rc::Rc::new(system)),
    };
    let inherit = matches!(opts.engine, SolverEngine::InheritedF4 { .. });

    // Reduce, propagate, repeat until the algebra stops learning.
    loop {
        drop_zeros(&mut system);
        if system.iter().any(is_constant_one) {
            stats.infeasible_branches += 1;
            return;
        }
        if policy.linear_elimination {
            let mut word_ops = 0u64;
            let elimination = eliminate_linear_generators(&system, &mut word_ops);
            if word_ops > 0 {
                charge_word_ops(word_ops);
                f4_profile_add(|p| p.word_ops += word_ops);
            }
            match elimination {
                LinearElimination::Nothing => {}
                LinearElimination::Refuted => {
                    stats.infeasible_branches += 1;
                    return;
                }
                LinearElimination::Substituted {
                    system: rewritten,
                    forced,
                    defined: definitions,
                } => {
                    for (v, val) in forced {
                        match assignment[v as usize] {
                            Some(existing) if existing != val => {
                                stats.infeasible_branches += 1;
                                return;
                            }
                            Some(_) => {}
                            None => {
                                stats.propagations += 1;
                                assignment[v as usize] = Some(val);
                            }
                        }
                    }
                    for &(v, _, _) in &definitions {
                        // Recovered from its definition at a leaf; the
                        // placeholder keeps the splitter off it.
                        stats.eliminated += 1;
                        assignment[v as usize] = Some(false);
                    }
                    defined.extend(definitions);
                    // An affine substitution is not a layout step: the
                    // node's bases are rebuilt from the rewritten system.
                    system = std::rc::Rc::new(rewritten);
                    bases = InheritedBases::default();
                    if assignment.iter().all(Option::is_some) {
                        let point = point_with_definitions(&assignment, &defined);
                        if original.iter().all(|equation| equation.eval(point) == 0) {
                            out.push(point);
                            if accept(point) {
                                *stop = true;
                            }
                        }
                        return;
                    }
                    continue;
                }
            }
        }
        let reduced = if inherit {
            reduce_inherited(
                &system,
                canonical,
                n_vars,
                opts.engine,
                policy.support_local,
                &mut bases,
                stats,
            )
            .map(|rows| Reduction::from_rows(&rows))
        } else {
            reduce_system(&system, n_vars, opts.engine, stats)
        };
        let reduced = match reduced {
            Some(r) => r,
            None => break, // no reduction available; split instead
        };
        if reduced.refuted {
            stats.infeasible_branches += 1;
            return;
        }
        let forced = reduced.forced;
        if forced.is_empty() {
            break;
        }
        for (v, val) in forced {
            match assignment[v as usize] {
                Some(existing) if existing != val => {
                    stats.infeasible_branches += 1;
                    return;
                }
                Some(_) => {}
                None => {
                    stats.propagations += 1;
                    assignment[v as usize] = Some(val);
                    let substituted: Vec<F2BoolPoly> = system
                        .iter()
                        .map(|p| substitute_in_solve(p, v, val, canonical))
                        .collect();
                    if inherit {
                        (bases, system) = bases.specialise_owned(v, val, substituted, policy);
                    } else {
                        system = std::rc::Rc::new(substituted);
                    }
                    // Keep the solver's system aligned with the bases',
                    // which drop generators that vanish.
                    drop_zeros(&mut system);
                }
            }
        }
        if stats.reductions >= opts.node_budget {
            stats.exhausted = true;
            return;
        }
    }

    match choose_split(&system, &assignment, opts.split_rule) {
        None => {
            let pt = point_with_definitions(&assignment, &defined);
            // Verify against the untouched system before accepting.
            if original.iter().all(|e| e.eval(pt) == 0) {
                out.push(pt);
                if accept(pt) {
                    *stop = true;
                }
            }
        }
        Some(free) => {
            stats.splits += 1;
            for value in [false, true] {
                let mut branch = assignment.clone();
                branch[free] = Some(value);
                let specialised: Vec<F2BoolPoly> = system
                    .iter()
                    .map(|p| substitute_in_solve(p, free as u32, value, canonical))
                    .collect();
                solve_rec(
                    specialised,
                    canonical,
                    original,
                    branch,
                    n_vars,
                    opts,
                    policy,
                    stats,
                    out,
                    accept,
                    stop,
                    Some((&bases, free as u32, value)),
                    defined.clone(),
                );
                if *stop || out.len() >= opts.max_solutions {
                    return;
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::binary_ecc::BinaryCurve;
    use crate::cryptanalysis::binary_semaev::binary_semaev_s3;
    use crate::cryptanalysis::koblitz_index_calculus::{find_irreducible, KoblitzCurve};

    fn fe(v: u64, n: u32) -> F2mElement {
        F2mElement::from_biguint(&num_bigint::BigUint::from(v), n)
    }

    /// The policies under which the inherited engine must walk the
    /// from-scratch engine's tree: linear elimination off (it changes the
    /// tree by design), either degree-drop rule.
    fn specialisation_policies() -> [InheritPolicy; 2] {
        [false, true].map(|rebuild_on_drop| InheritPolicy {
            rebuild_on_drop,
            linear_elimination: false,
            support_local: false,
        })
    }

    /// Solve under an explicit policy, whatever the environment says.
    fn solve_pinned(
        system: &[F2BoolPoly],
        n_vars: usize,
        opts: &SolveOptions,
        policy: InheritPolicy,
    ) -> (Vec<u64>, SolveStats) {
        solve_with_policy(system, n_vars, &opts.resolve(), policy, |_| false)
    }

    /// Symbolic multiplication must agree with the field's own.
    #[test]
    fn symbolic_mul_matches_field_mul() {
        let n = 9;
        let irr = find_irreducible(n).unwrap();
        let st = FieldStructure::new(n, &irr);
        for (u, v) in [(1u64, 1u64), (5, 7), (300, 47), (511, 256), (0, 123)] {
            let a = fe(u, n);
            let b = fe(v, n);
            let sym = SymElement::constant(&a, n, 4).mul(&SymElement::constant(&b, n, 4), &st);
            assert_eq!(sym.eval(0, n), a.mul(&b, &irr), "{u} · {v}");
        }
    }

    /// Symbolic squaring is the linear shortcut, and equals `x · x`.
    #[test]
    fn symbolic_square_matches_mul_by_self() {
        let n = 9;
        let irr = find_irreducible(n).unwrap();
        let st = FieldStructure::new(n, &irr);
        let basis: Vec<F2mElement> = (0..n)
            .map(|k| F2mElement::from_bit_positions(&[k], n))
            .collect();
        let x = SymElement::from_subspace_vars(&basis, 0, n, n as usize);
        let sq = x.square(&st);
        let by_mul = x.mul(&x, &st);
        for point in [0u64, 1, 2, 5, 170, 341, 511] {
            assert_eq!(sq.eval(point, n), by_mul.eval(point, n), "point {point}");
            // …and against the field's squaring of the same value.
            assert_eq!(sq.eval(point, n), x.eval(point, n).square(&irr));
        }
    }

    /// The symbolic S₃ coordinates evaluate to the scalar S₃.
    #[test]
    fn symbolic_s3_matches_scalar_s3() {
        let n = 9;
        let irr = find_irreducible(n).unwrap();
        let st = FieldStructure::new(n, &irr);
        let b = F2mElement::one(n);
        let basis: Vec<F2mElement> = (0..n)
            .map(|k| F2mElement::from_bit_positions(&[k], n))
            .collect();

        let x1 = SymElement::from_subspace_vars(&basis, 0, n, 2 * n as usize);
        let x2 = SymElement::from_subspace_vars(&basis, n as usize, n, 2 * n as usize);
        let x3 = SymElement::constant(&fe(37, n), n, 2 * n as usize);
        let eqs = sym_semaev_s3(&x1, &x2, &x3, &b, &st);

        for point in [0u64, 1, 0b101, 0b1_0101_0101, 12345, 0o777] {
            let v1 = x1.eval(point, n);
            let v2 = x2.eval(point, n);
            let scalar = binary_semaev_s3(&v1, &v2, &fe(37, n), &b, &irr);
            let mut got = Vec::new();
            for (k, e) in eqs.iter().enumerate() {
                if e.eval(point) == 1 {
                    got.push(k as u32);
                }
            }
            assert_eq!(F2mElement::from_bit_positions(&got, n), scalar);
        }
    }

    /// The symbolic `S₄` must agree with the scalar symmetrised `S₄`
    /// that `semaev_decomp` evaluates, on every point of the subspace.
    ///
    /// This is the gate on the twelve folded constants: they are
    /// transcribed here from the same derivation `binary_semaev_s4`
    /// uses, and a transcription error would produce a system that is
    /// wrong in a way no downstream test would catch — the roots would
    /// simply be different, and every one of them would fail the group
    /// re-check and silently cost relations.
    #[test]
    fn symbolic_s4_matches_the_scalar_symmetrised_s4() {
        use crate::cryptanalysis::semaev_decomp::{eval_f3, Gf2};

        let mut compared = 0u64;
        for (n, l) in [(6u32, 2u32), (9, 3), (12, 4)] {
            let irr = find_irreducible(n).unwrap();
            let st = FieldStructure::new(n, &irr);
            let gf = Gf2::new(&irr);
            let basis: Vec<F2mElement> = (0..l)
                .map(|k| F2mElement::from_bit_positions(&[k], n))
                .collect();
            let n_vars = 3 * l as usize;
            let x1 = SymElement::from_subspace_vars(&basis, 0, n, n_vars);
            let x2 = SymElement::from_subspace_vars(&basis, l as usize, n, n_vars);
            let x3 = SymElement::from_subspace_vars(&basis, 2 * l as usize, n, n_vars);

            for xr_raw in [1u64, 5, 37, 100] {
                let x_r = fe(xr_raw % (1 << n), n);
                let eqs = sym_semaev_s4(&x1, &x2, &x3, &x_r, &st);
                assert_eq!(eqs.len(), n as usize);
                for point in 0..(1u64 << n_vars) {
                    let v1 = gf.from_element(&x1.eval(point, n));
                    let v2 = gf.from_element(&x2.eval(point, n));
                    let v3 = gf.from_element(&x3.eval(point, n));
                    let scalar = eval_f3(v1, v2, v3, gf.from_element(&x_r), &gf);
                    let mut got = Vec::new();
                    for (k, e) in eqs.iter().enumerate() {
                        if e.eval(point) == 1 {
                            got.push(k as u32);
                        }
                    }
                    assert_eq!(
                        F2mElement::from_bit_positions(&got, n),
                        gf.to_element(scalar),
                        "n={n} l={l} x_r={xr_raw} point={point}"
                    );
                    compared += 1;
                }
            }
        }
        assert!(compared > 10_000, "only {compared} points compared");
    }

    /// Fixing `x₁` really does leave a system in `2ℓ` unknowns, and it
    /// really is lower degree than the three-unknown one — that is the
    /// premise of the fixed-`x₁` route.
    #[test]
    fn fixing_x1_leaves_a_system_in_two_summands() {
        let (n, l) = (12u32, 4u32);
        let irr = find_irreducible(n).unwrap();
        let st = FieldStructure::new(n, &irr);
        let basis: Vec<F2mElement> = (0..l)
            .map(|k| F2mElement::from_bit_positions(&[k], n))
            .collect();
        let x_r = fe(37, n);

        let deg = |eqs: &[F2BoolPoly]| -> u32 {
            eqs.iter()
                .flat_map(|e| e.terms.iter())
                .map(|t| t.mask.count_ones())
                .max()
                .unwrap_or(0)
        };

        // All three unknown: 3ℓ variables.
        let free = 3 * l as usize;
        let full = sym_semaev_s4(
            &SymElement::from_subspace_vars(&basis, 0, n, free),
            &SymElement::from_subspace_vars(&basis, l as usize, n, free),
            &SymElement::from_subspace_vars(&basis, 2 * l as usize, n, free),
            &x_r,
            &st,
        );

        // `x₁` fixed: 2ℓ variables, and a lower-degree system.
        let two = 2 * l as usize;
        let fixed = sym_semaev_s4(
            &SymElement::constant(&basis[0], n, two),
            &SymElement::from_subspace_vars(&basis, 0, n, two),
            &SymElement::from_subspace_vars(&basis, l as usize, n, two),
            &x_r,
            &st,
        );

        assert!(
            deg(&fixed) < deg(&full),
            "fixing x1 should drop the degree: {} vs {}",
            deg(&fixed),
            deg(&full)
        );
        // Nothing in the fixed system may touch a variable above 2ℓ.
        let top: u64 = fixed
            .iter()
            .flat_map(|e| e.terms.iter())
            .map(|t| t.mask)
            .fold(0, |a, b| a | b);
        assert_eq!(top >> two, 0, "fixed system used a variable beyond 2ℓ");
    }

    /// The decomposition systems really are multilinear with respect to
    /// the block partition — degree at most one per block — at every
    /// `m`.  That is the premise of [`matrix_f4_f2_blocked`], and it is
    /// a stronger statement than the total degree, which is 2 for
    /// `m = 2` and 3 once the chain appears.
    #[test]
    fn the_decomposition_systems_are_multilinear_in_their_blocks() {
        use crate::cryptanalysis::koblitz_index_calculus::build_frobenius_factor_base;
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let x_r = match kc.add(&fb.points[0], &fb.points[3]) {
            crate::binary_ecc::BinaryPoint::Affine { x, .. } => x,
            _ => panic!("P1 + P2 = O"),
        };

        for m in [2usize, 3] {
            let Some(sys) =
                build_decomposition_system(&fb.subspace_basis, &x_r, &kc.curve.b, m, &st)
            else {
                continue;
            };
            let blocks = sys.blocks(kc.n);
            assert_eq!(blocks.iter().sum::<usize>(), sys.n_vars, "m={m}");

            let total = sys
                .equations
                .iter()
                .flat_map(|e| e.terms.iter())
                .map(|t| t.mask.count_ones())
                .max()
                .unwrap_or(0);
            assert_eq!(total, if m == 2 { 2 } else { 3 }, "m={m} total degree");

            for (k, e) in sys.equations.iter().enumerate() {
                let d = poly_block_degrees(e, &blocks);
                assert!(
                    d.iter().all(|&x| x <= 1),
                    "m={m} equation {k} has block degrees {d:?}, not multilinear"
                );
            }
        }
    }

    /// The blocked Macaulay matrix must produce only genuine ideal
    /// members: whatever it returns has to vanish on every root of the
    /// original system.  It is allowed to be weaker than the
    /// total-degree matrix — its row space is a subspace — but never
    /// wrong.
    #[test]
    fn the_blocked_macaulay_returns_only_ideal_members() {
        use crate::cryptanalysis::koblitz_index_calculus::build_frobenius_factor_base;
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = build_frobenius_factor_base(&kc, 0).unwrap();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let x_r = match kc.add(&fb.points[0], &fb.points[3]) {
            crate::binary_ecc::BinaryPoint::Affine { x, .. } => x,
            _ => panic!("P1 + P2 = O"),
        };
        let sys =
            build_decomposition_system(&fb.subspace_basis, &x_r, &kc.curve.b, 2, &st).unwrap();
        let blocks = sys.blocks(kc.n);

        let roots: Vec<u64> = (0..(1u64 << sys.n_vars))
            .filter(|&p| sys.equations.iter().all(|q| q.eval(p) == 0))
            .collect();
        assert!(!roots.is_empty());

        for bound in [1u32, 2, 3] {
            let bounds = vec![bound; blocks.len()];
            let (rows, _) =
                matrix_f4_f2_blocked(&sys.equations, sys.n_vars, &blocks, &bounds).unwrap();
            for r in &rows {
                for &pt in &roots {
                    assert_eq!(r.eval(pt), 0, "bound {bound}: blocked row misses a root");
                }
            }
        }
    }

    /// A real decomposition is a root of the built system.
    #[test]
    fn known_decomposition_is_a_root_of_the_system() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = crate::cryptanalysis::koblitz_index_calculus::build_frobenius_factor_base(&kc, 0)
            .unwrap();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let basis = &fb.subspace_basis;

        // Pick two factor-base points and decompose their sum.
        let p1 = fb.points[0].clone();
        let p2 = fb.points[3].clone();
        let r = kc.add(&p1, &p2);
        let x_r = match &r {
            crate::binary_ecc::BinaryPoint::Affine { x, .. } => x.clone(),
            _ => panic!("P1 + P2 = O"),
        };
        let sys = build_decomposition_system(basis, &x_r, &kc.curve.b, 2, &st).unwrap();

        // Coordinates of x(P_i) in the subspace basis, as a Boolean point.
        let coords = |x: &F2mElement| -> u64 {
            for mask in 0..(1u64 << basis.len()) {
                let mut acc = F2mElement::zero(kc.n);
                for (t, bv) in basis.iter().enumerate() {
                    if (mask >> t) & 1 == 1 {
                        acc = acc.add(bv);
                    }
                }
                if &acc == x {
                    return mask;
                }
            }
            panic!("x not in the subspace");
        };
        let (x1, x2) = match (&p1, &p2) {
            (
                crate::binary_ecc::BinaryPoint::Affine { x: a, .. },
                crate::binary_ecc::BinaryPoint::Affine { x: b, .. },
            ) => (a.clone(), b.clone()),
            _ => panic!("factor base holds affine points"),
        };
        let point = coords(&x1) | (coords(&x2) << basis.len());
        assert!(
            sys.equations.iter().all(|e| e.eval(point) == 0),
            "the true decomposition must satisfy every equation"
        );
        // …and the layout helper reads the same x-coordinates back.
        assert_eq!(sys.summand_x(basis, point, 0, kc.n), x1);
        assert_eq!(sys.summand_x(basis, point, 1, kc.n), x2);
    }

    /// Degree: quadratic for `m = 2`, cubic once the chain introduces
    /// intermediate unknowns.
    #[test]
    fn system_degree_is_two_for_m2_and_three_when_chained() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = crate::cryptanalysis::koblitz_index_calculus::build_frobenius_factor_base(&kc, 0)
            .unwrap();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let sys =
            build_decomposition_system(&fb.subspace_basis, &fe(11, kc.n), &kc.curve.b, 2, &st)
                .unwrap();
        let deg = sys
            .equations
            .iter()
            .flat_map(|e| e.terms.iter())
            .map(|t| t.mask.count_ones())
            .max()
            .unwrap();
        assert_eq!(deg, 2);
        assert_eq!(sys.n_vars, 2 * fb.subspace_basis.len());
        assert_eq!(sys.equations.len(), kc.n as usize);

        // m = 3: one chaining unknown per link, and the term x₁x₂·e
        // pushes the degree to 3.
        let chained =
            build_decomposition_system(&fb.subspace_basis, &fe(11, kc.n), &kc.curve.b, 3, &st)
                .unwrap();
        let deg3 = chained
            .equations
            .iter()
            .flat_map(|e| e.terms.iter())
            .map(|t| t.mask.count_ones())
            .max()
            .unwrap();
        assert_eq!(deg3, 3);
        assert_eq!(chained.n_vars, 3 * fb.subspace_basis.len() + kc.n as usize);
        assert_eq!(chained.equations.len(), 2 * kc.n as usize);
    }

    /// The splitting solver finds exactly the roots, and closes
    /// infeasible branches by Gröbner rather than by enumeration.
    #[test]
    fn splitting_solver_agrees_with_exhaustive_evaluation() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = crate::cryptanalysis::koblitz_index_calculus::build_frobenius_factor_base(&kc, 0)
            .unwrap();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let basis = &fb.subspace_basis;

        for raw in [1u64, 9, 23, 64, 300] {
            let sys =
                build_decomposition_system(basis, &fe(raw, kc.n), &kc.curve.b, 2, &st).unwrap();
            let opts = SolveOptions {
                max_solutions: 64,
                ..SolveOptions::default()
            };
            let (sols, stats) = solve_boolean_system(&sys.equations, sys.n_vars, &opts);
            assert!(!stats.exhausted, "budget should suffice at this size");

            let mut brute = Vec::new();
            for pt in 0..(1u64 << sys.n_vars) {
                if sys.equations.iter().all(|e| e.eval(pt) == 0) {
                    brute.push(pt);
                }
            }
            let mut got = sols.clone();
            got.sort_unstable();
            brute.sort_unstable();
            assert_eq!(got, brute, "x_R = {raw}");
        }
    }

    /// The engines that share the F4 row space must walk the same splitting
    /// tree: same roots, same reductions, refutations, propagations and
    /// splits.  Checked on real Semaev systems for `m = 2` and the chained
    /// cubic `m = 3`, over targets that decompose and targets that do not.
    #[test]
    fn inherited_and_f5_engines_walk_the_same_tree_as_matrix_f4() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = crate::cryptanalysis::koblitz_index_calculus::build_frobenius_factor_base(&kc, 0)
            .unwrap();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let basis = &fb.subspace_basis;
        let engines = [
            SolverEngine::InheritedF4 { max_degree: 3 },
            SolverEngine::MatrixF5 { max_degree: 3 },
        ];
        for (m, raws) in [
            (2usize, vec![1u64, 9, 23, 64, 300, 511]),
            (3, vec![1u64, 23, 300]),
        ] {
            for raw in raws {
                let sys =
                    build_decomposition_system(basis, &fe(raw, kc.n), &kc.curve.b, m, &st).unwrap();
                let reference = SolveOptions {
                    max_solutions: 64,
                    engine: SolverEngine::MatrixF4 { max_degree: 3 },
                    ..SolveOptions::default()
                };
                let (mut want, want_stats) =
                    solve_boolean_system(&sys.equations, sys.n_vars, &reference);
                want.sort_unstable();
                for (engine, policy) in engines
                    .iter()
                    .flat_map(|&e| specialisation_policies().map(|p| (e, p)))
                {
                    let opts = SolveOptions {
                        engine,
                        ..reference
                    };
                    let (mut got, stats) = solve_pinned(&sys.equations, sys.n_vars, &opts, policy);
                    got.sort_unstable();
                    assert_eq!(
                        got, want,
                        "{engine:?} {policy:?} m={m} x_R={raw}: roots differ"
                    );
                    assert_eq!(
                        (
                            stats.reductions,
                            stats.infeasible_branches,
                            stats.propagations,
                            stats.splits
                        ),
                        (
                            want_stats.reductions,
                            want_stats.infeasible_branches,
                            want_stats.propagations,
                            want_stats.splits
                        ),
                        "{engine:?} {policy:?} m={m} x_R={raw}: the splitting tree differs"
                    );
                    assert_eq!(stats.max_degree_built, want_stats.max_degree_built);
                    assert_eq!(stats.oversize, want_stats.oversize);
                }
            }
        }
    }

    /// `Auto` resolves to the rule each engine runs best with, and an
    /// explicit rule is left alone.
    #[test]
    fn auto_split_rule_follows_the_engine() {
        // Only meaningful without the environment overrides the controls use.
        if std::env::var("KIC_F4_INHERIT").is_ok() {
            return;
        }
        let inherited = SolveOptions {
            engine: SolverEngine::InheritedF4 { max_degree: 3 },
            split_rule: SplitRule::Auto,
            ..SolveOptions::default()
        }
        .resolve();
        assert_eq!(inherited.split_rule, SplitRule::HighestFree);
        let scratch = SolveOptions {
            engine: SolverEngine::MatrixF4 { max_degree: 3 },
            split_rule: SplitRule::Auto,
            ..SolveOptions::default()
        }
        .resolve();
        assert_eq!(scratch.split_rule, SplitRule::LowestFree);
        let explicit = SolveOptions {
            engine: SolverEngine::InheritedF4 { max_degree: 3 },
            split_rule: SplitRule::LowestFree,
            ..SolveOptions::default()
        }
        .resolve();
        assert_eq!(explicit.split_rule, SplitRule::LowestFree);
        // The two rules pick opposite ends of the free variables.
        let system = vec![F2BoolPoly::from_monos(
            vec![
                F2BoolMono::from_mask(0b0110),
                F2BoolMono::var(3),
                F2BoolMono::one(),
            ],
            5,
        )];
        let assignment = vec![None; 5];
        assert_eq!(
            choose_split(&system, &assignment, SplitRule::LowestFree),
            Some(0)
        );
        assert_eq!(
            choose_split(&system, &assignment, SplitRule::HighestFree),
            Some(3)
        );
    }

    /// Same tree on random systems with linear equations mixed in — where
    /// degree drops (completion rows) and forced propagation chains occur.
    #[test]
    fn inherited_engine_matches_matrix_f4_on_random_systems() {
        let mut seed = 0xdead_beef_cafe_f00du64;
        let mut next = || {
            seed ^= seed << 13;
            seed ^= seed >> 7;
            seed ^= seed << 17;
            seed
        };
        for trial in 0..60 {
            let n_vars = 6 + (trial % 5);
            let m = 4 + (trial % 4);
            let system: Vec<F2BoolPoly> = (0..m)
                .map(|k| {
                    let deg = if k % 3 == 2 { 1 } else { 2 };
                    let terms = 3 + (next() % 6) as usize;
                    let monos = (0..terms)
                        .map(|_| {
                            let d = (next() % (deg + 1)) as u32;
                            let mut mask = 0u64;
                            for _ in 0..d {
                                mask |= 1u64 << (next() % n_vars as u64);
                            }
                            F2BoolMono::from_mask(mask)
                        })
                        .collect();
                    F2BoolPoly::from_monos(monos, n_vars)
                })
                .filter(|p| !p.is_zero())
                .collect();
            // Roots are the truth, whichever engine found them.
            let brute: Vec<u64> = (0..(1u64 << n_vars))
                .filter(|pt| system.iter().all(|e| e.eval(*pt) == 0))
                .collect();
            for split_rule in [SplitRule::LowestFree, SplitRule::HighestFree] {
                let reference = SolveOptions {
                    max_solutions: 1 << 12,
                    engine: SolverEngine::MatrixF4 { max_degree: 3 },
                    split_rule,
                    ..SolveOptions::default()
                };
                let (mut want, want_stats) = solve_boolean_system(&system, n_vars, &reference);
                want.sort_unstable();
                let opts = SolveOptions {
                    engine: SolverEngine::InheritedF4 { max_degree: 3 },
                    ..reference
                };
                for policy in specialisation_policies() {
                    let (mut got, stats) = solve_pinned(&system, n_vars, &opts, policy);
                    got.sort_unstable();
                    assert_eq!(
                        got, want,
                        "trial {trial} {split_rule:?} {policy:?}: roots differ"
                    );
                    assert_eq!(
                        (
                            stats.reductions,
                            stats.infeasible_branches,
                            stats.propagations,
                            stats.splits
                        ),
                        (
                            want_stats.reductions,
                            want_stats.infeasible_branches,
                            want_stats.propagations,
                            want_stats.splits
                        ),
                        "trial {trial} {split_rule:?} {policy:?}: the splitting tree differs"
                    );
                    assert_eq!(
                        got, brute,
                        "trial {trial} {split_rule:?} {policy:?}: roots are not the variety"
                    );
                }
            }
        }
    }

    /// Linear elimination changes the tree, never the roots: on random
    /// systems with linear generators mixed in, every engine and split
    /// rule, with either degree-drop rule, returns exactly the variety.
    #[test]
    fn linear_elimination_keeps_every_root() {
        let mut seed = 0x51ce_d00d_0bad_f00du64;
        let mut next = || {
            seed ^= seed << 13;
            seed ^= seed >> 7;
            seed ^= seed << 17;
            seed
        };
        let mut eliminated = 0usize;
        for trial in 0..80 {
            let n_vars = 6 + (trial % 7);
            let m = 3 + (trial % 5);
            let system: Vec<F2BoolPoly> = (0..m)
                .map(|k| {
                    // Every third generator linear, the rest up to cubic.
                    let deg = if k % 3 == 1 { 1 } else { 2 + (k % 2) as u64 };
                    let terms = 3 + (next() % 7) as usize;
                    let monos = (0..terms)
                        .map(|_| {
                            let d = (next() % (deg + 1)) as u32;
                            let mut mask = 0u64;
                            for _ in 0..d {
                                mask |= 1u64 << (next() % n_vars as u64);
                            }
                            F2BoolMono::from_mask(mask)
                        })
                        .collect();
                    F2BoolPoly::from_monos(monos, n_vars)
                })
                .filter(|p| !p.is_zero())
                .collect();
            let brute: Vec<u64> = (0..(1u64 << n_vars))
                .filter(|pt| system.iter().all(|e| e.eval(*pt) == 0))
                .collect();
            for engine in [
                SolverEngine::MatrixF4 { max_degree: 3 },
                SolverEngine::InheritedF4 { max_degree: 3 },
            ] {
                for split_rule in [SplitRule::LowestFree, SplitRule::HighestFree] {
                    for (rebuild_on_drop, support_local) in
                        [(false, false), (true, false), (false, true), (true, true)]
                    {
                        let opts = SolveOptions {
                            max_solutions: 1 << 13,
                            engine,
                            split_rule,
                            ..SolveOptions::default()
                        };
                        let policy = InheritPolicy {
                            rebuild_on_drop,
                            linear_elimination: true,
                            support_local,
                        };
                        let (mut got, stats) = solve_pinned(&system, n_vars, &opts, policy);
                        got.sort_unstable();
                        assert_eq!(
                            got, brute,
                            "trial {trial} {engine:?} {split_rule:?} {policy:?}: roots differ"
                        );
                        eliminated += stats.eliminated;
                    }
                }
            }
        }
        // The definitions path, not just propagation, was exercised.
        assert!(eliminated > 0, "no variable was ever defined by another");
    }

    /// Inconsistent linear generators refute; consistent ones fix or
    /// define their pivots, and the rewritten system has the same roots.
    #[test]
    fn eliminate_linear_generators_refutes_and_defines() {
        let n = 5;
        let lin = |vars: &[u32], c: bool| {
            let mut monos: Vec<F2BoolMono> = vars.iter().map(|&v| F2BoolMono::var(v)).collect();
            if c {
                monos.push(F2BoolMono::one());
            }
            F2BoolPoly::from_monos(monos, n)
        };
        let mut ops = 0u64;
        let refuted = [lin(&[0, 1], false), lin(&[1, 2], false), lin(&[0, 2], true)];
        assert!(matches!(
            eliminate_linear_generators(&refuted, &mut ops),
            LinearElimination::Refuted
        ));
        // x0 + x1 + x3 = 0, x1 + 1 = 0, and a quadratic in x0, x2, x4.
        let quad = F2BoolPoly::from_monos(
            vec![
                F2BoolMono::from_mask(0b00101),
                F2BoolMono::from_mask(0b10000),
                F2BoolMono::one(),
            ],
            n,
        );
        let system = [lin(&[0, 1, 3], false), lin(&[1], true), quad.clone()];
        let LinearElimination::Substituted {
            system: rewritten,
            forced,
            defined,
        } = eliminate_linear_generators(&system, &mut ops)
        else {
            panic!("expected a substitution");
        };
        assert_eq!(forced, vec![(1, true)]);
        assert_eq!(defined, vec![(0, 1 << 3, true)], "x0 = x3 + 1");
        assert!(rewritten
            .iter()
            .all(|p| p.terms.iter().all(|t| t.mask & 0b11 == 0)));
        assert!(ops > 0, "the elimination is charged");
        // Every root of the rewritten system, completed through the
        // definitions, is a root of the original, and every root of the
        // original arises that way.
        let mut via: Vec<u64> = (0..(1u64 << n))
            .filter(|pt| pt & 0b11 == 0 && rewritten.iter().all(|e| e.eval(*pt) == 0))
            .map(|pt| {
                // x1 forced, x0 a placeholder its definition overwrites,
                // the free variables read from `pt`.
                let assignment: Vec<Option<bool>> = (0..n)
                    .map(|i| Some(if i == 1 { true } else { pt >> i & 1 == 1 }))
                    .collect();
                point_with_definitions(&assignment, &defined)
            })
            .collect();
        via.sort_unstable();
        via.dedup();
        let direct: Vec<u64> = (0..(1u64 << n))
            .filter(|pt| system.iter().all(|e| e.eval(*pt) == 0))
            .collect();
        assert_eq!(via, direct);
    }

    /// The interleaved order is a permutation that keeps each block
    /// contiguous and puts the last summand at the highest indices, each
    /// intermediate point just below the summand it closes a link with.
    #[test]
    fn interleaved_order_puts_the_last_summand_highest() {
        let shape = |m: usize, ell: usize, n: usize| DecompositionSystem {
            equations: Vec::new(),
            n_vars: m * ell + m.saturating_sub(2) * n,
            ell,
            m,
        };
        let identity: Vec<u32> = (0..10).collect();
        assert_eq!(shape(2, 5, 7).interleaved_order(7), identity);
        // m = 3, ℓ = 2, n = 3: layout x1 x1 x2 x2 x3 x3 e e e.
        let perm = shape(3, 2, 3).interleaved_order(3);
        assert_eq!(perm, vec![0, 1, 2, 3, 7, 8, 4, 5, 6]);
        let inverse = invert_permutation(&perm);
        for v in 0..9u32 {
            assert_eq!(inverse[perm[v as usize] as usize], v);
        }
        // m = 4, ℓ = 1, n = 2: layout x1 x2 x3 x4 e1 e1 e2 e2
        // → x1 x2 e1 e1 x3 e2 e2 x4.
        assert_eq!(
            shape(4, 1, 2).interleaved_order(2),
            vec![0, 1, 4, 7, 2, 3, 5, 6]
        );
        let p = F2BoolPoly::from_monos(
            vec![F2BoolMono::from_mask(0b1_0000_0011), F2BoolMono::one()],
            9,
        );
        let q = permute_poly(&p, &perm);
        assert_eq!(permute_poly(&q, &inverse), p);
    }

    /// A chain solved in the interleaved order under the shipped policy
    /// has exactly the roots the pre-round default finds in the layout order
    /// (the inherited engine without linear elimination, which the pinned
    /// same-tree tests above tie to the from-scratch engine).
    #[test]
    fn interleaved_chain_solve_has_the_same_roots() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = crate::cryptanalysis::koblitz_index_calculus::build_frobenius_factor_base(&kc, 0)
            .unwrap();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let basis = &fb.subspace_basis;
        let opts = SolveOptions {
            max_solutions: 1 << 12,
            node_budget: 1 << 20,
            engine: SolverEngine::InheritedF4 { max_degree: 3 },
            split_rule: SplitRule::HighestFree,
        };
        let mut roots = 0usize;
        for (m, raws) in [(3usize, vec![1u64, 23, 300]), (4, vec![1u64, 23])] {
            for raw in raws {
                let sys =
                    build_decomposition_system(basis, &fe(raw, kc.n), &kc.curve.b, m, &st).unwrap();
                let before = InheritPolicy::default();
                let (mut want, want_stats) =
                    solve_pinned(&sys.equations, sys.n_vars, &opts, before);
                assert!(!want_stats.exhausted);
                want.sort_unstable();
                roots += want.len();
                let perm = sys.interleaved_order(kc.n);
                let inverse = invert_permutation(&perm);
                let permuted: Vec<F2BoolPoly> = sys
                    .equations
                    .iter()
                    .map(|e| permute_poly(e, &perm))
                    .collect();
                for (rebuild_on_drop, support_local) in
                    [(false, false), (true, false), (false, true), (true, true)]
                {
                    let policy = InheritPolicy {
                        rebuild_on_drop,
                        linear_elimination: true,
                        support_local,
                    };
                    let (got, stats) = solve_pinned(&permuted, sys.n_vars, &opts, policy);
                    assert!(!stats.exhausted);
                    let mut got: Vec<u64> =
                        got.into_iter().map(|r| permute_mask(r, &inverse)).collect();
                    got.sort_unstable();
                    assert_eq!(got, want, "m={m} x_R={raw} {policy:?}: roots differ");
                    assert!(
                        got.iter()
                            .all(|&r| sys.equations.iter().all(|e| e.eval(r) == 0)),
                        "m={m} x_R={raw}: a returned point is not a root"
                    );
                }
            }
        }
        assert!(roots > 0, "no system had a root; the comparison is vacuous");
    }

    /// Support-local multipliers build exactly the occurring-variable rows
    /// when every generator spans every variable, and otherwise a subset
    /// of them: every support-local row is a row of the occurring-variable
    /// Macaulay matrix.
    #[test]
    fn support_local_rows_are_occurring_rows() {
        let kc = KoblitzCurve::new(0, 9).unwrap();
        let fb = crate::cryptanalysis::koblitz_index_calculus::build_frobenius_factor_base(&kc, 0)
            .unwrap();
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let basis = &fb.subspace_basis;
        for (m, raw) in [(2usize, 23u64), (3, 23), (3, 300), (4, 1)] {
            let sys =
                build_decomposition_system(basis, &fe(raw, kc.n), &kc.curve.b, m, &st).unwrap();
            let occurring = occurring_vars(&sys.equations);
            let rows = |support_local: bool| -> std::collections::BTreeSet<Vec<u64>> {
                let (columns, matrix) = if support_local {
                    build_inherited_macaulay_support_local(
                        &sys.equations,
                        sys.n_vars,
                        3,
                        occurring,
                        false,
                    )
                } else {
                    build_inherited_macaulay(&sys.equations, sys.n_vars, 3, occurring, false)
                }
                .unwrap();
                matrix
                    .iter()
                    .map(|row| {
                        (0..columns.len())
                            .filter(|&c| row[c / 64] >> (c % 64) & 1 == 1)
                            .map(|c| columns[c])
                            .collect()
                    })
                    .collect()
            };
            let (local, full) = (rows(true), rows(false));
            assert!(
                local.is_subset(&full),
                "m={m}: a support-local row is not a Macaulay row"
            );
            if m == 2 {
                assert_eq!(local, full, "m=2: every generator spans every variable");
            } else {
                assert!(local.len() < full.len(), "m={m}: nothing was left out");
            }
        }
    }

    /// An unsatisfiable system is rejected by the basis, not by search.
    #[test]
    fn infeasible_system_is_closed_by_the_basis() {
        let n_vars = 4;
        // v0 = 0, v0 = 1 — contradictory.
        let p = F2BoolPoly::from_monos(vec![F2BoolMono::var(0)], n_vars);
        let q = F2BoolPoly::from_monos(vec![F2BoolMono::var(0), F2BoolMono::one()], n_vars);
        let (sols, stats) = solve_boolean_system(&[p, q], n_vars, &SolveOptions::default());
        assert!(sols.is_empty());
        assert_eq!(stats.infeasible_branches, 1);
        // The algebra settled it; no splitting happened.
        assert_eq!(stats.splits, 0);
    }

    /// `FieldStructure` really is the multiplication table of the field.
    #[test]
    fn structure_constants_match_the_curve_field() {
        let curve = BinaryCurve::test_curve_f256();
        let st = FieldStructure::new(curve.m, &curve.irreducible);
        for i in 0..curve.m {
            for j in 0..curve.m {
                let zi = F2mElement::from_bit_positions(&[i], curve.m);
                let zj = F2mElement::from_bit_positions(&[j], curve.m);
                let want = zi.mul(&zj, &curve.irreducible);
                assert_eq!(st.reduced[i as usize][j as usize], want.raw_bits()[0]);
            }
        }
    }

    /// A splitting rule may change how fast the search closes, never
    /// what it finds: on random Boolean systems all three rules return
    /// the same solution set, and it is the true one.
    #[test]
    fn every_split_rule_finds_exactly_the_solutions() {
        use crate::cryptanalysis::pq_groebner_f2::{F2BoolMono, F2BoolPoly};
        let mut seed = 0x9E3779B97F4A7C15u64;
        let mut next = move || {
            seed ^= seed << 13;
            seed ^= seed >> 7;
            seed ^= seed << 17;
            seed
        };
        for case in 0..12 {
            let n_vars = 6 + (case % 3);
            let n_eqs = 3 + (case % 4);
            let equations: Vec<F2BoolPoly> = (0..n_eqs)
                .map(|_| {
                    let terms: Vec<F2BoolMono> = (0..4)
                        .map(|_| {
                            let r = next();
                            // A degree-≤2 monomial over the first n_vars.
                            let a = (r % n_vars as u64) as u32;
                            let b = ((r >> 8) % n_vars as u64) as u32;
                            if (r >> 16) & 1 == 0 {
                                F2BoolMono::var(a)
                            } else {
                                F2BoolMono {
                                    mask: (1u64 << a) | (1u64 << b),
                                }
                            }
                        })
                        .collect();
                    F2BoolPoly::from_monos(terms, n_vars)
                })
                .collect();

            // Truth by enumeration.
            let mut truth: Vec<u64> = Vec::new();
            for pt in 0u64..(1u64 << n_vars) {
                if equations.iter().all(|e| e.eval(pt) == 0) {
                    truth.push(pt);
                }
            }

            for (rule, engine) in [
                (
                    SplitRule::LowestFree,
                    SolverEngine::MatrixF4 { max_degree: 3 },
                ),
                (
                    SplitRule::MostFrequent,
                    SolverEngine::MatrixF4 { max_degree: 3 },
                ),
                (
                    SplitRule::MinTermWeight,
                    SolverEngine::MatrixF4 { max_degree: 3 },
                ),
                (
                    SplitRule::HighestFree,
                    SolverEngine::MatrixF4 { max_degree: 3 },
                ),
                (
                    SplitRule::HighestFree,
                    SolverEngine::InheritedF4 { max_degree: 3 },
                ),
            ] {
                let opts = SolveOptions {
                    engine,
                    max_solutions: usize::MAX,
                    node_budget: 100_000,
                    split_rule: rule,
                };
                let (mut got, stats) = solve_boolean_system(&equations, n_vars, &opts);
                got.sort_unstable();
                got.dedup();
                assert!(
                    !stats.exhausted,
                    "case {case} rule {rule:?} ran out of budget"
                );
                assert_eq!(
                    got, truth,
                    "case {case} rule {rule:?} disagrees with enumeration"
                );
            }
        }
    }

    // ── Solving degree ─────────────────────────────────────────────

    /// Evaluate a boolean polynomial at the assignment packed in `a`.
    use rand::{rngs::StdRng, Rng, SeedableRng};

    fn eval_f2(p: &F2BoolPoly, a: u64) -> bool {
        p.terms
            .iter()
            .fold(false, |acc, t| acc ^ (t.mask & a == t.mask))
    }

    /// Brute-force solution count over the cube — deliberately
    /// independent of every Macaulay code path.
    fn brute_force_solutions(polys: &[F2BoolPoly], n_vars: usize) -> usize {
        (0u64..1 << n_vars)
            .filter(|&a| polys.iter().all(|p| !eval_f2(p, a)))
            .count()
    }

    #[test]
    fn solving_degree_pins_a_linear_system() {
        let n = 3;
        let polys = vec![
            F2BoolPoly::from_monos(vec![F2BoolMono::var(0), F2BoolMono::one()], n),
            F2BoolPoly::from_monos(vec![F2BoolMono::var(1)], n),
            F2BoolPoly::from_monos(vec![F2BoolMono::var(2), F2BoolMono::one()], n),
        ];
        let (d, profs) = solving_degree(&polys, n, 4);
        assert_eq!(d, Some(1), "a linear system resolves at degree 1");
        let last = profs.last().unwrap();
        assert_eq!(last.vars_determined, 3);
        assert!(!last.refuted);
    }

    #[test]
    fn solving_degree_detects_refutation() {
        let n = 2;
        let polys = vec![
            F2BoolPoly::from_monos(vec![F2BoolMono::var(0)], n),
            F2BoolPoly::from_monos(vec![F2BoolMono::var(0), F2BoolMono::one()], n),
        ];
        let (d, profs) = solving_degree(&polys, n, 3);
        assert_eq!(d, Some(1));
        assert!(profs.last().unwrap().refuted, "x0 = 0 and x0 = 1 is 1 = 0");
        assert_eq!(brute_force_solutions(&polys, n), 0);
    }

    /// The soundness gate: whatever `solving_degree` claims has to
    /// agree with an exhaustive count over the cube.
    ///
    /// Two directions, both checkable without trusting the Macaulay
    /// path: a reported refutation means zero solutions; a reported
    /// resolution-by-pinning means at most one; and a system with two
    /// or more solutions must never be reported as resolved at any
    /// degree.
    #[test]
    fn solving_degree_agrees_with_brute_force() {
        let mut rng = StdRng::seed_from_u64(0x0DE6_5EED);
        let n_vars = 8usize;
        let mut resolved = 0usize;
        let mut multi = 0usize;
        for _ in 0..200 {
            let n_eqs = 2 + (rng.gen::<usize>() % 8);
            let polys: Vec<F2BoolPoly> = (0..n_eqs)
                .map(|_| {
                    let n_terms = 1 + rng.gen::<usize>() % 4;
                    let monos: Vec<F2BoolMono> = (0..n_terms)
                        .map(|_| {
                            // degree ≤ 3 monomial over `n_vars`
                            let mut mask = 0u64;
                            for _ in 0..(rng.gen::<u32>() % 4) {
                                mask |= 1u64 << (rng.gen::<u32>() % n_vars as u32);
                            }
                            F2BoolMono::from_mask(mask)
                        })
                        .collect();
                    F2BoolPoly::from_monos(monos, n_vars)
                })
                .collect();

            let truth = brute_force_solutions(&polys, n_vars);
            // A variable that never occurs is free, so it doubles the
            // cube count without making the system any less resolved.
            let free = n_vars - occurring_vars(&polys).count_ones() as usize;
            let unique = 1usize << free;
            let deg = system_degree(&polys);
            let (d, profs) = solving_degree(&polys, n_vars, n_vars as u32);
            assert!(
                profs.iter().all(|p| p.degree >= deg),
                "no profile may be built below the system degree"
            );

            match d {
                Some(_) => {
                    resolved += 1;
                    let p = profs.last().unwrap();
                    if p.refuted {
                        assert_eq!(truth, 0, "refutation claimed but {truth} solutions exist");
                    } else {
                        assert!(
                            truth <= unique,
                            "every occurring variable pinned, so at most \
                             {unique} solutions may exist, but {truth} do"
                        );
                    }
                }
                None => {
                    multi += 1;
                }
            }
            if truth > unique {
                assert!(
                    d.is_none(),
                    "{truth} solutions over {free} free variables must not \
                     be reported as resolved"
                );
            }
        }
        assert!(resolved > 0, "the sample must contain resolved systems");
        assert!(multi > 0, "and unresolved ones, or it proves nothing");
    }

    /// A variable that never occurs is free, not unsolvable: it must be
    /// excluded from the pinning target rather than blocking it.
    #[test]
    fn solving_degree_ignores_variables_that_never_occur() {
        let n = 5;
        let polys = vec![
            F2BoolPoly::from_monos(vec![F2BoolMono::var(0), F2BoolMono::one()], n),
            F2BoolPoly::from_monos(vec![F2BoolMono::var(1)], n),
        ];
        let (d, profs) = solving_degree(&polys, n, 3);
        assert_eq!(d, Some(1));
        let p = profs.last().unwrap();
        assert_eq!(p.vars_occurring, 2, "only x0 and x1 appear");
        assert_eq!(p.vars_determined, 2);
    }

    /// The sparse path must answer **exactly** what the dense path
    /// answers.
    ///
    /// This is the entire safety argument for
    /// [`solving_profile_sparse`]: it is an optimisation, not a second
    /// opinion, so any disagreement is a bug rather than a data point.
    /// Rank, refutation, pinned-variable count and the resolve verdict
    /// are all compared, over systems drawn to span every interesting
    /// case — refuted, uniquely solved, and underdetermined.
    #[test]
    fn solving_profile_agrees_with_sparse() {
        let mut rng = StdRng::seed_from_u64(0x5A11_0C17);
        let n_vars = 9usize;
        let mut compared = 0usize;
        let mut refutations = 0usize;
        let mut pinnings = 0usize;

        for _ in 0..150 {
            let n_eqs = 2 + rng.gen::<usize>() % 10;
            let polys: Vec<F2BoolPoly> = (0..n_eqs)
                .map(|_| {
                    let n_terms = 1 + rng.gen::<usize>() % 4;
                    let monos: Vec<F2BoolMono> = (0..n_terms)
                        .map(|_| {
                            let mut mask = 0u64;
                            for _ in 0..(rng.gen::<u32>() % 4) {
                                mask |= 1u64 << (rng.gen::<u32>() % n_vars as u32);
                            }
                            F2BoolMono::from_mask(mask)
                        })
                        .collect();
                    F2BoolPoly::from_monos(monos, n_vars)
                })
                .collect();

            for d in system_degree(&polys).max(1)..=5 {
                let dense = solving_profile(&polys, n_vars, d);
                let sparse = solving_profile_sparse(&polys, n_vars, d);
                match (dense, sparse) {
                    (Some(a), Some(b)) => {
                        assert_eq!(a.rank, b.rank, "rank at degree {d}");
                        assert_eq!(a.refuted, b.refuted, "refutation at degree {d}");
                        assert_eq!(
                            a.vars_determined, b.vars_determined,
                            "pinned variables at degree {d}"
                        );
                        assert_eq!(a.vars_occurring, b.vars_occurring);
                        assert_eq!(a.resolves(), b.resolves(), "verdict at degree {d}");
                        compared += 1;
                        refutations += usize::from(a.refuted);
                        pinnings += usize::from(!a.refuted && a.vars_determined > 0);
                    }
                    (None, None) => {}
                    (a, b) => panic!("paths disagree on availability at degree {d}: {a:?} / {b:?}"),
                }
            }
        }

        assert!(compared > 100, "the comparison must actually run");
        assert!(refutations > 0, "and must cover refuted systems");
        assert!(pinnings > 0, "and systems that pin variables");
    }

    /// The fast kernel's profile must equal the dense reference's field for
    /// field — rank, rows and columns in reference units, refutation, and
    /// pinned variables even alongside a refutation — including systems
    /// that leave variables unused and degrees where F5 prunes rows.
    #[test]
    fn solving_profile_agrees_with_fast() {
        let mut rng = StdRng::seed_from_u64(0xFA57_9F0F);
        let mut compared = 0usize;
        let mut refuted = 0usize;
        let mut pinned = 0usize;
        for case in 0..200 {
            let n_vars = 6 + case % 5;
            let used = n_vars - (case % 3);
            let n_eqs = 2 + rng.gen::<usize>() % 10;
            let polys: Vec<F2BoolPoly> = (0..n_eqs)
                .map(|_| {
                    let n_terms = 1 + rng.gen::<usize>() % 4;
                    let monos: Vec<F2BoolMono> = (0..n_terms)
                        .map(|_| {
                            let mut mask = 0u64;
                            for _ in 0..(rng.gen::<u32>() % 4) {
                                mask |= 1u64 << (rng.gen::<u32>() % used as u32);
                            }
                            F2BoolMono::from_mask(mask)
                        })
                        .collect();
                    F2BoolPoly::from_monos(monos, n_vars)
                })
                .collect();
            for d in 2..=5u32 {
                assert_eq!(
                    macaulay_profile(&polys, n_vars, d),
                    macaulay_profile_fast(&polys, n_vars, d),
                    "macaulay profile at degree {d}"
                );
                let dense = solving_profile(&polys, n_vars, d);
                let fast = solving_profile_fast(&polys, n_vars, d);
                assert_eq!(dense, fast, "solving profile at degree {d}");
                if let Some(p) = dense {
                    compared += 1;
                    refuted += usize::from(p.refuted);
                    pinned += usize::from(!p.refuted && p.vars_determined > 0);
                }
            }
        }
        assert!(compared > 300, "only {compared} compared");
        assert!(
            refuted > 20 && pinned > 20,
            "{refuted} refuted, {pinned} pinned"
        );
    }

    /// Solve-cost pricing charges only the calling thread's reductions:
    /// another thread's F4 work must not move this thread's counter, and
    /// this thread's must.
    #[test]
    fn thread_word_ops_ignore_other_threads() {
        let n = 6;
        let polys: Vec<F2BoolPoly> = (0..n as u32)
            .map(|v| {
                F2BoolPoly::from_monos(
                    vec![
                        F2BoolMono::from_mask(1u64 << v | 1u64 << ((v + 1) % n as u32)),
                        F2BoolMono::var((v + 2) % n as u32),
                        F2BoolMono::one(),
                    ],
                    n,
                )
            })
            .collect();
        let before = f4_thread_word_ops();
        let elsewhere = polys.clone();
        std::thread::spawn(move || {
            let (_, ops) = matrix_f4_f2_counted(&elsewhere, n, 3).unwrap();
            assert!(ops > 0);
            assert!(f4_thread_word_ops() >= ops);
        })
        .join()
        .unwrap();
        assert_eq!(
            f4_thread_word_ops(),
            before,
            "another thread's work leaked in"
        );
        let (_, ops) = matrix_f4_f2_counted(&polys, n, 3).unwrap();
        assert_eq!(f4_thread_word_ops(), before + ops);
    }

    /// `xor_sorted` is addition over `F_2`: shared indices cancel.
    #[test]
    fn sparse_row_addition_cancels_shared_indices() {
        use crate::cryptanalysis::sparse_macaulay::xor_sorted;
        assert_eq!(xor_sorted(&[1, 3, 5], &[3, 4]), vec![1, 4, 5]);
        assert_eq!(xor_sorted(&[2, 7], &[2, 7]), Vec::<u32>::new());
        assert_eq!(xor_sorted(&[], &[9]), vec![9]);
    }

    /// The boundary the elimination targets really does separate the
    /// degree-≤1 monomials into a suffix.  If monomial order ever stops
    /// being degree-first, the sparse path's central equivalence —
    /// leading index past the boundary implies a linear consequence —
    /// silently breaks, and it would break in the direction of reporting
    /// spurious resolutions.
    #[test]
    fn low_columns_are_a_suffix_in_monomial_order() {
        use crate::cryptanalysis::sparse_macaulay::low_column_start;
        let n = 6;
        let polys = vec![
            F2BoolPoly::from_monos(
                vec![
                    F2BoolMono::from_mask(0b000111),
                    F2BoolMono::var(2),
                    F2BoolMono::one(),
                ],
                n,
            ),
            F2BoolPoly::from_monos(vec![F2BoolMono::from_mask(0b011000), F2BoolMono::var(0)], n),
        ];
        let (cols, _) = build_macaulay_sparse(&polys, n, 4).unwrap();
        let start = low_column_start(&cols);
        for (i, m) in cols.iter().enumerate() {
            if i < start {
                assert!(m.count_ones() >= 2, "column {i} before the boundary is low");
            } else {
                assert!(m.count_ones() <= 1, "column {i} after the boundary is high");
            }
        }
    }

    /// The sparse rank must equal the dense rank, degree by degree.
    ///
    /// `first_fall_degree` is decided by comparing rank against rows and
    /// cols, so a rank that is off by one moves the reported fall degree
    /// and silently changes a headline number.
    #[test]
    fn macaulay_profile_agrees_with_sparse() {
        let mut rng = StdRng::seed_from_u64(0xFA11_5EED);
        let n_vars = 9usize;
        let mut compared = 0usize;
        for _ in 0..120 {
            let n_eqs = 2 + rng.gen::<usize>() % 8;
            let polys: Vec<F2BoolPoly> = (0..n_eqs)
                .map(|_| {
                    let n_terms = 1 + rng.gen::<usize>() % 4;
                    let monos: Vec<F2BoolMono> = (0..n_terms)
                        .map(|_| {
                            let mut mask = 0u64;
                            for _ in 0..(rng.gen::<u32>() % 4) {
                                mask |= 1u64 << (rng.gen::<u32>() % n_vars as u32);
                            }
                            F2BoolMono::from_mask(mask)
                        })
                        .collect();
                    F2BoolPoly::from_monos(monos, n_vars)
                })
                .collect();
            for d in 2..=5u32 {
                match (
                    macaulay_profile(&polys, n_vars, d),
                    macaulay_profile_sparse(&polys, n_vars, d),
                ) {
                    (Some(a), Some(b)) => {
                        assert_eq!(a.rows, b.rows, "rows at degree {d}");
                        assert_eq!(a.cols, b.cols, "cols at degree {d}");
                        assert_eq!(a.rank, b.rank, "rank at degree {d}");
                        compared += 1;
                    }
                    (None, None) => {}
                    (a, b) => panic!("availability differs at degree {d}: {a:?} / {b:?}"),
                }
            }
        }
        assert!(compared > 100, "the comparison must actually run");
    }
}
