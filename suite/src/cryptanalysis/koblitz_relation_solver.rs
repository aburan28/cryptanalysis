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

#[inline]
fn submod(a: u64, b: u64, m: u64) -> u64 {
    if a >= b {
        a - b
    } else {
        a + (m - b)
    }
}

/// Modular inverse by the extended Euclidean algorithm; `None` when
/// `a` and `m` are not coprime (impossible for prime `m` and `a ≠ 0`).
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
    pub fn add_row(&mut self, mut row: Vec<u64>) -> RowStatus {
        assert_eq!(row.len(), self.unknowns + 2, "row width");
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
        // Normalise, then clear this column from every other pivot row
        // so the form stays fully reduced.
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

    #[test]
    fn rejects_moduli_that_do_not_fit() {
        let too_big = BigUint::from(1u8) << 70;
        assert!(IncrementalRelationSolver::new(4, &too_big).is_none());
        assert!(IncrementalRelationSolver::new(4, &BigUint::zero()).is_none());
    }
}
