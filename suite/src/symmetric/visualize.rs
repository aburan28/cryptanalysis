//! **Symmetric-cipher visualizations** — dataflow diagrams for every
//! mode of operation, AES round-by-round state trace, ChaCha20
//! quarter-round state evolution, ECB-penguin demo.

use crate::cryptanalysis::aes::reduced::ReducedAes128;
use crate::visualize::{
    format_bitmap_shaded, format_recovery_progress, format_round_bars, format_state_grid,
};

// ── ECB penguin: show how ECB leaks repeated plaintext blocks ────────

/// Render the canonical "ECB penguin" demonstration as ASCII art.
/// We synthesize a `width × height` bitmap with a repeating
/// rectangular pattern, encrypt it under AES-ECB and AES-CBC, and
/// render both ciphertexts as shaded bitmaps side by side.
///
/// ECB output preserves the pattern; CBC output looks like noise.
pub fn demo_ecb_penguin(width: usize, height: usize) -> String {
    use crate::symmetric::aes::{encrypt_block, AesKey};
    let mut s = String::from("# ECB penguin: structure leakage demo\n\n");
    s.push_str(
        "Synthesize a `bitmap` with a repeating pattern (a rectangular block of 0xFFs \
         on a 0x00 background), then ECB-encrypt it (block-by-block).  ECB preserves \
         block repetition → the pattern still leaks.  CBC randomises every block.\n\n",
    );
    // Build the bitmap.
    let mut pixels = vec![0u8; width * height];
    let _block_size = 4;
    for r in (height / 4)..(3 * height / 4) {
        for c in (width / 4)..(3 * width / 4) {
            pixels[r * width + c] = 0xFF;
        }
    }
    s.push_str(&format_bitmap_shaded(
        &pixels,
        width,
        height,
        "Original plaintext",
    ));

    // ECB-encrypt as bytes (we treat groups of 16 pixels as one block).
    let key = AesKey::new(&[0x42u8; 16]).unwrap();
    let mut ecb = pixels.clone();
    // Pad to multiple of 16
    while !ecb.len().is_multiple_of(16) {
        ecb.push(0);
    }
    let mut ecb_ct = Vec::with_capacity(ecb.len());
    for chunk in ecb.chunks_exact(16) {
        let mut b = [0u8; 16];
        b.copy_from_slice(chunk);
        let c = encrypt_block(&b, &key);
        ecb_ct.extend_from_slice(&c);
    }
    ecb_ct.truncate(pixels.len());
    s.push_str(&format_bitmap_shaded(
        &ecb_ct,
        width,
        height,
        "ECB ciphertext (pattern still visible)",
    ));

    // CBC for comparison.
    use crate::symmetric::aes_cbc::aes_cbc_encrypt;
    let iv = [0u8; 16];
    let cbc_ct = aes_cbc_encrypt(&pixels, &key, &iv);
    let cbc_view: Vec<u8> = cbc_ct.iter().take(pixels.len()).cloned().collect();
    s.push_str(&format_bitmap_shaded(
        &cbc_view,
        width,
        height,
        "CBC ciphertext (pattern hidden)",
    ));
    s
}

// ── Mode dataflow diagrams ───────────────────────────────────────────

/// Render block-by-block dataflow diagrams for every shipping mode.
pub fn demo_mode_dataflows() -> String {
    let mut s = String::from("# Block-cipher mode dataflow diagrams\n\n");

    s.push_str("## ECB — Electronic Codebook\n\n");
    s.push_str(
        "```\n  P_0 ──► E_K ──► C_0\n  P_1 ──► E_K ──► C_1\n  P_2 ──► E_K ──► C_2\n  ...\n```\n",
    );
    s.push_str(
        "_No chaining, no IV.  Identical plaintext blocks → identical ciphertext blocks (broken)._\n\n",
    );

    s.push_str("## CBC — Cipher Block Chaining\n\n");
    s.push_str(
        "```\n  P_0 ──┐                       C_0 ──┐\n  IV  ──⊕──► E_K ──► C_0    P_1 ──⊕──► E_K ──► C_1\n         ↓                       ↓\n        C_0 (feeds next)        C_1 (feeds next)\n```\n",
    );
    s.push_str(
        "_Each block's ciphertext XORed into the next block's plaintext.  Padding-oracle risk._\n\n",
    );

    s.push_str("## CTR — Counter\n\n");
    s.push_str(
        "```\n  E_K(N||0) ──⊕── P_0 ──► C_0\n  E_K(N||1) ──⊕── P_1 ──► C_1\n  E_K(N||2) ──⊕── P_2 ──► C_2\n  ...\n```\n",
    );
    s.push_str(
        "_Stream-cipher mode: encrypt counter, XOR with plaintext.  Trivially parallel.  Nonce reuse catastrophic._\n\n",
    );

    s.push_str("## CFB — Cipher Feedback\n\n");
    s.push_str(
        "```\n  IV  ──► E_K ──┐                C_0 ──► E_K ──┐\n                ⊕──► P_0 = C_0                 ⊕──► P_1 ⊕ E_K(C_0) = C_1\n  P_0 ──────────┘                P_1 ──────────┘\n```\n",
    );
    s.push_str(
        "_Self-synchronising: corrupted ciphertext affects next block only, then recovers._\n\n",
    );

    s.push_str("## OFB — Output Feedback\n\n");
    s.push_str(
        "```\n  IV ──► E_K ──► O_1 ──► E_K ──► O_2 ──► E_K ──► O_3\n                  ↓              ↓              ↓\n           P_0 ──⊕── C_0     P_1 ──⊕── C_1     P_2 ──⊕── C_2\n```\n",
    );
    s.push_str(
        "_Keystream pre-computable.  No error propagation.  Nonce reuse leaks XOR of plaintexts._\n\n",
    );

    s.push_str("## GCM — Galois/Counter Mode (AEAD)\n\n");
    s.push_str(
        "```\n  IV ──► CTR encrypt P → C ──┐\n                              ├──► GHASH (over AAD || C) ──► T (tag)\n  AAD ───────────────────────┘\n```\n",
    );
    s.push_str(
        "_CTR for confidentiality + GHASH(GF(2^128)) for authentication.  Nonce reuse catastrophic._\n\n",
    );

    s.push_str("## CCM — Counter + CBC-MAC (AEAD)\n\n");
    s.push_str(
        "```\n   B_0 = (flags || nonce || pt_len)\n  ┌──► CBC-MAC chain (B_0, AAD, P) ──► T\n  │\n  └──► CTR encrypt P ──► C\n\n  output = C || (T ⊕ E_K(A_0))\n```\n",
    );
    s.push_str("_Used in 802.11i / Bluetooth.  Tag verified before decryption._\n\n");

    s.push_str("## SIV — Synthetic IV (deterministic AEAD)\n\n");
    s.push_str(
        "```\n  K = K1 || K2\n  S2V(K1, AAD..., P) ──► V  (the synthetic IV / tag)\n                          ↓\n  CTR_{K2}(V) encrypt P ──► C\n  output = V || C\n```\n",
    );
    s.push_str(
        "_RFC 5297.  Misuse-resistant: same (K, AAD, P) → same C (key+nonce reuse not catastrophic)._\n\n",
    );

    s.push_str("## XTS — Disk-encryption mode\n\n");
    s.push_str(
        "```\n  T_0 = E_{K2}(tweak)\n  T_i = T_0 · α^i in GF(2^128)\n  C_i = E_{K1}(P_i ⊕ T_i) ⊕ T_i\n```\n",
    );
    s.push_str("_Different tweak per sector, length-preserving with ciphertext stealing._\n\n");

    s.push_str("## KW — Key Wrap\n\n");
    s.push_str(
        "```\n  A = IV (0xA6...)\n  R_i = P_i\n  Loop 6 times, for each R_i:\n      B = E_K(A || R_i)\n      A = MSB(B) ⊕ counter\n      R_i = LSB(B)\n  output = A || R_1 || ... || R_n\n```\n",
    );
    s.push_str("_RFC 3394.  Deterministic, no IV needed (high-entropy input)._\n\n");

    s
}

// ── AES state evolution through rounds ───────────────────────────────

/// Render the AES-128 state at the start of each round for a given
/// plaintext + key.  Shows how the state diffuses from a structured
/// input through 10 rounds to a random-looking output.
pub fn demo_aes_state_trace(plaintext: &[u8; 16], key: &[u8; 16]) -> String {
    use crate::cryptanalysis::aes::reduced::RoundOps;
    let mut s = String::from("# AES-128 round-by-round state trace\n\n");
    s.push_str("Plaintext:\n\n");
    s.push_str(&format_state_grid(plaintext, ""));
    s.push_str("\nKey:\n\n");
    s.push_str(&format_state_grid(key, ""));
    s.push('\n');
    let cipher = ReducedAes128::new(key, 10, false);
    let mut state = bytes_to_state(plaintext);
    RoundOps::add_round_key(&mut state, &cipher.round_key(0));
    s.push_str("## After round 0 (initial AddRoundKey)\n\n");
    s.push_str(&format_state_grid(&state_to_bytes(&state), ""));
    for round in 1..=10 {
        s.push_str(&format!("\n## After round {}\n\n", round));
        RoundOps::sub_bytes(&mut state);
        RoundOps::shift_rows(&mut state);
        if round < 10 {
            RoundOps::mix_columns(&mut state);
        }
        RoundOps::add_round_key(&mut state, &cipher.round_key(round));
        s.push_str(&format_state_grid(&state_to_bytes(&state), ""));
    }
    s
}

fn bytes_to_state(block: &[u8; 16]) -> [[u8; 4]; 4] {
    let mut st = [[0u8; 4]; 4];
    for c in 0..4 {
        for r in 0..4 {
            st[c][r] = block[4 * c + r];
        }
    }
    st
}

fn state_to_bytes(st: &[[u8; 4]; 4]) -> [u8; 16] {
    let mut out = [0u8; 16];
    for c in 0..4 {
        for r in 0..4 {
            out[4 * c + r] = st[c][r];
        }
    }
    out
}

// ── ChaCha20 quarter-round visualization ─────────────────────────────

/// Render the ChaCha20 4×4 word state at the start, after each
/// quarter-round in the first round, and at the end.  Each cell
/// shows the 32-bit word; we additionally mark "active" cells where
/// the word changes between snapshots.
pub fn demo_chacha20_state() -> String {
    let mut s = String::from("# ChaCha20 4×4 word-state evolution (1 round)\n\n");
    s.push_str(
        "Initial state: constants `expand 32-byte k`, 256-bit key (here all-zero), \
         32-bit counter, 96-bit nonce.  We render the state at the start, after \
         the 4 column quarter-rounds, and after the 4 diagonal quarter-rounds.\n\n",
    );
    let key = [0u8; 32];
    let nonce = [0u8; 12];
    let counter = 0u32;
    let mut state = [0u32; 16];
    // ChaCha20 initial state.
    state[0] = 0x61707865;
    state[1] = 0x3320646e;
    state[2] = 0x79622d32;
    state[3] = 0x6b206574;
    for i in 0..8 {
        state[4 + i] =
            u32::from_le_bytes([key[4 * i], key[4 * i + 1], key[4 * i + 2], key[4 * i + 3]]);
    }
    state[12] = counter;
    for i in 0..3 {
        state[13 + i] = u32::from_le_bytes([
            nonce[4 * i],
            nonce[4 * i + 1],
            nonce[4 * i + 2],
            nonce[4 * i + 3],
        ]);
    }
    s.push_str("## Initial state\n\n");
    s.push_str(&render_chacha_state(&state));
    // Column rounds.
    let qr = |s: &mut [u32; 16], a: usize, b: usize, c: usize, d: usize| {
        s[a] = s[a].wrapping_add(s[b]);
        s[d] ^= s[a];
        s[d] = s[d].rotate_left(16);
        s[c] = s[c].wrapping_add(s[d]);
        s[b] ^= s[c];
        s[b] = s[b].rotate_left(12);
        s[a] = s[a].wrapping_add(s[b]);
        s[d] ^= s[a];
        s[d] = s[d].rotate_left(8);
        s[c] = s[c].wrapping_add(s[d]);
        s[b] ^= s[c];
        s[b] = s[b].rotate_left(7);
    };
    qr(&mut state, 0, 4, 8, 12);
    qr(&mut state, 1, 5, 9, 13);
    qr(&mut state, 2, 6, 10, 14);
    qr(&mut state, 3, 7, 11, 15);
    s.push_str("\n## After 4 column quarter-rounds\n\n");
    s.push_str(&render_chacha_state(&state));
    qr(&mut state, 0, 5, 10, 15);
    qr(&mut state, 1, 6, 11, 12);
    qr(&mut state, 2, 7, 8, 13);
    qr(&mut state, 3, 4, 9, 14);
    s.push_str("\n## After 4 diagonal quarter-rounds (one full round complete)\n\n");
    s.push_str(&render_chacha_state(&state));
    s
}

fn render_chacha_state(state: &[u32; 16]) -> String {
    let mut s = String::from("```\n");
    for r in 0..4 {
        for c in 0..4 {
            s.push_str(&format!(" {:08x}", state[4 * r + c]));
        }
        s.push('\n');
    }
    s.push_str("```\n");
    s
}

// ── Avalanche heat-map for a generic cipher ──────────────────────────

/// Render an avalanche heat-map: for a 1-round cipher, plot
/// `Pr[output bit j flips | input bit i flipped]` for i, j in
/// `[0, 16)` (first 16 bits).
pub fn demo_avalanche_matrix(rounds: usize) -> String {
    let mut s = format!("# AES-{} avalanche matrix (first 16 bits)\n\n", rounds);
    s.push_str(
        "Cell `[i, j]`: probability that flipping input bit `i` flips output bit `j`.  \
         An ideal cipher gives `0.5` uniformly; reduced-round AES shows structure.\n\n",
    );
    let cipher = ReducedAes128::new(&[0u8; 16], rounds, true);
    let n_bits = 16;
    let trials = 256;
    let mut mat = vec![vec![0.0f64; n_bits]; n_bits];
    for i in 0..n_bits {
        for _ in 0..trials {
            let mut p1 = [0u8; 16];
            for b in p1.iter_mut() {
                *b = rand::random();
            }
            let mut p2 = p1;
            let byte_i = i / 8;
            let bit_i = i % 8;
            p2[byte_i] ^= 1 << bit_i;
            let c1 = cipher.encrypt(&p1);
            let c2 = cipher.encrypt(&p2);
            for j in 0..n_bits {
                let byte_j = j / 8;
                let bit_j = j % 8;
                if (c1[byte_j] ^ c2[byte_j]) >> bit_j & 1 == 1 {
                    mat[i][j] += 1.0;
                }
            }
        }
        for j in 0..n_bits {
            mat[i][j] /= trials as f64;
        }
    }
    s.push_str(&crate::visualize::format_matrix_heatmap(
        &mat,
        "Avalanche probability matrix",
        true,
    ));
    s
}

// ── Aggregate ────────────────────────────────────────────────────────

/// Run every symmetric visual demo.
pub fn run_all_symmetric_demos() -> String {
    let mut s = String::new();
    s.push_str("# Symmetric-cipher visual-demo bundle\n\n---\n\n");
    s.push_str(&demo_ecb_penguin(32, 16));
    s.push_str("\n---\n\n");
    s.push_str(&demo_mode_dataflows());
    s.push_str("\n---\n\n");
    s.push_str(&demo_aes_state_trace(b"YELLOW SUBMARINE", &[0x42u8; 16]));
    s.push_str("\n---\n\n");
    s.push_str(&demo_chacha20_state());
    s.push_str("\n---\n\n");
    s.push_str(&demo_avalanche_matrix(1));
    s.push_str("\n---\n\n");
    s.push_str(&demo_avalanche_matrix(2));
    s.push_str("\n---\n\n");
    s.push_str(&demo_avalanche_matrix(10));
    let _ = format_recovery_progress(0, 1, "");
    let _ = format_round_bars(&[1, 2], "", 10);
    s
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ecb_penguin_renders() {
        let s = demo_ecb_penguin(16, 8);
        assert!(s.contains("ECB penguin"));
        assert!(s.contains("Original plaintext"));
        assert!(s.contains("ECB ciphertext"));
        assert!(s.contains("CBC ciphertext"));
    }

    #[test]
    fn mode_dataflows_render_all() {
        let s = demo_mode_dataflows();
        for mode in &[
            "ECB", "CBC", "CTR", "CFB", "OFB", "GCM", "CCM", "SIV", "XTS", "KW",
        ] {
            assert!(s.contains(mode), "missing {}", mode);
        }
    }

    #[test]
    fn aes_state_trace_has_11_states() {
        let s = demo_aes_state_trace(b"YELLOW SUBMARINE", &[0u8; 16]);
        // 1 plaintext + 1 key + 1 initial AddRoundKey + 10 rounds = 13 grids.
        let grid_count = s.matches("┌────┬────┬────┬────┐").count();
        assert_eq!(grid_count, 13);
    }

    #[test]
    fn chacha_state_renders_three_snapshots() {
        let s = demo_chacha20_state();
        assert!(s.contains("Initial state"));
        assert!(s.contains("column quarter-rounds"));
        assert!(s.contains("diagonal quarter-rounds"));
    }

    #[test]
    fn avalanche_matrix_renders() {
        let s = demo_avalanche_matrix(1);
        assert!(s.contains("avalanche matrix"));
        assert!(s.contains("16 × 16") || s.contains("Matrix: 16 × 16"));
    }

    #[test]
    fn aggregate_runs_clean() {
        let s = run_all_symmetric_demos();
        assert!(s.contains("ECB penguin"));
        assert!(s.contains("Block-cipher mode dataflow"));
        assert!(s.contains("round-by-round"));
        assert!(s.contains("ChaCha20"));
    }

    #[test]
    #[ignore]
    fn demo_all_symmetric_visuals() {
        println!("{}", run_all_symmetric_demos());
    }
}
