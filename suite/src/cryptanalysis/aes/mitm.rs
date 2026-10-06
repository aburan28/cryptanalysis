//! Demirci-Selçuk Meet-in-the-Middle attack (FSE 2008).
//!
//! The Demirci-Selçuk MITM is the strongest **structural** attack
//! against reduced-round AES — better than impossible-differential or
//! Square at 7–8 rounds, in terms of time-data trade-offs. Dunkelman,
//! Keller and Shamir (CRYPTO 2010) refined it with the **multiset**
//! observation, reducing the offline-table size from
//! `~2²¹⁶` to `~2¹³⁸`, and Derbez-Fouque-Jean (EUROCRYPT 2013) further
//! brought it to `~2⁹⁹`.
//!
//! # δ-sets and ordered sequences
//!
//! A **δ-set** is a set of 256 plaintexts that differ in exactly one
//! byte (the "active" byte) and are constant elsewhere — same as a
//! Λ-set for the integral attack. The byte's 256 values cover all
//! `0..=255` exactly once.
//!
//! For each plaintext, the cipher produces a 16-byte ciphertext. Pick
//! any output byte position `i`; the **ordered sequence** at `i` is
//! the vector `(C_0[i], C_1[i], …, C_255[i])` indexed by the active
//! byte's value. The corresponding **multiset** at `i` discards the
//! ordering and keeps only the histogram of values.
//!
//! # The Demirci-Selçuk property
//!
//! After **4 rounds** of AES, the *ordered sequence* at any single
//! output byte is determined by only a small number of intermediate
//! state parameters (originally ~25 bytes; Dunkelman et al. reduce
//! it further). Crucially this is **less than `2²⁵⁶`** — the number
//! of possible 256-byte sequences for a random function — so the
//! cipher leaves a structural fingerprint.
//!
//! The 7-round attack proceeds:
//!
//! 1. **Offline.** Enumerate the parameter bytes and precompute the
//!    full table of possible sequences at the boundary between rounds
//!    3 and 4. Storage: `~2⁹⁹` entries with Derbez-Fouque-Jean's
//!    refinement.
//! 2. **Online.** Query the cipher on a δ-set and obtain 256 plaintext-
//!    ciphertext pairs. For each guess of the **outer** round-7 and
//!    round-6 key bytes (the ones that affect a single ciphertext
//!    byte through the last two rounds, ≈ `2⁶⁴` guesses), partially
//!    decrypt to reconstruct the candidate sequence at the boundary
//!    and look it up in the offline table. A hit identifies the
//!    correct key candidates.
//!
//! The full 7-round attack is impractical to run on a workstation,
//! and the offline table is `2⁹⁹` entries — also impractical. What
//! **this module** ships is the *structural machinery*: δ-set
//! construction, multiset/sequence extraction, a tiny-scale MITM
//! demonstration on 2-round AES recovering one byte of the round-2
//! key, and notes documenting how the full attack scales.

use super::reduced::{ReducedAes128, INV_SBOX, SBOX};

/// Generate a δ-set: 256 plaintexts equal to `base` everywhere except
/// position `active_byte`, which cycles `0..=255`.
pub fn delta_set(base: &[u8; 16], active_byte: usize) -> Vec<[u8; 16]> {
    assert!(active_byte < 16);
    (0..256u16)
        .map(|v| {
            let mut p = *base;
            p[active_byte] = v as u8;
            p
        })
        .collect()
}

/// Ordered 256-byte sequence at a single output byte position over a
/// δ-set's ciphertexts.
pub fn ordered_sequence(ciphertexts: &[[u8; 16]], byte_pos: usize) -> Vec<u8> {
    assert!(ciphertexts.len() == 256);
    ciphertexts.iter().map(|c| c[byte_pos]).collect()
}

/// Multiset (histogram) of values at a single output byte over a
/// δ-set's ciphertexts.
pub fn multiset(ciphertexts: &[[u8; 16]], byte_pos: usize) -> [u32; 256] {
    let mut h = [0u32; 256];
    for c in ciphertexts {
        h[c[byte_pos] as usize] += 1;
    }
    h
}

/// True iff `m` is a uniform histogram: every value appears exactly
/// once. For a δ-set of size 256, this is the "all values exactly once"
/// pattern that holds at any byte position through 1 AES round (since
/// SubBytes is a bijection and ShiftRows is a permutation).
pub fn is_uniform_multiset(m: &[u32; 256]) -> bool {
    m.iter().all(|&c| c == 1)
}

/// GF(2⁸) multiplication by `0x02` (the MC R1 coefficient that propagates
/// the active byte into the first row of column 0).
#[inline]
fn xtimes(a: u8) -> u8 {
    let hi = a & 0x80 != 0;
    let r = a.wrapping_shl(1);
    if hi {
        r ^ 0x1b
    } else {
        r
    }
}

/// Tiny-scale Demirci-Selçuk style MITM on **2-round AES**.
///
/// Algebraic setup for plaintext `(i, 0, …, 0)` (δ-set with active
/// byte 0) and ciphertext byte 0:
///
/// ```text
/// c_i[0] = S( 2 · S(i ⊕ K_R0[0]) ⊕ M ) ⊕ K_R2[0][0]
/// ```
///
/// where `M` aggregates the constant parts of MixColumns R1 and
/// `K_R1[0]`. Rearranging:
///
/// ```text
/// S⁻¹( c_i[0] ⊕ K_R2[0][0] ) ⊕ 2 · S( i ⊕ K_R0[0] ) = M  (constant over i)
/// ```
///
/// **MITM**: define
///
/// - `f_k(i) = S⁻¹(c_i[0] ⊕ k)` for a guess `k` of `K_R2[0][0]`.
/// - `g_j(i) = 2 · S(i ⊕ j)` for a guess `j` of `K_R0[0]`.
///
/// For the correct `(k, j)`, `f_k(i) ⊕ g_j(i)` is constant over
/// `i = 0..=255` (and equal to `M`). For wrong `(k, j)` the XOR is
/// essentially uniform across `i`. Sweeping the 2¹⁶ pair `(k, j)`
/// and checking the constancy condition recovers all three values:
/// `K_R0[0]`, `K_R2[0][0]`, and `M = K_R1[0] ⊕ const_mc`.
///
/// Returns the (usually single) candidate `(K_R0[0], K_R2[0][0], M)`.
pub fn mitm_recover_two_round(cipher: &ReducedAes128) -> Vec<(u8, u8, u8)> {
    assert_eq!(cipher.nr, 2, "MITM targets 2-round AES");
    let delta = delta_set(&[0u8; 16], 0);
    let cts: Vec<_> = delta.iter().map(|p| cipher.encrypt(p)).collect();

    let mut candidates = Vec::new();
    // Precompute g_j(i) = 2 · SBOX(i ⊕ j) for all j and i.
    let mut g = vec![[0u8; 256]; 256];
    for j in 0..256usize {
        for i in 0..256usize {
            g[j][i] = xtimes(SBOX[i ^ j]);
        }
    }
    // For each k, compute f_k(i) and check XOR-with-g_j gives a
    // constant over i.
    for k in 0..256usize {
        let mut f = [0u8; 256];
        for i in 0..256usize {
            f[i] = INV_SBOX[(cts[i][0] ^ k as u8) as usize];
        }
        for j in 0..256usize {
            let m0 = f[0] ^ g[j][0];
            let mut constant = true;
            for i in 1..256 {
                if (f[i] ^ g[j][i]) != m0 {
                    constant = false;
                    break;
                }
            }
            if constant {
                candidates.push((j as u8, k as u8, m0));
            }
        }
    }
    candidates
}

#[doc(hidden)]
pub fn _refer_sbox() -> &'static [u8; 256] {
    &SBOX
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn delta_set_has_uniform_multiset_at_active_byte() {
        let delta = delta_set(&[0u8; 16], 5);
        let mut hist = [0u32; 256];
        for p in &delta {
            hist[p[5] as usize] += 1;
        }
        assert!(is_uniform_multiset(&hist));
    }

    /// After 1 round of AES (FIPS), the multiset at any byte position
    /// affected by the active plaintext byte is uniform.
    #[test]
    fn one_round_multiset_uniform_at_affected_position() {
        let key = [0u8; 16];
        let cipher = ReducedAes128::new(&key, 1, false);
        let delta = delta_set(&[0u8; 16], 0); // plaintext (0,0) active
        let cts: Vec<_> = delta.iter().map(|p| cipher.encrypt(p)).collect();
        // After 1 FIPS round, ciphertext byte (0, 0) depends on
        // plaintext byte (0, 0). It should have uniform multiset.
        let m = multiset(&cts, 0);
        assert!(is_uniform_multiset(&m));
    }

    /// The 2-round Demirci-Selçuk-style MITM recovers `K_R0[0]` and
    /// `K_R2[0][0]` via sequence-matching.
    #[test]
    fn mitm_two_round_recovers_key_bytes() {
        let key: [u8; 16] = [
            0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xaa, 0xbb, 0xcc, 0xdd, 0xee,
            0xff, 0x00,
        ];
        let cipher = ReducedAes128::new(&key, 2, false);
        let cands = mitm_recover_two_round(&cipher);
        assert!(!cands.is_empty(), "no candidates survived");
        let true_k_r0_0 = key[0];
        let true_k_r2_00 = cipher.round_key(2)[0][0];
        assert!(
            cands.iter().any(|&(j, k, _)| j == true_k_r0_0 && k == true_k_r2_00),
            "true key bytes K_R0[0]={true_k_r0_0:#x}, K_R2[0][0]={true_k_r2_00:#x} not in candidates: {cands:?}"
        );
        // The 256-entry sequence match is strong; only the correct
        // triple should survive.
        assert_eq!(
            cands.len(),
            1,
            "expected unique recovery, got {} candidates",
            cands.len()
        );
    }
}
