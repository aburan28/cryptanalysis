//! Fast exhaustive search over quadratic Boolean systems, for the same
//! Semaev ANF the WDSat path emits.
//!
//! Inspired by the LIP6 / ALMASTY MQ suite
//! (<https://gitlab.lip6.fr/almasty/mq>, public domain):
//!
//! - **Moebius transform** (`moebius.c`) — pack ANF coefficients into a
//!   `2^n` table and convert to the truth table in `O(n·2^n)`; zeros are
//!   solutions.  Fallback when Monica does not apply.
//! - **Monica** (`monica.c`, `ffs.h`) — striped-down Crossbred: linearise
//!   `v ≈ √(2m)` variables and FFS-enumerate the rest.  Preferred when the
//!   cost model says it beats Möbius (see [`crate::cryptanalysis::mq_monica`]).
//!   Cubic chained systems still stay on SAT / WDSat.
//!
//! Also informed by Bouillaguet’s
//! [`libfes-lite`](https://github.com/cbouilla/libfes-lite).  This is a
//! study-library port of the *ideas*, not a binding to those trees.
//!
//! Restricted to degree ≤ 2, `n_vars ≤ 24`, and ≤ 64 equations.  Chained
//! `m ≥ 3` Semaev systems are cubic and are refused here.

use super::wdsat_oracle::AnfRow;
use crate::cryptanalysis::pq_groebner_f2::F2BoolPoly;

/// Packed quadratic form over `n` Boolean variables: constant, linear
/// coefficients, and upper-triangular quadratic coefficients.
#[derive(Clone, Debug)]
pub struct QuadraticForm {
    pub n: usize,
    pub constant: bool,
    pub linear: Vec<bool>,
    /// `quad[i][j]` for `0 ≤ j < i < n` is the coefficient of `x_i x_j`.
    pub quad: Vec<Vec<bool>>,
}

impl QuadraticForm {
    /// Convert an ANF row; returns `None` if any monomial has degree > 2.
    pub fn from_anf_row(row: &AnfRow, n: usize) -> Option<Self> {
        let mut form = Self {
            n,
            constant: row.constant,
            linear: vec![false; n],
            quad: (0..n).map(|i| vec![false; i]).collect(),
        };
        for mono in &row.monomials {
            match mono.len() {
                0 => form.constant = !form.constant,
                1 => {
                    let v = mono[0] as usize;
                    if v >= n {
                        return None;
                    }
                    form.linear[v] = !form.linear[v];
                }
                2 => {
                    let mut a = mono[0] as usize;
                    let mut b = mono[1] as usize;
                    if a == b || a >= n || b >= n {
                        return None;
                    }
                    if a < b {
                        std::mem::swap(&mut a, &mut b);
                    }
                    form.quad[a][b] = !form.quad[a][b];
                }
                _ => return None,
            }
        }
        Some(form)
    }

    pub fn from_poly(poly: &F2BoolPoly) -> Option<Self> {
        Self::from_anf_row(&AnfRow::from_poly(poly), poly.n_vars)
    }

    /// Evaluate at a bit-packed point (`bit i` = value of `x_i`).
    pub fn eval(&self, point: u64) -> bool {
        let mut v = self.constant;
        for i in 0..self.n {
            if ((point >> i) & 1) == 1 && self.linear[i] {
                v = !v;
            }
        }
        for i in 0..self.n {
            if ((point >> i) & 1) == 0 {
                continue;
            }
            for j in 0..i {
                if ((point >> j) & 1) == 1 && self.quad[i][j] {
                    v = !v;
                }
            }
        }
        v
    }

    /// XOR this form's ANF coefficients into bit `eq` of a Moebius table.
    fn scatter_anf(&self, table: &mut [u64], eq: usize) {
        let bit = 1u64 << eq;
        if self.constant {
            table[0] ^= bit;
        }
        for i in 0..self.n {
            if self.linear[i] {
                table[1 << i] ^= bit;
            }
        }
        for i in 0..self.n {
            for j in 0..i {
                if self.quad[i][j] {
                    table[(1 << i) | (1 << j)] ^= bit;
                }
            }
        }
    }
}

/// In-place Möbius / zeta transform over the Boolean lattice, as in
/// ALMASTY `moebius.c` (`small`): after this, `table[x]` holds the
/// packed truth-table values of every equation at assignment `x`.
pub fn moebius_transform(table: &mut [u64], n: usize) {
    debug_assert_eq!(table.len(), 1usize << n);
    for i in 0..n {
        let sz = 1usize << i;
        let mut pos = 0usize;
        while pos < table.len() {
            for j in 0..sz {
                table[pos + sz + j] ^= table[pos + j];
            }
            pos += 2 * sz;
        }
    }
}

/// Pack quadratic forms into an ANF table and solve by Möbius transform.
///
/// Returns every common zero, capped at `max_solutions`.  Needs
/// `n ≤ 24` and `forms.len() ≤ 64`.
pub fn moebius_find_all(forms: &[QuadraticForm], max_solutions: usize) -> Option<Vec<u64>> {
    if forms.is_empty() {
        return Some(vec![0]);
    }
    let n = forms[0].n;
    if n > 24 || forms.len() > 64 || forms.iter().any(|f| f.n != n) {
        return None;
    }
    let mut table = vec![0u64; 1usize << n];
    for (eq, form) in forms.iter().enumerate() {
        form.scatter_anf(&mut table, eq);
    }
    moebius_transform(&mut table, n);
    let mut out = Vec::new();
    for (x, packed) in table.into_iter().enumerate() {
        if packed == 0 {
            out.push(x as u64);
            if out.len() >= max_solutions {
                break;
            }
        }
    }
    Some(out)
}

/// Which quadratic FES backend produced a result.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FesBackend {
    Monica,
    Moebius,
}

/// Prefer Möbius for `n ≤ 24`; Monica only when Möbius refuses / cost model wins.
pub fn fes_find_all_auto(
    forms: &[QuadraticForm],
    max_solutions: usize,
) -> Option<(Vec<u64>, FesBackend)> {
    if forms.is_empty() {
        return Some((vec![0], FesBackend::Moebius));
    }
    let n = forms[0].n;
    let m = forms.len();
    if n > 24 || crate::cryptanalysis::mq_monica::monica_beats_moebius(n, m) {
        if let Some(roots) = crate::cryptanalysis::mq_monica::monica_find_all(forms, max_solutions)
        {
            return Some((roots, FesBackend::Monica));
        }
    }
    moebius_find_all(forms, max_solutions).map(|r| (r, FesBackend::Moebius))
}

/// First common zero via incremental Gray (early exit), else Möbius / Monica.
pub fn fes_find_one(forms: &[QuadraticForm]) -> Option<u64> {
    if forms.is_empty() {
        return Some(0);
    }
    if let Some(x) = gray_incremental_find_one(forms) {
        return Some(x);
    }
    // Gray refused (too large): try Monica, then Möbius.
    let n = forms[0].n;
    let m = forms.len();
    if n > 24 || crate::cryptanalysis::mq_monica::monica_beats_moebius(n, m) {
        if let Some(roots) = crate::cryptanalysis::mq_monica::monica_find_all(forms, 1) {
            return roots.into_iter().next();
        }
    }
    moebius_find_all(forms, 1)?.into_iter().next()
}

/// Every common zero via the auto-selected backend (empty on capacity refusal).
pub fn fes_find_all(forms: &[QuadraticForm], max_solutions: usize) -> Vec<u64> {
    fes_find_all_auto(forms, max_solutions)
        .map(|(r, _)| r)
        .unwrap_or_default()
}

/// Triangular index of the monomial `x_i x_j` with `i < j` (libfes `idxq`).
#[inline]
fn idxq(i: usize, j: usize) -> usize {
    debug_assert!(i < j);
    j * (j - 1) / 2 + i
}

/// Bitner–Ehrlich–Reingold focus pointers (`libfes-lite` / ALMASTY `ffs.h`).
#[derive(Clone, Debug)]
struct Ffs {
    focus: [i32; 34],
    stack: [i32; 33],
    sp: i32,
    k1: i32,
    k2: i32,
}

impl Ffs {
    fn reset(n: usize) -> Self {
        let mut focus = [0i32; 34];
        for j in 0..=32 {
            focus[j] = j as i32;
        }
        let mut stack = [0i32; 33];
        stack[0] = (n + 1) as i32;
        Self {
            focus,
            stack,
            sp: 1,
            k1: (n + 1) as i32,
            k2: -1,
        }
    }

    #[inline]
    fn step(&mut self) {
        let j = self.focus[0];
        self.focus[0] = 0;
        self.focus[j as usize] = self.focus[(j + 1) as usize];
        self.focus[(j + 1) as usize] = j + 1;
        self.k1 = j;
        self.sp -= j;
        self.k2 = self.stack[(self.sp - 1) as usize];
        self.stack[self.sp as usize] = j;
        self.sp += 1;
    }
}

/// Incremental Gray-code enumeration — **libfes-lite O(1) per step**.
///
/// Bouillaguet / ALMASTY / libfes-lite: after a one-time setup that pads two
/// fictive variables, each Gray step is
///
/// ```text
///     Fl[1+k1] ^= Fq[idxq(k1, k2)];
///     Fl[0]    ^= Fl[1+k1];
/// ```
///
/// so the hot loop no longer walks all `n` derivatives.  For `n ≥ 4` the
/// search uses a 16-way unrolled chunk (`L = 4`) matching
/// `feslite_generic_enum_1x32`.  Early exit on the first common zero still
/// applies.  Inspired by <https://github.com/cbouilla/libfes-lite>
/// (`generic_minimal.c`, `generic_1x32.c`) and ALMASTY `ffs.h`.
pub fn gray_incremental_find_all(
    forms: &[QuadraticForm],
    max_solutions: usize,
) -> Option<Vec<u64>> {
    if forms.is_empty() {
        return Some(vec![0]);
    }
    let n = forms[0].n;
    let m = forms.len();
    if n == 0 || n > 32 || m > 64 || forms.iter().any(|f| f.n != n) {
        return None;
    }

    // Stack tables: Fq through fictive n+1 is at most idxq(0,34)=561; Fl ≤ 34.
    let mut fq = [0u64; 561];
    let mut fl = [0u64; 34];

    for (eq, form) in forms.iter().enumerate() {
        let bit = 1u64 << eq;
        if form.constant {
            fl[0] ^= bit;
        }
        for i in 0..n {
            if form.linear[i] {
                fl[1 + i] ^= bit;
            }
            for j in 0..i {
                if form.quad[i][j] {
                    fq[idxq(j, i)] ^= bit;
                }
            }
        }
    }

    for i in 0..n {
        fq[idxq(i, n)] = 0;
    }
    fq[idxq(0, n + 1)] = 0;
    for i in 1..n {
        fq[idxq(i, n + 1)] = fq[idxq(i - 1, i)];
    }
    fq[idxq(n, n + 1)] = 0;

    let mut out = Vec::new();
    if n >= 4 {
        gray_ffs_unrolled_l4(&mut fq, &mut fl, n, max_solutions, &mut out);
    } else {
        gray_ffs_minimal(&mut fq, &mut fl, n, max_solutions, &mut out);
    }
    Some(out)
}

/// libfes `generic_minimal`: one FFS step per point.
fn gray_ffs_minimal(
    fq: &mut [u64; 561],
    fl: &mut [u64; 34],
    n: usize,
    max_solutions: usize,
    out: &mut Vec<u64>,
) {
    let mut ffs = Ffs::reset(n);
    ffs.step();
    let upto = (1u64 << n) - 1;
    let mut i = 0u64;
    loop {
        if fl[0] == 0 {
            out.push(i ^ (i >> 1));
            if out.len() >= max_solutions {
                return;
            }
        }
        let a = (1 + ffs.k1) as usize;
        let b = idxq(ffs.k1 as usize, ffs.k2 as usize);
        fl[a] ^= fq[b];
        fl[0] ^= fl[a];
        ffs.step();
        if i == upto {
            return;
        }
        i += 1;
    }
}

#[inline(always)]
fn step2(
    fq: &[u64; 561],
    fl: &mut [u64; 34],
    a: usize,
    b: usize,
    index: u64,
    out: &mut Vec<u64>,
    max_solutions: usize,
) -> bool {
    if fl[0] == 0 {
        out.push(index ^ (index >> 1));
        if out.len() >= max_solutions {
            return true;
        }
    }
    fl[a] ^= fq[b];
    fl[0] ^= fl[a];
    false
}

/// libfes `generic_1x32` / `UNROLLED_CHUNK`: 16 Gray steps per FFS advance.
fn gray_ffs_unrolled_l4(
    fq: &mut [u64; 561],
    fl: &mut [u64; 34],
    n: usize,
    max_solutions: usize,
    out: &mut Vec<u64>,
) {
    const L: usize = 4;
    let mut ffs = Ffs::reset(n - L);
    let mut k1 = ffs.k1 + L as i32;
    let mut k2;
    let iterations = 1u64 << (n - L);
    for j in 0..iterations {
        let alpha = idxq(0, k1 as usize);
        ffs.step();
        k1 = ffs.k1 + L as i32;
        k2 = ffs.k2 + L as i32;
        let beta = (1 + k1) as usize;
        let gamma = idxq(k1 as usize, k2 as usize);
        let base = j << L;
        // Hard-coded 16-step Gray chunk (libfes UNROLLED_CHUNK).
        if step2(fq, fl, 1, alpha, base, out, max_solutions)
            || step2(fq, fl, 2, alpha + 1, base + 1, out, max_solutions)
            || step2(fq, fl, 1, 0, base + 2, out, max_solutions)
            || step2(fq, fl, 3, alpha + 2, base + 3, out, max_solutions)
            || step2(fq, fl, 1, 1, base + 4, out, max_solutions)
            || step2(fq, fl, 2, 2, base + 5, out, max_solutions)
            || step2(fq, fl, 1, 0, base + 6, out, max_solutions)
            || step2(fq, fl, 4, alpha + 3, base + 7, out, max_solutions)
            || step2(fq, fl, 1, 3, base + 8, out, max_solutions)
            || step2(fq, fl, 2, 4, base + 9, out, max_solutions)
            || step2(fq, fl, 1, 0, base + 10, out, max_solutions)
            || step2(fq, fl, 3, 5, base + 11, out, max_solutions)
            || step2(fq, fl, 1, 1, base + 12, out, max_solutions)
            || step2(fq, fl, 2, 2, base + 13, out, max_solutions)
            || step2(fq, fl, 1, 0, base + 14, out, max_solutions)
            || step2(fq, fl, beta, gamma, base + 15, out, max_solutions)
        {
            return;
        }
    }
}

pub fn gray_incremental_find_one(forms: &[QuadraticForm]) -> Option<u64> {
    gray_incremental_find_all(forms, 1)?.into_iter().next()
}

/// Previous O(n)-per-step Gray update — kept for regression / speed comparison.
pub fn gray_on_step_find_all(forms: &[QuadraticForm], max_solutions: usize) -> Option<Vec<u64>> {
    if forms.is_empty() {
        return Some(vec![0]);
    }
    let n = forms[0].n;
    let m = forms.len();
    if n > 28 || m > 64 || forms.iter().any(|f| f.n != n) {
        return None;
    }
    let mut deriv = vec![0u64; n];
    let mut quad_mask = vec![vec![0u64; n]; n];
    let mut value = 0u64;
    for (eq, form) in forms.iter().enumerate() {
        let bit = 1u64 << eq;
        if form.constant {
            value ^= bit;
        }
        for i in 0..n {
            if form.linear[i] {
                deriv[i] ^= bit;
            }
            for j in 0..i {
                if form.quad[i][j] {
                    quad_mask[i][j] ^= bit;
                    quad_mask[j][i] ^= bit;
                }
            }
        }
    }
    let mut out = Vec::new();
    let mut point = 0u64;
    let limit = 1u64 << n;
    for step in 0..limit {
        if value == 0 {
            out.push(point);
            if out.len() >= max_solutions {
                break;
            }
        }
        let flip = (step + 1).trailing_zeros() as usize;
        if flip >= n {
            break;
        }
        value ^= deriv[flip];
        for j in 0..n {
            if j != flip {
                deriv[j] ^= quad_mask[flip][j];
            }
        }
        point ^= 1u64 << flip;
    }
    Some(out)
}

/// Naive Gray-code re-evaluation — retained as an independent check on
/// the Möbius path (ALMASTY monica / libfes enumeration shape).
pub fn gray_find_all(forms: &[QuadraticForm], max_solutions: usize) -> Vec<u64> {
    let mut out = Vec::new();
    if forms.is_empty() {
        return vec![0];
    }
    let n = forms[0].n;
    if n > 24 || forms.iter().any(|f| f.n != n) {
        return out;
    }
    let limit = 1u64 << n;
    let mut point = 0u64;
    for step in 0..limit {
        if forms.iter().all(|f| !f.eval(point)) {
            out.push(point);
            if out.len() >= max_solutions {
                break;
            }
        }
        let flip = (step + 1).trailing_zeros() as u64;
        if flip < n as u64 {
            point ^= 1u64 << flip;
        }
    }
    out
}

/// Solve a quadratic (`m = 2`) Semaev decomposition by Möbius FES.
///
/// Returns the same shape as
/// [`crate::cryptanalysis::koblitz_index_calculus::sat_decompose`].
/// Cubic chained systems (`m ≥ 3`) are reported as exhausted.
pub fn mq_fes_decompose(
    kc: &crate::cryptanalysis::koblitz_index_calculus::KoblitzCurve,
    fb: &crate::cryptanalysis::koblitz_index_calculus::FrobeniusFactorBase,
    index_of: &std::collections::HashMap<(num_bigint::BigUint, num_bigint::BigUint), usize>,
    st: &crate::cryptanalysis::koblitz_groebner::FieldStructure,
    target: &crate::binary_ecc::BinaryPoint,
    m: usize,
) -> (
    Option<Vec<usize>>,
    crate::cryptanalysis::koblitz_index_calculus::SatDecompositionStats,
) {
    use crate::binary_ecc::BinaryPoint;
    use crate::cryptanalysis::koblitz_index_calculus::{lift_candidate, SatDecompositionStats};

    let mut stats = SatDecompositionStats::default();
    if m != 2 {
        stats.exhausted = true;
        return (None, stats);
    }
    let x_r = match target {
        BinaryPoint::Affine { x, .. } => x.clone(),
        BinaryPoint::Infinity => return (None, stats),
    };
    let sys = match crate::cryptanalysis::polynomial_reuse::build_decomposition_system_reusing(
        &fb.subspace_basis,
        &x_r,
        &kc.curve.b,
        m,
        st,
    ) {
        Some(sys) => sys,
        None => {
            stats.exhausted = true;
            return (None, stats);
        }
    };
    let forms: Option<Vec<_>> = sys.equations.iter().map(QuadraticForm::from_poly).collect();
    let forms = match forms {
        Some(forms) => forms,
        None => {
            stats.exhausted = true;
            return (None, stats);
        }
    };
    stats.solver_calls = 1;
    // Prefer incremental Gray so a successful lift can stop before a full
    // Möbius transform; fall back to the auto all-roots backend otherwise.
    let roots = if let Some(roots) = gray_incremental_find_all(&forms, 64) {
        roots
    } else {
        match fes_find_all_auto(&forms, 64) {
            Some((roots, _)) => roots,
            None => {
                stats.exhausted = true;
                return (None, stats);
            }
        }
    };
    if roots.is_empty() {
        stats.refuted = true;
        return (None, stats);
    }
    for root in roots {
        stats.models += 1;
        if !sys.equations.iter().all(|e| e.eval(root) == 0) {
            stats.spurious += 1;
            continue;
        }
        let xs: Vec<_> = (0..m)
            .map(|i| sys.summand_x(&fb.subspace_basis, root, i, kc.n))
            .collect();
        if let Some(idxs) = lift_candidate(kc, fb, index_of, &xs, target) {
            return (Some(idxs), stats);
        }
    }
    stats.exhausted = true;
    (None, stats)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::wdsat_oracle::AnfRow;

    #[test]
    fn finds_the_unique_zero_of_a_tiny_system() {
        // x0 + x1 = 0 and x0 = 1  →  only (1,1).
        let rows = [
            AnfRow {
                monomials: vec![vec![0], vec![1]],
                constant: false,
            },
            AnfRow {
                monomials: vec![vec![0]],
                constant: true,
            },
        ];
        let forms: Vec<_> = rows
            .iter()
            .map(|r| QuadraticForm::from_anf_row(r, 2).unwrap())
            .collect();
        assert_eq!(fes_find_one(&forms), Some(0b11));
    }

    #[test]
    fn moebius_agrees_with_gray_on_random_quadratics() {
        let rows = [
            AnfRow {
                monomials: vec![vec![0, 1], vec![2], vec![4]],
                constant: true,
            },
            AnfRow {
                monomials: vec![vec![1, 3], vec![0, 4], vec![2, 3]],
                constant: false,
            },
        ];
        let forms: Vec<_> = rows
            .iter()
            .map(|r| QuadraticForm::from_anf_row(r, 5).unwrap())
            .collect();
        let mut a = moebius_find_all(&forms, 1024).unwrap();
        let mut b = gray_find_all(&forms, 1024);
        a.sort_unstable();
        b.sort_unstable();
        assert_eq!(a, b);
    }

    #[test]
    fn rejects_a_cubic_row() {
        let row = AnfRow {
            monomials: vec![vec![0, 1, 2]],
            constant: false,
        };
        assert!(QuadraticForm::from_anf_row(&row, 3).is_none());
    }

    #[test]
    fn mq_fes_agrees_with_native_sat_on_prime_degree() {
        use crate::binary_ecc::BinaryPoint;
        use crate::cryptanalysis::koblitz_groebner::FieldStructure;
        use crate::cryptanalysis::koblitz_index_calculus::{
            build_frobenius_factor_base, point_key, sat_decompose, KoblitzCurve,
        };
        use std::collections::HashMap;

        let kc = KoblitzCurve::new(1, 7).expect("K_1/F_2^7");
        let fb = build_frobenius_factor_base(&kc, 0).expect("factor base");
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let index_of: HashMap<_, _> = fb
            .points
            .iter()
            .enumerate()
            .map(|(i, p)| (point_key(p), i))
            .collect();
        let mut affine = fb.points.iter().enumerate().filter_map(|(i, p)| match p {
            BinaryPoint::Affine { .. } => Some(i),
            BinaryPoint::Infinity => None,
        });
        let i = affine.next().unwrap();
        let j = affine.next().unwrap();
        let target = kc.add(&fb.points[i], &fb.points[j]);

        let (native, _) = sat_decompose(&kc, &fb, &index_of, &st, &target, 2, 8, Some(2));
        let (fes, stats) = mq_fes_decompose(&kc, &fb, &index_of, &st, &target, 2);
        assert!(native.is_some(), "native SAT missed planted");
        assert!(fes.is_some(), "mq-fes missed planted: {stats:?}");
        let mut a = native.unwrap();
        let mut b = fes.unwrap();
        a.sort_unstable();
        b.sort_unstable();
        assert_eq!(a, b);
    }

    #[test]
    fn gray_incremental_agrees_with_moebius() {
        let rows = [
            AnfRow {
                monomials: vec![vec![0, 1], vec![2], vec![4]],
                constant: true,
            },
            AnfRow {
                monomials: vec![vec![1, 3], vec![0, 4], vec![2, 3]],
                constant: false,
            },
            AnfRow {
                monomials: vec![vec![0, 2], vec![1], vec![3, 4]],
                constant: true,
            },
        ];
        let forms: Vec<_> = rows
            .iter()
            .map(|r| QuadraticForm::from_anf_row(r, 5).unwrap())
            .collect();
        let mut a = gray_incremental_find_all(&forms, 1024).unwrap();
        let mut b = moebius_find_all(&forms, 1024).unwrap();
        let mut c = gray_on_step_find_all(&forms, 1024).unwrap();
        a.sort_unstable();
        b.sort_unstable();
        c.sort_unstable();
        assert_eq!(a, b);
        assert_eq!(a, c);
    }

    #[test]
    fn gray_ffs_beats_on_step_full_enum_wall() {
        // Full enumeration (no early exit): O(1)/step FFS vs O(n)/step update.
        let n = 18usize;
        let m = 18usize;
        let mut forms = Vec::with_capacity(m);
        for eq in 0..m {
            let mut linear = vec![false; n];
            let mut quad = (0..n).map(|i| vec![false; i]).collect::<Vec<_>>();
            for i in 0..n {
                linear[i] = ((eq * 19 + i * 5) % 3) == 0;
                for j in 0..i {
                    quad[i][j] = ((eq * 11 + i * 7 + j * 3) % 5) == 0;
                }
            }
            forms.push(QuadraticForm {
                n,
                constant: eq % 2 == 0,
                linear,
                quad,
            });
        }
        let t0 = std::time::Instant::now();
        let mut ffs = gray_incremental_find_all(&forms, usize::MAX).expect("ffs");
        let ffs_ns = t0.elapsed().as_nanos();
        let t1 = std::time::Instant::now();
        let mut on = gray_on_step_find_all(&forms, usize::MAX).expect("on");
        let on_ns = t1.elapsed().as_nanos();
        ffs.sort_unstable();
        on.sort_unstable();
        assert_eq!(ffs, on);
        let ratio = on_ns as f64 / ffs_ns.max(1) as f64;
        eprintln!(
            "gray_ffs_vs_on_step n={n} full_enum: ffs={ffs_ns}ns on_step={on_ns}ns ratio={ratio:.2} sols={}",
            ffs.len()
        );
        assert!(
            ratio >= 1.5,
            "expected FFS Gray ≥1.5× O(n)-step Gray, got {ratio:.3}"
        );
    }

    #[test]
    fn gray_early_exit_beats_moebius_find_one_wall() {
        // Plant a solution early in Gray order so early exit pays, while
        // Möbius still pays the full n·2^n transform.  n=18 keeps both fast.
        let n = 18usize;
        let m = 18usize;
        let gray_index: u64 = 2_000; // well below 2^18
        let planted = gray_index ^ (gray_index >> 1);
        let mut forms = Vec::with_capacity(m);
        for eq in 0..m {
            let mut linear = vec![false; n];
            let mut quad = (0..n).map(|i| vec![false; i]).collect::<Vec<_>>();
            for i in 0..n {
                linear[i] = ((eq * 19 + i * 5) % 3) == 0;
                for j in 0..i {
                    quad[i][j] = ((eq * 11 + i * 7 + j * 3) % 5) == 0;
                }
            }
            let probe = QuadraticForm {
                n,
                constant: false,
                linear: linear.clone(),
                quad: quad.clone(),
            };
            // Adjust constant so eval(planted) == false.
            let constant = probe.eval(planted);
            forms.push(QuadraticForm {
                n,
                constant,
                linear,
                quad,
            });
        }
        assert!(forms.iter().all(|f| !f.eval(planted)));

        let t0 = std::time::Instant::now();
        let g = gray_incremental_find_one(&forms).expect("gray");
        let gray_ns = t0.elapsed().as_nanos();
        let t1 = std::time::Instant::now();
        let mbi = moebius_find_all(&forms, 1).unwrap().into_iter().next();
        let moebius_ns = t1.elapsed().as_nanos();
        assert!(forms.iter().all(|f| !f.eval(g)));
        assert!(mbi.is_some() && forms.iter().all(|f| !f.eval(mbi.unwrap())));
        // Multiple roots are expected; Gray returns the first in Gray order,
        // Möbius the first in binary order — only require both be zeros.
        let ratio = moebius_ns as f64 / gray_ns.max(1) as f64;
        eprintln!(
            "gray_early_vs_moebius n={n}: gray={gray_ns}ns moebius={moebius_ns}ns ratio={ratio:.2} gray_sol={g:#x} moebius_sol={:#x}",
            mbi.unwrap()
        );
        assert!(
            ratio >= 1.5,
            "expected incremental Gray find_one ≥1.5× Möbius, got {ratio:.3}"
        );
    }

    #[test]
    fn monica_extends_past_moebius_cap() {
        // n=26 exceeds Möbius' n≤24 table; Monica must still run.
        let n = 26usize;
        let m = 64usize;
        assert!(n > 24);
        let mut forms = Vec::with_capacity(m);
        for eq in 0..m {
            let constant = eq % 5 == 0;
            let mut linear = vec![false; n];
            let mut quad = (0..n).map(|i| vec![false; i]).collect::<Vec<_>>();
            for i in 0..n {
                linear[i] = ((eq * 3 + i) % 4) == 0;
                for j in 0..i {
                    quad[i][j] = ((eq + i + j) % 11) == 0;
                }
            }
            forms.push(QuadraticForm {
                n,
                constant,
                linear,
                quad,
            });
        }
        assert!(moebius_find_all(&forms, 1).is_none());
        let roots = crate::cryptanalysis::mq_monica::monica_find_all(&forms, 4);
        assert!(roots.is_some(), "Monica should accept n=26");
        for x in roots.unwrap() {
            assert!(forms.iter().all(|f| !f.eval(x)), "bad Monica root {x:#x}");
        }
    }
}
