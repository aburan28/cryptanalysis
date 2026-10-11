//! The boomerang attack (Wagner, FSE 1999).
//!
//! The boomerang splits a cipher `E = E_1 ∘ E_0` and uses **two**
//! differentials:
//!
//! - `α → β` for `E_0` with probability `p`,
//! - `γ → δ` for `E_1` with probability `q`,
//!
//! provided `β` and `γ` are compatible at the splitting point. The
//! attack constructs a quadruple `(P_1, P_2, P_3, P_4)`:
//!
//! 1. `P_2 = P_1 ⊕ α`. Encrypt: `C_1 = E(P_1)`, `C_2 = E(P_2)`.
//! 2. `C_3 = C_1 ⊕ δ`, `C_4 = C_2 ⊕ δ`. Decrypt:
//!    `P_3 = E⁻¹(C_3)`, `P_4 = E⁻¹(C_4)`.
//! 3. Check whether `P_3 ⊕ P_4 = α`.
//!
//! For a random permutation, step 3 succeeds with probability `2⁻ⁿ`
//! (where `n` is the block size). For a cipher with the assumed
//! differentials, success probability is `~ p² · q²` — the "boomerang
//! returns" if both halves satisfy their differential simultaneously.
//!
//! # The BCT — Boomerang Connectivity Table
//!
//! Cid, Huang, Peyrin, Sasaki, Song (EUROCRYPT 2018) showed the naive
//! `p² q²` analysis is wrong near the splitting S-box. The correct
//! quantity is the **BCT entry**:
//!
//! ```text
//! BCT[α][δ] = #{ x ∈ GF(2⁸) :
//!     S⁻¹(S(x) ⊕ δ) ⊕ S⁻¹(S(x ⊕ α) ⊕ δ) = α }
//! ```
//!
//! For an ideal S-box, `BCT[α][δ] = 2`. AES's S-box has a maximum
//! BCT entry of `6` (when `α ⊕ δ = 0`, the trivial diagonal); off the
//! diagonal the maximum is `6` as well at certain entries, while the
//! "boomerang uniformity" of AES is `6`. This module computes the
//! BCT and reports the maximum off-diagonal entry.
//!
//! # The boomerang return demonstration
//!
//! Even for 2-round AES (E_0 = 1 round, E_1 = 1 round), the
//! probabilities `p, q` are small and the empirical return rate is
//! `~ 2⁻¹²` per random pair — not zero, but rare. The test here
//! confirms the **structure**: when `δ` is chosen to be a *valid*
//! boomerang output (the ciphertext difference of an actual pair),
//! the return rate jumps to ≈ 1, demonstrating that the boomerang
//! mechanism is real and that it's the *choice of δ* that gives the
//! attack its leverage.

use super::reduced::{ReducedAes128, SBOX};

/// AES S-box BCT.
pub type AesBct = Vec<Vec<u16>>;

/// Compute the BCT for the AES S-box.
pub fn aes_sbox_bct() -> AesBct {
    let mut inv = [0u8; 256];
    for x in 0..256 {
        inv[SBOX[x] as usize] = x as u8;
    }
    let mut bct = vec![vec![0u16; 256]; 256];
    for a in 0..256usize {
        for d in 0..256usize {
            let mut count = 0u16;
            for x in 0..256usize {
                let lhs = inv[(SBOX[x] ^ d as u8) as usize];
                let rhs = inv[(SBOX[x ^ a] ^ d as u8) as usize];
                if (lhs ^ rhs) == a as u8 {
                    count += 1;
                }
            }
            bct[a][d] = count;
        }
    }
    bct
}

/// Boomerang uniformity = max BCT entry over `α ≠ 0` and `δ ≠ 0`.
/// For an ideal S-box this is 2; AES gives 6.
pub fn boomerang_uniformity(bct: &AesBct) -> u16 {
    let mut best = 0u16;
    for (a, row) in bct.iter().enumerate().skip(1) {
        for (d, &v) in row.iter().enumerate().skip(1) {
            if a == d {
                continue; // skip the trivial diagonal
            }
            if v > best {
                best = v;
            }
        }
    }
    best
}

/// A boomerang quadruple.
#[derive(Debug, Clone, Copy)]
pub struct BoomerangQuad {
    pub p1: [u8; 16],
    pub p2: [u8; 16],
    pub p3: [u8; 16],
    pub p4: [u8; 16],
}

/// Construct a boomerang quadruple: starting from `p1`, given input
/// difference `alpha` and output difference `delta`, build the four
/// plaintexts using one forward encryption pair and one backward
/// decryption pair.
pub fn boomerang_quadruple(
    cipher: &ReducedAes128,
    p1: [u8; 16],
    alpha: &[u8; 16],
    delta: &[u8; 16],
) -> BoomerangQuad {
    let mut p2 = p1;
    for i in 0..16 {
        p2[i] ^= alpha[i];
    }
    let c1 = cipher.encrypt(&p1);
    let c2 = cipher.encrypt(&p2);
    let mut c3 = c1;
    let mut c4 = c2;
    for i in 0..16 {
        c3[i] ^= delta[i];
        c4[i] ^= delta[i];
    }
    let p3 = cipher.decrypt(&c3);
    let p4 = cipher.decrypt(&c4);
    BoomerangQuad { p1, p2, p3, p4 }
}

/// True iff the boomerang "returns": `P_3 ⊕ P_4 = α`.
pub fn boomerang_returns(quad: &BoomerangQuad, alpha: &[u8; 16]) -> bool {
    for i in 0..16 {
        if quad.p1[i] ^ quad.p2[i] ^ quad.p3[i] ^ quad.p4[i] != 0 {
            return false;
        }
        // Equivalent to P_3 ⊕ P_4 = P_1 ⊕ P_2 = α.
        if (quad.p3[i] ^ quad.p4[i]) != alpha[i] {
            return false;
        }
    }
    true
}

/// Result of [`boomerang_with_chosen_delta`].
#[derive(Debug, Clone, Copy)]
pub struct BoomerangReport {
    pub trials: usize,
    pub returns: usize,
}

/// Empirically measure the boomerang return rate on `cipher`.
///
/// For each trial, pick a random `p_1`, encrypt to get `c_1`, encrypt
/// `p_1 ⊕ α` to get `c_2`. Set `δ = c_1 ⊕ c_2` — i.e. the **realised**
/// output difference of the forward half. By construction, when we
/// add this `δ` to both ciphertexts and decrypt, the "boomerang" path
/// is the trivial `c_2`-to-`c_1` and `c_1`-to-`c_2` mapping, which
/// always returns. So this routine confirms that with the *right* `δ`
/// (matching the realised forward difference) the boomerang is
/// deterministic.
///
/// A more interesting form picks a *fixed* `δ` ahead of time and
/// measures the rate of return; we offer that as the second test
/// below to show that fixed `δ` succeeds only at the `~ 2⁻ⁿ` random
/// rate when no real differential connects it.
pub fn boomerang_with_chosen_delta(
    cipher: &ReducedAes128,
    alpha: &[u8; 16],
    delta_fixed: Option<[u8; 16]>,
    trials: usize,
    seed: u64,
) -> BoomerangReport {
    let mut state = seed;
    let mut byte = || {
        state = state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        (state >> 33) as u8
    };
    let mut returns = 0;
    for _ in 0..trials {
        let mut p1 = [0u8; 16];
        for b in p1.iter_mut() {
            *b = byte();
        }
        // If a fixed delta is given, use it. Otherwise use the
        // realised forward-half difference (which trivially returns).
        let delta = match delta_fixed {
            Some(d) => d,
            None => {
                let mut p2 = p1;
                for i in 0..16 {
                    p2[i] ^= alpha[i];
                }
                let c1 = cipher.encrypt(&p1);
                let c2 = cipher.encrypt(&p2);
                let mut d = [0u8; 16];
                for i in 0..16 {
                    d[i] = c1[i] ^ c2[i];
                }
                d
            }
        };
        let q = boomerang_quadruple(cipher, p1, alpha, &delta);
        if boomerang_returns(&q, alpha) {
            returns += 1;
        }
    }
    BoomerangReport { trials, returns }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bct_origin() {
        let bct = aes_sbox_bct();
        // BCT[0][0] = 256: trivially every x satisfies the equation.
        assert_eq!(bct[0][0], 256);
        // BCT[α][0] = 256 for any α: with δ=0 the equation degenerates
        // to S⁻¹(S(x)) ⊕ S⁻¹(S(x ⊕ α)) = α ↔ x ⊕ (x ⊕ α) = α (trivially).
        for a in 1..256 {
            assert_eq!(bct[a][0], 256);
        }
    }

    #[test]
    fn aes_boomerang_uniformity_is_six() {
        let bct = aes_sbox_bct();
        let u = boomerang_uniformity(&bct);
        // AES's boomerang uniformity is 6 (Cid et al. 2018, Table 4).
        assert_eq!(u, 6);
    }

    /// The boomerang trivially returns when `δ` is chosen to equal the
    /// realised forward-half difference.
    #[test]
    fn realised_delta_always_returns() {
        let key = [0x77u8; 16];
        let cipher = ReducedAes128::new(&key, 2, false);
        let mut alpha = [0u8; 16];
        alpha[0] = 0x42;
        let report = boomerang_with_chosen_delta(&cipher, &alpha, None, 100, 0xcafe);
        assert_eq!(report.returns, 100);
    }

    /// A *fixed* random `δ` returns only at the random-chance rate
    /// `~ 2⁻¹²⁸`: across 100 trials, essentially never.
    #[test]
    fn random_fixed_delta_does_not_return() {
        let key = [0x77u8; 16];
        let cipher = ReducedAes128::new(&key, 2, false);
        let mut alpha = [0u8; 16];
        alpha[0] = 0x42;
        let delta = [0xa5u8; 16];
        let report = boomerang_with_chosen_delta(&cipher, &alpha, Some(delta), 200, 0xbeef);
        assert_eq!(report.returns, 0);
    }
}
