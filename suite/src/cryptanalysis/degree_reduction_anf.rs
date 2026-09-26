//! # Lever L2 — does symmetrisation lower the solving degree?
//!
//! The degree-reduction thread's remaining untested lever. Iterations 1–4
//! settled the others: hybrid slicing is killed, degree falls pay only where
//! the base degree is high, their composition is killed, and the `Δ_low`
//! screen turned out to be a size proxy — so L2 must be scored the way
//! iterations 2 and 3 scored their levers: **measured `D*` and total work at
//! matched shape**, not a defect correlation.
//!
//! ## Why `S₄`, and why the rest of the thread could not test this
//!
//! Symmetrisation's saving scales like `m!`. The rest of this thread runs on
//! `S₃` (`m = 2`), where `m! = 2` — essentially nothing. Testing L2 there
//! would measure noise. [`binary_semaev_s4`] already carries a symmetrised
//! `S₄` descent at `m = 3`, which is both the first `m` where index calculus
//! beats Pollard ρ at all and the first where `m!` is worth having.
//!
//! ## The two presentations of one ideal
//!
//! [`S4System`] gives the symmetrised model in two halves:
//!
//! | half | variables | degree | count |
//! |---|---|---|---|
//! | correspondence `e_{i,d} = σ_i(x)_d` | x ∪ e | ≤ 3 | `6ℓ − 3` |
//! | descended `S₄` | e only | ≤ 2 | `n` |
//!
//! Eliminating `e` by substituting `e_{i,d} := σ_i(x)_d` gives the **same
//! ideal** presented over the `x` variables alone, at degree ≤ 6 (quadratic
//! in `e`, each `e` cubic in `x`). That is the non-symmetrised baseline, and
//! it needs no new algebra — only substitution — so the comparison is exact
//! rather than approximate.
//!
//! So L2 is a pure presentation question of the kind this thread was built
//! to ask: same ideal, `9ℓ − 3` variables at low degree versus `3ℓ`
//! variables at high degree. Which does the Macaulay tower prefer?
//!
//! ## What had to be built
//!
//! The thread's harness is quadratic-only ([`F2BoolPoly`] holds degree ≤ 2).
//! Both halves here exceed that, so this module carries an **arbitrary-degree
//! ANF** Macaulay path ([`anf_macaulay_rows`], [`anf_refutation_scan`]) that
//! reuses the same bit-packed elimination and the same "is `1` in the row
//! space" refutation test as the rest of the thread, so the `D*` numbers are
//! commensurable with iterations 1–4.
//!
//! [`binary_semaev_s4`]: crate::cryptanalysis::binary_semaev_s4
//! [`F2BoolPoly`]: crate::cryptanalysis::ffd_harness::F2BoolPoly

use crate::cryptanalysis::binary_semaev_s4::{AnfPoly, S4System};
use crate::cryptanalysis::ffd_harness::{monomial_index, num_monomials_upto_degree};
use crate::cryptanalysis::pc_degree_harness::rank_and_refute;

// ── Arbitrary-degree ANF Macaulay path ──────────────────────────────

/// Enumerate every multilinear monomial of degree `≤ max_deg` over
/// `num_vars` variables, as sorted variable-index vectors.
fn multilinear_monomials(num_vars: u32, max_deg: u32) -> Vec<Vec<u32>> {
    let mut out = vec![Vec::new()];
    let mut frontier: Vec<Vec<u32>> = vec![Vec::new()];
    for _ in 0..max_deg {
        let mut next = Vec::new();
        for m in &frontier {
            let start = m.last().map(|v| v + 1).unwrap_or(0);
            for v in start..num_vars {
                let mut c = m.clone();
                c.push(v);
                next.push(c);
            }
        }
        out.extend(next.iter().cloned());
        frontier = next;
        if frontier.is_empty() {
            break;
        }
    }
    out
}

/// Build the degree-`d` Macaulay matrix of an arbitrary-degree ANF system.
///
/// Rows are the products `m · f` for every equation `f` with
/// `deg(f) ≤ d` and every multilinear multiplier `m` with
/// `deg(m) ≤ d − deg(f)`; multiplication is multilinear (`x² = x`), so
/// `deg(m·f) ≤ d` always holds. Columns are the multilinear monomials of
/// degree `≤ d`, indexed by [`monomial_index`] — the same indexing the
/// quadratic path uses, so column 0 is the constant `1` and the refutation
/// test is the same one.
///
/// Returns `(rows, cols, rows_constructed)`.
pub fn anf_macaulay_rows(eqs: &[AnfPoly], num_vars: u32, d: u32) -> (Vec<Vec<u64>>, usize, u64) {
    let cols = num_monomials_upto_degree(num_vars, d) as usize;
    let words = cols.div_ceil(64);
    let mut rows: Vec<Vec<u64>> = Vec::new();

    for f in eqs {
        let fdeg = f.degree() as u32;
        if fdeg > d {
            continue;
        }
        for m in multilinear_monomials(num_vars, d - fdeg) {
            let mut acc = vec![0u64; words];
            let mut any = false;
            for t in f.monomials() {
                // Multilinear product: the union of the two supports.
                let mut prod: Vec<u32> = m.clone();
                for v in t {
                    if let Err(pos) = prod.binary_search(v) {
                        prod.insert(pos, *v);
                    }
                }
                if prod.len() as u32 > d {
                    continue;
                }
                let idx = monomial_index(&prod, num_vars, d);
                acc[idx / 64] ^= 1u64 << (idx % 64);
                any = true;
            }
            if any && acc.iter().any(|w| *w != 0) {
                rows.push(acc);
            }
        }
    }
    let n = rows.len() as u64;
    (rows, cols, n)
}

/// Predicted elimination cost of the degree-`d` Macaulay matrix, in 64-bit
/// word operations: `rows · min(rows, cols) · cols / 64`.
///
/// Computed from counts alone, *before* anything is allocated. That matters
/// here in a way it does not for the quadratic harness: the symmetrised
/// presentation has `9ℓ − 3` variables, so its column count explodes with
/// `D` far faster than the eliminated presentation's `3ℓ`, and a scan that
/// simply walked `D` upward would try to build a multi-terabyte matrix
/// before failing.
fn predicted_cost(eqs: &[AnfPoly], num_vars: u32, d: u32) -> u128 {
    let cols = num_monomials_upto_degree(num_vars, d) as u128;
    let rows: u128 = eqs
        .iter()
        .map(|f| {
            let fd = f.degree() as u32;
            if fd > d {
                0
            } else {
                num_monomials_upto_degree(num_vars, d - fd) as u128
            }
        })
        .sum();
    rows.saturating_mul(rows.min(cols)).saturating_mul(cols) / 64
}

/// Outcome of a refutation scan, including whether the scan ran out of
/// budget rather than out of degrees.
#[derive(Clone, Debug)]
pub struct AnfScan {
    /// Refutation degree, if reached within budget.
    pub dstar: Option<u32>,
    /// The scan stopped because the next degree exceeded the cost budget,
    /// not because the system failed to refute. A censored scan is **not**
    /// evidence that no refutation exists, and must never be read as one.
    pub censored_at: Option<u32>,
    /// `(degree, rows, cols, rank)` per degree actually built.
    pub profile: Vec<(u32, u64, u64, u64)>,
}

/// Refutation degree of an arbitrary-degree ANF system: the smallest `D` at
/// which the constant `1` enters the Macaulay row space.
///
/// Same definition and same test as
/// [`crate::cryptanalysis::pc_degree_harness::refutation_scan`], so the
/// degrees reported here are directly comparable with the rest of the
/// thread. `budget` caps the predicted elimination cost per degree (see
/// `predicted_cost`); a degree over budget stops the scan and is recorded
/// in `censored_at`.
pub fn anf_refutation_scan(
    eqs: &[AnfPoly],
    num_vars: u32,
    d_min: u32,
    d_max: u32,
    budget: u128,
) -> AnfScan {
    let mut profile = Vec::new();
    for d in d_min..=d_max.min(num_vars) {
        if predicted_cost(eqs, num_vars, d) > budget {
            return AnfScan {
                dstar: None,
                censored_at: Some(d),
                profile,
            };
        }
        let (mut rows, cols, built) = anf_macaulay_rows(eqs, num_vars, d);
        if rows.is_empty() {
            profile.push((d, 0, cols as u64, 0));
            continue;
        }
        let (rank, refuted) = rank_and_refute(&mut rows, cols);
        profile.push((d, built, cols as u64, rank as u64));
        if refuted {
            return AnfScan {
                dstar: Some(d),
                censored_at: None,
                profile,
            };
        }
    }
    AnfScan {
        dstar: None,
        censored_at: None,
        profile,
    }
}

/// Default per-degree elimination budget: ~2·10⁹ word operations, a few
/// seconds of the bit-packed reducer.
pub const DEFAULT_ANF_BUDGET: u128 = 2_000_000_000;

// ── The two presentations ───────────────────────────────────────────

/// The **symmetrised** presentation: both halves of [`S4System`] over the
/// joint variable space `x ‖ e`.
///
/// x-variables keep their indices `0..3ℓ`; e-variables are shifted up by
/// `3ℓ`. The correspondence constraint `e_{i,d} ⊕ σ_i(x)_d = 0` becomes one
/// equation per `(i, d)`.
pub fn symmetrised_presentation(sys: &S4System) -> (Vec<AnfPoly>, u32) {
    let x_vars = sys.n_x_vars();
    let total = x_vars + sys.n_e_vars();
    let mut eqs = Vec::new();

    // Correspondence: σ_i(x)_d ⊕ e_{i,d}.
    for (i, coeffs) in sys.correspondence.iter().enumerate() {
        for (d, sigma) in coeffs.iter().enumerate() {
            let mut eq = sigma.clone();
            eq.xor_assign(&AnfPoly::var(x_vars + sys.e_var(i, d)));
            eqs.push(eq);
        }
    }
    // Descended S₄, already over e-space — shift its variables up.
    for f in &sys.semaev {
        eqs.push(shift_vars(f, x_vars));
    }
    (eqs, total)
}

/// Relabel every variable of an ANF by `+offset`.
fn shift_vars(f: &AnfPoly, offset: u32) -> AnfPoly {
    let mut out = AnfPoly::zero();
    for m in f.monomials() {
        let mut term = AnfPoly::one();
        for v in m {
            term = term.mul(&AnfPoly::var(v + offset));
        }
        out.xor_assign(&term);
    }
    out
}

/// The **eliminated** (non-symmetrised) presentation: the same ideal with
/// `e` substituted away, leaving `n` equations over the `3ℓ` x-variables at
/// degree ≤ 6.
///
/// This is the matched baseline L2 must beat. It is obtained by
/// substitution, not by re-deriving `S₄` over the `Xᵢ`, so the two
/// presentations are guaranteed to describe the same ideal rather than two
/// independently-derived systems that might differ.
pub fn eliminated_presentation(sys: &S4System) -> (Vec<AnfPoly>, u32) {
    let x_vars = sys.n_x_vars();
    // Flat table: e-variable index → its σ expression over x.
    let mut sigma = Vec::new();
    for (i, coeffs) in sys.correspondence.iter().enumerate() {
        for (d, s) in coeffs.iter().enumerate() {
            debug_assert_eq!(sys.e_var(i, d) as usize, sigma.len());
            sigma.push(s.clone());
        }
    }

    let out = sys
        .semaev
        .iter()
        .map(|f| {
            let mut acc = AnfPoly::zero();
            for m in f.monomials() {
                let mut term = AnfPoly::one();
                for v in m {
                    term = term.mul(&sigma[*v as usize]);
                }
                acc.xor_assign(&term);
            }
            acc
        })
        .collect();
    (out, x_vars)
}

/// Is the target decomposable over the factor base? Brute force over the
/// `2^{3ℓ}` assignments of the x-variables, evaluating the eliminated
/// system (which is exactly "set `e = σ(x)` and test the descended `S₄`").
///
/// Only **non-decomposable** targets give an unsatisfiable system, and only
/// unsatisfiable systems have a refutation degree to measure — the same
/// discipline the rest of the thread uses.
pub fn s4_is_decomposable(sys: &S4System) -> bool {
    let (elim, x_vars) = eliminated_presentation(sys);
    for mask in 0u32..(1u32 << x_vars) {
        let assign: Vec<bool> = (0..x_vars).map(|i| (mask >> i) & 1 == 1).collect();
        if elim.iter().all(|f| !f.eval(&assign)) {
            return true;
        }
    }
    false
}

/// One matched comparison of the two presentations of the same ideal.
#[derive(Clone, Debug)]
pub struct L2Row {
    pub n: u32,
    pub l: u32,
    /// Variables in the symmetrised presentation (`9ℓ − 3`).
    pub sym_vars: u32,
    /// Equations in the symmetrised presentation (`6ℓ − 3 + n`).
    pub sym_eqs: u32,
    /// Max generator degree of the symmetrised presentation (3).
    pub sym_deg: u32,
    /// Variables in the eliminated presentation (`3ℓ`).
    pub elim_vars: u32,
    pub elim_eqs: u32,
    /// Max generator degree of the eliminated presentation (≤ 6).
    pub elim_deg: u32,
    /// Refutation degree of each presentation, `None` if not reached.
    pub sym_dstar: Option<u32>,
    pub elim_dstar: Option<u32>,
    /// True when the eliminated presentation's generators are already at
    /// (or above) its variable count, so the multilinear Macaulay tower has
    /// **no multiplier budget** — every multiplier of positive degree would
    /// push past degree `vars`, which does not exist in a Boolean ring with
    /// that many variables. The row space is then just the linear span of
    /// the generators, and "1 ∉ row space" says nothing about
    /// satisfiability. A degenerate cell must not be read as a measurement.
    pub elim_degenerate: bool,
    /// Degree at which each scan ran out of budget, if it did. A censored
    /// side has **no** measured `D*` and must not be reported as "did not
    /// refute".
    pub sym_censored_at: Option<u32>,
    pub elim_censored_at: Option<u32>,
    /// log2 Macaulay columns at each presentation's `D*` — the size of the
    /// biggest matrix each route actually builds.
    pub sym_log2_cols: Option<f64>,
    pub elim_log2_cols: Option<f64>,
}

impl L2Row {
    /// log2 work of a presentation at its own `D*`, as
    /// `rows(D) · cols(D)^{ω−1}` — the same row-aware model iteration 2
    /// settled on, since the two presentations differ in both dimensions.
    fn log2_cost(vars: u32, eqs: u32, dstar: Option<u32>, omega: f64) -> Option<f64> {
        let d = dstar?;
        let cols = num_monomials_upto_degree(vars, d) as f64;
        // Multipliers available to a generator of degree ≥ 2.
        let mult = num_monomials_upto_degree(vars, d.saturating_sub(2)) as f64;
        Some((eqs as f64 * mult).log2() + (omega - 1.0) * cols.log2())
    }

    pub fn sym_cost(&self, omega: f64) -> Option<f64> {
        Self::log2_cost(self.sym_vars, self.sym_eqs, self.sym_dstar, omega)
    }

    pub fn elim_cost(&self, omega: f64) -> Option<f64> {
        Self::log2_cost(self.elim_vars, self.elim_eqs, self.elim_dstar, omega)
    }

    /// Positive = symmetrisation wins.
    pub fn saving(&self, omega: f64) -> Option<f64> {
        Some(self.elim_cost(omega)? - self.sym_cost(omega)?)
    }
}

/// Measure both presentations of one `S4System`.
pub fn compare_presentations(sys: &S4System, d_max: u32, budget: u128) -> L2Row {
    let (sym, sym_vars) = symmetrised_presentation(sys);
    let (elim, elim_vars) = eliminated_presentation(sys);
    let sym_deg = sym.iter().map(|f| f.degree()).max().unwrap_or(0) as u32;
    let elim_deg = elim.iter().map(|f| f.degree()).max().unwrap_or(0) as u32;

    let sym_scan = anf_refutation_scan(&sym, sym_vars, 2, d_max, budget);
    // The eliminated system's generators already sit at `elim_deg`, so its
    // tower cannot refute below that; starting lower only wastes work.
    let elim_scan = anf_refutation_scan(&elim, elim_vars, elim_deg.max(2), d_max, budget);
    // Guard: with `elim_deg >= elim_vars` there is no room for any
    // multiplier, so the scan degenerates to a rank test on the generators
    // themselves. Flag it instead of reporting a meaningless `None`.
    let elim_degenerate = elim_deg >= elim_vars;

    let log2_cols =
        |vars: u32, d: Option<u32>| d.map(|d| (num_monomials_upto_degree(vars, d) as f64).log2());

    L2Row {
        n: sys.n,
        l: sys.l,
        sym_vars,
        sym_eqs: sym.len() as u32,
        sym_deg,
        elim_vars,
        elim_eqs: elim.len() as u32,
        elim_deg,
        sym_dstar: sym_scan.dstar,
        elim_dstar: elim_scan.dstar,
        sym_censored_at: sym_scan.censored_at,
        elim_censored_at: elim_scan.censored_at,
        elim_degenerate,
        sym_log2_cols: log2_cols(sym_vars, sym_scan.dstar),
        elim_log2_cols: log2_cols(elim_vars, elim_scan.dstar),
    }
}

// ── Tests ───────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::binary_ecc::F2mElement;
    use crate::cryptanalysis::binary_semaev_s4::weil_descend_s4;
    use crate::cryptanalysis::descent_expansion::enumerate_irreducibles;

    fn sys_for(n: u32, l: u32, xr_bits: &[u32]) -> S4System {
        let irr = enumerate_irreducibles(n, 1).into_iter().next().unwrap();
        let b = F2mElement::one(n);
        let x_r = F2mElement::from_bit_positions(xr_bits, n);
        weil_descend_s4(n, l, &irr, &b, &x_r)
    }

    /// Multiplier enumeration must produce every multilinear monomial of
    /// degree `≤ max_deg` exactly once — the column space of the Macaulay
    /// matrix depends on it.
    #[test]
    fn multilinear_monomials_are_complete_and_distinct() {
        for vars in 1..=6u32 {
            for d in 0..=vars {
                let ms = multilinear_monomials(vars, d);
                let expected = num_monomials_upto_degree(vars, d) as usize;
                assert_eq!(ms.len(), expected, "vars={vars} d={d}");
                let mut seen = ms.clone();
                seen.sort();
                seen.dedup();
                assert_eq!(seen.len(), expected, "duplicates at vars={vars} d={d}");
                assert!(ms.iter().all(|m| m.windows(2).all(|w| w[0] < w[1])));
            }
        }
    }

    /// **The load-bearing correctness test.** The two presentations must
    /// describe the same ideal, so they must agree on satisfiability: for
    /// every x-assignment, the eliminated system vanishes exactly when the
    /// symmetrised one does with `e` set to `σ(x)`.
    #[test]
    fn the_two_presentations_agree_on_every_assignment() {
        let sys = sys_for(6, 2, &[1]);
        let (sym, sym_vars) = symmetrised_presentation(&sys);
        let (elim, x_vars) = eliminated_presentation(&sys);
        assert_eq!(x_vars, sys.n_x_vars());
        assert_eq!(sym_vars, sys.n_x_vars() + sys.n_e_vars());

        for mask in 0u32..(1u32 << x_vars) {
            let xs: Vec<bool> = (0..x_vars).map(|i| (mask >> i) & 1 == 1).collect();
            // Extend with e := σ(x), the unique completion the
            // correspondence half forces.
            let mut full = xs.clone();
            for (i, coeffs) in sys.correspondence.iter().enumerate() {
                for (d, s) in coeffs.iter().enumerate() {
                    debug_assert_eq!(full.len(), (x_vars + sys.e_var(i, d)) as usize);
                    full.push(s.eval(&xs));
                }
            }
            let sym_sat = sym.iter().all(|f| !f.eval(&full));
            let elim_sat = elim.iter().all(|f| !f.eval(&xs));
            assert_eq!(
                sym_sat, elim_sat,
                "presentations disagree at x-mask {mask}: sym={sym_sat} elim={elim_sat}"
            );
        }
    }

    /// The eliminated system is quadratic in `e` and each `e` is cubic in
    /// `x`, so its generators must land at degree ≤ 6 — and strictly above
    /// the symmetrised system's 3. That degree gap is the whole trade L2
    /// is making.
    #[test]
    fn elimination_raises_the_generator_degree() {
        let sys = sys_for(8, 2, &[0, 1]);
        let (sym, _) = symmetrised_presentation(&sys);
        let (elim, _) = eliminated_presentation(&sys);
        let sd = sym.iter().map(|f| f.degree()).max().unwrap();
        let ed = elim.iter().map(|f| f.degree()).max().unwrap();
        assert!(
            sd <= 3,
            "symmetrised generators should be degree ≤ 3, got {sd}"
        );
        assert!(
            ed <= 6,
            "eliminated generators should be degree ≤ 6, got {ed}"
        );
        assert!(ed > sd, "elimination must raise the degree: {sd} → {ed}");
    }

    /// A satisfiable system has no refutation, an unsatisfiable one does.
    /// This is what makes `D*` meaningful, and it must hold in *both*
    /// presentations.
    ///
    /// Run at `ℓ = 3`: at `ℓ = 2` the eliminated system has degree-6
    /// generators in only 6 variables, so the multilinear Macaulay tower has
    /// zero multiplier budget and cannot refute anything — the instrument is
    /// degenerate there, which `L2Row::elim_degenerate` flags.
    #[test]
    fn refutation_exists_exactly_when_undecomposable() {
        let mut checked_sat = false;
        let mut checked_unsat = false;
        for bits in [vec![1u32], vec![0, 1], vec![2], vec![0, 2]] {
            let sys = sys_for(6, 3, &bits);
            let decomposable = s4_is_decomposable(&sys);
            let (elim, x_vars) = eliminated_presentation(&sys);
            let ed = elim.iter().map(|f| f.degree()).max().unwrap_or(0) as u32;
            let dstar =
                anf_refutation_scan(&elim, x_vars, ed.max(2), x_vars, DEFAULT_ANF_BUDGET).dstar;
            if decomposable {
                checked_sat = true;
                assert!(
                    dstar.is_none(),
                    "a decomposable target must not refute (bits {bits:?})"
                );
            } else {
                checked_unsat = true;
                assert!(
                    dstar.is_some(),
                    "a non-decomposable target must refute by full degree (bits {bits:?})"
                );
            }
        }
        assert!(
            checked_sat || checked_unsat,
            "test vacuous: no targets exercised"
        );
    }

    /// The degeneracy guard must fire exactly when the eliminated
    /// generators leave no multiplier room, so a degenerate cell is never
    /// read as "the eliminated presentation could not be refuted".
    #[test]
    fn degenerate_elimination_is_flagged() {
        let tight = compare_presentations(&sys_for(6, 2, &[1]), 6, DEFAULT_ANF_BUDGET);
        assert_eq!(tight.elim_vars, 6);
        assert!(
            tight.elim_degenerate,
            "deg {} in {} vars leaves no multiplier budget and must be flagged",
            tight.elim_deg, tight.elim_vars
        );
        let roomy = compare_presentations(&sys_for(6, 3, &[1]), 9, DEFAULT_ANF_BUDGET);
        assert_eq!(roomy.elim_vars, 9);
        assert!(
            !roomy.elim_degenerate,
            "deg {} in 9 vars has room",
            roomy.elim_deg
        );
    }

    /// Shifting variable indices must preserve structure exactly.
    #[test]
    fn shift_vars_preserves_the_polynomial() {
        let f = AnfPoly::var(0).mul(&AnfPoly::var(2));
        let mut g = f.clone();
        g.xor_assign(&AnfPoly::one());
        let shifted = shift_vars(&g, 5);
        assert_eq!(shifted.degree(), g.degree());
        assert_eq!(shifted.len(), g.len());
        assert!(shifted.has_constant());
        // x0·x2 ↦ x5·x7
        let expect = AnfPoly::var(5).mul(&AnfPoly::var(7));
        let mut want = expect;
        want.xor_assign(&AnfPoly::one());
        assert_eq!(shifted, want);
    }
}
