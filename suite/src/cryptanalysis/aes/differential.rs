//! Differential cryptanalysis of reduced-round AES.
//!
//! Differential cryptanalysis (Biham-Shamir, 1990) tracks how an XOR
//! difference between two plaintexts propagates through the cipher.
//! Block ciphers like DES, AES, and most modern designs are evaluated
//! partly on how *poorly* differences propagate — i.e., how low the
//! probability of any specific input difference Δ producing any
//! specific output difference is.
//!
//! For AES this property is excellent. Its S-box has maximum
//! differential probability `4/256 = 2⁻⁶` (out of an ideal lower bound
//! of `2⁻⁸`), and the MixColumns matrix has *branch number* 5: any
//! one-byte input difference into a column produces a column whose
//! four output bytes are all nonzero. Together they give the
//! "wide-trail" bound: any two-round differential characteristic has
//! at least **five active S-boxes**, so its probability is at most
//! `(2⁻⁶)⁵ = 2⁻³⁰`. Over four rounds that gives `2⁻¹⁵⁰` — already
//! enough to make full-AES differential cryptanalysis hopeless.
//!
//! What this module provides:
//!
//! 1. [`aes_sbox_ddt`] — the full Differential Distribution Table for
//!    the AES S-box. Each entry `DDT[α][β]` is the number of inputs
//!    `x` such that `S(x) ⊕ S(x ⊕ α) = β`.
//! 2. [`max_differential_probability`] — the headline `4/256` result,
//!    derived by scanning the DDT.
//! 3. [`propagate_one_round`] — deterministic difference propagation
//!    through ShiftRows + MixColumns (the linear half of a round). The
//!    nonlinear S-box step is non-deterministic from a difference
//!    point of view, which is *why* differential probability matters.
//! 4. [`key_recovery_two_round`] — the canonical 2-round
//!    differential attack: a single-byte input difference becomes a
//!    one-column-active difference after the first round, so the
//!    attacker can identify candidate last-round key bytes by
//!    checking whether the resulting ciphertext-pair differences are
//!    consistent with a one-byte-active state before SubBytes.
//!
//! # The 2-round attack in detail
//!
//! 2-round AES is: pre-whitening AddRoundKey → full round 1
//! (SB-SR-MC-AK) → final round 2 (SB-SR-AK, no MC).
//!
//! Pick input difference Δ_in = `(α, 0, 0, …, 0)` — only byte 0 active.
//!
//! Track the difference forward, byte position labels `(col, row)`
//! with column-major flat index `4·col + row`:
//!
//! | After step          | Active bytes (flat indices) | Difference pattern               |
//! |---------------------|-----------------------------|----------------------------------|
//! | AK (pre)            | {0}                         | `α`                              |
//! | SB R1               | {0}                         | `β` (some β with `DDT[α][β]>0`)  |
//! | SR R1               | {0}                         | `β` (row 0 unmoved)              |
//! | MC R1               | {0,1,2,3}                   | `(2β, β, β, 3β)` in column 0     |
//! | AK R1               | {0,1,2,3}                   | same                             |
//! | SB R2               | {0,1,2,3}                   | `(γ₀, γ₁, γ₂, γ₃)` — DDT-random  |
//! | SR R2               | {0, 7, 10, 13}              | shuffled across columns          |
//! | AK R2               | {0, 7, 10, 13}              | same — these are the active ct'  |
//!
//! So the ciphertext difference is concentrated in exactly four bytes:
//! 0, 7, 10, 13.
//!
//! Key recovery: for each pair `(P, P⊕Δ_in)`, the attacker observes
//! `(C, C')`. For each candidate value `k` of `K_R2[pos]` at one of the
//! four active byte positions, inverting AddRoundKey and SubBytes gives
//! a candidate for the difference at that position **before SB R2**.
//! For the *correct* key, that pre-SB difference equals `2β`, `β`,
//! `β`, or `3β` (depending on position), where `β` itself satisfies
//! `DDT[α][β] > 0`. For an arbitrary wrong key, the recovered
//! difference is essentially uniform over `GF(2⁸)\{0}`, so it lands in
//! `DDT[α][·]`'s support with probability ≈ 127/255 ≈ 1/2.
//!
//! Each pair therefore filters wrong keys by roughly a factor of 2.
//! With `N` pairs, expected false positives per byte ≈ `256 · 2⁻ᴺ`.
//! `N = 16` already drives that below 1; the attack uses 24 pairs by
//! default for a comfortable margin.

use super::reduced::{ReducedAes128, INV_SBOX, SBOX};

/// 256×256 differential distribution table.
pub type AesDdt = Vec<Vec<u16>>;

/// Compute the AES S-box DDT: `DDT[α][β] = |{x : S(x)⊕S(x⊕α) = β}|`.
///
/// Properties verified by the tests:
///
/// - Row sums: every row sums to 256 (over all `x`, `S(x)⊕S(x⊕α)`
///   takes some value).
/// - Even entries: `DDT[α][β]` is always even, because if `x` is a
///   solution then so is `x ⊕ α`.
/// - `DDT[0][0] = 256` and `DDT[0][β] = 0` for `β ≠ 0`.
/// - `max(DDT[α][β]) = 4` for `α ≠ 0` — the AES S-box's headline
///   "differential uniformity 4" property.
pub fn aes_sbox_ddt() -> AesDdt {
    let mut t = vec![vec![0u16; 256]; 256];
    for a in 0..256usize {
        for x in 0..256usize {
            let y = x ^ a;
            let beta = (SBOX[x] ^ SBOX[y]) as usize;
            t[a][beta] += 1;
        }
    }
    t
}

/// Returns `(α, β, count)` for the maximum DDT entry over `α ≠ 0`.
/// The headline value is `count = 4`, giving max differential
/// probability `4/256 = 2⁻⁶`.
pub fn max_differential_probability(ddt: &AesDdt) -> (u8, u8, u16) {
    let mut best = (0u8, 0u8, 0u16);
    for (a, row) in ddt.iter().enumerate().skip(1) {
        for (b, &c) in row.iter().enumerate() {
            if c > best.2 {
                best = (a as u8, b as u8, c);
            }
        }
    }
    best
}

/// Record of one round's effect on a difference.
#[derive(Debug, Clone, Copy)]
pub struct RoundDifference {
    pub before_sbox: [u8; 16],
    /// After SubBytes the difference is value-dependent — we just
    /// record the **active byte positions**, not the actual byte
    /// values.
    pub after_sbox_active: [bool; 16],
    pub after_shiftrows_active: [bool; 16],
    /// Set only when the round includes MixColumns. The actual byte
    /// values depend on the post-SB difference, so we record the
    /// *active pattern* and leave value-tracking to the caller.
    pub after_mixcolumns_active: [bool; 16],
}

/// Propagate a difference pattern one round, recording the **activity
/// pattern** (active = "could be nonzero") at each substep.
///
/// MixColumns has branch number 5: a column with `k > 0` active input
/// bytes has at least `5-k` active output bytes; with `k = 1` that
/// means `4` active output bytes.
pub fn propagate_one_round(diff_in: &[u8; 16], include_mixcolumns: bool) -> RoundDifference {
    let active_in: [bool; 16] = {
        let mut a = [false; 16];
        for i in 0..16 {
            a[i] = diff_in[i] != 0;
        }
        a
    };
    // SubBytes preserves activity (nonzero in ⇒ nonzero out).
    let after_sb = active_in;
    // ShiftRows: byte at column c, row r → column (c - r) mod 4.
    let mut after_sr = [false; 16];
    for c in 0..4 {
        for r in 0..4 {
            if after_sb[4 * c + r] {
                let new_c = (c + 4 - r) % 4;
                after_sr[4 * new_c + r] = true;
            }
        }
    }
    let after_mc = if include_mixcolumns {
        let mut a = [false; 16];
        for c in 0..4 {
            let any_active = (0..4).any(|r| after_sr[4 * c + r]);
            if any_active {
                for r in 0..4 {
                    a[4 * c + r] = true; // branch number 5 ⇒ entire column active
                }
            }
        }
        a
    } else {
        after_sr
    };
    RoundDifference {
        before_sbox: *diff_in,
        after_sbox_active: after_sb,
        after_shiftrows_active: after_sr,
        after_mixcolumns_active: after_mc,
    }
}

/// GF(2⁸) multiplication using the AES polynomial. Mirrors the
/// MixColumns coefficients used in the attack.
fn gmul(mut a: u8, mut b: u8) -> u8 {
    let mut p = 0u8;
    for _ in 0..8 {
        if b & 1 != 0 {
            p ^= a;
        }
        let hi = a & 0x80 != 0;
        a <<= 1;
        if hi {
            a ^= 0x1b;
        }
        b >>= 1;
    }
    p
}

/// Multiplicative inverse in GF(2⁸) using Fermat's little theorem:
/// `a^254 = a⁻¹` for nonzero `a`. Standard square-and-multiply.
fn ginv(a: u8) -> u8 {
    if a == 0 {
        return 0;
    }
    let mut result = 1u8;
    let mut base = a;
    let mut exp = 254u16;
    while exp > 0 {
        if exp & 1 == 1 {
            result = gmul(result, base);
        }
        base = gmul(base, base);
        exp >>= 1;
    }
    result
}

/// One chosen-plaintext pair with input difference Δ_in = `(α, 0, …, 0)`.
#[derive(Debug, Clone, Copy)]
pub struct DiffPair {
    pub p0: [u8; 16],
    pub p1: [u8; 16],
    pub c0: [u8; 16],
    pub c1: [u8; 16],
}

/// Outcome of the 2-round differential key recovery.
#[derive(Debug, Clone)]
pub struct DifferentialAttackReport {
    pub pairs_used: usize,
    /// Recovered last-round key bytes at the four active positions
    /// (column-major flat indices 0, 7, 10, 13).
    pub key_bytes: [(usize, u8); 4],
    /// Number of `(k, pair)` test combinations evaluated.
    pub trial_count: usize,
}

/// 2-round differential key recovery on AES-128 with `nr = 2`,
/// `final_mix_columns = false`. Recovers the four active bytes of the
/// last round key independently.
///
/// `alpha` is the input difference value at byte 0. `pairs` are
/// chosen-plaintext pairs of the form `(P, P ⊕ (α, 0, …, 0))` with
/// the corresponding ciphertexts.
///
/// Returns `Err(())` if at the end of `pairs` more than one candidate
/// remains for any position — meaning the caller should supply more
/// pairs.
pub fn key_recovery_two_round(
    alpha: u8,
    pairs: &[DiffPair],
    ddt: &AesDdt,
) -> Result<DifferentialAttackReport, &'static str> {
    // Active byte positions in the ciphertext difference, and the
    // MixColumns coefficient that scales β at the corresponding row
    // of column 0 before SR R2. Row 0 ⇒ 2β; row 1 ⇒ β; row 2 ⇒ β;
    // row 3 ⇒ 3β.
    //
    // After SR R2 the bytes land at the flat indices below.
    let active: [(usize, u8); 4] = [
        (0, 2),  // (col=0, row=0) ← came from col-0, row-0, coef 2
        (13, 1), // (col=3, row=1) ← came from col-0, row=1, coef 1
        (10, 1), // (col=2, row=2) ← came from col-0, row=2, coef 1
        (7, 3),  // (col=1, row=3) ← came from col-0, row=3, coef 3
    ];

    let mut trial_count = 0usize;
    let mut recovered = [(0usize, 0u8); 4];

    for (slot, &(pos, coef)) in active.iter().enumerate() {
        let coef_inv = ginv(coef);
        let mut candidates: Vec<u8> = (0u16..256).map(|v| v as u8).collect();

        for pair in pairs.iter() {
            if candidates.len() == 1 {
                break;
            }
            candidates.retain(|&k| {
                trial_count += 1;
                let v0 = INV_SBOX[(pair.c0[pos] ^ k) as usize];
                let v1 = INV_SBOX[(pair.c1[pos] ^ k) as usize];
                let delta = v0 ^ v1;
                if delta == 0 {
                    // Active byte must have nonzero difference for the
                    // right key.
                    return false;
                }
                // β is δ scaled by the inverse of the MC coefficient.
                let beta = gmul(delta, coef_inv);
                ddt[alpha as usize][beta as usize] > 0
            });
        }

        match candidates.len() {
            1 => recovered[slot] = (pos, candidates[0]),
            0 => return Err("no candidate survived — α/pairs inconsistent"),
            _ => return Err("ambiguous — supply more pairs"),
        }
    }

    Ok(DifferentialAttackReport {
        pairs_used: pairs.len(),
        key_bytes: recovered,
        trial_count,
    })
}

/// Build `n_pairs` chosen-plaintext pairs with input difference
/// `(alpha, 0, …, 0)`. Uses an LCG so the test is deterministic; for
/// research use, replace with an OS-backed RNG.
pub fn build_pairs(cipher: &ReducedAes128, alpha: u8, n_pairs: usize, seed: u64) -> Vec<DiffPair> {
    let mut state = seed;
    let mut next_byte = || {
        state = state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        (state >> 33) as u8
    };
    let mut pairs = Vec::with_capacity(n_pairs);
    for _ in 0..n_pairs {
        let mut p0 = [0u8; 16];
        for byte in p0.iter_mut() {
            *byte = next_byte();
        }
        let mut p1 = p0;
        p1[0] ^= alpha;
        let c0 = cipher.encrypt(&p0);
        let c1 = cipher.encrypt(&p1);
        pairs.push(DiffPair { p0, p1, c0, c1 });
    }
    pairs
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ddt_row_zero() {
        let ddt = aes_sbox_ddt();
        assert_eq!(ddt[0][0], 256);
        for b in 1..256 {
            assert_eq!(ddt[0][b], 0, "DDT[0][{b}] should be 0");
        }
    }

    #[test]
    fn ddt_rows_sum_to_256() {
        let ddt = aes_sbox_ddt();
        for row in &ddt {
            assert_eq!(row.iter().map(|&v| v as u32).sum::<u32>(), 256);
        }
    }

    #[test]
    fn ddt_entries_even() {
        let ddt = aes_sbox_ddt();
        for row in &ddt {
            for &v in row {
                assert_eq!(v % 2, 0);
            }
        }
    }

    #[test]
    fn aes_max_dp_is_four() {
        let ddt = aes_sbox_ddt();
        let (_, _, c) = max_differential_probability(&ddt);
        assert_eq!(c, 4, "AES S-box has differential uniformity 4");
    }

    /// Each row α ≠ 0 has exactly 127 nonzero β entries with value 2
    /// and (some) of value 4 (the standard AES S-box DDT structure).
    #[test]
    fn ddt_row_structure() {
        let ddt = aes_sbox_ddt();
        for a in 1..256 {
            let nonzero = ddt[a].iter().filter(|&&v| v > 0).count();
            assert_eq!(nonzero, 127, "row {a} should have 127 nonzero entries");
        }
    }

    #[test]
    fn one_active_byte_propagates_to_full_column() {
        let mut diff = [0u8; 16];
        diff[0] = 0x42;
        let r = propagate_one_round(&diff, true);
        // After SR + MC, the single active byte at (0,0) becomes a
        // full active column 0.
        for r_ in 0..4 {
            assert!(r.after_mixcolumns_active[r_]);
        }
        // Other columns remain inactive.
        for c in 1..4 {
            for r_ in 0..4 {
                assert!(!r.after_mixcolumns_active[4 * c + r_]);
            }
        }
    }

    #[test]
    fn gf_inv_round_trips() {
        for a in 1..=255u8 {
            assert_eq!(gmul(a, ginv(a)), 1);
        }
    }

    #[test]
    fn two_round_differential_recovers_active_bytes() {
        // Deterministic random key.
        let key: [u8; 16] = [
            0x91, 0x4f, 0x6d, 0xa1, 0xc7, 0x83, 0x05, 0xbb, 0x29, 0x57, 0xee, 0x10, 0x4d, 0x82,
            0x6c, 0xfa,
        ];
        let cipher = ReducedAes128::new(&key, 2, false);
        let alpha = 0x73u8;
        let ddt = aes_sbox_ddt();
        let pairs = build_pairs(&cipher, alpha, 24, 0xdead_beef_cafe);
        let report = key_recovery_two_round(alpha, &pairs, &ddt)
            .expect("attack should succeed with 24 pairs");

        // Verify the recovered bytes match the true last round key.
        let true_k = cipher.round_key(cipher.nr);
        for &(pos, k) in &report.key_bytes {
            let c = pos / 4;
            let r = pos % 4;
            assert_eq!(k, true_k[c][r], "wrong byte at flat position {pos}");
        }
    }

    /// Sanity: the active byte positions predicted by the attack are
    /// exactly where the ciphertext difference shows up empirically.
    #[test]
    fn ciphertext_difference_active_pattern_matches_theory() {
        let key = [0u8; 16];
        let cipher = ReducedAes128::new(&key, 2, false);
        let alpha = 0x11u8;
        let pairs = build_pairs(&cipher, alpha, 200, 0x1234_5678_abcd);
        // Across all pairs, the empirical set of "positions with any
        // nonzero difference in some pair" must equal {0, 7, 10, 13}.
        let mut seen = [false; 16];
        for pair in &pairs {
            for i in 0..16 {
                if pair.c0[i] != pair.c1[i] {
                    seen[i] = true;
                }
            }
        }
        let expected = [0usize, 7, 10, 13];
        for i in 0..16 {
            let want = expected.contains(&i);
            assert_eq!(
                seen[i], want,
                "position {i} expected active={want}, got active={}",
                seen[i]
            );
        }
    }
}
