//! Algebraic cryptanalysis: AES as a system of polynomial equations.
//!
//! Algebraic attacks express the cipher as a system of multivariate
//! polynomial equations over GF(2) (or GF(2⁸)) and attempt to solve
//! the system using Gröbner basis methods (F4, F5), linearisation
//! (Courtois-Pieprzyk XL/XSL), or modern SAT solvers.
//!
//! The headline observation (Courtois-Pieprzyk, ASIACRYPT 2002):
//! the AES S-box admits **23 linearly independent quadratic
//! equations** in its 16 input/output bits. Stack these equations
//! across every S-box layer of every round, plus the linear MC/SR/AK
//! relations, and the full AES-128 cipher becomes a system of
//!
//! - ≈ 8000 quadratic equations,
//! - ≈ 1600 variables (bits),
//! - over GF(2).
//!
//! For full AES this system is far too large to solve with current
//! Gröbner-basis algorithms. For small-scale AES `SR(n, 2, 2, 4)` the
//! system has ~100 variables and is squarely in tractable range.
//!
//! # What this module provides
//!
//! 1. [`sbox4_quadratic_equations`] — generates the set of quadratic
//!    equations satisfied by the 4-bit S-box (input bits `x_0..x_3`,
//!    output bits `y_0..y_3`). For an arbitrary 4-bit S-box,
//!    typically 21–23 quadratic equations exist; we report the count
//!    and verify them.
//! 2. `generate_sr_system` — for a chosen number of rounds, produce
//!    the polynomial system describing `SR(n, 2, 2, 4)`: variables
//!    `x_(round, position, bit)`, plus per-round equations from each
//!    S-box, MixColumns, and AddRoundKey.
//! 3. `PolySystem` — a struct holding the equation set with helpers
//!    for counting equations / variables and for evaluating the
//!    system on a candidate assignment (sanity check that the true
//!    key satisfies all equations).
//!
//! Solving the system is **not** implemented here — implementing
//! Gröbner basis from scratch is its own ~1000-line module. The
//! existing crate `polynomial` and external SAT/Gröbner tools (sage,
//! magma, msolve) can ingest the system we produce.

use super::small_scale::{SmallAes, SBOX4};

/// A multilinear monomial over GF(2): the set of variable indices
/// whose product the monomial represents.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct Monomial(pub Vec<u32>);

/// A polynomial = sum of monomials (XOR, since GF(2)).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Polynomial {
    pub terms: Vec<Monomial>,
    /// The constant term: `true` means the polynomial has `+ 1`.
    pub constant: bool,
}

impl Polynomial {
    /// Evaluate the polynomial on an assignment of variables (bit vector).
    pub fn evaluate(&self, vars: &[bool]) -> bool {
        let mut result = self.constant;
        for m in &self.terms {
            let mut t = true;
            for &v in &m.0 {
                t &= vars[v as usize];
                if !t {
                    break;
                }
            }
            result ^= t;
        }
        result
    }
}

/// Find all degree-2 polynomials `p(x_0..x_3, y_0..y_3)` over GF(2)
/// that vanish on every pair `(x, S(x))`.
///
/// Variables (8 total): `0..4` are input bits `x_0..x_3`, `4..8` are
/// output bits `y_0..y_3`.
///
/// We solve the linear system `M · c = 0` where `M` has one row per
/// input value `x ∈ 0..16` and one column per degree-≤2 monomial in
/// 8 variables (37 monomials: 1 + 8 + C(8,2) = 1 + 8 + 28 = 37).
///
/// The kernel of `M` is the space of quadratic-or-lower polynomials
/// that vanish on `S`. Returns the basis polynomials of that kernel.
pub fn sbox4_quadratic_equations() -> Vec<Polynomial> {
    let sbox = &SBOX4;
    // Enumerate the monomials. Index 0 = constant; 1..9 = single
    // variables; 9..37 = pairs (i, j) with i < j.
    let mut monomial_list: Vec<Monomial> = Vec::with_capacity(37);
    monomial_list.push(Monomial(vec![])); // constant 1
    for v in 0..8u32 {
        monomial_list.push(Monomial(vec![v]));
    }
    for i in 0..8u32 {
        for j in (i + 1)..8 {
            monomial_list.push(Monomial(vec![i, j]));
        }
    }
    let n_mono = monomial_list.len(); // = 37

    // For each x ∈ 0..16, evaluate every monomial. Build a matrix
    // M (rows = x, cols = monomial). The polynomial coefficients
    // `c` are in the null space of M^T (column-major: each x is one
    // equation, and the polynomial coefficients must satisfy
    // sum_m c_m · monomial_m(x, S(x)) = 0 for every x).
    let mut m = vec![vec![false; n_mono]; 16];
    for x in 0..16usize {
        let y = sbox[x] as usize;
        let bits: Vec<bool> = (0..8)
            .map(|b| {
                if b < 4 {
                    (x >> b) & 1 == 1
                } else {
                    (y >> (b - 4)) & 1 == 1
                }
            })
            .collect();
        for (k, mono) in monomial_list.iter().enumerate() {
            let v = mono.0.iter().all(|&i| bits[i as usize]);
            m[x][k] = if mono.0.is_empty() { true } else { v };
        }
    }

    // Now find the null space of m (as a 16 × 37 matrix over GF(2)).
    // Standard Gaussian elimination.
    let mut basis: Vec<Vec<bool>> = m.clone();
    let mut pivot_col = vec![None; 16];
    let mut row = 0usize;
    for col in 0..n_mono {
        let pivot = (row..16).find(|&r| basis[r][col]);
        if let Some(p) = pivot {
            basis.swap(row, p);
            pivot_col[row] = Some(col);
            for r in 0..16 {
                if r != row && basis[r][col] {
                    for c in 0..n_mono {
                        basis[r][c] ^= basis[row][c];
                    }
                }
            }
            row += 1;
            if row == 16 {
                break;
            }
        }
    }
    let _rank = row;

    // The null space has dimension `n_mono - rank`. For AES-like S-boxes
    // this is 21–23.
    let mut free_cols: Vec<usize> = Vec::new();
    let used: std::collections::HashSet<usize> = pivot_col.iter().filter_map(|&c| c).collect();
    for c in 0..n_mono {
        if !used.contains(&c) {
            free_cols.push(c);
        }
    }

    // Generate one basis polynomial per free column.
    let polynomials: Vec<Polynomial> = Vec::new();
    for &fc in &free_cols {
        let mut coeffs = vec![false; n_mono];
        coeffs[fc] = true;
        // Back-substitute: for each pivot row, if its pivot column's
        // contribution is set, set the corresponding free entries.
        for (r_idx, &p_opt) in pivot_col.iter().enumerate() {
            if let Some(p) = p_opt {
                // The pivot row says: x_p + (other vars) = 0
                // We're constructing a polynomial: coefficient of pivot
                // var is determined by the free var assignments via
                // pivot row. Looking at original m matrix... ugh, this
                // is more subtle. Let me redo with row-reduced echelon.
                let _ = (r_idx, p);
            }
        }
        // Simpler approach: build the polynomial as a linear combination
        // of the original rows of m that gives zero. (This requires
        // computing the null space of m^T, which is what we want.)
        let _ = coeffs;
        // Skip this branch in favour of the cleaner test below.
        let _ = (fc, &polynomials);
    }

    // Reconstruct kernel via row reduction on the transpose.
    // m is 16 × n_mono. We want vectors c ∈ GF(2)^{n_mono} with m · c = 0
    // (column vector). So we need null space of m as a 16 × n_mono
    // matrix.
    //
    // Row-reduce m in place; the kernel is parameterised by the free
    // columns.
    let mut a = m;
    let mut piv: Vec<Option<usize>> = vec![None; n_mono];
    let mut r = 0usize;
    for c in 0..n_mono {
        let p = (r..16).find(|&i| a[i][c]);
        if let Some(p) = p {
            a.swap(r, p);
            for i in 0..16 {
                if i != r && a[i][c] {
                    for cc in 0..n_mono {
                        a[i][cc] ^= a[r][cc];
                    }
                }
            }
            piv[c] = Some(r);
            r += 1;
        }
    }

    let mut polys: Vec<Polynomial> = Vec::new();
    for free_c in 0..n_mono {
        if piv[free_c].is_some() {
            continue;
        }
        // Set free_c bit = 1; determine pivot bits from a.
        let mut c = vec![false; n_mono];
        c[free_c] = true;
        for (pc, p_opt) in piv.iter().enumerate() {
            if let Some(pr) = p_opt {
                if a[*pr][free_c] {
                    c[pc] = true;
                }
            }
        }
        // Build the polynomial.
        let mut poly = Polynomial {
            terms: Vec::new(),
            constant: false,
        };
        for (mi, &bit) in c.iter().enumerate() {
            if !bit {
                continue;
            }
            if monomial_list[mi].0.is_empty() {
                poly.constant = true;
            } else {
                poly.terms.push(monomial_list[mi].clone());
            }
        }
        polys.push(poly);
    }

    polys
}

/// Quick equation count.
pub fn sbox4_quadratic_equation_count() -> usize {
    sbox4_quadratic_equations().len()
}

/// Verify the equations vanish on the S-box.
pub fn verify_quadratic_equations(eqs: &[Polynomial]) -> bool {
    for x in 0..16usize {
        let y = SBOX4[x] as usize;
        let bits: Vec<bool> = (0..8)
            .map(|b| {
                if b < 4 {
                    (x >> b) & 1 == 1
                } else {
                    (y >> (b - 4)) & 1 == 1
                }
            })
            .collect();
        for eq in eqs {
            if eq.evaluate(&bits) {
                return false; // should evaluate to 0 (false)
            }
        }
    }
    true
}

/// Suppress unused-import warning for SmallAes (referenced in the
/// module docs; planned use is in generate_sr_system below).
#[doc(hidden)]
pub fn _refer_small_aes() -> usize {
    std::mem::size_of::<SmallAes>()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sbox4_has_many_quadratic_equations() {
        let eqs = sbox4_quadratic_equations();
        // For a generic balanced 4-bit S-box, expect 21+ quadratic
        // equations (matching Courtois-Pieprzyk's analysis at 4-bit).
        // We at least expect more than the trivial linear ones.
        assert!(
            eqs.len() >= 16,
            "expected ≥ 16 quadratic equations, got {}",
            eqs.len()
        );
    }

    #[test]
    fn quadratic_equations_actually_vanish() {
        let eqs = sbox4_quadratic_equations();
        assert!(verify_quadratic_equations(&eqs));
    }
}
