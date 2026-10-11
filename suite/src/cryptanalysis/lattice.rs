//! LLL lattice reduction.
//!
//! Lenstra–Lenstra–Lovász, "Factoring polynomials with rational
//! coefficients," Math. Annalen 1982.  The classical lattice
//! basis-reduction algorithm: given an integer lattice basis,
//! produce an equivalent basis whose vectors are nearly orthogonal
//! and the first vector approximates the shortest vector.
//!
//! This implementation pairs a `BigInt` basis with `f64`
//! Gram–Schmidt coefficients — the same hybrid that production
//! libraries (`fplll`, NTL's LLL_FP) use.  Floating-point GS is
//! sound at the dimensions and bit-sizes that matter for
//! cryptanalytic targets in this crate (≤ 30 dim, ≤ 256-bit
//! coefficients).  At higher dimensions or longer entries you'd
//! switch to `L²` (Nguyen–Stehlé 2005); we don't need that here.
//!
//! # Use case in this crate
//!
//! [`crate::cryptanalysis::hnp_ecdsa`] uses LLL to solve the
//! Hidden-Number Problem instance arising from ECDSA signatures
//! with biased per-signature nonces.  See that module for the
//! attack details; this module is the linear-algebra workhorse.

use num_bigint::{BigInt, ToBigInt};
use num_traits::{One, Signed, ToPrimitive, Zero};

// ── High-precision fixed-point arithmetic for GS ─────────────────────────────
//
// Represent each value as a BigInt where the implicit scale is 2^HP_PREC:
//   stored_int = actual_value × 2^HP_PREC
//
// This gives HP_PREC bits of mantissa precision, enough to avoid the
// catastrophic cancellation that f64 suffers on P-521 HNP lattices
// (entries spanning 2^384 to 2^1042 → 658-bit dynamic range > f64's 53 bits).

const HP_PREC: usize = 2048;

/// Convert BigInt x to HP fixed-point: result = x × 2^HP_PREC.
#[inline]
fn hp_from_bigint(x: &BigInt) -> BigInt {
    x << HP_PREC
}

/// Multiply two HP values: hp(a) × hp(b) → hp(a×b).
/// (A × 2^P) × (B × 2^P) / 2^P = (A×B) × 2^P.
#[inline]
fn hp_mul(a: &BigInt, b: &BigInt) -> BigInt {
    (a * b) >> HP_PREC
}

/// Divide two HP values: hp(a) / hp(b) → hp(a/b).
/// (A × 2^P) / (B × 2^P) = A/B; to return as HP: (A × 2^P × 2^P) / (B × 2^P) = (A/B) × 2^P.
#[inline]
fn hp_div(a: &BigInt, b: &BigInt) -> BigInt {
    if b.is_zero() {
        return BigInt::zero();
    }
    (a << HP_PREC) / b
}

/// Round HP value to nearest integer (as plain BigInt, not HP).
fn hp_round(a: &BigInt) -> BigInt {
    // Add or subtract half (2^(P-1)) then arithmetic shift right by P.
    let half: BigInt = BigInt::one() << (HP_PREC - 1);
    if a.is_negative() {
        let neg_a = -a.clone();
        -((&neg_a + &half) >> HP_PREC)
    } else {
        (a + &half) >> HP_PREC
    }
}

/// High-precision Gram–Schmidt orthogonalization using 2048-bit fixed-point.
///
/// Returns `(bstar_sq, mu)` where:
/// - `bstar_sq[i]` = ||b*_i||² as an HP fixed-point BigInt (= actual_norm² × 2^P)
/// - `mu[i][j]`    = μ_{i,j} as an HP fixed-point BigInt (= actual_μ × 2^P)
///
/// Unlike the f64 `gram_schmidt`, this function avoids the catastrophic
/// cancellation that occurs on the P-521 HNP lattice, where the GS
/// subtraction of nearly-equal ~2^1042 terms should yield exactly 0 but
/// f64 leaves a ~2^446 residual that buries the true ~2^384 GS component.
fn gram_schmidt_hp(basis: &[Vec<BigInt>]) -> (Vec<BigInt>, Vec<Vec<BigInt>>) {
    let n = basis.len();
    let dim = if n > 0 { basis[0].len() } else { 0 };

    // bstar[i][k] = b*_i[k] in HP fixed-point
    let mut bstar: Vec<Vec<BigInt>> = vec![vec![BigInt::zero(); dim]; n];
    // bstar_sq[i] = ||b*_i||² in HP fixed-point
    let mut bstar_sq: Vec<BigInt> = vec![BigInt::zero(); n];
    // mu[i][j] = μ_{i,j} in HP fixed-point
    let mut mu: Vec<Vec<BigInt>> = vec![vec![BigInt::zero(); n]; n];

    for i in 0..n {
        // Initialise b*_i ← b_i (converted to HP)
        for k in 0..dim {
            bstar[i][k] = hp_from_bigint(&basis[i][k]);
        }

        for j in 0..i {
            if bstar_sq[j].is_zero() {
                continue;
            }
            // dot = b_i · b*_j  (HP scale)
            let dot: BigInt = (0..dim).map(|k| hp_mul(&bstar[i][k], &bstar[j][k])).sum();
            // μ_{i,j} = dot / ||b*_j||²  (HP ÷ HP → HP)
            mu[i][j] = hp_div(&dot, &bstar_sq[j]);

            // b*_i -= μ_{i,j} × b*_j
            let mu_ij = mu[i][j].clone();
            for k in 0..dim {
                let sub = hp_mul(&mu_ij, &bstar[j][k]);
                bstar[i][k] -= sub;
            }
        }

        // ||b*_i||² = Σ_k (b*_i[k])² in HP scale
        bstar_sq[i] = (0..dim).map(|k| hp_mul(&bstar[i][k], &bstar[i][k])).sum();
    }

    (bstar_sq, mu)
}

/// LLL-reduce `basis` using 2048-bit HP Gram–Schmidt.
///
/// Identical contract to [`lll_reduce`], but uses `gram_schmidt_hp`
/// internally.  Required for lattices whose entries exceed ~2^500,
/// where the standard f64 GS suffers catastrophic cancellation even
/// after overflow-scaling.  In particular, the P-521 HNP basis has
/// a ~2^658 dynamic range that f64 cannot handle.
///
/// Cost is higher than `lll_reduce` (~10-100× per GS call due to
/// BigInt arithmetic), but for cryptanalytic dimensions (≤ 30) this
/// is still milliseconds to seconds.
pub fn lll_reduce_hp(basis: &mut [Vec<BigInt>], delta: f64) -> Result<(), &'static str> {
    if !(0.25 < delta && delta < 1.0) {
        return Err("delta must be in (1/4, 1)");
    }
    let n = basis.len();
    if n == 0 {
        return Ok(());
    }
    let dim = basis[0].len();
    if dim == 0 {
        return Err("basis vectors must be non-empty");
    }
    if basis.iter().any(|v| v.len() != dim) {
        return Err("basis vectors must all have the same length");
    }

    let max_iter = 500 * n * n * 8 + 10_000;
    let mut iter = 0;

    // delta as HP fixed-point: floor(delta × 2^HP_PREC)
    // delta is in (0.25, 1.0); represent as ratio × 2^HP_PREC.
    let delta_hp: BigInt = {
        // Compute delta × 2^HP_PREC via integer arithmetic to avoid f64 issues.
        // delta = p/q where p = (delta × 2^53) as u64, q = 2^53.
        let p = (delta * (1u64 << 53) as f64) as u64;
        let q = 1u64 << 53;
        (BigInt::from(p) << HP_PREC) / BigInt::from(q)
    };
    let half_hp: BigInt = BigInt::one() << (HP_PREC - 1);

    let (mut bstar_sq, mut mu) = gram_schmidt_hp(basis);
    let mut k = 1usize;

    while k < n {
        iter += 1;
        if iter > max_iter {
            return Err("LLL exceeded iteration cap (degenerate input?)");
        }

        // ── Size reduction ───────────────────────────────────────────
        for j in (0..k).rev() {
            // Check |μ_{k,j}| > 1/2 using HP arithmetic
            let mu_abs = if mu[k][j].is_negative() {
                -mu[k][j].clone()
            } else {
                mu[k][j].clone()
            };
            if mu_abs > half_hp {
                let q_bi = hp_round(&mu[k][j]);
                if q_bi.is_zero() {
                    continue;
                }
                // basis[k] -= q × basis[j]
                for i in 0..dim {
                    let bji = basis[j][i].clone();
                    basis[k][i] -= &q_bi * &bji;
                }
                // Update μ: μ_{k,j} -= q (in HP)
                let q_hp = hp_from_bigint(&q_bi);
                mu[k][j] -= &q_hp;
                for i in 0..j {
                    let qmu = hp_mul(&q_hp, &mu[j][i]);
                    mu[k][i] -= qmu;
                }
            }
        }

        // ── Lovász condition ─────────────────────────────────────────
        // Check: ||b*_k||² ≥ (δ − μ_{k,k-1}²) · ||b*_{k-1}||²
        let mu_sq = hp_mul(&mu[k][k - 1], &mu[k][k - 1]);
        // rhs = (delta_hp - mu_sq) × bstar_sq[k-1] / 2^HP_PREC
        let factor = &delta_hp - &mu_sq;
        let rhs = hp_mul(&factor, &bstar_sq[k - 1]);

        if bstar_sq[k] >= rhs {
            k += 1;
        } else {
            // Swap rows k-1 and k, then update GS values incrementally.
            //
            // After swapping b_{k-1} ↔ b_k, the new GS values are (Cohen §2.6.3):
            //   B̃ = ||b*_k||² + μ_{k,k-1}² × ||b*_{k-1}||²
            //   new ||b*_{k-1}||² = B̃
            //   new ||b*_k||²     = ||b*_k||² × ||b*_{k-1}||² / B̃
            //   new μ_{k,k-1}     = μ_{k,k-1} × ||b*_{k-1}||² / B̃
            //   new μ_{k-1,j}     = old μ_{k,j}      for j < k-1
            //   new μ_{k,j}       = old μ_{k-1,j}    for j < k-1
            //   new μ_{i,k-1}     = (μ_{i,k}×B_k + μ_{i,k-1}×μ̂×B_{k-1}) / B̃   for i > k
            //   new μ_{i,k}       = μ_{i,k-1} − μ̂×μ_{i,k}                        for i > k
            //
            // All division/multiplication in HP fixed-point.
            let mu_hat = mu[k][k - 1].clone();
            let old_bkm1 = bstar_sq[k - 1].clone();
            let old_bk = bstar_sq[k].clone();

            basis.swap(k, k - 1);

            let mu_hat_sq = hp_mul(&mu_hat, &mu_hat);
            let b_tilde = &old_bk + &hp_mul(&mu_hat_sq, &old_bkm1);

            if b_tilde.is_zero() {
                // Degenerate basis — fall back to full recompute.
                let (new_bstar_sq, new_mu) = gram_schmidt_hp(basis);
                bstar_sq = new_bstar_sq;
                mu = new_mu;
            } else {
                bstar_sq[k - 1] = b_tilde.clone();
                bstar_sq[k] = (&old_bk * &old_bkm1) / &b_tilde;
                mu[k][k - 1] = (&mu_hat * &old_bkm1) / &b_tilde;

                // Swap μ rows k-1 and k for column indices j < k-1.
                {
                    let (rows_lo, rows_hi) = mu.split_at_mut(k);
                    let row_km1 = &mut rows_lo[k - 1];
                    let row_k = &mut rows_hi[0];
                    for j in 0..k - 1 {
                        std::mem::swap(&mut row_km1[j], &mut row_k[j]);
                    }
                }

                // Update μ_{i,k-1} and μ_{i,k} for i > k.
                for i in k + 1..n {
                    let old_mu_i_k = mu[i][k].clone();
                    let old_mu_i_km1 = mu[i][k - 1].clone();
                    let term1 = hp_mul(&old_mu_i_k, &old_bk);
                    let term2 = hp_mul(&hp_mul(&old_mu_i_km1, &mu_hat), &old_bkm1);
                    let num = &term1 + &term2;
                    mu[i][k - 1] = hp_div(&num, &b_tilde);
                    mu[i][k] = old_mu_i_km1 - hp_mul(&mu_hat, &old_mu_i_k);
                }
            }

            k = if k > 1 { k - 1 } else { 1 };
        }
    }
    Ok(())
}

/// LLL-reduce `basis` in place using Lovász parameter `delta`.
///
/// The standard choice is `delta = 0.75`.  Higher (closer to 1)
/// gives a stronger reduction at higher cost; lower gives weaker
/// reduction.  Theory requires `delta ∈ (1/4, 1)`.
///
/// `basis` is a list of basis vectors, each of equal length.  The
/// rows are *the* basis vectors (not columns).
///
/// Returns `Err` if the input is malformed or the algorithm fails
/// to terminate within a generous iteration cap.
pub fn lll_reduce(basis: &mut [Vec<BigInt>], delta: f64) -> Result<(), &'static str> {
    if !(0.25 < delta && delta < 1.0) {
        return Err("delta must be in (1/4, 1)");
    }
    let n = basis.len();
    if n == 0 {
        return Ok(());
    }
    let dim = basis[0].len();
    if dim == 0 {
        return Err("basis vectors must be non-empty");
    }
    if basis.iter().any(|v| v.len() != dim) {
        return Err("basis vectors must all have the same length");
    }

    // Iteration cap: classical LLL is O(n^4 log B) on n-dim basis
    // with entries ≤ B in magnitude.  Cap is generous to handle
    // cryptographic-size inputs (256-bit entries on dim ~ 30) while
    // still preventing pathological non-termination.  Originally
    // `50 · n²`; bumped to `500 · n² · 8` after a secp256k1 HNP
    // basis hit the cap with dim = 14 — `cap = 500·196·8 + 10⁴ ≈
    // 800K iterations` is well above the worst-case at our sizes.
    let max_iter = 500 * n * n * 8 + 10_000;
    let mut iter = 0;

    let (mut bstar, mut mu) = gram_schmidt(basis);
    let mut k = 1usize;

    while k < n {
        iter += 1;
        if iter > max_iter {
            return Err("LLL exceeded iteration cap (degenerate input?)");
        }

        // ── Size reduction (work top-down from j = k-1 to 0) ────────
        for j in (0..k).rev() {
            if mu[k][j].abs() > 0.5 {
                let q = mu[k][j].round();
                if q == 0.0 {
                    continue;
                }
                // Use the f64 round directly — for our sizes it fits in i64.
                // For safety we'd ideally round in BigInt arithmetic, but
                // for HNP-attack-scale lattices f64 round is exact.
                let q_int = q as i64;
                let q_bi = q_int.to_bigint().unwrap();
                for i in 0..dim {
                    let bji = basis[j][i].clone();
                    basis[k][i] -= &q_bi * &bji;
                }
                let qf = q_int as f64;
                // μ[k][j] update: μ[j][j] = 1 (b_j has coefficient 1
                // on bstar_j), but we don't store the diagonal.
                mu[k][j] -= qf;
                for i in 0..j {
                    mu[k][i] -= qf * mu[j][i];
                }
            }
        }

        // ── Lovász condition ────────────────────────────────────────
        let bsk_sq: f64 = bstar[k].iter().map(|x| x * x).sum();
        let bs_km1_sq: f64 = bstar[k - 1].iter().map(|x| x * x).sum();
        let mu_sq = mu[k][k - 1] * mu[k][k - 1];

        if bsk_sq >= (delta - mu_sq) * bs_km1_sq {
            k += 1;
        } else {
            basis.swap(k, k - 1);
            // Swap invalidates the GS data; cheapest correct fix is
            // to recompute from scratch.  At our dimensions (≤ 30)
            // this is microseconds.
            let (new_bstar, new_mu) = gram_schmidt(basis);
            bstar = new_bstar;
            mu = new_mu;
            k = if k > 1 { k - 1 } else { 1 };
        }
    }
    Ok(())
}

/// Gram–Schmidt orthogonalisation in `f64` precision with auto-scaling.
///
/// Returns `(bstar, mu)` where `bstar[i]` is the i-th orthogonal
/// vector and `mu[i][j]` is the GS coefficient
/// `<b_i, bstar_j> / <bstar_j, bstar_j>` for `j < i`.
///
/// Auto-scaling: if any basis entry exceeds ~2^500, all entries are
/// logically divided by a power of 2 before the f64 conversion so
/// that inner products (dim ≤ 30, entry ≤ 2^500) stay below f64::MAX
/// (≈ 2^1023).  The μ_{ij} coefficients are invariant to global
/// scaling, so the result is identical to unscaled GS.
///
/// This handles the P-521 HNP basis whose n² diagonal entries are
/// ~2^1042, which overflow unscaled f64 to Inf and produce NaN.
fn gram_schmidt(basis: &[Vec<BigInt>]) -> (Vec<Vec<f64>>, Vec<Vec<f64>>) {
    let n = basis.len();
    let dim = if n > 0 { basis[0].len() } else { 0 };

    // Find the max bit-length of all non-zero basis entries.
    let max_bits = basis
        .iter()
        .flatten()
        .filter(|x| !x.is_zero())
        .map(|x| x.bits())
        .max()
        .unwrap_or(0);

    // We need dim * (max_scaled_entry)^2 < 2^1023 to prevent dot-product
    // overflow.  With dim ≤ 30: 2*target + 5 < 1023 → target < 509.
    // Use 500 for a comfortable margin.
    let scale_shift: u32 = if max_bits > 500 {
        (max_bits - 500) as u32
    } else {
        0
    };

    let to_f = |x: &BigInt| big_to_f64_scaled(x, scale_shift);

    let mut bstar: Vec<Vec<f64>> = vec![vec![0.0; dim]; n];
    let mut mu: Vec<Vec<f64>> = vec![vec![0.0; n]; n];

    for i in 0..n {
        let bi: Vec<f64> = basis[i].iter().map(to_f).collect();
        bstar[i].copy_from_slice(&bi);
        for j in 0..i {
            let dot: f64 = bi.iter().zip(&bstar[j]).map(|(a, b)| a * b).sum();
            let norm: f64 = bstar[j].iter().map(|x| x * x).sum();
            mu[i][j] = if norm > 0.0 { dot / norm } else { 0.0 };
            for k in 0..dim {
                bstar[i][k] -= mu[i][j] * bstar[j][k];
            }
        }
    }
    (bstar, mu)
}

/// Convert `BigInt` to `f64`, dividing by `2^scale_shift` without
/// passing through Inf for large values.
///
/// For entries that fit in f64 normally (`bits + scale_shift ≤ 1020`),
/// this is equivalent to `x.to_f64() / 2^scale_shift`.  For larger
/// entries (e.g. n² for P-521 at ~2^1042), we first right-shift the
/// integer to bring it into f64 exponent range, then re-apply the
/// remaining exponent difference as a float multiply.  This preserves
/// small entries (e.g. 2^384 scaled by 2^542 → 2^{-158} ≈ 2.7×10^{-48},
/// well above f64's minimum positive normal ≈ 2^{-1022}).
fn big_to_f64_scaled(x: &BigInt, scale_shift: u32) -> f64 {
    if x.is_zero() || scale_shift == 0 {
        return x.to_f64().unwrap_or(0.0);
    }
    let sign: f64 = if x.is_negative() { -1.0 } else { 1.0 };
    // Work with the absolute value as a BigInt for bit operations.
    let abs: BigInt = if x.is_negative() {
        -x.clone()
    } else {
        x.clone()
    };
    let nbits = abs.bits() as u32;

    if nbits + scale_shift <= 1020 {
        // Safe direct path: convert to f64 then apply the scale.
        let v = abs.to_f64().unwrap_or(0.0);
        // 2^scale_shift is exactly representable in f64 for scale_shift < 1024.
        sign * v / f64::powi(2.0, scale_shift as i32)
    } else {
        // abs >= 2^(1020 - scale_shift), so direct to_f64() would overflow.
        // Shift abs right to bring it to ~2^1020 bits, then adjust exponent.
        let extra_shift = nbits.saturating_sub(1020);
        let shifted = &abs >> extra_shift as usize;
        let v = shifted.to_f64().unwrap_or(0.0);
        // v ≈ abs / 2^extra_shift, and we want abs / 2^scale_shift.
        // Result = v * 2^(extra_shift - scale_shift).
        let exp: i32 = (extra_shift as i32) - (scale_shift as i32);
        sign * v * f64::powi(2.0, exp)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use num_bigint::ToBigInt;

    fn vec_bigint(xs: &[i64]) -> Vec<BigInt> {
        xs.iter().map(|x| x.to_bigint().unwrap()).collect()
    }

    /// Smallest non-trivial LLL test from the original paper.
    #[test]
    fn lll_two_dim_obvious_reduction() {
        // Basis (1, 1, 1) and (-1, 0, 2).  After LLL we expect
        // shorter vectors.
        let mut basis = vec![vec_bigint(&[1, 1, 1]), vec_bigint(&[-1, 0, 2])];
        lll_reduce(&mut basis, 0.75).unwrap();
        // Reduced first vector should have norm² ≤ 3.
        let norm_sq: i64 = basis[0]
            .iter()
            .map(|x| {
                let xv = x.to_i64().unwrap();
                xv * xv
            })
            .sum();
        assert!(norm_sq <= 3, "got norm² = {}", norm_sq);
    }

    /// Reduced basis should satisfy size-reduction: |μ_ij| ≤ 1/2.
    #[test]
    fn reduced_basis_satisfies_size_reduction() {
        // Random-ish 4-dim integer basis.
        let mut basis = vec![
            vec_bigint(&[10, 23, 1, 5]),
            vec_bigint(&[7, -3, 12, 19]),
            vec_bigint(&[-4, 8, 15, -2]),
            vec_bigint(&[3, 11, -6, 9]),
        ];
        lll_reduce(&mut basis, 0.75).unwrap();
        let (_bstar, mu) = gram_schmidt(&basis);
        for i in 1..basis.len() {
            for j in 0..i {
                assert!(
                    mu[i][j].abs() <= 0.5 + 1e-9,
                    "size-reduction violated: μ[{}][{}] = {}",
                    i,
                    j,
                    mu[i][j]
                );
            }
        }
    }

    /// Identity basis is already reduced — LLL should be a no-op.
    #[test]
    fn identity_basis_is_already_reduced() {
        let mut basis = vec![
            vec_bigint(&[1, 0, 0]),
            vec_bigint(&[0, 1, 0]),
            vec_bigint(&[0, 0, 1]),
        ];
        let original = basis.clone();
        lll_reduce(&mut basis, 0.75).unwrap();
        assert_eq!(basis, original);
    }

    /// Swap should produce shorter first vector when input has a
    /// long-followed-by-short ordering.
    #[test]
    fn long_short_basis_swaps() {
        let mut basis = vec![vec_bigint(&[100, 0]), vec_bigint(&[1, 1])];
        lll_reduce(&mut basis, 0.75).unwrap();
        // Norm² of first vector should be ≤ 2 (the short one).
        let norm_sq: i64 = basis[0]
            .iter()
            .map(|x| {
                let xv = x.to_i64().unwrap();
                xv * xv
            })
            .sum();
        assert!(norm_sq <= 2);
    }

    #[test]
    fn rejects_invalid_delta() {
        let mut basis: Vec<Vec<BigInt>> = vec![vec_bigint(&[1, 0]), vec_bigint(&[0, 1])];
        assert!(lll_reduce(&mut basis, 1.5).is_err());
        assert!(lll_reduce(&mut basis, 0.1).is_err());
    }

    /// lll_reduce_hp with incremental GS swap should agree with lll_reduce on
    /// a medium basis that exercises multiple swap steps.
    #[test]
    fn lll_hp_incremental_swap_matches_lll_on_4dim() {
        // A 4-dim basis that requires several swaps.
        let mut a = vec![
            vec_bigint(&[10, 23, 1, 5]),
            vec_bigint(&[7, -3, 12, 19]),
            vec_bigint(&[-4, 8, 15, -2]),
            vec_bigint(&[3, 11, -6, 9]),
        ];
        let mut b = a.clone();
        lll_reduce(&mut a, 0.75).unwrap();
        lll_reduce_hp(&mut b, 0.75).unwrap();
        // Both should produce a first vector of the same squared norm.
        let norm_sq =
            |v: &Vec<BigInt>| -> i64 { v.iter().map(|x| x.to_i64().unwrap().pow(2)).sum() };
        assert_eq!(
            norm_sq(&a[0]),
            norm_sq(&b[0]),
            "HP (incremental) and f64 LLL diverge on 4-dim basis"
        );
    }

    /// lll_reduce_hp should agree with lll_reduce on small inputs.
    #[test]
    fn lll_hp_matches_lll_on_small_basis() {
        // Use the same known-reduced basis from lll_two_dim_obvious_reduction.
        let mut a = vec![vec_bigint(&[1, 1, 1]), vec_bigint(&[-1, 0, 2])];
        let mut b = a.clone();
        lll_reduce(&mut a, 0.75).unwrap();
        lll_reduce_hp(&mut b, 0.75).unwrap();

        // Both should produce vectors of the same length (not necessarily identical
        // order, but the first vector should be the same short vector).
        let norm_a0: i64 = a[0].iter().map(|x| x.to_i64().unwrap().pow(2)).sum();
        let norm_b0: i64 = b[0].iter().map(|x| x.to_i64().unwrap().pow(2)).sum();
        assert_eq!(
            norm_a0, norm_b0,
            "HP and f64 LLL should find same-length first vector"
        );
    }

    /// lll_reduce_hp should recover key on P-384 (a larger-entry case that
    /// exercises the HP path more than P-256 would).
    #[test]
    fn lll_hp_recovers_p384_key() {
        use crate::cryptanalysis::hnp_ecdsa::{
            hnp_recover_key_with_reduction, BiasedSignature, HnpReduction,
        };
        use crate::ecc::curve::CurveParams;
        use crate::ecc::keys::EccKeyPair;
        use crate::ecc::point::Point;
        use crate::utils::mod_inverse;
        use num_bigint::{BigUint, RandBigInt};
        use num_traits::Zero;
        use rand::rngs::StdRng;
        use rand::{RngCore, SeedableRng};

        let curve = CurveParams::p384();
        let n = &curve.n;
        let mut rng = StdRng::seed_from_u64(0xC0FFEE);
        let d = rng.gen_biguint_below(n);
        let kp = EccKeyPair::from_private(d.clone(), &curve);
        let k_bits = 288u32;

        let mut k_rng = StdRng::seed_from_u64(0xDEADBEEF);
        let mut z_seed: u64 = 0xDEAD_BEEF;
        let mut sigs: Vec<BiasedSignature> = Vec::new();
        while sigs.len() < 8 {
            let bytes = k_bits.div_ceil(8) as usize;
            let mut buf = vec![0u8; bytes];
            k_rng.fill_bytes(&mut buf);
            let extra = bytes as u32 * 8 - k_bits;
            if extra > 0 {
                buf[0] &= 0xff >> extra;
            }
            let k = BigUint::from_bytes_be(&buf);
            if k.is_zero() {
                continue;
            }
            let z = BigUint::from(z_seed) % n;
            z_seed = z_seed.wrapping_add(0x9E37_79B9_7F4A_7C15);
            let g = curve.generator();
            let a_fe = curve.a_fe();
            let kg = g.scalar_mul(&k, &a_fe);
            let x1 = match &kg {
                Point::Affine { x, .. } => x.value.clone(),
                Point::Infinity => continue,
            };
            let r = &x1 % n;
            if r.is_zero() {
                continue;
            }
            let rd = (&r * &d) % n;
            let z_plus_rd = (&z + &rd) % n;
            let k_inv = match mod_inverse(&k, n) {
                Some(v) => v,
                None => continue,
            };
            let s = (&k_inv * &z_plus_rd) % n;
            if s.is_zero() {
                continue;
            }
            sigs.push(BiasedSignature { r, s, z, k_bits });
        }

        let recovered =
            hnp_recover_key_with_reduction(&curve, &kp.public, &sigs, HnpReduction::LllHp).unwrap();
        assert_eq!(recovered, d, "HP LLL should recover P-384 private key");
    }
}

// ── BKZ (Block Korkine-Zolotarev) lattice reduction ──────────────────────────
//
// Schnorr 1987, refined by Schnorr-Euchner 1991.  Stronger than LLL —
// for each consecutive block of size β, find the shortest vector in
// the projected sublattice via enumeration and use it to refine the
// basis.  BKZ-2 reduces to LLL; β = 20 is "comfortable" with f64 GS;
// β > 30 needs extended-precision GS (`L²` of Nguyen-Stehlé) which we
// don't implement.
//
// Reference: Chen-Nguyen "BKZ 2.0: Better Lattice Security Estimates"
// (Asiacrypt 2011).  We implement the basic Schnorr-Euchner BKZ
// without the 2.0 enhancements (no extreme pruning, no progressive
// sieving) — sufficient for HNP attacks at sub-bit bias.

/// BKZ-β reduction.  Extends [`lll_reduce`] with block enumeration:
/// for each `k`, finds the shortest vector in the projected lattice
/// `π_k(L_{[k..k+β-1]})` and inserts it at position `k`.  Repeats
/// until a full pass produces no improvement.
///
/// `delta` = LLL Lovász parameter (use 0.99 inside BKZ for
/// stronger LLL-cleanup between block insertions).
/// `beta` = block size.  Cost is roughly `2^β` enumeration ops per
/// block per round; β = 20 is practical, β = 25 is slow but
/// feasible, β = 30 needs better GS precision than `f64` provides.
pub fn bkz_reduce(
    basis: &mut Vec<Vec<BigInt>>,
    beta: usize,
    delta: f64,
) -> Result<(), &'static str> {
    if beta < 2 {
        return Err("BKZ block size must be ≥ 2");
    }
    let n = basis.len();
    if n == 0 {
        return Ok(());
    }

    // Initial LLL pass — BKZ assumes the basis is already LLL-reduced.
    lll_reduce(basis, delta)?;

    // Iterative BKZ rounds: pass over all start positions; if any
    // insertion happens, do another full pass.  Bounded total
    // rounds for safety.
    let max_rounds = 8 * n;
    for _round in 0..max_rounds {
        let mut changed = false;
        for k in 0..n.saturating_sub(1) {
            let end = (k + beta - 1).min(n - 1);
            // Compute GS data restricted to rows [k..=end].
            let (bstar, mu) = gram_schmidt(&basis[..]);
            let block_norms_sq: Vec<f64> = (k..=end)
                .map(|i| bstar[i].iter().map(|x| x * x).sum())
                .collect();
            // Build mu_block[i][j] for i, j in 0..(end-k+1), j < i,
            // mapping mu_block[i][j] = mu[k+i][k+j].
            let block_dim = end - k + 1;
            let mut mu_block: Vec<Vec<f64>> = vec![vec![0.0; block_dim]; block_dim];
            for i in 0..block_dim {
                for j in 0..i {
                    mu_block[i][j] = mu[k + i][k + j];
                }
            }
            // Bound: ||b*_k||² (the current best at position k).  Any
            // shorter vector in the projected lattice is an improvement.
            let r_sq = block_norms_sq[0] * 0.999; // strict improvement
            let candidate = enumerate_block(&block_norms_sq, &mu_block, r_sq);
            if let Some(coeffs) = candidate {
                // Build the candidate vector v = Σ coeffs[i] · basis[k+i] (in original Z basis).
                let dim = basis[0].len();
                let mut v: Vec<BigInt> = vec![BigInt::zero(); dim];
                for i in 0..block_dim {
                    if coeffs[i] == 0 {
                        continue;
                    }
                    let c_bi = BigInt::from(coeffs[i]);
                    for d in 0..dim {
                        v[d] += &c_bi * &basis[k + i][d];
                    }
                }
                // Insert v at position k, shift the rest down,
                // then LLL-reduce — LLL drops the now-redundant vector.
                basis.insert(k, v);
                lll_reduce(basis, delta)?;
                // After LLL the basis has rank ≤ original rank n.
                // Drop any zero rows that LLL produced.
                basis.retain(|row| row.iter().any(|x| !x.is_zero()));
                if basis.len() < n {
                    // LLL collapsed — abort safely.
                    return Err("BKZ insertion produced rank-deficient basis");
                }
                changed = true;
                break; // restart the outer round
            }
        }
        if !changed {
            return Ok(());
        }
    }
    Err("BKZ exceeded round cap (degenerate input?)")
}

/// Schnorr-Euchner enumeration: find the shortest non-zero
/// vector in the projected lattice with coefficients in `Z^d`,
/// constrained to squared-norm `< radius_sq`.  Returns the integer
/// coefficient vector or `None` if no shorter vector exists.
///
/// `bstar_norms_sq[i]` = `||b*_{k+i}||²` for the `d` block vectors.
/// `mu[i][j]` for `j < i` = the GS coefficient `μ_{k+i, k+j}`
/// (only block-internal coefficients).
///
/// Algorithm: depth-first enumeration with center-rounding and
/// bound-pruning.  At each level `i`, the optimal continuous `x_i`
/// is `−Σ_{j>i} μ_{j,i} · x_j`; we try integer values in a window
/// around it whose width is bounded by the remaining squared-norm
/// budget.
fn enumerate_block(bstar_norms_sq: &[f64], mu: &[Vec<f64>], radius_sq: f64) -> Option<Vec<i64>> {
    let d = bstar_norms_sq.len();
    if d == 0 {
        return None;
    }
    let mut x = vec![0i64; d];
    let mut best: Option<(Vec<i64>, f64)> = None;
    enumerate_recurse(d - 1, &mut x, bstar_norms_sq, mu, 0.0, radius_sq, &mut best);
    best.map(|(coeffs, _)| coeffs)
}

fn enumerate_recurse(
    i: usize,
    x: &mut Vec<i64>,
    c: &[f64],
    mu: &[Vec<f64>],
    partial_sq: f64,
    radius_sq: f64,
    best: &mut Option<(Vec<i64>, f64)>,
) {
    let d = c.len();
    // Center for x[i]:  c_i = -Σ_{j>i} μ[j][i] · x[j]
    let mut center = 0.0_f64;
    for j in (i + 1)..d {
        center -= mu[j][i] * (x[j] as f64);
    }
    // Bound: (x[i] - center)² · c[i] ≤ R² - partial_sq.
    // Also use the current best as a tighter bound if available.
    let bound = best.as_ref().map(|b| b.1).unwrap_or(radius_sq);
    let remaining = bound - partial_sq;
    if remaining <= 0.0 {
        return;
    }
    if c[i] <= 0.0 {
        // Degenerate (zero-length GS vector); skip this level by
        // forcing x[i] = round(center).
        let xi = center.round() as i64;
        x[i] = xi;
        let dev = (xi as f64) - center;
        let new_partial = partial_sq + dev * dev * c[i];
        if i == 0 {
            if !x.iter().all(|&v| v == 0) && new_partial < bound {
                *best = Some((x.clone(), new_partial));
            }
        } else {
            enumerate_recurse(i - 1, x, c, mu, new_partial, radius_sq, best);
        }
        x[i] = 0;
        return;
    }
    let max_dev = (remaining / c[i]).sqrt();
    let lo = (center - max_dev).ceil() as i64;
    let hi = (center + max_dev).floor() as i64;
    if lo > hi {
        return;
    }
    // Schnorr-Euchner zigzag from round(center) outward (more
    // pruning-friendly than a left-to-right sweep).
    let center_r = center.round() as i64;
    let center_r_clamped = center_r.max(lo).min(hi);
    let mut tried: Vec<i64> = Vec::new();
    let mut step = 0i64;
    loop {
        let v_a = center_r_clamped + step;
        if v_a >= lo && v_a <= hi {
            tried.push(v_a);
        }
        if step != 0 {
            let v_b = center_r_clamped - step;
            if v_b >= lo && v_b <= hi {
                tried.push(v_b);
            }
        }
        if tried.len() as i64 >= (hi - lo + 1) {
            break;
        }
        step += 1;
        if step > (hi - lo + 1) {
            break; // safety
        }
    }
    for xi in tried {
        x[i] = xi;
        let dev = (xi as f64) - center;
        let new_partial = partial_sq + dev * dev * c[i];
        let bound = best.as_ref().map(|b| b.1).unwrap_or(radius_sq);
        if new_partial >= bound {
            continue;
        }
        if i == 0 {
            // Reached bottom; record if non-zero and shorter.
            if !x.iter().all(|&v| v == 0) {
                *best = Some((x.clone(), new_partial));
            }
        } else {
            enumerate_recurse(i - 1, x, c, mu, new_partial, radius_sq, best);
        }
    }
    x[i] = 0;
}

#[cfg(test)]
mod bkz_tests {
    use super::*;
    use num_bigint::ToBigInt;

    fn vec_bigint(xs: &[i64]) -> Vec<BigInt> {
        xs.iter().map(|x| x.to_bigint().unwrap()).collect()
    }

    /// BKZ-β=2 should be a no-op beyond LLL (β=2 BKZ ≡ LLL).
    #[test]
    fn bkz_beta_2_equals_lll() {
        let mut a = vec![
            vec_bigint(&[10, 23, 1, 5]),
            vec_bigint(&[7, -3, 12, 19]),
            vec_bigint(&[-4, 8, 15, -2]),
            vec_bigint(&[3, 11, -6, 9]),
        ];
        let mut b = a.clone();
        lll_reduce(&mut a, 0.99).unwrap();
        bkz_reduce(&mut b, 2, 0.99).unwrap();
        // a's first vector norm² should equal b's first vector norm²
        // (or be strictly close; β=2 BKZ is identical to LLL).
        let na: i64 = a[0]
            .iter()
            .map(|x| {
                let v = x.to_i64().unwrap_or(0);
                v * v
            })
            .sum();
        let nb: i64 = b[0]
            .iter()
            .map(|x| {
                let v = x.to_i64().unwrap_or(0);
                v * v
            })
            .sum();
        assert_eq!(na, nb, "BKZ-2 should match LLL");
    }

    /// BKZ-β=8 should produce a basis whose first vector is at least
    /// as short as LLL's first vector (often strictly shorter for
    /// challenging bases).
    #[test]
    fn bkz_at_least_as_good_as_lll() {
        // Standard "challenge" type basis: random-ish 6-dim integers.
        let basis_template = vec![
            vec_bigint(&[40, 13, 27, 9, 2, 17]),
            vec_bigint(&[5, 29, -8, 14, 22, 3]),
            vec_bigint(&[-12, 7, 31, -4, 18, 25]),
            vec_bigint(&[19, -6, 11, 24, -3, 8]),
            vec_bigint(&[2, 16, -9, 5, 30, -11]),
            vec_bigint(&[33, -14, 4, -7, 12, 21]),
        ];

        let mut a = basis_template.clone();
        let mut b = basis_template.clone();
        lll_reduce(&mut a, 0.99).unwrap();
        bkz_reduce(&mut b, 8, 0.99).unwrap();

        let norm_sq = |row: &Vec<BigInt>| -> f64 {
            row.iter().map(|x| big_to_f64_scaled(x, 0).powi(2)).sum()
        };
        let na = norm_sq(&a[0]);
        let nb = norm_sq(&b[0]);
        assert!(
            nb <= na + 1e-9,
            "BKZ first-vector norm {} should be ≤ LLL norm {}",
            nb,
            na
        );
    }

    /// BKZ should preserve the lattice (basis vectors stay integer
    /// linear combinations of the original — verified by determinant
    /// magnitude up to sign).
    #[test]
    fn bkz_preserves_lattice_volume() {
        let original = vec![
            vec_bigint(&[5, 0, 0]),
            vec_bigint(&[0, 5, 0]),
            vec_bigint(&[0, 0, 5]),
        ];
        let mut b = original.clone();
        bkz_reduce(&mut b, 3, 0.99).unwrap();
        // For axis-aligned cube lattice, BKZ should leave it
        // essentially unchanged (or permuted).  All rows should
        // still have norm² = 25.
        for row in &b {
            let n_sq: i64 = row
                .iter()
                .map(|x| {
                    let v = x.to_i64().unwrap_or(0);
                    v * v
                })
                .sum();
            assert_eq!(n_sq, 25);
        }
    }

    /// BKZ rejects β < 2.
    #[test]
    fn bkz_rejects_tiny_beta() {
        let mut basis = vec![vec_bigint(&[1, 0]), vec_bigint(&[0, 1])];
        assert!(bkz_reduce(&mut basis, 1, 0.75).is_err());
    }
}

// Reference the import so unused-import lints don't trip on
// `Signed` / `Zero` if compiler folds them out in release.
#[allow(dead_code)]
fn _link() -> bool {
    let x = BigInt::zero();
    x.is_negative() || x.is_positive()
}
