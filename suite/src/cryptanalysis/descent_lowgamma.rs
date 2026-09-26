//! # EXP-E — low-γ (subfield / structured) factor-base subspaces.
//!
//! Workflow iteration 2 ran the central G-P2 test (`γ` vs `D*`) only over
//! **generic** irreducible bases, all of which turned out to be
//! high-expansion (`γ_spec ∈ [0.74, 0.95]`). Prediction P2 is fundamentally
//! a **low-γ vs high-γ contrast** claim — the proof-complexity bridge says
//! the first-fall assumption holds *precisely* on the low-expansion
//! structures (subfield / Koblitz / sparse-normal bases) that index
//! calculus actually exploits (Diem, GHS). To test P2 honestly we must put
//! genuine **low-γ** points on the axis. This module does that.
//!
//! ## The mechanism: an arbitrary factor-base subspace `V`
//!
//! The point-decomposition problem restricts `X₁, X₂` to an `F_2`-subspace
//! `V ⊂ F_{2ⁿ}` of dimension `n'`. The existing `pc_degree_harness` hard-
//! codes the **coordinate** subspace `V = span{z⁰, …, z^{n'−1}}`. Here `V`
//! is given by an arbitrary `n × n'` binary **basis matrix** `M` (columns
//! = `F_2`-basis vectors of `V`, as bit-vectors over `{z⁰, …, z^{n−1}}`),
//! and we substitute
//!
//! ```text
//!   X₁ = Σ_{p<n'} a_p · v_p ,   X₂ = Σ_{p<n'} b_p · v_p ,   v_p = M[:,p],
//! ```
//!
//! into the (unrestricted) Weil-descended `S₃`, re-expressing each output
//! equation as an `F_2`-quadratic in the `2n'` new bit-variables
//! `(a_0..a_{n'-1}, b_0..b_{n'-1})`. The coordinate case (`M = [I; 0]`) must
//! reproduce `restrict_to_subspace` exactly — checked by a test.
//!
//! ## The three basis families
//!
//! - **`Coordinate`** — `v_p = z^p`. The baseline; high-γ generic.
//! - **`Subfield`** — when `d = n'` divides `n`, `V = F_{2^d}`, the unique
//!   subfield, spanned by `{1, w, …, w^{d−1}}` with `w = z^{(2ⁿ−1)/(2ᵈ−1)}`
//!   a generator of `F_{2^d}^×`. This is the Diem subfield case and the
//!   expected **low-γ** structure.
//! - **`Random`** — a random full-rank `n × n'` `M`; a high-γ control.
//!
//! ## What we measure on each `V`
//!
//! The **same** two numbers as the rest of the program, now on the
//! substituted system: the refutation degree `D*`
//! (`pc_degree_harness::refutation_scan`) and the incidence-graph spectral
//! expansion `γ` (`descent_expansion::report_from_graph`). A genuine
//! low-γ/high-γ split lets G-P2 finally span the full `γ` axis.
//!
//! ## References
//!
//! See `research/notes/index-calculus/RESEARCH_FFD_PROOF_COMPLEXITY.md` (§3 expansion conjecture) and
//! `research/notes/index-calculus/RESEARCH_FFD_WORKFLOW.md` (EXP-E). Subfield index calculus: C. Diem,
//! *On the discrete logarithm problem in elliptic curves*, 2011.

use crate::binary_ecc::{F2mElement, IrreduciblePoly};
use crate::cryptanalysis::descent_expansion::{report_from_graph, Biadjacency, ExpansionReport};
use crate::cryptanalysis::ffd_harness::{quad_monomial_index, weil_descend_s3, F2BoolPoly};
use crate::cryptanalysis::pc_degree_harness::refutation_scan;

// ── Factor-base subspace ────────────────────────────────────────────

/// Which structured factor-base subspace to use.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BasisFamily {
    /// `V = span{z⁰, …, z^{n'−1}}` (the `pc_degree_harness` default).
    Coordinate,
    /// `V = F_{2^{n'}}` the subfield (requires `n' | n`); the low-γ case.
    Subfield,
    /// A random full-rank `n × n'` basis matrix (high-γ control).
    Random,
}

/// An `F_2`-subspace `V ⊆ F_{2ⁿ}` of dimension `n'`, stored as its basis
/// matrix `M`: `cols[p]` is the `p`-th basis vector `v_p ∈ F_{2ⁿ}`.
#[derive(Clone, Debug)]
pub struct FactorSubspace {
    pub n: u32,
    pub n_sub: u32,
    /// `cols[p] = v_p`, the `p`-th `F_2`-basis vector of `V`.
    pub cols: Vec<F2mElement>,
    pub family: BasisFamily,
}

impl FactorSubspace {
    /// Build a structured subspace. `seed` is used only by `Random`.
    /// Returns `None` if the family is infeasible (e.g. `Subfield` with
    /// `n' ∤ n`).
    pub fn build(
        family: BasisFamily,
        n: u32,
        n_sub: u32,
        irr: &IrreduciblePoly,
        seed: u64,
    ) -> Option<Self> {
        assert!(n_sub >= 1 && n_sub <= n);
        let cols = match family {
            BasisFamily::Coordinate => (0..n_sub)
                .map(|p| F2mElement::from_bit_positions(&[p], n))
                .collect(),
            BasisFamily::Subfield => subfield_basis(n, n_sub, irr)?,
            BasisFamily::Random => random_fullrank_basis(n, n_sub, seed),
        };
        Some(FactorSubspace {
            n,
            n_sub,
            cols,
            family,
        })
    }

    /// Enumerate the `2^{n'}` elements of `V` (used by the decomposability
    /// oracle and for sanity checks). Element `mask` = `Σ_p mask_p v_p`.
    pub fn element(&self, mask: u32) -> F2mElement {
        let mut acc = F2mElement::from_bit_positions(&[], self.n);
        for p in 0..self.n_sub {
            if (mask >> p) & 1 == 1 {
                acc = acc.add(&self.cols[p as usize]);
            }
        }
        acc
    }
}

/// Basis of the subfield `F_{2^d} ⊂ F_{2ⁿ}` (`d = n_sub`, requires
/// `d | n`). Built **exactly** as the kernel of the `F_2`-linear map
/// `L(x) = x^{2ᵈ} + x` (Frobenius^d − identity): since `x^{2ᵈ} = x` iff
/// `x ∈ F_{2ᵈ}`, that kernel *is* the subfield, of dimension exactly `d`.
///
/// This avoids assuming the defining polynomial `irr` is **primitive** (an
/// earlier `w = z^{(2ⁿ−1)/(2ᵈ−1)}` attempt silently failed for
/// non-primitive `irr`, because then `z` does not generate `F_{2ⁿ}^×`).
/// The Frobenius map is `F_2`-linear regardless, so the kernel route is
/// always correct. Returns `None` if `d ∤ n`.
fn subfield_basis(n: u32, d: u32, irr: &IrreduciblePoly) -> Option<Vec<F2mElement>> {
    if d == 0 || !n.is_multiple_of(d) {
        return None;
    }
    if d == n {
        // The whole field; standard basis {z^0, …, z^{n-1}}.
        return Some(
            (0..n)
                .map(|i| F2mElement::from_bit_positions(&[i], n))
                .collect(),
        );
    }
    // Matrix of L(x) = Frob^d(x) + x over F_2: column i = L(z^i) as bits.
    // L is F_2-linear, so L(Σ x_i z^i) = Σ x_i L(z^i).
    let mut lcols: Vec<u128> = Vec::with_capacity(n as usize);
    for i in 0..n {
        let zi = F2mElement::from_bit_positions(&[i], n);
        let frob = zi.square_k_times(d, irr); // z^{i·2^d} reduced
        let limg = frob.add(&zi); // L(z^i)
        lcols.push(elem_to_u128(&limg, n));
    }
    // Kernel of the n×n matrix whose columns are lcols. We want vectors
    // x ∈ F_2^n with Σ x_i lcols[i] = 0. Solve by reducing the matrix whose
    // ROWS are lcols^T... simplest: build the n×n bit-matrix M[r][i] = bit r
    // of L(z^i), then find null space over F_2.
    let kernel = f2_nullspace(&lcols, n);
    if kernel.len() != d as usize {
        // Should be exactly d when d | n; bail defensively otherwise.
        return None;
    }
    Some(kernel.into_iter().map(|v| u128_to_elem(v, n)).collect())
}

/// Null space (kernel) basis of the `F_2`-linear map given by `cols`, where
/// `cols[i]` is the image of basis vector `e_i` (so the map sends
/// `x = Σ x_i e_i ↦ Σ x_i cols[i]`). Returns a basis of `{x : map(x)=0}` as
/// `u128` bitmasks over the `i`-indices. `n` = domain dimension.
///
/// Column reduction with provenance: each column carries `(value, tag)`
/// where `value = cols[i]` and `tag = e_i`. Eliminating leading bits keeps
/// the invariant `value = map(tag)`; a column reduced to `value == 0` then
/// has `map(tag) = 0`, i.e. `tag` is a kernel vector.
fn f2_nullspace(cols: &[u128], n: u32) -> Vec<u128> {
    let n = n as usize;
    let mut value: Vec<u128> = cols.to_vec();
    let mut tag: Vec<u128> = (0..n).map(|i| 1u128 << i).collect();
    for i in 0..n {
        if value[i] == 0 {
            continue;
        }
        let lead = value[i].trailing_zeros();
        for j in 0..n {
            if j != i && (value[j] >> lead) & 1 == 1 {
                value[j] ^= value[i];
                tag[j] ^= tag[i];
            }
        }
    }
    let kernel: Vec<u128> = (0..n)
        .filter(|&i| value[i] == 0 && tag[i] != 0)
        .map(|i| tag[i])
        .collect();
    independent_subset(&kernel, n as u32)
}

/// Reduce a set of `u128` vectors to an `F_2`-independent spanning subset.
fn independent_subset(vecs: &[u128], _n: u32) -> Vec<u128> {
    let mut basis: Vec<u128> = Vec::new();
    let mut reduced: Vec<u128> = Vec::new();
    for &v in vecs {
        let mut x = v;
        for &r in &reduced {
            let lead = r.trailing_zeros();
            if (x >> lead) & 1 == 1 {
                x ^= r;
            }
        }
        if x != 0 {
            reduced.push(x);
            basis.push(v);
        }
    }
    basis
}

fn u128_to_elem(v: u128, n: u32) -> F2mElement {
    let bits: Vec<u32> = (0..n).filter(|&i| (v >> i) & 1 == 1).collect();
    F2mElement::from_bit_positions(&bits, n)
}

/// Random full-rank `n × n'` `F_2` basis matrix, columns as `F_{2ⁿ}`
/// elements. Deterministic in `seed`.
fn random_fullrank_basis(n: u32, n_sub: u32, seed: u64) -> Vec<F2mElement> {
    let mut state = seed | 1;
    let mut next = || {
        // xorshift64*
        state ^= state >> 12;
        state ^= state << 25;
        state ^= state >> 27;
        state.wrapping_mul(0x2545F4914F6CDD1D)
    };
    loop {
        let mut cols = Vec::with_capacity(n_sub as usize);
        for _ in 0..n_sub {
            let bits: Vec<u32> = (0..n).filter(|_| (next() >> 17) & 1 == 1).collect();
            cols.push(F2mElement::from_bit_positions(&bits, n));
        }
        if rank_f2m(&cols, n) == n_sub as usize {
            return cols;
        }
        // else: reroll (rank-deficient draw).
    }
}

/// `F_2`-rank of a set of `F_{2ⁿ}` elements (treated as length-`n`
/// bit-vectors).
fn rank_f2m(cols: &[F2mElement], n: u32) -> usize {
    let mut rows: Vec<u128> = cols.iter().map(|c| elem_to_u128(c, n)).collect();
    let mut rank = 0;
    for bit in 0..n {
        let mask = 1u128 << bit;
        if let Some(piv) = (rank..rows.len()).find(|&r| rows[r] & mask != 0) {
            rows.swap(rank, piv);
            let pr = rows[rank];
            for r in 0..rows.len() {
                if r != rank && rows[r] & mask != 0 {
                    rows[r] ^= pr;
                }
            }
            rank += 1;
        }
    }
    rank
}

fn elem_to_u128(e: &F2mElement, n: u32) -> u128 {
    let raw = e.raw_bits();
    let mut v = 0u128;
    for j in 0..n as usize {
        let w = j / 64;
        let bit = j % 64;
        if (raw.get(w).copied().unwrap_or(0) >> bit) & 1 == 1 {
            v |= 1u128 << j;
        }
    }
    v
}

// ── Change of variables: descend S₃ onto an arbitrary V ─────────────

/// Re-express the Weil-descended `S₃` system on the factor-base subspace
/// `V`: substitute `X₁ = Σ_p a_p v_p`, `X₂ = Σ_p b_p v_p` and return the
/// `n` output equations as `F_2`-quadratics in the `2n'` variables
/// `(a_0..a_{n'-1}, b_0..b_{n'-1})`.
///
/// Implementation: the descended system from `weil_descend_s3` is a vector
/// of quadratics in the original `2n` bit-variables (`X₁` bits then `X₂`
/// bits). Each original bit `X₁[i]` equals `Σ_p M[i][p] a_p` (a linear form
/// in the new variables), and likewise `X₂[i]`. We substitute these linear
/// forms into every monomial. Because the new variables also satisfy
/// `a_p² = a_p`, products fold into multilinear quadratics over the new
/// `2n'` variables exactly as in `F2BoolPoly::mul_linear`.
pub fn descend_on_subspace(
    n: u32,
    v: &FactorSubspace,
    irr: &IrreduciblePoly,
    b: &F2mElement,
    x3: &F2mElement,
) -> Vec<F2BoolPoly> {
    let full = weil_descend_s3(n, irr, b, x3);
    let old_vars = 2 * n;
    let new_vars = 2 * v.n_sub;
    // For each old variable index, the linear form (over new vars) it maps
    // to. Old layout: [X₁ bits 0..n | X₂ bits 0..n].
    // X₁[i] = Σ_p M[i][p] a_p  ⇒  for new var a_p (index p), include if v_p
    // has bit i set. Similarly X₂[i] = Σ_p M[i][p] b_p (new index n'+p).
    let lin_form = |old: u32| -> F2BoolPoly {
        let mut f = F2BoolPoly::zero(new_vars);
        if old < n {
            // X₁ bit `old`
            let i = old;
            for p in 0..v.n_sub {
                if bit_of(&v.cols[p as usize], i, n) {
                    f.coeffs[1 + p as usize] ^= true;
                }
            }
        } else {
            // X₂ bit `old - n`
            let i = old - n;
            for p in 0..v.n_sub {
                if bit_of(&v.cols[p as usize], i, n) {
                    f.coeffs[1 + (v.n_sub + p) as usize] ^= true;
                }
            }
        }
        f
    };
    // Precompute the linear form for every old variable.
    let forms: Vec<F2BoolPoly> = (0..old_vars).map(lin_form).collect();

    full.iter()
        .map(|eq| {
            let mut out = F2BoolPoly::zero(new_vars);
            // Constant term.
            if eq.coeffs[0] {
                out.coeffs[0] ^= true;
            }
            // Linear terms: substitute X[old] → forms[old].
            for old in 0..old_vars {
                if eq.coeffs.get(1 + old as usize).copied().unwrap_or(false) {
                    out.xor_assign(&forms[old as usize]);
                }
            }
            // Quadratic terms X[a]·X[c] → forms[a] · forms[c].
            for a in 0..old_vars {
                for c in (a + 1)..old_vars {
                    let idx = quad_monomial_index(a, c, old_vars);
                    if idx < eq.coeffs.len() && eq.coeffs[idx] {
                        let prod = forms[a as usize].mul_linear(&forms[c as usize], new_vars);
                        out.xor_assign(&prod);
                    }
                }
            }
            out
        })
        .collect()
}

fn bit_of(e: &F2mElement, i: u32, _n: u32) -> bool {
    let raw = e.raw_bits();
    let w = (i / 64) as usize;
    let bit = (i % 64) as usize;
    (raw.get(w).copied().unwrap_or(0) >> bit) & 1 == 1
}

// ── Incidence graph of the V-substituted system ─────────────────────

/// Incidence (Tanner) graph of the substituted system on `V`: `left = n`
/// equations, `right = 2n'` new variables, edge iff the variable occurs in
/// the equation. Same construction as `descent_expansion::system_incidence`
/// but on the `V`-substituted system.
pub fn subspace_incidence(eqs: &[F2BoolPoly], new_vars: u32) -> Biadjacency {
    let left = eqs.len();
    let right = new_vars as usize;
    let mut bb = vec![vec![false; right]; left];
    for (j, eq) in eqs.iter().enumerate() {
        for i in 0..right {
            if eq.coeffs.get(1 + i).copied().unwrap_or(false) {
                bb[j][i] = true;
            }
        }
        for a in 0..new_vars {
            for c in (a + 1)..new_vars {
                let idx = quad_monomial_index(a, c, new_vars);
                if idx < eq.coeffs.len() && eq.coeffs[idx] {
                    bb[j][a as usize] = true;
                    bb[j][c as usize] = true;
                }
            }
        }
    }
    Biadjacency { b: bb, left, right }
}

// ── Combined measurement: (γ, D*) on one V ──────────────────────────

/// Joint `(γ, D*)` measurement on a structured subspace `V`, for one
/// `(b, x₃)`. `γ` is the spectral expansion of the `V`-substituted system's
/// incidence graph; `D*` is its refutation degree (`None` if no refutation
/// within `d_max`, i.e. the target decomposed over `V`).
#[derive(Clone, Debug)]
pub struct LowGammaPoint {
    pub family: BasisFamily,
    pub n: u32,
    pub n_sub: u32,
    pub report: ExpansionReport,
    pub first_fall: Option<u32>,
    pub refutation_degree: Option<u32>,
}

/// Measure `(γ, D*)` on subspace `V` for a single `(b, x₃)`.
pub fn measure_on_subspace(
    n: u32,
    v: &FactorSubspace,
    irr: &IrreduciblePoly,
    b: &F2mElement,
    x3: &F2mElement,
    d_max: u32,
) -> LowGammaPoint {
    let eqs = descend_on_subspace(n, v, irr, b, x3);
    let new_vars = 2 * v.n_sub;
    let g = subspace_incidence(&eqs, new_vars);
    let report = report_from_graph(n, v.n_sub, &g);
    let (first_fall, refutation_degree, _per) = refutation_scan(&eqs, new_vars, d_max);
    LowGammaPoint {
        family: v.family,
        n,
        n_sub: v.n_sub,
        report,
        first_fall,
        refutation_degree,
    }
}

/// Aggregated EXP-E statistics for one `(family, n, n')` cell over a batch
/// of random `(b, x₃)`: the **decomposability rate** (fraction of targets
/// that decompose over `V` — the index-calculus *success* rate), plus the
/// mean spectral `γ` and the mean refutation degree `D*` over the
/// **non-decomposable** targets (those for which `D*` is defined).
#[derive(Clone, Debug)]
pub struct LowGammaCell {
    pub family: BasisFamily,
    pub n: u32,
    pub n_sub: u32,
    pub trials: u32,
    /// Targets that decomposed over `V` (satisfiable; no refutation).
    pub decomposed: u32,
    /// Fraction `decomposed / trials` — the decomposition (success) rate.
    pub decomp_rate: f64,
    /// Mean spectral expansion `γ` over all trials (graph is independent of
    /// the target, so this is just the per-`(b)` mean).
    pub gamma_mean: f64,
    /// Mean `D*` over the non-decomposable trials, or `None` if none.
    pub dstar_mean: Option<f64>,
    /// Number of non-decomposable trials (those contributing to `dstar_mean`).
    pub nondecomp: u32,
}

/// Run an EXP-E cell: `trials` random `(b, x₃)` over subspace family
/// `family` at `(n, n')`. For `Random`, each trial reseeds the basis; for
/// `Coordinate`/`Subfield` the (unique) basis is fixed and only `(b, x₃)`
/// vary. Returns `None` if the family is infeasible (e.g. `Subfield` with
/// `n' ∤ n`).
pub fn run_lowgamma_cell(
    family: BasisFamily,
    n: u32,
    n_sub: u32,
    irr: &IrreduciblePoly,
    d_max: u32,
    trials: u32,
    seed: u64,
) -> Option<LowGammaCell> {
    // Feasibility probe for fixed-basis families.
    if matches!(family, BasisFamily::Subfield)
        && FactorSubspace::build(family, n, n_sub, irr, 0).is_none()
    {
        return None;
    }
    let mut state = seed | 1;
    let mut next = || {
        state ^= state >> 12;
        state ^= state << 25;
        state ^= state >> 27;
        state.wrapping_mul(0x2545F4914F6CDD1D)
    };
    let rand_nz = |m: u32, rng: &mut dyn FnMut() -> u64| loop {
        let bits: Vec<u32> = (0..m).filter(|_| (rng() >> 19) & 1 == 1).collect();
        let e = F2mElement::from_bit_positions(&bits, m);
        if !e.is_zero() {
            return e;
        }
    };

    let mut decomposed = 0u32;
    let mut nondecomp = 0u32;
    let mut gsum = 0.0f64;
    let mut gcount = 0u32;
    let mut dsum = 0.0f64;

    for t in 0..trials {
        let v = match family {
            BasisFamily::Random => {
                FactorSubspace::build(family, n, n_sub, irr, seed ^ (0x1000 + t as u64))
            }
            _ => FactorSubspace::build(family, n, n_sub, irr, 0),
        }?;
        let b = rand_nz(n, &mut next);
        let x3 = rand_nz(n, &mut next);
        let pt = measure_on_subspace(n, &v, irr, &b, &x3, d_max);
        gsum += pt.report.gamma_spectral;
        gcount += 1;
        match pt.refutation_degree {
            Some(d) => {
                nondecomp += 1;
                dsum += d as f64;
            }
            None => decomposed += 1,
        }
    }

    Some(LowGammaCell {
        family,
        n,
        n_sub,
        trials,
        decomposed,
        decomp_rate: decomposed as f64 / trials.max(1) as f64,
        gamma_mean: if gcount > 0 {
            gsum / gcount as f64
        } else {
            f64::NAN
        },
        dstar_mean: if nondecomp > 0 {
            Some(dsum / nondecomp as f64)
        } else {
            None
        },
        nondecomp,
    })
}

/// Is `x₃` decomposable over `V`? Brute force over `V × V` using the
/// subspace's own basis (so this works for any `V`, not just coordinate).
pub fn is_decomposable_on_subspace(
    v: &FactorSubspace,
    irr: &IrreduciblePoly,
    b: &F2mElement,
    x3: &F2mElement,
) -> bool {
    use crate::cryptanalysis::binary_semaev::binary_semaev_s3;
    let span = 1u32 << v.n_sub;
    for m1 in 0..span {
        let x1 = v.element(m1);
        for m2 in 0..span {
            let x2 = v.element(m2);
            if binary_semaev_s3(&x1, &x2, x3, b, irr).is_zero() {
                return true;
            }
        }
    }
    false
}

// ── Tests ───────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::ffd_harness::choose_irreducible;
    use crate::cryptanalysis::pc_degree_harness::restrict_to_subspace;

    /// The `Coordinate` substitution must reproduce `restrict_to_subspace`
    /// exactly (it is the special case `M = [I; 0]`).
    #[test]
    fn coordinate_matches_restrict_to_subspace() {
        let n = 6;
        let n_sub = 3;
        let irr = choose_irreducible(n);
        let b = F2mElement::from_bit_positions(&[0, 2], n);
        let x3 = F2mElement::from_bit_positions(&[1, 3], n);
        let v = FactorSubspace::build(BasisFamily::Coordinate, n, n_sub, &irr, 0).unwrap();
        let via_sub = descend_on_subspace(n, &v, &irr, &b, &x3);
        let full = weil_descend_s3(n, &irr, &b, &x3);
        let via_restrict = restrict_to_subspace(&full, n, n_sub);
        assert_eq!(via_sub.len(), via_restrict.len());
        for (p, q) in via_sub.iter().zip(via_restrict.iter()) {
            assert_eq!(
                p.coeffs, q.coeffs,
                "coordinate substitution must equal restrict_to_subspace"
            );
        }
    }

    /// Subfield basis exists when `n' | n` and spans a genuine subfield:
    /// `F_{2^2} ⊂ F_{2^4}`. The basis must be F_2-independent (rank n').
    #[test]
    fn subfield_basis_is_independent() {
        let n = 4;
        let d = 2; // 2 | 4
        let irr = choose_irreducible(n);
        let cols = subfield_basis(n, d, &irr).expect("F_4 ⊂ F_16 should exist");
        assert_eq!(cols.len(), 2);
        assert_eq!(rank_f2m(&cols, n), 2);
        // Closure check: V should be closed under multiplication (it's a
        // field). Take w = cols[1]; w·w must lie in span{cols}.
        let w = &cols[1];
        let wsq = w.mul(w, &irr);
        // wsq ∈ span{1, w} ⇔ rank{1, w, wsq} = 2.
        let mut test = cols.clone();
        test.push(wsq);
        assert_eq!(
            rank_f2m(&test, n),
            2,
            "subfield must be closed under squaring"
        );
    }

    /// Subfield is rejected when `n' ∤ n`.
    #[test]
    fn subfield_requires_divisibility() {
        let n = 5;
        let irr = choose_irreducible(n);
        assert!(FactorSubspace::build(BasisFamily::Subfield, n, 2, &irr, 0).is_none());
        // But n'=1 (the prime field F_2) always works.
        assert!(FactorSubspace::build(BasisFamily::Subfield, n, 1, &irr, 0).is_some());
    }

    /// Random basis is full-rank and the substituted system has the right
    /// shape (n equations, 2n' variables).
    #[test]
    fn random_basis_fullrank_and_shape() {
        let n = 6;
        let n_sub = 2;
        let irr = choose_irreducible(n);
        let v = FactorSubspace::build(BasisFamily::Random, n, n_sub, &irr, 0xABCD).unwrap();
        assert_eq!(rank_f2m(&v.cols, n), n_sub as usize);
        let b = F2mElement::from_bit_positions(&[1], n);
        let x3 = F2mElement::from_bit_positions(&[0, 2], n);
        let eqs = descend_on_subspace(n, &v, &irr, &b, &x3);
        assert_eq!(eqs.len(), n as usize);
        let expect_len = F2BoolPoly::zero(2 * n_sub).coeffs.len();
        for e in &eqs {
            assert_eq!(e.coeffs.len(), expect_len);
        }
    }

    /// Decomposability oracle on V agrees with refutation: a non-decomposable
    /// target over the subspace refutes; a decomposable one does not.
    #[test]
    fn refutation_iff_nondecomposable_on_subspace() {
        let n = 6;
        let n_sub = 2;
        let irr = choose_irreducible(n);
        let b = F2mElement::from_bit_positions(&[0], n);
        let v = FactorSubspace::build(BasisFamily::Random, n, n_sub, &irr, 0x55).unwrap();
        let d_max = 2 * n_sub + 1;
        let mut checked = 0;
        for t in 1u32..(1u32 << n) {
            let x3 = F2mElement::from_bit_positions(
                &(0..n).filter(|k| (t >> k) & 1 == 1).collect::<Vec<_>>(),
                n,
            );
            if x3.is_zero() {
                continue;
            }
            let decomp = is_decomposable_on_subspace(&v, &irr, &b, &x3);
            let pt = measure_on_subspace(n, &v, &irr, &b, &x3, d_max);
            assert_eq!(
                decomp,
                pt.refutation_degree.is_none(),
                "t={t}: decomposable={decomp} but D*={:?}",
                pt.refutation_degree
            );
            checked += 1;
        }
        assert!(checked > 0);
    }

    /// EXP-E cell runner: returns aggregated stats; `Subfield` is `None`
    /// when infeasible and `Some` when `n' | n`.
    #[test]
    fn cell_runner_basic() {
        let n = 8;
        let irr = choose_irreducible(n);
        // n'=3 does not divide 8 → subfield infeasible.
        assert!(run_lowgamma_cell(BasisFamily::Subfield, n, 3, &irr, 8, 8, 1).is_none());
        // n'=2 divides 8 → feasible.
        let cell = run_lowgamma_cell(BasisFamily::Subfield, n, 2, &irr, 8, 12, 1).unwrap();
        assert_eq!(cell.trials, 12);
        assert_eq!(cell.decomposed + cell.nondecomp, cell.trials);
        assert!(cell.gamma_mean >= 0.0 && cell.gamma_mean <= 1.0);
    }

    /// **The EXP-E finding, locked in — and it points AGAINST the bridge.**
    /// At the index-calculus regime `2n' = n`, the structured *subfield*
    /// factor base `F_{2^{n'}}` gives a **lower** refutation degree `D*`
    /// (the genuine "subfield is easier" effect, à la Diem) than a random
    /// subspace — yet its spectral expansion `γ` is **not lower** (indeed
    /// tends to be higher). So `γ` does *not* explain why the structured
    /// case is easier: the proposal's conjecture "`D*` increases with `γ`"
    /// (prediction P2) is contradicted by the most important structured
    /// case. This is the central negative signal for the bridge.
    #[test]
    fn subfield_lower_dstar_but_not_lower_gamma() {
        let n = 8;
        let n_sub = 4; // 2n' = n, and 4 | 8 ⇒ V = F_16 is a subfield
        let irr = choose_irreducible(n);
        let sub = run_lowgamma_cell(BasisFamily::Subfield, n, n_sub, &irr, 10, 32, 7).unwrap();
        let rnd = run_lowgamma_cell(BasisFamily::Random, n, n_sub, &irr, 10, 32, 7).unwrap();
        let (sd, rd) = (sub.dstar_mean.unwrap(), rnd.dstar_mean.unwrap());
        // Structured (subfield) is easier: lower D*.
        assert!(
            sd < rd,
            "subfield D* {sd:.2} should be below random D* {rd:.2} (structured is easier)"
        );
        // But γ does NOT track that: subfield γ is not below random γ, so
        // high-γ→high-D* (P2) fails on the structured case.
        assert!(
            sub.gamma_mean >= rnd.gamma_mean - 1e-3,
            "subfield γ {:.3} is below random γ {:.3} — would (partly) rescue P2",
            sub.gamma_mean,
            rnd.gamma_mean
        );
    }

    /// Smoke: all three families build and measure at n=8,n'=2.
    #[test]
    fn all_families_measure() {
        let n = 8;
        let n_sub = 2; // 2 | 8 so subfield exists
        let irr = choose_irreducible(n);
        let b = F2mElement::from_bit_positions(&[0, 3], n);
        let x3 = F2mElement::from_bit_positions(&[1], n);
        for fam in [
            BasisFamily::Coordinate,
            BasisFamily::Subfield,
            BasisFamily::Random,
        ] {
            let v = FactorSubspace::build(fam, n, n_sub, &irr, 0x99).unwrap();
            let pt = measure_on_subspace(n, &v, &irr, &b, &x3, 2 * n_sub + 2);
            assert_eq!(pt.report.left, n as usize);
            assert_eq!(pt.report.right, 2 * n_sub as usize);
            assert!(pt.report.gamma_spectral >= 0.0 && pt.report.gamma_spectral <= 1.0);
        }
    }
}
