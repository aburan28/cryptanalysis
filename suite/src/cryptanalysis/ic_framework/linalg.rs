//! # Relation matrices, as plug-ins.
//!
//! The relation loop takes any [`RelationSolver`]; this module ships a
//! second one so the linear-algebra stage is a real lever rather than a
//! fixed cost.
//!
//! | name | method | storage | pivot | work unit |
//! |:--|:--|:--|:--|:--|
//! | `incremental-gauss` | dense reduced row echelon, maintained as rows arrive | `rank × |F|` entries | leftmost non-zero | `row_ops` |
//! | `structured-gauss` | sparse reduced row echelon, maintained as rows arrive | the non-zeros | lightest column (Markowitz) | `row_ops` |
//!
//! Both count a multiply-subtract on a **non-zero** entry as one
//! `row_op`, so the two `work` figures are directly comparable and
//! differ only through the pivot choice: pivoting on the lightest
//! column limits fill-in, which on the `m`-non-zero rows an
//! index-calculus relation phase produces is worth a few per cent, not
//! a factor (538 against 582 `row_ops` on 63 two-summand rows over 121
//! columns, same rank, same answer).  What the dense matrix pays and
//! does not count is the scan of every column of every pivot row, and
//! `rank × |F|` words of storage against the sparse one's non-zeros;
//! that is the cost a structured elimination exists to avoid, and it
//! shows in `wall_ns` and `peak` before it shows in `row_ops`.
//!
//! ## The contract both obey
//!
//! `add_row` reduces the new row against the pivots held so far, and
//! either adopts it as a new pivot (`Independent`), finds it reduces to
//! `0 = 0` (`Dependent`) or to `0 = c ≠ 0` (`Inconsistent`).  `pinned`
//! answers whether the matrix determines one column on its own.  The
//! relation loop calls them in that order after every relation, so an
//! implementation must answer incrementally; a batch method would have
//! to re-solve on every call and is not what this trait is for.

use crate::cryptanalysis::ic_boundary::{IncrementalGauss, RelationSolver, RowStatus};

#[cfg(test)]
fn addmod(a: u64, b: u64, m: u64) -> u64 {
    ((a as u128 + b as u128) % m as u128) as u64
}
fn submod(a: u64, b: u64, m: u64) -> u64 {
    ((a as u128 + m as u128 - b as u128) % m as u128) as u64
}
fn mulmod(a: u64, b: u64, m: u64) -> u64 {
    ((a as u128 * b as u128) % m as u128) as u64
}
fn invmod(a: u64, m: u64) -> Option<u64> {
    // Extended Euclid over i128; `m` is prime, so any non-zero `a` inverts.
    let (mut r0, mut r1) = (m as i128, (a % m) as i128);
    let (mut t0, mut t1) = (0i128, 1i128);
    while r1 != 0 {
        let q = r0 / r1;
        (r0, r1) = (r1, r0 - q * r1);
        (t0, t1) = (t1, t0 - q * t1);
    }
    if r0 != 1 {
        return None;
    }
    Some(((t0 % m as i128 + m as i128) % m as i128) as u64)
}

/// A sparse row: `(column, coefficient)` sorted by column, no zeros.
type Sparse = Vec<(usize, u64)>;

/// `a − f·b`, both sparse and sorted, counting one `row_op` per
/// non-zero touched.
fn sparse_sub_scaled(a: &Sparse, f: u64, b: &Sparse, m: u64, ops: &mut u64) -> Sparse {
    let mut out = Vec::with_capacity(a.len() + b.len());
    let (mut i, mut j) = (0, 0);
    while i < a.len() || j < b.len() {
        match (a.get(i), b.get(j)) {
            (Some(&(ca, va)), Some(&(cb, vb))) if ca == cb => {
                let v = submod(va, mulmod(f, vb, m), m);
                *ops += 1;
                if v != 0 {
                    out.push((ca, v));
                }
                i += 1;
                j += 1;
            }
            (Some(&(ca, va)), Some(&(cb, _))) if ca < cb => {
                out.push((ca, va));
                i += 1;
            }
            (Some(&(ca, va)), None) => {
                out.push((ca, va));
                i += 1;
            }
            (_, Some(&(cb, vb))) => {
                let v = submod(0, mulmod(f, vb, m), m);
                *ops += 1;
                if v != 0 {
                    out.push((cb, v));
                }
                j += 1;
            }
            (None, None) => break,
        }
    }
    out
}

/// Sparse incremental elimination, pivoting on the lightest column.
///
/// Rows are kept sparse and the pivot of a new row is its non-zero
/// column of least global weight — the Markowitz-style choice that
/// keeps fill-in down.  Every multiply-subtract on a stored non-zero is
/// one `row_op`; nothing is charged for the zeros the dense method
/// walks over.  On relation rows with `m` non-zeros in `|F|` columns
/// that is the difference between `O(|F|)` and `O(m)` per reduction
/// step, which is where a real index-calculus linear algebra spends its
/// time and its memory.
pub struct StructuredGauss {
    modulus: u64,
    cols: usize,
    rows: Vec<Sparse>,
    rhs: Vec<u64>,
    pivot_of_row: Vec<usize>,
    row_of_pivot: Vec<Option<usize>>,
    /// Non-zeros per column across stored rows, for the pivot choice.
    weight: Vec<u32>,
    pub row_ops: u64,
    pub dependent: u64,
    pub inconsistent: u64,
    /// Total non-zeros stored: the method's footprint, which the dense
    /// method cannot report because it has none to speak of.
    pub nonzeros: u64,
    pub peak_nonzeros: u64,
}

impl StructuredGauss {
    pub fn new(cols: usize, modulus: u64) -> Self {
        Self {
            modulus,
            cols,
            rows: Vec::new(),
            rhs: Vec::new(),
            pivot_of_row: Vec::new(),
            row_of_pivot: vec![None; cols],
            weight: vec![0; cols],
            row_ops: 0,
            dependent: 0,
            inconsistent: 0,
            nonzeros: 0,
            peak_nonzeros: 0,
        }
    }

    fn note_weight(&mut self, row: &Sparse, delta: i32) {
        for &(c, _) in row {
            let w = &mut self.weight[c];
            *w = (*w as i32 + delta).max(0) as u32;
        }
    }
}

impl RelationSolver for StructuredGauss {
    fn add_row(&mut self, dense: Vec<u64>, mut rhs: u64) -> RowStatus {
        let m = self.modulus;
        debug_assert_eq!(dense.len(), self.cols);
        let mut row: Sparse = dense
            .iter()
            .enumerate()
            .filter(|(_, &v)| v != 0)
            .map(|(c, &v)| (c, v % m))
            .collect();
        // Reduce against every pivot the new row touches.  A sparse row
        // touches few, and the reduction adds only the pivot row's
        // non-zeros, so this is the step the structure pays for.
        loop {
            let hit = row
                .iter()
                .find_map(|&(c, f)| self.row_of_pivot[c].map(|i| (i, f)));
            let Some((i, f)) = hit else { break };
            let pivot_row = self.rows[i].clone();
            row = sparse_sub_scaled(&row, f, &pivot_row, m, &mut self.row_ops);
            rhs = submod(rhs, mulmod(f, self.rhs[i], m), m);
            self.row_ops += 1;
        }
        if row.is_empty() {
            if rhs == 0 {
                self.dependent += 1;
                return RowStatus::Dependent;
            }
            self.inconsistent += 1;
            return RowStatus::Inconsistent;
        }
        // Pivot on the lightest column the row touches.
        let (pc, pv) = row
            .iter()
            .copied()
            .min_by_key(|&(c, _)| (self.weight[c], c))
            .expect("non-empty row");
        let inv = invmod(pv, m).expect("prime modulus");
        for (_, v) in row.iter_mut() {
            *v = mulmod(*v, inv, m);
            self.row_ops += 1;
        }
        rhs = mulmod(rhs, inv, m);
        self.row_ops += 1;
        // Eliminate the new pivot column from every stored row that
        // holds it; only those rows are touched.
        for i in 0..self.rows.len() {
            let f = match self.rows[i].binary_search_by_key(&pc, |&(c, _)| c) {
                Ok(k) => self.rows[i][k].1,
                Err(_) => continue,
            };
            let before = self.rows[i].clone();
            let after = sparse_sub_scaled(&before, f, &row, m, &mut self.row_ops);
            self.rhs[i] = submod(self.rhs[i], mulmod(f, rhs, m), m);
            self.row_ops += 1;
            self.nonzeros = self.nonzeros - before.len() as u64 + after.len() as u64;
            self.note_weight(&before, -1);
            self.note_weight(&after, 1);
            self.rows[i] = after;
        }
        self.row_of_pivot[pc] = Some(self.rows.len());
        self.pivot_of_row.push(pc);
        self.nonzeros += row.len() as u64;
        self.note_weight(&row, 1);
        self.peak_nonzeros = self.peak_nonzeros.max(self.nonzeros);
        self.rows.push(row);
        self.rhs.push(rhs);
        RowStatus::Independent
    }

    fn pinned(&self, col: usize) -> Option<u64> {
        let i = self.row_of_pivot[col]?;
        let row = &self.rows[i];
        (row.len() == 1 && row[0].0 == col).then_some(self.rhs[i])
    }

    fn rank(&self) -> usize {
        self.rows.len()
    }

    fn dependent(&self) -> u64 {
        self.dependent
    }

    fn work(&self) -> (u64, &'static str) {
        (self.row_ops, "row_ops")
    }
}

/// The matrices the framework knows, by name.
pub const MATRIX_NAMES: &[(&str, &str)] = &[
    (
        "incremental-gauss",
        "dense reduced row echelon maintained as rows arrive, pivot on the leftmost non-zero; one row_op per non-zero multiply-subtract",
    ),
    (
        "structured-gauss",
        "sparse reduced row echelon maintained as rows arrive, pivot on the lightest column; one row_op per non-zero multiply-subtract, so the two are comparable",
    ),
];

/// Build one by name, for a matrix with `cols` columns over `Z/rZ`.
pub fn matrix_by_name(
    name: &str,
    cols: usize,
    modulus: u64,
) -> Result<Box<dyn RelationSolver>, String> {
    match name {
        "incremental-gauss" => Ok(Box::new(IncrementalGauss::new(cols, modulus))),
        "structured-gauss" => Ok(Box::new(StructuredGauss::new(cols, modulus))),
        other => Err(format!(
            "unknown relation matrix `{other}`; known: {}",
            MATRIX_NAMES
                .iter()
                .map(|(n, _)| *n)
                .collect::<Vec<_>>()
                .join(", ")
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::rngs::StdRng;
    use rand::{Rng, SeedableRng};

    /// **Both matrices must pin the same unknown to the same value on
    /// the same rows, at the same moment.**  A second implementation
    /// that agreed on the answer but pinned it a row later would change
    /// every trial count downstream while looking correct.
    #[test]
    fn structured_and_dense_agree_row_by_row() {
        let modulus = 1_000_003u64;
        let cols = 12usize;
        let target = cols - 1;
        let mut rng = StdRng::seed_from_u64(20260922);
        // A planted solution, so every row is consistent and the value
        // pinned can be checked against something.
        let x: Vec<u64> = (0..cols).map(|_| rng.gen_range(0..modulus)).collect();
        let mut dense = IncrementalGauss::new(cols, modulus);
        let mut sparse = StructuredGauss::new(cols, modulus);
        let mut pinned_at = None;
        for row_no in 0..40 {
            // Sparse relation rows: two or three non-zeros plus the target.
            let mut row = vec![0u64; cols];
            for _ in 0..rng.gen_range(2..=3) {
                row[rng.gen_range(0..cols)] = rng.gen_range(1..modulus);
            }
            row[target] = rng.gen_range(1..modulus);
            let rhs = row.iter().zip(&x).fold(0u64, |acc, (&a, &b)| {
                addmod(acc, mulmod(a, b, modulus), modulus)
            });
            let a = dense.add_row(row.clone(), rhs);
            let b = sparse.add_row(row, rhs);
            assert_eq!(
                std::mem::discriminant(&a),
                std::mem::discriminant(&b),
                "row {row_no}: the two matrices classified it differently"
            );
            assert_eq!(
                dense.rank(),
                RelationSolver::rank(&sparse),
                "row {row_no}: rank"
            );
            let pd = dense.pinned(target);
            let ps = sparse.pinned(target);
            assert_eq!(pd, ps, "row {row_no}: pinned value");
            if let Some(v) = ps {
                assert_eq!(v, x[target], "pinned the wrong value");
                pinned_at.get_or_insert(row_no);
            }
        }
        assert!(
            pinned_at.is_some(),
            "forty rows on twelve columns must pin the target"
        );
        // And the structure must have bought something: fewer
        // multiply-subtracts than the dense walk over every column.
        assert!(
            sparse.row_ops < dense.row_ops,
            "structured {} vs dense {} row_ops",
            sparse.row_ops,
            dense.row_ops
        );
    }

    /// An inconsistent row must be reported, not absorbed.
    #[test]
    fn an_inconsistent_row_is_reported() {
        let modulus = 101u64;
        let mut m = StructuredGauss::new(3, modulus);
        assert!(matches!(
            m.add_row(vec![1, 0, 0], 5),
            RowStatus::Independent
        ));
        assert!(matches!(m.add_row(vec![1, 0, 0], 5), RowStatus::Dependent));
        assert!(matches!(
            m.add_row(vec![2, 0, 0], 11),
            RowStatus::Inconsistent
        ));
        assert_eq!(m.pinned(0), Some(5));
    }

    #[test]
    fn the_registry_resolves_every_matrix_it_advertises() {
        for (name, _) in MATRIX_NAMES {
            assert!(matrix_by_name(name, 4, 101).is_ok(), "{name}");
        }
        assert!(matrix_by_name("wiedemann", 4, 101).is_err());
    }
}
