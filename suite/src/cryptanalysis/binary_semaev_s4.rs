//! # Symmetrised binary Semaev `S₄`, and its Weil descent.
//!
//! Companion to [`crate::cryptanalysis::binary_semaev`] (which handles
//! `S₃`).  Where `S₃` decomposes a point into **two** factor-base
//! points, `S₄` decomposes into **three** — and `m = 3` is where index
//! calculus starts to be worth doing at all: `m = 2` buys no asymptotic
//! improvement over Pollard ρ.
//!
//! ## Why symmetrise
//!
//! `S₄(X₁, X₂, X₃, x_R)` is symmetric in `X₁, X₂, X₃`, so it can be
//! rewritten over the elementary symmetric functions
//!
//! ```text
//!     e₁ = X₁ + X₂ + X₃
//!     e₂ = X₁X₂ + X₁X₃ + X₂X₃
//!     e₃ = X₁X₂X₃
//! ```
//!
//! which collapses the monomial count by roughly `m!` — the
//! Faugère–Gaudry–Huot–Renault speed-up.  Crucially it also drops the
//! *degree*: over the `eᵢ` the descended system is quadratic, where
//! over the `Xᵢ` it would be cubic.
//!
//! The price is that the `eᵢ` are not free: they must be tied back to
//! the `Xᵢ` by a **correspondence system**, which is where the cubic
//! degree goes.  So the model has two halves, and this module builds
//! both:
//!
//! | half | variables | degree | count |
//! |---|---|---|---|
//! | correspondence `eᵢ = σᵢ(X₁,X₂,X₃)` | `x` and `e` | ≤ 3 | `6l − 3` |
//! | descended `S₄` | `e` only | ≤ 2 | `n` |
//!
//! ## Frobenius is a relocation
//!
//! [`AnfF2m::square`] does no multiplication.  In characteristic 2,
//! `(Σ c_d z^d)² = Σ c_d² z^{2d}` — no cross terms — and each `c_d` is
//! an ANF over *Boolean* variables, where `a² = a` forces `c_d² = c_d`.
//! Both facts are needed; together they make squaring pure relocation
//! of coefficients from `d` to `2d`.  Of the twelve terms of `f₃`
//! below, including `e₁⁴`, `e₂⁴`, `e₃⁴` and `e₃³`, only four need a
//! genuine multiplication.
//!
//! ## Curve support
//!
//! The symmetrised form implemented here is specialised to `b = 1`,
//! i.e. the Koblitz curve `E: y² + xy = x³ + x² + 1`, which is the
//! curve the reference corpus in
//! `research/ec-index-calculus-review/` was generated on.  `S₄` does
//! not depend on `a₂`, but it *does* depend on `b`, and the `b`-powers
//! are folded into the constants below — a general-`b` form has to be
//! re-derived from `Res_X(S₃(X₁,X₂,X), S₃(X₃,x_R,X))` and then
//! re-symmetrised.  [`weil_descend_s4`] rejects `b ≠ 1` rather than
//! silently returning the wrong system.
//!
//! ## References
//!
//! - **J.-C. Faugère, P. Gaudry, L. Huot, G. Renault**, *Using
//!   symmetries in the index calculus for elliptic curves discrete
//!   logarithm*, J. Cryptology 2014.
//! - **P. Gaudry**, *Index calculus for abelian varieties of small
//!   dimension and the elliptic curve discrete logarithm problem*,
//!   J. Symbolic Computation 2009.
//! - **I. Semaev**, *Summation polynomials and the discrete logarithm
//!   problem on elliptic curves*, 2004.

use crate::binary_ecc::{F2mElement, IrreduciblePoly};
use std::collections::BTreeSet;

// ── Sparse ANF over F₂ ──────────────────────────────────────────────

/// A polynomial over `F₂` in Boolean variables, held as its set of
/// monomials (algebraic normal form).  A monomial is a strictly
/// increasing variable-index vector; the empty vector is the constant
/// `1`.  The polynomial is the XOR-sum of its monomials.
///
/// Variables are Boolean, so `x² = x` and every monomial is squarefree.
///
/// Note that addition is *symmetric difference*: a monomial added twice
/// cancels.  That is the whole difference between this and the upstream
/// C implementation's `multiply`, which accumulates with a bitwise OR
/// and is therefore only correct on multiplicity-free products.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct AnfPoly {
    monomials: BTreeSet<Vec<u32>>,
}

impl AnfPoly {
    pub fn zero() -> Self {
        Self {
            monomials: BTreeSet::new(),
        }
    }

    /// The constant `1`.
    pub fn one() -> Self {
        let mut m = BTreeSet::new();
        m.insert(Vec::new());
        Self { monomials: m }
    }

    /// The single variable `x_v`.
    pub fn var(v: u32) -> Self {
        let mut m = BTreeSet::new();
        m.insert(vec![v]);
        Self { monomials: m }
    }

    pub fn is_zero(&self) -> bool {
        self.monomials.is_empty()
    }

    /// Number of monomials (including the constant term, if present).
    pub fn len(&self) -> usize {
        self.monomials.len()
    }

    pub fn is_empty(&self) -> bool {
        self.monomials.is_empty()
    }

    /// Highest total degree of any monomial; `0` for a constant or zero.
    pub fn degree(&self) -> usize {
        self.monomials.iter().map(|m| m.len()).max().unwrap_or(0)
    }

    /// Iterate the monomials, each a sorted variable-index slice.
    pub fn monomials(&self) -> impl Iterator<Item = &Vec<u32>> {
        self.monomials.iter()
    }

    /// Does the constant term `1` appear?
    pub fn has_constant(&self) -> bool {
        self.monomials.contains(&Vec::new())
    }

    /// XOR one monomial in (adding it twice cancels).
    fn toggle(&mut self, mono: Vec<u32>) {
        if !self.monomials.remove(&mono) {
            self.monomials.insert(mono);
        }
    }

    /// `self ^= other`.
    pub fn xor_assign(&mut self, other: &Self) {
        for m in &other.monomials {
            self.toggle(m.clone());
        }
    }

    /// `self * other`, reducing `x² → x` in each product monomial.
    pub fn mul(&self, other: &Self) -> Self {
        let mut out = Self::zero();
        for a in &self.monomials {
            for b in &other.monomials {
                out.toggle(merge_squarefree(a, b));
            }
        }
        out
    }

    /// Evaluate at a Boolean assignment indexed by variable id.
    pub fn eval(&self, assignment: &[bool]) -> bool {
        let mut acc = false;
        for m in &self.monomials {
            if m.iter().all(|v| assignment[*v as usize]) {
                acc = !acc;
            }
        }
        acc
    }
}

/// Union of two sorted variable lists, deduplicated because `x² = x`.
fn merge_squarefree(a: &[u32], b: &[u32]) -> Vec<u32> {
    let mut out = Vec::with_capacity(a.len() + b.len());
    let (mut i, mut j) = (0, 0);
    while i < a.len() && j < b.len() {
        match a[i].cmp(&b[j]) {
            std::cmp::Ordering::Less => {
                out.push(a[i]);
                i += 1;
            }
            std::cmp::Ordering::Greater => {
                out.push(b[j]);
                j += 1;
            }
            std::cmp::Ordering::Equal => {
                out.push(a[i]); // x · x = x
                i += 1;
                j += 1;
            }
        }
    }
    out.extend_from_slice(&a[i..]);
    out.extend_from_slice(&b[j..]);
    out
}

// ── Symbolic F_{2^n} with ANF coefficients ──────────────────────────

/// An element of `F₂[vars][z]`: a polynomial in `z` whose coefficients
/// are ANF polynomials in Boolean variables.  Not reduced modulo the
/// field's irreducible until [`AnfF2m::reduce`] is called, which is
/// what lets degrees grow once and collapse once (lazy reduction).
#[derive(Clone, Debug, Default)]
pub struct AnfF2m {
    pub coeffs: Vec<AnfPoly>,
}

impl AnfF2m {
    pub fn zero(len: usize) -> Self {
        Self {
            coeffs: vec![AnfPoly::zero(); len],
        }
    }

    /// Lift a known field element to a constant symbolic element.
    pub fn from_const(c: &F2mElement, n: u32) -> Self {
        let raw = c.raw_bits();
        let mut coeffs = vec![AnfPoly::zero(); n as usize];
        for (i, slot) in coeffs.iter_mut().enumerate() {
            let set = (raw.get(i / 64).copied().unwrap_or(0) >> (i % 64)) & 1 == 1;
            if set {
                *slot = AnfPoly::one();
            }
        }
        Self { coeffs }
    }

    /// `Σ_{d < len} x_{offset + d} · z^d` — a free symbolic element
    /// whose coefficients are single fresh variables.
    pub fn from_vars(offset: u32, len: usize) -> Self {
        Self {
            coeffs: (0..len).map(|d| AnfPoly::var(offset + d as u32)).collect(),
        }
    }

    pub fn len(&self) -> usize {
        self.coeffs.len()
    }

    pub fn is_empty(&self) -> bool {
        self.coeffs.is_empty()
    }

    pub fn xor(&self, other: &Self) -> Self {
        let len = self.len().max(other.len());
        let mut out = Self::zero(len);
        for i in 0..len {
            if let Some(c) = self.coeffs.get(i) {
                out.coeffs[i].xor_assign(c);
            }
            if let Some(c) = other.coeffs.get(i) {
                out.coeffs[i].xor_assign(c);
            }
        }
        out
    }

    /// Polynomial multiplication (convolution).  No reduction.
    pub fn mul(&self, other: &Self) -> Self {
        if self.is_empty() || other.is_empty() {
            return Self::zero(0);
        }
        let mut out = Self::zero(self.len() + other.len() - 1);
        for (i, a) in self.coeffs.iter().enumerate() {
            if a.is_zero() {
                continue;
            }
            for (j, b) in other.coeffs.iter().enumerate() {
                if b.is_zero() {
                    continue;
                }
                let prod = a.mul(b);
                out.coeffs[i + j].xor_assign(&prod);
            }
        }
        out
    }

    /// **Squaring as relocation.**  `(Σ c_d z^d)² = Σ c_d z^{2d}`: in
    /// characteristic 2 there are no cross terms, and each `c_d` is an
    /// ANF over Boolean variables so `c_d² = c_d`.  No multiplication
    /// is performed — coefficients move from `d` to `2d` unchanged.
    pub fn square(&self) -> Self {
        if self.is_empty() {
            return Self::zero(0);
        }
        let mut out = Self::zero(2 * self.len() - 1);
        for (d, c) in self.coeffs.iter().enumerate() {
            out.coeffs[2 * d] = c.clone();
        }
        out
    }

    /// `self^k` for `k ≥ 1`, using [`AnfF2m::square`] for the powers of
    /// two and at most one real multiplication for an odd exponent.
    pub fn pow(&self, k: u32) -> Self {
        assert!(k >= 1, "pow requires a positive exponent");
        match k {
            1 => self.clone(),
            2 => self.square(),
            3 => self.square().mul(self),
            4 => self.square().square(),
            _ => {
                // General case: square-and-multiply, still paying only
                // relocations for the squarings.
                let mut result: Option<Self> = None;
                let mut base = self.clone();
                let mut e = k;
                while e > 0 {
                    if e & 1 == 1 {
                        result = Some(match result {
                            None => base.clone(),
                            Some(r) => r.mul(&base),
                        });
                    }
                    e >>= 1;
                    if e > 0 {
                        base = base.square();
                    }
                }
                result.unwrap()
            }
        }
    }

    /// Multiply by a *known* field constant.  Walks the constant's set
    /// bits and XORs a shifted copy per bit — the symbolic analogue of
    /// shift-and-add.
    pub fn mul_const(&self, c: &F2mElement, n: u32) -> Self {
        if self.is_empty() {
            return Self::zero(0);
        }
        let raw = c.raw_bits();
        let mut out = Self::zero(self.len() + n as usize - 1);
        for j in 0..n as usize {
            let set = (raw.get(j / 64).copied().unwrap_or(0) >> (j % 64)) & 1 == 1;
            if !set {
                continue;
            }
            for (i, a) in self.coeffs.iter().enumerate() {
                if !a.is_zero() {
                    let a = a.clone();
                    out.coeffs[i + j].xor_assign(&a);
                }
            }
        }
        out
    }

    /// Reduce modulo the field's irreducible, truncating to `n`
    /// coefficients.  `z^n ≡ Σ_{t ∈ low_terms} z^t`.
    pub fn reduce(&mut self, n: u32, irr: &IrreduciblePoly) {
        let n = n as usize;
        if self.coeffs.len() <= n {
            self.coeffs.resize(n, AnfPoly::zero());
            return;
        }
        for d in (n..self.coeffs.len()).rev() {
            if self.coeffs[d].is_zero() {
                continue;
            }
            let top = std::mem::replace(&mut self.coeffs[d], AnfPoly::zero());
            for &t in &irr.low_terms {
                let target = d - n + t as usize;
                let top = top.clone();
                self.coeffs[target].xor_assign(&top);
            }
        }
        self.coeffs.truncate(n);
    }

    /// Evaluate coefficient-wise at a Boolean assignment, giving the
    /// bits of the resulting `F_{2^n}` element (low coefficient first).
    pub fn eval_bits(&self, assignment: &[bool]) -> Vec<bool> {
        self.coeffs.iter().map(|c| c.eval(assignment)).collect()
    }
}

// ── Variable layout ─────────────────────────────────────────────────

/// Number of `z`-coefficients of `e_i` when each `X_j` has `l` of them:
/// `e_i` has degree `i(l − 1)`, hence `i·l − (i − 1)` coefficients.
pub fn e_len(i: usize, l: u32) -> usize {
    debug_assert!((1..=3).contains(&i));
    i * l as usize - (i - 1)
}

/// The Weil-descended, symmetrised `S₄` system for one target point.
///
/// Two variable spaces, each 0-indexed and independent; the SAT encoder
/// maps them into one numbering.
///
/// * **x-space** — `3l` variables, `x_{i,j}` at index `i·l + j` for
///   `i ∈ 0..3`, `j ∈ 0..l`, the bits of `X₁, X₂, X₃` in the factor-base
///   subspace `⟨1, z, …, z^{l−1}⟩`.
/// * **e-space** — `6l − 3` variables, `e_{i,d}` laid out consecutively
///   by `i` (see [`S4System::e_var`]).
#[derive(Clone, Debug)]
pub struct S4System {
    pub n: u32,
    pub l: u32,
    /// `correspondence[i][d]` is the coefficient of `z^d` in the
    /// `(i+1)`-th elementary symmetric function of `X₁, X₂, X₃`, as an
    /// ANF over **x-space**.  Pairing it with `e_{i,d}` gives the
    /// constraint `e_{i,d} ⊕ σ = 0`.
    pub correspondence: Vec<Vec<AnfPoly>>,
    /// The `n` Weil-descended `S₄` equations, as ANFs over **e-space**.
    /// Each is quadratic.
    pub semaev: Vec<AnfPoly>,
}

impl S4System {
    /// x-space index of the `j`-th bit of `X_{i+1}`.
    pub fn x_var(&self, i: usize, j: u32) -> u32 {
        debug_assert!(i < 3 && j < self.l);
        i as u32 * self.l + j
    }

    /// e-space index of `e_{i+1,d}`.
    pub fn e_var(&self, i: usize, d: usize) -> u32 {
        debug_assert!(i < 3 && d < e_len(i + 1, self.l));
        let mut base = 0usize;
        for k in 0..i {
            base += e_len(k + 1, self.l);
        }
        (base + d) as u32
    }

    /// Total number of x-space variables (`3l`).
    pub fn n_x_vars(&self) -> u32 {
        3 * self.l
    }

    /// Total number of e-space variables (`6l − 3`).
    pub fn n_e_vars(&self) -> u32 {
        (1..=3).map(|i| e_len(i, self.l) as u32).sum()
    }
}

// ── Building the system ─────────────────────────────────────────────

/// **Weil-descend the symmetrised Semaev `S₄`** for target x-coordinate
/// `x_r`, with the three unknown x-coordinates confined to the
/// `l`-dimensional factor-base subspace `⟨1, z, …, z^{l−1}⟩`.
///
/// Returns both halves of the model; see [`S4System`].
///
/// # Panics
///
/// If `b ≠ 1`.  The symmetrised form is specialised to the Koblitz
/// curve `y² + xy = x³ + x² + 1`; see the module docs.
pub fn weil_descend_s4(
    n: u32,
    l: u32,
    irr: &IrreduciblePoly,
    b: &F2mElement,
    x_r: &F2mElement,
) -> S4System {
    assert!(l >= 1 && l <= n, "subspace dimension l must lie in 1..=n");
    assert!(
        *b == F2mElement::one(n),
        "the symmetrised S₄ implemented here is specialised to b = 1 \
         (the Koblitz curve y² + xy = x³ + x² + 1); general b must be \
         re-derived — see the module documentation"
    );

    // ── half 1: the correspondence e_i = σ_i(X₁, X₂, X₃) ────────────
    // X_i lives in the subspace, so it has exactly l free bits.
    let xs: Vec<AnfF2m> = (0..3)
        .map(|i| AnfF2m::from_vars(i as u32 * l, l as usize))
        .collect();

    // These stay *unreduced*: e_i has degree i(l−1), and with l ≈ n/3
    // that is below n anyway.  Keeping them as plain z-polynomials is
    // what makes the e-variable count 6l−3 rather than 3n.
    let sigma1 = xs[0].xor(&xs[1]).xor(&xs[2]);
    let x0x1 = xs[0].mul(&xs[1]);
    let x0x2 = xs[0].mul(&xs[2]);
    let x1x2 = xs[1].mul(&xs[2]);
    let sigma2 = x0x1.xor(&x0x2).xor(&x1x2);
    let sigma3 = x0x1.mul(&xs[2]);

    let mut correspondence = Vec::with_capacity(3);
    for (i, sigma) in [sigma1, sigma2, sigma3].iter().enumerate() {
        let want = e_len(i + 1, l);
        let mut row = sigma.coeffs.clone();
        row.resize(want, AnfPoly::zero());
        debug_assert_eq!(row.len(), want);
        correspondence.push(row);
    }

    // ── half 2: S₄ over the e-variables ─────────────────────────────
    // Each e_i becomes a free symbolic element whose coefficients are
    // the fresh e-variables.
    let mut offset = 0u32;
    let mut e_syms = Vec::with_capacity(3);
    for i in 1..=3 {
        let len = e_len(i, l);
        e_syms.push(AnfF2m::from_vars(offset, len));
        offset += len as u32;
    }
    let (e1, e2, e3) = (&e_syms[0], &e_syms[1], &e_syms[2]);

    // Powers of the *known* constant x_R are reduced in the field
    // first, keeping every intermediate degree below n + max(deg e).
    let xr1 = x_r.clone();
    let xr2 = xr1.square(irr);
    let xr3 = xr2.mul(&xr1, irr);
    let xr4 = xr2.square(irr);

    // The symmetrised fourth summation polynomial for b = 1:
    //
    //   f₃ = x_R⁴ + e₁⁴ + e₃⁴ + e₂⁴x_R⁴ + e₃³x_R + e₃e₂²x_R³
    //        + e₃e₁²x_R + e₃x_R³ + e₁²e₃²x_R² + e₃²x_R⁴ + e₃² + e₂²x_R²
    //
    // Note how few real multiplications this needs: every `pow` with an
    // even exponent is a relocation, and `mul_const` is shift-and-add.
    let e1_2 = e1.square();
    let e2_2 = e2.square();
    let e3_2 = e3.square();
    let e1_4 = e1_2.square();
    let e2_4 = e2_2.square();
    let e3_4 = e3_2.square();
    let e3_3 = e3_2.mul(e3);

    let mut f3 = AnfF2m::zero(0);
    let terms: Vec<AnfF2m> = vec![
        AnfF2m::from_const(&xr4, n),        // x_R⁴
        e1_4,                               // e₁⁴
        e3_4,                               // e₃⁴
        e2_4.mul_const(&xr4, n),            // e₂⁴ x_R⁴
        e3_3.mul_const(&xr1, n),            // e₃³ x_R
        e3.mul(&e2_2).mul_const(&xr3, n),   // e₃ e₂² x_R³
        e3.mul(&e1_2).mul_const(&xr1, n),   // e₃ e₁² x_R
        e3.mul_const(&xr3, n),              // e₃ x_R³
        e1_2.mul(&e3_2).mul_const(&xr2, n), // e₁² e₃² x_R²
        e3_2.mul_const(&xr4, n),            // e₃² x_R⁴
        e3_2.clone(),                       // e₃²
        e2_2.mul_const(&xr2, n),            // e₂² x_R²
    ];
    for t in &terms {
        f3 = f3.xor(t);
    }

    // One reduction, at the end.
    f3.reduce(n, irr);
    debug_assert!(
        f3.coeffs.iter().all(|c| c.degree() <= 2),
        "the symmetrised system must be quadratic in the e-variables"
    );

    S4System {
        n,
        l,
        correspondence,
        semaev: f3.coeffs,
    }
}

/// Evaluate the symmetrised `f₃` directly over `F_{2ⁿ}`, for cross-
/// checking the descended system.  This is the same twelve-term
/// expression, with everything a concrete field element.
pub fn symmetrised_s4_eval(
    e1: &F2mElement,
    e2: &F2mElement,
    e3: &F2mElement,
    x_r: &F2mElement,
    irr: &IrreduciblePoly,
) -> F2mElement {
    let sq = |z: &F2mElement| z.square(irr);
    let (e1_2, e2_2, e3_2) = (sq(e1), sq(e2), sq(e3));
    let (e1_4, e2_4, e3_4) = (sq(&e1_2), sq(&e2_2), sq(&e3_2));
    let e3_3 = e3_2.mul(e3, irr);
    let xr2 = sq(x_r);
    let xr3 = xr2.mul(x_r, irr);
    let xr4 = sq(&xr2);

    let mut acc = xr4.clone();
    acc = acc.add(&e1_4);
    acc = acc.add(&e3_4);
    acc = acc.add(&e2_4.mul(&xr4, irr));
    acc = acc.add(&e3_3.mul(x_r, irr));
    acc = acc.add(&e3.mul(&e2_2, irr).mul(&xr3, irr));
    acc = acc.add(&e3.mul(&e1_2, irr).mul(x_r, irr));
    acc = acc.add(&e3.mul(&xr3, irr));
    acc = acc.add(&e1_2.mul(&e3_2, irr).mul(&xr2, irr));
    acc = acc.add(&e3_2.mul(&xr4, irr));
    acc = acc.add(&e3_2);
    acc = acc.add(&e2_2.mul(&xr2, irr));
    acc
}

/// Elementary symmetric functions of three field elements.
pub fn elementary_symmetric_3(
    x1: &F2mElement,
    x2: &F2mElement,
    x3: &F2mElement,
    irr: &IrreduciblePoly,
) -> (F2mElement, F2mElement, F2mElement) {
    let e1 = x1.add(x2).add(x3);
    let e2 = x1.mul(x2, irr).add(&x1.mul(x3, irr)).add(&x2.mul(x3, irr));
    let e3 = x1.mul(x2, irr).mul(x3, irr);
    (e1, e2, e3)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// `n = 19`, `l = 6` Koblitz parameters, taken verbatim from
    /// `INFOn19l6-1-S.dimacs` in the reference corpus (see
    /// `research/notes/ecc2k130/RESEARCH_TRIMOSKA_BENCHMARKS.md`).  The irreducible is
    /// `z¹⁹ + z⁵ + z² + z + 1`.
    fn corpus_n19l6() -> (u32, u32, IrreduciblePoly, F2mElement, [F2mElement; 3]) {
        let n = 19;
        let irr = IrreduciblePoly {
            degree: 19,
            low_terms: vec![0, 1, 2, 5],
        };
        let x_r = F2mElement::from_bit_positions(&[1, 2, 5, 6, 7, 8, 10, 11, 12, 16], n);
        let x1 = F2mElement::from_bit_positions(&[4], n);
        let x2 = F2mElement::from_bit_positions(&[2, 4, 5], n);
        let x3 = F2mElement::from_bit_positions(&[1, 4], n);
        (n, 6, irr, x_r, [x1, x2, x3])
    }

    /// **Cross-check against an independent generator.**  The planted
    /// decomposition recorded in the reference corpus must make the
    /// symmetrised `f₃` vanish.  If our twelve-term transcription were
    /// wrong, this would not hold.
    #[test]
    fn symmetrised_s4_vanishes_on_corpus_planted_solution() {
        let (n, _l, irr, x_r, xs) = corpus_n19l6();
        let (e1, e2, e3) = elementary_symmetric_3(&xs[0], &xs[1], &xs[2], &irr);
        let val = symmetrised_s4_eval(&e1, &e2, &e3, &x_r, &irr);
        assert!(
            val.is_zero(),
            "planted corpus solution must satisfy the symmetrised S₄"
        );
        let _ = n;
    }

    /// A random point of the subspace is overwhelmingly unlikely to
    /// decompose, so `f₃` should *not* vanish — a guard against a
    /// transcription that is accidentally identically zero.
    #[test]
    fn symmetrised_s4_is_not_identically_zero() {
        let (n, _l, irr, x_r, _) = corpus_n19l6();
        let y1 = F2mElement::from_bit_positions(&[0], n);
        let y2 = F2mElement::from_bit_positions(&[1], n);
        let y3 = F2mElement::from_bit_positions(&[3], n);
        let (e1, e2, e3) = elementary_symmetric_3(&y1, &y2, &y3, &irr);
        assert!(!symmetrised_s4_eval(&e1, &e2, &e3, &x_r, &irr).is_zero());
    }

    /// Squaring must be exactly relocation: same coefficients, moved
    /// from `d` to `2d`.
    #[test]
    fn square_is_relocation() {
        let a = AnfF2m::from_vars(0, 4);
        let sq = a.square();
        assert_eq!(sq.len(), 7);
        for d in 0..4 {
            assert_eq!(sq.coeffs[2 * d], a.coeffs[d], "coefficient {d} → {}", 2 * d);
            if 2 * d + 1 < sq.len() {
                assert!(sq.coeffs[2 * d + 1].is_zero(), "odd slots must be empty");
            }
        }
    }

    /// Squaring by relocation must agree with an honest multiplication.
    #[test]
    fn square_agrees_with_multiplication() {
        let a = AnfF2m::from_vars(0, 5);
        let by_mul = a.mul(&a);
        let by_shift = a.square();
        assert_eq!(by_mul.len(), by_shift.len());
        for d in 0..by_mul.len() {
            assert_eq!(by_mul.coeffs[d], by_shift.coeffs[d], "coefficient {d}");
        }
    }

    /// ANF addition is symmetric difference: adding a polynomial to
    /// itself must annihilate it.
    #[test]
    fn anf_addition_cancels() {
        let mut p = AnfPoly::var(1).mul(&AnfPoly::var(2));
        p.xor_assign(&AnfPoly::var(3));
        let q = p.clone();
        p.xor_assign(&q);
        assert!(p.is_zero(), "x ⊕ x must be 0");
    }

    /// `x · x = x`, so a squared monomial stays squarefree.
    #[test]
    fn anf_monomials_are_squarefree() {
        let x = AnfPoly::var(7);
        assert_eq!(x.mul(&x), x);
    }

    /// **End-to-end**: the descended system, evaluated at the planted
    /// solution's bits, must be all-zero — both halves.  This ties the
    /// symbolic descent to concrete field arithmetic.
    #[test]
    fn descended_system_vanishes_on_planted_solution() {
        let (n, l, irr, x_r, xs) = corpus_n19l6();
        let b = F2mElement::one(n);
        let sys = weil_descend_s4(n, l, &irr, &b, &x_r);

        // x-space assignment: the l low bits of each planted X_i.
        let mut x_assign = vec![false; sys.n_x_vars() as usize];
        for (i, x) in xs.iter().enumerate() {
            let raw = x.raw_bits();
            for j in 0..l {
                let bit = (raw[(j / 64) as usize] >> (j % 64)) & 1 == 1;
                x_assign[sys.x_var(i, j) as usize] = bit;
            }
        }

        // e-space assignment: read the e-variables off the
        // correspondence, which is exactly what it is for.
        let mut e_assign = vec![false; sys.n_e_vars() as usize];
        for i in 0..3 {
            for d in 0..e_len(i + 1, l) {
                e_assign[sys.e_var(i, d) as usize] = sys.correspondence[i][d].eval(&x_assign);
            }
        }

        // Half 1 sanity: those e-values must match the field-level
        // elementary symmetric functions of the planted X_i.
        let (e1, e2, e3) = elementary_symmetric_3(&xs[0], &xs[1], &xs[2], &irr);
        for (i, e) in [&e1, &e2, &e3].iter().enumerate() {
            // e_i is held unreduced but has degree < n here, so its
            // coefficients are directly the field element's bits.
            let raw = e.raw_bits();
            for d in 0..e_len(i + 1, l) {
                let want = (raw[d / 64] >> (d % 64)) & 1 == 1;
                let got = e_assign[sys.e_var(i, d) as usize];
                assert_eq!(got, want, "e_{}, coefficient {d}", i + 1);
            }
        }

        // Half 2: every descended equation must vanish.
        for (k, eq) in sys.semaev.iter().enumerate() {
            assert!(
                !eq.eval(&e_assign),
                "descended S₄ equation {k} did not vanish at the planted solution"
            );
        }
    }

    /// The descended system must be quadratic in the e-variables — that
    /// is the entire point of symmetrising.
    #[test]
    fn descended_system_is_quadratic() {
        let (n, l, irr, x_r, _) = corpus_n19l6();
        let b = F2mElement::one(n);
        let sys = weil_descend_s4(n, l, &irr, &b, &x_r);
        assert_eq!(sys.semaev.len(), n as usize);
        assert!(sys.semaev.iter().all(|e| e.degree() <= 2));
        // The correspondence carries the cubic part: e₃ = X₁X₂X₃.
        assert_eq!(
            sys.correspondence[0].iter().map(|p| p.degree()).max(),
            Some(1)
        );
        assert_eq!(
            sys.correspondence[1].iter().map(|p| p.degree()).max(),
            Some(2)
        );
        assert_eq!(
            sys.correspondence[2].iter().map(|p| p.degree()).max(),
            Some(3)
        );
    }

    /// A curve other than `b = 1` must be refused, not silently
    /// mis-descended.
    #[test]
    #[should_panic(expected = "specialised to b = 1")]
    fn general_b_is_rejected() {
        let (n, l, irr, x_r, _) = corpus_n19l6();
        let b = F2mElement::from_bit_positions(&[1], n);
        let _ = weil_descend_s4(n, l, &irr, &b, &x_r);
    }
}
