//! # Incremental modular echelon form for index-calculus relation matrices.
//!
//! The Koblitz index-calculus driver collects relations
//!
//! ```text
//!     Σ_o c_o · x_o  −  (h·b)·d  ≡  h·a   (mod r)
//! ```
//!
//! one at a time and wants to know, as early as possible, whether the
//! target scalar `d` is already pinned down.  Re-running a dense
//! `BigUint` Gaussian elimination after every batch is `O(U³)` big-integer
//! work per check and, worse, cannot distinguish "not yet determined"
//! from "determined": it returns a partial solution that must then be
//! verified in the group.
//!
//! This solver keeps the relation matrix in **reduced row echelon form
//! over `Z/rZ`** and updates it per row in `O(U²)` native `u64`
//! operations (`r < 2^64`, which covers every field degree this crate
//! materialises).  Column `U` is `d`; because every pivot row has zeros
//! in all other pivot columns, a pivot in column `U` reads off `d`
//! directly, so `target()` answers the "is `d` determined?" question
//! exactly.  Dependent relations are recognised and dropped instead of
//! silently padding the matrix, and an inconsistent row is reported —
//! it can only come from a wrong relation, which the driver treats as a
//! failure rather than something to average away.
//!
//! The dense solver in
//! [`crate::cryptanalysis::ec_index_calculus::gaussian_eliminate_mod_n`]
//! remains the reference; the tests cross-check the two on random
//! systems with planted solutions.

use num_bigint::BigUint;

use super::koblitz_index_calculus::KoblitzRelation;

/// Outcome of feeding one relation to the solver.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RowStatus {
    /// The row raised the rank.
    Independent,
    /// The row was a linear combination of earlier rows; nothing changed.
    Dependent,
    /// The row contradicts earlier rows: `0 ≡ c` with `c ≠ 0`.  Only a
    /// wrong relation can do this, so the driver must fail closed.
    Inconsistent,
}

/// Reduced row echelon form of the relation matrix, maintained one row
/// at a time.  Columns `0..unknowns` are orbit logarithms, column
/// `unknowns` is the target scalar `d`, and the right-hand side sits in
/// the last position of each stored row.
#[derive(Clone, Debug)]
pub struct IncrementalRelationSolver {
    modulus: u64,
    unknowns: usize,
    /// `pivot_rows[c]` is the row whose leading entry (normalised to 1)
    /// is in column `c`, or `None` if column `c` is free.
    pivot_rows: Vec<Option<Vec<u64>>>,
    rank: usize,
    rows_seen: usize,
    dependent_rows: usize,
    inconsistent: bool,
}

#[inline]
fn mulmod(a: u64, b: u64, m: u64) -> u64 {
    ((a as u128 * b as u128) % m as u128) as u64
}

/// `a − b mod m` for reduced `b`, without a branch: which side of `b` the
/// value `a` falls on is data, a coin flip in the elimination loops, and
/// a mispredicted branch there costs more than the arithmetic.
#[inline]
fn submod(a: u64, b: u64, m: u64) -> u64 {
    let (d, borrow) = a.overflowing_sub(b);
    d.wrapping_add(m & (borrow as u64).wrapping_neg())
}

/// A scalar `w` prepared for many multiplications modulo `m`.
///
/// Every inner loop of the elimination multiplies one scalar — a pivot
/// factor or an inverse — into a whole row, so the division a `u128 %`
/// performs per product can be paid once per row instead.  This is
/// Shoup's form of Barrett reduction: with `w' = ⌊w·2^64 / m⌋` stored
/// beside `w`, the estimate `q = ⌊w'·x / 2^64⌋` of `⌊w·x / m⌋` is exact
/// or one too small for every word `x` (the two floors lose less than
/// `x/2^64 + 1 < 2`), so `w·x − q·m` lies in `[0, 2m)` and one
/// conditional subtraction of `m` finishes the reduction.  The result is
/// `(w·x) mod m` exactly, for every `x < 2^64` and every modulus; that
/// `m` is prime is not used.
///
/// The remainder before correction is below `2m`, which fits a word only
/// while `m < 2^63`; the `WIDE` form carries it in 128 bits for the
/// moduli above that.  Both corrections are written as masks rather
/// than comparisons because the compiler turns a comparison against a
/// freshly loaded value into a branch, and this one is unpredictable.
#[derive(Clone, Copy, Debug)]
struct Scalar {
    w: u64,
    quotient: u64,
}

impl Scalar {
    #[inline]
    fn new(w: u64, m: u64) -> Self {
        let w = w % m;
        // `w < m`, so the quotient is below 2^64.
        let quotient = (((w as u128) << 64) / m as u128) as u64;
        Self { w, quotient }
    }

    /// `w·x mod m`.  `WIDE` must be set when `m ≥ 2^63`.
    #[inline(always)]
    fn mul<const WIDE: bool>(self, x: u64, m: u64) -> u64 {
        let q = ((self.quotient as u128 * x as u128) >> 64) as u64;
        if WIDE {
            // `t = w·x − q·m − m` lies in `[−m, m)`, so its high word is
            // all ones exactly when `t` is negative, i.e. when the
            // subtraction of `m` was one too many.
            let t = (self.w as u128 * x as u128)
                .wrapping_sub(q as u128 * m as u128)
                .wrapping_sub(m as u128);
            (t as u64).wrapping_add(m & (t >> 64) as u64)
        } else {
            // With `m < 2^63` the same `t` fits a signed word.
            let t = self
                .w
                .wrapping_mul(x)
                .wrapping_sub(q.wrapping_mul(m))
                .wrapping_sub(m);
            t.wrapping_add(m & ((t as i64 >> 63) as u64))
        }
    }
}

/// Modular inverse by the extended Euclidean algorithm; `None` when
/// `a` and `m` are not coprime (impossible for prime `m` and `a ≠ 0`).
///
/// The remainders never exceed `max(a, m)`, so they stay in words and
/// each step is one hardware division rather than a 128-bit one; only
/// the cofactors, bounded by `m` in absolute value, need a signed type
/// wider than a word.
fn invmod(a: u64, m: u64) -> Option<u64> {
    let (mut old_r, mut r) = (a, m);
    let (mut old_s, mut s) = (1i128, 0i128);
    while r != 0 {
        let q = old_r / r;
        (old_r, r) = (r, old_r - q * r);
        (old_s, s) = (s, old_s - q as i128 * s);
    }
    if old_r != 1 {
        return None;
    }
    Some(old_s.rem_euclid(m as i128) as u64)
}

fn to_u64_mod(v: &BigUint, m: u64) -> u64 {
    let reduced = v % BigUint::from(m);
    reduced.to_u64_digits().first().copied().unwrap_or(0)
}

impl IncrementalRelationSolver {
    /// A solver over `Z/rZ` with `unknowns` orbit columns plus the
    /// target column.  Returns `None` when the modulus does not fit a
    /// `u64` or is not at least 2; callers then fall back to the dense
    /// big-integer path.
    pub fn new(unknowns: usize, modulus: &BigUint) -> Option<Self> {
        if modulus.bits() > 64 || modulus < &BigUint::from(2u32) {
            return None;
        }
        let modulus = modulus.to_u64_digits().first().copied()?;
        Some(Self {
            modulus,
            unknowns,
            pivot_rows: vec![None; unknowns + 1],
            rank: 0,
            rows_seen: 0,
            dependent_rows: 0,
            inconsistent: false,
        })
    }

    /// The prime modulus `r`.
    pub fn modulus(&self) -> u64 {
        self.modulus
    }

    /// Current rank of the relation matrix (independent rows kept).
    pub fn rank(&self) -> usize {
        self.rank
    }

    /// Relations fed so far, dependent ones included.
    pub fn rows_seen(&self) -> usize {
        self.rows_seen
    }

    /// Relations that were linear combinations of earlier ones.
    pub fn dependent_rows(&self) -> usize {
        self.dependent_rows
    }

    /// Whether an inconsistent row has ever been seen.
    pub fn is_inconsistent(&self) -> bool {
        self.inconsistent
    }

    /// Number of orbit columns.
    pub fn unknowns(&self) -> usize {
        self.unknowns
    }

    /// Feed a relation `[a]G + [b]Q = Σ P_i`, already rewritten over the
    /// orbit columns, with the cofactor `h` applied as in the driver.
    pub fn add_relation(&mut self, relation: &KoblitzRelation, cofactor: &BigUint) -> RowStatus {
        let m = self.modulus;
        let h = to_u64_mod(cofactor, m);
        let hb = mulmod(h, to_u64_mod(&relation.coef_b, m), m);
        let ha = mulmod(h, to_u64_mod(&relation.coef_a, m), m);
        let mut row = vec![0u64; self.unknowns + 2];
        for (o, c) in relation.row.iter().enumerate().take(self.unknowns) {
            row[o] = to_u64_mod(c, m);
        }
        row[self.unknowns] = submod(0, hb, m);
        row[self.unknowns + 1] = ha;
        self.add_row(row)
    }

    /// Feed a raw row `[c_0, …, c_{U−1}, c_d | rhs]` reduced mod `r`.
    pub fn add_row(&mut self, row: Vec<u64>) -> RowStatus {
        assert_eq!(row.len(), self.unknowns + 2, "row width");
        // The reduction width is fixed by the modulus, so it is chosen
        // once per row here rather than once per product.
        if self.modulus < 1 << 63 {
            self.eliminate::<false>(row)
        } else {
            self.eliminate::<true>(row)
        }
    }

    fn eliminate<const WIDE: bool>(&mut self, mut row: Vec<u64>) -> RowStatus {
        let m = self.modulus;
        let width = self.unknowns + 2;
        self.rows_seen += 1;
        // Reduce against every existing pivot, in column order.  A pivot
        // row has zeros before its pivot column, so subtraction starts
        // there.
        for col in 0..=self.unknowns {
            let factor = row[col];
            if factor == 0 {
                continue;
            }
            if let Some(pivot) = &self.pivot_rows[col] {
                let factor = Scalar::new(factor, m);
                for (r, &p) in row[col..].iter_mut().zip(&pivot[col..]) {
                    if p != 0 {
                        *r = submod(*r, factor.mul::<WIDE>(p, m), m);
                    }
                }
            }
        }
        let lead = (0..=self.unknowns).find(|&c| row[c] != 0);
        let Some(lead) = lead else {
            if row[self.unknowns + 1] != 0 {
                self.inconsistent = true;
                return RowStatus::Inconsistent;
            }
            self.dependent_rows += 1;
            return RowStatus::Dependent;
        };
        // Normalise, then clear this column from every other pivot row
        // so the form stays fully reduced.
        let inv = invmod(row[lead], m).expect("prime modulus: nonzero entries invert");
        let inv = Scalar::new(inv, m);
        for r in &mut row[lead..] {
            *r = inv.mul::<WIDE>(*r, m);
        }
        // Only pivots left of `lead` can have an entry in its column: a
        // pivot row is zero before its own pivot column, and the rows
        // right of it would each cost a cache miss to find that out.
        for col in 0..lead {
            if let Some(pivot) = self.pivot_rows[col].as_mut() {
                let factor = pivot[lead];
                if factor == 0 {
                    continue;
                }
                let factor = Scalar::new(factor, m);
                for (p, &r) in pivot[lead..width].iter_mut().zip(&row[lead..]) {
                    if r != 0 {
                        *p = submod(*p, factor.mul::<WIDE>(r, m), m);
                    }
                }
            }
        }
        self.pivot_rows[lead] = Some(row);
        self.rank += 1;
        RowStatus::Independent
    }

    /// The target scalar `d`, exactly when the relations determine it —
    /// i.e. the reduced form has a pivot in the `d` column.
    pub fn target(&self) -> Option<u64> {
        let row = self.pivot_rows[self.unknowns].as_ref()?;
        // In reduced form the pivot row for the last unknown column is
        // `[0, …, 0, 1 | rhs]`.
        debug_assert!(row[..self.unknowns].iter().all(|&c| c == 0));
        Some(row[self.unknowns + 1])
    }

    /// The target scalar as a `BigUint`, if determined.
    pub fn target_biguint(&self) -> Option<BigUint> {
        self.target().map(BigUint::from)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::ec_index_calculus::gaussian_eliminate_mod_n;
    use num_traits::Zero;
    use rand::{rngs::StdRng, Rng, SeedableRng};

    fn planted_system(
        rng: &mut StdRng,
        unknowns: usize,
        rows: usize,
        modulus: u64,
        density: usize,
    ) -> (Vec<Vec<u64>>, Vec<u64>) {
        let secret: Vec<u64> = (0..=unknowns).map(|_| rng.gen_range(0..modulus)).collect();
        let mut out = Vec::new();
        for _ in 0..rows {
            let mut row = vec![0u64; unknowns + 2];
            for _ in 0..density {
                let o = rng.gen_range(0..unknowns);
                row[o] = rng.gen_range(1..modulus);
            }
            row[unknowns] = rng.gen_range(1..modulus);
            let mut rhs = 0u64;
            for (k, &c) in row.iter().enumerate().take(unknowns + 1) {
                rhs = (rhs + mulmod(c, secret[k], modulus)) % modulus;
            }
            row[unknowns + 1] = rhs;
            out.push(row);
        }
        (out, secret)
    }

    #[test]
    fn determines_the_planted_target_and_agrees_with_the_dense_solver() {
        let mut rng = StdRng::seed_from_u64(0x1234);
        for modulus in [127u64, 991, 2003, 262_543, 4_294_967_291] {
            for unknowns in [1usize, 3, 7, 12] {
                let (rows, secret) = planted_system(&mut rng, unknowns, unknowns + 6, modulus, 2);
                let big = BigUint::from(modulus);
                let mut solver = IncrementalRelationSolver::new(unknowns, &big).unwrap();
                let mut determined_at = None;
                for (i, row) in rows.iter().enumerate() {
                    let status = solver.add_row(row.clone());
                    assert_ne!(status, RowStatus::Inconsistent);
                    if let Some(d) = solver.target() {
                        assert_eq!(d, secret[unknowns], "modulus {modulus}, U {unknowns}");
                        if determined_at.is_none() {
                            determined_at = Some(i + 1);
                        }
                    }
                    // Whenever the dense solver's answer verifies, ours
                    // must be determined too, and equal.
                    let mut matrix: Vec<Vec<BigUint>> = rows[..=i]
                        .iter()
                        .map(|r| r[..=unknowns].iter().map(|&c| BigUint::from(c)).collect())
                        .collect();
                    let mut rhs: Vec<BigUint> = rows[..=i]
                        .iter()
                        .map(|r| BigUint::from(r[unknowns + 1]))
                        .collect();
                    if let Some(sol) = gaussian_eliminate_mod_n(&mut matrix, &mut rhs, &big) {
                        let dense_d = sol[unknowns].to_u64_digits().first().copied().unwrap_or(0);
                        if solver.target().is_some() {
                            assert_eq!(dense_d, solver.target().unwrap());
                        }
                    }
                }
                assert!(
                    determined_at.is_some(),
                    "U + 6 random rows should determine d (modulus {modulus}, U {unknowns})"
                );
                assert!(solver.rank() <= unknowns + 1);
                assert_eq!(solver.rows_seen(), unknowns + 6);
                assert_eq!(solver.rank() + solver.dependent_rows(), unknowns + 6);
            }
        }
    }

    #[test]
    fn dependent_rows_do_not_raise_rank_and_wrong_rows_are_flagged() {
        let modulus = 991u64;
        let big = BigUint::from(modulus);
        let mut solver = IncrementalRelationSolver::new(3, &big).unwrap();
        let row = vec![5u64, 0, 7, 3, 11];
        assert_eq!(solver.add_row(row.clone()), RowStatus::Independent);
        // Twice the same row is dependent.
        let doubled: Vec<u64> = row.iter().map(|&c| (2 * c) % modulus).collect();
        assert_eq!(solver.add_row(doubled), RowStatus::Dependent);
        assert_eq!(solver.rank(), 1);
        // Same coefficients, different right-hand side: inconsistent.
        let mut wrong = row.clone();
        wrong[4] = 12;
        assert_eq!(solver.add_row(wrong), RowStatus::Inconsistent);
        assert!(solver.is_inconsistent());
        assert!(solver.target().is_none());
    }

    #[test]
    fn target_is_only_reported_when_pinned() {
        // Two unknowns and d; one row cannot determine d.
        let modulus = 127u64;
        let big = BigUint::from(modulus);
        let mut solver = IncrementalRelationSolver::new(2, &big).unwrap();
        assert_eq!(solver.add_row(vec![1, 1, 1, 5]), RowStatus::Independent);
        assert!(solver.target().is_none());
        assert_eq!(solver.add_row(vec![1, 0, 1, 3]), RowStatus::Independent);
        assert!(solver.target().is_none());
        assert_eq!(solver.add_row(vec![0, 1, 1, 4]), RowStatus::Independent);
        // x0 + x1 + d = 5, x0 + d = 3, x1 + d = 4  ⇒  x0 = 1, x1 = 2, d = 2.
        assert_eq!(solver.target(), Some(2));
    }

    /// Moduli at the edges of both reduction widths: the smallest ones,
    /// word-size primes, and the primes either side of 2^63 and just
    /// below 2^64, where the pre-correction remainder `< 2m` stops
    /// fitting a word.
    const EDGE_PRIMES: [u64; 10] = [
        2,
        3,
        5,
        127,
        2_147_483_647,
        4_294_967_291,
        (1 << 61) - 1,
        (1 << 63) - 25,
        (1 << 63) + 29,
        u64::MAX - 58,
    ];

    #[test]
    fn scalar_mul_matches_the_u128_remainder() {
        let mut rng = StdRng::seed_from_u64(0x5ca1a);
        let mut moduli: Vec<u64> = EDGE_PRIMES.to_vec();
        moduli.extend([4, 1 << 32, (1 << 63) - 1, 1 << 63, (1 << 63) + 1, u64::MAX]);
        // Arbitrary moduli of every bit length: nothing here needs a prime.
        for bits in 2..=64u32 {
            let low = 1u64 << (bits - 1);
            moduli.push(low | (rng.gen::<u64>() & (low - 1)));
        }
        for &m in &moduli {
            let mut words = vec![0, 1, 2, m - 1, m, m.wrapping_add(1), 1 << 63, u64::MAX];
            words.extend((0..24).map(|_| rng.gen_range(0..m)));
            words.extend((0..8).map(|_| rng.gen::<u64>()));
            // The scalar is reduced on construction, so an unreduced one
            // is tested too; the operand may be any word.
            for &w in &words {
                let scalar = Scalar::new(w, m);
                for &x in &words {
                    let expected = mulmod(w % m, x, m);
                    assert_eq!(scalar.mul::<true>(x, m), expected, "wide w={w} x={x} m={m}");
                    if m < 1 << 63 {
                        assert_eq!(scalar.mul::<false>(x, m), expected, "w={w} x={x} m={m}");
                    }
                }
            }
        }
    }

    /// The elimination as it was written with a `u128 %` per product and
    /// branching subtraction, kept as the reference the solver must match
    /// bit for bit.
    fn reference_add_row(
        pivot_rows: &mut [Option<Vec<u64>>],
        unknowns: usize,
        m: u64,
        mut row: Vec<u64>,
    ) -> RowStatus {
        let sub = |a: u64, b: u64| if a >= b { a - b } else { a + (m - b) };
        let width = unknowns + 2;
        for col in 0..=unknowns {
            let factor = row[col];
            if factor == 0 {
                continue;
            }
            if let Some(pivot) = &pivot_rows[col] {
                for k in col..width {
                    if pivot[k] != 0 {
                        row[k] = sub(row[k], mulmod(factor, pivot[k], m));
                    }
                }
            }
        }
        let Some(lead) = (0..=unknowns).find(|&c| row[c] != 0) else {
            return if row[unknowns + 1] != 0 {
                RowStatus::Inconsistent
            } else {
                RowStatus::Dependent
            };
        };
        let inv = invmod(row[lead], m).unwrap();
        for k in lead..width {
            row[k] = mulmod(row[k], inv, m);
        }
        for col in 0..=unknowns {
            if col == lead {
                continue;
            }
            if let Some(pivot) = pivot_rows[col].as_mut() {
                let factor = pivot[lead];
                if factor == 0 {
                    continue;
                }
                for k in lead..width {
                    if row[k] != 0 {
                        pivot[k] = sub(pivot[k], mulmod(factor, row[k], m));
                    }
                }
            }
        }
        pivot_rows[lead] = Some(row);
        RowStatus::Independent
    }

    #[test]
    fn elimination_matches_the_division_reference_bit_for_bit() {
        let mut rng = StdRng::seed_from_u64(0xe11a);
        let mut seen = [0usize; 3];
        for &m in &EDGE_PRIMES {
            for (unknowns, density) in [(6usize, 2usize), (24, 3), (40, 12)] {
                let big = BigUint::from(m);
                let mut solver = IncrementalRelationSolver::new(unknowns, &big).unwrap();
                let mut reference = vec![None; unknowns + 1];
                // More rows than columns, so dependent rows occur, and
                // some repeated rows with a shifted right-hand side, so
                // inconsistent ones do too.
                let mut fed: Vec<Vec<u64>> = Vec::new();
                for i in 0..unknowns + 12 {
                    let row = if i % 7 == 6 {
                        let mut again = fed[rng.gen_range(0..fed.len())].clone();
                        again[unknowns + 1] = rng.gen_range(0..m);
                        again
                    } else {
                        let mut row = vec![0u64; unknowns + 2];
                        for _ in 0..density {
                            row[rng.gen_range(0..unknowns)] = rng.gen_range(1..m);
                        }
                        row[unknowns] = rng.gen_range(0..m);
                        row[unknowns + 1] = rng.gen_range(0..m);
                        row
                    };
                    fed.push(row.clone());
                    let expected = reference_add_row(&mut reference, unknowns, m, row.clone());
                    assert_eq!(solver.add_row(row), expected, "m={m} U={unknowns} row {i}");
                    assert_eq!(solver.pivot_rows, reference, "m={m} U={unknowns} row {i}");
                    seen[expected as usize] += 1;
                }
                assert_eq!(solver.rows_seen(), unknowns + 12);
            }
        }
        // Every outcome of a row was exercised, not only the pivot path.
        assert!(seen.iter().all(|&n| n > 0), "statuses seen {seen:?}");
    }

    #[test]
    fn rejects_moduli_that_do_not_fit() {
        let too_big = BigUint::from(1u8) << 70;
        assert!(IncrementalRelationSolver::new(4, &too_big).is_none());
        assert!(IncrementalRelationSolver::new(4, &BigUint::zero()).is_none());
    }
}

/// Differential check against the solver as it stood before the
/// precomputed-quotient reduction (994784af): the division-based
/// `mulmod`, the branching `submod`, the 128-bit Euclid and the
/// back-substitution over every pivot, copied verbatim.  The whole state —
/// every pivot row and every counter — must agree after every row, and
/// where the old code panicked (a non-prime modulus, an unreduced row)
/// the new one must panic on the same row and leave the same state.
#[cfg(test)]
mod division_reference {
    use super::{IncrementalRelationSolver, RowStatus};
    use num_bigint::BigUint;
    use rand::{rngs::StdRng, Rng, SeedableRng};
    use std::panic::{catch_unwind, AssertUnwindSafe};

    fn mulmod(a: u64, b: u64, m: u64) -> u64 {
        ((a as u128 * b as u128) % m as u128) as u64
    }

    fn submod(a: u64, b: u64, m: u64) -> u64 {
        if a >= b {
            a - b
        } else {
            a + (m - b)
        }
    }

    fn invmod(a: u64, m: u64) -> Option<u64> {
        let (mut old_r, mut r) = (a as i128, m as i128);
        let (mut old_s, mut s) = (1i128, 0i128);
        while r != 0 {
            let q = old_r / r;
            (old_r, r) = (r, old_r - q * r);
            (old_s, s) = (s, old_s - q * s);
        }
        if old_r != 1 {
            return None;
        }
        Some(old_s.rem_euclid(m as i128) as u64)
    }

    #[derive(Clone, Debug, PartialEq, Eq)]
    struct Old {
        modulus: u64,
        unknowns: usize,
        pivot_rows: Vec<Option<Vec<u64>>>,
        rank: usize,
        rows_seen: usize,
        dependent_rows: usize,
        inconsistent: bool,
    }

    impl Old {
        fn new(unknowns: usize, modulus: u64) -> Self {
            Self {
                modulus,
                unknowns,
                pivot_rows: vec![None; unknowns + 1],
                rank: 0,
                rows_seen: 0,
                dependent_rows: 0,
                inconsistent: false,
            }
        }

        fn add_row(&mut self, mut row: Vec<u64>) -> RowStatus {
            assert_eq!(row.len(), self.unknowns + 2, "row width");
            let m = self.modulus;
            let width = self.unknowns + 2;
            self.rows_seen += 1;
            for col in 0..=self.unknowns {
                let factor = row[col];
                if factor == 0 {
                    continue;
                }
                if let Some(pivot) = &self.pivot_rows[col] {
                    for k in col..width {
                        if pivot[k] != 0 {
                            row[k] = submod(row[k], mulmod(factor, pivot[k], m), m);
                        }
                    }
                }
            }
            let lead = (0..=self.unknowns).find(|&c| row[c] != 0);
            let Some(lead) = lead else {
                if row[self.unknowns + 1] != 0 {
                    self.inconsistent = true;
                    return RowStatus::Inconsistent;
                }
                self.dependent_rows += 1;
                return RowStatus::Dependent;
            };
            let inv = invmod(row[lead], m).expect("prime modulus: nonzero entries invert");
            for k in lead..width {
                row[k] = mulmod(row[k], inv, m);
            }
            for col in 0..=self.unknowns {
                if col == lead {
                    continue;
                }
                if let Some(pivot) = self.pivot_rows[col].as_mut() {
                    let factor = pivot[lead];
                    if factor == 0 {
                        continue;
                    }
                    for k in lead..width {
                        if row[k] != 0 {
                            pivot[k] = submod(pivot[k], mulmod(factor, row[k], m), m);
                        }
                    }
                }
            }
            self.pivot_rows[lead] = Some(row);
            self.rank += 1;
            RowStatus::Independent
        }
    }

    fn same_state(new: &IncrementalRelationSolver, old: &Old) -> bool {
        new.modulus == old.modulus
            && new.unknowns == old.unknowns
            && new.pivot_rows == old.pivot_rows
            && new.rank == old.rank
            && new.rows_seen == old.rows_seen
            && new.dependent_rows == old.dependent_rows
            && new.inconsistent == old.inconsistent
    }

    fn is_prime(n: u64) -> bool {
        if n < 2 {
            return false;
        }
        for p in [2u64, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37] {
            if n.is_multiple_of(p) {
                return n == p;
            }
        }
        let (mut d, mut s) = (n - 1, 0);
        while d % 2 == 0 {
            d /= 2;
            s += 1;
        }
        let pow = |mut b: u64, mut e: u64| {
            let mut acc = 1u64;
            while e > 0 {
                if e & 1 == 1 {
                    acc = mulmod(acc, b, n);
                }
                b = mulmod(b, b, n);
                e >>= 1;
            }
            acc
        };
        'witness: for a in [2u64, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37] {
            let mut x = pow(a, d);
            if x == 1 || x == n - 1 {
                continue;
            }
            for _ in 1..s {
                x = mulmod(x, x, n);
                if x == n - 1 {
                    continue 'witness;
                }
            }
            return false;
        }
        true
    }

    /// Primes and composites across both reduction widths.
    fn moduli(rng: &mut StdRng) -> Vec<u64> {
        let mut out = vec![
            2,
            3,
            4,
            6,
            7,
            127,
            (1 << 31) - 1,
            1 << 32,
            (1 << 61) - 1,
            (1 << 62) + 1,
            (1 << 63) - 25,
            (1 << 63) - 1,
            1 << 63,
            (1 << 63) + 1,
            (1 << 63) + 29,
            u64::MAX - 58,
            u64::MAX,
        ];
        for bits in [2u32, 8, 17, 32, 33, 48, 62, 63, 64] {
            let low = 1u64 << (bits - 1);
            loop {
                let m = low | (rng.gen::<u64>() & (low - 1));
                if is_prime(m) {
                    out.push(m);
                    break;
                }
            }
            out.push(low | (rng.gen::<u64>() & (low - 1)));
        }
        out
    }

    /// Feed `row` to both and compare the outcome and the whole state.
    fn feed(
        new: &mut IncrementalRelationSolver,
        old: &mut Old,
        row: Vec<u64>,
        ctx: &str,
    ) -> Option<RowStatus> {
        let a = catch_unwind(AssertUnwindSafe(|| new.add_row(row.clone())));
        let b = catch_unwind(AssertUnwindSafe(|| old.add_row(row.clone())));
        let status = match (a, b) {
            (Ok(x), Ok(y)) => {
                assert_eq!(x, y, "{ctx}: status");
                Some(x)
            }
            (Err(_), Err(_)) => None,
            (x, y) => panic!("{ctx}: new {:?} vs old {:?}", x.is_ok(), y.is_ok()),
        };
        assert!(same_state(new, old), "{ctx}: state differs");
        status
    }

    #[test]
    fn invmod_and_submod_match_the_old_routines() {
        let mut rng = StdRng::seed_from_u64(0x1a7e);
        for m in moduli(&mut rng) {
            let mut words = vec![0, 1, 2, m - 1, m, m.wrapping_add(1), 1 << 63, u64::MAX];
            words.extend((0..64).map(|_| rng.gen_range(0..m)));
            words.extend((0..16).map(|_| rng.gen::<u64>()));
            for &a in &words {
                assert_eq!(super::invmod(a, m), invmod(a, m), "invmod a={a} m={m}");
                for &b in &words {
                    // The old form is only defined for reduced `b`.
                    if b < m {
                        assert_eq!(super::submod(a, b, m), submod(a, b, m), "a={a} b={b} m={m}");
                    }
                }
            }
        }
    }

    #[test]
    fn solver_state_matches_the_old_solver_after_every_row() {
        let mut rng = StdRng::seed_from_u64(0xd1ff);
        let (mut statuses, mut panics) = ([0usize; 3], 0usize);
        for m in moduli(&mut rng) {
            for (unknowns, density) in [
                (0usize, 1usize),
                (1, 1),
                (2, 3),
                (31, 2),
                (63, 3),
                (64, 64),
                (65, 5),
                (100, 100),
                (130, 3),
            ] {
                let big = BigUint::from(m);
                let mut new = IncrementalRelationSolver::new(unknowns, &big).unwrap();
                let mut old = Old::new(unknowns, m);
                let width = unknowns + 2;
                let mut fed: Vec<Vec<u64>> = Vec::new();
                for i in 0..unknowns + 24 {
                    let kind = rng.gen_range(0..10);
                    let row = if kind < 6 || fed.is_empty() {
                        let mut row = vec![0u64; width];
                        for _ in 0..density.min(unknowns.max(1)) {
                            let c = rng.gen_range(0..=unknowns);
                            row[c] = rng.gen_range(0..m);
                        }
                        row[width - 1] = rng.gen_range(0..m);
                        row
                    } else if kind < 8 {
                        // A combination of earlier rows: dependent, or
                        // inconsistent when the right-hand side moves.
                        let mut row = vec![0u64; width];
                        for _ in 0..rng.gen_range(1..=3) {
                            let src = &fed[rng.gen_range(0..fed.len())];
                            let c = rng.gen_range(0..m);
                            for (r, &s) in row.iter_mut().zip(src) {
                                let sum = *r as u128 + mulmod(c, s % m, m) as u128;
                                *r = (sum % m as u128) as u64;
                            }
                        }
                        if kind == 7 {
                            row[width - 1] = rng.gen_range(0..m);
                        }
                        row
                    } else if kind == 8 {
                        // Only a right-hand side, or nothing at all.
                        let mut row = vec![0u64; width];
                        row[width - 1] = if rng.gen() { 0 } else { rng.gen_range(0..m) };
                        row
                    } else {
                        // Unreduced words: outside the documented
                        // contract, but the behaviour must not change.
                        let mut row = vec![0u64; width];
                        for _ in 0..density.min(unknowns.max(1)) {
                            row[rng.gen_range(0..=unknowns)] = rng.gen();
                        }
                        row[width - 1] = rng.gen();
                        row
                    };
                    fed.push(row.clone());
                    let ctx = format!("m={m} U={unknowns} row {i}");
                    match feed(&mut new, &mut old, row, &ctx) {
                        Some(s) => statuses[s as usize] += 1,
                        None => panics += 1,
                    }
                }
                let old_target = old.pivot_rows[unknowns].as_ref().map(|r| r[unknowns + 1]);
                assert_eq!(new.target(), old_target, "m={m} U={unknowns}");
            }
        }
        // Every outcome was exercised, the old panic included.
        assert!(
            statuses.iter().all(|&n| n > 0) && panics > 0,
            "statuses seen {statuses:?}, panics {panics}"
        );
    }
}
