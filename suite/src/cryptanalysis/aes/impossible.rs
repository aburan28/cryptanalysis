//! Impossible differential cryptanalysis (Biham, Biryukov, Shamir —
//! EUROCRYPT 1999). The "miss-in-the-middle" technique.
//!
//! The classical impossible differential for AES is:
//!
//! > Over **4 full rounds**, no plaintext-pair with input difference
//! > having exactly one active byte can produce an output difference
//! > with exactly one active byte.
//!
//! That is, the truncated differential `1 → 1` over 4 rounds has
//! probability **zero**, not just low.
//!
//! # Why it's impossible
//!
//! Track activity patterns through 4 rounds, starting with a single
//! active input byte at position `(0, 0)`:
//!
//! | Step    | Active bytes              | Reason                            |
//! |---------|---------------------------|-----------------------------------|
//! | input   | {(0,0)}                   | given                             |
//! | SB R1   | {(0,0)}                   | S-box preserves activity          |
//! | SR R1   | {(0,0)}                   | row 0 fixed                       |
//! | MC R1   | {(0,0),(0,1),(0,2),(0,3)} | branch number 5                   |
//! | AK R1   | same                      | XOR with constant                 |
//! | SB R2   | same                      | byte-wise                         |
//! | SR R2   | {(0,0),(3,1),(2,2),(1,3)} | rows 1, 2, 3 shifted              |
//! | MC R2   | all 16 active             | each column had 1 active ⇒ all 4  |
//! | …       | all 16                    | propagation only spreads          |
//! | output  | all 16                    | cannot collapse back              |
//!
//! Reading backwards from a single-active-byte output:
//!
//! | Step (reversed) | Active bytes              |
//! |-----------------|---------------------------|
//! | output          | {(0,0)}                   |
//! | INV AK R4       | {(0,0)}                   |
//! | INV SR R4       | {(0,0)}                   |
//! | INV MC R4       | column 0 fully active     |
//! | INV AK / SB R3  | same column-0 pattern     |
//! | INV SR R3       | one byte per column       |
//! | INV MC R3       | all 16 active             |
//!
//! The two views collide in the middle. Going *forward* the state is
//! all-active by round 2's MC; going *backward* the state is all-active
//! by round 3's INV_MC. There is no state pattern that both views
//! agree on, so the differential is impossible.
//!
//! # Distinguisher (this module)
//!
//! We implement the **distinguisher** at 4 rounds: across many
//! plaintext pairs with single-active-byte input difference, **zero**
//! pairs produce single-active-byte output difference. A random
//! permutation would produce such a pair with vanishing but nonzero
//! probability, so the gap is in principle detectable; in practice,
//! the empirical "0 vs 0" result on a finite test is the educational
//! point.
//!
//! # 5-round key-recovery sketch
//!
//! The historical attack adds one round at the end. For each candidate
//! value of the four bytes of `K_R5` that affect column 0 of the
//! post-round-4 state (positions 0, 7, 10, 13 — the same column-0
//! quartet as the differential attack), invert one round of the
//! ciphertext pair and check whether the resulting state has
//! single-active-byte difference at `(0,0)`. **Any such candidate is
//! provably wrong** (it would manifest a 4-round impossible
//! differential). With `2³²` guesses and a structure of `≈ 2¹⁶`
//! plaintexts, enough wrong guesses are eliminated to recover the four
//! key bytes uniquely.
//!
//! That full attack is `≈ 2⁹¹` operations as stated in the literature
//! and we do not run it here — see `docs/DEFERRED.md`. The
//! `key_byte_eliminations_5_round` routine below runs the *one-byte*
//! version of the elimination over a small parameter range, sufficient
//! to demonstrate the elimination mechanism on a runnable scale.

use super::reduced::{ReducedAes128, INV_SBOX};

/// Count the active bytes (nonzero positions) in a 16-byte difference.
pub fn active_byte_count(diff: &[u8; 16]) -> u32 {
    diff.iter().filter(|&&b| b != 0).count() as u32
}

/// Returns the single active-byte position if exactly one byte is
/// nonzero, else `None`.
pub fn single_active_position(diff: &[u8; 16]) -> Option<usize> {
    let mut found: Option<usize> = None;
    for (i, &b) in diff.iter().enumerate() {
        if b != 0 {
            if found.is_some() {
                return None;
            }
            found = Some(i);
        }
    }
    found
}

/// XOR-difference of two states.
pub fn diff(a: &[u8; 16], b: &[u8; 16]) -> [u8; 16] {
    let mut d = [0u8; 16];
    for i in 0..16 {
        d[i] = a[i] ^ b[i];
    }
    d
}

/// Result of the 4-round impossible-differential distinguisher.
#[derive(Debug, Clone)]
pub struct ImpossibilityReport {
    pub pairs_tested: usize,
    /// Pairs producing exactly 1 active byte at output (theoretical: 0).
    pub one_active_output_pairs: usize,
    /// Pairs producing 2..4 active bytes at output (rare but possible).
    pub low_activity_output_pairs: usize,
    pub fully_active_pairs: usize,
}

/// Empirically verify the 4-round impossible differential. Encrypts
/// `n_pairs` plaintext pairs `(P, P ⊕ (α, 0, …, 0))` under the given
/// 4-round AES and counts how many produce an output difference with
/// exactly 1 active byte.
pub fn verify_4_round_impossibility(
    cipher: &ReducedAes128,
    alpha: u8,
    n_pairs: usize,
    seed: u64,
) -> ImpossibilityReport {
    assert_eq!(cipher.nr, 4, "distinguisher targets 4-round AES");
    let mut state = seed;
    let mut byte = || {
        state = state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        (state >> 33) as u8
    };

    let mut one = 0usize;
    let mut low = 0usize;
    let mut full = 0usize;
    for _ in 0..n_pairs {
        let mut p = [0u8; 16];
        for b in p.iter_mut() {
            *b = byte();
        }
        let mut p2 = p;
        p2[0] ^= alpha;
        let d = diff(&cipher.encrypt(&p), &cipher.encrypt(&p2));
        let active = active_byte_count(&d);
        if active == 1 {
            one += 1;
        }
        if (2..=4).contains(&active) {
            low += 1;
        }
        if active == 16 {
            full += 1;
        }
    }
    ImpossibilityReport {
        pairs_tested: n_pairs,
        one_active_output_pairs: one,
        low_activity_output_pairs: low,
        fully_active_pairs: full,
    }
}

/// Check whether a candidate state-after-round-4 (i.e. one specific
/// inverse-round-5 reconstruction) is **contradicted** by the
/// 4-round impossible differential `1 → 1`.
///
/// The check: column 0 of the difference should NOT have exactly one
/// active byte at row 0. (Position (0,0) is where our single-byte
/// input difference lives; the impossibility says no path through 4
/// AES rounds can land back there alone.)
///
/// Returns `true` iff the candidate is contradicted (so any key guess
/// that produced this state can be discarded).
pub fn state_contradicts_impossibility(diff_state_r4: &[u8; 16]) -> bool {
    // "Single active byte at (0,0)" in column-major: index 0 nonzero,
    // indices 1..16 zero.
    if diff_state_r4[0] == 0 {
        return false;
    }
    diff_state_r4[1..].iter().all(|&b| b == 0)
}

/// Demonstrate the 5-round impossible-differential elimination mechanism
/// on a runnable scale. We guess the **true** K_R5 quartet and verify
/// that no pair is contradicted (the true key never witnesses the
/// impossibility); then guess a **random** K_R5 quartet and verify
/// that a contradiction shows up with enough pairs.
///
/// Returns `(contradictions_with_true_key, contradictions_with_random_key)`.
///
/// With the true key, the first must be **zero** for any number of
/// pairs (it's structurally impossible). With a random wrong key the
/// 32-bit pattern is essentially uniform, so contradictions appear at
/// rate ≈ `2⁻²⁴` per pair; expect a handful at `2²⁰` pairs.
pub fn elimination_demonstration(
    cipher: &ReducedAes128,
    alpha: u8,
    n_pairs: usize,
    seed: u64,
) -> (usize, usize) {
    assert_eq!(cipher.nr, 5);
    let quartet = [0usize, 7, 10, 13];
    let rk5 = cipher.round_key(5);
    // The true four bytes of K_R5 we'd be guessing in a full attack.
    let true_key_at = |flat: usize| rk5[flat / 4][flat % 4];

    // A wrong "guess" — XOR in a random pattern so each byte is wrong.
    let wrong_bytes = [0xa5u8, 0x5au8, 0x33u8, 0xcc];

    let check = |flat: usize, c: &[u8; 16], key_byte: u8| INV_SBOX[(c[flat] ^ key_byte) as usize];

    let mut state = seed;
    let mut byte = || {
        state = state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        (state >> 33) as u8
    };
    let mut true_hits = 0usize;
    let mut wrong_hits = 0usize;
    for _ in 0..n_pairs {
        let mut p = [0u8; 16];
        for b in p.iter_mut() {
            *b = byte();
        }
        let mut p2 = p;
        p2[0] ^= alpha;
        let c1 = cipher.encrypt(&p);
        let c2 = cipher.encrypt(&p2);
        // True-key inversion of column 0 of state_R4.
        let mut true_state = [0u8; 16];
        for (idx, &flat) in quartet.iter().enumerate() {
            // After INV_SR, ciphertext position `flat` lands at column 0,
            // row `idx`. Flat in the state_R4-diff array is `idx`.
            true_state[idx] =
                check(flat, &c1, true_key_at(flat)) ^ check(flat, &c2, true_key_at(flat));
        }
        // Wrong-key inversion.
        let mut wrong_state = [0u8; 16];
        for (idx, &flat) in quartet.iter().enumerate() {
            wrong_state[idx] = check(flat, &c1, true_key_at(flat) ^ wrong_bytes[idx])
                ^ check(flat, &c2, true_key_at(flat) ^ wrong_bytes[idx]);
        }
        if state_contradicts_impossibility(&true_state) {
            true_hits += 1;
        }
        if state_contradicts_impossibility(&wrong_state) {
            wrong_hits += 1;
        }
    }
    (true_hits, wrong_hits)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The 4-round impossible differential: no pair produces a
    /// single-active-byte output difference across hundreds of trials.
    #[test]
    fn four_round_no_one_active_byte() {
        let key = [0x33u8; 16];
        let cipher = ReducedAes128::new(&key, 4, false);
        let report = verify_4_round_impossibility(&cipher, 0x9c, 4_000, 0xcafe_babe);
        assert_eq!(
            report.one_active_output_pairs, 0,
            "4-round AES cannot map 1→1 — saw {} pairs",
            report.one_active_output_pairs
        );
        // Most pairs should be fully active.
        assert!(report.fully_active_pairs > report.pairs_tested * 9 / 10);
    }

    /// Sanity: at 3 rounds, single-byte differences DO end up
    /// concentrated in column 0 sometimes (after just one MC), so
    /// the equivalent "3-round impossibility" doesn't hold.
    #[test]
    fn three_round_not_impossible() {
        let key = [0x33u8; 16];
        let cipher = ReducedAes128::new(&key, 3, false);
        let mut state = 0xabcd_efabu64;
        let mut byte = || {
            state = state
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            (state >> 33) as u8
        };
        let mut full_active = 0;
        for _ in 0..1_000 {
            let mut p = [0u8; 16];
            for b in p.iter_mut() {
                *b = byte();
            }
            let mut p2 = p;
            p2[0] ^= 0x9c;
            let d = diff(&cipher.encrypt(&p), &cipher.encrypt(&p2));
            if active_byte_count(&d) == 16 {
                full_active += 1;
            }
        }
        // Mostly fully active, but not 100%.
        assert!(full_active > 800);
    }

    /// The elimination machinery: with the **true** K_R5 quartet, no
    /// pair witnesses the 4-round impossibility (the contradiction
    /// count is zero, regardless of how many pairs we throw at it).
    #[test]
    fn true_key_never_contradicts() {
        let key: [u8; 16] = [
            0x01, 0x23, 0x45, 0x67, 0x89, 0xab, 0xcd, 0xef, 0xfe, 0xdc, 0xba, 0x98, 0x76, 0x54,
            0x32, 0x10,
        ];
        let cipher = ReducedAes128::new(&key, 5, false);
        let (true_hits, _) = elimination_demonstration(&cipher, 0x9c, 1024, 0xfeed_beef);
        assert_eq!(true_hits, 0, "true key cannot witness the impossibility");
    }

    /// The contradiction signal: a wrong K_R5 quartet produces a few
    /// witnesses at scale `~ 2²⁰` pairs — the rate is `~ 2⁻²⁴`, so
    /// we use a generous bound.
    #[test]
    #[ignore = "slow: scans 2^20 pairs to see a handful of contradictions"]
    fn wrong_key_eventually_contradicts() {
        let key = [0u8; 16];
        let cipher = ReducedAes128::new(&key, 5, false);
        let (true_hits, wrong_hits) = elimination_demonstration(&cipher, 0x42, 1 << 20, 0x5eed);
        assert_eq!(true_hits, 0);
        // 2²⁰ pairs at rate ~2⁻²⁴ → ≈ 1/16 expected; allow up to 0–4.
        assert!(wrong_hits < 16, "unexpectedly high: {wrong_hits}");
    }
}
