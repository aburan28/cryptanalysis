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

    let (mut fq, mut fl) = gray_tables(forms, n);

    let mut out = Vec::new();
    if n >= 4 {
        gray_ffs_unrolled_l4(&mut fq, &mut fl, n, max_solutions, &mut out);
    } else {
        gray_ffs_minimal(&mut fq, &mut fl, n, max_solutions, &mut out);
    }
    Some(out)
}

/// The Gray-code derivative tables for `forms` over `n` variables, one
/// equation per bit: `fq` the second derivatives (the quadratic
/// coefficients, plus the fictive entries the focus pointers read), `fl`
/// the first derivatives with `f(0)` at `fl[0]`.
fn gray_tables(forms: &[QuadraticForm], n: usize) -> ([u64; 561], [u64; 34]) {
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
    (fq, fl)
}

/// `form` with its last `k` variables fixed to the bits of `lane` (bit
/// `j` of `lane` is variable `n − k + j`): a quadratic form in the first
/// `n − k` variables.  Fixing a variable folds its quadratic terms into
/// the linear ones and its linear term into the constant; the quadratic
/// terms among the free variables do not change, which is what lets
/// every lane share one second-derivative table.
fn specialise(form: &QuadraticForm, k: usize, lane: usize) -> QuadraticForm {
    let n = form.n;
    let free = n - k;
    let fixed = |j: usize| (lane >> j) & 1 == 1;
    let mut constant = form.constant;
    for j in 0..k {
        if fixed(j) && form.linear[free + j] {
            constant = !constant;
        }
        for jj in 0..j {
            if fixed(j) && fixed(jj) && form.quad[free + j][free + jj] {
                constant = !constant;
            }
        }
    }
    let mut linear = form.linear[..free].to_vec();
    for (i, l) in linear.iter_mut().enumerate() {
        for j in 0..k {
            if fixed(j) && form.quad[free + j][i] {
                *l = !*l;
            }
        }
    }
    QuadraticForm {
        n: free,
        constant,
        linear,
        quad: (0..free).map(|i| form.quad[i][..i].to_vec()).collect(),
    }
}

/// How many 32-bit lanes [`gray_find_all_wide`] runs on this host: 16
/// with AVX-512, 8 with AVX2, none otherwise.
pub fn wide_lanes() -> Option<usize> {
    #[cfg(target_arch = "x86_64")]
    {
        #[cfg(suite_avx512)]
        if std::is_x86_feature_detected!("avx512f") {
            return Some(16);
        }
        if std::is_x86_feature_detected!("avx2") {
            return Some(8);
        }
    }
    None
}

/// **Fast exhaustive search, one Gray-code walk over several sub-cubes
/// at once** — the vector form of libfes-lite's enumeration.  The last
/// `k = log₂(lanes)` variables are fixed differently in each 32-bit lane
/// of a vector register and the remaining `n − k` are walked in Gray
/// order, so one pair of vector XORs advances every lane: `2^n` points
/// in `2^{n−k}` steps.  The second-derivative table is shared (fixing a
/// variable leaves the quadratic part of the free ones alone) and
/// broadcast on use; the first-derivative table is per lane.
///
/// Needs at most 32 equations (one per lane bit), `n − k ≥ 4` for the
/// unrolled chunk and `n − k ≤ 32`.  Returns `None` when the host has
/// neither AVX-512 nor AVX2 or the system does not fit, and otherwise the
/// solutions (bit `i` = `x_i`, in no particular order) and the lane count.
pub fn gray_find_all_wide(
    forms: &[QuadraticForm],
    max_solutions: usize,
) -> Option<(Vec<u64>, usize)> {
    let lanes = wide_lanes()?;
    let n = forms.first()?.n;
    let k = lanes.trailing_zeros() as usize;
    if forms.len() > 32 || forms.iter().any(|f| f.n != n) || n < k + 4 || n - k > 32 {
        return None;
    }
    let free = n - k;
    let mut fq_shared = [0u32; 561];
    let mut fl_lanes = [[0u32; 16]; 34];
    for lane in 0..lanes {
        let spec: Vec<QuadraticForm> = forms.iter().map(|f| specialise(f, k, lane)).collect();
        let (fq, fl) = gray_tables(&spec, free);
        for (t, v) in fl.iter().enumerate() {
            fl_lanes[t][lane] = *v as u32;
        }
        if lane == 0 {
            for (t, v) in fq.iter().enumerate() {
                fq_shared[t] = *v as u32;
            }
        } else {
            debug_assert!(fq.iter().zip(&fq_shared).all(|(a, b)| *a as u32 == *b));
        }
    }
    let mut out = Vec::new();
    #[cfg(target_arch = "x86_64")]
    unsafe {
        // SAFETY: `wide_lanes` confirmed the feature each kernel is
        // compiled for before either is called.
        #[cfg(suite_avx512)]
        if lanes == 16 {
            wide::enumerate_avx512(&fq_shared, &fl_lanes, free, max_solutions, &mut out);
            return Some((out, lanes));
        }
        wide::enumerate_avx2(&fq_shared, &fl_lanes, free, max_solutions, &mut out);
    }
    Some((out, lanes))
}

/// The vector kernels: libfes-lite's unrolled 16-step chunk
/// ([`gray_ffs_unrolled_l4`]) with the first-derivative table held as
/// vectors of 32-bit lanes and the second derivatives broadcast.
#[cfg(target_arch = "x86_64")]
mod wide {
    use super::{idxq, Ffs};
    use std::arch::x86_64::*;

    /// Bit `ℓ` set iff lane `ℓ` of the vector is zero: a solution there.
    #[cfg(suite_avx512)]
    macro_rules! zero_lanes_512 {
        ($v:expr) => {
            _mm512_cmpeq_epi32_mask($v, _mm512_setzero_si512()) as u32
        };
    }
    macro_rules! zero_lanes_256 {
        ($v:expr) => {
            _mm256_movemask_ps(_mm256_castsi256_ps(_mm256_cmpeq_epi32(
                $v,
                _mm256_setzero_si256(),
            ))) as u32
        };
    }

    macro_rules! wide_kernel {
        ($(#[$attr:meta])* $name:ident, $feature:literal, $vec:ty, $load:ident, $set1:ident, $xor:ident, $zero_lanes:ident) => {
            $(#[$attr])*
            #[target_feature(enable = $feature)]
            pub(super) unsafe fn $name(
                fq: &[u32; 561],
                fl_lanes: &[[u32; 16]; 34],
                n: usize,
                max_solutions: usize,
                out: &mut Vec<u64>,
            ) {
                const L: usize = 4;
                let mut fl: [$vec; 34] = [std::mem::zeroed(); 34];
                for (t, lanes) in fl_lanes.iter().enumerate() {
                    fl[t] = $load(lanes.as_ptr() as *const _);
                }
                // `f(x)` for the current point, kept out of the array so it
                // stays in a register.
                let mut f0 = fl[0];
                macro_rules! step {
                    ($a:expr, $b:expr, $index:expr) => {{
                        let mask: u32 = $zero_lanes!(f0);
                        if mask != 0 {
                            let index: u64 = $index;
                            let gray = index ^ (index >> 1);
                            let mut bits = mask;
                            while bits != 0 {
                                let lane = bits.trailing_zeros() as u64;
                                out.push(gray | (lane << n));
                                bits &= bits - 1;
                            }
                            if out.len() >= max_solutions {
                                return;
                            }
                        }
                        let a: usize = $a;
                        fl[a] = $xor(fl[a], $set1(fq[$b] as i32));
                        f0 = $xor(f0, fl[a]);
                    }};
                }
                let mut ffs = Ffs::reset(n - L);
                let mut k1 = ffs.k1 + L as i32;
                let iterations = 1u64 << (n - L);
                for j in 0..iterations {
                    let alpha = idxq(0, k1 as usize);
                    ffs.step();
                    k1 = ffs.k1 + L as i32;
                    let k2 = ffs.k2 + L as i32;
                    let beta = (1 + k1) as usize;
                    let gamma = idxq(k1 as usize, k2 as usize);
                    let base = j << L;
                    step!(1, alpha, base);
                    step!(2, alpha + 1, base + 1);
                    step!(1, 0, base + 2);
                    step!(3, alpha + 2, base + 3);
                    step!(1, 1, base + 4);
                    step!(2, 2, base + 5);
                    step!(1, 0, base + 6);
                    step!(4, alpha + 3, base + 7);
                    step!(1, 3, base + 8);
                    step!(2, 4, base + 9);
                    step!(1, 0, base + 10);
                    step!(3, 5, base + 11);
                    step!(1, 1, base + 12);
                    step!(2, 2, base + 13);
                    step!(1, 0, base + 14);
                    step!(beta, gamma, base + 15);
                }
            }
        };
    }

    // AVX-512 target features are stable from 1.89 (see `build.rs`).
    #[cfg(suite_avx512)]
    wide_kernel!(
        #[clippy::msrv = "1.89"]
        enumerate_avx512,
        "avx512f",
        __m512i,
        _mm512_loadu_si512,
        _mm512_set1_epi32,
        _mm512_xor_si512,
        zero_lanes_512
    );

    wide_kernel!(
        enumerate_avx2,
        "avx2",
        __m256i,
        _mm256_loadu_si256,
        _mm256_set1_epi32,
        _mm256_xor_si256,
        zero_lanes_256
    );
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

    /// **The vector search finds exactly what the scalar one does.**
    /// Random quadratic systems with a planted root — and, with few
    /// equations, many roots of their own in every lane — from the
    /// smallest size the unrolled chunk takes up to the 32 equations a
    /// lane holds.
    #[test]
    fn the_wide_search_finds_exactly_what_the_scalar_one_does() {
        use rand::{Rng, SeedableRng};
        let Some(lanes) = wide_lanes() else {
            eprintln!("no AVX2 or AVX-512 on this host; the wide search is not exercised");
            return;
        };
        let k = lanes.trailing_zeros() as usize;
        let mut rng = rand::rngs::StdRng::seed_from_u64(20260923);
        for trial in 0..48usize {
            let n = k + 4 + trial % 14;
            let m = 1 + (trial * 7) % 32;
            let mut forms: Vec<QuadraticForm> = (0..m)
                .map(|_| QuadraticForm {
                    n,
                    constant: rng.gen(),
                    linear: (0..n).map(|_| rng.gen()).collect(),
                    quad: (0..n)
                        .map(|i| (0..i).map(|_| rng.gen_bool(0.4)).collect())
                        .collect(),
                })
                .collect();
            // Plant a root: shift each form's constant so it vanishes there.
            // With few equations the system has many more roots of its own.
            let planted: u64 = rng.gen::<u64>() & ((1u64 << n) - 1);
            for f in &mut forms {
                if f.eval(planted) {
                    f.constant = !f.constant;
                }
            }
            let mut scalar = gray_incremental_find_all(&forms, usize::MAX).unwrap();
            let (mut wide, used) =
                gray_find_all_wide(&forms, usize::MAX).expect("fits the wide search");
            assert_eq!(used, lanes);
            scalar.sort_unstable();
            wide.sort_unstable();
            assert!(
                scalar.contains(&planted),
                "trial {trial}: the scalar search lost the planted root"
            );
            assert_eq!(wide, scalar, "trial {trial} (n = {n}, m = {m})");
        }
        // Too many equations for a 32-bit lane, or too few variables for
        // the unrolled chunk: declined, not answered wrongly.
        let wide_form = |n: usize| QuadraticForm {
            n,
            constant: false,
            linear: vec![false; n],
            quad: (0..n).map(|i| vec![false; i]).collect(),
        };
        assert!(gray_find_all_wide(&vec![wide_form(12); 33], 1).is_none());
        assert!(gray_find_all_wide(&[wide_form(k + 3)], 1).is_none());
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
