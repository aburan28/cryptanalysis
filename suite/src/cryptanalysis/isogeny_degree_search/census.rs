//! # Exhaustive isogeny-class census over `F_{2^n}`.
//!
//! Tate's theorem makes "isogenous over `F_q`" the same relation as
//! "equal number of points", so enumerating an isogeny class is
//! enumerating curves by point count.  This module does that
//! **exhaustively**: every ordinary binary curve over `F_{2^n}`, both
//! twists, assigned to its class.
//!
//! ## Counting the curves
//!
//! Over `F_{2^n}` the ordinary curves are
//! `E_{a,b} : y² + xy = x³ + a x² + b` with `b ≠ 0`, and
//! `E_{a,b} ≅ E_{a',b'}` iff `b = b'` and `Tr(a) = Tr(a')` (take
//! `y ↦ y + sx` with `s² + s = a + a'`).  So the `F_{2^n}`-isomorphism
//! classes are in bijection with
//!
//! ```text
//!     { (b, ε) : b ∈ F_{2^n}^*, ε ∈ {0, 1} },        2·(2^n − 1) of them,
//! ```
//!
//! `ε = Tr(a)` selecting the curve or its quadratic twist, and
//! `j(E_{a,b}) = 1/b` depending on `b` alone.
//!
//! ## Counting the points, all at once
//!
//! Dividing the curve equation by `x²` turns the `x ≠ 0` fibres into the
//! Artin–Schreier condition `Tr(x + a + b/x²) = 0`, and `Tr(v²) = Tr(v)`
//! rewrites `Tr(b/x²)` as `Tr(c/x)` with `c = √b`.  With
//!
//! ```text
//!     K(c) := Σ_{x ≠ 0} (−1)^{Tr(x + c/x)}        (a Kloosterman sum)
//! ```
//!
//! the count is exactly
//!
//! ```text
//!     #E_{a,b}(F_{2^n}) = 2^n + 1 + (−1)^{Tr(a)} · K(√b),
//!     so    t = −(−1)^{Tr(a)} · K(√b).
//! ```
//!
//! Computing `K(c)` for one `c` costs `2^n` trace evaluations, so a
//! census by that route is `Θ(4^n)` and dies at `n ≈ 13`.  But
//! substituting `u = 1/x` turns `K` into an additive-character transform,
//!
//! ```text
//!     K(c) = Σ_{u ≠ 0} (−1)^{Tr(1/u)} · (−1)^{Tr(cu)} = ĝ(c),
//!     g(u) := (−1)^{Tr(1/u)},  g(0) := 0,
//! ```
//!
//! and `Tr(cu)` is an `F_2`-bilinear pairing.  Index `u` by its
//! coordinates in the polynomial basis `1, z, …, z^{n−1}` and `c` by its
//! coordinates in the **trace-dual** basis; the pairing becomes the plain
//! dot product, so one fast Walsh–Hadamard transform yields `K(c)` for
//! **every** `c` in `Θ(n · 2^n)`.  That is [`kloosterman_all`], and it is
//! what makes an exhaustive census reach `n = 17` and beyond instead of
//! `n = 13`.
//!
//! [`kloosterman_direct`] keeps the `Θ(2^n)`-per-`c` definition as the
//! reference oracle; the two are cross-checked against each other and
//! against the Koblitz trace recurrence in this module's tests, which is
//! the repository's standing rule for a new oracle that replaces an old
//! one.

use crate::binary_ecc::{F2mElement, IrreduciblePoly};
use std::collections::BTreeMap;

/// Largest `n` the census will attempt: it allocates `Θ(2^n)` `i64`s
/// for the transform plus an inverse table, so `n = 22` is ~64 MiB and
/// a sensible ceiling for a study library.
pub const MAX_CENSUS_N: u32 = 22;

// ── Field bookkeeping ───────────────────────────────────────────────

/// The low `u64` of a field element's bit pattern (`n ≤ 22` here, so
/// this is the whole element).
pub fn mask_of(e: &F2mElement) -> u64 {
    e.raw_bits().first().copied().unwrap_or(0)
}

/// Rebuild a field element from its polynomial-basis bitmask.
pub fn elem_of(mask: u64, n: u32) -> F2mElement {
    let positions: Vec<u32> = (0..n).filter(|k| (mask >> k) & 1 == 1).collect();
    F2mElement::from_bit_positions(&positions, n)
}

/// `Tr_{F_{2^n}/F_2}(z^k)` for `k = 0 .. 2n−2`, the data the trace form
/// and its dual basis are built from.
fn trace_of_powers(n: u32, irr: &IrreduciblePoly) -> Vec<u8> {
    let mut out = Vec::with_capacity(2 * n as usize - 1);
    for k in 0..(2 * n - 1) {
        let mut e = F2mElement::one(n);
        let z = F2mElement::z(n);
        for _ in 0..k {
            e = e.mul(&z, irr);
        }
        let mut acc = F2mElement::zero(n);
        let mut p = e;
        for _ in 0..n {
            acc = acc.add(&p);
            p = p.square(irr);
        }
        let w = mask_of(&acc);
        debug_assert!(w == 0 || w == 1, "trace must land in F_2");
        out.push((w & 1) as u8);
    }
    out
}

/// `Tr(u)` for every `u`, as a bit per field element.
pub fn trace_table(n: u32, irr: &IrreduciblePoly) -> Vec<u8> {
    let tau = trace_of_powers(n, irr);
    let size = 1usize << n;
    let mut tr = vec![0u8; size];
    for (u, slot) in tr.iter_mut().enumerate().take(size) {
        let mut acc = 0u8;
        let mut m = u as u64;
        while m != 0 {
            let k = m.trailing_zeros() as usize;
            m &= m - 1;
            acc ^= tau[k];
        }
        *slot = acc;
    }
    tr
}

/// The basis `d_0, …, d_{n−1}` dual to `1, z, …, z^{n−1}` under the
/// trace form: `Tr(z^i · d_j) = δ_{ij}`.
///
/// With `M[i][k] = Tr(z^{i+k})` (a Hankel matrix, invertible because the
/// trace form is nondegenerate) the dual basis is read off `M^{-1}`:
/// `d_j = Σ_k M^{-1}[j][k] · z^k`.
fn dual_basis_masks(n: u32, irr: &IrreduciblePoly) -> Vec<u64> {
    let tau = trace_of_powers(n, irr);
    let nn = n as usize;
    // Augmented [M | I] over F_2, rows packed as u128 (n ≤ 22 ⇒ fits).
    let mut rows: Vec<u128> = (0..nn)
        .map(|i| {
            let mut r = 0u128;
            for k in 0..nn {
                if tau[i + k] == 1 {
                    r |= 1u128 << k;
                }
            }
            r | (1u128 << (nn + i))
        })
        .collect();

    let mut pivot_of_col = vec![usize::MAX; nn];
    let mut row = 0usize;
    for (col, pivot) in pivot_of_col.iter_mut().enumerate() {
        let Some(p) = (row..nn).find(|&r| (rows[r] >> col) & 1 == 1) else {
            continue;
        };
        rows.swap(row, p);
        for r in 0..nn {
            if r != row && (rows[r] >> col) & 1 == 1 {
                rows[r] ^= rows[row];
            }
        }
        *pivot = row;
        row += 1;
    }
    assert_eq!(row, nn, "trace form is nondegenerate; M must be invertible");

    // Row `pivot_of_col[j]` of the reduced system carries M^{-1}'s row j
    // in its right half.
    (0..nn)
        .map(|j| {
            let r = rows[pivot_of_col[j]];
            ((r >> nn) & ((1u128 << nn) - 1)) as u64
        })
        .collect()
}

// ── Kloosterman sums ────────────────────────────────────────────────

/// `K(c) = Σ_{x ≠ 0} (−1)^{Tr(x + c/x)}`, straight from the definition.
///
/// `Θ(2^n)` field inversions.  This is the reference oracle
/// [`kloosterman_all`] is checked against.
pub fn kloosterman_direct(n: u32, irr: &IrreduciblePoly, c: &F2mElement) -> i64 {
    let tr = trace_table(n, irr);
    let mut acc = 0i64;
    for x in 1..(1u64 << n) {
        let xe = elem_of(x, n);
        let inv = xe.flt_inverse(irr).expect("x ≠ 0");
        let term = xe.add(&c.mul(&inv, irr));
        acc += if tr[mask_of(&term) as usize] == 0 {
            1
        } else {
            -1
        };
    }
    acc
}

/// **`K(√b)` for every `b ∈ F_{2^n}`, in `Θ(n · 2^n)`**, indexed by the
/// polynomial-basis bitmask of `b`.
///
/// Entry `0` is `K(0) = −1`, which corresponds to the excluded singular
/// `b = 0`; it is retained so the vector can be indexed by a raw mask.
///
/// The returned vector is the whole census: every ordinary binary curve
/// over `F_{2^n}` has its trace determined by one entry and the parity
/// `Tr(a)`, via [`trace_of_curve`].
pub fn kloosterman_all(n: u32, irr: &IrreduciblePoly) -> Vec<i64> {
    assert!(
        (1..=MAX_CENSUS_N).contains(&n),
        "census supports 1 ≤ n ≤ {MAX_CENSUS_N}"
    );
    let size = 1usize << n;
    let tr = trace_table(n, irr);

    // g(u) = (−1)^{Tr(1/u)}, indexed by u's polynomial-basis mask.
    let mut g = vec![0i64; size];
    for (u, slot) in g.iter_mut().enumerate().skip(1) {
        let inv = elem_of(u as u64, n).flt_inverse(irr).expect("u ≠ 0");
        *slot = if tr[mask_of(&inv) as usize] == 0 {
            1
        } else {
            -1
        };
    }

    // Fast Walsh–Hadamard transform: ĝ[Γ] = Σ_U g[U]·(−1)^{⟨Γ,U⟩}.
    let mut half = 1usize;
    while half < size {
        let mut i = 0usize;
        while i < size {
            for j in i..i + half {
                let (a, b) = (g[j], g[j + half]);
                g[j] = a + b;
                g[j + half] = a - b;
            }
            i += half << 1;
        }
        half <<= 1;
    }

    // ĝ is indexed by the *dual*-basis coordinates of c.  Re-index to c,
    // then to b = c².
    let dual = dual_basis_masks(n, irr);
    let mut out = vec![0i64; size];
    for (gamma, &k) in g.iter().enumerate() {
        let mut c = 0u64;
        let mut m = gamma as u64;
        while m != 0 {
            let i = m.trailing_zeros() as usize;
            m &= m - 1;
            c ^= dual[i];
        }
        let b = mask_of(&elem_of(c, n).square(irr));
        out[b as usize] = k;
    }
    out
}

// ── Traces, classes, census ─────────────────────────────────────────

/// Trace of Frobenius of `E_{a,b}/F_{2^n}` from the Kloosterman table:
/// `t = −(−1)^{Tr(a)} · K(√b)`.
///
/// `a_trace` is `Tr(a) ∈ {0, 1}`, which is all the curve's isomorphism
/// class remembers of `a`.
pub fn trace_of_curve(kloosterman: &[i64], b: u64, a_trace: u8) -> i64 {
    let k = kloosterman[b as usize];
    if a_trace == 0 {
        -k
    } else {
        k
    }
}

/// One `F_{2^n}`-isomorphism class of ordinary binary curves.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct CurveId {
    /// `b`, as a polynomial-basis bitmask.  `j = 1/b`.
    pub b: u64,
    /// `Tr(a) ∈ {0, 1}`: the curve (`0`) or its quadratic twist (`1`)
    /// relative to the `a = 0` model.
    pub a_trace: u8,
}

/// The exhaustive census of ordinary binary curves over `F_{2^n}`,
/// grouped into isogeny classes by trace.
#[derive(Clone, Debug)]
pub struct IsogenyCensus {
    /// Extension degree.
    pub n: u32,
    /// `K(√b)` indexed by `b`'s bitmask.
    pub kloosterman: Vec<i64>,
    /// Trace → every curve with that trace.  Keys are the traces that
    /// actually occur; the union of the values is *all* `2(2^n − 1)`
    /// isomorphism classes.
    pub classes: BTreeMap<i64, Vec<CurveId>>,
}

impl IsogenyCensus {
    /// Build the census.  `Θ(n · 2^n)` for the point counts plus
    /// `Θ(2^n log 2^n)` to sort them into classes.
    pub fn build(n: u32, irr: &IrreduciblePoly) -> Self {
        let kloosterman = kloosterman_all(n, irr);
        let mut classes: BTreeMap<i64, Vec<CurveId>> = BTreeMap::new();
        for b in 1..(1u64 << n) {
            for a_trace in 0..2u8 {
                let t = trace_of_curve(&kloosterman, b, a_trace);
                classes.entry(t).or_default().push(CurveId { b, a_trace });
            }
        }
        Self {
            n,
            kloosterman,
            classes,
        }
    }

    /// Trace of the ECC2K-130 analogue over this field: the Koblitz
    /// curve `K_0 : y² + xy = x³ + 1`, i.e. `b = 1`, `Tr(a) = 0`.
    pub fn koblitz_trace(&self) -> i64 {
        trace_of_curve(&self.kloosterman, 1, 0)
    }

    /// The trace predicted by Koblitz's recurrence
    /// `s_0 = 2, s_1 = t_1, s_k = t_1 s_{k−1} − 2 s_{k−2}` with
    /// `t_1 = −1` for `a = 0` — an independent check on the census.
    pub fn koblitz_trace_expected(&self) -> i64 {
        koblitz_trace_recurrence(-1, self.n)
            .try_into()
            .expect("census n ≤ 22 keeps the trace far inside i64")
    }

    /// **The isogeny class of the ECC2K-130 analogue**: every ordinary
    /// curve over `F_{2^n}` with the same point count as `K_0`.
    ///
    /// This is the exhaustive target set of the whole thread.
    pub fn koblitz_class(&self) -> &[CurveId] {
        self.classes
            .get(&self.koblitz_trace())
            .map(|v| v.as_slice())
            .unwrap_or(&[])
    }

    /// Class containing a given curve.
    pub fn class_containing(&self, id: CurveId) -> &[CurveId] {
        let t = trace_of_curve(&self.kloosterman, id.b, id.a_trace);
        self.classes.get(&t).map(|v| v.as_slice()).unwrap_or(&[])
    }

    /// Aggregate shape of the census, for the sanity table.
    pub fn stats(&self) -> ClassStats {
        let sizes: Vec<usize> = self.classes.values().map(|v| v.len()).collect();
        let total: usize = sizes.iter().sum();
        let hasse = (2.0f64 * (1u64 << self.n) as f64).sqrt();
        ClassStats {
            n: self.n,
            curves: total,
            classes: sizes.len(),
            largest: sizes.iter().copied().max().unwrap_or(0),
            smallest: sizes.iter().copied().min().unwrap_or(0),
            mean: if sizes.is_empty() {
                0.0
            } else {
                total as f64 / sizes.len() as f64
            },
            hasse_width: 2.0 * hasse,
            koblitz_class_size: self.koblitz_class().len(),
        }
    }
}

/// Summary row for a census.
#[derive(Clone, Copy, Debug)]
pub struct ClassStats {
    pub n: u32,
    /// `2(2^n − 1)`, every isomorphism class.
    pub curves: usize,
    /// Distinct traces occurring, i.e. isogeny classes.
    pub classes: usize,
    pub largest: usize,
    pub smallest: usize,
    pub mean: f64,
    /// `4√(2^n)`, the width of the Hasse interval — the number of traces
    /// that *could* occur.
    pub hasse_width: f64,
    /// Size of the class this thread searches.
    pub koblitz_class_size: usize,
}

/// `class_of(census, b, a_trace)` — convenience for the runner.
pub fn class_of(census: &IsogenyCensus, b: u64, a_trace: u8) -> &[CurveId] {
    census.class_containing(CurveId { b, a_trace })
}

/// `s_n` from Koblitz's recurrence, the trace of the `2^n`-power
/// Frobenius of a curve defined over `F_2` with trace `t1`.
///
/// Returns `i128`: at `n = 131` the trace is `≈ −2.2 · 10^19`, which
/// **overflows `i64`**, and silently truncating it would corrupt every
/// downstream quantity — the group order, the Frobenius discriminant,
/// and with it the list of isogeny degrees the curve admits.
pub fn koblitz_trace_recurrence(t1: i64, n: u32) -> i128 {
    let (mut prev, mut cur) = (2i128, t1 as i128);
    for _ in 1..n {
        let next = (t1 as i128) * cur - 2 * prev;
        prev = cur;
        cur = next;
    }
    cur
}

// ── Subfield members: the only lever, and where it lives ───────────

/// Every curve in the census whose `j`-invariant lies in a **proper
/// subfield** of `F_{2^n}` — the curves that admit the subfield/Koblitz
/// factor base, which is the one lever known to lower `D*`.
///
/// `j = 1/b`, so this is the set of `b` fixed by some `Frob^d` with
/// `d | n`, `d < n`.  For **prime** `n` — and `n = 131` is prime — the
/// only proper subfield is `F_2`, so the answer is the single element
/// `b = 1`: **ECC2K-130 itself**.  An isogeny walk cannot acquire this
/// structure, only lose it.
pub fn subfield_members(n: u32, irr: &IrreduciblePoly) -> Vec<(u32, Vec<u64>)> {
    assert!(
        n <= MAX_CENSUS_N,
        "subfield_members enumerates the field: n ≤ {MAX_CENSUS_N}. \
         For n = 131 use subfield_j_count, which counts without enumerating."
    );
    let mut out = Vec::new();
    for d in 1..n {
        if !n.is_multiple_of(d) {
            continue;
        }
        let mut members = Vec::new();
        for b in 1..(1u64 << n) {
            let e = elem_of(b, n);
            // b ∈ F_{2^d} ⟺ b^{2^d} = b.
            let mut p = e.clone();
            for _ in 0..d {
                p = p.square(irr);
            }
            if mask_of(&p) == b {
                members.push(b);
            }
        }
        out.push((d, members));
    }
    out
}

/// How many `j`-invariants of `F_{2^n}` lie in a proper subfield, without
/// enumerating the field — usable at `n = 131` where enumeration is not.
///
/// `|⋃_{d|n, d<n} F_{2^d}|`, by inclusion–exclusion over the divisor
/// lattice; the union is `F_{2^{d_max}}` when the proper divisors form a
/// chain, and for **prime `n` it is `F_2`, of size 2** — the count this
/// thread needs.
pub fn subfield_j_count(n: u32) -> u64 {
    let mut seen: Vec<u32> = (1..n).filter(|d| n.is_multiple_of(*d)).collect();
    seen.sort_unstable();
    // Elements of F_{2^d} ⊂ F_{2^e} whenever d | e, so the union is the
    // union of the maximal proper divisors' fields; count by
    // inclusion–exclusion on those.
    let maximal: Vec<u32> = seen
        .iter()
        .copied()
        .filter(|d| !seen.iter().any(|e| *e != *d && e.is_multiple_of(*d)))
        .collect();
    let k = maximal.len();
    let mut total = 0i64;
    for subset in 1u32..(1u32 << k) {
        let mut g = 0u32;
        for (i, d) in maximal.iter().enumerate() {
            if (subset >> i) & 1 == 1 {
                g = if g == 0 { *d } else { gcd(g, *d) };
            }
        }
        let sign = if (subset.count_ones() % 2) == 1 {
            1
        } else {
            -1
        };
        total += sign * (1i64 << g);
    }
    total.max(0) as u64
}

fn gcd(a: u32, b: u32) -> u32 {
    if b == 0 {
        a
    } else {
        gcd(b, a % b)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::koblitz_index_calculus::find_irreducible;

    /// The fast transform must reproduce the definition, element for
    /// element.  This is the cross-check the repository requires of a
    /// new oracle replacing an old one.
    #[test]
    fn wht_matches_direct_kloosterman() {
        for n in [3u32, 5, 7, 9] {
            let irr = find_irreducible(n).unwrap();
            let all = kloosterman_all(n, &irr);
            for c in 0..(1u64 << n) {
                let ce = elem_of(c, n);
                let b = mask_of(&ce.square(&irr));
                let direct = kloosterman_direct(n, &irr, &ce);
                assert_eq!(
                    all[b as usize], direct,
                    "n = {n}, c = {c:#x}: transform {} vs definition {direct}",
                    all[b as usize]
                );
            }
        }
    }

    /// The census must agree with Koblitz's trace recurrence on the
    /// curve the recurrence was written for.
    #[test]
    fn census_matches_koblitz_recurrence() {
        for n in [3u32, 5, 7, 9, 11, 13] {
            let irr = find_irreducible(n).unwrap();
            let census = IsogenyCensus::build(n, &irr);
            assert_eq!(
                census.koblitz_trace(),
                census.koblitz_trace_expected(),
                "n = {n}"
            );
        }
    }

    /// Every trace in the census must satisfy the Hasse bound, and the
    /// census must contain every isomorphism class exactly once.
    #[test]
    fn census_is_exhaustive_and_hasse_bounded() {
        for n in [5u32, 7, 9, 11] {
            let irr = find_irreducible(n).unwrap();
            let census = IsogenyCensus::build(n, &irr);
            let stats = census.stats();
            assert_eq!(stats.curves, 2 * ((1usize << n) - 1), "n = {n}");
            let bound = 2.0 * ((1u64 << n) as f64).sqrt();
            for t in census.classes.keys() {
                assert!((*t as f64).abs() <= bound + 1e-9, "n = {n}, t = {t}");
            }
        }
    }

    /// A quadratic twist has the negated trace, so the two halves of the
    /// census mirror each other.
    #[test]
    fn twist_negates_the_trace() {
        let n = 9;
        let irr = find_irreducible(n).unwrap();
        let census = IsogenyCensus::build(n, &irr);
        for b in 1..(1u64 << n) {
            let t0 = trace_of_curve(&census.kloosterman, b, 0);
            let t1 = trace_of_curve(&census.kloosterman, b, 1);
            assert_eq!(t0, -t1, "b = {b:#x}");
        }
    }

    /// For prime `n` the only curve with subfield structure is `b = 1`.
    /// This is the fact that kills the isogeny search at `n = 131`.
    #[test]
    fn prime_degree_has_exactly_one_subfield_curve() {
        for n in [5u32, 7, 11, 13] {
            let irr = find_irreducible(n).unwrap();
            let members = subfield_members(n, &irr);
            assert_eq!(members.len(), 1, "prime n has one proper divisor");
            assert_eq!(members[0].0, 1, "the divisor is d = 1");
            assert_eq!(members[0].1, vec![1u64], "F_2^* = {{1}}");
            assert_eq!(subfield_j_count(n), 2, "F_2 has two elements");
        }
        // 131 is prime, so the same count applies where it matters.
        assert_eq!(subfield_j_count(131), 2);
        // A composite degree really does have more room — the contrast
        // that makes the n = 131 answer a statement about 131.
        assert!(subfield_j_count(12) > 2);
    }
}
