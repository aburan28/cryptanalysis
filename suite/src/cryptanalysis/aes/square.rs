//! The Square attack (Daemen, Knudsen, Rijmen — FSE 1997).
//!
//! The Square attack predates AES — it was designed for the cipher
//! **Square**, which became AES's structural ancestor. The attack
//! transfers directly, and it's the strongest known approach against
//! AES at very low round counts.
//!
//! # The Λ-set property
//!
//! Take 256 plaintexts that agree in 15 of their 16 bytes and have the
//! remaining byte take all 256 possible values exactly once. Call this
//! a **Λ-set** with one *active* byte. Track what happens to this set
//! through the AES round structure:
//!
//! - After round 1 (SubBytes → ShiftRows → MixColumns → AddRoundKey):
//!   the active byte has been mapped through the bijective S-box (still
//!   "all 256 values"), shifted into one row position by ShiftRows,
//!   then MixColumns turns that single active byte in a column into
//!   **four active bytes in one column**, each independently taking
//!   all 256 values.
//! - After round 2: ShiftRows distributes the four active bytes into
//!   four different columns; MixColumns then turns each of those
//!   single-active-byte columns into four-active-byte columns. The
//!   state is now **all 16 bytes active**, each ranging over all 256
//!   values across the Λ-set.
//! - After round 3: SubBytes is byte-wise so it preserves "all" sets,
//!   then ShiftRows shuffles them. MixColumns sums four "all" sets per
//!   column; the sum of `0,1,...,255` in GF(2⁸) is **zero**, so
//!   every output byte is **balanced** (XOR sum over the 256 ciphertexts
//!   equals zero). AddRoundKey XORs a constant, which preserves
//!   balance.
//!
//! This is the **3-round distinguisher**.
//!
//! # 4-round key recovery
//!
//! AES's final round drops MixColumns (FIPS 197). So peeling the
//! 4ᵗʰ round off costs only a guess of one byte of the last round key:
//!
//! 1. Encrypt a Λ-set under 4-round AES.
//! 2. For each byte position `(c, r)` of the ciphertext, guess
//!    `K₄[c][r]`.
//! 3. For each guess `k`, invert that final-round step at position
//!    `(c, r)`: undo AddRoundKey by XOR, undo SubBytes by `INV_SBOX`.
//!    (ShiftRows just relocates which post-round-3 byte we're looking
//!    at — `(c, r)` after ShiftRows came from `((c+r) mod 4, r)`
//!    before it.)
//! 4. XOR the resulting 256 bytes. If the sum is zero, `k` is a
//!    candidate for `K₄[c][r]`.
//!
//! The correct key produces sum = 0 by the 3-round distinguisher;
//! random keys produce sum = 0 with probability `2⁻⁸`. One Λ-set gives
//! ≈ 1 candidate per position; another Λ-set disambiguates. Once all
//! 16 bytes of `K₄` are recovered, invert the key schedule to get the
//! master key.
//!
//! # Cost
//!
//! 256 chosen plaintexts × 1 Λ-set, 16 byte positions × 256 guesses ×
//! 256 partial inversions ≈ 2²⁰ S-box lookups. Completes in
//! milliseconds; the test in this file proves it on a random key.
//!
//! # 5-round and beyond
//!
//! The attack extends to 5 rounds by adding one extra round at the
//! *start* (use a 2³² structure of plaintexts varying in one column,
//! find embedded Λ-sets after the first round) for ≈ 2³⁹ work, and to
//! 6 rounds by additionally guessing a column of the *first* round key
//! at the front. We do not implement those — they are well documented
//! and the structure is the same; what gets harder is bookkeeping, not
//! technique. Cross-referenced in `docs/DEFERRED.md`.

use super::reduced::{bytes_to_state, state_to_bytes, ReducedAes128, RoundOps, INV_SBOX};

/// Build a Λ-set of 256 plaintexts.
///
/// `base` provides the constant bytes (its `active_byte` index is ignored
/// and replaced with `0..=255`). `active_byte` is the column-major
/// position `0..16`.
pub fn lambda_set(base: &[u8; 16], active_byte: usize) -> Vec<[u8; 16]> {
    assert!(active_byte < 16);
    (0..256u16)
        .map(|v| {
            let mut p = *base;
            p[active_byte] = v as u8;
            p
        })
        .collect()
}

/// XOR-sum each of the 16 byte positions across a set of states.
/// Returns the per-position sum; the set is "balanced" iff every entry
/// is zero.
pub fn xor_sum(states: &[[u8; 16]]) -> [u8; 16] {
    let mut acc = [0u8; 16];
    for s in states {
        for i in 0..16 {
            acc[i] ^= s[i];
        }
    }
    acc
}

/// True iff every byte position has XOR sum zero across `states`.
pub fn is_balanced(states: &[[u8; 16]]) -> bool {
    xor_sum(states) == [0u8; 16]
}

/// Verify the 3-round Square distinguisher: encrypt a Λ-set under
/// 3-round AES (with the final MixColumns retained, so the property
/// holds after a full third round) and check that every output byte
/// XORs to zero. Returns `true` on success.
pub fn square_distinguisher_three_round(cipher: &ReducedAes128, base: &[u8; 16]) -> bool {
    assert_eq!(cipher.nr, 3, "distinguisher targets 3-round AES");
    assert!(
        cipher.final_mix_columns,
        "needs full final round for the balanced property"
    );
    let pts = lambda_set(base, 0);
    let cts: Vec<_> = pts.iter().map(|p| cipher.encrypt(p)).collect();
    is_balanced(&cts)
}

/// Report from [`key_recovery_four_round`].
#[derive(Debug, Clone)]
pub struct SquareAttackReport {
    /// Number of Λ-sets the attack consumed before locking the key.
    pub lambda_sets_used: usize,
    /// Number of S-box lookups performed (rough work estimate).
    pub sbox_lookups: usize,
    /// Recovered last round key (`K_nr`).
    pub last_round_key: [[u8; 4]; 4],
    /// Recovered master key, derived by inverting the key schedule.
    pub master_key: [u8; 16],
}

/// Recover the master key from a 4-round AES-128 with `final_mix_columns
/// = false` (the FIPS form). `oracle` is a closure that returns
/// `(plaintext, ciphertext)` pairs — in practice a chosen-plaintext
/// query.
///
/// The strategy: build one Λ-set, run the per-byte balance test for
/// each guess of each byte of the last round key. Any byte position
/// that has more than one candidate gets re-tested with a fresh
/// Λ-set. With high probability one Λ-set suffices; pathological cases
/// occasionally need a second.
pub fn key_recovery_four_round<F>(mut oracle: F) -> SquareAttackReport
where
    F: FnMut(&[u8; 16]) -> [u8; 16],
{
    let mut candidates: [Vec<u8>; 16] = Default::default();
    for c in candidates.iter_mut() {
        *c = (0u16..256).map(|v| v as u8).collect();
    }
    let mut lambda_sets_used = 0usize;
    let mut sbox_lookups = 0usize;
    let mut rng_state: u64 = 0xa5a5_a5a5_a5a5_a5a5;

    // Cycle through fresh Λ-sets until every position has exactly one
    // surviving candidate.
    loop {
        // Build a Λ-set with a random `base` and active byte = 0.
        let mut base = [0u8; 16];
        for byte in base.iter_mut() {
            rng_state = rng_state
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            *byte = (rng_state >> 33) as u8;
        }
        let pts = lambda_set(&base, 0);
        let cts: Vec<[u8; 16]> = pts.iter().map(&mut oracle).collect();
        lambda_sets_used += 1;

        // For each ciphertext byte position (c, r), narrow the
        // candidate set for K_nr[c][r].
        for c in 0..4 {
            for r in 0..4 {
                let flat = c * 4 + r;
                if candidates[flat].len() == 1 {
                    continue;
                }
                candidates[flat].retain(|&k| {
                    let mut acc = 0u8;
                    for ct in &cts {
                        acc ^= INV_SBOX[(ct[flat] ^ k) as usize];
                    }
                    acc == 0
                });
                sbox_lookups += 256 * candidates[flat].len().max(1);
            }
        }

        if candidates.iter().all(|c| c.len() == 1) {
            break;
        }

        // Safety valve. With 2 Λ-sets we should always converge.
        if lambda_sets_used >= 6 {
            panic!(
                "Square attack failed to converge after {lambda_sets_used} Λ-sets — \
                 this should not happen for correctly-implemented 4-round AES"
            );
        }
    }

    let mut last_round_key = [[0u8; 4]; 4];
    for c in 0..4 {
        for r in 0..4 {
            last_round_key[c][r] = candidates[c * 4 + r][0];
        }
    }
    let master_key = ReducedAes128::invert_schedule(4, &last_round_key);

    SquareAttackReport {
        lambda_sets_used,
        sbox_lookups,
        last_round_key,
        master_key,
    }
}

/// Inverting the *last* round of a single state. The integral attack
/// uses this byte-by-byte; this helper exposes the full-state inverse
/// for unit tests and pedagogical traces.
pub fn invert_final_round(ciphertext: &[u8; 16], last_round_key: &[[u8; 4]; 4]) -> [u8; 16] {
    let mut s = bytes_to_state(ciphertext);
    RoundOps::add_round_key(&mut s, last_round_key);
    RoundOps::inv_shift_rows(&mut s);
    RoundOps::inv_sub_bytes(&mut s);
    state_to_bytes(&s)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 3-round AES with the final MixColumns retained is byte-wise
    /// balanced over a Λ-set.
    #[test]
    fn three_round_balanced() {
        let key = [0x2bu8; 16];
        let cipher = ReducedAes128::new(&key, 3, true);
        let base = [0u8; 16];
        assert!(square_distinguisher_three_round(&cipher, &base));
    }

    /// The balanced property does NOT hold at 4 rounds — peeling one
    /// extra round breaks it. (This is what makes the attack work: the
    /// correct key restores the property when the round is inverted.)
    #[test]
    fn four_round_not_balanced_at_output() {
        let key = [0x2bu8; 16];
        let cipher = ReducedAes128::new(&key, 4, false);
        let pts = lambda_set(&[0u8; 16], 0);
        let cts: Vec<_> = pts.iter().map(|p| cipher.encrypt(p)).collect();
        assert!(!is_balanced(&cts));
    }

    /// End-to-end: 4-round Square attack recovers the master key.
    #[test]
    fn four_round_key_recovery_random_key() {
        // Deterministic "random" key so the test is reproducible.
        let key: [u8; 16] = [
            0x0f, 0x15, 0x71, 0xc9, 0x47, 0xd9, 0xe8, 0x59, 0x0c, 0xb7, 0xad, 0xd6, 0xaf, 0x7f,
            0x67, 0x98,
        ];
        let cipher = ReducedAes128::new(&key, 4, false);
        let report = key_recovery_four_round(|p| cipher.encrypt(p));
        assert_eq!(report.master_key, key, "Square attack recovered wrong key");
        assert!(report.lambda_sets_used <= 2);
    }

    #[test]
    fn invert_final_round_undoes_one_round() {
        let key = [0u8; 16];
        let cipher = ReducedAes128::new(&key, 4, false);
        let pt = [0x42u8; 16];
        let ct = cipher.encrypt(&pt);
        let last_rk = cipher.round_key(cipher.nr);
        let pre_final = invert_final_round(&ct, &last_rk);
        // pre_final should equal the state right after the 3ʳᵈ round's
        // AddRoundKey. Re-encrypt that state through one final round
        // and check we get back the ciphertext.
        let mut s = bytes_to_state(&pre_final);
        RoundOps::sub_bytes(&mut s);
        RoundOps::shift_rows(&mut s);
        RoundOps::add_round_key(&mut s, &last_rk);
        assert_eq!(state_to_bytes(&s), ct);
    }
}
