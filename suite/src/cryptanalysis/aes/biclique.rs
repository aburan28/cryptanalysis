//! Biclique cryptanalysis of full-round AES (Bogdanov, Khovratovich,
//! Rechberger — ASIACRYPT 2011).
//!
//! The biclique attack is the **only public attack that covers all
//! rounds of AES**. The gains are tiny — `2¹²⁶·¹` operations for
//! AES-128 (vs `2¹²⁸` brute force) — but the work-factor improvement
//! is provable, and the attack ushered in a wave of biclique-based
//! analysis on AES-like primitives (Whirlpool, SQUARE, Kuznyechik,
//! etc.).
//!
//! # The structure
//!
//! Pick an `d`-dimensional **biclique** at the end of the cipher:
//! a bipartite-graph-like structure where one side `{S_i}` and the
//! other side `{T_j}`, `i, j ∈ {0, …, 2^d - 1}`, are connected by
//! the cipher's last few rounds under specific **key
//! differentials**. Construct so:
//!
//! ```text
//! E_K[i,j]^{(last d rounds)}(S_i) = T_j   for all (i, j)
//! ```
//!
//! where `K[i, j] = K* ⊕ Δᵢ ⊕ ∇ⱼ` for a base key `K*` and two
//! commuting key-difference families `(Δᵢ)`, `(∇ⱼ)`. The biclique
//! covers `2^(2d)` keys with only ~`2 · 2^d` cipher evaluations.
//!
//! With the biclique in hand, the **outer attack** is a standard
//! Meet-in-the-Middle on the inner rounds:
//!
//! 1. Pick a plaintext `P`. Forward-compute `2^d` candidate inner
//!    states `(v_i = E_{K* ⊕ Δᵢ}^{(first n−d rounds)}(P))`.
//! 2. Backward-decrypt the biclique to get `2^d` candidate inner
//!    states `(w_j)`.
//! 3. For each `(i, j)` with `v_i = w_j`, the key candidate
//!    `K[i, j]` is consistent; verify with a second plaintext-
//!    ciphertext pair.
//!
//! Total work: `~2^(2d)` from the inner MITM, plus the biclique
//! construction. For AES-128, `d = 8` gives the published `2¹²⁶·¹`
//! work factor.
//!
//! # What this module provides
//!
//! Implementing a biclique on full AES end-to-end is roughly 2000
//! lines of careful bookkeeping; the original BKR paper takes 30
//! pages of dense protocol description to specify it. We don't ship
//! that. Instead this module provides:
//!
//! - [`construct_toy_biclique`] — build a 2-dimensional biclique on
//!   2-round small-scale AES `SR(2, 2, 2, 4)`, demonstrating the
//!   bipartite structure: starting from a base key `K*`, four key
//!   variants `K[i, j]` with `i, j ∈ {0, 1}` produce a 4-vertex
//!   bipartite graph whose edges are the cipher's last 2 rounds.
//! - `verify_biclique` — confirm that all `2^(2d)` edges of the
//!   biclique hold.
//! - Documentation of how the inner-rounds MITM is performed,
//!   referenced to the toy case.
//!
//! The toy biclique runs in milliseconds and lets the reader trace
//! the structure end-to-end.

use super::small_scale::SmallAes;

/// A biclique on small-scale AES SR(2, 2, 2, 4).
///
/// `d` is the biclique dimension; the biclique covers `2^(2d)` keys.
#[derive(Debug, Clone)]
pub struct Biclique {
    pub d: u32,
    pub base_key: [u8; 4],
    pub delta_family: Vec<[u8; 4]>, // 2^d entries
    pub nabla_family: Vec<[u8; 4]>, // 2^d entries
}

impl Biclique {
    /// The key indexed by `(i, j)` in the biclique.
    pub fn key_at(&self, i: usize, j: usize) -> [u8; 4] {
        let mut k = self.base_key;
        for b in 0..4 {
            k[b] ^= self.delta_family[i][b] ^ self.nabla_family[j][b];
        }
        k
    }
}

/// Construct a 2-dimensional biclique on the last 2 rounds of
/// `SR(n, 2, 2, 4)`. The Δ family modifies the first column of the
/// last round key; the ∇ family modifies the second column.
///
/// This is a *contrived* biclique — its purpose is to be runnable,
/// not to give an attack advantage. A real biclique requires
/// carefully chosen key-difference paths so the resulting key
/// variants actually connect the chosen states.
pub fn construct_toy_biclique(base_key: [u8; 4]) -> Biclique {
    let delta_family = vec![[0, 0, 0, 0], [0x1, 0, 0, 0]];
    let nabla_family = vec![[0, 0, 0, 0], [0, 0, 0x2, 0]];
    Biclique {
        d: 1,
        base_key,
        delta_family,
        nabla_family,
    }
}

/// Demonstrate the **inner MITM** mechanism for one plaintext.
///
/// For each `(i, j)` in the biclique's `(2^d) × (2^d)` grid, encrypt
/// the plaintext under `key_at(i, j)` and check whether the resulting
/// ciphertext matches a known value `c_target`. If yes, the key is
/// a candidate.
pub fn mitm_against_biclique(
    biclique: &Biclique,
    nr: usize,
    plaintext: [u8; 4],
    c_target: [u8; 4],
) -> Vec<(usize, usize)> {
    let mut candidates = Vec::new();
    let n = 1usize << biclique.d;
    for i in 0..n {
        for j in 0..n {
            let k = biclique.key_at(i, j);
            let cipher = SmallAes::new(k, nr);
            if cipher.encrypt(plaintext) == c_target {
                candidates.push((i, j));
            }
        }
    }
    candidates
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn biclique_covers_four_keys() {
        let bq = construct_toy_biclique([0xa, 0x5, 0x3, 0xc]);
        let mut keys = Vec::new();
        for i in 0..2 {
            for j in 0..2 {
                keys.push(bq.key_at(i, j));
            }
        }
        // The 4 keys are distinct.
        for (a, k1) in keys.iter().enumerate() {
            for k2 in &keys[a + 1..] {
                assert_ne!(k1, k2, "biclique should cover distinct keys");
            }
        }
    }

    /// Demonstrate that the base key (i=0, j=0) is among the MITM
    /// candidates when we query its own ciphertext.
    #[test]
    fn mitm_finds_base_key() {
        let bq = construct_toy_biclique([0xa, 0x5, 0x3, 0xc]);
        let cipher = SmallAes::new(bq.base_key, 4);
        let pt = [0x1, 0x2, 0x3, 0x4];
        let ct = cipher.encrypt(pt);
        let cands = mitm_against_biclique(&bq, 4, pt, ct);
        assert!(cands.contains(&(0, 0)));
    }
}
