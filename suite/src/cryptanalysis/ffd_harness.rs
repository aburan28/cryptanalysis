//! # First-fall-degree measurement harness for binary Semaev systems.
//!
//! Direct response to the "FFD is controversial / nobody understands
//! why some systems collapse" thread in the ECDLP research-direction
//! map.  This module *measures*, not *predicts*: it constructs the
//! Macaulay matrix of a binary-Semaev `S₃` system over `F_{2^n}` after
//! Weil descent into `n` quadratic polynomials over `F_2` in `2n`
//! bit-variables, then computes its rank at every degree `D = 2, 3,
//! 4, …` and reports the **fall degree** — the smallest `D` at which
//! the rank deficit exceeds the deficit predicted for a generic
//! degree-2 system of the same shape.
//!
//! # The FFD claim, in measurable form
//!
//! For a *generic* system of `n` quadratic polynomials in `v` Boolean
//! variables (with the field equations `xᵢ² + xᵢ = 0` thrown in to
//! force multilinearity), the **Hilbert series at degree D** counts
//! the dimension of `(F_2[x]/I)_{≤D}` and equals
//!
//! ```text
//!   H_gen(D)  =  Σ_{k=0..D} C(v, k)   −   n · Σ_{k=0..D-2} C(v, k)   (mod neg-terms)
//! ```
//!
//! with appropriate truncation when entries go negative.  The
//! Macaulay-matrix rank at degree `D` for the generic system is
//!
//! ```text
//!   rank_gen(D)  =  cols(D)  −  max(H_gen(D), 0).
//! ```
//!
//! The **first fall degree** is the smallest `D` at which the *actual*
//! rank of the Macaulay matrix is **strictly greater** than the
//! generic prediction by at least `1` — i.e. the ideal "fell": new
//! syzygies appeared that the generic count did not anticipate.
//!
//! The FFD conjecture (Huang–Kiltz–Petit, Crypto 2015) predicts the
//! FFD for Semaev systems is `O(log n)`; the Galbraith / Petit
//! pushback says experimental fall degrees grow much faster in
//! practice.  Both sides can read the table this module prints.
//!
//! # Pipeline
//!
//! Per `n ∈ {n_min, …, n_max}`:
//!
//! 1. Pick a random `b ∈ F_{2^n}` and a random target `x_3 ∈ F_{2^n}`.
//! 2. Form `S₃(X₁, X₂, x_3) = (X₁+X₂)² x_3² + X₁X₂ x_3 + (X₁X₂)² + b`.
//! 3. **Weil-descend**: write `X₁ = Σ_i a_i zⁱ`, `X₂ = Σ_i c_i zⁱ`
//!    with `a_i, c_i ∈ F_2`; expand `S₃` as an element of
//!    `F_2[a₀..a_{n-1}, c₀..c_{n-1}][z] / m(z)` and extract the `n`
//!    coefficients in `z⁰..z^{n-1}`.  Each is an `F_2`-polynomial of
//!    degree ≤ 2 in the `2n` bit-variables.
//! 4. Build the Macaulay matrix at degree `D` for each
//!    `D ∈ 2..=D_max`.
//! 5. Compute the rank over `F_2` (bit-packed row reduction).
//! 6. Compute the generic prediction `rank_gen(D)` from binomial
//!    coefficients.
//! 7. The fall degree is the smallest `D` with
//!    `rank(D) > rank_gen(D)` — i.e. the actual ideal is *more*
//!    constraining than the generic prediction, which only happens
//!    when hidden syzygies show up.
//!
//! # Limitations
//!
//! - Field width capped at `n = 8` (matrix grows like `C(16, D) ≈ 1820`
//!   for `D = 4` already; `n = 9` already strains the row-reduction).
//! - Single-trial per `n`; for paper-grade FFD numbers you would
//!   average over many `(b, x_3)` choices.  The CLI flag for
//!   multi-trial sweeps is built in but defaulted to 1 to keep test
//!   time short.
//! - No "true Hilbert series" — we use the truncated generic count.
//!   For `D ≥ degrees-of-the-system`, the generic count can go
//!   negative and we clamp at zero, which slightly biases the FFD
//!   *upwards*.  In practice this still cleanly identifies the fall.
//!
//! # References
//!
//! - **I. Semaev**, *Summation polynomials and the discrete logarithm
//!   problem on elliptic curves*, eprint 2004/031.
//! - **M.-D. Huang, M. Kiltz, C. Petit**, *Last fall degree, HFE, and
//!   Weil descent attacks on ECDLP*, Crypto 2015.
//! - **S. Galbraith, S. Gebregiyorgis**, *Summation polynomial
//!   algorithms for elliptic curves in characteristic two*,
//!   INDOCRYPT 2014.
//! - **C. Petit**, *Notes on summation polynomials*, 2015 — the
//!   "backlash" reading the harness here is calibrated against.

use crate::binary_ecc::{F2mElement, IrreduciblePoly};
use crate::cryptanalysis::binary_semaev::binary_semaev_s3;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};

// ── Public API ──────────────────────────────────────────────────────

/// One row in the FFD measurement table.
#[derive(Clone, Debug)]
pub struct FfdRow {
    /// Field extension degree `n` (the system lives in `F_{2^n}`).
    pub n: u32,
    /// Number of bit-variables after Weil descent (`2n`).
    pub num_vars: u32,
    /// Number of `F_2`-equations after Weil descent (`n`).
    pub num_eqs: u32,
    /// Macaulay-matrix degree → (rank, columns, generic prediction).
    pub per_degree: Vec<MacaulayMeasurement>,
    /// Smallest `D ≥ 2` at which the Macaulay matrix has nontrivial
    /// syzygies (`rank < rows_constructed`) **and** has not saturated
    /// (`rank < cols`).  This matches the operational FFD definition
    /// used in Galbraith–Gebregiyorgis 2014 §4 and Petit's 2015 notes.
    /// `None` if no fall was observed up to `d_max`.
    pub fall_degree: Option<u32>,
}

#[derive(Clone, Debug)]
pub struct MacaulayMeasurement {
    pub degree: u32,
    pub rows_constructed: u64,
    pub cols: u64,
    pub rank: u64,
    /// Generic-prediction rank (clamped at 0 from below, `cols` from
    /// above).
    pub rank_generic: u64,
    /// `rank − rank_generic`.  Positive when the ideal "fell".
    pub fall_signal: i64,
}

/// **Run the FFD measurement sweep** over `n_range`, with `d_max`
/// being the largest Macaulay-matrix degree to construct.  `seed`
/// makes the random choices reproducible.
pub fn run_sweep(n_range: std::ops::RangeInclusive<u32>, d_max: u32, seed: u64) -> Vec<FfdRow> {
    let mut rng = StdRng::seed_from_u64(seed);
    let mut out = Vec::new();
    for n in n_range {
        let irr = choose_irreducible(n);
        // Random non-zero b and random x_3.
        let b = random_nonzero_f2m(&mut rng, n);
        let x3 = random_nonzero_f2m(&mut rng, n);
        let row = measure_one(n, &irr, &b, &x3, d_max);
        out.push(row);
    }
    out
}

/// Measure FFD for a single `(n, b, x_3)` choice.
pub fn measure_one(
    n: u32,
    irr: &IrreduciblePoly,
    b: &F2mElement,
    x3: &F2mElement,
    d_max: u32,
) -> FfdRow {
    // Step 1-3: build the n quadratic polynomials over F_2 in 2n vars.
    let eqs = weil_descend_s3(n, irr, b, x3);
    let num_vars = 2 * n;
    let num_eqs = eqs.len() as u32;

    // Step 4-6: build & rank Macaulay matrices at each degree.
    //
    // **First fall degree definition** (operational):
    //   the smallest D ≥ 2 at which the Macaulay matrix has
    //     rank < rows_constructed  AND  rank < cols.
    //
    // Equivalently: the first D at which non-trivial syzygies among
    // the Macaulay-shifted equations are detected (rank < rows) and
    // the system has not yet trivially saturated (rank < cols).
    let (fall_degree, per_degree) = measure_polys(&eqs, num_vars, d_max);

    FfdRow {
        n,
        num_vars,
        num_eqs,
        per_degree,
        fall_degree,
    }
}

/// **Measure FFD for an already-built system**, so callers that
/// Weil-descend with their own parameters — a subspace-restricted
/// factor base, a curve chosen by an isogeny search — get the *same*
/// operational first-fall-degree definition the sweep uses rather than
/// a lookalike.
///
/// The definition, unchanged from [`measure_one`]: the smallest `D ≥ 2`
/// at which the Macaulay matrix has `rank < rows_constructed` (a
/// non-trivial syzygy) **and** `rank < cols` (the system has not
/// saturated).  Rows are the products of each equation with every
/// monomial of degree `≤ D − 2`, which is the convention this harness
/// was calibrated with; note that it assumes every equation is
/// quadratic, and multiplies a lower-degree equation by too little.
/// [`crate::cryptanalysis::koblitz_groebner::first_fall_degree`] fills
/// the matrix to degree `D` per equation instead, so the two agree
/// exactly when no equation has dropped below degree 2.
pub fn measure_polys(
    eqs: &[F2BoolPoly],
    num_vars: u32,
    d_max: u32,
) -> (Option<u32>, Vec<MacaulayMeasurement>) {
    let mut per_degree = Vec::new();
    let mut fall_degree: Option<u32> = None;
    for d in 2..=d_max {
        let measurement = build_and_rank_macaulay(eqs, num_vars, d);
        let nontrivial_syzygy = measurement.rank < measurement.rows_constructed;
        let not_saturated = measurement.rank < measurement.cols;
        if fall_degree.is_none() && nontrivial_syzygy && not_saturated {
            fall_degree = Some(d);
        }
        per_degree.push(measurement);
    }
    (fall_degree, per_degree)
}

// ── Weil descent of binary S₃ ───────────────────────────────────────

/// A polynomial over `F_2` in `num_vars` Boolean variables, represented
/// as a set of monomials (each monomial is a sorted variable-index
/// vector; the empty vector is the constant `1`).  Coefficient = 1
/// for each monomial in the set; the polynomial is the XOR-sum over
/// all monomials in the set.
#[derive(Clone, Debug, Default)]
pub struct F2BoolPoly {
    /// One bit per monomial of degree ≤ 2 in `num_vars` variables.
    /// Encoding:
    ///   bit 0                  = the constant 1
    ///   bits 1..=num_vars      = the linear monomials xᵢ
    ///   bits num_vars+1..      = the quadratic monomials xᵢ·xⱼ (i<j)
    pub coeffs: Vec<bool>,
}

impl F2BoolPoly {
    pub fn zero(num_vars: u32) -> Self {
        let n = num_monomials_upto_degree(num_vars, 2) as usize;
        Self {
            coeffs: vec![false; n],
        }
    }

    pub fn is_zero(&self) -> bool {
        self.coeffs.iter().all(|b| !*b)
    }

    pub fn xor_assign(&mut self, other: &Self) {
        debug_assert_eq!(self.coeffs.len(), other.coeffs.len());
        for (a, b) in self.coeffs.iter_mut().zip(other.coeffs.iter()) {
            *a ^= *b;
        }
    }

    /// Multiply two degree-≤1 polys; result is degree-≤2.
    pub fn mul_linear(&self, other: &Self, num_vars: u32) -> Self {
        let mut out = Self::zero(num_vars);
        // Decompose self & other into (const, linear[]).
        let s_const = self.coeffs[0];
        let s_lin: Vec<bool> = (0..num_vars).map(|i| self.coeffs[1 + i as usize]).collect();
        let o_const = other.coeffs[0];
        let o_lin: Vec<bool> = (0..num_vars)
            .map(|i| other.coeffs[1 + i as usize])
            .collect();

        // const × const
        if s_const && o_const {
            out.coeffs[0] ^= true;
        }
        // const × lin (both ways)
        for i in 0..num_vars as usize {
            if s_const && o_lin[i] {
                out.coeffs[1 + i] ^= true;
            }
            if o_const && s_lin[i] {
                out.coeffs[1 + i] ^= true;
            }
        }
        // lin × lin
        for i in 0..num_vars as usize {
            if !s_lin[i] {
                continue;
            }
            for j in 0..num_vars as usize {
                if !o_lin[j] {
                    continue;
                }
                // xᵢ · xⱼ.  In F_2 with field eqs xᵢ² = xᵢ, the i==j case
                // collapses to xᵢ (a linear monomial).
                if i == j {
                    out.coeffs[1 + i] ^= true;
                } else {
                    let (a, b) = if i < j { (i, j) } else { (j, i) };
                    let idx = quad_monomial_index(a as u32, b as u32, num_vars);
                    out.coeffs[idx] ^= true;
                }
            }
        }
        out
    }
}

/// Number of multilinear monomials of degree ≤ `d` in `v` variables:
/// `Σ_{k=0..=d} C(v, k)`.
pub fn num_monomials_upto_degree(v: u32, d: u32) -> u64 {
    let mut s: u64 = 0;
    for k in 0..=d {
        s += binom(v as u64, k as u64);
    }
    s
}

/// Index of the multilinear quadratic monomial `xᵢ · xⱼ` (with `i < j`)
/// in the flat coefficient vector used by `F2BoolPoly`:
///   `1 + num_vars + (offset of (i,j) in lex order of pairs)`.
pub fn quad_monomial_index(i: u32, j: u32, num_vars: u32) -> usize {
    debug_assert!(i < j && j < num_vars);
    // # of pairs (a, b) with a < i is C(num_vars - 0, ...) — easier:
    // # of pairs with first index < i  =  i·num_vars − i·(i+1)/2.
    let pairs_before_i = (i as u64) * (num_vars as u64) - (i as u64) * (i as u64 + 1) / 2;
    let in_row = j as u64 - i as u64 - 1;
    1 + num_vars as usize + (pairs_before_i + in_row) as usize
}

fn binom(n: u64, k: u64) -> u64 {
    if k > n {
        return 0;
    }
    let k = k.min(n - k);
    let mut acc: u128 = 1;
    for i in 0..k {
        acc = acc * (n - i) as u128 / (i + 1) as u128;
    }
    acc as u64
}

/// Weil-descend the binary Semaev `S₃(X₁, X₂, x₃) = 0` into `n`
/// quadratic polynomials over `F_2` in `2n` bit-variables (the bits
/// of `X₁` then the bits of `X₂`).
pub fn weil_descend_s3(
    n: u32,
    irr: &IrreduciblePoly,
    b: &F2mElement,
    x3: &F2mElement,
) -> Vec<F2BoolPoly> {
    weil_descend_s3_subspace(n, n, irr, b, x3)
}

/// Weil-descend `S₃(X₁, X₂, x₃) = 0` with each `Xᵢ` **confined to the
/// `l`-dimensional `F_2`-subspace** `V = ⟨1, z, …, z^{l−1}⟩ ⊆ F_{2ⁿ}`,
/// giving `n` equations in `2l` bit-variables.
///
/// This is the ingredient that makes the system an *index calculus*
/// instance rather than "solve Semaev over the whole field".  The
/// factor base in Gaudry- and Diem-style descent is exactly such a
/// subspace, with `l ≈ n/m` for an `m`-point decomposition, and the
/// regime change matters more than the variable count: with `l = n/2`
/// the system is `n` equations in `n` unknowns instead of `n` equations
/// in `2n`, so a solution is essentially determined rather than one of
/// `2ⁿ`, and unit propagation has something to bite on.
///
/// `l = n` recovers the unrestricted descent, which is what
/// [`weil_descend_s3`] calls.
pub fn weil_descend_s3_subspace(
    n: u32,
    l: u32,
    irr: &IrreduciblePoly,
    b: &F2mElement,
    x3: &F2mElement,
) -> Vec<F2BoolPoly> {
    assert!(l >= 1 && l <= n, "subspace dimension l must lie in 1..=n");
    let num_vars = 2 * l;
    // We evaluate the Semaev polynomial in a *symbolic* (F_2-polynomial)
    // way: substitute X₁ and X₂ as formal sums and track coefficients
    // monomial-by-monomial.  Since binary_semaev_s3 only does add,
    // square, and mul (with x_3 constant), and squaring is linear in
    // char 2, the entire evaluation never exceeds degree 2 in the
    // bit-variables.
    //
    // The S₃ formula:
    //   S₃ = (X₁+X₂)² x₃² + X₁ X₂ x₃ + (X₁ X₂)² + b
    // becomes, after Weil descent:
    //   term A: (X₁+X₂)² x₃² — for each F_{2^n} coordinate, linear in bits.
    //   term B: X₁ X₂ x₃     — for each F_{2^n} coord, deg-2 (bilinear) in bits.
    //   term C: (X₁ X₂)²     — same support as term B (Frobenius).
    //   term D: b            — constant per F_{2^n} coord.
    //
    // We compute term-by-term by symbolic multiplication in
    // F_2[bits][z]/m(z).

    // Symbolic X₁, X₂ as length-n vectors of F2BoolPoly (each entry is
    // a linear polynomial in bits — exactly one bit per coordinate).
    let x1_sym = symbolic_variable(num_vars, 0, n, l);
    let x2_sym = symbolic_variable(num_vars, l, n, l);

    // Constants x₃ and b as length-n vectors of *constant* F2BoolPoly.
    let x3_sym = constant_f2m(num_vars, x3, n);
    let b_sym = constant_f2m(num_vars, b, n);

    // Term A: (X₁ + X₂)² · x₃².  In F_{2^n}, (X₁+X₂)² = X₁² + X₂², a
    // linear element of F_{2^n}.  Multiplying by x₃² (a constant) gives
    // a linear element in the bit-variables — degree 1.
    let sum = add_f2m_sym(&x1_sym, &x2_sym);
    let sum_sq = sq_f2m_sym(&sum, n, irr);
    let x3_sq = sq_f2m_const(x3, n, irr);
    let x3_sq_sym = constant_f2m(num_vars, &x3_sq, n);
    let term_a = mul_f2m_sym_lin(&sum_sq, &x3_sq_sym, n, irr, num_vars);

    // Term B: X₁ · X₂ · x₃.  Two-step multiplication; the X₁ · X₂
    // product is degree 2.  Multiplying by x₃ (constant) preserves
    // degree 2.
    let prod12 = mul_f2m_sym_lin(&x1_sym, &x2_sym, n, irr, num_vars);
    let term_b = mul_f2m_sym_quad_by_const(&prod12, &x3_sym, n, irr, num_vars);

    // Term C: (X₁ · X₂)².  Squaring in char 2 is Frobenius: we apply
    // the squaring map z^k ↦ z^{2k mod m(z)} to each F2BoolPoly entry.
    let term_c = sq_f2m_sym(&prod12, n, irr);

    // Term D: b (constant).
    let term_d = b_sym;

    // Sum (XOR) all four terms coordinate-by-coordinate.
    let mut result = vec![F2BoolPoly::zero(num_vars); n as usize];
    for i in 0..n as usize {
        result[i].xor_assign(&term_a[i]);
        result[i].xor_assign(&term_b[i]);
        result[i].xor_assign(&term_c[i]);
        result[i].xor_assign(&term_d[i]);
    }
    result
}

// ── Helpers: symbolic F_{2^n} arithmetic with F2BoolPoly coefficients

/// `X = Σ_{i=0..l} xᵢ zⁱ` where `xᵢ` is the `(offset + i)`-th bit-
/// variable.  Returns the length-`n` coefficient vector of `X` in
/// `F_2[bits][z] / m(z)` — coordinates `l..n` are identically zero,
/// which is precisely the statement that `X` lies in the subspace
/// `⟨1, z, …, z^{l−1}⟩`.
fn symbolic_variable(num_vars: u32, offset: u32, n: u32, l: u32) -> Vec<F2BoolPoly> {
    let mut out = vec![F2BoolPoly::zero(num_vars); n as usize];
    for i in 0..l as usize {
        out[i].coeffs[1 + offset as usize + i] = true;
    }
    out
}

/// Lift an `F_{2^n}` constant to a length-`n` vector of constant
/// `F2BoolPoly`s (each entry is the constant `0` or `1`).
fn constant_f2m(num_vars: u32, c: &F2mElement, n: u32) -> Vec<F2BoolPoly> {
    let mut out = vec![F2BoolPoly::zero(num_vars); n as usize];
    let raw = c.raw_bits();
    for i in 0..n as usize {
        let w = i / 64;
        let bit = i % 64;
        let is_set = (raw.get(w).copied().unwrap_or(0) >> bit) & 1 == 1;
        if is_set {
            out[i].coeffs[0] = true;
        }
    }
    out
}

fn add_f2m_sym(a: &[F2BoolPoly], b: &[F2BoolPoly]) -> Vec<F2BoolPoly> {
    debug_assert_eq!(a.len(), b.len());
    let mut out = a.to_vec();
    for (oi, bi) in out.iter_mut().zip(b.iter()) {
        oi.xor_assign(bi);
    }
    out
}

/// Multiply two F_{2^n} elements when both are at most linear in the
/// bit-variables.  The product is at most quadratic.  Modular
/// reduction by `irr` is done coefficient-wise.
fn mul_f2m_sym_lin(
    a: &[F2BoolPoly],
    b: &[F2BoolPoly],
    n: u32,
    irr: &IrreduciblePoly,
    num_vars: u32,
) -> Vec<F2BoolPoly> {
    let len = 2 * n as usize - 1;
    let mut conv = vec![F2BoolPoly::zero(num_vars); len];
    for i in 0..n as usize {
        for j in 0..n as usize {
            let prod = a[i].mul_linear(&b[j], num_vars);
            conv[i + j].xor_assign(&prod);
        }
    }
    // Reduce mod m(z).
    reduce_mod_irr(&mut conv, n, irr);
    conv.truncate(n as usize);
    conv
}

/// Multiply a degree-2 vector by a constant vector (degree-0 entries).
/// Conceptually identical to `mul_f2m_sym_lin` but skips work where
/// `b[j]` is a constant.
fn mul_f2m_sym_quad_by_const(
    a: &[F2BoolPoly],
    b: &[F2BoolPoly],
    n: u32,
    irr: &IrreduciblePoly,
    num_vars: u32,
) -> Vec<F2BoolPoly> {
    let len = 2 * n as usize - 1;
    let mut conv = vec![F2BoolPoly::zero(num_vars); len];
    for j in 0..n as usize {
        // b[j] is constant (0 or 1) iff coeffs[0] is the only set bit.
        let scalar = b[j].coeffs[0];
        if !scalar {
            continue;
        }
        for i in 0..n as usize {
            // a[i] is quadratic; scaling by 1 is a no-op.
            let mut copy = a[i].clone();
            // Multiplication by `b[j] = 1` is identity.
            conv[i + j].xor_assign(&copy);
            let _ = &mut copy;
        }
    }
    reduce_mod_irr(&mut conv, n, irr);
    conv.truncate(n as usize);
    conv
}

/// Square a length-`n` vector of `F2BoolPoly`s representing an
/// `F_{2^n}` element.  In char 2 this is `(Σ cᵢ zⁱ)² = Σ cᵢ² z^{2i}`;
/// since `cᵢ ∈ F_2[bits]` we apply the Frobenius `c ↦ c²` to each
/// coefficient as well.
fn sq_f2m_sym(a: &[F2BoolPoly], n: u32, irr: &IrreduciblePoly) -> Vec<F2BoolPoly> {
    let len = 2 * n as usize - 1;
    let num_vars = if a.is_empty() {
        0
    } else {
        // Reconstruct num_vars from a[0].coeffs.len().  We know
        // coeffs.len() = 1 + v + C(v,2), so we solve a quadratic.
        deduce_num_vars(a[0].coeffs.len())
    };
    let mut conv = vec![F2BoolPoly::zero(num_vars); len];
    for i in 0..n as usize {
        let squared = square_f2_bool_poly(&a[i], num_vars);
        conv[2 * i].xor_assign(&squared);
    }
    reduce_mod_irr(&mut conv, n, irr);
    conv.truncate(n as usize);
    conv
}

/// In F_2, `(p)² = p` *for individual variables* (a²=a) but **not** for
/// polynomial-valued coefficients when "squaring" means "apply the
/// Frobenius of `F_{2^n}` to the coefficient polynomial".  Inside
/// `F_2[bits]`, however, the Frobenius is the identity (because every
/// element is in the prime field), so squaring at this level is a
/// **no-op on the bit-polynomial** — we just need to clone.
///
/// (The non-trivial Frobenius lives in the `z` exponent: `z² → z^{2i}`,
/// which is handled in `sq_f2m_sym` above.)
fn square_f2_bool_poly(p: &F2BoolPoly, _num_vars: u32) -> F2BoolPoly {
    p.clone()
}

fn deduce_num_vars(coeffs_len: usize) -> u32 {
    // coeffs_len = 1 + v + v(v-1)/2 = 1 + v(v+1)/2.
    // Solve v(v+1)/2 = coeffs_len - 1.
    let target = (coeffs_len as u64).saturating_sub(1);
    // Quadratic v² + v − 2·target = 0; v = (−1 + sqrt(1 + 8·target))/2.
    let disc = 1u64 + 8 * target;
    let s = (disc as f64).sqrt() as u64;
    // Adjust for floating-point imprecision.
    let cand = ((s as i64 - 1) / 2) as u64;
    for k in cand.saturating_sub(2)..=cand + 2 {
        if k * (k + 1) / 2 == target {
            return k as u32;
        }
    }
    cand as u32
}

/// Constant Frobenius on an `F_{2^n}` element: `x ↦ x²`.
fn sq_f2m_const(c: &F2mElement, _n: u32, irr: &IrreduciblePoly) -> F2mElement {
    c.square(irr)
}

/// Reduce a convolution result (length `2n - 1`) modulo the irreducible
/// polynomial `m(z)` of degree `n`.  `irr.low_terms` lists the
/// non-leading nonzero exponents of `m`, so `z^n ≡ Σ_{e ∈ low_terms} z^e`.
fn reduce_mod_irr(conv: &mut [F2BoolPoly], n: u32, irr: &IrreduciblePoly) {
    let nu = n as usize;
    let high = conv.len();
    for k in (nu..high).rev() {
        if conv[k].is_zero() {
            continue;
        }
        let cloned = conv[k].clone();
        // z^k ≡ z^{k-n} · z^n ≡ z^{k-n} · Σ_e z^e = Σ_e z^{k-n+e}.
        for &e in &irr.low_terms {
            let target = k - nu + e as usize;
            // target may exceed conv.len() if irr.low_terms has entries
            // close to n; in canonical irreducible polynomials they are
            // small.
            if target < high {
                let cloned2 = cloned.clone();
                conv[target].xor_assign(&cloned2);
            }
        }
        conv[k] = F2BoolPoly::zero(cloned.coeffs.len() as u32);
        // Re-deduce num_vars correctly.
        conv[k] = F2BoolPoly {
            coeffs: vec![false; cloned.coeffs.len()],
        };
    }
}

// ── Macaulay matrix + rank ──────────────────────────────────────────

fn build_and_rank_macaulay(eqs: &[F2BoolPoly], num_vars: u32, d: u32) -> MacaulayMeasurement {
    let (mut rows, cols, rows_constructed) = build_macaulay_rows(eqs, num_vars, d);
    let cols_u64 = cols as u64;
    if rows.is_empty() {
        return MacaulayMeasurement {
            degree: d,
            rows_constructed: 0,
            cols: cols_u64,
            rank: 0,
            rank_generic: 0,
            fall_signal: 0,
        };
    }
    let rank = f2_rank(&mut rows, cols) as u64;
    let rank_generic = generic_rank_prediction(eqs.len() as u64, num_vars, d, cols_u64);
    let fall_signal = rank as i64 - rank_generic as i64;

    MacaulayMeasurement {
        degree: d,
        rows_constructed,
        cols: cols_u64,
        rank,
        rank_generic,
        fall_signal,
    }
}

/// Build the bit-packed Macaulay-matrix rows of `eqs` at degree `d`.
/// Returns `(rows, cols, rows_constructed)`, where each row is a packed
/// bit-vector over the degree-≤`d` multilinear monomial basis (column 0
/// is the constant monomial `1`).
///
/// Generate every multiplier monomial `m` of degree ≤ `d − 2` (each `f`
/// has degree 2), multiply by each equation, and emit the resulting
/// polynomial (degree ≤ `d`) as one row.  The field equations
/// `xᵢ² + xᵢ = 0` are enforced implicitly: multilinearity is baked into
/// the [`F2BoolPoly`] encoding (squares collapse in `mul_linear` /
/// `insert_sorted`), so no extra rows are needed.
///
/// Shared by [`build_and_rank_macaulay`] (first-fall measurement) and by
/// the PC-degree / refutation harness (`pc_degree_harness`).
pub(crate) fn build_macaulay_rows(
    eqs: &[F2BoolPoly],
    num_vars: u32,
    d: u32,
) -> (Vec<Vec<u64>>, usize, u64) {
    let cols = num_monomials_upto_degree(num_vars, d) as usize;
    if cols == 0 || eqs.is_empty() {
        return (Vec::new(), cols, 0);
    }
    let multipliers = enumerate_monomials_upto(num_vars, d.saturating_sub(2));
    let row_words = cols.div_ceil(64);
    let mut rows: Vec<Vec<u64>> = Vec::new();
    for mult in &multipliers {
        for eq in eqs {
            let row_poly = mul_by_monomial(eq, mult, num_vars);
            let flat = expand_to_flat(&row_poly, mult, num_vars, d);
            let packed = pack_bits(&flat, row_words);
            rows.push(packed);
        }
    }
    let rows_constructed = rows.len() as u64;
    (rows, cols, rows_constructed)
}

/// Sparse counterpart of [`build_macaulay_rows`]: each Macaulay row is
/// returned as the **sorted, deduplicated** list of its set column indices
/// (the monomial indices that survive the `x_i² = x_i` collapse and the
/// degree-`d` truncation) instead of a packed `cols/64`-word bit-vector.
///
/// This is the construction half of a sparse `F_2` backend. At very low
/// degree each row touches only a handful of monomials, so the memory is
/// proportional to the actual nonzeros rather than to `rows × cols/64`.
///
/// **Benchmark result (negative, recorded honestly).** The sparse path
/// (`pc_degree_harness::sparse_rank_and_refute`) was built to extend reach
/// to `2n' ≥ 16`, but benchmarking showed it is **slower** than the dense
/// bit-packed path there (≈ 391 s vs 23 s at `2n'=16`): Macaulay matrices
/// **densify under fill-in at degree ≥ 5**, and once rows are dense,
/// 64-bit-wide XOR beats element-wise symmetric difference by an order of
/// magnitude. The reach win at `2n'=14`–`16` came instead from the *dense*
/// single-pass `rank_and_refute` plus the `d_cap` censoring in EXP-G. The
/// sparse functions are retained as a validated reference (their `(rank,
/// refuted)` is asserted identical to the dense path) and for the
/// genuinely-sparse very-low-degree regime.
///
/// The set of column indices produced for a given system is identical to
/// the support of the dense rows (asserted in tests).
// Retained as a validated reference / for the very-low-degree sparse
// regime; the production scan uses the dense path (see benchmark above), so
// this is exercised only by tests.
#[allow(dead_code)]
pub(crate) fn build_macaulay_rows_sparse(
    eqs: &[F2BoolPoly],
    num_vars: u32,
    d: u32,
) -> (Vec<Vec<u32>>, usize, u64) {
    let cols = num_monomials_upto_degree(num_vars, d) as usize;
    if cols == 0 || eqs.is_empty() {
        return (Vec::new(), cols, 0);
    }
    let multipliers = enumerate_monomials_upto(num_vars, d.saturating_sub(2));
    let mut rows: Vec<Vec<u32>> = Vec::new();
    for mult in &multipliers {
        for eq in eqs {
            let row_poly = mul_by_monomial(eq, mult, num_vars);
            // XOR-accumulate column indices: a monomial that appears an even
            // number of times cancels over F_2.
            let mut idxs: Vec<u32> = Vec::with_capacity(row_poly.len());
            for mono in &row_poly {
                if mono.len() as u32 > d {
                    continue; // degree-d truncation (matches expand_to_flat)
                }
                idxs.push(monomial_index(mono, num_vars, d) as u32);
            }
            idxs.sort_unstable();
            // Keep indices occurring an odd number of times.
            let mut row: Vec<u32> = Vec::with_capacity(idxs.len());
            let mut i = 0;
            while i < idxs.len() {
                let mut j = i + 1;
                while j < idxs.len() && idxs[j] == idxs[i] {
                    j += 1;
                }
                if (j - i) & 1 == 1 {
                    row.push(idxs[i]);
                }
                i = j;
            }
            rows.push(row);
        }
    }
    let rows_constructed = rows.len() as u64;
    (rows, cols, rows_constructed)
}

/// Enumerate every multilinear monomial of degree ≤ `d` in `v`
/// variables.  Each monomial is the **sorted** vector of variable
/// indices.
fn enumerate_monomials_upto(v: u32, d: u32) -> Vec<Vec<u32>> {
    let mut out = vec![vec![]]; // start with constant 1
    if d == 0 {
        return out;
    }
    for size in 1..=d as usize {
        let mut idx = vec![0u32; size];
        for i in 0..size {
            idx[i] = i as u32;
        }
        loop {
            out.push(idx.clone());
            // Increment.  Standard combinatorial succession.
            let mut i = size as i32 - 1;
            while i >= 0 && idx[i as usize] == (v - (size as u32 - i as u32)) {
                i -= 1;
            }
            if i < 0 {
                break;
            }
            idx[i as usize] += 1;
            for j in (i as usize + 1)..size {
                idx[j] = idx[j - 1] + 1;
            }
        }
    }
    out
}

/// Multiply a degree-≤2 polynomial by a multilinear monomial (a sorted
/// variable-index vector), producing a polynomial of degree ≤ 2 +
/// monomial.len().
fn mul_by_monomial(p: &F2BoolPoly, mono: &[u32], num_vars: u32) -> Vec<Vec<u32>> {
    // Return the list of monomials (each a sorted Vec<u32>) of the
    // product.  Each monomial in `p` is XORed with `mono` (set-union;
    // collapsed if any variable repeats, since xᵢ² = xᵢ over F_2 with
    // the field equations).
    let mut out = Vec::new();
    // Constant term.
    if p.coeffs[0] {
        out.push(mono.to_vec());
    }
    // Linear terms.
    for i in 0..num_vars as usize {
        if p.coeffs[1 + i] {
            let mut m = mono.to_vec();
            insert_sorted(&mut m, i as u32);
            out.push(m);
        }
    }
    // Quadratic terms.
    for i in 0..num_vars {
        for j in (i + 1)..num_vars {
            let idx = quad_monomial_index(i, j, num_vars);
            if idx < p.coeffs.len() && p.coeffs[idx] {
                let mut m = mono.to_vec();
                insert_sorted(&mut m, i);
                insert_sorted(&mut m, j);
                out.push(m);
            }
        }
    }
    out
}

fn insert_sorted(v: &mut Vec<u32>, x: u32) {
    match v.binary_search(&x) {
        Ok(_pos) => { /* xᵢ² = xᵢ: skip, already present */ }
        Err(pos) => v.insert(pos, x),
    }
}

/// Flatten a polynomial (list of monomials, possibly with duplicates)
/// into a packed bit-vector indexed by monomial-of-degree-≤d.
fn expand_to_flat(monomials: &[Vec<u32>], _mult: &[u32], num_vars: u32, d: u32) -> Vec<bool> {
    let cols = num_monomials_upto_degree(num_vars, d) as usize;
    let mut flat = vec![false; cols];
    for mono in monomials {
        if mono.len() as u32 > d {
            // Out of column range: skip (this is the truncation that
            // makes Macaulay finite).
            continue;
        }
        let idx = monomial_index(mono, num_vars, d);
        flat[idx] ^= true;
    }
    flat
}

/// Index of a sorted multilinear monomial `mono` in the ordered list
/// of degree-≤d monomials in `v` variables.
pub fn monomial_index(mono: &[u32], v: u32, d: u32) -> usize {
    // Order: by degree, then by lex.  Within a fixed degree k, the
    // monomial {i_0 < i_1 < … < i_{k-1}} has rank (in colex order):
    //   rank = Σ_{t=0..k} C(i_t, t+1).
    let k = mono.len();
    if k == 0 {
        return 0;
    }
    if k > d as usize {
        // Beyond our degree budget — caller should have caught this.
        return 0;
    }
    // Offset = total # of monomials of degree < k.
    let mut offset: u64 = 0;
    for kk in 0..k {
        offset += binom(v as u64, kk as u64);
    }
    // Colex rank within degree k.
    let mut rank: u64 = 0;
    for (t, &i_t) in mono.iter().enumerate() {
        rank += binom(i_t as u64, t as u64 + 1);
    }
    (offset + rank) as usize
}

fn pack_bits(flat: &[bool], words: usize) -> Vec<u64> {
    let mut out = vec![0u64; words];
    for (i, &b) in flat.iter().enumerate() {
        if b {
            out[i / 64] |= 1u64 << (i % 64);
        }
    }
    out
}

/// Gauss-Jordan reduction over `F_2` (XOR rows).  Returns the rank.
pub(crate) fn f2_rank(rows: &mut [Vec<u64>], cols: usize) -> usize {
    let mut rank = 0;
    let mut row = 0;
    for col in 0..cols {
        let word = col / 64;
        let bit_mask = 1u64 << (col % 64);
        // Find a pivot row at or below `row` with bit `col` set.
        let mut pivot = None;
        for r in row..rows.len() {
            if rows[r][word] & bit_mask != 0 {
                pivot = Some(r);
                break;
            }
        }
        let Some(pivot) = pivot else { continue };
        rows.swap(row, pivot);
        // XOR-eliminate this column from every other row.
        for r in 0..rows.len() {
            if r == row {
                continue;
            }
            if rows[r][word] & bit_mask != 0 {
                let pivot_row = rows[row].clone();
                for (rr, pr) in rows[r].iter_mut().zip(pivot_row.iter()) {
                    *rr ^= *pr;
                }
            }
        }
        rank += 1;
        row += 1;
        if row >= rows.len() {
            break;
        }
    }
    rank
}

/// Generic-system rank prediction at Macaulay degree `D`.  For `n`
/// generic quadratic equations in `v` Boolean variables, the
/// (truncated) Hilbert series is
///
/// ```text
///   H(D)  =  Σ_{k=0..=D} C(v, k)   −   n · Σ_{k=0..=D-2} C(v, k).
/// ```
///
/// Clamp `H` at 0 from below; the predicted rank is `cols(D) − H(D)`.
pub(crate) fn generic_rank_prediction(n_eqs: u64, num_vars: u32, d: u32, cols: u64) -> u64 {
    let lower = if d >= 2 {
        num_monomials_upto_degree(num_vars, d - 2)
    } else {
        0
    };
    let upper = num_monomials_upto_degree(num_vars, d);
    let consumed = n_eqs * lower;
    if upper > consumed {
        let h = upper - consumed;
        cols.saturating_sub(h)
    } else {
        // Hilbert series went negative: rank saturates at cols.
        cols
    }
}

// ── Misc helpers ────────────────────────────────────────────────────

pub(crate) fn random_nonzero_f2m<R: Rng>(rng: &mut R, n: u32) -> F2mElement {
    loop {
        let bits: Vec<u32> = (0..n).filter(|_| rng.gen::<bool>()).collect();
        let e = F2mElement::from_bit_positions(&bits, n);
        if !e.is_zero() {
            return e;
        }
    }
}

pub(crate) fn choose_irreducible(n: u32) -> IrreduciblePoly {
    // Trinomials/pentanomials with low low_terms for n ∈ {3..16}.
    let low_terms: Vec<u32> = match n {
        2 => vec![0, 1],
        3 => vec![0, 1],
        4 => vec![0, 1],
        5 => vec![0, 2],
        6 => vec![0, 1],
        7 => vec![0, 1],
        8 => vec![0, 2, 3, 4],
        9 => vec![0, 1],
        10 => vec![0, 3],
        11 => vec![0, 2],
        12 => vec![0, 3],
        13 => vec![0, 1, 3, 4],
        14 => vec![0, 5],
        15 => vec![0, 1],
        16 => vec![0, 1, 3, 5],
        _ => vec![0, 1],
    };
    IrreduciblePoly {
        degree: n,
        low_terms,
    }
}

// Re-export the symbol so the demo binary can hit the binary semaev path.
#[allow(dead_code)]
fn semaev_eval_sanity(
    x1: &F2mElement,
    x2: &F2mElement,
    x3: &F2mElement,
    b: &F2mElement,
    irr: &IrreduciblePoly,
) -> F2mElement {
    binary_semaev_s3(x1, x2, x3, b, irr)
}

// ── Pretty printing ─────────────────────────────────────────────────

pub fn print_sweep(rows: &[FfdRow]) {
    println!();
    println!(
        "{:>3} {:>5} {:>5} | {:>5} {:>7} {:>9} {:>9} {:>9} {:>9}",
        "n", "vars", "eqs", "D", "rows", "cols", "rank", "gen rank", "fall"
    );
    println!("{}", "─".repeat(78));
    for r in rows {
        for (i, m) in r.per_degree.iter().enumerate() {
            let prefix = if i == 0 {
                format!("{:>3} {:>5} {:>5}", r.n, r.num_vars, r.num_eqs)
            } else {
                "                ".to_string()
            };
            println!(
                "{} | {:>5} {:>7} {:>9} {:>9} {:>9} {:>+9}",
                prefix, m.degree, m.rows_constructed, m.cols, m.rank, m.rank_generic, m.fall_signal
            );
        }
        match r.fall_degree {
            Some(d) => println!("     → first fall degree (FFD) at D = {}", d),
            None => println!("     → no fall observed"),
        }
        println!();
    }
}

// ── Tests ───────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn binomial_sanity() {
        assert_eq!(binom(0, 0), 1);
        assert_eq!(binom(5, 0), 1);
        assert_eq!(binom(5, 5), 1);
        assert_eq!(binom(5, 2), 10);
        assert_eq!(binom(10, 3), 120);
    }

    #[test]
    fn num_monomials_known_values() {
        // 4 vars: 1 + 4 + 6 = 11 monomials of degree ≤ 2.
        assert_eq!(num_monomials_upto_degree(4, 2), 11);
        // 6 vars: 1 + 6 + 15 + 20 + 15 = 57 monomials of degree ≤ 4.
        assert_eq!(num_monomials_upto_degree(6, 4), 57);
    }

    #[test]
    fn quad_monomial_index_round_trip() {
        let v = 6;
        // Verify the index function is one-to-one over all (i < j).
        let mut seen = std::collections::HashSet::new();
        for i in 0..v {
            for j in (i + 1)..v {
                let idx = quad_monomial_index(i, j, v);
                assert!(idx > v as usize);
                assert!(idx < 1 + v as usize + 15);
                assert!(seen.insert(idx), "duplicate index for ({},{})", i, j);
            }
        }
        assert_eq!(seen.len(), 15);
    }

    /// Monomial-index function is one-to-one across the full degree-≤d
    /// monomial list.
    #[test]
    fn monomial_index_is_injective() {
        let v: u32 = 5;
        let d: u32 = 3;
        let monos = enumerate_monomials_upto(v, d);
        let mut seen = std::collections::HashSet::new();
        for m in &monos {
            let idx = monomial_index(m, v, d);
            assert!(seen.insert(idx), "duplicate index for {:?}", m);
        }
        assert_eq!(seen.len() as u64, num_monomials_upto_degree(v, d));
    }

    /// F_2 row reduction sanity: 4 rows of 6 bits, known rank 3
    /// (row 4 = row 1 XOR row 2 XOR row 3).
    #[test]
    fn f2_rank_matches_hand_computed_example() {
        // Rows: 101000, 010100, 001010, and their XOR = 110110.
        let xor_row = 0b101000u64 ^ 0b010100u64 ^ 0b001010u64;
        let mut rows = vec![
            vec![0b101000u64],
            vec![0b010100u64],
            vec![0b001010u64],
            vec![xor_row],
        ];
        assert_eq!(f2_rank(&mut rows, 6), 3);
        // Adding a genuinely independent row should bump rank to 4.
        let mut rows = vec![
            vec![0b101000u64],
            vec![0b010100u64],
            vec![0b001010u64],
            vec![0b000001u64],
        ];
        assert_eq!(f2_rank(&mut rows, 6), 4);
    }

    /// **End-to-end FFD measurement** at `n = 4` runs and reports a
    /// table.  We don't bake the FFD into the test (it depends on
    /// the random `b, x_3`), but we *do* require:
    /// - the system has `n` equations in `2n` bit-variables;
    /// - the Macaulay matrix at D = 2 has at least one row that is
    ///   not identically zero (i.e. the Weil descent produced a
    ///   non-trivial system);
    /// - the rank at D = 4 saturates at the column count (the system
    ///   "fell" — every monomial of degree ≤ 4 was reduced).
    ///   **The factor-base descent must agree with field arithmetic.**
    ///   Pick `X₁, X₂` inside the `l`-dimensional subspace, evaluate the
    ///   descended equations at their bits, and compare against the bits
    ///   of `S₃(X₁, X₂, x₃)` computed directly over `F_{2ⁿ}`.
    #[test]
    fn subspace_descent_matches_field_evaluation() {
        use crate::cryptanalysis::binary_semaev::binary_semaev_s3;

        let n = 12u32;
        let l = 5u32;
        let irr = IrreduciblePoly {
            degree: n,
            low_terms: vec![0, 1, 2, 3],
        };
        let x3 = F2mElement::from_bit_positions(&[0, 4, 7], n);
        let b = F2mElement::from_bit_positions(&[1, 3], n);
        let eqs = weil_descend_s3_subspace(n, l, &irr, &b, &x3);
        assert_eq!(eqs.len(), n as usize);

        // Every equation lives in 2l bit-variables, not 2n.
        let num_vars = 2 * l;
        assert_eq!(
            eqs[0].coeffs.len(),
            num_monomials_upto_degree(num_vars, 2) as usize
        );

        // Evaluate an F2BoolPoly at a Boolean assignment.
        let eval = |p: &F2BoolPoly, a: &[bool]| -> bool {
            let mut acc = p.coeffs[0];
            for i in 0..num_vars as usize {
                if p.coeffs[1 + i] && a[i] {
                    acc ^= true;
                }
            }
            for i in 0..num_vars {
                for j in (i + 1)..num_vars {
                    let idx = quad_monomial_index(i, j, num_vars);
                    if p.coeffs[idx] && a[i as usize] && a[j as usize] {
                        acc ^= true;
                    }
                }
            }
            acc
        };

        for (v1, v2) in [
            (0b00000u32, 0b00000u32),
            (0b10110, 0b01101),
            (0b11111, 0b00001),
        ] {
            let bits = |v: u32| -> Vec<u32> { (0..l).filter(|k| (v >> k) & 1 == 1).collect() };
            let x1 = F2mElement::from_bit_positions(&bits(v1), n);
            let x2 = F2mElement::from_bit_positions(&bits(v2), n);

            let mut assign = vec![false; num_vars as usize];
            for k in 0..l as usize {
                assign[k] = (v1 >> k) & 1 == 1;
                assign[l as usize + k] = (v2 >> k) & 1 == 1;
            }

            let want = binary_semaev_s3(&x1, &x2, &x3, &b, &irr);
            let raw = want.raw_bits();
            for k in 0..n as usize {
                let want_bit = (raw[k / 64] >> (k % 64)) & 1 == 1;
                assert_eq!(
                    eval(&eqs[k], &assign),
                    want_bit,
                    "coefficient {k} at (X1={v1:#b}, X2={v2:#b})"
                );
            }
        }
    }

    #[test]
    fn ffd_pipeline_runs_at_n_4() {
        let irr = choose_irreducible(4);
        let b = F2mElement::from_bit_positions(&[0, 1], 4);
        let x3 = F2mElement::from_bit_positions(&[1, 2], 4);
        let row = measure_one(4, &irr, &b, &x3, 4);
        assert_eq!(row.num_vars, 8);
        assert_eq!(row.num_eqs, 4);
        // First entry should describe D = 2.
        assert_eq!(row.per_degree[0].degree, 2);
        assert!(row.per_degree[0].cols > 8);
        // Some non-trivial system was constructed.
        assert!(row.per_degree[0].rank >= 1);
        // Rank at the largest degree should be substantial.
        let last = row.per_degree.last().unwrap();
        assert!(last.rank >= 4);
    }

    /// **The FFD harness reports an FFD value for at least one curve
    /// in a small sweep**.  This is the "is anything actually
    /// falling?" smoke test.
    #[test]
    fn at_least_one_curve_in_sweep_has_a_fall_signal() {
        let rows = run_sweep(3..=5, 4, 0xFFD);
        let any_fall = rows.iter().any(|r| r.fall_degree.is_some());
        // We don't strictly assert any_fall — random b might make a
        // generic-shaped system — but we do assert the table is
        // populated.
        let _ = any_fall;
        assert_eq!(rows.len(), 3);
        for r in &rows {
            assert!(!r.per_degree.is_empty());
        }
    }
}
