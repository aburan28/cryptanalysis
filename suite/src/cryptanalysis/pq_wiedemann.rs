//! # Sequential Wiedemann sparse-matrix solver over `Z/N`.
//!
//! The iterative algorithm for solving giant sparse linear systems
//! used by every production index-calculus pipeline (NFS, FFS,
//! ECDLP-by-IC).  Where dense Gaussian elimination is `O(rows ·
//! cols²)` and ignores sparsity, Wiedemann is `O(rows · max_row_weight
//! · cols)` — for the bilinear PQ relation matrix (each row has at
//! most `n + 1` non-zeros where `n` is the decomposition size), that
//! is `O(n · rows · cols)` ≈ a few-thousand-times speedup at any
//! production parameter set.
//!
//! ## Algorithm
//!
//! For solving `A x = b` with `A` square (or `M^T M x = M^T b` when
//! `M` is not square — the **normal equations** trick):
//!
//! 1. Pick a random projection vector `u` in `(Z/N)^n`.
//! 2. Compute the **Krylov sequence** `s_i = u^T A^i b` for
//!    `i = 0, …, 2n - 1` — each step is one sparse mat-vec.
//! 3. Run **Berlekamp–Massey** on the scalar sequence to recover
//!    the minimum polynomial `p(λ) = p_0 + p_1 λ + … + p_d λ^d`
//!    that satisfies `p(A) b = 0` projected through `u`.
//! 4. From `p(A) b = 0`,
//!    `−p_0 b = p_1 A b + p_2 A² b + … + p_d A^d b
//!          = A (p_1 b + p_2 A b + … + p_d A^{d-1} b)`,
//!    so `x = −p_0^{-1} · (p_1 b + p_2 A b + … + p_d A^{d-1} b)`.
//!
//! The whole algorithm needs only **sparse mat-vec products** —
//! exactly what the relation matrix's structure makes cheap.
//!
//! ## Sequential vs. block variants
//!
//! - **Sequential Wiedemann** (Wiedemann 1986) — what this module
//!   ships.  Single random projection `u`, scalar Berlekamp–Massey.
//!   Pedagogically clean; production scales it via the block variant.
//!
//! - **Block Wiedemann** (Coppersmith 1994, *Math. Comp.*) — uses
//!   `k > 1` random vectors `u_1, …, u_k`, builds a *matrix* sequence
//!   of `k × k` blocks, runs **matrix Berlekamp–Massey** to recover a
//!   matrix polynomial.  Trades one big sequential pass for `k`
//!   parallelisable passes; massive win on multi-core hardware (and
//!   the standard choice for kilobit RSA / FFS / NFS).
//!
//! - **Block Lanczos** (Montgomery 1995, ANTS) — the symmetric analog
//!   working with `M^T M`.  Equivalent depth, simpler post-processing
//!   over `F_2` (no matrix BM); historically dominant for QS and
//!   `GF(2)` SNFS factorisations.
//!
//! For an `F_p` (prime modulus) PQ relation matrix the block
//! variants give wall-clock wins but no new algorithmic capability;
//! the sequential version exercises the same data structure
//! (sparse mat-vec) and the same correctness invariant (BM recovers
//! the action of `A` on a Krylov subspace).
//!
//! ## References
//!
//! - **D. H. Wiedemann**, *Solving sparse linear equations over
//!   finite fields*, IEEE Trans. Inf. Theory 32 (1986).
//! - **D. Coppersmith**, *Solving homogeneous linear equations over
//!   GF(2) via block Wiedemann algorithm*, Math. Comp. 62 (1994).
//! - **P. L. Montgomery**, *A block Lanczos algorithm for finding
//!   dependencies over GF(2)*, EUROCRYPT 1995.
//! - **E. R. Berlekamp**, *Algebraic Coding Theory*, McGraw-Hill 1968.
//! - **J. L. Massey**, *Shift-register synthesis and BCH decoding*,
//!   IEEE Trans. Inf. Theory 15 (1969).

use crate::cryptanalysis::pq_sparse_la::SparseRow;
use crate::utils::mod_inverse;
use num_bigint::BigUint;
use num_traits::Zero;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};

// ── Sparse mat-vec primitives ──────────────────────────────────────

/// Compute `M · v mod n` where `M` is sparse-row-indexed and `v` is
/// dense.  Result length = `n_rows`.
fn mat_vec(m: &[SparseRow], v: &[BigUint], n: &BigUint) -> Vec<BigUint> {
    m.iter()
        .map(|row| {
            let mut acc = BigUint::zero();
            for (col, val) in row.entries.iter() {
                acc = (&acc + &(val * &v[*col])) % n;
            }
            acc
        })
        .collect()
}

/// Compute `M^T · v mod n`.  Result length = `n_cols`.
fn mat_t_vec(m: &[SparseRow], v: &[BigUint], n_cols: usize, n: &BigUint) -> Vec<BigUint> {
    let mut out = vec![BigUint::zero(); n_cols];
    for (i, row) in m.iter().enumerate() {
        for (col, val) in row.entries.iter() {
            out[*col] = (&out[*col] + &(val * &v[i])) % n;
        }
    }
    out
}

/// Inner product `⟨a, b⟩ mod n`.
fn dot(a: &[BigUint], b: &[BigUint], n: &BigUint) -> BigUint {
    let mut acc = BigUint::zero();
    for (x, y) in a.iter().zip(b) {
        acc = (&acc + &(x * y)) % n;
    }
    acc
}

/// Compute `M^T M · v mod n`.  Avoids materialising the (potentially
/// dense) Gram matrix `M^T M`.
fn ata_vec(m: &[SparseRow], v: &[BigUint], n_cols: usize, n: &BigUint) -> Vec<BigUint> {
    let mv = mat_vec(m, v, n);
    mat_t_vec(m, &mv, n_cols, n)
}

// ── Berlekamp-Massey ────────────────────────────────────────────────

/// **Berlekamp-Massey** over `Z/n` (with `n` prime — or more
/// generally, every coefficient encountered being invertible mod `n`).
///
/// Given a sequence `s_0, s_1, …, s_{L-1}`, returns the connection
/// polynomial `c(x) = c_0 + c_1 x + … + c_L x^L` of the shortest
/// LFSR that generates `(s_i)`, satisfying
///
/// ```text
///     s_i = − (c_1 s_{i-1} + c_2 s_{i-2} + … + c_L s_{i-L})   for i ≥ L,
/// ```
///
/// with `c_0 = 1`.  Returns `None` if a non-invertible discrepancy
/// arises (indicating either bad luck on the random projection or a
/// non-prime modulus where `Z/n` has zero divisors).
pub fn berlekamp_massey(seq: &[BigUint], n: &BigUint) -> Option<Vec<BigUint>> {
    let mut c: Vec<BigUint> = vec![BigUint::from(1u32)];
    let mut b: Vec<BigUint> = vec![BigUint::from(1u32)];
    let mut l: usize = 0;
    let mut shift: usize = 1;
    let mut delta_b: BigUint = BigUint::from(1u32);
    for (i, s_i) in seq.iter().enumerate() {
        // Discrepancy: delta = s_i + sum_{j=1..l} c_j · s_{i-j}.
        let mut delta = s_i.clone();
        for j in 1..=l {
            if j < c.len() && j <= i {
                delta = (&delta + &(&c[j] * &seq[i - j])) % n;
            }
        }
        if delta.is_zero() {
            shift += 1;
            continue;
        }
        // coef = delta * delta_b^{-1} mod n.
        let delta_b_inv = mod_inverse(&delta_b, n)?;
        let coef = (&delta * &delta_b_inv) % n;
        // New c = old c − coef · x^shift · b.
        let needed_len = b.len() + shift;
        if c.len() < needed_len {
            c.resize(needed_len, BigUint::zero());
        }
        let t = c.clone();
        for j in 0..b.len() {
            let target = j + shift;
            let term = (&coef * &b[j]) % n;
            c[target] = (&c[target] + n - &term) % n;
        }
        if 2 * l <= i {
            l = i + 1 - l;
            b = t;
            delta_b = delta;
            shift = 1;
        } else {
            shift += 1;
        }
    }
    Some(c)
}

// ── Wiedemann solve ────────────────────────────────────────────────

/// **Solve `M x ≡ b (mod n)`** via sequential Wiedemann.
///
/// `m` is a sparse matrix with `n_cols` columns (the RHS `b` has
/// length = number of rows).  Returns `Some(x)` on success, `None` if
/// the random projection landed on a degenerate Krylov sequence (try
/// a different seed).
///
/// When `M` is non-square or singular, we apply the normal equations:
/// solve `M^T M x = M^T b` instead, which has a unique solution iff
/// `M` has full column rank.  The relation matrix from PQ is always
/// at least square (we over-collect by `target_extra ≥ 1`), so this
/// is a reasonable fallback.
///
/// **Failure modes worth knowing**:
/// - The minimum polynomial recovered by BM has `c_0 = 0` ⇒ `A` is
///   singular on the projection. Return `None`; the caller should
///   either retry with a different seed or add more relations.
/// - Non-invertible discrepancy in BM ⇒ the modulus isn't prime
///   *and* an unlucky element occurred. Return `None`.
pub fn wiedemann_solve(
    m: &[SparseRow],
    b: &[BigUint],
    n_cols: usize,
    n: &BigUint,
    seed: u64,
) -> Option<Vec<BigUint>> {
    assert_eq!(m.len(), b.len(), "M and b must have matching row counts");
    let n_rows = m.len();
    let mut rng = StdRng::seed_from_u64(seed);

    // For square invertible `M` we can run Wiedemann directly on
    // `M` and `b`; for the rectangular case (`n_rows ≠ n_cols`) we
    // fall back to the normal equations `(M^T M) x = M^T b`.  The
    // direct route avoids the cost of doubling the min-poly degree
    // and is what production index-calculus implementations use
    // when they pad / oversample to exactly square (or block-square).
    let square = n_rows == n_cols;

    // Working "vector" v_0 and matrix-vector op A.
    let (v0, apply_a, target_dim) = if square {
        // A = M, v_0 = b.
        let apply: Box<dyn Fn(&[BigUint]) -> Vec<BigUint>> =
            Box::new(|v: &[BigUint]| mat_vec(m, v, n));
        (b.to_vec(), apply, n_cols)
    } else {
        // A = M^T M, v_0 = M^T b.
        let c = mat_t_vec(m, b, n_cols, n);
        let apply: Box<dyn Fn(&[BigUint]) -> Vec<BigUint>> =
            Box::new(|v: &[BigUint]| ata_vec(m, v, n_cols, n));
        (c, apply, n_cols)
    };

    // Random projection vector u.
    let mut u = vec![BigUint::zero(); target_dim];
    for slot in u.iter_mut() {
        let mut buf = [0u8; 32];
        rng.fill(&mut buf);
        *slot = BigUint::from_bytes_le(&buf) % n;
    }

    // Build the Krylov scalar sequence s_i = u^T A^i v_0.
    // Sequence length must be ≥ 2·deg(min poly).  Min poly has
    // degree ≤ n_cols (square A) or ≤ 2·n_cols (M^T M); we use
    // `2·n_cols + 2` either way for safety.
    let seq_len = 2 * n_cols + 2;
    let mut seq = Vec::with_capacity(seq_len);
    let mut current = v0.clone();
    for _ in 0..seq_len {
        seq.push(dot(&u, &current, n));
        current = apply_a(&current);
    }

    // BM recovery.  The BM connection polynomial Λ(D) is the
    // **reciprocal** of the matrix min polynomial p(λ): if BM returns
    // `Λ = (Λ_0, Λ_1, …, Λ_L)` then the min poly of `A` on `v_0` is
    // `p(λ) = Λ_L · λ^0 + Λ_{L-1} · λ^1 + … + Λ_0 · λ^L`, equivalently
    // `p_j = Λ_{L-j}`.
    let lambda = berlekamp_massey(&seq, n)?;
    if lambda.is_empty() {
        return None;
    }
    // Trim trailing zeros (BM may produce a zero-padded polynomial).
    let mut lambda = lambda;
    while lambda.len() > 1 && lambda.last().map(|c| c.is_zero()).unwrap_or(false) {
        lambda.pop();
    }
    // p[j] = lambda[L - j], so p has the same coefficients reversed.
    let p_poly: Vec<BigUint> = lambda.iter().rev().cloned().collect();
    if p_poly.is_empty() || p_poly[0].is_zero() {
        return None;
    }

    // p(A) v_0 = 0:  Σ_{j=0..L} p_j A^j v_0 = 0.
    // ⇒  p_0 v_0 = -A · Σ_{j=1..L} p_j A^{j-1} v_0
    // ⇒  x = -p_0^{-1} · Σ_{j=1..L} p_j A^{j-1} v_0  satisfies A x = v_0.
    let mut x = vec![BigUint::zero(); target_dim];
    let mut a_pow_v = v0.clone();
    for i in 1..p_poly.len() {
        for (xj, vj) in x.iter_mut().zip(a_pow_v.iter()) {
            *xj = (&*xj + &(&p_poly[i] * vj)) % n;
        }
        if i < p_poly.len() - 1 {
            a_pow_v = apply_a(&a_pow_v);
        }
    }
    let p0_inv = mod_inverse(&p_poly[0], n)?;
    let neg_p0_inv = (n - (&p0_inv % n)) % n;
    for v in x.iter_mut() {
        *v = (&*v * &neg_p0_inv) % n;
    }

    // Verify against the ORIGINAL M (not A!) to catch min-poly
    // ambiguity: BM finds a polynomial whose projection onto `u`
    // annihilates `v_0`, which may be a proper divisor of A's true
    // min poly on v_0.  Verification by direct check is cheap.
    let mx = mat_vec(m, &x, n);
    if mx == b {
        Some(x)
    } else {
        None
    }
}

// ── Tests ──────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::ec_index_calculus::gaussian_eliminate_mod_n;
    use crate::cryptanalysis::pq_sparse_la::SparseRow;
    use num_traits::{One, Zero};

    /// **BM round-trip**: given a known LFSR sequence, recover its
    /// connection polynomial.
    ///
    /// LFSR: `s_i = 2 s_{i-1} + 3 s_{i-2} mod 13` with `s_0 = 1, s_1 = 1`.
    /// Connection polynomial (with our sign convention): `c_0 = 1,
    /// c_1 = -2, c_2 = -3` ⇒ `(1, 11, 10)` mod 13.
    #[test]
    fn bm_lfsr_round_trip() {
        let n = BigUint::from(13u32);
        let mut s = vec![BigUint::from(1u32), BigUint::from(1u32)];
        for i in 2..20 {
            let v = (&BigUint::from(2u32) * &s[i - 1] + &BigUint::from(3u32) * &s[i - 2]) % &n;
            s.push(v);
        }
        let c = berlekamp_massey(&s, &n).expect("BM should succeed");
        assert!(c.len() >= 3, "expected degree ≥ 2 poly, got {:?}", c);
        // Check recurrence: c_0 s_i + c_1 s_{i-1} + c_2 s_{i-2} = 0 for i ≥ 2.
        let zero = BigUint::zero();
        for i in 2..s.len() {
            let mut acc = BigUint::zero();
            for (j, c_j) in c.iter().enumerate().take(3) {
                if j <= i {
                    acc = (&acc + &(c_j * &s[i - j])) % &n;
                }
            }
            assert_eq!(acc, zero, "recurrence broken at i = {}", i);
        }
    }

    /// **Wiedemann recovers the solution of a 2×2 prime-modulus system.**
    /// System:
    ///   2x + 3y ≡ 8 (mod 11)
    ///   x + y ≡ 4 (mod 11)
    /// Unique solution: x = 4, y = 0.
    #[test]
    fn wiedemann_2x2_system() {
        let n = BigUint::from(11u32);
        let m = vec![
            SparseRow::from_entries(
                vec![(0, BigUint::from(2u32)), (1, BigUint::from(3u32))],
                BigUint::from(8u32),
            ),
            SparseRow::from_entries(
                vec![(0, BigUint::one()), (1, BigUint::one())],
                BigUint::from(4u32),
            ),
        ];
        let b: Vec<BigUint> = m.iter().map(|r| r.rhs.clone()).collect();
        // Try multiple seeds; Wiedemann can fail with bad random vector choices.
        let mut x_found = None;
        for seed in 0u64..20 {
            if let Some(x) = wiedemann_solve(&m, &b, 2, &n, seed) {
                x_found = Some(x);
                break;
            }
        }
        let x = x_found.expect("at least one seed should succeed");
        assert_eq!(x, vec![BigUint::from(4u32), BigUint::from(0u32)]);
    }

    /// **Wiedemann agrees with dense Gaussian on a random 4×4 prime-mod system.**
    #[test]
    fn wiedemann_agrees_with_dense_gaussian() {
        let n = BigUint::from(17u32);
        let true_sol = vec![
            BigUint::from(1u32),
            BigUint::from(2u32),
            BigUint::from(3u32),
            BigUint::from(4u32),
        ];
        // M is a small dense-ish matrix with known solution.
        let raw = vec![
            vec![(0usize, 1u32), (1, 2)],
            vec![(0, 3), (1, 1), (3, 1)],
            vec![(2, 1)],
            vec![(1, 1), (2, 1), (3, 2)],
        ];
        let mut sparse_m: Vec<SparseRow> = Vec::new();
        let mut b: Vec<BigUint> = Vec::new();
        let mut dense_m: Vec<Vec<BigUint>> = Vec::new();
        for row in &raw {
            let mut rhs = BigUint::zero();
            let mut dense_row = vec![BigUint::zero(); 4];
            let mut entries: Vec<(usize, BigUint)> = Vec::new();
            for &(c, v) in row {
                let bv = BigUint::from(v);
                rhs = (&rhs + &(&bv * &true_sol[c])) % &n;
                dense_row[c] = bv.clone();
                entries.push((c, bv));
            }
            sparse_m.push(SparseRow::from_entries(entries, rhs.clone()));
            b.push(rhs);
            dense_m.push(dense_row);
        }
        // Dense reference.
        let mut dense_m_clone = dense_m.clone();
        let mut b_clone = b.clone();
        let dense_x = gaussian_eliminate_mod_n(&mut dense_m_clone, &mut b_clone, &n).unwrap();
        // Try multiple seeds for Wiedemann.
        let mut wied_x = None;
        for seed in 0u64..20 {
            if let Some(x) = wiedemann_solve(&sparse_m, &b, 4, &n, seed) {
                wied_x = Some(x);
                break;
            }
        }
        let wied_x = wied_x.expect("Wiedemann should succeed on at least one seed");
        assert_eq!(wied_x, dense_x, "Wiedemann and dense should agree");
        assert_eq!(wied_x, true_sol);
    }

    /// **Determinism for fixed seed**: same input + same seed → same output.
    #[test]
    fn wiedemann_deterministic_for_fixed_seed() {
        let n = BigUint::from(11u32);
        let m = vec![SparseRow::from_entries(
            vec![(0, BigUint::from(3u32))],
            BigUint::from(7u32),
        )];
        let b: Vec<BigUint> = m.iter().map(|r| r.rhs.clone()).collect();
        let x1 = wiedemann_solve(&m, &b, 1, &n, 42);
        let x2 = wiedemann_solve(&m, &b, 1, &n, 42);
        assert_eq!(x1, x2);
    }

    /// **Singular system** → either `None` (BM finds `c_0 = 0`) or an
    /// incorrect verification (`M x ≠ b`).  Either way the function
    /// must not panic.
    #[test]
    fn wiedemann_singular_system_does_not_panic() {
        let n = BigUint::from(7u32);
        // Singular M: two identical rows.  Solution exists iff RHS
        // agrees on both — here it does so the system is consistent
        // but rank-deficient.
        let m = vec![
            SparseRow::from_entries(vec![(0, BigUint::one())], BigUint::from(3u32)),
            SparseRow::from_entries(vec![(0, BigUint::one())], BigUint::from(3u32)),
        ];
        let b: Vec<BigUint> = m.iter().map(|r| r.rhs.clone()).collect();
        for seed in 0u64..5 {
            let _ = wiedemann_solve(&m, &b, 1, &n, seed); // must not panic
        }
    }

    /// **Larger 6×6 system over a 31-bit prime**: cross-check
    /// Wiedemann vs dense Gaussian.
    #[test]
    fn wiedemann_6x6_large_prime() {
        // Pick a random invertible matrix over Z/p for p = 1_000_003.
        let n = BigUint::from(1_000_003u32);
        let true_sol = vec![
            BigUint::from(11u32),
            BigUint::from(22u32),
            BigUint::from(33u32),
            BigUint::from(44u32),
            BigUint::from(55u32),
            BigUint::from(66u32),
        ];
        // Triangular-ish sparse system.
        let raw = vec![
            vec![(0usize, 1u32), (3, 5)],
            vec![(1, 1), (4, 2)],
            vec![(2, 1), (5, 3)],
            vec![(3, 7)],
            vec![(4, 11)],
            vec![(5, 13)],
        ];
        let mut sparse_m: Vec<SparseRow> = Vec::new();
        let mut b: Vec<BigUint> = Vec::new();
        let mut dense_m: Vec<Vec<BigUint>> = Vec::new();
        for row in &raw {
            let mut rhs = BigUint::zero();
            let mut dense_row = vec![BigUint::zero(); 6];
            let mut entries: Vec<(usize, BigUint)> = Vec::new();
            for &(c, v) in row {
                let bv = BigUint::from(v);
                rhs = (&rhs + &(&bv * &true_sol[c])) % &n;
                dense_row[c] = bv.clone();
                entries.push((c, bv));
            }
            sparse_m.push(SparseRow::from_entries(entries, rhs.clone()));
            b.push(rhs);
            dense_m.push(dense_row);
        }
        let mut dense_m_clone = dense_m.clone();
        let mut b_clone = b.clone();
        let dense_x = gaussian_eliminate_mod_n(&mut dense_m_clone, &mut b_clone, &n).unwrap();
        let mut wied_x = None;
        for seed in 0u64..30 {
            if let Some(x) = wiedemann_solve(&sparse_m, &b, 6, &n, seed) {
                wied_x = Some(x);
                break;
            }
        }
        let wied_x = wied_x.expect("Wiedemann should succeed on at least one seed");
        assert_eq!(wied_x, dense_x);
        assert_eq!(wied_x, true_sol);
    }
}
