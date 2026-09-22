//! What one point decomposition is allowed to cost, if index calculus is to
//! beat Pollard rho on a binary curve.
//!
//! Every other cost comparison in this tree is either a *ratio*
//! ([`koblitz_speedup_model`](super::koblitz_index_calculus::koblitz_speedup_model)
//! gives the Frobenius discount, not an absolute cost) or a *measurement*
//! (the `vs_rho` block of `ic workflow` times a run that already happened).
//! Neither answers the question asked before a run is worth starting: at this
//! degree and arity, how many operations may a single decomposition take?
//!
//! This module answers it by charging relation collection **and** sparse linear
//! algebra against the same rho budget and inverting for what is left.
//!
//! # The pipeline being charged
//!
//! Factor base `F_V = {P : x(P) ∈ V}` for an `F_2`-subspace `V` of dimension
//! `l`, targets decomposed into `m` summands:
//!
//! | quantity | value |
//! |---|---|
//! | `\|F\|` | `2^l` |
//! | `R` | mean Frobenius orbit size on `V` (see [`orbit_reduction`]) |
//! | `D` | `\|F\| / R`, the linear-algebra dimension |
//! | `p` | `min(1, 2^(ml−n) / m!)`, a random target decomposes |
//! | relation collection | `(D / p) · C_solve` |
//! | linear algebra | `m · D²` |
//! | memory | `D` entries |
//!
//! Rho is `√(πr/2) / √(2n)` — the same formula as
//! [`rho_expected_steps`](super::koblitz_index_calculus::rho_expected_steps),
//! evaluated in logarithms so degrees past 63 stay representable.
//!
//! # The inversion
//!
//! Linear algebra does not depend on the solver at all, so it is a hard gate:
//! a cell whose linear algebra alone exceeds rho is lost before any
//! decomposition is attempted. Given a cell that passes it,
//!
//! ```text
//! log2 budget = log2(rho − linear algebra) − log2(attempts)
//! ```
//!
//! is the number of operations one decomposition may take. **A non-positive
//! budget means the cell loses to rho even with a free decomposition oracle**,
//! so no solver engineering can rescue it.
//!
//! # The second gate
//!
//! A decomposition must first *build* its Weil-descended system. Because every
//! Frobenius power is `F_2`-linear, a `K`-monomial `x^e` costs Boolean degree
//! equal to the Hamming weight of `e`, not `e`; `S_{m+1}` has degree `2^(m−1)`
//! per variable, whose largest Hamming weight is `m−1`, and each `x_i` is a
//! linear form in only `l` Boolean variables. So the descended degree is
//! `m · min(m−1, l)` ([`boolean_degree`]) and the system has about
//! `Σ_{i ≤ D} C(ml, i)` monomials ([`log2_anf_monomials`]). Forming it costs at
//! least one operation per monomial, so when that count exceeds the whole
//! budget the obstruction is the *size of the system*, not the difficulty of
//! solving it.
//!
//! That charge binds every method which materialises the system — Gröbner,
//! WDSat, CNF-SAT, crossbred, msolve all do. It does **not** bind a method that
//! never materialises it, and [`BudgetCell::anf_blocks`] is therefore a
//! statement about implemented approaches rather than a lower bound.
//!
//! # What this is not
//!
//! A verdict under a declared model, not an attack and not a lower bound on
//! ECDLP. Two charges are load-bearing and deliberately exposed so they can be
//! argued with: sparse linear algebra at `m·D²` (a method with a materially
//! lower exponent would relax the gate on `l`), and one operation per ANF
//! monomial. Polylog factors are dropped on both sides, so the comparison is
//! fair to within them but not to within constants.

use super::koblitz_index_calculus::{available_subspace_dimensions, order_of_2_mod_n};

/// Charged cost of one `(n, m, l)` choice. Every field is a base-2 logarithm
/// unless its name says otherwise.
#[derive(Clone, Debug, PartialEq)]
pub struct BudgetCell {
    /// Extension degree.
    pub n: u32,
    /// Factor-base points per relation.
    pub m: usize,
    /// `F_2`-dimension of the factor-base subspace.
    pub l: u32,
    /// Mean Frobenius orbit size on the subspace; `1.0` when the subspace is
    /// not stable, or is the line `F_2` on which Frobenius acts trivially.
    pub orbit_reduction: f64,
    /// `log2` of the rho step count for this degree.
    pub log2_rho: f64,
    /// `log2 |F|`.
    pub log2_factor_base: f64,
    /// `log2 D`, the linear-algebra dimension and the memory in entries.
    pub log2_la_dimension: f64,
    /// `log2` of the sparse linear-algebra cost.
    pub log2_linear_algebra: f64,
    /// `log2` of the probability that a random target decomposes.
    pub log2_decomposition_probability: f64,
    /// `log2` of the number of decomposition attempts.
    pub log2_attempts: f64,
    /// `log2` of the operations one decomposition may take. `None` when the
    /// linear algebra alone already exceeds rho.
    pub log2_budget: Option<f64>,
    /// The cell loses to rho even with a decomposition oracle that is free.
    pub free_oracle_loses: bool,
    /// Boolean degree of the Weil-descended system, `m · min(m−1, l)`.
    pub boolean_degree: u32,
    /// Boolean variables in the descended system, `m · l`.
    pub boolean_variables: u32,
    /// `log2` of the descended system's monomial count.
    pub log2_anf_monomials: f64,
    /// `log2 anf_monomials − log2 budget`. Positive means the system cannot be
    /// written down inside the whole budget.
    pub log2_anf_deficit: Option<f64>,
    /// The system is too large to form within the budget, whatever solves it.
    pub anf_blocks: bool,
    /// `log2 budget / boolean_variables`: the exponent a solver must achieve.
    pub required_solver_exponent: Option<f64>,
}

impl BudgetCell {
    /// The cell is worth attempting: the linear algebra fits, the budget is
    /// positive, and the system can be built inside it.
    pub fn viable(&self) -> bool {
        self.log2_budget.is_some_and(|b| b > 0.0) && !self.anf_blocks
    }
}

/// `log2` of `m!`, by summing logarithms so large `m` cannot overflow.
fn log2_factorial(m: usize) -> f64 {
    (2..=m).map(|i| (i as f64).log2()).sum()
}

/// `log2` of the rho step count on a degree-`n` binary Koblitz curve.
///
/// The subgroup order is taken as `2^n` divided by a cofactor of 2 or 4, the
/// Koblitz family's own. Pinned to the same `√(πr/2) / √(2n)` formula as
/// [`rho_expected_steps`](super::koblitz_index_calculus::rho_expected_steps)
/// and checked against it in the tests; evaluated in logarithms so degrees
/// past 63 — where that function's `u64` argument cannot reach — still work.
pub fn rho_log2(n: u32) -> f64 {
    let log2_r = f64::from(n) - 2.0; // cofactor 4, the usual Koblitz value
    0.5 * (log2_r + (std::f64::consts::PI / 2.0).log2()) - 0.5 * f64::from(2 * n).log2()
}

/// Mean Frobenius orbit size on a stable subspace of dimension `l` of
/// `F_(2^n)`, for `n` an odd prime.
///
/// Frobenius fixes exactly the subfield `F_2`, so a stable subspace splits into
/// `2^a` fixed points — `a = 1` when the subspace contains the line, `0` when
/// it does not — and full orbits of length `n` on everything else. Returns
/// `1.0` for a dimension that is not attainable, and for the fixed line itself,
/// where the orbits are singletons and the quotient buys nothing.
///
/// For composite `n` the orbit lengths are the divisors of `n` rather than
/// `1` and `n`; this returns `None` there rather than reporting a wrong mean.
pub fn orbit_reduction(n: u32, l: u32) -> Option<f64> {
    if !is_prime(n) || n == 2 {
        return None;
    }
    if l == 0 || !available_subspace_dimensions(n).contains(&l) {
        return Some(1.0);
    }
    let d = order_of_2_mod_n(n)?;
    // Attainable dimensions for prime n are a + b·d with a in {0, 1}: the
    // subspace contains the fixed line exactly when l ≡ 1 (mod d).
    let a = u32::from(l % d == 1 || l == 1);
    if l == a {
        return Some(1.0); // the fixed line, or nothing
    }
    let elements = exp2(f64::from(l));
    let fixed = exp2(f64::from(a));
    let orbits = fixed + (elements - fixed) / f64::from(n);
    Some(elements / orbits)
}

/// Boolean degree of the Weil-descended system: `m · min(m−1, l)`.
///
/// The `min` is not decoration. Each `x_i` is a linear form in only `l` Boolean
/// variables, so a product of more than `l` of its Frobenius powers cannot
/// exceed degree `l`; at `l = 2, m = 4` the degree is 8, not 12.
pub fn boolean_degree(m: usize, l: u32) -> u32 {
    m as u32 * ((m as u32).saturating_sub(1)).min(l)
}

/// `log2` of `Σ_{i ≤ degree} C(variables, i)`, the descended system's monomial
/// count, summed in the log domain so large degrees stay representable.
pub fn log2_anf_monomials(variables: u32, degree: u32) -> f64 {
    let d = degree.min(variables);
    let mut log2_term = 0.0f64; // C(v, 0) = 1
    let mut acc = f64::NEG_INFINITY; // the empty sum is 0, not 1
    for i in 0..=d {
        if i > 0 {
            log2_term += (f64::from(variables - i + 1)).log2() - (f64::from(i)).log2();
        }
        acc = log2_sum_exp2(acc, log2_term);
    }
    acc
}

/// Charge one `(n, m, l)` cell. `use_frobenius` decides whether the orbit
/// quotient is credited, which isolates exactly what it buys.
pub fn evaluate(n: u32, m: usize, l: u32, use_frobenius: bool) -> BudgetCell {
    let r = if use_frobenius {
        orbit_reduction(n, l).unwrap_or(1.0)
    } else {
        1.0
    };
    let log2_fb = f64::from(l);
    let log2_d = log2_fb - r.log2();
    let log2_p = (f64::from(m as u32 * l) - f64::from(n) - log2_factorial(m)).min(0.0);
    let log2_attempts = log2_d - log2_p;
    let log2_la = (m as f64).log2() + 2.0 * log2_d;
    let rho = rho_log2(n);
    let degree = boolean_degree(m, l);
    let variables = m as u32 * l;
    let anf = log2_anf_monomials(variables, degree);

    // rho − linear algebra, in logarithms; None when the gate is already lost.
    let log2_budget = if log2_la >= rho {
        None
    } else {
        Some(rho + (1.0 - exp2(log2_la - rho)).log2() - log2_attempts)
    };
    let anf_deficit = log2_budget.map(|b| anf - b);
    BudgetCell {
        n,
        m,
        l,
        orbit_reduction: r,
        log2_rho: rho,
        log2_factor_base: log2_fb,
        log2_la_dimension: log2_d,
        log2_linear_algebra: log2_la,
        log2_decomposition_probability: log2_p,
        log2_attempts,
        log2_budget,
        free_oracle_loses: log2_budget.is_none_or(|b| b <= 0.0),
        boolean_degree: degree,
        boolean_variables: variables,
        log2_anf_monomials: anf,
        log2_anf_deficit: anf_deficit,
        anf_blocks: anf_deficit.is_none_or(|d| d > 0.0),
        required_solver_exponent: log2_budget
            .filter(|_| variables > 0)
            .map(|b| b / f64::from(variables)),
    }
}

/// The dimension leaving the largest budget at this arity.
///
/// Every dimension below `n` is a candidate whether or not `use_frobenius` is
/// set: a subspace that is not Frobenius-stable is a perfectly legal factor
/// base, it simply forfeits the orbit quotient and is charged with `R = 1`.
/// Crediting Frobenius must widen what a cell is worth, never narrow what may
/// be chosen.
pub fn best_cell(n: u32, m: usize, use_frobenius: bool) -> Option<BudgetCell> {
    (1..n)
        .map(|l| evaluate(n, m, l, use_frobenius))
        .filter(|c| c.log2_budget.is_some())
        .max_by(|a, b| {
            a.log2_budget
                .unwrap()
                .partial_cmp(&b.log2_budget.unwrap())
                .unwrap_or(std::cmp::Ordering::Equal)
        })
}

/// The smallest arity with a positive budget at some dimension. Below it, no
/// decomposition oracle however fast beats rho at this degree.
pub fn minimum_viable_arity(n: u32, use_frobenius: bool, m_max: usize) -> Option<usize> {
    (2..=m_max).find(|&m| {
        best_cell(n, m, use_frobenius).is_some_and(|c| c.log2_budget.is_some_and(|b| b > 0.0))
    })
}

fn exp2(x: f64) -> f64 {
    x.exp2()
}

/// `log2(2^a + 2^b)` without leaving the log domain. `NEG_INFINITY` is the
/// additive identity, standing for a term of zero.
fn log2_sum_exp2(a: f64, b: f64) -> f64 {
    if a == f64::NEG_INFINITY {
        return b;
    }
    if b == f64::NEG_INFINITY {
        return a;
    }
    let (hi, lo) = if a > b { (a, b) } else { (b, a) };
    hi + (1.0 + exp2(lo - hi)).log2()
}

fn is_prime(n: u32) -> bool {
    if n < 2 {
        return false;
    }
    let mut i = 2u32;
    while i.saturating_mul(i) <= n {
        if n.is_multiple_of(i) {
            return false;
        }
        i += 1;
    }
    true
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::koblitz_index_calculus::rho_expected_steps;

    fn close(a: f64, b: f64, tol: f64) -> bool {
        (a - b).abs() <= tol
    }

    #[test]
    fn rho_in_logarithms_agrees_with_the_step_count_it_is_pinned_to() {
        // rho_log2 exists only because rho_expected_steps takes a u64 order and
        // so cannot reach degree 131, let alone 571. Where both are defined
        // they must be the same number.
        for n in [11u32, 19, 31, 41, 53] {
            let r = 1u64 << (n - 2); // the cofactor-4 order rho_log2 assumes
            let direct = rho_expected_steps(r, n).log2();
            assert!(
                close(rho_log2(n), direct, 1e-9),
                "n = {n}: {} vs {direct}",
                rho_log2(n)
            );
        }
    }

    #[test]
    fn two_is_primitive_at_131_and_163_so_no_usable_dimension_exists() {
        // The whole stable lattice at these degrees, from the existing
        // classification: nothing between the fixed line and everything.
        for n in [131u32, 163] {
            assert_eq!(
                available_subspace_dimensions(n),
                vec![0, 1, n - 1, n],
                "degree {n}"
            );
        }
    }

    #[test]
    fn frobenius_fixes_only_the_line_so_the_line_itself_buys_nothing() {
        for n in [41u32, 43, 131, 233] {
            assert_eq!(orbit_reduction(n, 1), Some(1.0), "degree {n}");
        }
    }

    #[test]
    fn mean_orbit_size_approaches_the_degree_on_a_faithful_subspace() {
        // Values computed independently of this implementation.
        assert!(close(orbit_reduction(41, 20).unwrap(), 40.9984, 1e-3));
        assert!(close(orbit_reduction(41, 21).unwrap(), 40.9984, 1e-3));
        assert!(close(orbit_reduction(43, 14).unwrap(), 42.8901, 1e-3));
        assert!(close(orbit_reduction(43, 15).unwrap(), 42.8901, 1e-3));
        assert!(close(orbit_reduction(131, 130).unwrap(), 131.0, 1e-6));
    }

    #[test]
    fn composite_degrees_are_refused_rather_than_answered_wrongly() {
        // Orbit lengths there are the divisors of n, not just 1 and n.
        assert_eq!(orbit_reduction(15, 4), None);
        assert_eq!(orbit_reduction(21, 6), None);
    }

    #[test]
    fn the_descended_degree_caps_at_m_times_l() {
        assert_eq!(boolean_degree(2, 8), 2);
        assert_eq!(boolean_degree(3, 8), 6);
        assert_eq!(boolean_degree(4, 8), 12);
        assert_eq!(boolean_degree(5, 8), 20);
        // l < m − 1: a product of more Frobenius powers than there are
        // variables cannot exceed degree l.
        assert_eq!(boolean_degree(4, 2), 8);
        assert_eq!(boolean_degree(4, 3), 12);
    }

    #[test]
    fn the_monomial_count_matches_a_small_binomial_sum_computed_by_hand() {
        // Σ_{i ≤ 2} C(8, i) = 1 + 8 + 28 = 37
        assert!(close(log2_anf_monomials(8, 2), 37f64.log2(), 1e-9));
        // Σ_{i ≤ 12} C(12, i) = 2^12: the degree cap is above the variable count
        assert!(close(log2_anf_monomials(12, 12), 12.0, 1e-9));
        assert!(close(log2_anf_monomials(12, 99), 12.0, 1e-9));
    }

    #[test]
    fn arity_two_loses_to_rho_at_every_standardised_binary_degree() {
        // Not "is slower": loses with a decomposition oracle that costs nothing.
        for n in [113u32, 127, 131, 163, 233, 239, 283, 409, 571] {
            let best = best_cell(n, 2, true).expect("linear algebra fits somewhere");
            assert!(
                best.free_oracle_loses,
                "degree {n} unexpectedly left an arity-2 budget of {:?}",
                best.log2_budget
            );
        }
    }

    #[test]
    fn the_linear_algebra_gate_forces_arity_four_without_the_orbit_quotient() {
        for n in [113u32, 127, 131, 163, 233, 239, 283, 409, 571] {
            assert_eq!(minimum_viable_arity(n, false, 8), Some(4), "degree {n}");
        }
    }

    #[test]
    fn the_orbit_quotient_is_what_keeps_arity_three_alive_where_it_is_alive() {
        // Exactly the degrees with a faithful stable dimension near n/3.
        for n in [113u32, 127, 233] {
            assert_eq!(minimum_viable_arity(n, true, 8), Some(3), "degree {n}");
        }
        // and cannot rescue the degrees where 2 is primitive
        for n in [131u32, 163] {
            assert_eq!(minimum_viable_arity(n, true, 8), Some(4), "degree {n}");
        }
    }

    #[test]
    fn below_the_crossover_the_system_is_too_large_to_write_down() {
        // The obstruction is the size of the system, not the solver: the ANF
        // exceeds the entire per-decomposition budget.
        for n in [113u32, 127, 131, 163, 233, 239, 283] {
            let best = (3..=6)
                .filter_map(|m| best_cell(n, m, true))
                .filter(|c| c.log2_budget.is_some_and(|b| b > 0.0))
                .min_by(|a, b| {
                    a.log2_anf_deficit
                        .unwrap()
                        .partial_cmp(&b.log2_anf_deficit.unwrap())
                        .unwrap()
                })
                .expect("some arity has a budget");
            assert!(
                best.anf_blocks,
                "degree {n} at m = {} unexpectedly fits: deficit {:?}",
                best.m, best.log2_anf_deficit
            );
        }
    }

    #[test]
    fn above_the_crossover_the_system_fits_and_the_question_becomes_the_solver() {
        // The ANF grows polynomially in n while the rho budget grows
        // exponentially, so the polynomial must eventually pass under it.
        for n in [409u32, 571] {
            let cell = best_cell(n, 4, true).expect("a dimension exists");
            assert!(
                !cell.anf_blocks,
                "degree {n} deficit {:?}",
                cell.log2_anf_deficit
            );
            assert!(cell.viable(), "degree {n}");
            let exponent = cell.required_solver_exponent.unwrap();
            assert!(
                (0.15..0.30).contains(&exponent),
                "degree {n} required solver exponent {exponent}"
            );
        }
    }

    #[test]
    fn the_crossover_lies_strictly_between_283_and_409() {
        let blocked = |n: u32| {
            (3..=6)
                .filter_map(|m| best_cell(n, m, true))
                .filter(|c| c.log2_budget.is_some_and(|b| b > 0.0))
                .all(|c| c.anf_blocks)
        };
        assert!(blocked(283), "283 should still be blocked");
        assert!(!blocked(409), "409 should already fit");
    }
}
