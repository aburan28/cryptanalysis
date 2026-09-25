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
//! ## Honest scope
//!
//! - The engine underneath is Buchberger with Gebauer–Möller pruning
//!   ([`crate::cryptanalysis::pq_groebner_f2`]), not F4/F5 with sparse
//!   linear algebra.  It is the right *algorithm* and the wrong
//!   *constant*; the toy parameters (`m·ℓ + (m−2)·n ≤ 64` unknowns, and
//!   in practice far fewer) are chosen accordingly.
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
use crate::cryptanalysis::pq_groebner_f2::{cmp_mono, groebner_basis_f2, F2BoolMono, F2BoolPoly};

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
    let caps = f4_caps();
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
            if rows_monos.len() > caps.max_rows {
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
    if cols.len() > caps.max_cols {
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

/// Macaulay size caps — 20 000 rows and 40 000 columns, so a too-large
/// system degrades to splitting instead of exhausting memory —
/// overridable for experiments through the `F4_F2_MAX_ROWS` /
/// `F4_F2_MAX_COLS` environment variables.
pub(crate) fn f4_caps() -> MacaulayCaps {
    f4_gf2::default_caps()
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
    /// The hash-indexed build over all variables, a full reduced echelon
    /// form, and polynomial readback: the implementation this module
    /// shipped with, kept as the paired control.
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
        F4Kernel::Reference => matrix_f4_f2_counted_reference(polys, n_vars, degree),
        F4Kernel::Fast => {
            let (rows, counters) = f4_gf2::matrix_rows(polys, n_vars, degree, f4_caps());
            f4_profile_add_kernel(&counters);
            rows.map(|r| (r, counters.word_ops))
        }
    }
}

/// [`matrix_f4_f2_counted`] on the [`F4Kernel::Reference`] kernel.
fn matrix_f4_f2_counted_reference(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
) -> Option<(Vec<F2BoolPoly>, u64)> {
    if polys.is_empty() {
        return Some((Vec::new(), 0));
    }
    let t_build = std::time::Instant::now();
    let built = build_macaulay(polys, n_vars, degree);
    let build_ns = t_build.elapsed().as_nanos();
    let (cols, mut matrix) = match built {
        Some(b) => b,
        None => {
            f4_profile_add(|p| {
                p.oversize += 1;
                p.build_ns += build_ns;
            });
            return None;
        }
    };
    if matrix.is_empty() {
        f4_profile_add(|p| {
            p.calls += 1;
            p.build_ns += build_ns;
        });
        return Some((Vec::new(), 0));
    }
    let mut word_ops = 0u64;
    let t_reduce = std::time::Instant::now();
    let rank = rref_f2_counted(&mut matrix, cols.len(), &mut word_ops);
    let reduce_ns = t_reduce.elapsed().as_nanos();

    let n_vars_out = polys[0].n_vars;
    let t_read = std::time::Instant::now();
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
    let readback_ns = t_read.elapsed().as_nanos();
    f4_profile_add(|p| {
        p.calls += 1;
        p.build_ns += build_ns;
        p.reduce_ns += reduce_ns;
        p.readback_ns += readback_ns;
        p.rows += matrix.len() as u64;
        p.cols += cols.len() as u64;
        p.eliminated_rows += matrix.len() as u64;
        p.eliminated_cols += cols.len() as u64;
        p.word_ops += word_ops;
    });
    Some((out, word_ops))
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
/// kernel fills.
pub(crate) fn f4_profile_add_kernel(k: &f4_gf2::KernelCounters) {
    if k.oversize {
        f4_profile_add(|p| {
            p.oversize += 1;
            p.build_ns += k.build_ns;
        });
    } else if k.built {
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
    /// 64-bit word XORs performed by the reductions.
    pub word_ops: u64,
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

    pub(super) fn all() -> [&'static AtomicU64; 11] {
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
    let pairs: [(&std::sync::atomic::AtomicU64, u64); 11] = [
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
    macaulay_rows_monos_capped(polys, n_vars, degree, f4_caps().max_rows)
}

/// [`macaulay_rows_monos`] with an explicit row cap.
fn macaulay_rows_monos_capped(
    polys: &[F2BoolPoly],
    n_vars: usize,
    degree: u32,
    max_rows: usize,
) -> Option<Vec<Vec<u64>>> {
    let mut rows_monos: Vec<Vec<u64>> = Vec::new();
    for p in polys {
        let pdeg = p
            .terms
            .iter()
            .map(|t| t.mask.count_ones())
            .max()
            .unwrap_or(0);
        if pdeg > degree {
            continue;
        }
        for mult in monomials_up_to(n_vars, degree - pdeg) {
            // Multiplying by a monomial is a union of masks, so two
            // distinct terms of `p` can collide — and collide means
            // cancel, in characteristic 2.  Keep the odd multiplicities.
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
            if !row.is_empty() {
                rows_monos.push(row);
            }
            if rows_monos.len() > max_rows {
                return None;
            }
        }
    }
    Some(rows_monos)
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
    macaulay_columns_capped(rows_monos, f4_caps().max_cols)
}

/// [`macaulay_columns`] with an explicit column cap.
fn macaulay_columns_capped(rows_monos: &[Vec<u64>], max_cols: usize) -> Option<Vec<u64>> {
    let mut cols: Vec<u64> = rows_monos.iter().flatten().copied().collect();
    cols.sort_unstable();
    cols.dedup();
    if cols.len() > max_cols {
        return None;
    }
    cols.sort_by(|a, b| cmp_mono(F2BoolMono::from_mask(*a), F2BoolMono::from_mask(*b)).reverse());
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
    let rows_monos = macaulay_rows_monos(polys, n_vars, degree)?;
    if rows_monos.is_empty() {
        return Some((Vec::new(), Vec::new()));
    }

    let cols: Vec<u64> = macaulay_columns(&rows_monos)?;
    let index: std::collections::HashMap<u64, usize> =
        cols.iter().enumerate().map(|(i, m)| (*m, i)).collect();

    let words = cols.len().div_ceil(64);
    let matrix: Vec<Vec<u64>> = rows_monos
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
    Some((cols, matrix))
}

/// Reduced row echelon form over `F_2`; returns the rank, with the
/// pivot rows moved to the front of `matrix`.
pub(crate) fn rref_f2(matrix: &mut [Vec<u64>], n_cols: usize) -> usize {
    let mut ignored = 0u64;
    rref_f2_counted(matrix, n_cols, &mut ignored)
}

/// [`rref_f2`], accumulating the 64-bit word XORs it performs into
/// `word_ops`.
fn rref_f2_counted(matrix: &mut [Vec<u64>], n_cols: usize, word_ops: &mut u64) -> usize {
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
        for row in before.iter_mut().chain(after.iter_mut()) {
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
fn occurring_vars(polys: &[F2BoolPoly]) -> u64 {
    polys
        .iter()
        .flat_map(|p| p.terms.iter())
        .fold(0u64, |acc, t| acc | t.mask)
}

/// Total degree of a boolean system.
pub fn system_degree(polys: &[F2BoolPoly]) -> u32 {
    polys
        .iter()
        .flat_map(|p| p.terms.iter())
        .map(|t| t.mask.count_ones())
        .max()
        .unwrap_or(0)
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
    let bit = 1u64 << var;
    let mut monos = Vec::with_capacity(p.terms.len());
    for t in &p.terms {
        if t.mask & bit == 0 {
            monos.push(*t);
        } else if value {
            monos.push(F2BoolMono::from_mask(t.mask & !bit));
        }
        // v = 0 kills every term containing v.
    }
    F2BoolPoly::from_monos(monos, p.n_vars)
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
    /// Boolean matrix-F4 ([`matrix_f4_f2`]) at degrees `2 ..= max_degree`.
    /// Fast, and the engine the real algorithm uses.
    MatrixF4 {
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
    fn default() -> Self {
        SolverEngine::MatrixF4 { max_degree: 3 }
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
}

/// The splitting rule the decomposition entry points use when their
/// caller does not build [`SolveOptions`] itself, overridable through
/// the `SOLVER_SPLIT_RULE` environment variable (`lowest`, `frequent`,
/// `mom`).  Unset means [`SplitRule::LowestFree`], so the production
/// paths and every earlier measurement are unchanged by default.
pub fn split_rule_default() -> SplitRule {
    match std::env::var("SOLVER_SPLIT_RULE").ok().as_deref() {
        Some("frequent") => SplitRule::MostFrequent,
        Some("mom") => SplitRule::MinTermWeight,
        _ => SplitRule::LowestFree,
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
    if rule == SplitRule::LowestFree {
        return Some(lowest);
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

/// [`reduce_system`] without the cache.  The matrix-F4 engine on the
/// [`F4Kernel::Fast`] kernel decides straight from the linear block of
/// each matrix; everything else reduces to rows first.
fn reduce_system_uncached(
    system: &[F2BoolPoly],
    n_vars: usize,
    engine: SolverEngine,
    stats: &mut SolveStats,
) -> Option<Reduction> {
    let SolverEngine::MatrixF4 { max_degree } = engine else {
        return reduce_system_rows(system, n_vars, engine, stats).map(|r| Reduction::from_rows(&r));
    };
    if f4_kernel() == F4Kernel::Reference {
        return reduce_system_rows(system, n_vars, engine, stats).map(|r| Reduction::from_rows(&r));
    }
    stats.reductions += 1;
    let base = system_degree(system).max(2);
    let caps = f4_caps();
    let mut best: Option<f4_gf2::Decision> = None;
    for d in base..=max_degree.max(base) {
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
    match engine {
        SolverEngine::Buchberger => Some(groebner_basis_f2(system.to_vec(), n_vars)),
        SolverEngine::MatrixF4 { max_degree } => {
            let base = system
                .iter()
                .flat_map(|p| p.terms.iter())
                .map(|t| t.mask.count_ones())
                .max()
                .unwrap_or(0)
                .max(2);
            let mut best: Option<Vec<F2BoolPoly>> = None;
            for d in base..=max_degree.max(base) {
                match matrix_f4_f2(system, n_vars, d) {
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
    mut accept: impl FnMut(u64) -> bool,
) -> (Vec<u64>, SolveStats) {
    let mut stats = SolveStats::default();
    let mut out = Vec::new();
    let mut stop = false;
    solve_rec(
        equations.to_vec(),
        equations,
        vec![None; n_vars],
        n_vars,
        opts,
        &mut stats,
        &mut out,
        &mut accept,
        &mut stop,
    );
    (out, stats)
}

#[allow(clippy::too_many_arguments)]
fn solve_rec(
    mut system: Vec<F2BoolPoly>,
    original: &[F2BoolPoly],
    mut assignment: Vec<Option<bool>>,
    n_vars: usize,
    opts: &SolveOptions,
    stats: &mut SolveStats,
    out: &mut Vec<u64>,
    accept: &mut impl FnMut(u64) -> bool,
    stop: &mut bool,
) {
    if *stop || out.len() >= opts.max_solutions {
        return;
    }
    if stats.reductions >= opts.node_budget {
        stats.exhausted = true;
        return;
    }

    // Reduce, propagate, repeat until the algebra stops learning.
    loop {
        system.retain(|p| !p.is_zero());
        if system.iter().any(is_constant_one) {
            stats.infeasible_branches += 1;
            return;
        }
        let reduced = match reduce_system(&system, n_vars, opts.engine, stats) {
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
                    system = system.iter().map(|p| substitute(p, v, val)).collect();
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
            let mut pt = 0u64;
            for (i, a) in assignment.iter().enumerate() {
                if *a == Some(true) {
                    pt |= 1 << i;
                }
            }
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
                    .map(|p| substitute(p, free as u32, value))
                    .collect();
                solve_rec(
                    specialised,
                    original,
                    branch,
                    n_vars,
                    opts,
                    stats,
                    out,
                    accept,
                    stop,
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

            for rule in [
                SplitRule::LowestFree,
                SplitRule::MostFrequent,
                SplitRule::MinTermWeight,
            ] {
                let opts = SolveOptions {
                    engine: SolverEngine::MatrixF4 { max_degree: 3 },
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
